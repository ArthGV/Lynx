"""Compiled loop plans.

A `loop` whose body is a flat run of simple numeric statements is compiled once
into a table of pre-bound operations and replayed every iteration instead of
being re-dispatched statement-by-statement through `execute` and `evaluate`.
Only a deliberately narrow subset of loops qualifies — plain same-type Number
arithmetic, no calls, no nested control flow, no division — and anything else
falls back to the generic walker unchanged, so this fast path can never alter
program behaviour: it is only ever a side-track, never a coarse route change.

The raw operations mirror the boxed ones exactly:

    PLUS/MINUS/STAR        -> operator.add/sub/mul        (simple_type.Number)
    order/equality compare -> raw <, >, <=, >=, ==, !=    (base_type.compare)
    ALMOST / *_ALMOST     -> abs(left - right) < 1        (simple_type.almost)
    write-back            -> Number(raw) int-normalizes   (Number.__init__)

SLASH, ROOT, POWER and XOR are excluded: the first two can vanish to a Void
sink, POWER can produce a complex, and XOR is `v * (1 - v)`.
"""

from __future__ import annotations

import operator
from collections.abc import Callable
from typing import Any

from src.core.nodes import (
    Assignment,
    BinaryExpression,
    Branch,
    Identifier,
    If,
)
from src.core.nodes import (
    Number as NumberNode,
)
from src.runtime import values
from src.runtime.environment import Environment
from src.types.simple_type import Number

# An operation's operand: (CONST, raw value) or (SLOT, variable name).
CONST = 0
SLOT = 1
Operand = tuple[int, Any]

_MISSING: Any = object()

# Same-type numeric arithmetic, mirrored from simple_type.Number.
_ARITH: dict[str, Callable[[Any, Any], Any]] = {
    "PLUS": operator.add,
    "MINUS": operator.sub,
    "STAR": operator.mul,
}


def _almost(left: Any, right: Any) -> bool:
    return bool(abs(left - right) < 1)


def _equal(left: Any, right: Any) -> bool:
    return bool(left == right)


def _not_equal(left: Any, right: Any) -> bool:
    return bool(left != right)


def _greater(left: Any, right: Any) -> bool:
    return bool(left > right)


def _less(left: Any, right: Any) -> bool:
    return bool(left < right)


def _greater_or_equal(left: Any, right: Any) -> bool:
    return bool(left >= right)


def _lesser_or_equal(left: Any, right: Any) -> bool:
    return bool(left <= right)


def _gt_almost(left: Any, right: Any) -> bool:
    return bool(left > right or abs(left - right) < 1)


def _lt_almost(left: Any, right: Any) -> bool:
    return bool(left < right or abs(left - right) < 1)


# Comparison tokens -> raw predicates, mirroring base_type's derived methods.
_CMP: dict[str, Callable[[Any, Any], bool]] = {
    "EQUAL": _equal,
    "NOT_EQUAL": _not_equal,
    "ALMOST": _almost,
    "GREATER": _greater,
    "LESS": _less,
    "GREATER_OR_EQUAL": _greater_or_equal,
    "LESSER_OR_EQUAL": _lesser_or_equal,
    "GREATER_OR_ALMOST": _gt_almost,
    "LESSER_OR_ALMOST": _lt_almost,
}


def _operand(node: Any, names: set[str]) -> Operand | None:
    """Flatten a numeric operand: an identifier (a slot) or a number literal
    (a constant). Anything richer disqualifies the surrounding statement."""
    if isinstance(node, Identifier):
        names.add(node.name)
        return (SLOT, node.name)
    if isinstance(node, NumberNode):
        return (CONST, Number(node.value).value)
    return None


def _assign(
    op: Callable[[Any, Any], Any], target: str, left: Operand, right: Operand
) -> Callable[[dict[str, Any]], None]:
    lk, lv = left
    rk, rv = right
    if lk is CONST and rk is CONST:
        settled = op(lv, rv)

        def const_step(data: dict[str, Any]) -> None:
            data[target] = settled

        return const_step
    if lk is CONST:
        def const_left_step(data: dict[str, Any]) -> None:
            data[target] = op(lv, data[rv])

        return const_left_step
    if rk is CONST:
        def const_right_step(data: dict[str, Any]) -> None:
            data[target] = op(data[lv], rv)

        return const_right_step

    def slot_step(data: dict[str, Any]) -> None:
        data[target] = op(data[lv], data[rv])

    return slot_step


def _cond(
    op: Callable[[Any, Any], bool], left: Operand, right: Operand
) -> Callable[[dict[str, Any]], bool]:
    lk, lv = left
    rk, rv = right
    if lk is CONST and rk is CONST:
        settled = op(lv, rv)

        def const_cond(data: dict[str, Any]) -> bool:
            return bool(settled)

        return const_cond
    if lk is CONST:
        def const_left_cond(data: dict[str, Any]) -> bool:
            return op(lv, data[rv])

        return const_left_cond
    if rk is CONST:
        def const_right_cond(data: dict[str, Any]) -> bool:
            return op(data[lv], rv)

        return const_right_cond

    def slot_cond(data: dict[str, Any]) -> bool:
        return op(data[lv], data[rv])

    return slot_cond


def _if_step(
    cond: Callable[[dict[str, Any]], bool],
    then_step: Callable[[dict[str, Any]], None],
    else_step: Callable[[dict[str, Any]], None] | None,
) -> Callable[[dict[str, Any]], None]:
    if else_step is None:
        def no_else_step(data: dict[str, Any]) -> None:
            if cond(data):
                then_step(data)

        return no_else_step

    def branch_step(data: dict[str, Any]) -> None:
        if cond(data):
            then_step(data)
        else:
            else_step(data)

    return branch_step


def _compile_condition(
    node: Any, names: set[str]
) -> Callable[[dict[str, Any]], bool] | None:
    if not isinstance(node, BinaryExpression):
        return None
    predicate = _CMP.get(node.operator)
    if predicate is None:
        return None
    left = _operand(node.left, names)
    right = _operand(node.right, names)
    if left is None or right is None:
        return None
    return _cond(predicate, left, right)


def _compile_assign(
    statement: Any, names: set[str]
) -> Callable[[dict[str, Any]], None] | None:
    if not isinstance(statement, Assignment):
        return None
    value = statement.value
    if not isinstance(value, BinaryExpression):
        return None
    op = _ARITH.get(value.operator)
    if op is None:
        return None
    left = _operand(value.left, names)
    right = _operand(value.right, names)
    if left is None or right is None:
        return None
    return _assign(op, statement.name, left, right)


def _compile_statement(
    statement: Any, names: set[str], writes: set[str]
) -> Callable[[dict[str, Any]], None] | None:
    if isinstance(statement, Assignment):
        step = _compile_assign(statement, names)
        if step is not None:
            writes.add(statement.name)
        return step
    if isinstance(statement, If):
        if len(statement.branches) != 1:
            return None
        branch = statement.branches[0]
        if not isinstance(branch, Branch) or len(branch.body) != 1:
            return None
        cond = _compile_condition(branch.condition, names)
        if cond is None:
            return None
        then_step = _compile_assign(branch.body[0], names)
        if then_step is None:
            return None
        writes.add(branch.body[0].name)
        else_step = None
        if statement.else_body is not None:
            if len(statement.else_body) != 1:
                return None
            else_step = _compile_assign(statement.else_body[0], names)
            if else_step is None:
                return None
            writes.add(statement.else_body[0].name)
        return _if_step(cond, then_step, else_step)
    return None


def _lookup(env: Environment, name: str) -> Any:
    """env.get without raising: the guard falls back to the walker, which
    re-raises the same name error, so the fast path never presents one first."""
    current: Environment | None = env
    while current is not None:
        if name in current.values:
            return current.values[name]
        current = current.parent
    return _MISSING


class LoopPlan:
    """A compiled fast path for one `Loop` node. `try_run` reads the loop's
    variables into a raw-number table once, replays the pre-bound steps, and
    boxes the writes back — or returns False so the caller runs the walker."""

    __slots__ = ("cond", "names", "over_name", "over_target", "steps", "writes")

    def __init__(
        self,
        names: list[str],
        writes: list[str],
        cond: Callable[[dict[str, Any]], bool] | None,
        over_name: str | None,
        over_target: str | None,
        steps: list[Callable[[dict[str, Any]], None]],
    ) -> None:
        self.names = names
        self.writes = writes
        self.cond = cond
        self.over_name = over_name
        self.over_target = over_target
        self.steps = steps

    def try_run(self, env: Environment) -> bool:
        data: dict[str, Any] = {}
        for name in self.names:
            value = _lookup(env, name)
            if not isinstance(value, Number):
                return False
            data[name] = value.value
        steps = self.steps
        ran = False
        cond = self.cond
        if cond is not None:
            while cond(data):
                for step in steps:
                    step(data)
                ran = True
        else:
            over_name = self.over_name
            target = self.over_target
            if over_name is None or target is None:
                return False
            container = _lookup(env, over_name)
            if not isinstance(container, values.Array):
                return False
            raw_items: list[Any] = []
            for cell in container.value:
                if not isinstance(cell, Number):
                    return False
                raw_items.append(cell.value)
            for item in raw_items:
                data[target] = item
                for step in steps:
                    step(data)
                ran = True
        if ran:
            for name in self.writes:
                env.set(name, Number(data[name]))
        return True


def compile_loop_plan(
    condition: Any,
    body: list[Any],
    targets: list[str] | None,
    iterable: Any | None,
) -> LoopPlan | None:
    names: set[str] = set()
    writes: set[str] = set()
    if targets is None:
        cond = _compile_condition(condition, names)
        if cond is None:
            return None
        over_name = None
        over_target = None
    else:
        if len(targets) != 1 or not isinstance(iterable, Identifier):
            return None
        over_name = iterable.name
        over_target = targets[0]
        cond = None
        writes.add(over_target)
    steps: list[Callable[[dict[str, Any]], None]] = []
    for statement in body:
        step = _compile_statement(statement, names, writes)
        if step is None:
            return None
        steps.append(step)
    if over_target is not None:
        names.discard(over_target)
    return LoopPlan(sorted(names), sorted(writes), cond, over_name, over_target, steps)
