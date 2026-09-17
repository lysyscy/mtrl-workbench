"""批量打印 / 仅导出 PDF 编排（`ACC-PAY-PRINT-001` + `ACC-PAY-PDF-001`）。

依据（《说明书》§4.6 + `DEV-P-07` / `API-07`）：
- 入口一律 **系统内勾选**（不依赖外部文件 / 手输清单），**单选与多选同一条通路**（001-09）。
- 版式一律取自 i8（`design`），**本地只渲染与出纸，不自绘版式**（001-01）。
- **取不到版式 / 渲染失败 ⇒ 该单据显式报错、不静默产出空白件**（001-03 / PDF-001-05）。
- **出纸失败 ⇒ 显式报出原因**（001-08）。
- **批内任一单据未产出 ⇒ 结束时列明未出单号**（001-07 / PDF-001-06）。
- 「仅导出 PDF」与「批量打印」**共用同一次勾选**，只渲染落盘、**不投递**（PDF-001-01/02）。

⚠️ 分层（可离线单测）：
- `run_batch()` 是**纯函数** —— 版式取数器 / 渲染器 / 投递器**全部依赖注入**，
  故 22 条判据里的绝大多数可**不连库、不启浏览器、不碰打印机**地断言。
- 落库（运行记录）与真实依赖的组装在 `router.py`（薄层）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Protocol

from app.core.config import get_settings
from app.core.errors import MustReportError
from app.core.logging import get_logger
from app.mod03_notice.models import PaymentNotice
from app.mod03_notice.print.fields import build_detail_rows, build_values
from app.mod03_notice.print.signatures import bind_signatures, check_signature_coverage
from app.mod03_notice.print.template import render_html

logger = get_logger()

MODE_PRINT = "print"
MODE_PDF = "pdf"
_MODES = (MODE_PRINT, MODE_PDF)

_UNSAFE_NAME_RE = re.compile(r'[\\/:*?"<>|\r\n\t]+')


class DesignLike(Protocol):
    """版式取数器协议（生产 = `print/design.DesignFetcher`；测试注入桩）。

    ⚠️ 返回的是**版式模板**（`PaymentNoticeDesign.tpl`），不是 HTML。
    """

    def fetch(self, bill_type: str):  # -> PaymentNoticeDesign
        ...


class DetailLike(Protocol):
    """单张单据的**主表 / 明细 / 流程**取数器协议。

    ⚠️ **必填依赖** —— 漏传会导致渲染出空值（印出空白件而毫无提示），故不给默认值。
    生产 = `mod02_i8.notice_source.NoticeDetailFetcher`。
    """

    def fetch_info(self, ph_id: str) -> dict:
        ...

    def fetch_detail(self, ph_id: str) -> list[dict]:
        ...

    def fetch_flow(self, ph_id: str) -> list[dict]:
        ...


class SignatureStoreLike(Protocol):
    """签名图取用器协议（生产 = `print/signatures.SignatureStore`）。"""

    def uri_for(self, rel: str) -> str:
        ...


@dataclass
class ItemOutcome:
    """单张单据的结果（逐单据留痕，支撑 001-07 / PDF-001-06 的未出清单）。"""

    notice_id: int
    bill_no: str
    ok: bool
    reason: str = ""
    pdf_path: str = ""


@dataclass
class BatchResult:
    mode: str
    outcomes: list[ItemOutcome] = field(default_factory=list)
    batch_dir: str = ""

    @property
    def total(self) -> int:
        return len(self.outcomes)

    @property
    def success(self) -> list[ItemOutcome]:
        return [o for o in self.outcomes if o.ok]

    @property
    def failed(self) -> list[ItemOutcome]:
        return [o for o in self.outcomes if not o.ok]

    @property
    def unprinted_bill_nos(self) -> list[str]:
        """未产出（未出）单据的单号 —— 结束时必须显式列明（001-07 / PDF-001-06）。"""
        return [o.bill_no for o in self.outcomes if not o.ok]


def run_batch(
    notices: list[PaymentNotice],
    *,
    mode: str,
    design_fetcher: DesignLike,
    detail_fetcher: DetailLike,
    signature_store: SignatureStoreLike,
    render_pdf: Callable[[str], bytes],
    dispatch_pdf: Callable[[bytes], None] | None = None,
    batch_dir: Path | None = None,
) -> BatchResult:
    """编排一批单据的「渲染 → （打印 / 落盘）」。

    - 渲染 = **模板驱动**（`template.render_html`）：版式来自 i8、数据来自三个详情接口、签名按节点名绑定。
    - `mode=print`：渲染后调 `dispatch_pdf` 投递（001-08 失败显式报）。
    - `mode=pdf`：只渲染并落盘到产物目录，**绝不调 `dispatch_pdf`**（PDF-001-02）。
    - 任一张失败 ⇒ 记入 `outcomes`（含原因），**不中断整批**，结束时由 `unprinted_bill_nos` 列明。
    """
    if mode not in _MODES:
        raise ValueError(f"未知模式：{mode}（应为 {' / '.join(_MODES)}）")
    if mode == MODE_PRINT and dispatch_pdf is None:
        raise MustReportError("打印模式缺少投递实现（内部错误）")

    result = BatchResult(mode=mode)

    base: Path | None = None
    if mode == MODE_PDF:
        base = Path(batch_dir) if batch_dir is not None else _new_batch_dir()
        base.mkdir(parents=True, exist_ok=True)
        result.batch_dir = str(base.resolve())

    designs: dict[str, object] = {}   # bill_type → PaymentNoticeDesign | Exception（批内复用，不重复取版式）
    used_names: set[str] = set()

    for notice in notices:
        bill_no = (notice.bill_no or "").strip() or str(notice.id)
        try:
            design = _get_design(designs, design_fetcher, notice.bill_type)
            html = render_notice_html(notice, design.tpl, detail_fetcher, signature_store)
            pdf = render_pdf(html)
            if mode == MODE_PRINT:
                dispatch_pdf(pdf)  # type: ignore[misc]
                result.outcomes.append(ItemOutcome(notice.id, bill_no, True))
            else:
                path = _write_pdf(base, bill_no, pdf, used_names)  # type: ignore[arg-type]
                result.outcomes.append(ItemOutcome(notice.id, bill_no, True, pdf_path=str(path)))
        except Exception as exc:  # noqa: BLE001 —— 逐单据兜住，转成"未出 + 原因"，绝不静默
            reason = _reason(exc)
            logger.warning("批量{} 未产出：单号={} 原因={}", mode, bill_no, reason)
            result.outcomes.append(ItemOutcome(notice.id, bill_no, False, reason=reason))

    return result


# --------------------------------------------------------------------- internals


def render_notice_html(
    notice,
    tpl,
    detail_fetcher: DetailLike,
    signature_store: SignatureStoreLike,
) -> str:
    """单张单据 → 打印 HTML（**模板驱动渲染**）—— ⚠️ **全工程唯一的渲染入口**。

    生产（`run_batch`）与工具（`tools/render_preview.py`）**都调这里**，
    使"预览看到的"与"实际打印的"是同一条路径（不各写一份组装，避免副本漂移）。
    `notice` 只需具备 `.ph_id` 与 `.fields`（鸭子类型，便于工具传轻量对象）。

    - 数据来源：`getInfo`（主表）· `getDetInfo`（明细）· `getFlowHisForPrint`（流程 = 签名）；
      ⚠️ 列表接口（`getList`）的字段**打底**、详情**覆盖** —— 两者是同一张单据的数据，详情更权威。
    - `001-04/05/06`：签名一律走 `signatures`（按节点名绑定 · 未走到留空 · **零命中抛错**）。
    - `001-10`：零值金额格留空 —— 由 `fields.money()` 保证（本层**不重复判一次**，避免两套口径）。
    """
    ph_id = str(getattr(notice, "ph_id", "") or "")
    info = {
        **dict(getattr(notice, "fields", None) or {}),
        **(detail_fetcher.fetch_info(ph_id) or {}),
    }
    detail = detail_fetcher.fetch_detail(ph_id)
    flow = detail_fetcher.fetch_flow(ph_id)

    values = build_values(info, detail)
    detail_rows = build_detail_rows(detail)
    bound = bind_signatures(signature_store, flow)
    check_signature_coverage(tpl, flow, bound)  # 001-06：零命中即抛错，不出无签名件

    html, _slots = render_html(tpl, values=values, detail_rows=detail_rows, signatures=bound)
    return html


def _get_design(cache: dict[str, object], fetcher: DesignLike, bill_type: str):
    """批内按单据类型复用版式；**失败也缓存**（避免对同一类型反复失败重取）。"""
    if bill_type not in cache:
        try:
            cache[bill_type] = fetcher.fetch(bill_type)
        except Exception as exc:  # noqa: BLE001
            cache[bill_type] = exc
    value = cache[bill_type]
    if isinstance(value, BaseException):
        raise value
    return value


def _new_batch_dir() -> Path:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    return get_settings().pdf_export_path / ts


def _safe_name(bill_no: str) -> str:
    cleaned = _UNSAFE_NAME_RE.sub("_", bill_no).strip(" .")
    return cleaned or "未命名单据"


def _write_pdf(base: Path, bill_no: str, pdf: bytes, used: set[str]) -> Path:
    stem = _safe_name(bill_no)
    name = f"{stem}.pdf"
    seq = 2
    while name in used:  # 批内重名（如同一单号重复勾选）不覆盖
        name = f"{stem}_{seq}.pdf"
        seq += 1
    used.add(name)
    path = base / name
    path.write_bytes(pdf)
    return path.resolve()


def _reason(exc: BaseException) -> str:
    text = str(exc).strip()
    return text or type(exc).__name__


__all__ = [
    "MODE_PRINT", "MODE_PDF",
    "DesignLike", "DetailLike", "SignatureStoreLike",
    "ItemOutcome", "BatchResult",
    "render_notice_html",      # ★ 全工程唯一的渲染入口（生产与预览工具共用）
    "run_batch",
]
