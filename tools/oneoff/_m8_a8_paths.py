"""A8 · **路径可配置改造**（M8 · `TAIL-188` · 2026-09-29 用户「全按推荐」）

## 为什么做

目标机（办公室电脑）**还要继续调试开发** ⇒ 它上面的路径与本机**必然不同**。本机写死的三处：
① **交付面定位** ② **node 路径** ③ **Playwright 目录**。

## 查证结果（⭐ 少改一处）

① **交付面定位本来就可配** —— `audit_common.delivery_root()` 读**仓根 `.env` 的 `PRD_ACCEPTANCE_BASELINE`**，
   上溯两级得交付面根 ✓（本仓的行事方式：**一处定义**，⛔ 不另造第二套机制）⇒ **不改代码**，
   只在 `docs/deployment.md` 写清"目标机怎么填、不填会怎样"。
② **node**：`doc_audit.run_ui_checks()` 里**写死**了本机那份 node 的绝对路径 ✗ ⇒ 改成
   `MTRL_NODE`（环境变量）⇒ `shutil.which("node")`（PATH）⇒ 旧默认路径，三级回退；
   都找不到 ⇒ **明确说"跳过 + 试过哪三处 + 怎么办"**（⛔ 不静默）。
③ **`tools/probe/_audit_face.py`**：`FACE` **写死**本机交付面路径 ✗ ⇒ 改走
   `audit_common.delivery_root()`（**同一机制** ✓）；拿不到 ⇒ 打印原因并**退出 2**（⛔ 不抛栈）。
④ **Playwright 目录**：标准环境变量 `PLAYWRIGHT_BROWSERS_PATH` ✓ ⇒ 只写进文档（探针是开发期工具）。

## 口径（写进 `docs/deployment.md`）

| 要配的 | 怎么配 | 不配会怎样 |
|---|---|---|
| 交付面定位 | 仓根 `.env` 里 `PRD_ACCEPTANCE_BASELINE=<交付面>/PRD/验收/验收基线.json` | 留空 ⇒ `doc_audit --ui` / `ui_parity` / `acc_report`（四态）**跑不了**（会打印"跳过 + 原因"） |
| node | `MTRL_NODE=<node.exe 全路径>`（或把它放进 PATH） | 找不到 ⇒ 交付面四检跳过（⛔ 不是静默：会打印试过哪三处） |
| Playwright 浏览器 | `PLAYWRIGHT_BROWSERS_PATH` | 真机探针装不上浏览器 ⇒ 那几条真机段跑不了（⚠️ 探针是开发期工具，目标机可不跑） |

跑法：`backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_m8_a8_paths.py --check` / `--write`
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC_AUDIT = ROOT / "tools" / "audit" / "doc_audit.py"
FACE = ROOT / "tools" / "probe" / "_audit_face.py"
DEPLOY = ROOT / "docs" / "deployment.md"
PLAN = ROOT / ".workbuddy" / "plans" / "开发计划-主文档.md"

EDITS: list[tuple[Path, str, str]] = [
    # ① node 三级回退（MTRL_NODE ⇒ PATH ⇒ 旧默认）＋ 说清"试过哪三处"
    (DOC_AUDIT,
     'def run_ui_checks() -> list[str]:\n    node = Path(r"C:\\Users\\Administrator\\.workbuddy\\binaries\\node\\versions\\22.22.2-3\\node.exe")\n'
     '    root = delivery_root()\n    if not node.exists() or not root:\n'
     '        return ["  （跳过：找不到 node 或交付面根）"]',
     'def _resolve_node() -> Path | None:\n'
     '    """⭐ A8（2026-09-29 · `TAIL-188`）：node 从**本机写死**改成**三级回退** ——\n'
     '    `MTRL_NODE`（目标机显式指路）⇒ `PATH` 里的 `node`（装过就有）⇒ 旧默认（本机那份）。\n'
     '    ⚠️ 换机时**必然不同**（本机写死的是 `C:\\Users\\Administrator\\.workbuddy\\...`）⇒ 找不到就**照实说**，⛔ 不静默。"""\n'
     '    cands: list[Path] = []\n'
     '    env = os.environ.get("MTRL_NODE", "").strip()\n'
     '    if env:\n        cands.append(Path(env))\n'
     '    which = shutil.which("node")\n'
     '    if which:\n        cands.append(Path(which))\n'
     '    cands.append(Path(r"C:\\Users\\Administrator\\.workbuddy\\binaries\\node\\versions\\22.22.2-3\\node.exe"))\n'
     '    for c in cands:\n        if c.exists():\n            return c\n    return None\n\n\n'
     'def run_ui_checks() -> list[str]:\n    node = _resolve_node()\n'
     '    root = delivery_root()\n    if not node:\n'
     '        return ["  （跳过：找不到 node —— 试过三处：环境变量 `MTRL_NODE` / PATH / 旧默认路径。"\n'
     '                "⚠️ 装 node 或设 `MTRL_NODE=<node.exe 全路径>`；详见 `docs/deployment.md`）"]\n'
     '    if not root:\n'
     '        return ["  （跳过：拿不到交付面根 —— 在仓根 `.env` 里设 `PRD_ACCEPTANCE_BASELINE=`"\n'
     '                "<交付面>/PRD/验收/验收基线.json`；目标机不装交付面属已知代价，详见 `docs/deployment.md`）"]'),
    # ② doc_audit 的 import 补两个标准库
    (DOC_AUDIT,
     "from collections import Counter\nfrom pathlib import Path",
     "import os\nimport shutil\nfrom collections import Counter\nfrom pathlib import Path"),
    # ③ `_audit_face.py` 的 FACE 改走**同一机制**（`audit_common.delivery_root()`）
    (FACE,
     'FACE = pathlib.Path(r"D:\\工作\\AI\\PRD编写夹 - Workbuddy专用")\nMOD_DIR = FACE / "PRD" / "02-功能规格"',
     '# ⭐ A8（2026-09-29 · `TAIL-188`）：交付面根**不再写死本机路径** ⇒ 走与 `doc_audit` **同一机制**\n'
     '#   （`audit_common.delivery_root()` = 读仓根 `.env` 的 `PRD_ACCEPTANCE_BASELINE` 上溯两级）。\n'
     '#   ⚠️ 换机时交付面路径必然不同；拿不到 ⇒ 打印原因并退出 2（⛔ 不抛栈）。\n'
     'sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "audit"))\n'
     'from audit_common import delivery_root                          # noqa: E402\n\n'
     'FACE = delivery_root()\n'
     'if FACE is None:\n'
     '    print("⛔ 拿不到交付面根 —— 在仓根 `.env` 里设 `PRD_ACCEPTANCE_BASELINE=<交付面>/PRD/验收/验收基线.json`。")\n'
     '    print("   目标机若不装交付面，本条尺子本就跑不了（已知代价）⇒ 详见 `docs/deployment.md`。")\n'
     '    raise SystemExit(2)\n'
     'MOD_DIR = FACE / "PRD" / "02-功能规格"'),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    apply = a.write and not a.check

    for i, (p, old, new) in enumerate(EDITS, 1):
        s = p.read_text(encoding="utf-8")
        n = s.count(old)
        print(f"  {'✓' if n == 1 else '⛔'} #{i} {p.relative_to(ROOT)}：命中 {n} 处（要 1）")
        if n != 1:
            print(f"     ⛔ 锚点对不上 ⇒ 整批停手：{old[:60]}…")
            return 2
        if apply:
            p.write_text(s.replace(old, new, 1), encoding="utf-8", newline="")

    # ④ 文档：在 §五 之前插一节"要配的三处"（⚠️ 锚**小节标题**更稳 —— 先前按整行匹配命中 0 处）
    s = DEPLOY.read_text(encoding="utf-8")
    old5 = "## §五 在目标机继续开发（包已按此配齐）"
    new5 = ("## §四之补 · 换机会踩的三处路径（✅ 已做成可配 · A8 · 2026-09-29）\n\n"
            "- ✅ **三处路径可配**（A8 · 2026-09-29）：\n"
            "  | 要配的 | 怎么配 | ⛔ 不配会怎样 |\n"
            "  |---|---|---|\n"
            "  | **交付面定位** | 仓根 `.env`：`PRD_ACCEPTANCE_BASELINE=<交付面>/PRD/验收/验收基线.json`（**同一机制**：`doc_audit` 与 `_audit_face.py` 都读它） | 留空 ⇒ `doc_audit --ui` / `ui_parity` / `acc_report`（四态报表）**跑不了**（会打印「跳过 + 原因」） |\n"
            "  | **node** | 环境变量 `MTRL_NODE=<node.exe 全路径>`，或把 node 放进 `PATH` | 三级都找不到 ⇒ 交付面**四检跳过**（会打印试过哪三处 ⇒ ⛔ 不是静默） |\n"
            "  | **Playwright 浏览器** | `PLAYWRIGHT_BROWSERS_PATH` | 真机探针装不上浏览器 ⇒ 那几条真机段跑不了（⚠️ 探针是**开发期**工具，目标机可不跑） |\n"
            "  ⭐ 一句话：**要跑「验收那套」就把交付面与 node 配齐；只跑系统本身则什么都不用配**（`ops/selfcheck.ps1` 不依赖它们）。\n\n"
            "---\n\n" + old5)
    n = s.count(old5)
    print(f"  {'✓' if n == 1 else '⛔'} #4 docs/deployment.md：命中 {n} 处（要 1）")
    if n != 1:
        print("     ⛔ 锚点对不上 ⇒ 停手"); return 2
    if apply:
        DEPLOY.write_text(s.replace(old5, new5, 1), encoding="utf-8", newline="")

    # ⑤ 台账：`TAIL-188` 补脚本路径（本轮它们**已经建出来了** ⇒ `T3` 不再判幽灵）
    p = PLAN
    raw = p.read_text(encoding="utf-8", newline="")
    eol = "\r\n" if "\r\n" in raw else "\n"
    t = raw.replace("\r\n", "\n")
    oldrow = "**打包 / 落地还原 / 自检三脚本 ＋ 一页落地说明（下一批新增）** ＋ **路径可配置改造**"
    newrow = ("`ops/pack.ps1` / `ops/deploy_restore.ps1` / `ops/selfcheck.ps1` ＋ `docs/deployment.md`"
              "（✅ 已建 · 2026-09-29）· ✅ **路径可配置改造已办**（node 三级回退；交付面定位走 `.env` 的"
              " `PRD_ACCEPTANCE_BASELINE`；`_audit_face.py` 改走同一机制；Playwright 目录写进 `docs/deployment.md`）")
    n = t.count(oldrow)
    print(f"  {'✓' if n == 1 else '⛔'} #5 计划 TAIL-188 行：命中 {n} 处（要 1）")
    if n != 1:
        print("     ⛔ 锚点对不上 ⇒ 停手"); return 2
    if apply:
        p.write_text(t.replace(oldrow, newrow, 1).replace("\n", eol), encoding="utf-8", newline="")

    print("\n" + ("🔧 已落盘" if apply else "🧪 --check（干跑）"))
    print("   复核：`_run_rulers.py` 全绿（含 `T3`/`T6`）＋ `doc_audit --ui` 仍能跑（本机 node 走旧默认那条路）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
