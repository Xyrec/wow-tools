.PHONY: lint typecheck format check fix resto ele elemental

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

resto:
	notepad data/resto.json

ele elemental:
	notepad data/elemental.json
