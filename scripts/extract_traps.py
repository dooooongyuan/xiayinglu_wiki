#!/usr/bin/env python3
"""Extract trap items, recipes, training requirements, effects, and icons for the wiki."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from extract_danyao import QUALITY_LABELS, clean_text, export_icons
from extract_wuxue import read_json, resolve_bundle, text_asset_tables


DEFAULT_GAME_ROOT = Path(r"F:\SteamLibrary\steamapps\common\侠影录")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_BUNDLE_NAME = "defaultpackage_assets_buildresources_db.bundle"
ICON_BUNDLE_NAME = "defaultpackage_assets_buildresources_prefab_uisprite_ui_item.bundle"

EFFECT_KEYWORDS = [
    ("流血", "流血"),
    ("中毒", "中毒"),
    ("减速", "减速"),
    ("击飞", "击飞"),
    ("灼烧", "灼烧"),
    ("冻结", "冻结"),
    ("冻伤", "冻伤"),
    ("眩晕", "眩晕"),
    ("落雷", "雷击"),
    ("闪电", "雷击"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-root", type=Path, default=DEFAULT_GAME_ROOT)
    parser.add_argument(
        "--index",
        type=Path,
        default=PROJECT_ROOT / "wiki" / "src" / "data" / "game-index.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "wiki" / "src" / "data" / "traps.generated.json",
    )
    parser.add_argument(
        "--icon-dir",
        type=Path,
        default=PROJECT_ROOT / "wiki" / "public" / "game" / "traps",
    )
    return parser.parse_args()


def item_name(
    item_id: int,
    item_by_id: dict[int, dict[str, Any]],
    string_by_id: dict[int, dict[str, Any]],
) -> str:
    item = item_by_id.get(item_id, {})
    row = string_by_id.get(int(item.get("nameId") or 0), {})
    return clean_text(row.get("_str")) or f"物品 {item_id}"


def gameplay_summary(description: str) -> str:
    parts = [part.strip() for part in re.split(r"(?<=。)", description) if part.strip()]
    return parts[-1] if parts else description


def effect_tags(description: str) -> list[str]:
    tags = ["伤害"]
    for keyword, label in EFFECT_KEYWORDS:
        if keyword in description and label not in tags:
            tags.append(label)
    return tags


def main() -> int:
    args = parse_args()
    game_root = args.game_root.resolve()
    package_root = game_root / "xiayinglu_Data" / "StreamingAssets" / "yougou" / "DefaultPackage"
    index = read_json(args.index)
    db_path = resolve_bundle(index, package_root, DB_BUNDLE_NAME)
    icon_path = resolve_bundle(index, package_root, ICON_BUNDLE_NAME)
    tables = text_asset_tables(
        db_path,
        {
            "dazaoprototype",
            "item_base",
            "item_equip",
            "spelleffect",
            "spellprotype",
            "stringlang",
            "xiuxi_graph",
            "xiuxi_node",
        },
    )

    item_by_id = {int(row["id"]): row for row in tables["item_base"]}
    string_by_id = {int(row["id"]): row for row in tables["stringlang"]}
    recipe_by_id = {int(row["id"]): row for row in tables["dazaoprototype"]}
    spell_by_id = {int(row["id"]): row for row in tables["spellprotype"]}
    effect_by_id = {int(row["id"]): row for row in tables["spelleffect"]}
    training_by_item = {
        int(row["itemId"]): row
        for row in tables["xiuxi_node"]
        if int(row.get("type") or 0) == 10 and int(row.get("itemId") or 0)
    }
    trap_ids = {
        int(row["id"])
        for row in tables["item_equip"]
        if int(row.get("partTypeId") or -1) == 6
    }
    trap_rows = [
        row for row in tables["item_base"]
        if int(row["id"]) in trap_ids and int(row.get("type") or 0) == 10
    ]

    prerequisite_by_group: dict[int, list[int]] = defaultdict(list)
    for edge in tables["xiuxi_graph"]:
        start = int(edge.get("startNodeGroup") or 0)
        end = int(edge.get("endNodeGroup") or 0)
        if start and end:
            prerequisite_by_group[end].append(start)
    training_by_group = {int(row["group"]): row for row in training_by_item.values()}

    entries: list[dict[str, Any]] = []
    icon_targets: dict[str, list[Path]] = defaultdict(list)
    for item in trap_rows:
        item_id = int(item["id"])
        recipe = recipe_by_id.get(item_id)
        training = training_by_item.get(item_id)
        spell = spell_by_id.get(int(item.get("spellId") or 0), {})
        primary_effect = effect_by_id.get(int(spell.get("effect1") or 0), {})
        if not recipe or not training or not primary_effect:
            raise RuntimeError(f"Trap {item_id} is missing recipe, training, or effect data")

        name_row = string_by_id.get(int(item.get("nameId") or 0), {})
        name = clean_text(name_row.get("_str")) or f"陷阱 {item_id}"
        traditional_name = clean_text(name_row.get("_strTW"))
        description = clean_text(string_by_id.get(int(item.get("baseDesc") or 0), {}).get("_str"))
        materials = [
            {
                "id": material_id,
                "name": item_name(material_id, item_by_id, string_by_id),
                "count": int(recipe.get(f"srcCount{position}") or 0),
            }
            for position in range(6)
            if (material_id := int(recipe.get(f"srcId{position}") or 0))
            and int(recipe.get(f"srcCount{position}") or 0)
        ]
        group = int(training["group"])
        prerequisites = [
            {
                "nodeId": int(previous["id"]),
                "itemId": int(previous["itemId"]),
                "name": item_name(int(previous["itemId"]), item_by_id, string_by_id),
            }
            for previous_group in prerequisite_by_group.get(group, [])
            if (previous := training_by_group.get(previous_group))
        ]
        quality = int(item.get("quality") or 1)
        icon_name = clean_text(item.get("icon"))
        icon_targets[icon_name].append(args.icon_dir / f"{item_id}.png")
        tags = effect_tags(description)
        entries.append(
            {
                "id": item_id,
                "name": name,
                "traditionalName": traditional_name,
                "description": description,
                "effectSummary": gameplay_summary(description),
                "effectTags": tags,
                "quality": quality,
                "qualityLabel": QUALITY_LABELS[quality],
                "icon": f"/game/traps/{item_id}.png",
                "iconSourceName": icon_name,
                "useCooldownSeconds": int(item.get("useCooldown") or 0),
                "stackLimit": int(item.get("overlapMax") or 0),
                "effect": {
                    "durationSeconds": int(primary_effect.get("trapDuration") or 0),
                    "triggerIntervalSeconds": int(primary_effect.get("trapInterval") or 0),
                    "triggerMode": "持续检测" if float(primary_effect.get("trapInterval") or 0) <= 1 else "单次触发",
                },
                "unlock": {
                    "nodeId": int(training["id"]),
                    "points": int(training.get("activeDianShu") or 0),
                    "prerequisites": prerequisites,
                },
                "recipe": {
                    "costMoney": int(recipe.get("costmoney") or 0),
                    "materials": materials,
                },
                "acquisitionSources": [
                    {
                        "type": "crafting",
                        "title": "打造制作",
                        "detail": f"激活{name}修习节点后，可在打造界面消耗材料与 {int(recipe.get('costmoney') or 0):,} 铜钱制作。",
                    }
                ],
            }
        )

    entries.sort(key=lambda entry: (entry["quality"], entry["id"]))
    export_icons(icon_path, icon_targets)
    payload = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "gameVersion": index["yooAsset"]["packageVersion"],
        "sources": {
            "databaseTables": [
                "dazaoprototype.json",
                "item_base.json",
                "item_equip.json",
                "spelleffect.json",
                "spellprotype.json",
                "stringlang.json",
                "xiuxi_graph.json",
                "xiuxi_node.json",
            ],
            "iconBundle": ICON_BUNDLE_NAME,
        },
        "counts": {
            "entries": len(entries),
            "qualities": dict(sorted(Counter(str(entry["quality"]) for entry in entries).items())),
            "effectTags": dict(sorted(Counter(tag for entry in entries for tag in entry["effectTags"]).items())),
        },
        "entries": entries,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Exported {len(entries)} trap records and {sum(len(paths) for paths in icon_targets.values())} icons")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
