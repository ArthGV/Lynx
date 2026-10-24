# 0005. What "greater" and "smaller" mean for collections, and NaN

Status: accepted

## Context

Every comparison (`>`, `<`, `>=`, `<=`) is built from one primitive per type, `compare(a, b)`, and `=` comes from `equals`. `operations.py` relies on three rules: swapping the sides flips the answer, `compare` is 0 exactly when `equals` is true, and the order is transitive. Three types broke them:

- **Tables** compared column names by their spelling, starting from the left table, so two tables with different columns could each be "greater" than the other.
- **Graphs** only compared node and edge counts, so any two different graphs of the same size compared as equal in order while `=` said they differed.
- **Maps** compared in insertion order while `equals` ignores it.
- **NaN** is not equal to, greater than or smaller than anything, so `nan < 1` and `1 < nan` were both true.

## Decision

**Bigger is greater; the same size is ordered by content in a canonical order, never by how the value was built.**

| Type | Size first | Then, in sorted order |
|---|---|---|
| Array | length | elements, position by position |
| Map | number of keys | keys (by type, then value), then the values under them |
| Table | rows, then columns | column names, then cells column by column in that name order |
| Graph | nodes, then edges | node ids and their values, then edges (source, target) and their labels |

Values of different types are ordered by type rank first (`compare_cells`, one shared helper). Column order, key order and creation order never change an answer, and `compare` is 0 exactly when `equals` is true.

**NaN is void.** `Number(...)` of something that would be NaN (infinity minus infinity) returns a Void, the same way `x / 0` does. Infinity is left alone for now.

## Consequences

- `>` and `<` on tables, graphs and maps are total and consistent, so sorting and `order` behave.
- A small table can no longer be "greater" than a bigger one because its first column name sorts later.
- `Number(...)` may now produce a Void: code that builds a Number from arithmetic must not assume the result has a `.value`. `Text.number()` already treats `nan` as a non-number.
- `tests/test_ordering_invariants.py` checks all three rules for every type, and every pair of types through the operators; any new type should be added to its pools.
