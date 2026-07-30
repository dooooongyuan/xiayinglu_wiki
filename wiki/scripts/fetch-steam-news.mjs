import { readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';

const appId = 3863760;
const count = 16;
const strict = process.argv.includes('--strict');
const outputPath = path.resolve(import.meta.dirname, '..', 'src', 'data', 'steam-news.generated.json');
const apiUrl = new URL('https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/');
apiUrl.search = new URLSearchParams({
  appid: String(appId),
  count: String(count),
  maxlength: '0',
  format: 'json',
  feeds: 'steam_community_announcements',
}).toString();

function decodeEntities(value) {
  const named = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ' };
  return value.replace(/&(#x?[0-9a-f]+|[a-z]+);/gi, (match, entity) => {
    if (entity[0] === '#') {
      const hexadecimal = entity[1]?.toLowerCase() === 'x';
      const codePoint = Number.parseInt(entity.slice(hexadecimal ? 2 : 1), hexadecimal ? 16 : 10);
      return Number.isFinite(codePoint) && codePoint >= 0 && codePoint <= 0x10ffff ? String.fromCodePoint(codePoint) : match;
    }
    return named[entity.toLowerCase()] ?? match;
  });
}

function safeExternalUrl(value) {
  const candidate = decodeEntities(String(value || '')).trim().replace(/^["']|["']$/g, '');
  try {
    const url = new URL(candidate);
    return url.protocol === 'http:' || url.protocol === 'https:' ? url.href : '';
  } catch {
    return '';
  }
}

function stripInlineTags(value) {
  return decodeEntities(value)
    .replace(/\[img(?:\s+[^\]]*)?\][\s\S]*?\[\/img\]/gi, ' ')
    .replace(/\[img\s+[^\]]*\]/gi, ' ')
    .replace(/\[[^\]]+\]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function appendPlainSegments(segments, value) {
  const text = stripInlineTags(value);
  if (!text) return;

  const urlPattern = /https?:\/\/[^\s<>"'\[\]]+/gi;
  let cursor = 0;
  for (const match of text.matchAll(urlPattern)) {
    const index = match.index ?? 0;
    if (index > cursor) segments.push({ text: text.slice(cursor, index) });
    const href = safeExternalUrl(match[0]);
    segments.push(href ? { text: match[0], href } : { text: match[0] });
    cursor = index + match[0].length;
  }
  if (cursor < text.length) segments.push({ text: text.slice(cursor) });
}

function parseInlineSegments(value) {
  const segments = [];
  const urlTagPattern = /\[url(?:=([^\]]+))?\]([\s\S]*?)\[\/url\]/gi;
  let cursor = 0;
  for (const match of value.matchAll(urlTagPattern)) {
    const index = match.index ?? 0;
    appendPlainSegments(segments, value.slice(cursor, index));
    const label = stripInlineTags(match[2]) || stripInlineTags(match[1] || '');
    const href = safeExternalUrl(match[1] || label);
    if (label) segments.push(href ? { text: label, href } : { text: label });
    cursor = index + match[0].length;
  }
  appendPlainSegments(segments, value.slice(cursor));
  return segments;
}

function extractImages(contents) {
  const images = [];
  const seen = new Set();
  const add = (value) => {
    const url = safeExternalUrl(value);
    if (url && !seen.has(url)) {
      seen.add(url);
      images.push(url);
    }
  };

  for (const match of contents.matchAll(/\[img\]([\s\S]*?)\[\/img\]/gi)) add(stripInlineTags(match[1]));
  for (const match of contents.matchAll(/\[img\s+([^\]]*)\]/gi)) {
    const source = match[1].match(/src\s*=\s*["']([^"']+)["']/i)?.[1];
    if (source) add(source);
  }
  return images;
}

function toContentBlocks(contents) {
  const marked = decodeEntities(contents)
    .replace(/\r?\n/g, ' ')
    .replace(/\[img\][\s\S]*?\[\/img\]/gi, '\n')
    .replace(/\[img\s+[^\]]*\]/gi, '\n')
    .replace(/\[h[1-6](?:\s+[^\]]*|=[^\]]*)?\]/gi, '\n::heading::')
    .replace(/\[\/h[1-6]\]/gi, '\n')
    .replace(/\[\*\]/g, '\n::item::')
    .replace(/\[\/\*\]/g, '\n')
    .replace(/\[p(?:\s+[^\]]*|=[^\]]*)?\]/gi, '')
    .replace(/\[\/p\]/gi, '\n')
    .replace(/\[\/?(?:list|quote|code)(?:\s+[^\]]*|=[^\]]*)?\]/gi, '\n')
    .replace(/\[(?:hr)(?:\s+[^\]]*|=[^\]]*)?\](?:\[\/hr\])?/gi, '\n::rule::\n')
    .replace(/\[(?:br)(?:\s+[^\]]*|=[^\]]*)?\](?:\[\/br\])?/gi, '\n');

  return marked
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const type = line.startsWith('::heading::') ? 'heading' : line.startsWith('::item::') ? 'item' : line === '::rule::' ? 'rule' : 'paragraph';
      const source = line.replace(/^::(?:heading|item)::/, '');
      return { type, segments: type === 'rule' ? [] : parseInlineSegments(source) };
    })
    .filter((block) => block.type === 'rule' || block.segments.some((segment) => segment.text.trim()));
}

function excerpt(blocks, maxLength = 220) {
  const text = blocks.flatMap((block) => block.segments.map((segment) => segment.text)).join(' ').replace(/\s+/g, ' ').trim();
  if (text.length <= maxLength) return text;
  const candidate = text.slice(0, maxLength);
  const sentenceEnd = Math.max(candidate.lastIndexOf('。'), candidate.lastIndexOf('！'), candidate.lastIndexOf('？'));
  return `${candidate.slice(0, sentenceEnd >= 100 ? sentenceEnd + 1 : maxLength).trim()}…`;
}

async function readExistingData() {
  try {
    const existing = JSON.parse(await readFile(outputPath, 'utf8'));
    return Array.isArray(existing.items) && existing.items.length > 0 ? existing : null;
  } catch {
    return null;
  }
}

function comparableData(data) {
  return JSON.stringify({
    appId: data.appId,
    storeUrl: data.storeUrl,
    items: data.items,
  });
}

try {
  const response = await fetch(apiUrl, {
    headers: { 'user-agent': 'xiayinglu-wiki-news-fetcher/1.0' },
    signal: AbortSignal.timeout(20_000),
  });
  if (!response.ok) throw new Error(`Steam API returned HTTP ${response.status}`);

  const payload = await response.json();
  const newsItems = payload?.appnews?.newsitems;
  if (!Array.isArray(newsItems) || newsItems.length === 0) throw new Error('Steam API returned no announcements');

  const generated = {
    appId,
    storeUrl: `https://store.steampowered.com/news/app/${appId}`,
    fetchedAt: new Date().toISOString(),
    items: newsItems.map((item) => {
      const contents = String(item.contents || '');
      const blocks = toContentBlocks(contents);
      return {
        id: String(item.gid),
        title: String(item.title || '未命名公告').trim(),
        url: `https://store.steampowered.com/news/app/${appId}/view/${item.gid}`,
        publishedAt: new Date(Number(item.date) * 1000).toISOString(),
        excerpt: excerpt(blocks),
        blocks,
        images: extractImages(contents),
        tags: Array.isArray(item.tags) ? item.tags.map(String) : [],
      };
    }),
  };

  const existing = await readExistingData();
  if (existing && comparableData(existing) === comparableData(generated)) {
    console.log(`Steam announcements are already current (${generated.items.length} items).`);
  } else {
    await writeFile(outputPath, `${JSON.stringify(generated, null, 2)}\n`, 'utf8');
    console.log(`Updated ${generated.items.length} Steam announcements in ${outputPath}`);
  }
} catch (error) {
  const detail = error instanceof Error ? error.message : String(error);
  if (await readExistingData()) {
    console.warn(`Steam announcements were not refreshed; keeping existing data. ${detail}`);
    if (strict) process.exitCode = 1;
  } else {
    console.error(`Steam announcements are unavailable and no existing data was found. ${detail}`);
    process.exitCode = 1;
  }
}
