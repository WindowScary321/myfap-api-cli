import json
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from scripts import ci_scope


class ScopePolicyTests(unittest.TestCase):
    def test_repository_only_changes_skip_checks(self):
        for paths in ([], ["docs/Example.md"], ["tasks/phase0.md"],
                      ["docs/cli/Example.md", "docs/discovery/todo.md"],
                      ["docs/old.md", "docs/new.md", "tasks/todo.md"]):
            with self.subTest(paths=paths):
                self.assertFalse(ci_scope.paths_require_checks(paths))

    def test_code_and_mixed_changes_run_checks(self):
        for paths in (["myfap/api.py"], ["docs/Example.md", "tests/test_cli.py"],
                      ["README.md"], ["LICENSE"], ["MANIFEST.in"],
                      [".github/workflows/ci.yml"], ["docs_extra/file.py"], ["tasks.py"],
                      [".docs/file.py"], ["./docs/file.py"], ["docs\\file.py"]):
            with self.subTest(paths=paths):
                self.assertTrue(ci_scope.paths_require_checks(paths))

    def test_reusable_workflow_always_runs_including_empty_ref(self):
        with patch.object(ci_scope, "_git", side_effect=AssertionError("Không cần diff")):
            for event in ("pull_request", "push", "workflow_dispatch"):
                for ref in ("", "v0.2.0"):
                    with self.subTest(event=event, ref=ref):
                        self.assertTrue(ci_scope.code_changed(event, {}, {"ref": ref}))

    def test_docs_only_ready_requires_skipped_heavy_jobs(self):
        self.assertTrue(ci_scope.ready_succeeded("false", "success", ["skipped"] * 3))
        for state in ("failure", "cancelled", "success", ""):
            with self.subTest(state=state):
                self.assertFalse(ci_scope.ready_succeeded("false", "success", [state, "skipped", "skipped"]))

    def test_full_ready_rejects_failure_cancellation_and_unexpected_skip(self):
        self.assertTrue(ci_scope.ready_succeeded("true", "success", ["success"] * 3))
        for index in range(3):
            for state in ("failure", "cancelled", "skipped", ""):
                with self.subTest(index=index, state=state):
                    results = ["success"] * 3
                    results[index] = state
                    self.assertFalse(ci_scope.ready_succeeded("true", "success", results))

    def test_scope_failure_or_missing_output_cannot_pass_ready(self):
        for state in ("failure", "cancelled", "skipped", ""):
            self.assertFalse(ci_scope.ready_succeeded("false", state, ["skipped"] * 3))
        self.assertFalse(ci_scope.ready_succeeded("", "success", ["skipped"] * 3))

    def test_scope_cli_prints_only_boolean_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            event_file = Path(temporary) / "event.json"
            event_file.write_text("{}", encoding="utf-8")
            env = {"GITHUB_EVENT_NAME": "push", "GITHUB_EVENT_PATH": str(event_file),
                   "WORKFLOW_INPUTS": json.dumps({"ref": ""})}
            output = StringIO()
            with patch.dict(os.environ, env), patch("sys.argv", ["ci_scope.py", "scope"]), redirect_stdout(output):
                self.assertEqual(ci_scope.main(), 0)
            self.assertEqual(output.getvalue(), "code_changed=true\n")


class GitScopeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.git("init", "-q")
        self.git("config", "user.name", "CI fixture")
        self.git("config", "user.email", "ci@example.invalid")
        for name in ("myfap/api.py", "docs/old.md", "tasks/todo.md"):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("fixture\n", encoding="utf-8")
        self.base = self.commit()

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, stderr=subprocess.DEVNULL).decode().strip()

    def commit(self):
        self.git("add", ".")
        self.git("commit", "-qm", "fixture")
        return self.git("rev-parse", "HEAD")

    def changed(self, head, event="push"):
        payload = {"before": self.base, "after": head}
        if event == "pull_request":
            payload = {"pull_request": {"base": {"sha": self.base}, "head": {"sha": head}}}
        return ci_scope.code_changed(event, payload, {}, cwd=self.root)

    def test_docs_rename_and_tasks_delete_are_ignored(self):
        self.git("mv", "docs/old.md", "docs/new.md")
        self.git("rm", "tasks/todo.md")
        head = self.commit()
        self.assertFalse(self.changed(head))
        self.assertFalse(self.changed(head, "pull_request"))

    def test_rename_from_docs_into_code_runs_checks(self):
        self.git("mv", "docs/old.md", "myfap/new.py")
        self.assertTrue(self.changed(self.commit()))

    def test_rename_code_into_docs_still_runs_checks(self):
        self.git("mv", "myfap/api.py", "docs/api.md")
        self.assertTrue(self.changed(self.commit()))

    def test_pull_request_uses_merge_base_and_code_changes_run(self):
        (self.root / "myfap/api.py").write_text("updated\n", encoding="utf-8")
        self.assertTrue(self.changed(self.commit(), "pull_request"))

    def test_new_branch_runs_all_checks_and_invalid_sha_is_rejected(self):
        self.assertTrue(ci_scope.code_changed("push", {"before": "0" * 40, "after": self.base}, {}, cwd=self.root))
        with self.assertRaises(ValueError):
            ci_scope.code_changed("push", {"before": "--bad-ref", "after": self.base}, {}, cwd=self.root)


if __name__ == "__main__":
    unittest.main()
