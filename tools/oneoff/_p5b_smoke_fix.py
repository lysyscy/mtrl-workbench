#!/usr/bin/env python
r"""`TAIL-64` **`P5-b`** 收尾之一：修**交付面** `demo/_smoke.js` 里那条**钉字面 `<tbody>`** 的断言。

**为什么**：`P5-b` 让 `TBL` **一律**在表体上出 `data-vs="…"` 属性 ⇒ 交付面那条断言
`h.slice(h.indexOf('<tbody>'))` **切不到**（那个字面不再出现）⇒ 它退化成"拿最后 1 个字符当行集"，
于是对照行被报成"没进付款窗口"（`606 通过 / 1 失败`）。
⚠️ 断言**要钉的意图**是"逐行看有没有那条单据" —— 与表体上有没有属性无关 ⇒ 改成**前缀匹配**。

⚠️ 交付面在**仓外**（WPS 云同步树）⇒ ⛔ 改前**先备份**到仓侧 `artifacts/delivery-backups/`；
⚠️ 注释里 ⛔ **不许写工程仓的文件名**（`demo/_links.js` 会判未登记断链 —— 已踩两次）。

用法：`python tools/oneoff/_p5b_smoke_fix.py`（干跑）· `… --write`
"""

from __future__ import annotations

import argparse
import pathlib
import re
import shutil

ROOT = pathlib.Path(__file__).resolve().parents[2]
SMOKE = pathlib.Path(r"D:\工作\AI\PRD编写夹 - Workbuddy专用\demo\_smoke.js")
BACKUPS = ROOT / "artifacts" / "delivery-backups"
BAK_NAME = "_smoke.js-备份-20260930-P5b前.js"

OLD = "const rowsHtml = h.slice(h.indexOf('<tbody>')).split('<tr ').slice(1);"
NEW = ("/* ⚠️ 表体上**会带属性**（如 `data-vs`）⇒ 必须按 **`<tbody` 前缀**切，⛔ 不能带 `>`：\n"
       "       带 `>` 时这句切不到、会退化成\"拿最后 1 个字符当行集\"（整条断言失去区分力、且不报错）。\n"
       "       ⭐ 本断言要钉的是\"逐行看有没有那条单据\" —— 与表体上挂什么属性无关。 */\n"
       "    const _tbs = h.indexOf('<tbody');\n"
       "    const rowsHtml = (_tbs >= 0 ? h.slice(_tbs) : '').split('<tr ').slice(1);")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    assert SMOKE.exists(), f"⛔ 交付面脚本不在预期位置：{SMOKE}"
    txt = SMOKE.read_text(encoding="utf-8")
    assert txt.count(OLD) == 1, f"⛔ 靶串命中 {txt.count(OLD)} 次（期望 1）—— 先核对原文"
    assert re.search(r"<tbody>", txt).group(0) == "<tbody>", "⛔ 还有别处钉字面 `<tbody>`，先全查"
    print("✅ 靶串命中 1 次（交付面里唯一一处钉字面 `<tbody>`）")
    if not args.write:
        print("\n（干跑：⛔ 未写）")
        return 0

    BACKUPS.mkdir(parents=True, exist_ok=True)
    dst = BACKUPS / BAK_NAME
    if not dst.exists():
        shutil.copy2(SMOKE, dst)
        print(f"  ✅ 备份交付面脚本 ⇒ {dst.relative_to(ROOT)}")
    out = txt.replace(OLD, NEW, 1)
    SMOKE.write_text(out, encoding="utf-8", newline="")
    back = SMOKE.read_text(encoding="utf-8")
    assert back == out and "h.indexOf('<tbody>')" not in back, "⛔ 写回自校验不过"
    print("  ✅ 已改：按 `<tbody` **前缀**切（判词意图不变）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
