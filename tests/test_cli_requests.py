"""Command-level request traces with an actual auth/client and fake HTTP."""

import inspect
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch
from urllib.parse import urlsplit

from typer.testing import CliRunner

from myfap.auth import MyFapAuth
from myfap.cli import app


RUNNER_OPTIONS = {"mix_stderr": False} if "mix_stderr" in inspect.signature(CliRunner).parameters else {}


class CommandRequestTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "session.json"
        self.path.write_text(json.dumps({
            "campus": "TEST", "authen_key": "fake-key", "mssv": "TEST000",
            "email": "sample@example.invalid",
        }), encoding="utf-8")
        self.auth = MyFapAuth(session_file=self.path)
        self.auth.session.get = Mock(side_effect=self.response)
        auth_patch = patch("myfap.cli.get_auth", return_value=self.auth)
        auth_patch.start()
        self.addCleanup(auth_patch.stop)
        self.runner = CliRunner(**RUNNER_OPTIONS)

    def response(self, url, **kwargs):
        operation = urlsplit(url).path.rsplit("/", 1)[-1]
        data = [{"semesterName": "Fall2026", "startDate": "2026-09-01"}] if operation == "GetSemester" else []
        return Mock(status_code=200, json=Mock(return_value={"code": "200", "data": data}))

    def operations(self):
        return [urlsplit(call.args[0]).path.rsplit("/", 1)[-1] for call in self.auth.session.get.call_args_list]

    def test_commands_without_semester_do_not_fetch_semesters(self):
        cases = (
            (["info", "student"], "GetStudentById"),
            (["info", "campus"], "GetCampusInfo"),
            (["applications"], "GetApplication"),
            (["news"], "GetTop10News"),
            (["marks", "--courseid", "123"], "GetMarkByCourse"),
            (["other", "survey"], "GetRequiredSurvey"),
            (["other", "feedback"], "CheckOpenFeedBack"),
            (["other", "profile"], "CheckUpdateProfile"),
            (["other", "notification"], "GetNotificationByRoll"),
            (["other", "fee"], "GeFeeByRoll"),
            (["other", "subjects"], "GetSubjets"),
        )
        for args, operation in cases:
            with self.subTest(command=args):
                self.auth.session.get.reset_mock()
                result = self.runner.invoke(app, [*args, "--stdout"])
                self.assertEqual(result.exit_code, 0, result.output)
                self.assertEqual(self.operations(), [operation])
                self.assertEqual(json.loads(result.stdout), {"code": "200", "data": []})

    def test_explicit_semester_skips_lookup_and_implicit_semester_fetches_once(self):
        for args, operation in (
            (["schedule"], "GetActivityStudent"),
            (["marks"], "GetStudentMark"),
            (["exams"], "GetScheduleExam"),
            (["attendance"], "GetStudentAttendances"),
            (["week-timetable", "--week", "3"], "GetActivityStudentByWeek"),
        ):
            for explicit in (False, True):
                with self.subTest(command=args, explicit=explicit):
                    self.auth.session.get.reset_mock()
                    options = ["--semester", "Fall2026"] if explicit else []
                    result = self.runner.invoke(app, [*args, *options, "--stdout"])
                    self.assertEqual(result.exit_code, 0, result.output)
                    expected = [operation] if explicit else ["GetSemester", operation]
                    self.assertEqual(self.operations(), expected)

    def test_semesters_command_fetches_only_once(self):
        result = self.runner.invoke(app, ["semesters"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(self.operations(), ["GetSemester"])

    def test_existing_login_loads_locally_without_claiming_server_validation(self):
        result = self.runner.invoke(app, ["login"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.auth.session.get.assert_not_called()
        self.assertNotIn("session hợp lệ", result.stderr)
