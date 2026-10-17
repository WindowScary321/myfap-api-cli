import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import requests

from myfap import api
from tests.test_api import response


class VersionedApiTests(unittest.TestCase):
    def setUp(self):
        self.session = Mock()
        self.session.request.side_effect = lambda method, url, **kwargs: getattr(self.session, method.lower())(url, **kwargs)
        self.auth = SimpleNamespace(
            session=self.session, campus="TEST", api_version="v2", account_type="student",
            authen_key="FAKE_OLD_KEY", mssv="TEST+ROLL", email=" USER@EXAMPLE.INVALID ",
            ensure_bound=Mock(), refresh_session=Mock(return_value=True), timeout=2.5,
        )
        self.session.get.return_value = response({"code": 200, "data": []})
        self.session.post.return_value = response({"code": 200, "data": []})

    def test_legacy_client_default_and_explicit_v1_keep_v1_get_contract(self):
        legacy = SimpleNamespace(session=self.session, campus="TEST", mssv="TEST+ROLL", authen_key="FAKE_KEY")
        for kwargs in ({}, {"api_version": "v1"}):
            with self.subTest(kwargs=kwargs):
                api.MyFapClient(legacy, **kwargs).get_schedule("Fall2026")
                call = self.session.get.call_args
                self.assertEqual(call.args[0], f"{api.FAP_HOST}/GetActivityStudent")
                self.assertEqual(call.kwargs["params"]["Authen"], "FAKE_KEY")
        self.session.post.assert_not_called()

    def test_version_override_must_match_binding_before_http(self):
        for cls in (api.MyFapEssential, api.MyFapClient, api.MyFapOther):
            with self.subTest(cls=cls):
                with self.assertRaises(api.ApiError):
                    cls(self.auth, api_version="v1")
        self.session.get.assert_not_called()
        self.session.post.assert_not_called()

    def test_invalid_versions_are_rejected_without_http(self):
        for value in ("v3", "V2", "", 2):
            with self.subTest(value=value):
                with self.assertRaises(api.ApiError):
                    api.MyFapEssential(api_version=value)
        self.session.get.assert_not_called()
        self.session.post.assert_not_called()

    def test_v2_bootstrap_uses_post_without_session_key_or_auto_detection(self):
        essential = api.MyFapEssential(self.auth)
        self.assertEqual(essential.get_campuses(), [])
        self.session.get.assert_not_called()
        self.session.post.assert_called_once()
        call = self.session.post.call_args
        self.assertEqual(call.args[0], "https://fap-proxy.fpt.edu.vn/MyFAP/GetAllActiveCampus")
        self.assertEqual(call.kwargs["json"], {})
        self.assertEqual(call.kwargs.get("params", {}), {})
        self.assertNotEqual(call.kwargs["headers"]["Authorization"], "Bearer FAKE_OLD_KEY")
        self.assertEqual(call.kwargs["timeout"], 2.5)

    def test_v2_public_client_can_be_selected_without_auth(self):
        essential = api.MyFapEssential(api_version="v2", timeout=4)
        essential.session = self.session
        self.assertEqual(essential.get_campuses(), [])
        self.assertEqual(self.session.post.call_args.kwargs["timeout"], 4)
        with self.assertRaises(api.ApiError):
            essential.get_semesters()

    def test_proxy_diagnostic_is_explicit_and_v2_only(self):
        essential = api.MyFapEssential(self.auth)
        self.session.post.return_value = response({"code": 200, "data": True})
        self.assertEqual(essential.get_api_active(), {"code": 200, "data": True})
        self.assertTrue(self.session.post.call_args.args[0].endswith("/GetApiActive"))
        self.session.post.assert_called_once()
        legacy = api.MyFapEssential()
        legacy.session = Mock()
        with self.assertRaises(api.ApiError):
            legacy.get_api_active()
        legacy.session.get.assert_not_called()
        legacy.session.post.assert_not_called()

    def test_v2_semesters_have_empty_query_and_preserve_guid_order_by_start_date(self):
        semesters = [
            {"termID": "ffffffff-ffff-ffff-ffff-ffffffffffff", "startDate": "2026-01-01"},
            {"termID": "00000000-0000-0000-0000-000000000000", "startDate": "2026-09-01"},
        ]
        self.session.get.return_value = response({"code": 200, "data": semesters})
        result = api.MyFapEssential(self.auth).get_semesters()
        self.assertEqual([item["termID"] for item in result], [semesters[1]["termID"], semesters[0]["termID"]])
        self.assertEqual(self.session.get.call_count, 1)
        call = self.session.get.call_args
        self.assertTrue(call.args[0].endswith("/GetSemester"))
        self.assertEqual(call.kwargs["params"], {})
        self.assertEqual(call.kwargs["headers"]["Authorization"], "Bearer FAKE_OLD_KEY")
        self.assertEqual(call.kwargs["headers"]["CampusCode"], "TEST")

    def test_v2_schedule_uses_header_key_exact_parameter_case_and_existing_output(self):
        self.session.get.return_value = response({"code": 200, "data": [{"subjectName": "A &amp; B"}]})
        result = api.MyFapClient(self.auth, api_version="v2").get_schedule("Fall&2026")
        self.assertEqual(result, {"code": 200, "data": [{"subjectName": "A & B"}]})
        call = self.session.get.call_args
        self.assertEqual(call.args[0], "https://fap-proxy.fpt.edu.vn/MyFAP/GetActivityStudent")
        self.assertEqual(call.kwargs["params"], {"CampusCode": "TEST", "rollNumber": "TEST+ROLL", "Semester": "Fall&2026"})
        self.assertEqual(call.kwargs["headers"]["Authorization"], "Bearer FAKE_OLD_KEY")
        self.assertEqual(call.kwargs["timeout"], 2.5)
        self.auth.ensure_bound.assert_called_with(campus="TEST", api_version="v2", account_type="student")

    def test_existing_read_wrappers_use_v2_contracts_and_preserve_output(self):
        student = {"CampusCode": "TEST", "rollNumber": "TEST+ROLL"}
        with_semester = {**student, "Semester": "Fall2026"}
        with_authen = {**student, "Authen": "FAKE_OLD_KEY"}
        cases = (
            (api.MyFapEssential, "get_week", ("2026-10-17",), "GetWeekByDate", {"date": "2026-10-17"}, "42"),
            (api.MyFapEssential, "get_news", (), "GetTop10News", {"CampusCode": "TEST", "type": 1}, []),
            (api.MyFapClient, "get_marks", ("Fall2026",), "GetStudentMark", with_semester, [{"courseID": 123, "averageMark": "8.0"}]),
            (api.MyFapClient, "get_mark_by_course", ("DEMO",), "GetMarkByCourse", {**student, "CourseId": "DEMO"}, "<table><tr><td>TEST</td></tr></table>"),
            (api.MyFapClient, "get_exams", ("Fall2026",), "GetScheduleExam", with_semester, []),
            (api.MyFapClient, "get_schedule_by_week", (42, "Fall2026", 2026), "GetActivityStudentByWeek", {**with_semester, "week": 42, "year": 2026}, []),
            (api.MyFapClient, "get_attendances", ("Fall2026",), "GetStudentAttendances", with_semester, []),
            (api.MyFapClient, "get_course_attendance", ("Fall2026", "DEMO", "CLASS"), "GetCourseAttendance", {**with_semester, "SubjectCode": "DEMO", "ClassName": "CLASS"}, []),
            (api.MyFapClient, "get_applications", (), "GetApplication", with_authen, []),
            (api.MyFapClient, "get_student_info", (), "GetStudentById", student, [{"fixture": "student"}]),
            (api.MyFapClient, "get_campus_info", (), "GetCampusInfo", student, [{"fixture": "campus"}]),
            (api.MyFapOther, "check_open_feedback", (), "CheckOpenFeedBack", with_authen, True),
            (api.MyFapOther, "check_update_profile", (), "CheckUpdateProfile", with_authen, False),
            (api.MyFapOther, "get_notification", (), "GetNotificationByRoll", with_authen, []),
            (api.MyFapOther, "get_fee", (), "GeFeeByRoll", student, [
                {"IsPaid": True, "invoice": "FAKE-PAID", "amount": 1000},
                {"IsPaid": False, "invoice": "FAKE-UNPAID", "amount": "2000.50"},
            ]),
            (api.MyFapOther, "get_subjects", (), "GetSubjets", {"CampusCode": "TEST"}, []),
        )
        for cls, method, args, operation, query, data in cases:
            with self.subTest(method=method):
                payload = {"code": 200, "data": data}
                self.session.get.return_value = response(payload)
                result = getattr(cls(self.auth), method)(*args)
                self.assertEqual(result, 42 if method == "get_week" else payload)
                call = self.session.get.call_args
                self.assertEqual(call.args[0], "https://fap-proxy.fpt.edu.vn/MyFAP/" + operation)
                self.assertEqual(call.kwargs["params"], query)
                self.assertEqual(call.kwargs["headers"]["Authorization"], "Bearer FAKE_OLD_KEY")
                self.assertEqual(call.kwargs["timeout"], 30 if method == "get_subjects" else 2.5)
        self.session.post.assert_not_called()
        self.auth.refresh_session.assert_not_called()

    def test_query_authen_and_canonical_reads_are_rebuilt_after_refresh(self):
        cases = (
            (api.MyFapOther, "check_open_feedback", (), "CheckOpenFeedBack"),
            (api.MyFapOther, "check_update_profile", (), "CheckUpdateProfile"),
            (api.MyFapOther, "get_notification", (), "GetNotificationByRoll"),
            (api.MyFapClient, "get_applications", (), "GetApplication"),
            (api.MyFapClient, "get_course_attendance", ("Fall2026", "DEMO", "CLASS"), "GetCourseAttendance"),
            (api.MyFapEssential, "get_week", ("2026-10-17",), "GetWeekByDate"),
        )
        for cls, method, args, operation in cases:
            with self.subTest(method=method):
                self.auth.authen_key = "FAKE_OLD_KEY"
                self.session.get.reset_mock()
                self.auth.refresh_session.reset_mock()
                data = 42 if method == "get_week" else []
                self.session.get.side_effect = [response({"code": 401}), response({"code": 200, "data": data})]

                def refresh():
                    self.auth.authen_key = "FAKE_NEW_KEY"
                    return True

                self.auth.refresh_session.side_effect = refresh
                result = getattr(cls(self.auth), method)(*args)
                self.assertEqual(result, 42 if method == "get_week" else {"code": 200, "data": []})
                self.auth.refresh_session.assert_called_once_with()
                first, second = self.session.get.call_args_list
                self.assertTrue(second.args[0].endswith("/" + operation))
                self.assertEqual(second.kwargs["headers"]["Authorization"], "Bearer FAKE_NEW_KEY")
                self.assertNotEqual(first.kwargs["headers"]["Checksum"], second.kwargs["headers"]["Checksum"])
                if operation in {"CheckOpenFeedBack", "CheckUpdateProfile", "GetNotificationByRoll", "GetApplication"}:
                    self.assertEqual(first.kwargs["params"]["Authen"], "FAKE_OLD_KEY")
                    self.assertEqual(second.kwargs["params"]["Authen"], "FAKE_NEW_KEY")

    def test_new_v2_reads_preserve_empty_errors_and_never_fall_back(self):
        cases = (
            (api.MyFapClient, "get_marks", ("Fall2026",)),
            (api.MyFapClient, "get_course_attendance", ("Fall2026", "DEMO", "CLASS")),
            (api.MyFapOther, "get_fee", ()),
            (api.MyFapOther, "get_notification", ()),
        )
        failures = (
            response({"code": 201, "data": None}), response({"code": 404, "data": None}),
            response(status=404), response(status=503),
            response({"errorMessage": "APP_CHECK_FAILED"}, 401),
            response("invalid-envelope"), requests.Timeout("PRIVATE_SENTINEL"),
        )
        for cls, method, args in cases:
            for failure in failures:
                with self.subTest(method=method, failure=type(failure).__name__):
                    self.session.get.reset_mock()
                    self.session.get.side_effect = [failure]
                    with self.assertRaises(api.ApiError) as caught:
                        getattr(cls(self.auth), method)(*args)
                    self.assertNotIn("PRIVATE_SENTINEL", str(caught.exception))
                    self.assertEqual(self.session.get.call_count, 1)
                    self.assertTrue(self.session.get.call_args.args[0].startswith("https://fap-proxy.fpt.edu.vn/MyFAP/"))
                    self.auth.refresh_session.assert_not_called()
        self.session.post.assert_not_called()

    def test_v2_session_keeps_independent_survey_signature_and_envelope(self):
        with patch("myfap.api.create_survey_checksum", return_value="FAKE+/CHECKSUM="):
            self.assertEqual(api.MyFapOther(self.auth).get_required_survey(), {"code": 200, "data": []})
        call = self.session.get.call_args
        self.assertEqual(call.args[0], "https://survey.fpt.edu.vn/API/myFAP/GetRequiredSurvey")
        self.assertEqual(call.kwargs["params"], {"username": "user@example.invalid", "checksum": "FAKE+/CHECKSUM="})
        self.assertNotIn("headers", call.kwargs)
        self.session.get.return_value = response({"code": 401, "data": None})
        with self.assertRaises(api.ApiOperationError):
            api.MyFapOther(self.auth).get_required_survey()
        self.auth.refresh_session.assert_not_called()

    def test_changed_version_or_binding_is_checked_before_each_send(self):
        client = api.MyFapClient(self.auth)
        self.auth.api_version = "v1"
        with self.assertRaises(api.ApiError):
            client.get_schedule("Fall2026")
        self.auth.api_version = "v2"
        self.auth.ensure_bound.side_effect = api.ApiError("Binding không khớp.")
        with self.assertRaises(api.ApiError):
            client.get_schedule("Fall2026")
        self.session.get.assert_not_called()
        self.session.post.assert_not_called()

    def test_explicit_wrong_campus_is_rejected_before_http(self):
        def ensure_bound(**binding):
            if binding["campus"] != "TEST":
                raise api.ApiError("Binding không khớp.")

        self.auth.ensure_bound.side_effect = ensure_bound
        with self.assertRaises(api.ApiError):
            api.MyFapEssential(self.auth).get_semesters("OTHER")
        self.session.get.assert_not_called()

    def test_v2_read_retries_once_for_each_expiry_signal_with_fresh_key(self):
        cases = (
            response(status=401), response({"code": 401}), response({"errorMessage": "Unauthorized"}),
        )
        for expired in cases:
            with self.subTest(expired=expired.status_code):
                self.auth.authen_key = "FAKE_OLD_KEY"
                self.auth.refresh_session.reset_mock()
                self.session.get.reset_mock()
                self.session.get.side_effect = [expired, response({"code": 200, "data": []})]

                def refresh():
                    self.auth.authen_key = "FAKE_NEW_KEY"
                    return True

                self.auth.refresh_session.side_effect = refresh
                result = api.MyFapClient(self.auth).get_schedule("Fall2026")
                self.assertEqual(result, {"code": 200, "data": []})
                self.auth.refresh_session.assert_called_once_with()
                self.assertEqual(self.session.get.call_count, 2)
                first, second = self.session.get.call_args_list
                self.assertEqual(first.kwargs["headers"]["Authorization"], "Bearer FAKE_OLD_KEY")
                self.assertEqual(second.kwargs["headers"]["Authorization"], "Bearer FAKE_NEW_KEY")
                self.assertNotEqual(first.kwargs["headers"]["Checksum"], second.kwargs["headers"]["Checksum"])
                self.assertEqual(first.kwargs["params"], second.kwargs["params"])

    def test_v2_retry_stops_after_second_expiry_or_failed_refresh(self):
        self.session.get.return_value = response(status=401)
        for refreshed, expected_calls in ((True, 2), (False, 1)):
            with self.subTest(refreshed=refreshed):
                self.session.get.reset_mock()
                self.auth.refresh_session.reset_mock()
                self.auth.refresh_session.return_value = refreshed
                with self.assertRaises(api.ApiSessionExpiredError):
                    api.MyFapEssential(self.auth).get_semesters()
                self.assertEqual(self.session.get.call_count, expected_calls)
                self.auth.refresh_session.assert_called_once_with()

    def test_v2_failures_do_not_refresh_or_fall_back(self):
        cases = (
            response({"code": 201, "message": "Token invalid", "data": None}),
            response({"code": 401}, 403), response({"errorMessage": "APP_CHECK_FAILED"}, 401),
            response(status=503), requests.Timeout("PRIVATE_SENTINEL"),
        )
        for failed in cases:
            with self.subTest(failure=type(failed).__name__):
                self.session.get.reset_mock()
                self.session.get.side_effect = [failed]
                with self.assertRaises(api.ApiError) as caught:
                    api.MyFapClient(self.auth).get_schedule("Fall2026")
                self.assertNotIn("PRIVATE_SENTINEL", str(caught.exception))
                self.assertEqual(self.session.get.call_count, 1)
                self.auth.refresh_session.assert_not_called()
        self.session.post.assert_not_called()

    def test_bootstrap_401_never_refreshes_authenticated_session(self):
        self.session.post.return_value = response(status=401)
        with self.assertRaises(api.ApiSessionExpiredError):
            api.MyFapEssential(self.auth).get_campuses()
        self.session.post.assert_called_once()
        self.auth.refresh_session.assert_not_called()


if __name__ == "__main__":
    unittest.main()
