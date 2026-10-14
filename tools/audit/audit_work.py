"""`doc_audit` 的**工作记录区**检查 —— `T14`（scratch TTL / 落点合规）· `T15`（产物白名单 ＋ work 状态头）。

据 `D:\\mtrl-workbench-文档架构审计-20260922.md` §七-15（长期维护）落地：
- `T14`：`work/00-scratch/` 里的件**超 14 天**未升档/未删 ⇒ 黄；`tools/` 根与 `logs/` 再出现散件 ⇒ 黄。
- `T15`：`artifacts/` 只许**工具生成物白名单**的 md；`work/` 的**三区**文档（`HEADER_ZONES`：
  `10-designs` / `30-troubleshooting` / `40-decisions`）必须带**文头四行元信息**
  （读者 / 回答什么问题 / 什么时候读 / 状态 ＋ 关联 ID）—— 没有元信息的文档 = 下个 Agent 不知道它是否还活着。
- ⭐ `T15` **新条**（2026-10-11 `TAIL-296` · 同属本件）：**决策区**（`40-decisions/`）的件，
  **状态词必须 ∈ 五档**，且「已定稿 / 已实施」档**必须有「落地位置」行** —— 此前这两件事
  **在决策区没有任何尺子看得见**（6 件状态写成"已办结/已拍板/已定案"、5 件缺落地位置，全是手查出来的）。
- `T26`（2026-10-05 `TAIL-236` 第 3 批）：**「结论已落地」⇒ 该降档**（只报不动）——
  「已定稿 / 已实施」两档的件，若 ① 件内 `TAIL-` 票**全部销号** ＋ ② 件内**声明的「落地位置」真存在**
  ⇒ 报黄。⭐ 治的是 `work/README.md` §二 那条「用完就丢」**只有规矩、没有机器眼**（`document-governance.md`
  §三 那两行自己写着「应有判据、现无」）。

⚠️ 与 `T12` 的分工：`T12` 管**目录与命名**（层级/前缀）；本件管**时间与元信息**（过期没、写没写头）。
⛔ 四条都是**黄**：形式 / 生命周期问题该被看见，但不挡合入（同 `T5`/`T10` 哲学）。
"""

from __future__ import annotations

import re
import sys
import time

from audit_common import BACKTICK_RE, RED, REPO_ROOT, YELLOW
#: ⭐ 票侧口径（目录 / 状态词 / **"销号"的定义**）**只从 `audit_meta` 取**（`T6` 守同一份）。
#: ⛔ 本件别另抄一个字面 —— `T26` 要判"件内票是不是全销号"，那正是最容易写成第二份口径的地方。
from audit_meta import TICKET_CLOSED, ticket_states

#: scratch 件存活上限（天）—— 审计 §六-9「TTL 14 天」
SCRATCH_TTL_DAYS = 14
#: `artifacts/` 允许出现的 md（工具生成物白名单 · ⛔ 过程类 md 去 `work/`）
ARTIFACTS_MD_ALLOW: tuple[str, ...] = ("变异覆盖台账.md", ".gitkeep")
#: 文头里**「状态」那一栏的栏名** —— ⛔ 只此一处：`WORK_HEADER_KEYS` 与 `T26` 都读它
#: （各写一份字面 ⇒ 改词表时 `T26` 静默失配，而它看上去还是绿的 —— 本仓「加了半边的守卫」那族）。
STATE_KEY = "状态"
#: `work/` 的 `HEADER_ZONES` 三区文档，文头必须齐这四个词（`README.md` 与 `D索引-*.md` 豁免）
WORK_HEADER_KEYS: tuple[str, ...] = ("读者", "回答", "何时读", STATE_KEY)
WORK_HEADER_EXEMPT: tuple[str, ...] = ("README.md", "D索引-")
#: 文档**文头窗口**（行数）—— `T15`（文头四行）与 `T26`（状态档）**共用同一个数**
#: （⛔ 别各写一遍：两处不一致 = 一份文档在一个判据里"有状态"、在另一个里"没状态"）。
WORK_HEAD_LINES = 15
#: `work/` 里**带文头四行**的区（`T15` 判）—— ⛔ **区名只此一处列**，别处一律从它推。
HEADER_ZONES: tuple[str, ...] = ("10-designs", "30-troubleshooting", "40-decisions")

#: ⛔⛔ **五档状态词一个字不动**（主人 = `docs/guides/work-records.md` §四）—— `T15` 新条按它判「状态出档」。
#: ⚠️ `DOWNGRADE_STATES`（下面 T26 那两档）是它的**子集**：改词表时两处一起看（⛔ 别处不另抄字面）。
STATE_WORDS: tuple[str, ...] = ("草稿", "在研", "已定稿", "已实施", "已归档")
#: `T15` 新条（2026-10-11 `TAIL-296`）的扫描面 = **决策区**。⚠️ **为什么只有这一区**（⛔ 别顺手扩到另两区）：
#:   · 决策件**永不出档**（`docs/guides/work-records.md` §二：只加不改、被推翻只补一行）⇒
#:     它必须自己说清「结论落到哪、谁改它」，否则下一个人只能把全部正文再读一遍；
#:   · 另两区（过程件）的存量件**故意不补声明行** —— `T26` 的 docstring 已写明那是**另一件事**
#:     （给存量件补声明行 = 改内容）⇒ 把它们扫进来只会当场多出十余条**本票不拥有的**黄；
#:   · ⛔ 要扩面属另一张票（`TAIL-297` 尺子体检），⛔ 不是在这儿调扫描面。
#: ⚠️ 区名**从 `HEADER_ZONES` 推**（照 `DOWNGRADE_ZONES` 的先例）⇒ 区名仍只有一处字面。
DECISION_ZONES: tuple[str, ...] = tuple(z for z in HEADER_ZONES if z == "40-decisions")
#: 「状态」那一栏的**值**（判它 ∈ 五档）—— 从 `状态` 起，切到行内第一个分隔符为止。
#: ⚠️ 必须切：文头常写成 `状态：**已实施**（原记「已办结」…）｜关联：…` ⇒ 不切的话括号与后半行
#:    里的词会一起被算进来（那正好是"判据看着绿、其实没判"那一族）。
STATE_VALUE_RE = re.compile(rf"{STATE_KEY}\s*[:：]?\s*\**([^｜|（(\n]*)")

# ------------------------------------------- T26 「结论已落地」⇒ 该降档（只报不动 · 黄）
#
# ⭐⭐ 2026-10-05（`TAIL-236` 第 3 批）：**只给缺判据的「已定稿 / 已实施」两档补判据** ——
#    这两档的含义就是「内容已冻结 / 结论已进代码」（`work/README.md` §四 的词表），
#    本仓口径是**该降档**，而此前**没有任何机器看得见**
#    （`docs/guides/document-governance.md` §三 那两行自己写着「应有判据、现无」）⇒
#    `work/README.md` §二 那条"用完就丢"**执行不了** ⇒ 只进不出（= 用户不安的根因）。
# ⛔⛔ **五档状态词一个字不动**（主人 = `docs/guides/work-records.md` §四 · `T15` 机核那四行文头）：
#    本判据只在两档上**加**机器眼，⛔ 不新增档位、不改词、不换轴（`TAIL-236` 决定 2）。
DOWNGRADE_STATES: tuple[str, ...] = ("已定稿", "已实施")
#: `T26` 的扫描面 = 上面那张区表里的**过程件两区** —— ⛔ **不含**决策区 `40-decisions/`：
#: 决策件的协议是「只加不改 ＋ 被推翻只补一行」（`docs/guides/document-governance.md` §三）⇒ 降档语义不同。
DOWNGRADE_ZONES: tuple[str, ...] = tuple(z for z in HEADER_ZONES if z != "40-decisions")
#: ⭐ **「落地位置」声明行**的形态 —— **唯一主人 = `docs/guides/work-records.md` §四**
#:   （⛔ 别处只指路，别重述形态）。两种冒号位置都收（写作习惯差异，不是两种格式）：
#:   `**落地位置**：`…` 与 `**落地位置：**`…`。
DECL_RE = re.compile(r"\*\*落地位置[：:]?\*\*[：:]?\s*(\S.*)")
#: 声明行里 `· 同批改：` 之后的那串**不参与"落地位置真存在"这条信号** —— 它只是"变了要一起改哪几处"
#: 那半边（验收 3 要的"读得到"），核不到由 `T3` 报黄即可。⇒ 摘 token 前先把两段切开。
DECL_SPLIT_RE = re.compile(r"\s*[·、,，]?\s*同批改\s*[：:]")


def check_downgrade_candidates() -> list[dict]:
    """`T26` · **「结论已落地」⇒ 该降档**（2026-10-05 `TAIL-236` 第 3 批 · **黄 · 只报不动**）。

    ⭐⭐ **判据 = 两个客观信号**（`TAIL-236` Implementation Decisions 3 · ⛔ 别改这个轴）：
      ① 件内提到的 `TAIL-` 票**全部销号**（口径 = `audit_meta.TICKET_CLOSED`，`T6` 守同一份）；
      ② 件内**声明的「落地位置」真存在**（形态 = `work/README.md` §四；路径写反引号 ⇒ `T3` 也核）。
    两条都成立 ⇒ 报黄：「本件结论已落地、却还在过程区 ⇒ **该降档**」＋ **落地位置**
    （它同时就是「口径主人」）＋ 声明行里 `· 同批改：` 那串（验收 3 要的"读得到"）。
    ⚠️ **走哪一步（归档仓外 / 沉进 `ops/` / 就地标收口）看 `docs/guides/work-records.md` §二 里
    本区那一行** —— 设计件与排查件的去向不同 ⇒ ⛔ 本判据**不替它规定去向**（别处重述 = 第二套口径）。
    ⛔ **「零机器引用」不是判据** —— 它只是一个**信号**（2026-10-05 实测：一份机器引用 0 的母本
       被四张票当唯一依据；`document-governance.md` §三 第 2 问）⇒ 报告里给的是**指路**：
       引用数去敲 `tools/audit/refs_query.py`（它自己的报告末尾本来就有「三路全 0 的件」那一行）。

    **如实记账：这条判据的边界**（⛔ 别当它覆盖了全部）
      · **只见"已声明落地位置"的件** —— 没声明行的件它一声不响。这是**有意的**：本批只"给两档
        **补**判据"，而给存量件补声明行 = 改内容（那是另一件事）；⇒ 它报出来的是**作者自己声明
        已落地**的那些，⛔ 不是"扫出了全部该降档的件"；
      · 件内**没提到任何票** ⇒ ①「全部销号」**空真**（仍报）—— 声明行本身就是"已落地"的断言；
      · 落地位置**核不到** ⇒ **本条不报**（交给 `T3`：它才是"路径必须存在"的主人）
        —— ⛔ 两条判据各报各的，别在这儿重复报一次；`· 同批改：` 之后那串**同样不参与**这条信号。
    ⚠️ 为什么是**黄**不是红：降档是**整理动作**，不是错（同 `T12`/`T15`/`T20` 的哲学：
       可能定错的、或该由人决定的，不该挡合入，但**必须被看见**）。
    """
    hits: list[dict] = []
    states = ticket_states()
    for zone in DOWNGRADE_ZONES:
        zdir = REPO_ROOT / ".codebuddy" / "work" / zone
        if not zdir.is_dir():
            continue
        for f in sorted(zdir.glob("*.md")):
            if f.name.startswith(WORK_HEADER_EXEMPT):
                continue
            lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
            head = lines[:WORK_HEAD_LINES]
            state = next((w for w in DOWNGRADE_STATES
                          if any(w in l for l in head if STATE_KEY in l)), None)
            if state is None:
                continue                      # 不在那两档 ⇒ 不归本条（"在研/草稿"本该留在过程区）
            decl, decl_no = "", 0
            for i, l in enumerate(lines, 1):
                m = DECL_RE.search(l)
                if m:
                    decl, decl_no = m.group(1), i
                    break
            if not decl:
                continue                      # 没声明 ⇒ 无从机判（见 docstring 的边界）
            parts = DECL_SPLIT_RE.split(decl, maxsplit=1)
            land_txt, also_txt = parts[0], (parts[1] if len(parts) > 1 else "")
            land = [p.strip().replace("\\", "/") for p in BACKTICK_RE.findall(land_txt)]
            if not land:
                continue
            if any(not (REPO_ROOT / p.rstrip("/")).exists() for p in land):
                continue                      # 落地位置核不到 ⇒ 交 `T3`（见 docstring 的边界）
            also = [p.strip().replace("\\", "/") for p in BACKTICK_RE.findall(also_txt)]
            tags = sorted({t for t in re.findall(r"TAIL-\d+", "\n".join(lines))})
            open_tags = [t for t in tags if states.get(t) != TICKET_CLOSED]
            if open_tags:
                continue                      # 还有票没销号 ⇒ 结论尚未全部落地
            tag_txt = ("件内票已全销号（%s）" % "、".join(tags)) if tags else "件内没提到票"
            also_txt2 = ("；声明行还写着同批改：" + "、".join("`%s`" % p for p in also)) if also else ""
            hits.append(_hit(
                "T26", f".codebuddy/work/{zone}/{f.name}",
                f"「{state}」档 · **结论已落地** ⇒ 该降档",
                f"{tag_txt} ＋ 声明的落地位置真存在（{'、'.join('`%s`' % p for p in land)}）⇒ "
                f"本件是**已完成的过程件**，却还留在过程区（`work/{zone}/`）——"
                f"「用完就丢」缺的正是这一条机器眼（`docs/guides/document-governance.md` §三 那两行"
                f"自己写着「应有判据、现无」）{also_txt2}",
                "① 引用面**只是参考、⛔ 不是判据**：敲 `tools/audit/refs_query.py` 看三路计数；"
                "② 落地位置即**口径主人** ⇒ 改它之前按 `docs/guides/document-governance.md` §二 核"
                "「变了要同批改哪几处」；③ **去向**看 `docs/guides/work-records.md` §二 里本区那一行"
                "（⛔ 别照抄别的区）；④ 要搬 ⇒ `tools/oneoff/_doc_downgrade.py <件名> --apply`"
                "（**唯一入口** · 默认干跑 · 可逆）—— 本判据**只报不动**",
                line=decl_no))
    return hits

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
#: ⭐⭐ 2026-10-02（`TAIL-217` · 用户选「②」）**交付面改前快照**（`交付面-*` / `原型-备份-*` /
#:   `_smoke.js-备份-*` / `*.bak`）的**条目数 / 容量提示线**（超 ⇒ 黄**一行**）。
#:   为什么加它：这一类此前的口径**只写**「另一用途 ⇒ 不计入手工快照 5 份上限」⇒ **自己一个上限都没有**
#:   ⇒ 只能只增不减（实测 2026-10-02：**18 个条目 / 9.5 MB**，而**没有任何机器看得见它涨**）。
#:   ⚠️ 单位 = **顶层条目数**（与 `BACKUP_KEEP` 同口径）；容量 = 递归文件字节。
#:   ⚠️ **不计** `*_壳单文件基线.html`（那 5 份由 `shell_verify` 自守，见 `BACKUP_SKIP_SUFFIXES`）。
FACE_KEEP, FACE_MAX_MB = 40, 25.0
#: ⭐⭐ 2026-10-02（`TAIL-217` 同批）**显式归档子目录**（`_归档-*` / `_旧快照归档-*`）的**件数 / 容量提示线**。
#:   加它的理由同上：归档此前**只被打印、从不被判** ⇒ 把东西「全塞归档」就能把上一条糊弄成假绿；
#:   而归档本就是「**先移后清**」的中转站 ⇒ 它自己也必须有上限。⚠️ 单位 = **递归文件件数**
#:   （归档子目录个数很少；里面件数才是「翻不翻得动」的代理指标 —— 与 `tools/oneoff/` 同哲学）。
ARCHIVE_KEEP, ARCHIVE_MAX_MB = 60, 12.0
#: ⭐ 2026-10-01（`TAIL-204` 第 7 步）**撤掉**「`.workbuddy/scratch/` 活区规模」这半条判据（连常量一起） ——
#:   理由见 `check_retention()` 里那段说明：**它一直在扫一个不存在的目录** = 僵尸判据。
#: ⭐ `tools/oneoff/`（**一次性 / 留痕的堆场** · 处置口径见 `tools/README.md`）的提示线：超 ⇒ 黄**一行**。
#:   ⭐ 为什么管它（`TAIL-194` · 2026-09-29 结构审计 §三 `P1-8`）：它曾是**全仓唯一"没有保留期、也没有机器眼"
#:   的目录**（对照当时还在的仓级活区 `.workbuddy/scratch`：明写「保留期 14 天 ＋ 索引 README ＋ `T20`」）⇒ 只会一直堆。
#:   ⚠️ **件数**才是它的病（"翻不翻得动"的代理指标）；**容量不是瓶颈**（实测 1.2 MB）⇒ 容量线只是挡住
#:   "往里扔大文件"。⚠️ 阈值出处 = `docs/reference/thresholds.md`（改数先改表）。
ONEOFF_MAX_FILES, ONEOFF_MAX_MB = 200, 5.0


def _hit(code: str, rel: str, what: str, why: str, fix: str, line: int = 1) -> dict:
    """本件四条黄档共用的命中形状 —— ⛔ 别在别处手拼同样的 dict（`/code-review` 2026-10-05 指出）。

    ⚠️ `line` **只有"能点到具体那一行"的判据才传**（`T26` 点声明行）；其余默认 1 —— 它们的
       "命中处"是**整件**（白名单外的 md / 超期临时件 / 仓库根多出来的条目），点行号没有意义。
    """
    return {"code": code, "side": "仓", "rel": rel, "line": line,
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


def _decision_state_hits(rel: str, lines: list[str]) -> list[dict]:
    """`T15` 新条的单件判定（2026-10-11 `TAIL-296`）—— 决策区：**状态词 ∈ 五档** ＋ **后两档必须有「落地位置」行**。

    ⭐ **治什么**（本轮实测，不是推演）：决策区 12 件里**6 件状态词出档**（写成"已办结 / 已拍板 / 已定案 /
    "⏳ 待实施"…）⇒ 机器判不了"这份还能不能再引用"，下一个人也要重猜一遍；而「已定稿 / 已实施」该声明
    「结论落到哪」这条，此前**只在过程件两区**被 `T26` 当**输入**读（没这一行它一声不响）⇒ 决策件没人守。

    ⚠️ **与 `T26` 的分工**（⛔ 别混、也别合并）：
      · `T26` 判**过程件**：「已声明落地 ＋ 件内票全销号 ⇒ **该降档**（只报不动）」；
      · 本条判**决策件**：「状态词必须在五档里 ＋ 后两档**必须**有落地位置行」—— 决策件**永不降档**
        （协议见 `docs/guides/work-records.md` §二）⇒ 两件事语义不同，⛔ 合起来写会让两边都读不懂。
    ⚠️ **落地位置真不真存在，不归本条**：仓内路径由 `T3` 核（反引号）、"声明了但核不到"由 `T26`/`T3`
      按各自分工报 —— ⛔ 本条只判那一行「在不在」（同 `T26` docstring：「路径必须存在」的主人只有一处）。
    ⚠️ **黄**（同本件其余四条）：形式问题该被看见、但不挡合入。
    """
    head = "\n".join(lines[:WORK_HEAD_LINES])
    #: 首尾的 `：`/`*`/空白都要剥掉（写法多样：`状态：**已实施**` / `**状态**：已定稿` / `状态 已定稿`）
    fields = [m.group(1).strip(" ：:*") for m in STATE_VALUE_RE.finditer(head)]
    words = [w for f in fields for w in STATE_WORDS if w in f]
    if not words:
        got = "、".join(f for f in fields if f) or "（文头里没有『状态』那一栏）"
        return [_hit(
            "T15", rel,
            f"状态词出档：不在五档里（现值：{got}）",
            "决定件的状态词是接手人判断「能不能再引用它」的唯一信号；写成"
            "「已办结 / 已拍板 / 已定案 / 待实施」这类**自造档** ⇒ 机器判不了、下一个人也要重猜一遍"
            "（2026-10-11 `TAIL-296` 实测：决策区 12 件里 6 件出档）",
            f"改成五档之一：{' / '.join(STATE_WORDS)}"
            "（词表主人 = `docs/guides/work-records.md` §四；原文别动，把原说法括在「原记…」里）")]
    if any(w in DOWNGRADE_STATES for w in words) and not any(DECL_RE.search(l) for l in lines):
        return [_hit(
            "T15", rel,
            f"「{words[0]}」档缺「落地位置」行",
            "这两档的含义就是**结论已冻结 / 已进代码** ⇒ 必须有一行说清「结论真正落到哪个文件」；"
            "没有它，接手的人只能再把全部正文读一遍（`T26` 对过程件读的是同一行 —— ⛔ 写法全仓只一处）",
            "补一行：`**落地位置**：`<结论真正落到的文件>`、<另一处> · 同批改：`<它变了要一起改的文件>`"
            "（写法主人 = `docs/guides/work-records.md` §四）")]
    return []


def check_artifacts_and_headers() -> list[dict]:
    """`T15`：artifacts md 白名单 ＋ work 三区（`HEADER_ZONES`）文档的文头四行元信息 ＋ 决策区状态词/落地位置（见 `_decision_state_hits`）。"""
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
    #: ⭐ 2026-10-01 五区 ⇒ 四区（撤 `20-experiments`）；⚠️ 2026-10-04（`TAIL-225`）加回第五区 `50-tickets`
    #:   ⚠️ 那两句说的是 `work/` 的**区总数**（`audit_meta.WORK_DIR_ALLOW`，5 个）；**本条的扫描面** = 上面
    #:   `HEADER_ZONES`（3 个，2026-10-11 `TAIL-296` 订正）—— ⛔ 两个数不是一个数，别混用。
    #:   ⇒ ⭐ **但票仓不在本条的扫描面里**：票是**工单**（照第二个项目的票面：`What to build` / `Blocked by` /
    #:   `Status` ＋ `- [ ]` 验收 ＋ `## Comments`），**不带"读者/何时读"那类文档文头** ⇒ 票的栏由 `T6` 守
    #:   （⛔ 一条只在一处定义：别在 `T6` 里另写一套文头词表，也别在这儿管票）。
    for zone in HEADER_ZONES:
        zdir = work / zone
        if not zdir.is_dir():
            continue
        for f in sorted(zdir.glob("*.md")):
            if f.name.startswith(WORK_HEADER_EXEMPT):
                continue
            lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
            head = "\n".join(lines[:WORK_HEAD_LINES])
            rel = f".codebuddy/work/{zone}/{f.name}"
            missing = [k for k in WORK_HEADER_KEYS if k not in head]
            if missing:
                hits.append(_hit(
                    "T15", rel,
                    f"文头缺元信息：{' / '.join(missing)}",
                    "没有『读者/回答什么/何时读/状态』⇒ 下个 Agent 不知它是否还在研、该不该读（审计 §5.3-1）",
                    "补文头四行（模板见 `docs/guides/work-records.md` §四）"))
            if zone in DECISION_ZONES:
                hits += _decision_state_hits(rel, lines)   # ⭐ `TAIL-296` 新条（状态 ∈ 五档 · 落地位置在位）
    return hits


def check_retention() -> list[dict]:
    r"""`T20` · **保留期与容量** —— ⭐ 治「口径写了『留 5 份』，却没有任何机器看得见」。

    ⚠️ 本 docstring 是 **raw 字符串**（前缀 r）：下面有仓外绝对路径 `D:\dev\...` ——
    非 raw 会把它当转义序列（`\d` ⇒ SyntaxWarning，将来是 SyntaxError）。
    ⛔ 也别把注释放到 docstring **前面**：那样它就不再是 docstring（`__doc__` 变 None）。
    ⛔ 写"本件是 raw"时**别把三引号本身写进来**（那会当场把 docstring 提前结束 ⇒ SyntaxError）。

    背景（2026-09-28 文档审计 §四-7 —— ⭐ **那份审计件已于 2026-10-06 降档到仓外**
    `D:\dev\.归档-mtrl\work-10-designs\设计-文档审计-20260928.md`，⛔ 仓内已无原件；
    要原文走仓外那份或 git `show HEAD:.codebuddy/work/10-designs/设计-文档审计-20260928.md`）：
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
        def _stat(items: list) -> tuple[int, float, float | None]:
            """→ (递归件数, MB, **最老一件**距今多少天) —— 三类上限与「何时清」共用同一把尺。"""
            fs = [f for it in items for f in (it.rglob("*") if it.is_dir() else [it]) if f.is_file()]
            mb = sum(f.stat().st_size for f in fs) / 1024 / 1024
            oldest = min((f.stat().st_mtime for f in fs), default=None)
            return len(fs), mb, ((time.time() - oldest) / 86400 if oldest else None)

        if face:
            n, mb, age = _stat(face)
            print(f"  （信息）`backups/` 交付面改前快照：{len(face)} 个条目 · {n} 件 · {mb:.1f} MB"
                  + (f" · 最老一件距今 {age:.0f} 天" if age is not None else "")
                  + " —— ⛔ **不计入「手工快照 5 份」上限**（另一种用途）；**何时清** = `README.md` §四 末两行")
            if len(face) > FACE_KEEP or mb > FACE_MAX_MB:
                hits.append(_hit(
                    "T20", ".codebuddy/backups/ 交付面改前快照",
                    f"{len(face)} 个条目 / {mb:.1f} MB > 提示线 {FACE_KEEP} 个 / {FACE_MAX_MB} MB",
                    "这一类**最容易只增不减** —— 老口径只说「另一用途、不计入 5 份上限」⇒ 它**自己一个上限都没有**"
                    "（`TAIL-217` · 2026-10-02 立本条：此前只打印、不判 ⇒ 涨到多少都没人看见）",
                    "按 `README.md` §四 的「何时清」：把**最旧的一批移进** `_旧快照归档-YYYYMMDD/`（可逆）；"
                    "⚠️ 5 份 `*_壳单文件基线.html` 由 `shell_verify` 自管，⛔ 不在这条的范围里"))
        if archived:
            n, mb, age = _stat(archived)
            print(f"  （信息）`backups/` 显式归档：{len(archived)} 个子目录 · {n} 件 · {mb:.1f} MB"
                  + (f" · 最老一件距今 {age:.0f} 天" if age is not None else "")
                  + " —— 归档不计入「手工快照 5 份」，但**它自己有上限**；**何时清** = `README.md` §四 末两行")
            if n > ARCHIVE_KEEP or mb > ARCHIVE_MAX_MB:
                hits.append(_hit(
                    "T20", ".codebuddy/backups/ 归档子目录",
                    f"{n} 件 / {mb:.1f} MB > 提示线 {ARCHIVE_KEEP} 件 / {ARCHIVE_MAX_MB} MB",
                    "归档是「**先移后清**」的中转站 ⇒ 它没有上限时，上一条就变成「换个地方堆」"
                    "（原口径只在报告里**打印**件数、没有任何判定；`TAIL-217` · 2026-10-02 立本条）",
                    "按 `README.md` §四 的「何时清」：**每次产包前一晚**复核一次 —— 真过期就删"
                    "（⚠️ 删前先查引用：`tools/oneoff/_oneoff_measure.py` 那种只读量法；⛔ 不静默删）"))
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
    # ⚠️⚠️ 2026-10-01（`TAIL-204` 第 7 步）**这里原本还有"活区规模"半条判据 —— 已撤掉**：
    #    它扫的是 `REPO_ROOT / ".workbuddy" / "scratch"` —— 那是**搬家（第 1 步）遗留的旧落点**。
    #    ⚠️ 它**一直在盘上**（所以这条判据**不是**"扫空集"），只是**没被移走**：`.gitignore` 里有一条
    #       `.workbuddy/scratch/` 把它藏住了 ⇒ **`git status` 干净、盘上却有东西**
    #       （⭐ 本轮最初的判断就是被这一点带偏的 → 已在原处订正，⛔ 不留错话）。
    #    ⇒ 第 7 步把旧落点**整棵清掉**（内容归位到 `.codebuddy/backups/_归档-旧临时区-20261001/`，⛔ 没删）⇒
    #       这条判据从此**正式失去对象** ⇒ **撤掉**（⛔ 不是改指向）：临时件现在**只有一处** `work/00-scratch/`，
    #       已由 `T14`（TTL 14 天）管 ✔ —— ⛔ 两条判据盯同一个目录 = 第二套口径。
    #    ⚠️ 同批撤掉它的变异：`tools/mut/_mut_t20.py` 原本往 `.workbuddy/scratch/` 写 51 MB 稀疏文件
    #       （那个目录当时**确实存在** ⇒ 能跑通；但它守的是**已废弃的落点**）。
    #    ⭐⭐ 教训（值得带回）：**`git status` 干净 ≠ 盘上没东西** —— 忽略规则会把整棵目录**藏起来**；
    #       查"盘上到底有没有"必须**用文件系统**，⛔ 别拿 git 的状态去推断。
    return hits


__all__ = ["ARCHIVE_KEEP", "ARCHIVE_MAX_MB", "ARTIFACTS_MD_ALLOW", "BACKUP_KEEP",
           "DECISION_ZONES", "DOWNGRADE_STATES", "FACE_KEEP", "FACE_MAX_MB", "HEADER_ZONES",
           "ONEOFF_MAX_FILES", "ONEOFF_MAX_MB", "SCRATCH_TTL_DAYS", "STATE_KEY",
           "STATE_WORDS", "WORK_HEADER_KEYS", "WORK_HEAD_LINES",
           "check_artifacts_and_headers", "check_downgrade_candidates", "check_retention",
           "check_scratch_ttl"]


def main() -> int:
    """**单跑本模块的检查**（`T14` / `T15` / `T20` / `T26`）。

    ⚠️⭐ 2026-10-01（`TAIL-204` 入场实测）：本件此前**只有被 `doc_audit` 当模块调用时才有用** ——
    **单跑 0 行输出、`rc` 恒 0**，而入门口令（计划 `§13.6`）的闸门清单里**逐行列着它**
    （`tools\\audit\\audit_work.py`）⇒ 那是**第五例僵尸闸门**（同族见 `T17` 立条说明：
    `shell_verify` / `cover_gap` / `audit_drift` / `audit_meta`，全是"一直在跑、其实什么都没判"）。
    ⇒ 补本入口（形态照 `audit_meta.main()`：**不另写一套判定**，只把已有检查跑一遍并打出来）。
    """
    print("=" * 78)
    print(" audit_work 单跑 —— T14/T15/T20/T26"
          "（⚠️ **都是黄档**：形式 / 生命周期问题该被看见、但不挡合入）")
    print("=" * 78)
    # ⚠️ 先打抬头再跑检查 —— `check_retention` 会打「（信息）…」行，
    #    抬头若放在它后面，那些信息行会**跑到抬头之上**（看着像别人的输出）。
    raw = (check_scratch_ttl() + check_artifacts_and_headers() + check_retention()
           + check_downgrade_candidates())
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
