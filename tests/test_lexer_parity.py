"""The Rust lexer must produce byte-identical results to the Python lexer.

Every golden program is tokenized by both implementations and the outcomes are
compared: a run either yields the exact token stream or fails with the exact
`LynxSyntaxError` message. Divergence here means the two implementations have
drifted -- fix the Rust side (or regen grammar.json) rather than weaken this.

The native check needs a built binary, found via LYNX_LEXER_PATH, `PATH`, or
the conventional target directory (`make lexers`). Without one the suite skips.
"""

import os
import shutil
from pathlib import Path

import pytest

from src.core.lexer import tokenize_native, tokenize_pure
from src.errors.errors import LynxSyntaxError

ROOT = Path(__file__).resolve().parents[1]
GRAMMAR_JSON = ROOT / "src" / "core" / "grammar.json"
RELEASE_BIN = ROOT / "rust" / "lexer" / "target" / "release" / "lynx-lexer"

_LX = sorted((ROOT / "tests" / "programs").glob("**/*.lx"))


def _find_binary() -> Path | None:
    env = os.environ.get("LYNX_LEXER_PATH")
    if env:
        return Path(env)
    on_path = shutil.which("lynx-lexer")
    if on_path:
        return Path(on_path)
    if RELEASE_BIN.is_file():
        return RELEASE_BIN
    return None


NATIVE = _find_binary()


def outcome(source: str, fn: object) -> tuple[str, object]:
    try:
        return ("ok", fn(source))  # type: ignore[operator]
    except LynxSyntaxError as err:
        return ("err", str(err))


@pytest.mark.skipif(NATIVE is None, reason="lynx-lexer binary not found -- run `make lexers`")
@pytest.mark.parametrize("program", _LX, ids=lambda p: p.stem)
def test_native_matches_pure(program: Path) -> None:
    source = program.read_text()
    assert NATIVE is not None
    pure = outcome(source, tokenize_pure)
    native = outcome(source, lambda s: tokenize_native(s, NATIVE, GRAMMAR_JSON))
    assert native == pure, program
