# 0001. Values are copied when they are bound or stored

Status: accepted

## Context

Variables used to hold references to value objects. `b: a` made both names point at the same object, so changing `a` (e.g. `a 0: 'x'`, `a <: 4`) also changed `b`, and a function could silently rewrite the caller's variable through its parameter. `Table.add` and `graph g` leaked shared cells in the same way.

## Decision

Assignment always produces an independent value, for every type (Text, Array, Map, Table, Graph). Every `Type` has a `copy()` method: `Number`, `Boolean` and `Void` return `self` (never mutated), `Text` returns a new `Text`, and the collections deep-copy their contents.

The interpreter copies wherever a value is bound or stored: assignment and multi-assignment, loop variables, function arguments, array/map/table literals, element and slice assignment, `<:` / `>:`, and graph node values and labels. Text stays mutable by index; it is just never shared.

## Consequences

- `b: a` then changing either side never affects the other.
- A function cannot mutate an array, map or table passed to it; it must return the new value.
- `x: arr 0` is independent of `arr`. Nested mutation of the real container (`arr 1 0: 'Q'`) still works, because it walks the stored objects.
- Self-containing values (`a 0: a`) can no longer be created.
- Cost: each bind is O(size of the value). Accepted for now; copy-on-write is the fallback if large data makes it matter.
- A new type must implement `copy()` (it is abstract on `Type`).

Tests: `tests/programs/statements/independent_copies.lx`.
