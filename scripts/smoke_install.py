"""Cài thử wheel và sdist trong các virtualenv sạch, tách khỏi checkout."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


class SmokeInstallError(RuntimeError):
    pass


def discover_artifacts(artifact_dir: Path, version: str) -> tuple[Path, Path]:
    expected = (
        artifact_dir / f"myfap-{version}-py3-none-any.whl",
        artifact_dir / f"myfap-{version}.tar.gz",
    )
    if any(not path.is_file() or path.is_symlink() for path in expected):
        raise SmokeInstallError("Thiếu artifact wheel hoặc sdist đúng version.")
    allowed = {path.name for path in expected}
    actual = {path.name for path in artifact_dir.iterdir() if path.suffix == ".whl" or path.name.endswith(".tar.gz")}
    if actual != allowed:
        raise SmokeInstallError("Thư mục artifact có file ngoài wheel/sdist cần smoke test.")
    return expected


def _venv_python(root: Path) -> Path:
    return root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONUTF8"] = "1"
    environment["PYTHONIOENCODING"] = "utf-8"
    for variable in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
        environment.pop(variable, None)
    try:
        return subprocess.run(
            command,
            cwd=str(cwd),
            check=True,
            text=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment,
            timeout=600,
        )
    except (OSError, subprocess.SubprocessError) as error:
        # Không in stdout/stderr vì pip có thể hiển thị dữ liệu package hoặc URL nội bộ.
        step = next((name for name in ("venv", "install", "check", "version", "--help") if name in command), "process")
        raise SmokeInstallError(f"Smoke install thất bại ở bước {step}.") from error


def smoke_install(artifact_dir: Path, python_executable: str, expected_version: str) -> None:
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", expected_version):
        raise SmokeInstallError("Expected version không hợp lệ.")
    wheel, sdist = discover_artifacts(artifact_dir, expected_version)
    with tempfile.TemporaryDirectory(prefix="myfap-smoke-") as temporary:
        root = Path(temporary)
        for index, artifact in enumerate((wheel, sdist), 1):
            env_dir = root / f"venv-{index}"
            _run([python_executable, "-I", "-m", "venv", str(env_dir)], root)
            python = _venv_python(env_dir)
            pip = [str(python), "-I", "-m", "pip", "--isolated", "--disable-pip-version-check"]
            _run(
                pip + [
                    "install",
                    "--no-cache-dir",
                    "--index-url", "https://pypi.org/simple/",
                    str(artifact.resolve()),
                ],
                root,
            )
            _run(pip + ["check"], root)
            cli = env_dir / ("Scripts/myfap.exe" if os.name == "nt" else "bin/myfap")
            version = _run([str(cli), "version"], root)
            expected_output = f"MyFap API CLI version: {expected_version}"
            if version.stdout.strip() != expected_output:
                raise SmokeInstallError("CLI version không khớp artifact đã cài.")
            _run([str(cli), "--help"], root)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", type=Path, default=Path("dist"))
    parser.add_argument("--python-executable", default=sys.executable)
    parser.add_argument("--expected-version", required=True)
    args = parser.parse_args()
    try:
        smoke_install(args.artifact_dir, args.python_executable, args.expected_version)
    except (SmokeInstallError, OSError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(f"smoke_install=ok version={args.expected_version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
