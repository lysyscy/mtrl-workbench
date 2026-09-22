"""`doc_audit` 的**工作记录区**检查 —— `T14`（scratch TTL / 落点合规）· `T15`（产物白名单 ＋ work 状态头）。

据 `D:\\mtrl-workbench-文档架构审计-20260922.md` §七-15（长期维护）落地：
- `T14`：`work/00-scratch/` 里的件**超 14 天**未升档/未删 ⇒ 黄；`tools/` 根与 `logs/` 再出现散件 ⇒ 黄。
- `T15`：`artifacts/` 只许**工具生成物白名单**的 md；`work/` 五区的文档必须带**文头四行元信息**
  （读者 / 回答什么问题 / 什么时候读 / 状态 ＋ 关联 ID）—— 没有元信息的文档 = 下个 Agent 不知道它是否还活着。

⚠️ 与 `T12` 的分工：`T12` 管**目录与命名**（层级/前缀）；本件管**时间与元信息**（过期没、写没写头）。
⛔ 两条都是**黄**：形式问题该被看见，但不挡合入（同 `T5`/`T10` 哲学）。
"""

from __future__ import annotations

import time

from audit_common import REPO_ROOT, YELLOW

#: scratch 件存活上限（天）—— 审计 §六-9「TTL 14 天」
SCRATCH_TTL_DAYS = 14
#: `artifacts/` 允许出现的 md（工具生成物白名单 · ⛔ 过程类 md 去 `work/`）
ARTIFACTS_MD_ALLOW: tuple[str, ...] = ("变异覆盖台账.md", ".gitkeep")
#: `work/` 五区文档的文头必须齐这四个词（`README.md` 与 `D索引-*.md` 豁免）
WORK_HEADER_KEYS: tuple[str, ...] = ("读者", "回答", "何时读", "状态")
WORK_HEADER_EXEMPT: tuple[str, ...] = ("README.md", "D索引-")


def _hit(code: str, rel: str, what: str, why: str, fix: str) -> dict:
    return {"code": code, "side": "仓", "rel": rel, "line": 1,
            "what": what, "why": why, "fix": fix, "level": YELLOW, "text": ""}


def check_scratch_ttl() -> list[dict]:
    """`T14`：scratch 超期 ＋ 散件落点（tools 根 / logs）。"""
    hits: list[dict] = []
    scratch = REPO_ROOT / ".workbuddy" / "work" / "00-scratch"
    now = time.time()
    if scratch.is_dir():
        for f in sorted(scratch.rglob("*")):
            if not f.is_file() or f.name == ".gitkeep":
                continue
            days = (now - f.stat().st_mtime) / 86400
            if days > SCRATCH_TTL_DAYS:
                hits.append(_hit(
                    "T14", f".workbuddy/work/00-scratch/{f.name}",
                    f"临时件已放 {days:.0f} 天（TTL {SCRATCH_TTL_DAYS} 天）",
                    "临时区变垃圾场（审计 P2 的复发形态）—— 过期件会让下个 Agent 以为是当前线索",
                    "升档（设计→10-designs / 实验→20-experiments / 排查→30-troubleshooting）或删除"))
    tools = REPO_ROOT / "tools"
    if tools.is_dir():
        for f in sorted(tools.glob("*.py")):
            hits.append(_hit(
                "T14", f"tools/{f.name}",
                "`tools/` 根出现了散件脚本",
                "工具根只放 `*_expected.txt` 登记表与 README（审计 P6）—— 根上散件没人知道它属于哪一类",
                "归位：尺子→`audit/` · 变异→`mut/` · 探针→`probe/` · 一次性→`oneoff/`"))
    logs = REPO_ROOT / "logs"
    if logs.is_dir():
        for f in sorted(logs.iterdir()):
            if f.is_file() and f.suffix not in (".log", "") and f.name != ".gitkeep":
                hits.append(_hit(
                    "T14", f"logs/{f.name}",
                    "`logs/` 里出现了非日志文件",
                    "logs 只放服务日志（审计 P13：探测便签混入过一次）",
                    "移去 `.workbuddy/work/00-scratch/`"))
    return hits


def check_artifacts_and_headers() -> list[dict]:
    """`T15`：artifacts md 白名单 ＋ work 五区文档的文头四行元信息。"""
    hits: list[dict] = []
    art = REPO_ROOT / "artifacts"
    if art.is_dir():
        for f in sorted(art.glob("*.md")):
            if f.name not in ARTIFACTS_MD_ALLOW:
                hits.append(_hit(
                    "T15", f"artifacts/{f.name}",
                    "`artifacts/` 根出现了白名单外的 md",
                    "产物区 gitignore、可随时清 ⇒ 过程类 md 放这里**换机即丢**（审计 P1 的机制）",
                    "按类型归位：设计→`work/10-designs/` · 排查→`work/30-troubleshooting/` · 审计→`plans/archive/`"))
    work = REPO_ROOT / ".workbuddy" / "work"
    for zone in ("10-designs", "20-experiments", "30-troubleshooting", "40-decisions"):
        zdir = work / zone
        if not zdir.is_dir():
            continue
        for f in sorted(zdir.glob("*.md")):
            if f.name.startswith(WORK_HEADER_EXEMPT):
                continue
            head = "\n".join(f.read_text(encoding="utf-8", errors="replace").splitlines()[:15])
            missing = [k for k in WORK_HEADER_KEYS if k not in head]
            if missing:
                hits.append(_hit(
                    "T15", f".workbuddy/work/{zone}/{f.name}",
                    f"文头缺元信息：{' / '.join(missing)}",
                    "没有『读者/回答什么/何时读/状态』⇒ 下个 Agent 不知它是否还在研、该不该读（审计 §5.3-1）",
                    "补文头四行（模板见 `.workbuddy/work/README.md` §四）"))
    return hits


__all__ = ["ARTIFACTS_MD_ALLOW", "SCRATCH_TTL_DAYS", "WORK_HEADER_KEYS",
           "check_artifacts_and_headers", "check_scratch_ttl"]
