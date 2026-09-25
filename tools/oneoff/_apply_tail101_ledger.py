"""`TAIL-101` 台账：**销号**（§一 撤行 → §四 留痕 · 计数 A 6→5 · 已销号 98→99 · §14.3 撤行）。

用法：
  `backend/.venv/Scripts/python.exe tools/oneoff/_apply_tail101_ledger.py`          # 只报不写
  `backend/.venv/Scripts/python.exe tools/oneoff/_apply_tail101_ledger.py --apply`  # 真写
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / ".workbuddy" / "plans" / "开发计划-主文档.md"

ROW_S1 = ("| `TAIL-101` | ⭐ **集采「剔除名单」没有进契约面**（`TAIL-96` 全链已落地，但《说明书》§6 与交付面 "
          "`PRD/` 里**一处都没有它**） | 2026-09-25 `TAIL-97` 同步契约面时核查发现（全库搜「剔除名单」/`jc-ignore` "
          "⇒ 交付面 **0 命中**） | 用户口径「不纳入名单」在**业务口径主人**里查不到 ⇒ 后来人读《说明书》"
          "**根本不知道有这条规则**；且它**没有任何验收用例**兜着（没登记 ⇒ `T7b` 也看不见） | "
          "《说明书》§6.5 补一节（或做成 §4.2.2「剔除规则」的集采姊妹节）· `MOD-14.md` 能力表一行 · "
          "`验收基线.json` 新增用例（覆盖四条：命中即剔除 / 名单空逐字节一致 / 反例不许放行 / 同名幂等可复活 "
          "—— 判据其实**已有**：`backend/tests/test_jc_ignore.py` ＋ 真机 `_shell_smoke` **⑫c**） | 随时 | 待做 |\n")

ROW_S143 = ("| `TAIL-101` 集采剔除名单未进契约面 | 随时 | ①**口径主人里查不到这条规则**（后来人不知道有它）；"
            "②改动面小（《说明书》一节 ＋ `MOD-14.md` 一行 ＋ 一条用例）；③⭐ 判据其实**已经有了**"
            "（`test_jc_ignore.py` ＋ 真机 ⑫c）⇒ **补登记即可** | 无（`TAIL-96` 已落地） |\n")

ROW_S4 = ("| `TAIL-101` | ⭐ **集采「剔除名单」没有进契约面**（`TAIL-96` 的遗留） | ✅ **已销号（2026-09-25）** —— "
          "① **发现**：`TAIL-97` 同步契约面时核查 —— 全库搜「剔除名单」/`jc-ignore` ⇒ 交付面 **0 命中**"
          "（而它有 M14 维护卡 / API / 表 / 真机判据 ⑫c ⇒ **用户可见，却没有口径主人、也没有判据**）；"
          "② **根因不是漏做、是「分批」**：`test_jc_ignore.py` 自己的 docstring 就写着「用户可见的口径判据点"
          "**待与契约面同批补**（`TAIL-97` 那批一起动 `验收基线.json`…）」—— 而 `TAIL-97` 那批**没带上它**；"
          "③ **补齐四处**：《说明书》**新建 §6.5.4**「不纳入名单」（口径主人；含与 §6.5.3「不纳入」两态的"
          "**分工** —— 名单 = **抓取前**的项目级过滤（压根不进来）· 两态 = **落库后**的逐条标记（进来了、不算账））"
          "· `MOD-14.md` 能力表 **#11** ＋ §四 验收清单 · `验收基线.json` 新建 **`ACC-JC-IGNORE-001`**（**4 点**："
          "命中摘出且不连坐 / 名单空逐字节一致（含行序）/ ⛔ 反例不许放宽判定 / 同名幂等＋停用留册）· "
          "两份活文档判据点计数 **560 → 564**；④ **判据早已有**：只是把 `test_jc_ignore.py` 的 `@acc()` 改成**绑定**"
          "（并拆出 `001-01`/`001-02` 两条各自独立的用例）；⑤ 闸门：pytest rc=0 · `doc_audit` ± `--ui` 双 0 · "
          "12 把尺子全 0 · 四态 **564 全绿** | 2026-09-25 |\n")

EDITS: list[tuple[str, str, str]] = [
    ("§0.2 计数：A 6⇒5 · 已销号 98⇒99",
     "- **尾巴**：A 类 **6** 条 · B 类 0 · C 类 **0** · 已销号 **98**（明细 = §15）。",
     "- **尾巴**：A 类 **5** 条 · B 类 0 · C 类 **0** · 已销号 **99**（明细 = §15）。"),
    ("§15 顶部计数：A 6⇒5 · 已销号 98⇒99",
     "> **当前状态（2026-09-25 · 实测）**：A 类 **6** 条 · B 类 **0** 条 · C 类 **0** 条 · 已销号 **98** 条",
     "> **当前状态（2026-09-25 · 实测）**：A 类 **5** 条 · B 类 **0** 条 · C 类 **0** 条 · 已销号 **99** 条"),
    ("§15 §一：撤掉 `TAIL-101` 行", ROW_S1, ""),
    ("§14.3：撤掉 `TAIL-101` 行", ROW_S143, ""),
    ("§15 §四：`TAIL-101` 销号留痕（§四 表头下**没有** `|---` ⇒ 用表头行当锚）",
     "| # | 事项 | 销号依据 | 日期 |\n| `TAIL-100` |",
     "| # | 事项 | 销号依据 | 日期 |\n" + ROW_S4 + "| `TAIL-100` |"),
]


def main() -> int:
    apply = "--apply" in sys.argv
    raw = PLAN.read_bytes()
    crlf = b"\r\n" in raw
    text = raw.decode("utf-8").replace("\r\n", "\n")
    if (text.replace("\n", "\r\n") if crlf else text).encode("utf-8") != raw:
        print("⛔ 行尾 round-trip 不一致 ⇒ 不动")
        return 1
    errors: list[str] = []
    for desc, old, new in EDITS:
        n = text.count(old)
        if n != 1:
            errors.append(f"{desc} —— 命中 {n} 次（期望 1）")
            continue
        text = text.replace(old, new, 1)
    print("=" * 78)
    print(("  写入" if apply else "  DRY-RUN（只报不写）") + " ·  TAIL-101 销号")
    print("=" * 78)
    print(f"  {PLAN.name} · 行尾={'CRLF' if crlf else 'LF'} · 替换 {len(EDITS)} 处")
    if errors:
        print("\n⛔ 有锚点对不上 ⇒ **一个字节都没写**：")
        for e in errors:
            print("   " + e)
        return 1
    if not apply:
        print("\n  （加 --apply 才真写。）")
        return 0
    PLAN.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))
    print("\n  ✅ 已写盘。")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
