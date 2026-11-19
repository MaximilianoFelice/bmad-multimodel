---
name: bmad-multimodel
description: Decides who runs each subagent that a skill or workflow launches (BMad implementers, review lenses, critics, or any other). A role with a definition file runs on the agent and model that file names (Claude, Gemini through Antigravity, Codex, Gemini CLI, OpenCode); a role without one runs as usual. Use before launching, spawning or starting any subagent, and before re-engaging one.
---

# BMad Multimodel

A skill that launches a subagent decides **what** the subagent does: its prompt. A role definition decides **who** runs it. The prompt is never rewritten, so every agent gets the same task.

`{skill-root}` is this skill's installed directory. `{agents-dir}` is `$SUB_AGENTS_DIR` or `<project root>/.agents/`. The runner is `python3 {skill-root}/scripts/run_agent.py`.

## Role definitions

Role definitions are files named `{agents-dir}/<skill>.<role>.md`. A second opinion on the same role is another file named `<skill>.<role>.<variant>.md`.

- **`<skill>`** is the skill that launches the subagent.
- **`<role>`** is the id that skill gives the subagent:
  - a review lens or layer uses its `id` or `code` from the skill's configuration;
  - a handoff uses its configuration key without `_handoff` (`implementation_handoff` → `implementation`).
- **Front matter:**
  - `run-agent`: `claude`, `antigravity`, `codex`, `gemini` or `opencode`;
  - `model`: optional;
  - `effort`: optional;
  - `permission`: an acpx mode, `approve-all`, `approve-reads` or `deny-all`. Optional; without it, acpx's own default applies.
- **The body is optional.** When it has text, the runner puts that text before the prompt.

Only the `bmad-multimodel-install` skill writes definitions, from what the user asked for. Never create, edit or delete one yourself.

## Launching a subagent

Whenever a skill or workflow tells you to launch, spawn or start a subagent:

1. **List the role's definitions:** `python3 {skill-root}/scripts/run_agent.py --list --prefix <skill>.<role>`.
2. **If there are none,** launch the subagent the way you normally would, with your host's own subagent tool. Nothing else changes.
3. **If there are definitions,** run each one with the exact prompt the skill gave, after the skill's own placeholder substitution:
   - Write the prompt to a temporary file and run `python3 {skill-root}/scripts/run_agent.py --agent <definition> --prompt-file <file> [--session <key>]`.
   - Pass `--session <key>` for any subagent the skill may re-engage, using the ticket or run id as the key.
   - Add nothing of your own to the prompt.
   - When the skill asks for parallel subagents, launch the runs as several blocking shell calls in one message.
   - Each run counts as a subagent for every rule of the launching skill.
4. **Read the JSON result.**
   - **`success`:** `text` is that subagent's result. With several definitions for one role, each is a separate result, labelled by its definition name.
   - **`empty`, `denied` or `error`:** the subagent did not do the work. Never read it as "nothing found". Report it as failed, with `error`, the way the skill handles a failed subagent.
5. **To re-engage a subagent,** run the same definition with the same `--session` key and the new message.
