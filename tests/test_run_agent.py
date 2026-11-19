"""Tests for run_agent.py against a fake acpx that records its calls."""
import json
import os
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "skills" / "bmad-multimodel" / "scripts" / "run_agent.py"

FAKE_ACPX = textwrap.dedent(
    """\
    #!/usr/bin/env python3
    import json, os, sys
    with open(os.environ["FAKE_LOG"], "a") as log:
        log.write(json.dumps(sys.argv[1:]) + "\\n")
    if "prompt" not in sys.argv:
        sys.exit(0)
    mode = os.environ.get("FAKE_MODE", "answer")
    def emit(event):
        print(json.dumps(event))
    if mode == "answer":
        for chunk in ("All ", "good."):
            emit({"method": "session/update", "params": {"update": {"sessionUpdate": "agent_message_chunk", "content": {"type": "text", "text": chunk}}}})
    if mode == "error":
        emit({"jsonrpc": "2.0", "id": None, "error": {"code": -32603, "message": "Cannot apply --model"}})
        sys.exit(1)
    emit({"jsonrpc": "2.0", "id": 2, "result": {"stopReason": "end_turn", "usage": {"totalTokens": 42}}})
    sys.exit(5 if mode == "denied" else 0)
    """
)


class RunAgentTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        fake = self.bin / "acpx"
        fake.write_text(FAKE_ACPX)
        fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
        self.agents = self.tmp / ".agents"
        self.agents.mkdir()
        self.log = self.tmp / "calls.jsonl"

    def define(self, name, front, body=""):
        lines = "\n".join(f"{k}: {v}" for k, v in front.items())
        (self.agents / f"{name}.md").write_text(f"---\n{lines}\n---\n{body}")

    def run_agent(self, *args, mode="answer"):
        env = dict(os.environ, PATH=f"{self.bin}:{os.environ['PATH']}", FAKE_LOG=str(self.log), FAKE_MODE=mode)
        done = subprocess.run([sys.executable, str(SCRIPT), "--cwd", str(self.tmp), *args], env=env, capture_output=True, text=True)
        return done.returncode, json.loads(done.stdout)

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def prompt_call(self):
        return next(c for c in self.calls() if "prompt" in c)

    def test_success_returns_the_answer(self):
        self.define("bmad-review.adversarial", {"run-agent": "claude", "model": "sonnet"})
        code, result = self.run_agent("--agent", "bmad-review.adversarial", "--prompt", "Review it.")
        self.assertEqual((code, result["status"], result["text"]), (0, "success", "All good."))
        self.assertEqual(result["usage"], {"totalTokens": 42})

    def test_prompt_is_sent_as_given_without_a_body(self):
        self.define("x.quick", {"run-agent": "claude"})
        self.run_agent("--agent", "x.quick", "--prompt", "The task.")
        self.assertEqual(self.prompt_call()[-1], "The task.")

    def test_body_when_present_goes_before_the_prompt(self):
        self.define("x.quick", {"run-agent": "claude"}, "Body line.\n")
        self.run_agent("--agent", "x.quick", "--prompt", "The task.")
        self.assertEqual(self.prompt_call()[-1], "Body line.\n\n---\n\nThe task.")

    def test_no_permission_flag_unless_the_definition_sets_one(self):
        self.define("x.quick", {"run-agent": "claude", "model": "sonnet"})
        self.run_agent("--agent", "x.quick", "--prompt", "Go.")
        call = self.prompt_call()
        self.assertIn("sonnet", call)
        for flag in ("--approve-all", "--approve-reads", "--deny-all", "--permission-policy", "--non-interactive-permissions"):
            self.assertNotIn(flag, call)

    def test_permission_maps_to_the_acpx_mode(self):
        self.define("x.quick", {"run-agent": "claude", "permission": "approve-reads"})
        self.run_agent("--agent", "x.quick", "--prompt", "Go.")
        self.assertIn("--approve-reads", self.prompt_call())

    def test_antigravity_uses_agy_acp_and_thought_level(self):
        self.define("x.quick.gemini", {"run-agent": "antigravity", "model": "gemini-4-hydrogen", "effort": "high"})
        self.run_agent("--agent", "x.quick.gemini", "--prompt", "Go.")
        calls = self.calls()
        self.assertTrue(all(c[c.index("--agent") + 1] == "agy acp" for c in calls))
        self.assertTrue(any(c[-2:] == ["thought_level", "high"] for c in calls))

    def test_effort_without_a_known_option_is_reported_not_dropped_silently(self):
        self.define("x.quick", {"run-agent": "gemini", "effort": "high"})
        code, result = self.run_agent("--agent", "x.quick", "--prompt", "Go.")
        self.assertEqual(result["notes"], ["effort is not applied for run-agent gemini"])

    def test_session_is_named_and_kept_open_and_one_shot_is_closed(self):
        self.define("x.implementation", {"run-agent": "claude"})
        self.run_agent("--agent", "x.implementation", "--prompt", "Build.", "--session", "41")
        self.assertIn(["claude", "sessions", "ensure", "--name", "x.implementation--41"], self.calls())
        self.assertFalse(any("close" in c for c in self.calls()))
        self.log.unlink()
        self.run_agent("--agent", "x.implementation", "--prompt", "Build.")
        self.assertTrue(any("close" in c for c in self.calls()))

    def test_failures_are_never_success(self):
        self.define("x.quick", {"run-agent": "claude"})
        for mode, status in (("empty", "empty"), ("denied", "denied"), ("error", "error")):
            code, result = self.run_agent("--agent", "x.quick", "--prompt", "Go.", mode=mode)
            self.assertEqual((code, result["status"]), (1, status), mode)

    def test_bad_definitions_are_errors(self):
        self.define("x.odd", {"run-agent": "cobol"})
        self.define("x.perm", {"run-agent": "claude", "permission": "safe-edit"})
        for name in ("x.odd", "x.perm", "x.missing", "../etc"):
            code, result = self.run_agent("--agent", name, "--prompt", "Go.")
            self.assertEqual((code, result["status"]), (1, "error"), name)

    def test_writes_nothing_besides_calling_acpx(self):
        self.define("x.quick", {"run-agent": "claude"})
        self.run_agent("--agent", "x.quick", "--prompt", "Go.")
        self.assertEqual(sorted(p.name for p in self.agents.iterdir()), ["x.quick.md"])

    def test_list_filters_by_role_prefix(self):
        self.define("bmad-build-auto.quick", {"run-agent": "claude"})
        self.define("bmad-build-auto.quick.gemini", {"run-agent": "antigravity", "model": "gemini-4-hydrogen"})
        self.define("bmad-build-auto.quickest", {"run-agent": "claude"})
        code, result = self.run_agent("--list", "--prefix", "bmad-build-auto.quick")
        self.assertEqual([d["name"] for d in result], ["bmad-build-auto.quick", "bmad-build-auto.quick.gemini"])


if __name__ == "__main__":
    unittest.main()
