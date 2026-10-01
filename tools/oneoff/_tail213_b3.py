"""`TAIL-213` **甲** · 批 3 = `m05` / `m01` / `m02` / `m09`（21 条 / 1,205 字）（2026-10-01）。

四个块**都逐条读过**才定的（⛔ 不按摘要拍脑袋）：
  `m05` 付款流水与欠款（7 条）：欠款公式 ×2（业务常识）·「多次付款 / 撤销」**页内 tip 已有** ·
       「台账 第 1 行 / 当月新增不是累计」**页内 tip 已有** ⇒ 删；留 = 欠款口径 ≠「已付金额」· 机械欠款是派生的 ·
       期初占位行按分类并入。
  `m01` 项目档案（5 条）：「两把钥匙」·「四个名字」（《说明书》§2.3 / 页面上就有那几列）·「建档路径」（复述 §2.4.2，
       操作现场有同步按钮与空态指路）⇒ 删；留 = 尾码剥离 ·「归档只改状态、不动业务数据」。
  `m02` i8 接入（5 条）：留 = 只读消费方 · 要等过账 · 统一降级方案 · ⭐**抓取一律要人点**（**判据钉着**，原话要保）；
       删 = 「各项抓取触发位置」（侧栏就是）。
  `m09` 特殊费用（4 条）：留 = 「独立报表、不是第 3 张透视表」·「安文费是 CBS 类目不是报表名」；
       删 = 自动项来源 / 项目维度（**页内 tip 已有等价两句**）。
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
INDEX = ROOT / "backend" / "app" / "web" / "index.html"

TIP_M05 = ('  <div class="tip">欠款口径 = <b>结算 − 付款</b>，与「已付金额」<b>无关</b>（付款状态另按已付 ≥ 审批判定）；'
           '<b>机械欠款是派生的</b>（源头在过程资料机械 6 列、本页只读）；<b>期初占位行</b>手填后按其分类并入辅材 / 机械。</div>\n')
TIP_M01 = ('  <div class="tip">项目名尾部的括号编号（如 <span class="fc">(XMCB2025080001)</span>）由系统<b>统一剥掉</b>'
           '（导出 / 两种同步用同一套规则）；「<b>归档</b>」<b>只改状态、不动业务数据</b>；筛选默认「在建」但候选里仍含归档项目'
           '（排最后、标注「已归档」）。</div>\n')
TIP_M02 = ('  <div class="tip">本系统只<b>只读</b> i8（竞价平台是另一套、不接）；结存 / 库存单据<b>要等 i8 过账完成</b>才有完整数据；'
           'i8 抓不到时可<b>手动下载 Excel → 导入</b>（与抓取走同一套解析）；⭐ <b>抓取一律要人点</b> —— '
           '<b>本系统没有任何定时任务</b>，不会自己每天跑一次。</div>\n')
TIP_M09 = ('  <div class="tip">本页是<b>一张独立报表</b>（<b>不是</b>库存单据的第 3 张透视表）；'
           '⚠️ 「<b>安文费</b>」是那个 CBS 类目（＝自动项），<b>不是这张报表的名字</b> —— 两者别再混着叫。</div>\n')

JOBS = (
    ("m05", "<b>辅材欠款</b>（§4.5.1）", TIP_M05, ("机械欠款", "期初占位行")),
    ("m01", "<b>两把钥匙（§2.3）</b>", TIP_M01, ("四个名字", "建档路径")),
    ("m02", "<b>本系统是「i8 的只读消费方」</b>", TIP_M02, ("抓取一律要人点", "统一降级方案")),
    ("m09", "<b>本页 = 「特殊费用月报表」</b>", TIP_M09, ("自动项来源", "项目维度")),
)

#: 真机 ㉖ 的红线（默认展开的说明 > 200 字）—— 本批新增的每一段都必须远低于它
TIP_LIMIT = 160
#: ⭐ `test_acc_jc_shell` 钉着的原话（撤块时必须原样留在壳里）
PINNED = ("抓取一律要人点", "本系统没有任何定时任务")


def main() -> int:
    text = INDEX.read_text(encoding="utf-8")
    for page, marker, tip, must in JOBS:
        assert text.count(marker) == 1, f"{page} 锚点命中 {text.count(marker)} 次"
        i = text.index(marker)
        a = text.rindex("${CALIB({", 0, i)
        b = text.index("]})}", i) + len("]})}")
        blk = text[a:b]
        assert 90 < len(blk) < 2600, f"{page} 那块长度 {len(blk)} 不像"
        for m in must:
            assert m in blk, f"{page} 那块里没有 {m!r} —— 不是我要删的那一块"
        n = len(re.sub(r"\s+", "", re.sub(r"<[^>]+>", "", tip)))
        assert n <= TIP_LIMIT, f"{page} 新写的页内说明 {n} 字 > {TIP_LIMIT}（真机 ㉖ 会红）"
        text = text[:a] + tip.rstrip("\n") + text[b:]

    for phrase in PINNED:
        assert phrase in text, f"⭐ 判据钉着的那句没了：{phrase!r}"

    left = text.count("${CALIB({")
    assert left == 5, f"全站 CALIB 调用点应为 5（9 − 本批 4）⇒ 实为 {left}"
    INDEX.write_text(text, encoding="utf-8", newline="")
    print(f"✅ 批 3：m05 / m01 / m02 / m09 折叠块已撤（21 条 ⇒ 四段页内说明；"
          f"判据钉着的两句仍在 · 余 {left} 块）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
