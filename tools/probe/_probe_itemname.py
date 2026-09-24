"""一次性取证：i8 **合同详情** `GetCntMInfoFirst` 的原文形态 —— 查 `material_name` 为何落下项目名。

**背景**：库里 **66 行** `material_name` 落的是**项目名**，而这些行的 `bill_name` 里**都写着真材料**
（如 `四分/内蒙古三峡项目/鑫呈/电缆桥架合同（65888）` ⇒ 材料应为「电缆桥架」）。
取值件 = `ContractFetcher.fetch_item_name`（先 `Grid` 后 `ItemGrid`，取**第一个非空 `ItemName`**）。
⇒ 本件把**原文**打出来，判「取错行」还是「i8 就这么给」。

⚠️ **PhId 只能从 i8 列表拿** —— `jc_contract` **没有 `PhId` 列**（那是抓取途中 `fields` 里的东西、不落库）。
   ⇒ 本件先 `fetch_all()` 取一次列表（**只读，不落库** —— 落库在 `fetch_service`，本件不调它），
     再按 `contract_no` 对上样本。

⚠️ 会登录 i8（**缓存命中则不登录**）；真登录含 `KillOnlineUser` 强踢 —— 用户 2026-09-24 已授权。
⚠️ 只读：不写库、不改任何业务件。

用法：`backend\\.venv\\Scripts\\python.exe tools\\probe\\_probe_itemname.py [样本条数]`
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from sqlalchemy import text                                    # noqa: E402

from app.core.db import session_scope                           # noqa: E402
from app.mod02_i8.client import I8Client                        # noqa: E402
from app.mod02_i8.contract_source import (                      # noqa: E402
    DETAIL_TYPE,
    ContractFetcher,
    configured_detail_url,
)

_SQL = text("""
    select contract_no, material_name, bill_name
    from jc_contract
    where coalesce(material_name, '') like '%项目%'
      and coalesce(contract_no, '') <> ''
    order by material_name, contract_no
    limit :n
""")


def _samples(n: int) -> list[tuple]:
    with session_scope() as s:
        return list(s.execute(_SQL, {"n": n}).all())


def _short(v: object, limit: int = 46) -> str:
    s = "" if v is None else str(v)
    return s if len(s) <= limit else s[:limit] + "…"


def main() -> int:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    samples = _samples(n)
    if not samples:
        print("库里没有「material_name 落项目名」的行 ⇒ 无需取证")
        return 0
    print(f"样本 {len(samples)} 条（库里 material_name 落「项目名」的合同）")
    for no, mat, bill in samples:
        print(f"   · {no}  material_name={mat!r}  bill_name={bill!r}")

    cli = I8Client(allow_kick=True)
    fetcher = ContractFetcher(cli)
    try:
        print("\n=== 取 i8 合同**列表**（只为拿 PhId；⛔ 不落库）===")
        listed = fetcher.fetch_all(since="")
        print(f"列表取到 {len(listed)} 条")
        by_no = {str(r.get("contract_no") or ""): r for r in listed}

        for i, (no, mat, bill) in enumerate(samples, 1):
            print("=" * 78)
            print(f"[{i}/{len(samples)}] 合同号 = {no}")
            print(f"   库里 material_name = {mat!r}")
            print(f"   库里 bill_name     = {bill!r}")
            r = by_no.get(no)
            if not r:
                print("   ⚠️ i8 列表里没有这个合同号（可能未审批 / 已删）⇒ 跳过")
                continue
            phid = str((r.get("fields") or {}).get("PhId") or "")
            print(f"   i8 PhId = {phid}")
            if not phid:
                print("   ⚠️ 该条没有 PhId ⇒ 跳过")
                continue
            print(f"   ⭐ 取值件 fetch_item_name() 返回 = {fetcher.fetch_item_name(phid)!r}")
            resp = cli.post_json(configured_detail_url(),
                                 params={"id": phid, "type": DETAIL_TYPE},
                                 data={}, timeout=60.0)
            if not isinstance(resp, dict):
                print(f"   ⚠️ 响应不是 dict：{type(resp)}")
                continue
            print(f"   响应顶层键 = {list(resp.keys())}")
            data = resp.get("Data")
            if not isinstance(data, dict):
                print("   ⚠️ Data 不是 dict —— 原文（前 600 字）：")
                print(json.dumps(resp, ensure_ascii=False)[:600])
                continue
            print(f"   Data 顶层键 = {list(data.keys())}")
            for gk in ("Grid", "ItemGrid"):
                g = data.get(gk)
                if not isinstance(g, dict):
                    print(f"   · {gk}：（无）")
                    continue
                rs = g.get("results") or []
                print(f"   · {gk}：results 共 {len(rs)} 行")
                for j, row in enumerate(rs):
                    if not isinstance(row, dict):
                        print(f"        [{j}]（非 dict：{type(row)}）")
                        continue
                    print(f"        [{j}] ItemName = {row.get('ItemName')!r}")
                    if j == 0:
                        pairs = [(k, _short(v)) for k, v in row.items()
                                 if v not in (None, "", [], {})]
                        print("            第 0 行非空字段（前 18 个）：")
                        for k, v in pairs[:18]:
                            print(f"              {k} = {v}")
    finally:
        cli.close()
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
