"""Statement-side mutation helpers.

`execute` in `_base.py` dispatches statements; the two mutations that have
enough standalone logic to matter — `append_to` for `<:`/`>:` and `assign_item`
for `name path: value` — live here. They are imported back by `_base`, which is
why their imports from it come from the partially-loaded module's
already-defined functions only.
"""

from typing import Any

from src.core.interpreter._base import evaluate, is_range
from src.core.interpreter.expressions import (
    _slice_bounds,
    _sliced_indices,
    get_element,
    slice_assign,
    table_cells,
)
from src.core.nodes import EdgeCreate, EdgeStep
from src.errors.errors import LynxError, LynxSyntaxError, LynxTypeError
from src.runtime import values
from src.runtime.environment import Environment


def append_to(base: str, value_node: Any, front: bool, line: int | None, env: Environment) -> values.Type:
    # `my_arr <: x` appends at the end; `my_arr >: x` at the front. An Array x
    # splices its elements, anything else appends as a single element. Returns
    # the (same, now mutated) array so it can be printed or assigned.
    container = env.get(base, line)
    if not isinstance(container, values.Array):
        raise LynxTypeError(f"cannot {'prepend' if front else 'append'} onto a {container.type_name()}", line)
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
    if isinstance(container, values.Graph) and _graph_assign(container, steps, value_node, line, env):
        # `g 'x': 42`, `g 'x': -> 'z'(label)` and `g 'a' -> 'b': label` are
        # graph-builtins, handled whole. Any other path falls through to the
        # generic walk below.
        return
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
            raise LynxTypeError(f"table assignment sets a whole column, got {len(steps)} access steps", line)
        if not isinstance(key, values.Text):
            raise LynxTypeError(f"table column name must be text, got {key.type_name()}", line)
        container.set_column(key.value, table_cells(value_node, line, env))
        return
    new_value = evaluate(value_node, env)
    if isinstance(container, values.Array):
        if not isinstance(key, values.Number):
            raise LynxTypeError(f"array index must be a number, got {key.type_name()}", line)
        idx = key.value
        if not isinstance(idx, int) or idx < 0 or idx >= len(container.value):
            raise LynxError(f"index {idx} out of range for an array of length {len(container.value)}", line)
        container.value[idx] = new_value
        return
    if isinstance(container, values.Map):
        if not isinstance(key, values.SimpleType):
            raise LynxTypeError(f"map key must be a simple type, got {key.type_name()}", line)
        container.set_item(key, new_value)
        return
    if isinstance(container, values.Text):
        if not isinstance(key, values.Number):
            raise LynxTypeError(f"text index must be a number, got {key.type_name()}", line)
        idx = key.value
        if not isinstance(idx, int) or idx < 0 or idx >= len(container.value):
            raise LynxError(f"index {idx} out of range for text of length {len(container.value)}", line)
        if not isinstance(new_value, values.Text):
            raise LynxTypeError(f"text index assignment needs a text, got {new_value.type_name()}", line)
        if len(new_value.value) != 1:
            raise LynxError(f"text index assignment needs exactly one character, got {len(new_value.value)}", line)
        chars = list(container.value)
        chars[idx] = new_value.value
        container.value = "".join(chars)
        return
    raise LynxTypeError(f"cannot assign into a {container.type_name()}", line)


def _graph_assign(graph: values.Graph, steps: list[Any], value_node: Any, line: int | None, env: Environment) -> bool:
    """Handle a mutation into a graph. Returns True when the mutation was a
    graph-builtin (node upsert, edge creation, strict label set); False for a
    nested plain path like `g 'cfg' 'k': 7`, which the generic set walks."""
    if isinstance(value_node, EdgeCreate):
        # `g 'from': -> 'to'` / `g 'from': -> 'to'(label)` — create the edge,
        # creating the target node as a by-product. The parenthesized value
        # seeds both the target node and the label.
        if len(steps) != 1 or is_range(steps[0]):
            raise LynxSyntaxError("an edge mutation looks like: g 'from': -> 'to'", line)
        source = _graph_node_id(steps[0], line, env)
        target = _graph_node_id(value_node.target, line, env)
        label: values.Type = values.Void()
        if value_node.value is not None:
            label = evaluate(value_node.value, env)
            if not isinstance(label, values.Text):
                raise LynxTypeError(f"an edge label must be a Text, got {label.type_name()}", line)
        if source == target:
            raise LynxError(f"cannot create an edge from '{source}' to itself", line)
        if source not in graph.nodes:
            raise LynxError(f"cannot create an edge from missing node '{source}'", line)
        if value_node.value is not None:
            # A labelled `-> 'to'(value)` upserts both the target node's value
            # and the edge's label; a bare `-> 'to'` creates the target if it
            # is missing but leaves an existing one's value untouched.
            graph.set_node(target, label)
        else:
            graph.nodes.setdefault(target, values.Void())
        graph.edges[(source, target)] = label
        return True
    if steps and isinstance(steps[-1], EdgeStep):
        # `g 'a' -> 'b': label` — strict: the edge must already exist.
        if len(steps) != 2 or is_range(steps[0]):
            raise LynxSyntaxError("an edge label looks like: g 'a' -> 'b': 'loves'", line)
        source = _graph_node_id(steps[0], line, env)
        target = _graph_node_id(steps[-1].target, line, env)
        label = evaluate(value_node, env)
        if not isinstance(label, values.Text):
            raise LynxTypeError(f"an edge label must be a Text, got {label.type_name()}", line)
        graph.set_edge_label(source, target, label, line)
        return True
    if len(steps) == 1:
        # `g 'x': value` — upsert the node (create it or overwrite its value).
        key = _graph_node_id(steps[0], line, env)
        graph.set_node(key, evaluate(value_node, env))
        return True
    return False


def _graph_node_id(node: Any, line: int | None, env: Environment) -> str:
    value = evaluate(node, env)
    if not isinstance(value, values.Text):
        raise LynxTypeError(f"a graph node id must be a Text, got {value.type_name()}", line)
    return value.value


def _delete_graph(graph: values.Graph, steps: list[Any], line: int | None, env: Environment) -> None:
    if steps and isinstance(steps[-1], EdgeStep):
        if len(steps) != 2:
            raise LynxSyntaxError("a graph edge deletion looks like: del g 'a' -> 'b'", line)
        source = _graph_node_id(steps[0], line, env)
        target = _graph_node_id(steps[-1].target, line, env)
        graph.delete_edge(source, target)
        return
    if len(steps) == 1:
        graph.delete_node(_graph_node_id(steps[0], line, env))
        return
    raise LynxSyntaxError("a graph deletion names a node id or an edge, like: del g 'a'", line)


def delete_item(base: str, steps: list[Any], line: int | None, env: Environment) -> None:
    # `del a 1, 0` / `del m 'k'` / `del t 'col'` — walk the deref path to the
    # innermost container, then remove the last step. With no steps at all the
    # whole variable goes. Range slicing works on the last step only, exactly
    # as in assign_item: a mid-path slice would delete from a throwaway copy.
    if not steps:
        env.delete(base, line)
        return
    container = env.get(base, line)
    # `del g 'x'` drops a node and its incident edges; `del g 'a' -> 'b'`
    # drops one edge. Missing targets are silent no-ops like Map deletion.
    if isinstance(container, values.Graph):
        _delete_graph(container, steps, line, env)
        return
    # A table holds no nested cells to delete below itself, so multi-step
    # paths into one are rejected before the walk: `t 'col'` is a column, and
    # `t 0` is a row, full stop. Without this, `del t 'col' 0` would descend
    # into a column copy and silently mutate nothing.
    if isinstance(container, values.Table) and len(steps) != 1:
        raise LynxTypeError(f"table deletion needs a single column or row, got {len(steps)} access steps", line)
    for step in steps[:-1]:
        if is_range(step):
            raise LynxError("a range slice can only be the last step of a delete path", line)
        container = get_element(container, step, line, env)
    if is_range(steps[-1]):
        if not isinstance(container, values.Array):
            raise LynxTypeError("range slicing is only supported for arrays", line)
        start, end = _slice_bounds(steps[-1], env, line)
        indices = _sliced_indices(start, end)
        worst = max(start, end)
        if worst >= len(container.value):
            which = "start" if start > end else "end"
            raise LynxError(f"range {which} {worst} out of bounds for an array of length {len(container.value)}", line)
        for index in sorted(indices, reverse=True):
            del container.value[index]
        return
    key = evaluate(steps[-1], env)
    if isinstance(container, values.Array):
        if not isinstance(key, values.Number):
            raise LynxTypeError(f"array index must be a number, got {key.type_name()}", line)
        idx = key.value
        if not isinstance(idx, int) or idx < 0 or idx >= len(container.value):
            raise LynxError(f"index {idx} out of range for an array of length {len(container.value)}", line)
        del container.value[idx]
        return
    if isinstance(container, values.Map):
        if not isinstance(key, values.SimpleType):
            raise LynxTypeError(f"map key must be a simple type, got {key.type_name()}", line)
        container.remove_item(key)
        return
    if isinstance(container, values.Table):
        # Column or row deletion only makes sense as a single step; there are
        # no nested cells to delete a level below the table.
        if len(steps) != 1:
            raise LynxTypeError(f"table deletion needs a single column or row, got {len(steps)} access steps", line)
        if isinstance(key, values.Text):
            container.del_column(key.value)
            return
        if isinstance(key, values.Number):
            idx = key.value
            if not isinstance(idx, int) or idx < 0 or idx >= container.nrows:
                raise LynxError(f"index {idx} out of range for a table with {container.nrows} rows", line)
            container.del_row(idx)
            return
        raise LynxTypeError(f"table deletion needs a column name or a row index, got {key.type_name()}", line)
    raise LynxTypeError(f"cannot delete from a {container.type_name()}", line)
