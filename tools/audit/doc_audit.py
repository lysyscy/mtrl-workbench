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
| `T3` | **幽灵路径** —— 反引号里的仓库内路径两侧都找不到 | 文件系统 |
| `T4` | **状态数字失配** —— 执行情况「当前版本」行的四态 ≠ 实际 | `artifacts/acc_results.json` |
| `T5` | **行数超限** —— 单文件 >400（黄 · 须登记拆分计划）/ >600（黄 · 须登记"为什么不拆"）<br>⚠️ 2026-09-21 **用户裁定：>600 从红降黄**（行数是代理指标，不作禁合入闸门） | 源文件行数（**输出即登记清单**）＋ `ops/阈值表.md` |
| `T6` | **尾巴台账** —— 清点处在不在（计划 §15）/ 栏位 / 编号 / 落点 / 计数 | `.workbuddy/plans/开发计划-主文档.md` |
| `T7a`/`T7b` | **判据覆盖** —— 有登记的能力却没判据兜住（**登记档，不判红**） | `cover_gap.py` |
| `T8` | ⭐ **已撤项复活** —— 用户裁定取消的东西**不得在代码里长回来** | `audit_common.CANCELLED` |
| `T9` | ⭐ **纪律的「口径出处」标记** —— `MEMORY.md` §八 每条必须带 `[用户]`/`[交付面]`/`[助手自定]` | `.workbuddy/memory/MEMORY.md` |
| `T10` | ⭐ **文档读预算** —— 每会话**注入/必读**档超预算（黄 + 登记；治「太长读不完 ⇒ 只 grep ⇒ 没搜到的就丢了」） | `ops/阈值表.md` ＋ `audit_meta.DOC_BUDGETS` |
| `T11` | ⭐ **建议类报告必须带「待办登记回执」** —— `artifacts/` 里的审计/提案/建议**不许只活在报告里** | `artifacts/*.md` ↔ 计划 §15 |
| `T12` | ⭐ **文档分层与命名约定** —— `plans/` 只许两份活文档（其余 `归档-` 打头）· `memory/` 日志必须进 `journal/` · 根只许 `README.md` | 根 `README.md` 的四层表 ＋ 本件三张白名单 |
| `T13` | ⭐ **主文档过程回潮** —— 计划主文档行数超预算（1700）· 标题出现过程词（逐批/逐次/收官记录）⇒ 黄：该块**该下沉归档了**（`§13.1`「完成的就扔出去」的机器守） | `.workbuddy/plans/开发计划-主文档.md` |
| `T14` | ⭐ **scratch 超期 / 落点合规** —— `work/00-scratch/` 超 14 天未升档未删 · `tools/` 根与 `logs/` 再现散件 ⇒ 黄（`audit_work.py`） | 文件系统 mtime |
| `T15` | ⭐ **产物白名单 ＋ 工作记录元信息** —— `artifacts/` 只许工具生成物 md · `work/` 五区文档必须带文头四行（读者/回答什么/何时读/状态）⇒ 黄 | `audit_work.py` 白名单 |
| `T16` | ⭐ **`T7a` 登记册必须在位** —— 登记册**读不到 / 解析不出条目** ⇒ **红**（治「静默降级成全部未清」） | `cover_gap.CLEARED_REGISTRY` |

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
    python tools/audit/doc_audit.py --ui         # 顺带跑交付面四检（需 node）
    python tools/audit/doc_audit.py --block      # 打印可粘贴进交接文件的「当前状态」块

⚠️ 本工具**只读**（`--block` 也只打印、不写文件）。

**本文件是薄壳** —— 检查逻辑已拆到同目录三件（`T5` 逼的，本文件曾 597 行）：
`audit_common.py`（常量 ＋ 扫描基础设施）· `audit_drift.py`（`T1`–`T4`）·
`audit_meta.py`（`T5`/`T6` 台账与行数 · `T9` 纪律出处 · `T10` 读预算 · `T11` 报告回执 · `T12` 分层约定）。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_common import (                                        # noqa: E402
    RED, REPO_ROOT, SKIP, YELLOW, delivery_root, iter_docs,
)
from audit_drift import (                                         # noqa: E402
    check_acc_ids, check_cancelled, check_count_anchors, check_paths, check_section_refs,
    check_status_line, check_terms,
)
from audit_meta import (                                          # noqa: E402
    HARD_LIMIT, LINE_LIMIT, check_doc_budgets, check_doc_layout, check_file_sizes,
    check_gate_liveness, check_guard_constants, check_plan_process, check_report_receipts,
    check_rule_origins, check_tail_ledger,
)
from audit_work import (                                          # noqa: E402
    check_artifacts_and_headers, check_scratch_ttl,
)


# ------------------------------------------------------------------- 四检（可选）


def run_ui_checks() -> list[str]:
    node = Path(r"C:\Users\Administrator\.workbuddy\binaries\node\versions\22.22.2-3\node.exe")
    root = delivery_root()
    if not node.exists() or not root:
        return ["  （跳过：找不到 node 或交付面根）"]
    demo = root / "demo"
    if not (demo / "_smoke.js").exists():
        return ["  （跳过：交付面 demo/ 里没有四检脚本）"]
    out = []
    for s in ("_smoke", "_doccheck", "_links", "_ids"):
        js = demo / f"{s}.js"
        if not js.exists():
            out.append(f"  {s:<10} （无此脚本）")
            continue
        r = subprocess.run([str(node), str(js)], cwd=str(demo), capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        concl = next((l.strip() for l in reversed((r.stdout or "").splitlines())
                      if "====" in l), "")
        out.append(f"  {s:<10} 退出码={r.returncode}  {concl[:66]}")
    return out


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
    ap.add_argument("--ui", action="store_true", help="顺带跑交付面四检（需 node）")
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
    # `T10`/`T11`（2026-09-21 立 · 用户：「文档太长了你也读不完 ⇒ 容易过期」）：
    #   `T10` = **文档读预算**（每会话注入/必读档超预算 ⇒ 黄 + 登记）；
    #   `T11` = **建议类报告必须带「待办登记回执」**（⇒ 报告里的建议不会烂在报告里）。
    raw += check_doc_budgets()
    raw += check_report_receipts()
    # `T12`：**文档分层与命名约定**（`plans/` 只许两份活文档 · `memory/` 日志必须进 `journal/` ·
    #   根只许 `README.md`）—— ⭐ 把"目录约定"从**口头纪律**变成**机器守**（用户 2026-09-21 要求
    #   「尽量减少…需要我停下来检查文档」）。
    raw += check_doc_layout()
    # `T13`（2026-09-22 立 · 用户问「为啥还是会有过期现象？是不是把太多过程塞到开发计划里了？」）：
    #   **主文档过程回潮守卫** —— 行数超预算 ＋ 标题出现过程词 ⇒ 黄（该下沉归档了）。
    #   ⭐ 治的是"§13.1 早有『完成的就扔出去』的裁定，却只有触发点、没有机器守"。
    raw += check_plan_process()
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
    #   ⭐ 治「新区变新垃圾场」：五区建好了只是分类学，**过期与元信息要机器盯着**才算闭环。
    raw += check_scratch_ttl()
    raw += check_artifacts_and_headers()
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
                print(f"  [{h['code']}] {h['side']}·{h['rel']}:{h['line']}  {h['what']}")
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

    if args.ui:
        print("交付面四检")
        print("-" * 78)
        for l in run_ui_checks():
            print(l)
        print()

    return 1 if (reds or any(h["level"] == RED for h in sizes)) else 0


if __name__ == "__main__":
    raise SystemExit(main())
