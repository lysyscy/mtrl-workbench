"""`MOD-06` 过程资料**历史导入**（§5.2.5 ①②）—— 解析 · 校验 · 预览 · 批次 · 核对报告。

> **为什么需要它**：本系统上线前各项目的过程资料**已在用户 Excel 里定稿**；且部分项目在 i8 里被改过、
> **与库存单据并不一致** ⇒ 只靠「从库存单据引用」（§5.2.3 单向流）搬不进历史账
> ⇒ 需要一条**历史进系统的通道**（与付款域的「历史付款流水导入」同构，§5.2.5 ②）。

## 列契约（**按表头文字认列 · 列序不限**）

| 列 | 含义 | 必填 |
|---|---|---|
| **核算月** | `2026-08`（也接受 `2026/8` · `2026.08` · `202608`；别名 `核算年月` / `月份` / **`时间`**） | ✅ |
| `domain.PROC_COLUMNS` 的 10 个材料列 | 入库 / 出库各 5 类（主辅材 · 工具 · 劳保 · 周转材料 · 临时设施） | **至少 1 列** |

- ⭐ **列名的唯一主人 = `domain.PROC_COLUMNS`** —— 本文件不另抄一份列名，只按 label 认列。
- ⚠️ **机械 6 列不导入**：机械列**全段手录**（旁路表 `proc_mech_manual`，见 `mech_ui.py`）
  ⇒ 文件里出现就**显式列出来给人看**（不静默忽略、也不顺手写进快照）。
- ⚠️ 认不出的列**列出来提示**（用户台账常带附注列）—— **不算错**；但**一列材料列都没有 ⇒ 报错**
  （那说明这文件不是过程资料，导进去只会污染历史段）。

## 三条硬纪律

1. **落库前必须预览**：预览阶段**一个字节都不写库**；
2. **异常行逐条列出**（行号 + 原因），**不静默丢弃**；
3. **改历史段 = 再导一次**（同批**整批回滚**后重导 / 另起新批次）—— 回滚只置状态、**不物理删**（§5.2.5 ②）。

⚠️ 本模块**只做 Excel 的解析与编排**：金额判定走 `core.money`，落库走 `repository.import_snapshot`，
  ⛔ 本层**不自己写库**、也**不碰正式段**（库存单据）与**机械手录**。

⭐ **2026-09-22（`TAIL-75` B3）：识别层收编到 `import_kit` 引擎**（落库与机械口径**一字未改**）。
   用户那三份真「材料机械消耗汇总表」逼出来的四件（实测见 `设计-识别样本-真实模板-20260922.md`）：

| 真文件现象 | 原来 | 现在 |
|---|---|---|
| **两级表头**（r2 分组头 ＋ r3 叶子：`线上入库（不含税）` › `主辅材`），且**父/子在项目间互换**（慧能把「含税/不含税」放 r2、把「外租设备（零租）」放 r3，与晋江/南平**正好相反**） | 只按**单行**精确匹配 label ⇒ **三份全拒**（"找不到表头"） | 两级**拼名**，且**两种顺序都试**（父+子 / 子+父） |
| 「**时间**」列 = 核算月，值是 **Excel 日期序列号**（`45444` ⇒ 2024-06） | `normalize_ym` 只认 `2026-08` 一类 ⇒ **认不出** | 序列号（20000~60000）按 1900 日期系统换算 ⇒ `YYYY-MM`；也认 `2025.09` 这种**浮点年月**与 `20250901` |
| 尾部有**合计/小计行** | 当数据行 ⇒ 报"核算月认不出"的**噪音异常** | 识别为**合计行**并跳过（记一条提示） |
| 一个工作簿可能有别的 sheet（慧能那张叫 `0.0`） | 只读**第一张** | 按"**哪张认得出表头**"挑（⛔ 不猜位置） |
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal

from app.core.errors import MustReportError
from app.core.money import MoneyError, to_money
from app.import_kit import mapping
from app.import_kit.mapping import Field
from app.mod06_proc import domain as D

MAX_ROWS = 2000
HEADER_SCAN_ROWS = 15          # 表头只在**前若干行**里找（用户台账常有标题行）

#: 「核算月」列的**别名**（真文件里那列叫「时间」—— 见 `识别样本` 文档）
YM_HEADERS: tuple[str, ...] = ("核算月", "核算年月", "月份", "时间")
YM_SUFFIXES: tuple[str, ...] = ("（元）", "(元)", "金额")     # 表头尾缀（"入库主辅材金额" ⇒ "入库主辅材"）
#: 只有 `auto` 档（≥0.90）才自动认列 ——「需确认」档留给界面（有人看着才敢用），口径同 `m04`（`B2`）
MIN_AUTO = 0.90
#: Excel 日期序列号区间（1900 日期系统）
_SERIAL_LO, _SERIAL_HI = 20000, 60000
#: 合计 / 小计行（不导入，也不当异常报）
_TOTAL_WORDS = ("合计", "小计", "总计")
#: 行首的「YYYY年M月」（真文件：`2025年9月（一标）` —— 标段行，用户裁定「数据没错」）
_YM_LOOSE = re.compile(r"^(\d{4})\s*年\s*(\d{1,2})\s*月")
#: 完整日期（`2024-06-01`）—— 真文件里「时间」列若是**日期单元格**，通用面会给 ISO 日期 ⇒ 取年月
_FULL_DATE = re.compile(r"^(\d{4})-(\d{1,2})-\d{1,2}$")


def _field(page: str, aliases: tuple[str, ...] = ()) -> Field:
    """造一条字段声明：`key` 取自 `domain.PROC_COLUMNS`（⛔ 别处不许再抄列名），别名 = 真模板里的写法。"""
    key = next(c["key"] for c in D.PROC_COLUMNS if c["label"] == page)
    return Field(key, page, aliases=aliases, type="amount")


def _mk_fields() -> tuple[Field, ...]:
    """⭐ **域声明**：13 个字段 ＋ 真模板各种写法的**别名**（两类来源，⛔ 不自己发明名字）：

    1. `PRD demo/模板/模板清单.md §5.3`（18 列「模板列（分组头 › 叶子）→ 页面列」的**登记表**）；
    2. 三份真文件实测到的**拼名两种顺序**（父+子 / 子+父，见本文件顶部表）。
    """
    mats: list[Field] = [Field("ym", "核算月", aliases=tuple(h for h in YM_HEADERS if h != "核算月"),
                               type="ym", required=True)]
    for page in ("入库主辅材", "入库工具", "入库劳保", "入库周转材料", "入库临时设施"):
        leaf = page[2:]
        mats.append(_field(page, aliases=(
            f"线上入库{leaf}", f"线上入库（不含税）{leaf}", f"线上入库不含税{leaf}",
            f"{leaf}线上入库", f"{leaf}线上入库（不含税）", f"{leaf}线上入库不含税",
        )))
    for page in ("出库主辅材", "出库工具", "出库劳保", "出库周转材料", "出库临时设施"):
        leaf = page[2:]
        mats.append(_field(page, aliases=(
            f"线下出库{leaf}", f"线下出库（不含税）{leaf}", f"线下出库不含税{leaf}",
            f"{leaf}线下出库", f"{leaf}线下出库（不含税）", f"{leaf}线下出库不含税",
        )))
    # 机械 6 列：**认出来只为提示「不导入」**（口径见模块头 ⚠️）
    mech = (
        ("租分公司设备", ("分公司设备", "租分公司设备")),
        ("内租设备", ("内部设备", "内租设备")),
        ("外租零租含税", ("外租机械（含税）零租", "零租外租机械（含税）", "含税外租设备（零租）",
                          "外租设备（零租）含税")),
        ("外租包月含税", ("外租机械（含税）包月", "包月外租机械（含税）", "含税外租设备（包月）",
                          "外租设备（包月）含税")),
        ("外租零租不含税", ("外租机械（不含税）零租", "零租外租机械（不含税）", "不含税外租设备（零租）",
                            "外租设备（零租）不含税")),
        ("外租包月不含税", ("外租机械（不含税）包月", "包月外租机械（不含税）", "不含税外租设备（包月）",
                            "外租设备（包月）不含税")),
    )
    for page, aliases in mech:
        mats.append(_field(page, aliases))
    return tuple(mats)


FIELDS: tuple[Field, ...] = _mk_fields()


def _norm(value) -> str:
    """表头 / 单元格文本归一：去空白（含全角）⇒ 去掉尾缀。"""
    text = "" if value is None else str(value)
    return text.replace("\u3000", "").replace(" ", "").strip()


def _norm_header(value) -> str:
    text = _norm(value)
    for suffix in YM_SUFFIXES:
        if text.endswith(suffix) and len(text) > len(suffix):
            text = text[: -len(suffix)]
    return text


def material_labels() -> dict[str, str]:
    """`{表头 label: 列 key}` —— **材料 10 列的正向映射**（唯一主人 = `domain.PROC_COLUMNS`）。"""
    return {col["label"]: col["key"] for col in D.PROC_COLUMNS if col["key"] in D.MATERIAL_KEYS}


def mech_labels() -> dict[str, str]:
    """`{表头 label: 列 key}` —— 机械 6 列（**认出来只为提示「不导入」**）。"""
    return {col["label"]: col["key"] for col in D.PROC_COLUMNS if col["key"] in D.MECH_KEYS}


# ------------------------------------------------------------------ 识别（引擎）
def _key_of(candidates: list[str]) -> tuple[str, float] | None:
    """一格的**候选写法**（单级 / 两级拼名两种顺序）→ `(字段key, 置信度)`；认不出 / 非 auto 档 ⇒ `None`。"""
    best: tuple[str, float] | None = None
    for text in candidates:
        if not _norm(text):
            continue
        got = mapping.guess([_norm_header(text)], FIELDS)[0]
        if got.field is None or got.level != "auto":
            continue
        key = next(f.key for f in FIELDS if f.label == got.field)
        if best is None or got.conf > best[1]:
            best = (key, got.conf)
    return best


def _recognize_cols(above: list, below: list | None = None) -> dict[int, str]:
    """两行表头（分组头 ＋ 叶子；`below=None` = 单行表头）→ `{列号: 字段key}`。

    ⭐ **同一列的两种拼名都要试**：`父+子` 与 `子+父` —— 真文件里父/子位置**在项目间互换**
      （慧能 = `含税` › `外租设备（零租）`；晋江/南平 = `外租机械（含税）` › `零租`）。
    """
    out: dict[int, str] = {}
    width = max(len(above or []), len(below or []))
    for col in range(width):
        up = _norm(above[col]) if above and col < len(above) else ""
        down = _norm(below[col]) if below and col < len(below) else ""
        if up and down and up != down:
            cands = [up + down, down + up]
        else:
            cands = [up or down]
        got = _key_of(cands)
        if got:
            out[col] = got[0]
    return out


def _recognize(above: list, below: list | None = None) -> dict[str, int]:
    """`{字段key: 列号}` —— 同一字段被多列认领时**只留第一列**（其余的交界面让人看）。"""
    out: dict[str, int] = {}
    for col, key in _recognize_cols(above, below).items():
        out.setdefault(key, col)
    return out


def _pick_header(grid: list[list]) -> tuple[int, int | None, dict[str, int]]:
    """找表头 ⇒ `(分组行下标, 叶子行下标 | None, 字段→列号)`。

    扫前 `HEADER_SCAN_ROWS` 行，**单行**与**两行**都试，取"认出字段最多"的那个；
    要认出「核算月」＋ 至少一列材料列才算数（⛔ 不猜位置、⛔ 不硬凑）。
    """
    best: tuple[int, int | None, dict[str, int]] | None = None
    for idx in range(min(len(grid), HEADER_SCAN_ROWS)):
        for below_idx in (None, idx + 1):
            below = grid[below_idx] if below_idx is not None and below_idx < len(grid) else None
            if below is not None and not any(_norm(c) for c in below):
                below = None
            found = _recognize(grid[idx], below)
            has_ym = "ym" in found
            mats = [k for k in found if k != "ym" and k in D.MATERIAL_KEYS]
            if has_ym and mats and (best is None or len(found) > len(best[2])):
                best = (idx, below_idx if below is not None else None, found)
    if best is None:
        mats_hint = " / ".join(list(material_labels())[:3])
        raise MustReportError(
            f"在文件的前 {HEADER_SCAN_ROWS} 行里找不到表头（应同时含「核算月」（模板里那列叫「时间」）与"
            f"至少一个材料列名，如「{mats_hint}」）—— 请核对表头后再导"
        )
    return best


def find_header(grid: list[list]) -> int:
    """定位**表头行**（返回分组行下标，0 基）—— 兼容旧调用；内部走 `_pick_header`。"""
    return _pick_header(grid)[0]


def map_columns(header: list, leaf: list | None = None) -> dict[str, int]:
    """表头（可带叶子行）→ `{列 key 或 `ym`: 下标}`。

    ⚠️ **只回 `ym` ＋ 材料 10 列** —— 机械 6 列**不进这个映射**（它们只用于「提示不导入」，
       见 `parse_sheet` 的 `ignored_mech`）。⛔ 别把机械列混进来：`parse_sheet` 是照它逐列取值的，
       混进来就会把机械金额**写进快照**（与「机械全段手录」的口径相冲 —— 自测抓到过）。
    """
    found = _recognize(header, leaf)
    if "ym" not in found:
        raise MustReportError(f"文件里没有「核算月」列（可写：{' / '.join(YM_HEADERS)}）")
    mats = {k: at for k, at in found.items() if k == "ym" or k in D.MATERIAL_KEYS}
    if not [k for k in mats if k != "ym"]:
        raise MustReportError(
            "文件里一列材料列都没认出来 —— 过程资料的列名见 §5.2.2（如「入库主辅材」「出库工具」）；"
            "这份文件看起来不是过程资料"
        )
    return mats


# ------------------------------------------------------------------ 核算月（含真文件那两种写法）
def _ym_from_number(value) -> str:
    """数字形态 → `YYYY-MM`：**Excel 序列号**（1900 日期系统）· `2025.09`（浮点年月）· `202509` · `20250901`。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return ""
    if _SERIAL_LO <= float(value) <= _SERIAL_HI:                 # 真文件（晋江/南平）就是这种
        day = datetime(1899, 12, 30) + timedelta(days=int(value))
        return f"{day.year}-{day.month:02d}"
    if float(value) >= 190001:                                   # 202509 / 20250901
        text = str(int(value))
        if len(text) == 6:
            return D.normalize_ym(text)
        if len(text) == 8:
            return D.normalize_ym(text[:4] + text[4:6] + "-" + text[6:])
        return ""
    if float(value) >= 1900 and float(value) < 2100:             # 2025.09（慧能那份）
        year = int(value)
        month = round((float(value) - year) * 100)               # 0.1 → 10（Excel 丢了末位 0）
        return f"{year}-{month:02d}" if 1 <= month <= 12 else ""
    return ""


def ym_of(value) -> str:
    """单元格 → 核算月（**认不出返回空串**，调用方据此报异常行）。

    ⭐ **公开出口**：通用导入面的域钩子也要用它（`imp_spec.commit`）—— ⛔ 别在钩子里另写一份。
    """
    if value is None or value == "":
        return ""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return _ym_from_number(value)
    text = _norm(value)
    if not text:
        return ""
    by_text = D.normalize_ym(text)
    if by_text:
        return by_text
    full = _FULL_DATE.match(text)                                 # `2024-06-01` ⇒ 2024-06
    if full:                                                      # （真文件里"时间"列可能是**日期单元格**
        return D.normalize_ym(f"{full.group(1)}-{full.group(2)}")  #   ⇒ 通用面已把它换成 ISO 日期）
    try:                                                          # 文本形态的序列号 / 浮点年月
        return _ym_from_number(float(text))
    except (TypeError, ValueError):
        return ""


def _is_total_row(row: list) -> bool:
    """合计 / 小计行（真文件尾部的 `合计数`、模板里的 `小计`）—— **不导入、不当异常**。"""
    return any(word in _norm(c) for c in row for word in _TOTAL_WORDS)


def _ym_loose(value) -> tuple[str, str]:
    """放宽解析：文本**以 `YYYY年M月` 开头** ⇒ `(核算月, 提示)`；认不出 ⇒ `("", "")`。

    ⭐ 真文件：「**2025年9月（一标）**」—— 用户 2026-09-22 裁定「**数据没错，是大设备**」
      ⇒ 认月、**值原样不动**（⛔ 不换算、⛔ 不因后缀就丢行）；同月多行由页面侧**相加**（`snapshot_by_month`）。
    ⛔ 只在**有材料金额**的行上走这条路（说明行先按"非数据行"跳过），且要求**从行首匹配** ——
      免得从一句说明里"抠"出个年月来。
    """
    text = _norm(str(value))
    m = _YM_LOOSE.match(text)
    if not m:
        return "", ""
    ym = D.normalize_ym(f"{m.group(1)}-{m.group(2)}")
    if not ym:
        return "", ""
    extra = text[m.end():].strip("（）()【】[] ")
    tail = f"（后缀「{extra}」）" if extra else ""
    return ym, f"原文「{text}」⇒ 按 {ym} 读{tail}"


def _has_amounts(row: list, index: dict[str, int]) -> bool:
    """该行**材料列**里有没有填东西（判定"是不是数据行"用；⛔ 不看机械列 —— 那不导入）。"""
    return any(_cell(row, at) for key, at in index.items() if key != "ym")


def _row_kind(row: list, index: dict[str, int]) -> str:
    """非数据行的类型（给提示用）：`合计/小计行` / `空行` / `说明行` / `""`（= 是数据行）。

    ⚠️ 判"空行 vs 说明行"看**文字本身**（真文件里说明就写在「时间」那一列：`6月总出库也多了53.54`）
      ⇒ ⛔ 不能按"除核算月列外还有没有字"判（那样说明行会被误判成空行 —— 自测踩过）。
    """
    if _is_total_row(row):
        return "合计/小计行"
    if _has_amounts(row, index):
        return ""
    for cell in row:
        text = _norm(cell)
        if len(text) > 4 and re.search(r"[\u4e00-\u9fff]", text):   # 成句的中文 ⇒ 说明行
            return "说明行"
    return "空行"


def _lines_note(kind: str, lines: list[int]) -> str:
    """把"跳过的行"攒成**一条**提示（⛔ 不一行一条 —— 南平那份有 10 行空行，刷屏）。"""
    where = "、".join(str(x) for x in lines) if len(lines) <= 4 else f"{lines[0]}~{lines[-1]}"
    return f"{kind} {len(lines)} 行（行 {where}）—— 不导入"


def _cell(row: list, at: int) -> str:
    return _norm(row[at]) if at < len(row) else ""


def _money_or_none(text: str, *, label: str, line: int):
    """单元格 → 金额。**空 ⇒ `None`（不写这一列）**；非数字 ⇒ `MustReportError`。

    ⭐ **允许负数**（2026-09-22 用户裁定 ①：「真文件里有红字/冲销 —— 收」）：过程资料的历史件是
      **定稿事实**（判据 `ACC-PROC-IMPORT-001/001-06`），⛔ 不由导入层替它改数。
      ⚠️ 对照：`core.money.require_non_negative` 那条「≥ 0」是给**付款通知书三金额 / 手动新增 /
      机械 6 列 / 大表手填 / 调整单**用的，**过程资料历史导入不在其列**（别顺手拉到一起）。
    """
    if not text:
        return None
    try:
        return to_money(text.replace(",", "").replace("，", ""))
    except (MoneyError, ArithmeticError, ValueError) as exc:
        raise MustReportError(f"第 {line} 行「{label}」不是数字：{text!r}") from exc


@dataclass
class ImportPlan:
    """**预览结果** —— 落库前给人看的全部东西。"""

    rows: list[dict] = field(default_factory=list)          # 将写入快照的行（只含非空列）
    anomalies: list[dict] = field(default_factory=list)     # 不入库的行（行号 + 原因）
    ignored_mech: list[str] = field(default_factory=list)   # 文件里出现、但不导入的机械列名
    unknown_headers: list[str] = field(default_factory=list)  # 认不出的列名（提示，不算错）
    header_row: int = 0                                     # 表头在 Excel 里的行号（1 基，报错好定位）
    header_levels: tuple[int, ...] = ()                      # 两级表头时 =（分组行, 叶子行）（1 基）
    sheet: str = ""                                         # 读的是哪张工作表（真文件里要说得清）
    notes: list[str] = field(default_factory=list)           # 只提示（如"尾部合计行已跳过"）

    @property
    def writable(self) -> int:
        return len(self.rows)

    @property
    def months(self) -> list[str]:
        return sorted({str(r.get("ym") or "") for r in self.rows if r.get("ym")})

    @property
    def default_cutoff(self) -> str:
        """**默认截止核算月 = 导入数据里最大的核算月**（§5.2.5 ①）。"""
        months = self.months
        return months[-1] if months else ""


def read_sheet(data: bytes) -> tuple[list[list], str]:
    """xlsx 字节 → `(网格, 工作表名)` —— **挑哪张认得出表头**（⛔ 不假设表名、不猜位置）。

    ⚠️ 读表收编 `import_kit.readers.read_grid`（`TAIL-69` Phase 2）；
       挑表与认列收编 `import_kit.mapping`（`TAIL-75` B3）。
    """
    from app.import_kit.readers import list_sheets, read_grid

    sheets = list_sheets(data)
    fallback: tuple[list[list], str] | None = None
    for name in sheets:
        try:
            grid, _ = read_grid(data, sheet=name, max_rows=MAX_ROWS,
                                fill_merged_rows=HEADER_SCAN_ROWS)   # ⭐ 只铺表头那几行（见 readers 注释）
        except MustReportError:
            continue                                  # 空表 / 读不了 ⇒ 跳过
        if fallback is None:
            fallback = (grid, name)
        for idx in range(min(len(grid), HEADER_SCAN_ROWS)):
            found = _recognize(grid[idx], grid[idx + 1] if idx + 1 < len(grid) else None)
            if "ym" in found and [k for k in found if k in D.MATERIAL_KEYS]:
                return grid, name
    if fallback is None:
        raise MustReportError("文件是空的（没有工作表内容）")
    return fallback                                   # 都不认得出 ⇒ 交回第一张，由 `parse_sheet` 报明白话


def parse_sheet(data: bytes) -> ImportPlan:
    """xlsx 字节 → `ImportPlan`（**纯函数：一个字节都不落库**）。"""
    grid, sheet = read_sheet(data)
    if not grid:
        raise MustReportError("文件是空的（没有工作表内容）")
    head, leaf, found = _pick_header(grid)
    index = map_columns(grid[head], grid[leaf] if leaf is not None else None)
    labels = {v: k for k, v in material_labels().items()}      # key → label（报错时写列名）

    plan = ImportPlan(header_row=head + 1, sheet=sheet,
                      header_levels=(head + 1, leaf + 1) if leaf is not None else ())
    plan.ignored_mech = [c["label"] for c in D.PROC_COLUMNS
                         if c["key"] in D.MECH_KEYS and c["key"] in found]
    # ⭐ 「认不出的列」= **整列都没认成任何字段**的那些（⛔ 不把两级表头的两半各报一条 —— 那是噪音：
    #    真文件里 13 条"认不出"，其中 12 条其实是已认出列的父级/叶子）
    cols = _recognize_cols(grid[head], grid[leaf] if leaf is not None else None)
    width = max(len(grid[head]), len(grid[leaf]) if leaf is not None else 0)
    unknown: list[str] = []
    for col in range(width):
        if col in cols:
            continue
        up = _norm_header(grid[head][col]) if col < len(grid[head]) else ""
        down = _norm_header(grid[leaf][col]) if leaf is not None and col < len(grid[leaf]) else ""
        if up or down:
            unknown.append(up or down)
    plan.unknown_headers = sorted(set(unknown))

    data_from = (leaf + 1) if leaf is not None else (head + 1)
    skipped: dict[str, list[int]] = {}
    row_notes: list[str] = []
    prev_total = False
    for offset, raw in enumerate(grid[data_from:], start=data_from + 1):
        if not any(_norm(c) for c in raw):
            continue                                    # 整行全空（连序号都没有）⇒ 跳过
        cell_ym = raw[index["ym"]] if index["ym"] < len(raw) else None
        ym = ym_of(cell_ym)
        # ⭐ **非数据行 ⇒ 跳过 ＋ 提示，⛔ 不当异常报**（2026-09-22 用户裁定 ③④：空行就是没数据、
        #    数据区下面的手写说明不是数据；合计行本来就该跳）
        kind = _row_kind(raw, index)
        if kind:
            skipped.setdefault(kind, []).append(offset)
            prev_total = kind == "合计/小计行"
            continue
        if not ym:
            if prev_total:                              # 合计块的下一行（合并格 `B18:B19` 那一类）
                skipped.setdefault("合计块（合计行的下半行）", []).append(offset)
                continue
            ym, why = _ym_loose(cell_ym)                # 「2025年9月（一标）」这类（用户裁定 ②）
            if not ym:
                plan.anomalies.append({"line": offset, "reason":
                                       f"核算月认不出：{_cell(raw, index['ym']) or '（空）'!r} —— "
                                       "写 2026-08 / 2025年9月 这种形态"})
                continue
            row_notes.append(f"第 {offset} 行：{why}")
        prev_total = False
        row: dict = {"ym": ym}
        bad = ""
        for key, at in index.items():
            if key == "ym":
                continue
            try:
                value = _money_or_none(_cell(raw, at), label=labels.get(key, key), line=offset)
            except MustReportError as exc:
                bad = exc.message
                break
            if value is not None:
                row[key] = value
        if bad:
            plan.anomalies.append({"line": offset, "ym": ym, "reason": bad})
            continue
        if len(row) == 1:                               # 有月份、一个材料金额都没有 ⇒ 空行（裁定 ④）
            skipped.setdefault("空行", []).append(offset)
            continue
        plan.rows.append(row)
    plan.notes = row_notes + [_lines_note(k, v) for k, v in skipped.items()] + plan.notes
    if not plan.rows:
        why = "；".join(f"行 {a['line']}：{a['reason']}" for a in plan.anomalies[:3]) or "文件里没有数据行"
        raise MustReportError(
            f"文件里没有一行可用的定稿数据（共 {len(plan.anomalies)} 行异常）—— {why}。"
            "历史段未被改动（不写库）"
        )
    return plan


def next_batch(*, at: datetime | None = None) -> str:
    """批次号 = `PROC-<yyyymmddHHMMSS>`（整批回滚按它，§5.2.5 ②）。"""
    return "PROC-" + (at or datetime.now()).strftime("%Y%m%d%H%M%S")


def commit(s, plan: ImportPlan, *, warehouse: str, batch: str, operator: str = "",
           cutoff_ym: str | None = None) -> dict:
    """**落库**（§5.2.5 ①）：写快照 ＋ 记批次 ＋ 设定该项目的**截止核算月**。

    ⭐ 只走 `repository.import_snapshot` ⇒ **只写历史段**：**不碰正式段（库存单据）、不碰机械手录**。
    """
    from app.mod06_proc import repository as repo

    batch_obj = repo.import_snapshot(
        s, warehouse=warehouse, rows=plan.rows, batch_no=batch,
        operator=operator, cutoff_ym=str(cutoff_ym or plan.default_cutoff or ""),
    )
    return {"batch": batch_obj.batch_no, "rows": batch_obj.row_count,
            "cutoff_ym": batch_obj.cutoff_ym, "months": plan.months}


def check_report(s, *, warehouse: str, batch_no: str, cutoff_ym: str) -> dict:
    """⭐ **核对报告**（与付款域同构的「漏记清单」）：本批月份 ＋ **会被显示成空态的月份**。

    「会被显示成空态的月份」= **截止核算月及以前**、**i8 库存单据里有数据**、而**本批快照里没有**的月份
    —— 历史段**不回落** i8（§5.2.5 ①），所以这些月一定印空 ⇒ 要么确实该空，要么**Excel 漏了**。
    """
    from app.mod06_proc import repository as repo

    snap_months = {str(r.get("ym") or "") for r in repo.load_history(s)
                   if str(r.get("warehouse") or "") == warehouse}
    inv_months = {str(r.get("ym") or "") for r in repo.load_inv_rows(s)
                  if str(r.get("warehouse") or "") == warehouse}
    empty_months = sorted(m for m in inv_months
                          if m and cutoff_ym and m <= str(cutoff_ym) and m not in snap_months)
    return {"batch": batch_no, "cutoff_ym": str(cutoff_ym),
            "months": sorted(m for m in snap_months if m),
            "count": len(empty_months), "rows": empty_months}


def rollback(s, *, batch_no: str) -> int:
    """整批回滚（= `repository.rollback_batch`：置 `rolled_back`、**不物理删**）。"""
    from app.mod06_proc import repository as repo

    return repo.rollback_batch(s, batch_no=batch_no)


__all__ = ["FIELDS", "MAX_ROWS", "HEADER_SCAN_ROWS", "YM_HEADERS", "YM_SUFFIXES", "ImportPlan",
           "material_labels", "mech_labels", "next_batch", "ym_of",
           "read_sheet", "find_header", "map_columns",
           "parse_sheet", "commit", "check_report", "rollback"]
