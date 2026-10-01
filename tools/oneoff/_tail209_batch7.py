"""`TAIL-209` 余项 ② 的第二半：**新装的机器眼第一次跑就抓出的 6 处**（同样按 `D29` 删工程代号）。

⭐ 这正是"给它一把机器眼"的价值：这 6 处**三轮手工捞全都没捞到**（它们既不在"弹窗说明块"里、
也不在批 4 那条"页内 ≥80 字"的靶上）：
`index.html:1537` 页内小 tip 的「（决策 3/4）」· `ui.js:238` 悬停 title 的「（链路 A）」·
`core.js:503/504` 弹窗里「**链路 C**：…（铁律 5/6）」· `core.js:837` toast 的「链路 B：」·
`core.js:1411` 卡头的「（链路 B）」。

⚠️ 每条断言**命中恰好 1 次**（含 CRLF 变体）⇒ 不命中**整批不写**；被 §13.6 入门口令点名 ⇒ 必有 `main()`。
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
W = ROOT / "backend" / "app" / "web"

EDITS: list[tuple[str, str, str]] = [
    ("index.html",
     "<b>设计要点（决策 3/4）：</b>",
     "<b>设计要点：</b>"),
    ("shell/ui.js",
     "title=\"档案里没有该全名 → 触发自动建档（链路 A）\"",
     "title=\"档案里没有该全名 → 触发自动建档\""),
    ("shell/core.js",
     "? `<b>链路 C</b>：集采合同的<b>项目名落在「壳」上</b>，而「单据名称」没能在该壳下的小微关键词里命中 ⇒ 系统<b>不猜</b>（铁律 5/6）。",
     "? `<b>项目名落在「壳」上</b>，而「单据名称」没能在该壳下的小微关键词里命中 ⇒ 系统<b>不猜</b>。"),
    ("shell/core.js",
     ": `<b>链路 C</b>：付款项目名落在<b>壳</b>上，而「单据名称」没能在该壳下的小微关键词里命中 ⇒ 系统<b>不猜</b>（铁律 5/6）。",
     ": `付款项目名落在<b>壳</b>上，而「单据名称」没能在该壳下的小微关键词里命中 ⇒ 系统<b>不猜</b>。"),
    ("shell/core.js",
     "msg += `<br>链路 B：自动扶正 ",
     "msg += `<br>自动扶正 "),
    ("shell/core.js",
     "<h4>待人工指认（链路 B）<span class=\"sp\">",
     "<h4>待人工指认<span class=\"sp\">"),
]


def main() -> int:
    files: dict[str, str] = {}
    bad: list[str] = []
    for name, old, new in EDITS:
        if name not in files:
            files[name] = (W / name).read_text(encoding="utf-8", newline="")
        for o, w in ((old, new), (old.replace("\n", "\r\n"), new.replace("\n", "\r\n"))):
            if files[name].count(o) == 1:
                files[name] = files[name].replace(o, w, 1)
                break
        else:
            bad.append(f"{name}: 命中 {files[name].count(old)} 次 ⇒ {old[:52]!r}")

    if bad:
        if all(files[n].count(new) >= 1 for n, _, new in EDITS):
            print(f"✔ 本批 {len(EDITS)} 处**已经改过**（幂等）")
            return 0
        print("⛔ 以下没命中（整批不写）：")
        for b in bad:
            print("   ", b)
        return 1

    for name, text in files.items():
        (W / name).write_text(text, encoding="utf-8", newline="")
        print(f"✅ 已改 {name}（{len(text)} 字节）")
    print(f"\n共 {len(EDITS)} 处替换 · 全部命中 1 次 ✔")
    return 0


if __name__ == "__main__":
    sys.exit(main())
