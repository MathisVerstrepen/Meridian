"""No-output same-UID probe used only inside the built browser-service container."""

import ctypes
import errno
import os
from pathlib import Path

PTRACE_SEIZE = 0x4206


def _status_value(path: Path, name: str) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{name}:"):
            return line.split(":", 1)[1].strip()
    raise AssertionError(f"missing {name}")


def main() -> None:
    command = Path("/proc/1/cmdline").read_bytes().replace(b"\0", b" ").decode()
    assert "uvicorn" in command and "app.main:app" in command
    assert os.geteuid() == int(_status_value(Path("/proc/1/status"), "Uid").split()[1])
    try:
        descriptor = os.open("/proc/1/environ", os.O_RDONLY)
    except OSError as error:
        assert error.errno in {errno.EACCES, errno.EPERM}
    else:
        os.close(descriptor)
        raise AssertionError("parent environment unexpectedly opened")
    libc = ctypes.CDLL(None, use_errno=True)
    libc.ptrace.argtypes = [
        ctypes.c_uint,
        ctypes.c_uint,
        ctypes.c_void_p,
        ctypes.c_void_p,
    ]
    libc.ptrace.restype = ctypes.c_long
    assert libc.ptrace(PTRACE_SEIZE, 1, None, None) == -1
    assert ctypes.get_errno() in {errno.EACCES, errno.EPERM}
    assert int(_status_value(Path("/proc/self/status"), "CapEff"), 16) == 0
    core = next(
        line
        for line in Path("/proc/1/limits").read_text().splitlines()
        if line.startswith("Max core file size")
    ).split()
    assert core[-3:-1] == ["0", "0"]


if __name__ == "__main__":
    main()
