// Hexo 的 updated（文章「更新于」、sitemap lastmod、article:modified_time）取文件修改时间（_config.yml: updated_option: 'mtime'），
// git checkout 后全是同一时刻。迁移前的文章和独立页面用线上页面里的原时间（mtimes.json，毫秒精度），迁移后改过或新发的用最后一次提交时间。
const fs = require('fs')
const { execSync } = require('child_process')
const map = fs.existsSync(`${__dirname}/mtimes.json`) ? require('./mtimes.json') : {}   // 没有就全部用提交时间
const sh = c => execSync(c).toString().trim()
const MIGRATED = Number(process.env.MIGRATED_AT || sh('git log --reverse --format=%ct').split('\n')[0] || 0)
const posts = fs.readdirSync('source/_posts').filter(n => n.endsWith('.md')).map(n => `source/_posts/${n}`)
let kept = 0, fromGit = 0
for (const f of new Set([...Object.keys(map), ...posts])) {
  if (!fs.existsSync(f)) continue
  const git = Number(sh(`git log -1 --format=%ct -- "${f}"`) || 0)
  const useGit = git > MIGRATED || !map[f]
  const t = useGit ? git : map[f]   // 秒，可带毫秒小数
  if (!t) continue
  fs.utimesSync(f, t, t)
  useGit ? fromGit++ : kept++
}
console.log(`mtime: ${kept} 个沿用迁移前时间，${fromGit} 个用提交时间`)
