import unittest
from unittest.mock import Mock, patch

from myfap import v2
from myfap.errors import ApiError


class Phase4TransportTests(unittest.TestCase):
    def setUp(self):
        self.session = Mock()
        self.query = {"rollNumber": "FAKE+ROLL"}
        self.term_query = {**self.query, "Semester": "opaque&term"}

    def send(self, operation, params=None, credential="fake-key"):
        return v2.request(self.session, operation, credential=credential, campus="TEST", params=params)

    def test_parity_routes_use_exact_app_query_and_bound_credential(self):
        cases = (
            ("GetSemester", {}, {}),
            ("GetTop10News", {"type": 2}, {"CampusCode": "TEST", "type": 2}),
            ("GetSubjets", {}, {"CampusCode": "TEST"}),
            ("GetWeekByDate", {"date": "2026-10-17"}, {"date": "2026-10-17"}),
            *((name, self.query, {"CampusCode": "TEST", **self.query}) for name in (
                "GeFeeByRoll", "GetStudentById", "GetCampusInfo")),
            *((name, self.query, {"CampusCode": "TEST", **self.query, "Authen": "fake-key"}) for name in (
                "CheckOpenFeedBack", "CheckUpdateProfile", "GetApplication", "GetNotificationByRoll")),
            *((name, self.term_query, {"CampusCode": "TEST", **self.term_query}) for name in (
                "GetActivityStudent", "GetStudentMark", "GetScheduleExam", "GetStudentAttendances")),
            ("GetMarkByCourse", {**self.query, "CourseId": 42}, {"CampusCode": "TEST", **self.query, "CourseId": 42}),
            ("GetActivityStudentByWeek", {**self.term_query, "week": 42, "year": 2026},
             {"CampusCode": "TEST", **self.term_query, "week": 42, "year": 2026}),
            ("GetCourseAttendance", {**self.term_query, "SubjectCode": "FAKE101", "ClassName": "FAKE"},
             {"CampusCode": "TEST", **self.term_query, "SubjectCode": "FAKE101", "ClassName": "FAKE"}),
        )
        for operation, params, expected in cases:
            with self.subTest(operation=operation), patch.object(v2, "create_checksum", return_value="fake-signature") as signer:
                original = dict(params)
                self.assertIs(self.send(operation, params), self.session.request.return_value)
                call = self.session.request.call_args
                self.assertEqual(call.args, ("GET", f"{v2.FAP_PROXY_HOST}/{operation}"))
                self.assertEqual(call.kwargs["params"], expected)
                self.assertEqual(params, original)
                self.assertEqual(call.kwargs["headers"]["Authorization"], "Bearer fake-key")
                self.assertEqual(call.kwargs["headers"]["CampusCode"], "TEST")
                self.assertEqual(call.kwargs["headers"]["Checksum"], "fake-signature")
                self.assertNotIn("Content-Type", call.kwargs["headers"])
                self.assertEqual(call.kwargs["headers"]["Accept"], "application/json, text/plain, */*")
                self.assertEqual(call.kwargs["headers"]["Accept-Encoding"], "gzip")
                self.assertEqual(call.kwargs["headers"]["User-Agent"], "okhttp/4.9.2")
                self.assertNotIn("json", call.kwargs)
                signer.assert_called_once_with("fake-key")

    def test_query_authen_is_rebuilt_from_each_current_credential(self):
        for operation in ("CheckOpenFeedBack", "CheckUpdateProfile", "GetApplication", "GetNotificationByRoll"):
            with self.subTest(operation=operation):
                self.send(operation, self.query, credential="fake-old")
                self.send(operation, self.query, credential="fake-new")
                first, second = self.session.request.call_args_list[-2:]
                self.assertEqual(first.kwargs["params"]["Authen"], "fake-old")
                self.assertEqual(second.kwargs["params"]["Authen"], "fake-new")
                self.assertEqual(second.kwargs["headers"]["Authorization"], "Bearer fake-new")
                self.assertNotIn("Authen", self.query)

    def test_course_id_text_and_numeric_query_values_keep_their_types(self):
        for course_id in ("FAKE&COURSE", "42", 42):
            with self.subTest(course_id=course_id):
                self.send("GetMarkByCourse", {**self.query, "CourseId": course_id})
                self.assertEqual(self.session.request.call_args.kwargs["params"]["CourseId"], course_id)
        self.send("GetActivityStudentByWeek", {**self.term_query, "week": "42", "year": "2026"})
        self.assertEqual(self.session.request.call_args.kwargs["params"]["week"], "42")

    def test_alias_is_explicit_and_only_supported_canonical_reads_are_exposed(self):
        self.assertEqual(v2.OPERATION_ALIASES, {"getCourseAttendance": "GetCourseAttendance"})
        self.assertIn("GetWeekByDate", v2.READ_OPERATIONS)
        self.assertIn("GetCourseAttendance", v2.READ_OPERATIONS)
        self.assertNotIn("getCourseAttendance", v2.READ_OPERATIONS)
        for operation in ("GetVersion", "GetStudentFeedbackForm", "AddRate", "UpdateTokedevices"):
            self.assertNotIn(operation, v2.SUPPORTED_OPERATIONS)

    def test_invalid_read_queries_are_rejected_before_http_without_echo(self):
        cases = (
            ("GetStudentMark", {"Semester": "TERM"}),
            ("GetStudentMark", {**self.term_query, "CampusCode": "OTHER"}),
            ("GetStudentMark", {**self.term_query, "campusCode": "TEST"}),
            ("GetStudentById", {"rollNumber": "PRIVATE\r\nVALUE"}),
            ("GetSubjets", {"rollNumber": "PRIVATE_VALUE"}),
            ("GetApplication", {**self.query, "Authen": "PRIVATE_VALUE"}),
            ("GetTop10News", {"type": True}),
            ("GetTop10News", {"type": 0}),
            ("GetTop10News", {"type": "١"}),
            ("GetMarkByCourse", {**self.query, "CourseId": True}),
            ("GetMarkByCourse", {**self.query, "CourseId": 0}),
            ("GetMarkByCourse", {**self.query, "CourseId": ""}),
            ("GetActivityStudentByWeek", {**self.term_query, "week": -1, "year": 2026}),
            ("GetActivityStudentByWeek", {**self.term_query, "week": 1, "year": 1.5}),
            ("GetCourseAttendance", {**self.term_query, "SubjectCode": "FAKE101"}),
            ("GetCourseAttendance", {**self.term_query, "SubjectCode": "FAKE101", "ClassName": []}),
            ("GetWeekByDate", {"date": "2026-02-30"}),
            ("GetWeekByDate", {"date": "2026-1-1"}),
            ("GetWeekByDate", {"date": "2026-10-17", "CampusCode": "TEST"}),
        )
        for operation, params in cases:
            with self.subTest(operation=operation, params=params), self.assertRaises(ApiError) as caught:
                self.send(operation, params)
            self.assertNotIn("PRIVATE", str(caught.exception))
        self.session.request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
