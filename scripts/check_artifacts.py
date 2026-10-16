"""Kiểm tra metadata, danh sách file và SHA-256 của artifact phát hành."""

from __future__ import annotations

import argparse
import configparser
import hashlib
import re
import stat
import sys
import tarfile
import zipfile
from dataclasses import dataclass
from email.parser import BytesParser
from pathlib import Path, PurePosixPath

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib


class ArtifactValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ArtifactReport:
    version: str
    artifacts: tuple[str, str]
    manifest_sha256: str


def _read_toml(path: Path) -> dict:
    try:
        with path.open("rb") as source:
            return tomllib.load(source)
    except (OSError, ValueError) as error:
        raise ArtifactValidationError("Không đọc được TOML hợp lệ.") from error


def _project_version(project_dir: Path) -> str:
    project = _read_toml(project_dir / "pyproject.toml").get("project", {})
    if not isinstance(project, dict):
        raise ArtifactValidationError("Project TOML không hợp lệ.")
    version = project.get("version", "")
    if project.get("name") != "myfap" or not isinstance(version, str) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        raise ArtifactValidationError("Tên hoặc version project không hợp lệ.")
    if project.get("scripts", {}).get("myfap") != "myfap.cli:app":
        raise ArtifactValidationError("Entry point project không khớp.")
    packages = _read_toml(project_dir / "uv.lock").get("package", [])
    own_packages = [package for package in packages if package.get("name") == "myfap"]
    if len(own_packages) != 1 or own_packages[0].get("version") != version:
        raise ArtifactValidationError("Version uv.lock không khớp project.")
    return version


def _safe_path(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if not name or any(ord(character) < 32 for character in name) or "\\" in name or ":" in name or path.is_absolute() or ".." in path.parts or path.as_posix() != name.rstrip("/"):
        raise ArtifactValidationError("Artifact chứa đường dẫn không an toàn.")
    parts = [part.lower() for part in path.parts]
    sensitive = re.compile(r"(^|[_.-])(session|sessions|credential|credentials|secret|secrets|token|tokens|cookies?|capture|captures|pii|password|authenkey)([_.-]|$)")
    if (
        any(part in {".env", ".pypirc", ".netrc", ".myfap-api-cli", ".git", "__pycache__", ".venv"} for part in parts)
        or any(part.startswith(".env.") for part in parts)
        or path.suffix.lower() in {".har", ".saz", ".pem", ".key", ".p12", ".pfx", ".pyc"}
        or any(sensitive.search(part) for part in parts)
    ):
        raise ArtifactValidationError("Artifact chứa đường dẫn dữ liệu nhạy cảm hoặc file cục bộ.")
    return path


def _repository_only_path(path: PurePosixPath) -> bool:
    parts = tuple(part.lower() for part in path.parts)
    return bool(parts and (parts[0] in {"docs", "tasks"} or (len(parts) > 1 and parts[0] == "myfap" and parts[1] in {"docs", "tasks"})))


def _metadata(content: bytes, version: str, *, readme: bool = False) -> None:
    message = BytesParser().parsebytes(content)
    if message.get_all("Name") != ["myfap"] or message.get_all("Version") != [version]:
        raise ArtifactValidationError("Metadata Name/Version không khớp.")
    description = message.get_payload()
    if readme and (
        message.get("Description-Content-Type") != "text/markdown"
        or not isinstance(description, str)
        or not description.strip()
        or "LICENSE" not in message.get_all("License-File", [])
    ):
        raise ArtifactValidationError("Wheel thiếu README hoặc license metadata.")


def _entry_point(content: bytes) -> None:
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read_string(content.decode("utf-8"))
        if parser.get("console_scripts", "myfap") != "myfap.cli:app":
            raise ValueError
    except (ValueError, configparser.Error) as error:
        raise ArtifactValidationError("Entry point artifact không khớp.") from error


def _wheel(path: Path, version: str) -> None:
    info_dir = f"myfap-{version}.dist-info"
    metadata_files = {"METADATA", "WHEEL", "entry_points.txt", "top_level.txt", "RECORD"}
    with zipfile.ZipFile(path) as archive:
        names = set()
        files = set()
        for member in archive.infolist():
            item = _safe_path(getattr(member, "orig_filename", member.filename))
            if _repository_only_path(item):
                raise ArtifactValidationError("Artifact chứa repository-only docs/tasks.")
            if member.filename in names or stat.S_ISLNK(member.external_attr >> 16):
                raise ArtifactValidationError("Wheel chứa file trùng hoặc symlink.")
            names.add(member.filename)
            if member.is_dir():
                continue
            files.add(member.filename)
            if not (
                len(item.parts) == 2 and item.parts[0] == "myfap" and item.suffix == ".py"
                or len(item.parts) == 2 and item.parts[0] == info_dir and item.name in metadata_files
                or item.parts == (info_dir, "licenses", "LICENSE")
            ):
                raise ArtifactValidationError("Wheel chứa file ngoài danh sách cho phép.")
        required = {
            "myfap/__init__.py",
            f"{info_dir}/METADATA",
            f"{info_dir}/WHEEL",
            f"{info_dir}/entry_points.txt",
            f"{info_dir}/top_level.txt",
            f"{info_dir}/RECORD",
            f"{info_dir}/licenses/LICENSE",
        }
        if not required <= files:
            raise ArtifactValidationError("Wheel thiếu file bắt buộc.")
        _metadata(archive.read(f"{info_dir}/METADATA"), version, readme=True)
        _entry_point(archive.read(f"{info_dir}/entry_points.txt"))
        if not archive.read(f"{info_dir}/licenses/LICENSE").strip():
            raise ArtifactValidationError("Wheel có license rỗng.")


def _sdist(path: Path, version: str) -> None:
    prefix = f"myfap-{version}"
    top_files = {"LICENSE", "README.md", "PKG-INFO", "pyproject.toml", "setup.cfg", "MANIFEST.in"}
    egg_files = {"PKG-INFO", "SOURCES.txt", "dependency_links.txt", "entry_points.txt", "requires.txt", "top_level.txt"}
    with tarfile.open(path, "r:gz") as archive:
        names = set()
        files = set()
        for member in archive.getmembers():
            item = _safe_path(member.name)
            if member.name in names or not (member.isdir() or member.isfile()):
                raise ArtifactValidationError("Sdist chứa file trùng hoặc link không an toàn.")
            names.add(member.name)
            if not item.parts or item.parts[0] != prefix:
                raise ArtifactValidationError("Sdist chứa thư mục gốc không khớp.")
            if _repository_only_path(PurePosixPath(*item.parts[1:])):
                raise ArtifactValidationError("Artifact chứa repository-only docs/tasks.")
            if member.isdir():
                continue
            files.add(member.name)
            parts = item.parts[1:]
            if not (
                len(parts) == 1 and parts[0] in top_files
                or len(parts) >= 2 and parts[0] == "myfap" and item.suffix == ".py"
                or len(parts) == 2 and parts[0] == "myfap.egg-info" and parts[1] in egg_files
                or len(parts) == 2 and parts[0] == "tests" and parts[1].startswith("test_") and item.suffix == ".py"
            ):
                raise ArtifactValidationError("Sdist chứa file ngoài danh sách cho phép.")
        required = {f"{prefix}/{name}" for name in ("PKG-INFO", "README.md", "LICENSE", "pyproject.toml")}
        required.add(f"{prefix}/myfap.egg-info/entry_points.txt")
        if not required <= files:
            raise ArtifactValidationError("Sdist thiếu file bắt buộc.")
        _metadata(archive.extractfile(f"{prefix}/PKG-INFO").read(), version)
        if f"{prefix}/myfap.egg-info/PKG-INFO" in names:
            _metadata(archive.extractfile(f"{prefix}/myfap.egg-info/PKG-INFO").read(), version)
        _entry_point(archive.extractfile(f"{prefix}/myfap.egg-info/entry_points.txt").read())
        try:
            project = tomllib.loads(archive.extractfile(f"{prefix}/pyproject.toml").read().decode("utf-8"))["project"]
        except (ValueError, KeyError) as error:
            raise ArtifactValidationError("Sdist có pyproject không hợp lệ.") from error
        if not isinstance(project, dict) or project.get("name") != "myfap" or project.get("version") != version or project.get("scripts", {}).get("myfap") != "myfap.cli:app":
            raise ArtifactValidationError("Sdist có pyproject không khớp project.")
        for name in ("README.md", "LICENSE"):
            if not archive.extractfile(f"{prefix}/{name}").read().strip():
                raise ArtifactValidationError("Sdist có README hoặc license rỗng.")


def build_manifest(dist_dir: Path) -> str:
    artifacts = sorted(path for path in dist_dir.iterdir() if path.name.endswith((".whl", ".tar.gz")))
    return "".join(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n" for path in artifacts)


def validate_artifacts(
    project_dir: Path,
    dist_dir: Path,
    *,
    write_manifest: bool = False,
    verify_manifest: bool = False,
    expected_version: str | None = None,
    expected_manifest_sha256: str | None = None,
) -> ArtifactReport:
    if write_manifest and verify_manifest:
        raise ArtifactValidationError("Chọn tạo hoặc xác minh manifest.")
    version = _project_version(project_dir)
    if expected_version is not None and version != expected_version:
        raise ArtifactValidationError("Project không khớp expected version.")
    expected = (f"myfap-{version}-py3-none-any.whl", f"myfap-{version}.tar.gz")
    paths = list(dist_dir.iterdir())
    if any(path.is_symlink() or not path.is_file() for path in paths):
        raise ArtifactValidationError("Thư mục artifact chứa link hoặc thư mục ngoài dự kiến.")
    if {path.name for path in paths} - {"SHA256SUMS", ".gitignore"} != set(expected):
        raise ArtifactValidationError("Cần đúng một wheel và một sdist của project version hiện tại.")
    manifest = build_manifest(dist_dir)
    manifest_path = dist_dir / "SHA256SUMS"
    if verify_manifest:
        if not manifest_path.is_file() or manifest_path.read_bytes() != manifest.encode("utf-8"):
            raise ArtifactValidationError("SHA256 artifact không khớp manifest.")
    manifest_sha256 = hashlib.sha256(manifest.encode("utf-8")).hexdigest()
    if expected_manifest_sha256 is not None and manifest_sha256 != expected_manifest_sha256:
        raise ArtifactValidationError("SHA256 manifest không khớp build output.")
    _wheel(dist_dir / expected[0], version)
    _sdist(dist_dir / expected[1], version)
    if write_manifest:
        manifest_path.write_bytes(manifest.encode("utf-8"))
    return ArtifactReport(version, expected, manifest_sha256)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", type=Path, default=Path("."))
    parser.add_argument("--dist-dir", type=Path, default=Path("dist"))
    parser.add_argument("--verify-manifest", action="store_true")
    parser.add_argument("--manifest-sha256")
    parser.add_argument("--expected-version")
    args = parser.parse_args()
    try:
        report = validate_artifacts(
            args.project_dir,
            args.dist_dir,
            write_manifest=not args.verify_manifest,
            verify_manifest=args.verify_manifest,
            expected_version=args.expected_version,
            expected_manifest_sha256=args.manifest_sha256,
        )
    except (ArtifactValidationError, OSError, tarfile.TarError, zipfile.BadZipFile, UnicodeError) as error:
        message = str(error) if isinstance(error, ArtifactValidationError) else "Không đọc được artifact hợp lệ."
        print(message, file=sys.stderr)
        return 1
    print(f"package_version={report.version}")
    print(f"manifest_sha256={report.manifest_sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
