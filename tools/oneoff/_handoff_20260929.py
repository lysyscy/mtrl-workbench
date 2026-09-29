#!/usr/bin/env python
"""交接材料换代（`HANDOFF-20260928-01` → `-20260929-01`）＋ **逐字下沉**旧的（2026-09-29 · `A4` 收尾）。

**为什么**：① 旧那份**已过期**（它写"9 批收官后等用户指令"，而 09-29 已把 `A1`–`A4` 四页做完）；
② 主文档**逼近预算**（1700 行）⇒ 按本仓规矩：**完成的叙述逐字下沉**到 `归档-历史单元条目.md`，
原处只留**指针 ＋ 一份写准的**交接（⛔ 不是静默删）。

**它做什么**（逐条断言，⛔ 不对就拒写）：
  1. 从 `§13.6` 里切出 `#### ★ 当前交接材料（HANDOFF-20260928-01 …` 到 `#### （历史）交接材料 ` 之前那一段；
  2. 把这段**逐字**追加到 `归档-历史单元条目.md`（带「搜得到」的标记）；
  3. 原处换成新的 `-20260929-01`（**只写状态 / 限制 / 第一步 / 口令**，⛔ 不复述进度 —— 进度只认 §0 ＋ 四态 ＋ §15 ＋ 简略版）。

用法：`… _handoff_20260929.py --check` / `--write`
"""

from __future__ import annotations

import argparse
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
PLAN = REPO / ".workbuddy" / "plans" / "开发计划-主文档.md"
ARCH = REPO / ".workbuddy" / "plans" / "归档-历史单元条目.md"

START = "#### ★ 当前交接材料（`HANDOFF-20260928-01"
END = "#### （历史）交接材料 `HANDOFF-20260927-02`"
MARK = "**下沉于 2026-09-29（计划 §13.6 · 交接材料 `HANDOFF-20260928-01`）**"

NEW = """#### ★ 当前交接材料（`HANDOFF-20260929-01` · ⭐ **按这份接续**）

> ⭐ **性质 = 仅保存**（本仓约定：**保存交接不附带提交**）⇒ ⛔ 未新建接手任务、未提交。
> ⚠️ `-20260928-01`（上一份）**已逐字下沉** ⇒ `归档-历史单元条目.md`（搜「**下沉于 2026-09-29（计划 §13.6 · 交接材料 `HANDOFF-20260928-01`）**」）⇒ ⛔ 别按它接续。

| 项 | 内容 |
|---|---|
| ⭐ **交接编号** | **`HANDOFF-20260929-01`**（**取代** `HANDOFF-20260928-01`） |
| **状态** | ⭐ 前端系统性重构**已收官**（三档 9 批全销号）；当前按 **`TAIL-117` 的逐页推进计划**自主推进 —— **`A1`–`A4` 已完成**（`m05`/`m03`/`m04`/`m06`），**下一批 = `A5` `m07`** |
| **工作目录** | `D:\\dev\\mtrl-workbench`（⚠️ 交付面在**仓外**：`D:\\工作\\AI\\PRD编写夹 - Workbuddy专用`） |
| **分支 / 提交位置** | `master`；⚠️ **工作区里积着本会话全部改动**（⛔ 未提交）—— 接手先 `git status` 认清这批改动；hash 以 `git log -1` 为准 |
| **权威资料（查什么去哪）** | **前端口径**：`ops/前端设计守则-以使用用户为中心.md`（§8 最新落地实例 · §10 变更史）· **页序与每页 7 步 ＋ 4 条停止点**：`work/10-designs/设计-前端逐页推进计划-20260929.md` · **台账**：计划 `§15` ＋ `§14.3` · ⭐ **进度只认四处**：§0 现状快照 ＋ 四态报表 ＋ §15 ＋ 简略版（⛔ 本区**不复述进度**） |
| **用户已确认的限制 / 口径** | ① 动前端**先读守则**；② ⭐ **能机器判的必须挂判据**（⛔ 不许"只改不挂"）；③ 文案一律**人话**；④ ⛔ **别造第二套视觉语言**；⑤ ⛔ **别动原型逻辑**（`D18`）；⑥ ⭐ **别一次性铺开**（一批一类）；⑦ 用户说「行 / 列」＝版式 |
| **接续动作（第一步）** | ⭐ 先看用户说哪句：**A. 报障** ⇒ 先复现再定位（⛔ 别照描述直接改）；**B. 点名某页** ⇒ 那一页插队；**C. 没说话** ⇒ 按逐页计划推进（下批 `A5` `m07`）。⛔ 审计件 §四 那张 9 批批次表**已作废**、别再摆 |
| **接手核验续记** | （待接手填） |

**入门口令（可复制）**

```
项目：D:\\dev\\mtrl-workbench
交接来源：.workbuddy\\plans\\开发计划-主文档.md §13.6 → HANDOFF-20260929-01（⛔ 别按 -20260928-01 及更早的接续）
入场（只读，先别改业务文件）：
  ① 读 §13.6 的 -20260929-01（状态 / 限制 / 第一步都在那张表里）；
  ② 读 ops/前端设计守则-以使用用户为中心.md（前端口径唯一主人；已登记为项目规则）；
  ③ 读 .workbuddy/work/10-designs/设计-前端逐页推进计划-20260929.md（页序 17 屏 · 每页 7 步 · 4 条停止点）；
  ④ 读 .codebuddy/memory/2026-09-29.md（本会话实况与踩过的坑）；
  ⑤ 跑 tools/audit/acc_report.py（四态 · 期望 629 绿 0 红）· tools/audit/doc_audit.py --ui（必须修 0）·
     tools/audit/audit_meta.py（⚠️ 黄档也要读汇总行）· tools/probe/_shell_smoke.py（真机 · 期望 rc=0 · 含 ㉛）·
     tools/probe/_audit_face.py（交付面五把尺子 · 期望「必须修 0」）
验收：pytest 全绿 ＋ 真机 rc=0 ＋ doc_audit（含 --ui）必须修 0 ＋ 12 把尺子 rc=0（⭐ 并读黄档汇总）＋（改壳则）盖章
  ＋ 每批台账 §15 销号 ＋ 守则 §10 记一笔 ＋ ⭐ 能机器判的必须挂判据（含反向灵敏度）
⚠️ 两条硬规矩：⭐ 在 `V.*` 切片里**加 / 删行**会让 `ui_parity` 逐行对位**级联报漂移** ⇒ 注记写「行数不变」形态；
              ⭐ 动交付面（PRD / 验收基线 / demo）**先备份** ＋ 同批说明（⛔ 不静默改）。
```
"""


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)

    raw = PLAN.read_text(encoding="utf-8", newline="")
    nl = "\r\n" if "\r\n" in raw else "\n"
    t = raw.replace("\r\n", "\n")
    assert t.count(START) == 1, f"起点命中 {t.count(START)} 次（期望 1）"
    assert t.count(END) == 1, f"终点命中 {t.count(END)} 次（期望 1）"
    i, j = t.find(START), t.find(END)
    assert i < j, "起点在终点之后 ⇒ ⛔ 别写"
    old = t[i:j]
    print(f"切出旧交接材料：{len(old.splitlines())} 行")
    assert MARK not in t, "下沉标记已在正文里 ⇒ 本脚本跑过了"
    assert "HANDOFF-20260928-01" in old, "切出来的那段里没有旧编号 ⇒ ⛔ 先核"

    arch = ARCH.read_text(encoding="utf-8", newline="")
    arch_nl = "\r\n" if "\r\n" in arch else "\n"
    # ⚠️ 幂等：那一段可能**已经**沉下去了（本批实况：脚本先写过一次、随后被 IDE 的旧副本盖回主文档）
    #    ⇒ 归档件这半边照旧别再追加（否则同一段留痕出现两遍）。
    #    ⚠️⚠️ 归档件的行尾是 **`\r\r\n`**（历史遗留，见当轮报告）⇒ 找标记前先去掉裸 CR。
    if MARK in arch.replace("\r", ""):
        print("归档件里**已有**这一段下沉 ⇒ 跳过追加（幂等）")
        arch = None

    block = (f"\n---\n\n## {MARK}\n\n"
             "> ⛔ **别按它接续** —— 它讲的是 2026-09-28 的状态（当前那份是 `-20260929-01`）。\n"
             "> 📦 本段是**逐字下沉**（原处只留指针）：2026-09-29 `A4` 收尾时主文档逼近预算 ⇒ 按"
             "「完成的叙述下沉、原处留指针」的规矩搬过来（⛔ 不是静默删）。\n\n"
             + old.rstrip("\n") + "\n")

    new_t = t[:i] + NEW + t[j:]
    after = new_t
    plan_delta = len(after.splitlines()) - len(t.splitlines())
    print(f"主文档 {len(t.splitlines())} 行 ⇒ {len(after.splitlines())} 行（Δ{plan_delta:+d}）")
    if arch is None:
        arch_after = None
    else:
        arch_after = arch.rstrip("\n") + "\n" + block
        print(f"归档件 {len(arch.splitlines())} 行 ⇒ {len(arch_after.splitlines())} 行（Δ"
              f"{len(arch_after.splitlines()) - len(arch.splitlines()):+d}）")
    if plan_delta >= 0:
        print("⛔ 主文档没变短 ⇒ ⛔ 别写（这份改动的目的就是减重）")
        return 1

    if args.write:
        PLAN.write_text(after.replace("\n", nl) if nl == "\r\n" else after, encoding="utf-8", newline="")
        if arch_after is not None:
            ARCH.write_text(arch_after.replace("\n", arch_nl) if arch_nl == "\r\n" else arch_after,
                            encoding="utf-8", newline="")
        print("✅ 已写回：" + ("主文档（新交接）＋ 归档件（逐字下沉）" if arch_after is not None
                             else "主文档（新交接；归档件已有该段 ⇒ 未重复追加）"))
        # ⭐⭐ **写完立刻回读校验**（本批教训：外部脚本写完，IDE 的旧副本可能把它盖回去
        #    ⇒ 必须用"读盘"证明落地，⛔ 别只看那句 "已写回"）
        back = PLAN.read_text(encoding="utf-8", newline="").replace("\r\n", "\n")
        print(f"   回读校验：行数 {len(back.splitlines())} · 含 `-20260929-01` "
              f"{back.count('HANDOFF-20260929-01')} 次 · 旧标题残留 {back.count('#### ★ 当前交接材料（`HANDOFF-20260928-01')} 处")
        print("   ⚠️ 接着复跑 audit_meta / doc_audit（T6 与 §13.6 指针都要过）")
    else:
        print("\n（`--check`：⛔ 未写）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
