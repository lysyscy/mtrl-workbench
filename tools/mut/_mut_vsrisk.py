"""反向灵敏度 —— **㊱ 接管缺口机器眼**（`TAIL-198` · 2026-09-30 立）：证明它**真看得见**。

⚠️ 本件为什么必需：那条机器眼守的是「**带标记的表够阈值却没被接管**」——而它**今天一个都不报**
   （实测：15 屏 22 张带标记的表 · 缺口 **0**）⇒ 「它到底会不会红」**没人知道**。
   本仓的规矩：新做的机制若不证明"改坏了会被抓住"，它跟没做一样（`_mut_vs.py` 文件头原话）。

**两个靶**（各改一处、各自跑一遍 `_shell_smoke.py`；改完**立刻按 bytes 复原** ＋ 收尾 MD5）：

| 靶 | 改哪 | 为什么它等价于"表涨上去了" |
|---|---|---|
| `M1` | `shell/view.js`：`const VSCROLL={};` ⇒ `{'m02':{min:5}}` | 把**那一页**的阈值降到它现有行数之下 ⇒ 那张 `m02` 日志表（50 行 · **没有 `.tw`**）当场"够阈值却接管不了" ✓；⚠️ **只动一页**：全局把 `VS_MIN` 降到地板会让**别的段先崩**（2026-09-30 实测：㊱ 根本跑不到）⇒ 那样测不到本段，⛔ 别用 |
| `M2` | `index.html`（`V.m08` 那张 1374 行的表）：`<div class="tw">` ⇒ `<div class="twx">` | 摘掉**自带滚动容器** ⇒ 那张大表**接管不了** ⇒ 「够阈值却没接管」当场成立（同一个红条件的**另一侧**） |

⚠️ 判据 = **`_shell_smoke.py` rc≠0** ＋ **那句话出现在输出里**（⛔ 别只看 rc：别的段也可能红）。
⚠️ 真机件 ⇒ **独占跑**（别与别的闸门并行）；需要壳在跑（`http://127.0.0.1:8000`）＋ Playwright。

用法：`backend\\.venv\\Scripts\\python.exe -X utf8 tools\\mut\\_mut_vsrisk.py`
"""

from __future__ import annotations

import hashlib
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
PY = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"
SMOKE = ROOT / "tools" / "probe" / "_shell_smoke.py"
VIEW = ROOT / "backend" / "app" / "web" / "shell" / "view.js"
SHELL = ROOT / "backend" / "app" / "web" / "index.html"

#: ⚠️ 机器眼在**红**的时候打的那句话（`_shell_vskeep.check_risk`）—— 判据串认它，⛔ 别只认 rc。
NEEDLE = "却没被接管"

CASES: list[tuple[pathlib.Path, str, bytes, bytes]] = [
    (VIEW, "M1 `m02` 那一页的阈值降到 5（它那张 50 行的日志表没有 `.tw` ⇒ 够阈值却接管不了）",
     b"const VSCROLL={};", b"const VSCROLL={'m02':{min:5}};"),
    (SHELL, "M2 摘掉 `m08` 那张大表的 `.tw`（它 1374 行 ⇒ 够阈值却接管不了）",
     b'<div class="tw">${TBL({head:ivThead(),key:\'m08:invoices\',',
     b'<div class="twx">${TBL({head:ivThead(),key:\'m08:invoices\','),
]


def run_smoke() -> tuple[int, str]:
    r = subprocess.run([str(PY), "-X", "utf8", str(SMOKE)], cwd=str(ROOT), capture_output=True,
                       text=True, encoding="utf-8", errors="replace",
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main() -> int:
    print("基线（未改坏）：")
    rc0, out0 = run_smoke()
    tail = next((l.strip() for l in reversed(out0.splitlines()) if "接管缺口" in l), "")
    print(f"  _shell_smoke.py rc={rc0}  {tail[:70] if tail else ''}")
    if rc0 != 0:
        print("  ⛔ 基线就红 ⇒ 先清红再来跑本件")
        return 1

    before = {p: p.read_bytes() for p, _d, _o, _n in CASES}
    hit = 0
    for target, desc, old, new in CASES:
        src = target.read_bytes()
        n = src.count(old)
        if n != 1:
            print(f"  ⛔ {desc} —— 靶串命中 {n} 次（期望 1）⇒ **未验证**")
            continue
        try:
            target.write_bytes(src.replace(old, new))
            rc, out = run_smoke()
        finally:
            target.write_bytes(src)                     # ⭐ 立刻复原
        gaps = [l.strip() for l in out.splitlines()
                if ("却没被接管" in l) or ("够阈值却没接管" in l)]
        ok = rc != 0 and any(NEEDLE in l for l in gaps)
        print(("  ✅ " if ok else "  ⛔ 未命中 ") + desc + f"  → rc={rc}"
              + ("" if ok else "（判据「" + NEEDLE + "」没出现在输出里）"))
        for g in gaps[:2]:
            print("        " + g[:150])
        hit += ok

    dirty = [p for p, b in before.items()
             if hashlib.md5(p.read_bytes()).hexdigest() != hashlib.md5(b).hexdigest()]
    print()
    print(f"  命中 {hit}/{len(CASES)}")
    print(f"  复原校验（MD5 逐字节）：{'✅ 全部复原' if not dirty else '❌ 未复原：' + '、'.join(map(str, dirty))}")
    return 0 if (hit == len(CASES) and not dirty) else 1


if __name__ == "__main__":
    sys.exit(main())
