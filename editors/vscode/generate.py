"""Generate the VS Code extension's grammar and language config from grammar.py.

Highlighting must not drift from the language, so no keyword, literal or symbol
is spelled out here: they are read from grammar.py — the same tables the lexer
and parser use — and the literal shapes (number, text, identifier) come from
the lexer's own compiled regexes. Add an operator to grammar.py, re-run this
script, and the editor follows.

A token type this script doesn't know how to colour raises instead of being
silently dropped, the same way `Value.__init_subclass__` refuses a type missing
an operation. That way the language can evolve without the editor quietly
falling behind.

Writes syntaxes/lynx.tmLanguage.json (what each piece of text is) and
language-configuration.json (comment toggling, bracket matching, auto-indent).
Both are generated artefacts — edit this script, not them.

    python editors/vscode/generate.py
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.core.grammar import (  # noqa: E402
    BLOCK_COMMENT,
    COMMENT,
    KEYWORDS,
    LITERALS,
    SYMBOLS,
    UNARY_METHOD,
)
from src.core.lexer import IDENTIFIER, NUMBER, TEXT  # noqa: E402

HERE = Path(__file__).parent
GRAMMAR_OUT = HERE / "syntaxes" / "lynx.tmLanguage.json"
CONFIG_OUT = HERE / "language-configuration.json"

# Keyword token types that read as control flow rather than as a function.
# Anything else that isn't a literal or a UNARY_METHOD is a word operator.
CONTROL = {"IF", "ELSE", "LOOP"}

# Control keywords that open an indented block, and the subset of those that
# also close the previous one (so typing `else` dedents to line up with `if`).
BLOCK_OPENERS = {"IF", "ELSE", "LOOP"}
BLOCK_CONTINUATIONS = {"ELSE"}

# Symbol token type -> TextMate scope. Every entry of grammar.SYMBOLS must be
# classified here; a new symbol makes this script fail until it is.
SYMBOL_SCOPE = {
    "PRINT": "keyword.control.lynx",
    "RETURN": "keyword.control.lynx",
    "RANGE": "keyword.operator.range.lynx",
    "EQUAL": "keyword.operator.comparison.lynx",
    "ALMOST": "keyword.operator.comparison.lynx",
    "GREATER": "keyword.operator.comparison.lynx",
    "LESS": "keyword.operator.comparison.lynx",
    "PLUS": "keyword.operator.arithmetic.lynx",
    "MINUS": "keyword.operator.arithmetic.lynx",
    "STAR": "keyword.operator.arithmetic.lynx",
    "SLASH": "keyword.operator.arithmetic.lynx",
    "COLON": "keyword.operator.assignment.lynx",
    "APPEND": "keyword.operator.assignment.lynx",
    "PREPEND": "keyword.operator.assignment.lynx",
    "COMMA": "punctuation.separator.comma.lynx",
    "SEMICOLON": "punctuation.separator.lynx",
    "LBRACE": "punctuation.section.braces.lynx",
    "RBRACE": "punctuation.section.braces.lynx",
}


def word_scope(word: str, token: str) -> str:
    if word in LITERALS:
        return "constant.language.lynx"
    if token in CONTROL:
        return "keyword.control.lynx"
    if token in UNARY_METHOD:
        return "support.function.builtin.lynx"
    return "keyword.operator.word.lynx"


def group(pairs: list[tuple[str, str]]) -> dict[str, list[str]]:
    """(spelling, scope) pairs -> scope -> its spellings."""
    groups: dict[str, list[str]] = {}
    for spelling, scope in pairs:
        groups.setdefault(scope, []).append(spelling)
    return groups


def alternation(spellings: list[str]) -> str:
    # Longest first, like the lexer's ORDERED_SYMBOLS, so `>>` never reads as
    # two `>`.
    return "|".join(re.escape(s) for s in sorted(spellings, key=len, reverse=True))


def word_patterns() -> list[dict]:
    groups = group([(word, word_scope(word, token)) for word, token in KEYWORDS.items()])
    return [
        {"name": scope, "match": rf"\b(?:{alternation(words)})\b"}
        for scope, words in sorted(groups.items())
    ]


def symbol_patterns() -> list[dict]:
    unknown = set(SYMBOLS.values()) - set(SYMBOL_SCOPE)
    if unknown:
        raise SystemExit(
            f"unclassified symbol token(s): {', '.join(sorted(unknown))} — "
            f"add them to SYMBOL_SCOPE in {Path(__file__).name}"
        )
    groups = group([(symbol, SYMBOL_SCOPE[token]) for symbol, token in SYMBOLS.items()])
    # Patterns matching at the same spot are tried in listed order, so the
    # group holding the longest symbol goes first: `>>>` (control) has to be
    # offered before `>` (comparison).
    ordered = sorted(groups.items(), key=lambda item: max(map(len, item[1])), reverse=True)
    return [{"name": scope, "match": alternation(symbols)} for scope, symbols in ordered]


def spellings_for(tokens: set[str]) -> list[str]:
    """The words in KEYWORDS that produce any of these token types."""
    return [word for word, token in KEYWORDS.items() if token in tokens]


def bracket_pairs() -> list[list[str]]:
    """Symbol pairs whose token types read as L<NAME>/R<NAME>, e.g. LBRACE/RBRACE."""
    openers = {token[1:]: symbol for symbol, token in SYMBOLS.items() if token.startswith("L")}
    closers = {token[1:]: symbol for symbol, token in SYMBOLS.items() if token.startswith("R")}
    return [[openers[name], closers[name]] for name in sorted(openers.keys() & closers.keys())]


def quote() -> str:
    """The text delimiter, read off the front of the lexer's TEXT pattern."""
    char = TEXT.pattern[0]
    if char in "\\^$.|?*+()[]{}":
        raise SystemExit(f"can't read the text delimiter from {TEXT.pattern!r}")
    return char


def build_grammar() -> dict:
    line_comment = re.escape(COMMENT)
    block = re.escape(BLOCK_COMMENT)
    return {
        "$schema": "https://raw.githubusercontent.com/martinring/tmlanguage/master/tmlanguage.json",
        "name": "lynx",
        "scopeName": "source.lynx",
        "fileTypes": ["lx"],
        "patterns": [
            {
                # A line starting with `///` opens a block that runs until a
                # line ends with `///`. The opener swallows its whole line, so
                # `/// x ///` opens rather than closes — as the lexer has it.
                "name": "comment.block.lynx",
                "begin": rf"^\s*{block}.*$",
                "end": rf"^.*{block}\s*$",
            },
            {
                "name": "comment.line.double-slash.lynx",
                "match": rf"{line_comment}.*$",
            },
            {
                "name": "string.quoted.single.lynx",
                "match": TEXT.pattern,
            },
            {
                # `name:` at the head of a line names a variable or a function.
                # Reserved words are excluded so `text: 'hi'` still reads as the
                # keyword the lexer sees there.
                "match": rf"^\s*(?!(?:{alternation(list(KEYWORDS))})\b)({IDENTIFIER.pattern})(?=\s*:)",
                "captures": {"1": {"name": "variable.other.definition.lynx"}},
            },
            *word_patterns(),
            *symbol_patterns(),
            {
                # Ahead of numbers, so a name like `total_1` stays one
                # identifier instead of a name plus a stray number.
                "name": "variable.other.lynx",
                "match": IDENTIFIER.pattern,
            },
            {
                # No leading word boundary: in the range `1__10`, the `10` sits
                # right after an underscore.
                "name": "constant.numeric.lynx",
                "match": rf"(?<![A-Za-z0-9.]){NUMBER.pattern}",
            },
        ],
    }


def build_config() -> dict:
    pairs = bracket_pairs()
    text = quote()
    return {
        "comments": {
            "lineComment": COMMENT,
            "blockComment": [BLOCK_COMMENT, BLOCK_COMMENT],
        },
        "brackets": pairs,
        "autoClosingPairs": [
            *({"open": left, "close": right} for left, right in pairs),
            {"open": text, "close": text, "notIn": ["string", "comment"]},
        ],
        "surroundingPairs": [*pairs, [text, text]],
        # Indentation is significant, so the editor has to follow blocks the way
        # the lexer's indent stack does: open one after `if`/`else`, and pull a
        # freshly typed `else` back out to line up with its `if`.
        "indentationRules": {
            "increaseIndentPattern": rf"^\s*(?:{alternation(spellings_for(BLOCK_OPENERS))})\b.*$",
            "decreaseIndentPattern": rf"^\s*(?:{alternation(spellings_for(BLOCK_CONTINUATIONS))})\b.*$",
        },
    }


def write(path: Path, content: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # ensure_ascii off so a symbol like `≈` stays readable in the output.
    path.write_text(json.dumps(content, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {path.relative_to(ROOT)}")


def main() -> None:
    write(GRAMMAR_OUT, build_grammar())
    write(CONFIG_OUT, build_config())


if __name__ == "__main__":
    main()
