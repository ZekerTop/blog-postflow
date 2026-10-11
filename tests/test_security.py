"""上线前的安全修复：真实 IP 限速、AI 地址防内网探测（SSRF）、安全响应头、改密码后旧会话失效。"""
import pytest
from fastapi.testclient import TestClient

from app.core.errors import BadRequest
from app.core.security import check_public_url, real_ip
from app.main import create_app
from tests.conftest import login, make_settings

TRUSTED = ["127.0.0.1/32", "::1/128", "172.16.0.0/12"]


def test_real_ip_only_trusts_proxy():
    assert real_ip("172.17.0.1", "203.0.113.9", TRUSTED) == "203.0.113.9"  # nginx → Docker 网桥
    assert real_ip("127.0.0.1", "203.0.113.9", TRUSTED) == "203.0.113.9"
    assert real_ip("198.51.100.7", "1.2.3.4", TRUSTED) == "198.51.100.7"  # 直连的人伪造头没用
    assert real_ip("127.0.0.1", "not-an-ip", TRUSTED) == "127.0.0.1"
    assert real_ip("testclient", "1.2.3.4", TRUSTED) == "testclient"


def test_login_limit_is_per_visitor_behind_proxy(fake_github, tmp_path):
    """反代后面：一个人输错 5 次只锁他自己，不会把站长也锁在门外。"""
    c = TestClient(create_app(make_settings(tmp_path), lambda t: fake_github.client(t)), client=("172.17.0.1", 40000))
    for _ in range(5):
        c.post("/api/login", json={"password": "bad"}, headers={"X-Real-IP": "203.0.113.9"})
    assert c.post("/api/login", json={"password": "pw"}, headers={"X-Real-IP": "203.0.113.9"}).status_code == 429
    assert c.post("/api/login", json={"password": "pw"}, headers={"X-Real-IP": "198.51.100.1"}).status_code == 200


@pytest.mark.parametrize("url", ["http://127.0.0.1:6379", "http://localhost:8080/v1", "http://10.1.2.3/v1",
                                 "http://172.17.0.1:6379", "http://192.168.1.1", "http://169.254.169.254/latest",
                                 "http://[::1]:3306", "https://relay.internal.test/v1", "ftp://x.com", "javascript:alert(1)"])
def test_private_or_bad_ai_urls_rejected(url):
    with pytest.raises(BadRequest):
        check_public_url(url)


def test_public_ai_url_allowed():
    check_public_url("https://api.deepseek.com/v1")
    check_public_url("https://relay.example.com/claudecode")


def test_ai_base_url_cannot_point_inside_server(client):
    h = login(client)
    r = client.post("/api/config/secrets", headers=h, json={"ai_base_url": "http://172.17.0.1:6379"})
    assert r.status_code == 400 and "内网" in r.json()["detail"]
    r = client.post("/api/config/ai/test", headers=h,
                    json={"provider": "openai", "base_url": "http://127.0.0.1:6379", "model": "m", "api_key": "k"})
    assert r.status_code == 400  # 「测试连接」也不能拿来探测内网


def test_security_headers(client):
    r = client.get("/")
    assert "script-src 'self'" in r.headers["content-security-policy"]
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
    assert r.headers["x-frame-options"] == "DENY" and r.headers["x-content-type-options"] == "nosniff"
    assert "<script>" not in r.text  # CSP 禁止内联脚本，页面里不能有
    login(client)
    assert client.get("/api/me").headers["cache-control"] == "no-store"


def test_password_change_logs_out_other_sessions(fake_github, tmp_path):
    app = create_app(make_settings(tmp_path, password_hash=""), lambda t: fake_github.client(t))
    a, b = TestClient(app), TestClient(app)
    code = app.state.config.setup_code
    ha = {"X-CSRF-Token": a.post("/api/setup", json={"code": code, "password": "first-pass-1"}).json()["csrf"]}
    b.post("/api/login", json={"password": "first-pass-1"})
    assert b.get("/api/me").status_code == 200
    r = a.post("/api/password", headers=ha, json={"current": "first-pass-1", "new": "second-pass-2"}).json()
    assert a.get("/api/me").status_code == 200 and r["csrf"]  # 改密码的这台继续可用
    res = b.get("/api/me")
    assert res.status_code == 401 and "重新登录" in res.json()["detail"]  # 另一台被踢下线
