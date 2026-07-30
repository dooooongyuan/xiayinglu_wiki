#!/usr/bin/env python3
"""Extract character profiles, locations, portraits, and verified relationships."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import UnityPy

from extract_danyao import clean_text
from extract_wuxue import read_json, resolve_bundle, text_asset_tables


DEFAULT_GAME_ROOT = Path(r"F:\SteamLibrary\steamapps\common\侠影录")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_BUNDLE_NAME = "defaultpackage_assets_buildresources_db.bundle"
PORTRAIT_BUNDLE_NAME = "defaultpackage_assets_buildresources_prefab_uisprite_ui_lihui.bundle"

GENDER_LABELS = {1: "男", 2: "女"}
GENERIC_MARKERS = (
    "弟子", "侍卫", "武僧", "江湖人", "守卫", "护卫", "捕快", "帮众", "喽啰", "山匪",
    "犯人", "兵", "黑衣人", "蒙面人", "神秘人", "大侠", "管事", "掌柜", "铁匠", "大婶",
    "大壮", "师爷", "阿嬷", "知客僧", "公子", "雅女",
)
OBJECT_MARKERS = ("交互", "空气墙", "休息点", "宿舍床", "线索道具")

# Only relationships stated directly by dialogue, character profiles, or explicit identity text are included.
# evidenceIds stay in generated data for maintenance and are deliberately not rendered on reader-facing pages.
VERIFIED_RELATIONS = [
    ("李尘舟", "雷啸川", "师兄弟", "school", False, [1001307, 1001762]),
    ("李尘舟", "沈砚秋", "师兄妹", "school", False, [1001815, 1001948]),
    ("雷啸川", "沈砚秋", "同门", "school", False, [1001783, 1001820]),
    ("李尘舟", "萧清雪", "红颜知己", "affection", False, [1001872]),
    ("李尘舟", "柳残星", "挚友", "friendship", False, [1000251]),
    ("解军", "柳残星", "昔日师兄弟", "school", False, [51917901]),
    ("沈胜舟", "解军", "掌门与弟子", "mentorship", True, [51917901]),
    ("聂守渊", "李尘舟", "师徒", "mentorship", True, [1000874]),
    ("陆心月", "萧清雪", "师承", "mentorship", True, [52124701]),
    ("江知白", "孙不二", "师兄弟·决裂", "broken", False, [1001601, 1001704]),
    ("江知白", "薛万嗔", "同门师兄弟", "school", False, [1001708]),
    ("李尘舟", "朴藏机", "师门血仇", "enmity", False, [1001870]),
    ("雷啸川", "朴藏机", "师门血仇", "enmity", False, [1001870]),
    ("沈砚秋", "朴藏机", "师门血仇", "enmity", False, [1001870]),
    ("李尘舟", "齐云霄", "联手约定", "alliance", False, [1001870]),
]

MENTIONED_CHARACTERS = {
    "柳残星": {"gender": "男", "faction": "潇湘剑阁", "description": "潇湘剑阁人物，解军昔日师兄，也是李尘舟的挚友。"},
    "沈胜舟": {"gender": "男", "faction": "潇湘剑阁", "description": "潇湘剑阁掌门，解军受其熏陶并恪守其教诲。"},
    "聂守渊": {"gender": "男", "faction": "苍玄门", "description": "李尘舟的师父，曾带李尘舟拜会潇湘剑阁。"},
}

FACTION_OVERRIDES = {
    "李尘舟": "苍影阁", "雷啸川": "苍影阁", "沈砚秋": "苍影阁",
    "柳残星": "潇湘剑阁", "解军": "潇湘剑阁", "沈胜舟": "潇湘剑阁",
    "江知白": "灵素谷", "孙不二": "灵素谷", "薛万嗔": "灵素谷",
    "萧清雪": "天鉴府", "萧无极": "天鉴府", "陆心月": "太华山",
    "聂守渊": "苍玄门", "齐云霄": "凌云寨", "崇黑虎": "凌云寨",
}

DESCRIPTION_OVERRIDES = {
    "李尘舟": "《侠影录》中由玩家操控的主角，与苍影阁关系密切。玩家将以李尘舟的身份踏入江湖，在探索、战斗与抉择中推动故事发展。",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-root", type=Path, default=DEFAULT_GAME_ROOT)
    parser.add_argument("--index", type=Path, default=PROJECT_ROOT / "wiki" / "src" / "data" / "game-index.json")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "wiki" / "src" / "data" / "characters.generated.json")
    parser.add_argument("--portrait-dir", type=Path, default=PROJECT_ROOT / "wiki" / "public" / "game" / "characters")
    return parser.parse_args()


def normalized_map_name(value: Any) -> str:
    name = clean_text(value)
    name = re.sub(r"(?:室内|BOSS)$", "", name).strip()
    return name


def is_generic_name(name: str) -> bool:
    return any(marker in name for marker in GENERIC_MARKERS)


def export_portraits(path: Path, portrait_dir: Path) -> set[str]:
    portrait_dir.mkdir(parents=True, exist_ok=True)
    exported: set[str] = set()
    env = UnityPy.load(str(path))
    for obj in env.objects:
        if obj.type.name != "Sprite":
            continue
        data = obj.read()
        name = clean_text(data.m_Name)
        if not name:
            continue
        data.image.save(portrait_dir / f"{name}.png", optimize=True)
        exported.add(name)
    return exported


def main() -> int:
    args = parse_args()
    package_root = args.game_root.resolve() / "xiayinglu_Data" / "StreamingAssets" / "yougou" / "DefaultPackage"
    index = read_json(args.index)
    db_path = resolve_bundle(index, package_root, DB_BUNDLE_NAME)
    portrait_path = resolve_bundle(index, package_root, PORTRAIT_BUNDLE_NAME)
    tables = text_asset_tables(db_path, {"mapinfo", "menpai", "npc_model", "npc_prototype", "stringlang"})

    strings = {int(row["id"]): row for row in tables["stringlang"]}
    models = {int(row["id"]): row for row in tables["npc_model"]}
    factions = {int(row["id"]): clean_text(row.get("name")) for row in tables["menpai"]}
    maps = {int(row["id"]): normalized_map_name(row.get("name")) for row in tables["mapinfo"]}
    exported_portraits = export_portraits(portrait_path, args.portrait_dir)

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in tables["npc_prototype"]:
        if int(row.get("NpcType") if row.get("NpcType") is not None else -1) not in {0, 3}:
            continue
        name_id = int(row.get("nameId") or 0)
        name = clean_text(strings.get(name_id, {}).get("_str"))
        model = models.get(int(row.get("NpcModelId") or 0), {})
        if not name or model.get("gender") not in GENDER_LABELS or any(marker in name for marker in OBJECT_MARKERS):
            continue
        grouped[name].append(row)

    entries: list[dict[str, Any]] = []
    for name, rows in grouped.items():
        name_ids = sorted({int(row.get("nameId") or 0) for row in rows if int(row.get("nameId") or 0)})
        canonical_name_id = name_ids[0]
        traditional_names = [clean_text(strings.get(name_id, {}).get("_strTW")) for name_id in name_ids]
        traditional_name = next((item for item in traditional_names if item and item != name), "")
        row_models = [models.get(int(row.get("NpcModelId") or 0), {}) for row in rows]
        icon_names = [clean_text(model.get("lihuiIcon")) for model in row_models]
        portrait_name = next((icon for icon in icon_names if icon in exported_portraits), "")
        gender_counts = Counter(GENDER_LABELS.get(int(model.get("gender") or 0), "未知") for model in row_models)
        gender = gender_counts.most_common(1)[0][0]
        locations = sorted({maps.get(int(row.get("mapId") or 0), "") for row in rows} - {""})
        levels = [int(row.get("level") or 0) for row in rows if int(row.get("level") or 0) > 0]
        if not levels:
            levels = [int(model.get("level") or 0) for model in row_models if int(model.get("level") or 0) > 1]
        faction_candidates = [factions.get(int(row.get("menPaiId") or 0), "") for row in rows]
        faction_candidates += [factions.get(int(model.get("gangId") or 0), "") for model in row_models]
        faction = FACTION_OVERRIDES.get(name) or next((item for item in faction_candidates if item), "未标明")
        descriptions = []
        for row in rows:
            description_id = int(row.get("desId") or 0)
            if description_id == int(row["id"]) * 100 + 1:
                description = clean_text(strings.get(description_id, {}).get("_str"))
                if description and description not in descriptions:
                    descriptions.append(description)
        generic = is_generic_name(name)
        role = "主要人物" if portrait_name and not generic else "普通 NPC" if generic else "江湖人物"
        if name in DESCRIPTION_OVERRIDES:
            description = DESCRIPTION_OVERRIDES[name]
        elif descriptions:
            description = descriptions[0]
        elif faction != "未标明":
            description = f"与{faction}相关的人物。" + (f"可在{'、'.join(locations[:3])}等地遇见。" if locations else "")
        elif locations:
            description = f"可在{'、'.join(locations[:3])}等地遇见的人物。"
        else:
            description = "游戏剧情与江湖事件中登场的人物。"
        entries.append({
            "slug": f"npc-{canonical_name_id}",
            "name": name,
            "traditionalName": traditional_name,
            "aliases": [],
            "portrait": f"/game/characters/{portrait_name}.png" if portrait_name else "",
            "gender": gender,
            "faction": faction,
            "locations": locations,
            "levelMin": min(levels) if levels else 0,
            "levelMax": max(levels) if levels else 0,
            "description": description,
            "role": role,
            "instanceCount": len(rows),
            "isMentionedOnly": False,
        })

    present_names = {entry["name"] for entry in entries}
    next_mentioned_id = 900001
    for name, profile in MENTIONED_CHARACTERS.items():
        if name in present_names:
            continue
        entries.append({
            "slug": f"npc-{next_mentioned_id}", "name": name, "traditionalName": "", "aliases": [],
            "portrait": "", "gender": profile["gender"], "faction": profile["faction"], "locations": [],
            "levelMin": 0, "levelMax": 0, "description": profile["description"], "role": "剧情人物",
            "instanceCount": 0, "isMentionedOnly": True,
        })
        next_mentioned_id += 1

    role_order = {"主要人物": 0, "剧情人物": 1, "江湖人物": 2, "普通 NPC": 3}
    entries.sort(key=lambda entry: (role_order[entry["role"]], entry["name"]))
    slug_by_name = {entry["name"]: entry["slug"] for entry in entries}
    relations = []
    for source, target, label, relation_type, directed, evidence_ids in VERIFIED_RELATIONS:
        if source not in slug_by_name or target not in slug_by_name:
            raise RuntimeError(f"Relationship references a missing character: {source} -> {target}")
        relations.append({
            "id": f"relation-{len(relations) + 1}", "source": slug_by_name[source], "target": slug_by_name[target],
            "label": label, "type": relation_type, "directed": directed, "evidenceIds": evidence_ids,
        })

    relation_counts = Counter()
    for relation in relations:
        relation_counts[relation["source"]] += 1
        relation_counts[relation["target"]] += 1
    for entry in entries:
        entry["relationCount"] = relation_counts[entry["slug"]]

    payload = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "gameVersion": index["yooAsset"]["packageVersion"],
        "counts": {
            "entries": len(entries), "portraits": len(exported_portraits), "relations": len(relations),
            "roles": dict(Counter(entry["role"] for entry in entries)),
        },
        "entries": entries,
        "relations": relations,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Exported {len(entries)} characters, {len(exported_portraits)} portraits, and {len(relations)} verified relationships")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
