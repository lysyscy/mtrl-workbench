"""链路 B · **「待人工指认」清单**（`TAIL-30`-③ · 用户 2026-09-18 批准方案，语义见计划 §17）。

**这一段补的是什么**：链路 B 的三类处置里 ——

| 命中情况 | 谁来做 |
|---|---|
| 1 条占位行 ⇒ 扶正改名 | **系统自己做**（抓取时无感完成，见 `recovery.recover_unknown_warehouses`） |
| 命中壳 ⇒ 新建具体小微 | **系统自己做** |
| ⭐ **≥2 条非壳行 ⇒ 挂到哪一行** | ⛔ **系统不猜**（决策 1 兜底）⇒ **必须人来做** ← 本模块 |

而这几条**只出现在抓取回执里一次**（页面一刷新就没了）⇒ 用户站在 `m01` 上**没有任何入口**
（这就是 `TAIL-30`-③ 的现状缺口：入口不是"加个按钮"，得先把这句话**留住并露出来**）。

⇒ 做法：抓取时把这几条**存进那条运行记录的 `detail`**（`mod07_setl` / `mod08_inv` 各自写），
`m01` 再从**最近一次材料侧抓取**读回来。

⚠️ 三条口径（都有主人，⛔ 无新立）：
1. **只认最近一次材料侧抓取**（`setl` / `inv`）—— 与 `mod03_notice.repository.latest_unresolved` 同款口径。
   ⛔ **不回溯历史记录**：抓取成功后仍摆着旧清单 ⇒ 用户对着**已经解决**的清单白干（`TAIL-41` 同族）。
   ⇒ 两条链路的**每一条**运行记录都写这个键（哪怕这次没有待人工）＝ "最近一次"永远指得住。
2. **清单只是"当时的判定"** ⇒ 读出来必须**逐条按当前档案现算**（用户可能刚建了行、刚扶正过、
   甚至刚删了行）—— 已经不再是那个情形的**当场丢掉**（`live_items`）。判据同理：清单是**线索**，
   真相是**档案现在的样子**。
3. **判定口径唯一出口 = `recovery.classify_hits`** —— ⛔ 不在这里再写一份「≥2 条非壳行」的判断。
   ⛔ 也**不看中文 `reason` 串**：文案一改，"挑出要人指认的那一类"就会静默失效 ⇒ 认 `kind`。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.mod01_projects.domain import ordered
from app.mod01_projects.models import TYPE_SHELL, TYPE_SMALL, Project
from app.mod01_projects.recovery import (
    KIND_MULTI,
    classify_hits,
    hits_of_full,
    rows_by_full,
    unknown_warehouses,
)
from app.mod01_projects.repository import all_projects

#: 运行记录 `detail` 里放待人工清单的键（**写侧唯一出口 = `record_detail`**：键名只此一处）
RECORD_KEY = "promote_pending"

#: 材料侧两条抓取链路的 `SPEC_KEY`（主人 = `mod07_setl.fetch_service.SPEC_KEY` /
#: `mod08_inv.fetch_service.SPEC_KEY`）。⚠️ 这里**不 import** 它们：那会形成
#: `mod01 → mod07 → mod01` 的循环 import（两条 fetch_service 都 import 本包）。
#: ⇒ 用 `target` 前缀认 ＋ **一条断言看住它**（`test_promote_pending.py` 里比对两处 SPEC_KEY）。
MATERIAL_TARGETS: tuple[str, ...] = ("setl", "inv")

#: 回溯多少条运行记录找"最近一次材料侧抓取"（与 `latest_unresolved` 同量级）
LOOKBACK = 20

#: 展示用的类型中文名（与 `m01` 档案页同一套说法）
TYPE_LABEL = {TYPE_SHELL: "壳", TYPE_SMALL: "具体小微", "normal": "普通项目"}


def record_detail(items=None) -> dict:
    """写进运行记录 `detail` 的那一段（**写侧唯一出口**）—— 没在抓取时的**两条链路都写**（见口径 1）。"""
    return {RECORD_KEY: [dict(x) for x in (items or [])]}


def is_material_target(target) -> bool:
    """这条运行记录是不是**材料侧抓取**（`target` = `<SPEC_KEY> <核算年月>（N 个项目）`）。"""
    t = str(target or "").strip()
    return any(t == key or t.startswith(key + " ") for key in MATERIAL_TARGETS)


def latest_pending(session: Session) -> dict:
    """**最近一次材料侧抓取**带的「待人工」原样清单 → `{found, items, target, at, run_record_id}`。

    ⚠️ 认不出材料侧记录 ⇒ `found=False` ＋ 空清单（**不拿别的记录凑**：那会让用户对着一份
       跟材料域无关的清单去改档案）。
    """
    from app.mod02_i8 import service as records
    recs = records.recent_records(session, run_type="fetch", limit=LOOKBACK)
    # ⚠️ 离线桩（`tests.m09_helpers.M09Session`）**不处理 `order_by`** ⇒ 这里再显式排一次。
    #    真库本来就已按 id 倒序返回 ⇒ 不改变语义，只是让断言与真机走同一条路。
    for r in sorted(recs, key=lambda x: getattr(x, "id", 0) or 0, reverse=True):
        if not is_material_target(getattr(r, "target", "")):
            continue
        detail = getattr(r, "detail", None) or {}
        started = getattr(r, "started_at", None)
        return {
            "found": True,
            "items": [dict(x) for x in (detail.get(RECORD_KEY) or [])],
            "target": str(getattr(r, "target", "") or ""),
            "at": started.isoformat(sep=" ", timespec="seconds") if started else "",
            "run_record_id": getattr(r, "id", None),
        }
    return {"found": False, "items": [], "target": "", "at": "", "run_record_id": None}


def candidate_row(p: Project) -> dict:
    """一条候选档案行 → 展示用形状（`TAIL-30`-③ 计划 §17.4 端点①的字段单）。"""
    return {
        "id": getattr(p, "id", None),
        "type": str(getattr(p, "project_type", "") or ""),
        "type_label": TYPE_LABEL.get(getattr(p, "project_type", ""), str(getattr(p, "project_type", "") or "")),
        "warehouse_name": str(getattr(p, "warehouse_name", "") or ""),
        "disp": str(getattr(p, "disp", "") or ""),
        "status": str(getattr(p, "status", "") or ""),
        "phid": str(getattr(p, "phid", "") or ""),
        # ⭐ 只有**占位行**能被扶正（§2.3.1：仓库名不可人工修改）—— 这一格决定界面能不能选它
        "is_placeholder": bool(getattr(p, "is_placeholder", False)),
    }


def candidates(session: Session, full) -> list[dict]:
    """**该全名下的档案行**（含归档行 · §17.2）—— 人工指认要先看见"有哪些行、都是什么"。

    ⚠️ 这是**读**（可按全名查）；**写**一律按 `id` 定位（铁律 5/6：禁止用名字反查）。
    排序走全站同一套（`domain.ordered`：归档后置 > `ord` > 原序）。
    """
    rows = hits_of_full(rows_by_full(all_projects(session)), full)
    return [candidate_row(p) for p in ordered(rows)]


def live_items(session: Session) -> list[dict]:
    """待指认清单：最近一次材料侧抓取的那几条，**逐条按当前档案现算**。

    一条条目**仍然成立**要同时满足两条 —— 只要有一条不成立，就**当场丢掉**
    （清单是**线索**、档案现在的样子才是**真相**；⛔ 摆着已解决的让人白干 = `TAIL-41` 同族）：

    ① **那个仓库名**在档案里**仍然找不到**（= 仍然"陌生"）—— 有人刚把某行扶正/建行成它，
       下次抓取就不会再报它了；
    ② 它的全名**仍然**命中 ≥2 条非壳行（`classify_hits` ⇒ `KIND_MULTI`）—— 有人建了行 / 改了名 /
       删到只剩 1 条，这个情形就没了（只剩 1 条占位行时，系统下次抓取会**自动扶正**，不用人）。

    - 仍成立 ⇒ 带上**现在的**候选行（`candidates`），界面不用再问一次；
    - ⚠️ 全名在各条目之间**可能重复**（两条陌生仓库指向同一个全名）⇒ 不去重：一条一条处理。
    """
    by_full = rows_by_full(all_projects(session))
    src = latest_pending(session)
    raw_items = list(src["items"])

    # ① 仍然"陌生"的仓库名 —— ⚠️ 口径**复用** `unknown_warehouses`（收发结存 / 库存单据共用那一份），
    #    ⛔ 不在这里再写一遍差集（"陌生"的定义只许有一个主人）。
    still_unknown = set(unknown_warehouses(
        session, [{"warehouse_name": str(x.get("warehouse_name") or "")} for x in raw_items]
    ))

    out: list[dict] = []
    for raw in raw_items:
        wh = str(raw.get("warehouse_name") or "")
        if wh not in still_unknown:
            continue                      # ① 仓库已经在档案里了
        full = str(raw.get("owner_full_name") or "")
        hits = hits_of_full(by_full, full)
        if classify_hits(hits) != KIND_MULTI:
            continue                      # ② 已经不是「≥2 条非壳行」那个情形了
        out.append({
            **raw,
            "kind": KIND_MULTI,
            "full_name": full,
            "candidates": [candidate_row(p) for p in ordered(hits)],
        })
    return out


def live_pending(session: Session) -> dict:
    """`m01` 顶部入口要的全部：**清单 ＋ 它来自哪一次抓取**（⛔ 不装作"刚刚"—— 如实告诉用户来源）。"""
    src = latest_pending(session)
    items = live_items(session)
    return {
        "found": src["found"],
        "items": items,
        "source": {"target": src["target"], "at": src["at"], "run_record_id": src["run_record_id"]},
        "dropped": len(src["items"]) - len(items),
    }


__all__ = ["RECORD_KEY", "MATERIAL_TARGETS", "LOOKBACK", "TYPE_LABEL",
           "record_detail", "is_material_target", "latest_pending",
           "candidate_row", "candidates", "live_items", "live_pending"]
