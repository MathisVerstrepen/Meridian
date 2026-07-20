import errno
from types import SimpleNamespace

import pytest

from browser_service.app import process_hardening


class FakePrctl:
    def __init__(self, *, set_result: int = 0, get_result: int = 0) -> None:
        self.argtypes = None
        self.restype = None
        self.set_result = set_result
        self.get_result = get_result
        self.calls = []

    def __call__(self, command, *args):
        self.calls.append((command, args))
        return self.set_result if command == process_hardening.PR_SET_DUMPABLE else self.get_result


def test_apply_sets_zero_core_and_verifies_dumpable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    limits = []
    prctl = FakePrctl()
    hardening = process_hardening.ProcessHardening(SimpleNamespace(prctl=prctl))
    monkeypatch.setattr(
        process_hardening.resource,
        "setrlimit",
        lambda kind, value: limits.append(value),
    )
    monkeypatch.setattr(process_hardening.resource, "getrlimit", lambda kind: (0, 0))

    hardening.apply()
    hardening.assert_applied()

    assert limits == [(0, 0)]
    assert [call[0] for call in prctl.calls] == [4, 3, 3]


@pytest.mark.parametrize(
    "failure",
    ["platform", "rlimit", "set", "readback", "missing"],
)
def test_hardening_failures_are_sanitized(monkeypatch: pytest.MonkeyPatch, failure: str) -> None:
    prctl = FakePrctl(
        set_result=-1 if failure == "set" else 0,
        get_result=1 if failure == "readback" else 0,
    )
    libc = SimpleNamespace(prctl=prctl) if failure != "missing" else SimpleNamespace()
    hardening = process_hardening.ProcessHardening(libc)
    if failure == "platform":
        monkeypatch.setattr(process_hardening.sys, "platform", "darwin")
    if failure == "rlimit":
        monkeypatch.setattr(
            process_hardening.resource,
            "setrlimit",
            lambda *args: (_ for _ in ()).throw(OSError(errno.EPERM, "raw")),
        )
    with pytest.raises(process_hardening.ProcessHardeningError) as captured:
        hardening.apply()
    assert str(captured.value) == "browser service process hardening failed"
