# 0004. File formats: what is read, what is written, and what is refused

Status: accepted

## Context

`read` / `write` handle `.txt`, `.csv` and `.yaml` with hand-written parsers (no PyYAML dependency). Fuzzing round trips (write, read, compare) and reading hand-written files found silent data loss and corruption in both directions:

- CSV: every line was trimmed, blank-looking rows vanished (an empty or whitespace-only value in a one-column table), text containing `\r` or other Unicode line separators broke rows, a quoted newline became two rows, an unterminated quote was swallowed, `inf`/`nan` became numbers.
- Graph CSV: text such as `(1, 2)` read back as an array, array items containing commas or quotes were mangled, nested arrays were written as `void`.
- YAML: the reader stopped at the first line it could not place and dropped the rest without an error (odd indentation, multi-line values, lists at their key's indent), cut values at `#` inside words and URLs, split `- http://x` and `- 12:30` into maps, rejected plain text containing `! & * | [ {`, kept the quotes of `"double quoted"` strings, and the writer turned nested arrays into `void`.
- `.txt`: `\r` and `\r\n` were translated on read.

## Decision

**Round trips are exact.** Anything lynx can write, it reads back identically: same types, same values, and writing what was read gives the same bytes. Anything a format cannot hold is refused with a clear error and no file is written.

**Numbers.** A bare cell or scalar is a Number only when it is plain decimal notation (ASCII digits, optional fraction and exponent) and printing the number gives the text back exactly. `007`, `1.50`, `1e3`, `-0`, `0x1F`, `1_000`, and `inf` / `nan` / `Infinity` stay Text. lynx has no infinity or NaN: `Text.number()` treats them as non-numbers too, and writing a non-finite Number to `.csv` or `.yaml` is an error.

**CSV.**
- Cells are typed: quoted is Text, bare is `void`, `true`/`false`, an exact number, or Text. Cells are never trimmed.
- Rows end at `\n`, `\r\n` or `\r` only; quoted cells may contain commas, quotes and line breaks. Bare blank lines are skipped, so the writer always quotes empty and whitespace-only text.
- An unterminated quote is an error naming its line. A BOM is dropped on read.
- One line reads as an Array, more as a Table, a header of exactly `kind,from,to,value` as a Graph. Header-only files read as an Array and a table with no rows cannot be written; these ambiguities are inherent and kept.

**Graph CSV value cells.** Arrays are written `(1, 'a,b', true)` with Text items quoted and `''` for a quote; nested arrays are refused. Text that would read as an array is written with one extra leading backslash, which the reader removes only in that case, so older files keep their meaning.

**YAML.** A supported subset: block maps and lists (a list may sit at its key's indent), nested lists, maps in lists, plain / single / double quoted scalars with escapes, comments (`#` after whitespace only), `---` and `...`, `true`/`false`/`null`/`~`/`void` in the usual spellings. Plain text may contain `! & * | [ { <<` anywhere but at the start. Text with control characters or line breaks is written double-quoted with escapes. Everything else (flow collections with content, block scalars, multi-line values, anchors, tags, merge keys, tabs, duplicate keys) is an error naming the file line. Leftover input is never skipped.

**Bytes.** Files are read and written as UTF-8 without newline translation (`.txt` exactly, `.csv` / `.yaml` ignoring a BOM). Invalid UTF-8 is a lynx error.

## Consequences

- No new dependency; the YAML subset is stated, enforced and tested.
- Files in other dialects fail loudly with a line number instead of being misread.
- Files written by older lynx versions still read, except in three corner cases: a bare `inf`/`nan` cell is now Text, a graph cell `()` is an empty array, and an unescaped Text cell that parses as an array is read as an array.
- The format code lives in `lynx/core/formats/` (`csv_io.py`, `yaml_io.py`) with shared helpers in `lynx/utils/` (`numbers.py`, `cells.py`, `graph_cells.py`), which also removes the types-to-core import cycle for graph cells.

Tests: `tests/test_roundtrip_files.py` (awkward strings and numbers in every position, seeded random nested values, refusals), `tests/test_file_readers.py` (hand-written CSV/YAML and malformed input), golden programs in `tests/programs/io/`.
