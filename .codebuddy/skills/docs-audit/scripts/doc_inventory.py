#!/usr/bin/env python
"""文档盘点器（**只读**）—— 分布 / 超预算 / 重复 / 过短。

用法：
    python .codebuddy/skills/docs-audit/scripts/doc_inventory.py            # 人读报告
    python .codebuddy/skills/docs-audit/scripts/doc_inventory.py --json     # 机器可读
    python .codebuddy/skills/docs-audit/scripts/doc_inventory.py --top 20   # 最大件列表长度

口径（⛔ 别改这几条）：
  · 行数**真值** = `len(text.splitlines())` —— ⛔ 别用 PowerShell `Get-Content`（默认不按 UTF-8 解码，
    实测同一文件 69 vs 198 行；本仓 `README.md` §八 有记录）。
  · 预算**不手抄**：从 `tools/audit/audit_meta.py` 的 `DOC_BUDGETS` 读（读不到就跳过并提示）
    —— 手抄的数字必漂（`T10` 报的是真值）。
  · ⛔ 本件**只读**：不写任何文件；⛔ 它**不是尺子**（不进收工闸门、不判红、不改任何登记）。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

SKIP_DIRS = {"node_modules", ".venv", ".git", "__pycache__", ".pytest_cache",
             ".mypy_cache", ".ruff_cache", ".idea"}
SHORT_LINES = 5          # 过短阈值（件 < 此行数 ⇒ 列出来问一句"它还有用吗"）
DUP_MIN_LINES = 5        # 重复检测的最小体量（太短的文件撞 hash 无意义）


def repo_root() -> Path:
    here = Path(__file__).resolve()
    for cand in (here, *here.parents):
        if (cand / "tools" / "audit" / "doc_audit.py").exists() and (cand / ".codebuddy").is_dir():
            return cand
    raise SystemExit("找不到仓库根（期望含 tools/audit/doc_audit.py 与 .codebuddy/）")


def iter_md(root: Path):
    for f in sorted(root.rglob("*.md")):
        if any(part in SKIP_DIRS for part in f.parts):
            continue
        if f.is_file():
            yield f


def group_key(rel: str) -> str:
    """分组键：`.codebuddy/<二级>` 单独成组（backups / memory / plans / work 各算一层），其余取顶层目录。"""
    parts = rel.split("/")
    if len(parts) >= 2 and parts[0] in (".codebuddy", ".codebuddy"):
        return "/".join(parts[:2])
    return parts[0] if len(parts) > 1 else "(根)"


def load_budgets(root: Path):
    sys.path.insert(0, str(root / "tools" / "audit"))
    try:
        from audit_meta import DOC_BUDGETS                        # noqa: PLC0415
        return list(DOC_BUDGETS), None
    except Exception as exc:                                      # noqa: BLE001
        return [], f"（跳过：读不到 `audit_meta.DOC_BUDGETS` —— {exc}）"


def main() -> int:
    ap = argparse.ArgumentParser(description="文档盘点（只读）")
    ap.add_argument("--json", action="store_true", help="机器可读输出")
    ap.add_argument("--top", type=int, default=10, help="最大件列表长度（默认 10）")
    ap.add_argument("--budgets", action="store_true", help="把登记册里**每份**预算档的现值都列出来（默认只列超的）")
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8")                  # 中文控制台兜底
    except Exception:                                             # noqa: BLE001
        pass

    root = repo_root()
    rows = []
    for f in iter_md(root):
        raw = f.read_bytes()
        text = raw.decode("utf-8", errors="replace")
        rows.append({
            "rel": str(f.relative_to(root)).replace("\\", "/"),
            "lines": len(text.splitlines()),
            "bytes": len(raw),
            "sha1": hashlib.sha1(raw).hexdigest(),
        })

    total = {"files": len(rows), "lines": sum(r["lines"] for r in rows),
             "bytes": sum(r["bytes"] for r in rows)}

    groups: dict[str, dict] = defaultdict(lambda: {"files": 0, "lines": 0})
    for r in rows:
        g = groups[group_key(r["rel"])]
        g["files"] += 1
        g["lines"] += r["lines"]
    by_group = [{"group": k, **v} for k, v in sorted(groups.items(), key=lambda kv: -kv[1]["lines"])]

    biggest = sorted(rows, key=lambda r: -r["lines"])[: max(args.top, 0)]

    budgets, budget_note = load_budgets(root)
    all_budgets, over = [], []
    for rel, budget, tier in budgets:
        p = root / rel
        if not p.exists():
            row = {"rel": rel, "budget": budget, "tier": tier, "lines": None, "over": None}
        else:
            n = len(p.read_text(encoding="utf-8", errors="replace").splitlines())
            row = {"rel": rel, "budget": budget, "tier": tier, "lines": n,
                   "over": (n - budget) if n > budget else 0}
        all_budgets.append(row)
        if row["lines"] is None or row["over"]:
            over.append(row)

    dup_map: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if r["lines"] >= DUP_MIN_LINES:
            dup_map[r["sha1"]].append(r)
    dups = [{"lines": v[0]["lines"], "files": [x["rel"] for x in v]}
            for v in dup_map.values() if len(v) >= 2]
    dups.sort(key=lambda d: (-d["lines"], -len(d["files"])))

    shorts = [{"rel": r["rel"], "lines": r["lines"]} for r in rows if r["lines"] < SHORT_LINES]

    if args.json:
        print(json.dumps({"total": total, "by_group": by_group, "biggest": biggest,
                          "budgets": all_budgets, "over_budget": over,
                          "duplicates": dups, "short": shorts,
                          "budget_note": budget_note}, ensure_ascii=False, indent=2))
        return 0

    w = 78
    print("=" * w)
    print(f" 文档盘点（只读 · 真值行数 = len(splitlines())）  根 = {root}")
    print("=" * w)
    print(f" 总量：{total['files']} 件 · {total['lines']} 行 · {total['bytes'] / 1024 / 1024:.1f} MB")
    print(f"\n--- 按目录（按行数降序）---")
    for g in by_group:
        share = (g["lines"] / total["lines"] * 100) if total["lines"] else 0
        print(f" {g['group']:<28} {g['files']:>4} 件 · {g['lines']:>7} 行 · {share:>5.1f}%")
    print(f"\n--- 最大 {len(biggest)} 件 ---")
    for r in biggest:
        print(f" {r['lines']:>7} 行  {r['rel']}")
    print(f"\n--- 超预算（`T10` 登记册里的 inject/must 档）{budget_note or ''} ---")
    if budgets and not over:
        print(" （无）")
    for o in over:
        if o["lines"] is None:
            print(f" ⚠️ 登记了但**文件不存在**：{o['rel']}（预算 {o['budget']}）")
        else:
            print(f" {o['lines']:>7} 行 / 预算 {o['budget']:>5}（超 {o['over']}）· {o['tier']:<6} {o['rel']}")
    if args.budgets:
        print(f"\n--- 登记册全量（现值 / 预算）---")
        for b in all_budgets:
            cur = "文件不存在" if b["lines"] is None else f"{b['lines']:>7} 行"
            print(f" {cur} / {b['budget']:>5} · {b['tier']:<6} {b['rel']}")
    print(f"\n--- 同一内容多份（sha1 相同 · ≥{DUP_MIN_LINES} 行）---")
    if not dups:
        print(" （无）")
    for d in dups[:10]:
        print(f" {d['lines']:>7} 行 × {len(d['files'])} 份：")
        for rel in d["files"][:4]:
            print(f"           {rel}")
        if len(d["files"]) > 4:
            print(f"           … 另 {len(d['files']) - 4} 份")
    print(f"\n--- 过短（<{SHORT_LINES} 行 ⇒ 问一句「它还有用吗」）---")
    if not shorts:
        print(" （无）")
    for s in shorts:
        print(f" {s['lines']:>3} 行  {s['rel']}")
    print("\n" + "-" * w)
    print(" ⚠️ 本件只盘点、不判红；『必须修』由 `tools/audit/doc_audit.py` 等尺子说了算。")
    print(" ⭐ 判读顺序：先看占比（哪一层在膨胀）⇒ 再看超预算 ⇒ 最后看重复。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
