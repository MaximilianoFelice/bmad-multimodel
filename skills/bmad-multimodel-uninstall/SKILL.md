---
name: bmad-multimodel-uninstall
description: Uninstaller for bmad-multimodel. It removes what the bmad-multimodel installer wrote, after the user approves. Use only when the user invokes bmad-multimodel-uninstall by name.
---

# bmad-multimodel uninstaller

`{skill-root}` is this skill's installed directory. The script is `python3 {skill-root}/scripts/uninstall.py`, run from the project root.

## Rules

- **Remove only what the script lists,** and only after the user has approved that list in this conversation.
- **Never run any other command that changes the project.** Never uninstall packages or skills yourself.

## Steps

1. Run `python3 {skill-root}/scripts/uninstall.py` and show its output. It lists everything the installer wrote and nothing else:
   - the definitions marked `installed-by: bmad-multimodel`;
   - the `AGENTS.md` block;
   - the dependency lines in `mise.toml`.
2. After an explicit approval, run `python3 {skill-root}/scripts/uninstall.py --apply` and show its output.
3. Tell the user what is left for them:
   - `npx skills remove bmad-multimodel bmad-multimodel-install bmad-multimodel-uninstall`;
   - their tool manager's cleanup for the removed dependencies.
