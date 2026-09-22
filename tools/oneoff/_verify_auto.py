"""一次性验证脚本（真机）：**链路 B 自动建档**是否真的在抓取里生效。

为什么必须真机：离线断言用的是假 client / 假会话 ⇒ 只能证明"逻辑对"，
证不了"抓 i8 时真的会建"。本轮要验的就是后者（`ACC-PRJ-AUTO-001` · `TAIL-26`）。

做法：**一次登录**（`KillOnlineUser` 只踢 1 次）——同一个 `I8Client` 包一层代理（`close` 变空操作），
两条链路（库存单据 / 收发结存）各跑一次**真正的 `run_fetch`**，于是每条的
「导出 → 解析 → 幂等落库 → 取仓库名单 → 自动建档」都是真路径。

⚠️ 会登录 i8 并**强踢在线用户**（`KillOnlineUser`）—— 用户 2026-09-17 已授权；跑完即止，不重试。
跑法：`backend/.venv/Scripts/python.exe tools/_verify_auto.py`（在工程根）
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

YM = "2026-09"


class _KeepAlive:
    """代理：把请求转给真 client，但**吞掉 `close`** ⇒ 两条链路共用一次登录。"""

    def __init__(self, inner):
        self._inner = inner

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def close(self):                       # noqa: D102 —— 故意不关（真正的关闭由脚本最后做）
        pass


def _snapshot(s) -> dict:
    from sqlalchemy import select

    from app.mod01_projects.models import Project
    from app.mod07_setl.models import SetlDetail
    from app.mod08_inv.models import InvDetail

    projs = list(s.execute(select(Project)).scalars())
    return {
        "projects": [(p.id, p.name_full, p.warehouse_name, p.project_type, p.parent_shell_id)
                     for p in projs],
        "whs": sorted({str(p.warehouse_name or "") for p in projs if p.warehouse_name}),
        "inv": len(list(s.execute(select(InvDetail)).scalars())),
        "setl": len(list(s.execute(select(SetlDetail)).scalars())),
    }


def main() -> int:
    import app.core.models_registry  # noqa: F401
    from app.core.db import session_scope
    from app.mod02_i8.client import I8Client
    from app.mod07_setl import fetch_service as FS7
    from app.mod08_inv import fetch_service as FS8

    with session_scope() as s:
        before = _snapshot(s)
        from app.mod01_projects.repository import export_phids

        ids_csv = export_phids(s)
    print("=== 抓前 ===")
    print("  项目档案:", len(before["projects"]), "条 · 仓库名", before["whs"])
    print("  inv_detail:", before["inv"], "行 · setl_detail:", before["setl"], "行")
    print("  导出项目参数:", len(ids_csv.split(",")), "项 · 唯一",
          len(set(ids_csv.split(","))), "（壳与其下小微共享 phid ⇒ 必须相等）")

    client = I8Client(allow_kick=True)
    keep = _KeepAlive(client)
    factory = lambda: keep                      # noqa: E731 —— 同一实例 ⇒ 只登录一次
    results: dict[str, dict] = {}
    try:
        for tag, runner in (("inv", FS8.run_fetch), ("setl", FS7.run_fetch)):
            print(f"\n=== 跑 {tag}（真机 · 复用同一会话）===")
            with session_scope() as s:
                out = runner(s, year_month=YM, confirmed=True, operator="科室用户",
                             client_factory=factory)
            results[tag] = out
            print(f"  ok={out.get('ok')} degraded={out.get('degraded')} rows={out.get('rows')}")
            if out.get("message"):
                print("  message:", str(out["message"])[:160])
            if out.get("stats"):
                print("  stats:", out["stats"])
            if out.get("unknown_warehouses") is not None:
                print("  陌生仓库:", out["unknown_warehouses"])
            rec = out.get("recovery")
            if rec:
                from app.mod01_projects.recovery import summary_text

                print("  ── 链路 B 回执（抓取页面上给人看的那句）──")
                print("    ", summary_text(rec) or "（无动作、无待办）")
                print("     计数:", {k: rec.get(k) for k in ("promote", "create", "unresolved", "degraded")})
    finally:
        client.close()

    with session_scope() as s:
        after = _snapshot(s)
    print("\n=== 抓后 ===")
    print("  项目档案:", len(after["projects"]), "条（抓前", len(before["projects"]), "）")
    new = [p for p in after["projects"] if p not in before["projects"]]
    print("  ⭐ 新增档案行:")
    for row in new:
        print("    ·", row)
    print("  inv_detail:", after["inv"], "行（抓前", before["inv"], "）")
    print("  setl_detail:", after["setl"], "行（抓前", before["setl"], "）")
    for kw in ("兰考", "大唐雷州", "焦作百利"):
        hit = [p for p in after["projects"] if kw in str(p[2] or "")]
        print(f"  「{kw}」已在档案:", bool(hit), hit or "")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
