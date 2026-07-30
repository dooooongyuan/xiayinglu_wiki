import generated from './characters.generated.json';

export type CharacterRole = '主要人物' | '剧情人物' | '江湖人物' | '普通 NPC';
export type CharacterRelationType = 'mentorship' | 'school' | 'friendship' | 'alliance' | 'enmity' | 'affection' | 'broken';

export interface CharacterEntry {
  slug: string;
  name: string;
  traditionalName: string;
  aliases: string[];
  portrait: string;
  gender: string;
  faction: string;
  locations: string[];
  levelMin: number;
  levelMax: number;
  description: string;
  role: CharacterRole;
  instanceCount: number;
  isMentionedOnly: boolean;
  relationCount: number;
}

export interface CharacterRelation {
  id: string;
  source: string;
  target: string;
  label: string;
  type: CharacterRelationType;
  directed: boolean;
  evidenceIds: number[];
}

export interface CharacterData {
  schemaVersion: number;
  generatedAt: string;
  gameVersion: string;
  counts: {
    entries: number;
    portraits: number;
    relations: number;
    roles: Record<CharacterRole, number>;
  };
  entries: CharacterEntry[];
  relations: CharacterRelation[];
}

export const characterData = generated as CharacterData;
export const characterEntries = characterData.entries;
export const characterRelations = characterData.relations;
export const characterBySlug = new Map(characterEntries.map((entry) => [entry.slug, entry]));
export const characterRoles: CharacterRole[] = ['主要人物', '剧情人物', '江湖人物', '普通 NPC'];
export const characterFactions = [...new Set(characterEntries.map((entry) => entry.faction).filter((item) => item !== '未标明'))].sort((a, b) => a.localeCompare(b, 'zh-CN'));
export const characterLocations = [...new Set(characterEntries.flatMap((entry) => entry.locations))].sort((a, b) => a.localeCompare(b, 'zh-CN'));

export const relationLabels: Record<CharacterRelationType, string> = {
  mentorship: '师承',
  school: '同门',
  friendship: '挚友',
  alliance: '合作',
  enmity: '敌对',
  affection: '知己',
  broken: '决裂',
};

export function characterHref(entry: CharacterEntry) {
  return `/characters/${entry.slug}/`;
}

export function characterLevel(entry: CharacterEntry) {
  if (!entry.levelMin) return '未标明';
  return entry.levelMin === entry.levelMax ? `${entry.levelMin} 级` : `${entry.levelMin}-${entry.levelMax} 级`;
}

export function relationsForCharacter(slug: string) {
  return characterRelations.filter((relation) => relation.source === slug || relation.target === slug);
}
