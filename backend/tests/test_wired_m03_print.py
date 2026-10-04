"""`m03` **批量打印 / 只导出 PDF / 打印机设置**的壳侧断言（`TAIL-46`）—— 离线静态。

**接的是什么**：这三件事原先**只有旧页 `mod03_notice/static/m03.html` 能做**（壳里 `ntPrint` 只回一句
「（模拟）→ 成功」、打印机设置压根没有入口）⇒ 旧页一删就**没有能真打印的入口**了。
⇒ 壳里：`ntPrint` 改**真调** `POST /api/m03/batch`；「只导出 PDF」「打印机设置」两个入口由
   `BIND.m03` **渲染后注入**（切片一行不动 ⇒ `ui_parity` 无漂移）。

⚠️ 静态检查**不证明运行时能跑**（真打印还要**打印机 + 人**）；离线那一半由
   `test_acc_pay_setup.py`（设置读写）与 `backend/tests` 的批量端点用例覆盖。
"""

from __future__ import annotations

from pathlib import Path

from tests.acc_plugin import acc

from tests.shell_src import SHELL, act_entry, bind_blocks, func_body  # noqa: F401  ← `P4`① 读取点收敛

# ⭐ 2026-10-03（`TAIL-219` 批 2b）：本件原先自带剪刀 `_fn`（"标记 A → 标记 B"）——
#    已**整把删掉**，取段改走壳的语义口径（`BIND` 块 / 动作条 / 函数各用对口的那个）。⛔ 别写回来。


@acc("ACC-PAY-SETUP-001", "001-01")
def test_打印机设置入口在新壳里可发现且真读写后端():
    """`001-01` 的口径是「**系统内提供可发现的修改入口**」—— ⛔ 它钉的**不是**旧页文件。
    旧页要删（§19）⇒ 断言搬到新壳：入口由 `BIND.m03` 注入到「批量打印」旁边，读写走 GET/PUT。"""
    assert "m03PrinterOpen" in SHELL and "打印机设置" in SHELL
    assert "API.printerGet()" in SHELL, "要读当前值回填（⛔ 不许只弹个空框）"
    assert "API.printerSet(" in SHELL, "保存要真写后端（写配置 + 清缓存 ⇒ 即时生效）"
    # ⚠️ 壳里 `BIND.m03` **有两块**（`pages-a.js` 管全选框 · `core.js` 链式注入打印机入口）
    #    ⇒ 按**内容**挑那一块（⛔ 别让它静默挑第一处 —— `bind_block()` 多处命中会抛）
    injects = [b for b in bind_blocks("m03") if "m03PrinterOpen" in b]
    assert len(injects) == 1, f"注入「打印机设置」入口的 `BIND.m03` 应当恰好一块，实得 {len(injects)}"
    inject = injects[0]
    assert "data-act=\"m03PrinterOpen\"" in inject, "入口要在渲染后注入（切片一行不动）"
    assert "dataset.m03More" in inject, "注入必须**幂等**（⛔ 多次 render 不叠加）"
    assert "_BIND_M03_OLD" in inject, "⛔ 不许覆盖别的 `BIND.m03`"


@acc()
def test_批量打印真的调后端且不再有模拟字样():
    """⭐ 原来那三件事只有旧页能做；壳里 `ntPrint` 只回「（模拟）→ 成功」= 假话。
    现在必须**真调** `POST /api/m03/batch`（`ids` = 系统内勾选的通知书）。"""
    nt = act_entry("ntPrint")
    assert "m03RunBatch(rows,'print')" in nt
    assert "（模拟）" not in nt and "模拟" not in nt, "⛔ 不许再假装成功"
    assert "API.m03Batch(ids, mode)" in SHELL, "要真的打后端那一个端点"
    assert "pickSet" in nt, "`ids` 必须来自**系统内勾选**（001-09：不收文件 / 不收手输清单）"


@acc()
def test_结果逐条如实_失败与未产出单号都要说出来():
    """⛔ 禁静默：失败要带原因、**未产出的单号必须显式列出**（001-07 / PDF-001-06 都要求）。"""
    run = func_body("m03RunBatch")
    assert "r.unprinted_bill_nos" in run, "未产出单号要列出来（别只报个数字）"
    assert "x.reason" in run and "失败原因" in run, "失败要带原因"
    assert "catch (e)" in run and "没能完成" in run, "整批失败也要说清（⛔ 不吞）"
    assert "不自建打印模板" in run, "口径要写清（DEV-P-07）"


@acc()
def test_只导出PDF与批量打印共用同一个出口():
    """同一次勾选、只换 `mode` ⇒ **只许有一个出口**（一份能力一个主人）。"""
    pdf = act_entry("ntPdf")
    assert "m03RunBatch(rows,'pdf')" in pdf
    assert SHELL.count("m03RunBatch(rows,") >= 2, "两个入口都要走它（批量打印 / 只导出 PDF）"
    assert SHELL.count("async function m03RunBatch(") == 1, "出口只许**定义一次**（一份能力一个主人）"


@acc()
def test_反向_不做本地打印也不自造入参():
    """⛔ 两条反向：
    ① `DEV-P-07`：**不自建打印模板**、不做本地渲染 ⇒ 壳里不许出现 `window.print()` / 本地排版；
    ② 入参**只**来自勾选（⛔ 不许出现"上传文件 / 手输单号清单"那条路）。"""
    run = func_body("m03RunBatch")
    for forbidden in ("window.print(", "printWindow(", "<iframe", "jsPDF", "html2canvas"):
        assert forbidden not in run, f"⛔ 不许本地打印/排版（发现有 {forbidden}）"
    assert "input type=\"file\"" not in run and "split(" not in run, \
        "⛔ 入参不许来自文件或手输清单（只能来自系统内勾选 `pickSet`）"
