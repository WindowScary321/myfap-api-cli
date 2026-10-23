"""Kiểm tra đầu vào và tính toàn vẹn của release; không publish artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path


class ReleaseValidationError(ValueError):
    pass


def stable_version(version: str) -> str:
    if not re.fullmatch(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)", version):
        raise ReleaseValidationError("Version phải có dạng stable X.Y.Z, không có số 0 đứng đầu.")
    return version


def verify_artifacts(dist_dir: Path, version: str, manifest_sha256: str) -> dict:
    stable_version(version)
    if not re.fullmatch(r"[0-9a-f]{64}", manifest_sha256):
        raise ReleaseValidationError("SHA-256 manifest không hợp lệ.")
    names = [f"myfap-{version}-py3-none-any.whl", f"myfap-{version}.tar.gz"]
    paths = list(dist_dir.iterdir())
    if dist_dir.is_symlink() or any(path.is_symlink() or not path.is_file() for path in paths):
        raise ReleaseValidationError("Artifact không được chứa symlink hoặc thư mục.")
    if {path.name for path in paths} != set(names + ["SHA256SUMS"]):
        raise ReleaseValidationError("Cần đúng wheel, sdist và SHA256SUMS của version đã chọn.")
    manifest = (dist_dir / "SHA256SUMS").read_bytes()
    if hashlib.sha256(manifest).hexdigest() != manifest_sha256:
        raise ReleaseValidationError("SHA-256 manifest không khớp output CI.")
    hashes = {name: hashlib.sha256((dist_dir / name).read_bytes()).hexdigest() for name in names}
    expected = "".join(f"{hashes[name]}  {name}\n" for name in sorted(names)).encode("ascii")
    if manifest != expected:
        raise ReleaseValidationError("SHA-256 artifact hoặc định dạng manifest không khớp.")
    return {"version": version, "manifest_sha256": manifest_sha256, "artifacts": hashes}


def validate_release(tag: str, commit: str, main_ref: str) -> dict:
    if not tag.startswith("v"):
        raise ReleaseValidationError("Tag release phải bắt đầu bằng v.")
    version = stable_version(tag[1:])
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", commit):
        raise ReleaseValidationError("Commit phải là SHA đầy đủ đã resolve.")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_./-]*", main_ref):
        raise ReleaseValidationError("Main ref không hợp lệ.")

    def git(*args):
        result = subprocess.run(["git", *args], stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, text=True, timeout=30)
        if result.returncode != 0:
            raise ReleaseValidationError("Không xác minh được tag hoặc lịch sử Git.")
        return result.stdout.strip()

    sha = git("rev-parse", "--verify", "--end-of-options", f"{commit}^{{commit}}")
    tag_sha = git("rev-parse", "--verify", "--end-of-options", f"refs/tags/{tag}^{{commit}}")
    main_sha = git("rev-parse", "--verify", "--end-of-options", f"{main_ref}^{{commit}}")
    if sha != tag_sha or git("rev-parse", "HEAD") != sha:
        raise ReleaseValidationError("Tag, commit và checkout không cùng một SHA.")
    git("merge-base", "--is-ancestor", sha, main_sha)

    try:
        import tomllib
    except ModuleNotFoundError:
        import tomli as tomllib
    with Path("pyproject.toml").open("rb") as source:
        project = tomllib.load(source).get("project", {})
    with Path("uv.lock").open("rb") as source:
        packages = tomllib.load(source).get("package", [])
    if not isinstance(project, dict) or project.get("name") != "myfap" or project.get("version") != version:
        raise ReleaseValidationError("Tag không khớp name/version trong pyproject.toml.")
    if not isinstance(project.get("scripts"), dict) or project["scripts"].get("myfap") != "myfap.cli:app":
        raise ReleaseValidationError("Entry point project không khớp.")
    if not isinstance(packages, list) or any(not isinstance(package, dict) for package in packages):
        raise ReleaseValidationError("Metadata package trong lockfile không hợp lệ.")
    own = [package for package in packages if package.get("name") == "myfap"]
    if len(own) != 1 or own[0].get("version") != version:
        raise ReleaseValidationError("Version uv.lock không khớp tag và project.")
    return {"tag": tag, "version": version, "sha": sha}


def release_notes(version: str, output: Path) -> dict:
    stable_version(version)
    content = Path("CHANGELOG.md").read_text(encoding="utf-8")
    headings = list(re.finditer(r"^##[ \t]+(.+)$", content, re.MULTILINE))
    matches = [index for index, heading in enumerate(headings)
               if re.match(r"\[" + re.escape(version) + r"\](?:[ \t]|$)", heading.group(1))]
    if len(matches) != 1:
        raise ReleaseValidationError("CHANGELOG phải có đúng một mục version cần phát hành.")
    index = matches[0]
    end = headings[index + 1].start() if index + 1 < len(headings) else len(content)
    notes = content[headings[index].end():end].strip()
    if not notes:
        raise ReleaseValidationError("Mục changelog của version không được rỗng.")
    output.write_bytes((notes + "\n").encode("utf-8"))
    return {"version": version, "output": str(output)}


def pypi_state(dist_dir: Path, version: str, manifest_sha256: str, index_url: str) -> dict:
    report = verify_artifacts(dist_dir, version, manifest_sha256)
    url = f"{index_url.rstrip('/')}/myfap/{version}/json"
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            content = response.read(1024 * 1024 + 1)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return {**report, "state": "missing", "missing": sorted(report["artifacts"])}
        raise ReleaseValidationError("Index trả lỗi HTTP; không được suy ra version chưa tồn tại.") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise ReleaseValidationError("Không đọc được index; dừng trước upload.") from None
    if len(content) > 1024 * 1024:
        raise ReleaseValidationError("Response index vượt giới hạn cho phép.")
    try:
        payload = json.loads(content)
    except (ValueError, UnicodeError):
        raise ReleaseValidationError("Index không trả JSON hợp lệ.") from None
    if not isinstance(payload, dict) or not isinstance(payload.get("info"), dict):
        raise ReleaseValidationError("Index thiếu metadata version.")
    info = payload["info"]
    if info.get("name") != "myfap" or info.get("version") != version:
        raise ReleaseValidationError("Metadata index không khớp name/version cần phát hành.")
    files = payload.get("urls")
    if not isinstance(files, list):
        raise ReleaseValidationError("Index thiếu danh sách file.")
    found = set()
    for item in files:
        if not isinstance(item, dict):
            raise ReleaseValidationError("Metadata file trên index không hợp lệ.")
        name = item.get("filename")
        digests = item.get("digests")
        if not isinstance(name, str) or name not in report["artifacts"] or name in found:
            raise ReleaseValidationError("Index có file ngoài dự kiến hoặc tên trùng.")
        if not isinstance(digests, dict) or digests.get("sha256") != report["artifacts"][name]:
            raise ReleaseValidationError("Hash trên index khác artifact đã kiểm thử; dừng upload.")
        if item.get("yanked") is not False:
            raise ReleaseValidationError("File đã yank hoặc thiếu trạng thái yank; cần maintainer kiểm tra.")
        found.add(name)
    missing = sorted(set(report["artifacts"]) - found)
    state = "complete" if not missing else ("partial" if found else "missing")
    return {**report, "state": state, "missing": missing}


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("--dist-dir", type=Path, required=True)
    verify.add_argument("--expected-version", required=True)
    verify.add_argument("--manifest-sha256", required=True)
    notes = commands.add_parser("notes")
    notes.add_argument("--version", required=True)
    notes.add_argument("--output", type=Path, required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("--tag", required=True)
    validate.add_argument("--commit", required=True)
    validate.add_argument("--main-ref", default="origin/main")
    state = commands.add_parser("pypi-state")
    state.add_argument("--dist-dir", type=Path, required=True)
    state.add_argument("--version", required=True)
    state.add_argument("--manifest-sha256", required=True)
    state.add_argument("--index-url", default="https://pypi.org/pypi")
    args = parser.parse_args(argv)
    try:
        if args.command == "verify":
            report = verify_artifacts(args.dist_dir, args.expected_version, args.manifest_sha256)
        elif args.command == "notes":
            report = release_notes(args.version, args.output)
        elif args.command == "validate":
            report = validate_release(args.tag, args.commit, args.main_ref)
        else:
            report = pypi_state(args.dist_dir, args.version, args.manifest_sha256, args.index_url)
    except (ReleaseValidationError, OSError, ValueError, subprocess.TimeoutExpired) as error:
        message = str(error) if isinstance(error, ReleaseValidationError) else "Không đọc được đầu vào release hợp lệ."
        print(message, file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
