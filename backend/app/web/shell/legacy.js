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

/* ============================================================ 状态（四个页各一份） */

/* ⚠️ 一律 `const 对象 + 原地改字段`（⛔ 不整对象重新赋值）：外部（自检 / 动作）持有的是对象引用
   —— 这条教训本仓记过（见 `actions.js` 里 `fJc` 那句）。 */
const SET = {items: [], logs: [], tips: [], errs: [], msg: '', kind: 'ok'};   /* 系统设置 */
const IMP05 = {meta: null, file: null, token: '', preview: null, report: null, msg: '', kind: 'ok'};
const IMP06 = {meta: null, data: null, pj: '', file: null, token: '', preview: null,
               report: null, msg: '', kind: 'ok'};
const IMP08 = {meta: null, file: null, token: '', preview: null, result: null, msg: '', kind: 'ok'};

/* ============================================================ 取数（标签 → 函数 见 core.js 的 LOADERS） */

async function reloadSet() {
  const d = await API.m14Settings();
  SET.items = d.items || []; SET.logs = d.logs || []; SET.tips = d.tips || [];
}
async function reloadImp05() { IMP05.meta = await API.m05ImpMeta(); }
async function reloadImp06() { IMP06.meta = await API.m06ImpMeta(); await imp06Load(IMP06.pj); }
async function reloadImp08() { IMP08.meta = await API.m08ImpMeta(); }
/* 过程资料导入：切项目 ⇒ 重拉该项目的截止核算月与批次（**候选项目由后端给** —— `service.projects_of`）。 */
async function imp06Load(pj) {
  const d = await API.m06ImpData(pj || '');
  IMP06.data = d; IMP06.pj = String((d && d.warehouse) || '');
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
        <tbody>${rows || lgEmpty(5, '还没有改动记录')}</tbody></table></div></div></div>`;
};

/* ============================================================ `V.m05imp` —— 历史付款流水导入（§4.4.6） */

const IMP05_STEPS = ['① 列说明 ＋ 选文件', '② 预览（四块 · 不写库）', '③ 确认导入 ＋ 核对报告'];

V.m05imp = () => {
  const meta = IMP05.meta || {columns: [], max_rows: 0};
  const cols = (meta.columns || []).map(([letter, name, required]) =>
    `<tr><td class="ctr fc">${esc(letter)}</td><td>${esc(name)}</td>
      <td class="ctr">${required ? '<span class="tag t-wn">必填</span>' : '<span class="mut">可空</span>'}</td></tr>`).join('');
  let body = '';
  if (IMP05.preview) {
    const p = IMP05.preview;
    const w = (p.rows || []).map(r => `<tr><td class="fc">${esc(r.bill_no)}</td><td class="num">${esc(r.amount)}</td>
      <td class="now">${esc(r.pay_date)}</td><td>${esc(r.pay_method) || '<span class="mut">（空）</span>'}</td>
      <td>${esc(r.remark)}</td></tr>`).join('');
    const u = (p.unmatched || []).map(r => `<tr><td class="num">${esc(r.line)}</td><td class="fc">${esc(r.bill_no)}</td>
      <td class="num">${esc(r.amount)}</td><td class="now">${esc(r.pay_date)}</td></tr>`).join('');
    const a = (p.anomalies || []).map(x => `<tr><td class="num">${esc(x.line)}</td>
      <td class="fc">${esc(x.bill_no) || '—'}</td><td>${esc(x.reason)}</td></tr>`).join('');
    body += `<div class="card"><h4>② 预览 —— 尚未写库</h4><div class="bd">
      <div class="tip">将写入 <b>${p.writable}</b> 条；未匹配 <b>${(p.unmatched || []).length}</b> 条；
        异常 <b>${(p.anomalies || []).length}</b> 条${p.skipped_header ? '（检测到首行是表头，已自动跳过）' : ''}。
        ⛔ 未匹配 / 异常两类的行**不入库**。</div>
      <h4 style="font-size:12.5px;margin:10px 0 5px">将写入（前 300 行）</h4>
      <div class="tw" style="max-height:300px;min-height:0"><table class="dt"><thead><tr><th>单据号</th>
        <th class="num">付款金额</th><th>付款时间</th><th>付款方式</th><th>备注</th></tr></thead>
        <tbody>${w || lgEmpty(5, '（没有可写入的行）')}</tbody></table></div>
      <h4 style="font-size:12.5px;margin:12px 0 5px">未匹配清单（单据号在本地找不到 —— 多半是该月通知书还没抓）</h4>
      <div class="tw" style="max-height:260px;min-height:0"><table class="dt"><thead><tr><th>行</th>
        <th>单据号</th><th class="num">付款金额</th><th>付款时间</th></tr></thead>
        <tbody>${u || lgEmpty(4, '（无 —— 全部单据号都匹配上了）')}</tbody></table></div>
      <h4 style="font-size:12.5px;margin:12px 0 5px">异常清单（不入库）</h4>
      <div class="tw" style="max-height:260px;min-height:0"><table class="dt"><thead><tr><th>行</th>
        <th>单据号</th><th>原因</th></tr></thead><tbody>${a || lgEmpty(3, '（无）')}</tbody></table></div>
      <h4 style="font-size:12.5px;margin:12px 0 5px">未识别的付款方式取值（已归入「其他」、原文进备注）</h4>
      <p class="sm">${(p.unknown_methods || []).map(esc).join(' · ') || '（无）'}</p>
      <div style="margin-top:8px"><button class="btn pri" data-act="imp05Ok">确认导入（写库并记批次）</button>
        <span class="mut sm" style="margin-left:8px">同批重导须先整批回滚（幂等口径，§4.4.6）</span></div>
      </div></div>`;
  } else {
    body += `<div class="card"><h4>① 列说明（按位置取，从 A 列开始）</h4><div class="bd">
      <div class="tw" style="max-height:240px;min-height:0"><table class="dt"><thead><tr><th class="ctr">列</th>
        <th>填什么</th><th class="ctr">要求</th></tr></thead><tbody>${cols || lgEmpty(3, '（取不到列契约）')}</tbody></table></div>
      <p class="mut sm" style="margin-top:6px">• 首行若是表头会被自动跳过并提示。<br>
        • <b>付款方式可空</b>（不会替你填「现汇」）；填了但认不出的，会归入「其他」并<b>把原文留在备注</b>。<br>
        • 单据号必须是 i8 单据编码（形如 FKTZS2026090466）；<b>本地查不到的会列进「未匹配清单」</b>，不会静默丢掉。<br>
        • 上限 ${esc(meta.max_rows)} 行。</p>
      ${lgPick('i05f', 'imp05Pick', 'imp05Parse', IMP05.file, '只读第一个工作表')}</div></div>`;
  }
  if (IMP05.report) body += reportHtml(IMP05.report, 'imp05Rollback');
  return `${lgSteps(IMP05_STEPS, IMP05.preview ? (IMP05.report ? 2 : 1) : 0)}${lgNotice(IMP05)}${body}`;
};

/* 核对报告（**付款域与过程资料同款**：③ 两部分 + 整批回滚按钮）。
   ⭐ `P4` 超付处置第三半「**核对报告单列**」（§4.4.6）：漏记清单之外**另列一张超付清单** ——
      「实付合计 > 审批金额」的单据单列出来（判定在后端 `repository.notices_overpaid`，⛔ 壳里不算）。 */
function reportHtml(rep, rollAct) {
  const main = (rep.rows || []).map(r => `<tr><td class="fc">${esc(r.bill_no)}</td>
    <td class="now">${esc(r.doc_date)}</td><td>${esc(r.project_name)}</td>
    <td class="num">${M(r.amount_approved)}</td></tr>`).join('');
  const over = (rep.overpaid || []).map(r => `<tr><td class="fc">${esc(r.bill_no)}</td>
    <td class="now">${esc(r.doc_date)}</td><td>${esc(r.project_name)}</td>
    <td class="num">${M(r.amount_approved)}</td><td class="num">${M(r.amount_paid)}</td>
    <td class="num"><span class="tag t-dg">${M(r.over_amount)}</span></td></tr>`).join('');
  return `<div class="card"><h4>③ 核对报告<span class="sp mut sm">批次 <b class="fc">${esc(rep.batch)}</b>
      · 涉及月份 ${esc((rep.months || []).join('、')) || '—'}</span></h4><div class="bd">
    <div class="tip wn">其中 <b>${rep.count}</b> 张通知书**一条流水都没有**（供发现 Excel 漏记 —— 历史欠款能否对平就看它）：</div>
    <div class="tw" style="max-height:260px;min-height:0"><table class="dt"><thead><tr><th>单据号</th>
      <th>单据日期</th><th>付款项目</th><th class="num">审批金额</th></tr></thead>
      <tbody>${main || lgEmpty(4, '（无 —— 这些月份的每张通知书都有流水了）')}</tbody></table></div>
    <h4 style="font-size:12.5px;margin:14px 0 5px">超付清单（§4.4.6「核对报告单列」）—— 实付合计 <b>大于</b> 审批金额</h4>
    <p class="mut sm">⚠️ 流水**照记**（NC 侧确实付了，事实不得篡改）、统计付款金额**照实不封顶**；
      此处只**如实单列**，与 §4.4.4「付款动作禁止超付」不冲突（那条约束的是动作）。</p>
    <div class="tw" style="max-height:260px;min-height:0"><table class="dt"><thead><tr><th>单据号</th>
      <th>单据日期</th><th>付款项目</th><th class="num">审批金额</th><th class="num">实付合计</th>
      <th class="num">超出</th></tr></thead>
      <tbody>${over || lgEmpty(6, '（无 —— 本批月份里没有超付的单据）')}</tbody></table></div>
    <div style="margin-top:10px"><button class="btn" data-act="${esc(rollAct)}"
      data-batch="${esc(rep.batch)}">整批回滚后重导</button>
      <span class="mut sm" style="margin-left:8px">置撤销 ＋ 原因留痕、<b>不物理删</b>（§4.4.6）</span></div>
  </div></div>`;
}

/* ============================================================ `V.m06imp` —— 过程资料历史导入（§5.2.5 ①②） */

const IMP06_STEPS = ['① 列说明 ＋ 选文件', '② 预览（不写库）', '③ 确认导入 ＋ 核对报告'];

V.m06imp = () => {
  const d = IMP06.data || {projects: [], warehouse: '', cutoff_ym: '', batches: []};
  const meta = IMP06.meta || {material_labels: [], mech_labels: []};
  const opts = (d.projects || []).map(p =>
    `<option value="${esc(p)}"${p === d.warehouse ? ' selected' : ''}>${esc(p)}</option>`).join('');
  const proj = d.projects.length
    ? `<div class="fbar" style="border:1px solid var(--bd);border-radius:var(--r)"><div class="fi">
        <label>项目（导入到哪一个项目 · 键 = 仓库名，§2.7.4）</label>
        <select class="inp" data-act="imp06Pj">${opts}</select></div>
       <div class="fi"><label>&nbsp;</label><span class="mut sm">当前截止核算月：
        <b class="fc">${esc(d.cutoff_ym) || '（未设定 ⇒ 一律正式段）'}</b></span></div></div>`
    : `<div class="tip wn">还没有可导入的项目 —— 先在「库存单据」页抓一次库存单据明细
        （项目键 = <b>仓库名</b>，§2.7.4）。</div>`;
  let body = proj;
  if (IMP06.preview) {
    const p = IMP06.preview;
    const rows = (p.rows || []).map(r => `<tr><td class="now">${esc(r.ym)}</td>` +
      (meta.material_labels || []).map(k => `<td class="num">${esc(r[k]) || '—'}</td>`).join('') + `</tr>`).join('');
    const head = (meta.material_labels || []).map(k => `<th class="num">${esc(k)}</th>`).join('');
    const an = (p.anomalies || []).map(x => `<tr><td class="num">${esc(x.line)}</td>
      <td class="now">${esc(x.ym) || '—'}</td><td>${esc(x.reason)}</td></tr>`).join('');
    body += `<div class="card"><h4>② 预览 —— 尚未写库</h4><div class="bd">
      <div class="tip">项目 <b>${esc(p.warehouse)}</b> · 将写入 <b>${p.writable}</b> 个月
        （${esc((p.months || []).join('、')) || '—'}） · 异常 <b>${(p.anomalies || []).length}</b> 行。</div>
      <div class="tw" style="max-height:300px;min-height:0"><table class="dt"><thead><tr><th>核算月</th>${head}</tr></thead>
        <tbody>${rows || lgEmpty((meta.material_labels || []).length + 1, '（没有可写入的行）')}</tbody></table></div>
      <h4 style="font-size:12.5px;margin:12px 0 5px">异常清单（不入库）</h4>
      <div class="tw" style="max-height:240px;min-height:0"><table class="dt"><thead><tr><th>行</th>
        <th>核算月</th><th>原因</th></tr></thead><tbody>${an || lgEmpty(3, '（无）')}</tbody></table></div>
      <h4 style="font-size:12.5px;margin:12px 0 5px">列提示</h4>
      <p class="sm">⛔ 未导入的机械列：${(p.ignored_mech || []).map(esc).join(' · ') || '（无）'}
        （机械列<b>全段手录</b>，见「过程资料」页的机械手录区块）<br>
        未识别的列（已忽略）：${(p.unknown_headers || []).map(esc).join(' · ') || '（无）'}</p>
      <div class="fbar" style="border:1px solid var(--bd);border-radius:var(--r)"><div class="fi">
        <label>截止核算月</label>
        <input class="inp" id="i06cut" value="${esc(p.default_cutoff)}" placeholder="YYYY-MM"></div>
       <div class="fi"><label>&nbsp;</label><button class="btn pri" data-act="imp06Ok">确认导入（写历史段 ＋ 记批次）</button></div>
       <div class="fi"><label>&nbsp;</label><span class="mut sm">默认 = 导入数据里最大的核算月（§5.2.5 ①，一次设定、可改）</span></div></div>
      </div></div>`;
  } else {
    body += `<div class="card"><h4>① 列说明（按表头文字认列 · 列序不限）</h4><div class="bd">
      <div class="tw" style="max-height:200px;min-height:0"><table class="dt"><thead><tr><th>列</th>
        <th>填什么</th><th>要求</th></tr></thead><tbody>
        <tr><td>核算月</td><td>如 2026-08（也认 2026/8 · 202608）</td><td><span class="tag t-wn">必填</span></td></tr>
        <tr><td>材料列</td><td>${esc((meta.material_labels || []).join(' / '))}</td>
          <td><span class="tag t-wn">至少 1 列</span></td></tr></tbody></table></div>
      <p class="mut sm" style="margin-top:6px">• 表头可以带「金额」「（元）」等尾缀，会被自动去掉。<br>
        • ⛔ <b>机械 6 列不导入</b> —— 机械列全段<b>手录</b>（回「过程资料」页的机械手录区块录）。<br>
        • 只填了核算月、一个材料金额都没有的行会被列进「异常清单」（分不清「确实为 0」还是「漏填」）。<br>
        • 一列材料列都认不出来 ⇒ <b>整份拒绝</b>（那不像是过程资料的定稿文件）。</p>
      ${lgPick('i06f', 'imp06Pick', 'imp06Parse', IMP06.file, '只读第一个工作表')}</div></div>
    <div class="card"><h4>历史段批次</h4><div class="bd">
      <p class="sm">已登记 <b>${(d.batches || []).length}</b> 批（回滚后不再计入）；
      ⛔ 历史段<b>不提供行内编辑</b>（要改只能再导一次，§5.2.5 ②）。</p>
      ${(d.batches || []).length ? `<p class="sm fc">${(d.batches || []).map(esc).join(' · ')}</p>` : ''}
      </div></div>`;
  }
  if (IMP06.report) body += reportHtml(IMP06.report, 'imp06Rollback');
  return `${lgSteps(IMP06_STEPS, IMP06.preview ? (IMP06.report ? 2 : 1) : 0)}${lgNotice(IMP06)}${body}`;
};

/* ============================================================ `V.m08imp` —— 库存单据 · 手动导入（§3.6） */

const IMP08_STEPS = ['① 选文件', '② 预览（不写库）', '③ 确认导入（幂等刷新）'];

V.m08imp = () => {
  const meta = IMP08.meta || {required_headers: [], ignored_headers: []};
  let body = '';
  if (IMP08.preview) {
    const g = (IMP08.preview.groups || []).map(x => `<tr><td class="now">${esc(x.ym)}</td>
      <td>${esc(x.warehouse)}</td><td class="num">${esc(x.rows)}</td><td class="num">${esc(x.amount)}</td></tr>`).join('');
    body += `<div class="card"><h4>② 预览 —— 尚未写库</h4><div class="bd">
      <div class="tip">解析出 <b>${IMP08.preview.rows}</b> 行，落在 <b>${(IMP08.preview.groups || []).length}</b> 个
        「核算年月 ＋ 仓库」范围里（刷新就按这个范围做幂等）。</div>
      <div class="tw" style="max-height:320px;min-height:0"><table class="dt"><thead><tr><th>核算年月</th>
        <th>仓库</th><th class="num">行数</th><th class="num">金额合计</th></tr></thead>
        <tbody>${g || lgEmpty(4, '（没有可写入的行）')}</tbody></table></div>
      <div style="margin-top:10px"><button class="btn pri" data-act="imp08Ok">确认导入（写库 · 幂等刷新）</button></div>
      <p class="mut sm" style="margin-top:6px">同月同仓库重导 = <b>更新</b>（键 = 核算年月 ＋ 仓库 ＋ 单据编号 ＋ 序号）；
        本次不再出现、且<b>没有调整单</b>的行会被删掉（不留残影）；
        ⛔ <b>有调整单的行一定保留</b>，调整单本身一行不改（§5.2.4 · ENT-04）。</p>
      </div></div>`;
  } else {
    body += `<div class="card"><h4>① 文件要求（列清单的主人 = i8 导出表头）</h4><div class="bd">
      <p class="sm">就是 i8「<b>库存单据明细</b>」导出的那个 <b>xlsx</b> —— <b>原样上传</b>即可。
        表头不在固定行也能认（前 10 行内自动找）；列按下表认名、<b>不按位置</b>。</p>
      <div class="tw" style="max-height:240px;min-height:0"><table class="dt"><thead><tr>
        <th>必须有这些列（少一列 ⇒ 整份拒绝并指出缺哪一列）</th></tr></thead><tbody>
        ${(meta.required_headers || []).map(h => `<tr><td>${esc(h)}</td></tr>`).join('') || lgEmpty(1, '（取不到表头清单）')}
        </tbody></table></div>
      <p class="mut sm" style="margin-top:6px">⛔ 以下源列<b>刻意不采</b>：
        ${esc((meta.ignored_headers || []).join(' / '))}（本系统<b>不为这些源列建字段</b>）。<br>
        • 核算年月取 <b>「核算年」＋「核算月」两列</b>，<b>不是</b>「单据日期」（§9.2 / §3.4）。<br>
        • 金额列非数字 ⇒ <b>报错并指出行号</b>，不静默丢行。</p>
      ${lgPick('i08f', 'imp08Pick', 'imp08Parse', IMP08.file, '只读「报表1 / Sheet1」（没有就取第一个工作表）')}</div></div>`;
  }
  if (IMP08.result) {
    const r = IMP08.result;
    const g = (r.groups || []).map(x => `<tr><td class="now">${esc(x.ym)}</td><td>${esc(x.warehouse)}</td>
      <td class="num">${x.rows}</td><td class="num">${x.inserted}</td><td class="num">${x.updated}</td>
      <td class="num">${x.deleted}</td><td class="num">${x.kept_with_adjustment}</td></tr>`).join('');
    const t = r.totals || {};
    body += `<div class="card"><h4>③ 导入结果</h4><div class="bd">
      <div class="tw" style="max-height:300px;min-height:0"><table class="dt"><thead><tr><th>核算年月</th>
        <th>仓库</th><th class="num">行数</th><th class="num">新增</th><th class="num">更新</th>
        <th class="num">删除</th><th class="num">因调整单保留</th></tr></thead>
        <tbody>${g || lgEmpty(7, '（没有范围）')}</tbody></table></div>
      <p class="sm" style="margin-top:8px">合计：新增 <b>${t.inserted || 0}</b> · 更新 <b>${t.updated || 0}</b> ·
        删除 <b>${t.deleted || 0}</b> · <b>因有调整单而保留 ${t.kept_with_adjustment || 0}</b>
        （共 ${(r.groups || []).length} 个「核算年月 ＋ 仓库」范围）。</p>
      <p class="mut sm">⚠️ 这批是<b>手动上传</b>的（降级通道）—— 看板「本月是否抓过」看的是<b>抓取</b>执行记录，
        手动导入不计入。</p></div></div>`;
  }
  return `${lgSteps(IMP08_STEPS, IMP08.preview ? (IMP08.result ? 2 : 1) : 0)}${lgNotice(IMP08)}${body}`;
};

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
/* 付款导入：选文件 → 解析预览 → 确认 → 回滚（四步都**只看后端 `ok`**，可预期的拒绝也走这里）。 */
ACT.imp05Pick = t => { IMP05.file = (t.files || [])[0] || null; IMP05.msg = ''; render(); };
ACT.imp05Parse = async () => {
  if (!IMP05.file) return;
  IMP05.msg = '正在解析（预览阶段不写库）…'; IMP05.kind = 'ok'; render();
  const fd = new FormData(); fd.append('file', IMP05.file);
  let r = null;
  try { r = await API.postFile('/api/m05/import/parse', fd); }
  catch (e) { IMP05.msg = `解析失败：${String((e && e.message) || e)}`; IMP05.kind = 'err'; render(); return; }
  if (!r || r.ok === false) { IMP05.msg = (r && r.message) || '解析失败'; IMP05.kind = 'err'; render(); return; }
  IMP05.token = r.token; IMP05.preview = r.preview; IMP05.report = null; IMP05.msg = ''; render();
};
ACT.imp05Ok = async () => {
  let r = null;
  try { r = await API.post('/api/m05/import/confirm', { token: IMP05.token }); }
  catch (e) { IMP05.msg = `导入失败：${String((e && e.message) || e)}`; IMP05.kind = 'err'; render(); return; }
  if (!r || r.ok === false) { IMP05.msg = (r && r.message) || '导入失败'; IMP05.kind = 'err'; render(); return; }
  IMP05.msg = r.message; IMP05.kind = 'ok'; IMP05.report = r.report;
  IMP05.preview = null; IMP05.token = ''; IMP05.file = null;
  LOADED.delete('付款域');                       /* ⭐ 刚落了一批流水 ⇒ 付款域那几路标脏（下次进页重拉） */
  render();
};
ACT.imp05Rollback = async t => {
  let r = null;
  try { r = await API.post('/api/m05/import/rollback', { batch: t.dataset.batch }); }
  catch (e) { IMP05.msg = `回滚失败：${String((e && e.message) || e)}`; IMP05.kind = 'err'; render(); return; }
  if (!r || r.ok === false) { IMP05.msg = (r && r.message) || '回滚失败'; IMP05.kind = 'err'; render(); return; }
  IMP05.msg = r.message; IMP05.kind = 'wn'; IMP05.report = r.report;
  LOADED.delete('付款域');
  render();
};
/* 过程资料导入：切项目 / 选文件 / 预览 / 确认 / 回滚。 */
ACT.imp06Pj = async t => {
  IMP06.pj = t.value || '';
  IMP06.preview = null; IMP06.report = null; IMP06.msg = '';
  try { await imp06Load(IMP06.pj); }
  catch (e) { IMP06.msg = `项目数据取不到：${String((e && e.message) || e)}`; IMP06.kind = 'err'; }
  render();
};
ACT.imp06Pick = t => { IMP06.file = (t.files || [])[0] || null; IMP06.msg = ''; render(); };
ACT.imp06Parse = async () => {
  if (!IMP06.file) return;
  IMP06.msg = '正在解析（预览阶段不写库）…'; IMP06.kind = 'ok'; render();
  const fd = new FormData(); fd.append('file', IMP06.file); fd.append('pj', IMP06.pj || '');
  let r = null;
  try { r = await API.postFile('/api/m06/import/parse', fd); }
  catch (e) { IMP06.msg = `解析失败：${String((e && e.message) || e)}`; IMP06.kind = 'err'; render(); return; }
  if (r && r.data) { IMP06.data = r.data; IMP06.pj = r.data.warehouse || IMP06.pj; }
  if (!r || r.ok === false) { IMP06.msg = (r && r.message) || '解析失败'; IMP06.kind = 'err'; render(); return; }
  IMP06.token = r.token; IMP06.preview = r.preview; IMP06.report = null; IMP06.msg = ''; render();
};
ACT.imp06Ok = async () => {
  const el = document.querySelector('#i06cut');
  const body = { token: IMP06.token, pj: IMP06.pj, cutoff_ym: (el && el.value) || '' };
  let r = null;
  try { r = await API.post('/api/m06/import/confirm', body); }
  catch (e) { IMP06.msg = `导入失败：${String((e && e.message) || e)}`; IMP06.kind = 'err'; render(); return; }
  if (r && r.data) { IMP06.data = r.data; IMP06.pj = r.data.warehouse || IMP06.pj; }
  if (!r || r.ok === false) { IMP06.msg = (r && r.message) || '导入失败'; IMP06.kind = 'err'; render(); return; }
  IMP06.msg = r.message; IMP06.kind = 'ok'; IMP06.report = r.report;
  IMP06.preview = null; IMP06.token = ''; IMP06.file = null;
  render();
};
ACT.imp06Rollback = async t => {
  let r = null;
  try { r = await API.post('/api/m06/import/rollback', { batch: t.dataset.batch, pj: IMP06.pj }); }
  catch (e) { IMP06.msg = `回滚失败：${String((e && e.message) || e)}`; IMP06.kind = 'err'; render(); return; }
  if (r && r.data) { IMP06.data = r.data; IMP06.pj = r.data.warehouse || IMP06.pj; }
  if (!r || r.ok === false) { IMP06.msg = (r && r.message) || '回滚失败'; IMP06.kind = 'err'; render(); return; }
  IMP06.msg = r.message; IMP06.kind = 'wn'; IMP06.report = r.report; render();
};
/* 库存单据导入：选文件 / 预览 / 确认（⛔ 本页**没有整批回滚** —— 幂等刷新，§9.5）。 */
ACT.imp08Pick = t => { IMP08.file = (t.files || [])[0] || null; IMP08.msg = ''; render(); };
ACT.imp08Parse = async () => {
  if (!IMP08.file) return;
  IMP08.msg = '正在解析（预览阶段不写库）…'; IMP08.kind = 'ok'; render();
  const fd = new FormData(); fd.append('file', IMP08.file);
  let r = null;
  try { r = await API.postFile('/api/m08/import/parse', fd); }
  catch (e) { IMP08.msg = `解析失败：${String((e && e.message) || e)}`; IMP08.kind = 'err'; render(); return; }
  if (!r || r.ok === false) { IMP08.msg = (r && r.message) || '解析失败'; IMP08.kind = 'err'; render(); return; }
  IMP08.token = r.token; IMP08.preview = r.preview; IMP08.result = null; IMP08.msg = ''; render();
};
ACT.imp08Ok = async () => {
  let r = null;
  try { r = await API.post('/api/m08/import/confirm', { token: IMP08.token }); }
  catch (e) { IMP08.msg = `导入失败：${String((e && e.message) || e)}`; IMP08.kind = 'err'; render(); return; }
  if (!r || r.ok === false) { IMP08.msg = (r && r.message) || '导入失败'; IMP08.kind = 'err'; render(); return; }
  IMP08.msg = r.message; IMP08.kind = 'ok'; IMP08.result = r.result;
  IMP08.preview = null; IMP08.token = ''; IMP08.file = null;
  LOADED.delete('库存单据');                     /* ⭐ 刚落了一批明细 ⇒ 库存单据那路标脏 */
  render();
};

/* ⚠️⚠️ **挂在表单元素上的动作必须进 `CHG`** —— 漏了 ⇒ `change` 被**静默丢弃**
   （症状：选完文件"解析"按钮永远是灰的 / 换项目没反应）。本仓踩过三次（`jcAmt` / `jcPartySet` / `themeSet`）。
   ⚠️ 只登记**表单元素**上挂的那几个（`<input type=file>` / `<select>`）——
      「解析并预览」是 `<button>`（走 click 委托），⛔ 不用进这里。 */
CHG.push('imp05Pick', 'imp06Pick', 'imp06Pj', 'imp08Pick');
