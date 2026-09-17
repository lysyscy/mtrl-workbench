"""项目档案域内核（**纯函数** · 可离线单测）。

依据：《说明书》§2.2（三类判定）· §2.3.2（尾码剥离）· §2.5.1（归属/链路 C）· §2.7.2（归档不变式）·
      §2.7.3（ord）· §2.7.1 / §2.7.4（候选 键与显示）· §9.2（核算年月）
      下沉专项《全自动建档-实施计划》§二 决策 1–6 · §三 链路 A/B/C

⚠️ 本模块**不连库、不碰网络**：只对"档案行集合"做判定，DB/HTTP 由调用方（repository / router）注入。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.core.errors import MustReportError
from app.mod01_projects.models import (
    PLACEHOLDER_PREFIX,
    STATUS_ACTIVE,
    STATUS_ARCHIVED,
    TYPE_NORMAL,
    TYPE_SHELL,
    TYPE_SMALL,
    Project,
)

DEFAULT_SMALL_KEYWORD = "小微"

# ============================================================ §2.3.2 尾码剥离

# 最宽规则（决策 6）：字母 ≥2 + 数字 ≥1
_CODE = r"[A-Za-z]{2,}\d+"
_PAREN_CODE_RE = re.compile(rf"\s*[(（]\s*{_CODE}\s*[)）]\s*$")
_BARE_CODE_RE = re.compile(rf"\s+{_CODE}\s*$")


def strip_trailing_code(name: str, *, pattern: str = _CODE) -> str:
    """剥离项目全名尾部的 `(XMCB2025080001)` 式项目代码（§2.3.2，**最宽规则**）。

    **三处共用**：付款通知书导出 · 仓库列表同步 · 项目列表同步。
    """
    if not name:
        return name or ""
    s = str(name).strip()
    paren = re.compile(rf"\s*[(（]\s*{pattern}\s*[)）]\s*$")
    bare = re.compile(rf"\s+{pattern}\s*$")
    m = paren.search(s)
    if m:
        return s[: m.start()].strip()
    m = bare.search(s)
    if m:
        return s[: m.start()].strip()
    return s


def norm_full_name(name: str) -> str:
    """全名归一（比较用）：先剥尾码、再压缩空白。"""
    return re.sub(r"\s+", " ", strip_trailing_code(name or "")).strip()


# ============================================================ §2.2.1 三类判定


def classify_name(
    name_full: str,
    warehouses_of_name: list[str] | None = None,
    *,
    small_keyword: str = DEFAULT_SMALL_KEYWORD,
    manual_override: str | None = None,
) -> str:
    """三类项目自动判定（双轨 ＋ 兜底 ＋ 人工覆盖，决策 1）。

    - `manual_override` ∈ {`normal`,`shell`} 优先（人工覆盖是"兜底中的兜底"）
    - 全名含「小微」（**关键字配置化**）⇒ 壳
    - 否则：该全名挂 **≥2 个仓库** ⇒ `needs_confirm`（兜底弹窗）；否则 ⇒ 普通项目
    """
    if manual_override in (TYPE_NORMAL, TYPE_SHELL):
        return manual_override
    if small_keyword and small_keyword in (name_full or ""):
        return TYPE_SHELL
    if len(warehouses_of_name or []) >= 2:
        return "needs_confirm"
    return TYPE_NORMAL


def derive_type_from_warehouse(warehouse_owner_full_name: str, *, shell_full_names: set[str]) -> str:
    """推导判据：仓库的「所属项目全名」= 某壳全名 ⇒ 该仓库是**具体小微**；否则是**普通项目**。"""
    return TYPE_SMALL if norm_full_name(warehouse_owner_full_name) in shell_full_names else TYPE_NORMAL


# ============================================================ §2.5.1 归属（链路 C）


@dataclass
class OwnershipDecision:
    kind: str                       # normal / small / needs_choice / needs_keyword / not_archived
    target_id: int | None = None
    shell_id: int | None = None
    matched_ids: list[int] = field(default_factory=list)
    keyword_to_add: str | None = None
    reason: str = ""

    @property
    def settled(self) -> bool:
        """归属是否"走完"（可入库）。⚠️ 未走完 ⇒ **整批不入库**（001-08）。"""
        return self.kind in ("normal", "small")


def resolve_ownership(
    *,
    name_full: str,
    doc_name: str = "",
    projects: list[Project],
    small_keyword: str = DEFAULT_SMALL_KEYWORD,
) -> OwnershipDecision:
    """判定一行付款通知书的**归属**（§2.5.1 · 链路 C · 铁律 §9.8-6）。

    ⚠️ **先判断是不是壳，不要直接拿全名去撞项目表**。
    ⚠️ 匹配范围**只在该壳下、不跨壳**；**含已归档的小微**（001-07）。
    """
    key = norm_full_name(name_full)

    # 壳（可有多个同全名行，但只有一条是壳）
    shells = [p for p in projects if p.project_type == TYPE_SHELL and norm_full_name(p.name_full) == key]
    if shells:
        shell = shells[0]
        smalls = [p for p in projects if p.parent_shell_id == shell.id]  # 含归档（001-07）
        matched = [p for p in smalls if hit_keyword(p.match_keywords, doc_name)]
        if len(matched) == 1:
            return OwnershipDecision(
                "small",
                target_id=matched[0].id,
                shell_id=shell.id,
                keyword_to_add=first_hit_keyword(matched[0].match_keywords, doc_name),
            )
        if len(matched) > 1:
            return OwnershipDecision(
                "needs_choice",
                shell_id=shell.id,
                matched_ids=[p.id for p in matched],
                reason="单据名命中该壳下多个具体小微 ⇒ 需用户指定",
            )
        return OwnershipDecision(
            "needs_keyword",
            shell_id=shell.id,
            reason="单据名未命中该壳下任何小微 ⇒ 需用户指定（选已有小微并补词 / 新建小微）",
        )

    # 普通项目：全名唯一命中（决策 2 推论）⇒ 归属天生确定，永不「待指定」
    normals = [p for p in projects if p.project_type == TYPE_NORMAL and norm_full_name(p.name_full) == key]
    if normals:
        return OwnershipDecision("normal", target_id=normals[0].id)

    # 壳未建档 / 项目未建档 ⇒ 走链路 A 建档（**不得用全名反查命中已存在的小微**，§9.8-6）
    return OwnershipDecision("not_archived", reason="未建档 ⇒ 需走链路 A（抓 phid → 抓仓库 → 建档）")


def hit_keyword(keywords: list[str] | None, doc_name: str) -> bool:
    text = doc_name or ""
    return any(k and k in text for k in (keywords or []))


def first_hit_keyword(keywords: list[str] | None, doc_name: str) -> str | None:
    text = doc_name or ""
    for k in keywords or []:
        if k and k in text:
            return k
    return None


def validate_keyword_in_doc(keyword: str, doc_name: str) -> str:
    """拟补的关键词**必须出现在单据名里**，否则**拒绝归集**（001-05，不得静默写入）。"""
    kw = (keyword or "").strip()
    if not kw:
        raise MustReportError("关键词不能为空 —— 归集需要能证明该行属于该小微的词")
    if kw not in (doc_name or ""):
        raise MustReportError(
            f"关键词「{kw}」未出现在单据名里 ⇒ **拒绝归集**（不得当作归属依据）。"
            "请换一个确实出现在单据名中的词，或改判为「新小微」。"
        )
    return kw


def append_keyword_dedup(existing: list[str] | None, keyword: str) -> list[str]:
    """关键词**去重追加**（001-06）。"""
    out = list(existing or [])
    kw = (keyword or "").strip()
    if kw and kw not in out:
        out.append(kw)
    return out


def ensure_batch_settled(decisions: list[OwnershipDecision]) -> None:
    """归属**未走完 ⇒ 整批不入库**（001-08）—— 库里不得出现「待指定」的行。"""
    unsettled = [d for d in decisions if not d.settled]
    if unsettled:
        raise MustReportError(
            f"归属未走完（{len(unsettled)} 行）⇒ **整批不入库**；"
            "请先把每一行的归属指定完（不得留下「待指定」的行）。"
        )


# ============================================================ §2.7.2 归档不变式


@dataclass
class StatusChange:
    allowed: bool
    writes: list[dict] = field(default_factory=list)        # ⚠️ **只含 status**（001-06：不动任何业务数据）
    blocked_by: list[dict] = field(default_factory=list)   # 未归档小微（讲清为什么）
    follow_ups: list[dict] = field(default_factory=list)   # 联动变更（壳自动归档）
    message: str = ""


def apply_status_change(project: Project, new_status: str, projects: list[Project]) -> StatusChange:
    """判定一次状态变更（§2.7.2 不变式，双向对称）。

    - **正向**：壳 → 归档，若壳下还有在建小微 ⇒ **拦截**（状态不改、**不写留痕**），并列出未归档的小微。
    - **反向**：归档壳下**最后一个在建小微** ⇒ 壳**自动跟着归档**（`follow_ups` 带出，需给壳单独留痕）。
    - 归档 ⇄ 在建**可来回改**（不锁死；001-07）。
    - ⚠️ `writes` **只含 `status` 一个字段**（001-06）—— 归档**不动任何业务数据**。
    """
    def _status_write(pid: int, value: str) -> dict:
        return {"id": pid, "field": "status", "value": value}

    if project.project_type == TYPE_SHELL and new_status == STATUS_ARCHIVED:
        active = [
            p for p in projects
            if p.parent_shell_id == project.id and p.status == STATUS_ACTIVE
        ]
        if active:
            return StatusChange(
                allowed=False,          # 状态不改
                writes=[],              # 不写留痕
                blocked_by=[_brief(p) for p in active],
                message=(
                    "该壳下仍有在建的具体小微，不能归档。请先把下列小微逐个归档："
                    + "、".join((p.disp or p.warehouse_name or str(p.id)) for p in active)
                ),
            )
        return StatusChange(allowed=True, writes=[_status_write(project.id, STATUS_ARCHIVED)])

    if project.project_type == TYPE_SMALL and new_status == STATUS_ARCHIVED and project.parent_shell_id:
        remaining = [
            p for p in projects
            if p.parent_shell_id == project.parent_shell_id
            and p.id != project.id
            and p.status == STATUS_ACTIVE
        ]
        if not remaining:
            shell = next((p for p in projects if p.id == project.parent_shell_id), None)
            if shell is not None:
                return StatusChange(
                    allowed=True,
                    writes=[
                        _status_write(project.id, STATUS_ARCHIVED),
                        _status_write(shell.id, STATUS_ARCHIVED),   # 壳自动跟随
                    ],
                    follow_ups=[{
                        **_brief(shell),
                        "reason": "壳下最后一个在建小微已归档 ⇒ 壳自动跟着归档（反向对称）",
                        "needs_log": True,
                    }],
                )
        return StatusChange(allowed=True, writes=[_status_write(project.id, STATUS_ARCHIVED)])

    # 普通项目归档 / 任何状态的改回（不锁死）
    return StatusChange(allowed=True, writes=[_status_write(project.id, new_status)])


def can_create_small(shell: Project) -> None:
    """**已归档的壳下不许新建具体小微**（会当场破坏不变式）⇒ 拦截（001-05）。"""
    if shell.project_type == TYPE_SHELL and shell.status == STATUS_ARCHIVED:
        raise MustReportError(
            f"壳「{shell.name_full}」已归档，其下不能新建具体小微"
            "（新小微必然是在建，会当场破坏归档不变式）。确实要新建，请先把壳改回「在建」。"
        )


def _brief(p: Project) -> dict:
    return {
        "id": p.id,
        "warehouse_name": p.warehouse_name,
        "disp": p.disp or p.warehouse_name or "",
        "status": p.status,
        "project_type": p.project_type,
    }


# ============================================================ §2.7.3 自定义排序（ord）

# 状态的中文标签（**唯一出口**）—— `status` 列存英文（技术栈 §3.2），界面按原型取值显示中文
# （原型 `pjStatus: {vals:['在建','归档']}`）。⚠️ 别在页面里各写一份 `== "archived" ? "归档" : "在建"`。
STATUS_LABELS: dict[str, str] = {STATUS_ACTIVE: "在建", STATUS_ARCHIVED: "归档"}


def status_label(status: str) -> str:
    """状态 → 中文标签（认不出 ⇒ 原样返回，**不臆造**）。

    ⚠️ 反向（标签 → 状态值）**刻意不提供** —— 筛选入参用的是**标签本身**
       （交互规格取值 = 原型 `pjStatus`），不需要反查；多一个反向出口就多一处会漂的映射。
    """
    return STATUS_LABELS.get(str(status or ""), str(status or ""))


def order_key(index: int):
    """排序键：**归档后置 > ord > 原序**（§2.7.3）。"""
    def _k(p: Project):
        return (p.status == STATUS_ARCHIVED, p.ord or 0, index)
    return _k


def ordered(projects: list[Project]) -> list[Project]:
    """按「归档后置 > ord > 原序」返回（全站同一顺序，001-02/001-05）。"""
    indexed = list(enumerate(projects))
    indexed.sort(key=lambda t: (t[1].status == STATUS_ARCHIVED, t[1].ord or 0, t[0]))
    return [p for _, p in indexed]


def reorder(
    projects: list[Project],
    *,
    project_id: int,
    to_position: int | None = None,
    direction: str | None = None,
) -> list[tuple[int, int]]:
    """自定义排序（§2.7.3）→ 返回重编号后的 `[(id, ord)]`，序号 **1..N 连续无重复**。

    - `to_position`（1-based）= **插到那个位置**（不是改数字本身，001-03）
    - `direction` ∈ {`up`,`down`} = 与**相邻一行对调**（001-03）
    - ⚠️ **不得跨过「在建 / 归档」分界**（001-06）
    - ⚠️ **不留痕**（001-07，只是展示顺序）
    """
    if not projects:
        return []
    seq = ordered(projects)
    ids = [p.id for p in seq]
    if project_id not in ids:
        raise MustReportError(f"档案行不存在：id={project_id}")

    moving = next(p for p in seq if p.id == project_id)
    group = [i for i, p in enumerate(seq) if (p.status == STATUS_ARCHIVED) == (moving.status == STATUS_ARCHIVED)]
    if not group:
        group = [ids.index(project_id)]
    pos_in_group = group.index(ids.index(project_id))

    if to_position is not None:
        # 插到「同组内」第 to_position 位（越界夹紧；不跨分界）
        target = max(1, min(int(to_position), len(group))) - 1
        target_idx = group[target]
    elif direction in ("up", "down"):
        delta = -1 if direction == "up" else 1
        new_pos = pos_in_group + delta
        if new_pos < 0 or new_pos >= len(group):
            target_idx = ids.index(project_id)  # 到边界：不动（不跨分界）
        else:
            target_idx = group[new_pos]
    else:
        raise ValueError("reorder 需要 to_position 或 direction")

    cur_idx = ids.index(project_id)
    item = seq.pop(cur_idx)
    seq.insert(target_idx, item)
    return [(p.id, i + 1) for i, p in enumerate(seq)]


# ============================================================ §2.7.1 / §2.7.4 候选


@dataclass
class Candidate:
    key: str        # **仓库名**（唯一标识 / 比较用）
    display: str    # **展示名**
    archived: bool
    placeholder: bool = False


def build_candidates(projects: list[Project]) -> list[Candidate]:
    """项目候选（全站统一，§2.7.1 / §2.7.4）。

    - **键 = 仓库名 · 显示 = 展示名**（001-02）
    - **只有能定位到仓库的档案进候选**（001-03）；**壳没有仓库 ⇒ 不进候选**（001-04）
    - **含归档 · 排最后 · 带标注**（001-01；顺序 = 自定义排序）
    """
    rows = [p for p in projects if p.has_warehouse]
    return [
        Candidate(
            key=p.warehouse_name or "",
            display=p.disp or p.warehouse_name or "",
            archived=p.status == STATUS_ARCHIVED,
            placeholder=p.is_placeholder,
        )
        for p in ordered(rows)
    ]


def multi_select_keys(selected: list[str] | None, all_keys: list[str]) -> list[str]:
    """多选语义（001-05）：**空选 = 全部**；多选取**并集**。"""
    sel = [s for s in (selected or []) if s]
    if not sel:
        return list(all_keys)
    return [k for k in all_keys if k in set(sel)]


def combine_filters(*filters: list[str] | None) -> list[str]:
    """与其它筛选条件按「**与**」组合（001-05）—— 返回各组选集的**交集**。"""
    sets = [set(f) for f in filters if f]
    if not sets:
        return []
    acc = set.intersection(*sets)
    return sorted(acc)


def resolve_display(name_full: str, projects: list[Project]) -> str:
    """展示名解析（001-06）：无匹配 ⇒ **显式标「未建档」**（不得静默留空）；壳全名多命中 ⇒ **「待指定」**。"""
    key = norm_full_name(name_full)
    hits = [p for p in projects if norm_full_name(p.name_full) == key]
    if not hits:
        return "未建档"
    if not any(p.is_shell for p in hits):
        return hits[0].disp or hits[0].warehouse_name or ""

    shells = [p for p in hits if p.is_shell]
    children = [p for p in projects if p.parent_shell_id in {s.id for s in shells}]
    if len(children) != 1:
        return "待指定"  # 壳全名：落在哪个小微未定 ⇒ 可点待指定
    return children[0].disp or children[0].warehouse_name or ""


# ============================================================ §9.2 核算年月
# ⚠️ **已上移到 `app.core.period`**（`MOD-01` / `MOD-02` **共用**，见《说明书》§9.2）
#    ⇒ 时间口径一律 `from app.core.period import ...`；本模块不再自带一份。


__all__ = [
    "PLACEHOLDER_PREFIX", "TYPE_NORMAL", "TYPE_SHELL", "TYPE_SMALL",
    "strip_trailing_code", "norm_full_name", "classify_name", "derive_type_from_warehouse",
    "OwnershipDecision", "resolve_ownership", "hit_keyword", "first_hit_keyword",
    "validate_keyword_in_doc", "append_keyword_dedup", "ensure_batch_settled",
    "StatusChange", "apply_status_change", "can_create_small",
    "ordered", "reorder", "Candidate", "build_candidates",
    "multi_select_keys", "combine_filters", "resolve_display",
]
