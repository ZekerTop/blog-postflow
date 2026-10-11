// 文章、标签、分类按 Windows 上最后一次构建的入库顺序排列（.github/scripts/windows-order.json，取自当时的 db.json）。
// 入库顺序决定同分相关推荐、同日文章、标签云、文章标签的先后；不固定的话每次构建都可能变，和线上对不上。
// 新文章 / 新标签不在名单里，排在最后。
'use strict'
const order = require('../.github/scripts/windows-order.json')

// 优先级 1：要排在 Hexo 自带的 render_post（10）之前，文章按这个顺序渲染，标题锚点的去重编号才和线上一致
hexo.extend.filter.register('before_generate', function () {
  const Post = this.model('Post'), Tag = this.model('Tag'), Category = this.model('Category')
  const post = id => (Post.findById(id) || {}).source
  const tag = id => (Tag.findById(id) || {}).name
  const cat = id => {
    const parts = []
    for (let c = Category.findById(id); c; c = c.parent && Category.findById(c.parent)) parts.unshift(c.name)
    return parts.join('/')
  }
  const keys = {
    Post: d => d.source,
    Tag: d => d.name,
    Category: d => cat(d._id),
    PostTag: d => post(d.post_id) + '|' + tag(d.tag_id),
    PostCategory: d => post(d.post_id) + '|' + cat(d.category_id)
  }
  for (const [name, key] of Object.entries(keys)) {
    const model = this.model(name)
    const rank = new Map(order[name].map((k, i) => [k, i]))
    const ids = Object.keys(model.data).filter(id => model.data[id])
    const pos = id => { const r = rank.get(key(model.findById(id))); return r === undefined ? Infinity : r }
    const sorted = ids.map((id, i) => [id, pos(id), i]).sort((a, b) => a[1] - b[1] || a[2] - b[2]).map(x => x[0])
    const data = {}
    for (const id of sorted) data[id] = model.data[id]
    model.data = data
  }
  this.locals.invalidate()
}, 1)
