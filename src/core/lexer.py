"""Turn source text into a flat list of tokens.

Indentation is significant: leading spaces open and close blocks, emitted as
INDENT / DEDENT tokens the parser relies on. Everything about which characters
mean what lives in grammar.py.
"""

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.core.grammar import BLOCK_COMMENT, COMMENT, KEYWORDS, LITERALS, SYMBOLS
from src.errors.errors import LynxError, LynxSyntaxError

NUMBER = re.compile(r"\d+(\.\d+)?")
TEXT = re.compile(r"'((?:[^'\\]|\\.)*)'")
IDENTIFIER = re.compile(r"[a-zA-Z_](?:[a-zA-Z0-9]|_(?!_))*")

ORDERED_SYMBOLS = sorted(SYMBOLS, key=len, reverse=True)

ESCAPES = {
    "n": "\n",
    "t": "\t",
    "r": "\r",
    "\\": "\\",
    "'": "'",
}

_GRAMMAR_JSON = Path(__file__).resolve().parent / "grammar.json"


def _unescape(raw: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(raw):
        if raw[i] == "\\" and i + 1 < len(raw):
            nxt = raw[i + 1]
            out.append(ESCAPES.get(nxt, raw[i] + nxt))
            i += 2
        else:
            out.append(raw[i])
            i += 1
    return "".join(out)


@dataclass
class Token:
    type: str
    value: Any
    line: int


def tokenize_pure(source: str) -> list[Token]:
    """Parse *source* into a token list using the Python regex-based lexer."""
    tokens: list[Token] = []
    indents = [0]
    in_block_comment = False
    block_start = 1

    for line_no, raw in enumerate(source.splitlines(), start=1):
        if not raw.strip():
            continue

        stripped = raw.strip()
        if in_block_comment:
            if stripped.endswith(BLOCK_COMMENT):
                in_block_comment = False
            continue
        if stripped.startswith(BLOCK_COMMENT):
            block_start = line_no
            in_block_comment = True
            continue

        indent = len(raw) - len(raw.lstrip(" "))
        if indent > indents[-1]:
            indents.append(indent)
            tokens.append(Token("INDENT", None, line_no))
        while indent < indents[-1]:
            indents.pop()
            tokens.append(Token("DEDENT", None, line_no))

        rest = stripped
        while rest:
            if rest.startswith(COMMENT):
                break
            rest = _read_token(rest, line_no, tokens)

        tokens.append(Token("NEWLINE", None, line_no))

    while len(indents) > 1:
        indents.pop()
        tokens.append(Token("DEDENT", None, tokens[-1].line if tokens else 1))

    if in_block_comment:
        raise LynxSyntaxError(
            f"unterminated multiline comment starting on line {block_start}",
            block_start,
        )

    return tokens


def _read_token(rest: str, line_no: int, tokens: list[Token]) -> str:
    """Read one token from the front of *rest* and return what's left."""
    match = TEXT.match(rest)
    if match:
        tokens.append(Token("TEXT", _unescape(match.group(1)), line_no))
        return rest[match.end() :].lstrip()

    match = NUMBER.match(rest)
    if match:
        after = rest[match.end() :]
        if after.startswith("_") and not after.startswith("__"):
            raise LynxSyntaxError(
                f"use '__' for ranges, not '_': {rest[: match.end()]}{after}",
                line_no,
            )
        tokens.append(Token("NUMBER", match.group(0), line_no))
        return after.lstrip()

    for symbol in ORDERED_SYMBOLS:
        if rest.startswith(symbol):
            tokens.append(Token(SYMBOLS[symbol], symbol, line_no))
            return rest[len(symbol) :].lstrip()

    match = IDENTIFIER.match(rest)
    if match:
        word = match.group(0)
        value = LITERALS.get(word, word)
        tokens.append(Token(KEYWORDS.get(word, "IDENTIFIER"), value, line_no))
        return rest[match.end() :].lstrip()

    raise LynxSyntaxError(f"unexpected character near {rest!r}", line_no)


# ---------------------------------------------------------------------------
# Native (Rust) lexer interface
# ---------------------------------------------------------------------------

_NATIVE_SENTINEL: Any = object()
_native: Any = _NATIVE_SENTINEL


def _native_lexer() -> Any:
    """Return a ``tokenize(source)`` callable using the Rust binary, or None."""
    global _native
    if _native is not _NATIVE_SENTINEL:
        return _native

    override = os.environ.get("LYNX_LEXER")
    lexer = None if override == "python" else _probe_native()
    _native = lexer
    return lexer


def _probe_native() -> Any:
    if not _GRAMMAR_JSON.is_file():
        return None
    path_env = os.environ.get("LYNX_LEXER_PATH")
    exe = path_env or shutil.which("lynx-lexer")
    if not exe:
        local = (
            Path(__file__).resolve().parents[2]
            / "rust" / "lexer" / "target" / "release" / "lynx-lexer"
        )
        if local.is_file():
            exe = str(local)
    if not exe:
        return None
    return _NativeSession(exe, _GRAMMAR_JSON).tokenize


class _NativeSession:
    """Keep one `lynx-lexer --serve` process and talk framed JSON over pipes."""

    def __init__(self, executable: str, grammar: Path) -> None:
        self._executable = executable
        self._grammar = grammar
        self._proc: subprocess.Popen[bytes] | None = None

    def _spawn(self) -> None:
        self._proc = subprocess.Popen(
            [self._executable, "--serve", str(self._grammar)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )

    def _exchange(self, source: str) -> bytes:
        proc = self._proc
        if proc is None or proc.poll() is not None:
            self._spawn()
            proc = self._proc
        assert proc is not None
        assert proc.stdin is not None and proc.stdout is not None
        request = json.dumps({"source": source}, ensure_ascii=False).encode() + b"\n"
        proc.stdin.write(request)
        proc.stdin.flush()
        line: bytes = proc.stdout.readline()
        if not line:
            # The worker died mid-request; retry once with a fresh process.
            self._spawn()
            proc = self._proc
            assert proc is not None
            assert proc.stdin is not None and proc.stdout is not None
            proc.stdin.write(request)
            proc.stdin.flush()
            line = proc.stdout.readline()
            if not line:
                raise LynxError("internal lexer error: native lexer exited")
        return line

    def tokenize(self, source: str) -> list[Token]:
        payload = json.loads(self._exchange(source))
        if "error" in payload:
            _raise_native_error(payload["error"])
        return [Token(_type, value, line) for _type, value, line in payload["tokens"]]


def tokenize(source: str) -> list[Token]:
    """Top-level entry: use the Rust binary when available, else Python."""
    native = _native_lexer()
    if native is not None:
        return list(native(source))
    return tokenize_pure(source)


def tokenize_native(source: str, executable: Path, grammar: Path) -> list[Token]:
    """Run the standalone Rust lexer and convert its JSON output."""
    proc = subprocess.run(
        [str(executable), str(grammar)],
        input=source,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    payload = json.loads(proc.stdout)
    if "error" in payload:
        _raise_native_error(payload["error"])
    return [Token(_type, value, line) for _type, value, line in payload["tokens"]]


def _raise_native_error(error: dict[str, Any]) -> None:
    kind = error["kind"]
    line = error["line"]
    fragment = error["fragment"]
    if kind == "number_underscore":
        message = f"use '__' for ranges, not '_': {fragment}"
    elif kind == "unexpected_character":
        message = f"unexpected character near {fragment!r}"
    elif kind == "unterminated_block_comment":
        message = f"unterminated multiline comment starting on line {line}"
    else:
        raise LynxError(f"internal lexer error: {kind}")
    raise LynxSyntaxError(message, line)
