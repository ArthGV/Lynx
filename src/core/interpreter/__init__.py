"""Dispatch surface for the interpreter.

`execute`/`evaluate` and their shared helpers live in `_base.py`; statement- and
expression-side helpers in `statements.py`/`expressions.py`, operator dispatch
in `operators.py`. This module just re-exports the walking entry points so
`from src.core.interpreter import execute, ...` keeps working.
"""

from src.core.interpreter._base import (
    _Return,
    _Skip,
    _Stop,
    evaluate,
    evaluate_key,
    evaluate_table_key,
    execute,
    is_range,
)