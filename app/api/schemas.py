"""请求体定义。响应直接返回 dict / 领域模型。"""
from pydantic import BaseModel

from ..domain.post import Post


class LoginIn(BaseModel):
    password: str


class SetupIn(BaseModel):
    code: str
    password: str


class PasswordIn(BaseModel):
    current: str
    new: str


class SecretsIn(BaseModel):
    """None = 不改；"" = 清除。"""

    github_token: str | None = None
    anthropic_api_key: str | None = None
    anthropic_model: str | None = None
    ai_provider: str | None = None
    ai_base_url: str | None = None


class AITestIn(BaseModel):
    """「测试连接」：不填的项用已保存的值。"""

    provider: str | None = None
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None


class BlogIn(BaseModel):
    """category_dirs / options 在页面上是 YAML 文本，由 services/config.py 解析校验。"""

    id: str
    name: str
    repo: str
    branch: str = "main"
    posts_dir: str
    filename: str = "{slug}.md"
    adapter: str
    post_url: str = ""
    category_dirs_yaml: str = ""
    default_category_dir: str = ""
    options_yaml: str = ""
    token: str | None = None  # 博客专用 GitHub Token：None = 不改，"" = 清除（改用全局）


class EnrichIn(BaseModel):
    body: str
    title: str = ""  # 作者定的标题，AI 不改；空着就用正文开头的「# 标题」


class PublishIn(BaseModel):
    post: Post
    blog_ids: list[str]
    overwrite: bool = False
    paths: dict[str, str] = {}  # 博客 id → 已有文章路径（编辑老文章时写回原文件）


class ArticlePathIn(BaseModel):
    path: str


class RetryIn(BaseModel):
    blog_ids: list[str]
    overwrite: bool = False
