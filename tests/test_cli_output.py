import io
import json
import os
import subprocess
import sys
import unittest
from contextlib import redirect_stdout

from rich.text import Text

from myfap.cli import save_output


class JSONOutputTests(unittest.TestCase):
    def setUp(self):
        self.payload = {"code": 200, "data": [{"title": "Thông báo học vụ", "course": "Lập trình cơ bản", "note": "Thử nghiệm 📚"}]}

    def test_json_stdout_uses_utf8_independent_of_text_encoding_and_newline(self):
        expected = (json.dumps(self.payload, ensure_ascii=False, indent=4) + "\n").encode("utf-8")
        for encoding in ("cp1252", "utf-8"):
            for newline in ("\n", "\r\n"):
                with self.subTest(encoding=encoding, newline=newline):
                    buffer = io.BytesIO()
                    with io.TextIOWrapper(buffer, encoding=encoding, newline=newline) as output:
                        with redirect_stdout(output):
                            save_output(self.payload, "unused.json", None, True)
                        output.flush()
                        raw = buffer.getvalue()
                    self.assertEqual(raw, expected)
                    self.assertEqual(json.loads(raw.decode("utf-8")), self.payload)

    def test_json_stdout_supports_text_only_streams(self):
        output = io.StringIO()
        with redirect_stdout(output):
            save_output(self.payload, "unused.json", None, True)
        self.assertEqual(output.getvalue(), json.dumps(self.payload, ensure_ascii=False, indent=4) + "\n")

    def test_cli_json_stdout_is_utf8_when_child_process_uses_cp1252(self):
        code = f"""
from types import SimpleNamespace
from unittest.mock import Mock, patch
from myfap.cli import app

auth = SimpleNamespace(campus="TEST", api_version="v1", load_session=Mock(return_value=True), resolve_api_version=Mock(return_value="v1"))
with patch("myfap.cli.get_auth", return_value=auth), patch("myfap.cli.MyFapClient") as client:
    client.return_value.get_student_info.return_value = {self.payload!r}
    app()
"""
        result = subprocess.run(
            [sys.executable, "-c", code, "info", "student", "--stdout"],
            env={**os.environ, "PYTHONIOENCODING": "cp1252:strict", "PYTHONUTF8": "0"},
            capture_output=True, timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout.decode("utf-8")), self.payload)
        self.assertEqual(result.stderr, b"")


class TableOutputTests(unittest.TestCase):
    def test_cli_tables_use_utf8_when_child_process_uses_cp1252(self):
        code = """
from types import SimpleNamespace
from unittest.mock import Mock, patch
from myfap.cli import app

auth = SimpleNamespace(campus="HN", load_session=Mock(return_value=True), resolve_api_version=Mock(return_value="v1"))
with patch("myfap.cli.get_auth", return_value=auth), patch("myfap.cli.MyFapEssential") as essential:
    essential.return_value.get_campuses.return_value = [{"campusName": "Cơ sở Hà Nội", "campusCode": "HN"}]
    essential.return_value.get_semesters.return_value = [{"semesterName": "Học kỳ mùa thu"}]
    app()
"""
        for command, expected in (("campuses", "Cơ sở Hà Nội"), ("semesters", "Học kỳ mùa thu")):
            with self.subTest(command=command):
                result = subprocess.run(
                    [sys.executable, "-c", code, command],
                    env={**os.environ, "PYTHONIOENCODING": "cp1252:strict", "PYTHONUTF8": "0"},
                    capture_output=True, timeout=20,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(expected, result.stdout.decode("utf-8"))
                self.assertEqual(result.stderr, b"")


class HelpOutputTests(unittest.TestCase):
    def test_plain_help_preserves_unicode_with_legacy_stdout(self):
        code = """
from unittest.mock import patch
from myfap.cli import app
app.rich_markup_mode = None
with patch("myfap.cli.get_auth", side_effect=AssertionError("help must not load auth")):
    app()
"""
        result = subprocess.run(
            [sys.executable, "-c", code, "--help"],
            env={**os.environ, "PYTHONIOENCODING": "cp1252:strict", "PYTHONUTF8": "0", "COLUMNS": "160"},
            capture_output=True, timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        self.assertIn("Đường dẫn file session tùy chỉnh", " ".join(result.stdout.decode("utf-8").split()))
        self.assertEqual(result.stderr, b"")

    def test_root_group_and_command_help_preserve_unicode_with_legacy_stdout(self):
        code = """
from unittest.mock import patch
from myfap.cli import app
with patch("myfap.cli.get_auth", side_effect=AssertionError("help must not load auth")), patch("requests.Session.request", side_effect=AssertionError("help must not call HTTP")):
    app()
"""
        for command in ([], ["info"], ["info", "student"], ["other", "survey"], ["schedule"]):
            for encoding, utf8 in (("cp1252:strict", "0"), ("utf-8", "1")):
                with self.subTest(command=command, encoding=encoding):
                    result = subprocess.run(
                        [sys.executable, "-c", code, *command, "--help"],
                        env={**os.environ, "PYTHONIOENCODING": encoding, "PYTHONUTF8": utf8, "COLUMNS": "160", "FORCE_COLOR": "1"},
                        capture_output=True, timeout=20,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr[-2000:])
                    output = " ".join(Text.from_ansi(result.stdout.decode("utf-8").replace("\r\n", "\n")).plain.split())
                    self.assertIn("--api-version", output)
                    self.assertIn("--config", output)
                    self.assertIn("Đường dẫn file session tùy chỉnh", output)
                    self.assertEqual(result.stderr, b"")
