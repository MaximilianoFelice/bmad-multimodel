#!/usr/bin/env python3
"""Set up bmad-multimodel in a project. Idempotent; prints every change.

1. mise.toml [tools]: pins acpx and the Claude ACP adapter (skipped without mise.toml).
2. AGENTS.md: the "Launching agents" block, between markers (created if missing).
3. .gitignore: the run log.

Usage: python3 <skill-root>/scripts/setup.py [--project-root DIR] [--check]
--check changes nothing and exits 1 when something is missing.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

TOOLS = {"npm:acpx": "0.22.0", "npm:@agentclientprotocol/claude-agent-acp": "0.95.0"}
BEGIN, END = "<!-- bmad-multimodel:begin -->", "<!-- bmad-multimodel:end -->"
BLOCK = f"""{BEGIN}
## Launching agents

Every subagent launch (BMad implementers, review lenses, critics and any other) follows the `bmad-multimodel` skill: load it before launching or re-engaging a subagent. Role definitions are in `.agents/<skill>.<role>[.<variant>].md`; the model for a role is changed there.
{END}"""
IGNORE = ".agents/runs.jsonl"


def mise_tools(text: str) -> str:
    missing = [k for k in TOOLS if not re.search(rf'^\s*"{re.escape(k)}"\s*=', text, re.MULTILINE)]
    if not missing:
        return text
    lines = "".join(f'"{k}" = "{TOOLS[k]}"\n' for k in missing)
    match = re.search(r"^\[tools\][^\n]*\n", text, re.MULTILINE)
    if not match:
        return text.rstrip("\n") + f"\n\n[tools]\n{lines}"
    nxt = re.search(r"^\[", text[match.end():], re.MULTILINE)
    at = match.end() + (nxt.start() if nxt else len(text) - match.end())
    head = text[:at].rstrip("\n") + "\n"
    return head + lines + ("\n" + text[at:] if text[at:] else "")


def agents_block(text: str) -> str:
    if BEGIN in text and END in text:
        return re.sub(re.escape(BEGIN) + r".*?" + re.escape(END), lambda _: BLOCK, text, flags=re.DOTALL)
    return (text.rstrip("\n") + "\n\n" if text.strip() else "") + BLOCK + "\n"


def gitignore(text: str) -> str:
    if IGNORE in text.splitlines():
        return text
    return (text.rstrip("\n") + "\n" if text.strip() else "") + IGNORE + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Set up bmad-multimodel in a project.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--check", action="store_true", help="report only; exit 1 if anything is missing")
    args = parser.parse_args(argv)
    root = Path(args.project_root).resolve()
    steps = [("mise.toml", mise_tools), ("AGENTS.md", agents_block), (".gitignore", gitignore)]
    pending = []
    for name, change in steps:
        path = root / name
        if name == "mise.toml" and not path.exists():
            print(f"skip   {name}: no mise.toml; install {', '.join(f'{k}@{v}' for k, v in TOOLS.items())} with your tool manager")
            continue
        before = path.read_text(encoding="utf-8") if path.exists() else ""
        after = change(before)
        if after == before:
            print(f"ok     {name}")
            continue
        pending.append(name)
        if not args.check:
            path.write_text(after, encoding="utf-8")
        print(f"{'missing' if args.check else 'wrote '} {name}")
    if pending and not args.check and (root / "mise.toml").exists():
        print("next   run `mise install`")
    return 1 if (args.check and pending) else 0


if __name__ == "__main__":
    sys.exit(main())
