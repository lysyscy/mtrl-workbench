/* shell/legacy.js —— 壳接线层④：**「四个暂留件」的壳内实现**（系统设置页 ＋ 三个历史导入页）。
 *
 * ⭐ **为什么单开一件**：本仓既定做法 =「**接线层可以加件，原型切片一行不动**」—— 这四页是**壳新增**的
 *    （原型里根本没有）⇒ `ui_parity` 的 `U1`（只比原型**同名** `V.*` 切片）**看不见本件** ⇒ 零漂移风险。
 * ⛔ **本件不许碰**：任何 `V.<原型页>` 切片 · `ACT` 里既有动作（一律**追加**：`V.set = …`）。
 * ⚠️⚠️ **加载顺序有严格要求**（`index.html` 的 `<script src>` 顺序即真源）：① 在 `actions.js` **之后**
 *    （本件要往 `ACT` 追加）；② 在 `core.js` **之前** —— `core.js` 的 `LOADERS` 表**加载期就求值**到
 *    `reloadSet` 这几位，而它们住在本件里：放在它之后 ⇒ `reloadSet is not defined` ⇒ `core.js` **整支中止**
 *    （`boot` 都没定义）⇒ 白屏，而离线断言（含 `node --check`）**全绿** —— 只有真机 console 才看得见。
 * ⚠️ 取数一律走 `API`（唯一数据出口）；判定**一行都不在壳里**（校验 / 落库 / 留痕 / 回滚全在后端）。
 * —— 这四页的来历与收口过程见《开发计划》§15 `TAIL-27`。 */

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

/* ⭐ **`**加粗**` 渲染成 `<b>`**（2026-09-26 用户报障「**落库结果可读性比较差**」里的一个具体毛病）：
   后端回执与区块说明里**本来就写着一堆 `**…**`**（= "这段最关键"的标记），此前一律 `esc` ⇒
   用户看到的是**满屏星号**（截图那句就是「导入完成：**按合同价匹配上并更新 5 条**」）。
   ⚠️ **先 `esc` 再替换**，⛔ 绝不反过来（反过来等于给自己开一个注入口子）。
   ⚠️ 只用于**说明文字**（标题 / 说明 / 一句话结果 / 指标名）；表格**单元格**里的仍是数据 ⇒ 只 `esc`。
   ⭐ 2026-09-28（`TAIL-105` · 守则 §3.1）：**① 步那五句「域自报文案」原先漏在外面**（`note` /
      `keep_note` / `memory` / `rule_note` / `field_list_hint` —— 五处都只 `esc`）⇒
      那一屏给用户看的是**满屏星号**。现已一并改走本函数（⛔ 别再退回 `esc`）。 */
const lgMd = s => esc(String(s == null ? '' : s)).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>');
/* 回执条：`kind` = ok / wn / err（与后端 `message` 的中文原因**原样**呈现，⛔ 不吞）。 */
const lgNotice = s => (s.msg
  ? `<div class="tip ${s.kind === 'err' ? 'dg' : (s.kind === 'wn' ? 'wn' : 'ok')}">${lgMd(s.msg)}</div>` : '');
/* 步骤条：`at` = 当前第几步（**从 0 起**；通用导入面是**四步** ⇒ 0..3）。
   ⚠️ 2026-09-29（`A8` 逐页）**订正过期注释**：本条原写「**三步**条：`at` = 当前第几步（0/1/2）」，
      而 `IMP_STEPS` 早就是四项 ⇒ 注释在说一件不存在的事。⛔ 本函数**不是"只能画三步"**：
      步数与文案一律由调用方给（本件三个导入页共用）。
   ⭐ 同批挂上判据 `001-63`（`tests/test_imp_shell.py`）：**同屏只许一条步骤条** ＋ 当前步 `on` / 走过 `dn`
      —— 这条当年是用户按截图报的「**两条一模一样的四步条**」，此前**没有任何机器判据**。 */
const lgSteps = (steps, at) => `<div class="steps">` + steps.map((t, i) =>
  `<div class="st ${i === at ? 'on' : (i < at ? 'dn' : '')}">${esc(t)}</div>`).join('') + `</div>`;
/* 选文件那一行（三个导入页同款）——⚠️ **文件对象存状态里**（`render()` 会重建 input ⇒ 只靠 input 会丢）；
   ⇒ 「解析」按钮的可用性看**状态里那个文件**，⛔ 不看 input 的 `files`（那正是"选完文件按钮还是灰的"的来源）。 */
function lgPick(id, pickAct, parseAct, file, tip) {
  return `${FBAR({cls:'pane',body:``
    + `<div class="fi"><label>选文件（.xlsx）</label>`
    + `<input class="inp" type="file" id="${esc(id)}" accept=".xlsx" data-act="${esc(pickAct)}"></div>`
    + `<div class="fi"><label>&nbsp;</label>`
    + `<button class="btn pri" data-act="${esc(parseAct)}"${file ? '' : ' disabled'} title="${file?'解析这个文件（一个字节都不写库）':'还没选文件 —— 选完才能解析'}">解析并预览（不写库）</button></div>`
    + `<div class="fi"><label>&nbsp;</label><span class="mut sm">${file
      ? `已选：<b class="fc">${esc(file.name)}</b>（${Math.max(1, Math.round(file.size / 1024))} KB）`
      : esc(tip || '只读第一个工作表')}</span></div>`})}`;
}
/* 空态行（跨列数由调用方给）。
   ⭐ 2026-09-27（`TAIL-117` 批次 6）：**本件已改成"薄转发"** —— 空态行真正的主人 =
   `index.html` 的 `EMPTYROW`（那里统一管"为什么空 ＋ 下一步"）。
   ⚠️ 本函数只剩通用导入面在用（`lgBlocks` / `V.set` 等），它的文案由**域**给、且只有一句
      ⇒ 只做 `esc` 后转发，⛔ **别在两处各写一套空态标记**（两套必然漂）。 */
const lgEmpty = (cols, text) => EMPTYROW(cols, esc(text));
/* 域补充区块（`TAIL-75` `B5b` 第三步：**通用面给域留的口子** —— 域侧补"只有它自己算得出"的几块，
   如历史付款流水的「未匹配清单」与「核对报告」）。
   ⚠️ 一律**通用渲染**（题 ＋ 说明 ＋ 表）：⛔ 壳里**不许出现任何域名 / 列名** ——
      那全由**后端**（域钩子 `Hooks.preview` / `commit` 的回执）给 ⇒ 加一个域不必改本页。 */
function lgBlocks(blocks) {
  return (blocks || []).map(b => `<div style="margin-top:calc(12px * var(--fscale))">
    <h4 style="font-size:calc(12.5px * var(--fscale));margin:0 0 calc(5px * var(--fscale))">${lgMd(b.title || '')}</h4>
    ${b.note ? `<p class="mut sm" style="margin:0 0 calc(5px * var(--fscale))">${lgMd(b.note)}</p>` : ''}
    <div class="tw" style="max-height:260px;min-height:0">${TBL({head:(b.columns || []).map(c => `<th>${esc(c)}</th>`).join(''),
      rows:(b.rows || []).length
        ? b.rows.map(r => `<tr>${(r || []).map(c =>
            `<td>${esc(c == null ? '' : String(c))}</td>`).join('')}</tr>`)
        : [],
      empty:lgEmpty((b.columns || []).length || 1, b.empty || '（无）')})}</div></div>`).join('');
}

/* ============================================================ `V.set` —— 系统设置（§7.8） */

V.set = () => {
  /* ⭐⭐ 2026-09-27（`TAIL-127` · 用户走查裁定 **B**）—— 本页**不再摆连接参数的输入框**。
     用户原话：「连接参数这个板块说实话可以删掉，因为**不可能有变动**；那系统设置就只剩下主题色了」。
     ⇒ 三个参数各自搬回**它起作用的地方**（守则 §5.8「**换地方，不是删掉**」）：
       · `i8 服务地址`          → 「**i8 接入层**」页卡头的「i8 连接设置」按钮（`ACT.i8SetOpen`）
       · 两个**打印版式 ID**    → 「**付款通知书**」页「打印机设置」弹窗里（打印相关的都在那儿）
     ⚠️ **能力一处没丢**：取值仍走 `GET/POST /api/m14/settings`（落库 ＋ 格式校验 ＋ **逐项留痕** ＋ 清缓存）。
     ⚠️ 那两个入口渲染时**照旧用后端给的 `it.label` / `it.hint` / `it.stored` / `it.effective`** ——
        ⛔ 别在这儿另写一份文案（反直觉提示「配反了会印错版式」必须原样来自后端，`001-04` 钉着它）。
     ⚠️ **留痕卡留着**（"这些参数被谁改成什么"的账），卡头写清现在去哪儿改。 */
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
      <p class="mut sm" style="margin:0 0 calc(9px * var(--fscale))">点一张卡<b>立即生效</b> —— ⛔ 不刷新页面、也不会把你踢回别的页。
        每张卡用它<b>自己那套的底色与文字色</b>画的 ⇒ 明暗差异一眼可见；左边<b>圆点 = 该套主色</b>，旁边是色值。</p>
      <div class="thgrid">${THEME_PALETTE.map(pcard).join('')
        || '<span class="mut">（取不到主题清单 —— 见顶部横幅）</span>'}</div>
      <p class="mut sm" style="margin-top:calc(9px * var(--fscale))">当前：<b class="fc">${esc(CUR_THEME) || '默认'}</b>　·　
        ⚠️ 主题<b>只管屏幕</b>：打印件与导出的 Excel 颜色与它无关（§7.7）。</p>
    </div></div>`;
  /* ⭐⭐ `TAIL-129`（2026-09-27 用户裁定走**方案 B**）：「**界面大小**」卡 —— 与主题卡**同款**
     （按<b>你的账号</b>保存 · 点了**即时生效不刷新**）。
     ⚠️ **档位清单来自后端**（`reloadTheme` 填的 `UI_SCALES` ⇒ 真源 = `domain.UI_SCALES`），
        壳⛔ 不写死"哪几档 / 几倍"（写死就是第二份真源：加一档得改两处）。
     ⚠️ 键走 `data-key`（⛔ 不读 `value` —— `<button>` 也有 `value`（默认空串），
        那正是主题当年"换了没反应"的坑）。 */
  const scard = s => {
    const on = s.key === CUR_UI_SCALE;
    return `<button class="btn ${on ? 'pri' : 'gost'}" data-act="uiScaleSet" data-key="${esc(s.key)}"
        title="${esc(s.label)}（${esc(s.css)} 倍）—— 点了即时生效">${on ? '✓ ' : ''}${esc(s.label)}</button>`;
  };
  const curLabel = (UI_SCALES.find(x => x.key === CUR_UI_SCALE) || {}).label || '标准';
  const scaleCard = `<div class="card"><h4>界面大小
    <span class="sp mut sm">按<b>你的账号</b>保存 · 只改你自己看到的样子</span></h4>
    <div class="bd">
      <p class="mut sm" style="margin:0 0 calc(9px * var(--fscale))"><b>字小看不清就点大一档</b> —— 点了<b>立即生效</b>：
        ⛔ 不刷新页面、也不会把你踢回别的页。只影响<b>屏幕上的字号与行距（表格框会跟着变宽）</b>；
        ⚠️ <b>打印件与导出的 Excel 不受影响</b>。</p>
      <div style="display:flex;gap:calc(8px * var(--fscale));flex-wrap:wrap">
        ${UI_SCALES.map(scard).join('')
          || '<span class="mut">（取不到档位清单 —— 见顶部横幅）</span>'}
      </div>
      <p class="mut sm" style="margin-top:calc(9px * var(--fscale))">当前：<b class="fc">${esc(curLabel)}</b>　·　
        想连按钮一起整屏放大，也可以用浏览器的 <span class="fc">Ctrl</span> ＋ 滚轮（浏览器会按站点记住）。</p>
    </div></div>`;
  return `<details class="tip"><summary>口径说明（§7.8：这些都是<b>会变、且变的时候不该改文件重启</b>的参数）</summary>
      <ul style="margin:calc(6px * var(--fscale)) 0 0 calc(18px * var(--fscale));line-height:1.8">${tips}</ul></details>
    ${lgNotice(SET)}${errs}
    <div class="card"><h4>i8 地址与打印版式<span class="sp mut sm">搬到「用它的那一页」了</span></h4>
      <div class="bd"><p class="mut sm" style="margin:0 0 calc(6px * var(--fscale))">这些<b>连接参数</b>（i8 地址 · 两个打印版式 ID）
        <b>配一次能用很久</b> ⇒ 不再占这一页，改到<b>用它的地方</b>去改（改动一样<b>留痕</b>，见下方记录）：</p>
        <ul class="sm" style="margin:0 0 0 calc(18px * var(--fscale));line-height:1.9">
          <li><b>i8 服务地址</b> → 「<b>i8 接入层</b>」页卡头的「i8 连接设置」</li>
          <li><b>材料类 / 外租机械类打印版式 ID</b> → 「<b>付款通知书</b>」页的「打印机设置」</li>
        </ul></div></div>
    <div class="card"><h4>变更留痕<span class="sp mut sm">最近 ${(SET.logs || []).length} 条</span></h4>
      <div class="bd np"><div class="tw" style="max-height:320px;min-height:0">${TBL({head:'<th>时间</th><th>设置项</th><th>改前</th><th>改后</th><th>改动人</th>',
        rows:[rows || lgEmpty(5, '还没有改动记录')]})}</div></div></div>
    ${themeCard}
    ${scaleCard}`;
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

/* ============================================================ 动作（**一律追加**到既有 `ACT`） */

/* ⭐ `TAIL-127`（2026-09-27 · 用户裁定 B）：**连接参数的唯一保存出口** ——
   `i8 地址`（住在 `m02` 的「i8 连接设置」弹窗）与**两个打印版式 ID**（住在 `m03` 的「打印机设置」弹窗）
   都走它。⚠️ **只传传进来的 key**（判据 `001-05` 钉着"不许顺带把别的项改掉/清空"）——
   所以调用方必须**把自己那几个键凑成一个对象**再进来，⛔ 别在这里"顺便读一遍全页输入框"
   （那正是旧 `ACT.setSave` 的写法：它一次交全部键，只在那张"整页就是那几个框"的页面上才安全）。
   ⚠️ 校验 / 落库 / 留痕 / 清缓存**全在后端**（`settings_api`）—— 壳里⛔ 不另写一份校验。
   ⚠️⚠️ **失败不抛异常、回 `{ok:false, errors:[…]}`** —— 这是仓里的既定形状（与后端"恒 200 ＋ `ok` 标志"
      同构），也是判据 `test_ux_errors`「**造错的口只有一个**（`api.js` 那个人话出口）」要求的：
      在别处造错对象 ⇒ 迟早有一处把状态码 / 接口地址当消息抛给用户。⛔ 别改成抛异常。
      ⚠️ 顺带记一笔：**那条判据扫的是全文、连注释也算** —— 我第一次写这行注释时把那个构造式的字面量
         抄了进去，当场被判红（本仓同类坑已记过：注释里别写"示例代码"）。 */
async function m14Save(pairs) {
  const body = {};
  (pairs || []).forEach(([k, v]) => { body[k] = v; });
  let r = null;
  try { r = await API.m14SettingsSave(body); }
  catch (e) { return { ok: false, errors: [`没连上服务器或被拦断：${String((e && e.message) || e)}`] }; }
  if (r && r.ok === false) return { ok: false, errors: (r.errors || ['后端未返回原因']) };
  if (r && r.items) SET.items = r.items;        /* 就地刷新（留痕卡与下次打开弹窗都看得到新值） */
  if (r && r.logs) SET.logs = r.logs;
  return { ok: true, message: (r && r.message) || '已保存' };
}

/* ⭐ 「i8 连接设置」（`TAIL-127`）：入口在 **`i8 接入层`页卡头**（`BIND.m02` 注入，⛔ 不动切片）。
   ⚠️ 渲染**照旧用后端给的那五个字段**（`label` / `hint` / `stored` / `env` / `effective`）——
      判据 `ACC-CFG-SETUP-001/001-01` 的"壳确实照着这份数据渲染"就是靠它们钉的；
      而 `001-04` 的反直觉提示也要求壳渲染 `it.hint`（⛔ 别在壳里另写文案）。 */
async function i8SetOpen() {
  let items = [];
  try { items = ((await API.m14Settings()) || {}).items || []; }
  catch (e) { return toast(`⚠️ 读不到当前连接参数：${esc(String((e && e.message) || e))}`, 8000); }
  const it = items.find(x => x.key === 'i8_base_url');
  if (!it) return toast('后端没给「i8 服务地址」这一项 —— 见顶部横幅', 8000);
  const src = it.stored ? '<span class="tag t-pri">本处所设</span>' : '<span class="tag t-in">.env</span>';
  const meta = it.stored
    ? `当前生效：<b class="fc">${esc(it.effective)}</b>（本处所设；清空输入框并保存即回落到 <code>.env</code>）`
    : (it.env ? `未设置过 ⇒ 现在用 <code>.env</code> 的值：<b class="fc">${esc(it.env)}</b>`
      : '未设置过，且 <code>.env</code> 也是空的');
  modal({
    title: 'i8 连接设置',
    body: `<div class="tip" style="margin:0 0 calc(10px * var(--fscale))">i8 装在哪台机器上 —— <b>保存后即时生效</b>
        （后端清缓存，无需重启服务）。⚠️ <b>i8 的账号密码不在这里</b>（那是每人一份，在「用户管理」页）。</div>
      <div class="fld"><label>${esc(it.label)} ${src}</label>
        <input class="inp" id="m02I8Url" style="width:100%" value="${esc(it.stored)}"
          placeholder="${esc(it.env)}" autocomplete="off">
        <div class="hint">${em(it.hint)}</div>
        <div class="hint mut">${meta}</div></div>`,
    footer: `<button class="btn" data-act="closeModal">取消</button>
      <button class="btn pri" data-act="i8SetSave">保存</button>`,
  });
}

ACT.i8SetOpen = () => i8SetOpen();
ACT.i8SetSave = async () => {
  const v = ((($('#m02I8Url') || {}).value) || '').trim();
  const got = await m14Save([['i8_base_url', v]]);
  if (!got.ok) {
    return toast(`<b>没能保存</b>：${got.errors.map(esc).join('<br>')}`, 9500);
  }
  closeModal();
  return toast(`i8 连接设置已保存${v ? `：<b>${esc(v)}</b>` : '（已清空 ⇒ 回落到 <code>.env</code>）'}`
    + '<br>改动已留痕（系统设置页的「变更留痕」看得到）', 9000);
};
/* ⛔ 付款导入的四个动作（`imp05Pick/Parse/Ok/Rollback`）**已随旧页下架删除**
   （`TAIL-75` `B5b` 第三步 · 2026-09-23 用户裁定 `B`）—— 那条路现在是通用面的
   `impParse / impPreview / impCommit / impRollback`（见下）。
   ⛔ `imp08*` 三个动作已随「库存单据手动导入」删除（2026-09-22 用户裁定；`T8` 守卫）。
   ⛔ `m06imp` 的 `imp06*` 也已删（`B5c`）。 */

/* ⚠️ 历史上这里有一条规矩：「**挂在表单元素上的动作必须登记**」—— 漏了 ⇒ `change` 被**静默丢弃**
   （症状：选完文件"解析"按钮永远是灰的 / 换项目没反应）。本仓因此踩过三次
   （`jcAmt` / `jcPartySet` / `themeSet`）。
   ⭐ `#2`（2026-09-26）：**那份名单（当年叫 `CHG`）已整份拆掉** —— `change` 由委托层**直呼 `ACT[a]`**
      ⇒ 这类"漏登记 ⇒ 静默丢弃"**在结构上不再可能**，⛔ 也不必（且无处）再登记。
   ⚠️ `impPj` 那一项随之下线（2026-09-26）：它原来是挂在 `<select data-act="impPj">` 上的；
      现在「项目」换成**共用面板 `projPanel`（单选）** ⇒ 面板内的 `radio` 挂 `impPjPick`、
      展开/收起是 `impPjToggle`（`<button>` / `radio`，走 **click 委托**）。 */

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
            ym: '', pjDisp: {}, cutoffs: {}, hasCut: false, hasYm: false, hasPj: false,
            /* ⭐ `busy` = **正在落库**（`TAIL-108`）：提交期间把 ④ 置灰 ＋ 挡住重入
               —— 连点两次会发两次请求，而默认批号到**秒** ⇒ 第二次撞批号唯一约束（`IntegrityError` 天书）。 */
            busy: false,
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
  IMP.org = []; IMP.wrap = ''; IMP.cutoff = ''; IMP.ym = ''; IMP.cutoffs = {};
  pjClose('impPj'); IMP.pjDisp = {}; IMP.hasCut = false; IMP.hasYm = false; IMP.hasPj = false;
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
  /* ⚠️ 2026-09-29（用户真机报障后修）：**取不到要说出来** —— 后端那条 `/options` 自己的口径就是
     「取不到也要让人**看见原因**，⛔ 不静默给空」（`import_kit/api.py` 的 `api_options`）。
     ⚠️ 原先这里把 `ok:false` 静默当作"这个域没有上下文" ⇒ 后果不是"少一格控件"，
        而是**项目闸门整条失灵**（`hasPj` 取不到 ⇒ `needPj = false` ⇒ ④ 亮着不可挡 ✗✗）。 */
  const ok = !!(d && d.ok !== false);
  const ctx = ok ? d : {};
  if (!ok) {
    IMP.msg = (d && d.message) || '取本域的上下文失败（候选项目 / 截止月可能不是最新的）—— 请重试或刷新';
    IMP.kind = 'wn';
  }
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
  /* ⛔⛔ **不预选项目**（2026-09-26 用户裁定「按推荐做」）：原先是
     `ctx.warehouse || ctx.project_key || IMP.org[0]` ⇒ **系统替用户挑好了候选里的第一个**，
     用户没留意就直接点「④ 确认落库」—— 而 `m06` 那一路是**直接写进该项目的"历史段"、且不报错**。
     《前端设计守则》§4「默认值不诱导 …… 默认项应是**最安全 / 最中性**的那一个」⇒ 最中性 = **空**
     （没选就落不了库，见 `ctxBar` 的 `needPj` 与 `ACT.impCommit` 的兜底拦住）。
     ⚠️ 域给的那个 `warehouse` 是"**读数据**时的当前项目"（= 候选人里的第一个），**不是落库默认值**。 */
  IMP.wrap = '';
  /* ⭐ **哪个域要哪些上下文，由域自己说**（键在不在），壳按这个渲染控件 —— 这就是"加一个域不改壳"：
       `projects` ⇒ 项目选择 · `year_month` ⇒ 本批归属年月（`m04`）· `cutoff_ym` ⇒ 截止核算月（`m06`） */
  /* ⭐⭐ **这个域要不要选项目 —— 由域自己说**（`projects` 键在不在），⛔ **不看"候选列表空不空"**。
     ⚠️⚠️ 2026-09-29 修（**用户真机报障**：「④ 确认落库**是亮的**、点下去**没反应**；刷新后才是灰的、
        而且有提示了」）—— 现象就是这条判据自己露的破绽：**两种状态都存在** ⇒ 不是"设计如此"，
        是状态**没算对**。原判据 `needPj = IMP.org.length > 0 && !IMP.wrap` 把"要不要选项目"
        **绑在候选列表上** ⇒ **候选为空**（库里还没有项目档案 ⇒ `m06_proc` 的 `options` 回 `projects: []`）
        时 `needPj = false`：④ 亮着 ＋ 同一条错写法的兜底也放行 ⇒ 请求照发 ⇒ **静默失败** ✗✗。
     ⭐ 改法：候选有没有**不改变"这个域要不要项目"** —— 空候选是**另一种状态**，只换**提示**
       （② 那条真出路：同步 i8「常用项目列表」），⛔ 不换"拦不拦"。 ⇒ 一条判据同时管住
       「档案还没建」与「建了但还没选」两种情形。判据 = `tests/test_imp_shell.py`。 */
  IMP.hasPj = Object.prototype.hasOwnProperty.call(ctx, 'projects');
  IMP.hasYm = Object.prototype.hasOwnProperty.call(ctx, 'year_month');
  IMP.hasCut = Object.prototype.hasOwnProperty.call(ctx, 'cutoff_ym');
  IMP.ym = IMP.hasYm ? String(ctx.year_month || '') : '';
  /* ⭐⭐ **截止核算月 = 每个项目一张表**（2026-09-26 修真缺陷）：它本身**按项目存**
     （`repository.load_cutoff`），而落库会把界面上这个值**写进所选项目**；此前只在**进域那一刻**
     取一次（取的是"候选人里的第一个"）⇒ **换项目后那个框不跟着换 ⇒ A 项目的分界被写给 B、且不报错**。
     ⇒ 现在只认域给的 `cutoffs`（`{仓库名: 截止月}`），选中项目后由 `ACT.impPjPick` 填。 */
  IMP.cutoffs = (ctx.cutoffs && typeof ctx.cutoffs === 'object') ? ctx.cutoffs : {};
  /* ⚠️ **不预填** `ctx.cutoff_ym` —— 那是"第一个项目"的那一格，与上面同一个坑（它只是那一项的值）。 */
  IMP.cutoff = '';
}

/* ⭐ **域上下文包**：**预览与落库共用同一份**（2026-09-26）——
   ⛔ 别在两处各拼一遍：预览若少了 `project_key`，集采 ③ 那条「**能配上几条**」就成了空话
   （而落库照旧用另一份 ⇒ 两边悄悄走形）。⚠️ 多给的键对域只是**字典里的空转**（各域只读它认识的）。 */
function impOptions() {
  const cut = document.querySelector('#impCut');
  const ym = document.querySelector('#impYm');
  return {warehouse: IMP.wrap, project_key: IMP.wrap,
          cutoff_ym: (cut && cut.value) || '', year_month: (ym && ym.value) || bjMonth()};
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
  /* ⭐⭐ **「候选键 → 显示名」的唯一出口**（2026-09-26 用户报障：「**候选和选择后显示的不一样**」）。
     此前**三处各自算**：① 下拉按钮 `IMP.pjDisp[键] || 键`（域给的 display，域没给就退化成**仓库名**）·
     ③ 只读回显同款 · 候选面板却走 `impPjMeta`（**档案展示名**）⇒ 同一个键能显示**两个名字**
     （实测：按钮「内蒙石灰窑项目」＝仓库名，候选里是「内蒙宜化项目」＝展示名 —— 用户就是拿这个报的障）。
     ⇒ 现在三处**一律**走 `impPjLabel`（＝ `impPjMeta(v).nm` —— 与面板**同一个函数**，同名是构造保证的）。
     ⛔ 别在这三处再各写一遍取值：那是"同一个事实有两个主人"，必然再次走形。 */
  const impPjLabel = v => impPjMeta(v).nm;
  /* 「项目」= **共用面板**（单选）—— 与 MOD-09 / 新增合同 / 台账导出（`ledPjPanel`）同款。
     ⚠️ 它渲染在本卡的 `fbar` 里、**不在 `.tw`（滚动容器）内** ⇒ 浮层不会被裁（同 `ledExpStrip` 的处置）。 */
  const impPjPanel = () => projPanel({list: () => IMP.org, selected: () => [IMP.wrap],
                                      pickAct: 'impPjPick', meta: impPjMeta, single: true});
  /* ⭐⭐ **「范围」栏 —— 画在 ①「选域与文件」，⛔ 不再画在 ③**（2026-09-26 用户裁定：
     「**能否在"选文件"时就选定项目**」）。此前后它在 ③ 预览卡里 ⇒ 用户**走到最后才知道要选项目**，
     而集采域那一步**还什么都看不出来**（对号在 ④ 才做）⇒ 顺序定为：
     **选域 ⇒ 定范围 ⇒ 选文件 ⇒ 列映射 ⇒ 预览 ⇒ 落库**。
     ⛔ 壳里**不看域号**：哪个域要哪些控件，由域给的**键**说 ——
       `projects` ⇒ 「这批数据进哪个项目」（**共用面板 · 单选**，⛔ 全站不得自造项目控件）·
       `year_month` ⇒ 本批归属年月（`m04`，§4.3.3）· `cutoff_ym` ⇒ 截止核算月（`m06`，§5.2.5）。
     ⚠️ 2026-09-26 所修（用户报障）：更早这里是 `IMP.domain === 'm04_plan' ? 年月 : (项目 ＋ 截止核算月)`
        —— 两处毛病：①「项目」是**自造的原生下拉**；②**截止核算月被画给了所有域**，而集采/付款计划的
        落库根本不读它（`ACT.impCommit` 给的上下文包里它只是空转）⇒ 用户填了**不生效**（死控件）。 */
  const ctxBar = (IMP.hasPj || IMP.hasYm || IMP.hasCut)
    ? `${FBAR({cls:'pane',body:`
      ${IMP.hasPj ? (IMP.org.length ? `<div class="fi pjwrap" style="position:relative">
        <label>这批数据进哪个项目（键 = 仓库名，§2.7.4）</label>
        ${PJB({act:'impPjToggle',w:186,label:`${esc(IMP.wrap ? impPjLabel(IMP.wrap) : '请选择项目')}`,title:`${IMP.wrap ? esc('仓库名（§2.7.4）：' + IMP.wrap) : ''}`})}
        ${pjIsOpen('impPj') ? impPjPanel() : ''}</div>`
      /* ⛔ **候选为空 ≠ 这个域不要项目**（2026-09-29 修）：仍要把这一格画出来 —— ① 让人看见
         "这一步有项目这一环"（⛔ 不静默少一格，否则用户以为不用选）；② 给**真出路**
         （去 `m02`「i8 接入层」同步 i8「常用项目列表」⇒ 按 phid 幂等建档）；③ 按钮**置灰**，
         ⛔ 不做成"可点的空面板"（点开是空的 = 假控件）。 */
      : `<div class="fi pjwrap" style="position:relative">
        <label>这批数据进哪个项目（键 = 仓库名，§2.7.4）</label>
        <button class="btn" disabled style="min-width:186px" title="库里还没有项目档案 —— 先去「i8 接入层」同步「常用项目列表」">（库里还没有项目档案）</button>
        <span class="mut sm">⚠️ <b>这个域要先有项目档案</b>：去 <b>「i8 接入层」</b>页同步
          <b>「常用项目列表」</b>（按 phid 幂等建档；「一个全名挂多个仓库」的进 <b>「项目档案」</b>页的
          「待人工建档」卡处理）—— 建完<b>回本页刷新</b>，候选就在了。</span></div>`) : ''}
      ${IMP.hasYm ? `<div class="fi"><label>本批归属年月（§4.3.3 —— 这批数据全归该月）</label>
        <input class="inp" id="impYm" value="${esc(IMP.ym || bjMonth())}" placeholder="2026-09"></div>` : ''}
      ${IMP.hasCut ? `<div class="fi"><label>截止核算月（＝历史段 / 正式段的分界月）</label>
        <input class="inp" id="impCut" value="${esc(IMP.cutoff)}" placeholder="2026-08"
               title="格式 YYYY-MM（如 2026-08）">
        <span class="mut sm">格式 <b>YYYY-MM</b>（如 <code>2026-08</code>；写成别的样子会<b>被拒</b>）。
          这个月 <b>及以前</b>算历史段（用这份表，不再从 i8 取）；<b>之后</b>才走 i8 抓取。
          留空 = 取本批里最大的核算月。换项目会自动换成<b>那个项目</b>已设的值。</span></div>` : ''}
      `})}` : '';
  /* ⛔ **该域要选项目、而还没选** ⇒ ④ 置灰（见下面 `prevCard` 里那个按钮）—— 「默认值不诱导」的落点：
     系统不再替用户挑第一个项目（`IMP.wrap` 初值 = 空），但也不能让人**点下去才发现没选**。 */
  const needPj = IMP.hasPj && !IMP.wrap;
  /* **③ 的只读回显**：范围栏在 ①，而 ④ 按钮在 ③ ⇒ 中间隔着两屏 ⇒ 点落库前必须能**复核一眼**
     （守则 §4 防误导：宁可少给信息，也不能让用户不知道自己正要写哪儿）。⛔ 这里**不给控件**（改在 ①）。 */
  const scopeEcho = (IMP.hasPj || IMP.hasYm || IMP.hasCut)
    ? `<div class="tip">本批数据将写入：${
        [
          IMP.hasPj ? `项目 <b>${esc(IMP.wrap ? impPjLabel(IMP.wrap)
            : (IMP.org.length ? '（还没选）' : '（库里还没有项目档案 —— 落不了库）'))}</b>`
            + (IMP.wrap ? `<span class="mut sm">（仓库名 ${esc(IMP.wrap)}）</span>` : '') : '',
          IMP.hasYm ? `归属年月 <b>${esc(IMP.ym || bjMonth())}</b>` : '',
          IMP.hasCut ? `截止核算月 <b>${esc(IMP.cutoff || '（留空 ⇒ 取本批最大月）')}</b>`
            + `<span class="mut sm">（该月及以前按这份表，之后走 i8）</span>` : '',
        ].filter(Boolean).join(' · ')}<span class="mut sm">　要改请回第 ① 步（「导入哪个域」下面那一栏）</span></div>`
    : '';
  /* ⭐ 2026-09-27（用户裁定 `A` · 守则 §4.5）：① 步里那三句域自报文案（`note` / `keep_note` / `memory`）
     **一律用普通 `tip`**。原先由**壳替域挑颜色**（`note` 普通 · `keep_note` 警示黄 · `memory` 成功绿）
     ⇒ 同一个域的三句话长出三种颜色，而壳**根本不知道域写了什么** ⇒ 与"颜色只承担语义"相反。
     ⛔ 别再按字段名挑颜色；将来真要分语气走 `B` 案（域自报 `note_kind`）。判据 = `tests/test_ux_colors.py`。 */
  const head = `<div class="card"><h4>数据导入<span class="sp"><span class="mut sm">一次导一个域的一种表 ·
    落库前一个字节都不写库</span></span></h4><div class="bd">${lgSteps(IMP_STEPS, IMP.step)}
    ${FBAR({cls:'pane',body:`
      <div class="fi"><label>导入哪个域</label>
        <select class="inp" data-act="impDomain">${doms || '<option value="">（后端还没挂任何域）</option>'}</select></div>
      <div class="fi"><label>&nbsp;</label><span class="mut sm">${sch ? esc(sch.title) : '—'}</span></div>`})}
    ${ctxBar}
    ${sch && sch.note ? `<div class="tip">${lgMd(sch.note)}</div>` : ''}
    ${sch && sch.keep_note ? `<div class="tip">${lgMd(sch.keep_note)}</div>` : ''}
    ${lgPick('iimp', 'impPick', 'impParse', IMP.file, '解析时自动挑「认得出表头」的那张工作表')}
    ${IMP.memory ? `<div class="tip">${lgMd(IMP.memory)}</div>` : ''}
  </div></div>`;

  /* ---- ② 列映射 ---- */
  /* ⭐⭐ **信息与版式（**用户 2026-09-26「拷问」后定稿** —— 前四版都被否，这条是用户逐条选的）**：
     原话：「**全部并排，宽了就左右滚动**」·「每个源列要看：**源列名**、**目标字段**、
     **导入后会怎样：会覆盖 / 只用于匹配 / 不写库**」·「**就用原生下拉**」·
     「**不写库的这列，不要给目标字段了，就提示不写库即可**」·
     「**要：顶部一句话说清 ＋ 每列标后果**」。
     ⇒ 所以这里：⛔ 不折叠、⛔ 不卡片、⛔ 不分页；⛔ 不显示样本/画像（用户没要）；
       ⛔ 不显示置信度数字与算法名（它们不是"用户要的信息"）。
     ⚠️ 判据与真机证据认 `<select data-act="impMap" data-src="…">`，⛔ 不许改这两个属性。 */
  let mapCard = '';
  if (IMP.cols.length) {
    const optsOf = (c) => {
      const cur = IMP.mapping[c.src] || '';
      const fields = ((sch && sch.fields) || []).map(f =>
        `<option value="${esc(f.label)}"${f.label === cur ? ' selected' : ''}>${esc(f.label)}${f.required ? '（必填）' : ''}</option>`).join('');
      return `<option value=""${cur ? '' : ' selected'}>${esc(IMP_IGNORE)}</option>` + fields;
    };
    /* ⭐⭐ 2026-09-26（用户裁定）：屏上只留**三个短词** —— 写台账 / 当钥匙 / 不参与
       （原话：「**写台账和进子表为一个意思，合并为写台账**」）；**完整说明一律下沉到悬停**，
       屏上不再出现长句（守则 §5.9：同屏做优先级 —— 用户当场说"那一行可读性太差"）。
       ⚠️ 随用户改下拉**实时变**：同一列选不同字段 ⇒ 去向与说明都跟着变。
       ⚠️ 判据与真机认 `data-act="impMap"` ⇒ ⛔ 别动那个属性；去向另起一行，⛔ 不塞进下拉那格。 */
    const impacts = {};                      /* 字段 → 完整说明（进悬停） */
    const kkinds = {};                       /* 字段 → 去向（写台账 / 当钥匙 / 不参与） */
    ((sch && sch.impacts) || []).forEach(x => { impacts[x.label] = x.what; kkinds[x.label] = x.kind || ''; });
    const kindOf = (c) => (c.ignored ? '不参与' : (kkinds[c.field] || ''));
    const whatOf = (c) => (c.ignored ? String(c.ignored) : (impacts[c.field] || ''));
    const tagOf = (k) => (k === '写台账' ? '<span class="tag t-wn">写台账</span>'
                        : k === '当钥匙' ? '<span class="tag t-in">当钥匙</span>'
                        : k === '不参与' ? '<span class="mut sm">不参与</span>' : '');
    const attrRow = (label, cellOf) =>
      `<tr><th style="text-align:left;white-space:nowrap;vertical-align:middle;min-width:92px" class="mut sm">${label}</th>`
      + IMP.cols.map(c => `<td>${cellOf(c)}</td>`).join('') + '</tr>';
    mapCard = `<div class="card" style="margin-top:calc(12px * var(--fscale))"><h4>列映射<span class="sp"><span class="mut sm">
      横看 = 你表里的每一列 · 系统只给建议，<b>选哪个由你定</b></span></span></h4>
      ${sch && sch.rule_note ? `<div class="tip" style="margin-bottom:calc(8px * var(--fscale))">${lgMd(sch.rule_note)}</div>` : ''}
      ${(sch && sch.impacts && sch.impacts.length) ? `<div class="sm mut" style="margin-bottom:calc(8px * var(--fscale))">
        <b>去向</b>：${tagOf('写台账')} 会盖掉台账里的值（<b>含往发票子表加一张票</b>）·
        ${tagOf('当钥匙')} 拿它去找那张合同（合同上的原值<b>不动</b>）·
        ${tagOf('不参与')} 导入不用它 —— 把鼠标停在格子上看完整说明</div>` : ''}
      <div class="tw">${TBL({cls:'sm',head:'<th style="min-width:92px"></th>'+IMP.cols.map(c => `<th style="vertical-align:bottom;min-width:136px">
        <div style="font-weight:600;white-space:normal">${esc(c.src)}</div></th>`).join(''),
      rows:[
        attrRow('导入到', c => {
          const k = kindOf(c);
          /* ⭐⭐ 2026-09-26 用户裁定：「**不参与的就不要给下拉选项了**」——
             导入既然不用它，给个"能点但点了没用"的下拉＝**误导**（守则 §4 相似元素不制造歧义 ·
             §5.5 不能点的要置灰或隐藏）⇒ 这一类（含"按口径不采"的列）**默认只显示去向标签**。
             ⭐ 同轮补的**退路**（用户选了 B 案）：标签旁边挂一个「改」——**点开才展开下拉**，
             这样"平时不误导"与"认错了还能纠"两头都占（用 `<details>` 实现 ⇒ ⛔ 不需要额外 JS 状态）。
             ⚠️ 要映射的列**必须照旧有** `data-act="impMap"`（判据与真机都认它）—— 这里的下拉也在，
             只是**折叠着**（`details` 收起来时不可见）。 */
          if (c.ignored || k === '不参与') {
            return `<details style="display:inline-block;max-width:100%">`
                 + `<summary class="sm" style="cursor:pointer" title="${esc(whatOf(c))}">`
                 + `<span class="mut">不参与</span> <span class="tag t-in">改</span></summary>`
                 + `<select class="inp" style="width:100%;margin-top:calc(4px * var(--fscale))" data-act="impMap"`
                 + ` data-src="${esc(c.src)}">${optsOf(c)}</select></details>`;
          }
          return `<select class="inp" style="width:100%" data-act="impMap" data-src="${esc(c.src)}">${optsOf(c)}</select>`;
        }),
        IMP.cols.some(c => !c.ignored && ['写台账', '当钥匙'].includes(kindOf(c)))
          ? attrRow('去向', c => {
              const k = kindOf(c);
              /* ⚠️「不参与」这一列**上面那格已经写着**它了 ⇒ 这行留空，⛔ 别重复（同一格两处"不参与"＝噪音） */
              return (c.ignored || !k || k === '不参与')
                ? '' : `<span title="${esc(whatOf(c))}">${tagOf(k)}</span>`;
            })
          : '' /* ⚠️ **一行"去向"都没内容 ⇒ 整行不画**（本域没这条信息，画个空行像坏了）*/
      ]})}</div>
      <div class="tip ${lack.length ? 'wn' : 'ok'}" style="margin-top:calc(10px * var(--fscale))">${lack.length
        ? `还差必填字段：<b>${esc(lack.join(' / '))}</b> —— 选好才能到下一步（⛔ 系统不替你填默认值）`
        : '必填都齐了，可以往下走'}</div>
      ${(() => {
        /* ⭐ ④ 「本系统要哪些列」—— **新增**（2026-09-26 用户报「缺贸易公司发票金额」）：
           ② 这一屏**只列"你表里有的源列"** ⇒ 表里没有的列**从不出现** ⇒ 会被读成"系统不支持它"。
           这一块把**域契约的全部字段**列齐（有 / 表里没有 ＋ 去向），并把域给的那句提醒**默认露出来**
           （用户裁定：缺列提醒⛔ **不能藏在折叠里** —— 藏了等于没提醒）。 */
        const fields = (sch && sch.fields) || [];
        if (!fields.length) return '';
        const has = (lb) => IMP.cols.some(c => c.field === lb);
        const rows = fields.map(f =>
          `<tr><td>${esc(f.label)}${f.required ? '<span class="mut sm">（必填）</span>' : ''}</td>`
          + `<td>${has(f.label) ? '有' : '<span class="mut">表里没有</span>'}</td>`
          + `<td>${tagOf(kkinds[f.label] || '')}</td></tr>`).join('');
        const miss = fields.filter(f => !has(f.label)).length;
        const hint = String((sch && sch.field_list_hint) || '');
        return `${hint ? `<div class="tip" style="margin-top:calc(10px * var(--fscale))">${lgMd(hint)}</div>` : ''}`
             + `<details style="margin-top:calc(8px * var(--fscale))"><summary class="mut sm" style="cursor:pointer">`
             + `本系统要哪些列（共 ${fields.length} 列 · 你表里缺 ${miss} 列，点开看）</summary>`
             + `<div class="tw" style="margin-top:calc(8px * var(--fscale))">${TBL({cls:'sm',head:'<th style="text-align:left">列名</th><th style="text-align:left">你表里</th><th style="text-align:left">去向</th>',
             rows:[rows]})}</div>`
             + '</details>';
      })()}
      <div style="margin-top:calc(10px * var(--fscale))">
        <button class="btn pri" data-act="impPreview"${lack.length ? ' disabled' : ''} title="${lack.length?'还缺必填项 / 列映射 —— 上面已列出缺什么':'生成预览（这一步一个字节都不写库）'}">③ 预览校验（不写库）</button>
        <button class="btn" data-act="impReset">重来</button></div></div>`;
  }

  /* ---- ③ 预览校验 ---- */
  let prevCard = '';
  if (IMP.preview) {
    const p = IMP.preview;
    const probs = (IMP.problems || []);
    /* ⚠️ 2026-09-26：**「范围」栏已整体挪到 ①（`ctxBar`）** —— 这一屏只留**只读回显**（`scopeEcho`），
       理由见 `V.imp` 里 `ctxBar` 那段（用户裁定"选文件时就选项目"）。⛔ 别把控件搬回来。 */
    /* ⚠️⚠️ 2026-09-26（用户报障：「导入晋江的过程资料时，**第 4 步显示的行不完整**」）——
       这一屏原先有两处**显示**毛病，报障的实质是它们叠在一起：
       ① **行号列被抠掉了**（`filter(k => k !== '_row')`）—— 而 ④ 落库报错写的是
          「**第 19 行**的核算月认不出…」⇒ 用户**在页面上根本找不到第 19 行**（连行号都没有可比）；
       ② 只画**前一打（12）行**却**一个字都不说**（后端其实给得更多）⇒ 看着像"系统只读到 12 行"。
       ⭐ 实测（晋江那份真文件）：数据在 Excel 的 r4~r32（29 行）＋ 尾部 r33/r34 合计 r35 说明，
          而用户看不到的正好就是出问题的 **r19/r20/r22**。
       ⇒ 现在：**行号列画出来**（= Excel 行号，与"第 N 行…"这类报错**同一个数**）＋
          **后端给多少行就画多少行** ＋ 写明「共几行 / 显示几行」。
       ⛔ 别再把 `_row` 抠掉、⛔ 也别再静默截断（那正是本条报障的来源）。 */
    const plist = (p.preview || []);
    const ptotal = Number(p.total == null ? plist.length : p.total);
    const pw = (p.writable == null ? null : Number(p.writable));      /* 域没给 ⇒ 不显示"能写入几行" */
    /* ⭐⭐ 2026-09-26（用户报障 · 原话：「**这些不会落库的行，要在行上直接标**，比如给一个浅色底，
       或者其他明确提示，这才叫好的前端设计，而不是还要**抬头去看文字说明**」—— 通用导入页都这么做）：
       域自报 `skipped` = `[{row: Excel 行号, why: 人话原因}]` ⇒ **标记落在行上**（三件事一起给）：
         · 整行浅底 ＋ 左侧警示竖条（`.skiprow`）；
         · **行号格上一枚「不写入」标签** ＋ 整行 `title` 写原因（悬停即见）；
         · 表格上方一枚**图例**（看表的人一眼知道浅底是什么意思）。
       ⇒ 用户不用再去读卡片底下那段话、也不用自己把"有 7 行"对上具体是哪几行。
       ⚠️ 通用面**不猜**哪几行写不进去：域给 `skipped` 就按行号标；**没给就只是不标**（照实）
          —— ⛔ 绝不拿 `total - writable` 反推"大概是最后几行"（那是"看起来对"的猜法，守则 §4.2 状态必须真实）。 */
    /* ⭐⭐ 2026-09-27（用户报障 · 原话：「**请将所有不写入输出的行也进行标注**」· 他截图里红框的是
       第 33 行「小计」/ 第 34 行「合计」）：域自报的 `skipped` 里**两类都要标**，而且**必须一眼分得开**
       （守则 §2.8：**要你处理的** vs **本来就跳过的**）——
         · `kind="bad"`（缺省）⇒ **要你处理**：浅底 ＋ 左侧警示竖条 ＋ 行号旁「**不写入**」（守则 §2.7）；
         · `kind="skip"` ⇒ **本来就跳过**（合计/小计 · 说明 · 空行）：灰底、**没有**竖条 ＋ 行号旁「**不导入**」。
       ⛔ 两类混成一种颜色/一个词，用户会以为"合计行也要我去改"（那正是"看起来有毛病"的误读）。
       ⚠️ 缺 `kind` 时按 `bad` 走（**保守**：宁可多提醒一句"要处理"，也别把该处理的悄悄归成"不用管"）。 */
    const skipOf = {};
    (p.skipped || []).forEach(x => {
      skipOf[String(x.row)] = {why: String(x.why || ''), kind: String(x.kind || 'bad')};
    });
    let nskip = 0, nplain = 0;
    Object.keys(skipOf).forEach(k => { if (skipOf[k].kind === 'skip') nplain += 1; else nskip += 1; });
    const prows = plist.map(r => {
      const hit = skipOf[String(r._row)] || null;
      const plain = !!hit && hit.kind === 'skip';
      const cell = (v, tail) => `<td class="now">${esc(String(v == null ? '' : v))}${tail || ''}</td>`;
      /* ⚠️ **行号格显式先画**（不靠"`_row` 恰好是第一个键"）：题头 `pcols` 与数据格是同源同序的，
         但**行号列是这一屏的锚**（"第 N 行…"那类报错按它对号）⇒ 把它钉死在第一格，
         顺带把那枚标记也钉在它上面（⛔ 别让标记跟着键顺序漂到别的格）。 */
      const tag = !hit ? ''
        : plain ? ' <span class="tag t-mut">不导入</span>' : ' <span class="tag t-wn">不写入</span>';
      const tip = !hit ? ''
        : `${plain ? '这一行本来就跳过（不用你改）' : '这一行不会写进系统（要处理）'}：${esc(hit.why)}`;
      return `<tr${hit ? ` class="skiprow${plain ? ' plain' : ''}" title="${tip}"` : ''}>`
        + cell(r._row, tag)
        + Object.keys(r).filter(k => k !== '_row').map(k => cell(r[k])).join('')
        + '</tr>';
    }).join('');
    const pcols = plist.length
      ? Object.keys(plist[0]).map(k => `<th>${esc(k === '_row' ? '行' : k)}</th>`).join('') : '';
    const pnote = `本步读到 <b class="fc">${ptotal}</b> 行`
      + (pw == null ? '' : ` · 能写入 <b class="fc">${pw}</b> 行`)
      + ` · 表格显示`
      + (ptotal > plist.length ? `前 <b class="fc">${plist.length}</b> 行（全量已随本批暂存，④ 落库按**全量**处理）`
                               : `全部 <b class="fc">${plist.length}</b> 行`);
    /* ⭐ 表上方图例：只有真有行被标出来时才画（没有就别让人去找一个不存在的东西）。
       ⭐ 2026-09-27：**两类标记要说清区别**（守则 §2.8）—— 否则"灰底"会被当成"淡一点的警告"。 */
    const plegend = (nskip || nplain)
      ? `<div class="mut sm" style="margin-top:calc(6px * var(--fscale))">⚠️ 表里有两类标记，**看颜色一眼分开**（鼠标放到那一行上看原因）：`
        + `<br>· <span class="tag t-wn">不写入</span>（浅底 ＋ 左侧竖条）= **不会写进系统，要你处理**`
        + `（把文件改成标准格式后重导）；`
        + `<br>· <span class="tag t-mut">不导入</span>（灰底、没有竖条）= **本来就跳过**`
        + `（合计/小计 · 说明 · 空行 —— **不用你改**）。</div>`
      : '';
    /* ⭐ 2026-09-26（用户报障后加）：**有行写不进去时必须当面说**，⛔ 不许让 ④ 点下去才知道。
       ⚠️ 数由**域**给（`writable` 与 `total` 是通用面的键）—— 壳里仍**不认域号**；
       数优先用 `skipped` 的**逐行**结果（比 `total - writable` 这个差值可靠），
       ⭐ 且**两类分开说**（守则 §4.7 口径透明：合成一个"3 行"⇒ 用户以为三行都要自己改）。 */
    const nbad = nskip || (pw != null ? Math.max(0, ptotal - pw) : 0);
    const said = [];
    if (nbad > 0) {
      said.push(`有 <b>${nbad}</b> 行**不会写入**`
                + (nskip ? ' —— 已在上表**逐行标出**（浅底 ＋ 左侧竖条 ＋ 行号旁的「不写入」，'
                           + '鼠标放上去看原因）'
                         : '（原因见下面「落不了库的行」）'));
    }
    if (nplain > 0) {
      said.push(`另有 <b>${nplain}</b> 行**本来就跳过**（合计/小计 · 说明 · 空行 ⇒ 不是数据行，`
                + `已标成灰底，**不用你改**）`);
    }
    const pwarn = said.length
      ? `<div class="tip wn" style="margin-top:calc(8px * var(--fscale))">⚠️ ${said.join('；')}。`
        + (nbad > 0
           ? '④ 只写能写入的那些；要它们也进去：先把文件改成标准格式，再**整批回滚后重导**'
             + '（⛔ 别让两批叠着）。'
           : '④ 照常落库即可 —— 这一批**不需要你改文件**。')
        + '</div>'
      : '';
    prevCard = `<div class="card" style="margin-top:calc(12px * var(--fscale))"><h4>预览校验<span class="sp"><span class="mut sm">
      这一步**一个字节都不写库**</span></span></h4><div class="kpis">
      <div class="kpi"><div class="k">将写入</div><div class="v">${p.writable == null ? p.total : p.writable}</div>
        <div class="s">行</div></div>
      <div class="kpi"><div class="k">待处理</div><div class="v">${p.problem_count || probs.length}</div>
        <div class="s">处（行/列/原值/原因）</div></div>
      <div class="kpi"><div class="k">本步写库量</div><div class="v">0</div><div class="s">确认前零写库</div></div>
      ${Object.keys(p.kpis || {}).map(k => `<div class="kpi"><div class="k">${esc(k)}</div>
        <div class="v">${esc(String(p.kpis[k]))}</div></div>`).join('')}</div>
      ${probs.length ? `<div class="tw" style="max-height:200px">${TBL({cls:'sm',head:'<th>行</th><th>列</th><th>原值</th><th>原因</th>',
        rows:probs.slice(0, 30).map(x => `<tr><td class="now">${esc(x.row)}</td><td class="now">${esc(x.column)}</td>
          <td class="now">${esc(x.raw)}</td><td>${esc(x.reason)}</td></tr>`)})}</div>
        <div class="tip wn" style="margin-top:calc(8px * var(--fscale))">这些问题**不影响其余行落库**；认不出的值一律原样留着给人看，⛔ 不静默改成 0/空。</div>`
      : '<div class="tip ok">没有发现问题行</div>'}
      ${scopeEcho}
      ${lgBlocks(p.blocks)}
      <div class="mut sm" style="margin-top:calc(10px * var(--fscale))">${pnote}
        · 「行」= <b>Excel 里的行号</b>（与"第 N 行…"那类报错**同一个数**，用来对号）</div>
      ${plegend}
      <div class="tw" style="max-height:280px;margin-top:calc(6px * var(--fscale))">${TBL({cls:'sm',head:pcols,
        rows:[prows || lgEmpty(1, '没有数据行')]})}</div>
      ${pwarn}
      <div style="margin-top:calc(10px * var(--fscale))"><button class="btn pri" data-act="impCommit"${(needPj || IMP.busy) ? ' disabled' : ''} title="${IMP.busy?'正在落库 —— 请勿重复点击':(needPj?'先回第 ① 步选「这批数据进哪个项目」—— 没选就落不了库':'确认落库（这一步才真正写库）')}">${IMP.busy ? '正在落库…' : '④ 确认落库'}</button>
        <button class="btn" data-act="impReset">重来</button>
        ${needPj ? `<span class="mut sm" style="margin-left:calc(8px * var(--fscale))">${IMP.org.length
          ? '⚠️ 先回第 ① 步选「这批数据进哪个项目」 —— 没选就落不了库（⛔ 系统不替你挑，免得写进错项目）'
          : '⚠️ <b>库里还没有项目档案</b> —— 这批数据无处可写：先去「i8 接入层」页同步「常用项目列表」，回本页刷新后再导'}</span>` : ''}</div></div></div>`;
  }

  /* ---- ④ 结果与批次回滚 ----
     ⭐⭐ 2026-09-26（用户报障「**落库结果可读性比较差**」· 四个域一起改）—— 这一版把回执分三层：
       ① **人话指标**（**域自报**的 `kpis`）画成 KPI 卡 —— ⛔ 不再把回执的**原始键名**
          （`updated` / `undo_rows` / `message`…）当标签铺一排：那是**给程序看的**
          （截图里 `message` 那一长句被挤成一根细柱，就是这么来的）；
       ② **一句话结果**（域的 `message`）**整行**显示（它本来就是一句人话）＋ `**…**` 渲染成粗体；
       ③ **写入目标**（项目）**从壳自己的状态取**（`IMP.wrap` ⇒ `impPjLabel`）—— ⛔ 不用回执里那个
          `project key`（那是**仓库名**：既难认，又和第 ① 步显示的名字不是一回事）。
       原始回执**一个字不丢**：全进「技术明细」折起来（排查时展开）。
     ⚠️ 通用面**不认识任何域键** —— 哪几个数值得给用户看**由域自报**（`kpis`）；
        四个域都自报了 kpis 这件事由判据钉着（`test_imp_m06_api` / `test_imp_m04_api` /
        `test_imp_m05_api` / `test_imp_m11_api` 的「回执自报人话指标」）。 */
  let repCard = '';
  if (IMP.report) {
    const r = IMP.report;
    /* ⚠️ 回执的标量项里，**壳自己已经处理掉的**不再重复画：`kpis` / `blocks` 另画；
       `message` 走整行；`batch` 走批次行 ⇒ 剩下的（`updated`/`undo_rows`/`project key`…）
       一律进「技术明细」（⚠️ 它们**不是垃圾**：排查时正好要看原始键名）。 */
    const scalar = k => r[k] == null || ['string', 'number', 'boolean'].includes(typeof r[k]);
    const handled = ['kpis', 'blocks', 'message', 'batch'];
    const tech = Object.keys(r).filter(k => scalar(k) && handled.indexOf(k) < 0);
    const kpis = Object.entries(r.kpis || {});
    repCard = `<div class="card" style="margin-top:calc(12px * var(--fscale))"><h4>落库结果<span class="sp"><span class="mut sm">${
      IMP.wrap ? `写入项目：<b>${esc(impPjLabel(IMP.wrap))}</b>`
        + `<span class="mut">（仓库名 ${esc(IMP.wrap)}）</span>` : ''}</span></span></h4><div class="bd">
      ${r.message ? `<div class="tip ok">${lgMd(r.message)}</div>` : ''}
      ${kpis.length ? `<div class="kpis">${kpis.map(([k, v]) => `<div class="kpi"><div class="k">${lgMd(k)}</div>
        <div class="v">${esc(String(v))}</div></div>`).join('')}</div>` : ''}
      ${r.batch ? `<div class="tip">本次批次 <b class="fc">${esc(r.batch)}</b>
        <span class="mut sm">（要撤销这一批就点右边 —— 撤销按 §4.4.6 留痕、不做物理删）</span>
        <button class="btn sm" data-act="impRollback" data-batch="${esc(r.batch)}">整批回滚</button></div>` : ''}
      ${lgBlocks(r.blocks)}
      ${tech.length ? `<details style="margin-top:calc(10px * var(--fscale))"><summary class="mut sm">技术明细（原始回执
        ${tech.length} 项 · 排查用；⛔ 不是给你看的指标）</summary>
        <div class="tw" style="margin-top:calc(6px * var(--fscale))">${TBL({cls:'sm',rows:tech.map(k =>
          `<tr><th style="width:30%">${esc(k)}</th><td>${esc(String(r[k]))}</td></tr>`)})}</div></details>` : ''}
      <div style="margin-top:calc(10px * var(--fscale))"><button class="btn" data-act="impReset">再导一份</button></div></div></div>`;
  }

  /* ⚠️ 这里**不再画步骤条**（2026-09-26 用户按截图指出：「两条一模一样的四步条」⇒「**只留卡里那条**」）——
     卡内的 `head` 里那份是**它自己**的（`lgSteps(IMP_STEPS, IMP.step)`），本行原先又画了一遍 ⇒ 同屏两条。 */
  return `${lgNotice(IMP)}${head}${mapCard}${prevCard}${repCard}`;
};

/* 切域（表单元素 ⇒ 由 `change` 委托直呼 `ACT[a]`，⛔ 没有名单） */
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
  /* ⚠️ 原先这里是一句**静默 `return`**（2026-09-26 改）：按钮虽已按 `IMP.file` 置灰，但**状态与界面
     可能不同步**（真机自检当场撞上：点了没有任何反应、页上也没有一句话 ⇒ 只看得到"失败"，
     看不出为什么）。⇒ 按守则 §5.5「不能点的要说明原因」补一句**说清缺什么**。 */
  if (!IMP.file || !IMP.domain) {
    IMP.msg = IMP.domain ? '先选一个 .xlsx 文件（上一行「选文件」）—— 没文件就没有可解析的东西'
                         : '先选「导入哪个域」（本卡第一行）—— 不同域认的列不一样';
    IMP.kind = 'wn'; render(); return;
  }
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
   ⚠️ 展开是 `<button>`、选择是面板内的 `radio` ⇒ 都走 **click 委托**
      （`change` 委托只管 `<select>` / `<input type=file>` 那种表单元素；⭐ `#2` 起它也不需要登记）。 */
ACT.impPjToggle = () => { pjToggle('impPj'); render(); };
ACT.impPjPick = t => { const v = (t && t.dataset && t.dataset.pj) || ''; if (!v) return;
  IMP.wrap = v;
  /* ⭐ **截止核算月跟着所选项目换**（2026-09-26 修真缺陷）：它按项目存、且落库会写进所选项目 ⇒
     换项目时必须换成**那个项目自己**的（没有记录 ⇒ 空 ⇒ 落库时取本批最大月，与输入框的 placeholder 一致）。 */
  if (IMP.hasCut) IMP.cutoff = String((IMP.cutoffs || {})[v] || '');
  pjClose('impPj'); render();
  toast(`这批数据将导入项目 <b>${esc(IMP.pjDisp[v] || v)}</b>（键 = 仓库名，§2.7.4）`); };
/* ② → ③：预览（不写库） */
ACT.impPreview = async () => {
  IMP.msg = '正在校验（预览阶段不写库）…'; IMP.kind = 'ok'; render();
  let r = null;
  /* ⭐ 2026-09-26（`TAIL-106`）：**上下文一并递过去** —— 集采要在 ③ 就说出"**这批能配上几条**"，
     而它"算得出什么"取决于**这批进哪个项目**（域钩子收 `options`，与落库同一份上下文包）。
     ⚠️ 通用的几个域收不收 `options` 由**它们的签名**决定（后端按签名判），壳多给不吃亏。 */
  try { r = await API.impPreview(IMP.domain, { token: IMP.token, mapping: IMP.mapping,
                                              options: impOptions() }); }
  catch (e) { IMP.msg = `预览失败：${String((e && e.message) || e)}`; IMP.kind = 'err'; render(); return; }
  if (!r || r.ok === false) { IMP.msg = (r && r.message) || '预览失败'; IMP.kind = 'err'; render(); return; }
  IMP.preview = r; IMP.problems = r.problems || []; IMP.step = 2; IMP.msg = ''; render();
};
/* ③ → ④：确认落库（`options` = 域上下文：过程资料要"进哪个项目"；`remember` = 记下这套映射） */
ACT.impCommit = async () => {
  /* ⛔ **兜底拦住"没选项目就落库"**（2026-09-26）：按钮已按 `needPj` 置灰，但**程序化调用 / 键盘
     回车**也可能走到这里 —— 而落错项目的代价是**静默**的（`m06` 写历史段、不报错）⇒ 拦在本地并
     说清去哪改（⛔ 别只靠后端那句 `请先选项目` 兜着：那时用户已经点了、还以为自己在导数据）。 */
  if (IMP.hasPj && !IMP.wrap) {
    IMP.msg = IMP.org.length
      ? '请先在第 ① 步选「这批数据进哪个项目」—— 没选就落不了库（⛔ 系统不替你挑，免得写进错项目）'
      : '库里还没有项目档案 ⇒ 这批数据无处可写：请先去「i8 接入层」页同步「常用项目列表」（按 phid 幂等建档），回本页刷新后再导';
    IMP.kind = 'wn'; render(); return;
  }
  /* ⭐ **上下文包 = 域声明的键一并给**（⛔ 壳里不再按域号挑那几个键 —— 2026-09-26 收口）：
     各域的 `commit` 只读它认识的那几个（`m06` 读 `warehouse` / `cutoff_ym`、`m04` 读 `year_month`、
     `m11` 读 `project_key`），多给的键对它只是**字典里的空转**。
     ⚠️ 壳**不知道**哪个域要哪个键（那是域的事）⇒ ⛔ 别再加回"`if (域号) 只给这几个`"的写法。
     ⚠️ 打包本体搬到 `impOptions()` —— **预览用的就是它**（同一份，⛔ 不许两处各拼一遍）。 */
  const options = impOptions();
  /* ⛔ **同一动作不许并发提交**（2026-09-26 · `TAIL-108`）：连点两次「④ 确认落库」会发两次请求 ——
     而默认批号到**秒** ⇒ 第二次会撞批号唯一约束，用户看到 `IntegrityError …重复键违反唯一约束`（天书）。
     ⚠️ 这里挡"人点的路"，后端另有一道（`imp_spec._batch_no`：撞了就换号）—— 两道都要，
     因为脚本 / 接口能绕过界面（本仓老规矩：界面挡不住的路要有后端挡）。 */
  if (IMP.busy) return;
  IMP.busy = true;
  IMP.msg = '正在落库…'; IMP.kind = 'ok'; render();
  let r = null;
  try { r = await API.impCommit(IMP.domain, { token: IMP.token, mapping: IMP.mapping,
                                            remember: true, options: options }); }
  catch (e) { IMP.busy = false; IMP.msg = `导入失败：${String((e && e.message) || e)}`; IMP.kind = 'err'; render(); return; }
  IMP.busy = false;
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
