"""The single source of truth for lynx's surface syntax.

Change a keyword, a symbol or an operator's precedence here and the lexer,
the parser and the error messages all follow. Nothing else in the codebase
should spell out an operator character.
"""

# How a comment begins. Everything after it on the line is ignored.
COMMENT = "//"

# Literal keywords: spelling -> the Python value it denotes. This is the ONE
# place these words are spelled — the lexer resolves them to their value and
# printing (SPELLING) reverses it, so renaming a literal here changes it
# everywhere, including program output.
LITERALS = {
    "true": True,
    "false": False,
    "void": None,
    "pi": 3.14,
}


def _literal_token(value):
    if isinstance(value, bool):
        return "BOOLEAN"
    if value is None:
        return "VOID"
    return "NUMBER"


# Keyword spelling -> token type. Literal keywords get their token type from
# the value they denote, so they never need to be listed twice.
KEYWORDS = {
    "if": "IF",
    "else": "ELSE",
    "typeof": "TYPEOF",
    "xor": "XOR",
    "len": "LENGHT",
    # "number": "NUMBER",
    "text": "TO_TEXT",
    # "bool": "BOOLEAN",
    **{word: _literal_token(value) for word, value in LITERALS.items()},
}

# Printing a value back to source form: Python value -> its spelling.
SPELLING = {value: word for word, value in LITERALS.items()}

# Symbol -> token type. Matched longest-first, so ">>" beats ">" and
# "//" (comment) beats "/".
SYMBOLS = {
    ">>": "PRINT",
    "=": "EQUAL",
    "≈": "ALMOST",
    ">": "GREATER",
    "<": "LESS",
    "+": "PLUS",
    "-": "MINUS",
    "*": "STAR",
    "/": "SLASH",
    ",": "COMMA",
    ":": "COLON",
}

# Binary operators grouped by precedence, lowest first. Each maps a token
# type to the Value method that implements it. Adding an operator is one line.
BINARY_LEVELS = [
    {"EQUAL": "equals", "ALMOST": "almost"},
    {"GREATER": "greater", "LESS": "less"},
    {"PLUS": "add", "MINUS": "subtract", "XOR": "xor"},
    {"STAR": "multiply", "SLASH": "divide"},
]

# Reverse lookups derived from the tables above.
SYMBOL_FOR = {token: symbol for symbol, token in SYMBOLS.items()}
BINARY_METHOD = {token: method for level in BINARY_LEVELS for token, method in level.items()}
