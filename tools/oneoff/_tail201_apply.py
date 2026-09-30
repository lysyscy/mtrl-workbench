#!/usr/bin/env python
r"""`TAIL-201`（**退场**）**解耦与墓碑**（2026-09-30 · 用户裁定 · 出处 = memory §22/§23）。

`ui_parity` 的 `U1`/`U5` 已整半拆掉（本体见那份文件自己的头注）⇒ 本脚本收尾"消费者"：
- `audit_drift.py`：撤 ③ 那块 `U5_COUNT` 锚点 ＋ `_U5_ANCHOR_RE`（⚠️ 不撤它 `ui_parity` 一拆就 import 崩）
- `_mut_shell.py`：撤 `U1` 那靶（4/4 → 3/3）＋ 头注
- `_mut_countanchors.py`：头注里那句 `ui_parity.U5_COUNT` 作废
- `shell_verify.py`：`newest_snapshot` 收回私有 ＋ 把"那是 `U1`/`U5` 的活"改成**缺口已接受**
- `shell_source.py` / `audit_common.py`：两处理由已过期 ⇒ 墓碑
- `_m14_parity.py`：它伺候的 `U1`/`U5` 与登记簿都没了 ⇒ 头注标失效

⚠️ 规矩：逐处先断言命中数、写回后 round-trip 核一遍。用法：干跑 / `--write`
"""

from __future__ import annotations

import argparse
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
AUD = ROOT / "tools" / "audit"
AD, SV, SS, AC = AUD / "audit_drift.py", AUD / "shell_verify.py", AUD / "shell_source.py", AUD / "audit_common.py"
MS = ROOT / "tools" / "mut" / "_mut_shell.py"
MC = ROOT / "tools" / "mut" / "_mut_countanchors.py"
M14 = ROOT / "tools" / "probe" / "_m14_parity.py"
NL = "\r\n"

AD_BLOCK = '''    # ③ `U5` 登记条目数（真值 = `ui_parity.U5_COUNT`）
    try:
        import sys
        sys.path.insert(0, str(REPO_ROOT / "tools" / "audit"))
        from ui_parity import U5_COUNT      # noqa: PLC0415
    except Exception:                       # noqa: BLE001
        U5_COUNT = None
    if U5_COUNT is not None:
        for rel, f in docs:
            for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                for m in _U5_ANCHOR_RE.finditer(line):
                    if int(m.group(1)) != U5_COUNT:
                        out.append(_anchor(rel, i, "`U5` 登记 %s 个" % m.group(1),
                                           "`ui_parity.U5_GROUPS` 实为 **%d** 个" % U5_COUNT, line))
'''
AD_NEW = '''    # ③ ~~`U5` 登记条目数~~ —— ⛔ **已撤**（2026-09-30 `TAIL-201` 退场）：
    #    原来这里 import `ui_parity.U5_COUNT`，再核活文档里"登记 N 个规格件"那句。
    #    `U1`/`U5` 退场后那个常量不存在了 ⇒ 这条锚点连同 `_U5_ANCHOR_RE` 一起撤（⛔ 别留着 ——
    #    它会**先崩 import**：`ui_parity` 一拆，本尺子就起不来，而症状是"整把尺子报错"、不是"少一条检查"）。
'''


def _edit(p: pathlib.Path, pairs: list[tuple[str, str]], dry: bool) -> None:
    t = p.read_text(encoding="utf-8", newline="").replace("\r\n", "\n")
    for old, new in pairs:
        n = t.count(old)
        assert n == 1, f"⛔ {p.name}：锚点命中 {n} 次（期望 1）—— {old[:70]!r}"
        t = t.replace(old, new, 1)
    if not dry:
        p.write_text(t.replace("\n", NL), encoding="utf-8", newline="")
        assert p.read_text(encoding="utf-8", newline="").replace("\r\n", "\n") == t, f"⛔ {p.name} 写回不一致"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    dry = not a.write

    _edit(AD, [
        (AD_BLOCK, AD_NEW),
        ('_U5_ANCHOR_RE = re.compile(r"登记\\s*\\*{0,2}(\\d+)\\*{0,2}\\s*个规格件")',
         '# ⛔ `_U5_ANCHOR_RE` **已撤**（2026-09-30 `TAIL-201`：`U5` 退场 ⇒ 那条锚点没了；理由见上面 ③ 处）'),
    ], dry)
    print("   ✅ audit_drift.py · 撤 `U5_COUNT` 锚点 ＋ `_U5_ANCHOR_RE`（T4 由 4 类减到 3 类）")

    _edit(MS, [
        ('"""反向灵敏度（一次性）：证明 `tools/audit/ui_parity.py` 的 U1/U2/U3 有区分力 —— 改坏 ⇒ 必须变红。',
         '"""反向灵敏度（一次性）：证明 `tools/audit/ui_parity.py` 的 **U2 / U2b / U3** 有区分力 —— 改坏 ⇒ 必须变红。\n'
         '（⭐ 2026-09-30 `TAIL-201`：`U1` 那条**已退场** ⇒ 本件剩 **3 靶**；`U1` 当年守的"切片对位"改看\n'
         ' `tools/audit/shell_verify.py`（差异 ⇒ rc=1 ⇒ 复核后盖章）。）'),
        ('    ("U1 视图切片漂移", "V.m03=()=>{", "V.m03=()=>{/* 顺手改了原型逻辑 */", False),\n', ''),
    ], dry)
    print("   ✅ _mut_shell.py · 撤 `U1` 靶（4/4 → 3/3）")

    _edit(MC, [
        ("`ui_parity.U5_COUNT`",
         "~~`ui_parity.U5_COUNT`~~（⛔ 2026-09-30 `TAIL-201`：`U5` 退场 ⇒ 那条锚点**已撤**）"),
    ], dry)
    print("   ✅ _mut_countanchors.py · 头注那句作废")

    _edit(SV, [
        ("def newest_snapshot() -> Path | None:      # ⭐ 公开：`ui_parity` 也用它（基准来源**只此一处**）",
         "def _newest_snapshot() -> Path | None:     # ⭐ 2026-09-30 `TAIL-201`：收回**私有**\n"
         "    #   （`ui_parity` 的 `U1`/`U5` 已退场 ⇒ 本件是唯一用它的；⛔ 当年「提为公开」那个理由没了）"),
        ("        snap = newest_snapshot()", "        snap = _newest_snapshot()"),
        ('⇒ 它**不等于**"壳完整性有守护"：把一段代码**原样挪到别处**它看不见（那是 `ui_parity` 的 `U1`/`U5` 的活）。',
         '⇒ 它**不等于**"壳完整性有守护"：把一段代码**原样挪到别处**它看不见（多重集**不看顺序**）。\n'
         '   ⚠️ **2026-09-30 `TAIL-201`**：`ui_parity` 的 `U1`/`U5`（逐行对位）**已退场** ⇒ 这一层\n'
         '      **现在没人守**，⭐ **本轮明确接受**这个缺口（见 §15 §四 `TAIL-201` 销号行）；\n'
         '      要补就从"把本件改成**顺序**比对"下手（⛔ 别退回去再养一份"第二真源"）。'),
    ], dry)
    print("   ✅ shell_verify.py · 收回私有 ＋ 缺口写明（谁都没守 ⇒ 接受）")

    _edit(SS, [
        ("`ui_parity` 的 `U1` 是**逐行**比**基准** ⇄ 壳（⭐ 2026-09-30 `TAIL-200` 前比的是**原型**，"
         "现已换成**最新壳快照**），搬了就是无谓风险",
         "⛔ 2026-09-30 `TAIL-201` 起**没有「逐行比基准」这条尺子了**（`ui_parity` 的 `U1`/`U5` 已退场）；"
         "**切片仍别搬走** —— 搬动会在 `shell_verify`（逐行**多重集**、**不看顺序**）那边制造无谓差异，白折腾"),
    ], dry)
    _edit(AC, [
        ("#:     ⇒ 上面那条\"单边删会报红\"**已不是理由**（原型现在只是**规格留痕** ＋ 可选的历史基准）。",
         "#:     ⇒ 上面那条\"单边删会报红\"**已不是理由**（原型现在只是**规格留痕**，不再是任何尺子的基准）——\n"
         "#:     `U1`/`U5` 随后已**整半退场**（`TAIL-201`）。"),
        ("（⭐ 2026-09-30 `TAIL-200`：`U1` 已不比原型 ⇒ 这条\"不漂\"的理由**过期**，本行只为留痕）",
         "（⭐ 2026-09-30 `TAIL-201`：`U1` 已**退场** ⇒ 这条\"不漂\"的理由过期，本行只为留痕）"),
    ], dry)
    print("   ✅ shell_source.py ＋ audit_common.py · 两处理由改墓碑")

    _edit(M14, [
        ("① `ui_parity.py` 的 `U2b` 登记表加 `m14`",
         "⛔⛔ **2026-09-30 `TAIL-201`：本件已失效**（它伺候的 `U1`/`U5` 与 `ui_parity_expected.txt` 登记簿\n"
         "都已退场 ⇒ 照着跑会找不到东西）。**留作留痕**，⛔ 别照它执行。\n\n① `ui_parity.py` 的 `U2b` 登记表加 `m14`"),
    ], dry)
    print("   ✅ _m14_parity.py · 头注标失效（留痕）")

    print("\n（干跑：⛔ 未写）" if dry else "\n✅ 解耦与墓碑完成")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
