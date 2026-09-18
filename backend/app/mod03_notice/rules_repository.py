"""剔除规则的**落库存取**（§4.2.2 · 系统配置）—— `TAIL-40`。

## 本模块的边界

- **规则主人 =《说明书》§4.2.2**（本模块**不复述取值**，只搬动"库里那几行"）。
- **判定的唯一出口**仍是 `classify.match_exclude_rule` —— 本模块只把库行转成 `classify.ExcludeRule`
  （⛔ 不另写一份判定；「同一件事被实现两遍」是本项目反复踩的坑）。
- **优先级 = 库 → 出厂默认**：库里**一行都没有** ⇒ 回落 `classify.DEFAULT_RULES`（＝ §4.2.2 那张表）
  ⇒ **首装行为即符合口径**，不必人工把 4 类规则录一遍（与 `core/app_settings` 的「库 → `.env`」同款）。
- **配置类数据 ⇒ 硬删、不留痕**（§9.4）。
- **改规则不重算历史**：已产生的剔除标记（`exclude_source=rule`）不受影响、也不重算（§4.2.2）
  ⇒ 本模块的写动作**不触发任何重算**（也不该有人在这里补一个）。

## 为什么表与仓储放**付款域**（`mod03_notice`）而不是配置域

§4.2.2 原文即「**剔除规则本身属付款域**」；抓取管线（付款域）要用它，而配置**页**在 `MOD-14`。
放这里 ⇒ 依赖**单向** `mod14_config → mod03_notice`（页面读付款域的规则仓储），**不成环**。
（若反过来把表放 `mod14_config`，`mod03` 要读它、`mod14` 又要读 `mod03` 的 `ExcludeRule` ⇒ 循环。）

## 命中值分隔符

**全角 `｜`**（《说明书》§4.2.2 表内写法，与原型演示常量同款）；⚠️ **解析时半角 `|` 也认**
（手输常见）—— **写入统一规整成全角**（唯一写法，免得同一个值两种写法各存一份）。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.mod03_notice import classify
from app.mod03_notice.models import ExcludeRuleRow

#: 命中值分隔符（写入用；唯一写法 = 全角）
SEP = "｜"
#: 解析时**也认**的写法（手输常见）
ALT_SEPS = ("|", "｜", "，", ",")


def split_values(raw) -> tuple[str, ...]:
    """命中值原文 → 去空、去重的元组（**半角/全角都认**）。"""
    text = str(raw if raw is not None else "")
    for ch in ALT_SEPS:
        text = text.replace(ch, SEP)
    out: list[str] = []
    for part in text.split(SEP):
        v = part.strip()
        if v and v not in out:        # ⚠️ 去重：同一个值出现两次没有意义，且会让回执难看
            out.append(v)
    return tuple(out)


def join_values(values) -> str:
    """命中值 → **规整后的原文**（全角 `｜` 分隔）。"""
    return SEP.join(split_values(SEP.join(str(v) for v in (values or ()))))


def to_rule(row: ExcludeRuleRow) -> classify.ExcludeRule:
    """库行 → 判定用的**不可变值对象**（`meaning` 不参与判定）。"""
    return classify.ExcludeRule(kind=str(row.kind or ""), values=split_values(row.values))


def all_rows(s: Session) -> list[ExcludeRuleRow]:
    """全部规则行（**按行序** = `ord` → `id`，与 §4.2.2 表序一致）。"""
    stmt = select(ExcludeRuleRow).order_by(ExcludeRuleRow.ord, ExcludeRuleRow.id)
    return list(s.execute(stmt).scalars().all())


def effective_rules(s: Session) -> tuple[classify.ExcludeRule, ...]:
    """**生效规则集（唯一出口）**：库里有 ⇒ 以库为准；**库空 ⇒ 出厂默认**（＝ §4.2.2 那张表）。"""
    rules = tuple(to_rule(r) for r in all_rows(s))
    return rules if rules else classify.DEFAULT_RULES


def ensure_seeded(s: Session) -> int:
    """**幂等初始化**：库空 ⇒ 把**出厂默认**落库一次；返回本次写入的行数（非空则 0）。

    ⚠️ **为什么需要它**：库空时页面上那 4 行来自 `DEFAULT_RULES`（**没有 `id`**）⇒ 用户**改不了也删不掉**
       （只有"新增"可用）—— 那等于"看起来能编辑、其实不能"。⇒ 页面首次读取时把出厂默认落库，
       它们就**成了真正的配置行**，随后增 / 删 / 改都落在库上。
    ⚠️ **只有配置页调用它**（`GET /api/m14/rules`）；⛔ **抓取管线不调** —— 抓取路径保持**纯读**
       （库空就用 `DEFAULT_RULES`，与接线前**逐字一致**，不因本功能改变任何抓取行为）。
    ⚠️ 取值**不打字**：一律取自 `classify.DEFAULT_RULES`（**唯一取值处**）—— 免得同一个值两处抄。
    """
    if all_rows(s):
        return 0
    for i, rule in enumerate(classify.DEFAULT_RULES, 1):
        s.add(ExcludeRuleRow(kind=rule.kind, values=join_values(rule.values),
                             meaning="", ord=i))
    s.flush()
    return len(classify.DEFAULT_RULES)


# ---------------------------------------------------------------- 写（硬删不留痕 · 不重算历史）


def _validate(*, kind: str, values: tuple[str, ...]) -> None:
    """写前校验 —— **复用 `classify.validate_rules`**（§4.2.2 的四类 / 不得按收款单位 / 命中值非空）。

    ⚠️ 借用 `ExcludeRule(kind, values)` 走同一个出口 —— ⛔ 不在本模块另写一份规则校验
       （否则"哪条规则合法"就有了两个说法）。
    """
    classify.validate_rules([classify.ExcludeRule(kind=str(kind or ""), values=tuple(values))])


def next_ord(s: Session) -> int:
    rows = all_rows(s)
    return (max((int(r.ord or 0) for r in rows), default=0)) + 1


def add_row(s: Session, *, kind: str, values, meaning: str = "") -> ExcludeRuleRow:
    """新增一条规则（**同 `kind` 允许多行** —— 与原型一致）。"""
    vals = split_values(values)
    _validate(kind=kind, values=vals)
    row = ExcludeRuleRow(kind=str(kind).strip(), values=join_values(vals),
                         meaning=str(meaning or "").strip(), ord=next_ord(s))
    s.add(row)
    s.flush()
    return row


def update_row(s: Session, row: ExcludeRuleRow, *, kind: str, values, meaning: str = "") -> None:
    vals = split_values(values)
    _validate(kind=kind, values=vals)
    row.kind = str(kind).strip()
    row.values = join_values(vals)
    row.meaning = str(meaning or "").strip()
    s.flush()


def delete_row(s: Session, row: ExcludeRuleRow) -> None:
    """**硬删、不留痕**（§9.4：配置类数据）。"""
    s.delete(row)
    s.flush()


def get_row(s: Session, row_id: int) -> ExcludeRuleRow | None:
    return s.get(ExcludeRuleRow, int(row_id))


def payload(s: Session) -> list[dict]:
    """给页面 / API 的形状（`kind_label` 由 `classify.KIND_LABELS` 给 —— **唯一出口**）。"""
    return [
        {
            "id": r.id,
            "kind": r.kind,
            "kind_label": classify.KIND_LABELS.get(r.kind, r.kind),
            "values": r.values,
            "meaning": r.meaning,
            "ord": r.ord,
            "rows": len(split_values(r.values)),
        }
        for r in all_rows(s)
    ]


def effective_payload(s: Session) -> dict:
    """生效规则集 → 给壳（含 `source` 说明，便于页面**如实**告诉用户当前值从哪来）。"""
    rows = all_rows(s)
    return {
        "source": "db" if rows else "default",
        "source_label": "系统配置" if rows else "出厂默认（§4.2.2）",
        "rules": payload(s),
        "kinds": [
            {"kind": k, "label": v}
            for k, v in classify.KIND_LABELS.items()
            if k != classify.KIND_PAYEE          # ⛔ 「收款单位」不在有效类别里（只能识别并拒绝）
        ],
    }


__all__ = [
    "SEP", "ALT_SEPS", "split_values", "join_values", "to_rule", "all_rows",
    "effective_rules", "effective_payload", "ensure_seeded", "next_ord", "get_row",
    "add_row", "update_row", "delete_row", "payload",
]
