"""i8 真机契约探测 —— `API-01`（取数方式）· `API-07`（版式响应形态）。

⚠️ **会登录 i8**（登录含 `KillOnlineUser` 强踢，会挤掉该账号其他在线会话）——
   仅在**用户明确同意**时运行（D9）。
⚠️ 只读探测：**不改任何数据**（getList 是查询、getPrintDesign 是取模板）。

用法（在工程根）：
    backend/.venv/Scripts/python.exe tools/i8_contract_probe.py [YYYY-MM]

结论回写处：`ops/i8-接口契约-旁证摘要.md`（真机核验后把"旁证"升级为"实测"）。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_settings  # noqa: E402
from app.mod02_i8.client import I8Client  # noqa: E402

LIST_PATH = "/FC/FM/PaymentBill/getList"
DESIGN_PATHS = (
    "/reportcenter/printManage/getPrintDesign",
    "/api/reportcenter/printManage/getPrintDesign",
)
PRINT_IDS = {"其他支出": "3700000000000215", "付款通知书": "3700000000000203"}

# 素材包实测的固定表单（`profiles_payment_bill._LIST_FORM`）
LIST_FORM = {
    "busType": "PaymentBill", "pageId": "Web:PaymentBill",
    "isLoadHistory": "1", "relateId": "14", "inputSource": "2",
    "phidOrgList": "3700000000000014", "phidProjList": "", "dataKey": "",
    "saveTableName": "fc3_code_table", "payStatus": "0",
    "summaryCols": "ApplyAmtFc,ApplyAmt,ApproveAmtFc,ApproveAmt",
    "limit": "5", "page": "0", "start": "0",
}


def _line(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def _brief(v, n: int = 70):  # noqa: ANN001
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
    s = str(s).replace("\n", " ")
    return s[:n] + ("…" if len(s) > n else "")


def probe_list(client: I8Client, year_month: str) -> dict:
    """① `API-01`：**POST form + queryfilter** 是否可取到数。"""
    _line(f"① API-01 getList（POST form）· 核算月 = {year_month}")
    ge, le = f"{year_month}-01", f"{year_month}-31"
    qf = json.dumps({"queryFilter": json.dumps(
        {"BillDt*date*ge*1": ge, "BillDt*date*le*1": le}, ensure_ascii=False)}, ensure_ascii=False)
    form = dict(LIST_FORM, queryfilter=qf)
    resp = client.request(
        "POST", LIST_PATH, data=form,
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    print(f"status = {resp.status_code}  ct = {resp.headers.get('content-type')}")
    try:
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        print("非 JSON 响应：", _brief(resp.text, 200), "|", exc)
        return {"ok": False}
    print("顶层键 =", list(data)[:8] if isinstance(data, dict) else type(data).__name__)
    recs = (data or {}).get("Record") or []
    print("Record 条数 =", len(recs))
    if recs:
        keys = sorted(recs[0])
        print("字段名（sorted）：")
        for k in keys:
            print(f"    {k:34s} = {_brief(recs[0].get(k), 48)}")
    return {"ok": bool(recs), "count": len(recs), "keys": sorted(recs[0]) if recs else []}


def probe_design(client: I8Client) -> dict:
    """② `API-07`：版式响应的**真实形态**（HTML？还是模板 JSON？）。"""
    for path in DESIGN_PATHS:
        for label, pid in list(PRINT_IDS.items())[:1]:
            _line(f"② API-07 getPrintDesign · {label} · printId = {pid}")
            resp = client.request("GET", path, params={"printId": pid})
            print(f"path   = {path}")
            print(f"status = {resp.status_code}  ct = {resp.headers.get('content-type')}")
            txt = resp.text or ""
            print(f"body 长度 = {len(txt)}")
            try:
                data = resp.json()
            except Exception:  # noqa: BLE001
                print("非 JSON（可能是 HTML 或错误页）：", _brief(txt, 160))
                continue

            # ⭐ 命中素材包所说的形态（printSchema / printSetting 是 **JSON 字符串**）
            if isinstance(data, dict) and ("printSchema" in data or "printSetting" in data):
                print("★ 命中模板形态：", sorted(data))
                for k in ("printName", "printSchema", "printSetting"):
                    v = data.get(k)
                    if isinstance(v, str):
                        print(f"  {k}: str(len={len(v)}) head={_brief(v, 110)}")
                        try:
                            parsed = json.loads(v)
                            if isinstance(parsed, list) and parsed:
                                print(f"    → list[0] keys = {sorted(parsed[0])[:12]}")
                                cells = parsed[0].get("cells")
                                if isinstance(cells, list) and cells:
                                    print(f"    → cells = {len(cells)} 个；第 1 个 cell keys = {sorted(cells[0])}")
                                    print(f"    → cell[0] 摘要 = {_brief(cells[0], 220)}")
                                gs = parsed[0].get("globalSettings")
                                if isinstance(gs, dict):
                                    print(f"    → globalSettings keys = {sorted(gs)}")
                                    print(f"    → cols/rows = {gs.get('cols')}/{gs.get('rows')}")
                        except Exception as exc:  # noqa: BLE001
                            print("    ⚠️ json.loads 失败：", exc)
                    else:
                        print(f"  {k}: {type(v).__name__} = {_brief(v, 80)}")
                return {"ok": True, "path": path, "keys": sorted(data), "label": label, "printId": pid}

            print("顶层键 =", sorted(data)[:10] if isinstance(data, dict) else type(data).__name__)
            # ⭐ 外层是 `Data` 包着 ⇒ **深入一层**看真实结构（并解析其中的 JSON 字符串）
            inner = data.get("Data") if isinstance(data, dict) else None
            if isinstance(inner, dict):
                print("Data 的键：")
                for k in sorted(inner):
                    v = inner.get(k)
                    kind = type(v).__name__
                    size = len(v) if isinstance(v, (str, list, dict)) else ""
                    print(f"    {k:20s} {kind:6s} len={size}  {_brief(v, 90)}")
                for k, v in sorted(inner.items()):
                    if isinstance(v, str) and v.lstrip()[:1] in "[{":
                        try:
                            parsed = json.loads(v)
                        except Exception:  # noqa: BLE001
                            continue
                        print(f"  ★ {k} 可解析为 JSON（{type(parsed).__name__}）：")
                        first = parsed[0] if isinstance(parsed, list) and parsed else parsed
                        if isinstance(first, dict):
                            print(f"      [0] keys = {sorted(first)}")
                            for kk in sorted(first):
                                vv = first.get(kk)
                                print(f"        {kk:22s} {type(vv).__name__:6s} {_brief(vv, 80)}")
                return {"ok": True, "path": path, "keys": sorted(inner), "label": label, "printId": pid,
                        "shape": "Data", "inner_keys": sorted(inner)}
            print("摘要 =", _brief(data, 220))
            return {"ok": True, "path": path, "keys": sorted(data) if isinstance(data, dict) else [], "label": label, "printId": pid}

    print("\n⚠️ 两个候选路径都没拿到模板形态")
    return {"ok": False}


def main() -> int:
    year_month = sys.argv[1] if len(sys.argv) > 1 else "2026-08"
    s = get_settings()
    print("i8 base =", s.i8_base_url, "| user =", s.i8_user)
    print("⚠️ 即将登录（含 KillOnlineUser 强踢）")

    client = I8Client(allow_kick=True)
    try:
        out_list = probe_list(client, year_month)
        out_design = probe_design(client)
    finally:
        client.close()

    _line("结论摘要")
    print("① 取数（POST form）：", "成功，%d 条" % out_list["count"] if out_list.get("ok") else "**未取到**")
    print("② 版式形态：", ("命中模板 JSON（%s）" % out_design["label"]) if out_design.get("ok") else "**未确认**")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
