# 架构设计

> 目标：加功能时知道往哪放，出问题时 1 分钟内定位到文件。
> 分层规则由 `tests/test_architecture.py` 自动检查，**放错层测试会失败**。

## 1. 分层与依赖方向

```
            ┌──────────────────────────────┐
  浏览器 ──▶ │ static/   前端（html/css/js） │
            └──────────────┬───────────────┘
                           │ HTTP /api/*
            ┌──────────────▼───────────────┐
            │ api/      路由、请求体、登录/CSRF │  ← 唯一能 import fastapi/starlette 的层
            └──────────────┬───────────────┘
            ┌──────────────▼───────────────┐
            │ services/ 业务流程              │  ← 发布、重发、状态、登录判定
            └───┬──────────┬──────────┬────┘
     ┌──────────▼──┐ ┌─────▼──────┐ ┌─▼──────────┐
     │ adapters/   │ │integrations│ │ storage/   │
     │ md 格式转换  │ │ GitHub/Claude│ │ SQLite 历史 │
     │ 纯函数无 IO  │ │ 外部 HTTP   │ │            │
     └──────┬──────┘ └─────┬──────┘ └─────┬──────┘
            └──────────────┼──────────────┘
            ┌──────────────▼───────────────┐
            │ domain/  Post 等数据模型与校验   │
            │ core/    配置、错误、密码、日志    │
            └──────────────────────────────┘
  main.py：只做组装（创建实例、挂路由、中间件、错误处理），不写业务
```

**依赖只能向下**。允许关系（`tests/test_architecture.py` 里的 `ALLOWED`）：

| 层 | 可以依赖 |
|---|---|
| `core` / `domain` | 无（最底层） |
| `adapters` | `domain` |
| `integrations` / `storage` | `core`、`domain` |
| `services` | `core`、`domain`、`adapters`、`integrations`、`storage` |
| `api` | `core`、`domain`、`integrations`、`services` |

## 2. 目录与职责

```
app/
  main.py                    组装入口：create_app() / app_from_env()
  core/
    config.py                Settings（环境变量）、BlogConfig、load_blogs()
    errors.py                业务异常：BadRequest / Unauthorized / Forbidden / NotFound / Conflict / TooManyRequests / UpstreamError
    security.py              scrypt 密码哈希、登录限速
    logging.py               日志格式
  domain/
    post.py                  Post（文章+校验）、Rendered（渲染结果）、PostMetadata（AI 建议）
  adapters/                  Post → 某框架的 md 文本
    __init__.py              get_adapter(预设名, options)、preset_list()
    presets.py               主题预设：classic-*（经典格式）、hexo/butterfly/next/fluid/icarus、vuepress-hope、vitepress、hugo、jekyll、astro、docusaurus
    markdown.py              唯一的渲染器：按 options 输出 front matter（fields/date_format/empty…）和处理正文（H1、more）
    base.py                  yaml_scalar（必要时才加引号）、段落切分
  integrations/
    github.py                Contents API 读写文件、查询 Actions 运行
    claude.py                Anthropic 格式（官方或兼容中转，base_url 显式传入）：元数据补全 + 测试连接；提示词在这里
    openai_compat.py         OpenAI 兼容格式（/chat/completions，DeepSeek、Kimi、OpenRouter、聚合中转）
  storage/
    publish_store.py         发布记录与各博客结果（SQLite）
    config_store.py          设置页保存的键值（密码哈希、Token、Key、模型）和博客列表（同一个 SQLite）
  services/
    publisher.py             预览、发布、重发、状态、历史；单博客失败隔离
    config.py                首次初始化、登录判定 + 限速、改密码、密钥（只回传末 4 位）、博客增删改查与连接自检、按博客取 GitHub 客户端
    articles.py              「文章」页：列出仓库里的已发布文章、载入（parse）、删除（与放行名单同一提交）
    allowlist.py             SEO 守门放行名单：删除 / 编辑改了正文时登记页面（文件名 + abbrlink）
    ai.py                    AI 补全：按「设置 → AI 接口」选格式，统一错误说明；测试连接
  api/
    deps.py                  从 app.state 取服务、require_login（会话 + CSRF）
    schemas.py               请求体模型
    auth.py                  /api/setup /api/login /api/logout /api/password /api/me
    config.py                /api/config（设置页：密钥、博客增删改查、检查连接）
    articles.py              /api/blogs/{id}/articles（列出 / 载入 / 删除已发布文章）
    posts.py                 /api/enrich /preview /publish /publish/{id}/retry /status/{id} /history
  static/
    index.html  style.css  app.js     单页前端，无构建链
  hashpw.py                  命令行：生成密码哈希
tests/
  conftest.py                公共夹具：FakeGitHub（内存版 GitHub）、publisher、client、login()
  adapters/                  适配器格式测试，含完整文章逐字对照
  fixtures/                  对照用的文章（vuepress：source.md 输入 / expected.md 期望输出）
  services/                  业务流程测试（不经 HTTP）
  api/                       接口测试（登录、CSRF、错误格式、完整发布流程）
  test_architecture.py       分层规则检查
workflows/                   博客源码仓库的 Actions 例子 + SEO 守门脚本 compare_site.py
deploy/                      nginx 示例、服务器运维脚本
```

## 3. 改什么去哪里

| 要做的事 | 改哪里 | 还要动 |
|---|---|---|
| 某个博客 front matter 字段不对 | 先在设置页该博客的「覆盖预设」里改 `fields` / `date_format`；所有用这个主题的人都该改的，改 `adapters/presets.py` | `tests/adapters/test_markdown.py` |
| `<!-- more -->` 位置不对 | 覆盖预设里的 `more_marker` / `more_after_paragraphs`；切段逻辑在 `adapters/base.py:split_blocks` | `tests/adapters/test_markdown.py` |
| 编辑老文章时 front matter 被改动 | `adapters/markdown.py:update`（只改动过的字段，其余原样保留）；`parse` 是 `render` 的反向 | `tests/adapters/test_markdown.py`、`test_vuepress.py` 的 round trip |
| 删除 / 编辑文章被 SEO 守门拦下 | 博客仓库 `.github/allowed-removals.txt`；Postflow 写入逻辑在 `services/allowlist.py`（删除：`articles.py:delete`，编辑：`publisher.py:_publish_one`） | `tests/api/test_articles.py`、`tests/test_compare_site.py` |
| 新增一个博客（已有框架） | `blogs.yml` 加一段 | 新源码仓库 + `workflows/` 加一份 |
| 新增一个主题 / 框架 | `adapters/presets.py` 加一项（照抄最接近的）；正文处理方式不同才改 `markdown.py` | `test_markdown.py` 自动覆盖所有预设能出合法 YAML |
| 文件名 / 文章 URL 规则 | `blogs.yml` 的 `filename`、`post_url`；占位符解析在 `services/publisher.py:format_template` | |
| 文章按分类放子目录（如 VuePress 按目录生成侧边栏） | `blogs.yml` 的 `category_dirs` / `default_category_dir`，`filename` 里用 `{category_dir}` | |
| AI 填的标题/slug/标签不满意 | `integrations/claude.py` 的 `SYSTEM` 提示词；字段增减改 `domain/post.py:PostMetadata` | 前端 `app.js` 回填 |
| 新增文章字段（如封面图） | `domain/post.py:Post` → 适配器输出 → `static/index.html` + `app.js` 表单 | 各层测试 |
| 发布流程逻辑（覆盖、重试、并发） | `services/publisher.py` | `tests/services/` |
| 新增接口 | `api/` 对应路由文件 + `api/schemas.py`；业务写在 `services/` | `tests/api/` |
| 新接一个外部服务 | `integrations/` 新文件，出错抛 `UpstreamError` | 在 `services/` 里调用 |
| GitHub Token 选择（博客专用 > 全局） | `services/config.py:ConfigService.github(blog)`；专用 Token 存 settings 表 `blog_token:<id>` | `tests/api/test_config.py` |
| 登录、会话、CSRF、首次初始化 | `services/config.py`、`core/security.py`、`api/deps.py` | `tests/api/test_auth.py`、`test_config.py` |
| 粘贴富文本转 Markdown 不对 | `static/html2md.js`（htmlToMarkdown / looksRich），粘贴处理在 `static/app.js` 的 paste 监听 | 在浏览器里用飞书 / 公众号 / 网页的真实复制内容验证 |
| AI 补全 / 中转站 | `services/ai.py` → `integrations/claude.py` 或 `openai_compat.py` | `tests/integrations/test_ai_providers.py` |
| 页面样式 / 交互 | `static/style.css` / `static/app.js`；登录页背景动画在 `static/fx.js`（canvas，系统开了「减少动态效果」不启动） | |
| 帮助抽屉（教程、快捷键、常见问题） | `static/index.html` 的 `#dlgHelp` | |
| 环境变量 | `core/config.py:get_settings` | `.env.example` 同步 |

## 4. 排障地图

所有接口错误统一返回 `{"detail": "中文说明", "code": "错误码"}`。日志 logger 名以 `postflow.` 开头。

| 现象 | 错误码 / 日志关键字 | 先看 |
|---|---|---|
| 页面一直弹登录 | `unauthorized` | `.env` 的 `POSTFLOW_COOKIE_SECURE`（本地 http 要 false）；`api/deps.py` |
| 提示 CSRF 校验失败 | `forbidden` | 会话过期或开了多个标签页登录，刷新页面；`api/deps.py:require_login` |
| 登录被锁 | `rate_limited` | 15 分钟后自动解锁，重启服务也会清零；`core/security.py` |
| AI 填写失败 | `upstream_error`，日志 `postflow.posts enrich failed` | `ANTHROPIC_API_KEY`、模型名；`integrations/claude.py` |
| 某博客发布失败 | 结果里的 `error`，日志 `publish #<id> <blog> ... failed` | `GitHub 401` → token 失效；`404` → 仓库名/分支/PAT 授权范围；`409/422` → sha 冲突，重发即可 |
| 提示目标文件已存在 | `conflict` | 预期行为，勾选「覆盖」或在历史页重发 |
| 提交成功但站点没更新 | 状态里 Actions `conclusion: failure` | 点 Actions 链接看构建日志；问题在源码仓库或 workflow，不在本服务 |
| 状态里没有 Actions 运行 | `runs` 为空 | workflow 是否已放进仓库、触发分支是否为 `main`、PAT 是否有 Actions 只读 |
| 启动时报「未知 adapter」 | `ValueError` | `adapter` 填的预设名不存在，可选值见 `adapters/presets.py`（别名 `vuepress` = `classic-vuepress`） |
| 格式和手工发布的不一致 | — | 拿一篇已发布文章对照，在设置页覆盖预设或改适配器，并补对照测试（放进 `tests/fixtures/`） |

## 5. 约定

- **错误**：`services`/`integrations`/`core` 只抛 `core/errors.py` 里的异常，不碰 `HTTPException`；`main.py` 统一转成 HTTP 响应。新错误类型在 `errors.py` 加子类，定好 `status` 和 `code`。
- **单博客隔离**：`Publisher._publish_one` 捕获全部异常写进结果，一个博客出问题不影响其他博客。新增的发布步骤也放在这个 try 里。
- **日志**：用 `logging.getLogger("postflow.<模块>")`；发布日志带 `#<发布id> <blog_id>`，方便按一次发布串起来查。日志里不打 token、密码、正文全文。
- **测试**：改哪层就在 `tests/` 同名目录加测试；外部服务一律用 `FakeGitHub` / monkeypatch 模拟，测试不访问外网。提交前 `pytest -q` 全绿。
- **配置**：博客相关的放 `blogs.yml`（不入库，模板 `blogs.example.yml`）；密钥放 `.env`（不入库，模板 `.env.example`）。
- **不加没用的抽象**：没有第二个实现之前不建接口/基类（适配器例外，因为已有两个框架）。
