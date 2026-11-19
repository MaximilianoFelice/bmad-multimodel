#!/usr/bin/env python3
"""Run one role definition through acpx and print one JSON result.

A definition is `<agents-dir>/<name>.md` with flat front matter: run-agent,
model, effort, permission (an acpx permission mode). Its body, if any, is
prepended to the prompt. `--session <key>` keeps the conversation so the
caller can send follow-up prompts to the same agent.

Statuses: success (exit 0 and a non-empty answer), denied (every permission
the agent asked for was refused), empty (it ended with no answer), error.
Only success means the agent did the work.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
from pathlib import Path

# run-agent value -> acpx agent arguments.
AGENTS = {
    "claude": ["claude"],
    "codex": ["codex"],
    "gemini": ["gemini"],
    "opencode": ["opencode"],
    "antigravity": ["--agent", "agy acp"],
}
# Session config option that carries the reasoning level, per agent.
EFFORT_KEYS = {"claude": "effort", "antigravity": "thought_level", "codex": "reasoning_effort"}
# acpx permission modes.
PERMISSIONS = {"approve-all": "--approve-all", "approve-reads": "--approve-reads", "deny-all": "--deny-all"}
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def parse_definition(path: Path) -> tuple[dict[str, str], str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.DOTALL)
    if not match:
        return {}, text.strip()
    fields = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip().strip("\"'")
    return fields, match.group(2).strip()


def agents_dir(args) -> Path:
    return Path(args.agents_dir or os.environ.get("SUB_AGENTS_DIR") or Path(args.cwd) / ".agents")


def parse_stream(stdout: str) -> dict:
    text, usage, errors = [], None, []
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("error"):
            errors.append(str(event["error"].get("message", event["error"])))
        update = (event.get("params") or {}).get("update") or {}
        if update.get("sessionUpdate") == "agent_message_chunk":
            text.append((update.get("content") or {}).get("text", ""))
        result = event.get("result")
        if isinstance(result, dict) and "stopReason" in result:
            usage = result.get("usage")
    return {"text": "".join(text), "usage": usage, "errors": errors}


def classify(exit_code: int, parsed: dict) -> str:
    if exit_code == 5:
        return "denied"
    if exit_code != 0 or parsed["errors"]:
        return "error"
    return "success" if parsed["text"].strip() else "empty"


def acpx(args: list[str], cwd: str, timeout: int | None) -> subprocess.CompletedProcess:
    return subprocess.run(["acpx", *args], cwd=cwd, capture_output=True, text=True, timeout=timeout)


def run(args) -> dict:
    if not NAME.match(args.agent):
        raise ValueError(f"invalid definition name {args.agent!r}")
    path = agents_dir(args) / f"{args.agent}.md"
    if not path.exists():
        raise FileNotFoundError(f"no definition {path}")
    fields, body = parse_definition(path)
    kind = fields.get("run-agent", "")
    if kind not in AGENTS:
        raise ValueError(f"unsupported run-agent {kind!r}; one of {', '.join(AGENTS)}")
    permission = fields.get("permission")
    if permission and permission not in PERMISSIONS:
        raise ValueError(f"unsupported permission {permission!r}; one of {', '.join(PERMISSIONS)}")
    if shutil.which("acpx") is None:
        raise FileNotFoundError("acpx is not on PATH; it is a dependency of this project (see the bmad-multimodel README)")
    prompt = Path(args.prompt_file).read_text(encoding="utf-8") if args.prompt_file else args.prompt
    session = f"{args.agent}--{args.session or 'run-' + secrets.token_hex(4)}"
    agent, notes = AGENTS[kind], []
    flags = ["--format", "json"]
    if fields.get("model"):
        flags += ["--model", fields["model"]]
    if permission:
        flags.append(PERMISSIONS[permission])
    if args.timeout:
        flags += ["--timeout", str(args.timeout)]
    started = time.time()
    ensured = acpx([*agent, "sessions", "ensure", "--name", session], args.cwd, 300)
    if ensured.returncode != 0:
        return {"status": "error", "definition": args.agent, "error": ensured.stderr.strip()[-500:]}
    if fields.get("effort"):
        if kind in EFFORT_KEYS:
            acpx([*agent, "set", "-s", session, EFFORT_KEYS[kind], fields["effort"]], args.cwd, 300)
        else:
            notes.append(f"effort is not applied for run-agent {kind}")
    message = f"{body}\n\n---\n\n{prompt}" if body else prompt
    try:
        done = acpx([*flags, *agent, "prompt", "-s", session, message], args.cwd, args.timeout + 60 if args.timeout else None)
        exit_code, stdout, stderr = done.returncode, done.stdout, done.stderr
    except subprocess.TimeoutExpired as expired:
        out = expired.stdout or ""
        exit_code, stdout, stderr = 124, out.decode() if isinstance(out, bytes) else out, "timeout"
    if not args.session:
        acpx([*agent, "sessions", "close", session], args.cwd, 60)
    parsed = parse_stream(stdout)
    return {
        "status": classify(exit_code, parsed),
        "definition": args.agent,
        "run_agent": kind,
        "model": fields.get("model"),
        "session": args.session,
        "exit_code": exit_code,
        "seconds": round(time.time() - started),
        "usage": parsed["usage"],
        "error": "; ".join(parsed["errors"]) or (stderr.strip()[-300:] if exit_code not in (0, 5) else None),
        "notes": notes,
        "text": parsed["text"],
    }


def list_definitions(args) -> list[dict]:
    found = []
    for path in sorted(agents_dir(args).glob("*.md"), key=lambda p: p.stem):
        if args.prefix and not (path.stem == args.prefix or path.stem.startswith(args.prefix + ".")):
            continue
        fields, _ = parse_definition(path)
        if "run-agent" in fields:
            found.append({"name": path.stem, **{k: fields[k] for k in ("run-agent", "model", "effort", "permission") if k in fields}})
    return found


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--agent", help="definition name, without .md")
    parser.add_argument("--prompt")
    parser.add_argument("--prompt-file")
    parser.add_argument("--session", help="key for a resumable session, e.g. a ticket id")
    parser.add_argument("--cwd", default=os.getcwd())
    parser.add_argument("--agents-dir")
    parser.add_argument("--timeout", type=int, help="seconds; default: acpx's own")
    parser.add_argument("--list", action="store_true", help="list definitions")
    parser.add_argument("--prefix", help="with --list: only <prefix> and <prefix>.*")
    args = parser.parse_args(argv)
    try:
        if args.list:
            print(json.dumps(list_definitions(args), indent=1))
            return 0
        if not args.agent or not (args.prompt or args.prompt_file):
            parser.error("--agent and --prompt (or --prompt-file) are required")
        result = run(args)
    except (OSError, ValueError) as problem:
        result = {"status": "error", "error": str(problem)}
    print(json.dumps(result, indent=1))
    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
