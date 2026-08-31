"""Golden tests: run each programs/**/*.lx and compare its stdout to the
matching *.expected file. Add a case by dropping in a new pair of files.

A program under programs/errors/ is expected to fail: the LynxError it raises
is written to the captured output the way main.py writes it to the terminal,
so its *.expected file holds whatever printed before the error plus the
one-line message.
"""

import contextlib
import io
from pathlib import Path

import pytest

from src.errors.errors import LynxError, LynxNotImplemented
from src.main import run

PROGRAMS = sorted(Path(__file__).parent.glob("programs/**/*.lx"))


def run_capturing(source):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        try:
            run(source)
        except LynxError as error:
            print(error)
    return out.getvalue()


@pytest.mark.parametrize("program", PROGRAMS, ids=lambda p: p.stem)
def test_program(program):
    expected = program.with_suffix(".expected").read_text()
    assert run_capturing(program.read_text()) == expected


def test_unimplemented_operation_reports_type_and_line():
    # Two lines on purpose: a hard-coded line 1 would pass a one-line version.
    with pytest.raises(LynxNotImplemented) as info:
        run(">> 'a' + 'b'\n>> 'a' - 'b'")
    assert str(info.value) == "NotImplemented on line 2: 'subtract' is not implemented yet for Text"


def test_unwritten_pair_names_both_types_and_the_line():
    # Nothing defines Boolean + Text, so the fallback reconciles the pair and
    # lands in a hole. The error must name the pair the user actually wrote —
    # not whichever type the fallback coerced towards — and stay a located lynx
    # error rather than a Python traceback.
    with pytest.raises(LynxNotImplemented) as info:
        run(">> text 42\n>> true + 'hi'")
    assert str(info.value) == (
        "NotImplemented on line 2: 'add' is not implemented yet between Boolean and Text"
    )


def test_unwritten_pair_reports_it_in_source_order():
    with pytest.raises(LynxNotImplemented) as info:
        run(">> 'hi' * true")
    assert str(info.value) == (
        "NotImplemented on line 1: 'multiply' is not implemented yet between Text and Boolean"
    )


# def test_unimplemented_prefix_operation_reports_type_and_line():
#     # Two lines on purpose: a hard-coded line 1 would pass a one-line version.
#     with pytest.raises(LynxNotImplemented) as info:
#         run(">> text 42\n>> len 'x'")
#     assert str(info.value) == "NotImplemented on line 2: 'lenght' is not implemented yet for Text"
