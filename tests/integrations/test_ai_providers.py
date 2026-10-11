"""两种 AI 接口格式：真实构造请求，用 MockTransport 截下来检查（不联网）。"""
import asyncio
import json

import anthropic
import httpx
import httpx2
import pytest

from app.core.errors import UpstreamError
from app.integrations import claude, openai_compat

META = {"slug": "a-b-c", "description": "摘要", "keywords": ["k"]}


def anthropic_reply(text: str, model: str = "claude-opus-5-5") -> dict:
    return {"id": "msg_1", "type": "message", "role": "assistant", "model": model, "stop_reason": "end_turn",
            "content": [{"type": "text", "text": text}], "usage": {"input_tokens": 1, "output_tokens": 1}}


def sdk_client(handler):
    return anthropic.DefaultAsyncHttpxClient(transport=httpx2.MockTransport(handler))


def test_official_uses_structured_output_and_fallbacks(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://relay.example.com")  # 本机给 Claude Code 配的中转不能被带进来
    seen = []

    def handler(req):
        seen.append(req)
        return httpx2.Response(200, json=anthropic_reply(json.dumps(META)))

    out = asyncio.run(claude.suggest_metadata("我的标题", "正文", "claude-opus-5-5", "k", None, sdk_client(handler)))
    assert out.description == "摘要"
    req = seen[0]
    assert "标题：我的标题" in json.loads(req.content)["messages"][0]["content"]
    assert req.url.host == "api.anthropic.com"
    body = json.loads(req.content)
    assert body["fallbacks"] == "default" and body["output_config"]["effort"] == "low"
    assert "server-side-fallback-2026-07-01" in req.headers["anthropic-beta"]


def test_relay_skips_betas_and_falls_back_to_plain_json():
    seen = []

    def handler(req):
        seen.append(req)
        if len(seen) == 1:  # 中转不支持结构化输出
            return httpx2.Response(400, json={"type": "error", "error": {"type": "invalid_request_error", "message": "output_config not supported"}})
        return httpx2.Response(200, json=anthropic_reply("好的：\n```json\n" + json.dumps(META, ensure_ascii=False) + "\n```"))

    out = asyncio.run(claude.suggest_metadata("我的标题", "正文", "claude-opus-5-5", "k", "https://relay.example.com/claudecode/", sdk_client(handler)))
    assert out.keywords == ["k"]
    assert all(r.url.host == "relay.example.com" and r.url.path.startswith("/claudecode/v1/") for r in seen)
    assert all("anthropic-beta" not in r.headers and "fallbacks" not in json.loads(r.content) for r in seen)


def test_anthropic_ping_reports_model():
    out = asyncio.run(claude.ping("claude-opus-5-5", "k", None,
                                  sdk_client(lambda req: httpx2.Response(200, json=anthropic_reply("收到")))))
    assert out["model"] == "claude-opus-5-5" and out["reply"] == "收到" and out["ms"] >= 0


def openai_reply(text: str) -> dict:
    return {"model": "deepseek-chat", "choices": [{"message": {"role": "assistant", "content": text}}]}


def test_openai_compatible_json_mode_and_url():
    seen = []

    def handler(req):
        seen.append(req)
        return httpx.Response(200, json=openai_reply(json.dumps(META)))

    out = asyncio.run(openai_compat.suggest_metadata("我的标题", "正文", "deepseek-chat", "sk-x", "https://api.deepseek.com/v1/",
                                                     httpx.MockTransport(handler)))
    assert out.keywords == ["k"]
    assert str(seen[0].url) == "https://api.deepseek.com/v1/chat/completions"
    assert seen[0].headers["authorization"] == "Bearer sk-x"
    assert json.loads(seen[0].content)["response_format"] == {"type": "json_object"}


def test_openai_compatible_without_json_mode_retries_plain():
    calls = []

    def handler(req):
        calls.append(json.loads(req.content))
        if "response_format" in calls[-1]:
            return httpx.Response(400, json={"error": {"message": "response_format is not supported"}})
        return httpx.Response(200, json=openai_reply(json.dumps(META)))

    assert asyncio.run(openai_compat.suggest_metadata("我的标题", "正文", "m", "k", "https://x.ai/v1", httpx.MockTransport(handler))).description == "摘要"
    assert len(calls) == 2


def test_openai_compatible_errors_are_readable():
    t = httpx.MockTransport(lambda req: httpx.Response(401, json={"error": {"message": "invalid api key"}}))
    with pytest.raises(UpstreamError, match="401：invalid api key"):
        asyncio.run(openai_compat.ping("m", "k", "https://x.ai/v1", t))
    with pytest.raises(UpstreamError, match="必须填接口地址"):
        asyncio.run(openai_compat.ping("m", "k", "", t))
    bad = httpx.MockTransport(lambda req: httpx.Response(200, json=openai_reply("不是 JSON")))
    with pytest.raises(UpstreamError, match="不是有效的 JSON"):
        asyncio.run(openai_compat.suggest_metadata("我的标题", "正文", "m", "k", "https://x.ai/v1", bad))
