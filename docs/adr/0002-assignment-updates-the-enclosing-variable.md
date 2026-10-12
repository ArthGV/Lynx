# 0002. Assignment updates an existing outer variable

Status: accepted

## Context

`Environment.set` always wrote into the current scope, so `n: n + 1` inside a function created a new local `n` and left the outer one untouched, silently. Counters, accumulators and state shared with a helper were impossible, while arrays could still be changed through `<:` and `a 0: x` (those walk outward), which made the language inconsistent.

## Decision

Plain assignment (`x: v` and `a, b: ...`) updates the **nearest scope that already holds the name**, walking out through the enclosing scopes. If no scope holds it, a local is created. This is `Environment.assign`.

Declarations stay local and use `Environment.set`: function parameters, loop variables (including unpack targets), the `catch` error variable, and `f: x` function definitions.

Scoping is lexical: a call's scope is a child of the scope the function was *defined* in, never the caller's. Only functions create scopes; `if`, `loop` and `try`/`catch` bodies share the enclosing one. Reads, element mutation (`a 0: 5`, `<:`, `>:`) and `del` already found names by walking outward, so all name operations now agree. The stored value is still copied (ADR 0001).

## Consequences

- A function can keep state in an outer variable, and nested functions can update the enclosing function's locals (closures).
- **Accidental overwrite.** A helper that assigns a throwaway name which also exists globally changes that global (`total: 0` inside `sum_list` overwrites a global `total`). There is no syntax to force a local; use a parameter or a different name. This is the main cost of the implicit rule.
- **Call-time dependence.** Whether `g: 1` inside a function is local or global depends on whether `g` exists when the function runs (`tests/programs/scope/global_defined_after.lx`).
- `x: x + 1` with no `x` anywhere is still a NameError (the right-hand side is read first).
- Lookup uses an iterative walk, so deep scope chains do not hit the Python recursion limit.

## Alternatives considered

- **Explicit keyword for outer writes** (e.g. `outer n: n + 1`) with plain assignment always local: safest, but adds another reserved word and syntax.
- **Forbid outer writes with an error:** keeps functions pure but makes counters and accumulators impossible.
- **Keep local-only:** the original behaviour; rejected because it fails silently.

Revisit with an explicit local/outer marker if accidental overwrites become a real problem.

Tests: `tests/test_environment.py` and `tests/programs/scope/`.
