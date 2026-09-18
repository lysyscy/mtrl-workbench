"""`TAIL-04` 壳侧接线：`zipSfjc`（收发结存「导出分仓库 zip」）由**假成功**改为**真下载**。

原实现（接线前）只在页面上报「⏳ 导出尚未落地（属 TAIL-04）…」而不产出文件。
新的做法：
- 走 `GET /api/m07/settlement/export?period=<核算年月>`（后端**模板法**生成 zip）；
- ⚠️ 失败时后端回 **JSON 200 ＋ `ok:false` ＋ 中文原因** ⇒ 壳据 `content-type` 分流：
  `application/json` ⇒ 把原因原样弹出来；否则当文件下载；
- ⛔ 前端**不自己拼文件名** —— 命名规则的主人在后端，经 `X-Export-Filename` 带出。

断言起点唯一；幂等（已接线则跳过）。
"""

from __future__ import annotations

import pathlib

ROOT = pathlib.Path(r"D:\dev\mtrl-workbench")
SHELL = ROOT / "backend" / "app" / "web" / "index.html"

src = SHELL.read_text(encoding="utf-8")
if "m07SettlementExport" in src:
    print("已接线过（幂等跳过）")
    raise SystemExit(0)

OLD = (
    " zipSfjc:()=>{ const rows=pjSort(whRows(fWhYm));\n"
    "   /* ⛔ **不做假成功**（原型这里报「已生成 .zip」却拿不到文件）：真实的成品文件写出属 `TAIL-04`\n"
    "      （方法已定案 = **模板法**：以用户手作成品 xlsx 为基底做 `zip` 字节替换），与本页接线分开做。 */\n"
    "   toast(`⏳ <b>导出尚未落地</b>（属 TAIL-04）：本页按 <b>${tmLabel(fWhYm)}</b> 应导出 `\n"
    "     + `<b>${rows.length}</b> 个分仓库 xlsx ＋ 1 个总表 = <b>${rows.length+1}</b> 个文件（zip 打包，走<b>模板法</b>）；`\n"
    "     + `方法与实测结论已就绪、只差移植。`, 8600); },"
)

NEW = """ /* ⭐ 接线（`TAIL-04`）：成品由**后端模板法**生成 —— 分仓库 xlsx ＋ 1 个总表打成**一个 zip**。
    ⚠️ 失败时后端回 **JSON 200 ＋ `ok:false` ＋ 中文原因**（模板缺失/损坏 · 该月没有明细 ·
       **缓存级对账不过**）⇒ 据 `content-type` 分流：JSON ⇒ 弹原因；否则当文件下载。
    ⛔ 前端不自己拼文件名（命名规则的主人在后端，经 `X-Export-Filename` 带出）。 */
 zipSfjc:async ()=>{
   const url='/api/m07/settlement/export?period='+encodeURIComponent(fWhYm);
   let r;
   try{ r=await fetch(url); }
   catch(e){ return toast(`<b>导出没能完成</b>：${esc(String((e&&e.message)||e))}`,8000); }
   const ct=r.headers.get('content-type')||'';
   if(ct.includes('application/json')){
     let d={}; try{ d=await r.json(); }catch(e){}
     return toast(`<b>导出没能完成</b>：${esc(d.message||'后端没给原因')}`,9600);
   }
   if(!r.ok) return toast(`<b>导出没能完成</b>：HTTP ${r.status}`,8000);
   const fn=decodeURIComponent(r.headers.get('x-export-filename')||'')||'收发结存表.zip';
   const blob=await r.blob(), a=document.createElement('a');
   a.href=URL.createObjectURL(blob); a.download=fn;
   document.body.appendChild(a); a.click(); a.remove();
   setTimeout(()=>URL.revokeObjectURL(a.href),5000);
   toast(`已导出<b>${pjSort(whRows(fWhYm)).length}</b> 个分仓库 xlsx ＋ 1 个总表（zip）；`
     + `走<b>模板法</b>（成品 = 以手作成品 xlsx 为基底）—— 金额按 <b>2 位小数对平、容差 0</b>`,7600); },"""

assert src.count(OLD) == 1, f"⛔ 锚命中 {src.count(OLD)} 次"
SHELL.write_text(src.replace(OLD, NEW, 1), encoding="utf-8")
print("✅ zipSfjc 已接线")
