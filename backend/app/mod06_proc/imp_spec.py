"""`m06` 过程资料 · **通用导入域的声明与钩子**（`TAIL-75`）—— 本域接上通用导入面的那一件。

⭐ 分工（设计 §六/§七）：读表 / 表头定位 / 映射建议 / 记忆 / 预览 / 暂存全在 `import_kit`；
   本件**只声明"要什么"**并给两个钩子，而两个钩子**原样复用既有落库口径**
   （`importer.commit` → `repository.import_snapshot`）—— ⛔ **不新写第二条落库路**
   （那正是"同一口径两个主人"的老毛病）。

⚠️ **字段清单 = 核算月 ＋ 材料 10 列**；**机械 6 列刻意不在里面**（口径：机械全段手录，导入只提示不落库）。
   ⛔ 不给机械列一个"能落库的字段"—— 否则又要踩一遍 `m11` 那个静默错：
   "认得出、白名单也放行、就是不写"，全程不报错。
"""

from __future__ import annotations

from app.core.errors import MustReportError
from app.core.money import to_money
from app.import_kit.spec import DomainSpec, Hooks
from app.mod06_proc import domain as D
from app.mod06_proc import importer as I
from app.mod06_proc.service import build_import_data

#: 通用面上的**域号**（⛔ 与模块号解耦：一个模块将来有两套导入时不必拆号）
DOMAIN = "m06_proc"

#: 材料 10 列 ＋ 核算月（机械 6 列不入，见模块头 ⚠️）
FIELDS = tuple(f for f in I.FIELDS if f.key == "ym" or f.key in D.MATERIAL_KEYS)

def _label_key() -> dict[str, str]:
    """`{界面字段名: 域内列 key}`（⛔ 不手抄第二份名单 —— 从 `FIELDS` 反查）。"""
    return {f.label: f.key for f in FIELDS}


def _ignored() -> tuple[tuple[str, str], ...]:
    """**明确不采**的列（认得出，但按口径不导入）—— 从 `FIELDS` 里的机械 6 列**自动生成**。

    ⚠️ 为什么必须显式列出来：它们在界面上若落进"未认出"，看着就像**系统漏了** ——
      而真相是"认得，但机械列全段手录、导入不碰"。理由写在 `why` 里，界面照原话显示。
    """
    out: list[tuple[str, str]] = [("序号", "行号，系统自己编")]
    for f in I.FIELDS:
        if f.key not in D.MECH_KEYS:
            continue
        why = "机械 6 列**不导入**（全段手录，见 §5.2.5）—— 导入只提示，⛔ 不写进历史段"
        out.append((f.label, why))
        out += [(a, why) for a in f.aliases]        # 真模板里的各种拼名写法
    return tuple(out)


SPEC = DomainSpec(
    domain=DOMAIN,
    title="过程资料 · 材料机械消耗汇总表",
    fields=FIELDS,
    source_label="各项目手填的消耗汇总表",
    max_rows=I.MAX_ROWS,
    batch=True,
    ignored=_ignored(),
    note="必须有「核算月」（真模板里那列叫「时间」，也认 Excel 序列号）与至少一列材料列；"
         "落库时要选**项目**（仓库名）—— 过程资料按项目分别存。",
    keep_note="未采（原样保留）：序号 / 尾部合计（小计）行 / 手写说明行。"
              "⚠️ **机械 6 列不导入**（全段手录）—— 界面上会提示，但不会落库。",
)


def commit(s, records, mapping_, operator, options):  # noqa: ARG001 —— `mapping_` 只进回执口径
    """落库：**原样复用** `importer.commit` ⇒ 只写**历史段**（不碰正式段、不碰机械手录）。

    `options`：`warehouse`（项目/仓库名，**必填**）· `cutoff_ym`（截止核算月，不给 ⇒ 取导入数据最大月）
    · `batch`（批次号，不给 ⇒ `importer.next_batch()`）。
    """
    opts = dict(options or {})
    warehouse = str(opts.get("warehouse") or "").strip()
    if not warehouse:
        raise MustReportError("请先选**项目**（仓库名）—— 过程资料按项目分别存，没选就无从落库")
    key_of = _label_key()
    rows: list[dict] = []
    for rec in records or []:
        ym = I.ym_of(rec.get("核算月"))
        if not ym:
            raise MustReportError(
                f"第 {rec.get('_row')} 行的核算月认不出：{rec.get('核算月')!r} —— "
                "写 2026-08 / 2025年9月 这种形态")
        row: dict = {"ym": ym}
        for label, key in key_of.items():
            if key == "ym":
                continue
            val = rec.get(label)
            if val in (None, ""):
                continue
            row[key] = to_money(str(val))
        rows.append(row)
    if not rows:
        raise MustReportError("没有一行可落库的数据 —— 历史段未被改动（不写库）")
    plan = I.ImportPlan(rows=rows)
    out = I.commit(s, plan, warehouse=warehouse,
                   batch=str(opts.get("batch") or I.next_batch()), operator=operator,
                   cutoff_ym=str(opts.get("cutoff_ym") or "") or None)
    out["cutoff_default"] = plan.default_cutoff        # 界面用来回显"默认截止月 = 最大核算月"
    return out


def rollback(s, batch, operator):
    """整批回滚（**置状态、不物理删**）—— 复用 `importer.rollback`。"""
    return {"revoked": I.rollback(s, batch_no=batch), "batch": batch, "operator": operator}


def options(s) -> dict:
    """**域上下文**（界面上的"项目 / 截止核算月 / 已有批次"）—— 复用 `service.build_import_data`。

    ⚠️ 2026-09-23（`B5c-2`）：原先这些走域专属端点 `/api/m06/import/data`；现在走通用面的
       `GET /api/imp/m06_proc/options`（壳**只认这一条**）⇒ 那条旧端点可以退休了。
       ⛔ 口径与取值**一字未改**（还是 `build_import_data` 这一处出口）。
    """
    data = build_import_data(s, warehouse="")
    return {
        "projects": list(data["projects"]),
        "warehouse": str(data["warehouse"] or ""),
        "cutoff_ym": str(data["cutoff_ym"] or ""),
        "batches": [str(getattr(b, "batch_no", "") or "") for b in data["batches"]],
    }


HOOKS = Hooks(commit=commit, rollback=rollback, options=options)

__all__ = ["DOMAIN", "FIELDS", "HOOKS", "SPEC", "commit", "options", "rollback"]
