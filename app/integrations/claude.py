"""Anthropic 格式接口：官方 API 或 Anthropic 兼容的中转站（base_url）。"""
import json
import re
import time

import anthropic
from pydantic import ValidationError

from ..core.errors import UpstreamError
from ..domain.post import SeoSuggestion

OFFICIAL = "https://api.anthropic.com"

SYSTEM = """你是中文技术博客的 SEO 编辑，目标是提高文章在百度等国内搜索引擎的排名。用户会给出文章标题和正文。
标题是作者定好的，不要改写、不要评价，也不要输出标题。只生成下面三项：

- slug：文章网址。用英文提炼标题的核心主题词（产品名、数字、关键概念），小写、用连字符连接、4~8 个词、不超过 60 个字符；
  中文概念翻成通用英文（套餐 plan、美元/美刀 dollar、更新 updates、教程 guide、价格 price、对比 vs），数字原样保留，不要拼音，不要 the/a/of 这类虚词。
- description：「中国搜索版」摘要，100~130 个汉字，两句话：
  第一句直接讲清事实和核心信息（包含标题里最核心的关键词）；
  第二句用「本文整理/详细介绍……是什么、……有哪些变化、……如何……」这类说法，把中国用户会搜的问题自然写进去。
  不堆砌关键词，不用引号和换行。
- keywords：15~30 个，中国用户真实会搜的说法，按重要性排序，覆盖三类：
  ① 核心词（品牌 / 产品 + 主题，如「Python 3.14 自由线程」）；
  ② 同义和口语说法（美元 / 美刀 / 刀、最新消息 / 最新更新、套餐 / 会员 等都要覆盖）；
  ③ 长尾问题词（……是什么、……有什么变化、……价格、……缩水、……值不值得、……怎么用、……国内使用）。
  产品名保留英文原名，不放与正文无关的热词，不重复。

只依据标题和正文，不编造文中没有的事实、数字和价格。

示例——标题：Python 3.14 正式发布，自由线程转正、模板字符串上线，升级前先看这 5 个变化
slug：python-314-free-threading-template-strings-upgrade
description：Python 3.14 正式发布，自由线程版本转为官方支持，新增模板字符串 t-string 和延迟求值注解。本文整理 Python 3.14 更新重点，详细介绍自由线程是什么、t-string 怎么用、老项目升级到 3.14 要注意哪些兼容问题。
keywords：Python 3.14, Python3.14, Python 3.14新特性, Python 3.14发布, Python最新版本, Python更新, Python 3.14更新内容, 自由线程, Python自由线程, Python无GIL, Python去掉GIL, GIL, free-threading, 模板字符串, t-string, Python t-string, 延迟注解, Python zstd, Python 3.14下载, Python 3.14安装, Python 3.14怎么升级, Python升级注意事项, Python 3.14兼容性, Python 3.14和3.13区别, Python 3.14性能, Python 3.14值得升级吗, Python多解释器, Python新版本, Python教程, Python 3.14是什么"""

JSON_HINT = '\n\n只输出一个 JSON 对象，不要任何其他文字，字段：{"slug": "", "description": "", "keywords": []}'


def user_message(title: str, body: str) -> str:
    return f"标题：{title}\n\n正文：\n{body}"


def client(api_key: str, base_url: str | None, http_client=None) -> anthropic.AsyncAnthropic:
    # 显式传 base_url：不传时 SDK 会读环境变量 ANTHROPIC_BASE_URL，本机若给 Claude Code 配了中转就会被悄悄带走
    return anthropic.AsyncAnthropic(api_key=api_key, base_url=(base_url or OFFICIAL).rstrip("/"), max_retries=1,
                                    **({"http_client": http_client} if http_client else {}))


def is_official(base_url: str | None) -> bool:
    return not base_url or base_url.rstrip("/") == OFFICIAL


async def suggest_metadata(title: str, body: str, model: str, api_key: str, base_url: str | None = None,
                           http_client=None) -> SeoSuggestion:
    c = client(api_key, base_url, http_client)
    if is_official(base_url):
        # 官方：结构化输出 + 拒答时服务端自动换模型
        resp = await c.beta.messages.parse(
            model=model, max_tokens=4000, system=SYSTEM,
            messages=[{"role": "user", "content": user_message(title, body)}],
            output_format=SeoSuggestion, output_config={"effort": "low"},
            betas=["server-side-fallback-2026-07-01"], fallbacks="default",
        )
        if resp.stop_reason == "refusal" or resp.parsed_output is None:
            raise UpstreamError(f"AI 未返回结果（stop_reason={resp.stop_reason}），请手动填写")
        return resp.parsed_output
    # 中转站：不发 beta / fallbacks（多数中转不认）；先试结构化输出，不支持就让模型直接输出 JSON
    try:
        resp = await c.messages.parse(model=model, max_tokens=4000, system=SYSTEM,
                                      messages=[{"role": "user", "content": user_message(title, body)}], output_format=SeoSuggestion)
        if resp.parsed_output is not None:
            return resp.parsed_output
    except anthropic.BadRequestError:
        pass
    resp = await c.messages.create(model=model, max_tokens=4000, system=SYSTEM + JSON_HINT,
                                   messages=[{"role": "user", "content": user_message(title, body)}])
    if resp.stop_reason == "refusal":
        raise UpstreamError("AI 拒绝了这次请求，请手动填写")
    return parse_json(next((b.text for b in resp.content if b.type == "text"), ""))


async def ping(model: str, api_key: str, base_url: str | None = None, http_client=None) -> dict:
    """测试连接：发一句极短的话，确认地址、Key、模型都可用。"""
    started = time.monotonic()
    resp = await client(api_key, base_url, http_client).messages.create(
        model=model, max_tokens=64, messages=[{"role": "user", "content": "只回复两个字：收到"}])
    text = next((b.text for b in resp.content if b.type == "text"), "")
    return {"model": resp.model, "reply": text.strip()[:40], "ms": int((time.monotonic() - started) * 1000)}


def parse_json(text: str) -> SeoSuggestion:
    m = re.search(r"\{.*\}", text, re.S)  # 容忍 ```json 包裹或前后多余文字
    try:
        return SeoSuggestion(**json.loads(m.group(0) if m else text))
    except (ValueError, ValidationError, TypeError) as e:
        raise UpstreamError(f"AI 返回的不是有效的 JSON（{type(e).__name__}），请手动填写或换个模型")
