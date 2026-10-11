import asyncio

import pytest

from app.core.config import BlogConfig
from app.core.errors import BadRequest, NotFound
from app.services.publisher import Publisher, format_template
from tests.conftest import BLOGS, make_post


def test_format_template():
    assert format_template("{year}/{month}/{day}/{slug}.md", make_post()) == "2026/10/05/test-post.md"


def test_render_path(publisher):
    assert publisher.render(BLOGS[0], make_post()).path == "source/_posts/test-post.md"


def test_category_dir_path(publisher):
    blog3 = BlogConfig(id="blog3", name="b3", repo="o/r3", posts_dir="docs/blog", filename="{category_dir}/{slug}.md",
                       adapter="classic-vuepress", category_dirs={"ChatGPT": "chatgpt"}, default_category_dir="ai")
    assert publisher.render(blog3, make_post(categories=["ChatGPT"])).path == "docs/blog/chatgpt/test-post.md"
    assert publisher.render(blog3, make_post(categories=["没配置的"])).path == "docs/blog/ai/test-post.md"
    assert publisher.render(blog3, make_post(categories=[])).path == "docs/blog/ai/test-post.md"


def test_pick_validation(publisher):
    with pytest.raises(BadRequest):
        publisher.pick([])
    with pytest.raises(BadRequest, match="未知博客"):
        publisher.pick(["nope"])


def test_bad_adapter_rejected_on_save(config):
    with pytest.raises(BadRequest, match="未知 adapter"):
        config.save_blog({"id": "x", "name": "x", "repo": "o/x", "posts_dir": "p", "adapter": "nope"}, is_new=True)


def test_retry_unknown_record(publisher):
    with pytest.raises(NotFound):
        asyncio.run(publisher.retry(999, ["blog1"], False))


def test_one_blog_failure_isolated(publisher, fake_github):
    fake_github.fail_repos.add("o/r1")
    rec = asyncio.run(publisher.publish(make_post(), ["blog1", "blog2"], False))
    by = {r["blog_id"]: r for r in rec["results"]}
    assert not by["blog1"]["ok"] and "500" in by["blog1"]["error"]
    assert by["blog2"]["ok"]
