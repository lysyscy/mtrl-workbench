"""反向灵敏度（`TBL` 表格件 —— `TAIL-64` 的**统一表外壳**）—— 证明那两条结构性判据**真有区分力**。

⚠️ 本件为什么必需：
- `TAIL-64` P0（2026-09-24）把「表外壳」抽进 `TBL` 之后，一批**钉源码形态**的判据当场假红
  （实测：`ACC-FEE-MON-001/001-01`）⇒ 判据被改成**结构无关**的两段式：
  **切片委托 `TBL`** ＋ **内核里真做了那件事**（`shell_src.with_tbl()` 把两段拼起来看）。
- ⚠️ 但 P0 **没为这套新判据补反向灵敏度**（表 A 里查不到 `_mut_tbl*`）⇒ "改坏了会不会红"**没人证过**；
  本件补上（随 `TAIL-64` P1b 一起做）。

两靶（都打**壳** `index.html`，改完**立刻按 bytes 复原** ＋ MD5 校验）：
- `M1` **去掉委托**：把 `m15` 切片里的 `TBL({head:'<th>登录账号</th>…` 改成 `TBLBROKEN({…`
  （合法标识符 ⇒ **不触发**语法错，只会让"本页主表没走统一出口"那一条红）。
- `M2` **掏空内核**：把 `TBL` 体内的 `+rows.join('')+` 改成 `+''+` ⇒ "内核没把 rows 拼进 tbody"必须红。

⚠️ 判据 = **目标测试件 rc≠0**（不是整支尺子）＋ **那条断言的原话出现在输出里**（⛔ 别只看 rc：别的用例红
也会让 rc≠0）。
⚠️ 子集 pytest **必须**把 `ACC_RESULTS_PATH` 指到 `artifacts/_mut_acc_results.json`（`MEMORY-细则 §十七`）
—— ⛔ 否则把**权威四态**冲成残档、`T4` 报红；⚠️ 本件跑完**必须重跑全套**写回（脚本末尾会提醒）。

用法：python tools/mut/_mut_tbl.py
"""

from __future__ import annotations

import hashlib
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SHELL = ROOT / "backend" / "app" / "web" / "index.html"
PY = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"
TARGET = "tests/test_acc_usr_mgmt.py"          #: 承载那两条判据的测试件
PARTIAL_ACC = ROOT / "artifacts" / "_mut_acc_results.json"

def _b(s: str) -> bytes:
    """⚠️ `bytes` 字面量**只能放 ASCII** ⇒ 含中文的靶串必须这样编（踩过：`SyntaxError`）。"""
    return s.encode("utf-8")


#: `(说明, 原文, 改坏成, 期望在输出里出现的断言原话)` —— 靶串都是**单行片段** ⇒ 不必做行尾归一
CASES: list[tuple[str, bytes, bytes, str]] = [
    ("M1 去掉委托（`m15` 主表不再走 `TBL`）", _b("TBL({head:'<th>登录账号</th>"),
     _b("TBLBROKEN({head:'<th>登录账号</th>"), "本页主表没走统一出口"),
    ("M2 掏空内核（`TBL` 不再把 rows 拼进 tbody）", _b("+rows.join('')+"), _b("+''+"),
     "内核没有把 rows 拼进 `tbody`"),
]


def run_target() -> tuple[int, str]:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1",
           # ⚠️ 子集跑 ⇒ 四态落**残档**（⛔ 别写权威档 `acc_results.json`）
           "ACC_RESULTS_PATH": str(PARTIAL_ACC)}
    r = subprocess.run([str(PY), "-m", "pytest", "-q", TARGET, "-p", "no:cacheprovider",
                        "--tb=line"], cwd=str(ROOT / "backend"), capture_output=True,
                       text=True, encoding="utf-8", errors="replace", env=env)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main() -> int:
    src = SHELL.read_bytes()
    md5_before = hashlib.md5(src).hexdigest()

    rc0, out0 = run_target()
    print(f"基线（未改坏）{TARGET} rc={rc0}（应为 0）")
    if rc0 != 0:
        print("  ⛔ 基线就红 ⇒ 先清红再来跑本件")
        return 1

    hit = 0
    for desc, old, new, needle in CASES:
        if src.count(old) != 1:
            print(f"  ⛔ {desc} —— 靶串命中 {src.count(old)} 次（期望 1）⇒ **未验证**")
            continue
        try:
            SHELL.write_bytes(src.replace(old, new, 1))
            rc, out = run_target()
        finally:
            SHELL.write_bytes(src)                     # ⭐ 立刻按原 bytes 复原
        ok = rc != 0 and needle in out
        print(("  ✅ " if ok else "  ⛔ 未命中 ") + desc + f"  → rc={rc}"
              + ("" if ok else f"（判据「{needle}」没出现在输出里）"))
        hit += ok

    ok_md5 = hashlib.md5(SHELL.read_bytes()).hexdigest() == md5_before
    print()
    print(f"  命中 {hit}/{len(CASES)}")
    print(f"  复原校验（MD5 逐字节）：{'✅ 复原' if ok_md5 else '❌ 未复原'}")
    print("⚠️ 本件只跑了目标件 ⇒ **接着必须重跑全套 pytest 写回权威四态**（否则报表掉绿）。")
    return 0 if (hit == len(CASES) and ok_md5) else 1


if __name__ == "__main__":
    sys.exit(main())
