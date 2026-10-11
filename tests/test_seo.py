"""AI 元数据兜底清理。"""
from app.domain.post import SeoSuggestion
from app.domain.seo import DESC_MAX, SLUG_MAX, clean_description, clean_slug, clean_terms, polish


def test_keywords_deduped_split_limited():
    kw = ["Python 3.14 升级", "python 3.14 升级", "Python教程、国内镜像", "#Hexo", "a", "这是一个非常非常非常非常长的关键词堆砌示例啊",
          "价格", "怎么用", "区别", "2026", "多余1", "多余2"]
    out = clean_terms(kw, 8, 2, 20)
    assert out[:4] == ["Python 3.14 升级", "Python教程", "国内镜像", "Hexo"]
    assert len(out) == 8 and "a" not in out and all(len(k) <= 20 for k in out)
    many = [f"关键词{i}" for i in range(40)]
    assert len(polish(SeoSuggestion(slug="x", description="d", keywords=many)).keywords) == 30


def test_description_cleaned():
    assert clean_description("本文将介绍了：\n“Python 3.14”  升级方法。") == "Python 3.14 升级方法。"
    long = "第一句讲清楚核心关键词Python 3.14 升级的完整方法和注意事项。" * 6
    out = clean_description(long)
    assert len(out) <= DESC_MAX and out.endswith("。")


def test_polish_keeps_good_output_unchanged():
    m = SeoSuggestion(slug="python-314-upgrade-guide", description="Python 3.14 升级的三种方法，对比兼容性、性能和依赖适配，附常见问题处理。",
                      keywords=["Python 3.14 升级", "Python 3.14 怎么安装", "Python 3.14 性能"])
    assert polish(m) == m


def test_slug_cleaned_or_rejected():
    assert clean_slug("python-314-free-threading-template-strings-upgrade") == "python-314-free-threading-template-strings-upgrade"
    assert clean_slug("Python 3.14: Free-Threading / T-Strings!") == "python-3-14-free-threading-t-strings"
    assert clean_slug("claude-code_vs_codex  guide") == "claude-code-vs-codex-guide"
    assert clean_slug("升级指南") == "" and clean_slug("2026-10") == ""  # 没有英文单词：不可用，退回拼音
    long = "-".join(["word"] * 30)
    assert len(clean_slug(long)) <= SLUG_MAX and not clean_slug(long).endswith("-")
    assert len(clean_slug("a" * 80)) == SLUG_MAX


def test_user_reference_example_passes_through_unchanged():
    """提示词里的参考示例：清理后应原样保留（规则不能把好结果改坏）。"""
    from app.integrations.claude import SYSTEM
    import re
    ref = re.search(r"slug：(.+)\ndescription：(.+)\nkeywords：(.+)", SYSTEM)
    m = SeoSuggestion(slug=ref.group(1), description=ref.group(2), keywords=ref.group(3).split(", "))
    assert polish(m) == m and len(m.keywords) == 30
