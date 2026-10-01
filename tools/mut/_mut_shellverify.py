"""反向灵敏度（**盖章式闸门** `tools/audit/shell_verify.py`）—— 证明它**真有牙**。

做法：把壳**故意改坏**三种残留形态（**加行 / 改行 / 删行**）⇒ 每一条都必须让 `shell_verify` **rc=1**
⇒ 立刻**逐字节复原**（MD5 校验）⇒ 复原后必须回到 `rc=0`。

⚠️ 为什么值得单立一条：2026-09-19 实测过「`_mut_*` 脚本中断 ⇒ `shell/core.js` 里**多**了两行变异态」，
   而当时**全套 pytest 与其它尺子全绿** —— **只有它（和真机探针）看得见**这种"多出来/少一行"的坏。
   它此前**两条出口都 `return 0`**（僵尸闸门 · 2026-09-24 修）⇒ 本件就是修完后的**自证**：
   **一条都不红 = 它又瞎了**（"没红 ≠ 没坏"）。

用法：python tools/mut/_mut_shellverify.py
"""

from __future__ import annotations

import hashlib
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
PY = str(ROOT / "backend" / ".venv" / "Scripts" / "python.exe")
TOOL = str(ROOT / "tools" / "audit" / "shell_verify.py")
TARGET = ROOT / "backend" / "app" / "web" / "shell" / "core.js"
BACKUPS = ROOT / ".codebuddy" / "backups"

#: 变异标记（写进去的那一行必须**明显不是真代码**，便于人肉辨认）
MARK = "  /* ⚠️ 变异残留：MUT */"

CASES = ["加行", "改行", "删行"]


def run_tool() -> int:
    p = subprocess.run([PY, TOOL], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    return p.returncode


def lines_of(text: str) -> list[str]:
    return text.split("\n")


def pick_index(lines: list[str], nth: int) -> int:
    """第 `nth` 个**非空行**的下标（⚠️ 必须非空：`shell_verify._lines()` 会滤掉空行，删空行 = 差 0 = 假绿）。"""
    seen = 0
    for i, l in enumerate(lines):
        if l.strip():
            seen += 1
            if seen == nth:
                return i
    raise RuntimeError(f"文件里没有第 {nth} 个非空行")


def main() -> int:
    if not TARGET.exists():
        print(f"  ⛔ 靶不存在：{TARGET}")
        return 1
    if not sorted(BACKUPS.glob("*_壳单文件基线.html")):
        print("  ⛔ 没有基线快照 ⇒ `shell_verify` 会判红（'无基准'）⇒ 本件无法自证。")
        print("     ⇒ 先复核壳（真机整支 rc=0）再跑 `python tools/audit/shell_verify.py --snapshot`")
        return 1

    raw = TARGET.read_bytes()
    md5_before = hashlib.md5(raw).hexdigest()
    rc0 = run_tool()
    print(f"  基线：shell_verify rc={rc0}（期望 0）")
    if rc0 != 0:
        print("  ⛔ 基线不是 0 ⇒ 壳现在就有漂移（先把壳弄干净 / 盖章）⇒ 停手")
        return 1

    hits = 0
    for name in CASES:
        text = TARGET.read_text(encoding="utf-8")
        lines = lines_of(text)
        i = pick_index(lines, 40)                     # 取第 40 个非空行当靶（位置稳定、不依赖字面锚点）
        if name == "加行":
            lines.insert(i + 1, MARK)
        elif name == "改行":
            lines[i] = lines[i] + MARK
        else:                                          # 删行
            del lines[i]
        TARGET.write_text("\n".join(lines), encoding="utf-8", newline="")
        rc = run_tool()
        TARGET.write_bytes(raw)                        # ⭐ 立刻复原（⛔ 别等循环结束）
        found = rc == 1
        hits += 1 if found else 0
        print(f"  {'✅' if found else '❌'} {name} ⇒ shell_verify rc={rc}（期望 1）"
              f"{'' if found else ' —— ⛔ 闸门没抓到，等于又瞎了'}")

    ok = hashlib.md5(TARGET.read_bytes()).hexdigest() == md5_before
    rc_end = run_tool()
    print(f"\n  复原校验（MD5 逐字节）：{'✅ 一致' if ok else '❌ 不一致'}")
    print(f"  复原后 shell_verify rc={rc_end}（期望 0）")
    print(f"  反向灵敏度：**{hits}/{len(CASES)} 命中**")
    return 0 if (hits == len(CASES) and ok and rc_end == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
