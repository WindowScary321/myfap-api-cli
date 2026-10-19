"""Offline CLI regressions for invalid refresh grants and incomplete identity."""

import inspect
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

import requests
from typer.testing import CliRunner

from myfap.auth import AuthError, FEID_HOST, MyFapAuth
from myfap.cli import app
from myfap.storage import SessionStoreError


RUNNER_OPTIONS = {"mix_stderr": False} if "mix_stderr" in inspect.signature(CliRunner).parameters else {}
MISSING = object()


def response(body, status=200):
    result = requests.Response()
    result.status_code = status
    result._content = json.dumps(body).encode()
    return result


class AuthRecoveryTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "session.json"
        self.runner = CliRunner(**RUNNER_OPTIONS)
        self.calls = []
        self.token_failure = response({"error": "invalid_grant"}, 400)
        request_patch = patch.object(requests.Session, "request", autospec=True, side_effect=self.request)
        request_patch.start()
        self.addCleanup(request_patch.stop)

    def saved(self, version):
        return {
            "campus": "TEST", "api_version": version, "account_type": "student",
            "authen_key": "fake-key", "mssv": "TEST000", "email": "sample@example.invalid",
            "jwt_token": "fake-access", "refresh_token": "fake-refresh",
            "oidc_subject": "fake-subject", "oidc_nonce": "fake-nonce",
            "oidc_validated": True, "fap_needs_reauth": False,
        }

    def write(self, saved):
        self.path.write_text(json.dumps(saved), encoding="utf-8")
        self.calls.clear()
        return self.path.read_bytes()

    def invoke(self, *args):
        return self.runner.invoke(app, ["--config", str(self.path), *args])

    def request(self, session, method, url, **kwargs):
        operation = urlsplit(url).path.rsplit("/", 1)[-1]
        self.calls.append((method, operation))
        if operation == "openid-configuration":
            return response({
                "issuer": FEID_HOST, "authorization_endpoint": FEID_HOST + "/connect/authorize",
                "token_endpoint": FEID_HOST + "/connect/token", "jwks_uri": FEID_HOST + "/.well-known/jwks",
                "id_token_signing_alg_values_supported": ["RS256"], "code_challenge_methods_supported": ["S256"],
            })
        if operation == "token":
            if isinstance(self.token_failure, Exception):
                raise self.token_failure
            return self.token_failure
        if operation == "GetStudentById":
            return response({}, 401)
        raise AssertionError("Unexpected HTTP operation: " + operation)

    def test_expired_read_invalid_grant_requires_browser_for_normal_login(self):
        for version in ("v1", "v2"):
            with self.subTest(version=version):
                original = self.saved(version)
                self.write(original)
                read = self.invoke("info", "student", "--stdout")
                self.assertEqual(read.exit_code, 1, read.output)
                self.assertEqual(read.stdout, "")
                self.assertEqual([operation for _, operation in self.calls], ["GetStudentById", "openid-configuration", "token"])
                stored = json.loads(self.path.read_text(encoding="utf-8"))
                self.assertTrue(stored["fap_needs_reauth"])
                self.assertFalse(stored["oidc_validated"])
                for field in ("authen_key", "jwt_token", "refresh_token", "mssv", "email"):
                    self.assertEqual(stored[field], original[field])
                before_login = self.path.read_bytes()
                with patch.object(MyFapAuth, "_authorize", side_effect=AuthError("REVIEW_BROWSER_REQUESTED")) as browser:
                    login = self.invoke("login")
                browser.assert_called_once()
                self.assertEqual(login.exit_code, 1, login.output)
                self.assertIn("REVIEW_BROWSER_REQUESTED", login.stderr)
                self.assertEqual(self.path.read_bytes(), before_login)
                self.assertEqual(sum(operation == "token" for _, operation in self.calls), 1)
                self.assertNotIn("fake-refresh", read.stderr + login.stderr)

                # A failed replacement login also keeps the old (now flagged) session.
                with patch.object(MyFapAuth, "_authorize", return_value="fake-code") as browser:
                    failed_login = self.invoke("login")
                browser.assert_called_once()
                self.assertEqual(failed_login.exit_code, 1, failed_login.output)
                self.assertEqual(self.path.read_bytes(), before_login)
                self.assertEqual(sum(operation == "token" for _, operation in self.calls), 2)

    def test_transient_refresh_failures_do_not_invalidate_or_open_browser(self):
        for version in ("v1", "v2"):
            for failure in (
                requests.Timeout("PRIVATE_SENTINEL"), requests.ConnectionError("PRIVATE_SENTINEL"),
                response({}, 503), response({"error": "invalid_client"}, 400),
            ):
                with self.subTest(version=version, failure=type(failure).__name__):
                    before = self.write(self.saved(version))
                    self.token_failure = failure
                    read = self.invoke("info", "student", "--stdout")
                    self.assertEqual(read.exit_code, 1, read.output)
                    self.assertEqual(self.path.read_bytes(), before)
                    with patch.object(MyFapAuth, "_authorize") as browser:
                        login = self.invoke("login")
                    self.assertEqual(login.exit_code, 0, login.output)
                    browser.assert_not_called()
                    self.assertEqual(sum(operation == "token" for _, operation in self.calls), 1)
                    self.assertEqual(self.path.read_bytes(), before)
                    self.assertNotIn("PRIVATE_SENTINEL", read.stderr + login.stderr)

    def test_failed_invalid_grant_persist_does_not_corrupt_session_or_retry(self):
        for version in ("v1", "v2"):
            with self.subTest(version=version):
                before = self.write(self.saved(version))
                with patch("myfap.auth.SessionStore.write", side_effect=SessionStoreError("PRIVATE_SENTINEL")):
                    read = self.invoke("info", "student", "--stdout")
                self.assertEqual(read.exit_code, 1, read.output)
                self.assertEqual(self.path.read_bytes(), before)
                self.assertEqual(sum(operation == "token" for _, operation in self.calls), 1)
                self.assertNotIn("PRIVATE_SENTINEL", read.stderr)

    def test_missing_or_invalid_student_identity_blocks_reads_and_login_recovers(self):
        for version in ("v1", "v2"):
            for field in ("mssv", "email"):
                for value in (MISSING, None, "", "  ", False, 0, [], {}):
                    with self.subTest(version=version, field=field, value_type=type(value).__name__):
                        saved = self.saved(version)
                        if value is MISSING:
                            del saved[field]
                        else:
                            saved[field] = value
                        before = self.write(saved)
                        for command in (("info", "student", "--stdout"), ("other", "survey", "--stdout")):
                            read = self.invoke(*command)
                            self.assertEqual(read.exit_code, 1, read.output)
                            self.assertEqual(self.calls, [])
                            self.assertEqual(self.path.read_bytes(), before)
                        with patch.object(MyFapAuth, "_authorize", side_effect=AuthError("REVIEW_BROWSER_REQUESTED")) as browser:
                            login = self.invoke("login")
                        self.assertEqual(login.exit_code, 1, login.output)
                        browser.assert_called_once()
                        self.assertIn("REVIEW_BROWSER_REQUESTED", login.stderr)
                        self.assertEqual(self.path.read_bytes(), before)
                        self.assertEqual([operation for _, operation in self.calls], ["openid-configuration"])

    def test_complete_and_legacy_sessions_still_load_without_network(self):
        oauth_fields = ("jwt_token", "refresh_token", "oidc_subject", "oidc_nonce", "oidc_validated", "access_token_expires_at")
        for version in ("v1", "v2"):
            for legacy in (False, True):
                with self.subTest(version=version, legacy=legacy):
                    saved = self.saved(version)
                    if legacy:
                        for field in oauth_fields:
                            saved.pop(field, None)
                    before = self.write(saved)
                    with patch.object(MyFapAuth, "_authorize") as browser:
                        login = self.invoke("login")
                    self.assertEqual(login.exit_code, 0, login.output)
                    browser.assert_not_called()
                    self.assertEqual(self.calls, [])
                    self.assertEqual(self.path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
