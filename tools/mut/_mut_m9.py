#!/usr/bin/env python
"""反向灵敏度（变异测试）—— `ACC-FEE-MON-001` 的 11 个判据点有没有区分力。

纪律（`细则.md` §十七）：① 变异 / 还原**一律走 bytes**；② 片段按目标文件**行尾归一**（`_fit`）；
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
#: ⚠️ 2026-09-23：最后一条（候选面板）搬到壳里 ⇒ 判据在 `test_wired_m09.py`，故两个都要跑。
TARGETS = ["tests/test_acc_fee_mon.py", "tests/test_wired_m09.py"]

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
    # ⚠️ 2026-09-23：原靶 `EMPTY_COLSPAN` / 原靶 `mod09_fee/view.py`（旧服务端渲染页）都已作废 ——
    #    空态跨列数与候选面板的 claim **搬到了壳**（`tests/test_wired_m09.py`）⇒ 靶一律改指壳里那几行。
    ("backend/app/web/index.html", "空态提示行的跨列数写死（不再派生自表头）",
     'colspan="${thCount(AWF_THEAD)}"',
     'colspan="3"'),
    ("backend/app/web/index.html", "候选面板不再读后端清单（键可能不是仓库名）",
     "const awfPjPanel=()=>projPanel({list:()=>AWF_PJS,",
     "const awfPjPanel=()=>projPanel({list:()=>[],"),
    # ⚠️ 2026-09-23：这段文案在壳里有**两处**（`title=` 提示 ＋ 可见文字）⇒ 变异要**一起改掉**，
    #    只改可见文字的话 `title` 里还留着「逐月欠款台账」⇒ 断言仍绿（实测踩过）。
    ("backend/app/web/index.html", "导出说明里不再点明「随逐月欠款台账」",
     '它随「逐月欠款台账」一起导出，作为每个项目工作簿的第 3 个工作表">随「逐月欠款台账」导出</span>',
     '它单独导出">导出</span>'),
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
