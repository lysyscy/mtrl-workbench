#!/usr/bin/env python
"""`doc_audit` 漂移检查 —— `T1` 幽灵用例号 · `T2` 已废除术语 · `T3` 幽灵路径 · `T4` 状态数字失配。

⚠️ **纯搬运**（自 `doc_audit.py` 拆出，无逻辑改动）。真源与常量见 `audit_common.py`。
"""

from __future__ import annotations

from pathlib import Path

from audit_common import (
    HANDBOOK_REL, KNOWN_ABSENT, LEDGER_REL, PATH_ROOTS, REPO_ROOT, RETIRED_TERMS, TOP_DIRS, YELLOW, RED,
    _ACC_ID_RE, _ACC_RE, _PATH_RE, _PLACEHOLDER, _STATUS_RE,
    _hit, delivery_root,
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


# ------------------------------------------------------------------- T3 路径


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
            if base.exists() and any(base.rglob(name)):
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
                            "fix": "跑 `python tools/doc_audit.py --block` 后替换该处",
                            "level": RED, "text": line.strip()})
        if must_have and not hits:
            out.append({"code": "T4", "side": "仓", "rel": rel, "line": 1,
                        "what": "（简略版里认不出四态）",
                        "why": "给用户看的那一页必须以真实数字开头（否则人只能靠猜）",
                        "fix": "在顶部写一行「绿 N · 红 N · 待建 N · 未绑定 N」",
                        "level": YELLOW, "text": ""})
    return out
