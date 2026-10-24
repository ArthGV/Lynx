"""Hashable keys and cell equality shared by Map and Table.

`map_key` turns any value into a hashable, type-qualified key so `1` and `'1'`
are distinct map keys. `value_from_key` rebuilds the value a key came from.
`cells_equal` is the table join's cell-comparison primitive.

The concrete types are imported lazily inside the functions — the same pattern
`Table.rows_where` already uses — because this module is imported by `map.py`
and `table.py` while the `lynx.types` package is still loading.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lynx.types.base_type import Type


def map_key(value: Type) -> tuple[str, Any]:
    """A hashable, type-qualified representation of a simple value, so `1`
    and `'1'` are distinct keys. Keys are restricted to simple types."""
    from lynx.types.simple_type import Boolean, Number, Text

    if isinstance(value, (Number, Text, Boolean)):
        return (value.type_name(), value.value)
    return (value.type_name(), repr(value))


def compare_cells(a: Type, b: Type) -> int:
    """Order two values of any types: same type by value, different types by
    rank. The one cell comparison collections use, so it is written once."""
    from lynx.utils.text import compare_raw

    return a.compare(b) if type(a) is type(b) else compare_raw(a.rank, b.rank)


def cells_equal(a: Type, b: Type) -> bool:
    """True when two table cells hold equal values of the same type."""
    return type(a) is type(b) and a.equals(b).is_true()


def value_from_key(raw: tuple[str, Any]) -> Type:
    """Reverse of `map_key`: rebuild the key value stored in a map."""
    from lynx.types.simple_type import Boolean, Number, Text, Void

    kind, value = raw
    if kind == "Number":
        return Number(value)
    if kind == "Text":
        return Text(value)
    if kind == "Boolean":
        return Boolean(value)
    return Void()
