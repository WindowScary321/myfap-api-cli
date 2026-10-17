import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import requests

from myfap import api
from tests.test_api import response


AUTHENTICATED_READ_CASES = (
    (api.MyFapEssential, "get_semesters", (), "GetSemester"),
    (api.MyFapEssential, "get_news", (), "GetTop10News"),
    (api.MyFapOther, "check_open_feedback", (), "CheckOpenFeedBack"),
    (api.MyFapOther, "check_update_profile", (), "CheckUpdateProfile"),
    (api.MyFapOther, "get_notification", (), "GetNotificationByRoll"),
    (api.MyFapOther, "get_fee", (), "GeFeeByRoll"),
    (api.MyFapOther, "get_subjects", (), "GetSubjets"),
    (api.MyFapClient, "get_schedule", ("Fall2026",), "GetActivityStudent"),
    (api.MyFapClient, "get_marks", ("Fall2026",), "GetStudentMark"),
    (api.MyFapClient, "get_mark_by_course", ("123",), "GetMarkByCourse"),
    (api.MyFapClient, "get_exams", ("Fall2026",), "GetScheduleExam"),
    (api.MyFapClient, "get_schedule_by_week", (42, "Fall2026", 2026), "GetActivityStudentByWeek"),
    (api.MyFapClient, "get_attendances", ("Fall2026",), "GetStudentAttendances"),
    (api.MyFapClient, "get_course_attendance", ("Fall2026", "TEST101", "DEMO01"), "getCourseAttendance"),
    (api.MyFapClient, "get_applications", (), "GetApplication"),
    (api.MyFapClient, "get_student_info", (), "GetStudentById"),
    (api.MyFapClient, "get_campus_info", (), "GetCampusInfo"),
)


class ApiErrorPolicyTests(unittest.TestCase):
    def test_authenticated_v1_reads_recognize_201_token_invalid_with_actual_http_status(self):
        for _, _, _, operation in AUTHENTICATED_READ_CASES:
            for code in (201, "201"):
                with self.subTest(operation=operation, code=code):
                    with self.assertRaises(api.ApiSessionExpiredError) as caught:
                        api.read_response(response({"code": code, "message": "Token invalid", "data": None}), api_version="v1", operation=operation)
                    self.assertEqual(caught.exception.status_code, 200)

    def test_other_v1_body_201_and_401_are_operation_errors_even_with_expiry_message(self):
        for operation in ("GetAllActiveCampus", "GetWeekByDate", "AuthenticationByFeId", "GetRequiredSurvey", "AddRate", "GetBalance", "UnknownOperation"):
            for code in (201, "201", 401, "401"):
                with self.subTest(operation=operation, code=code):
                    with self.assertRaises(api.ApiOperationError) as caught:
                        api.read_response(response({"code": code, "message": "Token invalid", "data": None}), api_version="v1", operation=operation)
                    self.assertEqual(caught.exception.api_version, "v1")
                    self.assertEqual(caught.exception.operation, operation)
                    self.assertEqual(caught.exception.code, str(code))

    def test_v1_201_requires_exact_token_invalid_message(self):
        for _, _, _, operation in AUTHENTICATED_READ_CASES:
            for message in (None, "token invalid", "Token Invalid", "Session expired", "Token invalid "):
                with self.subTest(operation=operation, message=message):
                    with self.assertRaises(api.ApiOperationError):
                        api.read_response(response({"code": 201, "message": message, "data": None}), api_version="v1", operation=operation)
            with self.subTest(operation=operation, message="missing"):
                with self.assertRaises(api.ApiOperationError):
                    api.read_response(response({"code": 201, "data": None}), api_version="v1", operation=operation)
            with self.subTest(operation=operation, code=401):
                with self.assertRaises(api.ApiOperationError):
                    api.read_response(response({"code": 401, "message": "Token invalid", "data": None}), api_version="v1", operation=operation)

    def test_v1_201_contract_does_not_require_data_field(self):
        with self.assertRaises(api.ApiSessionExpiredError):
            api.read_response(response({"code": "201", "message": "Token invalid"}), api_version="v1", operation="GetStudentMark")

    def test_http_401_is_explicit_expiry_and_keeps_status(self):
        for version in ("v1", "v2"):
            with self.subTest(version=version):
                with self.assertRaises(api.ApiSessionExpiredError) as caught:
                    api.read_response(response(status=401), api_version=version, operation="GetSemester")
                self.assertEqual(caught.exception.status_code, 401)

    def test_v2_has_explicit_body_expiry_signals(self):
        for body in ({"code": 401, "data": None}, {"code": "401", "data": None}, {"code": 401}, {"errorMessage": "Unauthorized"}, {"code": 200, "data": [], "errorMessage": "Unauthorized"}):
            with self.subTest(body=body):
                with self.assertRaises(api.ApiSessionExpiredError):
                    api.read_response(response(body), api_version="v2", operation="GetSemester")

    def test_v1_unauthorized_text_is_not_a_verified_expiry_contract(self):
        with self.assertRaises(api.ApiPayloadError):
            api.read_response(response({"errorMessage": "Unauthorized"}), api_version="v1", operation="GetSemester")

    def test_app_check_takes_priority_over_401_and_does_not_match_substrings(self):
        for status in (200, 401, 403):
            with self.subTest(status=status):
                with self.assertRaises(api.ApiAppCheckError):
                    api.read_response(response({"errorMessage": "APP_CHECK_FAILED", "code": 401, "data": None}, status), api_version="v2")
        with self.assertRaises(api.ApiSessionExpiredError):
            api.read_response(response({"errorMessage": "prefix APP_CHECK_FAILED"}, 401), api_version="v2")


class AuthenticatedRequestTests(unittest.TestCase):
    def setUp(self):
        self.session = Mock()
        self.auth = SimpleNamespace(
            session=self.session, campus="TEST", api_version="v1", account_type="student",
            authen_key="FAKE_OLD_KEY", mssv="TESTROLL", email="test@example.invalid",
            ensure_bound=Mock(), refresh_session=Mock(return_value=True),
        )
        self.session.get.return_value = response({"code": 200, "data": []})

    def test_news_and_notifications_201_do_not_refresh_or_invalidate_session(self):
        self.session.get.return_value = response({"code": 201, "data": None})
        for cls, method in ((api.MyFapEssential, "get_news"), (api.MyFapOther, "get_notification")):
            with self.subTest(method=method):
                with self.assertRaises(api.ApiOperationError):
                    getattr(cls(self.auth), method)()
                self.auth.refresh_session.assert_not_called()
                self.assertEqual(self.auth.authen_key, "FAKE_OLD_KEY")
        self.session.get.return_value = response({"code": 200, "data": []})
        self.assertEqual(api.MyFapEssential(self.auth).get_semesters(), [])

    def test_expired_read_retries_once_with_new_key_and_new_checksum(self):
        self.session.get.side_effect = [response(status=401), response({"code": 200, "data": []})]

        def refreshed():
            self.auth.authen_key = "FAKE_NEW_KEY"
            return True

        self.auth.refresh_session.side_effect = refreshed
        with patch("myfap.api.create_checksum", side_effect=["FAKE_OLD_CHECKSUM", "FAKE_NEW_CHECKSUM"]):
            self.assertEqual(api.MyFapClient(self.auth).get_schedule("Fall2026"), {"code": 200, "data": []})
        self.auth.refresh_session.assert_called_once_with()
        calls = self.session.get.call_args_list
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0].kwargs["params"]["Authen"], "FAKE_OLD_KEY")
        self.assertEqual(calls[1].kwargs["params"]["Authen"], "FAKE_NEW_KEY")
        self.assertEqual(calls[1].kwargs["params"]["checksum"], "FAKE_NEW_CHECKSUM")
        self.assertEqual(calls[1].kwargs["params"]["Semester"], "Fall2026")
        self.auth.ensure_bound.assert_called_with(campus="TEST", api_version="v1", account_type="student")

    def test_all_authenticated_v1_reads_retry_once_with_rotated_key_and_fresh_checksum(self):
        for cls, method, args, operation in AUTHENTICATED_READ_CASES:
            for code in (201, "201"):
                with self.subTest(operation=method, code=code):
                    self.auth.authen_key = "FAKE_OLD_KEY"
                    self.auth.refresh_session.reset_mock()
                    self.session.get.reset_mock()
                    self.session.get.side_effect = [
                        response({"code": code, "message": "Token invalid", "data": None}),
                        response({"code": 200, "data": []}),
                    ]

                    def refresh():
                        self.auth.authen_key = "FAKE_NEW_KEY"
                        return True

                    self.auth.refresh_session.side_effect = refresh
                    with patch("myfap.api.create_checksum", side_effect=["FAKE_OLD_CHECKSUM", "FAKE_NEW_CHECKSUM"]):
                        expected = [] if operation == "GetSemester" else {"code": 200, "data": []}
                        self.assertEqual(getattr(cls(self.auth), method)(*args), expected)
                    self.auth.refresh_session.assert_called_once_with()
                    self.assertEqual(self.session.get.call_count, 2)
                    self.assertTrue(all(call.args[0].endswith("/" + operation) for call in self.session.get.call_args_list))
                    first, retried = [call.kwargs["params"] for call in self.session.get.call_args_list]
                    self.assertEqual(first["Authen"], "FAKE_OLD_KEY")
                    self.assertEqual(retried["Authen"], "FAKE_NEW_KEY")
                    self.assertEqual(retried["checksum"], "FAKE_NEW_CHECKSUM")
                    self.assertEqual({key: value for key, value in first.items() if key not in ("Authen", "checksum")},
                                     {key: value for key, value in retried.items() if key not in ("Authen", "checksum")})

    def test_second_v1_201_failure_does_not_refresh_again(self):
        self.session.get.side_effect = [
            response({"code": 201, "message": "Token invalid", "data": None}),
            response({"code": "201", "message": "Token invalid", "data": None}),
        ]
        with self.assertRaises(api.ApiSessionExpiredError) as caught:
            api.MyFapClient(self.auth).get_marks("Fall2026")
        self.assertEqual(caught.exception.status_code, 200)
        self.auth.refresh_session.assert_called_once_with()
        self.assertEqual(self.session.get.call_count, 2)

    def test_known_v1_201_failed_refresh_does_not_retry(self):
        self.auth.refresh_session.return_value = False
        self.session.get.return_value = response({"code": 201, "message": "Token invalid", "data": None})
        with self.assertRaises(api.ApiSessionExpiredError):
            api.MyFapClient(self.auth).get_marks("Fall2026")
        self.auth.refresh_session.assert_called_once_with()
        self.assertEqual(self.session.get.call_count, 1)

    def test_second_expiry_raises_without_another_refresh(self):
        self.session.get.return_value = response(status=401)
        with self.assertRaises(api.ApiSessionExpiredError):
            api.MyFapClient(self.auth).get_marks("Fall2026")
        self.auth.refresh_session.assert_called_once_with()
        self.assertEqual(self.session.get.call_count, 2)

    def test_failed_refresh_does_not_retry(self):
        self.auth.refresh_session.return_value = False
        self.session.get.return_value = response(status=401)
        with self.assertRaises(api.ApiSessionExpiredError):
            api.MyFapClient(self.auth).get_marks("Fall2026")
        self.assertEqual(self.session.get.call_count, 1)

    def test_non_expiry_failures_never_refresh(self):
        cases = [
            response({"code": 201, "message": "Token invalid", "data": None}, status)
            for status in (403, 404, 500, 503)
        ] + [response({"code": "APP_CHECK_FAILED", "message": "Token invalid"}, 401), requests.Timeout("PRIVATE_SENTINEL")]
        for failed in cases:
            with self.subTest(failure=type(failed).__name__):
                self.session.get.side_effect = [failed]
                with self.assertRaises(api.ApiError):
                    api.MyFapClient(self.auth).get_marks("Fall2026")
                self.auth.refresh_session.assert_not_called()

    def test_credential_requests_disable_redirects_and_reject_3xx_without_refresh(self):
        for status in (301, 302, 303, 307, 308):
            with self.subTest(status=status):
                self.session.get.reset_mock()
                self.session.get.return_value = response({"code": 200, "data": []}, status)
                with self.assertRaises(api.ApiHTTPError) as caught:
                    api.MyFapClient(self.auth).get_marks("Fall2026")
                self.assertEqual(caught.exception.status_code, status)
                self.assertFalse(self.session.get.call_args.kwargs["allow_redirects"])
                self.assertEqual(self.session.get.call_count, 1)
                self.auth.refresh_session.assert_not_called()

    def test_get_write_route_is_never_replayed(self):
        self.session.get.return_value = response(status=401)
        with self.assertRaises(api.ApiSessionExpiredError):
            api._get(self.session, f"{api.FAP_HOST}/AddRate", {"Authen": "FAKE"}, auth=self.auth, operation="AddRate", params_factory=lambda: {"Authen": self.auth.authen_key})
        self.auth.refresh_session.assert_not_called()
        self.assertEqual(self.session.get.call_count, 1)

    def test_campus_mismatch_rejected_before_first_http_request(self):
        def bound(**binding):
            if binding["campus"] != "TEST":
                raise api.ApiError("Binding không khớp.")

        self.auth.ensure_bound.side_effect = bound
        with self.assertRaises(api.ApiError):
            api.MyFapEssential(self.auth).get_semesters("OTHER")
        self.session.get.assert_not_called()

    def test_changed_binding_is_checked_on_each_send(self):
        client = api.MyFapClient(self.auth)
        self.auth.ensure_bound.side_effect = api.ApiError("Binding không khớp.")
        with self.assertRaises(api.ApiError):
            client.get_marks("Fall2026")
        self.session.get.assert_not_called()

    def test_v2_session_is_not_sent_to_v1_host(self):
        self.auth.api_version = "v2"
        for cls in (api.MyFapEssential, api.MyFapClient, api.MyFapOther):
            with self.subTest(cls=cls):
                with self.assertRaises(api.ApiError):
                    cls(self.auth, api_version="v1")
        self.session.get.assert_not_called()


if __name__ == "__main__":
    unittest.main()
