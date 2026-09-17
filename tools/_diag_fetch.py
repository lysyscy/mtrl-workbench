"""一次性诊断脚本（真机）：**一次登录**里导出两份 → 落盘留证 → 复核修复 + 看收发结存真表头。

为什么要它：真机第一次跑暴露两件事 ——
① `inv` 抓取解析 559 行却只落库 18 行（根因 = `upsert_details` 的幂等范围漏了「仓库」，已修，需真机复核）；
② `setl` 抓取失败（前 4 行找不到表头）—— 离线断言看不见真表头，必须**把真文件留在磁盘上**再离线修。

⚠️ 会登录 i8 并**强踢在线用户**（`KillOnlineUser`）—— 用户 2026-09-17 已授权；跑完即止，不重试。
跑法：`backend/.venv/Scripts/python.exe tools/_diag_fetch.py`（在工程根）
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

YM = "2026-09"
OUT = ROOT / "artifacts" / "_diag"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    from app.core.db import session_scope
    from app.mod02_i8 import fetch_task, report_export
    from app.mod02_i8.client import I8Client
    from app.mod02_i8.repository import save_run_record
    from app.mod08_inv import fetch_service as FS8
    from app.mod08_inv import importer as IM8
    from app.mod08_inv.repository import load_rows, upsert_details

    with session_scope() as s:
        ids = FS8.project_ids(s)

    client = I8Client(allow_kick=True)
    try:
        print(f"=== 一次登录（强踢）· 项目 {len(ids.split(','))} 个 ===")
        inv = report_export.export(client, spec_key="inv", year_month=YM, proj_ids=ids)
        (OUT / f"inv_{YM}.xlsx").write_bytes(inv)
        setl = report_export.export(client, spec_key="setl", year_month=YM, proj_ids=ids)
        (OUT / f"setl_{YM}.xlsx").write_bytes(setl)
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()
    print(f"导出落盘：inv {len(inv)} B · setl {len(setl)} B → artifacts/_diag/")

    # ---------------- ① inv：解析 + 幂等落库（复核修复）
    rows = IM8.parse_rows(inv)
    groups = FS8.group_by_scope(rows)
    print(f"=== inv 解析 {len(rows)} 行 · 分组（核算年月＋仓库）{len(groups)} 个 ===")
    with session_scope() as s:
        stats = {"inserted": 0, "updated": 0, "deleted": 0, "kept_with_adjustment": 0}
        for (ym, wh), group in sorted(groups.items()):
            part = upsert_details(s, ym=ym, warehouse=wh, rows=group)
            for k in stats:
                stats[k] += part[k]
            print(f"  {ym} · {wh}：{len(group)} 行 → 新增 {part['inserted']} 更新 {part['updated']} "
                  f"删除 {part['deleted']} 保留 {part['kept_with_adjustment']}")
        save_run_record(s, **fetch_task.fetch_record_payload(
            object_desc=f"inv {YM}（{len(ids.split(','))} 个项目）", success=len(rows), fail=0),
            operator="科室用户")
    with session_scope() as s:
        kept = load_rows(s, ym=YM)
        print(f"=== 落库复核：{YM} 共 {len(kept)} 行 · 仓库 {len({r['warehouse'] for r in kept})} 个 ===")
        print("  ", sorted({r["warehouse"] for r in kept})[:4], "…" if len({r['warehouse'] for r in kept}) > 4 else "")
    print(f"  统计：{stats}")

    # ---------------- ② setl：只做诊断（不落库）—— 打印真表头
    print("=== setl 诊断：真实网格前 6 行 ===")
    from app.mod07_setl import importer as IM7

    grid = IM7.read_grid(setl)
    for i, line in enumerate(grid[:6]):
        cells = [str(c)[:14] for c in line[:18]]
        print(f"  行{i}: {cells}")
    try:
        srows = IM7.parse_rows(setl)
        print(f"  ⟹ 解析成功：{len(srows)} 行")
    except Exception as exc:                      # noqa: BLE001
        print(f"  ⟹ 解析失败：{type(exc).__name__}: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
