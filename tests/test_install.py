"""Tests for install.py: status, plan writes nothing, apply writes exactly the plan, reruns add."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "skills" / "bmad-multimodel-install" / "scripts" / "install.py"

BUILD_AUTO = '''[workflow]
implementation_handoff = """
Launch a subagent with no prior conversation context, with this prompt: ...
"""
review = "quick"

[[workflow.quick_lenses]]
id = "quick"
instruction = "Launch a context-free subagent with this prompt: ..."

[[workflow.thorough_lenses]]
id = "blind-hunter"
instruction = "Launch a context-free subagent with this prompt: ..."
'''
OVERRIDE = '''[workflow]
persistent_facts = ["file:AGENTS.md"]

[[workflow.quick_lenses]]
id = "external"
instruction = "Run the external reviewer over bash."
'''


class InstallTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        skill = self.root / ".agents" / "skills" / "bmad-build-auto"
        skill.mkdir(parents=True)
        (skill / "customize.toml").write_text(BUILD_AUTO)
        (self.root / "_bmad" / "custom").mkdir(parents=True)
        (self.root / "_bmad" / "custom" / "bmad-build-auto.toml").write_text(OVERRIDE)
        (self.root / ".agents" / "skills" / "no-config").mkdir()
        review = self.root / ".agents" / "skills" / "bmad-review"
        review.mkdir()
        (review / "customize.toml").write_text(
            '[workflow]\n[[workflow.lenses]]\ncode = "adversarial"\ninstruction = "Load references/lens-adversarial.md."\n'
            '[[workflow.menu]]\ncode = "X"\nskill = "other"\n'
        )
        (self.root / "mise.toml").write_text('[tools]\nnode = "22"\n\n[tasks.x]\nrun = "echo"\n')
        (self.root / "AGENTS.md").write_text("# Rules\n")

    def run_install(self, *args):
        done = subprocess.run([sys.executable, str(SCRIPT), *args, "--project-root", str(self.root)], capture_output=True, text=True, env=dict(os.environ, PATH="/usr/bin:/bin"))
        return done.returncode, done.stdout, done.stderr

    def snapshot(self):
        return {str(p.relative_to(self.root)): p.read_text() for p in self.root.rglob("*") if p.is_file()}

    GEMINI = ["--define", "bmad-build-auto.quick.gemini", "run-agent=antigravity", "model=gemini-4-hydrogen", "effort=high", "permission=approve-reads"]

    def test_status_lists_roles_from_skill_config_and_overrides(self):
        code, out, _ = self.run_install("status")
        state = json.loads(out)
        self.assertEqual(state["roles"], {"bmad-build-auto": ["implementation", "quick", "blind-hunter", "external"], "bmad-review": ["adversarial"]})
        self.assertEqual(state["definitions"], {})
        self.assertEqual(state["dependencies_needed"], [])
        self.assertFalse(state["agents_block"])

    def test_plan_writes_nothing(self):
        before = self.snapshot()
        code, out, _ = self.run_install("plan", *self.GEMINI, "--deps", "mise", "--agents-block")
        self.assertEqual(code, 0)
        self.assertIn("would write .agents/bmad-build-auto.quick.gemini.md", out)
        self.assertIn("would write mise.toml: npm:acpx = 0.22.0", out)
        self.assertEqual(self.snapshot(), before)

    def test_apply_writes_exactly_the_plan(self):
        self.run_install("apply", *self.GEMINI, "--deps", "mise", "--agents-block")
        self.assertEqual(
            (self.root / ".agents" / "bmad-build-auto.quick.gemini.md").read_text(),
            "---\nrun-agent: antigravity\nmodel: gemini-4-hydrogen\neffort: high\npermission: approve-reads\ninstalled-by: bmad-multimodel\n---\n",
        )
        self.assertEqual((self.root / "mise.toml").read_text(), '[tools]\nnode = "22"\n"npm:acpx" = "0.22.0"\n\n[tasks.x]\nrun = "echo"\n')
        self.assertIn("<!-- bmad-multimodel:begin -->", (self.root / "AGENTS.md").read_text())

    def test_rerun_adds_and_keeps_what_exists(self):
        self.run_install("apply", *self.GEMINI, "--deps", "mise", "--agents-block")
        code, out, _ = self.run_install("apply", "--define", "bmad-build-auto.implementation", "run-agent=claude", "--deps", "mise", "--agents-block")
        mise = (self.root / "mise.toml").read_text()
        self.assertEqual(mise.count("npm:acpx"), 1)
        self.assertIn('"npm:@agentclientprotocol/claude-agent-acp" = "0.95.0"', mise)
        self.assertEqual((self.root / "AGENTS.md").read_text().count("bmad-multimodel:begin"), 1)
        self.assertIn("ok      AGENTS.md block", out)
        code, out, _ = self.run_install("apply", "--define", "bmad-build-auto.quick.gemini", "run-agent=codex")
        self.assertIn("keep    .agents/bmad-build-auto.quick.gemini.md", out)
        self.assertIn("antigravity", (self.root / ".agents" / "bmad-build-auto.quick.gemini.md").read_text())
        self.run_install("apply", "--define", "bmad-build-auto.quick.gemini", "run-agent=codex", "--replace")
        self.assertEqual((self.root / ".agents" / "bmad-build-auto.quick.gemini.md").read_text(), "---\nrun-agent: codex\ninstalled-by: bmad-multimodel\n---\n")

    def test_without_deps_flag_it_only_reports_what_is_needed(self):
        code, out, _ = self.run_install("apply", "--define", "bmad-build-auto.quick", "run-agent=codex")
        self.assertIn("deps    not declared by this run; needed: npm:acpx@0.22.0, npm:@agentclientprotocol/codex-acp@1.13.1", out)
        self.assertNotIn("acpx", (self.root / "mise.toml").read_text())

    def test_missing_cli_is_a_warning(self):
        code, out, _ = self.run_install("plan", "--define", "bmad-build-auto.quick", "run-agent=opencode")
        self.assertIn("warn    not on PATH (install and log in yourself): opencode", out)

    def test_invalid_definitions_are_rejected_and_nothing_is_written(self):
        before = self.snapshot()
        for define in (["nodot", "run-agent=claude"], ["a.b", "run-agent=cobol"], ["a.b", "run-agent=claude", "permission=safe-edit"], ["a.b", "colour=red"]):
            code, out, err = self.run_install("apply", "--define", *define)
            self.assertEqual(code, 2, define)
        self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
