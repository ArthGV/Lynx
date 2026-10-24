"""Graph csv value cells: scalars, and arrays written as `(1, 'a,b', true)`.

An array cell lists its items separated by commas. Text items are always
single-quoted with `''` for a quote inside, so commas, parentheses and quotes
in them are safe; other items are bare (`void`, `true`, `false`, a number).

A Text value that would itself read as an array (`(1, 2)`) is written with one
extra leading backslash, and the reader removes exactly one in that case, so
the two can never be confused. Text that does not look like an array (including
older files with backslashes) is untouched.
"""

from lynx.errors.errors import LynxTypeError
from lynx.types.array import Array
from lynx.types.base_type import Type
from lynx.types.simple_type import Boolean, Number, Text, Void
from lynx.utils.cells import infer_cell

ESCAPE = "\\"


def parse_array_cell(text: str) -> Array | None:
    """The Array a `(...)` cell holds, or None if `text` is not a well-formed
    array cell (so plain text such as `(oops` stays text)."""
    if not (text.startswith("(") and text.endswith(")")):
        return None
    body = text[1:-1]
    if not body.strip():
        return Array([]) if body == "" else None
    items: list[Type] = []
    i, n = 0, len(body)
    while True:
        while i < n and body[i] == " ":
            i += 1
        if i < n and body[i] == "'":
            i += 1
            chars: list[str] = []
            while True:
                if i >= n:
                    return None  # unterminated quote
                if body[i] == "'":
                    if i + 1 < n and body[i + 1] == "'":
                        chars.append("'")
                        i += 2
                        continue
                    i += 1
                    break
                chars.append(body[i])
                i += 1
            items.append(Text("".join(chars)))
            while i < n and body[i] == " ":
                i += 1
            if i < n and body[i] != ",":
                return None
        else:
            end = body.find(",", i)
            end = n if end == -1 else end
            items.append(infer_cell(body[i:end].strip(), False))
            i = end
        if i >= n:
            return Array(items)
        i += 1  # the comma
        if i >= n:
            items.append(Text(""))  # a trailing comma leaves an empty last item
            return Array(items)


def write_array_cell(array: Array) -> str:
    return "(" + ", ".join(_array_item(item) for item in array.value) + ")"


def _array_item(item: Type) -> str:
    if isinstance(item, Text):
        return "'" + item.value.replace("'", "''") + "'"
    if isinstance(item, Boolean):
        return "true" if item.value else "false"
    if isinstance(item, Void):
        return "void"
    if isinstance(item, Number):
        return str(item.value)
    raise LynxTypeError(f"cannot write a {item.type_name()} inside an array in a graph .csv")


def escape_text(text: str) -> str:
    """Text as written in a value cell: prefixed when it would read as an array."""
    return ESCAPE + text if parse_array_cell(text.lstrip(ESCAPE)) is not None else text


def decode_value_cell(value: Type) -> Type:
    """A value cell as read from the csv: an array cell becomes an Array, an
    escaped one the Text it stands for, anything else is left alone."""
    if not isinstance(value, Text):
        return value
    text = value.value
    if text.startswith(ESCAPE) and parse_array_cell(text.lstrip(ESCAPE)) is not None:
        return Text(text[1:])
    parsed = parse_array_cell(text)
    return parsed if parsed is not None else value
