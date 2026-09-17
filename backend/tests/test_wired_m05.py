"""`m05`（付款流水与欠款）**前端壳接线**断言（离线 · 静态）。

配套：运行时端到端 = `tools/_e2e_m05_wired.py`（真机 ＋ 真库，跑完清理）·
结构一致性 = `tools/ui_parity.py`（U1 视图一致 ＋ **U2b 已接线页不得留演示数组**；
⚠️ `m05` 在 U1 里**有 1 条已登记漂移** —— `V.m05` 的机械结算项换数据源，理由写在登记簿里）。

⚠️ **本文件测不了什么**：静态检查（壳里有没有那些接线点），**不证明运行时真调通**。两把都要。

⭐ 反向断言是重点：**欠款 / 台账 / 付款统计不许再由前端自算**（那是第二份口径），
   写动作不许再用本地赋值冒充落库。
"""

from __future__ import annotations

from pathlib import Path

from tests.acc_plugin import acc

SHELL = (Path(__file__).resolve().parents[1] / "app" / "web" / "index.html").read_text(
    encoding="utf-8"
)


# --------------------------------------------------------------- 接线点（正向）


@acc()
def test_壳把m05标为已接后端并指向四个端点():
    assert "'m05'" in SHELL and "const WIRED=new Set(" in SHELL
    for fn in ("API.flows()", "API.debt()", "API.stats(", "API.ledger(", "API.flowRevoke("):
        assert fn in SHELL, f"缺接线点：{fn}"
    assert "/api/m05/flows?year_month=" in SHELL
    assert "/api/m05/ledger?project_id=" in SHELL


@acc()
def test_流水行与期初行在适配层完成转形():
    assert "function adaptFlow(x)" in SHELL and "function adaptOpening(x)" in SHELL
    # ⭐ 仓库名（归并键）与展示名分开 —— 拿展示名当键会静默失配
    assert "projKey: x.project_key || ''" in SHELL
    assert "proj: x.project_key || x.project_label || ''" in SHELL
    assert "proj: x.project_display || ''" in SHELL


@acc()
def test_读写都走统一的出口与外壳():
    assert "async function reloadM05()" in SHELL
    assert "async function m05Act(fn, okMsg, ms)" in SHELL
    # 期初 / 备注目前只有 PRG 表单端点 ⇒ 必须用表单编码发（不是 JSON）
    assert "postForm: async (url, obj) => {" in SHELL
    assert "URLSearchParams(obj || {})" in SHELL


# --------------------------------------------------------------- 反向（不许再出现）


@acc()
def test_欠款台账统计不再由前端自算():
    """⭐ 三块的**唯一出口 = 后端**（§4.5.1 / §4.5.4 / §4.5.5）。

    原型在浏览器里按 `NO` / `MACH6` / `JCs` / `LGs` 现算 —— 那是第二份口径，
    而且**机械会读到演示数据**（与后端 KPI 打架）。
    """
    # `debts()` 只读后端
    assert "const d = M05.debt || {};" in SHELL
    assert "d.by_category || []).find(x => x.category === c" in SHELL
    # 台账行只读后端
    assert "const ledOpen=(sc,proj)=>{ const side=m05Side(sc)" in SHELL
    assert "const ledRows=(sc,proj)=>{ const side=m05Side(sc)" in SHELL
    # 付款统计只读后端
    assert "const pstData=()=>{ const st=M05.stats||{};" in SHELL
    # ⛔ 旧的**前端自算**必须消失
    assert "const 辅材=N2(F-FP+lgF)" not in SHELL, "欠款还在前端算"
    assert "const ms=NO.filter(n=>ntLive(n)&&n.cat===sc&&ntProjKey(n)===proj).map(ntYm);" not in SHELL, \
        "台账还在前端按月拼行"
    assert "const axes=pstMonthsOfYear" not in SHELL, "付款统计还在前端拼时间轴"


@acc()
def test_写动作不許用本地赋值冒充落库():
    assert "f.voided=true; f.reason=rs;" not in SHELL, "撤销还在改内存"
    assert "LGs.push(O(['LG'" not in SHELL, "期初还在前端 push"
    assert "LGs.splice(i,1); closeModal()" not in SHELL, "期初删除还在改内存"
    assert "LEDNOTE[k]=v" not in SHELL, "台账备注还在写前端缓存"


@acc()
def test_机械结算源已接线_读真源():
    """⭐ **本轮改动**（`TAIL-27` 第 6 页 · `MOD-06` 机械源接线）：机械结算源 = 过程资料机械 6 列，
    现已接后端（`/api/m06/mech` ⇒ 壳里 `MACH6`）⇒ `V.m05` 的机械结算项**恢复原型写法**
    `machSettleOf(k)`，与原型**逐字一致**（那条 `ui_parity` 登记漂移已消号）。

    ⚠️ 本条断言**原先钉的是「未接线 ⇒ 取 0」的临时态**（那时取演示 `MACH6` 会让本页机械数
       与后端 KPI 打架）—— 接线完成后**按事实反转**：必须读真源，且取零出口必须消失。
    """
    assert "m05MechSettle" not in SHELL, "取零出口 `m05MechSettle` 还在（临时态没清）"
    assert "N2(machSettleOf(k)" in SHELL, "`V.m05` 的机械结算项没接真源"
    # ⚠️ 不要用「从 `V.m05=` 扫到 `V.m06=`」这种切片 —— 中间夹着 MOD-06 的**顶层助手函数**
    #    （本文件第一次就是这么切歪的）。**钉具体串**更准。


@acc()
def test_已接线页的演示数组必须已删():
    assert "const LG = [" not in SHELL
    assert "LG.map(r=>O(r,LG_COLS))" not in SHELL
