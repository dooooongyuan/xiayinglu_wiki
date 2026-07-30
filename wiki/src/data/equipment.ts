import generated from './equipment.generated.json';
import { optimizedGameImage } from './images';

export type EquipmentCategory = '武器' | '暗器' | '防具' | '饰品' | '宝物';
export type EquipmentQuality = 1 | 2 | 3 | 4 | 5;

export interface EquipmentAttribute {
  name: string;
  value: string;
  chance: number;
}

export interface EquipmentAffix {
  id: number;
  name: string;
  description: string;
  value: string;
  quality: EquipmentQuality;
  qualityLabel: string;
  weight: number;
}

export interface EquipmentSocketOutcome {
  count: number;
  probability: number;
}

export interface EquipmentSocketRule {
  qualityLabel: string;
  qualities: EquipmentQuality[];
  outcomes: EquipmentSocketOutcome[];
}

export interface EquipmentSocketConfig {
  supported: boolean;
  minimum: number;
  maximum: number;
  summary: string;
  rules: EquipmentSocketRule[];
}

export interface EquipmentAcquisitionSource {
  type: 'initial' | 'forge' | 'combine' | 'shop' | 'contribution' | 'drop' | 'chest' | 'event' | 'unknown';
  title: string;
  detail: string;
}

export interface EquipmentEntry {
  id: number;
  name: string;
  description: string;
  category: EquipmentCategory;
  subtype: string;
  level: number;
  tierLabel: string;
  quality: EquipmentQuality | null;
  qualityMode: 'random' | 'fixed';
  qualityLabel: string;
  icon: string;
  iconSourceName: string;
  fixedAttributes: EquipmentAttribute[];
  intrinsicAttributes: EquipmentAffix[];
  combatPower: Record<string, { label: string; value: number; share: number }>;
  acquisitionSources: EquipmentAcquisitionSource[];
  socketConfig: EquipmentSocketConfig;
  extraAttributes: {
    mode: 'none' | 'fixed' | 'random';
    slotMin: number;
    slotMax: number;
    candidateCount: number;
    candidates: EquipmentAffix[];
  };
}

export interface EquipmentData {
  schemaVersion: number;
  generatedAt: string;
  gameVersion: string;
  sources: {
    databaseBundle: string;
    databaseTables: string[];
    iconBundle: string;
  };
  counts: {
    entries: number;
    categories: Record<EquipmentCategory, number>;
    subtypes: Record<string, number>;
    tiers: Record<string, number>;
    qualities: Record<string, number>;
  };
  entries: EquipmentEntry[];
}

export const equipmentData = generated as unknown as EquipmentData;
export const equipmentEntries = equipmentData.entries.map((entry) => ({ ...entry, icon: optimizedGameImage(entry.icon) }));
export const equipmentById = new Map(equipmentEntries.map((entry) => [entry.id, entry]));
export const equipmentCategories = ['武器', '暗器', '防具', '饰品', '宝物'] as const;
export const equipmentQualities = [1, 2, 3, 4, 5] as const;
export const qualityLabels: Record<EquipmentQuality, string> = {
  1: '普通',
  2: '精良',
  3: '稀有',
  4: '珍奇',
  5: '绝世',
};

export function equipmentHref(entry: EquipmentEntry): string {
  return `/wiki/zhuangbei/${entry.id}/`;
}
