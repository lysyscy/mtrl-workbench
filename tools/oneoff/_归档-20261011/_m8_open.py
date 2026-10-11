"""M8 开场（用户 2026-09-29「M8 可以开始了」＋六答＋「在目标机上还要继续调试开发」＋「全按推荐」）：
把**交付形态定案**写进计划 —— 账本三处 ＋ 新立 `TAIL-188`（§15 §一 ＋ §14.3 各一行）＋ 顺带修一处过期计数。

⛔ 本脚本**只动文档**（计划），不碰代码 —— 4 个落地脚本（`pack`/`deploy_restore`/`selfcheck`/一页说明）与
   `A8 路径可配置`改造**下一轮**做（守用户自己确认的限制「别一次性铺开」）。

跑法：`backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_m8_open.py --check` / `--write`
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / ".workbuddy" / "plans" / "开发计划-主文档.md"

TAIL188_ROW = (
    "| `TAIL-188` | ⭐ **交付包与迁移**（本机 ⇒ 办公室电脑）：包 = **「可继续开发的可运行系统」**（开发链全带："
    "tests / tools / demo / 验收面 / 计划台账 / 记忆）· 含 `ops/pack.ps1` / `deploy_restore.ps1` / `selfcheck.ps1` / "
    "`docs/部署-落地说明.md` ＋ **路径可配置改造**（交付面定位 / node / Playwright） | 用户 2026-09-29 口述"
    "（出处 = `.codebuddy/memory/2026-09-29.md` §㉓/㉓之二） | 目标机上装不起来 / 落地无自检 ⇒ 系统交不出去 | "
    "`work/10-designs/设计-交付包与迁移-20260929.md` | `M8` | 待做 |\n"
)

TAIL188_SCHED = (
    "| `TAIL-188` 交付包与迁移（本机 ⇒ 办公室电脑） | **M8**（⭐ 2026-09-29 **用户新增输入**：目标机**还要继续调试开发** "
    "⇒ 开发链全带） | ① 用户明确要求（「打包为一个交付包，拷到办公室电脑能直接使用」）② 它是 `M8` 完成定义②"
    "（恢复演练）与④（交接口径）的**载体** ③ ⛔ **未冻结构**（录真实数据前才冻，见 §9.5） | "
    "`work/10-designs/设计-交付包与迁移-20260929.md`（＋ `ops/pack.ps1` / `ops/deploy_restore.ps1` / "
    "`ops/selfcheck.ps1` / `docs/部署-落地说明.md`） |\n"
)

EDITS: list[tuple[str, str, str, bool]] = [
    # ① §15 §一：A 类表加一行 TAIL-188（插在表头分隔线之后 = 表格第一行，⚠️ 别插到空行后：那儿已在表外）
    ("§15 §一 A 类表头（插入新行）",
     "### 一、A 类 · 我能做（工程侧，无外部依赖）\n\n"
     "| # | 事项 | 来源 | 不做会怎样 | 落点 | 阶段 / 时机 | 状态 |\n|---|---|---|---|---|---|---|\n",
     "### 一、A 类 · 我能做（工程侧，无外部依赖）\n\n"
     "| # | 事项 | 来源 | 不做会怎样 | 落点 | 阶段 / 时机 | 状态 |\n|---|---|---|---|---|---|---|\n" + TAIL188_ROW,
     False),
    # ② §15 顶部计数 ＋ §0.2 计数：**同一串出现两处** ⇒ 必须同批改两处（`T4` 逐处核）
    ("计数 A 4 → 5（两处同批）",
     "A 类 **4** 条 · B 类 **0** 条 · C 类 **0** 条 · 已销号 **186** 条",
     "A 类 **5** 条 · B 类 **0** 条 · C 类 **0** 条 · 已销号 **186** 条",
     True),
    # ②′ §0.2 那处计数**写法略有不同**（`B 类 0` 没加星号）⇒ 单独一处（`T4` 逐处核，漏了必黄）
    ("计数 A 4 → 5（§0.2 那处）",
     "A 类 **4** 条 · B 类 0 · C 类 **0** · 已销号 **186**",
     "A 类 **5** 条 · B 类 0 · C 类 **0** · 已销号 **186**",
     False),
    # ③ §14.3：登记即排期（`T6` 第 6 条：每条编号必须在 §14.3 有一行）—— 插在 TAIL-21 行之前
    ("§14.3 加 TAIL-188 行",
     "| `TAIL-21` 留痕范围用例（`§9.3` · `MOD-13`） | **M8**",
     TAIL188_SCHED + "| `TAIL-21` 留痕范围用例（`§9.3` · `MOD-13`） | **M8**",
     False),
    # ④ §5.1 M8 行：完成定义那两条的落法变了（恢复演练要在目标机那遍才算数）
    ("§5.1 M8 行",
     "| **M8** | 历史初始化与移交 | §9.7 | **初始值录入/导入入口可用** · **恢复演练成功一次** · 交付面清点 | M7 | "
     "补抓历史月份（库存单据） | ⏳ **未做**（⚠️ **四个初始化入口都已具备**：付款存量=历史付款导入 · "
     "过程资料=历史导入 · 库存单据=手动导入 · 集采=Excel 导入 ⇒ 都在壳里，见 §0.3） |",
     "| **M8** | 历史初始化与移交（⭐ **2026-09-29 改**：移交 = **交付包 ＋ 在办公室电脑落地**） | "
     "《说明书》§9.7 | **初始值录入/导入入口可用** · **恢复演练成功一次（⚠️ 在目标机那遍才算）** · "
     "**包内/交付面清点** | M7 | 补抓历史月份（库存单据） | ⏳ **未做**（四个初始化入口**都已具备**；"
     "⭐⭐ **2026-09-29 用户定交付形态**：本机跑通 ⇒ 打包（**可继续开发的可运行系统**）⇒ 拷办公室电脑 ⇒ "
     "**②③ 落地/自检通过才算数** ⇒ 落点 = `work/10-designs/设计-交付包与迁移-20260929.md` · 台账 `TAIL-188`） |",
     False),
    # ⑤ §5.5 M8 四步：把"移交"的落法写实
    ("§5.5 M8 四步",
     "| **M8** | ① 历史数据初始化入口（§9.7：付款=期初占位行手填 / 集采=手录 / 过程资料=手录+上传 / "
     "库存单据=补抓历史月份）② **恢复演练**（对空库还原成功才算数）③ 交付面清点（**不含 `.workbuddy/`**）④ 交接口径与自检命令 |",
     "| **M8** | ① 历史数据初始化入口（《说明书》§9.7：付款=期初占位行手填 / 集采=手录 / 过程资料=手录+上传 / "
     "库存单据=补抓历史月份）② **恢复演练**（⭐ **在目标机**对空库还原成功才算数）③ **交付包/交付面清点** "
     "④ **交接口径与自检命令**（= `docs/部署-落地说明.md` ＋ `ops/selfcheck.ps1`）"
     "⭐ **2026-09-29 增**：包 = 「**可继续开发的可运行系统**」（开发链全带：tests / tools / demo / 验收面 / "
     "计划台账 / 记忆）· 落地 = `ops/deploy_restore.ps1` · ⛔ 真 `.env` 不进包（现场填）· 库 = 空库＋出厂默认 |",
     False),
    # ⑥ §0.4 当前位置块：一处**过期计数**（TAIL-117 今天已销号，这行还写着"进行中"）
    ("§0.4 过期计数",
     "**尾巴 A 类只剩 5 条**：`TAIL-117`（进行中）＋ `TAIL-06` / `TAIL-21` / `TAIL-59` / `TAIL-64`（M8 / 持续档）",
     "**尾巴 A 类只剩 4 条**：`TAIL-06` / `TAIL-21` / `TAIL-59` / `TAIL-64`（M8 / 持续档）"
     "（⚠️ `TAIL-117` 已于 2026-09-29 销号；`TAIL-188` 交付包与迁移已新立 ⇒ 计数见 §15 顶部）",
     False),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    apply = a.write and not a.check

    raw = PLAN.read_text(encoding="utf-8", newline="")
    eol = "\r\n" if "\r\n" in raw else "\n"
    print(f"计划：{len(raw.splitlines())} 行")

    # 幂等
    if "TAIL-188" in raw:
        print("⏭ 计划里已有 `TAIL-188` ⇒ 视为已做过（幂等），停手")
        return 0

    # ⚠️ 锚点一律按 `\n` 写 ⇒ 先归一（本仓计划文件是 **CRLF**；2026-09-29 实测：不归一 ⇒ 锚点命中 **0** ✗）
    text = raw.replace("\r\n", "\n")
    for i, (label, old, new, all_) in enumerate(EDITS, 1):
        n = text.count(old)
        want = "≥1" if all_ else "1"
        ok = (n >= 1) if all_ else (n == 1)
        print(f"  {'✓' if ok else '⛔'} #{i} {label}：命中 {n} 处（要 {want}）"
              f"{'  ⇒ replace_all' if all_ and n > 1 else ''}")
        if not ok:
            print(f"     ⛔ 锚点对不上 ⇒ **整批停手**（宁可不动，别改错行）：{old[:56]}…")
            return 2
        text = text.replace(old, new) if all_ else text.replace(old, new, 1)

    if apply:
        PLAN.write_text(text.replace("\n", eol), encoding="utf-8", newline="")   # ⚠️ 还原原换行风格
        print(f"\n🔧 已落盘：计划 {len(text.splitlines())} 行（原 {len(raw.splitlines())}）")
    else:
        print("\n🧪 --check（干跑，未落盘）")
    print("   下一步：`_run_rulers.py`（`T6` 台账 / `T4` 计数 / `claim_audit` 出处 / 其余全绿）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
