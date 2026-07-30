import { entries, kindLabels } from './wiki';
import { wuxueEntries, wuxueHref, wuxueQualityLabels } from './wuxue';
import { equipmentEntries, equipmentHref } from './equipment';
import { danyaoEntries, danyaoHref } from './danyao';
import { materialEntries, materialHref } from './materials';
import { trapEntries, trapHref } from './traps';
import { zhuwenEntries, zhuwenHref, zhuwenKindLabel } from './zhuwen';
import { characterEntries, characterHref } from './characters';
import steamNews from './steam-news.generated.json';

export interface SearchEntry {
  title: string;
  subtitle: string;
  summary: string;
  tags: string[];
  aliases: string[];
  kindLabel: string;
  href: string;
}

export const searchEntries: SearchEntry[] = [
  {
    title: 'MOD',
    subtitle: '社区扩展分类',
    summary: '侠影录 MOD 内容分类，当前正在设计中。',
    tags: ['MOD', '模组', '插件', '社区扩展'],
    aliases: ['模组'],
    kindLabel: '分类',
    href: '/mods/',
  },
  {
    title: '游戏更新公告',
    subtitle: 'Steam 官方消息',
    summary: '汇总侠影录的版本更新、问题修复与后续计划。',
    tags: ['更新', '公告', '版本', '补丁', 'Steam'],
    aliases: ['更新日志', '版本公告'],
    kindLabel: '资讯',
    href: '/updates/',
  },
  ...steamNews.items.map((item) => ({
    title: item.title,
    subtitle: 'Steam 游戏更新公告',
    summary: item.excerpt,
    tags: ['更新', '公告', '版本', '补丁', 'Steam'],
    aliases: [],
    kindLabel: '更新公告',
    href: `/updates/${item.id}/`,
  })),
  ...entries.map(({ slug, title, subtitle, summary, kind, tags, aliases = [] }) => ({
    title,
    subtitle,
    summary,
    tags,
    aliases,
    kindLabel: kindLabels[kind],
    href: `/${kind === 'research' ? 'research' : 'wiki'}/${slug}/`,
  })),
  ...wuxueEntries.map((entry) => ({
    title: entry.name,
    subtitle: `${entry.category}${entry.category === '功法' ? ` · ${entry.style}` : ''}${entry.manualName && entry.manualName !== entry.name ? ` · 秘籍 ${entry.manualName}` : ''} · ${wuxueQualityLabels[entry.quality]}`,
    summary: entry.description,
    tags: [entry.category, entry.style, entry.affinity || '', wuxueQualityLabels[entry.quality], entry.traditionalName, entry.dataName, entry.manualName, entry.manualTraditionalName].filter(Boolean),
    aliases: [entry.traditionalName, entry.dataName, entry.manualName, entry.manualTraditionalName].filter(Boolean),
    kindLabel: entry.category,
    href: wuxueHref(entry),
  })),
  ...equipmentEntries.map((entry) => ({
    title: entry.name,
    subtitle: `${entry.category} · ${entry.subtype} · ${entry.category === '武器' || entry.category === '防具' || entry.category === '饰品' ? `${entry.tierLabel} · ` : ''}${entry.qualityLabel}`,
    summary: entry.description,
    tags: [
      entry.category,
      entry.subtype,
      entry.tierLabel,
      entry.qualityLabel,
      ...entry.fixedAttributes.map((attribute) => attribute.name),
      ...entry.extraAttributes.candidates.map((candidate) => candidate.name),
    ],
    aliases: [],
    kindLabel: '装备',
    href: equipmentHref(entry),
  })),
  ...danyaoEntries.map((entry) => ({
    title: entry.name,
    subtitle: `${entry.category} · ${entry.qualityLabel} · ${entry.effect.attribute}`,
    summary: entry.usageDescription || entry.description,
    tags: [
      entry.traditionalName,
      entry.category,
      entry.qualityLabel,
      entry.effect.attribute,
      entry.effect.description,
      entry.isPermanent ? '永久加点' : '',
      entry.isSpecial ? '特殊药品' : '',
      ...entry.recipe.materials.map((material) => material.name),
      ...entry.acquisitionSources.flatMap((source) => [source.title, source.detail]),
    ].filter(Boolean),
    aliases: entry.traditionalName && entry.traditionalName !== entry.name ? [entry.traditionalName] : [],
    kindLabel: '丹药',
    href: danyaoHref(entry),
  })),
  ...materialEntries.map((entry) => ({
    title: entry.name,
    subtitle: `${entry.category} · ${entry.qualityLabel}${entry.usageKinds.length ? ` · ${entry.usageKinds.join(' / ')}` : ''}`,
    summary: entry.description,
    tags: [
      entry.traditionalName,
      entry.category,
      entry.qualityLabel,
      ...entry.usageKinds,
      ...entry.usage.alchemy.map((target) => target.name),
      ...entry.usage.forging.map((target) => target.name),
      ...entry.acquisitionSources.flatMap((source) => [source.title, source.detail]),
    ].filter(Boolean),
    aliases: entry.traditionalName && entry.traditionalName !== entry.name ? [entry.traditionalName] : [],
    kindLabel: '材料',
    href: materialHref(entry),
  })),
  ...trapEntries.map((entry) => ({
    title: entry.name,
    subtitle: `陷阱 · ${entry.qualityLabel} · ${entry.effectTags.join(' / ')}`,
    summary: entry.effectSummary,
    tags: [
      entry.traditionalName,
      entry.qualityLabel,
      ...entry.effectTags,
      ...entry.recipe.materials.map((material) => material.name),
      ...entry.unlock.prerequisites.map((prerequisite) => prerequisite.name),
    ].filter(Boolean),
    aliases: entry.traditionalName && entry.traditionalName !== entry.name ? [entry.traditionalName] : [],
    kindLabel: '陷阱',
    href: trapHref(entry),
  })),
  ...zhuwenEntries.map((entry) => ({
    title: entry.name,
    subtitle: `${zhuwenKindLabel(entry)} · ${entry.qualityLabel} · ${entry.applicableParts.join(' / ')}`,
    summary: entry.description,
    tags: [
      entry.shortName,
      entry.direction,
      entry.qualityLabel,
      ...entry.applicableParts,
      ...(entry.kind === 'fixed'
        ? entry.stages.flatMap((stage) => stage.materials.map((material) => material.name))
        : [
            ...entry.recipe.materials.map((material) => material.name),
            ...entry.genericCandidates.map((candidate) => candidate.name),
            ...entry.spellGroups.map((group) => group.spellName),
          ]),
    ],
    aliases: entry.shortName !== entry.name ? [entry.shortName] : [],
    kindLabel: '铸纹',
    href: zhuwenHref(entry),
  })),
  ...characterEntries.map((entry) => ({
    title: entry.name,
    subtitle: `${entry.role} · ${entry.faction}${entry.locations.length ? ` · ${entry.locations.slice(0, 2).join(' / ')}` : ''}`,
    summary: entry.description,
    tags: [entry.traditionalName, entry.role, entry.gender, entry.faction, ...entry.locations].filter(Boolean),
    aliases: [entry.traditionalName, ...entry.aliases].filter(Boolean),
    kindLabel: '人物',
    href: characterHref(entry),
  })),
];
