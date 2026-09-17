"""`m04`（付款计划）**前端壳接线**断言（离线 · 静态）。

配套：
- 运行时端到端 = `tools/_e2e_m04_wired.py`（真机 ＋ **真库**，跑完清理）
- 结构一致性 = `tools/ui_parity.py`（U1 视图逐行一致 / U2b 已接线页不得留演示数组）

⚠️ **本文件测不了什么**：它是**静态检查**（壳里有没有那些接线点），**不证明运行时真调通**。
   两把都要 —— 这正是「判据绿 ≠ 链路对」的教训。

⭐ 其中四条是**反向**断言：审查结果不许前端自算 · 不许用本地赋值冒充落库 ·
   不许对没接的动作说成功 · 已接线页的**演示数组必须已删**。
"""

from __future__ import annotations

from pathlib import Path

from tests.acc_plugin import acc

SHELL = (Path(__file__).resolve().parents[1] / "app" / "web" / "index.html").read_text(
    encoding="utf-8"
)


# --------------------------------------------------------------- 接线点（正向）


@acc()
def test_壳把m04标为已接后端并指向真实端点():
    assert "'m04'" in SHELL and "const WIRED=new Set(" in SHELL
    assert "/api/m04/plans?year_month=" in SHELL
    for fn in ("API.plCell", "API.plRematch", "API.plForce", "API.plForceCancel",
               "API.plDelete", "API.plDeleteImpact"):
        assert fn in SHELL, f"缺写动作接线点：{fn}"


@acc()
def test_付款计划字段在适配层完成转形():
    """后端 `audit_result` / `forced_through` / `is_manual` / 派生两列 → 原型 `PL_COLS` 字段名。"""
    assert "function adaptPlan(x)" in SHELL
    assert "result: x.audit_result" in SHELL
    assert "forced: !!x.forced_through" in SHELL and "manual: !!x.is_manual" in SHELL
    assert "pay_date: 'pay_date'" in SHELL or "PL_COL_API" in SHELL
    # 「项目」列必须保留**用户填报原值**（换成展示名会把「未匹配」这一档抹掉）
    assert "proj: x.project_input || ''" in SHELL


@acc()
def test_写动作统一走后端并以后端为准重拉():
    assert "async function reloadPlans()" in SHELL
    assert "async function plAct(fn, okMsg, ms)" in SHELL
    # 删除走 §4.3.6 两步：先取**后端**影响范围
    assert "await API.plDeleteImpact(ids)" in SHELL


# --------------------------------------------------------------- 反向（不许再出现）


@acc()
def test_审查结果不再由前端自算():
    """唯一出口 = 后端 `domain.audit_rows`（§4.3.4 的 6 种判定）。

    原型原先在浏览器里实时派生（查通知书 ＋ 重复检测）⇒ 那是**第二份口径**。
    """
    assert "const plRev=(p)=>String((p&&p.result)" in SHELL, "`plRev` 没改成读后端"
    assert "if(Number(p.monthAmt)>Number(n.approve)-paidOf(n.id)) return '超过未付';" not in SHELL, \
        "旧的**前端判定**还在 ⇒ 口径有两份"


@acc()
def test_写动作不許用本地赋值冒充落库():
    assert "p[f]=String(t.value" not in SHELL, "行内改列还在改内存"
    assert "p.forced=true" not in SHELL, "强制通过还在改内存"
    assert "PLs.splice(i,1)" not in SHELL, "删除还在改内存"
    assert "plAlert" not in SHELL and "plNextIds('PL',3)" not in SHELL, "旧的造演示行还在"


@acc()
def test_已接线页的演示数组必须已删():
    """`m04` 标了「已接后端」⇒ 演示数组 `PL` 不得残留（产品化红线①）。"""
    assert "const PL = [" not in SHELL
    assert "let PLs=[];" in SHELL


@acc()
def test_未接通的动作不得假装成功():
    """Excel 导入 / 手动行（本轮不接）⇒ 必须如实说未接通（⛔ 不留半拉子入口）。"""
    assert SHELL.count("尚未接通") >= 6
    assert "plRowEditId=PL_NEW_ID" not in SHELL, "手动行还在进草稿态（填了却存不进去）"
