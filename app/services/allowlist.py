"""SEO 守门放行名单：博客仓库的 .github/allowed-removals.txt。

博客仓库 Actions 里的 workflows/compare_site.py 会拦下「老页面消失」和「老页面正文变化」；
名单里有的页面才放行。所以 Postflow 删除文章、或编辑老文章改了正文时，要在同一个提交里登记。
"""
import re
from datetime import date
from pathlib import PurePosixPath

from ..core.config import BlogConfig
from ..integrations.github import GitHub

ALLOW_FILE = ".github/allowed-removals.txt"
ALLOW_HEADER = ("# 故意删除或修改正文的页面：写在这里就不会被 SEO 守门拦下（每行一条，按路径结尾匹配，可用通配符）。\n"
                "# Postflow 删除 / 编辑文章时会自动追加；手动删改文章时自己加一行，如 my-old-post.html\n")
FRONT_MATTER = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n?", re.S)
ABBRLINK = re.compile(r"^abbrlink:\s*['\"]?([\w-]+)['\"]?\s*$", re.M)


def page_entries(path: str, text: str) -> list[str]:
    """文章对应的页面路径结尾：文件名（VuePress、按 slug 的 Hexo），以及 front matter 里的 abbrlink（hexo-abbrlink 插件）。"""
    p = PurePosixPath(path)
    stem = p.parent.name if p.stem.lower() == "index" else p.stem
    names = [stem]
    fm = FRONT_MATTER.match(text or "")
    m = ABBRLINK.search(fm.group(1)) if fm else None
    if m and m.group(1) != stem:
        names.append(m.group(1))
    return [e for n in names for e in (f"{n}.html", f"{n}/index.html")]


def body_of(text: str) -> str:
    return FRONT_MATTER.sub("", text or "", count=1)


async def with_entries(gh: GitHub, blog: BlogConfig, path: str, text: str, verb: str) -> str | None:
    """返回追加了这篇文章页面的名单全文；都已登记过就返回 None（不用改名单）。"""
    try:
        current, _ = await gh.get_file(blog.repo, ALLOW_FILE, blog.branch)
    except Exception:
        current = ALLOW_HEADER
    have = {ln.strip() for ln in current.splitlines()}
    missing = [e for e in page_entries(path, text) if e not in have]
    if not missing:
        return None
    entry = f"# {date.today().isoformat()} Postflow {verb} {path}\n" + "".join(f"{e}\n" for e in missing)
    return current.rstrip("\n") + "\n" + entry
