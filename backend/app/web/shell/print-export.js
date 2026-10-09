/* shell/print-export.js —— 壳接线层③：**打印 / 导出 / 设置**（`MOD-03` 的两个真出口）
 *
 * 来源：`index.html` 的第 L5619–L5687 行（`P4`② 三刀真拆 · 2026-09-19），原文逐字搬出、顺序未改。
 * 内容：`m03RunBatch`（批量打印 / 只导出 PDF 的唯一出口）· `m03PrinterOpen`（打印机设置入口）。
 * ⚠️ 另一些打印/导出入口**仍留在各自的对象里**（`ACT.ntPrint` / `ACT.zipSfjc` / `ACT.m03Printer*` / `API.printer*`）
 *    —— 那是**表驱动结构**（`ACT` 是个 1700 行的大对象）⇒ 强拆会把结构拆烂（§23 的权衡说明）。
 */
/* ⭐ `TAIL-46`：批量打印 / 只导出 PDF 的**唯一出口** —— 壳里两个入口（`ntPrint` / `ntPdf`）共用。
   ⚠️ 结果必须**逐条如实**：失败带原因、**未产出的单号显式列出**（001-07 / PDF-001-06 都要求）。
   ⛔ 不吞错、⛔ 不把"失败"说成"成功"；⛔ 不做本地打印/排版（DEV-P-07：接口不可用即砍这条功能）。 */
async function m03RunBatch(rows, mode) {
  const ids = rows.map(n => Number(n.id)).filter(x => Number.isFinite(x));
  if (!ids.length) return toast('这些行还没载全 ⇒ 请先刷新页面再试');
  const what = mode === 'print' ? '批量打印' : '只导出 PDF';
  toast(`正在${what} <b>${ids.length}</b> 条 ……`, 4000);
  let r = null;
  try { r = await API.m03Batch(ids, mode); }
  catch (e) { return toast(`⚠️ <b>${what}没能完成</b>：${esc(String((e && e.message) || e))}`, 9000); }
  /* ⚠️⚠️ **必须先看 `ok`**（2026-09-20 用户实测修）：
     后端对**执行失败**回的是 `{ok:false, message:"批量执行失败：…"}` ——
     ⚠️ 它走的是 **HTTP 200**（全站口径：成败看 `ok`，不看状态码）⇒ `API.post` **不会抛**。
     原先这里**不看 `ok`** 就直接读 `r.success` / `r.total` ⇒ 失败会显示成
     「**完成**：成功 `undefined` / 共 `undefined`」
     ⇒ **把失败说成完成**（本项目最忌的那类假成功），而且**真因那句话被整个丢掉** ——
        用户只能看到两个 undefined，既报不准、我也查不动。
     ⇒ 现在就把它顶掉：失败**第一句就是中文真因**。 */
  if (!r || r.ok === false) {
    return toast(`⚠️ <b>${what}没能完成</b>：${esc((r && r.message) || '系统没有给出原因，请重试')}`, 12000);
  }
  const bad = (r.items || []).filter(x => !x.ok);
  /* ⭐ `TAIL-46`-①：**已投递但无法核实**（`ok=true, unverified=true`）**不算失败** ——
     ⚠️ 用户 2026-09-18 实测教训：「假失败比假成功更危险」：报失败 ⇒ 人以为没打、**重复再打白浪费纸**。
     ⇒ 单独说出来 ＋ 叫人**去看打印机**，⛔ 不并进"失败"。 */
  const unver = (r.items || []).filter(x => x.ok && x.unverified);
  const unprinted = r.unprinted_bill_nos || [];
  const msg = [
    `<b>${what}完成</b>：成功 <b>${r.success}</b> / 共 ${r.total}`,
    unver.length ? `（其中 <b>${unver.length}</b> 条<b>已投递但未核实</b>）` : '',
    r.failed ? ` · 失败 <b>${r.failed}</b>` : '',
    unver.length ? `<br>⚠️ <b>已投递但未核实</b>的 ${unver.length} 条：请<b>看打印机实际出纸</b>，⛔ <b>别重复打印</b>` : '',
    unprinted.length ? `<br>⚠️ <b>未产出的单号</b>：${esc(unprinted.join('、'))}` : '',
    bad.length ? `<br><span class="sm">失败原因：${esc(bad.slice(0, 3).map(x => `${x.bill_no || x.notice_id}：${x.reason || '未说明'}`).join('；'))}${bad.length > 3 ? ` …另 ${bad.length - 3} 条` : ''}</span>` : '',
    mode === 'print' ? '<br><span class="sm mut">本系统只把勾选的通知书交给 i8（<b>不自建打印模板</b>）</span>' : '',
  ].join('');
  /* ⭐⭐ 2026-09-20 **导出改浏览器下载**（用户口径：「如果导出的话，换成浏览器下载吧」）——
     后端**不再往本机写文件**（旧做法攒了 884 个、壳里还压根没用那条路径）；
     这批字节现在停在服务端 `pdf_cache` 里等我们**取一次**（单张 = PDF / 多张 = 打包 zip）。
     ⚠️ **一张都没成** ⇒ 没有产物可下 ⇒ 只把原因如实报出来（⛔ 别去下一个空文件）。
     ⚠️ **部分失败** ⇒ 成功的那些**照样下载**（人点导出就是要拿到能出的那几张），
        失败的照实写在**同一条提示**里 —— 两件事都不瞒（禁静默）。 */
  if (mode !== 'pdf') return toast(msg, 9500);
  if (!r.success) return toast(msg, 12000);
  return m03Download(((r.items || []).find(x => x.download_url) || {}).download_url, msg);
}

/* ⭐ 浏览器下载（照 `procExpSave` / `expPivot` 那套：`fetch → 看 content-type → blob → <a download>`）。
   ⚠️⚠️ **必须先看 `content-type`**：后端"过期 / 重启过"时回的是 **JSON 200 ＋ 中文**
      —— 若直接当文件存下来，用户会拿到一个**打不开的「PDF」**、还不知道为什么。
   ⚠️ 文件名**由后端带出**（`X-Export-Filename`，UTF-8 percent-encoded）⇒ ⛔ 壳里不自己拼
      （命名规则一旦两处各写一份，改一处就会静默走形 · 同 `m06`/`m07`/`m08` 口径）。
   ⚠️ **文件顶层的函数** ⇒ ⛔ 不许塞进 `ACT` 对象字面量（那个坑踩过三次：`jcLinkAct` /
      `jcFetchSinceOn` / `jcHideTrade`）。 */
async function m03Download(url, okMsg) {
  if (!url) return toast(`<b>下载没能开始</b>：系统没有给出下载地址${okMsg ? `<br>${okMsg}` : ''}`, 10000);
  const fn=await dlExport(url,{name:'付款通知书.pdf',label:'下载'});
  if(!fn) return;
  return toast(`${okMsg}<br>已开始下载 <b>${esc(fn)}</b>`, 11000);
}

/* ⭐ `TAIL-46`：**打印机设置**入口（旧页 `m03.html` 那个 `btnSettings` 的事）——
   ⚠️ 壳的 `V.m03` 切片里**没有**这个入口（改切片会登记漂移）⇒ 由 `BIND.m03` **渲染后注入**。
   ⚠️ 地址读写走 `GET/PUT /api/m03/settings/printer`（后端**写配置 + 清缓存** ⇒ 保存即生效、无需重启）。 */
async function m03PrinterOpen() {
  let s = {}, prs = [], setItems = [];
  try { s = (await API.printerGet()) || {}; }
  catch (e) { return toast(`⚠️ 读不到当前打印机设置：${esc(String((e && e.message) || e))}`, 8000); }
  /* ⚠️ 本机打印机名取不到**不算错**（没装 pywin32 / 不是 Windows）⇒ 只影响"给不给提示" */
  try { prs = (await API.printerList()) || []; } catch (_) { prs = []; }
  /* ⭐⭐ 2026-09-27（`TAIL-127` · 用户裁定 B）：**两个「打印版式 ID」也搬进这个弹窗** ——
     它们原先在「系统设置」页（用户：「连接参数……不可能有变动」）。**打印相关的都在一处**，
     谁改打印谁看得见。⚠️ 与打印机地址**存储不同**（分两步保存，见 `ACT.m03PrinterSave`）：
       · 打印机地址 → **`.env`**（本弹窗自己的端点 `PUT /api/m03/settings/printer`）
       · 版式 ID     → **库**（`/api/m14/settings`，**逐项留痕**）
     ⚠️ 版式这两格照旧渲染后端给的 `it.label` / `it.hint`（「与直觉相反 / 配反了会印错版式」
        必须**原样来自后端**，判据 `001-04` 钉着）—— ⛔ 别在壳里另写一份文案。 */
  try { setItems = ((await API.m14Settings()) || {}).items || []; } catch (_) { setItems = []; }
  const pidField = (id, key) => {
    const it = setItems.find(x => x.key === key);
    if (!it) return '';
    const src = it.stored ? '<span class="tag t-pri">本处所设</span>' : '<span class="tag t-in">.env</span>';
    const meta = it.stored
      ? `当前生效：<b class="fc">${esc(it.effective)}</b>（本处所设；清空并保存即回落到 <code>.env</code>）`
      : (it.env ? `未设置过 ⇒ 现在用 <code>.env</code> 的值：<b class="fc">${esc(it.env)}</b>`
        : '未设置过，且 <code>.env</code> 也是空的');
    return `<div class="fld" style="margin-top:calc(8px * var(--fscale))"><label>${esc(it.label)} ${src}</label>
        <input class="inp" id="${id}" style="width:100%" value="${esc(it.stored)}"
          placeholder="${esc(it.env)}" autocomplete="off">
        <div class="hint">${em(it.hint)}</div>
        <div class="hint mut">${meta}</div></div>`;
  };
  const cur = String(s.printer_ipp_url || ''), mode = String(s.print_mode || 'auto');
  const nm = String(s.printer_name || '');
  /* ⚠️ 通道口径照用户调好的 `i8一键打印_新版`（2026-09-18）——**只把说明摆出来**，
       判定全在后端（`settings_store.validate_print_mode`）。 */
  const MODES = [
    ['auto', '自动（推荐）', '自动选择出纸通道'],
    ['ipp', 'IPP', '只用 IPP 通道'],
    ['driver', '系统驱动', '须在本机安装驱动并填写打印机名'],
    ['raw', 'RAW 9100', '不支持该通道的打印机可能打出乱码'],
  ];
  modal({
    title: '打印机设置',
    body: `<div class="tip" style="margin:0 0 calc(10px * var(--fscale))">保存后按新设置打印。</div>
      <div class="fld"><label>打印机 IPP 地址</label>
        <input class="inp" id="m03PrinterUrl" style="width:100%" value="${esc(cur)}" placeholder="ipp://192.168.5.248"></div>
      <div class="fld" style="margin-top:calc(8px * var(--fscale))"><label>出纸通道</label>
        <select class="inp" id="m03PrintMode" style="width:100%">
          ${MODES.map(m => `<option value="${m[0]}" ${m[0] === mode ? 'selected' : ''}>${m[1]} —— ${m[2]}</option>`).join('')}
        </select></div>
      <div class="tip wn" style="margin:calc(8px * var(--fscale)) 0 0">优先选自动；无法出纸或出现乱码时，可尝试系统驱动。</div>
      <div class="fld" style="margin-top:calc(8px * var(--fscale))"><label>打印机名（只有选「系统驱动」才用得上）</label>
        <input class="inp" id="m03PrinterName" list="m03PrinterNames" style="width:100%" value="${esc(nm)}" placeholder="如：RICOH IM 3000 PCL 6（名字要一字不差）">
        <datalist id="m03PrinterNames">${prs.map(p => `<option value="${esc(p)}"></option>`).join('')}</datalist>
        <div class="mut sm" style="margin-top:calc(4px * var(--fscale))">${prs.length
          ? `本机装了驱动的打印机有 <b>${prs.length}</b> 台（点输入框可选）：${esc(prs.slice(0, 4).join(' / '))}${prs.length > 4 ? ' …' : ''}`
          : '⚠️ 没取到本机打印机名（这台机器没装 <span class="fc">pywin32</span> 或不是 Windows）⇒ 名字要手填'}</div></div>
      <div class="tip" style="margin:calc(12px * var(--fscale)) 0 0">打印版式填写 i8 模板编号；不确定时请勿修改，改错会印错版式。</div>
      ${pidField('m03PidMat', 'i8_print_id_material')}${pidField('m03PidMech', 'i8_print_id_mechanical')}`,
    footer: `<button class="btn" data-act="closeModal">取消</button>
      <button class="btn pri" data-act="m03PrinterSave">保存</button>`,
  });
}
