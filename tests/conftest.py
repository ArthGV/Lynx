"""Shared pytest fixtures.

The golden file-io tests write real files into `programs/io/out/` (they read
them back in the same program, but the files persist across runs). This
autouse fixture resets that directory before and after every test so writes
stay deterministic and the repo is never left dirty.
"""

import shutil
from pathlib import Path

import pytest

OUT = Path(__file__).parent / "programs" / "io" / "out"


@pytest.fixture(autouse=True)
def clean_io_out():
    if OUT.exists():
        shutil.rmtree(OUT)
    yield
    if OUT.exists():
        shutil.rmtree(OUT)
