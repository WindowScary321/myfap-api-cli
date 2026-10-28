"""Doctor public API: local-only by default, explicit bootstrap probe only."""
import json
import unittest
from unittest.mock import Mock, patch

import requests

from myfap import diagnostics, v2
from myfap.errors import ApiError, ApiPayloadError


class DoctorTests(unittest.TestCase):
    def test_local_defaults_do_not_construct_auth_or_touch_session_or_http(self):
        with patch("myfap.auth.MyFapAuth", side_effect=AssertionError("auth must stay offline")), \
             patch("myfap.storage.SessionStore.read", side_effect=AssertionError("no session read")), \
             patch("myfap.storage.SessionStore.lock", side_effect=AssertionError("no session lock")), \
             patch("requests.Session.request", side_effect=AssertionError("no network")):
            report = diagnostics.get_diagnostics()
        self.assertEqual(report["api_version"], "v2")
        self.assertEqual(report["api_version_source"], "default")
        self.assertIsNone(report["campus"])
        self.assertEqual(report["session_validation"], "not_checked")
        self.assertEqual(report["available_operations"], sorted(v2.SUPPORTED_OPERATIONS | {"GetRequiredSurvey"}))
        self.assertEqual(report["online_probe"], {"requested": False})
        self.assertIsInstance(report["package_version"], str)
        self.assertEqual(set(report), {"package_version", "api_version", "api_version_source", "campus", "available_operations", "session_validation", "online_probe"})
        json.dumps(report)

    def test_local_explicit_version_and_campus_use_only_supplied_values(self):
        with patch("requests.Session.request", side_effect=AssertionError("no network")):
            report = diagnostics.get_diagnostics(api_version="v2", campus="TEST", timeout=3)
        self.assertEqual(report["api_version"], "v2")
        self.assertEqual(report["api_version_source"], "explicit")
        self.assertEqual(report["campus"], "TEST")
        self.assertEqual(report["available_operations"], sorted(v2.SUPPORTED_OPERATIONS | {"GetRequiredSurvey"}))
        self.assertEqual(report["session_validation"], "not_checked")

    def test_invalid_inputs_and_online_v1_fail_before_client_or_http(self):
        for kwargs in ({"api_version": "v3"}, {"api_version": ""}, {"api_version": False},
                       {"campus": ""}, {"campus": "  "}, {"campus": "TEST\nPRIVATE"},
                       {"campus": 3}, {"api_version": "v1", "online": True}):
            with self.subTest(kwargs=kwargs), \
                 patch("myfap.api.MyFapEssential", side_effect=AssertionError("no client")), \
                 patch("requests.Session.request", side_effect=AssertionError("no network")):
                with self.assertRaises(ApiError):
                    diagnostics.get_diagnostics(**kwargs)

    def test_online_probe_is_v2_bootstrap_not_user_session_or_selected_campus_validation(self):
        for active in (True, False):
            active_response = Mock(status_code=200, json=Mock(return_value={"code": 200, "data": active, "private": "MUST_NOT_APPEAR"}))
            version_response = Mock(status_code=200, json=Mock(return_value={"code": 200, "data": "SYNTHETIC_BACKEND_VERSION", "private": "MUST_NOT_APPEAR"}))
            with self.subTest(active=active), patch("requests.Session.request", side_effect=[active_response, version_response]) as request, \
                 patch("myfap.auth.MyFapAuth", side_effect=AssertionError("no auth")):
                report = diagnostics.get_diagnostics(api_version="v2", campus="TEST", timeout=3, online=True)
            self.assertEqual(report["campus"], "TEST")
            self.assertEqual(report["session_validation"], "not_checked")
            self.assertEqual(report["online_probe"], {"requested": True, "operation": "GetApiActive", "bootstrap_campus": "HN", "api_active": active, "backend_version": "SYNTHETIC_BACKEND_VERSION", "scope": "proxy_bootstrap_only"})
            self.assertNotIn("MUST_NOT_APPEAR", json.dumps(report))
            self.assertEqual(request.call_count, 2)
            first, second = request.call_args_list
            self.assertEqual(first.args, ("POST", "https://fap-proxy.fpt.edu.vn/MyFAP/GetApiActive"))
            self.assertEqual(second.args, ("POST", "https://fap-proxy.fpt.edu.vn/MyFAP/GetVersion"))
            for call in (first, second):
                self.assertEqual(call.kwargs["headers"]["CampusCode"], "HN")
                self.assertEqual(call.kwargs["params"], {})
                self.assertEqual(call.kwargs["json"], {})
                self.assertEqual(call.kwargs["timeout"], 3)
                self.assertFalse(call.kwargs["allow_redirects"])

    def test_online_probe_rejects_non_boolean_payload_without_echoing_it(self):
        for value in (None, [], {}, 1, "true", "PRIVATE_PAYLOAD"):
            response = Mock(status_code=200, json=Mock(return_value={"code": 200, "data": value}))
            with self.subTest(value=value), patch("requests.Session.request", return_value=response) as request:
                with self.assertRaises(ApiPayloadError) as caught:
                    diagnostics.get_diagnostics(api_version="v2", online=True)
            self.assertNotIn("PRIVATE_PAYLOAD", str(caught.exception))
            request.assert_called_once()

    def test_online_probe_rejects_non_string_version_without_echoing_it(self):
        active_response = Mock(status_code=200, json=Mock(return_value={"code": 200, "data": True}))
        for value in (None, [], {}, 3, "", "   "):
            version_response = Mock(status_code=200, json=Mock(return_value={"code": 200, "data": value, "private": "PRIVATE_PAYLOAD"}))
            with self.subTest(value=value), patch("requests.Session.request", side_effect=[active_response, version_response]) as request:
                with self.assertRaises(ApiPayloadError) as caught:
                    diagnostics.get_diagnostics(api_version="v2", online=True)
            self.assertNotIn("PRIVATE_PAYLOAD", str(caught.exception))
            self.assertEqual(request.call_count, 2)

    def test_probe_network_failure_is_safe_and_not_retried(self):
        with patch("requests.Session.request", side_effect=requests.Timeout("PRIVATE_TOKEN")) as request:
            with self.assertRaises(ApiError) as caught:
                diagnostics.get_diagnostics(api_version="v2", online=True)
        request.assert_called_once()
        self.assertNotIn("PRIVATE_TOKEN", str(caught.exception))


class DoctorCommandTests(unittest.TestCase):
    def test_cli_local_does_not_load_auth_and_keeps_json_stdout(self):
        from typer.testing import CliRunner
        from myfap.cli import app
        with patch("myfap.cli.get_auth", side_effect=AssertionError("no auth")), \
             patch("requests.Session.request", side_effect=AssertionError("no network")):
            result = CliRunner().invoke(app, ["--config", "PRIVATE_PATH", "doctor", "--stdout"])
        self.assertEqual(result.exit_code, 0, result.output)
        report = json.loads(result.stdout)
        self.assertEqual(report["session_validation"], "not_checked")
        self.assertEqual(report["online_probe"], {"requested": False})
        self.assertNotIn("PRIVATE_PATH", result.output)

    def test_cli_online_is_explicit_and_does_not_use_session(self):
        from typer.testing import CliRunner
        from myfap.cli import app
        replies = [Mock(status_code=200, json=Mock(return_value={"code": 200, "data": True})),
                   Mock(status_code=200, json=Mock(return_value={"code": 200, "data": "SYNTHETIC_BACKEND_VERSION"}))]
        with patch("myfap.cli.get_auth", side_effect=AssertionError("no auth")), \
             patch("requests.Session.request", side_effect=replies) as request:
            result = CliRunner().invoke(app, ["doctor", "--api-version", "v2", "--online", "--stdout"])
        self.assertEqual(result.exit_code, 0, result.output)
        report = json.loads(result.stdout)["online_probe"]
        self.assertTrue(report["api_active"])
        self.assertEqual(report["backend_version"], "SYNTHETIC_BACKEND_VERSION")
        self.assertEqual(request.call_count, 2)


if __name__ == "__main__":
    unittest.main()
