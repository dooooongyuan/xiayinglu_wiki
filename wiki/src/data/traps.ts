import generated from './traps.generated.json';
import { optimizedGameImage } from './images';

export type TrapQuality = 1 | 2 | 3 | 4 | 5;
export type TrapEffectTag = '伤害' | '流血' | '中毒' | '减速' | '击飞' | '灼烧' | '冻结' | '冻伤' | '眩晕' | '雷击';

export interface TrapMaterial {
  id: number;
  name: string;
  count: number;
}

export interface TrapPrerequisite {
  nodeId: number;
  itemId: number;
  name: string;
}

export interface TrapEntry {
  id: number;
  name: string;
  traditionalName: string;
  description: string;
  effectSummary: string;
  effectTags: TrapEffectTag[];
  quality: TrapQuality;
  qualityLabel: string;
  icon: string;
  iconSourceName: string;
  useCooldownSeconds: number;
  stackLimit: number;
  effect: {
    durationSeconds: number;
    triggerIntervalSeconds: number;
    triggerMode: '单次触发' | '持续检测';
  };
  unlock: {
    nodeId: number;
    points: number;
    prerequisites: TrapPrerequisite[];
  };
  recipe: {
    costMoney: number;
    materials: TrapMaterial[];
  };
  acquisitionSources: Array<{
    type: 'crafting';
    title: string;
    detail: string;
  }>;
}

export interface TrapsData {
  schemaVersion: number;
  generatedAt: string;
  gameVersion: string;
  counts: {
    entries: number;
    qualities: Record<string, number>;
    effectTags: Partial<Record<TrapEffectTag, number>>;
  };
  entries: TrapEntry[];
}

export const trapsData = generated as TrapsData;
export const trapEntries = trapsData.entries.map((entry) => ({ ...entry, icon: optimizedGameImage(entry.icon) }));
export const trapById = new Map(trapEntries.map((entry) => [entry.id, entry]));
export const trapQualities = [1, 2, 3, 4, 5] as const;
export const trapQualityLabels: Record<TrapQuality, string> = {
  1: '普通',
  2: '精良',
  3: '稀有',
  4: '珍奇',
  5: '绝世',
};
export const trapEffectTags = ['伤害', '流血', '中毒', '减速', '击飞', '灼烧', '冻结', '冻伤', '眩晕', '雷击'] as const;

export function trapHref(entry: TrapEntry): string {
  return `/wiki/xianjing/${entry.id}/`;
}
