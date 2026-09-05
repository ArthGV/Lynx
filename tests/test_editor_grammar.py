"""The VS Code extension's generated files must match grammar.py.

editors/vscode/generate.py builds the TextMate grammar and the language
configuration out of grammar.py's tables. These tests fail when grammar.py has
moved on and the checked-in files haven't been regenerated, so highlighting
can't silently fall behind the language.

    python editors/vscode/generate.py   # to fix a failure here
"""

import json
import sys
from pathlib import Path

import pytest

VSCODE = Path(__file__).resolve().parents[1] / "editors" / "vscode"
sys.path.insert(0, str(VSCODE))

from generate import (  # noqa: E402
    CONFIG_OUT,
    GRAMMAR_OUT,
    SYMBOL_SCOPE,
    build_config,
    build_grammar,
)

from src.core.grammar import KEYWORDS, SYMBOLS  # noqa: E402


@pytest.mark.parametrize(
    "path, build",
    [(GRAMMAR_OUT, build_grammar), (CONFIG_OUT, build_config)],
    ids=lambda value: getattr(value, "name", ""),
)
def test_generated_file_is_current(path, build):
    assert json.loads(path.read_text()) == build(), (
        f"{path.name} is stale — run `python editors/vscode/generate.py`"
    )


def test_every_symbol_is_coloured():
    assert set(SYMBOLS.values()) <= set(SYMBOL_SCOPE)


def test_every_keyword_is_coloured():
    matched = " ".join(
        pattern["match"] for pattern in build_grammar()["patterns"] if "match" in pattern
    )
    for word in KEYWORDS:
        assert word in matched
