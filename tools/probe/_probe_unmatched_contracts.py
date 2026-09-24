"""一次性取证：i8 里"抓到了但**匹配不上项目档案**"的合同是哪些项目、各几条。

**为什么要它**：2026-09-24 全量重抓的回执只说 `unmatched = 92`，**没给未命中项目的清单**
（回执里只有 `matched_projects`）⇒ 人看不到"漏的是哪些项目"。

**复用生产同一个匹配件**（`mod11_jc.fetch_service.match_projects` + `all_projects`）⇒ 口径与抓取完全一致，
⛔ 不另写一套"像不像"的判断（那必然漂移）。

⚠️ 会取一次 i8 **合同列表**（只读，⛔ 不落库 —— 落库在 `fetch_service`，本件不调它）⇒ 约 40 秒。
⚠️ 会登录 i8（**缓存命中则不登录**）；真登录含 `KillOnlineUser` 强踢（用户已授权）。

用法：`backend\\.venv\\Scripts\\python.exe tools\\probe\\_probe_unmatched_contracts.py`
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.core.db import session_scope                        # noqa: E402
from app.mod01_projects.repository import all_projects        # noqa: E402
from app.mod02_i8.client import I8Client                     # noqa: E402
from app.mod02_i8.contract_source import ContractFetcher     # noqa: E402
from app.mod11_jc.fetch_service import match_projects        # noqa: E402


def main() -> int:
    cli = I8Client(allow_kick=True)
    try:
        print("取一次 i8 合同列表（只读 · ⛔ 不落库）…")
        rows = ContractFetcher(cli).fetch_all(since="")
        with session_scope() as s:
            projects = list(all_projects(s))
        print(f"抓到 {len(rows)} 条 · 本地项目档案 {len(projects)} 行")
        res = match_projects(rows, projects)

        matched, unmatched = res["matched"], res["unmatched"]
        print(f"匹配上 {len(matched)} 条 · 匹配不上 {len(unmatched)} 条 · 同全名命中多行 {res['multi']} 条")

        tally: dict[str, int] = {}
        for r in unmatched:
            nm = str(r.get("project_name") or "(无项目名)").strip()
            tally[nm] = tally.get(nm, 0) + 1
        print(f"\n=== ⛔ 匹配不上的合同（按 i8 里的项目全名分组，共 {len(tally)} 个项目）===")
        for nm, n in sorted(tally.items(), key=lambda x: (-x[1], x[0])):
            print(f"  {n:>3} 条  {nm}")

        print("\n=== 对照：已纳管项目档案（本地）===")
        for p in sorted(str(getattr(x, "name_full", "") or "") for x in projects):
            print(f"       {p}")
    finally:
        cli.close()
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
