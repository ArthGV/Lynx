"""Unit tests for value methods not exposed as langauge keywords.

`middle`, `power`, `root`, and `not_` are implemented on every value type but
are not reachable from `.lx` programs — there is no keyword for them. These are
tested here directly against the values module.
"""

from src.errors.errors import LynxNotImplemented, LynxTypeError
from src.runtime.values import Array, Boolean, Map, Number, Table, Text, Void


def arr(*items):
    return Array(items)


def test_array_middle():
    assert print_(arr(Number(1), Number(2), Number(3)).middle()) == "2"
    assert print_(arr(Number(1), Number(2)).middle()) == "2"
    assert print_(arr(Number(1)).middle()) == "1"
    assert type(arr().middle()) is Void


def test_array_first_last():
    assert print_(arr(Number(1), Number(2), Number(3)).first()) == "1"
    assert print_(arr(Number(1), Number(2), Number(3)).last()) == "3"
    assert type(arr().first()) is Void
    assert type(arr().last()) is Void


def test_array_lenght():
    assert print_(arr(Number(1), Text("x"), Boolean(True)).lenght()) == "3"
    assert print_(arr().lenght()) == "0"


def test_array_conversions():
    a = arr(Number(1), Boolean(True))
    assert print_(a.text()) == "[ 1, true ]"
    assert print_(a.number()) == "2"
    assert a.boolean().is_true() is True
    assert arr().boolean().is_true() is False
    assert type(a.void()) is Void


def test_array_comparison():
    assert arr(Number(1), Number(2)).equals(arr(Number(1), Number(2))).is_true()
    assert arr(Number(1), Number(2)).equals(arr(Number(1), Number(3))).is_true() is False
    assert arr(Number(1), Number(2)).greater(arr(Number(1))).is_true()
    assert arr(Number(1), Number(2)).less(arr(Number(1), Number(2), Number(3))).is_true()


def test_array_almost():
    assert arr(Number(1), Number(2)).almost(arr(Number(1), Number(2))).is_true()
    assert arr(Number(1), Number(2)).almost(arr(Number(1), Number(3))).is_true() is False
    assert arr(Number(1)).almost(arr(Number(1), Number(2))).is_true() is False


def test_array_arithmetic_not_implemented():
    a = arr(Number(1), Number(2))
    for method in ("add", "subtract", "multiply", "divide", "power", "root", "xor"):
        try:
            getattr(a, method)(a)
            assert False, f"{method} should not be implemented"
        except LynxNotImplemented:
            pass
    try:
        a.not_()
        assert False, "not_ should not be implemented"
    except LynxNotImplemented:
        pass


def test_empty_array_is_not_void():
    empty = Array.default()
    assert type(empty) is Array
    assert len(empty.value) == 0
    assert type(empty) is not Void


# --- Map ---------------------------------------------------------------

def mp(*entries):
    return Map(list(entries))


def test_map_lenght():
    assert print_(mp((Text("a"), Number(1))).lenght()) == "1"
    assert print_(mp().lenght()) == "0"


def test_map_first_last():
    m = mp((Text("a"), Number(1)), (Text("b"), Number(2)))
    assert print_(m.first()) == "1"
    assert print_(m.last()) == "2"
    assert type(mp().first()) is Void
    assert type(mp().last()) is Void


def test_map_middle():
    m = mp((Text("a"), Number(1)), (Text("b"), Number(2)), (Text("c"), Number(3)))
    assert print_(m.middle()) == "2"
    assert type(mp().middle()) is Void


def test_map_conversions():
    m = mp((Text("a"), Number(1)))
    assert print_(m.text()) == "{ a: 1 }"
    assert print_(m.number()) == "1"
    assert m.boolean().is_true() is True
    assert mp().boolean().is_true() is False
    assert type(m.void()) is Void
    assert print_(mp().text()) == "{}"


def test_map_equality():
    a = mp((Text("a"), Number(1)), (Text("b"), Number(2)))
    b = mp((Text("a"), Number(1)), (Text("b"), Number(2)))
    c = mp((Text("a"), Number(1)))
    d = mp((Text("a"), Number(9)))
    assert a.equals(b).is_true()
    assert a.equals(c).is_true() is False
    assert a.equals(d).is_true() is False


def test_map_key_types_are_distinct():
    # 1, '1', and true are three different keys.
    m = mp((Number(1), Text("num")), (Text("1"), Text("text")), (Boolean(True), Text("bool")))
    assert print_(m.get_item(Number(1))) == "num"
    assert print_(m.get_item(Text("1"))) == "text"
    assert print_(m.get_item(Boolean(True))) == "bool"


def test_map_default_is_not_void():
    empty = Map.default()
    assert type(empty) is Map
    assert len(empty.value) == 0


def test_map_missing_key_returns_void():
    m = mp((Text("a"), Number(1)))
    assert type(m.get_item(Text("nope"))) is Void
    assert type(mp().get_item(Number(0))) is Void


def test_in_membership():
    a = arr(Number(1), Number(2), Number(3))
    assert Number(2).in_(a).is_true()
    assert Number(4).in_(a).is_true() is False
    # different element types never match
    assert Number(1).in_(arr(Text("1"), Boolean(True))).is_true() is False
    assert Array([Number(1)]).in_(arr(Text("x"), Array([Number(1)]))).is_true()
    # a map's keys, not its values
    m = mp((Text("a"), Number(1)))
    assert Text("a").in_(m).is_true()
    assert Number(1).in_(m).is_true() is False
    # scalars iterate too, so membership has a default there as well
    assert Number(3).in_(Number(5)).is_true()
    assert Text("h").in_(Text("hello")).is_true()
    assert Text("z").in_(Text("hello")).is_true() is False
    assert Number(1).in_(Void()).is_true() is False


def test_map_compare():
    a = mp((Text("a"), Number(1)), (Text("b"), Number(2)))
    b = mp((Text("a"), Number(1)), (Text("b"), Number(2)))
    c = mp((Text("a"), Number(1)))
    d = mp((Text("a"), Number(9)))
    assert a.compare(b) == 0
    assert a.greater(c).is_true()
    assert c.less(a).is_true()
    assert a.greater(d).is_true()
    assert d.less(a).is_true()


def test_map_almost():
    a = mp((Text("a"), Number(1)), (Text("b"), Number(2)))
    b = mp((Text("a"), Number(1)), (Text("b"), Number(2)))
    c = mp((Text("a"), Number(9)))
    assert a.almost(b).is_true()
    assert a.almost(c).is_true() is False


def test_map_distinct_is_identity():
    assert mp().distinct() is not None
    m = mp((Text('a'), Number(1)), (Text('b'), Number(2)))
    d = m.distinct()
    assert d.get_item(Text('a')).value == 1
    assert d.get_item(Text('b')).value == 2


def test_map_arithmetic_not_implemented():
    m = mp((Text("a"), Number(1)))
    for method in ("add", "subtract", "multiply", "divide", "power", "root", "xor"):
        try:
            getattr(m, method)(m)
            assert False, f"{method} should not be implemented"
        except LynxNotImplemented:
            pass
    try:
        m.not_()
        assert False, "not_ should not be implemented"
    except LynxNotImplemented:
        pass



def print_(v):
    return str(v)


# --- Number -------------------------------------------------------------

def test_number_middle():
    assert print_(Number(12345).middle()) == "3"
    assert print_(Number(1234).middle()) == "3"
    assert print_(Number(1).middle()) == "1"
    assert print_(Number(0).middle()) == "0"
    assert print_(Number(-55).middle()) == "5"
    assert print_(Number(3.14).middle()) == "1"


def test_number_power():
    assert print_(Number(2).power(Number(3))) == "8"
    assert print_(Number(3).power(Number(2))) == "9"
    assert print_(Number(2).power(Number(0))) == "1"
    assert print_(Number(0).power(Number(5))) == "0"


def test_number_root():
    assert print_(Number(8).root(Number(3))) == "2"
    assert print_(Number(9).root(Number(2))) == "3"
    assert print_(Number(16).root(Number(4))) == "2"
    assert type(Number(8).root(Number(0))) is Void


def test_number_not_():
    assert print_(Number(5).not_()) == "-4"
    assert print_(Number(0).not_()) == "1"
    assert print_(Number(1).not_()) == "0"
    assert print_(Number(2.5).not_()) == "-1.5"


# --- Text ---------------------------------------------------------------

def test_text_middle():
    assert print_(Text("hello").middle()) == "l"
    assert print_(Text("hi").middle()) == "i"
    assert print_(Text("a").middle()) == "a"
    assert print_(Text("").middle()) == ""


def test_text_power():
    assert print_(Text("ab").power(Text("xyz"))) == "ababab"
    assert print_(Text("a").power(Text("bc"))) == "aa"
    assert print_(Text("hello").power(Text("x"))) == "hello"


def test_text_root():
    assert print_(Text("hello").root(Number(2))) == "he"
    assert print_(Text("abcdef").root(Number(3))) == "abc"
    assert print_(Text("a").root(Number(1))) == ""
    assert print_(Text("").root(Number(5))) == ""


def test_text_not_():
    assert print_(Text("hello").not_()) == "-4"
    assert print_(Text("3").not_()) == "-2"
    assert print_(Text("").not_()) == "1"
    assert print_(Text("42").not_()) == "-41"


# --- Boolean ------------------------------------------------------------

def test_boolean_middle():
    assert print_(Boolean(True).middle()) == "true"
    assert print_(Boolean(False).middle()) == "false"


def test_boolean_power():
    assert print_(Boolean(True).power(Boolean(True))) == "true"
    assert print_(Boolean(True).power(Boolean(False))) == "true"
    assert print_(Boolean(False).power(Boolean(True))) == "false"
    assert print_(Boolean(False).power(Boolean(False))) == "true"


def test_boolean_root():
    assert print_(Boolean(True).root(Boolean(True))) == "true"
    assert print_(Boolean(True).root(Boolean(False))) == "true"
    assert print_(Boolean(False).root(Boolean(True))) == "false"
    assert print_(Boolean(False).root(Boolean(False))) == "false"


def test_boolean_not_():
    assert print_(Boolean(True).not_()) == "false"
    assert print_(Boolean(False).not_()) == "true"


# --- Void ---------------------------------------------------------------

def test_void_middle():
    assert type(Void().middle()) is Void


def test_void_power():
    assert type(Void().power(Void())) is Void
    assert type(Void().power(Number(3))) is Void


def test_void_root():
    assert type(Void().root(Void())) is Void
    assert type(Void().root(Number(2))) is Void


def test_void_not_():
    assert type(Void().not_()) is Void


# --- Table ---------------------------------------------------------------

def tbl(*columns):
    """Helper: tbl(('id', [1, 2, 3]), ('price', [10, 20])) → Table"""
    return Table([(name, [Number(v) if isinstance(v, (int, float)) else v for v in vals])
                  for name, vals in columns])


def test_table_construction():
    t = tbl(('id', [1, 2, 3]), ('price', [10, 20, 30]))
    assert t.nrows == 3
    assert list(t.columns.keys()) == ['id', 'price']


def test_table_empty():
    t = Table([])
    assert t.nrows == 0
    assert t.columns == {}


def test_table_lenght():
    t = tbl(('id', [1, 2, 3]), ('price', [10, 20, 30]))
    result = t.lenght()
    assert isinstance(result, Array)
    assert result.value[0].value == 3  # nrows
    assert result.value[1].value == 2  # ncols


def test_table_lenght_empty():
    t = Table([])
    result = t.lenght()
    assert isinstance(result, Array)
    assert result.value[0].value == 0
    assert result.value[1].value == 0


def test_table_first_last():
    t = tbl(('id', [1, 2, 3]), ('price', [10, 20, 30]))
    first = t.first()
    assert isinstance(first, Map)
    assert first.get_item(Text('id')).value == 1
    assert first.get_item(Text('price')).value == 10
    last = t.last()
    assert last.get_item(Text('id')).value == 3
    assert last.get_item(Text('price')).value == 30


def test_table_first_last_empty():
    t = Table([])
    assert type(t.first()) is Void
    assert type(t.last()) is Void


def test_table_middle():
    t = tbl(('a', [1, 2, 3, 4, 5]))
    mid = t.middle()
    assert isinstance(mid, Map)
    assert mid.get_item(Text('a')).value == 3


def test_table_conversions():
    t = tbl(('id', [1, 2]))
    assert t.number().value == 2  # nrows
    assert t.boolean().is_true() is True
    assert Table([]).boolean().is_true() is False
    assert type(t.void()) is Void


def test_table_text_repr():
    t = tbl(('id', [1, 2]), ('name', [Text('a'), Text('b')]))
    text_val = t.text().value
    assert 'id' in text_val
    assert 'name' in text_val


def test_table_equals():
    a = tbl(('x', [1, 2]))
    b = tbl(('x', [1, 2]))
    c = tbl(('x', [1, 3]))
    d = tbl(('y', [1, 2]))
    assert a.equals(b).is_true()
    assert a.equals(c).is_true() is False
    assert a.equals(d).is_true() is False


def test_table_compare():
    a = tbl(('x', [1, 2]))
    b = tbl(('x', [1, 2]))
    c = tbl(('x', [1]))
    d = tbl(('y', [1, 2]))
    assert a.compare(b) == 0
    assert a.greater(c).is_true()
    assert c.less(a).is_true()
    assert a.less(d).is_true()
    assert d.greater(a).is_true()


def test_table_almost():
    a = tbl(('x', [1, 2]))
    b = tbl(('x', [1, 2]))
    c = tbl(('x', [1, 3]))
    assert a.almost(b).is_true()
    assert a.almost(c).is_true() is False


def test_table_get_column():
    t = tbl(('id', [1, 2, 3]), ('price', [10, 20, 30]))
    col = t.get_column('id')
    assert isinstance(col, Array)
    assert len(col.value) == 3
    assert col.value[0].value == 1


def test_table_missing_column_returns_void():
    t = tbl(('id', [1, 2]))
    assert type(t.get_column('nope')) is Void


def test_table_get_row():
    t = tbl(('id', [1, 2, 3]), ('price', [10, 20, 30]))
    row = t.get_row(0)
    assert isinstance(row, Map)
    assert row.get_item(Text('id')).value == 1
    assert row.get_item(Text('price')).value == 10


def test_table_iterate():
    t = tbl(('x', [1, 2, 3]))
    rows = list(t.iterate())
    assert len(rows) == 3
    assert isinstance(rows[0], Map)
    assert rows[0].get_item(Text('x')).value == 1
    assert rows[2].get_item(Text('x')).value == 3


def test_table_column_name_must_be_text():
    try:
        Table([(123, [Number(1), Number(2)])])
        assert False, "should have raised TypeError"
    except LynxTypeError as e:
        assert "text" in str(e).lower()


def test_table_pads_short_columns():
    t = Table([('a', [Number(1), Number(2)]), ('b', [Number(3)])])
    assert t.nrows == 2
    assert len(t.columns['a']) == 2
    assert len(t.columns['b']) == 2
    assert type(t.columns['b'][1]) is Void


def test_table_empty_column_is_padded():
    t = Table([('id', []), ('price', [Number(1), Number(2)])])
    assert t.nrows == 2
    assert len(t.columns['id']) == 2
    assert type(t.columns['id'][0]) is Void
    assert type(t.columns['id'][1]) is Void


def test_table_get_row_pads_short_column():
    t = Table([('id', [Number(1), Number(2)]), ('price', [Number(3)])])
    row = t.get_row(1)
    assert row.get_item(Text('id')).value == 2
    assert type(row.get_item(Text('price'))) is Void


def test_table_arithmetic_not_implemented():
    t = tbl(('x', [1]))
    for method in ("add", "subtract", "multiply", "divide", "power", "root", "xor"):
        try:
            getattr(t, method)(t)
            assert False, f"{method} should not be implemented"
        except LynxNotImplemented:
            pass
    try:
        t.not_()
        assert False, "not_ should not be implemented"
    except LynxNotImplemented:
        pass


def test_table_default_is_not_void():
    empty = Table.default()
    assert type(empty) is Table
    assert empty.nrows == 0


# --- SQL-style operations ----------------------------------------------

def test_array_sum():
    assert arr(Number(1), Number(2), Number(3)).sum().value == 6
    # non-numbers are skipped
    assert arr(Number(1), Boolean(True), Text('hi'), Number(4)).sum().value == 5
    assert type(arr().sum()) is Void


def test_array_avg():
    assert arr(Number(1), Number(2), Number(3)).avg().value == 2
    assert arr(Number(1), Number(8), Text('x')).avg().value == 4.5
    assert type(arr().avg()) is Void


def test_array_min_max():
    assert arr(Number(3), Number(1), Number(9)).min().value == 1
    assert arr(Number(3), Number(1), Number(9)).max().value == 9
    assert type(arr().min()) is Void
    assert type(arr().max()) is Void


def test_number_aggregates_are_identity():
    assert Number(7).sum().value == 7
    assert Number(7).avg().value == 7
    assert Number(7).min().value == 7
    assert Number(7).max().value == 7


def test_count_defaults():
    assert arr(Number(1), Number(2)).count().value == 2
    assert arr().count().value == 0
    assert Text('hello').count().value == 5
    assert Text('').count().value == 0
    assert Void().count().value == 0
    m = mp((Text('a'), Number(1)), (Text('b'), Number(2)))
    assert m.count().value == 2
    assert Boolean(True).count().value == 1
    # a single scalar counts as one, whatever its digits
    assert Number(0).count().value == 1
    assert Number(12345).count().value == 1


def test_join_is_tables_only():
    for value in (Number(1), Text('a'), Boolean(True), Void(), arr(Number(1)), mp((Text('a'), Number(1)))):
        try:
            value.join(value)
            assert False, "join should not be implemented for non-tables"
        except LynxNotImplemented:
            pass


def test_aggregates_stub_on_non_numbers():
    for value in (Text('a'), Boolean(True), mp((Text('a'), Number(1))), tbl(('x', [1]))):
        for method in ("sum", "avg", "min", "max"):
            try:
                getattr(value, method)()
                assert False, f"{method} should not be implemented for {type(value).__name__}"
            except LynxNotImplemented:
                pass


def test_void_aggregates_return_void():
    for method in ("sum", "avg", "min", "max"):
        assert type(getattr(Void(), method)()) is Void


def test_table_count_is_rows():
    t = tbl(('id', [1, 2, 3]))
    assert t.count().value == 3
    assert Table([]).count().value == 0


def test_distinct_default_is_identity():
    assert Number(5).distinct().value == 5
    assert Text('x').distinct().value == 'x'
    assert type(Void().distinct()) is Void


def test_array_distinct():
    a = arr(Number(1), Number(1), Number(2), Number(3), Number(2))
    assert [v.value for v in a.distinct().value] == [1, 2, 3]
    b = arr(Text('a'), Text('a'), Boolean(True), Boolean(True))
    assert [print_(v) for v in b.distinct().value] == ["a", "true"]


def test_table_distinct_rows():
    t = tbl(('id', [1, 1, 2]), ('v', [5, 5, 9]))
    d = t.distinct()
    assert d.nrows == 2
    assert [c.value for c in d.columns['id']] == [1, 2]
    assert [c.value for c in d.columns['v']] == [5, 9]


def test_table_select():
    t = tbl(('id', [1, 2, 3]), ('price', [10, 20, 30]))
    s = t.select(['id', 'price'])
    assert list(s.columns.keys()) == ['id', 'price']
    assert s.nrows == 3
    only = t.select(['price'])
    assert list(only.columns.keys()) == ['price']
    assert only.columns['price'][0].value == 10


def test_table_select_missing_column_returns_void():
    t = tbl(('id', [1, 2]))
    assert type(t.select(['nope'])) is Void


def test_table_order_by():
    t = tbl(('id', [3, 1, 2]), ('v', [Text('c'), Text('a'), Text('b')]))
    o = t.order_by('v')
    assert [c.value for c in o.columns['id']] == [1, 2, 3]
    assert [c.value for c in o.columns['v']] == ['a', 'b', 'c']


def test_table_group_by():
    t = tbl(('dept', [Text('a'), Text('b'), Text('a')]), ('score', [1, 2, 3]))
    g = t.group_by('dept')
    assert isinstance(g, Map)
    assert g.lenght().value == 2
    group_a = g.get_item(Text('a'))
    assert isinstance(group_a, Table)
    assert group_a.nrows == 2
    assert [c.value for c in group_a.columns['score']] == [1, 3]
    group_b = g.get_item(Text('b'))
    assert [c.value for c in group_b.columns['score']] == [2]


def test_table_rows_where():
    t = tbl(('id', [1, 2, 3]), ('price', [10, 20, 30]))
    big = t.rows_where('price', 'GREATER', Number(15))
    assert [c.value for c in big.columns['id']] == [2, 3]
    exact = t.rows_where('price', 'ALMOST', Number(20))
    assert [c.value for c in exact.columns['id']] == [2]
    none = t.rows_where('price', 'GREATER', Number(100))
    assert none.nrows == 0


def test_table_join():
    j1 = tbl(('id', [1, 2]), ('name', [Text('a'), Text('b')]))
    j2 = tbl(('id', [2, 3]), ('score', [7, 8]))
    joined = j1.join(j2)
    assert list(joined.columns.keys()) == ['id', 'name', 'score']
    assert joined.nrows == 1
    assert joined.columns['id'][0].value == 2
    assert joined.columns['name'][0].value == 'b'
    assert joined.columns['score'][0].value == 7


def test_table_join_no_shared_columns_is_empty():
    a = tbl(('x', [1]))
    b = tbl(('y', [2]))
    joined = a.join(b)
    assert isinstance(joined, Table)
    assert joined.nrows == 0
    assert joined.columns == {}
    assert print_(joined) == "{}"


# --- iterate ------------------------------------------------------------

def iter_str(value):
    return [print_(v) for v in value.iterate()]


def test_array_iterate():
    assert iter_str(arr(Number(1), Number(2), Number(3))) == ["1", "2", "3"]
    assert iter_str(arr()) == []
    assert iter_str(arr(Text("a"), arr(Number(1)))) == ["a", "[ 1 ]"]


def test_map_iterate():
    m = mp((Text("a"), Number(1)), (Text("b"), Number(2)))
    assert iter_str(m) == ["a", "b"]
    assert iter_str(mp()) == []


def test_number_iterate():
    assert iter_str(Number(3)) == ["0", "1", "2", "3"]
    assert iter_str(Number(0)) == ["0"]
    assert iter_str(Number(-2)) == ["0", "-1", "-2"]
    assert iter_str(Number(2.7)) == ["0", "1", "2", "3"]
    assert iter_str(Number(-2.7)) == ["0", "-1", "-2", "-3"]


def test_number_iterate_rounds_like_python():
    # round() is ties-to-even, so 2.5 counts up to 2 and 3.5 up to 4.
    assert iter_str(Number(2.5)) == ["0", "1", "2"]
    assert iter_str(Number(3.5)) == ["0", "1", "2", "3", "4"]


def test_text_iterate():
    assert iter_str(Text("hi!")) == ["h", "i", "!"]
    assert iter_str(Text("")) == []


def test_boolean_iterate():
    assert iter_str(Boolean(True)) == ["true"]
    assert iter_str(Boolean(False)) == ["false"]


def test_void_iterate():
    assert iter_str(Void()) == []
