"""M1 切片 1 验收测试的公共桩（离线：不连库 / 不启浏览器 / 不碰打印机）。

⚠️ 渲染链路自 2026-09-15 起为**模板驱动**（`print/template.py`）：
   版式桩返回的是**模板对象**（`PaymentNoticeDesign.tpl`），**不再是 HTML**；
   数据来源是三个详情接口（`FakeDetailFetcher`），签名图来自 `FakeSignatureStore`。
"""

from __future__ import annotations

from app.core.errors import MustReportError
from app.mod03_notice.models import PaymentNotice
from app.mod03_notice.print.design import PaymentNoticeDesign
from app.mod03_notice.print.template import PrintTemplate

# 主表数据集 id（模板字段格的 `dataSetId`）——与页面件同一口径
DS_HEADER = "3700000000000010"


def make_notice(
    notice_id: int,
    bill_no: str,
    bill_type: str = "material",
    *,
    fields: dict | None = None,
    project_name: str = "",
    approve_status: str = "",
) -> PaymentNotice:
    """构造**内存态**单据（不落库）—— 供纯函数编排断言。

    ℹ️ 签名**不落库**（渲染时从 `getFlowHisForPrint` 现场取，见 `print/signatures.py`），故本构造器无签名参数。
    """
    return PaymentNotice(
        id=notice_id,
        ph_id=f"ph-{notice_id}",
        bill_no=bill_no,
        bill_type=bill_type,
        project_name=project_name,
        approve_status=approve_status,
        amount_approved=0,
        amount_paid=0,
        fields=dict(fields or {}),
    )


# ---------------------------------------------------------------- 迷你模板工厂


def template(
    cells: list[dict],
    *,
    cols: int = 2,
    rows: int = 4,
    widths: dict | None = None,
    heights: dict | None = None,
    print_name: str = "测试版式",
) -> PrintTemplate:
    """按给定单元格造一个迷你版式（用真实 `PrintTemplate`，行为与真机模板同构）。"""
    return PrintTemplate(
        print_id="TEST-PID",
        print_name=print_name,
        sheet_name="表1",
        cols=cols,
        rows=rows,
        widths=widths or {i: 100 for i in range(cols)},
        heights=heights or {},
        cells=cells,
        margin={"top": 5, "left": 10, "right": 10, "down": 5},
    )


def text_cell(row: int, col: int, value: str, **extra) -> dict:
    """静态文本格（`cellType=text`）—— 常用作"这段版式确实来自 i8"的标记。"""
    cell = {
        "cellType": "text", "row": row, "col": col, "colspan": extra.pop("colspan", 1),
        "className": extra.pop("className", "htLeft"), "cellData": {"value": value},
        "cellBorders": {},
    }
    cell.update(extra)
    return cell


def field_cell(row: int, col: int, field_id: str, **extra) -> dict:
    """主表字段格（`cellType=field`）—— 值取 `values["<DS_HEADER>.<field_id>"]`。"""
    cell = {
        "cellType": "field", "row": row, "col": col, "colspan": extra.pop("colspan", 1),
        "className": extra.pop("className", "htLeft"),
        "cellData": {"dataSetId": extra.pop("data_set_id", DS_HEADER), "fieldId": field_id},
        "cellBorders": {},
    }
    cell.update(extra)
    return cell


def sign_cell(row: int, col: int, node: str, **extra) -> dict:
    """签名图格 —— `otherShowType=image` ＋ `dataFilter` 的**「办理节点」**（模板侧唯一口径）。"""
    cell = {
        "cellType": "field", "row": row, "col": col, "colspan": extra.pop("colspan", 1),
        "className": extra.pop("className", "htCenter"),
        "cellData": {
            "dataSetId": DS_HEADER,
            "fieldId": "签名",
            "otherShowType": "image",
            "dataFilter": [{"fieldId": "办理节点", "value": node}],
        },
        "cellBorders": {},
    }
    cell.update(extra)
    return cell


# ---------------------------------------------------------------- 取数桩


class FakeDesignFetcher:
    """版式取数桩：按单据类型返回注入的**模板**；`fail_on` 指定类型取不到版式。"""

    def __init__(self, designs: dict | None = None, *, fail_on: dict[str, Exception] | None = None) -> None:
        self.designs = dict(designs or {})
        self.fail_on = dict(fail_on or {})
        self.calls: list[str] = []

    def fetch(self, bill_type: str) -> PaymentNoticeDesign:
        self.calls.append(bill_type)
        if bill_type in self.fail_on:
            raise self.fail_on[bill_type]
        tpl = self.designs.get(bill_type)
        if tpl is None:
            raise MustReportError(f"取不到单据类型「{bill_type}」对应的版式（测试桩）")
        return PaymentNoticeDesign(bill_type=bill_type, print_id=f"pid-{bill_type}", tpl=tpl)


class FakeDetailFetcher:
    """单张单据「主表 / 明细 / 流程」取数桩（新链路的必需依赖）。"""

    def __init__(self, *, info: dict | None = None, detail: list | None = None, flow: list | None = None) -> None:
        self.info = dict(info or {})
        self.detail = list(detail or [])
        self.flow = list(flow or [])
        self.calls: list[tuple] = []

    def fetch_info(self, ph_id: str) -> dict:
        self.calls.append(("info", ph_id))
        return dict(self.info)

    def fetch_detail(self, ph_id: str) -> list[dict]:
        self.calls.append(("detail", ph_id))
        return [dict(r) for r in self.detail]

    def fetch_flow(self, ph_id: str) -> list[dict]:
        self.calls.append(("flow", ph_id))
        return [dict(r) for r in self.flow]


class FakeSignatureStore:
    """签名图桩：按**流程节点的相对路径**给 data URI。

    `default=""` 时未配置的路径一律取不到（模拟掉图）—— 用于验证 001-06 的报警。
    """

    def __init__(self, uris: dict | None = None, *, default: str = "") -> None:
        self.uris = dict(uris or {})
        self.default = default
        self.calls: list[str] = []

    def uri_for(self, rel: str) -> str:
        rel = str(rel or "").strip()
        self.calls.append(rel)
        if not rel:
            return ""
        return self.uris.get(rel, self.default)


class RenderSpy:
    """渲染桩：记录被渲染的 HTML；可注入失败。"""

    def __init__(self, payload: bytes = b"%PDF-1.4\n% fake pdf\n", *, fail: Exception | None = None) -> None:
        self.payload = payload
        self.fail = fail
        self.htmls: list[str] = []

    def __call__(self, html: str) -> bytes:
        self.htmls.append(html)
        if self.fail is not None:
            raise self.fail
        return self.payload


class DispatchSpy:
    """投递桩：记录投递次数；`fail_on_call` 指定第几次调用时抛错（001-08）。"""

    def __init__(self, *, fail_on_call: int | None = None, exc: Exception | None = None) -> None:
        self.calls: list[bytes] = []
        self.fail_on_call = fail_on_call
        self.exc = exc or MustReportError("出纸失败：打印机返回 IPP 状态码 0x0406（测试桩）")

    def __call__(self, pdf: bytes) -> None:
        self.calls.append(pdf)
        if self.fail_on_call is not None and len(self.calls) == self.fail_on_call:
            raise self.exc
