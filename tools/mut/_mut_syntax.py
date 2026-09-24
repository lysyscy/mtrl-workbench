"""反向灵敏度（`syntax_audit` —— 「能编译吗 / 能解析吗 / 壳目录干净吗」）—— 证明它**真有区分力**。

⚠️ 本件为什么必需：`syntax_audit.py` **自带** `--selftest`（在临时目录里造样本 ⇒ `Q1`/`Q2`/`Q3` 各证明一次），
   但**没有任何地方跑它** —— 收工闸门跑的是 `syntax_audit.py`（**不带参数**）⇒ 那份自证是**休眠的**
   （写了、当时能过、此后**没人会碰它** ⇒ 尺子腐化了也没人知道）—— ⭐ "有一次证明过" ≠ "有守卫"。
   本件把两件事一起做：① 把那份休眠自检**叫醒**（`M4`）② 在**活树**上各改坏一处 ——
   内建自检用的是**临时样本**，它证明不了"**真仓里的文件**确实被这把尺子看得见"。

四靶（每处改完**立刻按 bytes 复原** ＋ 收尾 MD5 校验）：
- `M1` `Q1`：在 `tools/` 下新建一个**语法错**的 `.py` ⇒ 必须红（用完删掉；⚠️ 名字**故意不带** `_mut_`，
  免得被「变异件清单」当成常驻件统计）。
- `M2` `Q2`：把壳的**最小一件**（`web/shell/print-export.js`）追加一段过不了 `node --check` 的内容 ⇒ 必须红。
  ⚠️ **动过壳件** ⇒ 本轮收尾必须多走一步 `shell_verify.py --snapshot` 盖章（`MEMORY.md §〇之二`）。
- `M3` `Q3`：在 `backend/app/web/shell/` 下放一个 `*.bak-sync` 散件 ⇒ 必须红（用完删掉）。
- `M4` 内建 `--selftest`（临时样本那三条证明）⇒ 必须 `rc=0`（⚠️ 没有 `node` 时它会自报"无法自证" ⇒ 本件判失败，
  那是**对的** —— ⛔ 别把它当通过）。

用法：python tools/mut/_mut_syntax.py
"""

from __future__ import annotations

import hashlib
import os
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
RULER = ROOT / "tools" / "audit" / "syntax_audit.py"
PY = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"

Q1_TMP = ROOT / "tools" / "_tmp_q1_broken.py"           #: ⚠️ 用完删；名字不带 `_mut_`
Q2_TARGET = ROOT / "backend" / "app" / "web" / "shell" / "print-export.js"   #: 壳件里最小的一件
Q3_TMP = ROOT / "backend" / "app" / "web" / "shell" / "_tmp_stray.js.bak-sync"


def _env() -> dict[str, str]:
    return {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}


def run_ruler(*extra: str) -> tuple[int, str, int]:
    """→ (`必须修 N`, 输出, rc)。⚠️ `N` 解析不到 ⇒ `-1`（子进程没起来 ⇒ 每处"看起来变红" = 全假红）。

    ⚠️ `--selftest` 模式**不打**「必须修」那一行（它打的是「自检结论」）⇒ 那条靶**只能看 rc**。
    """
    r = subprocess.run([str(PY), str(RULER), *extra], cwd=str(ROOT), capture_output=True,
                       text=True, encoding="utf-8", errors="replace", env=_env())
    out = (r.stdout or "") + (r.stderr or "")
    m = re.search(r"必须修 (\d+)", out)
    return (int(m.group(1)) if m else -1), out, r.returncode


def main() -> int:
    base_n, base_out, _ = run_ruler()
    print(f"基线（未改坏）syntax_audit 必须修 {base_n}（应为 0）")
    if base_n != 0:
        print("  ⛔ 基线就不干净 ⇒ 先清红再来跑本件")
        return 1

    hits = 0
    total = 4

    # ---- M1 `Q1`：新造一个编译不过的 `.py` ----
    Q1_TMP.write_text('X = f"说"话"\n', encoding="utf-8")
    try:
        n, out, _ = run_ruler()
    finally:
        Q1_TMP.unlink(missing_ok=True)
    ok = n > 0 and Q1_TMP.name in out
    hits += ok
    print(f"  {'✅' if ok else '⛔ 未命中'} M1 `Q1` 造一个语法错的 `.py` ⇒ 必须修 {n}（应含 {Q1_TMP.name}）")

    # ---- M2 `Q2`：壳件追加一段 node 解析不了的内容 ----
    before = Q2_TARGET.read_bytes()
    try:
        Q2_TARGET.write_bytes(before + b"\nconst _tmp_broken = ;\n")
        n, out, _ = run_ruler()
    finally:
        Q2_TARGET.write_bytes(before)
    ok = n > 0 and f"{Q2_TARGET.name} 过不了" in out
    hits += ok
    print(f"  {'✅' if ok else '⛔ 未命中'} M2 `Q2` 壳件追加语法错 ⇒ 必须修 {n}（应含「{Q2_TARGET.name} 过不了」）")

    # ---- M3 `Q3`：壳目录放一个备份散件 ----
    Q3_TMP.write_text("// 临时散件（本件用完即删）\n", encoding="utf-8")
    try:
        n, out, _ = run_ruler()
    finally:
        Q3_TMP.unlink(missing_ok=True)
    ok = n > 0 and Q3_TMP.name in out
    hits += ok
    print(f"  {'✅' if ok else '⛔ 未命中'} M3 `Q3` 壳目录放 `*.bak-sync` ⇒ 必须修 {n}（应含 {Q3_TMP.name}）")

    # ---- M4：把**休眠的内建自检**叫醒（⚠️ 它不打「必须修」那一行 ⇒ 这条**只看 rc**）----
    _n, out, rc = run_ruler("--selftest")
    ok = rc == 0 and "三条规则都能区分" in out
    hits += ok
    print(f"  {'✅' if ok else '⛔ 未命中'} M4 内建 `--selftest` ⇒ 三条规则各证明一次"
          f"（rc={rc}，应为 0；⚠️ 无 node 时它会自报『无法自证』⇒ 本件判失败，那是对的）")

    # ---- 复原校验：两个临时件必须**不存在** ----
    leftovers = [p for p in (Q1_TMP, Q3_TMP) if p.exists()]
    shell_ok = hashlib.md5(Q2_TARGET.read_bytes()).hexdigest() == \
        hashlib.md5(before).hexdigest()
    print()
    print(f"  临时件残留：{'❌ ' + str(leftovers) if leftovers else '✅ 无'}"
          f" · 壳件逐字节复原：{'✅' if shell_ok else '❌'}")
    print(f"  反向灵敏度：**{hits}/{total} 命中**")
    return 0 if (hits == total and not leftovers and shell_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
