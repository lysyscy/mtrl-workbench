#!/usr/bin/env python
"""`doc_audit` 台账与行数检查 —— `T5` 单文件行数纪律 · `T6` 尾巴台账（计划主文档 §15）。

⚠️ **纯搬运**（自 `doc_audit.py` 拆出，无逻辑改动）。常量见 `audit_common.py`。
"""

from __future__ import annotations

import re
import sys
import tokenize
from pathlib import Path

from audit_common import (
    HANDBOOK_REL, LEDGER_NAME, LEDGER_REL, LENIENT_GLOBS, LIVE_MACHINE_GLOBS, RED, REPO_ROOT,
    SCAN_GLOBS, TAIL_MIN_CELLS, TAIL_SCHEDULE_RE, TAIL_STAGE_RE, YELLOW, delivery_root, read_counts,
    DOC_SUFFIXES, ROOT_ALLOW, GITIGNORE_REL,
)

# ------------------------------------------------- T5 单文件 >400 行是否已登记

#: 阈值出处 = `ops/阈值表.md`（**唯一一处集中登记**）。
#: ⭐ 2026-09-21 **用户裁定：`>600` 从「红 · 禁合入」降为「黄」** ——
#:    理由：行数是**代理指标**（700 行的扁平查表好过 300 行的三层回调）；它对「我整份读文件」
#:    这件事有护栏价值，但作为**禁合入的闸门过度**。⚠️ 保留为**黄** ≠ 不用管：>600 仍要
#:    **登记「为什么不拆」的理由**（在 `ops/阈值表.md` 那张表里给一行）。
LINE_LIMIT, HARD_LIMIT = 400, 600
CODE_DIRS: tuple[str, ...] = ("backend/app", "backend/tests", "tools")
#: `T5` 的"登记处"（>600 时说明"为什么不拆"）
THRESHOLD_DOC = "ops/阈值表.md"


def check_file_sizes() -> list[dict]:
    """`T5` · 单文件行数纪律：**>400 须登记拆分计划**（黄）· **>600 须登记"为什么不拆"**（黄）。

    ⚠️ **清单不抄进 `MEMORY.md`** —— 抄一份必然过期（实测：§八 手抄了 4 个，实际有 9 个）。
    ⇒ **本函数的输出就是那份清单**；文档只留纪律，不留名单（这正是「状态由机器生成」）。
    ⚠️ **`>600` 不再是红**（2026-09-21 用户裁定降级）：它**不挡合入**，但仍要求一条登记。
    ⛔ 别把这条悄悄改回红 —— 要改先改 `ops/阈值表.md` 里那一行（那里写着出处与理由）。

    ⭐⭐ 2026-09-29 **补第二半**（`TAIL-06` 的量测逼出来的）：**`>600` 的件必须在阈值表里被"点名"**。
      原先只报「超线 ⇒ 须登记」，⚠️ **却不核"那张表里到底有没有这一件"** ⇒ 实测当场对不上：
      阈值表写着「**现唯一超线件 = `mod11_jc/repository.py`（605 行）**」，而实际是 **5 件**
      （`audit_meta.py` **811** · `_shell_legacy.py` **809** · `mod06_proc/importer.py` **668** ·
      `mod11_jc/repository.py` **646** · `_shell_smoke.py` **650**）⇒ 又一个「**口径要求一件事、
      机器只看一半**」（同 `TAIL-59` 的病）。
    ⚠️ **认法 = 文件名出现即可**（黄档 · 不追求精确到行）；表不存在时本半**不判**（那是 `T18` 的事）。
    ⚠️⚠️ **它的边界（实测踩到，⛔ 别高估它）**：认法是"**文件名在表里任意位置出现过**" ⇒ **历史叙述里的
      旧名也算数**（`M16` 第一版就踩到：抹掉 `_shell_smoke.py` 的登记处、它在那句"（旧登记 = …671 行）"
      里仍被提到 ⇒ 判据**不报**）。⇒ 它挡的是「**完全没提**」这一档；⛔ **不区分"在哪个场合提的"**。
    """
    hits: list[dict] = []
    table = REPO_ROOT / THRESHOLD_DOC
    reg_text = table.read_text(encoding="utf-8", errors="replace") if table.exists() else ""
    for d in CODE_DIRS:
        for f in sorted((REPO_ROOT / d).rglob("*.py")):
            n = len(f.read_text(encoding="utf-8", errors="replace").splitlines())
            if n <= LINE_LIMIT:
                continue
            rel = str(f.relative_to(REPO_ROOT)).replace("\\", "/")
            over_max = n > HARD_LIMIT
            if over_max and reg_text and f.name not in reg_text:
                hits.append({"code": "T5", "side": "仓", "rel": rel, "line": 1,
                             "what": f"{n} 行 · ⚠️ **阈值表没点名本件**",
                             "why": f"超过 {HARD_LIMIT} 行 ⇒ 按口径必须在 `{THRESHOLD_DOC}` 登记"
                                    "**为什么不拆**，而那张表里**找不到本件的文件名** ⇒"
                                    "「口径有要求、机器只看一半」（2026-09-29 `TAIL-06` 实测：表里写"
                                    "「唯一超线件」而实际 5 件）",
                             "fix": f"在 `{THRESHOLD_DOC}` 的 **600** 那一行**点名本件** ＋ 一句"
                                    "「为什么不拆」（或真的拆开、复跑四态全绿）",
                             "level": YELLOW, "text": ""})
                continue
            hits.append({"code": "T5", "side": "仓", "rel": rel, "line": 1,
                         "what": f"{n} 行",
                         "why": (f"超过 {HARD_LIMIT} 行 —— 须在 `{THRESHOLD_DOC}` 登记"
                                 "**为什么不拆**（行数是代理指标，不作禁合入闸门）" if over_max
                                 else f"超过 {LINE_LIMIT} 行 —— 须登记拆分计划"),
                         "fix": (f"在 `{THRESHOLD_DOC}` 写一行理由（或真的拆开、复跑四态全绿）"
                                 if over_max
                                 else "登记拆分计划（清单以本工具输出为准，别抄进文档）"),
                         "level": YELLOW, "text": ""})
    return hits


# ------------------------------------------------- T9 纪律的「口径出处」标记


#: `T9` 认的三种标记（写在条目行内，可带后缀如 `[用户·2026-09-21]`）
RULE_ORIGINS: tuple[str, ...] = ("[用户", "[交付面", "[助手自定")
RULE_DOC_REL = ".codebuddy/memory/MEMORY.md"
RULE_SECTION_RE = re.compile(r"^##\s*八[、.]\s*工程纪律")


def _t9(lineno: int, what: str, why: str, fix: str, text: str = "") -> dict:
    return {"code": "T9", "side": "仓", "rel": RULE_DOC_REL, "line": lineno,
            "what": what, "why": why, "fix": fix, "level": RED, "text": text}


def check_rule_origins() -> list[dict]:
    """`T9` · **纪律的「口径出处」标记**（2026-09-21 用户裁定「加」）——
    `MEMORY.md` §八「工程纪律」的**每一条**都必须带一个出处标记。

    ⭐⭐ 为什么必须有这条（本仓 2026-09-21 审计**当场查到一次腐化**）：
       纪律册里混着两类东西 —— **用户的裁定** 与 **我自己加的工程习惯**。那天 §八 写着
       「每轮收尾**提交 ＋ 推送**」，而用户当天定的是「**先不提交，继续攒**」⇒ 两条**直接对立**，
       而**没有任何尺子在看 `MEMORY.md`**（`claim_audit` 只扫两份活文档）。
       ⚠️ 教训：**自定纪律比文档更危险** —— 文档只是描述，**纪律是指令，我每轮照着做**。

    标记三选一：`[用户]` / `[交付面]` / `[助手自定]`（可带后缀）。
    ⚠️ `[助手自定]` = **尚未经用户裁定** ⇒ 用户随时可以"改/撤"（这正是要标出来的原因）。
    """
    hits: list[dict] = []
    path = REPO_ROOT / RULE_DOC_REL
    if not path.exists():
        return [_t9(1, "找不到纪律册", f"{RULE_DOC_REL} 不存在 ⇒ 纪律没有集中锚点",
                    "恢复它（§八 工程纪律 ＋ 其余各节）")]
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    start = next((k for k, l in enumerate(lines) if RULE_SECTION_RE.match(l.strip())), None)
    if start is None:
        return [_t9(1, "找不到「八、工程纪律」段",
                    "段被删/改名 ⇒ `T9` 失去对照物（⛔ 别改名，改名要同步改本函数）",
                    "恢复 `## 八、工程纪律` 段（每条一行，行内带出处标记）")]
    end = next((k for k in range(start + 1, len(lines)) if lines[k].startswith("## ")), len(lines))
    rules = 0
    for k in range(start + 1, end):
        s = lines[k].strip()
        if not s.startswith("- "):
            continue                      # ⚠️ 只认条目行；小标题/引用块不算纪律
        rules += 1
        if not any(o in s for o in RULE_ORIGINS):
            hits.append(_t9(k + 1, "这条纪律没标「口径出处」",
                            "分不清是**用户定的**还是**我自定的** ⇒ 自定规则会静默腐化"
                            "（2026-09-21 实测过一次：与用户裁定直接对立而无人发现）",
                            "行首加 `[用户]` / `[交付面]` / `[助手自定]` 之一", text=s))
    if rules == 0:
        hits.append(_t9(start + 1, "§八 里一条纪律都没有",
                        "纪律册空着 ⇒ 要么真没有纪律（那也该写明），要么被误删",
                        "补上纪律条目（每条一行，行内带出处标记）"))
    return hits


#: `T9` ② 认的形态：**尺子名紧跟括号、括号里带数字**（实测咬人的样子 =
#: `` `T13`（行数预算 1700 ＋ 过程标题词） `` —— 真源已 1800，而**没有任何尺子看得见**）。
_RESTATE_RE = re.compile(r"`T\d+`\s*（[^）]{0,60}?\d[^）]{0,60}?）")


def check_rule_restatements() -> list[dict]:
    """`T9` ② · ⭐ **注入档里别复述守卫的阈值**（2026-09-29 立 · 由 `TAIL-59` 的**量测**逼出来的）。

    ⭐ 治的病（`TAIL-59` 原话）=「**同一规则出现两个版本，而没有尺子看得见**」。
    ⚠️ 量测（只读件 `tools/oneoff/_tail59_measure.py`）先把**两类方案**分开：
      · **数字级**扫描（"阈值表里每个数在几个面里出现过"）⇒ 27 行里 **26 行命中**，但绝大多数是
        **巧合噪音**（`6` / `300` / `1000` 在任何文档里都会自然出现）⇒ ⛔ **数字级判据不可行**（会把噪音当漂移）；
      · **指名复述**（`` `T13`（…数字…） ``）⇒ **自带上下文**（守卫名 ⇒ 读者知道它在说哪条规则）⇒ ✅ 可判。
    ⭐ 规则：**规则留、数字去** —— 注入档（每会话必读、最贵）只该写"**有这条守卫**"，
      现值一律**指路**（如「行数预算 —— ⛔ 现值别写死，跑 `doc_audit` 取」）。
    ⚠️ **黄**（同 `T5`/`T10` 哲学：形式问题该被看见、⛔ 不挡合入）；⛔ **只查注入档** ——
      计划 / 归档里那种"**历史叙事**里的旧数字"是**对的留痕**（实测：`开发计划:1628` 的「1872 > 1700」
      是 2026-09-27 那次的现场记录 ⇒ ⛔ 改了反而是篡改历史）。
    """
    hits: list[dict] = []
    path = REPO_ROOT / RULE_DOC_REL
    if not path.exists():
        return [_t9(1, "找不到注入档", f"{RULE_DOC_REL} 不存在 ⇒ `T9`② 无从对照",
                    "恢复它（§八 工程纪律 ＋ 其余各节）")]
    for i, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if _RESTATE_RE.search(line):
            hits.append({"code": "T9", "side": "仓", "rel": RULE_DOC_REL, "line": i,
                         "what": "注入档里**复述了守卫的阈值**（`T<n>` ＋ 括号里的数字）",
                         "why": "同一规则两个版本 ⇒ 真源一改，这里就**静默漂**（2026-09-29 实测："
                                "`MEMORY.md` 写 1700、真源已是 1800，**没有尺子看得见**）",
                         "fix": "**规则留、数字去**：改成指路（「行数预算 —— ⛔ 现值别写死，跑 `doc_audit` 取」）",
                         "level": YELLOW, "text": line.strip()})
    return hits


# ------------------------------------------------- T10 文档读预算（治「太长读不完」）


#: ⭐⭐ 2026-09-21 立（用户原话：「文档一直很乱 …**太长了你也读不完** ⇒ 容易过期」）。
#:   ⚠️ 预算 = **谁必须整份读它**，跟"文档写得好不好"无关：
#:   · `inject` 档 = **每个新会话都会进上下文**（最贵 —— 它天天吃 token 且**没有任何检索能绕开**）；
#:   · `must` 档 = 接手/收尾必读（次之）。
#: ⚠️ 超预算 ⇒ **黄 ＋ 登记**（⛔ 不是禁写）⇒ 去 `ops/阈值表.md` 登记"为什么该长 / 什么时候拆"。
#: ⛔ 别为了让这条变绿而**删真东西** —— 正确的动作是**把历史叙事挪出状态文档**（见 `MEMORY.md §八`）。
#: ⚠️ **预算按真值定 ＋ 留小余量**（2026-09-21 实测：我第一版按 PowerShell 量的数**偏小** ⇒ 4 份文档当场"超预算"）。
#:    ⭐ 真因（2026-09-24 实测订正）：主因**不是**"不数空行"，而是 `Get-Content` **默认不按 UTF-8 解码**（PS 5.1 = ANSI）
#:    ⇒ 多字节中文被拆错 ⇒ **行数 / 字符数全错**（同一文件：`Get-Content` **69 行** vs `len(splitlines())` **198 行**）。
#:    ⛔ 别拿 PowerShell 的数当行数真值；要用就读 `-Encoding UTF8`（或索性用本件这个 `len(…splitlines())`）。
#: ⭐⭐ 2026-09-21 **文档体系重构**：`CLAUDE.md` 删除（无人读取）⇒ 它的**必用部分并入注入档**，
#:    故 `MEMORY.md` 预算由 90 提到 200（⚠️ 这是**有意的上调**：把"每轮必用的规则"集中到一个被注入的
#:    文件里，比原来"散在一个 333 行、没人自动读的文件里"更省 —— 原来我每轮都要去翻它）。
#:
#: ⭐⭐ 2026-10-05（`TAIL-236` 同批修 ③）：**加第四格 = 字节档**。**为什么非加不可**（实测）：
#:   宿主往每个会话注入 `MEMORY.md` 时有个**字节硬顶**（≈ 14,400 B），**超了是静默截断**
#:   —— 被截掉的恰好是**文件尾部**（`§七`/`§八` 工程纪律，最不该丢的那段）。
#:   ⚠️ 2026-10-05 实测：一度 **14,859 B > 硬顶**、**行数却还在 200 以内** ⇒ `T10` 只看得见行数
#:   ⇒ **字节超了没有任何尺子拦**（当天是靠人肉量才发现）。⇒ 行数是代理指标，**字节才是宿主真正按的那个数**。
#: ⚠️ `None` = 该档**不设字节上限**（只认行预算）—— ⛔ 别为了"整齐"给每行都编一个数：
#:   编出来的数没有出处（本仓规矩：硬数字要么实测、要么不写）。
#: ⚠️ **一条数只定义一次**：字节档只写在本表（`ops/阈值表.md` 那行只记出处与理由，⛔ 不复述件名清单）。
DOC_BUDGETS: tuple[tuple[str, int, str, int | None], ...] = (
    ("README.md", 240, "inject", None),                        #: ⛔ 现值**别手抄** ⇒ 要现值跑 `doc_audit`（`T10` 会报）；字节档 = `None`（它不是宿主自动注入的那一件）
    (".codebuddy/memory/MEMORY.md", 200, "inject", 14400),      #: ⛔ 行现值由 `T10` 报；⭐ **字节档 14400** = 宿主注入的硬顶（超了**静默截断**，见上）
    #: ⭐ 2026-10-01（`TAIL-204` 第 6 步）：原 `.codebuddy/plans/执行情况-主文档.md`（预算 **200**）**已取消** ——
    #:   用户裁定「只留待办」⇒ 待办并入**根 `README.md` §〇**（本表第 1 行就是它，预算 240）
    #:   ⇒ ⛔ **别为它再列一行**：那会变成"同一件事两处预算"（本仓最贵的病，必漂）。
    (".codebuddy/memory/细则.md", 620, "must", None),          #: ⛔ 同上；⭐ **2026-10-01（`TAIL-204` 第 2 步）420 → 620**：并入原项目侧 `MEMORY.md` 全文（173 行归档为附录）
    (".codebuddy/plans/开发计划-主文档.md", 1800, "must", None),   # ⭐⭐ 2026-09-29 **用户裁定 `A`：1700 → 1800**
                                                          #:   （文档审计 §五之补 · ①）**理由 = 容量**：台账按设计每条一行，
                                                          #:   09-29 一天新立/销号 **19 条**尾巴 ⇒ 顶穿 8 行是它**该长的样子**；
                                                          #:   ⛔ 「搬叙事」已证伪（§15 §四 销号行受 `T6` 保护、一行不能搬；
                                                          #:   那三处叙事各是一整行）⇒ ⛔ 不许不明说地超着，故**明说调到 1800**。
                                                          #: ⭐ 2026-09-23 **统一成 1700**：
                                                          #: 此前 `T10` 用 1800、`T13` 用 1700
                                                          #: （同一件事两处写）⇒ 现已并成一个数       #: ⛔ **现值别手抄进注释** —— 2026-09-24 实测 **1510**，这里曾写「现 ~1746」（09-23 瘦身前的值）
                                                          #: ⇒ **手抄的数字必漂**；要现值就跑 `doc_audit`（`T10` 会报）。
)
#: ⭐⭐ **注入档字节「逼近线」**（2026-10-06 · `/retro` ③）＝ 硬顶 − 900 B。
#: ⭐ **为什么要有它**（实测同日）：硬顶是 **14,400 B**，而那天余量只剩 **~0.5 KB** ⇒
#:   **连续两轮都没敢往注入档里记任何东西**（"想记又不敢记" ＝ 记忆档事实上停止长进）。
#:   而超顶的后果不是报错，是**静默截断**（丢**文件尾部** ＝ `§七`/`§八` 工程纪律那两节）。
#:   ⇒ 光有"超顶报黄"太晚：得**提前一条线**，逼出"先蒸馏再写"这个动作。
#: ⚠️ 900 B 的取法 = **够写两三条纪律的量**（实测一条纪律约 250–400 B）⇒ 到线时至少还能记两条。
#:   阈值出处 = `ops/阈值表.md`（那一行只记这个数与理由，⛔ 不复述件名）。
BYTES_WARN = 13500


def check_doc_budgets() -> list[dict]:
    """`T10` · **文档读预算** —— "每会话必读"的文档不得超过它那份预算。

    ⭐ 为什么这条比 `T5`（代码行数）重要：**代码长了我可以只读一个函数；文档长了我只能整份读**
       —— 而"整份读"这件事的失败方式很特别：**我不读，我改去 grep** ⇒ 于是**没被 grep 到的东西就永久丢了**
       （2026-09-21 实测到过：三条待办只活在对话里、`计划` 里 0 处命中）。
    """
    hits: list[dict] = []
    for rel, budget, tier, byte_budget in DOC_BUDGETS:
        p = REPO_ROOT / rel
        if not p.exists():
            hits.append({"code": "T10", "side": "仓", "rel": rel, "line": 1,
                         "what": f"文档不存在（预算 {budget} 行 · {tier} 档）",
                         "why": "被登记为必读的文档不见了 ⇒ 接手的人读不到",
                         "fix": "恢复它，或从 `DOC_BUDGETS` 里撤下（撤下要同步改 `ops/阈值表.md`）",
                         "level": YELLOW, "text": ""})
            continue
        n = len(p.read_text(encoding="utf-8", errors="replace").splitlines())
        if n > budget:
            hits.append({"code": "T10", "side": "仓", "rel": rel, "line": 1,
                         "what": f"{n} 行（预算 {budget}·{tier} 档）",
                         "why": ("**每会话注入档**超预算 ⇒ 它天天吃上下文，且**没有检索能绕开**"
                                 if tier == "inject" else
                                 "**必读档**超预算 ⇒ 它会退化成\"读不完 ⇒ 只 grep ⇒ 没搜到的就丢了\""),
                         "fix": "把**历史叙事**挪到 `artifacts/` 或 memory 日志（⛔ 别删真东西）；"
                                "或在 `ops/阈值表.md` 登记维持理由",
                         "level": YELLOW, "text": ""})
        # ⭐⭐ 2026-10-05（`TAIL-236` 同批修 ③）：**字节档** —— 见 `DOC_BUDGETS` 上方那段
        #   （宿主按**字节**截断注入档，而行数看不见它 ⇒ 2026-10-05 实测 14,859 B 超顶却全绿）。
        #   ⚠️ 行档与字节档**各报各的**（同一件可能只踩其中一个）—— ⛔ 别合并成一条，
        #     否则"哪一条超了"在报告里就看不出来了。
        if byte_budget is not None:
            nb = len(p.read_bytes())
            # ⭐ 2026-10-06（`/retro` ③）：**逼近线** —— 原来只在**超顶**时报，而超顶的后果是
            #   **静默截断**（丢文件尾部）；实测那之前余量只剩 ~0.5 KB 时，**连续两轮都不敢往里记**
            #   （"想记又不敢记" ＝ 记忆档在事实上停止长进）。⇒ 加一条**提前提醒**。
            if BYTES_WARN and BYTES_WARN <= nb < byte_budget:
                hits.append({"code": "T10", "side": "仓", "rel": rel, "line": 1,
                             "what": f"{nb} 字节（逼近线 {BYTES_WARN} · 硬顶 {byte_budget}）",
                             "why": "**离硬顶只剩不到 1 KB** ⇒ 再加两条就超顶，而超顶 ＝ **静默截断**"
                                    "（丢的是文件尾部 ＝ 工程纪律那两节）；"
                                    "⚠️ 到了这条线就**先蒸馏再写**（细节下沉到不注入的分册，只留指针）",
                             "fix": f"蒸馏：把细节挪进 `细则.md` / `IDE-细节.md`，{rel} 只留指针；"
                                    f"⭐ **不许靠删真东西腾地方**（阈值出处 = `ops/阈值表.md`）",
                             "level": YELLOW, "text": ""})
            if nb > byte_budget:
                hits.append({"code": "T10", "side": "仓", "rel": rel, "line": 1,
                             "what": f"{nb} 字节（预算 {byte_budget}）",
                             "why": "**注入档按字节算的那个数超了** ⇒ 宿主会**静默截断**"
                                    "（被截掉的是**文件尾部**，而那是该档最要紧的部分）；"
                                    "⚠️ 行数可能还在预算内 ⇒ 只查行数的判据**看不见它**",
                             "fix": "压缩该档（细节下沉到不注入的分册 ＋ 只留指针）；"
                                    "或在 `ops/阈值表.md` 登记维持理由",
                             "level": YELLOW, "text": ""})
    return hits


# ------------------------------------------------- T11 建议类报告必须带「待办登记回执」


#: `T11` 扫的目录 / 认的"建议类"关键词 / 回执段标题
RECEIPT_DIR = "artifacts"
REPORT_KINDS: tuple[str, ...] = ("审计", "提案", "建议", "报告")
RECEIPT_HEAD_RE = re.compile(r"^#{2,4}\s*(待办)?登记回执")
#: ⛔ 例外：**留痕/备份类**文件（如 `X.md.备份-…`）不是"建议"，不该被要求回执
RECEIPT_SKIP_RE = re.compile(r"备份|副本|归档")


def _t11(rel: str, lineno: int, what: str, why: str, fix: str, text: str = "") -> dict:
    return {"code": "T11", "side": "仓", "rel": rel, "line": lineno,
            "what": what, "why": why, "fix": fix, "level": RED, "text": text}


def check_report_receipts() -> list[dict]:
    """`T11` · **建议类报告必须带「待办登记回执」**（2026-09-21 立 · 用户问「P0–P3 不做完是不是就漏了」）。

    ⭐⭐ 起因是**一次实测的漏洞**：审计报告里提出的 `P2`/`P3`（变异覆盖台账 · `tools/` 分目录 ·
    规则可机读），**只活在报告与对话里** —— `计划主文档` 里搜 0 处命中 ⇒ **它们会永久丢掉**。
    ⇒ 立这条：**凡 `artifacts/` 下名字含「审计/提案/建议/报告」的 md，必须有一段「待办登记回执」**，
      里面逐条写「已登记为 `TAIL-xx`」或「不登记的理由」；⚠️ 回执里引用的 `TAIL-*` **必须真实存在**
      （幽灵编号 ⇒ 一样是漏）。

    ⚠️ **它为什么必须机器判**：报告是"一次性的产物"，人不会回头读第二遍；**而台账每轮非过不可**
       （`T6`）⇒ ⭐ **把"报告的产出"和"台账的接收"焊在一起**，是"承诺不落空"的唯一机器手段。
    """
    hits: list[dict] = []
    root = REPO_ROOT / RECEIPT_DIR
    if not root.is_dir():
        return hits
    ledger = REPO_ROOT / LEDGER_REL
    known = (set(re.findall(r"TAIL-(\d+)", ledger.read_text(encoding="utf-8", errors="replace")))
             if ledger.exists() else set())
    for f in sorted(root.glob("*.md")):
        if not any(w in f.name for w in REPORT_KINDS) or RECEIPT_SKIP_RE.search(f.name):
            continue
        rel = f"{RECEIPT_DIR}/{f.name}"
        lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
        start = next((k for k, l in enumerate(lines) if RECEIPT_HEAD_RE.match(l.strip())), None)
        if start is None:
            hits.append(_t11(rel, 1, "建议类报告没有「待办登记回执」段",
                             "报告里的建议**只活在报告里** ⇒ 没人回头读第二遍 ⇒ 会永久丢掉"
                             "（2026-09-21 实测：三条建议在计划里 0 处命中）",
                             "在报告末尾加 `## 待办登记回执`：逐条写「已登记为 `TAIL-xx`」或"
                             "「不登记的理由」"))
            continue
        end = next((k for k in range(start + 1, len(lines)) if lines[k].startswith("## ")),
                   len(lines))
        body = [l for l in lines[start + 1:end] if l.strip().startswith(("-", "|"))]
        if not body:
            hits.append(_t11(rel, start + 1, "「待办登记回执」是空的",
                             "空回执 = 没登记（只是摆了个标题）",
                             "逐条写：已登记为 `TAIL-xx` / 无需登记（写明理由）"))
        for n in sorted(set(re.findall(r"TAIL-(\d+)", "\n".join(lines[start:end]))), key=int):
            if n not in known:
                hits.append(_t11(rel, start + 1,
                                 f"回执里引用了台账中不存在的 `TAIL-{n}`",
                                 "幽灵编号 ⇒ 以为登记了、其实没登记（漏的方式从\"忘了\"变成\"写错了\"）",
                                 f"在计划 §15 补 `TAIL-{n}`，或删掉这个引用"))
    return hits


# ------------------------------------------------- T12 文档分层与命名约定


#: `plans/` 下**只许**这些活文档（其余一律必须 `归档-` 打头）。
#: ⭐ 2026-10-01（`TAIL-204` 第 6 步）：`执行情况-主文档.md` **已取消**（用户裁定「只留待办」⇒ 并进 `README.md` §〇）
#:   ⇒ 从"两份"收成"一份"。⚠️ 收的是**件数**，⛔ 不是把"给人看的那一页"这件事一起砍掉 —— 它现在住在根 `README.md`。
PLANS_LIVE: tuple[str, ...] = ("开发计划-主文档.md",)
#: 根目录**允许**出现的 `.md`（文档地图；⛔ 别在根上散落别的 md）
#: ⭐ **2026-10-04 扩一员**：`AGENTS.md` —— ⚠️ 原先这里只许 `README.md`，而那条**是 AGENT 自定的**
#:   （用户 2026-10-04 订正：「我没说过只需建立 README.md，这估计又是 AGENT 擅自曲解我的意思」）⇒
#:   根 `AGENTS.md` = **给 agent 的唯一入口**（只放指针、不放内容；地图仍归 `README.md`），见本件同批的
#:   `ops/agents/*` 三页 ＋ 根 `README.md` §三/§四 的分层表述。⛔ 它**不复述任何口径**。
ROOT_MD_ALLOW: tuple[str, ...] = ("README.md", "AGENTS.md")
#: `memory/` 下允许的 `.md` 与子目录（日志必须进 `journal/`）
MEMORY_MD_ALLOW: tuple[str, ...] = ("MEMORY.md", "细则.md", "IDE-细节.md")
MEMORY_DIR_ALLOW: tuple[str, ...] = ("journal",)
#: ⭐ `work/` **四区**（Agent 工作记录 · 文档架构审计 2026-09-22 P2：五类缺三类是乱建文件的根因）。
#:   ⚠️ 2026-10-01（`TAIL-204` 第 7 步）**由五区收成四区**：`20-experiments` 从建区起**一件都没进过**
#:   （用户 2026-10-01「以最精简为目的」· 出处 = `.codebuddy/memory/journal/2026-10-01.md` §14）⇒ 撤区；
#:   ⭐「实验/实测/对比试验」这一类**不取消** —— 改由 `30-troubleshooting` 收
#:   （那边同时认 `排查-` 与 `实验-` 两种前缀，见 `WORK_NAME_PREFIX`）。
WORK_DIR_ALLOW: tuple[str, ...] = ("00-scratch", "10-designs",
                                   "30-troubleshooting", "40-decisions", "50-tickets")
#: 各区 md 的命名前缀（`00-scratch` 不查 —— 临时件形态自由；`40-decisions` 只查 D 开头）。
#: ⭐ 2026-10-01：`30-troubleshooting` 收**两种**前缀 —— `排查-`（报障/事故复盘）与 `实验-`（探针/实测/对比试验，
#:   即原 `20-experiments` 那一类）。⛔ 别顺手把 `实验-` 也删掉：那一类**是存在的**，只是不再单开一个区。
#: ⭐ 2026-10-04（`TAIL-225` 票体系）：**加第五区 `50-tickets`** —— 一张票一个文件（`TAIL-<编号>-<短名>.md`），
#:   索引 = 计划 `§15` 一行一票；协议 = `ops/agents/issue-tracker.md`。⚠️ 它不是"新的分类学"，
#:   而是**尾巴的载体**（原来尾巴只活在 `§15` 表里一格）。
WORK_NAME_PREFIX: dict[str, tuple[str, ...]] = {
    "10-designs": ("设计-",),
    "30-troubleshooting": ("排查-", "实验-"),
    "40-decisions": ("D",),
    "50-tickets": ("TAIL-",),
}


def _t12(rel: str, what: str, why: str, fix: str) -> dict:
    return {"code": "T12", "side": "仓", "rel": rel, "line": 1,
            "what": what, "why": why, "fix": fix, "level": YELLOW, "text": ""}


def check_doc_layout() -> list[dict]:
    """`T12` · **文档分层与命名约定**（2026-09-21 立 · 文档体系重构的落地闸门）。

    ⭐ 依据 = `README.md` 的**四层**（① 注入 ② 按需 ③ 留痕 ④ 产物）：
      · `plans/` 下**只许两份活文档**，其余**必须 `归档-` 打头**（⚠️ 这条纪律早就写在
        `细则.md §五`「⛔ 不许私自新建文档」里，但**此前没有任何尺子看着它** ⇒ 本次立 T12）；
      · `memory/` 下**日志必须进 `journal/`**（⭐ `journal/` = 只追加不回读层 —— 混在 `memory/` 根下时，
        没人分得清"这是纪律还是流水账"，这正是用户报「文档乱」的机制之一）；
      · 仓库根**只许 `README.md`** 一份 md。

    ⚠️ 为什么是**黄**而不是红：布局是**组织形式**问题（不是对错），而且"新加一份文档"有时是正当的
       ⇒ ⭐ 与 `T5`/`T10` 同款哲学：**可能定错的不该挡合入，但必须被看见**；
       要新增层级 ⇒ 先改 `README.md` 的四层表与这里的三张白名单（⛔ 别绕过）。
    """
    hits: list[dict] = []
    plans = REPO_ROOT / ".codebuddy" / "plans"
    if plans.is_dir():
        for f in sorted(plans.glob("*.md")):
            if f.name not in PLANS_LIVE and not f.name.startswith("归档-"):
                hits.append(_t12(f".codebuddy/plans/{f.name}",
                                 "`plans/` 下出现了「第三份文档」",
                                 "`plans/` 只有两份活文档（计划 ＋ 执行情况），其余是**留痕** ⇒ "
                                 "多出来的第三份没人知道它是活文档还是留痕（`T6` 也只看计划那份）",
                                 "改名 `归档-<主题>-<日期>.md`（留痕），或并进两份活文档之一"))
    mem = REPO_ROOT / ".codebuddy" / "memory"
    if mem.is_dir():
        for f in sorted(mem.glob("*.md")):
            if f.name not in MEMORY_MD_ALLOW:
                hits.append(_t12(f".codebuddy/memory/{f.name}",
                                 "`memory/` 根下出现了非白名单的 md",
                                 "`memory/` 根只放**注入档与分册**；日志混在这里 ⇒ "
                                 "分不清「这是规则还是流水账」（用户报「文档乱」的机制之一）",
                                 "日志移到 `memory/journal/`（`YYYY-MM-DD.md`，⛔ 不改文件名）"))
        for d in sorted(x for x in mem.iterdir() if x.is_dir()):
            if d.name not in MEMORY_DIR_ALLOW:
                hits.append(_t12(f".codebuddy/memory/{d.name}/",
                                 "`memory/` 下出现了非白名单子目录",
                                 "`memory/` 只认 `journal/` 一个子目录",
                                 "并进 `journal/`，或改到别处（见 `README.md` 四层表）"))
    # ⭐ `work/` **五区**（2026-09-22 审计 P2 的机器化落地；⭐ 2026-10-01 由五区收成四区；⭐ 2026-10-04 `TAIL-225` 加回第五区 `50-tickets`）
    work = REPO_ROOT / ".codebuddy" / "work"
    if work.is_dir():
        for d in sorted(x for x in work.iterdir() if x.is_dir()):
            if d.name not in WORK_DIR_ALLOW:
                hits.append(_t12(f".codebuddy/work/{d.name}/",
                                 "`work/` 下出现了五区之外的子目录",
                                 "工作记录只认五区（见 `work/README.md`）—— 多出来的区 = 第二套分类学，必漂",
                                 "并入五区之一，或先改 `work/README.md` ＋ 本文件 `WORK_DIR_ALLOW`"))
        for zone, prefixes in WORK_NAME_PREFIX.items():
            zdir = work / zone
            if not zdir.is_dir():
                continue
            for f in sorted(zdir.glob("*.md")):
                if f.name == "README.md":
                    continue
                if not f.name.startswith(tuple(prefixes)):
                    hits.append(_t12(f".codebuddy/work/{zone}/{f.name}",
                                     "work 区文档命名不符（缺类型前缀）",
                                     "命名表是检索的抓手（审计 P2）—— 前缀错了 = 决策树对不上号",
                                     f"改名打头：{' / '.join(prefixes)}（如 `设计-主题-YYYYMMDD.md`）"))
    for f in sorted(REPO_ROOT.glob("*.md")):
        if f.name not in ROOT_MD_ALLOW:
            hits.append(_t12(f.name, "仓库根出现了白名单外的 md",
                             "根目录只放 `README.md`（文档地图）—— 根上散落的 md 没人维护、必然过期",
                             "并进 `README.md`，或按四层放到 `ops/` / `.codebuddy/` / `artifacts/`"))
    return hits


# ------------------------------------------------- T24 仓库根白名单（落点守卫）


def _gitignore_tolerated() -> tuple[set[str], tuple[str, ...]]:
    """`.gitignore` 里**声明过的根条目** ⇒ `(字面名集合, 通配模式元组)`（供 `T24` 用）。

    ⚠️ 它**不是第二份白名单** —— 认的就是那份忽略规则本身（`T24` 与 `T25` 各读它一半）：
      · 行首 `!`（负向规则）与行尾 `/` 都剥掉；
      · 取**第一段**当"根条目名"（`artifacts/*` ⇒ `artifacts`）；带通配符的整条按 `fnmatch` 收。
    ⛔ 注释行与空行不参与（`.gitignore` 的注释**本来就没有规则效力** —— 2026-09-24 那次事故就是
    注释写法把整条规则废掉了）。
    """
    lit: set[str] = set()
    pats: list[str] = []
    f = REPO_ROOT / GITIGNORE_REL
    if not f.exists():
        return lit, ()
    for raw in f.read_text(encoding="utf-8", errors="replace").splitlines():
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        s = s.lstrip("!").rstrip("/")
        head = s.split("/")[0]
        if head and not any(ch in head for ch in "*?["):
            lit.add(head)
        pats.append(s)
    return lit, tuple(pats)


def check_drop_zones() -> list[dict]:
    """`T24` · **仓库根白名单**（2026-10-05 · `TAIL-236` 同批修 ①b · **红**）。

    ⭐⭐ **它补的是整整一片没人看的地方**：`T12` 只查**根上的 md**（`ROOT_MD_ALLOW`）⇒
       **目录与非 md 文件**落在根上，`T3` / `T12` / `T14` **一层都不拦**。
       2026-10-05 实测到的样子：我照着 `.gitignore` 注释里的旧落点，**在仓库根建了一个 `work/`** ——
       闸门全绿、没人看见，直到人肉发现（然后那个目录不在 `TOP_DIRS` 里，里面的东西
       也**不在任何尺子的扫描面内**）。

    **判什么**：根上的每个条目，必须落在下面**两处之一**：
      ① `audit_common.ROOT_ALLOW` = **常驻**骨架条目（随仓走）；
      ② `.gitignore` 声明过的条目 = **可再生 / 本机暂存**（缓存 · 虚拟环境 · 构建产物 …）。
    ⚠️ **两份允许表职责不同、允许重叠**（⛔ 别把它们读成"同一份清单抄了两遍"）：
       ① 是**权威**（少一条 ⇒ 根上那个条目就该报）；② 是**额外容忍**（本机暂存，不必进 ①）。
       重叠的几项（`artifacts` / `logs` / `face` …）以 ① 为准 —— 判据取的是**并集**。
    ⚠️ **已知妥协（2026-10-05 `/code-review` 指出，如实记下）**：往 `.gitignore` 里加一行同名规则
       即可让根上某目录被容忍 ⇒ **存在这条旁路**。接受它的理由：那是一次**显式、可复核**的动作
       （且 `T25` 会核 `.gitignore` 里写的落点是不是真存在）；⛔ 但它不是"不可能绕过"。
    ⚠️ **根上的 `.md` 刻意跳过**：那半边归 `T12`（`ROOT_MD_ALLOW`）—— 两处各报一次就是
       "同一件事两个主人"（老病）。⚠️ **只跳 `.md`、不跳 `.mdc`**（`/code-review` 抓到的"加了半边"）：
       `T12` 只 `glob("*.md")` ⇒ 根上一个 `.mdc` **两把尺子都不报** ⇒ 那半边归本判据。
    ⚠️ 为什么是**红**不是黄：根上多出来的东西不是"审美问题" —— 它**不在任何扫描面内**，
       等于在仓库里开了一块**无人看守的地**（本次事故正是这样）。
    """
    from fnmatch import fnmatch  # noqa: PLC0415
    allow = {x.rstrip("/") for x in ROOT_ALLOW}
    tol_lit, tol_pat = _gitignore_tolerated()
    hits: list[dict] = []
    for p in sorted(REPO_ROOT.iterdir(), key=lambda x: x.name):
        name = p.name
        if p.is_file() and p.suffix == ".md":
            continue                       # ⛔ 根上的 `.md` 归 `T12`；`.mdc` **不跳**（见 docstring）
        if name in allow or name in tol_lit or any(fnmatch(name, g) for g in tol_pat):
            continue
        hits.append({"code": "T24", "side": "仓", "rel": name, "line": 1,
                     "what": f"仓库根多出「{name}」",
                     "why": "根目录是**仓库骨架**（`ROOT_ALLOW` ＋ `.gitignore` 两种身份）——"
                            "白名单外的条目**不在任何尺子眼里**：2026-10-05 实测，根 `work/` 建起来后"
                            "`T3`/`T12`/`T14` 四层守卫没一层拦，而那片地方从此无人看守",
                     "fix": "移到它该在的地方（工作记录类 ⇒ `.codebuddy/work/`）；"
                            "确实是新的**常驻**条目 ⇒ 同批登进 `audit_common.ROOT_ALLOW`；"
                            "只是**本机暂存/缓存** ⇒ 在 `.gitignore` 里登记它",
                     "level": RED, "text": ""})
    return hits


# ---------------------------------------------------------------- T6 尾巴台账


def _t6(rel: str, lineno: int, what: str, why: str, fix: str, text: str = "") -> dict:
    return {"code": "T6", "side": "仓", "rel": rel, "line": lineno,
            "what": what, "why": why, "fix": fix, "level": RED, "text": text}


#: ⭐⭐ 2026-10-04（`TAIL-225` 票体系）：**票仓** —— 一张票一个文件，索引 = 本台账**一行一票**。
#:   票长什么样 / 状态怎么记 / 怎么开工收尾的**主人** = `ops/agents/issue-tracker.md`（⛔ 本段不复述口径，
#:   只写"机器怎么判"）。⚠️ 为什么要有这一层：尾巴原先**只活在 `§15` 表里一格**，那一格普遍 1000–2400 字
#:   ⇒ 谁读都得在一行里穿过上万字（**字墙的根**，见 `T21` 与方案 §十一）。
TICKET_DIR_REL = ".codebuddy/work/50-tickets"
#: 票文件里**必须出现**的栏（⭐ **三个英文栏名来自 `/to-tickets`** —— 2026-10-04 用户指出
#:   "票结构跟第二个项目不一样"后对齐；⛔ 票**不带**"读者/何时读"那类文档文头 —— 票是**工单**）
TICKET_FIELDS: tuple[str, ...] = ("What to build", "Blocked by", "Status")
#: ⭐ **验收 = `- [ ]` 复选框列表**（照参考项目：验收是**票面主体**，不是末尾一栏）
TICKET_CHECKBOX_RE = re.compile(r"^\s*-\s*\[[ xX]\]", re.M)
#: 票的合法**状态**（受控词；出处 = `ops/agents/issue-tracker.md` §三）
TICKET_STATES: tuple[str, ...] = ("ready-for-agent", "claimed", "ready-for-human",
                                  "needs-info", "needs-triage", "wontfix", "done")
#: ⭐ **"销号"＝哪个状态词**（`TICKET_STATES` 里的一个）—— 2026-10-05 立（`TAIL-236` 批 2）。
#: ⛔ 为什么要**单列一个常量**：`/code-review` 抓到 `refs_query.py` 里**硬写 `"done"`** ——
#:   那是"什么算销号"的**第二处字面** ⇒ 改词表时那处会静默漏掉（本仓最贵的病：改一处漏一处）。
#: ⚠️ 真源仍是 `TICKET_STATES`（本常量**必须**是它的成员，⛔ 别单独当词表用）。
TICKET_CLOSED: str = "done"
TICKET_NAME_RE = re.compile(r"^(TAIL-\d+)-.+\.md$")
TICKET_STATE_RE = re.compile(r"\*\*Status:\*\*\s*`?([a-z\-]+)`?")


def ticket_states() -> dict[str, str]:
    """票仓现有票的 **`TAIL-<n>` → 状态词**（读不到 / 不是受控词 ⇒ `""` ＝ 按**未销号**算，保守）。

    ⭐ 口径**只有一份**：票目录 / 文件名形态 / 状态正则 / 受控词表**全部**用本模块上面的常量
    （⛔ 调用方别另抄一遍 —— 「改一处漏一处」是本仓最贵的病）。
    ⭐ 为什么要单独给一个读函数：`T26`（降档判据，`TAIL-236` 第 3 批）要问
    「件内提到的票**是不是全销号了**」，而**"销号"的定义**在 `TICKET_CLOSED` 里
    （`T6` 与 `refs_query` 守着同一份）⇒ 谁都不许硬写 `"done"`。
    """
    out: dict[str, str] = {}
    tdir = REPO_ROOT / TICKET_DIR_REL
    if not tdir.is_dir():
        return out
    for f in sorted(tdir.glob("*.md")):
        m = TICKET_NAME_RE.match(f.name)
        if not m:
            continue
        st = TICKET_STATE_RE.search(f.read_text(encoding="utf-8", errors="replace"))
        out[m.group(1)] = st.group(1) if (st and st.group(1) in TICKET_STATES) else ""
    return out


def ledger_counts(text: str | None = None) -> dict[str, int] | None:
    """尾巴台账**四段各有多少行**（只数行，不做任何检查）。

    ⭐ 2026-09-24 从 `check_tail_ledger` 抽出：`T6` 用它核对顶部计数行，
    `audit_drift` 的 **`T4` 计数锚点**（黄档）用它核对**两份活文档**里手抄的尾巴计数
    ⇒ ⛔ **段解析与计数口径只留这一份**（别在别处再写一遍）。
    ⭐ 2026-10-02（`/retro` 候选 1）加 `text` 形参：**用来数"还没落盘的新文本"** ——
       `_tail_open.py` / `_tail_close.py` 的口径是"改完**先数**、数对了才写盘"，给它就**不必再临时落盘**。
    返回 `{"一": n, "二": n, "三": n, "四": n}`；台账 / 段找不到 ⇒ `None`。
    """
    if text is None:
        path = REPO_ROOT / LEDGER_REL
        if not path.exists():
            return None
        text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    start = next((k for k, l in enumerate(lines)
                  if re.match(r"^#{2,3}\s*[\d.]*\s*尾巴台账", l.strip())), None)
    if start is None:
        return None
    end = next((k for k in range(start + 1, len(lines)) if lines[k].startswith("## ")), len(lines))
    section = ""
    cnt: dict[str, int] = {}
    for raw in lines[start:end]:
        line = raw.strip()
        m_sec = re.match(r"^#{2,3}\s*([一二三四])\s*[、.]", line)
        if m_sec:
            section = m_sec.group(1)
            continue
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        first = cells[0] if cells else ""
        if first == "#" or not first or set(first) <= {"-", ":"}:
            continue
        cnt[section] = cnt.get(section, 0) + 1
    return cnt


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

    # ⭐ 计数口径 = `ledger_counts()`（**唯一一份**；`T4` 的计数锚点同时用它）
    _lc = ledger_counts() or {}
    counts = {k: _lc.get(k, 0) for k in ("一", "二", "三")}
    counts["四"] = _lc.get("四", 0)
    # ⚠️ 形态来自 `audit_common.COUNT_FULL_RE`（2026-10-02 收口：此前这里与 `_tail_close.py` 各写一遍）
    #    ⚠️⚠️ 想拿**数字**必须走 `read_counts()` —— 那条正则的捕获组抓的是**装饰**，直接 `int()` 会崩
    #    （2026-10-02 自测当场踩过；⭐ 是"立台账工具"的收尾断言抓出来的）
    got = read_counts("\n".join(lines))
    if got is None:
        hits.append(_t6(LEDGER_REL, 1, "找不到顶部的「当前状态」计数行",
                        "没有计数就没法一眼看出尾巴有没有在涨", "补一行：A 类 **n** 条 · B 类 … "))
    else:
        want = (counts["一"], counts["二"], counts["三"], counts["四"])
        if got != want:
            hits.append(_t6(LEDGER_REL, 1, f"计数与实际不符：写的 {got}，实际 {want}",
                            "计数漂了 ⇒ 人会按错的数判断", "按实际条数改这一行（机器核对）"))

    # ⭐⭐ 2026-10-04（`TAIL-225` 票体系）：**票文件必须在位** ＋ 票里得有该有的栏 ＋ 状态受控 ＋ 不许幽灵票。
    #    ⚠️ **只查 `§一/§二/§三`（在办）** —— `§四` 那 223 条已销号行按**留痕**口径**不追改**
    #       （方案 §十一-3：它们是"当初为什么这么定"的证据，不是待办）。
    #    ⚠️ 形态 = **新增一层 + ⛔ 不放松任何现有判据**（本仓「先立门禁 ＋ 老账记账」那套打法）。
    tdir = REPO_ROOT / TICKET_DIR_REL
    tickets: dict[str, Path] = {}
    if tdir.is_dir():
        for f in sorted(tdir.glob("*.md")):
            m_tk = TICKET_NAME_RE.match(f.name)
            if m_tk:
                tickets[m_tk.group(1)] = f
    for n in sorted(live, key=int):
        tag = f"TAIL-{n}"
        if tag not in tickets:
            hits.append(_t6(LEDGER_REL, 1, f"{tag} 没有票文件",
                            "尾巴只活在索引表一格 ⇒ 过程与证据没处放（**字墙的根**）",
                            f"建 `{TICKET_DIR_REL}/{tag}-<短名>.md` —— ⭐ 用 `tools/oneoff/_tail_open.py`"
                            "（⛔ 别手抄；模板见 `ops/agents/issue-tracker.md` §二）"))
    for tag, f in sorted(tickets.items(), key=lambda kv: int(kv[0].lstrip("TAIL-"))):
        n = tag.lstrip("TAIL-")
        if n not in ids:
            hits.append(_t6(f"{TICKET_DIR_REL}/{f.name}", 1, "票仓里有幽灵票文件",
                            "台账里没有这个编号 ⇒ 索引与票仓已经分叉（两份清单各说各话）",
                            "在 §15 补一行索引，或用 `_tail_close.py` 正规销号（⚠️ 删前确认它真没用了）"))
            continue
        body = f.read_text(encoding="utf-8", errors="replace")
        miss = [k for k in TICKET_FIELDS if k not in body]
        if miss:
            hits.append(_t6(f"{TICKET_DIR_REL}/{f.name}", 1, f"票里缺栏：{' / '.join(miss)}",
                            "没写清「要什么 / 为什么不做 / 落点 / 什么时候做」⇒ 领票的人一头雾水",
                            "按 `ops/agents/issue-tracker.md` §二 的模板补齐"))
        if not TICKET_CHECKBOX_RE.search(body):
            hits.append(_t6(f"{TICKET_DIR_REL}/{f.name}", 1, "票里没有**验收复选框**",
                            "`- [ ]` 那串就是「怎么算做完」（照参考项目：验收是**票面主体**）",
                            "补几条 `- [ ] …`（每条要能证伪 —— 跑哪条命令、看什么数）"))
        m_st = TICKET_STATE_RE.search(body)
        if not m_st:
            hits.append(_t6(f"{TICKET_DIR_REL}/{f.name}", 1, "找不到 `**Status:**` 行",
                            "状态是票体系唯一的进度信号",
                            "写一行：`**Status:** ready-for-agent`（词表见 `ops/agents/issue-tracker.md` §三）"))
        elif m_st.group(1) not in TICKET_STATES:
            hits.append(_t6(f"{TICKET_DIR_REL}/{f.name}", 1,
                            f"「状态」不是受控词：{m_st.group(1)}",
                            "状态词表是机器与人对表的唯一抓手（出处 = `ops/agents/issue-tracker.md` §三）",
                            f"改成：{' / '.join(TICKET_STATES)}"))
    return hits


# ------------------------------------------------- T13 主文档「过程回潮」守卫

#: ⭐ 2026-09-22 立（用户问「为啥还是会有过期现象？是不是把太多过程塞到开发计划里了？」）：
#: 病灶**实测成立** —— 主文档曾 1773 行、270 行含日期叙事；过程一写死就过期
#: （`TAIL-07` 挂着「待做」两个周期才被人肉发现）。⇒ `§13.1/13.2` 早有「完成的就扔出去」的裁定，
#: 但**只有触发点、没有机器守** ⇒ 治法 = 过程**只许下沉** `归档-历史单元条目.md`（原处留指针），
#: 本条守卫盯两件事：
#:   (a) 主文档**行数预算** —— 超了 = 过程又塞回来了（黄 ⇒ 下沉）；
#:   (b) 标题里出现**过程词**（逐批记录 / 逐次记录 / 收官记录）⇒ 该块该下沉了（黄）。
PLAN_DOC_REL = ".codebuddy/plans/开发计划-主文档.md"
PLAN_LINE_BUDGET = 1800          #: ⭐ 2026-09-29 用户裁定 `A` 1700 → 1800（**与 `T10` 那个数同源** ——
#:   `ops/阈值表.md:31` 写着「一个数、两处用」⇒ 改一处必须改另一处）
PROCESS_TITLE_RE = re.compile(r"^#{2,4}.*(逐批记录|逐次记录|收官记录)")
#: 标题里写着「下沉/归档/索引」的 = **指针节**，不是过程本体 ⇒ 豁免
PROCESS_EXEMPT_RE = re.compile(r"下沉|归档|索引")


def _t13(lineno: int, what: str, why: str, fix: str) -> dict:
    return {"code": "T13", "side": "仓", "rel": PLAN_DOC_REL, "line": lineno,
            "what": what, "why": why, "fix": fix, "level": YELLOW, "text": ""}


def check_plan_process() -> list[dict]:
    """`T13` · 主文档**过程回潮**守卫（黄）：行数超预算 ＋ 标题出现过程词。

    ⛔ **不是禁写** —— 是把「§13.2 第 4/5 条」的触发从"靠我每轮自觉"变成"机器一定看见"：
    黄了就做那个动作（把过程块逐字搬到归档件、原处留指针），不黄不拦任何事。
    """
    p = REPO_ROOT / PLAN_DOC_REL
    if not p.exists():
        return [_t13(1, "计划主文档不存在", "没有它，法规/现状/台账就没有单一出处", "恢复该文件")]
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    hits: list[dict] = []
    if len(lines) > PLAN_LINE_BUDGET:
        hits.append(_t13(1, f"主文档 {len(lines)} 行 > 预算 {PLAN_LINE_BUDGET}",
                         "行数涨 = 过程又塞回来了 ⇒ 要紧的（现在到哪/接下来做什么）被淹没",
                         "把已完成的**过程块**逐字下沉 `归档-历史单元条目.md`，原处留 2~3 行指针"))
    for i, l in enumerate(lines, 1):
        if PROCESS_TITLE_RE.match(l) and not PROCESS_EXEMPT_RE.search(l):
            hits.append(_t13(i, "标题含过程词（该块是过程，不是法规/现状）",
                             "过程留在主文档 = 过期语句的 incubator（写死即旧）",
                             "整块下沉归档件，原处留指针；标题改成「通法 / 清单 / 指针」形态"))
    return hits


# ------------------------------------------------- T21 文档「字墙」（单行过长）守卫
#
#: 阈值出处 = `ops/阈值表.md`（**唯一一处集中登记**）。
#: ⭐⭐ 2026-10-04 立（`TAIL-224` · 用户裁定「④按推荐」＝ 文档重构方案 §六-4 甲案）：
#:   「字墙」= **单行 >800 字** —— 它是"文档很乱"的**真身**：主文档 **88 行**超 800 字
#:   （存量最多的一行 **4563 字**：一整天的交接工作塞进一行）。⚠️ `T10`（读预算）与 `T13`
#:   （行数）都只看得见"**总共多少行**"，**看不见"一行有多长"** ⇒ 这类"行数在预算内、
#:   单行上万字"的病**从没有尺子看得见**（方案 §三-4 的实证）。
#: ⚠️ 为什么带**老账基线**，而不是像 `T5` 那样每次把 100+ 行全列出来：
#:   ① 106 条黄会把 `doc_audit` 的「疑似」从 12 抬到 118 ⇒ **判据当场变噪音源**
#:      （本仓老话：**噪音会把人逼到"把判据关掉"**）；
#:   ② 字墙的失败方式是「**沉下去又长回来**」—— `§13.6` 已沉过 **4 次**（09-23 / 09-30 /
#:      10-02 / 10-04）⇒ 要的是「**只许变短**」这道闸（同 `shell_scissors` / `_C_PENDING_START`
#:      的思路），⛔ 不是"每次复述一遍存量"（那正是这条病当初没人治的原因）。
#:   ⇒ 本检查的报法：**超基线 ⇒ 黄（字墙又长回来了）· 低于基线 ⇒ 黄（基线该下调了）**。
LINE_WALL_CHARS = 800

#: ⭐ **老账基线**（**只许变短**）：件 → 存量字墙条数。
#:   ⚠️ 量法 = **活文档**（`SCAN_GLOBS` 命中、**减** `LENIENT_GLOBS` 的留痕/归档件）里
#:      `len(line) > 800` 的行数；下面三个数 = 2026-10-04 立 `T21` 当场的实测值
#:      （量测件 = `.codebuddy/work/00-scratch/tmp-20261004-linewalls.py` · 只读可复跑）。
#:   ⇒ 把某件**下沉 / 拆行**之后**必须同批下调**这里的数（否则本检查报「基线过期」）；
#:      ⛔ **不许上调**（上调 = 把闸放松 = 这条判据失去意义）。
LINE_WALL_BASELINE: tuple[tuple[str, int], ...] = (
    (".codebuddy/plans/开发计划-主文档.md", 88),
    ("ops/前端设计守则-以使用用户为中心.md", 16),
    ("ops/阈值表.md", 2),
)


def _t21(rel: str, lineno: int, what: str, why: str, fix: str) -> dict:
    return {"code": "T21", "side": "仓", "rel": rel, "line": lineno,
            "what": what, "why": why, "fix": fix, "level": YELLOW, "text": ""}


def _live_docs() -> list[tuple[str, list[str]]]:
    """→ [(相对名, 行表)]：**活文档** = `SCAN_GLOBS` 命中的 md **减去**留痕/归档（`LENIENT_GLOBS`）。

    ⚠️ 复用 `audit_common` 的两个 glob（它们已是"会被当口径读的那几层"的**唯一定义**）
    —— ⛔ 别在这儿另写一套扫描面（那会长出第二套口径，本仓最贵的病；`T18` 也会盯着常量）。
    """
    from fnmatch import fnmatch

    out: list[tuple[str, list[str]]] = []
    seen: set[Path] = set()
    for pat in SCAN_GLOBS:
        for p in sorted(REPO_ROOT.glob(pat)):
            if not p.is_file() or p.suffix not in DOC_SUFFIXES or p in seen:
                continue
            seen.add(p)
            rel = str(p.relative_to(REPO_ROOT)).replace("\\", "/")
            if any(fnmatch(rel, g) for g in LENIENT_GLOBS):
                continue
            out.append((rel, p.read_text(encoding="utf-8", errors="replace").splitlines()))
    return out


def check_line_walls() -> list[dict]:
    """`T21` · 文档「字墙」（单行过长）守卫（黄）—— 见上方常量注释。"""
    base = dict(LINE_WALL_BASELINE)
    hits: list[dict] = []
    seen: set[str] = set()
    for rel, lines in _live_docs():
        seen.add(rel)
        over = [(i, len(x)) for i, x in enumerate(lines, 1) if len(x) > LINE_WALL_CHARS]
        cur = len(over)
        b = base.get(rel)
        if b is None:
            if cur:
                worst = max(over, key=lambda t: t[1])
                hits.append(_t21(rel, worst[0],
                                 f"新出现的「字墙」件：{cur} 行单行 > {LINE_WALL_CHARS} 字"
                                 f"（最长第 {worst[0]} 行 {worst[1]} 字）",
                                 "一行塞一整天的工作 ⇒ 接手的人得穿过上万字才找得到「下一步是哪一步」；"
                                 "（`T10`/`T13` 只管总行数，看不见「一行有多长」）",
                                 "把这几行拆成「一行一事」，或把过程叙述逐字下沉归档件；"
                                 "确需保留则在 `ops/阈值表.md` 的基线里登记本件"))
            continue
        if cur > b:
            w = sorted(over, key=lambda t: -t[1])[:2]
            where = "；".join(f"第 {i} 行 {n} 字" for i, n in w)
            hits.append(_t21(rel, w[0][0],
                             f"字墙**又长回来了**：{cur} 行单行 > {LINE_WALL_CHARS} 字"
                             f"（基线 {b} · 最长两处：{where}）",
                             "字墙的失败方式是「沉下去又长回来」（`§13.6` 已沉过 4 次）"
                             "⇒ 基线**只许变短**，新长的当场拦",
                             "把这批新长的**拆行 / 下沉归档件**；⛔ 别上调 `LINE_WALL_BASELINE`"
                             "（上调 = 把闸放松）"))
        elif cur < b:
            hits.append(_t21(rel, 1,
                             f"字墙基线**过期**：本件实为 {cur} 行 ≤ 基线 {b} ⇒ 请下调",
                             "基线只许变短；不跟改 ⇒ 那道闸会越来越松、最后形同虚设",
                             f"把 `ops/阈值表.md` 与 `audit_meta.LINE_WALL_BASELINE` 里本件改成 {cur}"))
    for rel, b in LINE_WALL_BASELINE:
        if rel not in seen:
            hits.append(_t21(rel, 1,
                             f"基线里的件已**不在活文档扫描面内**（基线写着 {b} 行）",
                             "件被删 / 改名 / 归档进留痕 ⇒ 这条基线成了幽灵（只增不减是它的常见烂法）",
                             "从 `LINE_WALL_BASELINE` 撤下本行（`ops/阈值表.md` 同改）"))
    return hits


# ------------------------------------------------- T22 注入档「两行粘成一行」
#
# ⭐⭐ 2026-10-05 立（`TAIL-235` 丁-2）。**先说它治的是什么**（当天实测）：
#   `replace_in_file` 的 `old_str` 末尾多写了一个换行 ⇒ 下一行的**列表符被吞进上一行**
#   ⇒ `MEMORY.md` 从 **93 行变 92 行**，两行变成一行。
#   而它的失败方式极其恶劣：**工具只报「2 lines removed」、闸门 rc=0、pytest 全绿、
#   没有任何尺子看得见** —— 因为 `MEMORY.md` **不在任何判据的栏位检查里**。
#   ⇒ 后果不是"文档丑了"，是**一整条纪律和一个渲染示例被粘进了上一行的句子里**，
#     而注入档每轮都读它 ⇒ 谁也发现不了。
#
# ⚠️ **为什么该做检查、不该写规则**：这是**固定语法模式**（不是判断题）⇒ 能机器判。
#    写进 `MEMORY.md` 当纪律，**没有任何尺子会执行它** ⇒ 写了没牙。
#
#: `T22` 的目标集 = **常读三件**（每会话自动注入 / 接手必读的那三件）。
#: ⛔ **刻意不叫"注入档三件"**（`/code-review` 指出的一处口径打架）：本仓的"注入档"**有精确含义** =
#:    **唯一** `MEMORY.md`（`细则.md §394/436/584` ＋ `MEMORY.md §二` 都这么写，`DOC_BUDGETS` 的
#:    `tier` 也是这么分的：`MEMORY.md`＝inject · `细则.md`＝must · `IDE-细节.md`＝不注入）。
#:    票面那句"注入档三件"是**口语**；本表若照抄就等于**给同一个词第二套定义**（本仓最贵的病）。
#:   ⚠️ 口径**只在这里定义一次**（`ops/阈值表.md` 那行只写"真源 = 本常量"，⛔ 不复述件名清单）。
#:   ⚠️ `journal/`（逐日日志）与 `plans/` **不在内** —— 那是**只追加留痕**，
#:     里面的粘连是**历史事实**，改了才是篡改（同 `LENIENT_GLOBS` 的哲学）。
ALWAYS_READ_DOCS: tuple[str, ...] = (
    ".codebuddy/memory/MEMORY.md",
    ".codebuddy/memory/细则.md",
    ".codebuddy/memory/IDE-细节.md",
)
#: 粘连特征 = **行尾标点**后面紧跟「列表符 / 引用符 + 空白」——
#:   即"本该是下一行行首的符号，被拼到了上一行的句号后面"。
#: ⛔⛔ **空白只许横向**（`[ \t]*`，⛔ **不能用 `\s*`**）：`\s` 含换行 ⇒ 它会匹配
#:   「上一行以句号收尾 ＋ 下一行是列表项」这种**完全正常的排版**
#:   （当天实测：全仓 **78 件** md 因此命中，注入档三件里也全是这种正常行 ⇒ **整条判据成废**）。
#:   ⇒ 第一版量测就是栽在这：**78 件的"命中"里 0 件是粘连**。
SPLICE_RE = re.compile(r"[。；：、，）】」!?！？][ \t]*(?:[-*+][ \t]|>[ \t]|\d+[.)][ \t])")


def _t22(rel: str, lineno: int, what: str, why: str, fix: str, text: str = "") -> dict:
    return {"code": "T22", "side": "仓", "rel": rel, "line": lineno, "what": what,
            "why": why, "fix": fix, "level": YELLOW, "text": text}


def check_line_splices() -> list[dict]:
    """`T22` · **注入档三件里出现「标点后紧跟列表符/引用符」的粘连 ⇒ 黄**。

    ⚠️ **只报黄、不报红**：粘连是**编辑事故**（工具用错），不是口径写错 ⇒
       它的正确处置是"当场把那两行拆回去"，不该挡住别人的合入（同 `T5`/`T10` 哲学）。
    """
    hits: list[dict] = []
    for rel in ALWAYS_READ_DOCS:
        p = REPO_ROOT / rel
        if not p.exists():
            hits.append(_t22(rel, 1, "（文件不存在）",
                             "注入档三件少了一件 ⇒ 接手的人读不到，而**没有任何尺子会提它**",
                             "恢复该件，或从 `INJECT_DOCS` 撤下（撤下要同步改 `ops/阈值表.md`）"))
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            m = SPLICE_RE.search(line)
            if not m:
                continue
            s = max(0, m.start() - 24)
            hits.append(_t22(
                rel, i, f"第 {i} 行有粘连：…{line[s:m.end() + 18]}…",
                "**两行被粘成了一行**（本该另起一行的列表项 / 引用符，拼到了上一行的句号后面）"
                "—— 实测成因是编辑工具的锚点末尾多写了一个换行；"
                "而这类损坏**闸门 rc=0、pytest 全绿、没有任何尺子看得见**，"
                "注入档却每轮都被读 ⇒ 没人会发现",
                "把粘连的那两行**拆回两行**（⛔ 核一下行数：改前改后 `len(splitlines())` 应 +1）；"
                "改已有 md 的脚本一律 `newline=\"\"` 读写"))
    return hits


# ------------------------------------------------- T23 活机器口径（`refs` 的"六路"）
#
# ⭐⭐ 2026-10-05 立（`TAIL-236` 第 2 批）。**它防的是当天真发生过的翻车**：
#   清「零机器引用的死重」时，第一版口径只扫后端与 `tools/` 下的 `.py`
#   ⇒ **漏了运维脚本与规则档两路**（壳的脚本 / 页面也漏）
#   ⇒ 差点把一份**被运维脚本引用**的设计件当死重搬走。
#   ⭐ 治法**不是"再补一处"**：口径**只此一份**（`audit_common.LIVE_MACHINE_GLOBS`），
#     查询命令与本条都 import 它 —— 而**光靠命令自己测自己不够**
#     （当天翻车正是"口径只写在脚本里、没人钉"）⇒ 本条就是钉它的那半边。
#
# ⚠️⚠️ **`LIVE_MACHINE_REQUIRED` 为什么是"看起来的第二份字面"**：它是**判据的靶**。
#    两者**故意住在两件里** —— 否则把执行清单里的一路删掉，判据会跟着一起删、**永远绿**
#    （同族教训：`T3` 的豁免词表若并进四把尺子共用的 `HARD_EXEMPT`，会把 `T2` 一起赦掉）。
#: ⚠️ **形态 = `(glob, 后缀白名单)` 两项**（`/code-review` 当场指出首版只钉了 glob）：
#:   `audit_common` 那张表的注释自称后缀白名单是"**第三半边**"，而首版的靶里**没有它**
#:   ⇒ 把某一路的后缀改坏（`(".ps1",)` → `(".mdc",)`）判据**一声不响**。
LIVE_MACHINE_REQUIRED: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("backend/app/**/*.py", (".py",)),
    ("backend/tests/**/*.py", (".py",)),
    ("tools/audit/**/*.py", (".py",)),
    ("tools/mut/**/*.py", (".py",)),
    ("tools/probe/**/*.py", (".py",)),
    ("ops/*.ps1", (".ps1",)),
    (".codebuddy/rules/**/*.mdc", (".mdc",)),
    ("backend/app/web/**/*.js", (".js",)),
    ("backend/app/web/**/*.html", (".html",)),
)
#: `refs` 查询命令件 —— 半边③ 守的就是它（⛔ 它的**代码**里不许再写一份活机器路径）。
REFS_QUERY_REL = "tools/audit/refs_query.py"
#: 半边④ 守**接线**：`doc_audit`（收工闸门清单里那一把）里必须有 `T23` 的调用。
DOC_AUDIT_REL = "tools/audit/doc_audit.py"
WIRE_CALL = "check_live_machine("


def _t23(lineno: int, what: str, why: str, fix: str, level: str) -> dict:
    return {"code": "T23", "side": "仓", "rel": "tools/audit/audit_meta.py", "line": lineno,
            "what": what, "why": why, "fix": fix, "level": level, "text": ""}


def _code_lines(path: Path, drop_strings: bool = True) -> dict[int, str]:
    """→ `{行号: 代码}`，**注释已剔除**（用 `tokenize`；⛔ 别拿正则剥注释 —— 注释里有 `#`
    也有引号，正则一定会剥错）。

    ⭐ 为什么要剔注释：口径**写在注释里是好的**（那是解释），**写在代码里才是第二套**
    ⇒ 判据只该管后者。
    ⚠️⚠️ **`drop_strings` 为什么必须是可关的**（当天被自己的变异件抓到）：
       路径**必然以字符串形式出现** ⇒ 若把字符串也剔掉，半边③ 就**永远抓不到任何东西** ——
       而它看上去是"有牙的"（会跑、会输出 0 命中）。
       ⇒ 半边③（查"代码里又抄了一份路径"）必须**连字符串一起看**，只剔注释。
    """
    stringy: set[int] = set()
    commy: set[int] = set()
    with open(path, "rb") as fh:
        for tok in tokenize.tokenize(fh.readline):
            if tok.type == tokenize.STRING and drop_strings:
                stringy.update(range(tok.start[0], tok.end[0] + 1))
            elif tok.type == tokenize.COMMENT:
                commy.add(tok.start[0])
    out: dict[int, str] = {}
    for i, raw in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if i in stringy or i in commy:
            continue
        out[i] = raw
    return out


def check_live_machine() -> list[dict]:
    """`T23` · 活机器口径**六路齐全**（红）＋ 每条 glob **真能命中**（红）
    ＋ `refs` 件里**不许复述口径**（黄）。

    ⚠️ 半边③ 是**形态类规则**（它认"代码里出现这串路径"这个形态）⇒ 按本仓纪律，
       上线前的量测结果是：**正常数据上 0 命中**（口径在 `audit_common` 一处，命令只 import）。
       ⚠️ 已知边界（如实记账）：把路径**拼出来**（`"ops/" + "*.ps1"`）能躲开这半边 ——
       它防的是"顺手又抄一份"，不是防"刻意绕过"。
    """
    out: list[dict] = []
    have = {(g, sufs) for g, _label, sufs in LIVE_MACHINE_GLOBS}
    for g, sufs in LIVE_MACHINE_REQUIRED:
        if (g, sufs) in have:
            continue
        out.append(_t23(1, f"活机器口径**缺一路，或那一路的后缀白名单对不上**：`{g}` {sufs}",
                        "少一路 ⇒ 引用盘点少扫那一处 ⇒ 会报「没人引用」"
                        "（2026-10-05 实测：漏了运维脚本与规则档两路，差点搬走被引用的设计件）；"
                        "**后缀对不上**同族 —— 那条路会扫到别的后缀上去，等于没扫对它",
                        f"把 `{g}` ＋ 后缀 {sufs} 加回 `audit_common.LIVE_MACHINE_GLOBS`"
                        "（改口径要同批改 `ops/阈值表.md` 与 `LIVE_MACHINE_REQUIRED`）", RED))
    for glob, label, sufs in LIVE_MACHINE_GLOBS:
        if any(p.is_file() and p.suffix in sufs for p in REPO_ROOT.glob(glob)):
            continue
        out.append(_t23(1, f"活机器口径里的 `{glob}`（{label}）**一条都不命中**",
                        "空命中 = 那一片**从没被扫过** ⇒ 盘点假装扫过（`T18` 同族的假绿）",
                        f"核对路径与后缀白名单（当前 {sufs}），或从 `LIVE_MACHINE_GLOBS` 撤下这一条", RED))
    q = REPO_ROOT / REFS_QUERY_REL
    if not q.exists():
        out.append(_t23(1, f"`{REFS_QUERY_REL}` **不在位**",
                        "查询命令没了 ⇒「某件还有谁在引用」又只能靠回忆（这正是本条要治的病）",
                        "恢复该件（只读工具 · `TAIL-236` 第 2 批）", RED))
    else:
        for i, raw in _code_lines(q, drop_strings=False).items():
            for g, _sufs in LIVE_MACHINE_REQUIRED:
                if g in raw:
                    out.append(_t23(i, f"`{REFS_QUERY_REL}` 的代码里又写了一份活机器路径：`{g}`",
                                    "口径**只定义一次**（`audit_common.LIVE_MACHINE_GLOBS`）——"
                                    "命令里再抄一份 ⇒ 改一处漏一处，正是当天翻车的那一族",
                                    "删掉这处字面、改用 `LIVE_MACHINE_GLOBS`（注释里可以写，⛔ 代码里不行）",
                                    YELLOW))
    # ⚠️ 半边④：**判据自检接线** —— 本仓已有五例「僵尸闸门」（在闸门清单里跑、其实什么都没判），
    #   而"装了判据只接了一半"也发生过（`T18` 首版只在 `doc_audit` 里被动生效、单跑是哑的）。
    da = REPO_ROOT / DOC_AUDIT_REL
    if not da.exists():
        out.append(_t23(1, f"`{DOC_AUDIT_REL}` 不在位", "收工闸门那一把尺子没了", "恢复该件", RED))
    elif not any(WIRE_CALL in raw for raw in _code_lines(da).values()):
        out.append(_t23(1, "`doc_audit` 里**没有 `T23` 的调用**",
                        "判据装了却没进收工闸门 ＝ 闸门里没有它（同族：五例「僵尸闸门」"
                        "＋ `T18` 首版单跑是哑的）",
                        f"在 `doc_audit.main()` 的 `raw` 累加里加一行 `{WIRE_CALL}...)`", RED))
    return out


# ------------------------------------------------- T17 闸门清单活性（治「僵尸闸门」）
#
# ⭐⭐ 2026-09-24 立（`TAIL-82`）：一天内核出**四例僵尸闸门**（症状同款：**一直在跑、`rc` 一直是 0、
#    其实什么都没判**）—— `shell_verify`（有效后退化 ⇒ 已改盖章式）· **`cover_gap` / `audit_drift` /
#    `audit_meta`**（后三件**从来没有 `__main__`** ⇒ 单跑 **0 行输出**、`rc` 恒 0 ⇒ **从未生效过**）。
# ⭐ 这一族里**「入口根本不存在」是机器能判的** ⇒ 本检查专管它；
#    另一半（入口在、但判据没牙）由 `tools/mut/_mut_*.py` ＋ 台账表 B 管 —— **两半合起来才闭环**。
# ⚠️ 清单**唯一出处 = 计划 `§22.1` 的 `foreach ($t in @(...))`** ⇒ ⛔ 别在这里另抄一份（抄必漂）。
GATE_LIST_RE = re.compile(r"foreach\s*\(\s*\$t\s+in\s*@\(([^)]*)\)")
GATE_RULER_DIR = "tools/audit"
#: ⚠️ **判据必须是「入口那一行」的正则，⛔ 不能用子串 `"__main__" in src`** ——
#:    2026-09-24 被 `_mut_docaudit` 的 `M9` **当场抓到**：把靶的入口整段截掉，本检查**居然不报**，
#:    因为**件说明（docstring）里也写着 `__main__` 这个词** ⇒ 子串测试把"注释里提到"当成了"入口在"。
#:    ⭐ 这正是本仓「存在性检查／整页 `in` 全是假绿温床」（`§十二`）的又一例。
GATE_GUARD_RE = re.compile(r"^if\s+__name__\s*==\s*['\"]__main__['\"]\s*:", re.M)


def _gate_blocks() -> list[list[str]]:
    """→ 计划里**每一处** `foreach ($t in @(...))` 的项名（通常 §22.1 一处 ＋ 接手开场白一处）。"""
    p = REPO_ROOT / PLAN_DOC_REL
    text = p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""
    return [[x.strip().strip("'\"") for x in m.group(1).split(",") if x.strip()]
            for m in GATE_LIST_RE.finditer(text)]


#: ⭐⭐ 2026-10-01（`TAIL-204` 入场实测）：`T17` 原先**只认 `foreach` 清单** ⇒ 漏掉了**第二份闸门清单** ——
#:    计划 `§13.6` 的「**入门口令**」里**逐行写着**要跑的件（`tools\oneoff\_run_rulers.py` ·
#:    `tools\audit\acc_report.py` · … · `tools\audit\audit_work.py`）。
#:    实测：口令列着 `audit_work.py`，而那件**是个没有 `__main__` 的模块** ⇒ 单跑 **0 行输出**、
#:    `rc` 恒 0 ⇒ **第五例僵尸闸门**，只因口令不是 `foreach` 而**整批漏网**（接手人会"以为它判过了"）。
#:    ⇒ 本检查扩**第二半**：口令代码块里出现的 `tools/<dir>/<name>.py` 也逐条查「在位 ＋ 有入口」。
HANDOFF_ANCHOR = "入门口令（可复制）"
#: ⭐⭐ 2026-10-02 **订正锚**（当天**连着踩了两层** · 都留在这儿，因为教训值钱）：
#:  **第一层（裸词锚）**：原文锚是 `"入门口令"`，`text.find()` 取**全篇第一处** ——
#:    当天 §0.2 新增的一段里只提了一句"上面那份**入门口令**" ⇒ **锚被挪到那段**，
#:    紧随其后那个代码块里**一条 `tools/*.py` 都没有** ⇒ **本半静默空扫**
#:    （`_mut_docaudit` 的 `M17` 当场从"必红"变"**未命中**"= **判据自己瞎了，而它看上去是绿的**）。
#:  **第二层（子串锚）**：改成块标题 `"入门口令（可复制）"` 还不够 —— 它仍是**子串**，
#:    实测全篇出现 **2 次**：① **修订行正文里引了一句** ② **块标题本身**；
#:    `find()` 命中的是**正文那处**，而它后面那个 ``` 块**恰好**就是真口令块 ⇒
#:    **"看着扫到 8 条、其实锚已经错位"**（把块标题改名 ⇒ 它照样扫得到 ⇒ 变异 `M18` 抓不到）。
#:  ⇒ **最终口径 = 整行锚**：那一行去掉 `*` 与空白后**逐字等于** `HANDOFF_ANCHOR` 才算（正文引一句**不算**）
#:    ＋ **空扫自证**（扫不到命令 ⇒ 判红）。⛔ 别再退回"子串"或"裸词"。
#:  ⚠️ 这是本仓最贵那族病（「检查在跑，其实扫空集」，见 `T18` 立条说明）的又一例 ——
#:     **锚必须锚到"结构性位置"，⛔ 不是锚到"某个词"**：词会被正文抢走，结构不会。
HANDOFF_CMD_RE = re.compile(r"tools[\\/]([\w]+)[\\/]([\w_]+)\.py")


def _handoff_commands() -> list[str]:
    """→ 计划「入门口令」代码块里出现的 `tools/<dir>/<name>.py`（相对路径 · 去重排序）。

    ⚠️ **锚 = 整行**（见上方两层订正）：`ln.strip().strip("*").strip() == HANDOFF_ANCHOR`
       ⇒ 正文里**引一句**不算，只有**标题那一行**算。
    ⚠️ 空集**不是"没问题"** —— 调用方必须当红报（2026-10-02 加）。
    """
    p = REPO_ROOT / PLAN_DOC_REL
    if not p.exists():
        return []
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    for i, ln in enumerate(lines):
        if ln.strip().strip("*").strip() != HANDOFF_ANCHOR:      # ⭐ 整行锚（⛔ 不是子串）
            continue
        for j in range(i + 1, min(i + 6, len(lines))):           # 标题后不远处就是 ``` 开栏
            if not lines[j].startswith("```"):
                continue
            for k in range(j + 1, len(lines)):
                if lines[k].startswith("```"):
                    block = "\n".join(lines[j + 1:k])
                    return sorted({f"tools/{d}/{n}.py"
                                   for d, n in HANDOFF_CMD_RE.findall(block)})
            return []
    return []


def check_gate_liveness() -> list[dict]:
    """`T17` · **闸门清单里每一把尺子都必须真有入口**（红）。

    ⭐ 判据：那件**在位** ＋ 有 `if __name__ == \\"__main__\\"` ＋ 件里有 `print(`
    （⛔ 有入口却一句不打 ⇒ 人看不见它在判什么 —— 另一种空转）。
    ⭐ 两份清单都查：① `§22.1` 的 `foreach`（按件名，落在 `tools/audit/`）② **`§13.6` 入门口令里的命令行**
    （按相对路径 —— 见 `HANDOFF_ANCHOR` 上方注释）。
    """
    def hit(what: str, why: str, fix: str) -> dict:
        return {"code": "T17", "side": "仓", "rel": PLAN_DOC_REL, "line": 1,
                "what": what, "why": why, "fix": fix, "level": RED, "text": ""}

    blocks = _gate_blocks()
    out: list[dict] = []
    if not blocks:
        out.append(hit("找不到闸门清单（`§22.1` 的 `foreach`）",
                       "清单是唯一出处 ⇒ 没了就没法判「哪些尺子在闸门里」",
                       "恢复 `foreach ($t in @(…))` 那一段"))
    for names in blocks:
        for n in names:
            f = REPO_ROOT / GATE_RULER_DIR / f"{n}.py"
            if not f.exists():
                out.append(hit(f"闸门里的 `{n}` 在 `{GATE_RULER_DIR}/` 里不存在",
                               "清单指的件不在 ⇒ 那一行跑起来是报错或被跳过（⛔ 不是「在判」）",
                               f"补上 `{GATE_RULER_DIR}/{n}.py`，或把它从清单里删掉"))
                continue
            src = f.read_text(encoding="utf-8", errors="replace")
            m = GATE_GUARD_RE.search(src)
            if m is None:
                out.append(hit(f"`{n}.py` **没有 `__main__`** ⇒ 跑它是空转",
                               "0 行输出、`rc` 恒 0 —— 而它在闸门清单里 ⇒ 人会以为它判过了"
                               "（2026-09-24 实测三例：`cover_gap` / `audit_drift` / `audit_meta`）",
                               f"给 `{GATE_RULER_DIR}/{n}.py` 补 `main()` ＋ "
                               "`if __name__ == \"__main__\":`"))
            elif "print(" not in src:
                # ⚠️ 这一条是**弱判据**（`print(` 可能在件里任何地方）—— 它能抓的只是"件里根本没有输出"，
                #    抓不了"入口那条路不打印"。⭐ 试过"只看入口之后有没有 print(" ⇒ **12 把尺子全被误判**
                #    （打印都写在 `main()` 里，守卫那几行只是 `sys.exit(main())`）⇒ 已退回弱判据。
                #    ⛔ 别为了"更严"把弱判据升级成错判据 —— 「判据绿」不等于「判得对」。
                out.append(hit(f"`{n}.py` 有入口却**一句都不打**",
                               "看不见它在判什么 ⇒ 另一种空转",
                               "让它正常时也打一行结论（件名 ＋ 判定）"))
    # ⭐ 第二半（2026-10-01）：**「入门口令」里逐行写的闸门命令**同样要"真有入口"
    #    （它是一份**独立的**清单 —— 不在 `foreach` 里，故原先无人守）。
    cmds = _handoff_commands()
    if not cmds:
        # ⭐ 2026-10-02 补：**空扫自证** —— 本仓最贵的假绿就是「检查在跑，其实扫空集」
        #    （见 `T18` 立条说明）；空扫时下面那条逐件核对**什么都没判**，而它看上去是绿的。
        out.append(hit("入门口令里**一条 `tools/*.py` 都没扫到** ⇒ 本半在**空扫**（判据瞎了）",
                       "空扫 = 上面那条逐件核对**一个字都没判**，而它看上去是绿的"
                       "（2026-10-02 实测：§0.2 里提了一句「入门口令」⇒ 裸词锚被挪走 ⇒ 这半瞎了半天）",
                       f"核对锚 `{HANDOFF_ANCHOR}` 与紧随其后那个代码块；"
                       "改动过口令文案 ⇒ 把锚同批对齐（⛔ 别让本半静默空扫）"))
    for rel in cmds:
        f = REPO_ROOT / rel
        if not f.exists():
            out.append(hit(f"入门口令里的 `{rel}` **不存在**",
                           "口令让人跑一个不存在的件 ⇒ 那一行是报错或被跳过（⛔ 不是「在判」）",
                           "核对路径；件改名/搬家了就同批改口令"))
            continue
        hsrc = f.read_text(encoding="utf-8", errors="replace")
        if GATE_GUARD_RE.search(hsrc) is None:
            out.append(hit(f"入门口令里的 `{rel}` **没有 `__main__`** ⇒ 跑它是空转",
                           "0 行输出、`rc` 恒 0 —— 而口令让人**每条都跑** ⇒ 人会以为它判过了"
                           "（2026-10-01 `TAIL-204` 入场实测：口令列着 `audit_work.py`，"
                           "而那件一直是个没有入口的模块 = 第五例僵尸闸门）",
                           f"给 `{rel}` 补 `main()` ＋ `if __name__ == \"__main__\":`，"
                           "或把该行从口令里去掉"))
    if len(blocks) > 1 and any(set(b) != set(blocks[0]) for b in blocks[1:]):
        out.append(hit("闸门清单在多处 `foreach` 里**不一致**",
                       "两处分叉 ⇒ 谁都不知道该跑哪一份（清单失去唯一出处）",
                       "对齐 —— 唯一出处 = `§22.1`"))
    return out


# ------------------------------------------------- T18 路径 / glob 常量体检（治「搬目录后常量失效」）
#
# ⭐ 2026-09-24 立（源头 = `work/30-troubleshooting/排查-尺子与规则的过期清单-20260924.md` §一 的**元发现**）：
#   当天查出的三处失效**同一个根因** —— `tools/audit/` 的**路径 / glob 常量在 `TAIL-58` 搬目录后没跟改**
#   （`doc_audit` 曾写 `tools/doc_audit.py` · `cover_gap` 曾写 `tools/cover_gap.py` ·
#    `_mut_prg_form` 曾写 `tools/prg_form_audit.py`）⇒ 症状**全是假绿**：「检查在跑，其实扫的是空集」。
#   ⚠️ **立本条当天就抓出第 4 例**：`SCAN_GLOBS` 里的 `.codebuddy/memory/CHANGELOG.md` 是**搬迁前的旧地址**
#      （该件现址 = `ops/changelog.md`，见 `README.md`「工程基准档」那行）⇒ 那条 glob **一条都不命中**。
#
# ⭐ 判据（**静态、秒级** ⇒ 进 `doc_audit`，每轮自动跑）：
#   · `path`：常量指向的件 / 目录**必须存在**；
#   · `glob` / `glob_delivery`：**必须至少命中 1 个真实件**（⛔ 空命中 = 那一片**从没被扫过**）；
#   · `path_tuple`：逐个查；`path_first` = 每项取**第 0 个元素**当路径（如 `DOC_BUDGETS`）。
#   ⭐ `TAIL-235` 丁-1 新增两档：`outside_prefix`（**仓外**根：在盘上真存在 ＋ 确实不在仓内）
#     与 `nonempty`（词表不许为空 —— 空词表 = 这条判据**看着在跑、其实等于没有**）。
# ⚠️ **只查登记在册的常量**（`GUARDED`）—— ⛔ **别自动扫"像路径的字符串"**：本仓有一批**故意**指向
#   已删件的字符串（如 `RETIRED_TERMS` 的 `print/sign.py`）⇒ 全自动必误报一片。
#   例外走 `GUARD_EXEMPT`（**每条写明理由**），与 `KNOWN_ABSENT` / `t7_expected.txt` 同款纪律。
GUARDED: tuple[tuple[str, str, str], ...] = (
    ("audit_common", "SCAN_GLOBS", "glob"),
    ("audit_common", "DELIVERY_GLOBS", "glob_delivery"),
    # ⚠️ `CANCELLED_DOC_GLOBS` **刻意不列**：它是 `SCAN_GLOBS` 的**别名**（`= SCAN_GLOBS`）⇒ 查一次即可。
    ("audit_common", "CANCELLED_SCAN_GLOBS", "glob"),
    ("audit_common", "CANCELLED_SKIP_RELS", "path_tuple"),
    ("audit_common", "LENIENT_GLOBS", "glob"),
    # ⚠️ `OUTSIDE_ROOTS` 是**仓外**根（不在 `REPO_ROOT` 下）⇒ ⛔ 不能用 `path` 档
    #   （那档判 `(REPO_ROOT / raw).exists()` ⇒ 永远不存在 ⇒ 天天假红）。
    #   它的"存在性"由 `T3` 的仓外白名单分支**逐条引用时**核（见 `audit_drift.check_paths`），
    #   而"这份登记本身没写坏"由本条的 `path_tuple` 核（文件件在不在）。
    ("audit_common", "OUTSIDE_ROOTS", "outside_prefix"),
    ("audit_common", "T3_OLD_PATH_HINTS", "nonempty"),
    # ⭐ 2026-10-05（`TAIL-236` 同批修 ①b）：两处新登记 ——
    #   · `ROOT_ALLOW` **不许为空**（空表 ⇒ `T24` 退化成"根上什么都报"，而它看着还在跑）；
    #   · `GITIGNORE_REL` **必须指到真件**（指错 ⇒ `T25` 静默扫空集 ＝ `T18` 那一族假绿）。
    ("audit_common", "ROOT_ALLOW", "nonempty"),
    ("audit_common", "GITIGNORE_REL", "path"),
    ("audit_meta", "ALWAYS_READ_DOCS", "path_tuple"),
    ("audit_meta", "CODE_DIRS", "path_tuple"),
    ("audit_meta", "DOC_BUDGETS", "path_first"),
    ("audit_meta", "RECEIPT_DIR", "path"),
    ("audit_meta", "THRESHOLD_DOC", "path"),
    ("cover_gap", "CLEARED_REGISTRY", "path"),
)

#: 例外（`"模块.常量"` → 理由）。⛔ 加例外必须写理由，且**别拿它掩盖"该修没修"**。
GUARD_EXEMPT: dict[str, str] = {}


def check_guard_constants() -> list[dict]:
    """`T18` · **登记在册的路径 / glob 常量必须解析得到真东西**（红）。

    ⭐ 它抓的是「**常量失效 ⇒ 检查静默扫空集**」这一族（本项目最贵的假绿）——
    ⚠️ 同类失效**每搬一次目录就可能复发一次**，而在此之前**没有任何尺子看得见**。
    """
    import importlib                                            # noqa: PLC0415

    if str(REPO_ROOT / GATE_RULER_DIR) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT / GATE_RULER_DIR))

    def hit(what: str, why: str, fix: str) -> dict:
        return {"code": "T18", "side": "仓", "rel": GATE_RULER_DIR, "line": 1,
                "what": what, "why": why, "fix": fix, "level": RED, "text": ""}

    out: list[dict] = []
    for mod_name, attr, kind in GUARDED:
        key = f"{mod_name}.{attr}"
        if key in GUARD_EXEMPT:
            continue
        try:
            mod = importlib.import_module(mod_name)
        except Exception as exc:                                # noqa: BLE001
            out.append(hit(f"`{key}` 所在模块 import 失败", str(exc)[:120], "修 import"))
            continue
        val = getattr(mod, attr, None)
        if val is None:
            out.append(hit(f"登记在册的 `{key}` **找不到**",
                           "常量被改名/删掉 ⇒ 本检查失去靶（⛔ 别静默跳过）",
                           f"改名了就把 `GUARDED` 一起改；不再需要就从 `GUARDED` 删掉并写进 `GUARD_EXEMPT`"))
            continue
        base = delivery_root() if kind == "glob_delivery" else REPO_ROOT
        if base is None:
            out.append(hit(f"`{key}` 无从核（交付面找不到）",
                           "交付面不在位 ⇒ 那一片没人扫", "先修交付面路径（本机 = `.env` / `audit_common`）"))
            continue
        # ⚠️ 只按**容器**判断：`CLEARED_REGISTRY` 是 `Path`、其余是 `str` / `tuple` / 元组列表
        items = list(val) if isinstance(val, (tuple, list, set, frozenset)) else [val]
        for item in items:
            raw = str(item[0] if kind == "path_first" else item)
            if kind.startswith("glob"):
                if not any(p.is_file() for p in base.glob(raw)):
                    out.append(hit(f"`{key}` 里的 glob `{raw}` **一条都不命中**",
                                   "那一片**从没被扫过**（= 假绿入口；⚠️ 2026-09-24 立本条当天就抓出 "
                                   "`CHANGELOG.md` 一例：**旧地址搬家后没跟改**）",
                                   f"核对路径（多半是搬迁/改名后没同步）或把 `{raw}` 从常量里删掉"))
            elif kind == "outside_prefix":
                # ⭐ 仓外根（`D:/dev/.归档-mtrl` 这类）**不在 REPO_ROOT 下** ⇒ 只核两件事：
                #   ① 它在**盘上真的存在**（否则 `T3` 的仓外分支恒黄）；
                #   ② 它**确实不在仓内**（否则就该走仓内分支 ⇒ 两套口径）。
                  # ⛔ 判“在不在仓内”**不能写 `base / raw`** —— 那是**绝对路径**，`pathlib` 遇绝对路径
                  #    会**整条替换**（`REPO_ROOT / "D:/…"` == `D:/…`）⇒ 恒判“在仓内”＝天天假红。只能按父子关系判。
                # ⚠️ ⛔ 换机时仓外根**必然不同** ⇒ 本条报"不存在"是**如实记账**，不是缺陷；
                #    处置 = 改 `OUTSIDE_ROOTS` 常量（阈值表那一行同步）。
                rp = Path(raw).resolve()
                inside = rp == REPO_ROOT or REPO_ROOT in rp.parents
                if not rp.exists():
                    out.append(hit(f"`{key}` 里的仓外根 `{raw}` **在盘上不存在**",
                                   "`T3` 的仓外白名单分支会恒报「找不到」⇒ 那一片等于没登记",
                                   f"改 `audit_common.OUTSIDE_ROOTS`（换机必改；`ops/阈值表.md` 同步）"))
                elif inside:
                    out.append(hit(f"`{key}` 里的 `{raw}` **其实在仓内**",
                                   "它在仓内就该走仓内分支（红）⇒ 登记成仓外 = 给幽灵开了后门",
                                   "把它从 `OUTSIDE_ROOTS` 删掉"))
            elif kind == "nonempty":
                if not str(item).strip():
                    out.append(hit(f"`{key}` 里有空项",
                                   "空词表 = 这条豁免**对任何行都不生效** ⇒ 判据看起来在跑、其实等于没有",
                                   "补词，或把这项从 `GUARDED` 删掉"))
            elif not (base / raw).exists():
                out.append(hit(f"`{key}` 指向的 `{raw}` **不存在**",
                               "路径常量失效 ⇒ 用它的检查**静默扫空集**（本项目最贵的一类假绿）",
                               "修路径（或改名后同步常量）"))
    return out


def main(argv: list[str] | None = None) -> int:
    """**单跑本模块的检查**（`T5`/`T6`/`T9`/`T10`/`T11`/`T12`/`T13`/`T17`/`T18`/`T21`/`T22`/`T23`）。

    ⚠️ 2026-09-24（自查一轮）：`T17` 与 `T18` 是**同一天**新立的两条，而首版只把 `T17` 塞进了本入口
    ⇒ **单跑 `audit_meta.py` 时 `T18` 是哑的**（只在 `doc_audit` 里被动生效）= 同一件事做了一半。
    现补齐，并把上面那句 docstring 与**实际调用面**对齐 —— ⛔ 这类"说明与代码各说各话"
    正是本轮的靶（`T17`/`T18` 治的就是"看起来在判"）。

    ⚠️ 2026-09-24 补：此前本件**没有 `__main__`** ⇒ 收工闸门清单里 `audit_meta.py` 那一行是**空转**
    （**0 行输出 · rc 恒 0**）—— 它作为**模块**被 `doc_audit` 调用时是有用的，**单跑则什么都没判**。
    ⭐ 同族已有四例（症状同款：**一直在跑、rc 一直是 0、其实什么都没判**）：
    `shell_verify` · `cover_gap` · `audit_drift` · 本件。
    ⚠️ 本件只是**单跑入口** —— ⛔ **不另写一套判定**；⚠️ `T14`/`T15` 不在这里（在 `audit_work.py`）。
    """
    import acc_report as ar                                        # noqa: PLC0415
    cases = set(ar.load_json(ar.resolve_baseline(None)).get("cases") or {})
    raw = (check_file_sizes() + check_rule_origins() + check_doc_budgets()
           + check_report_receipts() + check_doc_layout() + check_drop_zones()
           + check_tail_ledger(cases)
           + check_plan_process() + check_line_walls() + check_line_splices()
           + check_gate_liveness() + check_guard_constants() + check_live_machine())
    reds = [h for h in raw if h["level"] == RED]
    yellows = [h for h in raw if h["level"] == YELLOW]
    print("=" * 78)
    print(" audit_meta 单跑 —— T5/T6/T9/T10/T11/T12/T13/T17/T18/T21/T22/T23/T24"
          "（⚠️ T1–T4/T8 在 `audit_drift` · T7 在 `cover_gap` · T14/T15 在 `audit_work`）")
    print("=" * 78)
    print(f"必须修 {len(reds)} · 疑似 {len(yellows)}")
    for h in reds + yellows:
        print(f"  [{h['code']}] {'红' if h['level'] == RED else '黄'} {h['rel']}:{h['line']}  {h['what']}")
        print(f"        {h['why']} → {h['fix']}")
    return 1 if reds else 0


if __name__ == "__main__":
    sys.exit(main())
