#!/usr/bin/env python
"""四态验收报表（绿 / 红 / 待建 / 未绑定）。

契约（`PRD/验收/README.md` §三）：
- 报表**按 `ACC-*` 分组**列出红 / 待建 / 未绑定；
- **有红即非零退出**（供流水线判停）；
- ⚠️ **「未绑定」必须单独成态并显示** —— 否则出现「没验过 = 通过」（本项目最贵的一类假绿）；
- 用例**全部判据点都绿**才算绿，未达标报「绿 X/Y」。

判据来源（唯一主人）：`.env` 的 `PRD_ACCEPTANCE_BASELINE` 指向的**只读快照**
`PRD/验收/验收基线.json`（D3：工程内**不留副本**）。

用法：
    python tools/acc_report.py                 # 人读报表
    python tools/acc_report.py -v              # 附判据全文
    python tools/acc_report.py --by-stage      # 按计划阶段分组（解析 PRD/05-任务分解.md）
    python tools/acc_report.py --json          # 机器可读
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT: Path = Path(__file__).resolve().parents[2]
DEFAULT_RESULTS: Path = REPO_ROOT / "artifacts" / "acc_results.json"

GREEN, RED, PENDING, UNBOUND = "绿", "红", "待建", "未绑定"
_ACC_RE = re.compile(r"ACC-[A-Z0-9]+(?:-[A-Z0-9*]+)*")
_WILDCARD = "*"


# --------------------------------------------------------------------------- io


def read_env_value(key: str, env_file: Path) -> str:
    if not env_file.exists():
        return ""
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        if k.strip() == key:
            return v.strip()
    return ""


def resolve_baseline(cli_value: str | None) -> Path:
    if cli_value:
        return Path(cli_value)
    from_env = read_env_value("PRD_ACCEPTANCE_BASELINE", REPO_ROOT / ".env")
    if not from_env:
        print(
            "错误：未指定判据基线。请在 .env 里配置 PRD_ACCEPTANCE_BASELINE，"
            "或用 --baseline 传入（D3：直读 PRD 快照，工程内不留副本）。",
            file=sys.stderr,
        )
        raise SystemExit(2)
    configured = Path(from_env)
    return configured if configured.is_absolute() else REPO_ROOT / configured


def load_json(path: Path) -> Any:
    if not path.exists():
        print(f"错误：文件不存在 —— {path}", file=sys.stderr)
        raise SystemExit(2)
    return json.loads(path.read_text(encoding="utf-8"))


# ----------------------------------------------------------------- state model


def collect_points(baseline: dict) -> dict[str, dict[str, dict]]:
    """→ {case: {point_id: point_dict}}（判据的唯一来源）。"""
    out: dict[str, dict[str, dict]] = {}
    for case, spec in (baseline.get("cases") or {}).items():
        points = spec.get("points") or []
        out[case] = {p["id"]: p for p in points}
    return out


def collect_pending(baseline: dict) -> dict[tuple[str, str], str]:
    """→ {(case, point): 档位说明}，来自 `_pending_assertions` 的 A / B 两档。"""
    pending: dict[tuple[str, str], str] = {}
    pa = baseline.get("_pending_assertions") or {}
    for tier, label in (
        ("A_waiting_for_impl", "A·待实现方建断言"),
        ("B_not_machine_assertable", "B·人工复核"),
    ):
        for item in ((pa.get(tier) or {}).get("items") or []):
            case, point = item.get("case"), item.get("point")
            if case and point:
                pending[(case, point)] = label
    return pending


def collect_boundary(baseline: dict) -> list[dict]:
    """C 档（口径侧登记）—— **不映射到判据点**，单独列出、不计入四态。"""
    pa = baseline.get("_pending_assertions") or {}
    return list(((pa.get("C_dev_boundary") or {}).get("items")) or [])


def build_states(
    points: dict[str, dict[str, dict]],
    pending: dict[tuple[str, str], str],
    results_payload: dict,
) -> dict[str, dict[str, str]]:
    """把绑定与运行结果折算成四态 → {case: {point: state}}。"""
    bindings: dict[str, list[list[str]]] = results_payload.get("bindings") or {}
    outcomes: dict[str, str] = results_payload.get("results") or {}

    verdict: dict[tuple[str, str], str] = {}
    for nodeid, binds in bindings.items():
        outcome = outcomes.get(nodeid)
        if outcome == "passed":
            state = GREEN
        elif outcome in ("failed", "error", "skipped"):
            state = RED
        else:  # 被 deselect / 未执行 —— 一律不当作通过
            state = RED
        for case, point in binds or []:
            key = (case, point)
            # 同一判据点被多个测试绑定时：有红即红，否则绿
            if verdict.get(key) == RED:
                continue
            verdict[key] = state

    states: dict[str, dict[str, str]] = {}
    for case, pts in points.items():
        states[case] = {}
        for pid in pts:
            key = (case, pid)
            if key in verdict:
                states[case][pid] = verdict[key]
            elif key in pending:
                states[case][pid] = PENDING
            else:
                states[case][pid] = UNBOUND
    return states


# --------------------------------------------------------------- stage parsing


def parse_stages(prd_root: Path, all_cases: list[str]) -> tuple[list[tuple[str, list[str], bool]], str]:
    """解析 `PRD/05-任务分解.md` §二 的垂直切片表。

    ⚠️ **此处刻意不硬编码阶段↔用例映射** —— 那会造出第二份副本（主人 = 该文件 §二）。
    解析失败时降级返回空表 + 说明，不猜。
    """
    path = prd_root / "PRD" / "05-任务分解.md"
    if not path.exists():
        return [], f"未找到 {path}"

    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    start = next((i for i, ln in enumerate(lines) if ln.startswith("## 二、垂直切片")), None)
    if start is None:
        return [], "未定位到「## 二、垂直切片」标题"

    rows: list[tuple[str, list[str], bool]] = []
    for ln in lines[start:]:
        if ln.startswith("### ") or ln.startswith("## 三"):
            break
        if not ln.strip().startswith("|"):
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cells) < 4 or set(cells[0]) <= set("-#: "):
            continue
        stage, cover_cell = cells[0].strip("`* "), cells[3]
        if not stage.isdigit():
            continue
        tokens = _ACC_RE.findall(cover_cell)
        if not tokens:
            continue
        resolved: list[str] = []
        wildcard = False
        for tok in tokens:
            if _WILDCARD in tok:
                wildcard = True
                prefix = tok.replace(_WILDCARD, "")
                # 通配形态（如 ACC-PAY-*）：按已定义的用例做前缀展开
                resolved.extend(c for c in all_cases if c.startswith(prefix))
            else:
                resolved.append(tok)
        rows.append((f"M{stage}", sorted(set(resolved)), wildcard))
    if not rows:
        return [], "切片表解析结果为空"
    return rows, ""


# --------------------------------------------------------------------- report


def _cell(points_by_case: dict[str, dict[str, dict]], case: str) -> str:
    return f"{case} [{(points_by_case.get(case) or {}).get('__req__', '')}]"


def render(args: argparse.Namespace) -> tuple[int, dict]:
    baseline_path = resolve_baseline(args.baseline)
    baseline = load_json(baseline_path)
    results_path = Path(args.results) if args.results else DEFAULT_RESULTS
    results_payload = load_json(results_path) if results_path.exists() else {}

    points = collect_points(baseline)
    pending = collect_pending(baseline)
    boundary = collect_boundary(baseline)
    states = build_states(points, pending, results_payload)

    meta: dict[str, Any] = {
        "baseline": str(baseline_path),
        "baseline_asof": baseline.get("asof", ""),
        "results": str(results_path),
        "results_generated_at": results_payload.get("generated_at", "(未跑过测试)"),
    }

    # --- 统计 ---
    tally = {GREEN: 0, RED: 0, PENDING: 0, UNBOUND: 0}
    per_case: dict[str, dict[str, int]] = {}
    reds: list[tuple[str, str, str]] = []
    pendings: list[tuple[str, str, str]] = []
    unbound: list[tuple[str, str, str]] = []

    for case, pts in states.items():
        counts = {GREEN: 0, RED: 0, PENDING: 0, UNBOUND: 0}
        for pid, state in pts.items():
            counts[state] += 1
            tally[state] += 1
            claim = points[case][pid].get("claim", "")
            if state == RED:
                reds.append((case, pid, claim))
            elif state == PENDING:
                pendings.append((case, pid, claim))
            elif state == UNBOUND:
                unbound.append((case, pid, claim))
        per_case[case] = counts

    total = sum(tally.values())

    # --- 输出 ---
    out = sys.stdout
    line = "=" * 78
    print(line)
    print(" 验收报表 · 材料报表自动化工作台")
    print(f" 判据基线 asof: {meta['baseline_asof']}    结果生成于: {meta['results_generated_at']}")
    print(line)
    print(
        f"判据点合计 {total}    "
        f"{GREEN} {tally[GREEN]} · {RED} {tally[RED]} · "
        f"{PENDING} {tally[PENDING]} · {UNBOUND} {tally[UNBOUND]}"
    )
    print()

    print("按用例")
    print("-" * 78)
    for case in sorted(per_case):
        c = per_case[case]
        spec = (baseline.get("cases") or {}).get(case) or {}
        mark = ""
        if c[RED]:
            mark = "  ← 红"
        elif c[PENDING] + c[UNBOUND] == 0 and c[GREEN]:
            mark = "  ✅"
        detail = " · ".join(
            f"{k} {c[k]}" for k in (GREEN, RED, PENDING, UNBOUND) if c[k]
        )
        print(f"  {case:<28} [{spec.get('req', '—'):<9}] 绿 {c[GREEN]}/{sum(c.values()):<3} {detail}{mark}")
    print()

    if reds:
        print(f"{RED}（必须修 —— 有红即非零退出）")
        print("-" * 78)
        for case, pid, claim in reds:
            print(f"  {case} / {pid}  {claim if args.verbose else ''}".rstrip())
        print()

    print(f"{UNBOUND}（还没验过 —— ⚠️ 不等于通过）")
    print("-" * 78)
    if unbound:
        for case, pid, claim in unbound:
            print(f"  {case} / {pid}  {claim if args.verbose else ''}".rstrip())
    else:
        print("  （无）")
    print()

    print(f"{PENDING}（判据已定、断言未建 —— 登记在基线的待建区）")
    print("-" * 78)
    if pendings:
        for case, pid, claim in pendings:
            tier = pending.get((case, pid), "")
            print(f"  {case} / {pid}  [{tier}]  {claim if args.verbose else ''}".rstrip())
    else:
        print("  （无）")
    print()

    if boundary:
        print("口径侧登记（C 档 · 不映射判据点 · 不计入四态）")
        print("-" * 78)
        for item in boundary:
            print(f"  {item.get('dev', ''):<12} {item.get('status', ''):<8} {item.get('note', '') if args.verbose else ''}".rstrip())
        print()

    stage_rows: list[tuple[str, list[str], bool]] = []
    stage_note = ""
    if args.by_stage:
        stage_rows, stage_note = parse_stages(baseline_path.parents[2], sorted(per_case))
        print("按计划阶段（来源：PRD/05-任务分解.md §二 · 解析所得）")
        print("-" * 78)
        if stage_rows:
            for stage, cases, wildcard in stage_rows:
                green = sum(per_case.get(c, {}).get(GREEN, 0) for c in cases)
                tot = sum(sum(per_case.get(c, {}).values()) for c in cases)
                tag = "（含通配展开）" if wildcard else ""
                print(f"  {stage:<4} 绿 {green}/{tot:<4} {', '.join(cases)}{tag}")
            print(
                "  ℹ️ 解析规则：只认该行「**完成定义**」列里出现的编号 —— 若那一格里还提到**别的用例编号**"
                "（哪怕写在「除外 / 不在本片」的括号里），会被一并算进本片 ⇒ **别在该格写其他切片的编号**。"
            )
            if any(w for _, _, w in stage_rows):
                print(
                    "  ⚠️ 通配（如 `ACC-PAY-*`）是按**前缀**展开的，可能包含 PRD §二 明确"
                    "「除外」的那一条（该排除用中文描述、无编号，无法自动识别）"
                    "⇒ **以 `PRD/05-任务分解.md` §二 原文为准**。"
                )
        else:
            print(f"  解析失败：{stage_note}")
        print()

    meta.update(
        {
            "tally": tally,
            "total": total,
            "per_case": per_case,
            "red": [{"case": c, "point": p, "claim": cl} for c, p, cl in reds],
            "unbound": [{"case": c, "point": p} for c, p, _ in unbound],
            "pending": [{"case": c, "point": p, "tier": pending.get((c, p), "")} for c, p, _ in pendings],
            "boundary": boundary,
            "stages": [{"stage": s, "cases": cs, "wildcard": w} for s, cs, w in stage_rows],
        }
    )

    exit_code = 1 if tally[RED] else 0
    print(line)
    print(
        f"退出码 {exit_code}"
        + ("（有红）" if exit_code else "（无红）")
        + f"    ⚠️ 未绑定 {tally[UNBOUND]} 条不等于通过"
    )
    print(line)
    return exit_code, meta


def main() -> int:
    parser = argparse.ArgumentParser(description="四态验收报表")
    parser.add_argument("--baseline", help="判据基线 json（默认取 .env 的 PRD_ACCEPTANCE_BASELINE）")
    parser.add_argument("--results", help=f"测试结果 json（默认 {DEFAULT_RESULTS}）")
    parser.add_argument("-v", "--verbose", action="store_true", help="附判据全文")
    parser.add_argument("--by-stage", action="store_true", help="按计划阶段分组（解析 PRD/05-任务分解.md）")
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    parser.add_argument("--json-out", help="把 JSON 写入指定文件")
    args = parser.parse_args()

    if args.json or args.json_out:
        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            exit_code, meta = render(args)
        payload = json.dumps(meta, ensure_ascii=False, indent=2)
        if args.json_out:
            Path(args.json_out).write_text(payload, encoding="utf-8")
        if args.json:
            print(payload)
        else:
            print(buf.getvalue())
        return exit_code

    exit_code, _ = render(args)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
