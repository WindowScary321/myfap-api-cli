import inspect
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

from typer.testing import CliRunner

from myfap.cli import app
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
        data = [{
            "semesterName": "Fall2026", "startDate": "2026-09-01",
            "termID": "ffffffff-ffff-ffff-ffff-ffffffffffff",
        }] if operation == "GetSemester" else []
        return response({"code": 200, "data": data})

    def test_unsupported_commands_report_operation_before_semester_or_week_lookup(self):
        cases = (
            (["marks"], "GetStudentMark"),
            (["marks", "--courseid", "DEMO"], "GetMarkByCourse"),
            (["exams"], "GetScheduleExam"),
            (["week-timetable"], "GetActivityStudentByWeek"),
            (["attendance"], "GetStudentAttendances"),
            (["attendance", "--subjectcode", "DEMO", "--classname", "DEMO"], "getCourseAttendance"),
        )
        original = self.path.read_bytes()
        for command, operation in cases:
            for semester in ([], ["--semester", "Fall2026"]):
                with self.subTest(command=command, semester=semester), patch("requests.Session.request", side_effect=self.reply) as request:
                    result = self.runner.invoke(app, ["--config", str(self.path), *command, *semester, "--stdout"])
                self.assertEqual(result.exit_code, 1, result.output)
                self.assertEqual(result.stdout, "")
                self.assertIn(operation, result.stderr)
                self.assertIn("chưa được hỗ trợ", result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                request.assert_not_called()
                self.assertEqual(self.path.read_bytes(), original)

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
