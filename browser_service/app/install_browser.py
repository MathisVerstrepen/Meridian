"""Populate the image cache without Camoufox's release-list discovery."""

from camoufox.addons import DefaultAddons, maybe_download_addons
from camoufox.geolocation import download_mmdb
from camoufox.pkgman import AvailableVersion, CamoufoxFetcher, RepoConfig, Version

from .camoufox_runtime import load_browser_version


def install_browser() -> None:
    browser_version = load_browser_version()
    official = RepoConfig.find_by_name("Official")
    if official is None:
        raise RuntimeError("Camoufox Official repository configuration is unavailable")
    if official.get_os_name() != "lin":
        raise RuntimeError("The browser image requires Linux")
    arch = official.get_arch()
    if arch not in {"x86_64", "arm64"}:
        raise RuntimeError(f"Unsupported browser image architecture: {arch}")

    version, build = browser_version.split("-", 1)
    selected = AvailableVersion(
        version=Version(build=build, version=version),
        url=(
            f"https://github.com/daijro/camoufox/releases/download/v{browser_version}/"
            f"camoufox-{browser_version}-lin.{arch}.zip"
        ),
        is_prerelease=False,
    )
    # The library owns extraction, version metadata, active config and executable permissions.
    CamoufoxFetcher(repo_config=official, selected_version=selected).install()
    download_mmdb()
    maybe_download_addons(list(DefaultAddons))


if __name__ == "__main__":
    install_browser()
