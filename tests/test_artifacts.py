from __future__ import annotations

import hashlib
import io
import subprocess
import sys
import tarfile
import unittest
import zipfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from scripts import check_artifacts, smoke_install
from scripts.check_artifacts import (
    ArtifactValidationError,
    build_manifest,
    validate_artifacts,
)


PROJECT = "myfap"
VERSION = "0.2.0"


def _project_files(root: Path, version: str = VERSION, lock_version: str | None = None):
    (root / "pyproject.toml").write_text(
        f"""[project]\nname = \"{PROJECT}\"\nversion = \"{version}\"\nreadme = \"README.md\"\nlicense = \"MIT\"\n\n[project.scripts]\nmyfap = \"myfap.cli:app\"\n""",
        encoding="utf-8",
    )
    (root / "uv.lock").write_text(
        f"[[package]]\nname = \"{PROJECT}\"\nversion = \"{lock_version or version}\"\n",
        encoding="utf-8",
    )


def _wheel(path: Path, version: str = VERSION, unsafe_name: str | None = None, replace: dict | None = None):
    dist_info = f"{PROJECT}-{version}.dist-info"
    metadata = (
        "Metadata-Version: 2.4\n"
        f"Name: {PROJECT}\n"
        f"Version: {version}\n"
        "Description-Content-Type: text/markdown\n"
        "License-File: LICENSE\n\n"
        "# MyFAP API CLI\n"
    ).encode()
    entries = {
        f"{PROJECT}/__init__.py": b"",
        f"{dist_info}/METADATA": metadata,
        f"{dist_info}/WHEEL": b"Wheel-Version: 1.0\nTag: py3-none-any\n",
        f"{dist_info}/entry_points.txt": b"[console_scripts]\nmyfap = myfap.cli:app\n",
        f"{dist_info}/top_level.txt": b"myfap\n",
        f"{dist_info}/RECORD": b"",
        f"{dist_info}/licenses/LICENSE": b"MIT\n",
    }
    if unsafe_name:
        entries[unsafe_name] = b"fixture"
    entries.update(replace or {})
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in entries.items():
            info = zipfile.ZipInfo()
            info.filename = name
            archive.writestr(info, content)


def _sdist(path: Path, version: str = VERSION, unsafe_name: str | None = None):
    root = f"{PROJECT}-{version}"
    entries = {
        f"{root}/PKG-INFO": (
            f"Metadata-Version: 2.4\nName: {PROJECT}\nVersion: {version}\n\n"
        ).encode(),
        f"{root}/README.md": b"# MyFAP API CLI\n",
        f"{root}/LICENSE": b"MIT\n",
        f"{root}/pyproject.toml": (
            f"[project]\nname = 'myfap'\nversion = '{version}'\n"
            "[project.scripts]\nmyfap = 'myfap.cli:app'\n"
        ).encode(),
        f"{root}/myfap.egg-info/entry_points.txt": b"[console_scripts]\nmyfap = myfap.cli:app\n",
    }
    if unsafe_name:
        entries[f"{root}/{unsafe_name}"] = b"fixture"
    with tarfile.open(path, "w:gz") as archive:
        for name, content in entries.items():
            info = tarfile.TarInfo(name)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))


class ArtifactGateTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.dist = self.root / "dist"
        self.dist.mkdir()

    def bundle(self, version=VERSION):
        _project_files(self.root, version=version)
        _wheel(self.dist / f"{PROJECT}-{version}-py3-none-any.whl", version=version)
        _sdist(self.dist / f"{PROJECT}-{version}.tar.gz", version=version)

    def test_valid_wheel_and_sdist_produce_manifest(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            dist = root / "dist"
            dist.mkdir()
            _project_files(root)
            _wheel(dist / f"{PROJECT}-{VERSION}-py3-none-any.whl")
            _sdist(dist / f"{PROJECT}-{VERSION}.tar.gz")

            report = validate_artifacts(root, dist, write_manifest=True)

            self.assertEqual(report.version, VERSION)
            self.assertEqual(report.artifacts, (f"{PROJECT}-{VERSION}-py3-none-any.whl", f"{PROJECT}-{VERSION}.tar.gz"))
            self.assertTrue((dist / "SHA256SUMS").is_file())
            self.assertEqual(report.manifest_sha256, hashlib.sha256((dist / "SHA256SUMS").read_bytes()).hexdigest())
            self.assertEqual(build_manifest(dist), (dist / "SHA256SUMS").read_text(encoding="utf-8"))

    def test_version_must_match_project_lock_and_artifacts(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            dist = root / "dist"
            dist.mkdir()
            _project_files(root, lock_version="0.1.8")
            _wheel(dist / f"{PROJECT}-{VERSION}-py3-none-any.whl")
            _sdist(dist / f"{PROJECT}-{VERSION}.tar.gz")

            with self.assertRaisesRegex(ArtifactValidationError, "uv.lock"):
                validate_artifacts(root, dist)

    def test_sensitive_capture_fixture_is_rejected_without_reading_body(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            dist = root / "dist"
            dist.mkdir()
            _project_files(root)
            _wheel(dist / f"{PROJECT}-{VERSION}-py3-none-any.whl", unsafe_name="fixtures/session.json")
            _sdist(dist / f"{PROJECT}-{VERSION}.tar.gz")

            with self.assertRaisesRegex(ArtifactValidationError, "nhạy cảm"):
                validate_artifacts(root, dist)

    def test_manifest_verification_detects_hash_mismatch(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            dist = root / "dist"
            dist.mkdir()
            _project_files(root)
            wheel = dist / f"{PROJECT}-{VERSION}-py3-none-any.whl"
            _wheel(wheel)
            _sdist(dist / f"{PROJECT}-{VERSION}.tar.gz")
            validate_artifacts(root, dist, write_manifest=True)
            wheel.write_bytes(wheel.read_bytes() + b"tampered")

            with self.assertRaisesRegex(ArtifactValidationError, "SHA256"):
                validate_artifacts(root, dist, verify_manifest=True)

    def test_expected_manifest_hash_and_version_are_checked(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            dist = root / "dist"
            dist.mkdir()
            _project_files(root)
            _wheel(dist / f"{PROJECT}-{VERSION}-py3-none-any.whl")
            _sdist(dist / f"{PROJECT}-{VERSION}.tar.gz")
            report = validate_artifacts(root, dist, write_manifest=True)

            validate_artifacts(
                root,
                dist,
                verify_manifest=True,
                expected_version=VERSION,
                expected_manifest_sha256=report.manifest_sha256,
            )
            with self.assertRaisesRegex(ArtifactValidationError, "expected version"):
                validate_artifacts(root, dist, expected_version="9.9.9")

            with self.assertRaisesRegex(ArtifactValidationError, "manifest"):
                validate_artifacts(root, dist, verify_manifest=True, expected_manifest_sha256="0" * 64)

    def test_metadata_name_version_and_entry_point_must_match(self):
        self.bundle()
        info = f"myfap-{VERSION}.dist-info"
        invalid_metadata = (
            b"Name: another-package\nVersion: 0.2.0\n\nREADME",
            b"Name: myfap\nVersion: 9.9.9\n\nREADME",
        )
        wheel = self.dist / f"myfap-{VERSION}-py3-none-any.whl"
        for content in invalid_metadata:
            with self.subTest(content=content):
                _wheel(wheel, replace={f"{info}/METADATA": content})
                with self.assertRaisesRegex(ArtifactValidationError, "Metadata"):
                    validate_artifacts(self.root, self.dist)
        _wheel(wheel, replace={f"{info}/entry_points.txt": b"[console_scripts]\nmyfap = another.cli:app\n"})
        with self.assertRaisesRegex(ArtifactValidationError, "Entry point"):
            validate_artifacts(self.root, self.dist)

    def test_sensitive_paths_are_rejected_in_both_archive_formats(self):
        self.bundle()
        for path in ("tests/fixtures/auth.har", "tests/fixtures/snapshot.saz", ".env", ".env.production", ".pypirc", "fixtures/credentials.json", "myfap/session.json", "fixtures/pii.csv"):
            for kind in ("wheel", "sdist"):
                with self.subTest(path=path, kind=kind):
                    self.bundle()
                    if kind == "wheel":
                        _wheel(self.dist / f"myfap-{VERSION}-py3-none-any.whl", unsafe_name=path)
                    else:
                        _sdist(self.dist / f"myfap-{VERSION}.tar.gz", unsafe_name=path)
                    with self.assertRaisesRegex(ArtifactValidationError, "nhạy cảm"):
                        validate_artifacts(self.root, self.dist)

    def test_repository_only_directories_are_rejected_in_both_formats(self):
        for name in ("docs/Example.md", "tasks/phase0.md", "myfap/docs/example.py", "myfap/tasks/plan.py"):
            for kind in ("wheel", "sdist"):
                with self.subTest(path=name, kind=kind):
                    self.bundle()
                    if kind == "wheel":
                        _wheel(self.dist / f"myfap-{VERSION}-py3-none-any.whl", unsafe_name=name)
                    else:
                        _sdist(self.dist / f"myfap-{VERSION}.tar.gz", unsafe_name=name)
                    with self.assertRaisesRegex(ArtifactValidationError, "repository-only"):
                        validate_artifacts(self.root, self.dist)

    def test_unsafe_paths_and_unexpected_files_are_rejected(self):
        self.bundle()
        for path in ("../escaped.py", "/absolute.py", "myfap\\escaped.py", "myfap/data.json"):
            with self.subTest(path=path):
                _wheel(self.dist / f"myfap-{VERSION}-py3-none-any.whl", unsafe_name=path)
                with self.assertRaises(ArtifactValidationError):
                    validate_artifacts(self.root, self.dist)

    def test_version_is_read_dynamically(self):
        self.bundle(version="1.2.3")
        self.assertEqual(validate_artifacts(self.root, self.dist).version, "1.2.3")

    def test_stale_artifact_is_rejected(self):
        self.bundle()
        (self.dist / "myfap-0.1.8.tar.gz").write_bytes(b"fixture")
        with self.assertRaisesRegex(ArtifactValidationError, "đúng một"):
            validate_artifacts(self.root, self.dist)

    def test_sdist_symlink_is_rejected(self):
        self.bundle()
        sdist = self.dist / f"myfap-{VERSION}.tar.gz"
        with tarfile.open(sdist, "w:gz") as archive:
            link = tarfile.TarInfo(f"myfap-{VERSION}/myfap/link.py")
            link.type = tarfile.SYMTYPE
            link.linkname = "../../outside.py"
            archive.addfile(link)
        with self.assertRaisesRegex(ArtifactValidationError, "link"):
            validate_artifacts(self.root, self.dist)

    def test_sdist_required_directory_is_rejected_as_missing_file(self):
        self.bundle()
        sdist = self.dist / f"myfap-{VERSION}.tar.gz"
        with tarfile.open(sdist, "w:gz") as archive:
            root = f"myfap-{VERSION}"
            for name in ("README.md", "LICENSE", "pyproject.toml"):
                content = b"content\n"
                member = tarfile.TarInfo(f"{root}/{name}")
                member.size = len(content)
                archive.addfile(member, io.BytesIO(content))
            directory = tarfile.TarInfo(f"{root}/PKG-INFO")
            directory.type = tarfile.DIRTYPE
            archive.addfile(directory)
            entry = tarfile.TarInfo(f"{root}/myfap.egg-info/entry_points.txt")
            content = b"[console_scripts]\nmyfap = myfap.cli:app\n"
            entry.size = len(content)
            archive.addfile(entry, io.BytesIO(content))
        with self.assertRaisesRegex(ArtifactValidationError, "thiếu file"):
            validate_artifacts(self.root, self.dist)

    def test_wheel_readme_and_license_are_required(self):
        self.bundle()
        info = f"myfap-{VERSION}.dist-info"
        wheel = self.dist / f"myfap-{VERSION}-py3-none-any.whl"
        for replacement in (
            {f"{info}/METADATA": f"Name: myfap\nVersion: {VERSION}\n\n".encode()},
            {f"{info}/licenses/LICENSE": b""},
        ):
            with self.subTest(replacement=list(replacement)):
                _wheel(wheel, replace=replacement)
                with self.assertRaisesRegex(ArtifactValidationError, "README|license"):
                    validate_artifacts(self.root, self.dist)

    def test_cli_outputs_only_machine_fields_and_sanitized_errors(self):
        self.bundle()
        stdout, stderr = io.StringIO(), io.StringIO()
        arguments = ["check_artifacts.py", "--project-dir", str(self.root), "--dist-dir", str(self.dist)]
        with patch("sys.argv", arguments), redirect_stdout(stdout), redirect_stderr(stderr):
            self.assertEqual(check_artifacts.main(), 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(len(stdout.getvalue().splitlines()), 2)
        self.assertTrue(stdout.getvalue().startswith(f"package_version={VERSION}\nmanifest_sha256="))

        _wheel(self.dist / f"myfap-{VERSION}-py3-none-any.whl", unsafe_name="fixtures/credentials.json")
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch("sys.argv", arguments), redirect_stdout(stdout), redirect_stderr(stderr):
            self.assertEqual(check_artifacts.main(), 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertNotIn("fixtures/credentials.json", stderr.getvalue())


class SmokeInstallTests(unittest.TestCase):
    def test_subprocess_preserves_vietnamese_output(self):
        result = smoke_install._run(
            [sys.executable, "-c", "print('Kiểm tra tiếng Việt')"], Path(".")
        )
        self.assertEqual(result.stdout.strip(), "Kiểm tra tiếng Việt")

    def test_each_artifact_gets_a_separate_venv_outside_checkout(self):
        with TemporaryDirectory() as temp:
            dist = Path(temp)
            wheel = dist / f"myfap-{VERSION}-py3-none-any.whl"
            sdist = dist / f"myfap-{VERSION}.tar.gz"
            wheel.write_bytes(b"fixture")
            sdist.write_bytes(b"fixture")
            commands = []

            def run(command, cwd):
                commands.append((command, cwd))
                output = f"MyFap API CLI version: {VERSION}\n" if command[-1] == "version" else ""
                return subprocess.CompletedProcess(command, 0, stdout=output, stderr="")

            with patch.object(smoke_install, "_run", side_effect=run):
                smoke_install.smoke_install(dist, "selected-python", VERSION)

            creates = [command for command, _ in commands if "venv" in command]
            self.assertEqual(len(creates), 2)
            self.assertEqual(creates[0][0], "selected-python")
            self.assertNotEqual(creates[0][-1], creates[1][-1])
            installs = [command for command, _ in commands if "install" in command]
            self.assertEqual([command[-1] for command in installs], [str(wheel.resolve()), str(sdist.resolve())])
            self.assertTrue(all("--no-cache-dir" in command and "--isolated" in command for command in installs))
            self.assertEqual(sum(command[-1] == "check" for command, _ in commands), 2)
            self.assertEqual(sum(command[-1] == "--help" for command, _ in commands), 2)
            for _, cwd in commands:
                self.assertNotIn(Path(__file__).resolve().parents[1], cwd.resolve().parents)
                self.assertFalse(cwd.exists())

    def test_wrong_installed_version_fails(self):
        with TemporaryDirectory() as temp:
            dist = Path(temp)
            for name in (f"myfap-{VERSION}-py3-none-any.whl", f"myfap-{VERSION}.tar.gz"):
                (dist / name).write_bytes(b"fixture")
            with patch.object(smoke_install, "_run", return_value=subprocess.CompletedProcess([], 0, stdout="wrong version", stderr="")):
                with self.assertRaisesRegex(smoke_install.SmokeInstallError, "version"):
                    smoke_install.smoke_install(dist, "python", VERSION)

    def test_subprocess_output_is_not_exposed_on_failure(self):
        error = subprocess.CalledProcessError(1, ["python"], output="private package body", stderr="private URL")
        with patch.object(smoke_install.subprocess, "run", side_effect=error):
            with self.assertRaises(smoke_install.SmokeInstallError) as result:
                smoke_install._run(["python"], Path("."))
        self.assertNotIn("private", str(result.exception))


if __name__ == "__main__":
    unittest.main()
