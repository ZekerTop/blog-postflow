"""网页配置：首次初始化、密码、GitHub Token / Anthropic Key、博客增删改查与连通性自检。

取值顺序：页面里保存的（SQLite）> 环境变量。Token / Key 只回传是否已设置和末 4 位，永不回传原文。
"""
import hmac
import logging
import secrets
from collections.abc import Callable
from typing import Any

import yaml
from pydantic import ValidationError

from ..adapters import get_adapter, preset_list
from ..core.config import BlogConfig, Settings, load_blogs
from ..core.errors import BadRequest, Conflict, Forbidden, NotFound, Unauthorized
from ..core.security import LoginLimiter, check_public_url, hash_password, verify_password
from ..integrations.github import GitHub
from ..storage.config_store import ConfigStore

log = logging.getLogger("postflow.config")

SECRETS = {"github_token": "GitHub Token", "anthropic_api_key": "AI API Key"}  # 键名沿用旧的，兼容 .env 里的 ANTHROPIC_API_KEY
AI_SETTINGS = ("ai_provider", "ai_base_url", "anthropic_model")
MIN_PASSWORD = 8


def mask(value: str) -> str:
    return f"…{value[-4:]}" if len(value) > 8 else "已设置"


def parse_yaml_map(text: str, field: str) -> dict[str, Any]:
    if not text.strip():
        return {}
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise BadRequest(f"{field} 不是合法的 YAML：{e}")
    if not isinstance(data, dict):
        raise BadRequest(f"{field} 应为「键: 值」形式")
    return data


class ConfigService:
    def __init__(self, settings: Settings, store: ConfigStore,
                 github_factory: Callable[[str], GitHub] = GitHub):
        self.settings = settings
        self.store = store
        self.github_factory = github_factory
        self._clients: dict[str, GitHub] = {}  # 按 Token 缓存：不同博客可能在不同 GitHub 账号
        self.limiter = LoginLimiter()
        self.setup_code = "" if self.password_hash() else secrets.token_hex(4)
        self._import_blogs_yml()

    # ---------- 首次初始化 / 登录 / 密码 ----------

    def password_hash(self) -> str:
        return self.settings.password_hash or self.store.get("password_hash")

    def needs_setup(self) -> bool:
        return not self.password_hash()

    def setup(self, code: str, password: str, client_key: str) -> None:
        if not self.needs_setup():
            raise Conflict("已初始化过，请直接登录")
        self.limiter.check(client_key)
        if not hmac.compare_digest(code.strip(), self.setup_code):
            self.limiter.fail(client_key)
            raise Forbidden("初始化码不对（看服务启动日志或 data/setup-code.txt）")
        self._check_new_password(password)
        self.store.set("password_hash", hash_password(password))
        self.setup_code = ""
        log.info("initial password set")

    def login(self, password: str, client_key: str) -> None:
        if self.needs_setup():
            raise Unauthorized("还没设置密码，请先初始化")
        self.limiter.check(client_key)
        if not verify_password(password, self.password_hash()):
            self.limiter.fail(client_key)
            raise Unauthorized("密码错误")
        self.limiter.reset(client_key)

    def change_password(self, current: str, new: str) -> None:
        if self.settings.password_hash:
            raise BadRequest("密码由环境变量 POSTFLOW_PASSWORD_HASH 管理，请改 .env")
        if not verify_password(current, self.password_hash()):
            raise Unauthorized("当前密码错误")
        self._check_new_password(new)
        self.store.set("password_hash", hash_password(new))

    @staticmethod
    def _check_new_password(pw: str) -> None:
        if len(pw) < MIN_PASSWORD:
            raise BadRequest(f"密码至少 {MIN_PASSWORD} 位")

    # ---------- Token / Key / 模型 ----------

    def secret(self, key: str) -> str:
        return self.store.get(key) or getattr(self.settings, key)

    def model(self) -> str:
        return self.store.get("anthropic_model") or self.settings.anthropic_model

    def ai_provider(self) -> str:
        return self.store.get("ai_provider") or "anthropic"

    def ai_base_url(self) -> str:
        """留空 = 官方地址。不读 ANTHROPIC_BASE_URL 环境变量（本机给 Claude Code 配的中转不该被带进来）。"""
        return self.store.get("ai_base_url")

    def secrets_view(self) -> dict:
        out = {}
        for key, label in SECRETS.items():
            db, env = self.store.get(key), getattr(self.settings, key)
            value = db or env
            out[key] = {"label": label, "set": bool(value), "hint": mask(value) if value else "",
                        "source": "page" if db else ("env" if env else "")}
        out["anthropic_model"] = self.model()
        out["ai_provider"] = self.ai_provider()
        out["ai_base_url"] = self.ai_base_url()
        return out

    def update_secrets(self, changes: dict[str, str | None]) -> None:
        """None = 不改；"" = 清除页面里保存的值（若环境变量有值则回落到环境变量）。"""
        for key, value in changes.items():
            if value is None:
                continue
            if key not in (*SECRETS, *AI_SETTINGS):
                raise BadRequest(f"未知配置项：{key}")
            if key == "ai_provider" and value not in ("anthropic", "openai"):
                raise BadRequest(f"未知接口格式：{value}")
            if key == "ai_base_url" and value.strip() and not self.settings.allow_private_ai:
                check_public_url(value.strip())
            self.store.set(key, value.strip())
            log.info("config %s %s", key, "updated" if value.strip() else "cleared")

    def github(self, blog: BlogConfig) -> GitHub:
        """博客自己的 Token 优先（仓库在别的 GitHub 账号时用），没填就用全局 Token。"""
        token = self.blog_token(blog.id) or self.secret("github_token")
        if not token:
            raise BadRequest(f"「{blog.name}」没有可用的 GitHub Token：在「设置 → 密钥」填全局 Token，或在该博客里填专用 Token")
        if token not in self._clients:
            self._clients[token] = self.github_factory(token)
        return self._clients[token]

    async def aclose(self) -> None:
        for client in self._clients.values():
            await client.aclose()

    @staticmethod
    def _blog_token_key(blog_id: str) -> str:
        return f"blog_token:{blog_id}"

    def blog_token(self, blog_id: str) -> str:
        return self.store.get(self._blog_token_key(blog_id))

    def blog_token_view(self, blog_id: str) -> dict:
        token = self.blog_token(blog_id)
        return {"token_set": bool(token), "token_hint": mask(token) if token else ""}

    # ---------- 博客 ----------

    def blogs(self) -> list[BlogConfig]:
        return self.store.blogs()

    def adapters(self) -> list[dict[str, str]]:
        return preset_list()

    def save_blog(self, data: dict[str, Any], is_new: bool) -> BlogConfig:
        data = dict(data)
        token = data.pop("token", None)  # None = 不改；"" = 清除，改用全局 Token
        data["category_dirs"] = {str(k): str(v) for k, v in
                                 parse_yaml_map(data.pop("category_dirs_yaml", ""), "分类目录映射").items()}
        data["options"] = parse_yaml_map(data.pop("options_yaml", ""), "适配器选项")
        try:
            blog = BlogConfig(**data)
        except ValidationError as e:
            raise BadRequest("；".join(f"{'.'.join(map(str, err['loc']))}：{err['msg']}" for err in e.errors()))
        try:
            get_adapter(blog.adapter, blog.options)
        except ValueError as e:
            raise BadRequest(str(e))
        if "{category_dir}" in blog.filename and not blog.default_category_dir:
            raise BadRequest("文件名用了 {category_dir}，必须填「默认目录」")
        exists = any(b.id == blog.id for b in self.blogs())
        if is_new and exists:
            raise Conflict(f"id「{blog.id}」已存在")
        if not is_new and not exists:
            raise NotFound(f"博客「{blog.id}」不存在")
        self.store.save_blog(blog)
        if token is not None:
            self.store.set(self._blog_token_key(blog.id), token.strip())
        log.info("blog %s %s%s", blog.id, "added" if is_new else "updated",
                 "" if token is None else (", own token set" if token.strip() else ", own token cleared"))
        return blog

    def delete_blog(self, blog_id: str) -> None:
        if not self.store.delete_blog(blog_id):
            raise NotFound(f"博客「{blog_id}」不存在")
        self.store.set(self._blog_token_key(blog_id), "")
        log.info("blog %s deleted", blog_id)

    async def check_blog(self, blog_id: str) -> dict:
        blog = next((b for b in self.blogs() if b.id == blog_id), None)
        if not blog:
            raise NotFound(f"博客「{blog_id}」不存在")
        try:
            problems = await self.github(blog).check_target(blog.repo, blog.branch, blog.posts_dir)
        except Exception as e:
            problems = [str(e)]
        return {"ok": not problems, "problems": problems}

    def presets(self) -> list[dict]:
        """blogs.example.yml 里的三个博客写法，供「从模板填」使用。"""
        f = self.settings.blogs_file.parent / "blogs.example.yml"
        if not f.exists():
            return []
        return (yaml.safe_load(f.read_text(encoding="utf-8")) or {}).get("blogs", [])

    def _import_blogs_yml(self) -> None:
        """老配置迁移：库里还没有博客、而 blogs.yml 存在时导入一次。"""
        f = self.settings.blogs_file
        if self.store.blogs() or not f.exists():
            return
        for b in load_blogs(f):
            self.store.save_blog(b)
        log.info("imported blogs from %s", f.name)
