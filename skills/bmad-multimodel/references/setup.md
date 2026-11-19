# Setting up bmad-multimodel in a project

Do each step only when it is missing, and report what you changed.

1. **Install the runner's tools through the project's tool manager.** With mise, add these to `mise.toml` `[tools]` and run `mise install`:
   ```toml
   node = "22"                                         # if not already there; acpx needs Node 22.13+
   "npm:acpx" = "0.22.0"
   "npm:@agentclientprotocol/claude-agent-acp" = "0.95"  # only if a definition uses run-agent: claude
   ```
   - Pin exact versions, because acpx is pre-1.0.
   - The agent CLIs themselves (`claude`, `agy`, `codex`, `gemini`, `opencode`) must already be installed and logged in.
   - Without mise, install the same packages with the project's own tool manager. Do not install them globally unless the user asks.
2. **Add this block to the project's `AGENTS.md`**, or to the file the project's agents read first:
   ```markdown
   ## Launching agents

   Every subagent launch (BMad implementers, review lenses, critics and any other) follows the `bmad-multimodel` skill: load it before launching or re-engaging a subagent. Role definitions are in `.agents/<skill>.<role>[.<variant>].md`; the model for a role is changed there.
   ```
3. **Add `.agents/runs.jsonl` to `.gitignore`.**
4. **Optional guards, project-specific:**
   - `.agents/runner.env` sets environment for every launched agent, for example `ADB_SERVER_SOCKET=tcp:127.0.0.1:1` so no agent reaches a phone, or `KUBECONFIG=/dev/null`.
   - `.agents/runner-policy.json` refuses tools or commands for every definition, for example `{"autoDeny": ["adb", "kubectl", "helm"]}`. A command matches by its first word.
5. **Check it.**
   - `python3 {skill-root}/scripts/run_agent.py --list` must parse every definition.
   - A one-line run per agent kind in use must come back `success`: `--agent <definition> --prompt "Reply with the word ready."`.

## Changing who runs a role

- **Another model or vendor:** edit `run-agent`, `model` and `effort` in that role's definition.
- **A second opinion:** copy the definition to `<skill>.<role>.<variant>.md` and change its `run-agent` and `model`.
- **Keep a role in the host:** set `run-agent: native`.

Nothing in BMad's own files changes, so updating BMad or this skill never conflicts with the definitions.

## Antigravity notes

- `run-agent: antigravity` runs `agy acp`, the installed and logged-in agy, and not acpx's bundled Antigravity runtime.
- Over ACP its model ids carry no effort suffix: `gemini-4-hydrogen` with `effort: high`, not `gemini-4-hydrogen-high`. An unknown id fails the run with the list of valid ids.
