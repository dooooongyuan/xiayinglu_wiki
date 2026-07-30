#!/usr/bin/env python3
"""Extract player-facing inscription recipes, affix pools, and icons for the wiki."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import UnityPy

from extract_equipment import QUALITY_LABELS, affix_value_text, clean_text
from extract_wuxue import read_json, resolve_bundle, text_asset_tables


DEFAULT_GAME_ROOT = Path(r"F:\SteamLibrary\steamapps\common\侠影录")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_BUNDLE_NAME = "defaultpackage_assets_buildresources_db.bundle"
ICON_BUNDLE_NAME = "defaultpackage_assets_buildresources_prefab_uisprite_ui_item.bundle"

PART_LABELS = {
    1: "武器",
    2: "衣服",
    3: "鞋靴",
    4: "饰品",
    5: "傀儡",
    6: "武魄",
}

ATTRIBUTE_DIRECTIONS = {
    "基础属性": {"生命", "真气", "气势", "武", "敏", "体", "念", "意"},
    "战斗属性": {"攻击", "防御", "暴击", "暴伤", "暴抗", "增伤", "减伤", "速度", "硬直", "破甲"},
    "内劲属性": {"阳", "阴", "柔", "刚", "毒", "内劲", "五行"},
    "资源收益": {"修为", "金钱", "武学"},
    "特殊效果": {"入毒", "解毒", "凝血", "聚气", "聚力"},
}

NODE_PATTERN = re.compile(r"CheckXiuXiNodeIdActiveCondition\|(\d+)")


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
        default=PROJECT_ROOT / "wiki" / "src" / "data" / "zhuwen.generated.json",
    )
    parser.add_argument(
        "--icon-dir",
        type=Path,
        default=PROJECT_ROOT / "wiki" / "public" / "game" / "zhuwen",
    )
    return parser.parse_args()


def item_name(
    item_id: int,
    item_by_id: dict[int, dict[str, Any]],
    string_by_id: dict[int, dict[str, Any]],
) -> str:
    item = item_by_id.get(item_id, {})
    return clean_text(string_by_id.get(int(item.get("nameId") or 0), {}).get("_str")) or f"物品 {item_id}"


def material_records(
    row: dict[str, Any],
    item_by_id: dict[int, dict[str, Any]],
    string_by_id: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    materials: list[dict[str, Any]] = []
    for index in range(4):
        material_id = int(row.get(f"srcId{index}") or 0)
        count = int(row.get(f"srcCount{index}") or 0)
        if not material_id or not count:
            continue
        item = item_by_id.get(material_id, {})
        materials.append(
            {
                "id": material_id,
                "name": item_name(material_id, item_by_id, string_by_id),
                "count": count,
                "quality": max(int(item.get("quality") or 1), 1),
            }
        )
    return materials


def parts(value: Any) -> list[str]:
    return [
        PART_LABELS[int(part)]
        for part in str(value or "").split("|")
        if part.isdecimal() and int(part) in PART_LABELS
    ]


def direction_for(name: str) -> str:
    for direction, names in ATTRIBUTE_DIRECTIONS.items():
        if name in names:
            return direction
    return "特殊效果"


def render_affix(
    row: dict[str, Any],
    type_row: dict[str, Any],
    string_by_id: dict[int, dict[str, Any]],
    spell_name: str = "对应技能",
) -> dict[str, Any]:
    value = affix_value_text(row, type_row)
    description = clean_text(string_by_id.get(int(row.get("desId") or 0), {}).get("_str"))
    description = description.replace("{0:G}", value).replace("{effectName}", "对应效果")
    description = description.replace("{spellName}", spell_name)
    description = re.sub(r"\{[^}]+\}", "对应数值", description)
    name = clean_text(type_row.get("name")) or f"词条 {row['id']}"
    quality = max(int(row.get("quality") or 1), 1)
    return {
        "id": int(row["id"]),
        "name": name,
        "value": value,
        "description": description or f"{name} +{value}",
        "quality": quality,
        "qualityLabel": QUALITY_LABELS.get(quality, "普通"),
        "weight": int(row.get("rate") or 0),
    }


def recipe_record(
    row: dict[str, Any],
    item_by_id: dict[int, dict[str, Any]],
    string_by_id: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    target_id = int(row.get("targetItemId") or 0)
    target = item_by_id.get(target_id, {})
    quality = max(int(target.get("quality") or 1), 1)
    return {
        "configId": int(row["id"]),
        "targetItemId": target_id,
        "quality": quality,
        "qualityLabel": QUALITY_LABELS.get(quality, "普通"),
        "icon": f"/game/zhuwen/{target_id}.png",
        "costMoney": int(row.get("costmoneyCreate") or 0),
        "materials": material_records(row, item_by_id, string_by_id),
    }


def candidate_groups(
    group_id: int,
    affixes_by_group: dict[int, list[dict[str, Any]]],
    word_type_by_id: dict[int, dict[str, Any]],
    string_by_id: dict[int, dict[str, Any]],
    spell_by_id: dict[int, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    generic: list[dict[str, Any]] = []
    by_spell: dict[int, list[dict[str, Any]]] = defaultdict(list)
    rows = sorted(affixes_by_group.get(group_id, []), key=lambda row: int(row["id"]))
    for row in rows:
        type_row = word_type_by_id.get(int(row.get("wordEntryTypeId") or 0), {})
        spell_id = int(type_row.get("param2") or 0) if int(type_row.get("wordFunctionType") or 0) == 6 else 0
        spell_name = clean_text(spell_by_id.get(spell_id, {}).get("name")) if spell_id else "对应技能"
        candidate = render_affix(row, type_row, string_by_id, spell_name)
        if spell_id:
            by_spell[spell_id].append(candidate)
        else:
            generic.append(candidate)
    spell_groups = [
        {
            "spellId": spell_id,
            "spellName": clean_text(spell_by_id.get(spell_id, {}).get("name")) or f"武学 {spell_id}",
            "candidates": candidates,
        }
        for spell_id, candidates in sorted(
            by_spell.items(),
            key=lambda item: (clean_text(spell_by_id.get(item[0], {}).get("name")), item[0]),
        )
    ]
    return generic, spell_groups, len(rows)


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
        for target in targets:
            target.parent.mkdir(parents=True, exist_ok=True)
            data.image.save(target, optimize=True)
        remaining.discard(data.m_Name)
    if remaining:
        raise RuntimeError(f"Missing inscription icons: {sorted(remaining)}")


def main() -> int:
    args = parse_args()
    game_root = args.game_root.resolve()
    package_root = game_root / "xiayinglu_Data" / "StreamingAssets" / "yougou" / "DefaultPackage"
    index = read_json(args.index)
    db_path = resolve_bundle(index, package_root, DB_BUNDLE_NAME)
    icon_bundle_path = resolve_bundle(index, package_root, ICON_BUNDLE_NAME)
    tables = text_asset_tables(
        db_path,
        {"item_base", "spellprotype", "stringlang", "wordentry", "wordentrytype", "xiuxi_node", "zhuwenprototype"},
    )

    item_by_id = {int(row["id"]): row for row in tables["item_base"]}
    string_by_id = {int(row["id"]): row for row in tables["stringlang"]}
    word_by_id = {int(row["id"]): row for row in tables["wordentry"]}
    word_type_by_id = {int(row["id"]): row for row in tables["wordentrytype"]}
    spell_by_id = {int(row["id"]): row for row in tables["spellprotype"]}
    node_by_id = {int(row["id"]): row for row in tables["xiuxi_node"]}
    affixes_by_group: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in tables["wordentry"]:
        affixes_by_group[int(row.get("group") or 0)].append(row)

    recipes = [row for row in tables["zhuwenprototype"] if int(row.get("type") or 0) == 0]
    fixed_rows = [row for row in recipes if int(row.get("subtype") or 0) in {0, 2}]
    random_rows = [row for row in recipes if int(row.get("subtype") or 0) == 1]
    companion_rows = [row for row in recipes if int(row.get("subtype") or 0) in {3, 4}]

    icon_targets: dict[str, list[Path]] = defaultdict(list)
    for row in recipes:
        target_id = int(row.get("targetItemId") or 0)
        icon_name = clean_text(item_by_id.get(target_id, {}).get("icon"))
        target_path = args.icon_dir / f"{target_id}.png"
        if icon_name and target_path not in icon_targets[icon_name]:
            icon_targets[icon_name].append(target_path)

    fixed_groups: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
    for row in fixed_rows:
        word = word_by_id[int(row["wordentryId"])]
        fixed_groups[(int(word["wordEntryTypeId"]), str(row.get("useparttype") or ""))].append(row)

    entries: list[dict[str, Any]] = []
    for (type_id, part_value), rows in fixed_groups.items():
        rows.sort(key=lambda row: int(row["id"]))
        type_row = word_type_by_id[type_id]
        name = clean_text(type_row.get("name")) or f"词条 {type_id}"
        applicable_parts = parts(part_value)
        stages: list[dict[str, Any]] = []
        for stage_index, row in enumerate(rows, 1):
            word = word_by_id[int(row["wordentryId"])]
            stage = recipe_record(row, item_by_id, string_by_id)
            stage.update(
                {
                    "stage": stage_index,
                    "value": affix_value_text(word, type_row),
                    "description": render_affix(word, type_row, string_by_id)["description"],
                }
            )
            stages.append(stage)
        quality = max(stage["quality"] for stage in stages)
        part_text = "、".join(applicable_parts)
        entries.append(
            {
                "slug": f"fixed-{type_id}-{'-'.join(part_value.split('|'))}",
                "kind": "fixed",
                "name": f"{name}铸纹",
                "shortName": name,
                "description": f"可镶嵌在{part_text}上，提供{name}属性；实际数值与制作材料随阶段变化。",
                "applicableParts": applicable_parts,
                "direction": direction_for(name),
                "quality": quality,
                "qualityLabel": QUALITY_LABELS.get(quality, "普通"),
                "icon": stages[-1]["icon"],
                "wordEntryTypeId": type_id,
                "stageCount": len(stages),
                "valueRange": f"{stages[0]['value']} 至 {stages[-1]['value']}" if len(stages) > 1 else stages[0]["value"],
                "stages": stages,
            }
        )

    for row in sorted(random_rows, key=lambda item: int(item["id"])):
        recipe = recipe_record(row, item_by_id, string_by_id)
        group_id = int(row.get("wordentryRandomGroup") or 0)
        generic, spell_groups, candidate_count = candidate_groups(
            group_id, affixes_by_group, word_type_by_id, string_by_id, spell_by_id
        )
        entries.append(
            {
                "slug": f"random-{group_id}",
                "kind": "random",
                "name": f"{clean_text(row.get('wordentryRandomName'))}铸纹",
                "shortName": clean_text(row.get("wordentryRandomName")),
                "description": clean_text(row.get("wordentryRandomDesc")),
                "applicableParts": parts(row.get("useparttype")),
                "direction": "武学强化",
                "quality": recipe["quality"],
                "qualityLabel": recipe["qualityLabel"],
                "icon": recipe["icon"],
                "groupId": group_id,
                "candidateCount": candidate_count,
                "genericCandidates": generic,
                "spellGroups": spell_groups,
                "recipe": recipe,
            }
        )

    for row in sorted(companion_rows, key=lambda item: int(item["id"])):
        recipe = recipe_record(row, item_by_id, string_by_id)
        group_id = int(row.get("wordentryRandomGroup") or 0)
        generic, spell_groups, candidate_count = candidate_groups(
            group_id, affixes_by_group, word_type_by_id, string_by_id, spell_by_id
        ) if group_id else ([], [], 0)
        node_match = NODE_PATTERN.search(str(row.get("strShowCondition") or ""))
        node_id = int(node_match.group(1)) if node_match else 0
        node = node_by_id.get(node_id, {})
        companion_type = "傀儡材料" if int(row.get("subtype") or 0) == 3 else "武魄材料"
        entries.append(
            {
                "slug": f"companion-{int(row['targetItemId'])}",
                "kind": "companion",
                "name": clean_text(row.get("wordentryRandomName")),
                "shortName": clean_text(row.get("wordentryRandomName")),
                "description": clean_text(row.get("wordentryRandomDesc")),
                "applicableParts": parts(row.get("useparttype")),
                "direction": "附身材料",
                "quality": recipe["quality"],
                "qualityLabel": recipe["qualityLabel"],
                "icon": recipe["icon"],
                "companionType": companion_type,
                "heatValue": int(row.get("huohouzhi") or 0),
                "groupId": group_id,
                "candidateCount": candidate_count,
                "genericCandidates": generic,
                "spellGroups": spell_groups,
                "unlock": {
                    "nodeId": node_id,
                    "nodeName": clean_text(node.get("name")),
                    "points": int(node.get("activeDianShu") or 0),
                },
                "recipe": recipe,
            }
        )

    kind_order = {"fixed": 0, "random": 1, "companion": 2}
    entries.sort(key=lambda entry: (kind_order[entry["kind"]], entry.get("wordEntryTypeId", 0), entry["slug"]))
    export_icons(icon_bundle_path, icon_targets)

    assert len(recipes) == 196
    assert len(fixed_rows) == 175
    assert len(fixed_groups) == 33
    assert len(random_rows) == 3
    assert sum(1 for row in companion_rows if int(row["subtype"]) == 3) == 9
    assert sum(1 for row in companion_rows if int(row["subtype"]) == 4) == 9

    payload = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "gameVersion": index["yooAsset"]["packageVersion"],
        "counts": {
            "recipes": len(recipes),
            "fixedRecipes": len(fixed_rows),
            "fixedSeries": len(fixed_groups),
            "randomEntries": len(random_rows),
            "companionEntries": len(companion_rows),
            "puppetEntries": sum(1 for row in companion_rows if int(row["subtype"]) == 3),
            "soulEntries": sum(1 for row in companion_rows if int(row["subtype"]) == 4),
            "entries": len(entries),
            "directions": dict(Counter(entry["direction"] for entry in entries)),
            "qualities": dict(Counter(str(entry["quality"]) for entry in entries)),
        },
        "entries": entries,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(entries)} inscription entries from {len(recipes)} recipes to {args.output}")
    print(f"Exported {sum(len(paths) for paths in icon_targets.values())} inscription icons to {args.icon_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
