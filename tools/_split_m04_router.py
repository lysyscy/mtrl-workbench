# -*- coding: utf-8 -*-
"""拆 `mod04_plan/router.py`（**668 行 > 600 禁合入硬线**）：把 `TAIL-35` 的 JSON 端点与两个项目辅助函数
摘到独立件，`router.py` 只留页面（PRG）端点并 `include_router` 汇总。

新增件（已写好）：`plan_api_router.py`（JSON 端点）· `project_views.py`（项目匹配视图 · **中立件**）。

用法：`cd D:\\dev\\mtrl-workbench && backend/.venv/Scripts/python.exe tools/_split_m04_router.py`
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTER = ROOT / "backend" / "app" / "mod04_plan" / "router.py"

src = ROUTER.read_bytes()
CRLF = b"\r\n" in src


def fit(text: str) -> bytes:
    b = text.encode("utf-8").replace(b"\r\n", b"\n")
    return b.replace(b"\n", b"\r\n") if CRLF else b


if fit("from app.mod04_plan.plan_api_router import router as api_router") in src:
    print("已是目标状态（已拆件）—— 无需重复执行")
    sys.exit(0)


def drop_block(text: bytes, start: str, stop_before: str) -> bytes:
    s, e = fit(start), fit(stop_before)
    i = text.find(s)
    if i < 0:
        raise SystemExit(f"⛔ 起点找不到：{start[:60]!r}")
    j = text.find(e, i)
    if j <= i:
        raise SystemExit(f"⛔ 终点不在起点之后：{stop_before[:60]!r}")
    return text[:i] + text[j:]


def sub1(text: bytes, old: str, new: str) -> bytes:
    o, n = fit(old), fit(new)
    c = text.count(o)
    if c != 1:
        raise SystemExit(f"⛔ 命中 {c} 次（应 1）：{old[:60]!r}")
    return text.replace(o, n)


before = len(src)

# ① 删我加的两个 JSON 端点（含 `PlanRowRequest`）—— 它们已搬到 `plan_api_router.py`
src = drop_block(src, "class PlanRowRequest(BaseModel):", '@router.get("/api/m04/delete-impact")')
print("① 摘出 JSON 端点段（PlanRowRequest + 两个端点）")

# ② 删 `_project_label`（已搬到 `project_views.py`）
src = drop_block(src, "def _project_label(session: Session, project_id: int) -> str:",
                 '\n@router.get("/m04/delete"')
print("② 摘出 `_project_label` → project_views")

# ③ 删 `_project_briefs`（已搬到 `project_views.py`）
src = drop_block(src, "def _project_briefs(session: Session) -> list[ProjectBrief]:",
                 '\n@router.get("/m04/import"')
print("③ 摘出 `_project_briefs` → project_views")

# ④ 调用点改新名（各自只剩 1 处 —— JSON 端点那两处已随①删掉）
src = sub1(src, 'values["project_input"] = _project_label(session, values["project_id"])',
           'values["project_input"] = project_label(session, values["project_id"])')
src = sub1(src, "rows = attach_projects(parsed.rows, _project_briefs(session))",
           "rows = attach_projects(parsed.rows, project_briefs(session))")
print("④ 调用点改新名（project_label / project_briefs）")

# ⑤ 加 import（放在既有 mod04 import 之后）＋ 汇总 API 路由
src = sub1(
    src, "from app.mod04_plan.plan_ui import (",
    "from app.mod04_plan.plan_api_router import router as plan_api_router\n"
    "from app.mod04_plan.project_views import project_briefs, project_label\n"
    "from app.mod04_plan.plan_ui import ("
)
src = sub1(src, 'router = APIRouter(tags=["mod04"])',
           'router = APIRouter(tags=["mod04"])\n'
           '# ⭐ 前端壳的 **JSON API**（`TAIL-35`：手动行 ＋ 导入）—— 独立路由件，由本文件汇总\n'
           'router.include_router(plan_api_router)')
print("⑤ import ＋ include_router")

# ⑥ `BaseModel` 已不再用（JSON 端点搬走了）⇒ 摘掉，免 lint
if fit("BaseModel") not in src.replace(fit("from pydantic import BaseModel"), b""):
    src = src.replace(fit("from pydantic import BaseModel\n"), b"")
    print("⑥ 摘掉不再使用的 `from pydantic import BaseModel`")

ROUTER.write_bytes(src)
lines = src.decode("utf-8").count("\n") + 1
print(f"\n完成：{len(src)} 字节 · **{lines} 行**（拆前 668 行）")
print("下一步：跑 pytest 与 tools/doc_audit.py（T5 应不再报红）")
