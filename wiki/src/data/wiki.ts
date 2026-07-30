export type EntryKind = 'system' | 'character' | 'item' | 'guide' | 'research';
export type Verification = 'verified' | 'partial' | 'placeholder';

export interface SourceNote {
  label: string;
  detail: string;
  path?: string;
}

export interface WikiSection {
  id: string;
  title: string;
  paragraphs?: string[];
  bullets?: string[];
  spoiler?: boolean;
}

export interface WikiEntry {
  slug: string;
  title: string;
  subtitle: string;
  kind: EntryKind;
  category: string;
  summary: string;
  tags: string[];
  verification: Verification;
  updated: string;
  image?: string;
  facts: Array<{ label: string; value: string }>;
  sections: WikiSection[];
  sources: SourceNote[];
  related: string[];
  aliases?: string[];
}

export const kindLabels: Record<EntryKind, string> = {
  system: '玩法系统',
  character: '人物',
  item: '物品',
  guide: '攻略',
  research: '考据',
};

export const verificationLabels: Record<Verification, string> = {
  verified: '已核对',
  partial: '待补证',
  placeholder: '待编写',
};

export const entries: WikiEntry[] = [
  {
    slug: 'wuxue',
    title: '武学',
    subtitle: '功法招式与心法修习',
    kind: 'system',
    category: '成长',
    summary: '武学分为功法与心法；功法按剑诀、枪芒、拳罡、刀势整理，心法则拥有独立的装备效果与修习节点。',
    tags: ['秘籍', '心法', '备战', '成长'],
    verification: 'verified',
    updated: '2026-07-25',
    image: '/game/optimized/category-wuxue.webp',
    facts: [
      { label: '主要入口', value: '师门大殿 / 副本掉落' },
      { label: '培养资源', value: '武学修为' },
      { label: '配置位置', value: '备战界面' },
      { label: '关联系统', value: '心法、技能、属性成长' },
    ],
    sections: [
      {
        id: 'acquisition',
        title: '获取方式',
        paragraphs: ['游戏内“如何变强”说明指出，可在师门大殿向小师妹购买武学秘籍；大世界各副本也会掉落秘籍。'],
      },
      {
        id: 'training',
        title: '修炼与配置',
        bullets: ['修炼秘籍可提升武学修为。', '备战界面可自由搭配招式套路。', '心法培养可永久增加属性。'],
      },
      {
        id: 'attributes',
        title: '技能属性',
        paragraphs: ['本地化表中出现“攻、威、阳、阴、柔、刚、毒”以及冷却、消耗字段。具体计算公式仍需结合技能数据逐项验证。'],
      },
    ],
    sources: [
      { label: '游戏 UI 原图', detail: '“如何变强 / 武学”分类说明', path: 'localization-assets-shared_assets_all.bundle' },
      { label: '简体中文本地化表', detail: 'UITexts_zh-Hans：技能描述、技能属性、心法装配等键' },
    ],
    related: ['xianjing', 'zhuwen', 'resource-index'],
  },
  {
    slug: 'zhuangbei',
    title: '装备',
    subtitle: '换装、掉落与打造',
    kind: 'system',
    category: '成长',
    summary: '收录武器、暗器、防具、饰品与宝物，可按一至七阶和品质筛选，并查看固定属性与完整随机词条池。',
    tags: ['武器', '暗器', '防具', '饰品', '宝物', '打造'],
    verification: 'verified',
    updated: '2026-07-27',
    image: '/game/optimized/category-zhuangbei.webp',
    facts: [
      { label: '换装入口', value: '主界面 → 角色' },
      { label: '图鉴规模', value: '175 件玩家装备' },
      { label: '阶级范围', value: '一至七阶 / 无阶特殊' },
      { label: '图鉴分类', value: '武器、暗器、防具、饰品、宝物' },
    ],
    sections: [
      { id: 'equip', title: '换装', paragraphs: ['按 Esc 打开主界面，进入“角色”页即可换装。'] },
      { id: 'acquisition', title: '获取与打造', paragraphs: ['各副本会掉落装备。需要进一步强化时，可在师门基地寻找顾野樵打造。'] },
      { id: 'types', title: '装备分类', bullets: ['武器', '暗器', '防具', '饰品', '宝物'] },
      { id: 'forge', title: '打造关联', paragraphs: ['打造系统同时关联陷阱制作与装备铸纹；具体配方、材料和解锁条件可在对应图鉴中反查。'] },
    ],
    sources: [
      { label: '游戏 UI 原图', detail: '“如何变强 / 装备”分类说明' },
      { label: '简体中文本地化表', detail: '商店与打造界面的装备分类键' },
    ],
    related: ['xianjing', 'zhuwen', 'danyao'],
  },
  {
    slug: 'danyao',
    title: '丹药',
    subtitle: '恢复、增益与永久属性培养',
    kind: 'system',
    category: '成长',
    summary: '收录当前版本 78 种丹药，提供品质、效果、炼制材料、获取方式与永久丹服用上限查询。',
    tags: ['炼丹', '恢复', '增益', '永久属性', '服用上限'],
    verification: 'verified',
    updated: '2026-07-27',
    image: '/game/optimized/category-danyao.webp',
    facts: [
      { label: '丹药总数', value: '78 种' },
      { label: '主要分类', value: '内劲 / 属性 / 恢复 / 功能' },
      { label: '永久丹', value: '33 种' },
      { label: '炼制设施', value: '苍影阁 · 燕衔芦' },
    ],
    sections: [
      { id: 'catalog', title: '丹药图鉴', paragraphs: ['丹药图鉴按内劲、属性、恢复和功能四类整理，并支持品质、作用属性和永久效果筛选。'] },
      { id: 'alchemy', title: '炼制与获取', paragraphs: ['详情页列出燕衔芦炼制材料、铜钱成本、商店购买及游戏掉落记录。'] },
      { id: 'permanent', title: '永久属性丹', paragraphs: ['特殊药品会永久增加角色属性；图鉴同时列出单次增加值、服用次数上限和最大累计收益。'] },
    ],
    sources: [
      { label: '游戏数据库', detail: 'liandanprototype、item_base、spellprotype 与 spelleffect' },
      { label: '来源配置', detail: 'shop、loot_items、npc_prototype 与 npc_interact' },
    ],
    related: ['zhuangbei', 'xianjing', 'resource-index'],
  },
  {
    slug: 'xianjing',
    title: '陷阱',
    subtitle: '机关陷阱、配方与修习路线',
    kind: 'system',
    category: '战斗',
    summary: '收录当前版本 10 种可制作陷阱，提供品质、实际效果、打造材料、铜钱成本和修习节点前置关系。',
    tags: ['陷阱', '机关', '打造', '控制', '修习节点'],
    verification: 'verified',
    updated: '2026-07-29',
    image: '/game/optimized/category-qita.webp',
    facts: [
      { label: '陷阱总数', value: '10 种' },
      { label: '品质范围', value: '普通至绝世' },
      { label: '获取方式', value: '修习解锁后打造' },
      { label: '布设持续', value: '6 秒' },
    ],
    sections: [
      { id: 'catalog', title: '陷阱图鉴', paragraphs: ['图鉴可按品质与伤害、流血、中毒、减速、击飞、灼烧、冻结、眩晕、雷击等效果筛选。'] },
      { id: 'crafting', title: '制作与解锁', paragraphs: ['每种陷阱均有独立打造配方，并需要先消耗修习点激活相应节点；详情页同时展示前置陷阱。'] },
      { id: 'usage', title: '战斗使用', paragraphs: ['当前 10 种陷阱的物品冷却均为 10 秒，布设后持续 6 秒；具体触发效果以各陷阱详情为准。'] },
    ],
    sources: [
      { label: '游戏物品与配方数据库', detail: 'item_base、item_equip 与 dazaoprototype' },
      { label: '修习和效果配置', detail: 'xiuxi_node、xiuxi_graph、spellprotype 与 spelleffect' },
    ],
    related: ['zhuangbei', 'cailiao', 'zhuwen'],
  },
  {
    slug: 'cailiao',
    title: '材料',
    subtitle: '炼丹、打造与铸纹素材',
    kind: 'item',
    category: '物品',
    summary: '收录当前版本 167 种正式材料，提供品质、说明、获取方式以及炼丹、打造和铸纹用途反查。',
    tags: ['材料', '药材', '锻造', '炼丹', '铸纹', '配方'],
    verification: 'verified',
    updated: '2026-07-29',
    image: '/game/optimized/category-qita.webp',
    facts: [
      { label: '材料总数', value: '167 种' },
      { label: '药材', value: '59 种' },
      { label: '锻造材料', value: '105 种' },
      { label: '铸纹材料', value: '3 种' },
    ],
    sections: [
      {
        id: 'scope',
        title: '收录范围',
        paragraphs: ['材料图鉴收录 item_base 中明确标记为正式材料的 167 项记录；剧情物件“麻袋”品质为 0，且描述指向剧情用途，因此未混入材料图鉴。'],
      },
      {
        id: 'filters',
        title: '查询方式',
        paragraphs: ['图鉴支持按药材、锻造主材、锻造辅材和铸纹材料分类，并可组合品质、用途、获取来源与关键词筛选。'],
      },
      {
        id: 'usage',
        title: '用途反查',
        paragraphs: ['材料详情页会反向列出关联丹药、可打造装备和铸纹配置，并标明制作一份目标物品需要消耗的数量。'],
      },
    ],
    sources: [
      { label: '游戏物品数据库', detail: 'item_base：材料名称、说明、分类、品质与堆叠上限' },
      { label: '配方与来源配置', detail: 'liandanprototype、dazaoprototype、zhuwenprototype、shop、loot_items 与 NPC 场景数据' },
    ],
    related: ['danyao', 'zhuangbei', 'resource-index'],
  },
  {
    slug: 'zhuwen',
    title: '铸纹',
    subtitle: '装备词条与铸纹制作',
    kind: 'system',
    category: '成长',
    summary: '已整理 196 项玩家可制作配置，聚合为固定装备词条、神武随机铸纹，以及傀儡和武魄附身材料三套图鉴。',
    tags: ['铸纹', '装备', '词条', '材料', '打造'],
    verification: 'verified',
    updated: '2026-07-29',
    image: '/game/optimized/category-zhuangbei.webp',
    facts: [
      { label: '制作配方', value: '196 项' },
      { label: '固定系列', value: '33 个' },
      { label: '神武铸纹', value: '3 种' },
      { label: '附身材料', value: '18 种' },
    ],
    sections: [
      { id: 'scope', title: '收录范围', paragraphs: ['当前图鉴只统计 196 项实际制作配置；其余 260 条成品映射不作为独立条目重复展示。'] },
      { id: 'fixed', title: '装备铸纹', paragraphs: ['175 项固定词条配方按名称与适用部位聚合为 33 个系列，详情可逐阶比较数值、材料和铜钱。'] },
      { id: 'random', title: '随机与附身', bullets: ['3 种神武铸纹可查询通用效果与指定武学技能池', '9 种傀儡傀纹材料', '9 种武魄魄纹材料'] },
    ],
    sources: [{ label: '游戏铸纹数据库', detail: 'zhuwenprototype：目标装备、属性配置、材料与铜钱成本' }],
    related: ['zhuangbei', 'cailiao', 'xianjing'],
  },
  {
    slug: 'resource-index',
    title: '游戏资源索引',
    subtitle: 'Wiki 内容的版本证据层',
    kind: 'research',
    category: '考据',
    summary: '记录当前游戏构建、Addressables 地址、YooAsset 包和本地化数据的扫描结果。',
    tags: ['资源', '版本', 'Addressables', 'YooAsset'],
    verification: 'verified',
    updated: '2026-07-25',
    facts: [
      { label: '引擎', value: 'Unity IL2CPP' },
      { label: '资源系统', value: 'Addressables + YooAsset' },
      { label: '内容包版本', value: '2026-07-25-1164' },
      { label: '扫描方式', value: '只读、可增量重跑' },
    ],
    sections: [
      { id: 'pipeline', title: '索引流程', bullets: ['读取 Addressables catalog', '读取 YooAsset BuildinCatalog', '扫描 AssetBundle 元数据', '导出明确允许的 UI 素材', '生成 Wiki 构建数据'] },
      { id: 'reproducibility', title: '可复现性', paragraphs: ['运行 scripts/index_game.py 和 scripts/extract_wiki_assets.py 即可按当前安装重建索引与允许发布的素材。脚本不会写入游戏目录。'] },
      { id: 'limits', title: '当前限制', paragraphs: ['IL2CPP 自定义 ScriptableObject 需要类型树或元数据还原。大型场景与音视频包默认跳过，以控制首轮扫描时间。'] },
    ],
    sources: [
      { label: 'Addressables catalog', detail: 'xiayinglu_Data/StreamingAssets/aa/catalog.json' },
      { label: 'YooAsset catalog', detail: 'DefaultPackage/BuildinCatalog.json' },
    ],
    related: ['wuxue'],
  },
];

export const entryBySlug = new Map(entries.map((entry) => [entry.slug, entry]));

export const categories = [
  { slug: 'systems', label: '玩法系统', description: '成长、战斗、装备与探索机制', kinds: ['system', 'item', 'guide'] as EntryKind[] },
  { slug: 'characters', label: '人物', description: '角色、NPC 与人物关系', kinds: ['character'] as EntryKind[] },
  { slug: 'research', label: '考据库', description: '版本证据、资源索引与待验证记录', kinds: ['research'] as EntryKind[] },
];

export function getBacklinks(slug: string): WikiEntry[] {
  return entries.filter((entry) => entry.related.includes(slug));
}
