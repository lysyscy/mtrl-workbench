"""侦察材料域：把壳里 V.m06 / V.m07 / V.m08 三片按**括号配平**切出来，列依赖。"""
from __future__ import annotations

import io
import re
from pathlib import Path

SHELL = Path(__file__).resolve().parents[1] / "backend" / "app" / "web" / "index.html"


def slice_view(text: str, tag: str) -> tuple[int, str]:
    """返回 (起始行号, 切片正文)。用**花括号配平**定终点 —— 不靠"下一个 V."。"""
    start = text.find(f"\n{tag}=")
    if start < 0:
        return -1, ""
    start += 1
    # 从 `=` 之后找第一个 `{`，开始配平
    i = text.find("{", start)
    if i < 0:
        return -1, ""
    depth = 0
    j = i
    while j < len(text):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                break
        j += 1
    body = text[start:j + 1]
    return text[:start].count("\n") + 1, body


def main() -> None:
    text = io.open(SHELL, encoding="utf-8").read()
    for tag in ("V.m06", "V.m07", "V.m08"):
        ln, body = slice_view(text, tag)
        print("=" * 72)
        print("%s  L%d  共 %d 行 / %d 字符" % (tag, ln, body.count("\n") + 1, len(body)))
        acts = sorted(set(re.findall(r'data-act="([A-Za-z0-9_]+)"', body)))
        print("  动作(%d)：%s" % (len(acts), " ".join(acts)))
        ids = sorted(set(re.findall(r"\b([A-Z][A-Za-z0-9_]{1,18})\b", body)))
        print("  大写标识符：%s" % " ".join(ids))
        print("  归一迹象：%s" % [x for x in ("new Map(", "reduce(", "Set(", ".filter(", "pjRowOf", "pjDisp", "pjKey") if x in body])
    print()


if __name__ == "__main__":
    main()
