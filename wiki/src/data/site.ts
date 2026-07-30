export const site = {
  name: '侠影录 Wiki',
  shortName: '侠影录',
  description: '侠影录游戏资料、玩法机制与版本考据百科。',
  repoUrl: import.meta.env.PUBLIC_REPO_URL || '',
  publicEditingEnabled: false,
  buildLabel: '2026-07-25-1164',
  nav: [
    { href: '/', label: '首页' },
    { href: '/entries/', label: '百科目录' },
    { href: '/characters/', label: '人物图鉴' },
    { href: '/mods/', label: 'MOD' },
    { href: '/updates/', label: '游戏更新公告' },
  ],
} as const;
