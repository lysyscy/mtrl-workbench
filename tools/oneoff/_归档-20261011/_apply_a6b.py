#!/usr/bin/env python
"""`A6` 收口批（用户「按推荐」）· 一次性（2026-09-29）。

**它改什么**（⚠️ 每处在写前**断言恰好命中一次**；每处写前**重读盘** —— 别拿规划期的旧 `raw` 拼第二处）：
  1. **`m01` 删除按钮**（`TAIL-177` 的 `A` 案）：把「确认删除」**置灰 ＋ 写明为什么**；
     ⭐ 额外加一句**可见的**状态说明（⚠️ `disabled` 的 `title` **浏览器可能不弹**（鼠标事件被抑制）
     ⇒ 光挂 `title` 等于"灰着但没理由" ⇒ 理由必须**上屏**）。
  2. **`m03` 删除确认**的要求句 → 人话（同族第 3 例）。
  3. **`m05` 期初行删除**：要求句 → 人话 ＋ ⚠️ **「按软删留痕处理」是错的** ——
     `repo.delete_opening` 就是 `s.delete(row)`（**真删**），§9.4 的 2026-09-20 定案也把「期初」
     明确列在**硬删**那一档 ⇒ 那句会让用户以为"删了还能恢复"（同批改注释与 toast）。
  4. **`m14` 的「硬规矩」表**第 6 条：旧分档说法「核心数据删除是『软删 + 留痕』；配置类是真删」
     → §9.4 定案口径（**按"删了能不能复原"分**）。
  5. `BIG_THEAD` 上方注释「`<th>` 总数（**24**）」→ **23**（实测：第 1 行 12 ＋ 第 2 行 11）
     —— ⚠️ 它是 `U5` 逐字一致项 ⇒ **壳与原型同改同句**（改前先备份交付面）。

用法：`… _apply_a6b.py --check` / `--write`
"""

from __future__ import annotations

import argparse
import datetime as dt
import pathlib
import shutil
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
WEB = REPO / "backend" / "app" / "web"
ACT = WEB / "shell" / "actions.js"
INDEX = WEB / "index.html"
PROJ = WEB / "shell" / "proj.js"
FACE = pathlib.Path(r"D:\工作\AI\PRD编写夹 - Workbuddy专用")
PROTO = FACE / "demo" / "材料报表自动化工作台-交互原型.html"

EDITS: tuple[tuple[pathlib.Path, str, str, str], ...] = (
    # ── ① m01 的「确认删除」置灰 ＋ **可见**的状态说明 ────────────────────
    (
        ACT, "`m01` 删除确认：加一句**可见**的「还不能删」说明（`disabled` 的 `title` 不一定弹）",
        "     <div class=\"tip\" style=\"margin:0\">项目档案属<b>配置类数据 ⇒ 硬删</b>（§9.4）；"
        "被引用的核心业务数据（通知书 / 流水 / 库存单据 / 集采合同）<b>不随删</b> —— "
        "它们仍保留原项目全名，页面上会显示为<b>未建档</b>。</div>`,",
        "     <div class=\"tip\" style=\"margin:0\">项目档案属<b>配置类数据 ⇒ 硬删</b>（§9.4）；"
        "被引用的核心业务数据（通知书 / 流水 / 库存单据 / 集采合同）<b>不随删</b> —— "
        "它们仍保留原项目全名，页面上会显示为<b>未建档</b>。</div>\n"
        "     <div class=\"tip\" style=\"margin:0\">"
        "<b>删除这一项还没打通</b>：删除前得先把「影响范围」列全，而上面还有 3 项数不出来 "
        "—— 等这几项能列全就开放（所以下面那枚按钮现在是灰的）。</div>`,",
    ),
    (
        ACT, "`m01` 的「确认删除」置灰 ＋ `title` 写明为什么",
        "footer:`<button class=\"btn\" data-act=\"closeModal\">取消</button>"
        "<button class=\"btn dg\" data-act=\"delPjOk\" data-id=\"${p.id}\">确认删除</button>`}); },",
        "footer:`<button class=\"btn\" data-act=\"closeModal\">取消</button>"
        "<button class=\"btn dg\" data-act=\"delPjOk\" data-id=\"${p.id}\" disabled "
        "title=\"这一项还没打通：删除前得先把「影响范围」列全，而现还有 3 项数不出来 "
        "—— 等它们能列全就开放\">确认删除</button>`}); },",
    ),
    # ── ② m03 的要求句 → 人话 ─────────────────────────────────────────────
    (
        ACT, "`m03` 手动行删除确认：要求句 → 人话（同族第 3 例）",
        "body:`<div class=\"tip dg\" style=\"margin-bottom:calc(10px * var(--fscale))\">"
        "<b>⚠️ 删除前必须列出影响范围</b>（关联数据、统计影响）—— §7.2 / §9.4。<br>${imp.message}</div>",
        "body:`<div class=\"tip dg\" style=\"margin-bottom:calc(10px * var(--fscale))\">"
        "<b>⚠️ 删除前先看清下面这些影响</b>（关联数据 · 统计影响）—— §7.2 / §9.4。<br>${imp.message}</div>",
    ),
    # ── ③ m05 期初行删除：要求句 ＋ 「软删留痕」（与后端/§9.4 相反）───────
    (
        ACT, "`m05` 期初行删除：那句过时注释（写成「软删留痕」）",
        "/* 删除前必须列出影响范围（§7.2 / §9.4）：核心业务数据「软删留痕 + 统计重算」 */",
        "/* 删除前先看清影响范围（§7.2 / §9.4）：期初属「**用户自录、随时可重录**」那一档 ⇒ **真删**\n"
        "   （§9.4 的 2026-09-20 定案：**按「删了能不能凭源数据复原」分**）。\n"
        "   ⚠️ 2026-09-29 `A6` 订正：这里原写「核心业务数据『软删留痕』」—— 与后端 "
        "`repo.delete_opening`（就是 `s.delete`）**相反**，也与 §9.4 定案相反（行里根本没有留痕字段）。 */",
    ),
    (
        ACT, "`m05` 期初行删除确认：要求句 → 人话",
        "modal({title:'删除确认 · 期初占位行',body:`<div class=\"tip dg\" "
        "style=\"margin-bottom:calc(10px * var(--fscale))\"><b>⚠️ 删除前必须列出影响范围</b>"
        "（关联数据、统计影响）—— §7.2 / §9.4。</div>",
        "modal({title:'删除确认 · 期初占位行',body:`<div class=\"tip dg\" "
        "style=\"margin-bottom:calc(10px * var(--fscale))\"><b>⚠️ 删除前先看清下面这些影响</b>"
        "（关联数据 · 统计影响）—— §7.2 / §9.4。</div>",
    ),
    (
        ACT, "`m05` 期初行删除确认：后果说明改成**真删**口径（原写「软删留痕」= 会让用户以为能恢复）",
        "<div class=\"tip\" style=\"margin:0\">删除后：<b>期初占位欠款 ${M(dd)} → 0</b>，"
        "<b>欠款合计</b>同步重算；该行按<b>软删留痕</b>处理（属核心业务数据）。</div>`,",
        "<div class=\"tip\" style=\"margin:0\">删除后：<b>期初占位欠款 ${M(dd)} → 0</b>，"
        "<b>欠款合计</b>同步重算；⚠️ 这一行会被<b>真的删掉、删了不能恢复</b>"
        "（需要时随时可以<b>重新录入</b>）—— 期初属「你自己录、随时可重录」那一档（§9.4）。</div>`,",
    ),
    (
        ACT, "`m05` 期初行删除的**回执**：同上订正",
        "/* ⭐ 已接后端：`POST /m05/opening/delete`（软删留痕 ＋ 统计重算由后端做） */",
        "/* ⭐ 已接后端：`POST /m05/opening/delete`（**真删** ＋ 统计重算由后端做 —— "
        "`mod05_flow.repository.delete_opening` 就是 `s.delete(row)`；\n"
        "   ⚠️ 2026-09-29 订正：原写「软删留痕」与后端相反） */",
    ),
    (
        ACT, "`m05` 期初行删除的回执文案：同上订正",
        "'期初占位行已删除（软删留痕），欠款与台账已由后端重算'); },",
        "'期初占位行已删除（删了不能恢复、需要时随时可以重新录入），欠款与台账已由后端重算'); },",
    ),
    # ── ④ m14「硬规矩」表的旧分档说法 ─────────────────────────────────────
    (
        INDEX, "`m14`「硬规矩」表：旧分档说法 → §9.4 定案口径",
        "'核心数据删除是「软删 + 留痕」；配置类是真删'",
        "'删除分档（按「删了能不能复原」分）：可复原的 / 你自己录的（期初 · 特殊费用 · 手动补录 · "
        "付款计划）⇒ 真删；只有账号是软删（留痕里的人名要认得出来）'",
    ),
    # ── ⑤ BIG_THEAD 注释里的 `<th>` 总数：24 → 23（**两边同改同句**）──────
    (
        PROJ, "`BIG_THEAD` 注释：`<th>` 总数 24 → 23（实测 12 ＋ 11）",
        "两行表头的 `<th>` 总数（24）≠ 数据列数（20）",
        "两行表头的 `<th>` 总数（23）≠ 数据列数（20）",
    ),
    (
        PROTO, "原型同句镜像：`<th>` 总数 24 → 23（`U5` 逐字一致项）",
        "两行表头的 `<th>` 总数（24）≠ 数据列数（20）",
        "两行表头的 `<th>` 总数（23）≠ 数据列数（20）",
    ),
)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)

    plan: list[tuple[pathlib.Path, str, str, str]] = []
    for path, label, old, new in EDITS:
        raw = path.read_text(encoding="utf-8", newline="")
        n = raw.count(old)
        if new in raw and n == 0:
            print(f"  ⏭ 已应用：{label}")
            continue
        assert n == 1, f"{label}：锚点命中 {n} 次（要**恰好 1 次**）—— 先核再改"
        plan.append((path, label, old, new))
        print(f"  ✅ 锚点唯一：{label}（{path.name}）")
    if not plan:
        print("\n（全部已应用 ⇒ 无事可做）")
        return 0
    if not args.write:
        print(f"\n（`--check`：⛔ 未写；要改 {len(plan)} 处）")
        return 0

    # ⚠️ 动交付面（原型）⇒ 先备份（本批只改原型一件）
    if any(p == PROTO for p, _l, _o, _n in plan):
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M")
        backup = REPO / ".workbuddy" / "backups" / f"交付面-{stamp}-A6b"
        dst = backup / PROTO.relative_to(FACE)
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists():
            shutil.copy2(PROTO, dst)
            print(f"✅ 已备份原型 ⇒ {backup}")

    for path, label, old, new in plan:
        raw = path.read_text(encoding="utf-8", newline="")     # ⚠️ 每处写前**重读盘**
        assert raw.count(old) == 1, f"{label}：重读后锚点命中 {raw.count(old)} 次"
        path.write_text(raw.replace(old, new, 1), encoding="utf-8", newline="")
        back = path.read_text(encoding="utf-8", newline="")
        assert back.count(new) >= 1 and back.count(old) == 0, f"{label}：写回自校验不过"
        print(f"✅ 已写：{label}")

    print("\n接着：`ui_parity`（`U5` 必须仍逐字一致）⇒ `syntax_audit` ⇒ 判据 ⇒ 全套闸门")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
