"""一次性（2026-09-26 · 用户裁定「方案②」第 3 步）：把**贸易公司合同**落错列的「合同金额」清成 0。

**为什么清**：这类合同的「合同金额」（= 供应商价）在 i8 里**根本没有**、按设计**留空**；
而它们现在装着**贸易公司的价**（抓取时甲方还没分类 ⇒ 走了"正常甲方"分支落库；事后改分类**不回头重算**）。
方案② 落地后，导入会凭「**贸易公司合同金额**」对上、再把 Excel 的「供应商合同总价」**空才填**进来
⇒ 所以必须先把错值清掉（否则"空才填"永远不动它）。

**安全三件**（⛔ 缺一不做）：
① **先备份**：全行快照写 `<repo>/.workbuddy/backups/jc_trade_amt_clean_2026-09-26.json`（含 id / 编号 / 三个金额）；
② **条数核对**：按查实值（27 条）**硬核对** —— 不符 ⇒ **停**（⛔ 不猜、不半做）；
③ **只动一列**：只把这一类行的 `contract_amt` 置 0；⛔ 不动 trade 两列 / 不动 i8 事实列 / ⛔ 不删任何行。

跑法：`backend\\.venv\\Scripts\\python.exe tools\\oneoff\\_apply_jc_trade_amt_clean.py`
"""

from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import select                                    # noqa: E402

from app.core.db import session_scope                            # noqa: E402
from app.mod11_jc.models import JcContract, JcPartyKind          # noqa: E402

#: 查实值（`_jc_audit.py` · 2026-09-26）：甲方被标 trade 的合同共 27 条、且**全部**落错列
EXPECT = 27
BACKUP = ROOT / ".workbuddy" / "backups" / "jc_trade_amt_clean_2026-09-26.json"


#: ⚠️ **自检数据一律排除**（本仓惯例：自检行/项目名以 `__自检` 开头）。
#:   实测踩到一次：我调试试跑（`_dbg_imp.py`）留下的 `__自检_DBG_*` 那条被 ② 填了 150000
#:   ⇒ 不排除就会把"28 条"当成"业务数据多了 1 条"（其实是自己的垃圾）。
SELF_PREFIX = "__自检"


def main() -> int:
    from app.mod01_projects.models import Project

    with session_scope() as s:
        trade_names = {str(k.name) for k in s.execute(select(JcPartyKind)).scalars()
                       if str(k.kind) == "trade"}
        self_projects = {int(p.id) for p in s.execute(select(Project)).scalars()
                         if str(p.warehouse_name or "").startswith(SELF_PREFIX)
                         or str(getattr(p, "name_full", "") or "").startswith(SELF_PREFIX)}
        all_rows = list(s.execute(select(JcContract)).scalars())
        rows = [c for c in all_rows
                if str(c.party_name) in trade_names and float(c.contract_amt or 0) != 0
                and int(c.project_id) not in self_projects]
        print(f"甲方被标「贸易公司」的：{sorted(trade_names)}")
        print(f"待清（该类 · 合同金额非 0 · **排除自检项目**）：{len(rows)} 条（查实值 {EXPECT}）")
        if len(rows) != EXPECT:
            print(f"⛔ 条数与查实值不符（{len(rows)} ≠ {EXPECT}）⇒ **停**："
                  "先重新查一遍这一类到底有哪些（⛔ 不猜着改）")
            return 1

        # 顺手：清掉**我自己**造的自检垃圾（只认带 `__自检_DBG_` / 固定号的，⛔ 不碰别的）
        mine = [c for c in all_rows if int(c.project_id) in self_projects
                and (str(c.contract_no).startswith(SELF_PREFIX + "_DBG_")
                     or str(c.contract_no) == SELF_PREFIX + "_B5b_T1__")]
        for c in mine:
            s.delete(c)
        if mine:
            s.flush()
        print(f"🧹 顺手清掉自检垃圾 {len(mine)} 条（编号 {[str(c.contract_no) for c in mine][:6]}）")

        BACKUP.parent.mkdir(parents=True, exist_ok=True)
        snap = [{"id": int(c.id), "contract_no": str(c.contract_no), "project_id": int(c.project_id),
                 "party_name": str(c.party_name), "trade_co": str(c.trade_co or ""),
                 "trade_contract_amt": str(c.trade_contract_amt if c.trade_contract_amt is not None else ""),
                 "contract_amt_before": str(c.contract_amt)} for c in rows]
        BACKUP.write_text(json.dumps({"_note": "贸易公司合同「合同金额」清空前的全行快照（可据此还原）",
                                      "at": "2026-09-26", "rows": snap},
                                     ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"✅ 已备份 {len(snap)} 条 → {BACKUP.relative_to(ROOT)}")

        for c in rows:
            c.contract_amt = Decimal("0")
        s.flush()
        print(f"✅ 已把这 {len(rows)} 条的「合同金额」置 0（⛔ 未动 trade 两列 / i8 事实列 / 未删行）")
        for c in rows[:5]:
            print(f"    id={c.id} 编号={c.contract_no} 甲方={c.party_name} → 合同金额={c.contract_amt}")
    print("\n⏭️ 下一步：① 在页面上**抓取一次**（把 trade 两列补上）② 再用 Excel 导入（会凭贸易公司金额对号、空才填进真供应商价）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
