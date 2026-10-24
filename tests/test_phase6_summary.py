"""Operation-specific semester summary reader; all responses are synthetic."""
import inspect
import json
import unittest

import requests

from myfap.summary import read_semester_marks_response


def response(payload, status=200):
    result = requests.Response()
    result.status_code = status
    result.encoding = "utf-8"
    result._content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return result


class SemesterSummaryReaderTests(unittest.TestCase):
    def test_raw_array_is_normalized_without_changing_data(self):
        data = [{"synthetic": "Tiếng Việt", "nested": [1, None]}]
        for version in ("v1", "v2"):
            with self.subTest(api_version=version):
                self.assertEqual(read_semester_marks_response(response(data), api_version=version),
                                 {"code": 200, "data": data})

    def test_envelope_is_preserved_and_json_string_array_is_normalized(self):
        payload = {"code": "200", "data": [{"synthetic": 1}], "message": None}
        self.assertEqual(read_semester_marks_response(response(payload), api_version="v2"), payload)
        self.assertEqual(read_semester_marks_response(response('[{"synthetic": 1}]'), api_version="v1"),
                         {"code": 200, "data": [{"synthetic": 1}]})

    def test_errors_are_not_converted_to_empty_arrays(self):
        from myfap.errors import ApiAppCheckError, ApiHTTPError, ApiOperationError, ApiSessionExpiredError
        cases = (
            (response([], 401), "v1", ApiSessionExpiredError),
            (response([], 403), "v2", ApiHTTPError),
            (response({"code": "APP_CHECK_FAILED"}, 401), "v2", ApiAppCheckError),
            (response({"code": 401, "data": None}), "v2", ApiSessionExpiredError),
            (response({"code": 201, "data": None}), "v1", ApiOperationError),
        )
        for value, version, expected in cases:
            with self.subTest(version=version, status=value.status_code):
                with self.assertRaises(expected):
                    read_semester_marks_response(value, api_version=version)

    def test_oversize_error_body_preserves_http_status_classification(self):
        from myfap.errors import ApiHTTPError, ApiSessionExpiredError
        for status, expected in ((401, ApiSessionExpiredError), (503, ApiHTTPError)):
            with self.subTest(status=status):
                with self.assertRaises(expected) as caught:
                    read_semester_marks_response(response("x" * (1024 * 1024 + 1), status), api_version="v2")
                self.assertEqual(caught.exception.status_code, status)

    def test_unknown_wrapper_malformed_or_oversize_payload_is_safe(self):
        from myfap.errors import ApiPayloadError
        for value in (None, True, {}, {"code": 200, "data": {}}, "PRIVATE [not json]", "<string>[]</string>"):
            with self.subTest(value=value), self.assertRaises(ApiPayloadError) as caught:
                read_semester_marks_response(response(value), api_version="v2")
            self.assertNotIn("PRIVATE", str(caught.exception))
        with self.assertRaises(ApiPayloadError):
            read_semester_marks_response(response("x" * (1024 * 1024 + 1)), api_version="v2")


class SemesterSummaryCommandTests(unittest.TestCase):
    def test_summary_has_exact_query_and_never_looks_up_semester(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from unittest.mock import patch
        from typer.testing import CliRunner
        from myfap.cli import app
        for version in ("v1", "v2"):
            with self.subTest(version=version), TemporaryDirectory() as directory:
                path = Path(directory) / "session.json"
                path.write_text(json.dumps({"campus": "TEST", "api_version": version,
                    "authen_key": "FAKE_KEY", "mssv": "TEST000", "email": "sample@example.invalid"}), encoding="utf-8")
                with patch("requests.Session.request", return_value=response([{"synthetic": True}])) as request:
                    result = CliRunner(**({"mix_stderr": False} if "mix_stderr" in inspect.signature(CliRunner).parameters else {})).invoke(app, ["--config", str(path), "marks", "--summary", "--stdout"])
                self.assertEqual(result.exit_code, 0, result.output)
                self.assertEqual(json.loads(result.stdout), {"code": 200, "data": [{"synthetic": True}]})
                request.assert_called_once()
                self.assertTrue(request.call_args.args[1].endswith("/GetSemesterMark"))
                self.assertEqual(request.call_args.kwargs["params"], {
                    "CampusCode": "TEST", "rollNumber": "TEST000", "Authen": "FAKE_KEY"})
                if version == "v2":
                    self.assertEqual(request.call_args.kwargs["headers"]["Authorization"], "Bearer FAKE_KEY")

    def test_conflicting_summary_options_fail_before_auth(self):
        from unittest.mock import patch
        from typer.testing import CliRunner
        from myfap.cli import app
        for options in (["--semester", "Fall2026"], ["--courseid", "DEMO"], ["--pretty"]):
            with self.subTest(options=options), patch("myfap.cli.get_auth") as auth:
                result = CliRunner(**({"mix_stderr": False} if "mix_stderr" in inspect.signature(CliRunner).parameters else {})).invoke(app, ["marks", "--summary", *options, "--stdout"])
            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("--summary", result.stderr)
            auth.assert_not_called()

    def test_summary_rebuilds_authen_after_single_refresh(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from unittest.mock import patch
        from typer.testing import CliRunner
        from myfap.cli import app
        for version in ("v1", "v2"):
            with self.subTest(version=version), TemporaryDirectory() as directory:
                path = Path(directory) / "session.json"
                path.write_text(json.dumps({"campus": "TEST", "api_version": version,
                    "authen_key": "FAKE_OLD", "mssv": "TEST000", "email": "sample@example.invalid"}), encoding="utf-8")
                def refresh(auth):
                    auth.authen_key = "FAKE_NEW"
                    return True
                expired = {"code": 201, "message": "Token invalid", "data": None} if version == "v1" else {"code": 401, "data": None}
                with patch("requests.Session.request", side_effect=[response(expired), response([])]) as request, \
                     patch("myfap.auth.MyFapAuth.refresh_session", autospec=True, side_effect=refresh) as rotation:
                    result = CliRunner(**({"mix_stderr": False} if "mix_stderr" in inspect.signature(CliRunner).parameters else {})).invoke(app, ["--config", str(path), "marks", "--summary", "--stdout"])
                self.assertEqual(result.exit_code, 0, result.output)
                self.assertEqual(request.call_count, 2)
                rotation.assert_called_once()
                self.assertEqual(request.call_args.kwargs["params"]["Authen"], "FAKE_NEW")
                self.assertNotIn("checksum", request.call_args.kwargs["params"])


if __name__ == "__main__":
    unittest.main()
