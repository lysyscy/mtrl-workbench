#!/usr/bin/env python
"""`doc_audit` 台账与行数检查 —— `T5` 单文件行数纪律 · `T6` 尾巴台账（计划主文档 §15）。

⚠️ **纯搬运**（自 `doc_audit.py` 拆出，无逻辑改动）。常量见 `audit_common.py`。
"""

from __future__ import annotations

import re
import sys

from audit_common import (
    HANDBOOK_REL, LEDGER_NAME, LEDGER_REL, RED, REPO_ROOT, TAIL_MIN_CELLS,
    TAIL_SCHEDULE_RE, TAIL_STAGE_RE, YELLOW, delivery_root,
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
RULE_DOC_REL = ".workbuddy/memory/MEMORY.md"
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
DOC_BUDGETS: tuple[tuple[str, int, str], ...] = (
    ("README.md", 240, "inject"),                              #: ⛔ 现值**别手抄** ⇒ 要现值跑 `doc_audit`（`T10` 会报）
    (".workbuddy/memory/MEMORY.md", 200, "inject"),             #: ⛔ 同上（现值由 `T10` 报）
    (".workbuddy/plans/执行情况-主文档.md", 200, "must"),        #: ⛔ 同上
    (".workbuddy/memory/MEMORY-细则.md", 420, "must"),          #: ⛔ 同上
    (".workbuddy/plans/开发计划-主文档.md", 1800, "must"),   # ⭐⭐ 2026-09-29 **用户裁定 `A`：1700 → 1800**
                                                          #:   （文档审计 §五之补 · ①）**理由 = 容量**：台账按设计每条一行，
                                                          #:   09-29 一天新立/销号 **19 条**尾巴 ⇒ 顶穿 8 行是它**该长的样子**；
                                                          #:   ⛔ 「搬叙事」已证伪（§15 §四 销号行受 `T6` 保护、一行不能搬；
                                                          #:   那三处叙事各是一整行）⇒ ⛔ 不许不明说地超着，故**明说调到 1800**。
                                                          #: ⭐ 2026-09-23 **统一成 1700**：
                                                          #: 此前 `T10` 用 1800、`T13` 用 1700
                                                          #: （同一件事两处写）⇒ 现已并成一个数       #: ⛔ **现值别手抄进注释** —— 2026-09-24 实测 **1510**，这里曾写「现 ~1746」（09-23 瘦身前的值）
                                                          #: ⇒ **手抄的数字必漂**；要现值就跑 `doc_audit`（`T10` 会报）。
)


def check_doc_budgets() -> list[dict]:
    """`T10` · **文档读预算** —— "每会话必读"的文档不得超过它那份预算。

    ⭐ 为什么这条比 `T5`（代码行数）重要：**代码长了我可以只读一个函数；文档长了我只能整份读**
       —— 而"整份读"这件事的失败方式很特别：**我不读，我改去 grep** ⇒ 于是**没被 grep 到的东西就永久丢了**
       （2026-09-21 实测到过：三条待办只活在对话里、`计划` 里 0 处命中）。
    """
    hits: list[dict] = []
    for rel, budget, tier in DOC_BUDGETS:
        p = REPO_ROOT / rel
        if not p.exists():
            hits.append({"code": "T10", "side": "仓", "rel": rel, "line": 1,
                         "what": f"文档不存在（预算 {budget} 行 · {tier} 档）",
                         "why": "被登记为必读的文档不见了 ⇒ 接手的人读不到",
                         "fix": "恢复它，或从 `DOC_BUDGETS` 里撤下（撤下要同步改 `ops/阈值表.md`）",
                         "level": YELLOW, "text": ""})
            continue
        n = len(p.read_text(encoding="utf-8", errors="replace").splitlines())
        if n <= budget:
            continue
        hits.append({"code": "T10", "side": "仓", "rel": rel, "line": 1,
                     "what": f"{n} 行（预算 {budget}·{tier} 档）",
                     "why": ("**每会话注入档**超预算 ⇒ 它天天吃上下文，且**没有检索能绕开**"
                             if tier == "inject" else
                             "**必读档**超预算 ⇒ 它会退化成\"读不完 ⇒ 只 grep ⇒ 没搜到的就丢了\""),
                     "fix": "把**历史叙事**挪到 `artifacts/` 或 memory 日志（⛔ 别删真东西）；"
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


#: `plans/` 下**只许**这两份活文档（其余一律必须 `归档-` 打头）
PLANS_LIVE: tuple[str, ...] = ("开发计划-主文档.md", "执行情况-主文档.md")
#: 根目录**允许**出现的 `.md`（文档地图；⛔ 别在根上散落别的 md）
ROOT_MD_ALLOW: tuple[str, ...] = ("README.md",)
#: `memory/` 下允许的 `.md` 与子目录（日志必须进 `journal/`）
MEMORY_MD_ALLOW: tuple[str, ...] = ("MEMORY.md", "MEMORY-细则.md", "CHANGELOG.md")
MEMORY_DIR_ALLOW: tuple[str, ...] = ("journal",)
#: ⭐ `work/` 五区（Agent 工作记录 · 文档架构审计 2026-09-22 P2：五类缺三类是乱建文件的根因）
WORK_DIR_ALLOW: tuple[str, ...] = ("00-scratch", "10-designs", "20-experiments",
                                   "30-troubleshooting", "40-decisions")
#: 各区 md 的命名前缀（`00-scratch` 不查 —— 临时件形态自由；`40-decisions` 只查 D 开头）
WORK_NAME_PREFIX: dict[str, tuple[str, ...]] = {
    "10-designs": ("设计-",),
    "20-experiments": ("实验-",),
    "30-troubleshooting": ("排查-",),
    "40-decisions": ("D",),
}


def _t12(rel: str, what: str, why: str, fix: str) -> dict:
    return {"code": "T12", "side": "仓", "rel": rel, "line": 1,
            "what": what, "why": why, "fix": fix, "level": YELLOW, "text": ""}


def check_doc_layout() -> list[dict]:
    """`T12` · **文档分层与命名约定**（2026-09-21 立 · 文档体系重构的落地闸门）。

    ⭐ 依据 = `README.md` 的**四层**（① 注入 ② 按需 ③ 留痕 ④ 产物）：
      · `plans/` 下**只许两份活文档**，其余**必须 `归档-` 打头**（⚠️ 这条纪律早就写在
        `MEMORY-细则.md §五`「⛔ 不许私自新建文档」里，但**此前没有任何尺子看着它** ⇒ 本次立 T12）；
      · `memory/` 下**日志必须进 `journal/`**（⭐ `journal/` = 只追加不回读层 —— 混在 `memory/` 根下时，
        没人分得清"这是纪律还是流水账"，这正是用户报「文档乱」的机制之一）；
      · 仓库根**只许 `README.md`** 一份 md。

    ⚠️ 为什么是**黄**而不是红：布局是**组织形式**问题（不是对错），而且"新加一份文档"有时是正当的
       ⇒ ⭐ 与 `T5`/`T10` 同款哲学：**可能定错的不该挡合入，但必须被看见**；
       要新增层级 ⇒ 先改 `README.md` 的四层表与这里的三张白名单（⛔ 别绕过）。
    """
    hits: list[dict] = []
    plans = REPO_ROOT / ".workbuddy" / "plans"
    if plans.is_dir():
        for f in sorted(plans.glob("*.md")):
            if f.name not in PLANS_LIVE and not f.name.startswith("归档-"):
                hits.append(_t12(f".workbuddy/plans/{f.name}",
                                 "`plans/` 下出现了「第三份文档」",
                                 "`plans/` 只有两份活文档（计划 ＋ 执行情况），其余是**留痕** ⇒ "
                                 "多出来的第三份没人知道它是活文档还是留痕（`T6` 也只看计划那份）",
                                 "改名 `归档-<主题>-<日期>.md`（留痕），或并进两份活文档之一"))
    mem = REPO_ROOT / ".workbuddy" / "memory"
    if mem.is_dir():
        for f in sorted(mem.glob("*.md")):
            if f.name not in MEMORY_MD_ALLOW:
                hits.append(_t12(f".workbuddy/memory/{f.name}",
                                 "`memory/` 根下出现了非白名单的 md",
                                 "`memory/` 根只放**注入档与分册**；日志混在这里 ⇒ "
                                 "分不清「这是规则还是流水账」（用户报「文档乱」的机制之一）",
                                 "日志移到 `memory/journal/`（`YYYY-MM-DD.md`，⛔ 不改文件名）"))
        for d in sorted(x for x in mem.iterdir() if x.is_dir()):
            if d.name not in MEMORY_DIR_ALLOW:
                hits.append(_t12(f".workbuddy/memory/{d.name}/",
                                 "`memory/` 下出现了非白名单子目录",
                                 "`memory/` 只认 `journal/` 一个子目录",
                                 "并进 `journal/`，或改到别处（见 `README.md` 四层表）"))
    # ⭐ `work/` 五区（2026-09-22 审计 P2 的机器化落地）：子目录白名单 ＋ 各区命名前缀
    work = REPO_ROOT / ".workbuddy" / "work"
    if work.is_dir():
        for d in sorted(x for x in work.iterdir() if x.is_dir()):
            if d.name not in WORK_DIR_ALLOW:
                hits.append(_t12(f".workbuddy/work/{d.name}/",
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
                    hits.append(_t12(f".workbuddy/work/{zone}/{f.name}",
                                     "work 区文档命名不符（缺类型前缀）",
                                     "命名表是检索的抓手（审计 P2）—— 前缀错了 = 决策树对不上号",
                                     f"改名打头：{' / '.join(prefixes)}（如 `设计-主题-YYYYMMDD.md`）"))
    for f in sorted(REPO_ROOT.glob("*.md")):
        if f.name not in ROOT_MD_ALLOW:
            hits.append(_t12(f.name, "仓库根出现了白名单外的 md",
                             "根目录只放 `README.md`（文档地图）—— 根上散落的 md 没人维护、必然过期",
                             "并进 `README.md`，或按四层放到 `ops/` / `.workbuddy/` / `artifacts/`"))
    return hits


# ---------------------------------------------------------------- T6 尾巴台账


def _t6(rel: str, lineno: int, what: str, why: str, fix: str, text: str = "") -> dict:
    return {"code": "T6", "side": "仓", "rel": rel, "line": lineno,
            "what": what, "why": why, "fix": fix, "level": RED, "text": text}


def ledger_counts() -> dict[str, int] | None:
    """尾巴台账**四段各有多少行**（只数行，不做任何检查）。

    ⭐ 2026-09-24 从 `check_tail_ledger` 抽出：`T6` 用它核对顶部计数行，
    `audit_drift` 的 **`T4` 计数锚点**（黄档）用它核对**两份活文档**里手抄的尾巴计数
    ⇒ ⛔ **段解析与计数口径只留这一份**（别在别处再写一遍）。
    返回 `{"一": n, "二": n, "三": n, "四": n}`；台账 / 段找不到 ⇒ `None`。
    """
    path = REPO_ROOT / LEDGER_REL
    if not path.exists():
        return None
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
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


# ------------------------------------------------- T13 主文档「过程回潮」守卫

#: ⭐ 2026-09-22 立（用户问「为啥还是会有过期现象？是不是把太多过程塞到开发计划里了？」）：
#: 病灶**实测成立** —— 主文档曾 1773 行、270 行含日期叙事；过程一写死就过期
#: （`TAIL-07` 挂着「待做」两个周期才被人肉发现）。⇒ `§13.1/13.2` 早有「完成的就扔出去」的裁定，
#: 但**只有触发点、没有机器守** ⇒ 治法 = 过程**只许下沉** `归档-历史单元条目.md`（原处留指针），
#: 本条守卫盯两件事：
#:   (a) 主文档**行数预算** —— 超了 = 过程又塞回来了（黄 ⇒ 下沉）；
#:   (b) 标题里出现**过程词**（逐批记录 / 逐次记录 / 收官记录）⇒ 该块该下沉了（黄）。
PLAN_DOC_REL = ".workbuddy/plans/开发计划-主文档.md"
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


def check_gate_liveness() -> list[dict]:
    """`T17` · **闸门清单里每一把尺子都必须真有入口**（红）。

    ⭐ 判据：那件在 `tools/audit/` 里**在位** ＋ 有 `if __name__ == \\"__main__\\"` ＋ 件里有 `print(`
    （⛔ 有入口却一句不打 ⇒ 人看不见它在判什么 —— 另一种空转）。
    """
    def hit(what: str, why: str, fix: str) -> dict:
        return {"code": "T17", "side": "仓", "rel": PLAN_DOC_REL, "line": 1,
                "what": what, "why": why, "fix": fix, "level": RED, "text": ""}

    blocks = _gate_blocks()
    if not blocks:
        return [hit("找不到闸门清单（`§22.1` 的 `foreach`）",
                    "清单是唯一出处 ⇒ 没了就没法判「哪些尺子在闸门里」",
                    "恢复 `foreach ($t in @(…))` 那一段")]
    out: list[dict] = []
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
#   ⚠️ **立本条当天就抓出第 4 例**：`SCAN_GLOBS` 里的 `.workbuddy/memory/CHANGELOG.md` 是**搬迁前的旧地址**
#      （该件现址 = `docs/changelog.md`，见 `README.md`「工程基准档」那行）⇒ 那条 glob **一条都不命中**。
#
# ⭐ 判据（**静态、秒级** ⇒ 进 `doc_audit`，每轮自动跑）：
#   · `path`：常量指向的件 / 目录**必须存在**；
#   · `glob` / `glob_delivery`：**必须至少命中 1 个真实件**（⛔ 空命中 = 那一片**从没被扫过**）；
#   · `path_tuple`：逐个查；`path_first` = 每项取**第 0 个元素**当路径（如 `DOC_BUDGETS`）。
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
            elif not (base / raw).exists():
                out.append(hit(f"`{key}` 指向的 `{raw}` **不存在**",
                               "路径常量失效 ⇒ 用它的检查**静默扫空集**（本项目最贵的一类假绿）",
                               "修路径（或改名后同步常量）"))
    return out


def main(argv: list[str] | None = None) -> int:
    """**单跑本模块的检查**（`T5`/`T6`/`T9`/`T10`/`T11`/`T12`/`T13`/`T17`/`T18`）。

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
           + check_report_receipts() + check_doc_layout() + check_tail_ledger(cases)
           + check_plan_process() + check_gate_liveness() + check_guard_constants())
    reds = [h for h in raw if h["level"] == RED]
    yellows = [h for h in raw if h["level"] == YELLOW]
    print("=" * 78)
    print(" audit_meta 单跑 —— T5/T6/T9/T10/T11/T12/T13/T17/T18"
          "（⚠️ T1–T4/T8 在 `audit_drift` · T7 在 `cover_gap` · T14/T15 在 `audit_work`）")
    print("=" * 78)
    print(f"必须修 {len(reds)} · 疑似 {len(yellows)}")
    for h in reds + yellows:
        print(f"  [{h['code']}] {'红' if h['level'] == RED else '黄'} {h['rel']}:{h['line']}  {h['what']}")
        print(f"        {h['why']} → {h['fix']}")
    return 1 if reds else 0


if __name__ == "__main__":
    sys.exit(main())
