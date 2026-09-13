"""Golden tests: run each programs/**/*.lx and compare its stdout to the
matching *.expected file. Add a case by dropping in a new pair of files.

Full-line `//` comments in a *.expected file are ignored; they exist so each
test block can be labelled next to the output it produces.

A program under programs/errors/ is expected to fail: the LynxError it raises
is written to the captured output the way main.py writes it to the terminal,
so its *.expected file holds whatever printed before the error plus the
one-line message.
"""

import contextlib
import io
from pathlib import Path

import pytest

from src.errors.errors import LynxError
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


def strip_expected_comments(text):
    """Remove full-line // comment lines from golden-test expected output."""
    return "".join(
        line for line in text.splitlines(keepends=True)
        if not line.strip().startswith("//")
    )


@pytest.mark.parametrize("program", PROGRAMS, ids=lambda p: p.stem)
def test_program(program):
    expected = program.with_suffix(".expected").read_text()
    assert run_capturing(program.read_text()) == strip_expected_comments(expected)


def test_strip_expected_comments():
    text = "a\nb\n// a block header\nc\n\n// trailing\n"
    assert strip_expected_comments(text) == "a\nb\nc\n\n"
