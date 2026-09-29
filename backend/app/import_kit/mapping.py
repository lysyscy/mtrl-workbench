"""`import_kit.mapping` —— **表头映射引擎**（`TAIL-75` B1 · 设计 = `10-designs/设计-统一导入模块-20260922.md §六`）。

四步：`normalize`（归一化比较键）→ `profile`（内容画像）→ `guess`（四级命中出**建议**）→ `apply`（按映射取行）。

三条硬性（⛔ 实施各域时不得违背）：
1. **永不静默猜** —— 认不出就留空交界面让人选；`guess()` **只出建议**（带置信度与依据），不出决定。
2. **三档**：`≥0.90` 自动（仍可改）· `0.70~0.90` 预选但标「需确认」· `<0.70` **留空**。
3. ⚠️ 归一化**只用于比较**：出参与报错一律用**原文**（用户要看得到"系统按什么认的"）。

真文件校准（2026-09-22 · 见 `设计-识别样本-真实模板-20260922.md`）落在这里的几条：
- **两级表头拼名**要能出「父+子」「子+父」两种（慧能那份的父/子与另两份**互换**）；
- **括号里的单位才剥**（`金额（元）` → `金额`）—— ⛔ 「线上入库（不含税）」的括号是**语义**，剥了就与「含税」撞车；
- **Excel 序列号**（`45444`）与 `20250901` / `2026.7.15` / `9月11号` 同样是"日期味"；
- **同一字段被多列认领**（台账里「供应商」出现两次）⇒ 记进 `dupes`，由界面/域内裁。
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

#: 只剥**单位类**括号内容（语义括号如「不含税」不动）
_UNIT_WORDS = frozenset({
    "元", "万元", "千元", "亿元", "rmb", "人民币", "万元整", "个", "天", "月", "次", "笔",
})
#: 通用后缀词：**次要**比较键（`材料名称` ≈ `材料`）；⛔ 不作主键（`供应商` 与 `贸易公司` 必须区分开）
_GENERIC_SUFFIXES = ("编号", "名称", "金额", "合计", "小计", "汇总", "明细", "时间", "日期", "序号")

_CONF_AUTO = 0.90
_CONF_CONFIRM = 0.70
#: 类型画像**不符**时的降权（设计 §六为 −0.20）
_TYPE_PENALTY = 0.20

_WS = re.compile(r"[\s\u3000]+")
_PAREN = re.compile(r"[（(]([^（()）]*)[)）]")
_NUM = re.compile(r"^-?\d+(\.\d+)?$")
_CODE = re.compile(r"^[A-Za-z]{1,6}[-_]?\d{4,}$")
_YMD_TEXT = re.compile(r"^\d{4}\s*[-/.年]\s*\d{1,2}(\s*[-/.月]\s*\d{1,2}\s*日?)?$")
_YYYYMM = re.compile(r"^\d{6}$")
_YMD_NUM = re.compile(r"^\d{8}$")
_CN_MD = re.compile(r"^\d{1,2}\s*月\s*\d{1,2}\s*[日号]$")


def normalize(raw) -> str:
    """表头/列名 → **比较键**：去空白、全半角统一、大小写折叠；剥**单位类**括号与标点。

    ⚠️ 语义括号（如「（不含税）」）必须保留 —— 否则「线上入库（不含税）」与「线上入库（含税）」会撞成同一个键。
    """
    s = "" if raw is None else str(raw)
    s = unicodedata.normalize("NFKC", s)
    s = _PAREN.sub(lambda m: "" if m.group(1).strip().lower() in _UNIT_WORDS else m.group(0), s)
    s = _WS.sub("", s)
    return s.strip(":：* ").lower()


def secondary(raw) -> str:
    """**次要**比较键：在 `normalize` 之上再剥通用后缀词（`材料名称` → `材料`）。"""
    s = normalize(raw)
    for suf in sorted(_GENERIC_SUFFIXES, key=len, reverse=True):
        if s.endswith(suf) and len(s) > len(suf):
            return s[: -len(suf)]
    return s


def join_levels(parent: str, child: str) -> tuple[str, str]:
    """两级表头的**两种拼名**：`(父+子, 子+父)`。

    ⭐ 真文件逼出来的：慧能那份把「含税/不含税」放上级、把「外租设备（零租）」放下级，
    与晋江/南平的写法**正好互换** ⇒ 两种都要试（`guess` 里对同一列都试，取分高者）。
    """
    p, c = normalize(parent), normalize(child)
    if not p:
        return c, c
    if not c:
        return p, p
    return p + c, c + p


def _to_decimal(raw) -> Decimal | None:
    s = "" if raw is None else str(raw).replace(",", "").replace("，", "").replace(" ", "").strip()
    if not s or not re.search(r"\d", s):
        return None
    try:
        return Decimal(s)
    except (InvalidOperation, ArithmeticError, ValueError):
        return None


def _is_yyyymm(s: str) -> bool:
    """`202508` 且月份合法（01~12）—— ⛔ 不加月份校验的话，`400000` 也会被当成年月。"""
    return len(s) == 6 and s.isdigit() and 1 <= int(s[4:]) <= 12


def serial_hint(values) -> bool:
    """值像不像 **Excel 日期序列号**（全为整数且落在 20000~60000）—— 供域结合列名裁（如 `m06` 的「时间」）。

    ⚠️ 返回 True **只说明"有可能是日期"**（`45444` 也可能是金额 45444 元）⇒ ⛔ 本函数不替域下结论。
    """
    vals = [("" if v is None else str(v).strip()) for v in values]
    vals = [v for v in vals if v]
    if not vals:
        return False
    hits = sum(1 for v in vals if _NUM.match(v) and 20000 <= float(v) <= 60000)
    return hits / len(vals) >= 0.8


def profile(values) -> str:
    """内容画像（用**值**说话）：`空列 / 金额 / 日期 / 年月 / 编号 / 数字 / 枚举 / 文本`。

    ⚠️ 两条**克制**（真文件逼出来的，别改）：
    1. **纯整数不判「金额」** —— `45444` 既可能是金额也可能是 Excel 序列号 ⇒ 归 `数字`（模糊档，
       交叉验证时**一律不降权**）；要判序列号请用 `serial_hint()`，由**域**结合列名裁。
    2. `#REF!` 这类公式残值 ⇒ `文本`（⛔ 不当数字 —— 它会进问题清单，让人看见）。
    """
    vals = [("" if v is None else str(v).strip()) for v in values]
    vals = [v for v in vals if v]
    if not vals:
        return "空列"
    n = len(vals)
    dec = sum(1 for v in vals if _to_decimal(v) is not None)
    money_fmt = sum(1 for v in vals if ("." in v or "," in v or "，" in v) and _to_decimal(v) is not None)
    hit_int = sum(1 for v in vals if _NUM.match(v.replace(",", "").replace("，", "")))
    hit_ymd = sum(1 for v in vals if _YMD_TEXT.match(v))
    hit_ymd_num = sum(1 for v in vals if _YMD_NUM.match(v))
    hit_ym = sum(1 for v in vals if _is_yyyymm(v) or _CN_MD.match(v))
    hit_code = sum(1 for v in vals if _CODE.match(v))

    if (hit_ymd + hit_ymd_num) / n >= 0.8:
        return "日期"
    if hit_ym / n >= 0.8:
        return "年月"
    if dec / n >= 0.8:
        return "金额" if money_fmt / n >= 0.2 else "数字"     # 有小数点/千分位才算金额
    if hit_code / n >= 0.8:
        return "编号"
    if hit_int / n >= 0.8:
        return "数字"
    if n >= 2 and len(set(vals)) <= max(2, min(8, n // 3)):
        return "枚举"                 # ⚠️ `n>=2`：只有一个非空值的列不叫枚举（如整列 `#REF!`）
    return "文本"


#: 画像 → 该画像下**可接受**的字段类型（用于交叉验证；⛔ 只用来"降权"，不用来"改判"）
#: ⚠️ 三个**模糊/弱证据**档（`数字` 值有歧义 · `枚举` 只是"值少"未必是枚举列 · `文本` 没信息量）
#:    一律**接受所有类型** ⇒ 不降权。⛔ 只有"画像与类型**互相矛盾**"（金额列装着日期等）才降权。
_ALL_TYPES = frozenset({"amount", "number", "date", "ym", "code", "enum", "text"})
_TYPE_OK: dict[str, frozenset[str]] = {
    "金额": frozenset({"amount", "number", "text"}),
    "数字": _ALL_TYPES,
    "日期": frozenset({"date", "ym", "text"}),
    "年月": frozenset({"ym", "date", "text"}),
    "编号": frozenset({"code", "text", "number"}),
    # ⚠️ `枚举` 算**强证据**：数值列到不了这一档（`金额`/`数字` 先返回）⇒ 它出现 = 这列真的是几个重复文本
    #    （`电汇`/`已审批`）⇒ 若字段类型是 date/amount 那就是**真矛盾**（如"付款时间"列装着"电汇"）。
    "枚举": frozenset({"enum", "text", "code"}),
    "文本": _ALL_TYPES,
}


@dataclass(frozen=True)
class Field:
    """**域声明**里的一个目标字段（各域自己给；⛔ 底座不写死任何业务字段）。"""

    key: str
    label: str
    aliases: tuple[str, ...] = ()
    type: str = "text"
    required: bool = False

    def keys(self) -> tuple[str, ...]:
        """所有可比较的写法（label ＋ aliases），已归一化 —— **去重保序**。"""
        out: list[str] = []
        for raw in (self.label, *self.aliases):
            k = normalize(raw)
            if k and k not in out:
                out.append(k)
        return tuple(out)


@dataclass(frozen=True)
class Suggestion:
    """一列的**建议**（不是决定）：`field=None` = 认不出，留空交人。"""

    src: str                    # 源列**原文**（⛔ 不出归一化结果）
    field: str | None           # 目标字段的 `label`；None = 不预选
    conf: float
    why: str                    # 依据（可解释：命中方式 / 类型是否吻合）
    level: str = field(default="blank")   # auto / confirm / blank

    @property
    def needs_confirm(self) -> bool:
        return self.level == "confirm"


def level_of(conf: float) -> str:
    """置信度 → 三档。"""
    if conf >= _CONF_AUTO:
        return "auto"
    if conf >= _CONF_CONFIRM:
        return "confirm"
    return "blank"


def _score(src_key: str, src_second: str, f: Field) -> tuple[float, str] | None:
    """单列 × 单字段 → `(置信度, 依据)`；认不出 ⇒ `None`。"""
    keys = f.keys()
    for k in keys:                                            # ① 归一化相等
        if src_key and src_key == k:
            return 1.00, f"与「{f.label}」归一化后相同"
    if src_second and src_second != src_key:                  # ①b 去掉通用词后相等
        for k in keys:
            if src_second == secondary(k):
                return 0.96, f"与「{f.label}」去掉「名称/编号」等通用词后相同"
    if not src_key:
        return None
    for k in keys:                                            # ② 包含词命中（实拍长表头）
        if k and (k in src_key or src_key in k):
            return 0.90, f"包含「{f.label}」（实拍长表头常见）"
    for a in (f.aliases or (f.label,)):                       # ③ token/字符交集
        nk = normalize(a)
        if not nk:
            continue
        inter = len(set(src_key) & set(nk))
        union = len(set(src_key) | set(nk))
        if union and inter / union >= 0.6:
            return round(0.70 + 0.20 * (inter / union), 2), f"与「{f.label}」字形相似 {inter}/{union}"
    return None


def guess(headers, fields, samples: dict | None = None) -> list[Suggestion]:
    """逐列出**建议**：`headers` = 源表头原文（含两级拼名后的写法亦可）。

    `samples`：`{源列原文: [值, …]}` —— 给了就做**类型交叉验证**（不符 ⇒ 降 `0.20` 并写明）。
    ⛔ 永不返回 <0.70 的预选：那种一律 `field=None`（界面留空让人选）。
    """
    samples = samples or {}
    out: list[Suggestion] = []
    for raw in headers:
        src = "" if raw is None else str(raw)
        key, sec = normalize(src), secondary(src)
        best: tuple[float, str, str] | None = None       # (conf, why, field_label)
        for f in fields:
            scored = _score(key, sec, f)
            if not scored:
                continue
            conf, why = scored
            # ⭐ 类型交叉验证：名字认对、值不像 ⇒ 降权（防"认对了名字、拿错了列"）
            #    ⚠️ 判据是「**字段类型**在不在该画像接受集里」——第一版写反了（拿画像名去比），
            #       症状 = **所有列都被降权**（自测抓到：连"项目"这种精确命中也掉到 confirm）。
            prof = profile(samples.get(src, [])) if samples.get(src) else ""
            if prof and f.type and f.type not in _TYPE_OK.get(prof, _ALL_TYPES):
                conf = round(max(0.0, conf - _TYPE_PENALTY), 2)
                why += f"；⚠️ 值像「{prof}」与字段类型 {f.type} 不符"
            if best is None or conf > best[0]:
                best = (conf, why, f.label)
        if best and best[0] >= _CONF_CONFIRM:
            out.append(Suggestion(src, best[2], best[0], best[1], level_of(best[0])))
        else:
            why = "四级命中都没到 0.70 ⇒ 不猜，留给你选" if best is None else \
                  f"最高只有 {best[0]:.2f}（{best[1]}）⇒ 不猜，留给你选"
            out.append(Suggestion(src, None, round(best[0], 2) if best else 0.0, why, "blank"))
    return out


def dupes(suggestions) -> dict[str, list[str]]:
    """**同一字段被多列认领** ⇒ `{字段: [源列…]}`（如台账里「供应商」出现两次）。

    ⚠️ 不自动裁决（域内才懂哪一列是"真身"）—— 只把它显式暴露出来。
    """
    got: dict[str, list[str]] = {}
    for s in suggestions:
        if s.field:
            got.setdefault(s.field, []).append(s.src)
    return {k: v for k, v in got.items() if len(v) > 1}


def type_conflict(prof: str, field_type: str) -> bool:
    """内容画像与字段类型是否**矛盾**（如"合同日期"列里装着一列「电汇」）。

    ⭐ 供**各域**做交叉校验（`m11` 的 `cross_check` 就用它）—— ⛔ 只用于**提示**，
       ⛔ 不用来改判：判定权在域内（别名表 / 界面）。
    ⚠️ 早先 `m11` 直接摸 `_TYPE_OK`（私有名）—— 那是"下一个人不敢改这行"的写法，换成这个公开出口。
    """
    if not prof or not field_type:
        return False
    return field_type not in _TYPE_OK.get(prof, _ALL_TYPES)


#: 「像数据」的形态（表头行里出现这些 ⇒ 它是**数据行**，不是表头词）。
#:  ⚠️ 一律复用**已有**的那几个正则（编号 / 日期 / 纯数字 / 中文月日），⛔ 不新写一套。
_DATA_FORMATS = (_CODE, _YMD_TEXT, _YMD_NUM, _CN_MD)
#: `2025-12-03 00:00:00` 这种**带时刻**的日期字面量（`_YMD_TEXT` 只认到"日"，认不了时刻）
_YMD_TIME = re.compile(r"^\d{4}\s*[-/.年]\s*\d{1,2}\s*[-/.月]\s*\d{1,2}\s*日?(?:[ T]\d{1,2}:\d{2})?$")


def _data_ish(value: str) -> bool:
    """单个值**像数据**吗（编号 / 日期 / 金额 / 纯数字）—— `looks_like_data` 的逐格判据。"""
    v = (value or "").strip()
    if not v:
        return False
    if _YMD_TIME.match(v) or any(rx.match(v) for rx in _DATA_FORMATS):
        return True
    return _NUM.match(v.replace(",", "").replace("，", "")) is not None


def looks_like_data(values, *, need: int = 2, ratio: float = 0.5) -> bool:
    """这一行（或这一列）**像数据**吗 —— 而不是表头文字。⭐⭐ 2026-09-27 真表逼出来的（`TAIL-129`）。

    ⚠️ **它守的是一件真出过的事**（用户报障原话：「**最后落库的单据号大多都变成供应商名了**」）：
       通用面挑表头时只看"这一行非空"就把它当**二级表头的子行** ⇒ 真表的**第一行数据**被拼进了列名
       （`收款单位` ＋ 首行数据的 `资产处集中采购`）⇒ 别名「资产处」被"包含词命中"抢走这一列
       ⇒ `收款单位` 被认成"单据号" ⇒ 落库全是供应商名（**一行数据也顺带被当成表头吃掉**）。
    ⇒ 判据：**非空格子里"像数据"的 ≥ `need` 格、且占比 ≥ `ratio`** ⇒ 这行是数据（⛔ 不许当表头）。
    ⚠️ 两个门槛是**故意不严**的（⛔ 不是"有一格像数据就否"）：表头里出现 `2025` 这种年份格很常见。
    ⛔ 也不许反过来拿它当"表头识别"用 —— 它只说"像数据"，**不说"是表头"**。
    """
    vals = [("" if v is None else str(v).strip()) for v in values]
    nz = [v for v in vals if v]
    if not nz:
        return False
    hits = sum(1 for v in nz if _data_ish(v))
    return hits >= need and hits / len(nz) >= ratio


#: 界面上的「忽略此列」哨兵（未映射列 ⇒ **原样保留**，⛔ 不报错丢弃）
IGNORE = "（忽略 · 原样保留）"


def apply(rows, headers, mapping: dict[str, str], *, keep_raw: bool = True) -> list[dict]:
    """按映射取行：`mapping` = `{源列原文: 字段 label | IGNORE}`。

    ⭐ 未映射/忽略的列进 `raw`（`{源列原文: 原值}`）**原样保留**（设计硬性 ②）。
    """
    out: list[dict] = []
    for row in rows:
        rec: dict = {}
        raw: dict = {}
        for i, src in enumerate(headers):
            val = row[i] if i < len(row) else None
            to = mapping.get(src, IGNORE)
            if to and to != IGNORE:
                rec[to] = val
            elif keep_raw:
                raw[src] = val
        if keep_raw:
            rec["raw"] = raw
        out.append(rec)
    return out


__all__ = [
    "IGNORE", "Field", "Suggestion", "apply", "dupes", "guess", "join_levels",
    "level_of", "looks_like_data", "normalize", "profile", "secondary", "serial_hint",
    "type_conflict",
]
