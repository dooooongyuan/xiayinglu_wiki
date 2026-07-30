import rss from '@astrojs/rss';
import { entries } from '../data/wiki';

export function GET(context) {
  return rss({
    title: '侠影录 Wiki 更新',
    description: '侠影录游戏百科条目更新',
    site: context.site,
    items: entries.map((entry) => ({
      title: entry.title,
      description: entry.summary,
      pubDate: new Date(`${entry.updated}T00:00:00+08:00`),
      link: `${entry.kind === 'research' ? '/research' : '/wiki'}/${entry.slug}/`,
    })),
  });
}
