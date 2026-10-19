"""机械报表导入域：项目匹配、差异预览及机械有效值事务写入。"""

from app.core.errors import MustReportError
from app.core.money import require_non_negative, to_money
from app.import_kit.mapping import Field
from app.import_kit.spec import DomainSpec, Hooks
from app.mod06_proc import mech_matching as matching, mech_report as reader, repository

DOMAIN = "m06_mech_report"
FIELDS = (Field("ym", "核算月", type="text", required=True),
          Field("project", "报表项目名", type="text", required=True),
          *(Field(key, label, type="amount") for key, label in reader.LABELS.items()))
SPEC = DomainSpec(domain=DOMAIN, title="机械费报表", fields=FIELDS,
                  source_label="年度汇总及零租、包月明细", extra={"fixed_mapping": True},
                  note="先选月份，只导该月。空白金额保留原值；租分公司设备不导入。",
                  rule_note="按项目匹配名称写入所选月份；确认后覆盖已有金额。",
                  impacts=tuple((label, "覆盖该项目所选月份的金额；空白保留原值", "写台账")
                                for label in reader.LABELS.values()))


def options(s):
    from app.core.timing import today_cn
    today = today_cn().replace(day=1)
    from datetime import timedelta
    return {"year_month": (today - timedelta(days=1)).strftime("%Y-%m")}


def plan(s, records, options):
    """先完成全部匹配和金额校验，写入与预览共用同一份计划。"""
    ym = str((options or {}).get("year_month") or "")
    data = matching.list_rules(s)
    active = {p["warehouse"] for p in data["projects"]}
    rules = [r for r in data["items"] if r["warehouse"] in active]
    planned, unmatched, skipped = {}, set(), []
    for record in records:
        if record.get("核算月") != ym:
            raise MustReportError("导入月份已改变，请重新解析文件并预览")
        name = record.get("报表项目名") or ""
        warehouse = matching.resolve_report_project(name, rules)
        if not warehouse:
            unmatched.add(name)
            skipped.append({"row": record.get("_row"), "kind": "skip", "why": "项目名未匹配，不导入"})
            continue
        values = {}
        for key, label in reader.LABELS.items():
            raw = record.get("raw", {}).get(label, record.get(label))
            if raw is None or str(raw).strip() == "":
                continue
            try:
                values[key] = require_non_negative(raw, field=label)
            except ValueError as exc:
                raise MustReportError(f"「{name}」的{label}金额不正确，请修正后重新解析") from exc
        if not values:
            skipped.append({"row": record.get("_row"), "kind": "skip", "why": "所选月份没有金额，保留原值"})
            continue
        monthly = planned.setdefault(warehouse, {})
        for key, value in values.items():
            monthly[key] = to_money(monthly.get(key, 0)) + value
    return ym, planned, sorted(unmatched), skipped, {r["warehouse"]: r["display"] for r in rules}


def _unmatched_block(names):
    return {"title": f"未匹配项目（{len(names)} 项）", "note": "以下项目不导入。",
            "columns": ["报表项目名"], "rows": [[name] for name in names]}


def preview(s, records, mapping, options):
    ym, planned, unmatched, skipped, displays = plan(s, records, options)
    existing = {r["warehouse"]: r for r in repository.load_mech(s) if r["ym"] == ym}
    differences = []
    for warehouse, values in planned.items():
        for key, value in values.items():
            before = existing.get(warehouse, {}).get(key)
            if before is None or to_money(before) != value:
                differences.append([displays[warehouse], ym, reader.LABELS[key],
                                    "未填写" if before is None else str(to_money(before)), str(value)])
    blocks = [{"title": f"金额差异（{len(differences)} 格）" if differences else "没有差异",
               "note": "确认后覆盖以下金额。" if differences else "没有差异，确认还要导入么",
               "columns": ["项目", "核算月", "机械费项目", "原金额（元）", "导入金额（元）"],
               "rows": differences}]
    if unmatched:
        blocks.append(_unmatched_block(unmatched))
    return {"writable": len(planned), "skipped": skipped, "blocks": blocks,
            "confirmation": {"title": "确认导入机械费", "message": "确认覆盖并导入么" if differences
                             else "没有差异，确认还要导入么"},
            "kpis": {"写入项目": len(planned), "差异金额格": len(differences), "未匹配项目": len(unmatched)}}


def commit(s, records, mapping, operator, options):
    if not (options or {}).get("confirmed"):
        raise MustReportError("请先核对差异清单并确认导入")
    ym, planned, unmatched, _, _ = plan(s, records, options)
    planned = {warehouse: repository.writable_mech_values(repository.mech_row(s, warehouse, ym), values)
               for warehouse, values in planned.items()}
    planned = {warehouse: values for warehouse, values in planned.items() if values}
    with s.begin_nested():
        for warehouse, values in planned.items():
            # 与行内手录共用逐格写出口；不替换材料快照、不修改截止月，不写缺失列。
            repository.save_mech(s, ym=ym, warehouse=warehouse, values=values)
        s.flush()
    return {"rows": len(planned), "message": f"已导入 {ym} 的机械费，未匹配 {len(unmatched)} 项未导入。",
            "kpis": {"写入项目": len(planned), "未匹配项目": len(unmatched)},
            "blocks": [_unmatched_block(unmatched)] if unmatched else []}


HOOKS = Hooks(commit=commit, options=options, preview=preview, read_file=reader.read_file)
