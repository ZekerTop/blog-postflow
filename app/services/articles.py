"""已发布文章管理：列出仓库里的全部文章（含 Postflow 之前用别的方式发的）、载入编辑、删除。

删除和放行名单写在同一个提交里（见 allowlist.py），否则部署会被 SEO 守门拦下。
"""
import logging
from pathlib import PurePosixPath

from ..adapters import get_adapter
from ..core.config import BlogConfig
from ..core.errors import NotFound
from .allowlist import ALLOW_FILE, with_entries
from .config import ConfigService
from .publisher import check_article_path, dir_of

log = logging.getLogger("postflow.articles")


class ArticleService:
    def __init__(self, config: ConfigService):
        self.config = config

    def _blog(self, blog_id: str) -> BlogConfig:
        blog = next((b for b in self.config.blogs() if b.id == blog_id), None)
        if not blog:
            raise NotFound(f"博客「{blog_id}」不存在")
        return blog

    async def list(self, blog_id: str) -> list[dict]:
        blog = self._blog(blog_id)
        root = blog.posts_dir.strip("/") + "/"
        files = await self.config.github(blog).list_files(blog.repo, blog.branch)
        out = []
        posts = (f for f in files if f.startswith(root) and f.endswith(".md")
                 and PurePosixPath(f).name.lower() != "readme.md")  # README.md 是目录首页，不是文章
        for path in sorted(posts):
            stem = PurePosixPath(path).stem
            out.append({"path": path, "slug": stem, "dir": dir_of(blog, path),
                        "url": self._url(blog, path, stem)})
        return out

    async def load(self, blog_id: str, path: str) -> dict:
        blog = self._blog(blog_id)
        check_article_path(blog, path)
        text, _ = await self.config.github(blog).get_file(blog.repo, path, blog.branch)
        fields = get_adapter(blog.adapter, blog.options).parse(text)
        slug = PurePosixPath(path).stem
        if slug.lower() == "index":  # 「目录/index.md」这类，用目录名当 slug
            slug = PurePosixPath(path).parent.name
        return {"post": {"title": "", "tags": [], "categories": [], "description": "", "keywords": [], "cover": ""}
                | fields | {"slug": slug}, "blog_id": blog.id, "path": path}

    async def delete(self, blog_id: str, path: str) -> dict:
        blog = self._blog(blog_id)
        check_article_path(blog, path)
        gh = self.config.github(blog)
        text, _ = await gh.get_file(blog.repo, path, blog.branch)  # 取 abbrlink，用 abbrlink 的 Hexo 博客，页面路径不是文件名
        allow = await with_entries(gh, blog, path, text, "删除")
        res = await gh.commit_files(blog.repo, blog.branch, f"delete post: {path}",
                                    {path: None} | ({ALLOW_FILE: allow} if allow else {}))
        log.info("deleted %s from %s (%s)", path, blog.id, res["commit_sha"][:7])
        return res

    @staticmethod
    def _url(blog: BlogConfig, path: str, slug: str) -> str:
        """只在模板不依赖日期时给链接（列表里没有读 front matter，拿不到日期）。"""
        t = blog.post_url
        if not t or any(k in t for k in ("{year}", "{month}", "{day}")):
            return ""
        return t.format(slug=slug, category_dir=dir_of(blog, path), year="", month="", day="")
