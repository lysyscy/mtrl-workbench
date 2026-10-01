#!/usr/bin/env python
r"""`TAIL-64` **`P4-d-b`** 收尾：把台账 `§15` 与排期 `§14.3` 里 `TAIL-64` 那两行改到与实况一致。

**为什么单独落一个脚本**：要改的字符串里**全是反引号 / 全角括号**（`⇒ 余 **`P4-d-c`**…`）——
⚠️ 在 PowerShell 里内联跑 `python -c` 会被吞（本仓老坑）⇒ 一律落成文件再跑。

用法：`python tools/oneoff/_p4db_docs.py`（干跑）· `… --write`
"""

from __future__ import annotations

import argparse
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
PLAN = ROOT / ".workbuddy" / "plans" / "开发计划-主文档.md"
NL = "\r\n"

#: §15 里 `TAIL-64` 那行的**结尾**（原文 · 逐字）
S15_OLD = "⇒ 余 **`P4-d-b`** 与 **`P4-c`**（⚠️ 待定裁）与 **`P5`**） |"
S15_NEW = (
    "⇒ 余 **`P4-c`**（⚠️ 待定裁）与 **`P5`**）；⭐⭐ **同日 `P4-d-b` 也办完 ⇒ 全站 11 处项目按钮全清**"
    "（出口 `PJB` 补 **`cls` / `attrs`** 两参（**默认值都保持旧行为** ⇒ `m03` 那处试点零变化）；"
    "落点 = `index.html` **7** ＋ `legacy.js` **1** ＋ `pages-a.js` **2** ＋ `pages-b.js` **1** ＝ **11 处**："
    "**行数全 Δ0 · 渲染字节逐字节不变**（脚本 `tools/oneoff/_p4d_pjb.py` 逐处自证 `渲染 == 原文`）；"
    "`U1` = 换号 **7 行** ＋ 消号 **7 条幽灵**（净 **0**）；判据 = `test_项目选择按钮只走统一出口_PJB`（试点）"
    "＋ ⭐ **新写扫描式** `test_项目选择按钮全站都走统一出口`（**先查内核再扫**）；"
    "反向灵敏度 `tools/mut/_mut_pjb.py` **2/2 → 4/4**；⚠️ **同批把 3 条「钉源码形态」的老判据改成委托形式**"
    "（`test_imp_shell` / `test_page_m06` / `test_wired_m05` —— 抽件必然碰掉那批）；"
    "⭐ **范围是量出来的**（`tools/oneoff/_p4db_survey.py` 扫全部拆件：壳侧 **12 枚**带 `▼` 的样板按钮，"
    "其中 `ui.js` 的「**选时间**」`tmBtn` 样板同款但**另一家族** ⇒ 判据里写成**唯一一处例外** ＋ 立 `TAIL-196`）"
    "⇒ 实况见施工图 **§8.9**） |")

#: §14.3 里 `TAIL-64` 排期行的**结尾**（⚠️ 原文见干跑打印 · 脚本按"标记 → 行尾"换，⛔ 不逐字锚）
S143_MARK = "⛔ **`TAIL-65` 先落**"
S143_NEW = ("⛔ **`TAIL-65` 先落**（✅ 已落；⭐⭐ 2026-09-30 **`P4-a` ＋ `P4-b` ＋ `P4-d-a` ＋ `P4-d-b` 都办完**"
            " ⇒ 筛选栏外壳 **22 处**全清 ＋ 项目选择按钮 **11 处**全清（出口 `PJB`，补 `cls`/`attrs` 两参）；"
            "见 §15 §一 本行与施工图 §8.5/§8.6/§8.9）· ⏭ 余 **`P4-c`（口径说明 · 待用户定裁）** 与 **`P5`（最终目的）**"
            " ＋ 小尾巴 `TAIL-196`（「选时间」那枚要不要也收） |")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    t = PLAN.read_text(encoding="utf-8", newline="").replace("\r\n", "\n")
    #: ⚠️ 逐字锚点**易被全角/半角差一格打空** ⇒ 改用"**标记 → 行尾**"的稳健改法：
    #:    先定位 §15 里 `TAIL-64` 那一行，再把它从 `⇒ 余 **` 起、到行尾 ` |` 止整段换掉。
    rows = [ln for ln in t.split("\n") if ln.startswith("| `TAIL-64`")]
    for r in rows:
        print(f"   行首 = {r[:60]!r}")
    assert len(rows) == 2, f"⛔ 全文件里 `TAIL-64` 表行应恰好 2 行（§15 ＋ §14.3），实得 {len(rows)}"
    row15 = rows[0] if "前端表格/筛选/行模板" in rows[0] else rows[1]
    mark = "⇒ 余 **`P4-d-b`**"
    i = row15.find(mark)
    assert i > 0, "⛔ §15 那行里找不到 `⇒ 余 **`P4-d-b`**` 标记 —— 先核对原文"
    print(f"   §15 行尾原文 = {row15[i:]!r}")
    fix15 = row15[:i] + S15_NEW
    assert fix15.endswith(" |")
    #: §14.3 同样用**标记 → 行尾**（⛔ 别逐字锚：全角/变体选择符差一格就打空）
    row143 = rows[0] if rows[0] is not row15 else rows[1]
    k = row143.find(S143_MARK)
    assert k > 0, "⛔ §14.3 那行里找不到 `⛔ **`TAIL-65` 先落**` 标记 —— 先核对原文"
    print(f"   §14.3 行尾原文 = {row143[k:]!r}")
    fix143 = row143[:k] + S143_NEW
    assert fix143.endswith(" |")

    if not args.write:
        print("\n（干跑：⛔ 未写）")
        return 0

    out = t.replace(row15, fix15, 1).replace(row143, fix143, 1)
    PLAN.write_text(out.replace("\n", NL), encoding="utf-8", newline="")
    back = PLAN.read_text(encoding="utf-8", newline="").replace("\r\n", "\n")
    assert back == out and "⇒ 余 **`P4-d-b`**" not in back, "⛔ 写回自校验不过"
    print("✅ 已写：§15 ＋ §14.3 的 `TAIL-64` 两行都改到与实况一致")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
