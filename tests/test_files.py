"""Unit tests for the read/write file I/O feature.

Everything is driven through real lynx source (`run`), so the tests cover the
whole pipeline — keywords, parsing, the two new dispatch points, and the file
serialization layer — rather than calling the internals directly. Paths come
from pytest's tmp_path so tests never touch the repo or each other.

The contracts under test (final design):

* `.txt` is plain text: write Number/Text/Boolean/Void by their text form,
  read back *always* `Text` — the typed value is recovered by casting
  (`number`, `boolean`, `text`).
* `.csv` cells are typed: quoted `"..."` → Text, bare `void` → Void,
  `true`/`false` → Boolean, a number that round-trips exactly → Number,
  an empty cell → Text(""), any other bare token → Text. One data line reads
  as an Array, more as a Table; short rows are padded with Void.
* `.yaml` reads a root mapping into a Map (scalar keys, lenient scalars,
  nested maps/arrays, unsupported features → clear errors).
"""

import contextlib
import io
from pathlib import Path

import pytest

from src.errors.errors import LynxError
from src.main import run


def run_lx(source: str) -> str:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        run(source)
    return out.getvalue()


def run_err(source: str) -> str:
    with pytest.raises(LynxError) as info:
        run(source)
    return str(info.value)


def write_file(path: Path, content: str) -> Path:
    path.write_text(content)
    return path


# ---------------------------------------------------------------------------
# .txt
# ---------------------------------------------------------------------------


def test_txt_roundtrip_recovers_number_by_cast(tmp_path):
    p = tmp_path / "n.txt"
    assert run_lx(f"write 42, '{p}'") == ""
    assert p.read_text() == "42"
    assert run_lx(f">> read '{p}'") == "42\n"
    assert run_lx(f">> type (read '{p}')") == "Text\n"
    assert run_lx(f">> number (read '{p}')") == "42\n"
    assert run_lx(f">> type (number (read '{p}'))") == "Number\n"


def test_txt_write_content_is_exact_text_form(tmp_path):
    p = tmp_path / "t.txt"
    for source, expected in [
        ("'hello'", "hello"),
        ("42", "42"),
        ("3.5", "3.5"),
        ("-1", "-1"),
        ("true", "true"),
        ("false", "false"),
        ("void", "void"),
        ("''", ""),
    ]:
        run_lx(f"write {source}, '{p}'")
        assert p.read_text() == expected, source


def test_txt_always_reads_as_text_even_for_scalar_spellings(tmp_path):
    p = tmp_path / "b.txt"
    run_lx(f"write 'void', '{p}'")
    assert run_lx(f">> read '{p}'") == "void\n"
    assert run_lx(f">> type (read '{p}')") == "Text\n"
    run_lx(f"write '42', '{p}'")
    assert run_lx(f">> type (read '{p}')") == "Text\n"


def test_txt_roundtrip_equality(tmp_path):
    p = tmp_path / "t.txt"
    run_lx(f"write 'gam w', '{p}'")
    assert run_lx(f">> ('gam w' = read '{p}')") == "true\n"


# ---------------------------------------------------------------------------
# .csv — Array
# ---------------------------------------------------------------------------


def test_csv_array_write_bytes_and_roundtrip(tmp_path):
    p = tmp_path / "arr.csv"
    assert run_lx(f"a: (1, 2, 3)\nwrite a, '{p}'") == ""
    assert p.read_text() == "1,2,3"
    out = run_lx(f"a: (1, 2, 3)\nwrite a, '{p}'\nb: read '{p}'\n>> b\n>> type b\n>> a = b\n>> b 1\n")
    assert out == "[ 1, 2, 3 ]\nArray\ntrue\n2\n"


def test_csv_array_mixed_cells_keep_types(tmp_path):
    p = tmp_path / "mixed.csv"
    run_lx(f"a: (1, 'hello', true, void, '', '42')\nwrite a, '{p}'\n")
    assert p.read_text() == '1,hello,true,void,,"42"'
    out = run_lx(f"b: read '{p}'\n>> type b 0\n>> type b 1\n>> type b 2\n>> type b 3\n>> type b 4\n>> type b 5\n")
    assert out == "Number\nText\nBoolean\nVoid\nText\nText\n"


def test_csv_cells_quote_when_ambiguous_and_escape(tmp_path):
    p = tmp_path / "q.csv"
    src = (
        "a: ('42', 'true', 'void', '', 'hello, world', 'say \"hi\"')\n"
        f"write a, '{p}'\n"
        f"b: read '{p}'\n"
        ">> a = b\n"
        ">> b 5\n"
    )
    out = run_lx(src)
    assert p.read_text() == '"42","true","void",,"hello, world","say ""hi"""'
    assert out == 'true\nsay "hi"\n'
    assert (
        run_lx(f"b: read '{p}'\n>> type b 0\n>> type b 1\n>> type b 2\n>> type b 3\n>> type b 4\n>> type b 5\n")
        == "Text\nText\nText\nText\nText\nText\n"
    )


def test_csv_number_inference_is_roundtrip_exact(tmp_path):
    p = write_file(tmp_path / "exact.csv", "007,3.0,0.50,42,3.5,-1")
    out = run_lx(f"a: read '{p}'\n>> a\n>> type a 0\n>> type a 1\n>> type a 2\n>> type a 3\n>> type a 4\n>> type a 5\n")
    assert out == ("[ 007, 3.0, 0.50, 42, 3.5, -1 ]\nText\nText\nText\nNumber\nNumber\nNumber\n")


def test_csv_empty_file_reads_as_empty_array(tmp_path):
    p = tmp_path / "empty.csv"
    run_lx(f"a: array\nwrite a, '{p}'")
    assert p.read_text() == ""
    out = run_lx(f"b: read '{p}'\n>> type b\n>> b = array\n")
    assert out == "Array\ntrue\n"


def test_csv_single_line_of_quoted_empty_cell(tmp_path):
    p = write_file(tmp_path / "e.csv", '""')
    assert run_lx(f"a: read '{p}'\n>> type a 0") == "Text\n"


def test_csv_blank_lines_do_not_count(tmp_path):
    p = write_file(tmp_path / "blank.csv", "\n1,2,3\n\n")
    assert run_lx(f"a: read '{p}'\n>> type a") == "Array\n"
    p.write_text("\n")
    assert run_lx(f"a: read '{p}'\n>> type a") == "Array\n"


def test_csv_trailing_newline_is_one_line(tmp_path):
    p = write_file(tmp_path / "t.csv", "1,2,3\n")
    assert run_lx(f"a: read '{p}'\n>> type a") == "Array\n"


# ---------------------------------------------------------------------------
# .csv — Table
# ---------------------------------------------------------------------------


def test_csv_table_read_typed_columns(tmp_path):
    p = tmp_path / "people.csv"
    p.write_text("name,age,city\nada,36,london\nbob,hidden,\ncharlie,,")
    out = run_lx(f"t: read '{p}'\n>> t 'age'\n>> t 0\n>> t 1\n>> type t 'age' 0\n>> type t 'age' 1\n")
    assert out == (
        "[ 36, hidden,  ]\n{ name: ada; age: 36; city: london }\n{ name: bob; age: hidden; city:  }\nNumber\nText\n"
    )


def test_csv_table_write_bytes_and_roundtrip(tmp_path):
    p = tmp_path / "t.csv"
    run_lx(f"t: ['id': 1, 2; 'name': 'ada', 'bob']\nwrite t, '{p}'")
    assert p.read_text() == "id,name\n1,ada\n2,bob\n"
    out = run_lx(
        f"t: ['id': 1, 2; 'name': 'ada', 'bob']\nwrite t, '{p}'\nu: read '{p}'\n>> t = u\n>> u 'name' 1\n>> u 'id'\n"
    )
    assert out == "true\nbob\n[ 1, 2 ]\n"


def test_csv_table_short_rows_padded_with_void_and_rewrite(tmp_path):
    p = write_file(tmp_path / "pad.csv", "a,b,c\n1\n2,3")
    out = run_lx(f"t: read '{p}'\n>> t 'a'\n>> t 'b'\n>> t 'c'\nwrite t, '{tmp_path / 'rewrite.csv'}'\n")
    assert out == "[ 1, 2 ]\n[ void, 3 ]\n[ void, void ]\n"
    assert (tmp_path / "rewrite.csv").read_text() == "a,b,c\n1,void,void\n2,3,void\n"


def test_csv_table_row_too_long_is_error(tmp_path):
    p = write_file(tmp_path / "ragged.csv", "a,b,c\n1,2\n1,2,3,4")
    assert run_err(f">> read '{p}'") == ("Error on line 1: row 3 has 4 values but the header declares 3 columns")


def test_csv_table_non_text_spellings_are_valid_titles(tmp_path):
    p = write_file(tmp_path / "smart.csv", "42,true,name\n42,1,1")
    out = run_lx(f"t: read '{p}'\n>> t '42' 0\n>> t 'true' 0\n>> t 'name' 0\n>> t 0\n")
    assert out == "42\n1\n1\n{ 42: 42; true: 1; name: 1 }\n"


def test_csv_table_duplicate_titles_is_error(tmp_path):
    p = write_file(tmp_path / "dup.csv", "a,a\n1,2")
    assert run_err(f">> read '{p}'") == "TypeError on line 1: duplicate column title 'a'"


def test_csv_table_empty_title_allowed_once(tmp_path):
    p = write_file(tmp_path / "e.csv", ",b\n1,2")
    assert run_lx(f"t: read '{p}'\n>> t '' 0\n>> t 'b' 0") == "1\n2\n"


def test_csv_table_two_empty_titles_is_duplicate_error(tmp_path):
    p = write_file(tmp_path / "ee.csv", ",,a\n1,2,3")
    assert run_err(f">> read '{p}'") == ("TypeError on line 1: duplicate column title ''")


def test_csv_blank_lines_inside_table_are_skipped(tmp_path):
    p = write_file(tmp_path / "b.csv", "a,b\n1,2\n\n3,4\n")
    assert run_lx(f"t: read '{p}'\n>> t 'a'") == "[ 1, 3 ]\n"


def test_csv_write_complex_array_element_is_error(tmp_path):
    p = tmp_path / "c.csv"
    assert run_err(f"write (1, (2, 3)), '{p}'") == (
        "TypeError on line 1: cannot write Array values in a .csv; "
        "only scalars (number, text, boolean, void) are supported"
    )


def test_csv_write_complex_table_cell_is_error(tmp_path):
    p = tmp_path / "c.csv"
    assert run_err(f"t: ['a': (1, 2)]\nwrite t, '{p}'") == (
        "TypeError on line 2: cannot write Array values in a .csv; "
        "only scalars (number, text, boolean, void) are supported"
    )


def test_csv_write_empty_table_is_error(tmp_path):
    p = tmp_path / "e.csv"
    assert run_err(f"write table, '{p}'") == ("Error on line 1: cannot write a table with no columns to .csv")


def test_csv_write_newline_text_is_error(tmp_path):
    t = write_file(tmp_path / "multi.txt", "line one\nline two")
    p = tmp_path / "nl.csv"
    assert run_err(f"a: ((read '{t}'), 'x')\nwrite a, '{p}'") == (
        "Error on line 2: cannot write a text containing a newline to a .csv"
    )


def test_csv_text_crosses_formats_via_txt_read(tmp_path):
    t = write_file(tmp_path / "quote.txt", "O'Brien")
    p = tmp_path / "x.csv"
    run_lx(f"a: ((read '{t}'), 'plain')\nwrite a, '{p}'")
    assert p.read_text() == "O'Brien,plain"
    assert run_lx(f"b: read '{p}'\n>> b 0") == "O'Brien\n"


# ---------------------------------------------------------------------------
# .yaml
# ---------------------------------------------------------------------------


def test_yaml_write_bytes(tmp_path):
    p = tmp_path / "m.yaml"
    run_lx(
        "m: { 'name': 'lynx'; 'count': 3; 'ok': true; 'nothing': void; "
        "'empty_text': ''; 'list': (1, 'two'); 'empty_list': array; "
        "'empty_map': map; 'nested': { 'a': 1 } }\n"
        f"write m, '{p}'\n"
    )
    assert p.read_text() == (
        "'name': 'lynx'\n"
        "'count': 3\n"
        "'ok': true\n"
        "'nothing': void\n"
        "'empty_text': ''\n"
        "'list':\n"
        "  - 1\n"
        "  - 'two'\n"
        "'empty_list': []\n"
        "'empty_map': {}\n"
        "'nested':\n"
        "  'a': 1\n"
    )


def test_yaml_roundtrip_equality_and_nested_access(tmp_path):
    p = tmp_path / "m.yaml"
    source = (
        "m: { 'name': 'lynx'; 'count': 3; 'tags': ('read', 'write'); "
        "'nested': { 'ok': true; 'none': void } }\n"
        f"write m, '{p}'\nn: read '{p}'\n"
    )
    out = run_lx(source + ">> m = n\n>> n 'tags' 1\n>> n 'nested' 'none'\n")
    assert out == "true\nwrite\nvoid\n"
    out = run_lx(source + ">> type n 'tags'\n>> type n 'nested'\n")
    assert out == "Array\nMap\n"


def test_yaml_apostrophe_roundtrip(tmp_path):
    t = write_file(tmp_path / "q.txt", "let's go")
    p = tmp_path / "q.yaml"
    run_lx(f"m: {{ 'k': (read '{t}') }}\nwrite m, '{p}'\n")
    assert p.read_text() == "'k': 'let''s go'\n"
    assert run_lx(f"n: read '{p}'\n>> n 'k'") == "let's go\n"


def test_yaml_empty_root_mapping(tmp_path):
    p = tmp_path / "e.yaml"
    run_lx(f"m: map\nwrite m, '{p}'\n")
    assert p.read_text() == "{}\n"
    assert run_lx(f"n: read '{p}'\n>> type n\n>> n = map\n") == "Map\ntrue\n"


def test_yaml_list_of_maps_roundtrip(tmp_path):
    p = tmp_path / "l.yaml"
    run_lx(f"m: {{ 'people': ( {{ 'name': 'ada'; 'age': 36 }}, {{ 'name': 'bob' }} ) }}\nwrite m, '{p}'\n")
    assert p.read_text() == ("'people':\n  - 'name': 'ada'\n    'age': 36\n  - 'name': 'bob'\n")
    out = run_lx(f"n: read '{p}'\n>> n 'people' 0 'name'\n>> n 'people' 0 'age'\n>> n 'people' 1 'name'\n")
    assert out == "ada\n36\nbob\n"


def test_yaml_keys_keep_number_vs_text_type(tmp_path):
    p = write_file(tmp_path / "k.yaml", "1: 'one'\n'2': 'two'\n")
    out = run_lx(f"m: read '{p}'\n>> m 1\n>> m '2'\n>> type m 1\n>> m '1'\n")
    assert out == "one\ntwo\nText\nvoid\n"


def test_yaml_lenient_scalar_reading(tmp_path):
    p = write_file(
        tmp_path / "l.yaml",
        "# a config\nname: lynx   # trailing comment\n"
        "count: 3\nflag: true\nnone1: null\nnone2: ~\nnone3: void\nempty:\n",
    )
    out = run_lx(
        f"m: read '{p}'\n"
        ">> m 'name'\n>> m 'count'\n>> m 'flag'\n"
        ">> m 'none1'\n>> m 'none2'\n>> m 'none3'\n>> m 'empty'\n"
    )
    assert out == "lynx\n3\ntrue\nvoid\nvoid\nvoid\nvoid\n"


def test_yaml_duplicate_key_is_error(tmp_path):
    p = write_file(tmp_path / "d.yaml", "a: 1\na: 2\n")
    assert run_err(f"m: read '{p}'") == "TypeError on line 1: map keys must be unique, got duplicates a"


def test_yaml_duplicate_keys_multi_error_named(tmp_path):
    p = write_file(tmp_path / "d.yaml", "a: 1\nb: 2\na: 3\nb: 4\n")
    assert run_err(f"m: read '{p}'") == ("TypeError on line 1: map keys must be unique, got duplicates a, b")


def test_yaml_nested_duplicate_key_is_error(tmp_path):
    p = write_file(tmp_path / "d.yaml", "outer:\n  a: 1\n  a: 2\n")
    assert run_err(f"m: read '{p}'") == "TypeError on line 1: map keys must be unique, got duplicates a"


def test_yaml_root_sequence_or_scalar_is_error(tmp_path):
    for content in ("- a\n- b\n", "42\n", "[]\n"):
        p = write_file(tmp_path / "s.yaml", content)
        assert run_err(f">> read '{p}'") == (
            "Error on line 1: a .yaml file must be a mapping at the top level to read into a Map"
        ), content


@pytest.mark.parametrize(
    "content, token",
    [
        ("'a': &anchor 1\n", "&"),
        ("'a': *alias\n", "*"),
        ("'a': !tag 1\n", "!"),
        ("'a': |\n  text\n", "|"),
        ("<<: 'other'\n", "<<"),
        ("'a': [1, 2]\n", "["),
        ("'a': {b: 1}\n", "{"),
        ("'a':\n\t'b': 1\n", "\t"),
    ],
)
def test_yaml_unsupported_features_error(tmp_path, content, token):
    p = write_file(tmp_path / "f.yaml", content)
    assert run_err(f">> read '{p}'") == (f"Error on line 1: yaml feature '{token}' is not supported by lynx")


def test_yaml_write_nested_table_is_error(tmp_path):
    p = tmp_path / "t.yaml"
    assert run_err(f"write {{ 't': ['a': 1] }}, '{p}'\n") == (
        "TypeError on line 1: cannot write Table values in a .yaml; only scalars, maps and arrays are supported"
    )


def test_yaml_write_newline_text_is_error(tmp_path):
    t = write_file(tmp_path / "multi.txt", "line one\nline two")
    p = tmp_path / "nl.yaml"
    assert run_err(f"write {{ 'k': (read '{t}') }}, '{p}'\n") == (
        "Error on line 1: cannot write a text containing a newline to a .yaml"
    )


# ---------------------------------------------------------------------------
# format and path errors
# ---------------------------------------------------------------------------


def test_write_type_mismatches(tmp_path):
    assert run_err(f"write 42, '{tmp_path / 'x.csv'}'") == (
        "TypeError on line 1: a value of type Number writes to .txt, not .csv"
    )
    assert run_err(f"write 'hi', '{tmp_path / 'x.csv'}'") == (
        "TypeError on line 1: a value of type Text writes to .txt, not .csv"
    )
    assert run_err(f"write true, '{tmp_path / 'x.yaml'}'") == (
        "TypeError on line 1: a value of type Boolean writes to .txt, not .yaml"
    )
    assert run_err(f"write (1, 2), '{tmp_path / 'x.yaml'}'") == (
        "TypeError on line 1: a value of type Array writes to .csv, not .yaml"
    )
    assert run_err(f"write (1, 2), '{tmp_path / 'x.txt'}'") == (
        "TypeError on line 1: a value of type Array writes to .csv, not .txt"
    )
    assert run_err(f"t: table\nwrite t, '{tmp_path / 'x.yaml'}'") == (
        "TypeError on line 2: a value of type Table writes to .csv, not .yaml"
    )


def test_unsupported_extensions(tmp_path):
    p = tmp_path / "x.yml"
    p.write_text("a: 1\n")
    assert run_err(f">> read '{p}'") == ("Error on line 1: unsupported file format '.yml', use .txt, .csv or .yaml")
    assert run_err(f"write 42, '{tmp_path / 'x.docx'}'") == (
        "Error on line 1: unsupported file format '.docx', use .txt, .csv or .yaml"
    )
    assert run_err(f"write 42, '{tmp_path / 'noext'}'") == (
        "Error on line 1: unsupported file format '', use .txt, .csv or .yaml"
    )


def test_read_missing_file(tmp_path):
    p = tmp_path / "missing.txt"
    assert run_err(f">> read '{p}'") == (f"Error on line 1: cannot read '{p}': file not found")


def test_read_a_directory(tmp_path):
    d = tmp_path / "dir.txt"
    d.mkdir()
    assert run_err(f">> read '{d}'") == (f"Error on line 1: cannot read '{d}': Is a directory")


def test_write_a_directory(tmp_path):
    d = tmp_path / "dir.csv"
    d.mkdir()
    assert run_err(f"write 42, '{d}'") == (f"Error on line 1: cannot write '{d}': Is a directory")


def test_write_creates_parent_directories(tmp_path):
    p = tmp_path / "a" / "b" / "deep.txt"
    run_lx(f"write 'hi', '{p}'")
    assert p.read_text() == "hi"


def test_write_path_must_be_text(tmp_path):
    assert run_err("write 42, 5") == ("TypeError on line 1: write needs a text path, got Number")


def test_read_non_text_operand(tmp_path):
    assert run_err(">> read 5") == ("TypeError on line 1: read needs a text path, got Number")


# ---------------------------------------------------------------------------
# write -> read -> (cast) -> equal, for every type
# ---------------------------------------------------------------------------


def test_roundtrip_all_types(tmp_path):
    n = tmp_path / "n.txt"
    f = tmp_path / "f.txt"
    s = tmp_path / "s.txt"
    t = tmp_path / "t.txt"
    cells = tmp_path / "cells.csv"
    y = tmp_path / "m.yaml"
    t2 = tmp_path / "t.csv"
    out = run_lx(
        f"write 42, '{n}'\n"
        f"write 3.5, '{f}'\n"
        f"write 'lynx', '{s}'\n"
        f"write true, '{t}'\n"
        f"n1: number (read '{n}')\n"
        f"n2: number (read '{f}')\n"
        f"n3: (read '{s}')\n"
        f"n4: boolean (read '{t}')\n"
        f">> n1 = 42\n"
        f">> n2 = 3.5\n"
        f">> n3 = 'lynx'\n"
        f">> n4 = true\n"
        f"a: (1, true, false, void, '42')\n"
        f"write a, '{cells}'\n"
        f"b: read '{cells}'\n"
        f">> a = b\n"
        f">> b 2\n"
        f">> type b 3\n"
        f"m: {{ 'v': void; 'f': false; 'num': 3.5 }}\n"
        f"write m, '{y}'\n"
        f"nn: read '{y}'\n"
        f">> m = nn\n"
        f">> nn 'f'\n"
        f">> nn 'v'\n"
        f"tab: ['id': 1; 'name': 'ada']\n"
        f"write tab, '{t2}'\n"
        f"u: read '{t2}'\n"
        f">> tab = u\n"
    )
    assert out == "true\ntrue\ntrue\ntrue\ntrue\nfalse\nVoid\ntrue\nfalse\nvoid\ntrue\n"
    assert run_lx(f"u: read '{t2}'\n>> u 'name' 0") == "ada\n"
