"""集采台账 Excel **导入服务**（`M5-8`）—— 预览 ＋ 确认落库。

⭐ **形式**（用户 2026-09-19 定）：**上传他原来的台账** → 预览（含**列名核对**）→ 确认落库。
   ⛔ 不做"下载模板再填"作主路（他**已经有数据**；让表迁就模板 = 让工作方式迁就软件）。

⭐ **为什么不存暂存文件 / 不发 token**（这是本设计的关键取舍）：
   `parse` 只回**预览用的元信息**（工作表 / 列名 / 映射 / 条数 / 样例 / 跳过账），
   **不回全量行**；到 `commit` 时**前端把同一个文件再传一次**（它一直持有那个 `File` 对象）。
   ⇒ 服务端**无状态**：没有 tmp 文件要清理、不怕重启、不怕并发；而且**数据始终由后端自己解析**
     （⛔ 前端回传的"行数据"一律不信 —— 那才是最容易埋雷的做法）。

⭐⭐ **落库口径（2026-09-20 用户定案，覆盖 09-19 的"已存在不动"）**：

> 用户原话：「以**合同价为唯一锚点**，做到**两者互不覆盖**……单个项目同合同价的，就可以进行匹配，
> 用 excel 里的**材料名、发票金额、贸易公司发票金额、备注、存档、存档序号、寄回情况**来**覆盖** i8 抓出来的数据」

⇒ 流程是「**先抓 i8**（合同已在库里）→ **再导 Excel**（Excel 是来**补信息**的）」
  ⇒ 所以 **锚点 = 含税合同价**（`contract_amt`），**范围 = 单个项目内**（实测 347 条里只有 1 组同价：
  许昌安彩 `178600.00` 两条 —— 那是**同一份合同录了两遍**，不是"系统允许同价"）。

| Excel 行 | 动作 |
|---|---|
| 合同价**为空** | ⛔ **不参与匹配**（空值不许去撞任何行）⇒ 列进"配不上" |
| 命中 **1** 条 | ✅ **更新那条**：材料名 / 备注 / 存档三列 ＋ **汇总发票行**（用户列的字段） |
| 命中 **0** 条 | ⚠️ 列进"配不上"（⛔ **不静默新增** —— 锚点找不到 = 有问题，得先看） |
| 命中 **≥2** 条 | ⚠️ 列进"同价冲突"（**不猜** —— 和人挑供应商同一个道理） |

⚠️ **"互不覆盖"的机器化落点**：Excel **只动**它自己的地盘那几列；
  i8 的事实列（合同价 / 供应商 / 合同日期 / 甲方单位）**一个字都不碰**
  （反向由 `repository.FETCH_*` 三分法保证：i8 抓取也不碰 Excel 的地盘）。

⚠️ **发票汇总行**（用户 2026-09-19 定：「直接把台账中的数导入到发票子表里的一条里」）：
  ⛔ **不重复加** —— 该合同**已有同 kind 的发票行** ⇒ 跳过并**报出来**（再导一次不会翻倍）。
  付款**不导**（台账里的"付款"列是**派生**的，导它会**重复计入**，见 `M5-5`）。

⭐ 2026-09-22（`TAIL-75` B4）：接上 `import_kit` 的**建议 / 交叉校验 / 记忆**三件 ——
   ⛔ **判定口径与"锚点匹配落库"一字未改**：
   | 件 | 在哪 | 谁拍板 |
   |---|---|---|
   | 未认出列的**引擎建议**（带置信度） | `preview` 回的 `suggest` | 界面预选 ＋ 标「需你确认」（⛔ 引擎不直接落库） |
   | **值画像交叉校验**（防"名字认对、列拿错"） | `preview` 回的 `mapping.suspect` | 人核对（⛔ 系统不改判定） |
   | **映射记忆**（表头指纹 → 映射） | `preview` 回的 `memory` / `commit` 落库后写入 | 人（标「来自记忆 · 可改」） |
"""

from __future__ import annotations

from collections import Counter
from decimal import Decimal

from app.core import timing
from app.core.errors import human_reason
from app.mod11_jc import excel_parse as P
from app.mod11_jc import repository as R

#: 预览里每张表给几行样例（够人核对列名对不对就行，⛔ 不回全量 —— 见模块头那个取舍）。
SAMPLE_ROWS = 3

#: 预览里最多列几条"跳过的行"（全量太长没人看；落库回执里会给全量）。
SKIP_SHOW = 12

#: ⭐ 内容画像取多少行值来"看这列是什么"（`B4` 交叉校验用；够判就停，⛔ 不回传这些值）。
SAMPLE_SCAN = 30

#: 映射记忆的**域标签**（⛔ 不许与别的域混用 —— `profile_store` 会拦跨域套用）。
DOMAIN = "m11_jc"

#: ⚠️ 存档三列**走白名单** `update_contract`（它们不在 i8 抓取的刷新范围里 —— 那是**人的地盘**）。
#: ⚠️ 原先还有一个 `_CORE`（"主表字段 → `insert_contract` 入参名"），**2026-09-20 随口径改成
#: "锚点匹配 ⇒ 更新已有"后就没用了** ⇒ **删掉**（本仓纪律：⛔ 不留"已废弃但仍能被调用"的死代码）。
#: ⚠️ 同理，`_EXTRA = ("arch","arch_no","ret_date")` 也随下面的 `EXCEL_COLS` **一起删了** ——
#: 它俩本来就是同一件事的两半，留一半只会让下一个人**再漏一次**（2026-09-20）。

#: ⭐⭐ **Excel 能覆盖的主表列**（= "Excel 的地盘"）—— 用户 2026-09-20 列的字段。
#:
#: | 列 | 用户当时的说法 |
#: |---|---|
#: | `material_name` | 材料名 |
#: | `remark` | 备注 |
#: | `arch` / `arch_no` / `ret_date` | 存档 / 存档序号 / 寄回情况 |
#:
#: ⛔ **不在其中**的 = 来自 i8 的事实列（`contract_amt` / `supplier` / `contract_date` / `party_name`）
#:    —— 两边**互不覆盖**，见模块头。
#:
#: ⚠️⚠️ 为什么要抽成一个常量（而不是像原先那样在循环里写死 `("material_name", "remark")`）：
#:    **漏一列 = 那一列"认得出、白名单也放行、就是不写"，且全程不报错**。
#:    2026-10-14付款方式列取消后，不再映射或覆盖该字段。
#:    ⇒ 列的**唯一主人**在这儿；⚠️ 它与 `R.EDITABLE_COLS` 必须**是子集关系**（否则会被静默忽略），
#:    已由 `tests/test_acc_jc_import.py` 的一条断言钉住。
EXCEL_COLS: tuple[str, ...] = ("material_name", "remark", "arch", "arch_no", "ret_date")


# ============================================================ 预览

def _store(store=None):
    """映射记忆 ⇒ `ProfileStore`（可注入以便测；构造失败 ⇒ `None` ⇒ **导入照常**，⛔ 记忆坏了不许卡住导入）。"""
    if store is not None:
        return store
    try:
        from app.import_kit.profile_store import ProfileStore

        return ProfileStore()
    except Exception:                       # noqa: BLE001
        return None


def _samples(grid: list[list[str]], labels: list[str], *, row2: int) -> dict[int, list]:
    """表头下面若干行 → `{列下标: [值…]}`（**只服务画像**：⛔ 不改判定、⛔ 不回传这些值）。"""
    out: dict[int, list] = {}
    for row in grid[row2 + 1: row2 + 1 + SAMPLE_SCAN]:
        for i in range(len(labels)):
            v = str(row[i]).strip() if i < len(row) else ""
            if v:
                out.setdefault(i, []).append(v)
    return out


def _memory(store, labels: list[str]) -> dict | None:
    """记忆命中 ⇒ 给界面**预选**用：`{"mapping": {列下标: 字段}, "note", "sim"}`；没命中 ⇒ `None`。

    ⚠️ 记忆按**源列原文**存 ⇒ 这里按原文对应回列下标；**重复列名一律不预填**（原文↔列不是一对一，⛔ 不猜）。
    ⛔ 只是"预选"：人在界面上点头后走 `mapping`（那条路早就有）。
    """
    st = _store(store)
    if st is None:
        return None
    pre = st.prefill(DOMAIN, labels)
    if not pre:
        return None
    stored, note, sim = pre
    by_label = {v: k for k, v in P.FIELD_LABELS.items()}
    counts = Counter(labels)
    out: dict[str, str] = {}
    for i, lb in enumerate(labels):
        if counts[lb] > 1:
            continue
        fld = stored.get(lb)
        if fld and fld in by_label:
            out[str(i)] = by_label[fld]
    return {"mapping": out, "note": note, "sim": sim} if out else None


def _remember(store, labels: list[str], mapping: dict, *, filename: str, sheet: str) -> None:
    """落库成功后**存记忆**（表头指纹 → 映射）：同一来源第二次导入近似零操作。

    ⚠️ 只记**认出的字段**（且列名唯一）—— ⛔ 不记"忽略"项：多问一次不会错，记错了才会错。
    """
    st = _store(store)
    if st is None:
        return
    counts = Counter(labels)
    saved: dict[str, str] = {}
    for fld, idx in (mapping.get("fields") or {}).items():
        lb = labels[idx] if idx < len(labels) else ""
        if lb and counts[lb] == 1:
            saved[lb] = P.FIELD_LABELS.get(fld, fld)
    if saved:
        st.save(DOMAIN, labels, saved, source_label=f"{filename}·{sheet}")


def preview(data: bytes, filename: str, *, store=None) -> dict:
    """文件 ⇒ **每张工作表**的预览（列名 / 映射 / 条数 / 样例 / 跳过账）。

    ⚠️ ⛔ **不"取第 N 张表"**：用户样例的**第 1 张就是空表**（真数据在第 2 张）
       ⇒ 一律把表列出来，只给个"像主台账"的**提示**（`guess`），由人选。

    ⭐ `B4` 新增三项（⛔ 都不改判定，只加值）：`suggest`（未认出列的**引擎建议**，一律"需你确认"）·
       `mapping.suspect`（**值画像**与字段类型矛盾 ⇒ 提示可能认错列）· `memory`（**记忆预填** ＋ 来源说明）。
    """
    sheets: list[dict] = []
    for name in P.sheet_names(data, filename):
        info: dict = {"name": name}
        try:
            grid = P.read_grid(data, filename, name)
        except Exception as exc:                       # noqa: BLE001 —— 单表读坏不该拖垮整个预览
            info.update({"error": human_reason("这个工作表读不了（已跳过）", exc), "guess": False})
            sheets.append(info)
            continue
        rows = len(grid)
        cols = max((len(r) for r in grid), default=0)
        info.update({"rows": rows, "cols": cols})
        if rows == 0 or cols == 0:
            info.update({"guess": False, "note": "空表（没什么可导的）"})
            sheets.append(info)
            continue

        r1, r2 = P.detect_header(grid)
        labels = P.header_labels(grid, row1=r1, row2=r2)
        samples = _samples(grid, labels, row2=r2)                # ⭐ B4：只服务画像
        mapping = P.map_columns(labels, samples=samples)
        parsed = (P.parse_rows(grid, row2=r2, fields=mapping["fields"])
                  if mapping["fields"] else {"rows": [], "skipped": []})
        info.update({
            "header": {"row1": r1 + 1, "row2": r2 + 1},          # ⚠️ 给人看 ⇒ 1 基
            "labels": labels,
            "mapping": mapping,
            # ⭐ B4 三项（⛔ 不改判定）：未认出列的**建议**（一律"需你确认"）· **记忆预填** ·
            #    值画像矛盾（在 `mapping["suspect"]` 里，与 `fields` 并列）
            "suggest": P.suggest_unknown(labels, mapping, samples),
            "memory": _memory(store, labels),
            "counts": {"data": len(parsed["rows"]), "skipped": len(parsed["skipped"])},
            "sample": parsed["rows"][:SAMPLE_ROWS],
            "skipped": parsed["skipped"][:SKIP_SHOW],
            # 「像主台账」= 认出了字段 **且** 真有数据行
            "guess": bool(mapping["fields"]) and len(parsed["rows"]) > 0,
            # ⚠️⚠️ 认不出**锚点列**（合同价）⇒ 其它列认得再全，也**一条都配不上**
            #    （用户 2026-09-20：「有的合同里根本没有贸易公司合同金额和发票金额这两列，
            #     要注意匹配的问题」）⇒ 提前标出来。
            #    ⭐ `commit` 侧**还会再拦一次**（那里才是真动手的地方，见那段注释）。
            "anchor_missing": (bool(mapping["fields"]) and "contract_amt" not in mapping["fields"]),
            "note": ("⚠️ 没认出「合同价」列（供应商合同总价 / 合同总价 / 合同金额）"
                     "—— 它是**匹配锚点**，认不到就会**一条都配不上**"
                     if mapping["fields"] and "contract_amt" not in mapping["fields"] else ""),
        })
        sheets.append(info)
    # ⚠️ 只**排序**、不筛选：像主台账的排前面（人选起来快），但每张表都在
    sheets.sort(key=lambda s: (not s.get("guess"), -int(s.get("rows") or 0)))
    # ⚠️ `field_labels` 回给前端**显示用**（"系统认成 合同日期"要给人看中文名，⛔ 不是给码看 `contract_date`）
    return {"ok": True, "file": filename, "sheets": sheets, "field_labels": P.FIELD_LABELS}


# ============================================================ 落库

def _amount_key(v) -> str:
    """**锚点键**：金额归一成两位小数的字符串 —— `"100"` 与 `"100.00"` 必须是**同一个锚点**。

    ⚠️ **空 / 0 / 不是数 ⇒ 回空串**（= **不参与匹配**）：
       ⛔ 绝不让一个空锚点去"撞"库里任何一行 —— 那是"静默张冠李戴"最省事的做法。
    ⚠️ 用**字符串**做字典键（`Decimal` 可哈希但 `100` 与 `100.0` 不等价，字符串化后才稳）。
    """
    raw = str(v if v is not None else "").strip().replace(",", "").replace("¥", "")
    if raw == "":
        return ""
    try:
        d = Decimal(raw)
    except Exception:                       # noqa: BLE001 —— 认不出 ⇒ 当"没有锚点"，不是抛错
        return ""
    if d == 0:
        return ""
    return str(d.quantize(Decimal("0.01")))


#: 合计 / 小计行（不导入、不参与匹配）—— ⚠️ 与 `m06_proc` 同口径
_TOTAL_WORDS = ("合计", "小计", "总计")


def _row_kind(row: dict) -> str:
    """这行**是不是数据行**：`""` = 是（照常匹配）· `"合计/小计行"` · `"空行"`。

    ⚠️ 为什么必须有这一层（2026-09-27 用户报障 · **用他的真文件复现的**）：他文件里
      · **Excel r9~r15** 只填了「序号」（6~12）、其余全空 ⇒ 原来被报成「合同价为空 / 为 0」✗
      · **Excel r16** 是 `合计：` 行（合同总价 = 1011277，正是那些行金额之和）⇒ 原来被报成
        「项目内没有合同价 = 1011277 的合同」✗（用户会去追一条**根本不存在的合同**）
      ⇒ 两种都**不是"数据有问题"**（本来就不该导）⇒ 归「本来就跳过」，
        ⛔ 不许混进"没配上的行"（用户原话：「678 行明明有合同总价，但是却显示合同价为空」）。
    ⚠️ 「空行」= **一个映射字段都没有**（只填了「序号」这种**不采**的列）—— 通用面 `_records` 只跳
      "整行全空"，所以这种行会走到这里 ⇒ 得在这儿认出来。
    ⚠️ 口径与 `m06_proc.importer._row_kind_of` **同源**（合计/小计/总计 ＋ 空行）；⭐ 第三个域也要时再抽进 `import_kit`。
    """
    vals = [v for k, v in row.items() if k != "_row"]      # ⚠️ `_row` 是行号，不算"值"
    text = " ".join(str(v) for v in vals)
    if any(w in text for w in _TOTAL_WORDS):
        return "合计/小计行"
    if not any(str(v).strip() for v in vals):
        return "空行"
    return ""


def _skip_why(kind: str) -> str:
    """「本来就跳过」逐行一句人话 —— ⭐ **必须说清"不用你改"**（守则 §2.8：别让人以为文件有毛病）。"""
    if "合计" in kind or "小计" in kind:
        return "尾部合计/小计行 —— 不是数据行，**本来就跳过**（不用你改）"
    return "空白行（只填了「序号」这类不采的列）—— **本来就跳过**（不用你改）"


def _row_problem(row: dict) -> str:
    """这行为什么**不能落库**（`""` = 可以）。⚠️ 返回**给人看的一句话**。"""
    if not str(row.get("material_name") or "").strip() and not str(row.get("supplier") or "").strip():
        return "材料名称与供应商都空着（认不出这是一条什么合同）"
    return ""


def commit(s, data: bytes, filename: str, *, sheet: str, project_key: str,
           mapping: dict | None = None, row1: int | None = None, row2: int | None = None,
           store=None) -> dict:
    """确认落库（**幂等**：已存在的行不动）。

    `row1` / `row2` 是**人看的两行表头号（1 基）**（前端预览里可改）；不给就用探测值。
    `mapping` = 人在预览页手改的列映射（`{"列下标": "字段名"}`，值 `""` = 忽略）⇒ **优先于**别名表。
    `store` = 映射记忆（默认取 `artifacts/import_profiles.json`；⭐ 落库成功后把这次**确认过的映射**记下）

    ⚠️ 只用**主表行** ＋ **两条汇总发票行**；**付款不导**（见模块头）。
    """
    project_id = R.project_id_by_key(s, project_key)
    if project_id is None:
        return {"ok": False, "kind": "err",
                "message": f"找不到项目（仓库名 {project_key!r}）—— 请先在「项目档案」建好"}

    grid = P.read_grid(data, filename, sheet)
    d1, d2 = P.detect_header(grid)
    r1 = (int(row1) - 1) if row1 else d1
    r2 = (int(row2) - 1) if row2 else d2
    labels = P.header_labels(grid, row1=r1, row2=r2)
    m = P.map_columns(labels, mapping=mapping)
    fields = m["fields"]
    if "contract_date" not in fields and "material_name" not in fields:
        return {"ok": False, "kind": "err",
                "message": "列名还没对上：至少要认出「合同日期」或「材料名称」—— 请在预览页把列名点对"}

    # ⭐⭐ **锚点列必须在**（用户 2026-09-20：「有的合同里根本没有贸易公司合同金额和发票金额这两列，
    #     要注意匹配的问题」）—— 匹配锚点 = **含税合同价**（`contract_amt`），范围 = 单个项目内。
    #     ⚠️⚠️ 认不到它 ⇒ **每一行都会走进 "配不上"** ⇒ 回执是一大片"配不上"，而人**看不出根因是列没认对**
    #        （会以为"这些合同库里都没有"）⇒ 必须**在动手之前**拦住并说清（禁静默）。
    #     ⚠️ 注意：**缺「贸易公司那两列」不是错**（实测兰考 / 内蒙宜化 / 周口太康就是那样）——
    #        那两列只是"不更新"而已；真正致命的是缺**锚点**这一列。
    if "contract_amt" not in fields:
        return {"ok": False, "kind": "err", "message": (
            "这张表**没认出「合同价」列**（认得的写法：供应商合同总价 / 合同总价 / 合同金额）—— "
            "它是**匹配用的锚点**（在同一个项目里按它找已有合同），认不到就会**一条都配不上**。"
            "请在预览页把那一列点成「供应商合同总价」；若这张表本来就**没有**合同价列，"
            "那它导不了（没有锚点就无从判断该更新哪一条）。")}

    parsed = P.parse_rows(grid, row2=r2, fields=fields)
    out = match_and_apply(s, parsed["rows"], project_id=int(project_id), mapped=set(fields))
    try:                                    # ⭐ `B4` 映射记忆（写失败不影响本次导入）
        _remember(store, labels, m, filename=filename, sheet=sheet)
    except Exception:                       # noqa: BLE001
        pass
    return {"ok": True, "kind": "ok", "file": filename, "sheet": sheet,
            "project_key": project_key, **out,
            "header": {"row1": r1 + 1, "row2": r2 + 1}, "mapping": m,
            "skipped_rows": parsed["skipped"]}


def match_and_apply(s, rows: list[dict], *, project_id: int, mapped: set[str] | None = None,
                    dry_run: bool = False) -> dict:
    """⭐ **按「含税合同价」锚点匹配并更新**（本域落库的**唯一口径**）—— 从 `commit` 里拆出来。

    ⚠️ 为什么要拆（`TAIL-75` `B5b`）：**通用导入面自己已经把行解析好了**（它不发 token、也不再要文件）
    ⇒ 它没有"重读文件"这条路 ⇒ 只能复用本函数；⛔ 绝不让通用面另写一份匹配逻辑
    （"同一口径两个主人"是本仓反复踩过的坑）。

    `mapped` = 这次**映射出了哪些字段**（`commit` 传 `set(fields)`；通用面传 `None` ⇒ 行里有什么算什么）——
    它只管"**哪些列可更新**"（`EXCEL_COLS` 白名单），⛔ 不改匹配口径、也不动 i8 的事实列。

    ⭐⭐ `dry_run=True` = **只分类、不写库**（2026-09-26 · `TAIL-106` 用户裁定）：
      预览要在**落库之前**告诉人"这批能配上几条"，而"配上/配不上/同价冲突"这套分叉**只有这里知道**
      ⇒ 给它一个"只看不写"的开关，⛔ **不是**让预览另写一份匹配（那就是两份口径）。
      三处写口（`update_contract` / `fill_contract_amt_if_blank` / `_add_invoice`）在 `dry_run` 下**全部跳过**；
      分类结果、`items`（含"**会**填金额"）与真跑**逐字段一致**，只是库里一个字节没动。
      ⚠️ 判据：`tests/test_imp_m11_api.py` 钉着"预览/干跑后库里一模一样"（零写库）。
    """
    from sqlalchemy import select

    from app.mod11_jc.models import JcContract, JcInvoice

    # ⭐⭐ **锚点索引**（2026-09-26 用户裁定 · 方案②：**按合同类型分叉**）：
    #    · **贸易公司合同**（`trade_contract_amt` 有值 / 记了贸易公司名）⇒ 用「**贸易公司合同金额**」
    #      当钥匙 —— 它的「合同金额」（供应商价）在 i8 里**根本没有**、按设计**留空**
    #      （见 `upsert_fetched_contracts` 的"按甲方类型分叉"），空值当不了钥匙
    #      ⇒ 以前这类合同**永远配不上**（Excel 里那个真供应商价永远进不来）。
    #    · 其余合同 ⇒ 仍用「合同金额」（含税合同价）当钥匙 —— **口径一字未改**。
    #    ⚠️ 一次查完 ⇒ ⛔ 不逐行查 = N+1。
    by_amt: dict[str, list] = {}
    by_trade: dict[str, list] = {}
    for c in s.execute(select(JcContract).where(JcContract.project_id == int(project_id))).scalars():
        if c.trade_contract_amt is not None or str(c.trade_co or "").strip():
            k = _amount_key(c.trade_contract_amt)
            if k:
                by_trade.setdefault(k, []).append(c)
            continue                    # ⛔ 贸易公司合同**不进** `by_amt`（免得拿供应商价那条路撞错行）
        k = _amount_key(c.contract_amt)
        if k:
            by_amt.setdefault(k, []).append(c)

    updated: list[dict] = []
    unmatched: list[dict] = []
    ambiguous: list[dict] = []
    bad: list[dict] = []
    warned: list[dict] = []
    skip_rows: list[dict] = []          # ⭐ 「本来就跳过」：空白行 / 合计行（见 `_row_kind`）
    for n, row in enumerate(rows, start=1):
        # ⭐⭐ 2026-09-27（用户报障 · 原话「**678 行明明有合同总价，但是却显示合同价为空**」）：
        #    两个「行」不是一个数 —— 块里写的是**第几条数据**、数据表写的是 **Excel 行号**；
        #    用户拿"行 6"去表里找，找到的是**另一行**（真数据，当然有合同价）。
        #    ⇒ **行号一律取 Excel 行号**（通用面解析时给每行打了 `_row`，`imp_spec._rows_of` 带过来）；
        #    退回 `n` 只在**没有 `_row`** 时发生（旧路 / 直接调本函数）—— 保守兼容。
        row_no = int(row.get("_row") or n)
        # ⭐⭐ 同一轮（用**他的真文件** `内蒙宜化套筒窑项目集采台账.xlsx` 复现出来的）：
        #    · **Excel r9~r15** 只填了「序号」（6~12）的**空白行** ⇒ 原来报「合同价为空」✗
        #    · **Excel r16** 是 `合计：` 行（合同总价 1011277 = 上面各行之和）⇒ 原来报
        #      「项目内没有合同价 = 1011277 的合同」✗（用户会去追一条**根本不存在的合同**）
        #    ⇒ 这两种**本来就不该导**（不是"数据有问题"）⇒ 先分类，归「本来就跳过」，
        #    ⛔ 不许混进"没配上的行"（那会让人以为自己的文件有毛病 —— 正是这次报障的实质）。
        kind = _row_kind(row)
        if kind:
            skip_rows.append({"row_no": row_no, "kind": kind, "why": _skip_why(kind)})
            continue
        # ⭐ **先按「贸易公司合同金额」对号**（只有在 Excel 那行**填了这一列**时才走）——
        #    它对应库里**贸易公司合同**的钥匙；对上 ⇒ 这一行的「供应商合同总价」就是那合同的
        #    **合同金额**（空才填，见下）。0 命中 ⇒ 退回按「合同金额」对号（正常合同那条路，不变）。
        key_kind = ""
        key = ""
        cands: list = []
        trade_key = _amount_key(row.get("trade_contract_amt"))
        if trade_key:
            cands = by_trade.get(trade_key) or []
            if cands:
                key_kind, key = "trade", trade_key
        if not cands:
            raw_amt = row.get("contract_amt")
            key = _amount_key(raw_amt)
            if not key:
                unmatched.append({"row_no": row_no, "amount": str(raw_amt or ""),
                                  "material_name": str(row.get("material_name") or ""),
                                  "why": "**合同价为空 / 为 0** ⇒ 不参与匹配"
                                         "（⛔ 空值不许去撞库里任何一行）"})
                continue
            cands = by_amt.get(key) or []
            key_kind = "amount" if cands else ""
        if len(cands) == 0:
            unmatched.append({"row_no": row_no, "amount": key,
                              "material_name": str(row.get("material_name") or ""),
                              "why": f"该项目内**没有**合同价 = {key} 的合同（⛔ 不静默新增 —— 锚点找不到先看）"})
            continue
        if len(cands) > 1:
            ambiguous.append({"row_no": row_no, "amount": key,
                              "ids": [int(c.id) for c in cands],
                              "why": f"该项目内有 **{len(cands)}** 条同价合同 ⇒ **不猜**（和人挑供应商同一个道理）"})
            continue

        cur = cands[0]
        cid = int(cur.id)
        problem = _row_problem(row)
        if problem:
            bad.append({"row_no": row_no, "why": problem})
            continue

        # ⭐ **只更"Excel 的地盘"那几列**（用户 2026-09-20 列的字段）——
        #    ⛔ 合同价 / 供应商 / 合同日期 / 甲方单位**一个字都不碰**（那是 i8 的事实，两边互不覆盖）。
        # ⚠️⚠️ 必读：**拼 cols 这一步漏一列 = 那一列"认得出、白名单也放行、就是不写"**，
        #    而且**全程不报错**（2026-09-20 真机踩到：`method` 就是这么丢的 ——
        #    用户表里那列叫「详细付款方式」，预览页显示"已认成 付款方式"，
        #    落库后**台账里却一个都没有**）。⇒ 列的**唯一主人** = `EXCEL_COLS`，⛔ 别再散在循环里写死。
        cols: dict = {}
        allowed = set(mapped) if mapped is not None else set(row)
        for k in EXCEL_COLS:
            if k in allowed:
                cols[k] = row.get(k)
        if cols and not dry_run:
            R.update_contract(s, cid, **cols)

        # ⭐ **贸易公司合同那一支**（2026-09-26 方案② · 用户裁定）：这一行是**靠贸易公司金额对上**的
        #    ⇒ Excel 的「供应商合同总价」就是这张合同的**合同金额**（i8 里没有这个数 ⇒ 台账那格空着）
        #    ⇒ **空才填**（已有值一个字不改）。⛔ 不走 `update_contract`（那把"人能改 i8 事实列"放进白名单）。
        # ⚠️ `dry_run` 下走**同一个判据**的只读形态（`R.contract_amt_is_fillable`）——
        #    所以预览说的"会填"与真跑填的是同一件事（⛔ 不许在预览里另写一份"空才填"）。
        filled = False
        if key_kind == "trade":
            filled = (R.contract_amt_is_fillable(cur, row.get("contract_amt")) if dry_run
                      else R.fill_contract_amt_if_blank(s, cid, row.get("contract_amt")))

        # ⭐ **汇总发票行**：⛔ **不重复加** —— 已有同 kind 的发票行 ⇒ 跳过并报出来（再导一次不会翻倍）。
        already = {str(x) for x in s.execute(
            select(JcInvoice.kind).where(JcInvoice.contract_id == cid)).scalars()}
        for fld, kind, label in (("inv_sum", "supplier", "供应商"),
                                 ("trade_inv_sum", "trade", "贸易公司")):
            amt = row.get(fld)
            if amt in (None, ""):
                continue
            if kind in already:
                warned.append({"row_no": row_no, "why": f"合同 #{cid} 已有「{label}发票」行 ⇒ **未重复导入**"
                                                   f"（发票子表是一合同 1..N 张，重导会翻倍）"})
                continue
            # ⭐ **发票日期 = 操作当天（北京时间）** —— 2026-09-26 用户裁定：
            #    「新加的发票行的发票日期，**不要用合同日期，用操作时的日期**」。
            #    ⚠️ 原先取 `row["contract_date"]`（Excel 里的合同日期）⇒ 与"这张票是什么时候录进系统的"
            #    不符（发票要能对上所属期，本来关心的就是**录入这一天**）；真取不到日期就整条不落
            #    ⇒ 发票额白导、且人看不出为什么（现在这条 warned 分支也一并删掉了）。
            date = timing.to_iso(timing.today_cn())
            if not date:                                  # pragma: no cover —— `today_cn()` 恒有值
                warned.append({"row_no": row_no, "why": f"{label}发票额没落 —— 取不到当天日期"})
                continue
            if dry_run:
                # ⚠️ **只看不写**：`already` 照样记上（同一份表里后续行遇到同 kind 也按"加过了"算）
                #    ⇒ 干跑与真跑**逐行同判定**，⛔ 不然预览会多报几张票。
                already.add(kind)
                continue
            inv = _add_invoice(s, cid, kind=kind, date=date, amount=amt)
            if not inv.get("ok"):
                warned.append({"row_no": row_no, "why": f"{label}发票额没落：{inv.get('message')}"})
            else:
                already.add(kind)

        # ⚠️ 落地后**从索引里摘掉**：同一份 Excel 里两行撞同一个锚点 ⇒ 后一行必须被判"已配对"，
        #    ⛔ 不然两行都会去写同一条合同（后写的把先写的**静默覆盖**）。
        by_amt[key] = [c for c in cands if int(c.id) != cid]
        updated.append({"id": cid, "row_no": row_no, "amount": key,
                        "matched_by": key_kind,          # `trade` = 靠贸易公司金额对上 / `amount` = 合同价
                        "contract_amt_filled": filled,   # 只在 `trade` 那支可能为 True（空才填）
                        "material_name": str(row.get("material_name") or cur.material_name or ""),
                        "fields": sorted(list(cols) + (["contract_amt"] if filled else []))})

    return {
        "updated": len(updated), "unmatched": len(unmatched),
        "ambiguous": len(ambiguous), "bad": len(bad), "warned": len(warned),
        "items": updated,
        "unmatched_items": unmatched,
        "ambiguous_items": ambiguous,
        "bad_items": bad,
        "warn_items": warned,
        # ⭐ 2026-09-27：「**本来就跳过**」（空白行 / 合计行）与"没配上 / 不合格"**分开报** ——
        #    ③ 据此给**灰标「不导入」**（守则 §2.8：要你处理的 vs 本来就跳过的，必须一眼分得开）。
        "skip_items": skip_rows,
        "skipped": len(skip_rows),
        # ⚠️ 措辞按"**这次到底动没动手**"分开（守则 §4「状态必须真实」）：
        #    干跑**一个字都没写库** ⇒ ⛔ 不许说"导入完成"（那是最典型的一类假话）。
        "message": ((f"（**只查不写**）按合同价能配上 {len(updated)} 条"
                     if dry_run else
                     f"导入完成：**按合同价匹配上并更新 {len(updated)} 条**")
                    + f" · 配不上 {len(unmatched)} 条 · 同价冲突 {len(ambiguous)} 条"
                    f" · 不合格 {len(bad)} 条 · 提醒 {len(warned)} 条"),
    }


def _add_contract(s, kwargs: dict) -> dict:
    """走 `service.act_add_contract`（**判定归一处**：三态默认「纳入台账」由它给）。"""
    from app.mod11_jc import service as SV

    return SV.act_add_contract(s, **kwargs)


def _add_invoice(s, contract_id: int, *, kind: str, date: str, amount) -> dict:
    """走 `service.act_add_invoice`（校验在 `domain.invoice_problem`，⛔ 本层不另判）。"""
    from app.mod11_jc import service as SV

    return SV.act_add_invoice(s, contract_id=contract_id, kind=kind, date=date, amount=amount)


__all__ = ["DOMAIN", "EXCEL_COLS", "SAMPLE_ROWS", "SAMPLE_SCAN", "SKIP_SHOW", "commit",
           "match_and_apply", "preview"]
