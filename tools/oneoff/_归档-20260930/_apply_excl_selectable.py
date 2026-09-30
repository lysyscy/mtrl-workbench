# -*- coding: utf-8 -*-
"""一次性施加「剔除行可勾选 ＋ 超付标记」的改动（**字节级 · 保行尾**）。

⚠️ 为什么落成脚本而不是用编辑器：本仓纪律（`MEMORY.md` §十七）「行尾：工作区 CRLF、仓库存 LF」
   —— 而 `Path.write_text()` 在 Windows 上会把 `\\n` **翻译成 `\\r\\n`**
   ⇒ 本次实测踩到：原型（纯 LF）被整篇写成 CRLF（5058 裸 LF → 5067 CRLF）。
   ⇒ 一律 `read_bytes` / `write_bytes`，⛔ 不碰行尾。
⚠️ 壳的 `V.m03` 切片与**面**的原型**必须同句同长度**（`ui_parity` 的 `U1` 逐行比对）
   ⇒ 同一份替换表同时打到两边，逐条断言命中 **恰好 1 次**。

用法：`cd D:\\dev\\mtrl-workbench && backend/.venv/Scripts/python.exe tools/_apply_excl_selectable.py`
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SHELL_INDEX = ROOT / "backend" / "app" / "web" / "index.html"
SHELL_ACTIONS = ROOT / "backend" / "app" / "web" / "shell" / "actions.js"
SHELL_CORE = ROOT / "backend" / "app" / "web" / "shell" / "core.js"
PROTO = pathlib.Path(
    r"D:\工作\AI\PRD编写夹 - Workbuddy专用\demo\材料报表自动化工作台-交互原型.html")

#: 两边**逐字相同**的改动（壳的 V.m03 ⇄ 原型同名切片）
BOTH: list[tuple[str, str]] = [
    # ① 勾选框：钉死在「付款候选」上 ⇒ 剔除行永远勾不上 ⇒ 「恢复剔除」（要求必须勾选）走不通
    ("${ntPayCand(n)?'':'disabled'}",
     "${ntSelectable(n)?'':'disabled'}"),

    # ② 汇总条：两项金额只算**能付款**的那些行（标签本来就写「已勾选审批金额 / 本次应付」）
    ("  const pkA=N2(pk.reduce((a,n)=>a+n.approve,0)), pkP=N2(pk.reduce((a,n)=>a+payEff(n),0));",
     "  const pkPay=pk.filter(ntPayCand), pkA=N2(pkPay.reduce((a,n)=>a+n.approve,0)),"
     " pkP=N2(pkPay.reduce((a,n)=>a+payEff(n),0));"),

    # ③ 汇总条「已勾选」那格：把「有几条不进付款批次」明说出来（⛔ 不让人以为整批都要付）
    ('    <div class="m"><span class="k">已勾选</span><span class="v">${pk.length} 行</span></div>',
     '    <div class="m"><span class="k">已勾选</span><span class="v">${pk.length} 行</span>'
     '${pk.length>pkPay.length?` <span class="tag t-wn" title="选中的行里有剔除行 / i8 撤单行 —— '
     '它们不进付款批次（付款闸只收付款候选）；能被勾选是为了另一件事：「恢复剔除」。'
     '下面两项金额只算能付款的那些行。">其中 ${pk.length-pkPay.length} 条不进付款批次</span>`:""}'
     '</div>'),

    # ④ 「已付金额」那格挂「超付」标记（`P4` §4.4.6）。判定来自后端 `n.over`，⛔ 壳不自算
    ('      <td class="num">${p?M(p):\'<span class="mut">0.00</span>\'}</td>',
     '      <td class="num">${p?M(p):\'<span class="mut">0.00</span>\'}'
     '${n.over?` <span class="tag t-dg" title="超付（§4.4.6）：已付金额 ${M(p)} 大于审批金额 '
     '${M(n.approve)} —— NC 侧确实付了，是既成事实 ⇒ 流水照记、统计照实不封顶；'
     '系统不改写、不冲销，只在此提醒。⚠️ 与「付款动作禁止超付」（§4.4.4）不冲突：'
     '那条约束的是动作。">超付</span>`:""}</td>'),

    # ⑤ 口径说明：把「剔除行为什么可勾」讲清楚（原文只说"恢复剔除必须勾选"，没说能不能勾）
    ('勾选行里混有规则剔除时，提示会分开报「恢复了 N 条 / 另有 M 条是规则命中、不恢复」。</li>',
     '勾选行里混有规则剔除时，提示会分开报「恢复了 N 条 / 另有 M 条是规则命中、不恢复」。'
     '<b>剔除行本身是可以勾选的</b>（2026-09-21 修）：勾选不等于能付款 —— '
     '勾选集服务<b>「批量付款」与「恢复剔除」两件事</b>，剔除行<b>进不了付款批次</b>'
     '（批量付款那一步会自动排除并说明原因），但<b>必须能勾</b>，'
     '否则「恢复剔除」这条路根本走不通。规则命中的剔除行<b>也能勾</b> —— '
     '勾了会被明确告知"请去改规则配置"，而不是让你对着一个点不动的框猜。</li>'),

    # ⑥ 全选框回显：必须与 `pickAll` 走**同一个出口**（否则全选框永久卡在半选态）
    ("  const vis=ntHit(fNt).filter(ntPayCand).map(n=>n.id), hit=vis.filter(i=>pickSet.has(i)).length;",
     "  const vis=ntHit(fNt).filter(ntSelectable).map(n=>n.id), hit=vis.filter(i=>pickSet.has(i)).length;"),
]

#: 壳**接线层**独有（原型没有这一层）—— `actions.js`
ACTIONS_ONLY: list[tuple[str, str]] = [
    # 全选：与勾选框同一出口
    ("pickAll:t=>{ const ids=ntHit(fNt).filter(ntPayCand).map(n=>n.id);",
     "pickAll:t=>{ const ids=ntHit(fNt).filter(ntSelectable).map(n=>n.id);"),

    # 批量付款的「自动排除」提示：原文**写死「i8 已撤单」**，而剔除行现在也能被勾选 ⇒ 会撒谎
    ('const body=`${drop.length?`<div class="tip wn" style="margin-bottom:10px"><b>⚠️ 已自动排除 '
     '${drop.length} 条「i8 已撤单」的通知书</b>（${esc(drop.map(n=>n.code).join(\'、\'))}）—— '
     '它们的单据在 <b>i8 侧已被删除</b>，<b>不该再产生付款</b>；请先<b>撤销已付 / 解绑关联</b>'
     '（§4.2.7）。</div>`:\'\'}',
     'const whyOf=n=>ntVoid(n)?\'i8 已撤单\':\'已剔除\';\n'
     '   const body=`${drop.length?`<div class="tip wn" style="margin-bottom:10px"><b>⚠️ 已自动排除 '
     '${drop.length} 条不可付款的记录</b>（${esc(drop.map(n=>n.code+\'（\'+whyOf(n)+\'）\').join(\'、\'))}）'
     '—— <b>剔除行</b>按 §4.2.2 不进统计；<b>i8 已撤单行</b>的单据在 i8 侧已被删除。'
     '两者都<b>不该产生付款</b>；请先<b>恢复剔除 / 撤销已付 / 解绑关联</b>。</div>`:\'\'}'),
]

#: 壳接线层独有 —— `core.js`（`adaptNotice` 在这里，⛔ 不在 `actions.js`）
CORE_ONLY: list[tuple[str, str]] = [
    # 超付标记的**取数**：后端判定 → 壳字段（判定在后端，⛔ 壳不自算）
    ("    hasFlow: !!x.has_effective_flow, oid: x.ownership_id,",
     "    hasFlow: !!x.has_effective_flow, oid: x.ownership_id,\n"
     "    /* ⭐ `P4` 超付（§4.4.6）：**判定在后端**（`NoticeRow.is_overpaid`）—— 壳只拿来渲染 */\n"
     "    over: !!x.is_overpaid,"),
]

#: 壳侧**新增**的 `ntSelectable`（同步到原型，⛔ 原型不定义它就跑不起来）
BLOCK_START = "const ntPayCand=n=>ntLive(n)&&!ntVoid(n);"
BLOCK_END = "const ntSelectable=n=>ntPayCand(n)||!!n.excl;"


def _apply(path: pathlib.Path, pairs: list[tuple[str, str]], label: str) -> int:
    """按**字节**施加替换；每条断言命中恰好 1 次（⛔ 不静默少改/多改）。"""
    data = path.read_bytes()
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
        print(f"  ✅ [{label}] #{i} {old[:38].strip()}…")
    path.write_bytes(data)
    return 0


def _mirror_helper() -> int:
    """把壳里 `ntPayCand` + `ntSelectable` 那一段**逐字**同步进原型。"""
    st = SHELL_INDEX.read_bytes()
    i = st.index(BLOCK_START.encode())
    j = st.index(BLOCK_END.encode()) + len(BLOCK_END.encode())
    block = st[i:j]
    pt = PROTO.read_bytes()
    if BLOCK_END.encode() in pt:
        print("  ✅ [原型] ntSelectable 已在（跳过）")
        return 0
    assert pt.count(BLOCK_START.encode()) == 1, pt.count(BLOCK_START.encode())
    PROTO.write_bytes(pt.replace(BLOCK_START.encode(), block))
    print("  ✅ [原型] 同步 ntSelectable 出口")
    return 0


def main() -> int:
    print("① 同步 `ntSelectable` 出口到原型：")
    if _mirror_helper():
        return 1
    print("② 壳 ⇄ 原型**同句**改动（V.m03 切片内）：")
    if _apply(SHELL_INDEX, BOTH, "壳"): return 1
    if _apply(PROTO, BOTH, "原型"): return 1
    print("③ 壳**接线层**独有改动（actions.js / core.js）：")
    if _apply(SHELL_ACTIONS, ACTIONS_ONLY, "壳:actions"): return 1
    if _apply(SHELL_CORE, CORE_ONLY, "壳:core"): return 1
    for p in (SHELL_INDEX, SHELL_ACTIONS, SHELL_CORE, PROTO):
        b = p.read_bytes()
        assert b.count(b"\r\n") == 0, f"{p} 行尾被改了（出现 CRLF）"
    print("\n✅ 全部施加完毕 · 三个文件仍为纯 LF")
    return 0


if __name__ == "__main__":
    sys.exit(main())
