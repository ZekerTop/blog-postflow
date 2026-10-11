"""「文章」页：列出仓库里的已发布文章（含老文章）、载入编辑写回原文件、删除时同一提交登记放行名单。"""
from app.core.config import BlogConfig
from tests.conftest import login

REPO = "o/r3"
BLOG3 = BlogConfig(id="b3", name="b3", repo=REPO, posts_dir="docs/blog", filename="{category_dir}/{slug}.md",
                   adapter="classic-vuepress", category_dirs={"ChatGPT": "chatgpt"}, default_category_dir="ai",
                   post_url="https://blog.example.com/blog/{category_dir}/{slug}.html")
OLD = """---
title: 旧笔记迁移记录
date: 2025-03-01 10:00
description: 老文章
keywords: 迁移,笔记
sidebarDepth: 3
tags:
- ChatGPT
categories:
- ChatGPT
---

# 旧笔记迁移记录

正文。
"""
OLD_PATH = "docs/blog/notes/notes迁移记录.md"


def setup(client, fake_github):
    client.app.state.config.store.save_blog(BLOG3)
    fake_github.add(REPO, OLD_PATH, OLD)
    fake_github.add(REPO, "docs/blog/claude/hello_world.md", OLD)
    fake_github.add(REPO, "docs/README.md", "# home")
    fake_github.add(REPO, "package.json", "{}")
    return login(client)


def test_list_only_posts_dir_markdown(client, fake_github):
    setup(client, fake_github)
    items = client.get("/api/blogs/b3/articles").json()
    assert [i["path"] for i in items] == ["docs/blog/claude/hello_world.md", OLD_PATH]
    assert items[0] == {"path": "docs/blog/claude/hello_world.md", "slug": "hello_world", "dir": "claude",
                        "url": "https://blog.example.com/blog/claude/hello_world.html"}


def test_load_edit_and_write_back_to_original_path(client, fake_github):
    h = setup(client, fake_github)
    loaded = client.get("/api/blogs/b3/articles/file", params={"path": OLD_PATH}).json()
    post = loaded["post"]
    assert post["slug"] == "notes迁移记录" and post["title"] == "旧笔记迁移记录"
    assert post["body"] == "正文。\n" and post["keywords"] == ["迁移", "笔记"]

    # 原样发布 = 文件内容不变；分类是 ChatGPT，但写回原来的 notes/ 目录，不会另起一个文件
    payload = {"post": post, "blog_ids": ["b3"], "overwrite": True, "paths": {"b3": OLD_PATH}}
    prev = client.post("/api/preview", headers=h, json=payload).json()[0]
    assert prev["path"] == OLD_PATH and prev["exists"] and prev["editing"] and prev["content"] == OLD
    post["body"] = "改过的正文。\n"
    rec = client.post("/api/publish", headers=h, json=payload | {"post": post}).json()
    assert rec["results"][0]["ok"] and rec["results"][0]["path"] == OLD_PATH
    assert fake_github.content[(REPO, OLD_PATH)].endswith("# 旧笔记迁移记录\n\n改过的正文。\n")
    # 改了正文：页面同一提交登记进放行名单，部署时 SEO 守门不拦
    repo, msg, changes = fake_github.commits[-1]
    assert set(changes) == {OLD_PATH, ".github/allowed-removals.txt"}
    assert "Postflow 编辑 " + OLD_PATH + "\nnotes迁移记录.html\nnotes迁移记录/index.html\n" \
        in changes[".github/allowed-removals.txt"]
    assert not any(p.startswith("docs/blog/chatgpt/") for (_, p) in fake_github.files)
    st = client.get(f"/api/status/{rec['id']}").json()["results"][0]
    assert st["post_url"] == "https://blog.example.com/blog/notes/notes迁移记录.html"
    # 重发仍写回原文件
    rec = client.post(f"/api/publish/{rec['id']}/retry", headers=h, json={"blog_ids": ["b3"], "overwrite": True}).json()
    assert rec["results"][0]["path"] == OLD_PATH


def test_delete_commits_removal_and_allow_list_together(client, fake_github):
    h = setup(client, fake_github)
    r = client.post("/api/blogs/b3/articles/delete", headers=h, json={"path": "docs/blog/claude/hello_world.md"})
    assert r.status_code == 200
    repo, msg, changes = fake_github.commits[-1]
    assert changes["docs/blog/claude/hello_world.md"] is None
    allow = changes[".github/allowed-removals.txt"]
    assert allow.startswith("# 故意删除或修改正文的页面") and "hello_world.html\nhello_world/index.html\n" in allow
    assert (REPO, "docs/blog/claude/hello_world.md") not in fake_github.files
    # 再删一篇：追加到已有名单，不覆盖
    client.post("/api/blogs/b3/articles/delete", headers=h, json={"path": OLD_PATH})
    allow2 = fake_github.commits[-1][2][".github/allowed-removals.txt"]
    assert allow2.startswith(allow.rstrip("\n")) and "notes迁移记录.html" in allow2


def test_edit_without_body_change_does_not_touch_allow_list(client, fake_github):
    h = setup(client, fake_github)
    post = client.get("/api/blogs/b3/articles/file", params={"path": OLD_PATH}).json()["post"]
    post["keywords"] = ["迁移", "笔记", "新关键词"]
    rec = client.post("/api/publish", headers=h, json={"post": post, "blog_ids": ["b3"], "overwrite": True,
                                                         "paths": {"b3": OLD_PATH}}).json()
    assert rec["results"][0]["ok"] and not fake_github.commits
    assert "新关键词" in fake_github.content[(REPO, OLD_PATH)]


def test_allow_entries_use_abbrlink_and_skip_duplicates():
    from app.services.allowlist import page_entries
    old_post = "---\ntitle: Redis\nabbrlink: 9f3c2a71\n---\n正文"
    assert page_entries("source/_posts/redis.md", old_post) == [
        "redis.html", "redis/index.html", "9f3c2a71.html", "9f3c2a71/index.html"]
    assert page_entries("source/_posts/x.md", "---\nabbrlink: x\n---\n") == ["x.html", "x/index.html"]
    assert page_entries("docs/blog/ai/foo/index.md", "") == ["foo.html", "foo/index.html"]


def test_delete_twice_registered_page_not_duplicated(client, fake_github):
    h = setup(client, fake_github)
    fake_github.add(REPO, ".github/allowed-removals.txt", "# x\nhello_world.html\nhello_world/index.html\n")
    client.post("/api/blogs/b3/articles/delete", headers=h, json={"path": "docs/blog/claude/hello_world.md"})
    assert set(fake_github.commits[-1][2]) == {"docs/blog/claude/hello_world.md"}


def test_paths_outside_posts_dir_rejected(client, fake_github):
    h = setup(client, fake_github)
    for bad in ["package.json", "docs/README.md", "docs/blog/../../package.json", "docs/blog/x.txt"]:
        assert client.get("/api/blogs/b3/articles/file", params={"path": bad}).status_code == 400
        assert client.post("/api/blogs/b3/articles/delete", headers=h, json={"path": bad}).status_code == 400
    post = {"title": "T", "slug": "s", "date": "2026-10-09T10:00:00", "body": "b"}
    r = client.post("/api/publish", headers=h, json={"post": post, "blog_ids": ["b3"], "paths": {"b3": "package.json"}})
    assert r.status_code == 400 and not fake_github.puts


def test_unknown_blog_404(client, fake_github):
    setup(client, fake_github)
    assert client.get("/api/blogs/nope/articles").status_code == 404
