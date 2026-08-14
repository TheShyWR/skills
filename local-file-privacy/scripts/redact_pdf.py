#!/usr/bin/env python3
"""本地 PDF 打码：仅涂"冒号后的值"，标签保留。零网络调用。"""
import re
import argparse

try:
    import fitz  # PyMuPDF
except ImportError:
    raise SystemExit("缺少依赖 PyMuPDF：请先 `pip install pymupdf`")

# 统一口径：只涂"冒号后的值"
#   捕获组=1 -> 涂括号里的值（标签式字段，标签本身保留）
#   无括号的格式类只写号码 -> grp=0 即值本身
PATTERNS = [
    (r"\d{17}[\dXx]", 0),                       # 身份证：只涂号码
    (r"1[3-9]\d{9}", 0),                        # 手机号：只涂号码
    (r"姓名[：:\s]*([\u4e00-\u9fa5]{2,4})", 1),  # 姓名：只涂名字
    (r"性别[：:\s]*(男|女)", 1),                # 性别：只涂值
    (r"年龄[：:\s]*(\d{1,3})", 1),              # 年龄：只涂值
    (r"(\d{1,3})岁", 1),                        # 年龄（数字+岁）：只涂数字
]


def redact(src, dst):
    doc = fitz.open(src)
    total = 0
    for page in doc:
        text = page.get_text()
        if not text.strip():
            continue  # 纯扫描件无文本层，需 OCR，跳过
        for pat, grp in PATTERNS:
            for m in re.finditer(pat, text):
                target = m.group(grp) if grp else m.group(0)
                for rect in page.search_for(target):
                    page.add_redact_annot(rect, fill=(0, 0, 0))
                    total += 1
        page.apply_redactions()  # 真删除原文，不是盖黑框
    doc.save(dst)
    return total


def main():
    ap = argparse.ArgumentParser(description="本地 PDF 打码（值-only，零网络）")
    ap.add_argument("src", help="输入 PDF 路径")
    ap.add_argument("--dst", help="输出路径（默认 <src>_已打码.pdf）")
    args = ap.parse_args()
    src = args.src
    if src.lower().endswith(".pdf"):
        dst = args.dst or src[:-4] + "_已打码.pdf"
    else:
        dst = args.dst or src + "_已打码.pdf"
    n = redact(src, dst)
    print(f"redacted_spans: {n}")
    print(f"saved: {dst}")


if __name__ == "__main__":
    main()
