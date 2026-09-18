"""建档计划（切片 2 · **阶段 2「占位建档 · 链路 A」**）—— **纯函数**，不连库、不写路由。

规则主人 =《全自动建档-实施计划》**§三 链路 A** ＋《说明书》**§2.4.2**；
类型判定**走 `MOD-01` 唯一出口** `domain.classify_name`（**不另立规则**）。

链路 A ③ 的三条分支 —— 本模块的口径是「**能自动定的自动建、要人定的显式列出、绝不静默跳过**」：

| 全名对应的仓库数 | 处置 |
|---|---|
| **恰好 1 个** | 建档，带**真实仓库名** |
| **≥2 个** | ⛔ **不自动建** ⇒ 进 `manual`（原口径："列出让用户选，只建选中的那个"） |
| **0 个** | 建档，`warehouse_name` = **占位名**（`未建仓-序号`）、`name_full` **仍写全名**（扶正的钥匙） |

另两条也是"保留人工环节"的（有意为之，不是漏）：

- 含「小微」的全名 ⇒ **壳**（`shell`、无仓库）；其**壳下的仓库** = 「具体小微」⇒ 进 `manual`
  （关键词必须"出现在单据名里"，属链路 C 的人工确认）。
- **仓库侧有、常用项目侧没有**（无 `phid`）⇒ 进 `no_phid`，提示"请先加入 i8 常用项目列表"（链路 A ③-a）。
"""

from __future__ import annotations

from app.mod01_projects.domain import DEFAULT_SMALL_KEYWORD, classify_name
from app.mod01_projects.models import (
    PLACEHOLDER_PREFIX,
    STATUS_ACTIVE,
    TYPE_NORMAL,
    TYPE_SHELL,
)

#: 新建档案行的状态（链路 A 关键点：「占位行 `status` 填**在建**」）
NEW_STATUS = STATUS_ACTIVE

#: 计划的四类（**都要给，禁静默**）
PLAN_KEYS: tuple[str, ...] = ("create", "exists", "manual", "no_phid")


def warehouses_by_owner(warehouse_rows: list[dict] | None) -> dict[str, list[str]]:
    """仓库名单 → `{项目全名: [仓库名, ...]}`（**去重、保序**；缺任一侧的行跳过）。"""
    out: dict[str, list[str]] = {}
    for r in warehouse_rows or ():
        owner = str(r.get("owner_full_name") or "").strip()
        name = str(r.get("warehouse_name") or "").strip()
        if not owner or not name:
            continue
        bucket = out.setdefault(owner, [])
        if name not in bucket:
            bucket.append(name)
    return out


def next_placeholder(taken: set[str] | frozenset[str]) -> str:
    """下一个可用占位名 `未建仓-N`（N 从 1 起，**跳过已占用的**）。"""
    n = 1
    while f"{PLACEHOLDER_PREFIX}{n}" in taken:
        n += 1
    return f"{PLACEHOLDER_PREFIX}{n}"


def plan_archive(
    *,
    common_rows: list[dict] | None,
    warehouse_rows: list[dict] | None,
    existing: set[str] | frozenset[str] | None = None,
    taken_names: set[str] | frozenset[str] | None = None,
    shell_keyword: str = DEFAULT_SMALL_KEYWORD,
) -> dict:
    """→ 计划 `{create, exists, manual, no_phid}`（四类都给）。

    - `existing` = **已在档案的项目全名**（幂等依据：链路 A ①「全名已在档案 ⇒ 归集、结束」）
    - `taken_names` = **已占用的仓库名**（占位名取号用；含已有的占位行）
    """
    by_owner = warehouses_by_owner(warehouse_rows)
    existing_names = {str(x).strip() for x in (existing or ()) if str(x).strip()}
    taken = {str(x).strip() for x in (taken_names or ()) if str(x).strip()}
    shell_names = {n for n in by_owner if shell_keyword and shell_keyword in n}

    create: list[dict] = []
    exists: list[dict] = []
    manual: list[dict] = []
    seen_common: set[str] = set()

    def _shell_reason(whs: list[str], *, already: bool) -> str:
        head = "壳已在档，但壳下" if already else "壳下"
        return (f"{head}具体小微（{len(whs)} 个仓库：{'、'.join(whs)}）"
                "需配「出现在单据名里」的关键词 —— 走建档向导人工建")

    for row in common_rows or ():
        name = str(row.get("name_full") or "").strip()
        phid = str(row.get("phid") or "").strip()
        if not name or not phid:
            continue                                     # 没 phid 就没法抓数 ⇒ 不进 plan（由 no_phid 侧兜）
        seen_common.add(name)

        whs = by_owner.get(name, [])
        kind = classify_name(name, whs, small_keyword=shell_keyword)
        # ⚠️ 只看**尚未有档案行**的仓库（按「仓库名是唯一标识」判在不在档）——
        #    已经建过行的小微不该被反复列出。⚠️ 必须在 ① 之前算，否则会被下面的短路吞掉。
        gap_whs = [w for w in whs if w not in taken]

        if name in existing_names:                       # 链路 A ①：归集、结束
            exists.append({"name_full": name, "phid": phid})
            # ⭐ **归集「结束」≠ 壳下具体小微也结束了** —— 001-06 的「显式列出」与壳在不在档**无关**：
            #    壳早就在档、而它名下的仓库还没建行（本轮实测：`兰考金不换前置车间项目` 就是这样
            #    被静默吞掉的）⇒ 仍要列出，否则新仓库永远只在报表里、不在档案里。
            if kind == TYPE_SHELL and gap_whs:
                manual.append({"name_full": name, "phid": phid,
                               "reason": _shell_reason(gap_whs, already=True)})
            continue

        if kind == TYPE_SHELL:
            create.append({"name_full": name, "phid": phid,
                           "project_type": TYPE_SHELL, "warehouse_name": None})
            if gap_whs:                                  # 壳下的仓库 = **具体小微** ⇒ 人工
                manual.append({"name_full": name, "phid": phid,
                               "reason": _shell_reason(gap_whs, already=False)})
            continue

        if len(whs) >= 2:                                # 原口径：列出让用户选
            manual.append({
                "name_full": name, "phid": phid,
                # ⭐ **结构化候选仓库清单**（`TAIL-45`）：只给一句 `reason` 文案，界面**没法让人"选"**
                #    —— 选定之后要把那个仓库名**原样**交给建档口（⛔ 不许人手打，§9.4：仓库名是 i8 的）。
                "warehouses": list(whs),
                "reason": f"挂 {len(whs)} 个仓库（{'、'.join(whs)}）—— 需人工选一个再建",
            })
            continue

        if len(whs) == 1:                                # 唯一仓库 ⇒ 带真实仓库名
            create.append({"name_full": name, "phid": phid,
                           "project_type": TYPE_NORMAL, "warehouse_name": whs[0]})
            continue

        placeholder = next_placeholder(taken)             # 无仓库 ⇒ 占位行（全名仍写全名）
        taken.add(placeholder)
        create.append({"name_full": name, "phid": phid,
                       "project_type": TYPE_NORMAL, "warehouse_name": placeholder})

    no_phid = [
        {"name_full": owner, "warehouses": list(whs),
         "reason": "该全名有仓库、却不在 i8 常用项目列表（无 phid）—— "
                   "请先把它加入 i8 常用项目列表，再同步一次"}
        for owner, whs in by_owner.items()
        if owner not in seen_common and owner not in existing_names and owner not in shell_names
    ]
    return {"create": create, "exists": exists, "manual": manual, "no_phid": no_phid}


def counts_of(plan: dict | None) -> dict[str, int]:
    """四类计数（回执用；`plan=None` ⇒ 全 0）。"""
    return {k: len((plan or {}).get(k) or ()) for k in PLAN_KEYS}


__all__ = ["NEW_STATUS", "PLAN_KEYS", "warehouses_by_owner", "next_placeholder",
           "plan_archive", "counts_of"]
