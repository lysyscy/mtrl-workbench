"""`MOD-02` API 出入参（抓取任务页）。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class FetchPlanOut(BaseModel):
    """抓取弹窗的入参换算与能力声明（001-01 / 001-02）。"""

    year_month: str
    start_date: str
    end_date: str
    echo: str
    capabilities: list[str] = Field(default_factory=list)
    manual_only: bool = True
    confirm_closes_dialog: bool = True


class FetchPreviewRequest(BaseModel):
    year_month: str
    allow_kick: bool = Field(False, description="⚠️ 强制踢掉该账号其他在线会话，须用户显式授权")


class FetchPreviewOut(BaseModel):
    year_month: str
    echo: str
    total: int = 0
    valid: int = 0
    excluded: int = 0
    degraded: bool = False
    message: str = ""


class FetchRunRequest(BaseModel):
    year_month: str
    allow_kick: bool = Field(False, description="⚠️ 登录含强踢（KillOnlineUser），须显式授权")


class FetchRunOut(BaseModel):
    year_month: str
    fetched: int = 0
    status: str = "success"
    degraded: bool = False
    message: str = ""


class SyncOut(BaseModel):
    table: str
    count: int = 0
    sample: list[dict] = Field(default_factory=list)
    degraded: bool = False
    message: str = ""
    #: 建档四类计数（`ACC-PRJ-SYNC-001`）：新建 / 已存在 / 待人工 / 缺 phid —— **都要给，禁静默**
    counts: dict[str, int] = Field(default_factory=dict)


class RunRecordOut(BaseModel):
    id: int
    run_type: str
    target: str
    status: str
    success_count: int
    fail_count: int
    error_message: str
    started_at: str
    finished_at: str | None = None
    triggered_by: str = "manual"
    duration_seconds: float | None = None
