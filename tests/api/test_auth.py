from tests.conftest import POST, login


def test_requires_login(client):
    assert client.get("/api/me").status_code == 401
    r = client.post("/api/login", json={"password": "bad"})
    assert r.status_code == 401 and r.json()["code"] == "unauthorized"


def test_login_rate_limit(client):
    for _ in range(5):
        client.post("/api/login", json={"password": "bad"})
    assert client.post("/api/login", json={"password": "pw"}).status_code == 429


def test_csrf_required(client):
    login(client)
    r = client.post("/api/preview", json={"post": POST, "blog_ids": ["blog1"]})
    assert r.status_code == 403 and r.json()["code"] == "forbidden"


def test_static_assets(client):
    assert client.get("/").status_code == 200
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/style.css").status_code == 200
