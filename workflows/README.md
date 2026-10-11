# 博客源码仓库的 GitHub Actions

Postflow 只负责「生成 md 并提交到博客源码仓库」，构建和部署交给源码仓库里的 GitHub Actions。这里是三个可直接改用的例子，和一个**SEO 守门**脚本。

| 文件 | 适用场景 | 放到博客源码仓库的哪里 | 需要的 Secrets / Variables |
|---|---|---|---|
| `examples/vuepress-github-pages.yml` | VuePress 2 → 另一个仓库的 GitHub Pages | `.github/workflows/deploy.yml` | Secret `DEPLOY_KEY`（线上仓库 Deploy key 的私钥，允许写）；确认后加 Variable `DEPLOY_ENABLED=true` |
| `examples/hexo-github-pages.yml` | Hexo → 另一个仓库的 GitHub Pages | 同上 | 同上 |
| `examples/hexo-own-server.yml` | Hexo → 自己的服务器（git 裸仓库 + 钩子） | 同上 | Secret `DEPLOY_KEY`（只能 git 推拉的受限密钥）、`SERVER_HOST`（如 `git@1.2.3.4` 里 `@` 后面的部分）、`SERVER_KNOWN_HOSTS`；确认后加 `DEPLOY_ENABLED=true` |
| `compare_site.py` | 所有例子都用 | `.github/scripts/compare_site.py` | — |
| `helpers/restore-mtimes.js` | Hexo 用 `updated_option: mtime` 时，恢复文章修改时间 | `.github/scripts/`（可选配套 `mtimes.json`） | — |
| `helpers/windows-order.js` | 从 Windows 本地构建迁移的 Hexo 站点：固定文章 / 标签入库顺序 | `scripts/`（Hexo 自动加载），配套 `.github/scripts/windows-order.json` | — |
| `helpers/normalize-eol.py` | 从 Windows 本地 `hexo d` 迁移：构建产物 CRLF → LF | `.github/scripts/` | — |

例子里的 `<owner>`、`example.com` 都要换成你自己的。`helpers/` 只在**从本地手动部署迁移、要求新构建与线上逐字节一致**时才需要；全新站点直接删掉 workflow 里对应的步骤。

## 影子模式：不伤 SEO 的切换方式

把一个已经在线上跑了很久的博客改成 Actions 部署，最怕的是：构建环境一变（Linux 与 Windows、大小写、文件顺序、时区、换行符），老页面的 URL、正文、SEO 字段悄悄变了，搜索排名跟着掉。所以例子默认是**只构建、不部署**：

1. 构建后拉取线上站点，用 `compare_site.py` 逐页比对，报告在 Actions 运行页的 **Summary**，构建产物可下载（保留 7 天）。
2. **阻断项**（运行变红，不部署）：
   - 线上有而新构建没有的页面或文件（含站长验证文件、图片；带 hash 的 js/css 除外）
   - sitemap 里消失的 URL
   - `CNAME` / `robots.txt` / `ads.txt` 内容变化
   - **老页面正文变化**（只比正文容器：Butterfly `#article-container`、VuePress `.theme-default-content`、Icarus `article.article`；页面里恰好一个才比，404 页不比）
3. **提醒项**（不阻断）：已有页面的 title、description、keywords、canonical、robots、og:*、JSON-LD、h1 变化；整页可见文字变化（发新文章时侧边栏 / 导航本来就会变，所以只提醒）。
4. 报告无阻断项、提醒项也确认过 → 仓库 Settings → Secrets and variables → Actions → **Variables** 新建 `DEPLOY_ENABLED` = `true`，再手动 Run workflow 一次，才真正部署。只有 `main` 分支会部署，测试分支手动运行也不部署。
5. 切换后比对**照常运行**：以后哪次构建会让老页面消失或正文变化，就自动拦下不部署。
6. 故意删除或改正文的页面：登记在博客仓库的 `.github/allowed-removals.txt` 就放行。Postflow 删除 / 编辑文章时会自动登记，和改动在同一个提交里。
7. 回滚：删掉 `DEPLOY_ENABLED` 变量即回到只构建；站点本身用原来的本地流程重新部署即可覆盖回去。

## 自己的服务器（hexo-own-server.yml）

- 部署 = 把 `public/` 强推到服务器裸仓库 `master`；服务器 `post-receive` 钩子把内容同步到网站目录，例如：

  ```sh
  #!/bin/sh
  # /home/git/blog.git/hooks/post-receive
  TMP=$(mktemp -d)
  git --git-dir=/home/git/blog.git archive master | tar -x -C "$TMP"
  rsync -a --delete --exclude .user.ini --exclude .well-known "$TMP"/ /var/www/blog/
  rm -rf "$TMP"
  ```

- 线上基准 = 用同一把密钥 clone 裸仓库 `master`（不爬网站）。
- `DEPLOY_KEY` 建议给一个只能执行 git 的用户（`git-shell`），不要用 root。

## 从 Windows 本地构建迁移时要注意的差异

实测下来，要让 Linux 上的 Actions 构建与 Windows 上的本地构建逐字节一致，需要处理：

1. **文件名大小写**：Linux 区分大小写，`_config.butterfly.yml` 与 `_config.Butterfly.yml` 不是同一个文件。
2. **文件修改时间**：`git checkout` 后所有文件是同一时刻，`updated_option: mtime` 的「更新于」、sitemap lastmod 会全变 → `restore-mtimes.js`。
3. **入库顺序**：相关推荐、同日文章、标签云、文章标签顺序、标题锚点编号都依赖它 → `windows-order.js`。
4. **目录读取顺序**：VuePress 按 `readdirSync` 生成侧边栏时，NTFS 与 ext4 的顺序不同，要显式排序。
5. **语言和时区**：`TZ`、`LANG` / `LC_ALL` 与原来的系统一致。
6. **换行符**：Windows 上 git `autocrlf` 推送时把文本转成 LF → `normalize-eol.py`。
7. **git 历史带来的新内容**：有些主题在 git 仓库里构建会多出「Last Updated / Contributors」，不需要就在主题配置里关掉。

每次构建都会变、不算差异的：标签云随机颜色、首页与标签 / 分类页的 sitemap lastmod、`mailto:` 的随机实体编码（比对时按解码后的属性比较）。
