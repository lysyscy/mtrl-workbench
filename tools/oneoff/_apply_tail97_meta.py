"""`TAIL-97` 一次性补丁（第二片）：**看板 9 项 ⇒ 8 项** 连带要改的**文本面**。

覆盖 6 件（探针件 / 断言件 / 变异件 / 文档 / 后端注释）—— 都是"与 `jcPending` 相关的**计数与措辞**"。
⚠️ 其中三件是 **CRLF**（`_shell_home.py` / `_shell_smoke.py` / `docs/modules.md`）⇒ 同 `_apply_tail97_two_state.py`：
先归一到 `\\n`、改完按原风格还原，且**先做 round-trip 逐字节比对**；⛔ 不整份重写（那会把整个文件刷成"全改"）。

用法：
  `backend/.venv/Scripts/python.exe tools/oneoff/_apply_tail97_meta.py`          # 只报不写
  `backend/.venv/Scripts/python.exe tools/oneoff/_apply_tail97_meta.py --apply`  # 真写
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

HOME_PROBE = ROOT / "tools" / "probe" / "_shell_home.py"
SMOKE = ROOT / "tools" / "probe" / "_shell_smoke.py"
HOME_TEST = ROOT / "backend" / "tests" / "test_acc_home_todo.py"
MUT = ROOT / "tools" / "mut" / "_mut_home_wired.py"
MODULES = ROOT / "docs" / "modules.md"
HOME_ROUTER = ROOT / "backend" / "app" / "home" / "router.py"

#: {文件: [(说明, 原文, 改成, 期望命中次数)]}
PLAN: dict[Path, list[tuple[str, str, str, int]]] = {
    HOME_PROBE: [
        ("docstring：① 看板 9 项 ⇒ 8 项",
         "  ① 看板 9 项待办**都在**（把手集合是契约）；",
         "  ① 看板 8 项待办**都在**（把手集合是契约）；", 1),
        ("`KEYS`：去掉 `jcPending`",
         'KEYS = ["ntUnapproved", "ownership", "planUnmatched", "jcPending", "dfPending",\n'
         '        "placeholder", "fetchDue", "fetchFail", "printFail"]',
         'KEYS = ["ntUnapproved", "ownership", "planUnmatched", "dfPending",\n'
         '        "placeholder", "fetchDue", "fetchFail", "printFail"]', 1),
        ("`check` 的 docstring：9 项 ⇒ 8 项",
         '    """⑲ 真机走一遍：**回看板 → 9 项待办 → 三个记账数与后端对齐 → 去向与失败时间**。"""',
         '    """⑲ 真机走一遍：**回看板 → 8 项待办 → 三个记账数与后端对齐 → 去向与失败时间**。"""', 1),
        ("真机等待条件：瓦片数 `=== 9` ⇒ `=== 8`",
         "\"() => document.querySelectorAll('[data-todo]').length === 9\", timeout=15000)",
         "\"() => document.querySelectorAll('[data-todo]').length === 8\", timeout=15000)", 1),
        ("阶段名：读 9 项 ⇒ 8 项",
         '        stage = "读 9 项与后端账"',
         '        stage = "读 8 项与后端账"', 1),
        ("断言说明：9 项 ⇒ 8 项",
         'f"9 项待办把手齐全且顺序不变（',
         'f"8 项待办把手齐全且顺序不变（', 1),
    ],
    SMOKE: [
        ("编排件里那句注释：9 项 ⇒ 8 项",
         "# ---- ⑲ 看板接真数据（`§19` 批 5）—— 9 项待办 ＋ 三个记账数与后端对齐 ＋ 那句假话已不在，挪 `_shell_home.py`。",
         "# ---- ⑲ 看板接真数据（`§19` 批 5）—— 8 项待办 ＋ 三个记账数与后端对齐 ＋ 那句假话已不在，挪 `_shell_home.py`。", 1),
    ],
    HOME_TEST: [
        ("模块 docstring：9 项待办 ⇒ 8 项",
         '"""`ACC-HOME-TODO-001` —— 看板（默认落地页）= 待办页 · 9 项待办。',
         '"""`ACC-HOME-TODO-001` —— 看板（默认落地页）= 待办页 · 8 项待办。', 1),
        ("`KEYS` / `DEST`：去掉 `jcPending` 这一项",
         '#: 9 项把手（**顺序也是契约** —— 看板按此序展示）\n'
         'KEYS = ("ntUnapproved", "ownership", "planUnmatched", "jcPending", "dfPending",\n'
         '        "placeholder", "fetchDue", "fetchFail", "printFail")\n'
         "\n"
         "#: 每项的去向页（`data-k`）—— ⚠️ `dfPending` 2026-09-21 由 `m12`（已撤页）改指 `m08`\n"
         'DEST = {"ntUnapproved": "m03", "ownership": "m03", "planUnmatched": "m04", "jcPending": "m11",\n'
         '        "dfPending": "m08", "placeholder": "m01", "fetchDue": "m02", "fetchFail": "m02",\n'
         '        "printFail": "m03"}',
         '#: 8 项把手（**顺序也是契约** —— 看板按此序展示）\n'
         '#: ⭐ `TAIL-97`（2026-09-25）：`jcPending`（集采合同待确认）**已撤** ⇒ 9 项 ⇒ 8 项。\n'
         'KEYS = ("ntUnapproved", "ownership", "planUnmatched", "dfPending",\n'
         '        "placeholder", "fetchDue", "fetchFail", "printFail")\n'
         "\n"
         "#: 每项的去向页（`data-k`）—— ⚠️ `dfPending` 2026-09-21 由 `m12`（已撤页）改指 `m08`\n"
         'DEST = {"ntUnapproved": "m03", "ownership": "m03", "planUnmatched": "m04",\n'
         '        "dfPending": "m08", "placeholder": "m01", "fetchDue": "m02", "fetchFail": "m02",\n'
         '        "printFail": "m03"}', 1),
        ("用例名：九项 ⇒ 八项",
         "def test_九项待办把手齐全不重不漏():",
         "def test_八项待办把手齐全不重不漏():", 1),
        ("用例 docstring：9 项 ⇒ 8 项",
         '    """⭐ **9 项**、把手集合固定、**顺序即契约**。"""',
         '    """⭐ **8 项**、把手集合固定、**顺序即契约**（`TAIL-97` 撤掉 `jcPending`）。"""', 1),
        ("把手去重断言：`== 9` ⇒ `== 8`",
         '    assert len(set(got)) == 9, "把手有重复"',
         '    assert len(set(got)) == 8, "把手有重复"', 1),
        ("`want_expr`：去掉 `jcPending → nJc`",
         '        "ntUnapproved": "nUn", "ownership": "nOwn", "planUnmatched": "nPl", "jcPending": "nJc",\n'
         '        "dfPending": "nAdj", "placeholder": "ph.length",',
         '        "ntUnapproved": "nUn", "ownership": "nOwn", "planUnmatched": "nPl",\n'
         '        "dfPending": "nAdj", "placeholder": "ph.length",', 1),
        ("口径表达式清单：删掉 `nJc` 那一行",
         '        "const nJc =JCs.filter(j=>j.tag===\'待确认\').length;",\n',
         "", 1),
        ("用例名：九项都可点击 ⇒ 八项",
         "def test_九项都可点击跳到对应页():",
         "def test_八项都可点击跳到对应页():", 1),
        ("`001-09`：`nJc` 断言 ⇒ 改成「不许再数待确认」",
         '    assert "const nJc =JCs.filter(j=>j.tag===\'待确认\').length;" in block\n'
         '    assert "const nAdj=IVs.filter(iv=>adjOf(iv)).length;" in block',
         '    assert "const nAdj=IVs.filter(iv=>adjOf(iv)).length;" in block\n'
         '    # ⭐ `TAIL-97`：`jcPending`（集采待确认）**已撤** ⇒ ④ 号那条口径出口**不许再出现**\n'
         '    assert "nJc" not in block, "看板又数起了「集采待确认」（该待办已撤）"', 1),
        ("`001-09`：`jcPending` 必须**不在**瓦片里",
         '    assert "jcPending" in calls and "dfPending" in calls',
         '    assert "dfPending" in calls\n'
         '    assert "jcPending" not in calls, "看板的「集采待确认」瓦片已撤（TAIL-97）"', 1),
        ("坟头注释：9 项口径出口 ⇒ 8 项",
         '    assert not (home_dir / "domain.py").exists(), "旧看板的 9 项口径出口 `domain.py` 又回来了"',
         '    assert not (home_dir / "domain.py").exists(), "旧看板的 8 项口径出口 `domain.py` 又回来了"', 1),
    ],
    MUT: [
        ("变异件引用的用例名：九项 ⇒ 八项（⛔ 不改就会「找不到用例」）",
         '        "test_九项都可点击跳到对应页",',
         '        "test_八项都可点击跳到对应页",', 1),
    ],
    MODULES: [
        ("模块表：看板 9 项待办 ⇒ 8 项",
         "| — | 看板·待办 | 随各包给数据 | `home` | ✅ 9 项待办（不占模块号） |",
         "| — | 看板·待办 | 随各包给数据 | `home` | ✅ 8 项待办（不占模块号） |", 1),
    ],
    HOME_ROUTER: [
        ("后端注释：9 项待办的口径出口 ⇒ 8 项",
         "`home/domain.py`（9 项待办的口径出口，",
         "`home/domain.py`（8 项待办的口径出口，", 1),
    ],
}


def main() -> int:
    apply = "--apply" in sys.argv
    errors: list[str] = []
    todo: list[tuple[Path, str, bool, str]] = []

    for path, items in PLAN.items():
        raw = path.read_bytes()
        crlf = b"\r\n" in raw
        text = raw.decode("utf-8").replace("\r\n", "\n")
        back = text.replace("\n", "\r\n") if crlf else text
        if back.encode("utf-8") != raw:
            errors.append(f"{path.name}｜行尾 round-trip 不一致 ⇒ ⛔ 先查行尾假设")
            continue
        for desc, old, new, want in items:
            n = text.count(old)
            if n != want:
                errors.append(f"{path.name}｜{desc} —— 命中 {n} 次（期望 {want}）")
                continue
            text = text.replace(old, new, want)
        todo.append((path, text, crlf, text))

    print("=" * 78)
    print(("  写入" if apply else "  DRY-RUN（只报不写）") + " ·  TAIL-97「9 项 ⇒ 8 项」文本面补丁")
    print("=" * 78)
    for path, _t, crlf, _x in todo:
        raw = path.read_bytes()
        print(f"  {path.relative_to(ROOT)!s:<46} 行尾={'CRLF' if crlf else 'LF'}  "
              f"替换 {len(PLAN[path])} 条")

    if errors:
        print("\n⛔ 有锚点对不上 ⇒ **一行都没写**：")
        for e in errors:
            print("   " + e)
        return 1

    if apply:
        for path, text, crlf, _x in todo:
            path.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))
        print("\n  ✅ 已写盘。")
    else:
        print("\n  （加 --apply 才真写。）")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
