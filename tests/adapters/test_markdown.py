import re
from datetime import datetime

import pytest
import yaml

from app.adapters import get_adapter, preset_list
from app.adapters.presets import PRESETS
from tests.conftest import make_post


def parse(md: str):
    _, fm, body = md.split("---\n", 2)
    return yaml.safe_load(fm), body.strip()


def render(name: str, options: dict | None = None, **post) -> str:
    return get_adapter(name, options or {}).render(make_post(**post))


def test_hexo_front_matter():
    md = render("hexo")
    assert "\ndate: 2026-10-05 09:30:00\n" in md
    fm, body = parse(md)
    assert fm == {"title": "标题：测试", "date": datetime(2026, 10, 5, 9, 30), "tags": ["AI", "Claude"],
                  "categories": ["教程"], "description": "摘要", "keywords": "k1,k2"}
    assert "<!-- more -->" not in body


def test_more_marker_after_n_paragraphs():
    _, body = parse(render("hexo-next"))
    assert body.startswith("第一段。\n\n第二段。\n\n<!-- more -->\n\n```python")
    assert "a = 1\n\nb = 2" in body


def test_more_marker_not_duplicated():
    assert render("hexo-next", body="一\n\n<!-- more -->\n\n二\n\n三").count("<!-- more -->") == 1


def test_options_override_preset():
    fm, _ = parse(render("hexo", {"extra_front_matter": {"cover": "https://img/x.png"}, "date_format": "%Y-%m-%d"}))
    assert fm["cover"] == "https://img/x.png"
    assert fm["date"].isoformat() == "2026-10-05"


def test_custom_fields_and_placeholders():
    fm, _ = parse(render("hexo", {"fields": {"title": "$title", "abbrlink": "{slug}", "top": 1, "draft": False,
                                             "kw": "$keywords"}, "keywords_style": "list"}))
    assert fm == {"title": "标题：测试", "abbrlink": "test-post", "top": 1, "draft": False, "kw": ["k1", "k2"]}


def test_empty_values_omit_or_keep():
    fm, _ = parse(render("hexo", tags=[], description=""))
    assert "tags" not in fm and "description" not in fm
    md = render("hexo", {"empty": "keep"}, tags=[], description="")
    assert "\ntags: []\n" in md and "\ndescription: \n" in md


def test_cover_field_by_theme():
    cover = "https://img/c.png"
    assert parse(render("hexo-butterfly", cover=cover))[0]["cover"] == cover
    assert parse(render("hexo-fluid", cover=cover))[0]["index_img"] == cover
    assert "cover" not in parse(render("hexo-butterfly"))[0]  # 没填封面就不输出


def test_h1_and_strip():
    md = render("vitepress", body="# 旧标题\n\n正文")
    assert "旧标题" not in md and md.endswith("# 标题：测试\n\n正文")


@pytest.mark.parametrize("name", list(PRESETS))
def test_every_preset_renders_valid_yaml(name):
    fm, body = parse(render(name, cover="https://img/c.png"))
    assert isinstance(fm, dict) and fm and body


def test_hugo_date_has_timezone():
    assert "\ndate: 2026-10-05T09:30:00+08:00\n" in render("hugo")


def test_unknown_adapter_and_bad_options():
    with pytest.raises(ValueError, match="未知 adapter"):
        get_adapter("nope", {})
    with pytest.raises(ValueError, match=r"\$titel"):
        get_adapter("hexo", {"fields": {"title": "$titel"}})


def test_preset_list_for_ui():
    names = [p["name"] for p in preset_list()]
    assert "classic-hexo" in names and all(p["label"] for p in preset_list())


ORIGINAL = """---
title: '手写的标题: 带引号'
permalink: /custom/url.html
tags: [AI, Claude]
sidebarDepth: 2
head:
  - [meta, {name: robots, content: noindex}]
---

# 手写的 H1，比标题长

第一段。

第二段。
"""


def loaded(a, text, **kw):
    """模拟「文章」页载入：只用原文里解析出来的字段。"""
    from app.domain.post import Post
    return Post(slug="x", **a.parse(text) | kw)


def test_update_unchanged_is_byte_identical():
    a = get_adapter("classic-vuepress", {})
    post = loaded(a, ORIGINAL)
    assert post.date is None and post.tags == ["AI", "Claude"]
    assert a.update(ORIGINAL, post) == ORIGINAL


def test_update_only_touches_changed_fields_and_keeps_custom_ones():
    a = get_adapter("classic-vuepress", {})
    post = loaded(a, ORIGINAL)
    out = a.update(ORIGINAL, post.model_copy(update={"tags": ["AI"], "body": post.body.replace("第二段", "第二段（改）")}))
    assert "permalink: /custom/url.html\n" in out and "  - [meta, {name: robots, content: noindex}]\n" in out
    assert "title: '手写的标题: 带引号'\n" in out and "sidebarDepth: 2\n" in out  # 没改的原样保留
    assert "tags:\n- AI\nsidebarDepth" in out  # 改了的那个字段按模板重写，位置不变
    assert "# 手写的 H1，比标题长\n\n第一段。\n\n第二段（改）。\n" in out
    assert "date:" not in out and "description" not in out  # 原文没有、也没填的字段不新增


def test_update_title_follows_h1_only_when_h1_was_the_title():
    a = get_adapter("classic-vuepress", {})
    gen = a.render(make_post(title="旧标题", body="正文"))
    post = make_post(**a.parse(gen) | {"title": "新标题"})
    assert "# 新标题\n\n正文" in a.update(gen, post)
    custom = loaded(a, ORIGINAL, title="新标题")
    assert "# 手写的 H1，比标题长" in a.update(ORIGINAL, custom)


def test_new_post_still_requires_date():
    from app.core.config import BlogConfig
    from app.core.errors import BadRequest
    from app.services.publisher import Publisher
    blog = BlogConfig(id="b", name="b", repo="o/b", posts_dir="p", adapter="hexo")
    with pytest.raises(BadRequest, match="发布时间"):
        Publisher.render(None, blog, make_post(date=None))


# ---- 正文小节用了 H1：新文章自动降一级 ----
from app.adapters.markdown import demote_headings  # noqa: E402

PASTED = "开头一段。\n\n# 为什么做\n\n## 细节\n\n```sh\n# 这是注释\n```\n\n# 怎么用\n\n###### 六级\n"


def test_demote_headings_shifts_all_levels_and_skips_code():
    assert demote_headings(PASTED) == ("开头一段。\n\n## 为什么做\n\n### 细节\n\n```sh\n# 这是注释\n```\n\n"
                                       "## 怎么用\n\n###### 六级\n")
    no_h1 = "## 已经是二级\n\n```\n# 代码\n```\n\n#没空格不是标题\n"
    assert demote_headings(no_h1) == no_h1
    assert demote_headings("~~~\n# 代码\n~~~\n") == "~~~\n# 代码\n~~~\n"


def test_new_post_has_single_h1_but_edit_leaves_body_alone():
    from app.adapters import get_adapter
    for name in ("classic-hexo-abbrlink", "classic-vuepress", "classic-hexo"):
        a = get_adapter(name, {})
        out = a.render(make_post(body="# 标题：测试\n\n" + PASTED))
        body = re.sub(r"```.*?```", "", out.split("\n---\n", 1)[1], flags=re.S)
        assert len(re.findall(r"^# ", body, re.M)) == (1 if a.options.get("h1") else 0), name
        assert "## 为什么做" in out and "# 这是注释" in out
        # 编辑老文章：正文原样写回，不降级
        old = out.replace("## 为什么做", "# 为什么做")
        assert a.update(old, make_post(body=a.parse(old)["body"])) == old
    assert "\n# 为什么做" in get_adapter("classic-hexo-abbrlink", {"demote_h1": False}).render(make_post(body=PASTED))
