from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import login, make_settings

BLOG = {"id": "blog9", "name": "新博客", "repo": "o/r9", "posts_dir": "source/_posts", "adapter": "hexo-butterfly",
        "options_yaml": "date_format: '%Y-%m-%d'"}


def test_first_run_setup(fake_github, tmp_path):
    app = create_app(make_settings(tmp_path, password_hash=""), lambda t: fake_github.client(t))
    c = TestClient(app)
    assert c.get("/api/setup").json() == {"needs_setup": True}
    assert (tmp_path / "setup-code.txt").exists()
    assert c.post("/api/setup", json={"code": "wrong", "password": "12345678"}).status_code == 403
    code = app.state.config.setup_code
    assert c.post("/api/setup", json={"code": code, "password": "short"}).status_code == 400
    assert "csrf" in c.post("/api/setup", json={"code": code, "password": "12345678"}).json()
    assert c.get("/api/setup").json() == {"needs_setup": False}
    c.cookies.clear()
    assert c.post("/api/login", json={"password": "12345678"}).status_code == 200


def test_secrets_never_returned(client):
    h = login(client)
    client.post("/api/config/secrets", headers=h, json={"github_token": "ghp_abcdefghijklmnop1234"})
    view = client.get("/api/config").json()["secrets"]
    assert view["github_token"] == {"label": "GitHub Token", "set": True, "hint": "…1234", "source": "page"}
    assert "ghp_" not in client.get("/api/config").text


def test_blog_crud_and_presets(client):
    h = login(client)
    cfg = client.get("/api/config").json()
    assert any(a["name"] == "classic-hexo" for a in cfg["adapters"])
    assert client.post("/api/config/blogs", headers=h, json=BLOG).status_code == 200
    assert client.post("/api/config/blogs", headers=h, json=BLOG).status_code == 409
    bad = client.post("/api/config/blogs", headers=h, json=BLOG | {"id": "x", "adapter": "nope"})
    assert bad.status_code == 400 and "未知 adapter" in bad.json()["detail"]
    assert any(b["id"] == "blog9" for b in client.get("/api/me").json()["blogs"])
    assert client.post("/api/config/blogs/blog9/delete", headers=h).json() == {"ok": True}
    assert not any(b["id"] == "blog9" for b in client.get("/api/me").json()["blogs"])


def test_blog_own_token_for_other_github_account(client, fake_github):
    """博客在别的 GitHub 账号：填专用 Token，只用于这个博客；不回传原文；可清除改回全局。"""
    h = login(client)
    blog = BLOG | {"repo": "other-account/r9", "token": "github_pat_otheraccount_9999"}
    out = client.post("/api/config/blogs", headers=h, json=blog).json()
    assert out["token_set"] and out["token_hint"] == "…9999" and "token" not in out
    assert "github_pat_otheraccount" not in client.get("/api/config").text

    post = {"title": "T", "slug": "s", "date": "2026-10-09T10:00:00", "body": "b"}
    rec = client.post("/api/publish", headers=h, json={"post": post, "blog_ids": ["blog1", "blog9"]}).json()
    assert all(r["ok"] for r in rec["results"])
    assert fake_github.auth["other-account/r9"] == {"Bearer github_pat_otheraccount_9999"}
    assert fake_github.auth["o/r1"] == {"Bearer t"}  # 没填专用 Token 的博客用全局

    # 编辑时不传 token = 保留；传 "" = 清除，改回全局
    client.post("/api/config/blogs/blog9", headers=h, json=BLOG | {"repo": "other-account/r9"})
    assert next(b for b in client.get("/api/config").json()["blogs"] if b["id"] == "blog9")["token_set"]
    client.post("/api/config/blogs/blog9", headers=h, json=BLOG | {"repo": "other-account/r9", "token": ""})
    assert not next(b for b in client.get("/api/config").json()["blogs"] if b["id"] == "blog9")["token_set"]


def test_no_token_anywhere_gives_clear_error(fake_github, tmp_path):
    app = create_app(make_settings(tmp_path, github_token=""), lambda t: fake_github.client(t))
    c = TestClient(app)
    h = login(c)
    c.post("/api/config/blogs", headers=h, json=BLOG)
    r = c.post("/api/config/blogs/blog9/check", headers=h).json()
    assert not r["ok"] and "专用 Token" in r["problems"][0]


def test_ai_settings_and_test_connection(client, monkeypatch):
    from app.integrations import claude, openai_compat
    h = login(client)
    r = client.post("/api/config/secrets", headers=h, json={"ai_provider": "openai", "ai_base_url": "https://api.deepseek.com/v1",
                                                            "anthropic_model": "deepseek-chat", "anthropic_api_key": "sk-deepseek-123456789"})
    view = r.json()
    assert view["ai_provider"] == "openai" and view["ai_base_url"] == "https://api.deepseek.com/v1"
    assert view["anthropic_api_key"]["hint"] == "…6789" and "sk-deepseek" not in client.get("/api/config").text
    assert client.post("/api/config/secrets", headers=h, json={"ai_provider": "gpt"}).status_code == 400
    assert client.post("/api/config/secrets", headers=h, json={"ai_base_url": "api.x.com"}).status_code == 400

    calls = []

    async def fake_ping(model, api_key, base_url):
        calls.append((model, api_key, base_url))
        return {"model": model, "reply": "收到", "ms": 5}

    monkeypatch.setattr(openai_compat, "ping", fake_ping)
    monkeypatch.setattr(claude, "ping", fake_ping)
    assert client.post("/api/config/ai/test", headers=h, json={}).json()["ok"]
    assert calls[-1] == ("deepseek-chat", "sk-deepseek-123456789", "https://api.deepseek.com/v1")
    # 页面上还没保存的值也能测；没填的用已保存的
    client.post("/api/config/ai/test", headers=h, json={"provider": "anthropic", "base_url": "", "model": "claude-opus-5-5"})
    assert calls[-1] == ("claude-opus-5-5", "sk-deepseek-123456789", "")

    async def boom(model, api_key, base_url):
        raise ConnectionError("x")

    monkeypatch.setattr(openai_compat, "ping", boom)
    res = client.post("/api/config/ai/test", headers=h, json={}).json()
    assert res == {"ok": False, "error": "连不上接口地址（ConnectionError）"}
