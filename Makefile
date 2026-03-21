.PHONY: lint typecheck ty type types tsc format check fix resto ele elemental prot protection prot-paladin

EDITOR := $(or $(shell which cursor 2>/dev/null),$(shell which code 2>/dev/null),notepad)

lint:
	uv run ruff check .

typecheck ty type types tsc:
	uv run ty check .

format:
	uv run ruff format .

check: lint typecheck

fix:
	uv run ruff check . --fix
	uv run ruff format .

resto:
	$(EDITOR) . data/resto.json

ele elemental:
	$(EDITOR) . data/elemental.json

prot protection prot-paladin:
	$(EDITOR) . data/prot-paladin.json
