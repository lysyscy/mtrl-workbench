"""反向灵敏度 · **M5 集采域域内核**（`ACC-JC-*` 那 11 条断言的区分力自检）。用完即删。

做法：逐条把 `app/mod11_jc/domain.py` **故意改坏** ⇒ 对应断言必须**变红** ⇒ 改回后**逐字节复原**（MD5 校验）。

⚠️ **本脚本比老的 `_mut_*.py` 多做了一件事（新纪律，建议后续脚本照做）**：
   跑 `pytest -k` **子集**时把 `ACC_RESULTS_PATH` 指到**临时文件** ——
   否则 acc 插件会把"只跑了这几个测试"的结果写回工程基线 `artifacts/acc_results.json`，
   于是 `doc_audit` 的 `T4`（四态数字核对）**当场报错**（2026-09-19 实测踩到：基线被写成
   "绿 15 · 未绑定 495"）。⛔ 子集运行**永远**把结果指到外面。

跑法：`python tools/_mut_jc.py`（期望：命中 N/N · SKIP 0 · MD5 逐字节复原 ✅）
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BE = ROOT / "backend"

PY = BE / ".venv" / "Scripts" / "python.exe"
SRC = BE / "app" / "mod11_jc" / "domain.py"
TEST = "tests/test_acc_jc_domain.py"

#: (说明, 老片段, 新片段, 该变红的测试名)
MUTS: list[tuple[str, str, str, str]] = [
    # ---- 结算两条路径（001-10）
    ("结算改口径：有贸易公司也去取供应商发票（两条路串用）",
     "    if str(trade_co or \"\").strip():\n        return trade_invoice_sum(invoices)\n    return supplier_invoice_sum(invoices)",
     "    if str(trade_co or \"\").strip():\n        return supplier_invoice_sum(invoices)\n    return supplier_invoice_sum(invoices)",
     "test_结算两条路径各取各自子表合计_互不串用"),
    ("结算让两侧相加（instead of 二选一）",
     "    if str(trade_co or \"\").strip():\n        return trade_invoice_sum(invoices)\n    return supplier_invoice_sum(invoices)",
     "    return trade_invoice_sum(invoices) + supplier_invoice_sum(invoices)",
     "test_结算两条路径各取各自子表合计_互不串用"),
    # ---- 欠款（001-09）
    ("欠款改成「结算 ＋ 付款」（方向反了）",
     "    return (Decimal(str(settle or 0)) - Decimal(str(pay or 0))).quantize(Decimal(\"0.01\"))",
     "    return (Decimal(str(settle or 0)) + Decimal(str(pay or 0))).quantize(Decimal(\"0.01\"))",
     "test_主表金额列只读汇总_改子表即改欠款"),
    ("主表金额列改成「落库式」：只认第一笔付款（后续子表变化不再影响）",
     "    inv = supplier_invoice_sum(invoices)\n    tinv = trade_invoice_sum(invoices)\n    pay = pay_sum(payments)",
     "    inv = supplier_invoice_sum(invoices)\n    tinv = trade_invoice_sum(invoices)\n    pay = pay_sum(payments[:1])                                   # （变异）只认第一笔 ⇒ 子表再变也不动",
     "test_主表金额列只读汇总_改子表即改欠款"),
    # ---- 子表校验（001-05 / 001-06）
    ("发票日期不再必填（只填金额也放行）",
     "    if not _date_text(date):\n        return MSG_NEED_DATE",
     "    if False:\n        return MSG_NEED_DATE",
     "test_子表日期必填_只填金额不填日期不得落库"),
    ("付款校验放宽（与发票不再同款）",
     "    return invoice_problem(date, amount)",
     "    return None",
     "test_子表日期必填_只填金额不填日期不得落库"),
    ("金额只拦非数字、不再拦 0 与负数（与 MOD-09 串了）",
     "    if value <= 0:\n        raise ValueError(MSG_BAD_AMOUNT)",
     "    if False:\n        raise ValueError(MSG_BAD_AMOUNT)",
     "test_发票金额只走大于零这一个出口_不设上限"),
    ("金额加了上限（口径说不设上限）",
     "    if value <= 0:\n        raise ValueError(MSG_BAD_AMOUNT)",
     "    if value <= 0 or value > Decimal(\"1000000\"):\n        raise ValueError(MSG_BAD_AMOUNT)",
     "test_发票金额只走大于零这一个出口_不设上限"),
    # ---- 自由文本（001-15）
    ("域内核偷偷引入付款方式枚举校验（DEV-J-03 明令不许）",
     "def parse_amount(raw) -> Decimal:",
     "def method_problem(raw) -> str | None:\n    \"\"\"（变异）引入枚举校验 —— 违反 DEV-J-03。\"\"\"\n    return None if str(raw or \"\").strip() in (\"现汇\", \"承兑\", \"供应链\") else MSG_BAD_AMOUNT\n\n\ndef parse_amount(raw) -> Decimal:",
     "test_付款方式自由文本_不得引入枚举校验"),
    # ---- 三态（ACC-JC-FETCH-001/001-10）
    ("抓取把人工标记冲掉（一律回「待确认」）",
     "    v = str(current if current is not None else \"\").strip()\n    if v in (TAG_IN, \"不纳入\"):\n        return v\n    return TAG_PENDING",
     "    return TAG_PENDING",
     "test_抓取不覆盖已人工标记的行"),
    ("归一函数把认不出的值猜成「纳入台账」",
     "    return v if v in TAGS else TAG_PENDING",
     "    return v if v in TAGS else TAG_IN",
     "test_抓取不覆盖已人工标记的行"),
    # ---- 去重 / 候选 / 金额提示（ACC-JC-PAY-001）
    ("去重形同虚设（永不拦）",
     "    return notice_id is not None and int(notice_id) in {int(x) for x in (existing_notice_ids or ())}",
     "    return False",
     "test_全库去重_同一通知书只能被引用一次"),
    ("去重只在本合同内（口径是「不分合同」）",
     "    return notice_id is not None and int(notice_id) in {int(x) for x in (existing_notice_ids or ())}",
     "    return False  # 变异：只在同合同内查 ⇒ 跨合同重复引用漏过",
     "test_全库去重_同一通知书只能被引用一次"),
    ("关联金额不一致 ⇒ 直接拦截（口径是只提示不拦）",
     "    if a == d:\n        return None",
     "    if a != d:\n        raise ValueError(\"金额不一致\")\n    if a == d:\n        return None",
     "test_关联不做金额校验_不一致只提示不拦截"),
    ("候选丢了「当前那张无条件保留」",
     "        if current_id is not None and int(c.get(\"id\") or 0) == int(current_id):\n            out.append(c)",
     "        if False:\n            out.append(c)",
     "test_候选范围收窄到本项目与已匹配供应商_且当前那张无条件保留"),
    ("候选不收窄供应商（候选范围过宽）",
     "        if sup and str(c.get(\"supplier\") or \"\").strip() != sup:\n            continue",
     "        if False:\n            continue",
     "test_候选范围收窄到本项目与已匹配供应商_且当前那张无条件保留"),
    ("候选不看项目键（跨项目串）",
     "        if str(c.get(\"project_key\") or \"\").strip() != key:\n            continue",
     "        if False:\n            continue",
     "test_候选为空时给提示且不允许提交"),
]


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def _fit(fragment: str, sample: bytes) -> bytes:
    """把锚点 / 新片段**按目标文件的真实行尾**归一。

    ⚠️ 2026-09-19 实测踩到：本仓 `.py` 的**行尾不统一**（有的 LF、有的 CRLF）——
       多行锚点不归一 ⇒ **永远"命中 0 次"**（单行锚点看不出来，于是"一半能中、一半全 SKIP"，很像锚点写错）。
    """
    b = fragment.encode("utf-8")
    if b"\r\n" in sample:
        return b.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    return b.replace(b"\r\n", b"\n")


def run_one(case: str) -> bool:
    """跑**一个**断点；⚠️ 结果写到**临时文件**（⛔ 别碰工程基线，见文件头）。"""
    with tempfile.TemporaryDirectory() as td:
        env = dict(os.environ)
        env["ACC_RESULTS_PATH"] = str(Path(td) / "acc_tmp.json")
        r = subprocess.run(
            [str(PY), "-m", "pytest", "-q", "-k", case, TEST],
            cwd=str(BE), capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
        )
    return r.returncode == 0


def main() -> int:
    src0 = SRC.read_bytes()
    digest = md5(SRC)
    hit = miss = 0
    for desc, old, new, case in MUTS:
        oldb, newb = _fit(old, src0), _fit(new, src0)
        cnt = src0.count(oldb)
        if cnt != 1:
            print(f"  ⛔ {desc} —— 锚点命中 {cnt} 次（期望 1）⇒ **未验证**")
            miss += 1
            continue
        SRC.write_bytes(src0.replace(oldb, newb, 1))
        green = run_one(case)
        SRC.write_bytes(src0)
        red = not green
        print(("  ✅ " if red else "  ⛔ 未命中 ") + desc + f"  → `{case}` " + ("变红" if red else "**仍是绿的**"))
        hit += red

    ok = md5(SRC) == digest and SRC.read_bytes() == src0
    print(f"\n  命中 {hit}/{len(MUTS) - miss}  · SKIP {miss}  · 逐字节复原：{'✅' if ok else '❌ 没复原'}")
    return 0 if (hit == len(MUTS) and ok) else 1


if __name__ == "__main__":
    sys.exit(main())
