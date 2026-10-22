"""MOD-03 API 出入参（切片 1 最小）。

⚠️ 这里的字段只服务「打印 / 仅导出 PDF / 打印机设置」三条入口，**不含业务取值**。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class BatchRequest(BaseModel):
    """批量操作请求。

    ⚠️ `ids` 来自**系统内勾选**（单选 = 1 个元素、多选 = N 个元素）——
    **不接受文件 / 手输清单**（001-09 / PDF-001-01）。
    """

    ids: list[int] = Field(..., min_length=1, description="系统内勾选的单据 id（单选或多选）")
    mode: Literal["print", "pdf"] = Field("print", description="print=批量打印；pdf=只导出 PDF")


class ItemOutcomeOut(BaseModel):
    notice_id: int
    bill_no: str
    ok: bool
    unverified: bool = Field(
        False,
        description="**已投递但无法核实**（`ok=True` 时为「说不清」）—— ⚠️ 它不是失败：报失败会让人重复打印",
    )
    reason: str = ""
    pdf_path: str = ""
    download_url: str = ""


class BatchResponse(BaseModel):
    mode: str
    total: int
    success: int
    failed: int
    unprinted_bill_nos: list[str] = Field(default_factory=list, description="未产出单据的单号（001-07 / PDF-001-06）")
    batch_dir: str = ""
    items: list[ItemOutcomeOut] = Field(default_factory=list)


class FetchRequest(BaseModel):
    """按核算年月抓取付款通知书（D4 最小取数 · 纯手动触发）。"""

    year_month: str = Field(..., description="核算年月，形如 2026-08")
    expected_account: str | None = None
    allow_kick: bool = Field(
        False,
        description="是否允许强踢（KillOnlineUser）。⚠️ 登录会挤掉该账号其他在线会话，须用户显式授权",
    )


# --------------------------------------------------------------- 链路 C 弹窗（`TAIL-29`-② ④）


class SmallCandidateOut(BaseModel):
    """候选具体小微（弹窗逐行显示）。⚠️ 写操作一律按 **`id`** 定位，⛔ 不用全名反查。"""

    id: int
    disp: str = ""
    warehouse_name: str = ""
    keywords: list[str] = []
    status: str = ""


class UnresolvedItemOut(BaseModel):
    """一条「归属未走完」的记录 —— 链路口径：**弹窗的全部输入**。"""

    project_name: str = ""
    doc_name: str = ""
    bill_no: str = ""
    kind: str = ""
    shell_id: int | None = None
    reason: str = ""
    candidates: list[SmallCandidateOut] = []


class FetchResponse(BaseModel):
    year_month: str
    fetched: int
    upserted: int
    ignored: list[UnresolvedItemOut] = Field(default_factory=list)


class UnresolvedResponse(BaseModel):
    """最近一次「归属未走完」的抓取 ⇒ **未命中清单**。

    ⛔ 这里**不暂存整批数据**（用户 2026-09-18 裁定 `B`：补完关键词**再抓一次**）。
    """

    items: list[UnresolvedItemOut] = []


class AssignRequest(BaseModel):
    """补词 / 选小微（链路 C 弹窗提交，形态与原型 `ownOk` 一致）。

    - **选已有小微** ⇒ `small_id` ＋ `keyword`（关键词**必须出现在单据名里**）
    - **属于新小微** ⇒ `shell_id` ＋ `new_small_name` ＋ `keyword`
    """

    doc_name: str = ""
    keyword: str = ""
    small_id: int | None = None
    shell_id: int | None = None
    new_small_name: str = ""


class AssignResponse(BaseModel):
    ok: bool = False
    message: str = ""


class WarehouseCheckRequest(BaseModel):
    """**兜底前先跑一次 i8 仓库名单**（`TAIL-39`）。

    ⚠️ `allow_kick` 默认 `False`（`D9`）：取名单**要登录 i8**、可能**强踢**在线用户
       ⇒ 壳侧**必须在二次确认之后**才允许传 `True`。
    """

    warehouse_name: str = ""
    allow_kick: bool = False


class WarehouseCheckOut(BaseModel):
    """查一次的结果 —— ⚠️ 四态要分清（禁静默）：
    `found` 真 = 名单里有它 ｜ `found` 假且**没降级** = 名单里确实没有 ｜ `degraded` 真 = **没取到名单**（≠ 没有）。
    """

    warehouse_name: str
    found: bool = False
    owners: list[str] = []
    total: int = 0
    degraded: bool = False
    from_cache: bool = Field(False, description="这份结论用的是**上一次抓到的名单**（⛔ 不是刚抓的）")
    cached_at: str = Field("", description="上面那份缓存的抓取时间（`from_cache` 为真时必须一起说给用户）")
    message: str = ""


class PrinterSettingRequest(BaseModel):
    """打印机设置（`ACC-PAY-SETUP-001` ＋ `TAIL-46`-③ 的三项：地址 / 出纸通道 / 打印机名）。

    ⚠️ 通道口径照用户调好的 `i8一键打印_新版`：`auto` 依次试 IPP → 系统驱动 → RAW 9100（推荐）；
    `ipp` 只走标准方式；`driver` 走 Windows 打印驱动（须给打印机名）；`raw` 只走 RAW 9100。
    """

    printer_ipp_url: str = Field(..., description="打印机地址，形如 ipp://192.168.5.248")
    print_mode: str = Field("auto", description="出纸通道：auto（自动降级）/ ipp / driver / raw")
    printer_name: str = Field("", description="「系统驱动」通道用的打印机名（选 driver 时必填，其余留空）")


class PrinterSettingResponse(BaseModel):
    printer_ipp_url: str
    print_mode: str = "auto"
    printer_name: str = ""
