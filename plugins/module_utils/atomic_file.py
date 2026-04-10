"""
Atomic file writer that stages data in a temporary file and replaces the
destination on successful exit.

The temporary file is created in the destination directory so that
`os.replace()` can perform an atomic move on the same filesystem.
"""

from __future__ import annotations

import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import IO, Any, Optional, Union

PathLike = Union[str, os.PathLike[str]]


class AtomicFileWriter:
    """
    Context manager for atomic file replacement.

    A temporary file is created in the target directory. On successful
    exit, the file is flushed, synced, closed, and atomically moved to
    the final destination using `os.replace()`.

    If an exception occurs inside the context block, the temporary file
    is closed and removed.
    """

    def __init__(
        self,
        destination: PathLike,
        mode: str = "w",
        *,
        encoding: Optional[str] = "utf-8",
        suffix: Optional[str] = None,
    ) -> None:
        """
        Initialize the atomic file writer.

        Args:
            destination:
                Final file path that should be replaced atomically.
            mode:
                File mode, for example ``"w"`` or ``"wb"``.
            encoding:
                Text encoding for non-binary modes. Must be ``None`` in
                binary mode.
            suffix:
                Optional suffix for the temporary file.

        Raises:
            ValueError:
                If binary mode is used together with a non-None encoding.
        """
        if "b" in mode and encoding is not None:
            raise ValueError("encoding must be None when using binary mode")

        self.destination = Path(destination)
        self.mode = mode
        self.encoding = encoding
        self.suffix = suffix

        self._file_handle: Optional[IO[Any]] = None
        self._temp_name: Optional[str] = None

    def __enter__(self) -> IO[Any]:
        """
        Create and return the staged temporary file.

        Returns:
            The opened temporary file object.

        Raises:
            FileNotFoundError:
                If the target directory does not exist.
            NotADirectoryError:
                If the parent path is not a directory.
            PermissionError:
                If the temporary file cannot be created.
            OSError:
                For other filesystem-related errors.
        """
        self.destination.parent.mkdir(parents=True, exist_ok=True)

        kwargs: dict[str, Any] = {
            "mode": self.mode,
            "suffix": self.suffix,
            "delete": False,
            "dir": os.fspath(self.destination.parent),
        }

        if "b" not in self.mode:
            kwargs["encoding"] = self.encoding

        self._file_handle = NamedTemporaryFile(**kwargs)
        self._temp_name = self._file_handle.name

        return self._file_handle

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """
        Commit or rollback the staged file.

        On successful exit, the temporary file is flushed, synced, closed,
        and atomically moved to the destination.

        On error, the temporary file is removed.

        Returns:
            Always ``False`` so that exceptions are propagated.
        """
        cleanup_error: Optional[BaseException] = None

        try:
            if self._file_handle is not None:
                try:
                    self._file_handle.flush()
                    os.fsync(self._file_handle.fileno())
                except OSError as exc:
                    cleanup_error = exc

                try:
                    self._file_handle.close()
                except OSError as exc:
                    if cleanup_error is None:
                        cleanup_error = exc

            if (
                exc_type is None
                and cleanup_error is None
                and self._temp_name is not None
            ):
                os.replace(self._temp_name, self.destination)
                self._fsync_parent_directory()
            elif self._temp_name is not None:
                self._safe_unlink(self._temp_name)

        finally:
            self._file_handle = None
            self._temp_name = None

        if cleanup_error is not None and exc_type is None:
            raise cleanup_error

        return False

    def _fsync_parent_directory(self) -> None:
        """
        Best-effort sync of the parent directory on POSIX systems.

        This improves durability for the directory entry after `os.replace()`.
        On platforms where directory syncing is unsupported, this method
        silently does nothing.
        """
        if os.name != "posix":
            return

        try:
            dir_fd = os.open(self.destination.parent, os.O_RDONLY)
        except OSError:
            return

        try:
            os.fsync(dir_fd)
        except OSError:
            pass
        finally:
            os.close(dir_fd)

    @staticmethod
    def _safe_unlink(path: str) -> None:
        """
        Remove a file if it still exists.

        Args:
            path:
                File path to remove.
        """
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
