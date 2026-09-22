# -*- coding: utf-8 -*-
"""把三处**口径欠账**回写进交付面《材料科业务全流程说明书》（2026-09-21）。

欠账（计划 §9.5 的"待回写 3 处"）：
1. `§7.7`：主题清单 **10 套 · 每套独立** ＋ **结构规范四条**（原文写着"≥10 套"并带着 3 个「深色·X」变体）。
2. `§7.8`：**打印机地址不在本页**（合并进 `MOD-03`）—— 原表里它是第 4 项。
3. `§1.5.1`：**未登录 ⇒ 无身份**（不回落"首个管理员"）＋ 删除账号单列「回收站」。

⚠️ 交付面 md 是 **CRLF** ⇒ 按原 EOL 写回（先做**往返逐字节自检**）；⛔ 不走 `write_text`。
⚠️ 先 `--dry` 干跑：**四处锚点各命中恰好 1 次**才允许写（防止把别处改坏）。

跑法（工程根）：
    backend\\.venv\\Scripts\\python.exe tools\\_doc_handbook_sync.py --dry
    backend\\.venv\\Scripts\\python.exe tools\\_doc_handbook_sync.py
"""

from __future__ import annotations

import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "audit"))  # ⭐ `TAIL-58` 分目录
from audit_common import delivery_root  # noqa: E402

HANDBOOK = "材料科业务全流程说明书.md"

# --- 1. §1.5.1 增两行（未登录 = 无身份；删除账号单列回收站）------------------------------
OLD_LOGOUT = "| **登出** | 用户管理页提供**登出**入口；退出后回到登录页，**业务数据不受影响** |"
NEW_LOGOUT = OLD_LOGOUT + (
    "\n| **未登录时** | ⭐ **无身份**（2026-09-21 用户裁定）：**不回落**到「首个管理员」—— "
    "未登录**只能看**，**写动作一律拒**；顶栏提示「未登录 · 去登录」。"
    "⚠️ 此前那条过渡期兜底实测会让**任何不带会话的请求**被当成管理员 |"
)

OLD_DEL = ("| **停用 / 删除** | **停用** = 暂不可登录、可再启用；**删除 = 软删除**"
           "（账号名保留、**不销毁数据**，历史留痕里的人名仍认得出来，必要时可恢复） |")
NEW_DEL = ("| **停用 / 删除** | **停用** = 暂不可登录、可再启用；**删除 = 软删除**"
           "（账号名保留、**不销毁数据**，历史留痕里的人名仍认得出来，必要时可恢复；"
           "界面上**单列一块「回收站」**，主列表不混已删账号） |")

# --- 2. §7.7 清单 + 结构规范（替换原「清单」与「泛化机制」两行）------------------------
OLD_THEME_LIST = (
    "| ⭐ **预置主题清单**（用户 2026-09-20 定：**≥10 套，换着玩**） | "
    "**浅色系**：`默认`（现况 · 浅蓝）· `靛青` · `松绿` · `琥珀` · `绛红` · `石墨`（低饱和中性灰）· "
    "`米黄`（暖纸底 · 像纸）· `蓝灰工控`（冷灰 · 高密度感）<br>**深色系**：`深色`（暗底浅字 · 护眼）· "
    "`深色·松绿` · `深色·琥珀` · `深色·靛青`<br>**特殊**：`高对比`（加深文字与边框、去中间灰阶 —— "
    "投屏 / 弱视 / 打印屏校对）<br>⚠️ **清单可继续加**：加一套 = **加一行种子**（零 CSS 改动、零判据改动）；"
    "⛔ 但**每套必须覆盖同一组变量名**（缺项 = 显式报错，见判据） |"
)
NEW_THEME_LIST = (
    "| ⭐ **预置主题清单**（用户 2026-09-21 定：**恰好 10 套 · 每套独立**） | "
    "`默认`（日常通用）· `靛青`（长时段录入）· `松绿`（财务对账）· `琥珀`（仓储工单 · 暖光）· "
    "`绛红`（风控盯盘）· `石墨`（数据密集大表）· `米黄`（长时阅读 · 弱光）· `蓝灰工控`（现场大屏）· "
    "`深色`（夜间暗室）· `高对比`（弱视 / 强光 / 投影）<br>"
    "⚠️ 每套的**适用场景与设计风格**落在实现侧**一处**（与种子表同源）⇒ 界面上每张卡都写明"
    "「这套干什么用的」。<br>⛔ **不再有「深色·X」这类变体**（那不是「独立」的方案）；"
    "**加/改一套 = 改口径**（不是顺手加一行） |"
)
OLD_THEME_GEN = (
    "| ⭐ **泛化机制** | ⚠️ 清单再长，**一套主题的产出形态不变**：仍是**一份变量取值**（≈ 一段 `:root`）。"
    "新增的只是\"**从种子色派生整套**\"这一层（种子 = 主色 ＋ 底色 ＋ 文字色 ＋ 三个状态色）⇒ "
    "浅底 / 浅边框 / 深字由种子**算出来**，⛔ 不许一套一套手抄（手抄 = 12 份 43 个值 = 必有漏项与漂移） |"
)
NEW_THEME_GEN = (
    "| ⭐ **结构规范**（四条硬约束 · 2026-09-21 立） | ① **一行种子 → 派生整套变量**"
    "（每套覆盖**同一组变量名**，缺项**显式报错**）；② 状态色**四档成组**（主色 / 深字 / 浅底 / 浅边框）；"
    "③ **侧栏三档文字**（品牌·悬停 / 普通项 / 编号·分组·页脚）＋ 选中项底 = **主色**"
    "（⛔ 不借「主色之上的前景色」当面板文字 —— 深色套会变成黑字压深底）；"
    "④ ⭐ **可读性下限**：凡「给人读的文字」，对比度 **≥4.5**（WCAG AA；纯装饰 ≥1.15） |"
)

# --- 3. §7.8 打印机地址不在本页（删表里第 4 项 ＋ 补一段说明）-------------------------
OLD_PRINTER_ROW = (
    "| 4 | **打印机地址**（IPP） | `.env` `PRINTER_IPP_URL` | 换打印机 / 换 IP | — |\n"
)
NEW_PRINTER_ROW = ""
OLD_TABLE_TAIL = "| 3 | **外租机械类打印版式 ID** | `.env` `I8_PRINT_ID_MECHANICAL` | 同上 | — |"
NEW_TABLE_TAIL = OLD_TABLE_TAIL + (
    "\n\n- ⭐ **打印机地址（IPP）不在本页**（2026-09-21 用户裁定：**合并进 `MOD-03`**）——"
    "它的**唯一入口** = 付款通知书页的「打印机设置」弹窗、**唯一存储** = `.env`"
    "（`PRINTER_IPP_URL` / `PRINT_MODE` / `PRINTER_NAME` 三项）。"
    "⚠️ 原来两处都能改（本页写库、弹窗写 `.env`，而打印读「库优先」）⇒ 库里一旦有值，**弹窗改的不生效**。"
)

EDITS: list[tuple[str, str, str]] = [
    ("§1.5.1 登出（追加「未登录时」一行）", OLD_LOGOUT, NEW_LOGOUT),
    ("§1.5.1 停用/删除（追加「回收站」）", OLD_DEL, NEW_DEL),
    ("§7.7 预置主题清单（≥10 套 → 恰好 10 套）", OLD_THEME_LIST, NEW_THEME_LIST),
    ("§7.7 泛化机制 → 结构规范四条", OLD_THEME_GEN, NEW_THEME_GEN),
    ("§7.8 删掉表里「打印机地址」那一行", OLD_PRINTER_ROW, NEW_PRINTER_ROW),
    ("§7.8 表后补「打印机地址不在本页」", OLD_TABLE_TAIL, NEW_TABLE_TAIL),
]


def main() -> int:
    dry = "--dry" in sys.argv
    root = delivery_root()
    if root is None:
        print("⛔ 找不到交付面根（`.env` 的 PRD_ACCEPTANCE_BASELINE）")
        return 1
    path = root / HANDBOOK
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    eol = "\r\n" if "\r\n" in text else "\n"
    if text.replace("\r\n", "\n").replace("\n", eol) != text:
        print("⛔ 行尾不是统一的一种 —— 先别改")
        return 1

    out = text
    bad = 0
    for name, old_s, new_s in EDITS:
        n = out.count(old_s)
        flag = "✅" if n == 1 else "⛔"
        if n != 1:
            bad += 1
        print(f"  {flag} {name} —— 锚点命中 {n} 次")
        if n == 1 and old_s != new_s:
            out = out.replace(old_s, new_s, 1)

    if bad:
        print(f"\n⛔ 有 {bad} 处锚点对不上（⛔ 一个字都没写）—— 多半是原文变了，重新核一遍再跑")
        return 1
    if out == text:
        print("\n· 文本无变化（可能已经回写过了）")
        return 0
    if dry:
        print(f"\n✅ 干跑通过：全部锚点各命中 1 次（{len(EDITS)} 处）—— 去掉 `--dry` 即写入")
        return 0

    bak = path.with_name(f"_backup-handbook-{datetime.now().strftime('%Y%m%d-%H%M')}.md")
    shutil.copy2(path, bak)
    path.write_bytes(out.replace("\r\n", "\n").replace("\n", eol).encode("utf-8"))
    print(f"\n✅ 已回写 {len(EDITS)} 处 · 备份 = {bak.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
