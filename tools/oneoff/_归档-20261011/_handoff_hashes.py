"""把 §13.6 交接材料里那行「分支 / 提交位置」改准（提交之后必做 —— ⛔ 否则下次会话以为欠着提交）。

⚠️ 为什么值得单独一条提交：上一轮就是**先提交了、却留着「提交待办」那句话** ⇒ 下个会话照着交接材料
会以为还有东西没提交（"文档真话"那一类）。⇒ 提交完**同批**把这行刷新。

锚点用**行首前缀**（`| **分支 / 提交位置** |`）⇒ ⛔ 不受行内引号/反引号形态影响。
本文件是 **CRLF**（读 `newline=""`、写回 `\r\n`）。

跑法：`backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_handoff_hashes.py --check` / `--write`
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / ".workbuddy" / "plans" / "开发计划-主文档.md"

ROW_PREFIX = "| **分支 / 提交位置** |"

ROW_NEW = (
    "| **分支 / 提交位置** | `master`（⚠️ **本地领先远端** —— 已推送的部分到 `810317a` 为止）· "
    "⭐ **2026-09-29 晚实测**：`HEAD = 3bac93f`、**工作区干净（0 条未提交）** ⇒ 当天补交的 3 条 = "
    "`f129a1b`（`fix(m01,imp)`：`TAIL-189/190`）· `2c2e377`（`chore(m8)`：产包预案 ＋ 本机预演工具 ＋ 结构审计）· "
    "`3bac93f`（`refactor(docs,tests)`：`TAIL-192/193`）；hash 一律以当时的 `git log -1` 为准；"
    "⚠️ **产包脚本自带闸「未提交不让打包」** ⇒ **去办公室前一天要先提交**；⛔ **本批尚未 push**（等用户点头） |"
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="真写（默认只干跑）")
    ap.add_argument("--check", action="store_true", help="显式的干跑（本仓惯例）")
    args = ap.parse_args()

    head = subprocess.run(["git", "log", "-1", "--format=%h %s"], cwd=str(ROOT),
                          capture_output=True, text=True, encoding="utf-8").stdout.strip()
    raw = PLAN.read_text(encoding="utf-8", newline="")
    assert "\r\n" in raw, "本文件应当是 CRLF"
    lines = raw.split("\r\n")
    hit = [i for i, ln in enumerate(lines) if ln.startswith(ROW_PREFIX)]
    if len(hit) != 1:
        raise SystemExit(f"⛔ 「分支 / 提交位置」行：期望命中 1 行，实测 {len(hit)} 行 ⇒ 停手")
    print("当前 HEAD：", head)
    print("旧行：", lines[hit[0]][:110], "…")
    lines[hit[0]] = ROW_NEW
    new = "\r\n".join(lines)
    print("新行：", ROW_NEW[:110], "…")
    if not args.write:
        print("\n（--check 干跑结束；加 --write 才落盘）")
        return 0
    PLAN.write_text(new, encoding="utf-8", newline="")
    print("\n✅ 已写回 .workbuddy/plans/开发计划-主文档.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
