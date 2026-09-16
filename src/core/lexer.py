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

# Longest symbols first so ">>" wins over ">" and "//" over "/".
ORDERED_SYMBOLS = sorted(SYMBOLS, key=len, reverse=True)

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

        rest = stripped
        while rest:
            if rest.startswith(COMMENT):
                break
            rest = read_token(rest, line_no, tokens)

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


def read_token(rest: str, line_no: int, tokens: list[Token]) -> str:
    """Read one token from the front of `rest` and return what's left."""
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
        # Literal keywords carry their Python value; everything else its text.
        value = LITERALS.get(word, word)
        tokens.append(Token(KEYWORDS.get(word, "IDENTIFIER"), value, line_no))
        return rest[match.end() :].lstrip()

    raise LynxSyntaxError(f"unexpected character near {rest!r}", line_no)
