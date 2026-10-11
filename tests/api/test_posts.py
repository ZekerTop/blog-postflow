from app.domain.post import SeoSuggestion
from app.integrations import claude
from tests.conftest import POST, login


def test_invalid_slug_rejected(client):
    h = login(client)
    r = client.post("/api/preview", headers=h, json={"post": POST | {"slug": "Bad Slug"}, "blog_ids": ["blog1"]})
    assert r.status_code == 422


def test_preview_and_publish(client, fake_github):
    h = login(client)
    prev = client.post("/api/preview", headers=h, json={"post": POST, "blog_ids": ["blog1", "blog2"]}).json()
    assert [p["path"] for p in prev] == ["source/_posts/my-post.md"] * 2
    assert prev[0]["exists"] is False
    assert "<!-- more -->" in prev[1]["content"] and "<!-- more -->" not in prev[0]["content"]

    rec = client.post("/api/publish", headers=h, json={"post": POST, "blog_ids": ["blog1", "blog2"]}).json()
    assert all(r["ok"] for r in rec["results"])
    assert len(fake_github.puts) == 2 and "sha" not in fake_github.puts[0][2]

    st = client.get(f"/api/status/{rec['id']}").json()
    b2 = next(r for r in st["results"] if r["blog_id"] == "blog2")
    assert b2["post_url"] == "https://x.cn/2026/my-post/"
    assert b2["runs"][0]["status"] == "in_progress"


def test_existing_file_needs_overwrite(client, fake_github):
    h = login(client)
    fake_github.files[("o/r1", "source/_posts/my-post.md")] = "old"
    rec = client.post("/api/publish", headers=h, json={"post": POST, "blog_ids": ["blog1"]}).json()
    assert not rec["results"][0]["ok"] and "已存在" in rec["results"][0]["error"]
    rec = client.post(f"/api/publish/{rec['id']}/retry", headers=h,
                      json={"blog_ids": ["blog1"], "overwrite": True}).json()
    assert rec["results"][0]["ok"]
    assert fake_github.puts[-1][2]["sha"] == "old"
    assert len(client.get("/api/history").json()) == 1


def test_not_found_error_format(client):
    h = login(client)
    r = client.post("/api/publish/999/retry", headers=h, json={"blog_ids": ["blog1"]})
    assert r.status_code == 404 and r.json() == {"detail": "发布记录 #999 不存在", "code": "not_found"}


def test_enrich_keeps_title_and_only_fills_seo(client, monkeypatch):
    h = login(client)
    seen = {}

    async def fake(title, body, model, api_key, base_url):
        seen["title"] = title
        assert model == "claude-opus-5-5" and api_key == "k"
        return SeoSuggestion(slug=seen.get("slug", "Python 3.14: New Features"), description="摘要", keywords=["核心词", "长尾词"])

    monkeypatch.setattr(claude, "suggest_metadata", fake)
    r = client.post("/api/enrich", headers=h, json={"title": "我的标题", "body": "正文"}).json()
    assert r == {"title": "我的标题", "slug": "python-3-14-new-features", "description": "摘要", "keywords": ["核心词", "长尾词"]}
    assert seen["title"] == "我的标题"  # AI 拿到的是作者的标题，返回里没有 AI 改写的标题
    # 标题框空着：用正文开头的「# 标题」
    r = client.post("/api/enrich", headers=h, json={"title": "", "body": "# 正文里的标题\n\n内容"}).json()
    assert r["title"] == "正文里的标题"
    seen["slug"] = "升级指南"  # AI 给的 slug 没有英文（不可用）→ 退回按标题转拼音
    r = client.post("/api/enrich", headers=h, json={"title": "正文里的标题", "body": "x"}).json()
    assert r["slug"] == "zhengwen-li-biaoti"
    # 都没有：要求先填标题，不让 AI 编
    r = client.post("/api/enrich", headers=h, json={"title": "", "body": "内容"})
    assert r.status_code == 400 and "先填标题" in r.json()["detail"]


def test_enrich_unexpected_error_is_502(client, monkeypatch):
    h = login(client)

    async def boom(title, body, model, api_key, base_url):
        raise RuntimeError("x")

    monkeypatch.setattr(claude, "suggest_metadata", boom)
    r = client.post("/api/enrich", headers=h, json={"title": "T", "body": "正文"})
    assert r.status_code == 502 and r.json()["code"] == "upstream_error"
