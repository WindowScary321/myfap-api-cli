import copy
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

import requests

from myfap import api


FIXTURES = json.loads((Path(__file__).parent / "fixtures" / "api_responses.json").read_text(encoding="utf-8"))


def response(payload=None, status=200):
    return SimpleNamespace(status_code=status, json=Mock(return_value=copy.deepcopy(payload)), text="PRIVATE_BODY_SENTINEL")


class ApiContractTests(unittest.TestCase):
    def setUp(self):
        self.session = Mock()
        self.auth = SimpleNamespace(session=self.session, campus="TEST&campus", mssv="TEST+ROLL", authen_key="FAKE+AUTH&=", email="  USER+Test@EXAMPLE.INVALID  ")
        self.session.get.return_value = response({"code": "200", "data": []})

    def test_all_v1_operations_use_params_with_exact_case_and_raw_values(self):
        base = {"campusCode": self.auth.campus, "Authen": self.auth.authen_key, "checksum": "FAKE+/CHECKSUM="}
        student = {**base, "rollNumber": self.auth.mssv}
        cases = [
            (api.MyFapEssential, "get_campuses", (), "GetAllActiveCampus", {}, []),
            (api.MyFapEssential, "get_semesters", (), "GetSemester", base, []),
            (api.MyFapEssential, "get_week", ("2026-10-14",), "GetWeekByDate", {"date": "2026-10-14"}, 42),
            (api.MyFapEssential, "get_news", (2,), "GetTop10News", {**base, "type": 2}, []),
            (api.MyFapOther, "check_open_feedback", (), "CheckOpenFeedBack", student, []),
            (api.MyFapOther, "check_update_profile", (), "CheckUpdateProfile", student, []),
            (api.MyFapOther, "get_notification", (), "GetNotificationByRoll", student, []),
            (api.MyFapOther, "get_fee", (), "GeFeeByRoll", student, []),
            (api.MyFapOther, "get_subjects", (), "GetSubjets", base, []),
            (api.MyFapClient, "get_schedule", ("Fall&2026",), "GetActivityStudent", {**student, "Semester": "Fall&2026"}, []),
            (api.MyFapClient, "get_marks", ("Fall&2026",), "GetStudentMark", {**student, "Semester": "Fall&2026"}, []),
            (api.MyFapClient, "get_mark_by_course", ("FAKE+COURSE",), "GetMarkByCourse", {**student, "CourseId": "FAKE+COURSE"}, "<table></table>"),
            (api.MyFapClient, "get_exams", ("Fall&2026",), "GetScheduleExam", {**student, "Semester": "Fall&2026"}, []),
            (api.MyFapClient, "get_schedule_by_week", (42, "Fall&2026", 2026), "GetActivityStudentByWeek", {**student, "Semester": "Fall&2026", "week": 42, "year": 2026}, []),
            (api.MyFapClient, "get_attendances", ("Fall&2026",), "GetStudentAttendances", {**student, "Semester": "Fall&2026"}, []),
            (api.MyFapClient, "get_course_attendance", ("Fall&2026", "TEST+SUBJECT", "Class & One"), "getCourseAttendance", {**student, "Semester": "Fall&2026", "SubjectCode": "TEST+SUBJECT", "ClassName": "Class & One"}, []),
            (api.MyFapClient, "get_applications", (), "GetApplication", student, []),
            (api.MyFapClient, "get_student_info", (), "GetStudentById", student, []),
            (api.MyFapClient, "get_campus_info", (), "GetCampusInfo", student, []),
        ]
        with patch("myfap.api.create_checksum", return_value="FAKE+/CHECKSUM="):
            for cls, name, args, route, params, payload in cases:
                with self.subTest(operation=name):
                    self.session.get.return_value = response({"code": "200", "data": payload})
                    getattr(cls(self.auth), name)(*args)
                    call = self.session.get.call_args
                    self.assertEqual(call.args, (f"{api.FAP_HOST}/{route}",))
                    self.assertEqual(call.kwargs.get("params", {}), params)
                    prepared = requests.Request("GET", call.args[0], params=call.kwargs.get("params")).prepare()
                    self.assertEqual(parse_qs(urlsplit(prepared.url).query), {k: [str(v)] for k, v in params.items()})
                    self.assertEqual(call.kwargs["timeout"], max(api.DEFAULT_TIMEOUT, 30.0) if name == "get_subjects" else api.DEFAULT_TIMEOUT)

    def test_checksum_identifiers_follow_v1_operations(self):
        cases = [(api.MyFapEssential, "get_semesters", (), api.MAGIC_ID), (api.MyFapOther, "get_subjects", (), api.MAGIC_ID), (api.MyFapEssential, "get_news", (2,), "2"), (api.MyFapClient, "get_schedule", ("Fall2026",), self.auth.mssv)]
        with patch("myfap.api.create_checksum", return_value="FAKE") as checksum:
            for cls, name, args, identifier in cases:
                with self.subTest(operation=name):
                    getattr(cls(self.auth), name)(*args)
                    checksum.assert_called_with(identifier, self.auth.campus)

    def test_survey_uses_separate_checksum_and_normalized_username(self):
        self.session.get.return_value = response(FIXTURES["survey_success"])
        with patch("myfap.api.create_survey_checksum", return_value="FAKE+/SURVEY=", create=True) as checksum:
            result = api.MyFapOther(self.auth).get_required_survey()
        checksum.assert_called_once_with("user+test@example.invalid")
        self.assertEqual(result, FIXTURES["survey_success"])
        self.assertEqual(self.session.get.call_args.args, ("https://survey.fpt.edu.vn/API/myFAP/GetRequiredSurvey",))
        self.assertEqual(self.session.get.call_args.kwargs["params"], {"username": "user+test@example.invalid", "checksum": "FAKE+/SURVEY="})

    def test_survey_not_found_preserves_exact_envelope(self):
        self.session.get.return_value = response(FIXTURES["survey_not_found"])
        self.assertEqual(api.MyFapOther(self.auth).get_required_survey(), FIXTURES["survey_not_found"])

    def test_survey_rejects_other_404_bodies(self):
        for body in ({"code": "404", "message": "Session expired", "data": None}, {"code": "404", "message": "Data Not Found", "data": []}):
            with self.subTest(body=body):
                self.session.get.return_value = response(body)
                with self.assertRaises(Exception):
                    api.MyFapOther(self.auth).get_required_survey()

    def test_survey_rejects_blank_username(self):
        self.auth.email = "   "
        with self.assertRaises(Exception):
            api.MyFapOther(self.auth).get_required_survey()
        self.session.get.assert_not_called()

    def test_transport_error_does_not_expose_url_or_credential(self):
        self.session.get.side_effect = requests.Timeout("PRIVATE_QUERY_SENTINEL")
        with self.assertRaises(api.ApiError) as error:
            api.MyFapOther(self.auth).get_fee()
        self.assertNotIn("PRIVATE_QUERY_SENTINEL", str(error.exception))

    def test_fee_preserves_paid_and_unpaid_rows_and_numeric_amounts(self):
        self.session.get.return_value = response(FIXTURES["fee_success"])
        self.assertEqual(api.MyFapOther(self.auth).get_fee(), FIXTURES["fee_success"])

    def test_fee_http_404_is_error(self):
        self.session.get.return_value = response(status=404)
        with self.assertRaisesRegex(Exception, "HTTP 404") as error:
            api.MyFapOther(self.auth).get_fee()
        self.assertNotIn("PRIVATE_BODY_SENTINEL", str(error.exception))

    def test_semesters_use_dates_and_keep_server_order_for_ties(self):
        self.session.get.return_value = response(FIXTURES["semesters"])
        semesters = api.MyFapEssential(self.auth).get_semesters()
        self.assertEqual([s["semesterName"] for s in semesters], ["Fall2026", "Fall2026 second", "Spring2026"])

    def test_invalid_or_missing_semester_date_requires_explicit_semester(self):
        for date in (None, "", "nonsense", "2026-02-30", 123):
            with self.subTest(date=date):
                self.session.get.return_value = response({"code": "200", "data": [{"semesterName": "Test", "startDate": date}]})
                with self.assertRaisesRegex(Exception, "--semester"):
                    api.MyFapEssential(self.auth).get_semesters()

    def test_semesters_accept_iso_dates_and_timestamps(self):
        self.session.get.return_value = response({"code": "200", "data": [{"semesterName": "Older", "startDate": "2026-01-05T00:00:00"}, {"semesterName": "Newer", "startDate": "2026-09-07"}]})
        self.assertEqual([s["semesterName"] for s in api.MyFapEssential(self.auth).get_semesters()], ["Newer", "Older"])


class ResponseValidationTests(unittest.TestCase):
    def test_valid_success_preserves_payload_types(self):
        for value in ([], {}, None, 42, "<table>&lt;test&gt;</table>"):
            with self.subTest(value=value):
                payload = {"code": "200", "data": value}
                self.assertEqual(api.read_response(response(payload)), payload)

    def test_invalid_envelopes_are_rejected(self):
        for payload in ([], None, "PRIVATE_BODY_SENTINEL", 42, {}, {"code": "200"}, {"data": []}, {"code": True, "data": []}, {"code": [], "data": []}):
            with self.subTest(payload=payload):
                with self.assertRaises(api.ApiPayloadError) as error:
                    api.read_response(response(payload))
                self.assertNotIn("PRIVATE_BODY_SENTINEL", str(error.exception))

    def test_json_errors_have_safe_error(self):
        malformed = response()
        malformed.json.side_effect = ValueError("PRIVATE_BODY_SENTINEL")
        with self.assertRaises(api.ApiPayloadError) as error:
            api.read_response(malformed)
        self.assertNotIn("PRIVATE_BODY_SENTINEL", str(error.exception))

    def test_body_errors_and_app_check_are_distinct(self):
        for code, expected in ((201, api.ApiSessionExpiredError), ("APP_CHECK_FAILED", api.ApiAppCheckError), ("404", api.ApiError), (500, api.ApiError)):
            with self.subTest(code=code):
                with self.assertRaises(expected) as error:
                    api.read_response(response({"code": code, "message": "PRIVATE_BODY_SENTINEL", "data": None}))
                self.assertNotIn("PRIVATE_BODY_SENTINEL", str(error.exception))

    def test_http_errors_preserve_status_and_do_not_leak_response(self):
        for status in (401, 403, 404, 500, 503):
            with self.subTest(status=status):
                failed = response(status=status)
                with self.assertRaises(api.ApiHTTPError) as error:
                    api.read_response(failed)
                self.assertEqual(error.exception.status_code, status)
                self.assertNotIn("PRIVATE_BODY_SENTINEL", str(error.exception))

    def test_app_check_error_message_is_distinct_with_or_without_success_status(self):
        for status in (200, 403):
            for payload in ({"errorMessage": "APP_CHECK_FAILED"}, {"code": "APP_CHECK_FAILED"}):
                with self.subTest(status=status, payload=payload):
                    with self.assertRaises(api.ApiAppCheckError):
                        api.read_response(response(payload, status))

    def test_malformed_http_error_body_does_not_hide_http_status(self):
        failed = response(status=503)
        failed.json.side_effect = ValueError("PRIVATE_BODY_SENTINEL")
        with self.assertRaises(api.ApiHTTPError) as error:
            api.read_response(failed)
        self.assertEqual(error.exception.status_code, 503)
        self.assertNotIn("PRIVATE_BODY_SENTINEL", str(error.exception))

    def test_only_survey_not_found_option_permits_observed_body(self):
        with self.assertRaises(api.ApiError):
            api.read_response(response(FIXTURES["survey_not_found"]))
        self.assertEqual(api.read_response(response(FIXTURES["survey_not_found"]), allow_survey_not_found=True), FIXTURES["survey_not_found"])

    def test_campuses_http_failure_is_not_empty_data(self):
        essential = api.MyFapEssential()
        essential.session = Mock(get=Mock(return_value=response(status=500)))
        with self.assertRaises(api.ApiHTTPError):
            essential.get_campuses()

    def test_list_operations_reject_non_list_data(self):
        auth = SimpleNamespace(session=Mock(), campus="TEST", authen_key="FAKE")
        for method in ("get_campuses", "get_semesters"):
            with self.subTest(method=method):
                auth.session.get.return_value = response({"code": "200", "data": "PRIVATE_BODY_SENTINEL"})
                with self.assertRaises(api.ApiPayloadError):
                    getattr(api.MyFapEssential(auth), method)()


if __name__ == "__main__":
    unittest.main()
