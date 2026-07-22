#!/usr/bin/env python3
"""Extract WA custom-code snippets into lintable .lua files (spec §6)."""
import json
import pathlib
import re
import subprocess
import sys

# NOTE: custom_hide is an option string ("timed"/"custom"), not code — excluded.
CODE_KEYS = {"custom", "customDuration", "customName", "customIcon", "customTexture",
             "customStacks", "customVariables", "customText", "customTriggerLogic"}
# fields whose value is a Lua EXPRESSION (table literal etc.), not statements
EXPR_KEYS = {"customVariables"}


def _walk(node, path, out):
    if isinstance(node, dict):
        for key, value in node.items():
            p = f"{path}.{key}" if path else str(key)
            if isinstance(value, str) and (key in CODE_KEYS or key.endswith("_custom")) \
                    and value.strip():
                out.append((p, value))
            else:
                _walk(value, p, out)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            _walk(v, f"{path}[{i}]", out)


def extract_snippets(displays: dict) -> list:
    snippets = []
    for aura_id, aura in displays.items():
        found = []
        _walk({"triggers": aura.get("triggers", {}),
               "actions": aura.get("actions", {}),
               "customText": aura.get("customText", "")}, "", found)
        for slot, code in found:
            snippets.append({"aura": aura_id, "slot": slot, "code": code})
    return snippets


def wrap(code: str, slot: str = "") -> str:
    header = "local aura_env, WeakAuras = ...\n"
    is_expr = re.match(r"^\s*function\b", code) or slot.split(".")[-1] in EXPR_KEYS
    if is_expr:
        return header + "local _ = " + code + "\n"
    return header + code + "\n"


def main() -> int:
    out_dir = pathlib.Path("tmp/snippets")
    args = sys.argv[1:]
    if "-o" in args:
        i = args.index("-o"); out_dir = pathlib.Path(args[i + 1]); del args[i:i + 2]
    if args:
        displays = json.loads(pathlib.Path(args[0]).read_text())
    else:
        repo = pathlib.Path(__file__).resolve().parents[2]
        proc = subprocess.run([str(repo / "tools" / "wa"), "dump-displays"],
                              capture_output=True, text=True, check=True)
        displays = json.loads(proc.stdout)
    out_dir.mkdir(parents=True, exist_ok=True)
    snippets = extract_snippets(displays)
    for i, s in enumerate(snippets):
        safe = re.sub(r"[^A-Za-z0-9._-]+", "_", f'{s["aura"]}--{s["slot"]}')
        (out_dir / f"{i:03d}--{safe}.lua").write_text(wrap(s["code"], s["slot"]))
    print(f"{len(snippets)} snippets -> {out_dir}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
