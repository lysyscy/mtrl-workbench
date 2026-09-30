"""反向灵敏度（**交付面四检**：`_smoke` / `_doccheck` / `_links` / `_ids`）—— 证明它们**真有区分力**。

⚠️ 四检是**交付面**（`D:\\工作\\AI\\PRD编写夹 - Workbuddy专用\\demo\\*.js`）里的 node 自检，
   由 `doc_audit --ui` 代跑（`MEMORY.md §〇之二` ⭐ "最易漏！"）。此前**从没被证明过"改坏了会不会红"**。

五靶（**一次只碰一个文件**，改完**立刻按 bytes 复原** ＋ 收尾 MD5；用户 2026-09-24：
「云同步也没那么蠢，只要别同时大量连续改文件」）：
- `M1` `_smoke`：在 `_smoke.js` 的 `__X` **导出**里把 `CHG` 加回来 ⇒ `N6′｜表单类动作**不再需要登记**`
  （`#2` 2026-09-26：原型里**没有** `CHG` 名单）**必须红**。
  ⚠️⚠️ **本靶 2026-09-30 修过一次（而且是"方向修反"的那种）**：它原先往**原型**里插一句 `const CHG=[];`
  ⇒ 那句现在落在**注释**里（原型那个 `/* ⛔ \`#2\` */` 标记已变成注释内容）＝ **空动作**，
  而判词也早在 `#2` 那天**反过来了**（旧 `N6`「必须登记」⇒ 新 `N6′`「名单不许回来」）。
  ⇒ 教训同 `_mut_vs.py`：**判词会变，变异件不会自己跟着变**（它只会**静默地**变成空动作）。
- `M2` `_doccheck`：`.md` 追加一句**错的计数**（「可复用设计规则 99 条」）⇒ 计数类事实必须红。
- `M3` `_links`：同一件追加一处**不存在的路径引用** ⇒ 断链必须红。
- `M4` `_ids`：同一件追加 `DEV-R-99`（**全库无定义**）⇒ 悬空编号必须红。
- `M5` ⭐ **`doc_audit --ui` 的 rc**（`TAIL-197` · 2026-09-30 办）：靶与 `M3` 同款（`DOC` 追加一处断链），
  但**量的是闸门那一侧** —— ⛔ 以前 `doc_audit --ui` 只把四检的退出码**打印**出来、**自己的 rc 仍是 0**
  （实测：`_smoke` 606/1 那一轮 `BAD: []`）⇒ 交付面回归**报得出来、拦不住**。
  现在非零**并进 rc** ⇒ 本靶必须让 `doc_audit --ui` **rc≠0 且输出里出现那句话**。
  ⚠️ 靶**刻意复用 `M3`** 那条（已验证有效）：`M1` 的旧靶教过一次"拿一个**说不出为什么有效**的靶当基线"的亏。

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
PROTO = DEMO / "材料报表自动化工作台-交互原型.html"     #: 原型本体（⚠️ `M1` **不再**拿它当靶，见下）
SMOKE = DEMO / "_smoke.js"                              #: ⭐ `M1` 的靶：`__X` 导出名单（`N6′` 判的是它）
DOC = DEMO / "原型导读.md"                              #: `_doccheck`/`_links`/`_ids` 的靶（在它们的 FILES/扫描面内）
#: ⚠️ 四检里 `_smoke` 只吃原型；另三件扫整个交付面 ⇒ 往**同一份 md** 追加一行即可分别打中后两件

NODE_FALLBACK = r"C:\Users\Administrator\.workbuddy\binaries\node\versions\22.22.2-3\node.exe"


def node_exe() -> str:
    return shutil.which("node") or NODE_FALLBACK


def run_check(script: str) -> tuple[int, str]:
    """跑一件：`_xxx.js`（交付面的 node 自检），或 `doc_audit --ui`（**闸门那一侧**）。

    ⭐ `TAIL-197`（2026-09-30）：加了后者 —— 「四检的非零退出码要**并进闸门的 rc**」这件事，
      只有在**闸门那一侧**量才算数（单看某一件 `.js` 自己的 rc，`M1`–`M4` 早就验过了）。
    """
    if script == "doc_audit --ui":
        r = subprocess.run([str(PY), "-X", "utf8",
                            str(ROOT / "tools" / "audit" / "doc_audit.py"), "--ui"],
                           cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
                           errors="replace", env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        return r.returncode, (r.stdout or "") + (r.stderr or "")
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
    #: ⭐ `TAIL-197`：闸门那一侧也要先量基线 —— 否则 M5 的"rc≠0"会被**本来就有红**满足（假绿）。
    rc_ui, out_ui = run_check("doc_audit --ui")
    print(f"基线（未改坏）闸门侧：doc_audit --ui rc={rc_ui}（应为 0）")
    if rc_ui != 0:
        print("  ⛔ 基线就不对 ⇒ 先清红再来跑本件")
        return 1

    cases = [
        # (说明, 靶件, 改坏方式, 要跑的检查, 判据串)
        #: ⚠️ 靶改成 `_smoke.js` 的 `__X` 导出（`#2` 之后原型里已无 `CHG` 名单，判词反转成 `N6′`）。
        ("M1 `_smoke`：`CHG` 名单**又回来了**（`#2` 已裁定拆掉它 ⇒ `N6′` 必须红）", SMOKE,
         ("replace", b"globalThis.__X={V,ACT,", b"globalThis.__X={CHG:1,V,ACT,"), "_smoke.js",
         ("N6", "名单又回来了")),
        ("M2 `_doccheck`：文档里写**错的计数**（设计规则条数 ≠ 主人实时值）", DOC,
         ("append", "\n\n（变异靶：可复用设计规则 99 条）\n", None), "_doccheck.js", ("设计规则条数",)),
        ("M3 `_links`：文档里出现**不存在的路径引用**（断链）", DOC,
         ("append", "\n\n（变异靶：见 `demo/变异靶-不存在.md`。）\n", None), "_links.js",
         ("变异靶-不存在.md",)),
        ("M4 `_ids`：文档里出现**全库无定义的编号**（悬空号）", DOC,
         ("append", "\n\n（变异靶：引用 `DEV-R-99`。）\n", None), "_ids.js", ("DEV-R-99",)),
        #: ⭐ `TAIL-197`：靶**复用 `M3`**（已验证有效的那条：`DOC` 追加一处断链），但量的是**闸门那一侧** ——
        #:   「`doc_audit --ui` 的 rc 必须跟着红」这一条以前**根本没人验**（因为它恒 0）。
        ("M5 `doc_audit --ui`：交付面坏了，**闸门自己的 rc 也要红**（`TAIL-197`）", DOC,
         ("append", "\n\n（变异靶：见 `demo/变异靶-不存在.md`。）\n", None), "doc_audit --ui",
         ("交付面四检有**非零退出码**",)),
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
