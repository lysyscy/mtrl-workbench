"""`MOD-09` 特殊费用月报表 —— **真机端到端**（连真服务 + 真库）。

覆盖：读那一份 → ② 新增手填项 → ③ 改名 → ④ 改金额（合法）→ ⑤ **非法金额必须拒绝且原值不变**
→ ⑥ **负数允许**（§5.5 最宽松一档）→ ⑦ 删除复原 → ⑧ 直查库核实**无残留**。

⛔ 本页**不写 i8、不抓取**（自动项只读 `inv_detail`），所以跑它**不会顶号**。
⚠️ 仅限独占维护窗口；清理由同库连接按已知 ID 锁行删除。未取得 ID 时失败并报告可能残留，不猜删。

用法：服务在跑（`127.0.0.1:8000`）⇒ `python tools/probe/_e2e_m09_wired.py`
"""

from __future__ import annotations

import sys
from uuid import uuid4
from decimal import Decimal
from pathlib import Path

import httpx

# 让脚本能 import 到 app（查库那一步用）
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

BASE = "http://127.0.0.1:8000"
fails: list[str] = []


def check(ok: bool, what: str, extra: str = "") -> None:
    print(("  ✅ " if ok else "  ⛔ ") + what + (f" —— {extra}" if extra else ""))
    if not ok:
        fails.append(what)


def _manual_state(row: dict) -> dict[str, str]:
    """手填行的可比较基线字段（忽略随列表位置变化的 index）。"""
    amount = row.get("amount")
    return {"item": str(row.get("item") or ""), "amount": format(Decimal(str(amount)), ".2f") if amount is not None else ""}


def _db_manual_state(row, name) -> dict[str, str]:
    """ORM 手填行转成基线值；Decimal 0.00 不能被当成空值。"""
    return _manual_state({"item": name, "amount": row.amount})


def manual_snapshot(manuals) -> dict[int, dict[str, str]]:
    """按手填记录 id 保存当前作用域基线。"""
    out: dict[int, dict[str, str]] = {}
    for row in manuals or ():
        if row.get("id") is None:
            raise RuntimeError("手填项缺少记录 id，无法安全清理")
        rid = int(row["id"])
        if rid in out:
            raise RuntimeError(f"手填项 id 重复：{rid}")
        out[rid] = _manual_state(row)
    return out


def cleanup_manual(*, ym: str, project: str, baseline: dict[int, dict[str, str]],
                   owned_id: int | None, expected: dict[str, str], owned_item: bool = False) -> bool:
    """已知 ID 才锁行比较并删除；绝不把变化中的列表下标用于异常清理。"""
    from sqlalchemy import select
    from app.core.db import session_scope
    from app.mod09_fee.models import FeeItem, FeeManualItem
    from app.mod09_fee.repository import project_by_key

    if owned_id is None:
        raise RuntimeError("新增后未取得稳定记录 id，无法证明归属；可能有残留，须核对后处理")
    if owned_id in baseline:
        raise RuntimeError("拒绝清理基线中已有的手填项")
    with session_scope() as s:
        owner = project_by_key(s, project)
        row = s.get(FeeManualItem, owned_id)
        if row is None:
            return False
        item = s.execute(select(FeeItem).where(FeeItem.id == row.fee_item_id).with_for_update()).scalar_one()
        s.refresh(row, with_for_update=True)
        if (owner is None or row.project_id != owner.id or row.ym != ym or item.deleted or
                _db_manual_state(row, item.name) != _manual_state(expected)):
            raise RuntimeError(f"本次手填项 {owned_id} 已被其他值改动，停止清理以免覆盖")
        if owned_item:
            # 只允许本探针随机命名的独占定义，不能删共享或后来新增的月份。
            months = list(s.scalars(select(FeeManualItem.id).where(FeeManualItem.fee_item_id == item.id)))
            if not item.name.startswith('__fee_probe_') or months != [owned_id]:
                raise RuntimeError('费用项归属或关联月份已变化，停止清理')
        s.delete(row)
        if owned_item:
            s.flush()
            s.delete(item)
    return True


def db_manual_snapshot(ym: str, project: str) -> dict[int, dict[str, str]]:
    """直查本次月 / 项目作用域的手填记录，避免把全表为空当作净零。"""
    from sqlalchemy import select

    from app.core.db import session_scope
    from app.mod09_fee.models import FeeItem, FeeManualItem
    from app.mod09_fee.repository import project_by_key

    with session_scope() as s:
        owner = project_by_key(s, project)
        if owner is None:
            raise RuntimeError(f"项目档案不存在：{project}")
        rows = s.execute(select(FeeManualItem, FeeItem.name).join(FeeItem, FeeItem.id == FeeManualItem.fee_item_id).where(
            FeeManualItem.ym == ym, FeeManualItem.project_id == owner.id, FeeItem.deleted.is_(False)))
        return {int(row.id): _db_manual_state(row, name) for row, name in rows}



def verify_db_baseline(ym: str, project: str, baseline: dict[int, dict[str, str]]) -> tuple[bool, str]:
    """返回直查库结果；查库异常必须是失败而不是跳过。"""
    try:
        current = db_manual_snapshot(ym, project)
    except Exception as exc:  # noqa: BLE001
        return False, f"查库失败：{exc.__class__.__name__}: {exc}"
    return current == baseline, f"当前 {current!r} · 基线 {baseline!r}"


def main() -> int:
    c = httpx.Client(base_url=BASE, timeout=30.0)
    fee = c.get("/api/m09/fee").json()
    ym, pj = fee["ym"], fee["project"]
    print(f"① 读那一份 —— ym={ym} · pj={pj!r}")

    # ---- 读：形状与同源
    for k in ("ym", "project", "project_display", "projects", "auto", "manuals",
              "total", "count", "can_edit", "columns", "auto_name"):
        check(k in fee, f"读端点出字段 `{k}`")
    check("ops" not in (fee["auto"] or {}), "`ops` 列**不进 API**（`domain.PAGE_ONLY_KEYS`）")
    check(all(p.get("key") for p in fee["projects"]), "候选每项都有键（= 仓库名，§2.7.4）")
    check(isinstance(fee["total"], str), "金额出**字符串**（精度保护）⇒ 转数字是适配层（`N0()`）的职责")
    if not pj or not fee["can_edit"]:
        print("  ⚠️ 该月没有可写的项目那一份 ⇒ 只做读检查，跳过写路径")
        print("\n结论：" + ("全通 ✅" if not fails else f"⛔ {len(fails)} 条未过"))
        return 1 if fails else 0

    before = len(fee["manuals"])
    baseline = manual_snapshot(fee["manuals"])
    print(f"   起始手填项 {before} 条 · 合计 {fee['total']}")

    # 写前复核保存的作用域基线；已有并发改动就立即停止。
    current = c.get("/api/m09/fee", params={"ym": ym, "pj": pj}).json()
    if manual_snapshot(current.get("manuals")) != baseline:
        check(False, "写入前手填项仍保持基线")
        return 1

    owned_id: int | None = None
    expected: dict[str, str] = {}
    probe_name = '__fee_probe_' + uuid4().hex
    renamed = probe_name + '_renamed'
    try:
        # ---- ② 新增
        print("② 新增手填项（`POST /api/m09/fee/add`）")
        response = c.post("/api/m09/fee/add", json={"ym": ym, "project": pj, "name": probe_name})
        r = response.json()
        check(r.get("ok") is True, "新增成功", r.get("message", "")[:70])
        if response.status_code != 200 or r.get("ok") is not True:
            return 1

        # 这次新增后的回读和下标定位都必须在 try 内，后续异常才能进入清理。
        after = c.get("/api/m09/fee", params={"ym": ym, "pj": pj}).json()
        after_rows = after.get("manuals") or []
        after_snapshot = manual_snapshot(after_rows)
        new_ids = set(after_snapshot) - set(baseline)
        check(len(after_rows) == before + 1, "回读多了一行（真的落库了）",
              f"{before} → {len(after_rows)}")
        if len(new_ids) != 1:
            check(False, "新增记录可唯一归属", f"新增 id={sorted(new_ids)}")
            return 1
        owned_id = next(iter(new_ids))
        idx = next(i for i, row in enumerate(after_rows) if int(row["id"]) == owned_id)
        expected = after_snapshot[owned_id]

        # ---- ③ 改名
        print("③ 改名（`/fee/name`）")
        r = c.post("/api/m09/fee/name", json={"ym": ym, "project": pj, "index": idx, "value": renamed}).json()
        check(r.get("ok") is True, "改名成功", r.get("message", "")[:70])
        if r.get("ok") is True:
            expected["item"] = renamed
        got = c.get("/api/m09/fee", params={"ym": ym, "pj": pj}).json()
        check(got["manuals"][idx]["item"] == renamed, "回读项名确为本探针改名值")

        # ---- ④ 改金额（合法）
        print("④ 改金额（合法 12345.67）")
        r = c.post("/api/m09/fee/amount",
                   json={"ym": ym, "project": pj, "index": idx, "value": "12345.67"}).json()
        check(r.get("ok") is True, "合法金额被接受", r.get("message", "")[:70])
        if r.get("ok") is True:
            expected["amount"] = "12345.67"
        got = c.get("/api/m09/fee", params={"ym": ym, "pj": pj}).json()
        check(got["manuals"][idx]["amount"] == "12345.67", "回读金额 = 12,345.67",
              f"实际 {got['manuals'][idx]['amount']}")

        # ---- ⑤ 非法金额：**必须拒绝且原值不变**
        print("⑤ ⭐ 非法金额（`abc`）⇒ 必须拒绝且原值不变")
        r = c.post("/api/m09/fee/amount",
                   json={"ym": ym, "project": pj, "index": idx, "value": "abc"}).json()
        check(r.get("ok") is False, "非法金额被**拒绝**", r.get("message", "")[:70])
        got = c.get("/api/m09/fee", params={"ym": ym, "pj": pj}).json()
        check(got["manuals"][idx]["amount"] == "12345.67", "**原值未变**（不是 0、也不是空）",
              f"实际 {got['manuals'][idx]['amount']}")

        # ---- ⑥ 负数允许
        print("⑥ 负数（`-88.5`）⇒ §5.5 只拦「非数字」、**允许 0 与负数**")
        r = c.post("/api/m09/fee/amount",
                   json={"ym": ym, "project": pj, "index": idx, "value": "-88.5"}).json()
        check(r.get("ok") is True, "负数被接受", r.get("message", "")[:70])
        if r.get("ok") is True:
            expected["amount"] = "-88.50"
        got = c.get("/api/m09/fee", params={"ym": ym, "pj": pj}).json()
        check(got["manuals"][idx]["amount"] == "-88.50", "回读金额 = -88.50",
              f"实际 {got['manuals'][idx]['amount']}")
        check(got["auto"]["share"] in ("—",) or isinstance(got["auto"]["share"], str),
              "合计 ≤ 0 ⇒ 「占合计」给「—」而不是 `NaN%`", f"实际 {got['auto']['share']!r}")
    finally:
        # ---- ⑦ 复原（无论上面成没成，都要删掉那一行）
        print("⑦ 锁行清理本次手填项")
        try:
            ok = cleanup_manual(
                ym=ym, project=pj, baseline=baseline,
                owned_id=owned_id, expected=expected, owned_item=True,
            )
            check(ok, "本次手填项已删除")
        except Exception as exc:  # noqa: BLE001
            check(False, "本次手填项已删除", str(exc))

    got = c.get("/api/m09/fee", params={"ym": ym, "pj": pj}).json()
    check(manual_snapshot(got.get("manuals")) == baseline, "手填项回到保存的基线")

    # ---- ⑧ 直查库（只核本次作用域；查库异常必须失败）
    print("⑧ 直查库核实本次作用域回到基线")
    db_ok, db_detail = verify_db_baseline(ym, pj, baseline)
    check(db_ok, "直查库成功且本次作用域无残留", db_detail)

    print("\n结论：" + ("全通 ✅" if not fails else f"⛔ {len(fails)} 条未过"))
    for f in fails:
        print("   ·", f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
