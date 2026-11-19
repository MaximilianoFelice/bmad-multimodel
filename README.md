# bmad-multimodel

Run each subagent role on the model you choose: Claude, Gemini through Google Antigravity, Codex, Gemini CLI or OpenCode. You can also run the same role on several models to get second opinions. BMad workflows such as `bmad-build-auto` and `bmad-review` stay untouched.

BMad skills say **what** a subagent does: the prompt for the implementer or for a review lens. This skill decides **who** runs it, from one small definition file per role:

```
.agents/bmad-build-auto.implementer.md    run-agent: claude
.agents/bmad-build-auto.quick.md          run-agent: claude
.agents/bmad-build-auto.quick.gemini.md   run-agent: antigravity  ← second opinion, same prompt
.agents/bmad-review.adversarial.md        run-agent: codex
```

```markdown
---
run-agent: antigravity
model: gemini-4-hydrogen
effort: high
permission: read-only
---
Follow the task below exactly; it comes from the skill that launched you.
```

The front matter follows [sub-agents-skills](https://github.com/shinpr/sub-agents-skills), so you can move definitions between the two runners.

## How it works

- **The launch rule.** When a skill launches a subagent, the agent loads this skill. The skill tells it to find `<skill>.<role>*.md` and run each matching definition with the launching skill's exact prompt. When a role has no definition yet, it creates one that runs on Claude.
- **The runner.** [acpx](https://github.com/openclaw/acpx), a headless Agent Client Protocol client, launches the agents. It gives every vendor the same interface:
  - **Named sessions:** `--session <key>` lets a workflow send review fixes back to the same implementer conversation.
  - **One permission policy** for every agent.
  - **Structured output.**
- **The result.** `scripts/run_agent.py` (stdlib Python, about 200 lines) reads the definition, opens or resumes the session, applies the permission profile and prints one JSON result.
  - Statuses: `success`, `empty`, `denied` or `error`. An empty or refused run never passes as a clean review.
  - Every run appends metrics to `.agents/runs.jsonl`, so you can compare models later.

## Install

Install with the [skills CLI](https://github.com/vercel-labs/skills), the same installer BMad uses:

```bash
npx skills add MaximilianoFelice/bmad-multimodel
```

This puts the skill in `.agents/skills/`, which Antigravity, Codex, Gemini CLI and others read, links it for Claude Code, and records it in `skills-lock.json`. It does not touch BMad's files, so updating either one never conflicts.

Claude Code can also install it as a plugin:

```text
/plugin marketplace add MaximilianoFelice/bmad-multimodel
/plugin install bmad-multimodel@bmad-multimodel
```

Then ask your agent to "set up bmad-multimodel". It follows [`references/setup.md`](skills/bmad-multimodel/references/setup.md):

1. **Pin the tools** in your tool manager: `npm:acpx`, plus `npm:@agentclientprotocol/claude-agent-acp` for Claude. With mise:
   ```toml
   "npm:acpx" = "0.22.0"
   "npm:@agentclientprotocol/claude-agent-acp" = "0.95"
   ```
2. **Add a short "Launching agents" block** to `AGENTS.md`.
3. **Ignore the run log** (`.agents/runs.jsonl`) in git.
4. **Add guards if you need them** (optional):
   - `.agents/runner.env` sets environment variables for every launched agent.
   - `.agents/runner-policy.json` refuses tools or commands, for example `{"autoDeny": ["adb", "kubectl"]}`.

The agent CLIs themselves (`claude`, `agy`, `codex`, …) must already be installed and logged in.

## Security

`permission: read-only` only refuses file edits made through the agent's edit tools. The agent can still run commands. No CLI permission mode is a security boundary, and Antigravity's own sandbox can be bypassed by the model.

A launched agent has the same access as the session that launched it. Keep credentials the agents must not use out of their environment, with `runner.env`, a container or a separate user.

## Develop

```bash
python3 -m unittest discover -s tests
```

The tests run the runner against a fake `acpx`.

## License

MIT
