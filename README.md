# lynx

A small interpreted programming language, implemented as a tree-walking interpreter in Python.

Lynx has one guiding rule: **everything works with everything.** Every operation is defined for
every type, so there is no such thing as an "unsupported operand" error — only operations nobody
has written yet, which say so and point at the line.

```lynx
// a first program
name: 'world'
>> 'hello ' + name        // hello world

/// a comment can span several lines,
like a docstring. It ends on the first
line whose text ends with ///, done///
>> 1 + 1                   // 2

age: 20
if age > 18
 >> 'adult'
else
 >> 'minor'
```

## Install and run

```bash
pip install -e .
lynx example.lx
```

Source files use the `.lx` extension. `lynx` warns if a file doesn't end in `.lx`, but runs it
anyway. Without installing, `python -m src.main example.lx` does the same thing.

## The language

**Comments** start with `//` and run to the end of the line.

**Values.** Four types: `Number`, `Text`, `Boolean`, `Void`. Numbers are written `42` or `3.5`
and print without a trailing `.0`. Text is single-quoted: `'hi'`. The literal keywords are
`true`, `false`, `void`, and `pi` (3.14).

**Variables** are assigned with `:` — there is no declaration keyword.

```lynx
age: 20
age: age + 5    // reassignment is the same syntax
```

**Printing** is the `>>` statement:

```lynx
>> 1 + 2        // 3
```

**Operators**, loosest-binding level first:

| Level | Operators | Meaning |
|---|---|---|
| 1 | `=` `≈` | equal, approximately equal |
| 2 | `in` | contained in — element of an array, key of a map |
| 3 | `>` `<` | greater, less |
| 4 | `+` `-` `xor` | add, subtract, exclusive or |
| 5 | `*` `/` | multiply, divide |

Note that `=` is **equality**, not assignment (assignment is `:`), and there is no `==`. So
`>> 5 > 3 = true` prints `true`. For numbers, `≈` is true when the two are less than 1 apart.

**Keyword functions**: `type` gives a value's type name as text, `text` converts to text, and
`len` gives a length — for a number, its digit count. A keyword function takes the **whole rest
of the line** as its argument:

```lynx
>> type 'hi'     // Text
>> text 42       // 42
>> len 12345     // 5
>> len 1 + 10    // 2 — len (1 + 10), not (len 1) + 10
```

There are no parentheses yet, so you cannot use the result on the left of an operator:
`len 12345 > 3` means `len (12345 > 3)`, not `(len 12345) > 3`. Name it first:

```lynx
digits: len 12345
>> digits > 3    // true
```

**Conditionals** take a condition on the `if` line and an indented body. A second condition on an
`else` makes it an else-if; a bare `else` is the fallback.

```lynx
if 1 > 2
 >> 'a'
else 2 > 1
 >> 'b'
else
 >> 'c'
```

**Cross-type operations** follow the everything-works-with-everything rule rather than raising.
Booleans add as *or* and multiply as *and*, so `true + false` is `true` and `true * false` is
`false`. Where an operation hasn't been filled in yet you get a clear message:

```
NotImplemented on line 1: 'multiply' is not implemented yet for Text
```

**Complex values.** An array is a comma-separated list with no brackets (`1, true, 'hi'`);
element access reuses the call machinery (`my_array 0`, chained for nesting). A map uses
`{ 'a': 1; 'b': 2 }` — `;` separates entries so values can be arrays. Reading a missing key
returns `void`, like a `None`-default dictionary.

```lynx
m: { 'a': 1; 'b': 2 }
>> m 'nope'       // void
>> 'a' in m       // true — checks the keys
```

`in` also works on arrays, and on scalars (which iterate, so `3 in 5` is true and `'h' in 'hello'`
is character membership).

**Appending to an array** is `<:` (end) and `>: ` (front). The right-hand side is parsed like an
assignment, so an array splices its elements in and anything else appends as a single element.
The operation returns the array, so you can print it or chain it.

```lynx
nums: 1, 2, 3
nums <: 4            // [ 1, 2, 3, 4 ]
nums >: 0            // [ 0, 1, 2, 3, 4 ]
nums <: 5, 6         // [ 0, 1, 2, 3, 4, 5, 6 ]
>> nums <: 7         // [ 0, 1, 2, 3, 4, 5, 6, 7 ]
```

## Tests

Golden tests live in `tests/programs/`, grouped into subfolders by subject. Each `*.lx` program is paired with a `*.expected`
file holding its exact stdout. Add a case by dropping in a new pair in the fitting subfolder —
no code change needed.

```bash
pip install -e ".[dev]"
python -m pytest
```

## Status

Working today: arithmetic, text, booleans, comparisons, `type`, `text`, `len`, variables,
`if`/`else`, functions, and the complex types (arrays, maps) with `in` and `<:`/`>:`.
Planned next: tables, matrices, graphs, and input — `syntax` at the repo root sketches that
surface syntax and is a design doc, not a working program.

Known rough edges: many operations in `src/values.py` are still one-line stubs grouped under a
`# --- not implemented yet ---` comment; there are no parentheses yet, so you cannot group a
subexpression or use a keyword function's result on the left of an operator without naming it
first; and `tests/programs/same_type/comparisons.lx` is written with `==`, so that one golden test
currently fails.

## Layout

```
source text → tokenize() → Parser.parse() → execute()/evaluate()
              lexer.py      parser.py         interpreter.py
```

`grammar.py` is the single source of truth for the surface syntax — keywords, symbols, and
operator precedence all live there, and the lexer, parser, and error messages follow from it.
