#!/usr/bin/env python
"""`A10` 逐页（`m13` / `m14` / `set` / `m15`）的**文书收口** · 一次性（2026-09-29）。

**它改什么**（⚠️ 每处写前断言**恰好命中一次**）：
  1. 计划 `§15`：`§四` 加 **`TAIL-186`**（`A10` 收口 · 销号）；计数 已销号 `183 → 184`（C 类仍 0）；
  2. `§13.6`：状态行 / 入门口令下一步 / 接手核验续记（**下一批 = `A11` = `home` 看板**）；
  3. 守则 `§10` 记一笔（⭐ 本批最值钱的一条：**颜色闸门自己有个盲区** —— 只钉了 `ok`/`wn`，`dg` 从没审过）；
  4. 逐页计划 `§三` 进度块补 `A10`。
  ⚠️ **四态计数本批不动**（不新增判据点 —— 复用既有颜色闸门）。`set` 那页在 `legacy.js`（壳新增页、
  ⛔ 不在原型切片里），`⑳` 段看着它。

用法：`… _a10_docs.py --check` / `--write`
"""

from __future__ import annotations

import argparse
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
PLAN = REPO / ".workbuddy" / "plans" / "开发计划-主文档.md"
RULE = REPO / "ops" / "前端设计守则-以使用用户为中心.md"
PAGEPLAN = REPO / ".workbuddy" / "work" / "10-designs" / "设计-前端逐页推进计划-20260929.md"

STAMP = "20260929-1257"

ROW_DONE = (
    "| `TAIL-186` | 🧾 **`A10` 逐页（`m13` / `m14` / `set` / `m15`）收口**（2026-09-29 · ⛔ 未改任何口径）："
    "**一处必修** —— `V.m14` 里「**分类只有三类**（机械 / 集采 / 辅材），**没有「其他」类**…」那句挂的是 "
    "`class=\"tip dg\"`（**危险红**），而它是**口径说明**（陈述事实），不是危险 / 错误 ⇒ 守则 §4.5 判法："
    "**红只给危险 / 错**，说明一律普通 `tip`；⚠️ 同页 1545 那条**禁止项**（「不得配置收款单位 = 资产处集中采购」）"
    "用的是 `tip wn`（黄）—— 那才是对的形态 ⭐⭐ **顺带发现：既有的颜色闸门自己有个盲区** —— "
    "`tests/test_ux_colors.py` 的墓碑**只覆盖 `tip ok` / `tip wn`**（批次 0 数的就是这两类 38 处）"
    "⇒ **`tip dg` 从没被审过**；本批把这一类**也纳入那个闸门**（加墓碑 ＋ 改文件头口径） | "
    "判据 = **复用既有颜色闸门**（`tests/test_ux_colors.py` · `ACC-UI-SHELL-001/001-24`，本批**不新增判据点**）"
    "＋ **反向灵敏度** `tools/mut/_mut_a7.py` **10/10** ＋ 全套 pytest **100%** ＋ 四态**仍 641** ＋ "
    "`ui_parity` 登记 1 条切片漂移 ＋ **消号 1 条幽灵** ＋ **盖章** `" + STAMP + "`；"
    "⭐ **放过并写明理由**：`m13` 是纯说明页（0 动作 · 边界诚实：「本页没有自己的数据，所以这里不放按钮」；"
    "「不做提醒与督办」）· `m14` 的 `tip wn`（真禁止项）与规则表各按钮的 `title`（后果写清）· "
    "`m15` 的置灰 ＋ `title`（非管理员 / 最后一个管理员）与三种状态 tag 的 `ok`/`wn`/`dg` 用法 · "
    "`set` 页已按 `TAIL-127`（用户裁定 `B`）把连接参数搬回它起作用的地方 | 2026-09-29 |"
)

EDITS: tuple[tuple[pathlib.Path, str, str, str], ...] = (
    (PLAN, "§0.2 的尾巴计数（已销号 183 → 184）",
     "A 类 **5** 条 · B 类 0 · C 类 **0** · 已销号 **183**",
     "A 类 **5** 条 · B 类 0 · C 类 **0** · 已销号 **184**"),
    (PLAN, "§15 计数行（`T6` 按实际条数核）",
     "A 类 **5** 条 · B 类 **0** 条 · C 类 **0** 条 · 已销号 **183** 条",
     "A 类 **5** 条 · B 类 **0** 条 · C 类 **0** 条 · 已销号 **184** 条"),
    (PLAN, "§13.6 状态行：`A10` 已办 ＋ 下一批 = `A11`",
     "⇒ **下一批 = `A10` = `m13` 导出与删除 · `m14` 规则配置 · `set` 系统设置 · `m15` 用户管理**"
     "（全局页 · 复核「不变形」）",
     "⇒ ⭐ **`A10`（`m13` / `m14` / `set` / `m15`）也已办**（2026-09-29 · 见 §15 §四 `TAIL-186`："
     "`m14` 那句**口径说明从危险红降为普通 `tip`**；⭐⭐ 顺带发现**既有颜色闸门只钉了 `ok`/`wn`、`dg` 从没审过**"
     "⇒ 本批把 `dg` 也纳入）⇒ **下一批 = `A11` = `home` 看板**（刚清过账 · 只剩 4 张待办卡；"
     "⚠️ 用户说「寒酸」但**不加东西**，等他点 · `TAIL-161` 空态）"),
    (PLAN, "§13.6 入门口令的下一步：`A10` 已办 ＋ 指向 `A11`",
     "⑦ **下一步 = `A10` = `m13` / `m14` / `set` / `m15`**。",
     "⑦ ✅ **`A10` 也已办**（2026-09-29）：四页通读（`V.m13` 19 行/**0 动作** · `V.m14` 50 行/5 动作 · "
     "`V.m15` 64 行/8 动作 · `set` 在 `legacy.js`）＋ `m14` 那句口径说明降为普通 `tip`"
     "（⛔ 不新增判据点 · 复用颜色闸门；**并给闸门补上了 `dg` 这一类**）；⑧ **下一步 = `A11` = `home` 看板**。"),
    (PLAN, "§13.6 接手核验续记：补记 `A10`",
     "＋ **同批改 `ACC-INV-001/001-12` 的 claim**（判据点总数**不变**）⇒ 四态**仍 641**；⏳ 下一步 = `A10`",
     "＋ **同批改 `ACC-INV-001/001-12` 的 claim**（判据点总数**不变**）⇒ 四态**仍 641**；⭐ 再续 `A10`"
     "（`m13`/`m14`/`set`/`m15`）：`m14` 那句**口径说明降为普通 `tip`**（`TAIL-186`）＋ **给颜色闸门补上 `dg`**"
     "（原来只钉 `ok`/`wn`）⇒ 四态**仍 641**；⏳ 下一步 = `A11`（`home` 看板）"),
    (RULE, "守则 §10 变更记录：记一笔 `A10`（`m13`/`m14`/`set`/`m15`）",
     "{nl}---{nl}{nl}## 附录 A · 原始口述对照",
     "{nl}| 2026-09-29 | ⭐⭐ **`A10` 逐页（`m13` / `m14` / `set` / `m15`）：查到的不只是页面，还有**闸门自己的盲区**** "
     "—— `m14` 里「**分类只有三类**…」那句口径说明挂了 `tip dg`（**危险红**）⇒ 降为普通 `tip`"
     "（守则 §4.5：红只给危险 / 错；⚠️ 同页那条**真禁止项**用的是黄 —— 那才对）。⭐⭐ **更要紧的发现**："
     "`tests/test_ux_colors.py` 那道颜色闸门的墓碑**只覆盖 `tip ok` / `tip wn`**（批次 0 数的就是这两类 38 处）"
     "⇒ **`tip dg` 从没被审过** —— 也就是说**「有闸门」不等于「这一类被闸门管着」**；本批把 `dg` 也纳入同一个闸门 "
     "| §4.5 §5.9 | `tests/test_ux_colors.py` 墓碑（复用 `001-24`，**不新增判据点**）＋ `tools/mut/_mut_a7.py` "
     "**10/10** · 四态**仍 641** · 盖章 `" + STAMP + "` | 用户 2026-09-29「继续」 | ⭐⭐ **可复用**："
     "**看闸门要连「它管哪几类」一起看** —— 本仓的颜色闸门写得很清楚（文件头就写着「本件**只钉这 14 处**」），"
     "但那句「只钉」很容易被读成「已经管全了」；⇒ 遇到**第三类**（这里是 `dg`）时要主动**把它纳进来**，"
     "而不是另起一道闸门 |" + "{nl}{nl}---{nl}{nl}## 附录 A · 原始口述对照"),
    (PAGEPLAN, "逐页计划 §三 进度块：补 `A10`",
     "（全局页；上一轮已整页改过 ⇒ 复核「**不变形**」。）",
     "（全局页；上一轮已整页改过 ⇒ 复核「**不变形**」。）"
     "{nl}> ⭐ **进度**：`A10`（`m13` / `m14` / `set` / `m15`）**已办 2026-09-29**（`TAIL-186` · ⛔ 未改口径）"
     "—— **量测先行**：`V.m13` 19 行 · **0 动作** · 2 tips（纯说明页 · 边界诚实：「本页没有自己的数据，"
     "所以这里不放按钮」）；`V.m14` 50 行 · **5 动作** · 6 tips；`V.m15` 64 行 · **8 动作** · 2 tips；"
     "`set` 在 `legacy.js`（壳新增页 ⇒ `U1` 看不见，`⑳` 段看着）。"
     "{nl}> ✅ 本批收口：`m14` 那句「分类只有三类…」从 **`tip dg`（危险红）降为普通 `tip`**"
     "（守则 §4.5：红只给危险 / 错）＋ ⭐ **给颜色闸门补上 `dg` 这一类**（原来只钉 `ok`/`wn`）。"
     "{nl}> ⛔ **放过并写明理由**：`m13` 是纯说明页（0 动作 · 三张卡分别讲导出 / 删除 / 附件，边界全写实："
     "「暂不支持」「以后再做」「不做提醒与督办」）；`m14` 的 `tip wn`（真禁止项）＋ 规则表各按钮的 `title`"
     "（改 / 删的后果写清；`ruleDel` 带 `dg` ✓）；`m15` 的**置灰 ＋ `title`**（非管理员 / 最后一个管理员）"
     "＋ 三种状态 tag 的 `ok`/`wn`/`dg` 用法；`set` 页已按 `TAIL-127`（用户裁定 `B`）把连接参数"
     "**搬回它起作用的地方**（⛔ 本页不再摆输入框）。"
     "{nl}> ⚠️ **下一步 = `A11` = `home` 看板**（刚清过账 · 只剩 4 张待办卡；⚠️ 用户说「寒酸」但**不加东西**，"
     "等他点 · `TAIL-161` 空态）。"),
)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)

    plan: list[tuple[pathlib.Path, str, str, str]] = []
    for path, label, old_t, new_t in EDITS:
        raw = path.read_text(encoding="utf-8", newline="")
        nl = "\r\n" if "\r\n" in raw else "\n"
        old, new = old_t.replace("{nl}", nl), new_t.replace("{nl}", nl)
        if old == new:
            raise AssertionError(f"{label}：新旧串相同（空操作 ⇒ 本脚本写错了）")
        n = raw.count(old)
        assert n == 1, f"{label}：锚点命中 {n} 次（要**恰好 1 次**）—— 先核再改"
        assert new not in raw, f"{label}：新串已在 ⇒ 本脚本跑过了"
        plan.append((path, label, old, new))
        print(f"  ✅ 锚点唯一：{label}（{path.name}）")

    txt = PLAN.read_text(encoding="utf-8", newline="")
    nl = "\r\n" if "\r\n" in txt else "\n"
    lines = txt.replace("\r\n", "\n").split("\n")
    assert not any(ln.startswith("| `TAIL-186` |") for ln in lines), "`TAIL-186` 已在台账里"
    hD = [i for i, ln in enumerate(lines) if ln.strip() == "| # | 事项 | 销号依据 | 日期 |"]
    assert len(hD) == 1, "§四 表头不唯一"
    print("  ✅ 命中：§15 §四 表头（待插销号行）")

    if not args.write:
        print(f"\n（`--check`：⛔ 未写；逐处 {len(plan)} 处 ＋ §四 ＋1）")
        return 0

    lines.insert(hD[0] + 1, ROW_DONE)
    PLAN.write_text(nl.join(lines), encoding="utf-8", newline="")
    print("✅ 已写：§15（§四 ＋1 `TAIL-186` 销号）")

    for path, label, old, new in plan:
        raw = path.read_text(encoding="utf-8", newline="")     # ⚠️ 每处写前重读盘
        assert raw.count(old) == 1, f"{label}：重读后锚点命中 {raw.count(old)} 次"
        path.write_text(raw.replace(old, new, 1), encoding="utf-8", newline="")
        print(f"✅ 已写：{label}")

    print("\n接着：全套 pytest ＋ 12 把尺子 ＋ `claim_audit`（`T4`/`T6` 会盯计数）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
