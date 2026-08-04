"""Variable scopes.

A scope holds its own names and defers to its parent for the rest, so nested
scopes (functions, blocks, classes) fall out naturally once we add them.
"""

from src.errors import LynxNameError


class Environment:
    def __init__(self, parent=None):
        self.values = {}
        self.parent = parent

    def get(self, name, line=None):
        if name in self.values:
            return self.values[name]
        if self.parent is not None:
            return self.parent.get(name, line)
        raise LynxNameError(f"'{name}' is not defined", line)

    def set(self, name, value):
        self.values[name] = value

    def child(self):
        return Environment(self)
