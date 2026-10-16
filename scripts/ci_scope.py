"""Chọn các CI gate theo path thay đổi mà không đọc docs/ hoặc tasks/."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Mapping, Sequence


SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
REPOSITORY_ONLY = ("docs/", "tasks/")
HEAVY_JOBS = ("source", "build", "smoke")


def paths_require_checks(paths: Sequence[str]) -> bool:
    """Return whether any changed path is outside repository-only directories."""
    return any(
        path and not path.startswith(REPOSITORY_ONLY)
        for path in paths
    )


def _sha(value: object, name: str) -> str:
    if not isinstance(value, str) or not SHA_RE.fullmatch(value):
        raise ValueError(f"{name} không phải SHA hợp lệ.")
    return value


def _git(*args: str, cwd: Path) -> bytes:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise ValueError("Không lấy được danh sách path thay đổi.") from error
    return result.stdout


def _changed_paths(base: str, head: str, cwd: Path) -> list[str]:
    output = _git(
        "diff",
        "--name-only",
        "--no-renames",
        "--no-ext-diff",
        "--no-textconv",
        "-z",
        base,
        head,
        cwd=cwd,
    )
    return [item.decode("utf-8", "surrogateescape") for item in output.split(b"\0") if item]


def code_changed(
    event_name: str,
    event: Mapping[str, object],
    inputs: Mapping[str, object],
    *,
    cwd: Path = Path("."),
) -> bool:
    """Resolve whether source/build/smoke must run for one GitHub event."""
    # A called workflow must always validate the supplied release ref. GitHub's
    # event name remains the caller's event, so the input key is the signal.
    if "ref" in inputs:
        return True

    if event_name == "push":
        before = event.get("before")
        after = _sha(event.get("after"), "after")
        if before == "0" * 40:
            return True
        return paths_require_checks(_changed_paths(_sha(before, "before"), after, cwd))

    if event_name == "pull_request":
        pull_request = event.get("pull_request")
        if not isinstance(pull_request, Mapping):
            raise ValueError("Payload pull_request không hợp lệ.")
        base = pull_request.get("base")
        head = pull_request.get("head")
        if not isinstance(base, Mapping) or not isinstance(head, Mapping):
            raise ValueError("Payload base/head không hợp lệ.")
        base_sha = _sha(base.get("sha"), "base.sha")
        head_sha = _sha(head.get("sha"), "head.sha")
        merge_base = _sha(_git("merge-base", base_sha, head_sha, cwd=cwd).decode().strip(), "merge-base")
        return paths_require_checks(_changed_paths(merge_base, head_sha, cwd))

    # workflow_dispatch and unknown/manual events are conservative: validate code.
    return True


def ready_succeeded(code_changed_value: str, scope_result: str, heavy_results: Sequence[str]) -> bool:
    if scope_result != "success" or code_changed_value not in {"true", "false"}:
        return False
    if code_changed_value == "false":
        return list(heavy_results) == ["skipped"] * len(HEAVY_JOBS)
    return list(heavy_results) == ["success"] * len(HEAVY_JOBS)


def _load_json(path: str, default: object) -> object:
    if not path:
        return default
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ValueError("GitHub event JSON không hợp lệ.") from error


def _scope_main() -> int:
    event_name = os.environ.get("GITHUB_EVENT_NAME", "")
    event = _load_json(os.environ.get("GITHUB_EVENT_PATH", ""), {})
    inputs = json.loads(os.environ.get("WORKFLOW_INPUTS") or "{}")
    if inputs is None:
        inputs = {}
    if not isinstance(event, Mapping) or not isinstance(inputs, Mapping):
        raise ValueError("Payload CI không hợp lệ.")
    print(f"code_changed={str(code_changed(event_name, event, inputs)).lower()}")
    return 0


def _ready_main() -> int:
    heavy = [os.environ.get(f"{name.upper()}_RESULT", "") for name in HEAVY_JOBS]
    ok = ready_succeeded(os.environ.get("CODE_CHANGED", ""), os.environ.get("SCOPE_RESULT", ""), heavy)
    if ok:
        print("ready=true")
        return 0
    print("ready=false", file=sys.stderr)
    return 1


def main(argv: Sequence[str] | None = None) -> int:
    command = list(argv if argv is not None else sys.argv[1:])
    if command == ["scope"]:
        return _scope_main()
    if command == ["ready"]:
        return _ready_main()
    print("Dùng: ci_scope.py scope|ready", file=sys.stderr)
    return 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, KeyError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
