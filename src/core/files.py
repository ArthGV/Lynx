"""File I/O: read and write .txt, .csv and .yaml files.

The module is imported at the bottom of interpreter/_base.py so it can
lazily import types (via Text.read → files) without an import cycle.
"""

from pathlib import Path
from typing import Any, cast

from src.errors.errors import LynxError, LynxTypeError
from src.types.array import Array
from src.types.base_type import Type
from src.types.map import Map
from src.types.simple_type import Boolean, Number, Text, Void
from src.types.table import Table
from src.utils.keys import map_key, value_from_key

SUPPORTED = {".txt", ".csv", ".yaml"}


# ---------------------------------------------------------------------------
# read
# ---------------------------------------------------------------------------


def read(path: str, line: int | None = None) -> Type:
    """Read a file and return a lynx Value."""
    ext = Path(path).suffix
    if ext not in SUPPORTED:
        raise LynxError(f"unsupported file format '{ext}', use .txt, .csv or .yaml", line)
    try:
        content = Path(path).read_text()
    except FileNotFoundError:
        raise LynxError(f"cannot read '{path}': file not found", line)
    except IsADirectoryError:
        raise LynxError(f"cannot read '{path}': Is a directory", line)
    except OSError as error:
        raise LynxError(f"cannot read '{path}': {error.strerror}", line)
    if ext == ".txt":
        return Text(content)
    if ext == ".csv":
        return _read_csv(content, line)
    return _read_yaml(content, line)


# ---------------------------------------------------------------------------
# write
# ---------------------------------------------------------------------------


def write(value: Type, path: Type, line: int | None = None) -> None:
    """Write a lynx Value to a file."""
    if not isinstance(path, Text):
        raise LynxTypeError(f"write needs a text path, got {path.type_name()}", line)
    ext = Path(path.value).suffix
    if ext not in SUPPORTED:
        raise LynxError(f"unsupported file format '{ext}', use .txt, .csv or .yaml", line)
    target = Path(path.value)
    if target.is_dir():
        raise LynxError(f"cannot write '{path.value}': Is a directory", line)
    # type-dispatch before creating anything
    if ext == ".txt":
        content = _write_txt(value, ext, line)
    elif ext == ".csv":
        content = _write_csv(value, ext, line)
    else:
        content = _write_yaml(value, ext, line)
    try:
        target = Path(path.value)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    except IsADirectoryError:
        raise LynxError(f"cannot write '{path.value}': Is a directory", line)
    except OSError as error:
        raise LynxError(f"cannot write '{path.value}': {error.strerror}", line)


# ---------------------------------------------------------------------------
# supported-format helper
# ---------------------------------------------------------------------------


def _formats_to(value: Type) -> str:
    if isinstance(value, (Array, Table)):
        return ".csv"
    if isinstance(value, Map):
        return ".yaml"
    return ".txt"


# ---------------------------------------------------------------------------
# txt
# ---------------------------------------------------------------------------


def _write_txt(value: Type, ext: str, line: int | None) -> str:
    if isinstance(value, (Number, Boolean, Void)):
        return str(value)
    if isinstance(value, Text):
        return value.value
    raise LynxTypeError(
        f"a value of type {value.type_name()} writes to {_formats_to(value)}, not .txt",
        line,
    )


# ---------------------------------------------------------------------------
# csv - write
# ---------------------------------------------------------------------------


def _write_csv(value: Type, ext: str, line: int | None) -> str:
    if isinstance(value, Array):
        if not value.value:
            return ""
        return _csv_line([_csv_cell(item, line) for item in value.value])
    if isinstance(value, Table):
        if not value.columns:
            raise LynxError("cannot write a table with no columns to .csv", line)
        if value.nrows == 0:
            raise LynxError("cannot write a table with no rows to .csv", line)
        names = list(value.columns)
        header = _csv_line([_csv_cell(Text(name), line) for name in names])
        rows = []
        for i in range(value.nrows):
            rows.append(_csv_line([_csv_cell(value.columns[name][i], line) for name in names]))
        return header + "\n" + "\n".join(rows) + "\n"
    raise LynxTypeError(
        f"a value of type {value.type_name()} writes to {_formats_to(value)}, not .csv",
        line,
    )


def _csv_line(cells: list[str]) -> str:
    return ",".join(cells)


def _csv_cell(value: Type, line: int | None) -> str:
    if isinstance(value, Void):
        return "void"
    if isinstance(value, Boolean):
        return "true" if value.value else "false"
    if isinstance(value, Number):
        return str(value)
    if isinstance(value, Text):
        if "\n" in value.value:
            raise LynxError("cannot write a text containing a newline to a .csv", line)
        if '"' in value.value or "," in value.value:
            return '"' + value.value.replace('"', '""') + '"'
        if _reinfers_non_text(value.value):
            return '"' + value.value + '"'
        return value.value
    raise LynxTypeError(
        f"cannot write {value.type_name()} values in a .csv; only scalars (number, text, boolean, void) are supported",
        line,
    )


def _reinfers_non_text(s: str) -> bool:
    """True when reading this bare string back would yield a non-Text value."""
    return s in ("true", "false", "void") or _is_exact_number(s)


def _is_exact_number(s: str) -> bool:
    try:
        v = float(s)
    except ValueError:
        return False
    if v % 1 == 0:
        v = int(v)
    return str(v) == s


# ---------------------------------------------------------------------------
# csv - read
# ---------------------------------------------------------------------------


def _read_csv(content: str, line: int | None) -> Type:
    data_lines = []
    for raw in content.splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        data_lines.append(_parse_csv_line(stripped))
    if not data_lines:
        return Array([])
    if len(data_lines) == 1:
        return Array([_infer_cell(text, quoted) for text, quoted in data_lines[0]])
    # table path
    header = [text for text, _ in data_lines[0]]
    seen = {}
    for name in header:
        if name in seen:
            raise LynxTypeError(f"duplicate column title '{name}'", line)
        seen[name] = True
    ncols = len(header)
    columns: dict[str, list[Type]] = {name: [] for name in header}
    for row_idx, row in enumerate(data_lines[1:], start=1):
        if len(row) > ncols:
            raise LynxError(
                f"row {row_idx + 1} has {len(row)} values but the header declares {ncols} columns",
                line,
            )
        for col_idx, name in enumerate(header):
            if col_idx < len(row):
                columns[name].append(_infer_cell(row[col_idx][0], row[col_idx][1]))
            else:
                columns[name].append(Void())
    return Table([(name, columns[name]) for name in header], line)


def _parse_csv_line(line: str) -> list[tuple[str, bool]]:
    """Return list of (text, was_quoted) pairs."""
    cells = []
    i = 0
    n = len(line)
    while i < n:
        if line[i] == '"':
            i += 1
            parts = []
            while i < n:
                if line[i] == '"':
                    if i + 1 < n and line[i + 1] == '"':
                        parts.append('"')
                        i += 2
                    else:
                        i += 1
                        break
                else:
                    parts.append(line[i])
                    i += 1
            cells.append(("".join(parts), True))
            if i < n and line[i] == ",":
                i += 1
        else:
            buf = []
            while i < n and line[i] != ",":
                buf.append(line[i])
                i += 1
            cells.append(("".join(buf), False))
            if i < n:
                i += 1
    if i == n and line.endswith(","):
        cells.append(("", False))
    return cells


def _infer_cell(text: str, quoted: bool) -> Type:
    if quoted:
        return Text(text)
    if text == "void":
        return Void()
    if text == "true":
        return Boolean(True)
    if text == "false":
        return Boolean(False)
    if _is_exact_number(text):
        return Number(text)
    return Text(text)


# ---------------------------------------------------------------------------
# yaml - write
# ---------------------------------------------------------------------------


def _write_yaml(value: Type, ext: str, line: int | None) -> str:
    if not isinstance(value, Map):
        raise LynxTypeError(
            f"a value of type {value.type_name()} writes to {_formats_to(value)}, not .yaml",
            line,
        )
    entries = [(value_from_key(k), v) for k, v in value.value.items()]
    return _yaml_map_entries(entries, 0, line) + "\n"


def _yaml_key(key: Type, line: int | None) -> str:
    if isinstance(key, Text):
        return "'" + key.value.replace("'", "''") + "'"
    if isinstance(key, Number):
        return str(key.value)
    if isinstance(key, Boolean):
        return "true" if key.value else "false"
    return "void"


def _yaml_scalar(value: Type) -> str:
    if isinstance(value, Text):
        return "'" + value.value.replace("'", "''") + "'"
    if isinstance(value, Number):
        return str(value.value)
    if isinstance(value, Boolean):
        return "true" if value.value else "false"
    return "void"


def _yaml_entry(key: Type, value: Type, indent: int, line: int | None) -> str:
    pad = "  " * indent
    head = pad + _yaml_key(key, line) + ":"
    if isinstance(value, (Number, Boolean, Void)):
        return head + " " + _yaml_scalar(value)
    if isinstance(value, Text):
        if "\n" in value.value:
            raise LynxError("cannot write a text containing a newline to a .yaml", line)
        return head + " " + _yaml_scalar(value)
    if isinstance(value, Map):
        if not value.value:
            return head + " {}"
        entries = [(value_from_key(k), v) for k, v in value.value.items()]
        return head + "\n" + _yaml_map_entries(entries, indent + 1, line)
    if isinstance(value, Array):
        if not value.value:
            return head + " []"
        return head + "\n" + _yaml_list(value.value, indent + 1, line)
    raise LynxTypeError(
        f"cannot write {value.type_name()} values in a .yaml; only scalars, maps and arrays are supported",
        line,
    )


def _yaml_map_entries(entries: list[tuple[Type, Type]], indent: int, line: int | None) -> str:
    if not entries:
        return "{}"
    return "\n".join(_yaml_entry(k, v, indent, line) for k, v in entries)


def _yaml_list(items: list[Type], indent: int, line: int | None) -> str:
    pad = "  " * indent
    rows = []
    for item in items:
        if isinstance(item, Map):
            if not item.value:
                rows.append(pad + "- {}")
                continue
            entries = [(value_from_key(k), v) for k, v in item.value.items()]
            first_key, first_val = entries[0]
            dash = pad + "- " + _yaml_key(first_key, line) + ":"
            if isinstance(first_val, (Number, Boolean, Void)):
                rows.append(dash + " " + _yaml_scalar(first_val))
            elif isinstance(first_val, Text):
                if "\n" in first_val.value:
                    raise LynxError("cannot write a text containing a newline to a .yaml", line)
                rows.append(dash + " " + _yaml_scalar(first_val))
            elif isinstance(first_val, Map):
                if first_val.value:
                    entries_nested = [(value_from_key(k), v) for k, v in first_val.value.items()]
                    rows.append(dash + "\n" + _yaml_map_entries(entries_nested, indent + 2, line))
                else:
                    rows.append(dash + " {}")
            elif isinstance(first_val, Array):
                if first_val.value:
                    rows.append(dash + "\n" + _yaml_list(first_val.value, indent + 2, line))
                else:
                    rows.append(dash + " []")
            else:
                rows.append(dash + " void")
            for k, v in entries[1:]:
                rows.append(_yaml_entry(k, v, indent + 1, line))
        else:
            rows.append(pad + "- " + _yaml_scalar(item))
    return "\n".join(rows)


# ---------------------------------------------------------------------------
# yaml - read
# ---------------------------------------------------------------------------


def _read_yaml(content: str, line: int | None) -> Map:
    stripped_lines = []
    for raw in content.splitlines():
        if not raw.strip():
            continue
        if raw.strip().startswith("#"):
            continue
        # detect tab in leading whitespace
        stripped_content = raw.strip()
        leading = raw[: len(raw) - len(raw.lstrip(" \t"))]
        if "\t" in leading:
            raise LynxError("yaml feature '\t' is not supported by lynx", line)
        stripped_lines.append((len(leading), stripped_content))
    if not stripped_lines:
        raise LynxError(
            "a .yaml file must be a mapping at the top level to read into a Map",
            line,
        )
    parser = _YamlParser(stripped_lines, line)
    root = parser._parse_block(0)
    if isinstance(root, (list, type(None))) or not isinstance(root, dict):
        raise LynxError(
            "a .yaml file must be a mapping at the top level to read into a Map",
            line,
        )
    return Map([(value_from_key(k), _to_lynx(v)) for k, v in root.items()])


def _to_lynx(struct: Any) -> Type:
    if isinstance(struct, dict):
        return Map([(value_from_key(k), _to_lynx(v)) for k, v in struct.items()])
    if isinstance(struct, list):
        return Array([_to_lynx(v) for v in struct])
    return Void() if struct is None else cast(Type, struct)


def _strip_comment(s: str) -> str:
    """Remove trailing # … comment, but not inside single-quoted strings."""
    in_single_quote = False
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "'" and not in_single_quote:
            in_single_quote = True
        elif ch == "'" and in_single_quote:
            in_single_quote = False
        elif ch == "#" and not in_single_quote:
            return s[:i].rstrip()
        i += 1
    return s


class _YamlParser:
    def __init__(self, lines: list[tuple[int, str]], line: int | None) -> None:
        self.lines = lines
        self.n = len(lines)
        self.i = 0
        self.line = line

    def _parse_block(self, indent: int) -> Any:
        if self.i >= self.n:
            return None
        if self.lines[self.i][0] != indent:
            return None
        content = self.lines[self.i][1]
        if content == "[]":
            self.i += 1
            return []
        if content == "{}":
            self.i += 1
            return {}
        if content.startswith("- "):
            return self._parse_list(indent)
        key, _rest = self._split_top_level_colon(content)
        if key is not None:
            return self._parse_map(indent)
        self.i += 1
        return _parse_inline_value(content)

    def _parse_map(self, indent: int) -> dict[Any, Any]:
        mapping = []
        while self.i < self.n and self.lines[self.i][0] == indent:
            content = self.lines[self.i][1]
            if content.startswith("- "):
                break
            key, rest = self._split_top_level_colon(content)
            if key is None:
                self.i += 1
                continue
            key_value = _parse_token(key, for_key=True, line=self.line)
            value = self._parse_value_after(rest, indent)
            raw = map_key(key_value)
            mapping.append((raw, value))
        result: dict[Any, Any] = {}
        for raw, val in mapping:
            result[raw] = val
        return result

    def _parse_list(self, indent: int) -> list[Any]:
        items: list[Any] = []
        while self.i < self.n and self.lines[self.i][0] == indent:
            content = self.lines[self.i][1]
            if not content.startswith("- "):
                break
            after_dash = content[2:]
            key, rest = self._split_top_level_colon(after_dash)
            if key is not None:
                # map-in-list: first entry on the dash line
                key_value = _parse_token(key, for_key=True, line=self.line)
                value = self._parse_value_after(rest, indent)
                entries = [(map_key(key_value), value)]
                # continuation entries sit under the dash's content, two
                # spaces deeper than the dash itself
                while (
                    self.i < self.n
                    and self.lines[self.i][0] == indent + 2
                    and not self.lines[self.i][1].startswith("- ")
                ):
                    c = self.lines[self.i][1]
                    k2, r2 = self._split_top_level_colon(c)
                    if k2 is not None:
                        kv2 = _parse_token(k2, for_key=True, line=self.line)
                        v2 = self._parse_value_after(r2, indent + 2)
                        entries.append((map_key(kv2), v2))
                    else:
                        self.i += 1
                result: dict[Any, Any] = {}
                for raw, val in entries:
                    result[raw] = val
                items.append(result)
            else:
                val = _parse_inline_value(after_dash)
                items.append(val)
                self.i += 1
        return items

    def _parse_value_after(self, rest: str, indent: int) -> Any:
        """Parse the value after a key: line at `indent`."""
        rest = rest.strip()
        if rest == "":
            # value is on following lines (deeper indent)
            if self.i + 1 < self.n and self.lines[self.i + 1][0] > indent:
                self.i += 1
                return self._parse_block(self.lines[self.i][0])
            self.i += 1
            return None  # Void
        # strip trailing comment
        rest = _strip_comment(rest)
        if not rest:
            if self.i + 1 < self.n and self.lines[self.i + 1][0] > indent:
                self.i += 1
                return self._parse_block(self.lines[self.i][0])
            self.i += 1
            return None
        self.i += 1
        return _parse_inline_value(rest)

    def _split_top_level_colon(self, content: str) -> tuple[str | None, str]:
        """Split on the first top-level colon that is not inside quotes."""
        in_single_quote = False
        for i, ch in enumerate(content):
            if ch == "'" and not in_single_quote:
                in_single_quote = True
            elif ch == "'" and in_single_quote:
                in_single_quote = False
            elif ch == ":" and not in_single_quote:
                key = content[:i].rstrip()
                rest = content[i + 1 :].lstrip()
                return key, rest
        return None, content


def _parse_inline_value(s: str) -> Any:
    s = s.strip()
    if not s:
        return None
    s = _strip_comment(s)
    if not s:
        return None
    if s in ("void", "null", "~"):
        return None
    if s == "true":
        return Boolean(True)
    if s == "false":
        return Boolean(False)
    if s == "[]":
        return Array([])
    if s == "{}":
        return Map()
    # exact number
    try:
        v = float(s)
        if v % 1 == 0:
            v = int(v)
        if str(v) == s:
            return Number(v)
    except ValueError:
        pass
    # quoted text
    if s.startswith("'"):
        if s.endswith("'") and len(s) >= 2:
            return Text(s[1:-1].replace("''", "'"))
        # malformed — treat as text
        return Text(s)
    # unsupported features
    for tok in ("<<", "&", "*", "!", "|", "[", "{"):
        if tok in s:
            raise LynxError(f"yaml feature '{tok}' is not supported by lynx", None)
    return Text(s)


def _parse_token(s: str, for_key: bool = False, line: int | None = None) -> Any:
    """Parse a scalar token (used for both keys and values)."""
    s = s.strip()
    if not s:
        return None
    if s in ("void", "null", "~"):
        return Void()
    if s == "true":
        return Boolean(True)
    if s == "false":
        return Boolean(False)
    # exact number
    try:
        v = float(s)
        if v % 1 == 0:
            v = int(v)
        if str(v) == s:
            return Number(v)
    except ValueError:
        pass
    # quoted text
    if s.startswith("'"):
        if s.endswith("'") and len(s) >= 2:
            return Text(s[1:-1].replace("''", "'"))
        return Text(s)
    # unsupported features
    for tok in ("<<", "&", "*", "!", "|"):
        if tok in s:
            raise LynxError(f"yaml feature '{tok}' is not supported by lynx", line)
    return Text(s)
