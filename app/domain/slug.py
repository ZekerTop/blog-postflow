"""按标题生成网址 slug：中文按词转拼音（jieba 分词 + pypinyin），英文、数字原样小写，其余符号当分隔。
例：「Python发布20多项更新」→ python-fabu-20-duoxiang-gengxin。百度能识别拼音网址，也比中文网址（会被转成 %E5…）干净。"""
import logging
import re
import unicodedata
from datetime import date

MAX_LEN = 60  # 网址太长对搜索不友好，按词截断
# 标题里常见、对搜索没有意义的虚词，生成网址时去掉
STOP = set("的 了 吗 呢 吧 啊 呀 之 与 和 及 或 是 在 把 被 给 对 也 都 就 还 而".split())
_CJK = re.compile(r"[㐀-鿿]")
_ready = False


def _init() -> None:
    global _ready
    if not _ready:
        import jieba
        jieba.setLogLevel(logging.WARNING)
        _ready = True


def slugify(title: str) -> str:
    _init()
    import jieba
    from pypinyin import Style, lazy_pinyin

    text = unicodedata.normalize("NFKC", title or "").lower()
    parts: list[str] = []
    for tok in jieba.cut(text):
        tok = tok.strip()
        if not tok or tok in STOP:
            continue
        if _CJK.search(tok):
            # 一个词内的拼音连写（shengji），词与词之间用连字符；词里夹着的英文数字照样保留
            word = "".join(lazy_pinyin(tok, style=Style.NORMAL, errors=lambda s: re.sub(r"[^a-z0-9]", "", s)))
            pieces = [re.sub(r"[^a-z0-9]", "", word)]
        else:
            pieces = re.split(r"[^a-z0-9]+", tok)  # GPT-5.5 → gpt / 5 / 5
        parts += [p for p in pieces if p]
    out: list[str] = []
    for p in parts:  # 不去重：GPT-5.5 里的 5-5 是有意义的
        if len("-".join(out + [p])) > MAX_LEN:
            break
        out.append(p)
    return "-".join(out) or f"post-{date.today():%Y%m%d}"
