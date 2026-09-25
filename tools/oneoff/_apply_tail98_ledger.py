"""`TAIL-98` 台账：**销号** ＋ 登记 **`TAIL-102`**（`alembic check` 的历史漂移）。

计数：A 5 →（销 98）4 →（登记 102）**5** · 已销号 99 → **100**。

用法：
  `backend/.venv/Scripts/python.exe tools/oneoff/_apply_tail98_ledger.py`          # 只报不写
  `backend/.venv/Scripts/python.exe tools/oneoff/_apply_tail98_ledger.py --apply`  # 真写
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / ".workbuddy" / "plans" / "开发计划-主文档.md"

ROW98_S1 = ("| `TAIL-98` | **集采导入「整批回滚」＋ 覆盖语义文案** | 用户 2026-09-25「加吧」「可以加」 | "
            "导错只能手工改回（付款计划/过程资料都有回滚，集采没有）；界面没说清哪些列会被覆盖 ⇒ 易误操作 | "
            "`work/10-designs/设计-集采剔除名单与两态化-20260925.md` §三 | 随时 | 待做 |\n")

ROW98_S143 = ("| `TAIL-98` 导入回滚＋文案 | 随时 | ②小（域加 `batch` ＋ 批次表 ＋ 钩子；壳已就绪） | 无 |\n")

ROW98_S4 = ("| `TAIL-98` | **集采导入「整批回滚」＋ 覆盖语义文案** | ✅ **已销号（2026-09-25）** —— "
            "① **表**：新建 `jc_import_batch`（批次）＋ `jc_import_undo`（逐行「改前/改后」回滚点）· 迁移 "
            "`a2b4c6d8e0f2`（**打到两个库** · 命名外键 · ⛔ 不改已应用的迁移）；② **回滚点怎么取**："
            "`imp_batch.apply_batch` 在落库**之前**给「该项目的全部合同 ＋ 发票行」拍快照、之后**逐条 diff** "
            "⇒ 只有**真变了的**才记 —— ⛔ 不预设「哪些行会被改」（那等于把匹配逻辑再抄一遍）；"
            "③ **回滚**：批次号 `JC-YYYYMMDDHHMMSS`（回执带出 ⇒ 壳侧按钮出现）⇒ 那 **6 列逐列还原** ＋ "
            "**摘掉本批新加的发票行**、批次置 `rolled_back`（⛔ 不物理删）· **不许重复回滚** · "
            "导入之后**被人手改过**的行**照还原但逐条报出**（禁静默）；④ **文案**：写在 `SPEC.note` 里"
            "（**只动这 6 列** / **i8 的列不会被覆盖**）—— ⛔ 不许散在壳里（壳是通用面，不知道集采有哪些列）；"
            "⑤ **判据**：`ACC-JC-IMPORT-001` **＋ `001-05`~`001-07`**（判据点 564 → **567**）· 契约面同批"
            "（《说明书》**新建 §6.10** ＋ `MOD-11.md` 能力 #14）；⑥ ⚠️ **实测抓到一个真 bug 并当场修掉**："
            "批次号是**秒级**的 ⇒ **同一秒内连导两次会撞唯一键**（第二次直接落库失败，症状只是一句「导入失败」）"
            "—— 原有那条「同源重跑不翻倍」的断言就是这么红的 ⇒ 加 `unique_batch()`（撞号把秒数**顺延**、"
            "保持 `JC-<14 位>` 形态）；⑦ 闸门：pytest rc=0 · 真机 `_shell_smoke` rc=0 · `doc_audit` ± `--ui` 双 0 "
            "· 12 把尺子全 0 · 四态 **567 全绿** | 2026-09-25 |\n")

ROW102_S1 = ("| `TAIL-102` | ⚠️ **`alembic check` 有历史漂移** —— 「迁移三连」的**第三连从未通过**："
             "`remove_table user_account` ＋ `modify_default payment_flow.created_by` | "
             "2026-09-25 `TAIL-98` 加迁移时按纪律跑 `alembic check` 发现（⚠️ **与本次改动无关**：报的两条都不是新表） | "
             "「迁移三连」（`current` = head · `upgrade` 成功 · **`check` 无待生成**）里第三连**一直是红的** ⇒ "
             "模型与库**已经对不上**，而**没有任何尺子/闸门看得见**；⛔ 下一个人跑 `--autogenerate` 会**顺手生成"
             "「删 user_account 表」的迁移**（危险） | 先判清：`user_account` 是**表名不符**还是**模型没注册**；"
             "`payment_flow.created_by` 的 `server_default` 该不该进模型 —— 判完**新写一条迁移**对齐"
             "（⛔ 不许改已应用的迁移）· 落点 = `backend/alembic/versions/` | 随时 | 待做 |\n")

ROW102_S143 = ("| `TAIL-102` `alembic check` 历史漂移 | 随时 | ①**第三连一直红** ⇒ 模型与库已对不上，"
               "而**没有尺子看得见**；②⛔ 下一个人 `--autogenerate` 会**顺手生成「删 user_account 表」的迁移**"
               "（危险）；③改动面小（判清后新写一条迁移） | 无（与 `TAIL-98` 无关，独立） |\n")

EDITS: list[tuple[str, str, str]] = [
    ("§0.2 计数：已销号 99⇒100（A 仍 5：销 98 的同时登记 102）",
     "- **尾巴**：A 类 **5** 条 · B 类 0 · C 类 **0** · 已销号 **99**（明细 = §15）。",
     "- **尾巴**：A 类 **5** 条 · B 类 0 · C 类 **0** · 已销号 **100**（明细 = §15）。"),
    ("§15 顶部计数：同上",
     "> **当前状态（2026-09-25 · 实测）**：A 类 **5** 条 · B 类 **0** 条 · C 类 **0** 条 · 已销号 **99** 条",
     "> **当前状态（2026-09-25 · 实测）**：A 类 **5** 条 · B 类 **0** 条 · C 类 **0** 条 · 已销号 **100** 条"),
    ("§15 §一：`TAIL-98` 行 ⇒ `TAIL-102` 行", ROW98_S1, ROW102_S1),
    ("§14.3：`TAIL-98` 行 ⇒ `TAIL-102` 行", ROW98_S143, ROW102_S143),
    ("§15 §四：`TAIL-98` 销号留痕",
     "| # | 事项 | 销号依据 | 日期 |\n| `TAIL-101` |",
     "| # | 事项 | 销号依据 | 日期 |\n" + ROW98_S4 + "| `TAIL-101` |"),
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
    print(("  写入" if apply else "  DRY-RUN（只报不写）") + " ·  TAIL-98 销号 ＋ TAIL-102 登记")
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
