"""**链路对账**（chain_audit）—— 查「**文档里写明的那一步，代码里到底有没有落点**」。

**为什么有它**（2026-09-17 用户质疑「为啥出这个问题？是不是没排计划？」→ 反思的结论）：
    不是没排计划，是**计划的「完成定义」只到零件、没到链路**：
    · 判据（`ACC-*`）**全部钉在模块内的纯函数**上 ⇒ 零件越做越对
    · `doc_audit` 只查「能力行有没有用例号 / 口径节有没有被 cover」⇒ **不查"业务句子有没有落地"**
    · 真机验证只看「条数对不对 / 有没有报错」⇒ **不查"这一批为什么是这些行"**
    ⇒ **接缝（模块之间）没有任何尺子**，于是同一天暴露 3 个接缝缺陷：
      剔除判定与归属校验的**顺序**、链路 C 的**弹窗**、链路 A 的**触发方**。

**口径（本文件即定义）**：
- **真源** = 交付面《全自动建档-实施计划》**§三**（链路 A / B / C 的每个分支）。
- **认领表** = `tools/chain_expected.txt`（人认领；每条给「文档锚 ＋ 落点 ＋ 判据 ＋ 状态」）。
- 本工具**不解析树形结构** —— 靠**文档锚**（文档里的一段原文）双向校验，文档一改就报红/黄，**不会静默过期**。

**五把尺子**
| 代号 | 检查 | 判据 |
|---|---|---|
| `C1` | 认领行栏位齐全（链路/分支/文档锚/落点/判据/状态） | 缺栏 ⇒ **红** |
| `C2` | **文档锚**在真源里找得到 | 找不到 ⇒ **红**（文档改了 / 记错了） |
| `C3` | **落点真实存在**（`路径` 或 `路径::名字`） | 幽灵落点 ⇒ **红**（"以为接在别处"） |
| `C4` | **判据**真实存在 / 或明确声明 | 幽灵用例号 ⇒ **红**；`缺：…` ⇒ **红**（这条分支就是缺口）；`不可断言:…` ⇒ 黄 |
| `C5` | **状态** = 已接 / 接线缺 / 缺 / 形态不同 | `接线缺` `缺` ⇒ **红**；`形态不同` ⇒ **黄（待追认）** |
| `C6` | ⭐ **文档覆盖哨**：§三 里的编号/字母标记行，有没有认领行认领 | 没认领 ⇒ **黄**（提示"文档里有这条、表里没有"） |

用法：
    python tools/chain_audit.py            # 人读（有红即非零退出）
    python tools/chain_audit.py --json     # 机读
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = Path(r"D:\工作\AI\PRD编写夹 - Workbuddy专用\全自动建档-实施计划.md")
EXPECTED = ROOT / "tools" / "chain_expected.txt"
ENV = ROOT / ".env"

RED_STATES = {"接线缺", "缺"}
YELLOW_STATES = {"形态不同"}
OK_STATES = {"已接"}
ALL_STATES = RED_STATES | YELLOW_STATES | OK_STATES

TREE_CHARS = "│├└─ \t"
MARKER_RE = re.compile(r"^[①②③④⑤]|^[a-z]\.")


def norm(s: str) -> str:
    """归一化：去空白、去 markdown 强调符与代码符 —— 用于「文档锚」匹配。"""
    return re.sub(r"[\s*`]+", "", s or "")


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


def doc_text() -> tuple[str, list[str]]:
    """返回 (全文归一化, §三 代码块里的分支标记行列表)。"""
    lines = DOC.read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")
    try:
        a = next(i for i, l in enumerate(lines) if l.startswith("## 三、"))
        b = next(i for i, l in enumerate(lines) if l.startswith("## 四、"))
    except StopIteration:
        return "\n".join(lines).join([]), []
    section = lines[a:b]
    markers: list[str] = []
    in_fence = False
    for ln in section:
        if ln.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            continue
        text = ln.lstrip(TREE_CHARS)
        if MARKER_RE.match(text) and len(norm(text)) >= 6:
            markers.append(text.strip())
    return norm("\n".join(lines)), markers


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
    args = ap.parse_args()

    if not DOC.exists():
        print(f"⛔ 找不到真源：{DOC}")
        return 1
    if not EXPECTED.exists():
        print(f"⛔ 找不到认领表：{EXPECTED}")
        return 1

    claims = load_claims()
    full, markers = doc_text()
    ids = baseline_ids()
    red: list[str] = []
    yellow: list[str] = []

    for c in claims:
        tag = f"{c['chain']}｜{c['branch'][:34]}"
        if len(c["cells"]) < 6 or any(not x for x in c["cells"][:6]):
            red.append(f"C1 栏位不全：{tag}")
            continue
        if c["state"] not in ALL_STATES:
            red.append(f"C5 状态不合法（{c['state']}）：{tag}")
            continue
        if norm(c["anchor"]) not in full:
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

    # C6 · 文档覆盖哨
    unclaimed: list[str] = []
    for m in markers:
        nm = norm(m)
        if not any(norm(c["anchor"]) in nm or nm in norm(c["anchor"]) for c in claims):
            unclaimed.append(m)

    ok = len([c for c in claims if c["state"] in OK_STATES])

    if args.json:
        print(json.dumps({"red": red, "yellow": yellow, "unclaimed": unclaimed,
                          "ok": ok, "total": len(claims)}, ensure_ascii=False, indent=2))
        return 1 if red else 0

    print("=" * 80)
    print(" 链路对账 · chain_audit —— 「文档里写明的那一步，代码里有没有落点」")
    print("=" * 80)
    print(f" 真源：{DOC.name} §三   认领：{len(claims)} 条（已接 {ok}）")
    print()
    for chain in ("A", "B", "C"):
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
        print("黄（形态与文档不同 —— **需你追认**，但不阻断）：")
        for y in yellow:
            print("  " + y)
    if unclaimed:
        print()
        print(f"⚠️ C6 文档里有、认领表里没有的分支行（{len(unclaimed)}）—— 请核：")
        for u in unclaimed[:12]:
            print(f"  · {u[:64]}")
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
