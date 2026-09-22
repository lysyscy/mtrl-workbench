"""一次性取证：把 i8 **仓库名单**（`API-05`）整份取回来，找「永安」以及 2019 壳归属。

**为什么要这个脚本**：`sync/warehouses` 端点只回 `count` ＋ 前 5 条 `sample`，而**仓库名单本身不落库**
（它是「仓库名 ↔ 所属项目全名」的**映射**、是建档的输入）⇒ 想在库里查、或在回包里看全，都做不到。
⚠️ 本脚本**会登录 i8 并强踢在线用户**（`allow_kick=True`）——**跑之前必须告知用户**。

用法：`backend/.venv/Scripts/python.exe tools/_probe_wh.py`
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.mod02_i8.client import I8Client          # noqa: E402
from app.mod02_i8.sources import WarehouseSource  # noqa: E402


def main() -> int:
    kw = sys.argv[1] if len(sys.argv) > 1 else "永安"
    client = I8Client(allow_kick=True)
    try:
        rows = WarehouseSource(client).fetch()
    finally:
        client.close()

    print(f"仓库名单总条数 = {len(rows)}")
    print("\n=== 命中关键词 ===")
    hits = [r for r in rows if kw in str(r.get("warehouse_name") or "")
            or kw in str(r.get("owner_full_name") or "")]
    for r in hits:
        print(f"  仓={r['warehouse_name']!r}")
        print(f"     归属={r['owner_full_name']!r}")
    if not hits:
        print(f"  （没有含「{kw}」的仓库）")

    print("\n=== 含「2019」的归属 ===")
    for r in rows:
        if "2019" in str(r.get("owner_full_name") or ""):
            print(f"  仓={r['warehouse_name']!r}  归属={r['owner_full_name']!r}")

    print("\n=== 全量名单 ===")
    for i, r in enumerate(rows, 1):
        print(f"  {i:>3}. {r['warehouse_name']}   ←  {str(r.get('owner_full_name') or '')[:52]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
