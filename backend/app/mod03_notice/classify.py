"""付款通知书的**剔除判定**（§4.2.2）与**分类落实**（§4.2.3 / §4.2.4）—— 纯函数。

## 为什么有这个模块

M2 抓取链路的 `mod02_i8/fetch_task.preview(rows, is_excluded=...)` 早就预留了钩子，注释写明
「⚠️ 剔除规则本身属付款域（§4.2.2）⇒ 由调用方注入 `is_excluded`；本模块只做分列」。
**本模块就是那个"调用方"** —— 在此之前它是空的，所以抓回来的行既没分类、也没剔除。

## 剔除规则（§4.2.2 · 4 类有效）

按「规则类别 → 命中值」配置，**命中即剔除**：

| 规则类别（本模块 `kind`） | 命中方式 | 说明 |
|---|---|---|
| 业务类型 `biz_type` | **等值** | 付劳务公司款 / 付分包工程款 / 付劳务工工资 / 付材料采购款 / 付其他款 |
| 付款项目名 `project_name` | **等值** | 两个指定项目 |
| 单据名称关键字 `bill_name` | **包含**（口径原文即"关键字"） | 水电 / 水费 / 电费 / 房租 |
| 录入人 `input_by` | **等值** | 梁丽佳 |

⚠️ **硬约束**：**不得配「收款单位 = 资产处集中采购」**（集采**不走剔除**、参与分类）——
   由 `validate_rules()` 拒收（含"把它塞进别的规则类别"这种绕法）。

⚠️ 剔除是**标记**（`excluded=True` ＋ `exclude_source`），**不销毁数据**：默认隐藏，
   「分类 = 剔除」视图可查（该视图同时承载 i8 已撤单行，但**分档显示**）。

⚠️ **人工剔除 vs 规则命中**：`exclude_source` 取 `manual` / `rule`；
   **「恢复剔除」只放开人工剔除的行**（`restore_excluded()`）——规则命中的不因人工操作而放开。

## 分类（§4.2.3）

**复用 `mod05_flow.domain.classify()`**（同一出口，不另写一遍判定）。
⚠️ §4.2.4：**手改过的分类不被重抓覆盖** ⇒ 调用方传 `manual_category` 表示"这行分类是人工定的"。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.errors import MustReportError
from app.mod03_notice.models import EXCLUDE_BY_MANUAL, EXCLUDE_BY_RULE, EXCLUDE_NONE
from app.mod05_flow.domain import classify

# ---------------------------------------------------------------- 规则结构

KIND_BIZ_TYPE = "biz_type"
KIND_PROJECT_NAME = "project_name"
KIND_BILL_NAME = "bill_name"
KIND_INPUT_BY = "input_by"
KIND_PAYEE = "payee"                       # ⚠️ 存在只为"能识别并拒绝"，**不在有效规则里**

KIND_LABELS: dict[str, str] = {
    KIND_BIZ_TYPE: "业务类型",
    KIND_PROJECT_NAME: "付款项目名",
    KIND_BILL_NAME: "单据名称关键字",
    KIND_INPUT_BY: "录入人",
    KIND_PAYEE: "收款单位",
}

# ⚠️ 口径硬约束（§4.2.2）：集采**不走剔除**，参与分类
FORBIDDEN_PAYEE_VALUE = "资产处集中采购"


@dataclass(frozen=True)
class ExcludeRule:
    """一条剔除规则：`kind` 决定比对哪一列，`values` 是命中值集合。"""

    kind: str
    values: tuple[str, ...]

    @property
    def label(self) -> str:
        return KIND_LABELS.get(self.kind, self.kind)


# §4.2.2 的 4 类规则（**逐字照抄口径表**；`|` 分隔在原文里是"多个值"）
DEFAULT_RULES: tuple[ExcludeRule, ...] = (
    ExcludeRule(KIND_BIZ_TYPE, (
        "付劳务公司款", "付分包工程款", "付劳务工工资", "付材料采购款", "付其他款",
    )),
    ExcludeRule(KIND_PROJECT_NAME, (
        "杭州山亚南方水泥日产5000吨孰料水泥生产线技改工程",
        "集团公司第四分公司机关工程",
    )),
    ExcludeRule(KIND_BILL_NAME, ("水电", "水费", "电费", "房租")),
    ExcludeRule(KIND_INPUT_BY, ("梁丽佳",)),
)


def validate_rules(rules) -> None:
    """校验一份规则集 —— 违反 §4.2.2 硬约束即显式拒绝（**不静默忽略**）。"""
    for rule in rules or ():
        if rule.kind not in KIND_LABELS:
            raise MustReportError(f"未知的剔除规则类别「{rule.kind}」（见 §4.2.2 的四类）")
        if rule.kind == KIND_PAYEE:
            raise MustReportError(
                "剔除规则**不得**按「收款单位」配置 —— 集采不走剔除、而是参与分类（§4.2.2）"
            )
        if not rule.values:
            raise MustReportError(f"剔除规则「{rule.label}」没有任何命中值")
        for value in rule.values:
            if str(value).strip() == FORBIDDEN_PAYEE_VALUE:
                raise MustReportError(
                    f"剔除规则的命中值不得为「{FORBIDDEN_PAYEE_VALUE}」"
                    "（该收款单位走分类、不走剔除 —— §4.2.2 / §4.2.3）"
                )


# ---------------------------------------------------------------- 判定

# 各规则类别从记录里取哪一列（记录 = `mod02_i8.notice_source._map_record` 的产物）
_FIELD_OF_KIND: dict[str, str] = {
    KIND_BIZ_TYPE: "biz_type",
    KIND_PROJECT_NAME: "project_name",
    KIND_INPUT_BY: "input_by",
}


def _value_of(rec: dict, kind: str) -> str:
    """取这一列的值。

    ⚠️ 「单据名称」在 `payment_notice` 表里**没有独立列** —— 它随原始记录留在 `fields`（JSON）里，
       故这里从 `fields["BillName"]` 取（i8 `API-01` 的 12 字段之一）。
    """
    if kind == KIND_BILL_NAME:
        return str((rec.get("fields") or {}).get("BillName") or "").strip()
    return str(rec.get(_FIELD_OF_KIND[kind]) or "").strip()


def match_exclude_rule(rec: dict, rules=DEFAULT_RULES) -> ExcludeRule | None:
    """命中则返回**命中的那条规则**（便于在界面上说明"为什么被剔除"），否则 `None`。

    - `biz_type` / `project_name` / `input_by` ⇒ **等值**命中（口径给的是完整值）
    - `bill_name` ⇒ **包含**命中（口径原文即「单据名称关键字」）
    """
    for rule in rules or ():
        value = _value_of(rec, rule.kind)
        if not value:
            continue
        if rule.kind == KIND_BILL_NAME:
            if any(kw and kw in value for kw in rule.values):
                return rule
        elif value in tuple(str(v).strip() for v in rule.values):
            return rule
    return None


def is_excluded(rec: dict, rules=DEFAULT_RULES) -> bool:
    """**注入给 M2 的钩子**（`fetch_task.preview(rows, is_excluded=...)`）—— 只需回答是/否。"""
    return match_exclude_rule(rec, rules) is not None


def current_exclude_hint(rec: dict, rules=DEFAULT_RULES) -> str:
    """旧标记没有规则快照；只说明当前匹配，不能冒充当时的剔除依据。"""
    rule = match_exclude_rule(rec, rules)
    if not rule:
        return "当前无匹配规则；历史命中规则未保存，无法追溯"
    value = _value_of(rec, rule.kind)
    matched = [v for v in rule.values if v and v in value] if rule.kind == KIND_BILL_NAME else [value]
    return f"当前匹配规则：{rule.label}（{'、'.join(matched)}）；历史命中规则未保存"


def rows_needing_ownership(rows: list[dict], rules=DEFAULT_RULES) -> list[tuple[int, dict]]:
    """挑出**需要走归属校验**的行 → `(原序号, 行)`（`TAIL-29`-①）。

    ⚠️ **规则剔除行不需要归属**：§4.2.2「指定项目不在统计范围」的行**与本域无关**
       （落库时 `decide_placement` 会给它们打上 `exclude_source=rule`）。
       拿它们去跑「整批校验」会把**整批误拦** —— 实测：2026-09 抓 61 行，
       「集团公司第四分公司机关工程」×2 行就把 61 行**全拦下**，该月一条都进不来。

    ⛔ **判定必须走 `is_excluded`（同一份 `DEFAULT_RULES`）** —— 不许在编排层另写一份
       剔除判定（「同一件事被实现两遍」是本项目反复踩的坑）。
    ✅ 保留**原序号**，让调用方仍能按抓取顺序落库。剔除行跳过阻断校验，写入后非阻断尝试归属。
    """
    return [(i, row) for i, row in enumerate(rows or ()) if not is_excluded(row, rules)]


# ---------------------------------------------------------------- 分类 + 剔除的落库赋值


@dataclass
class Placement:
    """一条记录该落库的**分类与剔除**（§4.2.2 / §4.2.3 / §4.2.4 的合并结论）。"""

    category: str
    excluded: bool
    exclude_source: str = EXCLUDE_NONE
    matched_rule: ExcludeRule | None = None
    category_kept: bool = False          # 手改分类保护是否生效（§4.2.4）

    @property
    def reason(self) -> str:
        if not self.excluded:
            return ""
        if self.exclude_source == EXCLUDE_BY_MANUAL:
            return "人工批量剔除"
        rule = self.matched_rule
        return f"规则命中：{rule.label}（{('、'.join(rule.values))[:60]}）" if rule else "规则命中"


def decide_placement(
    rec: dict,
    *,
    rules=DEFAULT_RULES,
    manual_category: str | None = None,
    current_source: str = EXCLUDE_NONE,
) -> Placement:
    """一条记录 → 该落库的分类与剔除。

    - **剔除**：命中规则 ⇒ `excluded=True` ＋ `source=rule`；
      ⚠️ 若该行**本来就是人工剔除**（`current_source=manual`）⇒ **保持人工**（不降级成 rule，
      否则"恢复剔除"会突然变得能放开它 —— 那违反 §4.2.2）。
    - **分类**：`manual_category` 非空 ⇒ **保持手改值**（§4.2.4 人工判断优先）；否则跑 `classify()`。
    """
    rule = match_exclude_rule(rec, rules)

    if current_source == EXCLUDE_BY_MANUAL:
        excluded, source = True, EXCLUDE_BY_MANUAL
    elif rule is not None:
        excluded, source = True, EXCLUDE_BY_RULE
    else:
        excluded, source = False, EXCLUDE_NONE

    kept = bool(str(manual_category or "").strip())
    category = (
        str(manual_category).strip() if kept
        else classify(str(rec.get("biz_type") or ""), str(rec.get("payee") or ""))
    )

    return Placement(
        category=category,
        excluded=excluded,
        exclude_source=source,
        matched_rule=rule,
        category_kept=kept,
    )


# ---------------------------------------------------------------- 「恢复剔除」（§4.2.2）


@dataclass
class RestoreReport:
    """「恢复剔除」的**分档回报**（§4.2.2：混有规则命中时必须分开说清）。"""

    restored: list[int] = field(default_factory=list)        # 真正被恢复的行（**人工 ＋ 规则命中都算**）
    restored_by_rule: list[int] = field(default_factory=list)  # 其中「来自规则命中」的（⚠️ **也给恢复了**，见 `restore_excluded`）
    untouched: list[int] = field(default_factory=list)       # 勾选中本就未剔除的行

    @property
    def message(self) -> str:
        parts = [f"已恢复 {len(self.restored)} 条"]
        if self.restored_by_rule:
            parts.append(
                f"其中 {len(self.restored_by_rule)} 条是「规则命中」的 —— 已一并放回，"
                "重新计入统计与付款"
                "（要长期剔除请改「规则配置」，改完再抓一次才会重新剔除）"
            )
        if self.untouched:
            parts.append(f"另有 {len(self.untouched)} 条本就未剔除")
        return "；".join(parts)


def restore_excluded(rows: list[dict], picked) -> RestoreReport:
    """「恢复剔除」按**勾选行**生效（§4.2.2）。

    ⚠️ 三条口径：
    1. **必须先勾选**（`picked` 为空 ⇒ 显式报错，不做"一键全放回"）；
    2. **人工剔除 ＋ 规则命中的都恢复**（⭐ **2026-10-08 用户裁定**，此前列口径为"规则命中的不恢复"）；
    3. 勾选里混有本就未剔除的行 ⇒ **不报错，但分开回报**（`RestoreReport.message`）。

    ⭐ **为什么改这条口径**（原先那句"要放开只能改规则配置"在本系统里是**兑现不了**的承诺）：
       `mod14_config.rules_api` 明写「改规则**不重算**历史剔除标记」，而再次导入时
       `merge.PROTECTED` 又不覆盖 `excluded` / `exclude_source`
       ⇒ 规则命中的行**没有任何放开出口**（按钮却照旧提示"要放开请改规则配置"）。
       既然那条路走不通，就让「恢复剔除」本身能放开；想让某行长期被剔除，**改规则配置**仍是正解
       —— 只是需要**再抓一次**才生效（回执已如实说明）。
    ⚠️ 代价（用户已知）：恢复后该行**重新进统计与付款**；再次抓取**不会**自动反弹（人工标记受保护）。
    """
    want = {int(x) for x in (picked or ())}
    if not want:
        raise MustReportError("「恢复剔除」必须先勾选要恢复的行（§4.2.2：不做整表一键放回）")

    report = RestoreReport()
    for row in rows or ():
        rid = int(row.get("id") or 0)
        if rid not in want:
            continue
        source = str(row.get("exclude_source") or EXCLUDE_NONE)
        if source == EXCLUDE_BY_MANUAL:
            report.restored.append(rid)
        elif source == EXCLUDE_BY_RULE:
            # ⭐ 2026-10-08 用户裁定：**规则命中的也放回**（原先在此归 `kept_by_rule` = 不恢复）。
            report.restored.append(rid)
            report.restored_by_rule.append(rid)
        else:
            report.untouched.append(rid)
    return report


def apply_manual_exclude(rows: list[dict], picked) -> list[int]:
    """**人工批量剔除**（§4.2.2 现行能力）—— 返回被标记的行 id。

    ⚠️ 与"规则命中"区分：这里写的是 `exclude_source = manual`，**只有这一类能被恢复放开**。
    """
    want = {int(x) for x in (picked or ())}
    if not want:
        raise MustReportError("「批量剔除」必须先勾选要剔除的行（§4.2.2）")
    return [int(r.get("id") or 0) for r in rows or () if int(r.get("id") or 0) in want]


__all__ = [
    "KIND_BIZ_TYPE", "KIND_PROJECT_NAME", "KIND_BILL_NAME", "KIND_INPUT_BY", "KIND_PAYEE",
    "KIND_LABELS", "FORBIDDEN_PAYEE_VALUE",
    "ExcludeRule", "DEFAULT_RULES", "validate_rules",
    "match_exclude_rule", "is_excluded", "current_exclude_hint", "rows_needing_ownership",
    "Placement", "decide_placement",
    "RestoreReport", "restore_excluded", "apply_manual_exclude",
]
