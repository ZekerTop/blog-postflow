"""主题预设：blogs.yml / 设置页里 adapter 填预设名，options 里写的同名项覆盖预设。

classic-* 三个是「经典」格式：description + keywords + sidebarDepth，开头 H1 统一处理，已用真实线上文章逐字核对过。
其余按各主题官方文档的 front matter 约定写，接入前用该博客的一篇已发布文章核对一次。
新主题：照抄最接近的一个，改 fields 即可；只有正文处理方式也不同时才需要改 markdown.py。
"""
from typing import Any

CLASSIC_FIELDS = {"title": "$title", "date": "$date", "description": "$description"}
CLASSIC_LISTS = {"tags": "$tags", "categories": "$categories"}
HEXO_FIELDS = {"title": "$title", "date": "$date", "tags": "$tags", "categories": "$categories"}

PRESETS: dict[str, dict[str, Any]] = {
    # ---- 经典格式（已用真实线上文章逐字核对） ----
    "classic-hexo": {
        "label": "经典 · Hexo（无 H1，空字段保留）",
        "posts_dir": "source/_posts", "filename": "{slug}.md",
        "options": {"fields": CLASSIC_FIELDS | {"sidebarDepth": 3} | CLASSIC_LISTS,
                    "date_format": "%Y-%m-%d %H:%M", "empty": "keep", "strip_leading_h1": True},
    },
    "classic-hexo-abbrlink": {
        "label": "经典 · Hexo + abbrlink（含 H1、keywords、cover）",
        "posts_dir": "source/_posts", "filename": "{slug}.md",
        "options": {"fields": CLASSIC_FIELDS | {"keywords": "$keywords", "sidebarDepth": 3} | CLASSIC_LISTS
                    | {"abbrlink": "{slug}", "cover": "$cover"},
                    "date_format": "%Y-%m-%d %H:%M", "empty": "keep", "h1": True, "strip_leading_h1": True,
                    "remove_more": True},
    },
    "classic-vuepress": {
        "label": "经典 · VuePress 默认主题（含 H1、keywords）",
        "posts_dir": "docs/blog", "filename": "{category_dir}/{slug}.md",
        "options": {"fields": CLASSIC_FIELDS | {"keywords": "$keywords", "sidebarDepth": 3} | CLASSIC_LISTS,
                    "date_format": "%Y-%m-%d %H:%M", "empty": "keep", "h1": True, "strip_leading_h1": True},
    },
    # ---- Hexo 主题 ----
    "hexo": {
        "label": "Hexo · 通用（landscape 等）",
        "posts_dir": "source/_posts", "filename": "{slug}.md",
        "options": {"fields": HEXO_FIELDS | {"description": "$description", "keywords": "$keywords"}},
    },
    "hexo-butterfly": {
        "label": "Hexo · Butterfly",
        "posts_dir": "source/_posts", "filename": "{slug}.md",
        "options": {"fields": HEXO_FIELDS | {"keywords": "$keywords", "description": "$description", "cover": "$cover"}},
    },
    "hexo-next": {
        "label": "Hexo · NexT",
        "posts_dir": "source/_posts", "filename": "{slug}.md",
        "options": {"fields": HEXO_FIELDS | {"description": "$description", "keywords": "$keywords"},
                    "more_marker": "<!-- more -->", "more_after_paragraphs": 2},
    },
    "hexo-fluid": {
        "label": "Hexo · Fluid",
        "posts_dir": "source/_posts", "filename": "{slug}.md",
        "options": {"fields": HEXO_FIELDS | {"excerpt": "$description", "index_img": "$cover", "banner_img": "$cover"}},
    },
    "hexo-icarus": {
        "label": "Hexo · Icarus",
        "posts_dir": "source/_posts", "filename": "{slug}.md",
        "options": {"fields": HEXO_FIELDS | {"thumbnail": "$cover", "cover": "$cover"},
                    "more_marker": "<!-- more -->", "more_after_paragraphs": 2},
    },
    # ---- 其他框架 ----
    "vuepress-hope": {
        "label": "VuePress · theme-hope",
        "posts_dir": "src/posts", "filename": "{slug}.md",
        "options": {"fields": {"title": "$title", "date": "$date", "category": "$categories", "tag": "$tags",
                               "description": "$description", "cover": "$cover"},
                    "date_format": "%Y-%m-%d", "strip_leading_h1": True},
    },
    "vitepress": {
        "label": "VitePress",
        "posts_dir": "docs/posts", "filename": "{slug}.md",
        "options": {"fields": {"title": "$title", "date": "$date", "description": "$description", "tags": "$tags"},
                    "date_format": "%Y-%m-%d", "h1": True, "strip_leading_h1": True},
    },
    "hugo": {
        "label": "Hugo（PaperMod / Stack 等）",
        "posts_dir": "content/posts", "filename": "{slug}.md",
        "options": {"fields": {"title": "$title", "date": "$date", "draft": False, "slug": "$slug",
                               "description": "$description", "tags": "$tags", "categories": "$categories",
                               "keywords": "$keywords", "image": "$cover"},
                    "date_format": "%Y-%m-%dT%H:%M:%S+08:00", "keywords_style": "list", "strip_leading_h1": True},
    },
    "jekyll": {
        "label": "Jekyll（minima / Chirpy 等）",
        "posts_dir": "_posts", "filename": "{year}-{month}-{day}-{slug}.md",
        "options": {"fields": {"layout": "post", "title": "$title", "date": "$date", "categories": "$categories",
                               "tags": "$tags", "description": "$description", "image": "$cover"},
                    "date_format": "%Y-%m-%d %H:%M:%S +0800", "strip_leading_h1": True},
    },
    "astro": {
        "label": "Astro · 官方 blog 模板",
        "posts_dir": "src/content/blog", "filename": "{slug}.md",
        "options": {"fields": {"title": "$title", "description": "$description", "pubDate": "$date",
                               "heroImage": "$cover", "tags": "$tags"},
                    "date_format": "%Y-%m-%d", "strip_leading_h1": True},
    },
    "docusaurus": {
        "label": "Docusaurus blog",
        "posts_dir": "blog", "filename": "{year}-{month}-{day}-{slug}.md",
        "options": {"fields": {"slug": "$slug", "title": "$title", "date": "$date", "tags": "$tags",
                               "description": "$description", "image": "$cover"},
                    "date_format": "%Y-%m-%dT%H:%M:%S+08:00", "strip_leading_h1": True,
                    "more_marker": "<!-- truncate -->", "more_after_paragraphs": 2},
    },
}

# 早期配置里的名字
ALIASES = {"vuepress": "classic-vuepress"}
