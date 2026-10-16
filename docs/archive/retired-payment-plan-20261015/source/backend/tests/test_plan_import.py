"""付款计划**导入**（§4.3.3 数据入口 · §9.5 幂等）的工程自检（离线 · 不连库）。

⚠️ `@acc()` **显式不绑定判据点**（`ACC-PLAN-IMPORT-001` 的 7 条判据已由 `domain` 的纯函数钉住）；
   本文件守的是**导入这层**：表头识别 · 无效列原样入库 · 项目匹配 · **幂等重写**（不产生重复行 / 减行不留残影）·
   **可手改列不被覆盖** · 手动行不被触碰 · **同月同号照收不拦**（那是审查的「重复上报」）。
"""

from __future__ import annotations

import io
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.core.errors import MustReportError
from app.main import create_app
from app.mod01_projects.models import Project
from app.mod04_plan import repository as repo
from app.mod04_plan.domain import (
    MATCH_AMBIGUOUS,
    MATCH_MATCHED,
    MATCH_UNMATCHED,
    ProjectBrief,
    match_project,
)
from app.mod04_plan.importer import attach_projects, match_summary, parse_workbook
from app.mod04_plan.models import PlanRow
from app.mod04_plan.router import get_db
from tests.acc_plugin import acc
from tests.m04_helpers import FakeSession
from tests.m03_action_helpers import FakeWriteSession

HEADER = (
    "项目", "材料：其他支出付资产处/贸易公司（编号）", "外租机械：付款通知书（编号）",
    "该流程金额", "本月预付款金额", "付款时间", "付款方式", "备注",
    "科目", "费用日期", "收款单位", "已付款金额", "剩余付款金额",
)


def _xlsx(rows: list[tuple]) -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(HEADER)
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _row(project="甲仓库", material="D1", mech="", flow=1000, planned=800,
         pay_date="2026-09-15", method="现汇", remark="", subject="辅材费", payee="某公司"):
    return (project, material, mech, flow, planned, pay_date, method, remark,
            subject, "2026-09-01", payee, 0, 0)


def _plan_row(row_id: int, **kw) -> PlanRow:
    vals = dict(
        id=row_id, year_month="2026-09", project_input="甲仓库", project_id=11,
        match_status=MATCH_MATCHED, match_candidates=1, doc_no="D1",
        flow_amount=Decimal("1000.00"), planned_amount=Decimal("800.00"),
        pay_date="", pay_method="现汇", remark="", forced_through=False,
        forced_remark="", is_manual=False, raw={},
    )
    vals.update(kw)
    return PlanRow(**vals)


# ============================================================ 解析（§4.3.3）


@acc()
def test_表头识别与有效列抽取():
    parsed = parse_workbook(_xlsx([_row()]))
    assert parsed.header_row == 1
    assert parsed.columns["project_input"] == "项目"
    r = parsed.rows[0]
    assert r["project_input"] == "甲仓库" and r["doc_no"] == "D1"
    assert r["flow_amount"] == Decimal("1000.00") and r["planned_amount"] == Decimal("800.00")
    assert r["pay_date"] == "2026-09-15" and r["pay_method"] == "现汇"


@acc()
def test_无效列原样入库不参与审查():
    """§4.3.3：科目 / 费用日期 / 收款单位 / 已付款金额 / 剩余付款金额 —— **原样入库、不要求修正**。"""
    r = parse_workbook(_xlsx([_row(subject="辅材费", payee="某公司")])).rows[0]
    assert r["raw"]["科目"] == "辅材费"
    assert r["raw"]["收款单位"] == "某公司"
    assert r["raw"]["_row_no"] == 2
    # 无效列**不出现在**有效字段里
    assert "subject" not in r and "payee" not in r


@acc()
def test_表头认不出就显式报错():
    from openpyxl import Workbook

    wb = Workbook()
    wb.active.append(("序号", "名称", "金额"))
    buf = io.BytesIO()
    wb.save(buf)
    with pytest.raises(MustReportError) as err:
        parse_workbook(buf.getvalue())
    assert "没认出付款计划的表头" in err.value.message


@acc()
def test_单据号是一个字段_两列都有值时取第一个并提示():
    """⭐ 2026-09-27（`TAIL-129` · 用户裁定「**实际上单据号不分机械和材料**」）：
    那一列就是**一个字段**（`doc_no`）—— 原先拆成"材料单据 / 机械单据"再按编号形态猜类别，
    已随本裁定删除。文件里若真有两列都写着编号 ⇒ **取第一个非空的**并**提示**（只提示、不拦截）。
    """
    parsed = parse_workbook(_xlsx([_row(material="D1", mech="D2")]))
    assert parsed.rows[0]["doc_no"] == "D1"
    assert any("单据号在两列里都有值" in a for a in parsed.alerts)      # 只提示、不拦截
    assert not any("_material_doc" in k or "_mechanical_doc" in k
                   for k in parsed.rows[0]["raw"]), "⛔ 那两个「材料/机械」痕迹字段已随口径删除"


# ============================================================ 项目列匹配（§4.3.3）


@acc()
def test_项目按展示名或仓库名唯一匹配():
    briefs = [
        ProjectBrief(id=11, disp="甲仓库", warehouse_name="甲仓库"),
        ProjectBrief(id=12, disp="乙小微", warehouse_name="乙仓库"),
    ]
    rows = attach_projects(
        [{"project_input": "甲仓库"}, {"project_input": "乙仓库"}, {"project_input": "查无此项"}],
        briefs,
    )
    assert [r["match_status"] for r in rows] == [MATCH_MATCHED, MATCH_MATCHED, MATCH_UNMATCHED]
    assert rows[0]["project_id"] == 11 and rows[1]["project_id"] == 12


@acc()
def test_项目重名标重名N条且不猜():
    briefs = [
        ProjectBrief(id=11, disp="重名", warehouse_name="仓库A"),
        ProjectBrief(id=12, disp="重名", warehouse_name="仓库B"),
    ]
    rows = attach_projects([{"project_input": "重名"}], briefs)
    assert rows[0]["match_status"] == MATCH_AMBIGUOUS
    assert rows[0]["match_candidates"] == 2
    assert rows[0]["project_id"] is None                        # **不猜**


@acc()
def test_重名行给的是候选清单而不是个数():
    """⭐⭐ 2026-09-27 **真机抓出来的既有缺陷**：`match_summary` 把「个数（int）」当成清单去 `list()`
    ⇒ 真有重名行时 `TypeError: 'int' object is not iterable`（此前一直没有重名行去碰它）。

    ⇒ 契约：`match_candidates` = **个数** · `_candidate_labels` = **清单**（界面要能列出
      "对上了哪几条"，⛔ 只给个数字等于让人自己猜）。⚠️ 清单键**必须 `_` 开头**：旁路键由
      `repo.merge_month` 按前缀挡在表字段之外（新键不带 `_` 会当场漏进 `PlanRow(**payload)`）。
    """
    briefs = [ProjectBrief(id=11, disp="重名", warehouse_name="仓库A"),
              ProjectBrief(id=12, disp="重名", warehouse_name="仓库B")]
    rows = attach_projects([{"project_input": "重名", "_row_no": 3}], briefs)
    assert rows[0]["match_candidates"] == 2                      # 个数
    assert rows[0]["_candidate_labels"] == ["重名", "重名"]         # 清单
    got = match_summary(rows)
    assert got["multi"][0]["candidates"] == ["重名", "重名"], "⛔ 不许是 int（那是老缺陷的形态）"
    assert got["multi"][0]["row"] == 3


@acc()
def test_短输入不许靠包含匹配撞上项目():
    """⚠️ 2026-09-27 真机：夹具里项目列写成 `0` ⇒ 被"包含"撞上 `未建仓03` / `未建仓04`（**假歧义**）。
    ⇒ 第③步要求**两侧都 ≥ 3 个字**；实测真收益的两例（`晋江污泥` / `大唐雷州`）都是 4 字，不损失。
    """
    briefs = [ProjectBrief(id=1, disp="", warehouse_name="未建仓-03"),
              ProjectBrief(id=2, disp="", warehouse_name="未建仓-04"),
              ProjectBrief(id=3, disp="大唐雷州发电项目", warehouse_name="大唐雷州发电项目")]
    assert match_project("0", briefs).status == MATCH_UNMATCHED          # 太短 ⇒ 不猜
    got = match_project("大唐雷州", briefs)
    assert got.status == MATCH_MATCHED and got.project_id == 3           # 够长 ⇒ 命中
    assert got.how == "包含", "命中方式要记下来（界面要能回答「为什么它配上了」）"


# ============================================================ 幂等重写（§9.5）


def _merge(existing, rows, *, ym="2026-09"):
    s = FakeWriteSession({PlanRow: list(existing), Project: []})
    result = repo.merge_month(s, year_month=ym, rows=attach_projects(rows, []))
    return s, result


@acc()
def test_重复导入不产生重复行():
    s, r1 = _merge([], [{"project_input": "甲", "doc_no": "D1", "flow_amount": Decimal("1000.00"),
                         "planned_amount": Decimal("800.00"), "pay_date": "", "pay_method": "现汇",
                         "remark": "", "raw": {}, "project_id": None, "match_status": "matched",
                         "match_candidates": 1}])
    assert r1["created"] == 1 and r1["updated"] == 0
    again = list(s.by_model[PlanRow])
    s2, r2 = _merge(again, [{"project_input": "甲", "doc_no": "D1", "flow_amount": Decimal("1000.00"),
                             "planned_amount": Decimal("900.00"), "pay_date": "", "pay_method": "现汇",
                             "remark": "", "raw": {}, "project_id": None, "match_status": "matched",
                             "match_candidates": 1}])
    assert r2["created"] == 0 and r2["updated"] == 1            # **复用同一行**
    assert len(s2.by_model[PlanRow]) == 1                        # 不产生重复行


@acc()
def test_减行不留残影():
    existing = [_plan_row(1, doc_no="D1"), _plan_row(2, doc_no="D2")]
    s, r = _merge(existing, [{"project_input": "甲", "doc_no": "D1", "flow_amount": Decimal("1000.00"),
                              "planned_amount": Decimal("800.00"), "pay_date": "", "pay_method": "现汇",
                              "remark": "", "raw": {}, "project_id": None, "match_status": "matched",
                              "match_candidates": 1}])
    assert r["deleted"] == 1                                     # D2 那行被清掉
    assert [x.id for x in s.deleted] == [2]
    assert len(s.by_model[PlanRow]) == 1


@acc()
def test_可手改列不被导入覆盖():
    """§4.3.3：付款时间 / 付款方式 / 备注 落库、**不被导入覆盖**、不留痕。"""
    existing = [_plan_row(1, pay_method="承兑", pay_date="2026-09-01", remark="改过")]
    s, r = _merge(existing, [{"project_input": "甲", "doc_no": "D1", "flow_amount": Decimal("1000.00"),
                              "planned_amount": Decimal("800.00"), "pay_date": "2026-09-20",
                              "pay_method": "现汇", "remark": "导入值", "raw": {},
                              "project_id": None, "match_status": "matched", "match_candidates": 1}])
    row = s.by_model[PlanRow][0]
    assert (row.pay_method, row.pay_date, row.remark) == ("承兑", "2026-09-01", "改过")
    assert row.planned_amount == Decimal("800.00")               # 其余字段照常更新


@acc("ACC-PLAN-MANUAL-001", "001-04")
def test_手动行不被触碰():
    """§9.5：导入**只清理并重写自动行**，手动行原样保留。"""
    existing = [_plan_row(1, doc_no="M1", is_manual=True), _plan_row(2, doc_no="D1")]
    s, r = _merge(existing, [{"project_input": "甲", "doc_no": "D9", "flow_amount": Decimal("1.00"),
                              "planned_amount": Decimal("1.00"), "pay_date": "", "pay_method": "现汇",
                              "remark": "", "raw": {}, "project_id": None, "match_status": "matched",
                              "match_candidates": 1}])
    assert r["manual_kept"] == 1
    assert [x.doc_no for x in s.deleted] == ["D1"]                # 只删了自动行
    assert all(not x.is_manual for x in s.deleted)                # 手动行**没被删**
    assert any(getattr(x, "doc_no", "") == "M1" and x.is_manual for x in s.by_model[PlanRow])
    assert r["deleted"] == 1                                     # 只清了自动行 D1


@acc()
def test_同月同单据号照收不拦():
    """§4.3.4：同月同单据号两行 = **审查里的「重复上报」** ⇒ 导入照收、审查暴露、用户逐行删。"""
    row = {"project_input": "甲", "doc_no": "D1", "flow_amount": Decimal("1.00"),
           "planned_amount": Decimal("1.00"), "pay_date": "", "pay_method": "现汇",
           "remark": "", "raw": {}, "project_id": None, "match_status": "matched",
           "match_candidates": 1}
    s, r = _merge([], [dict(row), dict(row)])
    assert r["created"] == 2 and r["deleted"] == 0               # **不拦、不去重**


@acc()
def test_未选月份直接报错():
    with pytest.raises(MustReportError) as err:
        repo.merge_month(FakeWriteSession({PlanRow: []}), year_month="", rows=[])
    assert "必须先选「年月」" in err.value.message


# ============================================================ 路由 / 页面


def _client(rows=(), projects=()):
    app = create_app()
    fake = FakeWriteSession({PlanRow: list(rows), Project: list(projects)})
    app.dependency_overrides[get_db] = lambda: fake
    return TestClient(app), fake


# ⚠️ 2026-09-18（`TAIL-27` · `§19` **批 2**）：旧**导入页**（`GET /m04/import`）与其 PRG 端点
#    （`POST /m04/import`）已随旧渲染层删除（授权 `D18`）⇒ 原来钉在它们上的三条**搬了断言**：
#    · 「导入页给出先选月份与口径说明」= **纯页面形态** ⇒ 随页作废（那几句口径现在写在**壳**的导入弹窗里，
#      由 `tests/test_wired_m04.py::test_导入与手动行走后端` 的接线断言守）；
#    · 「导入成功回报四个数」与「月份缺失显式报错」= **产品 claim** ⇒ 改指新壳在用的端点。
#
# ⚠️⚠️ **2026-09-23（`TAIL-75` 余项 · 用户裁定「只留通用面」）：页内导入面整条连件删除** ——
#    `POST /api/m04/import`（一步式，2026-09-22 起**已软退役**，现**已删**。）＋ `/api/m04/import/parse|confirm`
#    （这两个**也已删**。）
#    （`TAIL-69` 的两步）＋ 只服务它们的 `TokenRequest` ⇒ 付款计划的导入**只剩通用面一条路**
#    （`/api/imp/m04_plan/*`，壳「数据导入」页选 `付款计划`）。
#    ⇒ 原先钉在这三个端点上的四条，**照本仓惯例「判词一字不改、只换落点」**：
#
#    | 原判据（本文件） | 现在的落点 |
#    |---|---|
#    | `test_两步导入_预览不写库_确认才落库` | `test_imp_m04_api.py::test_付款计划在通用面端到端_中文月日按年月补全_且幂等`（落库/幂等，同一份数值口径）；**"预览不写库"**这一半另由同件新增的 `test_通用面预览阶段不写库_且坏token显式报错` **直接查库**证明 |
#    | `test_两步导入_token不存在显式报错` | 同上那条新用例（坏 token ⇒ `ok:false` ＋ 中文原因）。⚠️ **形态变了**：通用面**恒 HTTP 200、成败看回包 `ok`**（全站写动作口径）⇒ 断言随之改形，claim 不变 |
#    | `test_两步导入_解析缺月份显式报错` | `test_imp_m04_api.py::test_缺年月要显式报错_不静默落库`。⚠️ **形态变了**：年月从 `parse` 的入参**移进** `commit` 的域上下文（`options.year_month`）⇒ "缺月份不静默落库"这条 claim 不变 |
#    | `test_一步式入口退役回执` | **随入口作废**（它守的是"留给缓存旧页面的一句明白话"—— 端点已删，没有可打的旧页面了） |
#
#    ⛔ 那个离线 client（`_api_client`：monkeypatch `plan_api_router.session_scope`）**同批删除** ——
#       它只服务上面这四条；通用面有**自己的真库用例**（`test_imp_m04_api.py`，含"预览不写库"的查库证明）。
