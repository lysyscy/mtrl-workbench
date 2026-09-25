"""`m11` 集采台账 · **通用导入域的声明与钩子**（`TAIL-75` `B5b`）—— 本域接上通用导入面的那一件。

⭐ 与 `m06`/`m04` 同款：识别/映射/记忆/预览/暂存在 `import_kit`；本件只声明"要什么"并给钩子，
   而钩子**原样复用**既有落库口径（`import_service.match_and_apply` ⇒ 按**含税合同价**锚点匹配并更新）——
   ⛔ 不新写第二条匹配逻辑。

⚠️ 本域的三条域内口径（通用面不管，也管不了）：
   ① **「合同价」列必须在**（它是匹配锚点，认不到 ⇒ 一条都配不上）—— 通用面按 `required` 卡；
   ② **匹配范围 = 单个项目** ⇒ 落库要 `options.project_key`（仓库名，§2.7.4）；
   ③ **只更「Excel 的地盘」那几列**（`EXCEL_COLS`）：i8 的事实列（合同价/供应商/合同日期/甲方单位）
      一个字都不碰 —— 由 `match_and_apply` 保证（它与老那条路是**同一个函数**）。
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


HOOKS = Hooks(commit=commit, rollback=rollback)

__all__ = ["DOMAIN", "FIELDS", "HOOKS", "SPEC", "commit", "rollback"]
