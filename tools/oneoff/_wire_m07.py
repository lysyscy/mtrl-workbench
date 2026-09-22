# -*- coding: utf-8 -*-
"""接线 `MOD-07`（收发结存与活动大表）到前端壳 —— **一次性批量替换脚本**。

用法：`cd D:\\dev\\mtrl-workbench && backend/.venv/Scripts/python.exe tools/_wire_m07.py`

⚠️ 三条纪律（本仓踩过，见 memory §十七）：
1. **幂等**：若壳已是目标状态 ⇒ 直接退出 0（防「一条命令被跑两次」把第二遍误读成失败）。
2. **每处都断言**：单行替换要求「命中恰好 1 次」；区间替换要求「起点唯一 ＋ 终点在起点之后 ＋ 区间不过大」。
3. **bytes 级**：按目标文件的实际行尾归一（本仓源码行尾不统一）。

⚠️ 脚本自己也会出错 ⇒ 报错时先怀疑脚本，再看实现。
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


def sub1(text: bytes, old: str, new: str) -> bytes:
    """单处替换：`old` 必须**命中恰好一次**。"""
    o, n = fit(old), fit(new)
    c = text.count(o)
    if c != 1:
        raise SystemExit(f"⛔ 命中 {c} 次（应 1）：{old[:70]!r}")
    return text.replace(o, n)


def sub_line(text: bytes, marker: str, new: str) -> bytes:
    """**整行**替换：含 `marker` 的行必须唯一。"""
    m = fit(marker)
    n_line = fit("\n")
    hits = [i for i in range(len(text)) if text.startswith(m, i)]
    if len(hits) != 1:
        raise SystemExit(f"⛔ 行标记命中 {len(hits)} 次（应 1）：{marker[:70]!r}")
    i = hits[0]
    a = text.rfind(n_line, 0, i) + len(n_line)
    b = text.find(n_line, i)
    b = len(text) if b < 0 else b
    return text[:a] + fit(new) + text[b:]


def sub_block(text: bytes, start: str, end: str, limit: int, new: str) -> bytes:
    """区间替换：`start` 唯一 ＋ `end` 在其后 ＋ 区间 < limit。"""
    s, e = fit(start), fit(end)
    i = text.find(s)
    if i < 0:
        raise SystemExit(f"⛔ 起点找不到：{start[:70]!r}")
    if text.find(s, i + 1) >= 0:
        raise SystemExit(f"⛔ 起点不唯一：{start[:70]!r}")
    j = text.find(e, i)
    if j <= i:
        raise SystemExit(f"⛔ 终点不在起点之后：{end[:70]!r}")
    j += len(e)
    if j - i >= limit:
        raise SystemExit(f"⛔ 区间 {j - i} 字节 ≥ {limit} —— 锚可能跑偏")
    return text[:i] + fit(new) + text[j:]


# ============================================================ 幂等闸

if fit("const WHM = {") not in src and fit("let WHM = {};") in src:
    print("已是目标状态（演示块已删、m07 已接线）—— 无需重复执行")
    sys.exit(0)

before = len(src)
log: list[str] = []


def step(label: str) -> None:
    global src
    log.append(label)
    print(f"  ✔ {label}")


# ============================================================ 1 · 演示数据块 → 空容器

src = sub_block(
    src, "const WHM = {", "\nconst whRows = ym => WHM[ym] || [];", 6000,
    """let WHM = {};   /* ⭐ 已接后端：由 `reloadM07()` 从 `/api/m07/settlement` **原地填充**
   （演示块 3 个月已删 —— 原先它是 `2026-08/07/06` 的模拟分仓库结存）。
   ⚠️ 对象身份不变：`whRows(ym)` 与 `V.m07` 都按**当前核算年月**取数（`fWhYm`）。 */
const whRows = ym => WHM[ym] || [];"""
)
step("WHM 演示块 → 空容器")

src = sub_block(
    src, "const EXTM = {};", "const EXTRACT = EXTM['2026-08'];", 3000,
    """let EXTM = {};   /* ⭐ 已接后端：由 `reloadM07()` 从 `/api/m07/extract` 转形填充
   （演示块 3 个月 ＋ 已失效的 `EXTRACT` 别名一并删除；取数口径唯一出口 = 后端 `extract`）。 */"""
)
step("EXTM 演示块 → 空容器")

src = sub_block(
    src, "const BIGVAL = {};",
    "'山西长治焦化升级改造项目仓库':['2023-11',560000.00,8162782.00,4200000.00,0,'']\n};", 4000,
    """let BIGVAL = {};   /* ⭐ 已接后端：由 `reloadM07()` 从 `/api/m07/big` 的 `manual` 转形填充
   （演示块 3 个月已删；⚠️ **全量月份**都要填 —— 「上次值带入」`OPEN-05` 要向更早月份取最近一次录入值）。 */
"""
)
step("BIGVAL 演示块 → 空容器")

src = sub_line(
    src, "let BIGSET = bigCands();",
    "let BIGSET = [];   /* ⭐ 已接后端：由 `reloadM07()` 从 `/api/m07/big` 的 `selected` 原地填充"
    "（行序 = 大表自己的顺序；未选题时后端给「全部候选」，与原型同款） */"
)
step("BIGSET → 后端填充")

# ============================================================ 2 · 切片内唯一必要改动（1 处，已登记 ui_parity 漂移）

src = sub_line(
    src, '<b>已验收基线：</b>2026-08 基准',
    '    <div class="bd"><div class="tip ok" style="margin:0"><b>交付形态：</b>'
    '<b>${rows.length}</b> 个分仓库 xlsx ＋ 1 个总表 = <b>${rows.length + 1}</b> 个文件打包 zip；'
    '金额按 2 位小数对平、<b>容差 0</b>。</div></div>'
)
step("V.m07 文案：不再引用演示基线 `WHM['2026-08']`（切片内唯一必要改动）")

# ============================================================ 3 · 主材累计（取数口未接入 ⇒ 显「—」）

src = sub_line(
    src, "const bigMatCum = wh =>",
    "/* ⚠️ 「主材累计（含税）」的取数口**集采台账属 M5**：未接入时给 `null`（页面显「—」），"
    "⛔ 不写 0 冒充「确实没有」（`TAIL-25`；口径 = 后端 `mat_available`）。 */\n"
    "const bigMatCum = wh => MAT_OK ? N2(JCs.filter(j => j.tag === '纳入台账' && j.proj === wh)"
    ".reduce((a, j) => a + jcSettle(j), 0)) : null;"
)
step("bigMatCum：取数口未接入 ⇒ null（显「—」）")

# ============================================================ 4 · `M()` 认 `null` ⇒ 「—」

src = sub_line(
    src, "const M=n=>{",
    "/* ⚠️ `null` / `undefined` ⇒ 「—」（**不可得 ≠ 0** —— 与后端口径一致：大表的「主材累计」"
    "取数口未接入时给 null，若按 `Number(null)||0` 会显示「0.00」= 冒充「确实没有」）。\n"
    "   ⭐ 对**数字入参**行为**完全不变**（`M(0)`→`0.00` · `M(-1.5)`→`-1.50` · `M(1234.5)`→`1,234.50`）。 */\n"
    "const M=n=>{if(n==null) return '—'; const v=r2(Number(n)||0); const s=Math.abs(v).toFixed(2); "
    "return (v<0?'-':'')+s.replace(/\\B(?=(\\d{3})+(?!\\d))/g,',');};"
)
step("M()：null ⇒ 「—」（数字入参行为不变）")

# ============================================================ 5 · API 客户端 + 适配层 + reload

src = sub1(
    src,
    "  /* ---- MOD-04 付款计划（⚠️ 后端这几个端点收 **query 参数**，不是 JSON body ⇒ 照它调用） ---- */",
    """  /* ---- MOD-07 收发结存与活动大表（⚠️ 金额后端出**字符串** ⇒ 适配层过 `N0()`） ---- */
  m07Settlement: ym => API.get(`/api/m07/settlement?period=${encodeURIComponent(ym || '')}`),
  m07Extract: () => API.get('/api/m07/extract'),
  m07Big: () => API.get('/api/m07/big'),
  m07BigCell: body => API.post('/api/m07/big/cell', body),
  m07BigSelection: selected => API.post('/api/m07/big/selection', { selected }),
  /* ⭐ 抓取：**失败也要看回执**（降级说明在 `message` 里）⇒ 不 throw，由调用方判 `ok`。 */
  m07Fetch: async month => {
    const r = await fetch('/api/m07/fetch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ month, confirm: true }),
    });
    const body = await r.json().catch(() => ({}));
    return r.ok ? { ok: true, ...body } : { ok: false, ...body };
  },

  /* ---- MOD-04 付款计划（⚠️ 后端这几个端点收 **query 参数**，不是 JSON body ⇒ 照它调用） ---- */"""
)
step("API 客户端：+ 5 个 m07 端点")

src = sub1(
    src,
    "/* 机械 6 列（**旁路表**的手录值）—— ⚠️ 不 `render()`：由 `boot()` 后面的 `reloadM05()` 统一渲染。 */",
    """/* ============ MOD-07 收发结存与活动大表（前端壳接线 · `TAIL-27`）============
   ⚠️ 后端金额出**字符串**（`numeric(18,2)` 精度保护）⇒ 这里**一律过 `N0()`**：
      不过的话壳里的求和会变成**字符串拼接**（`'100.00' + '1.00'`），而且**不报错**。 */
let MAT_OK = false;            /* 「主材累计（含税）」取数口是否已接入（后端 `mat_available`） */
/* 手填 6 列的 key 与格式 —— ⚠️ **顺序与列型的主人是后端**（`big_domain.BIG_MANUAL`），
   由 `reloadM07()` 按 `manual_keys` / `manual_fmts` 覆盖；这里只是**取数前的兜底**。 */
const BIG_MKEYS = ['open_ym', 'mech_est', 'contract', 'output_cum', 'oil', 'note'];
let BIG_MFMTS = ['ym', 'money', 'money', 'money', 'money', 'text'];

/* 手填值：后端 `{月:{仓库:{key:值}}}` → 原型 `BIGVAL[月][仓库] = [6 个值]`（与 `BIGCOLS` 同序）。
   ⭐ 哪几列是金额**由后端 `manual_fmts` 决定**（⛔ 前端不硬编码列序 / 列型）；
      金额转数字（否则手填列的合计 `typeof v === 'number'` 判假 ⇒ **恒 0**）；
      `开工时间 / 备注` 保持字符串；`null` 保持 `null`（= 未录入，交给「带入」逻辑）。 */
function adaptManual(manual, keys, fmts) {
  const out = {};
  const isMoney = i => String((fmts || BIG_MFMTS)[i] || '') === 'money';
  Object.keys(manual || {}).forEach(ym => {
    out[ym] = {};
    Object.keys(manual[ym] || {}).forEach(wh => {
      const src = manual[ym][wh] || {};
      out[ym][wh] = keys.map((k, i) => {
        const v = src[k];
        if (isMoney(i)) return (v == null || v === '') ? null : N0(v);
        return (v == null) ? null : String(v);
      });
    });
  });
  return out;
}

/* 提取：后端 `{类别:{仓库:{月:金额}}}` → 原型 `EXTM[月][类别] = [[仓库, 金额], …]`
   （原型 `extMon` 按 `x[0] === 仓库` 找 ⇒ 转形在适配层做，`V.m07` 一行不改）。 */
function adaptExtract(amounts) {
  const out = {};
  Object.keys(amounts || {}).forEach(kind => {
    const byWh = amounts[kind] || {};
    Object.keys(byWh).forEach(wh => {
      const months = byWh[wh] || {};
      Object.keys(months).forEach(ym => {
        const bucket = (out[ym] = out[ym] || {});
        (bucket[kind] = bucket[kind] || []).push([wh, N0(months[ym])]);
      });
    });
  });
  return out;
}

/* 收发结存行：后端 `{name, rows, begin, in, out, end}` → 原型同名字段（`id` 取仓库名 —— 全站唯一键就是它）。 */
const adaptWh = r => ({
  id: String(r.name || ''), name: r.name || '', rows: N0(r.rows),
  begin: N0(r.begin), in: N0(r.in), out: N0(r.out), end: N0(r.end),
});

/* ⭐ **重拉（唯一出口）**：写动作 / 切换核算年月之后一律走它 —— 以后端为准，⛔ 前端不自己造状态。
   ⚠️ `WHM` / `EXTM` / `BIGVAL` 一律**原地清空再填**（对象身份不变 —— 外部持有的是引用）。 */
async function reloadM07() {
  const [st, ex, bg] = await Promise.all([
    API.m07Settlement(fWhYm), API.m07Extract(), API.m07Big(),
  ]);
  const ym = (st && st.ym) || fWhYm;
  Object.keys(WHM).forEach(k => delete WHM[k]);
  (st.rows || []).forEach((r, i) => { (WHM[ym] = WHM[ym] || []).push(adaptWh(r)); });
  const ext = adaptExtract(ex && ex.amounts);
  Object.keys(EXTM).forEach(k => delete EXTM[k]);
  Object.keys(ext).forEach(k => { EXTM[k] = ext[k]; });
  if (bg) {
    if (bg.manual_keys && bg.manual_keys.length) {
      BIG_MKEYS.length = 0; bg.manual_keys.forEach(k => BIG_MKEYS.push(k));
    }
    if (bg.manual_fmts && bg.manual_fmts.length) BIG_MFMTS = bg.manual_fmts;
    const man = adaptManual(bg.manual, BIG_MKEYS, BIG_MFMTS);
    Object.keys(BIGVAL).forEach(k => delete BIGVAL[k]);
    Object.keys(man).forEach(k => { BIGVAL[k] = man[k]; });
    BIGSET.length = 0;
    (bg.selected || []).forEach(k => BIGSET.push(k));
    MAT_OK = !!bg.mat_available;
  }
  /* ⚠️ 大表月份 = `bjMonth(-1)`（原型写死「北京时间上月」，§9.2 材料报表类）——
     与后端 `default_month()` 同口径；后端 `selected` 已是「大表自己的顺序」，不需前端重排。 */
  if (!BIGSET.length) BIGSET.push(...bigCands().filter(k => !BIGSET.includes(k)));
  render();
}

/* 写动作统一外壳：**失败把后端原因原样给用户**（不吞、不换句话），成败都回后端真实状态。 */
async function bgFailed(name, r) {
  await reloadM07();
  toast(`<b>${esc(name)}没能保存</b>：${esc((r && r.message) || '后端未说明原因')}`, 7000);
}

/* 抓收发结存（`API-02`）—— ⚠️ **会登录 i8 并强踢在线用户**（D9 的二次确认由抓取弹窗承担）。 */
async function whFetchBackend(month) {
  closeModal();
  try {
    const r = await API.m07Fetch(month);
    if (r.ok === false) {                    /* 降级：i8 侧失败 ⇒ 走手动 Excel 导入（§3.6） */
      await reloadM07();
      return toast(`<b>抓取没能完成</b>，已<b>降级为手动导入</b>：${esc(r.message || '')}<br>`
        + `<span class="mut sm">可到「导入」入口上传 i8 导出的 Excel（解析走同一条管线）</span>`, 9000);
    }
    await reloadM07();
    const st = r.stats || {};
    let msg = `已按 <b>${esc(month)}</b> 抓取收发结存（API-02）：解析 <b>${r.rows || 0}</b> 行 —— `
      + `新增 <b>${st.inserted || 0}</b> · 更新 <b>${st.updated || 0}</b> · 删除 <b>${st.deleted || 0}</b>`;
    toast(msg + `<br><span class="mut sm">⚠️ 解析条数与落库条数不一致时先怀疑幂等范围（见 ops 实测结论）</span>`, 7600);
  } catch (e) {
    await reloadM07();
    toast(`<b>抓取没能完成</b>：${esc(String((e && e.message) || e))}<br>`
      + `<span class="mut sm">本系统<b>不会自动重试登录</b>（D9，避免反复顶号）—— 请确认 i8 账号后再试</span>`, 8600);
  }
}

/* 机械 6 列（**旁路表**的手录值）—— ⚠️ 不 `render()`：由 `boot()` 后面的 `reloadM05()` 统一渲染。 */"""
)
step("适配层 + reloadM07 + 抓取分支（插在 reloadMech 之前）")

# ============================================================ 6 · 写动作走后端

src = sub_block(
    src, "bigEdit:t=>{", "（${bjMonth(-1)}）`); },", 3000,
    """bigEdit:async t=>{ const wh=t.dataset.p, i=+t.dataset.i, NAME=BIGCOLS[i], raw=String(t.value).trim();
   /* ⭐ 接线：**判定与落库一律后端**（`big_service.save_manual_cell` ⇒ `big_domain.parse_manual`）——
      金额非负 / 开工时间 `YYYY-MM` 的校验不再在前端复写（否则 = 第二份口径）。
      ⛔ 也不本地改 `BIGVAL` 冒充落库：成功后**以后端为准重拉**（`reloadM07()`）。 */
   const was=bigCell(wh,bjMonth(-1),i);
   let r=null;
   try{ r=await API.m07BigCell({month:bjMonth(-1),warehouse:wh,key:BIG_MKEYS[i],raw:raw}); }
   catch(e){ return bgFailed(NAME,{message:String((e&&e.message)||e)}); }
   if(!r||r.ok===false) return bgFailed(NAME,r);
   await reloadM07();
   if(raw===''){ toast(`已清空 <b>${esc(NAME)}</b>（${bjMonth(-1)}），该格回到「上次值带入」状态`); return; }
   const show=(BIGFMT[i]==='m')?M(r.value):esc(String(r.value==null?raw:r.value));
   toast(was.from
     ? `<b>${esc(NAME)}</b>已录入 <b>${show}</b><br>原值带入自 ${was.from}，该格已转为本月正常录入（白底）`
     : `<b>${esc(NAME)}</b>已录入 <b>${show}</b>（${bjMonth(-1)}）`); },"""
)
step("bigEdit → POST /api/m07/big/cell（判定搬后端）")

src = sub_block(
    src, " bigPickOk:()=>{", "个项目出表（行序即刚才设置的行序）`); },", 900,
    """ bigPickOk:async ()=>{ const picked=BIGDRAFT.slice();
   /* ⭐ 接线：选题与顺序**落库走后端**（`big_service.save_selection`）—— 弹窗内仍是原型的草稿层 */
   try{ await API.m07BigSelection(picked); }
   catch(e){ closeModal(); await reloadM07();
     return toast(`<b>选题没能保存</b>：${esc(String((e&&e.message)||e))}`,7000); }
   closeModal(); await reloadM07();
   toast(`活动大表已按所选 <b>${BIGSET.length}</b> 个项目出表（行序即刚才设置的行序）`); },"""
)
step("bigPickOk → POST /api/m07/big/selection")

# ============================================================ 7 · 导出如实标注（属 TAIL-04）

src = sub_block(
    src, "zipSfjc:()=>{", """data-t="收发结存zip">保存到本地</button>`}); },""", 4000,
    """zipSfjc:()=>{ const rows=pjSort(whRows(fWhYm));
   /* ⛔ **不做假成功**（原型这里报「已生成 .zip」却拿不到文件）：真实的成品文件写出属 `TAIL-04`
      （方法已定案 = **模板法**：以用户手作成品 xlsx 为基底做 `zip` 字节替换），与本页接线分开做。 */
   toast(`⏳ <b>导出尚未落地</b>（属 TAIL-04）：本页按 <b>${tmLabel(fWhYm)}</b> 应导出 `
     + `<b>${rows.length}</b> 个分仓库 xlsx ＋ 1 个总表 = <b>${rows.length+1}</b> 个文件（zip 打包，走<b>模板法</b>）；`
     + `方法与实测结论已就绪、只差移植。`, 8600); },"""
)
step("zipSfjc → 如实标注未落地（原为模拟文件大小 + 「已生成」假成功）")

# ============================================================ 8 · 抓取分支 / 月份切换 / boot / WIRED

src = sub_line(
    src, "if(k==='iv') return ivFetchBackend(m);",
    "   if(k==='iv') return ivFetchBackend(m);\n   if(k==='wh') return whFetchBackend(m);"
    "   /* ⭐ 收发结存（API-02）已接后端；`nt` 走 `/api/m03/notices/fetch`（见 fetchNtOk） */"
)
step("fetchNtOk：wh 分支接后端")

src = sub_line(
    src, "if(sc==='wh'){",
    "   if(sc==='wh'){ fWhYm=v; mp.open=null; reloadM07();"
    " toast(`收发结存已切到 <b>${tmLabel(v)}</b>（核算年月，§9.2）`); return; }"
    "   /* ⭐ 切换核算年月 ⇒ **重新取数**（`WHM[月]` 现在来自后端；只 `render()` 会看到空表） */"
)
step("月份切换：重新取数（原只 render ⇒ 空表）")

src = sub_line(
    src, "await soft('付款域', reloadM05);",
    "  await soft('收发结存与大表', reloadM07);   /* ⚠️ 必须在 reloadMech / reloadInv **之后**："
    "大表的机械与焊材/气体列取它们 */\n"
    "  await soft('付款域', reloadM05);          /* 内部各自 render 一次 */"
)
step("boot()：+ 一路 soft（逐路容错）")

src = sub_line(
    src, "const WIRED=new Set([",
    "const WIRED=new Set(['m03','m01','m04','m05','m06','m07','m08']);"
)
step("WIRED：+ m07")

# ============================================================ 写回

SHELL.write_bytes(src)
print(f"\n完成：{before} → {len(src)} 字节（{len(src) - before:+d}）· {len(log)} 处")
print("下一步：`node --check` 抽检 script 段 + 真机自检 tools/_shell_smoke.py")
