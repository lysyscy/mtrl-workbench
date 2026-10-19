#!/usr/bin/env python
"""文档漂移自检（doc_audit）—— 把「改完还得人肉重扫一遍」变成一条命令。

**为什么存在**：文档里的**规则**很少变，但**状态描述**（数字 / 术语 / 用例号 / 路径）
必然随开发过期，而且**过期了不会报错** —— 这是本项目最贵的一类事故
（已实测两次：`sumrow` 变量未定义静默失效 · 签名漏认静默漏印）。

**只做「机器可判、几乎不误报」的检查**（语义是否还成立，仍需人/模型判断）：

| 代号 | 检查 | 真源 |
|---|---|---|
| `T1` | **幽灵用例号** —— 文档提到的 `ACC-*` 在验收基线里不存在 | `验收基线.json` |
| `T2` | **已废除术语** —— 命中 `RETIRED_TERMS` | `audit_common.py` |
| `T3` | **幽灵路径** —— 反引号里的仓库内路径两侧都找不到（⭐ 2026-10-05 `TAIL-235` 丁-1 扩半：① 扫描面进 `.codebuddy/`（**治理区此前整片无人管**）② **仓外绝对路径**落在 `OUTSIDE_ROOTS` 白名单内 ⇒ 到那个根下**真核存在** ③ 带 `〔已归档〕` 标记的引用**剥掉标记照核** ⇒ ⛔ **标记不是豁免**，加前缀不再能把坏路径洗掉） | 文件系统 |
| `T4` | **状态数字失配** —— 执行情况「当前版本」行的四态 ≠ 实际 | `artifacts/acc_results.json` |
| `T5` | **行数超限** —— 单文件 >400（黄 · 须登记拆分计划）/ >600（黄 · 须登记"为什么不拆"）<br>⚠️ 2026-09-21 **用户裁定：>600 从红降黄**（行数是代理指标，不作禁合入闸门） | 源文件行数（**输出即登记清单**）＋ `docs/reference/thresholds.md` |
| `T6` | **尾巴台账** —— 清点处在不在（计划 §15）/ 栏位 / 编号 / 落点 / 计数 | `docs/status.md` |
| `T7a`/`T7b` | **判据覆盖** —— 有登记的能力却没判据兜住（**登记档，不判红**） | `cover_gap.py` |
| `T8` | ⭐ **已撤项复活** —— 用户裁定取消的东西**不得在代码里长回来** | `audit_common.CANCELLED` |
| `T9` | ⭐ **纪律册卫生（两半）** —— ① **口径出处标记**：`MEMORY.md` §八 每条必须带 `[用户]`/`[交付面]`/`[助手自定]`；② ⭐ **注入档里别复述守卫的阈值**（`T13`（行数预算 1700）那种 ⇒ **规则留、数字去**） | `docs/agents/project-rules.md` |
| `T10` | ⭐ **文档读预算** —— 每会话**注入/必读**档超预算（黄 + 登记；治「太长读不完 ⇒ 只 grep ⇒ 没搜到的就丢了」） | `docs/reference/thresholds.md` ＋ `audit_meta.DOC_BUDGETS` |
| `T11` | ⭐ **建议类报告必须带「待办登记回执」** —— `artifacts/` 里的审计/提案/建议**不许只活在报告里** | `artifacts/*.md` ↔ 计划 §15 |
| `T12` | ⭐ **文档分层与命名约定** —— `plans/` 只许两份活文档（其余 `归档-` 打头）· `memory/` 日志必须进 `journal/` · 根上的 md 只许 `ROOT_MD_ALLOW` 那两件（⚠️ 根上的**目录与非 md 文件**归 `T24`） | 根 `README.md` 的四层表 ＋ 本件三张白名单 |
| `T13` | ⭐ **主文档过程回潮** —— 计划主文档行数超预算（1700）· 标题出现过程词（逐批/逐次/收官记录）⇒ 黄：该块**该下沉归档了**（`§13.1`「完成的就扔出去」的机器守） | `docs/status.md` |
| `T14` | ⭐ **scratch 超期 / 落点合规** —— `.scratch/local/` 超 14 天未升档未删 · `tools/` 根与 `logs/` 再现散件 ⇒ 黄（`audit_work.py`） | 文件系统 mtime |
| `T15` | ⭐ **产物白名单 ＋ 工作记录元信息** —— `artifacts/` 只许工具生成物 md · `.scratch/legacy-active`与`docs/adr`的旧D件文档必须带文头四行（读者/回答什么/何时读/状态；⚠️ **票仓不在扫描面里**，票按票面协议走）⭐ **2026-10-11 加一条**（`TAIL-296`）：**决策区**的件**状态词必须 ∈ 五档**，且「已定稿 / 已实施」**必须有「落地位置」行** ⇒ 黄 | `audit_work.py`（`STATE_WORDS` / `HEADER_ZONES` / `DECISION_ZONES` / `WORK_HEADER_KEYS` / `DECL_RE`） |
| `T16` | ⭐ **`T7a` 登记册必须在位** —— 登记册**读不到 / 解析不出条目** ⇒ **红**（治「静默降级成全部未清」） | `cover_gap.CLEARED_REGISTRY` |
| `T17` | ⭐ **闸门清单里每一把尺子都必须真有入口** —— 在跑却**0 行输出**（僵尸闸门）⇒ 红 | 计划 `§22.1` 的 `foreach` |
| `T18` | ⭐ **登记在册的路径 / glob 常量必须解析得到真东西** —— 空命中 = 那一片**从没被扫过** ⇒ 红 | `audit_meta.GUARDED` |
| `T19` | ⭐ **文档指针（节号）守卫** —— 「`X.md` §N」必须真有那一节（`T3` 只管文件在不在）⇒ 红 | `audit_drift` |
| `T20` | ⭐ **保留期与容量** —— `.artifacts/recovery/backups/` 顶层条目 > 5（口径「留 5 份 · 月度清」）⭐ **`tools/oneoff/` 件数 / 容量超线**（⚠️ 原第三条「`.workbuddy/scratch/` 活区规模」**2026-10-01 已撤** —— 它守的是**搬家遗留的旧落点**（盘上一直在、被 `.gitignore` 藏着 ⇒ `git status` 看不见），第 7 步已把旧落点**整棵清掉** ⇒ 判据**失去对象**；临时件现由 `T14` 管）（`TAIL-194`；处置口径 = `tools/README.md`）⇒ 黄 | `README.md` §三/§四 ＋ `tools/README.md` ＋ `docs/reference/thresholds.md` ＋ `audit_work.py` |
| `T22` | ⭐ **注入档「两行粘成一行」** —— 注入档三件里「**行尾标点后紧跟列表符/引用符**」⇒ 黄（治 `replace_in_file` 锚点末尾多写一个换行 ⇒ 下一行的列表符被吞进上一行；当天实测 `MEMORY.md` 93 → 92 行，而**闸门 rc=0 · pytest 全绿 · 无尺子看得见**）。⚠️ 固定语法模式 ⇒ **该做检查、不该写规则**（写进纪律没人执行） | `audit_meta.INJECT_DOCS` / `SPLICE_RE` ＋ `docs/reference/thresholds.md` |
| `T21` | ⭐ **文档「字墙」**（单行 >800 字）—— 治"行数在预算内、**单行上万字**"那一类：`T10`/`T13` 只看得见总行数。⚠️ 带**只许变短**的老账基线（`LINE_WALL_BASELINE`）：超基线 ⇒ 黄「又长回来了」· 低于基线 ⇒ 黄「基线该下调」⇒ 黄 | `docs/reference/thresholds.md` ＋ `audit_meta.LINE_WALL_CHARS` / `LINE_WALL_BASELINE` |
| `T23` | ⭐ **活机器口径六路齐全（变异仅现行顶层，归档不作活机器引用）**（`TAIL-236` 第 2 批）—— 判「某件还有谁在引用」时**该扫的那几处**（含运维脚本 · Agent宿主入口 · 壳的脚本与页面）**少一路 ⇒ 红**；某条 glob **空命中 ⇒ 红**；查询命令的**代码**里又抄一份口径 ⇒ 黄。⭐ 治的是当天真发生的翻车：第一版口径漏两路 ⇒ 差点搬走**被引用**的设计件 | `audit_common.LIVE_MACHINE_GLOBS` ＋ `audit_meta.LIVE_MACHINE_REQUIRED` ＋ `docs/reference/thresholds.md` |

| `T24` | ⭐ **仓库根白名单**（2026-10-05 `TAIL-236` 同批修 ①b）—— 根上的**目录与非 md 文件**必须落在「常驻骨架（`ROOT_ALLOW`）∪ `.gitignore` 声明过的暂存件」里，多出来的 ⇒ **红**。⭐ 起因：根 `work/` 建起来后 `T3`/`T12`/`T14` **四层守卫没一层拦**（那片地方**不在任何扫描面内**）。⚠️ 根上的 md 归 `T12`（本行**不**重复管） | `audit_common.ROOT_ALLOW` ＋ 仓根 `.gitignore` |
| `T25` | ⭐ **`.gitignore` 里的落点路径必须真存在**（2026-10-05 `TAIL-236` 同批修 ①b/③）—— `.gitignore` 反引号里的**仓库内目录落点**（含 `/` · 以 `TOP_DIRS` 前缀开头 · 不含模式字符）盘上核不到 ⇒ **红**。⭐ 治的是"照一份**没被核过**的落点找路 ⇒ 找到不存在的目录"（当天真实事故）；⚠️ `T3` 拦不住这一类（它只认**带后缀**的引用，而落点多是**目录**） | 仓根 `.gitignore` ＋ `audit_drift.check_gitignore_drops`（豁免沿用 `T3_OLD_PATH_HINTS`） |
| `T26` | ⭐ **「结论已落地」⇒ 该降档**（2026-10-05 `TAIL-236` 第 3 批 · **黄 · 只报不动**）—— `.scratch/legacy-active/`里处在「**已定稿 / 已实施**」两档的件，若 ① 件内 `TAIL-` 票**全部销号** ＋ ② 件内**声明的「落地位置」真存在** ⇒ 报黄「该降档」＋ 落地位置（＝**口径主人**）＋ 同批改那串（**去向**看 `docs/guides/work-records.md` §二 本区那一行）。⛔「零机器引用」**不是判据**（只是信号）。⭐ 治的是 `work/README.md` §二「用完就丢」**只有规矩、没有机器眼** | `audit_work.check_downgrade_candidates` ＋ `work/README.md` §四（**声明行写法**的唯一主人）＋ `audit_meta.TICKET_CLOSED`（销号定义）＋ `docs/reference/thresholds.md` |
| `T27` | ⭐ **交付面「页脚之后不许有内容」**（2026-10-06 `TAIL-234`）—— ⛔ `T1`–`T26` 没一层能看见"内容掉到落款后面"（当天实测：`MOD-14.md` 两条 `ACC-*` 验收条目就在页脚**下面**，而用例号 / 路径都是真的 ⇒ 只是**位置错了**）。⚠️ **归档目录按实测排除**（6 处全在 `.workbuddy/归档-audit/` 下 ⇒ 那是留痕、不是缺陷） | `audit_face.check_footer_tail` ＋ `audit_common.FOOTER_MARKER` / `FOOTER_SCAN_GLOB` / `FOOTER_EXCLUDE_PARTS` |
| `T28` | 交付面篇幅变短提示调查；能力编号损失或缺件仍报红。篇幅不能证明业务丢失，不阻挡已授权精简 | audit_face.check_prd_baseline ＋ audit_face.PRD_DOC_BASELINE |

> ⭐ **`T8` 是"如何永久记住某功能已取消"的答案**：撤项登记进 `audit_common.CANCELLED`，
> 每次跑 `doc_audit` 都扫**代码面**（`clean=True` 复活报红 / `clean=False` 还有残骸报黄）。
> ⚠️ 理由：撤项目前只写在**代码注释**里，而**注释没人每次读** ⇒ 下次照着一片残骸再做一遍
> （已发生过：`mod12_diff` 撤了，但判据还在、目录还在、壳里还渲染）。

### 怎么避免变成「新噪音源」（三条纪律）

1. **区分「当前状态」与「历史留痕」** —— 留痕里的旧术语是**正确的**，不该报。
   · 文件级：`LENIENT_GLOBS`（日志、历史计划、已执行的方案）⇒ 命中只报**黄**；
   · 段级：交接文件用 HTML 注释分区（`doc_audit:current` / `doc_audit:history`），
     `history` 段只报黄。**未标区**的文件默认整篇按 current。
2. **豁免窗口 ±2 行** —— 「勘误」常写在下一行，只看当前行会误报。
3. **强豁免词直接忽略**（`HARD_EXEMPT`）—— 行文本身就在说「它废了」的，不算漂移。

用法（⚠️ 2026-09-24 订正：尺子已随 `TAIL-58` 搬进 `tools/audit/`，旧写法 `tools/doc_audit.py` 已不存在）：
    python tools/audit/doc_audit.py              # 人读报告（有红即非零退出）
    python tools/audit/doc_audit.py -v           # 附命中行上下文
    python tools/audit/doc_audit.py --block      # 打印可粘贴进交接文件的「当前状态」块

⚠️ 本工具**只读**（`--block` 也只打印、不写文件）。

**本文件是薄壳** —— 检查逻辑已拆到同目录五件（`T5` 逼的，本文件曾 597 行）：
`audit_common.py`（常量 ＋ 扫描基础设施）· `audit_drift.py`（`T1`–`T4` · `T25` `.gitignore` 落点）·
`audit_meta.py`（`T5`/`T6` 台账与行数 · `T9` 纪律出处 · `T10` 读预算 · `T11` 报告回执 · `T12` 分层约定 · `T21` 字墙 · `T22` 注入档粘连 · `T23` 活机器口径 · `T24` 仓库根白名单）·
`audit_work.py`（`T14` scratch TTL · `T15` 文头与产物白名单 · `T20` 保留期 · `T26` 降档判据）·
`audit_face.py`（`T27` 页脚尾部 · `T28` `PRD` 规格件基线 —— ⭐ **交付面**那两处。单独成件是因为它有**自己的基线表** ＋ **自己的行数定义**；塞进 `audit_meta` 会把那件 1475 行的继续撑大）。
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_common import (                                        # noqa: E402
    LIVE_MACHINE_GLOBS, RED, REPO_ROOT, SKIP, YELLOW, delivery_root, iter_docs,
)
from audit_drift import (                                         # noqa: E402
    check_acc_ids, check_cancelled, check_count_anchors, check_gitignore_drops, check_paths,
    check_section_refs, check_status_line, check_terms,
)
from audit_meta import (                                          # noqa: E402
    HARD_LIMIT, LINE_LIMIT, check_doc_budgets, check_doc_layout, check_drop_zones,
    check_file_sizes,
    check_gate_liveness, check_guard_constants, check_line_splices, check_line_walls,
    check_live_machine, check_plan_process,
    check_report_receipts, check_rule_origins, check_rule_restatements, check_tail_ledger,
)
from audit_face import (                                          # noqa: E402
    check_footer_tail, check_prd_baseline, summary as face_summary,
)
from audit_work import (                                          # noqa: E402
    check_artifacts_and_headers, check_downgrade_candidates, check_retention, check_scratch_ttl,
)


# ------------------------------------------------------------------- 四检（可选）


# ----------------------------------------------------------------------- 主流程


def _print_block() -> int:
    from audit_drift import _actual_states                          # noqa: PLC0415
    st = _actual_states()
    if st is None:
        print("（拿不到真源：先跑全套 pytest 生成 artifacts/acc_results.json）")
        return 2
    code = 0 if st["红"] == 0 else 1
    print("四态 **%d = 绿 %d · 红 %d · 待建 %d · 未绑定 %d**（退出码 %d）"
          % (st["合计"], st["绿"], st["红"], st["待建"], st["未绑定"], code))
    return 0


def check_cover_registry() -> list[dict]:
    """`T16`：**`T7a` 登记册必须在位**（2026-09-24 立 · `TAIL-20`）。

    ⭐ 治的是「**读不到 ⇒ 静默降级成「全部未清」**」—— 2026-09-24 实测：登记册在 `tools/`，
    而 `cover_gap.CLEARED_REGISTRY` 按**自身所在目录**拼 ⇒ 恒读到空集 ⇒ 所有 `x` 标记**全部失效**，
    且**没有任何报错**（降级方向还是"宁多报"，看着反而更安全）⇒ 只有变异测试才撞得出来。
    ⇒ 光靠 stderr 不够（跑批只看 rc 时照样漏）⇒ 升成**红档**。
    """
    from cover_gap import CLEARED_REGISTRY

    try:
        rel = str(CLEARED_REGISTRY.resolve().relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        rel = str(CLEARED_REGISTRY)
    if not CLEARED_REGISTRY.exists():
        return [{"code": "T16", "side": "仓", "rel": rel, "line": 1,
                 "what": "（登记册文件不存在）",
                 "why": "`T7a` 的「已清」登记读不到 ⇒ `load_cleared()` 返回空集 ⇒ 所有 `x` 失效（静默）",
                 "fix": "恢复登记册，或改 `cover_gap.CLEARED_REGISTRY` 指向它的真实位置",
                 "level": RED, "text": ""}]
    rows = [ln for ln in CLEARED_REGISTRY.read_text(encoding="utf-8", errors="replace").splitlines()
            if ln.strip() and not ln.lstrip().startswith("#")]
    if not rows:
        return [{"code": "T16", "side": "仓", "rel": rel, "line": 1,
                 "what": "（登记册里解析不出任何条目行）",
                 "why": "读得到文件却读不到条目 ⇒ `x` 照样全失效",
                 "fix": "补回条目行（格式见登记册文件头注释）",
                 "level": RED, "text": ""}]
    return []


def main() -> int:
    ap = argparse.ArgumentParser(description="文档漂移自检")
    ap.add_argument("-v", "--verbose", action="store_true", help="附命中行上下文")
    ap.add_argument("--block", action="store_true", help="打印可粘贴的「当前状态」块")
    args = ap.parse_args()

    if args.block:
        return _print_block()

    import acc_report as ar                                    # noqa: PLC0415
    baseline = ar.load_json(ar.resolve_baseline(None))
    cases = set(baseline.get("cases") or {})
    docs = iter_docs()

    sizes = check_file_sizes()          # 单独成节：它输出的是「欠债清单」，与漂移不同性质
    # `T19`（2026-09-24 立 · `TAIL-84`）：**文档指针（节号）守卫** —— `T3` 只核**文件在不在**，
    #   而「`X.md` §N」这种**指到某一节**的引用烂了 **没有任何尺子看得见**（实证：`MEMORY §十七`
    #   的「已下沉 `docs/runbook.md` §七」是**死指针** —— runbook 止于 §六，差点让那六条坑静默消失）。
    raw = check_acc_ids(cases, docs) + check_terms(docs) + check_paths(docs) + check_section_refs(docs)
    # `T25`（2026-10-05 立 · `TAIL-236` 同批修 ①b/③）：⭐ **`.gitignore` 里的落点路径必须真存在** ——
    #   `.gitignore` 此前**不在任何扫描面** ⇒ 里面写的落点烂了没人看得见（当天正是"照它找路
    #   找进了不存在的目录"）。⚠️ `T3` 拦不住这一类：它只认**带文件后缀**的引用，而落点多是
    #   **目录形态**（`.../00-scratch/`）⇒ 对 `T3` 完全隐形。
    raw += check_gitignore_drops()
    raw += check_status_line()
    # `T4` **追加**（2026-09-24 立 · 用户「按推荐」）：**计数锚点**（黄）—— 手抄的、有机器真值的计数
    #   （尾巴计数 / `§22.1` 尺子把数 / `U5` 登记条目数）必须等于真值。⭐ 起因：一天内**两次**实测到
    #   "手抄的数字漂"（`claim_audit` 黄计数 · `U5` 登记 42↔43），而 `T4` 原先只管**四态数字**。
    raw += check_count_anchors()
    # `T8`：**已撤项不得在代码里复活**（真源 = `audit_common.CANCELLED`）。
    # ⭐ 这条是「**如何标记才能永久记住某功能已被取消**」的机器化答案 ——
    #    撤项登记在那张表里，`T8` 每次跑批都扫代码面 ⇒ ⛔ 不靠人记得。
    raw += check_cancelled()
    raw += check_tail_ledger(cases)     # `T6` 尾巴台账：格式 / 编号 / 落点 / 计数
    # `T9`：**纪律的「口径出处」标记**（用户 2026-09-21 裁定「加」）。
    # ⭐ 这条守的是"自定规则静默腐化"—— 当天刚实测到一次：`MEMORY.md §八` 写着
    #    「每轮收尾提交 ＋ 推送」，而用户当天定的是「先不提交，继续攒」，**没尺子看得见**。
    raw += check_rule_origins()
    # ⭐ `T9` ②（2026-09-29 立 · `TAIL-59` 的量测逼出来的）：**注入档里别复述守卫的阈值** ——
    #   实测咬人的样子 = `MEMORY.md` 写着「`T13`（行数预算 1700）」而真源已 1800，**没有尺子看得见**。
    #   ⚠️ 只查**注入档**（计划/归档里"历史叙事中的旧数字"是**对的留痕**，改了反而是篡改历史）。
    raw += check_rule_restatements()
    # `T10`/`T11`（2026-09-21 立 · 用户：「文档太长了你也读不完 ⇒ 容易过期」）：
    #   `T10` = **文档读预算**（每会话注入/必读档超预算 ⇒ 黄 + 登记）；
    #   `T11` = **建议类报告必须带「待办登记回执」**（⇒ 报告里的建议不会烂在报告里）。
    raw += check_doc_budgets()
    raw += check_report_receipts()
    # `T12`：**文档分层与命名约定**（`plans/` 只许两份活文档 · `memory/` 日志必须进 `journal/` ·
    #   根只许 `README.md`）—— ⭐ 把"目录约定"从**口头纪律**变成**机器守**（用户 2026-09-21 要求
    #   「尽量减少…需要我停下来检查文档」）。
    raw += check_doc_layout()
    # `T24`（2026-10-05 立 · `TAIL-236` 同批修 ①b）：⭐ **仓库根白名单** —— `T12` 只管**根上的 md**，
    #   ⇒ **目录与非 md 文件**落在根上**没有任何尺子看得见**。2026-10-05 实测：照 `.gitignore`
    #   注释里的旧落点在仓库根建了 `work/`，而 `T3`/`T12`/`T14` 四层守卫**没一层拦**
    #   （那片地方从此不在任何扫描面内）。⛔ 根上的 `.md` 仍归 `T12`（**`.mdc` 不跳**，见该函数 docstring）。
    #   ⭐ **"接线掉了"也有牙**：本条一旦被从这里拆掉，`_mut_docaudit` 的 `M27`/`M28`（连同 `M29`/`M30`）
    #   当场不命中 ⇒ 对应隔离自证报红（＝ `tools/README.md` 纪律 1 要的那条自检）。
    raw += check_drop_zones()
    # `T13`（2026-09-22 立 · 用户问「为啥还是会有过期现象？是不是把太多过程塞到开发计划里了？」）：
    #   **主文档过程回潮守卫** —— 行数超预算 ＋ 标题出现过程词 ⇒ 黄（该下沉归档了）。
    #   ⭐ 治的是"§13.1 早有『完成的就扔出去』的裁定，却只有触发点、没有机器守"。
    raw += check_plan_process()
    # `T21`（2026-10-04 立 · `TAIL-224` · 用户裁定「④按推荐」＝ 文档重构方案 §六-4 甲案）：
    #   **文档「字墙」**（单行 >800 字）—— ⭐ 治的是"行数在预算内、**单行上万字**"那一类病：
    #   `T10`（读预算）与 `T13`（行数）都只看得见总行数，**看不见"一行有多长"**
    #   （主文档 88 行超 800 字、最长一行 4563 字 —— 都是从没有尺子看见过的）。
    #   ⚠️ 带**只许变短的老账基线**（`LINE_WALL_BASELINE`）—— 存量不逐条复述（否则 106 条黄 = 噪音源）。
    raw += check_line_walls()
    # `T22`（2026-10-05 立 · `TAIL-235` 丁-2）：⭐ **注入档「两行粘成一行」** ——
    #   当天实测：编辑工具的锚点末尾多写一个换行 ⇒ 下一行的列表符被吞进上一行
    #   ⇒ `MEMORY.md` 93 → 92 行，而**闸门 rc=0 · pytest 全绿 · 没有任何尺子看得见**
    #   （`MEMORY.md` 不在任何判据的栏位检查里）⇒ 注入档每轮都读它、谁也发现不了。
    #   ⚠️ **只报黄**：它是编辑事故不是口径错，正确处置是"当场拆回去"，不该挡别人合入。
    raw += check_line_splices()
    # `T23`（2026-10-05 立 · `TAIL-236` 第 2 批）：⭐ **活机器口径六路齐全（变异仅现行顶层，归档不作活机器引用）** ——
    #   判「某件还有谁在引用」的那份代码侧语料，**当天第一版漏了两路**（运维脚本 · 规则档）
    #   ⇒ 差点把被引用的设计件当零引用死重搬走。
    #   ⚠️ 口径**只定义一次**（`audit_common.LIVE_MACHINE_GLOBS`）—— 光靠命令自己测自己
    #   **不够**（翻车正是"口径只写在脚本里"）⇒ 本条是钉它的那半边，缺一路即红。
    raw += check_live_machine()
    # `T17`（2026-09-24 立 · `TAIL-82`）：**闸门清单里每一把尺子都必须真有入口** ——
    #   ⭐ 一天内核出四例"僵尸闸门"（`shell_verify` · `cover_gap` · `audit_drift` · `audit_meta`），
    #   其中三例**从来没有 `__main__`** ⇒ 在闸门清单里跑了几个月，**0 行输出、rc 恒 0、什么都没判**。
    #   ⚠️ 清单**唯一出处 = 计划 `§22.1` 的 `foreach`**（本检查直接读它 ⇒ 新增尺子自动被查）。
    raw += check_gate_liveness()
    # `T18`（2026-09-24 立 · 排查件 §一 的元发现）：**登记在册的路径 / glob 常量必须解析得到真东西** ——
    #   ⭐ 当天三处失效同根（`tools/audit/` 的常量在 `TAIL-58` 搬目录后没跟改），症状全是
    #   「**检查在跑，其实扫空集**」；立本条当天就抓出第 4 例（`SCAN_GLOBS` 里 `CHANGELOG.md` 的旧地址）。
    raw += check_guard_constants()
    # `T14`/`T15`（2026-09-22 立 · 文档架构审计 §七-15 · 实现见 `audit_work.py`）：
    #   `T14` = scratch 超期（TTL 14 天）/ 落点合规；`T15` = artifacts md 白名单 ＋ work 文档文头四行。
    #   ⭐ 治「新区变新垃圾场」：分区只是分类学，**过期与元信息要机器盯着**才算闭环（⭐ 2026-10-01 四区 ⇒ 2026-10-04 五区）。
    raw += check_scratch_ttl()
    raw += check_artifacts_and_headers()
    # `T26`（2026-10-05 立 · `TAIL-236` 第 3 批）：⭐ **「结论已落地」⇒ 该降档**（**黄 · 只报不动**）——
    #   件在「已定稿 / 已实施」档，且 ① 件内 `TAIL-` 票**全销号** ＋ ② 件内**声明的「落地位置」真存在**
    #   ⇒ 报黄「该降档（下沉 / 归档）」。
    #   ⭐ 治的是 `work/README.md` §二 那条「用完就丢」**只有规矩、没有机器眼**
    #   （`docs/guides/document-governance.md` §三 那两行自己写着「应有判据、现无」）—— 那是用户"不安"的根因。
    #   ⛔ 两个客观信号**别改轴**（`TAIL-236` 决定 3）；⛔「零机器引用」不是判据，只是信号。
    #   ⚠️ **声明行写法**的唯一主人 = `docs/guides/work-records.md` §四；销号定义 = `audit_meta.TICKET_CLOSED`。
    raw += check_downgrade_candidates()
    # `T20`（2026-09-28 立 · 文档审计）：**保留期与容量** —— `backups/` 顶层条目 > 5（口径「留 5 份」）
    #   ＋ `tools/oneoff/` 件数 / 容量超线 ⇒ **黄**。
    #   ⚠️ 2026-10-01（`TAIL-204` 第 7 步）**撤掉**原来的第三条「`.workbuddy/scratch/` 活区规模」——
    #   它守的是**搬家遗留的旧落点**（盘上一直在、被 `.gitignore` 藏着 ⇒ `git status` 看不见），
    #   第 7 步已把旧落点**整棵清掉** ⇒ 判据失去对象（详见 `audit_work.check_retention` 末段）。
    #   ⭐ 起因：`README.md` 写着"留 5 份 · 月度清"，而 2026-09-22 整改设计自己给的验收判据
    #   "目录计数 ≤5（可数）"**从没被机器守过** ⇒ `TAIL-73` 销号只验了"唯一点"、没验"≤5" ⇒
    #   **口径在、判据无 ⇒ 静默漂**（43 个条目堆着，含 09-18 的旧快照）。
    raw += check_retention()
    # ⭐ `T27`/`T28`（2026-10-06 立 · `TAIL-234`）—— **交付面尾部守卫**，实现在同目录 `audit_face.py`：
    #   ① `T27` =「页脚标记之后还有非空行」—— ⛔ `T1`–`T26` 没一层能看见"内容掉到落款后面"
    #      （当天实测：`MOD-14.md` 两条 `ACC-*` 验收条目就在页脚下面，而**用例号是真的、路径是真的**）；
    #   ② `T28` =「`PRD/` 规格件**只许变长** + 编号表只许变多」—— 治WPS 云同步**整体盖回旧快照**
    #      （实测退化件**多数等长** ⇒ 只钉行数不够）。
    #   ⚠️ 两条都**只定义一次**（标记 / 排除目录 / 扫描面在 `audit_common`，基线表在 `audit_face`）。
    raw += check_footer_tail() + check_prd_baseline()
    # `T16`（2026-09-24 立 · `TAIL-20`）：**`T7a` 登记册必须在位** —— 读不到就静默降级成
    #   「全部未清」，而那个方向看着还更安全 ⇒ 必须升成红档才看得见。
    raw += check_cover_registry()
    # `T7` 登记：有能力的口径没被判据兜住（**逻辑在 tools/cover_gap.py** —— 别再内联）
    from cover_gap import T7_EXEMPT, check_cover_gaps         # noqa: PLC0415

    cover_gaps = check_cover_gaps(delivery_root(), baseline)
    skipped = [h for h in raw if h["level"] == SKIP]
    yellows = [h for h in raw if h["level"] == YELLOW]
    reds = [h for h in raw if h["level"] == RED]

    line = "=" * 78
    print(line)
    print(" 文档漂移自检 · doc_audit")
    print(f" 扫描 {len(docs)} 个文档 · {sum(len(d[3]) for d in docs)} 行 · 用例真源 {len(cases)} 条")
    print(line)
    print(f"必须修 {len(reds)} · 疑似 {len(yellows)} · 已豁免 {len(skipped)}"
          f"（豁免 = 行文本身在说「它废了」）")
    print()

    for tag, group, agg in (("必须修", reds, False),
                            ("疑似（都在留痕区 / 已在说明它废了 —— 仅聚合）", yellows, True),
                            ("已豁免（行文本身在声明它废了）", skipped, True)):
        if not group or (agg and not args.verbose and group is skipped):
            continue
        print(tag)
        print("-" * 78)
        if agg and not args.verbose:
            for rel, n in Counter(h["rel"] for h in group).most_common():
                print(f"  {n:>3} 条  {rel}")
        else:
            for h in group:
                # ⭐ 2026-10-06（`/retro` ⑤）：**每行自带档位标签**（`红/黄/豁免`）——
                #   原来档位只出现在**段标题**里 ⇒ 一旦用 `Select-String` 过滤输出，
                #   每行属于哪一段就**看不出来**（当天为此又临时写了个分组探针脚本）。
                print(f"  [{'红' if h['level'] == RED else ('豁免' if h['level'] == SKIP else '黄')}]"
                      f" [{h['code']}] {h['side']}·{h['rel']}:{h['line']}  {h['what']}")
                print(f"        {h['why']} → {h['fix']}")
                if args.verbose:
                    print(f"        原文：{h['text'][:150]}")
        print()

    if not reds and not yellows:
        print("✅ 无漂移：术语 / 用例号 / 路径 / 状态数字 全部一致")
        print()

    gaps_a = [h for h in cover_gaps if h["code"] == "T7a"]
    gaps_b = [h for h in cover_gaps if h["code"] == "T7b"]
    print(f"判据覆盖 `T7`（**有登记的能力、判据却没兜住** —— 登记档，不判红；"
          f"豁免 {len(T7_EXEMPT)} 类见代码 `T7_EXEMPT`）")
    print("-" * 78)
    print(f"  ⭐ `T7a` 无用例认领（末列没有 `ACC-*`）：{len(gaps_a)} 条"
          f" ｜ `T7b` 口径无人 cover：{len(gaps_b)} 条")
    if cover_gaps:
        for tag, grp in (("T7a · 无用例认领", gaps_a), ("T7b · 口径无人 cover", gaps_b)):
            if not grp:
                continue
            print(f"  -- {tag} --")
            for h in grp:
                print(f"  {h['rel'].replace('PRD/02-功能规格/', ''):<11} L{h['line']:<4} {h['what']}")
    else:
        print("  （无）")
    print()

    print(f"文件行数（>{LINE_LIMIT} 须登记拆分计划 · >{HARD_LIMIT} 须登记「为什么不拆」——**都是黄**）"
          "—— **这份清单就是登记，别抄进文档**")
    print("-" * 78)
    if sizes:
        for h in sizes:
            print(f"  {'红' if h['level'] == RED else '黄'}  {h['rel']:<52} {h['what']}")
    else:
        print("  （无超限文件）")
    print()

    # ⭐ `T23` **常态也要报出一行**（2026-10-05 立）：口径齐全不是"没消息"，是**有消息说它齐全**
    # —— 否则闸门里那条判据**跑过但看不见**（本仓"判据存在 ≠ 被看见"那族）。
    if not any(h["code"] == "T23" for h in raw):
        print("活机器口径 `T23` 结论：%d 条 glob · 六路齐全 ✅"
              "（少一路 / 空命中 / 接线掉 ⇒ 报红；反向灵敏度 `_mut_livemachine` 按受影响判据隔离自证）"
              % len(LIVE_MACHINE_GLOBS))
        print()
    # ⭐ `T24`/`T25` **同样"常态报一句"**（与 `T23` 同一条理由）：落点守卫是"没消息就是好消息"型
    #   —— 一声不响时，读者分不清"它判过且干净"与"它压根没跑"（本仓"判据存在 ≠ 被看见"那族）。
    if not any(h["code"] == "T24" for h in raw):
        print("仓库根落点 `T24` 结论：根上条目全部登记在册 ✅"
              "（`ROOT_ALLOW` 常驻 ∪ `.gitignore` 暂存；多出来的即红 · 反向灵敏度 `M27`）")
        print()
    if not any(h["code"] == "T25" for h in raw):
        print("`.gitignore` 落点 `T25` 结论：里面写的仓库内路径全部真存在 ✅"
              "（核不到即红 · 反向灵敏度 `M28`）")
        print()
    # ⭐ `T26` **同样"常态报一句"**（同 `T23`/`T24`/`T25`）：它是"没消息就是好消息"型
    #   —— 一声不响时读者分不清"它判过且没有该降档的件"与"它压根没跑"。
    if not any(h["code"] == "T26" for h in raw):
        print("降档判据 `T26` 结论：过程区没有「已声明落地、件内票已全销号」的已定稿/已实施件 ✅"
              "（有即报黄「该降档」· 只报不动 · 反向灵敏度 `_mut_downgrade`）")
        print()
    # ⭐ `T27`/`T28` **同样"常态报一句"**（同 `T23`/`T24`/`T25`/`T26`）：同样是"没消息就是好消息"型——
    #   而这一对**比前几条更需要有**：它们扫的是**交付面**，人肉翻不到。
    #   ⚠️ 这一句的**内容由 `audit_face.summary()` 出**（⛔ 别在两处各数一遍件数 —— 那正是"同一件事两处写"）。
    if not any(h["code"] in ("T27", "T28") for h in raw):
        print(face_summary() + "（页脚之后不许有内容 · 篇幅变化仅提示调查；反向灵敏度 `_mut_facedoc`）")
        print()
    bad = bool(reds or any(h["level"] == RED for h in sizes))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
