---
name: bmad-multimodel-install
description: Installer for bmad-multimodel. It proposes which subagent roles run on which agent and model from what the user says they need, then writes only what the user approves. Use only when the user invokes bmad-multimodel-install by name.
---

# bmad-multimodel installer

The user invokes this skill with a request in their own words, for example "Gemini as a second opinion on code reviews" or "Codex reviews high-risk changes". You turn that request into a proposal, show it to them, and write only what they approve. The user can run this skill as many times as they like, and each run adds to what is already there.

`{skill-root}` is this skill's installed directory. The script is `python3 {skill-root}/scripts/install.py`, run from the project root.

## Rules

- **Write only through `install.py apply`,** and only after the user has approved that exact plan in this conversation.
- **Never install, download or log in to anything.** That includes `mise install`, `npm`, `npx` and the agent CLIs. The user does those steps.
- **Never run any other command that changes the project.**
- **Never choose for the user** something their request does not say: an agent, a model, a permission or a role. Propose it, mark it as your proposal, and let the user decide.
- **Leave every role the request does not mention without a definition.** A role without a definition runs as before.

## Steps

1. **Read the current state:** `python3 {skill-root}/scripts/install.py status`. It reports:
   - `roles`: the roles each installed skill launches;
   - `definitions`: the definitions that already exist;
   - `dependencies_needed`: the dependencies those definitions need;
   - whether the project has a `mise.toml` and whether the `AGENTS.md` block is present;
   - which agent CLIs are on PATH.
2. **Draft the proposal from the user's request and that state.**
   - **Definitions.** Each one is named `<skill>.<role>` for the main agent of a role, or `<skill>.<role>.<variant>` for an extra opinion, for example `bmad-build-auto.quick.gemini`. Use only roles that `status` lists. For each one, give:
     - `run-agent`: `claude`, `antigravity`, `codex`, `gemini` or `opencode`;
     - `model`: the id the agent offers. Ask the user when the request does not name one;
     - `effort`: optional;
     - `permission`: the acpx mode, `approve-all`, `approve-reads` or `deny-all`. Ask the user for every definition; never assume one.
   - **Dependencies.** acpx is always needed. Claude needs the `claude-agent-acp` adapter and Codex needs the `codex-acp` adapter. Antigravity, Gemini CLI and OpenCode need nothing extra. Ask where to declare them: in `mise.toml` (`--deps mise`), or nowhere, in which case the user installs them their own way.
   - **The `AGENTS.md` block** (`--agents-block`). Show its text. It is what makes every agent apply the launch rule.
3. **Show the proposal as a table.** Then show the exact output of `install.py plan` with the same arguments. Ask the user to approve it, or to change it.
4. **After an explicit approval,** run `install.py apply` with exactly those arguments and show its output.
5. **Tell the user what is left for them:**
   - `mise install` (or their own tool manager), when dependencies were declared;
   - installing and logging in to any agent CLI the plan reported as missing.

## Command reference

```bash
python3 {skill-root}/scripts/install.py plan \
  --define bmad-build-auto.quick.gemini run-agent=antigravity model=gemini-4-hydrogen effort=high permission=approve-reads \
  --deps mise --agents-block
```

- `--define` is repeatable.
- An existing definition is kept unless `--replace` is given.
- `plan` writes nothing. `apply` writes exactly what `plan` printed.
