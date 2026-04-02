# Rust + AI Agent Scaffold

**Turn Rust's compiler into a real-time feedback loop for AI coding agents.**

This scaffold configures [Claude Code](https://code.claude.com) (or any hook-compatible AI agent) to receive automatic, token-efficient compilation feedback after every file edit.

---

## The problem this solves

When you have hot-reload / auto-compile running (bacon, cargo-watch, etc.), **the agent has no idea it exists**. It can't see your terminal. It doesn't know compilation takes 2–15 seconds. It doesn't know whether its last edit broke anything.

Without explicit feedback, agents either:
- Never check compilation and build on broken foundations
- Run `cargo check` manually at arbitrary times, wasting tokens
- Declare tasks "done" with code that doesn't compile

**This scaffold solves it** with a PostToolUse hook that automatically runs `cargo check` after every file write and feeds back tiered results:

| Result | Agent sees | Tokens | Exit code |
|--------|-----------|--------|-----------|
| Success | `✓ cargo check passed` | Minimal | 0 (continue) |
| Warnings | Summary + warning text | Low | 0 (continue) |
| Failure | Truncated error output | Medium | 2 (blocked) |

Exit code 2 is the key — it **blocks the agent from proceeding** until errors are fixed.

---

## What's in the box

```
.claude/
  settings.json                  # Hook configuration (PostToolUse + Stop gate)
  settings.local.json.example    # Per-developer overrides template
  hooks/
    rust-check.sh                # Compilation feedback (tiered, token-efficient)
    rust-gate.sh                 # Quality gate (blocks task completion)
CLAUDE.md                        # Project rules for Rust development
.gitignore                       # Ignores local settings, targets
```

---

## Quick start

1. **Copy the scaffold into your Rust project:**

   ```bash
   cp -r rust-claude-scaffold/.claude /path/to/your/project/
   cp rust-claude-scaffold/CLAUDE.md /path/to/your/project/
   ```

2. **Make hooks executable (Linux/macOS only):**

   ```bash
   chmod +x .claude/hooks/*.sh
   ```

3. **Edit `CLAUDE.md`** to match your project's conventions, architecture, and dependencies.

4. **Launch Claude Code:**

   ```bash
   claude
   ```

   Every file edit will now trigger automatic compilation feedback.

---

## Configuration

### Environment variables

Override behavior without editing scripts:

| Variable | Default | Description |
|----------|---------|-------------|
| `RUST_CHECK_MAX_ERRORS` | `30` | Max error lines fed to agent on failure |
| `RUST_CHECK_MAX_WARNINGS` | `10` | Max warning lines shown |
| `RUST_CHECK_CMD` | `cargo check` | Override with `cargo clippy` for stricter feedback |
| `RUST_CHECK_PACKAGE` | *(empty)* | Scope checks to a single workspace crate |
| `RUST_GATE_TESTS` | `true` | Run `cargo test` in quality gate |
| `RUST_GATE_CLIPPY` | `false` | Enforce clippy in quality gate |
| `RUST_GATE_FMT` | `false` | Enforce formatting in quality gate |

Set these in `.claude/settings.local.json` (gitignored) or export in your shell.

### Switching to clippy as the primary checker

If you want the agent to receive clippy diagnostics (not just compiler errors) on every edit:

```bash
export RUST_CHECK_CMD="cargo clippy"
```

Or set it in `.claude/settings.local.json`.

> **Warning:** Clippy is slower than `cargo check`. On large projects, this adds latency to every edit cycle. Consider using clippy only in the Stop gate instead.

### Using with Bacon (optional, for human monitoring)

If you also want a background compiler for your own terminal:

```bash
cargo install bacon
bacon --headless
```

This doesn't conflict with the hooks — they serve different audiences. Bacon is for your eyes, hooks are for the agent.

---

## How the hooks work

### PostToolUse → `rust-check.sh`

Fires after Claude uses `Write`, `Edit`, or `MultiEdit` tools (i.e., any file modification). Runs `cargo check --message-format=short` and returns:

- **Exit 0 + stdout** on success → Claude sees "✓ passed" and continues
- **Exit 2 + stderr** on failure → Claude is **blocked**, sees truncated errors, must fix before proceeding

The `--message-format=short` flag is critical — it produces compact one-line-per-error output instead of Rust's verbose default, keeping token costs low.

### Stop → `rust-gate.sh`

Fires when Claude considers its task complete. Runs up to 4 checks (configurable):

1. `cargo check` (always)
2. `cargo test` (default on)
3. `cargo clippy` (default off)
4. `cargo fmt --check` (default off)

**Exit 2 forces Claude to continue working** rather than declaring "done" — it cannot finish a task with broken compilation or failing tests.

Both hooks skip cleanly when `Cargo.toml` is not present, so this scaffold can be committed to template repos without causing issues.

---

## Design decisions and trade-offs

**Why PostToolUse instead of Bacon + FileChanged?**
The FileChanged approach has a timing problem: Bacon needs time to detect changes and recompile. If the agent edits a second file before Bacon finishes, it receives stale diagnostics. PostToolUse is synchronous with the edit — feedback always reflects the current state.

**Why truncated errors instead of full output?**
Token economy. A cascading Rust error (e.g., changing a core type) can produce 200+ error lines. The agent only needs the first few to identify the root cause. 30 lines is enough for ~95% of cases.

---

## Limitations

- **Large workspace compilation is slow.** `cargo check` on a 100-crate workspace can take 10+ seconds. For large projects, set `RUST_CHECK_PACKAGE` to scope checks to the crate the agent is working on.

---

## Windows compatibility

This scaffold is cross-platform. Claude Code on Windows uses Git Bash, so all bash scripts run correctly. A few things are handled automatically:

- **Line endings.** The included `.gitattributes` forces `*.sh` files to LF line endings. Without this, Git's default `core.autocrlf=true` on Windows adds `\r` to shebangs and breaks script execution.
- **File permissions.** `chmod +x` is a no-op on Windows, but this doesn't matter — the hooks invoke scripts via `bash .claude/hooks/rust-check.sh` (explicit interpreter), not via direct execution.

**No changes needed** — just clone/unzip and use as documented.

---

## Further reading

- [Claude Code Hooks Reference](https://code.claude.com/docs/en/hooks)
- [Bacon — Background Rust Code Checker](https://github.com/Canop/bacon)
- [cargo-mcp — MCP Server for Cargo](https://github.com/jbr/cargo-mcp)
