"""⭐ `TAIL-193` · **防扩散墓碑**：这几件事在本仓**已经有唯一出口**（或本该有），⛔ 不许再长第 N+1 份实现。

**为什么需要这一条**（落自 2026-09-29 结构审计 §三 `P1-5`）：同一件事**多份实现并存**是最贵的一类债 ——
改一处口径、另一处**静默不一致**。本仓真例：`amount_text` 那段原先在 **4 个 `parse_amount`** 里
各写一份、**且写得不一样** ⇒ 同一个 `¥ 1,234.56`：集采 / 特殊费用 / 付款流水都能过，
**付款通知书手填却被拒**（它那份只去逗号）。

⭐⭐ **本件的立场（照 `TAIL-193` 的裁定）：只防新增，⛔ 不动存量。**
存量不批量替换的硬理由：① 本仓已**实测两次**「抽通用件 ⇒ 钉源码形态的判据假红」；
② 这些副本的**判定口径刻意不同**（`MOD-09` 允许 0 与负数、`MOD-11` 必须 > 0 —— 两边注释都写着
「别把两套搅在一起」）⇒ 拍平成一处**会改业务行为**。

**登记册 = 本文件里的 `DUP_FAMILIES`（唯一主人）**：
- `pattern` **只匹配函数定义行**（⛔ 不扫调用点 —— 那会一片假阳性）；
- `copies` = **存量的 (文件, 函数名)**，逐条来自 `tools/oneoff/_tail193_measure.py` 的实测（2026-09-29）；
- `owner_files` = 唯一出口所在的件（它里面的函数**不算副本**，进族也不影响判据）；
- `forward_files` = **已经是薄转发**的（它照着出口做，本身不是第二份实现）；
- ⭐ **两半判据**：多一处 ⇒ 红（别再写第 N+1 份）；**少一处 ⇒ 也红**（那是**好方向** ⇒
  把登记册那一行删掉并在这里记一笔 —— ⛔ 别让登记册烂成「过去曾有过什么」）。

⚠️ 本件**刻意不绑契约面**（`@acc()` 空参 = 显式不绑定）：它守的是**工程侧可维护性**，
不对应任何「用户看得见的行为」（口径同 `TAIL-167` 的裁定）。

⚠️ **与审计件的一处口径差异**（如实记下）：审计件 §三 `P1-5` 列的计数是**正则扫更宽的面**得到的
（金额解析 6 / 格式化 9 / 项目 6 / 日期 8+ / 仓库名 4），本件按**函数定义名**重测，得到的是
**5 / 8 / 2 / 4 / 3**（明细见各族 `copies`）；另：审计件那句「**仓库名校验/排序 4 处**」实测对不上 ——
那一族的真身是 **4 个 `_norm`（文本归一）**（其中 `recovery.py` 那个已是转发）⇒ 本件按实测命名。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from tests.acc_plugin import acc

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "backend" / "app"


@dataclass(frozen=True)
class DupFamily:
    """一族「同一件事的多份实现」。"""

    fam: str
    owner: str
    pattern: str
    copies: tuple[tuple[str, str], ...]
    owner_files: tuple[str, ...] = ()
    forward_files: tuple[str, ...] = field(default=())


DUP_FAMILIES: tuple[DupFamily, ...] = (
    DupFamily(
        fam="金额·解析 / 归一",
        owner="`core/money.py` 的 `to_money()`（洗净走 `amount_text()`）",
        pattern=r"^def (parse_amount|_parse_amount|to_amount|_amount_key)\s*\(",
        owner_files=("backend/app/core/money.py",),
        copies=(
            ("backend/app/mod03_notice/notice_pay_actions.py", "parse_amount"),
            ("backend/app/mod09_fee/domain.py", "parse_amount"),
            ("backend/app/mod11_jc/domain.py", "parse_amount"),
        ),
    ),
    DupFamily(
        fam="金额·格式化（给人看的串）",
        owner="**（暂无唯一出口）** —— `core/money.py` 只管数值口径，这一族还没有主人",
        pattern=r"^def (_money|money_text|fmt_num|norm_num|_money_or_none)\s*\(",
        copies=(
            ("backend/app/mod06_proc/importer.py", "_money_or_none"),
            ("backend/app/mod08_inv/router.py", "_money"),
            ("backend/app/mod09_fee/domain.py", "money_text"),
            ("backend/app/report_export/fl_export.py", "_money"),
            ("backend/app/report_export/jc_export.py", "_money"),
            ("backend/app/report_export/setl_export.py", "fmt_num"),
            ("backend/app/report_export/xl_common.py", "fmt_num"),
            ("backend/app/report_export/xl_common.py", "norm_num"),
        ),
    ),
    DupFamily(
        fam="项目·把名字对上项目",
        owner="**（暂无唯一出口）** —— `core/projects.py` 只有 键 / 显示名，没有匹配",
        pattern=r"^def (match_project|match_projects)\s*\(",
        copies=(
            ("backend/app/mod04_plan/domain.py", "match_project"),
            ("backend/app/mod11_jc/fetch_service.py", "match_projects"),
        ),
    ),
    DupFamily(
        fam="时间·年月",
        owner="`core/timing.py`",
        pattern=r"^def (parse_ym|ym_of|shift_ym|month_range_closed|ym_to_closed_range"
                r"|default_ym_payment|default_ym_report|norm_pay_date|normalize_ym)\s*\(",
        owner_files=("backend/app/core/timing.py",),
        copies=(
            ("backend/app/mod06_proc/domain.py", "normalize_ym"),
            ("backend/app/mod06_proc/importer.py", "ym_of"),
            ("backend/app/mod09_fee/domain.py", "parse_ym"),
        ),
    ),
    DupFamily(
        fam="文本归一（做比较键用）",
        owner="`import_kit/mapping.py::normalize`（列名）／ `mod01_projects/domain.py::norm_full_name`（项目全名）",
        pattern=r"^def (_norm)\s*\(",
        forward_files=("backend/app/mod01_projects/recovery.py",),
        copies=(
            ("backend/app/mod06_proc/importer.py", "_norm"),
            ("backend/app/mod07_setl/importer.py", "_norm"),
            ("backend/app/mod08_inv/importer.py", "_norm"),
        ),
    ),
)


def _scan() -> dict[str, set[tuple[str, str]]]:
    """按族扫 `backend/app/**/*.py`（⛔ 不含 tests / tools）：命中 = **函数定义行**。

    ⚠️ 每条 `pattern` **必须有一个捕获组 = 函数名**（下面显式校验 —— 少了它就变成一条**哑判据**）。
    """
    for f in DUP_FAMILIES:
        if re.compile(f.pattern).groups != 1:
            raise AssertionError(f"「{f.fam}」的 pattern 必须恰好有一个捕获组（函数名）：{f.pattern}")
    out: dict[str, set[tuple[str, str]]] = {}
    for f in DUP_FAMILIES:
        rx = re.compile(f.pattern)
        skip = set(f.owner_files) | set(f.forward_files)
        hits: set[tuple[str, str]] = set()
        for p in sorted(APP.rglob("*.py")):
            rel = p.relative_to(ROOT).as_posix()
            if rel in skip:
                continue
            for line in p.read_text(encoding="utf-8").splitlines():
                m = rx.match(line)
                if m:
                    hits.add((rel, m.group(1)))
        out[f.fam] = hits
    return out


def _fmt(rows) -> str:
    return " · ".join(f"{rel}::def {fn}" for rel, fn in sorted(rows))


@acc()
def test_不许再长第N加1份实现():
    """⭐ 防扩散的正半：出现**登记册之外**的实现 ⇒ 红（去用唯一出口）。"""
    actual = _scan()
    problems: list[str] = []
    for f in DUP_FAMILIES:
        extra = actual[f.fam] - set(f.copies)
        if extra:
            problems.append(f"⚠️ 「{f.fam}」多了新的一份实现：{_fmt(extra)} ⇒ 改用唯一出口（{f.owner}）")
    assert not problems, "\n".join(problems)


@acc()
def test_登记册与现实同步_消掉副本要销号():
    """⭐ 反半：**少一处 = 好方向** —— 但登记册必须同步（⛔ 别让它成为"过去曾有过什么"）。"""
    actual = _scan()
    problems: list[str] = []
    for f in DUP_FAMILIES:
        gone = set(f.copies) - actual[f.fam]
        if gone:
            problems.append(
                f"✅ 「{f.fam}」已经被消掉了这些副本：{_fmt(gone)}"
                " ⇒ 这是好方向：把 `DUP_FAMILIES` 里对应那几行删掉，并在这里（或台账）记一笔"
            )
    assert not problems, "\n".join(problems)
