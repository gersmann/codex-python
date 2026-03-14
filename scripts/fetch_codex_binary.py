#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import subprocess  # nosec B404
import tarfile
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

GITHUB_API = "https://api.github.com"
GITHUB_WEB = "https://github.com"
USER_AGENT = "codex-python-binary-fetcher"
ZSTD_TIMEOUT_SECONDS = 300


@dataclass(slots=True, frozen=True)
class ReleaseAsset:
    name: str
    url: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch and stage codex binary assets into the wheel."
    )
    parser.add_argument(
        "--release-tag",
        default="latest",
        help="GitHub release tag (e.g. rust-v0.50.0). Use 'latest' to resolve latest release.",
    )
    parser.add_argument(
        "--repo",
        default="openai/codex",
        help="GitHub repository in owner/name format.",
    )
    parser.add_argument(
        "--dest-root",
        default="codex/vendor",
        help="Destination root directory for bundled binaries.",
    )
    parser.add_argument(
        "--target-triple",
        action="append",
        required=True,
        help="Target triple to fetch (repeatable).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    token = _read_optional_env("GITHUB_TOKEN")
    dest_root = Path(args.dest_root).resolve()
    targets: list[str] = list(dict.fromkeys(args.target_triple))
    resolved_tag = resolve_release_tag(args.repo, args.release_tag, token)

    release_assets: list[ReleaseAsset] | None = None
    for target in targets:
        if try_install_direct_asset(args.repo, resolved_tag, target, dest_root, token):
            continue

        if release_assets is None:
            release_assets = list_release_assets(args.repo, resolved_tag, token)
        asset = select_asset_for_target(release_assets, target)
        if asset is None:
            raise RuntimeError(
                f"No release asset found for target '{target}'. "
                f"Looked for names starting with 'codex-{target}'."
            )
        install_asset(asset, target, dest_root, token)
    print(f"Installed codex binaries for {len(targets)} target(s) into {dest_root}")
    return 0


def _read_optional_env(name: str) -> str | None:
    value = os.environ.get(name)
    if value is None or value == "":
        return None
    return value


def list_release_assets(repo: str, release_tag: str, token: str | None) -> list[ReleaseAsset]:
    url = f"{GITHUB_API}/repos/{repo}/releases/tags/{release_tag}"
    payload = github_json(url, token)
    assets = payload.get("assets")
    if not isinstance(assets, list):
        raise RuntimeError("Release payload did not include an assets list")
    release_assets: list[ReleaseAsset] = []
    for raw_asset in assets:
        if not isinstance(raw_asset, dict):
            continue
        name = raw_asset.get("name")
        download_url = raw_asset.get("browser_download_url")
        if isinstance(name, str) and isinstance(download_url, str):
            release_assets.append(ReleaseAsset(name=name, url=download_url))
    return release_assets


def resolve_release_tag(repo: str, release_tag: str, token: str | None) -> str:
    if release_tag != "latest":
        return release_tag

    url = f"{GITHUB_WEB}/{repo}/releases/latest"
    final_url = github_redirect_url(url, token)
    marker = "/releases/tag/"
    if marker not in final_url:
        raise RuntimeError(f"Could not resolve latest release tag from redirect URL: {final_url}")
    return final_url.split(marker, 1)[1]


def candidate_asset_names(target: str) -> list[str]:
    prefix = f"codex-{target}"
    return [
        f"{prefix}.tar.gz",
        f"{prefix}.zip",
        f"{prefix}.exe",
        f"{prefix}",
        f"{prefix}.zst",
        f"{prefix}.exe.zst",
    ]


def select_asset_for_target(assets: list[ReleaseAsset], target: str) -> ReleaseAsset | None:
    prefix = f"codex-{target}"
    exact_candidates = candidate_asset_names(target)
    by_name = {asset.name: asset for asset in assets}
    for candidate in exact_candidates:
        if candidate in by_name:
            return by_name[candidate]
    matching = sorted(
        [asset for asset in assets if asset.name.startswith(prefix)], key=lambda a: a.name
    )
    if matching:
        return matching[0]
    return None


def try_install_direct_asset(
    repo: str,
    release_tag: str,
    target: str,
    dest_root: Path,
    token: str | None,
) -> bool:
    for asset_name in candidate_asset_names(target):
        asset = ReleaseAsset(
            name=asset_name,
            url=f"{GITHUB_WEB}/{repo}/releases/download/{release_tag}/{asset_name}",
        )
        try:
            install_asset(asset, target, dest_root, token)
        except RuntimeError as exc:
            if _is_not_found_download_error(exc):
                continue
            raise
        return True
    return False


def install_asset(asset: ReleaseAsset, target: str, dest_root: Path, token: str | None) -> None:
    with tempfile.TemporaryDirectory(prefix=f"codex-asset-{target}-") as tmp:
        tmp_dir = Path(tmp)
        archive_path = tmp_dir / asset.name
        download(asset.url, archive_path, token)

        binary_name = "codex.exe" if "windows" in target else "codex"
        dest_path = dest_root / target / "codex" / binary_name
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        _extract_to_binary(archive_path, dest_path)

        if "windows" not in target:
            mode = dest_path.stat().st_mode
            dest_path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

        print(f"Installed {asset.name} -> {dest_path}")


def _extract_to_binary(archive_path: Path, dest_path: Path) -> None:
    name = archive_path.name
    if name.endswith(".tar.gz"):
        _extract_from_targz(archive_path, dest_path)
        return
    if name.endswith(".zip"):
        _extract_from_zip(archive_path, dest_path)
        return
    if name.endswith(".zst"):
        _extract_zst(archive_path, dest_path)
        return
    shutil.copyfile(archive_path, dest_path)


def _extract_from_targz(archive_path: Path, dest_path: Path) -> None:
    with tarfile.open(archive_path, "r:gz") as tar:
        members = [m for m in tar.getmembers() if m.isfile()]
        if not members:
            raise RuntimeError(f"No file entries found in {archive_path}")
        preferred = [m for m in members if Path(m.name).name.startswith("codex")]
        member = preferred[0] if preferred else members[0]
        extracted = tar.extractfile(member)
        if extracted is None:
            raise RuntimeError(f"Failed to read {member.name} from {archive_path}")
        with extracted, open(dest_path, "wb") as dest:
            shutil.copyfileobj(extracted, dest)


def _extract_from_zip(archive_path: Path, dest_path: Path) -> None:
    with zipfile.ZipFile(archive_path) as zf:
        members = [m for m in zf.infolist() if not m.is_dir()]
        if not members:
            raise RuntimeError(f"No file entries found in {archive_path}")
        preferred = [m for m in members if Path(m.filename).name.startswith("codex")]
        member = preferred[0] if preferred else members[0]
        with zf.open(member) as src, open(dest_path, "wb") as dest:
            shutil.copyfileobj(src, dest)


def _extract_zst(archive_path: Path, dest_path: Path) -> None:
    zstd_path = shutil.which("zstd")
    if zstd_path is not None:
        subprocess.run(
            [zstd_path, "-f", "-d", str(archive_path), "-o", str(dest_path)],
            check=True,
            timeout=ZSTD_TIMEOUT_SECONDS,
        )  # nosec B603
        return

    try:
        import zstandard
    except ImportError as exc:
        raise RuntimeError(
            f"Asset {archive_path.name} is zst-compressed, but neither 'zstd' nor Python package "
            "'zstandard' is available in the build environment."
        ) from exc

    with open(archive_path, "rb") as src, open(dest_path, "wb") as dest:
        decompressor = zstandard.ZstdDecompressor()
        decompressor.copy_stream(src, dest)


def github_json(url: str, token: str | None) -> dict[str, Any]:
    _require_https_url(url)
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": USER_AGENT,
    }
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, headers=headers)
    try:
        with urlopen(request) as response:  # nosec B310
            payload = response.read().decode("utf-8")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API request failed ({exc.code}) for {url}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"Network error while requesting {url}: {exc}") from exc

    data = json.loads(payload)
    if not isinstance(data, dict):
        raise RuntimeError(f"Expected object response from {url}")
    return data


def github_redirect_url(url: str, token: str | None) -> str:
    _require_https_url(url)
    headers = {"User-Agent": USER_AGENT}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, headers=headers)
    try:
        with urlopen(request) as response:  # nosec B310
            return response.geturl()
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"GitHub redirect request failed ({exc.code}) for {url}: {body}"
        ) from exc
    except URLError as exc:
        raise RuntimeError(f"Network error while requesting {url}: {exc}") from exc


def download(url: str, destination: Path, token: str | None) -> None:
    _require_https_url(url)
    headers = {"User-Agent": USER_AGENT}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, headers=headers)
    try:
        with urlopen(request) as response, open(destination, "wb") as output:  # nosec B310
            shutil.copyfileobj(response, output)
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Download failed ({exc.code}) for {url}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"Network error while downloading {url}: {exc}") from exc


def _require_https_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc == "":
        raise RuntimeError(f"Refusing to fetch non-HTTPS URL: {url}")


def _is_not_found_download_error(exc: RuntimeError) -> bool:
    return str(exc).startswith("Download failed (404)")


if __name__ == "__main__":
    raise SystemExit(main())
