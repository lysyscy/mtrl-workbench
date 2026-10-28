"""抓取任务（弹窗语义）：入参换算 · 命中回显 · 手动触发 · 降级 · 执行记录。

依据：《说明书》§3.1.3（触发方式 + 执行记录）· §3.2.1（导出条件）· §3.6（接口不可用时降级）· §9.2（时间口径）。
验收：`ACC-I8-FETCH-001`（8 点）。

⚠️ 本模块**纯逻辑**（不连库、不碰网络）：HTTP 与落库由调用方注入。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from app.core.errors import MustReportError
from app.core.logging import get_logger
from app.core.period import MODE_MONTH, parse_period, period_capabilities, period_range

logger = get_logger()

# ⚠️ 抓取**一律人工触发**（D9：本工程无任何定时任务，不引 APScheduler）；确认后关闭弹窗
MANUAL_ONLY = True
CONFIRM_CLOSES_DIALOG = True

# ⚠️ 不接竞价平台 —— **i8 是唯一外部数据源**（001-08 / §6.1.2 / `NG-13` / `DEV-J-05`）
EXTERNAL_SOURCES: tuple[str, ...] = ("i8",)

# 抓取对象（`§3.1.1` 数据来源清单；本片只用「付款通知书」）
OBJECT_NOTICE = "付款通知书"

# 抓取业务范围的确认令牌；保留旧值兼容既有调用，强踢不另设确认。
# ⚠️ **唯一存放处**：`MOD-03`/`MOD-08`/`MOD-07` 各抓取点**共用这一份**，
#    免得同一句"会强踢"的告知在多处各写一份、改一处漂一处（实测过这类副本必漂）。
CONFIRM_TOKEN = "kick-ok"
KICK_WARNING = (
    "抓取需要登录 i8 时允许**强踢该账号其他在线会话**（KillOnlineUser）。"
    "请确认抓取范围；同一张表**串行**抓取，失败**不会自动重试登录**。"
)


def build_fetch_params(year_month: str) -> dict:
    """入参 = **核算年月** → 单据日期起止（**闭区间**）（001-01）。

    ⚠️ 抓取**只允许「月」**（001-02）—— 业务上就是"一次一个月"，跨月 / 整年 / 全部一律拒绝。
    """
    if period_capabilities("fetch") != (MODE_MONTH,):
        raise RuntimeError("抓取只允许「月」模式（001-02）")
    mode, _ = parse_period(year_month)
    if mode != MODE_MONTH:
        raise MustReportError(
            f"抓取只允许「单月」核算年月，不支持跨月 / 整年 / 全部（收到：「{year_month}」）"
        )
    start, end = period_range(year_month)
    return {"year_month": year_month, "start_date": start, "end_date": end}


def echo_params(params: dict) -> str:
    """**回显换算结果**（001-01）—— 供用户在弹窗里核对。"""
    return (
        f"核算年月 {params['year_month']} ⇒ 单据日期 "
        f"{params['start_date']} ~ {params['end_date']}（闭区间）"
    )


@dataclass
class FetchPreview:
    """抓取前核对：**有效 / 剔除分列**（001-03）。"""

    total: int
    valid: int
    excluded: int
    excluded_rows: list[dict] = field(default_factory=list)


def preview(rows: list[dict], is_excluded: Callable[[dict], bool] | None = None) -> FetchPreview:
    """该月**命中条数**（有效 / 剔除分列）。

    ⚠️ 剔除规则本身属付款域（§4.2.2）⇒ 由调用方注入 `is_excluded`；本模块只做分列。
    """
    pred = is_excluded or (lambda _r: False)
    excluded = [r for r in rows if pred(r)]
    return FetchPreview(
        total=len(rows),
        valid=len(rows) - len(excluded),
        excluded=len(excluded),
        excluded_rows=excluded,
    )


@dataclass
class FetchDialog:
    """抓取弹窗状态（**改月份 ⇒ 整个弹窗自动重建**，001-04）。"""

    year_month: str
    params: dict
    preview: FetchPreview

    @property
    def echo(self) -> str:
        return echo_params(self.params)


def build_dialog(
    year_month: str,
    rows: list[dict],
    is_excluded: Callable[[dict], bool] | None = None,
) -> FetchDialog:
    """按核算年月构建弹窗状态；改月重建 ⇒ 区间与命中条数随之更新（001-04）。"""
    return FetchDialog(
        year_month=year_month,
        params=build_fetch_params(year_month),
        preview=preview(rows, is_excluded),
    )


def degrade_to_excel(exc: BaseException) -> dict:
    """接口不可用 ⇒ **降级为手动 Excel 导入**，且**必须显式说明处于降级路径**（§3.6）。

    ⚠️ **不得静默** —— 返回体里带 `degraded=True` 与说明；调用方必须把它呈给用户。
    ⚠️ **服务对象 = m02 / m07 / m11**（它们的手动/导入通道仍在）。
       ⛔ **m08 不在列**：库存手动导入已按用户 2026-09-22 裁定删除 ⇒ m08 用
       `degrade_no_manual`（显式报错待人处理），**别再把 m08 接回本函数**。
    """
    logger.warning("i8 抓不到数 ⇒ 降级为手动 Excel 导入：%s", exc)
    return {
        "degraded": True,
        "excel_import_available": True,
        "message": (
            "i8 抓不到数 ⇒ 已**降级为手动 Excel 导入**路径。"
            "请从 i8 导出该月数据后在本页导入。"
        ),
    }


def degrade_no_manual(exc: BaseException) -> dict:
    """接口不可用且**无手动兜底** ⇒ **显式报错待人处理**（m08 专用的降级说明）。

    依据 = 用户 2026-09-22 裁定：「库存单据手动导入给删掉，不要了」⇒ 库存数据唯一入口 = i8 抓取。
    ⚠️ 同样**不得静默**（`degraded=True` ＋ 原因），但**不得**再承诺"可手动导入"。
    """
    logger.warning("i8 抓不到数（本域无手动兜底）：%s", exc)
    return {
        "degraded": True,
        "message": (
            "i8 抓不到数 ⇒ 本次抓取**失败**。"
            "请稍后在 i8 可用时重试。"
        ),
    }


def fetch_record_payload(
    *,
    object_desc: str,
    success: int,
    fail: int,
    error_message: str = "",
) -> dict:
    """每次抓取**留一条执行记录**（时间 · 对象 · 结果 · 失败原因）（001-07）。

    供看板提示「本月尚未抓取」「最近一次抓取失败」。
    """
    if (fail or error_message) and not success:
        status = "failed"
    elif fail:
        status = "partial"
    else:
        status = "success"
    return {
        "run_type": "fetch",
        "target": object_desc,
        "status": status,
        "success_count": success,
        "fail_count": fail,
        "total_count": success + fail,
        "error_message": error_message,
    }


def assert_single_external_source() -> None:
    """**防回归**：外部数据源只能是 i8（001-08）。"""
    if EXTERNAL_SOURCES != ("i8",):
        raise AssertionError(f"外部数据源被改动：{EXTERNAL_SOURCES}（应为仅 i8）")


__all__ = [
    "MANUAL_ONLY", "CONFIRM_CLOSES_DIALOG", "EXTERNAL_SOURCES", "OBJECT_NOTICE",
    "CONFIRM_TOKEN", "KICK_WARNING",
    "build_fetch_params", "echo_params", "FetchPreview", "preview",
    "FetchDialog", "build_dialog", "degrade_to_excel", "fetch_record_payload",
    "assert_single_external_source",
]
