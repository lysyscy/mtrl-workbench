/* shell/core.js —— 壳接线层②：**数据出口与各模块接线**
 *
 * 来源：`index.html` 的第 L5096–L5618 ＋ L5688–L6620 行（`P4`② 三刀真拆 · 2026-09-19），分两段原样搬出（中间那段是打印/设置，见 `print-export.js`）。
 * 内容：`CAT_API` · 字段适配器（`adapt*`）· 各模块取数与写动作外壳（`reload*` / `*Act`）
 * ⚠️ **`API`（唯一数据出口）不在这里** —— 2026-09-24（`TAIL-48`）已切到 `api.js`；本件与各页只用它、⛔ 不再定义。
 *       · `BIND.*`（渲染后注入）· 按需取数表（`PAGE_LOAD` / `LOADERS` / `LOAD_DEP` / `soft` / `loadPaths`）。
 * ⚠️ `boot();` **不在本件**（它留在 `index.html` 末尾 ⇒ 启动点显式可见、加载顺序可调）。
 * ⛔ 改这里前先看计划 §23：**原型切片 `V.*` 不许搬出 `index.html`**（`ui_parity` 的 `U1` 逐行比它）。
 *    ⚠️ **订正（2026-09-28 · `TAIL-164`）**：原文写「`index.html` 里 258–3285 那一段（公共外壳 ＋ 原型切片）
 *    不许搬」—— 那句**过宽**（`§23` 的口径只管**原型切片**）：**非切片**的公共代码已按 `P2-a` 搬进
 *    `web/shell/{base,view,ui,proj,pages-a,pages-b}.js` ⇒ ⛔ 别再照那句拦。
 */
/* ⚠️ 分类的**内部值**是英文（`material` / `mechanical` / `jc`），中文只是**显示名** ——
   界面上传下来的是中文 ⇒ 在**这一处**转（映射只写一份，别在动作里各转一遍）。 */
const CAT_API = { '辅材': 'material', '机械': 'mechanical', '集采': 'jc' };

/* ---------- 共用文案（**一处在说、多处引用** ⇒ ⛔ 别在两处各写一遍）----------
   ⭐ 2026-10-01（`TAIL-210` 批 3b）：这几句原先在 2 处逐字重复（同一件事、两处各写一遍
   ⇒ 改一处必漏另一处）。⚠️ 判「要不要并」只看一句：**同一句在 ≥2 处、且将来会一起改**吗？
   ⛔ `class="tip"` 块里的那两处**刻意不并**（抽成 `${CONST}` 会让离线那条长度判据对它们**失明**）。 */
const I8_LOGIN_TIP = '本系统<b>不会自动重试登录</b>—— 请确认 i8 账号后再试；i8 抓不到时可走「手动导入」';
const IMP_DEGRADE_TIP = '可到「导入」入口上传 i8 导出的 Excel';
const OWN_KW_LABEL = '识别关键词（须出现在单据名里）';
const OWN_KW_HINT = '选已有小微时，<b>须填一个出现在上面单据名里的关键词</b>（选中后<b>去重追加</b>到该小微名下，供下次自动命中）；填不出说明不是它。';
/* ⭐ 名字格**按内容定宽**（`ACC-PRJ-LIST-001/001-07`「长项目名必须完整可读 —— ⛔ 不得被容器硬切」）
 *
 * ⚠️ 为什么必须这么干：`<input>` 的宽度**由 CSS 决定、不由内容决定** ⇒
 *    写死 `min-width:162px/240px` 时，长项目名**必然**被切 —— 能点进去横滚，
 *    但那是"藏起来"，**不等于"读得到"**。⭐ 2026-09-20 用户裁定走 **(b) 完整版**：
 *    **改实现去够口径**（⛔ 不是把 claim 收窄成"可点入读全"）。
 *
 * ⚠️⚠️ **为什么放在 `core.js`、而不是 `V.m01` 里面**：`tools/audit/ui_parity.py` 是
 *    按**行号逐行**把壳和原型切片比对的 ⇒ 在 `V.m01` 里**插一行**，
 *    它后面**每一行都算漂移**（我第一次就是这么干的，一下冒出 66 条"未登记漂移"）。
 *    ⇒ ⭐ **原型切片里只做等行数的原地替换**；新函数一律放本文件（它不参与逐行比对）。
 *
 * ⚠️ 算法：按**字符显示宽度**算 —— CJK / 全角记 2、其余记 1（≈ `ch` 的口径，即 `0` 的宽度），
 *    `ch` ＋ 内边距 ＋ 余量 ⇒ 名字**整串可见**；宽度超出时由表格整体横向滚动
 *    （⛔ 不是每行各自滚 —— 那会让人左右找不到北）。`min` 是下限，免得短名字的格子塌得点不进去。
 */
const nameW = (s, min) => {
  let u = 0;
  for (const c of String(s == null ? '' : s)) {
    u += /[\u1100-\u115f\u2e80-\ua4cf\ua960-\ua97f\uac00-\ud7ff\uf900-\ufaff\ufe30-\ufe6f\uff00-\uff60\uffe0-\uffe6]/.test(c) ? 2 : 1;
  }
  return `width:calc(${u}ch + 24px);min-width:${min}px;`;
};

/* ─────────────────────────────────────────────────────────────────────────
   ⭐⭐ **通用件**（`TAIL-67` · 2026-09-21 · 批次 0）—— 本段是**切片外**公共层，
       不参与 `U1` 的逐行比对 ⇒ 新函数一律放这里（`core.js` 头部就是这么说的）。
   ───────────────────────────────────────────────────────────────────────── */

/* ⭐ **导出下载**（原样重复了 **8 份**：`procExpSave` / `expPivot` / `zipSfjc` / 焊材气体 /
   总欠款 / 欠款台账 / 经济活动分析大表 / `m03Download`）。
   ⭐⭐ 抽它的**真理由不是省行数**，而是：**错误分类必须只有一个口径** ——
     8 份重复的下场是"改了一处的说法，另外 7 处还在说别的话"
     （与 2026-09-21「收款账号取错字段」同型：**同一件事 N 个主人**）。
   契约：
     · 成功 ⇒ 返回**文件名**（⛔ 命名规则的**主人是后端**，`name` 只是后端没给时的兜底）；
     · 失败 ⇒ 返回 `''`，且**已经弹过 toast** ⇒ ⛔ 调用方**不要再弹一遍**（会弹两条）。
     · `label` = '导出' / '下载'（只影响失败提示的措辞）；`close` = 成功后关弹窗。
   ⚠️ 顺序照旧：**先看 `content-type`**（后端失败回的是 **JSON 200**），再看 `r.ok`。
      ⛔ 反过来会拿一个"打不开的 xlsx/pdf"当文件存下来（2026-09-20 实测过的坑）。 */
async function dlExport(url, { name = '导出文件', label = '导出', close = false } = {}) {
  /* ⭐ 2026-09-21 用户口径「点了让人以为没点住」：导出是**重动作**（后端要现场生成文件，
     几秒很正常）⇒ **先给一句进行中反馈**，成功/失败的明确提示由调用方在完成后给。 */
  toast(`<b>${label}</b>：正在从服务器准备文件 …（完成后会再提示）`, 4000);
  let r;
  try { r = await fetch(url); }
  catch (e) {
    /* ⚠️ 这条 catch 抓的是 `fetch` **本身**抛的（断网 / 服务没起来）—— 它的 `message`
       是浏览器的英文原文（`Failed to fetch`）⇒ ⛔ 不能直接上屏，必须过「人话出口」。 */
    const h = errHuman(`没能连上服务器（${label}这一步）。请确认服务在运行，然后重试。`,
      String((e && e.message) || e));
    toast(`<b>${label}没能完成</b>：${esc(h.message)}`, 8000); return '';
  }
  const ct = r.headers.get('content-type') || '';
  if (ct.includes('application/json')) {
    let d = {};
    try { d = await r.json(); } catch (e) { /* 读不出 ⇒ 下面统一报「没拿到原因」的人话 */ }
    /* ⚠️ 两种失败体都认：自己回的 `{message}`（ok:false）· FastAPI 的 `{detail}`（HTTPException）。
       ⭐ 后端给了中文（"为什么＋怎么解决"）⇒ **原样透传**；没给 ⇒ 只说人话，⛔ 不写"后端没给原因"
         这种给开发看的话（守则 §3.3）。 */
    const why = (d && (d.message || d.detail)) || '';
    const h = errHuman(`没能生成文件${why ? '：' + why : '，服务器没有说明原因。请稍后重试'}`
      + '；仍失败请把这一步告诉管理员。', `GET ${url} → 200 · JSON 失败体=${JSON.stringify(d).slice(0, 300)}`);
    toast(`<b>${label}没能完成</b>：${esc(h.message)}`, 9600);
    return '';
  }
  if (!r.ok) {
    const h = errHuman('没能生成文件，服务器返回了错误。请稍后重试；仍失败请把这一步告诉管理员。',
      `GET ${url} → HTTP ${r.status}`);
    toast(`<b>${label}没能完成</b>：${esc(h.message)}`, 8000); return '';
  }
  const fn = decodeURIComponent(r.headers.get('x-export-filename') || '') || name;
  const blob = await r.blob(), a = document.createElement('a');
  a.href = URL.createObjectURL(blob); a.download = fn;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 5000);   /* ⚠️ 不 revoke ⇒ 每次导出都漏一份内存 */
  if (close) closeModal();
  return fn;
}

/* ⚠️ **日期件 `ymOf` / `ymdOf` 不在这里** —— 它们必须在**壳脚本初始化之前**就存在
   （`bjMonth()` 在初始化期就被调用），而本件（`shell/*.js`）是**在 `index.html` 的内联脚本之后**加载的
   ⇒ 放这儿会得到 `ymOf is not defined` ⇒ **整个壳起不来**（2026-09-21 实测，当场白屏一次）。
   ⇒ 它们落在 `index.html` 的切片外公共层（见那里「通用件」注释）。
   ⭐ 记这条判据：**切片外还分两层** —— 初始化期要用的 ⇒ `index.html`；只在交互时才用的 ⇒ 本件。 */

/* ⭐ `API`（取数出口）已切到 `shell/api.js`（2026-09-24 · 见设计件 §八.5 第 1 刀）——
   ⚠️ 它必须在 `core.js` **之前**挂载（顺序真源 = `index.html` 的 `<script src>`）。 */


/* ---------- 字段适配：后端**语义字段** → 原型字段名（`NT_COLS` / `PJ_COLS`） ----------
   ⚠️ API 不为某个前端定制 ⇒ 映射只写在这**一处**（前端壳的适配层）。 */
const numOr0 = s => Number(String(s == null ? '' : s).replace(/,/g, '')) || 0;

function adaptNotice(x) {
  return {
    /* ⚠️ id **必须 String** —— 原型里 id 是字符串（`'N01'`），全站到处 `n.id===t.dataset.id`
       做同值比较，而 `dataset` 出来的永远是字符串。后端给的是数字 ⇒ 不转就会**静默失配**
       （实测：勾选后汇总条恒为 0）⇒ 在这**一处**转，下游一行都不用改。 */
    id: String(x.notice_id), date: x.doc_date, code: x.bill_no,
    /* ⚠️⚠️ **必须是「项目全名」**（`project_name`），**不能**用 `project_display`（那是**展示名**）——
       `ownOf(n)` 拿它做 `PJs.find(p => p.full === n.proj)`（**全名等值**匹配），
       还会做 `isShellFull(n.proj)`（判是不是壳，靠名字里的「小微」）与 `matchKids(n.proj, n.doc)`。
       填展示名 ⇒ 三条**全部静默失配** ⇒ 归属判不出 ⇒ 「项目筛选」候选**一个都没有**（实测报障）。
       ⭐ 归属的权威值走 `x.ownership_id`（见 `reloadNotices()` 灌进 `OWN`），`proj` 只作兜底。 */
    proj: x.project_name || x.project_display, doc: x.bill_name,
    biz: x.biz_type, recv: x.payee, entry: x.input_by,
    approve: numOr0(x.amount_approved), pay: numOr0(x.pay_amount),
    ss: numOr0(x.stat_settle), sp: numOr0(x.stat_paid),
    cat: x.category_label || x.category, astat: x.approve_status,
    excl: !!x.is_excluded,
    exrule: x.exclude_source === 'manual' ? '人工批量剔除' : '规则命中',
    sup: x.jc_supplier || '', trail: x.edited_fields || [], planId: null,
    manual: !!x.is_manual,
    /* 后端算好的三个状态值**直接带上**（前端不重算）：已付 / 是否撤单 / 有无生效流水 */
    paidApi: numOr0(x.amount_paid), revoked: !!x.is_revoked,
    hasFlow: !!x.has_effective_flow, oid: x.ownership_id,
    /* ⭐ `P4` 超付（§4.4.6）：**判定在后端**（`NoticeRow.is_overpaid`）—— 壳只拿来渲染 */
    over: !!x.is_overpaid,
  };
}

/* 项目状态：**内部值（后端）↔ 显示值（原型）**的唯一出口（§2.7 的枚举在前端是中文）。
   ⛔ 不转的后果（实测口径）：`fPj.status`（`'在建'`）与 `p.status`（`'active'`）**永不相等**
   ⇒ 项目档案页**恒为空**，且状态列的 `<select>` 一个都不选中 —— **静默、不报错**。 */
const PJ_STATUS_LABEL = { active: '在建', archived: '归档' };
const PJ_STATUS_VALUE = { '在建': 'active', '归档': 'archived' };
/* 关键词：后端是**数组**、原型是**竖线串**（`|词1|词2|`，`editKw` 的输入框就是它）——
   在同一个出口转，两侧都不改。 */
const kwJoin = list => (list && list.length) ? '|' + list.join('|') + '|' : '';
const kwSplit = s => String(s == null ? '' : s).split('|').map(x => x.trim()).filter(Boolean);

/* ⭐ MOD-01 项目档案「**当前筛选下可见的行**」—— 导出（`TAIL-04` · `ACT.exp`）要用。
   ⚠️⚠️ **它是 `V.m01` 里那段内联筛选的镜像**：`V.m01` 里是
       `const TYPE=…; const q=…; const rows=pjSort(PJs.filter(p=>…));`（逐字见下）。
   ⛔ **为什么不直接把 `V.m01` 改成调本函数**（那样就只有一份了）：`V.` 切片是 `ui_parity` 的 `U1`
      逐行比对的**原件**，而**配对的原型在「面」**（`demo/…-交互原型.html`）——改一处要同改另一处，
      还会连带**原型导读的逐页「行号区间 + 行数」表**、`_smoke` 的四检断言、追溯表、验收基线一起重算
      （`audit_common.CANCELLED_KEEP_IN_PROTO_AND_DOCS` 那段注释里记着这笔账）。
      ⇒ 本仓既定做法：**接线层可以加件，原型切片一行不动**（同 `BIND.m11` 接管导出按钮那次）。
   ⚠️ **所以这是"故意存在的第二份"**，靠 `tests/test_tail04_pages.py` 把**两份钉死**：
      谁只改一处，测试当场点名（⛔ 别把那条测试当成"重复代码告警"删掉 —— 它就是这个重复的保险）。
   ⛔ 改筛选条件 ⇒ **两处一起改**。 */
const pjVisible = () => {
  const TYPE = { 普通项目: 'normal', 小微壳: 'shell', 具体小微: 'small' }[fPj.type] || '';
  const q = fPj.q.trim();
  return pjSort(PJs.filter(p => (fPj.status === '全部' || p.status === fPj.status)
    && (!TYPE || p.type === TYPE)
    && (!q || (p.name || '').includes(q) || (p.full || '').includes(q) || (p.disp || '').includes(q))));
};

function adaptProject(p) {
  return {
    id: String(p.id), name: p.warehouse_name || '', disp: p.disp || p.warehouse_name || '',
    full: p.name_full || '', phid: p.phid || '',
    status: PJ_STATUS_LABEL[p.status] || p.status || '',
    type: p.project_type || '',
    /* ⚠️ `parent` 必须 `String()` —— 原型到处 `x.parent === p.id` 做**同值比较**，
       而 `p.id` 是字符串、`parent_shell_id` 是数字 ⇒ 不转则**壳与小微永远对不上**
       （具体小微显示不出所属壳，归档不变式也判不了）。与 `id` 同一条纪律。 */
    parent: (p.parent_shell_id == null ? null : String(p.parent_shell_id)),
    kw: kwJoin(p.match_keywords), ord: p.ord,
  };
}

/* 留痕：后端的**语义对象** → 「修改留痕」卡要的**六元数组**。
   ⚠️ 为什么是数组：那张卡的渲染在 `V.m01` 里（原型**一行不改**），它按下标取
   `[时间, 项目, 字段, 改前值, 改后值, 改动人]` ⇒ 转换只能落在适配层。 */
function adaptTrail(l) {
  return [l.at, l.project, l.field_label, l.before, l.after, l.by];
}

/* 写动作成功后**以后端为准**重拉（⛔ 前端不自己造状态 —— 否则前后端各一份、必漂） */
async function reloadNotices() {
  const nt = await API.notices();
  const items = nt.items || [];
  NO = items.map(adaptNotice);
  /* ⭐⭐ 「归属」缓存 `OWN`（`通知书 id → 项目档案行 id`）—— **后端 `ownership_id` 是权威值**，
     每次重拉都按它重建。⛔ 这里以前是空的（只在原型的手动新增/归集动作里写），
     后果 = `ownOf(n)` 退化成"拿全名去档案里反查"⇒ 只要全名有一点差异（或还没入库）
     **归属就判不出** ⇒ 「项目筛选」候选一个都没有（实测报障）。
     ⚠️ **原地清空**、不 `OWN={}` 重新赋值（防外部持有旧引用 —— 壳里的既有教训）。 */
  Object.keys(OWN).forEach(k => delete OWN[k]);
  items.forEach(x => {
    if (x.ownership_id != null) OWN[String(x.notice_id)] = String(x.ownership_id);
  });
  render();
}

async function reloadProjects() {
  const [pj, tr] = await Promise.all([API.projects(), API.trails()]);
  PJs = (pj || []).map(adaptProject);
  PJ_TRAIL.splice(0, PJ_TRAIL.length, ...(tr || []).map(adaptTrail));
  /* ⭐ 待人工指认清单与档案**同源同刷**（刚扶正完必须立刻少一条，否则用户会以为没生效）——
     ⚠️ 但**不许**它拖垮档案页：这一路取不到时只是清单缺失，页面**如实说明**（`PEND_ERR`），
        档案与留痕照常显示（同 `boot()` 的逐路容错口径）。 */
  try { await reloadPending(); }
  catch (e) { PEND_ERR = String((e && e.message) || e); }
  try { await reloadArchPend(); }   /* ⭐ `TAIL-45`：建档向导那一路（独立容错 —— 别拖垮档案页） */
  catch (e) { ARCP_ERR = String((e && e.message) || e); }
  render();
}

/* 写动作的统一外壳：⛔ 后端拒绝时**把原因原样给用户**（如"壳下还有 N 个在建小微：A、B"），
   并把界面**恢复成后端真实状态**（本地不保留任何乐观改动）—— 「原值保留」是 §2.7.2 的明确要求。 */
/* 类型纠正弹窗（`TAIL-42`）—— 可选只有两个，其余是把口径讲清（⛔ 判定不在壳里） */
const PJ_TYPE_LABEL = {normal: '普通项目', shell: '小微壳', small: '具体小微'};
let pjTypeCur = null, pjTypeNew = '';

function pjTypeDlg() {
  const p = pjTypeCur;
  if (!p) return;
  const opt = (k, desc) => `<div style="display:flex;align-items:center;gap:calc(10px * var(--fscale));padding:calc(8px * var(--fscale));border:1px solid var(--bd);border-radius:7px;margin-bottom:calc(7px * var(--fscale))">
      <button class="btn sm ${pjTypeNew === k ? 'pri' : 'gost'}" style="flex:0 0 auto" data-act="pjTypePick" data-t="${k}">${pjTypeNew === k ? '已选' : '选它'}</button>
      <span style="flex:1;min-width:0"><b>${esc(PJ_TYPE_LABEL[k])}</b> <span class="mut sm">· ${desc}</span></span></div>`;
  modal({
    title: `改类型 · ${esc(pjDisp(p))}`,
    body: `<div class="tip" style="margin-bottom:calc(10px * var(--fscale))">当前类型：<b>${esc(PJ_TYPE_LABEL[p.type] || p.type)}</b>。
      <b>三类判定</b>（§2.2.1）：全名含「小微」⇒ <b>小微壳</b>；同一全名挂 <b>≥2 个仓库</b> ⇒ 待人工确认；其余 ⇒ <b>普通项目</b>。
      ⚠️ 有的壳全名里<b>没有「小微」</b> ⇒ 会被判成普通项目 —— <b>这里就是人工纠正的入口</b>（改动<b>留痕</b>，可在「修改留痕」卡查）。</div>
      <div class="tip wn" style="margin-bottom:calc(10px * var(--fscale))">⛔ <b>不能选「具体小微」</b>：它得挂在一个壳下面、还占一个仓库名，由链路产生（人工指定只会造出挂不上的行）。</div>
      ${opt('shell', '不挂仓库；它名下的仓库 = 具体小微（今后走这条路）')}
      ${opt('normal', '要挂一个仓库名（候选键）—— 选了它，下面会让你填')}
      ${pjTypeNew === 'normal' ? `<div style="margin-top:calc(6px * var(--fscale))"><div class="sm mut" style="margin-bottom:calc(4px * var(--fscale))">仓库名（普通项目必填）</div>
        <input class="inp" id="pjTypeWh" style="width:100%" value="${esc(p.name || '')}" placeholder="填这一行挂的仓库名"></div>` : ''}`,
    footer: `<button class="btn" data-act="closeModal">取消</button><button class="btn pri" data-act="pjTypeOk">确认改类型</button>`,
  });
}

async function pjAct(fn, okMsg, ms) {
  try {
    const r = await fn();
    await reloadProjects();
    toast(typeof okMsg === 'function' ? okMsg(r) : okMsg, ms);
    return r;
  } catch (e) {
    try { await reloadProjects(); } catch (_) { /* 取数也失败 ⇒ 交给 bootErrorBanner 的常驻提示 */ }
    toast(`<b>没能改成</b>：${esc(String((e && e.message) || e))}`, 7000);
    return null;
  }
}

/* ---------- MOD-05 付款流水与欠款（⭐ **判定一律后端**：欠款 / 台账 / 付款统计都由后端算） ----------
   ⚠️ 原型在**浏览器里**自算这三块（`debts()` / `ledRows()` / `pstData()`）⇒ 接线后**只读后端**；
      前端保留的只有**筛选 / 排序 / 显示**（D18：判定与落库一律后端，别留第二份口径）。 */
const M05 = { debt: null, stats: null, ledger: null };      /* 四块数据的缓存（`reloadM05` 填） */
const M05_GRAN_API = { '周': 'week', '月': 'month' };
const M05_GRAN_UI = { week: '周', month: '月' };
/* ⭐ **机械结算源已接线**（= 过程资料机械 6 列 ⇒ `MACH6` 由 `/api/m06/mech` 填）——
   所以 `V.m05` 直接调 `machSettleOf(k)`，与原型写法**逐字一致**（那条登记漂移已消号）。 */

function adaptFlow(x) {
  return {
    id: String(x.id), nid: (x.notice_id == null ? '' : String(x.notice_id)),
    date: x.pay_date || '', amt: numOr0(x.amount), method: x.pay_method || '',
    remark: x.remark || '', op: x.created_at || '',
    voided: x.status !== 'effective', reason: x.revoke_reason || '',
    projKey: x.project_key || '', proj: x.project_display || '', doc: x.doc_no || '',
  };
}
/* 期初行：只喂「按项目看欠款」的柱子（台账行改读后端）⇒ 按原型 `LG_COLS` 的关键字段给 */
function adaptOpening(x) {
  return {
    /* ⭐ 2026-09-28 修：这里原来把 id **写死成假值 `''`**（因为当时 `/api/m05/debt` 不返回 id）
       ⇒ 「删除期初行」按钮 `LGs.find(x=>x.id===…)` **永不匹配、静默无反应**（用户走查报障）。
       现在后端给了真 id（`openings[].id`，与 `ledger.opening_id` 同源）⇒ 如实带上；空值仍留空
       （守则 §铁律 4：⛔ 不许拿假值冒充 —— 但**调用方**必须对"没有"给可见反馈，不许静默 return）。 */
    id: x.id == null ? '' : String(x.id),
    proj: x.project_key || x.project_label || '', cat: x.category_label || '',
    settle: numOr0(x.settle), paid: numOr0(x.paid), cutoff: x.cutoff || '', remark: '',
  };
}

/* 一次拉齐四块（台账按**当前选中项目**）—— 换项目 / 换粒度 / 换轴 / 写动作之后都走它 */
const M05_FETCHED = { gran: '', year: 0, quarter: 0, pj: '' };   /* 上次**成功取到**的参数 */
/* ⚠️ `pstQq()` 返回的是 `'2026Q3'` 这种**字符串**，而后端 `quarter` 是 int ⇒ **必须解析**
   （不解析就是 422，整页取数全挂 —— 实测踩到过）。 */
const m05Params = () => ({
  granularity: M05_GRAN_API[pst.gran] || 'week',
  year: Number(pstYear()) || 0,
  quarter: Number(String(pstQq()).slice(5)) || 0,
  pj: ledCur(),
});
let m05Refetching = false;
/* ⏳ **启动期间不补拉**（性能 `P3`① · 2026-09-19）：`boot()` 里那 13 路**陆续到位**时，
   每路都会 `render()`，而 `m05Sync()` 挂在 `render` 上 —— 它的参数里有 `ledCur()`（依赖 `ledProjs()`，
   随项目数据到位而**变**）⇒ 实测同一页加载里 `/api/m05/{flows,stats,debt}` 各发了 **3 次**、
   `/api/m05/ledger` 2 次（合计约 **420 ms** 的**纯重复**请求 + 同等后端算力）。
   ⛔ `m05Refetching` 挡不住这个（它是"串行"、不是"合并"）。
   ⇒ `boot()` 期间一律不补拉；boot 末尾**本就有一次显式 `reloadM05()`**（第二组）✓，参数那时已稳定。 */
let BOOTING = true;
async function reloadM05() {
  const p = m05Params();
  const row = p.pj ? pjRowOf(p.pj) : null;
  const [fl, debt, st, lg] = await Promise.all([
    API.flows(), API.debt(), API.stats(p),
    (row && row.id) ? API.ledger(row.id) : Promise.resolve(null),
  ]);
  FLs = (fl.rows || []).map(adaptFlow);
  LGs.splice(0, LGs.length, ...((debt.openings || []).map(adaptOpening)));   /* `const` ⇒ 原地改 */
  M05.debt = debt; M05.stats = st; M05.ledger = lg;
  M05_FETCHED.gran = p.granularity; M05_FETCHED.year = p.year;
  M05_FETCHED.quarter = p.quarter; M05_FETCHED.pj = p.pj;
  render();
}
/* 参数（粒度 / 轴 / 台账项目）变了就**自动补拉** —— 收敛成一个点，
   ⛔ 不必给每个选择器（`pstGran` / 时间轴 / `ledPjPick`）各挂一个钩子。 */
async function m05Sync() {
  /* ⏳ `P3` 主体（2026-09-19）：**这一页的取数还没发生**时不补拉 —— 否则启动收尾那次 render 会
     顺手把 m05 那 4 路拉回来（用户还在 `home`，纯浪费；实测约 180 ms），且 `go('m05')` 时
     会与 `loadPaths` 的取数**并发重复**。`LOADED` 只在**取数完成后**才记名 ⇒ 这一条同时挡住两家。
     ⚠️ 参数驱动补拉（粒度 / 轴 / 台账项目）只在 m05 页上有意义 ⇒ 那时 `付款域` 必然已 LOADED ✓。 */
  if (BOOTING || m05Refetching || !LOADED.has('付款域')) return;
  const p = m05Params();
  if (p.granularity === M05_FETCHED.gran && p.year === M05_FETCHED.year
      && p.quarter === M05_FETCHED.quarter && p.pj === M05_FETCHED.pj) return;
  m05Refetching = true;
  try { await reloadM05(); } catch (e) { /* 取数失败 ⇒ 交给常驻提示 */ } finally { m05Refetching = false; }
}
/* ⭐ 把 `render` 包一层：渲染完顺手对账 m05 的参数（变了就补拉）。
   ⚠️ 这是**取数钩子**、不是改交互 —— `V.*` 一个切片都没碰（`ui_parity` U1 仍只认那 2 条已登记漂移）。 */
const _renderProto = render;
render = function () { _renderProto.apply(this, arguments); m05Sync(); };

/* 写动作外壳（与 `pjAct` / `plAct` 同款：失败**原样显示后端原因**并回滚到后端真实状态） */
async function m05Act(fn, okMsg, ms) {
  try {
    const r = await fn();
    await reloadM05();
    toast(typeof okMsg === 'function' ? okMsg(r) : okMsg, ms);
    return r;
  } catch (e) {
    try { await reloadM05(); } catch (_) { }
    toast(`<b>没能改成</b>：${esc(String((e && e.message) || e))}`, 7000);
    return null;
  }
}
/* 台账当前项目在**后端**的那一侧（按中文分类名找） */
const m05Side = sc => { const lg = M05.ledger; return lg ? ((lg.sides || []).find(x => x.label === sc) || null) : null; };
/* ---------- MOD-04 付款计划：后端语义字段 → 原型字段名（`PL_COLS`） ----------
   ⚠️ 行内可改列的**列名映射**（原型的 `data-f` → 后端列名）—— 只在适配层转一次 */
const PL_COL_API = { docNo: 'doc_no', date: 'pay_date', method: 'pay_method', remark: 'remark' };

function adaptPlan(x) {
  return {
    id: String(x.id),
    ym: x.year_month,
    /* ⚠️ `proj` 保留**用户填报原值**（展示名 / 仓库名）—— 原型据此做匹配显示（`plProjCell`），
       换成后端解析好的展示名会把「未匹配」这一档抹掉（那是显示逻辑，不是判定）。 */
    proj: x.project_input || '',
    docNo: x.doc_no || '',
    flowAmt: numOr0(x.flow_amount),
    monthAmt: numOr0(x.planned_amount),
    date: x.pay_date || '',
    method: x.pay_method || '',
    remark: x.remark || '',
    forced: !!x.forced_through,
    forceRemark: x.forced_remark || '',
    manual: !!x.is_manual,
    /* ⭐ **审查结果 = 后端判定**（`domain.audit_rows`），前端不再自算（见 `plRev`） */
    result: x.audit_result || '',
    bucket: x.audit_bucket || '',
    /* 派生两列（按单据号命中 i8 通知书）；`null` = 未命中 ⇒ 界面显示「—」 */
    paid: (x.paid_amount === '' || x.paid_amount == null) ? null : numOr0(x.paid_amount),
    left: (x.unpaid_amount === '' || x.unpaid_amount == null) ? null : numOr0(x.unpaid_amount),
  };
}

/* 待删行的 id 暂存（`plConfirm` 弹窗 → `plDelOk` 确认，两步之间传递） */
let plDelIds=[];
async function reloadPlans() {
  const d = await API.plans();
  PLs = (d.rows || []).map(adaptPlan);
  prunePlPick();          /* 勾选集合裁剪到当前可见范围（筛选/重拉后必做） */
  render();
}

/* 付款计划的写动作外壳（与 `pjAct` 同款：失败**原样显示后端原因**并回滚到后端真实状态） */
async function plAct(fn, okMsg, ms) {
  try {
    const r = await fn();
    await reloadPlans();
    toast(typeof okMsg === 'function' ? okMsg(r) : okMsg, ms);
    return r;
  } catch (e) {
    try { await reloadPlans(); } catch (_) { /* 取数也失败 ⇒ 交给常驻提示 */ }
    toast(`<b>没能改成</b>：${esc(String((e && e.message) || e))}`, 7000);
    return null;
  }
}

/* ---------- 启动：拉真数据 → 渲染；失败**降级成可读提示**（⛔ 不白屏、不静默） ---------- */
let BOOT_ERROR = '';
/* =====================================================================
   ⭐ 链路 C：抓取被拒 ⇒ 「未命中清单」弹窗（`TAIL-29`-② ④）
   形态照原型 `V.m03` 的 `ownOpen`：候选小微逐行 ＋ 每行关键词必填 ＋ 末行「属于新小微」。
   ⛔ 判定与落库一律后端（`validate_keyword_in_doc` / `append_keyword_dedup`）；本层只显示与转发。
   ⭐ 用户裁定 `B`：**不暂存整批数据** —— 弹窗只用「单据名 ＋ 候选小微」，
     补完词**再抓一次**即自动命中落库。
   ===================================================================== */
/* ⭐⭐ 2026-09-21 用户口径「统一像集采台账」：**抓取是重动作**（登录 i8 · 可能顶号 · 全量刷新当月），
   结果**必须弹窗回显**（条数 / 扶正 / 待人工 / 降级原因），⛔ 不是一闪而过的提示条 ——
   用户要能看完再关。nt / wh / iv 三条抓取已全部改走本件（集采 m11 本来就是弹窗 = 参照形态）。 */
function fetchResultModal(title, html) {
  modal({ title, body: `<div class="bd" style="line-height:1.95">${html}</div>`,
    footer: `<button class="btn pri" data-act="closeModal">知道了</button>` });
}

async function ntFetchBackend(m) {
  closeModal();
  toast(`正在抓取 <b>${m}</b> 的付款通知书（会登录 i8：<b>可能顶掉在线用户</b>）…`, 4000);
  let r;
  try { r = await API.fetchNotices(m); }
  catch (e) {
    await reloadM02IfOn();     /* ⚠️ 抓取失败**也写了一条执行记录**（`_persist_fetch` 的失败路径）⇒ 卡也要变 */
    return fetchResultModal(`抓取失败 · 付款通知书`,
      `<b style="color:var(--wn)">网络或服务异常</b>：${esc(String((e && e.message) || e))}`);
  }
  if (r.ok) {
    await reloadNotices();
    await reloadM02IfOn();     /* ⭐ 刚写的那条记录要**立刻**在记录卡上看到（见 `reloadM02IfOn`） */
    return fetchResultModal(`抓取结果 · 付款通知书`,
      `已抓取 <b>${esc(m)}</b>：i8 返回 <b>${r.fetched}</b> 条，写入 <b>${r.upserted}</b> 条。`);
  }
  /* 失败：把后端原因**原样**给用户（后端已写成中文）；属「归属未走完」⇒ 直接开补词弹窗 */
  await reloadM02IfOn();       /* ⚠️ 「抓取被拒」同样是**一条真记录**（`failed`）⇒ 卡上要能看到 */
  fetchResultModal(`抓取被拒 · 付款通知书`,
    `<b style="color:var(--wn)">这次抓取被拒绝了</b>：${esc(r.message || '未知原因')}`);
  try { await openOwnDialog(); } catch (e) { /* 打不开弹窗也不影响上面那句原因 */ }
}


/* ⭐ `TAIL-93`：弹窗的**数据源**可切换 —— `'nt'` = 付款通知书（原有）· `'jc'` = 集采合同（新）。
   ⛔ 判定与写路径**一个字都不分叉**：两个来源的条目形状**是同一个**（`project_name` / `doc_name` /
      `kind` / `shell_id` / `candidates`），写一律走 `ownAssignSubmit`（后端那个端点**只补档案**）。
   ⚠️ 两边都靠后端「**只认最近一次抓取** ＋ **按当前档案现算**」⇒ 用户刚补的词 / 刚建的小微**当场生效**。 */
let OWN_SRC = 'nt';

async function ownItems() {
  const d = await (OWN_SRC === 'jc' ? API.jcUnsettled() : API.unresolved());
  return (d && d.items) || [];
}

/* ⭐ 切数据源**不动 `openOwnDialog` 的签名**（有测试按原样匹配它）—— 这层壳只设置来源再开。 */
async function openOwnDialogFor(src) { OWN_SRC = src; return openOwnDialog(); }

async function openOwnDialog() {
  OWN_WH = {};                      /* ⚠️ 换来源/重开 ⇒ **清掉上次查名单的结果**（它按条目下标存，会串） */
  const items = await ownItems();
  if (!items.length) return;
  const box = items.map((it, i) => {
    OWN_CTX[i] = it.project_name || '';          /* `TAIL-39`：查名单后用来核"是不是同一个壳" */
    const cands = it.candidates || [];
    const rows = cands.map(c => `<div style="display:flex;align-items:center;gap:calc(9px * var(--fscale));padding:calc(7px * var(--fscale)) calc(8px * var(--fscale));border:1px solid var(--bd);border-radius:7px;margin-bottom:calc(7px * var(--fscale))">
      <button class="btn sm pri" style="flex:0 0 auto" data-act="ownAssign" data-i="${i}" data-pid="${c.id}">归集到它</button>
      <span style="flex:1;min-width:0">${esc(c.disp)} <span class="mut sm">· 仓库名 ${esc(c.warehouse_name || '—')} · 关键词 ${esc((c.keywords || []).join('、') || '—')}</span></span>
      <input class="inp" style="width:148px;flex:0 0 auto" id="ownKw_${i}_${c.id}" placeholder="关键词">
    </div>`).join('');
    const note = it.kind === 'needs_keyword' ? '（单据名未命中该壳下任何小微 ⇒ 选一个并补词即可）'
      : it.kind === 'needs_choice' ? '（单据名命中该壳下多个小微 ⇒ 选一个并补词）'
        : it.kind === 'not_archived'
          ? '⛔ <b>未建档</b>（且不在 i8 常用项目列表）⇒ 请把它<b>加入 i8 常用项目列表</b>，下次抓取会自动建档 —— <b>不要</b>在这里新建小微'
          : `（${esc(it.kind)}）`;
    return `<div style="border:1px solid var(--bd2);border-radius:8px;padding:calc(10px * var(--fscale));margin-bottom:calc(10px * var(--fscale))">
      <div class="sm" style="margin-bottom:calc(6px * var(--fscale))"><b>${esc(it.project_name)}</b> <span class="mut">${note}</span></div>
      ${kvBlock([['单据编码', `<span class="fc">${esc(it.bill_no || '—')}</span>`], ['单据名称', `<span class="fc">${esc(it.doc_name || '—')}</span>`]])}
      <p style="font-size:calc(12px * var(--fscale));margin:calc(6px * var(--fscale)) 0 calc(8px * var(--fscale))">${OWN_KW_HINT}</p>
      ${rows || '<div class="tip wn" style="margin:0 0 calc(9px * var(--fscale))">该壳下<b>暂无具体小微</b> → 只能走下面的「新小微」。</div>'}
      <div style="padding:calc(9px * var(--fscale));border:1px dashed var(--bd);border-radius:7px;margin-top:calc(8px * var(--fscale))">
        <div class="mut sm" style="margin-bottom:calc(7px * var(--fscale))">属于<b>新小微</b> → 录「仓库名 ＋ 关键词」建档</div>
        <div class="fld"><label>新小微的仓库名</label><input class="inp" id="ownNewName_${i}" placeholder="如：河南南阳热电项目仓库"></div>
        <div class="fld" style="margin-top:calc(6px * var(--fscale))"><label>${OWN_KW_LABEL}</label><input class="inp" id="ownNewKw_${i}" placeholder="如：南阳"></div>
        <div style="margin-top:calc(8px * var(--fscale))">
          <button class="btn gost" data-act="ownWhCheck" data-i="${i}">① 先查 i8 仓库名单</button>
          <span id="ownWhRes_${i}" class="sm" style="margin-left:calc(8px * var(--fscale))"></span>
        </div>
        <div class="mut sm" style="margin-top:calc(6px * var(--fscale))">⭐ <b>建档前必须先跑这一环</b>（用户 2026-09-18 口述裁定）——
          不查就建＝凭猜填仓库名，会留下与 i8 不符的<b>假档案行</b>。⚠️ 查名单要登录 i8，<b>会顶号</b>，故要二次确认。</div>
        <div style="margin-top:calc(8px * var(--fscale))"><button class="btn" data-act="ownAssign" data-i="${i}" data-pid="__new">建档并归集</button></div>
      </div>
    </div>`;
  }).join('');
  modal({
    title: `待指定归属 · ${items.length} 条`,
    wide: true,
    body: `<div class="tip" style="margin-bottom:calc(10px * var(--fscale))">${OWN_SRC === 'jc'
      ? `<b>项目名落在「壳」上</b>，而「单据名称」没能在该壳下的小微关键词里命中 ⇒ 系统<b>不猜</b>。<br>⭐ 补完关键词后请<b>再抓一次</b> —— 那几条这次会自动命中并写入（集采是<b>逐条写入</b>，已落的不受影响）。`
      : `付款项目名落在<b>壳</b>上，而「单据名称」没能在该壳下的小微关键词里命中 ⇒ 系统<b>不猜</b>。<br>⭐ 补完关键词后请<b>再抓一次</b> —— 本批数据<b>不暂存</b>，那次会自动命中并写入。`}</div>${box}`,
    footer: `<button class="btn" data-act="closeModal">关闭</button>`,
  });
}

/* ⭐ `TAIL-39`：**兜底前先跑一次 i8 仓库名单**（用户 2026-09-18 口述裁定）。
   为什么：兜底 = 手填仓库名新建具体小微 ⇒ 用户**凭猜**填 ⇒ 留下与 i8 不符的**假档案行**；
   日后 i8 真建了这个仓库 ⇒ 系统**再建一行**（重复）。所以**建之前先问 i8**。
   ⚠️ 判定**全在后端**（`domain.i8_warehouse_lookup` ＋ `/api/m03/notices/warehouse-check`）；
      壳里只做三件事：**问**（按钮）· **显示**（就地结果）· **拦**（没查过 / 没命中没确认 ⇒ 不许提交）。
   ⚠️ **四态要分清**：`found` 真 = 名单里有 ｜ `found` 假且**不降级** = 名单里确实没有 ｜ `degraded` = **没取到**
      （⛔ 「没取到」**不等于**「没有」—— 文案必须分开，别把取数失败说成名单里没有）。 */
let OWN_WH = {};      /* `{条目下标: {found, owners, total, degraded, message}}` —— 本次查的结果 */
let OWN_CTX = {};     /* `{条目下标: 该条上写的壳全名}` —— 用来提醒"这条仓库其实属于另一个壳" */

async function ownWhCheck(i) {
  const el = $('#ownNewName_' + i);
  const name = String((el && el.value) || '').trim();
  if (!name) return toast('先填<b>仓库名</b>，再查 i8 名单');
  /* ⚠️ `D9`：查名单**要登录 i8**（可能**强踢**在线用户）⇒ 先二次确认，确认之后才发请求。 */
  modal({
    title: `查 i8 仓库名单 · ${esc(name)}`,
    body: `<div class="tip dg" style="margin:0 0 calc(10px * var(--fscale))"><b>⚠️ 这一步会登录 i8，可能<b>强制踢掉</b>该账号其它在线会话</b>（不会自动重试登录）—— 若同事正在用 i8，请先<b>择时</b>。</div>
      <div class="tip" style="margin:0">查 i8 仓库名单里<b>有没有</b>「${esc(name)}」、以及它<b>挂在哪个项目全名</b>下 —— 用来判断该走「选已有小微」还是「只能手填」。⚠️ <b>只查不写入</b>。</div>`,
    footer: `<button class="btn" data-act="closeModal">取消</button>
      <button class="btn pri" data-act="ownWhOk" data-i="${i}">确认查询（会顶号）</button>`,
  });
}

async function ownWhOk(i) {
  const el = $('#ownNewName_' + i);
  const name = String((el && el.value) || '').trim();
  closeModal();
  let r = null;
  try {
    r = await API.whCheck({warehouse_name: name, allow_kick: true});
  } catch (e) {
    return toast(`⚠️ 查名单失败：${esc(String((e && e.message) || e))}`, 8000);
  }
  OWN_WH[i] = r;
  const host = $('#ownWhRes_' + i);
  if (host) {
    if (r.degraded) {
      host.innerHTML = `⚠️ <b>没取到名单</b>（⛔ 这不等于「名单里没有」）：${esc(r.message || '')}`
        + `<br><label><input type="checkbox" id="ownWhForce_${i}"> <b>我知道这是「没取到」、不是「名单里没有」</b>，仍要建档</label>`;
    } else if (r.found) {
      const inside = (r.owners || []).some(o => o === (OWN_CTX[i] || ''));
      host.innerHTML = `✅ i8 名单里<b>有</b>「${esc(name)}」，挂在 <b>${esc((r.owners || []).join('、') || '（没写所属项目）')}</b> 下（名单 ${r.total} 条）`
        + (inside ? ' ✓ <b>与本条壳一致</b>' : '<br>⚠️ <b>它挂的项目全名与条目上的壳不一致</b> —— 先确认是不是同一个壳，别建错行');
    } else {
      host.innerHTML = `⚠️ i8 名单里<b>没有</b>「${esc(name)}」（名单 ${r.total} 条）—— 将来 i8 建了这个仓库，系统<b>会再建一行</b>。`
        + `<br><label><input type="checkbox" id="ownWhForce_${i}"> <b>我确认现在就要按这个名字建</b>（将来会重复）</label>`;
    }
  }
  return null;
}

/* 提交：补词到小微（后端校验「词须出现在单据名里」＋ 去重追加；本层只转发） */
async function ownAssignSubmit(i, pid) {
  const it = (await ownItems())[i];
  if (!it) return toast('清单已过期，请重新抓取');   /* ⚠️ 清单按**当前档案**现算 ⇒ 索引可能已变 */
  let body;
  if (pid === '__new') {
    /* ⭐ `TAIL-39`：**兜底前必须先跑这一环** —— 没查过 / 查了没命中又没确认 ⇒ 当场拦下（⛔ 不静默建档）。
       ⚠️ 拦在**壳侧**是"提醒到位"，后端不为此加硬门槛（它不知道用户看没看见）—— 台账里写明这个取舍。 */
    const seen = OWN_WH[i];
    if (!seen) {
      return toast('先点「<b>① 先查 i8 仓库名单</b>」—— 不查就建 = 凭猜填仓库名，会留下与 i8 不符的<b>假档案行</b>', 9000);
    }
    if (!seen.found || seen.degraded) {
      const ck = $('#ownWhForce_' + i);
      if (!ck || !ck.checked) {
        return toast(seen.degraded
          ? '⚠️ <b>没取到名单</b>（⛔ 这不等于「名单里没有」）—— 仍要按这个名字建，请先在上面方框里<b>确认</b>'
          : '⚠️ <b>i8 名单里没有</b>这个仓库 —— 将来 i8 建了，系统会<b>再建一行</b>；仍要现在建，请先在上面方框里<b>确认</b>', 9500);
      }
    }
    body = {
      doc_name: it.doc_name,
      keyword: (($('#ownNewKw_' + i) || {}).value || ''),
      shell_id: it.shell_id,
      new_small_name: (($('#ownNewName_' + i) || {}).value || ''),
    };
  } else {
    body = {
      doc_name: it.doc_name,
      keyword: (($('#ownKw_' + i + '_' + pid) || {}).value || ''),
      small_id: Number(pid),
    };
  }
  let r;
  try { r = await API.assignOwnership(body); }
  catch (e) { return toast(`⚠️ 提交失败：${esc(String((e && e.message) || e))}`, 8000); }
  if (!r.ok) return toast(`<b>没补上</b>：${esc(r.message)}`, 8000);
  await reloadProjects();
  closeModal();
  toast(esc(r.message), 8000);
}

/* ============================================================ MOD-08 库存单据（`TAIL-27` 第 5 页）
   ⭐ **接后端**：`IVs`（单据行）/ `ADs`（调整单）由 `reloadInv()` 从 `/api/m08/inventory` 填。
   ⚠️ **字段转形只在这里做**（后端出**域内规范名** `doc_no`…，原型用**短名** `docNo`…）——
      两套命名必须在**唯一出口**对齐；错一个键就是**静默失配**（`iv.amt` 恒 undefined
      ⇒ 合计恒 0、状态列恒空，**而且不报错** —— `m01` 的状态枚举就踩过同一个坑）。
   ⚠️ 金额一律过 `N0()`：后端出 JSON number，但 null / 空串 ⇒ 0（否则 `+=` 变成字符串拼接）。
   ⚠️ `id` 一律 `String()`：原型的 `data-*` 都是**字符串**，`===` 比较不转会**静默找不到行**
      （同 `m03` 的教训）。 */
const N0 = v => { const n = Number(v); return Number.isFinite(n) ? n : 0; };

function adaptInv(r) {
  return {
    id: String(r.id),
    docNo: r.doc_no || '', seq: r.seq || '', dir: r.direction || '',
    mat: r.material || '', spec: r.spec || '', unit: r.unit || '',
    qty: N0(r.qty), px: N0(r.price_excl), pi: N0(r.price_incl), amt: N0(r.amount),
    tax: N0(r.tax_total), biz: r.biz_type || '', cp: r.vendor || '',
    dd: r.doc_date || '', ad: r.audit_date || '',
    wbs: r.wbs_name || '', cbs: r.cbs_name || '',
    wh: r.warehouse || '', pf: r.project_full_name || '',
    c5: r.c5 || '',                       /* 材料 5 类别（后端归集，⛔ 前端不重写规则） */
  };
}
function adaptAdj(a) {
  return {
    id: String(a.id), ivid: String(a.row_id),
    newAmt: N0(a.amount), remark: a.remark || '', op: a.operator || '',
    time: a.changed_at || '',
    /* ⚠️ `trail` 必须是**对象数组**：`adjDlg` 里按 `x.field / x.before / x.after` 取值
       （原型演示数据给的是数组数组 ⇒ 那张卡会渲染出一排 `undefined` —— **原型自身缺陷**，
        适配层转成正确形态绕过，⛔ 不改 `V.m08`）。 */
    trail: [{ field: '金额', before: N0(a.before_amount), after: N0(a.amount) }],
  };
}

/* 重拉库存单据 + 调整单（**写动作后一律走它** ⇒ 以后端为准，⛔ 前端不自己造状态）。
   ⭐ 顺带重算 `PROC_PJS` / `procPj`（见上面「加载时求值」那条注释）与失效的项目筛选值。 */
async function reloadInv() {
  const d = await API.m08Inventory();
  IVs = (d.rows || []).map(adaptInv);
  ADs = (d.adjustments || []).map(adaptAdj);
  if (invWhs.length) {          /* 筛选里失效的项目名清掉（原地改，外部持有的是数组引用） */
    const kept = invWhs.filter(k => IVs.some(iv=>iv.wh===k));
    if (kept.length !== invWhs.length) { invWhs.length = 0; kept.forEach(k => invWhs.push(k)); }
  }
  render();
}

/* 写动作统一走这里：**失败把后端原因原样给用户**（不吞、不换句话），成功/失败都**回后端真实状态**。 */
async function ivAct(fn, okMsg) {
  try {
    const r = await fn();
    await reloadInv();
    toast(typeof okMsg === 'function' ? okMsg(r) : okMsg);
    return r;
  } catch (e) {
    await reloadInv();                      /* 失败也重拉：弹窗里的旧值不能留在页面上 */
    toast(`<b>没能保存</b>：${esc(String((e && e.message) || e))}`, 7000);
    return null;
  }
}

/* 抓库存单据（`API-03`）—— ⚠️ **会登录 i8 并强踢在线用户**（D9 的二次确认由抓取弹窗承担）。 */
async function ivFetchBackend(month) {
  closeModal();
  try {
    const r = await API.m08Fetch(month);
    if (r.ok === false) {                    /* 降级：i8 侧失败 ⇒ 走手动 Excel 导入（§3.6） */
      await reloadInv();
      await reloadM02IfOn();                 /* ⚠️ 见 `reloadM02IfOn`：降级**也写了一条执行记录**（`failed`） */
      return fetchResultModal(`抓取没能完成 · 收发结存`,
        `已<b>降级为手动导入</b>：${esc(r.message || '')}<br>`
        + `<span class="mut sm">${IMP_DEGRADE_TIP}</span>`);
    }
    await reloadInv();
    await reloadM02IfOn();                   /* ⭐ 刚写的那条记录要立刻在记录卡上看到 */
    const st = r.stats || {};
    fetchResultModal(`抓取结果 · 库存单据明细`,
      `已按 <b>${esc(month)}</b> 抓取库存单据明细：<br>`
      + `本次插入 <b>${st.inserted || 0}</b> · 更新 <b>${st.updated || 0}</b>`
      + ` · i8 侧已删 <b>${st.deleted || 0}</b>`
      + `${st.kept_with_adjustment ? ` · <b>保留调整单 ${st.kept_with_adjustment}</b>` : ''}`
      + `<br><span class="mut sm">调整单独立存储、不被导入覆盖</span>`);
  } catch (e) {
    await reloadInv();
    await reloadM02IfOn();                   /* ⚠️ 抛了也可能已落一条失败记录 ⇒ 一并刷（不刷只会显示旧的） */
    fetchResultModal(`抓取没能完成`,
      `<b style="color:var(--wn)">${esc(String((e && e.message) || e))}</b><br>`
      + `<span class="mut sm">${I8_LOGIN_TIP}</span>`);
  }
}

/* ============ MOD-07 收发结存与月度会大表（前端壳接线 · `TAIL-27`）============
   ⚠️ 后端金额出**字符串**（`numeric(18,2)` 精度保护）⇒ 这里**一律过 `N0()`**：
      不过的话壳里的求和会变成**字符串拼接**（`'100.00' + '1.00'`），而且**不报错**。 */
let MAT_OK = false;            /* 「主材累计（含税）」取数口是否已接入（后端 `mat_available`） */
/* ⭐ `A5`（2026-09-29 逐页）：大表**空态**那句「为什么是空的」—— ⚠️ **主人是后端**
   （`/api/m07/big` 的 `empty_text`，源自 `big_domain.empty_text`）⇒ 壳里⛔ 不自己编一句。
   （它此前是后端的**死代码**，而壳那边 0 行时只 `return ''` ⇒ 只剩三级表头的大空表。） */
let BIG_EMPTY = '';
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

/* 结余：后端 `{类别: {仓库: 金额字符串}}` → 壳的 `BAL_EX[类别][仓库] = 数字`。
   ⚠️ 必须过 `N0()`（后端金额出**字符串**，不过就会让 `String(v)` 显示成一个带引号的串）；
   ⛔ **不给未录入补 0** —— 未录入的键**不出现**（域值 `null`；`0` 是**合法录入值**，两者不同）。 */
function adaptBalances(balances) {
  const out = {};
  Object.keys(balances || {}).forEach(kind => {
    const byWh = balances[kind] || {};
    out[kind] = {};
    Object.keys(byWh).forEach(wh => {
      const v = byWh[wh];
      if (v == null || v === '') return;                 /* 空 ⇒ 未录入（不建键） */
      out[kind][wh] = N0(v);
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
  /* 「结余」手工录入值（唯一取数出口 = 后端 `balances`）—— 同法**原地清空再填**（保对象引用）。 */
  const bal = adaptBalances(ex && ex.balances);
  Object.keys(BAL_EX).forEach(k => delete BAL_EX[k]);
  Object.keys(bal).forEach(k => { BAL_EX[k] = bal[k]; });
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
    BIG_EMPTY = String(bg.empty_text || '');
  }
  /* ⚠️ 大表月份 = `bjMonth(-1)`（原型写死「北京时间上月」，§9.2 材料报表类）——
     与后端 `default_month()` 同口径；后端 `selected` 已是「大表自己的顺序」，不需前端重排。
     ⛔ **不要在这里给 `BIGSET` 兜底「空了就填全部候选」**：后端的选择项目有**标记行**区分
        「从未选择项目」（⇒ 后端已给全部候选）与「选了空」（⇒ 表里 0 个项目）——
        前端兜底会把用户的「清空」**悄悄改回全部候选**（假成功，且不报错）。 */
  render();
}

/* 写动作统一外壳：**失败把后端原因原样给用户**（不吞、不换句话），成败都回后端真实状态。 */
async function bgFailed(name, r) {
  await reloadM07();
  toast(`<b>${esc(name)}没能保存</b>：${esc((r && r.message) || '系统没有给出原因，请重试')}`, 7000);
}

/* 抓收发结存（`API-02`）—— ⚠️ **会登录 i8 并强踢在线用户**（D9 的二次确认由抓取弹窗承担）。 */
async function whFetchBackend(month) {
  closeModal();
  try {
    const r = await API.m07Fetch(month);
    if (r.ok === false) {                    /* 降级：i8 侧失败 ⇒ 走手动 Excel 导入（§3.6） */
      await reloadM07();
      await reloadM02IfOn();                 /* ⚠️ 见 `reloadM02IfOn`：降级**也写了一条执行记录**（`failed`） */
      return fetchResultModal(`抓取没能完成 · 库存单据明细`,
        `已<b>降级为手动导入</b>：${esc(r.message || '')}<br>`
        + `<span class="mut sm">${IMP_DEGRADE_TIP}</span>`);
    }
    await reloadM07();
    await reloadM02IfOn();                   /* ⭐ 刚写的那条记录要立刻在记录卡上看到 */
    /* ⭐ 链路 B 的回执**必须露出来**（`TAIL-30`-③ 补的缺口）：原先这一路只报条数，
       回包里的 `recovery`（扶正了谁 / 新建了谁 / **还有哪几条要人指认**）**根本没露** ⇒
       用户在壳上抓完收发结存，**看不到"待人工 N 条"**，也就不知道该去 `m01` 处理。 */
    try { await reloadPending(); } catch (_) { /* 清单这一路失败 ⇒ 下面的回执里如实说明 */ }
    const st = r.stats || {};
    let msg = `已按 <b>${esc(month)}</b> 抓取收发结存：解析 <b>${r.rows || 0}</b> 行 —— `
      + `新增 <b>${st.inserted || 0}</b> · 更新 <b>${st.updated || 0}</b> · 删除 <b>${st.deleted || 0}</b>`;
    const rc = r.recovery || {};
    const pro = (rc.promoted || []).length, cre = (rc.created || []).length;
    if (pro || cre) msg += `<br>自动扶正 <b>${pro}</b> 行 · 自动建档 <b>${cre}</b> 行`
      + (pro ? `<br><span class="mut sm">${esc((rc.promoted || []).join('；'))}</span>` : '');
    const pend = rc.unresolved_items || [];
    if (pend.length) {
      msg += `<br>⚠️ <b>待人工 ${pend.length} 条</b>：`
        + esc(pend.map(x => `${x.warehouse_name}：${x.reason}`).join('；'))
        + `<br>⇒ <span class="link" data-act="go" data-k="m01" tabindex="0" role="button">去项目档案指认到哪一行 →</span>`;
    }
    if (rc.degraded && rc.message) msg += `<br>⚠️ ${esc(rc.message)}`;
    fetchResultModal(`抓取结果 · 收发结存`,
      msg);
  } catch (e) {
    await reloadM07();
    await reloadM02IfOn();                   /* ⚠️ 抛了也可能已落一条失败记录 ⇒ 一并刷（不刷只会显示旧的） */
    fetchResultModal(`抓取没能完成`,
      `<b style="color:var(--wn)">${esc(String((e && e.message) || e))}</b><br>`
      + `<span class="mut sm">${I8_LOGIN_TIP}</span>`);
  }
}

/* 机械 6 列（**旁路表**的手录值）—— ⚠️ 不 `render()`：由 `boot()` 后面的 `reloadM05()` 统一渲染。 */
/* 机械 6 列的**列名兜底**（真值由 `reloadMech()` 从 `/api/m06/mech` 的 `columns` 覆盖 ——
   ⚠️ 列名的**唯一主人 = 后端** `domain.MECH_COLUMNS`，⛔ 前端不硬编码）。 */
const MECH_LABELS = ['租分公司设备', '内租设备', '外租零租含税', '外租包月含税',
  '外租零租不含税', '外租包月不含税'];

/* 规则配置（`MOD-14`）—— 剔除规则读后端（**唯一主人在库**）。
   ⚠️ 「加载时算出来的派生量」一律在**本函数里重算**（本项目反复踩的坑：写在数据层 ⇒ 静默空）。 */
async function reloadM14() {
  const d = await API.m14Rules();
  RULE_RAW = d.rules || [];
  RULE_KINDS = d.kinds || [];
  RULE_SRC = d.source_label || '';
  /* ⭐ `TAIL-96` 集采项目剔除名单（页面在 M14、数据主人在集采域）
     ⚠️ 挂 `window` 而不是模块级 `let` —— 视图代码在 `index.html`，跨件引用走全局最稳（本壳非严格模式）。 */
  const dj = await API.m14JcIgnore();
  window.JCI_ALL = dj.items || [];
  /* ⚠️ 后端给 `kind_label`（**展示名**）—— 本页只展示，故用展示名；
     写动作要的是 `kind`（内部值）⇒ 从 `RULE_RAW[i]` 取，别从展示三元组反推。 */
  RULE_EX = RULE_RAW.map(r => [r.kind_label, r.values, r.meaning]);
}

/* 用户管理（`MOD-15` · §1.5）—— 读 `/api/m15/users`（**列表 ＋ 当前登录用户 ＋ 三态计数**）。
   ⚠️ 与已接线的其它页同一个形态：**空数组起手、boot 时用 API 原地填**。
   ⛔ 别整支换引用（`USERS` 是 `const`，且 `V.m15` 与自检回滚都按**原地**处理）。 */
function adaptUser(x) {
  return {
    /* ⚠️⚠️ **`id` 必须 `String()`** —— 这是本文件**全仓适配器的统一纪律**
       （看 `adaptProject`：`id: String(p.id)`，那里也写了注释）。
       原因：壳里到处是 `x.id === t.dataset.id` 的**同值比较**，而 `dataset.id` **永远是字符串**；
       后端出的 `id` 是**数字** ⇒ 不转则 `===` **永远不成立** ⇒
       动作**静默什么都不做**（⭐ 2026-09-20 片 4b 就是这么被抓到的：点「删除」毫无反应）。
       ⛔ 别图省事写 `id: x.id` —— 那不会报错，只会"按钮点了没反应"。 */
    id: String(x.id),
    acc: x.account,
    name: x.name,
    role: x.role,
    /* ⭐ 后端出的是**三态**（在用 / 已停用 / **已删除**）—— 与 `V.m15` 里用的词**完全一致**
       ⇒ 壳这边**不做映射**（⛔ 一映射就多一处"哪些值算已删"的判定，必漂）。 */
    status: x.state,
    /* 最近登录（`§1.5.1` 补口径）：**空串 = 从未登录过**（⛔ 不是"数据没取到"）。
       ⚠️ 别拿建号时间或 `—` 冒充 —— `V.m15` 对空串显示「从未登录」，那才是实话。 */
    last: x.last_login_at || '',
    /* ⛔ **列表不带密码**：要看密码走「查看密码」动作（单独端点、指名要哪一个）。
       ⇒ 这里先给空串；`V.m15` 的「改密」按钮本来就不读它。 */
    pwd: '',
    /* ⭐ `§7.8` i8 绑定（每人一份）：列表**只出账号名、不出密码**（同脱敏口径）⇒
       弹窗里那个密码框是**空的**，提交时"空"表示**不改**（见 `ACT.userPwdOk`）。 */
    i8: x.i8_user || '',
  };
}

/* 「当前登录用户」（`CUR`）—— ⭐ **唯一赋值处**：`/api/m15/users` 的 `me`。
   ⚠️ 为什么单列成两个函数（而不是只在 `reloadM15` 里赋值）：
      `boot()` 要**首屏**就拿到真身份 —— 顶栏那句从第一帧起就得说真话（⛔ 不许有"假名字占位"），
      而 `m15` 页另需账号列表 ⇒ 两处**共用同一个赋值体**（⛔ 各写一份 = 迟早只改一处）。
   ⚠️ 一律**逐字段赋值**、⛔ 不换 `CUR` 的引用 —— 本文件的既有教训（L536 那条注释）：
      自检回滚 / 刷新会整体替换 `USERS` 的内容，任何"指向 `USERS[i]` 的引用"都会失效。 */
function applyWho(d) {
  const me = (d && d.me) || {};
  /* ⭐ 身份状态（顶栏据此说不同的话，见 `index.html` 里 `WHO_STATE` 的注释）——
     `'none'` = **后端答了、但没有身份**；取数失败时本函数压根不跑 ⇒ 保持 `''`（"未取到"）。 */
  WHO_STATE = me.id ? 'in' : 'none';
  CUR.id = String(me.id);   /* ⚠️ `V.m15` 里是 `u.id===CUR.id` ⇒ 两边都必须是**字符串** */
  CUR.acc = me.account || '';
  CUR.name = me.name || '';
  CUR.role = me.role || '';
  /* ⭐⭐ 2026-09-27（`TAIL-129` 界面大小）：**在这个启动就一定会跑的地方**应用界面偏好 ——
     `/api/m15/users` 是 `boot()` 里的"当前登录用户"那一路 ⇒ 界面大小**首屏就生效**，
     ⛔ 不必为它新开一路请求（也⛔ 别只挂在 `reloadTheme` 上 —— 那一路上次就是这么把主题坑了的：
     只有进过"系统设置"页才生效）。⚠️ 取不到（`me` 为空 / 字段缺失）⇒ 什么都不做 = **保持标准档** ✓ */
  if (me.ui_scale_css) { CUR_UI_SCALE = String(me.ui_scale || ''); applyUiScale(me.ui_scale_css); }
}
async function reloadWho() { applyWho(await API.users()); }

async function reloadM15() {
  const d = await API.users();
  USERS.splice(0, USERS.length, ...((d.users || []).map(adaptUser)));
  applyWho(d);                 /* ⭐ 身份只在这一个地方赋值（`boot` 与 `m15` 共用） */
}

/* ⭐⭐ **回收站**（2026-09-21 用户裁定：「已删账号**从主列表移出**、单独可见可恢复」）。
   ⚠️⚠️ 为什么是"**渲染后搬 DOM**"而不是"改 `V.m15` 的模板"：
     `V.m15` 是**原型切片**（`ui_parity` 的 `U1` 要它与 `demo/` 原型**逐行一致**）⇒ 往切片里加一块
     "回收站"会与原型**不一致**；而**原型是规格**（`D18`）⇒ 要加就得**先在原型加块、壳再照抄**。
     ⭐ 2026-09-25 用户裁定「登记簿**可以变长**」⇒ 登记不再是拦路虎；**但"原型是规格"没变**，
     所以本期仍走搬 DOM；哪天真要做进切片，**先回原型加块**（模板：`TAIL-96` 集采剔除名单那块）。
     ⭐ 而原型里"已删除行"的**唯一特征**就是操作列那个 `userRestore` 按钮
     （切片：`u.status==='已删除' ? 恢复按钮 : 改密/看密码/停用/删除`）⇒ **拿它当选择器天然对齐**；
     行是**原样搬过去**的（⛔ 不重写模板、⛔ 不在壳里再造一份"哪些算已删"的判据），
     恢复按钮继续走**同一支** `ACT.userRestore`（⛔ 不新开动作）。
   ⚠️⚠️ **计数不受影响，因为 `USERS` 仍是全量**：`V.m15` 的「在用 / 停用 / 已删除」三个数都从
      `USERS` 算（`reloadM15` 照旧灌**全部**账号）⇒ ⛔ **别**为了"主列表不显示"去过滤 `USERS` ——
      那会让标题里那句「已删除 N」变成 **0（假话）**，而回收站也就永远空了。
   ⚠️ 幂等：`render()` 每次重建 `#view` ⇒ 本函数每次重跑；先删上一块，⛔ 不叠加。
   ⚠️ 挂点 `BIND[VIEW]`（`render()` 里 `innerHTML` 之后调用）—— 那是壳**本来就有、一直没人用**的
      渲染后钩子；⛔ 别把这段塞进 `render()` 本体（那会让"渲染"与"某一页的整理"混在一处）。 */
function m15Trash() {
  const view = document.querySelector('#view');
  if (!view) return;
  const stale = view.querySelector('#m15Trash');
  if (stale) stale.remove();
  const rows = [...view.querySelectorAll('[data-act="userRestore"]')].map(b => b.closest('tr'));
  if (!rows.length) return;    /* 没有已删账号 ⇒ **不占地方**（标题那句「已删除 0」已经说了实话） */
  const card = document.createElement('div');
  card.id = 'm15Trash';
  card.className = 'card';
  card.innerHTML = `<h4>回收站 · 已删除账号
    <span class="sp"><span class="mut sm">删除是<b>软删</b>：账号名保留、数据不销毁 ⇒ 历史留痕里的人名仍认得出来；恢复后回到它<b>原来的状态</b>（停用过的仍是「已停用」）</span></span></h4>
    <div class="tw"><table class="dt"><thead><tr><th>登录账号</th><th>姓名</th><th>角色</th><th>状态</th><th>最近登录</th><th>操作</th></tr></thead><tbody></tbody></table></div>`;
  const tb = card.querySelector('tbody');
  rows.forEach(tr => tb.appendChild(tr));                  /* ⭐ 原样搬（含恢复按钮） */
  const listCard = view.querySelector('.card');            /* 账号列表卡 ⇒ 插在它后面 */
  if (listCard && listCard.parentNode) listCard.parentNode.insertBefore(card, listCard.nextSibling);
  else view.appendChild(card);
}
BIND.m15 = m15Trash;

/* ⭐ 主题（`ACC-UI-THEME-001/001-06`）：**可选清单 ＋ 我这个账号当前用哪套**。
   ⚠️⚠️ 它必须是**自己的一路**（`LOADERS['外观主题']`），⛔ 不能塞在 `reloadM15` 里 ——
      切换器住 `V.set`（系统设置）而**那一页从不进** `reloadM15` ⇒ 清单恒为空 ⇒
      下拉里一个选项都没有、`themeSet` 写回**空串**（症状 = "换主题没用"，
      而且**全程不报错**；2026-09-21 实测踩到，正是用户报的那个毛病）。
   ⚠️ 取不到**不该让整页报错** ⇒ 清单空着即可（`V.set` 会写明"清单取不到"），⛔ 别把异常抛上去。 */
/* ⭐⭐ 2026-09-27（`TAIL-129` 界面大小 · 用户裁定走**方案 B**：字号＋间距走 CSS 变量）：
   `UI_SCALES` = **档位清单**（`[{key,label,css}]`，真源在后端 `domain.UI_SCALES` ⇒ 壳⛔ 不写死映射）、
   `CUR_UI_SCALE` = 我当前哪一档（键）。两者都由 `/api/m15/theme` 填（与主题同源最省事）。 */
let UI_SCALES = [], CUR_UI_SCALE = '';

/* 应用**界面大小**档：把倍率写到 `<html>` 的内联 `--fscale` 上。
   ⚠️ 用**内联 style**、不是改样式表：① 优先级最高 ⇒ ⛔ 不用碰 `theme.css`（那里的 `--fs` 是
      **字体族**，两个名字只差一个字母，别混）；② 换档**立即生效、不刷新页面**
      （与主题同一条纪律 —— 刷新会把用户扔回看板，那是 2026-09-21 报过的毛病）。
   ⚠️ 取不到值 ⇒ 回 `1`（标准档）：⛔ 别回空串 —— 空串会让 `calc(… * var(--fscale))` **整条失效**
      （字号回落成浏览器默认 = 界面全乱）。 */
function applyUiScale(css) {
  const v = String(css || '').trim() || '1';
  document.documentElement.style.setProperty('--fscale', v);
}

async function reloadTheme() {
  try {
    const th = await API.m15Theme();
    THEMES_LIST.splice(0, THEMES_LIST.length, ...((th.themes || [])));
    /* ⭐ 每套主题的**配色标本**（`{name,pri,bg,sf,bd,tx,on}`）—— 由后端从唯一真源解析出来，
       ⛔ 壳里**一个色值都不写**（写死就是第二份真源，`test_theme.py` 会红）。 */
    THEME_PALETTE.splice(0, THEME_PALETTE.length, ...((th.palette || [])));
    CUR_THEME = th.theme || th.default || '';
    /* ⭐ 界面大小（`TAIL-129`）：档位清单 ＋ "我当前哪一档" —— ⚠️ 清单的真源在**后端**
       （`domain.UI_SCALES`），壳只负责画按钮；`css` 是喂 `--fscale` 的倍率字符串。
       ⚠️ 进这一路时**顺手应用一次**（保证"没走过启动那一路"或"换过账号"时也对）。 */
    UI_SCALES.splice(0, UI_SCALES.length, ...((th.scales || [])));
    CUR_UI_SCALE = String(th.ui_scale || '');
    const cur = UI_SCALES.find(s => s.key === CUR_UI_SCALE);
    if (cur) applyUiScale(cur.css);
  } catch (e) { /* 见上 */ }
}

async function reloadMech() {
  const d = await API.m06Mech();
  MACH6 = d.mech || {};
  /* ⭐⭐ 2026-09-26（`TAIL-107`）：每个（项目 × 核算月）落在**哪一段** —— 后端给（`sections`）。
     用途 = 把"**历史段不许手录**"在界面上也说清（守则 §5.5：不能做的要置灰并说明原因）。
     ⚠️ 判断**只认后端**（`domain.section_of`）：⛔ 壳里不许自己拿截止月比大小（那是第二份口径）。 */
  MECH_SECTIONS = d.sections || {};
  if (d.columns && d.columns.length) {
    MECH_LABELS.length = 0;
    d.columns.forEach(x => MECH_LABELS.push(x));
  }
}

async function reloadProc() {
  const d = await API.m06Matrix();
  if (d.ok === false) throw errHuman(d.message || '过程资料没能读取，请重试。', 'm06 matrix rejected');
  PROC_MATRIX = d.matrices || {};
  PROC_PJS = d.projects || [];
  if (!PROC_PJS.includes(procPj)) procPj = PROC_PJS[0] || '';
}

/* ⭐⭐ `TAIL-38`：「录机械费」入口 —— 原型 `V.m06` **没画**这个入口（机械 6 列在原型里是**只读**的），
   而服务端页 `/m06` 才有 PRG 写入口 ⇒ 壳里**没法录**（机械欠款会长期停在 0）。按 §5.2.5 ③ 自行设计。
   ⛔ **不改 `V.m06` 一行**：走原型自己的 `BIND` 钩子（渲染后往页首注入一条工具栏）——
      判定与落库全在后端（`POST /api/m06/mech`）。⚠️ 机械值是**旁路载体**，重抓 / 重导都不覆盖它。 */
BIND.m06 = function () {
  const host = document.querySelector('#view');
  if (!host) return;
  /* ⭐⭐ 2026-09-29（用户裁定 `A` · `TAIL-173`）：**摘掉卡头那枚「导出 Excel」（朴素那份）** —— 它
     **永远只会说"这一页还没有导出功能"**（`EXP_ROUTES` 里没有「过程资料」），而同一张卡头里已经有
     **真入口**「批量导出（先选项目）…」⇒ 两枚导出并排、其中一枚点了必然空转 = 让用户以为坏了
     （守则 §4.4：相似元素不制造歧义）。
     ⚠️ **走 BIND 在渲染后摘除，⛔ 不改 `V.m06` 那一行**（同 `BIND.m11` 改导出按钮的做法）：
        切片是**逐行对位**核对的 ⇒ 删一行会让它后面**所有行**报漂移（`A4` 那次 101 条的教训）；
        而且 `tests/test_tail04_pages.py` 把 `data-act="exp" data-t=…` 的**名单钉在源码上** ⇒ 删源码必红。
     ⚠️ **兜底那句不许删**（它在 `EXP_ROUTES` 上面的分支里）：`m08` 朴素那份 / 已取消的差异清单仍在用它。
     ⚠️ **幂等**：`render()` 每次重画 `#view` ⇒ 本钩子每次都要重摘一遍。 */
  const naive = host.querySelector('[data-act="exp"][data-t="过程资料"]');
  if (naive) naive.remove();
  if (document.getElementById('mechEntry')) return;
  const bar = document.createElement('div');
  bar.id = 'mechEntry';
  /* ⭐ `A4`（2026-09-29 逐页）：改走**变体类** —— 原先这里把 `.fbar` 的声明在 JS 里**又写了一遍**
     （`border` / `border-radius` / `margin-bottom`），而那个 `margin-bottom:10px` **漏了 `--fscale`**
     ⇒ 用户把「界面大小」调大时**这一处不跟着变**（守则 §5.11：漏一处 = 半成品相）。
     ⚠️ `.fbar.plate`（`index.html` 样式块里那四个变体类之一）的声明与它**逐像素等价**、只差那个倍率。 */
  bar.className = 'fbar plate';
  bar.innerHTML = '<div class="fi"><label>机械费手录</label>'
    + '</div>'
    + '<button class="btn pri" data-act="mechOpen">录机械费</button>';
  host.prepend(bar);
};

/* ⭐⭐ `TAIL-185`（`A` 案 · 2026-09-29 **用户裁定**）：**摘掉 `m08` 卡头那枚「点了必然空转」的朴素导出**。
   `m08` 卡头并排两枚导出：「导出 Excel」（朴素 · `data-act="exp"` · 走 `EXP_ROUTES` 兜底 ⇒ 点了只会
   **如实说"这页还没有导出功能"**）＋「导出（含数据透视表）」（`expPivot` · **真下载**）。
   ⚠️ "点了必然空转"的那枚会让用户**以为坏了**（守则 §4.6：看不到的功能不留"点了报错"的入口）——
     同族先例：`m06` 那枚朴素导出已在 `TAIL-173`（同日 · 用户裁定 `A`）按同款摘掉。
   ⚠️ **为什么走 BIND 摘除、⛔ 不删切片那一行**：`V.m08` 是 `ui_parity` 的 `U1` 逐行对位原件（删一行 ⇒
      它后面**所有行**报漂移），而且 `tests/test_tail04_pages.py` 把 `data-act="exp" data-t=…` 的**名单
      钉在源码上**；"渲染后注入/摘除"正是本层（`BIND`）该干的活（同 `BIND.m06`）。
   ⚠️⚠️ **同批改了契约**：`ACC-INV-001/001-12` 的 claim 文字由「朴素导出与含透视那份**并存互不影响**」
      改成「卡头**只留真入口**（朴素那枚渲染后摘除）」—— ⛔ 别只改壳不改 claim（那正是 §4.1 的"说了不做"）；
      守卫同批改在 `tests/test_tail04_export.py`（`001-12`）。
   ⚠️ **幂等**：`render()` 每次重画 `#view` ⇒ 本钩子每次都要重摘一遍（同 `BIND.m06` 那条口径）。 */
BIND.m08 = function () {
  const host = document.querySelector('#view');
  if (!host) return;
  const naive = host.querySelector('[data-act="exp"][data-t="库存单据明细总表"]');
  if (naive) naive.remove();
};

/* ⭐ `TAIL-156`：**月份位移的唯一出口**（`m09` 批量录入用：默认那几行 / 「＋ 加一行」都靠它）。
   ⚠️ 只在壳里做**加减月份**这种纯算术；⛔ 不在这里判任何业务（判定一律后端）。 */
const ymAdd = (m, n) => {
  const [y, mm] = String(m || '').split('-').map(Number);
  const d = new Date(y, (mm || 1) - 1 + n, 1);
  return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0');
};

/* ⭐⭐ `TAIL-156` `P2`：`m09` 特殊费用的**月度批量录入**入口 —— 与 `BIND.m06`「录机械费」**同款**：
   走原型自己的 `BIND` 钩子往页首注入一条工具栏，⛔ **不改 `V.m09` 切片一行**（`D18`）。
   判定与落库全在后端（`POST /api/m09/fee/batch`，语义见 `mod09_fee.service.act_batch`）。 */
BIND.m09 = function () {
  const host = document.querySelector('#view');
  if (!host || document.getElementById('awfBatchEntry')) return;
  const bar = document.createElement('div');
  bar.id = 'awfBatchEntry';
  bar.className = 'fbar plate';   /* ⭐ 同 `BIND.m06`（`A4` 2026-09-29）：走变体类，⛔ 别在 JS 里重写声明 */
  bar.innerHTML = '<div class="fi"><label>特殊费用 · 按月批量录入（§5.5）</label>'
    + '<span class="mut sm">一屏把<b>好几个月</b>填完（列 = 本页这一份的项名 · 行数<b>可加减</b> · <b>核算期每行都能改</b>）</span></div>'
    + '<button class="btn pri" data-act="awfBatch">批量录入（按月）…</button>';
  host.prepend(bar);
};

/* ============================================================ ⭐⭐ 链路 B ·「待人工指认」（`TAIL-30`-③）
   **它是什么**：材料报表里出现**陌生仓库**，而它的全名在档案里命中 **≥2 条非壳行**时 ——
   系统**不猜**（决策 1 兜底），必须由人指明"这条真实仓库名该写到**哪一行**"。
   ⚠️ 链路 B 另外两类（命中 1 条占位行 ⇒ 扶正改名 · 命中壳 ⇒ 新建具体小微）是**系统自己做**的
      （抓取过程中无感完成）⇒ 本页的入口**只服务**"要人指认"这一类。

   **清单从哪来**：抓取回执里那句话`只出现一次`（页面一刷新就没了）⇒ 后端把它存进**那次抓取的
   运行记录**，这里从**最近一次材料侧抓取**（`setl` / `inv`）读回来（`GET /api/m01/promote-pending`）。
   ⚠️ 后端还会**逐条按当前档案现算**：已经解决的不再返回（⛔ 不摆着让人对着旧清单白干）。

   ⚠️⚠️ **前端不算任何判定**（D18）：候选行有哪些、哪几行是占位行、条目还成不成立，全由后端给；
      写入口一律传 `project_id`（铁律 5/6：⛔ 不用名字反查）。
   ⛔ **不改 `V.m01` 一行**：入口走原型自己的 `BIND` 钩子注入（同 `BIND.m06`）。 */
let PEND = [];          /* 待指认条目（含当前候选行） */
let PEND_SRC = null;    /* 清单来自哪一次抓取（如实告诉用户，⛔ 不装作"刚刚"） */
let PEND_ERR = '';      /* 这一路取数失败的原因（在页面上如实说明；⛔ 不静默成"本来就没有"） */
let PEND_DLG = null;    /* 当前打开的指认弹窗锁定哪一条（⛔ 不用下标：清单刷新后下标会错位） */
let ARCP = [];          /* 待人工建档条目（链路 A ③-b「≥2 个仓库」，含**当前候选仓库**） */
let ARCP_DROP = [];     /* ⭐ 被现算丢掉的那几条 ＋ 为什么/该去哪（`TAIL-190`：丢是对的，但⛔ 不许静默） */
let ARCP_SRC = null;    /* 清单来自哪一次同步（如实标来源，⛔ 不装作"刚刚"） */
let ARCP_ERR = '';      /* 这一路取数失败的原因（页面上如实说明；⛔ 不静默成"没有待办"） */
let ARCP_DLG = null;    /* 当前弹窗锁定哪一条（⛔ 不用下标：清单刷新后下标会错位） */

/* 后端那些说明串里用 `**…**` 标重点（给人看与进日志都方便）⇒ 显示前转成 `<b>`。
   ⚠️ **先 `esc` 再转**：模板串里的 HTML 一旦漏出去就是一个注入口子。 */
const em = s => esc(s).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>');

function adaptPend(x) {
  return {
    wh: x.warehouse_name || '',
    full: x.full_name || '',
    reason: x.reason || '',
    /* ⚠️ `id` 一律转字符串 —— 原型全站 `x.id===t.dataset.id` 都是**字符串同值比较** */
    candidates: (x.candidates || []).map(c => ({
      id: String(c.id), typeLabel: c.type_label || '', name: c.warehouse_name || '',
      disp: c.disp || '', status: c.status || '', phid: c.phid || '', ph: !!c.is_placeholder,
    })),
  };
}

async function reloadPending() {
  const d = await API.pjPromotePending();
  PEND = (d.items || []).map(adaptPend);
  PEND_SRC = d.source || null;
  PEND_ERR = '';
}

/* ⭐ `TAIL-45` · 链路 A ③-b：**待人工建档**清单 ——「只认最近一次成功同步」＋「逐条按当前档案现算」
   两件事都在后端做（`archive_pending.live_pending`），壳侧只转形与展示（⛔ 不在这儿重算一遍）。
   ⚠️ 与「待人工指认」（链路 B）是**两条链路、两个来源**：B 读**材料侧抓取**，A 读**名单同步**。 */
function adaptArch(it) {
  return {
    full: String(it.full_name || ''),
    phid: String(it.phid || ''),
    whs: (it.warehouses || []).map(String),            /* 能选的候选（i8 名单那条 − 已被占用的） */
    stored: (it.stored_warehouses || []).map(String),  /* 当时那份（留痕：看得见"少了谁"） */
    reason: String(it.reason || ''),
  };
}

async function reloadArchPend() {
  const d = await API.pjArchPend();
  ARCP = (d.items || []).map(adaptArch);
  /* ⭐ `TAIL-190`：丢掉的那几条（**连同为什么、该去哪**）后端已经算好并给了 ⇒ 壳侧只展示、⛔ 不重算 */
  ARCP_DROP = d.dropped_items || [];
  ARCP_SRC = d.source || null;
  ARCP_ERR = '';
}

/* m01 页首的入口 —— ⛔ 不动 `V.m01`；`render()` 画完再注入（同 `BIND.m06`）。
   ⚠️ **幂等**：先撤掉旧的那块再按当前清单重建（清单是异步来的，会重画多次）。 */
/* ============ MOD-02 i8 接入层（前端壳接线 · `TAIL-27`）============
   ⭐ **`V.m02` 一行不改**（原型切片一行不动是本仓铁律）：两张卡的内容都由本钩子在 `render()` 之后
      **就地纠正** ——
      · 「抓取结果回显」：那 6 行原先是**演示表达式**（`NO`/`WHs`/`IVs`/`JCs`/`PJs`，其中 `WHs`/`JCs`
        本身就是**演示数组** ⇒ 显示出来是假话）⇒ 换成**执行记录**里每类接口最近一次的结果；
      · 「抓取任务日志」：`tbody` 那 8 行是**硬编码演示行** ⇒ 换成真记录（时间 / 接口 / 结果 / 耗时）。
   ⚠️ 为什么要在这里做（而不是改切片）：切片是**逐行对位**核对的，删一行就会让后面**全部报漂移**；
      而 `BIND` 钩子正是本仓「渲染后注入」的既定位置（`BIND.m01` 那两张卡同款）。
   ⚠️ **幂等**：`render()` 会重画多次 ⇒ 每次重算、⛔ 不叠加。
   ⚠️ 卡片标题里那个「（模拟）」在切片里**已改准并登记**（`ui_parity_expected.txt` 的 `m02` 那行）——
      那是**一处**显式偏离，其余一律不动切片。 */
/* ============ MOD-03 · 打印那两个入口（前端壳接线 · `TAIL-46`）============
   ⭐ **为什么由钩子注入**：`V.m03` 切片里只有「批量打印」一个出口（那三件事原先全在旧页
   `mod03_notice/static/m03.html` 上）⇒ 给切片加按钮 = 登记漂移；而"渲染后注入"正是 `BIND` 的活。
   ⚠️ **幂等**（`render()` 会重画多次）：靠 `dataset.m03More` 打标，⛔ 不叠加。
   ⚠️ 保留别的 `BIND.m03`（若有）：先调旧的，再注入（⛔ 不覆盖）。 */
/* ============ MOD-11 · 集采台账的**页内工具条**（前端壳接线）============
   ⭐ **为什么由钩子注入**：切片里那排按钮（`jcFetch` / `jcAdd` / 批量标记…）生在"**不许搬**"的切片区
      ⇒ 给切片加按钮 = 登记漂移；"渲染后注入"正是 `BIND` 的活（同 `BIND.m03` 那两个入口）。
   ⚠️ **幂等**（`render()` 会重画多次）：靠 `dataset.m11Tools` 打标，⛔ 不叠加。
   ⚠️ **保留别的 `BIND.m11`**（那个管"全选 / 半选回显"）：先调旧的，再注入。
   ⚠️ 2026-09-23（`TAIL-75` 余项 · **用户裁定**）：这里原先**还注入一个「⬆ Excel 导入台账」按钮**
      ⇒ 已**连件删除**（导入只在启用初期用一次 ⇒ 只留通用面）。本钩子现在只剩 `M5-9` 的
      「隐藏贸易公司三列」（`hidBtn` 挂在同一个锚点后面）。 */
/* ⛔ `M5-8` 的 ② 预览弹窗（`jcImportShow`）与 ③ 结果回执（`jcImpResult`）已**连件删除**
   （`TAIL-75` 余项 · 2026-09-23 **用户裁定**：「导入只在启用初期用一次」⇒ **只留通用面**）。
   ⭐ 那两步现在是壳「**数据导入**」页的通用流程（`V.imp`：列映射 → 预览校验 → 确认落库），
   台账侧的匹配口径仍只有一份（后端 `import_service.match_and_apply`）。 */



const _BIND_M11_OLD = BIND.m11;
BIND.m11 = function () {
  if (typeof _BIND_M11_OLD === 'function') _BIND_M11_OLD();
  const host = document.querySelector('#view');
  if (!host) return;
  const anchor = host.querySelector('[data-act="jcFetch"]');
  if (!anchor || anchor.dataset.m11Tools) return;
  anchor.dataset.m11Tools = '1';
  /* ⛔ 「⬆ Excel 导入台账」那个按钮**已删**（`TAIL-75` 余项 · 2026-09-23 **用户裁定**：导入只在启用
     初期用一次 ⇒ **只留通用面**）—— 台账导入现在走壳「数据导入」页（`m11_jc` 域）。
     ⇒ 本钩子现在只剩 `M5-9` 的「隐藏贸易公司三列」（`hidBtn` 挂在同一个锚点后面）。 */

  /* ⭐ `M5-9`：① **导出**（按屏幕上这些行 · **列全给**）
     ② ⭐ **隐藏「贸易公司」三列**（用户 2026-09-20：「列太多了，贸易公司那 3 列不常用」）

     ⚠️ **为什么用 CSS 隐藏（`nth-child`）而不是改表头/行渲染**：
        裁列要同时动**三处**（表头 `JC_THEAD` / 行 / **合计行**）＋ 清排序状态；
        而 `display:none` **一次覆盖三处**，且 `table-layout:auto` 会让**剩下的列自动变宽**
        —— 正好是用户要的"隐藏后其他列宽跟着自适应"。⛔ 不用 `visibility:hidden`（那**留着宽度**，白搭）。
     ⚠️⚠️ **切换时必须清该表的排序状态**（`SORT['m11:jc']`）：
        若用户**先**按「贸易公司合同金额」（第 9 列）排了序、**再**隐藏 ⇒ `SORT.i=9` 仍在生效
        （对一列**看不见**的列排序）⇒ 界面看着"没排序"，人会以为排序坏了。
     ⚠️ 列号是**写死的位置**（8/9/10）—— 它跟着 `JC_THEAD` 的列序走；⚠️ **改表头列序要同步改这里**
        （这也是"通用列管理"值得单独做一次的原因：通用件该按列的**稳定身份**定位，而不是位置）。 */
  const hidBtn = document.createElement('button');
  hidBtn.className = 'btn';
  hidBtn.dataset.act = 'jcToggleTrade';
  hidBtn.id = 'jcTradeBtn';
  hidBtn.title = '隐藏 / 显示「贸易公司名 · 贸易公司合同金额 · 贸易公司发票金额」三列'
    + '（只影响屏幕；⭐ 导出永远是全列）';
  anchor.insertAdjacentElement('afterend', hidBtn);   /* ⚠️ 锚点已从「导入按钮」改成 `jcFetch`（那个按钮已删） */
  jcApplyHide();                       /* ⚠️ 表是刚重建的 ⇒ 把"隐藏"偏好重新落上去（见 `jcApplyHide`） */
  /* ⭐⭐ `TAIL-180`（`B` 案 · 2026-09-29 用户裁定）：行身份区（勾选框 ＋ 序号 ＋ 合同日期 ＋ 材料名）钉住
     —— 同「隐藏偏好」一个道理：`render()` 每次都重建整张表 ⇒ **每次都重量一次偏移**
     （本页偏移是量出来的，⛔ 不是静态算式 —— 为什么见 `actions.js::jcApplyPin` 那段注释）。 */
  jcApplyPin();

  /* ⭐⭐ `M5-9` 导出：**接管页面已有的那个「导出 Excel」按钮**，⛔ **不新建一个**。
     ⚠️ 2026-09-20 用户实测：「导出的按钮现在有俩了，你合并一下，把无色的合并到有颜色的按钮里」
        —— 页面上原本就有 `<button class="btn pri" data-act="exp">导出 Excel</button>`（**有颜色**），
        我又 `createElement` 了一个无色的 ⇒ 两个按钮干同一件事。
     ⚠️ **为什么"改它的 `data-act`"而不是去改切片里那行**：切片一行不改是硬约束（`ui_parity`）；
        而**渲染后注入属性**正是本层（`BIND`）该干的活 —— 同 `injectTypeEdit` 那套（那里也是注入属性、
        不改切片）。⛔ 不要为了省事去动 `V.m11` 那一行。
     ⚠️ 取**最后一个** `[data-act="exp"]`：m11 页里只有这一个，但按"最后一个"取更稳
        （将来若有人在前面的卡头再加一个，也不会误改到别的卡上）。 */
  const expOld = [...host.querySelectorAll('[data-act="exp"]')].pop();
  if (expOld) {
    expOld.dataset.act = 'jcExport';
    expOld.title = '导出当前屏幕上这些行（含筛选）为 Excel —— ⭐ 列是全列（隐藏列也会导出）';
    expOld.textContent = '⬇ 导出 Excel';
  } else {
    // ⚠️ 兜底：万一页面结构变了、找不到那个按钮 ⇒ **补一个**（⛔ 不能"导出功能凭空消失"而不报错）
    const b = document.createElement('button');
    b.className = 'btn pri';
    b.dataset.act = 'jcExport';
    b.title = '导出当前屏幕上这些行（含筛选）为 Excel —— ⭐ 列是全列（隐藏列也会导出）';
    b.textContent = '⬇ 导出 Excel';
    hidBtn.insertAdjacentElement('afterend', b);
  }
};

const _BIND_M03_OLD = BIND.m03;
BIND.m03 = function () {
  if (typeof _BIND_M03_OLD === 'function') _BIND_M03_OLD();
  const host = document.querySelector('#view');
  if (!host) return;
  const anchor = host.querySelector('[data-act="ntPrint"]');
  if (!anchor || anchor.dataset.m03More) return;
  anchor.dataset.m03More = '1';
  const box = document.createElement('span');
  box.className = 'sp';
  box.innerHTML = `<button class="btn" data-act="ntPdf" title="与批量打印同一次勾选，只换成「只产出 PDF」">只导出 PDF</button>
    <button class="btn gost" data-act="m03PrinterOpen" title="打印机地址（保存后即时生效、无需重启）">打印机设置</button>`;
  anchor.insertAdjacentElement('afterend', box);
};

/* ⭐⭐ 2026-09-28（`TAIL-144`）**这里原来有一个 `BIND.m05`**（2026-09-20 起：用 DOM 注入把「选择项目 ＋
   导出总欠款」两个按钮插到卡头「导出…」旁边）。⭐ **本轮撤掉**，理由（用户截图报障）：
     · 卡头因此挤了**三个**导出件（导出台账… / 选择项目 / 导出总欠款）—— 而用户 2026-09-13 的裁定是
       「**卡头一个导出入口**」；而且"点右上那个按钮、再跑到最左边选项目"（展开区在卡内左侧）正是他说的不便。
   ⇒ 现在这两个按钮**直接渲染在展开区里**（`index.html` 的 `ledExpStrip` 第 ② 段），与它们各自的项目范围挨着；
     卡头只留一个「导出…」。⭐ 这同时省掉了当年那个折中：注入是为了"零 `V.` 切片漂移"，
     而现在**改 `V.m05` 已经是常规操作**（`ui_parity` 的登记簿可增可减、逐条审过即可）。
   ⛔ **别再注入回卡头**（`test_wired_m05.py::test_台账卡头按钮分组与点开有反馈都钉住` 数着卡头只有这一个入口）。 */

BIND.m02 = function () {
  const host = document.querySelector('#view');
  if (!host) return;
  const kv = host.querySelector('.kv');
  if (kv) kv.innerHTML = m02EchoKv();
  const tbl = host.querySelector('table[data-sort-key="m02:logs"]');
  const tb = tbl && tbl.querySelector('tbody');
  if (tb) tb.innerHTML = m02LogRows();
  /* ⭐ 2026-09-20 用户口径：「**卡名改准**」+「里面显示的**接口名不直观**，换成直观的」。
     ① 卡名：这张表现在装的是**全部执行记录**（抓取 / 同步 / 打印 / 导出 PDF **都**写进来）
        ⇒ 叫「抓取任务日志」**名不副实**（用户就是据此说"任务日志里还没有吧" —— 他找的是"抓取"）。
        ⚠️ 改的是 **DOM 文本**（⛔ **不动 `V.m02` 切片**）：切片是**逐行对位**核对的，
           改一个字会让该片后面**全部报漂移**（实测插 1 行 = 67 行）；而 `BIND` 正是本仓
           「渲染后注入」的既定位置（`BIND.m01`/`m03`/`m11` 同款）。
     ② 表头「接口」→「动作 / 接口」：因为现在里面既有**抓取接口**、也有**打印/导出**这类"动作"。 */
  if (tbl) {
    const card = tbl.closest('.card');
    const h4 = card && card.querySelector('h4');
    if (h4) h4.textContent = '执行记录';
    const th = tbl.tHead && tbl.tHead.rows[0] && tbl.tHead.rows[0].cells[1];
    if (th) th.textContent = '动作';
  }
  /* ⭐ 2026-09-27（`TAIL-127` · 用户裁定 **B**）：**「i8 服务地址」搬到本页** ——
     用户原话：「连接参数这个板块说实话可以删掉，因为**不可能有变动**；那系统设置就只剩下主题色了」。
     ⚠️ **为什么注入、不进 `V.m02` 切片**：切片是**逐行对位**核对的 ⇒ 插一行 = 后面全部报漂移
        （实测一次 67 行）；而"渲染后注入"正是 `BIND` 的活（`BIND.m03`/`m11`/`m05` 同款）。
     ⚠️ 锚点取「装着回显 `.kv` 的那张卡的 `h4`」—— ⛔ 不赌列序号 / 不赌按钮文字（那是别处同一把尺子）。
     ⚠️ **幂等**：`render()` 会重画多次 ⇒ 靠 `dataset.i8Set` 打标，⛔ 不叠加。 */
  const kvCard = kv && kv.closest('.card');
  const h4 = kvCard && kvCard.querySelector('h4');
  if (h4 && !h4.dataset.i8Set) {
    h4.dataset.i8Set = '1';
    const b = document.createElement('button');
    b.className = 'btn sp';
    b.dataset.act = 'i8SetOpen';
    b.textContent = 'i8 连接设置';
    b.title = 'i8 装在哪台机器上（服务地址）—— 从「系统设置」搬到这里：它就是用它的那一页。'
      + '保存即时生效、改动留痕';
    h4.appendChild(b);
  }
};

BIND.m01 = function () {
  /* ---- ⭐ `TAIL-42`：**类型列的人工覆盖入口**（三类判定的纠正）--------------------------------
     ⚠️ 为什么由钩子注入：`V.m01` 切片里那一格是 `${typeTag(p.type)}`（**只读**，没有动作），
        给它加 `data-act` = 改切片那一行 ⇒ 会登记一处偏离；而**注入属性**正好是「渲染后注入」的活。
     ⚠️ 只给**真的档案行**注入（判据 = 该行有 `editStatus` 那个带 `data-id` 的按钮 ⇒ 与别处同一把尺子），
        列位置靠**单元格文字**认（三个类型标签之一）⇒ ⛔ 不赌列序号（列序变了这里也不会错）。
     ⚠️ **不在壳里筛类型**（"具体小微不给改"是后端的判定）—— 壳里再写一份就成第二份口径了。 */
  (function injectTypeEdit() {
    const TYPES = ['普通项目', '小微壳', '具体小微'];
    document.querySelectorAll('#view tr').forEach(tr => {
      const btn = tr.querySelector('[data-act="editStatus"][data-id]');
      if (!btn) return;
      const td = [...tr.children].find(c => TYPES.includes((c.textContent || '').trim()));
      if (!td) return;
      td.setAttribute('data-act', 'pjTypeOpen');
      td.setAttribute('data-id', btn.dataset.id);
      td.setAttribute('title', '点一下改类型（人工覆盖自动判定 · §2.2.1）');
      td.style.cursor = 'pointer';
    });
  })();

  const host = document.querySelector('#view');
  if (!host) return;
  /* ⭐ 链路 A ③-b 的入口（`TAIL-45`）—— 同一套注入法（**幂等**：先撤旧的、再按当前清单重建）。
     ⚠️ 与上面那张卡**两条链路、两个来源**（B：材料侧抓取报出的陌生仓库挂哪一行；
        A：名单同步报出的"一个全名挂 ≥2 个仓库"选哪一个）⇒ 失败原因**各报各的**。 */
  const aold = document.getElementById('archBox');
  if (aold) aold.remove();
  /* TAIL-263：只展示实际待人工建档与读取失败，其他同步条目不占默认页面。 */
  if (ARCP.length || ARCP_ERR) {
    const asrc = ARCP_SRC && ARCP_SRC.target
      ? `清单来自<b>最近一次「常用项目列表」同步</b>：<span class="fc">${esc(ARCP_SRC.target)}</span>`
        + (ARCP_SRC.at ? ` · ${esc(ARCP_SRC.at)}` : '')
      : '⚠️ 没找到同步记录（清单可能来自更早的会话）';
    const arows = ARCP.map((it, i) => `<tr>
      <td class="sm">${esc(it.full)}</td>
      <td class="sm">${it.whs.length} 个待选<br><span class="mut sm">${esc(it.whs.join('、'))}</span></td>
      <td class="sm">${em(it.reason)}</td>
      <td class="ctr now"><button class="btn sm pri" data-act="pjArchOpen" data-arch="${i}">选一个仓库建行</button></td></tr>`).join('');
    const abox = document.createElement('div');
    abox.id = 'archBox';
    abox.className = 'card';
    abox.innerHTML = `<h4>待人工建档<span class="sp"><span class="mut sm">共 ${ARCP.length} 条 · ${asrc}</span></span></h4>
      <div class="bd">
        ${ARCP_ERR ? `<div class="tip dg" style="margin:0 0 calc(8px * var(--fscale))">⚠️ <b>待建档清单没取到</b>：${esc(ARCP_ERR)}
          <br>其余档案数据照常显示（这一路失败不拖垮本页）—— 可刷新页面重试。</div>` : ''}
        ${ARCP.length ? `<div class="tip" style="margin:0 0 calc(8px * var(--fscale))">这个全名在 i8 名单里挂了
          <b>≥2 个仓库</b>，而一条项目只挂一个 ⇒ 请<b>选定一个</b>，系统按它建行（其余仓库<b>不会</b>再建行）。</div>
        ${TBL({cls:'cond',head:'<th>项目全名</th><th>待选仓库</th><th>系统为什么不自己定</th><th></th>',
        rows:[arows]})}` : ''}
      </div>`;
    host.prepend(abox);
  }
  const old = document.getElementById('pendBox');
  if (old) old.remove();
  if (!PEND.length && !PEND_ERR) return;        /* 没有待办、也没出错 ⇒ 不占地方 */
  const src = PEND_SRC && PEND_SRC.target
    ? `清单来自<b>最近一次材料侧抓取</b>：<span class="fc">${esc(PEND_SRC.target)}</span>`
      + (PEND_SRC.at ? ` · ${esc(PEND_SRC.at)}` : '')
    : '⚠️ 没找到材料侧抓取记录（清单可能来自更早的会话）';
  const rows = PEND.map((it, i) => {
    const ph = it.candidates.filter(c => c.ph).length;
    const list = it.candidates.map(c => `#${c.id} ${esc(c.name || '（壳无仓库）')}`
      + (c.ph ? '<span class="tag t-wn">占位</span>' : '')).join('、');
    return `<tr><td><span class="fc">${esc(it.wh)}</span></td>
      <td class="sm">${esc(it.full)}</td>
      <td class="sm">${it.candidates.length} 条（占位 ${ph}）<br><span class="mut sm">${list}</span></td>
      <td class="sm">${em(it.reason)}</td>
      <td class="ctr now"><button class="btn sm pri" data-act="pjPromoteOpen" data-pend="${i}">指认到哪一行</button></td></tr>`;
  }).join('');
  const box = document.createElement('div');
  box.id = 'pendBox';
  box.className = 'card';
  box.innerHTML = `<h4>待人工指认<span class="sp"><span class="mut sm">共 ${PEND.length} 条 · ${src}</span></span></h4>
    <div class="bd">
      ${PEND_ERR ? `<div class="tip dg" style="margin:0 0 calc(8px * var(--fscale))">⚠️ <b>待指认清单没取到</b>：${esc(PEND_ERR)}
        <br>其余档案数据照常显示（这一路失败不拖垮本页）—— 可刷新页面重试。</div>` : ''}
      <div class="tip" style="margin:0 0 calc(8px * var(--fscale))">材料报表出现了<b>陌生仓库</b>，其全名在档案里命中 <b>≥2 条</b>非壳行 ⇒ 系统<b>无法自己决定</b>挂哪条、也<b>不该猜</b> —— 请指明这条<b>真实仓库名</b>该写到<b>哪一行</b>上。⚠️ <b>只改仓库名</b>；<b>类型纠正</b>不在这里做。</div>
      ${TBL({cls:'cond',head:'<th>陌生仓库名</th><th>项目全名</th><th>同名档案行</th><th>系统为什么不自己定</th><th></th>',
      rows:[rows]})}
    </div>`;
  host.prepend(box);
};

/* 打开「人工指认」弹窗 —— **两个入口共用**（页首清单 / 占位行的「扶正」按钮）。
   形态照原型那个 `promote` 弹窗（信息块 ＋ 一个下拉 ＋ 取消/确认两键），
   只把下拉的语义从「选真实仓库名」换成**「选哪条档案行」**：仓库名是**已知**的（抓取回执给的），
   缺的是"挂哪一行"（§17.4）。 */
async function openPendDialog(i) {
  const it = PEND[i];
  if (!it) return;
  let d;
  try { d = await API.pjPromoteCandidates(it.full); }
  catch (e) { return toast(`<b>候选档案行没取到</b>：${esc(String((e && e.message) || e))}`, 7000); }
  const rows = (d.rows || []).map(c => ({
    id: String(c.id), typeLabel: c.type_label || '', name: c.warehouse_name || '',
    disp: c.disp || '', status: c.status || '', ph: !!c.is_placeholder,
  }));
  /* ⚠️ **只有占位行能被扶正**（§2.3.1「仓库名不可人工修改」）⇒ 非占位行**列出来但不可选**：
     让人看见"为什么有 ≥2 条"，而不是把它们藏起来让人以为只有 1 条。 */
  const usable = rows.filter(r => r.ph);
  const opts = rows.map(r => `<option value="${r.id}"${r.ph ? '' : ' disabled'}>`
    + `#${r.id} · ${esc(r.typeLabel)} · ${esc(r.name || '（壳无仓库）')}`
    + `${r.ph ? '（占位行 ✅ 可扶正）' : '（⛔ 已有真实仓库名，不可改）'}`
    + ` · ${esc(r.status === 'archived' ? '归档' : '在建')}</option>`).join('');
  PEND_DLG = it;
  modal({
    title: `人工指认 · ${it.wh}`,
    body: `<div class="tip" style="margin-bottom:calc(10px * var(--fscale))">材料报表里出现了
      <b>陌生仓库</b>，而它的全名在档案里命中 <b>${rows.length}</b> 条非壳行 ⇒ <b>系统不猜</b>，
      请你指明这条仓库名该写到<b>哪一行</b>。⚠️ 这是<b>系统写入</b>（不是人工改仓库名，§2.3.1）；
      <b>类型纠正</b>不在这里做（另立）。</div>
      ${kvBlock([['陌生仓库名', `<span class="fc">${esc(it.wh)}</span>`],
                 ['项目全名', `<span style="font-size:calc(11.5px * var(--fscale))">${esc(it.full)}</span>`],
                 ['系统当时为什么没自己定', `<span style="font-size:calc(11.5px * var(--fscale))">${em(it.reason)}</span>`]])}
      <div class="fld"><label>写到哪一行（候选 = 该全名下的档案行，含归档行）</label>
        <select class="inp" id="pmRow">${opts}</select></div>
      ${usable.length ? '' : `<div class="tip dg" style="margin:0">⚠️ 这几行<b>都不是占位行</b>（都已有真实仓库名）
        ⇒ （普通项目 ↔ 仓库 = 1 : 1）<b>不能靠扶正解决</b> —— 需要人工核对档案，属另一件事。</div>`}`,
    footer: `<button class="btn" data-act="closeModal">取消</button>
      <button class="btn pri" data-act="pjPromoteOk"${usable.length ? '' : ' disabled'} title="${usable.length?'把该小微写到选定的那一行':'候选里没有可写的占位行 —— 弹窗里已写明'}">按这一行扶正</button>`,
  });
}

/* 打开「选定仓库 ⇒ 建档」弹窗（`TAIL-45`）—— 形态照上面那个（信息块 ＋ 一个下拉 ＋ 两键），
   只把语义从「选哪条档案行」换成**「选哪个仓库」**：全名是**已知**的（同步回执给的），
   缺的是"用哪个仓库名建这一行"（决策 2：一条普通项目只挂一个仓库）。
   ⚠️ 候选 = **那次同步报出的 i8 名单减去已被占用的**（后端现算给的）⇒ 这里⛔ 不自己过滤、
      也⛔ 不给"手填仓库名"的口子（§9.4：仓库名以 i8 为准）。 */
async function openArchDialog(i) {
  const it = ARCP[i];
  if (!it) return;
  const opts = it.whs.map(w => `<option value="${esc(w)}">${esc(w)}</option>`).join('');
  /* ⚠️ 当时那份里**少了谁**要看得见（否则用户会以为系统漏报了某个仓库） */
  const gone = it.stored.filter(w => !it.whs.includes(w));
  ARCP_DLG = it;
  modal({
    title: `选定仓库 · ${esc(it.full)}`,
    body: `<div class="tip" style="margin-bottom:calc(10px * var(--fscale))">i8 名单里这个全名挂了
      <b>${it.stored.length}</b> 个仓库，而<b>一条普通项目只挂一个仓库</b> ⇒ <b>系统不猜</b>，
      请你选定<b>一个</b>，系统按它建行（⛔ 仓库名不许手填，§9.4）。</div>
      ${kvBlock([['项目全名', `<span style="font-size:calc(11.5px * var(--fscale))">${esc(it.full)}</span>`],
                 ['i8 名单里的仓库', `<span style="font-size:calc(11.5px * var(--fscale))">${esc(it.stored.join('、'))}</span>`],
                 ['已被别的行占用（不列）', `<span style="font-size:calc(11.5px * var(--fscale))">${gone.length ? esc(gone.join('、')) : '（无）'}</span>`],
                 ['系统当时为什么没自己定', `<span style="font-size:calc(11.5px * var(--fscale))">${em(it.reason)}</span>`]])}
      <div class="fld"><label>选定一个仓库（候选 = i8 名单里那条，减去已被占用的）</label>
        <select class="inp" id="arcWh">${opts}</select></div>`,
    footer: `<button class="btn" data-act="closeModal">取消</button>
      <button class="btn pri" data-act="pjArchOk">按这个仓库建行</button>`,
  });
}

/* ============ MOD-02 i8 接入层（前端壳接线 · `TAIL-27`）============
   ⭐ **「抓取结果回显」与「抓取任务日志」的唯一数据源 = 执行记录**（`/api/m02/fetch/records`）：
      原先两张卡是**模拟值 ＋ 硬编码行**（还读着演示数组 `WHs`/`JCs`）⇒ 接线后一律读真记录，
      ⛔ 不读任何演示数组（那两份数据的主人分别是 m07 的演示与集采域的原型页）。
   ⚠️ **接口清单表（`TASK`）已于 2026-09-27 删除**（`TAIL-117` 批次 7）—— 它**零引用**、且内容是
      **开发视角**（`API-0x` 代号 / 触发方式 / 数据源），数据源本就是《说明书》附录 E.1 的文档
      ⇒ 需要时查文档，⛔ 别在壳里再抄一份（两份真源 ⇒ 文档一改就静默过期）。
   ⚠️ 「采购合同信息」（`API-04`）**没有落点** —— 属**集采域（M5，未开工）** ⇒ 卡片上如实标「待接通」，
      ⛔ 不写 0（那是假话：会让人以为"抓过、没有"）。 */
let M02_RECS = [];        /* 执行记录（**新 → 旧**），由 `reloadM02()` 填 */
let M02_ERR = '';         /* 这一路取数失败的原因（页面上如实说；⛔ 不静默成"没有记录"） */

/* 回显卡：一行一个接口 → 在**执行记录**里认它的 `target`。
   ⚠️ 材料侧两条抓取的 `target` 是 `<SPEC_KEY> <年月>…`（`setl` / `inv`）—— 与 `m07`/`m08` 同源，
      而付款通知书是「付款通知书 <年月>」（见 `mod02_i8/router.py` 的 `fetch_run`）。 */
const M02_IFACES = [
  {label: '付款通知书', api: 'API-01', keys: ['付款通知书'], bare_month: true},
  {label: '收发结存表', api: 'API-02', keys: ['setl', '收发结存表']},
  {label: '库存单据明细表', api: 'API-03', keys: ['inv', '库存单据明细表']},
  {label: '采购合同信息', api: 'API-04', keys: ['采购合同']},
  {label: '仓库列表', api: 'API-05', keys: ['仓库列表']},
  {label: '常用项目列表', api: 'API-06', keys: ['常用项目列表']},
];

/* ⭐ 一条记录属不属于这个接口 —— **认得出才归**，认不出**不猜**。
   ⚠️ 付款通知书那条链路的执行记录**只写「年月」**（`mod03_notice/router.py` 里 `target=year_month`）
      ⇒ 纯 `YYYY-MM` 就是它（别的接口都带前缀：`setl …` / `inv …` / `仓库列表` …）。
      2026-09-18 真机实测踩到：不认它 ⇒ 回显卡对**已经抓过**的付款通知书说「还没有执行记录」（假话）。 */
function m02IsIf(it, r) {
  if (it.keys.some(k => r.target.indexOf(k) >= 0)) return true;
  return !!it.bare_month && /^\d{4}-\d{2}$/.test(String(r.target).trim());
}

function m02Latest(it) {
  return M02_RECS.find(r => m02IsIf(it, r)) || null;
}

function m02When(r) {
  return String(r.at || '').replace('T', ' ').slice(5, 16);     /* MM-DD HH:MM */
}

function m02Dur(r) {
  if (!r.at || !r.fin) return '—';
  const d = (new Date(String(r.fin).replace(' ', 'T')) - new Date(String(r.at).replace(' ', 'T'))) / 1000;
  if (!isFinite(d) || d < 0) return '—';
  return (d < 10 ? d.toFixed(1) : String(Math.round(d))) + 's';
}

function m02StatusTag(r) {
  if (r.status === 'success') return `<span class="tag t-ok">成功 ${r.ok} 条</span>`;
  if (r.status === 'failed') return `<span class="tag t-dg">失败</span>`;
  return `<span class="tag t-wn">部分成功 ${r.ok} / ${r.ok + r.fail}</span>`;
}

/* 回显卡那 6 行（`V.m02` 里原先是模拟表达式 ⇒ 换成这一个出口） */
function m02EchoKv() {
  return M02_IFACES.map(it => {
    const r = m02Latest(it);
    let dd;
    if (it.api === 'API-04') dd = '<span class="mut">待接通 —— 集采那边的抓取还没做</span>';
    else if (M02_ERR) dd = '<span class="dg">⚠️ 执行记录没取到（见下方日志卡）</span>';
    else if (!r) dd = '<span class="mut">还没有执行记录（抓过 / 同步过就有了）</span>';
    else dd = `${m02StatusTag(r)} <span class="mut sm">${esc(m02When(r))}</span>`
      + (r.err ? `<br><span class="dg sm">${lgMd(r.err)}</span>` : '');
    return `<dt title="${esc(it.api)}">${esc(it.label)}</dt><dd>${dd}</dd>`;
  }).join('');
}

/* 任务日志卡的行（时间 / 接口 / 结果 / 耗时 —— 后两项由适配层从记录算，⛔ 后端不为此加字段） */
function m02LogRows() {
  if (M02_ERR) return `<tr><td colspan="4" class="dg">⚠️ <b>执行记录没取到</b>：${esc(M02_ERR)}
    <br><span class="mut">其余页照常可用（这一路失败不拖垮本页）—— 可刷新页面重试。</span></td></tr>`;
  if (!M02_RECS.length) return '<tr><td colspan="4" class="mut">还没有执行记录 —— 抓过 / 同步过之后这里就有（按时间倒序）</td></tr>';
  return M02_RECS.map(r => `<tr><td class="fc">${esc(String(r.at).replace('T', ' '))}</td>
    <td title="${esc([m02CodeOf(r), String(r.target || '')].filter(Boolean).join(' · '))}">${esc(m02LabelOf(r))}</td>
    <td>${m02StatusTag(r)}${r.err ? `<br><span class="dg sm">${lgMd(r.err)}</span>` : ''}</td>
    <td class="fc">${esc(m02Dur(r))}</td></tr>`).join('');
}

function m02LabelOf(r) {
  const it = M02_IFACES.find(x => m02IsIf(x, r));
  /* ⚠️ 抓取接口给「名字（型号）」，⛔ 不再把 `API-0x` 顶在前面 —— 用户 2026-09-20：
     「里面显示的**接口名不直观**，换成直观的」。
     ⭐⭐ 2026-09-27（守则 §3.1 · `TAIL-117` 批次 2）：**接口代号整串撤出可见文案** ——
        上一版是 `付款通知书（API-01）`，用户看到的仍是内部编号。代号**没丢**：
        它挂在日志卡那一格 / 回显卡的 `title` 上（见 `m02CodeOf` ⇒ 悬停即见，守则 §5.8「换地方，不是删掉」）。 */
  if (it) return it.label;
  /* ⚠️⚠️ 2026-09-20 补：**打印 / 只导出 PDF 的记录不在 `M02_IFACES` 里**（那是"抓取接口"清单）
     ⇒ 原先 fallback 成 `r.target`，而那是**一长串单号**（`FKTZS…,FKTZS…`，最多 512 字符）
     ⇒ 界面上就是"完全看不出这是干什么的"。⇒ 按 `run_type` 给人话，单号只给**个数**、
     全文放进那一格的 `title`（悬停看，⛔ 不把一长串塞进格子里）。 */
  const RUN = {print: '批量打印', export_pdf: '只导出 PDF', fetch: '抓取付款通知书', sync: '同步 i8 名单'};
  const n = String(r.target || '').split(',').filter(Boolean).length;
  if (RUN[r.type]) return `${RUN[r.type]}${n ? ` · ${n} 张` : ''}`;
  return r.target;                                     /* 真认不出的走原文（⛔ 不猜成某一类） */
}

/** ⭐ 该记录对应的 i8 接口代号（`API-0x`）—— **只给悬停 `title` 用，⛔ 不上屏**（守则 §3.1/§5.8）。
 *  认不出就空串（别硬猜成某一类）。 */
function m02CodeOf(r) {
  const it = M02_IFACES.find(x => m02IsIf(x, r));
  return it ? it.api : '';
}

async function reloadM02() {
  const recs = await API.m02Records(50);
  M02_RECS = (recs || []).map(r => ({
    id: r.id, type: r.run_type || '', target: String(r.target || ''), status: String(r.status || ''),
    ok: Number(r.success_count || 0), fail: Number(r.fail_count || 0),
    err: String(r.error_message || ''), at: r.started_at || '', fin: r.finished_at || '',
  }));
  M02_ERR = '';
}

/* ⭐ 2026-09-20：**某个动作刚写完一条执行记录 ⇒ 若此刻正开着 `m02`，就地刷那两张卡**。
   ⚠️ 用户实测：「**执行记录并不会自动刷新**」——
      在 `m02` 页点「触发」抓完，回显卡与记录卡**都还是旧的**（得离开再回来才更新）。
   ⚠️ 为什么判 `VIEW`：⛔ 不在别的页白拉那 50 条（别页根本看不到这张卡）；
      等用户切回 `m02` 时，`ALWAYS_FRESH` 会保证重拉一次 —— 两条合起来才没有缝。
   ⚠️ 取数失败**不吞**：`reloadM02` 抛的话由 `M02_ERR` 在卡里如实说（与它本来的口径一致）。 */
async function reloadM02IfOn() {
  if (VIEW !== 'm02') return;
  try { await reloadM02(); } catch (_) { /* 卡里会如实说（`M02_ERR`） */ }
  render();
}

/* ⭐ 看板 ⑦⑬⑭ 的取数（`/api/home/run-counts` · 2026-09-21 接线）——
   原先那两个瓦片读**写死的演示数组** `RUNLOG` ⇒ 看板成了全站唯一还显示模拟数据的页。
   ⚠️⚠️ ⛔ **别改回"扫 `m02Records` 最近 N 条"**：那个端点是**窗口**（`limit ≤ 200`），
      而 `run_record` 是**流水表**（实测 ≈10 条/天 ⇒ 一个月 ≈300 条）⇒ **会漏，且漏了不报错**
      （症状 = 看板说"本月未抓" ⇒ 用户照着去重抓 ⇒ **白顶一次 i8 的号**）。
   ⭐ 后端走 **SQL 全表**（`app/home/service.py::run_counts`）⇒ 答案与表有多大**无关**。 */
/* ⭐⭐ 看板 ⑦⑬⑭ 的**取数接口**（`V.home` 只认这一个）—— ⚠️ 原型里有**同名同形**的一份，
   两份都定义在 `V.home` **切片之外**，所以 `ui_parity` 的逐行比对不受影响（切片本身逐字一致）。
   壳这一份 = **后端算好的**（`HOME`）；原型那一份 = 用它的演示记录现算。
   ⛔ 别把这里改成"在壳里扫 `m02Records` 最近 N 条"——那会漏（窗口），且**漏了不报错**。 */
function homeCounts() {
  return { counts: { fetchDue: HOME.counts.fetchDue, fetchFail: HOME.counts.fetchFail,
                     printFail: HOME.counts.printFail },
           latest: { fetchFail: HOME.latest.fetchFail, printFail: HOME.latest.printFail },
           err: HOME_ERR };
}
function runFailInfo(rec) {
  if (!rec) return null;
  /* 「表名 ＋ 时间」：标签走 `m02LabelOf`（与 `m02` 页**同一个出口**，⛔ 不在这儿另拼一套人话）；
     时间与 `m02LogRows` 同一展示口径（ISO ⇒ `T` 换空格）。 */
  return { obj: m02LabelOf({ type: rec.run_type, target: rec.target }),
           at: String(rec.started_at || '').replace('T', ' ') };
}
async function reloadHome() {
  try {
    const d = await API.homeRunCounts();
    const c = (d && d.counts) || {}, L = (d && d.latest) || {};
    HOME = {
      counts: { fetchDue: c.fetchDue ? 1 : 0, fetchFail: c.fetchFail ? 1 : 0,
                printFail: c.printFail ? 1 : 0 },
      latest: { fetchFail: runFailInfo(L.fetchFail), printFail: runFailInfo(L.printFail) },
    };
    HOME_ERR = '';
  } catch (e) {
    /* ⚠️ 记下来（三格要显「—」）**并且照常抛** —— 横幅得按路名点出这一路失败（`soft()` 的口径）。 */
    HOME_ERR = String((e && e.message) || e);
    throw e;
  }
}

/* ⭐ 两个同步（`API-05` / `API-06`）的**唯一入口** —— 壳里三处入口共用它：
   `m02` 表里 API-05/06 两行的「触发」＋ `m01` 页首那两个「同步…」按钮。
   ⚠️ **D9：会强踢该账号的在线用户** ⇒ ① 先弹**二次确认**（讲清顶号与时段），⛔ 不确认不发请求；
      ② 失败 / 降级 ⇒ 后端那句中文说明**原样**转给用户；③ 成功 ⇒ 刷新执行记录（回显与日志跟着变），
      同步**常用项目列表**还会**真的建档** ⇒ 顺手刷新档案与「待人工建档」卡（`TAIL-45`）。
   签发给谁：本函数的两种入参就是那两个端点（`warehouses` / `common-projects`）。 */
async function m02Sync(which) {
  const isWh = which === 'warehouses';
  const name = isWh ? '仓库名单' : '常用项目列表';
  const tail = isWh ? '仓库名单本身<b>不写入</b>（它是建档的输入）；建档请用「常用项目列表」那一行'
                    : '会按 信息化编号 <b>建档，重复的不会重复建</b>，并把「待人工建档」清单留在执行记录里（去 <b>m01</b> 处理）';
  modal({
    title: `同步 ${name}`,
    body: `<div class="tip dg" style="margin:0 0 calc(10px * var(--fscale))"><b>⚠️ 这一步会登录 i8，并强制踢掉该账号其它在线会话</b> ——
      若其他同事正在用 i8，请先<b>择时</b>；系统<b>不会</b>自动重试登录。</div>
      <div class="tip" style="margin:0">${tail}</div>`,
    footer: `<button class="btn" data-act="closeModal">取消</button>
      <button class="btn pri" data-act="m02SyncOk" data-which="${which}">确认同步（会顶号）</button>`,
  });
}

/* ============ MOD-09 特殊费用月报表（前端壳接线 · `TAIL-27`）============
   ⚠️ 后端金额出**字符串**（`numeric(18,2)` 精度保护）⇒ 这里**一律过 `N0()`**：
      原型切片里有 `r[1].toFixed(2)`，字符串会**直接 TypeError 整页崩**（而且不报错地坏）。
   ⚠️ 候选 / 默认项目 / 合计 / 自动项 **全部以后端回包为准**（⛔ 前端不再自算，避免第二份口径）。 */
async function reloadM09() {
  const d = await API.m09Fee(awfYm, awfPj);
  awfYm = d.ym || awfYm;                        /* 后端归一后的核算年月（认不出 ⇒ 回落默认月，§9.2） */
  awfPj = d.project || '';                      /* 后端已把"没给 / 给了无效值"归一成候选第一个 */
  AWF_PJS = (d.projects || []).map(p => p.key).filter(Boolean);
  AWF_ROWS = (d.manuals || []).map(r => ({ index: r.index, id: r.id, item: r.item, amount: N0(r.amount) }));
  AWF_AUTO = N0(d.auto && d.auto.amount);
  AWF_TOTAL = N0(d.total);
  AWF_CAN_EDIT = !!d.can_edit;
  render();
}

/* 写动作统一走这里：**成功/失败都回后端真实状态**，后端那句中文说明**原样转给用户**（不吞、不换句话）。
   ⚠️ 后端对「金额不合法」这类**可预期的拒绝**回的是 **HTTP 200 ＋ `ok:false`**（同 `m07` / `m03`）
      ⇒ 必须**同时**判 `ok === false`，否则那句"金额不合法…"会被当成成功吞掉。 */
async function awfAct(fn, okMsg) {
  let r = null;
  try { r = await fn(); }
  catch (e) {
    await reloadM09();
    return toast(`<b>没能保存</b>：${esc(String((e && e.message) || e))}`, 7000);
  }
  await reloadM09();
  if (!r || r.ok === false) { toast(`<b>没能保存</b>：${esc((r && r.message) || '系统没有给出原因，请重试')}`, 7000); return null; }
  toast(typeof okMsg === 'function' ? okMsg(r) : okMsg);
  return r;
}

/* ============ MOD-11 集采台账（前端壳接线 · `M5-7`）============
   ⚠️ 后端金额出**字符串**（`numeric(18,2)` 精度保护）⇒ 适配层**一律过 `N0()`**
      （漏了会让壳里求和变**字符串拼接**、合计安静地错 —— 技能「接后端时必查三件」那条）。

   ⭐ **`JCs` 是跨页共享的**（这是本页接线的价值面，也是风险面）：本页 + **看板** + **大表「主材累计」**
      （接上即解锁 `TAIL-25`）+ **`m03` 的集采关联区**（`jcUsedNids`/`jcRefOf`/`jcLinkCands`）。
      ⚠️ 但 **供应商自动匹配不再读它**（`M5-5` 已把判定搬到后端 `sup_match.py`）—— 那一路走 API。
      ⇒ 所以适配层给的字段必须**正好够那些读法**用（尤其 `proj` = 仓库名、`supplier`、`notice_ids`）。 */
const JC_ARCH_DEFAULT = '未存档';        /* 原型 `JC` 演示行用的初值（§6.7.2：未存档 → 资产处 → 已存档） */

function adaptJc(x) {
  return {
    /* ⚠️ id **必须 String** —— 原型到处 `x.id===t.dataset.id`，而 `dataset` 出来永远是字符串。
       后端给数字 ⇒ 不转就**静默失配**（勾选后汇总恒 0，同 `adaptNotice` 那条教训）。 */
    id: String(x.id),
    date: x.date || '', material: x.material || '', supplier: x.supplier || '',
    contractAmt: N0(x.contract_amt),
    tradeCo: x.trade_co || '',
    tradeContractAmt: (x.trade_contract_amt == null ? '' : N0(x.trade_contract_amt)),
    arch: x.arch || JC_ARCH_DEFAULT, archNo: x.arch_no || '', retDate: x.ret_date || '',
    method: x.method || '', remark: x.remark || '', tag: x.tag,
    /* ⚠️ 列表**不给子表明细**（那是 `/api/m11/detail` 的活）⇒ 这里留空数组；
       列表的金额列一律读下面的 `settle`/`pay`（后端派生），⛔ 不靠这两个数组现算。 */
    invoices: [], tradeInvoices: [], payments: [],
    proj: x.project_key || '',                                   /* ⭐ 键 = **仓库名**（§2.7.4） */
    /* ⭐ 派生金额**读后端**（判定搬家 —— 见 `jcSettle`/`jcPay`/`jcDebt`）。
       ⚠️⚠️ 键名以 `domain.DERIVED_MONEY_KEYS` 为准：是 **`pay_sum`**，⛔ 不是 `pay`！
       （写成 `x.pay` 会拿到 `undefined` ⇒ `N0()` 变 0 ⇒ **页面金额恒 0 而且不报错** —— 实测踩到过。） */
    inv_sum: N0(x.inv_sum), settle: N0(x.settle),
    trade_inv_sum: N0(x.trade_inv_sum), pay_sum: N0(x.pay_sum), debt: N0(x.debt),
    /* ⭐ 本行引用过的付款通知书 id（**字符串** —— `m03` 的 `jcUsedNids` 拿它跟 `n.id` 比） */
    notice_ids: (x.notice_ids || []).map(String),
  };
}

/* ⛔ 这里曾有 `adaptDf` ＋ `reloadM12()`（2026-09-20 为 `MOD-12` 差异登一页接的后端）。
   **已整段删除**（用户裁定撤页）—— 依据：§5.8.3 明写「差异归属「库存单据」（**不独立成模块**）」。
   ⭐ `DFs` 这个数组**留着**（`V.m12` 是**原型切片**、`ui_parity` 按它逐行对位）⇒ 让它保持
      **空数组**即可：页已从侧栏撤下、数据源已断，`V.m12` 渲染出的是空表（⛔ 不再是演示数据）。
   ⛔ 别再加回 `reloadM12` / `adaptDf`：差异的载体是**调整单**（`m08`）、产出是**差异表**（`m06`）。 */

async function reloadM11() {
  const d = await API.m11List();
  const rows = (d.rows || []).map(adaptJc);
  JCs.length = 0;                       /* ⚠️ **原地**替换（`JCs` 是 `const` ⇒ 只许改内容；同 `LGs` 的教训）。
                                           理由：`JCs` **跨页共享** —— 整支换引用会让 `JC_PROJ_LIST` 等派生量失效。 */
  rows.forEach(r => JCs.push(r));
  pruneJcPick();                        /* 数据换了 ⇒ 勾选按**当前筛选结果**重裁（判据 `001-06`） */
  render();
}

/* ⭐ 子表按需载入（三个子表弹窗的**唯一**数据来源）。
   ⚠️ 为什么必须"打开时拉"：`/api/m11/list` 每行**只给派生汇总**（settle/pay/debt），**不给子表明细**
      （那是 `/api/m11/detail` 的活）⇒ `adaptJc` 里的三个子表数组是**空的** ⇒ 不拉就显示"暂无发票"。
   ✅ **原地写回 `JCs` 那一行**（`j.invoices` / `j.tradeInvoices` / `j.payments`）⇒ 弹窗的渲染代码**一行不用改**。
   ⚠️ 删除动作按**下标**定位（原型就是 `data-i`）⇒ 这里把每张子表行的 **id** 按**同序**存进 `j._ids`
      （⛔ 不新开顶层变量 —— 那要同步 `_smoke.js` 的 `__X`，能用行字段就别开）。 */
async function jcLoadSub(j) {
  /* ⚠️ `/api/m11/detail` 的返回是 `{ok, kind, message, data}` —— 明细在 **`data`** 里（实测确认过键名，
     ⛔ 别凭印象写；少读一层 `data` 就会静默拿不到东西、弹窗永远显示"暂无"）。 */
  const resp = await API.m11Detail(j.id);
  const d = (resp && resp.data) || {};
  const money = r => [r.invoice_date, N0(r.amount)];
  j.invoices = (d.supplier_invoices || []).map(money);
  j.tradeInvoices = (d.trade_invoices || []).map(money);
  j.payments = (d.payments || []).map(r => [r.pay_date, N0(r.amount),
    (r.source === 'notice' ? '付款域引用' : '手工'), (r.notice_id == null ? null : String(r.notice_id))]);
  j._ids = {
    inv: (d.supplier_invoices || []).map(r => String(r.id)),
    tinv: (d.trade_invoices || []).map(r => String(r.id)),
    pay: (d.payments || []).map(r => String(r.id)),
  };
}

/* 写动作统一外壳（照 `awfAct`）：成功/失败**都回后端真实状态**，后端那句中文**原样**给用户。
   ⚠️ 后端对"可预期的拒绝"回 **HTTP 200 ＋ `ok:false`** ⇒ 必须**同时**判 `ok === false`。 */
async function jcAct(fn, okMsg) {
  let r = null;
  try { r = await fn(); }
  catch (e) {
    await reloadM11();
    return toast(`<b>没能保存</b>：${esc(String((e && e.message) || e))}`, 7000);
  }
  await reloadM11();
  if (!r || r.ok === false) { toast(`<b>没能保存</b>：${esc((r && r.message) || '系统没有给出原因，请重试')}`, 7000); return null; }
  toast(typeof okMsg === 'function' ? okMsg(r) : okMsg);
  return r;
}

/* ⭐ 抓取回执的**匹配预览**（`M5-6` 编排的 `matched_projects`/`unmatched_projects`）。
   ⚠️ 这不是"好看"——它是**唯一**能拦住"漏匹配被静默埋掉"的手段：
   匹配不上的按口径 = **不纳入**（终态、不会被后续抓取覆盖）⇒ 人必须**当场看一眼**再落。 */
function jcFetchPreview(d) {
  const list = (rows) => rows.length
    ? `<ul style="margin:calc(6px * var(--fscale)) 0 0;padding-left:calc(18px * var(--fscale));line-height:1.7">${rows.slice(0, 15).map(
      p => `<li><b>${p.count}</b> 条 · ${esc(p.name)}</li>`).join('')}</ul>`
      + (rows.length > 15 ? `<div class="mut sm">…另有 ${rows.length - 15} 个项目</div>` : '')
    : '<div class="mut sm">（无）</div>';
  const syn = d.sync || {};
  const warn = syn.degraded ? `<div class="tip wn" style="margin-top:calc(10px * var(--fscale))">⚠️ ${esc(syn.message || '')}</div>` : '';
  /* ⭐ 「**未落库**」的**原因分类**（后端回执 `d.unsettled` = 按 `kind` 计数；kind 来自
     `mod01_projects.domain.OwnershipDecision` —— 归属判定的**唯一出口**）。
     ⚠️ 这段文案的职责是**给人指下一步**：只写"没落库"用户不知道干什么。
     ⚠️ 口径（2026-09-25 · 用户「集采抓取与付款通知书同一套」）：未落库的**唯一**原因 = **归属没走完**
        （不再是"i8 常用列表里没有" —— 那是老口径的措辞），而落库前提 = 能归到一个**具体小微**。 */
  const KIND_TXT = {
    needs_keyword: '该项目名是「小微壳」，但单据名里认不出是壳下哪个小微 ⇒ 出路：到「档案」页在该壳下新建一个小微'
      + '（或给已有小微补上单据名里出现的关键词），补完再抓一次',
    needs_choice: '该项目名是「小微壳」，单据名同时命中壳下多个小微 ⇒ 出路：把关键词补得更具体，让它只命中一个，补完再抓一次',
    not_archived: '该项目还没建档 ⇒ 出路：先在「档案」页建档（或同步 i8 常用项目），建成后再抓一次',
  };
  const unsettled = (d.unsettled || []).filter(x => (x.count || 0) > 0);
  const unsettledHtml = unsettled.length
    ? `<div style="margin-top:calc(6px * var(--fscale))">${unsettled.map(x => `<div class="tip wn" style="margin:calc(4px * var(--fscale)) 0">`
        + `<b>${x.count}</b> 条 · ${esc(KIND_TXT[x.name] || ('归属未走完（' + x.name + '）'))}</div>`).join('')}</div>`
    : '';
  return `<div class="tip ok" style="margin-bottom:calc(10px * var(--fscale))"><b>抓取完成</b>：${esc(d.message || '')}</div>
   ${warn}
   <div style="font-size:calc(12.5px * var(--fscale))">
     <div><b>匹配上</b>（已写入 · 默认「纳入台账」）· ${d.matched} 条</div>
     ${list(d.matched_projects || [])}
     <div style="margin-top:calc(10px * var(--fscale))"><b>未写入</b>（<b>归属未走完</b> ⇒ 按口径<b>不纳管</b>）· ${d.unmatched} 条</div>
     ${unsettledHtml}
     ${unsettled.length ? `<div style="margin-top:calc(8px * var(--fscale))"><button class="btn pri" data-act="ownJcOpen">`
        + `去指定归属（${unsettled.reduce((n, x) => n + (x.count || 0), 0)} 条）</button>`
        + ` <span class="mut sm">补完关键词 / 建好小微后再抓一次即可自动归位</span></div>` : ''}
     ${list(d.unmatched_projects || [])}
   </div>`;
}

/* ⭐⭐ 性能 `P3` 主体 · **页级按需取数**（2026-09-19 · 用户批准的 A 方案）
   —— 打开页面**不再**把 13 路全量拉一遍，而是「**进哪页拉哪页**」（含该页会读到的全局所属的取数路）。
   ⚠️ 实测依据：13 路合计 ≈ 1971 ms（一路一等）；**初始视图是 `home`**（`let VIEW='home'`）而它只读
      `NO`/`PJs`/`PLs` ⇒ 首屏从「13 路后台全拉」降到「3 路」；`m07` 三条 / `m09` / `m08` 这些重活
      改为**进那页才拉**（实测请求数 25 → 18 是 `P3`① 的成果，本表是 `P3` 主体的成果）。
   ⛔ **三条不许动的红线**：① 逐路 `soft()` 容错 ＋ **失败点名**；② `收发结存与大表` / `付款域` 必须**等**
      `机械 6 列` ＋ `库存单据`（大表机械 / 焊材·气体列与 m05 机械欠款由它们派生）；
      ③ 写动作后**必须**回后端真实状态（各写动作自己的 `reload*()` 一字未动）。
   ⚠️ 缓存口径：`LOADED` 记"这路拉过了" ⇒ **同一页反复进出不重复拉**（与改前一致：改前是 boot 拉一次）。
      跨页写操作的陈旧性与改前**同级**（改前写 m03 也不会自动刷新 m05）；真要更强 = 写动作标脏，另立件。 */
const PAGE_LOAD = {
  /* ⭐ `home`（看板）：前三路供 ①–⑥ 与欠款卡；⭐ **第四路 `看板计数`** = ⑦⑬⑭ —— 它**只能问后端**
     （跨全表执行记录，见 `reloadHome` 上方那段为什么不能用记录窗口）。 */
  home: ['付款通知书', '项目档案', '付款计划', '看板计数'],
  m01: ['项目档案', '待人工指认', '待人工建档', '修改留痕'],
  m02: ['i8 执行记录', '库存单据'],      /* `V.m02` 的回显卡读 `IVs`/`ADs` */
  /* ⭐ `M5-5`：m03 页**也要读 `JCs`** —— 「集采实际供应商」那一格的关联区（`jcRefOf` 反查"被哪张合同引用了"、
     `jcLinkCands` 出候选）全靠它。⛔ **不后置**到写动作时再拉：
     首屏就得判"这行有没有被关联 / 有哪些候选"，否则按钮会先显示错的态再跳一下。 */
  m03: ['付款通知书', '付款计划', '项目档案', '集采台账'],
  m04: ['付款计划', '付款通知书', '付款域', '机械 6 列'],
  /* ⭐ 2026-09-28（用户口径 ①）：`m05` 新增「**按项目看集采欠款**」柱 ⇒ 本页**必须**带上「集采台账」
     这一路（它填 `JCs`）。⛔ 不加的话那条柱子会恒 0 —— 那是**假数**（比不显示更坏）。
     ⚠️ `JCs` 是跨页共享的（看板 / 大表主材累计 / m03 集采关联也读它）⇒ 多这一路不会重复取。 */
  m05: ['付款域', '修改留痕', '机械 6 列', '集采台账'],
  m06: ['过程资料', '机械 6 列', '库存单据', '收发结存与大表'],
  m07: ['机械 6 列', '库存单据', '收发结存与大表'],
  m08: ['库存单据'],
  m09: ['特殊费用月报表'],
  m14: ['规则配置'],
  /* ⭐ `M5-7`：集采台账。⚠️ 它**没有跨页依赖**（不读 `NO`/`PJs`/`PLs`）⇒ 单路即可。
     但它**自己的数据被别人读**（看板 / 大表主材累计 / m03 集采关联）—— 那些页各自按需拉自己的路，
     ⛔ 不在这里替它们拉（`P3` 的口径：进哪页拉哪页）。 */
  m11: ['集采台账'],
  /* ⭐ `m15`（`MOD-15` 用户管理）：**单路**（只读 `/api/m15/users`）——
     ⚠️ 它**不依赖**任何别的域（`V.m15` 只吃 `USERS`/`CUR`）⇒ 不进 `LOAD_DEP`。
     ⚠️ 但它**被别的页间接依赖**：`CUR`/`USERS` 是「当前登录用户」的来源，
       ⛔ 别把它排到需要"谁登录了"的页后面（目前无此依赖，登记在此备查）。 */
  m15: ['用户管理'],
  /* ⭐ `§19`「四个暂留件收口」（2026-09-21）：四页**各自一路**，都无跨页依赖（不读 `NO`/`PJs`/`PLs`）
     ⇒ ⛔ 不进 `LOAD_DEP`、也⛔ 不替别的页预拉。
     ⚠️ 它们的取数口**只在进这页时才发**（`go(k)` 触发）—— 与其余页同一条口径（`P3` 主体）。 */
  /* ⭐ `set`（系统设置）：主题清单是**这一页自己的取数路** —— 切换器住在这里（`MOD-14`），
     ⚠️ 塞进 `m15` 那一路会"只有进过用户管理才填得上"（见 `reloadTheme` 的注释）。 */
  set: ['系统设置', '外观主题'],
  /* ⭐ `TAIL-75` `B5`（2026-09-22）：「数据导入」（通用导入面）—— 域清单先来，其余按步走
     （选域 → 解析 → 映射 → 预览 → 确认），都在这一页自己的动作里发起 ⇒ **一路够**。 */
  imp: ['数据导入'],
  /* ⛔ `m08imp` 已随「库存单据手动导入」删除（2026-09-22 用户裁定）。 */
  };
/* 标签 → 取数函数（标签进顶部横幅的**失败点名** —— ⛔ 一字不许改，它们是给用户看的） */
const LOADERS = {
  '付款通知书': reloadNotices,      /* ⚠️ 走同一个出口：它还会重建「归属」缓存 `OWN` */
  '项目档案': async () => {
    const pj = await API.projects(); PJs = (pj || []).map(adaptProject);
  },
  '待人工指认': reloadPending,   /* ⭐ `TAIL-30`-③：m01 页首那个入口的数据源（独立一路） */
  '待人工建档': reloadArchPend,  /* ⭐ `TAIL-45`：链路 A ③-b「多仓库 ⇒ 选定一个」那一路 */
  'i8 执行记录': reloadM02,     /* ⭐ `TAIL-27`：`m02` 回显与任务日志的唯一数据源 */
  '看板计数': reloadHome,       /* ⭐ 看板 ⑦⑬⑭：**全表**记账（⛔ 与上面那路`窗口`是两回事，别合并） */
  '修改留痕': async () => {
    const tr = await API.trails();
    PJ_TRAIL.splice(0, PJ_TRAIL.length, ...(tr || []).map(adaptTrail));
  },
  '付款计划': async () => {
    const pl = await API.plans(); PLs = (pl.rows || []).map(adaptPlan);
  },
  '机械 6 列': reloadMech,
  '过程资料': reloadProc,
  '库存单据': reloadInv,
  /* ⚠️ `m09` 的自动项与手填项**都由后端自己算**（`mod09_fee/repository.inv_rows` 直读 `inv_detail`）
     ⇒ 与壳里的 `IVs` 无关、**不依赖 `reloadInv` 的顺序**。 */
  '特殊费用月报表': reloadM09,
  '规则配置': reloadM14,        /* 独立取数 ⇒ 无顺序依赖 */
  '用户管理': reloadM15,        /* ⭐ `m15`：`/api/m15/users` 单路，同样无顺序依赖 */
  '集采台账': reloadM11,        /* ⭐ `M5-7`：`/api/m11/list` ⇒ 原地填 `JCs`（跨页共享，见 `adaptJc` 上方注释） */
  /* ⭐ `§19`「四个暂留件收口」（2026-09-21）—— 实现在 `web/shell/legacy.js`（四页与其取数同处一件）。 */
  '系统设置': reloadSet,
  '外观主题': reloadTheme,      /* ⭐ 住 `V.set`（`MOD-14`）：可选清单 ＋ 我当前用哪套 */
  '数据导入': reloadImp,        /* ⭐ `B5`：通用导入面（域清单来自 `/api/imp/domains`） */
  /* ⛔ `'库存导入': reloadImp08` 已删（2026-09-22 撤手动导入）。 */
  /* ⛔ `'差异登记': reloadM12` 已删（2026-09-20 撤页）；`reloadM12` / `adaptDf` 也已删。 */
  '收发结存与大表': reloadM07,   /* ⚠️ 吃 `MACH6`/`IVs` ⇒ 见 `LOAD_DEP` */
  '付款域': reloadM05,          /* ⚠️ 机械欠款派生自 `MACH6` ⇒ 见 `LOAD_DEP` */
};
/* ⚠️ **依赖屏障**：这两路必须等 `机械 6 列` ＋ `库存单据`（组间串行、组内并发）。
   顺序写反 ⇒ 大表机械列 / 机械欠款**取到空值，且不报错**（`test_wired_boot.py` 有结构性断言）。 */
const LOAD_DEP = new Set(['收发结存与大表', '付款域']);

const fails = [];
/* ⚠️ **每一路取数独立容错**：任何一路失败（某端点临时 500 / 还没上线 / 网络抖）**不得拖垮其他页**。
   ⭐ 实测踩到：`/api/m06/mech` 404（后端加了端点但服务没重启）⇒ 原来的单个 `try` 把后面**全部**跳过，
      `m08`/`m05` 明明已接线却显示空表 —— **看起来像功能没做**（假故障、最难查的那类）。
   ⇒ 逐路 `soft()`：坏的那路在顶部横幅里**点名**，其余页**照常可用**。 */
const failsTech = [];          /* ⭐ 与上面 `fails` 并排的**技术明细**（只进横幅折叠区）—— 见 `soft` */
const soft = async (label, fn) => {
  try { await fn(); FAILED.delete(label); }        /* ⭐ 重试成功 ⇒ 摘掉"这一路坏了"的名 */
  catch (e) {
    FAILED.set(label, String((e && e.message) || e));   /* ⭐ `TAIL-117` 批次 6：按**路名**记失败（页级四态要用） */
    /* ⭐ 2026-09-27（`TAIL-117` 批次 1）：两半**分开收** ——
       `fails` = **上屏的那半**（`e.message` 已经过 `api.js` 的「人话出口」，守则 §3.7）；
       `failsTech` = **原始串那半**（方法 / 全路径 / 状态码）⇒ 只进横幅的「技术明细」折叠区。
       ⚠️ `BOOT_ERROR` 仍必须是**字符串**（`test_wired_boot` 与真机都按字符串判真假 ⇒ ⛔ 别改成数组）。 */
    fails.push(`${label}：${String((e && e.message) || e)}`);
    failsTech.push(`${label}：${String((e && e.tech) || (e && e.message) || e)}`);
  }
};
const LOADED = new Set();          /* 已经拉过的路（同一页反复进出不重复拉） */
/* ⭐⭐ 2026-09-27（`TAIL-117` 批次 6「页级四态」）：**逐路记失败** ＋ **记"正在拉"** —— 两件都只为
   `pageState()` 服务（见下方）。⛔ 别拿它们替代 `LOADED`：那三个集合问的是三个不同的问题 ——
     `LOADED` = 「这一路**拉过**没有」（缓存口径）· `PENDING` = 「**此刻**正在拉吗」（加载态口径）
     · `FAILED` = 「这一路**坏了吗**」（错误态口径）。⭐ 混成一个必然出错（实测过：写动作
     `LOADED.clear()` 之后，若拿"未 LOADED"当加载态 ⇒ **整页永远卡在"正在读取"**）。 */
const PENDING = new Set();
const FAILED = new Map();
/* ⭐⭐ 2026-09-20：**台账类取数不许被 `LOADED` 缓存住** —— 用户实测：「**执行记录并不会自动刷新**」。
   ⚠️ 缓存口径「同一页反复进出不重复拉」对**台账页**正好是错的：「i8 执行记录」的内容
      **由别的动作产生**（抓取 / 同步 / 批量打印 / 只导出 PDF 都往 `run_record` 里写一条），
      而用户看这一页**就是要看"刚刚那次跑完没"** ⇒ 缓存住的必然是**旧**的（在用户眼里就是假话）。
   ⇒ 列在这里的那几路：**每次进页都重拉**（它只是一次 50 条的 GET，代价可忽略）。
   ⛔ **不是**把 `LOADED` 删掉 —— 那会把 `机械 6 列` / `集采台账` / `收发结存与大表` 这些重活
      也拖成"每次进出都拉一遍"（`P3` 的性能收益白做）。只列「**内容由别人产生、且看它就是为了看新**」的。
   ⚠️ 这一条只解决"**切回 m02 时**看到的是新的"；"**人已经站在 m02 上**、从这页点触发"
      那一路由 `reloadM02IfOn()` 负责（见 `reloadM02` 下方）。 */
const ALWAYS_FRESH = new Set(['i8 执行记录']);

/* ⭐⭐ 2026-09-24（`TAIL-48` 余项 `P3`②）：**跨页写 ⇒ 全标脏** —— 壳里**唯一**的那个出口。
   证据（写/读两侧到表级）= `.codebuddy/work/10-designs/设计-写动作标脏数据流图-20260924.md`：
   壳按 `PAGE_LOAD` **进哪页拉哪页**、`LOADED` 记"这路拉过了"，而写动作**只 reload 自己那页**
   ⇒ ⛔ **别的页拿着旧数**（`payment_notice`/`payment_flow`/`jc_*`/`proc_mech_manual` 都是**多处读、一处写**）。
   ⚠️ 与 `TAIL-78`（导入落库 / 回滚：`legacy.js` 那两处 `LOADED.clear()`）**同一口径**，本件把它推广到写出口。
   ⛔ **不许**改成"写动作 → 受影响页"的字面映射表：读侧一改，那张表就开始漏（**双份真源**）；
   ✅ 全标脏 = "下次进哪页拉哪页"（多几路 GET），代价可忽略，**永不漏拉**。 */
function markCrossPageStale() { LOADED.clear(); }

/** 按需取数：把 `labels` 里**还没拉过**的几路拉回来（依赖路放**第二组**）。 */
async function loadPaths(labels) {
  const fresh = (labels || []).filter(l => ALWAYS_FRESH.has(l) || !LOADED.has(l));
  if (!fresh.length) return;
  /* ⭐ 批次 6：**先把这几路标成"正在拉"** ⇒ 页级状态才能把"还没回来"和"确实没有"分开
     （守则 §4.2「加载未完成不给最终数」）。⚠️ `finally` 里**一定**要摘掉 —— 否则中途抛异常
     会把整页永久卡在"正在读取"（比空页更糟：用户连重试的机会都没有）。 */
  fresh.forEach(l => PENDING.add(l));
  try {
    await Promise.all(fresh.filter(l => !LOAD_DEP.has(l)).map(l => soft(l, LOADERS[l])));
    await Promise.all(fresh.filter(l => LOAD_DEP.has(l)).map(l => soft(l, LOADERS[l])));
  } finally {
    fresh.forEach(l => PENDING.delete(l));
  }
  fresh.forEach(l => LOADED.add(l));
  BOOT_ERROR = fails.join('；');
  render();                          /* 各路内部多数已 render 一次；这里兜一次（幂等） */
  if (BOOT_ERROR) bootErrorBanner();
}

/* ⭐⭐⭐ 2026-09-27（`TAIL-117` 批次 6「四态统一」· 守则 §4.2 / §3.3 / §2.2 / §5.9）：
   **页级状态只有一个出口** —— 「这一页现在该显示什么」由本件说了算，⛔ 别在各页 `V.*` 里各判一次。

   为什么必须做（本批开工时的实测）：壳是「进哪页拉哪页」，而 `render()` **不看取数回来了没有**
   ⇒ 数据没到的那一瞬，页面画的是**空表 / 0 / 空图** —— 与"确实没有数据"**长得一模一样**。
   用户看到"这月没有付款"时，没法分辨**是真的没有**还是**还没取回来**（守则 §4.2 明禁）。

   四态（`kind`）与判据：
     · `loading`：本页依赖的路**此刻正在拉**（`PENDING`）或**启动还没收尾**（`BOOTING` 且该路没拉过）
     · `error`  ：本页依赖的路里**有坏了的**（`FAILED`）⇒ 说清"哪一块没取到" ＋ 给「重试」
     · `ready`  ：其余（含"这页本来就不取数"：`PAGE_LOAD` 没有这一页）
   ⚠️ **只认"本页依赖的那几路"**（`PAGE_LOAD[VIEW]`）—— ⛔ 别拿"全局有没有失败"当判据：
      别页坏了不该让这一页变成错误页（那是"某一项失败拖垮全站"，本仓 2026-09-17 踩过）。
   ⚠️ **只认 `PENDING`，⛔ 不拿"未 `LOADED`"当加载态**：写动作会 `LOADED.clear()`
      （`markCrossPageStale`），而它只 reload 自己那页 ⇒ 拿"未 LOADED"判就会**永久卡住**。 */
function pageState() {
  const deps = PAGE_LOAD[VIEW] || [];
  const failed = deps.filter(l => FAILED.has(l));
  if (failed.length) return { kind: 'error', failed: failed, why: failed.map(l => `${l}：${FAILED.get(l)}`) };
  const waiting = deps.filter(l => PENDING.has(l) || (BOOTING && !LOADED.has(l)));
  if (waiting.length) return { kind: 'loading', waiting: waiting };
  return { kind: 'ready', deps: deps };
}

/** 页级状态页的 HTML（`loading` / `error`）—— 与 `pageState()` 成对，⛔ 别在别处另拼一份。 */
function pageGate(st) {
  const head = `<div class="card"><div class="ctr" style="padding:calc(34px * var(--fscale)) calc(18px * var(--fscale))">`;
  if (st.kind === 'loading') {
    return head + `<div class="mut"><b>正在读取这一页的数据…</b>`
      + `<div class="sm" style="margin-top:calc(6px * var(--fscale))">（${esc(st.waiting.join('、'))}）</div>`
      + `<div class="sm" style="margin-top:calc(6px * var(--fscale))">读完自动显示，不用刷新。</div></div></div></div>`;
  }
  return head + `<div><b class="dg">这一页的数据没能取到</b>`
    + `<div class="sm" style="margin-top:calc(6px * var(--fscale))">${st.why.map(w => esc(w)).join('<br>')}</div>`
    + `<div class="sm" style="margin-top:calc(8px * var(--fscale))">别的页照常可用（某一项取不到不该拖垮全站）。`
    + `先点「重试」；一直这样就把这一步告诉管理员。</div>`
    + `<div style="margin-top:calc(12px * var(--fscale))"><button class="btn pri" data-act="retryPage">重试</button></div>`
    + `</div></div></div>`;
}

/** 重试本页依赖的取数（页级错误态那个按钮的唯一落点）。 */
async function retryPage() {
  const deps = PAGE_LOAD[VIEW] || [];
  deps.forEach(l => { FAILED.delete(l); LOADED.delete(l); });
  await loadPaths(deps);
  render();
}

/** ⭐ 批次 6：**进页时先"预告"要拉哪几路** —— 这样 `render()` 的第一帧就能出「正在读取」，
   而不是先画一张空表、等数据回来再跳一下（守则 §4.2）。
   ⚠️ 只标"确实要拉的"（与 `loadPaths` 的 `fresh` 同一条筛选）—— ⛔ 多标了就会**永久卡住**
      （`loadPaths` 见 `fresh` 为空会直接 return，那个 `PENDING` 没人摘）。 */
function markPending(labels) {
  (labels || []).filter(l => ALWAYS_FRESH.has(l) || !LOADED.has(l)).forEach(l => PENDING.add(l));
}

async function boot() {
  /* 首屏只拉**初始视图**要的那几路（`home` ⇒ 3 路；其余页在 `go()` 里按需拉）。
     ⚠️ `BOOTING` 的声明在 `m05Sync` 上方（`P3`① 加的，⛔ 别在这里重复声明 —— 会 SyntaxError）。 */
  /* ⭐ 顶栏身份（`CUR`）与首屏取数**并发**发起 —— 身份不是"某一页的取数"，全站每一页都要它，
     所以它⛔ 不进 `PAGE_LOAD`；⛔ 也不用 `Promise.all`（那条红线是防"退回全量拉 13 路"的形态，
     见 `test_wired_boot.py`）⇒ 先**发起**、首屏拉完再**收**它。 */
  const who = soft('当前登录用户', reloadWho);
  /* ⭐ 批次 6：**先把"正在读取"这一帧画出来**（⛔ 别等数据回来才有第一帧）——
     改前首屏在数据到位前 `#view` 是**空的**，用户看不出"是在读"还是"这页没东西"。 */
  markPending(PAGE_LOAD[VIEW] || []);
  render();
  await loadPaths(PAGE_LOAD[VIEW] || []);
  await who;
  /* ⚠️ `loadPaths` 自己也赋了一次 —— 两路并发时"它收尾在前、我这路失败在后"就会被漏掉 ⇒ 这里兜一次 */
  BOOT_ERROR = fails.join('；');
  BOOTING = false;        /* ⏳ `P3`①：启动收尾才允许 `m05Sync()` 补拉（见它的注释） */
  render();
  if (BOOT_ERROR) bootErrorBanner();
}

/* ⚠️ 取数失败 ⇒ **在页面上常驻说明**（⛔ 不只 toast —— 它一闪而过，用户只看到"页面是空的"、
   还以为功能没做）。最常见原因 = **用 `file://` 双击打开了这个文件**：浏览器禁止 `file://`
   页面读后端接口 ⇒ 数据必然空。⭐ 实测踩到：展示壳时预览面板打开的正是
   `file:///…/app/web/index.html`，于是"看起来和原型没区别、还没有数据"。 */
function bootErrorBanner() {
  /* ⭐ 2026-09-27（`TAIL-117` 批次 1 · 守则 §3.1 / §3.7 / §5.9）：横幅**分两截** ——
     ① 可见区**只放人话 ＋ 下一步**（`BOOT_ERROR` 里的 `e.message` 已经过 `api.js` 的人话出口）；
     ② 原始串（`GET /api/… → HTTP 500`）折进「技术明细」，排障要看就展开
        —— 守则 §5.8：换地方，⛔ 不是删掉。 */
  const det = failsTech.length
    ? '<details style="margin-top:calc(6px * var(--fscale))"><summary style="cursor:pointer">技术明细（给管理员看）</summary>'
      + '<div style="font-family:var(--fm);font-size:calc(11px * var(--fscale));margin-top:calc(4px * var(--fscale))">'
      + failsTech.map(t => esc(t)).join('<br>') + '</div></details>'
    : '';
  const why = location.protocol === 'file:'
    ? '你正在用 <b>file:// 直接打开这个 HTML 文件</b> —— 浏览器不许它读系统数据，所以页面是空的。'
    : '这几项没能取到：<br><span class="fc">' + esc(BOOT_ERROR) + '</span><br>'
      + '<b>其余页的数据照常可用</b>（某一项失败不该拖垮全站）。'
      + '<b>下一步</b>：刷新页面重试；若一直这样，请把下面的「技术明细」发给管理员。' + det;
  const el = document.createElement('div');
  el.className = 'tip dg';
  /* ⭐⭐ `TAIL-182`（`A` 案 · 2026-09-29 **用户裁定**）：**不许再盖住内容**。
     原先这里是 `position:fixed;left:0;right:0;top:0;z-index:9999` ⇒ 整带宽横幅**压在页面之上** ⇒
     页首那一带的**卡头按钮全都点不着**（真机实测：`#jcTradeBtn` 被它挡住，Playwright 报
     `intercepts pointer events` 连重试 57 次；`elementFromPoint` 拿到的正是它）——
     守则 `§4.6` 的反例原文就是「提示条盖住可点区（本仓真例：`.toast` 吃掉浮层点击）」，**同一族**。
     ⇒ 改成**进布局流**：插在 `main` 里、`#view` 之前 ＋ `flex:0 0 auto` ⇒ 它**占位**、把内容往下推。
     ⚠️ **为什么不能挂 `body`**：`html,body{height:100%;overflow:hidden}` ＋ `.app{height:100vh}` ⇒
        挂上去会**溢出被裁**（真机量过）；`.view` 才是那个自己滚的容器。
     ⚠️ 它**不会滚走**（比原先更省心）：真正的滚动容器是 `.view`，而本横幅是它的**兄弟节点**
        （挂在 `main` 里、`#view` 之前）⇒ 用户滚内容时它**一直停在顶上**、又不压任何东西。 */
  el.style.cssText = 'flex:0 0 auto;margin:0;border-radius:0';
  el.innerHTML = `⚠️ <b>没拿到数据</b> —— ${why}<br>`
    + '请改用<b>服务地址</b>打开：<b>http://127.0.0.1:8000/app</b>'
    + '（粘到浏览器地址栏回车；⛔ 不要双击 HTML 文件）';
  const host = document.querySelector('.app > main');
  const view = document.getElementById('view');
  if (host && view && view.parentElement === host) host.insertBefore(el, view);
  else (host || document.body).prepend(el);        /* 兜底：结构没认出来时也把提示留在屏幕上 */
}

/* 启动 */
