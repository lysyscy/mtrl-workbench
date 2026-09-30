# -*- coding: utf-8 -*-
"""接线 `TAIL-35`（`m04` 的 Excel 导入 ＋ 手动行）到前端壳 —— 一次性批量替换。

用法：`cd D:\\dev\\mtrl-workbench && backend/.venv/Scripts/python.exe tools/_wire_m04_tail35.py`

⚠️ 三条纪律（同 `_wire_m07.py`）：幂等 · 每处断言唯一命中 · bytes 级并按目标文件行尾归一。
⚠️ 手动行三个动作（`plRowAdd`/`plRowEdit`/`plRowCancel`）**从原型逐字取回** —— 它们是**本地草稿层**
   （不落库），接后端后**一行不用改**；只有 `plRowSave`（落库）与导入（上传）需要改。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHELL = ROOT / "backend" / "app" / "web" / "index.html"

src = SHELL.read_bytes()
CRLF = b"\r\n" in src


def fit(text: str) -> bytes:
    b = text.encode("utf-8").replace(b"\r\n", b"\n")
    return b.replace(b"\n", b"\r\n") if CRLF else b


def sub_line(text: bytes, marker: str, new: str) -> bytes:
    m = fit(marker)
    hits = [i for i in range(len(text)) if text.startswith(m, i)]
    if len(hits) != 1:
        raise SystemExit(f"⛔ 行标记命中 {len(hits)} 次（应 1）：{marker[:70]!r}")
    i = hits[0]
    a = text.rfind(fit("\n"), 0, i) + 1
    b = text.find(fit("\n"), i)
    b = len(text) if b < 0 else b
    return text[:a] + fit(new) + text[b:]


def sub1(text: bytes, old: str, new: str) -> bytes:
    o, n = fit(old), fit(new)
    c = text.count(o)
    if c != 1:
        raise SystemExit(f"⛔ 命中 {c} 次（应 1）：{old[:70]!r}")
    return text.replace(o, n)


if fit("plImportOk:async ()=>{") in src:
    print("已是目标状态（TAIL-35 已接线）—— 无需重复执行")
    sys.exit(0)

before = len(src)
steps: list[str] = []

# ============================================================ 1 · API 客户端

src = sub1(
    src,
    "  plRematch: id => API.send('POST', `/api/m04/plans/${id}/re-match`, null),",
    """  plRematch: id => API.send('POST', `/api/m04/plans/${id}/re-match`, null),
  /* ---- MOD-04 · 手动行 ＋ 导入（`TAIL-35`） ---- */
  /* 手动行新增 / 编辑 —— 判定与落库全在后端（`plan_manual.manual_row_payload`）。 */
  m04PlanSave: body => API.post('/api/m04/plans', body),
  /* ⚠️ 导入是 **multipart/form-data**（⛔ 不是 JSON）⇒ 单独写：`FormData` ＋ **不手动设 Content-Type**
     （浏览器要自己带 boundary；手设会把 boundary 写丢 ⇒ 后端收不到文件）。 */
  m04Import: async (year_month, file) => {
    const fd = new FormData();
    fd.append('year_month', year_month);
    fd.append('file', file);
    const r = await fetch('/api/m04/import', { method: 'POST', body: fd });
    const text = await r.text();
    let data = null;
    try { data = text ? JSON.parse(text) : null; } catch (e) { data = null; }
    if (!r.ok) throw new Error((data && (data.message || data.detail)) || text || `HTTP ${r.status}`);
    return data;
  },"""
)
steps.append("API 客户端：+ m04PlanSave / m04Import")

# ============================================================ 2 · 手动行三个动作（从原型逐字取回）

src = sub_line(
    src, "plRowAdd:()=>toast(",
    " plRowAdd:()=>{ plRowEditId=PL_NEW_ID; plD=plBlank(); render();"
    "   toast('已在<b>表尾生成一行草稿</b>（尚未保存）—— 填完点该行「保存」落库、点「取消」丢弃"
    "<br>它落库后**与导入行同住一表、同样要被审查**，且**导入不会清理它**（§9.5）',5600); },"
)
steps.append("plRowAdd：恢复原型（本地草稿）")

src = sub_line(
    src, "plRowEdit:()=>toast(",
    """ plRowEdit:t=>{ const p=PLs.find(x=>x.id===t.dataset.id); if(!p) return;
   if(!p.manual){ toast('<b>编辑只对「手动行」开放</b> —— 导入行是项目端报来的<b>源数据</b>：要改请<b>重新导入</b>（它在 §4.3.3 唯一的例外口 = 该行「再次匹配」）',6400); return; }
   plRowEditId=p.id;
   plD={ym:p.ym, proj:plProjKey(p.proj), docNo:p.docNo||'', flowAmt:String(p.flowAmt), monthAmt:String(p.monthAmt),
        date:p.date||'', method:p.method||'现汇', remark:p.remark||''};
   render();
   toast(`正在<b>原地编辑</b>手动行 <b>${esc(p.id)}</b> —— 点「保存」落库、点「取消」保持原样`,5200); },"""
)
steps.append("plRowEdit：恢复原型（本地草稿）")

# ============================================================ 3 · 保存（走后端）

src = sub_line(
    src, "plRowSave:()=>toast(",
    """ plRowSave:async ()=>{ const d=plD;
   /* ⭐ 接线：**判定与落库一律后端**（`plan_manual.manual_row_payload` → `/api/m04/plans`）——
      ⛔ 前端不再复写「年月必填 / 项目必选 / 金额非负」那三道校验（那是**第二份口径**）。
      ⚠️ 校验不过 ⇒ 后端 400 ＋ 原样原因；**草稿与已填内容一律保留**（§4.3.3.1：显式报错、不清空重填）。 */
   const isNew=(plRowEditId===PL_NEW_ID);
   try{
     const r=await API.m04PlanSave({
       row_id: isNew ? '' : String(plRowEditId||''),
       row_ym: String(d.ym||''), project_id: String(d.proj==null?'':d.proj),
       doc_no: String(d.docNo||''),
       flow_amount: String(d.flowAmt==null?'':d.flowAmt),
       planned_amount: String(d.monthAmt==null?'':d.monthAmt),
       pay_date: String(d.date||''), pay_method: String(d.method||''), remark: String(d.remark||''),
     });
     plf.ym=String(d.ym||plf.ym);     /* 保存后保证看得见（切到该行年月）；⚠️「项目」筛选一律不动 */
     plRowEditId=''; plD={};
     await reloadPlans();
     toast(`${esc(r.message||'已保存')} —— 已切到 <b>${esc(plf.ym)}</b>；它<b>与导入行同样参与审查</b>（§4.3.4），合计与 KPI 随之重算`,7600);
   }catch(e){
     await reloadPlans();          /* 回后端真实状态；⚠️ **`plD` 不动** ⇒ 草稿行与已填内容仍在（§4.3.3.1） */
     toast(`<b>没能保存</b>：${esc(String((e&&e.message)||e))}<br><span class="mut sm">已填内容保留，改完再存（§4.3.3.1）</span>`,9000);
   } },"""
)
steps.append("plRowSave：走后端（判定搬家）")

# ============================================================ 4 · 导入（原型一步式弹窗 ＋ 真上传）

src = sub_line(
    src, "plImport:()=>toast(",
    """ plImport:()=>{ modal({title:'导入付款计划 Excel',reopen:()=>ACT.plImport(),body:`<div class="tip" style="margin-bottom:10px">请先选择<b>本次导入数据的月份</b>；导入后本批全部行都归入该年月（<b>按月归档</b>）。<br><b>同一月份允许存在完全相同的行，且不被覆盖</b>（重复由「重复上报」提示，不靠自动去重掩盖）。</div>
       <div class="fbar" style="border:1px solid var(--bd2);border-radius:6px;margin-bottom:10px">
         <div class="fi"><label>导入数据的年月</label>${tmBtn('plImportMonth',{scope:'plimp',val:plImportM,modes:['月']})}</div>
         <div class="fi"><label>Excel 文件</label><input class="inp" type="file" id="plImpFile" accept=".xlsx,.xls" style="padding:4px"></div>
       </div>
       <div class="tip ok" style="margin:0">导入按所选月份「<b>清该月自动行 → 重写该批</b>」（§9.5 幂等）；<b>可手改列一律保留</b>、<b>该月手动行不被触碰</b>。</div>`,
     footer:`<button class="btn" data-act="closeModal">取消</button><button class="btn pri" data-act="plImportOk">导入</button>`}); },
 /* ⭐ 接线：**真上传**（`multipart`）—— ⛔ 不再造演示行（旧「造几行演示数据」的假成功已撤）。
    原型形态 = **一步式**（弹窗选月 → 选文件 → 导入）；**没有「预览」这一步**（按原型，不发明）。 */
 plImportOk:async ()=>{ const m=plImportM; const el=document.getElementById('plImpFile');
   const f=el&&el.files&&el.files[0];
   if(!f) return toast('<b>请先选择要导入的 Excel 文件</b>',5200);
   try{ const r=await API.m04Import(m,f);
     closeModal(); plf.ym=m; await reloadPlans();
     toast(`<b>${esc(m)}</b> 导入完成：${esc(r.message||'')}`,9000);
   }catch(e){ toast(`<b>导入没能完成</b>：${esc(String((e&&e.message)||e))}<br><span class="mut sm">已选文件不合法或表头认不出时会这样报；草稿/筛选均未改动</span>`,9000); } },"""
)
steps.append("plImport / plImportOk：恢复原型一步式弹窗 ＋ 真上传")

SHELL.write_bytes(src)
print(f"完成：{before} → {len(src)} 字节（{len(src) - before:+d}）· {len(steps)} 处")
for s in steps:
    print("  ✔", s)
