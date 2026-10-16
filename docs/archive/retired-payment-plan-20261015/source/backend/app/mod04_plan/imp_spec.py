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
    note='可在一份表中导入多个项目；本批全部归入所选年月。同月重导替换原导入行，手动行保留。',
    keep_note='审批状态、制单人、项目编号及已付款、剩余付款金额不导入。',
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

    ⚠️ 一处**不是简单改名**：
    ① 金额空 ⇒ **0**（本域的 `_amount` 就是这个口径），而不是通用面的"空 ⇒ 不写"。
    ⭐ 2026-09-27（`TAIL-129`）：**「单据号」现在就是通用面上的一个字段**（`doc_no`）——
       原先它在通用面上被拆成 `材料单据` / `机械单据` 两个标签、这里再按编号形态"消歧"
       （`importer.doc_kind`）；用户裁定「单据号不分机械和材料」后**那套消歧整条删掉**，
       于是本函数对单据号**只是原样搬运**（⛔ 别再长出第二套口径）。
    """
    key_of = {f.label: f.key for f in FIELDS}
    out: list[dict] = []
    for rec in records or []:
        for f in FIELDS:
            # 空金额是空串；显式 None 表示通用解析失败，不能按零写入。
            if f.type == "amount" and f.label in rec and rec[f.label] is None:
                raise MustReportError(
                    f"第 {rec.get('_row')} 行「{f.label}」不是有效金额，请修正后重新导入（本批未写入）")
        vals = {key_of[lb]: rec.get(lb) for lb in key_of if rec.get(lb) not in (None, "")}
        raw = dict(rec.get("raw") or {})            # ⭐ 未映射列**原样保留**（域里就是这么存的）
        raw["_row_no"] = rec.get("_row")
        out.append({
            "project_input": str(vals.get("project_input") or ""),
            "doc_no": str(vals.get("doc_no") or "").strip(),
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
        raise MustReportError("没有一行能写入的数据 —— 该月未被改动（没有写入）")
    rows = I.attach_projects(rows, project_briefs(s))
    out = repo.merge_month(s, year_month=ym, rows=rows)
    # ⭐ 2026-09-26（用户报障「**落库结果可读性比较差**」· 四个域一起改）：回执**自报人话指标** ——
    #    通用面只画 `kpis`，⛔ 不再把 `created` / `deleted` 这些**程序用的键名**糊到用户脸上。
    #    ⚠️ 标签必须说实话：`deleted` = **该月不在本批的自动行被移出**（§9.5「减行不留残影」），
    #       ⛔ 不是"删了用户的数据"；`manual_kept` = 该月**手动行原样保留**（§9.5 手动行不被触碰）。
    return {"year_month": ym, **out,
            "kpis": {"新增": out["created"], "更新": out["updated"],
                     "移出（该月不在本批的自动行）": out["deleted"],
                     "保留手改行": out["manual_kept"]}}


def preview(s, records, mapping_, options):  # noqa: ARG001 —— `mapping_` 由通用面记账，本域判定用不着
    """**域预览补丁**：③ 列出**项目匹配盘点**（命中 / 未匹配 / 重名）—— 让人先看见再确认。

    ⚠️ 为什么现在才接上（2026-09-26 · `TAIL-106`）：`importer.match_summary` 当初**就是为预览写的**
      （注释原话"预览用的项目匹配盘点 …… 让人先看见再确认"），可它随旧导入页 2026-09-23 下架后
      **零调用** ⇒ 接上它 = **零风险复用**，⛔ 绝不另写一份盘点口径。

    ⚠️ **本域不给 `writable`**（界面上「将写入」仍用通用面的 `total`）：付款计划是**整批按月重写**
      （`merge_month`），**项目没匹配上的行照样落库**（只是挂不上项目，到计划页里再逐行处理）——
      若把 `writable` 设成"匹配上的行数"，那是**假话**（守则 §4「状态必须真实」）。

    ⚠️ 「项目」列对不上**不是错误**：本域的口径是"**不猜**，显式标未匹配"⇒ 这里只**列出来**，
      ⛔ 不拦住落库、⛔ 也不替人猜一个项目。
    """
    ym = str((options or {}).get("year_month") or "").strip()
    # ⚠️ `ym` 可能为空（老客户端 / 直接调接口）：`norm_pay_date` 对空 `ym` **原样返回**（不猜），
    #    而盘点只看「项目」列 ⇒ 对结果没有影响。
    rows = I.attach_projects(_rows_of(records, ym), project_briefs(s))
    got = I.match_summary(rows)
    # ⚠️ 本域**不给 `skipped`** —— 不是"忘了"，是**本域没有"不会落库的行"**：
    #    付款计划**整批按月重写**（`merge_month`），项目没匹配上的行**照样进库**（只是挂不上项目，
    #    到计划页里再逐行处理）⇒ 一行都不缺，界面上也就**没有行要标**（守则 §4.2 状态必须真实：
    #    加了"不写入"标记反而是假话）。`writable` 同理不给（见上面那段注释）。
    return {
        "kpis": {"项目未匹配": len(got["unmatched"]), "项目重名": len(got["multi"])},
        "blocks": [
            {"title": '项目对不上的行（仍会写入）',
             "note": '导入后到付款计划页指定项目；请核对表中项目名与档案是否一致。',
             "columns": ["行", "你表里写的项目"],
             "rows": [[x.get("row"), x.get("project_input") or ""] for x in got["unmatched"]],
             "empty": "（无 —— 每一行的项目都对上了）"},
            {"title": '项目重名（仍会写入）',
             "columns": ["行", "你表里写的项目", "对上几条"],
             "rows": [[x.get("row"), x.get("project_input") or "", len(x.get("candidates") or [])]
                      for x in got["multi"]],
             "empty": "（无）"},
        ],
    }


def options(s) -> dict:  # noqa: ARG001 —— 本域的上下文不来自库，但签名要与通用面的钩子一致
    """**域上下文**（通用面唯一一条读端点：`GET /api/imp/{domain}/options`）—— 本域要「本批归属年月」。

    ⭐ 这里给的是**键的存在性**：壳按"域声明了哪个键就渲染哪个控件"来画（⛔ 壳里不看域号）——
      所以本域只要返回 `year_month` 这个键，壳就会把那格「本批归属年月」画出来（§4.3.3）。
    ⚠️ 值**故意留空**：默认值（北京时间当月）是**壳**的事 —— 后端塞一个"看起来像默认"的月份，
       会让「没选年月」看起来像「选过了」（而本域落库时年月**必填**，⛔ 不许出现这种假象）。
    """
    return {"year_month": ""}


HOOKS = Hooks(commit=commit, options=options, preview=preview)
# ⚠️ 无批次回滚 ⇒ 不给 `rollback` 钩子（通用面据此**不挂**那个端点、壳也不画那个按钮）。

__all__ = ["DOMAIN", "FIELDS", "HOOKS", "SPEC", "commit", "options", "preview"]
