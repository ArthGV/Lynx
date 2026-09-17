"""Turn source text into a flat list of tokens.

Indentation is significant: leading spaces open and close blocks, emitted as
INDENT / DEDENT tokens the parser relies on. Everything about which characters
mean what lives in grammar.py.
"""

import re
from dataclasses import dataclass
from typing import Any

from src.core.grammar import BLOCK_COMMENT, COMMENT, KEYWORDS, LITERALS, SYMBOLS
from src.errors.errors import LynxSyntaxError

NUMBER = re.compile(r"\d+(\.\d+)?")
# A backslash escapes the next character, so an escaped quote (`\'`) doesn't
# end the literal and an escaped backslash (`\\`) stays one backslash.
TEXT = re.compile(r"'((?:[^'\\]|\\.)*)'")
# An identifier stops before `__`, which is reserved for ranges — so `l__n`
# lexes as `l`, `__`, `n`, while `a_b` and trailing underscores stay a name.
IDENTIFIER = re.compile(r"[a-zA-Z_](?:[a-zA-Z0-9]|_(?!_))*")

# Longest symbols first so ">>" wins over ">" and "//" over "/". The cursor
# lexer splits this into a first-char map so a symbol costs one dict probe
# instead of a scan past every single-character symbol.
ORDERED_SYMBOLS = sorted(SYMBOLS, key=len, reverse=True)

# Single-character symbols: char -> token type, hit directly per character.
_SINGLE_SYMBOLS: dict[str, str] = {symbol: token for symbol, token in SYMBOLS.items() if len(symbol) == 1}
# Multi-character symbols: first char -> candidates, longest first, so `>>>`
# wins over the `>>` it starts with. Only consulted for a first char that has
# them.
_MULTI_SYMBOLS: dict[str, list[tuple[str, str]]] = {}
for _symbol, _token in SYMBOLS.items():
    if len(_symbol) > 1:
        _MULTI_SYMBOLS.setdefault(_symbol[0], []).append((_symbol, _token))
for _candidates in _MULTI_SYMBOLS.values():
    _candidates.sort(key=lambda pair: len(pair[0]), reverse=True)

# Escapes in text literals. An unknown sequence is kept literally, so `'C:\q'`
# stays `C:\q` and `'a\b'` is `\b`. Deliberately no `\"`: the language only
# uses single quotes.
ESCAPES = {
    "n": "\n",
    "t": "\t",
    "r": "\r",
    "\\": "\\",
    "'": "'",
}


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


def tokenize(source: str) -> list[Token]:
    tokens: list[Token] = []
    indents = [0]
    in_block_comment = False
    block_start = 1

    for line_no, raw in enumerate(source.splitlines(), start=1):
        if not raw.strip():
            continue

        stripped = raw.strip()
        if in_block_comment:
            # A line ending with `///` closes the block; everything else is
            # comment content. No tokens are emitted, so a block comment never
            # disturbs the indent stack or the statement boundaries around it.
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

        text = stripped
        pos = 0
        while pos < len(text):
            if text.startswith(COMMENT, pos):
                break
            pos = read_token(text, pos, line_no, tokens)
            while pos < len(text) and text[pos] == " ":
                pos += 1

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


def read_token(text: str, pos: int, line_no: int, tokens: list[Token]) -> int:
    """Read one token starting at `text[pos]`; return the index just past it.

    Matches are anchored with `re.match(..., pos)` so nothing past the token
    is ever sliced, and after a token the caller only skips spaces — the
    cursor never re-copies the rest of the line like the old offset+slice walk.
    """
    match = TEXT.match(text, pos)
    if match:
        tokens.append(Token("TEXT", _unescape(match.group(1)), line_no))
        return match.end()

    match = NUMBER.match(text, pos)
    if match:
        end = match.end()
        if end < len(text) and text[end] == "_" and text[end : end + 2] != "__":
            raise LynxSyntaxError(
                f"use '__' for ranges, not '_': {text[pos:]}",
                line_no,
            )
        tokens.append(Token("NUMBER", match.group(0), line_no))
        return end

    char = text[pos]
    candidates = _MULTI_SYMBOLS.get(char)
    if candidates is not None:
        for symbol, kind in candidates:
            if text.startswith(symbol, pos):
                tokens.append(Token(kind, symbol, line_no))
                return pos + len(symbol)
    token = _SINGLE_SYMBOLS.get(char)
    if token is not None:
        tokens.append(Token(token, char, line_no))
        return pos + 1

    match = IDENTIFIER.match(text, pos)
    if match:
        word = match.group(0)
        # Literal keywords carry their Python value; everything else its text.
        value = LITERALS.get(word, word)
        tokens.append(Token(KEYWORDS.get(word, "IDENTIFIER"), value, line_no))
        return match.end()

    raise LynxSyntaxError(f"unexpected character near {text[pos:]!r}", line_no)
