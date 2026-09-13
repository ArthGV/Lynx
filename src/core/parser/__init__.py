"""Recursive-descent parser: tokens in, AST out.

The `Parser` class is composed from three pieces so the grammar stays readable
as it grows: token navigation and the public `parse()` entry point live in
`_base.py`, statement rules in `statements.py`, expression rules in
`expressions.py`.
"""

from src.core.parser._base import Parser as _Parser
from src.core.parser.expressions import ExpressionMixin
from src.core.parser.statements import StatementMixin


class Parser(StatementMixin, ExpressionMixin, _Parser):
    """Composed parser: token utilities + statement grammar + expression grammar."""