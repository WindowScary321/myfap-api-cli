"""Phase 6 command contracts using real auth/client code and synthetic HTTP."""

import inspect
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

from typer.testing import CliRunner
from rich.text import Text

from myfap.cli import app
from tests.test_api import response


RUNNER_OPTIONS = {"mix_stderr": False} if "mix_stderr" in inspect.signature(CliRunner).parameters else {}


class BalanceCommandTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "session.json"
        self.runner = CliRunner(**RUNNER_OPTIONS)

    def save_session(self, version):
        session = {
            "campus": "TEST", "account_type": "student", "authen_key": "FAKE_FAP_KEY",
            "mssv": "TEST000", "email": "synthetic@example.invalid",
        }
        if version == "v2":
            session["api_version"] = version
        self.path.write_text(json.dumps(session), encoding="utf-8")

    def test_balance_preserves_envelope_and_uses_exact_version_contract_without_term_lookup(self):
        payload = {"code": 200, "data": {"synthetic": {"label": "Dữ liệu thử", "value": 7.5}}, "message": None}
        for version in ("v1", "v2"):
            with self.subTest(version=version):
                self.save_session(version)
                original = self.path.read_bytes()
                with patch("requests.Session.request", return_value=response(payload)) as request, patch(
                    "myfap.api.create_checksum", return_value="FAKE_ROLL_CHECKSUM"
                ) as checksum:
                    result = self.runner.invoke(app, ["--config", str(self.path), "other", "balance", "--stdout"])
                self.assertEqual(result.exit_code, 0, result.output)
                self.assertEqual(json.loads(result.stdout), payload)
                request.assert_called_once()
                self.assertEqual(request.call_args.args[0], "GET")
                parsed = urlsplit(request.call_args.args[1])
                self.assertEqual(parsed.path.rsplit("/", 1)[-1], "GetBalance")
                self.assertEqual(parsed.query, "")
                self.assertFalse(request.call_args.kwargs["allow_redirects"])
                if version == "v1":
                    self.assertEqual(parsed.netloc, "api.fpt.edu.vn")
                    self.assertEqual(request.call_args.kwargs["params"], {
                        "campusCode": "TEST", "rollNumber": "TEST000", "Authen": "FAKE_FAP_KEY",
                        "checksum": "FAKE_ROLL_CHECKSUM",
                    })
                    checksum.assert_called_once_with("TEST000", "TEST")
                else:
                    self.assertEqual(parsed.netloc, "fap-proxy.fpt.edu.vn")
                    self.assertEqual(request.call_args.kwargs["params"], {"CampusCode": "TEST", "rollNumber": "TEST000"})
                    self.assertEqual(request.call_args.kwargs["headers"]["Authorization"], "Bearer FAKE_FAP_KEY")
                    checksum.assert_not_called()
                self.assertEqual(self.path.read_bytes(), original)
                self.assertNotIn("FAKE_FAP_KEY", result.stdout + result.stderr)

    def test_balance_accepts_nested_common_options_and_preserves_empty_data(self):
        payload = {"code": "200", "data": []}
        for version in ("v1", "v2"):
            with self.subTest(version=version):
                self.save_session(version)
                with patch("requests.Session.request", return_value=response(payload)) as request:
                    result = self.runner.invoke(app, [
                        "other", "balance", "--config", str(self.path), "--api-version", version,
                        "--campus", "TEST", "--timeout", "31", "--stdout",
                    ])
                self.assertEqual(result.exit_code, 0, result.output)
                self.assertEqual(json.loads(result.stdout), payload)
                request.assert_called_once()
                self.assertEqual(request.call_args.args[0], "GET")
                self.assertTrue(request.call_args.args[1].endswith("/GetBalance"))
                self.assertEqual(request.call_args.kwargs["timeout"], 31.0)


class CoursesCommandTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "session.json"
        self.runner = CliRunner(**RUNNER_OPTIONS)

    def save_session(self, version):
        session = {
            "campus": "TEST", "account_type": "student", "authen_key": "FAKE_FAP_KEY",
            "mssv": "TEST000", "email": "synthetic@example.invalid",
        }
        if version == "v2":
            session["api_version"] = version
        self.path.write_text(json.dumps(session), encoding="utf-8")

    def test_courses_preserves_data_and_uses_explicit_or_latest_semester(self):
        payload = {"code": 200, "data": [{"synthetic": True}], "message": None}
        semesters = [
            {"semesterName": "Fall2025", "startDate": "2025-09-01", "termID": "zzzz-opaque-old"},
            {"semesterName": "Fall2026", "startDate": "2026-09-01", "termID": "aaaa-opaque-new"},
        ]

        def reply(method, url, **kwargs):
            operation = urlsplit(url).path.rsplit("/", 1)[-1]
            return response({"code": 200, "data": semesters}) if operation == "GetSemester" else response(payload)

        for version in ("v1", "v2"):
            for explicit in (False, True):
                with self.subTest(version=version, explicit=explicit):
                    self.save_session(version)
                    original = self.path.read_bytes()
                    options = ["--semester", "Summer&2026"] if explicit else []
                    with patch("requests.Session.request", side_effect=reply) as request, patch(
                        "myfap.api.create_checksum", return_value="FAKE_ROLL_CHECKSUM"
                    ) as checksum:
                        result = self.runner.invoke(app, ["--config", str(self.path), "courses", *options, "--stdout"])
                    self.assertEqual(result.exit_code, 0, result.output)
                    self.assertEqual(json.loads(result.stdout), payload)
                    operations = [urlsplit(call.args[1]).path.rsplit("/", 1)[-1] for call in request.call_args_list]
                    self.assertEqual(operations, ["GetCourseOfSemester"] if explicit else ["GetSemester", "GetCourseOfSemester"])
                    self.assertEqual(request.call_args.args[0], "GET")
                    parsed = urlsplit(request.call_args.args[1])
                    self.assertEqual(parsed.query, "")
                    self.assertFalse(request.call_args.kwargs["allow_redirects"])
                    semester = "Summer&2026" if explicit else "Fall2026"
                    if version == "v1":
                        self.assertEqual(parsed.netloc, "api.fpt.edu.vn")
                        self.assertEqual(request.call_args.kwargs["params"], {
                            "campusCode": "TEST", "rollNumber": "TEST000", "Authen": "FAKE_FAP_KEY",
                            "checksum": "FAKE_ROLL_CHECKSUM", "semester": semester,
                        })
                        self.assertEqual(checksum.call_args.args, ("TEST000", "TEST"))
                    else:
                        self.assertEqual(parsed.netloc, "fap-proxy.fpt.edu.vn")
                        self.assertEqual(request.call_args.kwargs["params"], {
                            "CampusCode": "TEST", "rollNumber": "TEST000", "semester": semester,
                        })
                        self.assertEqual(request.call_args.kwargs["headers"]["Authorization"], "Bearer FAKE_FAP_KEY")
                        checksum.assert_not_called()
                    self.assertEqual(self.path.read_bytes(), original)
                    self.assertNotIn("FAKE_FAP_KEY", result.stdout + result.stderr)

    def test_courses_rejects_blank_explicit_semester_before_http(self):
        for version in ("v1", "v2"):
            with self.subTest(version=version):
                self.save_session(version)
                with patch("requests.Session.request") as request:
                    result = self.runner.invoke(app, [
                        "--config", str(self.path), "courses", "--semester", "   ", "--stdout",
                    ])
                self.assertIn(result.exit_code, (1, 2))
                self.assertEqual(result.stdout, "")
                self.assertIn("--semester", Text.from_ansi(result.stderr).plain)
                request.assert_not_called()


class SubjectsBySemesterTests(unittest.TestCase):
    setUp = BalanceCommandTests.setUp
    save_session = BalanceCommandTests.save_session

    def test_subjects_option_preserves_legacy_and_signs_by_semester(self):
        for version in ("v1", "v2"):
            for semester in (None, "Fall&2026"):
                with self.subTest(version=version, semester=semester):
                    self.save_session(version)
                    options = ["--semester", semester] if semester is not None else []
                    with patch("requests.Session.request", return_value=response({"code": 200, "data": []})) as request, \
                         patch("myfap.api.MAGIC_ID", "SYNTHETIC_MAGIC_ID"), \
                         patch("myfap.api.create_checksum", return_value="SYNTHETIC_CHECKSUM") as checksum:
                        result = self.runner.invoke(app, ["--config", str(self.path), "other", "subjects", *options, "--stdout"])
                    self.assertEqual(result.exit_code, 0, result.output)
                    self.assertEqual(json.loads(result.stdout), {"code": 200, "data": []})
                    request.assert_called_once()
                    operation = "GetSubjectBySemester" if semester is not None else "GetSubjets"
                    self.assertTrue(request.call_args.args[1].endswith('/' + operation))
                    query = request.call_args.kwargs["params"]
                    self.assertNotIn("rollNumber", query)
                    self.assertNotIn("semester", query)
                    self.assertEqual(query.get("Semester"), semester)
                    self.assertGreaterEqual(request.call_args.kwargs["timeout"], 30)
                    if version == "v1" and semester is not None:
                        checksum.assert_called_once_with(semester, "TEST")
                    if version == "v2":
                        self.assertEqual(query, {"CampusCode": "TEST", **({"Semester": semester} if semester else {})})

    def test_blank_semester_is_rejected_before_http(self):
        with patch("requests.Session.request") as request:
            result = self.runner.invoke(app, ["other", "subjects", "--semester", " ", "--stdout"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("--semester", Text.from_ansi(result.stderr).plain)
        request.assert_not_called()


class SearchNewsTests(unittest.TestCase):
    setUp = BalanceCommandTests.setUp
    save_session = BalanceCommandTests.save_session

    def test_search_uses_type_signing_and_preserves_unicode_query(self):
        text = "Học phí & A+B%"
        for version in ("v1", "v2"):
            with self.subTest(version=version):
                self.save_session(version)
                payload = {"code": 200, "data": [{"synthetic": text}]}
                with patch("requests.Session.request", return_value=response(payload)) as request, \
                     patch("myfap.api.create_checksum", return_value="SYNTHETIC_SEARCH_SIGNATURE") as checksum:
                    result = self.runner.invoke(app, ["--config", str(self.path), "news", "--search", text, "--type", "2", "--stdout"])
                self.assertEqual(result.exit_code, 0, result.output)
                self.assertEqual(json.loads(result.stdout), payload)
                request.assert_called_once()
                self.assertTrue(request.call_args.args[1].endswith("/SearchNews"))
                query = request.call_args.kwargs["params"]
                self.assertEqual(query["keysearch"], text)
                self.assertEqual(query["type"], 2)
                self.assertNotIn("rollNumber", query)
                if version == "v1":
                    checksum.assert_called_once_with("2", "TEST")
                else:
                    self.assertEqual(query, {"CampusCode": "TEST", "type": 2, "keysearch": text})

    def test_empty_search_is_rejected_before_auth_and_http(self):
        for value in ("", "   "):
            with self.subTest(value=value), patch("myfap.cli.get_auth") as auth, patch("requests.Session.request") as request:
                result = self.runner.invoke(app, ["news", "--search", value, "--stdout"])
                self.assertNotEqual(result.exit_code, 0)
                self.assertIn("--search", Text.from_ansi(result.stderr).plain)
                auth.assert_not_called()
                request.assert_not_called()


class TranscriptCommandTests(unittest.TestCase):
    setUp = BalanceCommandTests.setUp
    save_session = BalanceCommandTests.save_session

    def test_transcript_uses_bound_key_without_semester_lookup(self):
        for version in ("v1", "v2"):
            with self.subTest(version=version):
                self.save_session(version)
                payload = {"code": 200, "data": [{"synthetic": "Toàn khóa"}]}
                with patch("requests.Session.request", return_value=response(payload)) as request:
                    result = self.runner.invoke(app, ["--config", str(self.path), "transcript", "--stdout"])
                self.assertEqual(result.exit_code, 0, result.output)
                self.assertEqual(json.loads(result.stdout), payload)
                request.assert_called_once()
                self.assertTrue(request.call_args.args[1].endswith("/AcademicTranscript"))
                query = request.call_args.kwargs["params"]
                self.assertEqual(query["rollNumber"], "TEST000")
                self.assertNotIn("Semester", query)
                if version == "v2":
                    self.assertEqual(query, {"CampusCode": "TEST", "rollNumber": "TEST000"})
                    self.assertEqual(request.call_args.kwargs["headers"]["Authorization"], "Bearer FAKE_FAP_KEY")


    def test_transcript_pretty_parses_html_and_default_keeps_raw_string(self):
        from tests.test_parsers import TranscriptHtmlTests

        html = TranscriptHtmlTests.fixture()
        for options, expect_parsed in (([], False), (["--pretty"], True)):
            with self.subTest(options=options):
                self.save_session("v2")
                payload = {"code": 200, "data": html}
                with patch("requests.Session.request", return_value=response(payload)) as request:
                    result = self.runner.invoke(app, ["--config", str(self.path), "transcript", *options, "--stdout"])
                self.assertEqual(result.exit_code, 0, result.output)
                data = json.loads(result.stdout)["data"]
                if expect_parsed:
                    self.assertEqual([table["headers"] for table in data],
                                     [TranscriptHtmlTests.MAIN_HEADERS, TranscriptHtmlTests.EXTRA_HEADERS])
                    self.assertEqual(data[0]["rows"][0]["Subject Code"], "PRO192")
                else:
                    self.assertEqual(data, html)
                request.assert_called_once()
                self.assertTrue(request.call_args.args[1].endswith("/AcademicTranscript"))


class TrainingCommandTests(unittest.TestCase):
    setUp = BalanceCommandTests.setUp
    save_session = BalanceCommandTests.save_session

    def test_training_uses_lowercase_semester_and_latest_resolver(self):
        for version in ("v1", "v2"):
            with self.subTest(version=version):
                self.save_session(version)
                payload = {"code": 200, "data": [{"synthetic": "Phong trào"}]}
                def reply(method, url, **kwargs):
                    if url.endswith("/GetSemester"):
                        return response({"code": 200, "data": [{"semesterName": "Fall2026", "startDate": "2026-09-01"}]})
                    return response(payload)
                with patch("requests.Session.request", side_effect=reply) as request:
                    result = self.runner.invoke(app, ["--config", str(self.path), "other", "training", "--stdout"])
                self.assertEqual(result.exit_code, 0, result.output)
                self.assertEqual(json.loads(result.stdout), payload)
                self.assertEqual([call.args[1].rsplit('/', 1)[-1] for call in request.call_args_list],
                                 ["GetSemester", "GetDiemphongtrao"])
                query = request.call_args.kwargs["params"]
                self.assertEqual(query["semester"], "Fall2026")
                self.assertNotIn("Semester", query)
                if version == "v2":
                    self.assertEqual(request.call_args.kwargs["headers"]["Authorization"], "Bearer FAKE_FAP_KEY")


class PhotoCommandTests(unittest.TestCase):
    setUp = BalanceCommandTests.setUp
    save_session = BalanceCommandTests.save_session

    def test_photo_preserves_opaque_json_without_fetching_or_decoding(self):
        payload = {"code": 200, "data": "opaque&amp;literal-not-a-url"}
        for version in ("v1", "v2"):
            with self.subTest(version=version):
                self.save_session(version)
                with patch("requests.Session.request", return_value=response(payload)) as request:
                    result = self.runner.invoke(app, ["--config", str(self.path), "info", "photo", "--stdout"])
                self.assertEqual(result.exit_code, 0, result.output)
                self.assertEqual(json.loads(result.stdout), payload)
                request.assert_called_once()
                self.assertTrue(request.call_args.args[1].endswith("/RetriveImage"))
                self.assertEqual(request.call_args.kwargs["params"]["rollNumber"], "TEST000")


class PublicReadValidationTests(unittest.TestCase):
    def test_invalid_semester_is_rejected_by_public_api_before_http(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from myfap.api import MyFapClient, MyFapOther
        from myfap.errors import ApiError
        for version in ("v1", "v2"):
            for value in (None, "", "   ", False, 3, "TERM\nPRIVATE"):
                for owner, method in ((MyFapClient, "get_courses"), (MyFapClient, "get_training"), (MyFapOther, "get_subjects")):
                    if method == "get_subjects" and value is None:
                        continue
                    with self.subTest(version=version, method=method, value=value):
                        session = Mock()
                        auth = SimpleNamespace(session=session, api_version=version, campus="TEST", account_type="student",
                                               authen_key="FAKE_KEY", mssv="TEST000", ensure_bound=Mock())
                        with self.assertRaises(ApiError):
                            getattr(owner(auth), method)(value)
                        session.request.assert_not_called()
                        session.get.assert_not_called()


class RatingListTests(unittest.TestCase):
    setUp = BalanceCommandTests.setUp
    save_session = BalanceCommandTests.save_session

    def test_rating_list_v1_uses_read_contract_without_semester(self):
        self.save_session("v1")
        payload = {"code": 200, "data": [{"synthetic": "rating item"}]}
        with patch("requests.Session.request", return_value=response(payload)) as request, \
             patch("myfap.api.create_checksum", return_value="SYNTHETIC_RATE_LIST") as checksum:
            result = self.runner.invoke(app, ["other", "rating", "list", "--config", str(self.path), "--stdout"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(json.loads(result.stdout), payload)
        request.assert_called_once()
        self.assertEqual(request.call_args.args[0], "GET")
        self.assertTrue(request.call_args.args[1].endswith("/GetStudentRate"))
        self.assertEqual(request.call_args.kwargs["params"], {
            "campusCode": "TEST", "rollNumber": "TEST000", "Authen": "FAKE_FAP_KEY", "checksum": "SYNTHETIC_RATE_LIST"})
        checksum.assert_called_once_with("TEST000", "TEST")

    def test_rating_list_v2_stub_is_rejected_before_session_load_or_http(self):
        self.save_session("v2")
        with patch("myfap.auth.MyFapAuth.load_session") as load, patch("requests.Session.request") as request:
            result = self.runner.invoke(app, ["--config", str(self.path), "other", "rating", "list", "--stdout"])
        self.assertEqual(result.exit_code, 1)
        self.assertEqual(result.stdout, "")
        self.assertIn("GetStudentRate", result.stderr)
        load.assert_not_called()
        request.assert_not_called()


class V1ObservedFailureTests(unittest.TestCase):
    setUp = BalanceCommandTests.setUp
    save_session = BalanceCommandTests.save_session

    def test_http_404_and_unexplained_201_remain_failures_without_refresh_or_fallback(self):
        # Only status/shape from live; every input and session here is synthetic.
        for command, operation, status, payload, message in (
            (["courses", "--semester", "FAKE_TERM"], "GetCourseOfSemester", 404, None, "HTTP 404"),
            (["marks", "--summary"], "GetSemesterMark", 404, None, "HTTP 404"),
            (["news", "--search", "synthetic"], "SearchNews", 200, {"code": 201, "data": None}, "201"),
            (["other", "training", "--semester", "FAKE_TERM"], "GetDiemphongtrao", 200, {"code": 201, "data": None}, "201"),
        ):
            with self.subTest(operation=operation):
                self.save_session("v1")
                before = self.path.read_bytes()
                with patch("requests.Session.request", return_value=response(payload, status)) as request, \
                     patch("myfap.auth.MyFapAuth.refresh_session") as refresh:
                    result = self.runner.invoke(app, ["--config", str(self.path), *command, "--stdout"])
                self.assertEqual(result.exit_code, 1)
                self.assertEqual(result.stdout, "")
                self.assertIn(message, Text.from_ansi(result.stderr).plain)
                request.assert_called_once()
                self.assertEqual(urlsplit(request.call_args.args[1]).netloc, "api.fpt.edu.vn")
                self.assertTrue(request.call_args.args[1].endswith('/' + operation))
                refresh.assert_not_called()
                self.assertEqual(self.path.read_bytes(), before)


class FeedbackListTests(unittest.TestCase):
    setUp = BalanceCommandTests.setUp
    save_session = BalanceCommandTests.save_session

    def test_feedbacks_v2_reads_exact_contract_and_preserves_envelope(self):
        self.save_session("v2")
        payload = {"code": 200, "data": [{"synthetic": "feedback item"}]}
        with patch("requests.Session.request", return_value=response(payload)) as request:
            result = self.runner.invoke(app, ["--config", str(self.path), "other", "feedbacks", "--stdout"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(json.loads(result.stdout), payload)
        request.assert_called_once()
        self.assertEqual(request.call_args.args[0], "GET")
        self.assertTrue(request.call_args.args[1].endswith("/GetStudentFeedbacks"))
        self.assertEqual(request.call_args.kwargs["params"], {"CampusCode": "TEST", "rollNumber": "TEST000"})
        self.assertNotIn("Authen", request.call_args.kwargs["params"])
        self.assertEqual(request.call_args.kwargs["headers"]["Authorization"], "Bearer FAKE_FAP_KEY")
        self.assertNotIn("json", request.call_args.kwargs)

    def test_feedbacks_preserves_empty_list(self):
        self.save_session("v2")
        payload = {"code": 200, "data": []}
        with patch("requests.Session.request", return_value=response(payload)) as request:
            result = self.runner.invoke(app, ["--config", str(self.path), "other", "feedbacks", "--stdout"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(json.loads(result.stdout), payload)
        request.assert_called_once()

    def test_feedbacks_v1_is_rejected_before_http(self):
        self.save_session("v1")
        with patch("requests.Session.request") as request:
            result = self.runner.invoke(app, ["--config", str(self.path), "other", "feedbacks", "--stdout"])
        self.assertEqual(result.exit_code, 1)
        self.assertEqual(result.stdout, "")
        self.assertIn("GetStudentFeedbacks", Text.from_ansi(result.stderr).plain)
        request.assert_not_called()


class ExamsIcsCommandTests(unittest.TestCase):
    setUp = BalanceCommandTests.setUp
    save_session = BalanceCommandTests.save_session

    ROW = {"subjectCode": "TEST101", "realSubject": "TEST101", "subjectName": "Môn thử nghiệm",
           "date": "2026-10-20T00:00:00", "slot": "Synthetic slot (7h30-9h50)", "time": "7h30-9h50",
           "note": "", "roomNo": "SY-101", "dateofPublication": "2026-10-01T00:00:00",
           "kythi": "FE", "note_Attendance": "", "isGraduated": False}

    def test_exams_ics_outputs_calendar_and_plain_keeps_json(self):
        payload = {"code": 200, "data": [dict(self.ROW)]}
        for options, expect_ics, expect_full in (
            ([], False, False),
            (["--ics"], True, False),
            (["--ics", "--full"], True, True),
            (["--full"], False, False),
        ):
            with self.subTest(options=options):
                self.save_session("v2")
                with patch("requests.Session.request", return_value=response(payload)) as request:
                    result = self.runner.invoke(app, ["--config", str(self.path), "exams", "--semester", "FAKE_TERM", *options, "--stdout"])
                self.assertEqual(result.exit_code, 0, result.output)
                if expect_ics:
                    self.assertTrue(result.stdout.startswith("BEGIN:VCALENDAR"))
                    self.assertIn("BEGIN:VEVENT", result.stdout)
                    self.assertIn("TEST101 (FE)", result.stdout)
                    self.assertIn("Môn: Môn thử nghiệm", result.stdout)
                    self.assertIn("Phòng: SY-101", result.stdout)
                    self.assertIn("Ngày công bố: 2026-10-01", result.stdout)
                    if expect_full:
                        self.assertIn("Mã slot: Synthetic slot", result.stdout)
                    else:
                        self.assertNotIn("Mã slot", result.stdout)
                else:
                    self.assertEqual(json.loads(result.stdout), payload)
                    # Mặc định JSON luôn bảo toàn toàn bộ thông tin gốc kể cả slot/UUID
                    self.assertEqual(json.loads(result.stdout)["data"][0]["slot"], "Synthetic slot (7h30-9h50)")
                request.assert_called_once()
                self.assertTrue(request.call_args.args[1].endswith("/GetScheduleExam"))
                query = request.call_args.kwargs["params"]
                self.assertEqual(query.get("Semester"), "FAKE_TERM")


class ReadSliceAcceptanceTests(unittest.TestCase):
    """Nghiệm thu nhóm mục 1: header contract và ma trận lỗi tại seam CLI."""

    COMMANDS = (
        (["other", "balance"], "GetBalance"),
        (["courses", "--semester", "FAKE_TERM"], "GetCourseOfSemester"),
        (["other", "subjects", "--semester", "FAKE_TERM"], "GetSubjectBySemester"),
        (["news", "--search", "synthetic"], "SearchNews"),
    )

    setUp = BalanceCommandTests.setUp
    save_session = BalanceCommandTests.save_session

    def test_v2_headers_carry_client_contract_and_get_has_no_body(self):
        self.save_session("v2")
        for command, operation in self.COMMANDS:
            with self.subTest(operation=operation):
                with patch("requests.Session.request", return_value=response({"code": 200, "data": []})) as request:
                    result = self.runner.invoke(app, ["--config", str(self.path), *command, "--stdout"])
                self.assertEqual(result.exit_code, 0, result.output)
                self.assertEqual(json.loads(result.stdout), {"code": 200, "data": []})
                self.assertEqual(request.call_args.args[0], "GET")
                self.assertTrue(request.call_args.args[1].endswith("/" + operation))
                headers = request.call_args.kwargs["headers"]
                self.assertEqual(headers["ClientCode"], "MyFAP")
                self.assertEqual(headers["CampusCode"], "TEST")
                self.assertEqual(headers["Authorization"], "Bearer FAKE_FAP_KEY")
                signature, separator, timestamp = headers["Checksum"].partition(":")
                self.assertEqual(separator, ":")
                self.assertTrue(signature and signature.isascii())
                self.assertTrue(timestamp and timestamp.isascii() and timestamp.isdecimal())
                self.assertNotIn("json", request.call_args.kwargs)
                self.assertNotIn("Content-Type", headers)

    def test_expiry_retries_once_with_fresh_credential_at_cli_seam(self):
        signals = (
            ("v1", {"code": 201, "message": "Token invalid", "data": None}, 200),
            ("v2", {"code": 401, "data": None}, 200),
            ("v2", {"code": 200, "data": []}, 401),
        )
        for command, operation in self.COMMANDS:
            for version, expired, status in signals:
                with self.subTest(operation=operation, version=version, status=status):
                    self.save_session(version)
                    original = self.path.read_bytes()

                    def refresh(auth):
                        auth.authen_key = "FAKE_NEW_KEY"
                        return True

                    with patch("requests.Session.request",
                               side_effect=[response(expired, status), response({"code": 200, "data": []})]) as request, \
                         patch("myfap.auth.MyFapAuth.refresh_session", autospec=True, side_effect=refresh) as rotation:
                        result = self.runner.invoke(app, ["--config", str(self.path), *command, "--stdout"])
                    self.assertEqual(result.exit_code, 0, result.output)
                    self.assertEqual(json.loads(result.stdout), {"code": 200, "data": []})
                    self.assertEqual(request.call_count, 2)
                    rotation.assert_called_once()
                    first, second = request.call_args_list
                    self.assertTrue(first.args[1].endswith("/" + operation))
                    self.assertTrue(second.args[1].endswith("/" + operation))
                    if version == "v1":
                        self.assertEqual(first.kwargs["params"]["Authen"], "FAKE_FAP_KEY")
                        self.assertEqual(second.kwargs["params"]["Authen"], "FAKE_NEW_KEY")
                    else:
                        self.assertEqual(first.kwargs["headers"]["Authorization"], "Bearer FAKE_FAP_KEY")
                        self.assertEqual(second.kwargs["headers"]["Authorization"], "Bearer FAKE_NEW_KEY")
                        self.assertNotEqual(first.kwargs["headers"]["Checksum"], second.kwargs["headers"]["Checksum"])
                        self.assertEqual(
                            {key: value for key, value in first.kwargs["params"].items() if key != "Authen"},
                            {key: value for key, value in second.kwargs["params"].items() if key != "Authen"},
                        )
                    self.assertEqual(self.path.read_bytes(), original)
                    self.assertNotIn("FAKE_FAP_KEY", result.stdout + result.stderr)

    def test_second_expiry_stops_after_single_retry(self):
        signals = (
            ("v1", {"code": 201, "message": "Token invalid", "data": None}, 200),
            ("v2", {"code": 401, "data": None}, 200),
        )
        for version, expired, status in signals:
            with self.subTest(version=version):
                self.save_session(version)

                def refresh(auth):
                    auth.authen_key = "FAKE_NEW_KEY"
                    return True

                with patch("requests.Session.request",
                           side_effect=[response(expired, status), response(expired, status)]) as request, \
                     patch("myfap.auth.MyFapAuth.refresh_session", autospec=True, side_effect=refresh) as rotation:
                    result = self.runner.invoke(app, ["--config", str(self.path), "other", "balance", "--stdout"])
                self.assertEqual(result.exit_code, 1)
                self.assertEqual(result.stdout, "")
                self.assertEqual(request.call_count, 2)
                rotation.assert_called_once()

    def test_app_check_timeout_and_5xx_fail_once_without_refresh_or_fallback(self):
        import requests as requests_module

        failures = (
            (response({"code": "APP_CHECK_FAILED"}), "APP_CHECK_FAILED"),
            (requests_module.Timeout("PRIVATE_SENTINEL_URL"), "thử lại sau"),
            (response(None, 503), "HTTP 503"),
        )
        for version in ("v1", "v2"):
            for command, operation in self.COMMANDS:
                for failure, message in failures:
                    with self.subTest(version=version, operation=operation, message=message):
                        self.save_session(version)
                        before = self.path.read_bytes()
                        with patch("requests.Session.request", side_effect=[failure]) as request, \
                             patch("myfap.auth.MyFapAuth.refresh_session") as refresh:
                            result = self.runner.invoke(app, ["--config", str(self.path), *command, "--stdout"])
                        self.assertEqual(result.exit_code, 1)
                        self.assertEqual(result.stdout, "")
                        self.assertIn(message, Text.from_ansi(result.stderr).plain)
                        self.assertNotIn("PRIVATE_SENTINEL_URL", Text.from_ansi(result.stderr).plain)
                        self.assertEqual(request.call_count, 1)
                        self.assertTrue(request.call_args.args[1].endswith("/" + operation))
                        refresh.assert_not_called()
                        self.assertEqual(self.path.read_bytes(), before)

    def test_malformed_payload_is_reported_without_retry_or_refresh(self):
        cases = (
            (response("invalid-envelope"), "phải có code và data"),
            (response({"code": "ok", "data": []}), "không hợp lệ"),
        )
        for version in ("v1", "v2"):
            for command, operation in self.COMMANDS:
                for failure, message in cases:
                    with self.subTest(version=version, operation=operation, message=message):
                        self.save_session(version)
                        with patch("requests.Session.request", side_effect=[failure]) as request, \
                             patch("myfap.auth.MyFapAuth.refresh_session") as refresh:
                            result = self.runner.invoke(app, ["--config", str(self.path), *command, "--stdout"])
                        self.assertEqual(result.exit_code, 1)
                        self.assertEqual(result.stdout, "")
                        self.assertIn(message, Text.from_ansi(result.stderr).plain)
                        self.assertEqual(request.call_count, 1)
                        self.assertTrue(request.call_args.args[1].endswith("/" + operation))
                        refresh.assert_not_called()


class OtherCommandLayoutTests(unittest.TestCase):
    setUp = BalanceCommandTests.setUp
    save_session = BalanceCommandTests.save_session

    def test_training_and_rating_inherit_options_at_nested_leaf(self):
        self.save_session("v1")
        for command, operation in (
            (["other", "--api-version", "v2", "training", "--semester", "FAKE_TERM"], "GetDiemphongtrao"),
            (["other", "--api-version", "v2", "rating", "--api-version", "v2", "list"], "GetStudentRate"),
        ):
            with self.subTest(operation=operation), patch("requests.Session.request", return_value=response({"code": 200, "data": []})) as request:
                result = self.runner.invoke(app, ["--api-version", "v2", *command,
                    "--config", str(self.path), "--api-version", "v1", "--timeout", "31", "--stdout"])
                self.assertEqual(result.exit_code, 0, result.output)
                self.assertEqual(json.loads(result.stdout), {"code": 200, "data": []})
                request.assert_called_once()
                self.assertTrue(request.call_args.args[1].endswith('/' + operation))
                self.assertEqual(urlsplit(request.call_args.args[1]).netloc, "api.fpt.edu.vn")
                self.assertEqual(request.call_args.kwargs["timeout"], 31)

    def test_new_help_paths_work_and_old_root_commands_are_absent_without_auth(self):
        with patch("myfap.cli.get_auth") as auth, patch("requests.Session.request") as request:
            for command in (["other"], ["other", "training"], ["other", "rating"], ["other", "rating", "list"]):
                with self.subTest(command=command):
                    result = self.runner.invoke(app, [*command, "--help"])
                    self.assertEqual(result.exit_code, 0, result.output)
            result = self.runner.invoke(app, ["other", "--help"])
            text = Text.from_ansi(result.stdout).plain
            self.assertIn("training", text)
            self.assertIn("rating", text)
            for command in (["training"], ["rating", "list"]):
                with self.subTest(old_command=command):
                    result = self.runner.invoke(app, [*command, "--help"])
                    self.assertEqual(result.exit_code, 2)
            auth.assert_not_called()
            request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
