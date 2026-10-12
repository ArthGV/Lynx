"""Statement grammar: the token-type dispatch, each statement rule, and the
lookahead that tells assignments from function declarations and while-loops
from for-loops.

Everything here is a `StatementMixin` on the base `Parser`, so statement rules
may call expression rules (`parse_expression`, `parse_assign_rhs`, ...) and the
token utilities (`match`, `_starts_expression`, ...) that the composed class in
`__init__.py` brings together.
"""

from typing import Any

from src.core.nodes import (
    Append,
    ArrayLiteral,
    Assignment,
    Branch,
    Call,
    Delete,
    EdgeCreate,
    EdgeStep,
    Error,
    Function,
    GraphLiteral,
    GraphSegment,
    If,
    Loop,
    MultiAssignment,
    Print,
    Return,
    SetItem,
    Skip,
    Stop,
    Test,
    Try,
    Write,
)
from src.core.parser._base import EOF, Parser
from src.errors.errors import LynxInputError, LynxSyntaxError


class StatementMixin(Parser):
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
            case "WRITE":
                return self.parse_write()
            case "DELETE":
                return self.parse_delete()
            case "TEST":
                return self.parse_test()
            case "ERROR":
                return self.parse_error()
            case "TRY":
                return self.parse_try()
            case "IDENTIFIER":
                return self.parse_name_statement()
        token = self.peek()
        raise LynxSyntaxError(f"unexpected {self.type()}", token.line if token else None)

    def parse_write(self) -> Write:
        token = self.match("WRITE")
        value = self.parse_expression()
        self.match("COMMA")
        path = self.parse_expression()
        return Write(value, path, token.line)

    def parse_test(self) -> Test:
        token = self.match("TEST")
        condition = self.parse_expression()
        message = None
        if self.type() == "COMMA":
            self.advance()
            if self._starts_expression(self.type()):
                message = self.parse_expression()
        return Test(condition, message, token.line)

    def parse_error(self) -> Error:
        token = self.match("ERROR")
        message = None
        if self._starts_expression(self.type()):
            message = self.parse_expression()
        return Error(message, token.line)

    def parse_try(self) -> Try:
        token = self.match("TRY")
        try_body = self.parse_body()
        catch_body = None
        catch_var = None
        else_body = None

        if self.type() == "CATCH":
            self.match("CATCH")
            if self.type() == "IDENTIFIER":
                catch_var = self.match("IDENTIFIER").value
            catch_body = self.parse_body()

        if self.type() == "ELSE":
            if catch_body is None:
                raise LynxSyntaxError("else block requires a catch block", self.peek().line)
            self.match("ELSE")
            else_body = self.parse_body()

        return Try(try_body, catch_body, catch_var, else_body, token.line)

    def parse_print(self) -> Print:
        self.match("PRINT")
        return Print(self.parse_assign_rhs())

    def parse_return(self) -> Return:
        token = self.match("RETURN")
        # Comma-separated right-hand side, so `>>> a, b` returns an array.
        return Return(self.parse_assign_rhs(), token.line)

    def parse_name_statement(self) -> Any:
        # After a leading identifier we could have an assignment (`x: 5`), a
        # function declaration (`f: a, b` + indented body), a function call
        # (`f a, b`) or an element mutation (`a 0: 5`). A colon means
        # declaration-or-assignment, decided by whether the right-hand side is
        # a parameter list followed by an indented block.
        # Also handle multi-assignment: `a, b, c: value`
        start = self.current
        line = self.peek().line
        name = self.advance().value
        if self.type() == "RANGE":
            # `a__2` as a bare statement is a range expression, not a call.
            self.current = start
            return self.parse_expression()
        if self.type() in ("APPEND", "PREPEND"):
            return self.parse_append(name, line)
        # Check for multi-assignment: a, b, c: value
        if self.type() == "COMMA" and self._is_multi_assignment_at(start):
            self.current = start
            return self._parse_multi_assignment()
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

    def _is_multi_assignment_at(self, start_pos: int) -> bool:
        # Check if we have: IDENTIFIER (, IDENTIFIER)* COLON
        i = start_pos + 1  # skip first IDENTIFIER
        if self._type_at(i) != "COMMA":
            return False
        i += 1
        while True:
            if self._type_at(i) != "IDENTIFIER":
                return False
            i += 1
            if self._type_at(i) == "COMMA":
                i += 1
                continue
            break
        return self._type_at(i) == "COLON"

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
        return self._type_at(i) == "NEWLINE" and self._type_at(i + 1) == "INDENT"

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
        # A function body starts outside any loop: `stop`/`skip` can't reach
        # a loop in the caller.
        outer_depth, self.loop_depth = self.loop_depth, 0
        try:
            body = self.parse_body()
        finally:
            self.loop_depth = outer_depth
        return Function(name, params, body)

    def parse_assignment(self) -> Any:
        # Check if this is a multi-assignment: a, b, c: value
        if self._is_multi_assignment():
            return self._parse_multi_assignment()
        name = self.match("IDENTIFIER").value
        self.match("COLON")
        return Assignment(name, self.parse_assign_rhs())

    def _is_multi_assignment(self) -> bool:
        # Look ahead for: IDENTIFIER (, IDENTIFIER)+ COLON (at least one comma)
        i = self.current
        if self._type_at(i) != "IDENTIFIER":
            return False
        i += 1
        has_comma = False
        while self._type_at(i) == "COMMA":
            has_comma = True
            i += 1
            if self._type_at(i) != "IDENTIFIER":
                return False
            i += 1
        return has_comma and self._type_at(i) == "COLON"

    def _parse_multi_assignment(self) -> MultiAssignment:
        names = [self.match("IDENTIFIER").value]
        while self.type() == "COMMA":
            self.advance()
            names.append(self.match("IDENTIFIER").value)
        self.match("COLON")
        value = self.parse_assign_rhs()
        return MultiAssignment(names, value, self.peek_line())

    def parse_assign_rhs(self) -> Any:
        # The right-hand side of `name:` is one expression unless a top-level
        # comma separates several, in which case it is an array literal. A
        # trailing comma closes a one-element array: `name: 2,` is `[2]`.
        # `,` consumed inside a call's args stays that call's args, never here.
        # A leading node id followed by `->` (or a `;`-separated node run) is a
        # graph literal rather than an expression.
        if self._looks_like_graph_literal():
            return self.parse_graph_literal()
        items = [self.parse_expression()]
        trailing = False
        while self.type() == "COMMA":
            self.advance()
            if not self._starts_comma_item(self.type()):
                trailing = True
                break
            items.append(self.parse_expression())
        if len(items) == 1 and not trailing:
            return items[0]
        return ArrayLiteral(items)

    def _looks_like_graph_literal(self) -> bool:
        # At the head of an assignment RHS: an IDENTIFIER that is a node id,
        # then either an ARROW (`a -> b`), a SEMICOLON (a bare leading isolated
        # node), or a parenthesized value followed by one of those
        # (`a('x') -> b`). A read like `g 'a' -> 'b'` doesn't match because its
        # step is a bare text/number, not parens — node values in literals are
        # always parenthesized (and could also be an array like `(1, 2)`).
        if self.type() != "IDENTIFIER":
            return False
        i = self.current + 1
        if i >= len(self.tokens):
            return False
        nxt = self.tokens[i].type
        if nxt in ("ARROW", "SEMICOLON"):
            return True
        if nxt != "LPAREN":
            return False
        depth = 0
        while i < len(self.tokens):
            token_type = self.tokens[i].type
            if token_type == "LPAREN":
                depth += 1
            elif token_type == "RPAREN":
                depth -= 1
                if depth == 0:
                    i += 1
                    return i < len(self.tokens) and self.tokens[i].type in ("ARROW", "SEMICOLON")
            i += 1
        return False

    def parse_graph_literal(self) -> GraphLiteral:
        # `a('Ida') -> b, c : 'loves'; d -> e` — `;` separates statements, each
        # building a source node, a target comma-run and (once) a shared label.
        line = self.peek_line()
        segments = [self.parse_graph_segment()]
        while self.type() == "SEMICOLON":
            self.advance()
            segments.append(self.parse_graph_segment())
        return GraphLiteral(segments, line)

    def parse_graph_segment(self) -> GraphSegment:
        line = self.peek_line()
        source = self.match("IDENTIFIER").value
        value: Any | None = None
        if self.type() == "LPAREN":
            value = self.parse_parenthesized(False)
        targets: list[tuple[str, Any | None]] = []
        if self.type() == "ARROW":
            self.advance()
            targets.append(self._parse_graph_target())
            while self.type() == "COMMA":
                self.advance()
                targets.append(self._parse_graph_target())
        label: Any | None = None
        if self.type() == "COLON":
            self.advance()
            label = self.parse_expression()
        return GraphSegment(source, value, targets, label, line)

    def _parse_graph_target(self) -> tuple[str, Any | None]:
        target = self.match("IDENTIFIER").value
        value: Any | None = None
        if self.type() == "LPAREN":
            value = self.parse_parenthesized(False)
        return (target, value)

    def parse_call(self, name: str, line: int | None) -> Call:
        args = [self.parse_expression(False)]
        while self.type() == "COMMA":
            self.advance()
            args.append(self.parse_expression(False))
        if self.type() == "ARROW":
            # An edge access — `g 'a' -> 'b'` — keeps both endpoint ids in the
            # same run's args so the interpreter sees the source and target
            # together.
            self.advance()
            args.append(EdgeStep(self.parse_expression(False)))
        return Call(name, args, line)

    def parse_append(self, name: str, line: int | None) -> Append:
        token = self.advance()
        return Append(name, self.parse_assign_rhs(), token.type == "PREPEND", line)

    def parse_delete(self) -> Delete:
        # `del <name>` deletes the variable; `del <name> <step>...` descends
        # through a deref path and deletes the last step, mirroring the step
        # run of try_parse_mutation (comma-grouped or space-chained).
        token = self.match("DELETE")
        name = self.match("IDENTIFIER").value
        steps: list[Any] = []
        if self._starts_expression(self.type()):
            steps.append(self.parse_expression(False))
            while True:
                if self.type() == "COMMA":
                    self.advance()
                    steps.append(self.parse_expression(False))
                elif self.type() == "ARROW":
                    self.advance()
                    steps.append(EdgeStep(self.parse_expression(False)))
                elif self._starts_expression(self.type()):
                    steps.append(self.parse_expression(False))
                else:
                    break
        return Delete(name, steps, token.line)

    def try_parse_mutation(self, name: str, line: int | None) -> SetItem | None:
        # `name <expr>... : value` is an element mutation (`a 0: 5`). The deref
        # path is a run of expressions, comma-grouped or space-chained, both
        # of which are sequential steps. If the run is followed by a colon we
        # have a mutation; otherwise rewind and let the call machinery handle it.
        save = self.current
        steps: list[Any] = []
        try:
            steps.append(self.parse_expression(False))
            while True:
                if self.type() == "COMMA":
                    self.advance()
                    steps.append(self.parse_expression(False))
                elif self.type() == "ARROW":
                    self.advance()
                    steps.append(EdgeStep(self.parse_expression(False)))
                elif self._starts_expression(self.type()):
                    steps.append(self.parse_expression(False))
                else:
                    break
        except LynxSyntaxError:
            self.current = save
            return None
        if self.type() != "COLON":
            self.current = save
            return None
        self.match("COLON")
        return SetItem(name, steps, self._parse_mutation_value(), line)

    def _parse_mutation_value(self) -> Any:
        # The right-hand side of a mutation. One expression, or a top-level
        # comma-run grouped as an array (`a 0: 5, 6` — a trailing comma closes
        # a one-element array, `a 0: 5,`). Each value parses
        # through `parse_cell_value`, so a parenthesized run at the head is
        # kept as one element (`a 0: (4, 5)` sets a single array) — the array
        # still holds the whole run, but for a table column `t 'c': (4, 5)`
        # writes one cell instead of spreading the array.
        if self.type() == "ARROW":
            # `g 'x': -> 'z'` creates an edge, optionally seeding the target
            # node and the label together: `g 'x': -> 'z'('loves')`.
            token = self.advance()
            target = self.parse_expression(False)
            value: Any | None = None
            if self.type() == "LPAREN":
                value = self.parse_parenthesized(False)
            return EdgeCreate(target, value, token.line)
        first = self.parse_cell_value()
        if self.type() != "COMMA":
            return first
        items = [first]
        while self.type() == "COMMA":
            self.advance()
            if not self._starts_comma_item(self.type()):
                break
            items.append(self.parse_cell_value())
        return ArrayLiteral(items)

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
            # Count simple targets (non-unpack groups)
            simple_count = sum(1 for t in targets if not isinstance(t, list))
            if simple_count > 2:
                raise LynxInputError(f"loop takes at most 2 simple loop variables, got {simple_count}", token.line)
            iterable = self.parse_assign_rhs()
            body = self._parse_loop_body()
            return Loop(None, body, targets, iterable)
        condition = self.parse_expression()
        body = self._parse_loop_body()
        return Loop(condition, body)

    def _parse_loop_body(self) -> list[Any]:
        self.loop_depth += 1
        try:
            return self.parse_body()
        finally:
            self.loop_depth -= 1

    def _loop_targets(self) -> list[Any] | None:
        # Look ahead for a for-header: targets can be:
        # - IDENTIFIER (, IDENTIFIER)* COLON (simple targets)
        # - (IDENTIFIER (, IDENTIFIER)*) (, (IDENTIFIER (, IDENTIFIER)*))* COLON (unpack groups)
        # Returns nested list structure: ["i", ["a", "b"]] for "loop i, (a, b):"
        i = self.current
        if self._type_at(i) not in ("IDENTIFIER", "LPAREN"):
            return None

        targets: list[Any] = []

        def parse_target_group(start_i: int) -> tuple[Any, int]:
            """Parse a target group: either IDENTIFIER or (IDENTIFIER, ...)."""
            if self._type_at(start_i) == "LPAREN":
                # Unpack group: (a, b, c)
                i = start_i + 1
                group: list[str] = []
                if self._type_at(i) != "IDENTIFIER":
                    return None, -1
                while True:
                    group.append(self._type_at(i))  # placeholder, will consume later
                    i += 1
                    if self._type_at(i) == "COMMA":
                        i += 1
                        if self._type_at(i) != "IDENTIFIER":
                            return None, -1
                        continue
                    if self._type_at(i) == "RPAREN":
                        return group, i + 1
                    return None, -1
            elif self._type_at(start_i) == "IDENTIFIER":
                return self._type_at(start_i), start_i + 1
            return None, -1

        # Parse first target
        first_group, next_i = parse_target_group(i)
        if first_group is None:
            return None
        i = next_i

        # Handle the first target
        if isinstance(first_group, list):
            targets.append(first_group)
        else:
            targets.append(first_group)

        # Parse remaining targets
        while self._type_at(i) == "COMMA":
            i += 1
            group, next_i = parse_target_group(i)
            if group is None:
                return None
            i = next_i
            if isinstance(group, list):
                targets.append(group)
            else:
                targets.append(group)

        if self._type_at(i) != "COLON":
            return None

        # Now consume the actual tokens
        consumed: list[Any] = []

        def consume_target_group() -> Any:
            if self.type() == "LPAREN":
                self.advance()  # consume LPAREN
                group: list[str] = []
                group.append(self.match("IDENTIFIER").value)
                while self.type() == "COMMA":
                    self.advance()
                    group.append(self.match("IDENTIFIER").value)
                self.match("RPAREN")
                return group
            else:
                return self.match("IDENTIFIER").value

        consumed.append(consume_target_group())
        while self.type() == "COMMA":
            self.advance()
            consumed.append(consume_target_group())
        self.match("COLON")
        return consumed

    def parse_loop_control(self, node_type: type[Any]) -> Any:
        # `stop`/`skip` may take an optional condition: `stop x > 3` desugars
        # to `if x > 3: stop`. With no trailing expression the control is
        # unconditional.
        token = self.advance()
        if self.loop_depth == 0:
            raise LynxSyntaxError(f"{token.value} outside of a loop", token.line)
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
