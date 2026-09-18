import contextlib
import io
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import benchmark_docker_cache as benchmark  # noqa: E402


def fixture(context):
    frontend = context / "ui/app/app.vue"
    frontend.parent.mkdir(parents=True)
    frontend.write_text(benchmark.FRONTEND_MARKER + "\nconst fixture = true;\n</script>\n")
    sandbox = context / "sandbox_manager/worker/bootstrap.py"
    sandbox.parent.mkdir(parents=True)
    sandbox.write_text("print('fixture')\n")
    return frontend, sandbox


class BuildCommandTests(unittest.TestCase):
    def test_local_only_arguments_and_mode_isolation(self):
        for image in benchmark.IMAGES:
            for mode in ("min", "max"):
                cache = Path("/tmp/opencode/test") / f"{image}-{mode}"
                for probe in ("cold", "unchanged", "changed"):
                    with self.subTest(image=image, mode=mode, probe=probe):
                        command = benchmark.build_command(
                            "owned", Path("/context"), image, mode, probe, cache
                        )
                        self.assertEqual(
                            command[:5], ["docker", "buildx", "build", "--builder", "owned"]
                        )
                        self.assertIn("--output=type=cacheonly", command)
                        self.assertEqual(
                            command[command.index("--file") + 1],
                            "/context/" + benchmark.IMAGES[image],
                        )
                        self.assertEqual(command[-1], "/context")
                        for forbidden in (
                            "--push",
                            "--load",
                            "--use",
                            "--tag",
                            "--secret",
                            "login",
                            "type=registry",
                        ):
                            self.assertNotIn(forbidden, " ".join(command))
                        if probe == "cold":
                            self.assertIn("--no-cache", command)
                            self.assertIn(f"type=local,dest={cache},mode={mode}", command)
                            self.assertNotIn("--cache-from", command)
                        else:
                            self.assertIn(f"type=local,src={cache}", command)
                            self.assertNotIn("--cache-to", command)
                            self.assertNotIn("--no-cache", command)
                        if image == "frontend":
                            version = "0.0.1-beta" if probe == "changed" else "0.0.0-beta"
                            self.assertIn(f"NUXT_PUBLIC_VERSION={version}", command)
                        else:
                            self.assertNotIn("--build-arg", command)

    def test_fixture_changes_are_harmless_and_fail_if_marker_drifts(self):
        with tempfile.TemporaryDirectory() as temp:
            context = Path(temp)
            frontend, sandbox = fixture(context)
            target, original = benchmark.change_context(context, "frontend")
            self.assertEqual(target, frontend)
            self.assertIn(
                benchmark.FRONTEND_MARKER + "\n// Docker cache benchmark", target.read_text()
            )
            self.assertIn("const fixture = true;", original)
            target, original = benchmark.change_context(context, "sandbox-python")
            self.assertEqual(target, sandbox)
            self.assertTrue(target.read_text().startswith(original))
            self.assertIn("\n# Docker cache benchmark", target.read_text())
            frontend.write_text("<template />")
            with self.assertRaisesRegex(benchmark.BenchmarkError, "script fixture"):
                benchmark.change_context(context, "frontend")


class SnapshotTests(unittest.TestCase):
    def test_dirty_or_untracked_representative_inputs_fail_before_archive(self):
        for dirty in (" M ui/app/app.vue", "?? ui/new.vue", "M  .dockerignore"):
            with mock.patch.object(benchmark, "capture", return_value=dirty) as capture:
                with self.assertRaisesRegex(benchmark.BenchmarkError, "must be clean"):
                    benchmark.snapshot(Path("/repo"), Path("/temp/context"), benchmark.Budget())
                self.assertEqual(capture.call_count, 1)
                self.assertIn("--untracked-files=all", capture.call_args.args[0])

    def test_archive_uses_only_committed_inputs_and_keeps_dockerignore(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "source"
            root.mkdir()
            (root / ".env").write_text("secret not in archive")
            context = Path(temp) / "context"
            calls = []

            def capture(command, budget, cwd):
                calls.append(command)
                if command[1] in ("status", "ls-files"):
                    return ""
                if command[1] == "rev-parse":
                    return "committed-head"
                archive = next(
                    arg.removeprefix("--output=") for arg in command if arg.startswith("--output=")
                )
                with tarfile.open(archive, "w") as tar:
                    for name, content in (
                        (".dockerignore", b"**/.env\n"),
                        ("ui/app/app.vue", b"committed"),
                    ):
                        member = tarfile.TarInfo(name)
                        member.size = len(content)
                        tar.addfile(member, io.BytesIO(content))
                return ""

            with mock.patch.object(benchmark, "capture", side_effect=capture):
                commit = benchmark.snapshot(root, context, benchmark.Budget())
            self.assertEqual(commit, "committed-head")
            self.assertEqual((context / ".dockerignore").read_text(), "**/.env\n")
            self.assertEqual((context / "ui/app/app.vue").read_text(), "committed")
            self.assertFalse((context / ".env").exists())
            archive_command = calls[-1]
            self.assertIn("committed-head", archive_command)
            paths_start = archive_command.index("--") + 1
            self.assertEqual(archive_command[paths_start:], list(benchmark.SOURCE_PATHS))
            self.assertFalse((context.parent / "source.tar").exists())

    def test_specific_ignore_overrides_are_not_silently_omitted(self):
        with mock.patch.object(
            benchmark, "capture", side_effect=["", "docker/ui.Dockerfile.dockerignore"]
        ):
            with self.assertRaisesRegex(benchmark.BenchmarkError, "ignore files"):
                benchmark.snapshot(Path("/repo"), Path("/temp/context"), benchmark.Budget())


class MeasurementTests(unittest.TestCase):
    def test_metrics_distinguish_cached_executed_and_unknown(self):
        duration, steps = benchmark.log_metrics(
            "\n".join(
                [
                    "#4 [builder 2/3] RUN pnpm install --frozen-lockfile",
                    "#4 CACHED",
                    "#5 [nsjail-builder 7/7] RUN make",
                    "#5 DONE 9.2s",
                    "#6 [stage-1 3/4] RUN pip install -r requirements.txt",
                    "#9 exporting cache to client",
                    "#9 preparing build cache for export",
                    "#9 writing layer sha256:abc 1.0s done",
                    "#9 DONE 2.4s",
                ]
            )
        )
        self.assertEqual(duration, 2.4)
        self.assertEqual([step["status"] for step in steps], ["cached", "executed", "unknown"])
        self.assertEqual(benchmark.log_metrics("missing logs"), (None, []))

    def test_unique_blob_bytes_and_missing_measurements(self):
        with tempfile.TemporaryDirectory() as temp:
            cache = Path(temp)
            self.assertIsNone(benchmark.blob_bytes(cache))
            (cache / "index.json").write_text("{}")
            blobs = cache / "blobs/sha256"
            blobs.mkdir(parents=True)
            self.assertIsNone(benchmark.blob_bytes(cache))
            (blobs / "abc").write_bytes(b"123")
            (blobs / "def").write_bytes(b"4567")
            self.assertEqual(benchmark.blob_bytes(cache), 7)

    def test_timeouts_and_interrupts_are_explicit(self):
        for error, status in (
            (subprocess.TimeoutExpired("docker", 900), "timeout"),
            (KeyboardInterrupt(), "interrupted"),
        ):
            with tempfile.TemporaryDirectory() as temp, mock.patch.object(
                benchmark.subprocess, "run", side_effect=error
            ) as run, contextlib.redirect_stdout(io.StringIO()):
                _, result, _ = benchmark.measured_build(
                    ["docker"], benchmark.Budget(), Path(temp) / "build.log"
                )
                self.assertEqual(result, status)
                self.assertLessEqual(run.call_args.kwargs["timeout"], 900)

    def test_total_budget_clamps_timeout_and_stops_before_spawn(self):
        with mock.patch.object(benchmark.time, "monotonic", side_effect=[0, 3590, 3601]):
            budget = benchmark.Budget()
            self.assertEqual(budget.remaining(900), 10)
            with self.assertRaisesRegex(benchmark.BenchmarkError, "budget exhausted"):
                budget.remaining(900)
        budget = mock.Mock()
        budget.remaining.side_effect = benchmark.BenchmarkError("budget exhausted")
        with mock.patch.object(benchmark.subprocess, "run") as run:
            with self.assertRaises(benchmark.BenchmarkError):
                benchmark.capture(["docker"], budget)
            run.assert_not_called()


class OrchestrationTests(unittest.TestCase):
    def test_twelve_sequential_fresh_builders_isolated_exports_and_cleanup(self):
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(
            benchmark, "capture", return_value="BuildKit fixture"
        ) as capture, mock.patch.object(
            benchmark, "measured_build", return_value=(1.0, 0, "")
        ) as build, mock.patch.object(
            benchmark.subprocess, "run"
        ) as cleanup, contextlib.redirect_stdout(
            io.StringIO()
        ):
            workspace = Path(temp)
            context = workspace / "context"
            sources = fixture(context)
            original = [source.read_text() for source in sources]
            rows = []
            benchmark.compare(context, workspace, benchmark.Budget(), rows)
            self.assertEqual(len(rows), 12)
            self.assertEqual(build.call_count, 12)
            builders = [
                command[command.index("--name") + 1]
                for command in (call.args[0] for call in capture.call_args_list)
                if command[2] == "create"
            ]
            self.assertEqual(len(set(builders)), 12)
            for command in (call.args[0] for call in capture.call_args_list):
                self.assertNotIn("--use", command)
            self.assertEqual(cleanup.call_count, 12)
            for call, builder in zip(cleanup.call_args_list, builders):
                self.assertEqual(call.args[0], ["docker", "buildx", "rm", "--force", builder])
                self.assertEqual(call.kwargs["timeout"], 30)
            exports = [
                arg
                for call in build.call_args_list
                for arg in call.args[0]
                if arg.startswith("type=local,dest=")
            ]
            self.assertEqual(len(set(exports)), 4)
            self.assertEqual([source.read_text() for source in sources], original)

    def test_failed_build_stops_without_retry_and_cleans_builder(self):
        for status in (1, "timeout", "interrupted"):
            with tempfile.TemporaryDirectory() as temp, mock.patch.object(
                benchmark, "capture", return_value=""
            ), mock.patch.object(
                benchmark, "measured_build", return_value=(1.0, status, "")
            ) as build, mock.patch.object(
                benchmark.subprocess, "run"
            ) as cleanup, contextlib.redirect_stdout(
                io.StringIO()
            ):
                workspace = Path(temp)
                context = workspace / "context"
                fixture(context)
                rows = []
                with self.assertRaisesRegex(benchmark.BenchmarkError, "Build stopped"):
                    benchmark.compare(context, workspace, benchmark.Budget(), rows)
                self.assertEqual(build.call_count, 1)
                self.assertEqual(cleanup.call_count, 1)
                self.assertEqual(rows[0]["exit"], status)

    def test_partial_create_failure_still_cleans_owned_builder(self):
        with mock.patch.object(
            benchmark, "capture", side_effect=subprocess.TimeoutExpired("create", 60)
        ), mock.patch.object(benchmark.subprocess, "run") as cleanup:
            with self.assertRaises(subprocess.TimeoutExpired):
                benchmark.run_probe(
                    Path("/context"),
                    Path("/nonexistent"),
                    "frontend",
                    "min",
                    "cold",
                    benchmark.Budget(),
                    [],
                )
            self.assertTrue(cleanup.call_args.args[0][-1].startswith("meridian-cache-bench-"))

    def test_cleanup_failure_stops_instead_of_leaking_more_builders(self):
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(
            benchmark, "capture", return_value=""
        ), mock.patch.object(
            benchmark, "measured_build", return_value=(1.0, 0, "")
        ) as build, mock.patch.object(
            benchmark.subprocess, "run", side_effect=subprocess.TimeoutExpired("rm", 30)
        ), contextlib.redirect_stdout(
            io.StringIO()
        ):
            workspace = Path(temp)
            fixture(workspace / "context")
            with self.assertRaisesRegex(benchmark.BenchmarkError, "Owned builder cleanup failed"):
                benchmark.compare(workspace / "context", workspace, benchmark.Budget(), [])
            self.assertEqual(build.call_count, 1)

    def test_dirty_cold_export_is_rejected_before_builder_creation(self):
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(
            benchmark, "capture"
        ) as capture:
            workspace = Path(temp)
            (workspace / "frontend-min").mkdir()
            with self.assertRaisesRegex(benchmark.BenchmarkError, "must be absent"):
                benchmark.run_probe(
                    workspace, workspace, "frontend", "min", "cold", benchmark.Budget(), []
                )
            capture.assert_not_called()

    def test_changed_fixture_is_restored_on_failure(self):
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(
            benchmark, "run_probe", side_effect=[None, None, benchmark.BenchmarkError("failure")]
        ):
            context = Path(temp)
            sources = fixture(context)
            original = sources[0].read_text()
            with self.assertRaises(benchmark.BenchmarkError):
                benchmark.compare(context, context, benchmark.Budget(), [])
            self.assertEqual(sources[0].read_text(), original)

    def test_main_cleans_temporary_context_and_reports_failure(self):
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(
            benchmark, "TEMP_ROOT", Path(temp)
        ), mock.patch.object(benchmark, "snapshot", return_value="head"), mock.patch.object(
            benchmark, "capture", return_value="version"
        ), mock.patch.object(
            benchmark, "compare", side_effect=benchmark.BenchmarkError("failed")
        ), contextlib.redirect_stdout(
            io.StringIO()
        ), contextlib.redirect_stderr(
            io.StringIO()
        ):
            self.assertEqual(benchmark.main([]), 1)
            self.assertEqual(list(Path(temp).iterdir()), [])

    def test_help_does_not_invoke_docker(self):
        with mock.patch.object(benchmark.subprocess, "run") as run, contextlib.redirect_stdout(
            io.StringIO()
        ):
            with self.assertRaises(SystemExit) as result:
                benchmark.main(["--help"])
            self.assertEqual(result.exception.code, 0)
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
