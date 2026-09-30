# -*- coding: utf-8 -*-
"""一次性施加「看板 ⑦⑬⑭ 接真执行记录」的**原型**侧改动（**字节级 · 保行尾 · 先备份**）。

⭐ **为什么原型也要改**（⚠️ 上一批 `_apply_m12tile.py` 里我把它写反了，这里更正）：
   `ui_parity` 的 `U1` **确实**逐行比 `V.home` —— 源码里那句
   `continue  # home 之类没有模块号：本检查不覆盖` 只作用于 **`U4`**（"WIRED 的页有没有调 `/api/mNN`"），
   `U1` 的循环是**遍历原型所有 `V.*`**（`for key, plines in p_views.items()`）⇒ `home` 在里面。
   ⇒ 壳的 `V.home` 与原型**必须逐行一致**，否则 `ui_parity` 当场红一片（实测：72 行漂移）。

⭐ **做法：把"数据从哪来"抽成两边**同名不同体**的 `homeCounts()`**（定义在 `V.home` 切片**之外**，
   `U1` 只比切片 ⇒ 不受影响）：
   · 原型 `homeCounts()` = **演示版后端**：用 `RUNLOG` 现算（`_smoke §10f` 那条"⑬⑭ 必须真的来自
     运行记录"的反面对照仍成立 —— 它改 `RUNLOG` 一条，数就跟着变）。
   · 壳 `homeCounts()` = **后端算好的那一份**（`GET /api/home/run-counts`，见 `core.js`）。
   ⇒ `V.home` 里那 5 行**逐字相同**，两个文件只在 `homeCounts()` 的定义处不同。

⚠️ **原型保留 `RUNLOG`（演示数组）与 `V.m12` 切片** —— 那是**留痕**，⛔ 别顺手清
   （用户 2026-09-20 22:16 改裁：「原型不动，改为在原型与文档各加标记」）。

⚠️ **唯一保留的一处行差**：`V.home` 开头那句 tip —— 原型必须说「所有数据均为虚构模拟值」，
   壳里那句必须说真话。⇒ 已登记进 `tools/ui_parity_expected.txt`（**只准变短**）。

用法：`cd D:\\dev\\mtrl-workbench && backend/.venv/Scripts/python.exe tools/_apply_home_wired.py`
"""

from __future__ import annotations

import pathlib
import shutil
import sys
from datetime import datetime

ROOT = pathlib.Path(__file__).resolve().parents[2]
PROTO = pathlib.Path(
    r"D:\工作\AI\PRD编写夹 - Workbuddy专用\demo\材料报表自动化工作台-交互原型.html")

#: 两边 `V.home` 切片内**逐字相同**的一段 —— ⑦⑬⑭ 的取数与三格瓦片出口
SHARED_OLD = """  /* ⑦⑬⑭ 取自**运行记录**（§3.1.3 抓取 / §4.6 打印）；月份由 `at` 派生、不另存字段（防副本）。 */
  const rf=RUNLOG.filter(r=>r.kind==='抓取'), rp=RUNLOG.filter(r=>r.kind==='打印');
  const fDone=rf.some(r=>r.at.slice(0,7)===bjMonth()&&r.result==='成功');   /* 本月有没有**成功**的抓取 */
  const fFail=[...rf].reverse().find(r=>r.result==='失败')||null;           /* 最近一次抓取失败 */
  const pFail=[...rp].reverse().find(r=>r.result==='失败')||null;           /* 打印投递失败 */"""

SHARED_NEW = """  /* ⑦⑬⑭ 取自**执行记录**（§3.1.3 / §4.6）—— 数一律从 `homeCounts()` 来：见它的定义处。 */
  const H=homeCounts(), hErr=!!H.err, HC=H.counts, HL=H.latest;
  const fDone=!hErr&&HC.fetchDue===0;                                       /* 本月有没有**成功**的抓取 */
  const fFail=hErr?null:HL.fetchFail;                                       /* 最近一次抓取失败 */
  const pFail=hErr?null:HL.printFail;                                       /* 打印投递失败 */"""

#: ⚠️ 交付面四检的 `_links` 会把反引号里的 `core.js` 当成**交付面内的文件引用** ⇒ 断链
#:    （实测：原型里唯一一处「引用了面外文件」）。改成不带反引号的措辞 —— 行数不变。
LINK_FIX: list[tuple[str, str]] = [
    ("   壳里有**同名同形**的另一份（`core.js`，取后端 `/api/home/run-counts`）——",
     "   壳里有**同名同形**的另一份（前端壳的接线层，取后端 `/api/home/run-counts`）——"),
]

#: 原型 `homeCounts()` —— 插在 `V.home` **切片之外**（紧跟演示记录数组之后）
PROTO_HELPER_ANCHOR = """/* =====================================================================
   3. 看板
   ===================================================================== */
V.home=()=>{"""

PROTO_HELPER = """/* ⭐⭐ 看板 ⑦⑬⑭ 的**取数接口**（`V.home` 只认这一个）。
   ⚠️ 本原型这一份 = **演示版后端**：用上面那份 `RUNLOG` 现算 ⇒ `_smoke §10f` 的
      "⑬⑭ 必须真的来自运行记录"反面对照仍成立（改一条记录，数就跟着变）。
   壳里有**同名同形**的另一份（`core.js`，取后端 `/api/home/run-counts`）——
   两份都定义在 `V.home` 切片**之外**，所以 `ui_parity` 的逐行比对不受影响。 */
function homeCounts(){
  const rf=RUNLOG.filter(r=>r.kind==='抓取'), rp=RUNLOG.filter(r=>r.kind==='打印');
  const fDone=rf.some(r=>r.at.slice(0,7)===bjMonth()&&r.result==='成功');
  const fFail=[...rf].reverse().find(r=>r.result==='失败')||null;
  const pFail=[...rp].reverse().find(r=>r.result==='失败')||null;
  return { counts:{ fetchDue:fDone?0:1, fetchFail:fFail?1:0, printFail:pFail?1:0 },
           latest:{ fetchFail:fFail, printFail:pFail }, err:'' };
}

/* =====================================================================
   3. 看板
   ===================================================================== */
V.home=()=>{"""

#: 三格瓦片出口 ＋ 内容（与壳逐字相同）：先把 `tile(` 换成带"取不到就如实说"的 `runTile`
RUN_TILE_BLOCK_ANCHOR = "  const todoTiles=["

RUN_TILE_BLOCK = """  /* ⚠️ ⑦⑬⑭ 三格**依赖取数**：拿不到就**如实说**（显「—」＋原因），
     ⛔ 不拿 0 冒充"没有待办"（铁律 4：「没数据就留空 / 标待接通，不写 0 冒充」）。 */
  const runTile=(k,n,cls,t,v,s,pg,tx)=>hErr
    ? tile(k,0,'wn',t,'—','<span class="dg">⚠️ 执行记录没取到（这三项要它）</span> · ',pg,tx)
    : tile(k,n,cls,t,v,s,pg,tx);
  const todoTiles=["""

RUN_CALLS: list[tuple[str, str]] = [
    ("    tile('fetchDue',fDone?0:1,", "    runTile('fetchDue',fDone?0:1,"),
    ("    tile('fetchFail',fFail?1:0,", "    runTile('fetchFail',fFail?1:0,"),
    ("    tile('printFail',pFail?1:0,", "    runTile('printFail',pFail?1:0,"),
]


def _repair(path: pathlib.Path) -> int:
    """⓪ 体检：**每段只许有一份**（⛔ 不是"自动修复"—— 复现过两次，自动改只会越改越乱）。

    ⚠️ 复现过的坑（两次都真踩到）：
       ① `_apply` 的"已施加过"判定 = `旧文本命中 0 次`，而本脚本两处替换的**新文本结尾就是旧文本**
          ⇒ 二次运行又插一份（`const runTile` 重复声明 = **JS 语法错** ⇒ `_smoke` 整支挂掉，
          退出码 1、一行输出都没有 —— 最难查的一种"红"）。
       ② `grep -c` **只数行不数处** ⇒ 三份挤在同一行时看着像 1 份。
    ⇒ 现在是**体检**：多一份就**当场红**，⛔ 不猜着改（自动改 = 越改越乱，两次都栽在这）。
    """
    d = path.read_bytes()
    bad = 0
    # ⚠️ 用**稳定短锚**，⛔ 别拿整段去数：`PROTO_HELPER` 里那句 `core.js` 已被 `LINK_FIX` 改过
    #    （拿整段比 = 拿"改前的文本"去数"改后的文件" ⇒ 恒 0 份 ⇒ 假红）。
    for unit, label in (
        ("function homeCounts(){\n  const rf=RUNLOG.filter(", "helper"),
        ("const runTile=(k,n,cls,t,v,s,pg,tx)=>hErr", "runTile 块"),
        ("\n  const todoTiles=[", "todoTiles 起始行"),
        ("V.home=()=>{\n  const d=debts();", "V.home 开头"),
    ):
        n = d.count(unit.encode("utf-8"))
        if n != 1:
            print(f"  ⛔ {label} 在原型里有 {n} 处（需 1）—— 见 `_repair` 的说明，别自动改")
            bad = 1
    if not bad:
        print("  ✅ 各段均只有一份")
    return bad


def _apply(path: pathlib.Path, pairs: list[tuple[str, str]], label: str) -> int:
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
        print(f"  ✅ [{label}] #{i} {old.splitlines()[0][:40].strip()}…")
    path.write_bytes(data)
    assert b"\r\n" not in path.read_bytes(), f"{path} 写回后出现 CRLF"
    return 0


def main() -> int:
    if not PROTO.exists():
        print(f"⛔ 找不到原型：{PROTO}")
        return 1
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dst = PROTO.with_name(PROTO.name + f".bak-{stamp}")
    shutil.copyfile(PROTO, dst)
    print(f"💾 备份 → {dst.name}\n")
    print("⓪ 体检：每段只许一份（⛔ 不自动改）：")
    if _repair(PROTO):
        return 1
    print("① 原型 `V.home` 切片内（与壳逐字相同）：")
    if _apply(PROTO, [(SHARED_OLD, SHARED_NEW)], "共享段"):
        return 1
    print("② 原型 `V.home` 切片内（三格瓦片出口 ＋ 调用改 `runTile`）：")
    # ⚠️ 这一对的**新文本结尾也是它的锚点**（`RUN_TILE_BLOCK` 结尾 = `const todoTiles=[`）
    #    ⇒ `_apply` 的"已施加过"判定**不成立**（锚点仍命中 1 次）⇒ 必须在这里**显式**挡一道。
    if b"const runTile=(k,n,cls,t,v,s,pg,tx)=>hErr" in PROTO.read_bytes():
        print("  ⏭ [出口] 已施加过（跳过）")
    elif _apply(PROTO, [(RUN_TILE_BLOCK_ANCHOR, RUN_TILE_BLOCK)], "出口"):
        return 1
    if _apply(PROTO, RUN_CALLS, "调用"):
        return 1
    print("③ 原型 `homeCounts()`（切片**之外** · 演示版后端）：")
    if b"function homeCounts(){" in PROTO.read_bytes():
        print("  ⏭ [helper] 已施加过（跳过）")
    elif _apply(PROTO, [(PROTO_HELPER_ANCHOR, PROTO_HELPER)], "helper"):
        return 1
    print("④ 修掉 `_links` 的断链（反引号里的面外文件名）：")
    if _apply(PROTO, LINK_FIX, "断链"):
        return 1
    print("\n✅ 全部施加完毕 · 原型仍为纯 LF")
    return 0


if __name__ == "__main__":
    sys.exit(main())
