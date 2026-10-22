.PHONY: lint fmt typecheck test check

lint:
	ruff check lynx/ tests/

fmt:
	ruff format lynx/ tests/
	ruff check --fix lynx/ tests/

typecheck:
	mypy --strict lynx/

test:
	python -m pytest

check: lint typecheck test
