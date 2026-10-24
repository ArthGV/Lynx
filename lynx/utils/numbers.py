"""Reading numbers from text, shared by csv, yaml and `Text.number()`.

lynx has no infinity or NaN, so `inf`, `nan` and friends are ordinary text.
"""

import math
import re

# Plain decimal notation, ASCII digits only: no `inf`/`nan`, no `1_000`, no
# surrounding spaces, no non-ASCII digits (all of which `float()` would take).
_DECIMAL = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\Z")


def parse_exact_number(text: str) -> int | float | None:
    """`text` as a number, but only when printing that number gives `text`
    back exactly. `007`, `1.50`, `1e3`, `-0` and `inf` stay text, so a value
    written to a file reads back as the same thing."""
    if not _DECIMAL.match(text):
        return None
    value: int | float = float(text)
    if not math.isfinite(value):
        return None
    if value % 1 == 0:
        value = int(value)
    return value if str(value) == text else None
