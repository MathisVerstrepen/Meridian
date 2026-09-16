"""Policy assertions supplement actionlint without YAML 1.1's `on` coercion."""

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
TAG_ONLY = "github.event_name == 'push' && startsWith(github.ref, 'refs/tags/')"
CACHE = (
    "type=registry,ref=ghcr.io/${{ steps.cache.outputs.repository }}/${{ matrix.image }}:buildcache"
)
IMAGES = {
    "frontend": "./docker/ui.Dockerfile",
    "backend": "./docker/api.Dockerfile",
    "browser-service": "./docker/browser-service.Dockerfile",
    "sandbox-manager": "./docker/sandbox-manager.Dockerfile",
    "sandbox-python": "./docker/sandbox-python.Dockerfile",
}


def action(job, name):
    matches = [step for step in job["steps"] if step.get("uses", "").startswith(name + "@")]
    if len(matches) != 1:
        raise AssertionError(f"Expected exactly one {name}: {matches}")
    return matches[0]


def named(job, name):
    return next(step for step in job["steps"] if step["name"] == name)


class DockerPublishPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = (ROOT / ".github/workflows/docker-publish.yml").read_text()
        # BaseLoader preserves every scalar as a string, including `on` and booleans.
        cls.workflow = yaml.load(cls.text, Loader=yaml.BaseLoader)
        cls.jobs = cls.workflow["jobs"]

    def test_triggers_serialization_and_permissions(self):
        self.assertEqual(
            self.workflow["on"],
            {"push": {"tags": ["*.*.*-beta"]}, "pull_request": {"branches": ["main"]}},
        )
        self.assertEqual(self.workflow["permissions"], {"contents": "read"})
        self.assertEqual(
            self.workflow["concurrency"],
            {
                "group": "${{ startsWith(github.ref, 'refs/tags/') && "
                "format('meridian-release-{0}', github.repository) || "
                "format('docker-publish-{0}', github.ref) }}",
                "cancel-in-progress": "${{ !startsWith(github.ref, 'refs/tags/') }}",
            },
        )
        self.assertEqual(
            set(self.jobs),
            {"lint", "build-pr", "build-and-push", "promote-images", "promote-release"},
        )
        for job in self.jobs.values():
            permissions = job.get("permissions", self.workflow["permissions"])
            if "write" in permissions.values():
                self.assertEqual(job["if"], TAG_ONLY)

    def test_five_way_matrix_parity_and_check_names(self):
        pr = self.jobs["build-pr"]
        tag = self.jobs["build-and-push"]
        self.assertEqual(pr["name"], "Build ${{ matrix.name }} image")
        self.assertEqual(tag["name"], "Publish ${{ matrix.name }} image")
        self.assertEqual(pr["strategy"], tag["strategy"])
        for job in (pr, tag):
            self.assertEqual(job["needs"], "lint")
            self.assertEqual(job["strategy"]["fail-fast"], "false")
            self.assertEqual(job["strategy"]["max-parallel"], "5")
            matrix = job["strategy"]["matrix"]["include"]
            self.assertEqual(len(matrix), 5)
            self.assertEqual({row["image"]: row["dockerfile"] for row in matrix}, IMAGES)
            for row in matrix:
                self.assertEqual(row["name"], row["image"])
                self.assertEqual(row["frontend"], str(row["image"] == "frontend").lower())
                self.assertNotIn("cache-scope", row)

    def test_pr_is_read_only_and_has_no_credential_or_export_path(self):
        pr = self.jobs["build-pr"]
        self.assertEqual(pr["if"], "github.event_name == 'pull_request'")
        self.assertEqual(pr["permissions"], {"contents": "read", "packages": "read"})
        for job in (pr, self.jobs["lint"]):
            self.assertEqual(
                action(job, "actions/checkout")["with"]["persist-credentials"], "false"
            )
            for step in job["steps"]:
                self.assertNotIn("docker/login-action", step.get("uses", ""))
                self.assertNotIn("cache-to", step.get("with", {}))
        build = action(pr, "docker/build-push-action")["with"]
        self.assertEqual(build["push"], "false")
        self.assertNotIn("secrets", build)
        self.assertNotIn("outputs", build)

    def test_only_tag_build_exports_shared_trusted_cache(self):
        tag = self.jobs["build-and-push"]
        self.assertEqual(tag["if"], TAG_ONLY)
        self.assertEqual(tag["permissions"], {"contents": "read", "packages": "write"})
        login = action(tag, "docker/login-action")
        self.assertEqual(login["if"], "startsWith(github.ref, 'refs/tags/')")
        self.assertEqual(login["with"]["password"], "${{ secrets.GITHUB_TOKEN }}")
        for job in (self.jobs["build-pr"], tag):
            cache = named(job, "Set trusted cache repository")
            self.assertEqual(cache["id"], "cache")
            self.assertEqual(cache["env"], {"BASE_REPOSITORY": "${{ github.repository }}"})
            self.assertEqual(
                cache["run"], 'echo "repository=${BASE_REPOSITORY,,}" >> "$GITHUB_OUTPUT"'
            )
            self.assertEqual(action(job, "docker/build-push-action")["with"]["cache-from"], CACHE)
        build = action(tag, "docker/build-push-action")["with"]
        self.assertEqual(build["push"], "true")
        self.assertEqual(
            build["cache-to"], CACHE + ",mode=max,oci-mediatypes=true,image-manifest=true"
        )
        self.assertNotIn("type=gha", self.text)
        self.assertNotIn("ignore-error", self.text)
        self.assertNotIn("github.head_ref", self.text)
        self.assertNotIn("head.repo", self.text)

    def test_metadata_and_frontend_arguments_remain_unchanged(self):
        for job in (self.jobs["build-pr"], self.jobs["build-and-push"]):
            self.assertEqual(action(job, "actions/checkout")["uses"], "actions/checkout@v4")
            self.assertEqual(
                action(job, "docker/setup-buildx-action")["uses"], "docker/setup-buildx-action@v3"
            )
            meta = action(job, "docker/metadata-action")
            self.assertEqual(meta["uses"], "docker/metadata-action@v5")
            self.assertEqual(
                meta["with"]["tags"].splitlines(),
                [
                    "type=ref,event=branch",
                    "type=semver,pattern={{version}}",
                    "type=semver,pattern={{major}}.{{minor}}",
                    "type=raw,value=latest,enable={{is_default_branch}}",
                ],
            )
            build = action(job, "docker/build-push-action")
            self.assertEqual(build["uses"], "docker/build-push-action@v5")
            self.assertEqual(
                build["with"]["build-args"],
                "${{ matrix.frontend && format('NUXT_PUBLIC_VERSION={0}', "
                "steps.meta.outputs.version) || '' }}",
            )

    def test_release_guards_and_promotion_order(self):
        for job_id in ("lint", "promote-images", "promote-release"):
            guard = named(self.jobs[job_id], "Validate release tag")
            self.assertEqual(guard["env"]["RELEASE_VERSION"], "${{ github.ref_name }}")
            self.assertIn(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)-beta$", guard["run"])
            self.assertIn("exit 1", guard["run"])
        lint = self.jobs["lint"]
        newest = named(lint, "Verify release is newest")
        self.assertEqual(newest["if"], "startsWith(github.ref, 'refs/tags/')")
        self.assertIn("verify-promotion", newest["run"])
        self.assertLess(
            lint["steps"].index(newest), lint["steps"].index(named(lint, "Run backend linters"))
        )
        images = self.jobs["promote-images"]
        release = self.jobs["promote-release"]
        self.assertEqual(images["needs"], "build-and-push")
        self.assertEqual(release["needs"], "promote-images")
        for job in (images, release):
            self.assertEqual(job["if"], TAG_ONLY)
            self.assertEqual(
                action(job, "actions/checkout")["with"],
                {"ref": "main", "persist-credentials": "false"},
            )
        promote = named(images, "Prevalidate and promote image manifests")["run"]
        self.assertIn(
            "images=(frontend backend browser-service sandbox-manager sandbox-python)", promote
        )
        self.assertIn('source="$REGISTRY/$repository/$image:$RELEASE_VERSION"', promote)
        self.assertLess(promote.index("done"), promote.index("verify-promotion"))
        self.assertLess(promote.index("verify-promotion"), promote.index("imagetools create"))
        self.assertIn('source="${sources[$index]%:$RELEASE_VERSION}@${digests[$index]}"', promote)
        promote = named(release, "Wait for and promote GitHub Release")["run"]
        self.assertEqual(promote.count("verify-promotion"), 2)
        self.assertLess(promote.index("verify-promotion"), promote.index("gh release view"))
        self.assertLess(promote.rindex("verify-promotion"), promote.index("gh release edit"))
        self.assertIn("--prerelease=false --latest", promote)

    def test_policy_tests_run_after_yaml_dependency_install(self):
        steps = self.jobs["lint"]["steps"]
        self.assertLess(
            steps.index(named(self.jobs["lint"], "Install Python dependencies")),
            steps.index(named(self.jobs["lint"], "Test Docker workflow policy")),
        )


if __name__ == "__main__":
    unittest.main()
