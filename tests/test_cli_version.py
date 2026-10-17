import inspect
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from rich.text import Text
from typer.testing import CliRunner

from myfap.cli import app


RUNNER_OPTIONS = {"mix_stderr": False} if "mix_stderr" in inspect.signature(CliRunner).parameters else {}


class CLIVersionTests(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner(**RUNNER_OPTIONS)

    def test_global_version_reaches_login_and_nested_commands(self):
        for args in (["login", "--force"], ["info", "student", "--stdout"], ["other", "survey", "--stdout"]):
            with self.subTest(command=args), patch("myfap.cli.MyFapAuth") as factory, patch("myfap.cli.MyFapClient") as client, patch("myfap.cli.MyFapOther") as other:
                factory.return_value.load_session.return_value = True
                client.return_value.get_student_info.return_value = {"code": "200", "data": []}
                other.return_value.get_required_survey.return_value = {"code": "200", "data": []}
                result = self.runner.invoke(app, ["--api-version", "v2", *args])
                self.assertEqual(result.exit_code, 0, result.output)
                self.assertEqual(factory.call_args.kwargs["api_version"], "v2")

    def test_invalid_version_is_rejected_before_auth_and_http(self):
        with patch("myfap.cli.get_auth") as factory, patch("requests.Session.request") as request:
            result = self.runner.invoke(app, ["--api-version", "v3", "campuses"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("--api-version", Text.from_ansi(result.stderr).plain)
        factory.assert_not_called()
        request.assert_not_called()

    def test_version_state_does_not_leak_between_invocations(self):
        with patch("myfap.cli.MyFapAuth") as factory:
            for flags, expected in ((["--api-version", "v2"], "v2"), ([], None)):
                result = self.runner.invoke(app, [*flags, "login", "--force"])
                self.assertEqual(result.exit_code, 0, result.output)
                self.assertEqual(factory.call_args.kwargs["api_version"], expected)

    def test_public_campuses_resolves_explicit_then_saved_then_v1(self):
        with TemporaryDirectory() as temporary:
            config = Path(temporary) / "state.json"
            for stored, flags, expected in (("v2", [], "v2"), ("v2", ["--api-version", "v1"], "v1"), (None, [], "v1")):
                with self.subTest(stored=stored, flags=flags), patch("myfap.cli.MyFapEssential") as essential:
                    config.write_text(json.dumps({"api_version": stored} if stored else {}), encoding="utf-8")
                    essential.return_value.get_campuses.return_value = []
                    result = self.runner.invoke(app, ["--config", str(config), *flags, "campuses"])
                    self.assertEqual(result.exit_code, 0, result.output)
                    self.assertEqual(essential.call_args.kwargs["api_version"], expected)

    def test_public_version_errors_have_safe_stderr_without_traceback(self):
        with TemporaryDirectory() as temporary:
            config = Path(temporary) / "state.json"
            config.write_text('{"fake":', encoding="utf-8")
            with patch("requests.Session.request") as request:
                result = self.runner.invoke(app, ["--config", str(config), "campuses"])
            self.assertEqual(result.exit_code, 1)
            self.assertEqual(result.stdout, "")
            self.assertIn("Lỗi", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            request.assert_not_called()
