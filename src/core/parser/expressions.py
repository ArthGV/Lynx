"""Expression grammar: precedence climbing over grammar.BINARY_LEVELS, the
primary forms, collection literals, table queries, and the chained-call
machinery.

Like `statements.py`, this is an `ExpressionMixin` on the base `Parser`: the
methods here are composed with the token utilities and statement rules in
`__init__.py`.
"""

from typing import Any

from src.core.grammar import (
    BINARY_LEVELS,
    UNARY_METHOD,
    UNARY_OPERAND_LEVEL,
    WHERE_OPERATORS,
)
from src.core.nodes import (
    ArrayLiteral,
    BinaryExpression,
    Boolean,
    Call,
    Identifier,
    MapLiteral,
    Number,
    RangeExpression,
    TableLiteral,
    TableQuery,
    Text,
    UnaryExpression,
    Void,
)
from src.core.parser._base import TABLE_QUERY, Parser
from src.errors.errors import LynxSyntaxError


class ExpressionMixin(Parser):
    def parse_expression(self, allow_chain: bool = True) -> Any:
        return self.parse_binary(0, allow_chain)

    def parse_binary(self, level: int, allow_chain: bool = True) -> Any:
        if level >= len(BINARY_LEVELS):
            return self.parse_primary(allow_chain)
        operators = BINARY_LEVELS[level]
        if self.type() == "RANGE" and "RANGE" in operators:
            # Leading `__N`: the start is omitted, so it runs up from 0.
            token = self.advance()
            return RangeExpression(
                None,
                self.parse_binary(level + 1, allow_chain) if self._can_start_bound(self.type()) else None,
                token.line,
            )
        left = self.parse_binary(level + 1, allow_chain)
        while self.type() in operators:
            token = self.advance()
            if token.type == "RANGE" and "RANGE" in operators:
                # A trailing `N__` has no end; it runs down to 0.
                right = self.parse_binary(level + 1, allow_chain) if self._can_start_bound(self.type()) else None
                left = RangeExpression(left, right, token.line)
            else:
                right = self.parse_binary(level + 1, allow_chain)
                left = BinaryExpression(left, token.type, right, token.line)
        return left

    def parse_primary(self, allow_chain: bool = True) -> Any:
        token = self.peek()
        match self.type():
            case operator if operator in UNARY_METHOD:
                self.advance()
                first = self.parse_binary(UNARY_OPERAND_LEVEL, allow_chain)
                if self.type() == "COMMA":
                    items = [first]
                    while self.type() == "COMMA":
                        self.advance()
                        items.append(
                            self.parse_binary(UNARY_OPERAND_LEVEL, allow_chain)
                        )
                    first = ArrayLiteral(items)
                return UnaryExpression(operator, first, token.line)
            case "NUMBER":
                return Number(self.advance().value)
            case "MINUS":
                return self.parse_negative()
            case "TEXT":
                text = Text(self.advance().value)
                if allow_chain and self._starts_expression(self.type()):
                    return self.parse_chain(text)
                return text
            case "BOOLEAN":
                return Boolean(self.advance().value)
            case "VOID":
                self.advance()
                return Void()
            case "ARRAY":
                # Zero-argument constructor: `a: array` is an empty array.
                self.advance()
                return ArrayLiteral([], token.line)
            case "MAP":
                # Zero-argument constructor: `m: map` is an empty map.
                self.advance()
                return MapLiteral([], token.line)
            case "TABLE":
                # Zero-argument constructor: `t: table` is an empty table.
                self.advance()
                return TableLiteral([], token.line)
            case kind if kind in TABLE_QUERY:
                token = self.advance()
                return self.parse_table_query(kind, token.line)
            case "LBRACE":
                return self.parse_map_literal()
            case "LBRACK":
                return self.parse_table_literal()
            case "LPAREN":
                return self.parse_parenthesized(allow_chain)
            case "IDENTIFIER":
                name = self.advance().value
                # Directly after `__` the RANGE is the operator: `a__7`, `a__b`
                # and `a__` are ranges over the name, not calls of it.
                if self.type() == "RANGE":
                    return Identifier(name, token.line)
                if self.type() in ("APPEND", "PREPEND"):
                    return self.parse_append(name, token.line)
                if self._starts_expression(self.type()):
                    return self.parse_chain(self.parse_call(name, token.line))
                return Identifier(name, token.line)
        raise LynxSyntaxError(
            f"unexpected {self.type()}", token.line if token else None
        )

    def parse_negative(self) -> Number:
        token = self.advance()
        if self.type() != "NUMBER":
            raise LynxSyntaxError(
                f"expected NUMBER after '-', got {self.type()}", token.line
            )
        return Number(-float(self.advance().value))

    def parse_parenthesized(self, allow_chain: bool) -> Any:
        """A `( … )` group is a primary: it overrides precedence at its spot,
        and a comma-run inside it is an array literal, so `(1, 2)` is an array
        and `(1 + 2) * 3` binds inside the parens. Like any value, a group may
        be chained — `(f x) 0`, `(m 'k') 0`."""
        opening = self.match("LPAREN")
        items = [self.parse_expression()]
        while self.type() == "COMMA":
            self.advance()
            items.append(self.parse_expression())
        self.match("RPAREN")
        node: Any = items[0] if len(items) == 1 else ArrayLiteral(items, opening.line)
        if allow_chain and self._starts_expression(self.type()):
            return self.parse_chain(node)
        return node

    def parse_map_literal(self) -> MapLiteral:
        opening = self.match("LBRACE")
        pairs: list[Any] = []
        if self.type() == "RBRACE":
            self.advance()
            return MapLiteral(pairs, opening.line)
        while True:
            key = self.parse_expression()
            self.match("COLON")
            items = [self.parse_expression()]
            while self.type() == "COMMA":
                self.advance()
                items.append(self.parse_expression())
            value: Any = items[0] if len(items) == 1 else ArrayLiteral(items)
            pairs.append((key, value))
            if self.type() == "SEMICOLON":
                self.advance()
                continue
            self.match("RBRACE")
            return MapLiteral(pairs, opening.line)

    def parse_table_literal(self) -> TableLiteral:
        # `[ 'id': 1, 2, 3; 'price': 10, 20 ]` — `:` separates a column name
        # from its values, `;` separates columns. A column with no values is
        # allowed: `['id': ; 'price': 1, 2]` and bare `['id'; 'price': 1, 2]`
        # both build an empty `id` column. Names can't be empty, so a stray
        # `:` or `;` right after `[` is a syntax error before parsing starts.
        opening = self.match("LBRACK")
        columns: list[Any] = []
        if self.type() == "RBRACK":
            self.advance()
            return TableLiteral(columns, opening.line)
        while True:
            token = self.peek()
            if self.type() in ("COLON", "SEMICOLON"):
                raise LynxSyntaxError("table column needs a name", token.line)
            name = self.parse_expression()
            values: list[Any] = []
            if self.type() == "COLON":
                self.advance()
                if self._starts_expression(self.type()):
                    values.append(self.parse_expression())
                    while self.type() == "COMMA":
                        self.advance()
                        values.append(self.parse_expression())
            columns.append((name, values))
            if self.type() == "SEMICOLON":
                self.advance()
                continue
            self.match("RBRACK")
            return TableLiteral(columns, opening.line)

    def parse_table_query(self, kind: str, line: int | None) -> TableQuery:
        # `select`/`order`/`group` take the whole rest of the line as their
        # operand (`select t 'a', 'b'`, `order t 'price'`). `where` is split in
        # two instead: the table and its column on the left, then one
        # comparison, so the operator binds between the two rather than being
        # swallowed into the column step.
        if kind != "WHERE":
            return TableQuery(kind, self.parse_binary(0), line)
        name_token = self.match("IDENTIFIER")
        left: Any = Identifier(name_token.value, name_token.line)
        left = self.parse_access_steps(left)
        if self.type() not in WHERE_OPERATORS:
            return TableQuery(kind, left, line)
        operator = self.advance()
        right = self.parse_binary(0)
        return TableQuery(kind, BinaryExpression(left, operator.type, right, line), line)

    def parse_access_steps(self, operand: Any) -> Any:
        # Access steps like parse_chain, except each step is a single primary —
        # a text column or a number — so a comparison operator that follows the
        # chain is never swallowed into one of its steps.
        while self._starts_expression(self.type()):
            args = [self.parse_primary(False)]
            while self.type() == "COMMA":
                self.advance()
                args.append(self.parse_primary(False))
            operand = Call(operand, args, self.peek_line())
        return operand

    def parse_chain(self, operand: Any) -> Any:
        # After `operand`, a run of space-separated expressions means chained
        # calls: `a 1 0` -> Call(Call(a, [1]), [0]). `,` inside one run stays
        # that run's args, so `a 1, 0` is a single two-arg call. Steps are
        # leaves (allow_chain False) so a text key followed by an index keeps
        # the chained-call shape: `t 'k' 0` is t['k'][0], not t['k'[0]].
        while self._starts_expression(self.type()):
            args = [self.parse_expression(False)]
            while self.type() == "COMMA":
                self.advance()
                args.append(self.parse_expression(False))
            operand = Call(operand, args, self.peek_line())
        return operand