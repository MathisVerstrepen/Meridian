"""Keep owned Python runtimes aligned and local environment upgrades non-destructive."""

import os
import re
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "scripts/python-env.sh"
VERSION = (ROOT / ".python-version").read_text().strip()


class RuntimeDeclarationTests(unittest.TestCase):
    def test_version_and_typechecker_targets(self):
        self.assertEqual(VERSION, "3.14")
        for service in ("api", "browser_service", "sandbox_manager"):
            with self.subTest(service=service):
                config = tomllib.loads((ROOT / service / "pyproject.toml").read_text())
                self.assertEqual(config["tool"]["mypy"]["python_version"], VERSION)

    def test_python_docker_stages_keep_service_os_baselines(self):
        variants = {
            "api": "trixie",
            "browser-service": "bookworm",
            "sandbox-manager": "bookworm",
            "sandbox-python": "bookworm",
        }
        for name, variant in variants.items():
            with self.subTest(image=name):
                dockerfile = (ROOT / "docker" / f"{name}.Dockerfile").read_text()
                bases = re.findall(r"^FROM (python:\S+)", dockerfile, re.MULTILINE)
                self.assertTrue(bases)
                self.assertEqual(set(bases), {f"python:{VERSION}-slim-{variant}"})

    def test_api_image_runs_bridge_smoke_as_runtime_user(self):
        dockerfile = (ROOT / "docker/api.Dockerfile").read_text()
        smoke = "RUN npm --prefix /app/gemini_cli_runtime run smoke:bridge-imports"
        self.assertIn(smoke, dockerfile)
        self.assertLess(
            dockerfile.index("COPY --chown=appuser:appuser ./api/app ."), dockerfile.index(smoke)
        )
        self.assertLess(dockerfile.index("USER appuser"), dockerfile.index(smoke))
        self.assertLess(dockerfile.index(smoke), dockerfile.index("CMD "))

    def test_ci_selects_declared_python_before_using_it(self):
        for path in (ROOT / ".github/workflows").glob("*.yml"):
            workflow = yaml.safe_load(path.read_text())
            for name, job in workflow.get("jobs", {}).items():
                selected = False
                for step in job.get("steps", []):
                    if step.get("uses", "").startswith("actions/setup-python@"):
                        self.assertEqual(step["with"]["python-version-file"], ".python-version")
                        selected = True
                    if re.search(r"^\s*(python\S*|pip\S*)\s", step.get("run", ""), re.MULTILINE):
                        with self.subTest(workflow=path.name, job=name, step=step.get("name")):
                            self.assertTrue(selected, "Select project Python before running it")


class EnvironmentGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="meridian-python-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = os.environ.copy()
        for name in ("API_PYTHON", "BROWSER_SERVICE_PYTHON", "SANDBOX_PYTHON", "MAKEFLAGS"):
            self.env.pop(name, None)

    def run_command(self, *args):
        return subprocess.run(
            [str(arg) for arg in args],
            cwd=ROOT,
            env=self.env,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def fake_python(self, path, version):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "#!/bin/bash\n"
            f'if [[ "$1" == "-c" ]]; then echo "{version}"; exit 0; fi\n'
            'printf "%s\\n" "$*" >> "${CALL_LOG:?}"\n'
        )
        path.chmod(0o755)
        return path

    def test_accepts_current_and_rejects_old_or_missing_interpreters(self):
        for version, expected in ((VERSION, 0), ("3.12", 1)):
            with self.subTest(version=version):
                python = self.fake_python(self.root / version / "python", version)
                result = self.run_command("bash", HELPER, "check", python)
                self.assertEqual(result.returncode, expected, result.stderr)
        result = self.run_command("bash", HELPER, "check", self.root / "missing")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Python 3.14 required", result.stderr)

    def test_old_environment_is_not_changed_or_recreated(self):
        venv = self.root / "old venv"
        python = self.fake_python(venv / "bin/python", "3.12")
        original = python.read_bytes()
        sentinel = venv / "user-data"
        sentinel.write_text("keep")
        result = self.run_command("bash", HELPER, "create", venv, sys.executable)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Existing files were not changed", result.stderr)
        self.assertEqual(python.read_bytes(), original)
        self.assertEqual(sentinel.read_text(), "keep")

    def test_broken_environment_is_not_replaced(self):
        venv = self.root / "broken"
        venv.symlink_to(self.root / "missing", target_is_directory=True)
        result = self.run_command("bash", HELPER, "create", venv, sys.executable)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(venv.is_symlink())
        self.assertFalse(venv.exists())

    def test_wrong_creator_does_not_create_environment(self):
        creator = self.fake_python(self.root / "python", "3.12")
        target = self.root / "new"
        result = self.run_command("bash", HELPER, "create", target, creator)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(target.exists())

    def test_create_and_reuse_actual_python314_environment(self):
        self.assertEqual(sys.version_info[:2], (3, 14), "Run runtime tests with Python 3.14")
        target = self.root / "new venv"
        result = self.run_command("bash", HELPER, "create", target, sys.executable)
        self.assertEqual(result.returncode, 0, result.stderr)
        python = target / "bin/python"
        result = self.run_command("bash", HELPER, "check", python)
        self.assertEqual(result.returncode, 0, result.stderr)
        sentinel = target / "user-data"
        sentinel.write_text("keep")
        # A matching existing environment does not need the creator installed on PATH.
        result = self.run_command("bash", HELPER, "create", target, self.root / "missing")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(sentinel.read_text(), "keep")

    def test_make_rejects_old_environments_before_install_or_checks(self):
        venv = self.root / "old venv"
        self.fake_python(venv / "bin/python", "3.12")
        log = self.root / "calls"
        self.env["CALL_LOG"] = str(log)
        for target, variable in (
            ("install-api", "API_VENV"),
            ("install-browser-service", "BROWSER_SERVICE_VENV"),
            ("lint-api", "API_VENV"),
            ("test-api", "API_VENV"),
            ("test-browser-service", "BROWSER_SERVICE_VENV"),
        ):
            with self.subTest(target=target):
                result = self.run_command("make", target, f"{variable}={venv}")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Python 3.14 required", result.stderr)
                self.assertFalse(log.exists(), "No installation or tool command may run")

    def test_make_linter_uses_overridden_environment_for_every_tool(self):
        venv = self.root / "selected venv"
        self.fake_python(venv / "bin/python", VERSION)
        log = self.root / "calls"
        self.env["CALL_LOG"] = str(log)
        result = self.run_command("make", "lint-api", f"API_VENV={venv}")
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = log.read_text().splitlines()
        self.assertEqual(len(calls), 4)
        for call, tool in zip(calls, ("black", "isort", "flake8", "mypy")):
            self.assertTrue(call.startswith(f"-m {tool} "), call)


if __name__ == "__main__":
    unittest.main()
