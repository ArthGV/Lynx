"""`>>>` outside a function is rejected at parse time with LynxReturnError,
before any statement runs; inside a function (even under a loop or `if`) it is
fine. The golden programs in programs/errors/return_outside_*.lx cover the
printed message; these tests pin the error class and its line number."""

import pytest

from lynx.core.lexer import tokenize
from lynx.core.parser import Parser
from lynx.errors.errors import LynxReturnError


def parse(source):
    return Parser(tokenize(source)).parse()


@pytest.mark.parametrize(
    "source, line",
    [
        (">>> 1\n", 1),
        (">> 'a'\n>>> 1\n", 2),
        ("loop i: 1__3\n  >>> i\n", 2),
        ("if true\n  >>> 1\n", 2),
        ("f: x\n  >>> x\n>>> 2\n", 3),  # leaving a function restores the depth
    ],
)
def test_return_outside_a_function_raises(source, line):
    with pytest.raises(LynxReturnError) as raised:
        parse(source)
    assert raised.value.line == line
    assert str(raised.value) == f"ReturnError on line {line}: return outside of a function"


@pytest.mark.parametrize(
    "source",
    [
        "f: x\n  >>> x\n",
        "f: x\n  if x\n    >>> 1\n  >>> 2\n",
        "f: x\n  loop i: 1__3\n    >>> i\n",
        "f: x\n  g: y\n    >>> y\n  >>> g x\n",  # nested function
    ],
)
def test_return_inside_a_function_parses(source):
    parse(source)
