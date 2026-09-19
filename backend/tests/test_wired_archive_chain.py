"""`TAIL-29`-③ · 抓取链路接「付款侧自动建档」（链路 A）的**接线断言**（离线 · 静态）。

⚠️ **本文件测不了什么**：它是**静态检查**（源码里那几环在不在、**顺序**对不对），
   **不证明运行时真调通** —— 那只能靠真机抓取。两把都要（「判据绿 ≠ 链路对」的教训）。

⭐ 为什么用**行序**断言而不是「字符串在不在」：`assert "sync_and_archive(" in src`
   这种写法只要**注释里提一句**就会假绿。这里改成「判定 → 建档 → 重判」的**顺序**断言。
"""

from __future__ import annotations

from pathlib import Path

from tests.acc_plugin import acc

from app.mod01_projects.domain import OwnershipDecision, needs_archive

# ⚠️ 2026-09-19（`T5` 拆件）：下面三条**行序断言**钉的是「判定 → 建档 → 重判」那一段 ——
#    它的**实体**已从 `router.py` 搬到 `notice_executors.py`（`router.py` 只再导出执行器）
#    ⇒ **观测面跟着搬**（⛔ 判据一字未改：顺序仍必须是对的），并把"再导出还在"另立一条守卫。
EXEC_SRC = (
    Path(__file__).resolve().parents[1] / "app" / "mod03_notice" / "notice_executors.py"
).read_text(encoding="utf-8")
#: `router.py` 本体 —— 只用于钉「拆件后**再导出**仍在」（`tools/chain_expected.txt` 的落点指它）。
ROUTER_SRC = (
    Path(__file__).resolve().parents[1] / "app" / "mod03_notice" / "router.py"
).read_text(encoding="utf-8")


# --------------------------------------------------------------- 纯函数（判定「要不要建档」）


@acc("ACC-PRJ-SYNC-001", "001-11")
def test_有未建档的行就要走建档():
    assert needs_archive([OwnershipDecision("not_archived")]) is True


@acc("ACC-PRJ-SYNC-001", "001-11")
def test_全部已走完就不必建档():
    ds = [OwnershipDecision("normal", target_id=1), OwnershipDecision("small", target_id=2)]
    assert needs_archive(ds) is False


@acc("ACC-PRJ-SYNC-001", "001-11")
def test_未命中关键词不触发建档():
    """⚠️ `needs_keyword` / `needs_choice` 走的是**链路 C 弹窗**，不是建档 —— 两者别混。"""
    assert needs_archive([OwnershipDecision("needs_keyword", shell_id=1)]) is False
    assert needs_archive([OwnershipDecision("needs_choice", shell_id=1)]) is False


# --------------------------------------------------------------- 接线（行序）


def _idx(needle: str) -> int:
    i = EXEC_SRC.find(needle)
    assert i >= 0, f"抓取链路里找不到「{needle}」"
    return i


@acc("ACC-PRJ-SYNC-001", "001-11")
def test_顺序是判定到建档再到重判():
    """⭐ 钉住**顺序**：先问「要不要建档」→ 再建档 → 再**重判**（不重判 ⇒ 新档案不生效）。"""
    i_need = _idx("if needs_archive(")
    i_arch = _idx("archive_out = sync_and_archive(")
    i_rejudge = EXEC_SRC.find("judged = _judge()", i_arch)
    assert i_need < i_arch, "没有先判定「要不要建档」就去建档"
    assert i_rejudge > i_arch, "建档之后**没有重判** —— 新档案不会生效"


@acc("ACC-PRJ-SYNC-001", "001-11")
def test_建档复用同一个i8会话不额外登录():
    """⛔ 一次抓取只应登录一次 —— 否则会**多次强踢**（D9：反复顶号）。"""
    i_arch = _idx("archive_out = sync_and_archive(")
    seg = EXEC_SRC[i_arch:i_arch + 800]
    assert "cp_loader(allow_kick, client)" in seg, "常用项目名单没复用会话"
    assert "wh_loader(allow_kick, client)" in seg, "仓库名单没复用会话"


@acc("ACC-PRJ-SYNC-001", "001-11")
def test_降级时不拿空档案重判():
    """取数失败（降级）⇒ `sync_and_archive` **一行都不写** ⇒ 此时不得重判。"""
    i_arch = _idx("archive_out = sync_and_archive(")
    seg = EXEC_SRC[i_arch:i_arch + 1000]
    assert 'if not archive_out.get("degraded"):' in seg, "降级时没做保护"


@acc()
def test_拆件后router仍再导出四个执行器():
    """⛔ 2026-09-19 拆件（`T5`：「`router.py` 647 行 > 600 ⇒ 禁合入」）留下的**专属守卫**。

    四个执行器的**实体**已搬进 `notice_executors.py`，但：
    · `tools/chain_expected.txt` 的落点写的是 `router.py::名字`（`C3` 查"落点名在不在该文件里"）；
    · `tests/test_acc_pay_print.py` / `test_acc_pay_pdf.py` 从 `router.py` import 它们；
    ⇒ `router.py` 里那段**兼容再导出**是**接口的一部分**，⛔ 删了就让落点变幽灵、测试断掉。
    """
    for name in ("apply_fetched_row", "get_batch_executor",
                 "get_fetch_executor", "get_notice_lister"):
        assert f"    {name},\n" in ROUTER_SRC, f"`router.py` 不再再导出 `{name}`（落点表会变幽灵）"
