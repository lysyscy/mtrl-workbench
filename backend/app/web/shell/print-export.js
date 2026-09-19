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
  if (!ids.length) return toast('这些行缺少后端 id ⇒ 请先刷新页面再试');
  const what = mode === 'print' ? '批量打印' : '只导出 PDF';
  toast(`正在${what} <b>${ids.length}</b> 条 ……`, 4000);
  let r = null;
  try { r = await API.m03Batch(ids, mode); }
  catch (e) { return toast(`⚠️ <b>${what}没能完成</b>：${esc(String((e && e.message) || e))}`, 9000); }
  const bad = (r.items || []).filter(x => !x.ok);
  /* ⭐ `TAIL-46`-①：**已投递但无法核实**（`ok=true, unverified=true`）**不算失败** ——
     ⚠️ 用户 2026-09-18 实测教训：「假失败比假成功更危险」：报失败 ⇒ 人以为没打、**重复再打白浪费纸**。
     ⇒ 单独说出来 ＋ 叫人**去看打印机**，⛔ 不并进"失败"。 */
  const unver = (r.items || []).filter(x => x.ok && x.unverified);
  const unprinted = r.unprinted_bill_nos || [];
  return toast([
    `<b>${what}完成</b>：成功 <b>${r.success}</b> / 共 ${r.total}`,
    unver.length ? `（其中 <b>${unver.length}</b> 条**已投递但未核实**）` : '',
    r.failed ? ` · 失败 <b>${r.failed}</b>` : '',
    unver.length ? `<br>⚠️ <b>已投递但未核实</b>的 ${unver.length} 条：请**看打印机实际出纸**，⛔ <b>别重复打印</b>` : '',
    unprinted.length ? `<br>⚠️ <b>未产出的单号</b>：${esc(unprinted.join('、'))}` : '',
    bad.length ? `<br><span class="sm">失败原因：${esc(bad.slice(0, 3).map(x => `${x.bill_no || x.notice_id}：${x.reason || '未说明'}`).join('；'))}${bad.length > 3 ? ` …另 ${bad.length - 3} 条` : ''}</span>` : '',
    mode === 'print' ? '<br><span class="sm mut">本系统只把勾选的通知书交给 i8（<b>不自建打印模板</b> · DEV-P-07）</span>' : '',
  ].join(''), 9500);
}

/* ⭐ `TAIL-46`：**打印机设置**入口（旧页 `m03.html` 那个 `btnSettings` 的事）——
   ⚠️ 壳的 `V.m03` 切片里**没有**这个入口（改切片会登记漂移）⇒ 由 `BIND.m03` **渲染后注入**。
   ⚠️ 地址读写走 `GET/PUT /api/m03/settings/printer`（后端**写配置 + 清缓存** ⇒ 保存即生效、无需重启）。 */
async function m03PrinterOpen() {
  let s = {}, prs = [];
  try { s = (await API.printerGet()) || {}; }
  catch (e) { return toast(`⚠️ 读不到当前打印机设置：${esc(String((e && e.message) || e))}`, 8000); }
  /* ⚠️ 本机打印机名取不到**不算错**（没装 pywin32 / 不是 Windows）⇒ 只影响"给不给提示" */
  try { prs = (await API.printerList()) || []; } catch (_) { prs = []; }
  const cur = String(s.printer_ipp_url || ''), mode = String(s.print_mode || 'auto');
  const nm = String(s.printer_name || '');
  /* ⚠️ 通道口径照用户调好的 `i8一键打印_新版`（2026-09-18）——**只把说明摆出来**，
       判定全在后端（`settings_store.validate_print_mode`）。 */
  const MODES = [
    ['auto', '自动（推荐）', '依次试：IPP → 系统驱动 → RAW 9100。换任何打印机都能打，不用先知道它的脾气'],
    ['ipp', 'IPP', '只用标准方式。好处是能确认打印机真的收件、打完了（Ricoh IM 3000 用这个）'],
    ['driver', '系统驱动', '走 Windows 打印驱动出纸，最稳的一条路 —— ⚠️ 这台电脑必须装过那台打印机的驱动，且下面要选「打印机名」'],
    ['raw', 'RAW 9100', '只用 RAW 通道。只对"自己能读 PDF"的打印机有意义 —— ⚠️ 多数小型机用它可能打出乱码'],
  ];
  modal({
    title: '打印机设置',
    body: `<div class="tip" style="margin:0 0 10px">保存后<b>即时生效、无需重启</b>（后端写配置并清缓存）—— 打印投递按新设置走。</div>
      <div class="fld"><label>打印机 IPP 地址</label>
        <input class="inp" id="m03PrinterUrl" style="width:100%" value="${esc(cur)}" placeholder="ipp://192.168.5.248"></div>
      <div class="fld" style="margin-top:8px"><label>出纸通道</label>
        <select class="inp" id="m03PrintMode" style="width:100%">
          ${MODES.map(m => `<option value="${m[0]}" ${m[0] === mode ? 'selected' : ''}>${m[1]} —— ${m[2]}</option>`).join('')}
        </select></div>
      <div class="tip wn" style="margin:8px 0 0"><b>打不出纸 / 打出乱码时看这里</b>：不同打印机认的投递方式不一样 ——
      原来能打的（Ricoh）保持<b>自动</b>不用动；换新机器先试<b>自动</b>，若打出来是<b>乱码</b>就改选<b>系统驱动</b>
      （有的打印机<b>没有 PDF 解释器</b>，只认位图格式，这时 IPP 会被直接拒收、RAW 会收下但打成乱码）。</div>
      <div class="fld" style="margin-top:8px"><label>打印机名（只有选「系统驱动」才用得上）</label>
        <input class="inp" id="m03PrinterName" list="m03PrinterNames" style="width:100%" value="${esc(nm)}" placeholder="如：RICOH IM 3000 PCL 6（名字要**一字不差**）">
        <datalist id="m03PrinterNames">${prs.map(p => `<option value="${esc(p)}"></option>`).join('')}</datalist>
        <div class="mut sm" style="margin-top:4px">${prs.length
          ? `本机装了驱动的打印机有 <b>${prs.length}</b> 台（点输入框可选）：${esc(prs.slice(0, 4).join(' / '))}${prs.length > 4 ? ' …' : ''}`
          : '⚠️ 没取到本机打印机名（这台机器没装 <span class="fc">pywin32</span> 或不是 Windows）⇒ 名字要手填'}</div></div>`,
    footer: `<button class="btn" data-act="closeModal">取消</button>
      <button class="btn pri" data-act="m03PrinterSave">保存</button>`,
  });
}
