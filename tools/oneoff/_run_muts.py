"""**守尺子的变异自证** —— 一把跑那几个「守尺子 / 守结构 / 守文档面」的变异件（它们是"尺子的尺子"）。

⭐⭐ 为什么有它（`TAIL-205` · 2026-10-01）：
    `tools/mut/**` 有 90+ 支**反向灵敏度**，却**不在任何闸门里**（`_run_rulers.py` 不含它）⇒
    加了"能证伪的判据"却**没人会跑** ⇒ **靶烂掉/判法烂掉都没人知道**。2026-10-01 一天抓到 4 例：
      ① `_mut_t20` **靶太薄**（基线手工快照已 0/5，只加 2 个到不了 6 ⇒ **哑靶**，报 `None → None`）
      ② `_mut_t12` **漏 `-X utf8`** ⇒ 子进程中文输出乱码 ⇒ 拿文件名比永远比不上 ⇒ `0/3` 却报"复原干净"（**假绿**）
      ③ `_mut_t14t15` 同款漏 `-X utf8`（返回 -1 ⇒ 三条全"未被抓到"）＋ **靶假设过期**（要求基线 0 命中，现实有 5 条黄）
      ④ `_oneoff_measure.py` 漏 `core.quotepath=false` ⇒ 非 ASCII 路径直接崩（**一直是坏的**）
    ⇒ 根因不是"某支写错了"，是**"没人跑"**。本件把最关键的一撮**接进收工闸门**（`_run_rulers.py` 调它）
      ⇒ 它们的烂掉**最迟下一次收工就被看见**。

**跑什么**：`KEY` 那一套（⚠️ 条数看本件输出，⛔ 别在别处抄 —— 会涨）—— 选它们的标准 =
**靶是"尺子 / 结构 / 文档面"本身**（业务面的变异件由各自域负责，按需用 `--all` 扫）。

跑法：`backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_run_muts.py`
      `… --all`          #: 跑 `tools/mut/**` 全部（很慢：有的支要跑 pytest/真机 ⇒ 按需，别进闸门）
      `… --all --timeout 900`
      `… --fast`         #: ⭐ 2026-10-06（`TAIL-237`）**只跑快集**（跳 `SLOW_KEY`）—— 收工闸门默认走这条
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
PY = str(ROOT / "backend" / ".venv" / "Scripts" / "python.exe")
MUT = ROOT / "tools" / "mut"

#: ⭐⭐ 慢集 = **每支实测 >20 秒**的那些（`TAIL-237`）—— ⭐ **秒数看每次运行自己打的那行**（⛔ 别抄进代码/文档，
#:   它随机器与靶件变化；2026-10-06 首次分层时抄了 6 处，同日 `/code-review` 判它违规并已全部撤掉）。
#: ⭐ **为什么按秒数分、而不是按"我以为它重要吗"**：本件**每轮都打印每支秒数** ⇒ 分层依据是**量出来的**，
#:   不靠谁记得住 ⇒ 别人接手也复现得出。
#: ⛔ **单一出口**：别在别处再写一份"哪些是慢的"（本仓规矩：同一条口径只许有一处）。
#: ⚠️ **漂移怎么办**：`FAST_BUDGET` ＋ `SLOW_BUDGET` 那两道提醒会自动喊（见 `main`）—— ⛔ 不靠人记得回来改。
FAST_BUDGET = 20.0
SLOW_BUDGET = 60.0

#: 慢集（`--fast` 跳过它们；跑全套时照跑）
SLOW_KEY: frozenset[str] = frozenset({
    "_mut_docaudit.py", "_mut_shellapi.py", "_mut_segments.py",
})

#: ⭐⭐ **刻意留在快集、且超预算也不提醒挪走**的那几支（`/code-review` 2026-10-06 抓出后才补上，
#:   否则第一轮就出现"提醒说该挪、而它挪了就会出事故"的自相矛盾 ⇒ **提醒变成噪音**）：
#:   `_mut_uicheck` —— 靶在**仓外交付面**，`git diff` 看不见 ⇒ 挪进慢集等于"**外部被回退也不验**"
#:   （`TAIL-234` 记的正是交付面被云同步回退过一次、41 处差异尺子只看见 2 处）。
#:   它实测在 `FAST_BUDGET` 上下 ⇒ **这一条是"按理由豁免超时提醒"，不是"免检"**。
KEEP_FAST: dict[str, str] = {
    "_mut_uicheck.py": "靶在仓外交付面，git 看不见 ⇒ 必须每轮验（挪进慢集＝外部回退不验）",
}

#: ⭐ 关键集：靶是**尺子自身 / 结构守卫 / 文档面**的那几支（⇒ 它们烂掉 = 一整片守卫静默失效）
KEY: tuple[tuple[str, str], ...] = (
    # ⚠️ 说明里**不抄条数**（2026-10-05 `/code-review` 指出：那与本件 docstring 的"共 N 条"是
    #    同一件事两处写 —— 而 docstring 自己就写着"条数看本件输出、⛔ 别在别处抄"）。
    ("_mut_docaudit.py", "doc_audit 的 T1–T19 ＋ T24/T25 ＋ T4 计数锚点（条数看本件输出）"),
    # ⭐ 2026-10-06（`TAIL-238`）：`T3` **叙述豁免收窄**的两个方向（真幽灵仍红 · 叙述句豁免）
    #   ＋「票仓不放水」「距离闸仍承重」—— ⛔ 不接进来 = 收了判据却没人跑它，烂掉无人知。
    ("_mut_t3_narr.py", "T3 幽灵路径的叙述豁免（真幽灵仍红 · 叙述句豁免 · 票仓不放水 · 距离闸承重）"),
    ("_mut_injectsplice.py", "T22 注入档「两行粘成一行」（+ 正常排版不许误伤）"),
    ("_mut_linewalls.py", "T21 文档「字墙」（单行 >800 字 · 基线只许变短）"),
    ("_mut_countanchors.py", "T4 的四类计数锚点"),
    ("_mut_claim.py", "claim_audit（裁定必须同行写日期＋出处）"),
    ("_mut_uicheck.py", "doc_audit --ui 的交付面四检"),
    ("_mut_covergap.py", "cover_gap（口径覆盖缺口登记册）"),
    ("_mut_t12.py", "T12 分层与命名"),
    ("_mut_t14t15.py", "T14/T15（scratch TTL · work 区文头 · artifacts 白名单）"),
    ("_mut_t20.py", "T20 保留期与容量（backups 上限 · oneoff 件数容量）"),
    ("_mut_segments.py", "真机自检**段注册表**的顺序守卫（`TAIL-215` 批 1 · 离线 · 秒级）"),
    ("_mut_shellapi.py", "壳的**语义口径**（`TAIL-219` 批 1：认结构 / 找不到必抛 · 离线 · 秒级）"),
    ("_mut_livemachine.py", "T23 活机器口径（`TAIL-236` 批 2：缺一路/空命中/复述/接线 ＋ 正常不误报）"),
    # ⚠️ 这一支的**方向与众不同**：票面要的是「抽掉一个信号 ⇒ 必须**不再**报」——
    #    `_mut_docaudit` 的框架只会断言"报了" ⇒ 表达不出这个方向（见该件 docstring）。
    ("_mut_downgrade.py", "T26 降档判据（`TAIL-236` 批 3：两个信号各撤一次必须不再报）"),
)


def run_one(p: pathlib.Path, timeout: int) -> tuple[int, float]:
    t = time.time()
    try:
        r = subprocess.run([PY, "-X", "utf8", str(p)], cwd=str(ROOT),
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=timeout)
        rc = r.returncode
        if rc:
            tail = [x for x in ((r.stdout or "") + (r.stderr or "")).strip().splitlines() if x.strip()][-3:]
            for x in tail:
                # ⚠️⭐ 2026-10-05（`/retro`）：**带上件名** —— 子进程的尾巴行是**先于**下面那行
                #   "结果行"打印的 ⇒ 不加归属时，读者会把它当成**上一支**的失败原因
                #   （当天实测误读一次：把 `_mut_linewalls` 的自检当成 `_mut_injectsplice` 的）。
                print(f"        [{p.name}] {x[:170]}")
    except subprocess.TimeoutExpired:
        print(f"        [{p.name}] ⚠️ 超过 {timeout}s 未结束 ⇒ **算未验证**（⛔ 不当通过）")
        rc = 124
    return rc, time.time() - t


def main() -> int:
    args = sys.argv[1:]
    timeout = 900
    if "--timeout" in args:
        timeout = int(args[args.index("--timeout") + 1])
    fast_only = "--fast" in args
    if "--all" in args:
        cases = [(p.name, "（按需全跑）") for p in sorted(MUT.glob("_mut_*.py"))]
    else:
        cases = [(n, why) for n, why in KEY if (MUT / n).exists()]
        miss = [n for n, _ in KEY if not (MUT / n).exists()]
        if miss:
            print("⛔ 关键集里有件**不在了**（改名/删件 ⇒ 本件要跟改）：", ", ".join(miss))
            return 1
        if fast_only:
            skipped = [n for n, _ in cases if n in SLOW_KEY]
            cases = [(n, w) for n, w in cases if n not in SLOW_KEY]

    bad: list[str] = []
    fast_hit: list[str] = []
    slow_hit: list[str] = []
    spent = 0.0
    mode = "快集（--fast）" if fast_only and not ("--all" in args) else "关键集"
    print(f"── 变异自证（{len(cases)} 支 · {mode} · timeout {timeout}s/支）")
    if fast_only and not ("--all" in args):
        print(f"   ⏭ 已按需跳过慢集 {len(SLOW_KEY)} 支 —— ⛔ 本次**没验**它们；"
              f"动了尺子/判据/闸门脚本请跑不带 `--fast` 的全套")
    for name, why in cases:
        rc, sec = run_one(MUT / name, timeout)
        spent += sec
        flag = "✅" if rc == 0 else "⛔"
        print(f"  {flag} {name:32s} rc={rc:<3d} {sec:6.1f}s   {why}")
        if rc:
            bad.append(name)
        if name not in SLOW_KEY and name not in KEEP_FAST and sec > FAST_BUDGET:
            fast_hit.append(f"{name}（{sec:.1f}s）")
        if name in SLOW_KEY and sec > SLOW_BUDGET:
            slow_hit.append(f"{name}（{sec:.1f}s）")
    # ⚠️⭐ 2026-10-06（`TAIL-237`）：**秒数只在这里算** —— 上面每行都是当次实测值。
    #   ⛔ 别把它抄进代码注释/文档/票名（首次分层时抄了 6 处，同日 `/code-review` 判违规并已撤掉）。
    print(f"── 本次合计 {spent:.1f} 秒（{len(cases)} 支）")
    print("BAD:", bad)
    if bad:
        print("  ⚠️ 上面这些 = **反向灵敏度没跑过**（要么判据变了、要么靶烂了）—— ⛔ 别当它是「环境问题」，去看那一支。")
    # ⚠️⭐ **分层漂移的机器提醒** —— 快集里长出慢支 / 慢集里长出超长支时自动喊，
    #   ⛔ 不靠"谁记得回来看一眼"（那正是本仓反复吃的那类静默漂移）。
    if fast_hit:
        print(f"  ⚠️ **快集超时提醒**：{'、'.join(fast_hit)} 已超 {FAST_BUDGET:.0f}s "
              f"⇒ 该挪进 `SLOW_KEY`（本件单一出口），否则每轮都在吃它的秒数。")
    if slow_hit:
        print(f"  ⚠️ **慢集过长提醒**：{'、'.join(slow_hit)} 已超 {SLOW_BUDGET:.0f}s "
              f"⇒ 该看它为什么变慢（靶件变大？多跑了一次真机？）。")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
