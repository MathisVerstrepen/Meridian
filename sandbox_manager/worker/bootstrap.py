import base64
import binascii
import ctypes.util
import errno
import os
import resource
import runpy
import sys
from pathlib import Path

CODE_ENV_VAR = "SANDBOX_CODE_B64"
OUTPUT_DIR_ENV_VAR = "MERIDIAN_OUTPUT_DIR"
RUNTIME_ENV_VAR = "MERIDIAN_SANDBOX_RUNTIME"
MAX_FILE_SIZE_ENV_VAR = "MERIDIAN_MAX_FILE_SIZE_BYTES"
SANDBOX_HOME_DIR = "/tmp/home"
SANDBOX_CACHE_DIR = "/tmp/.cache"
SANDBOX_CONFIG_DIR = "/tmp/.config"
SANDBOX_MPLCONFIGDIR = "/tmp/.config/matplotlib"
THREAD_LIMIT_ENV = {
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "VECLIB_MAXIMUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
}
DENIED_SYSCALLS = (
    "execve",
    "execveat",
    "ptrace",
    "process_vm_readv",
    "process_vm_writev",
    "bpf",
    "userfaultfd",
    "perf_event_open",
    "socket",
    "socketpair",
    "accept",
    "accept4",
    "connect",
    "bind",
    "listen",
    "mount",
    "umount2",
    "pivot_root",
    "setns",
    "unshare",
    "init_module",
    "finit_module",
    "delete_module",
)


def _resolve_libseccomp_path() -> str | None:
    candidates = (
        "/usr/lib/x86_64-linux-gnu/libseccomp.so.2",
        "/lib/x86_64-linux-gnu/libseccomp.so.2",
        "/usr/lib/aarch64-linux-gnu/libseccomp.so.2",
        "/lib/aarch64-linux-gnu/libseccomp.so.2",
    )
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return None


def _get_max_file_size_bytes() -> int:
    raw_limit = os.environ.get(MAX_FILE_SIZE_ENV_VAR, "").strip()
    if not raw_limit:
        return 0

    try:
        parsed_limit = int(raw_limit)
    except ValueError as exc:
        raise RuntimeError("Invalid sandbox file size limit") from exc

    return max(parsed_limit, 0)


def _apply_limits() -> None:
    for key, value in THREAD_LIMIT_ENV.items():
        os.environ.setdefault(key, value)

    max_file_size_bytes = _get_max_file_size_bytes()
    if max_file_size_bytes > 0:
        resource.setrlimit(
            resource.RLIMIT_FSIZE,
            (max_file_size_bytes, max_file_size_bytes),
        )


def _prepare_runtime_dirs() -> None:
    runtime_dirs = (
        Path(SANDBOX_HOME_DIR),
        Path(SANDBOX_CACHE_DIR),
        Path(SANDBOX_CONFIG_DIR),
        Path(SANDBOX_MPLCONFIGDIR),
    )
    for runtime_dir in runtime_dirs:
        runtime_dir.mkdir(parents=True, exist_ok=True)

    os.environ["HOME"] = SANDBOX_HOME_DIR
    os.environ["XDG_CACHE_HOME"] = SANDBOX_CACHE_DIR
    os.environ["XDG_CONFIG_HOME"] = SANDBOX_CONFIG_DIR
    os.environ["MPLCONFIGDIR"] = SANDBOX_MPLCONFIGDIR
    os.environ.setdefault("MPLBACKEND", "Agg")


def _apply_seccomp() -> None:
    if os.environ.get(RUNTIME_ENV_VAR) == "nsjail":
        return

    try:
        original_find_library = ctypes.util.find_library
        libseccomp_path = _resolve_libseccomp_path()
        if libseccomp_path:

            def _patched_find_library(name: str) -> str | None:
                if name == "seccomp":
                    return libseccomp_path
                return original_find_library(name)

            ctypes.util.find_library = _patched_find_library
        import pyseccomp as seccomp
    except Exception as exc:
        raise RuntimeError("pyseccomp is required in the sandbox worker") from exc
    finally:
        ctypes.util.find_library = original_find_library

    syscall_filter = seccomp.SyscallFilter(defaction=seccomp.ALLOW)
    for syscall in DENIED_SYSCALLS:
        try:
            syscall_filter.add_rule(seccomp.ERRNO(errno.EPERM), syscall)
        except Exception:
            continue

    syscall_filter.load()


def main() -> None:
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/execution.py")
    encoded_payload = os.environ.get(CODE_ENV_VAR)
    output_dir = Path(os.environ.get(OUTPUT_DIR_ENV_VAR, "/tmp/outputs"))
    if not encoded_payload:
        raise RuntimeError(f"Missing {CODE_ENV_VAR} environment variable")

    try:
        payload = base64.b64decode(encoded_payload.encode("ascii"), validate=True)
    except (ValueError, binascii.Error) as exc:
        raise RuntimeError("Invalid sandbox payload encoding") from exc

    target.parent.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)

    os.environ.pop(CODE_ENV_VAR, None)
    os.unsetenv(CODE_ENV_VAR)
    os.environ["PYTHONUNBUFFERED"] = "1"
    _prepare_runtime_dirs()
    _apply_limits()
    _apply_seccomp()

    sys.argv = [str(target)]
    runpy.run_path(str(target), run_name="__main__")


if __name__ == "__main__":
    main()
