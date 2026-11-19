#!/usr/bin/env python3
"""bmad-multimodel uninstaller: removes only what the bmad-multimodel installer wrote.

  uninstall.py            lists what would be removed; writes nothing
  uninstall.py --apply    removes it

What the installer wrote: the definitions marked `installed-by: bmad-multimodel`,
the AGENTS.md block between its markers, and the dependency lines it adds to
mise.toml. Nothing else is touched.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

MARK = "installed-by: bmad-multimodel"
BEGIN, END = "<!-- bmad-multimodel:begin -->", "<!-- bmad-multimodel:end -->"
DEPENDENCIES = ("npm:acpx", "npm:@agentclientprotocol/claude-agent-acp", "npm:@agentclientprotocol/codex-acp")
SKILLS = "bmad-multimodel bmad-multimodel-install bmad-multimodel-uninstall"


def uninstall(root: Path, write: bool) -> list[str]:
    report, verb = [], "remove" if write else "would remove"
    for path in sorted((root / ".agents").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        if re.match(r"^---\n.*?^" + re.escape(MARK) + r"$.*?^---", text, re.DOTALL | re.MULTILINE):
            report.append(f"{verb} .agents/{path.name}")
            if write:
                path.unlink()
    agents_md = root / "AGENTS.md"
    if agents_md.exists() and BEGIN in agents_md.read_text(encoding="utf-8"):
        text = agents_md.read_text(encoding="utf-8")
        after = re.sub(r"\n*" + re.escape(BEGIN) + r".*?" + re.escape(END) + r"\n?", "\n", text, flags=re.DOTALL)
        report.append(f"{verb} AGENTS.md block")
        if write:
            agents_md.write_text(after.rstrip("\n") + "\n" if after.strip() else "", encoding="utf-8")
    mise = root / "mise.toml"
    if mise.exists():
        text = mise.read_text(encoding="utf-8")
        pattern = r'^\s*"(' + "|".join(re.escape(n) for n in DEPENDENCIES) + r')"\s*=.*\n?'
        found = re.findall(pattern, text, re.MULTILINE)
        if found:
            report.append(f"{verb} from mise.toml: {', '.join(found)}")
            if write:
                mise.write_text(re.sub(pattern, "", text, flags=re.MULTILINE), encoding="utf-8")
    if len(report) == 0:
        report.append("nothing the installer wrote is left")
    report.append(f"then    you run: npx skills remove {SKILLS}")
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0], epilog=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--apply", action="store_true", help="remove; without it, only list")
    args = parser.parse_args(argv)
    print("\n".join(uninstall(Path(args.project_root).resolve(), write=args.apply)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
