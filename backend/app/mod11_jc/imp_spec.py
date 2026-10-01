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
    note="必须认出「**合同价**」列（供应商合同总价 / 合同总价 / 合同金额）—— 它是**匹配锚点**，"
         "认不到就一条都配不上；写入要选**项目**（仓库名）—— 匹配范围就在这个项目内。"
         "⭐ **覆盖语义**：已存在的行**会被更新**，但**只动这 6 列** —— 材料名 / 付款方式 / 备注 / "
         "存档情况 / 存档号 / 寄回日期；**合同价 / 供应商 / 合同日期 / 甲方单位**是 i8 的、"
         "**不会被覆盖**。导错了可以**整批回滚**（回执里有批次号）。",
    keep_note="不写入（系统自己算）：结算 / 付款 / 欠款；原样保留（本系统不录）：序号 / 重量 / 开票号 / 单价。",
    ignored=tuple((lb, why) for lb, why in P.IGNORED_LABELS.items()),
    #: ⭐ **这一批怎么入库**（页头一句话 · 大白话 · 用户 2026-09-26 拷问后要的）——
    #: 措辞**照代码真值**：对号键 = `EXCEL_COLS` 之外的 `contract_amt`（`import_service._amount_key`）；
    #: 只更 `EXCEL_COLS` 6 列；i8 事实列不碰（`import_service.py:353-365`）；有批次可整批回滚。
    rule_note="按「**含税合同价**」在**你选的项目里**对号：配上就更新那条，配不上**不新增**，"
              "同一个价好几条 ⇒ 系统**不猜**、跳过。"
              "有贸易公司的合同（那格「合同金额」空着）改用「**贸易公司合同金额**」对号，"
              "对上后把 Excel 的「供应商合同总价」填进「合同金额」（**空着才填**）。",
    #: ⭐ **逐列后果**（键 = **目标字段名** ⇒ 随用户改下拉实时跟着变）。
    #: ⚠️ 字段名用 `FIELD_LABELS` **反查**（⛔ 不手抄第二份列名 —— 改一处漏一处）。
    #: ⭐⭐ **去向（第三项）只许三个词**（2026-09-26 用户裁定）：
    #:   `写台账`（会盖掉台账里的值，**含"往发票子表加一张票"** —— 用户原话
    #:   「写台账和进子表为一个意思，合并为写台账」）· `当钥匙`（拿它找那张合同，合同上的原值不动）·
    #:   `不参与`（导入不用它）。⚠️ 屏上只留短词，**完整说明进悬停**（守则 §5.9 同屏做优先级）。
    impacts=tuple(
        (dict((f.key, f.label) for f in FIELDS)[key], what, kind)
        for key, what, kind in (
            # ① 写台账：那 6 列会被覆盖（`import_service.EXCEL_COLS`）
            ("material_name", "会盖掉台账「材料名称」里的原值", "写台账"),
            ("method", "会盖掉台账「付款方式」里的原值", "写台账"),
            ("remark", "会盖掉台账「备注」里的原值", "写台账"),
            ("arch", "会盖掉台账「存档」里的原值", "写台账"),
            ("arch_no", "会盖掉台账「存档序号」里的原值", "写台账"),
            ("ret_date", "会盖掉台账「寄回时间」里的原值", "写台账"),
            # ② 写台账（子表那两列，同一个词 —— 明细在悬停里）
            ("inv_sum", "往**发票子表**加一张「供应商发票」（发票日期 = **操作当天**）；"
                        "同一张合同已有同种发票就不再加（重导不会翻倍）", "写台账"),
            ("trade_inv_sum", "往**发票子表**加一张「贸易公司发票」（发票日期 = **操作当天**）；"
                              "同一张合同已有同种发票就不再加", "写台账"),
            # ③ 当钥匙：只用它找那张合同（合同上的原值不动）
            ("contract_amt", "**正常合同**：用它找台账里那张合同，合同上的数字不改；"
                             "**有贸易公司的合同**：会写进台账「合同金额」（该格**为空时才填**）", "当钥匙"),
            ("trade_contract_amt", "**有贸易公司的合同**用它找那张合同"
                                   "（那类合同的「合同金额」是空的，靠它才对得上号）", "当钥匙"),
            # ④ 不参与：导入完全不用它 —— ⚠️ 2026-09-26 用户当场纠正过：
            #    原先这三列都写着「只用来认行」，而**对号根本不用它们**（"认行"是错的，别再写回去）
            ("contract_date", "导入**不用它**（台账里的合同日期由**抓取**写）", "不参与"),
            ("supplier", "导入**不用它**（台账里的供应商由**抓取**写）", "不参与"),
            ("trade_co", "导入**不用它**（台账里的贸易公司名由**抓取**写）", "不参与"),
        )
    ),
    #: ⭐ 字段清单那段的一句话提醒（2026-09-26 用户裁定：**缺列提醒必须默认露出来**）。
    field_list_hint="⭐ **有贸易公司的合同**，结算按「**贸易公司发票金额**」的合计算 ⇒ "
                    "若你表里**没有**这一列，导完请在页面上**手工录发票**（或把这一列补进表里）。"
                    "另外：「合同金额」在台账里留空时，本轮会用 Excel 的「供应商合同总价」"
                    "**为空才填**（已有值不动）。",
)


def _rows_of(records) -> list[dict]:
    """通用面的 `records`（按字段名）→ 本域的**行形状**（key 即 `FIELD_LABELS` 的键）。

    ⭐⭐ 2026-09-27（用户报障 · 原话「**678 行明明有合同总价，但是却显示合同价为空**」）：
      把通用面的 `_row`（**Excel 行号**）一并带过来 —— 匹配结果里那一列从此是**同一个数**
      （守则 §4.7：同一个数不许在两个地方换说法）。
      ⚠️ 改前这里**丢掉了 `_row`** ⇒ `match_and_apply` 只好用"第几条数据"当行号（1 起）——
         两者差一个表头行数，页面上看不出任何毛病，**只有用户去对号时才发现对不上**（实测就是这个）。
    """
    key_of = {f.label: f.key for f in FIELDS}
    out: list[dict] = []
    for rec in records or []:
        row: dict = {key_of[lb]: rec[lb] for lb in key_of if rec.get(lb) not in (None, "")}
        if rec.get("_row") not in (None, ""):
            row["_row"] = rec["_row"]                      # ⭐ Excel 行号（见 docstring）
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
        raise MustReportError("没有一行能写入的数据 —— 台账未被改动（没有写入）")
    out = B.apply_batch(s, rows, project_id=int(project_id), project_key=key,
                        operator=str(operator or ""), batch_no=(options or {}).get("batch"))
    out["project_key"] = key
    # ⭐ 2026-09-26（用户报障「**落库结果可读性比较差**」· 四个域一起改）：回执**自报人话指标** ——
    #    通用面只画 `kpis`，⛔ 不再把 `updated` / `undo_rows` / `message` 这些**程序用的键名**铺一排。
    #    ⚠️ 词与 `preview` **完全一样**（配上 / 配不上 / 同价冲突 / 不合格）—— 同一个数在两屏不许换说法。
    out["kpis"] = {"配上并更新": int(out.get("updated") or 0),
                   "配不上": int(out.get("unmatched") or 0),
                   "同价冲突": int(out.get("ambiguous") or 0),
                   "不合格": int(out.get("bad") or 0),
                   "提醒": int(out.get("warned") or 0),
                   # ⭐ 2026-09-27：与 ③ **同一个口径**（空白行 / 合计行本来就不导）
                   "本来就跳过（空白行/合计行）": int(out.get("skipped") or 0)}
    return out


def rollback(s, batch, operator):
    """**整批回滚**（`TAIL-98`）—— 那 6 列逐列还原 ＋ 摘掉本批新加的发票行（批次置 `rolled_back`）。"""
    return B.rollback(s, batch, operator)


def preview(s, records, mapping_, options):  # noqa: ARG001 —— `mapping_` 由通用面记账，本域判定用不着
    """**域预览补丁**：③ 就能看到「配上有几条 / 配不上几条」——**只查不写**（2026-09-26 · `TAIL-106`）。

    ⭐ 用户原话：「匹配既然凭合同金额／贸易公司合同金额，为什么放到**最后一步**？能否在选文件时
      就选定项目、并**立刻显示"匹配上多少"**？」⇒ 本函数就是后半句的落点。

    ⚠️ **为什么不在这里另写一份匹配**：对号的口径（含"贸易公司合同改用贸易公司金额当钥匙""配上后
      空才填合同金额"）**只有** `import_service.match_and_apply` 一处主人 ⇒ 这里传 `dry_run=True`
      调**同一个函数**（⛔ 两份口径必然漂）。

    ⚠️ **没选项目就不猜**：台账按项目分存、对号只在项目内做 ⇒ 没选 ⇒ 一条都说不上，且**不给**
      `writable`（界面上「将写入」退回通用面的 `total`，免得用"能配上 0 条"这种假话糊人）。
    """
    key = str((options or {}).get("project_key") or "").strip()
    if not key:
        return {"blocks": [{
            "title": "还没选「这批数据进哪个项目」—— 现在还看不出能配上几条",
            "note": "台账按项目分存、对号也**只在项目内**做 ⇒ 先回第 ① 步把项目选定，"
                    "这一屏立刻会给「配上 / 配不上 / 同价冲突」三个数。",
            "columns": [], "rows": [], "empty": ""}]}
    project_id = R.project_id_by_key(s, key)
    if project_id is None:
        raise MustReportError(f"找不到项目（仓库名 {key!r}）—— 请先在「项目档案」建好")
    out = IS.match_and_apply(s, _rows_of(records), project_id=int(project_id), dry_run=True)
    bad_rows = ([["——", "——", "材料名称与供应商都空着，认不出是哪条合同", x.get("why") or ""]
                 for x in out.get("bad_items") or []])
    rows: list[list] = []
    for x in out.get("unmatched_items") or []:
        rows.append([x.get("row_no"), x.get("amount") or "（空）",
                     x.get("material_name") or "", x.get("why") or ""])
    for x in out.get("ambiguous_items") or []:
        rows.append([x.get("row_no"), x.get("amount"), "", x.get("why") or ""])
    rows += bad_rows
    return {
        # ⭐ **「将写入」改成真会更新的条数**（`writable` 覆盖通用面的 `total`）——
        #    这正是用户要的那个数：**这批能配上几条**。
        "writable": int(out["updated"]),
        # ⭐ 2026-09-27（用户报障「查一下问题在哪」· 用他**真文件**复现后定的口径）：
        #    **「本来就跳过」单独报一个数**（守则 §4.7）—— 他屏幕上"8 行没配上"里，
        #    **7 行是空白行（只填了序号）＋ 1 行是 `合计：` 行** ⇒ 合成一个数会让他以为文件有毛病。
        "kpis": {"配上": out["updated"], "配不上": out["unmatched"],
                 "同价冲突": out["ambiguous"], "不合格": out["bad"],
                 "本来就跳过（空白行/合计行）": len(out.get("skip_items") or [])},
        # ⭐ 2026-09-26（用户报障 · 原话：「**这些不会落库的行，要在行上直接标**，比如给一个浅色底，
        #    或者其他明确提示，这才叫好的前端设计，而不是还要**抬头去看文字说明**」）：
        #    域**自报**写不进去的行（配不上 / 同价冲突 / 不合格）⇒ 通用面按 `row_no` 标在那一行上。
        #    ⚠️ 与下面 `blocks` 那几张清单**同一个来源**（同一次 `dry_run` 的 `out`）—— ⛔ 别另算一份；
        #       ⚠️ **「提醒」（`warned`）不进这里**：那些行**是写进去的**（只是带了句提醒），
        #          标成"不写入"就是假话（守则 §4.2 状态必须真实）。
        "skipped": (
            # ⚠️ 行内原因**用这一行自己的** why（"合同价为空 / 为 0" / "项目内没有同价合同…"）——
            #    一句笼统的"项目内没有同价合同"会把"锚点是空"也罩进去（守则 §4.2 状态必须真实）。
            [{"row": int(x.get("row_no") or 0),
              "why": f"配不上：{x.get('why') or '项目内没有同价合同（或认不出锚点）'}"}
             for x in out.get("unmatched_items") or []]
            + [{"row": int(x.get("row_no") or 0),
                "why": "同价冲突：项目内有多条同价合同 ⇒ 系统不猜，这一行不写"}
               for x in out.get("ambiguous_items") or []]
            + [{"row": int(x.get("row_no") or 0),
                "why": f"不合格：{x.get('why') or '这一行不合格'}"}
               for x in out.get("bad_items") or []]
            # ⭐⭐ 「本来就跳过」= **空白行 / 合计行** ⇒ `kind="skip"`（壳给**灰标「不导入」**，
            #    守则 §2.8：要你处理的 vs 本来就跳过的，必须一眼分得开）
            + [{"row": int(x.get("row_no") or 0), "kind": "skip",
                "why": x.get("why") or "不是数据行 ⇒ 本来就跳过"}
               for x in out.get("skip_items") or []]),
        "blocks": [
            {"title": "没配上的行（**不会被写进台账**，台账里一条不动）",
             "note": "⚠️ 认不出锚点 / 项目内没有同价合同 / 同价有多条 —— 三种都**不猜、不新增**："
                     "先看这几行，多半是「这个项目的合同还没抓」或「第 ① 步的项目选错了」。"
                     "⛔ 空白行与合计行**不在这张表里**（见下面那张「本来就跳过的行」）。",
             "columns": ["行", "合同价", "材料名称", "原因"],
             "rows": rows,
             "empty": "（无 —— 每一行都配上了）"},
            # ⭐⭐ 2026-09-27（用户报障的**真因**）：空白行 / 合计行**本来就不该导** ——
            #    它们既不是"没配上"也不是"不合格"；单独摆一张，让人**一眼看出"不用你改"**。
            {"title": f"本来就跳过的行（{len(out.get('skip_items') or [])} 行 · **不用你改**）",
             "note": "空白行（只填了「序号」这类**不采**的列）· 尾部 `合计/小计` 行 —— "
                     "**本来就不该进台账**（⛔ 不是你文件的毛病）。"
                     "⚠️ 与上面「没配上的行」**不是一回事**：那些才要你去查。",
             "columns": ["行", "原因"],
             "rows": [[x.get("row_no"), x.get("why") or ""]
                      for x in out.get("skip_items") or []],
             "empty": "（无）"},
            {"title": "提醒（不影响本次写入）",
             "columns": ["行", "说明"],
             "rows": [[x.get("row_no"), x.get("why") or ""] for x in out.get("warn_items") or []],
             "empty": "（无）"},
        ],
    }


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


HOOKS = Hooks(commit=commit, rollback=rollback, options=options, preview=preview)

__all__ = ["DOMAIN", "FIELDS", "HOOKS", "SPEC", "commit", "options", "preview", "rollback"]
