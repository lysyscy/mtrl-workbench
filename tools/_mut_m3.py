"""M3 反向灵敏度：把 MOD-03 实现故意改坏 N 处，确认对应判径真变红。

⚠️ 变异 / 还原**一律走 bytes**（`write_text` 在 Windows 会把 `\n` 写成 `\r\n` ⇒ MD5 假 BAD）。
⚠️ 每一处变异点都**必须先确认能命中**（找不到 ⇒ 重写变异点，不得当作已通过）。
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BE = ROOT / "backend"

# (说明, 文件, 原串, 变异串, 预期变红的测试文件)
def _b(s: str) -> bytes:
    """把源码片段编成 **LF** bytes（脚本里一律按 LF 写片段）。

    ⚠️ **本仓源码行尾不统一，且实测是混着的**：
      · `notice_pay.py` = **CRLF**（263 个 \\r\\n、0 个孤立 \\n）
      · `domain.py` / `merge.py` / `notice_actions.py` = **LF**
    ⇒ 片段一律写成 LF，**匹配时再按目标文件的行尾归一**（见 `_fit`）。
    """
    return s.replace("\r\n", "\n").encode("utf-8")


def _fit(fragment: bytes, sample: bytes) -> bytes:
    """把 LF 片段转成**与目标文件一致**的行尾（目标含 CRLF ⇒ 转 CRLF，否则原样）。"""
    if b"\r\n" in sample:
        return fragment.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    return fragment.replace(b"\r\n", b"\n")


MUTATIONS: list[tuple[str, str, bytes, bytes, str]] = [
    (
        "① 批量付款：不可付行不再禁用（check_batch 永远 enabled）",
        "app/mod03_notice/domain.py",
        _b("    blocked = [r for r in rows if r.block() is not None]\n    if not blocked:\n        return BatchCheck(enabled=True, blocked=[])\n"),
        _b("    blocked = [r for r in rows if r.block() is not None]\n    if True:\n        return BatchCheck(enabled=True, blocked=[])\n"),
        "tests/test_notice_pay.py",
    ),
    (
        "② 批量付款：提交时不再整批重算（errors 不阻断、照落半批）",
        "app/mod03_notice/domain.py",
        _b("    if errors:\n        return ConfirmResult(flows=[], errors=errors)      # **不落半批**\n"),
        _b("    if False:\n        return ConfirmResult(flows=[], errors=errors)      # **不落半批**"),
        "tests/test_notice_pay.py",
    ),
    (
        "③ 批量付款：付款方式取不到不再兜底「现汇」",
        "app/mod03_notice/notice_pay.py",
        _b('''    return str((plan_methods or {}).get(str(bill_no or "").strip()) or "") or "现汇"'''),
        _b('''    return str((plan_methods or {}).get(str(bill_no or "").strip()) or "")'''),
        "tests/test_notice_pay.py",
    ),
    (
        "④ 批量付款：撤单行 / 剔除行照样能进付款批次",
        "app/mod03_notice/notice_pay.py",
        _b('''        elif row.i8_revoked:
            skipped.append((nid, SKIP_REVOKED))
        elif row.excluded:
            skipped.append((nid, SKIP_EXCLUDED))'''),
        _b('''        elif row.i8_revoked and False:
            skipped.append((nid, SKIP_REVOKED))
        elif row.excluded and False:
            skipped.append((nid, SKIP_EXCLUDED))'''),
        "tests/test_notice_pay.py",
    ),
    (
        "⑤ 移出本次付款：顺手把**其它行**的草稿也清掉（丢已填值）",
        "app/mod03_notice/domain.py",
        _b("    left_drafts = {k: v for k, v in (drafts or {}).items() if int(k) != int(notice_id)}\n    return left, left_drafts\n"),
        _b("    left_drafts = {}\n    return left, left_drafts\n"),
        "tests/test_acc_pay_verify.py",
    ),
    (
        "⑥ 再次导入：受保护字段被覆盖（① 主闸 SOURCE_FOLLOWED 塞入受保护键 ＋ ② 兜底 pop 摘掉 —— 两头同破）",
        "app/mod03_notice/merge.py",
        _b('    "biz_type", "payee", "input_by", "amount_approved", "fields",\n)'),
        _b(
            '    "biz_type", "payee", "input_by", "amount_approved", "fields",\n'
            '    "category", "excluded", "exclude_source", "i8_revoked", "revoked_joint",\n'
            '    "ownership_id",\n)'
            "\n<<AND>>\n"
            "    for key in PROTECTED:\n        plan.values.pop(key, None)"
            "\n<<AND>>\n"
            "    for key in ():\n        plan.values.pop(key, None)"
        ),
        "tests/test_merge.py",
    ),
    (
        "⑦ 再次导入：审批金额没变也照样重算（值没变就不动 —— 破坏）",
        "app/mod03_notice/merge.py",
        _b("    if not _same(approved_old, approved_new):"),
        _b("    if True:"),
        "tests/test_merge.py",
    ),
    (
        "⑧ 剔除判定：业务类型等值改成「包含」匹配（应误命中带后缀/前缀写法）",
        "app/mod03_notice/classify.py",
        _b('        elif value in tuple(str(v).strip() for v in rule.values):\n            return rule\n'),
        _b('        elif any(str(v).strip() and str(v).strip() in value for v in rule.values):\n            return rule\n'),
        "tests/test_classify.py",
    ),
    (
        "⑨ 手动行：统计结算金额不再恒 0（跟传入值走）",
        "app/mod03_notice/notice_actions.py",
        _b('        "stat_settle": STAT_SETTLE_FIXED,           # ① **恒 0 且不可改**'),
        _b('        "stat_settle": to_money(stat_settle) if stat_settle not in (None, "") else STAT_SETTLE_FIXED,'),
        "tests/test_notice_actions.py",
    ),
    (
        "⑩ 手动行：录入人改从表单取（不再 = 当前登录用户）",
        "app/mod03_notice/notice_actions.py",
        _b('        "input_by": str(entered_by or ""),          # ⑤ 录入人 = 当前登录用户（不从表单取）'),
        _b('        "input_by": str(input_by or entered_by or ""),'),
        "tests/test_notice_actions.py",
    ),
    (
        "⑪ 手动行：项目候选不再排除小微壳",
        "app/mod03_notice/notice_actions.py",
        _b("        if getattr(p, \"is_shell\", False):\n            continue\n"),
        _b("        if False:\n            continue\n"),
        "tests/test_notice_actions.py",
    ),
    (
        "⑫ 查看关联页：集采栏不再注明原因（臆造空值）",
        "app/mod03_notice/notice_page.py",
        _b('        ("集采实际供应商", "—（集采台账属 MOD-11，尚未落地）"),'),
        _b('        ("集采实际供应商", ""),'),
        # ⚠️ 2026-09-17 修正：拆件后「查看关联页」断言已搬进 `test_notice_action_page.py`
        #    —— 原先指向 `test_notice_actions.py` ⇒ **变异跑了不含该断言的件** ⇒ 假绿。
        "tests/test_notice_action_page.py",
    ),
    (
        "⑬ 查看关联页：已付金额改按全部流水算（含已撤销）",
        "app/mod03_notice/notice_page.py",
        _b("    paid = effective_total([{\"status\": f.get(\"status\"), \"amount\": f.get(\"amount\")} for f in flows])"),
        _b("    paid = sum((to_money(f.get(\"amount\")) for f in flows), to_money(0))"),
        # ⚠️ 2026-09-17 修正：同上 —— 该断言（`_cell_of(html, "已付金额（生效流水汇总）") == "3000.00"`）
        #    现住在 `test_notice_action_page.py`。
        "tests/test_notice_action_page.py",
    ),
]


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


# ⚠️ 「两头铁律」的变异点用这个分隔符把**第二处替换**编进 new：
#    原串①\n<<AND>>\n新串①\n<<AND>>\n原串②\n<<AND>>\n新串②
AND_SEP = "\n<<AND>>\n"


def _apply(src: bytes, old: bytes, new: bytes) -> bytes:
    """施加变异。`new` 含 `AND_SEP` ⇒ 按 `新①/原②/新②` 施加**两处**（两头同破）。

    ⚠️ 拆出来的分段**要各自再做一次行尾归一**（`_fit` 只处理了整串，分隔符本身是 LF）。
    """
    if AND_SEP.encode() not in new:
        return src.replace(old, new, 1)
    parts = new.split(AND_SEP.encode())
    assert len(parts) == 3, f"两头变异点格式错误：应 3 段（新①/原②/新②），实得 {len(parts)}"
    new1, old2, new2 = (_fit(p, src) for p in parts)
    assert src.count(old2) == 1, f"第二处变异点应唯一命中，实得 {src.count(old2)}"
    out = src.replace(old, new1, 1)
    return out.replace(old2, new2, 1)


def run_test(rel: str) -> int:
    r = subprocess.run(
        [str(BE / ".venv/Scripts/python.exe"), "-m", "pytest", rel, "-qq", "--no-header", "-p", "no:cacheprovider"],
        cwd=BE, capture_output=True,
    )
    return r.returncode


def main() -> int:
    before = {m[1]: md5(BE / m[1]) for m in MUTATIONS}
    ok, miss, missed_mut, skips = 0, [], [], []
    for desc, rel, old_lf, new_lf, test in MUTATIONS:
        p = BE / rel
        src = p.read_bytes()
        old, new = _fit(old_lf, src), _fit(new_lf, src)   # ⚠️ 按目标文件行尾归一
        if old not in src:
            miss.append(desc)
            print(f"[SKIP] 变异点找不到 —— {desc}")
            continue
        if old == new:
            missed_mut.append(desc)
            print(f"[SAME] ❌ 原串与变异串相同 —— {desc}")
            continue
        # ⚠️ 有些铁律在**两头**（主闸 ＋ 兜底），单破任一头不露馅 ⇒ 支持「同破」标记
        #    约定：new_lf 以 EXTRA_MARK 分隔的第二段 = 另一处替换（src → dst），同文件内一并施加。
        p.write_bytes(_apply(src, old, new))
        rc = run_test(test)
        p.write_bytes(src)                      # 逐条还原（bytes）
        if rc != 0:
            ok += 1
            print(f"[RED ] ✅ {desc}")
        else:
            missed_mut.append(desc)
            print(f"[GREEN] ❌ 变异了却还是绿 —— {desc}")

    print("\n--- 还原复核 ---")
    bad = [rel for rel, h in before.items() if md5(BE / rel) != h]
    for rel, h in before.items():
        state = "OK " if md5(BE / rel) == h else "BAD"
        print(f"  {state} {rel}  {md5(BE / rel)}")
    print(f"\n命中 {ok}/{len(MUTATIONS)} · 变异点找不到 {len(miss)} · 变异后仍绿 {len(missed_mut)}")
    if miss:
        print("找不到的变异点：", miss)
    if missed_mut:
        print("变异后仍绿（判据没区分力）：", missed_mut)
    return 0 if (not bad and not miss and not missed_mut) else 1


if __name__ == "__main__":
    sys.exit(main())
