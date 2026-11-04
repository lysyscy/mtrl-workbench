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
    allow_kick: bool = Field(False, description="界面主动操作传 true；省略时不强踢在线会话")
    #: 取数方式：空／`http` ＝产品原直连；`browser` ＝复用浏览器里已登录的 i8 会话。
    #: ⭐ 缺省值保证旧调用**行为逐字节不变**（仍走原 `I8Client`）。
    session_mode: str = Field("", description="http（缺省）＝直连；browser＝浏览器已有会话")
    #: 浏览器方式必传：本页面的连接标识（不是账号、不是凭据）。
    device_id: str = Field("", description="浏览模式必传：本页面的连接标识")


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
    allow_kick: bool = Field(False, description="界面主动操作传 true；省略时不强踢在线会话")
    session_mode: str = Field("", description="http（缺省）＝直连；browser＝浏览器已有会话")
    device_id: str = Field("", description="浏览模式必传：本页面的连接标识")


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


class BrowserConnectRequest(BaseModel):
    """「连接浏览器会话」入参。

    ⚠️ `i8_account` / `i8_org` 是**扩展从已登录 i8 页面可见身份读到的值**（不是用户手填：
       手填值一律不被接受为机器核对结果）。后端会拿它们与「工作台本人绑定的 i8 账号」
       和「取数组织范围」逐个比对，缺失或不符 ⇒ 停止。
    """

    device_id: str = Field(..., description="本页面的随机标识（sessionStorage，仅本页有效）")
    i8_origin: str = Field(..., description="浏览器里那个 i8 标签的站点原点（协议://主机[:端口]）")
    i8_account: str = Field("", description="i8 页面可见的登录账号")
    i8_org_code: str = Field("", description="i8 页面可见的组织**短码**（账号面板「名称 ｜ 短码」右侧）")
    i8_org_name: str = Field("", description="i8 页面可见的组织**名称**（同一行左侧）")


class BrowserStateOut(BaseModel):
    """连接/模式状态（去敏：不含 Cookie、不含令牌、不含页面内容）。"""

    connected: bool = False
    mode: str = "http"
    origin: str = ""
    i8_user: str = ""
    expected_org: str = ""
    expected_org_code: str = ""
    expected_org_name: str = ""
    #: 本次连接的**代号**：每次 connect 递增。页面回帖必须带同一个代号，
    #: 否则"断开重连之后，迟到的旧回帖"会被静默当成新连接的结果（见 `browser_broker`）。
    generation: int = 0
    message: str = ""


class BrowserPendingOut(BaseModel):
    """长轮询取活结果。`request` 为空是**正常状态**（没有活干），不是错误。"""

    request: dict | None = None


class BrowserCompleteRequest(BaseModel):
    """回帖：一次性票 + 响应原文（body 走 base64，二进制/文本都安全）。

    ⚠️ `generation` 必须与**当前这次连接**的代号一致：断开重连后，旧连接的迟到回帖
       不许落到新连接上（否则"上一次会话的结果"会被当成本次结果用）。
    """

    device_id: str
    ticket: str
    generation: int = 0
    status: int
    headers: dict[str, str] = Field(default_factory=dict)
    body_b64: str = ""
    declared_length: int | None = None


class BrowserCompleteOut(BaseModel):
    accepted: bool = False
    message: str = ""


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
