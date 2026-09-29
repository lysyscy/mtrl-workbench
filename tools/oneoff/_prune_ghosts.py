"""清 `TAIL-149`：删掉 `tools/ui_parity_expected.txt` 里的**幽灵登记行**（登记了、当前却无对应漂移）。

## 纪律（⛔ 别改）

- ⭐ **判定原样复现**：直接 `import ui_parity`，用**它的**原语（`PROTO` / `read_lines` / `slices` /
  `read_shell` / `load_expected` / `fp`）与它那段 5 行幽灵判定 ⇒ **⛔ 不另写第二套判定**
  （否则"脚本删的行"与"尺子报的幽灵"会不一致）。
- ⛔ **只删条目行**（`<页> <指纹> [备注]`），**注释行一行不动** —— 本仓规矩：⛔ 别冲掉旁边的理由注释
  （`# ⭐ <日期> 新增登记 N 条` 是**批次留痕**；`# ⭐⭐ …` 是**理由**）。
- ⛔ **不整份重写**（只删行，其余字节不动）。
- `--check` 为 dry-run。

跑法：`backend/.venv/Scripts/python.exe -X utf8 tools/oneoff/_prune_ghosts.py --check`
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "audit"))
import ui_parity as U   # noqa: E402  ← 壳一致性核对器（判定与它同源）


def ghost_keys() -> set[tuple[str, str]]:
    """当前**幽灵登记**的 `(页, 指纹)` 集合 —— 复现 `ui_parity.main()` 里那一段。"""
    p_views = U.slices(U.read_lines(U.PROTO))
    shell_lines = U.read_shell().replace("\r\n", "\n").split("\n")
    s_views = U.slices(shell_lines)
    exp = U.load_expected()
    now: dict[str, set[str]] = {}
    for key, plines in p_views.items():
        slines = s_views.get(key)
        if slines is None:
            continue
        for i in range(max(len(plines), len(slines))):
            a = plines[i].rstrip() if i < len(plines) else "<无此行>"
            b = slines[i].rstrip() if i < len(slines) else "<无此行>"
            if a != b:
                now.setdefault(key, set()).add(U.fp(a + "||" + b))
    return {(k, f) for k, fs in exp.items() for f in fs if f not in now.get(k, set())}


def main() -> int:
    ap = argparse.ArgumentParser(description="清 TAIL-149：删幽灵登记行")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()

    ghosts = ghost_keys()
    raw = U.EXPECTED.read_text(encoding="utf-8", newline="")
    lines = raw.split("\n")
    kill = set()
    for i, ln in enumerate(lines):
        s = ln.strip()
        if not s or s.startswith("#"):
            continue                                    # ⛔ 注释与空行一律不动
        parts = s.split()
        if len(parts) >= 2 and (parts[0], parts[1]) in ghosts:
            kill.add(i)

    entries = sum(1 for ln in lines if ln.strip() and not ln.strip().startswith("#"))
    comments = sum(1 for ln in lines if ln.strip().startswith("#"))
    print(f"幽灵登记 {len(ghosts)} 条 · 登记簿 {len(lines)} 行（条目 {entries} · 注释 {comments}）")
    print(f"⇒ 将删 {len(kill)} 行 · 删后剩 {len(lines) - len(kill)} 行（条目 {entries - len(kill)} · 注释 {comments} 保持）")
    if a.check:
        print("（--check：未写入）")
        return 0

    out = [ln for i, ln in enumerate(lines) if i not in kill]
    U.EXPECTED.write_text("\n".join(out), encoding="utf-8", newline="")
    print(f"⇒ 已写入 {U.EXPECTED.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
