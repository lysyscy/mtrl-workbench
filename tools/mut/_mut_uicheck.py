"""反向灵敏度（**交付面四检**：`_smoke` / `_doccheck` / `_links` / `_ids`）—— 证明它们**真有区分力**。

⚠️ 四检是**交付面**（`D:\\工作\\AI\\PRD编写夹 - Workbuddy专用\\demo\\*.js`）里的 node 自检，
   由 `doc_audit --ui` 代跑（`MEMORY.md §〇之二` ⭐ "最易漏！"）。此前**从没被证明过"改坏了会不会红"**。

四靶（**一次只碰一个文件**，改完**立刻按 bytes 复原** ＋ 收尾 MD5；用户 2026-09-24：
「云同步也没那么蠢，只要别同时大量连续改文件」）：
- `M1` `_smoke`：原型 html 里把 `CHG` 的 `'plRowSet'` 改名 ⇒ 断言
  `N6｜凡渲染成表单元素的动作都必须在 CHG 里` **必须红**（change 会被静默丢弃）。
- `M2` `_doccheck`：`.md` 追加一句**错的计数**（「可复用设计规则 99 条」）⇒ 计数类事实必须红。
- `M3` `_links`：同一件追加一处**不存在的路径引用** ⇒ 断链必须红。
- `M4` `_ids`：同一件追加 `DEV-R-99`（**全库无定义**）⇒ 悬空编号必须红。

⚠️ `M2`–`M4` 三个靶**共用同一份 md**（`demo/原型导读.md`）—— 刻意减少"同时碰多个交付面文件"。
⛔ **不在交付面新建文件**（WPS 云同步树 + 与 `MEMORY.md §八` 的纪律一致）：只**追加一行**、立刻复原。

用法：python tools/mut/_mut_uicheck.py
"""

from __future__ import annotations

import hashlib
import os
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
PY = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"

sys.path.insert(0, str(ROOT / "tools" / "audit"))
from audit_common import delivery_root  # noqa: E402

DEMO = delivery_root() / "demo"
PROTO = DEMO / "材料报表自动化工作台-交互原型.html"     #: `_smoke` 的靶
DOC = DEMO / "原型导读.md"                              #: `_doccheck`/`_links`/`_ids` 的靶（在它们的 FILES/扫描面内）
#: ⚠️ 四检里 `_smoke` 只吃原型；另三件扫整个交付面 ⇒ 往**同一份 md** 追加一行即可分别打中后两件

NODE_FALLBACK = r"C:\Users\Administrator\.workbuddy\binaries\node\versions\22.22.2-3\node.exe"


def node_exe() -> str:
    return shutil.which("node") or NODE_FALLBACK


def run_check(script: str) -> tuple[int, str]:
    r = subprocess.run([node_exe(), str(DEMO / script)], cwd=str(DEMO), capture_output=True,
                       text=True, encoding="utf-8", errors="replace",
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def tail_line(out: str) -> str:
    return next((l.strip() for l in reversed(out.splitlines()) if "=====" in l), "")[:60]


CHECKS = ("_smoke.js", "_doccheck.js", "_links.js", "_ids.js")


def main() -> int:
    print("基线（未改坏）四检：")
    base: dict[str, tuple[int, str]] = {}
    for s in CHECKS:
        rc, out = run_check(s)
        base[s] = (rc, out)
        print(f"  {s:<14} rc={rc}  {tail_line(out)}")
    bad = [s for s, (rc, _) in base.items() if rc != 0]
    if bad:
        print(f"  ⛔ 基线就有红的：{'、'.join(bad)} ⇒ 先清红再来跑本件")
        return 1

    cases = [
        # (说明, 靶件, 改坏方式, 要跑的检查, 判据串)
        ("M1 `_smoke`：`CHG` 少登记一个**表单元素动作**（change 会被静默丢弃）", PROTO,
         ("replace", b"'plRowSet'", b"'plRowSet_MUT'"), "_smoke.js", ("plRowSet", "CHG")),
        ("M2 `_doccheck`：文档里写**错的计数**（设计规则条数 ≠ 主人实时值）", DOC,
         ("append", "\n\n（变异靶：可复用设计规则 99 条）\n", None), "_doccheck.js", ("设计规则条数",)),
        ("M3 `_links`：文档里出现**不存在的路径引用**（断链）", DOC,
         ("append", "\n\n（变异靶：见 `demo/变异靶-不存在.md`。）\n", None), "_links.js",
         ("变异靶-不存在.md",)),
        ("M4 `_ids`：文档里出现**全库无定义的编号**（悬空号）", DOC,
         ("append", "\n\n（变异靶：引用 `DEV-R-99`。）\n", None), "_ids.js", ("DEV-R-99",)),
    ]

    before: dict[pathlib.Path, bytes] = {}
    for _, target, _, _, _ in cases:
        before.setdefault(target, target.read_bytes())

    hit = 0
    for desc, target, how, script, needle in cases:
        src = target.read_bytes()
        try:
            if how[0] == "replace":
                n = src.count(how[1])
                if n != 1:
                    print(f"  ⛔ {desc} —— 靶串命中 {n} 次（期望 1）⇒ **未验证**")
                    continue
                target.write_bytes(src.replace(how[1], how[2]))
            else:
                target.write_bytes(src + how[1].encode("utf-8"))
            rc, out = run_check(script)
        finally:
            target.write_bytes(src)                     # ⭐ 立刻复原（交付面文件，绝不留在坏态）
        ok = rc != 0 and all(x in out for x in needle)
        print(("  ✅ " if ok else "  ⛔ 未命中 ") + desc +
              f"  → {script} rc={rc}" + ("" if ok else f"（判据 {needle} 未全中）"))
        hit += ok

    dirty = [p for p, b in before.items() if hashlib.md5(p.read_bytes()).hexdigest()
             != hashlib.md5(b).hexdigest()]
    print()
    print(f"  命中 {hit}/{len(cases)}")
    print(f"  复原校验（MD5 逐字节）：{'✅ 全部复原' if not dirty else '❌ 未复原：' + '、'.join(map(str, dirty))}")
    return 0 if (hit == len(cases) and not dirty) else 1


if __name__ == "__main__":
    sys.exit(main())
