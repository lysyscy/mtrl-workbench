#!/usr/bin/env python
"""`HANDOFF-20260930-01` **增量刷新到「修订 8」** ＋ `TAIL-195` 改裁落纸（2026-09-30 晚）。

四件事（全部按**内容定位**，⛔ 不用硬编码行号）：
  1) §15 §一 的 `TAIL-195` 行：事项里「⛔ 现在不做」→「用户改裁 `B`：现在就做」＋ 落点补方案件 ＋ 阶段 `M8`→`立刻`、状态 `待做`→`待开工`；
  2) §14.3 的 `TAIL-195` 行：建议时机「缓（冻结后）」→「**立刻**」＋ 前置/触发按实况重写（实测半径：批1 **17 处** · 批2 **122 处/48 件**）；
  3) §13.6 交接表：`交接编号` 行后**插入一行**「2026-09-30 晚 · 增量（修订 8）」（状态/提交位置/权威资料/接续动作/交接状态 —— 增量更新、⛔ 不重写旧行）；
  4) §13.6「入门口令（可复制）」代码块**整块换新**（含新第一步 = `TAIL-195` 批 1、新闸门清单、新红线）。

⚠️ 行尾：`read_bytes().decode()` ＋ `splitlines(keepends=True)` ＋ `write_text(newline="")`（计划件是 CRLF）。
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PLAN = REPO / ".workbuddy" / "plans" / "开发计划-主文档.md"
BT = chr(96)

E1_OLD = "| " + BT + "TAIL-195" + BT + " | 🏗 **冻结后结构债**（⛔ 现在**不做**）：① 拆环——"
E1_NEW = ("| " + BT + "TAIL-195" + BT + " | 🏗 **结构债**（⭐ **2026-09-30 用户改裁 `B`：现在就做** —— "
          "方案 ＝ " + BT + "work/10-designs/设计-结构债-195-迁移方案-20260930.md" + BT + "）：① 拆环——")

E2_OLD = ("审计件 §四 阶段 2（⚠️ 每项先出**判据迁移方案**再动，⛔ 不许裸改） | M8 | 待做 |")
E2_NEW = ("方案件 ＝ " + BT + "work/10-designs/设计-结构债-195-迁移方案-20260930.md" + BT +
          "（⭐ **方案已出**：批 1 `models_registry` 挪层 → 批 1b（待你定）→ 批 2 拆环） | 立刻 | 待开工 |")

E3_OLD = ("| " + BT + "TAIL-195" + BT + " 🏗 **冻结后结构债**（拆两个环 ＋ 把 registry 挪出 `core`） | "
          "⏳ **缓（推荐冻结后单独立批）** ⇒ 见审计件 §三 P1-6/P1-7 | **四问**：① **不是前置**；② **成本不随时间变贵**"
          "（但**动它 = 动接口** ⇒ 越晚越怕）；③ **同域 = 后端装配层**（`core/models_registry.py` ＋ `main.py`）；"
          "④ ⚠️ **前置没到位**——`report_export ⇄ mod05/06/07/09` 与 `mod03 ⇄ mod05` 两个**环**、以及 `core` 反向依赖全部业务包："
          "拆它们 = 改接口 ＋ 同批迁判据 ⇒ **现在做 = 拿 641 条判据去冒险** | 触发 = 冻结 ＋ 用户点头；"
          "落点 = 审计件 §四 阶段 2（⚠️ 每项先出**判据迁移方案**再动） |")
E3_NEW = ("| " + BT + "TAIL-195" + BT + " 🏗 **结构债**（拆两个环 ＋ `core` 反向依赖） | "
          "⭐ **立刻**（⭐ 用户 2026-09-30 改裁 `B`：**现在就做** —— 原话「距产包还有好几天，够做完」） | "
          "**四问**：① **不是任何尾巴的前置**，但是「**以后改后端更省**」的前置；② **成本不随时间变贵**"
          "（⚠️ 但**改动的下游对齐量**随时间变多）；③ **同域 = 后端装配层 ＋ 导出层**（`core/` ↔ 各 `mod*/` ↔ `report_export/`）；"
          "④ ✅ **前置已到位** —— ⭐ **判据迁移方案已出**（" + BT + "work/10-designs/设计-结构债-195-迁移方案-20260930.md" + BT +
          "）；⚠️ 实测**纠正两处偏小**：`core` 反向依赖是 **4 个件**（不是 1 个）· 批 1 **17 处引用** · 批 2 **122 处 / 48 件** | "
          "触发 = 用户「`B`，全做」；⚠️ **硬约束** ＝ 批次须在**产包（前一天）之前收口**（产包闸只认「工作区干净 ＋ 尺子全绿」） |")

RECEIPT_ANCHOR = "| ⭐ **交接编号** |"
INSERT_ROW = ("| ⭐⭐ **2026-09-30 晚 · 增量（修订 8）** | **状态** ＝ 今天四批全办完：`TAIL-64` **收口销号** · "
              "`TAIL-202`（i8 未绑即拒）**当日立·办·销** · **文档审计「全按推荐」四项落纸**（新尾巴 `TAIL-203` 也已办完销号 ⇒ "
              "计划余量 **8 → 82**）· **产包收录面收口**（交付面 **2 件快照**进包 ＋ `-WriteBaseline` 开关）· "
              "⚠️ **`TAIL-195` 改裁**：用户定 `B`（**现在就做**）⇒ **当前目标 ＝ 按方案做批 1**｜"
              "**提交位置** ＝ HEAD **`ccab744`** · **工作区干净** · ⚠️ **本地领先远端 2（未 push）**｜"
              "**权威资料（新增）** ＝ `work/10-designs/设计-结构债-195-迁移方案-20260930.md`（批 1/批 2 逐处清单 ＋ 判据迁移）· "
              "`work/10-designs/设计-文档审计-20260930.md`（§六 裁定与执行记录）｜**接续动作** ＝ 见下面「入门口令」的**第一步**｜"
              "**交接状态** ＝ **材料已核对（本表）· 待接手核验**（源任务编号 / 接手任务编号：本宿主未提供 ⇒ **留空**；"
              "⚠️ 本宿主**没有「新建对话」的工具** ⇒ 接续走**手动入口**） |")

GATE = ("项目：D:\\dev\\mtrl-workbench\n"
        "交接来源：.workbuddy\\plans\\开发计划-主文档.md §13.6 → HANDOFF-20260930-01（本表已**增量刷新到「修订 8」**；⛔ 别按 -20260929-01 及更早的接续）\n"
        "入场（只读，先别改业务文件）：\n"
        "  ① 读 §13.6 那张表 —— ⭐⭐ **先读表里那条「2026-09-30 晚 · 增量（修订 8）」行**（状态 / 提交位置 / 权威资料 / 第一步都在那儿）；\n"
        "  ② 读 ops\\前端设计守则-以使用用户为中心.md（**前端口径唯一主人**；动前端必须先读）；\n"
        "  ③ ⭐ **当前这件的方案件** ＝ work\\10-designs\\设计-结构债-195-迁移方案-20260930.md（批 1 逐处清单 ＋ 批 2 目标形态 ＋ 判据迁移 ＋ 闸门）；\n"
        "  ④ 读 .codebuddy\\memory\\2026-09-30.md（**§1–§33**：当天逐批实况 —— P4/P5 收口 · `TAIL-202` · 产包收录面 · 文档审计 · `TAIL-203` · `TAIL-195` 改裁）；\n"
        "  ⑤ 跑闸门（期望全绿）：\n"
        "     backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_run_rulers.py    （16 把尺子 · rc=0 · BAD: []）\n"
        "     backend\\.venv\\Scripts\\python.exe -X utf8 tools\\audit\\acc_report.py      （四态 · 644 绿 / 0 红）\n"
        "     backend\\.venv\\Scripts\\python.exe -X utf8 tools\\audit\\doc_audit.py --ui  （必须修 0 ＋ 交付面四检 rc=0）\n"
        "     backend\\.venv\\Scripts\\python.exe -X utf8 tools\\audit\\audit_meta.py      （⚠️ 黄档也读汇总行）\n"
        "     backend\\.venv\\Scripts\\python.exe -X utf8 tools\\audit\\audit_work.py      （T14/T15/T20）\n"
        "     ⚠️ 改过 ops\\*.ps1 或 tools\\**\\*.ps1 ⇒ 再跑 tools\\oneoff\\_ps_bom.py ＋ _ps_parse_check.ps1\n"
        "     ⚠️ 动后端装配 / import 面 ⇒ **必跑** alembic check ＋ pytest tests/test_schema_drift.py\n"
        "已确认限制：① 能机器判的**必须挂判据**（⛔ 不许「只改不挂」）· 文案一律**人话**；② ⛔ 别造第二套视觉语言；\n"
        "  ③ ⛔ **别复制一份绕开结构问题**（那会长出第二套口径 —— 本仓最贵的病）；④ ⛔ **提交要用户点头**；\n"
        "  ⑤ ⛔ **产包不在现在**（重新产包 ＝ 去办公室的「**前一天**」）· ⑥ 冻结点 ＝ **你说冻就冻**；\n"
        "  ⑦ 动交付面（PRD / 验收基线 / demo）**先备份** ＋ 同批说明（⛔ 不静默改）；\n"
        "  ⑧ ⛔ **文档里别写「将要新建的路径」当普通路径**（`T3` 会判成断链 —— 已实测）。\n"
        "已确认的下一步：⭐⭐ 用户 2026-09-30 定 `B` 案 —— **`TAIL-195` 现在就全做**（原话「距产包还有好几天，够做完」）：\n"
        "  ⏭ **第一步 ＝ 批 1**（按方案 §二）：`backend/app/core/models_registry.py` 挪到 `backend/app/models_registry.py`\n"
        "     （`git mv` ⇒ **17 处** import 跟改 ⇒ 改 `tests/test_schema_drift.py` 的靶常量 ＋ 三处文案 ⇒ **同批**补\n"
        "     `tests/test_layering.py` 上半「`app/core/**` 不得 import `app.mod*`」＋ 变异件 `_mut_layering.py`）\n"
        "     ⇒ 闸门全绿（pytest 644/0 · 16 尺子 · **alembic check** · 真机 `_shell_smoke`）⇒ **一个提交**；\n"
        "  ⏭ **第二步 ＝ 批 1b（待用户定）**：`core` 另 3 个单点反向引用（`app_settings` / `identity` / `projects`）；\n"
        "  ⏭ **第三步 ＝ 批 2**：拆两个环（`report_export ⇄ 业务包` **122 处 / 48 件** ＋ `mod03 ⇄ mod05`）—— ⚠️ 最大，按方案 §三 两案**组合**用。\n"
        "  ⚠️ **硬约束**：批次必须**赶在产包（前一天）之前收口**（产包闸只认「工作区干净 ＋ 尺子全绿」）。\n"
        "验收：全套 pytest 100% ＋ **16 把尺子 rc=0** ＋ `alembic check` ＋ `doc_audit --ui` 修 0 ＋ `test_schema_drift` 绿 ＋\n"
        "  （改壳则）**壳基线 `--snapshot` 盖章** ＋ 每批台账 §15 销号 ＋ 能机器判的必须挂判据（含**反向灵敏度**）；\n"
        "  ⚠️ 收尾口径一律以 `.codebuddy/memory/2026-09-30.md` 的实况为准。")


def main() -> int:
    text = PLAN.read_bytes().decode("utf-8")
    nl = "\r\n" if "\r\n" in text[:3000] else "\n"
    ok = True
    for name, old, new in (("E1", E1_OLD, E1_NEW), ("E2", E2_OLD, E2_NEW), ("E3", E3_OLD, E3_NEW)):
        n = text.count(old)
        print(f"{name}: 命中 {n} 处" + ("" if n == 1 else "  ⛔ 期望 1"))
        if n != 1:
            ok = False
        else:
            text = text.replace(old, new)
    if not ok:
        print("⛔ 有锚点不唯一 —— 停手，未写盘"); return 1

    lines = text.splitlines(keepends=True)
    # 3) 交接表里插一行
    ri = next((i for i, l in enumerate(lines) if l.startswith(RECEIPT_ANCHOR)), None)
    if ri is None:
        print("⛔ 找不到「交接编号」行"); return 1
    lines.insert(ri + 1, INSERT_ROW + nl)
    # 4) 换入门口令代码块
    hi = next((i for i, l in enumerate(lines) if l.startswith("**入门口令（可复制）**")), None)
    if hi is None:
        print("⛔ 找不到入门口令标题"); return 1
    a = next(i for i in range(hi, len(lines)) if lines[i].startswith("```"))
    b = next(i for i in range(a + 1, len(lines)) if lines[i].startswith("```"))
    print(f"入门口令块 = 第 {a + 2}–{b} 行（{b - a - 1} 行 ⇒ 换新 {GATE.count(chr(10)) + 1} 行）")
    lines = lines[:a + 1] + [GATE.replace("\n", nl) + nl] + lines[b:]

    shutil.copy2(PLAN, PLAN.with_name(PLAN.name + ".pre-r8"))
    PLAN.write_text("".join(lines), encoding="utf-8", newline="")
    print(f"✅ 写盘 · 计划 {len(lines)} 行（写前备份 = {PLAN.name}.pre-r8）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
