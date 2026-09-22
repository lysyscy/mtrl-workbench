"""① 验证「改成 POST form 后能真抓到数」＋ ② 取一份**真实版式模板**存为测试样本。

⚠️ **会登录 i8**（含 KillOnlineUser 强踢）—— 仅在用户明确同意时运行（D9）。
⚠️ 只读：不写库、不打印（只取数与取样）。

用法（工程根）：
    backend/.venv/Scripts/python.exe tools/i8_fetch_smoke.py [YYYY-MM]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_settings  # noqa: E402
from app.mod02_i8.client import I8Client  # noqa: E402
from app.mod02_i8.notice_source import NoticeFetcher  # noqa: E402

FIXTURE = ROOT / "backend" / "tests" / "fixtures" / "i8_print_design_sample.json"
DESIGN_PATH = "/reportcenter/printManage/getPrintDesign"
PRINT_ID = "3700000000000215"      # 其他支出


def main() -> int:
    ym = sys.argv[1] if len(sys.argv) > 1 else "2026-08"
    s = get_settings()
    print("i8 base =", s.i8_base_url, "| 通知 URL =", s.i8_payment_notice_url)
    print("⚠️ 即将登录（含强踢）")

    client = I8Client(allow_kick=True)
    try:
        # ---------- ① 新取数方式（POST form）端到端 ----------
        rows = NoticeFetcher(client).fetch_month(ym)
        print(f"\n① fetch_month({ym}) → {len(rows)} 条")
        if rows:
            r0 = rows[0]
            for k in ("ph_id", "bill_no", "doc_date", "project_name", "bill_type",
                      "approve_status", "amount_approved", "biz_type", "payee", "input_by"):
                print(f"    {k:16s} = {str(r0.get(k))[:60]}")
            from collections import Counter
            print("    单据类型分布 =", dict(Counter(r["bill_type"] for r in rows)))
            print("    审批状态分布 =", dict(Counter(r["approve_status"] for r in rows)))

        # ---------- ② 取一份真实版式（做成测试样本） ----------
        resp = client.request("GET", DESIGN_PATH, params={"printId": PRINT_ID})
        payload = resp.json()
        data = payload.get("Data") or {}
        keep = {k: data.get(k) for k in
                ("printId", "printName", "printSchema", "printSetting",
                 "sheetProperty", "dataSetInfos", "workflowHistorySetting", "globalProperty")}
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(json.dumps(keep, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n② 版式样本已存：{FIXTURE.name}（{FIXTURE.stat().st_size} 字节）")
        print("   键 =", sorted(keep))
        # 顺带看一下模板里**不含业务数据**（只含占位符）——决定能不能入库
        schema = json.loads(keep["printSchema"])[0]
        cells = schema["cells"]
        print(f"   cells = {len(cells)} 个 · sheetName = {schema.get('sheetName')}")
        texts = [c.get("cellData", {}).get("value") for c in cells
                 if c.get("cellType") == "text" and isinstance(c.get("cellData"), dict)]
        print("   静态文本前 12 个 =", [t for t in texts if t][:12])
        fields = [c.get("cellData", {}) for c in cells if c.get("cellType") == "field"]
        print(f"   字段格（cellType=field）= {len(fields)} 个；前 6 个 fieldId =",
              [f.get("fieldId") for f in fields[:6]])
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
