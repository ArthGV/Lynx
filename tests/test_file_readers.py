"""Reading hand-written `.csv` and `.yaml` files, the way real ones look.

The round-trip tests only cover what lynx itself writes. These cover files
produced elsewhere: other line endings, a byte-order mark, quoting styles,
common YAML layouts, and every kind of malformed input, which must raise an
error that names the problem and never be skipped silently.
"""

import pytest
from lynx_values import lx, same

from lynx.core import files
from lynx.errors.errors import LynxError
from lynx.types import Array, Table, Text


def read_text(tmp_path, name, content):
    path = tmp_path / name
    path.write_bytes(content.encode("utf-8") if isinstance(content, str) else content)
    return files.read(str(path))


def read_error(tmp_path, name, content):
    with pytest.raises(LynxError) as info:
        read_text(tmp_path, name, content)
    return str(info.value)


# --- csv ---------------------------------------------------------------------


def table(**columns):
    return Table([(name, [lx(cell) for cell in cells]) for name, cells in columns.items()])


CSV_OK = {
    "lf": ("a,b\n1,2\n", table(a=[1], b=[2])),
    "crlf": ("a,b\r\n1,2\r\n3,4\r\n", table(a=[1, 3], b=[2, 4])),
    "old mac cr": ("a,b\r1,2\r3,4\r", table(a=[1, 3], b=[2, 4])),
    "no trailing newline": ("a,b\n1,2", table(a=[1], b=[2])),
    "blank lines skipped": ("a,b\n\n1,2\n   \n3,4\n\n", table(a=[1, 3], b=[2, 4])),
    "byte order mark": ("\ufeffa,b\n1,2\n", table(a=[1], b=[2])),
    "quoted newline": ('name,note\nbob,"line1\nline2"\n', table(name=["bob"], note=["line1\nline2"])),
    "quoted crlf inside": ('a\r\n"x\r\ny"\r\n', table(a=["x\r\ny"])),
    "quoted comma and quote": ('a\n"x,""y"""\n', table(a=['x,"y"'])),
    "quoted number is text": ('a\n"12"\n', table(a=["12"])),
    "bare types": ("a,b,c,d\n1,true,void,x\n", table(a=[1], b=[True], c=[None], d=["x"])),
    "cells are not trimmed": ("a,b\n x , y \n", table(a=[" x "], b=[" y "])),
    "short row padded with void": ("a,b,c\n1\n", table(a=[1], b=[None], c=[None])),
    "empty cell is empty text": ("a,b\n,2\n", table(a=[""], b=[2])),
    "exotic separators stay inside a cell": ("a\nx\u2028y\n", table(a=["x\u2028y"])),
    "inf and nan are text": ("a,b\ninf,nan\n", table(a=["inf"], b=["nan"])),
    "number-looking text stays text": ("a\n007\n1_0\n 12\n", table(a=["007", "1_0", " 12"])),
    "junk after a closing quote joins the cell": ('a,b\n"ab"c,2\n', table(a=["abc"], b=[2])),
    "stray quote inside a bare cell": ('a\nab"c\n', table(a=['ab"c'])),
}


@pytest.mark.parametrize("name", CSV_OK)
def test_csv_reads(tmp_path, name):
    content, expected = CSV_OK[name]
    assert same(read_text(tmp_path, "t.csv", content), expected)


def test_csv_single_line_is_an_array(tmp_path):
    assert same(read_text(tmp_path, "a.csv", "1,x,true\n"), lx([1, "x", True]))
    assert same(read_text(tmp_path, "a.csv", '""\n'), Array([Text("")]))
    assert same(read_text(tmp_path, "a.csv", ""), Array([]))


def test_csv_unterminated_quote_names_its_line(tmp_path):
    message = read_error(tmp_path, "u.csv", 'a,b\n1,2\n"unterminated,3\nx,y\n')
    assert "unterminated quoted cell starting on line 3" in message


def test_csv_ragged_and_duplicate_headers_still_error(tmp_path):
    assert "row 2 has 3 values but the header declares 2" in read_error(tmp_path, "r.csv", "a,b\n1,2,3\n")
    assert "duplicate column title 'a'" in read_error(tmp_path, "d.csv", "a,a\n1,2\n")


def test_csv_invalid_utf8_is_a_lynx_error(tmp_path):
    assert "not valid UTF-8" in read_error(tmp_path, "l.csv", "a\ncaf\xe9\n".encode("latin-1"))


# --- yaml --------------------------------------------------------------------

YAML_OK = {
    "list indented under its key": ("items:\n  - a\n  - b\nother: 1\n", {"items": ["a", "b"], "other": 1}),
    "list at its key's indent": ("items:\n- a\n- b\nother: 1\n", {"items": ["a", "b"], "other": 1}),
    "double quotes": ('name: "Ada Lovelace"\n', {"name": "Ada Lovelace"}),
    "double quote escapes": ('a: "x\\ny\\t\\"q\\" \\u00e9 \\x41"\n', {"a": 'x\ny\t"q" \u00e9 A'}),
    "double quoted key": ('"a b": 1\n', {"a b": 1}),
    "single quote escape": ("a: 'it''s'\nb: it's\n", {"a": "it's", "b": "it's"}),
    "document start": ("---\nname: x\n", {"name": "x"}),
    "document end": ("name: x\n...\n", {"name": "x"}),
    "comment before document start": ("# c\n---\nname: x\n", {"name": "x"}),
    "crlf": ("a: 1\r\nb: 2\r\n", {"a": 1, "b": 2}),
    "byte order mark": ("\ufeffa: 1\n", {"a": 1}),
    "url with port and query": ("url: http://x.com:8080/a?b=1&c=2\n", {"url": "http://x.com:8080/a?b=1&c=2"}),
    "hash inside a word is not a comment": ("a: x#y\nb: http://x.com/#frag\n", {"a": "x#y", "b": "http://x.com/#frag"}),
    "comment after a space": ("a: 1 # one\nb: 'x # y' # z\nc: \"q # r\" # s\n", {"a": 1, "b": "x # y", "c": "q # r"}),
    "trailing colon text": ("t: 12:30:45\n", {"t": "12:30:45"}),
    "colon inside list items": (
        "l:\n  - http://a.b/c\n  - 12:30\n  - a: b\n",
        {"l": ["http://a.b/c", "12:30", {"a": "b"}]},
    ),
    "special characters inside plain text": (
        "a: Hello!\nb: A & B\nc: 5*3\nd: a|b\ne: ~x\nf: a<<b\ng: Notes [draft]\nh: a{2}\n",
        {
            "a": "Hello!",
            "b": "A & B",
            "c": "5*3",
            "d": "a|b",
            "e": "~x",
            "f": "a<<b",
            "g": "Notes [draft]",
            "h": "a{2}",
        },
    ),
    "null forms": ("a: null\nb: ~\nc:\nd: Null\ne: void\n", {"a": None, "b": None, "c": None, "d": None, "e": None}),
    "boolean forms": (
        "a: true\nb: True\nc: FALSE\nd: yes\ne: No\n",
        {"a": True, "b": True, "c": False, "d": "yes", "e": "No"},
    ),
    "numbers that print back": ("a: 1\nb: -2.5\nc: 0\n", {"a": 1, "b": -2.5, "c": 0}),
    "numbers that do not stay text": (
        "a: 0x1F\nb: 1_000\nc: .5\nd: 1.\ne: +1\nf: 1e3\ng: -0\nh: 007\ni: inf\nj: nan\n",
        {
            "a": "0x1F",
            "b": "1_000",
            "c": ".5",
            "d": "1.",
            "e": "+1",
            "f": "1e3",
            "g": "-0",
            "h": "007",
            "i": "inf",
            "j": "nan",
        },
    ),
    "list of maps": (
        "people:\n  - name: Ada\n    age: 36\n  - name: Bob\n    age: 41\n",
        {"people": [{"name": "Ada", "age": 36}, {"name": "Bob", "age": 41}]},
    ),
    "list of lists": ("m:\n  - - 1\n    - 2\n  - - 3\n", {"m": [[1, 2], [3]]}),
    "dash alone then a block": ("m:\n  -\n    a: 1\n  - b\n", {"m": [{"a": 1}, "b"]}),
    "four space indentation": ("a:\n    b:\n        c: 1\n", {"a": {"b": {"c": 1}}}),
    "empty collections": ("a: []\nb: {}\n", {"a": [], "b": {}}),
    "number keys": ("1: a\n2.5: b\n", {1: "a", 2.5: "b"}),
    "boolean key": ("true: c\n", {True: "c"}),
    "key with spaces": ("first name: Ada\n", {"first name": "Ada"}),
    "empty string key": ("'': 1\n", {"": 1}),
    "colon with no space is text": ("a:1: x\n", {"a:1": "x"}),
    "empty map": ("{}\n", {}),
}


@pytest.mark.parametrize("name", YAML_OK)
def test_yaml_reads(tmp_path, name):
    content, expected = YAML_OK[name]
    assert same(read_text(tmp_path, "t.yaml", content), lx(expected))


YAML_ERRORS = {
    "multi-line plain value": ("a: first\n  second\nb: 1\n", "yaml line 2: unexpected indentation"),
    "odd indentation": ("a:\n  x: 1\n   y: 2\n", "yaml line 3: unexpected indentation"),
    "text after a quoted value": ("a: 'x' y\n", "yaml line 1: unexpected text after a quoted value"),
    "unterminated single quote": ("a: 'oops\n", "yaml line 1: unterminated quoted text"),
    "unterminated double quote": ('a: "oops\n', "yaml line 1: unterminated quoted text"),
    "unknown escape": ('a: "x\\qy"\n', "yaml line 1: unknown escape \\q"),
    "bad hex escape": ('a: "\\xZZ"\n', "yaml line 1: bad \\x escape"),
    "list item where a key belongs": ("a: 1\n- b\n", "yaml line 2: a list item where a key was expected"),
    "line that is not a key": ("a: 1\njust text\n", "yaml line 2: expected 'key: value'"),
    "array as a key": ("[]: 1\n", "yaml line 1: mapping keys must be scalars"),
    "block scalar": ("a: |\n  text\nb: 1\n", "yaml feature '|' is not supported by lynx (line 1)"),
    "folded scalar": ("a: >\n  text\n", "yaml feature '>' is not supported by lynx (line 1)"),
    "flow sequence": ("a: [1, 2]\n", "yaml feature '[' is not supported by lynx (line 1)"),
    "flow map": ("a: {x: 1}\n", "yaml feature '{' is not supported by lynx (line 1)"),
    "anchor": ("a: &x 1\n", "yaml feature '&' is not supported by lynx (line 1)"),
    "alias": ("a: *x\n", "yaml feature '*' is not supported by lynx (line 1)"),
    "tag": ("a: !!str 5\n", "yaml feature '!' is not supported by lynx (line 1)"),
    "merge key": ("<<: x\n", "yaml feature '<<' is not supported by lynx (line 1)"),
    "tab indentation": ("a:\n\tb: 1\n", "yaml feature '\t' is not supported by lynx (line 2)"),
    "top-level list": ("- 1\n- 2\n", "must be a mapping at the top level"),
    "top-level scalar": ("just text\n", "must be a mapping at the top level"),
    "only comments": ("# nothing\n", "must be a mapping at the top level"),
    "no space after colon at the top": ("a:1\nb: 2\n", "must be a mapping at the top level"),
    "duplicate keys": ("a: 1\na: 2\n", "map keys must be unique, got duplicates a"),
    "duplicate nested keys": ("o:\n  a: 1\n  a: 2\n", "map keys must be unique, got duplicates a"),
}


@pytest.mark.parametrize("name", YAML_ERRORS)
def test_yaml_errors_name_the_problem(tmp_path, name):
    content, expected = YAML_ERRORS[name]
    assert expected in read_error(tmp_path, "e.yaml", content)


def test_yaml_never_drops_input_silently(tmp_path):
    # every line of a readable file shows up in the result, or the read fails
    content = "a: 1\nb:\n  - x\n  - y\nc:\n  d: 2\ne: 'last'\n"
    result = read_text(tmp_path, "all.yaml", content)
    assert same(result, lx({"a": 1, "b": ["x", "y"], "c": {"d": 2}, "e": "last"}))
