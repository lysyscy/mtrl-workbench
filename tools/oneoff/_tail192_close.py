"""`TAIL-192`（结构审计 P0 四件）**销号** ＋ 同批订正计划里那处过期的壳件数（`TAIL-192`-③ 的第四处）。

⭐ 为什么落成脚本（而不是手改）：销号是**四处一起动**，且两处是**行手术** ——
本仓在这上面踩过两次（插行后下标整体失效 ⇒ 删错了别人的行）。⇒ 每步都断言「**恰好命中一次**」，
`--check` 先干跑；⛔ 任何一处不满足就**一个文件都不写**。

五类手术：
  ① §一 A 类表：**删掉** `TAIL-192` 那一整行（销号**不释放编号** ⇒ ⛔ 别改成占位行）；
  ② §四 已销号表：**在表头下一行插入**新行（⚠️ 该表**没有** `|---|` 分隔行 ⇒ 别按"标题后第一个 `|---`"找）；
  ③ §14.3 排期表：`TAIL-192` 那行的**状态格**改 ✅（⚠️ 单元格里会出现 `|词1|词2|` ⇒ 状态格 = **最后一个 `|…|`**）；
  ④ 两处**计数行**（§0 与 §15 顶部，写法略有不同 ⇒ 两处都改）；
  ⑤ §0.1 里那处**过期的壳件数**（原写「`web/shell/` 五件 … ＝ **6 件**」⇒ 改成指针）。

⚠️ 行手术（①②）**排在任何字符串替换之前**（先算下标会被插行整体搞坏）。
⚠️ 本文件是 **CRLF** ⇒ 读用 `newline=""`、写回 `\r\n`。

跑法：
  `backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_tail192_close.py --check`   # 干跑
  `… --write`                                                                            # 真写
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / ".workbuddy" / "plans" / "开发计划-主文档.md"

A_ROW_PREFIX = "| `TAIL-192` | ⭐ **结构审计 P0 四件**"
SEC4_HEAD = "| # | 事项 | 销号依据 | 日期 |"
SEC43_PREFIX = "| `TAIL-192` ⭐ **结构审计 P0 四件**（配置说清 ＋ 注释订正 ＋ 一处核查） |"

COUNT_SEC0 = "A 类 **9** 条 · B 类 0 · C 类 **0** · 已销号 **189**"
COUNT_SEC15 = "A 类 **9** 条 · B 类 **0** 条 · C 类 **0** 条 · 已销号 **189** 条"

#: §0.1 里过期的壳件数（原抄了 4 个件名 ＋ 写死件数 ⇒ 拆件后必漂）
STALE_SHELL = (
    "＋ **`web/shell/` 五件**（`actions.js` · `legacy.js` · `api.js` · `core.js` · `print-export.js`）"
    "＝ **6 件**（`P4` 拆包 ＋ `TAIL-77` 补记；⚠️ 读壳的**唯一出口** = "
    "`tools/audit/shell_source.py`，⛔ 别再从单文件读）"
)
FIXED_SHELL = (
    "＋ **`web/shell/` 各件**（⚠️ ⛔ **别在这里写死件数与件名** —— 拆件会涨；"
    "件清单与加载顺序的**唯一出口** = `index.html` 的 `<script src>`，读壳走 `tools/audit/shell_source.py`）"
)

SEC43_NEW = (
    "| `TAIL-192` ⭐ **结构审计 P0 四件**（配置说清 ＋ 注释订正 ＋ 一处核查） | "
    "✅ **已办（2026-09-29）** ⇒ 见 §15 §四 | "
    "**实际落点**（与登记时那格不同，已按根 `README.md` §五「配置项有哪些 ⇒ `ops/README.md`」改，⛔ 不新建文档）："
    "`ops/README.md` **§一之五 配置主人表** ＋ 仓根 `.env.example`（补 5 键）＋ "
    "`docs/architecture.md` / `backend/app/main.py` / `tools/audit/shell_source.py` / `web/shell/core.js` 四处过期说法 ＋ "
    "`actions.js` 局部 `API` **改名 `apiCode`**（防遮蔽）；判据 = `tests/test_config_env_example.py`（新建 2 条）＋ "
    "`tests/test_shell_part_routes.py`（+3 条）＋ `tools/mut/_mut_tail192.py` **4/4** | "
    "触发 = 用户 2026-09-29「按推荐开始就好」 |"
)

SEC4_NEW = (
    "| `TAIL-192` | ⭐ **结构审计 P0 四件**：① `.env.example` 补 `I8_SM2_PRIVATE_KEY` / `PRINT_MODE` / "
    "`PRINTER_NAME` / `OPERATOR_NAME` / `SESSION_SECRET`（各带一句「填什么 / 不填会怎样」）；"
    "② **配置主人表**落 `ops/README.md` **§一之五**（⚠️ 登记时那格写「放 `docs/`」，实际按根 `README.md` §五"
    "「配置项有哪些 ⇒ `ops/README.md`」落 —— ⛔ 不新建文档）；③ 订正**四处**过期说法："
    "`docs/architecture.md`（原抄 4 个件名）· `backend/app/main.py`（原写「这三件」）· "
    "`tools/audit/shell_source.py`（原写「现为 6 件」）· `web/shell/core.js` 头注（仍说 `API` 在本件）；"
    "④ `actions.js` 的局部 `const API={…}` ⇒ 改名 **`apiCode`** —— ⭐ **核查结论 = 有意**（那是「接口代号」映射，"
    "不是笔误），但**与全局数据出口同名** ⇒ 那个函数里一旦再用 `API.xxx` 就**静默失效**（当时没炸纯属没用到）；"
    "⭐ **同批挂判据**：新建 `tests/test_config_env_example.py`（样例必须覆盖 `Settings` 全部字段 ＋ 配置主人表在位）＋ "
    "`tests/test_shell_part_routes.py` **+3 条**（不许写死壳件数 · `API` 只许在 `api.js` 里定义 · `core.js` 头注要指路）＋ "
    "反向灵敏度 `tools/mut/_mut_tail192.py` **4/4**（四态**仍 641**：这四条**刻意不绑契约面** —— 守的是工程侧可操作性、"
    "不对应「用户看得见的行为」）；⚠️ **实测订正一处**：审计件写「README 与 `main.py` 说壳 12 件」—— "
    "**活文档里没有写死 12 的地方**，真漂的是上面那四处（含计划 §0.1 原写「＝ 6 件」） | "
    "用户 2026-09-29「按推荐开始就好」（出处 = `.codebuddy/memory/2026-09-29.md` §㊼/㊽） | 2026-09-29 |"
)


def _once(lines: list[str], pred, what: str) -> int:
    hit = [i for i, ln in enumerate(lines) if pred(ln)]
    if len(hit) != 1:
        raise SystemExit(f"⛔ {what}：期望恰好命中 1 处，实测 {len(hit)} 处 ⇒ 停手（一个文件都不写）")
    return hit[0]


def _once_text(text: str, needle: str, what: str) -> None:
    n = text.count(needle)
    if n != 1:
        raise SystemExit(f"⛔ {what}：期望恰好命中 1 处，实测 {n} 处 ⇒ 停手")


def build(raw: str) -> str:
    assert "\r\n" in raw, "本文件应当是 CRLF"
    lines = raw.split("\r\n")

    # ── ① 行手术：删 A 类那一行（先做；插行会让后面的下标失效）
    i_a = _once(lines, lambda ln: ln.startswith(A_ROW_PREFIX), "§一 A 类表里的 `TAIL-192` 行")
    del lines[i_a]

    # ── ② 行手术：§四 表头**下一行**插入（该表没有 `|---|` 分隔行）
    i_h = _once(lines, lambda ln: ln.strip() == SEC4_HEAD, "§四「已销号」表头")
    lines.insert(i_h + 1, SEC4_NEW)

    text = "\r\n".join(lines)

    # ── ③ §14.3 排期行 ⇒ ✅（整行替换）
    _once_text(text, SEC43_PREFIX, "§14.3 的 `TAIL-192` 行前缀")
    old43 = next(ln for ln in text.split("\r\n") if ln.startswith(SEC43_PREFIX))
    text = text.replace(old43, SEC43_NEW, 1)

    # ── ④ 两处计数
    _once_text(text, COUNT_SEC0, "§0 的计数行")
    _once_text(text, COUNT_SEC15, "§15 顶部的计数行")
    text = text.replace(COUNT_SEC0, COUNT_SEC0.replace("**9**", "**8**").replace("**189**", "**190**"), 1)
    text = text.replace(
        COUNT_SEC15, COUNT_SEC15.replace("**9** 条", "**8** 条").replace("**189**", "**190**"), 1
    )

    # ── ⑤ §0.1 那处过期的壳件数 ⇒ 指针
    _once_text(text, STALE_SHELL, "§0.1 的壳件数")
    text = text.replace(STALE_SHELL, FIXED_SHELL, 1)

    return text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="真写（默认只干跑）")
    ap.add_argument("--check", action="store_true", help="显式的干跑（与 --write 互斥；本仓惯例）")
    args = ap.parse_args()

    raw = PLAN.read_text(encoding="utf-8", newline="")
    new = build(raw)

    before, after = raw.split("\r\n"), new.split("\r\n")
    print(f"行数：{len(before)} → {len(after)}（期望**相等**：删 1 行 ＋ 插 1 行）")
    print(f"字节：{len(raw.encode('utf-8'))} → {len(new.encode('utf-8'))}")
    print("计数行、壳件数、§14.3、§四 均已按「恰好一次」校验 ✓")
    if not args.write:
        print("\n（--check 干跑结束；加 --write 才落盘）")
        return 0
    PLAN.write_text(new, encoding="utf-8", newline="")
    print("\n✅ 已写回 .workbuddy/plans/开发计划-主文档.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
