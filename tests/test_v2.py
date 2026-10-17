import base64
import hashlib
import hmac
import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

import requests

from myfap import v2
from myfap.errors import ApiError


class V2ChecksumTests(unittest.TestCase):
    def test_checksum_uses_utf8_key_and_seconds_with_header_padding(self):
        key, credential, timestamp = "f00d1234", "fake+/credential=", 1729000000
        message = f"{credential}MyFAP{timestamp}".encode("utf-8")
        expected = base64.b64encode(hmac.new(key.encode("utf-8"), message, hashlib.sha256).digest()).decode("ascii").replace("=", "%3d")
        with patch.object(v2, "V2_SECRET_KEY", key):
            actual = v2.create_checksum(credential, timestamp)
        self.assertEqual(actual, f"{expected}:{timestamp}")
        decoded_hex = base64.b64encode(hmac.new(bytes.fromhex(key), message, hashlib.sha256).digest()).decode("ascii").replace("=", "%3d")
        self.assertNotEqual(actual, f"{decoded_hex}:{timestamp}")
        self.assertTrue(actual.endswith(f"%3d:{timestamp}"))
        self.assertNotIn("%253d", actual)

    def test_checksum_uses_one_current_second_when_timestamp_is_omitted(self):
        with patch("myfap.v2.time.time", return_value=1729000000.999):
            actual = v2.create_checksum("fake-credential")
        self.assertTrue(actual.endswith(":1729000000"))

    def test_checksum_rejects_invalid_inputs_without_echoing_them(self):
        for credential, timestamp in ((None, 0), ("", 0), ("fake\r\nSECRET", 0), ("fake", True), ("fake", -1), ("fake", 1.5)):
            with self.subTest(credential=credential, timestamp=timestamp):
                with self.assertRaises(ApiError) as caught:
                    v2.create_checksum(credential, timestamp)
                self.assertNotIn("SECRET", str(caught.exception))


class V2TransportTests(unittest.TestCase):
    def setUp(self):
        self.session = Mock()
        self.response = Mock()
        self.session.request.return_value = self.response

    def test_bootstrap_uses_post_empty_json_and_bootstrap_campus_and_identity(self):
        for operation in ("GetAllActiveCampus", "GetApiActive"):
            with self.subTest(operation=operation), patch.object(v2, "V2_BOOTSTRAP_TOKEN", "fake-bootstrap"), patch.object(v2, "create_checksum", return_value="fake%3d:123") as signer:
                actual = v2.request(self.session, operation, campus="APHL", timeout=2.5)
                call = self.session.request.call_args
                self.assertIs(actual, self.response)
                self.assertEqual(call.args, ("POST", f"{v2.FAP_PROXY_HOST}/{operation}"))
                self.assertEqual(call.kwargs["params"], {})
                self.assertEqual(call.kwargs["json"], {})
                self.assertEqual(call.kwargs["headers"], {"ClientCode": "MyFAP", "Content-Type": "application/json", "CampusCode": "HN", "Authorization": "Bearer fake-bootstrap", "Checksum": "fake%3d:123"})
                self.assertEqual(call.kwargs["timeout"], 2.5)
                self.assertFalse(call.kwargs["allow_redirects"])
                signer.assert_called_once_with("fake-bootstrap")

    def test_handshake_uses_feid_identity_in_body_and_headers_but_not_query(self):
        with patch.object(v2, "create_checksum", return_value="fake%3d:123") as signer:
            v2.request(self.session, "AuthenticationByFeId", credential="fake-feid+/=", campus="TEST&campus", timeout=45)
        call = self.session.request.call_args
        self.assertEqual(call.args, ("POST", f"{v2.FAP_PROXY_HOST}/AuthenticationByFeId"))
        self.assertEqual(call.kwargs["params"], {})
        self.assertEqual(call.kwargs["json"], {"token": "fake-feid+/="})
        self.assertEqual(call.kwargs["headers"]["Authorization"], "Bearer fake-feid+/=")
        self.assertEqual(call.kwargs["headers"]["CampusCode"], "TEST&campus")
        self.assertEqual(call.kwargs["timeout"], 45)
        signer.assert_called_once_with("fake-feid+/=")
        self.assertNotIn("fake-feid", call.args[1])
        self.assertFalse(call.kwargs["allow_redirects"])

    def test_semester_has_empty_query_and_schedule_uses_exact_v2_case(self):
        cases = (("GetSemester", None, {}), ("GetActivityStudent", {"rollNumber": "FAKE+ROLL", "Semester": "opaque&term"}, {"CampusCode": "TEST&campus", "rollNumber": "FAKE+ROLL", "Semester": "opaque&term"}))
        for operation, params, expected in cases:
            with self.subTest(operation=operation), patch.object(v2, "create_checksum", return_value="fake%3d:123") as signer:
                v2.request(self.session, operation, credential="fake-fap+/=", campus="TEST&campus", params=params, timeout=3)
                call = self.session.request.call_args
                self.assertEqual(call.args, ("GET", f"{v2.FAP_PROXY_HOST}/{operation}"))
                self.assertEqual(call.kwargs["params"], expected)
                self.assertNotIn("json", call.kwargs)
                self.assertEqual(call.kwargs["headers"]["Authorization"], "Bearer fake-fap+/=")
                self.assertEqual(call.kwargs["headers"]["Checksum"], "fake%3d:123")
                signer.assert_called_once_with("fake-fap+/=")
                prepared = requests.Request("GET", call.args[1], params=call.kwargs["params"], headers=call.kwargs["headers"]).prepare()
                self.assertEqual(parse_qs(urlsplit(prepared.url).query), {key: [value] for key, value in expected.items()})
                self.assertNotIn("fake-fap", prepared.url)
                self.assertEqual(prepared.headers["Checksum"], "fake%3d:123")
                self.assertFalse(call.kwargs["allow_redirects"])

    def test_response_is_returned_without_classification_or_retry(self):
        self.response.status_code = 401
        self.assertIs(v2.request(self.session, "GetSemester", credential="fake", campus="TEST"), self.response)
        self.session.request.assert_called_once()
        self.response.json.assert_not_called()

    def test_unsupported_operation_fails_before_http_with_no_value_echo(self):
        for operation in ("GetStudentMark", "getCourseAttendance", "GetCourseAttendance", "AddRate", "https://PRIVATE_SECRET.invalid/", "UnknownOperation", None, []):
            with self.subTest(operation=operation), self.assertRaises(ApiError) as caught:
                v2.request(self.session, operation, credential="PRIVATE_SECRET", campus="TEST")
            self.assertNotIn("PRIVATE_SECRET", str(caught.exception))
        self.session.request.assert_not_called()

    def test_invalid_credential_campus_query_or_body_fails_before_http(self):
        cases = [
            ("GetSemester", {"credential": "", "campus": "TEST"}),
            ("GetSemester", {"credential": "fake", "campus": None}),
            ("GetSemester", {"credential": "fake", "campus": "TEST\r\nSECRET"}),
            ("GetSemester", {"credential": "fake", "campus": "TEST", "params": {"Authen": "SECRET"}}),
            ("GetSemester", {"credential": "fake", "campus": "TEST", "body": {}}),
            ("AuthenticationByFeId", {"credential": "fake", "campus": "TEST", "body": {"token": "other-SECRET"}}),
            ("GetActivityStudent", {"credential": "fake", "campus": "TEST", "params": {"rollNumber": "FAKE"}}),
            ("GetActivityStudent", {"credential": "fake", "campus": "TEST", "params": {"rollNumber": "FAKE", "Semester": "TERM", "campusCode": "TEST"}}),
            ("GetActivityStudent", {"credential": "fake", "campus": "TEST", "params": {"rollNumber": "FAKE", "Semester": "TERM", "CampusCode": "OTHER"}}),
            ("GetAllActiveCampus", {"credential": "SECRET"}),
            ("GetApiActive", {"params": {"Authen": "SECRET"}}),
        ]
        for operation, kwargs in cases:
            with self.subTest(operation=operation, kwargs=kwargs), self.assertRaises(ApiError) as caught:
                v2.request(self.session, operation, **kwargs)
            self.assertNotIn("SECRET", str(caught.exception))
        self.session.request.assert_not_called()

    def test_network_errors_do_not_expose_credential_url_or_body(self):
        self.session.request.side_effect = requests.Timeout("PRIVATE_SECRET URL AND BODY")
        with self.assertRaises(ApiError) as caught:
            v2.request(self.session, "GetSemester", credential="fake", campus="TEST")
        self.assertNotIn("PRIVATE_SECRET", str(caught.exception))
        self.assertIsNone(caught.exception.__cause__)



if __name__ == "__main__":
    unittest.main()
