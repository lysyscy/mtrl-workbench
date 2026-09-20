"""集采台账 Excel **解析层**（`M5-8` · §6.8）—— 纯函数：字节 → 网格 → 表头 → 字段映射 → 行。

⭐ 2026-09-19 与用户定案的形式（**主路 = 直接上传他原来的台账**，⛔ 不是"下载模板再填"）：
   理由 —— ① 他**已经有数据**在 Excel 里（重填一遍 = 白干）；② 那份表是**历史习惯**
   （两行表头 / 贸易公司那条线 / 逐项目一份且列名可能不同）⇒ 让表迁就模板 = 让工作方式迁就软件。

⚠️⚠️ **本级最容易踩的三个坑**（都实测过）：
1. **合并单元格**：`供应商` 一格跨两列 ⇒ `.xls` 读出来**只有左上角有值、右边是空**
   ⇒ 必须**向右填充**，否则"供应商合同总价 / 供应商发票金额"这一支**整支丢掉**（而且不报错）。
2. **两级表头**：`供应商` ＋ `合同总价` = `供应商合同总价` ⇒ 必须**上下拼名**；
   否则单看第二行会出现**两个 `合同总价`**（供应商线 / 贸易公司线各一个）⇒ 后一个把前一个覆盖。
3. **第 1 张表可能是空的**（用户样例就是这样：第 1 张是空表、有效的是第 2 张「晋江污泥」）
   ⇒ ⛔ **绝不"取第 N 张"**，一律**摆出工作表让用户选**（系统只给个"像主台账"的提示）。

⚠️ 本模块**只解析、不落库**（落库在 `import_service`）——「判定归一处」。
"""

from __future__ import annotations

import io
import re
from decimal import Decimal, InvalidOperation

# ------------------------------------------------------------------ 读网格

#: `.xls` 与 `.xlsx` 两套引擎（用户手里两种都可能有）。⛔ 不引 pandas —— 只为读网格不值当。
XLS_SUFFIXES = (".xls",)
XLSX_SUFFIXES = (".xlsx", ".xlsm")


def suffix_of(filename: str) -> str:
    s = str(filename or "").lower()
    for suf in XLS_SUFFIXES + XLSX_SUFFIXES:
        if s.endswith(suf):
            return suf
    return ""


def sheet_names(data: bytes, filename: str) -> list[str]:
    """该文件里有哪些工作表（**顺序保持原样** —— 用户按自己看到的顺序找）。"""
    suf = suffix_of(filename)
    if suf in XLS_SUFFIXES:
        import xlrd

        book = xlrd.open_workbook(file_contents=data)
        return [book.sheet_by_index(i).name for i in range(book.nsheets)]
    if suf in XLSX_SUFFIXES:
        import openpyxl

        book = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        try:
            return list(book.sheetnames)
        finally:
            book.close()
    raise ValueError(f"不认识的文件类型：{filename!r}（只支持 .xls / .xlsx）")


def read_grid(data: bytes, filename: str, sheet: str) -> list[list[str]]:
    """读成**矩形网格**（行 × 列，值一律 `str`、两侧去空白；`None` ⇒ `''`）。

    ⚠️ **合并单元格**按**真实的合并区**展开（见 `_fill_merges`）—— ⛔ **不是无脑向右填充**：
       无脑右填会把表头行 `发票金额` 后面的**空列一路填满** ⇒ 表头行反而"命中最多"
       ⇒ `detect_header` 会认错行（2026-09-19 实测踩到，报"第 1 级 = 第 3 行"）。

    ⚠️ 日期单元格给 `YYYY-MM-DD`（`20240723` 那种 8 位数字是用户自己敲的**文本**，
       而真正的日期单元格会被引擎给成序列号）⇒ 见 `_cell_text` / `to_date`。
    """
    suf = suffix_of(filename)
    grid: list[list[str]] = []
    merges: list[tuple[int, int, int, int]] = []      # (r1, r2, c1, c2) 都按 **0 基、闭区间**
    if suf in XLS_SUFFIXES:
        import xlrd

        book = xlrd.open_workbook(file_contents=data)
        sh = book.sheet_by_name(sheet)
        for r in range(sh.nrows):
            grid.append([_cell_text(sh.cell(r, c), book.datemode) for c in range(sh.ncols)])
        merges = [(r1, r2 - 1, c1, c2 - 1) for r1, r2, c1, c2 in sh.merged_cells]   # xlrd 上界是**开的**
    elif suf in XLSX_SUFFIXES:
        import openpyxl

        book = openpyxl.load_workbook(io.BytesIO(data), data_only=True)
        try:
            sh = book[sheet]
            for row in sh.iter_rows(values_only=True):
                grid.append([("" if v is None else str(v).strip()) for v in row])
            merges = [(r.min_row - 1, r.max_row - 1, r.min_col - 1, r.max_col - 1)
                      for r in sh.merged_cells.ranges]                              # openpyxl 是 1 基、闭
        finally:
            book.close()
    else:
        raise ValueError(f"不认识的文件类型：{filename!r}（只支持 .xls / .xlsx）")
    return _fill_merges(grid, merges)


def _cell_text(cell, datemode: int) -> str:
    """单元格 → 文本。**日期型**给 `YYYY-MM-DD`（⛔ 不给 `45123.0` 那种序列号）。"""
    import xlrd

    if cell.ctype == xlrd.XL_CELL_DATE:
        y, m, d, *_ = xlrd.xldate_as_tuple(cell.value, datemode)
        return f"{y:04d}-{m:02d}-{d:02d}"
    if cell.ctype == xlrd.XL_CELL_NUMBER:
        v = cell.value
        return str(int(v)) if float(v).is_integer() else str(v)
    return str(cell.value or "").strip()


def _fill_merges(grid: list[list[str]], merges: list[tuple[int, int, int, int]]) -> list[list[str]]:
    """按**真实的合并区**把左上角的值铺满整个合并块。

    ⚠️ 为什么必须这么做：`供应商` 一格跨两列（`供应商合同总价` / `供应商发票金额`）⇒
       `.xls` 读出来**只有左上角有值、右边是空** ⇒ 不铺 ⇒ 那两列变成**无名列**
       ⇒ 整支丢掉（而且**不报错**，只是金额少了一半）。
    ⚠️ 为什么**不能**改成"无脑向右填充"：表头行的 `发票金额` 后面本来就是**合法空列**，
       右填会把它们全变成 `发票金额` ⇒ `detect_header` 认错行（实测踩到）。
       ⇒ **只信 `merged_cells`**（引擎给的合并信息），⛔ 不猜。
    """
    out = [[str(v or "").strip() for v in row] for row in grid]
    for r1, r2, c1, c2 in merges:
        if r1 >= len(out) or c1 >= len(out[r1]):
            continue
        val = out[r1][c1]
        if not val:
            continue
        for r in range(r1, min(r2, len(out) - 1) + 1):
            for c in range(c1, min(c2, len(out[r]) - 1) + 1):
                out[r][c] = val
    return out


# ------------------------------------------------------------------ 表头探测

#: 表头行里**几乎必然出现**的词（用于猜"哪一行是表头"）。
HEADER_HINTS = ("序号", "合同日期", "材料名称", "材料", "供应商", "合同总价", "发票金额", "合同金额")

#: 数据行的"像日期"判定：`20240723` / `2024-07-23` / `2024/7/23` / Excel 日期序列号已在上游转好。
_DATE_RE = re.compile(r"^\s*(\d{4})[-/.]?(\d{1,2})[-/.]?(\d{1,2})\s*$")


def detect_header(grid: list[list[str]], *, max_scan: int = 8) -> tuple[int, int]:
    """猜**两级表头**的行号 ⇒ `(第 1 级行, 第 2 级行)`。

    ⚠️ 用户那份表的形态：`r0` 是**大标题**（"…集中采购付款"）、`r1`/`r2` 才是表头
       ⇒ ⛔ 不能假定"第 1 行就是表头"。
    ⚠️ 判据 = 该行命中的 `HEADER_HINTS` **不同词的个数**（⛔ **不是**"命中的单元格个数"）——
       后者会被**重复列名**骗到：第二级表头里 `合同总价`/`发票金额` 各出现两次，
       再加合并格被铺满，很容易反超第一级（实测踩到）。
    ⚠️ 找不到 ⇒ 返回 `(0, 0)`（**第 1 行 + 无二级**）—— 由用户在上一步"改表头行"兜底，⛔ 不抛异常。
    """
    def score(row) -> int:
        return len({h for v in row for h in HEADER_HINTS if h in str(v)})

    best_i, best_n = 0, 0
    for i, row in enumerate(grid[:max_scan]):
        n = score(row)
        if n > best_n:
            best_i, best_n = i, n
    second = best_i
    if best_i + 1 < len(grid):
        nxt = score(grid[best_i + 1])
        # 下一行**也**有一点表头味（词数更少 ⇒ 是"下级"）⇒ 认成二级
        if 0 < nxt < best_n:
            second = best_i + 1
    return best_i, second


# ------------------------------------------------------------------ 列名 → 系统字段

#: 系统字段（`jc_contract` 主表 ＋ 两条子线的汇总列）。⚠️ 键名与 `service.act_add` 的字段名一致。
FIELD_LABELS: dict[str, str] = {
    "contract_date": "合同日期",
    "material_name": "材料名称",
    "supplier": "供应商",
    "trade_co": "贸易公司",
    "contract_amt": "供应商合同总价",
    "inv_sum": "供应商发票金额",
    "trade_contract_amt": "贸易公司合同总价",
    "trade_inv_sum": "贸易公司发票金额",
    "method": "付款方式",
    "remark": "备注",
    "arch": "存档",
    "arch_no": "存档序号",
    "ret_date": "寄回时间",
}

#: 列名**别名**（两级拼名之后的样子 → 系统字段）。⚠️ 只放"见了就认得"的，⛔ 不做模糊匹配。
#: 认不出的列一律**摆到预览里让用户点**（`map_columns` 的 `unknown`），⛔ 不猜、⛔ 不静默丢。
ALIASES: dict[str, str] = {
    "合同日期": "contract_date", "日期": "contract_date", "签订日期": "contract_date",
    "材料名称": "material_name", "材料": "material_name", "品名": "material_name",
    "供应商": "supplier", "供货商": "supplier",
    "贸易公司": "trade_co",
    "供应商合同总价": "contract_amt", "合同总价": "contract_amt", "合同金额": "contract_amt",
    "供应商发票金额": "inv_sum", "发票金额": "inv_sum",
    "贸易公司合同总价": "trade_contract_amt", "贸易合同总价": "trade_contract_amt",
    "贸易公司发票金额": "trade_inv_sum", "贸易发票金额": "trade_inv_sum",
    "付款方式": "method", "付款方式说明": "method",
    "备注": "remark",
    "存档": "arch", "存档情况": "arch",
    # ⚠️⚠️ 2026-09-20 补（**拿用户 10 份真台账跑出来的**）：乌兰察布储能 / 周口太康那两份用的
    #    就是「**存档编号**」—— 原先只认「存档序号 / 存档号」⇒ 认不出 ⇒ **整列落空、还不报错**
    #    （最坏的一类错）。⛔ 别用模糊匹配兜：认不出的列一律摆到预览里让人点（见模块头）。
    "存档序号": "arch_no", "存档号": "arch_no", "存档编号": "arch_no",
    "寄回时间": "ret_date", "寄回日期": "ret_date",
}

#: **不导入**的列（系统里是**派生**或不属于台账）—— 认出来是为了**说清楚"为什么没导"**，
#: ⛔ 不是为了"顺手也导进去"。「结算/付款/欠款」尤其：系统里欠款 = 结算 − 付款（**算出来、不落库**）。
IGNORED_LABELS: dict[str, str] = {
    "序号": "行号，系统自己编",
    "结算": "由子表算出来（不落库）",
    "付款": "由付款子表算出来（不落库）",
    "欠款": "由 结算 − 付款 算出来（不落库）",
    # ⚠️ 2026-09-20 补：**实测**用户表里出现过、但本系统**不录**的额外列（宜昌那份有 重量 / 开票号 /
    #    单价 / 不含税 / 含税）。放进「**明确忽略**」而不是「不认识」：后者会让预览页看着像"系统漏了"
    #    ⇒ 人得一个个点过去。⚠️ 它们本来也不是台账列，是用户顺手加的。
    "重量": "本系统不录（用户表的额外列）",
    "开票号": "本系统不录（用户表的额外列）",
    "单价": "本系统不录（用户表的额外列）",
    "不含税金额": "本系统只认含税（口径见 §9.1）",
    "含税金额": "本系统只认含税（口径见 §9.1）",
}


def _join(up: str, down: str) -> str:
    """两级表头**上下拼名**（`供应商` ＋ `合同总价` ⇒ `供应商合同总价`）。

    ⚠️ 只拼"都非空且**不相等**"的；`up == down` 时（两行写同一个词）只留一个。
    """
    a, b = str(up or "").strip(), str(down or "").strip()
    if not a:
        return b
    if not b or a == b:
        return a
    return a + b


def header_labels(grid: list[list[str]], *, row1: int, row2: int) -> list[str]:
    """表头两行 ⇒ **逐列的拼名**（供人核对："系统认成什么了"）。

    ⚠️ **重复拼名的修正**（实测踩到）：手作表的合并区常**画得不完整** —— 用户样例里第 1 级的
       `供应商` 只合并了 2 列（`供应商合同总价` 那一列在区内、它右边的 `发票金额` 却在区外）
       ⇒ 那一列的上级是**空** ⇒ 拼出来也叫 `发票金额`，与贸易公司线那列**撞名**
       ⇒ 若不修，映射就会把它当"重复列"丢掉（而它其实该是 `供应商发票金额`）。
    ⇒ 修法：**上级为空、且该拼名与别的列撞车**时，取**左侧最近的非空上级**重拼
       （这正是 Excel 里"合并格视觉上盖住左边"的含义）—— ⛔ 不是无脑左填（只对撞名的列动手）。
    """
    width = max((len(r) for r in grid[: max(row2, row1) + 1]), default=0)
    up = list(grid[row1]) + [""] * (width - len(grid[row1])) if row1 < len(grid) else [""] * width
    down = (list(grid[row2]) + [""] * (width - len(grid[row2]))) if row2 < len(grid) else [""] * width
    ups = [str(up[i] if i < len(up) else "").strip() for i in range(width)]
    downs = [str(down[i] if i < len(down) else "").strip() for i in range(width)]
    labels = [_join(ups[i], downs[i]) for i in range(width)]

    counts: dict[str, int] = {}
    for lb in labels:
        if lb:
            counts[lb] = counts.get(lb, 0) + 1
    for i in range(width):
        if ups[i] or not downs[i] or counts.get(labels[i], 0) < 2:
            continue                                   # 有上级 / 无名 / 不撞车 ⇒ 不动
        for j in range(i - 1, -1, -1):
            if ups[j]:
                labels[i] = _join(ups[j], downs[i])
                break
    return labels


def map_columns(labels: list[str], *, mapping: dict[str, str] | None = None) -> dict:
    """逐列拼名 ⇒ `{field: 列下标}`；并**如实报出**认不出的与明确忽略的。

    `mapping` = 用户在预览页**手点的修正**（`{"列下标": "字段名"}`，值 `""` = 忽略）
    ⇒ ⭐ 它**优先于**别名表（人改过的必须算数）。

    返回 `{"fields": {field: idx}, "unknown": [{col, label}], "ignored": [{col, label, why}], "dupes": [...]}`
    ⚠️ `dupes`：同一个系统字段被**两列**认到（如既有`合同金额`又有`合同总价`）⇒ 报出来让人定，
       ⛔ **不"后一个覆盖前一个"**（那是最典型的静默错：导进去的金额来自哪一列没人知道）。
    """
    override = {int(k): str(v or "") for k, v in (mapping or {}).items()}
    fields: dict[str, int] = {}
    unknown: list[dict] = []
    ignored: list[dict] = []
    dupes: list[dict] = []
    for i, label in enumerate(labels):
        if i in override:
            fld = override[i]
            if not fld:
                ignored.append({"col": i, "label": label, "why": "你选择了忽略"})
                continue
            if fld in fields:
                dupes.append({"col": i, "label": label, "field": fld, "kept": fields[fld]})
                continue
            fields[fld] = i
            continue
        if label in IGNORED_LABELS:
            ignored.append({"col": i, "label": label, "why": IGNORED_LABELS[label]})
            continue
        fld = ALIASES.get(label)
        if fld is None:
            if label:
                unknown.append({"col": i, "label": label})
            continue
        if fld in fields:
            dupes.append({"col": i, "label": label, "field": fld, "kept": fields[fld]})
            continue
        fields[fld] = i
    return {"fields": fields, "unknown": unknown, "ignored": ignored, "dupes": dupes}


# ------------------------------------------------------------------ 值解析

_MONEY_CLEAN = re.compile(r"[,\s¥￥元]")


def to_money(v) -> Decimal | None:
    """金额文本 ⇒ `Decimal`；**空 ⇒ `None`**（≠ 0 —— "没填"和"填了 0"是两回事）。

    ⚠️ 认不出 ⇒ `None`（由调用方**列出来让人看**），⛔ 不静默当 0。
    """
    if v is None:
        return None
    s = _MONEY_CLEAN.sub("", str(v))
    if s == "":
        return None
    try:
        return Decimal(s).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


def to_date(v) -> str:
    """日期文本 ⇒ `YYYY-MM-DD`；认不出 ⇒ 原样返回（**不猜**）。

    ⚠️ 用户台账里的写法是 `20240723`（8 位数字，**文本**）—— 这是**必须**支持的一种。
    """
    s = str(v or "").strip()
    if not s:
        return ""
    m = _DATE_RE.match(s)
    if not m:
        return s
    y, mo, d = m.group(1), int(m.group(2)), int(m.group(3))
    return f"{y}-{mo:02d}-{d:02d}"


#: 明显的**非数据行**字样（合计行）—— 它们**也有金额**，光靠"有金额"挡不住。
NON_DATA_WORDS = ("合计", "小计", "总计", "合 计")


def looks_like_data_row(row: list[str], fields: dict[str, int]) -> bool:
    """该行是否**像数据行**（用于跳过标题 / 合计 / 空行）。

    ⚠️ 判据分三层，**每层都能自证**（⛔ 不靠"猜第几行是数据"）：
       ① 有**合同日期**或**材料名**；
       ② 有**任一金额**；
       ③ 若日期列**有值** ⇒ 它必须**像个日期** —— 合计行的 `"合计："` 就死在这一条上
          （实测：不挡它，那行 110,030,834.08 会被当成一条合同，**合计凭空翻倍**）。
    """
    def has(f: str) -> str:
        i = fields.get(f)
        return str(row[i]).strip() if (i is not None and i < len(row)) else ""

    if any(w in " ".join(str(v) for v in row) for w in NON_DATA_WORDS):
        return False
    if not (has("contract_date") or has("material_name")):
        return False
    dt = has("contract_date")
    if dt and not _DATE_RE.match(dt):
        return False
    return any(has(f) for f in ("contract_amt", "inv_sum", "trade_contract_amt", "trade_inv_sum"))


def parse_rows(grid: list[list[str]], *, row2: int, fields: dict[str, int]) -> dict:
    """数据区 ⇒ `{"rows": [...], "skipped": [{"row_no", "why"}]}`。

    ⚠️ **空行 / 不像数据的行会跳过 —— 但一律如实记账回传**（⛔ **禁静默**）：
       否则"表里有 82 行、系统说新增 72 条"，没人知道那 10 行去哪了。
       ⚠️ 尤其**合计行**：它**也有金额**，一旦混进去就会让合计**凭空翻倍**。
    """
    rows: list[dict] = []
    skipped: list[dict] = []
    for n, row in enumerate(grid[row2 + 1:], start=row2 + 2):        # `row_no` 按**人看的行号**（1 基）
        if not any(str(v).strip() for v in row):
            continue                                                 # 纯空行不记账（不是"丢数据"）
        if not looks_like_data_row(row, fields):
            skipped.append({"row_no": n, "why": _skip_reason(row, fields)})
            continue
        item: dict = {}
        for fld, idx in fields.items():
            val = row[idx] if idx < len(row) else ""
            item[fld] = to_money(val) if fld.endswith(("_amt", "_sum")) else (
                to_date(val) if fld in ("contract_date", "ret_date") else str(val or "").strip())
        rows.append(item)
    return {"rows": rows, "skipped": skipped}


def _skip_reason(row: list[str], fields: dict[str, int]) -> str:
    """为什么这行不算数据（**给人看的一句话**，⛔ 不写代码术语）。"""
    if any(w in " ".join(str(v) for v in row) for w in NON_DATA_WORDS):
        return "看着是合计 / 小结行（不是一条合同）"
    def has(f: str) -> str:
        i = fields.get(f)
        return str(row[i]).strip() if (i is not None and i < len(row)) else ""
    if not (has("contract_date") or has("material_name")):
        return "既没有合同日期、也没有材料名称"
    dt = has("contract_date")
    if dt and not _DATE_RE.match(dt):
        return f"合同日期「{dt}」不像日期"
    return "四个金额列全空"


__all__ = [
    "ALIASES", "FIELD_LABELS", "IGNORED_LABELS", "HEADER_HINTS",
    "detect_header", "header_labels", "looks_like_data_row", "map_columns",
    "parse_rows", "read_grid", "sheet_names", "suffix_of", "to_date", "to_money",
]
