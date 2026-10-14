"""反向灵敏度（**交付面四检**：`_smoke` / `_doccheck` / `_links` / `_ids`）—— 证明它们**真有区分力**。

⚠️ 四检是**交付面**（真源 `demo/*.js` —— ⭐ 路径由 `audit_common.delivery_root()` 跟着 `.env` 走；
   ⛔ **别在本件写死某一份根**：`D:\\工作\\AI\\…` 那份 2026-10-06 已迁到 `D:\\dev\\…`，写死的路径当天就成哑靶
   —— 这正是 `M1` 靶漂的根因）里的 node 自检，
   由 `doc_audit --ui` 代跑（`MEMORY.md §〇之二` ⭐ "最易漏！"）。此前**从没被证明过"改坏了会不会红"**。

五靶（**一次只碰一个文件**，改完**立刻按 bytes 复原** ＋ 收尾 MD5；用户 2026-09-24：
「云同步也没那么蠢，只要别同时大量连续改文件」）：
- `M1` ⭐ **`_smoke` 自己的「覆盖面自检」**（`TAIL-233` 2026-10-06 **换靶** · `TAIL-234` **再修一次靶**）：
  把那道自检里的**弹窗覆盖面阈值**改大 ⇒ 它必须喊「断言失去区分力」。⚠️ **锚点字面见本件 `cases` 里的 M1** ——
  ⛔ 这里**不复述**那份字面（同仓规矩：注释里别写会被判据钉住的代码字面，两处一改必有一处漂）。
  ⚠️⚠️ **2026-10-06 晚（`TAIL-234`）实测：上一版换的靶是 `#2` 之前的形态 ——「命中 0 次」**。
  ⛔ 那不是"判据没区分力"，是**"一次都没验过"**（脚本照实报「未验证」而不是假绿 —— 这一半是好设计）。
  ⇒ 根因是**靶必须逐字节在**真源那份**上核过**：旧根那份 `_smoke.js` 命中、新根那份不命中（`CHG` 名单已整份删除 ⇒
     那道覆盖面自检连同它一起没了）⇒ **"旧根能命中" ≠ "真源能命中"**，两份同名文件**必须各查一份**（同 `#2` 那条教训）。
  ⛔ 这里**不复述**那份字面（同仓规矩：注释里别写会被判据钉住的代码字面，两处一改必有一处漂）。
  ⚠️⚠️⚠️ **换靶理由（本仓「上一轮的修复本身就是无效动作」第三例 · 三层错，必须连着记）**：
  ① **2026-09-30 已修过一次**，把靶从「往原型插 `const CHG=[];`」改成「往 `_smoke.js` 的 `__X` 导出里
     把 `CHG` 加回来」，并认定判词已反转成 `N6′`「名单不许回来」；
  ② ⛔ **那个认定在交付面不成立** —— 实测原型的 `__X` 导出**本来就有 `CHG`**（第 63 行
     `'CHG,pst,pstData,…'`），而 `_smoke.js` 里的判词是 **`N6`「凡渲染成表单元素的动作都必须在 `CHG` 里」
     （第 1764 行 · 旧方向 · 在原型上完全正确）**；全库搜「不许回来」**零命中** ⇒ **交付面四检里
     从来没有「`CHG` 名单不许回来」这条守卫**（那条在**壳侧** `imp_shell` 判据里，属壳与原型两份不同的东西）；
  ③ ⇒ 旧靶往 `__X` 加的是**重复键** `CHG:1` ⇒ **什么也证明不了**，实测 rc=0。
  ⇒ 教训升级：**`#2` 拆掉 `CHG` 说的是壳（委托层直呼 `ACT[a]`），不是原型** ⇒ 「壳里没有 `X`」
     **推不出**「原型里没有 `X`」。跨两份东西下结论前先各查一份。
  ⭐ 新靶守的是**交付面真有、且本仓记过它假绿过**的那半（2026-09-13 实测：项目面板收起时
  `checkbox` 根本不渲染 ⇒ 面板清单不同步 ⇒ 整片盲区）⇒ 判词是交付面自己写的，措辞稳定、⛔ 不脆。
  ⚠️⭐ **覆盖变化必须登记（本轮 `/code-review` 的 Spec 轴点名要求）**：换靶后**本件不再覆盖任何
  `CHG` 相关语义**（`N6`「表单元素动作必须在 `CHG` 里」这条**业务判词**现在**没有变异覆盖**了）。
  ⇒ 那条守卫（`N6` 本身）的反向灵敏度**在壳侧判据**里，不在交付面四检 ⇒ **两处不重叠、不互相替代**。
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

DEMO = ROOT / "delivery" / "demo"
PROTO = DEMO / "材料报表自动化工作台-交互原型.html"     #: 原型本体（⚠️ 已**不是**任何一靶，见下）
SMOKE = DEMO / "_smoke.js"                              #: `M1` 的靶：`N6` 判词里的**覆盖面自检**那一行（见文件头「换靶理由」）
DOC = delivery_root() / "demo" / "原型导读.md"                              #: `_doccheck`/`_links`/`_ids` 的靶（在它们的 FILES/扫描面内）
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
        #: ⛔ 2026-10-06 晚（`TAIL-234`）**靶再修一次** —— 上一版（`TAIL-233`）把靶写成 `#2` **之前**的
        #:   `_smoke.js` 形态，真源那份**没有这一行** ⇒ 实测「靶串命中 0 次」＝**这条从没验过**。
        #:   ⭐ 真源那份**自己留着同族的那道**（`_smoke.js` 的「无死控件」守卫尾部：弹窗覆盖面不足就抛）
        #:   —— 交付面自己写的判词、措辞稳定（理由见文件头「换靶理由」那一段）。
        #:   ⚠️ 阈值取 `1e9` 而不是「30 ⇒ 300」那种倍数：真实弹窗数会变，**倍数会有一天真够到**
        #:   （那就变成"改坏了却红不了"）⇒ 取一个**恒成立**的量，让"覆盖面自检失效"这件事必红。
        ("M1 `_smoke`：「无死控件」守卫里的**覆盖面自检**被改坏（阈值 ⇒ 恒成立）⇒ 它必须喊「断言失去区分力」", SMOKE,
         ("replace", b"(nModal < 5)", b"(nModal < 1e9)"), "_smoke.js",
         ("断言失去区分力",)),
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
