/* shell/core.js —— 壳接线层②：**数据出口与各模块接线**
 *
 * 来源：`index.html` 的第 L5096–L5618 ＋ L5688–L6620 行（`P4`② 三刀真拆 · 2026-09-19），分两段原样搬出（中间那段是打印/设置，见 `print-export.js`）。
 * 内容：`CAT_API` / `API`（唯一数据出口）· 字段适配器（`adapt*`）· 各模块取数与写动作外壳（`reload*` / `*Act`）
 *       · `BIND.*`（渲染后注入）· 按需取数表（`PAGE_LOAD` / `LOADERS` / `LOAD_DEP` / `soft` / `loadPaths`）。
 * ⚠️ `boot();` **不在本件**（它留在 `index.html` 末尾 ⇒ 启动点显式可见、加载顺序可调）。
 * ⛔ 改这里前先看 §23：`index.html` 里 258–3285 那一段（公共外壳 ＋ 原型切片 `V.*`）**不许搬**。
 */
/* ⚠️ 分类的**内部值**是英文（`material` / `mechanical` / `jc`），中文只是**显示名** ——
   界面上传下来的是中文 ⇒ 在**这一处**转（映射只写一份，别在动作里各转一遍）。 */
const CAT_API = { '辅材': 'material', '机械': 'mechanical', '集采': 'jc' };

const API = {
  async get(url) {
    const r = await fetch(url, { headers: { Accept: 'application/json' } });
    if (!r.ok) throw new Error(`GET ${url} → HTTP ${r.status}`);
    return r.json();
  },
  async post(url, body) {
    const r = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body || {}),
    });
    if (!r.ok) throw new Error(`POST ${url} → HTTP ${r.status}`);
    return r.json();              /* ⚠️ 恒 HTTP 200 —— 成败看 `ok` 标志（见 notice_api_router） */
  },
  /* ⭐ `PUT` 等其余方法走这个 —— ⚠️ **失败时把后端的 `message` 原样抛出**：
     `MOD-01` 的状态不变式是「拦了就讲清**为什么 + 怎么解决**」（§2.7.2），
     若只抛 `HTTP 400`，那句"壳下还有 3 个在建小微：A、B、C"就丢了 ⇒ 用户只看到"保存失败"。
     ⛔ 由 `core/errors.py::AppError` 统一转成 `{code, message}` + 对应状态码。 */
  async send(method, url, body) {
    const r = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body || {}),
    });
    const text = await r.text();
    let data = null;
    try { data = text ? JSON.parse(text) : null; } catch (e) { data = null; }
    if (!r.ok) throw new Error((data && (data.message || data.detail)) || text || `HTTP ${r.status}`);
    return data;
  },
  /* `period=""` ⇒ **全量**（口径见后端 `notice_filters`）—— 筛选用前端 `ntHit` 原样做 */
  notices: () => API.get('/api/m03/notice-list?period='),
  /* ⚠️ `status=all`：原型的筛选**含归档**（默认值只是"在建"，候选里归档项排最后并标注，§2.7/§2.7.1）
     ⇒ 取数必须**全量**，筛选项由原型自己的 `fPj` 逻辑做（⛔ 别把默认值当"只取在建"）。 */
  projects: () => API.get('/api/m01/projects?status=all'),
  /* 修改留痕（§9.3 只有"项目全名 / 项目状态"）—— 供 `m01` 的「修改留痕」卡 */
  trails: () => API.get('/api/m01/trails?limit=20'),
  setCategory: (ids, category) =>
    API.post('/api/m03/actions/category', { ids, category: CAT_API[category] || category }),
  exclude: ids => API.post('/api/m03/actions/exclude', { ids }),
  restore: ids => API.post('/api/m03/actions/restore', { ids }),
  /* 统计金额手改（§4.5.3）：上限 / 留痕 / 欠款重算**全在后端**同一出口
     —— 前端只负责发与显示回执（⛔ 不本地改值、不本地留痕冒充落库）。
     ⚠️ 字段名是**后端旁路字段名**（`stat_settle` / `stat_paid`），壳里的短名 `ss`/`sp` 在此映射。 */
  statCell: body => API.post('/api/m03/actions/stat', body),
  /* 手动行新增 / 编辑（§4.2.6）：校验与落库**全在后端**（录入人取当前登录用户 / 统计结算恒 0 /
     全站「统计两金额 ≤ 审批金额」…）—— 前端只管发与显示回执（⛔ 不 `NO.push` 冒充落库）。
     `row_id` 空 = 新增；有值 = 编辑该手动行。 */
  manualSave: body => API.post('/api/m03/actions/manual-save', body),
  /* 删除前的影响范围（§7.2/§9.4 **硬要求**）：由后端给（项目/统计付款金额/已付金额/「欠款回增」那句）
     —— ⛔ 前端不自己拼这段文字。 */
  manualDeleteImpact: body => API.post('/api/m03/actions/manual-delete-impact', body),
  /* 删除手动行（§4.2.6）：只对手动行开放，i8 抓取行永不可删（§4.2.7）；⛔ 前端不本地 splice 冒充删除 */
  manualDelete: body => API.post('/api/m03/actions/manual-delete', body),
  /* 批量付款（§4.4.4）：**整批重算 / 整批不落半批 / 幂等** 全在后端同一出口
     （`notice_actions.apply_batch_pay`）—— 前端只管发与显示回执（⛔ 不本地往 FLs 塞流水冒充落库）。
     ⚠️ 必须带 `request_id`（幂等号）：服务端据它**拒重复提交**。 */
  batchPay: body => API.post('/api/m03/actions/batch-pay', body),
  /* ---- MOD-01 写动作（⛔ 判定与落库一律后端：状态不变式 / 排序重编号 / 全名留痕） ---- */
  pjUpdate: (id, body) => API.send('PUT', `/api/m01/projects/${id}`, body),
  pjStatus: (id, status) => API.send('PUT', `/api/m01/projects/${id}/status`, { status }),
  pjOrd: (id, body) => API.send('PUT', `/api/m01/projects/${id}/ord`, body),
  /* ---- MOD-01 · ⭐ 链路 B「人工指认」（`TAIL-30`-③）----
     ⚠️ 候选行按**全名**查（这是**读**）；**写**一律传 `project_id` 按 id 定位
        （铁律 5/6：禁止用名字反查 —— 一个全名可能对应多行）。 */
  pjPromotePending: () => API.get('/api/m01/promote-pending'),
  pjPromoteCandidates: full => API.get(
    `/api/m01/promote-candidates?full=${encodeURIComponent(full || '')}`),
  pjPromote: body => API.post('/api/m01/promote', body),

  /* ---- MOD-01 · 链路 A ③-b「≥2 个仓库 ⇒ 选定一个建行」（`TAIL-45`） ----
     ⚠️ 清单来自**最近一次成功的「常用项目列表」同步**；原先 `m01` 上**根本没有入口**
        （那条只在同步回执里报一次、刷新即丢）⇒ 这两个端点就是那个"可点"的出口。 */
  pjArchPend: () => API.get('/api/m01/archive-pending'),
  pjArchRow: body => API.post('/api/m01/archive-row', body),
  /* 人工改**类型**（`TAIL-42`）—— 三类判定的**人工覆盖**；⚠️ 合法域只有 `normal` / `shell`
     （「具体小微」由链路产生）⇒ 后端也会拒，壳里⛔ 不另写一份判定。 */
  pjType: (id, project_type, warehouse_name) => API.send(
    'PUT', `/api/m01/projects/${id}/type`,
    {project_type, warehouse_name: warehouse_name || null},
  ),

  /* ---- MOD-02 · i8 接入层（`TAIL-27`）----
     ⭐ 「抓取结果回显」与「抓取任务日志」的**唯一数据源 = 执行记录**（原先两张卡是模拟值/硬编码行）。
     ⚠️ 两个同步都会**登录 i8 并强踢该账号在线用户**（D9）⇒ `allow_kick=true` 只允许在
        界面**二次确认**之后传 —— 下面 `m02Sync()` 里那个弹窗就是那道闸（⛔ 不确认就不发请求）。 */
  m02Records: (limit = 50) => API.get(`/api/m02/fetch/records?limit=${limit}`),
  m02SyncWh: () => API.post('/api/m02/sync/warehouses?allow_kick=true', {}),
  m02SyncPj: () => API.post('/api/m02/sync/common-projects?allow_kick=true', {}),

  /* ---- MOD-03 · 抓取 ＋ 链路 C 弹窗（`TAIL-29`-② ④） ---- */
  /* ⭐ 抓取：**失败也要看回执** —— 「归属未走完」是**可预期的失败**（要拿它开弹窗）
     ⇒ 这里**不 throw**，把 body 原样返回，由调用方判 `ok`。 */
  fetchNotices: async year_month => {
    const r = await fetch('/api/m03/notices/fetch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ year_month, allow_kick: true }),
    });
    const body = await r.json().catch(() => ({}));
    return r.ok ? { ok: true, ...body } : { ok: false, ...body };
  },
  unresolved: () => API.get('/api/m03/notices/unresolved'),
  assignOwnership: body => API.post('/api/m03/notices/ownership-assign', body),
  /* ⭐ `TAIL-39`：**兜底前先跑一次 i8 仓库名单**（`API-05`）—— ⚠️ 会登录 i8、可能**强踢**（`D9`）
     ⇒ `allow_kick=true` 只允许在**二次确认之后**传（`ownWhCheck` 那个弹窗就是那道闸）。只查**不落库**。 */
  whCheck: body => API.post('/api/m03/notices/warehouse-check', body),
  /* ⭐ `TAIL-46`：批量打印 / 只导出 PDF / 打印机设置（`MOD-03` 三条**真出口**）——
     这三件事原先**只有旧页 `mod03_notice/static/m03.html` 能做**；接上之后才谈删旧页（§19 批 4.5）。
     ⚠️ `ids` 必须是**系统内勾选**的通知书 id（001-09 明令：不收文件、不收手输清单）。 */
  m03Batch: (ids, mode) => API.post('/api/m03/batch', {ids, mode}),
  printerGet: () => API.get('/api/m03/settings/printer'),
  printerSet: (url, mode, name) => API.send('PUT', '/api/m03/settings/printer',
    {printer_ipp_url: url, print_mode: mode, printer_name: name}),
  /* 本机装了驱动的打印机名（选「系统驱动」通道时**名字要一字不差**）—— 拿不到即空表，⛔ 不是错误 */
  printerList: () => API.get('/api/m03/settings/printers'),

  /* ---- MOD-07 收发结存与活动大表（⚠️ 金额后端出**字符串** ⇒ 适配层过 `N0()`） ---- */
  m07Settlement: ym => API.get(`/api/m07/settlement?period=${encodeURIComponent(ym || '')}`),
  m07Extract: () => API.get('/api/m07/extract'),
  m07BalCell: body => API.post('/api/m07/extract/balance', body),
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

  /* ---- MOD-04 付款计划（⚠️ 后端这几个端点收 **query 参数**，不是 JSON body ⇒ 照它调用） ---- */
  plans: () => API.get('/api/m04/plans?year_month='),
  plDeleteImpact: ids =>
    API.get(`/api/m04/delete-impact?ids=${encodeURIComponent(ids.join(','))}`),
  plCell: (id, column, value) =>
    API.send('POST', `/api/m04/plans/${id}/cell`
      + `?column=${encodeURIComponent(column)}&value=${encodeURIComponent(value == null ? '' : value)}`, null),
  plRematch: id => API.send('POST', `/api/m04/plans/${id}/re-match`, null),
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
  },
  plForce: (id, remark) =>
    API.send('POST', `/api/m04/plans/${id}/force?remark=${encodeURIComponent(remark || '')}`, null),
  /* ---- MOD-05 付款流水与欠款（读 4 个端点；写：撤销走 JSON、期初/备注走 PRG 表单端点） ---- */
  flows: () => API.get('/api/m05/flows?year_month='),
  debt: () => API.get('/api/m05/debt'),
  stats: q => API.get('/api/m05/stats?granularity=' + encodeURIComponent(q.granularity || 'week')
    + '&year=' + (q.year || 0) + '&quarter=' + (q.quarter || 0)),
  ledger: pid => API.get('/api/m05/ledger?project_id=' + pid),
  flowRevoke: (id, reason) => API.send('POST',
    `/api/m05/flows/${id}/revoke?reason=${encodeURIComponent(reason || '')}`, null),
  /* ⚠️ 期初录入 / 期初删除 / 台账备注 **目前只有 PRG 表单端点**（收 `Form`）⇒ 用表单编码发；
     它们回 303，我们**不看那页 HTML**，改「重拉数据 ＋ 自己的回执」（同一批落库出口）。 */
  postForm: async (url, obj) => {
    const r = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams(obj || {}).toString(),
      redirect: 'follow',
    });
    if (!r.ok) throw new Error(`POST ${url} → HTTP ${r.status}`);
    return true;
  },
  plForceCancel: id => API.send('POST', `/api/m04/plans/${id}/force-cancel`, null),
  /* ⚠️ `confirmed=true` 只在**用户已在确认弹窗里看过影响范围**之后才传（§4.3.6 的两步） */
  plDelete: ids =>
    API.send('POST', `/api/m04/plans/delete`
      + `?ids=${encodeURIComponent(ids.join(','))}&confirmed=true`, null),

  /* ---- MOD-08 库存单据与调整单（读全量 + 调整单；写走 JSON） ---- */
  m08Inventory: () => API.get('/api/m08/inventory'),
  m08Adjust: (rowId, body) => API.send('POST', '/api/m08/adjust', { row_id: Number(rowId), ...body }),
  m08AdjustClear: rowId => API.send('POST', '/api/m08/adjust/clear', { row_id: Number(rowId) }),
  /* ⚠️ 抓取**会顶号**（D9）：`confirm:true` = 用户已在抓取弹窗里确认过；
     缺它后端一律 400（防静默抓取）。失败（i8 异常）⇒ 后端降级回执，不抛。 */
  m08Fetch: month => API.send('POST', '/api/m08/fetch', { month, confirm: true }),

  /* ---- MOD-06 过程资料：机械 6 列手录值（旁路表，全量） ---- */
  m06Mech: () => API.get('/api/m06/mech'),
  /* ⭐ `TAIL-38`：「录机械费」写入口 —— 校验与落库**全在后端**
     （`mech_ui.parse_mech_values` ＋ `repository.save_mech`），与 PRG 端点同一份判定。 */
  m06MechSave: body => API.post('/api/m06/mech', body),

  /* ---- MOD-14 剔除规则（`TAIL-40`）⚠️ 唯一主人在库；⛔ 前端不做任何本地改数据冒充落库 ---- */
  m14Rules: () => API.get('/api/m14/rules'),
  m14RuleAdd: body => API.post('/api/m14/rules', body),
  m14RuleSet: (id, body) => API.send('PUT', `/api/m14/rules/${id}`, body),
  /* ⚠️ 写动作**恒 HTTP 200**，成败看回包的 `ok` —— 规则不合法是 §4.2.2 的可预期拒绝，
     后端那句中文必须原样给用户看。 */
  m14RuleDel: id => API.send('DELETE', `/api/m14/rules/${id}`, null),

  /* ---- MOD-09 特殊费用月报表（`TAIL-27`）⚠️ 金额后端出**字符串** ⇒ 适配层过 `N0()` ---- */
  m09Fee: (ym, pj) => API.get(`/api/m09/fee?ym=${encodeURIComponent(ym || '')}`
    + `&pj=${encodeURIComponent(pj || '')}`),
  m09Add: body => API.post('/api/m09/fee/add', body),
  m09Name: body => API.post('/api/m09/fee/name', body),
  m09Amount: body => API.post('/api/m09/fee/amount', body),
  m09Delete: body => API.post('/api/m09/fee/delete', body),
};

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
  const opt = (k, desc) => `<div style="display:flex;align-items:center;gap:10px;padding:8px;border:1px solid var(--bd);border-radius:7px;margin-bottom:7px">
      <button class="btn sm ${pjTypeNew === k ? 'pri' : 'gost'}" style="flex:0 0 auto" data-act="pjTypePick" data-t="${k}">${pjTypeNew === k ? '已选' : '选它'}</button>
      <span style="flex:1;min-width:0"><b>${esc(PJ_TYPE_LABEL[k])}</b> <span class="mut sm">· ${desc}</span></span></div>`;
  modal({
    title: `改类型 · ${esc(pjDisp(p))}`,
    body: `<div class="tip" style="margin-bottom:10px">当前类型：<b>${esc(PJ_TYPE_LABEL[p.type] || p.type)}</b>。
      三类判定（§2.2.1）本来是<b>自动</b>的：全名含「小微」⇒ <b>小微壳</b>；同一全名挂 <b>≥2 个仓库</b> ⇒ 待人工确认；其余算<b>普通项目</b>。
      ⚠️ 有的壳的全名里<b>没有「小微」</b>（图纸上的叫法就是这样）⇒ 会被误判成普通项目 —— <b>这里就是人工纠正的入口</b>
      （改动<b>会留痕</b>，在「修改留痕」卡里可查）。</div>
      <div class="tip wn" style="margin-bottom:10px">⛔ <b>不能选「具体小微」</b>：它得挂在一个壳下面、还占一个仓库名，由链路产生（人工指定只会造出挂不上的行）。</div>
      ${opt('shell', '不挂仓库；它名下的仓库 = 具体小微（今后走这条路）')}
      ${opt('normal', '要挂一个仓库名（候选键）—— 选了它，下面会让你填')}
      ${pjTypeNew === 'normal' ? `<div style="margin-top:6px"><div class="sm mut" style="margin-bottom:4px">仓库名（普通项目必填）</div>
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
    id: '', proj: x.project_key || x.project_label || '', cat: x.category_label || '',
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
async function ntFetchBackend(m) {
  closeModal();
  toast(`正在抓取 <b>${m}</b> 的付款通知书（会登录 i8：<b>可能顶掉在线用户</b>）…`, 4000);
  let r;
  try { r = await API.fetchNotices(m); }
  catch (e) { return toast(`⚠️ 抓取失败：${esc(String((e && e.message) || e))}`, 8000); }
  if (r.ok) {
    await reloadNotices();
    return toast(`已抓取 <b>${esc(m)}</b>：i8 返回 <b>${r.fetched}</b> 条，落库 <b>${r.upserted}</b> 条`, 6000);
  }
  /* 失败：把后端原因**原样**给用户（后端已写成中文）；属「归属未走完」⇒ 直接开补词弹窗 */
  toast(`<b>抓取被拒</b>：${esc(r.message || '未知原因')}`, 9000);
  try { await openOwnDialog(); } catch (e) { /* 打不开弹窗也不影响上面那句原因 */ }
}


async function openOwnDialog() {
  const d = await API.unresolved();
  const items = (d && d.items) || [];
  if (!items.length) return;
  const box = items.map((it, i) => {
    OWN_CTX[i] = it.project_name || '';          /* `TAIL-39`：查名单后用来核"是不是同一个壳" */
    const cands = it.candidates || [];
    const rows = cands.map(c => `<div style="display:flex;align-items:center;gap:9px;padding:7px 8px;border:1px solid var(--bd);border-radius:7px;margin-bottom:7px">
      <button class="btn sm pri" style="flex:0 0 auto" data-act="ownAssign" data-i="${i}" data-pid="${c.id}">归集到它</button>
      <span style="flex:1;min-width:0">${esc(c.disp)} <span class="mut sm">· 仓库名 ${esc(c.warehouse_name || '—')} · 关键词 ${esc((c.keywords || []).join('、') || '—')}</span></span>
      <input class="inp" style="width:148px;flex:0 0 auto" id="ownKw_${i}_${c.id}" placeholder="关键词">
    </div>`).join('');
    const note = it.kind === 'needs_keyword' ? '（单据名未命中该壳下任何小微 ⇒ 选一个并补词即可）'
      : it.kind === 'needs_choice' ? '（单据名命中该壳下多个小微 ⇒ 选一个并补词）'
        : it.kind === 'not_archived'
          ? '⛔ <b>未建档</b>（且不在 i8 常用项目列表）⇒ 请把它<b>加入 i8 常用项目列表</b>，下次抓取会自动建档 —— <b>不要</b>在这里新建小微'
          : `（${esc(it.kind)}）`;
    return `<div style="border:1px solid var(--bd2);border-radius:8px;padding:10px;margin-bottom:10px">
      <div class="sm" style="margin-bottom:6px"><b>${esc(it.project_name)}</b> <span class="mut">${note}</span></div>
      ${kvBlock([['单据编码', `<span class="fc">${esc(it.bill_no || '—')}</span>`], ['单据名称', `<span class="fc">${esc(it.doc_name || '—')}</span>`]])}
      <p style="font-size:12px;margin:6px 0 8px">选已有小微时，<b>须填一个出现在上面单据名里的关键词</b>（选中后<b>去重追加</b>到该小微名下，供下次自动命中）；填不出说明不是它。</p>
      ${rows || '<div class="tip wn" style="margin:0 0 9px">该壳下<b>暂无具体小微</b> → 只能走下面的「新小微」。</div>'}
      <div style="padding:9px;border:1px dashed var(--bd);border-radius:7px;margin-top:8px">
        <div class="mut sm" style="margin-bottom:7px">属于<b>新小微</b> → 录「仓库名 ＋ 关键词」建档</div>
        <div class="fld"><label>新小微的仓库名</label><input class="inp" id="ownNewName_${i}" placeholder="如：河南南阳热电项目仓库"></div>
        <div class="fld" style="margin-top:6px"><label>识别关键词（须出现在单据名里）</label><input class="inp" id="ownNewKw_${i}" placeholder="如：南阳"></div>
        <div style="margin-top:8px">
          <button class="btn gost" data-act="ownWhCheck" data-i="${i}">① 先查 i8 仓库名单</button>
          <span id="ownWhRes_${i}" class="sm" style="margin-left:8px"></span>
        </div>
        <div class="mut sm" style="margin-top:6px">⭐ <b>建档前必须先跑这一环</b>（用户 2026-09-18 口述裁定）——
          不查就建＝凭猜填仓库名，会留下与 i8 不符的<b>假档案行</b>。⚠️ 查名单要登录 i8，<b>会顶号</b>，故要二次确认。</div>
        <div style="margin-top:8px"><button class="btn" data-act="ownAssign" data-i="${i}" data-pid="__new">建档并归集</button></div>
      </div>
    </div>`;
  }).join('');
  modal({
    title: `待指定归属 · ${items.length} 条`,
    wide: true,
    body: `<div class="tip" style="margin-bottom:10px"><b>链路 C</b>：付款项目名落在<b>壳</b>上，而「单据名称」没能在该壳下的小微关键词里命中 ⇒ 系统<b>不猜</b>（铁律 5/6）。<br>⭐ 补完关键词后请<b>再抓一次</b> —— 本批数据<b>不暂存</b>，那次会自动命中并落库。</div>${box}`,
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
    body: `<div class="tip dg" style="margin:0 0 10px"><b>⚠️ 这一步会登录 i8，可能<b>强制踢掉</b>该账号其它在线会话</b>（决策 <span class="fc">D9</span>，不会自动重试登录）—— 若同事正在用 i8，请先<b>择时</b>。</div>
      <div class="tip" style="margin:0">查什么：i8 仓库名单（<span class="fc">API-05</span>）里**有没有**「${esc(name)}」，以及它**挂在哪个项目全名**下 ——
      用来判断该走「选已有小微」还是「只能手填」。⚠️ 只查**不落库**（名单本身不留档）。</div>`,
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
  const d = await API.unresolved();
  const it = ((d && d.items) || [])[i];
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
  PROC_PJS = uniqBy(IVs, iv => iv.wh);
  if (!procPj || !IVs.some(iv => iv.wh === procPj)) procPj = PROC_PJS[0] || '';
  if (invWhs.length) {          /* 筛选里失效的项目名清掉（原地改，外部持有的是数组引用） */
    const kept = invWhs.filter(k => PROC_PJS.indexOf(k) >= 0);
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
      return toast(`<b>抓取没能完成</b>，已<b>降级为手动导入</b>：${esc(r.message || '')}<br>`
        + `<span class="mut sm">可到「导入」入口上传 i8 导出的 Excel（解析走同一条管线）</span>`, 9000);
    }
    await reloadInv();
    const st = r.stats || {};
    toast(`已按 <b>${esc(month)}</b> 抓取库存单据明细（API-03）：<br>`
      + `本次插入 <b>${st.inserted || 0}</b> · 更新 <b>${st.updated || 0}</b>`
      + ` · i8 侧已删 <b>${st.deleted || 0}</b>`
      + `${st.kept_with_adjustment ? ` · <b>保留调整单 ${st.kept_with_adjustment}</b>` : ''}`
      + `<br><span class="mut sm">调整单独立存储、不被导入覆盖（ENT-04）</span>`, 7200);
  } catch (e) {
    await reloadInv();
    toast(`<b>抓取没能完成</b>：${esc(String((e && e.message) || e))}<br>`
      + `<span class="mut sm">本系统<b>不会自动重试登录</b>（D9，避免反复顶号）—— 请确认 i8 账号后再试</span>`, 8600);
  }
}

/* ============ MOD-07 收发结存与活动大表（前端壳接线 · `TAIL-27`）============
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
  }
  /* ⚠️ 大表月份 = `bjMonth(-1)`（原型写死「北京时间上月」，§9.2 材料报表类）——
     与后端 `default_month()` 同口径；后端 `selected` 已是「大表自己的顺序」，不需前端重排。
     ⛔ **不要在这里给 `BIGSET` 兜底「空了就填全部候选」**：后端的选题有**标记行**区分
        「从未选题」（⇒ 后端已给全部候选）与「选了空」（⇒ 表里 0 个项目）——
        前端兜底会把用户的「清空」**悄悄改回全部候选**（假成功，且不报错）。 */
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
    /* ⭐ 链路 B 的回执**必须露出来**（`TAIL-30`-③ 补的缺口）：原先这一路只报条数，
       回包里的 `recovery`（扶正了谁 / 新建了谁 / **还有哪几条要人指认**）**根本没露** ⇒
       用户在壳上抓完收发结存，**看不到"待人工 N 条"**，也就不知道该去 `m01` 处理。 */
    try { await reloadPending(); } catch (_) { /* 清单这一路失败 ⇒ 下面的回执里如实说明 */ }
    const st = r.stats || {};
    let msg = `已按 <b>${esc(month)}</b> 抓取收发结存（API-02）：解析 <b>${r.rows || 0}</b> 行 —— `
      + `新增 <b>${st.inserted || 0}</b> · 更新 <b>${st.updated || 0}</b> · 删除 <b>${st.deleted || 0}</b>`;
    const rc = r.recovery || {};
    const pro = (rc.promoted || []).length, cre = (rc.created || []).length;
    if (pro || cre) msg += `<br>链路 B：自动扶正 <b>${pro}</b> 行 · 自动建档 <b>${cre}</b> 行`
      + (pro ? `<br><span class="mut sm">${esc((rc.promoted || []).join('；'))}</span>` : '');
    const pend = rc.unresolved_items || [];
    if (pend.length) {
      msg += `<br>⚠️ <b>待人工 ${pend.length} 条</b>：`
        + esc(pend.map(x => `${x.warehouse_name}：${x.reason}`).join('；'))
        + `<br>⇒ <span class="link" data-act="go" data-k="m01" tabindex="0" role="button">去项目档案指认到哪一行 →</span>`;
    }
    if (rc.degraded && rc.message) msg += `<br>⚠️ ${esc(rc.message)}`;
    toast(msg + `<br><span class="mut sm">⚠️ 解析条数与落库条数不一致时先怀疑幂等范围（见 ops 实测结论）</span>`,
      pend.length ? 15000 : 7600);
  } catch (e) {
    await reloadM07();
    toast(`<b>抓取没能完成</b>：${esc(String((e && e.message) || e))}<br>`
      + `<span class="mut sm">本系统<b>不会自动重试登录</b>（D9，避免反复顶号）—— 请确认 i8 账号后再试</span>`, 8600);
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
  /* ⚠️ 后端给 `kind_label`（**展示名**）—— 本页只展示，故用展示名；
     写动作要的是 `kind`（内部值）⇒ 从 `RULE_RAW[i]` 取，别从展示三元组反推。 */
  RULE_EX = RULE_RAW.map(r => [r.kind_label, r.values, r.meaning]);
}

async function reloadMech() {
  const d = await API.m06Mech();
  MACH6 = d.mech || {};
  if (d.columns && d.columns.length) {
    MECH_LABELS.length = 0;
    d.columns.forEach(x => MECH_LABELS.push(x));
  }
}

/* ⭐⭐ `TAIL-38`：「录机械费」入口 —— 原型 `V.m06` **没画**这个入口（机械 6 列在原型里是**只读**的），
   而服务端页 `/m06` 才有 PRG 写入口 ⇒ 壳里**没法录**（机械欠款会长期停在 0）。按 §5.2.5 ③ 自行设计。
   ⛔ **不改 `V.m06` 一行**：走原型自己的 `BIND` 钩子（渲染后往页首注入一条工具栏）——
      判定与落库全在后端（`POST /api/m06/mech`）。⚠️ 机械值是**旁路载体**，重抓 / 重导都不覆盖它。 */
BIND.m06 = function () {
  const host = document.querySelector('#view');
  if (!host || document.getElementById('mechEntry')) return;
  const bar = document.createElement('div');
  bar.id = 'mechEntry';
  bar.className = 'fbar';
  bar.style.cssText = 'border:1px solid var(--bd2);border-radius:6px;margin-bottom:10px';
  bar.innerHTML = '<div class="fi"><label>机械费手录（§5.2.5 ③）</label>'
    + '<span class="mut sm">机械 6 列是<b>旁路载体</b> —— 重抓 i8 / 重导历史都<b>不覆盖</b>它</span></div>'
    + '<button class="btn pri" data-act="mechOpen">录机械费</button>';
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

BIND.m02 = function () {
  const host = document.querySelector('#view');
  if (!host) return;
  const kv = host.querySelector('.kv');
  if (kv) kv.innerHTML = m02EchoKv();
  const tb = host.querySelector('table[data-sort-key="m02:logs"] tbody');
  if (tb) tb.innerHTML = m02LogRows();
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
    abox.innerHTML = `<h4>待人工建档（链路 A · 多仓库）<span class="sp"><span class="mut sm">共 ${ARCP.length} 条 · ${asrc}</span></span></h4>
      <div class="bd">
        ${ARCP_ERR ? `<div class="tip dg" style="margin:0 0 8px">⚠️ <b>待建档清单没取到</b>：${esc(ARCP_ERR)}
          <br>其余档案数据照常显示（这一路失败不拖垮本页）—— 可刷新页面重试。</div>` : ''}
        <div class="tip" style="margin:0 0 8px"><b>为什么这里要人来定</b>：这个全名在 i8 名单里挂了
          <b>≥2 个仓库</b>，而<b>一条普通项目只挂一个仓库</b>（决策 2）⇒ 系统<b>不猜</b> ——
          请你<b>选定一个</b>，系统按它建行；⚠️ 其余仓库<b>不会</b>再建行。</div>
        <table class="dt cond"><thead><tr><th>项目全名</th><th>待选仓库</th><th>系统为什么不自己定</th><th></th></tr></thead>
        <tbody>${arows}</tbody></table>
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
  box.innerHTML = `<h4>待人工指认（链路 B）<span class="sp"><span class="mut sm">共 ${PEND.length} 条 · ${src}</span></span></h4>
    <div class="bd">
      ${PEND_ERR ? `<div class="tip dg" style="margin:0 0 8px">⚠️ <b>待指认清单没取到</b>：${esc(PEND_ERR)}
        <br>其余档案数据照常显示（这一路失败不拖垮本页）—— 可刷新页面重试。</div>` : ''}
      <div class="tip" style="margin:0 0 8px"><b>为什么这里要人来定</b>：材料报表出现了<b>陌生仓库</b>，
        而它的全名在档案里命中 <b>≥2 条</b>非壳行 ⇒ 系统<b>无法自己决定</b>挂哪一条、也<b>不该猜</b>
        （决策 1 兜底）—— 请你指明这条<b>真实仓库名</b>该写到<b>哪一行</b>上。
        ⚠️ 只改仓库名（系统写入）；<b>类型纠正</b>不在这里做。</div>
      <table class="dt cond"><thead><tr><th>陌生仓库名</th><th>项目全名</th><th>同名档案行</th><th>系统为什么不自己定</th><th></th></tr></thead>
      <tbody>${rows}</tbody></table>
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
    body: `<div class="tip" style="margin-bottom:10px"><b>链路 B · 材料侧扶正</b>：材料报表里出现了
      <b>陌生仓库</b>，而它的全名在档案里命中 <b>${rows.length}</b> 条非壳行 ⇒ <b>系统不猜</b>（决策 1 兜底），
      请你指明这条仓库名该写到<b>哪一行</b>。⚠️ 这是**系统写入**（不是人工改仓库名，§2.3.1）；
      <b>类型纠正</b>不在这里做（另立）。</div>
      ${kvBlock([['陌生仓库名', `<span class="fc">${esc(it.wh)}</span>`],
                 ['项目全名', `<span style="font-size:11.5px">${esc(it.full)}</span>`],
                 ['系统当时为什么没自己定', `<span style="font-size:11.5px">${em(it.reason)}</span>`]])}
      <div class="fld"><label>写到哪一行（候选 = 该全名下的档案行，含归档行）</label>
        <select class="inp" id="pmRow">${opts}</select></div>
      ${usable.length ? '' : `<div class="tip dg" style="margin:0">⚠️ 这几行<b>都不是占位行</b>（都已有真实仓库名）
        ⇒ 按决策 2（普通项目 ↔ 仓库 = 1 : 1）**不能靠扶正解决** —— 需要人工核对档案，属另一件事。</div>`}`,
    footer: `<button class="btn" data-act="closeModal">取消</button>
      <button class="btn pri" data-act="pjPromoteOk"${usable.length ? '' : ' disabled'}>按这一行扶正</button>`,
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
    body: `<div class="tip" style="margin-bottom:10px"><b>链路 A · 多仓库建档</b>：i8 名单里这个全名挂了
      <b>${it.stored.length}</b> 个仓库，而<b>一条普通项目只挂一个仓库</b>（决策 2）⇒ <b>系统不猜</b>，
      请你选定<b>一个</b>，系统按它建行（⛔ 仓库名不许手填，§9.4）。</div>
      ${kvBlock([['项目全名', `<span style="font-size:11.5px">${esc(it.full)}</span>`],
                 ['i8 名单里的仓库', `<span style="font-size:11.5px">${esc(it.stored.join('、'))}</span>`],
                 ['已被别的行占用（不列）', `<span style="font-size:11.5px">${gone.length ? esc(gone.join('、')) : '（无）'}</span>`],
                 ['系统当时为什么没自己定', `<span style="font-size:11.5px">${em(it.reason)}</span>`]])}
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
   ⚠️ **接口清单表（`TASK`）刻意不接** —— 它是**口径文档式静态表**（《说明书》附录 E.1 的**子集**），
      数据源就是**文档本身**，不是运行数据；它的「触发 / 手动导入」两个按钮才走下面这些入口。
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
    if (it.api === 'API-04') dd = '<span class="mut">待接通 —— 该接口属<b>集采域</b>（M5 未开工）</span>';
    else if (M02_ERR) dd = '<span class="dg">⚠️ 执行记录没取到（见下方日志卡）</span>';
    else if (!r) dd = '<span class="mut">还没有执行记录（抓过 / 同步过就有了）</span>';
    else dd = `${m02StatusTag(r)} <span class="mut sm">${esc(m02When(r))}</span>`
      + (r.err ? `<br><span class="dg sm">${esc(r.err)}</span>` : '');
    return `<dt>${esc(it.label)}</dt><dd>${dd}</dd>`;
  }).join('');
}

/* 任务日志卡的行（时间 / 接口 / 结果 / 耗时 —— 后两项由适配层从记录算，⛔ 后端不为此加字段） */
function m02LogRows() {
  if (M02_ERR) return `<tr><td colspan="4" class="dg">⚠️ <b>执行记录没取到</b>：${esc(M02_ERR)}
    <br><span class="mut">其余页照常可用（这一路失败不拖垮本页）—— 可刷新页面重试。</span></td></tr>`;
  if (!M02_RECS.length) return '<tr><td colspan="4" class="mut">还没有执行记录 —— 抓过 / 同步过之后这里就有（按时间倒序）</td></tr>';
  return M02_RECS.map(r => `<tr><td class="fc">${esc(String(r.at).replace('T', ' '))}</td>
    <td>${esc(m02LabelOf(r))}</td><td>${m02StatusTag(r)}${r.err ? `<br><span class="dg sm">${esc(r.err)}</span>` : ''}</td>
    <td class="fc">${esc(m02Dur(r))}</td></tr>`).join('');
}

function m02LabelOf(r) {
  const it = M02_IFACES.find(x => m02IsIf(x, r));
  return it ? `${it.api} ${it.label}` : r.target;      /* 认不出的走原文（⛔ 不猜成某一类） */
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

/* ⭐ 两个同步（`API-05` / `API-06`）的**唯一入口** —— 壳里三处入口共用它：
   `m02` 表里 API-05/06 两行的「触发」＋ `m01` 页首那两个「同步…」按钮。
   ⚠️ **D9：会强踢该账号的在线用户** ⇒ ① 先弹**二次确认**（讲清顶号与时段），⛔ 不确认不发请求；
      ② 失败 / 降级 ⇒ 后端那句中文说明**原样**转给用户；③ 成功 ⇒ 刷新执行记录（回显与日志跟着变），
      同步**常用项目列表**还会**真的建档** ⇒ 顺手刷新档案与「待人工建档」卡（`TAIL-45`）。
   签发给谁：本函数的两种入参就是那两个端点（`warehouses` / `common-projects`）。 */
async function m02Sync(which) {
  const isWh = which === 'warehouses';
  const name = isWh ? '仓库名单（API-05）' : '常用项目列表（API-06）';
  const tail = isWh ? '仓库名单本身**不落库**（它是建档的输入）；建档请用「常用项目列表」那一行'
                    : '会按 phid **幂等建档**，并把「待人工建档」清单留在执行记录里（去 <b>m01</b> 处理）';
  modal({
    title: `同步 ${name}`,
    body: `<div class="tip dg" style="margin:0 0 10px"><b>⚠️ 这一步会登录 i8，并强制踢掉该账号其它在线会话</b>（决策 <span class="fc">D9</span>，不会自动重试登录）——
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
  if (!r || r.ok === false) { toast(`<b>没能保存</b>：${esc((r && r.message) || '后端未返回原因')}`, 7000); return null; }
  toast(typeof okMsg === 'function' ? okMsg(r) : okMsg);
  return r;
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
  home: ['付款通知书', '项目档案', '付款计划'],
  m01: ['项目档案', '待人工指认', '待人工建档', '修改留痕'],
  m02: ['i8 执行记录', '库存单据'],      /* `V.m02` 的回显卡读 `IVs`/`ADs` */
  m03: ['付款通知书', '付款计划', '项目档案'],
  m04: ['付款计划', '付款通知书', '付款域', '机械 6 列'],
  m05: ['付款域', '修改留痕', '机械 6 列'],
  m06: ['机械 6 列', '库存单据', '收发结存与大表'],   /* 过程资料读 `MACH6`/`IVs`/`EXTM`/`BIGVAL` */
  m07: ['机械 6 列', '库存单据', '收发结存与大表'],
  m08: ['库存单据'],
  m09: ['特殊费用月报表'],
  m14: ['规则配置'],
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
  '修改留痕': async () => {
    const tr = await API.trails();
    PJ_TRAIL.splice(0, PJ_TRAIL.length, ...(tr || []).map(adaptTrail));
  },
  '付款计划': async () => {
    const pl = await API.plans(); PLs = (pl.rows || []).map(adaptPlan);
  },
  '机械 6 列': reloadMech,
  '库存单据': reloadInv,
  /* ⚠️ `m09` 的自动项与手填项**都由后端自己算**（`mod09_fee/repository.inv_rows` 直读 `inv_detail`）
     ⇒ 与壳里的 `IVs` 无关、**不依赖 `reloadInv` 的顺序**。 */
  '特殊费用月报表': reloadM09,
  '规则配置': reloadM14,        /* 独立取数 ⇒ 无顺序依赖 */
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
const soft = async (label, fn) => {
  try { await fn(); } catch (e) { fails.push(`${label}：${String((e && e.message) || e)}`); }
};
const LOADED = new Set();          /* 已经拉过的路（同一页反复进出不重复拉） */

/** 按需取数：把 `labels` 里**还没拉过**的几路拉回来（依赖路放**第二组**）。 */
async function loadPaths(labels) {
  const fresh = (labels || []).filter(l => !LOADED.has(l));
  if (!fresh.length) return;
  await Promise.all(fresh.filter(l => !LOAD_DEP.has(l)).map(l => soft(l, LOADERS[l])));
  await Promise.all(fresh.filter(l => LOAD_DEP.has(l)).map(l => soft(l, LOADERS[l])));
  fresh.forEach(l => LOADED.add(l));
  BOOT_ERROR = fails.join('；');
  render();                          /* 各路内部多数已 render 一次；这里兜一次（幂等） */
  if (BOOT_ERROR) bootErrorBanner();
}

async function boot() {
  /* 首屏只拉**初始视图**要的那几路（`home` ⇒ 3 路；其余页在 `go()` 里按需拉）。
     ⚠️ `BOOTING` 的声明在 `m05Sync` 上方（`P3`① 加的，⛔ 别在这里重复声明 —— 会 SyntaxError）。 */
  await loadPaths(PAGE_LOAD[VIEW] || []);
  BOOTING = false;        /* ⏳ `P3`①：启动收尾才允许 `m05Sync()` 补拉（见它的注释） */
  render();
  if (BOOT_ERROR) bootErrorBanner();
}

/* ⚠️ 取数失败 ⇒ **在页面上常驻说明**（⛔ 不只 toast —— 它一闪而过，用户只看到"页面是空的"、
   还以为功能没做）。最常见原因 = **用 `file://` 双击打开了这个文件**：浏览器禁止 `file://`
   页面读后端接口 ⇒ 数据必然空。⭐ 实测踩到：展示壳时预览面板打开的正是
   `file:///…/app/web/index.html`，于是"看起来和原型没区别、还没有数据"。 */
function bootErrorBanner() {
  const why = location.protocol === 'file:'
    ? '你正在用 <b>file:// 直接打开这个 HTML 文件</b> —— 浏览器不许它读后端接口，所以页面是空的。'
    : '这几路没取到：<br><span class="fc">' + esc(BOOT_ERROR) + '</span><br>'
      + '<b>其余页的数据照常可用</b>（某一路失败不该拖垮全站）—— 如需重试，刷新页面即可。';
  const el = document.createElement('div');
  el.className = 'tip dg';
  el.style.cssText = 'position:fixed;left:0;right:0;top:0;z-index:9999;margin:0;border-radius:0';
  el.innerHTML = `⚠️ <b>没拿到数据</b> —— ${why}<br>`
    + '请改用<b>服务地址</b>打开：<b>http://127.0.0.1:8000/app</b>'
    + '（粘到浏览器地址栏回车；⛔ 不要双击 HTML 文件）';
  document.body.prepend(el);
}

/* 启动 */
