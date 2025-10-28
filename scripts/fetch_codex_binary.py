#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import subprocess
import tarfile
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

GITHUB_API = "https://api.github.com"
USER_AGENT = "codex-python-binary-fetcher"


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
    release_assets = list_release_assets(args.repo, args.release_tag, token)
    dest_root = Path(args.dest_root).resolve()
    targets: list[str] = list(dict.fromkeys(args.target_triple))
    for target in targets:
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
    if release_tag == "latest":
        url = f"{GITHUB_API}/repos/{repo}/releases/latest"
    else:
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


def select_asset_for_target(assets: list[ReleaseAsset], target: str) -> ReleaseAsset | None:
    prefix = f"codex-{target}"
    exact_candidates = [
        f"{prefix}.tar.gz",
        f"{prefix}.zip",
        f"{prefix}.exe",
        f"{prefix}",
        f"{prefix}.zst",
        f"{prefix}.exe.zst",
    ]
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
    if shutil.which("zstd") is not None:
        subprocess.check_call(["zstd", "-f", "-d", str(archive_path), "-o", str(dest_path)])
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
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": USER_AGENT,
    }
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, headers=headers)
    try:
        with urlopen(request) as response:
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


def download(url: str, destination: Path, token: str | None) -> None:
    headers = {"User-Agent": USER_AGENT}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, headers=headers)
    try:
        with urlopen(request) as response, open(destination, "wb") as output:
            shutil.copyfileobj(response, output)
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Download failed ({exc.code}) for {url}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"Network error while downloading {url}: {exc}") from exc


if __name__ == "__main__":
    raise SystemExit(main())
