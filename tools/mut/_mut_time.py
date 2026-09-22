"""**反向灵敏度**：证明 `tests/test_acc_i8_time.py::test_壳的业务时钟取自北京时间而非写死`
（⭐ `TAIL-51` · 壳的业务时钟接真）**真有区分力**。

做法：逐条把实现**改坏** → 确认**对应的那条断言变红** → 全部复原（**MD5 逐字节校验**）。
⚠️ 若某条变异**没能让断言变红** ⇒ 那条断言是**假绿** ⇒ 脚本报错退出。

⚠️ 一律走 **bytes**：还原用**原 bytes**（用 `write_text(newline=…)` 会把 CRLF 静默换成 LF ⇒ MD5 假 BAD）。
⚠️ 子进程必须设 `ACC_RESULTS_PATH`（否则每处变异把权威 `acc_results.json` 冲成单条）
   与 `PYTHONIOENCODING=utf-8`（否则 Windows 上 GBK 解码假红）。
⚠️ 跑完**必须再跑一次全套 pytest** 把权威结果写回（见 `MEMORY.md` §十七「本机环境坑」那条）。

⭐ 与 `_mut_boot.py` 的一处**改进**：锚点**同时**试「原样 LF」与「按目标文件行尾归一」两种形态，
   取唯一命中的那一种 —— 本仓 `index.html` 出现过**混行尾**（手写块 LF、`git checkout` 出来的块 CRLF），
   只试一种会报「命中 0」，而那个报错**看起来像锚点写错了**（其实只是行尾）。
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BE = ROOT / "backend"
sys.path.insert(0, str(ROOT / "tools"))
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "audit"))  # ⭐ `TAIL-58` 分目录：shell_source 在 audit/
from shell_source import SHELL_PATH as SHELL, pick  # noqa: E402  ← `P4`① 读取点收敛
PY = BE / ".venv" / "Scripts" / "python.exe"
TEST = "tests/test_acc_i8_time.py"
CASE = "test_壳的业务时钟取自北京时间而非写死"


def _b(s: str) -> bytes:
    """把源码片段编成 **LF** bytes（脚本里一律按 LF 写片段）。"""
    return s.replace("\r\n", "\n").encode("utf-8")


def _fit(fragment: bytes, sample: bytes) -> bytes:
    """把 LF 片段转成**与目标文件一致**的行尾（目标含 CRLF ⇒ 转 CRLF，否则原样）。"""
    if b"\r\n" in sample:
        return fragment.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    return fragment.replace(b"\r\n", b"\n")


# (说明, 文件, 原文（LF）, 改成（LF）, 断言 ①②③④ 里的哪一条负责抓它)
MUTS: list[tuple[str, Path, bytes, bytes, str]] = [
    (
        "M1 ① `SYS_YM` 又写死成固定月（= `TAIL-51` 的原样复发；一过月默认年月指到空月份）",
        SHELL,
        _b("const SYS_YM = _BJ_NOW.year + '-' + _BJ_NOW.month;\n"),
        _b("const SYS_YM = '2026-09';\n"),
        "① 初值不得是日期字面量",
    ),
    (
        "M2 ① `SYS_TODAY` 又写死成固定日（付款窗口判定会永远停在 9 月）",
        SHELL,
        _b("let SYS_TODAY = SYS_YM + '-' + _BJ_NOW.day;\n"),
        _b("let SYS_TODAY = '2026-09-12';\n"),
        "① 初值不得是日期字面量",
    ),
    (
        "M3 ② 时区从北京时间换成 UTC（默认年月会比中国时间早 8 小时 ⇒ 月初/月末各错一天）",
        SHELL,
        _b("{timeZone:'Asia/Shanghai',\n"),
        _b("{timeZone:'UTC',\n"),
        "② 取值来源必须是北京时间",
    ),
    (
        "M4 ③ 兜底路径退到**本机时区**（口径要的是北京时间，不是「这台机的时间」）",
        SHELL,
        _b("  const t = new Date(Date.now() + 8*3600*1000);\n"
           "  return { year:String(t.getUTCFullYear()),\n"
           "           month:String(t.getUTCMonth()+1).padStart(2,'0'),\n"
           "           day:String(t.getUTCDate()).padStart(2,'0') };\n"),
        _b("  const t = new Date();\n"
           "  return { year:String(t.getFullYear()),\n"
           "           month:String(t.getMonth()+1).padStart(2,'0'),\n"
           "           day:String(t.getDate()).padStart(2,'0') };\n"),
        "③ 兜底必须按 UTC + 固定 +8 小时",
    ),
    (
        "M5 ③ 兜底的 +8 小时偏移被抹掉（退化成 UTC ⇒ 又是早 8 小时）",
        SHELL,
        _b("new Date(Date.now() + 8*3600*1000);"),
        _b("new Date(Date.now());"),
        "③ 兜底必须按 UTC + 固定 +8 小时",
    ),
    (
        "M6 ④ 唯一出口 `bjMonth` 的默认偏移被改（全站默认年月整体挪一个月）",
        SHELL,
        _b("const bjMonth = (off=0)=>{"),
        _b("const bjMonth = (off=1)=>{"),
        "④ `bjMonth` 形态未变",
    ),
    (
        "M7 ④ 出口不再从 `SYS_YM` 拆（时钟符号与出口脱钩 ⇒ 改时钟不再影响任何页）",
        SHELL,
        _b("SYS_YM.split('-')"),
        _b("SYS_TODAY.split('-')"),
        "④ 出口仍从 `SYS_YM` 拆",
    ),
]


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def run_one() -> bool:
    env = {**os.environ,
           "ACC_RESULTS_PATH": "../artifacts/_mut_acc_results.json",
           "PYTHONIOENCODING": "utf-8",
           "PYTHONDONTWRITEBYTECODE": "1"}
    r = subprocess.run(
        [str(PY), "-m", "pytest", "-q", f"{TEST}::{CASE}"],
        cwd=str(BE), capture_output=True, text=True, encoding="utf-8",
        errors="replace", env=env,
    )
    return r.returncode == 0


def _locate(src: bytes, frag_lf: bytes) -> tuple[int, bytes] | None:
    """返回 (命中次数, 目标形态)；原样 LF 与「按文件行尾归一」各试一次，取唯一命中的那种。"""
    for cand in (frag_lf, _fit(frag_lf, src)):
        n = src.count(cand)
        if n == 1:
            return n, cand
        if n > 1:
            return n, cand
    return None


def main() -> int:
    before = {p: (p.read_bytes(), md5(p)) for p in {m[1] for m in MUTS}}
    hit = 0
    for desc, path, old_lf, new_lf, which in MUTS:
        # ⚠️ `pick()` 按**子串**在某一件里找锚点，而多行锚点跨不过行尾差异（CRLF 件里找不到 LF 片段）
        #    ⇒ 优先用**首行**当锚点（都是单行、在文件里唯一），多行片段再兜底。
        first = old_lf.decode("utf-8").strip().split("\n")[0].strip()
        path = pick(path, first, old_lf.decode("utf-8"), new_lf.decode("utf-8"))
        before.setdefault(path, (path.read_bytes(), md5(path)))
        src = path.read_bytes()
        found = _locate(src, old_lf)
        if found is None or found[0] != 1:
            n = 0 if found is None else found[0]
            print(f"  ⛔ {desc} —— 锚点命中 {n} 次（期望 1）⇒ **未验证**")
            continue
        old = found[1]
        # 新片段按**命中形态**的行尾归一（否则替换进去的行尾与文件不一致）
        if old != old_lf:
            new = _fit(new_lf, src)
        else:
            new = new_lf
        path.write_bytes(src.replace(old, new, 1))
        red = not run_one()
        path.write_bytes(src)                      # 逐条按原 bytes 还原
        print(("  ✅ " if red else "  ⛔ 未命中 ") + desc
              + f"  → 抓它的断言：{which} " + ("变红" if red else "**仍是绿的**"))
        hit += red

    print()
    ok = all(md5(p) == h for p, (_, h) in before.items())
    print(f"  命中 {hit}/{len(MUTS)}")
    print(f"  复原校验（MD5 逐字节）：{'✅ 全部复原' if ok else '❌ 有文件没复原'}")
    return 0 if (hit == len(MUTS) and ok) else 1


if __name__ == "__main__":
    sys.exit(main())
