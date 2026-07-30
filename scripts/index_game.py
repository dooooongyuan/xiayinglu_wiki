#!/usr/bin/env python3
"""Build a reproducible, read-only index of the Xiayinglu Unity install.

The script never writes to the game directory. It inventories Addressables and
YooAsset bundles, then emits JSON consumed by the wiki build.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import UnityPy
except ImportError as exc:  # pragma: no cover - environment guidance
    raise SystemExit("UnityPy is required: python -m pip install UnityPy") from exc


DEFAULT_GAME_ROOT = Path(r"F:\SteamLibrary\steamapps\common\侠影录")
DATA_DIR_NAME = "xiayinglu_Data"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-root", type=Path, default=DEFAULT_GAME_ROOT)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "wiki" / "src" / "data" / "game-index.json",
    )
    parser.add_argument(
        "--bundle-cache",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "logs" / "bundle-index.json",
    )
    parser.add_argument(
        "--max-bundle-mb",
        type=float,
        default=128,
        help="Skip oversized bundles during metadata discovery; use 0 for no limit.",
    )
    parser.add_argument("--force", action="store_true", help="Ignore the incremental bundle cache.")
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def clean_asset_name(value: str) -> str:
    return value.replace("\\", "/").strip()


def classify_address(address: str) -> str:
    lower = address.lower()
    if lower.startswith("skilldata/"):
        return "skill"
    if "localization" in lower:
        return "localization"
    if lower.endswith((".png", ".jpg", ".jpeg", ".webp")):
        return "image"
    if lower.endswith(".bundle"):
        return "bundle"
    if lower.endswith(".asset"):
        return "asset"
    if any(token in lower for token in ("scene", "map/", "level")):
        return "scene"
    return "other"


def addressables_summary(data_root: Path) -> dict[str, Any]:
    catalog_path = data_root / "StreamingAssets" / "aa" / "catalog.json"
    catalog = read_json(catalog_path)
    addresses = [clean_asset_name(value) for value in catalog.get("m_InternalIds", [])]
    categories = Counter(classify_address(value) for value in addresses)
    skill_ids = sorted(
        (value.split("/", 1)[1] for value in addresses if value.startswith("SkillData/")),
        key=lambda value: (len(value), value),
    )
    images = [value for value in addresses if classify_address(value) == "image"]
    return {
        "catalog": str(catalog_path),
        "buildHash": catalog.get("m_BuildResultHash"),
        "addressCount": len(addresses),
        "categories": dict(sorted(categories.items())),
        "skillIds": skill_ids,
        "imageAddresses": images,
    }


def load_cache(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": 1, "bundles": {}}
    try:
        data = read_json(path)
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "bundles": {}}
    return data if data.get("version") == 1 else {"version": 1, "bundles": {}}


def inspect_bundle(path: Path) -> dict[str, Any]:
    record: dict[str, Any] = {
        "file": path.name,
        "bytes": path.stat().st_size,
        "modifiedNs": path.stat().st_mtime_ns,
        "bundleName": None,
        "assets": [],
        "types": {},
    }
    try:
        env = UnityPy.load(str(path))
        type_counts: Counter[str] = Counter()
        asset_names: list[str] = []
        for obj in env.objects:
            type_counts[obj.type.name] += 1
            if obj.type.name != "AssetBundle":
                continue
            data = obj.read()
            record["bundleName"] = getattr(data, "m_Name", None)
            container = getattr(data, "m_Container", []) or []
            for entry in container:
                name = getattr(entry, "first", None)
                if name is None and isinstance(entry, (list, tuple)) and entry:
                    name = entry[0]
                if name:
                    asset_names.append(clean_asset_name(str(name)))
        record["assets"] = sorted(set(asset_names))
        record["types"] = dict(sorted(type_counts.items()))
    except Exception as exc:  # Keep one bad bundle from invalidating the complete index.
        record["error"] = f"{type(exc).__name__}: {exc}"
    return record


def bundle_summary(data_root: Path, cache_path: Path, max_bundle_mb: float, force: bool) -> dict[str, Any]:
    package_root = data_root / "StreamingAssets" / "yougou" / "DefaultPackage"
    catalog_path = package_root / "BuildinCatalog.json"
    catalog = read_json(catalog_path)
    bundle_paths = sorted(package_root.glob("*.bundle"))
    limit_bytes = int(max_bundle_mb * 1024 * 1024) if max_bundle_mb else 0
    cache = load_cache(cache_path)
    cached_bundles: dict[str, Any] = cache.setdefault("bundles", {})
    records: list[dict[str, Any]] = []
    skipped = 0

    for index, path in enumerate(bundle_paths, start=1):
        stat = path.stat()
        cached = cached_bundles.get(path.name)
        if limit_bytes and stat.st_size > limit_bytes:
            skipped += 1
            record = {
                "file": path.name,
                "bytes": stat.st_size,
                "modifiedNs": stat.st_mtime_ns,
                "skipped": "size-limit",
            }
        elif (
            not force
            and cached
            and cached.get("bytes") == stat.st_size
            and cached.get("modifiedNs") == stat.st_mtime_ns
        ):
            record = cached
        else:
            record = inspect_bundle(path)
            cached_bundles[path.name] = record
        records.append(record)
        if index % 100 == 0:
            print(f"Indexed {index}/{len(bundle_paths)} bundles", file=sys.stderr)

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    named = [record for record in records if record.get("bundleName")]
    errors = [record for record in records if record.get("error")]
    asset_count = sum(len(record.get("assets", [])) for record in records)
    return {
        "catalog": str(catalog_path),
        "packageVersion": catalog.get("PackageVersion"),
        "declaredBundleCount": len(catalog.get("Wrappers", [])),
        "bundleCount": len(bundle_paths),
        "indexedBundleCount": len(named),
        "skippedBundleCount": skipped,
        "errorCount": len(errors),
        "discoveredAssetCount": asset_count,
        "bundles": records,
    }


def game_build_info(game_root: Path, data_root: Path) -> dict[str, Any]:
    executable = game_root / "xiayinglu.exe"
    app_info = (data_root / "app.info").read_text(encoding="utf-8", errors="replace").splitlines()
    return {
        "title": "侠影录",
        "engine": "Unity IL2CPP",
        "publisher": app_info[0] if app_info else None,
        "application": app_info[1] if len(app_info) > 1 else None,
        "executableModified": datetime.fromtimestamp(executable.stat().st_mtime, timezone.utc).isoformat(),
    }


def main() -> int:
    args = parse_args()
    game_root = args.game_root.resolve()
    data_root = game_root / DATA_DIR_NAME
    required = [game_root / "xiayinglu.exe", data_root / "StreamingAssets"]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise SystemExit("Game install is incomplete or missing:\n" + "\n".join(missing))

    payload = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "sourceRoot": str(game_root),
        "game": game_build_info(game_root, data_root),
        "addressables": addressables_summary(data_root),
        "yooAsset": bundle_summary(data_root, args.bundle_cache, args.max_bundle_mb, args.force),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
