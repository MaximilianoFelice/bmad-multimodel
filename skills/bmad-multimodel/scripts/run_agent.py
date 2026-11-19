#!/usr/bin/env python3
"""Run one agent definition through acpx and print one JSON result.

A definition is `<agents-dir>/<name>.md` with flat front matter (the
sub-agents-skills format): run-agent, model, effort, permission. The body is
prepended to the prompt. Sessions are named `<definition>--<session>` so a
caller can send follow-up prompts to the same agent.

Statuses: success (exit 0 and a non-empty answer), denied (every permission
the agent asked for was refused), empty (the agent ended with no answer),
error (anything else). Only success means the agent did the work.
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

# run-agent value -> acpx agent arguments (a named acpx agent, or a raw ACP command).
AGENTS = {
    "claude": ["claude"],
    "codex": ["codex"],
    "gemini": ["gemini"],
    "opencode": ["opencode"],
    "antigravity": ["--agent", "agy acp"],
    "agy": ["--agent", "agy acp"],
}
# Session config key that carries the reasoning level, per agent.
EFFORT_KEYS = {"claude": "effort", "antigravity": "thought_level", "agy": "thought_level", "codex": "reasoning_effort"}
SAFE = ["read", "search", "fetch", "think", "execute"]
PERMISSIONS = {
    "read-only": {"autoApprove": SAFE, "autoDeny": ["edit", "delete", "move"], "defaultAction": "deny"},
    "safe-edit": {"autoApprove": SAFE + ["edit", "delete", "move"], "defaultAction": "deny"},
}
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def parse_definition(path: Path) -> tuple[dict[str, str], str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.DOTALL)
    if not match:
        return {}, text.strip()
    fields = {}
    for line in match.group(1).splitlines():
        if ":" in line and not line.lstrip().startswith("#"):
            key, value = line.split(":", 1)
            fields[key.strip()] = value.split(" #", 1)[0].strip().strip("\"'")
    return fields, match.group(2).strip()


def agents_dir(args) -> Path:
    return Path(args.agents_dir or os.environ.get("SUB_AGENTS_DIR") or Path(args.cwd) / ".agents")


def policy_for(permission: str, directory: Path) -> dict | None:
    if permission == "yolo":
        return None
    policy = json.loads(json.dumps(PERMISSIONS.get(permission, PERMISSIONS["safe-edit"])))
    extra = directory / "runner-policy.json"
    if extra.exists():
        project = json.loads(extra.read_text(encoding="utf-8"))
        policy["autoDeny"] = policy.get("autoDeny", []) + project.get("autoDeny", [])
    return policy


def runner_env(directory: Path) -> dict[str, str]:
    env = dict(os.environ)
    extra = directory / "runner.env"
    if extra.exists():
        for line in extra.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                env[key.strip()] = value.strip()
    return env


def parse_stream(stdout: str) -> dict:
    text, usage, errors, stop = [], None, [], None
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
            stop, usage = result["stopReason"], result.get("usage")
    return {"text": "".join(text), "usage": usage, "errors": errors, "stop_reason": stop}


def classify(exit_code: int, parsed: dict) -> str:
    if exit_code == 5:
        return "denied"
    if exit_code != 0 or parsed["errors"]:
        return "error"
    return "success" if parsed["text"].strip() else "empty"


def acpx(base: list[str], tail: list[str], env, cwd, timeout) -> subprocess.CompletedProcess:
    return subprocess.run(["acpx", *base, *tail], cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)


def run(args) -> dict:
    directory = agents_dir(args)
    if not NAME.match(args.agent):
        raise ValueError(f"invalid definition name {args.agent!r}")
    path = directory / f"{args.agent}.md"
    if not path.exists():
        raise FileNotFoundError(f"no definition {path}; create it from the skill's template")
    fields, body = parse_definition(path)
    kind = fields.get("run-agent", "")
    if kind == "native":
        raise ValueError("run-agent: native is launched with the host's own subagent tool, not this runner")
    if kind not in AGENTS:
        raise ValueError(f"unsupported run-agent {kind!r}; one of {', '.join(AGENTS)} or native")
    if shutil.which("acpx") is None:
        raise FileNotFoundError("acpx is not on PATH; add npm:acpx to the project's mise.toml")
    prompt = Path(args.prompt_file).read_text(encoding="utf-8") if args.prompt_file else args.prompt
    session = f"{args.agent}--{args.session or 'run-' + secrets.token_hex(4)}"
    env, cwd = runner_env(directory), args.cwd
    flags = ["--format", "json", "--non-interactive-permissions", "deny", "--timeout", str(args.timeout)]
    if fields.get("model"):
        flags += ["--model", fields["model"]]
    policy = policy_for(fields.get("permission", "safe-edit"), directory)
    flags += ["--approve-all"] if policy is None else ["--permission-policy", json.dumps(policy)]
    agent = AGENTS[kind]
    started = time.time()
    ensured = acpx(agent, ["sessions", "ensure", "--name", session], env, cwd, 300)
    if ensured.returncode != 0:
        return {"status": "error", "error": ensured.stderr.strip()[-500:], "session": session}
    if fields.get("effort") and kind in EFFORT_KEYS:
        acpx(agent, ["set", "-s", session, EFFORT_KEYS[kind], fields["effort"]], env, cwd, 300)
    message = f"{body}\n\n---\n\n{prompt}" if body else prompt
    try:
        done = acpx(flags + agent, ["prompt", "-s", session, message], env, cwd, args.timeout + 60)
        exit_code, stdout, stderr = done.returncode, done.stdout, done.stderr
    except subprocess.TimeoutExpired as expired:
        exit_code, stdout, stderr = 124, expired.stdout or "", "timeout"
        stdout = stdout.decode() if isinstance(stdout, bytes) else stdout
    parsed = parse_stream(stdout)
    if not args.session:
        acpx(agent, ["sessions", "close", session], env, cwd, 60)
    result = {
        "status": classify(exit_code, parsed),
        "definition": args.agent,
        "run_agent": kind,
        "model": fields.get("model"),
        "session": args.session,
        "exit_code": exit_code,
        "seconds": round(time.time() - started),
        "usage": parsed["usage"],
        "error": "; ".join(parsed["errors"]) or (stderr.strip()[-300:] if exit_code not in (0, 5) else None),
        "text": parsed["text"],
    }
    log = directory / "runs.jsonl"
    with log.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({k: v for k, v in result.items() if k != "text"} | {"at": int(started)}) + "\n")
    return result


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
    parser.add_argument("--session", help="key for a resumable session (e.g. a ticket id)")
    parser.add_argument("--cwd", default=os.getcwd())
    parser.add_argument("--agents-dir")
    parser.add_argument("--timeout", type=int, default=1800, help="seconds")
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
