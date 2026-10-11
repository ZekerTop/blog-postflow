"""发布业务：渲染、提交、重发、状态查询。

不依赖 FastAPI；出错抛 core.errors 里的异常。单个博客失败只记录，不影响其他博客。
"""
import asyncio
import logging

from ..adapters import get_adapter
from ..core.config import BlogConfig
from ..core.errors import BadRequest, Conflict, NotFound, UpstreamError
from ..domain.post import Post, Rendered
from ..storage.publish_store import PublishStore
from .allowlist import ALLOW_FILE, body_of, with_entries
from .config import ConfigService

log = logging.getLogger("postflow.publisher")


def category_dir(blog: BlogConfig, post: Post) -> str:
    first = post.categories[0].strip() if post.categories else ""
    return blog.category_dirs.get(first, blog.default_category_dir)


def format_template(template: str, post: Post, blog: BlogConfig | None = None, cat_dir: str | None = None) -> str:
    d = post.date
    if d is None:
        raise BadRequest("还没填发布时间")
    if cat_dir is None:
        cat_dir = category_dir(blog, post) if blog else ""
    return template.format(slug=post.slug, year=f"{d.year:04d}", month=f"{d.month:02d}", day=f"{d.day:02d}",
                           category_dir=cat_dir)


def check_article_path(blog: BlogConfig, path: str) -> str:
    """编辑 / 删除已有文章时传来的路径：必须在文章目录下、是 .md、不能跳出目录。"""
    root = blog.posts_dir.strip("/") + "/"
    if not path.startswith(root) or not path.endswith(".md") or ".." in path.split("/") or "//" in path:
        raise BadRequest(f"路径不在「{blog.name}」的文章目录 {root} 下：{path}")
    return path


def dir_of(blog: BlogConfig, path: str) -> str:
    """文章路径相对文章目录的子目录（用于 {category_dir}）。"""
    rel = path[len(blog.posts_dir.strip("/")) + 1:]
    return rel.rsplit("/", 1)[0] if "/" in rel else ""


class Publisher:
    """博客列表和 GitHub 客户端每次从 ConfigService 取，「设置」页改完立即生效，不用重启。
    每个博客用自己的 GitHub 客户端（各博客的仓库可以在不同账号，Token 各自配置）。"""

    def __init__(self, config: ConfigService, store: PublishStore):
        self.config = config
        self.store = store

    @property
    def blogs(self) -> dict[str, BlogConfig]:
        return {b.id: b for b in self.config.blogs()}

    def pick(self, ids: list[str]) -> list[BlogConfig]:
        if not ids:
            raise BadRequest("至少选一个博客")
        blogs = self.blogs
        unknown = [i for i in ids if i not in blogs]
        if unknown:
            raise BadRequest(f"未知博客：{unknown}")
        return [blogs[i] for i in ids]

    def render(self, blog: BlogConfig, post: Post, path: str | None = None, original: str | None = None) -> Rendered:
        """新文章按文件名模板算路径、整篇生成；编辑已有文章（path + original）写回原文件、只改动过的部分。"""
        adapter = get_adapter(blog.adapter, blog.options)
        if path:
            path = check_article_path(blog, path)
            if original is not None:
                return Rendered(blog_id=blog.id, path=path, content=adapter.update(original, post))
        else:
            path = f"{blog.posts_dir.rstrip('/')}/{format_template(blog.filename, post, blog)}"
        if post.date is None:
            raise BadRequest("还没填发布时间")
        return Rendered(blog_id=blog.id, path=path, content=adapter.render(post))

    async def _existing(self, blog: BlogConfig, path: str | None) -> tuple[str | None, str | None]:
        """编辑已有文章时取原文 (内容, sha)；文件已不在就当新文件。"""
        if not path:
            return None, None
        try:
            return await self.config.github(blog).get_file(blog.repo, check_article_path(blog, path), blog.branch)
        except UpstreamError as e:
            if "文件不存在" in e.message:
                return None, None
            raise

    async def preview(self, post: Post, blog_ids: list[str], paths: dict[str, str] | None = None) -> list[dict]:
        out = []
        paths = paths or {}
        for blog in self.pick(blog_ids):
            path, original = paths.get(blog.id), None
            try:
                original, _ = await self._existing(blog, path)
                r = self.render(blog, post, path, original)
                exists, check_error = (True if original is not None else
                                       bool(await self.config.github(blog).file_sha(blog.repo, r.path, blog.branch))), None
            except BadRequest:
                raise
            except Exception as e:
                r = self.render(blog, post, path)
                exists, check_error = None, str(e)
            out.append(r.model_dump() | {"name": blog.name, "exists": exists, "check_error": check_error,
                                         "editing": blog.id in paths})
        return out

    async def publish(self, post: Post, blog_ids: list[str], overwrite: bool, paths: dict[str, str] | None = None) -> dict:
        targets = self.pick(blog_ids)
        paths = {k: v for k, v in (paths or {}).items() if k in blog_ids}
        for b in targets:  # 先校验路径，免得记了一条无效的发布记录
            if b.id in paths:
                check_article_path(b, paths[b.id])
        # 编辑已有文章的原路径随记录保存，重发时仍写回原文件
        pid = self.store.new_publish(post.model_dump(mode="json") | ({"_paths": paths} if paths else {}))
        await asyncio.gather(*(self._publish_one(pid, b, post, overwrite, paths.get(b.id)) for b in targets))
        return self.store.get(pid)

    async def retry(self, pid: int, blog_ids: list[str], overwrite: bool) -> dict:
        rec = self._record(pid)
        post, paths = Post(**rec["post"]), rec["post"].get("_paths") or {}
        await asyncio.gather(*(self._publish_one(pid, b, post, overwrite, paths.get(b.id)) for b in self.pick(blog_ids)))
        return self.store.get(pid)

    async def status(self, pid: int) -> dict:
        rec = self._record(pid)
        post = Post(**rec["post"])
        blogs = self.blogs
        for res in rec["results"]:
            blog = blogs.get(res["blog_id"])  # blogs.yml 里删掉的博客仍保留历史
            cat = dir_of(blog, res["path"]) if blog and "{category_dir}" in blog.post_url else None
            try:
                res["post_url"] = format_template(blog.post_url, post, blog, cat) if blog and blog.post_url else ""
            except BadRequest:  # 老文章没有日期、链接模板又要日期
                res["post_url"] = ""
            res["runs"] = []
            if res["ok"] and blog:
                try:
                    res["runs"] = await self.config.github(blog).runs_for_commit(blog.repo, res["commit_sha"])
                except Exception as e:
                    res["runs_error"] = str(e)
        return rec

    def history(self) -> list[dict]:
        return self.store.history()

    def _record(self, pid: int) -> dict:
        rec = self.store.get(pid)
        if not rec:
            raise NotFound(f"发布记录 #{pid} 不存在")
        return rec

    async def _publish_one(self, pid: int, blog: BlogConfig, post: Post, overwrite: bool, path: str | None = None) -> None:
        r = self.render(blog, post, path) if not path else Rendered(blog_id=blog.id, path=path, content="")
        try:
            gh = self.config.github(blog)
            if path:
                original, sha = await self._existing(blog, path)
                r = self.render(blog, post, path, original)
            else:
                sha = await gh.file_sha(blog.repo, r.path, blog.branch)
            if sha and not overwrite:
                raise Conflict("目标文件已存在，勾选「覆盖」后重发")
            verb = "update" if sha else "add"
            msg = f"{verb} post: {post.title}"
            # 编辑老文章改了正文：页面登记进放行名单、同一个提交，否则部署时被 SEO 守门当成意外改动拦下
            allow = (await with_entries(gh, blog, r.path, original, "编辑")
                     if path and original is not None and body_of(original) != body_of(r.content) else None)
            if allow:
                res = await gh.commit_files(blog.repo, blog.branch, msg, {r.path: r.content, ALLOW_FILE: allow})
            else:
                res = await gh.put_file(blog.repo, r.path, blog.branch, r.content, msg, sha)
            self.store.save_result(pid, blog.id, r.path, True, res["commit_sha"], res["commit_url"])
            log.info("publish #%s %s -> %s ok %s", pid, blog.id, r.path, res["commit_sha"][:7])
        except Exception as e:
            self.store.save_result(pid, blog.id, r.path, False, error=str(e))
            log.warning("publish #%s %s -> %s failed: %s", pid, blog.id, r.path, e)
