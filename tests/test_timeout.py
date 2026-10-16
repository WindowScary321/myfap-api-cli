import inspect
import io
import json
import os
import subprocess
import sys
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

from typer.testing import CliRunner
from rich.text import Text

from myfap import api
from myfap.auth import MyFapAuth
from myfap.cli import app


RUNNER_OPTIONS = {"mix_stderr": False} if "mix_stderr" in inspect.signature(CliRunner).parameters else {}


def response(data):
    return SimpleNamespace(status_code=200, json=lambda: data)


class TimeoutTests(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner(**RUNNER_OPTIONS)
        env_patch = patch.dict(os.environ, {}, clear=False)
        env_patch.start()
        self.addCleanup(env_patch.stop)
        os.environ.pop("MYFAP_TIMEOUT", None)

    def test_global_option_reaches_public_and_nested_data_requests(self):
        for args in (["campuses"], ["info", "student", "--stdout"], ["other", "survey", "--stdout"]):
            with self.subTest(command=args), TemporaryDirectory() as temporary:
                session_file = Path(temporary) / "session.json"
                session_file.write_text(json.dumps({"authen_key": "fake-key", "mssv": "TEST000", "email": "test@example.invalid", "campus": "APHL"}), encoding="utf-8")
                with patch("requests.Session.get", return_value=response({"code": "200", "data": []})) as request:
                    result = self.runner.invoke(app, ["--timeout", "2.5", "--config", str(session_file), *args])
                self.assertEqual(result.exit_code, 0, result.output)
                self.assertTrue(request.called)
                self.assertTrue(all(call.kwargs["timeout"] == 2.5 for call in request.call_args_list))

    def test_flag_overrides_invalid_environment_and_state_does_not_leak(self):
        with patch.dict(os.environ, {"MYFAP_TIMEOUT": "invalid"}), patch("requests.Session.get", return_value=response({"code": "200", "data": []})) as request:
            result = self.runner.invoke(app, ["--timeout", "4", "campuses"])
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertEqual(request.call_args.kwargs["timeout"], 4)
        with patch("requests.Session.get", return_value=response({"code": "200", "data": []})) as request:
            result = self.runner.invoke(app, ["campuses"])
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertEqual(request.call_args.kwargs["timeout"], 10)

    def test_environment_is_read_per_invocation(self):
        for value in ("1.25", "45"):
            with self.subTest(value=value), patch.dict(os.environ, {"MYFAP_TIMEOUT": value}), patch("requests.Session.get", return_value=response({"code": "200", "data": []})) as request:
                result = self.runner.invoke(app, ["campuses"])
                self.assertEqual(result.exit_code, 0, result.output)
                self.assertEqual(request.call_args.kwargs["timeout"], float(value))

    def test_invalid_timeout_is_rejected_before_network(self):
        for value in ("0", "-1", "nan", "inf", "-inf", "1e309", "invalid", ""):
            for use_env in (True, False):
                with self.subTest(value=value, env=use_env), patch("requests.Session.get") as request:
                    env = {"MYFAP_TIMEOUT": value} if use_env else {}
                    args = ["campuses"] if use_env else ["--timeout", value, "campuses"]
                    with patch.dict(os.environ, env):
                        result = self.runner.invoke(app, args)
                    self.assertNotEqual(result.exit_code, 0)
                    self.assertEqual(result.stdout, "")
                    self.assertNotIn("Traceback", result.stderr)
                    self.assertTrue(result.stderr)
                    request.assert_not_called()

    def test_invalid_environment_does_not_break_help_import(self):
        result = subprocess.run(
            [sys.executable, "-c", "from myfap.cli import app; app()", "--help"],
            env={**os.environ, "MYFAP_TIMEOUT": "invalid", "PYTHONUTF8": "1", "FORCE_COLOR": "1"},
            capture_output=True, text=True, encoding="utf-8", timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--timeout", Text.from_ansi(result.stdout).plain)
        self.assertNotIn("Traceback", result.stderr)

    def test_auth_preserves_defaults_and_honors_environment_for_data_and_refresh(self):
        for value in (None, "2.5"):
            with self.subTest(value=value), TemporaryDirectory() as temporary:
                if value is not None:
                    os.environ["MYFAP_TIMEOUT"] = value
                auth = MyFapAuth(session_file=Path(temporary) / "session.json")
                auth.authen_key, auth.refresh_token = "fake-key", "fake-refresh"
                auth.mssv, auth.email = "TEST000", "test@example.invalid"
                auth.subject, auth.login_nonce = "test-subject", "test-nonce"
                auth._oidc_validated = True
                auth.save_session()
                auth.session.get = Mock(return_value=response({"code": "200", "data": []}))
                self.assertTrue(auth.load_session())
                auth.session.get.assert_not_called()
                api.MyFapEssential(auth).get_semesters()
                self.assertEqual(auth.session.get.call_count, 1)
                self.assertEqual(auth.session.get.call_args.kwargs["timeout"], 10 if value is None else 2.5)
                auth.session.post = Mock(return_value=response({"code": "200", "data": [{
                    "authenKey": "fake-new-key", "rollnumber": "TEST000", "email": "test@example.invalid", "typeAcc": "student",
                }]}))
                with patch("myfap.auth.OIDCClient.request_token", return_value={"access_token": "fake-access"}) as token_request, \
                     patch("myfap.auth.OIDCClient.validate_tokens", return_value={"sub": "test-subject"}), \
                     redirect_stderr(io.StringIO()):
                    self.assertEqual(auth._oidc().timeout, 10 if value is None else 2.5)
                    self.assertTrue(auth.refresh_session())
                token_request.assert_called_once()
                self.assertEqual(token_request.call_args.args[0]["grant_type"], "refresh_token")
                self.assertEqual(auth.session.post.call_count, 1)
                self.assertEqual(auth.session.post.call_args.kwargs["timeout"], 10 if value is None else 2.5)

    def test_programmatic_auth_and_public_client_honor_override(self):
        with patch.dict(os.environ, {"MYFAP_TIMEOUT": "invalid"}):
            auth = MyFapAuth(timeout=7.5)
            self.assertEqual(auth.timeout, 7.5)
            essential = api.MyFapEssential(timeout=8.5)
            essential.session.get = Mock(return_value=response({"code": "200", "data": []}))
            essential.get_campuses()
            self.assertEqual(essential.session.get.call_args.kwargs["timeout"], 8.5)

    def test_api_groups_inherit_auth_timeout_and_keep_subjects_floor(self):
        for value in (2.5, 45):
            auth = SimpleNamespace(timeout=value, campus="TEST", mssv="TEST000", authen_key="fake-key", email="test@example.invalid", session=Mock())
            auth.session.get.return_value = response({"code": "200", "data": []})
            for cls, method, args in (
                (api.MyFapEssential, "get_semesters", ()),
                (api.MyFapOther, "get_required_survey", ()),
                (api.MyFapClient, "get_schedule", ("Fall2026",)),
                (api.MyFapOther, "get_subjects", ()),
            ):
                with self.subTest(value=value, method=method):
                    getattr(cls(auth), method)(*args)
                    self.assertEqual(auth.session.get.call_args.kwargs["timeout"], max(value, 30) if method == "get_subjects" else value)


if __name__ == "__main__":
    unittest.main()
