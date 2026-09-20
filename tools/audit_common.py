#!/usr/bin/env python
"""`doc_audit` 公共件 —— 常量表 ＋ 文档扫描基础设施（**纯搬运**，无逻辑改动）。

拆因：`doc_audit.py` 涨到 597 行（<600 但贴着 `T5` 硬上限）。
拆法：常量与基础设施 → 本件；`T1–T4` → `audit_drift.py`；`T5/T6` → `audit_meta.py`；
`doc_audit.py` 只留 `main()` 与报告打印（薄壳）。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

REPO_ROOT: Path = Path(__file__).resolve().parents[1]

RED, YELLOW, SKIP = "红", "黄", "忽略"

# --------------------------------------------------------------- 数据（可维护）

#: 已废除术语 → (缘由, 现在的正确说法)
#: ⚠️ 加条目要**依据一次真实的改名/删除**，别把「你觉得不好听」的词加进来。
RETIRED_TERMS: dict[str, tuple[str, str]] = {
    "pay_amount_src": ("字段已删（2026-09-16）", "金额只取 ApproveAmt；该列已取消"),
    "付款金额（源）": ("字段已取消（2026-09-16）", "三金额：审批金额 / 付款金额 / 已付金额"),
    "四金额": ("已改为三金额（2026-09-16）", "三金额"),
    "四个金额字段": ("已改为三个（2026-09-16）", "三个金额字段"),
    "print/sign.py": ("模块已删（2026-09-15）", "print/signatures.py"),
    "render.py::build_print_html": ("函数已删（2026-09-15）", "service.render_notice_html()"),
    "SOURCE_FIELDS": ("常量已删（2026-09-16）", "—"),
}

# ------------------------------------------------------------ 已撤项（`T8` 的真源）
#
# ⭐⭐ **「如何标记才能让人/AI 永久记住某功能已被取消？」—— 答案就是这张表。**
#
# ⚠️ 为什么不能只写注释：撤项目前散落在**代码注释**里（如 `shell/core.js` 那句
#    「⛔ 别再加回来」）—— 而**注释没人每次读** ⇒ 下次（包括 AI）照着一片**残骸**
#    把它再做一遍（本项目已发生过：`mod12_diff` 撤了、判据还在、目录还在、壳里还渲染）。
# ⭐ 本表的用法**不是"留个记录"**，而是**守卫**：`T8` 每次 `doc_audit` 跑批都扫**代码面**，
#    命中即报 —— 这才是"永久记住"（**机器每次把它端到你面前**，⛔ 不靠人记得）。
#
# 与 `RETIRED_TERMS` 的分工：
#   `RETIRED_TERMS` = 「**术语改名**」（扫 `.md` 文档，提示"该改叫 X"）；
#   本表           = 「**整个东西被撤了**」（扫**代码**，提示"不得复活 / 还有残骸"）。
#
# 形态：`标识符 → (理由＋依据, 正确的替代路径, 是否已清干净)`
#   ⭐ 第 3 项 `clean` 是关键：
#     · `True`  ⇒ 已清干净 ⇒ 再出现就报**红**（复活 = 真出错）
#     · `False` ⇒ 还有残骸   ⇒ 每次报**黄**（提醒"这里还留着，去清"）
#   ⇒ 这样机制**一上线就有区分力**，而且**立刻暴露所有残骸**（⛔ 不用先清完才能上线）。
CANCELLED: dict[str, tuple[str, str, bool]] = {
    # ⚠️⚠️ 用户 2026-09-20 裁定：**MOD-12「差异登记」整个页面取消**。
    #    依据 = §5.8.3 明写「差异归属恒为「**库存单据**」——**不独立成模块**」
    #    ⇒ 差异**从来不该有自己的页面**；它只是**调整单的产物**。
    "mod12_diff": ("已撤（2026-09-20 用户裁定）· §5.8.3「差异归属「库存单据」（**不独立成模块**）」",
                   "差异去**库存单据打调整单**（`API.m08Adjust`）；差异表由后端按调整单算（`m06`）", True),
    "m12List": ("同上 —— 这 4 个接口指向已撤的页", "`m08Adjust`（写调整单）＋ `m06` 的差异表（读）", True),
    "m12Create": ("同上", "`m08Adjust`", True),
    "m12Delete": ("同上", "调整单的撤销走 `m08` 自己的路", True),
    "m12Status": ("同上", "差异状态由调整单派生，⛔ 不单独存", True),
    # ⭐ 表 `diff_record` 也已按用户裁定 drop（迁移 `c9e5f1a3b7d2`）。
    #   ⚠️ 登记它**不是**为了"禁提这个名字"（迁移文件里必然还要写），
    #   而是提醒：**谁要是再建这张表 / 再给它配接口，就是复活已撤的页**。
    "diff_record": ("表已 drop（用户 2026-09-20 夜裁定）· 迁移 `c9e5f1a3b7d2`",
                    "⛔ 不重建：差异的载体是**调整单**（`m08`），产出是**差异表**（`m06` 按调整单算）", True),
    "m12Create": ("同上", "`m08Adjust`", False),
    "m12Delete": ("同上", "调整单的撤销走 `m08` 自己的路", False),
    "m12Status": ("同上", "差异状态由调整单派生，⛔ 不单独存", False),
}

#: `T8` 扫描面 —— **只扫代码**（文档面由 `T2`/`RETIRED_TERMS` 管）。
#: ⚠️ `demo/`（原型）**故意不在内** —— 原型是**历史留痕**，它留着 `V.m12` 是**正确的**。
#: ⚠️⚠️ **`backend/alembic/versions/` 也故意不在内** —— ⭐ 实测踩过：
#:   把迁移链扫进来后，**表名在迁移里出现是正常的**（`create_table` / `drop_table` 必然要写它），
#:   结果一条撤项登记凭空多出 **25 条黄**、还夹 1 条红（红在"新迁移的文件名"那句上）。
#:   ⇒ ⭐ **迁移链是"历史记录"，不是"复活"** ⇒ 本守卫⛔ 不扫它。
CANCELLED_SCAN_GLOBS: tuple[str, ...] = (
    "backend/app/**/*.py", "backend/app/**/*.js", "backend/app/**/*.html",
    "backend/tests/*.py", "tools/*.py",
)

#: `T8` 跳过本机制自己（这张表与它两个使用者**必然**要写出那些标识符）
CANCELLED_SKIP_RELS: tuple[str, ...] = (
    "tools/audit_common.py", "tools/audit_drift.py", "tools/doc_audit.py",
)

#: **强豁免**：行文本身就在声明「它废了 / 别再用」⇒ 直接忽略，连黄都不报
HARD_EXEMPT: tuple[str, ...] = (
    "已取消", "已作废", "已删除", "已废除", "已删", "取消「", "不再取", "不再用",
    "勘误", "旧术语", "别再引入", "不得再写",
)

#: **强豁免（模式版）** —— ⭐ 有些"它废了"的写法**中间会夹东西**，纯子串匹配会漏：
#:  ⚠️⚠️ **实测踩到（2026-09-20）**：`**已于 2026-09-20 删除**` ——
#:    「已」与「删」之间夹了日期 ⇒ `"已删" in text` **不成立** ⇒
#:    一条**完全正确、还写清了日期**的撤项说明被判**红** ✗
#:  ⭐ 而「写清哪天撤的」正是**最该鼓励**的写法 ⇒ 必须用**模式**匹配，⛔ 不能只比子串。
#:  ⚠️ 收紧边界（`[^，。；\n]{0,16}`）：只跨"日期 / 版本号"这类短插入，
#:    避免「已……删」跨半句话把正常行误豁免。
HARD_EXEMPT_RE: tuple[str, ...] = (
    r"已[^，。；\n]{0,16}(?:删|取消|作废|废除|撤|废)",
)

#: **弱豁免**：邻近出现 ⇒ 降黄（人看一眼）。豁免窗口 = 命中行 ±2 行
#: ⚠️ 只放**明确指向「这是旧写法 / 外部件」**的词 —— 「计划 / 拟 / 历史 / 留痕」太泛，
#:    放进来会把大片正常行误豁免（那类由 `LENIENT_GLOBS` 按文件管更准）。
SOFT_EXEMPT: tuple[str, ...] = (
    "原名", "原先", "（原", "原「", "改成", "改为", "改取", "更正", "曾",
    "非本工程", "素材包", "老工程", "_tmp_", "源文件",
)

#: 文件级「留痕」白名单（**相对两侧根的完整相对路径**，glob）—— 命中只报黄
#: ⚠️ 别写成 `plans/*.md` —— 实际相对名是 `.workbuddy/plans/…`，少前缀就不匹配（踩过一次）。
LENIENT_GLOBS: tuple[str, ...] = (
    # ⭐ 2026-09-17 起：`plans/` 里**只有两份活文档**（`开发计划-主文档.md` / `执行情况-主文档.md`，
    #    按**严格标准**查），其余一律 `归档-*`（只留痕）⇒ **一条 glob 覆盖全部归档件**。
    #    ⚠️ 别再逐份列（`2026-09-1[0-9]-*.md` / 各方案名）—— **逐份列 = 新归档件必然漏网**，
    #    这正是"计划文档悄悄过期却查不出来"的老路。
    #    ℹ️ `handoff/` 已于同日并入 `plans/`（history 条目 = `plans/归档-历史单元条目.md`）。
    ".workbuddy/plans/归档-*.md",
)

#: 合法的「幽灵用例号」—— 文档里明写「不建用例」的编号
KNOWN_ABSENT: frozenset[str] = frozenset({"ACC-X-ATT-001", "ACC-X-ATT-002"})

#: `T3` 只检查这些顶级目录开头的路径（`C:\…`、URL、SSH 一律不管）
TOP_DIRS: tuple[str, ...] = (
    "backend/", "tools/", "ops/", "demo/", "PRD/", "app/", "tests/",
    "alembic/", "artifacts/", "frontend/", "static/", "scripts/", "input/",
)

#: 治理目录下的**两份活文档**（2026-09-17 收敛：`.workbuddy/` 只留两份；2026-09-19 **换定位不换名**）
#: ⭐ 现分工：`开发计划-主文档.md` = **给 AI 的完整版**（规则 / 口径 / 台账 / 接手 / 闸门）；
#: `执行情况-主文档.md` = **给用户看的一页**（现状 / 下一步 / 要你做什么）。
#: ⚠️ `T4` 查**两份里所有**四态数字（2026-09-19 扩面，见 `audit_drift.check_status_line`）；
#: `T6` 查「计划」里的尾巴台账（§15）＋「简略版」里必须指向计划。
HANDBOOK_REL: str = ".workbuddy/plans/执行情况-主文档.md"

#: `T6` 尾巴台账（**唯一清点处** = 计划主文档 §15）—— 尾巴的单一清点处
LEDGER_REL: str = ".workbuddy/plans/开发计划-主文档.md"
LEDGER_NAME: str = "开发计划-主文档"
TAIL_MIN_CELLS: int = 6          # 表格行去掉首尾竖线后的最少格数（栏位齐全 = 含**落点** ＋ **阶段**）

#: `T6` 尾巴的**阶段受控词** —— 尾巴一登记就必须回答"在哪个阶段处理"（2026-09-17 用户裁定：
#: 「尾巴不能就简单地进总计划，肯定要分析尾巴合适在什么阶段处理」）。
#: ⭐ **只登记、不排期 ⇒ 判红**；能通过 = 这条尾巴的时机已经想清楚了。
TAIL_STAGE_RE = re.compile(r"^(?:M[0-8]|立刻|持续|随时|已做|已完成)")

#: `T6` 排期表（§14.3）—— 每条尾巴的编号必须在那里也有一行（**登记即排期**，两处一致）
TAIL_SCHEDULE_RE = re.compile(r"^#{2,3}\s*[\d.]*\s*逐条排期")

#: 路径解析时依次尝试的前缀（文档常省略 `backend/`）
PATH_ROOTS: tuple[str, ...] = ("", "backend/", "backend/app/")

SCAN_GLOBS: tuple[str, ...] = (
    "README.md", "ops/*.md", ".workbuddy/plans/*.md",
    ".workbuddy/memory/MEMORY.md", ".workbuddy/memory/CHANGELOG.md",
)
DELIVERY_GLOBS: tuple[str, ...] = (
    "*.md", "PRD/*.md", "PRD/*/*.md", "demo/*.md", "demo/*/*.md",
)

_ACC_RE = re.compile(r"ACC-[A-Z0-9]+(?:-[A-Z0-9]+)*")
_ACC_ID_RE = re.compile(r"^ACC-[A-Z0-9]+(?:-[A-Z0-9]+)*-\d{3}$")
_PATH_RE = re.compile(r"`([A-Za-z0-9_][A-Za-z0-9_./\\-]*\.[A-Za-z0-9]{1,5})`")
_PLACEHOLDER = re.compile(r"[*<>{}]|YYYY|MM|DD|\bX\b")
_ZONE_RE = re.compile(r"<!--\s*doc_audit:(current|history)\s*-->")
#: ⚠️ 只匹配**四态本身**，不要求 `四态 **N =` 这种前缀 —— 文件里的写法是
#: `四态 **绿 171 · 红 0 · 待建 16 · 未绑定 131**（合计 **318**）`，前缀形态并不固定。
#: （踩过一次：原正则带前缀 ⇒ 认不出 ⇒ **静默跳过**，把"改错了"读成"通过"。）
_STATUS_RE = re.compile(
    r"绿\s*(\d+)\s*·\s*红\s*(\d+)\s*·\s*待建\s*(\d+)\s*·\s*未绑定\s*(\d+)"
)


# ------------------------------------------------------------------ 基础设施


def read_env(key: str) -> str:
    f = REPO_ROOT / ".env"
    if not f.exists():
        return ""
    for line in f.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return ""


def delivery_root() -> Path | None:
    """交付面根 = `.env` 里 `PRD_ACCEPTANCE_BASELINE`（…/PRD/验收/验收基线.json）上溯两级。"""
    p = read_env("PRD_ACCEPTANCE_BASELINE")
    return Path(p).resolve().parents[2] if p else None


def _is_lenient(rel: str) -> bool:
    from fnmatch import fnmatch
    return any(fnmatch(rel, g) for g in LENIENT_GLOBS)


def iter_docs() -> list[tuple[str, str, Path, list[str], list[str]]]:
    """→ [(侧, 相对名, 路径, 行, 每行所属区)]；区 = `current` / `history`。"""
    out = []
    seen: set[Path] = set()
    plan: list[tuple[str, Path, str]] = []
    for pat in SCAN_GLOBS:
        for p in sorted(REPO_ROOT.glob(pat)):
            if p.is_file() and p.suffix == ".md" and p not in seen:
                seen.add(p)
                plan.append(("仓", p, str(p.relative_to(REPO_ROOT))))
    root = delivery_root()
    if root:
        for pat in DELIVERY_GLOBS:
            for p in sorted(root.glob(pat)):
                if p.is_file() and p not in seen:
                    seen.add(p)
                    plan.append(("面", p, str(p.relative_to(root))))
    for side, p, rel in plan:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        zone, zones = "current", []
        for l in lines:
            m = _ZONE_RE.search(l)
            if m:
                zone = m.group(1)
            zones.append(zone)
        out.append((side, rel, p, lines, zones))
    return out


def _near(lines: list[str], i: int, n: int = 1) -> str:
    """命中行 ±n 行的合并文本（豁免判定用 —— 勘误常写在下一行）。"""
    lo, hi = max(0, i - n), min(len(lines), i + n + 1)
    return "\n".join(lines[lo:hi])


def _verdict(near: str, lenient: bool) -> str:
    """返回 RED / YELLOW / SKIP（`near` = 命中行 ±2 行）。

    ⚠️ 强豁免查**两遍**：先子串（`HARD_EXEMPT`）、再**模式**（`HARD_EXEMPT_RE`）——
       后者兜「已**于 <日期>** 删除」这类**中间夹了东西**的正确写法（见该常量注释）。
    """
    if any(w in near for w in HARD_EXEMPT):
        return SKIP
    if any(re.search(p, near) for p in HARD_EXEMPT_RE):
        return SKIP
    if lenient or any(w in near for w in SOFT_EXEMPT):
        return YELLOW
    return RED


def _hit(code, side, rel, path, i, lines, zones, *, what, why, fix) -> dict:
    line = lines[i].strip()
    lenient = _is_lenient(rel) or zones[i] == "history"
    return {"code": code, "side": side, "rel": rel, "line": i + 1,
            "what": what, "why": why, "fix": fix, "text": line,
            "level": _verdict(_near(lines, i, 2), lenient)}
