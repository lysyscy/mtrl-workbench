/* =============================================================================
   api.js —— 壳的**取数出口**（`API` 对象）
   ⭐ 2026-09-24 从 `core.js` 切出（依据 `work/10-designs/设计-文件拆分必要性判据-20260924.md` §八.5 第 1 刀）。
      接缝 = 「取数出口」与「渲染 / 动作」本就分开；本件**自包含**（块内只有 `const API`，其余全是箭头函数）
      ⇒ ⛔ 别引用 `core.js` 的**加载期**标识符（要引用只能写在函数体里 = 运行时才求值）。
   ⚠️ 挂载顺序的真源 = `index.html` 里 `<script src>` 的顺序：本件必须在 `core.js` **之前**。
   ⛔ 别把本件再塞回 `core.js`：`shell_verify` 比的是**并集**，搬动会让「只在旧版 / 只在现在」各多一堆行。
   ============================================================================= */

/* ⭐⭐ **报错「人话出口」**（唯一 · 2026-09-27 立 · 守则 §3.2 / §3.7 / §5.3）
   契约两条：
    ① **上屏的永远是用户语言 ＋ 下一步**；原始报错（方法 / 全路径 / HTTP 状态码）⛔ **绝不上屏**，
       只进 `err.tech` ＋ `console.warn` 留痕（排障要用 ⇒ 不是删掉，是**换地方**，守则 §5.8）。
    ② ⭐ **改在「抛出的那一处」**：壳里 60 余处 `catch` 显示的都是 `e.message`
       （`toast(...esc(e.message)...)`）⇒ 在源头把 message 写成用户语言，**全场自动受益**；
       ⛔ 别去逐个改那 60 处 —— 那等于把"人话"这件事抄 60 份，漏一处就是"用户又看到 HTTP 500"。
   ⚠️ **后端 `AppError` 给的中文必须原样透传**（如「壳下还有 3 个在建小微：A、B、C」）——
      那是「拦了就讲清**为什么 ＋ 怎么解决**」（§2.7.2）⇒ ⛔ 别被人话模板盖掉。
   ⚠️ 本件在 `core.js` **之前**挂载（见文件头）⇒ 这三件对 `core.js` / `actions.js` / `legacy.js` 都可见。 */
const ERR_NEXT = '请刷新页面重试；仍失败请把这一步告诉管理员。';
/* ⭐⭐ 2026-09-28（用户口径：「**提醒需要告诉具体原因和解决方法**」）——
   ⚠️ 仍守本件上面那条铁律：**原始报错（方法 / 全路径 / HTTP 状态码）一律不上屏**（只进 `err.tech`）。
   ⇒ 但"没能完成"这句话本身**太空**了（用户原话：光说"刷新页面重试 / 告诉管理员"没用，
      **管理员就是他自己**）⇒ 在**不违反铁律**的前提下，把原因**归类成人话**并把下一步写具体：
     仍不出现状态码、不出现 URL、不出现英文原文。 */
const errWhyByStatus = s => {
  const n = Number(s) || 0;
  if (n === 401 || n === 403) return ['登录状态过期、或这个动作没有权限', '请刷新页面重新登录；仍不行请核对当前账号的权限。'];
  if (n === 404 || n === 405) return ['这个动作还没生效（最常见的原因：刚更新过、但没有重启）',
    '请重启系统服务，再刷新页面重试（改过配置或代码都要重启才生效）。'];
  if (n >= 500) return ['系统内部出错了（不是你的输入问题）', '请刷新页面重试；一直不行请把这一步的时间点告诉维护人。'];
  return ['系统没有接受这一步', ERR_NEXT];
};
const errHuman = (why, tech) => {
  const e = new Error(why || ('这一步没能完成。' + ERR_NEXT));
  e.tech = String(tech || '');
  /* ⚠️ `warn`（不是 `error`）：真机自检只把 `console.error` 当失败 ⇒ 这里留痕但**不误报**。 */
  if (e.tech) console.warn('[没能完成]', why || '', e.tech);
  return e;
};

/* ⭐⭐ 2026-09-27（`TAIL-117` 批次 6 的 ㉗ 当场抓到的缺口）：**`fetch` 自己抛的那条路**也要人话。
   ⚠️ 症状（真机实测）：把 `m09` 那一路拦断后，页级错误态上写着 **`Failed to fetch`** ——
      那是**浏览器的英文原文**（fetch 承诺被拒时的 `TypeError.message`）。
      此前 `errHuman` 只罩住了"**服务器答了但状态码不对**"（`!r.ok`）这条；
      "**压根没答上来**"（服务没起 / 断网 / 被拦）走的是 fetch 的 reject ⇒ **原样漏到了屏幕上**。
   ⇒ 统一在这里收口：两句话都说清"**怎么了 ＋ 下一步**"（守则 §3.7）。⛔ 别在调用点各写一份。 */
const netErr = (tech) => errHuman(
  '连不上服务器 —— 请确认服务在运行、网络正常，然后重试。' + ERR_NEXT, tech);
/* ⚠️ **壳里所有取数都要过这里**（`GET` / `JSON 写` / 表单 / 文件 / 抓取）——
   ⛔ 别再直接写 `fetch`：漏一处就是"某条路上用户看到 `Failed to fetch`"。
   ⚠️ 判据 `tests/test_ux_states.py` 数的是"**没经过包装的取数**"（壳里只允许两处：
      本函数 ＋ `core.js::dlExport`——后者自己有一份人话 catch）。 */
const rawFetch = async (url, opts, tech) => {
  try { return await fetch(url, opts); }
  catch (e) { throw netErr(`${tech} · ${String((e && e.message) || e)}`); }
};
const getSafe = (url, tech) => rawFetch(url, { headers: { Accept: 'application/json' } }, tech);
const postSafe = (url, body, tech) => rawFetch(url, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body || {}),
}, tech);

const API = {
  async get(url) {
    const r = await getSafe(url, 'GET ' + url);
    if (!r.ok) { const [wy, nx] = errWhyByStatus(r.status);
      throw errHuman('这页的数据没能取到：' + wy + '。' + nx, `GET ${url} → HTTP ${r.status}`); }
    return r.json();
  },
  async post(url, body) {
    const r = await postSafe(url, body, 'POST ' + url);
    if (!r.ok) { const [wy, nx] = errWhyByStatus(r.status);
      throw errHuman('这一步没能完成：' + wy + '。' + nx, `POST ${url} → HTTP ${r.status}`); }
    markCrossPageStale();         /* ⭐ `TAIL-48` `P3`②：JSON 写出口（见 `markCrossPageStale`） */
    return r.json();              /* ⚠️ 恒 HTTP 200 —— 成败看 `ok` 标志（见 notice_api_router） */
  },
  /* ⭐ `PUT` 等其余方法走这个 —— ⚠️ **失败时把后端的 `message` 原样抛出**：
     `MOD-01` 的状态不变式是「拦了就讲清**为什么 + 怎么解决**」（§2.7.2），
     若只抛 `HTTP 400`，那句"壳下还有 3 个在建小微：A、B、C"就丢了 ⇒ 用户只看到"保存失败"。
     ⛔ 由 `core/errors.py::AppError` 统一转成 `{code, message}` + 对应状态码。 */
  async send(method, url, body) {
    const r = await rawFetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body || {}),
    }, `${method} ${url}`);
    const text = await r.text();
    let data = null;
    try { data = text ? JSON.parse(text) : null; } catch (e) { data = null; }
    /* ⭐ 两种情况分开（守则 §3.7）：**后端给了中文** ⇒ 原样透传（那是"为什么＋怎么解决"）；
       **后端没给**（网关 / 500 / 代理页）⇒ 换成人话，把原始体截断后只放进 `tech`（⛔ 不上屏）。 */
    if (!r.ok) {
      const why = (data && (data.message || data.detail)) || '';
      const [wy, nx] = errWhyByStatus(r.status);
      throw errHuman(why || ('这一步没能完成：' + wy + '。' + nx),
        `${method} ${url} → HTTP ${r.status}` + (why ? '' : ' · ' + String(text || '').slice(0, 300)));
    }
    markCrossPageStale();         /* ⭐ `TAIL-48` `P3`②：`PUT`/`POST` 写出口（`plDelete` 等走这条） */
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
  /* ⭐ `M5-5`「集采实际供应商」（§6.6.3）：判定（**仅「集采」分类可填**）与落库都在后端
     （`notice_actions.jc_supplier_problem` 是唯一出口）—— 前端只负责发与显示回执（⛔ 不本地改 `n.sup`）。 */
  jcSupplier: body => API.post('/api/m03/actions/jc-supplier', body),
  /* ⭐ `M5-5` 供应商**自动匹配**（§6.6.3）：判定**在后端**（`mod03_notice/sup_match.py`）——
     拿**本项目候选池**去探测**单据名**，返回 `{pool, level, level_name, cands}`。
     ⚠️ **只算不写**：1 家预填 / ≥2 家让选 / 0 家手动，三条分叉与"预填须经人采用"由壳编排；
        落库一律走上面的 `jcSupplier`。⛔ 壳里**不再自带**一套片段/等级算法（两份 = 迟早漂移）。 */
  m03SupMatch: body => API.post('/api/m03/actions/sup-match', body),
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
  /* ⭐ 看板 ⑦⑬⑭ 的取数口（2026-09-21 接线）—— ⚠️ **另起一个端点、⛔ 不复用 `m02Records`**：
     那个是**窗口**（`limit ≤ 200`），而 `run_record` 是**流水表**（≈10 条/天 ⇒ 一个月 ≈300 条）
     ⇒ 用窗口算「本月有没有成功抓取」**会漏、且漏了不报错**。
     本端点在后端走 **SQL 全表**（`app/home/service.py::run_counts`）。 */
  homeRunCounts: () => API.get('/api/home/run-counts'),

  /* ---- MOD-03 · 抓取 ＋ 链路 C 弹窗（`TAIL-29`-② ④） ---- */
  /* ⭐ 抓取：**失败也要看回执** —— 「归属未走完」是**可预期的失败**（要拿它开弹窗）
     ⇒ 这里**不 throw**，把 body 原样返回，由调用方判 `ok`。 */
  fetchNotices: async year_month => {
    const r = await rawFetch('/api/m03/notices/fetch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ year_month, allow_kick: true }),
    }, 'POST /api/m03/notices/fetch');
    const body = await r.json().catch(() => ({}));
    markCrossPageStale();         /* ⭐ `TAIL-48` `P3`②：抓取是**跨页写**（`payment_notice`/`run_record`；
                                     ⚠️ 「归属未走完」也是**已落库**的可预期失败 ⇒ 成败都要标脏） */
    return r.ok ? { ok: true, ...body } : { ok: false, ...body };
  },
  unresolved: () => API.get('/api/m03/notices/unresolved'),
  /* ⭐ `TAIL-93`：**集采**侧的「归属未走完」清单（口径与上面那条**逐条对齐**：只认最近一次抓取 ＋
     按当前档案现算）。⚠️ 写仍走 `assignOwnership` —— 那个端点**只补档案、不写业务行**，两域共用一份。 */
  jcUnsettled: () => API.get('/api/m11/unsettled'),
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

  /* ---- MOD-07 收发结存与月度会大表（⚠️ 金额后端出**字符串** ⇒ 适配层过 `N0()`） ---- */
  m07Settlement: ym => API.get(`/api/m07/settlement?period=${encodeURIComponent(ym || '')}`),
  m07Extract: () => API.get('/api/m07/extract'),
  m07BalCell: body => API.post('/api/m07/extract/balance', body),
  m07Big: () => API.get('/api/m07/big'),
  m07BigCell: body => API.post('/api/m07/big/cell', body),
  m07BigSelection: selected => API.post('/api/m07/big/selection', { selected }),
  /* ⭐ 抓取：**失败也要看回执**（降级说明在 `message` 里）⇒ 不 throw，由调用方判 `ok`。 */
  m07Fetch: async month => {
    const r = await rawFetch('/api/m07/fetch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ month, confirm: true }),
    }, 'POST /api/m07/fetch');
    const body = await r.json().catch(() => ({}));
    markCrossPageStale();         /* ⭐ `TAIL-48` `P3`②：抓取落 `setl_detail` ⇒ m06/m07 都读它 */
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
  /* ⛔ `m04ImportParse` / `m04ImportConfirm` 已撤（`TAIL-75` `B5c` · 2026-09-22）：
     付款计划的导入改走**通用导入面**（`impParse/impPreview/impCommit`，见下方 `API.imp*`）——
     壳里不许再留第二条导入路（`plImport` 现在只是"跳到向导并预选本域"）。 */
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
    const r = await rawFetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams(obj || {}).toString(),
      redirect: 'follow',
    }, `POST ${url}`);
    if (!r.ok) { const [wy, nx] = errWhyByStatus(r.status);
      throw errHuman('这一步没能完成：' + wy + '。' + nx, `POST ${url} → HTTP ${r.status}`); }
    markCrossPageStale();         /* ⭐ `TAIL-48` `P3`②：PRG 表单写出口（期初录入 / 台账备注） */
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
  m06Matrix: () => API.get('/api/m06/matrix'),
  /* ⭐ `TAIL-38`：「录机械费」写入口 —— 校验与落库**全在后端**
     （`mech_ui.parse_mech_values` ＋ `repository.save_mech`），与 PRG 端点同一份判定。 */
  m06MechSave: body => API.post('/api/m06/mech', body),
  /* ⭐ `TAIL-156` `P2`：`m09` **月度批量录入**的唯一出口（一次写「N 个核算月 × M 个项」；
     语义 = 按 (月, 项目, 项名) 幂等 / 空格外跳过 / 一格非法整批不写 —— 见 `mod09_fee.service.act_batch`） */
  m09Batch: body => API.post('/api/m09/fee/batch', body),

  /* ---- MOD-14 剔除规则（`TAIL-40`）⚠️ 唯一主人在库；⛔ 前端不做任何本地改数据冒充落库 ---- */
  m14Rules: () => API.get('/api/m14/rules'),
  m14RuleAdd: body => API.post('/api/m14/rules', body),
  m14RuleSet: (id, body) => API.send('PUT', `/api/m14/rules/${id}`, body),
  /* ⭐ `MOD-15` 用户管理（§1.5）：整页数据 = 列表 ＋ **当前登录用户** ＋ 三态计数。
     ⚠️ 它是 `CUR`（"当前登录用户"）的**唯一来源** —— 别再另开一个"我是谁"的取数口。 */
  users: () => API.get('/api/m15/users'),
  m15Theme: () => API.get('/api/m15/theme'),
  m15ThemeSet: theme => API.post('/api/m15/theme', { theme }),
  /* ⭐ 界面大小档位（`TAIL-129`）：与主题同构 —— **只改自己那一行**（⛔ 不接 `id`） */
  m15UiScaleSet: uiScale => API.post('/api/m15/ui-scale', { ui_scale: uiScale }),
  m15Password: id => API.get(`/api/m15/password?id=${encodeURIComponent(id)}`),
  /* ⭐ `§7.8` i8 绑定（每人一份）：**写**出口。
     ⚠️ `i8Pwd === null` ⇒ 请求里**不带** `i8_password` ⇒ 后端**不改密码**
        （界面上那个框是空的 = "我没改它"，⛔ 不是"清空它"）。 */
  m15I8: (id, i8User, i8Pwd) => API.post('/api/m15/actions/i8',
    i8Pwd === null || i8Pwd === undefined
      ? { id, i8_user: i8User }
      : { id, i8_user: i8User, i8_password: i8Pwd }),
  /* ⚠️ 6 个写动作**逐个对应后端端点**（⛔ 不在壳里拼一个"通用动作"——
     那样参数一多就分不清谁是谁，且后端加校验时看不出该改哪儿）。 */
  m15Create: (account, name, password) =>
    API.post('/api/m15/actions/create', { account, name, password }),
  m15Pwd: (id, password) => API.post('/api/m15/actions/password', { id, password }),
  m15Status: (id, status) => API.post('/api/m15/actions/status', { id, status }),
  m15Delete: id => API.post('/api/m15/actions/delete', { id }),
  m15Restore: id => API.post('/api/m15/actions/restore', { id }),
  m15Transfer: id => API.post('/api/m15/actions/transfer', { id }),
  /* ⚠️ 登出**由后端清 cookie**（`delete_cookie`）⇒ 壳这边只管**跳登录页**。 */
  m15Logout: () => API.post('/api/m15/logout', {}),
  /* ⚠️ 写动作**恒 HTTP 200**，成败看回包的 `ok` —— 规则不合法是 §4.2.2 的可预期拒绝，
     后端那句中文必须原样给用户看。 */
  m14RuleDel: id => API.send('DELETE', `/api/m14/rules/${id}`, null),
  /* ⭐ `TAIL-96` 集采项目**剔除名单**（页面在 M14、数据主人在集采域 ⇒ 与上面「剔除规则」同构） */
  m14JcIgnore: () => API.get('/api/m14/jc-ignore'),
  m14JcIgnoreAdd: body => API.post('/api/m14/jc-ignore', body),
  m14JcIgnoreSet: (id, body) => API.send('PUT', `/api/m14/jc-ignore/${id}`, body),

  /* ---- MOD-09 特殊费用月报表（`TAIL-27`）⚠️ 金额后端出**字符串** ⇒ 适配层过 `N0()` ---- */
  m09Fee: (ym, pj) => API.get(`/api/m09/fee?ym=${encodeURIComponent(ym || '')}`
    + `&pj=${encodeURIComponent(pj || '')}`),
  m09Add: body => API.post('/api/m09/fee/add', body),
  m09Name: body => API.post('/api/m09/fee/name', body),
  m09Amount: body => API.post('/api/m09/fee/amount', body),
  m09Delete: body => API.post('/api/m09/fee/delete', body),

  /* ---- MOD-11 集采台账（`M5-7`）⚠️ 金额后端出**字符串** ⇒ 适配层过 `N0()` ---- */
  m11List: () => API.get('/api/m11/list'),
  m11Detail: id => API.get(`/api/m11/detail?id=${encodeURIComponent(id)}`),
  /* ⭐ `M5-5` 付款域双向引用：**关联 / 解绑**。
     ⚠️ 关联关系**不另建表** —— 就写进合同的**付款子表**（`source=notice` ＋ `notice_id`）⇒
        与「从付款域引用（R8）」是**同一份记录** ⇒ 两个入口调的是**同一个端点**（`ACC-JC-PAY-001/001-01`）。
     ⚠️ 一对一（换合同 = **先解绑再写新**）/ 全库去重 / 不校验金额 —— 三条判定全在后端。 */
  m11Link: body => API.post('/api/m11/link', body),
  m11Unlink: body => API.post('/api/m11/unlink', body),

  /* ⛔ `MOD-12` 差异登的四个接口（`m12List` / `m12Create` / `m12Delete` / `m12Status`）
     **已于 2026-09-20 删除**（用户裁定撤页 —— 依据见 `backend/app/main.py` 的 import 处注释）。
     ⛔ 别再加回来：差异的载体是**调整单**（`API.m08Adjust`），差异表由后端按调整单算（`m06`）。
     ⭐ 这四行方法体**已于 2026-09-20 夜一并删掉**（原来只剩说明、代码还挂着 ⇒ 越挂越像"还在用"）；
        守卫：`tools/audit/audit_common.py::CANCELLED` ＋ `doc_audit` 的 `T8`。 */
  /* ⭐ `M5-6b` 甲方单位分类：它决定「i8 抓来的那个合同价是谁的价」。
     ⚠️ 正常甲方 ⇒ i8 的价 = **供应商价**（落 `contract_amt` · **锚点**）；
        贸易公司甲方 ⇒ i8 的价 = **贸易公司的价**（落 `trade_contract_amt`），
        而真供应商价 i8 里**没有** ⇒ 要人工从 Excel 供应商线补进 `contract_amt`。
     ⚠️ 没见过的甲方抓取时会**自动落成「未指定」**（⛔ 不静默当成正常）⇒ 页面得能指定。 */
  m11PartyKinds: () => API.get('/api/m11/party-kinds'),
  m11SetPartyKind: body => API.post('/api/m11/party-kind', body),
  /* ⭐ `M5-9` 集采台账导出（2026-09-20 用户定）：
     **行** = 页面上当前看到的那些（传 id ⇒ 口径与屏幕 100% 一致）；
     **列** = **全列**（含「贸易公司」3 列）—— 用户选 **(B)**：屏幕上的"隐藏列"**只是屏幕的事**。
     ⚠️ 走 POST 回来的是 **base64**（id 可能几百个 ⇒ GET 的 URL 会超长）⇒ 前端造 Blob 下载。 */
  m11Export: body => API.post('/api/m11/export', body),
  /* ⛔ `m11ImportParse` / `m11ImportCommit`（`/api/m11/import/*`）**已连件删除**
     （`TAIL-75` 余项 · 2026-09-23 **用户裁定**：「导入只在启用初期用一次」⇒ **只留通用面**）。
     ⭐ 集采台账导入改走 `impParse/impPreview/impCommit` 的 `m11_jc` 域（见下方 `API.imp*`）。 */
  /* ⚠️ 写动作**恒 HTTP 200**，成败看回包的 `ok`（可预期的拒绝 = `ok:false` ＋ 一句中文）。 */
  m11Tag: body => API.post('/api/m11/tag', body),          /* {id, tag} 或 {ids:[…], tag} */
  m11Add: body => API.post('/api/m11/add', body),
  m11Fields: body => API.post('/api/m11/fields', body),    /* {id, fields:{…}}（白名单列） */
  m11InvAdd: body => API.post('/api/m11/invoice/add', body),
  m11InvDel: body => API.post('/api/m11/invoice/del', body),
  m11PayAdd: body => API.post('/api/m11/payment/add', body),
  m11PayDel: body => API.post('/api/m11/payment/del', body),
  /* ⚠️ 抓取**会顶号**（`D9`）⇒ `confirm:true` = 用户已在确认弹窗里点过；缺它后端一律拒。
     ⭐ `M5-6`：`since`（`YYYY-MM-DD`）= **单据日期起点** ⇒ 空串 = 让后端用 `default_since`
        （库里最大合同日期 − 3 天）；**实测**增量 1~5 秒 vs 全量 40 秒。 */
  m11Fetch: (since = '') => API.post('/api/m11/fetch', { confirm: true, since }),

  /* ---- ⭐ `§19`「四个暂留件收口」（2026-09-21）：系统设置 ＋ 三个历史导入 ----
     ⚠️ 这四页原先**只有服务端渲染页**（壳里零入口 ⇒ 一直删不掉）—— 现在能力搬进壳
        （页在 `web/shell/legacy.js`），服务端那四个渲染件与它们的 PRG 已删。
     ⚠️ 判定**一行都不在壳里**：格式校验 / 留痕 / 落库 / 批量回滚 / 幂等刷新全在后端。
     ⚠️ 四个端点**恒 HTTP 200 ＋ `ok` 标志**（可预期的拒绝也是 `ok:false` ＋ 一句中文）——
        ⛔ 别把它们当成"抛异常"来写，否则后端那句原因会被吞掉。 */
  /* 系统设置（§7.8）：列表 = 设置项 ＋ 提示 ＋ 变更留痕；保存 = 只处理传进来的 key。 */
  m14Settings: () => API.get('/api/m14/settings'),
  m14SettingsSave: body => API.post('/api/m14/settings', body),
  /* ⛔ `m05ImpMeta`（`/api/m05/import/meta`）**已删除**（`TAIL-75` `B5b` 第三步 · 2026-09-23 用户裁定 `B`）：
     历史付款导入**只剩通用面一条路**（`/api/imp/m05_flow/{schema,parse,preview,commit,rollback}`）——
     列契约改从**域声明**出（`mod05_flow/imp_spec.py` 的 `SPEC.as_schema()`）。 */
  /* 过程资料历史导入（§5.2.5 ①②）：项目候选 / 截止核算月 / 批次 ＋ 列说明。 */
  /* ⭐ **域上下文**（候选项目 / 截止月 / 批次…）—— 通用面**唯一**一条（`/api/imp/{domain}/options`）。
     ⛔ `m06ImpData`（`/api/m06/import/data`）**已删除**（`TAIL-75` `B5c-2` · 2026-09-23）：
        加一个域不该在壳里再加一条专属读端点。 */
  impOptions: domain => API.get(`/api/imp/${encodeURIComponent(domain)}/options`),
  /* ⭐ `TAIL-75` `B5`（2026-09-22）**通用导入面**（域清单 ＋ 五个端点）—— 一套面盖所有已挂的域。
     ⚠️ `parse` 是 **multipart/form-data**（`FormData` ＋ 不手设 Content-Type，见 `postFile` 上方注释）；
     ⚠️ 所有端点**恒 HTTP 200 ＋ `ok` 标志**（可预期的拒绝也是 `ok:false` ＋ 一句中文）⇒ ⛔ 别当异常写。 */
  impDomains: () => API.get('/api/imp/domains'),
  impSchema: domain => API.get(`/api/imp/${encodeURIComponent(domain)}/schema`),
  impParse: (domain, fd) => API.postFile(`/api/imp/${encodeURIComponent(domain)}/parse`, fd),
  impPreview: (domain, body) => API.post(`/api/imp/${encodeURIComponent(domain)}/preview`, body),
  impCommit: (domain, body) => API.post(`/api/imp/${encodeURIComponent(domain)}/commit`, body),
  impRollback: (domain, body) => API.post(`/api/imp/${encodeURIComponent(domain)}/rollback`, body),
  /* ⛔ `m08ImpMeta` 已随「库存单据手动导入」删除（2026-09-22 用户裁定；`T8` 守卫）。 */
  /* ⚠️ 三个导入的「解析」都是 **multipart/form-data**（⛔ 不是 JSON）⇒ `FormData` ＋ **不手动设
     Content-Type**（浏览器要自己带 boundary；手设会把 boundary 写丢 ⇒ 后端收不到文件）。
     此件即 `m04Import` 那段逻辑的共用出口（⛔ 别在调用方各写一遍）。 */
  postFile: async (url, fd) => {
    const r = await rawFetch(url, { method: 'POST', body: fd }, `POST ${url}`);
    const text = await r.text();
    let data = null;
    try { data = text ? JSON.parse(text) : null; } catch (e) { data = null; }
    if (!r.ok) {
      const why = (data && (data.message || data.detail)) || '';
      throw errHuman(why || ('文件没能交上去。请重新选一次文件再试；仍失败请把这一步告诉管理员。'),
        `POST ${url} → HTTP ${r.status}` + (why ? '' : ' · ' + String(text || '').slice(0, 300)));
    }
    markCrossPageStale();         /* ⭐ `TAIL-48` `P3`②：文件写出口（导入解析等） */
    return data;
  },
};
