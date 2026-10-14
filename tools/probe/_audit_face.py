"""交付面**结构完整性审查**（一次性 · 可复跑）—— 抓「内容静默缺失」类问题。

为什么要它：交付面**不在 git 里**（WPS 同步树）⇒ 文件被回退时**没有历史可比对**。
2026-09-17 实测到一次：`MOD-06.md` 少了「能力 11 · 按模板导出」整行（只在一份 `-副本` 里），
而**机器此前看不见** —— `doc_audit` 的四检全绿、`_doccheck` 31/31 通过。

五把尺子（都是**跨文件一致性**，不依赖 git 历史）：
- `A` 各 `MOD-*.md` 的**能力编号连续**（1…N 无断档）
- `B` 验收基线里 `module = MOD-XX` 的**每个用例**，都要在该 MOD 的**能力表里被引用**
      ← 这一条就是抓 `MOD-06` 的那把尺子
- `C` 能力表里引用的 `ACC-*` **必须真存在**（防幽灵用例号）
- `D` `用例索引.md` 的每个 `ACC-*` 必须在 `验收基线.json` 里
- `E` `05-任务分解.md` 点名的 `ACC-*` 必须在 `用例索引.md` 里

跑法：`python tools/_audit_face.py`（退出码非 0 = 有「必须修」项）
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

# ⭐ A8（2026-09-29 · `TAIL-188`）：交付面根**不再写死本机路径** ⇒ 走与 `doc_audit` **同一机制**
#   （`audit_common.delivery_root()` = 读仓根 `.env` 的 `PRD_ACCEPTANCE_BASELINE` 上溯两级）。
#   ⚠️ 换机时交付面路径必然不同；拿不到 ⇒ 打印原因并退出 2（⛔ 不抛栈）。
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "audit"))
from audit_common import delivery_root                          # noqa: E402

FACE = delivery_root()
if FACE is None:
    print("⛔ 拿不到产品资料根 —— 在仓根 `.env` 里设 `PRD_ACCEPTANCE_BASELINE=delivery/PRD/验收/验收基线.json`。")
    print("   目标机若不装交付面，本条尺子本就跑不了（已知代价）⇒ 详见 `docs/guides/deployment.md`。")
    raise SystemExit(2)
MOD_DIR = FACE / "PRD" / "02-功能规格"
INDEX = FACE / "PRD" / "验收" / "用例索引.md"
BASELINE = FACE / "PRD" / "验收" / "验收基线.json"
DECOMP = FACE / "PRD" / "05-任务分解.md"

ACC_RE = re.compile(r"`(ACC-[A-Z0-9-]+)`")
ACC_HEAD_RE = re.compile(r"^\|\s*`(ACC-[A-Z0-9-]+)`\s*\|.*", re.M)
ROW_RE = re.compile(r"^\|\s*(\d+)\s*\|(.*)$", re.M)


def index_all(text: str) -> set[str]:
    """`用例索引.md` 首列的**全部**用例号（含「不建用例」—— 引用它们是合法的，见 `MOD-13` 能力 5/6）。"""
    return {m.group(1) for m in ACC_HEAD_RE.finditer(text)}


def index_cases(text: str) -> set[str]:
    """`用例索引.md` 首列里**真的要建判据**的用例号 —— ⛔ 排除「不建用例」（Non-goals / 二期）。"""
    kept: set[str] = set()
    for raw in text.splitlines():
        m = ACC_HEAD_RE.match(raw)
        if not m:
            continue
        if "不建用例" in raw or "不建判据" in raw:
            continue
        kept.add(m.group(1))
    return kept


def mod_files() -> list[pathlib.Path]:
    return sorted(p for p in MOD_DIR.glob("MOD-*.md") if "副本" not in p.name)


def capability_rows(text: str) -> list[tuple[int, str]]:
    """`§二 能力清单` 的行（**从「## 二、能力清单」到下一个 `## `**）。"""
    start = text.index("## 二、能力清单")
    end = text.find("\n## ", start + 10)
    body = text[start:end if end > 0 else len(text)]
    return [(int(n), rest) for n, rest in ROW_RE.findall(body)]


def main() -> int:
    problems: list[str] = []
    suspects: list[str] = []

    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    cases = baseline["cases"]
    index_text = INDEX.read_text(encoding="utf-8")
    index_cases_set = index_cases(index_text)
    index_all_set = index_all(index_text)
    decomp_cases = set(ACC_RE.findall(DECOMP.read_text(encoding="utf-8")))

    by_module: dict[str, set[str]] = {}
    for name, case in cases.items():
        by_module.setdefault(str(case.get("module") or ""), set()).add(name)

    for path in mod_files():
        text = path.read_text(encoding="utf-8")
        rows = capability_rows(text)
        nums = [n for n, _ in rows]
        # A 编号连续
        if nums and nums != list(range(1, len(nums) + 1)):
            problems.append(f"[A] {path.name} 能力编号不连续：{nums}")
        # C 引用的用例要真存在
        for n, rest in rows:
            for acc in ACC_RE.findall(rest):
                if acc not in index_all_set:
                    problems.append(f"[C] {path.name} 能力 {n} 引用了不存在的用例 {acc}")
        # B 该模块的用例都要在能力表里被引用（**抓 MOD-06 那把尺子**）
        cited = set()
        for _n, rest in rows:
            cited |= set(ACC_RE.findall(rest))
        mod = path.stem                       # `MOD-06`
        missing = sorted(by_module.get(mod, set()) - cited)
        if missing:
            suspects.append(f"[B] {path.name} 能力表**没有引用**这些用例（该模块名下）：{missing}")

    # D 用例索引 → 基线
    for acc in sorted(index_cases_set - set(cases)):
        problems.append(f"[D] 用例索引里的 {acc} 在验收基线里不存在")
    for acc in sorted(set(cases) - index_cases_set):
        problems.append(f"[D] 验收基线里的 {acc} 不在用例索引首列")
    # E 任务分解 → 用例索引
    for acc in sorted(decomp_cases - index_cases_set):
        problems.append(f"[E] 05-任务分解 点名了但用例索引里没有：{acc}")

    print(f"交付面结构审查：MOD 文件 {len(mod_files())} · 用例 {len(cases)} · 判据点 "
          f"{sum(len(c['points']) for c in cases.values())}")
    for line in problems:
        print("  必须修：", line)
    for line in suspects:
        print("  疑似　：", line)
    if not problems and not suspects:
        print("  ✅ 五把尺子全过（编号连续 · 引用双向对得上）")
    print(f"\n必须修 {len(problems)} · 疑似 {len(suspects)}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
