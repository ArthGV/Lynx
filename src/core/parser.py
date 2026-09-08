"""Recursive-descent parser: tokens in, AST out.

Binary-operator precedence is driven entirely by grammar.BINARY_LEVELS and
prefix keyword functions by grammar.UNARY_METHOD, so neither a new operator nor
a new keyword function needs new parsing code.
"""

from typing import Any

from src.core.grammar import BINARY_LEVELS, UNARY_METHOD, UNARY_OPERAND_LEVEL
from src.core.lexer import Token
from src.core.nodes import (
    ArrayLiteral,
    Assignment,
    BinaryExpression,
    Boolean,
    Branch,
    Call,
    Function,
    Identifier,
    If,
    Loop,
    MapLiteral,
    Number,
    Print,
    Program,
    RangeExpression,
    Return,
    SetItem,
    Skip,
    Stop,
    Text,
    UnaryExpression,
    Void,
)
from src.errors.errors import LynxInputError, LynxSyntaxError

EOF = "EOF"


class Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.current = 0

    def peek(self) -> Token | None:
        if self.current >= len(self.tokens):
            return None
        return self.tokens[self.current]

    def type(self) -> str:
        token = self.peek()
        return token.type if token else EOF

    def advance(self) -> Token:
        token = self.tokens[self.current]
        self.current += 1
        return token

    def match(self, expected: str) -> Token:
        if self.type() != expected:
            token = self.peek()
            line = token.line if token else None
            raise LynxSyntaxError(f"expected {expected}, got {self.type()}", line)
        return self.advance()

    def skip_newlines(self) -> None:
        while self.type() == "NEWLINE":
            self.advance()

    # -- statements -----------------------------------------------------

    def parse(self) -> Program:
        statements: list[Any] = []
        self.skip_newlines()
        while self.type() != EOF:
            statements.append(self.parse_statement())
            self.skip_newlines()
        return Program(statements)

    def parse_statement(self) -> Any:
        match self.type():
            case "PRINT":
                return self.parse_print()
            case "RETURN":
                return self.parse_return()
            case "IF":
                return self.parse_if()
            case "LOOP":
                return self.parse_loop()
            case "STOP":
                return self.parse_loop_control(Stop)
            case "SKIP":
                return self.parse_loop_control(Skip)
            case "IDENTIFIER":
                return self.parse_name_statement()
        token = self.peek()
        raise LynxSyntaxError(
            f"unexpected {self.type()}", token.line if token else None
        )

    def parse_print(self) -> Print:
        self.match("PRINT")
        return Print(self.parse_expression())

    def parse_return(self) -> Return:
        token = self.match("RETURN")
        return Return(self.parse_expression(), token.line)

    def parse_name_statement(self) -> Any:
        # After a leading identifier we could have an assignment (`x: 5`), a
        # function declaration (`f: a, b` + indented body), a function call
        # (`f a, b`) or an element mutation (`a 0: 5`). A colon means
        # declaration-or-assignment, decided by whether the right-hand side is
        # a parameter list followed by an indented block.
        start = self.current
        line = self.peek().line
        name = self.advance().value
        if self.type() != "COLON":
            if self._starts_expression(self.type()):
                mutation = self.try_parse_mutation(name, line)
                if mutation is not None:
                    return mutation
            return self.parse_call(name, line)
        if self._is_function_declaration():
            return self._parse_function(name)
        self.current = start
        return self.parse_assignment()

    def _is_function_declaration(self) -> bool:
        # At the COLON. True when the right-hand side is IDENTIFIER
        # (, IDENTIFIER)* then an indented block — i.e. a parameter list rather
        # than an assignment expression.
        i = self.current + 1  # skip COLON
        if self._type_at(i) != "IDENTIFIER":
            return False
        i += 1
        while self._type_at(i) == "COMMA":
            i += 1
            if self._type_at(i) != "IDENTIFIER":
                return False
            i += 1
        return (
            self._type_at(i) == "NEWLINE"
            and self._type_at(i + 1) == "INDENT"
        )

    def _type_at(self, i: int) -> str:
        if i < len(self.tokens):
            return self.tokens[i].type
        return EOF

    def _parse_function(self, name: str) -> Function:
        self.match("COLON")
        params = [self.match("IDENTIFIER").value]
        while self.type() == "COMMA":
            self.advance()
            params.append(self.match("IDENTIFIER").value)
        return Function(name, params, self.parse_body())

    def parse_assignment(self) -> Assignment:
        name = self.match("IDENTIFIER").value
        self.match("COLON")
        return Assignment(name, self.parse_assign_rhs())

    def parse_assign_rhs(self) -> Any:
        # The right-hand side of `name:` is one expression unless a top-level
        # comma separates several, in which case it is an array literal.
        # `,` consumed inside a call's args stays that call's args, never here.
        items = [self.parse_expression()]
        while self.type() == "COMMA":
            self.advance()
            items.append(self.parse_expression())
        if len(items) == 1:
            return items[0]
        return ArrayLiteral(items)

    def parse_call(self, name: str, line: int | None) -> Call:
        args = [self.parse_expression()]
        while self.type() == "COMMA":
            self.advance()
            args.append(self.parse_expression())
        return Call(name, args, line)

    def try_parse_mutation(self, name: str, line: int | None) -> SetItem | None:
        # `name <expr>... : value` is an element mutation (`a 0: 5`). The deref
        # path is a run of expressions, comma-grouped or space-chained, both
        # of which are sequential steps. If the run is followed by a colon we
        # have a mutation; otherwise rewind and let the call machinery handle it.
        save = self.current
        steps: list[Any] = []
        try:
            steps.append(self.parse_expression())
            while True:
                if self.type() == "COMMA":
                    self.advance()
                    steps.append(self.parse_expression())
                elif self._starts_expression(self.type()):
                    steps.append(self.parse_expression())
                else:
                    break
        except LynxSyntaxError:
            self.current = save
            return None
        if self.type() != "COLON":
            self.current = save
            return None
        self.match("COLON")
        return SetItem(name, steps, self.parse_assign_rhs(), line)

    def parse_chain(self, operand: Any) -> Any:
        # After `operand`, a run of space-separated expressions means chained
        # calls: `a 1 0` -> Call(Call(a, [1]), [0]). `,` inside one run stays
        # that run's args, so `a 1, 0` is a single two-arg call.
        while self._starts_expression(self.type()):
            args = [self.parse_expression()]
            while self.type() == "COMMA":
                self.advance()
                args.append(self.parse_expression())
            operand = Call(operand, args, self.peek_line())
        return operand

    def peek_line(self) -> int | None:
        token = self.peek()
        return token.line if token else None

    def parse_if(self) -> If:
        self.match("IF")
        branches = [Branch(self.parse_expression(), self.parse_body())]
        else_body = None
        while self.type() == "ELSE":
            self.advance()
            if self.type() == "NEWLINE":  # bare else
                else_body = self.parse_body()
                break
            branches.append(Branch(self.parse_expression(), self.parse_body()))
        return If(branches, else_body)

    def parse_loop(self) -> Loop:
        token = self.match("LOOP")
        targets = self._loop_targets()
        if targets is not None:
            # `loop <name>[, <name>]: <iterable>` — a for-loop. One name binds
            # the element; two bind index + element like enumerate.
            if len(targets) > 2:
                raise LynxInputError(
                    f"loop takes 1 or 2 loop variables, got {len(targets)}", token.line
                )
            iterable = self.parse_assign_rhs()
            body = self.parse_body()
            return Loop(None, body, targets, iterable)
        condition = self.parse_expression()
        body = self.parse_body()
        return Loop(condition, body)

    def _loop_targets(self) -> list[str] | None:
        # Look ahead for a for-header: an IDENTIFIER [, IDENTIFIER]* run that
        # ends in COLON. Expressions can't contain a top-level `,` or `:` in a
        # loop header, so this is unambiguous with the while form. Consumes the
        # header on a match, returns None (tokens untouched) otherwise.
        i = self.current
        if self._type_at(i) != "IDENTIFIER":
            return None
        i += 1
        while self._type_at(i) == "COMMA":
            i += 1
            if self._type_at(i) != "IDENTIFIER":
                return None
            i += 1
        if self._type_at(i) != "COLON":
            return None
        targets = [self.advance().value]
        while self.type() == "COMMA":
            self.advance()
            targets.append(self.match("IDENTIFIER").value)
        self.match("COLON")
        return targets

    def parse_loop_control(self, node_type) -> Any:
        # `stop`/`skip` may take an optional condition: `stop x > 3` desugars
        # to `if x > 3: stop`. With no trailing expression the control is
        # unconditional.
        token = self.advance()
        condition = None
        if self._starts_expression(self.type()):
            condition = self.parse_expression()
        return node_type(condition, token.line)

    def parse_body(self) -> list[Any]:
        self.match("NEWLINE")
        self.match("INDENT")
        statements: list[Any] = []
        self.skip_newlines()
        while self.type() not in ("DEDENT", EOF):
            statements.append(self.parse_statement())
            self.skip_newlines()
        self.match("DEDENT")
        return statements

    # -- expressions ----------------------------------------------------

    def parse_expression(self) -> Any:
        return self.parse_binary(0)

    def parse_binary(self, level: int) -> Any:
        if level >= len(BINARY_LEVELS):
            return self.parse_primary()
        operators = BINARY_LEVELS[level]
        if self.type() == "RANGE" and "RANGE" in operators:
            # Leading `__N`: the start is omitted, so it runs up from 0.
            token = self.advance()
            return RangeExpression(
                None,
                self.parse_binary(level + 1) if self._can_start_bound(self.type()) else None,
                token.line,
            )
        left = self.parse_binary(level + 1)
        while self.type() in operators:
            token = self.advance()
            if token.type == "RANGE" and "RANGE" in operators:
                # A trailing `N__` has no end; it runs down to 0.
                right = self.parse_binary(level + 1) if self._can_start_bound(self.type()) else None
                left = RangeExpression(left, right, token.line)
            else:
                right = self.parse_binary(level + 1)
                left = BinaryExpression(left, token.type, right, token.line)
        return left

    def parse_primary(self) -> Any:
        token = self.peek()
        match self.type():
            case operator if operator in UNARY_METHOD:
                self.advance()
                return UnaryExpression(
                    operator, self.parse_binary(UNARY_OPERAND_LEVEL), token.line
                )
            case "NUMBER":
                return Number(self.advance().value)
            case "MINUS":
                return self.parse_negative()
            case "TEXT":
                return Text(self.advance().value)
            case "BOOLEAN":
                return Boolean(self.advance().value)
            case "VOID":
                self.advance()
                return Void()
            case "LBRACE":
                return self.parse_map_literal()
            case "IDENTIFIER":
                name = self.advance().value
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

    def _starts_expression(self, token_type: str) -> bool:
        if token_type in ("NUMBER", "TEXT", "BOOLEAN", "VOID", "IDENTIFIER", "LBRACE", "RANGE"):
            return True
        return token_type in UNARY_METHOD

    def _can_start_bound(self, token_type: str) -> bool:
        return token_type == "MINUS" or self._starts_expression(token_type)