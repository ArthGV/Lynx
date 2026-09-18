"""src/core/grammar.json must match grammar.py and lexer.py.

tools/export_grammar.py snapshots the lexer-relevant tables into
src/core/grammar.json, which the optional standalone `lynx-lexer` binary reads.
This test fails when the tables have moved on and the checked-in file hasn't
been regenerated, so the two lexer implementations can't drift apart silently.

    python tools/export_grammar.py   # fixes a staleness-test failure
"""

import json
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

from export_grammar import GRAMMAR_OUT, build_grammar  # noqa: E402

_STALE = "grammar.json is stale -- run `python tools/export_grammar.py`"


def test_grammar_json_is_current():
    assert json.loads(GRAMMAR_OUT.read_text()) == build_grammar(), _STALE
