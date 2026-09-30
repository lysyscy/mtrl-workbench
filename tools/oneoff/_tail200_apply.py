#!/usr/bin/env python
r"""`TAIL-200` `A` 案**改码**（2026-09-30）：把 `ui_parity` 的基准从「交付面那份交互原型」
换成「**`.workbuddy/backups/` 里最新那份壳单文件基线**」＋ 登记簿归档 ＋ 三处口径订正。

⚠️ 规矩同其他 `_apply_*.py`：逐处先断言命中数、写回后 round-trip 核一遍；⛔ 不动交付面（原型只读）。

用法：`python tools/oneoff/_tail200_apply.py`（干跑）· `… --write`
"""

from __future__ import annotations

import argparse
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
AUD = ROOT / "tools" / "audit"
SV = AUD / "shell_verify.py"
UP = AUD / "ui_parity.py"
SS = AUD / "shell_source.py"
AC = AUD / "audit_common.py"
MU5 = ROOT / "tools" / "mut" / "_mut_u5.py"
REG = ROOT / "tools" / "ui_parity_expected.txt"
ARCH_DIR = ROOT / "tools" / "oneoff" / "_归档-20260930"
ARCH = ARCH_DIR / "ui_parity_expected-原型基准期.txt"
NL = "\r\n"

HEAD_UP = '''"""**壳一致性核对器**（基准 ⇄ 前端壳）· **纯 Python · 不依赖浏览器**。

**⭐ 基准 = `.workbuddy/backups/` 里最新那份「壳单文件基线」**（2026-09-30 `TAIL-200` `A` 案 · 用户裁定 ·
原为交付面那份交互原型）—— `shell_verify.py --snapshot` 盖的章就是它。⭐ 为什么换（用户原话）：
「原型在我看来就是 **1.0 版本**，我们现在的版本可能已经到 **6789** 了……为啥要在更新版本的时候，
把改动**同步到 1.0**？」⇒ 换掉之后：① **双边同步消失**（改壳不必再往原型抄一份同样的字节）；
② 原型**退成只读归档**（不再是任何尺子的基准；需要时用 `--proto <路径>` 显式指它）；
③ 本件**语义不变**（见下表 `U1`/`U5`：守的仍是"壳有没有无声漂离**大家批准过的那个样子**"，
只是"那个样子"从**另一份文件**变成了**上一版壳的快照**）；④ ⭐ **跑本件不再需要交付面**
（目标机上也能跑 ⇒ `docs/deployment.md` 同批订正）。⛔ **缺基准直接判红**（⛔ 不回落原型 ——
闸门没基准 = 没在工作）。

**⚠️ 与 `shell_verify` 的分工（有重叠 · 已立 `TAIL-201` 议）**：`shell_verify` = 逐行**多重集**（盖章制 ·
抓变异残留）；本件 = 逐行**对位 ＋ 登记理由**（抓"无声漂移"并留下**为什么**）。两者现在**同一个基准**。

**（以下是上一轮的口径留痕 · ⛔ 别删）**'''

OLD_U1 = ('| `U1` | ⭐⭐ **原型逻辑一行不改**（D18 的硬约束）—— 把原型的筛选 / 排序 / 合计 / 勾选逻辑'
          '**顺手改掉**，就再没有"规格"可言了 | 壳的每个 `V.<页>` 切片 与原型同名切片**逐行一致**；'
          '差异未登记 ⇒ **红**（登记簿 `tools/ui_parity_expected.txt` · ⭐ 2026-09-25 起**可增可减**：'
          '新功能产生的正当差异照登；补回原型/消号时删行） |')
NEW_U1 = ('| `U1` | ⭐⭐ **切片 `V.<页>` 相对基准逐行一致** —— **无声漂移**（改了却没人知道）是这一路最贵的病：'
          '`P4`/`P5` 几十处都拿"**零可见变化**"当合同（⭐ 2026-09-30 前这条的原话是"**原型逻辑一行不改**"：'
          '那时基准是原型，"改一处就得往原型抄一处"） | 壳的每个 `V.<页>` 切片 与**基准**同名切片**逐行一致**；'
          '差异未登记 ⇒ **红**（登记簿 `tools/ui_parity_expected.txt` · ⭐ 2026-09-25 起**可增可减**：'
          '正当差异照登、消号人工删行） |')

NEW_RESOLVE = '''    if args.proto:
        base = pathlib.Path(args.proto)                 # 显式指定基准（历史对账 / 反向灵敏度拿临时副本用）
    else:
        base = newest_snapshot()
        if base is None:
            print("⛔ 找不到基准：`.workbuddy/backups/` 里没有「壳单文件基线」—— 闸门没有基准 = 闸门没在工作，"
                  "⛔ 不静默放行（也⛔ 不回落原型：那是 `TAIL-200` 换掉的旧口径）。")
            print("   修法：① 复核当前壳（真机 `tools/probe/_shell_smoke.py` 整支 rc=0 ＋ 确认没在变异态）")
            print("         ② 跑 `python tools/audit/shell_verify.py --snapshot` 建一份基线")
            return 1
    if not base.exists():
        print(f"⛔ 找不到基准文件：{base}")
        return 1'''


def _sub(p: pathlib.Path, pairs: list[tuple[str, str]], dry: bool) -> None:
    t = p.read_text(encoding="utf-8", newline="").replace("\r\n", "\n")
    for old, new in pairs:
        n = t.count(old)
        assert n == 1, f"⛔ {p.name}：锚点命中 {n} 次（期望 1）—— {old[:60]!r}"
        t = t.replace(old, new, 1)
    if not dry:
        p.write_text(t.replace("\n", NL), encoding="utf-8", newline="")
        back = p.read_text(encoding="utf-8", newline="").replace("\r\n", "\n")
        assert back == t, f"⛔ {p.name} 写回不一致"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    dry = not a.write

    _sub(SV, [
        ("def _newest_snapshot() -> Path | None:",
         "def newest_snapshot() -> Path | None:      # ⭐ 公开：`ui_parity` 也用它（基准来源**只此一处**）"),
        ("        snap = _newest_snapshot()", "        snap = newest_snapshot()"),
    ], dry)
    print("   ✅ shell_verify.py · `newest_snapshot` 提为公开（供 ui_parity 复用，⛔ 不复制一份）")

    _sub(UP, [
        ('"""**壳一致性核对器**（原型 ⇄ 前端壳）· **纯 Python · 不依赖浏览器**。', HEAD_UP),
        ("from shell_source import SHELL_PARTS, SHELL_PATH, read_shell  # noqa: E402  ← `P4`① 读取点收敛",
         "from shell_source import SHELL_PARTS, SHELL_PATH, read_shell  # noqa: E402  ← `P4`① 读取点收敛\n"
         "from shell_verify import newest_snapshot  # noqa: E402  ← ⭐ 基准来源**只此一处**"
         "（`TAIL-200`：⛔ 不复制一份找快照的逻辑）"),
        ('PROTO = pathlib.Path(r"D:\\工作\\AI\\PRD编写夹 - Workbuddy专用\\demo\\材料报表自动化工作台-交互原型.html")\n',
         "#: ⭐ `TAIL-200`（2026-09-30）：**默认基准不再是原型** —— 改成**最新那份壳快照**"
         "（`newest_snapshot()`）。\n"
         "#: 原型现在只作**历史对账**用（`--proto <路径>` 显式指它；交付面 §二 那份已退成**只读归档**）。\n"
         "PROTO: pathlib.Path | None = None   #: ⛔ **别给它默认值** —— 给了，「双边同步」就会悄悄回来"
         "（`backend/tests/test_ui_parity_base.py`（已删 · 见 `_tail201_docs.py`）会当场红）\n"),
        (OLD_U1, NEW_U1),
        ("**壳公共件 ⇄ 原型里嵌的同段，逐行一致**（`TAIL-65` · 2026-09-23 立）",
         "**壳公共件 ⇄ 基准里嵌的同段，逐行一致**（`TAIL-65` · 2026-09-23 立）"),
        ("登记表里的每个顶层件，**原型与壳必须逐字一致**（哈希比对）",
         "登记表里的每个顶层件，**基准与壳必须逐字一致**（哈希比对）"),
        ('    ap.add_argument("--proto", default=None, help="原型路径（默认 = 交付面那份）")',
         '    ap.add_argument("--proto", default=None,\n'
         '                    help="显式指定**基准**路径（默认 = `.workbuddy/backups/` 里最新那份'
         '「壳单文件基线」；给老原型路径 = 历史对账）")'),
        ('    proto = pathlib.Path(args.proto) if args.proto else PROTO\n'
         '    if not proto.exists():\n'
         '        print(f"⛔ 找不到原型：{proto}（它不在工程仓里，属交付面）")\n'
         '        return 1', NEW_RESOLVE),
        ("    p_views = slices(read_lines(proto))", "    p_views = slices(read_lines(base))"),
        ('        p_seg, s_seg = top_segs(proto.read_text(encoding="utf-8")), '
         'top_segs("\\n".join(shell_lines))',
         '        p_seg, s_seg = top_segs(base.read_text(encoding="utf-8")), '
         'top_segs("\\n".join(shell_lines))'),
        ('        print(f" U5 候选扫描 —— 原型 {proto.name}（{len(p_seg)} 个顶层段） ⇄ 壳（{len(s_seg)} 个）")',
         '        print(f" U5 候选扫描 —— 基准 {base.name}（{len(p_seg)} 个顶层段） ⇄ 壳（{len(s_seg)} 个）")'),
        ('    p_seg = top_segs(proto.read_text(encoding="utf-8"))',
         '    p_seg = top_segs(base.read_text(encoding="utf-8"))'),
        ('    print(f" 原型 {proto.name}（{len(p_views)} 个视图）  ⇄  壳（{len(s_views)} 个视图 · '
         '{len(SHELL_PARTS)} 件）")',
         '    print(f" 基准 {base.name}（{len(p_views)} 个视图）  ⇄  壳（{len(s_views)} 个视图 · '
         '{len(SHELL_PARTS)} 件）")'),
        ('                u1.append({"key": key, "line": i + 1, "proto": a[:160], "shell": b[:160],',
         '                u1.append({"key": key, "line": i + 1, "base": a[:160], "shell": b[:160],'),
        ('            "# 格式：`<页> <指纹> [备注]`；指纹 = md5(原型行 + \'||\' + 壳行)[:8]。",',
         '            "# 格式：`<页> <指纹> [备注]`；指纹 = md5(基准行 + \'||\' + 壳行)[:8]。",'),
        ('        add = [f"{d[\'key\']} {d[\'fp\']}  # 原型: {d[\'proto\'][:50]}｜壳: {d[\'shell\'][:50]}"',
         '        add = [f"{d[\'key\']} {d[\'fp\']}  # 基准: {d[\'base\'][:50]}｜壳: {d[\'shell\'][:50]}"'),
        ("    #    `--proto` 让反向灵敏度能**拿一份临时副本**证明\"原型那侧改了也红\"（⛔ 不必去动交付面）；",
         "    #    `--proto` = **显式指定基准路径**（⭐ `TAIL-200` 起默认基准是壳快照）；反向灵敏度拿一份"
         "**临时副本**证明\"基准那侧改了也红\"（⛔ 不必去动交付面）；"),
    ], dry)
    print("   ✅ ui_parity.py · 基准换成壳快照（缺基准判红 ＋ `--proto` 仍可显式指）＋ 文案/键名对齐")

    _sub(SS, [
        ("`ui_parity` 的 `U1` 是**逐行**比原型 ⇄ 壳，搬了就是无谓风险",
         "`ui_parity` 的 `U1` 是**逐行**比**基准** ⇄ 壳（⭐ 2026-09-30 `TAIL-200` 前比的是**原型**，"
         "现已换成**最新壳快照**），搬了就是无谓风险"),
    ], dry)
    _sub(AC, [
        ("#:   · 它同时是 `ui_parity` 的**基准** ⇒ 单边删会立刻报红。",
         "#:   · 它同时是 `ui_parity` 的**基准** ⇒ 单边删会立刻报红。\n"
         "#:   · ⭐ **2026-09-30 订正**（`TAIL-200` `A` 案）：`ui_parity` 的基准**已换成「最新那份壳快照」**\n"
         "#:     ⇒ 上面那条\"单边删会报红\"**已不是理由**（原型现在只是**规格留痕** ＋ 可选的历史基准）。\n"
         "#:     ⛔ 但**裁定不变**：原型与文档里的残片**照旧别清** —— 它记的是\"当初为什么会撤\"。"),
        ("② 壳 `backend/app/web/index.html` 的 `V.m12` 切片内（**与 ① 逐行完全相同** —— "
         "这样 `ui_parity` 的 `U1` 不漂）",
         "② 壳 `backend/app/web/index.html` 的 `V.m12` 切片内（**与 ① 逐行完全相同** —— "
         "这样 `ui_parity` 的 `U1` 不漂）（⭐ 2026-09-30 `TAIL-200`：`U1` 已不比原型 ⇒ "
         "这条\"不漂\"的理由**过期**，本行只为留痕）"),
    ], dry)
    print("   ✅ shell_source.py ＋ audit_common.py · 三处口径订正（理由过期 ≠ 裁定作废）")

    _sub(MU5, [
        ("真守得住「壳公共件 ⇄ 原型同段」。",
         "真守得住「壳公共件 ⇄ **基准**同段」。\n\n"
         "（⭐ 2026-09-30 `TAIL-200`：基准已从**原型**换成**最新壳快照** —— `M2` 那支"
         "\"基准侧漂移\"照旧拿 `--proto` 指一份**临时副本** ✓；⛔ 从不打开写交付面那份。）"),
    ], dry)
    print("   ✅ _mut_u5.py · 文案对齐（两靶不变）")

    # ── 登记簿：归档旧条目（原型基准期）＋ 立一份只有头的新登记簿
    old = REG.read_text(encoding="utf-8", newline="").replace("\r\n", "\n") if REG.exists() else ""
    n_entries = sum(1 for l in old.split("\n") if l.strip() and not l.strip().startswith("#"))
    if dry:
        print(f"   （干跑）登记簿：将归档 {n_entries} 条历史登记 ⇒ {ARCH.relative_to(ROOT)}，并新建空登记簿")
    else:
        ARCH_DIR.mkdir(parents=True, exist_ok=True)
        ARCH.write_text(
            "# 归档：`ui_parity` 的**原型基准期**漂移登记簿（2026-09-30 `TAIL-200` `A` 案换基准时整体留痕）\n"
            "# ⚠️ 这些条目记的是「壳 ⇄ **交付面那份交互原型**」的差异 —— 基准换成壳快照后它们**不再被读**\n"
            "#    （⛔ 别删：那是 2026-09-20 以来几十批「零可见变化」改动的**原始理由**）。\n\n"
            + old, encoding="utf-8", newline="")
        REG.write_text(
            "# 壳一致性核对器 · 已登记漂移（ui_parity_expected.txt）\n"
            "# ⭐ 基准 = `.workbuddy/backups/` 里最新那份「壳单文件基线」（2026-09-30 `TAIL-200` `A` 案起）。\n"
            "# ⚠️ **原型基准期**的历史登记（" + str(n_entries) + " 条）已归档 ⇒\n"
            "#    `tools/oneoff/_归档-20260930/ui_parity_expected-原型基准期.txt`（⛔ 别删，那是留痕）。\n"
            "# 格式：`<页> <指纹> [备注]`；指纹 = md5(基准行 + '||' + 壳行)[:8]。\n"
            "# ⚠️ **可增可减**：正当差异照登（`--write-expected` 只追加）；消号**人工删行**。\n",
            encoding="utf-8", newline="")
        assert REG.read_text(encoding="utf-8").count("\n") < 40, "⛔ 新登记簿不该有内容"
        print(f"   ✅ 登记簿 · 归档 {n_entries} 条 ⇒ {ARCH.relative_to(ROOT)} ＋ 新建空登记簿")

    print("\n（干跑：⛔ 未写）" if dry else "\n✅ 改码完成")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
