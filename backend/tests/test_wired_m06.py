"""`MOD-06` 过程资料的**机械源**接线 —— 离线断言。

⭐ 本轮的性质是「**只换来源、不改结构**」：`MACH6` 仍是 `{仓库名: {核算月: [6 列]}}`，
   所以壳里十几处引用（过程资料 17 列的机械 6 列 / 活动大表 / 机械结算 / 台账候选）**一行未改**。
   断言要钉住的正是这件事：**来源变了、引用面没变、且不许留取零出口**。

⚠️ 反向三条：
1. 不许再往壳里塞演示 `MACH6`（页面会显示演示值，与后端 KPI **打架**）。
2. 不许留 `m05MechSettle` 那种**取零出口**（它是"未接线"的临时态 ⇒ 接线后必须消失）。
3. `V.m06` 切片内不得出现 `API.`（原型渲染逻辑一行不改 —— `D18`）。
"""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ROUTER = (ROOT / "backend" / "app" / "mod06_proc" / "router.py").read_text(encoding="utf-8")


# ── ⭐ 2026-10-04（`TAIL-219` 批 2b 余下 ②）：本件两把自造剪刀已换成语义窗口子 ──────────
#   · `page_slice("m06")` ⇒ `page_slice("m06")`：**页切片的唯一算法**（原先本件自写"花括号配平"，
#     与 `ui_parity`/`shell_src` 那套**并存** = 同一件事两套算法 —— 正是本要治的病）。
#     实测：`page_slice("m06")` 比旧切片**多**页尾那段横幅注释，而本件三条断言（无 `API.` / 无 `mechOpen` /
#     有 `TBL({head:DIFF_THEAD,`）**换后仍成立** ⇒ 换得了（量测件 `.scratch/local/_tail219_batch2b_rest.py`）。
#   · `_act_body(name)` ⇒ `act_entry(name)`：⭐ 逐字节一致（`procExpToggle` 789 / `mechOpen` 2577 都对上）。










def test_后端机械读数端点存在且形状对齐原型():
    assert '@router.get("/api/m06/mech")' in ROUTER, "后端缺 `GET /api/m06/mech`"
    assert "MECH_COLUMNS" in ROUTER, "端点没按 `MECH_COLUMNS` 出 6 列"
    assert '"mech": out' in ROUTER, "端点没出 `mech` 键（壳按它填 `MACH6`）"






# ============================================================== `TAIL-38` · 录机械费入口






# --------------------------------------- `ACC-RPT-PROC-001` 的**形态**半边（搬家 · §19 批 2）
#
# 这 9 条判据原先有 6 条带"页面形态"观测（`tab=` / 筛选栏 radio / 合计行 `colspan` 之和 /
# `tot` 行 …）。旧页删除（`D18`）⇒ 形态那半边**改指新壳**（⛔ 判据不删）。
# ⭐ 新壳把这些做成了**结构**（格数由表头派生 / 单选面板 / 选中即收起）—— 比逐格数更硬。

























def test_后端机械写端点存在():
    assert '@router.post("/api/m06/mech")' in ROUTER, "后端缺 `POST /api/m06/mech`（`TAIL-38` 的写入口）"
    # ⚠️ 必须**看 API 端点自己的函数体** —— 只写「文件里含 `mech_ui.parse_mech_values(`」是**假绿**：
    #    PRG 端点（`POST /m06/mech`）里也有一处 ⇒ 变异掉 API 端点那一处照样能过。
    i = ROUTER.find("def api_mech_save(")
    assert i > 0, "后端缺 `def api_mech_save(`"
    body = ROUTER[i:i + 2000]
    assert "mech_ui.parse_mech_values(" in body, (
        "写端点没走 `mech_ui.parse_mech_values`（判定该与 PRG 端点复用**同一出口**，不另写一套）"
    )


# --------------------------------------------------------------- 按模板导出（`TAIL-04` 片 4a）






# ------------- ⭐ `TAIL-173`（2026-09-29 · 用户裁定 `A`）：`A4` 顺手报的两件，本批落地
