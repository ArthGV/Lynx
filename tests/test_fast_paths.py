"""Optimisation-robustness tests.

Every shipped fast path mirrors a boxed value operation with raw arithmetic and
must never drift from it as the language evolves: compiled loop plans
(`core/plan.py`), the table column lanes (`types/table.py`), the int fast path
in `Number.__init__`, and the cursor lexer's symbol tables (`core/lexer.py`).

Each parity test below reads the result from the *boxed* Value method as the
source of truth and asserts the raw mirror produces the identical result, so a
change to either side surfaces here. `test_differential_fast_paths_on_off`
runs a corpus once with every fast path live and once with every one patched
out, demanding byte-identical stdout; the golden suite already pins live ==
expected, so generic-vs-fast equality follows transitively.

Convention: when a new fast path ships, (a) add a toggle row to
`_FAST_PATH_TOGGLES` so the differential harness disables it too, and (b) add a
parity or eligibility test beside the ones here.
"""

import contextlib
import io
import itertools

import pytest

from src.core.grammar import SYMBOLS
from src.core.interpreter import _base as base_mod
from src.core.lexer import tokenize
from src.core.nodes import Loop
from src.core.parser import Parser
from src.core.plan import _ARITH, _CMP, LoopPlan, compile_loop_plan
from src.errors.errors import LynxError, LynxSyntaxError
from src.main import run
from src.types.array import Array
from src.types.simple_type import Number, Text
from src.types.table import _NUMBER_PREDICATES, Table

# The value matrix for the raw-op parity sweeps: ints, floats, negatives, and
# near-1 pairs that exercise the `almost` family right at its boundary.
RAW_NUMBERS = [-2, -1, -0.5, 0, 0.5, 0.9, 1, 1.5, 2, 9]

_ARITH_METHOD = {"PLUS": "add", "MINUS": "subtract", "STAR": "multiply"}
_CMP_METHOD = {
    "EQUAL": "equals",
    "NOT_EQUAL": "not_equal",
    "ALMOST": "almost",
    "GREATER": "greater",
    "LESS": "less",
    "GREATER_OR_EQUAL": "greater_or_equal",
    "LESSER_OR_EQUAL": "lesser_or_equal",
    "GREATER_OR_ALMOST": "greater_or_almost",
    "LESSER_OR_ALMOST": "lesser_or_almost",
}


def run_capturing(source: str) -> str:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        try:
            run(source)
        except LynxError as error:
            print(error)
    return out.getvalue()


def scalar(value):
    """A comparable, type-aware view of a value (Void has no `.value`)."""
    return (value.type_name(), value.value if hasattr(value, "value") else None)


# --- Number construction -----------------------------------------------


def test_number_construction_int_fast_path():
    # Within exact-float range the direct-int and float-roundtrip paths agree.
    for value in (-2, -1, 0, 1, 2, 9, -(2**53), 2**53):
        number = Number(value)
        assert number.value == int(float(value))
        assert isinstance(number.value, int)
    # Beyond it the fast path stays exact where float() would lose precision.
    for value in (-(10**30), 10**30):
        number = Number(value)
        assert number.value == value
        assert isinstance(number.value, int)
    # Bools must not sneak through the int fast path (they go the float way).
    for value in (True, False):
        number = Number(value)
        assert number.value == int(value)
        assert isinstance(number.value, int)
    assert Number(1.5).value == 1.5
    assert isinstance(Number(1.5).value, float)
    assert Number(2.0).value == 2  # integral floats still normalize to int
    assert Number("7").value == 7
    assert Number("7.5").value == 7.5


# --- raw-op parity sweeps ----------------------------------------------


@pytest.mark.parametrize("op", list(_ARITH))
@pytest.mark.parametrize("a, b", list(itertools.product(RAW_NUMBERS, repeat=2)))
def test_plan_arith_matches_number_ops(op, a, b):
    boxed = getattr(Number(a), _ARITH_METHOD[op])(Number(b)).value
    assert _ARITH[op](a, b) == boxed


@pytest.mark.parametrize("op", list(_CMP))
@pytest.mark.parametrize("a, b", list(itertools.product(RAW_NUMBERS, repeat=2)))
def test_plan_cmp_matches_number_comparisons(op, a, b):
    boxed = getattr(Number(a), _CMP_METHOD[op])(Number(b)).is_true()
    assert _CMP[op](a, b) == boxed


@pytest.mark.parametrize("method", sorted(_NUMBER_PREDICATES))
@pytest.mark.parametrize("a, b", list(itertools.product(RAW_NUMBERS, repeat=2)))
def test_lane_predicates_match_number_comparisons(method, a, b):
    boxed = getattr(Number(a), method)(Number(b)).is_true()
    assert _NUMBER_PREDICATES[method](a, b) == boxed


# --- table column aggregates --------------------------------------------


def test_column_aggregate_matches_array_aggregates():
    columns = [
        [Number(1), Number(2), Number(3)],
        [Number(1.5), Number(2.5), Number(3.5)],
        [Number(-1), Number(0), Number(1)],
        [],
    ]
    for cells in columns:
        table = Table([("price", cells)])
        generic = Array(list(cells))
        for method in ("sum", "avg", "min", "max"):
            fast = table.column_aggregate("price", method)
            boxed = getattr(generic, method)()
            assert fast is not None
            assert scalar(fast) == scalar(boxed)

    # A column holding any non-Number (or missing) refuses the fast path.
    mixed = Table([("price", [Number(1), Text("x"), Number(3)])])
    assert mixed.column_aggregate("price", "sum") is None
    padded = Table([("price", [Number(1), Number(2)]), ("note", [Text("a"), Text("b"), Text("c")])])
    assert padded.column_aggregate("price", "sum") is None
    assert Table([("price", [Number(1)])]).column_aggregate("nope", "sum") is None


# --- loop-plan eligibility ----------------------------------------------


def first_loop(source: str) -> Loop:
    tree = Parser(tokenize(source)).parse()
    return next(statement for statement in tree.statements if isinstance(statement, Loop))


loop_eligibility = [
    ("while_plus", "loop i < 5\n i: i + 1\n", True),
    ("while_minus", "loop i > 0\n i: i - 1\n", True),
    ("while_star", "loop i < 5\n i: p * i\n", True),
    ("while_if", "loop i < 5\n if i >~ 2\n  s: s + i\n i: i + 1\n", True),
    ("while_if_else", "loop i < 5\n if i > 2\n  s: s + i\n else\n  t: t + 1\n", True),
    ("over_identifier", "values: 1, 2, 3\nloop v: values\n s: s + v\n", True),
    ("division", "loop i < 5\n i: i / 2\n", False),
    ("power", "loop i < 5\n i: i ^ 2\n", False),
    ("call_in_body", "loop i < 5\n i: f i\n", False),
    ("nested_if_body", "loop i < 5\n if i > 2\n  s: s + i\n  t: t + i\n", False),
    ("else_two_branch", "loop i < 5\n if i > 2\n  s: s + i\n else i > 0\n  s: s - i\n", False),
    ("bare_condition", "loop i\n i: i + 1\n", False),
    ("non_cmp_condition", "loop i + 1\n i: i + 1\n", False),
    ("if_bare_condition", "loop i < 5\n if i\n  s: s + i\n", False),
    ("over_literal", "loop v: 1, 2, 3\n s: s + v\n", False),
    ("over_two_targets", "loop i, v: values\n s: s + v\n", False),
]


@pytest.mark.parametrize("case", loop_eligibility, ids=lambda item: item[0])
def test_loop_plan_eligibility(case):
    _, source, expect_plan = case
    loop = first_loop(source)
    plan = compile_loop_plan(loop.condition, loop.body, loop.targets, loop.iterable)
    if expect_plan:
        assert isinstance(plan, LoopPlan)
    else:
        assert plan is None


# --- table lane extraction and validity --------------------------------


def test_lane_extraction_and_invalidation():
    table = Table([("price", [Number(1), Number(2), Number(3)])])
    lane = table._lane("price")
    assert lane.numbers == [1, 2, 3]
    assert lane.column_id == id(table.columns["price"])
    assert lane.length == 3
    assert table._lane("price") is lane  # cached while source list is untouched

    table.set_column("price", [Number(9), Number(8)])
    refreshed = table._lane("price")
    assert refreshed is not lane
    assert refreshed.numbers == [9, 8]
    assert refreshed.length == 2

    table.del_row(0)
    assert table._lane("price").numbers == [8]

    mixed = Table([("price", [Number(1), Text("x")])])
    assert mixed._lane("price").numbers is None
    assert Table([("price", [])])._lane("price").numbers == []
    assert Table([("price", [Number(1)])])._lane("nope") is None


# --- differential end-to-end fast paths on vs off -----------------------

# Each toggle patches one fast-path seam; every row must disable a fast path.
_FAST_PATH_TOGGLES = [
    (base_mod, "compile_loop_plan", lambda *args, **kwargs: None),
    (Table, "_lane", lambda self, name: None),
]

DIFFERENTIAL_CORPUS = [
    ("loop_arith_plus", "i: 0\ns: 0\nloop i < 10\n s: s + i\n i: i + 1\n>> s\n"),
    ("loop_arith_minus", "i: 10\nloop i > 0\n i: i - 1\n>> i\n"),
    ("loop_arith_star", "s: 1\ni: 1\nloop i < 5\n s: s * i\n i: i + 1\n>> s\n"),
    ("loop_cond_equal", "i: 0\nloop i = 3\n i: i + 1\n>> i\n"),
    ("loop_cond_not_equal", "i: 0\nloop i != 3\n i: i + 1\n>> i\n"),
    ("loop_cond_almost", "i: 3\nloop i \u2248 3\n i: i + 1\n>> i\n"),
    ("loop_cond_greater", "i: 5\nloop i > 2\n i: i - 1\n>> i\n"),
    ("loop_cond_less", "i: 0\nloop i < 3\n i: i + 1\n>> i\n"),
    ("loop_cond_greater_or_equal", "i: 5\nloop i >= 2\n i: i - 1\n>> i\n"),
    ("loop_cond_lesser_or_equal", "i: 0\nloop i <= 3\n i: i + 1\n>> i\n"),
    ("loop_cond_greater_or_almost", "i: 7\nloop i >~ 2\n i: i - 1\n>> i\n"),
    ("loop_cond_lesser_or_almost", "i: 0\nloop i <~ 3\n i: i + 1\n>> i\n"),
    ("over_reduce", "values: 1, 2, 3, 4\ns: 0\nloop v: values\n s: s + v\n>> s\n"),
    ("over_filter", "values: 1, 2, 3, 4, 5\ns: 0\nloop v: values\n if v >~ 2\n  s: s + v\n>> s\n"),
    ("over_empty", "values: array\ns: 7\nloop v: values\n s: s + v\n>> s\n"),
    ("over_literal", "s: 0\nloop v: 1, 2, 3\n s: s + v\n>> s\n"),
    (
        "table_aggregates",
        "t: [ 'id': 1, 2, 3; 'price': 10, 20, 30 ]\n"
        ">> sum t 'price'\n"
        ">> avg t 'price'\n"
        ">> min t 'price'\n"
        ">> max t 'price'\n",
    ),
    (
        "table_where",
        "t: [ 'price': 1, 2, 3, 4 ]\n>> where t 'price' = 2\n>> where t 'price' != 2\n>> where t 'price' >~ 2\n",
    ),
    ("table_order", "t: [ 'price': 3, 1, 2 ]\n>> order t 'price'\n"),
    ("table_mutation", "t: [ 'price': 1, 2, 3 ]\nt 'price': 4, 5, 6\n>> sum t 'price'\n>> order t 'price'\n"),
    (
        "table_fallback",
        "t: [ 'price': 1, 2, 3; 'note': 'a', 'b', 'c' ]\n>> sum t 'note'\n>> avg t 'price'\n>> sum t 'nope'\n",
    ),
    ("where_generic_text", "t: [ 'price': 1, 2, 3; 'note': 'a', 'b', 'c' ]\n>> where t 'note' = 'b'\n"),
]


@pytest.mark.parametrize("case", DIFFERENTIAL_CORPUS, ids=lambda item: item[0])
def test_differential_fast_paths_on_off(case, monkeypatch):
    name, source = case
    on = run_capturing(source)
    for module, attribute, patch in _FAST_PATH_TOGGLES:
        monkeypatch.setattr(module, attribute, patch)
    off = run_capturing(source)
    assert on, f"{name} produced no output"
    assert on == off, f"{name} diverges when fast paths are disabled"


# --- lexer symbol live-ness and token streams ---------------------------


def content_tokens(source: str) -> list[tuple[str, object]]:
    keep = ("INDENT", "DEDENT", "NEWLINE")
    return [(token.type, token.value) for token in tokenize(source) if token.type not in keep]


@pytest.mark.parametrize(
    "case",
    sorted(SYMBOLS.items(), key=lambda pair: len(pair[0])),
    ids=lambda item: item[0],
)
def test_symbol_lexes_to_its_token_type(case):
    symbol, kind = case
    assert content_tokens(symbol) == [(kind, symbol)]


@pytest.mark.parametrize(
    "case",
    [
        ("a  +  b", [("IDENTIFIER", "a"), ("PLUS", "+"), ("IDENTIFIER", "b")]),
        ("3__7", [("NUMBER", "3"), ("RANGE", "__"), ("NUMBER", "7")]),
        ("a // rest", [("IDENTIFIER", "a")]),
        ("'\\n'", [("TEXT", "\n")]),
        ("''", [("TEXT", "")]),
        ("'a\\'b'", [("TEXT", "a'b")]),
        ("x_1", [("IDENTIFIER", "x_1")]),
        ("_x", [("IDENTIFIER", "_x")]),
        ("l__n", [("IDENTIFIER", "l"), ("RANGE", "__"), ("IDENTIFIER", "n")]),
        ("___", [("RANGE", "__"), ("IDENTIFIER", "_")]),
        ("x >> y", [("IDENTIFIER", "x"), ("PRINT", ">>"), ("IDENTIFIER", "y")]),
        ("///\nbody\n///", []),
    ],
    ids=lambda item: item[0],
)
def test_token_stream_parity(case):
    source, expected = case
    assert content_tokens(source) == expected


def test_lexer_number_underscore_error():
    with pytest.raises(LynxSyntaxError) as error:
        tokenize("3_7")
    assert "use '__' for ranges, not '_'" in str(error.value)


def test_lexer_unexpected_character_error():
    with pytest.raises(LynxSyntaxError) as error:
        tokenize("@")
    assert "unexpected character near" in str(error.value)


def test_lexer_unterminated_block_comment_error():
    with pytest.raises(LynxSyntaxError) as error:
        tokenize("///\nbody\n")
    assert "unterminated multiline comment" in str(error.value)
