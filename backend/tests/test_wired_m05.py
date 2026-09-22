"""`m05`（付款流水与欠款）**前端壳接线**断言（离线 · 静态）。

配套：运行时端到端 = `tools/probe/_e2e_m05_wired.py`（真机 ＋ 真库，跑完清理）·
结构一致性 = `tools/audit/ui_parity.py`（U1 视图一致 ＋ **U2b 已接线页不得留演示数组**；
⚠️ `m05` 在 U1 里**有 1 条已登记漂移** —— `V.m05` 的机械结算项换数据源，理由写在登记簿里）。

⚠️ **本文件测不了什么**：静态检查（壳里有没有那些接线点），**不证明运行时真调通**。两把都要。

⭐ 反向断言是重点：**欠款 / 台账 / 付款统计不许再由前端自算**（那是第二份口径），
   写动作不许再用本地赋值冒充落库。
"""

from __future__ import annotations

from pathlib import Path

from tests.acc_plugin import acc

from tests.shell_src import SHELL, with_kernel  # noqa: F401  ← `P4`① 读取点收敛（`with_kernel`：`TAIL-67`）


def _slice(name: str, limit: int = 16000) -> str:
    """取壳里 `V.<name>=()=>{…}` 的切片（花括号配平）。"""
    i = SHELL.find(f"\nV.{name}=()=>{{")
    assert i > 0, f"壳里找不到 `V.{name}=()=>{{`"
    i += 1
    depth, k = 0, SHELL.find("{", i)
    while k < len(SHELL):
        if SHELL[k] == "{":
            depth += 1
        elif SHELL[k] == "}":
            depth -= 1
            if depth == 0:
                break
        k += 1
    body = SHELL[i:k + 1]
    assert 2000 < len(body) < limit, f"`V.{name}` 切片长度 {len(body)} 可疑 —— 配平可能跑偏"
    return body


# ------------------------------- `§19` 批 3：旧页删除后，几条**形态** claim 由新壳接管
# 原先在 `tests/test_page_m05.py` 里借**旧服务端页**观测（该文件已改守数据出口 ✓）。


@acc()
def test_台账两侧共用同一个项目选择器且无切换口径():
    """§4.5.4：台账两侧**共用同一个**项目选择器（切一次两边都换）；⛔ 没有「切换口径」按钮。"""
    assert "const ledPjPanel=()=>projPanel({list:ledProjs,selected:()=>[ledCur()],pickAct:'ledPjPick'" in SHELL, \
        "两侧没有共用同一个项目选择器"
    assert "切换口径" not in _slice("m05"), "壳里出现了「切换口径」按钮"


@acc()
def test_撤销入口只在生效行且必须填原因():
    """§4.4.5：撤销按钮**只在生效行**出（已撤销那行给「—」）；撤销**必须填原因**（后端把关）。"""
    s = _slice("m05")
    assert 'data-act="revDlg"' in s, "流水行没有撤销入口"
    assert """${f.voided?'<span class="mut sm">—</span>':`<button class="btn sm dg" data-act="revDlg\"""" in s, \
        "撤销入口不是「只在生效行」出的"
    assert "撤销原因必填" in SHELL, "没写明撤销必须填原因"


@acc()
def test_流水空态跨列由表头派生且不分页():
    """空态行的 `colspan` **由表头派生**（⛔ 不写死）；该表**不做分页**（一次给全）。"""
    s = _slice("m05")
    assert 'colspan="${thCount(FL_THEAD)}"' in s, "空态行的跨列数不再由表头派生"
    assert "没有付款流水" in s, "空态提示丢了"
    assert "不做分页" in s, "没写明「不做分页」"


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


# --------------------------------------------------------------- 台账导出（`TAIL-04` 片 2＋3）


@acc("ACC-FLOW-LED-001", "001-11")
def test_台账导出走真下载而不是假成功():
    """⭐ `TAIL-04` **片 2＋3**：台账成品由后端模板填充生成 ⇒ 壳侧必须是**真下载**。

    ⚠️ 原型那个「保存到本地」是 `data-act="exp"`（诚实占位：**没有文件产生**）——
       接线后**必须换成**本页自己的动作，否则又变成"点了像成功、其实没文件"。
    """
    assert "ledExpSave:async ()=>{" in SHELL, "缺真下载动作 `ledExpSave`"
    assert "/api/m05/ledger/export?projects=" in SHELL, "没走台账导出端点"
    assert "'&ym='+encodeURIComponent(bjMonth(-1))" in SHELL, \
        "报告月没原样带给后端（§9.2 材料报表类默认 = 上月；⛔ 前端不另算一份期间）"
    assert "x-export-filename" in SHELL, "文件名没从 `X-Export-Filename` 带出（命名规则的主人在后端）"
    # ⛔ 旧的**假成功**必须消失
    assert 'data-act="exp" data-t="逐月欠款台账"' not in SHELL, "预览弹窗还留着假成功的 `exp`"
    assert 'data-act="ledExpSave"' in SHELL, "预览弹窗的「保存到本地」没接到 `ledExpSave`"


@acc("ACC-FLOW-LED-001", "001-11")
def test_台账导出失败必须给人原因不静默():
    """后端失败回 **JSON 200 ＋ `ok:false` ＋ 中文原因**（没选项目 / 项目不在档案 / 模板坏 /
    **显示区对账不过**）⇒ 壳必须**弹原因**，⛔ 不能静默、也不能当文件下载。"""
    # ⚠️ 取体的**终点锚**用**下一个动作名**（`ledNote`，纯 ASCII）—— 别用中文注释当锚：
    #    中文注释里哪怕一个标点不同就找不到（本文件实测踩到一次），而动作名是代码结构。
    i = SHELL.index("ledExpSave:async ()=>{")
    body = SHELL[i:SHELL.index("\n ledNote:t=>{", i)]
    assert 100 < len(body) < 2500, f"取体越界（{len(body)} 字符）—— 锚点可能切歪了"
    _b = with_kernel(body)         # ⭐ `TAIL-67`：错误分类已抽到 `dlExport` 通用件
    assert "ct.includes('application/json')" in _b, "没按 content-type 分流"
    assert "后端没给原因" in _b, "失败时没把后端的中文原因给用户"
    assert "r.ok" in _b and "HTTP ${r.status}" in _b, \
        "非 2xx 没显式报错（会静默产出空文件）"
