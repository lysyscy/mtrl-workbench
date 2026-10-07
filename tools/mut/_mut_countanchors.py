"""反向灵敏度（`T4` 的**计数锚点**（黄档 · 2026-09-24 立））—— 证明它**真会报**。

做法：把**手抄的计数**改错 ⇒ `check_count_anchors()` **必须命中**（那条锚报出）⇒ 立刻**逐字节复原**（MD5）。

⚠️ 这类"锚点型"检查最容易退化成**永远绿**（正则没命中 = 不报，没人看得出）——
   本件就是它的自证：**三条靶各改错一处 ⇒ 必须各自报一条**；⛔ 一条都不报 = 它瞎了。
⚠️ 判据**不是 rc**：锚点是**黄档**（同 `T5`/`T10` 哲学"形式问题该被看见、不挡合入"）⇒ `doc_audit` 的 rc 不变，
   要判的是"**报告里出现了那条**"（本件直接调检查函数取命中列表，最精确）。

靶：① 尾巴计数（活文档）② CMDS 定义锚（实际执行清单；TAIL-245 同批改靶）
④ `ops/阈值表.md` 自己（数字 vs 它自称的真源）。⚠️ ③（`U5` 登记数）没配靶：它的真值来自
~~`ui_parity.U5_COUNT`~~（⛔ 2026-09-30 `TAIL-201`：`U5` 退场 ⇒ 那条锚点**已撤**），改文档里的数同样会报 —— 但三条已够证明这类检查有牙，⛔ 不为凑数硬加。

用法：python tools/mut/_mut_countanchors.py
"""

from __future__ import annotations

import hashlib
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "audit"))
from audit_drift import check_count_anchors  # noqa: E402

PLAN = ROOT / ".codebuddy" / "plans" / "开发计划-主文档.md"
THRESHOLDS = ROOT / "ops" / "阈值表.md"
RUNNER = ROOT / "tools" / "oneoff" / "_run_rulers.py"

#: `(名称, 靶件, 旧串, 改成的错值, 期望命中的 what 关键词)`
#: ⚠️⚠️ 2026-10-01（`TAIL-205` 收口 · 新闸门 `_run_muts.py` 一跑就抓到）：**靶一律"现取"，⛔ 不抄数字** ——
#:   本件原先把三处靶**写死**（`已销号 **80**` / `**12 把尺子全` / `| **240** |`）⇒ 文档一改写法/一涨数字，
#:   靶就**静默失效**（实测症状：`❌ 靶串没找到 ⇒ 本件需重定靶` ＋ `0/3 命中`，而它**不在任何闸门里** ⇒ 没人知道）。
#:   ⇒ 现在三条都**按同源正则从当前文档现取**（与本文件 docstring 那条"⛔ 不抄行号"同一条纪律）。
def _tail_case(text: str) -> tuple[str, str, str]:
    """① 尾巴计数（§0.2 手抄的「已销号 N」）—— 现取并把 N 减 1。"""
    m = re.search(r"已销号 \*\*(\d+)\*\*", text)
    if not m:
        raise SystemExit("  ⛔ 找不到『已销号 **N**』锚 ⇒ 文档又改写法了 ⇒ 本件需重定靶")
    n = int(m.group(1))
    return m.group(0), m.group(0).replace(m.group(1), str(n - 1), 1), f"已销号{n - 1}"


def _ruler_case(text: str) -> tuple[str, str, str]:
    """② CMDS 清单锚移除必须报黄；历史命令不再是计数主人。"""
    m = re.search(r"(?m)^CMDS(?=:)", text)
    if not m:
        raise SystemExit("找不到 CMDS 定义锚")
    return "CMDS:", "CMDS_MISSING:", "CMDS 清单"


def _threshold_case(text: str) -> tuple[str, str, str]:
    """④ `ops/阈值表.md` 的 `README.md` 行数预算 —— 现取并把数字加 1。"""
    m = re.search(r"\| \*\*(\d+)\*\* \| `README\.md` 行数预算", text)
    if not m:
        raise SystemExit("  ⛔ 找不到『`README.md` 行数预算』那一行 ⇒ 本件需重定靶")
    n = int(m.group(1))
    return f"| **{n}** |", f"| **{n + 1}** |", f"数字 **{n + 1}**"


def build_cases(texts: dict) -> list[tuple[str, pathlib.Path, str, str, str]]:
    o1, n1, k1 = _tail_case(texts[PLAN])
    o2, n2, k2 = _ruler_case(texts[RUNNER])
    o4, n4, k4 = _threshold_case(texts[THRESHOLDS])
    return [
        ("① 尾巴计数（§0.2 手抄的「已销号」）", PLAN, o1, n1, k1),
        ("② CMDS 清单缺失必须报黄", RUNNER, o2, n2, k2),
        ("④ `ops/阈值表.md`（数字 vs 自称真源）", THRESHOLDS, o4, n4, k4),
    ]


def hits() -> list[dict]:
    return check_count_anchors()


def main() -> int:
    before = {p: p.read_bytes() for p in (PLAN, THRESHOLDS, RUNNER)}
    md5_before = {p: hashlib.md5(b).hexdigest() for p, b in before.items()}
    texts = {p: b.decode("utf-8") for p, b in before.items()}

    base = hits()
    print(f"  基线：锚点命中 {len(base)} 条（期望 0）")
    if base:
        print("  ⛔ 基线就有命中 ⇒ 先把数字改对再来跑本件")
        return 1

    cases = build_cases(texts)
    ok_all = True
    for name, target, old, new, needle in cases:
        if old not in texts[target]:
            print(f"  ❌ {name} —— 靶串没找到（文档改了？）⇒ 本件需重定靶")
            ok_all = False
            continue
        target.write_text(texts[target].replace(old, new, 1), encoding="utf-8", newline="")
        got = hits()
        target.write_bytes(before[target])                     # ⭐ 立刻复原
        found = any(needle in h["what"] for h in got)
        ok_all &= found
        print(f"  {'✅' if found else '❌'} {name} ⇒ 命中 {len(got)} 条"
              f"{'（含「' + needle + '」）' if found else ' —— ⛔ 没报到，锚点是假的'}")

    bad = [p.name for p in before
           if hashlib.md5(p.read_bytes()).hexdigest() != md5_before[p]]
    after = hits()
    print(f"\n  复原校验（MD5 逐字节）：{'✅ 全部一致' if not bad else '❌ 未复原：' + '、'.join(bad)}")
    print(f"  复原后锚点命中 {len(after)} 条（期望 0）")
    print(f"  反向灵敏度：**{len(cases) if ok_all else 0}/{len(cases)} 命中**")
    return 0 if (ok_all and not bad and not after) else 1


if __name__ == "__main__":
    sys.exit(main())
