"""Unit tests for value methods not exposed as langauge keywords.

`middle`, `power`, `root`, and `not_` are implemented on every value type but
are not reachable from `.lx` programs — there is no keyword for them. These are
tested here directly against the values module.
"""

from src.runtime.values import Array, Boolean, Number, Text, Void
from src.errors.errors import LynxNotImplemented

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
    assert print_(a.text()) == "1, true"
    assert print_(a.number()) == "2"
    assert a.boolean().is_true() is True
    assert arr().boolean().is_true() is False
    assert type(a.void()) is Void


def test_array_comparison():
    assert arr(Number(1), Number(2)).equals(arr(Number(1), Number(2))).is_true()
    assert arr(Number(1), Number(2)).equals(arr(Number(1), Number(3))).is_true() is False
    assert arr(Number(1), Number(2)).greater(arr(Number(1))).is_true()
    assert arr(Number(1), Number(2)).less(arr(Number(1), Number(2), Number(3))).is_true()


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
