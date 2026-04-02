.PHONY: build release lint format check fix resto ele elemental prot protection prot-paladin

EDITOR := $(or $(shell which cursor 2>/dev/null),$(shell which code 2>/dev/null),notepad)

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

resto:
	$(EDITOR) . data/resto.json

ele elemental:
	$(EDITOR) . data/elemental.json

prot protection prot-paladin:
	$(EDITOR) . data/prot-paladin.json
