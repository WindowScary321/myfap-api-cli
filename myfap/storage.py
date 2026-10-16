"""Atomic, private session-file storage with a small cross-process lock."""

from __future__ import annotations

import errno
import json
import os
from contextlib import contextmanager
from pathlib import Path
import stat
import tempfile
import time
from typing import Iterator, Mapping, Optional


_LOCK_TIMEOUT = 10.0
_LOCK_POLL_INTERVAL = 0.05
_REPARSE_POINT = 0x400


class SessionStoreError(RuntimeError):
    """A session file could not be safely read, written, or locked."""


class SessionFormatError(SessionStoreError):
    """Session bytes can be read safely but are not a JSON object."""


class _PathChanged(SessionStoreError):
    pass


def _validate_path(path: Path) -> Optional[os.stat_result]:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return None
    except OSError:
        raise SessionStoreError("Không thể kiểm tra đường dẫn session.") from None
    if (
        not stat.S_ISREG(metadata.st_mode)
        or getattr(metadata, "st_file_attributes", 0) & _REPARSE_POINT
    ):
        raise SessionStoreError("Đường dẫn session phải là file thường.")
    return metadata


def _open(path: Path, flags: int, mode: int = 0o600) -> int:
    _validate_path(path)
    flags |= getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    descriptor = os.open(str(path), flags, mode)
    try:
        metadata = _validate_path(path)
        opened_metadata = os.fstat(descriptor)
        if metadata is None or not os.path.samestat(metadata, opened_metadata):
            raise _PathChanged("Đường dẫn session đã thay đổi khi mở file.")
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


class SessionStore:
    """Store session JSON without exposing or partially replacing credentials."""

    def __init__(self, path: os.PathLike[str] | str):
        self.path = Path(path)
        self.lock_path = Path(f"{self.path}.lock")

    def read(self) -> Optional[dict]:
        try:
            fd = _open(self.path, os.O_RDONLY)
        except FileNotFoundError:
            _validate_path(self.path)
            return None
        except OSError:
            raise SessionStoreError("Không thể mở file session an toàn.") from None
        try:
            with os.fdopen(fd, "r", encoding="utf-8") as stream:
                fd = None
                try:
                    data = json.load(stream)
                except (UnicodeError, ValueError):
                    raise SessionFormatError("File session không phải JSON hợp lệ.") from None
        except SessionStoreError:
            raise
        except (OSError, ValueError):
            raise SessionStoreError("Không thể đọc file session.") from None
        finally:
            if fd is not None:
                os.close(fd)
        if not isinstance(data, dict):
            raise SessionFormatError("File session phải chứa một object JSON.")
        return data

    def write(self, data: Mapping[str, object]) -> None:
        if not isinstance(data, Mapping):
            raise SessionStoreError("Dữ liệu session phải là một object.")
        _validate_path(self.path)
        try:
            self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            _validate_path(self.path)
            fd, temporary_name = tempfile.mkstemp(
                prefix=f".{self.path.name}.", suffix=".tmp", dir=str(self.path.parent)
            )
            temporary_path = Path(temporary_name)
            try:
                try:
                    os.chmod(temporary_name, 0o600)
                except OSError:
                    if os.name != "nt":
                        raise
                with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
                    fd = None
                    json.dump(data, stream, ensure_ascii=False, indent=2)
                    stream.write("\n")
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary_name, self.path)
            finally:
                if fd is not None:
                    try:
                        os.close(fd)
                    except OSError:
                        pass
                try:
                    temporary_path.unlink()
                except OSError:
                    pass
        except SessionStoreError:
            raise
        except (OSError, TypeError, ValueError):
            raise SessionStoreError("Không thể ghi file session an toàn.") from None

    @contextmanager
    def lock(self, *, cleanup: bool = False) -> Iterator[None]:
        """Hold an exclusive one-byte lock on a stable sidecar file."""

        _validate_path(self.path)
        _validate_path(self.lock_path)
        fd = self._acquire_lock()
        identity = os.fstat(fd)
        try:
            yield
        finally:
            try:
                # POSIX waiters must revalidate their inode after unlink while held.
                if cleanup and os.name != "nt":
                    self._cleanup_lock(identity)
                self._unlock(fd)
            except OSError:
                raise SessionStoreError("Không thể nhả khóa session an toàn.") from None
            finally:
                os.close(fd)
                # Windows refuses deletion while another owner or waiter holds a handle.
                if cleanup and os.name == "nt":
                    self._cleanup_lock(identity)

    def _acquire_lock(self) -> int:
        deadline = time.monotonic() + _LOCK_TIMEOUT
        try:
            self.lock_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            while True:
                fd, acquired, keep = None, False, False
                try:
                    fd = _open(self.lock_path, os.O_RDWR | os.O_CREAT)
                    if os.fstat(fd).st_size == 0:
                        os.write(fd, b"\0")
                        os.fsync(fd)
                    elif os.fstat(fd).st_size != 1:
                        raise SessionStoreError("File khóa session không hợp lệ.")
                    self._try_lock(fd)
                    acquired = True
                    if self._lock_path_matches(fd):
                        keep = True
                        return fd
                except _PathChanged:
                    pass
                except OSError as error:
                    if error.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                        raise
                finally:
                    if fd is not None and not keep:
                        try:
                            if acquired:
                                self._unlock(fd)
                        finally:
                            os.close(fd)
                if time.monotonic() >= deadline:
                    raise SessionStoreError("Đã hết thời gian chờ khóa session.") from None
                time.sleep(_LOCK_POLL_INTERVAL)
        except OSError:
            raise SessionStoreError("Không thể mở khóa session an toàn.") from None

    def _lock_path_matches(self, fd: int) -> bool:
        metadata = _validate_path(self.lock_path)
        return metadata is not None and os.path.samestat(metadata, os.fstat(fd))

    def _cleanup_lock(self, identity: os.stat_result) -> None:
        try:
            current = _validate_path(self.lock_path)
            if current is not None and os.path.samestat(current, identity):
                self.lock_path.unlink()
        except (OSError, SessionStoreError):
            pass

    @staticmethod
    def _try_lock(fd: int) -> None:
        if os.name == "nt":
            import msvcrt

            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            return
        import fcntl

        fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB, 1, 0, os.SEEK_SET)

    @staticmethod
    def _unlock(fd: int) -> None:
        if os.name == "nt":
            import msvcrt

            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            return
        import fcntl

        fcntl.lockf(fd, fcntl.LOCK_UN, 1, 0, os.SEEK_SET)
