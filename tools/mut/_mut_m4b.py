"""`ACC-RPT-BIG-001`（活动大表）的**反向灵敏度**：把实现故意改坏，确认对应断言**确实变红**。

跑法：`python tools/_mut_m4b.py`（在工程根）—— 退出码非 0 = 有"仍绿"或有还原失败。

⚠️ 三条纪律（都是踩出来的）：
1. **本仓源码行尾不统一** ⇒ 片段一律按 LF 写，匹配前用 `_fit()` 按目标文件归一；
2. **片段含中文要用 `str` + `.encode()`** —— bytes 字面量只允许 ASCII（`b"中文"` 直接 SyntaxError）；
3. **跑完必须重跑一次全套 `pytest`** —— 否则 `artifacts/acc_results.json` 留的是**变异态**结果
   ⇒ `acc_report.py` / `doc_audit` 的 `T4` 会报**假数字**。
"""

from __future__ import annotations

import hashlib
import subprocess
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
BE = ROOT / "backend"
PY = str(BE / ".venv/Scripts/python.exe")

#: `(说明, 相对路径, 原文, 替换)` —— 原文/替换**一律按 LF 写**
MUTATIONS: list[tuple[str, str, str, str]] = [
    ("① 带入判据用真值判断（0 会被当成「未录入」⇒ 重新带入）",
     "backend/app/mod07_setl/big_domain.py",
     "    if cur.get(key) is not None:",
     "    if cur.get(key):"),

    ("② 带入只看紧邻上一个月（不再往前找 ⇒ 乙仓取不到 06 月）",
     "backend/app/mod07_setl/big_domain.py",
     '    earlier = sorted((m for m in own_by_ym if str(m) < str(month)), reverse=True)',
     '    earlier = sorted((m for m in own_by_ym if str(m) < str(month)), reverse=True)[:1]'),

    ("③ 合计漏掉设备租赁（只算外租机械）",
     "backend/app/mod07_setl/big_domain.py",
     "    return sum_money([_dec(rent_cum), _dec(lease_cum)])",
     "    return sum_money([_dec(rent_cum)])"),

    ("④ 使用率分母为 0 时臆造 0（而不是「不可得」）",
     "backend/app/mod07_setl/big_domain.py",
     "    den = _dec(mech_est)\n    if den == 0:\n        return None",
     "    den = _dec(mech_est)\n    if den == 0:\n        return Decimal(\"0.0000\")"),

    ("⑤ 主材累计不过滤「纳入台账」（把未纳入的也算进去）",
     "backend/app/mod07_setl/big_domain.py",
     "        if str(c.get(\"project\") or \"\") == str(project_key or \"\") and bool(c.get(\"in_ledger\"))",
     "        if str(c.get(\"project\") or \"\") == str(project_key or \"\")"),

    ("⑥ 金额解析放过负数", "backend/app/mod07_setl/big_domain.py",
     "    if v < 0:\n        return {\"ok\": False, \"value\": None, \"message\": MSG_BAD_MONEY}",
     "    if False:\n        return {\"ok\": False, \"value\": None, \"message\": MSG_BAD_MONEY}"),

    ("⑦ 开工时间格式放宽（长度不判 ⇒ `2026-3` 也能过）",
     "backend/app/mod07_setl/big_domain.py",
     "    if len(v) != 7 or v[4] != \"-\":\n        return None",
     "    if v[4:5] != \"-\":\n        return None"),

    ("⑧ 候选不过滤归档（归档项目也进候选）",
     "backend/app/mod07_setl/big_domain.py",
     "        if not c.archived and c.key",
     "        if c.key"),

    ("⑨ 编辑一格时把同行其它格连带确认（置 0）",
     "backend/app/mod07_setl/big_repository.py",
     "    setattr(row, column, value)",
     "    for _k, _c in B.MANUAL_COLUMN.items():\n"
     "        setattr(row, _c, value if _k == key else (_c and 0))"),

    ("⑩ 选题不写标记行（「清空」会被当成「从未选题」⇒ 悄悄回到全部候选）",
     "backend/app/mod07_setl/big_repository.py",
     "    s.add(AnalysisBigProject(warehouse_name=CHOICE_MARKER, seq=-1))    # 标记行（见常量说明）",
     "    pass"),

    ("⑪ 手填值触发欠款重算（越界调用付款域出口）",
     "backend/app/mod07_setl/big_service.py",
     "    R.save_cell(s, ym=month, warehouse=warehouse, key=key, value=parsed[\"value\"])",
     "    R.save_cell(s, ym=month, warehouse=warehouse, key=key, value=parsed[\"value\"])\n"
     "    from app.mod05_flow.repository import sync_stat_paid\n"
     "    sync_stat_paid(s, 0)"),

    ("⑫ 出纸仍留 A3 打印通道（§1.4.1 的取消被回退）",
     "backend/app/mod07_setl/big_view.py",
     "f\"**出纸**：{B.PRINT_CHANNEL}",
     "f\"**出纸**：A3 打印或 {B.PRINT_CHANNEL}"),

    ("⑬ 展示名不进「项目名称」列（那一列会渲染成空）",
     "backend/app/mod07_setl/big_domain.py",
     "    if key == \"project\":\n        return str(row.get(\"display\") or \"\"), \"\"",
     "    if key == \"project\":\n        return None, \"\""),

    ("⑭ 主材累计混进手填列（§5.7.1 已改派生）",
     "backend/app/mod07_setl/big_domain.py",
     "    (\"oil\",         KIND_HAND,    FMT_MONEY),   # 工程用油（手填 · 油卡台账）",
     "    (\"oil\",         KIND_HAND,    FMT_MONEY),   # 工程用油（手填 · 油卡台账）\n"
     "    (\"mat_dup\",     KIND_HAND,    FMT_MONEY),   # 故意：把手填列凑成 7 个"),

    ("⑮ 路由把出口挂到错的模块上（`parse_state` 其实住在 `big_service`）",
     "backend/app/mod07_setl/router.py",
     '    month = big_state({"period": str(form.get("period") or "")})["month"]\n'
     "    with session_scope() as s:\n"
     '        cands = build_big_data(s, {"month": month})["candidates"]\n'
     "        res = save_manual_cell(",
     '    month = big_state.parse_month({"period": str(form.get("period") or "")})["month"]\n'
     "    with session_scope() as s:\n"
     '        cands = build_big_data(s, {"month": month})["candidates"]\n'
     "        res = save_manual_cell("),
]

TEST = "tests/test_acc_rpt_big.py"


def _fit(fragment: str, sample: bytes) -> bytes:
    """把片段的行尾归一成 `sample` 的样子（本仓源码行尾不统一）。"""
    raw = fragment.replace("\r\n", "\n").encode("utf-8")
    if b"\r\n" in sample:
        return raw.replace(b"\n", b"\r\n")
    return raw


def run_test() -> int:
    return subprocess.run([PY, "-m", "pytest", TEST, "-qq", "--no-header",
                           "-p", "no:cacheprovider"], cwd=BE, capture_output=True).returncode


def main() -> int:
    files = sorted({rel for _d, rel, _o, _n in MUTATIONS})
    src0 = {f: (ROOT / f).read_bytes() for f in files}
    md5_0 = {f: hashlib.md5(b).hexdigest() for f, b in src0.items()}
    bad = 0
    for desc, rel, old_s, new_s in MUTATIONS:
        src = src0[rel].replace(b"\r\n", b"\n")
        o, n = old_s.encode("utf-8"), new_s.encode("utf-8")
        if src.count(o) != 1:
            print(f"[SKIP ] ❓ {desc} —— 锚点命中 {src.count(o)} 次（应为 1）")
            bad += 1
            continue
        (ROOT / rel).write_bytes(_fit(src.replace(o, n, 1).decode("utf-8"), src0[rel]))
        rc = run_test()
        (ROOT / rel).write_bytes(src0[rel])
        print(f"[{'RED ' if rc else 'GREEN'}] {'✅' if rc else '❌'} {desc}")
        bad += 0 if rc else 1
    print("\n--- 还原复核（MD5 逐字节）---")
    for f in files:
        now = hashlib.md5((ROOT / f).read_bytes()).hexdigest()
        ok = now == md5_0[f]
        print(("OK  " if ok else "BAD "), f, now)
        bad += 0 if ok else 1
    print(f"\n合计问题 = {bad}（0 = 全部变异都被判据抓住、且源文件逐字节复原）")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
