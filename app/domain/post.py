import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

# 文件名安全的字符：字母、数字、中文，用单个 - 或 _ 连接。新文章推荐小写英文 + 连字符；老文章里有中文、下划线的照样能编辑重发
SLUG_RE = re.compile(r"^[0-9A-Za-z\u4e00-\u9fff]+(?:[-_][0-9A-Za-z\u4e00-\u9fff]+)*$")


class Post(BaseModel):
    title: str
    slug: str
    date: datetime | None = None  # 新文章必填（发布时检查）；部分老文章没有日期，编辑时保持没有
    tags: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    description: str = ""
    keywords: list[str] = Field(default_factory=list)
    cover: str = ""  # 封面图 URL，主题用得上才输出（butterfly cover、fluid index_img、hugo image…）
    body: str

    @field_validator("title", "body")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("不能为空")
        return v

    @field_validator("slug")
    @classmethod
    def valid_slug(cls, v: str) -> str:
        if not SLUG_RE.match(v):
            raise ValueError("slug 只能用字母、数字、中文，用 - 或 _ 连接（推荐小写英文，如 claude-code-tips）")
        return v


class Rendered(BaseModel):
    blog_id: str
    path: str
    content: str


class SeoSuggestion(BaseModel):
    """AI 只生成这三项；标题由作者定、AI 不改。slug 是提炼标题核心主题的英文词（domain/seo.py 再把关格式）。"""

    slug: str
    description: str
    keywords: list[str]
