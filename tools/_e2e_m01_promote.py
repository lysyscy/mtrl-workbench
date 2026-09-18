"""真机验证 · `TAIL-30`-③ **人工指认**（链路 B：命中 ≥2 条非壳行 ⇒ 人指定挂哪一行）。

用法：先起服务（改了后端要**重启**），再 `python tools/_e2e_m01_promote.py`。

**演练怎么做**（计划 §17.6）：真机造一份**同名冗余行**（这就是"疑似名字没带「小微」的壳"的现实样子）
＋ 一条**材料侧抓取记录**（带一条待人工条目）⇒ 走三条端点 ⇒ **作业后复原（净零）**。

⚠️ 只碰自己造的样本（全名 / 仓库名都带 `真机演练` 前缀）；跑完**逐条删掉**并**直查库核残留**。
⚠️ 造行一律走**应用自己的写入出口**（`repository.create_project` / `save_run_record`），
   ⛔ 不手写 SQL —— 那样验的就不是真实落库路径了。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
import app.core.models_registry  # noqa: E402, F401

import httpx  # noqa: E402
from sqlalchemy import delete, func, select  # noqa: E402

from app.core.db import session_scope  # noqa: E402
from app.mod01_projects.models import Project  # noqa: E402
from app.mod01_projects.pending import record_detail  # noqa: E402
from app.mod01_projects.recovery import KIND_MULTI  # noqa: E402
from app.mod01_projects.repository import create_project  # noqa: E402
from app.mod02_i8.models import RunRecord  # noqa: E402
from app.mod02_i8.repository import save_run_record  # noqa: E402

BASE = "http://127.0.0.1:8000"

# 演练样本（一律带前缀 ⇒ 万一没清掉也一眼看得出来是谁留下的）
FULL = "真机演练-待指认项目(XMCB2025990001)"
FULL_OTHER = "真机演练-别的项目(XMCB2025990002)"
WH_REAL = "真机演练-真实仓库名"
WH_IN_OTHER = "真机演练-别处的仓库名"

fails: list[str] = []
made_pids: list[int] = []
made_recs: list[int] = []


def ck(ok: bool, what: str, extra: str = "") -> None:
    print(("  ✅ " if ok else "  ⛔ ") + what + (f" —— {extra}" if extra else ""))
    if not ok:
        fails.append(what)


def post(c, path, body):
    r = c.post(path, json=body)
    try:
        return r.status_code, r.json()
    except Exception:                                     # noqa: BLE001
        return r.status_code, {"_raw": r.text[:200]}


def setup() -> None:
    """造样本：同一全名的 **2 条占位行** ＋ **1 条已有真实仓库名**的行 ＋ 一条材料侧抓取记录。"""
    with session_scope() as s:
        a = create_project(s, project_type="normal", name_full=FULL)                  # 占位行 甲
        made_pids.append(a.id)
        b = create_project(s, project_type="normal", name_full=FULL)                  # 占位行 乙
        made_pids.append(b.id)
        c3 = create_project(s, project_type="normal", name_full=FULL,
                            warehouse_name=WH_IN_OTHER)                               # 已有真实名
        made_pids.append(c3.id)
        d = create_project(s, project_type="normal", name_full=FULL_OTHER)            # 别全名（守卫用）
        made_pids.append(d.id)
        run = save_run_record(
            s, run_type="fetch", target="setl 2026-09（3 个项目）", status="success",
            success_count=1, fail_count=0,
            detail=record_detail([{"kind": KIND_MULTI, "warehouse_name": WH_REAL,
                                   "owner_full_name": FULL,
                                   "reason": f"同一全名命中 3 条非壳档案 —— 演示样本"}]),
        )
        made_recs.append(run.id)
        print(f"  （造好：档案行 {made_pids} · 运行记录 {run.id}「setl 2026-09」）")


def teardown() -> None:
    with session_scope() as s:
        s.execute(delete(Project).where(Project.id.in_(made_pids)))
        s.execute(delete(RunRecord).where(RunRecord.id.in_(made_recs)))


def main() -> int:
    c = httpx.Client(base_url=BASE, timeout=30.0)
    try:
        setup()

        # ---------------- ① 清单端点：造的那条**必须**出现，并且带上"现在的"候选行
        d = c.get("/api/m01/promote-pending").json()
        mine = [x for x in (d.get("items") or []) if x.get("full_name") == FULL]
        ck(len(mine) == 1, "待指认清单里出现演练条目", f"{len(mine)} 条")
        ck("setl 2026-09" in str((d.get("source") or {}).get("target", "")),
           "清单如实报出**来自哪一次抓取**", str((d.get("source") or {}).get("target")))
        if not mine:
            return 1
        it = mine[0]
        ck(it.get("warehouse_name") == WH_REAL, "条目带着**真实仓库名**（抓取回执给的那个）",
           str(it.get("warehouse_name")))
        ck(len(it.get("candidates") or []) == 3, "条目带上**现在的**候选行（3 条同名行）",
           str([x.get("id") for x in it.get("candidates") or []]))

        # ---------------- ② 候选端点：只含该全名 · 标出占位行 · 含归档行
        cand = c.get(f"/api/m01/promote-candidates?full={FULL}").json()
        ids = [x["id"] for x in cand["rows"]]
        ck(set(ids) == set(made_pids[:3]) and len(ids) == 3, "候选 = **该全名下的**那几行（不多不少）",
           str(ids))
        ck([x["is_placeholder"] for x in cand["rows"]] == [True, True, False],
           "占位行被标出来（前两条占位、第三条已有真实仓库名）",
           str([(x["id"], x["is_placeholder"]) for x in cand["rows"]]))
        ck(all(x["type_label"] == "普通项目" for x in cand["rows"]), "带类型（中文标签）")
        other = c.get(f"/api/m01/promote-candidates?full={FULL_OTHER}").json()
        ck([x["id"] for x in other["rows"]] == [made_pids[3]], "别的全名查不到这几行（精确相等）")

        # ---------------- ③ 写入口：非占位行**明确拒**（§2.3.1 仓库名不可人工修改）
        st, j = post(c, "/api/m01/promote", {"project_id": made_pids[2],
                                            "warehouse_name": WH_REAL, "full_name": FULL})
        ck(st != 200 and "占位行" in str(j.get("message", "")),
           "已有真实仓库名的行 ⇒ **明确拒**（不是静默改）", f"HTTP {st} · {str(j.get('message'))[:60]}")
        with session_scope() as s:
            ck(s.get(Project, made_pids[2]).warehouse_name == WH_IN_OTHER, "被拒后**一个字都没改**")

        # ---------------- ④ 一致性守卫：跨全名指认 ⇒ 拒（防"张冠李戴"）
        st, j = post(c, "/api/m01/promote", {"project_id": made_pids[1],
                                            "warehouse_name": WH_REAL, "full_name": FULL_OTHER})
        ck(st != 200 and "对不上" in str(j.get("message", "")),
           "指认的行与全名对不上 ⇒ **拒**", f"HTTP {st} · {str(j.get('message'))[:70]}")

        # ---------------- ⑤ 正路：把真实仓库名写到**用户指定的那一行**（甲行）
        st, j = post(c, "/api/m01/promote", {"project_id": made_pids[0],
                                            "warehouse_name": WH_REAL, "full_name": FULL})
        ck(st == 200 and j.get("ok") is True, "指认成功", str(j.get("message"))[:80])
        ck(j.get("old_warehouse_name", "").startswith("未建仓-") and j.get("warehouse_name") == WH_REAL,
           "占位名 → 真实仓库名", f"{j.get('old_warehouse_name')} → {j.get('warehouse_name')}")
        ck(j.get("disp") == WH_REAL and j.get("disp_followed") is True,
           "展示名沿用占位名 ⇒ 一并跟着换（否则屏幕还挂着「未建仓-N」）")
        with session_scope() as s:
            row = s.get(Project, made_pids[0])
            ck((row.warehouse_name, row.disp) == (WH_REAL, WH_REAL), "**真的落库了**（回读核对）")
            ck(s.get(Project, made_pids[1]).warehouse_name.startswith("未建仓-"),
               "**别的行一个字都没动**（按 id 定位，⛔ 不是名字反查）")
            # ⚠️ 扶正**不留痕**（§9.3 留痕范围只有全名/状态）—— 别让"顺手加了留痕"悄悄进来
            from app.mod01_projects.models import ProjectFieldLog
            n = s.execute(select(func.count()).select_from(ProjectFieldLog)
                          .where(ProjectFieldLog.project_id == made_pids[0])).scalar_one()
            ck(n == 0, "扶正不写留痕（§9.3 只给全名 / 状态）", f"{n} 条")

        # ---------------- ⑥ 已解决的要**当场从清单里消失**（⛔ 不摆着让人白干）
        d2 = c.get("/api/m01/promote-pending").json()
        ck(not [x for x in (d2.get("items") or []) if x.get("full_name") == FULL],
           "这条真实仓库名已在档案里 ⇒ 清单里**不再出现**",
           f"dropped={d2.get('dropped')}")
    finally:
        teardown()
        # ⭐ **复原核对**：直查库，确认演练样本一条不剩
        with session_scope() as s:
            left_p = s.execute(select(func.count()).select_from(Project)
                               .where(Project.id.in_(made_pids))).scalar_one()
            left_r = s.execute(select(func.count()).select_from(RunRecord)
                               .where(RunRecord.id.in_(made_recs))).scalar_one()
            dirty = s.execute(select(func.count()).select_from(Project)
                              .where(Project.name_full.like("真机演练%"))).scalar_one()
        ck(left_p == 0 and left_r == 0 and dirty == 0,
           "作业后**复原**：演练样本（档案行 / 运行记录）一条不剩",
           f"残留 档案={left_p} 记录={left_r} 名字带前缀={dirty}")

    print("\n结论：" + ("✅ 全通（指认真的落库、拒得住、且可逆）" if not fails
                     else f"⛔ {len(fails)} 项未过"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
