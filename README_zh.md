<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/logo-dark.svg">
  <img width="112" src="docs/images/logo.svg" alt="Postflow logo">
</picture>

# Postflow

**粘贴一次，同时发布到多个静态博客。**

把文章生成 Hexo / VuePress / Hugo / Jekyll / Astro … 各自格式的 Markdown，提交到各博客的源码仓库，由 GitHub Actions 构建部署——并在部署前逐页比对线上站点，**不让老页面的 SEO 被悄悄改坏**。

[English](README.md) | 简体中文

![License](https://img.shields.io/badge/license-MIT-green.svg)
![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-backend-009688?logo=fastapi&logoColor=white)
![Tests](https://img.shields.io/badge/tests-114%20passed-brightgreen)

![写作页](docs/images/write.png)

</div>

## 为什么做这个项目

我的文章先写在公众号上，然后要同步到三个独立博客：两个 Hexo（主题不同）、一个 VuePress。三个博客的 front matter 各不一样，部署方式也不一样。以前每发一篇文章都要：

1. 打开放博客源码的那台 Windows 电脑；
2. 把正文粘进 `source.md`，手改标题、日期、标签、分类、描述、关键词；
3. 跑一个 Python 脚本，生成三份格式不同的 md；
4. 分别复制到三个博客目录；
5. 三次 `hexo clean && hexo d -g` / `deploy.sh`，其中一个每次还要输服务器密码。

一篇文章 15～20 分钟，只能在那一台电脑上做；哪一步漏了，就有一个博客少一篇，自己还不知道。

想把它搬到 CI 上时，又碰到一个更大的顾虑：这几个博客都跑了好几年，主要靠搜索带流量。**构建环境一换（Windows → Linux），文件顺序、大小写、修改时间、时区、换行符都可能变**，老页面的 URL、正文、`<title>`、sitemap 就会悄悄变化，排名跟着掉，而且不会有任何报错。

所以 Postflow 做两件事：

- **发布**：浏览器里粘贴一次 → AI 补全 SEO 元数据 → 按每个博客的主题生成 md → 通过 GitHub API 提交到各自源码仓库 → 各仓库的 Actions 构建部署。手机上也能发。
- **守门**：每次部署前把新构建和线上站点逐页比对，老页面消失、正文变化、sitemap 缺地址就**拦下不部署**；默认先「影子模式」只构建不部署，确认零差异才切换。

作者自己的三个博客（两个 Hexo、一个 VuePress）已经用它完成迁移并正常发文：切换前后逐页比对，老页面正文 0 变化、sitemap 无地址消失。

## 截图

| 预览：每个博客一份 md | 发布结果：提交 + Actions 状态 |
|---|---|
| ![预览](docs/images/preview.png) | ![发布结果](docs/images/result.png) |
| **文章：管理仓库里已有的文章** | **设置：博客、Token、AI 接口** |
| ![文章](docs/images/articles.png) | ![设置](docs/images/settings.png) |
| **登录** | **暗色模式** |
| ![登录](docs/images/login.png) | ![暗色](docs/images/write-dark.png) |

## 功能

**写作与发布**
- 粘贴富文本自动转 Markdown：飞书文档、公众号后台、网页、Word / Google Docs（标题、加粗、列表、代码块、表格、链接、图片等）；`⌘Z` 撤销转换，`⌘⇧V` 按纯文本粘贴。飞书 / 公众号的图片（需登录或防盗链）会提醒换图床
- AI 生成英文 slug、描述（100～130 字）、关键词；**不改你的标题**。没配 AI 时按标题生成拼音 slug
- 预览每个博客将要提交的 md，目标文件已存在会提醒，勾选才覆盖
- 一次发布到多个博客，**单个博客失败不影响其他**，历史页可重发 / 补发
- 发布后自动轮询 GitHub Actions 状态，给出提交、运行、文章链接
- 新文章正文里的 H1 自动降一级，一页只保留一个 H1
- 草稿自动保存、导入 / 拖入 `.md`、阅读时长、快捷键（`⌘↵` 预览、`⌘⇧↵` 发布、`?` 帮助）、亮 / 暗主题

**多博客、多主题**
- 14 个主题预设：Hexo（通用 / Butterfly / NexT / Fluid / Icarus）、VuePress theme-hope、VitePress、Hugo、Jekyll、Astro、Docusaurus，以及 3 个「经典」格式
- 每个博客可在设置页用 YAML 覆盖 `fields`、`date_format`、`more` 位置、H1 处理等
- 文件名 / 文章链接模板：`{slug}` `{year}` `{month}` `{day}` `{category_dir}`；按分类放子目录（适合按目录生成侧边栏的 VuePress）
- 博客可以在不同 GitHub 账号下：每个博客可配专用 Token，留空用全局 Token

**管理已有文章**
- 「文章」页列出仓库里全部文章（包括以前用别的方式发的），编辑时**只改动过的字段**，其余逐字保留
- 删除 / 改正文时，自动把页面登记进 SEO 守门的放行名单，与改动在同一个提交里

**SEO 守门（GitHub Actions 里运行）**
- 影子模式：先只构建并比对，报告写在 Actions Summary，确认后加一个变量才真正部署
- 阻断：页面 / 文件消失、sitemap 地址消失、`CNAME` / `robots.txt` / `ads.txt` 变化、老页面正文变化
- 提醒：title、description、keywords、canonical、og:*、JSON-LD、h1 变化
- 详见 [workflows/README.md](workflows/README.md)

**安全**
- 单用户：scrypt 密码、登录限速、CSRF、CSP 等安全头；首次使用需要服务器日志里的初始化码
- 密钥只存在服务器本地 SQLite，页面上只显示末 4 位
- AI 接口地址禁止内网 / 本机（防止借「测试连接」探测服务器内网），可用环境变量放开

## 工作原理

```
浏览器 ──登录──▶ Postflow（FastAPI + SQLite，单页前端无构建链）
                  · AI 补全 slug / 描述 / 关键词（Anthropic 或 OpenAI 兼容接口）
                  · 适配器按主题预设生成各博客的 md
                  · GitHub API 提交（Contents / Git Data API）
                  ▼
        博客源码仓库 ×N ──push──▶ GitHub Actions
                                    · 构建（hexo / vuepress / …）
                                    · compare_site.py 与线上逐页比对（SEO 守门）
                                    · 无阻断项才部署（GitHub Pages / 自己的服务器）
```

Postflow 只负责「生成 md 并提交」，构建和部署全在各博客仓库的 Actions 里，所以它不需要你的服务器密码，也不需要装 Node。

## 快速开始（本地）

```sh
git clone https://github.com/ZekerTop/blog-postflow.git
cd blog-postflow
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
POSTFLOW_COOKIE_SECURE=false .venv/bin/uvicorn --factory app.main:app_from_env --port 8000
```

1. 打开 http://localhost:8000 ，用启动日志里的**初始化码**（也写在 `data/setup-code.txt`）设置登录密码。
2. 「设置 → GitHub」：填一个 [fine-grained PAT](https://github.com/settings/personal-access-tokens)，只授权博客源码仓库，权限 **Contents 读写 + Actions 只读**。
3. 「设置 → AI 接口」（可选）：Anthropic 官方 / 兼容中转，或 OpenAI 兼容格式（DeepSeek、Kimi、OpenRouter 等），先「测试连接」再保存。
4. 「设置 → 博客 → 添加博客」：选主题预设，填源码仓库和分支，点「检查连接」。
5. 回到「写作」，粘贴文章，预览，发布。

> 本地是 http，所以要 `POSTFLOW_COOKIE_SECURE=false`；线上走 HTTPS 时保持默认 `true`。其余环境变量见 [.env.example](.env.example)（全部可选）。

## 用 Docker 部署

```sh
docker build -t postflow .
mkdir -p data && sudo chown 10001:10001 data
docker run -d --name postflow --restart unless-stopped \
  -p 127.0.0.1:8790:8000 -v "$PWD/data:/data" \
  --read-only --tmpfs /tmp --cap-drop ALL --security-opt no-new-privileges \
  postflow
docker logs postflow   # 看初始化码
```

再用 nginx 反代并配 HTTPS（示例 [deploy/nginx.example.conf](deploy/nginx.example.conf)）。完整的服务器部署、备份、升级、回滚见 [docs/DEPLOY.md](docs/DEPLOY.md)。

## 接入一个博客

1. 把博客**源码**（不是构建产物）放进一个 GitHub 仓库，建议私有。
2. 从 [`workflows/examples/`](workflows/examples) 选一个最接近的 workflow，放到源码仓库 `.github/workflows/deploy.yml`，`compare_site.py` 放到 `.github/scripts/`，配好 Secrets。
3. 推一次，Actions 会只构建并和线上比对；看 Summary 里的报告，**零阻断**后在仓库 Variables 里加 `DEPLOY_ENABLED=true`。
4. 在 Postflow「设置」里添加这个博客，先用一篇已发布文章核对一次生成格式（「文章」页载入、预览即可）。

从 Windows 本地构建迁移、要求逐字节一致时的注意事项（文件顺序、修改时间、换行符、locale 等）见 [workflows/README.md](workflows/README.md)。

## 主题预设

| 预设 | 说明 |
|---|---|
| `hexo` / `hexo-butterfly` / `hexo-next` / `hexo-fluid` / `hexo-icarus` | Hexo 通用及常见主题 |
| `vuepress-hope` / `vitepress` | VuePress theme-hope、VitePress |
| `hugo` / `jekyll` / `astro` / `docusaurus` | 其他常见静态站点框架 |
| `classic-hexo` / `classic-hexo-abbrlink` / `classic-vuepress` | 经典格式（description + keywords + sidebarDepth），已用真实线上文章逐字核对 |

除 `classic-*` 外，预设按各主题官方文档的 front matter 约定编写。**接入前请用一篇已发布文章核对一次**；不一致就在设置页覆盖 `fields` 等选项，或在 [`app/adapters/presets.py`](app/adapters/presets.py) 加一个预设（欢迎 PR）。

## 开发

```sh
.venv/bin/python -m pytest -q    # 114 项；GitHub 与 AI 调用全部模拟，不访问外网
```

代码按 `api → services → adapters / integrations / storage → domain / core` 分层，依赖只能向下，由 `tests/test_architecture.py` 自动检查。改哪里、怎么排障见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。

## 已知限制

- **单用户**工具，没有多账号 / 权限体系。
- 只支持 **GitHub**（源码仓库和 Actions），暂不支持 GitLab / Gitea。
- 图片不做转存：飞书 / 公众号图片要先换成图床链接。
- AI 提示词针对**中文内容和国内搜索引擎**（百度）调优；英文博客可在 `app/integrations/claude.py` 里改提示词。
- 界面目前只有中文。
- 手机窄屏（约 390px）下顶部导航文字会换行，功能可用，排版待优化。

## License

[MIT](LICENSE)
