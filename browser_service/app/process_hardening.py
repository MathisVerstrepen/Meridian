import ctypes
import errno
import resource
import sys
from typing import Any

PR_SET_DUMPABLE = 4
PR_GET_DUMPABLE = 3


class ProcessHardeningError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("browser service process hardening failed")


class ProcessHardening:
    def __init__(self, libc: Any | None = None) -> None:
        self._libc = libc
        self.applied = False

    def apply(self) -> None:
        if not sys.platform.startswith("linux"):
            raise ProcessHardeningError()
        try:
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
            libc = self._libc or ctypes.CDLL(None, use_errno=True)
            prctl = libc.prctl
            prctl.argtypes = [
                ctypes.c_int,
                ctypes.c_ulong,
                ctypes.c_ulong,
                ctypes.c_ulong,
                ctypes.c_ulong,
            ]
            prctl.restype = ctypes.c_int
            if prctl(PR_SET_DUMPABLE, 0, 0, 0, 0) != 0:
                ctypes.set_errno(ctypes.get_errno() or errno.EPERM)
                raise ProcessHardeningError()
            if prctl(PR_GET_DUMPABLE, 0, 0, 0, 0) != 0:
                raise ProcessHardeningError()
        except ProcessHardeningError:
            raise
        except Exception:
            raise ProcessHardeningError() from None
        self._libc = libc
        self.applied = True

    def assert_applied(self) -> None:
        if not self.applied or self._libc is None:
            raise ProcessHardeningError()
        try:
            if self._libc.prctl(PR_GET_DUMPABLE, 0, 0, 0, 0) != 0:
                raise ProcessHardeningError()
            if resource.getrlimit(resource.RLIMIT_CORE) != (0, 0):
                raise ProcessHardeningError()
        except ProcessHardeningError:
            raise
        except Exception:
            raise ProcessHardeningError() from None
