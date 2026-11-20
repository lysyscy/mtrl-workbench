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
⭐ 本件**兼作 `MOD-03` 的包间出口**（`TAIL-195` 批 2a）：**跨包调用只许经本件**（见文末那段）。
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
from app.mod02_i8.browser_session import StrictSessionStopped
from app.mod02_i8.client import I8OnlineConflictError
from app.mod02_i8.login import I8AuthFailedError
from app.mod03_notice.models import PaymentNotice
from app.mod03_notice.print.dispatch import DispatchOutcome, DispatchPlan
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
    unverified: bool = False
    """⭐ **已投递但无法核实**（`TAIL-46`-①）：`ok=True` 且本进程说不清"到底出纸没有"。
    ⚠️ 它**不是失败** —— 用户 2026-09-18 实测教训：「假失败比假成功更危险」（报失败 ⇒ 人重复打印白浪费纸）。"""
    reason: str = ""
    pdf_path: str = ""
    delivery: DispatchOutcome | None = None

    def receipt_fields(self) -> dict:
        return self.delivery.receipt_fields() if self.delivery else {}


@dataclass
class BatchResult:
    mode: str
    outcomes: list[ItemOutcome] = field(default_factory=list)
    batch_dir: str = ""
    """⚠️ 只有**显式传了 `batch_dir`**（工具/自检）才有值 —— 生产路径**不再落盘**（见 `files`）。"""
    files: list[tuple[str, bytes]] = field(default_factory=list)
    """⭐⭐ **本批产物的字节**（`(文件名, 字节)`，按单据顺序）—— **不落盘**：

    用户 2026-09-20 口径：「**导出的话，换成浏览器下载**」。
    ⚠️ 旧的"写进 `artifacts/pdf/<批次>/` 再给个路径"会在本机**越攒越多** ——
       实测 09-15 起已攒 **884 个 / 7.7MB**，而且用户还得**自己去翻目录**（壳里压根没用那些 URL）。
    ⇒ 渲染出的字节**只在这里停一下**，由 `pdf_cache` 交给 `GET /api/m03/pdf/{token}` 流给浏览器。
    ⚠️ 放**字节**而不是路径 ⇒ 从根上没有"文件留在本机"这回事。
    """

    @property
    def total(self) -> int:
        return len(self.outcomes)

    @property
    def success(self) -> list[ItemOutcome]:
        return [o for o in self.outcomes if o.ok]

    @property
    def failed(self) -> list[ItemOutcome]:
        return [o for o in self.outcomes if not o.ok and (not o.delivery or o.delivery.last.status == "failed")]

    @property
    def unknown(self) -> list[ItemOutcome]:
        return [o for o in self.outcomes if o.delivery and o.delivery.last.status == "unknown"]

    @property
    def unprinted_bill_nos(self) -> list[str]:
        """未产出（未出）单据的单号 —— 结束时必须显式列明（001-07 / PDF-001-06）。"""
        return [o.bill_no for o in self.failed]


@dataclass(frozen=True)
class PreparedPdf:
    notice_id: int
    bill_no: str
    filename: str
    content: bytes


def prepare_batch(
    notices: list[PaymentNotice],
    *,
    mode: str,
    design_fetcher: DesignLike,
    detail_fetcher: DetailLike,
    signature_store: SignatureStoreLike,
    render_pdf: Callable[[str], bytes],
    on_start: Callable[[int, str], None],
    on_item: Callable[[ItemOutcome, PreparedPdf | None], None],
    on_connected: Callable[[], None] = lambda: None,
) -> None:
    """Render the confirmed scope in order, without contacting a printer."""
    designs: dict[str, object] = {}
    used_names: set[str] = set()
    connected = False
    for notice in notices:
        bill_no = (notice.bill_no or "").strip() or str(notice.id)
        on_start(notice.id, bill_no)
        prepared = None
        try:
            if not notice.ph_id:
                raise MustReportError("通知书已不存在或缺少 i8 单据标识。")
            design = _get_design(designs, design_fetcher, notice.bill_type)
            if not connected:
                on_connected()
                connected = True
            html = render_notice_html(notice, design.tpl, detail_fetcher, signature_store)
            pdf = render_pdf(html)
            if not pdf.startswith(b"%PDF-"):
                raise MustReportError("未生成有效的 PDF。")
            name = _unique_name(bill_no, used_names)
            prepared = PreparedPdf(notice.id, bill_no, name, pdf)
            outcome = ItemOutcome(notice.id, bill_no, True, pdf_path=name)
        except (StrictSessionStopped, I8OnlineConflictError, I8AuthFailedError):
            raise
        except Exception as exc:  # noqa: BLE001
            reason = _reason(exc)
            logger.warning("准备 PDF 失败：单号={} 原因={}", bill_no, reason)
            outcome = ItemOutcome(notice.id, bill_no, False, reason=reason)
        on_item(outcome, prepared)
        if mode == MODE_PRINT and not outcome.ok:
            return


def dispatch_prepared(pdf: PreparedPdf, dispatch_pdf: Callable[[bytes], object]) -> ItemOutcome:
    try:
        reply = dispatch_pdf(pdf.content)
        if isinstance(reply, DispatchOutcome):
            status = reply.last.status
            return ItemOutcome(
                pdf.notice_id, pdf.bill_no, status == "accepted",
                unverified=status != "failed", reason=reply.last.reason, delivery=reply,
            )
        note = str(reply or "")
        return ItemOutcome(pdf.notice_id, pdf.bill_no, True, unverified=bool(note), reason=note)
    except Exception as exc:  # noqa: BLE001
        reason = _reason(exc)
        logger.warning("投递打印机失败：单号={} 原因={}", pdf.bill_no, reason)
        return ItemOutcome(pdf.notice_id, pdf.bill_no, False, reason=reason)


def complete_preparation(
    mode: str,
    ids: tuple[int, ...],
    outcomes: dict[int, ItemOutcome],
    prepared: list[PreparedPdf],
    *,
    bill_nos: dict[int, str],
) -> BatchResult:
    """Report every confirmed item, including those left unprocessed after a stop."""
    result = BatchResult(mode=mode)
    for notice_id in ids:
        outcome = outcomes.get(notice_id)
        if outcome is None or (mode == MODE_PRINT and outcome.ok):
            bill_no = bill_nos.get(notice_id, str(notice_id))
            reason = "本批准备失败，未投递。" if outcome else "本批准备已停止，未处理此单。"
            outcome = ItemOutcome(notice_id, bill_no, False, reason=reason)
        result.outcomes.append(outcome)
    if mode == MODE_PDF:
        result.files = [(pdf.filename, pdf.content) for pdf in prepared]
    return result


def run_batch(
    notices: list[PaymentNotice],
    *,
    mode: str,
    design_fetcher: DesignLike,
    detail_fetcher: DetailLike,
    signature_store: SignatureStoreLike,
    render_pdf: Callable[[str], bytes],
    dispatch_pdf: Callable[[bytes], object] | None = None,
    batch_dir: Path | None = None,
    lock_channel: Callable[[], DispatchPlan] | None = None,
) -> BatchResult:
    """Synchronous adapter for the existing endpoint and offline tools."""
    if mode not in _MODES:
        raise ValueError(f"未知模式：{mode}（应为 {' / '.join(_MODES)}）")
    if mode == MODE_PRINT and dispatch_pdf is None and lock_channel is None:
        raise MustReportError("打印模式缺少投递实现（内部错误）")

    outcomes: dict[int, ItemOutcome] = {}
    prepared: list[PreparedPdf] = []

    def on_item(outcome: ItemOutcome, pdf: PreparedPdf | None) -> None:
        outcomes[outcome.notice_id] = outcome
        if pdf is not None:
            prepared.append(pdf)

    prepare_batch(
        notices, mode=mode, design_fetcher=design_fetcher, detail_fetcher=detail_fetcher,
        signature_store=signature_store, render_pdf=render_pdf, on_start=lambda *_: None,
        on_item=on_item,
    )
    if mode == MODE_PRINT and prepared and len(prepared) == len(notices):
        sender = lock_channel().send if lock_channel else dispatch_pdf
        assert sender is not None
        return BatchResult(mode=mode, outcomes=[dispatch_prepared(pdf, sender) for pdf in prepared])

    result = complete_preparation(
        mode, tuple(notice.id for notice in notices), outcomes, prepared,
        bill_nos={notice.id: (notice.bill_no or "").strip() or str(notice.id) for notice in notices},
    )
    if mode == MODE_PDF and batch_dir is not None:
        base = Path(batch_dir)
        base.mkdir(parents=True, exist_ok=True)
        result.batch_dir = str(base.resolve())
        for outcome, pdf in zip(result.success, prepared, strict=True):
            outcome.pdf_path = str(_write_pdf(base, pdf.filename, pdf.content))
        result.files.clear()
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
    bound = bind_signatures(signature_store, flow, tpl=tpl)
    check_signature_coverage(tpl, flow, bound)  # 001-06：零命中即抛错，不出无签名件

    html, _slots = render_html(tpl, values=values, detail_rows=detail_rows, signatures=bound)
    return html


def _get_design(cache: dict[str, object], fetcher: DesignLike, bill_type: str):
    """批内按单据类型复用版式；**失败也缓存**（避免对同一类型反复失败重取）。"""
    if bill_type not in cache:
        try:
            cache[bill_type] = fetcher.fetch(bill_type)
        except (StrictSessionStopped, I8OnlineConflictError, I8AuthFailedError):
            raise
        except Exception as exc:  # noqa: BLE001
            cache[bill_type] = exc
    value = cache[bill_type]
    if isinstance(value, BaseException):
        raise value
    return value


def _safe_name(bill_no: str) -> str:
    cleaned = _UNSAFE_NAME_RE.sub("_", bill_no).strip(" .")
    return cleaned or "未命名单据"


def _unique_name(bill_no: str, used: set[str]) -> str:
    """单号 → 批内**不重名**的文件名（如同一单号被重复勾选 ⇒ `X.pdf` / `X_2.pdf`）。

    ⚠️ 从 `_write_pdf` 里拆出来：现在**不落盘**那条路也要用它（zip 里同样不能重名）。
    """
    stem = _safe_name(bill_no)
    name = f"{stem}.pdf"
    seq = 2
    while name in used:
        name = f"{stem}_{seq}.pdf"
        seq += 1
    used.add(name)
    return name


def _write_pdf(base: Path, name: str, pdf: bytes) -> Path:
    """落盘（⚠️ **只有显式给了目录才走这里** —— 工具/自检；生产路径不落盘）。"""
    path = base / name
    path.write_bytes(pdf)
    return path.resolve()


def _reason(exc: BaseException) -> str:
    """出纸 / 渲染失败要**如实说原因**（001-08）—— 异常自己带的话优先。

    ⚠️ `TAIL-212`：兜底**不许**回异常类名（那是技术串、用户看不懂）⇒ 给一句人话。
    """
    text = str(exc).strip()
    return text or "（打印服务没有说明原因）"


# ------------------------------------------------- 包间出口（`TAIL-195` 批 2a）
# ⚠️⚠️ 跨包调用**只许经这一层**（计划 §2.3：「包间只经 `service` 调用，**不得跨包直查对方表**」）。
#    ⛔ 别的包**别** `import app.mod03_notice.repository` —— 守卫 = `backend/tests/test_layering.py` **规则 C**。
#    ⭐ 与 `repository` 里那份**是同一个对象**（纯再导出，⛔ 不另写一套）——
#       同款先例：`mod03_notice/repository.py` 再导出 `MOD-02` 的运行记录仓储。
from app.mod03_notice import repository as _repo      # noqa: E402  ← 顶层导入安全（`repository` 不引 `service`）
def stat_paid_is_protected(s, notice_id: int) -> bool:
    """统计付款金额是否受人工留痕保护。"""
    from app.mod03_notice.domain import F_STAT_PAID, was_manually_edited
    return was_manually_edited(_repo.list_stat_traces(s, notice_id), notice_id, F_STAT_PAID)


list_stat_traces = _repo.list_stat_traces             # 统计手改留痕（=「是否手改」的唯一事实来源）
restore_stat_paid_auto = _repo.restore_stat_paid_auto  # 恢复模式与留痕，同事务包间出口


__all__ = ["project_references",
    "MODE_PRINT", "MODE_PDF",
    "DesignLike", "DetailLike", "SignatureStoreLike",
    "ItemOutcome", "BatchResult",
    "render_notice_html",      # ★ 全工程唯一的渲染入口（生产与预览工具共用）
    "run_batch",
    "list_stat_traces",        # ⭐ 包间出口（`TAIL-195` 批 2a）
    "restore_stat_paid_auto",
    "get_notice", "get_notices_by_ids", "all_notice_rows", "debt_notice_rows", "stat_paid_of_many",
]


def get_notice(session, notice_id, **kw):
    from app.mod03_notice import repository
    return repository.get_notice(session, notice_id, **kw)


def get_notices_by_ids(session, ids):
    from app.mod03_notice import repository
    return repository.get_notices_by_ids(session, ids)


def all_notice_rows(session):
    from app.mod03_notice import repository
    return repository.all_notice_rows(session)


def debt_notice_rows(session):
    from app.mod03_notice import repository
    return repository.debt_notice_rows(session)


def stat_paid_of_many(session, ids):
    """批量通知书统计付款事实，供集采装配金额。"""
    from app.mod03_notice import repository
    return repository.stat_paid_of_many(session, ids)


def project_references(session, project_id, warehouse, *, lock=False):
    """项目安全删除的只读关联明细；包括停用、撤销及恢复记录。"""
    from app.core.references import project_references as read
    from .models import PaymentNotice

    return read(session, ((PaymentNotice, '付款通知书'),), project_id, warehouse, lock=lock)
