from __future__ import annotations

import hashlib
import io
import json
import subprocess
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from scripts import smoke_index


VERSION = "0.2.0"


class SmokeIndexTests(unittest.TestCase):
    def test_release_is_available_when_index_contains_expected_files(self):
        payload = {
            "info": {"name": "myfap", "version": VERSION},
            "urls": [
                {"filename": f"myfap-{VERSION}-py3-none-any.whl", "digests": {"sha256": "a" * 64}},
                {"filename": f"myfap-{VERSION}.tar.gz", "digests": {"sha256": "b" * 64}},
            ],
        }
        with patch.object(smoke_index, "fetch_index", return_value=payload):
            result = smoke_index.wait_for_release("https://pypi.invalid/pypi", VERSION, attempts=1, delay=0)
        self.assertEqual(result.state, "available")
        self.assertEqual(result.files, (f"myfap-{VERSION}-py3-none-any.whl", f"myfap-{VERSION}.tar.gz"))

    def test_index_not_found_is_retried_then_reported(self):
        with patch.object(smoke_index, "fetch_index", side_effect=smoke_index.IndexNotReady):
            result = smoke_index.wait_for_release("https://pypi.invalid/pypi", VERSION, attempts=2, delay=0)
        self.assertEqual(result.state, "missing")

    def test_partial_index_is_retried_until_both_artifacts_are_visible(self):
        partial = {"info": {"name": "myfap", "version": VERSION}, "urls": [{"filename": f"myfap-{VERSION}-py3-none-any.whl", "digests": {"sha256": "a" * 64}}]}
        complete = {"info": {"name": "myfap", "version": VERSION}, "urls": [
            {"filename": f"myfap-{VERSION}-py3-none-any.whl", "digests": {"sha256": "a" * 64}},
            {"filename": f"myfap-{VERSION}.tar.gz", "digests": {"sha256": "b" * 64}},
        ]}
        with patch.object(smoke_index, "fetch_index", side_effect=[partial, complete]) as fetch:
            result = smoke_index.wait_for_release("https://pypi.invalid/pypi", VERSION, attempts=2, delay=0)
        self.assertEqual(result.state, "available")
        self.assertEqual(fetch.call_count, 2)

    def test_pip_environment_isolated_from_index_overrides(self):
        environment = smoke_index.pip_environment({
            "PIP_EXTRA_INDEX_URL": "https://private.invalid/simple", "PIP_CONFIG_FILE": "private.ini",
            "PYTHONPATH": "private-package", "PYTHONHOME": "private-python", "PATH": "keep-path",
        })
        self.assertEqual(environment["PIP_CONFIG_FILE"], smoke_index.os.devnull)
        self.assertNotIn("PIP_EXTRA_INDEX_URL", environment)
        self.assertNotIn("PYTHONPATH", environment)
        self.assertNotIn("PYTHONHOME", environment)
        self.assertEqual(environment["PATH"], "keep-path")

    def test_production_cli_installs_pinned_version_in_external_venv(self):
        payload = {
            "info": {"name": "myfap", "version": VERSION},
            "urls": [{"filename": f"myfap-{VERSION}-py3-none-any.whl", "digests": {"sha256": "a" * 64}}, {"filename": f"myfap-{VERSION}.tar.gz", "digests": {"sha256": "b" * 64}}],
        }
        commands = []

        def run(command, **kwargs):
            commands.append((command, kwargs))
            output = ""
            if command[-1] == "version":
                output = f"MyFap API CLI version: {VERSION}\n"
            elif "importlib.metadata" in command[-1]:
                output = VERSION + "\n"
            return subprocess.CompletedProcess(command, 0, stdout=output, stderr="")

        output = io.StringIO()
        args = ["smoke_index.py", "--expected-version", VERSION, "--attempts", "1", "--delay", "0"]
        with patch("sys.argv", args), patch.object(smoke_index.urllib.request, "urlopen", return_value=io.BytesIO(json.dumps(payload).encode())), patch.object(smoke_index.subprocess, "run", side_effect=run), redirect_stdout(output):
            self.assertEqual(smoke_index.main(), 0)
        self.assertEqual(output.getvalue(), f"smoke_index=ok version={VERSION} index=pypi\n")
        installs = [(command, options) for command, options in commands if "install" in command]
        self.assertEqual(len(installs), 1)
        command, options = installs[0]
        self.assertEqual(command[-1], f"myfap=={VERSION}")
        self.assertIn("https://pypi.org/simple/", command)
        self.assertIn("--no-cache-dir", command)
        self.assertIn("--isolated", command)
        self.assertEqual(options["env"]["PIP_CONFIG_FILE"], smoke_index.os.devnull)
        self.assertNotIn(Path(__file__).resolve().parents[1], Path(options["cwd"]).parents)
        self.assertFalse(Path(options["cwd"]).exists())

    def test_index_hashes_must_match_trusted_local_manifest(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            names = (f"myfap-{VERSION}-py3-none-any.whl", f"myfap-{VERSION}.tar.gz")
            manifest = b""
            metadata = {}
            for name in names:
                (root / name).write_bytes(name.encode())
                digest = hashlib.sha256(name.encode()).hexdigest()
                manifest += f"{digest}  {name}\n".encode()
                metadata[name] = {"digests": {"sha256": digest}}
            (root / "SHA256SUMS").write_bytes(manifest)
            manifest_hash = hashlib.sha256(manifest).hexdigest()
            smoke_index.verify_index_files(root, metadata, VERSION, manifest_hash)
            metadata[names[0]]["digests"]["sha256"] = "0" * 64
            with self.assertRaises(smoke_index.SmokeIndexError):
                smoke_index.verify_index_files(root, metadata, VERSION, manifest_hash)

    def test_cli_requires_manifest_digest_with_artifact_directory(self):
        stderr = io.StringIO()
        with patch("sys.argv", ["smoke_index.py", "--expected-version", VERSION, "--artifact-dir", "missing-dir"]), redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as result:
                smoke_index.main()
        self.assertEqual(result.exception.code, 2)
        self.assertIn("--manifest-sha256", stderr.getvalue())
        self.assertNotIn("unrecognized arguments", stderr.getvalue())

    def test_testpypi_downloads_only_wheel_and_resolves_dependencies_on_pypi(self):
        wheel_name = f"myfap-{VERSION}-py3-none-any.whl"
        payload = {"info": {"name": "myfap", "version": VERSION}, "urls": [
            {"filename": wheel_name, "digests": {"sha256": hashlib.sha256(b"wheel").hexdigest()}, "url": "https://files.invalid/wheel"},
            {"filename": f"myfap-{VERSION}.tar.gz", "digests": {"sha256": "b" * 64}},
        ]}
        commands = []

        def run(command, **kwargs):
            commands.append(command)
            if "download" in command:
                destination = Path(command[command.index("--dest") + 1])
                destination.mkdir(exist_ok=True)
                (destination / wheel_name).write_bytes(b"wheel")
            output = ""
            if command[-1] == "version":
                output = f"MyFap API CLI version: {VERSION}\n"
            elif "importlib.metadata" in command[-1]:
                output = VERSION + "\n"
            return subprocess.CompletedProcess(command, 0, stdout=output, stderr="")

        with patch("sys.argv", ["smoke_index.py", "--expected-version", VERSION, "--test-pypi", "--attempts", "1"]), patch.object(smoke_index.urllib.request, "urlopen", return_value=io.BytesIO(json.dumps(payload).encode())), patch.object(smoke_index.subprocess, "run", side_effect=run), redirect_stdout(io.StringIO()):
            self.assertEqual(smoke_index.main(), 0)
        downloads = [command for command in commands if "download" in command]
        self.assertEqual(len(downloads), 1)
        self.assertIn("--no-deps", downloads[0])
        self.assertIn("https://test.pypi.org/simple/", downloads[0])
        installs = [command for command in commands if "install" in command]
        self.assertEqual(len(installs), 1)
        self.assertTrue(installs[0][-1].endswith(wheel_name))
        self.assertNotIn("--no-deps", installs[0])
        self.assertIn("https://pypi.org/simple/", installs[0])
        self.assertTrue(all("--extra-index-url" not in command for command in commands))

    def test_corrupt_testpypi_download_is_rejected_before_install(self):
        wheel_name = f"myfap-{VERSION}-py3-none-any.whl"
        report = smoke_index.IndexReport("available", (wheel_name,), {
            wheel_name: {"digests": {"sha256": hashlib.sha256(b"expected wheel").hexdigest()}},
        })
        commands = []

        def run(command, cwd):
            commands.append(command)
            if "download" in command:
                destination = Path(command[command.index("--dest") + 1])
                (destination / wheel_name).write_bytes(b"modified wheel")
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        with patch.object(smoke_index, "wait_for_release", return_value=report), patch.object(smoke_index, "run_process", side_effect=run):
            with self.assertRaises(smoke_index.SmokeIndexError):
                smoke_index.smoke_index(VERSION, test_pypi=True)
        self.assertTrue(any("download" in command for command in commands))
        self.assertFalse(any("install" in command for command in commands))

    def test_install_failure_is_not_retried_as_index_delay(self):
        report = smoke_index.IndexReport("available", (), {})
        commands = []

        def run(command, cwd):
            commands.append(command)
            if "install" in command:
                raise smoke_index.SmokeIndexError("Dependency install failed")
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        with patch.object(smoke_index, "wait_for_release", return_value=report) as wait, patch.object(smoke_index, "run_process", side_effect=run):
            with self.assertRaises(smoke_index.SmokeIndexError):
                smoke_index.smoke_index(VERSION)
        self.assertEqual(wait.call_count, 1)
        self.assertEqual(sum("install" in command for command in commands), 1)

    def test_malformed_duplicate_yanked_or_wrong_identity_index_fails_without_retry(self):
        wheel = {"filename": f"myfap-{VERSION}-py3-none-any.whl", "digests": {"sha256": "a" * 64}}
        sdist = {"filename": f"myfap-{VERSION}.tar.gz", "digests": {"sha256": "b" * 64}}
        info = {"name": "myfap", "version": VERSION}
        for payload in (
            None, [], {"info": info, "urls": "invalid"},
            {"info": {"name": "different", "version": VERSION}, "urls": [wheel, sdist]},
            {"info": info, "urls": [wheel, wheel, sdist]},
            {"info": info, "urls": [dict(wheel, yanked=True), sdist]},
            {"info": info, "urls": [dict(wheel, digests={"sha256": "invalid"}), sdist]},
        ):
            with self.subTest(payload=payload), patch.object(smoke_index, "fetch_index", return_value=payload) as fetch:
                with self.assertRaises(smoke_index.SmokeIndexError):
                    smoke_index.wait_for_release("https://pypi.invalid/pypi", VERSION, attempts=2, delay=0)
                self.assertEqual(fetch.call_count, 1)

    def test_retry_budget_rejects_more_than_six_attempts_before_network(self):
        with patch.object(smoke_index, "fetch_index") as fetch:
            with self.assertRaises(smoke_index.SmokeIndexError):
                smoke_index.wait_for_release("https://pypi.invalid/pypi", VERSION, attempts=7, delay=0)
        fetch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
