import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "release_tools.py"


class ReleaseToolsCliTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.env = dict(os.environ, PYTHONUTF8="1")

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, "-I", str(SCRIPT), *args], cwd=self.root,
            env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", timeout=30,
        )

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, env=self.env,
                                       stderr=subprocess.DEVNULL, text=True).strip()

    def prepare_git(self):
        self.git("init", "-q")
        self.git("config", "user.name", "Release fixture")
        self.git("config", "user.email", "release@example.invalid")
        (self.root / "pyproject.toml").write_text(
            '[project]\nname = "myfap"\nversion = "0.2.0"\n'
            '[project.scripts]\nmyfap = "myfap.cli:app"\n', encoding="utf-8",
        )
        (self.root / "uv.lock").write_text(
            'version = 1\n[[package]]\nname = "myfap"\nversion = "0.2.0"\n', encoding="utf-8",
        )
        self.git("add", ".")
        self.git("commit", "-qm", "fixture")
        commit = self.git("rev-parse", "HEAD")
        self.git("update-ref", "refs/remotes/origin/main", commit)
        self.git("tag", "-a", "v0.2.0", "-m", "fixture")
        return commit

    def test_validate_accepts_annotated_tag_at_merged_commit(self):
        commit = self.prepare_git()
        result = self.run_cli("validate", "--tag", "v0.2.0", "--commit", commit)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"tag": "v0.2.0", "version": "0.2.0", "sha": commit})

    def test_verify_accepts_exact_artifact_set_without_source_checkout(self):
        # Hashes are independent SHA-256 vectors for ASCII a and b.
        dist = self.root / "dist"
        dist.mkdir()
        (dist / "myfap-0.2.0-py3-none-any.whl").write_bytes(b"a")
        (dist / "myfap-0.2.0.tar.gz").write_bytes(b"b")
        manifest = (
            "ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb  myfap-0.2.0-py3-none-any.whl\n"
            "3e23e8160039594a33894f6564e1b1348bbd7a0088d42c4acb73eeaed59c009d  myfap-0.2.0.tar.gz\n"
        )
        (dist / "SHA256SUMS").write_bytes(manifest.encode("ascii"))
        import hashlib
        digest = hashlib.sha256(manifest.encode("ascii")).hexdigest()
        result = self.run_cli("verify", "--dist-dir", str(dist), "--expected-version", "0.2.0", "--manifest-sha256", digest)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["version"], "0.2.0")
        self.assertFalse((self.root / "pyproject.toml").exists())

    def prepare_artifacts(self):
        import hashlib
        dist = self.root / "dist"
        dist.mkdir()
        names = ["myfap-0.2.0-py3-none-any.whl", "myfap-0.2.0.tar.gz"]
        hashes = {}
        for name, content in zip(names, (b"a", b"b")):
            (dist / name).write_bytes(content)
            hashes[name] = hashlib.sha256(content).hexdigest()
        manifest = "".join(f"{hashes[name]}  {name}\n" for name in names).encode("ascii")
        (dist / "SHA256SUMS").write_bytes(manifest)
        return dist, hashlib.sha256(manifest).hexdigest(), hashes

    @contextmanager
    def index_server(self, status, payload):
        body = json.dumps(payload).encode("utf-8")

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(status if self.path == "/myfap/0.2.0/json" else 400)
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}"
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_pypi_state_reports_all_files_missing_for_http_404(self):
        dist, digest, hashes = self.prepare_artifacts()
        with self.index_server(404, {"detail": "Not Found"}) as url:
            result = self.run_cli("pypi-state", "--dist-dir", str(dist), "--version", "0.2.0",
                                  "--manifest-sha256", digest, "--index-url", url)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["state"], "missing")
        self.assertEqual(report["missing"], sorted(hashes))

    def test_pypi_state_distinguishes_partial_and_complete_matching_uploads(self):
        dist, digest, hashes = self.prepare_artifacts()
        names = sorted(hashes)
        for count, expected in ((1, "partial"), (2, "complete")):
            with self.subTest(state=expected):
                payload = {"info": {"name": "myfap", "version": "0.2.0"}, "urls": [
                    {"filename": name, "digests": {"sha256": hashes[name]}, "yanked": False}
                    for name in names[:count]
                ]}
                with self.index_server(200, payload) as url:
                    result = self.run_cli("pypi-state", "--dist-dir", str(dist), "--version", "0.2.0",
                                          "--manifest-sha256", digest, "--index-url", url)
                self.assertEqual(result.returncode, 0, result.stderr)
                report = json.loads(result.stdout)
                self.assertEqual(report["state"], expected)
                self.assertEqual(report["missing"], names[count:])

    def test_validate_rejects_invalid_stable_tags_before_git_access(self):
        for tag in ("0.2.0", "v01.2.0", "v0.02.0", "v0.2.00", "v0.2.0rc1", "v0.2.0+build", "v0.2.0\n", "v0.2"):
            with self.subTest(tag=tag):
                result = self.run_cli("validate", "--tag", tag, "--commit", "a" * 40)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, "")
                self.assertNotIn("Traceback", result.stderr)

    def test_validate_rejects_tag_metadata_and_lock_mismatches(self):
        commit = self.prepare_git()
        for filename, content in (
            ("uv.lock", '[[package]]\nname="myfap"\nversion="0.1.8"\n'),
            ("pyproject.toml", '[project]\nname="myfap"\nversion="0.3.0"\n'),
        ):
            path = self.root / filename
            original = path.read_bytes()
            with self.subTest(filename=filename):
                path.write_text(content, encoding="utf-8")
                result = self.run_cli("validate", "--tag", "v0.2.0", "--commit", commit)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, "")
            path.write_bytes(original)

    def test_validate_rejects_tag_not_on_main_and_checkout_not_matching_commit(self):
        commit = self.prepare_git()
        unrelated = self.git("commit-tree", "HEAD^{tree}", "-m", "unrelated")
        self.git("update-ref", "refs/remotes/origin/main", unrelated)
        result = self.run_cli("validate", "--tag", "v0.2.0", "--commit", commit)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.git("update-ref", "refs/remotes/origin/main", commit)
        result = self.run_cli("validate", "--tag", "v0.2.0", "--commit", unrelated)
        self.assertEqual(result.returncode, 1)

    def test_notes_rejects_missing_duplicate_and_empty_version_sections(self):
        for text in ("## [0.1.8]\nLịch sử.\n", "## [0.2.0]\n\n## [0.1.8]\nLịch sử.\n",
                     "## [0.2.0]\nMột.\n## [0.2.0] - Khác\nHai.\n"):
            with self.subTest(content=text):
                (self.root / "CHANGELOG.md").write_text(text, encoding="utf-8")
                result = self.run_cli("notes", "--version", "0.2.0", "--output", "notes.md")
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, "")
                self.assertFalse((self.root / "notes.md").exists())

    def test_verify_rejects_modified_artifact_manifest_and_extra_inventory(self):
        dist, digest, _ = self.prepare_artifacts()
        artifact = dist / "myfap-0.2.0-py3-none-any.whl"
        for name, content in ((artifact.name, b"tampered"), ("SHA256SUMS", b"changed"),
                              ("extra.whl", b"extra"), (".gitignore", b"extra")):
            path = dist / name
            original = path.read_bytes() if path.exists() else None
            with self.subTest(name=name):
                path.write_bytes(content)
                result = self.run_cli("verify", "--dist-dir", str(dist), "--expected-version", "0.2.0",
                                      "--manifest-sha256", digest)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, "")
            if original is None:
                path.unlink()
            else:
                path.write_bytes(original)
        (dist / "unexpected").mkdir()
        result = self.run_cli("verify", "--dist-dir", str(dist), "--expected-version", "0.2.0",
                              "--manifest-sha256", digest)
        self.assertEqual(result.returncode, 1)

    def test_pypi_state_fails_closed_for_mismatch_unexpected_duplicate_or_yanked_file(self):
        dist, digest, hashes = self.prepare_artifacts()
        name = sorted(hashes)[0]
        good = {"filename": name, "digests": {"sha256": hashes[name]}, "yanked": False}
        invalid_sets = (
            [{**good, "digests": {"sha256": "0" * 64}}],
            [{**good, "filename": "private-secret-data.whl"}],
            [good, good], [{**good, "yanked": True}],
            [{"filename": name, "digests": {"sha256": hashes[name]}}],
        )
        for files in invalid_sets:
            with self.subTest(files=files):
                payload = {"info": {"name": "myfap", "version": "0.2.0"}, "urls": files}
                with self.index_server(200, payload) as url:
                    result = self.run_cli("pypi-state", "--dist-dir", str(dist), "--version", "0.2.0",
                                          "--manifest-sha256", digest, "--index-url", url)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, "")
                self.assertNotIn("private-secret-data", result.stderr)

    def test_pypi_state_does_not_treat_server_errors_or_invalid_schema_as_missing(self):
        dist, digest, _ = self.prepare_artifacts()
        for status, payload in ((500, {}), (403, {}), (200, []), (200, {"urls": []}),
                                (200, {"info": {"name": "other", "version": "0.2.0"}, "urls": []}),
                                (200, {"info": {"name": "myfap", "version": "0.1.8"}, "urls": []})):
            with self.subTest(status=status, payload=payload):
                with self.index_server(status, payload) as url:
                    result = self.run_cli("pypi-state", "--dist-dir", str(dist), "--version", "0.2.0",
                                          "--manifest-sha256", digest, "--index-url", url)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, "")

    def test_notes_extracts_only_matching_version_without_heading(self):
        (self.root / "CHANGELOG.md").write_text(
            "# Changelog\n\n## [0.3.0]\nChưa phát hành.\n\n"
            "## [0.2.0] - Chưa phát hành\n\nV2 chỉ dùng khi chọn rõ.\n\n"
            "### Giới hạn\nGiữ lỗi live v1.\n\n## [0.1.8]\nLịch sử.\n", encoding="utf-8",
        )
        result = self.run_cli("notes", "--version", "0.2.0", "--output", "notes.md")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / "notes.md").read_text(encoding="utf-8"),
                         "V2 chỉ dùng khi chọn rõ.\n\n### Giới hạn\nGiữ lỗi live v1.\n")


if __name__ == "__main__":
    unittest.main()
