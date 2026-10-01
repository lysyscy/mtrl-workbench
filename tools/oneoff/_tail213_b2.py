"""`TAIL-213` **甲** · 批 2 = 四个小页撤块（`m07` / `m11` / `m13` / `m14` · 共 9 条 / 441 字）（2026-10-01）。

逐条去向（先读过原文再定的）：
  `m07` 收发结存（2 条）：「导出形态」**页内已有一模一样的 tip**（交付形态 = N 个分仓库 xlsx ＋ 总表 = zip、
        2 位小数对平）⇒ **删**；「认项目只靠仓库列 ⇒ 陌生仓库会自动建档 / 扶正」⇒ **留**（页内一小段）。
  `m11` 库存单据（3 条）：「本页 = 对账主工具」·「仓库名 ＋ 全名都在」（复述 §3.5 ⇒ 删）；
        「调整单打在单据行上 / 不被导出覆盖 / 差异的修正只改库存单据」**页内已有 tip（两条）**⇒ **删** ⇒ 本页**无需新增**。
  `m13` 导出与删除（2 条）：「导出导的是当前筛选那几行 ＋ 文件名」·「删除前先列影响、删完留痕可查 / 规则类不留痕」
        ⇒ **压成页内一小段**（那是"会做错的后果"，不是复述）。
  `m14` 规则配置（2 条）：「剔除规则 4 类 ＋ 标记保留、可筛选、不销毁数据」·「分类只有三类、手改不被覆盖」
        ⇒ **页内已有等价 tip**（「分类只有三类（机械 / 集采 / 辅材）…手改后重新抓取导入，分类不被覆盖」）⇒ **删**。
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
INDEX = ROOT / "backend" / "app" / "web" / "index.html"

TIP_M07 = ('  <div class="tip">认项目只靠<b>「仓库」列</b>（本表没有全名列）—— '
           '表里出现档案里没有的名字就是「<b>陌生仓库</b>」，系统会自动建档 / 扶正。</div>\n')
TIP_M13 = ('  <div class="tip"><b>导出</b>导的是你当前筛选看到的那几行（含顺序），文件名带<b>日期 ＋ 页名</b>；'
           '<b>删除</b>前系统会先列出<b>会影响什么</b> —— 删完核心单据<b>留痕可查</b>，规则类配置<b>直接删掉、不留痕</b>。</div>\n')

#: (块号, 该块**第一条**里的唯一子串, 替换成什么, 该块里必须还能找到的记号)
JOBS = (
    ("m07", "<b>认项目只靠「仓库」列</b>", TIP_M07, ("分仓库 xlsx", "对平")),
    ("m11", "<b>本页 = 对账主工具</b>", "", ("调整单", "差异的修正只改库存单据")),
    ("m13", "<b>导出</b>在每个列表页上", TIP_M13, ("删除", "留痕可查")),
    ("m14", "<b>剔除规则 4 类</b>", "", ("分类规则", "只有三类")),
)


def main() -> int:
    text = INDEX.read_text(encoding="utf-8")
    for page, marker, repl, must in JOBS:
        assert text.count(marker) == 1, f"{page} 的定位锚点命中 {text.count(marker)} 次（要 1）"
        i = text.index(marker)
        a = text.rindex("${CALIB({", 0, i)
        b = text.index("]})}", i) + len("]})}")
        blk = text[a:b]
        assert 90 < len(blk) < 2600, f"{page} 那一块长度 {len(blk)} 不像（锚点选错了？）"
        for m in must:
            assert m in blk, f"{page} 那块里没有 {m!r} —— 不是我要删的那一块"
        text = text[:a] + repl.rstrip("\n") + text[b:]

    # ⚠️ 起点数 = **13**（原来的 14 块里 `m03` 已在批 1 撤掉）⇒ 13 − 本批 4 = **9**
    assert text.count("${CALIB({") == 9, \
        f"全站 CALIB 调用点应为 9（13 − 本批 4）⇒ 实为 {text.count('${CALIB({')}"
    INDEX.write_text(text, encoding="utf-8", newline="")
    print("✅ 批 2：m07 / m11 / m13 / m14 折叠块已撤（9 条 ⇒ 页内 2 小段，另两页页内本就有）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
