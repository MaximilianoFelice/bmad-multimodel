# Setting up bmad-multimodel in a project

Setup is one script. Run it as written. Do not edit these files by hand, and do not run BMad's installer for this skill, because this skill is not a BMad module.

```bash
python3 {skill-root}/scripts/setup.py --project-root <project root>
mise install
```

The script prints one line per file. It writes only these three:

| File | Change |
| --- | --- |
| `mise.toml` | Adds `"npm:acpx" = "0.22.0"` and `"npm:@agentclientprotocol/claude-agent-acp" = "0.95.0"` under `[tools]`. An existing pin is never changed. Without a `mise.toml` it skips this step and prints what to install with the project's tool manager. |
| `AGENTS.md` | Adds the "Launching agents" block between `<!-- bmad-multimodel:begin -->` and `<!-- bmad-multimodel:end -->`. A later run replaces the block in place. |
| `.gitignore` | Adds `.agents/runs.jsonl`. |

Running it again changes nothing. `--check` reports what is missing and exits 1 without writing anything.

The agent CLIs (`claude`, `agy`, `codex`, `gemini`, `opencode`) must already be installed and logged in. The script does not install them.

## Optional guards

These are project-specific, and the script never writes them:

- **`.agents/runner.env`:** `KEY=VALUE` lines added to every launched agent's environment. For example, `ADB_SERVER_SOCKET=tcp:127.0.0.1:1` keeps agents off a phone on adb, and `KUBECONFIG=/dev/null` keeps them off a cluster.
- **`.agents/runner-policy.json`:** a list of tools or commands refused for every definition, for example `{"autoDeny": ["adb", "kubectl", "helm"]}`. A command matches by its first word.

## Check

```bash
python3 {skill-root}/scripts/run_agent.py --list
python3 {skill-root}/scripts/run_agent.py --agent <definition> --prompt "Reply with the word ready."
```

`--list` must parse every definition. The second command must return `"status": "success"` for each agent kind in use.

## Changing who runs a role

- **Another model or vendor:** edit `run-agent`, `model` and `effort` in that role's definition.
- **A second opinion:** copy the definition to `<skill>.<role>.<variant>.md` and change its `run-agent` and `model`.
- **Keep a role in the host:** set `run-agent: native`.

Nothing in BMad's own files changes, so updating BMad or this skill never conflicts with the definitions.

## Antigravity notes

- `run-agent: antigravity` runs `agy acp`, the installed and logged-in agy, not acpx's bundled Antigravity runtime.
- Over ACP its model ids carry no effort suffix: `gemini-4-hydrogen` with `effort: high`, not `gemini-4-hydrogen-high`.
- An unknown id fails the run and lists the valid ids.
