"""`m01` 接线**真机端到端**自检（服务 ＋ **真库**）· 跑完把临时数据**清干净**。

为什么要有它：`tests/test_wired_m01.py` 是**静态**检查（壳里有没有接线点），
它**证明不了**"按下去真的落库"。本脚本走**真 HTTP ＋ 真库**，覆盖六件事：

1. 建档（临时壳 ＋ 2 个具体小微）→ 列表能取到、父子关系对得上
2. 改展示名（`disp`）→ 落库、**不留痕**
3. 改全名（`name_full`）→ 落库、**留痕**（改动人 = `科室用户` 占位，§三-3）
4. 改关键词（数组 ⇄ 竖线串）→ 落库
5. 排序（`to_position`）→ **全表 1..N 连续**
6. ⭐ 状态不变式**由后端判**：壳下有在建小微 ⇒ **拒绝归档**（原值保留、无留痕）；
   归档壳下**最后一个**在建小微 ⇒ 壳**自动跟着归档**

⚠️ 它**会写库**（只写自己建的临时行），结束前 `finally` 里删净 ＋ 重编号复原。
用法：服务在跑 ⇒ `python tools/_e2e_m01_wired.py`（从 `backend/` 或仓库根都能跑）。
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8000"
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

TAG = "【自检临时】"
fails: list[str] = []


def check(ok: bool, what: str, extra: str = "") -> None:
    print(("  ✅ " if ok else "  ⛔ ") + what + (f" —— {extra}" if extra else ""))
    if not ok:
        fails.append(what)


def main() -> int:
    from app.core.db import session_scope
    from app.mod01_projects import repository as repo
    from app.mod01_projects.domain import ordered

    c = httpx.Client(base_url=BASE, timeout=30.0)
    ids: list[int] = []

    print("① 建档（链路 A 的最小形态：壳 ＋ 2 个小微）")
    shell = c.post("/api/m01/projects", json={
        "project_type": "shell", "name_full": f"{TAG}自检壳全名", "disp": "自检壳",
    })
    check(shell.status_code == 200, "建壳 200", f"HTTP {shell.status_code} {shell.text[:80]}")
    if shell.status_code != 200:
        return 1
    sid = shell.json()["id"]
    ids.append(sid)

    kids = []
    for i, (wh, kw) in enumerate([("自检仓A", ["甲词"]), ("自检仓B", ["乙词"])], 1):
        r = c.post("/api/m01/projects", json={
            "project_type": "small", "name_full": f"{TAG}自检壳全名",
            "warehouse_name": wh, "parent_shell_id": sid, "match_keywords": kw,
        })
        check(r.status_code == 200, f"建小微{i} 200", f"HTTP {r.status_code}")
        if r.status_code == 200:
            kids.append(r.json()["id"])
            ids.append(r.json()["id"])

    rows = {p["id"]: p for p in c.get("/api/m01/projects?status=all").json()}
    check(all(i in rows for i in ids), "列表（status=all）能取到三行")
    check(rows[kids[0]]["parent_shell_id"] == sid, "小微的父壳 id 正确",
          f"{rows[kids[0]]['parent_shell_id']} vs {sid}")

    print("② 改展示名（可改 · 不留痕）")
    r = c.put(f"/api/m01/projects/{kids[0]}", json={"disp": "自检显示名"})
    check(r.status_code == 200 and r.json()["disp"] == "自检显示名", "展示名落库")
    logs = c.get(f"/api/m01/projects/{kids[0]}/logs").json()
    check(not logs, "改展示名**不留痕**（§9.3）", f"logs={len(logs)}")

    print("③ 改全名（可改 · 留痕 · 改动人 = 唯一出口）")
    r = c.put(f"/api/m01/projects/{kids[0]}", json={"name_full": f"{TAG}改后的全名"})
    check(r.status_code == 200 and r.json()["name_full"] == f"{TAG}改后的全名", "全名落库")
    logs = c.get(f"/api/m01/projects/{kids[0]}/logs").json()
    check(len(logs) == 1 and logs[0]["field"] == "name_full", "写了一条全名留痕")
    check(logs and logs[0]["changed_by"] == "科室用户",
          "改动人 = `current_operator()` 占位（不填真人名）", logs[0]["changed_by"] if logs else "")

    print("④ 改关键词（数组 ⇄ 竖线串）")
    r = c.put(f"/api/m01/projects/{kids[0]}", json={"match_keywords": ["甲词", "丙词", "甲词"]})
    got = r.json()["match_keywords"]
    check(got == ["甲词", "丙词"], "关键词落库并去重", str(got))

    print("⑤ 排序（填号 = 插到第 v 位；全表重编号 1..N）")
    r = c.put(f"/api/m01/projects/{ids[-1]}/ord", json={"to_position": 1})
    check(r.status_code == 200, "排序 200", f"HTTP {r.status_code} {r.text[:80]}")
    with session_scope() as s:
        seq = [p.ord for p in ordered(repo.all_projects(s))]
    check(seq == list(range(1, len(seq) + 1)), "序号连续无重复 1..N", str(seq))

    print("⑥ 状态不变式：**由后端判**")
    r = c.put(f"/api/m01/projects/{sid}/status", json={"status": "archived"})
    check(r.status_code == 400, "壳下还有在建小微 ⇒ 归档被拒（400）", f"HTTP {r.status_code}")
    msg = r.json().get("message", "") if r.headers.get("content-type", "").startswith("application/json") else r.text
    check("自检仓" in msg, "拒绝原因里**点名**了尚未归档的小微", msg[:90])
    still = {p["id"]: p for p in c.get("/api/m01/projects?status=all").json()}
    check(still[sid]["status"] == "active", "壳状态**原值保留**（没被改）")
    check(not c.get(f"/api/m01/projects/{sid}/logs").json(), "被拒时**不写留痕**")

    print("⑦ 归档壳下最后一个在建小微 ⇒ 壳自动跟着归档")
    c.put(f"/api/m01/projects/{kids[1]}/status", json={"status": "archived"})
    r = c.put(f"/api/m01/projects/{kids[0]}/status", json={"status": "archived"})
    check(r.status_code == 200, "归档最后一个小微 200")
    now = {p["id"]: p for p in c.get("/api/m01/projects?status=all").json()}
    check(now[kids[0]]["status"] == "archived", "小微已归档")
    check(now[sid]["status"] == "archived", "⭐ 壳**自动跟着归档**（不变式：壳归档 ⇔ 小微全归档）")
    slog = c.get(f"/api/m01/projects/{sid}/logs").json()
    check(any(x["field"] == "status" for x in slog), "壳自己也有状态留痕")

    print("⑧ 最近留痕（/api/m01/trails，新 → 旧）")
    tr = c.get("/api/m01/trails?limit=20").json()
    check(bool(tr) and all("field_label" in x for x in tr), "能取到留痕且带中文列名", f"{len(tr)} 条")
    check(any(TAG in x["project"] or "自检" in x["project"] for x in tr[:8]), "本次自检的留痕在最近几条里")

    return 1 if fails else 0


def cleanup() -> None:
    """删净自检产生的档案行与留痕，并把 `ord` 重编号复原（**失败也要跑**）。"""
    from sqlalchemy import delete, select

    from app.core.db import session_scope
    from app.mod01_projects import repository as repo
    from app.mod01_projects.domain import ordered
    from app.mod01_projects.models import Project, ProjectFieldLog

    with session_scope() as s:
        rows = [p for p in s.execute(select(Project)).scalars().all() if p.name_full.startswith(TAG)]
        ids = [p.id for p in rows]
        if ids:
            s.execute(delete(ProjectFieldLog).where(ProjectFieldLog.project_id.in_(ids)))
            s.execute(delete(Project).where(Project.id.in_(ids)))
            s.flush()
        for i, p in enumerate(ordered(repo.all_projects(s)), 1):     # 全表重编号复原
            p.ord = i
        s.flush()
    print(f"  🧹 已清理临时档案行 {len(ids)} 行 ＋ 其留痕，`ord` 已重编号复原")


if __name__ == "__main__":
    try:
        rc = main()
    finally:
        cleanup()
    print("\n结论：" + ("✅ 端到端全通" if rc == 0 else f"⛔ {len(fails)} 项未通过"))
    sys.exit(rc)
