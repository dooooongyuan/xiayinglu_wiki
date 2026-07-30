#!/usr/bin/env python3
"""Extract verified player martial-arts records and icons for the wiki.

The game install is read-only. Bundle filenames are resolved through the
generated game index so the extractor continues to work when bundle hashes
change between game versions.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import UnityPy


DEFAULT_GAME_ROOT = Path(r"F:\SteamLibrary\steamapps\common\侠影录")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_BUNDLE_NAME = "defaultpackage_assets_buildresources_db.bundle"
ICON_BUNDLE_NAME = "defaultpackage_assets_buildresources_prefab_uisprite_ui_spell.bundle"

STYLE_LABELS = {
    0: "剑诀",
    1: "刀势",
    2: "枪芒",
    3: "拳罡",
}

POWER_FIELDS = {
    "attack": ("攻", "weiLiGongJi"),
    "yang": ("阳", "weiLiYang"),
    "yin": ("阴", "weiLiYin"),
    "soft": ("柔", "weiLiRou"),
    "hard": ("刚", "weiLiGang"),
    "poison": ("毒", "weiLiDu"),
}

UNLOCK_ITEM_PATTERN = re.compile(r"(?:^|&)NpcUseItem\|1\|(\d+)\|1(?:&|$)")
PLAYER_LEVEL_PATTERN = re.compile(r"CheckPlayerLevel\|(\d+)")
HEART_AFFINITY_PATTERN = re.compile(r"(?:自身)?(阳|阴|柔|刚|毒)\+(\d+)")

CURATED_ALTERNATE_NAMES: dict[int, tuple[str, ...]] = {
    # The public-facing spell and manual use 玄清道, while effect records use 玄青道.
    70081: ("玄青道",),
}

CURATED_ITEM_SOURCES: dict[int, list[dict[str, str]]] = {
    16001: [{"type": "quest", "title": "神机山庄比武大会", "detail": "取得魁首后，由范先秋赠予"}],
    16002: [{"type": "quest", "title": "萧清雪相关剧情", "detail": "推进剧情后由萧清雪传授"}],
    16008: [{"type": "quest", "title": "谢孤鸿相关剧情", "detail": "天鉴府一战后由谢孤鸿相赠"}],
    16405: [{"type": "event", "title": "惊鸿坊 · 武林小会", "detail": "角色等级 15，累计优胜 3 次"}],
    16402: [{"type": "event", "title": "惊鸿坊 · 武林小会", "detail": "角色等级 20，累计优胜 5 次"}],
    16611: [{"type": "event", "title": "惊鸿坊 · 武林小会", "detail": "角色等级 25，累计优胜 7 次"}],
    17029: [{"type": "event", "title": "惊鸿坊 · 武林小会", "detail": "累计优胜 1 次"}],
}

CURATED_ENTRY_SOURCES: dict[int, list[dict[str, str]]] = {
    10001: [{"type": "initial", "title": "初始自带", "detail": "创建角色后即可使用"}],
    10141: [
        {
            "type": "quest",
            "title": "神机山庄后山 · 巨剑奇遇",
            "detail": "角色等级达到 35，且范星野在队伍中时，前往神机山庄后山巨剑处触发奇遇，完成后获得《求败》。",
        },
        {
            "type": "shop",
            "title": "苍影阁后山 · 佛像",
            "detail": "若未通过上述奇遇取得，相关剧情推进后可通过后山拜佛补购；角色等级达到 40，花费 300,000 铜钱。",
        },
    ],
    10191: [
        {
            "type": "quest",
            "title": "“千字文”后续剧情 · 谢军切磋",
            "detail": "推进“千字文”后续剧情，找到谢军并完成切磋后获得《孤光剑影》。",
        },
        {
            "type": "shop",
            "title": "苍影阁后山 · 佛像",
            "detail": "若未通过上述剧情取得，角色等级达到 40 后可花费 150,000 铜钱补购。",
        },
    ],
    20041: [
        {
            "type": "quest",
            "title": "天鉴府经楼 · 经楼管事",
            "detail": "角色等级达到 20 后，与经楼管事交谈触发“极乐草”奇遇，完成奇遇后获得《斗战刀法》。",
        }
    ],
    20051: [{"type": "quest", "title": "主线任务 · 朴藏机切磋", "detail": "推进主线至天鉴府，与朴藏机切磋获胜后获得"}],
    20091: [{"type": "initial", "title": "初始自带", "detail": "创建角色后即可使用"}],
    20151: [
        {
            "type": "drop",
            "title": "副本 · 瓮中捉鳖 · 朴藏机",
            "detail": "推进“瓮中捉鳖”副本并击败 BOSS 朴藏机后获得《黑煞魔刀》。",
        }
    ],
    30001: [{"type": "initial", "title": "初始自带", "detail": "创建角色后即可使用"}],
    30111: [
        {
            "type": "quest",
            "title": "副本 · 银龙锁岳",
            "detail": "在五毒宫取得“毒谷鳞纹残笺”，找沈砚秋解密开启副本后获得",
        }
    ],
    40021: [
        {
            "type": "event",
            "title": "惊鸿坊 · 武林小会",
            "detail": "角色等级 30，累计优胜 10 次；领取并开启“玲珑宝匣”获得",
        }
    ],
    40071: [
        {
            "type": "drop",
            "title": "绝龙岭 · 虎类精英",
            "detail": "前往绝龙岭，击败虎类精英后获得《猛虎式》。",
        }
    ],
    40091: [{"type": "initial", "title": "初始自带", "detail": "创建角色后即可使用"}],
    40101: [
        {
            "type": "quest",
            "title": "丐帮 · 特殊任务",
            "detail": "完成丐帮相关特殊任务后获得《降龙吞岳》。",
        },
        {
            "type": "shop",
            "title": "苍影阁后山 · 佛像",
            "detail": "若错过丐帮特殊任务，相关剧情失败标记触发后可在角色等级达到 40 时花费 400,000 铜钱补购。",
        },
    ],
    40121: [
        {
            "type": "quest",
            "title": "菩提禅院 · 藏经阁任务",
            "detail": "随净尘前往藏经阁，与了心论武后领悟",
        }
    ],
}

CURATED_ENTRY_SOURCES.update(
    {
        60001: [
            {
                "type": "event",
                "title": "凌云寨 · 冷青瓷切磋",
                "detail": "与冷青瓷切磋获胜，直接获得《凌云心诀》。",
            },
            {
                "type": "shop",
                "title": "苍影阁后山 · 佛像",
                "detail": "完成上述切磋后，如尚未持有秘籍，角色等级 35 可花 50,000 铜钱购买。",
            },
        ],
        60041: [
            {
                "type": "drop",
                "title": "主线副本 · 血炎追踪",
                "detail": "推进至第 7 个房间并击败冷雪，固定获得《傲寒诀》。",
            }
        ],
        60061: [
            {
                "type": "drop",
                "title": "悬赏副本 · 逍遥宫",
                "detail": "推进至第 15 个房间并击败首领慕容炎，固定获得《狂夷咒》。",
            }
        ],
        60071: [
            {
                "type": "drop",
                "title": "连环坞中坞 · 石田二郎",
                "detail": "推进至第 9 个房间并击败石田二郎，固定获得“黑蟒毒牙令”。",
            },
            {
                "type": "quest",
                "title": "惊鸿坊 · 影娘",
                "detail": "携带“黑蟒毒牙令”与影娘交谈，选择“噬星咒”后获得秘籍。",
            },
        ],
        60091: [
            {
                "type": "drop",
                "title": "副本 · 霹雳狂人",
                "detail": "推进至第 5 个房间并击败地狂，固定获得《少阳功》。",
            }
        ],
        60101: [
            {
                "type": "unavailable",
                "title": "当前版本暂无正常获取途径",
                "detail": "游戏数据中存在《金罡诀》秘籍和完整修习节点，但未配置商店、掉落、宝箱、任务或场景奖励。",
            }
        ],
        60171: [
            {
                "type": "event",
                "title": "连环坞外滩",
                "detail": "先完整通关至少 1 次。",
            },
            {
                "type": "quest",
                "title": "惊鸿坊 · 影娘",
                "detail": "满足通关条件后与影娘交谈，选择“蚀元诀”获得秘籍。",
            },
        ],
        60181: [
            {
                "type": "drop",
                "title": "主线副本 · 论武大会",
                "detail": "在第 1 个房间击败凌箫，固定获得《神霄天霆》。",
            }
        ],
        60191: [
            {
                "type": "explore",
                "title": "神机山庄后院 · 巨剑",
                "detail": "先与范星野切磋取得《求败》，修满其全部 6 个节点并将“意”提升至 120，再次调查巨剑后领悟《独孤心诀》。",
            },
            {
                "type": "shop",
                "title": "苍影阁后山 · 佛像",
                "detail": "主线推进至《除魔卫道》并返回苍影阁后，角色等级 40 且未持有秘籍时，可花 300,000 铜钱购买。",
            },
        ],
        60211: [
            {
                "type": "drop",
                "title": "连环坞中坞 · 石田二郎",
                "detail": "推进至第 9 个房间并击败石田二郎，固定获得《四象心法》。",
            }
        ],
        60221: [
            {
                "type": "quest",
                "title": "主线任务 · 正魔决战",
                "detail": "奉云王之命前往天鉴府经楼，与曹管事交谈领取《九阳焚厄经》。",
            }
        ],
        60251: [
            {
                "type": "quest",
                "title": "主线任务 · 灭门真相",
                "detail": "任务进行中在苍影阁与雷啸川切磋，完成随后剧情后由沈砚秋赠予《苍云太玄经》。",
            }
        ],
        60261: [
            {
                "type": "drop",
                "title": "连环坞下坞 · 真本三郎",
                "detail": "推进至第 9 个房间并击败真本三郎，固定获得《破体心诀》。",
            }
        ],
        60271: [
            {
                "type": "quest",
                "title": "天鉴大战后 · 萧清雪",
                "detail": "完成天鉴大战后与萧清雪对话，开启《天绝心法》相关获取流程。",
            },
            {
                "type": "quest",
                "title": "天鉴府 · 铁匠段机玄",
                "detail": "与段机玄对话，使用寒晶铁换取“剑骨”。",
            },
            {
                "type": "quest",
                "title": "门派铁匠 · 合成",
                "detail": "携带“剑骨”找门派铁匠完成合成，取得开启竹海迷宫石壁所需物品。",
            },
            {
                "type": "explore",
                "title": "竹海迷宫 · 石壁隐藏区域",
                "detail": "使用合成物开启竹海迷宫石壁，进入隐藏区域后取得《天绝心法》。",
            },
            {
                "type": "shop",
                "title": "苍影阁后山 · 佛像",
                "detail": "若错过竹海迷宫获取流程，相关剧情推进后可在角色等级达到 40 时花费 100,000 铜钱补购。",
            },
        ],
        70001: [
            {
                "type": "chest",
                "title": "主线副本 · 鹤羽飘香",
                "detail": "推进至第 8 个房间，开启场景宝箱获得《战阵韬略》。",
            }
        ],
        70011: [
            {
                "type": "explore",
                "title": "主线副本 · 血炎追踪",
                "detail": "推进至第 11 个房间，调查“无相诀交互点”获得秘籍；该副本在完成主线《竹海迷踪》后开启。",
            }
        ],
        70031: [
            {
                "type": "event",
                "title": "神机山庄 · 冷青瓷切磋",
                "detail": "与冷青瓷切磋获胜，直接获得《寒冰真气》。",
            },
            {
                "type": "shop",
                "title": "苍影阁后山 · 佛像",
                "detail": "若相关剧情结束时仍未取得秘籍，角色等级 40 可花 100,000 铜钱补购。",
            },
        ],
        70041: [
            {
                "type": "drop",
                "title": "副本 · 纨绔子弟",
                "detail": "在第 1 个房间击败孙玉麟，固定获得《爆元经》。",
            }
        ],
        70051: [
            {
                "type": "drop",
                "title": "竹海迷宫",
                "detail": "推进至第 17 个房间并击败假扮灵素弟子的剑客，固定获得《万毒诀》。",
            }
        ],
        70061: [
            {
                "type": "chest",
                "title": "主线副本 · 苍鹰探秘",
                "detail": "推进至第 10 个房间，开启场景宝箱获得《乾坤诀》。",
            }
        ],
        70071: [
            {
                "type": "quest",
                "title": "主线副本 · 镇狱毒司",
                "detail": "从连云山腹地找到镇狱司入口，推进至第 11 个房间，与囚犯呼延葬交互并完成剧情后获得《葬神心诀》。",
            }
        ],
        70081: [
            {
                "type": "drop",
                "title": "悬赏副本 · 移花宫",
                "detail": "推进至第 8 个房间并击败宫主妖月，有概率获得《玄清道》。",
            }
        ],
        70091: [
            {
                "type": "drop",
                "title": "连环坞内坞 · 宫本太郎",
                "detail": "推进至第 10 个房间并击败宫本太郎，固定获得“血沁骨珠串”。",
            },
            {
                "type": "quest",
                "title": "惊鸿坊 · 影娘",
                "detail": "携带“血沁骨珠串”与影娘交谈，选择“幽冥界”后获得秘籍。",
            },
        ],
        80021: [
            {
                "type": "drop",
                "title": "主线副本 · 血雨潇湘",
                "detail": "推进至第 4 个房间并击败杀手首领地煞，固定获得《灵犀经》。",
            }
        ],
        80041: [
            {
                "type": "drop",
                "title": "主线副本 · 血炎追踪",
                "detail": "推进至第 10 个房间并击败地劫，固定获得《炎心诀》。",
            }
        ],
        80061: [
            {
                "type": "drop",
                "title": "主线副本 · 花海寻药",
                "detail": "推进至第 8 个房间并击败特殊精英灵素弟子，固定获得“破妄矿”。",
            },
            {
                "type": "quest",
                "title": "苍影阁 · 顾野樵",
                "detail": "携带“破妄矿”与顾野樵交谈，用矿石换取《天师雷法》。",
            },
        ],
        80081: [
            {
                "type": "drop",
                "title": "主线副本 · 沙漠瀚海城",
                "detail": "推进至第 15 个房间并击败呼延濯，固定获得《八方真罡诀》。",
            }
        ],
        80091: [
            {
                "type": "event",
                "title": "天鉴府悬赏榜 · 逍遥遗址",
                "detail": "先在天鉴府悬赏榜揭取“逍遥遗址”悬赏。",
            },
            {
                "type": "drop",
                "title": "四宫悬赏副本 · 首领掉落",
                "detail": "在五毒宫击败何溪凤取得毒纹灵钥，在移花宫击败妖月取得凝芳玉钥，在星宿腐海击败丁纯丘取得玄星铁钥，在极乐宫击败薛三娘取得烬金秘钥。",
            },
            {
                "type": "explore",
                "title": "逍遥遗址 · 逍遥宫密藏",
                "detail": "在首领房右侧找到四座机关雕塑，放入对应秘钥后调查“逍遥宫密藏”，获得《逍遥极影道》。",
            },
        ],
        80111: [
            {
                "type": "drop",
                "title": "悬赏副本 · 极乐宫",
                "detail": "推进至第 7 个房间并击败宫主薛三娘，固定获得《噬心咒》。",
            }
        ],
        80121: [
            {
                "type": "explore",
                "title": "主线副本 · 血雨潇湘",
                "detail": "推进至第 6 个房间，调查“剑痴秘籍交互点”获得《三才化元诀》。",
            }
        ],
        80131: [
            {
                "type": "explore",
                "title": "缥缈峰雪宫（太华雪山）",
                "detail": "深入最底部的宝箱地图，打破颜色不同的石壁进入隐藏区域，在佛像前调查蒲团并选择叩拜，获得《九阴》。",
            }
        ],
        80141: [
            {
                "type": "unavailable",
                "title": "当前版本暂无正常获取途径",
                "detail": "该心法没有对应秘籍物品，游戏数据中也未配置任务、掉落、商店或场景解锁动作。",
            }
        ],
    }
)


# Loot NPC records do not carry their instantiated dungeon map. These locations
# are verified against dungeon/clue data and keep player-facing sources specific.
LOOT_GROUP_CONTEXT: dict[int, tuple[str, str]] = {
    335: ("绝龙岭", "虎类精英"),
    507: ("副本 · 毒沙风雨", "绝幽客"),
    517: ("主线副本 · 鹤羽飘香", "徐中鹤"),
    523: ("悬赏副本 · 霸王一枪", "狂枪"),
    525: ("主线副本 · 血炎追踪", "地劫"),
    529: ("主线副本 · 苍鹰探秘", "天罪"),
    537: ("主线副本 · 葬花追凶", "孙不二"),
    539: ("副本 · 突袭瀚海", "呼延葬"),
    541: ("悬赏副本 · 星宿腐海", "丁纯丘"),
    545: ("悬赏副本 · 五毒宫", "何溪凤"),
    555: ("主线副本 · 瓮中捉鳖", "朴藏机"),
    593: ("连环坞内坞", "宫本太郎"),
    595: ("悬赏副本 · 瀚海遗迹", "鬼枪"),
    601: ("副本 · 连云匪患", "赫连勃"),
    603: ("副本 · 百草深处", "枪系首领"),
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
        default=PROJECT_ROOT / "wiki" / "src" / "data" / "wuxue.generated.json",
    )
    parser.add_argument(
        "--icon-dir",
        type=Path,
        default=PROJECT_ROOT / "wiki" / "public" / "game" / "wuxue",
    )
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def resolve_bundle(index: dict[str, Any], package_root: Path, bundle_name: str) -> Path:
    matches = [
        record
        for record in index["yooAsset"]["bundles"]
        if record.get("bundleName") == bundle_name
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one bundle named {bundle_name}, found {len(matches)}")
    path = package_root / matches[0]["file"]
    if not path.exists():
        raise RuntimeError(f"Indexed bundle no longer exists: {path}. Re-run index_game.py first.")
    return path


def text_asset_tables(path: Path, names: set[str]) -> dict[str, list[dict[str, Any]]]:
    env = UnityPy.load(str(path))
    tables: dict[str, list[dict[str, Any]]] = {}
    for obj in env.objects:
        if obj.type.name != "TextAsset":
            continue
        data = obj.read()
        name = data.m_Name.lower().removesuffix(".json")
        if name not in names:
            continue
        raw = data.m_Script.decode("utf-8-sig") if isinstance(data.m_Script, bytes) else str(data.m_Script)
        payload = json.loads(raw)
        if not isinstance(payload, list):
            raise RuntimeError(f"Expected a list in {data.m_Name}")
        tables[name] = payload
    missing = names - tables.keys()
    if missing:
        raise RuntimeError(f"Missing database tables: {sorted(missing)}")
    return tables


def timeline_ids(resources_path: Path) -> set[int]:
    env = UnityPy.load(str(resources_path))
    ids: set[int] = set()
    for obj in env.objects:
        if obj.type.name != "TextAsset":
            continue
        name = obj.read().m_Name
        if name.isdecimal():
            ids.add(int(name))
    return ids


def export_icons(path: Path, icon_targets: dict[str, Path]) -> None:
    env = UnityPy.load(str(path))
    remaining = set(icon_targets)
    for obj in env.objects:
        if obj.type.name != "Sprite":
            continue
        data = obj.read()
        target = icon_targets.get(data.m_Name)
        if target is None:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        data.image.save(target, optimize=True)
        remaining.remove(data.m_Name)
    if remaining:
        raise RuntimeError(f"Missing martial-arts icons: {sorted(remaining)}")


def format_seconds(milliseconds: int) -> int | float:
    seconds = milliseconds / 1000
    return int(seconds) if seconds.is_integer() else seconds


def unlock_item_id(condition: Any) -> int | None:
    match = UNLOCK_ITEM_PATTERN.search(str(condition or ""))
    return int(match.group(1)) if match else None


def clean_source_name(value: Any) -> str:
    name = re.sub(r"[（(][^）)]*[）)]", "", str(value or "")).strip()
    name = re.sub(r"^师妹", "", name)
    name = re.sub(r"^[^-]*BOSS-", "", name, flags=re.IGNORECASE)
    name = re.sub(r"-[^-]*(?:BOSS|大体型|剧情用|将军|精英)$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\d*BOSS$", "", name, flags=re.IGNORECASE)
    return name.replace("_", " · ").strip(" -·")


def chest_location(value: str) -> str:
    location = re.sub(r"宝箱\d*$", "", value).strip(" -·")
    return location.removesuffix("副本") or "未知副本"


def acquisition_sources(
    entry_id: int,
    item_id: int | None,
    shop_by_item: dict[int, list[dict[str, Any]]],
    merchants_by_group: dict[int, list[dict[str, str]]],
    loot_by_item: dict[int, list[dict[str, Any]]],
    loot_npcs_by_group: dict[int, list[str]],
    interaction_by_item: dict[int, list[dict[str, str]]],
) -> list[dict[str, str]]:
    curated_entry_sources = CURATED_ENTRY_SOURCES.get(entry_id, [])
    if curated_entry_sources:
        return curated_entry_sources
    if item_id is None:
        return [
            {
                "type": "unknown",
                "title": "未关联秘籍物品",
                "detail": "可能为初始武学或剧情直接解锁，具体条件待实机核实。",
            }
        ]

    sources: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()

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
        requirement_text = f" · 需满足{'、'.join(requirements)}" if requirements else ""
        for merchant in merchants:
            merchant_name = merchant["title"].rsplit(" · ", 1)[-1]
            source = {
                "type": "shop",
                "title": merchant["title"],
                "detail": f"向{merchant_name}购买（{merchant['shopTitle']}） · {int(shop_row['buyCost']):,} 铜钱{requirement_text}",
            }
            key = (source["type"], source["title"], source["detail"])
            if key not in seen:
                seen.add(key)
                sources.append(source)

    for loot_row in loot_by_item.get(item_id, []):
        group_id = int(loot_row["groupId"])
        npc_names = loot_npcs_by_group.get(group_id, [])
        if not npc_names:
            continue
        is_chest = all("宝箱" in name for name in npc_names)
        if is_chest:
            locations = list(dict.fromkeys(chest_location(name) for name in npc_names))
            source = {
                "type": "chest",
                "title": "、".join(f"副本 · {location} · 场景宝箱" for location in locations),
                "detail": "在上述副本内开启场景宝箱后固定获得。",
            }
        else:
            context = LOOT_GROUP_CONTEXT.get(group_id)
            if context is None:
                raise RuntimeError(
                    f"Missing dungeon or map context for loot group {group_id}: {npc_names}"
                )
            location, enemy_name = context
            source = {
                "type": "drop",
                "title": f"{location} · {enemy_name}",
                "detail": f"在{location}击败{enemy_name}后固定获得。",
            }
        key = (source["type"], source["title"], source["detail"])
        if key not in seen:
            seen.add(key)
            sources.append(source)

    for source in [
        *interaction_by_item.get(item_id, []),
        *CURATED_ITEM_SOURCES.get(item_id, []),
    ]:
        key = (source["type"], source["title"], source["detail"])
        if key not in seen:
            seen.add(key)
            sources.append(source)

    if not sources:
        sources.append(
            {
                "type": "unknown",
                "title": "获取方式待核实",
                "detail": "当前版本数据库中未找到可直接定位的商店、敌人掉落或宝箱记录。",
            }
        )
    return sources


def main() -> int:
    args = parse_args()
    game_root = args.game_root.resolve()
    data_root = game_root / "xiayinglu_Data"
    package_root = data_root / "StreamingAssets" / "yougou" / "DefaultPackage"
    index = read_json(args.index)

    db_path = resolve_bundle(index, package_root, DB_BUNDLE_NAME)
    icon_path = resolve_bundle(index, package_root, ICON_BUNDLE_NAME)
    tables = text_asset_tables(
        db_path,
        {
            "wuxueprototype",
            "spellprotype",
            "xiuxi_node",
            "xiuxi_node_pos",
            "xiuxi_graph",
            "item_base",
            "stringlang",
            "shop",
            "loot_items",
            "npc_prototype",
            "npc_interact",
            "mapinfo",
        },
    )
    spell_by_id = {int(row["id"]): row for row in tables["spellprotype"]}
    item_by_id = {int(row["id"]): row for row in tables["item_base"]}
    string_by_id = {int(row["id"]): row for row in tables["stringlang"]}
    training_nodes = tables["xiuxi_node"]
    training_positions = {
        int(row["id"]): row for row in tables["xiuxi_node_pos"]
    }
    training_edges = tables["xiuxi_graph"]
    root_by_spell_id = {
        int(row["spellId"]): row
        for row in training_nodes
        if int(row["spellId"]) > 0 and row.get("name")
    }
    player_wuxue_ids = {int(row["id"]) for row in tables["wuxueprototype"]}
    shop_by_item: dict[int, list[dict[str, Any]]] = {}
    for row in tables["shop"]:
        shop_by_item.setdefault(int(row["itemid"]), []).append(row)
    loot_by_item: dict[int, list[dict[str, Any]]] = {}
    for row in tables["loot_items"]:
        loot_by_item.setdefault(int(row["lootItemId"]), []).append(row)

    map_names = {int(row["id"]): str(row["name"]) for row in tables["mapinfo"]}
    merchant_ids = {
        int(row["npcId"]): str(row["title"] or "商店")
        for row in tables["npc_interact"]
        if int(row["subtype"]) == 5
    }
    merchants_by_group: dict[int, list[dict[str, str]]] = {}
    loot_npcs_by_group: dict[int, list[str]] = {}
    interaction_by_item: dict[int, list[dict[str, str]]] = {}
    for row in tables["npc_prototype"]:
        npc_id = int(row["id"])
        npc_name = clean_source_name(row.get("name"))
        if npc_id in merchant_ids and int(row.get("miscValue2") or 0) > 0:
            group_id = int(row["miscValue2"])
            map_name = map_names.get(int(row.get("mapId") or 0), "").removesuffix("室内")
            title = " · ".join(value for value in (map_name, npc_name) if value)
            merchant = {"title": title or npc_name or "商店", "shopTitle": merchant_ids[npc_id]}
            group_merchants = merchants_by_group.setdefault(group_id, [])
            if merchant not in group_merchants:
                group_merchants.append(merchant)
        loot_group_id = int(row.get("lootGroupId") or 0)
        if loot_group_id > 0 and npc_name:
            group_names = loot_npcs_by_group.setdefault(loot_group_id, [])
            if npc_name not in group_names:
                group_names.append(npc_name)
        interaction_parts = str(row.get("miscString2") or "").split("|")
        if int(row.get("NpcSubType") or 0) == 12 and len(interaction_parts) >= 3 and interaction_parts[1].isdecimal():
            interaction_item_id = int(interaction_parts[1])
            location = npc_name.removesuffix("-秘籍交互点").strip(" -")
            source = {
                "type": "explore",
                "title": location or "场景探索",
                "detail": "在场景中的秘籍交互点取得",
            }
            item_interactions = interaction_by_item.setdefault(interaction_item_id, [])
            if source not in item_interactions:
                item_interactions.append(source)
    martial_roots = [row for row in root_by_spell_id.values() if int(row["type"]) in {1, 2, 3, 4, 6}]
    catalog_roots = sorted(
        (
            row
            for row in martial_roots
            if int(row["type"]) == 6 or int(row["spellId"]) in player_wuxue_ids
        ),
        key=lambda row: (int(row["type"]), int(row["spellId"])),
    )
    excluded_graph_roots = sorted(
        (
            {"id": int(row["spellId"]), "name": str(row["name"]), "reason": "未列入玩家武学主表"}
            for row in martial_roots
            if int(row["type"]) != 6 and int(row["spellId"]) not in player_wuxue_ids
        ),
        key=lambda row: row["id"],
    )
    timeline_available = timeline_ids(data_root / "resources.assets")
    addressable_ids = {int(value) for value in index["addressables"]["skillIds"] if value.isdecimal()}

    entries: list[dict[str, Any]] = []
    icon_targets: dict[str, Path] = {}
    records = [
        (int(row["spellId"]), "心法" if int(row["type"]) == 6 else "功法")
        for row in catalog_roots
    ]
    for record_id, category in records:
        spell = spell_by_id.get(record_id)
        if spell is None:
            raise RuntimeError(f"Martial-arts record {record_id} has no matching spell record")

        style_code = int(spell["taoluType"]) if category == "功法" else None
        if category == "功法" and style_code not in STYLE_LABELS:
            raise RuntimeError(f"Unknown martial-arts style code {style_code} for {record_id}")
        style = STYLE_LABELS[style_code] if style_code is not None else "心法"
        root = root_by_spell_id.get(record_id)
        if root is None:
            raise RuntimeError(f"Martial-arts record {record_id} has no matching training root")

        manual_item_id = unlock_item_id(root.get("strHideBookCondition"))
        manual_item = item_by_id.get(manual_item_id) if manual_item_id is not None else None
        manual_text = string_by_id.get(int(manual_item["nameId"])) if manual_item is not None else None
        manual_name = str(manual_text.get("_str") or "") if manual_text else ""
        manual_traditional_name = str(manual_text.get("_strTW") or "") if manual_text else ""
        source_name = str(root["name"]) if category == "心法" else str(spell["name"])
        source_traditional_name = (
            str(root.get("nameTW") or "")
            if category == "心法"
            else str(spell.get("nameTW") or "")
        )
        canonical_name = manual_name or source_name
        traditional_name = manual_traditional_name or source_traditional_name
        alternate_names = list(
            dict.fromkeys(
                name
                for name in (
                    str(spell["name"]),
                    str(root["name"]),
                    *CURATED_ALTERNATE_NAMES.get(record_id, ()),
                )
                if name and name != canonical_name
            )
        )

        power = {
            key: {"label": label, "rawValue": int(spell[field])}
            for key, (label, field) in POWER_FIELDS.items()
        }
        affinities = [
            value
            for key, value in power.items()
            if key != "attack" and value["rawValue"] > 0
        ]
        affinity = max(affinities, key=lambda value: value["rawValue"])["label"] if affinities else None
        effect_ids = [int(spell[f"effect{index}"]) for index in range(1, 11) if int(spell[f"effect{index}"]) != 0]
        icon_name = str(spell["icon"])
        icon_targets[icon_name] = args.icon_dir / f"{record_id}.png"
        node_records = [
            {
                "id": int(node["id"]),
                "name": str(node.get("wordentryname") or ""),
                "traditionalName": str(node.get("wordentrynameTW") or ""),
                "description": str(node.get("wordentrydesc") or ""),
                "traditionalDescription": str(node.get("wordentrydescTW") or ""),
                "activationPoints": int(node["activeDianShu"]),
            }
            for node in training_nodes
            if int(node["spellGroup"]) == record_id and node.get("wordentrydesc")
        ]
        if category == "心法":
            heart_affinities: dict[str, int] = {}
            for node in node_records:
                for match in HEART_AFFINITY_PATTERN.finditer(node["description"]):
                    label, value_text = match.groups()
                    heart_affinities[label] = max(
                        heart_affinities.get(label, 0), int(value_text)
                    )
            if len(heart_affinities) != 1:
                raise RuntimeError(
                    f"Expected one training affinity for heart method {record_id}, found {heart_affinities}"
                )
            affinity = next(iter(heart_affinities))
        graph_node_rows = [
            node for node in training_nodes if int(node["spellGroup"]) == record_id
        ]
        graph_node_ids = {int(node["group"]) for node in graph_node_rows}
        graph_nodes = []
        for node in graph_node_rows:
            node_id = int(node["group"])
            position = training_positions[node_id]
            x_text, y_text = str(position["posStr"]).split("|", 1)
            is_root = int(node.get("spellId") or 0) == record_id
            graph_nodes.append(
                {
                    "id": node_id,
                    "name": canonical_name if is_root else str(node.get("wordentryname") or ""),
                    "traditionalName": traditional_name if is_root else str(node.get("wordentrynameTW") or ""),
                    "description": str(spell.get("desc") or "") if is_root else str(node.get("wordentrydesc") or ""),
                    "traditionalDescription": str(spell.get("descTW") or "") if is_root else str(node.get("wordentrydescTW") or ""),
                    "activationPoints": int(node["activeDianShu"]),
                    "nodeType": int(position["nodeType"]),
                    "x": float(x_text),
                    "y": float(y_text),
                    "isRoot": is_root,
                }
            )
        graph_edges = [
            {
                "from": int(edge["startNodeGroup"]),
                "to": int(edge["endNodeGroup"]),
            }
            for edge in training_edges
            if int(edge["startNodeGroup"]) in graph_node_ids
            and int(edge["endNodeGroup"]) in graph_node_ids
        ]
        entry_sources = acquisition_sources(
            record_id,
            manual_item_id,
            shop_by_item,
            merchants_by_group,
            loot_by_item,
            loot_npcs_by_group,
            interaction_by_item,
        )

        entries.append(
            {
                "id": record_id,
                "name": canonical_name,
                "traditionalName": traditional_name,
                "dataName": " / ".join(alternate_names),
                "manualItemId": manual_item_id,
                "manualName": manual_name,
                "manualTraditionalName": manual_traditional_name,
                "acquisitionSources": entry_sources,
                "description": str(spell["desc"]),
                "category": category,
                "listedInWuxuePrototype": record_id in player_wuxue_ids,
                "styleCode": style_code,
                "style": style,
                "quality": int(spell["quality"]),
                "icon": f"/game/wuxue/{record_id}.png",
                "iconSourceName": icon_name,
                "rootNodeId": int(root["id"]),
                "activationPoints": int(root["activeDianShu"]),
                "trainingNodes": node_records,
                "trainingGraph": {
                    "nodes": graph_nodes,
                    "edges": graph_edges,
                },
                "cooldownMs": int(spell["coolDown"]),
                "cooldownSeconds": format_seconds(int(spell["coolDown"])),
                "mpCost": int(spell["mpcost"]),
                "affinity": affinity,
                "power": power,
                "effectIds": effect_ids,
                "timelineAddress": f"SkillData/{record_id}",
                "timelineAvailable": record_id in timeline_available and record_id in addressable_ids,
            }
        )

    entries.sort(
        key=lambda entry: (
            0 if entry["category"] == "功法" else 1,
            entry["styleCode"] if entry["styleCode"] is not None else 99,
            entry["id"],
        )
    )
    export_icons(icon_path, icon_targets)

    payload = {
        "schemaVersion": 8,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "gameVersion": index["yooAsset"]["packageVersion"],
        "sources": {
            "databaseBundle": DB_BUNDLE_NAME,
            "databaseTables": [
                "wuxueprototype.json",
                "spellprotype.json",
                "xiuxi_node.json",
                "xiuxi_node_pos.json",
                "xiuxi_graph.json",
                "item_base.json",
                "stringlang.json",
                "shop.json",
                "loot_items.json",
                "npc_prototype.json",
                "npc_interact.json",
                "mapinfo.json",
            ],
            "iconBundle": ICON_BUNDLE_NAME,
            "timelineAsset": "xiayinglu_Data/resources.assets",
        },
        "counts": {
            "entries": len(entries),
            "playerTableCovered": sum(entry["listedInWuxuePrototype"] for entry in entries),
            "excludedGraphRoots": len(excluded_graph_roots),
            "categories": dict(sorted(Counter(entry["category"] for entry in entries).items())),
            "styles": dict(sorted(Counter(entry["style"] for entry in entries).items())),
            "affinities": dict(
                sorted(Counter(entry["affinity"] for entry in entries if entry["affinity"]).items())
            ),
            "qualities": dict(sorted(Counter(str(entry["quality"]) for entry in entries).items())),
            "timelineCovered": sum(entry["timelineAvailable"] for entry in entries),
        },
        "excludedGraphRoots": excluded_graph_roots,
        "entries": entries,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"Exported {len(entries)} martial-arts records and {len(icon_targets)} icons "
        f"for game version {payload['gameVersion']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
