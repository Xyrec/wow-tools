.PHONY: lint typecheck format check fix character

lint:
	uv run ruff check .

typecheck:
	uv run ty check .

format:
	uv run ruff format .

check: lint typecheck

fix:
	uv run ruff check . --fix
	uv run ruff format .

character:
	notepad data/character.json
