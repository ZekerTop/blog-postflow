"""workflows/compare_site.py：博客仓库 Actions 里跑的 SEO 守门脚本。"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("compare_site", ROOT / "workflows" / "compare_site.py")
cs = sys.modules["compare_site"] = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cs)

PAGE = """<html><head><title>{title}</title><meta name="description" content="{desc}">
<link rel="canonical" href="https://x.cn/a.html"><script type="application/ld+json">{{"@type":"Article"}}</script>
<script src="/assets/app.ab8dd57b.js"></script></head><body><h1>{title}</h1><p>{body}</p></body></html>"""


def site(root: Path, pages: dict[str, dict], extra: dict[str, str]) -> Path:
    for rel, kw in pages.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(PAGE.format(**({"title": "T", "desc": "D", "body": "b"} | kw)), encoding="utf-8")
    for rel, text in extra.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return root


BASE_PAGES = {"index.html": {}, "blog/a.html": {}, "googleabc.html": {}}
BASE_FILES = {"CNAME": "blog.example.com", "robots.txt": "User-agent: *", "BingSiteAuth.xml": "<x/>",
              "assets/js/app.ab8dd57b.js": "1", "images/logo.png": "png",
              "sitemap.xml": "<urlset><url><loc>https://x.cn/blog/a.html</loc></url></urlset>"}


def test_identical_build_passes(tmp_path):
    r = cs.compare(site(tmp_path / "l", BASE_PAGES, BASE_FILES), site(tmp_path / "n", BASE_PAGES, BASE_FILES))
    assert not r["blocking"] and r["live_pages"] == 3 and not r["text_changed"]


def test_body_change_warns_and_hashed_assets_are_ignored(tmp_path):
    new_files = {k: v for k, v in BASE_FILES.items() if "app." not in k} | {"assets/js/app.99ff00aa.js": "2"}
    live_files = BASE_FILES | {".DS_Store": "x", "images/.DS_Store": "x", "assets/js/7372.0e670417.js.LICENSE.txt": "l",
                               ".nojekyll": ""}
    r = cs.compare(site(tmp_path / "l", BASE_PAGES, live_files),
                   site(tmp_path / "n", BASE_PAGES | {"blog/a.html": {"body": "最近更新时间变了"}}, new_files))
    assert not r["blocking"] and not r["seo_changed"]
    assert r["text_changed"] == ["blog/a.html"]


def test_new_post_is_fine(tmp_path):
    r = cs.compare(site(tmp_path / "l", BASE_PAGES, BASE_FILES),
                   site(tmp_path / "n", BASE_PAGES | {"blog/new.html": {}}, BASE_FILES))
    assert not r["blocking"] and r["added_pages"] == ["blog/new.html"]


def test_blocks_removed_page_file_sitemap_and_cname(tmp_path):
    live = site(tmp_path / "l", BASE_PAGES, BASE_FILES)
    new_files = {k: v for k, v in BASE_FILES.items() if k not in ("BingSiteAuth.xml", "images/logo.png")}
    new_files |= {"CNAME": "other.com", "sitemap.xml": "<urlset></urlset>"}
    r = cs.compare(live, site(tmp_path / "n", {"index.html": {}}, new_files))
    assert r["blocking"]
    assert r["removed_pages"] == ["blog/a.html", "googleabc.html"]
    assert r["removed_files"] == ["BingSiteAuth.xml", "images/logo.png"]
    assert r["removed_sitemap_urls"] == ["https://x.cn/blog/a.html"]
    assert r["guarded_changed"] == ["CNAME（内容变化）"]
    assert "❌ 消失的页面" in cs.report(r)


def test_seo_field_change_warns_but_does_not_block(tmp_path):
    r = cs.compare(site(tmp_path / "l", BASE_PAGES, BASE_FILES),
                   site(tmp_path / "n", BASE_PAGES | {"blog/a.html": {"title": "新标题"}}, BASE_FILES))
    assert not r["blocking"]
    assert r["seo_changed"][0]["page"] == "blog/a.html"
    assert set(r["seo_changed"][0]["fields"]) == {"title", "h1"}


def test_main_exit_code_and_summary(tmp_path, monkeypatch):
    live = site(tmp_path / "l", BASE_PAGES, BASE_FILES)
    new = site(tmp_path / "n", {"index.html": {}}, BASE_FILES)
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    monkeypatch.chdir(tmp_path)
    assert cs.main(["x", str(live), str(new)]) == 1
    assert "有阻断项" in summary.read_text(encoding="utf-8")
    assert (tmp_path / "compare-report.json").exists()


def test_allowed_removals_do_not_block(tmp_path):
    live = site(tmp_path / "l", BASE_PAGES, BASE_FILES)
    new = site(tmp_path / "n", {k: v for k, v in BASE_PAGES.items() if k != "blog/a.html"},
               BASE_FILES | {"sitemap.xml": "<urlset></urlset>"})
    allow = tmp_path / "allowed-removals.txt"
    allow.write_text("# 2026-10-09 删除 docs/blog/a.md\na.html\na/index.html\n", encoding="utf-8")
    r = cs.compare(live, new, cs.load_allowed(allow))
    assert not r["blocking"]
    assert r["allowed_removals"] == ["blog/a.html", "https://x.cn/blog/a.html"]
    assert "按放行名单删除" in cs.report(r)
    # 名单里没写的照样拦
    r = cs.compare(live, new, ["other.html"])
    assert r["blocking"] and r["removed_pages"] == ["blog/a.html"]


def test_allow_matching_is_by_path_suffix():
    assert cs.is_allowed("blog/claude/x.html", ["x.html"])
    assert cs.is_allowed("blog/claude/x.html", ["blog/claude/*.html"])
    assert not cs.is_allowed("blog/claude/ax.html", ["x.html"])  # 不能误伤同名结尾的其他文章
    assert cs.is_allowed("https://blog.example.com/blog/claude/x.html", ["x.html"])


def butterfly(body: str, aside: str = "侧边栏") -> str:
    return (f'<html><head><title>T</title></head><body><aside>{aside}</aside><article class="post-content" '
            f'id="article-container"><div class="note"><p>{body}</p></div><div>尾</div></article></body></html>')


def test_old_page_body_change_blocks(tmp_path):
    """渲染器 / 插件换掉时老文章正文变了，SEO 字段可能一个不变，必须拦下。"""
    pages = {"posts/a/index.html": butterfly("<code>x</code>"), "posts/b/index.html": butterfly("b")}
    live = site(tmp_path / "l", {}, BASE_FILES | pages)
    new = site(tmp_path / "n", {}, BASE_FILES | pages | {"posts/a/index.html": butterfly("<code>y</code>", "新侧边栏"),
                                                       "posts/b/index.html": butterfly("b", "新侧边栏")})
    r = cs.compare(live, new)
    assert r["blocking"] and r["body_changed"] == ["posts/a/index.html"] and not r["seo_changed"]
    assert "正文变了" in cs.report(r)
    # 主动改的：登记后放行
    r = cs.compare(live, new, ["a/index.html"])
    assert not r["blocking"] and r["allowed_changes"] == ["posts/a/index.html"]


def test_body_check_skips_lists_and_404(tmp_path):
    vp = '<html><body><div class="theme-default-content"><p>{}</p></div></body></html>'
    icarus = '<html><body><article class="card-content article"><div class="content">{}</div></article>' \
             '<article class="card-content article"><div class="content">摘要二</div></article></body></html>'
    live = site(tmp_path / "l", {}, BASE_FILES | {"404.html": vp.format("随机一"), "index.html": icarus.format("摘要一")})
    new = site(tmp_path / "n", {}, BASE_FILES | {"404.html": vp.format("随机二"), "index.html": icarus.format("新文章")})
    r = cs.compare(live, new)
    assert not r["blocking"] and not r["body_changed"]


def test_body_parser_handles_nested_same_tag():
    p = cs.BodyParser()
    p.feed('<div class="theme-default-content"><div><img src="a.png"><br/>x</div> y</div><div>外面</div>')
    assert p.body == '<div><img src="a.png"><br/>x</div> y'


def test_body_ignores_entity_encoding_of_attributes():
    """marked 每次构建随机把 mailto 地址编码成十进制 / 十六进制实体，内容一样不算变化。"""
    a, b = cs.BodyParser(), cs.BodyParser()
    a.feed('<article id="article-container"><a href="mailto:&#115;&#x75;@x.com">s&amp;u</a></article>')
    b.feed('<article id="article-container"><a href=\'mailto:&#x73;&#117;@x.com\'>s&#38;u</a></article>')
    assert a.body == b.body == '<a href="mailto:su@x.com">s&u</a>'
