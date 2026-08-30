"""Command-line entry point: `lynx <file.lx>`."""

import argparse
import sys

from src import __version__
from src.lexer import tokenize
from src.parser import Parser
from src.interpreter import execute, _Return
from src.environment import Environment
from src.errors import LynxError, LynxInputError


def run(source, env=None):
    """Run lynx source. Raises LynxError on a program error."""
    tree = Parser(tokenize(source)).parse()
    try:
        execute(tree, env or Environment())
    except _Return:
        raise LynxInputError("return outside of a function")


def main():
    parser = argparse.ArgumentParser(prog="lynx", description="Run a lynx program.")
    parser.add_argument("file", metavar="file.lx", help="lynx source file to run")
    parser.add_argument("--version", action="version", version=f"lynx {__version__}")
    args = parser.parse_args()

    # .lx is the convention, not a requirement — say something, then run anyway.
    if not args.file.endswith(".lx"):
        print(f"warning: {args.file} does not end in .lx", file=sys.stderr)

    with open(args.file) as f:
        source = f.read()

    try:
        run(source)
    except LynxError as error:
        print(error, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
