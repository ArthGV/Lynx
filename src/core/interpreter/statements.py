"""Statement-side mutation helpers.

`execute` in `_base.py` dispatches statements; the two mutations that have
enough standalone logic to matter — `append_to` for `<:`/`>:` and `assign_item`
for `name path: value` — live here. They are imported back by `_base`, which is
why their imports from it come from the partially-loaded module's
already-defined functions only.
"""

from typing import Any

from src.core.interpreter._base import evaluate, is_range
from src.core.interpreter.expressions import get_element, slice_assign, table_cells
from src.errors.errors import LynxError, LynxTypeError
from src.runtime import values
from src.runtime.environment import Environment


def append_to(base: str, value_node: Any, front: bool, line: int | None, env: Environment) -> values.Type:
    # `my_arr <: x` appends at the end; `my_arr >: x` at the front. An Array x
    # splices its elements, anything else appends as a single element. Returns
    # the (same, now mutated) array so it can be printed or assigned.
    container = env.get(base, line)
    if not isinstance(container, values.Array):
        raise LynxTypeError(
            f"cannot {'prepend' if front else 'append'} onto a {container.type_name()}", line
        )
    added = evaluate(value_node, env)
    items = added.value if isinstance(added, values.Array) else [added]
    if front:
        container.value[0:0] = items
    else:
        container.value.extend(items)
    return container


def assign_item(base: str, steps: list[Any], value_node: Any, line: int | None, env: Environment) -> None:
    # `a 1, 0: 5` — walk the deref path to the innermost container, then set.
    container = env.get(base, line)
    for step in steps[:-1]:
        if is_range(step):
            raise LynxError("range slicing is only supported for the last index", line)
        container = get_element(container, step, line, env)
    if is_range(steps[-1]):
        slice_assign(container, steps[-1], value_node, line, env)
        return
    key = evaluate(steps[-1], env)
    if isinstance(container, values.Table):
        # Column assignment only makes sense as a single step, whole-column.
        if len(steps) != 1:
            raise LynxTypeError(
                f"table assignment sets a whole column, got {len(steps)} access steps", line
            )
        if not isinstance(key, values.Text):
            raise LynxTypeError(
                f"table column name must be text, got {key.type_name()}", line
            )
        container.set_column(key.value, table_cells(value_node, line, env))
        return
    new_value = evaluate(value_node, env)
    if isinstance(container, values.Array):
        if not isinstance(key, values.Number):
            raise LynxTypeError(
                f"array index must be a number, got {key.type_name()}", line
            )
        idx = key.value
        if not isinstance(idx, int) or idx < 0 or idx >= len(container.value):
            raise LynxError(
                f"index {idx} out of range for an array of length {len(container.value)}", line
            )
        container.value[idx] = new_value
        return
    if isinstance(container, values.Map):
        if not isinstance(key, values.SimpleType):
            raise LynxTypeError(
                f"map key must be a simple type, got {key.type_name()}", line
            )
        container.set_item(key, new_value)
        return
    if isinstance(container, values.Text):
        if not isinstance(key, values.Number):
            raise LynxTypeError(
                f"text index must be a number, got {key.type_name()}", line
            )
        idx = key.value
        if not isinstance(idx, int) or idx < 0 or idx >= len(container.value):
            raise LynxError(
                f"index {idx} out of range for text of length {len(container.value)}", line
            )
        if not isinstance(new_value, values.Text):
            raise LynxTypeError(
                f"text index assignment needs a text, got {new_value.type_name()}", line
            )
        if len(new_value.value) != 1:
            raise LynxError(
                f"text index assignment needs exactly one character, got {len(new_value.value)}", line
            )
        chars = list(container.value)
        chars[idx] = new_value.value
        container.value = "".join(chars)
        return
    raise LynxTypeError(f"cannot assign into a {container.type_name()}", line)