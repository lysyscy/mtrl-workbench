"""`m01`（项目档案）**前端壳接线**断言（离线 · 静态）＋ `/api/m01/trails` 契约。

**为什么单独立一个文件**：`ui_parity` 只管「壳的视图切片与原型**逐行一致**」，它自己写明了
**测不了**「标了已接后端、其实没接」。本文件补的正是那一条。

⚠️ **本文件测不了什么（别误当已覆盖）**：这些是**静态检查** —— 壳里有没有那些接线点，
   **不证明运行时真的调通**。运行时那一段由 `tools/_e2e_m01_wired.py`（真机 ＋ **真库**、跑完清理）覆盖。
   ⇒ 两把都要：这正是「**判据绿 ≠ 链路对**」的教训。

⭐ 其中三条是**反向**断言（"不许再出现"）：前端**不得自己算**状态不变式、
   不得再用本地赋值冒充落库、不得对没接的动作**假装成功** —— 判定与落库只许有一个出口（后端）。
"""

from __future__ import annotations

from pathlib import Path

from tests.acc_plugin import acc

SHELL = (Path(__file__).resolve().parents[1] / "app" / "web" / "index.html").read_text(
    encoding="utf-8"
)


# --------------------------------------------------------------- 接线点（正向）


@acc()
def test_壳把m01标为已接后端并指向真实端点():
    """`WIRED` 含 `m01`，且壳里真的出现该模块的端点（读全量 ＋ 留痕）。"""
    assert "'m01'" in SHELL and "const WIRED=new Set(" in SHELL
    # ⚠️ `status=all`：原型的筛选含归档（默认值只是"在建"）⇒ 取数必须全量
    assert "/api/m01/projects?status=all" in SHELL
    assert "/api/m01/trails" in SHELL


@acc()
def test_项目状态在适配层完成内部值与显示值的互转():
    """后端 `active/archived` ⇄ 原型枚举 `在建/归档`。

    ⚠️ **这是实测出来的坑**：不转 ⇒ `fPj.status`（`'在建'`）与 `p.status`（`'active'`）**永不相等**
    ⇒ 项目档案页**恒为空**、状态列 `<select>` 一个都不选中，而且**静默、不报错**。
    """
    assert "PJ_STATUS_LABEL" in SHELL and "PJ_STATUS_VALUE" in SHELL
    assert "active: '在建'" in SHELL and "archived: '归档'" in SHELL
    assert "PJ_STATUS_LABEL[p.status]" in SHELL, "adaptProject 必须走这个映射"
    assert "PJ_STATUS_VALUE[v]||v" in SHELL, "写回时必须把中文换回内部值"


@acc()
def test_项目id与父壳id一律转字符串():
    """原型全站 `x.parent === p.id` 做**同值比较** ⇒ 两侧必须同为字符串。

    （与已登记的 `id` 纪律同一条：不转 ⇒ 静默失配。）
    """
    assert "id: String(p.id)" in SHELL
    assert "parent_shell_id == null ? null : String(" in SHELL


@acc()
def test_关键字与留痕在适配层转形():
    """关键词：后端**数组** ⇄ 原型**竖线串**；留痕：后端**对象** ⇄ 卡片的**六元数组**。"""
    assert "const kwJoin" in SHELL and "const kwSplit" in SHELL
    assert "function adaptTrail" in SHELL
    assert "kw: kwJoin(p.match_keywords)" in SHELL


@acc()
def test_写动作统一走后端并以后端为准重拉():
    """`reloadProjects` ＋ `pjAct`（失败时**把后端原因原样给用户**并回滚到后端状态）。"""
    assert "async function reloadProjects()" in SHELL
    assert "async function pjAct(fn, okMsg, ms)" in SHELL
    assert "API.pjStatus" in SHELL and "API.pjUpdate" in SHELL and "API.pjOrd" in SHELL


# --------------------------------------------------------------- 反向（不许再出现）


@acc()
def test_前端不再自己算状态不变式():
    """⛔ 本地那套「壳下还有在建小微 ⇒ 不许归档」必须删干净 ——

    唯一出口 = 后端 `domain.apply_status_change`（与判据同一份纯函数）。
    前端留着第二份 ⇒ 两份规则必然分叉（D18：判定与落库一律后端）。
    """
    assert "不能归档" not in SHELL, "本地不变式文案还在 ⇒ 前端仍在自己判"
    assert "pushTrail(PJ_TRAIL" not in SHELL, "留痕必须由后端写（前端只读展示）"


@acc()
def test_写动作不許用本地赋值冒充落库():
    """旧写法（改内存 → `render()`）一律消失：改完必须**以后端为准重拉**。"""
    assert "p.disp=v; render()" not in SHELL
    assert "p.full=v; render()" not in SHELL
    assert "kw=$('#kwV').value" not in SHELL
    assert "p.name=nv;" not in SHELL


@acc()
def test_未接通的动作不得假装成功():
    """删除 / 两个同步**仍待接通**（依赖其它尾巴）⇒ 必须**如实说未接通**。

    ⛔ 原型里的那几句"已成功"toast 是**模拟值**：壳一旦接了真后端，继续显示它就是**对用户说假话**。
    ⭐ 2026-09-18（`TAIL-30`-③）：「扶正」**已接通** ⇒ 它那句 ⏳ 必须**当场消失**
       （断言钉的临时状态完成使命就改 —— 留着就成了"已接的动作还在说没接"）。
    """
    assert "已同步仓库名单（API-05）：8 个仓库" not in SHELL
    assert "9 个项目，phid 已写入" not in SHELL
    assert "本次导入已重跑，陌生仓库告警已记录" not in SHELL
    assert "扶正尚未接通后端" not in SHELL, "扶正已接通（`TAIL-30`-③）⇒ 那句 ⏳ 该删干净"
    assert SHELL.count("尚未接通") >= 3, "仍没接的动作（删除 · 两个同步）要有明显提示"


# --------------------------------------------------- 链路 B「人工指认」（`TAIL-30`-③）


@acc()
def test_待人工指认清单与档案同源同刷且单独容错():
    """⭐ `TAIL-30`-③：`m01` 页首那个入口的清单 = **最近一次材料侧抓取**的待人工条目。

    - 与档案**同源同刷**（刚扶正完必须立刻少一条，否则用户以为没生效）；
    - ⚠️ 但它**不许拖垮档案页**：这一路失败只让清单缺失，且页面要**如实说明**（⛔ 不静默成"本来就没有"）；
    - `boot()` 里是**独立一路**（同 `m06` 那次实测的教训：一路 404 不该让全站空表）。
    """
    assert "API.pjPromotePending" in SHELL and "/api/m01/promote-pending" in SHELL
    assert "async function reloadPending()" in SHELL
    body = SHELL[SHELL.index("async function reloadProjects()"):]
    body = body[:body.index("async function pjAct(")]
    assert "await reloadPending();" in body, "档案刷新时要**一起**刷待办清单"
    assert "catch (e) { PEND_ERR =" in body, "清单取不到要**记下原因**（页面上如实说明）"
    assert "await soft('待人工指认', reloadPending)" in SHELL, "boot 里要独立一路（单独容错）"
    assert "PEND_ERR ? " in SHELL and "待指认清单没取到" in SHELL, "取不到时页面上要说出来"


@acc()
def test_指认写入口按id定位并且前端不做第二份判定():
    """⭐ 铁律 5/6：**写操作按 id 定位，禁止用名字反查**；且**前端不算任何判定**（`D18`）。

    - 提交体只给 `project_id` ＋ 那条**已知的真实仓库名** ＋ 一致性守卫用的全名；
    - 行内「扶正」按钮与页首清单**共用同一个弹窗**，匹配靠**后端给的候选行 id**
      （⛔ 不在前端拿全名比对 —— 那要复刻一份归一化，两份早晚分叉）；
    - 候选行 / 哪几行是占位行 / 条目还成不成立，**全部读后端**。
    """
    assert "pjPromote: body => API.post('/api/m01/promote', body)" in SHELL
    assert "pjPromote({project_id:id, warehouse_name:it.wh, full_name:it.full})" in SHELL, \
        "写入口必须传 project_id（⛔ 不用全名去定位）"
    assert "API.pjPromoteCandidates(it.full)" in SHELL, "候选行读后端（按全名查 = 读，可以）"
    # 行内「扶正」按钮 = 同一个弹窗的另一个入口，按**候选行 id** 找条目
    assert "PEND.findIndex(x=>(x.candidates||[]).some(c=>c.id===String(p.id)))" in SHELL, \
        "行内按钮要靠候选行 id 匹配（⛔ 不自己比对全名）"
    assert 'data-act="pjPromoteOpen"' in SHELL and "data-act=\"pjPromoteOpen\" data-pend" in SHELL
    # ⛔ 前端不许自己判断"能不能扶正"：占位标记由后端给（`c.is_placeholder`）
    assert "ph: !!c.is_placeholder" in SHELL, "占位行标记必须来自后端"


@acc()
def test_材料侧抓取回执必须露出待人工并给跳转():
    """⭐ 补的缺口：壳上抓收发结存时，回包的 `recovery` **原先根本没露出来** ——
    用户看不到"待人工 N 条"，也就不知道要去 `m01` 处理（服务端渲染页有 `summary_text`，壳侧只报条数）。
    """
    assert "const rc = r.recovery || {};" in SHELL, "回执要读 `recovery`"
    assert "rc.promoted" in SHELL and "rc.created" in SHELL, "扶正 / 新建了谁也都要说"
    assert "待人工 ${pend.length} 条" in SHELL, "待人工条数要露出来"
    assert "去项目档案指认到哪一行" in SHELL and 'data-k="m01"' in SHELL, "要给直达入口"
    assert "rc.unresolved_items" in SHELL


# --------------------------------------------------------------- 端点契约


@acc()
def test_trails端点存在且limit有边界():
    """`GET /api/m01/trails`：存在、且 `limit` 有下上界（越界由 FastAPI 直接 422，不连库）。"""
    from fastapi.testclient import TestClient

    from app.main import create_app
    from app.mod01_projects.router import router as mod01_router

    routes = {(r.path, tuple(sorted(r.methods))) for r in mod01_router.routes}
    assert ("/api/m01/trails", ("GET",)) in routes

    client = TestClient(create_app(), raise_server_exceptions=False)
    assert client.get("/api/m01/trails?limit=0").status_code == 422
    assert client.get("/api/m01/trails?limit=999").status_code == 422
