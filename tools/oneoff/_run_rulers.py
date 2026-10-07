"""收口闸门一把跑：`CMDS` 里的每一把逐个跑、只打印"该读的那几行"，rc≠0 的列进 `BAD`。
⚠️ **条数别抄在这里**（⛔ 抄了必漂，`tools/README.md` 纪律）—— 清单的**唯一出处 = 本件 `CMDS`**。

⭐ 2026-10-01（`TAIL-205`）起**末尾多一步**：**守尺子的变异自证**（`tools/oneoff/_run_muts.py` ·
  ⛔ 支数看那件自己的输出）—— `tools/mut/**` 原先不在任何闸门里
  ⇒ "加了反向灵敏度却没人跑" ⇒ 一天抓到 4 例假绿。
⭐ 2026-10-05（`TAIL-236` 批 2）：`CMDS` 里也多了 `refs_query.py --selftest`
  —— 同族：命令自身的自测不在闸门里 ⇒ 它的检索逻辑坏了没人知道。
⭐⭐ 2026-10-06（`TAIL-241`）：末尾那把 pytest **按需触发 + 按范围选测**
  （`tools/oneoff/_pytestscope.py` —— **该跑什么的单一出口**；⛔ 秒数看那次运行自己的输出）。
  两种形态都要看得见：跑了 ⇒ 打印「跑了哪些 / 跳过了哪些」；跳过 ⇒ 打印**为什么跳**。

**为什么单独落成文件**：2026-09-29 实测 —— 这套命令用 `python -c "…\\nfor …"` 的**内联多行**写法
在 PowerShell 里**反复被吃掉换行**（`unexpected character after line continuation character` ✗）。
⇒ 凡是"反复要跑的一串命令"，落成脚本；⛔ 别在命令行里拼多行 Python。

跑法：`backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_run_rulers.py`
      `… --all`   #: 连 pytest 一起跑（默认只跑尺子 —— 没动代码时不必）
                   #: ⚠️ `--all` **不再等于「pytest 全套」** —— 跑哪些由 `_pytestscope` 说了算
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
PY = str(ROOT / "backend" / ".venv" / "Scripts" / "python.exe")
#: ⭐ 2026-10-06（`TAIL-241`）：**pytest 段的选测范围**由 `_pytestscope` 独家说了算
#:   （三张名单 ＋ import 闭包 ＋ 缺口自检都在那件里 ⇒ 本件⛔ 不再自己判断跑什么）。
sys.path.insert(0, str(ROOT / "tools" / "oneoff"))
import _pytestscope as _scope      # noqa: E402

KEEP = ("必须修", "结论：", "_smoke", "_links", "_ids", "_doccheck", "台账一致", "逐行一致",
        "判据点合计", "幽灵", "[T6]", "[T10]", "[T13]", "[T20]",
        "自测 ")          # ⭐ `refs_query --selftest` 的"自测 N/N"那一行（2026-10-05 加）
# ⚠️ 「结论**：**」带冒号：光靠 `结论` 会把**文件名里带"结论"两字**的件名也抓进来
#    （实测 `refs` 那一行后面跟了两行 `ops/…-实测结论.md` ⇒ 闸门输出里全是噪声）。

CMDS: list[tuple[str, list[str]]] = [
    ("tools/audit/doc_audit.py", ["--ui"]),
    ("tools/audit/audit_drift.py", []),
    ("tools/audit/audit_meta.py", []),
    # ⭐ 2026-10-05（`/retro` 候选④）：`audit_work` 此前**不在闸门里** ⇒ 它的输出没人看
    #   （`T14`/`T15`/`T20` 三条黄档 · 单跑过是 0/0）⇒ 「工具上了没人跑」的第一例。
    ("tools/audit/audit_work.py", []),
    ("tools/audit/syntax_audit.py", []),
    ("tools/audit/ui_parity.py", []),
    ("tools/audit/wiring_audit.py", []),
    ("tools/audit/chain_audit.py", []),
    ("tools/audit/asset_audit.py", []),
    ("tools/audit/claim_audit.py", []),
    ("tools/audit/cover_gap.py", []),
    ("tools/audit/prg_form_audit.py", []),
    ("tools/audit/shell_verify.py", []),
    ("tools/audit/sticky_probe.py", []),
    ("tools/audit/mut_cover.py", ["--check"]),
    ("tools/audit/acc_report.py", []),
    # ⭐ 2026-10-05（`TAIL-236` 批 2 · `/code-review` 指出）：`refs` 命令**自身的自测**
    #   原先不在任何闸门里 ⇒ "命令的检索逻辑坏了没人知道"（同 `tools/mut/**` 那族假绿）。
    #   ⛔ 只进收工闸门、不进 `pre-commit`（那个只跑便宜子集）。
    ("tools/audit/refs_query.py", ["--selftest"]),
    # ⭐ 2026-10-06（`TAIL-236` 第 4 批）：**降档动作命令自身的自测**进闸门 —— 同族理由
    #   （"命令的搬运逻辑坏了没人知道"）。⚠️ 它自测里会**跑一遍那 5 把秒级尺子**（跑前/跑后比 rc），
    #   所以比别的 `--selftest` 慢一档（十几秒）—— 换来的是"降档动作不会悄悄改变闸门结论"有断言。
    ("tools/oneoff/_doc_downgrade.py", ["--selftest"]),
    ("tools/probe/_audit_face.py", []),
]

#: ⭐ 触发全套变异自证的**改动形状**（`TAIL-237`）—— ⛔ **单一出口**，别在别处再写一份。
#: ⚠️ 判据的用意：慢集那几支的**靶是仓内的尺子/文档面** ⇒ 只有动了这些，它们才可能变哑。
#: ⛔ **故意不含**（每条都是查案查出来的，不是随手剔的）：
#:   · `backend/app` 与 `shell/` —— 那两处的守卫是 pytest（判据层），本票不动它；
#:   · `ops/` —— 只出运维脚本，不进任何变异件的靶；
#:   · ⭐ **`.codebuddy/`** —— 票面/日志/台账**每轮都在写** ⇒ 留在表里等于**判据恒真**：
#:     最常见的"写文档"流程一节能都省不到（`/code-review` 2026-10-06 抓出，实测 325.9s > 改前 308.7s）。
#:     而它并不需要慢集来守 —— 票面/台账的真守卫是 `T6`（票面栏齐全 ＋ 登记即排期），
#:     那是**收工闸门里的常驻尺子**，本来就每轮跑。
#:   · ⭐ **仓外交付面**（`_mut_uicheck` 的靶）—— git 看不见它 ⇒ 留在慢集等于"外部被回退了也不验"。
#:     正解：那支已**移出慢集**（见 `_run_muts.py` 的 `SLOW_KEY`）⇒ 交付面每轮都被验。
_SLOW_TRIGGERS = ("tools/audit/", "tools/mut/", "tools/probe/", "tools/oneoff/",
                  "backend/tests/", "README.md", "AGENTS.md")


def _touched_rulers() -> list[str]:
    """工作区（vs `HEAD`）里有没有动过**尺子/判据/闸门脚本** ⇒ 该跑全套。返回命中清单（空 = 没动）。

    ⭐ **为什么用 `git diff` 而不是"记住上次跑过"**：后一种要引入状态（时间戳/计数/记忆文件）⇒
    本仓吃过"靠回忆 ⇒ 静默失效"的亏。`git diff` 是**现成、可复核、提交后自然归零**的事实。
    ⚠️ **必须把 untracked 也算进来**（`/code-review` 2026-10-06 抓出）：只看已跟踪件时，
    「**新建一把尺子**」——恰恰是最该跑全套的场景——会让判据失灵、闸门静默跳过慢集。
    ⇒ 两问都问（`diff` ＝已跟踪件的改动，`ls-files --others` ＝尚未跟踪的新件）。
    """
    # ⭐ 单一出口：`changed_paths()` 住在 `_pytestscope`（`git diff` 口径只此一处）
    # ⚠️ 它算不出来时返回 `None` ⇒ 这里**按「全都动过」处理**（宁可跑全套，也别静默跳慢集）
    names = _scope.changed_paths()
    if names is None:
        return list(_SLOW_TRIGGERS)
    return sorted({n for n in names for t in _SLOW_TRIGGERS if n.startswith(t) or n == t})


def main() -> int:
    with_pytest = "--all" in sys.argv
    bad: list[str] = []
    for rel, args in CMDS:
        p = subprocess.run([PY, "-X", "utf8", str(ROOT / rel)] + args, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", cwd=str(ROOT))
        ls = [x for x in (p.stdout or "").strip().splitlines() if x.strip()]
        keep = [x for x in ls if any(k in x for k in KEEP)]
        print("%-34s rc=%d  %s" % (rel, p.returncode, " || ".join(keep[:3])[:175]))
        if p.returncode:
            bad.append(rel)
    # ⭐⭐ 2026-10-01（`TAIL-205`）：**守尺子的变异自证** —— `tools/mut/**` 原先**不在任何闸门里**
    #    ⇒ "加了反向灵敏度却没人跑" ⇒ 2026-10-01 一天抓到 4 例"靶烂掉 / 判法烂掉"（假绿）。
    # ⭐⭐⭐ 2026-10-06（`TAIL-237` · 用户「改点东西太慢」）：**这一支按需触发** ——
    #    实测全套 **185 秒**（慢集 4 支占 156 秒）⇒ 改一行代码也要等 3 分钟。
    #    ⇒ 判据 = **本轮有没有动"尺子/判据/文档/交付面"**（`git diff` 工作区 vs HEAD）：
    #      · 没动 ⇒ 只跑**快集**（实测 29 秒）—— 改业务代码这种小修小改走这条；
    #      · 动了 ⇒ 跑**全套**（尺子自己的靶被改了 ⇒ 必须重验，否则它们烂掉没人知道）。
    #    ⚠️ **零状态**：判据是"工作区有没有相关改动"⇒ 提交后自然变快；⛔ 不引计数/时间戳/记忆文件。
    mut_args: list[str] = []
    hit = _touched_rulers()
    if hit:
        mut_args = []
        print(f"  ⏭ 变异自证跑**全套**（本轮动过 {len(hit)} 处尺子/判据/闸门脚本：{', '.join(hit[:4])}"
              f"{' …' if len(hit) > 4 else ''}）")
    else:
        mut_args = ["--fast"]
    p = subprocess.run([PY, "-X", "utf8", str(ROOT / "tools" / "oneoff" / "_run_muts.py")] + mut_args,
                       capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(ROOT))
    keep2 = [x for x in (p.stdout or "").strip().splitlines() if x.strip()][-1:]
    print("%-34s rc=%d  %s  %s" % ("守尺子的变异自证(_run_muts)", p.returncode,
                                    "全套" if not mut_args else "快集", " || ".join(keep2)[:150]))
    if p.returncode:
        bad.append("守尺子的变异自证(_run_muts.py)")
    if with_pytest:
        # ⭐⭐ 2026-10-06（`TAIL-241` 第 0/1 批）：**pytest 按需触发 + 按范围选测**。
        #   第 0 批：`backend/` 与「pytest 在仓外也读的那些落点」都没动 ⇒ 整把跳过（**零漏跑风险**）。
        #   第 1 批：动了 ⇒ 按 import 闭包选测，**并强制含全仓敏感清单**；算不出就退回全套。
        #   ⛔ 本段只负责"跑与打印"；**该跑什么**由 `_pytestscope` 独家说了算（单一出口）。
        # ⭐⭐ **选集自检每轮都跑**（`TAIL-239` 同族）：新加一个测试件而没落进任何一档 ⇒ 当场报红。
        #   ⛔ 放在这里而不是 `CMDS`：它必须**紧挨着选测**（选测错了它得立刻说话）。
        cover_rc, cover_line = _scope.report_cover()   # ⛔ 结论由那件自己写，本段只转发
        print("%-34s rc=%d  %s" % ("选集自检(_pytestscope)", cover_rc, cover_line))
        if cover_rc:
            bad.append("选集自检(_pytestscope --cover-only)")
        pl = _scope.plan(_scope.changed_paths())
        if not pl.run:
            print("%-34s ⏭ 跳过  %s" % ("pytest", pl.reason))
        else:
            # ⚠️ 环境变量**由 `_pytestscope` 独家给**（⛔ 别在这儿再抄一份）：
            #   **子集跑不许写权威四态档** —— 那是 `TAIL-241` 当场踩到的坑（闸门自己污染自己）。
            import os
            e = dict(os.environ, **_scope.pytest_env(pl))
            cmd = [PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--tb=line"] + pl.argv()
            p = subprocess.run(cmd, cwd=str(ROOT / "backend"), env=e, capture_output=True,
                               text=True, encoding="utf-8", errors="replace")
            tail = [x for x in (p.stdout or "").strip().splitlines() if x.strip()][-2:]
            print("%-34s rc=%d  %s" % ("pytest", p.returncode, " || ".join(tail)[:175]))
            # ⛔ **不许只跑子集就报绿**：必须能说出「跑了哪些 / 跳过了哪些」
            #   （否则「变绿」与「没跑」分不开 —— 票面铁律）。
            allf = sorted(x.name for x in (ROOT / "backend" / "tests").glob("test_*.py"))
            if pl.files:
                ran, skipped = set(pl.files), [n for n in allf if n not in set(pl.files)]
                print("   ▸ 跑了 %d 件：%s" % (len(ran), " ".join(sorted(ran)[:6])
                                              + (" …" if len(ran) > 6 else "")))
                print("   ⏭ 跳过 %d 件（够不着本轮改动）：%s"
                      % (len(skipped), " ".join(skipped[:6]) + (" …" if len(skipped) > 6 else "")))
            else:
                print("   ▸ 跑全套 %d 件（%s）" % (len(allf), pl.reason))
            if p.returncode:
                bad.append("pytest")
    print("BAD:", bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
