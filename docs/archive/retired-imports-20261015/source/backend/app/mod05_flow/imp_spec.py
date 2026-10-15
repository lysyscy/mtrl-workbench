"""`m05` 历史付款流水 · **通用导入域的声明与钩子**（`TAIL-75` `B5b` 第三步）—— 本域接上通用导入面的那一件。

⭐ 分工与 `m06_proc` / `m04_plan` / `m11_jc` 同款：读表 / 表头定位 / 映射建议 / 记忆 / 暂存在 `import_kit`；
   本件只声明"要什么"并给钩子，而**落库原样复用**既有出口（`importer.commit` → `repository.create_flow`
   → `sync_stat_paid`，§4.4.6/§4.4.7）—— ⛔ **不新写第二条落库路**（"同一口径两个主人"是本仓反复踩过的坑）。

⚠️ 本域的判定**一个都没搬进底座**：金额必须 > 0 / 付款时间多格式 / 付款方式归一四类 +
   归不进记「其他」且**原文留备注** / 单据号精确 1:1 匹配 —— 全在 `importer.py`（§4.4.6 的口径主人）；
   本件只把它们**编排**起来（`_plan_of` 逐行调域内的单值判定）。

⚠️ 本域**比别的域多一件**（`Hooks.preview`）：它的判据要求**预览里**就列出
   「**未匹配清单**」（单据号在本地找不到 —— 要读库）与「未识别的付款方式取值」，
   而通用面的预览是**域无关**的 ⇒ 这几块只有域自己算得出。⭐ 该钩子**只读**：
   `preview_store` 仍是预览的**唯一载具**（确认前零写库，判据 001-06 不受影响）。
"""

from __future__ import annotations

from app.core.errors import MustReportError
from app.core.money import to_money
from app.import_kit.mapping import Field
from app.import_kit.spec import DomainSpec, Hooks
from app.mod05_flow import importer as I

#: 通用面上的域号（⛔ 与模块号解耦）
DOMAIN = "m05_flow"

#: 五列各自的**引擎侧**声明：`(域内 key, 界面字段名, 类型, 别名)`。
#: ⚠️ 顺序**必须**与 `importer.COLUMNS`（§4.4.6 的固定列序）一致 —— 下面的 `zip` 是机器守卫；
#:    而 `required` **直接取 `COLUMNS` 的第三位**，⛔ 不在这里再抄一份（抄了就是两处口径）。
_FIELDS = (
    ("bill_no", "单据号", "text", ()),
    ("amount", "付款金额", "amount", ("金额",)),
    ("pay_date", "付款时间", "date", ("付款日期", "支付时间")),
    ("pay_method", "付款方式", "text", ("支付方式", "结算方式")),
    ("remark", "备注", "text", ("说明",)),
)
assert len(_FIELDS) == len(I.COLUMNS), "字段条数与 §4.4.6 的五列不符 —— 改这里要同批改 `importer.COLUMNS`"

FIELDS = tuple(
    Field(key=key, label=label, aliases=aliases, type=ftype, required=bool(req))
    for (key, label, ftype, aliases), (_, _, req) in zip(_FIELDS, I.COLUMNS)
)

SPEC = DomainSpec(
    domain=DOMAIN,
    title='历史付款流水',
    fields=FIELDS,
    source_label="NC / 网银导出的历史付款流水台账",
    max_rows=I.MAX_ROWS,
    batch=True,                       # 每次导入记批次号，同批可**整批回滚**后重导（§4.4.6 第四条）
    note='按单据号匹配已有通知书，可一次导入多个项目。未匹配或金额、日期异常的行不写入。',
    keep_note='付款方式可留空；无法识别的方式记为「其他」，原文保留在备注。',
)

#: 与引擎字段名对应的**中文列名**（`_plan_of` 取值用；⛔ 只此一处）
_LABELS = tuple(f.label for f in FIELDS)


def _plan_of(records) -> I.ImportPlan:
    """通用面的 `records` → 本域的 `ImportPlan`（**逐行复用域内的单值判定**）。

    ⚠️ **不在本层重复报"必填为空"**：通用面的**行级问题清单**（`spec.required`）已经把
       "必填为空 ⇒ 需处理"逐条列出来了 ⇒ 本函数只补**通用面看不见**的那两类：
       ① 值**非空但**不合域内口径（金额 ≤ 0 / 付款时间不可解析）；
       ② 付款方式认不出四类（归一 ＋ **原文留备注**）。
    """
    plan = I.ImportPlan()
    for rec in records or []:
        line = int(rec.get("_row") or 0)
        bill_no = str(rec.get(_LABELS[0]) or "").strip()
        amount = str(rec.get(_LABELS[1]) or "").strip()
        pay_date = str(rec.get(_LABELS[2]) or "").strip()
        method_raw = str(rec.get(_LABELS[3]) or "").strip()
        remark = str(rec.get(_LABELS[4]) or "").strip()
        if not any((bill_no, amount, pay_date, method_raw, remark)):
            continue                                   # 整行空 ⇒ 跳过（通用面已按"全空行"处理）
        if not (bill_no and amount and pay_date):
            continue                                   # 必填缺 ⇒ 通用面的问题清单已列（⛔ 不重复报）
        try:
            money = I.parse_amount(rec.get(_LABELS[1]))
        except ValueError as exc:
            plan.anomalies.append({"line": line, "bill_no": bill_no, "reason": str(exc)})
            continue
        try:
            date_text = I.parse_date(rec.get(_LABELS[2]))
        except ValueError as exc:
            plan.anomalies.append({"line": line, "bill_no": bill_no, "reason": str(exc)})
            continue
        method, recognized = I.normalize_method(method_raw)
        if not recognized:                             # 原文留备注（不丢信息，§4.4.6）
            plan.unknown_methods.append(method_raw)
            remark = (f"原付款方式：{method_raw}；{remark}" if remark
                      else f"原付款方式：{method_raw}")
        plan.rows.append(I.ParsedRow(line=line, bill_no=bill_no, amount=money, pay_date=date_text,
                                     pay_method=method, remark=remark, method_recognized=recognized))
    return plan


def _problems(plan: I.ImportPlan, split: I.ImportPlan) -> list[dict]:
    """域侧补的**行级问题清单**（行 / 列 / 原值 / 原因 —— 与通用面同形）。"""
    out: list[dict] = []
    for a in split.anomalies:
        out.append({"row": int(a.get("line") or 0), "column": "（本行）",
                    "raw": str(a.get("bill_no") or ""), "reason": str(a.get("reason") or "")})
    for meth in split.unknown_methods:
        out.append({"row": 0, "column": _LABELS[3], "raw": meth,
                    "reason": "归不进四类（现汇 / 承兑 / 供应链 / 其他）⇒ 记「其他」并把**原文留在备注**"
                              "（⛔ 不静默归一）"})
    return out


def _blocks(plan: I.ImportPlan) -> list[dict]:
    """域侧补的预览区块（**未匹配 / 异常 / 未识别**三张表 —— 即 §4.4.6 的"必须逐条列出来"）。"""
    return [
        {"title": '未匹配清单（单据号未找到，不写入）',
         "note": "⚠️ 这些行**不入库**（⛔ 不静默丢弃，也不替它猜一张通知书安上）；"
                 "先抓齐该月通知书，再用同一份文件重导这一批。",
         "columns": ["行", "单据号", "付款金额", "付款时间"],
         "rows": [[u.get("line"), u.get("bill_no"), u.get("amount"), u.get("pay_date")]
                  for u in plan.unmatched],
         "empty": "（无 —— 全部单据号都匹配上了）"},
        {"title": '异常清单（金额或日期异常，不写入）',
         "columns": ["行", "单据号", "原因"],
         "rows": [[a.get("line"), a.get("bill_no") or "—", a.get("reason")] for a in plan.anomalies],
         "empty": "（无）"},
        {"title": '未识别的付款方式取值（按「其他」写入）',
         "columns": ["付款方式（原文）"],
         "rows": [[x] for x in plan.unknown_methods],
         "empty": "（无）"},
    ]


def _report_blocks(report: dict) -> list[dict]:
    """**核对报告**两张表（§4.4.6 —— 漏记清单 ＋ **超付单列**）—— 落库/回滚后都回一次。"""
    def money(x) -> str:
        return f"{to_money(x):.2f}"

    return [
        {"title": '漏记清单（尚无付款流水的通知书）',
         "note": '核对是否确实未付，或 Excel 漏记了付款。',
         "columns": ["单据号", "单据日期", "付款项目", "审批金额"],
         "rows": [[r.get("bill_no"), r.get("doc_date"), r.get("project_name"),
                   money(r.get("amount_approved"))] for r in report.get("rows") or []],
         "empty": "（无 —— 这些月份的每张通知书都有流水了）"},
        {"title": '超付清单（实付超过审批金额）',
         "note": '历史流水按实际金额导入。请核对以下超付单据。',
         "columns": ["单据号", "单据日期", "付款项目", "审批金额", "实付合计", "超出"],
         "rows": [[r.get("bill_no"), r.get("doc_date"), r.get("project_name"),
                   money(r.get("amount_approved")), money(r.get("amount_paid")),
                   money(r.get("over_amount"))] for r in report.get("overpaid") or []],
         "empty": "（无 —— 本批月份里没有超付的单据）"},
    ]


def preview(s, records, mapping_):  # noqa: ARG001 —— `mapping_` 由通用面记账，本域判定用不着
    """**域预览补丁**：预览里就给出「将写入条数 ＋ 未匹配 ＋ 异常 ＋ 未识别付款方式」（§4.4.6）。

    ⚠️ **只读**：`known_notices` 是纯查询 ⇒ 本钩子**一个字节都不写库**（判据 001-06 的口径不变）。
    """
    plan = I.split_by_match(_plan_of(records), I.known_notices(s))
    return {
        "writable": len(plan.rows),                  # ⭐ 覆盖通用面的 `total`（那个是"解析出的行数"）
        "kpis": {"未匹配": len(plan.unmatched), "异常": len(plan.anomalies),
                 "未识别付款方式": len(plan.unknown_methods)},
        "problems": _problems(plan, plan),
        "blocks": _blocks(plan),
        # ⭐ 2026-09-26（用户报障 · 原话：「**这些不会落库的行，要在行上直接标**，比如给一个浅色底，
        #    或者其他明确提示，这才叫好的前端设计，而不是还要**抬头去看文字说明**」）：
        #    域**自报**写不进去的行（未匹配 ＋ 异常）⇒ 通用面按 `row` 标在那一行上、`why` 挂悬停。
        #    ⚠️ 与 `_blocks(plan)` 里那两张清单**同一个来源**（同一个 `plan`）—— ⛔ 别另算一份；
        #       措辞也照抄那两张清单的标题原话（`未匹配` / `异常` —— 同一个数在两屏不换说法）。
        "skipped": (
            [{"row": int(u.get("line") or 0),
              "why": f"未匹配：单据号 {u.get('bill_no')} 在本地找不到（多半是该月通知书还没抓）⇒ 不入库"}
             for u in plan.unmatched]
            + [{"row": int(a.get("line") or 0),
                "why": f"异常：{a.get('reason')}（本行不入库）"} for a in plan.anomalies]),
        }


def commit(s, records, mapping_, operator, options):  # noqa: ARG001 —— `mapping_` 只进回执口径
    """落库：**原样复用** `importer.commit`（一次付款一条独立流水 ＋ 自动重算，§4.4.6/§4.4.7）。

    `options`：`batch`（批次号，不给 ⇒ `importer.next_batch()`，每次导入都记一个）。
    ⚠️ 匹配在**落库前**做一次（与本域自己的路径同一句话）：**未匹配 / 异常的行绝不落库**，
       但**必须逐条报出来**（预览已列，回执里再给条数）。
    """
    batch = str((options or {}).get("batch") or "").strip() or I.next_batch()
    plan = I.split_by_match(_plan_of(records), I.known_notices(s))
    if not plan.rows:
        raise MustReportError(
            "没有一行能写入的数据 —— 流水未被改动（没有写入）。"
            "未匹配 / 异常的行都不写入，见预览里的两张清单")
    out = I.commit(s, plan, batch=batch, operator=operator)
    report = I.check_report(s, out["batch"])
    return {
        "batch": out["batch"], "written": int(out["written"]),
        "unmatched": len(plan.unmatched), "anomalies": len(plan.anomalies),
        "unknown_methods": len(plan.unknown_methods),
        "missing_notices": int(report["count"]), "overpaid": int(report["overpaid_count"]),
        # ⭐ 2026-09-26（用户报障「落库结果可读性差」）：**人话指标**（下面是给程序用的原始键，留作排查）。
        #  ⚠️ 前三个词与 `preview` 的 `kpis`（未匹配 / 异常 / 未识别付款方式）**逐字相同** ——
        #     同一个数在两屏不许换说法；后两个用核对报告那两张清单的标题原话（漏记 / 超付）。
        "kpis": {"写入流水": int(out["written"]),
                 "未匹配": len(plan.unmatched),
                 "异常": len(plan.anomalies),
                 "未识别付款方式": len(plan.unknown_methods),
                 "漏记（该批月份里一条流水都没有的通知书）": int(report["count"]),
                 "超付（实付 ＞ 审批金额）": int(report["overpaid_count"])},
        "blocks": _report_blocks(report),
    }


def rollback(s, batch, operator):
    """整批回滚（**置撤销 ＋ 原因留痕、不物理删**，§4.4.6 第四条）—— 复用 `importer.rollback`。

    ⚠️ 回滚后**再给一次核对报告**（与本域自己的页面同款：回滚会改变"该类月份有没有流水"的结论）。
    """
    out = I.rollback(s, batch, changed_by=operator)
    report = I.check_report(s, out["batch"])
    return {**out, "missing_notices": int(report["count"]),
            "overpaid": int(report["overpaid_count"]), "blocks": _report_blocks(report)}


HOOKS = Hooks(commit=commit, rollback=rollback, preview=preview)

__all__ = ["DOMAIN", "FIELDS", "HOOKS", "SPEC", "commit", "preview", "rollback"]
