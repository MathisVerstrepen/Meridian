#!/usr/bin/env python3
"""Prepare and publish Meridian releases through GitHub's REST API."""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Mapping


VERSION_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)-beta$")
TITLE_RE = re.compile(r"^Release Meridian ((?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)-beta)$")
SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
API_ROOT = "https://api.github.com"


class ReleaseError(RuntimeError):
    """Safe, operator-facing release automation failure."""


class GitHubError(ReleaseError):
    def __init__(self, method: str, path: str, status: int, detail: str = "") -> None:
        suffix = f": {detail}" if detail else ""
        super().__init__(f"GitHub {method} {path} failed with status {status}{suffix}")
        self.status = status


@dataclass(frozen=True, order=True)
class Version:
    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, value: str) -> "Version":
        match = VERSION_RE.fullmatch(value)
        if not match:
            raise ReleaseError(f"invalid strict beta version: {value!r}")
        return cls(*(int(part) for part in match.groups()))

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}-beta"

    def bump(self, kind: str) -> "Version":
        if kind == "patch":
            return Version(self.major, self.minor, self.patch + 1)
        if kind == "minor":
            return Version(self.major, self.minor + 1, 0)
        if kind == "major":
            return Version(self.major + 1, 0, 0)
        raise ReleaseError(f"unsupported bump: {kind!r}")


@dataclass(frozen=True)
class Response:
    status: int
    headers: Mapping[str, str]
    body: bytes


Transport = Callable[[str, str, Mapping[str, str], bytes | None, float], Response]


def urllib_transport(
    method: str, url: str, headers: Mapping[str, str], body: bytes | None, timeout: float
) -> Response:
    request = urllib.request.Request(url, data=body, headers=dict(headers), method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return Response(response.status, dict(response.headers), response.read())
    except urllib.error.HTTPError as exc:
        return Response(exc.code, dict(exc.headers), exc.read())


class GitHubClient:
    def __init__(
        self,
        repository: str,
        token: str,
        transport: Transport = urllib_transport,
        timeout: float = 20,
    ) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
            raise ReleaseError("repository must use owner/name format")
        if not token:
            raise ReleaseError("RELEASE_TOKEN is required")
        self.repository = repository
        self.api_url = f"{API_ROOT}/repos/{repository}"
        self.transport = transport
        self.timeout = timeout

        self.headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "meridian-release-automation",
        }

    def request(
        self, method: str, path: str, payload: Mapping[str, Any] | None = None
    ) -> tuple[Any, Mapping[str, str]]:
        url = path if path.startswith("https://") else self.api_url + path
        if not url.startswith(API_ROOT + "/"):
            raise ReleaseError("GitHub pagination URL escaped GitHub API scope")
        body = None
        headers = dict(self.headers)
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        response = self.transport(method, url, headers, body, self.timeout)
        if not 200 <= response.status < 300:
            detail = ""
            try:
                parsed = json.loads(response.body)
                if isinstance(parsed, dict) and isinstance(parsed.get("message"), str):
                    detail = parsed["message"]
            except (UnicodeDecodeError, json.JSONDecodeError):
                pass
            raise GitHubError(method, urllib.parse.urlsplit(url).path, response.status, detail)
        if not response.body:
            return None, response.headers
        try:
            return json.loads(response.body), response.headers
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ReleaseError(f"GitHub {method} response was not valid JSON") from exc

    def get_optional(self, path: str) -> Any | None:
        try:
            return self.request("GET", path)[0]
        except GitHubError as exc:
            if exc.status == 404:
                return None
            raise

    def paginate(self, path: str) -> list[Any]:
        items: list[Any] = []
        next_url: str | None = path
        seen: set[str] = set()
        while next_url:
            if next_url in seen:
                raise ReleaseError("GitHub pagination loop detected")
            seen.add(next_url)
            page, headers = self.request("GET", next_url)
            if not isinstance(page, list):
                raise ReleaseError("GitHub paginated response was not a list")
            items.extend(page)
            next_url = _next_link(headers.get("Link") or headers.get("link"))
        return items


def _next_link(header: str | None) -> str | None:
    if not header:
        return None
    for part in header.split(","):
        match = re.fullmatch(r'\s*<([^>]+)>;\s*rel="([^"]+)"\s*', part)
        if not match:
            raise ReleaseError("malformed GitHub Link pagination header")
        if match.group(2) == "next":
            return match.group(1)
    return None


def latest_version(tags: list[Any], excluded: str | None = None) -> Version:
    versions: list[Version] = []
    for tag in tags:
        if not isinstance(tag, dict) or not isinstance(tag.get("name"), str):
            raise ReleaseError("GitHub tag response contained an invalid item")
        name = tag["name"]
        if name != excluded and VERSION_RE.fullmatch(name):
            versions.append(Version.parse(name))
    if not versions:
        raise ReleaseError("no existing strict beta tag found")
    return max(versions)


def verify_promotion(client: GitHubClient, version: str) -> str:
    candidate = Version.parse(version)
    tags = client.paginate("/tags?per_page=100")
    newest = latest_version(tags)
    if candidate != newest:
        raise ReleaseError(
            f"promotion candidate {candidate} is stale; newest strict beta tag is {newest}"
        )
    return str(candidate)


def release_title(version: str) -> str:
    Version.parse(version)
    return f"Release Meridian {version}"


def parse_release_title(title: Any) -> str:
    if not isinstance(title, str):
        raise ReleaseError("release PR title is missing")
    match = TITLE_RE.fullmatch(title)
    if not match:
        raise ReleaseError("release PR title must be exactly 'Release Meridian <version>'")
    return match.group(1)


def changelog_path(version: str) -> str:
    Version.parse(version)
    return f"docs/changelogs/Update-{version}.md"


def decode_changelog(content: Any, version: str) -> str:
    if not isinstance(content, dict) or content.get("type") != "file":
        raise ReleaseError("changelog content is not a regular file")
    if content.get("encoding") != "base64" or not isinstance(content.get("content"), str):
        raise ReleaseError("changelog content is not base64 encoded")
    try:
        encoded = "".join(content["content"].split())
        raw = base64.b64decode(encoded, validate=True)
        text = raw.decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        raise ReleaseError("changelog content is not valid base64 UTF-8") from exc
    if not text:
        raise ReleaseError("changelog is empty")
    if text.splitlines()[0] != f"# Meridian {version}":
        raise ReleaseError(f"changelog first line must be exactly '# Meridian {version}'")
    return text


def _q(value: str) -> str:
    return urllib.parse.quote(value, safe="")


def _contents_path(version: str, ref: str) -> str:
    path = urllib.parse.quote(changelog_path(version), safe="/")
    return f"/contents/{path}?{urllib.parse.urlencode({'ref': ref})}"


def prepare(client: GitHubClient, bump: str, base: str = "main", head: str = "dev") -> str:
    tags = client.paginate("/tags?per_page=100")
    version = str(latest_version(tags).bump(bump))
    compare, _ = client.request("GET", f"/compare/{_q(base)}...{_q(head)}")
    if not isinstance(compare, dict) or not isinstance(compare.get("ahead_by"), int):
        raise ReleaseError("GitHub compare response is invalid")
    if compare["ahead_by"] <= 0:
        raise ReleaseError(f"{head} has no commits ahead of {base}")
    changelog = decode_changelog(client.request("GET", _contents_path(version, head))[0], version)
    owner = client.repository.split("/", 1)[0]
    query = urllib.parse.urlencode(
        {"state": "open", "base": base, "head": f"{owner}:{head}", "per_page": 100}
    )
    pulls = client.paginate(f"/pulls?{query}")
    matching = [
        pull for pull in pulls if _same_repository_pull(pull, client.repository, base, head)
    ]
    if len(matching) > 1:
        raise ReleaseError("multiple open same-repository release PRs found")
    payload = {"title": release_title(version), "body": changelog, "base": base, "head": head}
    if not matching:
        client.request("POST", "/pulls", payload)
    else:
        number = matching[0].get("number")
        if not isinstance(number, int):
            raise ReleaseError("existing release PR number is invalid")
        client.request("PATCH", f"/pulls/{number}", {"title": payload["title"], "body": changelog})
    return version


def _same_repository_pull(pull: Any, repository: str, base: str, head: str) -> bool:
    try:
        return (
            isinstance(pull, dict)
            and pull["base"]["ref"] == base
            and pull["head"]["ref"] == head
            and pull["head"]["repo"]["full_name"].lower() == repository.lower()
        )
    except (KeyError, TypeError, AttributeError):
        raise ReleaseError("GitHub pull request response is invalid")


def _read_tag_target(client: GitHubClient, version: str) -> str | None:
    ref = client.get_optional(f"/git/ref/tags/{_q(version)}")
    if ref is None:
        return None
    try:
        obj = ref["object"]
        seen: set[str] = set()
        while obj["type"] == "tag":
            sha = obj["sha"]
            if sha in seen or len(seen) >= 10:
                raise ReleaseError("annotated tag dereference loop detected")
            seen.add(sha)
            tag, _ = client.request("GET", f"/git/tags/{_q(sha)}")
            obj = tag["object"]
        if obj["type"] != "commit" or not SHA_RE.fullmatch(obj["sha"]):
            raise ReleaseError("tag does not resolve to a commit")
        return obj["sha"].lower()
    except (KeyError, TypeError) as exc:
        raise ReleaseError("GitHub tag response is invalid") from exc


def _ensure_tag(client: GitHubClient, version: str, merge_sha: str) -> None:
    target = _read_tag_target(client, version)
    if target is None:
        try:
            client.request("POST", "/git/refs", {"ref": f"refs/tags/{version}", "sha": merge_sha})
        except GitHubError as exc:
            if exc.status != 422:
                raise
        target = _read_tag_target(client, version)
    if target != merge_sha.lower():
        raise ReleaseError(f"tag {version} does not resolve to merge commit")


def _canonical_release(version: str, changelog: str) -> dict[str, Any]:
    return {
        "tag_name": version,
        "name": version,
        "body": changelog,
        "draft": False,
        "prerelease": True,
        "generate_release_notes": False,
    }


def _ensure_release(client: GitHubClient, version: str, changelog: str) -> None:
    path = f"/releases/tags/{_q(version)}"
    release = client.get_optional(path)
    canonical = _canonical_release(version, changelog)
    if release is None:
        try:
            client.request("POST", "/releases", canonical)
            return
        except GitHubError as exc:
            if exc.status != 422:
                raise
        release = client.get_optional(path)
    if not isinstance(release, dict) or not isinstance(release.get("id"), int):
        raise ReleaseError("GitHub release response is invalid")
    comparable = {key: release.get(key) for key in canonical if key != "generate_release_notes"}
    desired = {key: value for key, value in canonical.items() if key != "generate_release_notes"}
    if release.get("prerelease") is False:
        desired["prerelease"] = False
    if comparable != desired:
        client.request("PATCH", f"/releases/{release['id']}", desired)


def publish(
    client: GitHubClient, pull_request_number: int, base: str = "main", head: str = "dev"
) -> str:
    pull, _ = client.request("GET", f"/pulls/{pull_request_number}")
    if not _same_repository_pull(pull, client.repository, base, head):
        raise ReleaseError("release PR does not match trusted repository branches")
    if pull.get("merged") is not True or pull.get("state") != "closed":
        raise ReleaseError("release PR is not merged")
    merge_sha = pull.get("merge_commit_sha")
    if not isinstance(merge_sha, str) or not SHA_RE.fullmatch(merge_sha):
        raise ReleaseError("release PR merge commit SHA is invalid")
    version = parse_release_title(pull.get("title"))
    changelog = decode_changelog(
        client.request("GET", _contents_path(version, merge_sha))[0], version
    )
    pull_body = pull.get("body")
    if not isinstance(pull_body, str) or pull_body.replace("\r\n", "\n") != changelog.replace(
        "\r\n", "\n"
    ):
        raise ReleaseError("release PR body does not equal merged changelog")
    tags = client.paginate("/tags?per_page=100")
    prior = latest_version(tags, excluded=version)
    candidate = Version.parse(version)
    if candidate not in {prior.bump(kind) for kind in ("patch", "minor", "major")}:
        raise ReleaseError(f"release {version} is stale or is not a valid successor of {prior}")
    _ensure_tag(client, version, merge_sha)
    _ensure_release(client, version, changelog)
    return version


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--repository", required=True)
    prepare_parser.add_argument("--bump", required=True, choices=("patch", "minor", "major"))
    prepare_parser.add_argument("--base", default="main")
    prepare_parser.add_argument("--head", default="dev")
    publish_parser = subparsers.add_parser("publish")
    publish_parser.add_argument("--repository", required=True)
    publish_parser.add_argument("--pull-request-number", required=True, type=int)
    verify_parser = subparsers.add_parser("verify-promotion")
    verify_parser.add_argument("--repository", required=True)
    verify_parser.add_argument("--version", required=True)
    args = parser.parse_args(argv)
    try:
        client = GitHubClient(args.repository, os.environ.get("RELEASE_TOKEN", ""))
        if args.command == "prepare":
            version = prepare(client, args.bump, args.base, args.head)
        elif args.command == "publish":
            version = publish(client, args.pull_request_number)
        else:
            version = verify_promotion(client, args.version)
        print(version)
        return 0
    except ReleaseError as exc:
        print(f"release automation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
