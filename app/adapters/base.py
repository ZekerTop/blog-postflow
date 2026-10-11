import json
from typing import Any

import yaml

from ..domain.post import Post


def yaml_scalar(value: str) -> str:
    """手写 front matter 用：能原样写就原样写（和手工发布一致），会被 YAML 读歪的才加双引号。"""
    if value == "":
        return ""
    try:
        if "\n" not in value and yaml.safe_load(f"k: {value}") == {"k": value}:
            return value
    except yaml.YAMLError:
        pass
    return json.dumps(value, ensure_ascii=False)


def split_blocks(body: str) -> list[str]:
    """按空行切分段落，代码块（``` 围栏）内的空行不切。"""
    blocks, cur, in_fence = [], [], False
    for line in body.strip().splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        if not line.strip() and not in_fence:
            if cur:
                blocks.append("\n".join(cur))
                cur = []
            continue
        cur.append(line)
    if cur:
        blocks.append("\n".join(cur))
    return blocks


class Adapter:
    def __init__(self, options: dict[str, Any] | None = None):
        self.options = options or {}

    def render(self, post: Post) -> str:
        raise NotImplementedError

    def update(self, original: str, post: Post) -> str:
        """编辑已发布文章：在原文基础上只改动过的部分。"""
        raise NotImplementedError

    def parse(self, text: str) -> dict[str, Any]:
        """render 的反向：已发布的 md → Post 字段（不含 slug）。用于载入老文章编辑。"""
        raise NotImplementedError
