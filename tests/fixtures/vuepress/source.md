![](https://images.example.com/cover.webp)

**一句话总结**：`blog-postflow` 把「复制粘贴 + 手动部署」变成一次点击。 
写完就发，三个博客同时更新


本文记录我把三个博客迁到 GitHub Actions 的全过程，以及踩过的坑。

如果你也同时维护好几个博客，可以直接照着做。

<!-- more -->

## 为什么不再手动发布

![](https://images.example.com/step-1.png)

以前每发一篇文章都要：改 `source.md`、跑脚本、复制文件、执行 `hexo d`。

![](https://images.example.com/step-2.png)

> 最怕的不是麻烦，而是某一步漏了，线上少一篇文章还不知道。

## 三个博客，三种格式

-   **Hexo + Butterfly**，文章路径用 abbrlink
-   **Hexo + Icarus**，正文里不写 H1
-   **VuePress 默认主题**，按目录生成侧边栏，front matter 带 `sidebarDepth`

| 博客 | 框架 | 部署 |
|---|---|---|
| A | Hexo 5 | 自己的服务器 |
| B | Hexo 7 | GitHub Pages |
| C | VuePress 2 | GitHub Pages |

## 迁移后的流程

```sh
git push origin main   # 剩下的交给 Actions
```

1. 网页里粘贴文章
2. AI 补全 slug、描述、关键词
3. 预览三份 Markdown，确认后发布

更多细节见 [项目说明](https://example.com/postflow)。

## 最后

有问题欢迎提 Issue，**我们下次见！**
