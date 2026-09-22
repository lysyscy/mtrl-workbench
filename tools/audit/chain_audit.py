"""**链路对账**（chain_audit）—— 查「**文档里写明的那一步，代码里到底有没有落点**」。

**为什么有它**（2026-09-17 用户质疑「为啥出这个问题？是不是没排计划？」→ 反思的结论）：
    不是没排计划，是**计划的「完成定义」只到零件、没到链路**：
    · 判据（`ACC-*`）**全部钉在模块内的纯函数**上 ⇒ 零件越做越对
    · `doc_audit` 只查「能力行有没有用例号 / 口径节有没有被 cover」⇒ **不查"业务句子有没有落地"**
    · 真机验证只看「条数对不对 / 有没有报错」⇒ **不查"这一批为什么是这些行"**
    ⇒ **接缝（模块之间）没有任何尺子**，于是同一天暴露 3 个接缝缺陷：
      剔除判定与归属校验的**顺序**、链路 C 的**弹窗**、链路 A 的**触发方**。

**口径（本文件即定义）**：
- ⭐ **契约原文**（`PRD/05-任务分解.md` §二）：「**垂直切片（每片 = 一条需求能端到端跑通）**」——
  **切片本来就是"链路"**。执行时被降解成「该切片名下 `ACC-*` 全绿」⇒ 链路中间环节没人守。
  本工具 = 把「端到端」落成**可机读的度量单位**。
- **真源** = `tools/chain_sources.txt` 注册的**每条链路各一节**（不是单一文档的一节）。
- **认领表** = `tools/chain_expected.txt`（人认领；每条给「文档锚 ＋ 落点 ＋ 判据 ＋ 状态」）。
- 本工具**不解析树形结构** —— 靠**文档锚**（文档里的一段原文）双向校验，文档一改就报红/黄，**不会静默过期**。

**六把尺子**
| 代号 | 检查 | 判据 |
|---|---|---|
| `C1` | 认领行栏位齐全（链路/分支/文档锚/落点/判据/状态）· 且**链路代码已在 `chain_sources.txt` 注册** | 缺栏 / 未注册 ⇒ **红** |
| `C2` | **文档锚**在该链路的真源文档里找得到 | 找不到 ⇒ **红**（文档改了 / 记错了） |
| `C3` | **落点真实存在**（`路径` 或 `路径::名字`） | 幽灵落点 ⇒ **红**（"以为接在别处"） |
| `C4` | **判据**真实存在 / 或明确声明 | 幽灵用例号 ⇒ **红**；`缺：…` ⇒ **红**（这条分支就是缺口）；`不可断言:…` ⇒ 黄 |
| `C5` | **状态** = 已接 / 接线缺 / 缺 / 形态不同 | `接线缺` `缺` ⇒ **红**；`形态不同` ⇒ **黄（待追认）** |
| `C6` | ⭐ **文档覆盖哨**：各真源节代码块里的分支标记行，有没有认领行认领 | 没认领 ⇒ **黄**（提示"文档里有这条、表里没有"） |

用法：
    python tools/chain_audit.py                    # 人读（有红即非零退出）
    python tools/chain_audit.py --json             # 机读
    python tools/chain_audit.py --chain P1         # 只看某条链路
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCES = ROOT / "tools" / "chain_sources.txt"
EXPECTED = ROOT / "tools" / "chain_expected.txt"
ENV = ROOT / ".env"

RED_STATES = {"接线缺", "缺"}
YELLOW_STATES = {"形态不同"}
OK_STATES = {"已接"}
ALL_STATES = RED_STATES | YELLOW_STATES | OK_STATES

TREE_CHARS = "│├└─ \t"
MARKER_RE = re.compile(r"^[①②③④⑤⑥⑦⑧⑨]|^[a-z]\.")


def norm(s: str) -> str:
    """归一化：去空白、去 markdown 强调符与代码符 —— 用于「文档锚」匹配。"""
    return re.sub(r"[\s*`]+", "", s or "")


def load_sources() -> tuple[list[dict], dict[str, dict]]:
    """读链路真源注册表 ⇒ (有序列表, {链路代码: 行})。"""
    rows: list[dict] = []
    if not SOURCES.exists():
        return rows, {}
    for i, raw in enumerate(SOURCES.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        p = [x.strip() for x in line.split("|")]
        rows.append({"lineno": i, "chain": p[0] if p else "", "name": p[1] if len(p) > 1 else "",
                     "doc": p[2] if len(p) > 2 else "", "start": p[3] if len(p) > 3 else "",
                     "end": p[4] if len(p) > 4 else ""})
    return rows, {r["chain"]: r for r in rows}


def load_claims() -> list[dict]:
    rows: list[dict] = []
    for i, raw in enumerate(EXPECTED.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        rows.append({"lineno": i, "chain": parts[0] if parts else "",
                     "branch": parts[1] if len(parts) > 1 else "",
                     "anchor": parts[2] if len(parts) > 2 else "",
                     "target": parts[3] if len(parts) > 3 else "",
                     "case": parts[4] if len(parts) > 4 else "",
                     "state": parts[5] if len(parts) > 5 else "",
                     "cells": parts})
    return rows


_FULL_CACHE: dict[str, str] = {}


def doc_full(path: str) -> str:
    """真源文档全文（归一化）。不存在 ⇒ 空串（由调用方报红）。"""
    if path not in _FULL_CACHE:
        p = Path(path)
        _FULL_CACHE[path] = norm(p.read_text(encoding="utf-8")) if p.exists() else ""
    return _FULL_CACHE[path]


def section_markers(doc: str, start: str, end: str) -> list[str]:
    """节内**代码块**里以 ①/②/… 或 `a.` 开头的分支行。"""
    p = Path(doc)
    if not p.exists():
        return []
    lines = p.read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")
    try:
        a = next(i for i, l in enumerate(lines) if l.startswith(start))
        b = next(i for i, l in enumerate(lines) if i > a and l.startswith(end))
    except StopIteration:
        return []
    out: list[str] = []
    in_fence = False
    for ln in lines[a:b]:
        if ln.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            continue
        text = ln.lstrip(TREE_CHARS)
        if MARKER_RE.match(text) and len(norm(text)) >= 6:
            out.append(text.strip())
    return out


def baseline_ids() -> set[str]:
    if not ENV.exists():
        return set()
    url = None
    for line in ENV.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("PRD_ACCEPTANCE_BASELINE"):
            url = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not url:
        return set()
    p = Path(url)
    if not p.exists():
        return set()
    data = json.loads(p.read_text(encoding="utf-8"))
    cases = data.get("cases", {})
    if isinstance(cases, dict):
        return set(cases)
    return {c.get("id", "") for c in cases if isinstance(c, dict)}


def check_target(target: str) -> str | None:
    if not target or target == "—":
        return None
    if "::" in target:
        path, name = target.split("::", 1)
    else:
        path, name = target, ""
    f = ROOT / path
    if not f.exists():
        return f"落点文件不存在：{path}"
    if name and name not in f.read_text(encoding="utf-8"):
        return f"落点名字在文件里找不到：{path}::{name}"
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="链路对账")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--chain", default="", help="只看某条链路（如 P1）")
    args = ap.parse_args()

    if not SOURCES.exists():
        print(f"⛔ 找不到真源注册表：{SOURCES}")
        return 1
    if not EXPECTED.exists():
        print(f"⛔ 找不到认领表：{EXPECTED}")
        return 1

    src_rows, chain2src = load_sources()
    claims = load_claims()
    if args.chain:
        claims = [c for c in claims if c["chain"] == args.chain]
    ids = baseline_ids()
    red: list[str] = []
    yellow: list[str] = []

    for c in claims:
        tag = f"{c['chain']}｜{c['branch'][:34]}"
        if len(c["cells"]) < 6 or any(not x for x in c["cells"][:6]):
            red.append(f"C1 栏位不全：{tag}")
            continue
        if c["chain"] not in chain2src:
            red.append(f"C1 链路代码没在 chain_sources.txt 注册：{c['chain']}（{c['branch'][:24]}）")
            continue
        if c["state"] not in ALL_STATES:
            red.append(f"C5 状态不合法（{c['state']}）：{tag}")
            continue
        src = chain2src[c["chain"]]
        full = doc_full(src["doc"])
        if not full:
            red.append(f"C2 真源文档不存在：{src['doc']}")
        elif norm(c["anchor"]) not in full:
            red.append(f"C2 文档锚在真源里找不到 ⇒ 文档可能改了：{tag}（锚：{c['anchor'][:30]}）")
        if c["target"] == "—":
            if c["state"] in OK_STATES | RED_STATES - {"缺"}:
                red.append(f"C3 没写落点却说「{c['state']}」：{tag}")
        else:
            err = check_target(c["target"])
            if err:
                red.append(f"C3 {err}：{tag}")
        case = c["case"]
        is_gap = case.startswith("缺")
        if is_gap:
            red.append(f"C4 这条分支**就是缺口**（需补判据）：{tag}")
        elif case.startswith("不可断言"):
            yellow.append(f"C4 声明不可断言：{tag} —— {case}")
        elif ids and case not in ids:
            red.append(f"C4 幽灵用例号 {case}：{tag}")
        # C5：状态为「缺」且 C4 已报过 ⇒ 不重复报（同一条事实只报一次）
        if c["state"] in RED_STATES and not (c["state"] == "缺" and is_gap):
            red.append(f"C5 状态={c['state']} ⇒ 这条分支还没落地：{tag}")
        elif c["state"] in YELLOW_STATES:
            yellow.append(f"C5 形态与文档不同（待追认）：{tag}")

    # C6 · 文档覆盖哨（按**节**去重，同一节被多条链路共用时只算一次）
    unclaimed: list[str] = []
    seen_sections: set[tuple[str, str, str]] = set()
    section_ok = 0
    for s in src_rows:
        key = (s["doc"], s["start"], s["end"])
        if key in seen_sections:
            continue
        seen_sections.add(key)
        markers = section_markers(s["doc"], s["start"], s["end"])
        if not markers:
            continue
        owners = [r["chain"] for r in src_rows if (r["doc"], r["start"], r["end"]) == key]
        miss = [m for m in markers
                if not any(norm(c["anchor"]) in norm(m) or norm(m) in norm(c["anchor"])
                           for c in load_claims() if c["chain"] in owners)]
        if miss:
            unclaimed.append(f"[{'/'.join(owners)}] {s['start'].strip()} 有 "
                             f"{len(miss)}/{len(markers)} 条分支**没有任何认领行**")
            for m in miss[:4]:
                unclaimed.append(f"      · {m[:62]}")
        else:
            section_ok += 1

    ok = len([c for c in claims if c["state"] in OK_STATES])

    # 按链路汇总
    summary: list[dict] = []
    for s in src_rows:
        rows = [c for c in claims if c["chain"] == s["chain"]]
        summary.append({"chain": s["chain"], "name": s["name"], "total": len(rows),
                        "ok": len([c for c in rows if c["state"] in OK_STATES]),
                        "red": len([c for c in rows if c["state"] in RED_STATES]),
                        "yellow": len([c for c in rows if c["state"] in YELLOW_STATES])})

    if args.json:
        print(json.dumps({"red": red, "yellow": yellow, "unclaimed": unclaimed,
                          "ok": ok, "total": len(claims), "summary": summary},
                         ensure_ascii=False, indent=2))
        return 1 if red else 0

    print("=" * 84)
    print(" 链路对账 · chain_audit —— 「文档里写明的那一步，代码里有没有落点」")
    print(" 契约原文：prd 05-任务分解 §二「垂直切片（每片 = 一条需求能端到端跑通）」")
    print("=" * 84)
    print(f" 真源：chain_sources.txt（{len(src_rows)} 条链路）   认领：{len(claims)} 条（已接 {ok}）")
    print()
    print("─ 全站链路总览")
    for s in summary:
        if not s["total"]:
            print(f"   ⬜ {s['chain']:<3} {s['name'][:38]:<40} **本链路没有任何认领行**")
            continue
        mark = "✅" if s["red"] == 0 and s["yellow"] == 0 else ("🟡" if s["red"] == 0 else "⛔")
        print(f"   {mark} {s['chain']:<3} {s['name'][:38]:<40} 已接 {s['ok']}/{s['total']}"
              f" · 红 {s['red']} · 黄 {s['yellow']}")
    print()
    for chain in [s["chain"] for s in src_rows]:
        rows = [c for c in claims if c["chain"] == chain]
        if not rows:
            continue
        print(f"─ 链路 {chain}（{len(rows)} 条）")
        for c in rows:
            mark = "✅" if c["state"] in OK_STATES else ("🟡" if c["state"] in YELLOW_STATES else "⛔")
            print(f"   {mark} {c['branch'][:52]:<54} {c['state']}")
    print()
    print(f"─ 结果：**已接 {ok}／{len(claims)}** · 黄（待追认）{len(yellow)} · 红 **{len(red)}**")
    if yellow:
        print()
        print("黄（形态与文档不同 / 不可断言 —— **需你追认**，但不阻断）：")
        for y in yellow:
            print("  " + y)
    if unclaimed:
        print()
        print(f"⚠️ C6 覆盖哨：真源里有分支、认领表里没有（{len(unclaimed)} 段）—— 请核：")
        for u in unclaimed:
            print(f"  {u}" if u.startswith("      ") else "  · " + u)
    if red:
        print()
        print("红（必须修）：")
        for r in red:
            print("  " + r)
    print()
    print(f"结论：**必须修 {len(red)}**" + ("（有红 ⇒ 非零退出）" if red else "（rc=0）"))
    return 1 if red else 0


if __name__ == "__main__":
    sys.exit(main())
