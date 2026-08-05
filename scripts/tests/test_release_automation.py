import base64
import io
import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock
from urllib.parse import urlsplit


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import release_automation as release


REPOSITORY = "meridian-project/Meridian"
API = f"https://api.github.com/repos/{REPOSITORY}"
SHA = "a" * 40
CHANGELOG = "# Meridian 1.7.5-beta\n\nExact notes.\n"


def encoded_changelog(text=CHANGELOG):
    encoded = base64.b64encode(text.encode()).decode()
    return {"type": "file", "encoding": "base64", "content": encoded}


def pull(number=12, version="1.7.5-beta", body=CHANGELOG, merged=True, sha=SHA):
    return {
        "number": number,
        "state": "closed" if merged else "open",
        "merged": merged,
        "merge_commit_sha": sha,
        "title": f"Release Meridian {version}",
        "body": body,
        "base": {"ref": "main"},
        "head": {"ref": "dev", "repo": {"full_name": REPOSITORY}},
    }


class FakeTransport:
    def __init__(self):
        self.responses = []
        self.calls = []

    def add(self, method, path, data=None, status=200, headers=None):
        body = b"" if data is None else json.dumps(data).encode()
        self.responses.append((method, path, release.Response(status, headers or {}, body)))

    def __call__(self, method, url, headers, body, timeout):
        self.calls.append(
            {
                "method": method,
                "path": url.removeprefix(API),
                "headers": headers,
                "payload": json.loads(body) if body else None,
                "timeout": timeout,
            }
        )
        if not self.responses:
            raise AssertionError(f"unexpected request: {method} {url}")
        expected_method, expected_path, response = self.responses.pop(0)
        self.assert_request(method, url, expected_method, expected_path)
        return response

    @staticmethod
    def assert_request(method, url, expected_method, expected_path):
        if method != expected_method or url != API + expected_path:
            raise AssertionError(
                f"expected {expected_method} {expected_path}, got {method} {url.removeprefix(API)}"
            )

    def assert_done(self):
        if self.responses:
            raise AssertionError(f"unused responses: {self.responses}")


class VersionTests(unittest.TestCase):
    def test_strict_version_and_numeric_latest(self):
        tags = [
            {"name": "1.9.9-beta"},
            {"name": "1.10.0-beta"},
            {"name": "v9.0.0-beta"},
            {"name": "2.0.0"},
            {"name": "1.11.0-rc"},
            {"name": "01.12.0-beta"},
        ]
        self.assertEqual(str(release.latest_version(tags)), "1.10.0-beta")

    def test_all_bumps_reset_expected_components(self):
        version = release.Version.parse("1.7.9-beta")
        self.assertEqual(str(version.bump("patch")), "1.7.10-beta")
        self.assertEqual(str(version.bump("minor")), "1.8.0-beta")
        self.assertEqual(str(version.bump("major")), "2.0.0-beta")

    def test_invalid_and_missing_base_fail(self):
        for value in ("v1.2.3-beta", "1.2.3", "01.2.3-beta", "1.2.3-BETA"):
            with self.subTest(value=value), self.assertRaises(release.ReleaseError):
                release.Version.parse(value)
        with self.assertRaisesRegex(release.ReleaseError, "no existing"):
            release.latest_version([{"name": "v1.0.0-beta"}])

    def test_exact_title_generation_and_parsing(self):
        self.assertEqual(release.release_title("1.2.3-beta"), "Release Meridian 1.2.3-beta")
        self.assertEqual(release.parse_release_title("Release Meridian 1.2.3-beta"), "1.2.3-beta")
        for title in (
            "Release 1.2.3-beta",
            "Release Meridian v1.2.3-beta",
            "Release Meridian 1.2.3-beta ",
        ):
            with self.subTest(title=title), self.assertRaises(release.ReleaseError):
                release.parse_release_title(title)

    def test_changelog_validation_preserves_exact_text(self):
        wrapped = encoded_changelog()
        wrapped["content"] = "\n".join(
            wrapped["content"][index : index + 8] for index in range(0, len(wrapped["content"]), 8)
        )
        self.assertEqual(release.decode_changelog(wrapped, "1.7.5-beta"), CHANGELOG)
        invalid = [
            {},
            {"type": "dir", "encoding": "base64", "content": ""},
            encoded_changelog(""),
            encoded_changelog("# Meridian 1.7.4-beta\n"),
            {"type": "file", "encoding": "base64", "content": base64.b64encode(b"\xff").decode()},
        ]
        for content in invalid:
            with self.subTest(content=content), self.assertRaises(release.ReleaseError):
                release.decode_changelog(content, "1.7.5-beta")


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.transport = FakeTransport()
        self.client = release.GitHubClient(REPOSITORY, "secret", self.transport)

    def test_pagination_follows_repository_scoped_next_link(self):
        next_url = API + "/tags?per_page=100&page=2"
        self.transport.add(
            "GET",
            "/tags?per_page=100",
            [{"name": "1.0.0-beta"}],
            headers={"Link": f'<{next_url}>; rel="next"'},
        )
        self.transport.add("GET", "/tags?per_page=100&page=2", [{"name": "1.1.0-beta"}])
        self.assertEqual(len(self.client.paginate("/tags?per_page=100")), 2)
        self.transport.assert_done()

    def test_malformed_or_external_pagination_fails(self):
        self.transport.add("GET", "/tags", [], headers={"Link": "not a link"})
        with self.assertRaisesRegex(release.ReleaseError, "malformed"):
            self.client.paginate("/tags")
        self.transport.add(
            "GET", "/tags", [], headers={"Link": '<https://evil.invalid/tags>; rel="next"'}
        )
        with self.assertRaisesRegex(release.ReleaseError, "escaped"):
            self.client.paginate("/tags")

    def test_api_error_is_safe_and_status_aware(self):
        self.transport.add("GET", "/tags", {"message": "denied"}, status=403)
        with self.assertRaises(release.GitHubError) as raised:
            self.client.request("GET", "/tags")
        self.assertEqual(raised.exception.status, 403)
        self.assertNotIn("secret", str(raised.exception))


class PromotionTests(unittest.TestCase):
    def setUp(self):
        self.transport = FakeTransport()
        self.client = release.GitHubClient(REPOSITORY, "secret", self.transport)

    def test_numeric_newest_strict_beta_is_accepted_with_gets_only(self):
        self.transport.add(
            "GET",
            "/tags?per_page=100",
            [
                {"name": "1.9.9-beta"},
                {"name": "1.10.0-beta"},
                {"name": "v2.0.0-beta"},
                {"name": "2.0.0"},
                {"name": "01.11.0-beta"},
            ],
        )

        self.assertEqual(release.verify_promotion(self.client, "1.10.0-beta"), "1.10.0-beta")
        self.assertTrue(all(call["method"] == "GET" for call in self.transport.calls))
        self.transport.assert_done()

    def test_stale_candidate_is_rejected_with_gets_only(self):
        self.transport.add(
            "GET",
            "/tags?per_page=100",
            [{"name": "1.9.9-beta"}, {"name": "1.10.0-beta"}],
        )

        with self.assertRaisesRegex(
            release.ReleaseError,
            r"promotion candidate 1\.9\.9-beta is stale; newest strict beta tag is 1\.10\.0-beta",
        ):
            release.verify_promotion(self.client, "1.9.9-beta")
        self.assertTrue(all(call["method"] == "GET" for call in self.transport.calls))
        self.transport.assert_done()


class PrepareTests(unittest.TestCase):
    def setUp(self):
        self.transport = FakeTransport()
        self.client = release.GitHubClient(REPOSITORY, "secret", self.transport)

    def queue_reads(self, pulls=None, ahead_by=1):
        self.transport.add("GET", "/tags?per_page=100", [{"name": "1.7.4-beta"}])
        self.transport.add("GET", "/compare/main...dev", {"ahead_by": ahead_by})
        self.transport.add(
            "GET", "/contents/docs/changelogs/Update-1.7.5-beta.md?ref=dev", encoded_changelog()
        )
        self.transport.add(
            "GET",
            "/pulls?state=open&base=main&head=meridian-project%3Adev&per_page=100",
            pulls or [],
        )

    def test_create_exact_release_pr(self):
        self.queue_reads()
        self.transport.add("POST", "/pulls", {"number": 12}, status=201)
        self.assertEqual(release.prepare(self.client, "patch"), "1.7.5-beta")
        call = self.transport.calls[-1]
        self.assertEqual(
            call["payload"],
            {
                "title": "Release Meridian 1.7.5-beta",
                "body": CHANGELOG,
                "base": "main",
                "head": "dev",
            },
        )
        self.transport.assert_done()

    def test_update_single_stale_release_pr(self):
        existing = pull(merged=False)
        existing["title"] = "old"
        existing["body"] = "old"
        self.queue_reads([existing])
        self.transport.add("PATCH", "/pulls/12", {"number": 12})
        release.prepare(self.client, "patch")
        self.assertEqual(
            self.transport.calls[-1]["payload"],
            {"title": "Release Meridian 1.7.5-beta", "body": CHANGELOG},
        )

    def test_no_diff_refuses_before_changelog_or_mutation(self):
        self.transport.add("GET", "/tags?per_page=100", [{"name": "1.7.4-beta"}])
        self.transport.add("GET", "/compare/main...dev", {"ahead_by": 0})
        with self.assertRaisesRegex(release.ReleaseError, "no commits ahead"):
            release.prepare(self.client, "patch")
        self.transport.assert_done()
        self.assertEqual([call["method"] for call in self.transport.calls], ["GET", "GET"])

    def test_duplicate_matching_prs_refuse_without_mutation(self):
        self.queue_reads([pull(12, merged=False), pull(13, merged=False)])
        with self.assertRaisesRegex(release.ReleaseError, "multiple"):
            release.prepare(self.client, "patch")
        self.assertTrue(all(call["method"] == "GET" for call in self.transport.calls))


class PublishTests(unittest.TestCase):
    def setUp(self):
        self.transport = FakeTransport()
        self.client = release.GitHubClient(REPOSITORY, "secret", self.transport)

    def queue_publish_validation(self, pr=None, tags=None):
        self.transport.add("GET", "/pulls/12", pr or pull())
        self.transport.add(
            "GET", f"/contents/docs/changelogs/Update-1.7.5-beta.md?ref={SHA}", encoded_changelog()
        )
        self.transport.add("GET", "/tags?per_page=100", tags or [{"name": "1.7.4-beta"}])

    def test_create_lightweight_tag_then_release(self):
        self.queue_publish_validation()
        self.transport.add("GET", "/git/ref/tags/1.7.5-beta", {"message": "missing"}, status=404)
        self.transport.add("POST", "/git/refs", {"ref": "refs/tags/1.7.5-beta"}, status=201)
        self.transport.add(
            "GET", "/git/ref/tags/1.7.5-beta", {"object": {"type": "commit", "sha": SHA}}
        )
        self.transport.add("GET", "/releases/tags/1.7.5-beta", {"message": "missing"}, status=404)
        self.transport.add("POST", "/releases", {"id": 8}, status=201)
        self.assertEqual(release.publish(self.client, 12), "1.7.5-beta")
        writes = [call for call in self.transport.calls if call["method"] == "POST"]
        self.assertEqual(writes[0]["payload"], {"ref": "refs/tags/1.7.5-beta", "sha": SHA})
        self.assertEqual(
            writes[1]["payload"],
            {
                "tag_name": "1.7.5-beta",
                "name": "1.7.5-beta",
                "body": CHANGELOG,
                "draft": False,
                "prerelease": True,
                "generate_release_notes": False,
            },
        )

    def test_existing_annotated_tag_and_release_are_reconciled(self):
        self.queue_publish_validation(tags=[{"name": "1.7.4-beta"}, {"name": "1.7.5-beta"}])
        tag_sha = "b" * 40
        self.transport.add(
            "GET", "/git/ref/tags/1.7.5-beta", {"object": {"type": "tag", "sha": tag_sha}}
        )
        self.transport.add(
            "GET", f"/git/tags/{tag_sha}", {"object": {"type": "commit", "sha": SHA}}
        )
        self.transport.add(
            "GET",
            "/releases/tags/1.7.5-beta",
            {
                "id": 8,
                "tag_name": "1.7.5-beta",
                "name": "wrong",
                "body": "wrong",
                "draft": True,
                "prerelease": False,
            },
        )
        self.transport.add("PATCH", "/releases/8", {"id": 8})
        release.publish(self.client, 12)
        self.assertEqual(
            self.transport.calls[-1]["payload"],
            {
                "tag_name": "1.7.5-beta",
                "name": "1.7.5-beta",
                "body": CHANGELOG,
                "draft": False,
                "prerelease": False,
            },
        )

    def test_exact_existing_release_is_noop(self):
        self.queue_publish_validation()
        self.transport.add(
            "GET", "/git/ref/tags/1.7.5-beta", {"object": {"type": "commit", "sha": SHA}}
        )
        existing = {"id": 8, **release._canonical_release("1.7.5-beta", CHANGELOG)}
        self.transport.add("GET", "/releases/tags/1.7.5-beta", existing)
        release.publish(self.client, 12)
        self.assertTrue(all(call["method"] == "GET" for call in self.transport.calls))

    def test_exact_existing_promoted_release_is_noop(self):
        self.queue_publish_validation()
        self.transport.add(
            "GET", "/git/ref/tags/1.7.5-beta", {"object": {"type": "commit", "sha": SHA}}
        )
        existing = {"id": 8, **release._canonical_release("1.7.5-beta", CHANGELOG)}
        existing["prerelease"] = False
        self.transport.add("GET", "/releases/tags/1.7.5-beta", existing)

        release.publish(self.client, 12)

        self.assertTrue(all(call["method"] == "GET" for call in self.transport.calls))

    def test_tag_create_race_is_reread(self):
        self.queue_publish_validation()
        self.transport.add("GET", "/git/ref/tags/1.7.5-beta", {"message": "missing"}, status=404)
        self.transport.add("POST", "/git/refs", {"message": "already exists"}, status=422)
        self.transport.add(
            "GET", "/git/ref/tags/1.7.5-beta", {"object": {"type": "commit", "sha": SHA}}
        )
        self.transport.add("GET", "/releases/tags/1.7.5-beta", {"message": "missing"}, status=404)
        self.transport.add("POST", "/releases", {"id": 8}, status=201)
        release.publish(self.client, 12)

    def test_mismatched_tag_refuses_before_release(self):
        self.queue_publish_validation()
        self.transport.add(
            "GET", "/git/ref/tags/1.7.5-beta", {"object": {"type": "commit", "sha": "b" * 40}}
        )
        with self.assertRaisesRegex(release.ReleaseError, "does not resolve"):
            release.publish(self.client, 12)
        self.assertFalse(any("/releases" in call["path"] for call in self.transport.calls))

    def test_newer_tag_makes_finalizer_stale_before_mutation(self):
        self.queue_publish_validation(tags=[{"name": "1.7.4-beta"}, {"name": "1.8.0-beta"}])
        with self.assertRaisesRegex(release.ReleaseError, "stale"):
            release.publish(self.client, 12)
        self.assertTrue(all(call["method"] == "GET" for call in self.transport.calls))

    def test_invalid_pr_title_or_body_refuses_before_mutation(self):
        invalid_title = pull()
        invalid_title["title"] = "Release 1.7.5-beta"
        self.transport.add("GET", "/pulls/12", invalid_title)
        with self.assertRaises(release.ReleaseError):
            release.publish(self.client, 12)
        invalid_body = pull(body="edited")
        self.transport.add("GET", "/pulls/12", invalid_body)
        self.transport.add(
            "GET", f"/contents/docs/changelogs/Update-1.7.5-beta.md?ref={SHA}", encoded_changelog()
        )
        with self.assertRaisesRegex(release.ReleaseError, "body"):
            release.publish(self.client, 12)

    def test_release_create_race_is_updated(self):
        self.queue_publish_validation()
        self.transport.add(
            "GET", "/git/ref/tags/1.7.5-beta", {"object": {"type": "commit", "sha": SHA}}
        )
        self.transport.add("GET", "/releases/tags/1.7.5-beta", {"message": "missing"}, status=404)
        self.transport.add("POST", "/releases", {"message": "race"}, status=422)
        self.transport.add(
            "GET",
            "/releases/tags/1.7.5-beta",
            {
                "id": 8,
                "tag_name": "1.7.5-beta",
                "name": "old",
                "body": "old",
                "draft": True,
                "prerelease": False,
            },
        )
        self.transport.add("PATCH", "/releases/8", {"id": 8})
        release.publish(self.client, 12)
        self.assertIs(self.transport.calls[-1]["payload"]["prerelease"], False)


class CliTests(unittest.TestCase):
    def test_missing_token_fails_without_transport(self):
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(
            release, "urllib_transport", side_effect=AssertionError("network called")
        ):
            self.assertEqual(
                release.main(["prepare", "--repository", REPOSITORY, "--bump", "patch"]), 1
            )

    def test_verify_promotion_stale_candidate_exits_nonzero_without_writes(self):
        transport = FakeTransport()
        client = release.GitHubClient(REPOSITORY, "secret", transport)
        transport.add(
            "GET",
            "/tags?per_page=100",
            [{"name": "1.7.5-beta"}, {"name": "1.8.0-beta"}],
        )
        stderr = io.StringIO()

        with mock.patch.object(release, "GitHubClient", return_value=client), mock.patch.dict(
            os.environ, {"RELEASE_TOKEN": "secret"}, clear=True
        ), mock.patch("sys.stderr", stderr):
            result = release.main(
                [
                    "verify-promotion",
                    "--repository",
                    REPOSITORY,
                    "--version",
                    "1.7.5-beta",
                ]
            )

        self.assertEqual(result, 1)
        self.assertIn("1.7.5-beta is stale", stderr.getvalue())
        self.assertIn("1.8.0-beta", stderr.getvalue())
        self.assertTrue(all(call["method"] == "GET" for call in transport.calls))
        transport.assert_done()


if __name__ == "__main__":
    unittest.main()
