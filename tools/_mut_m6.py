#!/usr/bin/env python
"""反向灵敏度（变异测试）—— `ACC-INIT-001` / `ACC-ODDVAL-001` 的判据有没有区分力。

纪律（`MEMORY-细则.md` §十七）：
1. **变异 / 还原一律走 bytes** —— `write_text` 在 Windows 上会把 `\n` 写成 `\r\n` ⇒ MD5 假 BAD；
2. **片段按目标文件的行尾归一**（本仓源码行尾不统一）；
3. **变异点找不到 ⇒ 必须当红灯处理**（脚本报「未验证」，不报「通过」）；
4. 跑完**重跑全套 pytest**（本脚本内只跑两个目标文件，会覆盖 `artifacts/acc_results.json`）。

用法：`python tools/_mut_m6.py`（只读 → 变异 → 跑目标测试 → 还原 → 校验 MD5 逐字节一致）
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"
TARGETS = ["tests/test_acc_init.py", "tests/test_acc_oddval.py"]

#: (相对路径, 变异说明, 原文片段, 替换片段) —— 片段**一律按 LF 写**（str，应用时 encode 再按目标文件归一）
#: ⚠️ 片段含中文 ⇒ 用 `str` 而非 `bytes` 字面量（`b"…"` 只允许 ASCII）。
MUTATIONS: list[tuple[str, str, str, str]] = [
    ("backend/app/mod05_flow/domain.py", "期初不再并入辅材（那条 + _opening 摘掉）",
     " + _opening(CATEGORY_MATERIAL)", ""),
    ("backend/app/mod05_flow/domain.py", "台账自截止月（而非次月）起排行 ⇒ 期初被重复计入",
     "start_ym = next_month(opening.cutoff_ym) if opening.cutoff_ym else None",
     "start_ym = opening.cutoff_ym or None"),
    ("backend/app/mod05_flow/importer.py", "认不出的取值不留原文（原文不进备注）",
     "        if not recognized:", "        if False:"),
    ("backend/app/mod05_flow/importer.py", "异常行不再带源行号（报错定位失效）",
     'plan.anomalies.append({"line": line, "bill_no": bill_no, "reason": str(exc)})\n'
     "            continue\n"
     "        try:\n"
     "            pay_date = parse_date(date_raw)",
     'plan.anomalies.append({"line": 0, "bill_no": bill_no, "reason": str(exc)})\n'
     "            continue\n"
     "        try:\n"
     "            pay_date = parse_date(date_raw)"),
    ("backend/app/mod05_flow/importer.py", "未匹配的行也当匹配放进可写集（模糊匹配）",
     "            out.unmatched.append(",
     "            out.rows.append(r) or True or out.unmatched.append("),
    ("backend/app/mod05_flow/importer.py", "对认不出的写法**猜**一个四类（替用户做判断）",
     '    return "其他", False',
     '    return "现汇", True'),
    ("backend/app/mod05_flow/importer.py", "单据号精确匹配失效（命中 0 也不报未匹配）",
     "        if str(r.bill_no) in known:",
     "        if False:"),
    ("backend/app/mod05_flow/importer.py", "导入不落库（付款事实补录失效）",
     "        repo.create_flow(\n            s, notice_id=int(r.notice_id), project_id=None, amount=r.amount,",
     "        (lambda *a, **k: None)(\n            s, notice_id=int(r.notice_id), project_id=None, amount=r.amount,"),
    ("backend/app/mod02_i8/report_export.py", "补抓历史月份时年份取当前年（而不是该月所属年）",
     "    return ym[:4], str(month), ym[:4], str(month)",
     "    return str(__import__('datetime').date.today().year), str(month), ym[:4], str(month)"),
    # ⚠️ 2026-09-21（`§19` 四个暂留件收口）：落点从 PRG 路由件搬到 JSON API 件（**逐字**搬）。
    ("backend/app/mod05_flow/import_api.py", "历史流水导入三步少一步（预览端点改名）",
     '@router.post("/api/m05/import/parse"', '@router.post("/api/m05/import/parse-x"'),
]


def _fit(fragment: bytes, sample: bytes) -> bytes:
    """把片段的行尾归一成 `sample` 的样子（本仓源码行尾不统一）。"""
    if b"\r\n" in sample:
        return fragment.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    return fragment.replace(b"\r\n", b"\n")


def main() -> int:
    bad: list[str] = []
    for rel, label, old, new in MUTATIONS:
        f = ROOT / rel
        src = f.read_bytes()
        md5_before = hashlib.md5(src).hexdigest()
        o, n = _fit(old.encode("utf-8"), src), _fit(new.encode("utf-8"), src)
        if src.count(o) != 1:
            print(f"  ⚠️ 未验证（变异点命中 {src.count(o)} 次）：{rel} · {label}")
            bad.append(label)
            continue
        try:
            f.write_bytes(src.replace(o, n, 1))
            r = subprocess.run([str(PY), "-m", "pytest", "-q", *TARGETS],
                               cwd=str(ROOT / "backend"), capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
            ok = r.returncode != 0
        finally:
            f.write_bytes(src)
        md5_after = hashlib.md5(f.read_bytes()).hexdigest()
        flag = "✅ 变红" if ok else "❌ 仍绿（假绿，判据没区分力）"
        same = "逐字节复原" if md5_before == md5_after else "!! MD5 BAD !!"
        print(f"  {flag}  {rel} · {label}  [{same}]")
        if not ok or md5_before != md5_after:
            bad.append(label)
    print(f"\n合计 {len(MUTATIONS)} 处 · 通过 {len(MUTATIONS) - len(bad)} · 有问题 {len(bad)}")
    if bad:
        print("有问题：" + " / ".join(bad))
        return 1
    print("⚠️ 本脚本只跑了目标文件 ⇒ 接着必须重跑**全套** pytest 再出报表（否则报表掉绿）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
