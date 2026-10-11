"""`TAIL-97` 一次性补丁（第四片）：**交付面 `demo/_smoke.js`** —— 原型自检里钉着旧口径的断言。

**为什么要改它**：`_smoke` 是交付面四检之一（`doc_audit --ui`），§22.1 每轮都跑；
  改原型（`ENUMS` / `V.home` / `V.m11` / 演示数据）之后，它按旧口径必红（实测 **7 条**失败）。

⚠️ 其中一条是"**退化成空转**"的（`#fTag = '待确认'` 筛出 0 行 ⇒ 两条断言恒真）
   —— 一并把它改成用「不纳入」收窄，把**区分力**拿回来（⛔ 不是把期望值改大了事）。

用法：
  `backend/.venv/Scripts/python.exe tools/oneoff/_apply_tail97_smoke.py`          # 只报不写
  `backend/.venv/Scripts/python.exe tools/oneoff/_apply_tail97_smoke.py --apply`  # 真写
"""

from __future__ import annotations

import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SMOKE = Path(r"D:\工作\AI\PRD编写夹 - Workbuddy专用\demo\_smoke.js")
BACKUPS = ROOT / ".workbuddy" / "backups"

EDITS: list[tuple[str, str, str]] = [
    ("`M10` 集采筛选生效：两态的实际条数",
     "guard('M10｜MOD-11 三态筛选生效（待确认 3 / 纳入 8 / 全部 12）', () => {\n"
     "  /* 每行恰好一个「付款子表」入口 ⇒ 用它数行（原 `jcDetail` 已随\"子表拆开\"删除） */\n"
     "  const cnt = () => (V.m11().match(/data-act=\"jcPayDlg\"/g) || []).length;\n"
     "  X.fJc.tag = '待确认'; const a = cnt();\n"
     "  X.fJc.tag = '纳入台账'; const b = cnt();\n"
     "  X.fJc.tag = '全部'; const c = cnt();\n"
     "  if (!(a === 3 && b === 8 && c === 12)) throw new Error(`待确认 ${a} / 纳入 ${b} / 全部 ${c}`);\n"
     "});",
     "guard('M10｜MOD-11 两态筛选生效（纳入 11 / 不纳入 1 / 全部 12；⭐ TAIL-97：待确认已取消）', () => {\n"
     "  /* 每行恰好一个「付款子表」入口 ⇒ 用它数行（原 `jcDetail` 已随\"子表拆开\"删除） */\n"
     "  const cnt = () => (V.m11().match(/data-act=\"jcPayDlg\"/g) || []).length;\n"
     "  X.fJc.tag = '纳入台账'; const b = cnt();\n"
     "  X.fJc.tag = '不纳入'; const a = cnt();\n"
     "  X.fJc.tag = '全部'; const c = cnt();\n"
     "  if (!(b === 11 && a === 1 && c === 12)) throw new Error(`纳入 ${b} / 不纳入 ${a} / 全部 ${c}`);\n"
     "});"),
    ("`N7` 操作列按钮：改成两态互切",
     "ck('N7｜操作列按钮已改名「是否纳入台账」，且不再叫「改标记」', (function () {\n"
     "  const h = V.m11();   /* 默认筛选（全部）里 9 条非「待确认」行 ⇒ 该按钮必定出现 */\n"
     "  return (h.indexOf('>是否纳入台账<') >= 0 && h.indexOf('>改标记<') < 0) ? 1 : 0;\n"
     "})(), 1);",
     "ck('N7｜操作列按钮是**两态互切**（「纳入台账」/「不纳入」），且不再叫「改标记」', (function () {\n"
     "  const h = V.m11();   /* ⭐ TAIL-97：没有「是否纳入台账」那种\"回到待确认\"的写法了 */\n"
     "  return (h.indexOf('>不纳入<') >= 0 && h.indexOf('>纳入台账<') >= 0\n"
     "    && h.indexOf('>是否纳入台账<') < 0 && h.indexOf('>改标记<') < 0) ? 1 : 0;\n"
     "})(), 1);"),
    ("手工新增：默认值 ⇒ 纳入台账",
     "    if (j.tag !== '待确认') throw new Error('三态默认应为「待确认」：' + j.tag);",
     "    if (j.tag !== '纳入台账') throw new Error('默认应为「纳入台账」（TAIL-97 取消「待确认」· 与抓取行同一个默认值）：' + j.tag);"),
    ("枚举值域表：`jcTag` 去掉「待确认」",
     "      jcTag: ['待确认', '纳入台账', '不纳入'], jcArch: ['未存档', '资产处', '已存档'],",
     "      jcTag: ['纳入台账', '不纳入'], jcArch: ['未存档', '资产处', '已存档'],"),
    ("批量标记「收窄后裁剪」：改用「不纳入」把**区分力**拿回来（原用「待确认」筛出 0 行 ⇒ 两条断言恒真）",
     "    doc.querySelector('#fTag').value = '待确认'; ACT.jcFilter({ dataset: {}, tagName: 'SELECT' });\n"
     "    const vis = X.jcVisible().length;\n"
     "    if (vis >= X.JCs.length) throw new Error('筛选未生效，测试无效');\n"
     "    if (X.jcPick.size !== vis) throw new Error(`筛选后勾选应裁剪到 ${vis}，实际 ${X.jcPick.size}`);\n"
     "    ACT.jcBatchTag({ dataset: { v: '纳入台账' }, tagName: 'BUTTON' });\n"
     "    if (X.JCs.filter(j => j.tag === '待确认').length !== 0) throw new Error('批量标记未覆盖全部可见行');",
     "    /* ⭐ TAIL-97：改用「不纳入」收窄 —— 原来用「待确认」（该值已取消，筛出 0 行）\n"
     "       ⇒ `vis >= X.JCs.length` 与「全被标记」两条断言**退化成空转**（0 < 12 恒真）。 */\n"
     "    doc.querySelector('#fTag').value = '不纳入'; ACT.jcFilter({ dataset: {}, tagName: 'SELECT' });\n"
     "    const vis = X.jcVisible().length;\n"
     "    if (vis <= 0 || vis >= X.JCs.length) throw new Error('筛选未生效，测试无效');\n"
     "    if (X.jcPick.size !== vis) throw new Error(`筛选后勾选应裁剪到 ${vis}，实际 ${X.jcPick.size}`);\n"
     "    ACT.jcBatchTag({ dataset: { v: '纳入台账' }, tagName: 'BUTTON' });\n"
     "    if (X.JCs.filter(j => j.tag === '不纳入').length !== 0) throw new Error('批量标记未覆盖全部可见行');"),
    ("10f 段标题：9 项 ⇒ 8 项（并去掉已不产出的 `§6.5.3`）",
     "  console.log('\\n--- 10f. 看板页 = 待办页（9 项待办 · §3.1.3 / §4.6 / §4.3.4 / §5.8.3 / §6.5.3 / §2.5.1 / §2.4.2）---');",
     "  console.log('\\n--- 10f. 看板页 = 待办页（8 项待办 · §3.1.3 / §4.6 / §4.3.4 / §5.8.3 / §2.5.1 / §2.4.2；⭐ TAIL-97 撤 jcPending）---');"),
    ("`homeTodo()` 的 keys：去掉 `jcPending`",
     "    const keys = ['ntUnapproved', 'ownership', 'planUnmatched', 'jcPending', 'dfPending', 'placeholder', 'fetchDue', 'fetchFail', 'printFail'];",
     "    const keys = ['ntUnapproved', 'ownership', 'planUnmatched', 'dfPending', 'placeholder', 'fetchDue', 'fetchFail', 'printFail'];"),
    ("把手齐全：8 项",
     "  guard('§5·看板｜9 项待办的把手齐全（`data-todo` 恰好 9 个、不重不漏）', () => {\n"
     "    const got = [...String(X.V.home()).matchAll(/data-todo=\"([^\"]+)\"/g)].map(m => m[1]);\n"
     "    const want = ['ntUnapproved', 'ownership', 'planUnmatched', 'jcPending', 'dfPending', 'placeholder', 'fetchDue', 'fetchFail', 'printFail'];\n"
     "    if (got.length !== 9) throw new Error('data-todo 个数 = ' + got.length + '（应为 9）');\n"
     "    if (new Set(got).size !== 9) throw new Error('data-todo 有重复：' + got.join(','));",
     "  guard('§5·看板｜8 项待办的把手齐全（`data-todo` 恰好 8 个、不重不漏；⭐ TAIL-97 撤 jcPending）', () => {\n"
     "    const got = [...String(X.V.home()).matchAll(/data-todo=\"([^\"]+)\"/g)].map(m => m[1]);\n"
     "    const want = ['ntUnapproved', 'ownership', 'planUnmatched', 'dfPending', 'placeholder', 'fetchDue', 'fetchFail', 'printFail'];\n"
     "    if (got.length !== 8) throw new Error('data-todo 个数 = ' + got.length + '（应为 8）');\n"
     "    if (new Set(got).size !== 8) throw new Error('data-todo 有重复：' + got.join(','));"),
    ("独立复算表：去掉 `jcPending` 那一行",
     "      jcPending: X.JCs.filter(j => j.tag === '待确认').length,\n",
     ""),
    ("每项可点：8 项",
     "  guard('§5·看板｜9 项每项都「可点」：`data-act=\"go\"` + `data-k` 是已注册视图 + 键盘可达（R13 无障碍）', () => {",
     "  guard('§5·看板｜8 项每项都「可点」：`data-act=\"go\"` + `data-k` 是已注册视图 + 键盘可达（R13 无障碍）', () => {"),
]


def main() -> int:
    apply = "--apply" in sys.argv
    raw = SMOKE.read_bytes()
    crlf = b"\r\n" in raw
    text = raw.decode("utf-8").replace("\r\n", "\n")
    back = text.replace("\n", "\r\n") if crlf else text
    if back.encode("utf-8") != raw:
        print("⛔ 行尾 round-trip 不一致 ⇒ 不动")
        return 1

    errors: list[str] = []
    for desc, old, new in EDITS:
        n = text.count(old)
        if n != 1:
            errors.append(f"{desc} —— 命中 {n} 次（期望 1）")
            continue
        text = text.replace(old, new, 1)

    print("=" * 80)
    print(("  写入" if apply else "  DRY-RUN（只报不写）") + " ·  TAIL-97 交付面 `demo/_smoke.js` 断言同步")
    print("=" * 80)
    print(f"  {SMOKE.name} · 行尾={'CRLF' if crlf else 'LF'} · 替换 {len(EDITS)} 条")
    if errors:
        print("\n⛔ 有锚点对不上 ⇒ **一个字节都没写**：")
        for e in errors:
            print("   " + e)
        return 1
    if not apply:
        print("\n  （加 --apply 才真写。）")
        return 0

    BACKUPS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    shutil.copy2(SMOKE, BACKUPS / f"face-{stamp}-_smoke.js")
    SMOKE.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))
    print("\n  ✅ 已写盘 ＋ 备份完成。")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
