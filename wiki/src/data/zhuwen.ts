import generated from './zhuwen.generated.json';
import { optimizedGameImage } from './images';

export type ZhuwenKind = 'fixed' | 'random' | 'companion';
export type ZhuwenQuality = 1 | 2 | 3 | 4 | 5;
export type ZhuwenDirection = '基础属性' | '战斗属性' | '内劲属性' | '资源收益' | '特殊效果' | '武学强化' | '附身材料';
export type ZhuwenPart = '武器' | '衣服' | '鞋靴' | '饰品' | '傀儡' | '武魄';

export interface ZhuwenMaterial {
  id: number;
  name: string;
  count: number;
  quality: ZhuwenQuality;
}

export interface ZhuwenRecipe {
  configId: number;
  targetItemId: number;
  quality: ZhuwenQuality;
  qualityLabel: string;
  icon: string;
  costMoney: number;
  materials: ZhuwenMaterial[];
}

export interface ZhuwenCandidate {
  id: number;
  name: string;
  value: string;
  description: string;
  quality: ZhuwenQuality;
  qualityLabel: string;
  weight: number;
}

export interface ZhuwenSpellGroup {
  spellId: number;
  spellName: string;
  candidates: ZhuwenCandidate[];
}

export interface ZhuwenBaseEntry {
  slug: string;
  kind: ZhuwenKind;
  name: string;
  shortName: string;
  description: string;
  applicableParts: ZhuwenPart[];
  direction: ZhuwenDirection;
  quality: ZhuwenQuality;
  qualityLabel: string;
  icon: string;
}

export interface ZhuwenStage extends ZhuwenRecipe {
  stage: number;
  value: string;
  description: string;
}

export interface FixedZhuwenEntry extends ZhuwenBaseEntry {
  kind: 'fixed';
  wordEntryTypeId: number;
  stageCount: number;
  valueRange: string;
  stages: ZhuwenStage[];
}

export interface RandomZhuwenEntry extends ZhuwenBaseEntry {
  kind: 'random';
  groupId: number;
  candidateCount: number;
  genericCandidates: ZhuwenCandidate[];
  spellGroups: ZhuwenSpellGroup[];
  recipe: ZhuwenRecipe;
}

export interface CompanionZhuwenEntry extends ZhuwenBaseEntry {
  kind: 'companion';
  companionType: '傀儡材料' | '武魄材料';
  heatValue: number;
  groupId: number;
  candidateCount: number;
  genericCandidates: ZhuwenCandidate[];
  spellGroups: ZhuwenSpellGroup[];
  unlock: {
    nodeId: number;
    nodeName: string;
    points: number;
  };
  recipe: ZhuwenRecipe;
}

export type ZhuwenEntry = FixedZhuwenEntry | RandomZhuwenEntry | CompanionZhuwenEntry;

export interface ZhuwenData {
  schemaVersion: number;
  generatedAt: string;
  gameVersion: string;
  counts: {
    recipes: number;
    fixedRecipes: number;
    fixedSeries: number;
    randomEntries: number;
    companionEntries: number;
    puppetEntries: number;
    soulEntries: number;
    entries: number;
    directions: Partial<Record<ZhuwenDirection, number>>;
    qualities: Record<string, number>;
  };
  entries: ZhuwenEntry[];
}

export const zhuwenData = generated as ZhuwenData;
export const zhuwenEntries = zhuwenData.entries.map((entry) => ({ ...entry, icon: optimizedGameImage(entry.icon) }));
export const fixedZhuwenEntries = zhuwenEntries.filter((entry): entry is FixedZhuwenEntry => entry.kind === 'fixed');
export const randomZhuwenEntries = zhuwenEntries.filter((entry): entry is RandomZhuwenEntry => entry.kind === 'random');
export const companionZhuwenEntries = zhuwenEntries.filter((entry): entry is CompanionZhuwenEntry => entry.kind === 'companion');
export const zhuwenBySlug = new Map(zhuwenEntries.map((entry) => [entry.slug, entry]));
export const zhuwenQualities = [1, 2, 3, 4, 5] as const;
export const zhuwenDirections = ['基础属性', '战斗属性', '内劲属性', '资源收益', '特殊效果'] as const;
export const zhuwenParts = ['武器', '衣服', '鞋靴', '饰品', '傀儡', '武魄'] as const;
export const zhuwenQualityLabels: Record<ZhuwenQuality, string> = {
  1: '普通',
  2: '精良',
  3: '稀有',
  4: '珍奇',
  5: '绝世',
};

export function zhuwenHref(entry: ZhuwenEntry): string {
  return `/wiki/zhuwen/${entry.slug}/`;
}

export function zhuwenKindLabel(entry: ZhuwenEntry): string {
  if (entry.kind === 'fixed') return '装备铸纹';
  if (entry.kind === 'random') return '随机铸纹';
  return entry.companionType;
}
