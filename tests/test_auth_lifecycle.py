import io
import json
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from myfap import auth as module
from myfap.errors import ApiOperationError
from myfap.oidc import OAuthError


def response(body, status=200):
    return Mock(status_code=status, json=Mock(return_value=body))


def identity(**overrides):
    return {"rollnumber": "TEST000", "email": "sample@example.invalid", "authenKey": "new-fake-key", "typeAcc": "student", **overrides}


class AuthLifecycleTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "session.json"
        self.auth = module.MyFapAuth(campus="TEST", session_file=self.path, timeout=2.5)
        self.auth.authen_key = "old-fake-key"
        self.auth.mssv = "TEST000"
        self.auth.email = "sample@example.invalid"
        self.auth.account_type = "student"
        self.auth.subject = "fake-subject"
        self.auth.login_nonce = "fake-nonce"
        self.auth.jwt_token = "old-fake-access"
        self.auth.refresh_token = "old-fake-refresh"
        self.auth._oidc_validated = True
        self.auth.save_session()
        self.oidc_patch = patch.object(module, "OIDCClient", create=True)
        self.oidc = self.oidc_patch.start().return_value
        self.addCleanup(self.oidc_patch.stop)
        self.oidc.request_token.return_value = {"access_token": "new-fake-access", "refresh_token": "new-fake-refresh"}
        self.oidc.validate_tokens.return_value = None
        self.auth.session.post = Mock(return_value=response({"code": "200", "data": [identity()]}))

    def load_file(self):
        return json.loads(self.path.read_text(encoding="utf-8"))

    def refresh(self):
        with redirect_stderr(io.StringIO()):
            return self.auth.refresh_session()

    def test_legacy_session_adopts_saved_campus_and_v1_without_decoding_access(self):
        self.path.write_text(json.dumps({"authen_key": "fake", "mssv": "TEST000", "email": "sample@example.invalid", "campus": "SAVED", "jwt_token": "not-a-jwt"}), encoding="utf-8")
        auth = module.MyFapAuth(session_file=self.path)
        auth.session.get = Mock(return_value=response({"code": "200", "data": []}))
        self.assertTrue(auth.load_session())
        self.assertEqual(auth.campus, "SAVED")
        self.assertEqual(auth.api_version, "v1")
        self.assertEqual(auth.session.get.call_args.kwargs["params"]["campusCode"], "SAVED")

    def test_saving_subject_alone_does_not_mark_oidc_verified(self):
        self.auth._fap_ready = None
        self.auth._oidc_validated = False
        self.auth.save_session()
        self.assertFalse(self.load_file()["oidc_validated"])

    def test_probe_201_does_not_refresh_or_modify_session(self):
        before = self.path.read_bytes()
        self.auth.session.get = Mock(return_value=response({"code": "201", "data": None, "message": None}))
        self.auth.refresh_session = Mock()
        with self.assertRaises(ApiOperationError):
            self.auth.load_session()
        self.auth.refresh_session.assert_not_called()
        self.auth.session.post.assert_not_called()
        self.assertEqual(self.path.read_bytes(), before)

    def test_binding_is_checked_before_any_data_request(self):
        with self.assertRaises(module.SessionBindingError):
            self.auth.ensure_bound(campus="OTHER", api_version="v1", account_type="student")
        with self.assertRaises(module.SessionBindingError):
            self.auth.ensure_bound(campus="TEST", api_version="v2", account_type="student")
        with self.assertRaises(module.SessionBindingError):
            self.auth.ensure_bound(campus="TEST", api_version="v1", account_type="donor")
        self.auth.session.post.assert_not_called()

    def test_campus_change_handshakes_without_sending_old_fap_key(self):
        auth = module.MyFapAuth(campus="OTHER", session_file=self.path)
        auth.session.get = Mock()
        auth.session.post = Mock(return_value=response({"code": "200", "data": [identity(campusCode="OTHER")]}))
        self.assertTrue(auth.load_session())
        auth.session.get.assert_not_called()
        call = auth.session.post.call_args
        self.assertEqual(call.kwargs["params"]["campusCode"], "OTHER")
        self.assertNotIn("Authen", call.kwargs["params"])
        self.assertEqual(self.load_file()["campus"], "OTHER")

    def test_campus_change_failure_keeps_old_binding_and_credentials(self):
        before = self.path.read_bytes()
        auth = module.MyFapAuth(campus="OTHER", session_file=self.path)
        auth.session.get = Mock()
        auth.session.post = Mock(return_value=response({"code": "200", "data": [identity(campusCode="WRONG")]}))
        with self.assertRaises(module.AuthError):
            auth.load_session()
        auth.session.get.assert_not_called()
        self.assertEqual(self.path.read_bytes(), before)

    def test_version_change_is_blocked_until_adapter_exists(self):
        auth = module.MyFapAuth(api_version="v2", session_file=self.path)
        auth.session.get, auth.session.post = Mock(), Mock()
        with self.assertRaises(module.AuthError):
            auth.load_session()
        auth.session.get.assert_not_called()
        auth.session.post.assert_not_called()
        self.assertEqual(self.load_file()["api_version"], "v1")

    def test_recovery_refreshes_known_expired_access_before_handshake(self):
        saved = self.load_file()
        saved.update(authen_key=None, fap_needs_reauth=True, access_token_expires_at=1)
        self.path.write_text(json.dumps(saved), encoding="utf-8")
        self.auth._refresh_locked = Mock(return_value=True)
        self.assertTrue(self.auth.load_session())
        self.auth._refresh_locked.assert_called_once_with()
        self.auth.session.post.assert_not_called()

    def test_recovery_refreshes_once_on_explicit_handshake_401(self):
        saved = self.load_file()
        saved.update(authen_key=None, fap_needs_reauth=True)
        self.path.write_text(json.dumps(saved), encoding="utf-8")
        self.auth.session.post.return_value = response({}, 401)
        self.auth._refresh_locked = Mock(return_value=True)
        self.assertTrue(self.auth.load_session())
        self.auth._refresh_locked.assert_called_once_with()
        self.assertEqual(self.auth.session.post.call_count, 1)

    def test_refresh_rotation_is_persisted_before_validation_and_handshake(self):
        def validate(*args, **kwargs):
            stored = self.load_file()
            self.assertEqual(stored["refresh_token"], "new-fake-refresh")
            self.assertTrue(stored["fap_needs_reauth"])
            return {"sub": "fake-subject"}
        self.oidc.validate_tokens.side_effect = validate
        self.assertTrue(self.refresh())
        self.assertFalse(self.load_file()["fap_needs_reauth"])
        self.assertEqual(self.load_file()["authen_key"], "new-fake-key")
        self.oidc.validate_tokens.assert_called_once_with(self.oidc.request_token.return_value, "fake-nonce", expected_subject="fake-subject", refresh=True)

    def test_id_token_validation_failure_preserves_rotated_refresh_and_blocks_fap(self):
        self.oidc.validate_tokens.side_effect = OAuthError("Invalid test ID token", code="id_token")
        self.assertFalse(self.refresh())
        stored = self.load_file()
        self.assertEqual(stored["refresh_token"], "new-fake-refresh")
        self.assertTrue(stored["fap_needs_reauth"])
        self.auth.session.post.assert_not_called()
        with self.assertRaises(module.SessionBindingError):
            self.auth.ensure_bound(campus="TEST", api_version="v1", account_type="student")

    def test_handshake_failure_preserves_rotated_refresh_and_original_binding(self):
        self.auth.session.post.return_value = response({}, status=503)
        self.assertFalse(self.refresh())
        stored = self.load_file()
        self.assertEqual(stored["refresh_token"], "new-fake-refresh")
        self.assertEqual(stored["campus"], "TEST")
        self.assertTrue(stored["fap_needs_reauth"])

    def test_missing_rotated_token_keeps_old_and_unknown_expiry_stays_unknown(self):
        self.oidc.request_token.return_value = {"access_token": "new-fake-access"}
        self.assertTrue(self.refresh())
        stored = self.load_file()
        self.assertEqual(stored["refresh_token"], "old-fake-refresh")
        self.assertIsNone(stored["access_token_expires_at"])

    def test_failed_persist_stops_before_validation_and_handshake(self):
        before = self.path.read_bytes()
        with patch.object(self.auth.store, "write", side_effect=module.SessionStoreError("write failed")):
            self.assertFalse(self.refresh())
        self.assertEqual(self.path.read_bytes(), before)
        self.oidc.validate_tokens.assert_not_called()
        self.auth.session.post.assert_not_called()

    def test_refresh_rereads_after_lock_and_skips_already_rotated_token(self):
        newer = self.load_file()
        newer.update(authen_key="other-process-key", refresh_token="other-process-refresh", jwt_token="other-process-access")
        self.path.write_text(json.dumps(newer), encoding="utf-8")
        self.assertTrue(self.refresh())
        self.oidc.request_token.assert_not_called()
        self.assertEqual(self.auth.authen_key, "other-process-key")

    def test_refresh_rejects_concurrent_account_or_binding_changes(self):
        original = self.load_file()
        for changes in (
            {"oidc_subject": "other-subject"}, {"campus": "OTHER"}, {"api_version": "v2"},
            {"account_type": "donor"}, {"mssv": "OTHER000"}, {"email": "other@example.invalid"},
        ):
            with self.subTest(changes=tuple(changes)):
                self.auth._restore(original)
                newer = {**original, **changes, "authen_key": "other-process-key"}
                self.path.write_text(json.dumps(newer), encoding="utf-8")
                before = self.path.read_bytes()
                with self.assertRaises(module.SessionBindingError):
                    self.refresh()
                self.oidc.request_token.assert_not_called()
                self.auth.session.post.assert_not_called()
                self.assertEqual(self.path.read_bytes(), before)
                self.assertEqual(self.auth.subject, original["oidc_subject"])
                self.assertEqual(self.auth._binding, ("TEST", "v1", "student"))

    def test_refresh_does_not_recreate_session_deleted_by_other_process(self):
        self.path.unlink()
        with self.assertRaises(module.SessionBindingError):
            self.refresh()
        self.oidc.request_token.assert_not_called()
        self.assertFalse(self.path.exists())

    def _prepare_login(self, auth, before):
        self.oidc.begin_login.return_value = {"nonce": "new-fake-nonce", "code_verifier": "fake-verifier"}
        self.oidc.validate_tokens.return_value = {"sub": "new-fake-subject"}
        auth.session.post = Mock(return_value=response({"code": "200", "data": [identity()]}))

        def authorize(*args):
            self.assertEqual(self.path.read_bytes(), before)
            return "fake-code"

        auth._authorize = Mock(side_effect=authorize)

    def test_login_recovers_invalid_json_or_schema_only_after_success(self):
        for content in (
            '{"PRIVATE_SENTINEL":', '[]', '{}',
            '{"campus":"SAVED","authen_key":[]}',
            '{"campus":"SAVED","oidc_subject":42}',
        ):
            with self.subTest(content=content):
                self.path.write_text(content, encoding="utf-8")
                before = self.path.read_bytes()
                auth = module.MyFapAuth(session_file=self.path)
                self._prepare_login(auth, before)
                self.assertEqual(auth.login(), ("new-fake-key", "TEST000"))
                auth._authorize.assert_called_once()
                self.assertEqual(auth.campus, "APHL")
                self.assertEqual(self.load_file()["oidc_subject"], "new-fake-subject")

    def test_failed_login_preserves_invalid_session_bytes(self):
        for content in ('{"PRIVATE_SENTINEL":', '{"campus":"SAVED","authen_key":[]}'):
            with self.subTest(content=content):
                self.path.write_text(content, encoding="utf-8")
                before = self.path.read_bytes()
                auth = module.MyFapAuth(session_file=self.path)
                auth._authorize = Mock(side_effect=module.AuthError("Đã hủy đăng nhập."))
                self.oidc.begin_login.return_value = {"nonce": "fake-nonce"}
                with self.assertRaises(module.AuthError):
                    auth.login()
                auth._authorize.assert_called_once()
                self.assertEqual(self.path.read_bytes(), before)

    def test_login_does_not_ignore_session_path_or_permission_errors(self):
        with patch.object(self.auth.store, "read", side_effect=module.SessionStoreError("PRIVATE_SENTINEL")):
            with self.assertRaises(module.AuthError) as caught:
                self.auth.login()
        self.assertNotIn("PRIVATE_SENTINEL", str(caught.exception))
        self.oidc.begin_login.assert_not_called()

    def test_handshake_rejects_wrong_account_or_ambiguous_identity(self):
        for rows in ([identity(typeAcc="donor")], [identity(), identity()], [identity(email="other@example.invalid")], [identity(rollnumber="OTHER000")]):
            with self.subTest(rows_count=len(rows)):
                self.auth.session.post.return_value = response({"code": "200", "data": rows})
                self.assertFalse(self.refresh())


if __name__ == "__main__":
    unittest.main()
