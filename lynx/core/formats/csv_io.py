"""`.csv` reading and writing.

Cells are typed (see `lynx.utils.cells.infer_cell`): a quoted cell is Text, a
bare one is `void`, a boolean, a number that prints back exactly, or Text.

The reader works on the whole text, not line by line, so a quoted cell may hold
commas, quotes and line breaks. Rows end at `\\n`, `\\r\\n` or `\\r` only. Cells
are never trimmed. Blank lines are skipped, which is why the writer always
quotes empty and whitespace-only text: a bare blank line is never data.

One data line reads as an Array, more as a Table. A header that is exactly
`kind,from,to,value` reads as a Graph.
"""

import math

from lynx.errors.errors import LynxError, LynxTypeError
from lynx.types.array import Array
from lynx.types.base_type import Type
from lynx.types.graph import Graph
from lynx.types.map import Map
from lynx.types.simple_type import Boolean, Number, Text, Void
from lynx.types.table import Table
from lynx.utils.cells import infer_cell
from lynx.utils.graph_cells import escape_text, write_array_cell
from lynx.utils.numbers import parse_exact_number

# A csv whose header is exactly these columns holds graph records. `read`
# re-assembles it into a Graph; the writer emits the same header for a Graph.
GRAPH_SCHEMA = ["kind", "from", "to", "value"]

Cell = tuple[str, bool]  # (text, was it quoted)


# ---------------------------------------------------------------------------
# read
# ---------------------------------------------------------------------------


def parse_records(content: str, line: int | None) -> list[list[Cell]]:
    """Split csv text into records of (text, quoted) cells."""
    records: list[list[Cell]] = []
    cells: list[Cell] = []
    buf: list[str] = []
    quoted = False
    in_quotes = False
    quote_line = 1
    line_no = 1
    i, n = 0, len(content)

    def end_record() -> None:
        cells.append(("".join(buf), quoted))
        # a bare blank (or all-space) line is not a record
        if not (len(cells) == 1 and not cells[0][1] and not cells[0][0].strip()):
            records.append(list(cells))
        cells.clear()
        buf.clear()

    while i < n:
        ch = content[i]
        if in_quotes:
            if ch == '"':
                if i + 1 < n and content[i + 1] == '"':
                    buf.append('"')
                    i += 2
                    continue
                in_quotes = False
            else:
                if ch == "\n":
                    line_no += 1
                buf.append(ch)
            i += 1
            continue
        if ch == '"' and not buf and not quoted:
            in_quotes = quoted = True
            quote_line = line_no
        elif ch == ",":
            cells.append(("".join(buf), quoted))
            buf.clear()
            quoted = False
        elif ch in "\r\n":
            if ch == "\r" and i + 1 < n and content[i + 1] == "\n":
                i += 1
            end_record()
            quoted = False
            line_no += 1
        else:
            buf.append(ch)  # a stray quote after the opening one is literal text
        i += 1
    if in_quotes:
        raise LynxError(f"unterminated quoted cell starting on line {quote_line} of the .csv", line)
    if cells or buf or quoted:
        end_record()
    return records


def read_csv(content: str, line: int | None) -> Type:
    records = parse_records(content, line)
    if not records:
        return Array([])
    header = [text for text, _ in records[0]]
    if header == GRAPH_SCHEMA:
        # A graph csv: a bare header is an empty graph, rows go through the
        # table shape so every `_from_table` rule and error message applies.
        if len(records) == 1:
            return Graph()
        return Graph(table_from_records(records, line), line)
    if len(records) == 1:
        return Array([infer_cell(text, quoted) for text, quoted in records[0]])
    return table_from_records(records, line)


def table_from_records(records: list[list[Cell]], line: int | None) -> Table:
    header = [text for text, _ in records[0]]
    seen: set[str] = set()
    for name in header:
        if name in seen:
            raise LynxTypeError(f"duplicate column title '{name}'", line)
        seen.add(name)
    ncols = len(header)
    columns: dict[str, list[Type]] = {name: [] for name in header}
    for row_idx, row in enumerate(records[1:], start=1):
        if len(row) > ncols:
            raise LynxError(
                f"row {row_idx + 1} has {len(row)} values but the header declares {ncols} columns",
                line,
            )
        for col_idx, name in enumerate(header):
            if col_idx < len(row):
                columns[name].append(infer_cell(*row[col_idx]))
            else:
                columns[name].append(Void())
    return Table([(name, columns[name]) for name in header], line)


# ---------------------------------------------------------------------------
# write
# ---------------------------------------------------------------------------


def write_csv(value: Type, formats_to: str, line: int | None) -> str:
    if isinstance(value, Array):
        if not value.value:
            return ""
        return _csv_line([csv_cell(item, line) for item in value.value])
    if isinstance(value, Table):
        if not value.columns:
            raise LynxError("cannot write a table with no columns to .csv", line)
        if value.nrows == 0:
            raise LynxError("cannot write a table with no rows to .csv", line)
        names = list(value.columns)
        header = _csv_line([csv_cell(Text(name), line) for name in names])
        rows = [_csv_line([csv_cell(value.columns[name][i], line) for name in names]) for i in range(value.nrows)]
        return header + "\n" + "\n".join(rows) + "\n"
    if isinstance(value, Graph):
        rows = [",".join(GRAPH_SCHEMA)]
        for node_id, node_value in value.nodes.items():
            rows.append(_csv_line(["node", csv_cell(Text(node_id), line), "", _graph_cell(node_value, line)]))
        for (source, target), label in value.edges.items():
            rows.append(
                _csv_line(
                    [
                        "edge",
                        csv_cell(Text(source), line),
                        csv_cell(Text(target), line),
                        _graph_cell(label, line),
                    ]
                )
            )
        return "\n".join(rows) + "\n"
    raise LynxTypeError(f"a value of type {value.type_name()} writes to {formats_to}, not .csv", line)


def _graph_cell(value: Type, line: int | None) -> str:
    # A graph value or label cell: scalars serialize like any csv cell, arrays
    # as a `(...)` cell, Text that could be mistaken for an array is escaped.
    if isinstance(value, Array):
        try:
            return csv_cell(Text(write_array_cell(value)), line)
        except LynxTypeError as error:
            raise LynxTypeError(error.message, line) from error
    if isinstance(value, (Map, Table, Graph)):
        raise LynxTypeError(
            f"cannot write {value.type_name()} values in a .csv; only scalars and arrays are supported",
            line,
        )
    if isinstance(value, Text):
        return csv_cell(Text(escape_text(value.value)), line)
    return csv_cell(value, line)


def _csv_line(cells: list[str]) -> str:
    return ",".join(cells)


def csv_cell(value: Type, line: int | None) -> str:
    if isinstance(value, Void):
        return "void"
    if isinstance(value, Boolean):
        return "true" if value.value else "false"
    if isinstance(value, Number):
        if not math.isfinite(value.value):
            raise LynxError("cannot write infinity or NaN to a .csv", line)
        return str(value)
    if isinstance(value, Text):
        text = value.value
        if (
            not text.strip()
            or any(ch in text for ch in ',"\r\n')
            or text in ("true", "false", "void")
            or parse_exact_number(text) is not None
        ):
            return '"' + text.replace('"', '""') + '"'
        return text
    raise LynxTypeError(
        f"cannot write {value.type_name()} values in a .csv; only scalars (number, text, boolean, void) are supported",
        line,
    )
