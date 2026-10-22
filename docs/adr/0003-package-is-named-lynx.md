# 0003. The Python package is named `lynx`

Status: accepted

## Context

The code lived in a top-level package called `src`, and `pyproject.toml` listed `packages = ["src"]`, which only includes that one directory, not `src.core`, `src.runtime`, `src.types` and so on. A normal (non-editable) install or a built wheel therefore contained only `src/__init__.py` and `src/main.py`, and the `lynx` command crashed with `ModuleNotFoundError: No module named 'src.core'`. Editable installs and CI (`pip install -e`) hid it. A top-level package named `src` would also collide with any other project using that name in the same environment.

## Decision

- The package is renamed `src` → `lynx` (`lynx.main:main` is the entry point, `python -m lynx.main` runs a file).
- `pyproject.toml` uses `[tool.setuptools.packages.find] include = ["lynx*"]`, so subpackages are discovered.
- Every package directory has an `__init__.py` (`lynx/errors/` was missing one). Discovery silently skips directories without it, so `tests/test_packaging.py` fails if one goes missing.
- CI has a `package` job that builds a wheel, installs it into a clean venv and runs `lynx` from outside the repo.

## Consequences

- A normal `pip install .` / wheel works.
- Anything that imported `src.…` must now import `lynx.…`. The sibling `Lynx_Notebook` project imports `src.main` and `src.runtime.environment` and needs updating.
- Existing editable installs must be refreshed with `pip install -e .`; the old `lynx` script still points at `src.main`.
- Large mechanical diff (imports in every module and test); open branches will need a rebase.
