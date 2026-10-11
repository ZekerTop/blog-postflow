#!/usr/bin/env python3
"""影子构建比对：新构建产物 vs 线上站点，守住 SEO / GEO。只用标准库，在博客仓库的 Actions 里运行。

用法：python3 compare_site.py <线上目录> <新构建目录> [放行名单文件]
  放行名单（如 .github/allowed-removals.txt）：故意删除或修改正文的页面写在这里就不阻断。每行一条，# 开头为注释；
  按路径结尾匹配、可用通配符，如 `postflow-test.html`、`postflow-test/index.html`、`blog/old/*.html`。
  Postflow 删除 / 编辑文章时会自动追加；手动删改文章时自己加一行。
  复制到博客源码仓库的 .github/scripts/compare_site.py

阻断（退出码 1，不部署）：
  - 线上有、新构建没有的页面（老链接会 404）
  - 线上有、新构建没有的其他文件：图片、站长验证文件（BingSiteAuth.xml 等）、feed……
    带内容 hash 的 js/css 及其 .LICENSE.txt（每次构建都换名）和 .DS_Store 之类系统垃圾文件除外
  - sitemap 里消失的 URL
  - CNAME / robots.txt / ads.txt 变化或丢失
  - 已有页面的正文变化（只比正文容器里的 HTML，见 BODY_CONTAINERS；渲染器、插件、主题升级改了老文章就会被拦下）
提醒（不阻断，写进报告）：
  - 已有页面的 title、description、keywords、canonical、robots、og:*、JSON-LD、h1 变化
  - 已有页面的可见文字变化（如侧边栏顺序、正文改动；忽略 script/style）
  - 新增页面、其他文件变化
报告写到 $GITHUB_STEP_SUMMARY（Actions 运行页面可见），没有就打到标准输出。
"""
from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

GUARDED = ("CNAME", "robots.txt", "ads.txt")
HASHED = re.compile(r"[.-][0-9A-Za-z_]{8,}\.(js|css|map|mjs)(\.LICENSE\.txt)?$")  # 构建工具给静态资源加的内容 hash
JUNK = {".DS_Store", "Thumbs.db", "desktop.ini",  # 系统垃圾文件，消失是好事
        ".nojekyll"}  # 部署时由 actions-gh-pages 自动加到线上，构建产物里本来就没有
SKIP_DIRS = {".git", ".github"}
# 正文容器：(标签, 属性, 值)，标签为 None 表示不限；页面里恰好出现一次才比（首页、列表页有多个摘要，跳过）
BODY_CONTAINERS = (
    (None, "id", "article-container"),        # Hexo Butterfly
    (None, "class", "theme-default-content"),  # VuePress 默认主题
    ("article", "class", "article"),           # Hexo Icarus
)


class SeoParser(HTMLParser):
    """抽出影响收录和引用的字段，忽略正文和带 hash 的静态资源。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.fields: dict[str, str] = {}
        self._capture: str | None = None
        self._buf: list[str] = []
        self._h1_done = False

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if tag == "title" and "title" not in self.fields:
            self._capture, self._buf = "title", []
        elif tag == "h1" and not self._h1_done:
            self._capture, self._buf = "h1", []
        elif tag == "script" and a.get("type") == "application/ld+json":
            self._capture, self._buf = "ld+json", []
        elif tag == "meta":
            key = a.get("name") or a.get("property")
            if key and (key in ("description", "keywords", "robots") or key.startswith("og:")):
                self.fields[f"meta:{key}"] = norm(a.get("content", ""))
        elif tag == "link" and "canonical" in a.get("rel", "").split():
            self.fields["canonical"] = a.get("href", "")

    def handle_data(self, data):
        if self._capture:
            self._buf.append(data)

    def handle_endtag(self, tag):
        if self._capture and tag in ("title", "h1", "script"):
            text = norm("".join(self._buf))
            if self._capture == "ld+json":
                self.fields["ld+json"] = (self.fields.get("ld+json", "") + " " + text).strip()
            else:
                self.fields[self._capture] = text
                self._h1_done = self._h1_done or self._capture == "h1"
            self._capture = None


class BodyParser(HTMLParser):
    """取正文容器里的 HTML（标签 + 属性 + 文字，空白归一）；找不到或出现多次时 body 为 None。
    标签按解析后的属性重新拼，实体写法不同（如 marked 每次随机编码 mailto 地址）不算变化。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.found: dict[int, list[str]] = {}  # 容器序号 → 每次出现的内容
        self._open: list[tuple[int, str, int, list[str]]] = []  # (容器序号, 标签, 同名标签深度, 缓冲)

    def handle_starttag(self, tag, attrs):
        for o in self._open:
            o[3].append(tag_text(tag, attrs))
        self._open = [(i, t, d + (t == tag), buf) for i, t, d, buf in self._open]
        a = {k: (v or "") for k, v in attrs}
        for i, (want, attr, value) in enumerate(BODY_CONTAINERS):
            hit = a.get(attr) == value if attr == "id" else value in a.get(attr, "").split()
            if hit and (want is None or want == tag):
                self._open.append((i, tag, 1, []))

    def handle_startendtag(self, tag, attrs):
        for o in self._open:
            o[3].append(tag_text(tag, attrs, "/"))

    def handle_endtag(self, tag):
        still = []
        for i, t, d, buf in self._open:
            d -= t == tag
            if d == 0:
                self.found.setdefault(i, []).append(norm("".join(buf)))
            else:
                buf.append(f"</{tag}>")
                still.append((i, t, d, buf))
        self._open = still

    def handle_data(self, data):
        for o in self._open:
            o[3].append(data)

    @property
    def body(self) -> str | None:
        for i in sorted(self.found):
            return self.found[i][0] if len(self.found[i]) == 1 else None
        return None


def tag_text(tag: str, attrs: list, close: str = "") -> str:
    return "<" + tag + "".join(f' {k}="{v}"' if v is not None else f" {k}" for k, v in attrs) + close + ">"


def body_html(path: Path) -> str | None:
    p = BodyParser()
    p.feed(path.read_text(encoding="utf-8", errors="replace"))
    return p.body


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def visible_text(path: Path) -> str:
    s = path.read_text(encoding="utf-8", errors="replace")
    s = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", s, flags=re.S | re.I)
    return norm(re.sub(r"<[^>]+>", " ", s))


def seo_fields(path: Path) -> dict[str, str]:
    p = SeoParser()
    p.feed(path.read_text(encoding="utf-8", errors="replace"))
    return p.fields


def files(root: Path) -> dict[str, Path]:
    out = {}
    for p in root.rglob("*"):
        if p.is_file() and p.name not in JUNK and not SKIP_DIRS & set(p.relative_to(root).parts):
            out[p.relative_to(root).as_posix()] = p
    return out


def sitemap_urls(root: Path) -> set[str]:
    urls = set()
    for p in root.glob("sitemap*.xml"):
        urls |= set(re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", p.read_text(encoding="utf-8", errors="replace")))
    return urls


def digest(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load_allowed(path: Path | None) -> list[str]:
    if not path or not path.exists():
        return []
    lines = (ln.strip() for ln in path.read_text(encoding="utf-8").splitlines())
    return [ln.lstrip("/") for ln in lines if ln and not ln.startswith("#")]


def is_allowed(path: str, allowed: list[str]) -> bool:
    """path 是站点内相对路径或 URL；规则匹配整个路径或路径结尾（以 / 分隔）。"""
    path = re.sub(r"^https?://[^/]+/", "", path).lstrip("/")
    return any(fnmatch.fnmatch(path, a) or fnmatch.fnmatch(path, "*/" + a) for a in allowed)


def compare(live: Path, new: Path, allowed: list[str] | None = None) -> dict:
    allowed = allowed or []
    lf, nf = files(live), files(new)
    lp = {k for k in lf if k.endswith(".html")}
    np_ = {k for k in nf if k.endswith(".html")}
    r = {
        "removed_pages": sorted(lp - np_),
        "added_pages": sorted(np_ - lp),
        "removed_files": sorted(k for k in set(lf) - set(nf) if not k.endswith(".html") and not HASHED.search(k)),
        "removed_sitemap_urls": sorted(sitemap_urls(live) - sitemap_urls(new)),
        "guarded_changed": [],
        "seo_changed": [],
        "body_changed": [],
        "text_changed": [],
        "other_changed": 0,
        "live_pages": len(lp),
        "new_pages": len(np_),
    }
    for name in GUARDED:
        a, b = lf.get(name), nf.get(name)
        if a and b and digest(a) != digest(b):
            r["guarded_changed"].append(f"{name}（内容变化）")
    for k in sorted(lp & np_):
        a, b = seo_fields(lf[k]), seo_fields(nf[k])
        diff = {f: (a.get(f, ""), b.get(f, "")) for f in sorted(set(a) | set(b)) if a.get(f, "") != b.get(f, "")}
        if diff:
            r["seo_changed"].append({"page": k, "fields": diff})
        old_body = None if k.rsplit("/", 1)[-1] == "404.html" else body_html(lf[k])  # 404 页不收录，VuePress 还会随机换提示语
        if old_body is not None and old_body != body_html(nf[k]):
            r["body_changed"].append(k)
        if visible_text(lf[k]) != visible_text(nf[k]):
            r["text_changed"].append(k)
    r["other_changed"] = sum(1 for k in set(lf) & set(nf) if not k.endswith(".html") and k not in GUARDED
                             and digest(lf[k]) != digest(nf[k]))
    r["allowed_removals"] = []
    for key in ("removed_pages", "removed_files", "removed_sitemap_urls"):
        r["allowed_removals"] += [p for p in r[key] if is_allowed(p, allowed)]
        r[key] = [p for p in r[key] if not is_allowed(p, allowed)]
    r["allowed_changes"] = [p for p in r["body_changed"] if is_allowed(p, allowed)]
    r["body_changed"] = [p for p in r["body_changed"] if not is_allowed(p, allowed)]
    r["blocking"] = bool(r["removed_pages"] or r["removed_files"] or r["removed_sitemap_urls"] or r["guarded_changed"]
                         or r["body_changed"])
    return r


def report(r: dict, limit: int = 30) -> str:
    def lines(items):
        shown = [f"- `{i}`" for i in items[:limit]]
        return "\n".join(shown + ([f"- ……共 {len(items)} 项"] if len(items) > limit else []))

    out = [f"## 影子构建比对：{'❌ 有阻断项，不部署' if r['blocking'] else '✅ 无阻断项'}",
           f"线上 {r['live_pages']} 个页面 · 新构建 {r['new_pages']} 个页面 · "
           f"新增 {len(r['added_pages'])} · 消失页面 {len(r['removed_pages'])} · 消失文件 {len(r['removed_files'])} · "
           f"正文变化 {len(r['body_changed'])} 页 · SEO 字段变化 {len(r['seo_changed'])} 页 · "
           f"可见文字变化 {len(r['text_changed'])} 页 · 其他文件变化 {r['other_changed']}"]
    if r["allowed_removals"]:
        out += ["### 🗑 按放行名单删除（不阻断）", lines(r["allowed_removals"])]
    if r["removed_pages"]:
        out += ["### ❌ 消失的页面（老链接会 404）", lines(r["removed_pages"])]
    if r["removed_files"]:
        out += ["### ❌ 消失的文件（图片、验证文件、feed 等）", lines(r["removed_files"])]
    if r["removed_sitemap_urls"]:
        out += ["### ❌ sitemap 里消失的 URL", lines(r["removed_sitemap_urls"])]
    if r["allowed_changes"]:
        out += ["### ✏️ 按放行名单修改正文（不阻断）", lines(r["allowed_changes"])]
    if r["guarded_changed"]:
        out += ["### ❌ 关键文件变化", lines(r["guarded_changed"])]
    if r["body_changed"]:
        out += ["### ❌ 老页面的正文变了（多半是渲染器 / 插件 / 主题变化；是你主动改的就把页面路径加进放行名单）",
                lines(r["body_changed"])]
    if r["seo_changed"]:
        out.append("### ⚠️ 已有页面的 SEO 字段变化（不阻断，请确认）")
        for c in r["seo_changed"][:limit]:
            out.append(f"- `{c['page']}`")
            out += [f"  - {f}：`{a[:80]}` → `{b[:80]}`" for f, (a, b) in c["fields"].items()]
        if len(r["seo_changed"]) > limit:
            out.append(f"- ……共 {len(r['seo_changed'])} 页")
    if r["text_changed"]:
        out += ["### ⚠️ 可见文字变化的页面（不阻断；大面积变化多半是侧边栏 / 导航顺序变了）", lines(r["text_changed"])]
    if r["added_pages"]:
        out += ["### 新增页面", lines(r["added_pages"])]
    return "\n\n".join(out) + "\n"


def main(argv: list[str]) -> int:
    if len(argv) not in (3, 4):
        print(__doc__)
        return 2
    r = compare(Path(argv[1]), Path(argv[2]), load_allowed(Path(argv[3]) if len(argv) == 4 else None))
    text = report(r)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(text)
    print(text)
    Path("compare-report.json").write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    return 1 if r["blocking"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
