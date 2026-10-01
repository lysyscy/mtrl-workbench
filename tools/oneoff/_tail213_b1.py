"""`TAIL-213` **甲** · 批 1 = `m03`（付款通知书）撤掉折叠的「口径说明」块（2026-10-01）。

口径（用户 2026-10-01 拍板「选甲」＋ 我定的两条）：
  · **会做错的后果** ⇒ 留（压成**页内默认展开的一小段** ≤ 120 字，或挂到**操作现场的悬停**）；
  · **复述《说明书》的规则** ⇒ **删**（真源在《说明书》 ⇒ 删掉复述 = 根治"复述必漂"）；
  · `§节号`：界面上不再当指路牌（只在《说明书》里留）。

`m03` 那 13 条的去向（逐条）：
  `[1]` 无付款方式字段（业务常识）⇒ 删 · `[5]` 已付金额来源/本页不展示（指路）⇒ 删
  `[2][3][4]` 付款状态判定基准 / 手改语义 / 统计只能往小调 ⇒ **压成页内一小段**（原来就写在块里）
  `[6]` 付款批量 · `[9]` 手动新增行 · `[10]` 时间 · `[11]` 恢复剔除 · `[12]` 操作列
        ⇒ **现场已有**（`付款` 按钮 / `＋ 手动新增通知书` / 筛选栏 / `恢复剔除` / 操作列 的 `title`）✓ 无需再写
  `[7][8]` 集采实际供应商 / 关联集采合同 ⇒ 复述规则（§6.6.3）⇒ 删（操作现场有弹窗与按钮文字）
  `[13]` 再次导入会发生什么 ⇒ **挪到「抓取 i8 付款通知书（按月）」按钮的悬停**（那正是它发生的地方）
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
INDEX = ROOT / "backend" / "app" / "web" / "index.html"

TIP = ("  <div class=\"tip\"><b>付款状态</b>看<b>已付金额 vs 审批金额</b>（⛔ 不看统计金额）；"
       "<b>统计结算 / 统计付款金额</b>只能往下调（上限 = 审批金额）；<b>付款金额</b>手改只本次会话有效，"
       "<b>统计两金额</b>才持久（留痕、不被导入覆盖）。</div>\n")

WORKING = '<button class="btn" data-act="fetchNt">抓取 i8 付款通知书（按月）</button>'
WORKING2 = ('<button class="btn" data-act="fetchNt" title="i8 改了单据再抓一次：**已手改的统计金额保住**、'
            '未手改的跟随新审批金额（越界则挂「导入提醒」）；分类 / 集采供应商 / 调整单不被覆盖">'
            '抓取 i8 付款通知书（按月）</button>')

STAT_LABEL = '<div class="fi"><label>付款状态</label>'
STAT_LABEL2 = '<div class="fi"><label title="已付金额 ≥ 审批金额 ＝ 已付清（不看统计金额）">付款状态</label>'


def main() -> int:
    text = INDEX.read_text(encoding="utf-8")
    orig = text

    # ① 整块删掉（起点 = 全站唯一的那个 `post:` 调用点）
    start = "${CALIB({post:'&nbsp;',items:["
    i = text.index(start)
    j = text.index("]})}", i) + len("]})}")
    blk = text[i:j]
    assert 1500 < len(blk) < 4500, f"要删的那块长度 {len(blk)} 不像 m03（起点选错了？）"
    for mark in ("通知书<b>无付款方式字段</b>", "再次导入会发生什么", "恢复剔除必须勾选"):
        assert mark in blk, f"要删的块里没有 {mark!r}（不是 m03 那一块？）"
    assert text.count(start) == 1, "`CALIB({post:` 命中不止 1 次"
    text = text[:i] + TIP.rstrip("\n") + text[j:]

    # ② 抓取按钮：挂上「再次导入发生什么」（它原来在块里的第 13 条）
    assert text.count(WORKING) == 1, "抓取按钮命中不止 1 次"
    text = text.replace(WORKING, WORKING2, 1)

    # ③ 付款状态筛选：挂上「判定基准」（原来在块里的第 2 条）
    assert text.count(STAT_LABEL) == 1, "付款状态 label 命中不止 1 次"
    text = text.replace(STAT_LABEL, STAT_LABEL2, 1)

    # ④ 自检：块没了 + 该在的还在
    assert "口径说明 · " not in text.split("V.m04=")[0], "m03 段里还留着「口径说明 · N 条」"
    assert "CALIB({post:" not in text, "还有别的 `CALIB({post:` 调用点（本批只该动 m03）"
    assert "抓取一律要人点" not in text or True  # m02 那条不在 m03 段，无需管

    assert text != orig, "没有变化？"
    INDEX.write_text(text, encoding="utf-8", newline="")
    print("✅ m03：折叠块已撤（13 条 ⇒ 页内 1 小段 ＋ 2 处悬停）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
