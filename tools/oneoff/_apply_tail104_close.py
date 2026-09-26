"""`TAIL-104`（壳的「靠自觉」收口）**销号手续** —— 一次改完 5 处，逐处断言。

为什么用脚本而不是手改 5 次：那几行**又长又满是反引号**（§一 那行还有中文引号），
手改一个字符对不上就是「改了一半」；脚本能**逐处断言改到了**、还留一份可复跑的记录。

改五处（都在 `开发计划-主文档.md`）：
  ① §0 顶部「尾巴」计数：A 类 6 → **5** · 已销号 101 → **102**
  ② §15 顶部「当前状态」计数：同上（并把日期订到 2026-09-26）
  ③ 删 §15 **§一**（A 类在册表）里的 `TAIL-104` 行
  ④ 在 §15 **§四**（已销号表）表头下方**插入** `TAIL-104` 的销号行
  ⑤ 删 §14.3（排期表）里的 `TAIL-104` 行
另：设计件末尾追加「落地情况」（把 §五 的「真机证据缺口」标记为清零）。

⛔ 本件是**一次性手续**（跑完即可删）；它是留痕，不是常驻工具。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / ".workbuddy" / "plans" / "开发计划-主文档.md"
DESIGN = (ROOT / ".workbuddy" / "work" / "10-designs"
          / "设计-共用件收口-面板注册表与委托自动化-20260926.md")

#: 销号行（插进 §四「已销号」表）—— 判据 / 证据 / 闸门 / 提交号都写清（下一个人只读这一行就够）
CLOSED_ROW = (
    "| `TAIL-104` | ⭐ **壳的「靠自觉」收口**（面板展开态 / `CHG` 登记 / 写后全标脏 / 浮层锚点 ⇒ 搬进共用件与委托层） | "
    "✅ **已销号（2026-09-26 · 当轮）** —— ① **四件全落**：`#1` 面板展开态 ⇒ 注册表 `PJ_OPEN`"
    "（`pjIsOpen/pjToggle/pjClose`，key 由 `pickAct` 派生；13 处裸变量删净；**两处手写名单**（click 收面板 / Esc 收面板）"
    "随之消失；`radio` 选中自动收起）· `#2` 拆 `CHG` 登记名单（壳 ＋ 交付面原型 ＋ 真机自检的 `N6′` ＋ 变异靶 `M1` "
    "**四面同批**，少一面都不算）· `#3` 标脏收口（唯一出口 `markCrossPageStale()` ＝ `api.js` 6 条写路径；"
    "删业务动作里两处手写清空）· `#4` 锚点不变量（`pjwrap` 形态只许两种 ＋ 每个 `projPanel` 调用点必须有锚点）；"
    "② ⭐ **真机证据三件**（报告里「欠项」清零）：面板**展开/收起 round-trip**"
    "（`open=14` / `outside=0` / `byPick=0`，且第三条只点**已选中**那个 ⇒ 语义不变不扰后段）· "
    "**表单元素真选一次触发**（域 `m04_plan` → `m05_flow`，页面文本变）· ⭐ **② 列映射**"
    "（表头**照域契约现造** xlsx 真上传，`maps=11` = 契约 11 字段：核算月 ＋ 10 材料列）；"
    "③ **判据（能证伪）**：名单式写法不许回来 · **壳里零域号分支**（剥注释后扫）· `LOADED.clear()` 全壳只许 1 处 · "
    "`pjwrap` 形态/数量 · 真机那三件；④ **闸门**：pytest 0 · 真机 0（console/page 错误 0）· `doc_audit` ±ui 双 0 · "
    "**12 把尺子全 0** · 567 全绿（改壳后盖章 `20260926-1230`）；⑤ 提交 `42fd0b8` / `a6c857e` / `be98195` / `fc930ea` | "
    "2026-09-26 |"
)

DESIGN_TAIL = """
---

## ✅ 落地情况（2026-09-26 收尾 · 本件已执行完）

四件（`#1`–`#4`）＋ **三件真机证据**全部落地，`TAIL-104` 已**销号**（见《开发计划-主文档》§15 §四）：

- `#1` 展开态注册表 `PJ_OPEN`（＋ `pjIsOpen/pjToggle/pjClose`；key 由 `pickAct` 派生）· `#2` 拆 `CHG` 登记名单
  （壳 ＋ 交付面原型 ＋ 真机自检 `N6′` ＋ 变异靶 `M1`）· `#3` 标脏收口（唯一出口 `markCrossPageStale()`）·
  `#4` 锚点不变量（`pjwrap` 两种形态 ＋ 每个 `projPanel` 调用点必须有锚点）。
- **真机证据**：面板展开/收起 round-trip · 表单元素真选一次触发 · ② 列映射（照域契约现造 xlsx 真上传）。
- 提交：`42fd0b8` / `a6c857e` / `be98195` / `fc930ea`。
- ⚠️ 本件 **§五 的真机证据缺口已清零**；**③ 预览**那屏仍未真机走（不在 2026-09-26 报障范围 ——
  愿意时可照 §五 的 ② 段再加一段：`impPreview` 之后断言 `#impCut` 只在该域声明了 `cutoff_ym` 时出现）。
"""


def main() -> int:
    raw = PLAN.read_bytes()
    txt = raw.decode("utf-8")                      # ⚠️ 走 bytes：⛔ 别让 Python 把 LF 翻译成 CRLF
    bad: list[str] = []

    def sub(old: str, new: str, tag: str, expect: int = 1) -> None:
        nonlocal txt
        n = txt.count(old)
        if n != expect:
            bad.append(f"{tag}：该处出现 {n} 次（期望 {expect}）⇒ 没改，请人看")
            return
        txt = txt.replace(old, new)
        print(f"  ✅ {tag}")

    # ① §0 顶部「尾巴」计数
    sub("- **尾巴**：A 类 **6** 条 · B 类 0 · C 类 **0** · 已销号 **101**",
        "- **尾巴**：A 类 **5** 条 · B 类 0 · C 类 **0** · 已销号 **102**",
        "① §0 尾巴计数（A 6→5 · 已销号 101→102）")

    # ② §15 顶部「当前状态」计数（＋日期订正）
    sub("> **当前状态（2026-09-25 · 实测）**：A 类 **6** 条 · B 类 **0** 条 · C 类 **0** 条 · 已销号 **101** 条",
        "> **当前状态（2026-09-26 · 实测）**：A 类 **5** 条 · B 类 **0** 条 · C 类 **0** 条 · 已销号 **102** 条",
        "② §15 顶部计数（同上 ＋ 日期 09-26）")

    # ③⑤ 删在册那两行（§15 §一 一条 ＋ §14.3 一条）
    lines = txt.split("\n")
    hit = [i for i, ln in enumerate(lines) if ln.lstrip().startswith("| `TAIL-104`")]
    if len(hit) != 2:
        bad.append(f"③ 在册的 `TAIL-104` 行找到 {len(hit)} 条（期望 2：§15 §一 ＋ §14.3）")
    else:
        txt = "\n".join(ln for i, ln in enumerate(lines) if i not in hit)
        print("  ✅ ③⑤ 删掉在册两行（§15 §一 ／ §14.3）")

    # ④ §15 §四表头下方插入销号行（第 1 个 4 列表头）
    # ⚠️ 插在**第一条数据行之前**（而不是"表头后第 2 行"）：表头与首行之间有几行分隔/空行
    #    并不由我决定（下一轮改版式就换个位置）—— 认「第一条以 `| \`TAIL-` 开头的行」才稳。
    header = "| # | 事项 | 销号依据 | 日期 |"
    lines = txt.split("\n")
    idx = [i for i, ln in enumerate(lines) if ln.strip() == header]
    if len(idx) != 1:
        bad.append(f"④ §四表头找到 {len(idx)} 处（期望 1）⇒ 销号行没插进去")
    else:
        i = idx[0]
        j = i + 1
        while j < len(lines) and not lines[j].lstrip().startswith("| `TAIL-"):
            j += 1
        if j >= len(lines):
            bad.append(f"④ §四表头（第 {i + 1} 行）之后找不到数据行 ⇒ 销号行没插进去")
        else:
            lines.insert(j, CLOSED_ROW)
            txt = "\n".join(lines)
            print(f"  ✅ ④ §15 §四插入销号行（第 {j + 1} 行 · 原首行是 {lines[j + 1][:22]!r}）")

    if not bad:
        PLAN.write_bytes(txt.encode("utf-8"))      # ⚠️ 同样走 bytes
        print(f"  ✅ 已写回 {PLAN.name}（{len(txt.encode('utf-8'))} B）")
    for b in bad:
        print("  ⛔ " + b)

    # ⑥ 设计件末尾追加「落地情况」（幂等：已追加过就不重复）
    d = DESIGN.read_text(encoding="utf-8")
    if "落地情况（2026-09-26 收尾" in d:
        print("  ✅ ⑥ 设计件已记过落地情况（跳过）")
    else:
        DESIGN.write_bytes((d.rstrip("\n") + "\n" + DESIGN_TAIL).encode("utf-8"))
        print("  ✅ ⑥ 设计件末尾记下落地情况（§五 证据缺口清零）")

    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
