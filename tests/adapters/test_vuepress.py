from datetime import datetime
from pathlib import Path

import yaml

from app.adapters import get_adapter
from tests.conftest import make_post

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "vuepress"


def test_matches_published_article():
    """source.md 是粘贴的正文，expected.md 是期望的完整文件（与真实线上文章同一格式），要求逐字一致。"""
    _, fm, _ = (FIXTURES / "expected.md").read_text(encoding="utf-8").split("---\n", 2)
    meta = yaml.safe_load(fm)
    post = make_post(
        title=meta["title"], slug="multi-blog-one-click-publish-github-actions",
        date=datetime(2026, 9, 30, 12, 30), description=meta["description"],
        keywords=meta["keywords"].split(","), tags=meta["tags"], categories=meta["categories"],
        body=(FIXTURES / "source.md").read_text(encoding="utf-8"),
    )
    assert get_adapter("classic-vuepress", {}).render(post) == (FIXTURES / "expected.md").read_text(encoding="utf-8")


def test_leading_h1_replaced_and_more_kept():
    md = get_adapter("classic-vuepress", {}).render(make_post(body="# 旧标题\n\n第一段。\n\n<!-- more -->\n\n第二段。"))
    assert "旧标题" not in md
    assert md.endswith("---\n\n# 标题：测试\n\n第一段。\n\n<!-- more -->\n\n第二段。")


def test_empty_lists_and_quoting():
    md = get_adapter("vuepress", {}).render(  # 别名 vuepress 仍可用
        make_post(title="Claude: 新功能 #1", tags=[], categories=[], keywords=[], description=""))
    fm = yaml.safe_load(md.split("---\n", 2)[1])
    assert fm["title"] == "Claude: 新功能 #1"
    assert fm["tags"] == [] and fm["categories"] == []
    assert fm["sidebarDepth"] == 3
    assert "title: \"Claude: 新功能 #1\"\n" in md
    assert "date: 2026-10-05 09:30\n" in md


def test_parse_round_trip_published_article():
    """载入老文章编辑：parse 再 render 必须回到逐字相同的原文，否则一保存就改动了线上文章。"""
    text = (FIXTURES / "expected.md").read_text(encoding="utf-8")
    fields = get_adapter("classic-vuepress", {}).parse(text)
    assert fields["title"].startswith("三个博客一键发布") and fields["date"] == datetime(2026, 9, 30, 12, 30)
    assert fields["tags"] == ["GitHub Actions"] and len(fields["keywords"]) > 5
    post = make_post(slug="multi-blog-one-click-publish-github-actions", **fields)
    assert get_adapter("classic-vuepress", {}).render(post) == text
