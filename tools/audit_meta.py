#!/usr/bin/env python
"""`doc_audit` 台账与行数检查 —— `T5` 单文件行数纪律 · `T6` 尾巴台账（计划主文档 §15）。

⚠️ **纯搬运**（自 `doc_audit.py` 拆出，无逻辑改动）。常量见 `audit_common.py`。
"""

from __future__ import annotations

import re

from audit_common import (
    HANDBOOK_REL, LEDGER_NAME, LEDGER_REL, RED, REPO_ROOT, TAIL_MIN_CELLS,
    TAIL_SCHEDULE_RE, TAIL_STAGE_RE, YELLOW,
)

# ------------------------------------------------- T5 单文件 >400 行是否已登记

#: 工程纪律（`MEMORY.md` §八）：单文件 >400 行**必须登记拆分计划**（>600 禁合入）
LINE_LIMIT, HARD_LIMIT = 400, 600
CODE_DIRS: tuple[str, ...] = ("backend/app", "backend/tests", "tools")


def check_file_sizes() -> list[dict]:
    """`T5` · 单文件行数纪律：**>400 须登记拆分计划**（黄）· **>600 禁合入**（红）。

    ⚠️ **清单不抄进 `MEMORY.md`** —— 抄一份必然过期（实测：§八 手抄了 4 个，实际有 9 个）。
    ⇒ **本函数的输出就是那份清单**；文档只留纪律，不留名单（这正是「状态由机器生成」）。
    """
    hits: list[dict] = []
    for d in CODE_DIRS:
        for f in sorted((REPO_ROOT / d).rglob("*.py")):
            n = len(f.read_text(encoding="utf-8", errors="replace").splitlines())
            if n <= LINE_LIMIT:
                continue
            rel = str(f.relative_to(REPO_ROOT)).replace("\\", "/")
            over_max = n > HARD_LIMIT
            hits.append({"code": "T5", "side": "仓", "rel": rel, "line": 1,
                         "what": f"{n} 行",
                         "why": (f"超过硬上限 {HARD_LIMIT} 行 —— **禁合入**" if over_max
                                 else f"超过 {LINE_LIMIT} 行 —— 须登记拆分计划"),
                         "fix": ("同一单元内拆分后复跑四态全绿" if over_max
                                 else "登记拆分计划（清单以本工具输出为准，别抄进文档）"),
                         "level": RED if over_max else YELLOW, "text": ""})
    return hits


# ---------------------------------------------------------------- T6 尾巴台账


def _t6(rel: str, lineno: int, what: str, why: str, fix: str, text: str = "") -> dict:
    return {"code": "T6", "side": "仓", "rel": rel, "line": lineno,
            "what": what, "why": why, "fix": fix, "level": RED, "text": text}


def check_tail_ledger(cases: set[str]) -> list[dict]:
    """`T6` · **尾巴台账**（唯一清点处 = 计划主文档 `§15`）—— 尾巴必须有单一清点处。

    为什么单独立一条：执行情况只保留「当前这一件事 ＋ 少量最相关的 ⏳」，旧尾巴会被一轮轮顶下去，
    对话汇报会被冲走、`memory` 日志没人回头读 ⇒ **"一直跟着下一步走"时尾巴会永远悬着**。
    ⇒ 台账 + 本条检查 = 尾巴有落点、且**每轮非过不可**。

    七查：① 台账在、且**执行情况的 §③ 必读清单里可达**（否则新会话根本读不到）② 每条**栏位齐全（含落点）**
    ③ 编号唯一且 `1..N` **顺延不跳号**（销号不释放编号）④ 落点引用的 `ACC-*` **真实存在**
    ⑤ ⭐ **每条必须有「阶段 / 时机」**且是**受控词**（`M0`–`M8` / 立刻 / 持续 / 随时）—— **只登记不排期即判红**
    ⑥ ⭐ 每条编号**必须能在 §14.3 排期表里找到**（**登记即排期**，两处一致）⑦ 顶部「当前状态」计数**与实际条数一致**。

    ⚠️ **2026-09-17 起台账并入计划 `§15`**：段标题由 `## 一、…` 变成 `### 一、…`（层级降一级），
       故段落识别改成**认中文数字**而不是「第 4 个字符」，`##`/`###` 都收。
    ⚠️ **⑤⑥ 是同日用户裁定的产物**：「尾巴不能就简单地进总计划，肯定要分析尾巴合适在什么阶段处理」
       —— 原台账只有「落点」（谁在哪做），没有「阶段」（什么时候做）⇒ 尾巴可能永远悬着。
    """
    hits: list[dict] = []
    path = REPO_ROOT / LEDGER_REL
    if not path.exists():
        return [_t6(LEDGER_REL, 1, "台账（计划主文档）不存在",
                    "尾巴没有单一清点处 ⇒ 会一轮轮掉队",
                    f"创建 {LEDGER_REL}（含 §15 尾巴台账：A/B/C/已销号 四段）")]

    handbook = REPO_ROOT / HANDBOOK_REL
    hand_text = handbook.read_text(encoding="utf-8", errors="replace") if handbook.exists() else ""
    # ⚠️ **2026-09-19 改落点**：原来查「简略版 §③ 必读清单里有没有计划名」—— 但简略版已改成
    #    **给用户看的一页**（不再有 AI 侧的 §③ 必读清单；那份清单搬进了计划 §21.3）。
    #    ⇒ 现在只要求：**简略版里必须指向计划**（它是人/新会话读到的第一份，必须能把人引到台账）。
    #    ⛔ 别退回「不检查」：台账没人指着 = 没人看的文件（这正是本条存在的理由）。
    if LEDGER_NAME not in hand_text:
        hits.append(_t6(HANDBOOK_REL, 1,
                        f"简略版里没有指向「{LEDGER_NAME}」",
                        "人/新会话先读简略版 ⇒ 读不到台账，台账就成了没人看的文件",
                        "在简略版顶部写一句「完整工程台账见 开发计划-主文档.md」"))

    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    # ⚠️ **只扫「尾巴台账」那一段** —— 台账已并入计划（整份计划里还有大量别的表格，
    #    不分段就会把它们的行也当成台账条目 ⇒ 满屏"栏位不全"的假红）。段的起点认标题文字。
    start = next((k for k, l in enumerate(lines)
                  if re.match(r"^#{2,3}\s*[\d.]*\s*尾巴台账", l.strip())), None)
    if start is None:
        hits.append(_t6(LEDGER_REL, 1, "找不到「尾巴台账」段（计划 §15）",
                        "台账被删/被改名 ⇒ 尾巴没有单一清点处",
                        "在计划里恢复 `## 15. 尾巴台账`（含 A/B/C/已销号 四段 + 计数行）"))
        return hits
    end = next((k for k in range(start + 1, len(lines)) if lines[k].startswith("## ")), len(lines))
    lines = lines[start:end]
    offset = start

    section = ""
    ids: dict[str, int] = {}          # 编号 → 行号（重复即红）
    live: set[str] = set()            # 一/二/三 段的编号（**未销号** —— 要和排期表对齐的就是它们）
    hdr: dict[str, list[str]] = {}    # 段号 → 表头栏位名（「阶段 / 时机」靠它定位）
    per_section: dict[str, int] = {}
    for i, raw in enumerate(lines):
        line = raw.strip()
        # ⚠️ 段落 = `##` / `###` ＋ 中文数字（台账并入计划后层级降了一级）
        m_sec = re.match(r"^#{2,3}\s*([一二三四])\s*[、.]", line)
        if m_sec:
            section = m_sec.group(1)
            continue
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        first = cells[0] if cells else ""
        if first == "#":
            hdr[section] = cells      # 表头 ⇒ 记下栏位顺序（找「阶段 / 时机」用）
            continue
        if not first or set(first) <= {"-", ":"}:
            continue                  # 分隔行 / 空行
        per_section[section] = per_section.get(section, 0) + 1
        # ⭐ **编号只认「第一格」** —— 正文里交叉引用 `TAIL-10`（如"依赖 TAIL-10"）不算重复定义
        m_id = re.match(r"`?(TAIL-(\d+))`?", first)
        if m_id:
            n = m_id.group(2)
            if n in ids:
                hits.append(_t6(LEDGER_REL, offset + i + 1,
                                f"编号 TAIL-{n} 重复（另一处在第 {ids[n]} 行）",
                                "编号重复 ⇒ 销号/引用会对错条目", "顺延取新号，不重用"))
            ids[n] = offset + i + 1
            if section in ("一", "二", "三"):
                live.add(n)
        # 栏位齐全：**尾巴（一/二/三）必须有落点** —— 那是"谁在哪做"；
        # 已销号（四）只要求四格（编号 / 事项 / 销号依据 / 日期）。
        need = TAIL_MIN_CELLS if section in ("一", "二", "三") else 4
        if len(cells) < need or any(not c for c in cells):
            hits.append(_t6(LEDGER_REL, offset + i + 1, f"栏位不全（{len(cells)} 格，需 ≥{need}）",
                            "有空格 ⇒ 多半是**没写落点**", "补齐：来源 / 落点 / 状态 都要有值"))
        for acc in re.findall(r"ACC-[A-Z0-9\-]+", line):
            if acc not in cases:
                hits.append(_t6(LEDGER_REL, offset + i + 1, f"落点引用的用例号不存在：{acc}",
                                "落点写了幽灵 ⇒ 这条尾巴没人接", "改成真实用例号，或写清归属单元"))
        # ⭐ **阶段受控词**（用户 2026-09-17 裁定：尾巴不能只登记、必须分析在哪个阶段处理）
        if section in ("一", "二", "三"):
            cols = hdr.get(section, [])
            si = next((k for k, c in enumerate(cols) if "阶段" in c or "时机" in c), None)
            if si is None:
                hits.append(_t6(LEDGER_REL, offset + i + 1,
                                f"「{section}」段表头缺「阶段 / 时机」栏",
                                "只有落点、没有阶段 ⇒ 尾巴永远悬着、或在错误时机插队",
                                "表头加一栏「阶段 / 时机」，值取受控词 `M0`–`M8` / 立刻 / 持续 / 随时"))
            else:
                val = cells[si] if si < len(cells) else ""
                if not TAIL_STAGE_RE.match(val):
                    hits.append(_t6(LEDGER_REL, offset + i + 1,
                                    f"{first} 的「阶段」不是受控词：{val or '（空）'}",
                                    "说不清在哪个阶段处理 ⇒ 这条尾巴还没想清楚（只登记未排期）",
                                    "填 `M0`–`M8` 之一 / `立刻` / `持续` / `随时`，并回 §14.3 补一行"))

    nums = sorted(int(n) for n in ids)
    if nums and nums != list(range(1, len(nums) + 1)):
        hits.append(_t6(LEDGER_REL, offset + 1, f"编号不连续：{nums}",
                        "跳号 ⇒ 看不出有没有被静默删过", "编号**顺延**；销号也**不释放**编号"))

    # ⭐ **登记即排期**：未销号的每条必须能在 §14.3「逐条排期」里找到（两处不一致即红）
    full = path.read_text(encoding="utf-8", errors="replace").splitlines()
    si = next((k for k, l in enumerate(full) if TAIL_SCHEDULE_RE.match(l.strip())), None)
    if si is None:
        hits.append(_t6(LEDGER_REL, 1, "找不到 §14.3「逐条排期」表",
                        "排期表没了 ⇒ 「阶段」栏失去对照物，尾巴的时机无从追溯",
                        "在 §14 恢复 `### 14.3 逐条排期`（含「建议时机 / 理由 / 前置」三栏）"))
    else:
        sched: set[str] = set()
        for l in full[si:]:
            if l.startswith("## "):
                break
            m_row = re.match(r"^\|\s*`?TAIL-(\d+)`?", l.strip())
            if m_row:
                sched.add(m_row.group(1))
        for n in sorted(live, key=int):
            if n not in sched:
                hits.append(_t6(LEDGER_REL, 1,
                                f"TAIL-{n} 登记了但没在 §14.3 排期表里",
                                "只登记、不排期 ⇒ 没人知道它该在哪个阶段做（**正是用户点出的病**）",
                                "在 §14.3 补一行（写清四问理由与前置），使其与「阶段」栏一致"))
        for n in sorted(sched - live - set(ids), key=int):
            hits.append(_t6(LEDGER_REL, 1,
                            f"§14.3 排期表里的 TAIL-{n} 在台账里不存在",
                            "排期表留了个幽灵编号 ⇒ 两份清单已经分叉",
                            "删掉该行，或补进台账 §一/§二/§三"))

    counts = {k: per_section.get(k, 0) for k in ("一", "二", "三")}
    counts["四"] = per_section.get("四", 0)
    m = re.search(r"A 类 \*\*(\d+)\*\* 条 · B 类 \*\*(\d+)\*\* 条 · C 类 \*\*(\d+)\*\* 条"
                  r" · 已销号 \*\*(\d+)\*\* 条", "\n".join(lines))
    if not m:
        hits.append(_t6(LEDGER_REL, 1, "找不到顶部的「当前状态」计数行",
                        "没有计数就没法一眼看出尾巴有没有在涨", "补一行：A 类 **n** 条 · B 类 … "))
    else:
        got = tuple(int(x) for x in m.groups())
        want = (counts["一"], counts["二"], counts["三"], counts["四"])
        if got != want:
            hits.append(_t6(LEDGER_REL, 1, f"计数与实际不符：写的 {got}，实际 {want}",
                            "计数漂了 ⇒ 人会按错的数判断", "按实际条数改这一行（机器核对）"))
    return hits
