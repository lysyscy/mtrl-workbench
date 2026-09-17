"""统一错误出口 —— **必须显式报出**（禁静默失败）。

为什么单独立一个模块：多条验收判据是 **must-report** 型 —— 例如
「取不到版式须显式报错，不得静默产出空白件」「出纸失败须报出原因，禁止整批静默丢弃」
「批量中任一单据未产出，结束时须列出未出单号」（`ACC-PAY-PRINT-001` 的 `001-03/06/07/08`）。

⇒ 全站凡"该报出来的"一律抛本模块的异常，由 API 层统一转成响应；
**禁止**吞异常后返回空值/默认值。
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """业务可预期的错误基类。`message` 会原样呈给用户，务必写清"发生了什么"。"""

    code: str = "app_error"
    http_status: int = 400

    def __init__(self, message: str, *, detail: Any = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.detail is not None:
            payload["detail"] = self.detail
        return payload


class NotConfiguredError(AppError):
    """配置缺失（如未填 i8 地址 / 未填打印机地址）—— 属部署期问题，不该静默跳过。"""

    code = "not_configured"
    http_status = 500


class MustReportError(AppError):
    """**必须让用户看见**的错误：取不到版式 / 出纸失败 / 签名零命中 / 批内未产出。"""

    code = "must_report"


class ExternalServiceError(AppError):
    """外部依赖不可用（i8 接口 / 打印机 / 浏览器渲染）。"""

    code = "external_service"
    http_status = 502


class DataConflictError(AppError):
    """并发冲突（乐观锁 409 场景：手改分类等低频冲突）。"""

    code = "data_conflict"
    http_status = 409


class DataIntegrityError(AppError):
    """数据完整性冲突（唯一约束 / 引用悬空）—— 调用方不得吞掉。"""

    code = "data_integrity"
    http_status = 409
