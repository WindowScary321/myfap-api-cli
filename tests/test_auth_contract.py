import base64
import hashlib
import hmac
import io
import inspect
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

import requests
from typer.testing import CliRunner

from myfap import api as api_module
from myfap import auth as auth_module
from myfap.auth import MyFapAuth
from myfap.cli import app


RUNNER_OPTIONS = {"mix_stderr": False} if "mix_stderr" in inspect.signature(CliRunner).parameters else {}


def response(body, status=200):
    result = requests.Response()
    result.status_code = status
    result._content = json.dumps(body).encode()
    return result


class AuthContractTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.auth = MyFapAuth(campus="TEST&campus", session_file=Path(temporary.name) / "state.json")
        self.auth.authen_key = "fake+key/=&value"
        self.auth.mssv = "TEST000"
        self.auth.email = "sample@example.invalid"
        self.auth.jwt_token = "fake-access"
        self.auth.refresh_token = "fake-refresh"
        self.auth.subject = "fake-subject"
        self.auth.login_nonce = "fake-nonce"
        self.auth._oidc_validated = True
        self.auth.save_session()

    def assert_query(self, call, expected):
        url = call.args[0]
        self.assertEqual(urlsplit(url).query, "")
        self.assertEqual(call.kwargs["params"], expected)
        prepared = requests.Request("GET", url, params=call.kwargs["params"]).prepare()
        self.assertEqual(parse_qs(urlsplit(prepared.url).query), {key: [value] for key, value in expected.items()})

    def test_loading_bound_session_is_local_without_probe_or_refresh(self):
        self.auth.session.get = Mock()
        self.auth.session.post = Mock()
        self.auth.refresh_session = Mock()
        self.assertTrue(self.auth.load_session())
        self.auth.session.get.assert_not_called()
        self.auth.session.post.assert_not_called()
        self.auth.refresh_session.assert_not_called()

    def test_semesters_command_uses_raw_params(self):
        self.auth.session.get = Mock(return_value=response({"code": "200", "data": []}))
        with patch.object(api_module, "create_checksum", return_value="fake+/=="), patch("myfap.cli.get_auth", return_value=self.auth):
            result = CliRunner(**RUNNER_OPTIONS).invoke(app, ["semesters"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(self.auth.session.get.call_count, 1)
        self.assertTrue(self.auth.session.get.call_args.args[0].endswith("/GetSemester"))
        self.assert_query(self.auth.session.get.call_args, {
            "campusCode": "TEST&campus", "Authen": "fake+key/=&value", "checksum": "fake+/==",
        })
        self.assertFalse(self.auth.session.get.call_args.kwargs["allow_redirects"])

    def test_data_command_does_not_follow_redirect(self):
        self.auth.session.get = Mock(return_value=response({"code": "200", "data": []}, 302))
        self.auth.session.post = Mock()
        with patch("myfap.cli.get_auth", return_value=self.auth):
            result = CliRunner(**RUNNER_OPTIONS).invoke(app, ["info", "student", "--stdout"])
        self.assertEqual(result.exit_code, 1, result.output)
        self.assertEqual(result.stdout, "")
        self.assertIn("HTTP 302", result.stderr)
        self.assertTrue(self.auth.session.get.call_args.args[0].endswith("/GetStudentById"))
        self.assertFalse(self.auth.session.get.call_args.kwargs["allow_redirects"])
        self.auth.session.post.assert_not_called()

    def test_transient_data_failures_never_refresh(self):
        malformed = response({})
        malformed._content = b"not json"
        for failure in (
            requests.Timeout("private-url"), response({}, 503), response({}, 404), response([], 200), malformed,
            response({"errorMessage": "APP_CHECK_FAILED"}, 403),
            response({"errorMessage": "APP_CHECK_FAILED"}, 401),
        ):
            with self.subTest(failure=type(failure).__name__):
                self.auth.session.get = Mock(side_effect=failure) if isinstance(failure, Exception) else Mock(return_value=failure)
                self.auth.refresh_session = Mock(return_value=True)
                with patch("myfap.cli.get_auth", return_value=self.auth):
                    result = CliRunner(**RUNNER_OPTIONS).invoke(app, ["info", "student", "--stdout"])
                self.assertEqual(result.exit_code, 1, result.output)
                self.assertEqual(result.stdout, "")
                self.assertNotIn("private-url", result.stderr)
                self.assertNotIn("Chưa đăng nhập", result.stderr)
                self.assertTrue(self.auth.session.get.call_args.args[0].endswith("/GetStudentById"))
                self.assertEqual(self.auth.session.get.call_count, 1)
                self.auth.refresh_session.assert_not_called()

    def test_cli_reports_data_error_without_suggesting_expired_session(self):
        self.auth.session.get = Mock(return_value=response({}, 503))
        with patch("myfap.cli.get_auth", return_value=self.auth):
            result = CliRunner(**RUNNER_OPTIONS).invoke(app, ["info", "student", "--stdout"])
        self.assertEqual(result.exit_code, 1)
        self.assertEqual(result.stdout, "")
        self.assertIn("HTTP 503", result.stderr)
        self.assertNotIn("Chưa đăng nhập", result.stderr)
        self.assertTrue(self.auth.session.get.call_args.args[0].endswith("/GetStudentById"))

    def test_news_and_notification_201_do_not_invalidate_saved_session(self):
        before = self.auth.session_file.read_bytes()
        self.auth.refresh_session = Mock()
        cases = [(["news", "--stdout"], "GetTop10News"), (["other", "notification", "--stdout"], "GetNotificationByRoll")]
        for args, operation in cases:
            with self.subTest(operation=operation):
                self.auth.session.get = Mock(return_value=response({"code": "201", "data": None}))
                with patch("myfap.cli.get_auth", return_value=self.auth):
                    result = CliRunner(**RUNNER_OPTIONS).invoke(app, args)
                self.assertEqual(result.exit_code, 1, result.output)
                self.assertEqual(result.stdout, "")
                self.assertIn("201", result.stderr)
                self.assertNotIn("hết hạn", result.stderr)
                self.assertTrue(self.auth.session.get.call_args.args[0].endswith("/" + operation))
                self.auth.refresh_session.assert_not_called()
                self.assertEqual(self.auth.session_file.read_bytes(), before)
        self.auth.session.get = Mock(return_value=response({"code": "200", "data": []}))
        with patch("myfap.cli.get_auth", return_value=self.auth):
            result = CliRunner(**RUNNER_OPTIONS).invoke(app, ["info", "student", "--stdout"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(json.loads(result.stdout), {"code": "200", "data": []})

    def test_data_command_stdout_stays_json_after_actual_refresh(self):
        self.auth.session.get = Mock(side_effect=[
            response({}, 401),
            response({"code": "200", "data": []}),
        ])
        self.auth.session.post = Mock(return_value=response({"code": "200", "data": [{"authenKey": "fake-new-key", "rollnumber": "TEST000", "email": "sample@example.invalid", "typeAcc": "student"}]}))
        with patch("myfap.cli.get_auth", return_value=self.auth), patch.object(self.auth, "_oidc") as factory:
            factory.return_value.request_token.return_value = {"access_token": "fake-new-access", "refresh_token": "fake-new-refresh"}
            factory.return_value.validate_tokens.return_value = None
            result = CliRunner(**RUNNER_OPTIONS).invoke(app, ["schedule", "--semester", "Fall2026", "--stdout"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(json.loads(result.stdout), {"code": "200", "data": []})
        self.assertIn("thành công", result.stderr)
        self.assertEqual(self.auth.session.get.call_count, 2)
        self.assertTrue(all(call.args[0].endswith("/GetActivityStudent") for call in self.auth.session.get.call_args_list))
        self.assertEqual([call.kwargs["params"]["Authen"] for call in self.auth.session.get.call_args_list], ["fake+key/=&value", "fake-new-key"])
        self.assertEqual(self.auth.session.post.call_count, 1)
        self.assertEqual(json.loads(self.auth.session_file.read_text(encoding="utf-8"))["refresh_token"], "fake-new-refresh")

    def test_actual_data_request_retries_explicit_expiry_only_once(self):
        self.auth.session.get = Mock(return_value=response({}, 401))
        self.auth.refresh_session = Mock(return_value=True)
        with patch("myfap.cli.get_auth", return_value=self.auth):
            result = CliRunner(**RUNNER_OPTIONS).invoke(app, ["info", "student", "--stdout"])
        self.assertEqual(result.exit_code, 1, result.output)
        self.assertEqual(result.stdout, "")
        self.auth.refresh_session.assert_called_once_with()
        self.assertEqual(self.auth.session.get.call_count, 2)
        self.assertTrue(all(call.args[0].endswith("/GetStudentById") for call in self.auth.session.get.call_args_list))

    def test_refresh_handshake_uses_params_and_logs_only_to_stderr(self):
        self.auth.session.post = Mock(return_value=response({"code": "200", "data": [{"authenKey": "fake-new-key", "rollnumber": "TEST000", "email": "sample@example.invalid", "typeAcc": "student"}]}))
        out, err = io.StringIO(), io.StringIO()
        with patch.object(auth_module, "create_checksum", return_value="fake+/=="), patch.object(self.auth, "_oidc") as factory, redirect_stdout(out), redirect_stderr(err):
            factory.return_value.request_token.return_value = {"access_token": "fake-new-access", "refresh_token": "fake-new-refresh"}
            factory.return_value.validate_tokens.return_value = None
            self.assertTrue(self.auth.refresh_session())
        self.assertEqual(out.getvalue(), "")
        self.assertIn("thành công", err.getvalue())
        call = self.auth.session.post.call_args_list[0]
        self.assert_query(call, {"campusCode": "TEST&campus", "checksum": "fake+/=="})
        self.assertEqual(call.kwargs["json"], {"token": "fake-new-access"})

    def test_login_handshake_uses_params(self):
        self.auth.timeout = 2.5
        self.auth.session.post = Mock(return_value=response({"code": "200", "data": [{
            "authenKey": "fake-login-key", "rollnumber": "TEST000",
            "email": "sample@example.invalid", "typeAcc": "student",
        }]}))
        client = auth_module.OIDCClient(self.auth.session, timeout=2.5, issuer=auth_module.FEID_HOST,
                                       client_id=auth_module.CLIENT_ID, redirect_uri=auth_module.REDIRECT_URI)
        client._metadata = {"authorization_endpoint": auth_module.FEID_HOST + "/connect/authorize"}
        client.request_token = Mock(return_value={"access_token": "opaque-fake-access", "refresh_token": "fake-new-refresh"})
        client.validate_tokens = Mock(return_value={"sub": "fake-subject"})
        playwright = Mock()
        page = playwright.chromium.launch.return_value.new_context.return_value.new_page.return_value
        handlers = {}
        page.on.side_effect = lambda event, callback: handlers.update({event: callback})
        def navigate(url):
            state = parse_qs(urlsplit(url).query)["state"][0]
            callback = auth_module.REDIRECT_URI + "?code=fake-code&state=" + state
            handlers["request"](SimpleNamespace(url=callback))
            handlers["request"](SimpleNamespace(url=callback))
        page.goto.side_effect = navigate
        manager = Mock()
        manager.__enter__ = Mock(return_value=playwright)
        manager.__exit__ = Mock(return_value=False)
        with patch.object(auth_module, "sync_playwright", return_value=manager), patch.object(auth_module, "OIDCClient", return_value=client), patch.object(auth_module, "create_checksum", return_value="fake+/=="), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(self.auth.login(), ("fake-login-key", "TEST000"))
        self.assert_query(self.auth.session.post.call_args, {"campusCode": "TEST&campus", "checksum": "fake+/=="})
        self.assertEqual(self.auth.session.post.call_args.kwargs["timeout"], 2.5)
        client.validate_tokens.assert_called_once()
        for failure in (requests.Timeout("PRIVATE_SIGNATURE_SENTINEL"), ValueError("PRIVATE_SIGNATURE_SENTINEL")):
            self.auth.session.post = Mock(side_effect=failure)
            with patch.object(auth_module, "sync_playwright", return_value=manager), patch.object(auth_module, "OIDCClient", return_value=client), patch("myfap.cli.get_auth", return_value=self.auth):
                result = CliRunner(**RUNNER_OPTIONS).invoke(app, ["login", "--force"])
            self.assertEqual(result.exit_code, 1)
            self.assertEqual(result.stdout, "")
            self.assertNotIn("PRIVATE_SIGNATURE_SENTINEL", result.stderr)

    def test_invalid_session_diagnostic_is_stderr_only(self):
        self.auth.session_file.write_text("not json", encoding="utf-8")
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            self.assertFalse(self.auth.load_session())
        self.assertEqual(out.getvalue(), "")
        self.assertIn("JSON", err.getvalue())

    def test_survey_checksum_uses_own_key_normalized_username_and_vietnam_hour(self):
        clock = datetime(2026, 10, 14, 17, 30, tzinfo=timezone.utc)
        expected = base64.b64encode(hmac.new(
            b"survey-test-key", b"sample@example.invalidMYFAP15/10/2026 00:00", hashlib.sha1,
        ).digest()).decode()
        with patch.object(auth_module, "SURVEY_SECRET_KEY", "survey-test-key", create=True), patch.object(auth_module, "SECRET_KEY", "different-fap-key"), patch.object(auth_module, "datetime") as mocked_clock:
            mocked_clock.now.side_effect = lambda tz: clock.astimezone(tz)
            actual = getattr(auth_module, "create_survey_checksum", lambda value: "missing")("  Sample@Example.Invalid  ")
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
