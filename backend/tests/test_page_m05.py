"""`MOD-05` **页面与组装层**的工程自检（离线 · 不连库）。

⚠️ 本文件**不绑定 `ACC-*` 判据点**（`@acc()` 显式声明）—— `ACC-FLOW-{LIST,PST,DEBT,LED}-001` 的判据
在 `test_acc_flow_*.py` 里已由**纯函数**钉住；本文件守的是**页面装配**这层：
五段骨架 / 台账两侧共用同一选择器 / 机械侧无手填入口 / 期初行在首行且空月不跳 / 统计页左右栏 /
流水页默认当月与撤销入口只在生效行。
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app
from app.mod03_notice.page import LIST_PAGE_SEGMENTS, segment_sequence, tip_block_count
from app.mod05_flow.router import (
    get_debt_data,
    get_flows_data,
    get_ledger_data,
    get_stats_data,
)
from app.mod05_flow.service import build_debt, build_flows, build_ledger, build_stats
from app.mod05_flow.view import FLOW_COLUMNS
from tests.acc_plugin import acc
from tests.m05_helpers import FakeSession, dataset

PROJECT_ID = 11


def _client() -> TestClient:
    app = create_app()

    def _flows(**kw):
        return build_flows(FakeSession(dataset()), **kw)

    def _debt(**kw):
        return build_debt(FakeSession(dataset()), **kw)

    def _ledger(**kw):
        return build_ledger(FakeSession(dataset()), **kw)

    def _stats(**kw):
        return build_stats(FakeSession(dataset()), **kw)

    app.dependency_overrides[get_flows_data] = lambda: _flows
    app.dependency_overrides[get_debt_data] = lambda: _debt
    app.dependency_overrides[get_ledger_data] = lambda: _ledger
    app.dependency_overrides[get_stats_data] = lambda: _stats
    return TestClient(app)


@acc()
def test_四个页面都是五段骨架且口径说明恒一块():
    c = _client()
    for path in ("/m05", "/m05/debt", "/m05/ledger", "/m05/stats"):
        r = c.get(path, params={"project_id": PROJECT_ID})
        assert r.status_code == 200, path
        html = r.text
        assert segment_sequence(html)[:4] == list(LIST_PAGE_SEGMENTS[:4]), path
        assert tip_block_count(html) == 1, path


@acc()
def test_台账两侧共用同一个项目选择器且无切换口径按钮():
    html = _client().get("/m05/ledger", params={"project_id": PROJECT_ID}).text
    # 「选择器」只认 `<select>`（每行表单里的 hidden `project_id` 不算）
    assert html.count('<select name="project_id"') == 1
    assert html.count('name="project_id"') > 1            # 行内表单要带回当前项目
    # 没有"切换口径"**按钮**（口径本身在域内核就是 False；文案里提到"无此按钮"不算）
    assert ">切换口径<" not in html
    assert "两侧共用" in html


@acc()
def test_台账机械侧没有手填入口_辅材侧有():
    html = _client().get("/m05/ledger", params={"project_id": PROJECT_ID}).text
    # 手填输入框只在**辅材**侧出现一次（机械侧「其他支出金额」是派生只读）
    assert html.count('name="settle_amount"') == 1
    assert html.count('name="paid_amount"') == 1
    assert "派生只读，无手填入口" in html


@acc()
def test_台账首行是期初且空月也出行():
    html = _client().get("/m05/ledger", params={"project_id": PROJECT_ID}).text
    assert "期初" in html and "2026-06" in html            # 期初行 = 截止年月
    assert ">2026-07<" in html and ">2026-09<" in html    # 有数据的月
    assert ">2026-08<" in html                            # **空月也出行**（连续，不跳月）


@acc()
def test_流水页默认当月且撤销入口只在生效行():
    html = _client().get("/m05").text
    assert "F301" in html and "F302" in html              # 9 月两条都在
    assert html.count('action="/m05/revoke"') == 1        # **只有生效行**给撤销表单
    assert "已撤销" in html
    assert FLOW_COLUMNS[-1]["key"] == "op"


@acc()
def test_统计页左右栏都在且默认按周():
    data = build_stats(FakeSession(dataset()))
    assert data["granularity"] == "week"                  # 默认**按周**
    assert data["layout"] == {"left": "by_project", "right": "timeline"}
    assert data["buckets"] and data["left"] and data["right"]
    html = _client().get("/m05/stats").text
    assert "合计（时间轴）" in html and "Σ 统计付款金额" in html


@acc()
def test_流水列表不分页且空态跨列数由表头派生():
    data = build_flows(FakeSession({}), year_month="", status=None)   # ""=全部月份（约定）
    assert data["paginated"] is False
    html = _client().get("/m05", params={"year_month": "2020-01"}).text   # 该月无数据 ⇒ 空态
    assert f'colspan="{len(FLOW_COLUMNS)}"' in html        # 空态跨列 = 表头列数（不写死）
    assert "当前筛选没有付款流水" in html


@acc()
def test_欠款页把三类与按项目都渲染出来():
    html = _client().get("/m05/debt").text
    for label in ("辅材", "机械", "集采"):
        assert f"{label}欠款" in html
    assert "欠款合计" in html
    assert "未判定" in html                                # 无归属的行**单列**、不并入任何小微
