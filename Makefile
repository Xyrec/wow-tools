.PHONY: build release lint format check-code fix check scrape crit-cap find-stat lookup compare edit

EDITOR := $(or $(shell which cursor 2>/dev/null),$(shell which code 2>/dev/null),notepad)
BIN := powershell -Command "& .\target\release\wow-tools.exe

# --- Build & dev ---

build:
	cargo build

release:
	cargo build --release

lint:
	cargo clippy --all-targets --all-features

format:
	cargo fmt

check-code:
	cargo check

fix:
	cargo fmt
	cargo clippy --fix --allow-dirty --allow-staged

# --- Tool commands (require SPEC= for spec-specific ones) ---

check:
	$(BIN) check --spec $(SPEC)"

scrape:
	$(BIN) scrape $(SPEC)"

crit-cap:
	$(BIN) find-stat data/$(SPEC).json --stat defense --target 490 --source easy"

find-stat:
	$(BIN) find-stat data/$(SPEC).json --stat $(STAT) --target $(TARGET) --source $(or $(SOURCE),easy)"

lookup:
	$(BIN) lookup $(ARGS)"

compare:
	$(BIN) lookup --compare $(ARGS)"

# --- Editor shortcut ---

edit:
	$(EDITOR) . data/$(SPEC).json
