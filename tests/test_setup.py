"""Tests for setup.py: exact edits, idempotent, --check changes nothing."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "skills" / "bmad-multimodel" / "scripts" / "setup.py"


class SetupTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())

    def run_setup(self, *args):
        done = subprocess.run([sys.executable, str(SCRIPT), "--project-root", str(self.root), *args], capture_output=True, text=True)
        return done.returncode, done.stdout

    def read(self, name):
        return (self.root / name).read_text()

    def test_writes_all_three_then_is_idempotent(self):
        (self.root / "mise.toml").write_text('[tools]\nnode = "22"\n\n[tasks.x]\nrun = "echo"\n')
        (self.root / "AGENTS.md").write_text("# Rules\n\n- Be kind.\n")
        code, out = self.run_setup()
        self.assertEqual(code, 0)
        self.assertEqual(
            self.read("mise.toml"),
            '[tools]\nnode = "22"\n"npm:acpx" = "0.22.0"\n"npm:@agentclientprotocol/claude-agent-acp" = "0.95.0"\n\n[tasks.x]\nrun = "echo"\n',
        )
        self.assertTrue(self.read("AGENTS.md").startswith("# Rules\n\n- Be kind.\n\n<!-- bmad-multimodel:begin -->\n## Launching agents"))
        self.assertEqual(self.read(".gitignore"), ".agents/runs.jsonl\n")
        self.assertIn("mise install", out)
        snapshot = {n: self.read(n) for n in ("mise.toml", "AGENTS.md", ".gitignore")}
        code, out = self.run_setup()
        self.assertEqual({n: self.read(n) for n in snapshot}, snapshot)
        self.assertEqual(out.count("ok "), 3)

    def test_check_reports_and_changes_nothing(self):
        (self.root / "mise.toml").write_text('[tools]\nnode = "22"\n')
        code, out = self.run_setup("--check")
        self.assertEqual(code, 1)
        self.assertEqual(self.read("mise.toml"), '[tools]\nnode = "22"\n')
        self.assertFalse((self.root / "AGENTS.md").exists())
        self.run_setup()
        self.assertEqual(self.run_setup("--check")[0], 0)

    def test_block_is_replaced_not_duplicated(self):
        (self.root / "AGENTS.md").write_text("A\n<!-- bmad-multimodel:begin -->\nold text\n<!-- bmad-multimodel:end -->\nB\n")
        self.run_setup()
        text = self.read("AGENTS.md")
        self.assertEqual(text.count("bmad-multimodel:begin"), 1)
        self.assertNotIn("old text", text)
        self.assertTrue(text.endswith("<!-- bmad-multimodel:end -->\nB\n"))

    def test_without_mise_toml_it_skips_and_keeps_existing_pins(self):
        code, out = self.run_setup()
        self.assertIn("skip   mise.toml", out)
        self.assertFalse((self.root / "mise.toml").exists())
        (self.root / "mise.toml").write_text('[tools]\n"npm:acpx" = "0.21.0"\n')
        self.run_setup()
        self.assertIn('"npm:acpx" = "0.21.0"', self.read("mise.toml"))
        self.assertEqual(self.read("mise.toml").count("npm:acpx"), 1)

    def test_mise_without_tools_section_gets_one(self):
        (self.root / "mise.toml").write_text('[env]\nA = "1"\n')
        self.run_setup()
        self.assertTrue(self.read("mise.toml").endswith('[tools]\n"npm:acpx" = "0.22.0"\n"npm:@agentclientprotocol/claude-agent-acp" = "0.95.0"\n'))


if __name__ == "__main__":
    unittest.main()
