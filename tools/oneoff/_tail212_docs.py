"""`TAIL-212` 的台账 / 交接刷新（**一次性** · `TAIL-212` · 2026-10-01）。

干什么（每一条都**先断言命中 1 次**，任一条不达标 ⇒ **整批不写盘**）：
  ① §15 §一 删掉 `TAIL-212` 那一行（它已办完 ⇒ 移到 §四）
  ② §14.3 排期表删掉 `TAIL-212` 那条（**登记即排期**：销号要同步销排期）
  ③ §15 §四 插入 `TAIL-212` 的**销号依据**行
  ④ §15 顶部计数：A 类 **2 → 1** · 已销号 **213 → 214**
  ⑤ §0.2 的位置块：同一处计数同改 ＋ 把 `TAIL-212` 从「候选」改写成「已办」
  ⑥ §13.6 **修订 17** 行内增量：把 `TAIL-212` 标成「已办销号」（⚠️ 交接表是**当前状态表** ⇒ 行内更新，⛔ 不另开第二份）
     —— ⚠️ 这一处的原文里有 **ASCII 引号**，所以走「起点…终点」**切片替换**，⛔ 不硬拼整串
  ⑦ §15 顶部加一行「深夜之七之二」留痕
  ⑧ §13.6 入门口令的「点名单」同步（`TAIL-212` 已不是待办）
  ⑨ 根 `README.md` §〇：把「报错里还夹着英文技术串」那条从「已登记」改成「已办」

⚠️ 为什么用脚本：这些行都**很长**，手改容易漏一半 ⇒ 点位 ＋ 命中数断言是这台机器上最省事又最不会错的做法
  （同族：`_tail210_docs.py` / `_tail211_docs.py`）。
⚠️ 本件里的引号一律用「」，⛔ 别在 `"` 串里再嵌 `"`（写第一版时就是这么崩的：`SyntaxError`）。
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
PLAN = ROOT / ".codebuddy" / "plans" / "开发计划-主文档.md"
README = ROOT / "README.md"

_ROW_HEAD = "| `TAIL-212` | 💬 **把 Python 异常类名／原始异常串拼进用户可见文案**"

SECTION4_ROW = (
    _ROW_HEAD
    + " | **销号依据** = 用户 2026-10-01「提交；然后继续」（承接上一轮「技术串」收尾：`client.py` 的 "
    + "URL／状态码／响应原文 · `fetch_task.degrade*` 的异常类名 · `resources.py` 的模板路径与 SHA —— "
    + "当场办掉、但**同类还剩一大片**）⇒ **当日立 · 当日办 · 当日销**："
    + "① **先量** = 搜 `type(exc).__name__` ⇒ `backend/app` **23 处 / 15 件**；"
    + "② **口径建档** = `.codebuddy/work/40-decisions/D29-文案审计口径-以熟手为准.md` **§六**"
    + "（判据一句话：**这句是给「用系统的人」看的，还是给「修系统的人」看的？**）—— "
    + "⛔ 异常类名／原文／URL／状态码／路径**只给后者**；⭐ **两条例外都写明了**：**执行记录**"
    + "（`error_message=`，排障面，`test_acc_inv_fetch` 钉着「boom 要落进去」）· **打印机地址**（`ipp://…`，"
    + "用户要拿去核对，`test_acc_pay_print` 的 `001-08`② 钉着「失败要带出地址」）；"
    + "③ **唯一出口** = `app/core/errors.py` 新加 `human_reason(人话前缀, exc, next_step=…)` ＋ `log_exc(前缀, exc)`"
    + "（⚠️ `get_logger()` **在函数里 import** —— `core.logging → core.config → core.errors` 是**环**，"
    + "顶层导入会让 `conftest` 直接 `ImportError: partially initialized module`，2026-10-01 实测）；"
    + "④ **清 19 处**（回执／报错／明细全换人话 ＋ 细节进日志）：`import_kit/api.py` 6（取本域选项／解析／预览／"
    + "导入／回滚／明细「不是数字」）· `mod03_notice/router.py` 3（仓库名单 ×2 ＋ 批量执行失败）· "
    + "`mod01_projects/recovery.py` 3（建档降级／扶正／建档）· `print/render.py` · `print/ipp.py` · "
    + "`print/dispatch.py` · `service.py::_reason` 兜底 · `mod11_jc/fetch_service.py` · "
    + "`mod11_jc/import_service.py` · `mod02_i8/login.py` · `mod01_projects/sync_service.py` · `home/service.py`；"
    + "**刻意保留 4 处**（3 条执行记录 ＋ 1 处已有的日志）；"
    + "⑤ **机器眼** = `tests/test_ux_text.py::test_用户可见串里不许拼异常原文`（`@acc()` ⇒ **判据点不涨**）："
    + "**AST** 扫 `backend/app/**`（注释与 docstring **天然看不见** —— 本件头部那条「手写词法机被注释带偏」的教训）"
    + "＋ **逐行白名单** `logger.` / `log_exc(` / `human_reason(` / `error_message=`；"
    + "**自证** `tools/oneoff/_tail209_mark_proof.py` **5 → 6 条**（新增 `T6`：写进用户可见串 ⇒ 必红；"
    + "⭐ 写进**注释**／**裸表达式语句** ⇒ 不红 —— ⚠️ 自证当场抓到两个**假红**：「只跳 `node.value` 没跳子孙」"
    + "＋「没跳语句节点自己」） | 2026-10-01 |"
)

NOTE_LINE = (
    "> ⭐ **2026-10-01（深夜之七之二）**：⭐⭐ **`TAIL-212` 当日立 · 当日办 · 当日销** —— 「异常类名／原始串拼进"
    "**用户可见**文案」那一类：先量 **23 处 / 15 件** ⇒ 逐处判「给谁看」 ⇒ **清 19 处**（回执／报错／明细 ⇒ "
    "人话 ＋ 下一步，细节进运行日志）＋ **刻意保留 4 处**（执行记录 3 ＋ 日志 1）⇒ 新落**唯一出口** "
    "`app/core/errors.py::human_reason / log_exc` ＋ **机器眼**（`test_ux_text.py::test_用户可见串里不许拼异常原文`，"
    "`@acc()` ⇒ 判据点仍 **644**）＋ **自证 6/6**；口径落纸 = `D29` **§六**（含**两条例外**：执行记录 · 打印机地址）"
    "⇒ A 类 **2 → 1 条**、已销号 **213 → 214**（**两处计数同改**：本节顶部 ＋ §0.2）。\n"
)

NEW_TAIL = (
    "④ ⭐⭐ **`TAIL-212`（异常类名／原文拼进用户可见文案）当日立 · 办 · 销**：量 **23 处 / 15 件** ⇒ "
    "**清 19 处**（回执／报错／明细 ⇒ 人话 ＋ 下一步，细节进运行日志）＋ **保留 4 处**（执行记录 3 ＋ 日志 1）＋ "
    "**唯一出口** `app/core/errors.py::human_reason / log_exc` ＋ **机器眼**（`test_ux_text.py::"
    "test_用户可见串里不许拼异常原文`，`@acc()` ⇒ **判据点仍 644**）＋ **自证 6/6** ⇒ 依据见 §15 §四"
)


def _once(text: str, needle: str) -> None:
    n = text.count(needle)
    assert n == 1, f"锚点命中 {n} 次（要 1 次）：{needle[:80]!r}"


def _drop_line(text: str, prefix: str) -> str:
    lines = text.split("\n")
    hit = [i for i, ln in enumerate(lines) if ln.startswith(prefix)]
    assert len(hit) == 1, f"要删的行命中 {len(hit)} 次（要 1 次）：{prefix[:60]!r}"
    del lines[hit[0]]
    return "\n".join(lines)


def _swap_span(text: str, start: str, end: str, new: str, *, limit: int = 400) -> str:
    """把从 `start` 起到 `end`（含）的那一段整段换成 `new`（⚠️ 避开原文里的引号）。"""
    i = text.index(start)
    j = text.index(end, i) + len(end)
    assert 0 < j - i < limit, f"要替换的那段长度 {j - i} 不像（>={limit}？起点/终点选错了）"
    return text[:i] + new + text[j:]


def main() -> int:
    plan = PLAN.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")

    # ① §15 §一 删行（待做表）
    plan = _drop_line(plan, _ROW_HEAD)
    # ② §14.3 删行（排期表）
    plan = _drop_line(plan, "| `TAIL-212` **异常串上屏**")
    # ③ §15 §四 插入销号行
    _once(plan, "| # | 事项 | 销号依据 | 日期 |\n")
    plan = plan.replace("| # | 事项 | 销号依据 | 日期 |\n",
                        "| # | 事项 | 销号依据 | 日期 |\n" + SECTION4_ROW + "\n", 1)
    # ④ 计数（顶部 ＋ §0.2）
    _once(plan, "A 类 **2** 条 · B 类 **0** 条 · C 类 **0** 条 · 已销号 **213** 条")
    plan = plan.replace("A 类 **2** 条 · B 类 **0** 条 · C 类 **0** 条 · 已销号 **213** 条",
                        "A 类 **1** 条 · B 类 **0** 条 · C 类 **0** 条 · 已销号 **214** 条", 1)
    _once(plan, "A 类 **2** 条 · B 类 0 · C 类 **0** · 已销号 **213**")
    plan = plan.replace("A 类 **2** 条 · B 类 0 · C 类 **0** · 已销号 **213**",
                        "A 类 **1** 条 · B 类 0 · C 类 **0** · 已销号 **214**", 1)
    # ⑤ §0.2 位置块：候选写法 ⇒ 已办
    old_cand = ("② ⭐ **新 `TAIL-212`**（**把异常类名／原始串拼进用户可见文案** —— 实测 `backend/app` 还剩 "
                "**23 处 / 15 件**；建议**先分类**「回执/报错」vs「执行记录/排障面」＋ 做**一个共用出口**）。")
    _once(plan, old_cand)
    plan = plan.replace(
        old_cand,
        "② ✅ **`TAIL-212`（异常类名／原文拼进用户可见文案）当日已办销号**"
        "（清 **19 处** ＋ 唯一出口 `human_reason` ＋ 机器眼 ＋ 自证 6/6 ⇒ 依据见 §15 §四）。", 1)
    # ⑥ §13.6 修订 17 行内增量（原文有 ASCII 引号 ⇒ 切片替换）
    plan = _swap_span(plan, "④ ⭐ **新尾巴 `TAIL-212`**", "另起一件）", NEW_TAIL)
    # ⑦ 顶部留痕（⚠️ 锚点带上「1 → 2」那一句 —— 单靠「两处计数同改」那句，四条留痕行都能命中）
    anchor = "⇒ A 类 **1 → 2 条**（**两处计数同改**：本节顶部 ＋ §0.2）。\n"
    _once(plan, anchor)
    plan = plan.replace(anchor, anchor + NOTE_LINE, 1)
    # ⑧ 入门口令的「点名单」
    old_pick = ("**B. 点名某条** ⇒ 从 §15 §一 挑（⚠️ 现为 **`TAIL-188` 交付包与迁移** ＋ "
                "⭐ **新 `TAIL-212`（异常串上屏 · 实测还剩 23 处 / 15 件）**；条数看 §15 顶部）；")
    _once(plan, old_pick)
    plan = plan.replace(
        old_pick,
        "**B. 点名某条** ⇒ 从 §15 §一 挑（⚠️ 现**只剩 `TAIL-188` 交付包与迁移**一条 —— "
        "`TAIL-209`–`212` 都已销号；条数看 §15 顶部）；", 1)
    # ⑨ README §〇
    _once(readme, "⏳ **已登记 `TAIL-212`**（实测约 **23 处**）：本轮先把最常撞见的几处")
    readme = readme.replace(
        "⏳ **已登记 `TAIL-212`**（实测约 **23 处**）：本轮先把最常撞见的几处",
        "✅ **2026-10-01 已办**（实测 **23 处** 清了 **19 处**；另**两处是刻意保留的例外** —— "
        "**执行记录**是排障面、**打印机地址**是你核对现场要看的）：最常撞见的几处", 1)

    PLAN.write_text(plan, encoding="utf-8", newline="")
    README.write_text(readme, encoding="utf-8", newline="")
    print("✅ 台账 / 交接 / README 已刷新（9 条，全部命中 1 次）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
