"""The single source of truth for lynx's surface syntax.

Change a keyword, a symbol or an operator's precedence here and the lexer,
the parser and the error messages all follow. Nothing else in the codebase
should spell out an operator character.
"""

# How a comment begins. Everything after it on the line is ignored.
COMMENT = "//"

# A multi-line (block / docstring) comment: a line starting with this opens one,
# and a line ending with it closes it. The whole block is ignored.
BLOCK_COMMENT = "///"

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


def _literal_token(value: bool | float | None) -> str:
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
    "loop": "LOOP",
    "stop": "STOP",
    "skip": "SKIP",
    "type": "TYPE",
    "xor": "XOR",
    "len": "LENGTH",
    "first": "FIRST",
    "last": "LAST",
    "in": "IN",
    "not": "NOT",
    "middle": "MIDDLE",
    #types
    "number": "TO_NUMBER",
    "boolean": "TO_BOOLEAN",
    "text": "TO_TEXT",
    #constructors
    "array": "ARRAY",
    "map": "MAP",
    "table": "TABLE",
    "sqrt": "SQRT",
    "root": "ROOT",
    # table SQL-style operations
    "sum": "SUM",
    "avg": "AVG",
    "min": "MIN",
    "max": "MAX",
    "count": "COUNT",
    "distinct": "DISTINCT",
    "select": "SELECT",
    "order": "ORDER",
    "group": "GROUP",
    "where": "WHERE",
    "join": "JOIN",
    **{word: _literal_token(value) for word, value in LITERALS.items()},
}

# Printing a value back to source form: Python value -> its spelling.
SPELLING = {value: word for word, value in LITERALS.items()}

# Symbol -> token type. Matched longest-first, so ">>" beats ">" and
# "//" (comment) beats "/".
SYMBOLS = {
    ">>>": "RETURN",
    ">>": "PRINT",
    ">≈": "GREATER_OR_ALMOST",
    ">~": "GREATER_OR_ALMOST",
    ">=": "GREATER_OR_EQUAL",
    ">": "GREATER",
    "<≈": "LESSER_OR_ALMOST",
    "<~": "LESSER_OR_ALMOST",
    "<=": "LESSER_OR_EQUAL",
    "<": "LESS",
    "<:": "APPEND",
    ">:": "PREPEND",
    "=": "EQUAL",
    "!=": "NOT_EQUAL",
    "≈": "ALMOST",
    "+": "PLUS",
    "-": "MINUS",
    "^": "POWER",
    "*": "STAR",
    "/": "SLASH",
    "__": "RANGE",
    ",": "COMMA",
    ":": "COLON",
    "{": "LBRACE",
    "}": "RBRACE",
    "(": "LPAREN",
    ")": "RPAREN",
    "[": "LBRACK",
    "]": "RBRACK",
    ";": "SEMICOLON",
}

# The two comparison tiers, factored out so `where` (WHERE_OPERATORS below)
# accepts exactly the same operators as these precedence tiers. EQUALITY sits
# one tier looser than IN; ordering one tier tighter.
EQUALITY_LEVEL = {"EQUAL": "equals", "NOT_EQUAL": "not_equal", "ALMOST": "almost"}
ORDERING_LEVEL = {
    "GREATER": "greater", "LESS": "less",
    "GREATER_OR_EQUAL": "greater_or_equal", "LESSER_OR_EQUAL": "lesser_or_equal",
    "GREATER_OR_ALMOST": "greater_or_almost", "LESSER_OR_ALMOST": "lesser_or_almost",
}

# Binary operators grouped by precedence, lowest first. Each maps a token
# type to the Value method that implements it. Adding an operator is one line.
# RANGE is listed at the tightest tier for precedence, but it parses into its
# own RangeExpression node (see parser.py) and is interpreted by build_range —
# it never dispatches to a Value method.
BINARY_LEVELS = [
    {"JOIN": "join"},
    EQUALITY_LEVEL,
    {"IN": "in_"},
    ORDERING_LEVEL,
    {"PLUS": "add", "MINUS": "subtract", "XOR": "xor"},
    {"STAR": "multiply", "SLASH": "divide"},
    {"POWER": "power", "ROOT": "root"},
    {"RANGE": "range"},
]

# Prefix keyword functions: token type -> the zero-argument Value method behind
# it. Written before their operand, like `len 12345`. Adding one is this line
# plus its spelling in KEYWORDS — no parser, node, or interpreter change.
UNARY_METHOD = {
    "TYPE": "type_of",
    "TO_TEXT": "text",
    "TO_NUMBER": "number",
    "TO_BOOLEAN": "boolean",
    "LENGTH": "length",
    "FIRST": "first",
    "LAST": "last",
    "NOT": "not_",
    "MIDDLE": "middle",
    "SQRT": "sqrt",
    "SUM": "sum",
    "AVG": "avg",
    "MIN": "min",
    "MAX": "max",
    "COUNT": "count",
    "DISTINCT": "distinct",
}

# How much of the line a keyword function swallows: its operand is parsed at
# this BINARY_LEVELS tier, so it takes that tier and every tighter one. At 0 it
# takes the whole rest of the line, so `len 1 + 10` means `len (1 + 10)`.
# Raise it to 2 to stop before comparisons, making `len n > 3` mean `(len n) > 3`.
UNARY_OPERAND_LEVEL = 0

# The comparison tokens `where t 'col' <op> value` accepts on its right side:
# exactly the two comparison tiers above.
WHERE_OPERATORS = EQUALITY_LEVEL.keys() | ORDERING_LEVEL.keys()

# Reverse lookups derived from the tables above.
SYMBOL_FOR = {token: symbol for symbol, token in SYMBOLS.items()}
BINARY_METHOD = {token: method for level in BINARY_LEVELS for token, method in level.items()}
