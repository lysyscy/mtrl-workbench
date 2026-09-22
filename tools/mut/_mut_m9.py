#!/usr/bin/env python
"""反向灵敏度（变异测试）—— `ACC-FEE-MON-001` 的 11 个判据点有没有区分力。

纪律（`MEMORY-细则.md` §十七）：① 变异 / 还原**一律走 bytes**；② 片段按目标文件**行尾归一**（`_fit`）；
③ **变异点找不到 ⇒ 当红灯**（脚本报「未验证」，不报「通过」）；④ 跑完**重跑全套 pytest**。

用法：`python tools/_mut_m9.py`
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PY = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"
TARGETS = ["tests/test_acc_fee_mon.py"]

#: (相对路径, 变异说明, 原文片段, 替换片段) —— 片段按 LF 写（str），应用时 encode 再按目标文件归一
#: ⚠️ 片段含中文 ⇒ 用 `str` 而非 `bytes` 字面量（`b"…"` 只允许 ASCII）。
MUTATIONS: list[tuple[str, str, str, str]] = [
    ("backend/app/mod09_fee/domain.py", "自动项不再限定「出库」（只留 CBS 判据）",
     '        if str(r.get("cbs") or "") != CBS_AWF or str(r.get("direction") or "") != DIRECTION_OUT:',
     '        if str(r.get("cbs") or "") != CBS_AWF:'),
    ("backend/app/mod09_fee/domain.py", "自动项不再限定「核算年月」",
     '        if str(r.get("ym") or "") != str(ym or ""):',
     '        if False:'),
    ("backend/app/mod09_fee/domain.py", "Σ 手填项漏掉第 2 项起",
     "    for it in items or ():\n        total += Decimal(str(it.get(\"amount\") or 0))",
     "    for it in (items or ())[:1]:\n        total += Decimal(str(it.get(\"amount\") or 0))"),
    ("backend/app/mod09_fee/repository.py", "取手填项时不再限定「项目」（跨项目串份）",
     "        .where(FeeManualItem.ym == ym, FeeManualItem.project_id == project_id)",
     "        .where(FeeManualItem.ym == ym)"),
    ("backend/app/mod09_fee/domain.py", "默认年月改成「当月」（材料报表类应为上月）",
     '    return default_period("fee", now)',
     '    return default_period("notice", now)'),
    ("backend/app/mod09_fee/domain.py", "金额非法时静默变 0（不再报错）",
     "    except (InvalidOperation, ArithmeticError, ValueError) as exc:\n"
     "        raise ValueError(MSG_BAD_AMOUNT) from exc",
     "    except (InvalidOperation, ArithmeticError, ValueError):\n"
     "        return ZERO"),
    ("backend/app/mod09_fee/service.py", "删除反馈里不再带「重算后的合计」",
     'f" —— 合计重算为 {D.money_text(after)}（§5.5）")',
     'f"（§5.5）")'),
    ("backend/app/mod09_fee/domain.py", "空态提示行的跨列数写死（不再派生自表头）",
     "EMPTY_COLSPAN = len(AWF_COLUMNS)",
     "EMPTY_COLSPAN = 3"),
    ("backend/app/mod09_fee/view.py", "项目候选的 value 渲染成展示名（键不是仓库名）",
     'f\'<label><input type="radio" name="pj" value="{esc(c.key)}"\'',
     'f\'<label><input type="radio" name="pj" value="{esc(c.display)}"\''),
    ("backend/app/mod09_fee/domain.py", "导出说明里不再点明「随逐月欠款台账」",
     'EXPORT_NOTE = "随「逐月欠款台账」导出（工作表：辅材欠款 / 机械欠款 / 特殊费用月报表）"',
     'EXPORT_NOTE = "导出（工作表：辅材欠款 / 机械欠款 / 特殊费用月报表）"'),
    ("backend/app/mod09_fee/domain.py", "表头首列改成库存单据的特征列名（不再是「数据项」）",
     '{"key": "item", "label": "数据项", "type": "text"},',
     '{"key": "item", "label": "物料", "type": "text"},'),
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
