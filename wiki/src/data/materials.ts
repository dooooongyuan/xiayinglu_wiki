import generated from './materials.generated.json';
import { optimizedGameImage } from './images';

export type MaterialCategory = '药材' | '锻造主材' | '锻造辅材' | '铸纹材料';
export type MaterialQuality = 1 | 2 | 3 | 4 | 5;
export type MaterialUsageKind = '炼丹' | '打造' | '铸纹';
export type MaterialSourceType = 'dismantle' | 'smelting' | 'shop' | 'gathering' | 'exploration' | 'dungeon' | 'chest' | 'drop' | 'reward';

export interface MaterialSource {
  type: MaterialSourceType;
  title: string;
  detail: string;
}

export interface MaterialUsageTarget {
  id: number;
  name: string;
  count: number;
  targetKind?: '装备' | '陷阱' | '机关道具';
  hasDetail?: boolean;
}

export interface MaterialInscriptionTarget {
  id: number;
  slug: string;
  name: string;
  recipeCount: number;
  countMin: number;
  countMax: number;
}

export interface MaterialEntry {
  id: number;
  name: string;
  traditionalName: string;
  description: string;
  category: MaterialCategory;
  quality: MaterialQuality;
  qualityLabel: string;
  icon: string;
  iconSourceName: string;
  stackLimit: number;
  usageKinds: MaterialUsageKind[];
  usage: {
    alchemy: MaterialUsageTarget[];
    forging: MaterialUsageTarget[];
    inscription: {
      recipeCount: number;
      targets: MaterialInscriptionTarget[];
    };
  };
  acquisitionSources: MaterialSource[];
  sourceTypes: MaterialSourceType[];
}

export interface MaterialsData {
  schemaVersion: number;
  generatedAt: string;
  gameVersion: string;
  counts: {
    entries: number;
    categories: Record<MaterialCategory, number>;
    qualities: Record<string, number>;
    usageKinds: Record<MaterialUsageKind, number>;
    sourceTypes: Partial<Record<MaterialSourceType, number>>;
  };
  entries: MaterialEntry[];
}

export const materialsData = generated as MaterialsData;
export const materialEntries = materialsData.entries.map((entry) => ({ ...entry, icon: optimizedGameImage(entry.icon) }));
export const materialById = new Map(materialEntries.map((entry) => [entry.id, entry]));
export const materialCategories = ['药材', '锻造主材', '锻造辅材', '铸纹材料'] as const;
export const materialQualities = [1, 2, 3, 4, 5] as const;
export const materialUsageKinds = ['炼丹', '打造', '铸纹'] as const;
export const materialSourceTypes = ['dismantle', 'smelting', 'shop', 'gathering', 'exploration', 'dungeon', 'chest', 'drop', 'reward'] as const;
export const materialQualityLabels: Record<MaterialQuality, string> = {
  1: '普通',
  2: '精良',
  3: '稀有',
  4: '珍奇',
  5: '绝世',
};
export const materialSourceLabels: Record<MaterialSourceType, string> = {
  dismantle: '天工分解',
  smelting: '天工熔炼',
  shop: '商店购买',
  gathering: '地图采集',
  exploration: '场景探索',
  dungeon: '副本产出',
  chest: '宝箱获取',
  drop: '敌人掉落',
  reward: '副本奖励',
};

export function materialHref(entry: MaterialEntry): string {
  return `/wiki/cailiao/${entry.id}/`;
}
