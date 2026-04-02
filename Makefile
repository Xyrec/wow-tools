.PHONY: build release lint format check fix resto ele elemental prot protection prot-paladin check-resto check-ele check-prot crit-cap lookup compare

EDITOR := $(or $(shell which cursor 2>/dev/null),$(shell which code 2>/dev/null),notepad)
BIN := powershell -Command "& .\target\release\wow-tools.exe

build:
	cargo build

release:
	cargo build --release

lint:
	cargo clippy --all-targets --all-features

format:
	cargo fmt

check:
	cargo check

fix:
	cargo fmt
	cargo clippy --fix --allow-dirty --allow-staged

# --- Tool commands (run via release binary) ---

check-resto:
	$(BIN) check --spec resto"

check-ele:
	$(BIN) check --spec ele"

check-prot:
	$(BIN) check --spec prot"

crit-cap:
	$(BIN) find-stat data/prot-paladin.json --stat defense --target 490 --source easy"

lookup:
	$(BIN) lookup $(ARGS)"

compare:
	$(BIN) lookup --compare $(ARGS)"

# --- Editor shortcuts ---

resto:
	$(EDITOR) . data/resto.json

ele elemental:
	$(EDITOR) . data/elemental.json

prot protection prot-paladin:
	$(EDITOR) . data/prot-paladin.json
