.PHONY: lint fmt typecheck test check

lint:
	ruff check src/ tests/

fmt:
	ruff format src/ tests/
	ruff check --fix src/ tests/

typecheck:
	mypy --strict src/

test:
	python -m pytest

check: lint typecheck test
