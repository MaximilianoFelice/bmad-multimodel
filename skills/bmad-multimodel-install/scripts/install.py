#!/usr/bin/env python3
"""bmad-multimodel installer: shows the project's state and writes only what it is told.

  install.py status                      roles the installed skills launch, current definitions,
                                         dependencies, the AGENTS.md block, agent CLIs on PATH
  install.py plan  [changes]             prints what apply would change; writes nothing
  install.py apply [changes]             writes exactly that

Changes (repeatable, all optional):
  --define NAME KEY=VALUE...   a role definition .agents/NAME.md; keys: run-agent, model, effort, permission
  --replace                    let --define overwrite an existing definition (otherwise it is kept)
  --deps mise                  declare the dependencies the definitions need in mise.toml
  --agents-block               add the "Launching agents" block to AGENTS.md

Running it again only adds what is missing, so it can be run as often as needed.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tomllib
from pathlib import Path

RUN_AGENTS = ("claude", "antigravity", "codex", "gemini", "opencode")
CLI = {"claude": "claude", "antigravity": "agy", "codex": "codex", "gemini": "gemini", "opencode": "opencode"}
PERMISSIONS = ("approve-all", "approve-reads", "deny-all")
KEYS = ("run-agent", "model", "effort", "permission")
# What each agent needs besides its own CLI. acpx is needed by all of them.
ACPX = ("npm:acpx", "0.22.0")
ADAPTERS = {
    "claude": ("npm:@agentclientprotocol/claude-agent-acp", "0.95.0"),
    "codex": ("npm:@agentclientprotocol/codex-acp", "1.13.1"),
}
BEGIN, END = "<!-- bmad-multimodel:begin -->", "<!-- bmad-multimodel:end -->"
BLOCK = f"""{BEGIN}
## Launching agents

Every subagent launch (BMad implementers, review lenses, critics and any other) follows the `bmad-multimodel` skill: load it before launching or re-engaging a subagent. A role with a definition in `.agents/<skill>.<role>[.<variant>].md` runs on the agent and model it names; a role without one runs as usual.
{END}"""


def parse_front(text: str) -> dict[str, str]:
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    fields = {}
    for line in (match.group(1).splitlines() if match else []):
        if ":" in line:
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip()
    return fields


def roles(root: Path) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for skill_dir in sorted((root / ".agents" / "skills").glob("*/")):
        tables = []
        for path in (skill_dir / "customize.toml", root / "_bmad" / "custom" / f"{skill_dir.name}.toml"):
            if path.exists():
                tables.append(tomllib.loads(path.read_text(encoding="utf-8")).get("workflow", {}))
        names: list[str] = []
        for workflow in tables:
            for key, value in workflow.items():
                if isinstance(value, str) and key.endswith("_handoff") and "subagent" in value.lower():
                    names.append(key[: -len("_handoff")])
                if isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict) and "instruction" in item and (item.get("id") or item.get("code")):
                            names.append(str(item.get("id") or item.get("code")))
        if names:
            found[skill_dir.name] = list(dict.fromkeys(names))
    return found


def definitions(root: Path) -> dict[str, dict[str, str]]:
    out = {}
    for path in sorted((root / ".agents").glob("*.md"), key=lambda p: p.stem):
        fields = parse_front(path.read_text(encoding="utf-8"))
        if "run-agent" in fields:
            out[path.stem] = fields
    return out


def needed_deps(run_agents: set[str]) -> list[tuple[str, str]]:
    if not run_agents:
        return []
    return [ACPX] + [ADAPTERS[a] for a in sorted(run_agents) if a in ADAPTERS]


def mise_add(text: str, deps: list[tuple[str, str]]) -> str:
    missing = [(k, v) for k, v in deps if not re.search(rf'^\s*"{re.escape(k)}"\s*=', text, re.MULTILINE)]
    if not missing:
        return text
    lines = "".join(f'"{k}" = "{v}"\n' for k, v in missing)
    match = re.search(r"^\[tools\][^\n]*\n", text, re.MULTILINE)
    if not match:
        return text.rstrip("\n") + ("\n\n" if text.strip() else "") + f"[tools]\n{lines}"
    nxt = re.search(r"^\[", text[match.end():], re.MULTILINE)
    at = match.end() + (nxt.start() if nxt else len(text) - match.end())
    rest = text[at:]
    return text[:at].rstrip("\n") + "\n" + lines + ("\n" + rest if rest else "")


def agents_add(text: str) -> str:
    if BEGIN in text and END in text:
        return re.sub(re.escape(BEGIN) + r".*?" + re.escape(END), lambda _: BLOCK, text, flags=re.DOTALL)
    return (text.rstrip("\n") + "\n\n" if text.strip() else "") + BLOCK + "\n"


def render(fields: dict[str, str]) -> str:
    front = "".join(f"{k}: {fields[k]}\n" for k in KEYS if fields.get(k))
    return f"---\n{front}---\n"


def parse_define(raw: list[str]) -> tuple[str, dict[str, str]]:
    name, pairs = raw[0], raw[1:]
    if not re.match(r"^[A-Za-z0-9][A-Za-z0-9._-]*$", name) or name.count(".") < 1:
        raise ValueError(f"definition name {name!r} must look like <skill>.<role>[.<variant>]")
    fields = {}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep or key not in KEYS or not value:
            raise ValueError(f"{name}: expected KEY=VALUE with KEY in {', '.join(KEYS)}, got {pair!r}")
        fields[key] = value
    if fields.get("run-agent") not in RUN_AGENTS:
        raise ValueError(f"{name}: run-agent must be one of {', '.join(RUN_AGENTS)}")
    if fields.get("permission") and fields["permission"] not in PERMISSIONS:
        raise ValueError(f"{name}: permission must be one of {', '.join(PERMISSIONS)}")
    return name, fields


def status(root: Path) -> dict:
    defs = definitions(root)
    agents_md = root / "AGENTS.md"
    mise = root / "mise.toml"
    used = {d["run-agent"] for d in defs.values()}
    return {
        "roles": roles(root),
        "definitions": defs,
        "dependencies_needed": [f"{k}@{v}" for k, v in needed_deps(used)],
        "mise_toml": mise.exists(),
        "agents_block": agents_md.exists() and BEGIN in agents_md.read_text(encoding="utf-8"),
        "clis_on_path": {a: shutil.which(CLI[a]) is not None for a in RUN_AGENTS},
    }


def change(root: Path, args, write: bool) -> list[str]:
    report, existing = [], definitions(root)
    defines = [parse_define(raw) for raw in args.define or []]
    for name, fields in defines:
        path = root / ".agents" / f"{name}.md"
        if path.exists() and not args.replace:
            report.append(f"keep    .agents/{name}.md (exists; --replace to overwrite)")
            continue
        if path.exists() and path.read_text(encoding="utf-8") == render(fields):
            report.append(f"ok      .agents/{name}.md")
            continue
        report.append(f"{'write' if write else 'would write'} .agents/{name}.md: {render(fields).strip().replace(chr(10), ' ')}")
        if write:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(render(fields), encoding="utf-8")
        existing[name] = fields
    used = {d["run-agent"] for d in existing.values()}
    deps = needed_deps(used)
    if args.deps == "mise":
        mise = root / "mise.toml"
        before = mise.read_text(encoding="utf-8") if mise.exists() else ""
        after = mise_add(before, deps)
        if after == before:
            report.append("ok      mise.toml")
        else:
            report.append(f"{'write' if write else 'would write'} mise.toml: {', '.join(f'{k} = {v}' for k, v in deps if k not in before)}")
            if write:
                mise.write_text(after, encoding="utf-8")
    elif deps:
        report.append("deps    not declared by this run; needed: " + ", ".join(f"{k}@{v}" for k, v in deps))
    if args.agents_block:
        path = root / "AGENTS.md"
        before = path.read_text(encoding="utf-8") if path.exists() else ""
        after = agents_add(before)
        if after == before:
            report.append("ok      AGENTS.md block")
        else:
            report.append(f"{'write' if write else 'would write'} AGENTS.md block")
            if write:
                path.write_text(after, encoding="utf-8")
    missing = sorted(CLI[a] for a in used if shutil.which(CLI[a]) is None)
    if missing:
        report.append("warn    not on PATH (install and log in yourself): " + ", ".join(missing))
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0], epilog=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("status", "plan", "apply"))
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--define", nargs="+", action="append", metavar="NAME KEY=VALUE")
    parser.add_argument("--replace", action="store_true")
    parser.add_argument("--deps", choices=("mise",))
    parser.add_argument("--agents-block", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.project_root).resolve()
    try:
        if args.command == "status":
            print(json.dumps(status(root), indent=1))
        else:
            print("\n".join(change(root, args, write=args.command == "apply")) or "nothing to change")
    except (ValueError, tomllib.TOMLDecodeError) as problem:
        print(f"error   {problem}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
