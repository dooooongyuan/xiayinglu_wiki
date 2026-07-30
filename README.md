# 侠影录 Wiki

基于 Astro 7、TypeScript 和 Pagefind 的现代静态 Wiki，以及配套的游戏资源索引工具。游戏安装目录仅作为只读数据源，所有生成内容都位于本项目内。

## 架构说明

- Astro 静态生成：部署后不需要 Node.js、数据库或后台常驻服务。
- Pagefind：在浏览器中提供简体中文全文搜索，不依赖第三方搜索服务。
- TypeScript 严格模式：条目结构、来源、反向链接和信息框使用类型化数据维护。
- Nginx / Docker：可部署到普通 Linux 服务器、宝塔、对象存储或 CDN。
- Git：建议用 Git 管理条目修订历史；当前目录不会自动初始化仓库。

与 Wiki.js 这类动态 Wiki 相比，这套架构的运维面更小，适合以版本考据、资源索引和人工校订为主的单机游戏资料站。

## 本地开发

```powershell
cd E:\xiayinglu\wiki
npm.cmd install
npm.cmd run dev
```

开发服务器默认位于 `http://localhost:4321/`。

## 更新游戏索引

```powershell
python E:\xiayinglu\scripts\index_game.py
python E:\xiayinglu\scripts\extract_wiki_assets.py
python E:\xiayinglu\scripts\extract_wuxue.py
python E:\xiayinglu\scripts\extract_equipment.py
python E:\xiayinglu\scripts\extract_danyao.py
python E:\xiayinglu\scripts\extract_materials.py
python E:\xiayinglu\scripts\extract_traps.py
python E:\xiayinglu\scripts\extract_zhuwen.py
python E:\xiayinglu\scripts\extract_characters.py
```

默认只扫描 128 MB 以下的资源包元数据，大型场景与视频包会跳过。需要完整扫描时传入
`--max-bundle-mb 0`。增量缓存保存在 `logs/bundle-index.json`。素材导出脚本只处理明确的白名单，不会修改游戏安装目录。各图鉴提取脚本分别重建武学、装备、丹药和材料数据，并把对应 UI 图标写入 `wiki/public/game/` 下的独立目录。材料提取同时反查炼丹、打造和铸纹配方，并关联商店、战利品、NPC 与地图来源。

## 生产构建

```powershell
cd E:\xiayinglu\wiki
npm.cmd run build
```

构建产物位于 `wiki/dist/`，可直接部署到 Nginx、对象存储或 CDN。

正式构建时应传入站点公开地址，Sitemap、RSS 和 `robots.txt` 会使用这个地址：

```powershell
$env:SITE_URL = 'https://wiki.example.com'
$env:PUBLIC_REPO_URL = 'https://github.com/dooooongyuan/xiayinglu_wiki'
npm.cmd run build
```

`PUBLIC_REPO_URL` 可省略。设置后，条目页的修订入口会指向对应的 Git 仓库。

## 质量检查

先在终端 1 启动生产预览：

```powershell
cd E:\xiayinglu\wiki
npm.cmd run preview -- --host 0.0.0.0
```

保持预览进程运行，在终端 2 执行：

```powershell
cd E:\xiayinglu\wiki
npm.cmd run qa:visual
npm.cmd run qa:links
```

视觉检查覆盖桌面、手机和 320px 超窄屏，并验证搜索、筛选、收藏、移动导航、横向溢出和浏览器控制台错误。

链接检查直接解析 `dist/` 内的静态文件，不需要启动预览服务器；运行前应先执行 `npm.cmd run build`。不传参数时检查全站，开发单个专题时可传入路径，只检查该路径下的页面及其链接目标：

```powershell
npm.cmd run qa:links -- /wiki/xianjing/
npm.cmd run qa:links -- /wiki/xianjing/ /entries/
```

专题范围检查适合日常开发，正式发布前再运行一次不带路径参数的全站检查。两种模式都会核对站内地址和页内锚点。

## Docker 部署

```bash
cd /path/to/xiayinglu/wiki
docker build \
  --build-arg SITE_URL=https://wiki.example.com \
  --build-arg PUBLIC_REPO_URL=https://github.com/dooooongyuan/xiayinglu_wiki \
  -t xiayinglu-wiki .
docker run -d --name xiayinglu-wiki --restart unless-stopped -p 8080:80 xiayinglu-wiki
```

然后让服务器反向代理或域名直接指向 `8080` 端口。没有 Git 仓库修订入口时可省略 `PUBLIC_REPO_URL` 参数。

## Nginx / 宝塔部署

1. 在本地用正式 `SITE_URL` 执行 `npm.cmd run build`。
2. 将 `wiki/dist/` 内的全部内容上传到网站根目录，不要上传 `dist` 目录外壳。
3. 站点根目录配置为该上传目录，首页设为 `index.html`。
4. 使用 `wiki/nginx.conf` 中的 `location`、缓存和 404 规则；宝塔可把相应内容合并进网站的 Nginx 配置。
5. 开启 HTTPS 后重新用最终 `https://` 域名构建并上传，保证 canonical URL、RSS、Sitemap 和 `robots.txt` 一致。

纯静态部署不支持访客直接在线编辑。修订流程是通过 Git 仓库提交内容变更，再重新构建发布；收藏和最近浏览保存在各访客浏览器的本地存储中。

## Cloudflare Workers Builds

站点使用 Workers Static Assets 部署，不需要 Astro SSR 适配器或 Worker 入口文件。在 Cloudflare Dashboard 中连接本仓库后填写：

```text
Git repository: dooooongyuan/xiayinglu_wiki
Production branch: main
Root directory: /wiki
Build command: npm run build
Deploy command: npm run deploy
```

构建环境使用 Node.js 22，并设置正式站点地址：

```text
NODE_VERSION=22
SITE_URL=https://你的正式域名
```

`SITE_URL` 会写入 canonical URL、Sitemap、RSS 和 `robots.txt`，必须与最终对外域名一致。本地验证 Cloudflare 部署包时运行：

```powershell
cd E:\xiayinglu\wiki
npm.cmd ci
npm.cmd run build
npm.cmd run deploy:dry-run
```

## Steam 公告自动同步

`.github/workflows/update-steam-news.yml` 每天约在北京时间 09:17 检查一次 Steam 官方公告，也可以在 GitHub Actions 页面手动运行。只有公告列表或正文发生变化时才会提交 `wiki/src/data/steam-news.generated.json`；该提交会继续触发 Cloudflare Workers Builds，将新公告发布到 Wiki。

本地手动检查可运行：

```powershell
cd E:\xiayinglu\wiki
npm.cmd run news:update -- --strict
```

`--strict` 用于自动化任务：Steam API 暂时不可用时保留现有公告，同时让任务失败并留下可见日志，避免误以为同步成功。
