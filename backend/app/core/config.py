"""配置（唯一入口）。

- 凭据只来自环境变量 / `.env`（工程底线·安全：**绝对禁止硬编码**）。
- `.env` 在工程根，已在 `.gitignore` 里。
- ⚠️ 本模块**不含任何业务取值**；业务口径一律回《材料科业务全流程说明书》。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.errors import NotConfiguredError

# backend/app/core/config.py -> 工程根
PROJECT_ROOT: Path = Path(__file__).resolve().parents[3]
ENV_FILE: Path = PROJECT_ROOT / ".env"


# --------- i8 端点路径（**固定常量** —— 会变的只有 `host:port`，见《说明书》§7.8）
# ⚠️ 四个端点**不得各存一份**：一律由「i8 服务地址」＋ 下列常量推导。
I8_PATH_PRINT_DESIGN = "/reportcenter/printManage/getPrintDesign"
I8_PATH_PAYMENT_NOTICE = "/FC/FM/PaymentBill/getList"
I8_PATH_WAREHOUSE_LIST = "/PMS/PMM/KcBaseSetting/GetWareHouseList"
I8_PATH_COMMON_PROJECT = (
    "/SUP/RichHelp/GetCommonUseList?helpid=project_table_pchelp&ORMMode=true&skipInfoAuth=1"
)
# 报表类导出（收发结存 / 库存单据）—— 与上面几个不是同一条路：**POST JSON + 直接返回 xlsx**
I8_PATH_REPORT_EXPORT = "/reportcenter/reportExport/export"

# --------- 报表类导出的**三项标识**（主人 = 《技术栈选型分析》§9.8 定稿）
# ⚠️ **每张表各存一份**（`rep_id` / `dataSetId` / 项目参数 key / `reportName` 四者**逐表不同**，
#    合并成"通用值"必错）；⚠️ 时间入参 = 「起止年月」四个独立值（见 `mod02_i8.report_export`）。
# ⚠️ 这里**只登记已定稿的**表；取值以《技术栈选型分析》§9.8 为准（工程侧不得各自另记一份）。
I8_REPORTS: dict[str, dict] = {
    "inv": {
        "rep_id": "3700000000000104",
        "dataset_id": "3700000000000165",
        "proj_param": "xmid",      # ⚠️ 收发结存用 `pc`，本表用 `xmid`
        "report_name": None,       # ⭐ 库存单据**必须传 null**（与收发结存不同，已抓包确认）
        "label": "库存单据明细表",
    },
    # `API-02` 收发结存表 —— 三项标识与表名均定稿（2026-09-16 从素材包取齐：
    # `PRD素材包-20260911/input/sfjc_export_http.py` 的 `REPORT_NAME`，已回写 §9.8）
    "setl": {
        "rep_id": "3700000000000085",
        "dataset_id": "3700000000000178",
        "proj_param": "pc",        # ⭐ 收发结存的项目参数 key = `pc`（§9.8）
        "report_name": "收发结存表",   # ⭐ **必须传表名**（与库存单据的 null 相反）
        "label": "收发结存表",
    },
}


# --------- ⭐ 系统设置的**取值出口**（§7.8）-----------------------------------
# ⚠️ 做成**模块级函数**（而非只挂 `Settings` 方法）—— 测试桩只要还有 `i8_base_url`
#    字段就能用，不必跟着加方法。


def effective_of(key: str, fallback: str) -> str:
    """⭐ **唯一取值出口**：库（「设置」页所设）→ `.env`。

    ⚠️ 调用方**不得各自读 `.env`** —— 否则出现「页面改了但不生效」。
    """
    from app.core.app_settings import effective

    return effective(key, fallback)


def i8_base_of(settings) -> str:
    """i8 服务地址（`host:port`）—— 页面可改（§7.8 设置项 1）。"""
    return effective_of("i8_base_url", getattr(settings, "i8_base_url", "") or "").rstrip("/")


def i8_endpoint_of(settings, path: str) -> str:
    """⭐ i8 端点 = **服务地址 ＋ 常量路径**（四个端点**不得各存一份**，§7.8 ①）。

    ⚠️ 返回值**恒非空**（至少有路径部分）⇒ **判「是否配置」要判 `i8_base_of()`**，别判本函数的返回值。
    """
    return i8_base_of(settings) + path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- 应用 ---
    app_env: str = "dev"
    app_host: str = "0.0.0.0"  # D1=A：绑 0.0.0.0 + 应用层 IP 白名单中间件
    app_port: int = 8000

    # --- 访问控制（D1=A：不用反向代理，靠应用层白名单 + 防火墙）---
    # 逗号分隔的 CIDR；**为空时 dev 放行并告警、非 dev 拒绝启动**
    allowed_ip_cidrs: str = ""
    # 同源部署时留空；仅开发期前端 dev server 需要
    cors_allow_origins: str = ""

    # --- 数据库（开发库 / 测试库物理隔离）---
    database_url: str = ""
    test_database_url: str = ""

    # --- 验收基线（D3：直读 PRD 快照，工程内不留副本）---
    prd_acceptance_baseline: str = ""

    # --- i8（纯 HTTP；登录含强踢，抓取一律人工触发）---
    i8_base_url: str = ""
    i8_user: str = ""
    i8_password: str = ""
    # i8 登录页前端 JS 里的 SM2 私钥（**公开资产**，非本系统凭据）；留空则用内置默认值
    i8_sm2_private_key: str = ""

    # --- i8 业务接口（**契约待确认**：PRD 仅给接口名 getPrintDesign/API-01，未给 URL 与参数口径）---
    # 端点 URL 一律走配置，不硬编码；以下为空 ⇒ 由 NotConfiguredError 显式报错（不得静默）
    i8_payment_notice_url: str = ""  # API-01：付款通知书取数（D4 最小取数）
    # API-04：采购合同列表（集采抓取）—— ⚠️ 2026-09-19 **实测确认 = POST**（GET 会 500「method 'GET' is not supported」；
    #   无会话会 401「No SessionInfo found」）⇒ 必须走登录后的 client，⛔ 不能当普通 GET 打。
    i8_contract_list_url: str = ""
    i8_print_design_url: str = ""  # API-07：取版式 getPrintDesign
    # 两类分流（机械类 / 辅材·集采类）的 printId（**取值待确认**，从配置读、不写死）
    i8_print_id_mechanical: str = ""
    i8_print_id_material: str = ""

    # --- i8 基础数据源（**契约待确认**：PRD 只给接口名 API-05 / API-06）---
    i8_warehouse_list_url: str = ""   # API-05：仓库列表 GetWareHouseList（仓库名 ↔ 所属项目全名）
    i8_common_project_url: str = ""   # API-06：常用项目列表 GetCommonUseList（phid 权威来源）

    # --- 打印机（IPP 直投）---
    printer_ipp_url: str = ""
    # ⭐ 打印**出纸通道**（`TAIL-46`-③ —— 口径照用户调好的 `i8一键打印_新版`）：
    #    `auto` 依次试 IPP → 系统驱动 → RAW 9100；`ipp` 只走标准方式；`driver` 走 Windows 打印驱动；
    #    `raw` 只走 RAW 9100。⚠️ 选 `driver` 时必须给 `printer_name`（同一台机器上驱动与 IP 是两回事）。
    print_mode: str = "auto"
    printer_name: str = ""

    # --- 当前操作人（留痕 / 手动行录入人；⚠️ `MOD-15` 用户管理落地前的中性占位）---
    operator_name: str = ""

    # --- 登录会话签名密钥（`MOD-15` · 见 `core/session.py`）---
    # ⚠️ **不允许有硬编码默认值**（本文件开篇的底线：凭据只来自环境变量 / `.env`）——
    #    留空时由 `session.secret()` **生成一个并写回 `.env`**（只做一次）。
    session_secret: str = ""

    # --- 产物体与日志 ---
    artifacts_dir: str = "artifacts"
    logs_dir: str = "logs"
    log_retention_days: int = 30

    @property
    def artifacts_path(self) -> Path:
        return PROJECT_ROOT / self.artifacts_dir

    @property
    def logs_path(self) -> Path:
        return PROJECT_ROOT / self.logs_dir

    @property
    def pdf_export_path(self) -> Path:
        """「仅导出 PDF」产物目录（artifacts/pdf/<批次时间戳>/）。"""
        p = self.artifacts_path / "pdf"
        p.mkdir(parents=True, exist_ok=True)
        return p

    # --- ⭐ 系统设置（§7.8）：取值 = **库（页面所设）→ .env** ---------------

    def _effective(self, key: str, fallback: str) -> str:
        """走**唯一取值出口**（见模块级 `effective_of`）。"""
        return effective_of(key, fallback)

    def i8_base(self) -> str:
        """i8 服务地址（`host:port`）—— 页面可改（§7.8 设置项 1）。"""
        return i8_base_of(self)

    def i8_endpoint(self, path: str) -> str:
        """⭐ i8 端点 = **服务地址 ＋ 常量路径**（四个端点**不得各存一份**，§7.8 ①）。"""
        return i8_endpoint_of(self, path)

    def print_id_for_bill_type(self, bill_type: str) -> str:
        """两类分流（001-02）：机械类 → 机械 printId；其余（辅材·集采类）→ 辅材 printId。

        ⚠️ printId 取值属 **待确认**（PRD 未给），一律从配置读、不写死。
        """
        _key = "i8_print_id_mechanical" if bill_type == "mechanical" else "i8_print_id_material"
        _env = self.i8_print_id_mechanical if bill_type == "mechanical" else self.i8_print_id_material
        pid = self._effective(_key, _env)
        if not pid:
            raise NotConfiguredError(
                "未配置对应单据类型的 printId"
                "（见 .env：I8_PRINT_ID_MECHANICAL / I8_PRINT_ID_MATERIAL）"
            )
        return pid


@lru_cache
def get_settings() -> Settings:
    return Settings()
