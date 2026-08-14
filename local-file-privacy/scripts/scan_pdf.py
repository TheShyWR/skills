#!/usr/bin/env python3
"""本地验证：仅统计敏感模式命中"次数"，绝不输出任何正文。零网络调用。"""
import re
import argparse

try:
    import fitz  # PyMuPDF
except ImportError:
    raise SystemExit("缺少依赖 PyMuPDF：请先 `pip install pymupdf`")

# 标签类命中为"信息性"（标签非敏感，预期存在）；值类命中应为 0
CHECKS = [
    ("身份证_值", r"\d{17}[\dXx]"),
    ("手机号_值", r"1[3-9]\d{9}"),
    ("姓名_标签", r"姓名[：:\s]*[\u4e00-\u9fa5]{2,4}"),
    ("性别_标签", r"性别[：:\s]*(男|女)"),
    ("年龄_岁",   r"\d{1,3}岁"),
    ("年龄_标签", r"年龄[：:\s]*\d{1,3}"),
]


def main():
    ap = argparse.ArgumentParser(description="本地扫描 PDF 残留敏感信息（仅计数）")
    ap.add_argument("src", help="待检查 PDF 路径")
    args = ap.parse_args()
    doc = fitz.open(args.src)
    print(f"file: {args.src}")
    print(f"pages: {doc.page_count}")
    for label, pat in CHECKS:
        cnt = sum(len(re.findall(pat, p.get_text())) for p in doc)
        print(f"{label}_命中: {cnt}")


if __name__ == "__main__":
    main()
