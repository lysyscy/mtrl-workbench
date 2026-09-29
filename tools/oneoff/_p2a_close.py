"""`P2-a` 收尾：台账**销号**（`TAIL-164` ＋ 伞 `TAIL-145`）＋ 守则 §10 记一笔 ＋ 审计件状态订正。

一次性脚本，带 `--check`。操作**按行/按前缀**（⛔ 不整串替换 —— 计划是 CRLF，逐行更稳）。

跑法：`backend/.venv/Scripts/python.exe -X utf8 tools/oneoff/_p2a_close.py --check`
      `backend/.venv/Scripts/python.exe -X utf8 tools/oneoff/_p2a_close.py`
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PLAN = REPO / ".workbuddy" / "plans" / "开发计划-主文档.md"
AUDIT = REPO / ".workbuddy" / "work" / "10-designs" / "设计-前端系统性重构审计-20260928.md"
RULES = REPO / "ops" / "前端设计守则-以使用用户为中心.md"

TAIL164 = (
    "| `TAIL-164` | ✂️ **`P2-a` 拆 `index.html` 的「非切片」内联 JS**（用户裁定走 **`A` 档**）：把内联 `<script>` 里"
    "**非 `V.*` 切片**的顶层段按件搬进 `web/shell/*.js` ⇒ 新 **6 件**（`base` 公共常量/纯函数/排序内核 · "
    "`view` 导航/渲染内核/虚拟滚动 · `ui` 共用 UI 件与浮层 · `proj` 通知书草稿/表格件/表头常量/集采口径 · "
    "`pages-a` 付款域三页辅助 ＋ `BIND` · `pages-b` 其余各页辅助）；⛔ **`V.*` 原型切片一行未搬**（计划 §23 口径）· "
    "⛔ 不动 CSS · ⛔ 不改口径、不动后端。`index.html` **3967 → 1627 行**、壳 **6 → 12 件**。"
    "⚠️ **拆件必须两处登记**：`index.html` 的 `<script src>` ＋ `main.py` 一条路由（缺 ⇒ 404 ⇒ 整支崩，"
    "判据 `tests/test_shell_part_routes.py`）。⚠️ 途中查出的**两类真坑**（都写进守则 §10）："
    "① 内联脚本里有 **7 处加载期就调 `bjMonth()`** 的筛初值 ⇒ **时钟簇必须留在 `index.html`**"
    "（否则内联脚本当场中断、其后 `const` 停在 TDZ ⇒ **页面空白而离线断言全绿**）；"
    "② 新件路由加完**必须重启后端**，否则真机 404（离线看不见）。"
    "⚠️ 同批按本仓惯例**改指**了 6 条\"按锚点直读 `index.html`\"的判据（判据内容一字未改）。 "
    "| 用户 2026-09-28「可以，那按 `A` 吧」；判据 = pytest **616 绿 / 0 红** · 12 把尺子 rc=0 · "
    "真机 `_shell_smoke` **rc=0** · `ui_parity` **U1 无未登记漂移**（新增登记 **35** 行，逐条审过＝全是基建行）/ "
    "`U5` 43 件逐字一致 · 盖章 5 次（末次 `20260929-0004`） | 2026-09-28 |"
)
TAIL145 = (
    "| `TAIL-145` | 🏗 **伞：前端全页面系统性重构**（用户 2026-09-28）—— 三档 **9 批全部完成**："
    "`P0-a` 死代码清账 / `P0-b` `imp`·`set` 补页级判据 / `P0-c` 内联样式补 `--fscale` / `P1-a` 展开区变体类 / "
    "`P1-c` 下拉清点 / `P1-b` 卡头形态 / `P2-c` 逐页走查（产出 `TAIL-153`…`162`）/ `P2-b` 注释分级 / "
    "**`P2-a` 拆 `index.html`**（`TAIL-164`）。⭐ 净结果：`index.html` **3967 → 1627 行**、壳 6 → 12 件、"
    "`P0-c` 279 处内联字号/间距接上「界面大小四档」。 "
    "| 用户 2026-09-28「对前端所有页面的全部模块进行系统性重构」＋「按推荐顺序开工」＋ 各批次逐条裁定；"
    "判据 = 各批自己的判据 ＋ 全闸门绿 | 2026-09-28 |"
)
RULE_ROW = (
    "| 2026-09-28 | ⭐ **`P2-a`：`index.html` 拆件（「只拆非切片」）**（`TAIL-164`）—— 内联脚本里**非 `V.*` 切片**的 "
    "顶层段按件搬进 `web/shell/*.js` ⇒ 新 6 件，`index.html` **3967 → 1627 行**。**两条可复用的硬结论**："
    "① ⛔ **`V.*` 原型切片不许搬**（计划 §23：`U1` 逐行比它）—— 只搬切片外 ⇒ **`U1` 零漂移**；"
    "② ⚠️⚠️ **`index.html` 里\"加载期就求值\"的顶层声明⛔ 不许引到\"晚加载的件\"里的名字** —— 本仓真例："
    "7 处筛初值写成 `let fX={ym:bjMonth()}`，把时钟簇搬走 ⇒ **`bjMonth is not defined` ⇒ 内联脚本当场中断、"
    "其后所有 `const` 停在 TDZ ⇒ 页面空白，而 pytest / `node --check` 全绿**（只有真机 `/app` 看得见）。"
    "⇒ 立的做法：**新件的 `<script src>` 一律插在 `actions.js` 之前**（保持原相对顺序）＋ 把\"加载期被调的名字\""
    "列入 `keep` 留在 `index.html` ＋ 拆件脚本带**加载期依赖预检**。⚠️ 另两条：**加件必须同时改 `main.py` 路由并重启后端**"
    "（缺 ⇒ 真机 404）；拆件会让\"按锚点直读 `index.html`\"的判据假红 ⇒ 按本仓惯例**改指合并后的壳**（⛔ 不是不许拆件）。 "
    "| §5.9 §2.4（可维护性）＋ §0「能机器判的必须挂判据」 | 判据 = pytest 616/0 · 12 把尺子 rc=0 · 真机 `_shell_smoke` rc=0 · "
    "`ui_parity` U1 0 未登记漂移 ＋ `U5` 43 件逐字一致 · 盖章 `20260929-0004` | 用户 2026-09-28「可以，那按 `A` 吧」 | "
    "⭐ 教训：**\"离线全绿\" 远不等于\"页面能用\"** —— 拆件的失败模式（404 / 加载期依赖 / `<script>` 顺序）**全在离线判据的盲区**，"
    "只能靠真机 `/app` 走一遍 |"
)

#: `(文件, 操作, 参数…)`：`rep` 整行替换（按唯一前缀定位）· `ins_before` 插在该前缀行之前 · `drop` 删行（按前缀）
OPS: list[tuple] = [
    (PLAN, "rep", "| 🏗 **进行中**（一件一批；每批跑全闸门 ＋ 盖章）",
     "| ✅ **已做（2026-09-28 · 留痕，别删）**—— 6 件全部拆完（`base`/`view`/`ui`/`proj`/`pages-a`/`pages-b`）· "
     "`index.html` **3967 → 1627 行**、壳 **6 → 12 件** |"),
    (PLAN, "rep", "| 🏗 **进行中**（2026-09-28 用户裁定「A」＋「按推荐顺序开工」· 见 §15 本行）",
     "| ✅ **已做（2026-09-28 · 留痕，别删）**—— 三档 9 批**全部完成**（`P0-a`…`P2-c`，见 `TAIL-146`…`164`）；"
     "壳 **6 → 12 件**、`index.html` **3967 → 1627 行** |"),
    # ⚠️ **顺序要紧**：先删 §一 的 A 类行，再往 §四 插已销号行 ——
    #    否则新插的已销号行与 A 类行**同前缀**，会被同一趟的 drop 一起删掉（dry-run 实测踩到）。
    (PLAN, "drop", ["| `TAIL-164` | ⭐ **`P2-a` 拆", "| `TAIL-145` | 🏗 **伞：前端全页面系统性重构**"], None),
    (PLAN, "ins_before", "| `TAIL-156` | 🧩 **`P2-c` 走查发现④", [TAIL145, TAIL164]),
    (PLAN, "rep", "A 类 **11** 条 · B 类 0 · C 类 **0** · 已销号 **156**",
     "A 类 **9** 条 · B 类 0 · C 类 **0** · 已销号 **158**"),
    (PLAN, "rep", "A 类 **11** 条 · B 类 **0** 条 · C 类 **0** 条 · 已销号 **156** 条",
     "A 类 **9** 条 · B 类 **0** 条 · C 类 **0** 条 · 已销号 **158** 条"),
    (RULES, "ins_after", "| 2026-09-28 | ⭐ **补一条落点约定**", [RULE_ROW]),   # ⚠️ 接在 §10 表最后一行之后
    (AUDIT, "rep", "`shell_source` 的件清单自动跟进） |",
     "`shell_source` 的件清单自动跟进） · ✅ **已完成（2026-09-28 · `TAIL-164`）**：6 件拆完、`index.html` **3967 → 1627 行**、"
     "壳 6 → 12 件，全闸门绿（末次盖章 `20260929-0004`） |"),
    (AUDIT, "rep", "> **状态**：**审计完成 · 待用户点批次**",
     "> **状态**：⭐ **9 批全部完成**（`P0-a`…`P2-a` · 2026-09-28 · 末批 = `TAIL-164`）—— 本件现在是**历史审计留痕**，"
     "⛔ 别按\"待点批次\"读（原状态：审计完成 · 待用户点批次"),
]


def _read(p: Path) -> tuple[list[str], bool]:
    t = p.read_text(encoding="utf-8", newline="")
    return t.split("\n"), "\r\n" in t


def _write(p: Path, lines: list[str], crlf: bool) -> None:
    t = "\n".join(lines)
    t = t.replace("\r\n", "\n")
    if crlf:
        t = t.replace("\n", "\r\n")
    p.write_text(t, encoding="utf-8", newline="")


def main() -> int:
    ap = argparse.ArgumentParser(description="P2-a 收尾（销号 ＋ 守则 §10 ＋ 审计件状态）")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()

    cache: dict[Path, tuple[list[str], bool]] = {}
    bad = 0
    for path, op, key, val in OPS:
        if path not in cache:
            cache[path] = _read(path)
        lines, crlf = cache[path]
        ln_all = "\n".join(lines)
        if op == "rep":
            idx = [i for i, ln in enumerate(lines) if key in ln]
        elif op in ("ins_before", "ins_after"):
            idx = [i for i, ln in enumerate(lines) if key in ln]
        else:                                        # drop：`key` 是前缀**列表**
            idx = [i for i, ln in enumerate(lines) if any(ln.startswith(p) for p in key)]

        if op == "rep":
            if val.rstrip("\r") in ln_all:
                print(f"  ⚠️ 已应用  {path.name} :: {key[:40]}…")
                continue
            if len(idx) != 1:
                print(f"  ⛔ 命中 {len(idx)} 行  {path.name} :: {key[:40]}…")
                bad += 1
                continue
            lines[idx[0]] = val + ("\r" if crlf else "")
            print(f"  ✅ 替换    {path.name} :: {key[:36]}…")
        elif op in ("ins_before", "ins_after"):
            if val[-1].rstrip("\r") in ln_all:       # ⚠️ 用**最后一行**当"已插入"的标记（首行可能与其他行同前缀）
                print(f"  ⚠️ 已应用  {path.name} :: 插入 {val[0][:36]}…")
                continue
            if len(idx) != 1:
                print(f"  ⛔ 锚点命中 {len(idx)} 行  {path.name} :: {key[:36]}…")
                bad += 1
                continue
            at = idx[0] if op == "ins_before" else idx[0] + 1
            lines[at:at] = [x + ("\r" if crlf else "") for x in val]
            print(f"  ✅ 插入 {len(val)} 行  {path.name} :: {key[:30]}…")
        else:                                        # drop
            if not idx:
                print(f"  ⚠️ 已应用  {path.name} :: 删 {key[0][:36]}…")
                continue
            for i in reversed(idx):
                del lines[i]
            print(f"  ✅ 删除 {len(idx)} 行  {path.name}")

    if bad:
        print(f"\n⛔ 有 {bad} 条没命中 ⇒ 别硬改")
        return 1
    if a.check:
        print("\n✅ dry-run 通过")
        return 0
    for p, (lines, crlf) in cache.items():
        _write(p, lines, crlf)
        print(f"⇒ 已写入 {p.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
