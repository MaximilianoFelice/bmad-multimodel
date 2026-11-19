---
name: bmad-multimodel
description: Routes every subagent a skill or workflow launches (BMad implementers, review lenses, critics, or any other) through per-role agent definitions, so each role can run on a different model or vendor (Claude, Gemini through Antigravity, Codex, Gemini CLI, OpenCode) and get second opinions. Use before launching, spawning or starting any subagent, before re-engaging one, and when the user asks to set up or change which model runs a role.
---

# BMad Multimodel

A skill that says "launch a subagent" decides **what** the subagent does: its prompt. This skill decides **who** runs it: which CLI and model, read from a small definition file per role. The skill's prompt is never rewritten, so every model gets the same task.

`{skill-root}` is this skill's installed directory. `{agents-dir}` is `$SUB_AGENTS_DIR` or `<project root>/.agents/`. The runner is `python3 {skill-root}/scripts/run_agent.py`.

## Role definitions

One Markdown file per role and model, in the `sub-agents-skills` format:

- **Path:** `{agents-dir}/<skill>.<role>.md`, plus `{agents-dir}/<skill>.<role>.<variant>.md` for each extra opinion.
  - Examples: `bmad-build-auto.implementer.md`, `bmad-build-auto.quick.md`, `bmad-build-auto.quick.gemini.md`, `bmad-review.adversarial.md`.
- **`<skill>`** is the skill that launches the subagent.
- **`<role>`** is the id the skill gives that subagent:
  - a review lens or layer uses its `id` or `code`, such as `quick`, `blind-hunter`, `edge-case-hunter`, `verification-gap` or `intent-alignment`;
  - the implementation handoff uses `implementer`;
  - anything else uses a short kebab-case name for what the subagent does.
- **Front matter:**
  - `run-agent` is `claude`, `antigravity`, `codex`, `gemini`, `opencode` or `native`.
  - `model` is the model id that agent advertises over ACP, for example `sonnet`, `opus`, `gemini-4-hydrogen` or `gpt-5.4`.
  - `effort` is optional, for example `high`.
  - `permission` is `read-only`, `safe-edit` (the default) or `yolo`.
- **Body:** one line at most. The launching skill's prompt carries the task, so the body never restates the role.
- **`run-agent: native`** means "use the host's own subagent tool". It is the escape hatch for a role that must stay in the host.

Template: `{skill-root}/templates/definition.md`.

## Launching a subagent

Whenever a skill or workflow tells you to launch, spawn or start a subagent:

1. **Name the role** (`<skill>.<role>`) and list its definitions with `python3 {skill-root}/scripts/run_agent.py --list --prefix <skill>.<role>`.
2. **If the list is empty, create `{agents-dir}/<skill>.<role>.md`** from the template, with `run-agent: claude`. Leave out `model` so the agent uses its default; set `permission: read-only` for a reviewer and `safe-edit` for a role that edits. Then use it. Mention the new file in your report.
3. **Run every definition in the list with the exact prompt the skill gave**, after the skill's own placeholder substitution:
   - Write the prompt to a temporary file and pass `--prompt-file`.
   - Pass `--session <key>` for any subagent the skill may re-engage. That is always the implementer; use the ticket or run id as the key.
   - Command: `python3 {skill-root}/scripts/run_agent.py --agent <definition> --prompt-file <file> [--session <key>]`.
   - Do not add goals, file lists or hints of your own to the prompt.
   - Definitions with `run-agent: native` go through the host's subagent tool with the same prompt.
4. **Launch them in parallel the way the skill asks for subagents:** several blocking shell calls in one message, never backgrounded or detached. A run through this runner **is a subagent** for every rule of the launching skill, including "subagents are mandatory".
5. **Read the JSON result.** `text` is the subagent's answer and `status` says whether it counts:
   - `success`: use `text` as that subagent's result. With several definitions for one role, each is a separate reviewer, labelled by its definition name, as if the skill had launched them separately.
   - `empty`, `denied` or `error`: the subagent did not do the work. Never read it as "nothing found". Retry once. If it fails again, report that role as failed with the `error`, and continue the way the skill handles a subagent that failed.
6. **To re-engage a subagent**, for example to send review fixes to the implementer, run the same definition with the same `--session` key and the new message. That is the same conversation, not a fresh launch.

Record the definition name (for example `quick.gemini`) wherever the skill records which subagents ran, such as `lenses_ran`.

## Rules

- **Never use the host's own subagent tool for a role that has a non-`native` definition.** When none exists yet, create one (step 2) rather than falling back to the host's tool.
- **`permission` is not a security boundary.** `read-only` still lets the agent run commands; it only refuses file edits through the agent's edit tools. Guard the environment with the project's own files:
  - `{agents-dir}/runner.env` holds `KEY=VALUE` lines added to every run's environment, for example a dead `ADB_SERVER_SOCKET`.
  - `{agents-dir}/runner-policy.json` holds `{"autoDeny": [...]}`: tool kinds or command names refused for every definition.
- **Launched agents read the project's `AGENTS.md`** like any other session. Project rules belong there, not in definition bodies.
- **Every run appends a line to `{agents-dir}/runs.jsonl`:** definition, model, status, seconds and tokens. It holds no answer text. Retrospectives use it to compare models.

## Setup and changes

To set up a project, check it, or change which model runs a role, follow `{skill-root}/references/setup.md`.
