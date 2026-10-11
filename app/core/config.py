import os
import re
import secrets
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator

ROOT = Path(__file__).resolve().parent.parent.parent


class BlogConfig(BaseModel):
    id: str
    name: str
    repo: str
    branch: str = "main"
    posts_dir: str
    filename: str = "{slug}.md"
    adapter: str
    post_url: str = ""  # 如 "https://blog.example.com/{year}/{month}/{day}/{slug}/"，留空则不显示链接
    # {category_dir} 占位符：按文章第一个分类查子目录，查不到用 default_category_dir（如 VuePress 按目录生成侧边栏）
    category_dirs: dict[str, str] = Field(default_factory=dict)
    default_category_dir: str = ""
    options: dict[str, Any] = Field(default_factory=dict)

    @field_validator("id")
    @classmethod
    def valid_id(cls, v: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", v):
            raise ValueError("id 只能用字母、数字、- 和 _")
        return v

    @field_validator("repo")
    @classmethod
    def valid_repo(cls, v: str) -> str:
        if not re.fullmatch(r"[\w.-]+/[\w.-]+", v):
            raise ValueError("仓库格式应为 owner/name")
        return v

    @field_validator("name", "branch", "posts_dir", "filename")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("不能为空")
        return v.strip()


class Settings(BaseModel):
    """启动参数。密码、Token、Key、博客都可以留空，登录后在「设置」页填写（存 SQLite）；环境变量只作兜底。"""

    password_hash: str = ""
    session_secret: str = ""
    github_token: str = ""
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-5-5"
    blogs_file: Path = ROOT / "blogs.yml"
    db_file: Path = ROOT / "data" / "postflow.db"
    cookie_secure: bool = True
    session_days: int = 30
    # 只有来自这些地址的请求才信任 X-Real-IP（nginx 反代 / Docker 网桥）；直连的请求一律用对端地址
    trusted_proxies: list[str] = ["127.0.0.1/32", "::1/128", "172.16.0.0/12"]
    # AI 接口地址默认不允许内网 / 本机地址（防止借「测试连接」探测服务器内网的 Redis、MySQL 等）
    allow_private_ai: bool = False


def load_blogs(path: Path) -> list[BlogConfig]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    blogs = [BlogConfig(**b) for b in data["blogs"]]
    ids = [b.id for b in blogs]
    if len(ids) != len(set(ids)):
        raise ValueError("blogs.yml 中 id 重复")
    return blogs


def ensure_session_secret(settings: Settings) -> str:
    """没配置时自动生成并存在数据库旁边（权限 600），重启后会话不失效。"""
    if settings.session_secret:
        return settings.session_secret
    f = settings.db_file.parent / "session_secret"
    if not f.exists():
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(secrets.token_urlsafe(48))
        f.chmod(0o600)
    return f.read_text().strip()


@lru_cache
def get_settings() -> Settings:
    env = os.environ
    return Settings(
        password_hash=env.get("POSTFLOW_PASSWORD_HASH", ""),
        session_secret=env.get("POSTFLOW_SESSION_SECRET", ""),
        github_token=env.get("GITHUB_TOKEN", ""),
        anthropic_api_key=env.get("ANTHROPIC_API_KEY", ""),
        anthropic_model=env.get("ANTHROPIC_MODEL", "claude-opus-5-5"),
        blogs_file=Path(env.get("POSTFLOW_BLOGS_FILE", ROOT / "blogs.yml")),
        db_file=Path(env.get("POSTFLOW_DB_FILE", ROOT / "data" / "postflow.db")),
        cookie_secure=env.get("POSTFLOW_COOKIE_SECURE", "true").lower() != "false",
        **({"trusted_proxies": [x.strip() for x in env["POSTFLOW_TRUSTED_PROXIES"].split(",") if x.strip()]}
           if env.get("POSTFLOW_TRUSTED_PROXIES") else {}),
        allow_private_ai=env.get("POSTFLOW_ALLOW_PRIVATE_AI", "").lower() == "true",
    )
