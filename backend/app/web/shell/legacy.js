/* shell/legacy.js —— 壳接线层④：**「四个暂留件」的壳内实现**（`TAIL-27` · `§19` 收口 · 2026-09-21）
 *
 * 来源：`/m14/settings`（系统设置页）＋ `/m05/import*` · `/m06/import*` · `/m08/import*`（三个历史导入页）
 * —— 它们原先**只有服务端渲染页**、壳里**零入口** ⇒ 一直「暂留」删不掉（`§19` 只剩这一件）。
 * 本件把那四页的能力**原样搬进壳**，服务端那四个渲染件随之删除。
 *
 * ⭐ **为什么单开一件（而不是塞进 `core.js` / `actions.js`）**：本仓既定做法 =「**接线层可以加件，
 *    原型切片一行不动**」——这四个页是**壳新增**的（`demo/` 原型里根本没有它们）⇒
 *    `ui_parity` 的 `U1`（只比原型**同名** `V.*` 切片）**看不见本件** ⇒ **零漂移风险**。
 *
 * ⛔ **本件不许碰的东西**：任何 `V.<原型页>` 切片 · `ACT` 里既有动作 · `CHG` 里既有项
 *    （都是**追加**：`V.set = …` / `ACT.xxx = …` / `CHG.push(…)`）。
 * ⚠️⚠️ **加载顺序有严格要求**（`index.html` 里的 `<script src>` 顺序即真源）：
 *    ① 在 `actions.js` **之后** —— 本件要往 `ACT` / `CHG` 上追加；
 *    ② 在 `core.js` **之前** —— `core.js` 的 `LOADERS` 表**加载期就求值**到 `reloadSet` 这几个名字，
 *       而它们住在本件里。⭐ 实测踩到：放在 `core.js` 之后 ⇒ `reloadSet is not defined` ⇒
 *       `core.js` **整支中止**（`boot` 都没定义）⇒ 页面一片空白、看板一行数据都没有，
 *       而离线断言（含 `node --check`）**全绿** —— 只有真机 console 才看得见。
 *
 * ⚠️ 取的数一律走 `API`（`core.js`：唯一数据出口）；`PAGE_LOAD` / `LOADERS` 两张表在 `core.js` 里追加。
 * ⚠️ 判定**一行都不在壳里**：格式校验 / 落库 / 留痕 / 批量回滚 / 幂等刷新全在后端（各模块 JSON API）。
 */

/* ============================================================ 状态（暂留件各一份） */

/* ⚠️ 一律 `const 对象 + 原地改字段`（⛔ 不整对象重新赋值）：外部（自检 / 动作）持有的是对象引用
   —— 这条教训本仓记过（见 `actions.js` 里 `fJc` 那句）。
   ⛔ `IMP05`（历史付款导入旧页的状态）**已随该页下架删除**（`TAIL-75` `B5b` 第三步 · 2026-09-23
      用户裁定 `B`：同一件事只留一个入口 ⇒ 走通用面 `/api/imp/m05_flow/*`，见 `V.imp`）。 */
const SET = {items: [], logs: [], tips: [], errs: [], msg: '', kind: 'ok'};   /* 系统设置 */


/* ============================================================ 取数（标签 → 函数 见 core.js 的 LOADERS） */

async function reloadSet() {
  const d = await API.m14Settings();
  SET.items = d.items || []; SET.logs = d.logs || []; SET.tips = d.tips || [];
}


/* ============================================================ 小工具（⛔ 只在本件内用，不污染全局语义） */

/* 回执条：`kind` = ok / wn / err（与后端 `message` 的中文原因**原样**呈现，⛔ 不吞）。 */
const lgNotice = s => (s.msg
  ? `<div class="tip ${s.kind === 'err' ? 'dg' : (s.kind === 'wn' ? 'wn' : 'ok')}">${esc(s.msg)}</div>` : '');
/* 三步条：`at` = 当前第几步（0/1/2）。 */
const lgSteps = (steps, at) => `<div class="steps">` + steps.map((t, i) =>
  `<div class="st ${i === at ? 'on' : (i < at ? 'dn' : '')}">${esc(t)}</div>`).join('') + `</div>`;
/* 选文件那一行（三个导入页同款）——⚠️ **文件对象存状态里**（`render()` 会重建 input ⇒ 只靠 input 会丢）；
   ⇒ 「解析」按钮的可用性看**状态里那个文件**，⛔ 不看 input 的 `files`（那正是"选完文件按钮还是灰的"的来源）。 */
function lgPick(id, pickAct, parseAct, file, tip) {
  return `<div class="fbar" style="border:1px solid var(--bd);border-radius:var(--r)">`
    + `<div class="fi"><label>选文件（.xlsx）</label>`
    + `<input class="inp" type="file" id="${esc(id)}" accept=".xlsx" data-act="${esc(pickAct)}"></div>`
    + `<div class="fi"><label>&nbsp;</label>`
    + `<button class="btn pri" data-act="${esc(parseAct)}"${file ? '' : ' disabled'}>解析并预览（不写库）</button></div>`
    + `<div class="fi"><label>&nbsp;</label><span class="mut sm">${file
      ? `已选：<b class="fc">${esc(file.name)}</b>（${Math.max(1, Math.round(file.size / 1024))} KB）`
      : esc(tip || '只读第一个工作表')}</span></div></div>`;
}
/* 空态行（跨列数由调用方给）。 */
const lgEmpty = (cols, text) => `<tr><td colspan="${cols}" class="ctr mut" style="padding:18px">${esc(text)}</td></tr>`;
/* 域补充区块（`TAIL-75` `B5b` 第三步：**通用面给域留的口子** —— 域侧补"只有它自己算得出"的几块，
   如历史付款流水的「未匹配清单」与「核对报告」）。
   ⚠️ 一律**通用渲染**（题 ＋ 说明 ＋ 表）：⛔ 壳里**不许出现任何域名 / 列名** ——
      那全由**后端**（域钩子 `Hooks.preview` / `commit` 的回执）给 ⇒ 加一个域不必改本页。 */
function lgBlocks(blocks) {
  return (blocks || []).map(b => `<div style="margin-top:12px">
    <h4 style="font-size:12.5px;margin:0 0 5px">${esc(b.title || '')}</h4>
    ${b.note ? `<p class="mut sm" style="margin:0 0 5px">${esc(b.note)}</p>` : ''}
    <div class="tw" style="max-height:260px;min-height:0"><table class="dt"><thead><tr>
      ${(b.columns || []).map(c => `<th>${esc(c)}</th>`).join('')}</tr></thead><tbody>
      ${(b.rows || []).length
        ? b.rows.map(r => `<tr>${(r || []).map(c =>
            `<td>${esc(c == null ? '' : String(c))}</td>`).join('')}</tr>`).join('')
        : lgEmpty((b.columns || []).length || 1, b.empty || '（无）')}</tbody></table></div></div>`).join('');
}

/* ============================================================ `V.set` —— 系统设置（§7.8） */

V.set = () => {
  const items = (SET.items || []).map(it => {
    const src = it.stored
      ? `<span class="tag t-pri">本页所设</span>` : `<span class="tag t-in">.env</span>`;
    const meta = it.stored
      ? `当前生效：<b class="fc">${esc(it.effective)}</b>（本页所设；清空输入框并保存即回落到 <code>.env</code>）`
      : (it.env ? `未在本页设置 ⇒ 当前用 <code>.env</code> 的值：<b class="fc">${esc(it.env)}</b>`
        : `未在本页设置，且 <code>.env</code> 也是空的`);
    return `<div class="fld" style="border:1px solid var(--bd);border-radius:8px;padding:10px 12px">
      <label>${esc(it.label)} ${src}</label>
      <input class="inp" data-k="${esc(it.key)}" value="${esc(it.stored)}"
        placeholder="${esc(it.env)}" autocomplete="off">
      <div class="hint">${em(it.hint)}</div>
      <div class="hint mut">${meta}</div></div>`;
  }).join('');
  const tips = (SET.tips || []).map(t => `<li>${em(t)}</li>`).join('');
  const rows = (SET.logs || []).map(l => `<tr><td class="now">${esc(l.at)}</td><td class="fc">${esc(l.key)}</td>
    <td>${esc(l.old) || '（空）'}</td><td>${esc(l.new) || '（空）'}</td><td>${esc(l.operator) || '—'}</td></tr>`).join('');
  const errs = (SET.errs || []).length
    ? `<div class="tip dg">${SET.errs.map(e => esc(e)).join('<br>')}</div>` : '';
  /* ⭐ **外观主题**（`ACC-UI-THEME-001/001-06`）—— 用户 2026-09-21 两次裁定的合体：
     ① 「移进 `MOD-14` 更符合逻辑」② 「**不要某一套的色板预览**，要**每一套的主题色**，
        旁边显示颜色值，颜色点要**圆形**，观感要高级一点」。
     ⚠️ 它**按用户**保存（判据要的是"A 与 B 各挑各的"）⇒ 所以它**不进** `SET.items`
        （那是"会变、且与「谁的账号」无关的连接参数"，`ACC-CFG-SETUP-001/001-01`）—— 它只是**住在本页**的一张卡片。
     ⛔ 也别把它改成系统级配置：那会把「按用户隔离」这条判据做没。
     ⭐ 切换**就地生效、不刷新页面**（`ACT.themeSet` → `applyThemeLive()`）。
     ⭐⭐ **每套一张"配色标本"卡**：卡面用它**自己那套**的 底色/文字/边框 画（取值由**后端**从唯一真源解析出来），
        左边一个**圆形主色点**、旁边是**主色色值** ⇒ 明暗差异**一眼可见**
        —— 这正是用户"**感觉不到颜色变化**"的解药（浅色那几套只差一个主色，在满屏表格里根本看不出来）。 */
  const pcard = p => {
    const on = p.name === CUR_THEME;
    return `<button class="thcard${on ? ' on' : ''}" data-act="themeSet" data-theme="${esc(p.name)}"
        title="${esc(p.name)}｜适用：${esc(p.scene)}｜风格：${esc(p.style)}（点了即时生效）"
        style="background:${p.bg};color:${p.tx};border-color:${on ? p.pri : p.bd}">
      <span class="thdot" style="background:${p.pri}"></span>
      <span class="thmeta">
        <b>${esc(p.name)}</b>
        <i class="thhex">${esc(p.pri)}</i>
        <i class="thscene">${esc(p.scene)}</i>
      </span>
      ${on ? `<span class="thck" style="color:${p.pri}">✓</span>` : ''}
    </button>`;
  };
  const themeCard = `<div class="card"><h4>外观主题
    <span class="sp mut sm">按<b>你的账号</b>保存 · 只改你自己看到的样子（§7.7）</span></h4>
    <div class="bd">
      <p class="mut sm" style="margin:0 0 9px">点一张卡**立即生效** —— ⛔ 不刷新页面、也不会把你踢回别的页。
        每张卡用它<b>自己那套的底色与文字色</b>画的 ⇒ 明暗差异一眼可见；左边<b>圆点 = 该套主色</b>，旁边是色值。</p>
      <div class="thgrid">${THEME_PALETTE.map(pcard).join('')
        || '<span class="mut">（取不到主题清单 —— 见顶部横幅）</span>'}</div>
      <p class="mut sm" style="margin-top:9px">当前：<b class="fc">${esc(CUR_THEME) || '默认'}</b>　·　
        ⚠️ 主题**只管屏幕**：打印件与导出的 Excel 颜色与它无关（§7.7）。</p>
    </div></div>`;
  return `<details class="tip"><summary>口径说明（§7.8：本页只放会变、且变的时候不该改文件重启的连接参数）</summary>
      <ul style="margin:6px 0 0 18px;line-height:1.8">${tips}</ul></details>
    ${lgNotice(SET)}${errs}
    <div class="card"><h4>连接参数<span class="sp mut sm">改动一律留痕（改前 / 改后 / 改动人 / 时间）</span></h4>
      <div class="bd">${items || '<div class="mut">（取不到设置项 —— 见顶部横幅）</div>'}
        <div style="margin-top:6px"><button class="btn pri" data-act="setSave">保存</button>
          <span class="mut sm" style="margin-left:8px">清空某一项 = 该项回落到 <code>.env</code>（空值合法）</span></div>
      </div></div>
    <div class="card"><h4>变更留痕<span class="sp mut sm">最近 ${(SET.logs || []).length} 条</span></h4>
      <div class="bd np"><div class="tw" style="max-height:320px;min-height:0"><table class="dt"><thead><tr>
        <th>时间</th><th>设置项</th><th>改前</th><th>改后</th><th>改动人</th></tr></thead>
        <tbody>${rows || lgEmpty(5, '还没有改动记录')}</tbody></table></div></div></div>
    ${themeCard}`;
};

/* ============================================================ ⛔ `V.m05imp` —— **已下架**（`TAIL-75` `B5b` 第三步）
 * `m05imp`（历史付款导入页）＋ `reportHtml()`（它的核对报告渲染）**整段删除**（2026-09-23 **用户裁定 `B`**）：
 *   同一件事只留一个入口 —— 历史付款导入**走通用导入面**（`V.imp` 的 `m05_flow` 域）。
 * ⭐ **能力一处没丢，只是换了落点**：
 *   · 列说明 / 认列  → 通用面的**列映射**表（源列原⽂ ＋ 画像 ＋ 样本 ＋ 目标字段 ＋ 建议）；
 *   · ② 预览四块     → 通用面的**域补充区块**（后端 `imp_spec.preview` 给的 `blocks`／`kpis`，
 *                       壳由 `lgBlocks()` **通用渲染** —— ⛔ 壳里不写任何域名字/列名）；
 *   · ③ 核对报告     → 通用面**回执**里的域补充区块（`imp_spec._report_blocks`：漏记清单 ＋ **超付单列**）；
 *   · 整批回滚       → 通用面的 `impRollback`（同一批号）。
 * ⚠️ **口径变更已记账**：旧页按**源表列位置**读（无表头也读得动），通用面按**列名**认
 *   ⇒ 判据 `ACC-FLOW-IMPORT-001/001-01` 已按此改写（老台账若没有表头，请先补一行表头）。
 * ⛔ 后端 `/api/m05/import/*` 同批**连件删除**（`mod05_flow/import_api.py`）；⛔ 别再把它加回来。 */

/* ============================================================ 动作（**一律追加**到既有 `ACT` / `CHG`） */

/* 系统设置：保存（把**页面上那几个输入框**的值整批交后端 —— 校验 / 留痕 / 清缓存全在后端）。
   ⚠️ 输入框**不挂 `data-act`**（它们是整批提交的字段、不是逐字段动作）⇒ 不用进 `CHG`。 */
ACT.setSave = async () => {
  const body = {};
  document.querySelectorAll('#view input[data-k]').forEach(el => { body[el.dataset.k] = el.value; });
  SET.errs = []; SET.msg = '';
  let r = null;
  try { r = await API.m14SettingsSave(body); }
  catch (e) { SET.msg = `保存失败：${String((e && e.message) || e)}`; SET.kind = 'err'; render(); return; }
  if (r && r.ok === false) { SET.errs = r.errors || ['后端未返回原因']; SET.msg = ''; render(); return; }
  SET.items = (r && r.items) || SET.items; SET.logs = (r && r.logs) || SET.logs;
  SET.msg = (r && r.message) || '已保存'; SET.kind = 'ok'; render();
};
/* ⛔ 付款导入的四个动作（`imp05Pick/Parse/Ok/Rollback`）**已随旧页下架删除**
   （`TAIL-75` `B5b` 第三步 · 2026-09-23 用户裁定 `B`）—— 那条路现在是通用面的
   `impParse / impPreview / impCommit / impRollback`（见下）。
   ⛔ `imp08*` 三个动作已随「库存单据手动导入」删除（2026-09-22 用户裁定；`T8` 守卫）。
   ⛔ `m06imp` 的 `imp06*` 也已删（`B5c`）。 */

/* ⚠️⚠️ **挂在表单元素上的动作必须进 `CHG`** —— 漏了 ⇒ `change` 被**静默丢弃**
   （症状：选完文件"解析"按钮永远是灰的 / 换项目没反应）。本仓踩过三次（`jcAmt` / `jcPartySet` / `themeSet`）。
   ⚠️ 只登记**表单元素**上挂的那几个（`<input type=file>` / `<select>`）——
      「解析并预览」是 `<button>`（走 click 委托），⛔ 不用进这里。 */
/* `#2`（2026-09-26）：那行「变更事件白名单」登记已废 —— 表单类动作不再需要登记 */
/* ⚠️ `impPj` **已从 `CHG` 里去掉**（2026-09-26）：它原来是挂在 `<select data-act="impPj">` 上的，
   现在「项目」换成**共用面板 `projPanel`（单选）** ⇒ 面板内的 `radio` 挂的是 `impPjPick`、
   展开/收起是 `impPjToggle`（都是 `<button>` / `radio`，走 click 委托）⇒ ⛔ 不用进 `CHG`。
   （`CHG` 只管 `<select>` / `<input type=file>` 这类 **change 事件**的控件。） */

/* =====================================================================
   `V.imp` —— 「**数据导入**」（通用导入面 · `TAIL-75` · `B5` · 2026-09-22）
   =====================================================================
   ⭐ 一页盖住**所有已挂通用面的域**（域清单由后端给：`/api/imp/domains`，⛔ 壳里不抄一份域清单）。
   ⭐ 四步：① 选域与文件 → ② **列映射** → ③ 预览校验 → ④ 确认落库（＋批次回滚）。

   ⚠️ 四条纪律（设计 §六）：
     ① **系统只出建议**：认出的列**预选**、认不出的**留空**（⛔ 不硬凑）；
     ② **落库前零写库**：②③ 只带 `token`（后端 `preview_store` 是唯一载具）；
     ③ **建议带依据与置信度**：界面上把"为什么这么认"照原话显示；
     ④ **记忆只是预填**：来自记忆的映射照样可改，并标明来源。
   ⚠️ 域的上下文（如过程资料的"这批进哪个项目"、付款计划的"归属年月"）走 `options` 递——见 `ACT.impCommit`。
      ⛔ 壳里**零域号分支**（也不再有域专属读端点）：一律调**通用面的** `options` 端点
     （`GET /api/imp/{domain}/options`，由域的 `Hooks.options` 给），**哪个域有哪些上下文由域自己说**
     （键在不在）⇒ 加一个域不用动壳。⚠️ 2026-09-26 收口：此前 `impSetDomain` / `ACT.impCommit` 里
     共有 **5 处** `IMP.domain === '…'` 分支（与这句注释不符 —— 注释当时是"目标"，实现没跟上）。
   ⛔ **`m06imp`（过程资料历史导入页）已下架**（`B5c` · 2026-09-22）：同一件事不留两个入口 ——
      `m05imp`（历史付款导入）**暂留**，等 `m05` 也挂上通用面再删（`B5c-2`）。 */
const IMP = {domains: [], domain: '', schema: null, file: null, token: '', cols: [], mapping: {},
             memory: '', preview: null, report: null, step: 0, org: [], wrap: '', cutoff: '',
             ym: '', pjDisp: {}, hasCut: false, hasYm: false,
             msg: '', kind: 'ok'};

const IMP_STEPS = ['① 选域与文件', '② 列映射', '③ 预览校验', '④ 确认落库'];
/* 映射表里「不导入」那一项的取值：⛔ 用**空串**而不是后端那个哨兵常量 ——
   后端 `_records` 见 `mapping_.get(src, IGNORE)`，空串是 falsy ⇒ 同样走"原样保留"那条路（实测口径），
   而抄一份哨兵字面量到壳里，一旦后端改了字面量，就会变成"把一个不存在的字段名当目标"（静默写脏）。 */
const IMP_IGNORE = '（不导入 · 原样保留）';

async function reloadImp() {
  const d = await API.impDomains();
  IMP.domains = (d && d.domains) || [];
  if (!IMP.domain && IMP.domains.length) await impSetDomain(IMP.domains[0].domain);
}

/* 切域 ⇒ 重取该域的**字段契约**，并把上一次的进度清干净（⛔ 不许残留上一域的文件/映射）。 */
async function impSetDomain(domain) {
  IMP.domain = String(domain || '');
  IMP.file = null; IMP.token = ''; IMP.cols = []; IMP.mapping = {}; IMP.memory = '';
  IMP.preview = null; IMP.report = null; IMP.step = 0; IMP.msg = '';
  IMP.org = []; IMP.wrap = ''; IMP.cutoff = ''; IMP.ym = '';
  pjClose('impPj'); IMP.pjDisp = {}; IMP.hasCut = false; IMP.hasYm = false;
  if (!IMP.domain) { IMP.schema = null; return; }
  IMP.schema = await API.impSchema(IMP.domain);
  await impLoadCtx();
}

/* ⭐ **域上下文**（候选项目 / 截止核算月 / 归属年月…）一律走通用面**唯一**一条读端点
   （`GET /api/imp/{domain}/options`，由域的 `Hooks.options` 给）—— 本页**零域号分支**。
   ⛔ 壳里不再有 `if (IMP.domain === 'xxx')` 这种分支、⛔ 也不再调域专属读端点。
   ⭐ 2026-09-26 用户报障后收口（原来集采域那一条分支调的是域专属端点 `/api/m11/list`，
      而它给的是**对象**，壳里 `(p && p.key) || String(p)` 在 `key` 为空串时把对象渲染成
      `[object Object]` ⇒ 真机实测 20 条候选里 3 条是坏的，选中即报「找不到项目」）。
   ⚠️ 没挂 `options` 的域该端点**没注册**（HTTP 404）⇒ 这里按"这个域没有上下文"处理，
      ⛔ 不报错、不拦路（域清单的主人在后端，壳不该认识"哪个域有上下文"）。 */
async function impLoadCtx() {
  let d = null;
  try { d = await API.impOptions(IMP.domain); }
  catch (e) { d = null; }                       /* 404 / 网络失败 ⇒ 都算"没有域上下文" */
  const ctx = (d && d.ok !== false) ? d : {};
  /* 候选项目的**两种历史形态**都能收（`m06`/`m11` 现在都给字符串键，`{key,display}` 也认）——
     ⚠️ 这里是**唯一**一处拍平；⛔ **空键一律丢弃**：空键渲染出来就是 `[object Object]`（本次报障的根因），
        而且 `project_id_by_key('')` 必然查不到 ⇒ 早丢早好，⛔ 不靠下游报错来兜。 */
  const raw = ctx.projects || [];
  IMP.org = []; IMP.pjDisp = {};
  raw.forEach(p => {
    const k = (typeof p === 'string' ? p : String((p && p.key) || '')).trim();
    if (!k) return;
    IMP.org.push(k);
    const disp = (typeof p === 'string' ? '' : String((p && p.display) || ''));
    if (disp) IMP.pjDisp[k] = disp;
  });
  IMP.wrap = ctx.warehouse || ctx.project_key || IMP.org[0] || '';
  /* ⭐ **哪个域要哪些上下文，由域自己说**（键在不在），壳按这个渲染控件 —— 这就是"加一个域不改壳"：
       `projects` ⇒ 项目选择 · `year_month` ⇒ 本批归属年月（`m04`）· `cutoff_ym` ⇒ 截止核算月（`m06`） */
  IMP.hasYm = Object.prototype.hasOwnProperty.call(ctx, 'year_month');
  IMP.hasCut = Object.prototype.hasOwnProperty.call(ctx, 'cutoff_ym');
  IMP.ym = IMP.hasYm ? String(ctx.year_month || '') : '';
  IMP.cutoff = IMP.hasCut ? String(ctx.cutoff_ym || '') : '';
}

V.imp = () => {
  const sch = IMP.schema;
  const doms = IMP.domains.map(d =>
    `<option value="${esc(d.domain)}"${d.domain === IMP.domain ? ' selected' : ''}>${esc(d.title)}</option>`).join('');
  const req = (sch && sch.required) || [];
  const got = Object.values(IMP.mapping || {}).filter(v => v);
  const lack = req.filter(f => !got.includes(f));
  /* 「键 → 显示」= **域给的展示名**优先，没有就原样显示仓库名。
     ⚠️ **刻意不无条件用 `PROJ_META_KEY`**：它要从**项目档案**（`PJs`）查展示名与归档状态，而
        「数据导入」页的 `page_load` 只有 `['数据导入']` ⇒ 档案**可能没加载** ⇒ 那样满屏黄字「未建档」，
        比原来的下拉还糟。`PJs` 恰好在（用户刚去过档案页）就用它 —— 能顺带标出**归档**与**未建档**。 */
  const impPjMeta = v => (PJs.length ? PROJ_META_KEY(v)
    : {nm: IMP.pjDisp[v] || v, warn: false, arc: false, title: '仓库名（§2.7.4）：' + v});
  /* 「项目」= **共用面板**（单选）—— 与 MOD-09 / 新增合同 / 台账导出（`ledPjPanel`）同款。
     ⚠️ 它渲染在本卡的 `fbar` 里、**不在 `.tw`（滚动容器）内** ⇒ 浮层不会被裁（同 `ledExpStrip` 的处置）。 */
  const impPjPanel = () => projPanel({list: () => IMP.org, selected: () => [IMP.wrap],
                                      pickAct: 'impPjPick', meta: impPjMeta, single: true});
  const head = `<div class="card"><h4>数据导入<span class="sp"><span class="mut sm">一次导一个域的一种表 ·
    落库前一个字节都不写库</span></span></h4><div class="bd">${lgSteps(IMP_STEPS, IMP.step)}
    <div class="fbar" style="border:1px solid var(--bd);border-radius:var(--r)">
      <div class="fi"><label>导入哪个域</label>
        <select class="inp" data-act="impDomain">${doms || '<option value="">（后端还没挂任何域）</option>'}</select></div>
      <div class="fi"><label>&nbsp;</label><span class="mut sm">${sch ? esc(sch.title) : '—'}</span></div></div>
    ${sch && sch.note ? `<div class="tip">${esc(sch.note)}</div>` : ''}
    ${sch && sch.keep_note ? `<div class="tip wn">${esc(sch.keep_note)}</div>` : ''}
    ${lgPick('iimp', 'impPick', 'impParse', IMP.file, '解析时自动挑「认得出表头」的那张工作表')}
    ${IMP.memory ? `<div class="tip ok">${esc(IMP.memory)}</div>` : ''}
  </div></div>`;

  /* ---- ② 列映射 ---- */
  /* ⭐⭐ **版式 = 转置**（2026-09-26 用户**第三次**说清，这是最终口径）：
     原话「我要**每个表头在列上**，你能明白么？**excel 里是列，本系统里也是列**；
     你做列映射一开始弄行，后来又弄卡片；**卡片也是你误解的**」
     ⇒ **每个源列 = 表里的一列**（源列名当**表头横排**，跟 Excel 一样），
       **属性在行上**（画像·样本 / 映射到 / 系统建议 / 依据）。
     ⛔ 之前两版都错：① 源列占**行**（一行一个源列，名字在行首）② 卡片网格。
     ⚠️ 判据与真机证据认 `<select data-act="impMap" data-src="…">`，⛔ 不许改这两个属性。 */
  let mapCard = '';
  if (IMP.cols.length) {
    const optsOf = (c) => {
      const cur = IMP.mapping[c.src] || '';
      const fields = ((sch && sch.fields) || []).map(f =>
        `<option value="${esc(f.label)}"${f.label === cur ? ' selected' : ''}>${esc(f.label)}${f.required ? '（必填）' : ''}</option>`).join('');
      return `<option value=""${cur ? '' : ' selected'}>${esc(IMP_IGNORE)}</option>` + fields;
    };
    const badge = (c) => {
      /* ⚠️ 「自动」那一档**不带数字**（用户《前端设计规则》§6：置信度只在"要人判断"时才有意义）；
         「需确认」才给分 —— 那才是他真要看的。 */
      if (c.field && c.level === 'auto') return '<span class="tag t-ok">自动</span>';
      if (c.field) return `<span class="tag t-wn">需确认 ${Number(c.conf).toFixed(2)}</span>`;
      if (c.ignored) return '<span class="tag t-in">不导入</span>';
      return '<span class="tag t-dg">认不出</span>';
    };
    /* ⚠️ 域声明了 `ignored` 的列（认得、但按口径**不导入**）**不进映射表**：它们不需要人选
       （域已定死），混在里面会把"要人做决定的列"淹掉（用户 2026-09-26 口径：不导入的**单独写**）。
       ⚠️ 而**认不出**的列要**留在表里**（它们正等人点下拉）。 */
    const toMap = IMP.cols.filter(c => !c.ignored);
    const skipped = IMP.cols.filter(c => c.ignored);
    /* 每行 = 一个**属性**（行首是属性名，其余各列 = 各源列该属性）—— 这就是"转置" */
    const attrRow = (label, cellOf) =>
      `<tr><th style="text-align:left;white-space:normal;min-width:104px" class="mut sm">${label}</th>`
      + toMap.map(c => `<td>${cellOf(c)}</td>`).join('') + '</tr>';
    mapCard = `<div class="card" style="margin-top:12px"><h4>列映射<span class="sp"><span class="mut sm">
      <b>横着一列一个源列</b>（照你 Excel 的样子）· 系统只给建议，决定权在你</span></span></h4>
      <div class="tw"><table class="dt sm">
      <thead><tr><th style="min-width:104px"></th>${toMap.map(c => `<th style="vertical-align:bottom;min-width:146px">
        <div style="font-weight:600">${esc(c.src)}</div>
        <div class="mut sm" style="font-weight:400;white-space:normal">${esc([c.profile, (c.samples || []).join(' / ')]
          .filter(Boolean).join(' · ')).slice(0, 52)}</div></th>`).join('')}</tr></thead>
      <tbody>
        ${attrRow('映射到', c => `<select class="inp" style="width:100%" data-act="impMap" data-src="${esc(c.src)}">${optsOf(c)}</select>`)}
        ${attrRow('系统建议', c => badge(c))}
        ${attrRow('依据', c => `<span class="mut sm">${esc(c.field ? (c.why || '') : '')}</span>`)}
      </tbody></table></div>
      ${skipped.length ? `<div class="tip" style="margin-top:10px"><b>这几列不导入</b>（原样保留，不需要你选）：
        ${skipped.map(c => `<div class="sm">· ${esc(c.src)} —— ${esc(c.ignored)}</div>`).join('')}</div>` : ''}
      <div class="tip ${lack.length ? 'wn' : 'ok'}" style="margin-top:10px">${lack.length
        ? `还差必填字段：<b>${esc(lack.join(' / '))}</b> —— 选好才能到下一步（⛔ 系统不替你填默认值）`
        : '必填都齐了，可以往下走'}</div>
      <div style="margin-top:10px">
        <button class="btn pri" data-act="impPreview"${lack.length ? ' disabled' : ''}>③ 预览校验（不写库）</button>
        <button class="btn" data-act="impReset">重来</button></div></div>`;
  }

  /* ---- ③ 预览校验 ---- */
  let prevCard = '';
  if (IMP.preview) {
    const p = IMP.preview;
    const probs = (IMP.problems || []);
    /* ⭐ **域上下文那一栏 = 按域给的键渲染**（⛔ 壳里不看域号）：
         · `projects`   ⇒ 「这批数据进哪个项目」= **共用项目面板（单选）**（⛔ 全站不得自造项目控件）
         · `year_month` ⇒ 「本批归属年月」（`m04`：这批全归该月，§4.3.3；落库**必填**）
         · `cutoff_ym`  ⇒ 「截止核算月」（`m06` 的历史段分界，§5.2.5）
       ⚠️ 2026-09-26 所修（用户报障）：原先这里是 `IMP.domain === 'm04_plan' ? 年月 : (项目 ＋ 截止核算月)`
          —— 两处毛病：①「项目」是**自造的原生下拉**（全站约定是共用面板，10 处都在用它）；
          ②**截止核算月被画给了所有域**，而集采/付款计划的落库根本不读它（`ACT.impCommit` 给的上下文包里
          它只是空转）⇒ 用户填了**不生效**，属于"让人以为能改"的死控件。 */
    const ctxBar = (IMP.org.length || IMP.hasYm || IMP.hasCut)
      ? `<div class="fbar" style="border:1px solid var(--bd);border-radius:var(--r)">
        ${IMP.org.length ? `<div class="fi pjwrap" style="position:relative">
          <label>这批数据进哪个项目（键 = 仓库名，§2.7.4）</label>
          <button class="btn" data-act="impPjToggle" style="min-width:186px;display:inline-flex;align-items:center;justify-content:space-between;gap:8px"><span>${esc(IMP.wrap ? (IMP.pjDisp[IMP.wrap] || IMP.wrap) : '请选择项目')}</span><span class="mut" style="font-size:9px">▼</span></button>
          ${pjIsOpen('impPj') ? impPjPanel() : ''}</div>` : ''}
        ${IMP.hasYm ? `<div class="fi"><label>本批归属年月（§4.3.3 —— 这批数据全归该月）</label>
          <input class="inp" id="impYm" value="${esc(IMP.ym || bjMonth())}" placeholder="2026-09"></div>` : ''}
        ${IMP.hasCut ? `<div class="fi"><label>截止核算月（历史段分界）</label>
          <input class="inp" id="impCut" value="${esc(IMP.cutoff)}" placeholder="留空 ⇒ 取本批最大月"></div>` : ''}
        </div>` : '';
    const prows = (p.preview || []).slice(0, 12).map(r => `<tr>${Object.keys(r).filter(k => k !== '_row')
      .map(k => `<td class="now">${esc(String(r[k] == null ? '' : r[k]))}</td>`).join('')}</tr>`).join('');
    const pcols = p.preview && p.preview.length
      ? Object.keys(p.preview[0]).filter(k => k !== '_row').map(k => `<th>${esc(k)}</th>`).join('') : '';
    prevCard = `<div class="card" style="margin-top:12px"><h4>预览校验<span class="sp"><span class="mut sm">
      这一步**一个字节都不写库**</span></span></h4><div class="kpis">
      <div class="kpi"><div class="k">将写入</div><div class="v">${p.writable == null ? p.total : p.writable}</div>
        <div class="s">行</div></div>
      <div class="kpi"><div class="k">待处理</div><div class="v">${p.problem_count || probs.length}</div>
        <div class="s">处（行/列/原值/原因）</div></div>
      <div class="kpi"><div class="k">本步写库量</div><div class="v">0</div><div class="s">确认前零写库</div></div>
      ${Object.keys(p.kpis || {}).map(k => `<div class="kpi"><div class="k">${esc(k)}</div>
        <div class="v">${esc(String(p.kpis[k]))}</div></div>`).join('')}</div>
      ${probs.length ? `<div class="tw" style="max-height:200px"><table class="dt sm">
        <thead><tr><th>行</th><th>列</th><th>原值</th><th>原因</th></tr></thead><tbody>
        ${probs.slice(0, 30).map(x => `<tr><td class="now">${esc(x.row)}</td><td class="now">${esc(x.column)}</td>
          <td class="now">${esc(x.raw)}</td><td>${esc(x.reason)}</td></tr>`).join('')}</tbody></table></div>
        <div class="tip wn" style="margin-top:8px">这些问题**不影响其余行落库**；认不出的值一律原样留着给人看，⛔ 不静默改成 0/空。</div>`
      : '<div class="tip ok">没有发现问题行</div>'}
      ${ctxBar}
      ${lgBlocks(p.blocks)}
      <div class="tw" style="max-height:260px;margin-top:10px"><table class="dt sm">
        <thead><tr>${pcols}</tr></thead><tbody>${prows || lgEmpty(1, '没有数据行')}</tbody></table></div>
      <div style="margin-top:10px"><button class="btn pri" data-act="impCommit">④ 确认落库</button>
        <button class="btn" data-act="impReset">重来</button></div></div></div>`;
  }

  /* ---- ④ 结果与批次回滚 ---- */
  let repCard = '';
  if (IMP.report) {
    const r = IMP.report;
    /* ⚠️ 回执的 KPI 只取**标量**项：`kpis` / `blocks` 是域补充块（下面专门画），
       混进 KPI 会渲染成 "[object Object]"（实测踩到过）。 */
    const scalar = k => r[k] == null || ['string', 'number', 'boolean'].includes(typeof r[k]);
    repCard = `<div class="card" style="margin-top:12px"><h4>落库结果</h4><div class="bd">
      <div class="kpis">${Object.keys(r).filter(scalar).map(k => `<div class="kpi"><div class="k">${esc(k)}</div>
        <div class="v">${esc(String(r[k]))}</div></div>`).join('')}
        ${Object.keys(r.kpis || {}).map(k => `<div class="kpi"><div class="k">${esc(k)}</div>
          <div class="v">${esc(String(r.kpis[k]))}</div></div>`).join('')}</div>
      ${r.batch ? `<div class="tip ok">批次 <b class="fc">${esc(r.batch)}</b>
        <button class="btn sm" data-act="impRollback" data-batch="${esc(r.batch)}">整批回滚</button></div>` : ''}
      ${lgBlocks(r.blocks)}
      <div style="margin-top:10px"><button class="btn" data-act="impReset">再导一份</button></div></div></div>`;
  }

  return `${lgSteps(IMP_STEPS, IMP.step)}${lgNotice(IMP)}${head}${mapCard}${prevCard}${repCard}`;
};

/* 切域（表单元素 ⇒ 已在 `CHG` 里登记） */
ACT.impDomain = async t => {
  IMP.msg = '';
  try { await impSetDomain(t.value); }
  catch (e) { IMP.msg = `取域契约失败：${String((e && e.message) || e)}`; IMP.kind = 'err'; }
  render();
};
ACT.impPick = t => { IMP.file = (t.files || [])[0] || null; IMP.msg = ''; render(); };
ACT.impReset = () => { IMP.file = null; IMP.token = ''; IMP.cols = []; IMP.mapping = {};
  IMP.memory = ''; IMP.preview = null; IMP.report = null; IMP.step = 0; IMP.msg = ''; pjClose('impPj');
  render(); };
/* ① → ②：解析（不写库）。预选 = 后端给的建议；**记忆命中的映射盖在建议之上**（并标明来源）。 */
ACT.impParse = async () => {
  if (!IMP.file || !IMP.domain) return;
  IMP.msg = '正在解析（预览阶段不写库）…'; IMP.kind = 'ok'; render();
  const fd = new FormData(); fd.append('file', IMP.file); fd.append('sheet', '');
  let r = null;
  try { r = await API.impParse(IMP.domain, fd); }
  catch (e) { IMP.msg = `解析失败：${String((e && e.message) || e)}`; IMP.kind = 'err'; render(); return; }
  if (!r || r.ok === false) { IMP.msg = (r && r.message) || '解析失败'; IMP.kind = 'err'; render(); return; }
  IMP.token = r.token; IMP.cols = r.cols || []; IMP.step = 1; IMP.preview = null; IMP.report = null;
  IMP.mapping = {};
  (r.cols || []).forEach(c => { if (c.field) IMP.mapping[c.src] = c.field; });
  IMP.memory = '';
  if (r.memory && r.memory.mapping) {
    Object.keys(r.memory.mapping).forEach(src => { IMP.mapping[src] = r.memory.mapping[src]; });
    IMP.memory = r.memory.note || '来自记忆 · 可改';
  }
  IMP.msg = r.dupes && Object.keys(r.dupes).length
    ? `⚠️ 有字段被多列认到：${Object.keys(r.dupes).map(k => `${k}←${(r.dupes[k] || []).join('、')}`).join('；')}` : '';
  IMP.kind = IMP.msg ? 'wn' : 'ok';
  render();
};
ACT.impMap = (t) => { IMP.mapping[t.dataset.src] = t.value || ''; render(); };
/* 「项目」共用面板（**单选**）—— 第 11 个 `projPanel` 调用点。
   ⚠️ 展开是 `<button>`、选择是面板内的 `radio` ⇒ 都走 **click 委托**，⛔ 不进 `CHG`
      （`CHG` 只管 `<select>` / `<input type=file>` 那种 **change** 事件）。 */
ACT.impPjToggle = () => { pjToggle('impPj'); render(); };
ACT.impPjPick = t => { const v = (t && t.dataset && t.dataset.pj) || ''; if (!v) return;
  IMP.wrap = v; pjClose('impPj'); render();
  toast(`这批数据将导入项目 <b>${esc(IMP.pjDisp[v] || v)}</b>（键 = 仓库名，§2.7.4）`); };
/* ② → ③：预览（不写库） */
ACT.impPreview = async () => {
  IMP.msg = '正在校验（预览阶段不写库）…'; IMP.kind = 'ok'; render();
  let r = null;
  try { r = await API.impPreview(IMP.domain, { token: IMP.token, mapping: IMP.mapping }); }
  catch (e) { IMP.msg = `预览失败：${String((e && e.message) || e)}`; IMP.kind = 'err'; render(); return; }
  if (!r || r.ok === false) { IMP.msg = (r && r.message) || '预览失败'; IMP.kind = 'err'; render(); return; }
  IMP.preview = r; IMP.problems = r.problems || []; IMP.step = 2; IMP.msg = ''; render();
};
/* ③ → ④：确认落库（`options` = 域上下文：过程资料要"进哪个项目"；`remember` = 记下这套映射） */
ACT.impCommit = async () => {
  const cut = document.querySelector('#impCut');
  const ym = document.querySelector('#impYm');
  /* ⭐ **上下文包 = 域声明的键一并给**（⛔ 壳里不再按域号挑那几个键 —— 2026-09-26 收口）：
     各域的 `commit` 只读它认识的那几个（`m06` 读 `warehouse` / `cutoff_ym`、`m04` 读 `year_month`、
     `m11` 读 `project_key`），多给的键对它只是**字典里的空转**。
     ⚠️ 壳**不知道**哪个域要哪个键（那是域的事）⇒ ⛔ 别再加回"`if (域号) 只给这几个`"的写法。 */
  const options = {warehouse: IMP.wrap, project_key: IMP.wrap,
                   cutoff_ym: (cut && cut.value) || '', year_month: (ym && ym.value) || bjMonth()};
  IMP.msg = '正在落库…'; IMP.kind = 'ok'; render();
  let r = null;
  try { r = await API.impCommit(IMP.domain, { token: IMP.token, mapping: IMP.mapping,
                                             remember: true, options: options }); }
  catch (e) { IMP.msg = `导入失败：${String((e && e.message) || e)}`; IMP.kind = 'err'; render(); return; }
  if (!r || r.ok === false) { IMP.msg = (r && r.message) || '导入失败'; IMP.kind = 'err'; render(); return; }
  IMP.report = r.report || {}; IMP.step = 3; IMP.msg = r.message || '已导入'; IMP.kind = 'ok';
  IMP.preview = null; IMP.token = ''; IMP.file = null;
  /* ⭐⭐ 2026-09-23（`TAIL-78` · 查 `TAIL-75` 落库下游时查出）：**导入是跨页写** ⇒ 这里必须
     **全标脏**（`LOADED.clear()`）。原先只删「机械 6 列 / 收发结存与大表」两路 —— 那是**旧导入页
     `m06imp`（已下架）**单域时代的遗留；`B5` 起导入已是**通用面**（域由后端 `/api/imp/domains` 列，⛔ 壳里不许再抄一份）。
     · **漏标的真后果**（实测路径）：`m05_flow` 落库走 `sync_stat_paid`（重算唯一出口）⇒ 改了
       付款通知书的「统计付款金额」⇒ m03 列表的「已付金额」与 m05 的欠款/台账/统计**都变了**，
       而 `LOADED` 记着"拉过了" ⇒ **切回那两页看到的是旧数**（对真数据说旧话，是本仓最忌的一类）。
     · ⛔ 也**不许**改成"补几个字面域名单"：域清单的主人在后端，壳侧列一份 = "加一个域要改两处"。
     ⇒ 壳侧最省心的**正确**做法 = 全标脏：下次进哪页拉哪页（多几路 GET），⛔ 永不漏拉。
     ⭐ **`#3`（2026-09-26）：这个清空搬进了写出口** —— `API.impCommit` 是**写出口**，`api.js` 里
     已经统一调 `markCrossPageStale()`（= `LOADED.clear()`）⇒ 本动作**不再自己写**
     （业务动作里手写清空 = "靠自觉"，下一个人还得记得写；判据见 `test_wired_boot.py`）。 */
  render();
};
ACT.impRollback = async t => {
  let r = null;
  try { r = await API.impRollback(IMP.domain, { batch: t.dataset.batch }); }
  catch (e) { IMP.msg = `回滚失败：${String((e && e.message) || e)}`; IMP.kind = 'err'; render(); return; }
  if (!r || r.ok === false) { IMP.msg = (r && r.message) || '回滚失败'; IMP.kind = 'err'; render(); return; }
  IMP.report = r.report || IMP.report; IMP.msg = r.message || '已回滚'; IMP.kind = 'wn';
  /* 同上（`TAIL-78`）：回滚也是**跨页写** —— `rollback_batch` 会逐个重算 `stat_paid`。
     ⭐ `#3`（2026-09-26）：清空**由写出口统一做**（`API.impRollback` ⇒ `api.js` 的 `markCrossPageStale()`），
     本动作⛔ 不再自己写（理由同上）。 */
  render();
};
