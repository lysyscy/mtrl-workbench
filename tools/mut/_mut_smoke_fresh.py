"""守真机前置「服务在跑的是不是磁盘上这一份代码」：一致必须**放行**，磁盘侧对不上必须**指名报红**。

（`TAIL-298` 收尾加的，2026-10-11 真实发生过：改了 `domain.JC_COLUMNS` 没重启服务 ⇒
 `/api/m11/list` 还是旧列清单 ⇒ 钉列/隐藏整体错位、症状全在界面上 ⇒ 白跑一整轮 39 段真机。）

**靶** = `tools/probe/_shell_smoke.py` 的 `_freshness`（真机那一半：页面 `fetch` ＋ 磁盘 `import`，
纯比较那半是 `_freshness_error`）。做法：源码在**内存**里 exec 两遍 ——
① 原样 ⇒ 必须**零错误**（服务与磁盘一致才叫绿）；② 把磁盘侧期望塞一个哨兵列 ⇒ 必须转红
（且那句话里得有「旧模块」与 `server_ctl` ⇒ 人照着就能修，⛔ 不是"某处不一致"）。

⚠️ 靶在**内存**（⛔ 不写 `tools/probe/` 正式件）、不写库、不落文件。
⚠️ 要真机（活服务 ＋ 浏览器）：先起服务再跑本件。
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "tools" / "probe")]

from _mut_probe_m11 import _open                      # noqa: E402
from playwright.sync_api import sync_playwright       # noqa: E402


def main() -> int:
    source = (ROOT / "tools" / "probe" / "_shell_smoke.py").read_text(encoding="utf-8")
    anchor = 'want = [c["key"] for c in D.JC_COLUMNS]'
    if source.count(anchor) != 1:
        print(f"  ⛔ 锚点在 `_shell_smoke.py` 里命中 {source.count(anchor)} 次（期望 1）⇒ **本件未验证**")
        return 1
    # ⚠️ `__file__` 必须给：探针里 `_freshness` 用 `pathlib.Path(__file__)` 找仓根 —— exec 出来的模块**没有**
    #    它（2026-10-11 首跑就栽在这：`NameError: name '__file__' is not defined`）。
    probe = ROOT / "tools" / "probe" / "_shell_smoke.py"
    base_ns = {"__file__": str(probe)}                     # ⛔ 别用 `__main__`（会真跑 39 段）
    with sync_playwright() as pw:
        page = _open(pw)
        ns = dict(base_ns, __name__="isolated_smoke_fresh")
        exec(source, ns)
        errors: list[str] = []
        ns["_freshness"](page, errors)
        if errors:
            print("  ⛔ 基线就红（服务是不是真的旧？先 `server_ctl -Action restart`）：", errors)
            return 1
        print("  ✅ 基线：服务与磁盘同一份列清单 ⇒ 放行")
        ns2 = dict(base_ns, __name__="isolated_smoke_stale")
        exec(source.replace(anchor, anchor + " + ['__sentinel__']"), ns2)
        errors = []
        ns2["_freshness"](page, errors)
        hit = [e for e in errors if "旧模块" in e and "server_ctl" in e]
        if not hit:
            print("  ⛔ 磁盘侧被改坏，前置**没有**指名报红 ⇒ 判据没牙：", errors)
            return 1
        print("  ✅ 变异：磁盘侧多一个哨兵列 ⇒ 前置**指名**报红（含「旧模块」＋ 重启命令）")
        page.context.browser.close()
    print("  靶在内存、未写正式件、未写库。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
