"""i8 已有浏览器会话的**严格复用**验证入口（默认只打印计划，不连 i8、不发任何请求）。

用途：在当次现场有一个**已核身份的 i8 业务会话**时，沿既有取数与解析链做一次
**单号精确**的只读查询，核对业务结果，并证明本次没有登录、没有顶号、没有把会话落盘。

边界（本入口一律照做，不设开关）：

- 会话材料**只从标准输入**读（`--execute` 时），不读文件、不读环境变量、不打印、不落盘。
- 目标站点必须与产品配置的 i8 服务地址一致，否则**一条请求都不发**就退出；
  每条实际请求的目的地与重定向同样受约束（跳转即停止，会话不被带去未核实的地址）。
- 会话失效即停止；**不重登、不强踢、不写产品 Cookie 缓存**。
- 只支持单号精确查（最小代表）；不做列表全量、不做任何写操作、不做打印/导出。
- 输出只含**具名必要核对字段**与受控的停止类别：不打印原始行、不打印任意异常原文、
  不打印响应片段；站点只打印协议 / 主机 / 端口。

用法（示例，`<...>` 处由当次操作者提供）：

    # 1) 只看计划：不连 i8、不读任何会话材料
    python -B -X utf8 tools/dev/i8_browser_session_reuse.py --plan

    # 2) 严格复用一次（会话材料经标准输入喂入，不落盘）
    python -B -X utf8 tools/dev/i8_browser_session_reuse.py --execute --bill-no FKTZS2026090001

    # 3) 拿不到可导出的 Cookie 时，注入一个转发到宿主浏览器的传输适配
    python -B -X utf8 tools/dev/i8_browser_session_reuse.py --execute --bill-no ... \\
        --transport my_adapter:build

退出码：0 = 响应解析完成且单号一致、字段齐全（**不等于**整体真实复用验收通过）；
2 = 按边界停止（未验证）；1 = 其它失败（已脱敏的类别名）。

会话从哪来：本入口**只用**调用方注入的一份临时会话材料 —— Cookie 头（若确实拿得到）
或一个转发到宿主浏览器的 `httpx.BaseTransport`。它**不自带**浏览器通道实现，
所以"通道已接线"这件事只能在真实已登录会话跑通后另行声明，不能由本文件的存在推断。
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

#: 判"这张单被解析出来了"的最小字段集。**只说明响应解析完整**，不说明账号/组织正确。
REQUIRED_FIELDS: tuple[str, ...] = ("ph_id", "bill_no", "project_name", "approve_status")

#: 允许出现在输出里的具名核对字段（等价于"把原始行裁到这几个键"，不外泄其余字段）。
REPORT_FIELDS: tuple[str, ...] = (
    "bill_no",
    "ph_id",
    "project_name",
    "approve_status",
    "doc_date",
    "amount_approved",
)

#: 受控的停止类别（输出用固定词，不用异常类名或原始报错）。
_STOP_LABELS: dict[str, str] = {
    "i8_strict_session_unavailable": "没有可复用的会话材料（未发请求）",
    "i8_strict_target_mismatch": "会话站点与配置不一致（未发请求）",
    "i8_strict_redirect_stopped": "i8 要求跳转，已停止（未跟随）",
    "i8_strict_session_ended": "会话在 i8 侧已失效（未重登、未强踢）",
    "not_configured": "i8 服务地址未配置（未发请求）",
    "external_service": "i8 那边的这次取数没成功（未重登、未强踢）",
    "data_conflict": "与当前配置冲突，已停止",
    "app_error": "取数未成功（受控类别）",
}


#: 本入口**没有**内置任何浏览器通道实现（不新造服务、不猜端点、不复制浏览器配置）。
#: 下面这段是给"接线人"的最小契约：满足它就能作为一个 `--transport` 传进来；
#: 它**不等于**已经接线成功 —— 没有真实已登录会话跑通之前，通道始终是"未接线"。
_CHANNEL_CONTRACT: tuple[str, ...] = (
    "浏览器通道的最小契约（用一个 httpx.BaseTransport 实现，经 --transport 模块:函数 传入）：",
    "  · handle_request(request) → httpx.Response：把这条请求送到宿主浏览器里**同一个** i8 会话上发出；",
    "  · 会话留在浏览器里（同源页面 fetch 自动带 Cookie / 或等价通道），本入口不要求、也不假定 Cookie 可导出；",
    "  · 不自行跟随重定向、不重试、不登录、不写任何会话文件：3xx 必须原样返回，由本入口判为停止；",
    "  · 拿不到可判读响应时（例如浏览器只给不透明响应）必须让本次调用失败，不许伪装成 200；",
    "  · 不打印/不记录 Cookie、Authorization 或响应原文；",
    "  · 只接受与本入口相同的 i8 站点（httpx.Client 已带 base_url，通道不该改指别处）。",
    "⛔ 当前未接入任何真实通道（现场无已登录业务会话）：这一项按「未验证」记，不能当成已可复用。",
)


def _plan() -> int:
    print("严格复用入口：本次只打印计划，**未连接 i8、未发任何请求**。")
    print("  · 会话来源：标准输入的一份临时会话材料（Cookie 头 与/或 传输适配）")
    print("  · 目标校验：会话站点与每条请求目的地都必须等于产品配置的 i8 服务地址，否则不发请求")
    print("  · 跳转处理：不跟随重定向，跳转即停止（会话不被带去未核实的地址）")
    print("  · 查询范围：单号精确查（limit=5），沿既有付款通知书解析链")
    print("  · 失效处理：立即停止（不重登、不强踢、不写 Cookie 缓存）")
    print("  · 输出内容：仅具名核对字段 + 受控停止类别；不打印原始行/异常原文/响应片段")
    print("  · 判据边界：退出 0 只代表「响应解析完成且单号一致」，**不代表**账号/组织/页面对象已核")
    print("  · 浏览器通道：本入口不自带实现，最小契约见下；未接线 ⇒ 该项按未验证记")
    for line in _CHANNEL_CONTRACT:
        print(f"    {line}")
    print("⇒ 条件具备后加 --execute --bill-no <单号> 再跑。")
    return 0


def _read_session_from_stdin() -> dict:
    raw = sys.stdin.read()
    if not raw.strip():
        raise ValueError("标准输入里没有会话材料（--execute 需要一份临时会话材料）")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # ⛔ 不回显解析器原文（可能带出输入片段）：只给固定提示与位置无关的说明。
        raise ValueError("会话材料不是合法 JSON（未回显内容；请检查格式：站点地址 / Cookie 头 / 声明目标）") from None
    if not isinstance(data, dict):
        raise ValueError("会话材料须是一个 JSON 对象")
    return data


def _load_transport(spec: str):
    module_name, _, attr = spec.partition(":")
    if not module_name or not attr:
        raise ValueError("--transport 要写成 模块:函数 的形式")
    module = importlib.import_module(module_name)
    factory = getattr(module, attr)
    return factory()


def _report(row: dict) -> dict:
    """只把具名核对字段放进输出（不外泄原始行的其余内容）。"""
    return {key: row.get(key) for key in REPORT_FIELDS if key in row}


def _print_facts(facts: dict) -> None:
    print(json.dumps(facts, ensure_ascii=False, indent=2))


def _stop(code: str, message: str, facts: dict) -> int:
    print(f"已按边界停止：{_STOP_LABELS.get(code, '受控停止')}。")
    print(message)
    _print_facts(facts)
    return 2


def _run(args: argparse.Namespace) -> int:
    if str(ROOT / "backend") not in sys.path:
        sys.path.insert(0, str(ROOT / "backend"))

    from app.core.errors import AppError
    from app.mod02_i8.browser_session import (
        I8BrowserSessionClient,
        ReusedBrowserSession,
        StrictSessionUnavailable,
        StrictTargetMismatch,
        strict_payment_notice_by_bill_no,
    )

    material = _read_session_from_stdin()
    transport = _load_transport(args.transport) if args.transport else None
    try:
        session = ReusedBrowserSession(
            base_url=str(material.get("base_url") or ""),
            cookie_header=str(material.get("cookie_header") or ""),
            transport=transport,
            declared_target=str(material.get("declared_target") or ""),
        )
    except StrictSessionUnavailable:
        print("已按边界停止：这份会话材料不完整（缺站点地址或没有任何会话通道），未发出任何请求。")
        return 2
    client = I8BrowserSessionClient(session)
    try:
        row = strict_payment_notice_by_bill_no(client, args.bill_no)
    except AppError as exc:
        return _stop(exc.code, exc.message, client.facts())
    finally:
        client.close()

    facts = client.facts()
    if row is None:
        print("没查到这张单：可能是单号不对、或该会话看不到这张单 —— **不算复用成功**。")
        _print_facts(facts)
        return 2

    report = _report(row)
    missing = [key for key in REQUIRED_FIELDS if not row.get(key)]
    same_bill = str(row.get("bill_no") or "").strip() == args.bill_no.strip()
    print(json.dumps({"facts": facts, "checked": report}, ensure_ascii=False, indent=2))
    if missing or not same_bill:
        print(f"核对未完成：缺字段 {missing}、单号一致={same_bill}")
        return 2
    print("响应解析完成：单号一致、具名字段齐全；本次未登录、未强踢、未写产品会话缓存、未跟随跳转。")
    print("⚠️ 以上**只**证明解析链跑通；账号 / 组织 / 页面对象是否与声明的目标一致，仍须人工交叉核对。")
    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="i8 已有浏览器会话的严格复用验证入口（只读 · 单号精确查）")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true", help="只打印计划，不连 i8、不发请求")
    mode.add_argument("--execute", action="store_true", help="按严格边界真实复用一次（需 --bill-no）")
    parser.add_argument("--bill-no", default="", help="要精确查的付款通知书单号")
    parser.add_argument("--transport", default="", help="可选：模块:函数，返回一个转发到宿主浏览器的传输适配")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.plan:
        return _plan()
    if not args.bill_no.strip():
        print("--execute 需要 --bill-no <单号>：本入口只做单号精确查。", file=sys.stderr)
        return 2
    try:
        return _run(args)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001
        # ⛔ 不打印任意异常原文：只给类别名与固定提示（诊断细节走运行日志，不进证据）。
        print(f"入口自身失败（类别 {type(exc).__name__}）：未取得可用结果，按未验证处理。", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
