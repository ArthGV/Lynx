"""File I/O: read and write .txt, .csv and .yaml files.

This module dispatches on the file extension and does the byte-level work
(UTF-8, no newline translation, clean errors); the formats themselves live in
`lynx/core/formats/`. The module is imported at the bottom of
interpreter/_base.py so the interpreter can reach it without an import cycle.
"""

from pathlib import Path

from lynx.core.formats.csv_io import read_csv, write_csv
from lynx.core.formats.yaml_io import read_yaml, write_yaml
from lynx.errors.errors import LynxError, LynxTypeError
from lynx.types.array import Array
from lynx.types.base_type import Type
from lynx.types.graph import Graph
from lynx.types.map import Map
from lynx.types.simple_type import Boolean, Number, Text, Void
from lynx.types.table import Table

SUPPORTED = {".txt", ".csv", ".yaml"}


def read(path: str, line: int | None = None) -> Type:
    """Read a file and return a lynx Value."""
    ext = Path(path).suffix
    if ext not in SUPPORTED:
        raise LynxError(f"unsupported file format '{ext}', use .txt, .csv or .yaml", line)
    try:
        raw = Path(path).read_bytes()
    except FileNotFoundError:
        raise LynxError(f"cannot read '{path}': file not found", line)
    except IsADirectoryError:
        raise LynxError(f"cannot read '{path}': Is a directory", line)
    except OSError as error:
        raise LynxError(f"cannot read '{path}': {error.strerror}", line)
    # csv and yaml may start with a byte-order mark; txt is read exactly as it is.
    try:
        content = raw.decode("utf-8" if ext == ".txt" else "utf-8-sig")
    except UnicodeDecodeError:
        raise LynxError(f"cannot read '{path}': the file is not valid UTF-8", line)
    if ext == ".txt":
        return Text(content)
    if ext == ".csv":
        return read_csv(content, line)
    return read_yaml(content, line)


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
        content = write_csv(value, _formats_to(value), line)
    else:
        content = write_yaml(value, _formats_to(value), line)
    if ext != ".txt" and content.startswith("\ufeff"):
        content = "\ufeff" + content  # the reader drops one BOM; keep the data's own
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content.encode("utf-8"))
    except IsADirectoryError:
        raise LynxError(f"cannot write '{path.value}': Is a directory", line)
    except OSError as error:
        raise LynxError(f"cannot write '{path.value}': {error.strerror}", line)


def _formats_to(value: Type) -> str:
    """The extension a value of this type is written to, for error messages."""
    if isinstance(value, (Array, Table, Graph)):
        return ".csv"
    if isinstance(value, Map):
        return ".yaml"
    return ".txt"


def _write_txt(value: Type, ext: str, line: int | None) -> str:
    if isinstance(value, (Number, Boolean, Void)):
        return str(value)
    if isinstance(value, Text):
        return value.value
    raise LynxTypeError(
        f"a value of type {value.type_name()} writes to {_formats_to(value)}, not .txt",
        line,
    )
