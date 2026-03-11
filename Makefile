.PHONY: install lint format test ci

install:
	pip install -e .[dev]

lint:
	ruff check .
	black --check .

format:
	black .
	ruff check --fix .

test:
	pytest

ci: lint test
