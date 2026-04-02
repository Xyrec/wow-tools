#!/usr/bin/env bash
# ============================================================================
# rust-gate.sh — Quality gate: blocks task completion unless code is sound
# ============================================================================
# Triggered by the "Stop" hook. Exit 2 forces Claude to keep working.
# Runs cargo check + cargo test (tests are optional via env var).
# ============================================================================

set -uo pipefail

# Skip all checks if no Cargo.toml exists (scaffold/template repo)
if [ ! -f Cargo.toml ]; then
  echo "✓ No Cargo.toml found — skipping gate checks (not a Rust project yet)."
  exit 0
fi

RUN_TESTS="${RUST_GATE_TESTS:-true}"       # set to "false" to skip tests
RUN_CLIPPY="${RUST_GATE_CLIPPY:-false}"     # set to "true" to enforce clippy
RUN_FMT="${RUST_GATE_FMT:-false}"           # set to "true" to enforce formatting

FAILURES=()

# ---------------------------------------------------------------------------
# Stage 1: Compilation
# ---------------------------------------------------------------------------
echo "🔍 Gate check: compilation..."
if ! cargo check --quiet 2>/dev/null; then
  FAILURES+=("compilation")
fi

# ---------------------------------------------------------------------------
# Stage 2: Tests (optional)
# ---------------------------------------------------------------------------
if [ "$RUN_TESTS" = "true" ]; then
  echo "🔍 Gate check: tests..."
  if ! cargo test --quiet 2>/dev/null; then
    FAILURES+=("tests")
  fi
fi

# ---------------------------------------------------------------------------
# Stage 3: Clippy (optional)
# ---------------------------------------------------------------------------
if [ "$RUN_CLIPPY" = "true" ]; then
  echo "🔍 Gate check: clippy..."
  if ! cargo clippy --all-targets --all-features --quiet -- -D warnings 2>/dev/null; then
    FAILURES+=("clippy")
  fi
fi

# ---------------------------------------------------------------------------
# Stage 4: Formatting (optional)
# ---------------------------------------------------------------------------
if [ "$RUN_FMT" = "true" ]; then
  echo "🔍 Gate check: formatting..."
  if ! cargo fmt -- --check 2>/dev/null; then
    FAILURES+=("formatting")
  fi
fi

# ---------------------------------------------------------------------------
# Verdict
# ---------------------------------------------------------------------------
if [ ${#FAILURES[@]} -eq 0 ]; then
  echo "✓ All gate checks passed. Task may complete."
  exit 0
else
  {
    echo "✗ Gate blocked — the following checks failed: ${FAILURES[*]}"
    echo ""
    echo "Run the relevant commands to see details:"
    for f in "${FAILURES[@]}"; do
      case "$f" in
        compilation) echo "  → cargo check" ;;
        tests)       echo "  → cargo test" ;;
        clippy)      echo "  → cargo clippy --all-targets --all-features -- -D warnings" ;;
        formatting)  echo "  → cargo fmt -- --check" ;;
      esac
    done
    echo ""
    echo "Fix all issues before finishing this task."
  } >&2
  exit 2
fi
