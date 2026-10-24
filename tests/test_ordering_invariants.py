"""The rules every ordering must obey, for every type and every pair of types.

`operations.py` builds `>`, `<`, `>=`, `<=` from each type's `compare`, and `=`
from `equals`. That only works if:

* swapping the two sides flips the answer: `a.compare(b) == -b.compare(a)`;
* `compare` is 0 exactly when `equals` is true (equal means equal, nothing less);
* the order is transitive, so sorting is well defined.

Collections order by size first (more rows/keys/nodes is greater), then by
their content in a canonical sorted order, so how a value happened to be built
(column order, key order, insertion order) never changes the answer.
"""

import itertools
import random
from functools import cmp_to_key

import pytest
from lynx_values import lx

from lynx.errors.errors import LynxNotImplemented
from lynx.runtime import operations
from lynx.types import Boolean, Graph, Map, Number, Table, Text, Void


def table(**columns):
    return Table([(name, [lx(cell) for cell in cells]) for name, cells in columns.items()])


def graph(nodes, edges=()):
    result = Graph()
    for node_id in nodes:
        result.nodes[node_id] = Void()
    for source, target, *label in edges:
        result.edges[(source, target)] = Text(label[0]) if label else Void()
    return result


def with_values(nodes):
    result = Graph()
    for node_id, value in nodes.items():
        result.nodes[node_id] = lx(value)
    return result


SIMPLE = [Void(), Boolean(False), Boolean(True), Text(""), Text("a"), Text("b"), Number(-1), Number(0), Number(2.5)]

ARRAYS = [lx([]), lx([1]), lx([1, 2]), lx([2, 1]), lx(["a"]), lx([1, "a"]), lx([[1], [2]]), lx([[2], [1]]), lx([None])]

MAPS = [
    lx({}),
    lx({"a": 1}),
    lx({"a": 2}),
    lx({"b": 1}),
    lx({"a": 1, "b": 2}),
    lx({"b": 2, "a": 1}),  # same content, other insertion order
    lx({"a": 1, "b": 3}),
    lx({1: "x", "1": "y"}),
    lx({"1": "y", 1: "x"}),
    lx({None: 1}),
    lx({"a": {"x": 1}}),
    lx({"a": {"x": 2}}),
]

TABLES = [
    Table([]),
    table(a=[1]),
    table(a=[2]),
    table(a=[1, 2]),
    table(b=[1]),
    table(a=[1], b=[2]),
    table(b=[2], a=[1]),  # same content, other column order
    table(a=[1], c=[2]),
    table(b=[1], a=[2]),  # the pair that used to rank each other "greater"
    table(a=[2], c=[1]),
    table(a=["x"], b=[None]),
    table(a=[1], b=[2], c=[3]),
]

GRAPHS = [
    Graph(),
    graph(["a"]),
    graph(["b"]),
    graph(["a", "b"]),
    graph(["b", "a"]),  # same graph, other creation order
    graph(["a", "b"], [("a", "b")]),
    graph(["b", "a"], [("a", "b")]),
    graph(["a", "b"], [("b", "a")]),
    graph(["x", "y"], [("x", "y")]),  # same size as the one above, different content
    graph(["a", "b"], [("a", "b", "l")]),
    graph(["a", "b"], [("a", "b", "m")]),
    with_values({"a": 1}),
    with_values({"a": 2}),
    with_values({"a": [1, 2]}),
]

POOLS = {
    "simple": SIMPLE,
    "array": ARRAYS,
    "map": MAPS,
    "table": TABLES,
    "graph": GRAPHS,
}


def same_type_pairs(pool):
    return [(a, b) for a in pool for b in pool if type(a) is type(b)]


@pytest.mark.parametrize("name", POOLS)
def test_swapping_the_sides_flips_the_answer(name):
    for a, b in same_type_pairs(POOLS[name]):
        assert a.compare(b) == -b.compare(a), f"{a!r} vs {b!r}"


@pytest.mark.parametrize("name", POOLS)
def test_compare_is_zero_exactly_when_equal(name):
    for a, b in same_type_pairs(POOLS[name]):
        assert (a.compare(b) == 0) == a.equals(b).is_true(), f"{a!r} vs {b!r}"


@pytest.mark.parametrize("name", POOLS)
def test_the_order_is_transitive(name):
    pool = [value for value in POOLS[name]]
    for a, b, c in itertools.product(pool, repeat=3):
        if not (type(a) is type(b) is type(c)):
            continue
        if a.compare(b) <= 0 and b.compare(c) <= 0:
            assert a.compare(c) <= 0, f"{a!r} <= {b!r} <= {c!r} but not {a!r} <= {c!r}"


@pytest.mark.parametrize("name", POOLS)
def test_sorting_is_the_same_whatever_the_starting_order(name):
    pool = [value for value in POOLS[name] if type(value) is type(POOLS[name][-1])]
    expected = sorted(pool, key=cmp_to_key(lambda a, b: a.compare(b)))
    for seed in range(20):
        shuffled = list(pool)
        random.Random(seed).shuffle(shuffled)
        got = sorted(shuffled, key=cmp_to_key(lambda a, b: a.compare(b)))
        assert all(x.compare(y) == 0 for x, y in zip(got, expected))


def test_every_pair_of_types_orders_consistently_through_the_operators():
    # `>`, `<`, `>=`, `<=` and `=` as the interpreter evaluates them, mixed types
    # included. A pair the language reports as "not implemented yet" (comparing a
    # void with an array, say) is a documented hole, not a contradiction: skipped.
    everything = [value for pool in POOLS.values() for value in pool]
    checked = 0

    def holds(method, a, b):
        return operations.binary(method, a, b).is_true()

    for a, b in itertools.product(everything, repeat=2):
        try:
            greater, less, equal = holds("greater", a, b), holds("less", a, b), holds("equals", a, b)
            mirrored_less, mirrored_greater = holds("less", b, a), holds("greater", b, a)
            greater_or_equal, lesser_or_equal = holds("greater_or_equal", a, b), holds("lesser_or_equal", a, b)
        except LynxNotImplemented:
            continue
        checked += 1
        assert mirrored_less == greater, f"{a!r} vs {b!r}"
        assert mirrored_greater == less, f"{a!r} vs {b!r}"
        assert not (greater and less), f"{a!r} is both greater and less than {b!r}"
        if equal:
            assert not greater and not less, f"{a!r} = {b!r} but ordered"
            assert greater_or_equal and lesser_or_equal
        if type(a) is type(b):
            assert greater_or_equal == (greater or equal), f"{a!r} vs {b!r}"
    assert checked > len(everything)  # the loop really covered the pairs


# --- the cases that were broken, by name ------------------------------------


def test_tables_with_different_columns_are_not_each_greater():
    one, other = table(b=[1], a=[2]), table(a=[2], c=[1])
    assert one.compare(other) == -other.compare(one) != 0


def test_column_order_never_changes_a_table_comparison():
    assert table(a=[1], b=[2]).compare(table(b=[2], a=[1])) == 0
    assert table(a=[1], b=[2]).equals(table(b=[2], a=[1])).is_true()


def test_bigger_means_greater_before_content_is_looked_at():
    assert table(a=[1, 2]).compare(table(z=[9])) > 0  # more rows wins over a later name
    assert table(a=[1], b=[1]).compare(table(z=[9])) > 0  # same rows, more columns wins
    assert lx({"a": 1, "b": 2}).compare(lx({"z": 9})) > 0
    assert graph(["a", "b"]).compare(graph(["z"])) > 0
    assert graph(["a", "b"], [("a", "b")]).compare(graph(["x", "y"])) > 0  # same nodes, more edges


def test_different_graphs_of_the_same_size_are_not_equal_in_order():
    one, other = graph(["a", "b"], [("a", "b")]), graph(["x", "y"], [("x", "y")])
    assert one.compare(other) != 0
    assert not one.equals(other).is_true()
    assert one.compare(other) == -other.compare(one)


def test_graph_creation_order_never_changes_a_comparison():
    assert graph(["a", "b"], [("a", "b")]).compare(graph(["b", "a"], [("a", "b")])) == 0


def test_a_graph_label_or_value_decides_when_the_shape_is_the_same():
    assert graph(["a", "b"], [("a", "b", "l")]).compare(graph(["a", "b"], [("a", "b", "m")])) < 0
    assert with_values({"a": 1}).compare(with_values({"a": 2})) < 0


def test_map_insertion_order_never_changes_a_comparison():
    assert lx({"a": 1, "b": 2}).compare(lx({"b": 2, "a": 1})) == 0


# --- random collections with a tiny alphabet, so ties are common -------------

NAMES = ["a", "b", "c"]


def random_table(rng):
    names = rng.sample(NAMES, rng.randint(1, 3))
    rows = rng.randint(0, 2)
    return Table([(name, [Number(rng.randint(0, 1)) for _ in range(rows)]) for name in names])


def random_map(rng):
    result = Map()
    for key in rng.sample(NAMES, rng.randint(0, 3)):
        result.set_item(Text(key), Number(rng.randint(0, 1)))
    return result


def random_graph(rng):
    ids = rng.sample(NAMES, rng.randint(0, 3))
    result = Graph()
    for node_id in ids:
        result.nodes[node_id] = Number(rng.randint(0, 1))
    for source in ids:
        for target in ids:
            if source != target and rng.random() < 0.4:
                result.edges[(source, target)] = rng.choice([Void(), Text("l"), Text("m")])
    return result


@pytest.mark.parametrize("make", [random_table, random_map, random_graph])
def test_random_collections_obey_the_rules(make):
    values = [make(random.Random(seed)) for seed in range(60)]
    for a, b in itertools.product(values, repeat=2):
        assert a.compare(b) == -b.compare(a)
        assert (a.compare(b) == 0) == a.equals(b).is_true()
    for a, b, c in itertools.product(values[:25], repeat=3):
        if a.compare(b) <= 0 and b.compare(c) <= 0:
            assert a.compare(c) <= 0
