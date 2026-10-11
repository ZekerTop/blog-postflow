"""AI 补全元数据：按「设置 → AI 接口」选 Anthropic 格式（官方或中转）或 OpenAI 兼容格式。"""
import logging
import re
from dataclasses import dataclass

from ..core.errors import AppError, BadRequest, UpstreamError
from ..core.security import check_public_url
from ..domain.seo import polish
from ..domain.slug import slugify
from ..integrations import claude, openai_compat
from .config import ConfigService

log = logging.getLogger("postflow.ai")
PROVIDERS = {"anthropic": "Anthropic 格式（官方或兼容中转）", "openai": "OpenAI 兼容格式（DeepSeek、Kimi、OpenRouter、聚合中转）"}


@dataclass
class AIConfig:
    provider: str
    base_url: str
    model: str
    api_key: str


class AIService:
    def __init__(self, config: ConfigService):
        self.config = config

    def current(self, overrides: dict | None = None) -> AIConfig:
        """overrides：「测试连接」时用页面上还没保存的值；没填的取已保存的。"""
        o = {k: (v or "").strip() for k, v in (overrides or {}).items() if v is not None}
        provider = o.get("provider") or self.config.ai_provider()
        if provider not in PROVIDERS:
            raise BadRequest(f"未知接口格式：{provider}")
        cfg = AIConfig(provider, o["base_url"] if "base_url" in o else self.config.ai_base_url(),
                       o.get("model") or self.config.model(), o.get("api_key") or self.config.secret("anthropic_api_key"))
        if not cfg.api_key:
            raise BadRequest("还没配置 AI API Key：去「设置 → AI 接口」填写，或手动填写元数据")
        if provider == "openai" and not cfg.base_url:
            raise BadRequest("OpenAI 兼容格式必须填接口地址，如 https://api.deepseek.com/v1")
        if cfg.base_url and not self.config.settings.allow_private_ai:
            check_public_url(cfg.base_url)  # 每次调用前都查：防止域名后来被改解析到内网
        return cfg

    async def suggest(self, title: str, body: str) -> dict:
        """标题由作者定、原样使用：网址按标题生成拼音，AI 只写描述和关键词。"""
        if not body.strip():
            raise BadRequest("正文为空")
        title = title.strip() or leading_h1(body)
        if not title:
            raise BadRequest("先填标题：网址、描述和关键词都围绕标题生成")
        c = self.current()
        try:
            impl = claude if c.provider == "anthropic" else openai_compat
            seo = polish(await impl.suggest_metadata(title, body, c.model, c.api_key, c.base_url))
            return {"title": title} | seo.model_dump() | {"slug": seo.slug or slugify(title)}  # AI 没给出可用 slug 时退回拼音
        except AppError:
            raise
        except Exception as e:
            log.exception("enrich failed (%s %s)", c.provider, c.model)
            raise UpstreamError(f"AI 补全失败：{describe(e)}，请检查「设置 → AI 接口」或手动填写")

    async def test(self, overrides: dict | None = None) -> dict:
        c = self.current(overrides)
        try:
            impl = claude if c.provider == "anthropic" else openai_compat
            res = await impl.ping(c.model, c.api_key, c.base_url)
            return {"ok": True} | res
        except Exception as e:
            log.warning("ai test failed (%s %s): %s", c.provider, c.model, e)
            return {"ok": False, "error": e.message if isinstance(e, AppError) else describe(e)}


def leading_h1(body: str) -> str:
    """标题框为空时用正文开头的「# 标题」（仍是作者自己写的标题）。"""
    m = re.match(r"\s*#\s+(.+)", body)
    return m.group(1).strip() if m else ""


def describe(e: Exception) -> str:
    """把 SDK / 网络异常翻成看得懂的一句话（不带 Key）。"""
    status = getattr(e, "status_code", None)
    hints = {401: "Key 无效或已过期", 403: "Key 没有权限", 404: "接口地址或模型名不对", 429: "额度用完或被限流"}
    if status in hints:
        return f"{status} {hints[status]}"
    if status:
        return f"接口返回 {status}"
    name = type(e).__name__
    if "Connect" in name or "Timeout" in name:
        return f"连不上接口地址（{name}）"
    return name
