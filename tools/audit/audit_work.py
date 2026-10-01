"""`doc_audit` 的**工作记录区**检查 —— `T14`（scratch TTL / 落点合规）· `T15`（产物白名单 ＋ work 状态头）。

据 `D:\\mtrl-workbench-文档架构审计-20260922.md` §七-15（长期维护）落地：
- `T14`：`work/00-scratch/` 里的件**超 14 天**未升档/未删 ⇒ 黄；`tools/` 根与 `logs/` 再出现散件 ⇒ 黄。
- `T15`：`artifacts/` 只许**工具生成物白名单**的 md；`work/` 四区的文档必须带**文头四行元信息**
  （读者 / 回答什么问题 / 什么时候读 / 状态 ＋ 关联 ID）—— 没有元信息的文档 = 下个 Agent 不知道它是否还活着。

⚠️ 与 `T12` 的分工：`T12` 管**目录与命名**（层级/前缀）；本件管**时间与元信息**（过期没、写没写头）。
⛔ 两条都是**黄**：形式问题该被看见，但不挡合入（同 `T5`/`T10` 哲学）。
"""

from __future__ import annotations

import sys
import time

from audit_common import RED, REPO_ROOT, YELLOW

#: scratch 件存活上限（天）—— 审计 §六-9「TTL 14 天」
SCRATCH_TTL_DAYS = 14
#: `artifacts/` 允许出现的 md（工具生成物白名单 · ⛔ 过程类 md 去 `work/`）
ARTIFACTS_MD_ALLOW: tuple[str, ...] = ("变异覆盖台账.md", ".gitkeep")
#: `work/` 四区文档的文头必须齐这四个词（`README.md` 与 `D索引-*.md` 豁免）
WORK_HEADER_KEYS: tuple[str, ...] = ("读者", "回答", "何时读", "状态")
WORK_HEADER_EXEMPT: tuple[str, ...] = ("README.md", "D索引-")

# ------------------------------------------------- T20 保留期与容量（2026-09-28 立）

#: `.codebuddy/backups/` 顶层**允许的条目数**（口径出处 = `README.md` §三/§四「留 5 份 · 月度清」）
BACKUP_KEEP = 5
#: 显式归档子目录（⛔ 不计入 `BACKUP_KEEP`；但会在报告里**如实打印它的件数与体积** —— 防"全塞进归档"糊弄）
BACKUP_ARCHIVE_PREFIXES = ("_归档-", "_旧快照归档-")
#: ⛔ 不计数：壳单文件基线由 `shell_verify` **自己**守 5 份（阈值表另有一行），不在本条重复管
BACKUP_SKIP_SUFFIXES = ("_壳单文件基线.html",)
#: ⛔ **另一用途 ⇒ 不计数**（2026-10-01 · `TAIL-204` 第 5 步）：`交付面-*` = **改交付面之前的**快照
#:   （原址 `artifacts/delivery-backups/`；第 5 步把它并到"备份唯一落点"）。
#:   ⚠️ 它与「**手工快照**留 5 份」**不是一件事** —— 混进同一个上限 ⇒ 上限**永远超**
#:   （实测：并入当天 22 > 5 ⇒ 立刻报黄，而这是**新搬进来**的、不是"又攒了一堆"）。
#:   ⇒ 与 `README.md` §三/§四 同批写明（口径改了才动计数范围，⛔ 不是放水）。
BACKUP_OTHER_PREFIXES = ("交付面-", "原型-备份-", "_smoke.js-备份-")
#: 同上：`.bak` 散件（改交付面/文档**之前**留的）—— 也属"另一种用途"
BACKUP_OTHER_SUFFIXES = (".bak",)
#: ⭐ 2026-10-01（`TAIL-204` 第 7 步）**撤掉**「`.workbuddy/scratch/` 活区规模」这半条判据（连常量一起） ——
#:   理由见 `check_retention()` 里那段说明：**它一直在扫一个不存在的目录** = 僵尸判据。
#: ⭐ `tools/oneoff/`（**一次性 / 留痕的堆场** · 处置口径见 `tools/README.md`）的提示线：超 ⇒ 黄**一行**。
#:   ⭐ 为什么管它（`TAIL-194` · 2026-09-29 结构审计 §三 `P1-8`）：它曾是**全仓唯一"没有保留期、也没有机器眼"
#:   的目录**（对照当时还在的仓级活区 `.workbuddy/scratch`：明写「保留期 14 天 ＋ 索引 README ＋ `T20`」）⇒ 只会一直堆。
#:   ⚠️ **件数**才是它的病（"翻不翻得动"的代理指标）；**容量不是瓶颈**（实测 1.2 MB）⇒ 容量线只是挡住
#:   "往里扔大文件"。⚠️ 阈值出处 = `ops/阈值表.md`（改数先改表）。
ONEOFF_MAX_FILES, ONEOFF_MAX_MB = 200, 5.0


def _hit(code: str, rel: str, what: str, why: str, fix: str) -> dict:
    return {"code": code, "side": "仓", "rel": rel, "line": 1,
            "what": what, "why": why, "fix": fix, "level": YELLOW, "text": ""}


def check_scratch_ttl() -> list[dict]:
    """`T14`：scratch 超期 ＋ 散件落点（tools 根 / logs）。"""
    hits: list[dict] = []
    scratch = REPO_ROOT / ".codebuddy" / "work" / "00-scratch"
    now = time.time()
    if scratch.is_dir():
        for f in sorted(scratch.rglob("*")):
            if not f.is_file() or f.name == ".gitkeep":
                continue
            days = (now - f.stat().st_mtime) / 86400
            if days > SCRATCH_TTL_DAYS:
                hits.append(_hit(
                    "T14", f".codebuddy/work/00-scratch/{f.name}",
                    f"临时件已放 {days:.0f} 天（TTL {SCRATCH_TTL_DAYS} 天）",
                    "临时区变垃圾场（审计 P2 的复发形态）—— 过期件会让下个 Agent 以为是当前线索",
                    "升档（设计→10-designs / 实验与排查→30-troubleshooting / 决策→40-decisions）或删除"))
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
                    "移去 `.codebuddy/work/00-scratch/`"))
    return hits


def check_artifacts_and_headers() -> list[dict]:
    """`T15`：artifacts md 白名单 ＋ work 四区文档的文头四行元信息。"""
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
    work = REPO_ROOT / ".codebuddy" / "work"
    for zone in ("10-designs", "30-troubleshooting", "40-decisions"):   # ⭐ 2026-10-01 五区 ⇒ 四区（撤 `20-experiments`）
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
                    "T15", f".codebuddy/work/{zone}/{f.name}",
                    f"文头缺元信息：{' / '.join(missing)}",
                    "没有『读者/回答什么/何时读/状态』⇒ 下个 Agent 不知它是否还在研、该不该读（审计 §5.3-1）",
                    "补文头四行（模板见 `.codebuddy/work/README.md` §四）"))
    return hits


def check_retention() -> list[dict]:
    """`T20` · **保留期与容量** —— ⭐ 治「口径写了『留 5 份』，却没有任何机器看得见」。

    背景（2026-09-28 文档审计 · `work/10-designs/设计-文档审计-20260928.md` §四-7）：
      `README.md` §三/§四 写着 `.codebuddy/backups/`「**留 5 份 · 月度清**」，而 2026-09-22 那份整改
      设计给出的验收判据**就是**「`backups/` 目录计数 ≤5（可数）」—— 却**从没被机器守过**
      ⇒ `TAIL-73` 销号时只验了"备份收敛到唯一点"、没验"≤5" ⇒ **43 个条目静默堆着**（含 09-18 的旧快照）。

    口径（⛔ 别自己另定一套）：
      · 计数对象 = `backups/` **顶层**条目（目录与散件都算）；
      · **不计**显式归档子目录（`_归档-*` / `_旧快照归档-*`）与壳单文件基线（后者由 `shell_verify` 自守）；
      · 归档子目录**照实打印件数与体积** —— 防"全塞进归档"把这条糊弄成假绿；
      · 上限 = `BACKUP_KEEP`（5，出处 = 根 `README.md`）。

    ⚠️ **黄**（与 `T5`/`T10`/`T12` 同款哲学：可能定错的不该挡合入，但**必须被看见**）。
    """
    hits: list[dict] = []
    backups = REPO_ROOT / ".codebuddy" / "backups"
    if backups.is_dir():
        counted, archived, face = [], [], []
        for e in sorted(backups.iterdir()):
            name = e.name
            if name.startswith(BACKUP_ARCHIVE_PREFIXES):
                archived.append(e)
                continue
            if name.startswith(BACKUP_OTHER_PREFIXES) or name.endswith(BACKUP_OTHER_SUFFIXES):
                face.append(e)                              # ⭐ 交付面改前快照：另一用途 ⇒ 不计数
                continue
            if name.endswith(BACKUP_SKIP_SUFFIXES):
                continue
            counted.append(e)
        if face:
            print(f"  （信息）`backups/` 交付面改前快照：{len(face)} 件"
                  f" —— ⛔ **另一用途、不计入上限**（口径见 `README.md` §三/§四）")
        if archived:
            n = sum(1 for a in archived for _ in a.rglob("*") if _.is_file())
            mb = sum(_.stat().st_size for a in archived for _ in a.rglob("*") if _.is_file()) / 1024 / 1024
            print(f"  （信息）`backups/` 显式归档：{len(archived)} 个子目录 · {n} 件 · {mb:.1f} MB"
                  f" —— ⛔ 归档不计入上限，但它**应当被清掉或定期复核**（见 `TAIL-134`）")
        if len(counted) > BACKUP_KEEP:
            names = " · ".join(x.name for x in counted[:8])
            hits.append(_hit(
                "T20", ".codebuddy/backups/",
                f"顶层 {len(counted)} 个条目 > 上限 {BACKUP_KEEP}（口径：留 {BACKUP_KEEP} 份 · 月度清）",
                "⭐ 口径在 `README.md` 写着、却没人守 ⇒ 只会继续长；本条是它的机器眼（2026-09-28 立）",
                f"把旧的**移进** `_旧快照归档-YYYYMMDD/`（可逆）或清掉；现值：{names}"))
    oneoff = REPO_ROOT / "tools" / "oneoff"
    if oneoff.is_dir():
        # ⭐⭐ 2026-09-30（用户「可以归档」）：**已入档的不计数** —— 口径与 `.codebuddy/backups/` 完全一致
        #    （那边有 `BACKUP_ARCHIVE_PREFIXES = ("_归档-", "_旧快照归档-")`）。
        #    ⚠️ 为什么这**不是"放松判据"**：`T20` 这一条的本意写得很清楚 ——「件数是**「翻不翻得动」**的代理指标」
        #       ⇒ 躺在 `_归档-YYYYMMDD/` 里的件**已经不在"堆"里**（且⛔ 一个字节都没删，随时可移回）。
        #    阈值仍是 200 件，改的只是**计数范围**；⭐ 而且下面**把入档件数照实打出来**（不遮、不藏）。
        def _is_archived(f: pathlib.Path) -> bool:
            return any(p.startswith("_归档-") for p in f.relative_to(oneoff).parts[:-1])

        allf = [f for f in oneoff.rglob("*") if f.is_file() and "__pycache__" not in f.parts]
        fs = [f for f in allf if not _is_archived(f)]
        n_arch = len(allf) - len(fs)
        note = f"（另有 `_归档-*` {n_arch} 件已按口径入档，不计）" if n_arch else ""
        mb = sum(f.stat().st_size for f in fs) / 1024 / 1024
        if len(fs) > ONEOFF_MAX_FILES or mb > ONEOFF_MAX_MB:
            hits.append(_hit(
                "T20", "tools/oneoff/",
                f"{len(fs)} 件 / {mb:.1f} MB > 提示线 {ONEOFF_MAX_FILES} 件 / {ONEOFF_MAX_MB} MB {note}",
                "它是**一次性 / 留痕的堆场**，此前**没有保留期、也没有机器眼**（`TAIL-194` · 结构审计 `P1-8`）"
                " ⇒ 只会一直堆；⚠️ 件数是「翻不翻得动」的代理指标（**已入档的不计** —— 它们已不在堆里）",
                "按 `tools/README.md` 那一段处置口径走：**先查引用**（只读件 `tools/oneoff/_oneoff_measure.py`）"
                " ⇒ ⛔ **不盲删**（会被台账/判据/记忆引用 ⇒ 造断链），把零引用的**移进** "
                "`tools/oneoff/_归档-YYYYMMDD/`（可逆）"))
        else:
            print(f"  （信息）`tools/oneoff/`：{len(fs)} 件 · {mb:.1f} MB"
                  f"（提示线 {ONEOFF_MAX_FILES} 件 / {ONEOFF_MAX_MB} MB ⇒ 余 {ONEOFF_MAX_FILES - len(fs)} 件）"
                  f"{note} —— 处置口径见 `tools/README.md`")
    # ⚠️⚠️ 2026-10-01（`TAIL-204` 第 7 步）**这里原本还有"活区规模"半条判据 —— 已撤掉**，因为它是**僵尸判据**：
    #    它扫的是 `REPO_ROOT / ".workbuddy" / "scratch"` —— 这个根**搬家后就不存在了**（仓里现在只有 `.codebuddy\`），
    #    而那个仓级活区也早在 `TAIL-134`（2026-09-28）被清空 ⇒ **每次都在空集上跑** ⇒ 从不报、也永远不报。
    #    ⭐ 这正是本仓点名的病：**"不报错，只是什么都没找到"，而"什么都没有"最容易被当成"正常"**。
    #    ⇒ 处置 = **撤掉**（⛔ 不是改指向）：临时件现在**只有一处** `work/00-scratch/`，已由 `T14`（TTL 14 天）管 ✔。
    #    ⚠️ 同族（同一天查出的）：`tools/mut/_mut_t20.py` 曾往那个**死路径**写 51 MB 稀疏文件 ⇒
    #       一跑就**在仓里复活旧根**（而它自证"通过"，因为两边用的是同一个死路径）—— 那条变异已同批撤。
    return hits


__all__ = ["ARTIFACTS_MD_ALLOW", "BACKUP_KEEP", "ONEOFF_MAX_FILES", "ONEOFF_MAX_MB",
           "SCRATCH_TTL_DAYS", "WORK_HEADER_KEYS",
           "check_artifacts_and_headers", "check_retention", "check_scratch_ttl"]


def main() -> int:
    """**单跑本模块的检查**（`T14` / `T15` / `T20`）。

    ⚠️⭐ 2026-10-01（`TAIL-204` 入场实测）：本件此前**只有被 `doc_audit` 当模块调用时才有用** ——
    **单跑 0 行输出、`rc` 恒 0**，而入门口令（计划 `§13.6`）的闸门清单里**逐行列着它**
    （`tools\\audit\\audit_work.py`）⇒ 那是**第五例僵尸闸门**（同族见 `T17` 立条说明：
    `shell_verify` / `cover_gap` / `audit_drift` / `audit_meta`，全是"一直在跑、其实什么都没判"）。
    ⇒ 补本入口（形态照 `audit_meta.main()`：**不另写一套判定**，只把已有检查跑一遍并打出来）。
    """
    print("=" * 78)
    print(" audit_work 单跑 —— T14/T15/T20"
          "（⚠️ 三条**都是黄档**：形式问题该被看见、但不挡合入）")
    print("=" * 78)
    # ⚠️ 先打抬头再跑检查 —— `check_retention` 会打「（信息）…」行，
    #    抬头若放在它后面，那些信息行会**跑到抬头之上**（看着像别人的输出）。
    raw = check_scratch_ttl() + check_artifacts_and_headers() + check_retention()
    reds = [h for h in raw if h["level"] == RED]
    yellows = [h for h in raw if h["level"] == YELLOW]
    print(f"必须修 {len(reds)}（本件无红档；出现红即上面有检查降级） · 疑似 {len(yellows)}")
    for h in reds + yellows:
        print(f"  [{h['code']}] {'红' if h['level'] == RED else '黄'}"
              f" {h['rel']}:{h['line']}  {h['what']}")
        print(f"        {h['why']} → {h['fix']}")
    return 1 if reds else 0


if __name__ == "__main__":
    sys.exit(main())
