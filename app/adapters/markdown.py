"""通用 Markdown 适配器：front matter 字段、日期格式、正文处理全部由 options 描述，换主题只改配置不改代码。

options（都可选，预设见 presets.py）:
  fields:        有序的「输出字段名 → 取值」。取值写 $title / $slug / $date / $description /
                 $keywords / $tags / $categories / $cover 引用文章元数据；其他为固定值，
                 字符串里可用 {slug} {year} {month} {day} 占位符
  date_format:   strftime 格式，默认 "%Y-%m-%d %H:%M:%S"（文章时间按北京时间，带时区的格式自己写 +08:00）
  keywords_style: comma（逗号拼接成一个字符串，默认）| list
  empty:         omit（空值不输出，默认）| keep（空列表写 []，空字符串写空值）
  h1:            正文前加 "# 标题"（默认 false）
  strip_leading_h1: 去掉正文开头已有的 H1（默认 false）
  demote_h1:     正文里还有 H1（公众号 / 飞书常把小节标题设成一级）时，全部标题降一级，一页只留文章标题一个 H1
                 （默认 true；只作用于新生成的文章，编辑老文章不动）
  remove_more:   删掉正文里的 more_marker
  more_marker / more_after_paragraphs: 正文里没有截断标记时，在第 N 段（默认 2）后插入
  extra_front_matter: 追加的固定字段（兼容旧配置，等同写进 fields）
"""
import json
import re
from datetime import datetime
from typing import Any

import yaml

from ..domain.post import Post
from .base import Adapter, split_blocks, yaml_scalar

LEADING_H1 = re.compile(r"^\s*#\s+.*?(?:\r?\n)+")
ATX_HEADING = re.compile(r"^( {0,3})(#{1,6})(?=[ \t]|$)")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
FRONT_MATTER = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n?", re.S)
LIST_SOURCES = ("tags", "categories", "keywords")
SOURCES = {"title", "slug", "date", "description", "keywords", "tags", "categories", "cover"}
DEFAULT_FIELDS = {"title": "$title", "date": "$date", "tags": "$tags", "categories": "$categories",
                  "description": "$description", "keywords": "$keywords"}


def validate_options(o: dict[str, Any]) -> None:
    """配置保存时调用，错误尽早暴露给「设置」页。"""
    fields = o.get("fields", {})
    if not isinstance(fields, dict):
        raise ValueError("fields 应为「字段名: 取值」形式")
    for key, src in fields.items():
        if isinstance(src, str) and src.startswith("$") and src[1:] not in SOURCES:
            raise ValueError(f"fields.{key}：未知取值 {src}，可用 {', '.join('$' + s for s in sorted(SOURCES))}")
    if o.get("keywords_style", "comma") not in ("comma", "list"):
        raise ValueError("keywords_style 只能是 comma 或 list")
    if o.get("empty", "omit") not in ("omit", "keep"):
        raise ValueError("empty 只能是 omit 或 keep")


class MarkdownAdapter(Adapter):
    def render(self, post: Post) -> str:
        o = self.options
        fields = dict(o.get("fields") or DEFAULT_FIELDS)
        fields.update(o.get("extra_front_matter") or {})
        lines = ["---"]
        for key, src in fields.items():
            lines += self._field(key, self._value(src, post))
        lines.append("---")
        head = "\n".join(lines) + "\n\n"
        if o.get("h1"):
            head += f"# {post.title}\n\n"
        body = self._body(post)
        return head + (demote_headings(body) if o.get("demote_h1", True) else body)

    def _value(self, src: Any, post: Post) -> Any:
        if not isinstance(src, str):
            return src
        if src.startswith("$") and src[1:] in SOURCES:
            name = src[1:]
            if name == "date":
                return Raw(post.date.strftime(self.options.get("date_format", "%Y-%m-%d %H:%M:%S"))) if post.date else ""
            if name == "keywords" and self.options.get("keywords_style", "comma") == "comma":
                return ",".join(post.keywords)
            return getattr(post, name)
        d = post.date
        return src.format(slug=post.slug, year=f"{d.year:04d}" if d else "", month=f"{d.month:02d}" if d else "",
                          day=f"{d.day:02d}" if d else "")

    def _field(self, key: str, value: Any) -> list[str]:
        keep = self.options.get("empty", "omit") == "keep"
        if isinstance(value, list):
            if not value:
                return [f"{key}: []"] if keep else []
            return [f"{key}:"] + [f"- {scalar(v)}" for v in value]
        if value in ("", None):
            return [f"{key}: "] if keep else []
        return [f"{key}: {scalar(value)}"]

    def _body(self, post: Post) -> str:
        o = self.options
        body = post.body
        if o.get("strip_leading_h1"):
            body = LEADING_H1.sub("", body, count=1)
        marker = o.get("more_marker") or "<!-- more -->"
        if o.get("remove_more"):
            body = body.replace(marker, "")
        elif o.get("more_marker") and marker not in body:
            blocks = split_blocks(body)
            n = int(o.get("more_after_paragraphs", 2))
            if len(blocks) > n:
                blocks.insert(n, marker)
                body = "\n\n".join(blocks) + "\n"
        return body.lstrip()


    def update(self, original: str, post: Post) -> str:
        """编辑已发布文章：只改动过的字段，其余（含 Postflow 不认识的自定义字段、字段顺序、引号写法）原样保留；
        正文没改就保留原文。不改任何东西时输出与原文逐字相同。"""
        m = FRONT_MATTER.match(original)
        if not m:
            return self.render(post)
        o, old = self.options, self.parse(original)
        nl = "\r\n" if "\r\n" in original[:m.end()] else "\n"
        blocks = fm_blocks(m.group(1).splitlines())
        fields = dict(o.get("fields") or DEFAULT_FIELDS)
        fields.update(o.get("extra_front_matter") or {})
        title_changed = False
        for key, src in fields.items():
            if not (isinstance(src, str) and src.startswith("$")) or src[1:] == "slug":
                continue  # 固定值字段不碰：原文有就保留，没有也不加
            name = src[1:]
            if self._same(name, old.get(name), post):
                continue
            title_changed |= name == "title"
            lines = self._field(key, self._value(src, post))
            idx = next((i for i, (k, _) in enumerate(blocks) if k == key), None)
            if idx is None:
                blocks.append((key, lines))
            else:
                blocks[idx] = (key, lines)
        head = "---" + nl + nl.join(ln for _, b in blocks for ln in b) + nl + "---" + nl
        tail, old_body = original[m.end():], old["body"]
        if not tail.endswith(old_body):  # 解析不出正文起点（极少见）：按模板重建正文
            return head + nl + (f"# {post.title}{nl}{nl}" if o.get("h1") else "") + self._body(post)
        prefix = tail[:len(tail) - len(old_body)]  # front matter 之后、正文之前：空行和生成的「# 标题」，原样保留
        if title_changed and o.get("h1"):  # 「# 标题」原本等于旧标题才跟着改；手写的不同 H1 不碰
            old_title = (old.get("title") or "").strip()
            prefix = re.sub(r"^(\s*)#\s+(.*)", lambda x: f"{x.group(1)}# {post.title}"
                            if x.group(2).strip() == old_title else x.group(0), prefix, count=1)
        return head + prefix + post.body

    def _same(self, name: str, old: Any, post: Post) -> bool:
        new = getattr(post, name)
        if name == "date":
            fmt = self.options.get("date_format", "%Y-%m-%d %H:%M:%S")
            return (old.strftime(fmt) if old else "") == (new.strftime(fmt) if new else "")
        if name in LIST_SOURCES:
            return list(old or []) == list(new or [])
        return (old or "") == (new or "")

    def parse(self, text: str) -> dict[str, Any]:
        o = self.options
        m = FRONT_MATTER.match(text)
        fm = (yaml.safe_load(m.group(1)) or {}) if m else {}
        if not isinstance(fm, dict):
            fm = {}
        body = text[m.end():] if m else text
        out: dict[str, Any] = {}
        fields = dict(o.get("fields") or DEFAULT_FIELDS)
        for key, src in fields.items():
            if not (isinstance(src, str) and src.startswith("$")) or key not in fm or src[1:] in out:
                continue
            name, v = src[1:], fm[key]
            if name in ("tags", "categories", "keywords"):
                v = [str(x).strip() for x in (v if isinstance(v, list) else str(v or "").split(",")) if str(x).strip()]
            elif name == "date":
                v = to_datetime(v)
                if v is None:
                    continue
            elif name == "slug":
                continue
            else:
                v = "" if v is None else str(v)
            out[name] = v
        if o.get("h1"):
            body = LEADING_H1.sub("", body.lstrip(), count=1)
        out["body"] = body.lstrip("\r\n")
        return out


def demote_headings(body: str) -> str:
    """正文里有 H1 就把所有 # 标题降一级（H6 不再降），层级关系不变；代码块里的 # 不算。没有 H1 原样返回。"""
    lines = body.split("\n")
    heads, fence = [], None
    for i, ln in enumerate(lines):
        m = FENCE.match(ln)
        if m and (fence is None or (m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence))):
            fence = m.group(1) if fence is None else None
        elif fence is None and (h := ATX_HEADING.match(ln)):
            heads.append((i, h))
    if not any(len(h.group(2)) == 1 for _, h in heads):
        return body
    for i, h in heads:
        lines[i] = h.group(1) + "#" * min(len(h.group(2)) + 1, 6) + lines[i][h.end():]
    return "\n".join(lines)


def fm_blocks(lines: list[str]) -> list[tuple[str | None, list[str]]]:
    """front matter 按顶层字段切块：(字段名, 原始行)。缩进行、列表项、注释归到上一个字段。"""
    blocks: list[tuple[str | None, list[str]]] = []
    for ln in lines:
        top = re.match(r"^([^\s#\-][^:]*):(\s|$)", ln)
        if top:
            blocks.append((top.group(1).strip(), [ln]))
        elif blocks:
            blocks[-1][1].append(ln)
        else:
            blocks.append((None, [ln]))
    return blocks


def to_datetime(v: Any) -> datetime | None:
    if isinstance(v, datetime):
        return v.replace(tzinfo=None)
    if hasattr(v, "year"):  # date
        return datetime(v.year, v.month, v.day)
    s = str(v or "").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M", "%Y/%m/%d"):
        try:
            return datetime.strptime(s[:19], fmt)
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(s).replace(tzinfo=None)
    except ValueError:
        return None


class Raw(str):
    """原样输出、不加引号（日期）。"""


def scalar(v: Any) -> str:
    if isinstance(v, Raw):
        return str(v)
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, dict):
        return json.dumps(v, ensure_ascii=False)
    return yaml_scalar(str(v))
