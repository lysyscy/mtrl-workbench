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
    allow_kick: bool = Field(
        False,
        description="是否允许强踢（KillOnlineUser）。⚠️ 登录会挤掉该账号其他在线会话，须用户显式授权",
    )


class FetchResponse(BaseModel):
    year_month: str
    fetched: int
    upserted: int


class PrinterSettingRequest(BaseModel):
    printer_ipp_url: str = Field(..., description="打印机地址，形如 ipp://192.168.5.248")


class PrinterSettingResponse(BaseModel):
    printer_ipp_url: str
