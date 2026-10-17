import io
import json
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from myfap import auth as module
from myfap.errors import ApiAppCheckError


def response(body, status=200):
    return Mock(status_code=status, json=Mock(return_value=body))


def identity(**changes):
    return {"rollnumber": "TEST000", "email": "sample@example.invalid", "authenKey": "fake-v2-key", "typeAcc": "student", **changes}


class VersionSelectionTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "session.json"

    def test_public_version_uses_parameter_then_session_then_v1(self):
        auth = module.MyFapAuth(session_file=self.path)
        self.assertEqual(auth.resolve_api_version(), "v1")
        self.path.write_text(json.dumps({"api_version": "v2"}), encoding="utf-8")
        self.assertEqual(auth.resolve_api_version(), "v2")
        explicit = module.MyFapAuth(api_version="v1", session_file=self.path)
        with patch.object(explicit.store, "read", side_effect=AssertionError("must not read")):
            self.assertEqual(explicit.resolve_api_version(), "v1")
        self.path.write_text("{}", encoding="utf-8")
        self.assertEqual(auth.resolve_api_version(), "v1")

    def test_public_version_never_restores_identity_handshakes_or_writes(self):
        self.path.write_text(json.dumps({"api_version": "v2", "authen_key": "private-fake-key"}), encoding="utf-8")
        before = self.path.read_bytes()
        auth = module.MyFapAuth(session_file=self.path)
        auth._restore, auth._handshake = Mock(), Mock()
        auth.session = Mock()
        self.assertEqual(auth.resolve_api_version(), "v2")
        self.assertIsNone(auth.authen_key)
        auth._restore.assert_not_called()
        auth._handshake.assert_not_called()
        auth.session.request.assert_not_called()
        self.assertEqual(self.path.read_bytes(), before)

    def test_invalid_stored_version_and_io_errors_are_safe(self):
        auth = module.MyFapAuth(session_file=self.path)
        for version in ("v3", "PRIVATE_SENTINEL", None, [], 2):
            with self.subTest(version=version):
                self.path.write_text(json.dumps({"api_version": version}), encoding="utf-8")
                with self.assertRaises(module.AuthError) as caught:
                    auth.resolve_api_version()
                self.assertNotIn("PRIVATE_SENTINEL", str(caught.exception))
        with patch.object(auth.store, "read", side_effect=module.SessionStoreError("PRIVATE_SENTINEL")):
            with self.assertRaises(module.AuthError) as caught:
                auth.resolve_api_version()
        self.assertNotIn("PRIVATE_SENTINEL", str(caught.exception))


class AuthV2Tests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "session.json"
        self.auth = module.MyFapAuth(campus="TEST", session_file=self.path, timeout=2.5)
        self.auth.authen_key, self.auth.mssv, self.auth.email = "fake-v1-key", "TEST000", "sample@example.invalid"
        self.auth.jwt_token, self.auth.refresh_token = "fake-feid-access", "fake-refresh"
        self.auth.subject, self.auth.login_nonce = "fake-subject", "fake-nonce"
        self.auth._oidc_validated = True
        self.auth.save_session()

    def stored(self):
        return json.loads(self.path.read_text(encoding="utf-8"))

    def target(self, version=None):
        auth = module.MyFapAuth(api_version=version, session_file=self.path, timeout=2.5)
        auth.session.request = Mock(return_value=response({"code": 200, "data": [identity()]}))
        auth.session.post = Mock(return_value=response({"code": 200, "data": [identity(authenKey="fake-v1-new-key")]}))
        return auth

    def test_version_change_handshakes_with_feid_before_persisting_v2_binding(self):
        auth = self.target("v2")
        before = self.path.read_bytes()

        def handshake(*args, **kwargs):
            self.assertEqual(self.path.read_bytes(), before)
            return response({"code": 200, "data": [identity()]})

        auth.session.request.side_effect = handshake
        self.assertTrue(auth.load_session())
        call = auth.session.request.call_args
        self.assertEqual(call.args[:2], ("POST", "https://fap-proxy.fpt.edu.vn/MyFAP/AuthenticationByFeId"))
        self.assertEqual(call.kwargs["params"], {})
        self.assertEqual(call.kwargs["json"], {"token": "fake-feid-access"})
        self.assertEqual(call.kwargs["headers"]["Authorization"], "Bearer fake-feid-access")
        self.assertEqual(call.kwargs["headers"]["CampusCode"], "TEST")
        self.assertEqual(call.kwargs["timeout"], 2.5)
        self.assertFalse(call.kwargs["allow_redirects"])
        self.assertNotIn("fake-v1-key", repr(call))
        self.assertEqual((self.stored()["api_version"], self.stored()["authen_key"]), ("v2", "fake-v2-key"))
        auth.ensure_bound(api_version="v2")
        auth.session.post.assert_not_called()

    def test_failed_v2_handshake_keeps_v1_session_without_fallback(self):
        auth = self.target("v2")
        auth.session.request.return_value = response({}, 503)
        before = self.path.read_bytes()
        with self.assertRaises(module.ApiError):
            auth.load_session()
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(auth._binding, ("TEST", "v1", "student"))
        with self.assertRaises(module.SessionBindingError):
            auth.ensure_bound(api_version="v2")
        auth.session.post.assert_not_called()

    def test_app_check_does_not_refresh_or_fallback(self):
        auth = self.target("v2")
        auth.session.request.return_value = response({"errorMessage": "APP_CHECK_FAILED"}, 403)
        auth._refresh_locked = Mock()
        before = self.path.read_bytes()
        with self.assertRaises(ApiAppCheckError):
            auth.load_session()
        auth._refresh_locked.assert_not_called()
        auth.session.post.assert_not_called()
        self.assertEqual(self.path.read_bytes(), before)

    def test_bound_v2_session_is_adopted_without_network(self):
        saved = self.stored()
        saved["api_version"] = "v2"
        self.path.write_text(json.dumps(saved), encoding="utf-8")
        auth = self.target()
        self.assertTrue(auth.load_session())
        self.assertEqual(auth.api_version, "v2")
        auth.ensure_bound(api_version="v2")
        auth.session.request.assert_not_called()
        auth.session.post.assert_not_called()

    def test_return_to_v1_handshakes_instead_of_reusing_v2_key(self):
        saved = self.stored()
        saved.update(api_version="v2", authen_key="fake-v2-key")
        self.path.write_text(json.dumps(saved), encoding="utf-8")
        auth = self.target("v1")
        self.assertTrue(auth.load_session())
        call = auth.session.post.call_args
        self.assertTrue(call.args[0].endswith("/AuthenticationByFeId"))
        self.assertEqual(call.kwargs["json"], {"token": "fake-feid-access"})
        self.assertNotIn("fake-v2-key", repr(call))
        self.assertEqual((self.stored()["api_version"], self.stored()["authen_key"]), ("v1", "fake-v1-new-key"))
        auth.session.request.assert_not_called()

    def test_version_switch_rejects_identity_change_for_same_campus(self):
        saved = self.stored()
        for stored_version, requested in (("v1", "v2"), ("v2", "v1")):
            for changed in ({"rollnumber": "OTHER000"}, {"email": "other@example.invalid"}):
                with self.subTest(version=requested, changed=changed):
                    self.path.write_text(json.dumps({**saved, "api_version": stored_version}), encoding="utf-8")
                    before = self.path.read_bytes()
                    auth = self.target(requested)
                    result = response({"code": 200, "data": [identity(**changed)]})
                    auth.session.post.return_value = auth.session.request.return_value = result
                    with self.assertRaises(module.AuthError):
                        auth.load_session()
                    self.assertEqual(self.path.read_bytes(), before)
                    self.assertEqual(auth._binding, ("TEST", stored_version, "student"))

    def test_legacy_unverified_feid_cannot_switch_versions(self):
        saved = self.stored()
        saved.pop("oidc_validated")
        self.path.write_text(json.dumps(saved), encoding="utf-8")
        auth = self.target("v2")
        with self.assertRaises(module.SessionBindingError):
            auth.load_session()
        auth.session.request.assert_not_called()
        auth.session.post.assert_not_called()

    def test_v2_handshake_requires_same_strict_identity_schema(self):
        for rows in ([identity(typeAcc="donor")], [identity(campusCode="WRONG")], [identity(), identity()], [identity(authenKey=None)], [identity(rollnumber=None)]):
            with self.subTest(rows=rows):
                before = self.path.read_bytes()
                auth = self.target("v2")
                auth.session.request.return_value = response({"code": 200, "data": rows})
                with self.assertRaises(module.AuthError):
                    auth.load_session()
                self.assertEqual(self.path.read_bytes(), before)

    def test_fresh_login_uses_explicit_version_then_saved_version_then_v1(self):
        for saved_version, selected, expected in (("v1", "v2", "v2"), ("v2", None, "v2"), ("v2", "v1", "v1"), (None, None, "v1")):
            with self.subTest(saved_version=saved_version, selected=selected):
                saved = self.stored()
                if saved_version is None:
                    saved.pop("api_version", None)
                else:
                    saved["api_version"] = saved_version
                self.path.write_text(json.dumps(saved), encoding="utf-8")
                auth = self.target(selected)
                oidc = Mock()
                oidc.begin_login.return_value = {"nonce": "fake-new-nonce", "code_verifier": "fake-verifier"}
                oidc.request_token.return_value = {"access_token": "fake-new-access", "refresh_token": "fake-new-refresh"}
                oidc.validate_tokens.return_value = {"sub": "fake-new-subject"}
                auth._authorize = Mock(return_value="fake-code")
                with patch.object(auth, "_oidc", return_value=oidc):
                    auth.login()
                self.assertEqual(self.stored()["api_version"], expected)
                self.assertEqual(auth.api_version, expected)
                self.assertEqual(self.stored()["oidc_nonce"], "fake-new-nonce")
                self.assertEqual(auth.session.request.call_count, int(expected == "v2"))
                self.assertEqual(auth.session.post.call_count, int(expected == "v1"))

    def test_fresh_login_handshake_rejection_explains_version_and_campus_choice(self):
        auth = self.target("v2")
        oidc = Mock()
        oidc.begin_login.return_value = {"nonce": "fake-new-nonce", "code_verifier": "fake-verifier"}
        oidc.request_token.return_value = {"access_token": "fake-new-access", "refresh_token": "fake-new-refresh"}
        oidc.validate_tokens.return_value = {"sub": "fake-new-subject"}
        auth._authorize = Mock(return_value="fake-code")
        auth.session.request.return_value = response({"code": 401, "data": None})
        before = self.path.read_bytes()

        with patch.object(auth, "_oidc", return_value=oidc):
            with self.assertRaises(module.AuthError) as caught:
                auth.login()

        message = str(caught.exception).lower()
        self.assertIn("v2", message)
        self.assertIn("--campus", message)
        self.assertIn("campuses", message)
        self.assertNotIn("hết hạn", message)
        self.assertEqual(auth.session.request.call_args.kwargs["headers"]["CampusCode"], "TEST")
        self.assertEqual(self.path.read_bytes(), before)

    def test_v2_refresh_persists_rotation_before_validation_and_handshake(self):
        saved = self.stored()
        saved["api_version"] = "v2"
        self.path.write_text(json.dumps(saved), encoding="utf-8")
        auth = self.target()
        self.assertTrue(auth.load_session())
        oidc = Mock()
        oidc.request_token.return_value = {"access_token": "fake-new-access", "refresh_token": "fake-new-refresh"}

        def validate(*args, **kwargs):
            self.assertEqual(self.stored()["refresh_token"], "fake-new-refresh")
            self.assertEqual(self.stored()["api_version"], "v2")
            self.assertTrue(self.stored()["fap_needs_reauth"])
            auth.session.request.assert_not_called()
            return None

        oidc.validate_tokens.side_effect = validate
        with patch.object(auth, "_oidc", return_value=oidc), redirect_stderr(io.StringIO()):
            self.assertTrue(auth.refresh_session())
        self.assertEqual(self.stored()["authen_key"], "fake-v2-key")
        oidc.validate_tokens.assert_called_once_with(oidc.request_token.return_value, "fake-nonce", expected_subject="fake-subject", refresh=True)

    def test_failed_switch_after_refresh_keeps_old_binding_and_rotated_feid(self):
        saved = self.stored()
        saved["access_token_expires_at"] = 1
        self.path.write_text(json.dumps(saved), encoding="utf-8")
        auth = self.target("v2")
        auth.session.request.return_value = response({}, 503)
        oidc = Mock()
        oidc.request_token.return_value = {"access_token": "fake-new-access", "refresh_token": "fake-new-refresh"}
        oidc.validate_tokens.return_value = None
        with patch.object(auth, "_oidc", return_value=oidc), redirect_stderr(io.StringIO()):
            self.assertFalse(auth.load_session())
        stored = self.stored()
        self.assertEqual(stored["api_version"], "v1")
        self.assertEqual(stored["refresh_token"], "fake-new-refresh")
        self.assertTrue(stored["fap_needs_reauth"])
        auth.session.post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
