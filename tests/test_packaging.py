"""Guards the package layout that a built wheel depends on.

setuptools' package discovery only picks up directories that have an
`__init__.py`. A directory without one is silently left out of the wheel, so
`lynx` would work from a checkout and crash after a normal install.
"""

from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1] / "lynx"


def test_every_package_directory_has_an_init():
    missing = [
        str(directory.relative_to(PACKAGE.parent))
        for directory in [PACKAGE, *PACKAGE.rglob("*")]
        if directory.is_dir()
        and directory.name != "__pycache__"
        and any(directory.glob("*.py"))
        and not (directory / "__init__.py").exists()
    ]
    assert missing == []
