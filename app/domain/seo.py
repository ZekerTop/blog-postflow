"""AI 生成的描述 / 关键词在用之前统一清理：模型偶尔不守规矩（关键词重复或太多、描述带换行引号、空话开头），
这里兜底，保证进文章的元数据符合国内搜索的习惯。"""
import re
import unicodedata

from .post import SeoSuggestion

DESC_MAX = 150  # 「中国搜索版」两句话 100~130 字；超过 150 在句号处截断
KW_MAX, KW_LEN = 30, (2, 20)
SLUG_MAX = 60
_QUOTES = re.compile(r"[\"'“”‘’「」『』《》]")
_FILLER = re.compile(r"^(本文|这篇文章|这篇|笔者|小编)(将|会|主要|详细)?(介绍|讲解|分享|带你|为你|和大家)?了?[，,：:]?")


def _flat(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("　", " ")).strip()


def clean_description(s: str) -> str:
    s = _FILLER.sub("", _QUOTES.sub("", _flat(s))).strip("，,；; ")
    if len(s) > DESC_MAX:
        cut = max(s.rfind(p, 0, DESC_MAX) for p in "。！？；")
        s = s[:cut + 1] if cut >= 40 else s[:DESC_MAX].rstrip("，,、；; ") + "。"
    return s


def clean_terms(items: list[str], limit: int, min_len: int = 1, max_len: int = 30) -> list[str]:
    """拆开混在一起的（「a,b」「a、b」）、去 # 和引号、按不区分大小写去重、过滤过长过短、限制个数。"""
    out, seen = [], set()
    for raw in items:
        for t in re.split(r"[,，、;；|/]+", raw or ""):
            t = _QUOTES.sub("", _flat(t)).strip("#＃ ")
            if not (min_len <= len(t) <= max_len) or t.lower() in seen:
                continue
            seen.add(t.lower())
            out.append(t)
    return out[:limit]


def clean_slug(s: str) -> str:
    """只留小写字母、数字、单个连字符，按词截到 60 字符内；不含字母（AI 没给好）返回空串，由调用方退回拼音。"""
    s = re.sub(r"[^a-z0-9]+", "-", unicodedata.normalize("NFKC", s or "").lower()).strip("-")
    out = []
    for w in s.split("-"):
        if len("-".join(out + [w])) > SLUG_MAX:
            break
        out.append(w)
    s = "-".join(out) or s[:SLUG_MAX].strip("-")
    return s if re.search(r"[a-z]", s) else ""


def polish(m: SeoSuggestion) -> SeoSuggestion:
    return SeoSuggestion(slug=clean_slug(m.slug), description=clean_description(m.description),
                         keywords=clean_terms(m.keywords, KW_MAX, *KW_LEN))
