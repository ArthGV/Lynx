.PHONY: lint fmt typecheck test check lexers

lint:
	ruff check src/ tests/

fmt:
	ruff format src/ tests/
	ruff check --fix src/ tests/

typecheck:
	mypy --strict src/

test:
	python -m pytest

# Build the optional Rust lexer. The suite skips native-vs-pure parity tests
# when this hasn't been run; the built binary also needs `rust/lexer`'s
# `target/` path (or LYNX_LEXER_PATH / PATH) for the test to pick it up.
lexers:
	cargo build --release --manifest-path rust/lexer/Cargo.toml

check: lint typecheck test
