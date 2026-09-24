"""一次性件（`TAIL-92` · 2026-09-25）：把**挂在「壳」上的集采合同**按新口径归位。

**为什么有它**：`TAIL-92` 之前，集采匹配是「全名精确相等 ⇒ 取第一条」——
而壳与具体小微**共用同一个全名**（《说明书》§2.2 / §2.6）⇒ 壳全名命中了 `[壳, 小微]`、取到了**壳**
⇒ **23 条**合同挂在壳上（壳没有仓库、不进候选 ⇒ 界面上"没有项目"、欠款无从归集）。

**口径与代码同源**：判定一律调 `mod01_projects.domain.resolve_ownership`（付款侧唯一出口），
⛔ 本件**不自己判**、也不改任何判定逻辑（`TAIL-92` 已把生产路径接上同一个出口）。

用法（工程根）：
    backend\\.venv\\Scripts\\python.exe tools\\oneoff\\_tail92_repair_shell_contracts.py          # 只报（dry-run）
    backend\\.venv\\Scripts\\python.exe tools\\oneoff\\_tail92_repair_shell_contracts.py --apply    # 真改（先自动备份）
"""

from __future__ import annotations

import csv
import datetime as dt
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import select                                    # noqa: E402

from app.core.db import session_scope                            # noqa: E402
from app.mod01_projects.domain import resolve_ownership          # noqa: E402
from app.mod01_projects.models import TYPE_SHELL, Project        # noqa: E402
from app.mod01_projects.repository import all_projects           # noqa: E402
from app.mod11_jc.models import JcContract                       # noqa: E402

BACKUP_DIR = ROOT / ".workbuddy" / "backups"


def main(argv: list[str]) -> int:
    apply = "--apply" in argv
    with session_scope() as s:
        projects = list(all_projects(s))
        shells = {p.id: p for p in projects if p.project_type == TYPE_SHELL}
        rows = list(s.execute(select(JcContract).where(JcContract.project_id.in_(shells.keys()))).scalars())
        plan: list[tuple[JcContract, object]] = []
        for c in rows:
            shell = shells.get(int(c.project_id or 0))
            d = resolve_ownership(
                name_full=str(getattr(shell, "name_full", "") or ""),
                doc_name=str(getattr(c, "bill_name", "") or ""),
                projects=projects,
            )
            plan.append((c, d))

        print(f"挂在壳上的集采合同 = {len(plan)} 条")
        moved = stay = 0
        out: list[dict] = []
        for c, d in plan:
            cur = str(getattr(c, "project_id", "") or "")
            if d.settled and int(d.target_id or 0) != int(getattr(c, "project_id", 0) or 0):
                moved += 1
                verdict = f"→ 归到 project_id={d.target_id}（{d.kind}）"
            else:
                stay += 1
                verdict = f"不动（kind={d.kind} · settled={d.settled}）"
            out.append({"contract_no": c.contract_no, "bill_name": getattr(c, "bill_name", "") or "",
                        "from_project_id": cur, "kind": d.kind,
                        "to_project_id": str(d.target_id or ""), "verdict": verdict})
            print(f"  {c.contract_no}  {verdict}  | 单据名：{str(getattr(c, 'bill_name', '') or '')[:46]}")

        print(f"\n可归位 {moved} 条 · 归不了（留原地并报出）{stay} 条")
        if not apply:
            print("\n（dry-run —— 加 --apply 才真改；改前自动备份）")
            return 0

        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        bak = BACKUP_DIR / f"tail92-shell-contracts-{dt.datetime.now():%Y%m%d-%H%M}.csv"
        with bak.open("w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(out[0].keys()))
            w.writeheader()
            w.writerows(out)
        print(f"备份 → {bak}")

        for c, d in plan:
            if d.settled and int(d.target_id or 0) != int(getattr(c, "project_id", 0) or 0):
                c.project_id = int(d.target_id)
        s.flush()
        print(f"已归位 {moved} 条 ✓（剩下的 {stay} 条留原地，原因见上表 —— 需人工指认/补关键词）")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main(sys.argv[1:]))
