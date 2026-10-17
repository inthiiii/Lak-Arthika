.PHONY: install run test lint format typecheck check stress-build stress-status

install:
	uv sync --all-groups
	uv run pre-commit install

run:
	uv run uvicorn lak_arthika.api:app --reload

test:
	uv run pytest

lint:
	uv run ruff check .

format:
	uv run ruff check --fix .
	uv run ruff format .

typecheck:
	uv run mypy src

check:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy src
	uv run pytest

stress-build:
	uv run lak-arthika stress build

stress-status:
	uv run lak-arthika stress status
