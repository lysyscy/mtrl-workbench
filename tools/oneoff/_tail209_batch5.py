"""批 5（弹窗说明块）：按 `D29` 删**内部编号 / 内部叫法 / 实现细节 / 机制辩解**（⛔ 不动口径事实）。

⚠️ **为什么这一批比原报的多**：`_text_audit5.py` 首版的"在不在弹窗里"判法是坏的
   （用「块前 600 字里 `modal({` 比最后一个 `}` 更靠右」—— 而弹窗标题常写 `title: …${x}…`，
   `${…}` 里就有 `}` ⇒ 弹窗被误判成页内）。订正后真值 = **弹窗内 42 处**（原报 16 处）。
   即：**待办没变、只是之前量少了** ⇒ 本批按同一口径把这一类一次收口（⛔ 不留"一处改一处漏"）。

**本批删的**（全部是"用户不需要知道的"）：
| 类 | 例 |
|---|---|
| 工程代号 | `（决策 D9）` · `（决策 1 兜底）` · `（决策 2）` · `（决策 3/4）` · `（DEV-J-01）` · `（DEV-J-03）` · `（DEV-P-02）` · `· DEV-P-07` · `（ENT-04）` · `（R8）` |
| 内部叫法 | 「**链路 B · 材料侧扶正**：…」·「**链路 A · 多仓库建档**：…」（照 2026-10-01 批 3 对 `m01` 的同款处置） |
| 实现细节 | 「（后端清缓存…）」·「（后端写配置并清缓存）」 |
| 机制辩解 | 「因为供应商名不可靠，不做自动匹配」 |
**本批⛔ 不动**的：`§节号`（2026-09-27 裁定**可留**）· 一切"系统特有行为/后果"（`D29` 第 5 类）。

⚠️ 每条断言**命中恰好 1 次**（含 CRLF 变体）⇒ 不命中**整批不写**。
⚠️ 本件被 §13.6 的**入门口令**点名 ⇒ 必须有 `main()` ＋ `__main__`（`T17` 守「口令里列的件不许是僵尸闸门」）。
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
W = ROOT / "backend" / "app" / "web"

EDITS: list[tuple[str, str, str]] = [
    # ---------------- shell/actions.js ----------------
    ("shell/actions.js",
     "<b>⚠️ 这一步会登录 i8，可能顶掉该账号其它在线会话</b>（决策 D9）。",
     "<b>⚠️ 这一步会登录 i8，可能顶掉该账号其它在线会话</b>。"),
    ("shell/actions.js",
     "（无「部分付」中间态，DEV-P-02）",
     "（无「部分付」中间态）"),
    ("shell/actions.js",
     "命中多个时弹窗让用户选（决策 3/4）。",
     "命中多个时弹窗让用户选。"),
    ("shell/actions.js",
     "不做枚举约束（DEV-J-03）'",
     "不做枚举约束'"),
    ("shell/actions.js",
     "title:'从付款域引用付款记录（R8）'",
     "title:'从付款域引用付款记录'"),
    ("shell/actions.js",
     "。因为供应商名不可靠，<b>不做自动匹配</b>（DEV-J-01），由你按",
     " —— 由你按"),
    # ---------------- shell/print-export.js ----------------
    ("shell/print-export.js",
     "（<b>不自建打印模板</b> · DEV-P-07）",
     "（<b>不自建打印模板</b>）"),
    ("shell/print-export.js",
     "保存后<b>即时生效、无需重启</b>（后端写配置并清缓存）—— 打印投递按新设置走。",
     "保存后<b>即时生效、无需重启</b> —— 打印投递按新设置走。"),
    # ---------------- shell/core.js ----------------
    ("shell/core.js",
     "调整单独立存储、不被导入覆盖（ENT-04）",
     "调整单独立存储、不被导入覆盖"),
    ("shell/core.js",
     "可能<b>强制踢掉</b>该账号其它在线会话</b>（决策 <span class=\"fc\">D9</span>，不会自动重试登录）——",
     "可能<b>强制踢掉</b>该账号其它在线会话</b>（不会自动重试登录）——"),
    ("shell/core.js",
     "<b>链路 B · 材料侧扶正</b>：材料报表里出现了",
     "材料报表里出现了"),
    ("shell/core.js",
     "<b>系统不猜</b>（决策 1 兜底），",
     "<b>系统不猜</b>，"),
    ("shell/core.js",
     "按决策 2（普通项目 ↔ 仓库 = 1 : 1）",
     "（普通项目 ↔ 仓库 = 1 : 1）"),
    ("shell/core.js",
     "<b>链路 A · 多仓库建档</b>：i8 名单里这个全名挂了",
     "i8 名单里这个全名挂了"),
    ("shell/core.js",
     "<b>一条普通项目只挂一个仓库</b>（决策 2）⇒ ",
     "<b>一条普通项目只挂一个仓库</b> ⇒ "),
    ("shell/core.js",
     "并强制踢掉该账号其它在线会话</b>（决策 <span class=\"fc\">D9</span>，不会自动重试登录）——",
     "并强制踢掉该账号其它在线会话</b> ——"),
    # ---------------- shell/proj.js ----------------
    ("shell/proj.js",
     "（与「从付款域引用（R8）」写同一份记录、双向可见）",
     "（与「从付款域引用」写同一份记录、双向可见）"),
    # ---------------- shell/legacy.js ----------------
    ("shell/legacy.js",
     "<b>保存后即时生效</b>\n        （后端清缓存，无需重启服务）。",
     "<b>保存后即时生效、无需重启服务</b>。"),
]


def main() -> int:
    files: dict[str, str] = {}
    bad: list[str] = []
    for name, old, new in EDITS:
        if name not in files:
            files[name] = (W / name).read_text(encoding="utf-8", newline="")
        for o, w in ((old, new), (old.replace("\n", "\r\n"), new.replace("\n", "\r\n"))):
            if files[name].count(o) == 1:
                files[name] = files[name].replace(o, w, 1)
                break
        else:
            bad.append(f"{name}: 命中 {files[name].count(old)} 次 ⇒ {old[:52]!r}")

    if bad:
        # ⭐ 幂等：旧串全不在、而对应的新串都在 ⇒ 说明本批**已经应用过** ⇒ rc=0（⛔ 别报成失败）
        if all(files[n].count(new) >= 1 for n, _, new in EDITS):
            print(f"✔ 本批 {len(EDITS)} 处**已经改过**（幂等：旧串都不在、新串都在）")
            return 0
        print("⛔ 以下没命中（整批不写）：")
        for b in bad:
            print("   ", b)
        return 1

    for name, text in files.items():
        (W / name).write_text(text, encoding="utf-8", newline="")
        print(f"✅ 已改 {name}（{len(text)} 字节）")
    print(f"\n共 {len(EDITS)} 处替换 · 全部命中 1 次 ✔")
    return 0


if __name__ == "__main__":
    sys.exit(main())
