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
| 1 | `=` `!=` `≈` | equal, not equal, approximately equal |
| 2 | `in` | contained in — element of an array, key of a map |
| 3 | `>` `<` `>=` `<=` `>≈` `<≈` | greater, less, and their-or-almost variants |
| 4 | `+` `-` `xor` | add, subtract, exclusive or |
| 5 | `*` `/` | multiply, divide |
| 6 | `^` `root` | power, nth root (`2 ^ 3` = 8, `8 root 3` = 2) |

Note that `=` is **equality**, not assignment (assignment is `:`), and `!=` is its negation —
there is no `==`. So
`>> 5 > 3 = true` prints `true`. For numbers, `≈` is true when the two are less than 1 apart.
The `-or-almost` variants (`>≈`, `<≈`, or the ASCII equivalents `>~`, `<~`) combine comparison
with approximation: `5 >~ 5.3` is true because 5.3 is within 1 of 5.

**Keyword functions**: `type` gives a value's type name as text, `text` converts to text,
`len` gives a length — for a number, its digit count, `not` negates (logical NOT / `1 - x`),
`middle` returns the middle element, and `sqrt` is square root. A keyword function takes the
**whole rest of the line** as its argument:

```lynx
>> type 'hi'     // Text
>> text 42       // 42
>> len 12345     // 5
>> not true      // false
>> not 5         // -4
>> middle 12345  // 3
>> sqrt 9        // 3
>> sqrt 4        // 2
```

**Parentheses group and override priority** — a `( … )` is a value at any spot, so a keyword
function's result can go on the left of an operator, and a parenthesized comma-run is an array literal:

```lynx
>> (len 12345) > 3                // true
>> (1 + 2) * 3                    // 9
>> 2 in (1, 2, 3)                 // true
>> f (1, 2, 3), 4                 // one array arg and one number arg
```

**Constructors** `array` and `map` create empty collections. Unlike `len`/`type`, they take no
argument (they do not swallow the rest of the line), so they work anywhere a value works — in
literals, as call arguments, or as loop iterables:

```lynx
a: array      // []
m: map        // {}
a <: 1, 2     // [ 1, 2 ]
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

**Complex values.** An array is a comma-separated list (`1, true, 'hi'`), or built empty with
`array`; element access reuses the call machinery (`my_array 0`, chained for nesting). A map uses
`{ 'a': 1; 'b': 2 }` or is built empty with `map` — `;` separates entries so values can be
arrays. Reading a missing key returns `void`, like a `None`-default dictionary.

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

**Functions** are declared like variables, with `:` and an indented body; parameters are listed
after the colon. `>>>` returns, and a comma after it returns an array of the values — so functions
can hand back several things at once:

```lynx
pair: a, b
 >>> a, b
r: pair 7, 9
>> r 0               // 7
>> r 1               // 9
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

Working today: arithmetic, text, booleans, comparisons (including `>=`, `<=`, `>≈`/`<≈`, `!=`),
`not`, `middle`, `sqrt`, `type`, `text`, `len`, variables, `if`/`else`, functions, the complex
types (arrays, maps) with `in` and `<:`/`>:`, `^`/`root` for power, parentheses for grouping,
and `array`/`map` constructors.
Planned next: tables, matrices, graphs, and notebooks.

## Layout

```
source text → tokenize() → Parser.parse() → execute()/evaluate()
              lexer.py      parser.py         interpreter.py
```

`grammar.py` is the single source of truth for the surface syntax — keywords, symbols, and
operator precedence all live there, and the lexer, parser, and error messages follow from it.
