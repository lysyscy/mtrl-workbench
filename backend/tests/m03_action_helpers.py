"""`MOD-03` **动作 / 列表 API** 验收断言的公共桩（**离线：不连库**）。

拆因：`test_notice_actions.py` 涨到 527 行（贴近 `T5` 硬上限）⇒ 桩件抽到本文件，
测试按「域内核 / 端点」两件（**断言一字未改，只搬位置**）：

- `test_notice_actions.py`    —— 域内核纯函数（批量改分类 / 剔除恢复 / 手动行载荷）
- `test_notice_action_api.py` —— 端点（`/api/m03/*` 动作与列表查询）

⭐ 2026-09-19（`§19` 批 4 · **S4⑤**）：旧页删净（授权 `D18`）⇒ 原来的**页面渲染桩**
（`_render` / `_rows` / `_row_of` / `_cell_of` / `_render_with_traces`，都靠抠 HTML 观测）
**随页删除** —— 它们守的形态判据已由 `test_wired_m03_*.py` 在**新壳侧**承载 ✓。
本件此后只留**离线会话与取数桩**（假会话 / 造行 / 带注入的 client）。

`FakeWriteSession` 在 `m04_helpers.FakeSession` 上加**写**能力，让 `repository` 的真实代码跑起来，
只是数据来自内存。
"""

from __future__ import annotations

from decimal import Decimal

from tests._auth import TestClient          # ⭐ 带会话票（见该件注释）

from app.main import create_app
from app.mod01_projects.models import Project
from app.mod03_notice.models import PaymentNotice
from app.mod03_notice.notice_api_router import get_session
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


__all__ = ["FakeWriteSession", "_notice", "_client"]
