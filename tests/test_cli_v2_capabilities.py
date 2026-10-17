import inspect
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

from typer.testing import CliRunner

from myfap.cli import app
from myfap.auth import MyFapAuth
from tests.test_api import response


RUNNER_OPTIONS = {"mix_stderr": False} if "mix_stderr" in inspect.signature(CliRunner).parameters else {}


class CLIV2CapabilityTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "session.json"
        self.path.write_text(json.dumps({
            "campus": "TEST", "api_version": "v2", "account_type": "student",
            "authen_key": "FAKE_V2_KEY", "mssv": "TEST000", "email": "test@example.invalid",
        }), encoding="utf-8")
        self.runner = CliRunner(**RUNNER_OPTIONS)

    @staticmethod
    def reply(method, url, **kwargs):
        operation = urlsplit(url).path.rsplit("/", 1)[-1]
        if operation == "GetSemester":
            data = [{
                "semesterName": "Fall2026", "startDate": "2026-09-01",
                "termID": "ffffffff-ffff-ffff-ffff-ffffffffffff",
            }]
        else:
            data = "42" if operation == "GetWeekByDate" else []
        return response({"code": 200, "data": data})

    @staticmethod
    def operations(request):
        return [urlsplit(call.args[1]).path.rsplit("/", 1)[-1] for call in request.call_args_list]

    def test_v2_existing_commands_without_semester_keep_json_and_only_call_proxy(self):
        cases = (
            (["marks", "--courseid", "DEMO"], "GetMarkByCourse"),
            (["applications"], "GetApplication"),
            (["news"], "GetTop10News"),
            (["info", "student"], "GetStudentById"),
            (["info", "campus"], "GetCampusInfo"),
            (["other", "feedback"], "CheckOpenFeedBack"),
            (["other", "profile"], "CheckUpdateProfile"),
            (["other", "notification"], "GetNotificationByRoll"),
            (["other", "fee"], "GeFeeByRoll"),
            (["other", "subjects"], "GetSubjets"),
        )
        original = self.path.read_bytes()
        for command, operation in cases:
            with self.subTest(command=command), patch("requests.Session.request", side_effect=self.reply) as request:
                result = self.runner.invoke(app, ["--config", str(self.path), *command, "--stdout"])
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertEqual(json.loads(result.stdout), {"code": 200, "data": []})
            self.assertEqual(self.operations(request), [operation])
            self.assertEqual(urlsplit(request.call_args.args[1]).netloc, "fap-proxy.fpt.edu.vn")
            self.assertEqual(request.call_args.kwargs["headers"]["Authorization"], "Bearer FAKE_V2_KEY")
            self.assertEqual(self.path.read_bytes(), original)

    def test_v2_semester_commands_skip_lookup_for_explicit_semester(self):
        cases = (
            (["schedule"], "GetActivityStudent"),
            (["marks"], "GetStudentMark"),
            (["exams"], "GetScheduleExam"),
            (["week-timetable", "--week", "42", "--year", "2026"], "GetActivityStudentByWeek"),
            (["attendance"], "GetStudentAttendances"),
            (["attendance", "--subjectcode", "DEMO", "--classname", "DEMO"], "GetCourseAttendance"),
        )
        original = self.path.read_bytes()
        for command, operation in cases:
            for explicit in (False, True):
                options = ["--semester", "Fall2026"] if explicit else []
                with self.subTest(command=command, explicit=explicit), patch("requests.Session.request", side_effect=self.reply) as request:
                    result = self.runner.invoke(app, ["--config", str(self.path), *command, *options, "--stdout"])
                self.assertEqual(result.exit_code, 0, result.output)
                self.assertEqual(json.loads(result.stdout), {"code": 200, "data": []})
                self.assertEqual(self.operations(request), [operation] if explicit else ["GetSemester", operation])
                self.assertEqual(request.call_args.kwargs["params"]["Semester"], "Fall2026")
                self.assertTrue(all(urlsplit(call.args[1]).netloc == "fap-proxy.fpt.edu.vn" for call in request.call_args_list))
                self.assertEqual(self.path.read_bytes(), original)

    def test_v2_week_lookup_uses_scalar_data_and_requested_date_year(self):
        with patch("requests.Session.request", side_effect=self.reply) as request:
            result = self.runner.invoke(app, ["--config", str(self.path), "week-timetable", "--date", "2026-10-17", "--stdout"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(json.loads(result.stdout), {"code": 200, "data": []})
        self.assertEqual(self.operations(request), ["GetWeekByDate", "GetSemester", "GetActivityStudentByWeek"])
        self.assertEqual(request.call_args.kwargs["params"]["week"], 42)
        self.assertEqual(request.call_args.kwargs["params"]["year"], 2026)

    def test_invalid_week_data_stops_before_semester_and_timetable_requests(self):
        for data in (True, None, [], {}, "not-a-week"):
            with self.subTest(data=data), patch("requests.Session.request", return_value=response({"code": 200, "data": data})) as request:
                result = self.runner.invoke(app, ["--config", str(self.path), "week-timetable", "--date", "2026-10-17", "--stdout"])
                self.assertEqual(result.exit_code, 1, result.output)
                self.assertEqual(result.stdout, "")
                self.assertIn("Số tuần trong response API không hợp lệ", result.stderr)
                self.assertEqual(self.operations(request), ["GetWeekByDate"])

    def test_v2_survey_keeps_separate_service_without_proxy_headers(self):
        with patch("requests.Session.request", side_effect=self.reply) as request:
            result = self.runner.invoke(app, ["--config", str(self.path), "other", "survey", "--stdout"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(json.loads(result.stdout), {"code": 200, "data": []})
        self.assertEqual(self.operations(request), ["GetRequiredSurvey"])
        self.assertEqual(urlsplit(request.call_args.args[1]).netloc, "survey.fpt.edu.vn")
        self.assertNotIn("headers", request.call_args.kwargs)
        self.assertIn("survey.fpt.edu.vn", result.stderr)
        self.assertIn("API v2", result.stderr)

    def test_missing_capability_stops_before_semester_or_week_lookup(self):
        from myfap import v2

        cases = (
            (["semesters"], "GetSemester"),
            (["schedule"], "GetActivityStudent"),
            (["marks"], "GetStudentMark"),
            (["marks", "--courseid", "DEMO"], "GetMarkByCourse"),
            (["exams"], "GetScheduleExam"),
            (["week-timetable"], "GetActivityStudentByWeek"),
            (["attendance"], "GetStudentAttendances"),
            (["attendance", "--subjectcode", "DEMO", "--classname", "DEMO"], "GetCourseAttendance"),
            (["applications"], "GetApplication"),
            (["news"], "GetTop10News"),
            (["info", "student"], "GetStudentById"),
            (["info", "campus"], "GetCampusInfo"),
            (["other", "feedback"], "CheckOpenFeedBack"),
            (["other", "profile"], "CheckUpdateProfile"),
            (["other", "notification"], "GetNotificationByRoll"),
            (["other", "fee"], "GeFeeByRoll"),
            (["other", "subjects"], "GetSubjets"),
        )
        original = self.path.read_bytes()
        for command, operation in cases:
            for explicit in (False, True):
                options = ["--api-version", "v2"] if explicit else []
                args = command if command == ["semesters"] else [*command, "--stdout"]
                with self.subTest(command=command, explicit=explicit), patch.object(v2, "SUPPORTED_OPERATIONS", v2.SUPPORTED_OPERATIONS - {operation}), patch.object(MyFapAuth, "load_session", side_effect=AssertionError("must not load session")) as load, patch("requests.Session.request") as request:
                    result = self.runner.invoke(app, ["--config", str(self.path), *args, *options])
                    self.assertEqual(result.exit_code, 1, result.output)
                    self.assertEqual(result.stdout, "")
                    self.assertIn("chưa được hỗ trợ", result.stderr)
                    self.assertIn(operation, result.stderr)
                    load.assert_not_called()
                    request.assert_not_called()
                    self.assertEqual(self.path.read_bytes(), original)

    def test_missing_capability_skips_session_handshake_and_token_refresh(self):
        from myfap import v2

        saved = json.loads(self.path.read_text(encoding="utf-8"))
        for stored_version in ("v1", "v2"):
            for expiry in (None, 1):
                with self.subTest(stored=stored_version, expiry=expiry):
                    self.path.write_text(json.dumps({
                        **saved, "api_version": stored_version, "fap_needs_reauth": True,
                        "jwt_token": "fake-access", "refresh_token": "fake-refresh",
                        "oidc_subject": "fake-subject", "oidc_nonce": "fake-nonce", "oidc_validated": True,
                        "access_token_expires_at": expiry,
                    }), encoding="utf-8")
                    original = self.path.read_bytes()
                    with patch.object(v2, "SUPPORTED_OPERATIONS", v2.SUPPORTED_OPERATIONS - {"GetApplication"}), patch("requests.Session.request") as request:
                        result = self.runner.invoke(app, ["--config", str(self.path), "--api-version", "v2", "applications", "--stdout"])
                    self.assertEqual(result.exit_code, 1, result.output)
                    self.assertIn("GetApplication", result.stderr)
                    request.assert_not_called()
                    self.assertEqual(self.path.read_bytes(), original)

    def test_v1_commands_are_independent_of_v2_capabilities(self):
        from myfap import v2

        saved = json.loads(self.path.read_text(encoding="utf-8"))
        self.path.write_text(json.dumps({**saved, "api_version": "v1"}), encoding="utf-8")
        for command in (["news"], ["info", "student"], ["other", "fee"]):
            with self.subTest(command=command), patch.object(v2, "SUPPORTED_OPERATIONS", frozenset()), patch("requests.Session.request", side_effect=self.reply) as request:
                result = self.runner.invoke(app, ["--config", str(self.path), *command, "--stdout"])
                self.assertEqual(result.exit_code, 0, result.output)
                self.assertEqual(json.loads(result.stdout), {"code": 200, "data": []})
                request.assert_called_once()
                self.assertNotEqual(urlsplit(request.call_args.args[1]).netloc, "fap-proxy.fpt.edu.vn")

    def test_supported_schedule_uses_semester_name_and_preserves_guid_metadata(self):
        with patch("requests.Session.request", side_effect=self.reply) as request:
            result = self.runner.invoke(app, ["--config", str(self.path), "schedule", "--stdout"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(json.loads(result.stdout), {"code": 200, "data": []})
        self.assertEqual([urlsplit(call.args[1]).path.rsplit("/", 1)[-1] for call in request.call_args_list],
                         ["GetSemester", "GetActivityStudent"])
        self.assertEqual(request.call_args.kwargs["params"]["Semester"], "Fall2026")


if __name__ == "__main__":
    unittest.main()
