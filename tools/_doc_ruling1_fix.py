"""修 `doc_audit` 的 5 条 T6 报红（都是本轮落账自己引入的格式问题）：

1. `TAIL-04` / `TAIL-39` / `TAIL-40` 的「阶段」栏**必须以受控词开头**（我写了 `⭐ **立刻**` / `**立刻**`
   ⇒ 前面有星号和加粗 ⇒ 判不出受控词）⇒ 改成**纯 `立刻（…）`**。
2. `TAIL-28` 已销号 ⇒ **必须从 B 类表移出**（编号唯一；留痕在 §14.3 与 §15「四、已销号」两处）。
3. §15 顶部「当前状态」计数要跟着改：A 8→10 · B 1→0 · 已销号 31→32。
"""

from __future__ import annotations

import pathlib
import sys
from datetime import datetime

ROOT = pathlib.Path(__file__).resolve().parents[1]
PLAN = ROOT / ".workbuddy" / "plans" / "开发计划-主文档.md"

lines = PLAN.read_text(encoding="utf-8").split("\n")
done: list[str] = []


def sub1(old: str, new: str, tag: str) -> None:
    global lines
    joined = "\n".join(lines)
    n = joined.count(old)
    if n != 1:
        raise SystemExit(f"⛔ {tag}：命中 {n} 次（期望 1）\n{old[:140]}")
    lines = joined.replace(old, new).split("\n")
    done.append(tag)
    print(f"  ✅ {tag}")


# ---- ① 三处「阶段」栏改纯受控词
sub1(
    "| ⭐ **立刻**（用户 2026-09-18 裁定「现在就做」· 原排 M6） | **进行中**",
    "| 立刻（用户 2026-09-18 裁定「现在就做」· 原排 M6） | **进行中**",
    "TAIL-04 阶段 → 立刻（纯受控词）",
)
sub1(
    " | **立刻** | 待做 |",
    " | 立刻 | 待做 |",
    "TAIL-39 阶段 → 立刻（纯受控词）",
)
sub1(
    "（规则**从库读**，不得分叉成第二份） | **立刻** | 待做（**方案先行**：用户要求先看方案再动） |",
    "（规则**从库读**，不得分叉成第二份） | 立刻 | 待做（**方案先行**：用户要求先看方案再动） |",
    "TAIL-40 阶段 → 立刻（纯受控词）",
)

# ---- ② 把已销号的 TAIL-28 从 B 类表移出（编号唯一）
i = None
for k, ln in enumerate(lines):
    if ln.startswith("| `TAIL-28` | **2 个老旧项目待建档**（真机抓 2026-09"):
        i = k
        break
if i is None:
    raise SystemExit("⛔ B 类表里找不到 TAIL-28 行（可能已移出）")
lines.pop(i)
done.append("B 类表 · 移出已销号的 TAIL-28")
print("  ✅ B 类表 · 移出已销号的 TAIL-28")

# ---- ③ 计数行
now = datetime.now().strftime("%Y-%m-%d %H:%M")
_hdr = [k for k, ln in enumerate(lines) if ln.startswith("> **当前状态（2026-09-18")]
if len(_hdr) != 1:
    raise SystemExit(f"⛔ 计数行命中 {len(_hdr)} 次")
lines[_hdr[0]] = (
    f"> **当前状态（{now}）**：A 类 **10** 条 · B 类 **0** 条 · C 类 **1** 条 · 已销号 **32** 条。"
)
done.append("§15 计数行 → A 10 · B 0 · C 1 · 已销号 32")
print("  ✅ §15 计数行 → A 10 · B 0 · C 1 · 已销号 32")

PLAN.write_text("\n".join(lines), encoding="utf-8")
print(f"\n共 {len(done)} 处")
sys.exit(0)
