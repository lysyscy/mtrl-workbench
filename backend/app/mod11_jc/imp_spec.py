"""`m11` 集采台账 · **通用导入域的声明与钩子**（`TAIL-75` `B5b`）—— 本域接上通用导入面的那一件。

⭐ 与 `m06`/`m04` 同款：识别/映射/记忆/预览/暂存在 `import_kit`；本件只声明"要什么"并给钩子，
   而钩子**原样复用**既有落库口径（`import_service.match_and_apply` ⇒ 按**含税合同价**锚点匹配并更新）——
   ⛔ 不新写第二条匹配逻辑。

⚠️ 本域的三条域内口径（通用面不管，也管不了）：
  ① **「合同价」列必须在**（它是匹配锚点，认不到 ⇒ 一条都配不上）—— 通用面按 `required` 卡；
  ② **匹配范围 = 单个项目** ⇒ 落库要 `options.project_key`（仓库名，§2.7.4）；
  ③ **只更「Excel 的地盘」那几列**（`EXCEL_COLS`）：i8 的事实列（合同价/供应商/合同日期/甲方单位）
     一个字都不碰 —— 由 `match_and_apply` 保证（它与老那条路是**同一个函数**）。

⭐ 域上下文（候选项目）走通用面**唯一**一条端点 `GET /api/imp/{domain}/options`（= 下面的 `options` 钩子）
  —— 2026-09-26 用户报障后补上：本域原先**没有**它，壳只好单开一条**域号分支**去调**域专属读端点**
  `/api/m11/list`（那条路给的是**对象**），于是渲染出 `[object Object]`（详见 `options` 的 docstring）。
"""

from __future__ import annotations

from app.core.errors import MustReportError
from app.core.money import to_money
from app.import_kit.mapping import Field
from app.import_kit.spec import DomainSpec, Hooks
from app.mod11_jc import excel_parse as P
from app.mod11_jc import imp_batch as B
from app.mod11_jc import import_service as IS
from app.mod11_jc import repository as R

#: 通用面上的域号（⛔ 与模块号解耦）
DOMAIN = "m11_jc"


def _fields() -> tuple[Field, ...]:
    """本域的界面字段 = `excel_parse.FIELD_LABELS`（页面列名）；别名 = `ALIASES` 里其余写法。

    ⭐ **自动反查** ⇒ ⛔ 不手抄第二份名单（抄一份 = 将来改一处漏一处）。类型取 `FIELD_TYPES`。
    """
    extra: dict[str, list[str]] = {}
    for alias, fld in P.ALIASES.items():
        if alias != P.FIELD_LABELS.get(fld):
            extra.setdefault(fld, []).append(alias)
    return tuple(Field(key=k, label=v, aliases=tuple(extra.get(k, ())),
                       type=P.FIELD_TYPES.get(k, "text"))
                 for k, v in P.FIELD_LABELS.items())


FIELDS = _fields()

SPEC = DomainSpec(
    domain=DOMAIN,
    title="集采台账",
    fields=FIELDS,
    source_label="项目集采台账（逐项目一份）",
    batch=True,              # ⭐ `TAIL-98`：有**整批回滚**（批次号形如 `JC-…`，回执带出、壳侧按钮据此出现）
    note="必须认出**「合同价」列**（供应商合同总价 / 合同总价 / 合同金额）——它是匹配锚点，"
         "认不到就一条都配不上；落库要选**项目**（仓库名）—— 匹配范围就在这个项目内。"
         "⭐ **覆盖语义（导入前必读）**：已存在的行**会被更新**，但 **只动这 6 列** —— "
         "**材料名 / 付款方式 / 备注 / 存档情况 / 存档号 / 寄回日期**；"
         "⭐ **i8 的列（合同价 / 供应商 / 合同日期 / 甲方单位）不会被覆盖**（两边互不覆盖）。"
         "⭐ 落库回执会带**批次号**（形如 `JC-YYYYMMDDHHMMSS`）⇒ 导错了可以**整批回滚**。",
    keep_note="不落库（系统自己算）：结算 / 付款 / 欠款；原样保留（本系统不录）：序号 / 重量 / 开票号 / 单价。",
    ignored=tuple((lb, why) for lb, why in P.IGNORED_LABELS.items()),
    #: ⭐ **这一批怎么入库**（页头一句话 · 大白话 · 用户 2026-09-26 拷问后要的）——
    #: 措辞**照代码真值**：对号键 = `EXCEL_COLS` 之外的 `contract_amt`（`import_service._amount_key`）；
    #: 只更 `EXCEL_COLS` 6 列；i8 事实列不碰（`import_service.py:353-365`）；有批次可整批回滚。
    rule_note="这一批按「**含税合同价**」在**你所选的那个项目里**对号：配上 1 条 ⇒ 更新它；"
              "配不上 ⇒ **不新增**；同一个价有多条 ⇒ 系统**不猜**、跳过。"
              "更新时**只改 6 列**（材料名 / 付款方式 / 备注 / 存档情况 / 存档号 / 寄回日期）；"
              "**合同价 / 供应商 / 合同日期 / 甲方单位**是 i8 的，导入**不动它们**。"
              "导完可以**整批回滚**（回执里有批次号）。",
    #: ⭐ **逐列后果**（键 = **目标字段名** ⇒ 随用户改下拉实时跟着变）。
    #: ⚠️ 字段名用 `FIELD_LABELS` **反查**（⛔ 不手抄第二份列名 —— 改一处漏一处）。
    impacts=tuple(
        (dict((f.key, f.label) for f in FIELDS)[key], what)
        for key, what in (
            # ① `EXCEL_COLS` 那 6 列 = **会被覆盖**（`import_service.py:88`）
            ("material_name", "会写进台账（覆盖原值）"),
            ("method", "会写进台账（覆盖原值）"),
            ("remark", "会写进台账（覆盖原值）"),
            ("arch", "会写进台账（覆盖原值）"),
            ("arch_no", "会写进台账（覆盖原值）"),
            ("ret_date", "会写进台账（覆盖原值）"),
            # ② **只用来对号**：含税合同价 = 匹配锚点（`_amount_key`）—— 用户 2026-09-26 原话
            #    「用于匹配的只有一条字段：合同价」
            ("contract_amt", "只用来对号（在项目内按它找已有行）—— 合同上的这个数字一个字不改"),
            # ③ **只用来认行**：i8 的事实列（`import_service.py:353-365` 一个字不碰）
            ("supplier", "只用来认行 —— 合同上的原值不改（i8 的事实列）"),
            ("contract_date", "只用来认行 —— 合同上的原值不改（i8 的事实列）"),
            # ④ **写进子表**（不改合同主表上的金额）
            ("inv_sum", "写进「供应商发票」子表（不改合同上的金额）"),
            ("trade_inv_sum", "写进「贸易公司发票」子表（不改合同上的金额）"),
            # ⚠️ `trade_co`（贸易公司）/ `trade_contract_amt`（贸易公司合同总价）**刻意不声明** ——
            #    我对它们「落库去哪一列」没有确证 ⇒ 按契约口径**不替域编**（界面就不标那两格）。
        )
    ),
)


def _rows_of(records) -> list[dict]:
    """通用面的 `records`（按字段名）→ 本域的**行形状**（key 即 `FIELD_LABELS` 的键）。"""
    key_of = {f.label: f.key for f in FIELDS}
    out: list[dict] = []
    for rec in records or []:
        row: dict = {key_of[lb]: rec[lb] for lb in key_of if rec.get(lb) not in (None, "")}
        for k, v in list(row.items()):                     # 金额回 `Decimal`（通用面给的是字符串）
            if k.endswith(("_amt", "_sum")):
                row[k] = to_money(str(v))
        out.append(row)
    return out


def commit(s, records, mapping_, operator, options):  # noqa: ARG001 —— `mapping_` 只进回执口径
    """落库：**复用** `imp_batch.apply_batch`（它里面调的仍是 `import_service.match_and_apply`）。

    `options`：`project_key`（**必填** · 匹配范围 = 该项目内）· `batch`（批次号，不给 ⇒ 现生成 `JC-…`）。
    ⭐ `TAIL-98`：回执里**带批次号** ⇒ 壳侧据此显示「整批回滚」按钮（通用面已就绪）。
    """
    key = str((options or {}).get("project_key") or "").strip()
    if not key:
        raise MustReportError("请先选**项目**（仓库名）—— 台账按项目分存，匹配也只在项目内做")
    project_id = R.project_id_by_key(s, key)
    if project_id is None:
        raise MustReportError(f"找不到项目（仓库名 {key!r}）—— 请先在「项目档案」建好")
    rows = _rows_of(records)
    if not rows:
        raise MustReportError("没有一行可落库的数据 —— 台账未被改动（不写库）")
    out = B.apply_batch(s, rows, project_id=int(project_id), project_key=key,
                        operator=str(operator or ""), batch_no=(options or {}).get("batch"))
    out["project_key"] = key
    return out


def rollback(s, batch, operator):
    """**整批回滚**（`TAIL-98`）—— 那 6 列逐列还原 ＋ 摘掉本批新加的发票行（批次置 `rolled_back`）。"""
    return B.rollback(s, batch, operator)


def options(s) -> dict:
    """**域上下文**（通用面唯一一条读端点：`GET /api/imp/{domain}/options`）—— 候选项目（§2.7.4）。

    ⭐ **为什么要它**（2026-09-26 用户报障「项目的选择要用通用模块」）：本域原先**没有** `options`
      ⇒ 壳只好给它单开一条**域号分支**、去调**域专属读端点** `/api/m11/list`；那条路是
      `repository.project_choices()` 给的**对象** `{"key","display"}`，而壳里写的是
      `(p && p.key) || String(p)` ⇒ `key` 是**空串**（项目没记仓库名）时落到 `String(对象)`
      ⇒ 下拉里出现 `[object Object]`（真机实测 20 条里 3 条），**选中即报「找不到项目」**。
    ⇒ 走通用面这条路**只给候选键**、且**空的键根本不进候选**（根因从源头去掉，⛔ 不靠壳里兜底）。

    ⚠️ 与 `m06_proc` 的 `options` 同形（都是 `{"projects": [仓库名, …]}`）⇒ 壳侧**同一段通用代码**处理两域，
      ⛔ 壳里不再有"集采给对象、过程资料给字符串"这种两套形态（那正是本次坏选项的土壤）。
    """
    return {"projects": [c["key"] for c in R.project_choices(s) if str(c.get("key") or "").strip()]}


HOOKS = Hooks(commit=commit, rollback=rollback, options=options)

__all__ = ["DOMAIN", "FIELDS", "HOOKS", "SPEC", "commit", "options", "rollback"]
