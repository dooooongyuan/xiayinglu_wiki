#!/usr/bin/env python3
"""Extract approved UI art and localization data for the wiki.

Only a small, explicit allowlist is exported. This keeps the website repository
compact and makes it clear which game files are being redistributed.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import UnityPy
from PIL import Image


DEFAULT_GAME_ROOT = Path(r"F:\SteamLibrary\steamapps\common\侠影录")
PROJECT_ROOT = Path(__file__).resolve().parents[1]

ASSET_EXPORTS = {
    -7985025590841280237: "wiki-logo.png",
    7148510507295874923: "wiki-background.jpg",
    4504271544747551660: "category-wuxue.png",
    -3916738839717996089: "category-zhuangbei.png",
    6286644621508397270: "category-danyao.png",
    6236116366830885663: "category-qita.png",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-root", type=Path, default=DEFAULT_GAME_ROOT)
    parser.add_argument("--public-dir", type=Path, default=PROJECT_ROOT / "wiki" / "public" / "game")
    parser.add_argument("--data-dir", type=Path, default=PROJECT_ROOT / "wiki" / "src" / "data")
    return parser.parse_args()


def bundle_root(game_root: Path) -> Path:
    return game_root / "xiayinglu_Data" / "StreamingAssets" / "aa" / "StandaloneWindows64"


def export_images(root: Path, output_dir: Path) -> list[dict[str, Any]]:
    shared = root / "localization-assets-shared_assets_all.bundle"
    env = UnityPy.load(str(shared))
    output_dir.mkdir(parents=True, exist_ok=True)
    exported: list[dict[str, Any]] = []
    remaining = set(ASSET_EXPORTS)

    for obj in env.objects:
        if obj.path_id not in remaining or obj.type.name != "Texture2D":
            continue
        data = obj.read()
        image = data.image
        filename = ASSET_EXPORTS[obj.path_id]
        target = output_dir / filename
        if target.suffix.lower() in {".jpg", ".jpeg"}:
            if image.mode == "RGBA":
                background = Image.new("RGB", image.size, (18, 17, 15))
                background.paste(image, mask=image.getchannel("A"))
                image = background
            image.convert("RGB").save(target, quality=88, optimize=True, progressive=True)
        else:
            image.save(target, optimize=True)
        exported.append(
            {
                "file": f"/game/{filename}",
                "sourcePathId": obj.path_id,
                "sourceName": data.m_Name,
                "width": image.width,
                "height": image.height,
            }
        )
        remaining.remove(obj.path_id)

    if remaining:
        raise RuntimeError(f"Missing allowlisted textures: {sorted(remaining)}")
    return sorted(exported, key=lambda item: item["file"])


def mono_trees(path: Path) -> list[dict[str, Any]]:
    env = UnityPy.load(str(path))
    return [obj.read_typetree() for obj in env.objects if obj.type.name == "MonoBehaviour"]


def export_localization(root: Path, output_dir: Path) -> dict[str, Any]:
    shared_path = root / "localization-assets-shared_assets_all.bundle"
    simplified_path = root / "localization-string-tables-chinese(simplified)(zh-hans)_assets_all.bundle"

    shared_tables: dict[str, dict[int, str]] = {}
    for tree in mono_trees(shared_path):
        name = tree.get("m_Name", "")
        if not name.endswith("Shared Data"):
            continue
        shared_tables[name.removesuffix(" Shared Data")] = {
            int(entry["m_Id"]): entry["m_Key"] for entry in tree.get("m_Entries", [])
        }

    tables: dict[str, list[dict[str, Any]]] = {}
    for tree in mono_trees(simplified_path):
        name = tree.get("m_Name", "")
        table_name = re.sub(r"_zh-Hans$", "", name)
        keys = shared_tables.get(table_name, {})
        entries = []
        for item in tree.get("m_TableData", []):
            entry_id = int(item["m_Id"])
            entries.append(
                {
                    "id": entry_id,
                    "key": keys.get(entry_id, f"unknown_{entry_id}"),
                    "value": item.get("m_Localized", ""),
                }
            )
        tables[table_name] = entries

    payload = {
        "schemaVersion": 1,
        "locale": "zh-Hans",
        "source": str(simplified_path),
        "tables": tables,
        "entryCount": sum(len(entries) for entries in tables.values()),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / "localization.zh-Hans.json"
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    args = parse_args()
    root = bundle_root(args.game_root.resolve())
    if not root.exists():
        raise SystemExit(f"Addressables directory not found: {root}")

    assets = export_images(root, args.public_dir)
    localization = export_localization(root, args.data_dir)
    manifest = {
        "schemaVersion": 1,
        "assets": assets,
        "localizationEntries": localization["entryCount"],
    }
    (args.data_dir / "asset-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Exported {len(assets)} images and {localization['entryCount']} localized strings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
