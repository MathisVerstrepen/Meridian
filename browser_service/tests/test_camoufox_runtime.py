import asyncio

from browser_service.app import camoufox_runtime


def test_minimal_child_environment_is_strict(monkeypatch) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", "api-secret")
    monkeypatch.setenv("LINK_EXTRACTION_BROWSER_SERVICE_TOKEN", "service-secret")
    monkeypatch.setenv("LINK_EXTRACTION_BROWSER_PROXY_URL", "proxy-secret")
    for index, key in enumerate(camoufox_runtime.CHILD_ENV_KEYS):
        monkeypatch.setenv(key, f"sentinel-{index}")
    child = camoufox_runtime.minimal_child_environment()
    assert set(child) == set(camoufox_runtime.CHILD_ENV_KEYS)
    assert child == camoufox_runtime.CHILD_ENVIRONMENT
    assert child is not camoufox_runtime.CHILD_ENVIRONMENT
    assert all(not value.startswith("sentinel-") for value in child.values())
    assert not (
        {
            "JWT_SECRET_KEY",
            "LINK_EXTRACTION_BROWSER_SERVICE_TOKEN",
            "LINK_EXTRACTION_BROWSER_PROXY_URL",
        }
        & set(child)
    )
    assert "api-secret" not in repr(child)
    assert child["FONTCONFIG_FILE"] == "/etc/browser-service/fonts.conf"
    child["HOME"] = "mutated"
    assert camoufox_runtime.minimal_child_environment() == camoufox_runtime.CHILD_ENVIRONMENT


def test_proxy_parser_preserves_paired_percent_decoded_credentials() -> None:
    proxy = camoufox_runtime.parse_browser_proxy(
        "https://user%40name:pass%3Aword@proxy.example:8443/"
    )
    assert proxy.server == "https://proxy.example:8443"
    assert proxy.username == "user@name"
    assert proxy.password == "pass:word"


def test_plugin_passes_only_minimal_child_environment(monkeypatch) -> None:
    captured = []
    monkeypatch.setattr(camoufox_runtime, "load_browser_version", lambda: "152.0.4-beta.27")
    monkeypatch.setattr(camoufox_runtime, "preflight_camoufox_cache", lambda *args: None)
    monkeypatch.setattr(
        camoufox_runtime,
        "camoufox_launch_options",
        lambda **kwargs: captured.append(kwargs) or {"prepared": True},
    )

    async def launch(*args, **kwargs):
        return object()

    monkeypatch.setattr(camoufox_runtime, "AsyncNewBrowser", launch)
    monkeypatch.setattr(
        camoufox_runtime, "PlaywrightBrowserController", lambda *args, **kwargs: kwargs
    )
    plugin = camoufox_runtime.CamoufoxPlugin()
    plugin._playwright = object()
    asyncio.run(plugin.new_browser())
    assert set(captured[0]["env"]) == set(camoufox_runtime.CHILD_ENV_KEYS)
    assert "proxy" not in captured[0] and "geoip" not in captured[0]


def test_proxy_geolocation_is_prepared_once_for_four_controllers(monkeypatch) -> None:
    prepared_calls = []
    public_ip_calls = []
    browser_options = []
    monkeypatch.setattr(camoufox_runtime, "load_browser_version", lambda: "152.0.4-beta.27")
    monkeypatch.setattr(camoufox_runtime, "preflight_camoufox_cache", lambda *args: None)

    def prepare(**kwargs):
        prepared_calls.append(kwargs)
        return {"proxy": dict(kwargs["proxy"]), "geoip": {"latitude": 1.0}}

    def resolve_ip(proxy):
        public_ip_calls.append(proxy)
        return "203.0.113.10"

    async def launch(*args, **kwargs):
        browser_options.append(kwargs["from_options"])
        return object()

    monkeypatch.setattr(camoufox_runtime, "camoufox_launch_options", prepare)
    monkeypatch.setattr(camoufox_runtime, "public_ip", resolve_ip)
    monkeypatch.setattr(camoufox_runtime, "AsyncNewBrowser", launch)
    monkeypatch.setattr(
        camoufox_runtime, "PlaywrightBrowserController", lambda *args, **kwargs: kwargs
    )
    proxy = camoufox_runtime.BrowserProxyConfig("https://proxy.example:8443", "user", "password")
    plugin = camoufox_runtime.CamoufoxPlugin(proxy_config=proxy)
    plugin._playwright = object()

    async def scenario() -> None:
        await asyncio.gather(*(plugin.new_browser() for _ in range(4)))

    asyncio.run(scenario())
    assert len(public_ip_calls) == 1
    assert len(prepared_calls) == 4
    assert all(call["geoip"] == "203.0.113.10" for call in prepared_calls)
    assert len(browser_options) == 4
    assert len({id(options) for options in browser_options}) == 4
    assert all(options["geoip"] == {"latitude": 1.0} for options in browser_options)
