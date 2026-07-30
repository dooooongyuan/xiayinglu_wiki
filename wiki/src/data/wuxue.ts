import generated from './wuxue.generated.json';
import { optimizedGameImage } from './images';

export type WuxueQuality = 2 | 3 | 4 | 5;

export interface WuxuePowerValue {
  label: string;
  rawValue: number;
}

export interface WuxueTrainingNode {
  id: number;
  name: string;
  traditionalName: string;
  description: string;
  traditionalDescription: string;
  activationPoints: number;
}

export interface WuxueTrainingGraphNode extends WuxueTrainingNode {
  nodeType: 1 | 2 | 3;
  x: number;
  y: number;
  isRoot: boolean;
}

export interface WuxueTrainingGraphEdge {
  from: number;
  to: number;
}

export interface WuxueTrainingGraph {
  nodes: WuxueTrainingGraphNode[];
  edges: WuxueTrainingGraphEdge[];
}

export interface WuxueAcquisitionSource {
  type: 'initial' | 'shop' | 'drop' | 'chest' | 'quest' | 'event' | 'explore' | 'unavailable' | 'unknown';
  title: string;
  detail: string;
}

export interface WuxueEntry {
  id: number;
  name: string;
  traditionalName: string;
  dataName: string;
  manualItemId: number | null;
  manualName: string;
  manualTraditionalName: string;
  acquisitionSources: WuxueAcquisitionSource[];
  description: string;
  category: '功法' | '心法';
  listedInWuxuePrototype: boolean;
  styleCode: number | null;
  style: string;
  quality: WuxueQuality;
  icon: string;
  iconSourceName: string;
  rootNodeId: number;
  activationPoints: number;
  trainingNodes: WuxueTrainingNode[];
  trainingGraph: WuxueTrainingGraph;
  cooldownMs: number;
  cooldownSeconds: number;
  mpCost: number;
  affinity: string | null;
  power: Record<string, WuxuePowerValue>;
  effectIds: number[];
  timelineAddress: string;
  timelineAvailable: boolean;
}

export interface WuxueData {
  schemaVersion: number;
  generatedAt: string;
  gameVersion: string;
  sources: {
    databaseBundle: string;
    databaseTables: string[];
    iconBundle: string;
    timelineAsset: string;
  };
  counts: {
    entries: number;
    playerTableCovered: number;
    excludedGraphRoots: number;
    categories: Record<string, number>;
    styles: Record<string, number>;
    affinities: Record<string, number>;
    qualities: Record<string, number>;
    timelineCovered: number;
  };
  excludedGraphRoots: Array<{ id: number; name: string; reason: string }>;
  entries: WuxueEntry[];
}

export const wuxueData = generated as WuxueData;
export const wuxueEntries = wuxueData.entries.map((entry) => ({ ...entry, icon: optimizedGameImage(entry.icon) }));
export const wuxueById = new Map(wuxueEntries.map((entry) => [entry.id, entry]));
export const wuxueCategories = ['功法', '心法'] as const;
export const wuxueStyles = ['剑诀', '枪芒', '拳罡', '刀势'];
export const wuxueAffinities = ['阳', '阴', '柔', '刚', '毒'];
export const wuxueQualities: WuxueQuality[] = [2, 3, 4, 5];
export const wuxueQualityLabels: Record<WuxueQuality, string> = {
  2: '精良',
  3: '稀有',
  4: '珍奇',
  5: '绝世',
};

export function wuxueHref(entry: WuxueEntry): string {
  return `/wiki/wuxue/${entry.id}/`;
}
