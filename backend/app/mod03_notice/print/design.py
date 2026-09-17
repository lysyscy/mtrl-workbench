"""取版式（`API-07` getPrintDesign）—— ⚠️ **取回的是版式模板，不是 HTML**。

依据（《说明书》§4.6 / `DEV-P-07` / `API-07`）：
- **版式一律取自 i8**（`getPrintDesign`），**本地只渲染与出纸，不得自行设计版式**（001-01）。
- **按单据类型走对应版式（两类分流）**（001-02）：机械类 / 辅材·集采类 → 各自 printId。
- **取不到对应版式 ⇒ 显式报错，不得静默产出空白件**（001-03）。

## 契约（**2026-09-15 真机复核**，不再是揣测）

响应 = `{"Status","Code","Msg","Data"}` ⇒ 模板在 **`Data`** 里：
`printSchema`（JSON 串 → `cells[]` ＋ `globalSettings{cols,rows,widths,heights}`）·
`printSetting`（JSON 串 → `printConfig{page,margin}`）· `dataSetInfos`。

⇒ 解析与渲染交给页面件 `print/template.py`（`extract_design_data` ＋ `parse_design`）；
  本模块**只负责按类型取回** ＋ **形状不对就显式报错**。
  ⚠️ 历史上这里曾假设"响应是 HTML、本地做占位符替换"—— **已被真机证伪**（响应里没有 HTML）。
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import I8_PATH_PRINT_DESIGN, get_settings, i8_base_of, i8_endpoint_of
from app.core.errors import MustReportError, NotConfiguredError
from app.mod02_i8.client import I8Client, serialize_fetch
from app.mod03_notice.print.template import PrintTemplate, extract_design_data, parse_design


class DesignFetcher:
    """按单据类型取 i8 版式（返回**模板对象**）。

    `client` 注入（生产用 `I8Client`，测试用桩）—— 满足"取版式来自 i8、不自绘"（001-01）。
    """

    def __init__(self, client: I8Client) -> None:
        self._client = client

    def fetch(self, bill_type: str) -> "PaymentNoticeDesign":
        settings = get_settings()
        if not i8_base_of(settings):
            raise NotConfiguredError("i8 服务地址未配置（见 .env 的 I8_BASE_URL，或到「设置」页填写）")
        print_id = settings.print_id_for_bill_type(bill_type)  # 两类分流（001-02）

        # 同表串行（D9：版式抓取也按表互斥）
        with serialize_fetch("print_design"):
            resp = self._client.get_json(
                i8_endpoint_of(settings, I8_PATH_PRINT_DESIGN), params={"printId": print_id}
            )

        try:
            tpl = parse_design(extract_design_data(resp))
        except MustReportError as exc:
            # 001-03：取不到版式 ⇒ 显式报错，禁止静默产出空白件
            raise MustReportError(
                f"取不到单据类型「{bill_type}」对应的版式（printId={print_id}）：{exc} "
                "已停止打印，未产出空白件。"
            ) from exc
        return PaymentNoticeDesign(bill_type=bill_type, print_id=print_id, tpl=tpl)


@dataclass
class PaymentNoticeDesign:
    """一份从 i8 取回的版式**模板**（本地只渲染、不修改其业务内容、也不自存）。"""

    bill_type: str
    print_id: str
    tpl: PrintTemplate


__all__ = ["DesignFetcher", "PaymentNoticeDesign"]
