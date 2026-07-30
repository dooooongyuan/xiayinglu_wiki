#!/usr/bin/env python3
"""Extract medicine records, effects, recipes, sources, and icons for the wiki."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import UnityPy

from extract_wuxue import clean_source_name, read_json, resolve_bundle, text_asset_tables


DEFAULT_GAME_ROOT = Path(r"F:\SteamLibrary\steamapps\common\侠影录")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_BUNDLE_NAME = "defaultpackage_assets_buildresources_db.bundle"
ICON_BUNDLE_NAME = "defaultpackage_assets_buildresources_prefab_uisprite_ui_item.bundle"

QUALITY_LABELS = {
    1: "普通",
    2: "精良",
    3: "稀有",
    4: "珍奇",
    5: "绝世",
}

ATTRIBUTE_LABELS = {
    1: "生命",
    3: "真气",
    5: "气势",
    21: "攻击",
    22: "防御",
    25: "暴击",
    26: "暴击伤害",
    28: "速度",
    31: "减伤",
    37: "增伤",
    51: "武",
    52: "敏",
    53: "体",
    54: "念",
    55: "意",
    81: "阳",
    82: "阴",
    83: "柔",
    84: "刚",
    85: "毒",
    110: "经脉点数",
}

INNER_ATTRIBUTES = {"阳", "阴", "柔", "刚", "毒"}


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
        default=PROJECT_ROOT / "wiki" / "src" / "data" / "danyao.generated.json",
    )
    parser.add_argument(
        "--icon-dir",
        type=Path,
        default=PROJECT_ROOT / "wiki" / "public" / "game" / "danyao",
    )
    return parser.parse_args()


def clean_text(value: Any) -> str:
    text = str(value or "").replace("\\n", "\n")
    text = re.sub(r"<color(?:=[^>]+)?>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"</color>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", text).strip()


def compact_number(value: float) -> int | float:
    return int(value) if value.is_integer() else round(value, 2)


def item_name(
    item_id: int,
    item_by_id: dict[int, dict[str, Any]],
    string_by_id: dict[int, dict[str, Any]],
) -> str:
    item = item_by_id.get(item_id, {})
    string_row = string_by_id.get(int(item.get("nameId") or 0), {})
    return clean_text(string_row.get("_str")) or f"物品 {item_id}"


def loot_source_name(value: Any) -> str:
    name = clean_source_name(value)
    name = re.sub(r"\d+$", "", name).strip()
    return name or "未知来源"


def summarized_names(names: set[str], unit: str, limit: int = 5) -> str:
    ordered = sorted(names)
    visible = ordered[:limit]
    text = "、".join(visible)
    remaining = len(ordered) - len(visible)
    return f"{text}等 {len(ordered)} {unit}" if remaining else text


def medicine_category(subtype: int, attribute: str) -> str:
    if subtype == 2:
        return "恢复"
    if attribute in INNER_ATTRIBUTES:
        return "内劲"
    if subtype == 3:
        return "功能"
    return "属性"


def acquisition_sources(
    item_id: int,
    recipe: dict[str, Any],
    materials: list[dict[str, Any]],
    shop_by_item: dict[int, list[dict[str, Any]]],
    merchants_by_group: dict[int, list[dict[str, str]]],
    loot_by_item: dict[int, list[dict[str, Any]]],
    loot_names_by_group: dict[int, set[str]],
) -> list[dict[str, str]]:
    material_text = "、".join(
        f"{material['name']} × {material['count']}" for material in materials
    )
    money = int(recipe.get("costmoney") or 0)
    money_text = f"，另需 {money:,} 铜钱" if money else ""
    sources: list[dict[str, str]] = [
        {
            "type": "alchemy",
            "title": "苍影阁 · 燕衔芦炼制",
            "detail": f"消耗 {material_text}{money_text}。",
        }
    ]

    seen_shops: set[tuple[str, int, str]] = set()
    for shop_row in shop_by_item.get(item_id, []):
        group_id = int(shop_row["group"])
        merchants = merchants_by_group.get(group_id) or [
            {"title": "行商", "shopTitle": "交易"}
        ]
        cost = int(shop_row["buyCost"])
        for merchant in merchants:
            key = (merchant["title"], cost, merchant["shopTitle"])
            if key in seen_shops:
                continue
            seen_shops.add(key)
            merchant_name = merchant["title"].rsplit(" · ", 1)[-1]
            sources.append(
                {
                    "type": "shop",
                    "title": merchant["title"],
                    "detail": f"向{merchant_name}购买（{merchant['shopTitle']}），花费 {cost:,} 铜钱。",
                }
            )

    chest_names: set[str] = set()
    enemy_names: set[str] = set()
    has_unmapped_loot = False
    for loot_row in loot_by_item.get(item_id, []):
        names = loot_names_by_group.get(int(loot_row["groupId"]), set())
        if not names:
            has_unmapped_loot = True
            continue
        for name in names:
            if "宝箱" in name or "采集物" in name:
                chest_names.add(name)
            else:
                enemy_names.add(name)

    if chest_names:
        sources.append(
            {
                "type": "chest",
                "title": "宝箱或场景收集",
                "detail": f"可从{summarized_names(chest_names, '处来源')}中获得。",
            }
        )
    if enemy_names:
        sources.append(
            {
                "type": "drop",
                "title": "敌人掉落",
                "detail": f"可由{summarized_names(enemy_names, '类敌人')}掉落。",
            }
        )
    if has_unmapped_loot:
        sources.append(
            {
                "type": "event",
                "title": "副本或战斗奖励",
                "detail": "该丹药还存在未绑定到具体场景对象的战利品记录，可由对应阶段的副本或战斗奖励获得。",
            }
        )

    unique: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for source in sources:
        key = (source["type"], source["title"], source["detail"])
        if key not in seen:
            seen.add(key)
            unique.append(source)
    return unique


def export_icons(path: Path, icon_targets: dict[str, list[Path]]) -> None:
    expected = {target.resolve() for targets in icon_targets.values() for target in targets}
    output_dirs = {target.parent.resolve() for targets in icon_targets.values() for target in targets}
    for output_dir in output_dirs:
        if output_dir.exists():
            for existing in output_dir.glob("*.png"):
                if existing.resolve() not in expected:
                    existing.unlink()

    env = UnityPy.load(str(path))
    remaining = set(icon_targets)
    for obj in env.objects:
        if obj.type.name != "Sprite":
            continue
        data = obj.read()
        targets = icon_targets.get(data.m_Name)
        if not targets:
            continue
        image = data.image
        for target in targets:
            target.parent.mkdir(parents=True, exist_ok=True)
            image.save(target, optimize=True)
        remaining.discard(data.m_Name)
    if remaining:
        raise RuntimeError(f"Missing medicine icons: {sorted(remaining)}")


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
            "item_base",
            "liandanprototype",
            "loot_items",
            "mapinfo",
            "npc_interact",
            "npc_prototype",
            "shop",
            "spelleffect",
            "spellprotype",
            "stringlang",
        },
    )

    item_by_id = {int(row["id"]): row for row in tables["item_base"]}
    string_by_id = {int(row["id"]): row for row in tables["stringlang"]}
    spell_by_id = {int(row["id"]): row for row in tables["spellprotype"]}
    effect_by_id = {int(row["id"]): row for row in tables["spelleffect"]}

    shop_by_item: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in tables["shop"]:
        shop_by_item[int(row["itemid"])].append(row)
    loot_by_item: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in tables["loot_items"]:
        loot_by_item[int(row["lootItemId"])].append(row)

    map_names = {
        int(row["id"]): clean_text(row.get("name")) for row in tables["mapinfo"]
    }
    merchant_titles = {
        int(row["npcId"]): clean_text(row.get("title")) or "商店"
        for row in tables["npc_interact"]
        if int(row.get("subtype") or 0) == 5
    }
    merchants_by_group: dict[int, list[dict[str, str]]] = defaultdict(list)
    loot_names_by_group: dict[int, set[str]] = defaultdict(set)
    for row in tables["npc_prototype"]:
        npc_id = int(row["id"])
        source_name = loot_source_name(row.get("name"))
        map_name = map_names.get(int(row.get("mapId") or 0), "").removesuffix("室内")
        loot_group = int(row.get("lootGroupId") or 0)
        if loot_group and source_name != "未知来源":
            loot_names_by_group[loot_group].add(
                f"{map_name} · {source_name}" if map_name and map_name not in source_name else source_name
            )
        shop_group = int(row.get("miscValue2") or 0)
        if npc_id in merchant_titles and shop_group:
            title = " · ".join(value for value in (map_name, source_name) if value)
            merchant = {
                "title": title or source_name or "商店",
                "shopTitle": merchant_titles[npc_id],
            }
            if merchant not in merchants_by_group[shop_group]:
                merchants_by_group[shop_group].append(merchant)

    entries: list[dict[str, Any]] = []
    icon_targets: dict[str, list[Path]] = defaultdict(list)
    for recipe in tables["liandanprototype"]:
        item_id = int(recipe["id"])
        item = item_by_id.get(item_id)
        if item is None:
            raise RuntimeError(f"Medicine recipe {item_id} has no item record")
        spell = spell_by_id.get(int(item.get("spellId") or 0))
        if spell is None:
            raise RuntimeError(f"Medicine {item_id} has no use spell")
        effect_ids = [
            int(spell.get(f"effect{index}") or 0)
            for index in range(1, 11)
            if int(spell.get(f"effect{index}") or 0)
        ]
        if not effect_ids:
            raise RuntimeError(f"Medicine {item_id} has no use effect")
        effect = effect_by_id[effect_ids[0]]
        attribute_code = int(effect.get("buffMisValue1") or effect.get("misvalue1") or 0)
        attribute = ATTRIBUTE_LABELS.get(attribute_code)
        if attribute is None:
            raise RuntimeError(
                f"Unknown medicine attribute code {attribute_code} for item {item_id}"
            )

        name_row = string_by_id.get(int(item.get("nameId") or 0), {})
        name = clean_text(name_row.get("_str")) or str(recipe.get("name") or item_id)
        traditional_name = clean_text(name_row.get("_strTW"))
        raw_description = str(
            string_by_id.get(int(item.get("baseDesc") or 0), {}).get("_str") or ""
        ).replace("\\n", "\n")
        description_parts = [clean_text(part) for part in raw_description.split("\n\n") if clean_text(part)]
        description = description_parts[0] if description_parts else "暂无说明。"
        usage_description = next(
            (part for part in description_parts[1:] if part.startswith("使用后")),
            clean_text(effect.get("buffdescription")),
        )
        value = float(effect.get("basevalue1") or 0)
        use_limit = int(item.get("useMaxCount") or 0)
        is_permanent = use_limit > 0
        subtype = int(item.get("subType") or 0)
        category = medicine_category(subtype, attribute)
        materials = [
            {
                "id": material_id,
                "name": item_name(material_id, item_by_id, string_by_id),
                "count": int(recipe.get(f"srcCount{index}") or 0),
            }
            for index in range(6)
            if (material_id := int(recipe.get(f"srcId{index}") or 0))
            and int(recipe.get(f"srcCount{index}") or 0)
        ]
        quality = int(item.get("quality") or 1)
        icon_name = str(item.get("icon") or "")
        icon_targets[icon_name].append(args.icon_dir / f"{item_id}.png")

        entries.append(
            {
                "id": item_id,
                "name": name,
                "traditionalName": traditional_name,
                "description": description,
                "usageDescription": usage_description,
                "category": category,
                "quality": quality,
                "qualityLabel": QUALITY_LABELS[quality],
                "icon": f"/game/danyao/{item_id}.png",
                "iconSourceName": icon_name,
                "effect": {
                    "attributeCode": attribute_code,
                    "attribute": attribute,
                    "value": compact_number(value),
                    "durationSeconds": compact_number(float(effect.get("buffDuration") or 0)),
                    "description": clean_text(effect.get("buffdescription")) or usage_description,
                },
                "useCooldownSeconds": compact_number(float(item.get("useCooldown") or 0)),
                "isPermanent": is_permanent,
                "isSpecial": is_permanent,
                "useLimit": use_limit if is_permanent else None,
                "maximumGain": compact_number(value * use_limit) if is_permanent else None,
                "recipe": {
                    "costMoney": int(recipe.get("costmoney") or 0),
                    "materials": materials,
                },
                "acquisitionSources": acquisition_sources(
                    item_id,
                    recipe,
                    materials,
                    shop_by_item,
                    merchants_by_group,
                    loot_by_item,
                    loot_names_by_group,
                ),
            }
        )

    category_order = {"内劲": 0, "属性": 1, "恢复": 2, "功能": 3}
    entries.sort(key=lambda entry: (category_order[entry["category"]], entry["quality"], entry["id"]))
    export_icons(icon_path, icon_targets)

    payload = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "gameVersion": index["yooAsset"]["packageVersion"],
        "counts": {
            "entries": len(entries),
            "categories": dict(sorted(Counter(entry["category"] for entry in entries).items())),
            "qualities": dict(sorted(Counter(str(entry["quality"]) for entry in entries).items())),
            "attributes": dict(sorted(Counter(entry["effect"]["attribute"] for entry in entries).items())),
            "permanent": sum(entry["isPermanent"] for entry in entries),
            "special": sum(entry["isSpecial"] for entry in entries),
        },
        "entries": entries,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"Exported {len(entries)} medicine records and {sum(len(paths) for paths in icon_targets.values())} icons "
        f"for game version {payload['gameVersion']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
