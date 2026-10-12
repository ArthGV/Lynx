"""Unit tests for Environment scoping.

`set` declares a name in the current scope (parameters, loop variables, the
catch variable, function definitions). `assign` is plain assignment: it updates
the nearest scope that already holds the name, else creates it locally.
"""

import pytest

from src.errors.errors import LynxNameError
from src.runtime.environment import Environment


def chain(depth):
    """A root scope with `depth` nested children; returns [root, ..., leaf]."""
    scopes = [Environment()]
    for _ in range(depth):
        scopes.append(scopes[-1].child())
    return scopes


def test_assign_updates_the_defining_scope():
    root = Environment()
    root.set("n", 1)
    child = root.child()
    child.assign("n", 2)
    assert root.values["n"] == 2
    assert "n" not in child.values


def test_assign_creates_a_local_when_the_name_is_unknown():
    root = Environment()
    child = root.child()
    child.assign("fresh", 1)
    assert child.values == {"fresh": 1}
    assert "fresh" not in root.values


def test_assign_in_the_same_scope_updates_it():
    env = Environment()
    env.assign("x", 1)
    env.assign("x", 2)
    assert env.values == {"x": 2}


def test_assign_prefers_the_nearest_binding():
    root, middle, leaf = chain(2)
    root.set("v", "root")
    middle.set("v", "middle")
    leaf.assign("v", "changed")
    assert root.values["v"] == "root"
    assert middle.values["v"] == "changed"
    assert "v" not in leaf.values


def test_assign_reaches_a_middle_scope_through_a_longer_chain():
    scopes = chain(4)
    scopes[2].set("m", 0)
    scopes[4].assign("m", 1)
    assert scopes[2].values["m"] == 1
    assert all("m" not in s.values for i, s in enumerate(scopes) if i != 2)


def test_set_always_declares_locally_even_if_an_outer_name_exists():
    root = Environment()
    root.set("x", "outer")
    child = root.child()
    child.set("x", "inner")
    assert root.values["x"] == "outer"
    assert child.get("x") == "inner"


def test_assign_after_a_local_declaration_updates_the_local():
    root = Environment()
    root.set("x", "outer")
    child = root.child()
    child.set("x", "param")
    child.assign("x", "changed")
    assert root.values["x"] == "outer"
    assert child.values["x"] == "changed"


def test_sibling_scopes_do_not_see_each_other():
    root = Environment()
    first, second = root.child(), root.child()
    first.assign("only_first", 1)
    with pytest.raises(LynxNameError):
        second.get("only_first")


def test_assign_walks_a_very_deep_chain_without_recursion():
    scopes = chain(5000)
    scopes[0].set("deep", 0)
    scopes[-1].assign("deep", 1)
    assert scopes[0].values["deep"] == 1


def test_get_and_delete_still_walk_outward():
    root = Environment()
    root.set("x", 1)
    child = root.child()
    assert child.get("x") == 1
    child.delete("x")
    with pytest.raises(LynxNameError):
        root.get("x")
