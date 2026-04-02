#!/usr/bin/env bash
# ============================================================================
# rust-check.sh — Compilation feedback bridge for Claude Code
# ============================================================================
# This script is triggered by Claude Code hooks after every file write/edit.
# It runs `cargo check` and returns tiered, token-efficient feedback:
#
#   ✓ Success  → single line, minimal context cost
#   ⚠ Warnings → compact summary + warning text
#   ✗ Failure  → truncated errors, exit 2 blocks the agent
#
# Exit codes:
#   0 = success (stdout becomes agent context)
#   2 = blocking error (stderr fed to agent, action blocked)
# ============================================================================

set -euo pipefail

# Skip if no Cargo.toml exists (scaffold/template repo)
if [ ! -f Cargo.toml ]; then
  echo "✓ No Cargo.toml found — skipping check (not a Rust project yet)."
  exit 0
fi

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MAX_ERROR_LINES="${RUST_CHECK_MAX_ERRORS:-30}"      # max error lines to feed back
MAX_WARNING_LINES="${RUST_CHECK_MAX_WARNINGS:-10}"   # max warning lines to show
CHECK_CMD="${RUST_CHECK_CMD:-cargo check}"           # override with clippy if desired
MESSAGE_FMT="--message-format=short"                 # compact one-line-per-error

# Optional: scope to a specific workspace crate
# Set RUST_CHECK_PACKAGE in your environment or .claude/settings.local.json
if [ -n "${RUST_CHECK_PACKAGE:-}" ]; then
  CHECK_CMD="$CHECK_CMD -p $RUST_CHECK_PACKAGE"
fi

# ---------------------------------------------------------------------------
# Run cargo check
# ---------------------------------------------------------------------------
OUTPUT=$($CHECK_CMD $MESSAGE_FMT 2>&1) || true
EXIT_CODE=${PIPESTATUS[0]:-$?}

# Re-capture exit code properly since `|| true` masks it
if $CHECK_CMD $MESSAGE_FMT > /dev/null 2>&1; then
  COMPILED=true
else
  COMPILED=false
fi

# ---------------------------------------------------------------------------
# Parse and report
# ---------------------------------------------------------------------------
if [ "$COMPILED" = true ]; then
  # Check for warnings in successful compilation
  WARNING_COUNT=$(echo "$OUTPUT" | grep -c "warning\[" || true)

  if [ "$WARNING_COUNT" -gt 0 ]; then
    echo "⚠ cargo check passed with $WARNING_COUNT warning(s):"
    echo ""
    echo "$OUTPUT" | grep "warning" | head -"$MAX_WARNING_LINES"
    if [ "$WARNING_COUNT" -gt "$MAX_WARNING_LINES" ]; then
      echo "  ... and $((WARNING_COUNT - MAX_WARNING_LINES)) more warnings (run \`cargo check\` to see all)"
    fi
  else
    echo "✓ cargo check passed — no errors, no warnings"
  fi
  exit 0

else
  # Compilation failed — extract error lines
  ERROR_COUNT=$(echo "$OUTPUT" | grep -c "^error" || true)

  # Feed errors to stderr (Claude sees this on exit 2)
  {
    echo "✗ cargo check failed — $ERROR_COUNT error(s):"
    echo ""
    echo "$OUTPUT" | grep -E "^error|^\s*-->" | head -"$MAX_ERROR_LINES"
    echo ""
    TOTAL_LINES=$(echo "$OUTPUT" | grep -c "^error" || true)
    if [ "$TOTAL_LINES" -gt "$MAX_ERROR_LINES" ]; then
      echo "  ... truncated ($TOTAL_LINES total errors). Run \`cargo check\` for full output."
    fi
    echo ""
    echo "Fix these compilation errors before continuing."
  } >&2

  exit 2
fi
