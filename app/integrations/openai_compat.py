"""OpenAI 兼容格式接口（/chat/completions）：DeepSeek、Kimi、OpenRouter、各类 API 聚合中转。
项目里没装 openai SDK，直接用 httpx 调；Claude 走 integrations/claude.py。"""
import time

import httpx

from ..core.errors import UpstreamError
from ..domain.post import SeoSuggestion
from .claude import JSON_HINT, SYSTEM, parse_json, user_message


def _url(base_url: str) -> str:
    base = (base_url or "").rstrip("/")
    if not base:
        raise UpstreamError("OpenAI 兼容格式必须填接口地址，如 https://api.deepseek.com/v1")
    return base if base.endswith("/chat/completions") else base + "/chat/completions"


async def _chat(base_url: str, api_key: str, payload: dict, transport: httpx.AsyncBaseTransport | None = None) -> dict:
    async with httpx.AsyncClient(timeout=120, transport=transport) as c:
        r = await c.post(_url(base_url), json=payload, headers={"Authorization": f"Bearer {api_key}"})
    if r.status_code >= 400:
        try:
            err = r.json().get("error") or r.json()
            msg = err.get("message", r.text) if isinstance(err, dict) else str(err)
        except ValueError:
            msg = r.text[:200]
        raise UpstreamError(f"AI 接口 {r.status_code}：{msg}")
    return r.json()


async def suggest_metadata(title: str, body: str, model: str, api_key: str, base_url: str,
                           transport: httpx.AsyncBaseTransport | None = None) -> SeoSuggestion:
    payload = {"model": model, "max_tokens": 4000,
               "messages": [{"role": "system", "content": SYSTEM + JSON_HINT}, {"role": "user", "content": user_message(title, body)}]}
    try:
        data = await _chat(base_url, api_key, payload | {"response_format": {"type": "json_object"}}, transport)
    except UpstreamError as e:
        if "response_format" not in e.message and "json" not in e.message.lower():
            raise
        data = await _chat(base_url, api_key, payload, transport)  # 不支持 JSON 模式的服务：靠提示词
    return parse_json(data["choices"][0]["message"].get("content") or "")


async def ping(model: str, api_key: str, base_url: str, transport: httpx.AsyncBaseTransport | None = None) -> dict:
    started = time.monotonic()
    data = await _chat(base_url, api_key, {"model": model, "max_tokens": 16,
                                           "messages": [{"role": "user", "content": "只回复两个字：收到"}]}, transport)
    text = data["choices"][0]["message"].get("content") or ""
    return {"model": data.get("model", model), "reply": text.strip()[:40], "ms": int((time.monotonic() - started) * 1000)}
