import { chromium } from 'playwright-core';
import { mkdir } from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';

const baseUrl = process.env.WIKI_URL || 'http://127.0.0.1:4321';
const executablePath = process.env.EDGE_PATH || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const outputDir = path.resolve(import.meta.dirname, '..', '..', 'logs', 'qa');
await mkdir(outputDir, { recursive: true });
const browser = await chromium.launch({ executablePath, headless: true });
const failures = [];

async function graphHasRenderedPixels(page, selector) {
  return page.locator(selector).evaluateAll((canvases) => canvases.some((canvas) => {
    const pixels = canvas.getContext('2d')?.getImageData(0, 0, canvas.width, canvas.height).data;
    if (!pixels) return false;
    let opaque = 0;
    for (let index = 3; index < pixels.length; index += 4) {
      if (pixels[index] && ++opaque > 500) return true;
    }
    return false;
  }));
}

async function inspect(name, viewport, pathname, actions) {
  const context = await browser.newContext({ viewport, colorScheme: 'light' });
  const page = await context.newPage();
  const errors = [];
  page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
  page.on('pageerror', (error) => errors.push(error.stack || error.message));
  const response = await page.goto(`${baseUrl}${pathname}`, { waitUntil: 'networkidle' });
  if (!response?.ok()) failures.push(`${name}: HTTP ${response?.status()}`);
  await actions(page);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  if (overflow > 1) failures.push(`${name}: horizontal overflow ${overflow}px`);
  if (errors.length) failures.push(`${name}: ${errors.join(' | ')}`);
  const screenshot = path.join(outputDir, `${name}.png`);
  await page.screenshot({ path: screenshot, fullPage: true });
  console.log(`${name}: ${screenshot}`);
  await context.close();
}

await inspect('characters-index-desktop', { width: 1440, height: 1000 }, '/characters/', async (page) => {
  if ((await page.locator('.filter-item:not([hidden])').count()) !== 202) failures.push('characters-index-desktop: expected 202 characters');
  await page.locator('#character-query').fill('李尘舟');
  const filteredNames = await page.locator('.filter-item:not([hidden]) h2').allTextContents();
  if (!filteredNames.includes('李尘舟')) failures.push('characters-index-desktop: search did not find 李尘舟');
  await page.locator('#character-query').fill('');
  await page.locator('.role-tabs button[data-role="主要人物"]').click();
  if ((await page.locator('.filter-item:not([hidden])').count()) !== 46) failures.push('characters-index-desktop: major-character count is incorrect');
  const firstImages = page.locator('.filter-item:not([hidden]) img').first();
  await firstImages.waitFor();
  if (!(await firstImages.evaluate((image) => image.complete && image.naturalWidth > 0))) failures.push('characters-index-desktop: portrait failed to load');
  await page.locator('.search-trigger').first().click();
  await page.locator('.search-dialog input').fill('李尘舟');
  await page.locator('.quick-results a[href="/characters/npc-53351400/"]').waitFor({ timeout: 5000 });
  await page.locator('.search-close').click();
  const directory = await page.request.get(`${baseUrl}/entries/`);
  if (!(await directory.text()).includes('/characters/')) failures.push('characters-index-desktop: encyclopedia directory has no character entry');
});

await inspect('characters-graph-desktop', { width: 1440, height: 1000 }, '/characters/#relations', async (page) => {
  await page.locator('.relations-panel:not([hidden]) .graph-canvas canvas').last().waitFor({ timeout: 10000 });
  await page.waitForFunction(() => document.querySelector('.relations-panel [data-relationship-graph]')?.dataset.graphState === 'ready');
  if (!(await graphHasRenderedPixels(page, '.relations-panel .graph-canvas canvas'))) failures.push('characters-graph-desktop: graph canvas is blank');
  const graphSize = await page.locator('.relations-panel .graph-canvas').boundingBox();
  if (!graphSize || graphSize.width < 700 || graphSize.height < 500) failures.push('characters-graph-desktop: graph canvas is too small');
  await page.locator('.relations-panel .graph-search input').fill('李尘舟');
  await page.waitForTimeout(300);
  if (!(await page.locator('.relations-panel .node-inspector').textContent())?.includes('李尘舟')) failures.push('characters-graph-desktop: graph search did not focus 李尘舟');
  await page.locator('.relations-panel [data-relation-filter]').selectOption('enmity');
});

await inspect('character-detail-desktop', { width: 1440, height: 1000 }, '/characters/npc-53351400/', async (page) => {
  const text = await page.locator('.character-page').textContent();
  if (!text?.includes('李尘舟') || !text.includes('玩家操控的主角') || !text.includes('苍影阁') || !text.includes('人物关系')) failures.push('character-detail-desktop: core profile content is incomplete');
  if (text.includes('可在灵素谷等地遇见')) failures.push('character-detail-desktop: protagonist still uses the generic location description');
  if (text?.includes('1001307') || text?.includes('资料来源') || text?.includes('配置编号')) failures.push('character-detail-desktop: maintenance evidence leaked into reader content');
  if ((await page.locator('.relation-list > a').count()) !== 7) failures.push('character-detail-desktop: expected 7 verified relationships');
  if ((await page.locator('.detail-toc a').count()) < 4) failures.push('character-detail-desktop: detail toc is incomplete');
  await page.locator('#relationship-map').scrollIntoViewIfNeeded();
  await page.locator('#relationship-map canvas').last().waitFor({ timeout: 10000 });
  await page.waitForFunction(() => document.querySelector('#relationship-map [data-relationship-graph]')?.dataset.graphState === 'ready');
  if (!(await graphHasRenderedPixels(page, '#relationship-map canvas'))) failures.push('character-detail-desktop: relationship graph canvas is blank');
  const bookmark = page.locator('.bookmark-button');
  await bookmark.click();
  if (!(await bookmark.evaluate((button) => button.classList.contains('active')))) failures.push('character-detail-desktop: bookmark did not activate');
  await page.reload({ waitUntil: 'networkidle' });
  if (!(await page.locator('.bookmark-button').evaluate((button) => button.classList.contains('active')))) failures.push('character-detail-desktop: bookmark did not persist after reload');
});

await inspect('character-search-mobile', { width: 390, height: 844 }, '/search/?q=李尘舟', async (page) => {
  await page.locator('.search-results a[href="/characters/npc-53351400/"]').waitFor({ timeout: 5000 });
});

await inspect('characters-mobile', { width: 390, height: 844 }, '/characters/#relations', async (page) => {
  await page.locator('.relations-panel:not([hidden]) canvas').last().waitFor({ timeout: 10000 });
  const stage = await page.locator('.relations-panel .graph-stage').boundingBox();
  if (!stage || stage.width > 358 || stage.height < 480) failures.push('characters-mobile: graph stage does not fit mobile viewport');
});

await inspect('character-detail-narrow', { width: 320, height: 720 }, '/characters/npc-51917800/', async (page) => {
  if (!(await page.locator('.detail-toc-mobile').isVisible())) failures.push('character-detail-narrow: mobile toc is hidden');
  if (!(await page.locator('.hero-portrait img').evaluate((image) => image.complete && image.naturalWidth > 0))) failures.push('character-detail-narrow: hero portrait failed to load');
});

await browser.close();
if (failures.length) {
  console.error('\nCharacter QA failed:');
  failures.forEach((failure) => console.error(`- ${failure}`));
  process.exit(1);
}
console.log('\nCharacter QA passed.');
