"""Cài thử version phát hành từ PyPI hoặc TestPyPI trong venv ngoài checkout."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
import os
import re
import time
import math
import urllib.error
import urllib.request
from dataclasses import dataclass


class SmokeIndexError(RuntimeError):
    pass


class IndexNotReady(SmokeIndexError):
    pass


@dataclass(frozen=True)
class IndexReport:
    state: str
    files: tuple[str, ...]
    metadata: dict


def pip_environment(source: dict | None = None) -> dict:
    environment = {
        key: value for key, value in (os.environ if source is None else source).items()
        if not key.upper().startswith("PIP_")
        and key.upper() not in {"PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"}
    }
    # os.devnull also suppresses global/site config, unlike --isolated alone.
    environment["PIP_CONFIG_FILE"] = os.devnull
    environment["PYTHONUTF8"] = "1"
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["NO_COLOR"] = "1"
    return environment


def fetch_index(base_url: str, version: str) -> dict:
    try:
        with urllib.request.urlopen(f"{base_url}/myfap/{version}/json", timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            raise IndexNotReady("Version chưa có trên index.") from None
        raise SmokeIndexError("Không đọc được release index.") from None
    except (OSError, ValueError):
        raise SmokeIndexError("Không đọc được release index.") from None


def wait_for_release(base_url: str, version: str, *, attempts: int = 6, delay: float = 10) -> IndexReport:
    if not re.fullmatch(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)", version):
        raise SmokeIndexError("Expected version không hợp lệ.")
    if not 1 <= attempts <= 6 or delay < 0 or not math.isfinite(delay):
        raise SmokeIndexError("Số lần thử hoặc delay không hợp lệ.")
    for attempt in range(attempts):
        try:
            payload = fetch_index(base_url, version)
        except IndexNotReady:
            if attempt + 1 == attempts:
                return IndexReport("missing", (), {})
            if delay:
                time.sleep(delay)
            continue
        expected = (f"myfap-{version}-py3-none-any.whl", f"myfap-{version}.tar.gz")
        if not isinstance(payload, dict) or not isinstance(payload.get("info"), dict) or not isinstance(payload.get("urls"), list):
            raise SmokeIndexError("Release index có cấu trúc không hợp lệ.")
        if payload["info"].get("name") != "myfap" or payload["info"].get("version") != version:
            raise SmokeIndexError("Release index không khớp name/version.")
        files = {}
        for item in payload["urls"]:
            if not isinstance(item, dict) or not isinstance(item.get("filename"), str):
                raise SmokeIndexError("Release index chứa file không hợp lệ.")
            name = item["filename"]
            digests = item.get("digests")
            if name not in expected or name in files or item.get("yanked", False) is not False:
                raise SmokeIndexError("Release index chứa file thừa, trùng hoặc bị yank.")
            if not isinstance(digests, dict) or not isinstance(digests.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", digests["sha256"]):
                raise SmokeIndexError("Release index thiếu SHA-256 hợp lệ.")
            files[name] = item
        if set(files) != set(expected):
            if attempt + 1 == attempts:
                return IndexReport("missing", (), {})
            if delay:
                time.sleep(delay)
            continue
        return IndexReport("available", expected, files)
    raise SmokeIndexError("Không xác định được trạng thái release index.")


def verify_index_files(artifact_dir: Path, files: dict, version: str, manifest_sha256: str) -> None:
    helper = Path(__file__).resolve().with_name("release_tools.py")
    with tempfile.TemporaryDirectory(prefix="myfap-index-verify-") as temporary:
        report = run_process([
            sys.executable, "-I", str(helper), "verify", "--dist-dir", str(artifact_dir.resolve()),
            "--expected-version", version, "--manifest-sha256", manifest_sha256,
        ], Path(temporary))
    try:
        hashes = json.loads(report.stdout)["artifacts"]
        if set(files) != set(hashes) or any(files[name].get("digests", {}).get("sha256") != digest for name, digest in hashes.items()):
            raise SmokeIndexError("Hash artifact local và index không khớp.")
    except (ValueError, KeyError, TypeError, AttributeError):
        raise SmokeIndexError("Metadata hash artifact không hợp lệ.") from None


def run_process(command: list[str], cwd: Path) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            command, cwd=str(cwd), env=pip_environment(), check=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", timeout=600,
        )
    except (OSError, subprocess.SubprocessError):
        # pip can print private URLs and local paths; never expose its output.
        raise SmokeIndexError("Tiến trình smoke index thất bại.") from None


def smoke_index(version: str, *, python_executable: str = sys.executable, attempts: int = 6, delay: float = 10, artifact_dir: Path | None = None, manifest_sha256: str | None = None, test_pypi: bool = False) -> None:
    index = "https://test.pypi.org/pypi" if test_pypi else "https://pypi.org/pypi"
    report = wait_for_release(index, version, attempts=attempts, delay=delay)
    if report.state != "available":
        raise SmokeIndexError("Version chưa có đủ trên index sau số lần chờ cho phép.")
    with tempfile.TemporaryDirectory(prefix="myfap-index-smoke-") as temporary:
        root = Path(temporary)
        env_dir = root / "venv"
        run_process([python_executable, "-I", "-m", "venv", str(env_dir)], root)
        python = env_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        pip = [str(python), "-I", "-m", "pip", "--isolated", "--disable-pip-version-check"]
        if artifact_dir is not None:
            if not manifest_sha256:
                raise SmokeIndexError("--manifest-sha256 bắt buộc khi có --artifact-dir.")
            verify_index_files(artifact_dir, report.metadata, version, manifest_sha256)
        if test_pypi:
            destination = root / "download"
            destination.mkdir()
            run_process(pip + [
                "download", "--no-cache-dir", "--no-deps", "--only-binary=:all:",
                "--index-url", "https://test.pypi.org/simple/", "--dest", str(destination), f"myfap=={version}",
            ], root)
            wheel_path = destination / report.files[0]
            if {path.name for path in destination.iterdir()} != {wheel_path.name} or not wheel_path.is_file() or wheel_path.is_symlink():
                raise SmokeIndexError("TestPyPI không tải đúng một wheel của release.")
            if hashlib.sha256(wheel_path.read_bytes()).hexdigest() != report.metadata[wheel_path.name].get("digests", {}).get("sha256"):
                raise SmokeIndexError("Hash wheel TestPyPI không khớp release index.")
            run_process(pip + ["install", "--no-cache-dir", "--index-url", "https://pypi.org/simple/", str(wheel_path)], root)
        else:
            run_process(pip + ["install", "--no-cache-dir", "--index-url", "https://pypi.org/simple/", f"myfap=={version}"], root)
        run_process(pip + ["check"], root)
        installed = run_process([str(python), "-I", "-c", "from importlib.metadata import version; print(version('myfap'))"], root)
        if installed.stdout.strip() != version:
            raise SmokeIndexError("Metadata version đã cài không khớp release.")
        cli = env_dir / ("Scripts/myfap.exe" if os.name == "nt" else "bin/myfap")
        output = run_process([str(cli), "version"], root)
        if output.stdout.strip() != f"MyFap API CLI version: {version}":
            raise SmokeIndexError("CLI version đã cài không khớp release.")
        run_process([str(cli), "--help"], root)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--python-executable", default=sys.executable)
    parser.add_argument("--attempts", type=int, default=6)
    parser.add_argument("--delay", type=float, default=10)
    parser.add_argument("--artifact-dir", type=Path)
    parser.add_argument("--manifest-sha256")
    parser.add_argument("--test-pypi", action="store_true")
    args = parser.parse_args()
    if args.artifact_dir is not None and not args.manifest_sha256:
        parser.error("--manifest-sha256 bắt buộc khi có --artifact-dir")
    try:
        smoke_index(args.expected_version, python_executable=args.python_executable, attempts=args.attempts, delay=args.delay, artifact_dir=args.artifact_dir, manifest_sha256=args.manifest_sha256, test_pypi=args.test_pypi)
    except (SmokeIndexError, OSError):
        print("Smoke index không đạt; không tiếp tục tạo Release.", file=sys.stderr)
        return 1
    print(f"smoke_index=ok version={args.expected_version} index={'testpypi' if args.test_pypi else 'pypi'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
