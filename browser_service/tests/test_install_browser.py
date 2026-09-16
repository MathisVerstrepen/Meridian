import json
import os
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock
from zipfile import ZipFile

import pytest
import requests
from camoufox import addons, geolocation, multiversion, pkgman

from browser_service.app import camoufox_runtime, install_browser


@pytest.fixture(autouse=True)
def no_network_or_discovery(monkeypatch):
    forbidden = Mock(side_effect=requests.HTTPError("403 release discovery forbidden"))
    monkeypatch.setattr(requests.sessions.Session, "request", forbidden)
    monkeypatch.setattr(pkgman.GitHubDownloader, "_get_releases", forbidden)
    monkeypatch.setattr(pkgman, "list_available_versions", forbidden)
    monkeypatch.setattr(pkgman.CamoufoxFetcher, "fetch_latest", forbidden)
    yield forbidden
    forbidden.assert_not_called()


@pytest.fixture
def isolated_install(monkeypatch, tmp_path):
    root = tmp_path / "camoufox"
    monkeypatch.setattr(pkgman, "INSTALL_DIR", root)
    for name, path in {
        "INSTALL_DIR": root,
        "BROWSERS_DIR": root / "browsers",
        "CONFIG_FILE": root / "config.json",
        "REPO_CACHE_FILE": root / "repo_cache.json",
        "COMPAT_FLAG": root / ".0.5_FLAG",
    }.items():
        monkeypatch.setattr(multiversion, name, path)
    monkeypatch.setattr(addons, "ADDONS_DIR", root / "addons")
    monkeypatch.setattr(geolocation, "GEOIP_DIR", root / "geoip")
    monkeypatch.setattr(geolocation, "GEOIP_CONFIG", root / "geoip" / "config.yml")
    monkeypatch.setattr(geolocation, "MMDB_DIR", root / "geoip" / "mmdb")
    monkeypatch.setattr(pkgman.sys, "platform", "linux")
    monkeypatch.setattr(pkgman.platform, "machine", lambda: "x86_64")

    archive = BytesIO()
    with ZipFile(archive, "w") as zipped:
        zipped.writestr("camoufox-bin", "synthetic browser executable")

    def download(file, url):
        file.write(archive.getvalue())
        file.seek(0)
        return file

    def geoip():
        for ip_version in ("ipv4", "ipv6"):
            path = geolocation.get_mmdb_path(ip_version)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"synthetic GeoIP database")

    def populate_addons(defaults):
        for addon in defaults:
            path = Path(addons.get_addon_path(addon.name))
            path.mkdir(parents=True, exist_ok=True)
            (path / "manifest.json").write_text("{}")

    download_mock = Mock(side_effect=download)
    geoip_mock = Mock(side_effect=geoip)
    addons_mock = Mock(side_effect=populate_addons)
    monkeypatch.setattr(pkgman.CamoufoxFetcher, "download_file", download_mock)
    monkeypatch.setattr(install_browser, "download_mmdb", geoip_mock)
    monkeypatch.setattr(install_browser, "maybe_download_addons", addons_mock)
    return root, download_mock, geoip_mock, addons_mock


@pytest.mark.parametrize("machine,arch", [("x86_64", "x86_64"), ("aarch64", "arm64")])
def test_selected_official_asset_retains_real_installer_metadata(
    monkeypatch, isolated_install, machine, arch
):
    root, download, geoip, default_addons = isolated_install
    monkeypatch.setattr(pkgman.platform, "machine", lambda: machine)
    install_browser.install_browser()

    assert download.call_args.args[1] == (
        "https://github.com/daijro/camoufox/releases/download/v152.0.4-beta.27/"
        f"camoufox-152.0.4-beta.27-lin.{arch}.zip"
    )
    installed = multiversion.find_installed_version("152.0.4-beta.27")
    assert installed is not None
    active = multiversion.get_active_path()
    assert active == root / "browsers" / "official" / "152.0.4-beta.27"
    assert multiversion.load_config()["active_version"] == str(active.relative_to(root))
    metadata = json.loads((active / "version.json").read_text())
    assert metadata["version"] == "152.0.4"
    assert metadata["build"] == "beta.27"
    assert metadata["prerelease"] is False
    assert metadata["sha256"] is None  # No claim of upstream byte verification.
    assert (root / ".0.5_FLAG").is_file()
    assert os.access(active / "camoufox-bin", os.X_OK)
    assert pkgman.camoufox_path(download_if_missing=False) == active
    geoip.assert_called_once_with()
    default_addons.assert_called_once_with(list(addons.DefaultAddons))
    camoufox_runtime.preflight_camoufox_cache(camoufox_runtime.load_browser_version(), True)


@pytest.mark.parametrize("platform,machine", [("darwin", "arm64"), ("linux", "i686")])
def test_unsupported_platform_fails_before_download(
    monkeypatch, isolated_install, platform, machine
):
    _, download, geoip, default_addons = isolated_install
    monkeypatch.setattr(pkgman.sys, "platform", platform)
    monkeypatch.setattr(pkgman.platform, "machine", lambda: machine)
    with pytest.raises(RuntimeError, match="Linux|architecture"):
        install_browser.install_browser()
    download.assert_not_called()
    geoip.assert_not_called()
    default_addons.assert_not_called()


def test_invalid_pin_fails_before_download(monkeypatch, tmp_path, isolated_install):
    manifest = tmp_path / "version.txt"
    manifest.write_text("official/stable/latest")
    monkeypatch.setattr(camoufox_runtime, "BROWSER_MANIFEST_PATH", manifest)
    with pytest.raises(camoufox_runtime._CamoufoxLaunchError):
        install_browser.install_browser()
    isolated_install[1].assert_not_called()


def test_missing_official_config_fails_before_download(monkeypatch, isolated_install):
    monkeypatch.setattr(pkgman.RepoConfig, "find_by_name", lambda name: None)
    with pytest.raises(RuntimeError, match="Official"):
        install_browser.install_browser()
    isolated_install[1].assert_not_called()


def test_browser_download_failure_propagates_and_skips_extras(isolated_install):
    root, download, geoip, default_addons = isolated_install
    download.side_effect = requests.HTTPError("404 pinned asset unavailable")
    with pytest.raises(requests.HTTPError, match="404"):
        install_browser.install_browser()
    assert not (root / ".0.5_FLAG").exists()
    assert multiversion.find_installed_version("152.0.4-beta.27") is None
    geoip.assert_not_called()
    default_addons.assert_not_called()


def test_geoip_failure_propagates(isolated_install):
    _, _, geoip, default_addons = isolated_install
    geoip.side_effect = requests.HTTPError("GeoIP unavailable")
    with pytest.raises(requests.HTTPError, match="GeoIP"):
        install_browser.install_browser()
    default_addons.assert_not_called()


def test_preflight_rejects_swallowed_addon_failure(monkeypatch, isolated_install):
    monkeypatch.setattr(install_browser, "maybe_download_addons", addons.maybe_download_addons)
    monkeypatch.setattr(
        addons, "download_and_extract", Mock(side_effect=requests.HTTPError("add-on unavailable"))
    )
    install_browser.install_browser()
    with pytest.raises(camoufox_runtime._CamoufoxLaunchError):
        camoufox_runtime.preflight_camoufox_cache(camoufox_runtime.load_browser_version(), True)


def test_dockerfile_retains_cache_preparation_order():
    dockerfile = Path(__file__).resolve().parents[2] / "docker" / "browser-service.Dockerfile"
    source = dockerfile.read_text()
    steps = (
        "PYTHONPATH=/build python -m app.install_browser",
        "preflight_camoufox_cache(load_browser_version(), True)",
        "launch_options(os=name",
        "build_cache_manifest())",
        "chmod -R a-w /home/browseruser/.cache/camoufox",
    )
    positions = [source.index(step) for step in steps]
    assert positions == sorted(positions)
    assert "('linux', 'macos', 'windows')" in source
    assert "python -m camoufox fetch" not in source
    assert "USER browseruser" in source
