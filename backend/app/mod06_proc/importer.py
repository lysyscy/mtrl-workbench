"""MOD-06 材料、机械导入的解析、预览及提交编排。
双截止仅筛选本次输入；先排除未选类别，再校验金额；同月标段行聚合。
真实写入唯一出口 repository.import_snapshot；i8 原单不改。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal

from app.core.errors import MustReportError, human_reason
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
    # 机械 6 列：**要导入**（⭐ 2026-09-26 用户裁定 —— 历史机械费在 excel 里；别名照真模板）
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
    """`{表头 label: 列 key}` —— 机械 6 列（⭐ 2026-09-26 起**也要落库**，见模块头）。"""
    return {col["label"]: col["key"] for col in D.PROC_COLUMNS if col["key"] in D.MECH_KEYS}


def value_labels() -> dict[str, str]:
    """`{列 key: 表头 label}` —— **材料 ＋ 机械**（报错时写"哪一列"用；⛔ 别只盖材料那半）。"""
    return {col["key"]: col["label"] for col in D.PROC_COLUMNS
            if col["key"] in D.MATERIAL_KEYS or col["key"] in D.MECH_KEYS}


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
    """表头（可带叶子行）→ `{列 key 或 `ym`: 下标}` —— 回 `ym` ＋ 材料 10 列 ＋ **机械 6 列**。

    ⭐ 2026-09-26（`TAIL-107`）：**机械 6 列进这个映射**（要落库）。⚠️ 改前这里**故意把它们滤掉**
      （旧口径"机械全段手录、导入只提示不落库"）—— 那条口径已作废，⛔ 别把 filter 加回来。
    ⚠️ 「一列都没认出来」的判据：**材料列与机械列都算**（只填机械列的表也是过程资料）。
    """
    found = _recognize(header, leaf)
    if "ym" not in found:
        raise MustReportError(f"文件里没有「核算月」列（可写：{' · '.join(YM_HEADERS)}）")
    vals = {k: at for k, at in found.items()
            if k == "ym" or k in D.MATERIAL_KEYS or k in D.MECH_KEYS}
    if not [k for k in vals if k != "ym"]:
        raise MustReportError(
            "文件里一列材料列 / 机械列都没认出来 —— 过程资料的列名见 §5.2.2（如「入库主辅材」"
            "「外租机械（含税）零租」）；这份文件看起来不是过程资料"
        )
    return vals


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
    """识别从行首开始的 YYYY年M月 标段月份；先认标准格式再尝试此补充，不从说明中猜月。"""
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
    """该行**材料列 / 机械列**里有没有填东西（判定"是不是数据行"用）。

    ⭐ 2026-09-26（`TAIL-107`）：**机械列也算** —— "只填了机械列"的行从此**是数据行**
      （改前它被判成"空行"丢掉，而机械费正是用户要导的东西）。判据只认 `index`（= `map_columns` 的出口）
      ⇒ 加列不必改这里（⛔ 别在这里硬写列名）。
    """
    return any(_cell(row, at) for key, at in index.items() if key != "ym")


def _row_kind(row: list, index: dict[str, int]) -> str:
    """非数据行的类型（给提示用）：`合计/小计行` / `空行` / `说明行` / `""`（= 是数据行）。

    ⚠️ 判"空行 vs 说明行"看**文字本身**（真文件里说明就写在「时间」那一列：`6月总出库也多了53.54`）
      ⇒ ⛔ 不能按"除核算月列外还有没有字"判（那样说明行会被误判成空行 —— 自测踩过）。
    ⚠️ **网格形态的薄壳**：判法本体在 `_row_kind_of`（通用导入面的记录形态走的是同一个本体 ——
       ⛔ 别在这里另写一套，否则同一个域就有了两份"什么算数据行"）。
    """
    return _row_kind_of(cells=[_norm(c) for c in row], has_amounts=_has_amounts(row, index))


def _row_kind_of(*, cells: list[str], has_amounts: bool) -> str:
    """**判"是不是数据行"的本体**（网格与记录两种形态共用）：`合计/小计行` / `空行` / `说明行` / `""`。"""
    if _is_total_row(cells):
        return "合计/小计行"
    if has_amounts:
        return ""
    for text in cells:
        if len(text) > 4 and re.search(r"[\u4e00-\u9fff]", text):   # 成句的中文 ⇒ 说明行
            return "说明行"
    return "空行"


def _lines_note(kind: str, lines: list[int]) -> str:
    """把"跳过的行"攒成**一条**提示（⛔ 不一行一条 —— 南平那份有 10 行空行，刷屏）。

    ⚠️ 只服务**域内旧路** `parse_sheet`（页面已下架）。⭐ 通用导入面（现行唯一入口）不再用它 ——
      那里给的是**逐行**清单（`[{row, kind, why}]`），因为用户 2026-09-27 要求"**所有不写入的行
      都要在行上标出来**"，而一句"合计/小计行 2 行（行 33、34）—— 不导入"在表里**对不上行**。
    """
    where = "、".join(str(x) for x in lines) if len(lines) <= 4 else f"{lines[0]}~{lines[-1]}"
    return f"{kind} {len(lines)} 行（行 {where}）—— 不导入"


def _skip_why(kind: str) -> str:
    """「本来就跳过」的那几行**逐行**说一句人话（通用面把它挂成那一行的悬停说明）。

    ⚠️ 措辞要点（守则 §2.8）：**必须说清"不用你管"** —— 否则用户看到"没写进去"，
      第一反应是自己的文件有问题（而合计行/说明行/空行**本来就该跳**）。
    """
    if "合计" in kind or "小计" in kind:
        return "尾部合计/小计行 —— 不是数据行，**本来就跳过**（不用你改）"
    if "说明" in kind:
        return "手写说明行 —— 不是数据行，**本来就跳过**（不用你改）"
    if "空" in kind:
        return "空行 —— **本来就跳过**（不用你改）"
    if kind.startswith("截止核算月"):
        return f"{kind} —— **不导入**；若需导入该月，请返回修改截止核算月"
    return f"{kind} —— **本来就跳过**（不是数据行，不用你改）"


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


# ---------------------------------------------------------------- 记录 → 能落库的行（**预览与落库共用这一处**）
def _record_cells(rec: dict) -> list[str]:
    """一条**通用面的记录** → "像一行的文本序列"（供给 `_row_kind_of` 判"是不是数据行"）。

    ⚠️ 通用面给的是**按列名映射后**的记录（键 = 界面字段名），而旧路 `parse_sheet` 拿到的是**原始网格行**
      ⇒ 为了让"什么算数据行"**只有一个主人**，这里把记录摊成"一行文本"，再走同一个 `_row_kind_of`。
      ⛔ 别在这里另写一套判法（同一个域两份口径 = 往后必然说不一样）。
    """
    vals = [str(rec.get(f.label) or "") for f in FIELDS]
    vals += [str(v or "") for v in (rec.get("raw") or {}).values()]
    return [_norm(v) for v in vals]


def plan_rows(records, *, cutoff_ym: str | None = None, material_cutoff_ym: str | None = None, mechanical_cutoff_ym: str | None = None) -> tuple[list[dict], list[dict], list[dict]]:
    """通用预览与提交共用：非数据行跳过，两类分别过滤截止月后再验金额；任一异常由调用方整批拒写。"""
    cutoff = normalized_cutoff(material_cutoff_ym if material_cutoff_ym is not None else cutoff_ym)
    mech_cutoff = normalized_cutoff(mechanical_cutoff_ym if mechanical_cutoff_ym is not None else cutoff_ym)
    key_of = {f.label: f.key for f in FIELDS}
    # ⚠️ "有没有金额"= **材料列 ＋ 机械列**（⭐ `TAIL-107`：只填机械列的行也算数据行）——
    #    ⛔ 别只挑材料列：那样"只填了机械费的那些月"会被当空行丢掉（而那正是用户要导的东西）。
    amount_labels = [f.label for f in FIELDS
                     if f.key in D.MATERIAL_KEYS or f.key in D.MECH_KEYS]
    rows: list[dict] = []
    skipped: dict[str, list[int]] = {}
    bad: list[dict] = []
    for rec in records or []:
        line = int(rec.get("_row") or 0)
        kind = _row_kind_of(cells=_record_cells(rec),
                            has_amounts=any(rec.get(lb) not in (None, "") for lb in amount_labels))
        if kind:
            skipped.setdefault(kind, []).append(line)
            continue
        ym = ym_of(rec.get("核算月")) or _ym_loose(rec.get("核算月"))[0]
        if not ym:
            bad.append({"line": line, "reason":
                        f"核算月认不出：{str(rec.get('核算月') or '（空）')!r} —— 写 2026-08 / 2025年9月 "
                        "这种形态（⛔ 这一行**不导入**：请改成标准格式后重导）"})
            continue
        row: dict = {"ym": ym}
        try:
            for label, key in key_of.items():
                if key == "ym":
                    continue
                limit = mech_cutoff if key in D.MECH_KEYS else cutoff
                if limit and ym > limit:
                    continue
                val = rec.get(label)
                if val in (None, ""):
                    continue
                row[key] = to_money(str(val))
        except ArithmeticError as exc:          # ⭐ 外来（如 DivisionByZero）⇒ 原文不上屏，进日志
            bad.append({"line": line, "reason": human_reason(
                "金额认不出", exc, next_step="请把这一格改成数字（或先清空）")})
            continue
        except (MoneyError, ValueError) as exc:   # 我们自己的（`MoneyError` / `to_money` 的 `ValueError`）⇒ message 本就是人话
            bad.append({"line": line, "reason": f"金额认不出：{exc}"})
            continue
        if len(row) == 1:
            skipped.setdefault(f"材料截止月 {cutoff or '不限'}、机械截止月 {mech_cutoff or '不限'}筛选后无金额（{ym}）", []).append(line)
            continue
        rows.append(row)
    # ⭐ 逐行清单（不是一句汇总）：通用面要按 `row` 把这几行**在行上**标出来（守则 §2.7/§2.8）。
    skip_rows = [{"row": line, "kind": k, "why": _skip_why(k)}
                 for k, lines in skipped.items() for line in lines]
    return rows, skip_rows, bad


def normalized_cutoff(value) -> str:
    """预览与落库共用截止月校验；留空由可写行最大月推断。"""
    text = str(value or "").strip()
    if not text:
        return ""
    norm = D.normalize_ym(text)
    if not norm:
        raise MustReportError(f"截止核算月认不出：{text!r} —— 请写 YYYY-MM（如 2025-11）；留空取本批最大核算月")
    return norm


def selected_cutoffs(rows, *, cutoff_ym=None, material_cutoff_ym=None, mechanical_cutoff_ym=None):
    """空截止分别取该类有效输入的最大月；旧单截止同时限制两类。"""
    def maximum(keys):
        return max((row["ym"] for row in rows if any(row.get(k) not in (None, "") for k in keys)), default="")
    return {
        "material_cutoff_ym": normalized_cutoff(material_cutoff_ym if material_cutoff_ym is not None else cutoff_ym) or maximum(D.MATERIAL_KEYS),
        "mechanical_cutoff_ym": normalized_cutoff(mechanical_cutoff_ym if mechanical_cutoff_ym is not None else cutoff_ym) or maximum(D.MECH_KEYS),
    }


@dataclass
class ImportPlan:
    """**预览结果** —— 落库前给人看的全部东西。"""

    rows: list[dict] = field(default_factory=list)          # 将写入快照的行（只含非空列）
    anomalies: list[dict] = field(default_factory=list)     # 不入库的行（行号 + 原因）
    # ⛔ `ignored_mech` 字段已删（2026-09-26 · `TAIL-107`）：机械 6 列**从此要导入**
    #    ⇒ "文件里出现、但不导入的机械列"这个概念不存在了（那条旧口径已作废）。
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
    labels = value_labels()                                    # key → label（报错时写列名，含机械列）

    plan = ImportPlan(header_row=head + 1, sheet=sheet,
                      header_levels=(head + 1, leaf + 1) if leaf is not None else ())
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
            "历史段未被改动（没有写入）"
        )
    return plan


def next_batch(*, at: datetime | None = None) -> str:
    """批次号 = `PROC-<yyyymmddHHMMSS>`（整批回滚按它，§5.2.5 ②）。"""
    return "PROC-" + (at or datetime.now()).strftime("%Y%m%d%H%M%S")


def commit(s, plan: ImportPlan, *, warehouse: str, batch: str, operator: str = "",
           cutoff_ym: str | None = None, material_cutoff_ym: str | None = None,
           mechanical_cutoff_ym: str | None = None) -> dict:
    """通过 repository.import_snapshot 写材料快照及统一有效机械，保留两类截止及批次溯源。"""
    from app.mod06_proc import repository as repo

    batch_obj = repo.import_snapshot(
        s, warehouse=warehouse, rows=plan.rows, batch_no=batch,
        operator=operator, cutoff_ym=cutoff_ym, material_cutoff_ym=material_cutoff_ym,
        mechanical_cutoff_ym=mechanical_cutoff_ym,
    )
    return {"batch": batch_obj.batch_no, "rows": batch_obj.row_count,
            "cutoff_ym": batch_obj.cutoff_ym, "material_cutoff_ym": batch_obj.cutoff_ym,
            "mechanical_cutoff_ym": batch_obj.mechanical_cutoff_ym, "months": plan.months}


def check_report(s, *, warehouse: str, batch_no: str, cutoff_ym: str) -> dict:
    """兼容核对报告：列出截止内有 i8、无导入快照的月份；金额显示仍整月优先 i8，不因缺快照而变空。"""
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
           "material_labels", "mech_labels", "value_labels", "next_batch", "ym_of", "plan_rows",
           "read_sheet", "find_header", "map_columns",
           "parse_sheet", "commit", "check_report", "rollback"]
