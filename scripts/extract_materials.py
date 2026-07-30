#!/usr/bin/env python3
"""Extract crafting materials, usage relationships, sources, and icons for the wiki."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import UnityPy

from extract_danyao import QUALITY_LABELS, clean_text, export_icons, loot_source_name, summarized_names
from extract_wuxue import read_json, resolve_bundle, text_asset_tables


DEFAULT_GAME_ROOT = Path(r"F:\SteamLibrary\steamapps\common\侠影录")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_BUNDLE_NAME = "defaultpackage_assets_buildresources_db.bundle"
ICON_BUNDLE_NAME = "defaultpackage_assets_buildresources_prefab_uisprite_ui_item.bundle"
FUBEN_BUNDLE_NAME = "defaultpackage_assets_buildresources_prefab_battlefuben.bundle"

CATEGORY_BY_SUBTYPE = {
    0: "锻造主材",
    1: "药材",
    2: "锻造辅材",
    10: "铸纹材料",
    11: "铸纹材料",
    12: "铸纹材料",
}
CATEGORY_ORDER = {name: index for index, name in enumerate(["药材", "锻造主材", "锻造辅材", "铸纹材料"])}
NON_READER_SOURCE_MARKERS = ("测试", "模板", "练习木桩", "战斗小师妹", "debug")
COMMON_EARLY_DUNGEONS = ("血雨潇湘", "竹海迷宫", "血炎追踪", "鹤羽飘香")
MAX_DISPLAY_SOURCE_LOCATIONS = 4
SOURCE_LOCATION_ALIASES = {
    "潇湘剑雨": "血雨潇湘",
    "断龙脊": "绝岭断龙",
    "葬花海": "葬花追凶",
    "毒沙帮": "毒沙风雨",
    "缥缈峰雪宫": "缥缈雪宫",
    "连环坞副本低级区": "连环下坞",
    "连环坞下坞": "连环下坞",
    "连环坞副本中级区": "连环中坞",
    "连环坞中坞": "连环中坞",
    "连环坞副本高级区": "连环内坞",
    "连环坞内坞": "连环内坞",
    "五毒宫": "五毒邪宫",
    "星宿海": "星宿腐海",
    "极乐宫": "极乐魅影",
    "移花宫": "移花神宫",
    "逍遥宫": "逍遥遗址",
    "镇狱司": "镇狱毒司",
    "贪狼寨": "贪狼贼寨",
    "雪域寻援": "雪山求援",
    "鹤羽寨": "鹤羽毒寨",
}
SOURCE_LOCATION_ORDER = (
    "血雨潇湘", "竹海迷宫", "血炎追踪", "鹤羽飘香", "血战天鉴",
    "苍鹰探秘", "纨绔子弟", "花海寻药", "绝岭断龙", "葬花追凶",
    "莲花决战", "论武大会", "瓮中捉鳖", "突袭瀚海", "缥缈雪宫",
    "连云腹地", "鹤羽毒寨", "镇狱毒司", "贪狼贼寨", "悔悟悬崖",
    "苍影遇袭", "太华雪峰", "雪山求援", "驰援丐帮", "奇袭天鉴",
    "云霞山庄", "剑阁遗骨", "毒沙风雨", "连环外滩", "霹雳狂人",
    "再探剑阁", "霸王一枪", "连环下坞", "极乐魅影", "连环中坞",
    "五毒邪宫", "银龙锁岳", "星宿腐海", "瀚海遗迹", "连环内坞",
    "移花神宫", "逍遥遗址", "竹林探宝", "金陵寻踪", "百草深处",
    "连云匪患", "武林汇聚", "边关告急", "旅途终点",
)
SOURCE_LOCATION_RANK = {name: index for index, name in enumerate(SOURCE_LOCATION_ORDER)}

# NPC loot groups frequently use generic combatants whose mapId is zero. These
# player-facing aliases recover a stable location from the prototype name while
# deliberately ignoring internal template names.
ENEMY_LOCATION_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("血雨潇湘", ("潇湘剑雨", "血雨潇湘")),
    ("竹海迷宫", ("竹海迷宫",)),
    ("血炎追踪", ("血炎",)),
    ("鹤羽飘香", ("鹤羽飘香",)),
    ("再探剑阁", ("再探剑阁",)),
    ("剑阁遗骨", ("剑阁遗骨",)),
    ("苍鹰探秘", ("苍鹰探秘",)),
    ("百草深处", ("百草深处",)),
    ("连云腹地", ("连云寨", "连云腹地")),
    ("贪狼寨", ("贪狼",)),
    ("毒沙帮", ("毒沙帮",)),
    ("连环坞", ("连环坞",)),
    ("缥缈峰", ("缥缈峰",)),
    ("灵素谷", ("灵素",)),
    ("镇狱司", ("镇狱司",)),
    ("极乐宫", ("极乐",)),
    ("云霞山庄", ("云霞",)),
    ("凌云寨", ("凌云",)),
    ("瀚海遗迹", ("瀚海遗迹",)),
    ("星宿海", ("星宿",)),
    ("菩提禅院", ("菩提",)),
    ("五毒宫", ("五毒",)),
    ("天鉴府", ("天鉴府",)),
    ("逍遥宫", ("逍遥宫",)),
    ("移花宫", ("移花宫",)),
    ("武林汇聚", ("武林汇聚",)),
    ("边关告急", ("边关告急",)),
    ("旅途终点", ("旅途终点",)),
    ("太华山", ("太华山",)),
)

# These entries mirror the player-facing source list shown by the current game
# client. Generic loot groups are reused by many NPC and chest prototypes, so
# expanding those groups cannot reliably identify the displayed dungeons.
VERIFIED_LOOT_SOURCES: dict[int, list[dict[str, str]]] = {
    1278: [
        {
            "type": "dungeon",
            "title": "副本产出",
            "detail": "可在血雨潇湘、竹海迷宫、血炎追踪、鹤羽飘香中获得。",
        }
    ],
    1279: [
        {
            "type": "dungeon",
            "title": "副本产出",
            "detail": "可在血雨潇湘、竹海迷宫、血炎追踪、鹤羽飘香中获得。",
        }
    ],
}
SMELTING_SOURCE_FAMILIES = {
    1191: "药材",
    1192: "药材",
    1193: "药材",
    1291: "矿石",
    1292: "矿石",
    1293: "矿石",
    1591: "杂物",
    1592: "杂物",
    1593: "杂物",
}


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
        default=PROJECT_ROOT / "wiki" / "src" / "data" / "materials.generated.json",
    )
    parser.add_argument(
        "--icon-dir",
        type=Path,
        default=PROJECT_ROOT / "wiki" / "public" / "game" / "materials",
    )
    return parser.parse_args()


def item_name(
    item_id: int,
    item_by_id: dict[int, dict[str, Any]],
    string_by_id: dict[int, dict[str, Any]],
) -> str:
    item = item_by_id.get(item_id, {})
    string_row = string_by_id.get(int(item.get("nameId") or 0), {})
    return clean_text(string_row.get("_str")) or f"物品 {item_id}"


def recipe_materials(row: dict[str, Any], length: int) -> list[tuple[int, int]]:
    return [
        (material_id, int(row.get(f"srcCount{index}") or 0))
        for index in range(length)
        if (material_id := int(row.get(f"srcId{index}") or 0))
        and int(row.get(f"srcCount{index}") or 0)
    ]


def readable_source_location(value: str, marker: str) -> str:
    location = re.sub(rf"{marker}.*$", "", value).strip(" -·")
    location = location.removesuffix("副本").strip(" -·")
    return location or "对应区域"


def dismantle_source(
    records: list[dict[str, Any]],
    equipment_detail_ids: set[int],
) -> dict[str, str] | None:
    if not records:
        return None
    equipment_names = sorted({record["name"] for record in records if record["id"] in equipment_detail_ids})
    other_names = sorted({record["name"] for record in records if record["id"] not in equipment_detail_ids})
    examples = equipment_names[:4]
    if not examples:
        examples = [name.replace("铸纹·", "") + "铸纹" for name in other_names[:4]]
    source_kinds = "装备或铸纹" if equipment_names and other_names else "装备" if equipment_names else "铸纹"
    counts = [record["count"] for record in records]
    count_text = str(counts[0]) if min(counts) == max(counts) else f"{min(counts)}–{max(counts)}"
    return {
        "type": "dismantle",
        "title": "天工分解",
        "detail": f"在天工的分解功能中，分解{'、'.join(examples)}等指定{source_kinds}，每次可获得 {count_text} 个。",
    }


def deduplicated_sources(sources: list[dict[str, str]]) -> list[dict[str, str]]:
    unique: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for source in sources:
        key = (source["type"], source["title"], source["detail"])
        if key not in seen:
            seen.add(key)
            unique.append(source)
    return unique


def explicit_names(names: set[str]) -> str:
    normalized_names = {
        SOURCE_LOCATION_ALIASES.get(name.split(" · ", 1)[0], name.split(" · ", 1)[0])
        for name in names
        if name
    }
    ordered_names = sorted(
        normalized_names,
        key=lambda name: (SOURCE_LOCATION_RANK.get(name, len(SOURCE_LOCATION_RANK)), name),
    )
    return "、".join(ordered_names[:MAX_DISPLAY_SOURCE_LOCATIONS])


def enemy_source_locations(enemy_names: set[str]) -> set[str]:
    locations: set[str] = set()
    for enemy_name in enemy_names:
        if " · " in enemy_name:
            locations.add(enemy_name.split(" · ", 1)[0])
        for location, aliases in ENEMY_LOCATION_ALIASES:
            if any(alias in enemy_name for alias in aliases):
                locations.add(location)
    return locations


def generic_merchant_source(shop_rows: list[dict[str, Any]]) -> dict[str, str] | None:
    if not shop_rows:
        return None
    variants = sorted(
        {
            (
                int(row.get("buyCost") or 0),
                int(row.get("itemcount") or 0),
                int(row.get("refreshtime") or 0),
            )
            for row in shop_rows
        }
    )
    variant_texts: list[str] = []
    for cost, stock, refresh_seconds in variants:
        text = f"{cost:,} 铜钱"
        if stock:
            text += f"（库存 {stock}）"
        if refresh_seconds:
            text += f"，约 {refresh_seconds // 60} 分钟刷新"
        variant_texts.append(text)
    return {
        "type": "shop",
        "title": "行商购买",
        "detail": f"可向行商购买；商队货单中的价格与库存档位为：{'；'.join(variant_texts)}。",
    }


def fuben_material_sources(
    path: Path,
    fuben_rows: list[dict[str, Any]],
    npc_by_id: dict[int, dict[str, Any]],
    loot_by_group: dict[int, set[int]],
    material_ids: set[int],
) -> dict[int, list[str]]:
    """Resolve the same first-four dungeon sources shown by the game UI.

    The database loot table only says what each NPC loot group may drop. The
    actual NPC composition of every dungeon lives in FuBenBattleInfo assets, so
    reading npc_prototype.mapId or expanding every matching prototype produces
    false locations.
    """
    env = UnityPy.load(str(path))
    enemy_ids_by_asset: dict[str, set[int]] = {}
    for obj in env.objects:
        if obj.type.name != "TextAsset":
            continue
        data = obj.read()
        raw = data.m_Script.decode("utf-8-sig") if isinstance(data.m_Script, bytes) else str(data.m_Script)
        enemy_ids: set[int] = set()
        for block in re.findall(
            r'"m_EnemyNpcDatas"\s*:\s*\{(.*?)"m_SpectorNpcDatas"\s*:',
            raw,
            flags=re.DOTALL,
        ):
            enemy_ids.update(int(value) for value in re.findall(r'"m_NpcId"\s*:\s*(\d+)', block))
        enemy_ids_by_asset[data.m_Name] = enemy_ids

    sources: dict[int, list[str]] = defaultdict(list)
    for fuben in sorted(
        (row for row in fuben_rows if int(row.get("type") or 0) == 1),
        key=lambda row: int(row["id"]),
    ):
        asset_name = f"FuBenBattleInfo_{int(fuben['npcFuBenId'])}"
        group_ids = {
            int(npc_by_id.get(npc_id, {}).get("lootGroupId") or 0)
            for npc_id in enemy_ids_by_asset.get(asset_name, set())
        }
        available_materials = {
            material_id
            for group_id in group_ids
            for material_id in loot_by_group.get(group_id, set())
            if material_id in material_ids
        }
        for material_id in available_materials:
            sources[material_id].append(clean_text(fuben.get("fubenName")))
    return sources


def acquisition_sources(
    item_id: int,
    shop_by_item: dict[int, list[dict[str, Any]]],
    merchants_by_group: dict[int, list[dict[str, str]]],
    loot_by_item: dict[int, list[dict[str, Any]]],
    loot_origins_by_group: dict[int, dict[str, set[str]]],
    ignored_loot_groups: set[int],
    dismantle_by_material: dict[int, list[dict[str, Any]]],
    equipment_detail_ids: set[int],
    fuben_sources_by_material: dict[int, list[str]],
) -> list[dict[str, str]]:
    sources: list[dict[str, str]] = []
    dismantle = dismantle_source(dismantle_by_material.get(item_id, []), equipment_detail_ids)
    if dismantle:
        sources.append(dismantle)
    smelting_family = SMELTING_SOURCE_FAMILIES.get(item_id)
    if smelting_family:
        sources.append(
            {
                "type": "smelting",
                "title": "天工熔炼",
                "detail": f"在天工的熔炼功能中投入{smelting_family}，根据熔炼结果获得。",
            }
        )
    seen_shops: set[tuple[str, int, str]] = set()
    generic_shop_rows: list[dict[str, Any]] = []
    for shop_row in shop_by_item.get(item_id, []):
        group_id = int(shop_row["group"])
        merchants = merchants_by_group.get(group_id)
        if not merchants:
            generic_shop_rows.append(shop_row)
            continue
        cost = int(shop_row.get("buyCost") or 0)
        stock = int(shop_row.get("itemcount") or 0)
        refresh_seconds = int(shop_row.get("refreshtime") or 0)
        for merchant in merchants:
            if merchant["title"].rsplit(" · ", 1)[-1] == "行商":
                generic_shop_rows.append(shop_row)
                continue
            key = (merchant["title"], cost, merchant["shopTitle"])
            if key in seen_shops:
                continue
            seen_shops.add(key)
            stock_text = f"，每次库存 {stock}" if stock else ""
            refresh_text = f"，约 {refresh_seconds // 60} 分钟刷新" if refresh_seconds else ""
            sources.append(
                {
                    "type": "shop",
                    "title": merchant["title"],
                    "detail": f"在“{merchant['shopTitle']}”中购买，单价 {cost:,} 铜钱{stock_text}{refresh_text}。",
                }
            )
    generic_merchant = generic_merchant_source(generic_shop_rows)
    if generic_merchant:
        sources.append(generic_merchant)

    chest_names: set[str] = set()
    gathering_names: set[str] = set()
    exploration_names: set[str] = set()
    enemy_names: set[str] = set()
    has_unmapped_loot = False
    item_loot_rows = loot_by_item.get(item_id, [])
    for loot_row in item_loot_rows:
        group_id = int(loot_row["groupId"])
        origins = loot_origins_by_group.get(group_id)
        if not origins:
            if group_id in ignored_loot_groups:
                continue
            has_unmapped_loot = True
            continue
        gathering_names.update(origins["gathering"])
        chest_names.update(origins["chest"])
        exploration_names.update(origins["exploration"])
        enemy_names.update(origins["enemy"])

    if item_id in VERIFIED_LOOT_SOURCES:
        sources.extend(VERIFIED_LOOT_SOURCES[item_id])
        return deduplicated_sources(sources)

    fuben_sources = fuben_sources_by_material.get(item_id, [])[:MAX_DISPLAY_SOURCE_LOCATIONS]
    if fuben_sources:
        sources.append(
            {
                "type": "dungeon",
                "title": "副本产出",
                "detail": f"可在{'、'.join(fuben_sources)}中获得。",
            }
        )
        return deduplicated_sources(sources)

    if gathering_names:
        sources.append(
            {
                "type": "gathering",
                "title": "地图采集",
                "detail": f"可在以下地图的采集点获得：{explicit_names(gathering_names)}。",
            }
        )
    if exploration_names:
        sources.append(
            {
                "type": "exploration",
                "title": "场景探索",
                "detail": f"可在以下地图探索获取：{explicit_names(exploration_names)}。",
            }
        )
    if chest_names:
        sources.append(
            {
                "type": "chest",
                "title": "宝箱获取",
                "detail": f"可从以下地图的宝箱中获得：{explicit_names(chest_names)}。",
            }
        )
    if enemy_names and not (gathering_names or exploration_names or chest_names):
        locations = enemy_source_locations(enemy_names)
        if locations:
            enemy_detail = f"可在以下地图击败敌人获得：{explicit_names(locations)}。"
        elif len(enemy_names) <= 8:
            enemy_detail = f"可由{summarized_names(enemy_names, '类敌人', 8)}掉落。"
        else:
            enemy_detail = f"可在{'、'.join(COMMON_EARLY_DUNGEONS)}中击败敌人获得。"
        sources.append(
            {
                "type": "drop",
                "title": "敌人掉落",
                "detail": enemy_detail,
            }
        )
    if has_unmapped_loot and not (gathering_names or exploration_names or chest_names or enemy_names) and not sources:
        sources.append(
            {
                "type": "reward",
                "title": "战斗奖励",
                "detail": "可通过战斗结算获得。",
            }
        )

    return deduplicated_sources(sources)


def main() -> int:
    args = parse_args()
    game_root = args.game_root.resolve()
    package_root = game_root / "xiayinglu_Data" / "StreamingAssets" / "yougou" / "DefaultPackage"
    index = read_json(args.index)
    db_path = resolve_bundle(index, package_root, DB_BUNDLE_NAME)
    icon_path = resolve_bundle(index, package_root, ICON_BUNDLE_NAME)
    fuben_path = resolve_bundle(index, package_root, FUBEN_BUNDLE_NAME)
    tables = text_asset_tables(
        db_path,
        {
            "dazaoprototype",
            "fenjieprototype",
            "fuben_prototype",
            "item_base",
            "item_equip",
            "liandanprototype",
            "loot_items",
            "mapinfo",
            "npc_interact",
            "npc_prototype",
            "shop",
            "stringlang",
            "wordentry",
            "wordentrytype",
            "zhuwenprototype",
        },
    )

    item_by_id = {int(row["id"]): row for row in tables["item_base"]}
    string_by_id = {int(row["id"]): row for row in tables["stringlang"]}
    word_by_id = {int(row["id"]): row for row in tables["wordentry"]}
    word_type_by_id = {int(row["id"]): row for row in tables["wordentrytype"]}
    material_rows = [
        row
        for row in tables["item_base"]
        if int(row.get("type") or 0) == 8 and int(row.get("subType") or 0) in CATEGORY_BY_SUBTYPE
    ]
    material_ids = {int(row["id"]) for row in material_rows}
    equipment_detail_ids = {
        int(row["id"])
        for row in tables["item_equip"]
        if int(row.get("partTypeId") or 0) in {0, 1, 2, 3, 4, 5}
    }
    trap_detail_ids = {
        int(row["id"])
        for row in tables["item_equip"]
        if int(row.get("partTypeId") or 0) == 6
    }
    dismantle_by_material: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in tables["fenjieprototype"]:
        source_id = int(row["id"])
        source_name = item_name(source_id, item_by_id, string_by_id)
        for material_id, count in recipe_materials(row, 6):
            if material_id in material_ids:
                dismantle_by_material[material_id].append({"id": source_id, "name": source_name, "count": count})

    shop_by_item: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in tables["shop"]:
        if int(row["itemid"]) in material_ids:
            shop_by_item[int(row["itemid"])].append(row)
    loot_by_item: dict[int, list[dict[str, Any]]] = defaultdict(list)
    loot_by_group: dict[int, set[int]] = defaultdict(set)
    for row in tables["loot_items"]:
        loot_by_group[int(row["groupId"])].add(int(row["lootItemId"]))
        if int(row["lootItemId"]) in material_ids:
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
    loot_origins_by_group: dict[int, dict[str, set[str]]] = defaultdict(
        lambda: {"gathering": set(), "chest": set(), "exploration": set(), "enemy": set()}
    )
    ignored_loot_groups: set[int] = set()
    for row in tables["npc_prototype"]:
        npc_id = int(row["id"])
        raw_source_name = clean_text(row.get("name"))
        source_name = loot_source_name(raw_source_name)
        map_name = map_names.get(int(row.get("mapId") or 0), "").removesuffix("室内")
        display_name = f"{map_name} · {source_name}" if map_name and map_name not in source_name else source_name
        loot_group = int(row.get("lootGroupId") or 0)
        if loot_group and source_name != "未知来源":
            if any(marker.lower() in raw_source_name.lower() for marker in NON_READER_SOURCE_MARKERS):
                ignored_loot_groups.add(loot_group)
            elif "宝箱" in raw_source_name:
                loot_origins_by_group[loot_group]["chest"].add(readable_source_location(display_name, "宝箱"))
            elif "采集物" in raw_source_name or int(row.get("NpcType") or 0) == 3:
                loot_origins_by_group[loot_group]["gathering"].add(readable_source_location(display_name, "采集物"))
            elif "偷点" in raw_source_name:
                loot_origins_by_group[loot_group]["exploration"].add(readable_source_location(display_name, "偷点"))
            else:
                loot_origins_by_group[loot_group]["enemy"].add(display_name)
        shop_group = int(row.get("miscValue2") or 0)
        if npc_id in merchant_titles and shop_group:
            merchant = {"title": display_name, "shopTitle": merchant_titles[npc_id]}
            if merchant not in merchants_by_group[shop_group]:
                merchants_by_group[shop_group].append(merchant)

    npc_by_id = {int(row["id"]): row for row in tables["npc_prototype"]}
    fuben_sources_by_material = fuben_material_sources(
        fuben_path,
        tables["fuben_prototype"],
        npc_by_id,
        loot_by_group,
        material_ids,
    )

    usage_by_material: dict[int, dict[str, Any]] = {
        item_id: {"alchemy": [], "forging": [], "inscription": {"recipeCount": 0, "targets": {}}}
        for item_id in material_ids
    }
    for recipe in tables["liandanprototype"]:
        target_id = int(recipe["id"])
        for material_id, count in recipe_materials(recipe, 6):
            if material_id in material_ids:
                usage_by_material[material_id]["alchemy"].append(
                    {"id": target_id, "name": item_name(target_id, item_by_id, string_by_id), "count": count}
                )
    for recipe in tables["dazaoprototype"]:
        target_id = int(recipe["id"])
        for material_id, count in recipe_materials(recipe, 6):
            if material_id in material_ids:
                usage_by_material[material_id]["forging"].append(
                    {
                        "id": target_id,
                        "name": item_name(target_id, item_by_id, string_by_id),
                        "count": count,
                        "targetKind": (
                            "装备" if target_id in equipment_detail_ids
                            else "陷阱" if target_id in trap_detail_ids
                            else "机关道具"
                        ),
                        "hasDetail": target_id in equipment_detail_ids or target_id in trap_detail_ids,
                    }
                )
    for recipe in tables["zhuwenprototype"]:
        if int(recipe.get("type") or 0) != 0:
            continue
        target_id = int(recipe.get("targetItemId") or 0)
        subtype = int(recipe.get("subtype") or 0)
        if subtype in {0, 2}:
            word = word_by_id.get(int(recipe.get("wordentryId") or 0), {})
            type_id = int(word.get("wordEntryTypeId") or 0)
            type_name = clean_text(word_type_by_id.get(type_id, {}).get("name")) or f"词条 {type_id}"
            part_slug = "-".join(str(recipe.get("useparttype") or "").split("|"))
            target_slug = f"fixed-{type_id}-{part_slug}"
            target_name = f"{type_name}铸纹"
        elif subtype == 1:
            group_id = int(recipe.get("wordentryRandomGroup") or 0)
            target_slug = f"random-{group_id}"
            target_name = f"{clean_text(recipe.get('wordentryRandomName'))}铸纹"
        else:
            target_slug = f"companion-{target_id}"
            target_name = clean_text(recipe.get("wordentryRandomName")) or item_name(target_id, item_by_id, string_by_id)
        for material_id, count in recipe_materials(recipe, 4):
            if material_id not in material_ids:
                continue
            inscription = usage_by_material[material_id]["inscription"]
            inscription["recipeCount"] += 1
            target = inscription["targets"].setdefault(
                target_slug,
                {
                    "id": target_id,
                    "slug": target_slug,
                    "name": target_name,
                    "recipeCount": 0,
                    "countMin": count,
                    "countMax": count,
                },
            )
            target["recipeCount"] += 1
            target["countMin"] = min(target["countMin"], count)
            target["countMax"] = max(target["countMax"], count)

    entries: list[dict[str, Any]] = []
    icon_targets: dict[str, list[Path]] = defaultdict(list)
    for item in material_rows:
        item_id = int(item["id"])
        subtype = int(item.get("subType") or 0)
        name_row = string_by_id.get(int(item.get("nameId") or 0), {})
        name = clean_text(name_row.get("_str")) or f"材料 {item_id}"
        traditional_name = clean_text(name_row.get("_strTW"))
        description = clean_text(
            string_by_id.get(int(item.get("baseDesc") or 0), {}).get("_str")
        ) or "暂无材料说明。"
        quality = int(item.get("quality") or 1)
        icon_name = clean_text(item.get("icon"))
        icon_targets[icon_name].append(args.icon_dir / f"{item_id}.png")
        usage = usage_by_material[item_id]
        inscription = usage["inscription"]
        inscription["targets"] = sorted(inscription["targets"].values(), key=lambda target: (target["name"], target["slug"]))
        usage_kinds = [
            label
            for key, label in (("alchemy", "炼丹"), ("forging", "打造"))
            if usage[key]
        ]
        if inscription["recipeCount"]:
            usage_kinds.append("铸纹")
        sources = acquisition_sources(
            item_id,
            shop_by_item,
            merchants_by_group,
            loot_by_item,
            loot_origins_by_group,
            ignored_loot_groups,
            dismantle_by_material,
            equipment_detail_ids,
            fuben_sources_by_material,
        )
        entries.append(
            {
                "id": item_id,
                "name": name,
                "traditionalName": traditional_name,
                "description": description,
                "category": CATEGORY_BY_SUBTYPE[subtype],
                "quality": quality,
                "qualityLabel": QUALITY_LABELS[quality],
                "icon": f"/game/materials/{item_id}.png",
                "iconSourceName": icon_name,
                "stackLimit": int(item.get("overlapMax") or 0),
                "usageKinds": usage_kinds,
                "usage": usage,
                "acquisitionSources": sources,
                "sourceTypes": sorted({source["type"] for source in sources}),
            }
        )

    entries.sort(key=lambda entry: (CATEGORY_ORDER[entry["category"]], entry["quality"], entry["id"]))
    leaked_sources = [
        (entry["id"], entry["name"], source["detail"])
        for entry in entries
        for source in entry["acquisitionSources"]
        if any(marker.lower() in f"{source['title']} {source['detail']}".lower() for marker in NON_READER_SOURCE_MARKERS)
    ]
    if leaked_sources:
        raise RuntimeError(f"Internal source names leaked into reader-facing material data: {leaked_sources[:5]}")
    extracted_dismantle_ids = {
        entry["id"]
        for entry in entries
        if "dismantle" in entry["sourceTypes"]
    }
    if extracted_dismantle_ids != set(dismantle_by_material):
        raise RuntimeError("Dismantle material sources are incomplete")
    vague_sources = [
        (entry["id"], entry["name"], source["detail"])
        for entry in entries
        for source in entry["acquisitionSources"]
        if "随剧情进度更新" in source["detail"]
        or "随副本与战斗进度变化" in source["detail"]
        or "多个已解锁副本" in source["detail"]
    ]
    if vague_sources:
        raise RuntimeError(f"Vague progression-dependent material sources remain: {vague_sources[:5]}")
    bare_merchant_sources = [
        (entry["id"], entry["name"])
        for entry in entries
        for source in entry["acquisitionSources"]
        if source["title"] == "行商"
    ]
    if bare_merchant_sources:
        raise RuntimeError(f"Bare merchant labels remain: {bare_merchant_sources[:5]}")
    for item_id, expected_sources in VERIFIED_LOOT_SOURCES.items():
        entry = next((entry for entry in entries if entry["id"] == item_id), None)
        if entry is None or any(source not in entry["acquisitionSources"] for source in expected_sources):
            raise RuntimeError(f"Verified loot sources are incomplete for material {item_id}")
    missing_acquisition_sources = [
        (entry["id"], entry["name"])
        for entry in entries
        if not entry["acquisitionSources"]
    ]
    if missing_acquisition_sources:
        raise RuntimeError(f"Materials without reader-facing acquisition sources: {missing_acquisition_sources}")
    export_icons(icon_path, icon_targets)
    payload = {
        "schemaVersion": 5,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "gameVersion": index["yooAsset"]["packageVersion"],
        "sources": {
            "databaseTables": [
                "dazaoprototype.json",
                "fenjieprototype.json",
                "fuben_prototype.json",
                "item_base.json",
                "item_equip.json",
                "liandanprototype.json",
                "loot_items.json",
                "mapinfo.json",
                "npc_interact.json",
                "npc_prototype.json",
                "shop.json",
                "stringlang.json",
                "wordentry.json",
                "wordentrytype.json",
                "zhuwenprototype.json",
            ],
            "iconBundle": ICON_BUNDLE_NAME,
            "fubenBundle": FUBEN_BUNDLE_NAME,
        },
        "counts": {
            "entries": len(entries),
            "categories": dict(sorted(Counter(entry["category"] for entry in entries).items())),
            "qualities": dict(sorted(Counter(str(entry["quality"]) for entry in entries).items())),
            "usageKinds": dict(sorted(Counter(kind for entry in entries for kind in entry["usageKinds"]).items())),
            "sourceTypes": dict(sorted(Counter(kind for entry in entries for kind in entry["sourceTypes"]).items())),
        },
        "entries": entries,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Exported {len(entries)} material records and {sum(len(paths) for paths in icon_targets.values())} icons")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
