"""渲染**两个模板**的打印预览（模板驱动 + 签名图），给人肉眼判版式。

完整链路（只差最后一步不出纸）：
    getPrintDesign（按单据类型取版式） → getList / getInfo / getDetInfo / 流程
    → **生产同一个渲染入口** `service.render_notice_html`
      （内部再走 `print/fields.py` 值组装 + `print/signatures.py` 签名绑定 + `print/template.py` 模板渲染）
    → 落盘 HTML
⚠️ 本脚本**不自己组装**（曾与 `service` 各写一份 ⇒ 预览可能与实际打印不一致，2026-09-15 已收敛为同一个入口）。

⚠️ **会登录 i8**（含 KillOnlineUser 强踢）—— 仅在用户同意时运行（D9）。
⚠️ **不打印、不写库**。

用法（工程根）：
    backend/.venv/Scripts/python.exe tools/render_preview.py [YYYY-MM]
"""

from __future__ import annotations

from pathlib import Path as _WorkspacePath
import sys as _workspace_sys
_workspace_sys.path.insert(0, str(_WorkspacePath(__file__).resolve().parents[2] / 'tools/audit'))
from workspace_paths import output as _run_output, output_dir as _run_dir

import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_settings  # noqa: E402
from app.mod02_i8.client import I8Client  # noqa: E402
from app.mod02_i8.notice_source import NoticeDetailFetcher, NoticeFetcher  # noqa: E402
from app.mod03_notice.print.fields import uncovered_field_ids  # noqa: E402
from app.mod03_notice.print.signatures import (  # noqa: E402
    SignatureStore,
    bind_signatures,
    collect_signature_paths,
    signature_slots,
)
from app.mod03_notice.print.template import (  # noqa: E402
    extract_design_data,
    parse_design,
)
# ★ 渲染一律走**生产同一个入口**（预览看到的 = 实际印出来的），不在这里另写一份组装
from app.mod03_notice.service import render_notice_html  # noqa: E402

DESIGN_PATH = "/reportcenter/printManage/getPrintDesign"
OUT_DIR = ROOT / _run_dir()
FIXTURES = ROOT / "backend" / "tests" / "fixtures"
SIG_CACHE = ROOT / "var/cache/signatures"
BILL_TYPE_LABEL = {"material": "其他支出", "mechanical": "付款通知书"}


def fetch_design(client: I8Client, bill_type: str):
    """按单据类型取版式 → 解析成模板（顺带把样本更新到 fixtures）。"""
    settings = get_settings()
    print_id = settings.print_id_for_bill_type(bill_type)
    resp = client.request("GET", DESIGN_PATH, params={"printId": print_id})
    data = extract_design_data(resp.json())
    tpl = parse_design(data)
    name = f"i8_print_design_{'notice' if bill_type == 'mechanical' else 'sample'}.json"
    (FIXTURES / name).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return tpl, print_id, name


class _Prefetched:
    """把**已取好**的 info/detail/flow 包成 `DetailLike` —— 避免同一张单重复请求 i8。"""

    def __init__(self, info: dict, detail: list, flow: list) -> None:
        self._info, self._detail, self._flow = info, detail, flow

    def fetch_info(self, ph_id: str) -> dict:  # noqa: ARG002
        return self._info

    def fetch_detail(self, ph_id: str) -> list:  # noqa: ARG002
        return self._detail

    def fetch_flow(self, ph_id: str) -> list:  # noqa: ARG002
        return self._flow


def render_one(client: I8Client, rec: dict, store: SignatureStore) -> dict:
    """一条单据 → 渲染结果（HTML 落盘）。"""
    bill_type = rec["bill_type"]
    label = BILL_TYPE_LABEL.get(bill_type, bill_type)
    print(f"\n{'=' * 66}\n【{label}】{rec['bill_no']} · {rec['approve_status']}\n{'=' * 66}")

    tpl, print_id, fname = fetch_design(client, bill_type)
    det = NoticeDetailFetcher(client)
    info = det.fetch_info(rec["ph_id"])
    detail = det.fetch_detail(rec["ph_id"])
    flow = det.fetch_flow(rec["ph_id"])
    print(f"版式：printName={tpl.print_name} · printId={print_id} · {tpl.cols}列×{tpl.rows}行 · {len(tpl.cells)}格"
          f"（样本 → {fname}）")
    print(f"数据：getInfo {len(info)} 字段 · 明细 {len(detail)} 条 · 流程 {len(flow)} 节点")

    # ⚠️ 渲染调**生产同一个入口**（`service.render_notice_html`）：预览与实际打印同一条路径。
    #    这里仅额外算一份 bound 用于打印统计（同一个函数、同输入；签名图有缓存，成本可忽略）。
    notice = SimpleNamespace(ph_id=rec["ph_id"], fields=rec)
    signatures = bind_signatures(store, flow)                    # 仅用于下方统计
    html = render_notice_html(notice, tpl, _Prefetched(info, detail, flow), store)

    out = OUT_DIR / f"print_preview_{label}_{rec['bill_no']}.html"
    out.write_text(html, encoding="utf-8")
    # 存**原始数据快照**：以后调整渲染可直接离线重跑（不必再登录 i8 强踢）
    snapshot = OUT_DIR / f"preview_data_{rec['bill_no']}.json"
    snapshot.write_text(json.dumps(
        {"bill_no": rec["bill_no"], "bill_type": bill_type, "ph_id": rec["ph_id"],
         "print_id": print_id, "info": info, "detail": detail, "flow": flow},
        ensure_ascii=False, indent=1), encoding="utf-8")

    wanted = signature_slots(tpl)
    provided = collect_signature_paths(flow)
    hit = [n for n in wanted if signatures.get(n)]
    missing = [n for n in wanted if not signatures.get(n)]
    print(f"渲染：{html.count('<td')} 个 td · 表格宽 {html.split('width:')[1].split('px')[0]}px → {out.name}")
    print(f"未覆盖的字段格 = {uncovered_field_ids(tpl) or '无'}")
    print(f"签名格要 {len(wanted)} 个节点：命中 {len(hit)} 个 · 未命中 {len(missing)} 个")
    print(f"   命中：{hit}")
    print(f"   未命中：{missing}（其中「流程里根本没有该节点」= {[n for n in missing if n not in provided]}）")
    print(f"   流程提供的节点名：{sorted(provided)}")
    return {"bill_no": rec["bill_no"], "label": label, "html": out, "hit": len(hit),
            "wanted": len(wanted), "uncovered": uncovered_field_ids(tpl)}


def main() -> int:
    ym = sys.argv[1] if len(sys.argv) > 1 else "2026-08"
    print(f"⚠️ 即将登录 i8（含强踢）· 取数月份 = {ym}")
    client = I8Client(allow_kick=True)
    try:
        rows = NoticeFetcher(client).fetch_month(ym)
        if not rows:
            print("该月没有单据"); return 1
        store = SignatureStore(client, cache_dir=SIG_CACHE)
        results = []
        for bill_type in ("material", "mechanical"):
            rec = next((r for r in rows if r["bill_type"] == bill_type), None)
            if rec is None:
                print(f"\n（{ym} 没有 {BILL_TYPE_LABEL[bill_type]} 类型的单据，跳过）"); continue
            results.append(render_one(client, rec, store))
    finally:
        client.close()

    print(f"\n{'=' * 66}\n汇总\n{'=' * 66}")
    for r in results:
        print(f"  {r['label']}｜{r['bill_no']}｜签名 {r['hit']}/{r['wanted']}｜"
              f"未覆盖字段 {r['uncovered'] or '无'}｜{r['html']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
