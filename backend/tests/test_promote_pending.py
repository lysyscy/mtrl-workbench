"""`TAIL-30`-③ · **「待人工指认」清单**（链路 B 里唯一必须人来做的那一类）—— 离线断言。

规则主人：计划 **§17**（用户 2026-09-18 逐条确认的语义）· 《说明书》**§2.4.2** 链路 B ·
《全自动建档-实施计划》**§1.2 安全绳**、**决策 1/2**。

⚠️ 本文件测**清单层**（`mod01_projects.pending`）＋ 端点契约；「指认真的落库了」由真机
   `tools/probe/_e2e_m01_promote.py` 覆盖（离线断言证不了运行时）。
⚠️ **判据点**：`ACC-PRJ-AUTO-001` 的加点属**扩范围** ⇒ 本文件一律 `@acc()` **显式不绑定**。
"""

from __future__ import annotations

from app.mod01_projects import pending as PE
from app.mod01_projects import recovery as R
from app.mod01_projects.models import (
    STATUS_ARCHIVED,
    TYPE_NORMAL,
    TYPE_SHELL,
    Project,
)
from app.mod02_i8.models import RunRecord
from tests.m09_helpers import M09Session

FULL = "第四工程公司2026年小微项目(TBLX2026070003)"
FULL_B = "甲项目(XMCB2025080001)"
WH = "兰考金不换前置车间项目"


def p(pid, full, wh, *, ptype=TYPE_NORMAL, disp=None, status="active", order=0):
    return Project(id=pid, project_type=ptype, name_full=full, warehouse_name=wh,
                   disp=disp if disp is not None else (wh or ""), status=status, ord=order)


def rec(rid, target, items, *, run_type="fetch", at="2026-09-18 10:00:00"):
    from datetime import datetime

    return RunRecord(id=rid, run_type=run_type, target=target, status="success",
                     detail=PE.record_detail(items),
                     started_at=datetime.strptime(at, "%Y-%m-%d %H:%M:%S"))


def item(wh=WH, full=FULL, kind=R.KIND_MULTI):
    return {"kind": kind, "warehouse_name": wh, "owner_full_name": full, "reason": "（测试用）"}


def session(*, projects, records):
    return M09Session({Project: list(projects), RunRecord: list(records)})


# ============================================================ ① 判定口径（唯一出口）


def test_命中处置的类别由唯一出口判定():
    """⭐ `classify_hits` = **判定口径的唯一出口**（`plan_recovery` 与「待指认」清单都吃它）。

    ⚠️ 顺序即优先级：**先判壳** —— 命中里有壳 ⇒ 这条仓库是具体小微（走新建），
       哪怕同时还有 2 条同名普通项目，**也不进"要人指认"分支**（§17.2）。
    """
    assert R.classify_hits([]) == R.KIND_NOT_ARCHIVED
    assert R.classify_hits([p(1, FULL, "未建仓-01")]) == R.KIND_PROMOTE
    assert R.classify_hits([p(1, FULL, "甲仓")]) == R.KIND_REAL_WAREHOUSE
    assert R.classify_hits([p(1, FULL, "未建仓-01"), p(2, FULL, "未建仓-02")]) == R.KIND_MULTI
    # 壳优先于「≥2 条」：有壳 ⇒ 新建小微（不进指认）
    assert R.classify_hits([p(1, FULL, None, ptype=TYPE_SHELL),
                            p(2, FULL, "未建仓-01")]) == R.KIND_CREATE_SMALL


def test_归一化后精确相等才算命中():
    """§17.2：**归一化全名精确相等** —— ⛔ 不包含、不模糊、无兜底（「宁报出来给人看，不猜」）。"""
    proj = [p(1, FULL, "未建仓-01")]
    by = R.rows_by_full(proj)
    assert R.hits_of_full(by, FULL) == proj, "全名相等 ⇒ 命中"
    assert R.hits_of_full(by, FULL.replace("(TBLX2026070003)", "")) == proj, \
        "剥掉尾部项目代码后相等 ⇒ 也算命中（走同一归一出入口）"
    assert R.hits_of_full(by, FULL + "二期") == [], "包含 / 相似 **不算**命中（⛔ 不猜）"
    assert R.hits_of_full(by, FULL[2:]) == []


def test_每条unresolved都带kind不靠中文原因串认类别():
    """⛔ **不许用中文 `reason` 串判类别**：文案一改，"挑出要人指认的那一类"就会**静默失效**。"""
    plan = R.plan_recovery(
        unknown_wh=["甲仓2"],
        warehouse_rows=[{"warehouse_name": "甲仓2", "owner_full_name": FULL}],
        projects=[p(1, FULL, "未建仓-01"), p(2, FULL, "未建仓-02")],
    )
    it = plan["unresolved"][0]
    assert it["kind"] == R.KIND_MULTI, f"条目必须带 kind（实得 {it!r}）"
    assert "疑似" in it["reason"], "人读的原因照旧要给（kind 不替代 reason）"


# ============================================================ ② 清单从哪来、只认最近一次


def test_两条材料侧链路的登记键都要被认出来():
    """⭐ 防漂：`MATERIAL_TARGETS` 认的是各自 `fetch_service.SPEC_KEY` —— 它一旦改名，
    「最近一次材料侧抓取」就会**静默认不出来**（清单恒空，页面看着像"本来就没有待办"）。
    """
    from app.mod07_setl.fetch_service import SPEC_KEY as K7
    from app.mod08_inv.fetch_service import SPEC_KEY as K8

    assert {K7, K8} <= set(PE.MATERIAL_TARGETS), \
        f"两条链路的 SPEC_KEY（{K7}/{K8}）都要在 MATERIAL_TARGETS={PE.MATERIAL_TARGETS} 里"
    assert PE.is_material_target(f"{K7} 2026-08（14 个项目）")
    assert PE.is_material_target(f"{K8} 2026-08（14 个项目）")
    assert not PE.is_material_target("nt 2026-09（0 个项目）"), "付款侧不算材料侧"
    assert not PE.is_material_target("setlx 2026-08（1 个项目）"), "前缀必须**整词**（防子串误认）"
    assert not PE.is_material_target("")


def test_待指认清单只认最近一次材料侧抓取():
    """⭐ **只认最近一次**（与 `latest_unresolved` 同款口径）：

    - 更早那条记录里还有待人工 ⇒ **不再拿出来**（否则就是让用户对着**已经解决**的清单白干，`TAIL-41` 同族）；
    - 付款侧 / 同步记录 ⇒ **跳过**（材料域的清单不能由别的域凑出来）；
    - 一条材料侧记录都没有 ⇒ `found=False` ＋ 空清单（**不拿别的记录凑**）。
    """
    old = rec(1, "setl 2026-08（14 个项目）", [item()])
    pay = rec(2, "nt 2026-09（0 个项目）", [item(wh="付款侧的")])
    sync = rec(3, "仓库列表", [item(wh="同步的")], run_type="sync")
    new = rec(4, "setl 2026-09（14 个项目）", [], at="2026-09-18 11:00:00")

    got = PE.latest_pending(session(projects=[], records=[new, pay, sync, old]))
    assert got["found"] is True and got["items"] == [], "最近一次说没有待人工 ⇒ 就是没有（⛔ 不回溯）"
    assert got["run_record_id"] == 4 and "setl 2026-09" in got["target"], "来源要如实报出"
    assert got["at"] == "2026-09-18 11:00:00"

    got2 = PE.latest_pending(session(projects=[], records=[pay, sync]))
    assert got2 == {"found": False, "items": [], "target": "", "at": "", "run_record_id": None}, \
        "没有材料侧记录 ⇒ 明确 found=False（⛔ 不猜别的记录）"

    # ⚠️ 再喂一遍**反序**（老记录在前）：「最新」必须**按 id 判**，⛔ 不许信传入顺序 ——
    #    离线桩不处理 `order_by`，不显式排序的实现会在这里把**旧清单**当成最新的。
    got3 = PE.latest_pending(session(projects=[], records=[old, new]))
    assert got3["run_record_id"] == 4 and got3["items"] == [], "不许信记录传入顺序（按 id 取最新）"


def test_清单条目是两个链路共用一份不会各写一份():
    """收发结存（`setl`）与库存单据（`inv`）**共用同一个键与同一份读法** —— 写侧唯一出口。"""
    d = PE.record_detail([item()])
    assert list(d) == [PE.RECORD_KEY], "写侧只许写这一个键"
    assert PE.record_detail() == {PE.RECORD_KEY: []}, "没待人工也要写**空**（否则『最近一次』指不住）"
    d["x"] = 1
    assert "x" not in PE.record_detail(), "写侧不许留后门"
    from app.mod07_setl.fetch_service import record_detail as d7
    from app.mod08_inv.fetch_service import record_detail as d8

    assert d7 is PE.record_detail is d8, "两条链路必须是**同一个**写侧出口（⛔ 别各写一份）"


# ============================================================ ③ 读出来必须按当前档案现算


def test_清单逐条按当前档案现算已解决的当场丢掉():
    """清单是**线索**，真相是**档案现在的样子**（`pending` 口径 2）——

    一条条目**仍然成立**要同时满足：① 那个仓库名**仍然陌生**；② 全名**仍然**命中 ≥2 条非壳行。
    两条各自都足以让条目消失（都对应"下次抓取不会再报它"）。
    """
    s = session(projects=[p(1, FULL, "未建仓-01"), p(2, FULL, "未建仓-02")],
                records=[rec(1, "setl 2026-08（14 个项目）", [item()])])
    # ⚠️ 桩持有的是**构造时的副本** ⇒ 增 / 删行必须动它自己那一份（改对象的字段则两处同时变）
    projs = s.by_model[Project]
    items = PE.live_items(s)
    assert len(items) == 1 and items[0]["kind"] == R.KIND_MULTI
    assert [c["id"] for c in items[0]["candidates"]] == [1, 2], "条目要带上**现在的**候选行"
    assert all(c["is_placeholder"] for c in items[0]["candidates"])

    # ① 有人把第 2 行**扶正成了这条陌生仓库**（= 条目里的仓库名）⇒ 仓库不再陌生 ⇒ 清单该空
    projs[1].warehouse_name = WH
    assert PE.live_items(s) == [], "仓库已在档案里 ⇒ 下次抓取不会再报它（⛔ 不摆着让人白干）"

    # ② 另一种「已解决」：仓库**仍陌生**，但只剩 1 条非壳行（其余行删了 / 改了全名）
    #    ⇒ 下次抓取走「1 条占位行 ⇒ 系统自动扶正」，不用人来
    projs.pop(1)
    assert PE.live_items(s) == [], "只剩 1 条 ⇒ 系统会自动扶正，不再是「要人指认」那个情形"

    # ③ 又冒出第 3 条同名行（仓库仍陌生）⇒ 重新成为待指认
    projs.append(p(3, FULL, "未建仓-03"))
    assert len(PE.live_items(s)) == 1


def test_清单里没有全名的条目直接丢掉():
    """仓库名单里查不到全名那一类（`no_owner`）**没有全名** ⇒ 本入口处理不了它（它要人去核对名单）。"""
    s = session(projects=[p(1, FULL, "未建仓-01"), p(2, FULL, "未建仓-02")],
                records=[rec(1, "setl 2026-08（14 个项目）",
                             [{"kind": R.KIND_NO_OWNER, "warehouse_name": "某仓", "reason": "…"}])])
    assert PE.live_items(s) == []
    out = PE.live_pending(s)
    assert out["found"] is True and out["dropped"] == 1, "丢了几条要如实报出（⛔ 不静默）"


# ============================================================ ④ 候选清单（端点①的数据源）


def test_候选清单只含该全名且含归档行并标出占位():
    """§17.2 / §17.4：**只查本地档案表（含归档行）**；字段单 = id / 类型 / 仓库名 / 展示名 / 状态 / phid。"""
    rows = PE.candidates(
        session(projects=[
            p(1, FULL, "未建仓-01", status=STATUS_ARCHIVED, order=9),
            p(2, FULL, "未建仓-02"),
            p(3, FULL + "（二期）", "别仓"),
        ], records=[]),
        FULL,
    )
    assert [r["id"] for r in rows] == [2, 1], "归档行**也在内**（排最后 —— 全站同一套 `ordered`）"
    assert all(r["type_label"] == "普通项目" for r in rows)
    assert [r["is_placeholder"] for r in rows] == [True, True], "哪几行是占位行要标出来"
    assert rows[0]["warehouse_name"] == "未建仓-02" and rows[0]["disp"] == "未建仓-02"
    assert rows[0]["status"] == "active" and "phid" in rows[0]


def test_候选清单与判定吃同一份索引():
    """⭐ 防"系统说命中 2 条、弹窗里只列出 1 条"：两处必须**同一份索引**（`rows_by_full`）。"""
    proj = [p(1, FULL, "未建仓-01"), p(2, FULL, "未建仓-02")]
    by = R.rows_by_full(proj)
    assert len(R.hits_of_full(by, FULL)) == len(PE.candidates(session(projects=proj, records=[]), FULL))


# ============================================================ ⑤ 端点契约


def test_三个端点都在且写入口按id定位():
    """`TAIL-30`-③ 的三条端点（清单 / 候选行 / 指定扶正）—— **写**必须收 `project_id`（铁律 5/6）。"""
    from app.mod01_projects.router import router as mod01_router
    from app.mod01_projects.schemas import PromoteRequest

    routes = {(r.path, tuple(sorted(r.methods))) for r in mod01_router.routes}
    assert ("/api/m01/promote-pending", ("GET",)) in routes
    assert ("/api/m01/promote-candidates", ("GET",)) in routes
    assert ("/api/m01/promote", ("POST",)) in routes
    assert "project_id" in PromoteRequest.model_fields, "写入口必须按 id 定位（⛔ 不用名字反查）"


def test_写入口缺参数直接422不进业务():
    """`project_id` 缺失 ⇒ FastAPI 直接 422（**不连库、不落到"猜一个行"**）。"""
    from tests._auth import TestClient          # ⭐ 带会话票（见该件注释）

    from app.main import create_app

    client = TestClient(create_app(), raise_server_exceptions=False)
    assert client.post("/api/m01/promote", json={"warehouse_name": "甲仓"}).status_code == 422


def test_写入口有一致性守卫且落库只走系统扶正出口():
    """⚠️ 端点层要真库才跑得起来 ⇒ **行为**由真机 `tools/probe/_e2e_m01_promote.py` 覆盖（含"跨全名指认被拒"）。

    这里**钉住守卫本身**（静态）：它一旦被删 / 被绕过，
    "把 A 全名的仓库名写到 B 全名的行上"就会**静默放行**（`真实仓库名` 挂错行 = 钱记到别人头上）。
    """
    import inspect

    from app.mod01_projects.router import promote

    src = inspect.getsource(promote)
    assert "norm_full_name(row.name_full) != norm_full_name(want_full)" in src, \
        "守卫（所选行的全名必须与本次指认的全名一致）被删了"
    assert "promote_placeholder" in src, "落库必须走**系统扶正出口**（判据与它同一份）"
    assert "row.warehouse_name =" not in src, \
        "⛔ 端点自己赋值 = 绕过 §2.3.1（只有占位行才能被扶正）"
