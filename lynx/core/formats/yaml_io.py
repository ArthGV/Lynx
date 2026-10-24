"""`.yaml` reading and writing: the subset of YAML that lynx values map onto.

Supported: block maps and lists (a list may sit at its key's indent), nested
lists (`- - 1`), maps inside lists, plain / 'single' / "double" quoted
scalars, `#` comments, a leading `---` and a trailing `...`. `true`/`false`
and `null`/`~`/`void` (in the usual spellings) are Boolean and Void, numbers
that print back exactly are Number, everything else is Text.

Everything else (flow collections with content, block scalars `|` `>`,
multi-line scalars, anchors, tags, merge keys, tabs, duplicate keys) is a
lynx error naming the line; nothing is ever skipped silently. Written text is
single-quoted, or double-quoted with escapes when it holds control characters
or line breaks, so any Text round-trips.
"""

import math
import re
from dataclasses import dataclass

from lynx.errors.errors import LynxError, LynxTypeError
from lynx.types.array import Array
from lynx.types.base_type import Type
from lynx.types.graph import Graph
from lynx.types.map import Map
from lynx.types.simple_type import Boolean, Number, Text, Void
from lynx.types.table import Table
from lynx.utils.keys import value_from_key
from lynx.utils.numbers import parse_exact_number

ROOT_ERROR = "a .yaml file must be a mapping at the top level to read into a Map"

_NULLS = {"null", "Null", "NULL", "~", "void"}
_TRUES = {"true", "True", "TRUE"}
_FALSES = {"false", "False", "FALSE"}
_ESCAPES = {
    "0": "\0",
    "a": "\a",
    "b": "\b",
    "t": "\t",
    "n": "\n",
    "v": "\v",
    "f": "\f",
    "r": "\r",
    "e": "\x1b",
    " ": " ",
    '"': '"',
    "/": "/",
    "\\": "\\",
    "N": "\x85",
    "_": "\xa0",
    "L": chr(0x2028),
    "P": chr(0x2029),
}
_HEX_ESCAPES = {"x": 2, "u": 4, "U": 8}
# Besides control characters, these are written double-quoted with an escape.
_ESCAPED_EXTRA = "\x7f\x85" + chr(0x2028) + chr(0x2029) + chr(0xFEFF)
_LINE_BREAKS = re.compile(r"\r\n|\r|\n")
# A plain scalar may not start with these: anchors, aliases, tags, directives
# and the characters YAML reserves. Inside a scalar they are ordinary text.
_UNSUPPORTED_START = {"&", "*", "!", "%", "@", "`"}


# ---------------------------------------------------------------------------
# read
# ---------------------------------------------------------------------------


@dataclass
class _Line:
    indent: int
    text: str
    number: int  # 1-based line in the file


def read_yaml(content: str, line: int | None) -> Map:
    lines = _significant_lines(content, line)
    if not lines:
        raise LynxError(ROOT_ERROR, line)
    parser = _Parser(lines, line)
    root = parser.parse_block(lines[0].indent)
    if not isinstance(root, Map):
        raise LynxError(ROOT_ERROR, line)
    if parser.i < len(lines):
        raise LynxError(f"yaml line {lines[parser.i].number}: unexpected indentation", line)
    return root


def _significant_lines(content: str, line: int | None) -> list[_Line]:
    result: list[_Line] = []
    first = True
    for number, raw in enumerate(_LINE_BREAKS.split(content), start=1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        leading = raw[: len(raw) - len(raw.lstrip(" \t"))]
        if "\t" in leading:
            raise LynxError(f"yaml feature '\t' is not supported by lynx (line {number})", line)
        text = raw.strip()
        if text == "..." or (text.startswith("... ") and text[4:].lstrip().startswith("#")):
            break
        if first and (text == "---" or (text.startswith("--- ") and text[4:].lstrip().startswith("#"))):
            first = False
            continue
        first = False
        result.append(_Line(len(leading), text, number))
    return result


def _strip_comment(text: str) -> str:
    """Cut a trailing ` # comment` (a `#` only starts one after whitespace)."""
    for i, ch in enumerate(text):
        if ch == "#" and (i == 0 or text[i - 1] in " \t"):
            return text[:i].rstrip()
    return text


class _Parser:
    def __init__(self, lines: list[_Line], line: int | None) -> None:
        self.lines = lines
        self.i = 0
        self.line = line

    def fail(self, message: str, number: int) -> LynxError:
        return LynxError(f"yaml line {number}: {message}", self.line)

    def unsupported(self, token: str, number: int) -> LynxError:
        return LynxError(f"yaml feature '{token}' is not supported by lynx (line {number})", self.line)

    # -- blocks -----------------------------------------------------------

    def parse_block(self, indent: int) -> Type:
        current = self.lines[self.i]
        if current.text == "-" or current.text.startswith("- "):
            return self.parse_sequence(indent)
        if self.split_key(current) is not None:
            return self.parse_mapping(indent)
        self.i += 1
        return self.parse_scalar(current.text, current.number)

    def parse_mapping(self, indent: int) -> Map:
        entries: list[tuple[Type, Type]] = []
        while self.i < len(self.lines):
            current = self.lines[self.i]
            if current.indent < indent:
                break
            if current.indent > indent:
                raise self.fail("unexpected indentation", current.number)
            if current.text == "-" or current.text.startswith("- "):
                raise self.fail("a list item where a key was expected", current.number)
            split = self.split_key(current)
            if split is None:
                raise self.fail(f"expected 'key: value', got {current.text!r}", current.number)
            key_text, rest = split
            key = self.parse_scalar(key_text, current.number, as_key=True)
            if not isinstance(key, (Text, Number, Boolean, Void)):
                raise self.fail("mapping keys must be scalars", current.number)
            self.i += 1
            entries.append((key, self.parse_value(rest, indent, current.number)))
        return Map(entries, self.line)

    def parse_value(self, rest: str, indent: int, number: int) -> Type:
        """The value after `key:` — inline, or the block on the next lines."""
        rest = rest.strip()
        if rest and not rest.startswith("#"):
            return self.parse_scalar(rest, number)
        if self.i < len(self.lines):
            following = self.lines[self.i]
            if following.indent > indent:
                return self.parse_block(following.indent)
            if following.indent == indent and (following.text == "-" or following.text.startswith("- ")):
                return self.parse_sequence(indent)  # a list level with its key
        return Void()

    def parse_sequence(self, indent: int) -> Array:
        items: list[Type] = []
        while self.i < len(self.lines):
            current = self.lines[self.i]
            if current.indent != indent or not (current.text == "-" or current.text.startswith("- ")):
                if current.indent > indent:
                    raise self.fail("unexpected indentation", current.number)
                break
            after = current.text[1:].lstrip()
            if not after or after.startswith("#"):
                self.i += 1
                following = self.lines[self.i] if self.i < len(self.lines) else None
                if following is not None and following.indent > indent:
                    items.append(self.parse_block(following.indent))
                else:
                    items.append(Void())
                continue
            # The item's content starts two columns in (after "- "): treat it
            # as a line of its own at that column, so `- a: 1`, `- - 1` and
            # `- text` all parse by the ordinary block rules.
            column = indent + (len(current.text) - len(current.text[1:].lstrip()))
            self.lines[self.i] = _Line(column, current.text[1:].lstrip(), current.number)
            items.append(self.parse_block(column))
        return Array(items)

    # -- keys and scalars ---------------------------------------------------

    def split_key(self, current: _Line) -> tuple[str, str] | None:
        """(key, rest of line) for a `key: value` / `key:` line, else None."""
        text = current.text
        if text.startswith(("'", '"')):
            try:
                _, end = self.read_quoted(text, current.number)
            except LynxError:
                return None
            tail = text[end:].lstrip()
            if tail.startswith(":") and (len(tail) == 1 or tail[1] == " "):
                return text[:end], tail[1:]
            return None
        found = text.find(": ")
        if found == -1:
            if not text.endswith(":"):
                return None
            key, rest = text[:-1], ""
        else:
            key, rest = text[:found], text[found + 2 :]
        if _strip_comment(key) != key:
            return None  # the colon is inside a comment
        return key.rstrip(), rest

    def read_quoted(self, text: str, number: int) -> tuple[str, int]:
        """The value of the quoted scalar at the start of `text`, and where it ends."""
        quote = text[0]
        out: list[str] = []
        i = 1
        while i < len(text):
            ch = text[i]
            if ch == quote:
                if quote == "'" and text[i + 1 : i + 2] == "'":
                    out.append("'")
                    i += 2
                    continue
                return "".join(out), i + 1
            if quote == '"' and ch == "\\":
                i += 1
                if i >= len(text):
                    break
                code = text[i]
                if code in _HEX_ESCAPES:
                    width = _HEX_ESCAPES[code]
                    digits = text[i + 1 : i + 1 + width]
                    if len(digits) != width or not all(c in "0123456789abcdefABCDEF" for c in digits):
                        raise self.fail(f"bad \\{code} escape", number)
                    out.append(chr(int(digits, 16)))
                    i += 1 + width
                    continue
                if code not in _ESCAPES:
                    raise self.fail(f"unknown escape \\{code}", number)
                out.append(_ESCAPES[code])
                i += 1
                continue
            out.append(ch)
            i += 1
        raise self.fail("unterminated quoted text", number)

    def parse_scalar(self, text: str, number: int, as_key: bool = False) -> Type:
        text = text.strip()
        if text[:1] in ("'", '"'):
            value, end = self.read_quoted(text, number)
            if _strip_comment(text[end:].strip()):
                raise self.fail("unexpected text after a quoted value", number)
            return Text(value)
        text = _strip_comment(text)
        first = text[:1]
        if as_key and text == "<<":
            raise self.unsupported("<<", number)
        if first in ("|", ">"):
            raise self.unsupported(first, number)  # block / folded scalars
        if first in ("[", "{"):
            if text in ("[]", "{}"):
                return Array([]) if first == "[" else Map()
            raise self.unsupported(first, number)  # flow collections with content
        if first in _UNSUPPORTED_START:
            raise self.unsupported(first, number)
        if first == "?" and (len(text) == 1 or text[1] == " "):
            raise self.unsupported("?", number)
        if text in _NULLS:
            return Void()
        if text in _TRUES:
            return Boolean(True)
        if text in _FALSES:
            return Boolean(False)
        number_value = parse_exact_number(text)
        if number_value is not None:
            return Number(number_value)
        return Text(text)


# ---------------------------------------------------------------------------
# write
# ---------------------------------------------------------------------------


def write_yaml(value: Type, formats_to: str, line: int | None) -> str:
    if not isinstance(value, Map):
        raise LynxTypeError(f"a value of type {value.type_name()} writes to {formats_to}, not .yaml", line)
    if not value.value:
        return "{}\n"
    return "\n".join(_map_lines(value, 0, line)) + "\n"


def _map_lines(mapping: Map, indent: int, line: int | None) -> list[str]:
    pad = "  " * indent
    lines: list[str] = []
    for raw_key, item in mapping.value.items():
        head = pad + _scalar(value_from_key(raw_key), line) + ":"
        inline = _inline_value(item, line)
        if inline is not None:
            lines.append(head + " " + inline)
        elif isinstance(item, Map):
            lines.append(head)
            lines.extend(_map_lines(item, indent + 1, line))
        else:
            assert isinstance(item, Array)
            lines.append(head)
            lines.extend(_sequence_lines(item, indent + 1, line))
    return lines


def _sequence_lines(array: Array, indent: int, line: int | None) -> list[str]:
    pad = "  " * indent
    lines: list[str] = []
    for item in array.value:
        inline = _inline_value(item, line)
        if inline is not None:
            lines.append(pad + "- " + inline)
            continue
        if isinstance(item, Map):
            child = _map_lines(item, indent + 1, line)
        else:
            assert isinstance(item, Array)
            child = _sequence_lines(item, indent + 1, line)
        # the first line of the child shares the dash's line
        lines.append(pad + "- " + child[0].lstrip())
        lines.extend(child[1:])
    return lines


def _inline_value(value: Type, line: int | None) -> str | None:
    """The one-line form of a scalar or an empty collection, else None."""
    if isinstance(value, Map):
        return None if value.value else "{}"
    if isinstance(value, Array):
        return None if value.value else "[]"
    return _scalar(value, line)


def _scalar(value: Type, line: int | None) -> str:
    if isinstance(value, Text):
        return _quote(value.value)
    if isinstance(value, Number):
        if not math.isfinite(value.value):
            raise LynxError("cannot write infinity or NaN to a .yaml", line)
        return str(value.value)
    if isinstance(value, Boolean):
        return "true" if value.value else "false"
    if isinstance(value, Void):
        return "void"
    if isinstance(value, (Table, Graph)):
        raise LynxTypeError(
            f"cannot write {value.type_name()} values in a .yaml; only scalars, maps and arrays are supported",
            line,
        )
    raise LynxTypeError(f"cannot write {value.type_name()} values in a .yaml", line)


def _quote(text: str) -> str:
    if any(ord(ch) < 32 or ch in _ESCAPED_EXTRA for ch in text):
        out: list[str] = []
        for ch in text:
            escaped = {"\\": "\\\\", '"': '\\"', "\n": "\\n", "\r": "\\r", "\t": "\\t", "\0": "\\0"}.get(ch)
            if escaped is not None:
                out.append(escaped)
            elif ord(ch) < 32 or ch in _ESCAPED_EXTRA:
                out.append(f"\\x{ord(ch):02x}" if ord(ch) < 256 else f"\\u{ord(ch):04x}")
            else:
                out.append(ch)
        return '"' + "".join(out) + '"'
    return "'" + text.replace("'", "''") + "'"
