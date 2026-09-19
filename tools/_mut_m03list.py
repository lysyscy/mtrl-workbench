"""**反向灵敏度**：证明 `test_wired_m03_list.py`（`§19` 批 4 小轮① 搬的 10 条壳侧断言）**真有区分力**。

做法：逐条把实现**改坏** → 确认**对应的那条断言变红** → 全部复原（**MD5 逐字节校验**）。

⚠️ 若某条变异**没能让断言变红** ⇒ 那条断言是**假绿**（它没钉住它声称钉的东西）⇒ 脚本报错退出。
⚠️ 与 `_mut_m08wired.py` 的两点差别（都是本仓踩过的坑）：
   ① 子进程**必须**设 `ACC_RESULTS_PATH` —— 否则每处变异都会把全套 `artifacts/acc_results.json`
      冲成"单条"，而且是在**改坏的代码**下写的 ⇒ 台账数字全错；
   ② 子进程**必须**设 `PYTHONIOENCODING=utf-8` —— 否则 Windows 上按 GBK 写 stdout，读线程解码崩。
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
from shell_source import SHELL_PATH as SHELL, pick  # noqa: F401  ← `P4`① 读取点收敛
PY = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"
TEST = "tests/test_wired_m03_list.py"

# (说明, 文件, 原文, 改成, 应变红的断言名)
MUTS: list[tuple[str, Path, str, str, str]] = [
    (
        "M1 表头常量改名（表头出口找不到 ⇒ 列数与末列无从谈起）",
        SHELL,
        "const NT_THEAD=`",
        "const NT_THEAD_X=`",
        "test_壳里列表页骨架齐备且表头18列",
    ),
    (
        "M2 单据日期不再标「闭区间」（只读显示的口径丢了）",
        SHELL,
        "对应单据日期（闭区间）",
        "对应单据日期",
        "test_壳里年月走统一时间控件且单据日期是闭区间",
    ),
    (
        "M3 有效行口径退回「只看剔除」（撤单但有牵涉的行会被错误隐藏）",
        SHELL,
        "const ntLive=n=>!n.excl&&(!ntVoid(n)||ntVoidJoint(n));",
        "const ntLive=n=>!n.excl;",
        "test_壳里有效行口径与计数三档",
    ),
    (
        "M4 剔除来源不再分档（「人工批量剔除」与「规则命中」混作一谈）",
        SHELL,
        "exrule: x.exclude_source === 'manual' ? '人工批量剔除' : '规则命中',",
        "exrule: '剔除',",
        "test_壳里剔除来源分档不混作一谈",
    ),
    (
        "M5 排序按**字符串**比较（金额列会排错）",
        SHELL,
        "_cmp(a.v,b.v,tp,st.d)",
        "_cmp(a.v,b.v,'s',st.d)",
        "test_壳里金额列按数值排序而不是按字符串",
    ),
    (
        "M6 空态行的跨列数写死（加列时会错位）",
        SHELL,
        'colspan="${thCount(NT_THEAD)}"',
        'colspan="18"',
        "test_壳里空态行跨列数由表头派生且指出剔除行去哪看",
    ),
    (
        "M7 默认月不由后端给（前端自己算会落到「上月」）",
        SHELL,
        "tmBtn('ntMonth',{scope:'nt',val:fNt.month,",
        "tmBtn('ntMonth',{scope:'nt',val:'',",
        "test_壳里默认月由后端给且付款域默认当月",
    ),
    (
        "M8 勾选框不再由渲染注入（数据与结构混在一起）",
        SHELL,
        'data-act="pick" data-id="${n.id}"',
        'data-act="pickX" data-id="${n.id}"',
        "test_壳里勾选框与标签由渲染注入而不是数据带的",
    ),
    (
        "M9 合计行不再排除剔除行（剔除行会被加进合计）",
        SHELL,
        "const sumRows=list.filter(ntLive);",
        "const sumRows=list;",
        "test_壳里合计行只算非剔除行且无有效行时不给",
    ),
    (
        "M10 项目选择器不再走共用件（本页自己写一份面板）",
        SHELL,
        "${pjOpen?pjPanel():''}",
        "${pjOpen?'':''}",
        "test_壳里项目选择器走共用件且label只一层",
    ),
]


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def run_one(case: str) -> bool:
    """跑单条断言 ⇒ True = 通过，False = 变红。"""
    env = {**os.environ,
           "ACC_RESULTS_PATH": "../artifacts/_mut_acc_results.json",
           "PYTHONIOENCODING": "utf-8",
           "PYTHONDONTWRITEBYTECODE": "1"}
    r = subprocess.run(
        [str(PY), "-m", "pytest", "-q", f"{TEST}::{case}"],
        cwd=str(ROOT / "backend"), capture_output=True, text=True, encoding="utf-8",
        errors="replace", env=env,
    )
    return r.returncode == 0


def main() -> int:
    before = {p: (p.read_bytes(), md5(p)) for p in {m[1] for m in MUTS}}
    hit = 0
    for desc, path, old, new, case in MUTS:
        # ⚠️ 2026-09-19（性能 `P4`② 三刀真拆）：壳已拆成多件（`web/shell/*.js`）⇒ 锚点在哪件就改哪件。
        path = pick(path, old, new)
        before.setdefault(path, (path.read_bytes(), hashlib.md5(path.read_bytes()).hexdigest()))
        t = path.read_text(encoding="utf-8")
        if t.count(old) != 1:
            print(f"  ⛔ {desc} —— 锚点命中 {t.count(old)} 次（期望 1）⇒ **未验证**")
            continue
        path.write_text(t.replace(old, new), encoding="utf-8", newline="\n")
        red = not run_one(case)
        path.write_text(before[path][0].decode("utf-8"), encoding="utf-8", newline="\n")
        print(("  ✅ " if red else "  ⛔ 未命中 ") + desc + f"  → `{case}` " + ("变红" if red else "**仍是绿的**"))
        hit += red

    print()
    ok = all(md5(p) == h for p, (_, h) in before.items())
    print(f"  命中 {hit}/{len(MUTS)}")
    print(f"  复原校验（MD5 逐字节）：{'✅ 全部复原' if ok else '❌ 有文件没复原'}")
    return 0 if (hit == len(MUTS) and ok) else 1


if __name__ == "__main__":
    sys.exit(main())
