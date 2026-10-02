"""反向灵敏度 —— **㊲ `m11` 打开不卡**（`TAIL-214` · 2026-10-02 立）：证明它**真看得见**「偏移退化回按行量」。

⚠️ 本件为什么必需：㊲ 守的是**几何读的次数**，而它两次量测的**结果数**（4 次）**一样** ——
   "它到底会不会红"只看绿是**看不出来**的。本仓的规矩：新机制若不证明"改坏了会被抓住"，它跟没做一样
   （`_mut_vs.py` 文件头原话）。

**两个靶**（各改一处、各自跑一遍 `_shell_smoke.py`；改完**立刻按 bytes 复原** ＋ 收尾 MD5）：

| 靶 | 改哪 | 为什么它等价于"又变成按行量了" |
|---|---|---|
| `M1` | `shell/actions.js`：`put()` 里 `OFF[i]` ⇒ 改回 `off(i)`（即**把量偏移塞回行循环里**） | 这就是 `TAIL-214` 修之前**原样式** ⇒「读几何 ↔ 写样式」交替 ⇒ 每行 3 次 ✓ |
| `M2` | 同一行再塞一个 `el.offsetWidth * 0`（**值不变**、屏幕上一模一样） | ⭐ 专打"**只数 `getBoundingClientRect`**"那条窄口径：它走的是 `offsetWidth`（**同样**强制同步布局）⇒ 计数器若没扩面就**瞎**（2026-10-02 实测：扩面前这条是绿的） |

⚠️ `M2` 的重点：**它不改任何可见结果**（`offsetWidth * 0` ＝ 0 ⇒ 偏移值逐字不变、`㉝` 钉列几何照样绿）
   ⇒「看得见的都对」而**只有 ㊲ 看见代价** —— 这正是这条判据存在的理由。
⚠️ 判据 = **`_shell_smoke.py` rc≠0** ＋ **那句话出现在输出里**（⛔ 别只看 rc：别的段也可能红）。
⚠️ 真机件 ⇒ **独占跑**（别与别的闸门并行）；需要壳在跑（`http://127.0.0.1:8000`）＋ Playwright。

用法：`backend\\.venv\\Scripts\\python.exe -X utf8 tools\\mut\\_mut_m11cost.py`
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
ACTIONS = ROOT / "backend" / "app" / "web" / "shell" / "actions.js"

#: ⚠️ 判据在**红**的时候打的那两句（`_shell_m11cost.check`）—— 判据串认它们，⛔ 别只认 rc。
NEEDLES = ("几何读次数", "随行数增长")

#: `put()` 里那一行（修复后的形态）—— 它是 `M1`/`M2` 的锚点。
ANCHOR = b"el.classList.add('fl'); el.style.left=OFF[i]+'px';"

CASES: list[tuple[bytes, bytes, str]] = [
    (ANCHOR,
     b"el.classList.add('fl'); el.style.left=off(i)+'px';",
     "M1 把量偏移塞回行循环（`OFF[i]` ⇒ `off(i)`）＝ `TAIL-214` 修之前的原样式"),
    (ANCHOR,
     b"el.classList.add('fl'); el.style.left=(OFF[i]+el.offsetWidth*0)+'px';",
     "M2 值不变、屏上一模一样，只**多读一次 `offsetWidth`**（专打\"只认 getBoundingClientRect\"那条窄口径）"),
]


def run_smoke() -> tuple[int, str]:
    r = subprocess.run([str(PY), "-X", "utf8", str(SMOKE)], cwd=str(ROOT), capture_output=True,
                       text=True, encoding="utf-8", errors="replace",
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main() -> int:
    print("基线（未改坏）：")
    rc0, out0 = run_smoke()
    line = next((l.strip() for l in out0.splitlines() if "每多一行只多读" in l), "")
    print(f"  _shell_smoke.py rc={rc0}  {line[:80]}")
    if rc0 != 0:
        print("  ⛔ 基线就红 ⇒ 先清红再来跑本件")
        return 1

    before = ACTIONS.read_bytes()
    hit = 0
    for old, new, desc in CASES:
        n = before.count(old)
        if n != 1:
            print(f"  ⛔ {desc} —— 锚点命中 {n} 次（期望 1）⇒ **未验证**（仓里那一行被改过？）")
            continue
        try:
            ACTIONS.write_bytes(before.replace(old, new))
            rc, out = run_smoke()
        finally:
            ACTIONS.write_bytes(before)                    # ⭐ 立刻复原
        hits = [l.strip() for l in out.splitlines() if all(k in l for k in NEEDLES)]
        ok = rc != 0 and bool(hits)
        print(("  ✅ " if ok else "  ⛔ 未命中 ") + desc + f"  → rc={rc}"
              + ("" if ok else "（判据「" + NEEDLES[1] + "」没出现在输出里）"))
        for h in hits[:1]:
            print("        " + h[:150])
        hit += ok

    dirty = (hashlib.md5(ACTIONS.read_bytes()).hexdigest()
             != hashlib.md5(before).hexdigest())
    print()
    print(f"  命中 {hit}/{len(CASES)}")
    print(f"  复原校验（MD5 逐字节）：{'✅ 已复原' if not dirty else '❌ 未复原'}")
    return 0 if (hit == len(CASES) and not dirty) else 1


if __name__ == "__main__":
    sys.exit(main())
