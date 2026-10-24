"""Helpers for comparing and building lynx values in tests."""

from lynx.types import Array, Boolean, Graph, Map, Number, Table, Text, Void


def same(a, b):
    """Strictly equal: same types all the way down, same values."""
    if type(a) is not type(b):
        return False
    if isinstance(a, (Number, Text, Boolean)):
        return a.value == b.value
    if isinstance(a, Void):
        return True
    if isinstance(a, Array):
        return len(a.value) == len(b.value) and all(same(x, y) for x, y in zip(a.value, b.value))
    if isinstance(a, Map):
        return list(a.value) == list(b.value) and all(same(a.value[k], b.value[k]) for k in a.value)
    if isinstance(a, Table):
        return list(a.columns) == list(b.columns) and all(
            len(a.columns[c]) == len(b.columns[c]) and all(same(x, y) for x, y in zip(a.columns[c], b.columns[c]))
            for c in a.columns
        )
    if isinstance(a, Graph):
        return (
            list(a.nodes) == list(b.nodes)
            and list(a.edges) == list(b.edges)
            and all(same(a.nodes[k], b.nodes[k]) for k in a.nodes)
            and all(same(a.edges[k], b.edges[k]) for k in a.edges)
        )
    raise AssertionError(f"cannot compare {type(a).__name__}")


def lx(obj):
    """A lynx value from plain Python: dict -> Map, list -> Array,
    str -> Text, int/float -> Number, bool -> Boolean, None -> Void."""
    if isinstance(obj, dict):
        mapping = Map()
        for key, value in obj.items():
            mapping.set_item(lx(key), lx(value))
        return mapping
    if isinstance(obj, list):
        return Array([lx(item) for item in obj])
    if isinstance(obj, bool):
        return Boolean(obj)
    if isinstance(obj, (int, float)):
        return Number(obj)
    if obj is None:
        return Void()
    if isinstance(obj, str):
        return Text(obj)
    return obj
