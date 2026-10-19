"""按 **单据号** 取数 → 取版式 → 渲染 PDF → （可选）**IPP 出纸**。

用途：① 真机打印件对照（一次只打指定的几张）② 排障时"只想打这一张"。
⚠️ 与 `render_preview.py` 的分工：那个**按月**抓一批、**只渲染不出纸**；本工具**按单号**、**可选出纸**。
⚠️ 两者**共用同一个渲染入口** `service.render_notice_html`（预览 = 实印，不各写一份组装）。

⚠️ **会登录 i8**（含 `KillOnlineUser` 强踢，D9）—— 仅在你明确同意时运行。
⚠️ **会往打印机投递真实作业**（除非给 `--no-print`）。

用法（工程根）：
    # ① 只识别 + 渲染，不出纸
    backend/.venv/Scripts/python.exe tools/print_bills.py --no-print FKTZS2026090466 FKTZS2026090465 ...
    # ② 出纸；并**校验识别结果**（分类与预期不符则**不出纸**，只报告）
    backend/.venv/Scripts/python.exe tools/print_bills.py --expect material=2 --expect mechanical=2 FKTZS... ...

产物：`artifacts/pdf/<时间戳>/<单号>.pdf`（**先落盘、再出纸** —— 出纸失败也留得下可复核的件）。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_settings  # noqa: E402
from app.mod02_i8.client import I8Client  # noqa: E402
from app.mod02_i8.notice_source import (  # noqa: E402
    EMPTY_RETRY, EMPTY_RETRY_SLEEP, LIST_FORM, NoticeDetailFetcher, _map_record,
)
from app.mod03_notice.print.design import DesignFetcher  # noqa: E402
from app.mod03_notice.print.ipp import send_pdf  # noqa: E402
from app.mod03_notice.print.render import PdfRenderer  # noqa: E402
from app.mod03_notice.print.signatures import (  # noqa: E402
    SignatureStore, bind_signatures, check_signature_coverage, signature_slots,
    unresolved_image_slots,
)
from app.mod03_notice.service import render_notice_html  # noqa: E402

OUT_DIR = ROOT / "exports/pdf"
SIG_CACHE = ROOT / "var/cache/signatures"
LABEL = {"material": "其他支出", "mechanical": "付款通知书"}


def query_one(client: I8Client, bill_no: str, *, retries: int = EMPTY_RETRY) -> dict:
    """按**单据号精查**一张（⚠️ 不走全量列表：全量 44.9s vs 精确 0.3s）。

    依据 = `技术栈选型分析` §9.2 的"单张精确查"：`queryfilter` 用 `BillNo*string*eq*1`；
    **空结果要再确认一次**（i8 偶发"有效但空"，不确认就会误判成"单据不存在"）。
    """
    import time

    settings = get_settings()
    qf = json.dumps(
        {"queryFilter": json.dumps({f"BillNo*string*eq*1": bill_no}, ensure_ascii=False)},
        ensure_ascii=False,
    )
    form = {**LIST_FORM, "queryfilter": qf, "limit": "5"}
    for attempt in range(retries + 1):
        resp = client.post_json(settings.i8_payment_notice_url, data=form)
        records = resp.get("Record") if isinstance(resp, dict) else None
        if records or attempt >= retries:
            return records[0] if records else {}
        print(f"    （{bill_no} 首次回空 —— 再确认一次）")
        time.sleep(EMPTY_RETRY_SLEEP)
    return {}


def one_bill(client, bill_no: str, det, store, renderer: PdfRenderer, outdir: Path) -> dict:
    """一张单据的完整链路（**只渲染、不投递** —— 投递由调用方统一在闸门之后做）。"""
    row_out: dict = {"bill_no": bill_no, "ok": False, "reason": ""}
    rec = query_one(client, bill_no)
    if not rec:
        row_out["reason"] = "i8 查不到该单号（已确认一次）"
        return row_out

    mapped = _map_record(rec) or {}
    bill_type = mapped.get("bill_type") or "material"
    ph_id = mapped.get("ph_id") or ""

    design = DesignFetcher(client).fetch(bill_type)          # 001-01/02/03（取不到即抛错）
    info, detail = det.fetch_info(ph_id), det.fetch_detail(ph_id)
    flow = det.fetch_flow(ph_id)

    notice = SimpleNamespace(ph_id=ph_id, fields=rec)
    html = render_notice_html(notice, design.tpl, det, store)   # ★ 唯一渲染入口
    pdf = renderer.render_html_to_pdf(html)

    pdf_path = outdir / f"{bill_no}.pdf"
    pdf_path.write_bytes(pdf)
    # 留存 **HTML 与原始数据快照** ⇒ 以后调渲染/SVG 可直接离线重跑（不必再登录 i8 强踢）
    (outdir / f"{bill_no}.html").write_text(html, encoding="utf-8")
    (outdir / f"{bill_no}.json").write_text(json.dumps(
        {"bill_no": bill_no, "ph_id": ph_id, "bill_type": bill_type,
         "print_id": design.print_id, "info": info, "detail": detail, "flow": flow},
        ensure_ascii=False, indent=1), encoding="utf-8")

    bound = bind_signatures(store, flow)
    cov = check_signature_coverage(design.tpl, flow, bound)

    row_out.update({
        "ok": True, "ph_id": ph_id, "bill_type": bill_type,
        "type_raw": str(rec.get("PhidRecPayType_EXName") or ""),
        "print_name": design.tpl.print_name, "print_id": design.print_id,
        "detail": len(detail), "flow": len(flow),
        "slots": len(signature_slots(design.tpl)), "filled": len(cov.filled),
        "missing": cov.missing, "blank": cov.blank_by_design,
        "unresolved": len(unresolved_image_slots(design.tpl)),
        "html_bytes": len(html), "pdf": pdf_path,
    })
    return row_out


def main() -> int:
    ap = argparse.ArgumentParser(description="按单号取数→渲染→出纸")
    ap.add_argument("bill_nos", nargs="+", help="单据号（可多个）")
    ap.add_argument("--no-print", action="store_true", help="只渲染落盘，不出纸")
    ap.add_argument("--expect", action="append", default=[],
                    metavar="TYPE=N", help="识别校验（如 --expect material=2）；不符则不出纸")
    args = ap.parse_args()

    settings = get_settings()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    outdir = OUT_DIR / stamp
    outdir.mkdir(parents=True, exist_ok=True)

    print("=" * 78)
    print("按单号打印 · 共 %d 张 · 出纸 = %s" % (len(args.bill_nos), "否" if args.no_print else "是"))
    print("⚠️ 即将登录 i8（含 KillOnlineUser 强踢）· 打印机 = %s" % (settings.printer_ipp_url or "未配置"))
    print("产物目录 = %s" % outdir)
    print("=" * 78)

    client = I8Client(allow_kick=True)
    rows: list[dict] = []
    renderer = PdfRenderer()
    try:
        det = NoticeDetailFetcher(client)
        store = SignatureStore(client, cache_dir=SIG_CACHE)
        for bill_no in args.bill_nos:
            print("\n---- %s ----" % bill_no)
            try:
                r = one_bill(client, bill_no, det, store, renderer, outdir)
            except Exception as exc:                      # noqa: BLE001
                r = {"bill_no": bill_no, "ok": False,
                     "reason": "%s: %s" % (type(exc).__name__, exc)}
            rows.append(r)
            if r["ok"]:
                print("  识别：i8「%s」→ bill_type=%s → 版式「%s」(printId=%s)"
                      % (r["type_raw"], r["bill_type"], r["print_name"], r["print_id"]))
                print("  数据：明细 %d 条 · 流程 %d 节点 · 签名槽位 %d" % (r["detail"], r["flow"], r["slots"]))
                print("  签名：**命中 %d** ｜ 该留空（流程未走到）%d %s ｜ ⚠️该印没印（流程有、图没取到）%d %s ｜ 认不出 %d"
                      % (r["filled"], len(r["blank"]), r["blank"] or "",
                         len(r["missing"]), r["missing"] or "", r["unresolved"]))
                print("  产物：%s（%.1f KB）＋ 同名 .html / .json 快照" % (r["pdf"].name, len(r["pdf"].read_bytes()) / 1024))
            else:
                print("  ✗ %s" % r["reason"])

        # ---------------- 识别汇总 ----------------
        print("\n" + "=" * 78)
        print("识别汇总")
        print("-" * 78)
        print("%-18s %-12s %-10s %-14s %-6s %-6s %s"
              % ("单号", "i8 收付款类型", "bill_type", "版式", "槽位", "命中", "结果"))
        for r in rows:
            if r["ok"]:
                print("%-18s %-12s %-10s %-14s %-6d %-6d %s"
                      % (r["bill_no"], r["type_raw"], r["bill_type"], r["print_name"],
                         r["slots"], r["filled"], "已渲染"))
            else:
                print("%-18s %-12s %-10s %-14s %-6s %-6s ✗ %s"
                      % (r["bill_no"], "—", "—", "—", "—", "—", r["reason"]))

        counts: dict[str, int] = {}
        for r in rows:
            if r["ok"]:
                counts[r["bill_type"]] = counts.get(r["bill_type"], 0) + 1
        print("-" * 78)
        print("识别结果统计：" + ("· ".join(
            "%s(%s)=%d" % (LABEL.get(k, k), k, v) for k, v in sorted(counts.items())) or "无"))

        # ---------------- 识别校验闸（不符则不出纸）----------------
        expected = {}
        for spec in args.expect:
            k, _, v = spec.partition("=")
            expected[k.strip()] = int(v)
        if expected and counts != expected:
            print("\n⛔ **识别校验不通过** —— 预期 %s，实际 %s ⇒ **不出纸**（只报告）。"
                  % (expected, counts))
            print("   请复核 printId 分流（《说明书》§4.6「版式分流」/ 技术栈 §9.5）。")
            return 2
        if expected:
            print("✅ 识别校验通过（%s）" % counts)

        failed = [r for r in rows if not r["ok"]]
        if failed:
            print("\n⚠️ 未出单号（%d 张）：%s" % (len(failed), [r["bill_no"] for r in failed]))

        # ---------------- 出纸 ----------------
        if args.no_print:
            print("\n（--no-print）已跳过出纸。PDF 在：%s" % outdir)
            return 0

        ok_rows = [r for r in rows if r["ok"]]
        print("\n" + "=" * 78)
        print("开始出纸（IPP 直投 %s）" % settings.printer_ipp_url)
        print("-" * 78)
        for r in ok_rows:
            try:
                send_pdf(r["pdf"].read_bytes(), settings.printer_ipp_url)
                print("  ✅ %s → 已投递打印机" % r["bill_no"])
            except Exception as exc:                      # noqa: BLE001
                r["reason"] = "%s: %s" % (type(exc).__name__, exc)
                print("  ❌ %s → 出纸失败：%s" % (r["bill_no"], r["reason"]))

        unprinted = [r["bill_no"] for r in rows if not r["ok"] or r.get("reason")]
        print("-" * 78)
        print("已投递 %d 张 · 未出 %s" % (len(ok_rows) - len(unprinted), unprinted or "无"))
        print("PDF 全在：%s" % outdir)
        return 0
    finally:
        try:
            renderer.close()
        finally:
            client.close()


if __name__ == "__main__":
    raise SystemExit(main())
