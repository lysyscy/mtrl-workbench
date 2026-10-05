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
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
PY = str(ROOT / "backend" / ".venv" / "Scripts" / "python.exe")
MUT = ROOT / "tools" / "mut"

#: ⭐ 关键集：靶是**尺子自身 / 结构守卫 / 文档面**的那几支（⇒ 它们烂掉 = 一整片守卫静默失效）
KEY: tuple[tuple[str, str], ...] = (
    ("_mut_docaudit.py", "doc_audit 的 T1–T19 ＋ T4 计数锚点（本件 M1–M23）"),
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
                print(f"        {x[:170]}")
    except subprocess.TimeoutExpired:
        print(f"        ⚠️ 超过 {timeout}s 未结束 ⇒ **算未验证**（⛔ 不当通过）")
        rc = 124
    return rc, time.time() - t


def main() -> int:
    args = sys.argv[1:]
    timeout = 900
    if "--timeout" in args:
        timeout = int(args[args.index("--timeout") + 1])
    if "--all" in args:
        cases = [(p.name, "（按需全跑）") for p in sorted(MUT.glob("_mut_*.py"))]
    else:
        cases = [(n, why) for n, why in KEY if (MUT / n).exists()]
        miss = [n for n, _ in KEY if not (MUT / n).exists()]
        if miss:
            print("⛔ 关键集里有件**不在了**（改名/删件 ⇒ 本件要跟改）：", ", ".join(miss))
            return 1

    bad: list[str] = []
    print(f"── 变异自证（{len(cases)} 支 · timeout {timeout}s/支）")
    for name, why in cases:
        rc, sec = run_one(MUT / name, timeout)
        flag = "✅" if rc == 0 else "⛔"
        print(f"  {flag} {name:32s} rc={rc:<3d} {sec:6.1f}s   {why}")
        if rc:
            bad.append(name)
    print("BAD:", bad)
    if bad:
        print("  ⚠️ 上面这些 = **反向灵敏度没跑过**（要么判据变了、要么靶烂了）—— ⛔ 别当它是「环境问题」，去看那一支。")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
