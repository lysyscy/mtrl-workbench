"""真机端到端自检：付款计划的「强制通过」走一遍完整链路（**需要服务在跑**）。

为什么留着它（2026-09-17 的教训）：本轮修的正是**离线断言看不见**的那类缺陷 ——
    · 端点参数声明为 `Query` 而表单提交的是 **body** ⇒ 真机 **422**（`pytest` 全绿也照样坏）；
    · PRG 端点的提交发生在**响应之后**（依赖清理时）⇒ 303 回跳的 GET **可能读到旧值**。
两者都只有"真的发一次请求 ＋ 真的查一次库"才能发现。

用法（先确保 `http://127.0.0.1:8000` 在跑）：
    backend/.venv/Scripts/python.exe tools/_e2e_plan_force.py

它会**插一行临时计划行 → 真机提交 → 查库 → 取消 → 查库 → 删掉临时行**，跑完不留痕迹。
"""

from __future__ import annotations

import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

import app.models_registry  # noqa: F401,E402  （ORM 脚本必须先注册全表）
from app.core.db import session_scope  # noqa: E402
from app.mod04_plan.models import PlanRow  # noqa: E402

BASE = "http://127.0.0.1:8000"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **kw):  # noqa: ANN002, ANN003
        return None


_opener = urllib.request.build_opener(_NoRedirect)


def post(path: str, data: dict) -> int:
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(BASE + path, data=body, method="POST")
    try:
        with _opener.open(req, timeout=20) as r:
            return int(r.status)
    except urllib.error.HTTPError as e:
        return int(e.code)


def show(row_id: int) -> tuple[bool, str]:
    with session_scope() as s:
        row = s.get(PlanRow, row_id)
        return (bool(row.forced_through), str(row.forced_remark or ""))


def main() -> int:
    with session_scope() as s:
        row = PlanRow(year_month="2026-09", project_input="端到端自检（临时行）",
                      match_status="unmatched", doc_no="", flow_amount=0, planned_amount=0, raw={})
        s.add(row)
        s.flush()
        rid = int(row.id)
    print(f"① 插入临时行 id={rid}")

    code = post("/m04/force", {"row_id": str(rid), "remark": "端到端自检：已向项目核实，金额无误"})
    st, remark = show(rid)
    ok1 = code == 303 and st and remark.startswith("端到端自检")
    print(f"② POST /m04/force ⇒ HTTP {code} · 库=({st}, {remark!r}) ⇒ {'✅' if ok1 else '❌'}")

    code = post("/m04/force", {"row_id": str(rid), "remark": "   "})
    st2, remark2 = show(rid)
    ok2 = code == 303 and st2 and remark2.startswith("端到端自检")     # 空备注 ⇒ **原值不动**
    print(f"③ 空备注 ⇒ HTTP {code} · 库仍是 ({st2}, {remark2!r}) ⇒ {'✅' if ok2 else '❌'}")

    code = post("/m04/force-cancel", {"row_id": str(rid)})
    st3, remark3 = show(rid)
    ok3 = code == 303 and st3 is False and remark3 == ""
    print(f"④ POST /m04/force-cancel ⇒ HTTP {code} · 库=({st3}, {remark3!r}) ⇒ {'✅' if ok3 else '❌'}")

    with session_scope() as s:
        s.delete(s.get(PlanRow, rid))
    print(f"⑤ 临时行 id={rid} 已删")

    good = ok1 and ok2 and ok3
    print(f"\n端到端结论：{'✅ 真机链路通' if good else '❌ 有一步不符'}")
    return 0 if good else 1


if __name__ == "__main__":
    sys.exit(main())
