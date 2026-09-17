#!/usr/bin/env python
"""素材守卫（asset_audit）—— 查「**一手权威有没有被真用上**」里的**素材包那一半**。

**为什么存在**（用户 2026-09-17 原话）：
    「**之前明明素材包里有实现，你也非要自己试半天** —— 我的积分和时间都耗在这上面了」。
    ⇒ 根因不是"态度"，是**没把「一手权威」变成必查项**。本尺子就是那个必查项：
    它盯着 `ops/素材包-索引.md` —— **每条素材必须说清"谁在用 / 什么时候接 / 为什么不用"**，
    且**说的必须是真的**（落点真存在 · 台账真存在 · 用例号真存在）。

### 四把尺子（都**零人工登记** —— 信息全在索引表自己的栏位里）
| 代号 | 检查 | 判据 |
|---|---|---|
| `A1` | §一「**已在用**」的**落点路径**必须真实存在 | 幽灵路径 ⇒ **红**（"以为接了其实没有"） |
| `A2` | §二「**还没接**」的条目必须挂到一条**真实存在的 `TAIL-*`** | 缺 / 幽灵台账号 ⇒ **红**（"以为记着了其实没有"） |
| `A3` | 每行**栏位必须齐全**（素材 / 是什么 / 落点或时机 / 备注） | 空格 ⇒ **红**（没栏位的条目 = 没想清楚的条目） |
| `A4` | 索引里引到的 `ACC-*` 用例号必须真实存在 | 幽灵用例号 ⇒ **红** |
| `A5` | ⭐ **运行时依赖**类（模板本体等）必须**实际在仓** | 缺文件 ⇒ **红**（"少带一个交付物"） |

用法：
    python tools/asset_audit.py            # 人读报告（有红即非零退出）
    python tools/asset_audit.py --json     # 机器可读
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "ops" / "素材包-索引.md"
PLAN = ROOT / ".workbuddy" / "plans" / "开发计划-主文档.md"
ENV = ROOT / ".env"

# 表格 row 里以反引号包住、且像"本仓路径"的 token
PATH_RE = re.compile(r"`([A-Za-z0-9_./\\-]+)`")
REPO_PREFIX = ("backend/", "tools/", "ops/", "frontend/", ".workbuddy/", "logs/", "artifacts/")
TAIL_RE = re.compile(r"TAIL-\d{2}")
ACC_RE = re.compile(r"ACC-[A-Z0-9]+(?:-[A-Z0-9]+)*-\d{3}")
DEP_MARKERS = ("运行时依赖", "须随代码走")

SECTIONS = {
    "一": ("## 一、可直接复用", "素材（包内相对路径）", 4),
    "二": ("## 二、可复用、**但还没接**", "素材", 4),
    "三": ("## 三、只作参照", "素材", 2),
}


def cellsof(line: str) -> list[str]:
    raw = line.strip()
    if raw.startswith("|"):
        raw = raw[1:]
    if raw.endswith("|"):
        raw = raw[:-1]
    return [c.strip() for c in raw.split("|")]


def is_sep(cells: list[str]) -> bool:
    return all(set(c) <= set("-: ") and c for c in cells)


def load_sections() -> dict[str, list[list[str]]]:
    out: dict[str, list[list[str]]] = {k: [] for k in SECTIONS}
    cur = None
    for line in INDEX.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            cur = None
            for key, (head, _c1, _n) in SECTIONS.items():
                if line.startswith(head):
                    cur = key
                    break
            continue
        if cur is None or not line.strip().startswith("|"):
            continue
        cells = cellsof(line)
        if is_sep(cells):
            continue
        out[cur].append(cells)
    return out


def tail_ids() -> set[str]:
    txt = PLAN.read_text(encoding="utf-8")
    return set(TAIL_RE.findall(txt))


def acc_ids() -> set[str]:
    p = None
    for line in ENV.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("PRD_ACCEPTANCE_BASELINE"):
            p = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not p:
        return set()
    q = Path(p)
    if not q.exists():
        return set()
    data = json.loads(q.read_text(encoding="utf-8"))
    cases = data.get("cases", {})
    if isinstance(cases, dict):
        # 形态 = {用例号: {...}}（本仓现状）
        return set(cases) | {v.get("id", "") for v in cases.values() if isinstance(v, dict)}
    return {c.get("id", "") for c in cases if isinstance(c, dict)}


def repo_paths(text: str) -> list[str]:
    return [t for t in PATH_RE.findall(text) if t.startswith(REPO_PREFIX)]


def main() -> int:
    ap = argparse.ArgumentParser(description="素材守卫")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if not INDEX.exists():
        print(f"⛔ 找不到索引：{INDEX}")
        return 1

    secs = load_sections()
    tails = tail_ids()
    accs = acc_ids()
    red: list[str] = []
    info: list[str] = []

    a1 = a2 = a3 = a4 = a5 = 0

    # ── A3 · 栏位齐全 + A1/A5 · 落点真实存在
    for key in ("一", "二", "三"):
        _head, _first, want = SECTIONS[key]
        rows = [r for r in secs[key] if not r[0].startswith("素材（") and not r[0].startswith("素材`")]
        for r in rows:
            if len(r) < want or any(not c for c in r[:want]):
                red.append(f"A3 §{key} 栏位不全（{want} 栏）: {' | '.join(r)[:90]}")
                a3 += 1
                continue
            joined = " ".join(r)
            for ghost in repo_paths(joined):
                if not (ROOT / ghost).exists():
                    red.append(f"A1 §{key} 落点/引用路径不存在: {ghost}")
                    a1 += 1
            if key == "一" and any(m in joined for m in DEP_MARKERS):
                for ghost in repo_paths(r[2]):
                    if not (ROOT / ghost).exists():
                        red.append(f"A5 运行时依赖缺失: {ghost}")
                        a5 += 1

    # ── A2 · §二 必须挂真实台账
    for r in secs["二"]:
        if len(r) < 4 or r[0].startswith("素材"):
            continue
        found = TAIL_RE.findall(" ".join(r))
        if not found:
            red.append(f"A2 §二 没挂台账（不知道什么时候做）: {r[0][:60]}")
            a2 += 1
            continue
        for t in found:
            if t not in tails:
                red.append(f"A2 §二 台账号不存在于计划 §15: {t}（行：{r[0][:40]}）")
                a2 += 1

    # ── A4 · 用例号真实存在
    for key in ("一", "二", "三"):
        for r in secs[key]:
            for c in ACC_RE.findall(" ".join(r)):
                if accs and c not in accs:
                    red.append(f"A4 幽灵用例号: {c}（§{key} 行：{r[0][:40]}）")
                    a4 += 1

    rows_total = sum(len([r for r in secs[k] if not r[0].startswith("素材")]) for k in secs)
    info.append(f"索引条目 {rows_total} 条（§一 {len(secs['一'])} · §二 {len(secs['二'])} · §三 {len(secs['三'])}）")
    info.append(f"台账号 {len(tails)} 个 · 用例号 {len(accs)} 个（来自 PRD 基线）")

    if args.json:
        print(json.dumps({"red": red, "info": info}, ensure_ascii=False, indent=2))
    else:
        print("=" * 78)
        print(" 素材守卫 · asset_audit —— 「素材包里的实现，有没有真被用上 / 有没有真记着」")
        print("=" * 78)
        for line in info:
            print(" " + line)
        print()
        for code, name in (
            ("A1", "§一 已在用 · 落点路径真实存在"),
            ("A5", "运行时依赖 · 实际在仓"),
            ("A2", "§二 还没接 · 挂到真实台账"),
            ("A3", "每行栏位齐全"),
            ("A4", "引用的用例号真实存在"),
        ):
            n = {"A1": a1, "A2": a2, "A3": a3, "A4": a4, "A5": a5}[code]
            print(f"─ {code} · {name} —— {'✅ 无' if n == 0 else f'⛔ {n} 条'}")
        if red:
            print()
            print("必须修：")
            for r in red:
                print("  " + r)
        print()
        print(f"结论：**必须修 {len(red)}**" + ("（有红 ⇒ 非零退出）" if red else "（rc=0）"))

    return 1 if red else 0


if __name__ == "__main__":
    sys.exit(main())
