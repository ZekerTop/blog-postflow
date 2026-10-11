"""按标题生成拼音网址。"""
import pytest

from app.domain.post import SLUG_RE
from app.domain.slug import MAX_LEN, slugify


@pytest.mark.parametrize("title,expected", [
    ("Python发布20多项更新", "python-fabu-20-duoxiang-gengxin"),
    ("Python 3.14 新特性与升级指南", "python-3-14-xin-texing-shengji-zhinan"),
    ("Claude Code 的三个提效技巧", "claude-code-sange-tixiao-jiqiao"),
    ("GPT-5.5 和 Claude Opus 5.5 有什么区别？", "gpt-5-5-claude-opus-5-5-you-shenme-qubie"),
])
def test_titles(title, expected):
    assert slugify(title) == expected


def test_polyphones_read_as_words():
    assert slugify("银行卡") == "yinhangka"  # 「行」在词里读 hang
    assert slugify("重新升级") == "chongxin-shengji"  # 「重」读 chong


def test_always_valid_and_short():
    long = "国内如何仅通过命令行方式快速完成部署迁移各类静态博客以及常见问题的完整解决方案汇总"
    s = slugify(long)
    assert len(s) <= MAX_LEN and SLUG_RE.match(s) and not s.endswith("-")
    for t in ["", "？？？", "【纯干货】", "  空格  ", "Ｃｈａｔ　ＧＰＴ（全角）", "emoji 🚀 测试"]:
        assert SLUG_RE.match(slugify(t)), t
    assert slugify("？？？").startswith("post-")
    assert slugify("Ｃｈａｔ　ＧＰＴ") == "chat-gpt"


def test_slug_endpoint_and_ai_uses_title(client, monkeypatch):
    from app.domain.post import SeoSuggestion
    from app.integrations import claude
    from tests.conftest import login
    h = login(client)
    assert client.get("/api/slug", params={"title": "Python发布20多项更新"}).json() == {"slug": "python-fabu-20-duoxiang-gengxin"}
    assert client.get("/api/slug", params={"title": "x"}).status_code == 200

    async def fake(title, body, model, api_key, base_url):
        return SeoSuggestion(slug="python-314-upgrade-guide", description="d", keywords=[])

    monkeypatch.setattr(claude, "suggest_metadata", fake)
    r = client.post("/api/enrich", headers=h, json={"title": "Python 3.14 升级指南", "body": "正文"}).json()
    assert r["slug"] == "python-314-upgrade-guide" and r["title"] == "Python 3.14 升级指南"
