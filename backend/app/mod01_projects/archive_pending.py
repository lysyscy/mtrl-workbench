"""链路 A · **「待人工建档」清单 ＋ 选定仓库建档**（`TAIL-45`）。

**补的是什么**：链路 A ③（启动建档）三条分支里，**恰好 1 个仓库**与**一个都没有**系统自己就建了；
只有 **≥2 个仓库**这一条要人来定（原口径：「**列出让用户选，只建选中的那个**」）。
而实现原先**只做到"列出"** —— 那条被列进同步回执的 `manual` 清单里，**页面一刷新就没了**，
`m01` 上**没有任何入口**可点 ⇒ 用户按回执看得见、却**无处可点**（`chain_audit` 的 `A` 链路仅剩的红）。

⇒ 本模块补的就是那一半（与 `pending.py`（链路 B · 待人工指认）**同一套做法**）：

| 步 | 做什么 |
|---|---|
| ① **留住** | 同步常用项目列表时，把 `plan_archive` 给的 `manual` 清单随**那一条运行记录**落进 `detail` |
| ② **读回** | `m01` 从**最近一次「常用项目列表」同步**读回来，并**逐条按当前档案现算** |
| ③ **落库** | 人选定一个仓库 ⇒ 走 `repository.create_project`（**唯一建档出口**）就地建行 |

⚠️ 三条口径（与 `pending.py` / `latest_unresolved` 同款，⛔ 无新立）：
1. **只认最近一次「常用项目列表」同步**（`run_type=sync` ＋ `target=常用项目列表`）——
   ⛔ **不回溯更早的**：同步成功之后仍摆着旧清单 ⇒ 用户对着**已经解决**的清单白干（`TAIL-41` 同族）。
   ⚠️ 但**"最近一次"取的是「最近一次成功的同步」**（＝ 记录里**带这个键**的那条）：
   同步**失败**（i8 取数失败 ⇒ `plan=None`）**一行都没建、档案没变** ⇒ 那份清单**照旧有效**，
   跳过它反而对（`pending.py` 那边是"抓取成功即清空"，所以它要求**三种结局都写标记** —— 两条链路
   在这点上**正好相反**，别照抄）。
2. **清单只是"当时的判定"** ⇒ 读出来必须**逐条按当前档案现算**（人可能刚挑过、别处刚建过、行刚被删）
   ⇒ 已经不再是那个情形的**当场丢掉**。
3. **仓库名不许人手打** —— 界面上能选的候选，一律来自**那条同步记录里的 i8 名单**（§9.4：仓库名是 i8 的）。

⚠️ **本模块只做链路 A 的「≥2 个仓库」这一条**：壳下具体小微（要关键词）属链路 C 的人工确认
（`m03` 弹窗 ＋ `TAIL-39`），缺 `phid` 那条要人去 i8 侧加项目 —— **都不在这里**。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import MustReportError
from app.mod01_projects import archive as ARCHIVE      # ⚠️ 只为 `MANUAL_SHELL` 这个字面（唯一主人 = 那边）
from app.mod01_projects.domain import DEFAULT_SMALL_KEYWORD, classify_name, norm_full_name
from app.mod01_projects.models import Project
from app.mod01_projects.repository import all_projects, create_project

#: 运行记录 `detail` 里放这份清单的键（**写侧唯一出口 = `record_detail`**：键名只此一处）
RECORD_KEY = "archive_pending"

#: 认「哪一条同步记录是它」—— `_persist_fetch(object_desc=…)` 会把这段文字写进 `target`。
#: ⚠️ 与 `mod02_i8/router.py::sync_common_projects` 的 `object_desc` **必须逐字一致**（一条断言看住它）。
TARGET_OF_SYNC = "常用项目列表"

#: 回溯多少条运行记录找"最近一次同步"（技术台账，量很小；与 `pending.LOOKBACK` 同量级）
LOOKBACK = 20


def record_detail(items=None) -> dict:
    """写进同步那条运行记录 `detail` 的那一段（**写侧唯一出口**；每次同步都写，见口径 1）。"""
    return {RECORD_KEY: [dict(x) for x in (items or [])]}


def is_common_project_sync(target) -> bool:
    """这条运行记录是不是**「常用项目列表」同步**（`target` 就是 `object_desc`）。"""
    return str(target or "").strip() == TARGET_OF_SYNC


def latest_pending(session: Session) -> dict:
    """**最近一次「常用项目列表」同步**带的待人工清单 → `{found, items, target, at, run_record_id}`。

    ⚠️ 认不出 ⇒ `found=False` ＋ 空清单（**⛔ 不拿更早的记录凑**：那会让用户对着早已解决的事白干）。
    """
    from app.mod02_i8 import service as records
    recs = records.recent_records(session, run_type="sync", limit=LOOKBACK)
    # ⚠️ 离线桩（`tests.m09_helpers.M09Session`）**不处理 `order_by`** ⇒ 再显式按 id 倒序一次
    #    （真库本来就有序 ⇒ 语义不变，只让断言与真机走同一条路）。
    for r in sorted(recs, key=lambda x: getattr(x, "id", 0) or 0, reverse=True):
        if not is_common_project_sync(getattr(r, "target", "")):
            continue
        detail = getattr(r, "detail", None) or {}
        if RECORD_KEY not in detail:
            continue          # ⚠️ 失败的同步（没建任何行、档案没变）⇒ 跳过它，见口径 1
        started = getattr(r, "started_at", None)
        return {
            "found": True,
            "items": [dict(x) for x in (detail.get(RECORD_KEY) or [])],
            "target": str(getattr(r, "target", "") or ""),
            "at": started.isoformat(sep=" ", timespec="seconds") if started else "",
            "run_record_id": getattr(r, "id", None),
        }
    return {"found": False, "items": [], "target": "", "at": "", "run_record_id": None}


# ------------------------------------------------------------------ 读（现行清单）


def _snapshot(session: Session) -> tuple[set[str], set[str]]:
    """当前档案的两把钥匙 → `(已占用的仓库名, 已有行的全名（归一化）)`。"""
    projects = all_projects(session)
    taken = {str(getattr(p, "warehouse_name", "") or "") for p in projects}
    have_full = {norm_full_name(getattr(p, "name_full", "")) for p in projects}
    return taken, have_full


#: 丢掉的理由（**机器认**；人话在 `_WHY_TEXT` 里 —— ⛔ 别拿中文串判类别，`recovery.py` 的老纪律）
WHY_SHELL = "shell_small"          # ⭐ 壳下具体小微 ⇒ **本来就不属本卡**（出路 = 建档向导）
WHY_NO_WH = "no_warehouses"        # 老记录 / 手工拼的（没有结构化仓库清单）⇒ 让人「选」都无从选
WHY_HAS_ROW = "has_row"            # 该全名已经建过行了
WHY_NOT_ENOUGH = "not_enough"      # 那条 i8 名单里剩下的候选不足 2 个

_WHY_TEXT = {
    WHY_SHELL: "它是「壳下具体小微」（壳已在档，但它名下的仓库还没建行）—— 要的是"
               "「出现在单据名里」的**关键词**，出路是**建档向导**（m03 里遇到该壳时选小微／补词），"
               "⛔ 不是在这里选仓库 ⇒ **不属本卡**",
    WHY_NO_WH: "这条没带候选仓库清单（老记录 / 手工拼的）⇒ 本卡让人「选一个」都无从选",
    WHY_HAS_ROW: "这个全名**已经建过行**了",
    WHY_NOT_ENOUGH: "那条 i8 名单里剩下的候选**不足 2 个**（下次同步系统自己就建了，不必打扰人）",
}


def _scan_rows(session: Session, raw_items: list[dict]) -> list[dict]:
    """把同步报出的**每一条**过一遍现算 ⇒ 逐条给出结论：`{keep, why, ...}`。

    ⭐⭐ **只此一处判**：`live_items`（留下的）与 `dropped_items`（丢掉的 ＋ 为什么）**都从这儿切**
    —— 写两遍判据 = 同一个事实有两个主人（本仓铁律，那种地方必然走形）。

    ⚠️ 为什么还要把"丢掉的"报出来（`TAIL-190` · 2026-09-29 真机报障）：丢是**对的**（清单是线索、
    档案现在才是真相），但**原先壳上一个字都不说** ⇒ 用户看到的是「回执说有待人工 2 条、
    卡是空的」✗✗（本仓最贵那类**静默**）。⇒ 现在丢掉也要**有理由、有去处**。
    """
    taken, have_full = _snapshot(session)
    out: list[dict] = []
    for raw in raw_items:
        full = str(raw.get("name_full") or "")
        whs = [str(w) for w in (raw.get("warehouses") or []) if str(w)]
        if not full:
            continue                                   # 连全名都没有 ⇒ 无从谈起（不进任何一侧）
        if not whs:
            # ⚠️ 按 `kind` 分（⛔ 不看中文 `reason`）：壳下小微那类**本来就不属本卡**
            why = WHY_SHELL if raw.get("kind") == ARCHIVE.MANUAL_SHELL else WHY_NO_WH
            out.append({"keep": None, "why": why, "full_name": full,
                        "reason": str(raw.get("reason") or "")})
            continue
        if norm_full_name(full) in have_full:
            out.append({"keep": None, "why": WHY_HAS_ROW, "full_name": full,
                        "reason": str(raw.get("reason") or "")})
            continue
        left = [w for w in whs if w not in taken]
        if len(left) < 2:
            out.append({"keep": None, "why": WHY_NOT_ENOUGH, "full_name": full,
                        "reason": str(raw.get("reason") or "")})
            continue
        out.append({"keep": {
            "full_name": full,
            "phid": str(raw.get("phid") or ""),
            "warehouses": left,          # ⭐ 界面能选的候选 = **i8 名单里那条**、且尚未被占用
            "stored_warehouses": whs,    # 当时同步报出来的全部（留痕：看得见"少了谁"）
            "reason": str(raw.get("reason") or ""),
        }, "why": ""})
    return out


def live_items(session: Session) -> list[dict]:
    """待人工建档清单：最近一次同步报出的那几条，**逐条按当前档案现算**。

    一条**仍然成立**要同时满足（只要有一条不成立，就**当场丢掉** —— 清单是**线索**，
    档案现在的样子才是**真相**；⛔ 摆着已解决的让人白干 = `TAIL-41` 同族）：

    ① 该全名在档案里**还没有任何行**（有人刚挑过 / 别处刚建过 ⇒ 这条已经没了）；
    ② 那条同步记录里给的仓库清单里，**还有 ≥2 个**没被任何档案行占用
       （只剩 1 个 ⇒ 下次同步系统**自己就建了**，不必打扰人）。

    ⚠️ 全名比较走**归一化出口** `norm_full_name`（`ACC-PRJ-NAME-001` 的唯一出口）；
       与 `sync_service.existing`（原样比较）的差别仅在**尾码 / 空白** —— 归一化更**保守**：
       ⛔ 宁可少列一条，也不重复建行。
    ⭐ 判据**只此一处**（`_scan_rows`）—— 本函数只是把"留下的"挑出来。
    """
    return [r["keep"] for r in _scan_rows(session, latest_pending(session)["items"]) if r["keep"]]


def dropped_items(session: Session) -> list[dict]:
    """⭐ **被现算丢掉的那几条 ＋ 为什么**（`TAIL-190`）—— 丢是对的，但**不许静默**：

    `m01` 那张卡要如实说明「这次同步报出 N 条，其中 M 条不属本卡 ＋ 各自去哪」，
    否则用户看着"回执说有待人工、卡却是空的"，只能猜是不是坏了（2026-09-29 实测报障）。
    """
    rows = _scan_rows(session, latest_pending(session)["items"])
    return [{"full_name": r["full_name"], "why": r["why"], "why_text": _WHY_TEXT[r["why"]],
             "reason": r.get("reason", "")} for r in rows if not r["keep"]]


def live_pending(session: Session) -> dict:
    """`m01` 那个入口要的全部：**清单 ＋ 它来自哪一次同步**（⛔ 不装作"刚刚"—— 如实标来源）。

    ⭐ `dropped_items`（＋ `dropped` 计数）＝ 丢掉的那几条**连同理由与去处**（见 `dropped_items`）。
    """
    src = latest_pending(session)
    rows = _scan_rows(session, src["items"])
    items = [r["keep"] for r in rows if r["keep"]]
    dropped = [{"full_name": r["full_name"], "why": r["why"], "why_text": _WHY_TEXT[r["why"]],
                "reason": r.get("reason", "")} for r in rows if not r["keep"]]
    return {
        "found": src["found"],
        "items": items,
        "dropped_items": dropped,
        "source": {"target": src["target"], "at": src["at"], "run_record_id": src["run_record_id"]},
        "dropped": len(dropped),
    }


# ------------------------------------------------------------------ 写（选定一个仓库 ⇒ 建行）


def pick_row(session: Session, *, full_name: str, warehouse_name: str) -> Project:
    """人**选定一个仓库** ⇒ 就地建行（`TAIL-45`）。返回新建的档案行。

    两条守卫（都**显式报出**，⛔ 不静默、也不给"只剩一个候选所以自动选中"这种自作聪明）：
    ① 这一对（全名 ＋ 仓库名）必须**出现在「待人工」清单里** —— 该全名得**还没有档案行**（决策 2
       「普通项目 ↔ 仓库 = 1 : 1」，也防"别人刚挑过"）、该仓库名得**来自那次同步报出的 i8 名单**
       （§9.4：仓库名是 i8 的，⛔ 不许人手打）；
    ② 这个仓库名**没被别的行占用** —— 仓库名是**唯一标识**（唯一约束在库上）。
    ⚠️ **这两条的判据都已在 `live_items` 的现算里生效**（已有行 ⇒ 整条丢掉；被占用的仓库 ⇒
       不进候选）⇒ 本层只把它们**报成一句人话**，⛔ **不再各写一遍判据**（写两遍就是两份副本 ——
       本仓老纪律；而且那种"守卫"永远到不了，是**死代码**，2026-09-18 实测踩到）。
    """
    full = str(full_name or "").strip()
    wh = str(warehouse_name or "").strip()
    if not full or not wh:
        raise MustReportError("「指明全名 ＋ 选定一个仓库」两项都必填（⛔ 仓库名不许留空让人猜）")

    hit = next((it for it in live_items(session)
                if norm_full_name(it["full_name"]) == norm_full_name(full)), None)
    if hit is None:
        raise MustReportError(
            "这条已不在「待人工建档」清单里（可能刚被挑过 / 已经建了行）—— 请刷新页面再看"
        )
    if wh not in hit["warehouses"]:
        raise MustReportError(
            f"「{wh}」不在这次同步报出的候选里（候选：{'、'.join(hit['warehouses'])}）—— "
            "可能是它**已被别的档案行占用**（仓库名是唯一标识），或**本来就不在 i8 名单里**；"
            "⛔ 仓库名以 i8 名单为准，不许手填（§9.4）"
        )

    # ⭐ 类型判定走 `MOD-01` 唯一出口（⛔ 不在这里另立规则）：候选里只剩它一个 ⇒ 与链路 A 落同一判决
    project_type = classify_name(full, [wh], small_keyword=DEFAULT_SMALL_KEYWORD)
    return create_project(
        session, project_type=project_type, name_full=full, warehouse_name=wh,
        phid=str(hit.get("phid") or ""),
    )


__all__ = ["RECORD_KEY", "TARGET_OF_SYNC", "LOOKBACK", "record_detail",
           "is_common_project_sync", "latest_pending", "live_items", "dropped_items",
           "live_pending", "pick_row",
           "WHY_SHELL", "WHY_NO_WH", "WHY_HAS_ROW", "WHY_NOT_ENOUGH"]
