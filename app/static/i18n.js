// 界面语言（中文 / English）。中文原文就是 key：英文表里查不到就原样显示中文，所以漏翻不会坏页面。
// 静态页面：apply() 遍历文本节点和 placeholder / title / aria-label，按原文替换；切回中文时还原。
// 动态文案：app.js 里用 t("中文 {变量}", { 变量 })。后端返回的中文报错也走 t()（下面的 PATTERNS 处理带变量的）。
// 帮助抽屉是整段说明，直接写了两份（data-lang="zh" / "en"），按 <html lang> 显示其一。
window.i18n = (() => {
  const EN = {
    // 登录 / 首次设置
    "欢迎回来": "Welcome back",
    "输入密码，继续发布。": "Enter your password to continue.",
    "密码": "Password",
    "显示密码": "Show password",
    "隐藏密码": "Hide password",
    "大写锁定已开启": "Caps Lock is on",
    "进入工作台": "Enter",
    "设置登录密码": "Set a login password",
    "首次使用。初始化码在服务启动日志里，也写在服务器的": "First run. The setup code is in the server log and in",
    "。": ".",
    "初始化码": "Setup code",
    "新密码": "New password",
    "至少 8 位": "at least 8 characters",
    "再输一次": "Confirm password",
    "完成设置并进入": "Save and enter",
    "一次粘贴，发布到所有博客": "Paste once, publish to every blog",
    "AI 生成英文网址、描述与关键词": "AI drafts the slug, description and keywords",
    "提交即部署，GitHub Actions 接力": "Commit, and GitHub Actions deploys it",
    "请输入密码": "Enter your password",
    "密码至少 8 位": "Password must be at least 8 characters",
    "两次输入的密码不一致": "Passwords don't match",
    "密码已设置": "Password set",
    "退出登录？": "Log out?",
    "草稿会保留在这个浏览器里。": "Your draft stays in this browser.",
    "退出": "Log out",
    "登录已过期，请重新登录": "Session expired, please log in again",
    "请求失败（{status}）": "Request failed ({status})",

    // 顶栏
    "写作": "Write",
    "文章": "Posts",
    "历史": "History",
    "设置": "Settings",
    "使用教程与常见问题（?）": "Guide and FAQ (?)",
    "帮助": "Help",
    "切换主题": "Switch theme",
    "退出登录": "Log out",
    "跟随系统": "System",
    "亮色": "Light",
    "暗色": "Dark",
    "主题：跟随系统": "Theme: System",
    "主题：{name}（点击切换）": "Theme: {name} (click to switch)",
    "主题：{name}": "Theme: {name}",

    // 写作页
    "发布结果": "Publish result",
    "自动刷新中": "Auto-refreshing",
    "刷新状态": "Refresh",
    "收起": "Close",
    "正在编辑": "Editing a published post on",
    "上的已发布文章": "·",
    "发布会写回原文件，只改你动过的部分": "Publishing writes back to the original file and changes only what you edited",
    "之后发布当作新文章": "Publish as a new post from now on",
    "取消关联": "Unlink",
    "正文": "Body",
    "字 · 约": "chars · ~",
    "分钟 ·": "min ·",
    "清空，开始新文章": "Clear and start a new post",
    "新文章": "New",
    "导入 .md 文件（也可以直接拖进来）": "Import a .md file (or drag it in)",
    "导入": "Import",
    "AI 生成网址、描述、关键词": "AI: slug & SEO",
    "粘贴文章：飞书文档、公众号后台、网页复制的内容会自动转成 Markdown（⌘⇧V 按纯文本粘贴）；也可以把 .md 文件拖进来…":
      "Paste your post: rich text copied from Feishu, WeChat or any web page is converted to Markdown (⌘⇧V pastes plain text). You can also drop a .md file here…",
    "松开即可导入 Markdown 文件": "Drop to import the Markdown file",
    "元数据": "Metadata",
    "标题": "Title",
    "文章网址的一部分": "part of the post URL",
    "点「AI 生成」按标题提炼英文网址": "Click “AI” to derive an English slug from the title",
    "没有 AI 时：按标题转拼音": "Without AI: convert the title to pinyin",
    "按标题转拼音": "Convert title to pinyin",
    "发布时间": "Publish date",
    "分类": "Categories",
    "标签": "Tags",
    "逗号分隔": "comma-separated",
    "关键词": "Keywords",
    "逗号分隔，15–30 个，核心词放前面": "comma-separated, 15–30, core terms first",
    "描述": "Description",
    "搜索结果里的摘要": "the snippet shown in search results",
    "封面图": "Cover image",
    "可选，主题支持才输出": "optional, only output if the theme supports it",
    "发布到": "Publish to",
    "管理博客": "Manage blogs",
    "还没有博客。": "No blogs yet.",
    "去添加 →": "Add one →",
    "目标文件已存在时覆盖": "Overwrite if the file already exists",
    "预览": "Preview",
    "发布": "Publish",
    "草稿已保存 {time}": "Draft saved {time}",
    "已恢复上次的草稿": "Restored your last draft",
    "已转成 Markdown · ⌘Z 撤销 · ⌘⇧V 粘贴纯文本": "Converted to Markdown · ⌘Z to undo · ⌘⇧V for plain text",
    "；{n} 张图片发布前要换成图床链接（飞书需登录 / 公众号防盗链）":
      "; {n} image(s) must be replaced with hosted URLs before publishing (Feishu needs login / WeChat blocks hotlinking)",
    "这里有一张粘贴进来的本地图片，请上传到图床后替换成链接": "A local image was pasted here. Upload it to an image host and replace this with its URL",
    "只能用字母、数字、中文，用 - 或 _ 连接（不能有空格和其他符号）": "Letters, digits or Chinese only, joined by - or _ (no spaces or other symbols)",
    "已发布文章的网址不能改（改了老链接会 404）": "A published post's URL can't change (old links would 404)",
    "可以用，但推荐小写英文 + 连字符，网址更干净": "Valid, but lowercase English with hyphens makes a cleaner URL",
    "点「AI 生成」按标题提炼英文主题词，如 {eg}": "Click “AI” to turn the title into English keywords, e.g. {eg}",
    "已发布文章的网址不能改，改了老链接会 404": "A published post's URL can't change; old links would 404",
    "{n} 字 · 建议 100–130 字（第一句讲事实，第二句写读者会搜的问题）": "{n} chars · aim for 100–130 (first sentence: the fact; second: the question readers search for)",
    "（偏长）": " (long)",
    "（偏短）": " (short)",
    "建议 100–130 字：第一句讲事实，第二句写读者会搜的问题": "Aim for 100–130 chars: first sentence the fact, second the question readers search for",
    "开始新文章？": "Start a new post?",
    "当前正文和元数据会被清空，草稿也会删除。": "The body and metadata will be cleared and the draft deleted.",
    "清空": "Clear",
    "只支持 .md / .markdown / .txt": "Only .md / .markdown / .txt files are supported",
    "导入「{name}」？": "Import “{name}”?",
    "会替换当前正文。": "This replaces the current body.",
    "替换": "Replace",
    "已导入 {name}": "Imported {name}",
    "先粘贴正文": "Paste the body first",
    "已生成网址、描述、关键词；标题没改": "Slug, description and keywords generated; title unchanged",
    "还没填：{list}": "Missing: {list}",
    "Slug 格式不对": "Invalid slug",
    "至少选一个博客": "Select at least one blog",
    "已存在，将覆盖": "Exists, will overwrite",
    "已存在，需打开覆盖": "Exists, turn on overwrite",
    "无法检查是否已存在": "Couldn't check whether it exists",
    "新文件": "New file",
    "编辑原文件 · 只改动过的部分": "Editing original · changed parts only",
    "{n} 个博客 · 未提交，只是看看": "{n} blog(s) · nothing committed yet",
    "发布这篇文章？": "Publish this post?",
    "「{title}」将提交到 {names}，提交后各仓库会自动构建部署。": "“{title}” will be committed to {names}. Each repo then builds and deploys automatically.",
    "已提交，等待构建": "Committed, waiting for the build",
    "{n} 个失败，见发布结果": "{n} failed, see the publish result",
    "已部署": "Deployed",
    "排队中": "Queued",
    "构建中": "Building",
    "已提交": "Committed",
    "失败": "Failed",
    "Actions 未开始": "Actions not started",
    "提交 {sha}": "Commit {sha}",

    // 文章页
    "直接读取博客仓库里的全部文章（包括以前用别的方式发的）。编辑会写回原文件、只改你动过的部分；删除会同时登记 SEO 守门的放行名单。":
      "Lists every post in the blog repo, including ones published some other way. Editing writes back to the original file and changes only what you edited; deleting also adds the page to the SEO guard's allowlist.",
    "选择博客": "Choose a blog",
    "搜索文件名或目录": "Search file names or folders",
    "重新读取仓库": "Reload from the repo",
    "还没有博客，先去「设置」添加": "No blogs yet. Add one in Settings first",
    "正在读取仓库…": "Reading the repo…",
    "{shown} / {total} 篇": "{shown} / {total} posts",
    "查看": "View",
    "编辑": "Edit",
    "删除": "Delete",
    "没有匹配的文章": "No matching posts",
    "这个博客的文章目录里还没有文章": "This blog's posts folder is empty",
    "载入这篇文章？": "Load this post?",
    "会替换写作页里当前的内容（当前草稿不会保留）。": "This replaces what's on the Write page (the current draft won't be kept).",
    "载入": "Load",
    "已载入，改完点发布会写回原文件": "Loaded. Publishing will write back to the original file",
    "删除这篇文章？": "Delete this post?",
    "将从「{blog}」仓库删除 {path}，并登记到放行名单；约 2 分钟后线上页面消失。已被搜索引擎收录的链接会变成 404，能改就尽量别删。":
      "{path} will be deleted from the “{blog}” repo and added to the allowlist; the live page disappears in about 2 minutes. Indexed links will 404, so prefer editing over deleting.",
    "已删除，约 2 分钟后从线上消失": "Deleted. It will disappear from the live site in about 2 minutes",
    "已取消关联，之后发布当作新文章": "Unlinked. Publishing now creates a new post",

    // 历史页
    "发布历史": "Publish history",
    "最近 50 次。失败的可以重发，后来新加的博客可以补发，也可以载入编辑后再发。":
      "Last 50 publishes. Retry failed ones, publish to blogs added later, or load one to edit and publish again.",
    "搜索标题或 slug": "Search title or slug",
    "重发失败的": "Retry failed",
    "补发 {n} 个": "Publish to {n} more",
    "载入编辑": "Load to edit",
    "查看状态": "Status",
    "没有匹配的记录": "No matching records",
    "还没有发布记录": "Nothing published yet",
    "载入「{title}」？": "Load “{title}”?",
    "会替换编辑器里当前的内容。": "This replaces what's in the editor.",
    "已载入，发布会写回原文件": "Loaded. Publishing will write back to the original file",
    "已载入，修改后可重新发布（同 slug 需打开覆盖）": "Loaded. Edit and publish again (same slug needs overwrite on)",
    "发布到 {names}？": "Publish to {names}?",
    "用当时保存的文章内容重新生成并提交。": "Regenerates and commits the post as it was saved then.",

    // 设置页
    "只存在服务器本地数据库；密钥页面上只显示末 4 位。": "Stored only in the server's local database; secrets show only their last 4 characters.",
    "博客": "Blogs",
    "每个博客一个源码仓库，主题预设决定生成的 Markdown 格式。": "One source repo per blog. The theme preset decides the generated Markdown format.",
    "添加博客": "Add blog",
    "全局默认 Token；博客仓库在别的 GitHub 账号时，在该博客里填专用 Token。留空 = 不修改。":
      "Default token for all blogs. If a blog's repo is under another GitHub account, give that blog its own token. Leave empty to keep the current one.",
    "fine-grained PAT：Contents 读写 + Actions 只读": "Fine-grained PAT: Contents read/write + Actions read-only",
    "清除": "Clear",
    "保存": "Save",
    "AI 接口": "AI provider",
    "用于「AI 生成网址、描述、关键词」。官方和中转站都可以；先「测试连接」，通过了再保存。":
      "Used by “AI: slug & SEO”. Official APIs and relays both work; run “Test connection” before saving.",
    "接口格式": "API format",
    "接口地址": "Base URL",
    "留空 = 不修改": "Leave empty to keep the current one",
    "模型": "Model",
    "测试连接": "Test connection",
    "登录密码": "Login password",
    "当前密码": "Current password",
    "修改密码": "Change password",
    "已设置 {hint}": "Set {hint}",
    " · 环境变量": " · env var",
    "未设置": "Not set",
    "已设置": "set",
    "中转站": "Relay",
    "官方": "Official",
    "已配置": "Configured",
    "未配置": "Not configured",
    "这个博客用自己的 GitHub Token": "This blog uses its own GitHub token",
    "专用 Token {hint}": "Own token {hint}",
    "检查连接": "Check",
    "还没有博客，点右上角「添加博客」": "No blogs yet. Click “Add blog” above",
    "删除「{name}」？": "Delete “{name}”?",
    "只删除这里的配置，不会动 GitHub 仓库；历史记录保留。": "Only the settings here are removed. The GitHub repo is untouched and history is kept.",
    "已删除": "Deleted",
    "连接正常": "OK",
    "有问题": "Problem",
    "编辑「{name}」": "Edit “{name}”",
    "保存后改用全局 Token": "Will use the global token after saving",
    "已保存": "Saved",
    "先填 Token": "Enter a token first",
    "留空 = 官方 api.anthropic.com；中转站填它给的地址": "empty = official api.anthropic.com; for a relay, use the URL it gives you",
    "必填，一般到 /v1，如 https://api.deepseek.com/v1": "required, usually ends in /v1, e.g. https://api.deepseek.com/v1",
    "正在测试…": "Testing…",
    "✓ 连接正常：{model} 回复「{reply}」，用时 {s} 秒": "✓ Connected: {model} replied “{reply}” in {s}s",
    "先填模型名": "Enter a model name first",
    "清除 {label}？": "Clear {label}?",
    "清除页面里保存的值；若环境变量里也有，会改用环境变量的。": "Clears the value saved here. If an environment variable is also set, that one takes over.",
    "已清除": "Cleared",
    "新密码至少 8 位": "New password must be at least 8 characters",
    "密码已修改，其他设备需要重新登录": "Password changed. Other devices will need to log in again",

    // 弹窗
    "关闭": "Close",
    "确认发布": "Publish",
    "取消": "Cancel",
    "确定": "OK",
    "主题预设": "Theme preset",
    "决定 front matter 字段和正文处理": "decides front matter fields and body handling",
    "显示名": "Display name",
    "保存后不能改": "can't change after saving",
    "源码仓库": "Source repo",
    "分支": "Branch",
    "测试用 postflow-test 不触发部署": "use postflow-test to try without deploying",
    "文章目录": "Posts folder",
    "文件名": "File name",
    "专用 GitHub Token": "Blog-specific GitHub token",
    "仓库在别的 GitHub 账号时填；留空 = 用全局 Token": "for repos under another GitHub account; empty = use the global token",
    "这个账号的 fine-grained PAT：该仓库 Contents 读写 + Actions 只读": "Fine-grained PAT for that account: Contents read/write + Actions read-only on this repo",
    "改用全局": "Use global",
    "高级：文章链接、分类目录、覆盖预设": "Advanced: post URL, category folders, preset overrides",
    "文章链接模板": "Post URL template",
    "可选，发布后显示链接": "optional, shows a link after publishing",
    "分类 → 子目录": "Category → subfolder",
    "每行「分类: 目录」": "one “category: folder” per line",
    "默认子目录": "Default subfolder",
    "文件名里用了 {category_dir} 时必填": "required when the file name uses {category_dir}",
    "覆盖预设（YAML）": "Preset overrides (YAML)",
    "如 date_format、fields": "e.g. date_format, fields",
    "占位符：{slug} {year} {month} {day} {category_dir}": "Placeholders: {slug} {year} {month} {day} {category_dir}",
    "快速上手": "Quick start",
    "快捷键": "Shortcuts",
    "常见问题": "FAQ",

    // 后端传来的标签（主题预设、AI 接口格式）
    "Anthropic 格式（官方或兼容中转）": "Anthropic format (official or compatible relay)",
    "OpenAI 兼容格式（DeepSeek、Kimi、OpenRouter、聚合中转）": "OpenAI-compatible (DeepSeek, Kimi, OpenRouter, aggregators)",
    "经典 · Hexo（无 H1，空字段保留）": "Classic · Hexo (no H1, keeps empty fields)",
    "经典 · Hexo + abbrlink（含 H1、keywords、cover）": "Classic · Hexo + abbrlink (H1, keywords, cover)",
    "经典 · VuePress 默认主题（含 H1、keywords）": "Classic · VuePress default theme (H1, keywords)",
    "Hexo · 通用（landscape 等）": "Hexo · generic (landscape etc.)",
    "Hugo（PaperMod / Stack 等）": "Hugo (PaperMod / Stack etc.)",
    "Jekyll（minima / Chirpy 等）": "Jekyll (minima / Chirpy etc.)",
    "Astro · 官方 blog 模板": "Astro · official blog template",

    // 后端报错（固定文字）
    "未登录": "Not logged in",
    "密码已修改，请重新登录": "Password changed, please log in again",
    "CSRF 校验失败，请刷新页面": "CSRF check failed, please reload the page",
    "失败次数过多，15 分钟后再试": "Too many failed attempts, try again in 15 minutes",
    "已初始化过，请直接登录": "Already set up, please log in",
    "初始化码不对（看服务启动日志或 data/setup-code.txt）": "Wrong setup code (see the server log or data/setup-code.txt)",
    "还没设置密码，请先初始化": "No password yet, finish setup first",
    "密码错误": "Wrong password",
    "密码由环境变量 POSTFLOW_PASSWORD_HASH 管理，请改 .env": "The password is managed by POSTFLOW_PASSWORD_HASH; change it in .env",
    "当前密码错误": "Current password is wrong",
    "接口地址要以 http:// 或 https:// 开头": "The base URL must start with http:// or https://",
    "接口地址不能是本机或内网地址（安全限制，防止借此访问服务器内网服务）": "The base URL can't be localhost or a private address (blocked so it can't reach the server's internal services)",
    "OpenAI 兼容格式必须填接口地址，如 https://api.deepseek.com/v1": "The OpenAI-compatible format needs a base URL, e.g. https://api.deepseek.com/v1",
    "仓库文件太多，GitHub 返回的列表被截断了": "The repo has too many files; GitHub truncated the listing",
    "Token 无效或已过期": "token invalid or expired",
    "Token 无权访问": "token has no access",
    "仓库不存在，或 Token 没授权这个仓库": "repo not found, or the token isn't granted this repo",
    "Token 对这个仓库没有写权限（需要 Contents: Read and write）": "The token can't write to this repo (needs Contents: Read and write)",
    "还没配置 AI API Key：去「设置 → AI 接口」填写，或手动填写元数据": "No AI API key yet. Add one in Settings → AI provider, or fill in the metadata by hand",
    "正文为空": "The body is empty",
    "先填标题：网址、描述和关键词都围绕标题生成": "Enter the title first: the slug, description and keywords are built from it",
    "还没填发布时间": "Publish date is missing",
    "目标文件已存在，勾选「覆盖」后重发": "The file already exists; turn on “overwrite” and retry",
    "不能为空": "can't be empty",
    "id 只能用字母、数字、- 和 _": "id may only use letters, digits, - and _",
    "仓库格式应为 owner/name": "repo should look like owner/name",
    "slug 只能用字母、数字、中文，用 - 或 _ 连接（推荐小写英文，如 claude-code-tips）": "slug may only use letters, digits or Chinese joined by - or _ (lowercase English recommended, e.g. claude-code-tips)",
    "文件名用了 {category_dir}，必须填「默认目录」": "The file name uses {category_dir}, so “Default subfolder” is required",
    "fields 应为「字段名: 取值」形式": "fields should be “name: value” pairs",
    "keywords_style 只能是 comma 或 list": "keywords_style must be comma or list",
    "empty 只能是 omit 或 keep": "empty must be omit or keep",
    "Key 无效或已过期": "key invalid or expired",
    "Key 没有权限": "key lacks permission",
    "接口地址或模型名不对": "wrong base URL or model name",
    "额度用完或被限流": "out of quota or rate limited",
    "AI 拒绝了这次请求，请手动填写": "The AI refused this request; fill it in by hand",
    "分类目录映射": "Category folders",
    "适配器选项": "Preset overrides",

    // 列表拼接
    "、": ", ",
    "；": "; ",
  };

  // 后端带变量的报错：[正则, 英文模板]；英文模板里 $1… 是捕获组，{t:n} 表示把第 n 组再翻译一次
  const PATTERNS = [
    [/^Value error, ([\s\S]+)$/, "{t:1}"],
    [/^GitHub (\d+)：([\s\S]+)$/, "GitHub $1: {t:2}"],
    [/^(\d+) (Key .+|额度.+|接口地址或模型名不对)$/, "$1 {t:2}"],
    [/^接口返回 (\d+)$/, "The API returned $1"],
    [/^连不上接口地址（(.+)）$/, "Can't reach the base URL ($1)"],
    [/^AI 补全失败：(.+)，请检查「设置 → AI 接口」或手动填写$/, "AI generation failed: {t:1}. Check Settings → AI provider or fill it in by hand"],
    [/^AI 接口 (\d+)：([\s\S]*)$/, "AI API $1: $2"],
    [/^AI 未返回结果（(.+)），请手动填写$/, "The AI returned nothing ($1); fill it in by hand"],
    [/^AI 返回的不是有效的 JSON（(.+)），请手动填写或换个模型$/, "The AI didn't return valid JSON ($1); fill it in by hand or try another model"],
    [/^接口地址的域名解析失败：(.+)$/, "Couldn't resolve the base URL's host: $1"],
    [/^文件不存在：(.+)$/, "File not found: $1"],
    [/^分支 (.+) 不存在$/, "Branch $1 doesn't exist"],
    [/^目录 (.+) 在分支 (.+) 上不存在$/, "Folder $1 doesn't exist on branch $2"],
    [/^fields\.(\w+)：未知取值 (\S+)，可用 (.+)$/, "fields.$1: unknown value $2; available: $3"],
    [/^(.+) 不是合法的 YAML：([\s\S]+)$/, "{t:1} is not valid YAML: $2"],
    [/^(.+) 应为「键: 值」形式$/, "{t:1} should be “key: value” pairs"],
    [/^密码至少 (\d+) 位$/, "Password must be at least $1 characters"],
    [/^未知配置项：(.+)$/, "Unknown setting: $1"],
    [/^未知接口格式：(.+)$/, "Unknown API format: $1"],
    [/^「(.+)」没有可用的 GitHub Token：.+$/, "“$1” has no GitHub token: add a global one in Settings, or a blog-specific one for this blog"],
    [/^id「(.+)」已存在$/, "id “$1” already exists"],
    [/^博客「(.+)」不存在$/, "Blog “$1” not found"],
    [/^未知博客：(.+)$/, "Unknown blog: $1"],
    [/^发布记录 #(\d+) 不存在$/, "Publish record #$1 not found"],
    [/^路径不在「(.+)」的文章目录 (.+) 下：(.+)$/, "Path is outside “$1”'s posts folder $2: $3"],
    [/^([\w.]+)：([\s\S]+)$/, "$1: {t:2}"],  // 表单校验：「字段：原因」
  ];

  const CJK = /[　-〿一-鿿＀-￯]/;
  let lang = "zh";
  try { lang = localStorage.getItem("pf-lang") || ""; } catch {}
  if (lang !== "zh" && lang !== "en") lang = /^zh/i.test(navigator.language || "") ? "zh" : "en";

  function english(s) {
    if (s in EN) return EN[s];
    if (s.includes("；")) return s.split("；").map(english).join("; ");  // 多条报错拼在一起的
    for (const [re, tpl] of PATTERNS) {
      const m = s.match(re);
      if (m) return tpl.replace(/\{t:(\d)\}/g, (_, i) => english(m[i])).replace(/\$(\d)/g, (_, i) => m[i] ?? "");
    }
    return s;
  }

  function t(s, vars) {
    let out = lang === "en" ? english(String(s)) : String(s);
    if (vars) out = out.replace(/\{(\w+)\}/g, (m, k) => (k in vars ? vars[k] : m));
    return out;
  }

  // 静态页面：记住每个节点的中文原文，切换时总是从原文翻译 / 还原
  const origText = new WeakMap(), origAttr = new WeakMap();
  const ATTRS = ["placeholder", "title", "aria-label"];
  const OFF = "[data-lang], [data-i18n=off]";  // 帮助正文（两份）、用户内容区不碰
  const skipText = el => el.closest(`${OFF}, script, style, textarea, pre, code`);

  function apply(root = document.body) {
    document.documentElement.lang = lang === "en" ? "en" : "zh-CN";
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      if (!n.parentElement || skipText(n.parentElement)) continue;
      if (!origText.has(n)) { if (!CJK.test(n.nodeValue)) continue; origText.set(n, n.nodeValue); }
      const o = origText.get(n), key = o.trim();
      n.nodeValue = o.replace(key, t(key));
    }
    root.querySelectorAll(ATTRS.map(a => `[${a}]`).join(",")).forEach(el => {
      if (el.closest(OFF)) return;
      let saved = origAttr.get(el);
      if (!saved) {
        saved = Object.fromEntries(ATTRS.filter(a => CJK.test(el.getAttribute(a) || "")).map(a => [a, el.getAttribute(a)]));
        if (!Object.keys(saved).length) return;
        origAttr.set(el, saved);
      }
      for (const [a, v] of Object.entries(saved)) el.setAttribute(a, t(v));
    });
  }

  return {
    t, apply,
    get lang() { return lang; },
    set(next) { lang = next; try { localStorage.setItem("pf-lang", next); } catch {} apply(); },
  };
})();
const t = i18n.t;
i18n.apply();
