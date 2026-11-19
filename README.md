# bmad-multimodel

Choose which model runs each part of your BMad workflow: Claude, Gemini (through Antigravity), Codex, Gemini CLI or OpenCode.

## The idea

Your harness, your skills, your agents and your models should not come as one bundle. BMad already says **what** each subagent does: the implementer, each review lens. This repo only lets you say **who** runs it.

- **BMad stays untouched.** Every model gets the same prompt BMad wrote.
- **Nothing changes until you ask.** A role you don't configure keeps running exactly as it does today.
- **You decide everything:** which roles, which agents, which models, which permissions. Nothing is chosen for you, and nothing is downloaded behind your back.
- **Second opinions are just more agents on the same role.** For example, Claude and Gemini both review the same change.

## What you do

1. **Install the skills** (`bmad-multimodel`, `bmad-multimodel-install`, `bmad-multimodel-uninstall`) in your project:
   ```bash
   npx skills add MaximilianoFelice/bmad-multimodel
   ```
2. **Ask your agent for the installer, in your own words**, for example:
   ```text
   /bmad-multimodel-install I want Gemini 4 Hydrogen as a second opinion on code reviews
   ```
   It shows you which roles exist, proposes a setup, and asks you about anything your request did not settle, such as the model or the permissions. It writes only what you approve.
3. **Install the dependencies it declared** with your own tool, for example `mise install`.

Run the installer again whenever you want to add or change something. It keeps what is already there.

## Uninstall

1. **Run the uninstaller:**
   ```text
   /bmad-multimodel-uninstall
   ```
   It shows everything the installer wrote: its role files, the `AGENTS.md` block and the dependency lines. It removes them only after you approve. Role files it did not write are never touched.
2. **Remove the skills:**
   ```bash
   npx skills remove bmad-multimodel bmad-multimodel-install bmad-multimodel-uninstall
   ```

## What you need to know

- **One file per role.** Each configured role is a small file, `.agents/<skill>.<role>.md`. An extra opinion on the same role is another file, `.agents/<skill>.<role>.<variant>.md`. To see or change who runs a role, open its file.
- **Dependencies are yours.** The installer declares them in your repo, and you install them.

  | You use | You need |
  | --- | --- |
  | any agent | [acpx](https://github.com/openclaw/acpx), which launches the agents and keeps their conversations |
  | Claude Code | `@agentclientprotocol/claude-agent-acp` |
  | Codex | `@agentclientprotocol/codex-acp` |
  | Antigravity, Gemini CLI, OpenCode | nothing extra |

  The agents' own CLIs (`claude`, `agy`, `codex`, `gemini`, `opencode`) must be installed and logged in by you.
- **Permissions are your choice.** Each role uses one of acpx's modes: `approve-all`, `approve-reads` or `deny-all`. None of them is a security boundary. A launched agent can reach whatever your own session can reach.
- **A failed agent never counts as a clean result.** An agent that gives no answer, or whose actions were all refused, is reported as failed, never as "nothing found".

## License

MIT
