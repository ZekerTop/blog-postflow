import base64
import json
from urllib.parse import unquote
from datetime import datetime

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import BlogConfig, Settings
from app.core.security import hash_password
from app.domain.post import Post
from app.integrations.github import GitHub
from app.main import create_app
from app.services.config import ConfigService
from app.services.publisher import Publisher
from app.storage.config_store import ConfigStore
from app.storage.publish_store import PublishStore

BLOGS = [
    BlogConfig(id="blog1", name="b1", repo="o/r1", posts_dir="source/_posts", adapter="hexo"),
    BlogConfig(id="blog2", name="b2", repo="o/r2", posts_dir="source/_posts", adapter="hexo",
               options={"more_marker": "<!-- more -->"}, post_url="https://x.cn/{year}/{slug}/"),
]
POST = {"title": "T", "slug": "my-post", "date": "2026-10-05T10:00:00", "tags": ["a"], "categories": ["c"],
        "description": "d", "keywords": ["k"], "body": "p1\n\np2\n\np3"}
BODY = "第一段。\n\n第二段。\n\n```python\na = 1\n\nb = 2\n```\n\n第四段。"


def make_post(**kw) -> Post:
    base = dict(title="标题：测试", slug="test-post", date=datetime(2026, 10, 5, 9, 30), tags=["AI", "Claude"],
                categories=["教程"], description="摘要", keywords=["k1", "k2"], body=BODY)
    return Post(**(base | kw))


class FakeGitHub:
    """内存版 GitHub：files[(repo, path)] = sha，content[(repo, path)] = 文本；fail_repos 里的仓库写入返回 500。
    支持 Contents API（读写单文件）、git tree 列表、Git Data API 多文件提交、Actions 运行查询。"""

    def __init__(self):
        self.files, self.content, self.puts, self.fail_repos = {}, {}, [], set()
        self.auth: dict[str, set[str]] = {}  # 仓库 → 用过的 Authorization 头
        self.commits: list[tuple[str, str, dict]] = []  # (仓库, 提交信息, {路径: 内容或 None})
        self._trees: dict[str, dict] = {}

    def add(self, repo: str, path: str, text: str) -> None:
        self.content[(repo, path)] = text
        self.files[(repo, path)] = f"sha-{len(self.content)}"

    def handler(self, req: httpx.Request) -> httpx.Response:
        parts = req.url.path.split("/")
        repo = f"{parts[2]}/{parts[3]}"
        self.auth.setdefault(repo, set()).add(req.headers.get("authorization", ""))
        p = req.url.path
        if "/actions/runs" in p:
            return httpx.Response(200, json={"workflow_runs": [
                {"name": "deploy", "status": "in_progress", "conclusion": None, "html_url": "https://gh/run/1"}]})
        if "/git/" in p:
            return self._git(req, repo, p)
        path = unquote("/".join(parts[5:]))
        if req.method == "GET":
            sha = self.files.get((repo, path))
            if not sha:
                return httpx.Response(404, json={"message": "Not Found"})
            text = self.content.get((repo, path), "")
            return httpx.Response(200, json={"sha": sha, "content": base64.b64encode(text.encode()).decode()})
        if repo in self.fail_repos:
            return httpx.Response(500, json={"message": "boom"})
        body = json.loads(req.content)
        self.puts.append((repo, path, body))
        sha = f"sha{len(self.puts)}"
        self.files[(repo, path)] = sha
        self.content[(repo, path)] = base64.b64decode(body["content"]).decode()
        return httpx.Response(201, json={"commit": {"sha": sha * 5, "html_url": f"https://gh/commit/{sha}"}})

    def _git(self, req: httpx.Request, repo: str, p: str) -> httpx.Response:
        if "/git/trees/" in p and req.method == "GET":
            return httpx.Response(200, json={"truncated": False, "tree": [
                {"path": path, "type": "blob"} for (r, path) in self.files if r == repo]})
        if "/git/ref/heads/" in p:
            return httpx.Response(200, json={"object": {"sha": "head"}})
        if "/git/commits/" in p and req.method == "GET":
            return httpx.Response(200, json={"tree": {"sha": "base"}})
        if repo in self.fail_repos:
            return httpx.Response(500, json={"message": "boom"})
        body = json.loads(req.content)
        if p.endswith("/git/trees"):
            tid = f"tree{len(self._trees)}"
            self._trees[tid] = {t["path"]: t.get("content") for t in body["tree"]}
            return httpx.Response(201, json={"sha": tid})
        if p.endswith("/git/commits"):
            changes = self._trees[body["tree"]]
            for path, text in changes.items():
                if text is None:
                    self.files.pop((repo, path), None)
                    self.content.pop((repo, path), None)
                else:
                    self.add(repo, path, text)
            self.commits.append((repo, body["message"], changes))
            return httpx.Response(201, json={"sha": f"c{len(self.commits)}" * 5, "html_url": "https://gh/commit/c"})
        if "/git/refs/heads/" in p:
            return httpx.Response(200, json={})
        return httpx.Response(404, json={"message": "Not Found"})

    def client(self, token: str = "t") -> GitHub:
        return GitHub(token, transport=httpx.MockTransport(self.handler))


@pytest.fixture
def fake_github():
    return FakeGitHub()


def make_settings(tmp_path, **kw) -> Settings:
    base = dict(password_hash=hash_password("pw"), session_secret="s" * 32, github_token="t",
                anthropic_api_key="k", db_file=tmp_path / "db.sqlite", blogs_file=tmp_path / "none.yml",
                cookie_secure=False)
    return Settings(**(base | kw))


def seed(config: ConfigService) -> ConfigService:
    for b in BLOGS:
        config.store.save_blog(b)
    return config


@pytest.fixture
def config(fake_github, tmp_path):
    settings = make_settings(tmp_path)
    return seed(ConfigService(settings, ConfigStore(settings.db_file), lambda token: fake_github.client(token)))


@pytest.fixture
def publisher(config, tmp_path):
    return Publisher(config, PublishStore(tmp_path / "db.sqlite"))


@pytest.fixture
def client(fake_github, tmp_path):
    app = create_app(make_settings(tmp_path), lambda token: fake_github.client(token))
    seed(app.state.config)
    return TestClient(app)


def login(c: TestClient) -> dict:
    csrf = c.post("/api/login", json={"password": "pw"}).json()["csrf"]
    return {"X-CSRF-Token": csrf}


@pytest.fixture(autouse=True)
def fake_dns(monkeypatch):
    """测试不联网：IP 原样返回，localhost / *.internal.test 解析到内网，其他域名一律当公网。"""
    import ipaddress
    import socket

    def getaddrinfo(host, port, *a, **kw):
        try:
            ip = str(ipaddress.ip_address(host))
        except ValueError:
            ip = {"localhost": "127.0.0.1"}.get(host) or ("10.0.0.5" if host.endswith(".internal.test") else "93.184.216.34")
        fam = socket.AF_INET6 if ":" in ip else socket.AF_INET
        return [(fam, socket.SOCK_STREAM, 6, "", (ip, port))]

    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
