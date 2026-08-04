"""Turn source text into a flat list of tokens.

Indentation is significant: leading spaces open and close blocks, emitted as
INDENT / DEDENT tokens the parser relies on. Everything about which characters
mean what lives in grammar.py.
"""

import re
from dataclasses import dataclass

from src.grammar import COMMENT, KEYWORDS, LITERALS, SYMBOLS
from src.errors import LynxSyntaxError

NUMBER = re.compile(r"\d+(\.\d+)?")
TEXT = re.compile(r"'([^']*)'")
IDENTIFIER = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]*")

# Longest symbols first so ">>" wins over ">" and "//" over "/".
ORDERED_SYMBOLS = sorted(SYMBOLS, key=len, reverse=True)


@dataclass
class Token:
    type: str
    value: object
    line: int


def tokenize(source):
    tokens = []
    indents = [0]

    for line_no, raw in enumerate(source.splitlines(), start=1):
        if not raw.strip():
            continue

        indent = len(raw) - len(raw.lstrip(" "))
        if indent > indents[-1]:
            indents.append(indent)
            tokens.append(Token("INDENT", None, line_no))
        while indent < indents[-1]:
            indents.pop()
            tokens.append(Token("DEDENT", None, line_no))

        rest = raw.strip()
        while rest:
            if rest.startswith(COMMENT):
                break
            rest = read_token(rest, line_no, tokens)

        tokens.append(Token("NEWLINE", None, line_no))

    while len(indents) > 1:
        indents.pop()
        tokens.append(Token("DEDENT", None, tokens[-1].line if tokens else 1))

    return tokens


def read_token(rest, line_no, tokens):
    """Read one token from the front of `rest` and return what's left."""
    match = TEXT.match(rest)
    if match:
        tokens.append(Token("TEXT", match.group(1), line_no))
        return rest[match.end():].lstrip()

    match = NUMBER.match(rest)
    if match:
        tokens.append(Token("NUMBER", match.group(0), line_no))
        return rest[match.end():].lstrip()

    for symbol in ORDERED_SYMBOLS:
        if rest.startswith(symbol):
            tokens.append(Token(SYMBOLS[symbol], symbol, line_no))
            return rest[len(symbol):].lstrip()

    match = IDENTIFIER.match(rest)
    if match:
        word = match.group(0)
        # Literal keywords carry their Python value; everything else its text.
        value = LITERALS[word] if word in LITERALS else word
        tokens.append(Token(KEYWORDS.get(word, "IDENTIFIER"), value, line_no))
        return rest[match.end():].lstrip()

    raise LynxSyntaxError(f"unexpected character near {rest!r}", line_no)
