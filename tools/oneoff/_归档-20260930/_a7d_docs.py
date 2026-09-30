#!/usr/bin/env python
"""`TAIL-182`（`A` 案）的**文书收口** · 一次性（2026-09-29）。

**它改什么**（⚠️ 每处写前断言**恰好命中一次**；台账行手术排在字符串编辑**之前**、每步重新定位下标）：
  1. 四态计数 **4 处一起改**（`639 → 640`）：`§0.2`（＋接"再涨"）· `§22.1` · `§13.6` 入门口令 · 简略版页首；
  2. 计划 `§15`：**`TAIL-182` 从 `§三` 移到 `§四`（销号 · `A` 案）**；计数 `C 1 → 0` · 已销号 `179 → 180`；
  3. `§14.3`：`TAIL-182` 那行标 ✅ 已办；
  4. `§13.6`：状态行 / 入门口令下一步 / 接手核验续记；
  5. 守则 `§10` 记一笔（含那条**便宜量不出来**的口径：`body` 是 `overflow:hidden` ⇒ 页级提示只能进 `main`）；
  6. 逐页计划 `§三` 进度块补一句（`TAIL-182` 已办）。

用法：`… _a7d_docs.py --check` / `--write`
"""

from __future__ import annotations

import argparse
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
PLAN = REPO / ".workbuddy" / "plans" / "开发计划-主文档.md"
HAND = REPO / ".workbuddy" / "plans" / "执行情况-主文档.md"
RULE = REPO / "ops" / "前端设计守则-以使用用户为中心.md"
PAGEPLAN = REPO / ".workbuddy" / "work" / "10-designs" / "设计-前端逐页推进计划-20260929.md"

STAMP = "20260929-1200"
SRC = "出处 = §13.6 接手核验续记 ＋ `.codebuddy/memory/2026-09-29.md`"

ROW_DONE = (
    "| `TAIL-182` | ⚠️ **启动失败横幅盖住页首、吃掉卡头点击** ⇒ **改成进布局流**（`A` 案 · "
    "2026-09-29 **用户裁定** · " + SRC + "）：`core.js::bootErrorBanner()` 那条横幅原是 "
    "**`position:fixed;left:0;right:0;top:0;z-index:9999`** ⇒ 整带宽压在页面之上 ⇒ 页首那一带的"
    "**卡头按钮全都点不着**（发现经过：`A7` 量测时 `㉝` 想点「隐藏贸易公司列」被它挡住，Playwright 报 "
    "`intercepts pointer events` 连重试 57 次；`elementFromPoint` 拿到的正是它）。⭐ 改法 = **进布局流**："
    "插在 `main` 里 `#view` 之前 ＋ `flex:0 0 auto`（**占位**、把内容往下推）；⛔ **不能挂 `body`** —— "
    "`html,body{height:100%;overflow:hidden}` ＋ `.app{height:100vh}`，挂上去**溢出被裁**；"
    "⭐ 而且它**不会滚走**（真正的滚动容器是 `.view`，本横幅是它的**兄弟**）—— 比原先「永远钉在最上面」更省心 | "
    "判据 = **新判据 1 条**（`ACC-UI-SHELL-001/001-62`：不许 `fixed`/`absolute` ＋ 必须进布局流）＋ "
    "**真机新段 ㉞**（`tools/probe/_shell_bootbar.py`：自己拦断 `/api/**` ＋ 刷新**造出**那个状态 ⇒ "
    "在流里 / 不重叠 / **卡头按钮正中间 `elementFromPoint` 就是它**；顺带修掉本段自己写歪的一条假红 —— "
    "按钮被顶到视口外时 `elementFromPoint` 返回 `null` ⇒ 先 `scrollIntoView` 再量）＋ **反向灵敏度** "
    "`tools/mut/_mut_a7.py` **6/6** ＋ 全套 pytest **100%** ＋ 四态 **639 → 640** ＋ 12 把尺子 rc=0 ＋ "
    "`ui_parity` 零漂移（**没碰任何切片**）＋ **盖章** `" + STAMP + "` | 2026-09-29 |"
)

EDITS: tuple[tuple[pathlib.Path, str, str, str], ...] = (
    (PLAN, "§0.2 判据计数 639 → 640",
     "**判据（唯一完成度口径）**：**639 = 绿 639 · 红 0 · 待建   0 · 未绑定    0**",
     "**判据（唯一完成度口径）**：**640 = 绿 640 · 红 0 · 待建   0 · 未绑定    0**"),
    (PLAN, "§0.2 接一条 `TAIL-182`（`A` 案）的「再涨」说明",
     "（⭐ **2026-09-29 再涨 1 = `TAIL-180`（`B` 案）**",
     "（⭐ **2026-09-29 再涨 1 = `TAIL-182`（`A` 案 · **全局件**）**：**启动失败横幅不再盖住内容** "
     "—— 原先是 `position:fixed;top:0`，压在页首把**卡头按钮的点击全吃掉**（守则 §4.6 的反例同族）"
     "⇒ 改成进布局流（判据 `001-62` ＋ 真机 ㉞）；**2026-09-29 再涨 1 = `TAIL-180`（`B` 案）**"),
    (HAND, "简略版页首判据总账 639 → 640",
     "**639 = 绿 639 · 红 0 · 待建 0 · 未绑定 0**", "**640 = 绿 640 · 红 0 · 待建 0 · 未绑定 0**"),
    (PLAN, "§22.1 四态零丢失基线 639 → 640",
     "- ⭐ **四态零丢失的基线 = 639 = 绿 639 · 红 0 · 待建 0 · 未绑定 0**"
     "（2026-09-29 随 `TAIL-180`（`B` 案 · `A7` · `m11`）**再涨 1**",
     "- ⭐ **四态零丢失的基线 = 640 = 绿 640 · 红 0 · 待建 0 · 未绑定 0**"
     "（2026-09-29 随 `TAIL-182`（`A` 案 · **全局件**）**再涨 1**：**启动失败横幅不再盖住内容**"
     "（`001-62`）—— 页级提示改成「进布局流」，卡头按钮点得到了；同日此前随 `TAIL-180`（`B` 案 · `A7` · `m11`）"
     "**再涨 1**"),
    (PLAN, "§13.6 入门口令里的期望值 639 → 640",
     "（四态 · 期望 639 绿 0 红）", "（四态 · 期望 640 绿 0 红）"),
    (PLAN, "§0.2 的尾巴计数（C 1 → 0 · 已销号 179 → 180）",
     "A 类 **5** 条 · B 类 0 · C 类 **1** · 已销号 **179**",
     "A 类 **5** 条 · B 类 0 · C 类 **0** · 已销号 **180**"),
    (PLAN, "§15 计数行（`T6` 按实际条数核）",
     "A 类 **5** 条 · B 类 **0** 条 · C 类 **1** 条 · 已销号 **179** 条",
     "A 类 **5** 条 · B 类 **0** 条 · C 类 **0** 条 · 已销号 **180** 条"),
    (PLAN, "§14.3：`TAIL-182` 那行标 ✅ 已办",
     "| ⏳ **待用户一句话**（属用户可见的交互变化；⚠️ 但它**只在启动取数失败时**出现，不阻塞主线） |",
     "| ✅ **已办（`A` 案 · 2026-09-29）** ⇒ 见 §15 §四 |"),
    (PLAN, "§13.6 状态行：`TAIL-182` 已按 `A` 案办",
     "⇒ **下一批 = `A8` = `imp` 数据导入**（通用导入面 · 4 域共用；⏳ 本批**顺带查出**一条全局件的问题："
     "启动失败横幅盖住页首吃掉点击 ⇒ 新立 `TAIL-182` 待你裁）",
     "⇒ **下一批 = `A8` = `imp` 数据导入**（通用导入面 · 4 域共用；⭐ 那条全局件问题已按 **`A` 案**办："
     "启动失败横幅**改成进布局流**（不再盖住页首、卡头按钮点得到了）—— `TAIL-182` 销号 · 判据 `001-62` · "
     "真机新段 **㉞**）"),
    (PLAN, "§13.6 入门口令的下一步：`TAIL-182` 已办",
     "⏳ 本批顺带查出的**全局件**问题 ⇒ 新立 `TAIL-182`（启动失败横幅盖住页首、吃掉卡头按钮的点击 · 待你裁）；"
     "⑤ **下一步 = `A8` = `imp` 数据导入**。",
     "⭐ 本批顺带查出的**全局件**问题已按 **`A` 案**办（`TAIL-182` 销号 · 判据 `001-62` · 真机 **㉞**："
     "横幅进布局流、卡头按钮 `elementFromPoint` 就是它）；⑤ **下一步 = `A8` = `imp` 数据导入**。"),
    (PLAN, "§13.6 接手核验续记：`TAIL-182` 已办",
     "⏳ 待办 = 新立的 `TAIL-182`（启动失败横幅盖住页首吃掉点击 · 全局件 · 待裁）",
     "⭐ 再续：`TAIL-182` 也已按 **`A` 案**办（横幅进布局流 · 判据 `001-62` · 真机 **㉞**）⇒ 四态 **640**；"
     "⏳ 待办 = 无（新一批开始前台账干净：A 类 5 · C 类 0）"),
    (RULE, "守则 §10 变更记录：记一笔 `TAIL-182`（`A` 案）",
     "{nl}---{nl}{nl}## 附录 A · 原始口述对照",
     "{nl}| 2026-09-29 | ⭐⭐ **`TAIL-182`（`A` 案 · 全局件）：页级提示**不许盖住内容** —— "
     "启动失败横幅（`bootErrorBanner`）原是 `position:fixed;left:0;right:0;top:0;z-index:9999` ⇒ "
     "**压在页面之上** ⇒ 页首那一带的**卡头按钮全都点不着**（真机：`intercepts pointer events` 连重试 57 次）；"
     "守则 §4.6 的反例原文就是「提示条盖住可点区（本仓真例：`.toast` 吃掉浮层点击）」—— 同一族 ⇒ "
     "改成**进布局流**（`main` 里 `#view` 之前 ＋ `flex:0 0 auto`） | §4.6 §5.5 | "
     "`ACC-UI-SHELL-001/001-62` ＋ 真机 **㉞**（`tools/probe/_shell_bootbar.py`：自己拦断 `/api/**` 造出该状态 "
     "⇒ 在流里 / 不重叠 / 卡头按钮正中间 `elementFromPoint` 就是它）＋ `tools/mut/_mut_a7.py` **6/6** · "
     "四态 **639 → 640** · 盖章 `" + STAMP + "` | 用户 2026-09-29「二、A，然后继续」 | "
     "⭐⭐ **两条可复用的**：① **页级提示只能进 `main`** —— 本仓 `html,body{height:100%;overflow:hidden}` ＋ "
     "`.app{height:100vh}` ⇒ 挂到 `body` 上会**溢出被裁**（真机量过），而 `.view` 才是那个自己滚的容器 ⇒ "
     "把横幅插成 `.view` 的**兄弟**（`flex:0 0 auto`）：**占位、不覆盖，而且不跟着滚**。"
     "② **`elementFromPoint` 的假红陷阱**：目标在视口外时它返回 `null`（不是「被挡住」）⇒ 量「点得到」之前"
     "**先 `scrollIntoView`**（本条是 ㉞ 自己写歪一次、当场修掉的） |" +
     "{nl}{nl}---{nl}{nl}## 附录 A · 原始口述对照"),
    (PAGEPLAN, "逐页计划 §三 进度块：补 `TAIL-182` 已办",
     "（当年只修了 `.toast`）。",
     "（当年只修了 `.toast`）。"
     "{nl}> ✅ **`TAIL-182` 已按 `A` 案办（2026-09-29）**：横幅**进布局流**（插在 `main` 里 `#view` 之前 ＋ "
     "`flex:0 0 auto`；⛔ 不挂 `body` —— 那里是 `overflow:hidden`）⇒ **不再盖住页首、卡头按钮点得到**，"
     "而且**不跟着滚**（滚动容器是 `.view`，它是兄弟）⇒ 判据 `001-62` ＋ 真机新段 **㉞**（自己拦断 `/api/**` "
     "造出该状态来量）。"),
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
    drop = [i for i, ln in enumerate(lines) if ln.startswith("| `TAIL-182` |")]
    assert len(drop) == 1, f"§三 的 `TAIL-182` 行命中 {len(drop)} 行"
    assert not any(ln.startswith("| `TAIL-182` |") and i != drop[0] for i, ln in enumerate(lines)), \
        "`TAIL-182` 已在 §四 里"
    print(f"  ✅ 命中：§三 第 {drop[0] + 1} 行 = `TAIL-182`（转销号 ⇒ 删）")

    if not args.write:
        print(f"\n（`--check`：⛔ 未写；逐处 {len(plan)} 处 ＋ §三 −1 / §四 ＋1）")
        return 0

    lines.pop(drop[0])
    hD = [i for i, ln in enumerate(lines) if ln.strip() == "| # | 事项 | 销号依据 | 日期 |"]
    assert len(hD) == 1, "删行后 §四 表头不唯一"
    lines.insert(hD[0] + 1, ROW_DONE)
    PLAN.write_text(nl.join(lines), encoding="utf-8", newline="")
    print("✅ 已写：§15（§三 −1 `TAIL-182` · §四 ＋1 销号）")

    for path, label, old, new in plan:
        raw = path.read_text(encoding="utf-8", newline="")     # ⚠️ 每处写前重读盘
        assert raw.count(old) == 1, f"{label}：重读后锚点命中 {raw.count(old)} 次"
        path.write_text(raw.replace(old, new, 1), encoding="utf-8", newline="")
        print(f"✅ 已写：{label}")

    print("\n接着：全套 pytest ＋ `acc_report` ＋ 12 把尺子 ＋ `claim_audit`（`T4`/`T6` 会盯计数与排期）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
