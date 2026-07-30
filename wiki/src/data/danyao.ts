import generated from './danyao.generated.json';
import { optimizedGameImage } from './images';

export type DanyaoCategory = '内劲' | '属性' | '恢复' | '功能';
export type DanyaoQuality = 1 | 2 | 3 | 4 | 5;

export interface DanyaoMaterial {
  id: number;
  name: string;
  count: number;
}

export interface DanyaoAcquisitionSource {
  type: 'alchemy' | 'shop' | 'drop' | 'chest' | 'event';
  title: string;
  detail: string;
}

export interface DanyaoEntry {
  id: number;
  name: string;
  traditionalName: string;
  description: string;
  usageDescription: string;
  category: DanyaoCategory;
  quality: DanyaoQuality;
  qualityLabel: string;
  icon: string;
  iconSourceName: string;
  effect: {
    attributeCode: number;
    attribute: string;
    value: number;
    durationSeconds: number;
    description: string;
  };
  useCooldownSeconds: number;
  isPermanent: boolean;
  isSpecial: boolean;
  useLimit: number | null;
  maximumGain: number | null;
  recipe: {
    costMoney: number;
    materials: DanyaoMaterial[];
  };
  acquisitionSources: DanyaoAcquisitionSource[];
}

export interface DanyaoData {
  schemaVersion: number;
  generatedAt: string;
  gameVersion: string;
  counts: {
    entries: number;
    categories: Record<DanyaoCategory, number>;
    qualities: Record<string, number>;
    attributes: Record<string, number>;
    permanent: number;
    special: number;
  };
  entries: DanyaoEntry[];
}

export const danyaoData = generated as DanyaoData;
export const danyaoEntries = danyaoData.entries.map((entry) => ({ ...entry, icon: optimizedGameImage(entry.icon) }));
export const danyaoById = new Map(danyaoEntries.map((entry) => [entry.id, entry]));
export const danyaoCategories = ['内劲', '属性', '恢复', '功能'] as const;
export const danyaoQualities = [1, 2, 3, 4, 5] as const;
export const danyaoAttributes = Object.keys(danyaoData.counts.attributes).sort((left, right) => left.localeCompare(right, 'zh-CN'));
export const danyaoQualityLabels: Record<DanyaoQuality, string> = {
  1: '普通',
  2: '精良',
  3: '稀有',
  4: '珍奇',
  5: '绝世',
};

export function danyaoHref(entry: DanyaoEntry): string {
  return `/wiki/danyao/${entry.id}/`;
}
