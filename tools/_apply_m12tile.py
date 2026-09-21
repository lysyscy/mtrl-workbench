# -*- coding: utf-8 -*-
"""一次性施加「看板 ⑤ 差异瓦片改指库存单据」的**面**侧改动（**字节级 · 保行尾 · 先备份**）。

⚠️ 为什么落成脚本而不是用编辑器（本仓纪律 `CLAUDE.md` §7 ＋ 已踩过的坑）：
   `Path.write_text()` 在 Windows 上把 `\\n` **翻译成 `\\r\\n`** ⇒ 实测把**纯 LF** 的原型
   整篇写成 CRLF（5058 裸 LF → 5067 CRLF）。⇒ 一律 `read_bytes` / `write_bytes`，⛔ 不碰行尾。

⭐ **背景（用户 2026-09-21 裁定）**：`MOD-12` 差异登记整页已撤（2026-09-20），差异的**载体 =
   库存单据的调整单**（§5.8.3）。而看板 ⑤ 号瓦片仍写着「差异待核对 · 数据源 = `DFs`（恒空）
   · 去向 = `m12`」⇒ 它指向一个**已撤的页**、数恒 0。用户裁定：**改指库存单据**（保持 9 项）。

⚠️ 为什么动**原型**：`home` 没有模块号 ⇒ `ui_parity` 的 `U1` **不查 `V.home`**（`ui_parity.py:202`）；
   换句话讲这次原型改动**不是**被 U1 逼的，而是因为**原型是这一页的交互规格主人**
   （`app/home/domain.py` 的旧注释、`demo/原型导读.md`）⇒ 规格与实现**一起改**，否则两边分叉。

⚠️ 顺带：原型**保留** `RUNLOG`（演示数组）与 `V.m12` 切片 —— 那是**留痕**，⛔ 别顺手清
   （用户 2026-09-20 22:16 改裁：「原型不动，改为在原型与文档各加标记」）。

用法：`cd D:\\dev\\mtrl-workbench && backend/.venv/Scripts/python.exe tools/_apply_m12tile.py`
"""

from __future__ import annotations

import pathlib
import shutil
import sys
from datetime import datetime

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROTO = pathlib.Path(
    r"D:\工作\AI\PRD编写夹 - Workbuddy专用\demo\材料报表自动化工作台-交互原型.html")
SMOKE = PROTO.parent / "_smoke.js"

#: 原型 `V.home` 切片内 —— ⚠️ 与**壳** `index.html` 的 `V.home` **逐字相同**（规格 = 实现）
PROTO_PAIRS: list[tuple[str, str]] = [
    # ⑤ 的**数**：差异的载体是调整单 ⇒ 数 = 「有调整单的库存单据行数」（⛔ 不再是那个恒空的 `DFs`）
    ("  const nDf =DFs.filter(x=>x.status==='待核对').length;          /* ⑤ §5.8.3 差异状态 */",
     "  const nAdj=IVs.filter(iv=>adjOf(iv)).length;                  /* ⑤ §5.8.3 差异的**载体 = 调整单** */"),

    # 合计项跟着换名（`tN` 只是"共 N 项需处理"的计数，口径不变）
    ("  const tN=nUn+nOwn+nPl+nJc+nDf+ph.length+(fDone?0:1)+(fFail?1:0)+(pFail?1:0);",
     "  const tN=nUn+nOwn+nPl+nJc+nAdj+ph.length+(fDone?0:1)+(fFail?1:0)+(pFail?1:0);"),

    # ⑤ 瓦片：文案 ＋ 去向（`m12` 已撤 ⇒ 改 `m08`）
    ("    tile('dfPending',nDf,'wn','差异待核对',nDf,'差异状态 = 待核对 · ','m12','去差异登记'),",
     "    tile('dfPending',nAdj,'ok','差异（看调整单）',nAdj,"
     "'差异一律落在库存单据的<b>调整单</b>上（差异表由系统按调整单算） · ','m08','去库存单据'),"),
]

#: 交付面四检 —— `_smoke.js` §10f 的**独立复算**（口径变更 ⇒ 复算式跟着变）
SMOKE_PAIRS: list[tuple[str, str]] = [
    # ⚠️ 刻意**不复用**原型的 `adjOf`：这里用 `ADs` 自己找一遍（该 guard 的口径就是"各写各的、写完再对"）
    ("      dfPending: X.DFs.filter(d => d.status === '待核对').length,",
     "      dfPending: X.IVs.filter(iv => X.ADs.some(a => a.ivid === iv.id)).length,"),
]


def _backup(p: pathlib.Path) -> None:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dst = p.with_name(p.name + f".bak-{stamp}")
    shutil.copyfile(p, dst)
    print(f"  💾 备份 → {dst.name}")


def _apply(path: pathlib.Path, pairs: list[tuple[str, str]], label: str) -> int:
    """按**字节**施加替换；每条断言命中恰好 1 次（⛔ 不静默少改/多改）。幂等：已改过就跳过。"""
    data = path.read_bytes()
    assert b"\r\n" not in data, f"{path} 不是纯 LF —— 先查，别继续（会掩盖行尾漂移）"
    for i, (old, new) in enumerate(pairs, 1):
        o, nw = old.encode("utf-8"), new.encode("utf-8")
        cnt, done = data.count(o), data.count(nw)
        if cnt == 0 and done >= 1:
            print(f"  ⏭ [{label}] #{i} 已施加过（跳过）")
            continue
        if cnt != 1:
            print(f"  ⛔ [{label}] #{i}：旧文本命中 {cnt} 次（需 1）—— 未改，先核对锚点：{old[:60]!r}")
            return 1
        data = data.replace(o, nw)
        print(f"  ✅ [{label}] #{i} {old[:34].strip()}…")
    path.write_bytes(data)
    assert b"\r\n" not in path.read_bytes(), f"{path} 写回后出现 CRLF"
    return 0


def main() -> int:
    print("① 备份交付面两个文件：")
    for p in (PROTO, SMOKE):
        if not p.exists():
            print(f"  ⛔ 找不到 {p}")
            return 1
        _backup(p)
    print("② 原型 `V.home` 切片（⑤ 差异瓦片改指库存单据）：")
    if _apply(PROTO, PROTO_PAIRS, "原型"):
        return 1
    print("③ 交付面四检 `_smoke.js` §10f 的独立复算式：")
    if _apply(SMOKE, SMOKE_PAIRS, "_smoke"):
        return 1
    print("\n✅ 全部施加完毕 · 两个文件仍为纯 LF")
    return 0


if __name__ == "__main__":
    sys.exit(main())
