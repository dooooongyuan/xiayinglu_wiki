import { readdir, readFile } from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';
import { performance } from 'node:perf_hooks';
import { parse } from 'parse5';

const startedAt = performance.now();
const siteRoot = path.resolve(import.meta.dirname, '..', 'dist');
const localOrigin = 'https://wiki.local';
const scopes = process.argv.slice(2).filter((argument) => !argument.startsWith('-')).map(normalizeScope);
const failures = [];

function normalizeScope(scope) {
  const url = new URL(scope, localOrigin);
  return url.pathname.endsWith('/') ? url.pathname : `${url.pathname}/`;
}

async function collectFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const nested = await Promise.all(entries.map((entry) => {
    const target = path.join(directory, entry.name);
    return entry.isDirectory() ? collectFiles(target) : [target];
  }));
  return nested.flat();
}

function routeFromHtmlFile(file) {
  const relative = path.relative(siteRoot, file).split(path.sep).join('/');
  if (relative === 'index.html') return '/';
  if (relative.endsWith('/index.html')) return `/${relative.slice(0, -'index.html'.length)}`;
  return `/${relative}`;
}

function attributesOf(node) {
  return new Map((node.attrs || []).map(({ name, value }) => [name, value]));
}

function extractDocument(html, file) {
  const links = [];
  const anchors = new Set();
  const document = parse(html);
  const stack = [document];

  while (stack.length) {
    const node = stack.pop();
    const attributes = attributesOf(node);
    const id = attributes.get('id');
    const name = attributes.get('name');
    if (id) anchors.add(id);
    if (name) anchors.add(name);
    if (node.tagName === 'a' && attributes.get('href')) links.push(attributes.get('href'));
    if (node.childNodes) stack.push(...node.childNodes);
    if (node.content?.childNodes) stack.push(...node.content.childNodes);
  }

  return { file, route: routeFromHtmlFile(file), links, anchors };
}

function safeDecode(value) {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

function targetCandidates(pathname) {
  const decoded = safeDecode(pathname).replace(/^\/+/, '');
  const direct = path.resolve(siteRoot, ...decoded.split('/').filter(Boolean));
  if (direct !== siteRoot && !direct.startsWith(`${siteRoot}${path.sep}`)) return [];
  if (pathname.endsWith('/')) return [path.join(direct, 'index.html')];
  if (path.extname(decoded)) return [direct];
  return [direct, `${direct}.html`, path.join(direct, 'index.html')];
}

function inScope(route) {
  if (!scopes.length) return true;
  return scopes.some((scope) => route === scope || route.startsWith(scope));
}

let allFiles;
try {
  allFiles = await collectFiles(siteRoot);
} catch (error) {
  console.error(`无法读取静态构建目录 ${siteRoot}。请先运行 npm run build。`);
  console.error(error instanceof Error ? error.message : error);
  process.exit(1);
}

const htmlFiles = allFiles.filter((file) => file.endsWith('.html'));
const existingFiles = new Set(allFiles.map((file) => path.resolve(file)));
const sourceFiles = htmlFiles.filter((file) => inScope(routeFromHtmlFile(file)));
const documentPromises = new Map();

function loadDocument(file) {
  const resolved = path.resolve(file);
  if (!documentPromises.has(resolved)) {
    documentPromises.set(resolved, readFile(resolved, 'utf8').then((html) => extractDocument(html, resolved)));
  }
  return documentPromises.get(resolved);
}

function firstExistingFile(candidates) {
  return candidates.map((candidate) => path.resolve(candidate)).find((candidate) => existingFiles.has(candidate)) || null;
}

const sourceDocuments = await Promise.all(sourceFiles.map(loadDocument));

if (!sourceDocuments.length) {
  console.error(`没有找到与检查范围匹配的页面：${scopes.join('、')}`);
  process.exit(1);
}

const checkedTargets = new Map();
const checkedFragments = new Set();
let linkCount = 0;

for (const document of sourceDocuments) {
  const sourceUrl = new URL(document.route, localOrigin);
  for (const rawHref of document.links) {
    let targetUrl;
    try {
      targetUrl = new URL(rawHref, sourceUrl);
    } catch {
      failures.push(`${document.route} 包含无法解析的链接 ${rawHref}`);
      continue;
    }
    if (targetUrl.origin !== localOrigin || !['http:', 'https:'].includes(targetUrl.protocol)) continue;
    linkCount += 1;

    const targetKey = `${targetUrl.pathname}${targetUrl.search}`;
    let targetFile = checkedTargets.get(targetKey);
    if (targetFile === undefined) {
      targetFile = firstExistingFile(targetCandidates(targetUrl.pathname));
      checkedTargets.set(targetKey, targetFile || null);
    }
    if (!targetFile) {
      failures.push(`${document.route} 指向不存在的站内地址 ${targetKey}`);
      continue;
    }

    if (targetUrl.hash && targetUrl.hash !== '#') {
      const fragmentKey = `${targetKey}${targetUrl.hash}`;
      if (checkedFragments.has(fragmentKey)) continue;
      checkedFragments.add(fragmentKey);
      const targetDocument = targetFile.endsWith('.html') ? await loadDocument(targetFile) : null;
      const fragment = safeDecode(targetUrl.hash.slice(1));
      if (!targetDocument) {
        failures.push(`${document.route} 在非 HTML 地址上使用锚点 ${fragmentKey}`);
      } else if (!targetDocument.anchors.has(fragment)) {
        failures.push(`${document.route} 指向不存在的页内锚点 ${fragmentKey}`);
      }
    }
  }
}

const elapsedSeconds = ((performance.now() - startedAt) / 1000).toFixed(2);
const scopeLabel = scopes.length ? `范围 ${scopes.join('、')}` : '全站';
console.log(`${scopeLabel}：检查 ${sourceDocuments.length} 个 HTML 页面、${linkCount} 条链接、${checkedTargets.size} 个唯一地址和 ${checkedFragments.size} 个唯一锚点，用时 ${elapsedSeconds} 秒。`);
if (failures.length) {
  console.error('\n链接检查失败：');
  [...new Set(failures)].forEach((failure) => console.error(`- ${failure}`));
  process.exit(1);
}
console.log('静态站内链接检查通过。');
