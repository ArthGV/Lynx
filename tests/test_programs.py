"""Golden tests: run each programs/*.lx and compare its stdout to the
matching *.expected file. Add a case by dropping in a new pair of files.
"""

import contextlib
import io
from pathlib import Path

import pytest

from src.main import run
from src.errors import LynxNotImplemented

PROGRAMS = sorted(Path(__file__).parent.glob("programs/*.lx"))


def run_capturing(source):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        run(source)
    return out.getvalue()


@pytest.mark.parametrize("program", PROGRAMS, ids=lambda p: p.stem)
def test_program(program):
    expected = program.with_suffix(".expected").read_text()
    assert run_capturing(program.read_text()) == expected


def test_unimplemented_operation_reports_type_and_line():
    with pytest.raises(LynxNotImplemented) as info:
        run(">> 'a' > 1")
    assert str(info.value) == "NotImplemented on line 1: 'greater' is not implemented yet for Text"
