"""Run explicitly inside the built, network-none, read-only browser container."""

import asyncio
import os
import sys
from pathlib import Path


def verify_non_writable(root: Path) -> None:
    if os.geteuid() == 0:
        raise RuntimeError("The offline probe must run as the image's non-root user")
    for path in (root, *root.rglob("*")):
        if path.stat().st_mode & 0o222 or os.access(path, os.W_OK):
            raise RuntimeError(f"Writable browser cache path: {path}")


async def main() -> None:
    sys.path.insert(0, "/app")
    from camoufox.async_api import AsyncNewBrowser, launch_options
    from playwright.async_api import async_playwright

    from app.artifacts import CACHE_ROOT, verify_cache_manifest
    from app.camoufox_runtime import (
        load_browser_version,
        minimal_child_environment,
        preflight_camoufox_cache,
    )

    version = load_browser_version()
    verify_cache_manifest()
    preflight_camoufox_cache(version, require_geoip=True)
    verify_non_writable(CACHE_ROOT)
    prepared = [
        launch_options(
            os=name,
            headless=True,
            browser=version,
            debug=False,
            env=minimal_child_environment(),
        )
        for name in ("linux", "macos", "windows")
    ]
    async with async_playwright() as playwright:
        browser = await AsyncNewBrowser(playwright, from_options=prepared[0])
        try:
            page = await browser.new_page()
            await page.goto("about:blank")
            if await page.evaluate("1 + 1") != 2:
                raise RuntimeError("Browser script evaluation failed")
        finally:
            await browser.close()
    verify_cache_manifest()
    preflight_camoufox_cache(version, require_geoip=True)
    verify_non_writable(CACHE_ROOT)
    print("PASS: offline launch, three OS launch options, manifest and immutable non-root cache")


if __name__ == "__main__":
    asyncio.run(main())
