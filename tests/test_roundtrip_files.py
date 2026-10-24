"""Write a value to a file, read it back, and check nothing changed.

Three layers, all through the real `files.write` / `files.read`:

* a matrix of awkward strings and numbers, each placed in every position a
  value can occupy in `.csv`, graph `.csv` and `.yaml`;
* a seeded property test over random nested values, which also checks that
  writing what was read gives the same bytes (the format is stable);
* values a format cannot hold must be refused with a clean LynxError, never
  written as something else.
"""

import random

import pytest
from lynx_values import same

from lynx.core import files
from lynx.errors.errors import LynxError
from lynx.types import Array, Boolean, Graph, Map, Number, Table, Text, Void

# Characters that tend to break hand-written parsers, built with chr() so the
# test file itself stays plain ASCII.
SEPARATORS = [chr(0x0B), chr(0x0C), chr(0x1C), chr(0x85), chr(0x2028), chr(0x2029)]

NASTY_TEXT = [
    "",
    " ",
    "  ",
    "  a",
    "a  ",
    " a b ",
    "a,b",
    "a,",
    ",a",
    'q"uote',
    '"',
    '""',
    "it's",
    "'",
    "''",
    "'q'",
    "true",
    "false",
    "void",
    "null",
    "~",
    "yes",
    "True",
    "NULL",
    "12",
    "12.0",
    "1e5",
    "-3",
    "007",
    "0x1F",
    "1_000",
    ".5",
    "nan",
    "NaN",
    "inf",
    "-inf",
    "Infinity",
    "#c",
    "a # b",
    "a#b",
    "x: y",
    "key:",
    ":v",
    "- z",
    "-",
    "[1]",
    "[",
    "{a}",
    "{",
    "!",
    "&",
    "*",
    "|",
    ">",
    "%",
    "@",
    "`",
    "<<",
    "?",
    "(1, 2)",
    "(1)",
    "()",
    "(",
    ")",
    "('a')",
    "(a, b)",
    "\\",
    "\\(1)",
    "\\\\(1, 2)",
    "a\\nb",
    "http://x.com/?a=1&b=2#frag",
    "Hello!",
    "12:30",
    "tab\there",
    "\ttab",
    "a\nb",
    "a\r\nb",
    "a\rb",
    "\n",
    "trailing\n",
    "x" + chr(0) + "y",
    chr(0xFEFF) + "bom",
    "café",
    "日本",
    "\U0001f600",
    *("a" + separator + "b" for separator in SEPARATORS),
]

NUMBERS = [0, 1, -1, 7, 1.5, -2.25, 0.1, 1e-7, 1e22, 1e300, 2**70, 123456789012345678, 3.14, -0.0, 1e-300]


def roundtrip(value, tmp_path, ext):
    path = tmp_path / ("data" + ext)
    files.write(value, Text(str(path)))
    return files.read(str(path)), path.read_bytes()


def graph_with(nodes=None, edges=None):
    graph = Graph()
    graph.nodes.update(nodes or {})
    graph.edges.update(edges or {})
    return graph


def map_with(*pairs):
    mapping = Map()
    for key, value in pairs:
        mapping.set_item(key, value)
    return mapping


# --- the matrix: one string at a time, in every position ---------------------

TEXT_CONTEXTS = {
    "csv array item": (lambda s: Array([Text(s), Number(1)]), ".csv"),
    "csv array of one": (lambda s: Array([Text(s)]), ".csv"),
    "csv table cell": (lambda s: Table([("a", [Text(s)]), ("b", [Number(1)])]), ".csv"),
    "csv one-column table": (lambda s: Table([("a", [Text(s), Text("z")])]), ".csv"),
    "csv table header": (lambda s: Table([(s, [Number(1)]), ("b", [Number(2)])]), ".csv"),
    "csv one-column header": (lambda s: Table([(s, [Number(1), Number(2)])]), ".csv"),
    "graph node id": (lambda s: graph_with({s: Void()}), ".csv"),
    "graph node text value": (lambda s: graph_with({"n": Text(s)}), ".csv"),
    "graph edge label": (
        lambda s: graph_with({"a": Void(), "b": Void()}, {("a", "b"): Text(s)}),
        ".csv",
    ),
    "graph edge endpoint": (
        lambda s: graph_with({s: Void(), "z": Void()}, {(s, "z"): Text("l")}),
        ".csv",
    ),
    "graph array item": (lambda s: graph_with({"n": Array([Text(s), Number(1)])}), ".csv"),
    "graph array of one": (lambda s: graph_with({"n": Array([Text(s)])}), ".csv"),
    "yaml key": (lambda s: map_with((Text(s), Number(1))), ".yaml"),
    "yaml value": (lambda s: map_with((Text("k"), Text(s))), ".yaml"),
    "yaml list item": (lambda s: map_with((Text("k"), Array([Text(s), Text("z")]))), ".yaml"),
    "yaml map in list": (lambda s: map_with((Text("k"), Array([map_with((Text("x"), Text(s)))]))), ".yaml"),
    "yaml nested list": (lambda s: map_with((Text("k"), Array([Array([Text(s)])]))), ".yaml"),
    "yaml nested map": (lambda s: map_with((Text("a"), map_with((Text(s), Text(s))))), ".yaml"),
    "yaml list first in map": (
        lambda s: map_with((Text("k"), Array([map_with((Text(s), Array([Text(s)])), (Text("n"), Number(1)))]))),
        ".yaml",
    ),
}


@pytest.mark.parametrize("context", TEXT_CONTEXTS)
def test_every_awkward_string_roundtrips(context, tmp_path):
    make, ext = TEXT_CONTEXTS[context]
    failures = []
    for text in NASTY_TEXT:
        value = make(text)
        try:
            back, raw = roundtrip(value, tmp_path, ext)
        except LynxError as error:
            failures.append((text, f"error: {error}"))
            continue
        if not same(value, back):
            failures.append((text, f"read back as {back!r} from {raw!r}"))
    assert failures == [], f"{context}: {len(failures)} of {len(NASTY_TEXT)} strings changed: {failures[:5]}"


NUMBER_CONTEXTS = {
    "csv array": (lambda n: Array([Number(n), Text("z")]), ".csv"),
    "csv table": (lambda n: Table([("a", [Number(n)]), ("b", [Text("q")])]), ".csv"),
    "graph node value": (lambda n: graph_with({"n": Number(n)}), ".csv"),
    "graph array item": (lambda n: graph_with({"n": Array([Number(n)])}), ".csv"),
    "yaml value": (lambda n: map_with((Text("k"), Number(n))), ".yaml"),
    "yaml key": (lambda n: map_with((Number(n), Text("v"))), ".yaml"),
    "yaml list item": (lambda n: map_with((Text("k"), Array([Number(n)]))), ".yaml"),
}


@pytest.mark.parametrize("context", NUMBER_CONTEXTS)
@pytest.mark.parametrize("number", NUMBERS)
def test_numbers_roundtrip_exactly(context, number, tmp_path):
    make, ext = NUMBER_CONTEXTS[context]
    value = make(number)
    back, _ = roundtrip(value, tmp_path, ext)
    assert same(value, back)


@pytest.mark.parametrize("ext", [".txt"])
@pytest.mark.parametrize("text", NASTY_TEXT)
def test_txt_roundtrips_any_text_exactly(text, ext, tmp_path):
    back, raw = roundtrip(Text(text), tmp_path, ext)
    assert back.value == text
    assert raw == text.encode("utf-8")  # no newline translation, no BOM added


# --- a seeded property test over random nested values -----------------------


def random_scalar(rng):
    kind = rng.random()
    if kind < 0.4:
        return Text(rng.choice(NASTY_TEXT))
    if kind < 0.65:
        return Number(rng.choice(NUMBERS))
    if kind < 0.85:
        return Boolean(rng.random() < 0.5)
    return Void()


def random_key(rng):
    kind = rng.random()
    if kind < 0.6:
        return Text(rng.choice(NASTY_TEXT))
    if kind < 0.8:
        return Number(rng.choice([0, 1, -1, 2.5]))
    if kind < 0.9:
        return Boolean(rng.random() < 0.5)
    return Void()


def random_yaml_value(rng, depth):
    kind = rng.random()
    if depth <= 0 or kind < 0.4:
        return random_scalar(rng)
    if kind < 0.7:
        return Array([random_yaml_value(rng, depth - 1) for _ in range(rng.randint(0, 3))])
    mapping = Map()
    for _ in range(rng.randint(0, 3)):
        mapping.set_item(random_key(rng), random_yaml_value(rng, depth - 1))
    return mapping


def random_yaml_map(rng):
    mapping = Map()
    for _ in range(rng.randint(1, 4)):
        mapping.set_item(random_key(rng), random_yaml_value(rng, 3))
    return mapping


def random_csv_array(rng):
    return Array([random_scalar(rng) for _ in range(rng.randint(1, 5))])


def random_csv_table(rng):
    names = []
    while len(names) < rng.randint(1, 4):
        name = rng.choice(NASTY_TEXT)
        if name not in names:
            names.append(name)
    rows = rng.randint(1, 4)
    return Table([(name, [random_scalar(rng) for _ in range(rows)]) for name in names])


def random_graph(rng):
    ids = list({rng.choice(NASTY_TEXT) for _ in range(rng.randint(1, 4))})
    graph = Graph()
    for node_id in ids:
        graph.nodes[node_id] = rng.choice(
            [Void(), random_scalar(rng), Array([random_scalar(rng) for _ in range(rng.randint(0, 3))])]
        )
    for source in ids:
        for target in ids:
            if source != target and rng.random() < 0.4:
                graph.edges[(source, target)] = rng.choice([Void(), Text(rng.choice(NASTY_TEXT))])
    return graph


GENERATORS = {
    "csv array": (random_csv_array, ".csv"),
    "csv table": (random_csv_table, ".csv"),
    "graph csv": (random_graph, ".csv"),
    "yaml map": (random_yaml_map, ".yaml"),
}


@pytest.mark.parametrize("name", GENERATORS)
def test_random_values_roundtrip_and_are_stable(name, tmp_path):
    generate, ext = GENERATORS[name]
    for seed in range(600):
        value = generate(random.Random(seed))
        back, raw = roundtrip(value, tmp_path, ext)
        assert same(value, back), f"seed {seed}: {value!r} -> {raw!r} -> {back!r}"
        again, raw_again = roundtrip(back, tmp_path, ext)
        assert raw_again == raw, f"seed {seed}: writing what was read changed the bytes"
        assert same(back, again)


# --- what a format cannot hold is refused, never written as something else ---


def expect_clean_error(value, tmp_path, ext):
    path = tmp_path / ("refused" + ext)
    with pytest.raises(LynxError):
        files.write(value, Text(str(path)))
    assert not path.exists(), "a refused write must not leave a file behind"


def test_yaml_refuses_tables_and_graphs_anywhere(tmp_path):
    table = Table([("a", [Number(1)])])
    expect_clean_error(map_with((Text("k"), table)), tmp_path, ".yaml")
    expect_clean_error(map_with((Text("k"), Array([table]))), tmp_path, ".yaml")
    expect_clean_error(map_with((Text("k"), Array([Array([Graph()])]))), tmp_path, ".yaml")


def test_graph_csv_refuses_nested_arrays(tmp_path):
    expect_clean_error(graph_with({"n": Array([Array([Number(1)])])}), tmp_path, ".csv")
    expect_clean_error(graph_with({"n": Array([Map()])}), tmp_path, ".csv")


@pytest.mark.parametrize("number", [float("inf"), float("-inf"), float("nan")])
def test_csv_and_yaml_refuse_non_finite_numbers(number, tmp_path):
    expect_clean_error(Array([Number(number)]), tmp_path, ".csv")
    expect_clean_error(Table([("a", [Number(number)])]), tmp_path, ".csv")
    expect_clean_error(map_with((Text("k"), Number(number))), tmp_path, ".yaml")
    expect_clean_error(map_with((Number(number), Text("v"))), tmp_path, ".yaml")


def test_csv_refuses_a_table_with_no_rows(tmp_path):
    expect_clean_error(Table([("a", [])]), tmp_path, ".csv")


def test_inf_and_nan_are_plain_text(tmp_path):
    for word in ("inf", "-inf", "nan", "NaN", "Infinity", "1e999"):
        csv = tmp_path / "w.csv"
        csv.write_text(f"{word},1\n")
        assert same(files.read(str(csv)), Array([Text(word), Number(1)]))
        yaml = tmp_path / "w.yaml"
        yaml.write_text(f"k: {word}\n")
        assert same(files.read(str(yaml)), map_with((Text("k"), Text(word))))
    assert Text("inf").number().value == 3  # falls back to the length, like any non-number
    assert Text("nan").number().value == 3
    assert Text("1e999").number().value == 5
    assert Text("1e3").number().value == 1000
