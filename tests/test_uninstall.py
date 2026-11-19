"""Tests for uninstall.py: it removes exactly what install.py wrote, after --apply."""
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[1] / "skills"
INSTALL = SKILLS / "bmad-multimodel-install" / "scripts" / "install.py"
UNINSTALL = SKILLS / "bmad-multimodel-uninstall" / "scripts" / "uninstall.py"


def load(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class UninstallTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        skill = self.root / ".agents" / "skills" / "bmad-build-auto"
        skill.mkdir(parents=True)
        (skill / "customize.toml").write_text('[workflow]\n[[workflow.quick_lenses]]\nid = "quick"\ninstruction = "Launch a subagent."\n')
        (self.root / "mise.toml").write_text('[tools]\nnode = "22"\n\n[tasks.x]\nrun = "echo"\n')
        (self.root / "AGENTS.md").write_text("# Rules\n\n- Be kind.\n")
        (self.root / ".agents" / "someone-elses.md").write_text("---\nrun-agent: codex\n---\nTheirs.\n")

    def call(self, script, *args):
        done = subprocess.run([sys.executable, str(script), *args, "--project-root", str(self.root)], capture_output=True, text=True, env=dict(os.environ, PATH="/usr/bin:/bin"))
        return done.stdout

    def snapshot(self):
        return {str(p.relative_to(self.root)): p.read_text() for p in self.root.rglob("*") if p.is_file()}

    def install(self):
        self.call(INSTALL, "apply", "--define", "bmad-build-auto.quick.gemini", "run-agent=antigravity",
                 "--define", "bmad-build-auto.quick.codex", "run-agent=codex",
                 "--define", "bmad-build-auto.implementation", "run-agent=claude", "--deps", "mise", "--agents-block")

    def test_lists_without_writing_then_restores_the_project_exactly(self):
        original = self.snapshot()
        self.install()
        installed = self.snapshot()
        out = self.call(UNINSTALL)
        self.assertIn("would remove .agents/bmad-build-auto.quick.gemini.md", out)
        self.assertIn("would remove AGENTS.md block", out)
        self.assertIn("would remove from mise.toml: npm:acpx, npm:@agentclientprotocol/claude-agent-acp, npm:@agentclientprotocol/codex-acp", out)
        self.assertIn("npx skills remove bmad-multimodel bmad-multimodel-install bmad-multimodel-uninstall", out)
        self.assertEqual(self.snapshot(), installed)
        self.call(UNINSTALL, "--apply")
        self.assertEqual(self.snapshot(), original)

    def test_nothing_left_after_a_second_run(self):
        self.install()
        self.call(UNINSTALL, "--apply")
        self.assertIn("nothing the installer wrote is left", self.call(UNINSTALL))

    def test_shares_the_installers_marks(self):
        install, uninstall = load(INSTALL), load(UNINSTALL)
        self.assertEqual((install.MARK, install.BEGIN, install.END), (uninstall.MARK, uninstall.BEGIN, uninstall.END))
        self.assertEqual({install.ACPX[0], *(k for k, _ in install.ADAPTERS.values())}, set(uninstall.DEPENDENCIES))


if __name__ == "__main__":
    unittest.main()
