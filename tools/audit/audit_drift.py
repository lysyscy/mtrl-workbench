#!/usr/bin/env python
"""`doc_audit` 漂移检查 —— `T1` 幽灵用例号 · `T2` 已废除术语 · `T3` 幽灵路径 · `T4` 状态数字失配。

⚠️ **纯搬运**（自 `doc_audit.py` 拆出，无逻辑改动）。真源与常量见 `audit_common.py`。
"""

from __future__ import annotations

import os
import re
import sys
from functools import lru_cache
from pathlib import Path

from audit_common import (
    CANCELLED, CANCELLED_DOC_GLOBS, CANCELLED_SCAN_GLOBS, CANCELLED_SKIP_RELS, _is_lenient,
    HANDBOOK_REL, HARD_EXEMPT, KNOWN_ABSENT, LEDGER_REL, PATH_ROOTS, REPO_ROOT,
    RETIRED_TERMS, SOFT_EXEMPT, TOP_DIRS, YELLOW, RED,
    _ACC_ID_RE, _ACC_RE, _PATH_RE, _PLACEHOLDER, _STATUS_RE,
    _hit, delivery_root, iter_docs,
)


# --------------------------------------------------------------- T1 幽灵用例号


def check_acc_ids(cases: set[str], docs: list) -> list[dict]:
    hits = []
    for side, rel, path, lines, zones in docs:
        for i, line in enumerate(lines):
            for m in _ACC_RE.finditer(line):
                aid = m.group(0).rstrip("-")
                if aid in cases or aid in KNOWN_ABSENT or not _ACC_ID_RE.match(aid):
                    continue
                hits.append(_hit("T1", side, rel, path, i, lines, zones,
                                 what=aid, why="验收基线里没有这个用例号",
                                 fix="改成实际存在的用例号，或从基线里补上"))
    return hits


# ------------------------------------------------------------------- T2 术语


def check_terms(docs: list) -> list[dict]:
    hits = []
    for side, rel, path, lines, zones in docs:
        for i, line in enumerate(lines):
            for term, (why, now) in RETIRED_TERMS.items():
                if term in line:
                    hits.append(_hit("T2", side, rel, path, i, lines, zones,
                                     what=term, why=why, fix=f"改为：{now}"))
    return hits


# --------------------------------------------------------------- T8 已撤项复活
#
# ⭐⭐ 这条回答的是「**如何标记才能永久记住某功能已被取消**」：
#    真正的答案是「**别靠记忆，靠机器每次跑批把它端到你面前**」。
#
# ⚠️ 为什么必须有它（`T2` 不够）：`T2` 扫的是 **`.md` 文档**，而"复活"总是发生在**代码**里
#    （新建模块目录 / 把接口加回壳 / 把页面渲回来）⇒ 文档全对、代码已经长回来了。
# ⭐ 本项的判定**沿用同一套豁免纪律**（`HARD_EXEMPT` / `SOFT_EXEMPT` / 文件级 `LENIENT_GLOBS`）——
#    ⛔ 否则「为说'别再加回来'而提到它」的注释会被自己判红（那正是撤项最初的记录方式）。
def check_cancelled() -> list[dict]:
    """`T8` · **已撤项不得在代码里复活**（真源 = `audit_common.CANCELLED`）。

    `clean=True` 的：命中 ⇒ **红**（已清干净还出现 = 复活）。
    `clean=False` 的：命中 ⇒ **黄**（还有残骸，提醒去清 —— ⛔ 不是"这条错了"）。
    """
    out: list[dict] = []
    # ⭐ 2026-09-24（用户裁定 **A**）：**代码面 ＋ 活文档面**都扫 —— 文档面复用 `SCAN_GLOBS`
    #   （见 `CANCELLED_DOC_GLOBS` 的注释：原来文档面只由 `T2` 的 `RETIRED_TERMS` 管，
    #   而那张词表不含已撤页 / 端点名 ⇒ 「用现在时描述已撤功能」没有任何尺子看得见）。
    for pat in (*CANCELLED_SCAN_GLOBS, *CANCELLED_DOC_GLOBS):
        for p in sorted(REPO_ROOT.glob(pat)):
            if not p.is_file():
                continue
            rel = p.relative_to(REPO_ROOT).as_posix()
            if rel in CANCELLED_SKIP_RELS:
                continue
            # ⭐ 2026-09-24（用户裁定 **A** · 文档面）：**留痕档不扫** —— `T8` 抓的是「**复活**」，
            #   而 `plans/归档-*.md` / `memory/journal/` 里出现旧名是**有意的**（历史就该那样写）。
            #   ⚠️ 不加这行的话，扩面第一跑 = **36 条红，其中 34 条来自留痕档** = 纯噪音
            #   （实测：`归档-历史单元条目.md` 一家占 22 条）。
            if rel.endswith(".md") and _is_lenient(rel):
                continue
            try:
                lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            zones = ["current"] * len(lines)
            for i, line in enumerate(lines):
                for token, (why, fix, clean) in CANCELLED.items():
                    if token not in line:
                        continue
                    h = _hit("T8", "仓", rel, p, i, lines, zones,
                             what=f"已撤项 `{token}`", why=why, fix=f"改为：{fix}")
                    # ⭐ `clean` 档位**覆盖**豁免判定（豁免只管"行文在说它废了"，
                    #    而"还没清干净"这件事**与行文怎么写无关**）——
                    #    ⚠️ 但**行文本身在说它废了**的，仍不该报（那是撤项记录本身）。
                    if h["level"] == "忽略":
                        continue
                    h["level"] = RED if clean else YELLOW
                    if clean:
                        h["why"] = why + "；**该项已确认清干净** ⇒ 再出现即复活"
                    else:
                        h["why"] = why + "；⚠️ **残骸尚未清完**（黄）—— 清掉后把 `CANCELLED` 里该位改 `True`"
                    out.append(h)
    return out


# ------------------------------------------------------------------- T3 路径


@lru_cache(maxsize=8)
def _name_index(root_str: str) -> dict[str, tuple[Path, ...]]:
    """「根目录 → `{名字: (路径…)}`」的**一次性索引**（缓存）—— `audit_drift` 8.8 s 的根因就在这。

    ⚠️ 原先三处（`_path_exists` / `_resolve_md` / `_resolve_repo_path`）**每个引用各走一遍全仓**
       （`rglob(name)`）：引用几百个 ⇒ 几百遍 `rglob`，而且 `rglob` **拦不住 `.venv`**（它照样进去翻，
       过滤发生在**遍历之后**）⇒ 8.8 s 基本都耗在这。实测（2026-09-26）。
    ⭐ 口径**一字不变**：仍然"同名**唯一**才算命中"（`len(hits) == 1`）、仍然排除 `.venv` / `__pycache__`；
       区别只是**走一次树、问很多次**。文件与目录**都进索引**（原 `rglob` 也匹配目录名）。
    """
    idx: dict[str, list[Path]] = {}
    root = Path(root_str)
    for cur, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in {".venv", "__pycache__"}]   # ⭐ 剪枝：别进去
        for name in (*dirnames, *filenames):
            idx.setdefault(name, []).append(Path(cur) / name)
    return {k: tuple(v) for k, v in idx.items()}


def _path_exists(raw: str, roots: list) -> str:
    """→ `exact` 精确命中 / `same-name` 同名文件存在 / `` 都没有。"""
    for r in roots:
        for pre in PATH_ROOTS:
            for cand in ((r / pre / raw), (r / pre / raw).with_suffix("")):
                if cand.exists():
                    return "exact"
    name = Path(raw).name
    for r in roots:
        for pre in ("", "backend/"):
            base = r / pre
            if base.exists() and _name_index(base).get(name):
                return "same-name"
    return ""


def check_paths(docs: list) -> list[dict]:
    roots = [REPO_ROOT] + ([delivery_root()] if delivery_root() else [])
    hits = []
    for side, rel, path, lines, zones in docs:
        for i, line in enumerate(lines):
            for m in _PATH_RE.finditer(line):
                raw = m.group(1).replace("\\", "/")
                if _PLACEHOLDER.search(raw) or not any(raw.startswith(d) for d in TOP_DIRS):
                    continue
                got = _path_exists(raw, roots)
                if got == "exact":
                    continue
                hits.append(_hit("T3", side, rel, path, i, lines, zones,
                                 what=raw,
                                 why="在所有候选根下都找不到该文件（含同名匹配）"
                                     if not got else "只找到同名文件、无此相对路径",
                                 fix="核对文件名 / 补上真实路径 / 标注「非本工程」"))
    return hits


# --------------------------------------------------- T19 文档指针（**节号**）守卫
#
# ⭐⭐ 2026-09-24 立（`TAIL-84`）：`T3` 只核**文件在不在**，而文档里更常见的是「`X.md` §N」
#    这种**指到某一节**的引用 —— **节号烂了没有任何尺子看得见**。
#    实证：`MEMORY §十七` 写着「已下沉 `docs/runbook.md` §七」，而 runbook **止于 §六**
#    ⇒ 这条死指针**存活至今**，而"已下沉"的假象让它指的那六条坑差点**静默消失**。
# ⚠️ 判据必须**窄**（探针实测：全扫描面 140 条「`X.md` §N」引用，初版误报 115 条 = 82%）
#    ⇒ 三条纪律：
#    ① 引用要**紧贴**：`X.md` 与 `§N` 之间 ≤8 个字符 —— 否则 `A.md` → … → `§0` 这种串联会被误抓；
#    ② 节号在**被引件**或**当前文档**里任一存在 ⇒ 通过（引"本文档 §20.2"是合法写法，实测踩到）；
#    ③ 目标**解析不到 ⇒ 跳过**（那是 `T3` 的活，本守卫不为它二次报）；同行含 `SEC_REF_EXEMPT` ⇒ 跳过
#       （"叙述某指针已废 / 已订正"的行**必须**能引用那个坏节号，否则没法写清历史）。
SEC_REF_EXEMPT: tuple[str, ...] = ("不存在", "已废", "订正", "死指针", "原指针", "已删", "假陈述")
#: 解析目标 md 时依次尝试的前缀（文档常省略 `backend/` 与 `.codebuddy/`）
SEC_REF_PREFIXES: tuple[str, ...] = ("", "backend/", "backend/app/", ".codebuddy/")

#: 节号本体（中文数字 / 阿拉伯 · 都允许 `之N` 与 `.N` 后缀）
_SEC_NUM = (r"\d+(?:\.\d+)*"
            r"|[一二三四五六七八九十廿卅]+(?:之[一二三四五六七八九十]+)*")
#: 标题里的节号：`## 十七、…` / `## §十七 …` / `### §廿二之二` / `### 14.3 …`
_HEAD_SEC_RE = re.compile(r"^#{1,4}\s*(?:§\s*)?(" + _SEC_NUM + r")")
#: 引用：反引号里的 `X.md` **紧接着**（≤8 字符）`§N`
_REF_SEC_RE = re.compile(r"`([A-Za-z0-9_][\w./\\-]*\.md)`[^`\n]{0,8}?§\s*(" + _SEC_NUM + r")")


def _head_secs(p: Path) -> set[str]:
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()
    out = set()
    for line in text.splitlines():
        m = _HEAD_SEC_RE.match(line)
        if m:
            out.add(m.group(1))
    return out


def _resolve_md(raw: str, roots: list) -> Path | None:
    """→ 目标 md 路径；⛔ **解析不到返回 `None`**（本守卫不报它 —— 那是 `T3` 的活）。"""
    raw = raw.replace("\\", "/")
    for r in roots:
        for pre in SEC_REF_PREFIXES:
            cand = r / pre / raw
            if cand.exists():
                return cand
    name = Path(raw).name
    hits = [p for r in roots for p in _name_index(r).get(name, ())]
    return hits[0] if len(hits) == 1 else None


def check_section_refs(docs: list) -> list[dict]:
    """`T19` · **文档里的「`X.md` §N」必须真有那一节**（红）。

    ⚠️ 标题键缓存**只在本函数内**（⛔ 不做模块级缓存）—— 模块级缓存会让"变异脚本改坏了被引件、
    再跑本检查"读到**旧键** ⇒ **假绿**（本项目最贵的一类）。
    """
    roots = [REPO_ROOT] + ([delivery_root()] if delivery_root() else [])
    cache: dict[Path, set[str]] = {}

    def keys(p: Path) -> set[str]:
        if p not in cache:
            cache[p] = _head_secs(p)
        return cache[p]

    hits = []
    for side, rel, path, lines, zones in docs:
        own = keys(path)
        for i, line in enumerate(lines):
            if any(w in line for w in SEC_REF_EXEMPT):
                continue
            for m in _REF_SEC_RE.finditer(line):
                raw, sec = m.group(1), m.group(2)
                target = _resolve_md(raw, roots)
                if target is None or sec in keys(target) or sec in own:
                    continue
                hits.append(_hit("T19", side, rel, path, i, lines, zones,
                                 what=f"`{raw}` §{sec}",
                                 why="该引用指的那一节，在**被引件**与**本文档**里都没有"
                                     f"（被引件的节号：{'、'.join(sorted(keys(target))) or '（无标题）'}）",
                                 fix="改指向真实存在的节，或把节号删掉（改成件名指路）"))
    return hits



# --------------------------------------------------------- T4 交接文件状态数字


def _actual_states() -> dict[str, int] | None:
    try:
        import acc_report as ar
    except Exception:                                  # noqa: BLE001
        return None
    try:
        baseline = ar.load_json(ar.resolve_baseline(None))
        rp = ar.DEFAULT_RESULTS
        payload = ar.load_json(rp) if rp.exists() else {}
        states = ar.build_states(ar.collect_points(baseline),
                                 ar.collect_pending(baseline), payload)
    except SystemExit:
        return None
    tally = {"绿": 0, "红": 0, "待建": 0, "未绑定": 0}
    for pts in states.values():
        for st in pts.values():
            tally[st] += 1
    tally["合计"] = sum(tally.values())
    return tally


def check_status_line() -> list[dict]:
    """`T4` · **两份活文档里每一处四态数字**都必须等于实际（2026-09-19 **扩面**）。

    ⚠️ **为什么扩**：原实现只看「当前版本」行**后 8 行**里的**第一处**数字 —— 实测漏过一次：
    `执行情况-主文档.md` 的「接手起步」清单里还写着 **521 = 绿 447**（已过期一周），而 `T4` 报
    「必须修 0」。⇒ 现在**两份活文档的每一处**四态数字都核对，且**简略版（给用户看的那页）
    必须至少有一处**（它要以真实数字开头）。⛔ **归档件不查**（那里的旧数字是**正确的留痕**）。

    ⚠️ **认不出 / 拿不到真源 ⇒ 显式报黄**，绝不静默跳过 —— 静默跳过会让人把
    「没检查」读成「检查通过」（本项目已栽过两次的同一类错）。
    """
    actual = _actual_states()
    out: list[dict] = []
    if actual is None:
        return [{"code": "T4", "side": "仓", "rel": HANDBOOK_REL, "line": 1, "what": "（无法校验）",
                 "why": "拿不到真源：先跑全套 pytest 生成 artifacts/acc_results.json",
                 "fix": "跑 pytest 后再跑本工具", "level": YELLOW, "text": ""}]
    want = (actual["绿"], actual["红"], actual["待建"], actual["未绑定"])
    for rel, must_have in ((HANDBOOK_REL, True), (LEDGER_REL, False)):
        f = REPO_ROOT / rel
        if not f.exists():
            out.append({"code": "T4", "side": "仓", "rel": rel, "line": 1, "what": "（文件不存在）",
                        "why": "活文档缺失 ⇒ 无法校验状态数字", "fix": "恢复该文件",
                        "level": YELLOW, "text": ""})
            continue
        lines = f.read_text(encoding="utf-8").splitlines()
        hits = 0
        for i, line in enumerate(lines):
            m = _STATUS_RE.search(line)
            if not m:
                continue
            hits += 1
            got = tuple(int(g) for g in m.groups())
            if got != want:
                out.append({"code": "T4", "side": "仓", "rel": rel, "line": i + 1,
                            "what": "绿%d·红%d·待建%d·未绑定%d" % got,
                            "why": "实际是 绿%d·红%d·待建%d·未绑定%d（合计 %d）"
                                   % (want + (actual["合计"],)),
                            "fix": "跑 `python tools/audit/doc_audit.py --block` 后替换该处",
                            "level": RED, "text": line.strip()})
        if must_have and not hits:
            out.append({"code": "T4", "side": "仓", "rel": rel, "line": 1,
                        "what": "（简略版里认不出四态）",
                        "why": "给用户看的那一页必须以真实数字开头（否则人只能靠猜）",
                        "fix": "在顶部写一行「绿 N · 红 N · 待建 N · 未绑定 N」",
                        "level": YELLOW, "text": ""})
    return out


#: `T4` ④ 的靶文档
THRESHOLD_DOC = "ops/阈值表.md"
_CODE_EXT_RE = re.compile(r"([\w\u4e00-\u9fff/.\-]+\.(?:py|md|json|txt))")
_BACKTICK_RE = re.compile(r"`([^`]*)`")


def _resolve_repo_path(rel: str) -> Path | None:
    """阈值表里的路径多是**短式**（`tests/x.py` / `app/core/y.py`）⇒ 依次试 仓根 / `backend/`，再按**文件名**找唯一件。"""
    rel = rel.replace("\\", "/")
    for cand in (REPO_ROOT / rel, REPO_ROOT / "backend" / rel):
        if cand.exists():
            return cand
    name = Path(rel).name
    hits = list(_name_index(REPO_ROOT).get(name, ()))
    return hits[0] if len(hits) == 1 else None


def _check_threshold_doc() -> list[dict]:
    """`T4` ④（**黄**）：`ops/阈值表.md` 每行的数字必须能在它自称的「位置（真源）」里找到。

    ⛔ 真源栏写「同上」⇒ **报黄**（合法但**机器读不了**，人也要回看上一行 —— 本表的可核性全靠这一栏）；
    真源不是文件（如「计划 §9.5 ①」/「只作对照」）⇒ 跳过（那是文档指针，⛔ 不当错误报）。
    """
    doc = REPO_ROOT / THRESHOLD_DOC
    if not doc.exists():
        return [_anchor(THRESHOLD_DOC, 1, "（阈值表不存在）",
                        "本表是硬数字的唯一登记处 ⇒ 没了就没出处", "")]
    out: list[dict] = []
    for i, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1):
        if not line.startswith("|") or line.startswith("|---") or "| 数字 |" in line:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 5:
            continue
        m_num = re.search(r"([\d.]+)", cells[0])
        if not m_num:
            continue
        where = cells[3]
        if where.strip().startswith("同上"):      # ⚠️ 判据用 **startswith**（⛔ 别用子串：说明文字里提到"同上"会自伤）
            out.append(_anchor(THRESHOLD_DOC, i, "真源栏写了「同上」",
                               "机器读不了（人也得回看上一行）⇒ **写全文件名**（本表的可核性靠它）", line))
            continue
        files = [f for span in _BACKTICK_RE.findall(where) for f in _CODE_EXT_RE.findall(span)]
        if not files:
            continue                      # 真源不是文件 ⇒ 无法机核（不算错）
        num = m_num.group(1).rstrip(".")
        ok = False
        for rel in files:
            p = _resolve_repo_path(rel)
            if p is None:
                out.append(_anchor(THRESHOLD_DOC, i, f"真源文件找不到 → `{rel}`",
                                   "路径写错 / 件已搬走 ⇒ 这一行的数字**无从核**", line))
                continue
            if re.search(rf"(?<![\d.]){re.escape(num)}(?![\d])",
                         p.read_text(encoding="utf-8", errors="replace")):
                ok = True
        if not ok:
            out.append(_anchor(THRESHOLD_DOC, i, f"数字 **{num}** 在真源里找不到",
                               f"真源 = {'、'.join(files)} ⇒ 要么代码改了没回填本表、要么本表指错了件", line))
    return out


# ------------------------------------------- `T4` 追加：**计数锚点**（黄 · 2026-09-24 立）
#: 文档里**手抄的、有机器真值的计数** → 真值。⭐ 只收**四类**（⛔ 不贪多）：
#:  ① 尾巴计数（A/B/C/已销号）② `§22.1` 的**尺子把数**（与同一代码块的 `foreach` 项数自洽）
#:  ③ `U5` 登记条目数 ④ `ops/阈值表.md` **自己**（每行的数字必须能在它自称的真源里找到）。
#: ⚠️ **为什么必须机器判**：`T4` 原先只管**四态数字**，而这三类**同样会漂** —— 2026-09-24 **一天内实测两次**
#:  （`claim_audit` 的黄计数 · `§15` 的 `U5` 登记数 42↔43）⇒ 用户「按推荐」把它们钉住。
#: ⛔ **只报黄**（同 `T5`/`T10` 哲学：形式问题该被看见、不挡合入）。
_TAIL_ANCHOR_RE = re.compile(
    r"A 类\s*\*{0,2}(\d+)\*{0,2}\s*条\s*·\s*"
    r"B 类\s*\*{0,2}(\d+)\*{0,2}\s*条?\s*·\s*"
    r"C 类\s*\*{0,2}(\d+)\*{0,2}\s*条?\s*·\s*"
    r"已销号\s*\*{0,2}(\d+)\*{0,2}")
# ⛔ `_U5_ANCHOR_RE` **已撤**（2026-09-30 `TAIL-201`：`U5` 退场 ⇒ 那条锚点没了；理由见上面 ③ 处）
_FOREACH_RE = re.compile(r"foreach\s*\(\s*\$t\s+in\s+@\(([^)]*)\)")
_RULERS_JUDGE_RE = re.compile(
    r"\*{0,2}(\d+)\s*把尺子全\s*`rc=0`\*{0,2}\s*（[^）]*?合计\s*\*{0,2}(\d+)\s*把")


def _anchor(rel: str, line_no: int, what: str, why: str, text: str) -> dict:
    return {"code": "T4", "side": "仓", "rel": rel, "line": line_no, "what": what, "why": why,
            "fix": "改成真值，或该处改成「别写死、跑工具看」（⛔ 手抄的数字必漂）",
            "level": YELLOW, "text": text.strip()}


def check_count_anchors() -> list[dict]:
    """`T4` 追加（**黄**）：三类**计数锚点**必须等于机器真值（见上方常量注释）。"""
    from audit_meta import ledger_counts      # 局部导入：与 `T6` **共用同一份段解析口径**

    out: list[dict] = []
    docs = [(rel, REPO_ROOT / rel) for rel in (HANDBOOK_REL, LEDGER_REL)]
    docs = [(rel, f) for rel, f in docs if f.exists()]

    # ① 尾巴计数（真值 = 台账**实际段行数**）
    lc = ledger_counts()
    if lc is None:
        out.append(_anchor(LEDGER_REL, 1, "（台账读不到）", "计数锚点拿不到真源 ⇒ 无从核对", ""))
    else:
        want = (lc.get("一", 0), lc.get("二", 0), lc.get("三", 0), lc.get("四", 0))
        for rel, f in docs:
            for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                for m in _TAIL_ANCHOR_RE.finditer(line):
                    got = tuple(int(g) for g in m.groups())
                    if got != want:
                        out.append(_anchor(rel, i, "尾巴计数 A%d·B%d·C%d·已销号%d" % got,
                                           "台账实际是 A%d·B%d·C%d·已销号%d" % want, line))

    # ② `§22.1` 尺子把数（真值 = 同一代码块 `foreach` 的项数 ⇒ 应写「N 把 ＋ doc_audit ＝ N+1 把」）
    plan = REPO_ROOT / LEDGER_REL
    if plan.exists():
        lines = plan.read_text(encoding="utf-8").splitlines()
        n_rulers: int | None = None
        for line in lines:
            m = _FOREACH_RE.search(line)
            if m:
                n_rulers = len([x for x in m.group(1).split(",") if x.strip()])
                break
        found_judge = False
        for i, line in enumerate(lines, 1):
            m = _RULERS_JUDGE_RE.search(line)
            if not m:
                continue
            found_judge = True
            if n_rulers is None:
                out.append(_anchor(LEDGER_REL, i, "（找不到 `foreach`）",
                                   "判定行写了把数，但同文件里找不到 `foreach` 项数 ⇒ 无从核对", line))
            elif (int(m.group(1)), int(m.group(2))) != (n_rulers, n_rulers + 1):
                out.append(_anchor(
                    LEDGER_REL, i, "尺子把数 %s 把 / 合计 %s 把" % (m.group(1), m.group(2)),
                    "同一代码块的 `foreach` 实为 **%d** 项 ⇒ 应写「%d 把 ＋ `doc_audit` ＝ %d 把」"
                    % (n_rulers, n_rulers, n_rulers + 1), line))
        if not found_judge:
            out.append(_anchor(LEDGER_REL, 1, "（找不到判定行）",
                               "`§22.1` 的判定行不见了 ⇒ 尺子把数失去对照物", ""))

    # ③ ~~`U5` 登记条目数~~ —— ⛔ **已撤**（2026-09-30 `TAIL-201` 退场）：
    #    原来这里 import `ui_parity.U5_COUNT`，再核活文档里"登记 N 个规格件"那句。
    #    `U1`/`U5` 退场后那个常量不存在了 ⇒ 这条锚点连同 `_U5_ANCHOR_RE` 一起撤（⛔ 别留着 ——
    #    它会**先崩 import**：`ui_parity` 一拆，本尺子就起不来，而症状是"整把尺子报错"、不是"少一条检查"）。

    # ④ ⭐ `ops/阈值表.md` **自己**：每行的数字必须能在它自称的「位置（真源）」里找到。
    #    ⚠️ 为什么加：本表自称"硬数字的唯一集中登记处"，却**不被任何尺子扫**；2026-09-24 探针实测
    #       **24 行数值全对**（⇒ 那就顺手钉住，免得以后漂了没人知道）。
    out += _check_threshold_doc()
    return out


def main(argv: list[str] | None = None) -> int:
    """**单跑本模块的检查**（`T1`/`T2`/`T3`/`T4`/`T4'`(计数锚点)/`T8`）。

    ⚠️ 2026-09-24 补：此前本件**没有 `__main__`** ⇒ 收工闸门清单里 `audit_drift.py` 那一行是**空转**
    （**0 行输出 · rc 恒 0**）—— 它作为**模块**被 `doc_audit` 调用时是有用的，**单跑则什么都没判**。
    ⭐ 同族已有四例（症状同款：**一直在跑、rc 一直是 0、其实什么都没判**）：
    `shell_verify`（改盖章式）· `cover_gap`（补 `main`）· 本件 · `audit_meta`。
    ⚠️ 本件只是**单跑入口** —— ⛔ **不另写一套判定**，用的就是 `doc_audit` 调的同一批函数。
    """
    import acc_report as ar                                        # noqa: PLC0415
    cases = set(ar.load_json(ar.resolve_baseline(None)).get("cases") or {})
    docs = iter_docs()
    raw = (check_acc_ids(cases, docs) + check_terms(docs) + check_paths(docs) + check_section_refs(docs)
           + check_status_line() + check_count_anchors() + check_cancelled())
    reds = [h for h in raw if h["level"] == RED]
    yellows = [h for h in raw if h["level"] == YELLOW]
    print("=" * 78)
    print(" audit_drift 单跑 —— T1/T2/T3/T19/T4/T4' 计数锚点/T8"
          "（⚠️ T5–T7/T9–T18 分别在 `audit_meta` / `cover_gap` / `audit_work`）")
    print("=" * 78)
    print(f"必须修 {len(reds)} · 疑似 {len(yellows)}")
    for h in reds + yellows:
        print(f"  [{h['code']}] {'红' if h['level'] == RED else '黄'} {h['rel']}:{h['line']}  {h['what']}")
        print(f"        {h['why']} → {h['fix']}")
    return 1 if reds else 0


if __name__ == "__main__":
    sys.exit(main())
