"""付款计划域内核（**纯函数**）：审查引擎 · 项目列匹配 · 无单据号处置 · 生效窗口。

依据：《说明书》§4.3.3（Excel 结构 / 可手改列）· §4.3.4（审查规则 6 种 + 两档归并）· §4.3.6（历史保留）· §4.3.7（10 号截止）。

⚠️ **审查结果不落库**（001-01）：一律 `audit_rows()` 现算。
⚠️ **判定优先级**：PRD 只给了 6 种判定的成立条件、**未给优先级**；本实现按 §4.3.4 表序取
   「结构性问题优先」：无单据号 → 单据号查不到 → 重复上报 → 超过未付 → 金额不符 → 完全匹配。
   （**该优先级属实现约定，已登记待确认**；口径若给出优先级，改此处一处即可。）
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal

from app.core.errors import MustReportError
from app.core.money import to_money
from app.mod04_plan.models import (
    EDITABLE_COLUMNS,
    MATCH_AMBIGUOUS,
    MATCH_MATCHED,
    MATCH_UNMATCHED,
)

# ---------------------------------------------------------------- 判定（§4.3.4 六种）

R_MATCHED = "完全匹配"
R_AMOUNT_MISMATCH = "金额不符"
R_DOC_NOT_FOUND = "单据号查不到"
R_NO_DOC = "无单据号"
R_DUPLICATE = "重复上报"
R_OVER_UNPAID = "超过未付"

ALL_RESULTS: tuple[str, ...] = (
    R_MATCHED, R_AMOUNT_MISMATCH, R_DOC_NOT_FOUND, R_NO_DOC, R_DUPLICATE, R_OVER_UNPAID,
)

# 界面筛选**只归并两档**（§4.3.4）：完全匹配 / 未匹配（= 其余 5 种）
BUCKET_MATCHED = "完全匹配"
BUCKET_UNMATCHED = "未匹配"
BUCKET_ALL = "全部"
FILTER_BUCKETS: tuple[str, ...] = (BUCKET_ALL, BUCKET_MATCHED, BUCKET_UNMATCHED)


def bucket(result: str) -> str:
    """判定 → 筛选两档（001-06 / 001-07）。"""
    return BUCKET_MATCHED if result == R_MATCHED else BUCKET_UNMATCHED


# ---------------------------------------------------------------- 比对视图


@dataclass
class NoticeAmounts:
    """由命中的 i8 通知书派生的比对视图。"""

    doc_no: str
    approved: Decimal          # 审批金额
    paid: Decimal              # 已付金额（**付款流水汇总**）

    @property
    def unpaid(self) -> Decimal:
        """未付金额 = 审批金额 − 已付金额。"""
        return self.approved - self.paid


def outstanding(approved, paid) -> Decimal:
    """未付金额（口径落点，供独立复算）。"""
    return to_money(approved) - to_money(paid)


# ---------------------------------------------------------------- 项目列匹配（§4.3.3）


@dataclass
class ProjectBrief:
    """匹配用的档案行视图（只需这几个字段；避免与 `MOD-01` 强耦合）。"""

    id: int
    disp: str = ""
    warehouse_name: str | None = None
    name_full: str = ""     # ⚠️ **不作匹配键**（001-02）—— 仅用于证明"全名不参与匹配"
    #: ⭐ 用户在「项目管理」页维护的**关键词/简称**（`project.match_keywords`）—— 第④步别名用。
    #:  ⚠️ 它同时服务 i8 单据名的归属判定（§2.5.1），语义是"这个项目的叫法"⇒ 复用**不是**挪用。
    keywords: tuple[str, ...] = ()


@dataclass
class MatchResult:
    project_id: int | None
    status: str
    candidates: int = 0
    display: str = ""
    #: ⭐ 靠**哪一步**命中的（`精确` / `归一` / `包含` / `别名`）—— 界面要能回答"为什么它配上了"
    #:  （守则 §3.3 状态要真实）；`ambiguous` / `unmatched` 也记，便于定位是**哪一步**出的歧义。
    how: str = ""
    #: ⭐⭐ 重名时的**候选展示名清单**（只有 `ambiguous` 会填）—— 界面要能列出"对上了哪几条"。
    #:  ⚠️⚠️ 从前这里**只有个数**（`candidates`），而 `importer.match_summary` 却把它当**清单**去
    #:     `list(...)` ⇒ 一旦真有重名就 `TypeError: 'int' object is not iterable`
    #:     （2026-09-27 真机抓出来的**既有缺陷**：此前一直没有"重名行"去触发它）。
    candidate_labels: tuple[str, ...] = ()

    @property
    def is_matched(self) -> bool:
        return self.status == MATCH_MATCHED


PROJECT_COLUMN_HEADER = "项目（填「展示名」或「仓库名」）"

#: 归一化时去掉的**噪声字符**（空白 / 括号 / 各种标点）—— ⚠️ 只用于**比较**，⛔ 不出参、不改原值。
_NAME_NOISE = re.compile(r"[\s\u3000()（）\[\]【】·、,，。:：;；\-—_/\\'\"“”‘’]")
#: 归一化时去掉的**尾部通用词**（`晋江污泥` ≈ `晋江污泥项目`）。
#:  ⚠️ 只削**尾部**、且**从长到短**匹配（`XX项目部` 要削成 `XX`，不能被 `项目` 咬成 `XX部`）。
_TAIL_WORDS = ("项目部", "项目", "工程")
#: 第③步「包含匹配」的**最小长度**（归一化后·**两侧都要够长**）。
#:  ⚠️ 定这个数的依据（2026-09-27 真机）：短输入做包含匹配会到处乱撞（`0` 撞上 `未建仓03`/`未建仓04`），
#:     而实测真正靠它命中的两例（`晋江污泥` / `大唐雷州`）都是 4 个字 ⇒ 3 字是**不损失收益的下限**。
_MIN_CONTAIN = 3


def _label_of(p: ProjectBrief) -> str:
    """档案行的**展示名**（与「项目」列的填报口径一致；拿不到就退回仓库名 / id）。"""
    return p.disp or p.warehouse_name or f"#{p.id}"


def norm_name(value: str) -> str:
    """项目名的**归一化比较键**（只用于比较）：全半角统一 → 去噪声字符 → 去尾部「项目/工程」。

    ⭐ 2026-09-27（`TAIL-129` · 用户走查 ＋ 真表实验）：用户表里写的是**简称**
      （`晋江污泥` / `大唐雷州`），档案展示名却是 `晋江污泥项目` / `大唐雷州发电项目`
      ⇒ 只做精确相等时**只中 8/10**；加上本归一化与"唯一包含"后 **10/10 全中、零歧义**。
    """
    s = unicodedata.normalize("NFKC", str(value or "")).strip()
    s = _NAME_NOISE.sub("", s)
    for w in _TAIL_WORDS:                      # 已按长度排序（长词在前）
        if s.endswith(w) and len(s) > len(w):
            s = s[: -len(w)]
            break
    return s.lower()


def match_project(value: str, projects: list[ProjectBrief]) -> MatchResult:
    """「项目」列 → 档案行：**四步递进**，每一步都必须**唯一命中**才算过（§4.3.3）。

    | 步 | 判据 | 真表上的例子 |
    |---|---|---|
    | ① 精确 | 展示名 / 仓库名 **全等** | `灵宝二期` → `灵宝二期` |
    | ② 归一 | 归一化（去空白标点、去尾部「项目」）后全等 | `晋江污泥` → `晋江污泥项目` |
    | ③ 包含 | 归一化后一方**包含**另一方，且**命中唯一** | `大唐雷州` ⊂ `大唐雷州发电项目` |
    | ④ 别名 | `match_keywords` 归一化全等（用户在「项目管理」页维护） | 用户自己补的简称 |
    命不中 ⇒ `unmatched`（**不猜**）；任一步命中多条 ⇒ `ambiguous`（标「重名 N 条」，人工核对）。

    ⚠️ **全名不作匹配键**（001-02：核销键是仓库名/展示名；全名壳与小微共用）—— ⛔ 别为了"多发命中"
       把 `name_full` 拉进来（那会破判据，且全名里带编号后缀，匹配上更容易误伤）。
    ⚠️ 第③步**只在"唯一命中"时才算数**：命中多条一律交人（⛔ 不挑一个"最像的"）。
    ⭐ **为什么不引入 AI**（用户问过"这里引入 AI 效果如何？"）：真表 10 种写法上，
      规则已 **10/10 全中**；而 AI 的代价是**不可复现**（同输入两次不同结果）、
      依赖模型与网络、**判据写不出来**（本仓每条口径都要有机器判据）、
      且表里有**收款单位与金额**（发出去就是数据外流）⇒ 收益为 0、代价全占。
    """
    v = (value or "").strip()
    if not v:
        return MatchResult(None, MATCH_UNMATCHED)

    def hit(hits: list[ProjectBrief], how: str) -> MatchResult | None:
        """唯一 ⇒ matched；多条 ⇒ ambiguous；0 条 ⇒ `None`（交给下一步）。

        ⚠️ `ambiguous` 时**必须**带上候选清单（`candidate_labels`）—— 界面上那句「重名 N 条」
           要能点开看"是哪几条"（⛔ 只给个数字等于让人自己去猜，与"不猜"的整条口径相冲突）。
        """
        if len(hits) == 1:
            p = hits[0]
            return MatchResult(p.id, MATCH_MATCHED, 1, _label_of(p), how)
        if hits:
            return MatchResult(None, MATCH_AMBIGUOUS, len(hits), "", how,
                               tuple(_label_of(p) for p in hits))
        return None

    # ① 精确（原口径：展示名 / 仓库名全等）
    got = hit([p for p in projects if p.disp == v or (p.warehouse_name and p.warehouse_name == v)], "精确")
    if got:
        return got

    nv = norm_name(v)
    if not nv:
        return MatchResult(None, MATCH_UNMATCHED)
    briefs = [(p, norm_name(p.disp), norm_name(p.warehouse_name or "")) for p in projects]

    # ② 归一化后相等
    got = hit([p for p, d, w in briefs if nv == d or (w and nv == w)], "归一")
    if got:
        return got

    # ③ 唯一包含（一方含另一方）—— ⚠️ 命中多条 ⇒ ambiguous，⛔ 不挑"最像的"
    #    ⚠️⚠️ **两侧都要够长**（`_MIN_CONTAIN`）：短输入做包含匹配会**到处乱撞** ——
    #    2026-09-27 真机实测：夹具里项目列写成 `0`，当场撞上 `未建仓03` / `未建仓04` 两条 ⇒ **假歧义**
    #    （顺带把 `match_summary` 里一个既有的 `list(int)` 缺陷也一起引爆了）。实测有效的两例
    #    （`晋江污泥` / `大唐雷州`）都是 4 个字 ⇒ 定 3 字**不损失真实收益**。
    def _cont(a: str, b: str) -> bool:
        return bool(a) and bool(b) and min(len(a), len(b)) >= _MIN_CONTAIN and (a in b or b in a)

    got = hit([p for p, d, w in briefs if _cont(nv, d) or _cont(nv, w)], "包含")
    if got:
        return got

    # ④ 别名（用户维护的关键词，**全等**才算）—— ⚠️ 这一档**只做全等**：
    #    关键词里有"油漆""铝板"这类**材料词**（它服务 i8 单据名归属），做包含匹配会误伤。
    got = hit([p for p in projects
               if any(nv == norm_name(k) for k in (p.keywords or ()) if norm_name(k))], "别名")
    if got:
        return got

    return MatchResult(None, MATCH_UNMATCHED)


# ---------------------------------------------------------------- 审查引擎（§4.3.4）


def duplicate_keys(rows: list[dict]) -> set[tuple]:
    """判重键集合：**同月 + 同单据号**出现 ≥2 次（跨月不算）；**空单据号不参与判重**（001-05 / NODOC-001-01）。"""
    counts: dict[tuple, int] = {}
    for r in rows:
        doc = str(r.get("doc_no") or "").strip()
        if not doc:
            continue
        key = (str(r.get("year_month") or ""), doc)
        counts[key] = counts.get(key, 0) + 1
    return {k for k, n in counts.items() if n >= 2}


def audit_row(
    row: dict,
    notices_by_doc: dict[str, NoticeAmounts],
    dup_keys: set[tuple],
) -> str:
    """单行判定（§4.3.4；优先级见模块头）。"""
    doc = str(row.get("doc_no") or "").strip()
    if not doc:
        return R_NO_DOC                                    # ① 无单据号（也不并入判重）
    notice = notices_by_doc.get(doc)
    if notice is None:
        return R_DOC_NOT_FOUND                             # ② 单据号查不到
    if (str(row.get("year_month") or ""), doc) in dup_keys:
        return R_DUPLICATE                                 # ③ 重复上报（**双向**：两行都判）
    planned = to_money(row.get("planned_amount") or 0)
    if planned > notice.unpaid:
        return R_OVER_UNPAID                               # ④ 本月预付款 > 未付金额
    if to_money(row.get("flow_amount") or 0) != notice.approved:
        return R_AMOUNT_MISMATCH                           # ⑤ 该流程金额 ≠ 通知书审批金额
    return R_MATCHED                                       # ⑥ 号对 + 金额对 + 不超未付


def audit_rows(rows: list[dict], notices_by_doc: dict[str, NoticeAmounts]) -> list[str]:
    """整批审查（**实时派生、不落库**，001-01）。返回与 `rows` 等长的判定列表。"""
    dup = duplicate_keys(rows)
    return [audit_row(r, notices_by_doc, dup) for r in rows]


def re_audit(row: dict, notices_by_doc: dict[str, NoticeAmounts], rows_for_dup: list[dict] | None = None) -> str:
    """「再次匹配」= 用同一引擎重判该行（改完单据号后调用，001-03）。"""
    dup = duplicate_keys(rows_for_dup if rows_for_dup is not None else [row])
    return audit_row(row, notices_by_doc, dup)


def can_edit_doc(result: str) -> bool:
    """单据号**只对「未匹配」行开放编辑**；「完全匹配」行只读（NODOC-001-02）。"""
    return result != R_MATCHED


def derived_columns(notice: NoticeAmounts | None) -> tuple[str, str]:
    """界面上的「已付款金额 / 剩余付款金额」两列（**由命中通知书派生**）。

    - 命中 ⇒ `(已付金额, 未付金额)`
    - **命不中 ⇒ 留空**（`("", "")`）—— 不猜、不留假数据（NODOC-001-04）
    """
    if notice is None:
        return "", ""
    return f"{notice.paid:.2f}", f"{notice.unpaid:.2f}"


# 列序（NODOC-001-05）：派生两列夹在「i8 流程金额」与「本月预付款金额」之间
COLUMN_ORDER: tuple[str, ...] = (
    "year_month", "project", "doc_no",
    "flow_amount", "paid_amount", "unpaid_amount", "planned_amount",
    "pay_date", "pay_method", "remark", "audit_result",
)


def column_order_ok() -> bool:
    i_flow = COLUMN_ORDER.index("flow_amount")
    i_planned = COLUMN_ORDER.index("planned_amount")
    return COLUMN_ORDER[i_flow + 1:i_planned] == ("paid_amount", "unpaid_amount")


# ---------------------------------------------------------------- 强制通过（001-09）


def force_through(remark: str) -> dict:
    """强制通过：**必须写备注**（留痕）；空备注 ⇒ 拒绝（001-09）。"""
    text = (remark or "").strip()
    if not text:
        raise MustReportError("强制通过必须填写备注（说明为什么放行）—— 空备注不被接受")
    return {"forced_through": True, "forced_remark": text}


def cancel_force() -> dict:
    """取消强制通过：回到**原判定**且**备注清空**（不留残余；取消不留痕）（001-09）。"""
    return {"forced_through": False, "forced_remark": ""}


# ---------------------------------------------------------------- 生效窗口（§4.3.2 / §4.3.7）


WINDOW_START_DAY = 10   # 每月 10 号起生效（10 号 → 月底）


def in_effective_window(day_of_month: int) -> bool:
    """是否落在付款计划生效窗口（每月 **10 号 → 月底**）。窗口外按钮**先禁用**（PLAN-UI-001-08）。"""
    return WINDOW_START_DAY <= int(day_of_month) <= 31


def window_label(day_of_month: int) -> str:
    if in_effective_window(day_of_month):
        return "生效中（每月 10 号 → 月底）"
    return "未到生效窗口（每月 10 号起生效）"


# ---------------------------------------------------------------- 默认筛选（IMPORT-001-07）


def default_plan_filters(now=None) -> dict:
    """默认筛选：**年月 = 北京时间当月**；**审查结果 = 全部**（IMPORT-001-07）。"""
    from app.core.period import default_period

    return {"year_month": default_period("plan", now), "audit_bucket": BUCKET_ALL}


# ---------------------------------------------------------------- 页面交互内核 → 已拆出
#
# ⚠️ **2026-09-15 拆分**（工程纪律：单文件 >400 行须拆）：
#    页面交互内核（筛选栏 / 行内改列 / 再次匹配 / 列表内删除 / 生效窗口按钮态）
#    已移到 **`app.mod04_plan.plan_ui`**；本文件只保留**审查引擎与口径基础件**。
#    ⇒ 两边**不得各留一份定义**：判定一律 `audit_rows` / `re_audit`，可改列一律 `can_edit_doc`。


__all__ = [
    "R_MATCHED", "R_AMOUNT_MISMATCH", "R_DOC_NOT_FOUND", "R_NO_DOC", "R_DUPLICATE", "R_OVER_UNPAID",
    "ALL_RESULTS", "BUCKET_MATCHED", "BUCKET_UNMATCHED", "BUCKET_ALL", "FILTER_BUCKETS", "bucket",
    "NoticeAmounts", "outstanding", "ProjectBrief", "MatchResult", "match_project", "norm_name",
    "PROJECT_COLUMN_HEADER", "duplicate_keys", "audit_row", "audit_rows", "re_audit",
    "can_edit_doc", "derived_columns", "COLUMN_ORDER", "column_order_ok",
    "force_through", "cancel_force",
    "WINDOW_START_DAY", "in_effective_window", "window_label", "default_plan_filters",
    "EDITABLE_COLUMNS", "MATCH_MATCHED", "MATCH_UNMATCHED", "MATCH_AMBIGUOUS",
]
