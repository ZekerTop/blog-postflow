"""构建产物里的 CRLF 转成 LF，和 Windows 上 hexo d 推送时 git（core.autocrlf=true）做的一样。

源码里不少文件是 CRLF（robots.txt、部分 svg），原样复制进 public；Windows 推送时 git 把文本文件转成了 LF，
线上一直是 LF。这里按 git 判断文本 / 二进制的规则（含 NUL、孤立 CR、不可打印字符过多 = 二进制）只转文本文件。
用法：python3 normalize-eol.py <目录>
"""
import sys
from pathlib import Path


def is_binary(data: bytes) -> bool:
    if b"\0" in data or data.replace(b"\r\n", b"").count(b"\r"):
        return True
    printable = nonprintable = 0
    for c in data:
        if c == 127 or (c < 32 and c not in (8, 9, 10, 12, 13, 27)):
            nonprintable += 1
        else:
            printable += 1
    return (printable >> 7) < nonprintable


def main(root: str) -> None:
    changed = 0
    for p in Path(root).rglob("*"):
        if not p.is_file():
            continue
        data = p.read_bytes()
        if b"\r\n" in data and not is_binary(data):
            p.write_bytes(data.replace(b"\r\n", b"\n"))
            changed += 1
    print(f"换行符：{changed} 个文件 CRLF → LF")


if __name__ == "__main__":
    main(sys.argv[1])
