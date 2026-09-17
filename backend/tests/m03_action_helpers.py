"""`MOD-03` **行级动作 / 操作列 / 统计手改**验收断言的公共桩（**离线：不连库**）。

拆因：`test_notice_actions.py` 涨到 527 行（贴近 `T5` 硬上限）⇒ 桩件抽到本文件，
测试按「域内核 / 渲染面 / 端点」拆成三件（**断言一字未改，只搬位置**）：

- `test_notice_actions.py`       —— 域内核纯函数（批量改分类 / 剔除恢复 / 手动行载荷）
- `test_notice_action_page.py`   —— 页面渲染（操作列 / 草稿行 / 查看关联页 / 统计可改格）
- `test_notice_action_api.py`    —— 端点（`/api/*` 与 PRG 动作路由）

`FakeWriteSession` 在 `m04_helpers.FakeSession` 上加**写**能力，让 `repository` 的真实代码跑起来，
只是数据来自内存。
"""

from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient

from app.main import create_app
from app.mod01_projects.models import Project
from app.mod03_notice.models import PaymentNotice
from app.mod03_notice.notice_page import build_page_data, render_notice_page
from app.mod03_notice.notice_router import get_session
from app.mod05_flow.models import PaymentFlow
from tests.m04_helpers import FakeSession


class FakeWriteSession(FakeSession):
    """在 `FakeSession` 上加**写**能力（add / delete / flush）—— 动作端点的离线桩。"""

    def __init__(self, by_model: dict) -> None:
        super().__init__(by_model)
        self.added: list = []
        self.deleted: list = []

    def add(self, row) -> None:  # noqa: ANN001
        self.added.append(row)
        self.by_model.setdefault(type(row), []).append(row)

    def delete(self, row) -> None:  # noqa: ANN001
        self.deleted.append(row)
        rows = self.by_model.get(type(row), [])
        if row in rows:
            rows.remove(row)

    def flush(self) -> None:
        return None

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None


def _notice(nid: int, **kw) -> PaymentNotice:
    vals = dict(
        id=nid, ph_id=f"P{nid}", bill_no=f"B{nid}", bill_type="material",
        doc_date="2026-09-05", category="material", biz_type="付其他供应商款",
        payee="某供应商", input_by="王潜森", amount_approved=Decimal("10000.00"),
        stat_settle=Decimal("10000.00"),
        stat_paid=Decimal("10000.00"), approve_status="已批",
        excluded=False, exclude_source="", i8_revoked=False, is_manual=False,
        ownership_id=11, project_name="甲项目", fields={"BillName": "材料款结算单"},
    )
    vals.update(kw)
    return PaymentNotice(**vals)


def _client(notices, projects=(), flows=()) -> tuple[TestClient, FakeWriteSession]:
    app = create_app()
    fake = FakeWriteSession(
        {PaymentNotice: list(notices), Project: list(projects), PaymentFlow: list(flows)}
    )
    app.dependency_overrides[get_session] = lambda: fake
    return TestClient(app), fake


def _cell_of(html: str, label: str) -> str:
    """从渲染页里取出**某一格**的值 —— `<b>标签</b><span>值</span>` 结构。

    ⚠️ **只读页的断言必须按格取值，不能用整页 `in`** —— 同页「统计付款金额」与「已付金额」
       数值不同、但字符串会互相喂饱整页断言（实测：把已付金额改成"全部流水汇总"后
       `"3000.00" in html` 仍然通过，因为另一个字段印了 3000）。
    """
    import re

    m = re.search(
        r"<b>\s*" + re.escape(label) + r"\s*</b>\s*<span>([^<]*)</span>", html
    )
    assert m is not None, f"页面上找不到格子「{label}」"
    return m.group(1).strip()


def _render(notices, flows=None, *, draft=None):
    session = FakeWriteSession({PaymentNotice: list(notices), Project: [], PaymentFlow: []})
    flows_map = flows or {}
    data = build_page_data(
        session, sort_col="", sort_dir=0, draft=draft,
        flows_of=lambda nid: flows_map.get(nid, []),
    )
    return render_notice_page(data)


def _rows(html: str) -> list[str]:
    """取数据区里的每一行 `<tr>`（用于按行断言「操作」列，而不是拿整页去撞关键词）。"""
    import re

    body = re.search(r"<tbody\b[^>]*>([\s\S]*?)</tbody>", html)
    return re.findall(r"<tr\b[^>]*>[\s\S]*?</tr>", body.group(1) if body else "")


def _row_of(html: str, bill_no: str) -> str:
    return next(r for r in _rows(html) if f">{bill_no}<" in r)


def _render_with_traces(notices, traces=None):
    session = FakeWriteSession({PaymentNotice: list(notices), Project: [], PaymentFlow: []})
    idx = traces or {}
    data = build_page_data(
        session, sort_col="", sort_dir=0,
        flows_of=lambda nid: [], traces_of=lambda nid: idx.get(nid, []),
    )
    return render_notice_page(data)
