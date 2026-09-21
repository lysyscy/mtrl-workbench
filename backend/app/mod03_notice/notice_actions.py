"""`MOD-03` 付款通知书的**行级动作 · 域内核**（能力 2 / 3 ＋ 统计手改）—— 纯函数与**唯一出口**。

依据：
- 《说明书》§4.2.2（剔除与恢复：**按勾选行**生效 · **只恢复人工剔除** · 混档必须**分开回报**）
- §4.2.3 / §4.2.4（分类**只有三类**，没有"其他"；**手改后重抓不被覆盖**）
- §4.5.3（统计金额手改：**唯一出口** ＋ 超上限拦截 ＋ 留痕）
- §9.8.2-5（一切写操作**按 id 定位**，禁止用名字反查）

⚠️ 本模块只做**判定与字段组装**；落库在 `repository`、动作入口在 `notice_api_router`。
⚠️ 「恢复剔除」**复用 `classify.restore_excluded`**（同一出口，不另写一套判定）。

⚠️ **2026-09-21（`T5` 拆分：614 行 ⇒ ≤400）**：另两块**整体搬出本件**（⛔ 别再搬回来）——
  · 能力 4 · **手动新增行 / 编辑 / 删除** ⇒ `mod03_notice/notice_manual_actions.py`（§4.2.6）；
  · **批量付款**（默认值 / 金额解析 / 提交出口）⇒ `mod03_notice/notice_pay_actions.py`（§4.4.2 / §4.4.4）。
  本件此后只管**分类 · 剔除 · 统计手改**；三件都从同一个 `repository` 落库，判定各归各家。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.errors import MustReportError
from app.mod03_notice.classify import (  # noqa: F401  ← 「恢复剔除」直接复用，不重写
    RestoreReport,
    apply_manual_exclude,
    restore_excluded,
)
from app.mod03_notice.models import EXCLUDE_BY_MANUAL, EXCLUDE_BY_RULE, EXCLUDE_NONE
from app.mod05_flow.domain import CATEGORY_MATERIAL
from app.mod05_flow.models import CATEGORIES


# 分类的中文名（**唯一出口**；页面不再各写一份 colmap）
CATEGORY_NAMES: dict[str, str] = {
    "material": "辅材",
    "mechanical": "机械",
    "jc": "集采",
}

# §4.2.3：**只有三类**、没有"其他"
CATEGORY_CHOICES: tuple[str, ...] = CATEGORIES


def jc_supplier_problem(row) -> str | None:
    """「**集采实际供应商**」能否写（§6.6.3 · `DEV-P-04`）⇒ `None` = 可写。

    ⚠️ **只有「集采」分类的通知书**能填 —— 该字段是「按供应商统计欠款」与
       **集采台账付款引用的候选收窄**两件事的**关联锚点**；别的分类填了没有意义。
    ⛔ 判定**只许有这一处**（这个出口 + API 端点调它）：前端不许再自行判定后"假装成功"。
    """
    from app.mod03_notice.list_view import CATEGORY_JC

    if row is None:
        return "找不到该付款通知书"
    if str(getattr(row, "category", "") or "") != CATEGORY_JC:
        return "仅「集采」分类的记录可填集采实际供应商（DEV-P-04）"
    return None


def category_name(value: str) -> str:
    return CATEGORY_NAMES.get(str(value or "").strip(), str(value or "").strip() or "—")


# ============================================================ 能力 2 · 批量改分类（§4.2.4）

# 手改分类**不设留痕**（§9.3 明确"不留痕"），但**重抓不被覆盖**由 `merge.PROTECTED` 保证 ——
# 本模块**不另开"已手改"状态位**（同一事实两处存 ⇒ 副本必然静默过期）。


@dataclass
class CategoryChange:
    """批量改分类的结果（三类分别报，便于逐条核对）。"""

    category: str = ""
    changed: list[int] = field(default_factory=list)
    unchanged: list[int] = field(default_factory=list)
    missing: list[int] = field(default_factory=list)

    @property
    def message(self) -> str:
        label = category_name(self.category)
        parts = [f"已把 {len(self.changed)} 行改为「{label}」"]
        if self.unchanged:
            parts.append(f"另有 {len(self.unchanged)} 行本就是「{label}」、未变")
        if self.missing:
            parts.append(f"另有 {len(self.missing)} 行不在当前数据里、跳过")
        parts.append("分类改动**落库、不留痕**，且再次抓取**不被覆盖**（§4.2.4）")
        return "；".join(parts)


def change_category(rows: list[dict], picked, category: str) -> CategoryChange:
    """**批量改分类**（§4.2.4）—— 只能改成辅材 / 机械 / 集采三类。

    ⚠️ 与「批量剔除」同款：**必须先勾选**（批量 = 对勾选集操作，不是"对整表操作"）。
    ⚠️ 手改后的分类**不被再次抓取覆盖**（`merge.PROTECTED` 落库侧保证）。
    """
    cat = str(category or "").strip()
    if cat not in CATEGORY_CHOICES:
        allowed = " / ".join(category_name(c) for c in CATEGORY_CHOICES)
        raise MustReportError(f"分类只能是「{allowed}」三类，没有「其他」类（§4.2.3）")

    want = {int(x) for x in (picked or ())}
    if not want:
        raise MustReportError("批量改分类必须先勾选要改的行（§4.2.4）")

    result = CategoryChange(category=cat)
    seen: set[int] = set()
    for row in rows or ():
        rid = int(row.get("id") or 0)
        if rid not in want:
            continue
        seen.add(rid)
        if str(row.get("category") or "").strip() == cat:
            result.unchanged.append(rid)
        else:
            result.changed.append(rid)
    result.missing = sorted(want - seen)
    return result


# ============================================================ 能力 3 · 批量剔除 / 恢复剔除（§4.2.2）


@dataclass
class ExcludeReport:
    """**人工批量剔除**的结果（来源 = `manual`，只有这一类能被「恢复剔除」放开）。"""

    marked: list[int] = field(default_factory=list)
    already: list[int] = field(default_factory=list)
    missing: list[int] = field(default_factory=list)

    @property
    def message(self) -> str:
        parts = [f"已把 {len(self.marked)} 行标记为**人工批量剔除**（标记保留、默认隐藏、不销毁数据）"]
        if self.already:
            parts.append(f"另有 {len(self.already)} 行本就已剔除、未重复标记")
        if self.missing:
            parts.append(f"另有 {len(self.missing)} 行不在当前数据里、跳过")
        parts.append("规则命中的剔除**不在此列**（要放开只能改规则配置）")
        return "；".join(parts)


def manual_exclude(rows: list[dict], picked) -> ExcludeReport:
    """**人工批量剔除**（§4.2.2 现行能力）—— 写 `exclude_source = manual`。

    ⚠️ 「恢复剔除」**只放开这一类**；规则命中的剔除不因人工操作而放开。
    """
    ids = apply_manual_exclude(rows, picked)   # ← 复用：含"必须先勾选"的拦截
    want = set(ids)
    report = ExcludeReport()
    seen: set[int] = set()
    for row in rows or ():
        rid = int(row.get("id") or 0)
        if rid not in want:
            continue
        seen.add(rid)
        if bool(row.get("excluded")):
            report.already.append(rid)
        else:
            report.marked.append(rid)
    report.missing = sorted(want - seen)
    return report


# ======================================================== 统计金额手改（§4.5.3）


def apply_stat_change(
    session,
    notice_id: int,
    *,
    field: str,
    value: object,
    changed_by: str,
) -> tuple[object | None, str]:
    """**统计金额手改**（§4.5.3）的**唯一出口** —— PRG（`POST /m03/notices/stat`）与 JSON API
    （`POST /api/m03/actions/stat`）**共用这一份**：⛔ 不许两份判定、不许两份文案。

    分三层，各有各的主人（本函数只做"接线"）：
      · **判定**：`domain.adjust_stat` —— 四种拒绝（非法金额 / 非旁路字段 / **超上限** / 值没变）；
      · **落库 + 留痕**：`repository.adjust_notice_stat`（留痕 = 壳判「黄底」的唯一事实来源）；
      · **欠款重算**：MOD-05 的 `service.build_debt`（⛔ 不另写算法）。

    返回 `(trace, message)`：
      · `trace is None` ⇒ **值没变、什么都没做**（§4.2.7：不做无意义的重算，也不产生空留痕）；
      · `message` 一律是**可直接给人看**的中文（改前改后 / 改动人 / 欠款重算结果 / 那条例外说明）。
    """
    from app.mod03_notice import repository as repo
    from app.mod05_flow import service as flow_service

    notice = repo.get_notice(session, int(notice_id))
    if notice is None:
        raise MustReportError(f"通知书 {notice_id} 不存在")

    trace = repo.adjust_notice_stat(
        session, notice, field=field, value=value, changed_by=changed_by
    )
    if trace is None:
        return None, (
            f"「{notice_id}」的该格没有变化 —— **什么都没做**"
            "（§4.2.7：不做无意义的重算、不留空痕）"
        )

    debt = flow_service.build_debt(session)
    parts = " · ".join(f"{d['label']} {d['amount']}" for d in debt["by_category"])
    note = "" if debt.get("mech_settle_ready") else "（机械侧结算额来自过程资料 MOD-06，尚未落地 ⇒ 按 0 计）"
    return trace, (
        f"{trace.label}已由 {trace.before} 改为 {trace.after}（改动人 {trace.changed_by}、已留痕）；"
        f"欠款已实时重算：{parts} · 合计 {debt['total']}{note}"
    )


__all__ = [
    "CATEGORY_NAMES", "CATEGORY_CHOICES", "category_name", "jc_supplier_problem",
    "CategoryChange", "change_category",
    "ExcludeReport", "manual_exclude",
    "RestoreReport", "restore_excluded",                       # 复用 classify（同一出口）
    "apply_stat_change",
    "EXCLUDE_BY_MANUAL", "EXCLUDE_BY_RULE", "EXCLUDE_NONE", "CATEGORY_MATERIAL",
]
