# lynx

A **data-native scripting language**. Tables, maps, and arrays are first-class values that you
query with the language itself — no ORM, no `groupby` chain, no `pd` import.

`lynx` is a small interpreted language, implemented as a tree-walking interpreter in Python. It
is early and opinionated: the grammar fits on one screen, the feature set is deliberate, and
everything about the surface syntax lives in a single file.

```lynx
orders: ['id': 1, 2, 3, 4; 'customer': 'ada', 'bob', 'ada', 'cynthia'; 'amount': 40.0, 10.0, 35.0, 25.0]
>> where orders 'amount' > 15
```

```
┌────┬─────────┬──────┐
│ id │ customer│amount│
├────┼─────────┼──────┤
│  1 │'ada'    │   40 │
│  3 │'ada'    │   35 │
│  4 │'cynthia'│   25 │
└────┴─────────┴──────┘
```

## Why lynx?

SQL is where data already lives,  but it is a query language, not a programming one. Python is a
programming language, but data is a visitor: it has to be imported, converted, and wrangled out
of a library. `lynx` is one language for both.

- `where sales 'amount' > 100` — in place of `sales[sales['amount'] > 100]`
- `group orders 'customer'` — in place of a `groupby(...)` chain
- `users join orders` — in place of a `merge` call
- `sum sales 'amount'` — in place of a column then `.sum()`

This is what **everything works with everything** means. Every operation is defined for every
type, so the interpreter never answers "unsupported operand" — only "not implemented yet,"
pointing at the line. No casts, no type juggling, no `None` special-casing: data stays native.

## Design principles

**Data and ML focused.** Every feature earns its place by moving data forward. Graphics, web, UI,
and OS glue are out of scope by design — a feature, not a limitation. The roadmap extends only
where data lives: graphs, tensors, the rest of SQL, native machine learning.

**Minimal syntax.** The whole grammar fits on one screen. Keywords, symbols, and precedence all
live in one file, and the lexer, parser, and editor follow from it — fewer rules to learn, fewer
surprises.

**Low verbosity.** One symbol, one meaning: `:` assigns, `=` compares — no `==`, no
`let`/`const`/`var`. High-level keywords phrase operations as English sentences and take the
whole rest of the line, so `sum orders 'amount'` and `where orders 'amount' > 15` replace the
parenthesis-plumbing chains other languages need. Parentheses group; they don't decorate.

**Clear separation between data and code.** Data lives in files; code reads it, transforms it,
and hands it back — read, manipulate, write, done. The language is agnostic to the data's
specifics: `read` infers typing across `.csv`, `.yaml`, and `.txt`, ragged or missing cells
become `void`, and the same high-level queries (`where`, `group`, `sum`) work whatever the shape
of the data. You don't adapt the pipeline per data source.

## A real program

Tables are values. Columns are arrays, rows are maps, and the query keywords read like English.

```lynx
orders: ['id': 1, 2, 3, 4; 'customer': 'ada', 'bob', 'ada', 'cynthia'; 'amount': 40.0, 10.0, 35.0, 25.0]
>> orders                         // prints the whole table

>> sum orders 'amount'            // 110
>> avg orders 'amount'            // 27.5

// filter rows, then sort them
>> order (where orders 'customer' = 'ada') 'amount'

// split a table into per-key sub-tables
g: group orders 'customer'
>> len g                          // 3 distinct customers
>> sum (g 'ada') 'amount'         // 75

// join two tables on a shared column
users: ['id': 1, 2, 3; 'name': 'ada', 'bob', 'cynthia']
>> users join orders

// rows are maps, columns are arrays
>> orders 'id' 0                  // 1
>> first orders                   // { id: 1; customer: ada; amount: 40 }
>> count orders                   // 4
```

Output:

```text
┌────┬─────────┬──────┐
│ id │ customer│amount│
├────┼─────────┼──────┤
│  1 │'ada'    │   40 │
│  2 │'bob'    │   10 │
│  3 │'ada'    │   35 │
│  4 │'cynthia'│   25 │
└────┴─────────┴──────┘
110
27.5
┌────┬────────┬──────┐
│ id │customer│amount│
├────┼────────┼──────┤
│  3 │'ada'   │   35 │
│  1 │'ada'   │   40 │
└────┴────────┴──────┘
3
75
┌────┬─────────┬────────┬──────┐
│ id │ name    │customer│amount│
├────┼─────────┼────────┼──────┤
│  1 │'ada'    │'ada'   │   40 │
│  2 │'bob'    │'bob'   │   10 │
│  3 │'cynthia'│'ada'   │   35 │
└────┴─────────┴────────┴──────┘
1
{ id: 1; customer: ada; amount: 40 }
4
```

## Install and run

**Requirements.** lynx is a Python tree-walking interpreter — the only dependency is Python
3.10+. `pip install -e .` installs it, then `lynx program.lx` runs your file. The `.lx` files you
write are plain text.

```bash
pip install -e .
lynx program.lx
```

Source files use the `.lx` extension. `lynx` warns if a file doesn't end in `.lx`, but runs it
anyway. Without installing, `python -m src.main program.lx` does the same thing.

## A tour of the language

**Values.** Four types: `Number`, `Text`, `Boolean`, and `Void`. Numbers print without a
trailing `.0`. Text is single-quoted: `'hi'`. The literal keywords are `true`, `false`, `void`,
and `pi`.

**Variables** are assigned with `:` — there is no declaration keyword.

```lynx
age: 20
age: age + 5    // reassignment is the same syntax
```

**Printing** is the `>>` statement:

```lynx
>> 1 + 2        // 3
>> 3, 4         // [ 3, 4 ] — a comma-run prints as an array
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
| 7 | `__` | inclusive range (`3__7` = `[ 3, 4, 5, 6, 7 ]`) |

Note that `=` is **equality**, not assignment (assignment is `:`), and `!=` is its negation —
there is no `==`. So `>> 5 > 3 = true` prints `true`. For numbers, `≈` is true when the two are
less than 1 apart. The `-or-almost` variants (`>≈`, `<≈`, or the ASCII forms `>~`, `<~`) combine
comparison with approximation: `5 >~ 5.3` is true because 5.3 is within 1 of 5 and bigger than it.

**Keyword functions** read like English sentences and take the **whole rest of the line** as
their argument:

```lynx
>> type 'hi'      // Text
>> text 42        // 42
>> number '3.5'   // 3.5
>> boolean 1      // true
>> len 12345      // 5
>> first (1, 2, 3) // 1
>> last (1, 2, 3)  // 3
>> not true       // false
>> middle 12345   // 3
>> sqrt 9         // 3
```

**Parentheses group and override priority** — a `( … )` is a value at any spot, and a
parenthesized comma-run is an array literal:

```lynx
>> (len 12345) > 3              // true
>> (1 + 2) * 3                  // 9
>> 2 in (1, 2, 3)               // true
>> f (1, 2, 3), 4               // one array arg and one number arg
```

**Arrays.** A comma-separated list of anything, or built empty with `array`. Element access
reuses the call machinery (`my_array 0`, chained for nesting). Appending is `<:` (end) and `>:`
(front) — the right-hand side is parsed like an assignment, so an array splices its elements in
and anything else appends as a single element.

```lynx
nums: 1, 2, 3
nums <: 4            // [ 1, 2, 3, 4 ]
nums >: 0            // [ 0, 1, 2, 3, 4 ]
>> nums <: 7         // [ 0, 1, 2, 3, 4, 5, 6, 7 ]
```

**Maps.** `{ 'a': 1; 'b': 2 }` — `;` separates entries so values can be arrays. Reading a missing
key returns `void`. `in` checks keys.

```lynx
m: { 'a': 1; 'b': 2 }
>> m 'nope'       // void
>> 'a' in m       // true
```

**Tables** are column-oriented. A table literal lists columns, each with a name and values; the
`table` keyword builds an empty one. Columns and rows are both accessible, and loops iterate rows.

```lynx
t: ['id': 1, 2, 3; 'price': 10.0, 20.0, 30.0]
>> len t               // [ 3, 2 ] — rows, columns
>> t 'id'              // [ 1, 2, 3 ] — a whole column is an array
>> t 'id' 0            // 1 — chained access picks one cell
>> t 0                 // { id: 1; price: 10 } — a row is a map
>> first t             // { id: 1; price: 10 }
>> last t              // { id: 3; price: 30 }
```

**SQL-style queries** are part of the language, not a library layer:

```lynx
>> select t 'id'            // project a column
>> where t 'price' > 15     // filter rows by a comparison
>> order t 'id'             // sort rows
>> group t 'dept'           // split into a map of sub-tables
>> t1 join t2               // join on shared columns
>> sum t 'price'            // aggregates: sum avg min max count distinct
>> count t                  // number of rows
```

**Ranges** `start__end` build inclusive integer sequences, and work for slicing:

```lynx
>> 3__7             // [ 3, 4, 5, 6, 7 ]
>> __7              // [ 0, 1, 2, 3, 4, 5, 6, 7 ] — the lower bound defaults
>> len 3__7         // 5
```

**Conditionals** take a condition on the `if` line and an indented body. A second condition on an
`else` makes it an else-if; a bare `else` is the fallback.

```lynx
if temperature > 25
 >> 'warm'
else
 >> 'cold'
```

**Loops.** `loop` iterates anything — arrays, maps, tables, ranges, text — and binds an index too
when you declare two variables. With a condition instead of an iterable, it is a `while` loop.
`stop` breaks, `skip` continues; both take an optional condition.

```lynx
loop val: 1, 2, 3
 >> val

loop ind, val: 1, 2, 3
 >> ind            // 0, 1, 2

counter: 0
loop counter < 3
 counter: counter + 1
 >> counter
```

**Functions** are declared like variables, with `:` and an indented body. `>>>` returns, and a
comma after it returns an array — so functions hand back several things at once:

```lynx
pair: a, b
 >>> a, b
r: pair 7, 9
>> r 0               // 7
>> r 1               // 9
```

**File I/O** speaks the formats data lives in: `read` and `write` handle `.txt`, `.csv`, and
`.yaml`, with typed-cell inference (numbers stay numbers, text stays text, nothing is lost in a
round-trip).

```lynx
t: read 'sales.csv'      // a CSV becomes a table, headers and all
>> sum t 'amount'
write 'report.yaml', t
```

**Cross-type operations** follow the everything-works-with-everything rule rather than raising.
Booleans add as *or* and multiply as *and*, so `true + false` is `true` and `true * false` is
`false`. Where an operation hasn't been filled in yet, you get a clear message instead of a
traceback:

```
NotImplemented on line 1: 'multiply' is not implemented yet for Text
```

## Roadmap

The direction is more of the same: data stays native, and the heavy lifting happens in the
language rather than in glue code.

- **Graphs** — relationships a table can't express (nodes, edges, traversal), replacing
  an adjacency-map workaround with a first-class value.
- **Tensors** — n-dimensional arrays for working on data in bulk, with the same operator coverage
  every other type gets.
- **Full SQL commands** — the rest of the query layer: `limit`, `offset`, joins that take
  conditions, update and delete on tables.
- **Native machine learning** — training and running models in the language itself, with syntax
  that reads like the rest of lynx instead of a model-serving wrapper.
- **Imports / multi-file modules** — real projects and shared libraries beyond a single file.
- **Error handling (`try`/`expect`)** — programs that catch and recover instead of aborting
  on the first runtime error.

Nothing here is set in stone. If you build one of them (or decide a planned one is the wrong
direction), your voice carries — this is early software.

## Contributing

`lynx` is at pre 1.0 and deliberately small. Contributions, reviews, and opinions are very
welcome — open a pull request or an issue.

A few things that make the codebase easy to work with:

- **Golden tests.** Every program in `tests/programs/` is a `.lx` file paired with a `.expected`
  file of its exact stdout. Add a case by dropping in a new pair under the fitting subject folder
  — no code changes. Full suite: `python -m pytest`.
- **One source of truth.** The whole surface syntax — keywords, symbols, operator precedence —
  lives in `src/core/grammar.py`. Change nothing else by hand.
- **Everything works with everything.** A new type must carry a stub for every interface method,
  even unimplemented ones. Covered in the layout notes below.

If you are unsure where a feature starts, the grammar table in `src/core/grammar.py` and the
golden test folders answer most questions.

## Project layout

```
source text → tokenize()  → Parser(tokens).parse()  → execute()/evaluate()
               lexer.py      core/parser/                core/interpreter/
```

- `src/core/grammar.py` — the single source of truth: keywords, symbols, literals, and operator
  precedence. The lexer, parser, and error messages all follow from it.
- `src/core/parser/` and `src/core/interpreter/` — syntax and semantics, split into statements and
  expressions.
- `src/types/` — the value types: `Number`, `Text`, `Boolean`, `Void`, plus `Array` (`array.py`),
  `Map` (`map.py`), and `Table` (`table.py`).
- `src/runtime/` — how pairs of values resolve (including cross-type operations) and function
  values.
- `src/core/files.py` — `read`/`write` for `.txt`, `.csv`, and `.yaml`.
- `editors/vscode/` — syntax highlighting, generated from `grammar.py`.

## License

MIT — see `LICENSE`.