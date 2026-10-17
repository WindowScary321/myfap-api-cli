import inspect
from contextlib import ExitStack
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from ics import Calendar
from rich.text import Text
from typer.testing import CliRunner

from myfap.cli import app


RUNNER_OPTIONS = {"mix_stderr": False} if "mix_stderr" in inspect.signature(CliRunner).parameters else {}


class CommonOptionTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(os.environ))
        os.environ.pop("MYFAP_TIMEOUT", None)
        self.runner = CliRunner(**RUNNER_OPTIONS)
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.config = str(Path(temporary.name) / "fake-session.json")
        for name in ("MyFapAuth", "MyFapClient", "MyFapEssential", "MyFapOther"):
            factory = self.stack.enter_context(patch("myfap.cli." + name))
            setattr(self, name, factory)
        self.MyFapAuth.return_value.load_session.return_value = True
        self.MyFapAuth.return_value.api_version = "v1"
        self.MyFapAuth.return_value.campus = "HN"
        payload = {"code": "200", "data": []}
        self.MyFapEssential.return_value.get_semesters.return_value = [{"semesterName": "TestTerm"}]
        self.MyFapEssential.return_value.get_campuses.return_value = []
        self.MyFapClient.return_value.get_schedule.return_value = payload
        self.MyFapClient.return_value.get_student_info.return_value = payload
        self.MyFapClient.return_value.get_mark_by_course.return_value = payload
        self.MyFapClient.return_value.get_course_attendance.return_value = payload
        self.MyFapOther.return_value.get_fee.return_value = payload
        self.stack.enter_context(patch("requests.Session.request", side_effect=AssertionError("Offline test")))

    def options(self):
        return ["--api-version", "v2", "--campus", "HN", "--config", self.config, "--timeout", "2.5"]

    def assert_auth_options(self, **changes):
        expected = {"campus": "HN", "session_file": self.config, "api_version": "v2", "timeout": 2.5}
        expected.update(changes)
        self.assertEqual(self.MyFapAuth.call_args.kwargs, expected)

    def test_common_options_work_before_after_and_between_nested_commands(self):
        for command in (["login", "-f"], ["logout"], ["refresh"], ["schedule", "--ics", "--stdout"], ["info", "student", "--stdout"], ["other", "fee", "--stdout"]):
            placements = [self.options() + command, command + self.options()]
            if command[0] in ("info", "other"):
                placements.append([command[0], *self.options(), *command[1:]])
            for args in placements:
                with self.subTest(args=args):
                    result = self.runner.invoke(app, args)
                    self.assertEqual(result.exit_code, 0, result.output)
                    self.assert_auth_options()
                    if command[0] == "schedule":
                        Calendar(result.stdout)

    def test_deeper_explicit_values_override_parent_values(self):
        result = self.runner.invoke(app, ["--campus", "ROOT", "--timeout", "1", "--config", "root.json", "--api-version", "v1", "info", "--campus", "GROUP", "--timeout", "2", "student", "--stdout", *self.options()])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assert_auth_options()

    def test_last_value_wins_when_an_option_is_repeated(self):
        result = self.runner.invoke(app, ["login", "-f", "--api-version", "v1", "--timeout", "1", "-c", "OTHER", *self.options()])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assert_auth_options()

    def test_public_command_uses_trailing_options_without_reading_session(self):
        result = self.runner.invoke(app, ["campuses", *self.options()])
        self.assertEqual(result.exit_code, 0, result.output)
        self.MyFapEssential.assert_called_once_with(timeout=2.5, api_version="v2")
        self.MyFapAuth.assert_not_called()

    def test_aliases_and_equals_keep_existing_command_options(self):
        for command, expected_method in ((["marks", "-cid", "fake-course", "--stdout"], self.MyFapClient.return_value.get_mark_by_course), (["attendance", "-sc", "TEST101", "-cn", "TESTCLASS", "--semester", "TestTerm", "--stdout"], self.MyFapClient.return_value.get_course_attendance)):
            with self.subTest(command=command):
                result = self.runner.invoke(app, [*command, "-c", "HN", "--api-version=v2", "--timeout=2.5", "--config=" + self.config])
                self.assertEqual(result.exit_code, 0, result.output)
                self.assert_auth_options()
                expected_method.assert_called_once()

    def test_option_like_values_are_not_reinterpreted(self):
        with patch("myfap.cli.save_output") as save:
            result = self.runner.invoke(app, ["schedule", "--semester", "--timeout", "--output", "--api-version"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.MyFapClient.return_value.get_schedule.assert_called_once_with("--timeout")
        self.assertEqual(save.call_args.args[2], "--api-version")
        self.assertIsNone(self.MyFapAuth.call_args.kwargs["api_version"])

    def test_trailing_timeout_overrides_invalid_environment(self):
        with patch.dict(os.environ, {"MYFAP_TIMEOUT": "invalid"}):
            result = self.runner.invoke(app, ["login", "-f", "--timeout", "2.5"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(self.MyFapAuth.call_args.kwargs["timeout"], 2.5)

    def test_invalid_or_missing_options_fail_before_auth(self):
        for options in (["--api-version", "invalid"], ["--timeout", "nan"], ["--timeout", "-1"], ["--timeout"], ["--config"], ["--campus"], ["--api-version"]):
            with self.subTest(options=options):
                result = self.runner.invoke(app, ["login", "-f", *options])
                self.assertNotEqual(result.exit_code, 0)
                self.assertEqual(result.stdout, "")
                self.assertNotIn("Traceback", result.stderr)
                self.MyFapAuth.assert_not_called()

    def test_end_of_options_marker_is_preserved(self):
        result = self.runner.invoke(app, ["login", "--", "--api-version", "v2"])
        self.assertNotEqual(result.exit_code, 0)
        self.MyFapAuth.assert_not_called()

    def test_command_help_lists_common_options_without_auth(self):
        for command in (["schedule"], ["info"], ["info", "student"], ["other", "fee"]):
            with self.subTest(command=command):
                result = self.runner.invoke(app, [*command, "--help"])
                self.assertEqual(result.exit_code, 0, result.output)
                output = Text.from_ansi(result.stdout).plain
                for flag in ("--api-version", "--campus", "--config", "--timeout"):
                    self.assertIn(flag, output)
        self.MyFapAuth.assert_not_called()

    def test_common_options_do_not_leak_between_invocations(self):
        result = self.runner.invoke(app, ["login", "-f", *self.options()])
        self.assertEqual(result.exit_code, 0, result.output)
        result = self.runner.invoke(app, ["login", "-f"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(self.MyFapAuth.call_args.kwargs, {"campus": None, "session_file": None, "api_version": None, "timeout": None})
