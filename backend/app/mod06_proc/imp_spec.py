"""MOD-06 通用导入域声明和钩子。
预览与提交共用 importer.plan_rows，材料与机械分别按截止月筛选。
机械手录和导入同级；标段月份识别并按同月汇总；异常金额整批拒写。
"""

from __future__ import annotations

from app.core.errors import MustReportError
from app.import_kit.spec import DomainSpec, Hooks
from app.mod06_proc import domain as D
from app.mod06_proc import importer as I
from app.mod06_proc.service import build_import_data

#: 通用面上的**域号**（⛔ 与模块号解耦：一个模块将来有两套导入时不必拆号）
DOMAIN = "m06_proc"

#: 核算月 ＋ 材料 10 列 ＋ **机械 6 列**（= `I.FIELDS` 全部，共 17 列）—— ⭐ `TAIL-107`：机械列也要导
FIELDS = tuple(I.FIELDS)
# ⚠️ 原先这里还有一个 `_label_key()`（把记录转成"界面名 → 列 key"）—— 2026-09-26 **已删**：
#    取行这一件事**整体搬进了 `importer.plan_rows`**（③ 预览与 ④ 落库共用），本件不该再留一份
#    "哪些字段要落库"的小抄（那就是同一口径的第二个主人）。


def _ignored() -> tuple[tuple[str, str], ...]:
    """**明确不采**的列（认得出，但按口径不导入）。

    ⚠️ 为什么必须显式列出来：它们在界面上若落进"未认出"，看着就像**系统漏了** ——
      而真相是"认得，但这一列不导入"。理由写在 `why` 里，界面照原话显示。

    ⭐ 2026-09-26（`TAIL-107`）：**机械 6 列从这里删掉了**（它们改成"要导"）—— 只剩 `序号`
      （行号，系统自己编）。⛔ 别再按"机械列 = 不采"往这里加回来：那是改前的旧口径。
    """
    return (("序号", "行号，系统自己编"),)


SPEC = DomainSpec(
    domain=DOMAIN,
    title="过程资料 · 材料机械消耗汇总表",
    fields=FIELDS,
    source_label="各项目手填的消耗汇总表",
    max_rows=I.MAX_ROWS,
    batch=True,
    protect_populated_columns=True,
    ignored=_ignored(),
    note='每次导入一个项目的历史资料；材料和机械列均可导入。合计、说明和空行自动跳过。',
    keep_note='序号、合计、小计、说明和空行不导入；材料与机械列均可导入。',
)


def _blocks_of(bad: list[dict], skip_rows: list[dict]) -> list[dict]:
    """**③ 预览与 ④ 回执共用**的两块：`落不了库的行` ＋ `本来就跳过的行`。

    ⛔ 别在两处各拼一份 —— 那正是"同一件事两个说法"的开端（用户按 ③ 的数核对，④ 却给另一份）。

    ⭐ 2026-09-27（用户报障：「**请将所有不写入输出的行也进行标注**」）：第二块的**列从「说明」改成
      「行 / 原因」** —— 原先是一句"合计/小计行 2 行（行 33、34）—— 不导入"，**与表里那几行对不上号**
      （用户得自己数到第 33 行）。现在逐行给行号 ⇒ 与行级标记**同一个数**（守则 §2.7）。
    """
    out: list[dict] = []
    if bad:
        out.append({"title": f"⚠️ 写不进去的行（{len(bad)} 行）",
                    "note": '本次导入不会写入，原历史保留。修正以下行后重新预览。',
                    "columns": ["行", "原因"],
                    "rows": [[a["line"], a["reason"]] for a in bad]})
    if skip_rows:
        out.append({"title": f"本来就跳过的行（{len(skip_rows)} 行）",
                    "note": '合计、说明、空行及截止月后的行不导入；原因见各行。',
                    "columns": ["行", "原因"],
                    "rows": [[x["row"], x["why"]] for x in skip_rows]})
    return out


def _cutoff_options(options):
    opts = options or {}
    return {k: opts.get(k) for k in ("cutoff_ym", "material_cutoff_ym", "mechanical_cutoff_ym")}


def _category_block(records, rows, options, bad, skipped):
    limits = I.selected_cutoffs(rows, **_cutoff_options(options))
    labels = {field.key: field.label for field in FIELDS}
    bad_by_line = {item["line"]: item["reason"] for item in bad}
    skip_by_line = {item["row"]: item["why"] for item in skipped}
    details = []
    for record in records or []:
        ym = I.ym_of(record.get("核算月")) or I._ym_loose(record.get("核算月"))[0]
        if not ym:
            continue
        def mark(keys, cutoff):
            line = record.get("_row", 0)
            if line in skip_by_line:
                return "不导入，" + skip_by_line[line]
            if line in bad_by_line:
                return "不导入，本行须修正"
            if bad:
                return "不导入，须先修正其他异常行"
            if not any(record.get(labels[key]) not in (None, "") for key in keys):
                return "空格，不写入"
            if cutoff and ym > cutoff:
                return f"不导入，超过 {cutoff}"
            return "导入"
        details.append([record.get("_row", ""), ym, mark(D.MATERIAL_KEYS, limits["material_cutoff_ym"]),
                        mark(D.MECH_KEYS, limits["mechanical_cutoff_ym"])])
    return {"title": "材料与机械的导入范围", "note": "两类分别筛选；空格不写入，明确填写 0 会覆盖原值。材料同月显示优先 i8，机械覆盖本次写入的月份和列。",
            "columns": ["行", "核算月", "材料", "机械"], "rows": details}


def preview(s, records, mapping_, options):  # noqa: ARG001 —— `mapping_` 不参与本域的判定
    """只读预览：共享计划确认可写数、异常/跳过及逐行材料机械范围；截止分别回显。"""
    rows, skip_rows, bad = I.plan_rows(records, **_cutoff_options(options))
    writable = 0 if bad else len(rows)
    return {"writable": writable, **I.selected_cutoffs(rows, **_cutoff_options(options)),
            # ⭐ 2026-09-27（用户报障「所有不写入的行都要标」）：两个数**分开报**（守则 §4.7 口径透明）
            #    —— 用户看到"3 行没进去"会以为三行都要自己改，而其中"本来就跳过"的那几行
            #    （合计/说明/空行）**什么都不用做**。⛔ 别合成一个"不写入的行"。
            "kpis": {"能写入的行": writable, "不写入的行": len(bad),
                     "正常跳过（含截止月后）": len(skip_rows)},
            # ⭐ 2026-09-26（用户报障 · 原话：「**这些不会落库的行，要在行上直接标**，比如给一个浅色底，
            #    或者其他明确提示，这才叫好的前端设计，而不是还要**抬头去看文字说明**」）：
            #    域**自报**哪几行写不进去（通用面按 `row` 标在那一行上、把 `why` 挂成悬停原因）。
            #    ⚠️ 与 `_blocks_of` 里那两块**同一个来源**（`bad` / `skip_rows`）—— ⛔ 别另算一份。
            #    ⚠️ 显式给 `[]`（而不是省略键）：`[]` = "本域认定一行都不缺"，
            #       省略 = "本域没这个概念" —— 两者在界面上不一样（前者不标注、后者照实不标注但语义不同）。
            #    ⭐ `kind`（守则 §2.8）：`bad` = **要你处理**（改成标准格式后重导）；`skip` = **本来就跳过**
            #       （合计/说明/空行，不用你改）⇒ 壳给**两种标记**，⛔ 不能混成一种颜色/一个词。
            "skipped": ([{"row": a["line"], "kind": "bad", "why": a["reason"]} for a in bad]
                        + [{"row": x["row"], "kind": "skip", "why": x["why"]} for x in skip_rows]),
            "blocks": [_category_block(records, rows, options, bad, skip_rows)] + _blocks_of(bad, skip_rows)}


def _batch_no(s, opts: dict) -> str:
    """本批的批号：调用方给了就用它；没给 ⇒ `PROC-<yyyymmddHHMMSS>`（**秒**），**撞了就换一个**。

    ⭐ 2026-09-26（`TAIL-108`）：默认批号**到秒** ⇒ **同一秒里的第二次落库**会撞
      `proc_history_batch.batch_no` 的唯一约束，用户看到的是
      `导入失败：IntegrityError … 重复键违反唯一约束`（**天书**，守则 §5.5 不让这么报）。
      ⚠️ 诱因很自然：**连点两次「④ 确认落库」**（壳侧同批加了"提交期间禁用" —— 这里是**后端那一道**，
      ⛔ 只靠界面挡不住脚本 / 接口）。
      ⇒ 撞了就补 `-2` / `-3`…（最多试到 9；真撞满就照旧让数据库报错 —— ⛔ 不静默吞、也不编一个假批号）。
    """
    given = str(opts.get("batch") or "")
    if given:
        return given
    from app.mod06_proc import repository as repo

    base = I.next_batch()
    for n in range(1, 10):
        cand = base if n == 1 else f"{base}-{n}"
        if not repo.batch_exists(s, batch_no=cand):
            return cand
    return base


def commit(s, records, mapping_, operator, options):  # noqa: ARG001 —— `mapping_` 只进回执口径
    """落库：**原样复用** `importer.commit` ⇒ 只写**历史段**（不碰正式段、不碰机械手录）。

    `options`：`warehouse`（项目/仓库名，**必填**）· `cutoff_ym`（截止核算月，不给 ⇒ 取导入数据最大月）
    · `batch`（批次号，不给 ⇒ `importer.next_batch()`）。

    ⭐⭐ 2026-09-26 用户裁定的两条口径，**都落在 `I.plan_rows` 这一处**（与 ③ 预览共用）：
      「**合计/说明行跳过**」＋「**不合规的核算月文本不收**（正式导入时会改成标准格式）」。
    校验出现异常行时整批拒写，保留原有效历史；正常合计、说明、空行及截止后的行仍跳过。
    """
    opts = dict(options or {})
    warehouse = str(opts.get("warehouse") or "").strip()
    if not warehouse:
        raise MustReportError("请先选**项目**（仓库名）—— 过程资料按项目分别存，没选就无从写入")
    rows, skip_rows, bad = I.plan_rows(records, **_cutoff_options(opts))
    if bad:
        why = "；".join(f"第 {a['line']} 行：{a['reason']}" for a in bad[:3])
        raise MustReportError(f"本次导入未写入，原历史保留。请修正后重新预览：{why}")
    if not rows:
        why = "；".join(f"行 {a['line']}：{a['reason']}" for a in bad[:3]) or "文件里没有数据行"
        raise MustReportError(f"没有一行能写入的数据 —— {why}。历史段未被改动（没有写入）")
    # ⚠️ `notes`（`ImportPlan` 的老字段）**不再拼**：那几行现在走**逐行**的 `skip_rows`（上面
    #    `_blocks_of` 与 `skipped` 都用它）⇒ 再拼一份文本就是"同一件事两个说法"。
    plan = I.ImportPlan(rows=rows, anomalies=bad, notes=[])
    out = I.commit(s, plan, warehouse=warehouse, batch=_batch_no(s, opts),
                   operator=operator, **_cutoff_options(opts))
    out["cutoff_default"] = plan.default_cutoff        # 界面用来回显"默认截止月 = 最大核算月"
    # ⭐ ④ 的回执也要**说清有几行没写进去**（⛔ 不许只在 ③ 说过、到这里就悄悄算了）
    out["不写入的行数"] = len(bad)
    out["本来就跳过的行数"] = len(skip_rows)            # ⭐ 与"要你处理"分开报（同上）
    out["blocks"] = _blocks_of(bad, skip_rows)
    # ⭐ 2026-09-26（用户报障「**落库结果可读性比较差**」· 四个域一起改）：回执**自报人话指标** ——
    #    通用面只画 `kpis`（原始键仍留着：排查与判据都要看它们）。
    out["kpis"] = {"写入行数": int(out.get("rows") or 0), "不写入的行数": len(bad),
                   "正常跳过（含截止月后）": len(skip_rows)}
    return out


def rollback(s, batch, operator):
    """整批回滚（**置状态、不物理删**）—— 复用 `importer.rollback`。"""
    return {"revoked": I.rollback(s, batch_no=batch), "batch": batch, "operator": operator}


def options(s) -> dict:
    """按项目提供材料和机械上次导入截止；旧 cutoff_ym/cutoffs 为材料兼容别名。"""
    data = build_import_data(s, warehouse="")
    return {
        "projects": list(data["projects"]),
        # ⚠️ `warehouse` 是"**读数据**时的当前项目"（= 候选人里的第一个）—— 通用面**拿它当默认**用会出事
        #   （⛔ 别再把 `ctx.warehouse` 当预选值：那是"系统替你挑了一个项目"，见 §4 默认值不诱导）；
        #   它继续给着，是为了壳侧**不认域号**这条纪律下仍能读懂"这个域有项目维度"。
        "warehouse": str(data["warehouse"] or ""),
        "cutoff_ym": str(data["cutoff_ym"] or ""),
        "material_cutoff_ym": str(data["cutoff_ym"] or ""),
        "mechanical_cutoff_ym": str(data.get("mechanical_cutoff_ym") or ""),
        "material_cutoffs": dict(data.get("cutoffs") or {}),
        "mechanical_cutoffs": dict(data.get("mechanical_cutoffs") or {}),
        # ⭐ **每个项目的截止核算月表**（2026-09-26）：界面上的「截止核算月」曾只在**进域那一刻**取一次，
        #   用户换项目后那个框**不跟着换**，而落库会把它**写进新项目**（A 的分界写给 B，且不报错）⇒
        #   现在壳按**当前选中的项目**查这张表。⚠️ 与 `cutoff_ym` 同表同口径（`repository.load_cutoffs`）。
        "cutoffs": dict(data.get("cutoffs") or {}),
        "batches": [str(getattr(b, "batch_no", "") or "") for b in data["batches"]],
    }


HOOKS = Hooks(commit=commit, rollback=rollback, options=options, preview=preview)

__all__ = ["DOMAIN", "FIELDS", "HOOKS", "SPEC", "commit", "options", "preview", "rollback"]
