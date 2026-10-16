import json
import multiprocessing
import os
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from myfap.storage import SessionFormatError, SessionStore, SessionStoreError
from myfap import storage as storage_module


def _hold_lock(path, acquired, release):
    with SessionStore(path).lock():
        acquired.set()
        release.wait(15)


def _update_counter(path, started):
    store = SessionStore(path)
    started.set()
    with store.lock():
        data = store.read()
        store.write({"counter": data["counter"] + 1})


def _paused_waiter(path, opened, proceed, blocked, acquired):
    original_open, original_lock = storage_module._open, SessionStore._try_lock
    first_open = True

    def pause_open(*args, **kwargs):
        nonlocal first_open
        fd = original_open(*args, **kwargs)
        if first_open:
            first_open = False
            opened.set()
            if not proceed.wait(15):
                os.close(fd)
                raise RuntimeError("fake-waiter-timeout")
        return fd

    def observe_lock(fd):
        try:
            original_lock(fd)
        except OSError:
            blocked.set()
            raise

    with patch.object(storage_module, "_open", side_effect=pause_open), patch.object(SessionStore, "_try_lock", side_effect=observe_lock):
        with SessionStore(path).lock():
            acquired.set()


class SessionStoreTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "config" / "session.json"
        self.store = SessionStore(self.path)

    def test_missing_file_returns_none(self):
        self.assertIsNone(self.store.read())

    def test_round_trip_preserves_unknown_fields(self):
        data = {"authen_key": "fake-session-key", "new_field": {"flag": True}}
        self.store.write(data)
        self.assertEqual(self.store.read(), data)

    def test_invalid_json_and_non_object_fail_without_exposing_contents(self):
        self.path.parent.mkdir()
        for payload in ('{"PRIVATE_SENTINEL":', '["PRIVATE_SENTINEL"]', '"PRIVATE_SENTINEL"', "null"):
            with self.subTest(payload=payload):
                self.path.write_text(payload, encoding="utf-8")
                with self.assertRaises(SessionFormatError) as caught:
                    self.store.read()
                self.assertNotIn("PRIVATE_SENTINEL", str(caught.exception))
                self.assertNotIn(str(self.path), str(caught.exception))

    def test_atomic_replace_failure_preserves_previous_session_and_cleans_temp(self):
        self.store.write({"refresh_token": "fake-old-token"})
        original = self.path.read_bytes()
        with patch("myfap.storage.os.replace", side_effect=OSError("PRIVATE_SENTINEL")):
            with self.assertRaises(SessionStoreError) as caught:
                self.store.write({"refresh_token": "fake-new-token"})
        self.assertNotIn("PRIVATE_SENTINEL", str(caught.exception))
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_serialization_failure_preserves_previous_session_and_cleans_temp(self):
        self.store.write({"refresh_token": "fake-old-token"})
        original = self.path.read_bytes()
        with self.assertRaises(SessionStoreError):
            self.store.write({"not_json": object()})
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_fsync_failure_preserves_previous_session_and_cleans_temp(self):
        self.store.write({"refresh_token": "fake-old-token"})
        original = self.path.read_bytes()
        with patch("myfap.storage.os.fsync", side_effect=OSError("PRIVATE_SENTINEL")):
            with self.assertRaises(SessionStoreError) as caught:
                self.store.write({"refresh_token": "fake-new-token"})
        self.assertNotIn("PRIVATE_SENTINEL", str(caught.exception))
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    @unittest.skipIf(os.name == "nt", "Windows dùng ACL thay cho mode POSIX")
    def test_secret_file_is_private_before_writing_and_after_replace(self):
        original_dump = json.dump
        observed_modes = []

        def check_mode(data, stream, *args, **kwargs):
            observed_modes.append(stat.S_IMODE(os.fstat(stream.fileno()).st_mode))
            return original_dump(data, stream, *args, **kwargs)

        with patch("myfap.storage.json.dump", side_effect=check_mode):
            self.store.write({"refresh_token": "fake-token"})
        self.assertEqual(observed_modes, [0o600])
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)

    def _symlink(self, link, target):
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("Không có quyền tạo symlink trên môi trường này")

    def test_session_symlink_is_rejected_without_modifying_target(self):
        self.path.parent.mkdir()
        target = self.path.parent / "target.json"
        target.write_text('{"marker": "fake-original"}', encoding="utf-8")
        self._symlink(self.path, target)
        with self.assertRaises(SessionStoreError):
            self.store.read()
        with self.assertRaises(SessionStoreError):
            self.store.write({"marker": "fake-replaced"})
        self.assertEqual(json.loads(target.read_text(encoding="utf-8")), {"marker": "fake-original"})

    def test_reparse_point_is_rejected_before_opening(self):
        metadata = SimpleNamespace(st_mode=stat.S_IFREG, st_file_attributes=0x400)
        with patch("myfap.storage.Path.lstat", return_value=metadata):
            for action in (self.store.read, lambda: self.store.write({"fake": True})):
                with self.subTest(action=action):
                    with self.assertRaises(SessionStoreError):
                        action()
            with self.assertRaises(SessionStoreError):
                with self.store.lock():
                    self.fail("Không được sử dụng reparse point")

    def test_non_file_path_is_rejected_without_replacing_directory(self):
        self.path.mkdir(parents=True)
        with self.assertRaises(SessionStoreError):
            self.store.read()
        with self.assertRaises(SessionStoreError):
            self.store.write({"fake": True})
        with self.assertRaises(SessionStoreError):
            with self.store.lock():
                self.fail("Đường dẫn session phải là file thường")
        self.assertTrue(self.path.is_dir())

    def test_path_inspection_failure_does_not_expose_operating_system_message(self):
        with patch("myfap.storage.Path.lstat", side_effect=PermissionError("PRIVATE_SENTINEL")):
            for action in (self.store.read, lambda: self.store.write({"fake": True})):
                with self.subTest(action=action):
                    with self.assertRaises(SessionStoreError) as caught:
                        action()
                    self.assertNotIn("PRIVATE_SENTINEL", str(caught.exception))

    def test_lock_reparse_point_is_rejected_before_opening(self):
        original_stat = Path.lstat
        metadata = SimpleNamespace(st_mode=stat.S_IFREG, st_file_attributes=0x400)

        def inspect_path(path):
            if path == Path(str(self.path) + ".lock"):
                return metadata
            return original_stat(path)

        with patch("myfap.storage.Path.lstat", inspect_path):
            with self.assertRaises(SessionStoreError):
                with self.store.lock():
                    self.fail("Không được khóa reparse point")

    def test_lock_with_invalid_size_fails_without_changing_it(self):
        self.path.parent.mkdir()
        lock_path = Path(str(self.path) + ".lock")
        lock_path.write_bytes(b"fake-invalid-size")
        with self.assertRaises(SessionStoreError):
            with self.store.lock():
                self.fail("File khóa không hợp lệ")
        self.assertEqual(lock_path.read_bytes(), b"fake-invalid-size")

    def test_lock_symlink_is_rejected_without_modifying_target(self):
        self.path.parent.mkdir()
        target = self.path.parent / "target.txt"
        target.write_text("fake-original", encoding="utf-8")
        self._symlink(Path(str(self.path) + ".lock"), target)
        with self.assertRaises(SessionStoreError):
            with self.store.lock():
                self.fail("Không được khóa qua symlink")
        self.assertEqual(target.read_text(encoding="utf-8"), "fake-original")

    def test_lock_is_stable_and_remains_after_exception(self):
        lock_path = Path(str(self.path) + ".lock")
        with self.assertRaisesRegex(RuntimeError, "fake-error"):
            with self.store.lock():
                identity = lock_path.stat().st_ino
                raise RuntimeError("fake-error")
        self.assertTrue(lock_path.exists())
        with self.store.lock():
            self.assertEqual(lock_path.stat().st_ino, identity)
            self.assertEqual(lock_path.stat().st_size, 1)

    def test_body_io_error_is_propagated_and_lock_released(self):
        failure = OSError("fake-body-error")
        with self.assertRaises(OSError) as caught:
            with self.store.lock():
                raise failure
        self.assertIs(caught.exception, failure)
        with self.store.lock():
            pass

    def test_cleanup_removes_idle_lock_after_critical_section(self):
        with self.store.lock(cleanup=True):
            self.assertTrue(self.store.lock_path.exists())
        self.assertFalse(self.store.lock_path.exists())
        with self.store.lock():
            self.store.write({"after_cleanup": True})
        self.assertEqual(self.store.read(), {"after_cleanup": True})

    def test_cleanup_preserves_body_exception(self):
        with self.assertRaisesRegex(RuntimeError, "fake-body-error"):
            with self.store.lock(cleanup=True):
                raise RuntimeError("fake-body-error")
        self.assertFalse(self.store.lock_path.exists())

    def test_cleanup_does_not_split_lock_with_open_waiter(self):
        context = multiprocessing.get_context("spawn")
        opened, proceed, blocked, acquired = (context.Event() for _ in range(4))
        process = context.Process(target=_paused_waiter, args=(str(self.path), opened, proceed, blocked, acquired))
        try:
            with self.store.lock(cleanup=True):
                process.start()
                self.assertTrue(opened.wait(10), "Tiến trình chờ chưa mở file khóa")
            if os.name == "nt":
                self.assertTrue(self.store.lock_path.exists(), "Windows phải giữ khóa khi handle khác còn mở")
            else:
                self.assertFalse(self.store.lock_path.exists())
            with self.store.lock():
                proceed.set()
                self.assertTrue(blocked.wait(10), "Tiến trình chờ phải đợi khóa đang được giữ")
                self.assertFalse(acquired.is_set(), "Không được tạo hai khóa song song sau cleanup")
            self.assertTrue(acquired.wait(10), "Tiến trình chờ chưa lấy được khóa hiện tại")
            process.join(10)
            self.assertEqual(process.exitcode, 0)
            with self.store.lock(cleanup=True):
                pass
            self.assertFalse(self.store.lock_path.exists())
        finally:
            proceed.set()
            if process.pid is not None:
                process.join(10)
                if process.is_alive():
                    process.terminate()
                    process.join()

    def test_logout_removes_session_and_idle_sidecar(self):
        from myfap.auth import MyFapAuth

        self.store.write({"fake": True})
        with self.store.lock():
            pass
        self.assertTrue(MyFapAuth(session_file=self.path).logout())
        self.assertFalse(self.path.exists())
        self.assertFalse(self.store.lock_path.exists())

    def test_logout_removes_corrupt_regular_file_without_parsing(self):
        from myfap.auth import MyFapAuth

        self.path.parent.mkdir()
        for payload in (b'{"PRIVATE_SENTINEL":', b'[]', b'null', b'\xff\xfe'):
            with self.subTest(payload=payload):
                self.path.write_bytes(payload)
                auth = MyFapAuth(session_file=self.path)
                with patch.object(auth.store, "read", side_effect=AssertionError("Không đọc JSON khi logout")):
                    self.assertTrue(auth.logout())
                self.assertFalse(self.path.exists())
                self.assertFalse(self.store.lock_path.exists())

    def test_logout_missing_file_is_idempotent_and_cleans_idle_lock(self):
        from myfap.auth import MyFapAuth

        auth = MyFapAuth(session_file=self.path)
        self.assertFalse(auth.logout())
        self.assertFalse(auth.logout())
        self.assertFalse(self.store.lock_path.exists())

    def test_logout_rejects_symlink_and_preserves_target(self):
        from myfap.auth import AuthError, MyFapAuth

        self.path.parent.mkdir()
        target = self.path.parent / "target.json"
        target.write_text("PRIVATE_SENTINEL", encoding="utf-8")
        self._symlink(self.path, target)
        with self.assertRaises(AuthError):
            MyFapAuth(session_file=self.path).logout()
        self.assertEqual(target.read_text(encoding="utf-8"), "PRIVATE_SENTINEL")

    def test_logout_rejects_non_regular_file_and_reparse_point(self):
        from myfap.auth import AuthError, MyFapAuth

        self.path.mkdir(parents=True)
        with self.assertRaises(AuthError):
            MyFapAuth(session_file=self.path).logout()
        self.assertTrue(self.path.is_dir())
        metadata = SimpleNamespace(st_mode=stat.S_IFREG, st_file_attributes=0x400)
        with patch("myfap.storage.Path.lstat", return_value=metadata):
            with self.assertRaises(AuthError):
                MyFapAuth(session_file=self.path).logout()

    def test_delete_revalidates_path_after_lock_is_acquired(self):
        self.store.write({"fake": "original"})
        before = self.path.read_bytes()
        metadata = SimpleNamespace(st_mode=stat.S_IFREG, st_file_attributes=0x400)
        with self.store.lock():
            with patch("myfap.storage.Path.lstat", return_value=metadata):
                with self.assertRaises(SessionStoreError):
                    self.store.delete()
        self.assertEqual(self.path.read_bytes(), before)

    @unittest.skipUnless(os.name == "nt", "Best-effort chmod chỉ áp dụng trên Windows")
    def test_windows_chmod_failure_does_not_hide_write_failure(self):
        with patch("myfap.storage.os.chmod", side_effect=OSError("fake-acl-error")):
            self.store.write({"fake": "initial"})
            with patch("myfap.storage.os.replace", side_effect=OSError("fake-write-error")):
                with self.assertRaises(SessionStoreError):
                    self.store.write({"fake": "replacement"})
        self.assertEqual(self.store.read(), {"fake": "initial"})

    def test_another_process_times_out_then_acquires_same_lock(self):
        context = multiprocessing.get_context("spawn")
        acquired, release = context.Event(), context.Event()
        process = context.Process(target=_hold_lock, args=(str(self.path), acquired, release))
        process.start()
        try:
            self.assertTrue(acquired.wait(10), "Tiến trình con chưa lấy được khóa")
            with patch("myfap.storage._LOCK_TIMEOUT", 0.15):
                with self.assertRaises(SessionStoreError):
                    with self.store.lock():
                        self.fail("Hai process không được giữ cùng khóa")
        finally:
            release.set()
            process.join(10)
            if process.is_alive():
                process.terminate()
                process.join()
        self.assertEqual(process.exitcode, 0)
        with self.store.lock():
            self.store.write({"after_release": True})
        self.assertEqual(self.store.read(), {"after_release": True})

    def test_concurrent_process_waits_before_read_modify_write(self):
        self.store.write({"counter": 0})
        context = multiprocessing.get_context("spawn")
        started = context.Event()
        process = context.Process(target=_update_counter, args=(str(self.path), started))
        try:
            with self.store.lock():
                process.start()
                self.assertTrue(started.wait(10), "Tiến trình con chưa bắt đầu")
                self.store.write({"counter": 10})
            process.join(10)
            self.assertFalse(process.is_alive(), "Tiến trình con không nhả khóa")
            self.assertEqual(process.exitcode, 0)
            self.assertEqual(self.store.read(), {"counter": 11})
        finally:
            if process.is_alive():
                process.terminate()
                process.join()


if __name__ == "__main__":
    unittest.main()
