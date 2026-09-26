"""`m06` 过程资料 · **通用导入域的声明与钩子**（`TAIL-75`）—— 本域接上通用导入面的那一件。

⭐ 分工（设计 §六/§七）：读表 / 表头定位 / 映射建议 / 记忆 / 预览 / 暂存全在 `import_kit`；
   本件**只声明"要什么"**并给两个钩子，而两个钩子**原样复用既有落库口径**
   （`importer.commit` → `repository.import_snapshot`）—— ⛔ **不新写第二条落库路**
   （那正是"同一口径两个主人"的老毛病）。

⚠️ **字段清单 = 核算月 ＋ 材料 10 列**；**机械 6 列刻意不在里面**（口径：机械全段手录，导入只提示不落库）。
   ⛔ 不给机械列一个"能落库的字段"—— 否则又要踩一遍 `m11` 那个静默错：
   "认得出、白名单也放行、就是不写"，全程不报错。

⭐⭐ **2026-09-26（用户报障后收口）—— 本域的两条口径都归到 `importer.plan_rows` 一处**：
  ① **合计/小计行 · 说明行 · 空行 ⇒ 跳过**（旧路 `parse_sheet` 一直如此，搬到通用面时丢了）；
  ② **不合规的核算月文本 ⇒ 这一行不收**（用户原话：「不合规的核算月文本**不收**，我说了正式导入的时候
     会改成标准格式」）—— ⚠️ **取代** 2026-09-22 那条「`2025年9月（一标）` 照收」（那只剩旧路在用）。
  ⛔ **预览（`preview`）与落库（`commit`）必须是同一个函数**：此前各写一套 ⇒ ③ 说"没问题"、④ 才报
     「第 19 行认不出」（实测晋江那份真文件），用户**走到最后才知道**。
"""

from __future__ import annotations

from app.core.errors import MustReportError
from app.import_kit.spec import DomainSpec, Hooks
from app.mod06_proc import domain as D
from app.mod06_proc import importer as I
from app.mod06_proc.service import build_import_data

#: 通用面上的**域号**（⛔ 与模块号解耦：一个模块将来有两套导入时不必拆号）
DOMAIN = "m06_proc"

#: 材料 10 列 ＋ 核算月（机械 6 列不入，见模块头 ⚠️）
FIELDS = tuple(f for f in I.FIELDS if f.key == "ym" or f.key in D.MATERIAL_KEYS)
# ⚠️ 原先这里还有一个 `_label_key()`（把记录转成"界面名 → 列 key"）—— 2026-09-26 **已删**：
#    取行这一件事**整体搬进了 `importer.plan_rows`**（③ 预览与 ④ 落库共用），本件不该再留一份
#    "哪些字段要落库"的小抄（那就是同一口径的第二个主人）。


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


def _blocks_of(bad: list[dict], notes: list[str]) -> list[dict]:
    """**③ 预览与 ④ 回执共用**的两块：`落不了库的行` ＋ `不导入的行（提示）`。

    ⛔ 别在两处各拼一份 —— 那正是"同一件事两个说法"的开端（用户按 ③ 的数核对，④ 却给另一份）。
    """
    out: list[dict] = []
    if bad:
        out.append({"title": f"⚠️ 落不了库的行（{len(bad)} 行 · 不会写进历史段）",
                    "note": "这些行**不导入**，其余行照常落库。要它们也进去：改成标准格式后**重导一次**"
                            "（先把同批整批回滚，⛔ 别让两批叠着）。",
                    "columns": ["行", "原因"],
                    "rows": [[a["line"], a["reason"]] for a in bad]})
    if notes:
        out.append({"title": "不导入的行（提示）", "columns": ["说明"],
                    "rows": [[n] for n in notes]})
    return out


def preview(s, records, mapping_, options):  # noqa: ARG001 —— `mapping_` 不参与本域的判定
    """域预览补丁（`Hooks.preview`）：⭐ **③ 就说出"能写几行 / 哪几行写不了"**。

    ⚠️ 与落库**同一个函数**（`I.plan_rows`）—— "预览说没事、落库才炸"正是用户 2026-09-26 报障的实质
      （实测：④ 报「第 19 行的核算月认不出」，而 ③ 只报了一条无关的行 35）。⛔ 别在这里另算一套行数。
    ⚠️ **只读**（`plan_rows` 是纯函数，不碰库）⇒ 「确认前一个字节都不写库」不受影响。
    """
    rows, notes, bad = I.plan_rows(records)
    return {"writable": len(rows),
            "kpis": {"能写入的行": len(rows), "不写入的行": len(bad)},
            "blocks": _blocks_of(bad, notes)}


def commit(s, records, mapping_, operator, options):  # noqa: ARG001 —— `mapping_` 只进回执口径
    """落库：**原样复用** `importer.commit` ⇒ 只写**历史段**（不碰正式段、不碰机械手录）。

    `options`：`warehouse`（项目/仓库名，**必填**）· `cutoff_ym`（截止核算月，不给 ⇒ 取导入数据最大月）
    · `batch`（批次号，不给 ⇒ `importer.next_batch()`）。

    ⭐⭐ 2026-09-26 用户裁定的两条口径，**都落在 `I.plan_rows` 这一处**（与 ③ 预览共用）：
      「**合计/说明行跳过**」＋「**不合规的核算月文本不收**（正式导入时会改成标准格式）」。
    ⚠️ **异常行只跳过自己** —— 其余行照常落库（仓内既有口径：`test_acc_oddval` 明写"好的两行照常进"）；
       只有**一行都没有**时才拒绝整批（历史段一个字不动）。
    """
    opts = dict(options or {})
    warehouse = str(opts.get("warehouse") or "").strip()
    if not warehouse:
        raise MustReportError("请先选**项目**（仓库名）—— 过程资料按项目分别存，没选就无从落库")
    rows, notes, bad = I.plan_rows(records)
    if not rows:
        why = "；".join(f"行 {a['line']}：{a['reason']}" for a in bad[:3]) or "文件里没有数据行"
        raise MustReportError(f"没有一行可落库的数据 —— {why}。历史段未被改动（不写库）")
    plan = I.ImportPlan(rows=rows, anomalies=bad, notes=notes)
    out = I.commit(s, plan, warehouse=warehouse,
                   batch=str(opts.get("batch") or I.next_batch()), operator=operator,
                   cutoff_ym=str(opts.get("cutoff_ym") or "") or None)
    out["cutoff_default"] = plan.default_cutoff        # 界面用来回显"默认截止月 = 最大核算月"
    # ⭐ ④ 的回执也要**说清有几行没写进去**（⛔ 不许只在 ③ 说过、到这里就悄悄算了）
    out["不写入的行数"] = len(bad)
    out["blocks"] = _blocks_of(bad, notes)
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
        # ⚠️ `warehouse` 是"**读数据**时的当前项目"（= 候选人里的第一个）—— 通用面**拿它当默认**用会出事
        #   （⛔ 别再把 `ctx.warehouse` 当预选值：那是"系统替你挑了一个项目"，见 §4 默认值不诱导）；
        #   它继续给着，是为了壳侧**不认域号**这条纪律下仍能读懂"这个域有项目维度"。
        "warehouse": str(data["warehouse"] or ""),
        "cutoff_ym": str(data["cutoff_ym"] or ""),
        # ⭐ **每个项目的截止核算月表**（2026-09-26）：界面上的「截止核算月」曾只在**进域那一刻**取一次，
        #   用户换项目后那个框**不跟着换**，而落库会把它**写进新项目**（A 的分界写给 B，且不报错）⇒
        #   现在壳按**当前选中的项目**查这张表。⚠️ 与 `cutoff_ym` 同表同口径（`repository.load_cutoffs`）。
        "cutoffs": dict(data.get("cutoffs") or {}),
        "batches": [str(getattr(b, "batch_no", "") or "") for b in data["batches"]],
    }


HOOKS = Hooks(commit=commit, rollback=rollback, options=options, preview=preview)

__all__ = ["DOMAIN", "FIELDS", "HOOKS", "SPEC", "commit", "options", "preview", "rollback"]
