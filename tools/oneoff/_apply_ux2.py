#!/usr/bin/env python
"""任务 2/3 第二批：wh/iv 成功与异常 ⇒ 弹窗；expPivot 二次确认 ＋ allow_kick。"""
from __future__ import annotations

import pathlib
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(r"D:\dev\mtrl-workbench")
BAK = ROOT / ".workbuddy" / "scratch"
CORE = ROOT / "backend" / "app" / "web" / "shell" / "core.js"
ACTS = ROOT / "backend" / "app" / "web" / "shell" / "actions.js"


def patch(p, old, new, tag, count=1):
    t = p.read_text(encoding="utf-8")
    n = t.count(old)
    if not n:
        print(f"⚠️  {p.name}: 找不到锚点 ⇒ {tag}")
        return
    shutil.copy2(p, BAK / (p.name + ".bak-ux2"))
    p.write_text(t.replace(old, new) if count == -1 else t.replace(old, new, count),
                 encoding="utf-8", newline="")
    print(f"✅ {p.name}: {tag}（{min(n, count) if count > 0 else n} 处）")


# ── wh 成功段收尾（toast ⇒ 弹窗）
patch(CORE,
  "    toast(msg + `<br><span class=\"mut sm\">⚠️ 解析条数与落库条数不一致时先怀疑幂等范围（见 ops 实测结论）</span>`,\n"
  "      pend.length ? 15000 : 7600);",
  "    fetchResultModal(`抓取结果 · 收发结存（API-02）`,\n"
  "      msg + `<br><span class=\"mut sm\">⚠️ 解析条数与落库条数不一致时先怀疑幂等范围（见 ops 实测结论）</span>`);",
  "wh 成功 ⇒ 弹窗")

# ── wh / iv 共用的异常段（两处同文 ⇒ 全部替换）
patch(CORE,
  "    toast(`<b>抓取没能完成</b>：${esc(String((e && e.message) || e))}<br>`\n"
  "      + `<span class=\"mut sm\">本系统<b>不会自动重试登录</b>（D9，避免反复顶号）—— 请确认 i8 账号后再试</span>`, 8600);",
  "    fetchResultModal(`抓取没能完成`,\n"
  "      `<b style=\"color:var(--wn)\">${esc(String((e && e.message) || e))}</b><br>`\n"
  "      + `<span class=\"mut sm\">本系统<b>不会自动重试登录</b>（D9，避免反复顶号）—— 请确认 i8 账号后再试；"
  "接口失败可走「手动导入」降级（解析同一条管线）</span>`);",
  "wh/iv 异常 ⇒ 弹窗", count=-1)

# ── iv 降级 ⇒ 弹窗
patch(CORE,
  "      return toast(`<b>抓取没能完成</b>，已<b>降级为手动导入</b>：${esc(r.message || '')}<br>`\n"
  "        + `<span class=\"mut sm\">可到「导入」入口上传 i8 导出的 Excel（解析走同一条管线）</span>`, 9000);",
  "      return fetchResultModal(`抓取没能完成 · 库存单据明细（API-03）`,\n"
  "        `已<b>降级为手动导入</b>：${esc(r.message || '')}<br>`\n"
  "        + `<span class=\"mut sm\">可到「导入」入口上传 i8 导出的 Excel（解析走同一条管线）</span>`);",
  "iv 降级 ⇒ 弹窗")

# ── iv 成功 ⇒ 弹窗
patch(CORE,
  "    toast(`已按 <b>${esc(month)}</b> 抓取库存单据明细（API-03）：<br>`\n"
  "      + `本次插入 <b>${st.inserted || 0}</b> · 更新 <b>${st.updated || 0}</b>`\n"
  "      + ` · i8 侧已删 <b>${st.deleted || 0}</b>`\n"
  "      + `${st.kept_with_adjustment ? ` · <b>保留调整单 ${st.kept_with_adjustment}</b>` : ''}`\n"
  "      + `<br><span class=\"mut sm\">调整单独立存储、不被导入覆盖（ENT-04）</span>`, 7200);",
  "    fetchResultModal(`抓取结果 · 库存单据明细（API-03）`,\n"
  "      `已按 <b>${esc(month)}</b> 抓取库存单据明细（API-03）：<br>`\n"
  "      + `本次插入 <b>${st.inserted || 0}</b> · 更新 <b>${st.updated || 0}</b>`\n"
  "      + ` · i8 侧已删 <b>${st.deleted || 0}</b>`\n"
  "      + `${st.kept_with_adjustment ? ` · <b>保留调整单 ${st.kept_with_adjustment}</b>` : ''}`\n"
  "      + `<br><span class=\"mut sm\">调整单独立存储、不被导入覆盖（ENT-04）</span>`);",
  "iv 成功 ⇒ 弹窗")

# ── expPivot：二次确认 ＋ allow_kick（照集采形态；切片外 ⇒ U1 不受影响）
t = ACTS.read_text(encoding="utf-8")
s = t.find(" expPivot:async ()=>{")
e = t.find("',6400); },", s)
assert s > 0 and e > s, "expPivot 块定位失败"
NEW = (
  " expPivot:async ()=>{\n"
  "   /* ⭐ 2026-09-21 用户口径「统一像集采台账」：这份导出的取数 = **HTTP 现导**（`spec_key='inv'`，\n"
  "      会登录 i8）⇒ 照集采形式先**二次确认**（D9），确认后才带 `allow_kick=true`。 */\n"
  "   return modal({title:'导出 · 库存单据明细表（含两张透视）· 二次确认',reopen:()=>ACT.expPivot(),\n"
  "     body:`<div class=\"tip wn\" style=\"margin-bottom:10px\"><b>⚠️ 这份导出的取数是「HTTP 现导」</b>：会登录 i8 ——\n"
  "       cookie 有效时<b>不重登、不顶号</b>；仅在会话拿不到时才需要<b>强踢</b>该账号其它在线会话（决策 D9）。若同事正在用 i8，请先择时。</div>\n"
  "       <div class=\"tip ok\" style=\"margin:0\">确认后浏览器<b>直接下载</b>成品 xlsx（两张真透视：过程资料 / 安全文明施工费）；\n"
  "       失败时弹中文原因（模板缺失 / 该月没有明细 / 缓存级对账不过），<b>不会静默</b>。</div>`,\n"
  "     footer:`<button class=\"btn\" data-act=\"closeModal\">取消</button>"
  "<button class=\"btn pri\" data-act=\"expPivotOk\">确认导出</button>`});\n"
  " },\n"
  " expPivotOk:async ()=>{\n"
  "   closeModal();\n"
  "   const url='/api/m08/inventory/export?period='+encodeURIComponent(fIvYm)+'&allow_kick=true';\n"
  "   const fn=await dlExport(url,{name:'库存单据明细表.xlsx'});\n"
  "   if(!fn) return;\n"
  "   toast('已导出「库存单据明细（含数据透视表）」：<b>工作表 1</b> = 明细（<b>列随 i8 源文件</b>，与页面列不同）；"
  "<b>工作表 2</b> = <b>「过程资料」透视</b>（按仓 × 出入库方向 × 物料性质）；<b>工作表 3</b> = "
  "<b>「安全文明施工费」透视</b>（按仓 × 金额）<br>⚠️ 这份走<b>路径②</b>（脚本直接改 i8 导出源文件、含真·透视表）："
  "<b>不套模板骨架、不认 DATA_START</b>；主表的「导出 Excel（R1）」不受影响',6400); },"
)
ACTS.write_text(t[:s] + NEW + t[e + len("',6400); },"):], encoding="utf-8", newline="")
print("✅ actions.js: expPivot ⇒ 二次确认 ＋ allow_kick（新增 expPivotOk）")
