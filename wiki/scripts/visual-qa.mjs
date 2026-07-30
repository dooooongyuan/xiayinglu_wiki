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

async function loadLazyImages(page) {
  const height = await page.evaluate(() => document.documentElement.scrollHeight);
  for (let y = 0; y < height; y += 600) {
    await page.evaluate((top) => window.scrollTo(0, top), y);
    await page.waitForTimeout(30);
  }
  await page.waitForFunction(() => [...document.querySelectorAll('.filter-item:not([hidden]) img')].every((img) => img.complete && img.naturalWidth > 0), null, { timeout: 10000 });
  await page.evaluate(() => window.scrollTo(0, 0));
}

async function inspect(name, viewport, pathname, actions) {
  const context = await browser.newContext({ viewport, colorScheme: 'light' });
  const page = await context.newPage();
  const consoleErrors = [];
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text());
  });
  page.on('pageerror', (error) => consoleErrors.push(error.message));

  const response = await page.goto(`${baseUrl}${pathname}`, { waitUntil: 'networkidle' });
  if (!response?.ok()) failures.push(`${name}: HTTP ${response?.status()}`);
  if (actions) await actions(page);

  const metrics = await page.evaluate(() => ({
    viewportWidth: document.documentElement.clientWidth,
    documentWidth: document.documentElement.scrollWidth,
    title: document.title,
    h1: document.querySelector('h1')?.textContent?.trim() || '',
  }));
  if (metrics.documentWidth > metrics.viewportWidth + 1) {
    failures.push(`${name}: horizontal overflow ${metrics.documentWidth}px > ${metrics.viewportWidth}px`);
  }
  if (!metrics.h1) failures.push(`${name}: missing h1`);
  if (consoleErrors.length) failures.push(`${name}: console errors: ${consoleErrors.join(' | ')}`);
  if ((pathname.startsWith('/wiki/') || pathname.startsWith('/characters/')) && await page.getByText('修订条目', { exact: true }).count()) {
    failures.push(`${name}: public edit entry is still visible`);
  }

  const screenshot = path.join(outputDir, `${name}.png`);
  await page.screenshot({ path: screenshot, fullPage: true });
  console.log(JSON.stringify({ name, pathname, screenshot, ...metrics }));
  await context.close();
}

await inspect('home-desktop', { width: 1440, height: 1000 }, '/', async (page) => {
  const featuredCards = await page.locator('.entry-grid').textContent();
  const materialHref = await page.locator('.entry-grid a', { hasText: '材料' }).getAttribute('href');
  if (!featuredCards?.includes('材料') || featuredCards.includes('本地化表中的人物') || materialHref !== '/wiki/cailiao/') {
    failures.push(`home-desktop: featured material card is missing or incorrect (${materialHref})`);
  }
  await page.locator('.search-trigger').first().click();
  const dialog = page.locator('.search-dialog');
  await dialog.locator('input').fill('武学');
  await dialog.locator('.quick-results a').first().waitFor();
  const resultText = await dialog.locator('.quick-results').textContent();
  if (!resultText?.includes('武学')) failures.push('home-desktop: quick search did not find 武学');
  await dialog.locator('input').fill('玄剑式');
  await dialog.locator('.quick-results a').first().waitFor();
  const generatedResultText = await dialog.locator('.quick-results').textContent();
  if (!generatedResultText?.includes('玄剑式')) failures.push('home-desktop: quick search did not find 玄剑式');
  await dialog.locator('input').fill('空明诀');
  await dialog.locator('.quick-results a').first().waitFor();
  const heartResultText = await dialog.locator('.quick-results').textContent();
  if (!heartResultText?.includes('空明诀') || !heartResultText.includes('心法') || !heartResultText.includes('稀有')) failures.push('home-desktop: quick search did not find categorized heart method 空明诀 with its quality label');
  await dialog.locator('input').fill('凌云心决');
  await dialog.locator('.quick-results a').first().waitFor();
  const expandedHeartResultText = await dialog.locator('.quick-results').textContent();
  const expandedHeartResultHref = await dialog.locator('.quick-results a').first().getAttribute('href');
  if (!expandedHeartResultText?.includes('凌云心诀') || expandedHeartResultHref !== '/wiki/wuxue/60001/') failures.push('home-desktop: legacy name 凌云心决 did not resolve to canonical manual name 凌云心诀');
  await dialog.locator('input').fill('乾坤诀');
  await dialog.locator('.quick-results a').first().waitFor();
  const manualAliasHref = await dialog.locator('.quick-results a').first().getAttribute('href');
  if (manualAliasHref !== '/wiki/wuxue/70061/') failures.push(`home-desktop: manual alias 乾坤诀 resolved to ${manualAliasHref}`);
  await dialog.locator('input').fill('玄青道');
  await dialog.locator('.quick-results a').first().waitFor();
  const xuanqingAliasText = await dialog.locator('.quick-results').textContent();
  const xuanqingAliasHref = await dialog.locator('.quick-results a').first().getAttribute('href');
  if (!xuanqingAliasText?.includes('玄清道') || xuanqingAliasHref !== '/wiki/wuxue/70081/') failures.push(`home-desktop: effect alias 玄青道 resolved to ${xuanqingAliasHref}`);
  await dialog.locator('input').fill('暖阳丹');
  await dialog.locator('.quick-results a').first().waitFor();
  const danyaoResultText = await dialog.locator('.quick-results').textContent();
  const danyaoResultHref = await dialog.locator('.quick-results a').first().getAttribute('href');
  if (!danyaoResultText?.includes('暖阳丹') || !danyaoResultText.includes('丹药') || danyaoResultHref !== '/wiki/danyao/10116/') {
    failures.push(`home-desktop: quick search did not resolve 暖阳丹 (${danyaoResultHref})`);
  }
  await dialog.locator('input').fill('精铁');
  await dialog.locator('.quick-results a').first().waitFor();
  const materialResultText = await dialog.locator('.quick-results').textContent();
  const materialResultHref = await dialog.locator('.quick-results a').first().getAttribute('href');
  if (!materialResultText?.includes('精铁') || !materialResultText.includes('材料') || materialResultHref !== '/wiki/cailiao/1201/') {
    failures.push(`home-desktop: quick search did not resolve material 精铁 (${materialResultHref})`);
  }
  await dialog.locator('input').fill('电击匣');
  await dialog.locator('.quick-results a').first().waitFor();
  const trapResultText = await dialog.locator('.quick-results').textContent();
  const trapResultHref = await dialog.locator('.quick-results a').first().getAttribute('href');
  if (!trapResultText?.includes('电击匣') || !trapResultText.includes('陷阱') || trapResultHref !== '/wiki/xianjing/30510/') {
    failures.push(`home-desktop: quick search did not resolve trap 电击匣 (${trapResultHref})`);
  }
  await dialog.locator('input').fill('生命铸纹');
  await dialog.locator('.quick-results a').first().waitFor();
  const zhuwenResultText = await dialog.locator('.quick-results').textContent();
  const zhuwenResultHref = await dialog.locator('.quick-results a').first().getAttribute('href');
  if (!zhuwenResultText?.includes('生命铸纹') || !zhuwenResultText.includes('铸纹') || zhuwenResultHref !== '/wiki/zhuwen/fixed-1-2/') {
    failures.push(`home-desktop: quick search did not resolve inscription 生命铸纹 (${zhuwenResultHref})`);
  }
  await dialog.locator('.search-close').click();
});

await inspect('home-wide', { width: 1920, height: 955 }, '/', async (page) => {
  const cards = page.locator('.entry-grid .entry-card');
  if ((await cards.count()) !== 4) failures.push('home-wide: expected 4 featured cards');
  const lastCard = await cards.last().boundingBox();
  if (!lastCard || lastCard.y + lastCard.height > 955) {
    failures.push('home-wide: featured cards do not fit in the first viewport');
  }
});

await inspect('wuxue-index-desktop', { width: 1440, height: 1000 }, '/wiki/wuxue/', async (page) => {
  const defaultCards = await page.locator('.filter-item:not([hidden])').count();
  if (defaultCards !== 72) failures.push(`wuxue-index-desktop: expected 72 player gongfa cards, found ${defaultCards}`);
  const qualityColors = new Map([
    ['2', 'rgb(47, 138, 76)'],
    ['3', 'rgb(45, 111, 183)'],
    ['4', 'rgb(123, 74, 176)'],
    ['5', 'rgb(169, 120, 24)'],
  ]);
  const qualityNames = new Map([
    ['2', '精良'],
    ['3', '稀有'],
    ['4', '珍奇'],
    ['5', '绝世'],
  ]);
  const qualityOptions = await page.locator('#wuxue-quality option').allTextContents();
  if (!['全部品质', '精良', '稀有', '珍奇', '绝世'].every((label) => qualityOptions.includes(label)) || qualityOptions.some((label) => /^品质 [2-5]$/.test(label))) {
    failures.push(`wuxue-index-desktop: quality options are incorrect (${qualityOptions.join(', ')})`);
  }
  const gongfaQualityChecks = [
    ['玄剑式', '2'],
    ['藏剑式', '3'],
    ['流云七笈剑', '4'],
    ['苍云太玄剑', '5'],
  ];
  for (const [name, quality] of gongfaQualityChecks) {
    await page.locator('#wuxue-query').fill(name);
    const card = page.locator('.filter-item:not([hidden]) .wuxue-card').first();
    if ((await card.getAttribute('data-quality')) !== quality) failures.push(`wuxue-index-desktop: ${name} is not quality ${quality}`);
    if ((await card.locator('.quality-badge').textContent())?.trim() !== qualityNames.get(quality)) failures.push(`wuxue-index-desktop: ${name} does not show ${qualityNames.get(quality)}`);
    const badgeColor = await card.locator('.quality-badge').evaluate((element) => getComputedStyle(element).color);
    if (badgeColor !== qualityColors.get(quality)) failures.push(`wuxue-index-desktop: quality ${quality} rendered as ${badgeColor}`);
  }
  await page.locator('#wuxue-query').fill('求败');
  const visibleCards = await page.locator('.filter-item:not([hidden])').count();
  if (visibleCards !== 1) failures.push(`wuxue-index-desktop: expected 1 filtered card, found ${visibleCards}`);
  const resultText = await page.locator('.filter-item:not([hidden])').textContent();
  if (!resultText?.includes('求败')) failures.push('wuxue-index-desktop: query did not find 求败');
  await page.locator('#wuxue-query').fill('');
  await page.locator('.style-control button[data-style="刀势"]').click();
  const knifeCards = await page.locator('.filter-item:not([hidden])').count();
  if (knifeCards !== 16) failures.push(`wuxue-index-desktop: expected 16 knife cards, found ${knifeCards}`);
  await page.locator('.style-control button[data-style=""]').click();
  await page.locator('#wuxue-query').fill('熊霸天下');
  const excludedGraphCards = await page.locator('.filter-item:not([hidden])').count();
  if (excludedGraphCards !== 0) failures.push(`wuxue-index-desktop: excluded graph-only gongfa 熊霸天下 is visible`);
  await page.locator('#wuxue-query').fill('');
  await page.locator('.affinity-control button[data-affinity="阴"]').click();
  const yinGongfaCards = page.locator('.filter-item:not([hidden])');
  if ((await yinGongfaCards.count()) !== 16) failures.push(`wuxue-index-desktop: expected 16 yin gongfa cards, found ${await yinGongfaCards.count()}`);
  if ((await yinGongfaCards.evaluateAll((items) => items.some((item) => item.getAttribute('data-affinity') !== '阴')))) failures.push('wuxue-index-desktop: yin filter includes another affinity');
  await page.locator('.affinity-control button[data-affinity=""]').click();
  await page.locator('.catalog-tabs button[data-category="心法"]').click();
  const heartCards = await page.locator('.filter-item:not([hidden])').count();
  if (heartCards !== 47) failures.push(`wuxue-index-desktop: expected 47 heart-method cards, found ${heartCards}`);
  if (!(await page.locator('.style-control').isHidden())) failures.push('wuxue-index-desktop: gongfa styles remain visible for heart methods');
  const heartQualityChecks = [
    ['烈火诀', '2'],
    ['迅雷心诀', '3'],
    ['神霄天霆', '4'],
    ['九阳焚厄经', '5'],
  ];
  for (const [name, quality] of heartQualityChecks) {
    await page.locator('#wuxue-query').fill(name);
    const card = page.locator('.filter-item:not([hidden]) .wuxue-card').first();
    if ((await card.getAttribute('data-quality')) !== quality) failures.push(`wuxue-index-desktop: ${name} is not quality ${quality}`);
    if ((await card.locator('.quality-badge').textContent())?.trim() !== qualityNames.get(quality)) failures.push(`wuxue-index-desktop: ${name} does not show ${qualityNames.get(quality)}`);
    const badgeColor = await card.locator('.quality-badge').evaluate((element) => getComputedStyle(element).color);
    if (badgeColor !== qualityColors.get(quality)) failures.push(`wuxue-index-desktop: heart-method quality ${quality} rendered as ${badgeColor}`);
  }
  await page.locator('#wuxue-query').fill('');
  await page.locator('.affinity-control button[data-affinity="刚"]').click();
  const hardHeartCards = page.locator('.filter-item:not([hidden])');
  if ((await hardHeartCards.count()) !== 10) failures.push(`wuxue-index-desktop: expected 10 hard heart methods, found ${await hardHeartCards.count()}`);
  if ((await hardHeartCards.evaluateAll((items) => items.some((item) => item.getAttribute('data-affinity') !== '刚')))) failures.push('wuxue-index-desktop: hard heart-method filter includes another affinity');
  await page.locator('.affinity-control button[data-affinity=""]').click();
  await page.locator('#wuxue-query').fill('玄青道');
  const xuanqingCards = page.locator('.filter-item:not([hidden])');
  if ((await xuanqingCards.count()) !== 1 || !(await xuanqingCards.textContent())?.includes('玄清道')) failures.push('wuxue-index-desktop: alias 玄青道 did not find canonical 玄清道');
  await page.locator('#wuxue-query').fill('');
  const heartLinks = await page.locator('.filter-item:not([hidden]) a').evaluateAll((links) => [...new Set(links.map((link) => link.getAttribute('href')).filter(Boolean))]);
  let unavailableHeartMethods = 0;
  for (const href of heartLinks) {
    const response = await page.request.get(`${baseUrl}${href}`);
    const html = await response.text();
    if (['获取方式待核实', '未关联秘籍物品', '可能为初始武学或剧情直接解锁'].some((term) => html.includes(term))) {
      failures.push(`wuxue-index-desktop: unresolved acquisition copy remains at ${href}`);
    }
    if (html.includes('当前版本暂无正常获取途径')) unavailableHeartMethods += 1;
  }
  if (unavailableHeartMethods !== 2) failures.push(`wuxue-index-desktop: expected 2 unavailable heart methods, found ${unavailableHeartMethods}`);
  await loadLazyImages(page);
});

await inspect('article-desktop', { width: 1440, height: 1000 }, '/wiki/wuxue/10021/', async (page) => {
  await page.locator('.bookmark-button').click();
  if (!(await page.locator('.bookmark-button').evaluate((element) => element.classList.contains('active')))) {
    failures.push('article-desktop: bookmark did not activate');
  }
  const articleText = await page.locator('.wuxue-page').textContent();
  if (!articleText?.includes('修习节点') || !articleText.includes('功法来源')) failures.push('article-desktop: player-facing gongfa sections are missing');
  if (articleText?.includes('伤害倾向') || await page.locator('.power-list').count()) failures.push('article-desktop: removed gongfa damage tendency is still visible');
  if ((await page.locator('.training-node').count()) !== 6) failures.push('article-desktop: expected 6 gongfa training nodes');
  const tocLabels = await page.locator('.detail-toc a').allTextContents();
  if (!['功法说明', '修习节点', '功法来源'].every((label) => tocLabels.includes(label))) failures.push('article-desktop: gongfa detail toc is incomplete');
  if (!articleText?.includes('苍影阁 · 沈砚秋') || !articleText.includes('2,000 铜钱')) failures.push('article-desktop: verified acquisition source is missing');
  for (const removedHeading of ['威力配置', '配置快照', '资料快照', '资料版本', '关联记录', '资料来源']) {
    if (articleText?.includes(removedHeading)) failures.push(`article-desktop: removed section ${removedHeading} is still visible`);
  }
  const sourceChecks = [
    ['/wiki/wuxue/10001/', ['初始自带', '创建角色后即可使用']],
    ['/wiki/wuxue/10051/', ['副本', '连云匪患', '赫连勃']],
    ['/wiki/wuxue/10111/', ['副本', '武林汇聚', '场景宝箱']],
    ['/wiki/wuxue/10141/', ['角色等级达到 35', '范星野', '神机山庄后山', '巨剑奇遇', '后山拜佛补购']],
    ['/wiki/wuxue/10191/', ['千字文', '谢军', '切磋', '150,000 铜钱补购']],
    ['/wiki/wuxue/20041/', ['角色等级达到 20', '天鉴府经楼', '经楼管事', '极乐草']],
    ['/wiki/wuxue/20051/', ['朴藏机切磋', '切磋获胜后获得']],
    ['/wiki/wuxue/20151/', ['瓮中捉鳖', 'BOSS 朴藏机', '黑煞魔刀']],
    ['/wiki/wuxue/30111/', ['银龙锁岳', '毒谷鳞纹残笺', '沈砚秋']],
    ['/wiki/wuxue/30101/', ['悬赏副本', '瀚海遗迹', '鬼枪']],
    ['/wiki/wuxue/30091/', ['角色等级 15', '累计优胜 3 次']],
    ['/wiki/wuxue/30051/', ['角色等级 20', '累计优胜 5 次']],
    ['/wiki/wuxue/40181/', ['角色等级 25', '累计优胜 7 次']],
    ['/wiki/wuxue/40021/', ['角色等级 30', '累计优胜 10 次', '玲珑宝匣']],
    ['/wiki/wuxue/40121/', ['菩提禅院', '藏经阁任务', '净尘', '了心']],
    ['/wiki/wuxue/40071/', ['绝龙岭', '虎类精英', '猛虎式']],
    ['/wiki/wuxue/40101/', ['丐帮', '特殊任务', '400,000 铜钱补购']],
    ['/wiki/wuxue/60071/', ['连环坞中坞', '黑蟒毒牙令', '影娘', '噬星咒']],
    ['/wiki/wuxue/60171/', ['连环坞外滩', '通关至少 1 次', '影娘', '蚀元诀']],
    ['/wiki/wuxue/60191/', ['神机山庄后院', '求败', '全部 6 个节点', '意', '120', '独孤心诀']],
    ['/wiki/wuxue/60221/', ['正魔决战', '天鉴府经楼', '曹管事', '九阳焚厄经']],
    ['/wiki/wuxue/60251/', ['灭门真相', '雷啸川', '沈砚秋', '苍云太玄经']],
    ['/wiki/wuxue/60271/', ['天鉴大战', '萧清雪', '段机玄', '寒晶铁', '剑骨', '门派铁匠', '竹海迷宫', '石壁']],
    ['/wiki/wuxue/70011/', ['血炎追踪', '第 11 个房间', '无相诀交互点', '竹海迷踪']],
    ['/wiki/wuxue/70071/', ['镇狱毒司', '连云山腹地', '第 11 个房间', '呼延葬']],
    ['/wiki/wuxue/70081/', ['玄清道', '每2秒生成 1 把冰剑', '最多 10 把', '阴属性3倍伤害', '附加1级寒气', '移花宫', '妖月', '有概率获得']],
    ['/wiki/wuxue/70091/', ['连环坞内坞', '血沁骨珠串', '影娘', '幽冥界']],
    ['/wiki/wuxue/80061/', ['花海寻药', '破妄矿', '顾野樵', '天师雷法']],
    ['/wiki/wuxue/80091/', ['逍遥遗址', '五毒宫', '何溪凤', '移花宫', '妖月', '星宿腐海', '丁纯丘', '极乐宫', '薛三娘', '毒纹灵钥', '凝芳玉钥', '玄星铁钥', '烬金秘钥', '逍遥宫密藏']],
    ['/wiki/wuxue/80131/', ['缥缈峰雪宫', '颜色不同的石壁', '佛像', '叩拜']],
    ['/wiki/wuxue/60101/', ['当前不可获取', '当前版本暂无正常获取途径', '未配置商店、掉落、宝箱、任务或场景奖励']],
    ['/wiki/wuxue/80141/', ['当前不可获取', '当前版本暂无正常获取途径', '没有对应秘籍物品']],
  ];
  for (const [pathname, terms] of sourceChecks) {
    const response = await page.request.get(`${baseUrl}${pathname}`);
    const html = await response.text();
    if (!terms.every((term) => html.includes(term))) failures.push(`article-desktop: incomplete acquisition source at ${pathname}`);
  }
});

await inspect('xinfa-graph-desktop', { width: 1440, height: 1000 }, '/wiki/wuxue/60001/', async (page) => {
  const graphNodes = page.locator('.training-node');
  const graphEdges = page.locator('.graph-edge');
  if ((await graphNodes.count()) !== 6) failures.push('xinfa-graph-desktop: expected 6 graph nodes');
  if ((await graphEdges.count()) !== 5) failures.push('xinfa-graph-desktop: expected 5 graph edges');
  if ((await page.locator('.training-node.is-root').count()) !== 1) failures.push('xinfa-graph-desktop: expected 1 root node');
  if ((await page.locator('.training-node.is-major').count()) !== 1) failures.push('xinfa-graph-desktop: expected 1 major node');
  if ((await page.locator('.training-node.is-minor').count()) !== 4) failures.push('xinfa-graph-desktop: expected 4 minor nodes');

  await page.locator('[data-node-id="6000105"]').click();
  const selectedDetail = page.locator('[data-node-detail="6000105"]');
  if (!(await selectedDetail.isVisible())) failures.push('xinfa-graph-desktop: selected node detail is hidden');
  const detailText = await selectedDetail.textContent();
  if (!detailText?.includes('增伤+14') || !detailText.includes('归元')) failures.push('xinfa-graph-desktop: selected node effect or prerequisite is missing');
  if ((await page.locator('.graph-edge.is-path').count()) !== 4) failures.push('xinfa-graph-desktop: prerequisite path was not highlighted');
});

await inspect('xinfa-two-major-desktop', { width: 1440, height: 1000 }, '/wiki/wuxue/60151/', async (page) => {
  if ((await page.locator('.training-node.is-major').count()) !== 2) failures.push('xinfa-two-major-desktop: expected 2 major nodes');
});

await inspect('xuanqing-detail-desktop', { width: 1440, height: 1000 }, '/wiki/wuxue/70081/', async (page) => {
  const text = await page.locator('.wuxue-page').textContent();
  for (const term of ['玄清道', '珍奇', '每2秒生成 1 把冰剑', '最多 10 把', '阴属性3倍伤害', '附加1级寒气', '移花宫', '妖月', '有概率获得']) {
    if (!text?.includes(term)) failures.push(`xuanqing-detail-desktop: missing ${term}`);
  }
  if (text?.includes('品质 4')) failures.push('xuanqing-detail-desktop: numeric quality label remains visible');
  if ((await page.locator('.training-node').count()) !== 6) failures.push('xuanqing-detail-desktop: expected 6 graph nodes');
});

await inspect('equipment-index-desktop', { width: 1440, height: 1000 }, '/wiki/zhuangbei/', async (page) => {
  const defaultCards = await page.locator('.filter-item:not([hidden])').count();
  if (defaultCards !== 58) failures.push(`equipment-index-desktop: expected 58 weapon cards, found ${defaultCards}`);
  const expectedCounts = new Map([['武器', 58], ['暗器', 26], ['防具', 30], ['饰品', 17], ['宝物', 44]]);
  for (const [category, count] of expectedCounts) {
    await page.locator(`.catalog-tabs button[data-category="${category}"]`).click();
    const visible = await page.locator('.filter-item:not([hidden])').count();
    if (visible !== count) failures.push(`equipment-index-desktop: expected ${count} ${category} cards, found ${visible}`);
  }
  await page.locator('.catalog-tabs button[data-category="武器"]').click();
  await page.locator('#equipment-tier').selectOption('7');
  if ((await page.locator('.filter-item:not([hidden])').count()) !== 8) failures.push('equipment-index-desktop: expected 8 seventh-tier weapons');
  await page.locator('#equipment-tier').selectOption('');
  await page.locator('.subtype-control:not([hidden]) button[data-subtype="剑"]').click();
  if ((await page.locator('.filter-item:not([hidden])').count()) !== 16) failures.push('equipment-index-desktop: expected 16 swords');
  await page.locator('.subtype-control:not([hidden]) button[data-subtype=""]').click();
  await page.locator('#equipment-query').fill('卓堇');
  const qualityCard = page.locator('.filter-item:not([hidden]) .equipment-card').first();
  if ((await qualityCard.getAttribute('data-quality')) !== '5') failures.push('equipment-index-desktop: 卓堇 is not quality 5');
  const qualityColor = await qualityCard.locator('.quality-badge').evaluate((element) => getComputedStyle(element).color);
  if (qualityColor !== 'rgb(169, 120, 24)') failures.push(`equipment-index-desktop: quality 5 rendered as ${qualityColor}`);
  await page.locator('#equipment-query').fill('');
  await loadLazyImages(page);
});

await inspect('equipment-random-detail-desktop', { width: 1440, height: 1000 }, '/wiki/zhuangbei/30002/', async (page) => {
  const articleText = await page.locator('.equipment-page').textContent();
  if (!articleText?.includes('攻击22') || !articleText.includes('暴击8')) failures.push('equipment-random-detail-desktop: fixed attributes are missing');
  for (const sourceTerm of ['天工打造', '精铁 × 1', '刘铁匠', '205 补给', '场景宝箱', '敌人掉落']) {
    if (!articleText?.includes(sourceTerm)) failures.push(`equipment-random-detail-desktop: acquisition source ${sourceTerm} is missing`);
  }
  if (!articleText?.includes('镶嵌孔位') || !articleText.includes('普通') || !articleText.includes('精良及以上')) failures.push('equipment-random-detail-desktop: quality-specific socket rules are missing');
  const socketRows = page.locator('.socket-probability .socket-row');
  if ((await socketRows.count()) !== 3) failures.push('equipment-random-detail-desktop: expected socket header and two quality rules');
  const socketText = await page.locator('.socket-probability').textContent();
  if (!socketText?.includes('0 孔') || !socketText.includes('1 孔') || !socketText.includes('2 孔') || !socketText.includes('33.33%')) failures.push('equipment-random-detail-desktop: 0-2 socket probabilities are incomplete');
  if ((await page.locator('[data-affix-row]').count()) !== 27) failures.push('equipment-random-detail-desktop: expected 27 complete affix candidates');
  if ((await page.locator('.affix-select:not([disabled])').count()) !== 4) failures.push('equipment-random-detail-desktop: expected four active weapon affix slots');
  const selects = page.locator('.affix-select');
  await selects.nth(0).selectOption('100100');
  await selects.nth(1).selectOption('100101');
  await selects.nth(2).selectOption('100102');
  await selects.nth(3).selectOption('100103');
  const previewText = await page.locator('.combination-preview').textContent();
  if (!previewText?.includes('攻击') || !previewText.includes('暴击')) failures.push('equipment-random-detail-desktop: four-slot combination preview did not update');
  await page.locator('.candidate-filters button[data-affix-quality="5"]').click();
  if ((await page.locator('[data-affix-row]:not([hidden])').count()) !== 5) failures.push('equipment-random-detail-desktop: expected 5 quality-5 candidates');
  const anqiHtml = await (await page.request.get(`${baseUrl}/wiki/zhuangbei/30413/`)).text();
  if (!['新游戏初始携带', '天工打造', '玄影锥', '消耗 50 点'].every((term) => anqiHtml.includes(term))) failures.push('equipment-random-detail-desktop: dark-weapon forge requirement is incomplete');
});

await inspect('equipment-section-order-desktop', { width: 1440, height: 1000 }, '/wiki/zhuangbei/30002/', async (page) => {
  const cases = [
    ['/wiki/zhuangbei/30002/', ['overview', 'fixed-attributes', 'extra-attributes', 'sockets', 'acquisition']],
    ['/wiki/zhuangbei/30413/', ['overview', 'fixed-attributes', 'damage', 'acquisition']],
    ['/wiki/zhuangbei/32002/', ['overview', 'fixed-attributes', 'extra-attributes', 'sockets', 'acquisition']],
    ['/wiki/zhuangbei/34016/', ['overview', 'fixed-attributes', 'extra-attributes', 'sockets', 'acquisition']],
    ['/wiki/zhuangbei/36101/', ['overview', 'fixed-attributes', 'intrinsic-effects', 'acquisition']],
  ];
  for (const [pathname, expected] of cases) {
    await page.goto(`${baseUrl}${pathname}`, { waitUntil: 'networkidle' });
    const sectionIds = await page.locator('.detail-main > section').evaluateAll((sections) => sections.map((section) => section.id));
    const tocIds = await page.locator('.detail-toc a').evaluateAll((links) => links.map((link) => link.getAttribute('href')?.slice(1)));
    if (sectionIds.join(',') !== expected.join(',') || tocIds.join(',') !== expected.join(',')) {
      failures.push(`equipment-section-order-desktop: ${pathname} rendered ${sectionIds.join(',')} / ${tocIds.join(',')}`);
    }
  }
});

await inspect('equipment-one-socket-detail-desktop', { width: 1440, height: 1000 }, '/wiki/zhuangbei/30010/', async (page) => {
  const socketText = await page.locator('.socket-section').textContent();
  if (!socketText?.includes('固定 1 孔') || !socketText.includes('100%')) failures.push('equipment-one-socket-detail-desktop: fixed one-socket rule is missing');
  const acquisitionText = await page.locator('.acquisition').textContent();
  if (!acquisitionText?.includes('竹海迷宫神兵宝箱')) failures.push('equipment-one-socket-detail-desktop: verified chest source is missing');
});

await inspect('equipment-two-socket-detail-desktop', { width: 1440, height: 1000 }, '/wiki/zhuangbei/30209/', async (page) => {
  const socketText = await page.locator('.socket-section').textContent();
  if (!socketText?.includes('固定 2 孔') || !socketText.includes('100%')) failures.push('equipment-two-socket-detail-desktop: fixed two-socket rule is missing');
});

await inspect('equipment-fixed-detail-desktop', { width: 1440, height: 1000 }, '/wiki/zhuangbei/30009/', async (page) => {
  if ((await page.locator('.fixed-affixes article').count()) !== 4) failures.push('equipment-fixed-detail-desktop: expected four fixed affixes for 卓堇');
  if (await page.locator('.combination-builder').count()) failures.push('equipment-fixed-detail-desktop: fixed equipment should not show a random combination builder');
  const acquisitionText = await page.locator('.acquisition').textContent();
  if (!acquisitionText?.includes('未发现常规来源') || !acquisitionText.includes('宁毅') || !acquisitionText.includes('陆心月') || !acquisitionText.includes('暂不能确认玩家可正常获得')) failures.push('equipment-fixed-detail-desktop: NPC-only acquisition state is incomplete');
});

await inspect('equipment-treasure-detail-desktop', { width: 1440, height: 1000 }, '/wiki/zhuangbei/36101/', async (page) => {
  const text = await page.locator('.equipment-page').textContent();
  for (const term of ['专属效果', '蓄积', '1 条必定出现']) {
    if (!text?.includes(term)) failures.push(`equipment-treasure-detail-desktop: missing ${term}`);
  }
  if ((await page.locator('#intrinsic-effects .fixed-affixes article').count()) !== 1) failures.push('equipment-treasure-detail-desktop: intrinsic effect is not separated');
  if (await page.locator('#extra-attributes').count()) failures.push('equipment-treasure-detail-desktop: unverified random affix section is still visible');
  const tocLabels = await page.locator('.detail-toc a').allTextContents();
  if (tocLabels.join(',') !== ['装备介绍', '固定属性', '专属效果', '获取方式'].join(',')) failures.push('equipment-treasure-detail-desktop: detail toc is incorrect');
});

await inspect('danyao-index-desktop', { width: 1440, height: 1000 }, '/wiki/danyao/', async (page) => {
  const defaultCards = await page.locator('.filter-item:not([hidden])').count();
  if (defaultCards !== 15) failures.push(`danyao-index-desktop: expected 15 inner-strength medicines, found ${defaultCards}`);
  const expectedCounts = new Map([['内劲', 15], ['属性', 45], ['恢复', 15], ['功能', 3]]);
  for (const [category, count] of expectedCounts) {
    await page.locator(`.catalog-tabs button[data-category="${category}"]`).click();
    const visible = await page.locator('.filter-item:not([hidden])').count();
    if (visible !== count) failures.push(`danyao-index-desktop: expected ${count} ${category} cards, found ${visible}`);
  }
  await page.locator('.catalog-tabs button[data-category="属性"]').click();
  await page.locator('#danyao-attribute').selectOption('防御');
  if ((await page.locator('.filter-item:not([hidden])').count()) !== 5) failures.push('danyao-index-desktop: defense filter did not return 5 medicines');
  await page.locator('#danyao-quality').selectOption('5');
  if ((await page.locator('.filter-item:not([hidden])').count()) !== 1) failures.push('danyao-index-desktop: quality and defense filters did not combine');
  await page.locator('#danyao-quality').selectOption('');
  await page.locator('#danyao-attribute').selectOption('');
  await page.locator('#danyao-permanent').check();
  if ((await page.locator('.filter-item:not([hidden])').count()) !== 15) failures.push('danyao-index-desktop: permanent-only filter did not return 15 attribute medicines');
  await page.locator('#danyao-permanent').uncheck();
  await page.locator('#danyao-query').fill('暴击');
  if ((await page.locator('.filter-item:not([hidden])').count()) !== 10) failures.push('danyao-index-desktop: critical search did not return 10 attribute medicines');
  await page.locator('#danyao-query').fill('');
  await loadLazyImages(page);
});

await inspect('danyao-permanent-detail-desktop', { width: 1440, height: 1000 }, '/wiki/danyao/10116/', async (page) => {
  const text = await page.locator('.danyao-page').textContent();
  for (const term of ['暖阳丹', '永久属性丹', '阳 +2', '最多 3 次', '阳 +6', '炼制配方', '人参', '红花', '枸杞', '黄酒', '燕衔芦炼制']) {
    if (!text?.includes(term)) failures.push(`danyao-permanent-detail-desktop: missing ${term}`);
  }
  if ((await page.locator('.permanent-summary dl > div').count()) !== 3) failures.push('danyao-permanent-detail-desktop: permanent dosage summary is incomplete');
  const materialLinks = page.locator('#recipe .material-list a[href^="/wiki/cailiao/"]');
  if ((await materialLinks.count()) !== 4) failures.push('danyao-permanent-detail-desktop: recipe materials do not all link to material details');
  if (text?.includes('物品 ')) failures.push('danyao-permanent-detail-desktop: recipe still exposes internal item ids');
  const firstMaterialHref = await materialLinks.first().getAttribute('href');
  if (!firstMaterialHref || !(await page.request.get(`${baseUrl}${firstMaterialHref}`)).ok()) failures.push(`danyao-permanent-detail-desktop: recipe material link is invalid (${firstMaterialHref})`);
});

await inspect('danyao-recovery-detail-desktop', { width: 1440, height: 1000 }, '/wiki/danyao/10001/', async (page) => {
  const text = await page.locator('.danyao-page').textContent();
  for (const term of ['止血散', '生命 +150', '立即生效', '使用冷却', '9 秒', '恢复150生命', '燕衔芦', '行脚商人', '行商']) {
    if (!text?.includes(term)) failures.push(`danyao-recovery-detail-desktop: missing ${term}`);
  }
  if (await page.locator('.permanent-summary').count()) failures.push('danyao-recovery-detail-desktop: recovery medicine shows permanent dosage summary');
});

await inspect('materials-index-desktop', { width: 1440, height: 1000 }, '/wiki/cailiao/', async (page) => {
  if ((await page.locator('.filter-item:not([hidden])').count()) !== 167) failures.push('materials-index-desktop: expected 167 materials');
  await page.locator('.catalog-tabs button[data-category="药材"]').click();
  if ((await page.locator('.filter-item:not([hidden])').count()) !== 59) failures.push('materials-index-desktop: expected 59 medicinal materials');
  await page.locator('#material-usage').selectOption('炼丹');
  if ((await page.locator('.filter-item:not([hidden])').count()) !== 55) failures.push('materials-index-desktop: alchemy usage filter did not return 55 materials');
  await page.locator('#material-usage').selectOption('');
  await page.locator('#material-query').fill('人参');
  if ((await page.locator('.filter-item:not([hidden])').count()) !== 1) failures.push('materials-index-desktop: 人参 search did not return one material');
  await page.locator('#material-query').fill('');
  await page.locator('.catalog-tabs button[data-category=""]').click();
  await page.locator('#material-source').selectOption('dungeon');
  if ((await page.locator('.filter-item:not([hidden])').count()) !== 144) failures.push('materials-index-desktop: dungeon source filter did not return 144 materials');
  await page.locator('#material-source').selectOption('dismantle');
  if ((await page.locator('.filter-item:not([hidden])').count()) !== 7) failures.push('materials-index-desktop: dismantle source filter did not return 7 materials');
  await page.locator('#material-source').selectOption('smelting');
  if ((await page.locator('.filter-item:not([hidden])').count()) !== 9) failures.push('materials-index-desktop: smelting source filter did not return 9 materials');
  await page.locator('#material-source').selectOption('chest');
  if ((await page.locator('.filter-item:not([hidden])').count()) !== 7) failures.push('materials-index-desktop: chest source filter did not return 7 materials');
  const catalogText = await page.locator('main.materials-index').textContent();
  for (const term of ['37 处区域', '随剧情进度更新', '多个已解锁副本', '测试', '模板', '战斗测试Npc']) {
    if (catalogText?.includes(term)) failures.push(`materials-index-desktop: leaked unreliable source ${term}`);
  }
  await loadLazyImages(page);
});

await inspect('material-detail-desktop', { width: 1440, height: 1000 }, '/wiki/cailiao/1201/', async (page) => {
  const text = await page.locator('.material-page').textContent();
  for (const term of ['精铁', '锻造主材', '普通', '材料说明', '获取方式', '苍影阁 · 顾野樵', '副本产出', '竹海迷宫', '血炎追踪', '关联用途', '精铁剑', '铸纹制作', '堆叠']) {
    if (!text?.includes(term)) failures.push(`material-detail-desktop: missing ${term}`);
  }
  if (await page.locator('.target-grid a[href^="/wiki/zhuangbei/305"]').count()) failures.push('material-detail-desktop: trap target still points to equipment');
  if (!(await page.locator('.target-grid a[href="/wiki/xianjing/30501/"]').count())) failures.push('material-detail-desktop: trap recipe does not link back to 困兽夹');
  const tocLabels = await page.locator('.detail-toc a').allTextContents();
  if (tocLabels.join(',') !== ['材料说明', '材料属性', '关联用途', '获取方式'].join(',')) failures.push('material-detail-desktop: detail toc order is incorrect');
  const sectionIds = await page.locator('.detail-main > section').evaluateAll((sections) => sections.map((section) => section.id));
  if (sectionIds.join(',') !== ['overview', 'properties', 'usage', 'acquisition'].join(',')) failures.push('material-detail-desktop: section order is incorrect');
});

await inspect('material-dismantle-detail-desktop', { width: 1440, height: 1000 }, '/wiki/cailiao/1277/', async (page) => {
  const text = await page.locator('.material-page').textContent();
  for (const term of ['太初砂', '天工分解', '玄铁剑', '指定装备或铸纹', '2–5 个']) {
    if (!text?.includes(term)) failures.push(`material-dismantle-detail-desktop: missing ${term}`);
  }
  for (const term of ['测试', '模板', '战斗测试Npc']) {
    if (text?.includes(term)) failures.push(`material-dismantle-detail-desktop: leaked internal source name ${term}`);
  }
});

await inspect('material-smelting-detail-desktop', { width: 1440, height: 1000 }, '/wiki/cailiao/1191/', async (page) => {
  const text = await page.locator('.material-page').textContent();
  for (const term of ['万药粉', '天工熔炼', '投入药材', '根据熔炼结果获得']) {
    if (!text?.includes(term)) failures.push(`material-smelting-detail-desktop: missing ${term}`);
  }
});

await inspect('material-verified-dungeon-source-desktop', { width: 1440, height: 1000 }, '/wiki/cailiao/1279/', async (page) => {
  const text = await page.locator('.material-page').textContent();
  for (const term of ['傀陨铁', '副本产出', '血雨潇湘', '竹海迷宫', '血炎追踪', '鹤羽飘香']) {
    if (!text?.includes(term)) failures.push(`material-verified-dungeon-source-desktop: missing ${term}`);
  }
  for (const term of ['37 处区域', '宝箱获取', '敌人掉落', '云霞山庄', '极乐宫', '随剧情进度更新']) {
    if (text?.includes(term)) failures.push(`material-verified-dungeon-source-desktop: contains incorrect source ${term}`);
  }
});

await inspect('material-longyan-source-desktop', { width: 1440, height: 1000 }, '/wiki/cailiao/1010/', async (page) => {
  const text = await page.locator('.material-page').textContent();
  for (const term of ['龙涎果', '副本产出', '苍鹰探秘', '绝岭断龙', '葬花追凶', '莲花决战']) {
    if (!text?.includes(term)) failures.push(`material-longyan-source-desktop: missing ${term}`);
  }
  for (const term of ['瓮中捉鳖', '缥缈雪宫']) {
    if (text?.includes(term)) failures.push(`material-longyan-source-desktop: contains incorrect source ${term}`);
  }
});

await inspect('material-liuguang-source-desktop', { width: 1440, height: 1000 }, '/wiki/cailiao/1547/', async (page) => {
  const text = await page.locator('.material-page').textContent();
  for (const term of ['流光缎', '副本产出', '缥缈雪宫', '连云腹地', '鹤羽毒寨', '镇狱毒司']) {
    if (!text?.includes(term)) failures.push(`material-liuguang-source-desktop: missing ${term}`);
  }
  if (text?.includes('贪狼贼寨')) failures.push('material-liuguang-source-desktop: contains incorrect source 贪狼贼寨');
});

await inspect('entries-desktop', { width: 1440, height: 1000 }, '/entries/', async (page) => {
  const cards = await page.locator('.entries-grid .entry-card').count();
  if (cards !== 6) failures.push(`entries-desktop: expected 6 top-level entries, found ${cards}`);
  const systemCards = await page.locator('#systems .entry-card').count();
  if (systemCards !== 5) failures.push(`entries-desktop: expected 5 gameplay entries, found ${systemCards}`);
  const systemText = await page.locator('#systems').textContent();
  if (!systemText?.includes('陷阱') || !systemText.includes('铸纹') || systemText.includes('经脉') || systemText.includes('机簧')) {
    failures.push('entries-desktop: gameplay directory replacement is incomplete');
  }
  const directoryText = await page.locator('.directory-groups').textContent();
  if (directoryText?.includes('资料与考据') || directoryText?.includes('游戏资源索引') || await page.locator('#research').count()) failures.push('entries-desktop: research directory is still visible');
});

await inspect('traps-index-desktop', { width: 1440, height: 1000 }, '/wiki/xianjing/', async (page) => {
  if ((await page.locator('.filter-item:not([hidden])').count()) !== 10) failures.push('traps-index-desktop: expected 10 traps');
  await page.locator('#trap-effect').selectOption('中毒');
  if ((await page.locator('.filter-item:not([hidden])').count()) !== 2) failures.push('traps-index-desktop: poison filter did not return 2 traps');
  await page.locator('#trap-effect').selectOption('');
  await page.locator('#trap-query').fill('银丝');
  if ((await page.locator('.filter-item:not([hidden])').count()) !== 2) failures.push('traps-index-desktop: recipe material search did not return 2 traps');
  await page.locator('#trap-query').fill('');
  await page.locator('#trap-quality').selectOption('4');
  if ((await page.locator('.filter-item:not([hidden])').count()) !== 2) failures.push('traps-index-desktop: quality filter did not return 2 rare traps');
  await loadLazyImages(page);
});

await inspect('trap-detail-desktop', { width: 1440, height: 1000 }, '/wiki/xianjing/30510/', async (page) => {
  const text = await page.locator('.trap-page').textContent();
  for (const term of ['电击匣', '绝世', '闪电链', '最多链接5个敌人', '3,750 修习点', '引雷针', '龙鳞金', '银丝', '800 铜钱', '打造制作', '使用冷却']) {
    if (!text?.includes(term)) failures.push(`trap-detail-desktop: missing ${term}`);
  }
  const tocLabels = await page.locator('.detail-toc a').allTextContents();
  if (!['陷阱说明', '实际效果', '修习解锁', '制作配方', '获取方式', '使用参数'].every((label) => tocLabels.includes(label))) failures.push('trap-detail-desktop: detail toc is incomplete');
  if ((await page.locator('.material-grid a[href^="/wiki/cailiao/"]').count()) !== 2) failures.push('trap-detail-desktop: material links are incomplete');
  for (let id = 30501; id <= 30510; id += 1) {
    const response = await page.request.get(`${baseUrl}/wiki/xianjing/${id}/`);
    if (!response.ok()) failures.push(`trap-detail-desktop: trap ${id} returned HTTP ${response.status()}`);
    const icon = await page.request.get(`${baseUrl}/game/traps/${id}.png`);
    if (!icon.ok()) failures.push(`trap-detail-desktop: icon ${id} returned HTTP ${icon.status()}`);
  }
});

await inspect('entries-mobile', { width: 390, height: 844 }, '/entries/', async (page) => {
  const heading = await page.locator('main h1.page-heading').textContent();
  if (heading?.trim() !== '百科目录') failures.push(`entries-mobile: expected 百科目录 heading, found ${heading?.trim()}`);
  const groups = await page.locator('.directory-group').count();
  if (groups !== 2) failures.push(`entries-mobile: expected 2 directory groups, found ${groups}`);
  const cards = await page.locator('.entries-grid .entry-card').count();
  if (cards !== 6) failures.push(`entries-mobile: expected 6 top-level entries, found ${cards}`);
  await page.locator('.nav-toggle').click();
  const expanded = await page.locator('.nav-toggle').getAttribute('aria-expanded');
  if (expanded !== 'true') failures.push('entries-mobile: navigation did not expand');
  const sidebarText = await page.locator('#site-sidebar nav').textContent();
  if (!sidebarText?.includes('首页') || !sidebarText.includes('百科目录') || !sidebarText.includes('武学图鉴') || !sidebarText.includes('陷阱图鉴') || !sidebarText.includes('MOD') || !sidebarText.includes('游戏更新公告')) failures.push('entries-mobile: reorganized navigation labels are missing');
  const sidebarGroups = await page.locator('#site-sidebar .nav-group').evaluateAll((groups) => Object.fromEntries(groups.map((group) => [group.querySelector('.nav-label')?.textContent?.trim(), group.textContent?.trim()])));
  if (!sidebarGroups['工具']?.includes('MOD') || sidebarGroups['专题']?.includes('MOD')) failures.push('entries-mobile: MOD is not grouped under tools');
  for (const removedLabel of ['百科总览', '考据库', '关于与参与']) {
    if (sidebarText?.includes(removedLabel)) failures.push(`entries-mobile: removed navigation label ${removedLabel} is still visible`);
  }
  if (await page.locator('#site-sidebar a[href="/systems/"]').count()) failures.push('entries-mobile: legacy systems link is still in primary navigation');
  await page.locator('.nav-scrim').click();
});

await inspect('mods-mobile', { width: 390, height: 844 }, '/mods/', async (page) => {
  const text = await page.locator('.mods-page').textContent();
  if (!text?.includes('MOD') || !text.includes('正在设计中~')) failures.push('mods-mobile: placeholder content is incomplete');
});

await inspect('updates-desktop', { width: 1440, height: 1000 }, '/updates/', async (page) => {
  if ((await page.locator('.news-item').count()) === 0) failures.push('updates-desktop: Steam announcements are missing');
  const firstItem = await page.locator('.news-item').first().textContent();
  if (!firstItem?.includes('版本更新公告')) failures.push('updates-desktop: latest Steam update title is missing');
  const firstHref = await page.locator('.news-item').first().locator('h2 a').getAttribute('href');
  if (firstHref !== '/updates/1839676055881984/') failures.push(`updates-desktop: announcement does not link to its detail page (${firstHref})`);
  if (!(await page.locator('.news-item').first().locator('.news-link').isVisible())) failures.push('updates-desktop: Steam source link is missing');
});

await inspect('updates-mobile', { width: 390, height: 844 }, '/updates/', async (page) => {
  if (!(await page.locator('.steam-link').isVisible()) || (await page.locator('.news-item').count()) === 0) failures.push('updates-mobile: Steam source link or announcements are missing');
});

await inspect('recent-desktop', { width: 1440, height: 1000 }, '/recent/', async (page) => {
  await page.evaluate(() => {
    const now = Date.now();
    localStorage.setItem('xy-wiki-recent', JSON.stringify([
      { slug: 'wuxue-70081', title: '玄清道', path: '/wiki/wuxue/70081/', visitedAt: now - 4 * 60 * 1000 },
      { slug: 'cailiao-1277', title: '太初砂', path: '/wiki/cailiao/1277/', visitedAt: now - 2 * 60 * 60 * 1000 },
    ]));
    localStorage.setItem('xy-wiki-bookmarks', JSON.stringify(['wuxue-70081']));
  });
  await page.reload({ waitUntil: 'networkidle' });
  if ((await page.locator('.recent-list .personal-item').count()) !== 2 || (await page.locator('.bookmark-list .personal-item').count()) !== 1) failures.push('recent-desktop: saved items did not render');
  const recentText = await page.locator('.recent-list').textContent();
  if (!recentText?.includes('玄清道') || !recentText.includes('武学') || !recentText.includes('分钟前') || !recentText.includes('太初砂') || !recentText.includes('材料')) failures.push('recent-desktop: item hierarchy or relative time is incomplete');
  if ((await page.locator('.recent-count').textContent())?.trim() !== '2' || (await page.locator('.bookmark-count').textContent())?.trim() !== '1') failures.push('recent-desktop: panel counts are incorrect');
  const panels = await page.locator('.personal-panel').evaluateAll((items) => items.map((item) => item.getBoundingClientRect().height));
  if (panels[0] === panels[1]) failures.push('recent-desktop: panels are still forced to equal height');
});

await inspect('recent-mobile', { width: 390, height: 844 }, '/recent/', async (page) => {
  await page.evaluate(() => localStorage.setItem('xy-wiki-recent', JSON.stringify([{ slug: 'wuxue-70081', title: '玄清道', path: '/wiki/wuxue/70081/', visitedAt: Date.now() - 60 * 1000 }])));
  await page.reload({ waitUntil: 'networkidle' });
  const columns = await page.locator('.personal-grid').evaluate((element) => getComputedStyle(element).gridTemplateColumns.split(' ').length);
  if (columns !== 1 || !(await page.locator('.personal-link').first().isVisible())) failures.push('recent-mobile: single-column item layout is incorrect');
});

await inspect('update-detail-desktop', { width: 1440, height: 1000 }, '/updates/1839676055881984/', async (page) => {
  const text = await page.locator('.update-detail').textContent();
  if (!text?.includes('手柄操作优化') || !text.includes('Boss AI 优化') || !text.includes('1074840507')) failures.push('update-detail-desktop: full announcement content is incomplete');
  if ((await page.locator('.news-body h2').count()) === 0 || (await page.locator('.news-body li').count()) === 0) failures.push('update-detail-desktop: announcement structure is missing');
  if ((await page.locator('.news-body a[href^="http"]').count()) === 0) failures.push('update-detail-desktop: announcement links are missing');
  if (!(await page.locator('.steam-source').isVisible())) failures.push('update-detail-desktop: Steam source link is missing');
});

await inspect('update-detail-mobile', { width: 390, height: 844 }, '/updates/1839676055881984/', async (page) => {
  if ((await page.locator('.news-body li').count()) === 0 || !(await page.locator('.steam-source').isVisible())) failures.push('update-detail-mobile: formatted content or Steam source link is missing');
});

await inspect('wuxue-index-mobile', { width: 390, height: 844 }, '/wiki/wuxue/', async (page) => {
  if (!(await page.locator('.affinity-control').isVisible())) failures.push('wuxue-index-mobile: affinity control is hidden');
  await page.locator('.style-control button[data-style="拳罡"]').click();
  const fistCards = await page.locator('.filter-item:not([hidden])').count();
  if (fistCards !== 20) failures.push(`wuxue-index-mobile: expected 20 player fist cards, found ${fistCards}`);
  await loadLazyImages(page);
});

await inspect('wuxue-detail-mobile', { width: 390, height: 844 }, '/wiki/wuxue/10141/', async (page) => {
  if (!(await page.locator('.detail-toc-mobile').isVisible())) failures.push('wuxue-detail-mobile: compact detail toc is hidden');
  await page.locator('.detail-toc-mobile summary').click();
  if ((await page.locator('.detail-toc-mobile a').count()) !== 3) failures.push('wuxue-detail-mobile: compact detail toc is incomplete');
  if ((await page.locator('.training-node').count()) === 0) failures.push('wuxue-detail-mobile: gongfa training graph is missing');
});

await inspect('equipment-index-mobile', { width: 390, height: 844 }, '/wiki/zhuangbei/', async (page) => {
  await page.locator('.catalog-tabs button[data-category="防具"]').click();
  if ((await page.locator('.filter-item:not([hidden])').count()) !== 30) failures.push('equipment-index-mobile: expected 30 armor cards');
  await loadLazyImages(page);
});

await inspect('equipment-detail-mobile', { width: 390, height: 844 }, '/wiki/zhuangbei/34016/', async (page) => {
  if ((await page.locator('[data-affix-row]').count()) !== 38) failures.push('equipment-detail-mobile: expected 38 affix candidates for 化天镯');
  if ((await page.locator('.affix-select:not([disabled])').count()) !== 4) failures.push('equipment-detail-mobile: expected four active affix slots');
  if (!(await page.locator('.socket-probability').isVisible())) failures.push('equipment-detail-mobile: socket probability table is hidden');
  if (!(await page.locator('.acquisition').isVisible())) failures.push('equipment-detail-mobile: acquisition section is hidden');
  await page.locator('.detail-toc-mobile summary').click();
  const tocLabels = await page.locator('.detail-toc-mobile a').allTextContents();
  if (tocLabels.join(',') !== ['装备介绍', '固定属性', '额外属性', '镶嵌孔位', '获取方式'].join(',')) failures.push('equipment-detail-mobile: accessory toc order is incorrect');
});

await inspect('equipment-weapon-detail-mobile', { width: 390, height: 844 }, '/wiki/zhuangbei/30002/', async (page) => {
  if ((await page.locator('.slot-track > div').count()) !== 4) failures.push('equipment-weapon-detail-mobile: expected four rendered weapon affix slots');
  if ((await page.locator('.affix-select:not([disabled])').count()) !== 4) failures.push('equipment-weapon-detail-mobile: expected four active weapon affix selects');
  const text = await page.locator('#extra-attributes').textContent();
  if (!text?.includes('最多 4 条') || !text.includes('4 条词条组合') || !text.includes('词条槽位 4')) failures.push('equipment-weapon-detail-mobile: four-slot copy is incomplete');
});

await inspect('danyao-index-mobile', { width: 390, height: 844 }, '/wiki/danyao/', async (page) => {
  await page.locator('.catalog-tabs button[data-category="恢复"]').click();
  if ((await page.locator('.filter-item:not([hidden])').count()) !== 15) failures.push('danyao-index-mobile: expected 15 recovery medicines');
  await page.locator('#danyao-attribute').selectOption('生命');
  if ((await page.locator('.filter-item:not([hidden])').count()) !== 5) failures.push('danyao-index-mobile: life recovery filter did not return 5 medicines');
  await loadLazyImages(page);
});

await inspect('danyao-detail-mobile', { width: 390, height: 844 }, '/wiki/danyao/10504/', async (page) => {
  const text = await page.locator('.danyao-page').textContent();
  if (!text?.includes('混元无极丹') || !text.includes('经脉点数 +5') || !text.includes('最多 2 次') || !text.includes('经脉点数 +10')) failures.push('danyao-detail-mobile: special medicine limit or maximum gain is incomplete');
  if (!(await page.locator('.material-list').isVisible()) || !(await page.locator('.acquisition').isVisible())) failures.push('danyao-detail-mobile: recipe or acquisition section is hidden');
});

await inspect('materials-index-mobile', { width: 390, height: 844 }, '/wiki/cailiao/', async (page) => {
  await page.locator('.catalog-tabs button[data-category="锻造辅材"]').click();
  if ((await page.locator('.filter-item:not([hidden])').count()) !== 69) failures.push('materials-index-mobile: expected 69 forging auxiliary materials');
  await page.locator('#material-quality').selectOption('3');
  if ((await page.locator('.filter-item:not([hidden])').count()) === 0) failures.push('materials-index-mobile: combined category and quality filters returned no results');
  await loadLazyImages(page);
});

await inspect('traps-index-mobile', { width: 390, height: 844 }, '/wiki/xianjing/', async (page) => {
  await page.locator('#trap-quality').selectOption('3');
  if ((await page.locator('.filter-item:not([hidden])').count()) !== 4) failures.push('traps-index-mobile: expected 4 rare traps');
  await loadLazyImages(page);
});

await inspect('trap-detail-narrow', { width: 320, height: 720 }, '/wiki/xianjing/30502/', async (page) => {
  const text = await page.locator('.trap-page').textContent();
  if (!text?.includes('棘地刺') || !text.includes('减速') || !text.includes('黑铁') || !text.includes('困兽夹')) failures.push('trap-detail-narrow: content is incomplete');
  if (!(await page.locator('.detail-toc-mobile').isVisible())) failures.push('trap-detail-narrow: compact detail toc is hidden');
});

await inspect('material-detail-mobile', { width: 390, height: 844 }, '/wiki/cailiao/1001/', async (page) => {
  const text = await page.locator('.material-page').textContent();
  if (!text?.includes('人参') || !text.includes('止血散') || !text.includes('行脚商人') || !text.includes('铸纹制作')) failures.push('material-detail-mobile: source or usage content is incomplete');
  if (!(await page.locator('.detail-toc-mobile').isVisible())) failures.push('material-detail-mobile: compact detail toc is hidden');
  await page.locator('.detail-toc-mobile summary').click();
  if ((await page.locator('.detail-toc-mobile a').count()) !== 4) failures.push('material-detail-mobile: compact detail toc is incomplete');
});

await inspect('xinfa-detail-mobile', { width: 390, height: 844 }, '/wiki/wuxue/70061/', async (page) => {
  const nodes = await page.locator('.training-node').count();
  if (nodes !== 6) failures.push(`xinfa-detail-mobile: expected 6 graph nodes, found ${nodes}`);
  if ((await page.locator('.graph-edge').count()) !== 5) failures.push('xinfa-detail-mobile: expected 5 graph edges');
  if (await page.locator('.power-list').count()) failures.push('xinfa-detail-mobile: power configuration should not be shown for heart methods');
  const articleText = await page.locator('.wuxue-page').textContent();
  if (!articleText?.includes('秘籍：乾坤诀')) failures.push('xinfa-detail-mobile: manual alias 乾坤诀 is missing');
});

await inspect('search-mobile', { width: 390, height: 844 }, '/search/?q=一气化三诀', async (page) => {
  await page.locator('.search-results li').first().waitFor({ timeout: 10000 });
  const resultText = await page.locator('.search-results').textContent();
  if (!resultText?.includes('三才化元诀') || !resultText.includes('精良') || resultText.includes('品质 2')) failures.push('search-mobile: legacy name 一气化三诀 did not resolve with the named quality label');
  const firstHref = await page.locator('.search-results a').first().getAttribute('href');
  if (firstHref !== '/wiki/wuxue/80121/') failures.push(`search-mobile: legacy name resolved to ${firstHref}`);
  await page.locator('#full-search').fill('暖阳丹');
  await page.locator('.search-form button').click();
  await page.locator('.search-results a[href="/wiki/danyao/10116/"]').waitFor({ timeout: 10000 });
  const danyaoText = await page.locator('.search-results').textContent();
  if (!danyaoText?.includes('暖阳丹')) failures.push('search-mobile: full search did not find 暖阳丹');
});

await inspect('zhuwen-index-desktop', { width: 1440, height: 1000 }, '/wiki/zhuwen/', async (page) => {
  if ((await page.locator('.filter-item:not([hidden])').count()) !== 33) failures.push('zhuwen-index-desktop: expected 33 fixed inscription series');
  await page.locator('.mode-tabs button[data-mode="random"]').click();
  if ((await page.locator('.filter-item:not([hidden])').count()) !== 3) failures.push('zhuwen-index-desktop: expected 3 random inscriptions');
  await page.locator('.mode-tabs button[data-mode="companion"]').click();
  if ((await page.locator('.filter-item:not([hidden])').count()) !== 18) failures.push('zhuwen-index-desktop: expected 18 companion materials');
  await page.locator('#zhuwen-query').fill('灵苍');
  const filtered = page.locator('.filter-item:not([hidden])');
  if ((await filtered.count()) !== 1 || !(await filtered.textContent())?.includes('灵苍')) failures.push('zhuwen-index-desktop: companion search did not find 灵苍');
  await loadLazyImages(page);
});

await inspect('zhuwen-fixed-detail-desktop', { width: 1440, height: 1000 }, '/wiki/zhuwen/fixed-1-2/', async (page) => {
  if ((await page.locator('.stage-table article').count()) !== 7) failures.push('zhuwen-fixed-detail-desktop: life inscription does not have 7 stages');
  const finalStage = await page.locator('.stage-table article').last().textContent();
  if (!finalStage?.includes('346–433') || !finalStage.includes('太初砂')) failures.push('zhuwen-fixed-detail-desktop: final life stage is incomplete');
  if ((await page.locator('.stage-materials a[href^="/wiki/cailiao/"]').count()) === 0) failures.push('zhuwen-fixed-detail-desktop: material links are missing');
  const toc = await page.locator('.detail-toc a').allTextContents();
  if (!['铸纹说明', '阶段成长', '制作配方', '镶嵌方式', '属性一览'].every((label) => toc.includes(label))) failures.push('zhuwen-fixed-detail-desktop: detail toc is incomplete');
});

await inspect('zhuwen-random-detail-desktop', { width: 1440, height: 1000 }, '/wiki/zhuwen/random-3501/', async (page) => {
  if ((await page.locator('.spell-pool details').count()) !== 72) failures.push('zhuwen-random-detail-desktop: expected 72 martial-art groups');
  if ((await page.locator('#candidates .candidate-grid article').count()) !== 337) failures.push('zhuwen-random-detail-desktop: expected all 337 candidate affixes');
  const firstSummary = page.locator('.spell-pool details summary').first();
  await firstSummary.click();
  if (!(await page.locator('.spell-pool details').first().evaluate((element) => element.open))) failures.push('zhuwen-random-detail-desktop: martial-art candidate group did not expand');
});

await inspect('zhuwen-companion-detail-narrow', { width: 320, height: 720 }, '/wiki/zhuwen/companion-7712/', async (page) => {
  const text = await page.locator('.zhuwen-page').textContent();
  if (!text?.includes('灵苍') || !text.includes('火候 250') || !text.includes('随机1条词条')) failures.push('zhuwen-companion-detail-narrow: soul material details are incomplete');
  if ((await page.locator('#candidates .candidate-grid article').count()) !== 46) failures.push('zhuwen-companion-detail-narrow: expected 46 random affixes');
  if (!(await page.locator('.detail-toc-mobile').isVisible())) failures.push('zhuwen-companion-detail-narrow: compact detail toc is hidden');
});

await inspect('zhuwen-material-backlink-mobile', { width: 390, height: 844 }, '/wiki/cailiao/1271/', async (page) => {
  if (!(await page.locator('a[href="/wiki/zhuwen/fixed-1-2/"]').count())) failures.push('zhuwen-material-backlink-mobile: fixed inscription backlink is missing');
});

await inspect('home-narrow', { width: 320, height: 720 }, '/', async (page) => {
  const headerBox = await page.locator('.site-header').boundingBox();
  if (!headerBox || headerBox.width > 320) failures.push('home-narrow: header exceeds viewport');
});

await browser.close();

if (failures.length) {
  console.error('\nVisual QA failed:');
  failures.forEach((failure) => console.error(`- ${failure}`));
  process.exit(1);
}
console.log('\nVisual QA passed.');
