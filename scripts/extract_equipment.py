#!/usr/bin/env python3
"""Extract equipment records, attributes, affix pools, and icons for the wiki."""

from __future__ import annotations

import argparse
import json
import math
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

CATEGORY_BY_PART = {
    0: "武器",
    1: "防具",
    2: "防具",
    3: "饰品",
    4: "宝物",
    5: "暗器",
}

SUBTYPE_BY_PART = {
    (0, 0): "剑",
    (0, 1): "刀",
    (0, 2): "枪",
    (0, 3): "拳套",
    (1, 20): "衣服",
    (2, 40): "鞋靴",
    (3, 60): "饰品",
    (4, 80): "秘宝",
    (5, 5): "暗器",
}

QUALITY_LABELS = {
    1: "普通",
    2: "精良",
    3: "稀有",
    4: "珍奇",
    5: "绝世",
}

ATTRIBUTE_FALLBACKS = {
    0: "生命",
    2: "真气",
    4: "气势",
    21: "攻击",
    22: "防御",
    25: "暴击",
    27: "暴抗",
    28: "速度",
}

POWER_FIELDS = {
    "attack": ("攻击", "weiLiGongJi"),
    "yang": ("阳", "weiLiYang"),
    "yin": ("阴", "weiLiYin"),
    "soft": ("柔", "weiLiRou"),
    "hard": ("刚", "weiLiGang"),
    "poison": ("毒", "weiLiDu"),
}

PLAYER_LEVEL_PATTERN = re.compile(r"CheckPlayerLevel\|(\d+)")
TRAINING_NODE_PATTERN = re.compile(r"CheckXiuXiNodeIdActiveCondition\|(\d+)")
CLUE_PATTERN = re.compile(r"XianSuoActive\|(\d+)")


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
        default=PROJECT_ROOT / "wiki" / "src" / "data" / "equipment.generated.json",
    )
    parser.add_argument(
        "--icon-dir",
        type=Path,
        default=PROJECT_ROOT / "wiki" / "public" / "game" / "equipment",
    )
    return parser.parse_args()


def clean_text(value: Any) -> str:
    text = str(value or "").replace("\\n", "\n")
    text = re.sub(r"<color(?:=[^>]+)?>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"</color>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", text).strip()


def compact_number(value: float) -> str:
    if value.is_integer():
        return f"{int(value):,}"
    return f"{value:.2f}".rstrip("0").rstrip(".")


def affix_value_text(row: dict[str, Any], type_row: dict[str, Any]) -> str:
    minimum = float(row["min"])
    maximum = float(row["max"])
    is_percent = int(type_row.get("isPCT") or 0) == 1
    if is_percent:
        divisor = abs(float(type_row.get("param3") or 0)) or 10000
        minimum = minimum * 100 / divisor
        maximum = maximum * 100 / divisor
    suffix = "%" if is_percent else ""
    if math.isclose(minimum, maximum):
        return f"{compact_number(minimum)}{suffix}"
    return f"{compact_number(minimum)}–{compact_number(maximum)}{suffix}"


def affix_description(
    row: dict[str, Any],
    type_row: dict[str, Any],
    string_by_id: dict[int, dict[str, Any]],
    value_text: str,
) -> str:
    description = clean_text(string_by_id.get(int(row.get("desId") or 0), {}).get("_str"))
    if not description:
        description = f"{type_row.get('name') or '额外属性'} +{value_text}"
    description = description.replace("{0:G}", value_text).replace("{effectName}", "对应效果")
    return re.sub(r"\{[^}]+\}", "对应数值", description)


def display_subtype(part_type: int, subtype_id: int, item_id: int) -> str:
    if part_type == 4:
        if 36000 <= item_id < 36100:
            return "傀儡"
        if 36100 <= item_id < 36200:
            return "武魄"
    return SUBTYPE_BY_PART.get((part_type, subtype_id), "其他")


def socket_outcomes(minimum: int, maximum: int) -> list[dict[str, Any]]:
    """Return the equally weighted socket counts used by the game's item roll."""
    span = maximum - minimum + 1
    probability = round(100 / span, 2)
    return [
        {"count": count, "probability": probability}
        for count in range(minimum, maximum + 1)
    ]


def socket_config(
    equip_row: dict[str, Any],
    category: str,
    quality_mode: str,
    display_quality: int | None,
) -> dict[str, Any]:
    if category not in {"武器", "防具", "饰品"}:
        return {
            "supported": False,
            "minimum": 0,
            "maximum": 0,
            "summary": "不可镶嵌",
            "rules": [],
        }

    minimum = max(int(equip_row.get("miscvaluekongMin") or 0), 0)
    maximum = max(int(equip_row.get("miscvalue") or 0), minimum)
    supported = maximum > 0
    if not supported:
        return {
            "supported": False,
            "minimum": 0,
            "maximum": 0,
            "summary": "不可镶嵌",
            "rules": [
                {
                    "qualityLabel": "全部品质" if quality_mode == "random" else QUALITY_LABELS[display_quality or 1],
                    "qualities": [1, 2, 3, 4, 5] if quality_mode == "random" else [display_quality or 1],
                    "outcomes": [{"count": 0, "probability": 100}],
                }
            ],
        }

    rolled_outcomes = socket_outcomes(minimum, maximum)
    if quality_mode == "random":
        chance_text = compact_number(100 / (maximum - minimum + 1))
        rules = [
            {
                "qualityLabel": "普通",
                "qualities": [1],
                "outcomes": [{"count": 0, "probability": 100}],
            },
            {
                "qualityLabel": "精良及以上",
                "qualities": [2, 3, 4, 5],
                "outcomes": rolled_outcomes,
            },
        ]
        count_text = "/".join(str(count) for count in range(minimum, maximum + 1))
        summary = f"普通 0 孔 · 精良+ {count_text} 孔各 {chance_text}%"
    elif (display_quality or 1) <= 1:
        rules = [
            {
                "qualityLabel": QUALITY_LABELS[display_quality or 1],
                "qualities": [display_quality or 1],
                "outcomes": [{"count": 0, "probability": 100}],
            }
        ]
        summary = "不可镶嵌"
        supported = False
    else:
        rules = [
            {
                "qualityLabel": QUALITY_LABELS[display_quality or 1],
                "qualities": [display_quality or 1],
                "outcomes": rolled_outcomes,
            }
        ]
        if minimum == maximum:
            summary = f"固定 {minimum} 孔"
        else:
            count_text = " / ".join(str(count) for count in range(minimum, maximum + 1))
            chance_text = compact_number(100 / (maximum - minimum + 1))
            summary = f"{count_text} 孔各 {chance_text}%"

    return {
        "supported": supported,
        "minimum": minimum if supported else 0,
        "maximum": maximum if supported else 0,
        "summary": summary,
        "rules": rules,
    }


def item_name(
    item_id: int,
    item_by_id: dict[int, dict[str, Any]],
    string_by_id: dict[int, dict[str, Any]],
) -> str:
    item = item_by_id.get(item_id, {})
    name_row = string_by_id.get(int(item.get("nameId") or 0), {})
    return clean_text(name_row.get("_str")) or f"物品 {item_id}"


def recipe_material_text(
    row: dict[str, Any],
    slot_count: int,
    item_by_id: dict[int, dict[str, Any]],
    string_by_id: dict[int, dict[str, Any]],
) -> str:
    materials: list[str] = []
    for index in range(slot_count):
        material_id = int(row.get(f"srcId{index}") or 0)
        count = int(row.get(f"srcCount{index}") or 0)
        if material_id and count:
            materials.append(f"{item_name(material_id, item_by_id, string_by_id)} × {count}")
    return "、".join(materials) or "无需额外材料"


def forge_requirement(
    condition: Any,
    training_node_by_id: dict[int, dict[str, Any]],
    clue_by_id: dict[int, dict[str, Any]],
) -> str:
    condition_text = str(condition or "")
    node_match = TRAINING_NODE_PATTERN.search(condition_text)
    if node_match:
        node = training_node_by_id.get(int(node_match.group(1)), {})
        node_name = clean_text(node.get("name")) or "对应暗器"
        points = int(node.get("activeDianShu") or 0)
        point_text = f"（消耗 {points} 点）" if points else ""
        return f"；需先解锁“{node_name}”修习节点{point_text}"
    clue_match = CLUE_PATTERN.search(condition_text)
    if clue_match:
        clue = clue_by_id.get(int(clue_match.group(1)), {})
        clue_name = clean_text(clue.get("name")) or "对应线索"
        return f"；需先完成“{clue_name}”线索"
    if condition_text:
        return "；需先满足对应解锁条件"
    return ""


def loot_source_name(value: Any) -> str:
    name = clean_source_name(value)
    name = re.sub(r"\d+$", "", name).strip()
    name = re.sub(r"副本神兵(?:剑|刀|枪|拳套?|缠)?$", "神兵宝箱", name)
    return name or "未知来源"


def summarized_names(names: set[str], unit: str, limit: int = 7) -> str:
    ordered = sorted(names)
    visible = ordered[:limit]
    text = "、".join(visible)
    remaining = len(ordered) - len(visible)
    return f"{text}等 {len(ordered)} {unit}" if remaining else text


def equipment_acquisition_sources(
    item_id: int,
    forge_by_item: dict[int, dict[str, Any]],
    combine_by_item: dict[int, list[dict[str, Any]]],
    shop_by_item: dict[int, list[dict[str, Any]]],
    merchants_by_group: dict[int, list[dict[str, str]]],
    contribution_by_item: dict[int, list[dict[str, Any]]],
    loot_by_item: dict[int, list[dict[str, Any]]],
    loot_names_by_group: dict[int, set[str]],
    npc_owners_by_item: dict[int, set[str]],
    initial_item_ids: set[int],
    item_by_id: dict[int, dict[str, Any]],
    string_by_id: dict[int, dict[str, Any]],
    training_node_by_id: dict[int, dict[str, Any]],
    clue_by_id: dict[int, dict[str, Any]],
) -> list[dict[str, str]]:
    sources: list[dict[str, str]] = []

    if item_id in initial_item_ids:
        sources.append(
            {
                "type": "initial",
                "title": "新游戏初始携带",
                "detail": "创建角色进入游戏后随身携带，无需额外获取。",
            }
        )

    forge_row = forge_by_item.get(item_id)
    if forge_row:
        materials = recipe_material_text(forge_row, 6, item_by_id, string_by_id)
        money = int(forge_row.get("costmoney") or 0)
        requirement = forge_requirement(
            forge_row.get("strShowCondition"), training_node_by_id, clue_by_id
        )
        if materials == "无需额外材料":
            cost_text = f"无需额外材料，花费 {money:,} 铜钱" if money else materials
        else:
            money_text = f"，另需 {money:,} 铜钱" if money else ""
            cost_text = f"消耗 {materials}{money_text}"
        sources.append(
            {
                "type": "forge",
                "title": "天工打造",
                "detail": f"{cost_text}{requirement}。",
            }
        )

    for combine_row in combine_by_item.get(item_id, []):
        material_ids = [
            int(combine_row.get(f"srcId{index}") or 0) for index in range(4)
        ]
        has_named_materials = all(
            material_id == 0 or material_id in item_by_id for material_id in material_ids
        )
        if has_named_materials:
            materials = recipe_material_text(combine_row, 4, item_by_id, string_by_id)
            detail = f"消耗 {materials} 合成。"
        else:
            detail = "在合成系统中使用符合该配方要求的同类装备合成。"
        sources.append(
            {
                "type": "combine",
                "title": "装备合成",
                "detail": detail,
            }
        )

    for shop_row in shop_by_item.get(item_id, []):
        group_id = int(shop_row["group"])
        merchants = merchants_by_group.get(group_id) or [
            {"title": "行商或门派商店", "shopTitle": "商店"}
        ]
        condition = str(shop_row.get("condition") or "")
        level_match = PLAYER_LEVEL_PATTERN.search(condition)
        requirements: list[str] = []
        if level_match:
            requirements.append(f"角色等级 {level_match.group(1)}")
        if condition and "CheckPlayMakerGlobalVariables" in condition:
            requirements.append("相关剧情条件")
        requirement_text = f"；需满足{'、'.join(requirements)}" if requirements else ""
        for merchant in merchants:
            sources.append(
                {
                    "type": "shop",
                    "title": merchant["title"],
                    "detail": f"在{merchant['shopTitle']}花费 {int(shop_row['buyCost']):,} 铜钱购买{requirement_text}。",
                }
            )

    for contribution_row in contribution_by_item.get(item_id, []):
        currency = clean_text(contribution_row.get("contributiontypedes")) or "贡献物资"
        cost = int(contribution_row.get("contributionitemcost") or 0)
        sources.append(
            {
                "type": "contribution",
                "title": "贡献商店",
                "detail": f"消耗 {cost:,} {currency}兑换。",
            }
        )

    chest_names: set[str] = set()
    enemy_names: set[str] = set()
    has_unmapped_loot = False
    for loot_row in loot_by_item.get(item_id, []):
        group_names = loot_names_by_group.get(int(loot_row["groupId"]), set())
        if not group_names:
            has_unmapped_loot = True
            continue
        for source_name in group_names:
            if "宝箱" in source_name or "神兵" in source_name:
                chest_names.add(source_name)
            else:
                enemy_names.add(source_name)

    if chest_names:
        sources.append(
            {
                "type": "chest",
                "title": "场景宝箱",
                "detail": f"开启{summarized_names(chest_names, '处宝箱')}时有机会获得。",
            }
        )
    if enemy_names:
        sources.append(
            {
                "type": "drop",
                "title": "敌人掉落",
                "detail": f"击败{summarized_names(enemy_names, '类敌人')}后有机会获得。",
            }
        )
    if has_unmapped_loot and not chest_names and not enemy_names:
        sources.append(
            {
                "type": "event",
                "title": "副本或战斗奖励",
                "detail": "列入通用装备战利品，可在对应阶段的副本或战斗结算中获得。",
            }
        )

    unique_sources: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for source in sources:
        key = (source["type"], source["title"], source["detail"])
        if key not in seen:
            seen.add(key)
            unique_sources.append(source)
    if not unique_sources:
        owners = npc_owners_by_item.get(item_id, set())
        if owners:
            owner_text = "、".join(sorted(owners))
            detail = f"{owner_text}当前佩戴这件装备，但未发现掉落、商店、打造、合成或宝箱入口，暂不能确认玩家可正常获得。"
        else:
            detail = "当前版本未发现打造、合成、商店、掉落、宝箱或初始携带途径，可能是剧情专属、NPC 专属或尚未开放的装备。"
        unique_sources.append(
            {
                "type": "unknown",
                "title": "未发现常规来源",
                "detail": detail,
            }
        )
    return unique_sources


def export_icons(path: Path, icon_targets: dict[str, list[Path]]) -> None:
    expected_targets = {target.resolve() for targets in icon_targets.values() for target in targets}
    output_dirs = {target.parent.resolve() for targets in icon_targets.values() for target in targets}
    for output_dir in output_dirs:
        if output_dir.exists():
            for existing in output_dir.glob("*.png"):
                if existing.resolve() not in expected_targets:
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
        raise RuntimeError(f"Missing equipment icons: {sorted(remaining)}")


def main() -> int:
    args = parse_args()
    game_root = args.game_root.resolve()
    package_root = game_root / "xiayinglu_Data" / "StreamingAssets" / "yougou" / "DefaultPackage"
    index = read_json(args.index)
    db_path = resolve_bundle(index, package_root, DB_BUNDLE_NAME)
    icon_bundle_path = resolve_bundle(index, package_root, ICON_BUNDLE_NAME)
    tables = text_asset_tables(
        db_path,
        {
            "dazaoprototype",
            "gongxianshop",
            "item_base",
            "item_combine",
            "item_equip",
            "loot_items",
            "mapinfo",
            "npc_attribute_base",
            "npc_interact",
            "npc_prototype",
            "player_prototype",
            "shop",
            "spellprotype",
            "stringlang",
            "wordentry",
            "wordentrytype",
            "xiansuo",
            "xiuxi_node",
        },
    )

    item_by_id = {int(row["id"]): row for row in tables["item_base"]}
    string_by_id = {int(row["id"]): row for row in tables["stringlang"]}
    spell_by_id = {int(row["id"]): row for row in tables["spellprotype"]}
    word_type_by_id = {int(row["id"]): row for row in tables["wordentrytype"]}

    attributes_by_group: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in tables["npc_attribute_base"]:
        attributes_by_group[int(row["formulaGroupId"])].append(row)

    attribute_names = dict(ATTRIBUTE_FALLBACKS)
    for row in tables["wordentrytype"]:
        if int(row.get("wordFunctionType") or -1) != 0:
            continue
        attribute_type = int(row.get("param0") or 0)
        name = clean_text(row.get("name"))
        if name:
            attribute_names.setdefault(attribute_type, name)

    affixes_by_group: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in tables["wordentry"]:
        affixes_by_group[int(row["group"])].append(row)

    forge_by_item = {int(row["id"]): row for row in tables["dazaoprototype"]}
    combine_by_item: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in tables["item_combine"]:
        combine_by_item[int(row["targetItemid"])].append(row)
    shop_by_item: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in tables["shop"]:
        shop_by_item[int(row["itemid"])].append(row)
    contribution_by_item: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in tables["gongxianshop"]:
        contribution_by_item[int(row["itemid"])].append(row)
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
    npc_owners_by_item: dict[int, set[str]] = defaultdict(set)
    for row in tables["npc_prototype"]:
        npc_id = int(row["id"])
        raw_name = row.get("name")
        source_name = loot_source_name(raw_name)
        map_name = map_names.get(int(row.get("mapId") or 0), "").removesuffix("室内")
        if map_name and map_name not in source_name:
            source_name = f"{map_name} · {source_name}"
        loot_group_id = int(row.get("lootGroupId") or 0)
        if loot_group_id and source_name != "未知来源":
            loot_names_by_group[loot_group_id].add(source_name)
        shop_group_id = int(row.get("miscValue2") or 0)
        if npc_id in merchant_titles and shop_group_id:
            merchant_name = loot_source_name(raw_name)
            title = " · ".join(value for value in (map_name, merchant_name) if value)
            merchant = {
                "title": title or merchant_name or "商店",
                "shopTitle": merchant_titles[npc_id],
            }
            if merchant not in merchants_by_group[shop_group_id]:
                merchants_by_group[shop_group_id].append(merchant)
        owner_name = loot_source_name(raw_name)
        for equipped_item in str(row.get("equip") or "").split("|"):
            if equipped_item.isdecimal() and owner_name != "未知来源":
                npc_owners_by_item[int(equipped_item)].add(owner_name)

    first_player = min(tables["player_prototype"], key=lambda row: int(row["id"]))
    initial_item_ids = {
        int(value)
        for value in str(first_player.get("initEquip") or "").split("|")
        if value.isdecimal()
    }
    initial_anqi = str(first_player.get("initAnQi") or "").split("|", 1)[0]
    if initial_anqi.isdecimal():
        initial_item_ids.add(int(initial_anqi))

    training_node_by_id = {
        int(row["id"]): row for row in tables["xiuxi_node"]
    }
    clue_by_id = {int(row["id"]): row for row in tables["xiansuo"]}

    entries: list[dict[str, Any]] = []
    icon_targets: dict[str, list[Path]] = defaultdict(list)
    category_order = {name: index for index, name in enumerate(["武器", "暗器", "防具", "饰品", "宝物"])}

    for equip_row in tables["item_equip"]:
        part_type = int(equip_row["partTypeId"])
        if part_type not in CATEGORY_BY_PART:
            continue
        item_id = int(equip_row["id"])
        item = item_by_id.get(item_id)
        if item is None:
            continue

        category = CATEGORY_BY_PART[part_type]
        # NPC-held weapon copies also appear in item_equip, but have no player-facing
        # attribute formula or affix group. Keep the actual player equipment records.
        if category == "武器" and not int(item.get("attributeId") or 0):
            continue
        subtype = display_subtype(part_type, int(equip_row.get("subTypeId") or 0), item_id)
        level = int(item.get("level") or 0)
        raw_quality = int(item.get("quality") or 0)
        group_id = int(item.get("wordentrygroup") or 0)
        if raw_quality == 0 and category in {"武器", "防具", "饰品"} and group_id:
            quality_mode = "random"
            display_quality: int | None = None
            quality_label = "品质随机"
        else:
            quality_mode = "fixed"
            display_quality = max(raw_quality, 1)
            quality_label = QUALITY_LABELS[display_quality]

        fixed_attributes: list[dict[str, Any]] = []
        attribute_id = int(item.get("attributeId") or 0)
        for attribute in attributes_by_group.get(attribute_id, []):
            minimum = float(attribute["minRandom"])
            maximum = float(attribute["maxRandom"])
            if math.isclose(minimum, maximum) and math.isclose(minimum, 0):
                continue
            value = compact_number(minimum) if math.isclose(minimum, maximum) else f"{compact_number(minimum)}–{compact_number(maximum)}"
            fixed_attributes.append(
                {
                    "name": attribute_names.get(int(attribute["attriType"]), f"属性 {attribute['attriType']}"),
                    "value": value,
                    "chance": int(attribute.get("chance") or 10000) / 100,
                }
            )

        spell_id = int(item.get("miscvalue") or 0) if category == "暗器" else 0
        spell = spell_by_id.get(spell_id, {})
        combat_power = {
            key: {"label": label, "value": int(spell.get(field) or 0)}
            for key, (label, field) in POWER_FIELDS.items()
            if int(spell.get(field) or 0) > 0
        }
        if category == "暗器":
            energy = int(item.get("anqiCostEnergy") or 0)
            recover_cd = float(item.get("anqiRecoverCD") or 0)
            if energy:
                fixed_attributes.append({"name": "暗器能量", "value": str(energy), "chance": 100})
            if recover_cd:
                fixed_attributes.append({"name": "恢复时间", "value": f"{compact_number(recover_cd)} 秒", "chance": 100})

        candidate_rows = sorted(affixes_by_group.get(group_id, []), key=lambda row: int(row["id"]))
        candidates: list[dict[str, Any]] = []
        for row in candidate_rows:
            type_row = word_type_by_id.get(int(row["wordEntryTypeId"]), {})
            value_text = affix_value_text(row, type_row)
            affix_quality = max(int(row.get("quality") or 1), 1)
            candidates.append(
                {
                    "id": int(row["id"]),
                    "name": clean_text(type_row.get("name")) or f"词条 {row['id']}",
                    "description": affix_description(row, type_row, string_by_id, value_text),
                    "value": value_text,
                    "quality": affix_quality,
                    "qualityLabel": QUALITY_LABELS.get(affix_quality, "普通"),
                    "weight": int(row.get("rate") or 0),
                }
            )

        configured_min = int(item.get("wordentrycountMin") or 0)
        configured_max = int(item.get("wordentrycountMax") or 0)
        intrinsic_attributes = candidates if category == "宝物" else []
        if category == "宝物":
            # Treasure templates and save-game instances only contain their named,
            # guaranteed effect. Keep it separate from ordinary equipment affixes.
            candidates = []
            affix_mode = "none"
            slot_min = 0
            slot_max = 0
        elif not candidates:
            affix_mode = "none"
            slot_min = 0
            slot_max = 0
        elif configured_max and configured_min == configured_max == len(candidates):
            affix_mode = "fixed"
            slot_min = configured_min
            slot_max = configured_max
        else:
            affix_mode = "random"
            # Base forge templates store zero here; generated equipment instances
            # in current-version saves carry up to four random affixes.
            slot_min = configured_min
            slot_max = configured_max or 4

        icon_name = clean_text(item.get("icon"))
        icon_path = f"/game/equipment/{item_id}.png"
        icon_targets[icon_name].append(args.icon_dir / f"{item_id}.png")

        power_values = [record["value"] for record in combat_power.values()]
        total_power = sum(power_values) or 1
        for record in combat_power.values():
            record["share"] = round(record["value"] * 100 / total_power)

        entries.append(
            {
                "id": item_id,
                "name": clean_text(string_by_id.get(int(item.get("nameId") or 0), {}).get("_str")) or f"装备 {item_id}",
                "description": clean_text(string_by_id.get(int(item.get("baseDesc") or 0), {}).get("_str")) or "当前版本未提供物品介绍。",
                "category": category,
                "subtype": subtype,
                "level": level,
                "tierLabel": f"{level} 阶" if level else "无阶 / 特殊",
                "quality": display_quality,
                "qualityMode": quality_mode,
                "qualityLabel": quality_label,
                "icon": icon_path,
                "iconSourceName": icon_name,
                "fixedAttributes": fixed_attributes,
                "intrinsicAttributes": intrinsic_attributes,
                "combatPower": combat_power,
                "acquisitionSources": equipment_acquisition_sources(
                    item_id,
                    forge_by_item,
                    combine_by_item,
                    shop_by_item,
                    merchants_by_group,
                    contribution_by_item,
                    loot_by_item,
                    loot_names_by_group,
                    npc_owners_by_item,
                    initial_item_ids,
                    item_by_id,
                    string_by_id,
                    training_node_by_id,
                    clue_by_id,
                ),
                "socketConfig": socket_config(equip_row, category, quality_mode, display_quality),
                "extraAttributes": {
                    "mode": affix_mode,
                    "slotMin": slot_min,
                    "slotMax": slot_max,
                    "candidateCount": len(candidates),
                    "candidates": candidates,
                },
            }
        )

    entries.sort(key=lambda entry: (category_order[entry["category"]], entry["subtype"], entry["level"], entry["id"]))
    export_icons(icon_bundle_path, icon_targets)

    category_counts = Counter(entry["category"] for entry in entries)
    subtype_counts = Counter(entry["subtype"] for entry in entries)
    tier_counts = Counter(str(entry["level"]) for entry in entries if entry["category"] in {"武器", "防具", "饰品"})
    quality_counts = Counter(entry["qualityLabel"] for entry in entries)
    output = {
        "schemaVersion": 2,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "gameVersion": index["yooAsset"]["packageVersion"],
        "sources": {
            "databaseBundle": DB_BUNDLE_NAME,
            "databaseTables": [
                "dazaoprototype.json",
                "gongxianshop.json",
                "item_base.json",
                "item_combine.json",
                "item_equip.json",
                "loot_items.json",
                "mapinfo.json",
                "npc_attribute_base.json",
                "npc_interact.json",
                "npc_prototype.json",
                "player_prototype.json",
                "shop.json",
                "spellprotype.json",
                "stringlang.json",
                "wordentry.json",
                "wordentrytype.json",
                "xiansuo.json",
                "xiuxi_node.json",
            ],
            "iconBundle": ICON_BUNDLE_NAME,
        },
        "counts": {
            "entries": len(entries),
            "categories": dict(category_counts),
            "subtypes": dict(subtype_counts),
            "tiers": dict(tier_counts),
            "qualities": dict(quality_counts),
        },
        "entries": entries,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(entries)} equipment entries to {args.output}")
    print(f"Exported {sum(len(paths) for paths in icon_targets.values())} item icons to {args.icon_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
