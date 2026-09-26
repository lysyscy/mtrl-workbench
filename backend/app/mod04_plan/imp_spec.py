"""`m04` 付款计划 · **通用导入域的声明与钩子**（`TAIL-75` `B5b`）—— 本域接上通用导入面的那一件。

⭐ 分工与 `m06_proc/imp_spec.py` 同款：读表/表头定位/映射建议/记忆/预览/暂存在 `import_kit`；
   本件只声明"要什么"并给钩子，**落库原样复用**既有出口（`repo.merge_month`，§9.5 幂等）——
   ⛔ 不新写第二条落库路（"同一口径两个主人"是本仓反复踩过的坑）。

⚠️ 两处**域内口径必须跟着走**（通用面自己不管，也管不了）：
   ① **年月**：本域**必须先选「年月」**（本批数据一律归入所选月，§4.3.3）⇒ 走 `options.year_month`；
   ② **「9月11号」这种中文月日**：要按所选年月补成完整日期（`importer.norm_pay_date`）——
      ⚠️ 通用面的日期出口只认"真日期 / Excel 序列号 / 已经是 ISO 的"，**中文月日它不认识**（也不该认识）。
"""

from __future__ import annotations

from app.core.errors import MustReportError
from app.core.money import to_money
from app.import_kit.spec import DomainSpec, Hooks
from app.mod04_plan import importer as I
from app.mod04_plan import repository as repo
from app.mod04_plan.project_views import project_briefs

#: 通用面上的域号（⛔ 与模块号解耦）
DOMAIN = "m04_plan"

#: 字段清单 = 本域既有的域声明（`importer.FIELDS`）—— ⛔ 不另抄一份
FIELDS = I.FIELDS

SPEC = DomainSpec(
    domain=DOMAIN,
    title="付款计划 · 材机费",
    fields=FIELDS,
    source_label="项目付款计划（各项目人工填的 Excel）",
    batch=False,                     # 本域**无批次回滚**（同月重导 = 覆盖更新，幂等键见 `repo.merge_month`）
    note="必须有「项目」与「该流程金额」；导入前要先选**年月**（本批数据全归该月，§4.3.3）。",
    keep_note="未采（原样保留）：审批状态 / 制单人 / 项目编号 / 已付款金额 / 剩余付款金额 "
              "（后两列是 i8 派生，见 §4.3.2）。",
    ignored=(("审批状态", "本系统不采（i8/流程侧的事，不在计划表的口径里）"),
             ("制单人", "本系统不采（留痕另有来源）"),
             ("项目编号", "本系统不采（项目靠**仓库名**认，§2.7.4）"),
             ("已付款金额", "派生态（该单据的已付流水汇总）—— ⛔ 不采，免得与流水两处对不上"),
             ("剩余付款金额", "派生态（未付金额）—— ⛔ 不采，理由同上"),
             ("科目", "本系统不采（用户表的附注列）"),
             ("费用日期", "本系统不采（与「付款时间」不是一回事）"),
             ("收款单位", "本系统不采（属付款通知书的字段）")),
)


def _rows_of(records, year_month: str) -> list[dict]:
    """通用面的 `records` → 本域的**行形状**（`doc_no` 一类，见 `parse_workbook` 的 same 口径）。

    ⚠️ 两处**不是简单改名**（自测踩到 `'material_doc' is an invalid keyword argument for PlanRow`）：
    ① 本域的行字段是**单个 `doc_no`** —— 「材料／外租机械」是**同一列的二选一**（§4.3.3），
       通用面按"一列一个目标"映射 ⇒ 这一格落进 `材料单据` 或 `机械单据` 之一，**消歧要在这里补**
       （`importer.doc_kind`，与解析路同一个出口）；
    ② 金额空 ⇒ **0**（本域的 `_amount` 就是这个口径），而不是通用面的"空 ⇒ 不写"。
    """
    key_of = {f.label: f.key for f in FIELDS}
    out: list[dict] = []
    for rec in records or []:
        vals = {key_of[lb]: rec.get(lb) for lb in key_of if rec.get(lb) not in (None, "")}
        material = mechanical = ""
        for fld in ("material_doc", "mechanical_doc"):
            v = str(vals.get(fld) or "").strip()
            if not v:
                continue
            if I.doc_kind(v) == "mechanical_doc":
                mechanical = v
            else:
                material = v
        raw = dict(rec.get("raw") or {})            # ⭐ 未映射列**原样保留**（域里就是这么存的）
        raw["_row_no"] = rec.get("_row")
        raw["_material_doc"] = material
        raw["_mechanical_doc"] = mechanical
        out.append({
            "project_input": str(vals.get("project_input") or ""),
            "doc_no": material or mechanical,
            "flow_amount": to_money(str(vals.get("flow_amount") or 0)),
            "planned_amount": to_money(str(vals.get("planned_amount") or 0)),
            "pay_date": I.norm_pay_date(str(vals.get("pay_date") or ""), year_month),
            "pay_method": str(vals.get("pay_method") or ""),
            "remark": str(vals.get("remark") or ""),
            "raw": raw,
            "_row_no": rec.get("_row"),
        })
    return out


def commit(s, records, mapping_, operator, options):  # noqa: ARG001 —— `mapping_` 只进回执口径
    """落库：**原样复用** `repo.merge_month`（§9.5：同源重跑 = 更新不重复、减行不留残影）。

    `options`：`year_month`（**必填** · 本批归入哪个月）。
    ⚠️ 项目匹配在**落库前**做一次（`attach_projects`），与本域自己的路径同一句话：
       「**所见即所落**」—— 预览里看到的匹配结论就是要落的那个（⛔ 确认时重算 = 第二份口径）。
    """
    ym = str((options or {}).get("year_month") or "").strip()
    if not ym:
        raise MustReportError("导入前**必须先选「年月」**（本批数据一律归入所选月份，§4.3.3）")
    rows = _rows_of(records, ym)          # ⭐ 中文月日按所选年月补全在 `_rows_of` 里做（域内口径，通用面不管）
    if not rows:
        raise MustReportError("没有一行可落库的数据 —— 该月未被改动（不写库）")
    rows = I.attach_projects(rows, project_briefs(s))
    out = repo.merge_month(s, year_month=ym, rows=rows)
    return {"year_month": ym, **out}


def options(s) -> dict:  # noqa: ARG001 —— 本域的上下文不来自库，但签名要与通用面的钩子一致
    """**域上下文**（通用面唯一一条读端点：`GET /api/imp/{domain}/options`）—— 本域要「本批归属年月」。

    ⭐ 这里给的是**键的存在性**：壳按"域声明了哪个键就渲染哪个控件"来画（⛔ 壳里不看域号）——
      所以本域只要返回 `year_month` 这个键，壳就会把那格「本批归属年月」画出来（§4.3.3）。
    ⚠️ 值**故意留空**：默认值（北京时间当月）是**壳**的事 —— 后端塞一个"看起来像默认"的月份，
       会让「没选年月」看起来像「选过了」（而本域落库时年月**必填**，⛔ 不许出现这种假象）。
    """
    return {"year_month": ""}


HOOKS = Hooks(commit=commit, options=options)   # 无批次回滚 ⇒ 不给 `rollback` 钩子（通用面据此不挂那个端点）

__all__ = ["DOMAIN", "FIELDS", "HOOKS", "SPEC", "commit", "options"]
