"""侦察脚本：**两个版式模板** ＋ **两类单据的流程数据**（为"签名图绑定"与"双模板渲染"取证）。

⚠️ **会登录 i8**（含 KillOnlineUser 强踢）—— 仅在用户同意时运行（D9）。
⚠️ 只读：不打印、不写库。

它回答三件事：
1. *付款通知书*（printId=203）与 *其他支出*（215）两个模板的**结构差异**（尤其图片格与节点名）；
2. 模板图片格的 `dataFilter`「办理节点」值 ↔ 流程节点的**哪个字段**能对上（**不猜、用数据对照**）；
3. 流程节点的 `signature` 到底有没有值（有 ⇒ 可下载签名图）。

用法（工程根）：
    backend/.venv/Scripts/python.exe tools/i8_flow_probe.py [YYYY-MM]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.mod02_i8.client import I8Client  # noqa: E402
from app.mod02_i8.notice_source import NoticeDetailFetcher, NoticeFetcher  # noqa: E402
from app.mod03_notice.print.template import (  # noqa: E402
    extract_design_data,
    is_image_cell,
    node_of,
    parse_design,
)

DESIGN_PATH = "/reportcenter/printManage/getPrintDesign"
# 命名与 `tools/render_preview.py` 一致（样本只留一份，避免两份副本漂移）
TEMPLATES = (("其他支出", "3700000000000215", "i8_print_design_sample.json"),
             ("付款通知书", "3700000000000203", "i8_print_design_notice.json"))
FIXTURES = ROOT / "backend" / "tests" / "fixtures"

# 流程节点里**可能**承载"节点名"的字段（逐个对照打印，取真正对得上的那个）
NODE_NAME_CANDIDATES = ("actionname", "task_des", "nodeid", "username", "deptname", "cno")
# 可能承载签名图路径的字段
SIGN_CANDIDATES = ("signature", "signcode")


def grab_templates(client: I8Client) -> dict:
    out = {}
    for label, pid, fname in TEMPLATES:
        resp = client.request("GET", DESIGN_PATH, params={"printId": pid})
        data = extract_design_data(resp.json())
        FIXTURES.mkdir(parents=True, exist_ok=True)
        (FIXTURES / fname).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        tpl = parse_design(data)
        imgs = [(c["row"], c["col"], (c.get("cellData") or {}).get("fieldId"), node_of(c))
                for c in tpl.field_cells() if is_image_cell(c)]
        out[label] = tpl
        print(f"\n【模板】{label} · printId={pid} · printName={tpl.print_name}")
        print(f"  存样本 → {fname}（{len(json.dumps(data))} 字节）")
        print(f"  {tpl.cols} 列 × {tpl.rows} 行 · {len(tpl.cells)} 格 · 字段格 {len(tpl.field_cells())}")
        print(f"  图片格 {len(imgs)} 个（row,col,fieldId,办理节点名）：")
        for it in imgs:
            print("     ", it)
    return out


def show_flow(client: I8Client, rec: dict) -> None:
    det = NoticeDetailFetcher(client)
    info = det.fetch_info(rec["ph_id"])
    detail = det.fetch_detail(rec["ph_id"])
    flow = det.fetch_flow(rec["ph_id"])
    print(f"\n【单据】{rec['bill_no']} · 类型={rec['bill_type']} · 状态={rec['approve_status']}"
          f" · 明细 {len(detail)} 条 · 流程 {len(flow)} 节点")
    print(f"  单据头关键字段：PhidRecPayType_EXName={info.get('PhidRecPayType_EXName')!r}"
          f" · BillName={str(info.get('BillName'))[:30]!r}")
    print("  流程节点（序号 | 候选节点名字段 | 签名字段）：")
    for i, n in enumerate(flow, 1):
        names = {k: str(n.get(k) or "")[:16] for k in NODE_NAME_CANDIDATES}
        signs = {k: ("有(%d 字符)" % len(str(n.get(k))) if n.get(k) else "空") for k in SIGN_CANDIDATES}
        print(f"    {i:2d} {names}")
        print(f"       {signs}")


def main() -> int:
    ym = sys.argv[1] if len(sys.argv) > 1 else "2026-08"
    print(f"⚠️ 即将登录 i8（含强踢）· 取数月份 = {ym}")
    client = I8Client(allow_kick=True)
    try:
        grab_templates(client)

        rows = NoticeFetcher(client).fetch_month(ym)
        print(f"\n== {ym} 共 {len(rows)} 条 ==")
        mat = next((r for r in rows if r["bill_type"] == "material"), None)
        mech = next((r for r in rows if r["bill_type"] == "mechanical"), None)
        for tag, rec in (("material（→ 其他支出模板）", mat), ("mechanical（→ 付款通知书模板）", mech)):
            if rec is None:
                print(f"\n【{tag}】该月没有这种类型的单据"); continue
            print(f"\n================ {tag} ================")
            show_flow(client, rec)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
