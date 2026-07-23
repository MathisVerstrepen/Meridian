from browser_service.app.diagnostics import response_diagnostics, sanitize_url


def test_diagnostics_never_include_arbitrary_body() -> None:
    body = "account@example.com cookie=secret ordinary account text"
    result = response_diagnostics(
        requested_url="https://example.com",
        status_code=403,
        decision="stop",
        response_url="https://example.com/private?token=secret",
        headers={"set-cookie": "secret", "server": "edge"},
        body=body,
    )
    assert result["body_markers"] == []
    assert body not in repr(result)
    assert "set-cookie" not in repr(result)


def test_browser_marker_is_hostname_independent_and_body_safe() -> None:
    result = response_diagnostics(
        requested_url="https://request.example/article",
        status_code=401,
        decision="stop",
        response_url="https://redirect.example/challenge",
        headers={},
        body="Please enable JS and disable any ad blocker private@example.com",
    )
    assert result["body_markers"] == ["browser_challenge"]
    assert "private@example.com" not in repr(result)


def test_cmsg_marker_requires_lambda_header() -> None:
    without_header = response_diagnostics(
        requested_url="https://example.com",
        status_code=403,
        decision="stop",
        response_url="https://example.com",
        headers={"server": "Varnish"},
        body="<p id='cmsg'>Access denied</p>",
    )
    with_header = response_diagnostics(
        requested_url="https://example.com",
        status_code=403,
        decision="stop",
        response_url="https://example.com",
        headers={"x-cache": "LambdaGeneratedResponse from cloudfront"},
        body="<p id='cmsg'>Access denied</p>",
    )
    assert without_header["body_markers"] == []
    assert with_header["body_markers"] == ["browser_challenge"]


def test_requested_and_redirect_capability_paths_are_redacted() -> None:
    requested_capability = "AbCdEfGhIjKlMnOpQrStUvW9"
    redirect_capability = "ZyXwVuTsRqPoNmLkJiHgFeDcBa9876543210zyxwvutsrqponmlkjihgfed"
    requested_url = f"https://example.com/callback/{requested_capability}"
    redirect_url = f"https://redirect.example/access/{redirect_capability}"

    assert sanitize_url(requested_url) == "https://example.com/callback/[redacted]"
    result = response_diagnostics(
        requested_url=requested_url,
        status_code=302,
        decision="stop",
        response_url=redirect_url,
        headers={"location": redirect_url},
        body="",
    )
    assert result["url"] == "https://redirect.example/access/[redacted]"
    assert result["headers"] == {"location": "https://redirect.example/access/[redacted]"}
    assert requested_capability not in repr(result)
    assert redirect_capability not in repr(result)
