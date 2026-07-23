import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from camoufox import DefaultAddons
from camoufox.addons import get_addon_path
from camoufox.async_api import AsyncNewBrowser
from camoufox.async_api import launch_options as camoufox_launch_options
from camoufox.geolocation import get_mmdb_path, needs_update
from camoufox.ip import Proxy as CamoufoxProxy
from camoufox.ip import public_ip
from camoufox.multiversion import find_installed_version
from crawlee.browsers import PlaywrightBrowserController, PlaywrightBrowserPlugin

BROWSER_MANIFEST_PATH = Path(__file__).with_name("camoufox_browser_version.txt")
EXPECTED_BROWSER_BUILD = "official/stable/152.0.4-beta.27"
GEOIP_PREPARATION_TIMEOUT_SECONDS = 35
CHILD_ENVIRONMENT = {
    "HOME": "/home/browseruser",
    "PATH": "/opt/venv/bin:/usr/local/bin:/usr/bin:/bin",
    "LANG": "C.UTF-8",
    "LC_ALL": "C.UTF-8",
    "TMPDIR": "/tmp",
    "FONTCONFIG_FILE": "/etc/browser-service/fonts.conf",
}
CHILD_ENV_KEYS = tuple(CHILD_ENVIRONMENT)


class _CamoufoxLaunchError(Exception):
    """Sanitized browser cache, GeoIP, or launch failure."""


@dataclass(frozen=True)
class BrowserProxyConfig:
    server: str
    username: str | None = None
    password: str | None = None

    def as_camoufox_proxy(self) -> dict[str, str]:
        value = {"server": self.server}
        if self.username is not None and self.password is not None:
            value.update(username=self.username, password=self.password)
        return value


def parse_browser_proxy(value: str) -> BrowserProxyConfig:
    parsed = urlsplit(value.strip())
    if parsed.scheme.lower() not in {"http", "https"}:
        raise ValueError("unsupported proxy scheme")
    if not parsed.hostname or any(char.isspace() for char in parsed.hostname):
        raise ValueError("proxy hostname is required")
    try:
        port = parsed.port
    except ValueError as error:
        raise ValueError("proxy port is invalid") from error
    if port is None:
        raise ValueError("proxy port is required")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ValueError("proxy URL contains unsupported components")
    if (parsed.username is None) != (parsed.password is None):
        raise ValueError("proxy credentials must be paired")
    username = unquote(parsed.username) if parsed.username is not None else None
    password = unquote(parsed.password) if parsed.password is not None else None
    if username == "" or password == "":
        raise ValueError("proxy credentials must not be empty")
    hostname = parsed.hostname
    host = f"[{hostname}]" if ":" in hostname else hostname
    return BrowserProxyConfig(f"{parsed.scheme.lower()}://{host}:{port}", username, password)


def load_browser_version() -> str:
    try:
        value = BROWSER_MANIFEST_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        raise _CamoufoxLaunchError("Camoufox browser cache is unavailable") from None
    if value != EXPECTED_BROWSER_BUILD:
        raise _CamoufoxLaunchError("Camoufox browser cache is unavailable")
    return value.rsplit("/", 1)[-1]


def preflight_camoufox_cache(browser_version: str, require_geoip: bool = True) -> None:
    if find_installed_version(browser_version) is None:
        raise _CamoufoxLaunchError("Camoufox browser cache is unavailable")
    addons = [Path(get_addon_path(addon.name)) for addon in DefaultAddons]
    if not addons or not all(path.is_dir() and any(path.iterdir()) for path in addons):
        raise _CamoufoxLaunchError("Camoufox browser cache is unavailable")
    if require_geoip:
        geoip = [get_mmdb_path("ipv4"), get_mmdb_path("ipv6")]
        if not all(path.is_file() and path.stat().st_size for path in geoip) or needs_update():
            raise _CamoufoxLaunchError("Camoufox GeoIP cache is unavailable")


def minimal_child_environment() -> dict[str, str]:
    return dict(CHILD_ENVIRONMENT)


class CamoufoxPlugin(PlaywrightBrowserPlugin):
    def __init__(self, proxy_config: BrowserProxyConfig | None = None) -> None:
        super().__init__(
            browser_type="firefox",
            fingerprint_generator=None,
            use_incognito_pages=False,
            max_open_pages_per_browser=1,
        )
        self._proxy_config = proxy_config
        self._launch_prepared = False
        self._proxy_ip_task: asyncio.Task[str] | None = None

    @property
    def proxy_enabled(self) -> bool:
        return self._proxy_config is not None

    @property
    def launch_prepared(self) -> bool:
        return self._launch_prepared

    async def new_browser(self) -> PlaywrightBrowserController:
        if self._playwright is None:
            raise _CamoufoxLaunchError("Camoufox browser initialization failed")
        try:
            async with asyncio.timeout(GEOIP_PREPARATION_TIMEOUT_SECONDS):
                version = load_browser_version()
                preflight_camoufox_cache(version, self.proxy_enabled)
                options: dict[str, Any] = {
                    "headless": True,
                    "browser": version,
                    "debug": False,
                    "env": minimal_child_environment(),
                }
                if self._proxy_config is not None:
                    options["proxy"] = self._proxy_config.as_camoufox_proxy()
                    options["geoip"] = await self._proxy_public_ip()
                prepared = await asyncio.to_thread(camoufox_launch_options, **options)
                self._launch_prepared = True
            browser = await AsyncNewBrowser(self._playwright, from_options=prepared)
            return PlaywrightBrowserController(
                browser,
                max_open_pages_per_browser=1,
                use_incognito_pages=False,
                header_generator=None,
                fingerprint_generator=None,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            raise _CamoufoxLaunchError("Camoufox browser initialization failed") from None

    async def _proxy_public_ip(self) -> str:
        if self._proxy_config is None:
            raise _CamoufoxLaunchError("Camoufox browser initialization failed")
        if self._proxy_ip_task is None:
            proxy = CamoufoxProxy(**self._proxy_config.as_camoufox_proxy()).as_string()
            self._proxy_ip_task = asyncio.create_task(asyncio.to_thread(public_ip, proxy))
        return await asyncio.shield(self._proxy_ip_task)


def silent_crawlee_logger(name: str) -> logging.Logger:
    target = logging.getLogger(name)
    target.handlers.clear()
    target.addHandler(logging.NullHandler())
    target.propagate = False
    target.setLevel(logging.CRITICAL + 1)
    return target
