"""**PRG 表单端点形态审查**（prg_form_audit）—— 查「POST 端点的参数声明与表单提交方式是否一致」。

**为什么有它**（2026-09-17 **真机实测**抓到的缺陷）：
    服务端渲染的 PRG 端点，输入来自 `<form method="post">` 的 **body**（hidden inputs）。
    而多个端点把参数声明成了 `Query(...)`（= 只读 URL query string）⇒ **表单提交永远 422**：
    · `POST /m04/cell` = **422**（行内改列「存」按钮点了没反应）· 另 `act_delete` / `act_re_match` 同病；
    · `POST /m05/revoke` = **422**（**收款流水的「撤销」按钮点了没反应**）· 另 3 处同病。
    ⚠️ 而当时 `pytest` **全绿** —— 因为断言只写了 `assert 'action="/m04/cell"' in html`
      （**只查字符串在不在**）。**离线断言看不见**，只有真机发一次请求才暴露。
    ⭐ 与 `chain_audit` 同一初心：**判据要钉住"这条路真的走得通"，不是"零件在不在"**。

**两档**（同形态、两种后果）：
- ⛔ **必填**（`Query(...)` 无默认值）⇒ 表单 body 里没有它 ⇒ **永远 422**（按钮废掉）⇒ **非零退出**
- ⚠️ **可选**（`Query("")` 有默认值）⇒ 不报错，但表单传的是 body、取不到 ⇒ **筛选条件静默丢失**
  （PRG 回跳回不到原查询）⇒ 只报不计

⚠️ `/api/*` 的 JSON 端点**不受此限**（前端 `fetch` 确实可以带 query string）。

用法：
    python tools/prg_form_audit.py            # 有「必填 Query」即非零退出
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "backend" / "app"
DECO = re.compile(r'@\w+\.post\(\s*"([^"]+)"')
SIG_END = re.compile(r"\)\s*->|\)\s*:")
HARD = re.compile(r"=\s*Query\(\s*\.\.\.\s*\)")   # 必填 ⇒ 422
SOFT = re.compile(r"=\s*Query\(")                 # 可选 ⇒ 丢筛选


def main() -> int:
    hard: list[str] = []
    soft: list[str] = []
    scanned = 0
    for path in sorted(ROOT.rglob("*.py")):
        if "__pycache__" in str(path):
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        for i, ln in enumerate(lines):
            m = DECO.search(ln.strip())
            if not m:
                continue
            route = m.group(1)
            if route.startswith("/api/"):
                continue
            sig: list[str] = []
            for j in range(i + 1, min(i + 40, len(lines))):
                sig.append(lines[j].strip())
                if SIG_END.search(lines[j]):
                    break
            body = " ".join(sig)
            fn = re.search(r"def\s+(\w+)", body)
            rel = path.relative_to(ROOT.parent.parent).as_posix()
            head = f"{rel}:{i + 1}  POST {route}  →  {fn.group(1) if fn else '?'}"
            scanned += 1
            if HARD.search(body):
                hard.append(head)
            elif SOFT.search(body):
                soft.append(head)

    print("=" * 78)
    print(" PRG 表单端点形态审查 · prg_form_audit —— 参数声明 vs 表单提交方式")
    print("=" * 78)
    print(f" 扫过 PRG（非 /api）POST 端点 {scanned} 个")
    print()
    if hard:
        print(f"⛔ 必填参数声明为 Query ⇒ **表单提交永远 422**（{len(hard)} 处）：")
        for s in hard:
            print("  · " + s)
    else:
        print("✅ 无「必填 Query」类 —— 不会出现「按钮点了 422」")
    if soft:
        print()
        print(f"⚠️ 可选参数声明为 Query ⇒ 不报错但**筛选条件静默丢失**（{len(soft)} 处，仅报不计）：")
        for s in soft:
            print("  · " + s)
    print()
    print(f"结论：**必须修 {len(hard)}**" + ("（非零退出）" if hard else "（rc=0）"))
    return 1 if hard else 0


if __name__ == "__main__":
    sys.exit(main())
