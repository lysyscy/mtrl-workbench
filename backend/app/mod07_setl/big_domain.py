"""`MOD-07` **经济活动分析大表**的域内核（**纯函数** · 不连库、不写路由、不写 HTML）。

口径主人 = 《说明书》**§5.7.1 / §5.7.2 / §5.7.3**（另参 §2.7.3 顺序 · §2.7.4 项目键 · §1.4.1 出纸通道）。
交互规格 = 原型 `V.m07` 的「经济活动分析大表」块（`BIG_THEAD` / `BIGCOLS` / `BIGFMT` / `bigCell` / `bigRows`）。

本文件只做四件事：**列结构** · **手填值解析与「上次值带入」** · **行装配**（页面与导出共用）· **三个派生列**。

⚠️ **列名与列数一律回主人（§5.7.1）** —— 本文件只是它的**工程投影**：`BIG_HEADER`（两行表头）与
   `BIG_COLUMNS`（20 列）由**同一份** `_SPECS` 生成（`zip(..., strict=True)`）
   ⇒ 表头与列**不可能各写一遍**（`MOD-09` 的教训：「同一句文案写两遍 ⇒ 改坏一处仍然全绿」）。

⛔ **不臆造**：分母为空 / 为 0 时比率列给 `None`（页面显「—」），**不写 0**；
   集采结算额**不可得**时同样给 `None`（区别于「该项目确实没有纳入台账的合同」的 0）。
"""

from __future__ import annotations

from decimal import Decimal

from app.core.money import sum_money, to_money
from app.core.period import default_period
from app.mod01_projects.domain import build_candidates

# ============================================================ 列结构（§5.7.1 · 20 列 · 两行表头）

#: **两行表头**（逐条照原型 `BIG_THEAD`）：`(组标签, 子列标签…)`；**子列为空 ⇒ 该列跨两行**。
BIG_HEADER: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("序号", ()),
    ("项目名称", ()),
    ("开工时间", ()),
    ("辅材使用（不含税）", ("焊材累计", "焊材当月", "三气累计", "三气当月")),
    ("外租使用（含税）", ("外租机械开工累计", "外租机械当月", "设备租赁开工累计", "设备租赁当月")),
    ("合计", ()),
    ("机械费测算", ()),
    ("使用率", ()),
    ("产值", ("产值完成率", "合同（预估）价", "产值累计（含税）")),
    ("主材累计（含税）", ()),
    ("工程用油", ()),
    ("备注", ()),
)

#: 列的性质：`auto` = 系统自动取数 · `hand` = 手填 · `derived` = 派生
KIND_AUTO = "auto"
KIND_HAND = "hand"
KIND_DERIVED = "derived"

#: 列的**存储 / 显示格式**（照原型 `BIGFMT`）：`ym` 年月 · `money` 金额 · `text` 文本 · `int` 序号 · `rate` 比率
FMT_YM = "ym"
FMT_MONEY = "money"
FMT_TEXT = "text"
FMT_INT = "int"
FMT_RATE = "rate"

#: `(key, 性质, 格式)` —— **20 列一行一个**，顺序 = 表头叶序（下面与 `BIG_HEADER` 用 `strict=True` 对齐）
_SPECS: tuple[tuple[str, str, str], ...] = (
    ("seq",         KIND_DERIVED, FMT_INT),     # 序号：自增
    ("project",     KIND_DERIVED, FMT_TEXT),    # 项目名称：**展示名**（§2.7.4）
    ("open_ym",     KIND_HAND,    FMT_YM),      # ┐
    ("hw_cum",      KIND_AUTO,    FMT_MONEY),   # │ 焊材累计 = 提取的「总金额」口径（§5.3.3）
    ("hw_mon",      KIND_AUTO,    FMT_MONEY),   # │ 焊材当月 = 该核算月
    ("qt_cum",      KIND_AUTO,    FMT_MONEY),   # │ 三气累计
    ("qt_mon",      KIND_AUTO,    FMT_MONEY),   # ┘ 三气当月
    ("rent_cum",    KIND_AUTO,    FMT_MONEY),   # ┐ 外租机械开工累计 = 外租零租含税 ＋ 外租包月含税
    ("rent_mon",    KIND_AUTO,    FMT_MONEY),   # │ 当月
    ("lease_cum",   KIND_AUTO,    FMT_MONEY),   # │ 设备租赁（含内租）开工累计 = 机械 6 列的「内租设备」
    ("lease_mon",   KIND_AUTO,    FMT_MONEY),   # ┘ 当月
    ("total_cum",   KIND_DERIVED, FMT_MONEY),   # 合计 = 外租机械开工累计 ＋ 设备租赁开工累计
    ("mech_est",    KIND_HAND,    FMT_MONEY),   # 机械费测算（手填）
    ("use_rate",    KIND_DERIVED, FMT_RATE),    # 使用率 = 合计 ÷ 机械费测算
    ("output_rate", KIND_DERIVED, FMT_RATE),    # 产值完成率 = 产值累计 ÷ 合同（预估）价
    ("contract",    KIND_HAND,    FMT_MONEY),   # 合同（预估）价（手填）
    ("output_cum",  KIND_HAND,    FMT_MONEY),   # 产值累计（含税）（手填）
    ("mat_cum",     KIND_DERIVED, FMT_MONEY),   # 主材累计（含税）= 按项目取集采台账结算额（§5.7.1 末条）
    ("oil",         KIND_HAND,    FMT_MONEY),   # 工程用油（手填 · 油卡台账）
    ("note",        KIND_HAND,    FMT_TEXT),    # 备注（手填 · 自由文本）
)


def _leaf_labels() -> tuple[str, ...]:
    """把两行表头拍平成 **20 个叶标签**（顺序 = 列顺序）。"""
    out: list[str] = []
    for group, subs in BIG_HEADER:
        out.extend(subs or (group,))
    return tuple(out)


_LEAVES = _leaf_labels()

#: **列定义**（20 项）—— `dict(key, label, kind, fmt)`
BIG_COLUMNS: tuple[dict, ...] = tuple(
    {"key": key, "label": label, "kind": kind, "fmt": fmt}
    for (key, kind, fmt), label in zip(_SPECS, _LEAVES, strict=True)   # ⭐ 列数与表头**不可能脱节**
)

_LABEL: dict[str, str] = {c["key"]: c["label"] for c in BIG_COLUMNS}
_KIND: dict[str, str] = {c["key"]: c["kind"] for c in BIG_COLUMNS}

#: 列标签（按列序）—— 页面表头与断言共用同一份
BIG_LABELS: tuple[str, ...] = tuple(c["label"] for c in BIG_COLUMNS)

#: 手填列的**持久化列名**（`(key, 格式, 落库列名)`）—— 表头 / 列名的主人仍是上表，这里**不重复写标签**
_MANUAL_SPECS: tuple[tuple[str, str, str], ...] = (
    ("open_ym",    FMT_YM,    "open_ym"),
    ("mech_est",   FMT_MONEY, "mech_est"),
    ("contract",   FMT_MONEY, "contract_price"),
    ("output_cum", FMT_MONEY, "output_cum"),
    ("oil",        FMT_MONEY, "oil"),
    ("note",       FMT_TEXT,  "note"),
)

#: **手填 6 列**（标签取自 `BIG_COLUMNS`，⛔ 不再写一遍）
BIG_MANUAL: tuple[dict, ...] = tuple(
    {"key": key, "fmt": fmt, "column": column, "label": _LABEL[key]}
    for key, fmt, column in _MANUAL_SPECS
)
BIG_MANUAL_KEYS: tuple[str, ...] = tuple(m["key"] for m in BIG_MANUAL)
MANUAL_COLUMN: dict[str, str] = {m["key"]: m["column"] for m in BIG_MANUAL}
MANUAL_FMT: dict[str, str] = {m["key"]: m["fmt"] for m in BIG_MANUAL}

#: **合计行**逐列求和的范围（照原型：自动列 ＋ 手填金额列 ＋ 主材累计；**不含**比率列 / 开工时间 / 备注）
TOTAL_KEYS: tuple[str, ...] = (
    "hw_cum", "hw_mon", "qt_cum", "qt_mon",
    "rent_cum", "rent_mon", "lease_cum", "lease_mon", "total_cum",
    "mech_est", "contract", "output_cum", "mat_cum", "oil",
)

#: 三个派生列的公式（**唯一出口**：页面与导出、断言都用它）
TOTAL_FORMULA = "合计 = 外租机械开工累计 ＋ 设备租赁开工累计"
USE_RATE_FORMULA = "使用率 = 合计 ÷ 机械费测算"
OUTPUT_RATE_FORMULA = "产值完成率 = 产值累计 ÷ 合同（预估）价"

#: 项目集合与顺序（§5.7.3）
SELECT_NOTE = ("候选 = 项目档案里**状态在建 · 非壳**（壳没有仓库 ⇒ 不进候选）；"
               "**从未选题时默认 = 全部候选**，一旦选题过 ⇒ **表里只出现所选的那几个**"
               "（后来新增的项目要**再勾一次**）；顺序是**大表自己的**"
               "（与全站项目排序无关，可逐项上移 / 下移）。")

#: 主材累计的取数口径（§5.7.1 末条 · 与 `MOD-11` 的「Σ 结算金额」同口径）
MAIN_MATERIAL_NOTE = ("主材累计（含税）= 按项目取**集采台账结算**额"
                      "（= 该项目集采合同**结算金额**之和；**只计「纳入台账」的合同**）。")
MAIN_MATERIAL_UNAVAILABLE = "集采台账（`MOD-11`）未接入"      # 取数口未接 ⇒ 显示「—」，**不写 0**

#: 硬边界（§5.7.1 注 · `DEV-R-03` · `NG-01`/`NG-02`/`NG-04`）—— 页面与导出**都不得出现**
FORBIDDEN_TEXTS: tuple[tuple[str, str], ...] = (
    ("材料费", "大表**不得设「材料费」数据项**（业务上无此数据，`DEV-R-03`）"),
    ("租分公司设备", "该列**不进本表**（付款由会计直接划拨，§5.6.1.1）"),
    ("外租零租不含税", "两个「不含税」列**不进本表**（同上）"),
    ("外租包月不含税", "两个「不含税」列**不进本表**（同上）"),
    ("列设置", "列设置面板不做（`NG-01`）"),
    ("列宽", "列宽拖动不做（`NG-02`）"),
    ("督办", "提醒与督办不做（`NG-04`）"),
    ("A3", "出纸通道已整条取消「A3 打印」（§1.4.1 · §5.7.2）"),
)

#: 出纸通道（§5.7.2 · §1.4.1）
PRINT_CHANNEL = "按模板导出 → Excel 打印"

#: 手填值四个提示（页面文案的唯一出口）
MSG_BAD_YM = "开工时间要填 `YYYY-MM`（例：2026-03）；本次未保存，原值不变"
MSG_BAD_MONEY = "金额要填数字（2 位小数 · **不得为负**）；本次未保存，原值不变"
MSG_SAVED = "已保存到本月（该格转为本月录入，不再带入）"
MSG_CLEARED = "已清空 → 回到「上次值带入」态"
MSG_NO_PROJECT = "没找到这个项目（键 = 仓库名）"
MSG_NO_COLUMN = "认不出的列"


# ============================================================ 时间（§9.2）

def default_month(now=None) -> str:
    """本表默认核算年月 = **材料报表类 · 北京时间上月**（§9.2，唯一出口 = `core.period`）。"""
    return default_period("big", now)


def label_of(key: str) -> str:
    """列 key → 列标签（**唯一出口**；认不出原样返回，不臆造）。"""
    return _LABEL.get(str(key or ""), str(key or ""))


def parse_month(raw) -> str | None:
    """手填的**开工时间**：**只接受 `YYYY-MM`**（原型 `bigStore` 的同一条正则），认不出给 `None`。

    ⚠️ 不能用 `isNaN` 那一套判 —— `isNaN('2024-05')` 恒为 `True`（原型的注释就为这条踩过）。
    """
    v = str(raw if raw is not None else "").strip()
    if len(v) != 7 or v[4] != "-":
        return None
    y, m = v[:4], v[5:]
    if not (y.isdigit() and m.isdigit()) or not 1 <= int(m) <= 12:
        return None
    return v


# ============================================================ 手填值：解析 ＋「上次值带入」（§5.7.2）

def parse_manual(raw, fmt: str) -> dict:
    """手填格的输入解析 → `{"ok": bool, "value": …, "message": str}`。

    - **空** ⇒ `ok=True, value=None` = **清空**（回到带入态，001-10）
    - `ym` ⇒ 只认 `YYYY-MM`；`money` ⇒ 数字 · 2 位小数 · **不得为负**（001-07/001-08）
    - `text` ⇒ 原样（去首尾空白）
    """
    s = str(raw if raw is not None else "").strip()
    if s == "":
        return {"ok": True, "value": None, "message": ""}
    if fmt == FMT_TEXT:
        return {"ok": True, "value": s, "message": ""}
    if fmt == FMT_YM:
        v = parse_month(s)
        if v is None:
            return {"ok": False, "value": None, "message": MSG_BAD_YM}
        return {"ok": True, "value": v, "message": ""}
    # money
    try:
        v = to_money(s)
    except Exception:  # noqa: BLE001 - 非数字一律拒（不猜、不静默变 0）
        return {"ok": False, "value": None, "message": MSG_BAD_MONEY}
    if v < 0:
        return {"ok": False, "value": None, "message": MSG_BAD_MONEY}
    return {"ok": True, "value": v, "message": ""}


def manual_cell(own_by_ym: dict, month: str, warehouse: str, key: str) -> dict:
    """某一格的手填取值（§5.7.2「上次值带入」）→ `{"value": …, "from": "来源月" | ""}`。

    ⭐ 判据 = **`is not None`**（不是真值判断）—— **0 是合法录入值**，不得被当成「未录入」（001-09）。
    本月已录 ⇒ `from=""`；否则**由近及远**跨月取**最近一次录入值**并标出来源月；全程无记录 ⇒ `value=None`。
    """
    cur = (own_by_ym.get(month) or {}).get(warehouse) or {}
    if cur.get(key) is not None:
        return {"value": cur[key], "from": ""}
    earlier = sorted((m for m in own_by_ym if str(m) < str(month)), reverse=True)
    for m in earlier:
        prev = (own_by_ym.get(m) or {}).get(warehouse) or {}
        if prev.get(key) is not None:
            return {"value": prev[key], "from": str(m)}
    return {"value": None, "from": ""}


# ============================================================ 三个派生列（§5.7.1）

def _dec(value, default: str = "0.00") -> Decimal:
    """取数容错：`None` / 空 ⇒ `default`（**只用于「合计」这类加法**；比率列的分母另有判据）。"""
    if value is None or value == "":
        return Decimal(default)
    return to_money(value)


def total_of(rent_cum, lease_cum) -> Decimal:
    """合计 = **外租机械开工累计 ＋ 设备租赁开工累计**（§5.7.1）。"""
    return sum_money([_dec(rent_cum), _dec(lease_cum)])


def use_rate(total_cum, mech_est) -> Decimal | None:
    """使用率 = **合计 ÷ 机械费测算**；分母为空 / 0 ⇒ `None`（**不臆造 0**）。"""
    den = _dec(mech_est)
    if den == 0:
        return None
    return (to_money(total_cum) / den).quantize(Decimal("0.0001"))


def output_rate(output_cum, contract) -> Decimal | None:
    """产值完成率 = **产值累计 ÷ 合同（预估）价**；分母为空 / 0 ⇒ `None`。"""
    den = _dec(contract)
    if den == 0:
        return None
    return (to_money(output_cum) / den).quantize(Decimal("0.0001"))


def rate_text(value) -> str:
    """比率显示（照原型 `PCT`）：1 位小数 + `%`；`None` ⇒ 空串（调用点给「—」）。"""
    if value is None:
        return ""
    return f"{(Decimal(str(value)) * 100):.1f}%"


# ============================================================ 主材累计（含税）—— 集采结算额

def main_material_total(contracts, *, project_key: str) -> Decimal:
    """主材累计（含税）= **按项目取「集采台账结算」额**（§5.7.1 末条 · §6.4.1 结算口径）。

    `contracts` 每行 = 集采合同落库行的**最小投影**（三个要素，都是《说明书》已定义的）：
    `{"project": 仓库名, "in_ledger": 是否纳入台账, "settle": 结算金额}`。

    ⭐ **只计「纳入台账」的合同**（用户 2026-09-13 裁定「甲」），与 `MOD-11` 的「Σ 结算金额」**同口径**。
    ⚠️ 集采台账属 **M5**，本函数是**规则**（可独立验证）；**取数口**在 `big_service`，未接入时给 `None`。
    """
    return sum_money([
        c.get("settle")
        for c in (contracts or ())
        if str(c.get("project") or "") == str(project_key or "") and bool(c.get("in_ledger"))
    ])


# ============================================================ 项目集合与顺序（§5.7.3）

def candidates(projects) -> list[dict]:
    """**候选** = 项目档案里**状态 = 在建 · 非壳**（§5.7.3）⇒ `[{"warehouse", "display"}]`。

    ⭐ 复用 `MOD-01` 的 `build_candidates`（键 = 仓库名 · 显示 = 展示名 · 壳没有仓库 ⇒ 不进候选），
       **不在这里另立一套**项目筛选。
    """
    return [
        {"warehouse": c.key, "display": c.display}
        for c in build_candidates(list(projects or ()))
        if not c.archived and c.key
    ]


def normalize_selection(selected, cands) -> list[str]:
    """保存选题结果 → 落库顺序（**只保留仍在候选里的键**，去重、保序）。

    ⚠️ 候选里已消失的（被归档 / 改名）**静默剔除但不新建** —— 大表只显示**真实存在**的项目。
    """
    keys = [str(c["warehouse"]) for c in (cands or ())]
    seen: list[str] = []
    for s in (selected or ()):
        k = str(s or "")
        if k in keys and k not in seen:
            seen.append(k)
    return seen


def resolve_order(order, cands, *, chosen: bool = True) -> list[str]:
    """库里的顺序 × 候选 → **本次要显示的顺序**（§5.7.3）。

    - **从未选题**（`chosen=False`）⇒ 默认 **全部候选**（按档案顺序）
    - **已选题** ⇒ 表里**只出现所选的那几个**（⛔ 不把后来新增的候选自动塞进去 ——
      口径是「表里只出现所选的那几个」，新项目要**再勾一次**）

    ⚠️ 「清空」与「从未选题」是两件事：前者是"表里 0 个项目"，后者才是"默认全部"
       ⇒ 靠仓储层的**标记行**区分（`big_repository.CHOICE_MARKER`）。
    """
    keys = [str(c["warehouse"]) for c in (cands or ())]
    if not chosen:
        return keys
    return [k for k in (str(x) for x in order) if k in keys]


def move_in_list(order, warehouse: str, direction: str) -> list[str]:
    """逐项**上移 / 下移**一格（§5.7.3）—— 越界即原样返回（不抛异常、不绕圈）。"""
    seq = [str(x) for x in (order or ())]
    key = str(warehouse or "")
    if key not in seq:
        return seq
    i = seq.index(key)
    j = i - 1 if direction == "up" else (i + 1 if direction == "down" else i)
    if j < 0 or j >= len(seq) or j == i:
        return seq
    seq[i], seq[j] = seq[j], seq[i]
    return seq


# ============================================================ 行装配（页面与导出**共用**）

def assemble_rows(projects, amounts: dict, own_by_ym: dict, *, month: str) -> list[dict]:
    """装配**整表行**（行序 = 所设顺序）—— 页面渲染与导出**共用这一份**（§5.7.3「两处同序」）。

    - `projects` = `[{"warehouse", "display"}]`（已按大表自己的顺序排好）
    - `amounts`   = `{仓库名: {自动列 key: 金额 | None}}`（取数由 `big_service` 注入；
      `None` = **取数口未接入 / 不可得** ⇒ 页面显「—」，**不写 0**）
      —— 键：`hw_cum/hw_mon/qt_cum/qt_mon/rent_cum/rent_mon/lease_cum/lease_mon/mat_cum`
    - `own_by_ym` = `{年月: {仓库名: {手填 key: 值}}}`（`None` = 该月未录入）
    """
    rows: list[dict] = []
    for i, p in enumerate(projects or ()):
        wh = str(p.get("warehouse") or "")
        amt = dict(amounts.get(wh) or {})
        manual = {k: manual_cell(own_by_ym, month, wh, k) for k in BIG_MANUAL_KEYS}
        rent_cum, lease_cum = amt.get("rent_cum"), amt.get("lease_cum")
        auto = {k: amt.get(k) for k in (
            "hw_cum", "hw_mon", "qt_cum", "qt_mon",
            "rent_cum", "rent_mon", "lease_cum", "lease_mon",
        )}
        rows.append({
            "seq": i + 1,
            "warehouse": wh,
            "display": str(p.get("display") or wh),
            "manual": manual,
            "auto": auto,
            "derived": {
                "total_cum": total_of(rent_cum, lease_cum),
                "use_rate": use_rate(total_of(rent_cum, lease_cum), manual["mech_est"]["value"]),
                "output_rate": output_rate(manual["output_cum"]["value"], manual["contract"]["value"]),
                "mat_cum": amt.get("mat_cum"),
            },
            # 带入格计数（页面「N 格带入」提示用）
            "carry_n": sum(1 for c in manual.values() if c["from"]),
        })
    return rows


def cell_value(row: dict, key: str):
    """按列 key 取该行的**取值 + 带入来源**（渲染层的唯一分支出口）。

    - `seq` / `project` ⇒ 取自**行本身**（序号与**展示名**，§2.7.4）
    - 手填列 ⇒ `(值, 来源月)`；自动 / 派生列 ⇒ `(值, "")`
    """
    if key == "seq":
        return row.get("seq"), ""
    if key == "project":
        return str(row.get("display") or ""), ""
    kind = _KIND.get(key)
    if kind == KIND_HAND:
        c = (row.get("manual") or {}).get(key) or {}
        return c.get("value"), str(c.get("from") or "")
    if kind == KIND_AUTO:
        return (row.get("auto") or {}).get(key), ""
    return (row.get("derived") or {}).get(key), ""


def totals_row(rows) -> dict:
    """**合计行**（照原型的列清单）：自动列 ＋ 手填金额列（**含带入值**）＋ 主材累计逐列求和。

    ⚠️ **比率列 / 开工时间 / 备注不求**（照原型）；主材累计**不可得**（`None`）时该格给 `None`。
    """
    out: dict = {}
    for key in TOTAL_KEYS:
        vals = []
        for r in rows or ():
            v, _from = cell_value(r, key)
            if v is None or v == "":
                continue
            vals.append(v)
        if key == "mat_cum" and not vals:
            out[key] = None               # 整列不可得 ⇒ 不写 0
        else:
            out[key] = sum_money(vals)
    return out


def carry_count(rows) -> int:
    """全表带入格总数（页面提示用）。"""
    return sum(int(r.get("carry_n") or 0) for r in (rows or ()))


def empty_text(month: str) -> str:
    """空态提示行（不是「没有数据」，而是**还没勾项目**）。"""
    return (f"{month}：大表里还没有项目 —— 点上方「选题」从**在建项目**里挑几个"
            "（默认 = 全部候选）。")


# ============================================================ 硬边界（页面 / 导出都查）

def boundary_violations(*, html: str = "", actions=()) -> list[str]:
    """硬边界自检（`FORBIDDEN_TEXTS`）—— 返回违规说明（空 = 合规）。页面与导出**都跑这一条**。"""
    hits: list[str] = []
    text = str(html or "")
    for needle, why in FORBIDDEN_TEXTS:
        if needle and needle in text:
            hits.append(f"页面 / 导出里出现了「{needle}」：{why}")
    for a in actions or ():
        if str(a) in ("print", "printA3", "pagePrint"):
            hits.append(f"动作 `{a}`：出纸通道已取消「页面 / A3 打印」（§1.4.1）")
    return hits


__all__ = [
    "BIG_HEADER", "BIG_COLUMNS", "BIG_LABELS", "BIG_MANUAL", "BIG_MANUAL_KEYS",
    "MANUAL_COLUMN", "MANUAL_FMT", "TOTAL_KEYS", "KIND_AUTO", "KIND_HAND", "KIND_DERIVED",
    "FMT_YM", "FMT_MONEY", "FMT_TEXT", "FMT_INT", "FMT_RATE",
    "TOTAL_FORMULA", "USE_RATE_FORMULA", "OUTPUT_RATE_FORMULA", "SELECT_NOTE",
    "MAIN_MATERIAL_NOTE", "MAIN_MATERIAL_UNAVAILABLE", "PRINT_CHANNEL", "FORBIDDEN_TEXTS",
    "MSG_BAD_YM", "MSG_BAD_MONEY", "MSG_SAVED", "MSG_CLEARED", "MSG_NO_PROJECT", "MSG_NO_COLUMN",
    "default_month", "parse_month", "parse_manual", "manual_cell", "label_of",
    "total_of", "use_rate", "output_rate", "rate_text", "main_material_total",
    "candidates", "normalize_selection", "resolve_order", "move_in_list",
    "assemble_rows", "cell_value", "totals_row", "carry_count", "empty_text",
    "boundary_violations",
]
