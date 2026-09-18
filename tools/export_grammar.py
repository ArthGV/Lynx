"""Export the lexer-relevant grammar tables to src/core/grammar.json.

grammar.py (and the ESCAPES / patterns in lexer.py) stays the single source of
truth; this script snapshots the subset the optional standalone `lynx-lexer`
binary needs into a JSON file. tests/test_grammar_export.py fails when the
checked-in file has drifted, so the Python and Rust lexers can't silently
diverge -- mirroring editors/vscode/generate.py.

    python tools/export_grammar.py   # fixes a staleness-test failure
"""

import json
from pathlib import Path

from src.core.grammar import BLOCK_COMMENT, COMMENT, KEYWORDS, LITERALS, SYMBOLS
from src.core.lexer import ESCAPES, IDENTIFIER, NUMBER, TEXT

GRAMMAR_OUT = Path(__file__).resolve().parents[1] / "src" / "core" / "grammar.json"


def build_grammar() -> dict:
    return {
        "symbols": SYMBOLS,
        "keywords": KEYWORDS,
        "literals": LITERALS,
        "escapes": ESCAPES,
        "line_comment": COMMENT,
        "block_comment": BLOCK_COMMENT,
        "patterns": {
            "number": NUMBER.pattern,
            "text": TEXT.pattern,
            "identifier": IDENTIFIER.pattern,
        },
    }


def main() -> None:
    GRAMMAR_OUT.write_text(json.dumps(build_grammar(), indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()