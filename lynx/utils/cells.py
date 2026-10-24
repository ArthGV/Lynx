"""Typing a bare csv-style cell: the one inference rule shared by `.csv` files
and the array cells inside a graph csv."""

from lynx.types.base_type import Type
from lynx.types.simple_type import Boolean, Number, Text, Void
from lynx.utils.numbers import parse_exact_number


def infer_cell(text: str, quoted: bool) -> Type:
    """A quoted cell is always Text. A bare one is `void`, `true`/`false`, a
    number that prints back exactly, or else Text."""
    if quoted:
        return Text(text)
    if text == "void":
        return Void()
    if text == "true":
        return Boolean(True)
    if text == "false":
        return Boolean(False)
    number = parse_exact_number(text)
    if number is not None:
        return Number(number)
    return Text(text)
