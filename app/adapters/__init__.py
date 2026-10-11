"""格式适配器：Post → 某个博客框架的 md 文本。纯函数，不做任何 IO。

adapter 字段填主题预设名（presets.py），options 覆盖预设里的同名项。
新增主题：presets.py 加一项；正文处理方式不同才动 markdown.py。
"""
from typing import Any

from .base import Adapter
from .markdown import MarkdownAdapter, validate_options
from .presets import ALIASES, PRESETS


def get_adapter(name: str, options: dict[str, Any]) -> Adapter:
    preset = PRESETS.get(ALIASES.get(name, name))
    if not preset:
        raise ValueError(f"未知 adapter：{name}，可选 {list(PRESETS)}")
    merged = preset["options"] | (options or {})
    validate_options(merged)
    return MarkdownAdapter(merged)


def preset_list() -> list[dict[str, str]]:
    return [{"name": k, "label": v["label"], "posts_dir": v["posts_dir"], "filename": v["filename"]}
            for k, v in PRESETS.items()]
