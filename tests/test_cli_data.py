import json
import inspect
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock, patch

from ics import Calendar
from typer.testing import CliRunner

from myfap.cli import app


RUNNER_OPTIONS = {"mix_stderr": False} if "mix_stderr" in inspect.signature(CliRunner).parameters else {}


class DataCommandTests(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner(**RUNNER_OPTIONS)
        self.auth = SimpleNamespace(campus="APHL", load_session=Mock(return_value=True))
        self.auth_patch = patch("myfap.cli.get_auth", return_value=self.auth)
        self.auth_factory = self.auth_patch.start()
        self.addCleanup(self.auth_patch.stop)
        self.apis = {}
        for name in ("MyFapEssential", "MyFapClient", "MyFapOther"):
            api_patch = patch(f"myfap.cli.{name}")
            self.apis[name] = api_patch.start().return_value
            self.addCleanup(api_patch.stop)
        self.essential = self.apis["MyFapEssential"]
        self.client = self.apis["MyFapClient"]
        self.other = self.apis["MyFapOther"]
        self.essential.get_semesters.return_value = [
            {"semesterName": "Fall2026", "startDate": "2026-09-01"}
        ]
        self.essential.get_week.return_value = 20
        self.payload = {"code": "200", "data": []}

    def data_commands(self):
        return [
            (["schedule"], self.client.get_schedule),
            (["marks"], self.client.get_marks),
            (["marks", "--courseid", "123"], self.client.get_mark_by_course),
            (["exams"], self.client.get_exams),
            (["week-timetable"], self.client.get_schedule_by_week),
            (["attendance"], self.client.get_attendances),
            (
                ["attendance", "--subjectcode", "TEST101", "--classname", "DEMO01"],
                self.client.get_course_attendance,
            ),
            (["applications"], self.client.get_applications),
            (["news"], self.essential.get_news),
            (["info", "student"], self.client.get_student_info),
            (["info", "campus"], self.client.get_campus_info),
            (["other", "survey"], self.other.get_required_survey),
            (["other", "feedback"], self.other.check_open_feedback),
            (["other", "profile"], self.other.check_update_profile),
            (["other", "notification"], self.other.get_notification),
            (["other", "fee"], self.other.get_fee),
            (["other", "subjects"], self.other.get_subjects),
        ]

    def test_stdout_contains_only_json_for_all_data_commands(self):
        for args, request in self.data_commands():
            with self.subTest(command=args):
                request.return_value = self.payload
                result = self.runner.invoke(app, [*args, "--stdout"])
                self.assertEqual(result.exit_code, 0, result.output)
                self.assertEqual(json.loads(result.stdout), self.payload)

    def test_api_failures_go_to_stderr_for_all_data_commands(self):
        for args, request in self.data_commands():
            with self.subTest(command=args):
                request.side_effect = ValueError("API fixture failure")
                result = self.runner.invoke(app, [*args, "--stdout"])
                self.assertNotEqual(result.exit_code, 0)
                self.assertEqual(result.stdout, "")
                self.assertIn("API fixture failure", result.stderr)
                request.side_effect = None

    def test_missing_session_error_has_no_stdout(self):
        self.auth.load_session.return_value = False

        result = self.runner.invoke(app, ["schedule", "--stdout"])

        self.assertNotEqual(result.exit_code, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("myfap login", result.stderr)
        self.client.get_schedule.assert_not_called()

    def test_explicit_semester_skips_semester_lookup(self):
        self.client.get_schedule.return_value = self.payload

        result = self.runner.invoke(
            app, ["schedule", "--semester", "Spring2025", "--stdout"]
        )

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(json.loads(result.stdout), self.payload)
        self.client.get_schedule.assert_called_once_with("Spring2025")
        self.essential.get_semesters.assert_not_called()

    def test_resolver_uses_first_semester_and_logs_to_stderr(self):
        self.client.get_schedule.return_value = self.payload

        result = self.runner.invoke(app, ["schedule", "--stdout"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(json.loads(result.stdout), self.payload)
        self.client.get_schedule.assert_called_once_with("Fall2026")
        self.assertIn("Fall2026", result.stderr)

    def test_semester_api_failure_has_actionable_stderr(self):
        self.essential.get_semesters.side_effect = ValueError("startDate không hợp lệ")

        result = self.runner.invoke(app, ["schedule", "--stdout"])

        self.assertNotEqual(result.exit_code, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("startDate", result.stderr)
        self.assertIn("--semester", result.stderr)
        self.client.get_schedule.assert_not_called()

    def test_empty_semesters_have_actionable_stderr(self):
        self.essential.get_semesters.return_value = []

        result = self.runner.invoke(app, ["schedule", "--stdout"])

        self.assertNotEqual(result.exit_code, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("--semester", result.stderr)
        self.client.get_schedule.assert_not_called()

    def test_invalid_command_options_report_to_stderr(self):
        for args in (
            ["marks", "--pretty"],
            ["attendance", "--semester", "Fall2026", "--subjectcode", "TEST101"],
        ):
            with self.subTest(command=args):
                result = self.runner.invoke(app, [*args, "--stdout"])
                self.assertNotEqual(result.exit_code, 0)
                self.assertEqual(result.stdout, "")
                self.assertIn("Lỗi", result.stderr)

    def test_ics_stdout_is_a_clean_calendar(self):
        self.client.get_schedule.return_value = {"data": []}

        result = self.runner.invoke(app, ["schedule", "--ics", "--stdout"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue(result.stdout.startswith("BEGIN:VCALENDAR"))
        self.assertEqual(len(Calendar(result.stdout).events), 0)
        self.assertIn("Fall2026", result.stderr)

    def test_pretty_marks_keep_json_output(self):
        self.client.get_mark_by_course.return_value = {
            "code": "200",
            "data": "<table><tr><td>Demo</td><td>Item</td><td>8</td></tr></table>",
        }

        result = self.runner.invoke(
            app, ["marks", "--courseid", "123", "--pretty", "--stdout"]
        )

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(
            json.loads(result.stdout),
            {"code": "200", "data": [{"category": "Demo", "item": "Item", "value": "8"}]},
        )

    def test_tables_remain_on_stdout(self):
        self.essential.get_campuses.return_value = [
            {"campusName": "Demo campus", "campusCode": "DEMO"}
        ]
        for args, text in ((["campuses"], "Demo campus"), (["semesters"], "Fall2026")):
            with self.subTest(command=args):
                result = self.runner.invoke(app, args)
                self.assertEqual(result.exit_code, 0, result.output)
                self.assertIn(text, result.stdout)

    def test_date_infers_year_and_keeps_stdout_clean(self):
        self.client.get_schedule_by_week.return_value = self.payload

        result = self.runner.invoke(
            app, ["week-timetable", "--date", "2025-01-01", "--stdout"]
        )

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(json.loads(result.stdout), self.payload)
        self.essential.get_week.assert_called_once_with("2025-01-01")
        self.client.get_schedule_by_week.assert_called_once_with(20, "Fall2026", 2025)

    def test_explicit_year_overrides_date_year(self):
        self.client.get_schedule_by_week.return_value = self.payload

        result = self.runner.invoke(
            app,
            ["week-timetable", "--date", "2025-01-01", "--year", "2024", "--stdout"],
        )

        self.assertEqual(result.exit_code, 0, result.output)
        self.client.get_schedule_by_week.assert_called_once_with(20, "Fall2026", 2024)

    def test_explicit_week_skips_lookup_but_date_still_infers_year(self):
        self.client.get_schedule_by_week.return_value = self.payload

        result = self.runner.invoke(
            app,
            ["week-timetable", "--week", "3", "--date", "2025-01-01", "--stdout"],
        )

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(json.loads(result.stdout), self.payload)
        self.essential.get_week.assert_not_called()
        self.client.get_schedule_by_week.assert_called_once_with(3, "Fall2026", 2025)

    def test_invalid_date_never_loads_session_or_calls_api(self):
        for date in ("2025-02-29", "not-a-date", "2026-13-01"):
            for week_args in ([], ["--week", "3"]):
                with self.subTest(date=date, week=week_args):
                    result = self.runner.invoke(
                        app, ["week-timetable", "--date", date, *week_args, "--stdout"]
                    )
                    self.assertNotEqual(result.exit_code, 0)
                    self.assertEqual(result.stdout, "")
                    self.assertIn("YYYY-MM-DD", result.stderr)
        self.auth_factory.assert_not_called()
        self.essential.get_week.assert_not_called()
        self.client.get_schedule_by_week.assert_not_called()

    def test_no_date_uses_current_year(self):
        self.client.get_schedule_by_week.return_value = self.payload
        with patch("myfap.cli.datetime", wraps=datetime) as clock:
            clock.now.return_value = datetime(2024, 12, 31, 8, 0)

            result = self.runner.invoke(app, ["week-timetable", "--stdout"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.essential.get_week.assert_called_once_with("2024-12-31")
        self.client.get_schedule_by_week.assert_called_once_with(20, "Fall2026", 2024)


if __name__ == "__main__":
    unittest.main()
