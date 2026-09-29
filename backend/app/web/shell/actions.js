/* shell/actions.js —— 壳接线层①：**写动作与交互**
 *
 * 来源：`index.html` 的第 L3329–L5095 行（`P4`② 三刀真拆 · 2026-09-19），**原文逐字搬出、顺序未改**。
 * 内容：`ACT` 表（表驱动的按钮 / 单元格动作）· 4 个全局事件委托（click / change / input / keydown）。
 * 加载顺序：**紧跟 `index.html` 的内联脚本之后**（见那里的 `<script src>`）；`boot();` 在三件都加载完之后。
 * ⛔ 改这里前先看计划 §23：**原型切片 `V.*` 不许搬出 `index.html`**（`ui_parity` 的 `U1` 逐行比它）。
 *    ⚠️ **订正（2026-09-28 · `TAIL-164`）**：原文写「`index.html` 里 258–3285 那一段（公共外壳 ＋ 原型切片）
 *    不许搬」—— 那句**过宽**（`§23` 的口径只管**原型切片**）：**非切片**的公共代码已按 `P2-a` 搬进
 *    `web/shell/{base,view,ui,proj,pages-a,pages-b}.js` ⇒ ⛔ 别再照那句拦。
 */
/* =====================================================================
   18. 交互处理器（`ACT.*` —— 全部交互动作的映射；`data-act="名"` → `ACT.名`）
   ⭐ `#2`（2026-09-26）起**没有 `CHG` 名单了**：`change` 由委托层**直呼 `ACT[a]`**
   ⇒ "表单类动作漏登记 ⇒ `change` 被静默丢弃"那个老坑**在结构上不再可能**（见目录 ⑤）。
   ===================================================================== */
/* ⭐ `M5-5`：跨页写动作的**统一包装**（关联 / 解绑 / 集采实际供应商）—— 成功后**两侧同刷**。
   ⚠️ 为什么不复用集采页的 `jcAct`：那个只重建 `JCs`（集采页专用）。而这三件事都是**跨页**的 ——
      m03 的「关联区」与集采台账的「付款子表」是**同一份记录**（判据 `ACC-JC-PAY-001/001-01`）
      ⇒ **两侧都要重拉**，"双向可见"才算落到界面上；少刷一侧 = 用户看着像"没生效"。
   ⚠️ 成败一律**看 `ok`**：后端对可预期的拒绝回 **HTTP 200 ＋ `ok:false` ＋ 一句中文**（同 `m07`/`m03`）
      ⇒ 只 catch 异常不够，那句中文会被当成成功吞掉。
   ⚠️ **必须放在 `ACT` 对象之外**（文件顶层）—— 它是函数声明，放进对象字面量会直接语法错（实测踩到）。 */
async function jcLinkAct(fn, okMsg) {
  let r = null;
  try { r = await fn(); }
  catch (e) { return toast(`<b>没能保存</b>：${esc(String((e && e.message) || e))}`, 7000); }
  if (!r || r.ok === false) { toast(`<b>没能保存</b>：${esc((r && r.message) || '后端未返回原因')}`, 7000); return null; }
  toast(typeof okMsg === 'function' ? okMsg(r) : okMsg);
  await reloadNotices();     /* 付款域侧（m03 行上那个"已关联"态） */
  await reloadM11();         /* 集采侧（合同的付款子表） */
  render();
  return r;
}
/* ⛔ `M5-8` 集采台账**页内导入向导**的状态与工具已删（`TAIL-75` 余项 · 2026-09-23 用户裁定：
   「导入只在启用初期用一次，之后实时更新」⇒ **只留通用面**）—— 现在那条路是「数据导入」页的
   `m11_jc` 域（`/api/imp/m11_jc/*`）。⛔ 别再往本文件加回 `jcImp*` 那一套。 */

/* ⭐ `M5-6` 增量抓取：**记住用户填过的「开始日期」**（取消后再开不丢，也不每次重算）。 */
let jcFetchSinceOn = '';
/* ⭐ `TAIL-69`（2026-09-22）：m04 导入的**预览态**（⚠️ 必须在 `ACT` 对象之外 —— 同上，`let` 进
   对象字面量 = `Unexpected identifier` ⇒ 整支 actions.js 失效、壳只剩 home，且离线文本断言全绿）。 */
/* ⛔ `plImportPrev` 已随页内导入弹窗删除（`TAIL-75` `B5c`）：预览态现在住在「数据导入」页的 `IMP`。 */
/* ⭐ `M5-6`：**默认开始日期** = 集采台账里**最大合同日期 − 3 天**（页面看得见、可改）。
   ⚠️ 与后端 `default_since` **同一口径** —— 只是壳里拿**已加载的 `JCs`** 算（够用、且立刻可见）；
      算不出来（库空 / 没有合法日期）⇒ 回空串 ⇒ **交给后端**（后端会走「全量」）。
   ⚠️ 为什么减 3 天：i8 里**增补合同沿用原单据日期**（实测有 2024 年的合同挂在近期单据下）
      ⇒ 起点卡在"最后一天"会**漏**；而落库按 `BillNo` **幂等** ⇒ 推早了只是多拿几条、不会重复插。
   ⚠️⚠️ **必须放在 `ACT` 对象之外**（文件顶层）—— `let` / `function` 放进对象字面量会直接语法错
      （`syntax_audit` 的 `node --check` 会当场抓到；`jcLinkAct` 那次已踩过一次，这是第二次）。 */
function jcFetchSinceDefault() {
  const ds = JCs.map(j => String(j.date || '').slice(0, 10))
    .filter(d => /^\d{4}-\d{2}-\d{2}$/.test(d)).sort();
  if (!ds.length) return '';
  const t = new Date(ds[ds.length - 1] + 'T00:00:00');
  t.setDate(t.getDate() - 3);
  const p = n => String(n).padStart(2, '0');
  return `${t.getFullYear()}-${p(t.getMonth() + 1)}-${p(t.getDate())}`;
}
/* ⭐⭐ `M5-9`：集采台账的「隐藏贸易公司三列」开关状态（**纯屏幕** · 刷新即回默认「显示」）。
   ⚠️ **不持久化**：它是显示偏好，不是业务数据（`SORT` 也是运行态、同样不持久化 —— 两者一致）。 */
let jcHideTrade=false;

/* ⭐ `M5-9`：把「隐藏贸易公司列」这个**屏幕偏好**落到表上。
   ⚠️⚠️ **不能只在 `BIND.m11` 里做一次** —— `render()` 会**重建整张表**（class 随之丢掉）
      ⇒ 每渲染一次都要重新落（否则一改筛选，隐藏就"自己弹回来了"，而且**不报错**）。
   ⚠️ `classList.toggle(cls, 布尔)` 一次搞定"加上/去掉"，⛔ 不用 if/else 两行（那种写法忘掉一支就静默）。 */
function jcApplyHide(){
  const tbl=document.querySelector('#view table[data-sort-key="m11:jc"]');
  if(tbl){
    /* ⚠️ 用**内联 `display`**，⛔ **不写 CSS 规则**：CSS 得放进真正的 `<style>` 段，而本页样式与脚本
       在同一文件里 —— 我上次把规则插进了 `<script>` 段 ⇒ 那句 CSS 成了**语法错** ⇒ **整段脚本崩掉**
       （症状是 `PJs is not defined`；`syntax_audit` 查的是壳的 JS 件、**没覆盖**这段 ⇒ 没拦住）。
       ⚠️ 列号 8/9/10 是**位置**：贸易公司名 / 贸易公司合同金额 / 贸易公司发票金额
          ⇒ **改 `JC_THEAD` 列序要同步改这里**（这也是"通用列管理"该按列的**稳定身份**定位的原因）。
       ⚠️ `display:none` ⇒ 剩下的列**自动变宽**（`table.dt` 是 `width:100%` + `table-layout:auto`）
          ＝ 用户要的「隐藏后其他列宽跟着自适应」。⛔ 别用 `visibility:hidden`（那**留着宽度**，白搭）。 */
    tbl.querySelectorAll(
      'thead > tr > th:nth-child(8), thead > tr > th:nth-child(9), thead > tr > th:nth-child(10),'
      + ' tbody > tr > td:nth-child(8), tbody > tr > td:nth-child(9), tbody > tr > td:nth-child(10)'
    ).forEach(el => { el.style.display = jcHideTrade ? 'none' : ''; });
  }
  const b=document.querySelector('#jcTradeBtn');
  if(b) b.textContent = jcHideTrade ? '👁 显示贸易公司列' : '🙈 隐藏贸易公司列';
}

/* ⭐⭐ `TAIL-180`（`B` 案 · 2026-09-29 **用户裁定**）：`m11` 合同主表的**行身份区**（勾选框 ＋ 序号 ＋
   合同日期 ＋ 材料名）一起钉 —— 表 **20 列 · 330 行**，往右滚去填那 **4 个可编辑列**（付款方式 / 备注 /
   存档号 / 寄回日期，正好落在最右）时，**看不见自己在给哪条合同填**（**会填错行**；
   同族 = 月度会大表 `TAIL-175`，那页已按 `A` 案钉好）。
   ⚠️⚠️ **为什么本页是"量出来的偏移"，而大表是静态 `calc(Npx * var(--fscale))`**（⛔ 两页形态不同，别照抄）：
      真机实测（`tools/oneoff/_a711_measure.py`「视口 × 档位」扫描）——
      ① 本表表头**带排序箭头**（`applySorts` 加的）⇒ 列宽不是"纯文字宽 × 倍率"；
      ② `table.dt` 是 `table-layout:auto` ⇒ 余宽会分给某些列 ⇒「勾选框」列 **1440/1920 时 29px、2560 时 34px**
      ⇒ 静态算式在某档视口 / 某种列数下**必然错位**（错位是 `sticky` 的经典失败模式，且**不报错**）。
      ⇒ 本页一律**渲染后按表头实测**，`left` 取**相邻格的真实右缘**（⛔ 不取整 —— 取整会攒出 1px 的缝）。
   ⚠️ **钉的必须是「连续前缀」**（`sticky` 的硬约束）：序号(#1) 与 材料名(#3) 中间隔着 合同日期(#2)
      ⇒ 只钉两头会让 #2 从缝里露出来 / 被盖住 ⇒ **一并钉上 #2**（用户选 `B` 时点的是"行身份区"）。
   ⚠️ 列号（0/1/2/3）是**位置**、跟着 `JC_THEAD` 的列序走 —— 改列序要同步改这里（同 `jcApplyHide` 那条口径）。
   ⚠️ 幂等：`render()` 会**重建整张表** ⇒ 每次渲染都要重新落（同 `jcApplyHide`，⛔ 别只做一次）。 */
const JC_PIN = [1, 2, 3];   /* ⭐ 首格 0（勾选框）在原型切片里**本来就带 `fl`**（`TAIL-170`-③）⇒ 不在这儿管 */
function jcApplyPin(){
  const tbl=document.querySelector('#view table[data-sort-key="m11:jc"]');
  if(!tbl) return;
  const head=tbl.querySelector('thead > tr'); if(!head) return;
  const ths=[...head.children];
  if(ths.length<=JC_PIN[JC_PIN.length-1]) return;         /* 列数不像预期 ⇒ ⛔ 别瞎设偏移 */
  const L0=ths[0].getBoundingClientRect().left;
  /* 第 i 列的 `left` = **它前面那一格的右缘**（真实边界，见上）。
     ⚠️ `i===0` 必须单列（左缘 = `L0`）—— 合计行首格「合计」也钉 `i=0`，而 `ths[-1]` 是 `undefined`
     ⇒ 不单列会**静默抛** `Cannot read properties of undefined`（实测：真机 3 次 pageerror；
     ⚠️ 它**不报在界面上** —— 只有 `fl` 那句先跑到了，看起来"居然还是对的"，最难查的那种）。 */
  const off=i=>i===0?0:ths[i-1].getBoundingClientRect().right-L0;
  const put=(el,i)=>{
    if(!el||el.colSpan>1) return;                         /* 空态行是 `colspan=20` 的单格 ⇒ 不是"一格一列" */
    el.classList.add('fl'); el.style.left=off(i)+'px';
  };
  JC_PIN.forEach(i=>put(ths[i],i));
  [...tbl.querySelectorAll('tbody > tr')].forEach(tr=>{
    const tds=[...tr.children];
    if(tds.length<ths.length) return;                     /* 列数不足（空态行 / 结构变了）⇒ 整行跳过 */
    if(tr.classList.contains('sumrow')) put(tds[0],0);    /* ⚠️ 合计行的首格是「合计」两个字：不钉它，
                                                             横滚时它被滚走 ⇒ 钉住的那几格左边**露个洞** */
    JC_PIN.forEach(i=>put(tds[i],i));
  });
}
/* ⚠️ 偏移是**量出来的** ⇒ **视口一变就得重量**（大表那种静态算式不需要这条）—— 只在本页生效。
   ⚠️ 防抖：`resize` 一次会连发几十下，每下都排 330 行会把滚动卡住。 */
let _jcPinTimer=null;
window.addEventListener('resize',()=>{
  if(typeof VIEW==='undefined'||VIEW!=='m11') return;
  clearTimeout(_jcPinTimer); _jcPinTimer=setTimeout(jcApplyPin,120);
});

/* ⭐ `M5-9` base64 ⇒ 浏览器下载。
   ⚠️ 必须 `Blob` + `URL.createObjectURL`：把 base64 直接塞进 `<a href>` 在几百 KB 时会
      **静默失败**（URL 长度上限，而失败时**不会有任何提示** —— 那种"点了没反应"最难查）。 */
function jcDownload(name, b64) {
  try {
    const bin = atob(String(b64 || ''));
    const buf = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) buf[i] = bin.charCodeAt(i);
    const url = URL.createObjectURL(new Blob([buf], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' }));
    const a = document.createElement('a');
    a.href = url; a.download = String(name || 'export.xlsx');
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 4000);      /* ⚠️ 不 revoke 会漏内存（每次导出都漏一份） */
  } catch (e) { toast(`<b>下载失败</b>：${esc(String((e && e.message) || e))}`, 7000); }
}

/* 热替换主题样式（⭐ 2026-09-21 加）——**⛔ 不刷新页面**。
   ⚠️ 主题是 `<link>` 拉的一整份 CSS（不是几个变量），但**换 URL 就能就地换掉**：
      新建一个带 cache-bust 查询串的 `<link>`，等它 `load` 完再把旧的那份摘掉
      ⇒ 全站样式当场换、**当前页与页面状态一个都不动**。
   ⚠️ 为什么必须这样（⛔ 不能走"整页刷新"那条路）：刷新会把壳的视图状态清零 ⇒
      用户正在「系统设置」上点、一刷新就被**扔回看板**（还得再点回来）—— 这正是用户报的那个毛病。
   ⚠️⚠️ **连注释里也别写出"那个 API 的调用形态"** —— `test_acc_theme_user.py` 会扫壳全文找它，
      把注释里的示例当成真调用报一条假红（同类坑：主题守卫会把注释里那种"变量引用示例"当成真引用）。
   ⛔ 也**不许**改成"在 JS 里写变量值" —— 那是把主题真源复制成第二份
      （`test_theme.py` 的「壳不得自带 `:root`」守卫盯着这条）。
   ⚠️ `onload` 才摘旧的 ⇒ 新 CSS 万一取不到，**旧样式仍在**（不会变成一张没样式的白页）。 */
function applyThemeLive() {
  const old = document.querySelector('link[href^="/static/theme.css"]');
  const nw = document.createElement('link');
  nw.rel = 'stylesheet';
  nw.href = '/static/theme.css?v=' + Date.now();
  nw.onload = () => { if (old && old.parentNode) old.parentNode.removeChild(old); };
  document.head.appendChild(nw);
}

/* ⚠️⚠️⚠️ **放这里的东西一律是"文件顶层的函数/变量"** —— 上面这三段（`jcHideTrade` / `jcApplyHide` /
   `jcDownload`）我**又**先插进了 `ACT` 对象字面量里，`syntax_audit` 的 `node --check` 当场报
   `SyntaxError: Unexpected identifier 'jcHideTrade'`。
   ⭐ **这是同一个坑的第三次**（前两次：`jcLinkAct`、`jcFetchSinceOn`）——
      **凡 `let` / `const` / `function` 声明，只能放"文件顶层"或"函数体里"，⛔ 绝不能放 `const ACT={…}` 内部。** */

/* ===== 「导出 Excel」的**真分发**（`TAIL-04` · `REQ-R1` · §7.1）=====
   壳里 10 个按钮共用**同一个动作** `exp`，靠按钮上的 `data-t` 认页 ⇒ 这里就是那张分发**表**。

   ⛔ **本段只动动作体，不动任何 `V.` 切片、⛔ 不改按钮的 `data-act`**：
      `ACT` / 本表都是**顶层 const**、不在 `V.<页>` 切片内 ⇒ `ui_parity` 的 `U1` 看不见它们
      （口径见 `.workbuddy/plans/开发计划-主文档.md` §2 与 §6.2；`BIND.m11` 那次改了 `data-act` 才惹出"两个导出按钮"）。

   ⭐ **行 = 屏幕上当前看到的那些** —— 取数一律走**该页自己的可见行出口**
      （`pjVisible` / `flVisible` / `ntHit(fNt)` / `plVisible`），⛔ **不在这里另写筛选**：
      两份筛选口径必打架（本项目的旧账）。顺序也由它带过去 —— 后端按传入 id 顺序出行。
   ⭐ **字节与文件名全由后端给**（`{ok, filename, content_b64}`）—— ⛔ 壳里不自己拼命名。

   ⚠️ **没有落点的页走兜底**（i8 接口清单 = 用户裁定不算列表页 · 已取消的差异清单 · m13 的演示按钮）
      ⇒ **如实说"还没有真文件"**，⛔ 绝不假装成功（原型那句「已导出 …」是**假成功**，本项目最忌）。
   ⭐ 2026-09-29（`TAIL-173` / `TAIL-185` · **用户两次裁定 `A`**）：**`m06` 与 `m08` 那两枚"点了必然空转"的
      朴素导出都已摘掉**（走 `BIND` 渲染后摘除，⛔ 不动切片）—— 它们的卡头里本来就各有一枚**真入口**
      （`m06` 的「批量导出（先选项目）」/ `m08` 的「导出（含数据透视表）」）⇒ 两枚并排、其中一枚必然空转
      ＝让用户以为坏了（守则 §4.6）。⚠️ 兜底分支**仍然要在**，它还有上面那几个落点在用。
   ⛔ **别顺手给这些页编一个落点**：`MOD-08` 的「含透视」那份有自己的按钮（`expPivot`）——
      把朴素这份也接过去 = 两个按钮干同一件事，还毁掉 `ACC-INV-001/001-12` 的「并存互不影响」
      （`tests/test_tail04_export.py` 会当场红）。
   ⛔ `集采台账` 也**不在本表**：`BIND.m11` 渲染时已把它的按钮改指 `jcExport`（走全列口径）⇒ 到不了这里。 */
const EXP_ROUTES = {
  /* `data-t`（与按钮上那个**逐字一致**）→ 拿行出口 ＋ 端点 */
  '项目档案':        { rows: () => pjVisible(), url: '/api/m01/projects/export' },
  '付款流水':        { rows: () => flVisible(), url: '/api/m05/flows/export' },
  '付款通知书台账':   { rows: () => ntHit(fNt),  url: '/api/m03/notices/export' },
  '付款计划审查结果': { rows: () => plVisible(), url: '/api/m04/plans/export' },
};

const ACT={
 /* 导航 */
 go:t=>go(t.dataset.k),
 /* ⭐ 批次 6（页级四态）：错误态那个「重试」按钮的唯一落点（`core.js::retryPage`）。
    ⚠️ 它只重拉**本页依赖的那几路** —— ⛔ 别改成"全站重拉"（那会把 `P3` 按需取数的收益还回去）。 */
 retryPage:()=>retryPage(),
 closeModal:()=>closeModal(),
 maskBg:(t,e)=>{ if(e.target.classList.contains('mask')) closeModal(); },
 /* 表头点击排序：同一列 升序 → 降序 → 原序；换一列则从该列升序开始（三态可反复切换） */
 headSort:t=>{ const k=t.dataset.tk, i=+t.dataset.i; const s=SORT[k]||(SORT[k]={i:-1,d:0});
   if(s.i!==i){ s.i=i; s.d=1; } else { s.d=(s.d===1)?-1:((s.d===-1)?0:1); }
   /* 弹窗内的表要重绘弹窗（render() 只重画 #view，不会更新弹窗内容） */
   if(String(k).indexOf('modal:')===0&&lastModal){ (lastModal.reopen||(()=>modal(lastModal)))(); }
   else render(); },

 /* 导出 / 通用 */
 /* ⭐ `TAIL-04`：**导出真分发** —— 按按钮上的 `data-t` 查 `EXP_ROUTES`（口径见那张表上面那段）。
    ⚠️ 原先是**一条诚实提示**（"导出尚未落地"）—— 那时**一个列表页都还没有真端点**。
       现在 4 页有端点了 ⇒ 它们改走真下载；**没端点的页照旧走兜底**，那句话**留在兜底分支里**
       （⛔ 别删：它是"这个页确实还没有落点"的唯一说法，删了就只剩沉默或假成功）。
    ⚠️ **失败一律说中文真因**：`API.post` 恒 HTTP 200（成败看 `ok`）⇒ 只看 `ok`，
       ⛔ 别去看状态码（那会得到"undefined"这类报不准也查不动的提示 —— `m03RunBatch` 踩过）。
    ⚠️ **空行集要拦住**：⛔ 不导一本空表让人以为坏了，也⛔ 不悄悄改成"导全量"（那就违背了
       「行 = 屏幕上看到的那些」）。 */
 exp:async t=>{ const tt=String(t.dataset.t||''), route=EXP_ROUTES[tt];
   /* ⭐ 2026-09-27（守则 §2.2/§3.1）：兜底提示改用**用户语言** —— 原措辞里有内部台账编号与后端术语
      （"导出端点"），用户看不懂也不知道该干什么。⛔ 那条"不假装成功"的底线不变。 */
   if(!route) return toast(`⏳ <b>「${esc(tt)}」这一页还没有导出功能</b>：`
     + `本页不单独导出 —— 请用它自己的那个入口（或换一页导出）`
     + `<br><span class="mut sm">⛔ 这里不假装成功：没有真文件生成，就绝不写「已导出」</span>`,9000);
   const rows=route.rows();
   if(!rows.length) return toast(`当前筛选下**一行都没有** —— 没什么可导的（先点「重置」看全部）`);
   let d=null;
   try{ d=await API.post(route.url,{ids:rows.map(r=>Number(r.id))}); }
   catch(e){ return toast(`<b>导出失败</b>：${esc(String((e&&e.message)||e))}`,8000); }
   if(!d||d.ok===false) return toast(`<b>导出失败</b>：${esc((d&&d.message)||'后端未返回原因')}`,8000);
   jcDownload(d.filename,d.content_b64);
   toast(`已导出 <b>${rows.length}</b> 行 ⇒ <b>${esc(d.filename)}</b>`
     + `<br><span class="mut sm">行 = 当前筛选下看到的那些（含顺序）· 列 = 页面表头去掉「操作」</span>`); },
  /* 已删除（2026-09-12）：一键抓取（fetchAll）—— 用户不需要该模块；接口清单页保留逐接口「触发」与「手动导入」。 */
 /* 触发：三个**按月抓取**的真入口（同一个弹窗形态、同一份口径）——
    `API-01` 付款通知书（默认「北京时间当月」）· `API-02` 收发结存表 / `API-03` 库存单据明细表
    （2026-09-13 用户口径：后两者**默认抓取本页所选核算年月**的数据）。
    ⚠️ 其余接口没有对应的抓取交互 ⇒ 保持"模拟成功"提示（用户拍板 2026-09-13：抓取入口行为必须一致）。 */
 fetchOne:t=>{ const api=t.dataset.api||'', tt=t.dataset.t||'';
   if(api==='API-01'||tt==='付款通知书') return ACT.fetchNt();
   if(api==='API-02'||tt==='收发结存表') return ACT.fetchWh();
   if(api==='API-03'||tt==='库存单据明细表') return ACT.fetchIv();
   /* ⭐ 2026-09-18 接线（`TAIL-27`）：API-05/06 现在是**真同步**（走 `m02Sync` 的二次确认 —— 会顶号）。
      ⛔ API-04（采购合同信息）**没有落点** —— 属**集采域（M5，未开工）** ⇒ 如实说不接，⛔ 不假装成功。 */
   if(api==='API-05'||tt==='仓库列表') return m02Sync('warehouses');
   if(api==='API-06'||tt==='常用项目列表') return m02Sync('common-projects');
   toast(`⏳ <b>「${esc(tt)}」尚未接通</b>：它的落点在<b>集采域</b>（M5 未开工）—— 在此之前⛔ 不假装成功`,7000); },
 /* ⭐ 降级路径（§3.6）的**真实入口在各自那一页**（与抓取走**同一套解析 / 落库管线**）
    ⇒ 这里只**把人送过去**，⛔ 不在这张表里再做一个上传控件（一份能力只许一个主人）。 */
 manualUp:t=>{ const tt=t.dataset.t||'';
   const map={'收发结存表':'m07','库存单据明细表':'m08','过程资料':'m06'};
   const k=map[tt];
   if(k){ go(k);
     return toast(`「${esc(tt)}」的降级路径 = <b>在那一页的「导入」入口</b>上传 i8 导出的 Excel（与抓取<b>同一套解析 / 落库</b>，§3.6）—— 已跳过去`,7500); }
   toast(`⏳ <b>「${esc(tt)}」的手动导入入口尚未接通</b>：降级路径要有对应页面的导入入口（与全站其它导入走同一套管线）—— 在此之前⛔ 不演示假上传`,7500); },
 /* MOD-14 剔除规则：**真增 / 删 / 改**（2026-09-13 P6 裁定①·乙）。
    ⚠️ 只改这张**演示表**（`RULE_EX`）；**不重算**已产生的剔除标记（`NO[].exrule`）—— 页内已写明。
    配置类数据按 §9.4 = **硬删、不留痕**；弹窗内输入由「保存」按钮一次性读取（不挂 data-act ⇒ 走不到委托层）。 */
 ruleAdd:()=>ACT.ruleForm(-1),
 ruleEdit:t=>ACT.ruleForm(+t.dataset.i),
 ruleForm:i=>{ const r=i>=0?RULE_EX[i]:null; if(i>=0&&!r) return;
   /* ⚠️ 规则类别必须是**后端认的四个 key 之一** ⇒ 用后端给的 `kinds` 做下拉。
      ⛔ 不用自由文本：填个「收款单位」后端会拒（§4.2.2 硬约束），填个错别字就更看不出问题。 */
   if(!RULE_KINDS.length) return toast('<b>规则类别还没取到</b> —— 页面顶部有取数失败的提示；请刷新后重试');
   const cur=i>=0?(RULE_RAW[i]||{}):{};
   const sel = `<select class="inp" id="rxKind">`
     + RULE_KINDS.map(k=>`<option value="${esc(k.kind)}"${k.kind===cur.kind?' selected':''}>${esc(k.label)}</option>`).join('')
     + `</select>`;
   modal({title:i>=0?`编辑剔除规则 · ${esc(r[0])}`:'新增剔除规则',
     body:`<div class="tip" style="margin-bottom:calc(10px * var(--fscale))">配置类数据<b>硬删</b>、不留痕（§9.4）；改规则<b>只影响后续抓取</b>，已产生的剔除标记<b>不重算</b>（§4.2.2）。</div>
       <div class="fld"><label>规则类别 <b>*</b></label>${sel}</div>
       <div class="fld"><label>命中值 <b>*</b>（多个用 ｜ 分隔）</label><input class="inp" id="rxHit" value="${esc(i>=0?r[1]:'')}" placeholder="例：水电｜水费｜电费"></div>
       <div class="fld"><label>剔除的业务含义</label><input class="inp" id="rxWhy" value="${esc(i>=0?r[2]:'')}" placeholder="例：期间费用，非材料/机械"></div>`,
     footer:`<button class="btn" data-act="closeModal">取消</button><button class="btn pri" data-act="ruleSave" data-i="${i}">${i>=0?'保存修改':'新增'}</button>`}); },
 /* ⭐ **落库走后端**：回执一律用后端那句中文原话（含「不重算」提醒）；失败**不关弹窗** ⇒ 已填内容都在。 */
 ruleSave:async t=>{ const i=+t.dataset.i;
   const body={kind:$('#rxKind').value, values:$('#rxHit').value.trim(), meaning:$('#rxWhy').value.trim()};
   if(!body.values) return toast('<b>命中值不能为空</b> —— 弹窗未关闭，已填内容都在');
   try{
     const res = i>=0 ? await API.m14RuleSet((RULE_RAW[i]||{}).id, body) : await API.m14RuleAdd(body);
     if(res.ok===false) return toast(`<b>没能保存</b>：${esc(res.message||'')}`, 8000);
     closeModal(); await reloadM14(); render();
     toast(esc(res.message||'已保存'), 7000);
   }catch(e){ toast(`<b>没能保存</b>：${esc(String((e&&e.message)||e))}`, 8000); } },
 ruleDel:async t=>{ const i=+t.dataset.i, r=RULE_EX[i]; if(!r) return;
   try{
     const res = await API.m14RuleDel((RULE_RAW[i]||{}).id);
     if(res.ok===false) return toast(`<b>没能删除</b>：${esc(res.message||'')}`, 8000);
     await reloadM14(); render();
     toast(esc(res.message||'已删除'), 7000);
   }catch(e){ toast(`<b>没能删除</b>：${esc(String((e&&e.message)||e))}`, 8000); } },
 /* ⭐ TAIL-96 集采项目剔除名单：**加入 / 停用 / 恢复**（页面在 M14；数据主人在集采域）。
    ⚠️ 回执一律用后端那句中文原话；失败只把话讲清、⛔ 不静默。 */
 jciAdd:async()=>{ const el=$('#jciName'), why=$('#jciWhy');
   const name=((el&&el.value)||'').trim();
   if(!name) return toast('<b>项目全名不能为空</b> —— 粘贴「项目全名」（与档案里那个名字一致）');
   try{
     const res = await API.m14JcIgnoreAdd({name_full:name, reason:((why&&why.value)||'').trim()});
     if(res.ok===false) return toast('<b>没能加入</b>：'+esc(res.message||''), 8000);
     await reloadM14(); render();
     toast(esc(res.message||'已加入剔除名单'), 8000);
   }catch(e){ toast('<b>没能加入</b>：'+esc(String((e&&e.message)||e)), 8000); } },
 jciSet:async t=>{ const id=+t.dataset.id, on=t.dataset.on==='1';
   try{
     const res = await API.m14JcIgnoreSet(id, {active:on});
     if(res.ok===false) return toast('<b>没能改</b>：'+esc(res.message||''), 8000);
     await reloadM14(); render();
     toast(esc(res.message||'已更新'), 7000);
   }catch(e){ toast('<b>没能改</b>：'+esc(String((e&&e.message)||e)), 8000); } },

 /* —— MOD-03 付款通知书 —— */
 pick:t=>{ const id=t.dataset.id; t.checked?pickSet.add(id):pickSet.delete(id); render(); },
 /* 全选：范围 = 【当前筛选结果里的可勾选行】，而不是全库（否则会选中看不见的行） */
 pickAll:t=>{ const ids=ntHit(fNt).filter(ntSelectable).map(n=>n.id);
   if(t.checked) ids.forEach(i=>pickSet.add(i)); else ids.forEach(i=>pickSet.delete(i));
   render(); },
 /* 金额编辑：审批金额只读（i8 源数据）；付款金额（会话级覆盖，**不留痕**）/ 统计结算金额 / 统计付款金额（旁路字段，留痕 + 不被导入覆盖）可手改 */
 editss:t=>{ const n=NO.find(x=>x.id===t.dataset.id); if(!n) return;
   const LAB={pay:'付款金额',ss:'统计结算金额',sp:'统计付款金额'};
   const k=t.dataset.k, NAME=LAB[k]||k;
   const old=k==='pay'?payEff(n):n[k], v=numOf(t.value);
   if(badMoney(v)){ toast(badMoneyMsg(NAME)+` ${M(old)}`); render(); return; }
   /* 统计字段只能「往小调」：按发票走，只能少付不能多付 → 上限 = 审批金额 */
   if((k==='ss'||k==='sp') && overCap(v,n.approve)){
     toast(`<b>${NAME}不能超过审批金额 ${M(n.approve)}</b><br>按发票走，<b>只能往下调（少付），不能往上调（多付）</b>。已保留原值 ${M(old)}`,4600);
     render(); return;
   }
   if(v===old) return;
   /* 付款金额：只做本次会话的临时覆盖 —— 不写 i8 原值、不影响统计口径与欠款，刷新即恢复默认。
      ⚠️ 会话级覆盖**不留痕**（口径 2026-09-12 定案：留痕只给统计两金额与调整单）。 */
   if(k==='pay'){
     n.payOv=v;
     render();
     toast(`<b>付款金额</b>已临时改为 ${M(v)}（原 ${M(old)}）<br>这是<b>本次会话的覆盖</b>，<b>刷新页面后会恢复为「审批金额 − 已付金额」</b><br>i8 原值 ${M(n.pay)} 与「统计付款金额」<b>均未改动</b>（会话级覆盖不留痕）`,5400);
     return;
   }
   /* ⭐ 2026-09-19 接线（`§19` 批 4 · S1）：统计两金额**走后端** `POST /api/m03/actions/stat` ——
      上限 / 留痕 / 欠款重算全在后端**同一出口**（`notice_actions.apply_stat_change`）；
      ⛔ 前端不再本地改值 + 本地留痕冒充落库（原先 `n[k]=v; pushTrail(...); debts()` 就是那个毛病）。
      回执里的中文说明（含欠款重算）**原样给用户**，失败亦然。
      ⚠️ 成功后 `reloadNotices()` 重拉列表：**黄底**由后端的 `edited_fields` 还原
         （适配层 `adaptNotice` 已把它映射成 `trail`，`hasT` 按列名判 —— 前端无需自己记留痕）✓ */
   const FIELD={ss:'stat_settle', sp:'stat_paid'}[k];
   API.statCell({notice_id:Number(t.dataset.id), field:FIELD, value:String(t.value)})
     /* ⚠️⚠️ 2026-09-20 补：`m03` 对**可预期拒绝**（如统计两金额越界）回 **200 ＋ `ok:false` ＋ 中文**
        ⇒ 不会抛。原先这里**直接 toast `r.message`** —— 失败那句中文看着和成功没什么两样
        （而且后面还会 `reloadNotices()` 把用户刚输入的值刷回去，人只会觉得"白输了"）。
        ⇒ **先判 `ok`**，失败就把话说清楚（并说明输入被还原是为什么）。 */
     .then(r=>{ if(!r || r.ok === false){
         toast(`<b>保存失败</b>：${esc((r && r.message) || '后端未返回原因')}`
           + `<br><span class="mut sm">这一格已还原成原来的值（后端没写进去）</span>`, 7000);
         return reloadNotices(); }
       toast(r.message, r.changed?4800:4600); return reloadNotices(); })
     .catch(e=>{ toast(`<b>保存失败</b>：${esc(e.message||e)}`); render(); }); },
 /* ⭐ 批量打印付款通知书（§4.6 场景五 · REQ-R6 · API-07）—— 2026-09-14 补出口：
    口径 = **勾选通知书 → 人工点击 → 调 i8 接口批量打印**（入参就是勾选的通知书）。
    ⛔ DEV-P-07 明令：**不自建打印模板**、只调 i8 接口、**接口不可用即砍功能**（非阻塞项）。
    ⇒ 本动作刻意**不调 window.print()**、不做打印预览 / 本地排版 / 导出，
      也**不清空勾选**（打印不改数据，属 R14 的"非消费型"动作，与"就地改值型"同侧）。
    ⭐ 2026-09-18 接线（`TAIL-46`）：原来只回一条「（模拟）→ 成功」（与 syncWh 同款）⇒ 现在**真调**
      `POST /api/m03/batch`，结果**逐条如实**（成功 N / 失败 M / **未产出单号显式列出**）—— 见 `m03RunBatch`。 */
 ntPrint:async ()=>{ const rows=[...pickSet].map(id=>NO.find(n=>n.id===id)).filter(Boolean);
   if(!rows.length) return toast('请先勾选要打印的付款通知书');   /* 防御：按钮在未勾选时已禁用 */
   return m03RunBatch(rows,'print'); },
 /* 只导出 PDF：与批量打印**同一次勾选**，只换 `mode`（后端 `MODE_PRINT` 分流）—— 入口由 `BIND.m03` 注入 */
 ntPdf:async ()=>{ const rows=[...pickSet].map(id=>NO.find(n=>n.id===id)).filter(Boolean);
   if(!rows.length) return toast('请先勾选要导出的付款通知书');
   return m03RunBatch(rows,'pdf'); },
 /* ⭐ `TAIL-46`：打印机设置的入口与保存（入口由 `BIND.m03` 注入到「批量打印」旁边） */
 m03PrinterOpen:()=>m03PrinterOpen(),
 m03PrinterSave:async ()=>{ const g=id=>((($(id)||{}).value)||'').trim();
   const url=g('#m03PrinterUrl'), mode=g('#m03PrintMode')||'auto', nm=g('#m03PrinterName');
   if(!url) return toast('请填打印机地址（形如 <span class="fc">ipp://192.168.5.248</span>）');
   /* ⚠️ 三项的合法性**全交后端**（`settings_store` 先校验后落盘：任一项非法 ⇒ 一个字都不写）——
      壳里⛔ 不另写一份校验（那会成第二份口径，且两处迟早不一致）。 */
   try { const r = await API.printerSet(url, mode, nm);
     /* ⭐ 2026-09-27（`TAIL-127` · 用户裁定 B）：**这个弹窗现在也管两个「打印版式 ID」**
        （从「系统设置」搬来）—— 它们**存在库里**、与打印机地址（`.env`）**不是同一个存储**
        ⇒ 分两步保存；⚠️ 只在**那两格真的在**时才提交（⛔ 别拿空串去覆盖它们的现值）。 */
     const pid = [['i8_print_id_material', '#m03PidMat'], ['i8_print_id_mechanical', '#m03PidMech']]
       .filter(([, sel]) => $(sel));
     let pidMsg = '（本弹窗没有版式 ID 那两格 ⇒ 未提交）';
     if (pid.length) {
       const pairs = pid.map(([k, sel]) => [k, g(sel)]);
       const pidRes = await m14Save(pairs);
       if (!pidRes.ok) {
         return toast('打印机设置**已保存**，但<b>版式 ID 没保存上</b>：'
           + `${pidRes.errors.map(esc).join('<br>')}`
           + '<br>⚠️ 请核对后重试（打印机那部分已经生效了）', 12000);
       }
       pidMsg = ` · 版式 ID 已保存 <b>${pid.length}</b> 项（已留痕）`;
     }
     closeModal();
     return toast(`打印机设置已保存：<b>${esc(r.printer_ipp_url)}</b> · 通道 <b>${esc(r.print_mode)}</b>`
       + (r.printer_name ? ` · 打印机 <b>${esc(r.printer_name)}</b>` : '')
       + pidMsg + `（<b>即时生效</b>，无需重启）`, 9000); }
   catch (e) { return toast(`<b>没保存上</b>：${esc(String((e && e.message) || e))}`, 9500); } },
 batchPay:()=>{ const all=[...pickSet].map(id=>NO.find(n=>n.id===id)).filter(Boolean);
   /* ⭐ 撤单行**不进付款批次**（走 `ntPayCand`，§4.2.7 方向）：正常路径下它们**根本勾不上**
      （勾选框对撤单行禁用、全选/按计划勾选也走同一出口）；这里再兜一道，
      防的是"勾上之后才被标撤单"这类**状态错位**把一张已作废的单送进付款。 */
   const rows=all.filter(ntPayCand), drop=all.filter(n=>!ntPayCand(n));
   if(!rows.length){ closeModal(); return toast('请先勾选要付款的记录'); }
   /* 不可付 = 未审批 · 本次应付 ≤ 0（已付清）· ⭐ **集采未关联**（§4.4.3）。
      ⚠️ 判据走**唯一出口** `ntPayBlock(n)`（`index.html`，与后端 `PayRow.block()` 逐条对应）——
         ⛔ 别在这里再手写一遍条件（两套判据必然漂移）。存在任一条时「确认付款」直接禁用（不是点了才拦）。 */
   const bad=rows.filter(n=>ntPayBlock(n));
  /* ⭐ 2026-09-25 用户点检后追加要求：**不可付必须说清是哪种原因**（⛔ 不能只写"不可付"）。
     ⚠️ 原因一律取自 `ntPayBlock(n)`（`index.html` 的**唯一出口**，与后端 `PayRow.block()` 逐条对应）——
        ⛔ 别在这里另写一套文案（两套必然漂）。 */
  const whyCell=n=>{ const w=ntPayBlock(n);
    return w?`<span class="mut sm" title="${esc(w)}">不可付：${esc(w)}</span>`:'<span class="mut sm">不可付</span>'; };
  const badWhy=(()=>{ const m={}; bad.forEach(n=>{ const w=ntPayBlock(n); if(w) m[w]=(m[w]||0)+1; });
    return Object.keys(m).map(w=>w+' '+m[w]+' 条').join(' · '); })();
   Object.keys(payDraft).forEach(id=>{ if(!pickSet.has(id)) delete payDraft[id]; });   /* 清掉已不在批次里的草稿 */
   const whyOf=n=>ntVoid(n)?'i8 已撤单':'已剔除';
   const body=`${drop.length?`<div class="tip wn" style="margin-bottom:calc(10px * var(--fscale))"><b>⚠️ 已自动排除 ${drop.length} 条不可付款的记录</b>（${esc(drop.map(n=>n.code+'（'+whyOf(n)+'）').join('、'))}）—— <b>剔除行</b>按 §4.2.2 不进统计；<b>i8 已撤单行</b>的单据在 i8 侧已被删除。两者都<b>不该产生付款</b>；请先<b>恢复剔除 / 撤销已付 / 解绑关联</b>。</div>`:''}<div class="tip" style="margin-bottom:calc(10px * var(--fscale))">已勾选 <b>${rows.length}</b> 条。<b>本次应付 = 付款金额</b>（默认 = 审批金额 − 已付金额；人工改过则以人工值为准）；「本次付款金额」<b>默认等于本次应付</b>，可改小。校验：<b>未审批</b>不可付（DEV-P-06）；<b>超出本次应付</b>被拦截（防超付）；付款方式选「其他」须填备注（DEV-P-01）。<b>任一校验不通过，整批不产生流水。</b></div>
     ${bad.length?`<div class="tip wn" style="margin-bottom:calc(10px * var(--fscale))"><b>⚠️ 有 ${bad.length} 条不可付，「确认付款」已禁用。</b>${badWhy?`（${badWhy}）`:''}请点该行的「<b>删除</b>」把它移出本次付款，或关闭后调整勾选 —— <b>删除会同时取消该行的勾选</b>，<b>已填的方式与金额不会丢</b>。${bad.some(ntJcUnlinked)?'<br><b>⚠️ 其中「集采未关联合同」的行，出路不是「删除」</b> —— 回付款通知书页把那一行<b>关联到一张集采合同</b>（§4.4.3），再回来付款。':''}</div>`:''}
     <div class="tw" style="max-height:44vh">${TBL({cls:'cond',key:'modal:batchPay',head:BP_THEAD,
     rows:rows.map((n,i)=>{const p=paidOf(n.id), can=payEff(n), ok=!ntPayBlock(n);
       const plan=PLs.find(pl=>pl.docNo===n.code), dm=plan?plan.method:'现汇';
       const df=payDraft[n.id]||{}, curM=df.m||dm, curA=df.a||can.toFixed(2);
       return `<tr class="${ok?'':'hl'}"><td class="fc">${n.code}</td>
       <td class="now" title="付款项目全名：${esc(n.proj)}">${dispCell(n.proj,n)}</td>
       <td class="ctr">${astatTag(n.astat)}</td>
       <td class="num">${M(n.approve)}</td><td class="num">${M(p)}</td>
       <td class="num" style="${can>0?'':'color:var(--ok)'}"><b>${M(can)}</b></td>
       <td>${ok?`<select class="inp" id="bm${i}" data-act="payDraft" data-id="${n.id}" data-f="m">${optsOf(enumVals('payMethod'),curM)}</select>`:whyCell(n)}</td>
       <td class="num">${ok?`<input class="inp num" id="ba${i}" data-act="payDraft" data-id="${n.id}" data-f="a" value="${curA}">`:'<span class="mut">—</span>'}</td>
       <td class="ctr now"><button class="btn sm dg" data-act="batchPayDel" data-id="${n.id}">删除</button></td></tr>`}),
     sum:rows.length?sumRowOf(BP_THEAD,rows,{5:rs=>N2(rs.reduce((a,n)=>a+payEff(n),0)),7:rs=>N2(rs.reduce((a,n)=>a+Number((payDraft[n.id]&&payDraft[n.id].a)||payEff(n)),0))},{tip:'本次应付 / 本次付款金额 合计；「本次付款金额」按当前已填值合计（改金额后重绘刷新）'}):''})}</div>
     <div class="f2" style="margin-top:calc(11px * var(--fscale))">
       <div class="fld"><label>付款日期</label><input class="inp" type="date" id="bDate" value="${SYS_TODAY}"></div>
       <div class="fld"><label>备注</label><input class="inp" id="bRemark" placeholder="选「其他」付款方式时必填"></div>
     </div>
     <div class="tip" style="margin:0"><b>提交后：</b>每条写入一条<b>独立付款流水</b> → 「已付金额」累加 → 状态按 <span class="fc">已付金额 ≥ 审批金额</span> 自动判定（无「部分付」中间态，DEV-P-02）。</div>`;
   modal({wide:true,title:`批量付款 · 已勾选 ${rows.length} 条`,body,reopen:()=>ACT.batchPay(),
     footer:`<button class="btn" data-act="batchPayCancel">取消</button><button class="btn pri" data-act="batchPayOk"${bad.length?` disabled title="有 ${bad.length} 条不可付，请先删除这些行"`:''}>确认付款</button>`}); },
 /* 草稿记录：行内的付款方式 / 金额一改就存下，重建弹窗（删除行、排序）时不丢 */
 payDraft:t=>{ const id=t.dataset.id; const d=payDraft[id]||(payDraft[id]={});
   if(t.dataset.f==='m') d.m=t.value; else d.a=t.value; },
 batchPayCancel:()=>{ payDraft={}; closeModal(); },
 /* 删除行：从本次付款中移出该行（= 取消该行勾选），并重建弹窗 */
 batchPayDel:t=>{ const id=t.dataset.id, n=NO.find(x=>x.id===id);
   pickSet.delete(id); render();
   if(pickSet.size){ toast(`已把 <b>${n?n.code:id}</b> 移出本次付款（同时取消该行勾选）`); ACT.batchPay(); }
   else { closeModal(); toast('已移除全部记录，本次付款未提交'); } },
 batchPayOk:t=>{ if(busy) return;
   /* ⭐ 与 `batchPay` 同一道闸：撤单行**不得产生付款流水**（窗口里已排除，这里兜底防状态错位） */
   const rows=[...pickSet].map(id=>NO.find(n=>n.id===id)).filter(Boolean).filter(ntPayCand);
   if(!rows.length) return toast('没有可付款的记录');
   const dt=($('#bDate')&&$('#bDate').value)||SYS_TODAY;
   const rm=(($('#bRemark')&&$('#bRemark').value)||'').trim();
   const batch=[], errs=[];
   rows.forEach((n,i)=>{
     const can=payEff(n);      /* 本次应付 = 付款金额（默认 = 审批金额 − 已付金额） */
     if(n.astat!=='已批'){ errs.push(`${n.code} · 审批状态非「已批」，不可付款`); return; }
     if(can<=0){ errs.push(`${n.code} · 本次应付为 0（审批金额 − 已付金额）`); return; }
    /* ⭐ ⑤ 集采未关联（§4.4.3）：窗口已禁用按钮，这行是**兜底**（防"勾上之后才被解绑"的状态错位）——
       与后端 `PayRow.block()` 同一条口径、同一句文案。 */
    if(ntJcUnlinked(n)){ errs.push(`${n.code} · 集采未关联合同，不可付款`); return; }
     const mEl=$('#bm'+i), aEl=$('#ba'+i);
     const m=(mEl&&mEl.value)||'现汇';
     const amt=numOf(aEl?aEl.value:'');
     if(badMoney(amt,{positive:1})){ errs.push(`${n.code} · 付款金额不合法`); return; }
     if(amt>can){ errs.push(`${n.code} · 本次 ${M(amt)} 超出本次应付 ${M(can)}`); return; }
     if(m==='其他'&&!rm){ errs.push(`${n.code} · 付款方式选「其他」必须填备注`); return; }
     batch.push({n,amt,m});
   });
   if(errs.length) return toast(`<b>已拦截 ${errs.length} 条，整批不产生任何流水</b><br>${errs.slice(0,3).map(esc).join('<br>')}${errs.length>3?`<br>…还有 ${errs.length-3} 条`:''}`,5600);
   /* ⭐ 2026-09-19 接线（`§19` 批 4 · **S3③**）：**落库走后端** `POST /api/m03/actions/batch-pay` ——
      整批重算 / 整批不落半批 / 幂等 全在服务端（`notice_actions.apply_batch_pay`）；
      ⛔ 前端不再本地往 `FLs` 塞流水冒充落库（原先就是这样，刷新即丢 ✗）。
      ⭐ **必须带幂等号** `request_id`：提交按钮按下即锁定，服务端据它**拒重复提交**（§4.4.4）
      —— 「重复提交被拒」那条判据能成立，全靠这一行。 */
   const rid=(self.crypto&&crypto.randomUUID)?crypto.randomUUID():String(Date.now())+Math.random().toString(16).slice(2);
   const drafts={}; rows.forEach((n,i)=>{ const mEl=$('#bm'+i), aEl=$('#ba'+i);
     drafts[String(n.id)]={pay_method:(mEl&&mEl.value)||'', amount:(aEl?aEl.value:'')}; });
   busy=true; if(t){ t.disabled=true; t.textContent='提交中…'; }
   const unlock=()=>{ busy=false; if(t){ t.disabled=false; t.textContent='确认付款'; } };
   API.batchPay({ids:rows.map(n=>Number(n.id)), drafts, pay_date:dt, remark:rm, request_id:rid})
     .then(r=>{ if(!r.ok){ unlock(); return toast(`<b>提交被拦下，整批未产生任何流水</b><br>${esc(r.message)}`,6000); }
       unlock(); pickSet.clear(); payDraft={}; closeModal();
       toast(r.message,5200); return reloadNotices(); })
     .catch(e=>{ unlock(); return toast(`<b>提交失败</b>：${esc(e.message||e)}`,6000); }); },
 revDlg:t=>{ const f=FLs.find(x=>x.id===t.dataset.fid); if(!f) return;
   const n=NO.find(x=>x.id===f.nid)||{};
   modal({title:`撤销付款流水 · ${f.id}`,body:`<div class="tip dg" style="margin-bottom:calc(10px * var(--fscale))"><b>撤销必须填写原因</b>（留痕）。撤销后该通知书的「已付金额」随之减少、状态<b>自动回退</b>（按 §4.4.2 判定基准 = <b>审批金额</b> 重判）。</div>
     ${kvBlock([['流水号',`<span class="fc">${f.id}</span>`],['单据编码',`<span class="fc">${n.code||'—'}</span>`],
       ['付款项目',`<span style="font-size:calc(11.5px * var(--fscale))">${esc(n.proj||'—')}</span>`],
       ['付款金额',`<span class="fc">${M(f.amt)}</span>`],['付款日期',`<span class="fc">${f.date}</span>`],
       ['实际付款方式',enumTag('payMethod',f.method)]])}
     <div class="fld"><label>撤销原因 <b>*</b></label><input class="inp" id="rReason" placeholder="例：收款单位变更，需重付"></div>`,
     footer:`<button class="btn" data-act="closeModal">取消</button><button class="btn dg" data-act="revOk" data-fid="${f.id}">确认撤销</button>`}); },
 /* ⭐ 已接后端：`POST /api/m05/flows/{id}/revoke?reason=`（§4.4.5 —— **原因必填由后端把关**；
    撤销后已付金额回退、状态按 §4.4.2 重判，都在后端做） */
 revOk:t=>{ const f=FLs.find(x=>x.id===t.dataset.fid); if(!f) return;
    const rs=(($('#rReason')&&$('#rReason').value)||'').trim();
    if(!rs) return toast('<b>撤销原因必填</b>（撤销留痕）');
    closeModal();
    m05Act(()=>API.flowRevoke(f.id, rs),
      `已撤销流水 <b>${f.id}</b>（原因：${esc(rs)}）<br>该单据「已付金额」已回退，状态按 §4.4.2 重判`); },
 /* 抓取 i8 —— 一律**按月抓取**（2026-09-13 用户口径：三个入口都抓「所选月份」的数据；
   ⚠️ 下面两个动作里那个**局部**变量叫 `apiCode`（⛔ 别叫 `API`）—— `API` 是全壳**数据出口**的名字
      （定义在 `api.js`），同名会把外层接线整个遮蔽掉（本函数里再用 `API.xxx` 就静默失效）。
    收发结存表 / 库存单据明细表打开弹窗时**默认月份 = 本页「核算年月」当前所选**）。
    界面只选「核算年月」；i8 侧的入参是「单据日期起止」（闭区间），由系统自动换算后传入。
    ⚠️ `fetchDlg` 的 **nt 分支文案一字未改**（既有断言钉着它）；wh / iv 两个分支另写。 */
 ownAssign:t=>ownAssignSubmit(Number(t.dataset.i), t.dataset.pid),
 /* `TAIL-39`：**兜底前先跑一次 i8 仓库名单**（问 → 二次确认 → 就地显示结果）；判定全在后端 */
 ownWhCheck:t=>ownWhCheck(Number(t.dataset.i)),
 ownWhOk:t=>ownWhOk(Number(t.dataset.i)),
 fetchNt:()=>{ fetchKind='nt'; return ACT.fetchDlg(); },
 fetchWh:()=>{ fetchKind='wh'; fetchM=fWhYm; return ACT.fetchDlg(); },   /* 默认 = 本页「核算年月」当前所选 */
 fetchIv:()=>{ fetchKind='iv'; fetchM=fIvYm; return ACT.fetchDlg(); },   /* 同上 */
 fetchDlg:()=>{ const k=fetchKind, m=fetchM, from=m+'-01', to=monthEnd(m);
   const NM={nt:'付款通知书',wh:'收发结存表',iv:'库存单据明细表'}[k]||'付款通知书';
   const apiCode={nt:'API-01',wh:'API-02',iv:'API-03'}[k]||'API-01';
   const box=`<div class="fbar plate">
        <div class="fi"><label>抓取月份</label>${tmBtn('fetchMonth',{scope:'fetch',val:m,modes:['月']})}</div>
        <div class="fi"><label>换算后传给 i8 的入参（只读）</label><div class="inp" style="background:var(--sf2);color:var(--tx2);border-style:dashed;font-family:var(--fm);white-space:nowrap">单据日期 ${from} ~ ${to}</div></div>
      </div>`;
   const foot=`<button class="btn" data-act="closeModal">取消</button><button class="btn pri" data-act="fetchNtOk">按 ${m} 抓取</button>`;
   if(k==='nt'){ const hit=NO.filter(n=>n.date>=from&&n.date<=to);
     const okN=hit.filter(ntLive).length, exN=hit.filter(n=>n.excl).length;
     const vdN=hit.filter(ntVoid).length;
     const unN=hit.filter(n=>ntLive(n)&&n.astat==='未批').length;
     return modal({title:'抓取 i8 付款通知书（按月）',reopen:()=>ACT.fetchDlg(),body:
       `<div class="tip" style="margin-bottom:calc(10px * var(--fscale))">i8 侧的抓取实现是<b>选择「单据日期」起止时间</b>；这里只需选<b>月份</b>（默认「北京时间当月」），系统自动换算为<b>当月 1 号 ~ 末日</b>（<b>闭区间</b>），并<b>全量、不选项目、不分页</b>。</div>
      ${box}
      <div class="tip" style="margin:0"><b>${m}</b> 目前有 <b>${hit.length}</b> 条：有效 <b>${okN}</b> · 剔除 <b>${exN}</b> · i8 已撤单 <b>${vdN}</b>${unN?` · 其中未审批 <b>${unN}</b>`:''}。<br>抓取会<b>全量刷新源数据</b>，但<b>旁路值不受影响</b>（统计结算/统计付款金额 · 分类 · 集采实际供应商 · 调整单 —— 均不被导入覆盖）。</div>`,
       footer:foot}); }
   return modal({title:`抓取 i8 ${NM}（按月）`,reopen:()=>ACT.fetchDlg(),body:
     `<div class="tip" style="margin-bottom:calc(10px * var(--fscale))">i8 侧的抓取实现是<b>选择「单据日期」起止时间</b>；这里只需选<b>月份</b>（<b>默认 = 本页「核算年月」当前所选</b>，可改），系统自动换算为<b>当月 1 号 ~ 末日</b>（<b>闭区间</b>），并按<b>项目（phid 筛）</b>抓取（${apiCode} · §9.2）。</div>
      ${box}
      <div class="tip" style="margin:0">抓取会<b>全量刷新该月 · 该项目</b>的源数据；<b>手工值与调整单不被覆盖</b>（§9.5 幂等）。<br>要抓别的月份，改上面的月份即可 —— <b>默认就是本页当前所选的那个月</b>。</div>`,
     footer:foot}); },
 fetchNtOk:()=>{ const k=fetchKind, m=fetchM, from=m+'-01', to=monthEnd(m);
   /* ⭐ **接线（`TAIL-29`-② ④）**：付款通知书走**真抓**（后端 `/api/m03/notices/fetch`）；
      `wh` / `iv` 两条（材料域）仍走原型演示逻辑 —— 它们还没接线，别在这里假装成功。 */
   if(k==='nt') return ntFetchBackend(m);
   if(k==='iv') return ivFetchBackend(m);
   if(k==='wh') return whFetchBackend(m);   /* ⭐ 收发结存已接后端；`nt` 走 `/api/m03/notices/fetch`（见 fetchNtOk） */
   const NM={nt:'付款通知书',wh:'收发结存表',iv:'库存单据明细表'}[k]||'付款通知书';
   const apiCode={nt:'API-01',wh:'API-02',iv:'API-03'}[k]||'API-01';
   closeModal();
   if(k==='nt'){ const hit=NO.filter(n=>n.date>=from&&n.date<=to);
     /* ⭐ 再次导入的合并（§4.2.7 · 方案乙）：**模拟 i8 那边"这一批的单据有改动"** ——
        演示数据里 N05 的 i8 审批金额被调小（用来触发"越界提醒"），N08 未被手改（用来触发"跟随"）。
        ⚠️ 演示数据是**自造**的：`IMP_DEMO` 模拟"本次 i8 返回的源值"，只对**已存在的抓取范围**生效。 */
     const changed=[], warned=[], followed=[];
     hit.forEach(n=>{
       const newAp=impDemoAp(n);                    /* 模拟 i8 本次返回的审批金额（见下） */
       if(newAp==null||N2(newAp)===N2(n.approve)) return;
       const wasMan=impManSS(n)||impManSP(n);
       const msgs=impMerge(n,{approve:newAp,pay:n.pay});
       if(msgs.length) warned.push(n.code||n.id);
       else if(wasMan) changed.push(n.code||n.id);
       else followed.push(n.code||n.id);
     });
     /* ⭐ i8 撤单：演示里把**两行**当作 i8 本轮不再返回（标 IMP_GONE、不硬删），覆盖两个分叉：
        · `N19` —— **有牵涉**（已挂付款流水 F9）⇒ 硬拦、仍参与统计、带警示
        · `N24` —— **无牵涉**（无流水无关联）⇒ 正常退出统计
        口径（§4.2.7 定案 2026-09-14）：i8 侧**真删**了该单据 ⇒ 标「i8 已撤单」保留可查，
        但**退出全部统计**；单据号必变 ⇒ 撤单标记 = **终态**（不做"下次抓回来自动复原"）。
        ⚠️ 有牵涉（已挂付款流水 / 集采关联）⇒ **硬拦**：不许静默退出统计，提示"请先撤销付款 / 解绑关联"。 */
     const GONE_DEMO=['N19','N24'];
     GONE_DEMO.forEach(gid=>{ const gn=NO.find(n=>n.id===gid);
       if(gn&&!gn.manual&&!impHasGone(gn)) IMP_GONE[gn.id]={date:gn.date,code:gn.code,doc:gn.doc}; });
     render();
     const gw=Object.keys(IMP_WARN).length, gg=Object.keys(IMP_GONE).length;
     const gv=NO.filter(ntVoid), gBlocked=gv.filter(ntVoidJoint), gFree=gv.filter(n=>!ntVoidJoint(n));
     return toast(`已按 <b>${m}</b> 抓取付款通知书：传入 i8 的入参 = <span class="fc">单据日期 ${from} ~ ${to}</span>（闭区间）→ <b>${hit.length}</b> 条<br>`
       + `<b>再次导入的合并（方案乙）</b>：未手改的统计金额<b>跟随</b>新审批金额 <b>${followed.length}</b> 条`
       + `${changed.length?` · 已手改<b>保留人工值</b> ${changed.length} 条`:''}`
       + `${warned.length?`<br><span style="color:var(--wn)">⚠️ <b>${warned.length}</b> 条人工值越界（已保留原值、挂提醒）：${warned.slice(0,3).map(esc).join(' · ')}${warned.length>3?' …':''}</span>`:''}`
       + `${gg?`<br>⚠️ <b>i8 已撤单 ${gg} 条</b> —— 其中 <b>${gFree.length}</b> 条<b>已退出全部统计</b>（保留可查、终态不可复原，切「分类 = 剔除」可见）`
            + `${gBlocked.length?`；<b>${gBlocked.length}</b> 条<b>有牵涉 · 已硬拦</b>（仍参与统计）：请先<b>撤销付款 / 解绑关联</b>，处理完它才退出统计`  :''}`
            + `<br><span class="mut sm">不做「删除付款通知书」按钮 —— i8 行是源数据、永不删除，排除撤单靠的是「退出统计」（§4.2.7）</span>`:''}`
       + `<br><span class="mut sm">旁路值（分类 / 集采实际供应商 / 调整单）不被覆盖</span>`,7200); }
   toast(`已按 <b>${m}</b> 抓取 ${NM}（${apiCode}）：入参 = <span class="fc">核算年月 ${m}</span> → 单据日期 ${from} ~ ${to}（闭区间）＋ <b>项目（phid 筛）</b><br>该月源数据已全量刷新；<b>调整单 / 手工值不被覆盖</b>`,5600); },
  /* 批量改分类（重做）：勾选 → 点一次「→ 辅材 / → 机械 / → 集采」即完成，不再走弹窗
     ⭐ 改为「集采」时顺带**自动匹配供应商**（§6.6.3 触发时机）；离开集采时清空待确认标记 */
  /* ⭐ 已接后端：判定与落库全在后端（`POST /api/m03/actions/category`），前端只发勾选集 + 显示回执 */
  batchCatApply:async t=>{ const c=t.dataset.c; if(!c) return;
    if(!pickSet.size) return toast('请先勾选要改分类的记录');
    try{
      const r=await API.setCategory([...pickSet],c);
      if(!r.ok) return toast(`⚠️ 改分类失败：${esc(r.message)}`);
      await reloadNotices();
      toast(`${esc(r.message)}<br>人工判断优先，重新抓取<b>分类不被覆盖</b>（§4.2.4）`,5200);
    }catch(e){ toast(`⚠️ 改分类失败：${esc(String((e&&e.message)||e))}`); } },
  /* 单行改分类：直接在下拉的「分类」列里改，零额外点击
     ⭐ 改为「集采」时顺带**自动匹配供应商**（§6.6.3 触发时机） */
  /* ⭐ 已接后端：单行改分类与批量**走同一条路**（只传一个 id）—— 前端不另写一套判定 */
  editCat:async t=>{ const n=NO.find(x=>x.id===t.dataset.id); if(!n) return;
    const c=t.value, old=n.cat; if(c===old) return;
    try{
      const r=await API.setCategory([n.id],c);
      if(!r.ok){ t.value=old; return toast(`⚠️ 改分类失败：${esc(r.message)}`); }
      await reloadNotices();
      toast(`分类已改为 <b>${esc(c)}</b>（原 ${esc(old)}）<br>人工判断优先，重新抓取不被覆盖`,5600);
    }catch(e){ t.value=old; toast(`⚠️ 改分类失败：${esc(String((e&&e.message)||e))}`); } },
 /* 展示名人工修改（默认取仓库名；改它只影响显示，不影响项目归属）
    ⚠️ 不留痕 —— 留痕只给 ENT-01 明确要求的两处：项目全名 / 项目状态 */
  editDisp:t=>{ const p=PJs.find(x=>x.id===t.dataset.id); if(!p) return;
    const v=String(t.value).trim(); if(v===p.disp) return;
    /* ⭐ 已接后端：`PUT /api/m01/projects/{id}` —— 展示名**可改、不留痕**（§2.3.1 / §9.3） */
    pjAct(()=>API.pjUpdate(p.id,{disp:v}),
      `展示名已改为 <b>${esc(v)}</b>（只影响显示，不影响项目归属；该字段不留痕）`); },
 /* ⭐ 已接后端：`POST /api/m03/actions/exclude`（标记来源 `manual` 由后端定） */
 batchEx:async ()=>{ if(!pickSet.size) return toast('请先勾选要剔除的记录');
   try{
     const r=await API.exclude([...pickSet]);
     if(!r.ok) return toast(`⚠️ 剔除失败：${esc(r.message)}`);
     pickSet.clear();
     await reloadNotices();
     toast(`${esc(r.message)}<br>剔除行<b>默认不显示</b>，把「分类」切到 <b>剔除</b> 即可复查或恢复`,4600);
   }catch(e){ toast(`⚠️ 剔除失败：${esc(String((e&&e.message)||e))}`); } },
 /* 恢复剔除（2026-09-14 用户口径修正）：**必须勾选才恢复** —— 只恢复「已勾选 且 人工批量剔除」的行。
   ⚠️ 旧实现是 `NO.forEach` **无差别恢复全部人工剔除行**（点一下就把别人剔除的都放回来了）——
      与「剔除 / 恢复是一对**按行生效**的操作」不符，也与「批量」二字矛盾（批量 = 对勾选集操作）。
   ⚠️ 规则命中的剔除**任何情况下都不恢复**（§4.2.2「命中即剔除」语义靠这行保住）。
   ⚠️ 三个分母分开报：**勾选数 / 可恢复数（勾选∩人工剔除） / 不可恢复数（勾选∩规则剔除）** ——
      只报一个数会让用户以为"点了没反应"（勾了一堆规则剔除的行时，n 必然是 0）。 */
 /* ⭐ 已接后端：`POST /api/m03/actions/restore` —— 「只恢复人工剔除、规则命中不恢复」由后端保（§4.2.2），
    ⚠️ 三档分母（勾选 / 可恢复 / 规则命中）也已由后端的回执分开报，前端不再自己拼。 */
 batchUnEx:async ()=>{ if(!pickSet.size) return toast('请先勾选要恢复的剔除行 —— 「恢复剔除」<b>只对勾选行生效</b><br><span class="mut sm">（不能一键把所有人工剔除的行都放回来）</span>',5200);
   try{
     const r=await API.restore([...pickSet]);
     if(!r.ok) return toast(`⚠️ 恢复失败：${esc(r.message)}`);
     pickSet.clear();
     await reloadNotices();
     toast(`${esc(r.message)}<br><span class="mut sm">恢复后需把「分类」切回对应分类（或「全部」）才看得到</span>`,6000);
   }catch(e){ toast(`⚠️ 恢复失败：${esc(String((e&&e.message)||e))}`); } },

 /* —— MOD-04 付款计划：筛选 + 行多选 + 多选删除 + 选月份导入（2026-09-12 新增）—— */
 plFilter:()=>{ const el=$('#plReview'); plf.review=(el&&el.value)||'全部'; prunePlPick(); render(); },
 plFilterReset:()=>{ plf.ym=bjMonth(); plf.projs=[]; plf.review='全部'; pjClose('plPj'); prunePlPick(); render();
   toast('付款计划筛选已重置（年月回到「北京时间当月」，审查结果回到「全部」）'); },
 plPjToggle:()=>{ pjToggle('plPj'); render(); },
 plPjPick:t=>{ const f=t.dataset.pj; const i=plf.projs.indexOf(f); if(i>=0) plf.projs.splice(i,1); else plf.projs.push(f); prunePlPick(); render(); },
 plPjAll:()=>{ plf.projs=PL_PROJ_LIST(); prunePlPick(); render(); },
 plPjNone:()=>{ plf.projs=[]; prunePlPick(); render(); },
 /* 行多选：范围 = 当前筛选结果（与付款通知书页同款语义） */
 plPick:t=>{ const id=t.dataset.id; if(!id) return; if(plPick.has(id)) plPick.delete(id); else plPick.add(id); render(); },
 plPickAll:()=>{ const cur=plVisible(); const hit=cur.filter(p=>plPick.has(p.id)).length;
   if(hit===0){ cur.forEach(p=>plPick.add(p.id)); } else { cur.forEach(p=>plPick.delete(p.id)); } render(); },
 /* ⭐ 删除（逐行 / 批量**共用**）—— §4.3.6 的**两步**：先取**后端影响范围**，用户确认后再删。
    ⚠️ 影响范围**必须来自后端**（`/api/m04/delete-impact`）：它是硬要求、不是装饰；
       取不到就**不删**（宁可不动，也不做「看不见影响范围的删除」）。 */
 plConfirm:async ids=>{ if(!ids.length) return;
    let imp=null;
    try { imp=await API.plDeleteImpact(ids); }
    catch(e){ toast(`⚠️ 取不到「删除影响范围」：${esc(String((e&&e.message)||e))}<br><b>未删除任何数据</b>`,6400); return; }
    plDelIds=ids.slice();
    const impList=(imp.impacts||[]);
    const rows=impList.slice(0,15).map(r=>`<tr><td class="fc">${esc(String(r.row_id))}</td>`
      +`<td class="fc">${esc(String(r.year_month||''))}</td>`
      +`<td>${esc(String(r.result||''))}</td></tr>`).join('');
    modal({title:'删除付款计划行确认',body:`<div class="tip dg" style="margin-bottom:calc(10px * var(--fscale))"><b>⚠️ 将删除 <span class="fc">${ids.length}</span> 行付款计划数据</b>。删除后需重新导入才能恢复。</div>
      ${kvBlock([['删除行数',`<span class="fc">${ids.length} 行</span>`],['影响范围','只影响付款计划表；<b>不影响付款通知书与欠款统计</b>']])}
      <div class="tw" style="max-height:220px"><table class="dt cond"><thead><tr><th>行号</th><th>年月</th><th>审查结果</th></tr></thead><tbody>${rows}</tbody></table></div>
      <div class="mut sm" style="margin-top:calc(6px * var(--fscale))">后端报出 ${impList.length} 行影响 · 涉及表：${esc(String((imp.affected_tables||['plan_row']).join('、')))}</div>`,
      footer:`<button class="btn" data-act="closeModal">取消</button><button class="btn dg" data-act="plDelOk">确认删除</button>`}); },
 /* ⭐ 逐行删除：与批量删除**走同一套**（先取后端影响范围 → 确认 → 删） */
 plDelRow:t=>{ const id=t.dataset.id; if(!id) return; ACT.plConfirm([id]); },
 plDel:()=>{ const ids=[...plPick]; if(!ids.length){ toast('请先勾选要删除的行'); return; } ACT.plConfirm(ids); },
 plDelOk:()=>{ const ids=plDelIds.slice(); plDelIds=[]; closeModal();
    if(!ids.length) return;
    plAct(()=>API.plDelete(ids), `已删除 <b>${ids.length}</b> 行付款计划（只影响付款计划表）`); },
 /* ⭐ `TAIL-69`（2026-09-22）：导入升级为「**选文件 → 解析预览（不写库）→ 确认落库**」——
    预览里先看见**行数 / 项目匹配盘点（未匹配 / 重名）/ 解析提示**，再决定写不写（⛔ 永不静默猜）。
    ⚠️ `plImportPrev` 的 `let` 声明在本文件**顶层**（对象字面量里 ⛔ 不能放 `let` ——
       实测：放里面 = `Unexpected identifier` ⇒ **整支 actions.js 失效**、壳白得只剩 home，
       而离线文本断言全绿（只有真机 / `node --check` 看得见）。 */
 /* ⭐⭐ 2026-09-22（`TAIL-75` `B5c`）：**付款计划的导入收进「数据导入」向导**（通用导入面）——
    原页内弹窗（选月 → 解析预览 → 确认）**已删**，此处只做"跳到向导并预选本域"。
    ⚠️ 切片里的按钮文案（`data-act="plImport"` 那一行）**一个字没动** ⇒ `U1` 零漂移；
       三步纪律（**预览不写库 → 确认才落库**）由向导承接：`impParse → impPreview → impCommit`。
    ⭐ 2026-09-23（`TAIL-75` 余项 · **用户裁定**「只留通用面」）：后端那两条**页内端点**
       （`/api/m04/import/parse|confirm`，以及 2026-09-22 起已软退役的一步式 `/api/m04/import`）
       **同批连件删除**（**都已删**：连同只服务它们的 `TokenRequest`）⇒ 付款计划导入
       **只剩通用面这一条路**（`/api/imp/m04_plan/*`）。
       判据**判词一字未改、只换落点**：`test_plan_import.py` 里那几条搬进 `test_imp_m04_api.py`
       （其中「预览不写库」改由**直接查库**证明）。 */
 plImport:async ()=>{ await impSetDomain('m04_plan'); go('imp'); IMP.step=0; render();
   toast('已打开「<b>数据导入</b>」并选好 <b>付款计划</b>：选文件 → 看列映射 → 预览（不写库）→ 确认落库',8000); },
 /* ⭐ 2026-09-18：**已接通**（`TAIL-35` ＋ `TAIL-27` 批 2）—— 手动行走 JSON 端点 `POST /api/m04/plans`
    （`plan_api_router.py`；与旧 PRG 端点**同一份判定** `plan_manual.manual_row_payload`）。
    ⚠️ 旧服务端页（`POST /m04/row/save` ＋ `render_m04`）已随 `§19` 批 2 删除 ⇒ **壳是唯一入口**；
    判据点 `ACC-PLAN-MANUAL-001` 已搬到 `tests/test_api_m04_manual.py`（端点）与 `test_wired_m04.py`（壳）。 */
 plRowAdd:()=>{ plRowEditId=PL_NEW_ID; plD=plBlank(); render();   toast('已在<b>表尾生成一行草稿</b>（尚未保存）—— 填完点该行「保存」落库、点「取消」丢弃<br>它落库后**与导入行同住一表、同样要被审查**，且**导入不会清理它**（§9.5）',5600); },
 plRowEdit:t=>{ const p=PLs.find(x=>x.id===t.dataset.id); if(!p) return;
   if(!p.manual){ toast('<b>编辑只对「手动行」开放</b> —— 导入行是项目端报来的<b>源数据</b>：要改请<b>重新导入</b>（它在 §4.3.3 唯一的例外口 = 该行「再次匹配」）',6400); return; }
   plRowEditId=p.id;
   plD={ym:p.ym, proj:plProjKey(p.proj), docNo:p.docNo||'', flowAmt:String(p.flowAmt), monthAmt:String(p.monthAmt),
        date:p.date||'', method:p.method||'现汇', remark:p.remark||''};
   render();
   toast(`正在<b>原地编辑</b>手动行 <b>${esc(p.id)}</b> —— 点「保存」落库、点「取消」保持原样`,5200); },
 plRowSave:async ()=>{ const d=plD;
  /* ⭐ **挡重入**（守则 §5.5）：连点两次「保存」= 两次 `POST /api/m04/plans` ⇒ 落两行完全相同的计划行；
     ⚠️ 后端**不会挡** —— 同月完全相同的行是**本业务的合法状态**（§4.3.3：重复由「重复上报」提示、
     不靠自动去重掩盖）⇒ 这一道只能由界面挡（与 `IMP.busy` 同款）。 */
  if(plSaving) return;
  plSaving=true; render();
   /* ⭐ 接线：**判定与落库一律后端**（`plan_manual.manual_row_payload` → `/api/m04/plans`）——
      ⛔ 前端不再复写「年月必填 / 项目必选 / 金额非负」那三道校验（那是**第二份口径**）。
      ⚠️ 校验不过 ⇒ 后端 400 ＋ 原样原因；**草稿与已填内容一律保留**（§4.3.3.1：显式报错、不清空重填）。 */
   const isNew=(plRowEditId===PL_NEW_ID);
   try{
     const r=await API.m04PlanSave({
       row_id: isNew ? '' : String(plRowEditId||''),
       row_ym: String(d.ym||''), project_id: String(d.proj==null?'':d.proj),
       doc_no: String(d.docNo||''),
       flow_amount: String(d.flowAmt==null?'':d.flowAmt),
       planned_amount: String(d.monthAmt==null?'':d.monthAmt),
       pay_date: String(d.date||''), pay_method: String(d.method||''), remark: String(d.remark||''),
     });
     plf.ym=String(d.ym||plf.ym);     /* 保存后保证看得见（切到该行年月）；⚠️「项目」筛选一律不动 */
     plRowEditId=''; plD={}; plSaving=false;
     await reloadPlans();
     toast(`${esc(r.message||'已保存')} —— 已切到 <b>${esc(plf.ym)}</b>；它<b>与导入行同样参与审查</b>（§4.3.4），合计与 KPI 随之重算`,7600);
   }catch(e){
     plSaving=false;                /* 解除挡重入（草稿还在 ⇒ 改完可以再存） */
     await reloadPlans();          /* 回后端真实状态；⚠️ **`plD` 不动** ⇒ 草稿行与已填内容仍在（§4.3.3.1） */
     toast(`<b>没能保存</b>：${esc(String((e&&e.message)||e))}<br><span class="mut sm">已填内容保留，改完再存（§4.3.3.1）</span>`,9000);
   } },
 /* （旧「导入付款计划 Excel」弹窗 ＋ `plImportOk`（造演示行）已撤 —— 见上方 `plImport` 的诚实提示） */
 /* —— MOD-04 · 手动行 = **表内增行模式**（§4.3.3.1 · 2026-09-16 用户口述新增 + 同日追认细节 6 项）——
    用途：项目端报来的计划**漏项 / 临时补报**时提供**不依赖 Excel 的补录入口**。
    ⚠️ 落库后**与导入行同住一表、走同一条审查链路**（判定一律 `plRev()` 实时派生、不看来源）；
       **导入只清并重写自动行 ⇒ 手动行不被触碰**（§9.5）。 */
 /* 草稿层写入口（表单元素走 `change` ⇒ 委托层直呼 `ACT[a]`，⛔ 没有名单）
    ⚠️ 本动作**不重绘** —— 免得每改一格就把焦点丢掉（与 `ntRowSet` 同款，只有需要联动时才重绘） */
 plRowSet:t=>{ const k=t.dataset.k; if(!k) return; plD[k]=String(t.value==null?'':t.value); },
 plRowCancel:()=>{ const was=(plRowEditId&&plRowEditId!==PL_NEW_ID)?plRowEditId:'';
   plRowEditId=''; plD={}; render();
   toast(was?`已放弃对 <b>${esc(was)}</b> 的修改 —— 该行<b>保持原样</b>（草稿未落库）`:'已取消新增 —— 草稿行丢弃，<b>未写入任何数据</b>'); },
 /* 「编辑」= 该行**原地变草稿行**（不新增行；文案与校验与新增共用 `plRowSave`）。
    ⚠️ **只有手动行可编辑**：对导入行请求编辑时**显式说明原因**（不静默忽略、不当作新增 —— §4.3.3.1） */
 /* 保存（新增 / 编辑**共用**）：年月必填且月度形态 → 项目必选 → 金额校验（非法 / 负数）
    ⚠️ 校验不过 ⇒ **保留草稿行与已填内容**（§4.3.3.1：显式报错 + 不清空重填） */
 force:t=>{ const p=PLs.find(x=>x.id===t.dataset.id); const rv=plRev(p,PLs);
   modal({title:`强制通过 · ${rv}`,body:`<div class="tip wn" style="margin-bottom:calc(10px * var(--fscale))">审查结果 = <b>${rv}</b>。系统<b>只提示、不拦截</b>；强制通过<b>必须写备注</b>（留痕），发现问题由用户<b>追问项目</b>。<br><span class="mut sm">强制通过后如需撤回，可在该行点「取消强制通过」回到「未处理」态。</span></div>
     ${kvBlock([['项目',`<span style="font-size:calc(11.5px * var(--fscale))">${dispCell(p.proj)}</span>`],['单据号',p.docNo||'<span class="tag t-dg">未填</span>'],['i8 流程金额',M(p.flowAmt)],['本月预付款金额',M(p.monthAmt)]])}
     <div class="fld"><label>强制通过备注 <b>*</b></label><input class="inp" id="fRemark" placeholder="例：已向项目核实，金额无误"></div>`,
     footer:`<button class="btn" data-act="closeModal">取消</button><button class="btn pri" data-act="forceOk" data-id="${p.id}">强制通过</button>`}); },
 /* ⭐ 已接后端：`POST /api/m04/plans/{id}/force` —— **空备注由后端拒**（§4.3.4）。
    ⚠️ 前端那一道只为**即时反馈**；真正把关在后端（口径只许一个出口）。 */
 forceOk:t=>{ const rs=$('#fRemark').value.trim(); if(!rs) return toast('<b>强制通过必须写备注</b>（§4.3.4）');
    const p=PLs.find(x=>x.id===t.dataset.id); if(!p) return;
    closeModal();
    plAct(()=>API.plForce(p.id, rs), `已强制通过 <b>${p.id}</b> 并留痕（备注：${esc(rs)}）`); },
 /* 取消强制通过：回到「未处理」态。**不弹确认、不产生留痕**（取消 = 撤回一次人工放行，不产生新事实） */
 /* ⭐ 已接后端：`POST /api/m04/plans/{id}/force-cancel` —— 回到原判定、备注清空（§4.3.4） */
 unforce:t=>{ const p=PLs.find(x=>x.id===t.dataset.id); if(!p||!p.forced) return;
    plAct(()=>API.plForceCancel(p.id), ()=>{
      const np=PLs.find(x=>x.id===p.id)||p;
      return `已取消 <b>${p.id}</b> 的强制通过 —— 回到「未处理」，审查结果仍为 <b>${plRev(np)}</b>，可重新处理`;
    }); },
 /* 行内可改列：付款时间 / 付款方式 / 备注 / （仅未匹配行的）单据号
    ⚠️ 改动**立刻写回数据**（不是草稿层）—— 全量重渲染后 value 仍由数据生成，所以不会冲掉；
       持久性口径：**落库 + 不被导入覆盖 + 不留痕**（与「统计两金额」那类旁路字段同族，但**不留痕**）。 */
 /* ⭐ 已接后端：`POST /api/m04/plans/{id}/cell` —— §4.3.3 **立刻落库 · 不被导入覆盖 · 不留痕**。
    ⚠️ 可改范围**由后端判**（单据号只对「未匹配」行开放）⇒ 前端不再自己把关。 */
 plCell:t=>{ const p=PLs.find(x=>x.id===t.dataset.id); if(!p) return;
    const f=t.dataset.f, F={docNo:'单据号',date:'付款时间',method:'付款方式',remark:'备注'};
    if(!F[f]) return;
    const v=String(t.value==null?'':t.value).trim();
    plAct(()=>API.plCell(p.id, PL_COL_API[f], v),
      `<b>${p.id}</b> 的${F[f]}已改为 <b>${esc(v)||'（空）'}</b>${f==='docNo'?' —— 点该行「再次匹配」重新比对 i8 通知书':''}`); },
 /* 再次匹配：审查结果是实时派生的，按当前单据号重跑一次即可（并给出新的审查结果） */
 /* ⭐ 已接后端：`POST /api/m04/plans/{id}/re-match` —— 重跑**同一个审查引擎**（§4.3.3） */
 plRematch:t=>{ const p=PLs.find(x=>x.id===t.dataset.id); if(!p) return;
    const code=esc(String(p.docNo||'').trim())||'（空）';
    plAct(()=>API.plRematch(p.id), ()=>{
      const rv=plRev(PLs.find(x=>x.id===p.id)||p);
      return `<b>${p.id}</b> 已按单据号 <b>${code}</b> 重新比对 → 审查结果：<b>${rv}</b>${rv==='完全匹配'?'（该行转入「无需处理」）':''}`;
    }); },
 /* 逐行删除：与批量删除同款确认（删除前列影响范围）；删掉的 id 同时从勾选集合里移除 */
 /* 按付款计划勾选：入口在付款通知书页（勾选与付款在同一处）。**2026-09-12 定案**：
   · **只在付款计划生效窗口（当月 10 号 → 月末，§4.3.2）内可点**；窗口外按钮先禁用（R14）
   · 月份来源 = **北京时间当月**（不可自选）
   · 计划行指向的通知书**可能落在别的月份**（当月计划里混着上月/更早的通知书）
     ⇒ 做法：把**视图参数**（单据年月 / 分类 / 审批状态 / 付款状态）放宽到「全部月份 + 未付清」，
       使当月计划命中的通知书**全部落在当前筛选结果内**，再一次性勾选 ——
       这样「只勾当前筛选结果内的行」（§4.3.5）**依然成立**，且勾中的行都能在页面上看到、逐步核对。
   · ⚠️ **「项目」筛选一律不动**（用户口径 2026-09-12）—— 它是用户表达的业务范围，
       勾选范围**尊重已选项目**；因此被项目筛选挡掉的行会跳过并在提示里报数。
   · 剔除行 / **撤单行一律不勾**（判据 = 付款候选 `ntPayCand`；撤单的单据 i8 已删，不许再产生付款）；未命中的计划行在提示里说明。 */
 planPick:()=>{ const win=plWin();
   if(!win.open){ toast(`<b>付款计划 ${win.from} 号起生效、月末截止</b>—— 今天是 <b>${SYS_TODAY}</b>，还没到付款窗口，暂不可勾选`,4800); return; }
   const ym=win.ym;
   /* ⚠️ 只放宽「视图参数」；**不碰 fNt.projs**（项目筛选是用户选定的业务范围） */
   fNt.month='全部'; fNt.cat='全部'; fNt.astat='全部'; fNt.stat='未付清'; pjClose('pj'); mp.open=null;
   pickSet.clear();
   const plan=PLs.filter(p=>p.ym===ym);
   let hit=0, miss=0;
   plan.forEach(p=>{ const c=String(p.docNo||'').trim();
     const n=c?NO.find(x=>x.code===c&&ntPayCand(x)):null;
     if(!n){ miss++; return; }
     hit++; pickSet.add(n.id); });
   const before=pickSet.size;
   VIEW='m03'; prunePick(); render();
   const cut=before-pickSet.size;                 /* 被「项目」筛选等挡掉、未能勾上的条数 */
   const months={}; [...pickSet].forEach(i=>{ const m=NO.find(n=>n.id===i).date.slice(0,7); months[m]=(months[m]||0)+1; });
   const other=Object.keys(months).filter(m=>m!==ym).sort();
   const cx=other.reduce((a,m)=>a+months[m],0);
   toast(`已按 <b>${ym}</b> 付款计划勾选 <b>${pickSet.size}</b> 条（计划命中 <b>${hit}</b> 条${miss?`，另 <b>${miss}</b> 行无单据号 / 编号查不到`:''}${cut?`；<b>${cut}</b> 条不在你选定的「项目」范围内，已跳过`:''}${cx?`；含<b>跨月 ${cx}</b> 条（${other.map(m=>`${m} ×${months[m]}`).join('、')}）`:''}）<br><b>「项目」筛选未被改动</b>；已放宽「单据年月 / 分类 / 审批状态」并把付款状态置为「未付清」，便于逐条核对 —— <b>实际付什么、付多少由用户自行修改</b>`,7000); },

 /* —— MOD-03 · 手动新增 / 编辑付款通知书 = **表内增行模式**（2026-09-13 用户口径）——
    用途不变：付「期初占位行」的款 —— 那笔钱没有 i8 单据，只能手工补一行。
    ⭐ 2026-09-13 用户拍板：「手动新增 / 编辑」**弹窗取消**，改为**表内增行**（甲案：草稿行不落 `NO`）。
    草稿层仍是 `naD`（键与 `NT_COLS` 同名，另加 `pid`）⇒ "改一格不会冲掉别的格"这条老教训照旧成立。 */
 ntRowAdd:()=>{ naEditId=NT_NEW_ID; naD=ntBlank(); ntReveal(); render();
   toast('已在表尾生成<b>一行草稿</b>（尚未保存）—— 填完点该行「保存」落库、点「取消」丢弃<br>已放宽「单据年月 / 分类 / 审批状态 / 付款状态」以便看见草稿行；<b>「项目」筛选未改动</b>',5600); },
 /* 草稿层写入口：输入即记录（表单元素走 `change` ⇒ 委托层直呼，⛔ 没有名单）；
    ⚠️ 只有「分类」变了需要重绘（它决定「集采实际供应商」是否可填）—— 其余字段不重绘，
       免得每改一格就把焦点丢掉。 */
 ntRowSet:t=>{ const k=t.dataset.k, v=t.value;
   /* 「付款项目」的候选值是**仓库名**（§2.7.4）⇒ 落草稿前解析成**档案 id**（§9.8-5 按 id 不按名）。
      宽容输入：直接给 id 也认（先按 id 找，再按 仓库名 / 展示名 / 全名 解析）。 */
   naD[k]=(k==='pid')?((PJs.find(x=>x.id===v)||pjRowOf(v)||{}).id||''):v;
   if(k==='cat') render(); },
 ntRowCancel:()=>{ const was=(naEditId&&naEditId!==NT_NEW_ID)?naEditId:''; naEditId=''; naD={}; render();
   toast(was?`已放弃对 <b>${esc(was)}</b> 的修改 —— 该行<b>保持原样</b>（草稿未落库）`:'已取消新增 —— 草稿行丢弃，<b>未写入任何数据</b>'); },
 /* 「编辑」= 该行**原地变草稿行**（不新增行；文案/校验与新增共用 `ntRowSave`） */
 ntEdit:t=>{ const n=NO.find(x=>x.id===t.dataset.id); if(!n||!n.manual) return;
   naEditId=n.id;
   naD={date:n.date, code:n.code, pid:((ownOf(n)||{}).id)||'',
     doc:n.doc, biz:n.biz, recv:n.recv, cat:n.cat, astat:n.astat,
     approve:String(n.approve), sp:String(n.sp), sup:n.sup||''};
   ntReveal(); render();
   toast(`正在<b>原地编辑</b>手动行 <b>${esc(n.id)}</b> —— 该行已变为草稿态；点「保存」落库、点「取消」保持原样`,5200); },
 /* 保存 = 原弹窗的「确认新增 / 保存修改」——校验链**一字未改**（项目必选 → badMoney → overCap 拦截并保留原值） */
 ntRowSave:()=>{ const pj=PJs.find(p=>p.id===naD.pid);
   if(!pj){ toast('<b>请先选「付款项目」</b>：候选 = 全部已建档项目（含归档；壳除外，§六-9）'); return; }
   const ap=naNum(naD.approve), sp=naNum(naD.sp);
   if(badMoney(ap)){ toast(badMoneyMsg('审批金额')); return; }
   if(badMoney(sp)){ toast(badMoneyMsg('统计付款金额')); return; }
   if(overCap(sp,ap)){ toast(`<b>统计付款金额超上限</b>：全站口径「按发票走、只能少不能多」⇒ 上限 = 审批金额 <b>${M(ap)}</b>。<br>要付 <b>${M(sp)}</b> 就把<b>审批金额</b>也填到 <b>${M(sp)}</b>（手动行没有 i8 结算、审批金额由你定），已保留原值`,7000); return; }
   const cat=naD.cat||'辅材';
   const dt=/^\d{4}-\d{2}-\d{2}$/.test(String(naD.date||''))?naD.date:naDefDate();
   const f={date:dt, code:String(naD.code||'').trim(), doc:String(naD.doc||'').trim(), biz:String(naD.biz||'').trim(),
     recv:String(naD.recv||'').trim(), cat, astat:naD.astat||'已批', approve:ap, sp,
     sup:(cat==='集采')?String(naD.sup||'').trim():''};
   /* ⭐ 2026-09-19 接线（`§19` 批 4 · **S2a**）：手动行**新增 / 编辑一律落库走后端**
      `POST /api/m03/actions/manual-save` —— 校验（录入人取当前登录用户 · 统计结算恒 0 ·
      全站「统计两金额 ≤ 审批金额」· 是不是手动行…）**只在后端一处**（`manual_row_payload` ＋ `assert_manual_editable`）。
      ⛔ 前端不再本地改对象 / 本地塞数组冒充落库（原先就是这样，刷新即丢）。
      回执里的中文说明**原样给用户**；失败 ⇒ `ok=False` ⇒ 提示并把**草稿行保留**（R14③，不清空已填内容）。 */
   if(ntSaving) return;
  ntSaving=true; render();
  const body={ row_id:(naEditId&&naEditId!==NT_NEW_ID)?String(naEditId):'',
     doc_date:f.date, bill_no:f.code, bill_name:f.doc, biz_type:f.biz, payee:f.recv,
     /* ⚠️ 分类：下拉框的值是**中文标签**（`ENUMS.cat`），而服务端只认**键** ⇒ 必须映射
       （照 `setCategory` 的既有做法 `CAT_API`）—— 不映射会被后端按「分类不合法」拒掉。 */
    category:CAT_API[f.cat]||f.cat, amount_approved:String(naD.approve||''), stat_paid:String(naD.sp||''),
     ownership_id:String(pj.id) };
   API.manualSave(body)
     /* ⚠️⚠️ 2026-09-20 补：**先判 `ok` 再清草稿**。原先不管成败都先 `naEditId=''; naD={}`
        ⇒ 后端拒了（200 ＋ `ok:false`）也把**用户刚填的一整行草稿丢掉**了
        ⇒ 人只会看到"点了保存、填的东西没了"，还得重填一遍。 */
     .then(r=>{ if(!r || r.ok === false){
         ntSaving=false;
         toast(`<b>保存失败</b>：${esc((r && r.message) || '后端未返回原因')}`
           + `<br>草稿行已保留，改完再点「保存」`, 6000);
         return reloadNotices(); }
       naEditId=''; naD={}; ntSaving=false;
       /* 新增后**保证看得见**（同「按付款计划勾选」的做法）：切到该行年月 + 放宽三档筛选；「项目」筛选一律不动 */
       fNt.month=String(f.date).slice(0,7); fNt.cat='全部'; fNt.astat='全部'; fNt.stat='全部'; prunePick();
       toast(r.message,5200); return reloadNotices(); })
     .catch(e=>{ ntSaving=false; toast(`<b>保存失败</b>：${esc(e.message||e)}<br>草稿行已保留，改完再点「保存」`,6000); }); },
 /* 手动行的「审批金额」表内可改（i8 抓取行该列仍只读） */
 editApprove:t=>{ const n=NO.find(x=>x.id===t.dataset.id); if(!n||!n.manual) return;
   const v=naNum(t.value);
   if(badMoney(v)){ toast(badMoneyMsg('审批金额')+` ${M(n.approve)}`); render(); return; }
   if(overCap(n.sp,v)){ toast(`<b>审批金额不能低于「统计付款金额」</b>：全站口径「统计两金额 ≤ 审批金额」⇒ 至少 <b>${M(n.sp)}</b>（先把统计付款金额调小，或把审批金额填大），已保留原值 ${M(n.approve)}`,6000); render(); return; }
   n.approve=v; render();
   toast(`手动行 <b>${n.id}</b> 审批金额已改为 <b>${M(v)}</b> —— 「付款金额（本次应付）」与付款状态已实时重判`); },
 /* ⭐ 2026-09-19 接线（`§19` 批 4 · **S2b**）：**删除前的影响范围由后端给**（§7.2 / §9.4 是硬要求）——
    项目 / 统计付款金额 / 已付金额 / 「欠款回增」那句全由 `/api/m03/actions/manual-delete-impact` 出，
    ⛔ 前端不再自己拼这段文字（原先正是本地拼的 ✗）。⚠️ i8 抓取行连"影响范围"都不给看（§4.2.7）。 */
 ntDel:t=>{ const n=NO.find(x=>x.id===t.dataset.id); if(!n||!n.manual) return;
  const id=Number(n.id);
  API.manualDeleteImpact({notice_id:id})
    .then(imp=>{ if(!imp.ok) return toast(imp.message);
      modal({title:'删除确认 · 手动新增付款通知书',
        body:`<div class="tip dg" style="margin-bottom:calc(10px * var(--fscale))"><b>⚠️ 删除前先看清下面这些影响</b>（关联数据 · 统计影响）—— §7.2 / §9.4。<br>${imp.message}</div>
    ${kvBlock([['单据',`<span class="fc">${esc(imp.label)}</span>`],['项目',`<span style="font-size:calc(11.5px * var(--fscale))">${esc(imp.project_name)}</span>`],['单据日期',`<span class="fc">${esc(imp.doc_date)}</span>`],['统计结算金额',`<span class="fc">${esc(imp.stat_settle)}</span>（恒 0）`],['统计付款金额',`<span class="fc">${esc(imp.stat_paid)}</span>`],['已付金额（流水）',`<span class="fc">${esc(imp.amount_paid)}</span>`]])}
    <div class="tip" style="margin:0">${imp.effects.map(x=>`· ${esc(x)}`).join('<br>')}</div>`,
        footer:`<button class="btn" data-act="closeModal">取消</button><button class="btn dg" data-act="ntDelOk" data-id="${id}">确认删除</button>`}); })
    .catch(e=>toast(`<b>取删除影响范围失败</b>：${esc(e.message||e)}`)); },
 /* ⭐ 删除**落库走后端**（S2b）：⛔ 前端不再本地 `splice` 冒充删除 */
 ntDelOk:t=>{ const id=Number(t.dataset.id);
  API.manualDelete({notice_id:id})
    .then(r=>{ if(!r.ok) return toast(r.message);
      pickSet.delete(id); if(String(naEditId)===String(id)) naEditId='';
      closeModal(); toast(r.message); return reloadNotices(); })
    .catch(e=>toast(`<b>删除失败</b>：${esc(e.message||e)}`)); },

 /* ⭐ 撤销付款（2026-09-14 新增）：**付款通知书页的就近入口** —— 把 §4.4.5 的能力搬到用户发现问题的位置。
   ⚠️ **不新开口径**：撤销逻辑与「付款流水与欠款统计」页的 `revDlg` / `revOk` **完全同一套**
      （原因必填 + 留痕 + 已付金额回退 + 按审批金额重判）⇒ 这里只负责"找到该撤哪条 / 分流到哪"。
   ① 该行**只有 1 条生效流水** ⇒ 直接开撤销弹窗（省一次跳转；复用 `revDlg`）。
   ② 该行**有多条生效流水** ⇒ 跳「付款流水与欠款统计」页并**只筛出这一单**（`ntFlows` 落筛选）——
      不做"一次撤全部"（撤销是**逐条**留痕的动作，批量撤会让每条的原因被糊成一个）。
   ③ 该行**没有生效流水**（理论上不会走到，按钮只在 `paidOf>0` 时出现）⇒ 提示并返回。 */
 ntRevoke:t=>{ const n=NO.find(x=>x.id===t.dataset.id); if(!n) return;
   const live=FLs.filter(f=>f.nid===n.id&&!f.voided);
   if(!live.length){ toast('这行通知书当前<b>没有生效的付款流水</b> —— 无需撤销'); render(); return; }
   if(live.length===1) return ACT.revDlg({ dataset:{fid:live[0].id}, tagName:'BUTTON' });
   /* 多条：跳到流水页并只筛这一单（流水页有"关键词"筛选，用它把单据编码填进去） */
   flf.ym=fNt.month; flf.projs=[]; flf.method='全部'; flf.state='全部'; flf.q=n.code||'';
   pjClose('flPj');   /* 面板收起（变量名是 `pjIsOpen('flPj')`，交互路径与 `rollback` 都用它） */
   go('m05');   /* `go` 内部已 render + 滚动到顶；离开 m03 它会自动 clear pickSet */
   toast(`该行有 <b>${live.length}</b> 条生效流水 —— 已跳到「付款流水与欠款统计」并筛出 <b>${esc(n.code||n.id)}</b><br>请逐条点「撤销」并分别填写原因（撤销是<b>逐条留痕</b>的动作，不做一次撤全部）`,6800); },

 /* ⭐ 查看关联（2026-09-14 新增）：**纯只读** —— 从通知书反查"这笔钱付到哪去了"。
   内容两块：① 集采合同关联（`jcRefOf`，写的是集采合同付款子表那份记录）；
             ② 已登记付款流水（生效 + 已撤销都列，撤销的显示原因 —— 这才是"去向"的完整视图）。
   ⚠️ 零口径风险：不写任何数据、不改任何状态；两个弹窗按钮一律「关闭」。 */
 ntTrace:t=>{ const n=NO.find(x=>x.id===t.dataset.id); if(!n) return;
   const j=jcRefOf(n.id);
   const flows=FLs.filter(f=>f.nid===n.id);
   const live=flows.filter(f=>!f.voided), voided=flows.filter(f=>f.voided);
   const amtLive=N2(live.reduce((a,f)=>a+f.amt,0));
   const jcRow=j?`${esc(j.id)} · ${esc(j.material||'')} · ${esc(j.supplier||'')} · 欠款 <span class="fc">${M(jcDebt(j))}</span>`:'<span class="mut">未关联集采合同（仅「集采」分类的行可关联）</span>';
   const flRow=flows.length
     ? `<div class="tw" style="max-height:34vh">${TBL({cls:'cond',head:'<th>流水号</th><th>付款日期</th><th>金额</th><th>方式</th><th>操作人</th><th>状态</th>',
       rows:flows.map(f=>`<tr class="${f.voided?'ex':''}"><td class="fc">${f.id}</td><td class="now">${f.date}</td><td class="num">${M(f.amt)}</td><td>${enumTag('payMethod',f.method)}</td><td class="sm">${esc(f.op)}</td><td>${f.voided?enumTag('flowState','已撤销')+' <span class="mut sm">'+esc(f.reason)+'</span>':enumTag('flowState','生效')}</td></tr>`)})}</div>`
     : '<div class="tip" style="margin:0">这行通知书<b>还没有付款流水</b> —— 尚未付款（或流水已全被撤销）。</div>';
   modal({title:`查看关联 · ${n.code||n.id}`,body:
     `<div class="tip" style="margin-bottom:calc(10px * var(--fscale))"><b>只读视图</b> —— 看这行通知书的<b>关联与去向</b>：关联了哪张集采合同、已产生哪些付款流水。<b>不改任何数据</b>。</div>
      ${kvBlock([['单据',`<span class="fc">${esc(n.id)} · ${esc(n.code||'（未填编码）')}</span>`],
        ['付款项目',`<span style="font-size:calc(11.5px * var(--fscale))">${esc(n.proj)}</span>`],
        ['单据名称',`<span style="font-size:calc(11.5px * var(--fscale))">${esc(n.doc||'—')}</span>`],
        ['分类 / 审批状态',`${ntArchTag(n)||esc(n.cat)} ｜ ${astatTag(n.astat)}`],
        ['集采实际供应商',n.sup?`<span class="fc">${esc(n.sup)}</span>`+(supHas(n)?' '+tag('自动匹配 · 待确认','wn'):''):'<span class="mut">—</span>'],
        ['集采合同关联',jcRow],
        ['审批金额',`<span class="fc">${M(n.approve)}</span>`],
        ['已付金额（生效流水合计）',`<span class="fc">${M(amtLive)}</span>${voided.length?`<span class="mut sm">（另有 ${voided.length} 条已撤销，不计入）</span>`:''}`],
        ['付款状态',stTag(statOf(n))]])}
      <div style="margin-top:calc(4px * var(--fscale))"><b>付款流水</b>（生效 ${live.length} 条${voided.length?` · 已撤销 ${voided.length} 条`:''}）</div>
      <div style="margin-top:calc(6px * var(--fscale))">${flRow}</div>`,
     footer:`<button class="btn" data-act="closeModal">关闭</button>`}); },

 /* —— MOD-05 —— */
 /* data-sc = 从哪一栏点进来的 —— 作为「分类」的预选值（仍可在展开区里改）
    ⭐ 2026-09-13 增行模式（用户拍板 C-1 / C-7）：**「录入期初占位行」弹窗取消** ⇒
       改为**栏内展开区**，且整条展开区渲染在 `.tw` **之外**（表格上方的独立条带）。 */
 addLg:t=>{ const sc=t&&t.dataset?t.dataset.sc:''; if(sc) lgCat=sc;
  /* 项目默认 = **欠款台账当前选中的项目**；截止年月默认 = **该项目「该分类」已有数据的最早月 − 1**（2026-09-13 口径）。
     ⚠️ 只在「进入增行态」时算一次；展开区内重绘（选截止年月 / 改分类）**不重算** —— 否则会把用户选的值冲掉。
        唯一例外：**改「分类」**要重算 —— 辅材 / 机械 的最早数据月各算各的，不重算就会给出错的默认值。 */
  lgPjName=lgDefPjName(); lgCut=lgCutFor(lgPjName,lgCat);
  lgD.s='0.00'; lgD.p='0.00'; lgD.r=LG_R_DEF;                 /* 新开一次 → 草稿复位（原地改字段） */
  lgOn=true; pjClose('lgPj'); render();
  toast(`已在「<b>${esc(lgCat)}</b>」栏上方展开期初占位行录入区 —— 填完点「保存」落库、点「取消」丢弃（<b>草稿不入库</b>）`,5400); },
 lgCancel:()=>{ lgOn=false; pjClose('lgPj'); render();
  toast('已取消期初占位行录入 —— <b>未写入任何数据</b>'); },
 /* 草稿层写入口：输入立即记下，展开区重绘时不丢 */
 lgS:t=>{ lgD.s=String((t&&t.value)!=null?t.value:''); },
 lgP:t=>{ lgD.p=String((t&&t.value)!=null?t.value:''); },
 lgR:t=>{ lgD.r=String((t&&t.value)!=null?t.value:''); },
 lgCat:t=>{ lgCat=String((t&&t.value)||lgCat);
  lgCut=lgCutFor(lgPjName,lgCat); render(); },   /* 改「分类」→ 截止年月按新分类重算（**唯一会重算的入口**） */
 /* —— 付款流水的筛选（R4：改动即时生效、不设「应用」按钮） ——
    ⚠️ 复位一律【原地改字段】，不要 `flf={...}` 重新赋值（同 `fJc` / `BIGVAL` 的教训）
    ⚠️ ⭐ 「付款项目」自 2026-09-13 起是**共用面板（多选）** ⇒ 本动作**不再读 `#flPj`**（该控件已不存在），
       只联动「实际付款方式 / 状态」两个下拉；项目那一路走 `flPjPick` / `flPjAll` / `flPjNone`。 */
 flFilter:()=>{ const b=$('#flMethod'), c=$('#flState');
  flf.method=(b&&b.value)||'全部'; flf.state=(c&&c.value)||'全部'; render(); },
 /* —— 付款流水「付款项目」共用面板（能力由调用点声明：**多选**） —— */
 flPjToggle:()=>{ pjToggle('flPj'); render(); },
 flPjPick:t=>{ const v=(t&&t.dataset&&t.dataset.pj)||''; if(!v) return;
  const i=flf.projs.indexOf(v); if(i>=0) flf.projs.splice(i,1); else flf.projs.push(v); render(); },
 flPjAll:()=>{ const all=flProjs(); flf.projs.length=0; all.forEach(v=>flf.projs.push(v)); render(); },
 flPjNone:()=>{ flf.projs.length=0; render(); },
 /* ⭐ 关键词**只在这一个按钮里生效**（输入框不挂 data-act ⇒ 走不到委托层）—— 别的动作不会带着它去搜 */
 flSearch:()=>{ const i=$('#flQ'); flf.q=String((i&&i.value)||'').trim(); render();
  toast(flf.q?`付款流水已按关键词 <b>${esc(flf.q)}</b> 搜索`:'已清空关键词'); },
 flReset:()=>{ flf.ym=bjMonth(); flf.projs.length=0; flf.method='全部'; flf.state='全部'; flf.q=''; pjClose('flPj'); render();
  toast('付款流水筛选已重置（年月回到默认「当月」，§9.2）'); },
 /* —— 付款统计（§4.5「付款」侧）—— 粒度切换 · 点项目条联动下方流水 —— */
 pstGran:t=>{ pst.gran=(t&&t.dataset&&t.dataset.g)||'周'; pst.ym=''; mp.open=null; render(); },   /* 换粒度 → 桶回到该粒度下"最新有数据"的那个（兜底也随默认值走「周」） */
 pstPj:t=>{ const k=(t&&t.dataset&&t.dataset.pj)||''; if(!k) return;
  /* 联动 = 把该项目**并进 / 移出**「付款流水」的「付款项目」**多选**（语义不变：再点一次 = 取消） */
  const i=flf.projs.indexOf(k); if(i>=0) flf.projs.splice(i,1); else flf.projs.push(k); render();
  toast(i>=0?`付款统计 → 下方「付款流水」已取消 <b>${esc(pjLabel(k))}</b> 的筛选`:`付款统计 → 下方「付款流水」已加选 <b>${esc(pjLabel(k))}</b>`); },
 /* 「项目」共用面板（**单选** —— 能力由调用点声明，与 `MOD-09` / 台账主选择器同款：点一下即切换并收起） */
 lgPjToggle:()=>{ pjToggle('lgPj'); render(); },
 lgPjPick:t=>{ const v=(t&&t.dataset&&t.dataset.pj)||''; if(!v) return;
  lgPjName=v; pjClose('lgPj'); render();
  toast(`期初占位行的项目已切到 <b>${esc(pjLabel(v))}</b>（截止年月仍按当前「分类」单独算）`); },
 /* 保存 = 原弹窗的「保存」——**只读草稿层**，不再从 DOM 取值（增行模式：没有弹窗可读） */
 /* ⭐ 已接后端：`POST /m05/opening`（PRG 表单端点 · 同一「口径 + 项目 + 截止年月」重复录入 = **覆盖**）
    ⚠️ 草稿层（`lgD`）的取数方式不变，只是**落库不再由前端 push**。 */
 addLgOk:()=>{ const pj=lgPjName; if(!pj){ toast('<b>请先选「项目」</b>（点展开区里的「项目」按钮）'); return; }
    const row=pjRowOf(pj);
    if(!row||!row.id){ toast('<b>项目没对上档案</b>（请重选）—— 未写入任何数据'); return; }
    m05Act(()=>API.postForm('/m05/opening', {
        category: CAT_API[lgCat] || lgCat, project_id: row.id,
        cutoff_ym: lgCut, settle_amount: String(lgD.s||''), paid_amount: String(lgD.p||''),
        remark: String(lgD.r||''), end_ym: '',
      }), ()=>{ ledProj=pj; return `期初占位行已录入（<b>${lgCat}</b> · ${esc(ledCutLabel(lgCut))}）`
                 + `，台账已切到 <b>${esc(pjLabel(ledCur()))}</b>，欠款与台账已由后端重算`; }); },
 /* 删除前先看清影响范围（§7.2 / §9.4）：期初属「**用户自录、随时可重录**」那一档 ⇒ **真删**
   （§9.4 的 2026-09-20 定案：**按「删了能不能凭源数据复原」分**）。
   ⚠️ 2026-09-29 `A6` 订正：这里原写「核心业务数据『软删留痕』」—— 与后端 `repo.delete_opening`（就是 `s.delete`）**相反**，也与 §9.4 定案相反（行里根本没有留痕字段）。 */
 /* ⭐⭐ 2026-09-28 修「点了删除没反应」（用户走查报障 · 守则 §5.5「看着能点必须符合预期或给明确反馈」）：
    老写法 = `LGs.find(x=>x.id===t.dataset.id)` ⇒ **三个坑叠一起必失败**：
      ① `LGs` 的 id 曾是**假值 `''`**（`core.js::adaptOpening` 写死 —— 因为 `/api/m05/debt` 那时不返回 id）；
      ② `t.dataset.id` **恒是字符串**，而 `x.id` 是数字 ⇒ `===` 恒 false；
      ③ 找不到就 `return` ⇒ **静默**，用户只看到"点了没反应"。
    新写法：① 优先在**台账真源**里找（按钮就在台账行上，数据同源）② 回退 `LGs`（`String()` 归一）
    ③ ⛔ **两处都没有 ⇒ 必须给可见反馈**（"点了没反应"就是本条的老毛病）。 */
 delLg:t=>{ const id=String((t&&t.dataset&&t.dataset.id)||'');
   if(!id) return toast('这一行没有 id（界面数据异常）—— 请刷新页面后重试');
   let it=null;
   for(const sd of ((M05.ledger||{}).sides||[])){
     const r=(sd.rows||[]).find(x=>x.is_opening&&String(sd.opening_id)===id);
     if(r){ it={id, proj:pjLabel(ledCur()), settle:numOr0(r.other_expense), paid:numOr0(r.payment)}; break; }
   }
   if(!it){ const l=LGs.find(x=>String(x.id)===id);
     if(l) it={id, proj:l.proj, settle:numOr0(l.settle), paid:numOr0(l.paid)}; }
   if(!it) return toast(`没找到这条期初占位行（id=${esc(id)}）—— 它可能已被删除，<b>请刷新页面</b>再试`, 7000);
   const dd=N2(it.settle-it.paid);
   modal({title:'删除确认 · 期初占位行',body:`<div class="tip dg" style="margin-bottom:calc(10px * var(--fscale))"><b>⚠️ 删除前先看清下面这些影响</b>（关联数据 · 统计影响）—— §7.2 / §9.4。</div>
     ${kvBlock([['项目',`<span style="font-size:calc(11.5px * var(--fscale))">${esc(it.proj)}</span>`],['统计结算金额',`<span class="fc">${M(it.settle)}</span>`],['统计付款金额',`<span class="fc">${M(it.paid)}</span>`],['该行欠款',`<span class="fc">${M(dd)}</span>`]])}
     <div class="tip" style="margin:0">删除后：<b>期初占位欠款 ${M(dd)} → 0</b>，<b>欠款合计</b>同步重算；⚠️ 这一行会被<b>真的删掉、删了不能恢复</b>（需要时随时可以<b>重新录入</b>）—— 期初属「你自己录、随时可重录」那一档（§9.4）。</div>`,
     footer:`<button class="btn" data-act="closeModal">取消</button><button class="btn dg" data-act="delLgOk" data-id="${it.id}">确认删除</button>`}); },
 /* ⭐ 已接后端：`POST /m05/opening/delete`（**真删** ＋ 统计重算由后端做 —— `mod05_flow.repository.delete_opening` 就是 `s.delete(row)`；
   ⚠️ 2026-09-29 订正：原写「软删留痕」与后端相反） */
 delLgOk:t=>{ const id=t.dataset.id; if(!id) return;
    closeModal();
    m05Act(()=>API.postForm('/m05/opening/delete', { opening_id:id, project_id:'', end_ym:'' }),
      '期初占位行已删除（删了不能恢复、需要时随时可以重新录入），欠款与台账已由后端重算'); },

  /* —— MOD-01 —— */
  /* ⭐ 已接后端：`PUT /api/m01/projects/{id}` —— 全名**可改 + 留痕**（§2.3.1 / §9.3）。
     ⚠️ 尾码剥离（`strip_trailing_code`）在**后端**做：导出 / 仓库同步 / 项目同步**三处共用同一份**。 */
  editFull:t=>{ const p=PJs.find(x=>x.id===t.dataset.id), v=t.value.trim(); if(!p||v===p.full) return;
    pjAct(()=>API.pjUpdate(p.id,{name_full:v}),
      `项目全名已修改并<b>留痕</b>（尾部的括号编号由系统统一剥掉）`); },
  /* ⭐ 已接后端：`PUT /api/m01/projects/{id}/status`
     ⛔ **不变式整段搬到后端**（`domain.apply_status_change` —— 与判据同一份纯函数）：
        ① 壳下还有在建小微 ⇒ **拒绝归档**并把是谁列出来（原值保留）；
        ② 归档壳下**最后一个在建小微** ⇒ 壳**自动跟着归档**（各自留痕）。
     前端只把后端回执显示出来 —— 自己算就有两份规则（D18：判定与落库一律后端）。 */
  editStatus:t=>{ const p=PJs.find(x=>x.id===t.dataset.id), v=t.value; if(!p||v===p.status) return;
    const wasSmall=(v==='归档'&&p.type==='small'&&p.parent);
    pjAct(()=>API.pjStatus(p.id, PJ_STATUS_VALUE[v]||v), ()=>{
      const sh=wasSmall?PJs.find(x=>x.id===p.parent):null;
      return `状态改为 <b>${v}</b>（各处筛选默认「在建」）`
        +((sh&&sh.status==='归档')?`<br>壳下已无在建小微 ⇒ 壳「${esc(sh.full)}」<b>自动一并归档</b>（已留痕）`:'');
    });
  },
 /* —— 自定义排序（2026-09-13 用户口径）——
    `ord` 挂在**档案行**（= 仓库，唯一标识 §9.8-4）上：全名 / 仓库名 / 展示名只是同一行的三种叫法，
    **全站各处都按这一条 ord 排**。改完**重编号**保持 1..N 连续无重复。
    ⚠️ **不留痕**：排序只是展示顺序，不是业务口径（与现行留痕范围一致）。 */
  /* ⭐ 已接后端：`PUT /api/m01/projects/{id}/ord` —— **填号 = 插到第 v 位 ＋ 全表重编号 1..N**（§2.7.3）
     ⚠️ 重编号与「不跨在建 / 归档分界」都在后端（`domain.reorder`，与判据同一份纯函数），前端只报结果。 */
  editOrd:t=>{ const p=PJs.find(x=>x.id===t.dataset.id); if(!p) return;
    const v=Math.max(1,Math.min(PJs.length,Math.floor(Number(t.value)||1)));
    pjAct(()=>API.pjOrd(p.id,{to_position:v}), ()=>{
      const np=PJs.find(x=>x.id===p.id);
      return `「${esc(p.name||p.full)}」已排到第 <b>${np?np.ord:'?'}</b> 位：全站（选项目 / 选仓库 / 选展示名）顺序同步<br>注：<b>归档项恒在最后</b>，所以填的位次与最终位置可能有偏差`;
    }, 6000); },
  ordUp:t=>ACT.ordMove(t.dataset.id,-1),
  ordDown:t=>ACT.ordMove(t.dataset.id,1),
  /* ↑ / ↓ = 与**相邻**一行对调（在"当前显示顺序"里，即自定义排序顺序），不是改 ord 数字。
     ⚠️ 「已在最前 / 最后」这类边界**由后端判**（它不动、也不跨分界）⇒ 前端只比 ord 有没有变。 */
  ordMove:(id,d)=>{ const p=PJs.find(x=>x.id===id); if(!p) return;
    const before=p.ord;
    pjAct(()=>API.pjOrd(p.id,{direction:d<0?'up':'down'}), ()=>{
      const np=PJs.find(x=>x.id===id);
      if(np&&np.ord===before) return d<0?'已经在最前面了':'已经在最后面了';
      const L=pjSortedAll(), i=L.findIndex(x=>x.id===id), q=L[i+(d<0?1:-1)];
      return `「${esc(p.name||p.full)}」已${d<0?'上移':'下移'}一位${q?`（与「${esc(q.name||q.full)}」对调）`:''}<br>注：<b>归档项恒在最后</b>，所以移动不会跨过在建 / 归档的分界`;
    }); },
 editKw:t=>{ const p=PJs.find(x=>x.id===t.dataset.id);
   modal({title:`小微识别关键词 · ${p.name}`,body:`<div class="tip" style="margin-bottom:calc(10px * var(--fscale))">关键词挂在<b>具体小微的行</b>上，格式 <span class="fc">|词1|词2|</span>；<b>允许重复</b>，命中多个时弹窗让用户选（决策 3/4）。</div>
     <div class="fld"><label>关键词（用 | 分隔）</label><input class="inp" id="kwV" value="${esc(p.kw)}"></div>`,
     footer:`<button class="btn" data-act="closeModal">取消</button><button class="btn pri" data-act="editKwOk" data-id="${p.id}">保存</button>`}); },
 /* ⭐ 已接后端：`PUT /api/m01/projects/{id}` 的 `match_keywords`。
    ⚠️ 输入是**竖线串**（`|词1|词2|`）、后端收**数组** ⇒ 在适配层 `kwSplit` / `kwJoin` 转（唯一出口）。 */
 editKwOk:t=>{ const p=PJs.find(x=>x.id===t.dataset.id); if(!p) return;
    const list=kwSplit($('#kwV').value);
    closeModal();
    pjAct(()=>API.pjUpdate(p.id,{match_keywords:list}),
      `关键词已保存：<b>${esc(list.length?kwJoin(list):'（清空）')}</b>`); },
 promote:t=>{ const p=PJs.find(x=>x.id===String(t.dataset.id)); if(!p) return;
    /* ⭐ **已接后端**（`TAIL-30`-③）：行内「扶正」＝ 指认弹窗的**另一个入口**（原型本来就画在这一列）。
       ⚠️ 匹配靠**候选行的 id**（后端给的），⛔ 不在前端拿全名去比对 —— 那要复刻一份
          `norm_full_name`（剥尾码 / 压缩空白），两份归一化早晚分叉 = 静默失配。 */
    const i=PEND.findIndex(x=>(x.candidates||[]).some(c=>c.id===String(p.id)));
    if(i<0) return toast(`「${esc(p.name||p.full)}」这一行<b>当前没有待指认的事</b>：`
      + `<br>只有<b>材料报表里出现陌生仓库</b>、且它的全名在档案里命中 <b>≥2 条</b>非壳行时，才需要人来指认"挂哪一行"；`
      + `命中 <b>1 条</b>占位行时，系统在抓取时<b>已经自动扶正</b>（不需要人工点）。`
      + `<br><span class="mut sm">刚抓过材料报表却没有待指认条目 ⇒ 本次没有这类情形；待办清单在本页顶部</span>`, 9000);
    openPendDialog(i); },
 /* ⭐ 人工指认的**落库出口**（`TAIL-30`-③）：⭐ 按 `project_id` 定位（铁律 5/6：⛔ 不用名字反查）。
    ⚠️ 成功/失败**都回后端真实状态**：被拒时后端给一句中文原因（如"只有占位行才能被系统扶正"）
       ⇒ `pjAct` 原样转给用户、并重新拉档案与待办清单（清单少一条才对）。 */
 pjPromoteOpen:t=>openPendDialog(Number(t.dataset.pend)),
 pjPromoteOk:t=>{ const it=PEND_DLG; if(!it) return;
    const sel=$('#pmRow');
    const id=Number(sel && sel.value);
    if(!id) return toast('<b>请先选择要写到哪一行</b>');
    closeModal();
    /* ⚠️ 提交的 `full_name` 取**开弹窗时锁定的那一条**（`PEND_DLG`）—— 清单后来刷新了也不会错位；
       后端还会拿它做一致性守卫（所选行的全名必须与它相同），对不上就**明确拒**。 */
    pjAct(()=>API.pjPromote({project_id:id, warehouse_name:it.wh, full_name:it.full}),
      r=>`<b>${esc((r&&r.message)||'已扶正')}</b>`, 9000); },
 /* —— 链路 A ③-b「全名对应 ≥2 个仓库 ⇒ 选定一个建行」（`TAIL-45`）——
    这条原先**只被列出来**（同步回执里报一次、刷新即丢）⇒ 用户看得见、**无处可点**；
    这里就是那个"可点"的出口（⛔ 判定与落库仍在后端：候选来自那次同步的 i8 名单）。 */
 pjArchOpen:t=>openArchDialog(Number(t.dataset.arch)),
 pjArchOk:t=>{ const it=ARCP_DLG; if(!it) return;
    const sel=$('#arcWh');
    const wh=String((sel&&sel.value)||'');
    if(!wh) return toast('<b>请先选择一个仓库</b>');
    closeModal();
    /* ⚠️ 提交的这一对（全名 ＋ 仓库名）取**开弹窗时锁定的那一条**（`ARCP_DLG`）—— 清单后来刷新了
       也不会错位；后端还会按当前档案现算再守卫一次（不在清单里 / 仓库名不在候选里 ⇒ 明确拒）。 */
    pjAct(()=>API.pjArchRow({full_name:it.full, warehouse_name:wh}),
      r=>`<b>${esc((r&&r.message)||'已建档')}</b>`, 9000); },
 /* ---- ⭐ `TAIL-42`：**人工覆盖三类判定**（把被误判成普通项目的壳纠正成壳）--------------------
    根因：三类判定（§2.2.1）里"是不是壳"**只看全名里有没有「小微」** ⇒ 有的壳全名不含它（图纸上的叫法）
    ⇒ 被误判成**普通项目**；材料侧再遇同族仓库时就按普通项目那条路重复处理。
    ⚠️ 判定与落库**全在后端**（`classify_name(manual_override=…)` 是判定唯一出口；改类型也只有一个出口）
       ⇒ 壳里只做"问用户选哪个"＋"把答案送过去"，⛔ 不在这儿再写一份三类判定。 */
 pjTypeOpen:t=>{ const p=PJs.find(x=>String(x.id)===String(t.dataset.id)); if(!p) return;
   pjTypeCur=p; pjTypeNew=''; pjTypeDlg(); },
 pjTypePick:t=>{ pjTypeNew=String(t.dataset.t||''); pjTypeDlg(); },
 pjTypeOk:t=>{ const p=pjTypeCur; if(!p) return;
   if(!pjTypeNew) return toast('先选一个目标类型（普通项目 / 小微壳）');
   const inp=$('#pjTypeWh');
   const wh=((inp&&inp.value)||'').trim();
   if(pjTypeNew==='normal'&&!wh) return toast('<b>改成「普通项目」必须填仓库名</b>：普通项目靠仓库名做候选键（§2.7.4），而壳原本不挂仓库 ⇒ 系统无从得知，⛔ 不猜一个填上',8500);
   closeModal();
   return pjAct(()=>API.pjType(p.id, pjTypeNew, wh),
     r=>`已把「${esc(pjDisp(p))}」改成 <b>${esc(PJ_TYPE_LABEL[pjTypeNew]||pjTypeNew)}</b>`
        +((r&&r.warehouse_name)?`（挂仓库 <b>${esc(r.warehouse_name)}</b>）`:''), 9000); },
 /* —— 链路 C · 归属判定（付款通知书行 → 具体小微）· 2026-09-12 定案 ——
    入口只开在「待指定」标签上；命中 1 个时**自动归集、不弹窗**（ownOf 已算好） */
 ownOpen:t=>{ const n=NO.find(x=>x.id===t.dataset.id); if(!n) return;
   const cands=ownCands(n), hit=matchKids(n.proj,n.doc), tot=projMatches(n.proj).length;
   modal({title:`指定归属 · ${esc(n.proj)}`,wide:true,
     body:`<div class="tip" style="margin-bottom:calc(10px * var(--fscale))"><b>链路 C</b>：这张通知书的付款项目是<b>壳的全名</b>，同一全名下共 ${tot} 条档案（1 个壳 + ${tot-1} 个具体小微），系统<b>不猜</b>（铁律 5/6）。
       本次用「单据名称」在<b>该壳下</b>的关键词里匹配，命中 <b>${hit.length}</b> 个${hit.length===0?' → 需人工指定':''}。关键词允许重复（决策 4）；<b>匹配范围限定在该壳下</b>，不跨壳（否则别的壳会把钱抢走）。</div>
       ${kvBlock([['单据编码',`<span class="fc">${esc(n.code)}</span>`],['单据名称',`<span class="fc">${esc(n.doc)}</span>`],['本次应付',M(payEff(n))]])}
       <p style="font-size:calc(12px * var(--fscale));margin:0 0 calc(8px * var(--fscale))">选已有小微时，<b>须填一个出现在上面单据名里的关键词</b>（选中后<b>去重追加</b>到该小微名下，供下次自动命中）；填不出说明不是它。</p>
       ${cands.map(p=>`<div style="display:flex;align-items:center;gap:calc(9px * var(--fscale));padding:calc(7px * var(--fscale)) calc(8px * var(--fscale));border:1px solid var(--bd);border-radius:7px;margin-bottom:calc(7px * var(--fscale))">
         <button class="btn sm pri" style="flex:0 0 auto" data-act="ownOk" data-id="${n.id}" data-pid="${p.id}">归集到它</button>
         <span style="flex:1;min-width:0">${esc(pjDisp(p))}${pjArcMark(p)} <span class="mut sm">· 仓库名 ${esc(p.name)} · 关键词 ${esc(p.kw||'—')}${hit.some(h=>h.id===p.id)?' · <b>已命中</b>':''}</span></span>
         <input class="inp" style="width:148px;flex:0 0 auto" id="ownKw_${p.id}" placeholder="关键词">
       </div>`).join('')}
       ${cands.length?'':'<div class="tip wn" style="margin:0 0 calc(9px * var(--fscale))">该壳下<b>暂无在建的具体小微</b> → 只能走下面的「新小微」建档。</div>'}
       <div style="padding:calc(9px * var(--fscale));border:1px dashed var(--bd);border-radius:7px">
         <div class="mut sm" style="margin-bottom:calc(7px * var(--fscale))">属于<b>新小微</b> → 录关键词并建档（<b>仓库名手输</b>）</div>
         <div class="fld"><label>新小微的仓库名</label><input class="inp" id="ownNewName" placeholder="如：河南南阳热电项目仓库"></div>
         <div class="fld" style="margin-top:calc(6px * var(--fscale))"><label>识别关键词（须出现在单据名里）</label><input class="inp" id="ownNewKw" placeholder="如：南阳"></div>
         <div style="margin-top:calc(8px * var(--fscale))"><button class="btn pri" data-act="ownOk" data-id="${n.id}" data-pid="__new">建档并归集</button></div>
       </div>`,
     footer:`<button class="btn" data-act="closeModal">取消（保持「待指定」）</button>`}); },
/* ⭐ `TAIL-93`：集采抓取回执里的「去指定归属」—— 开的是**同一个弹窗**（`core.js`），
   只是**数据源**换成集采（`API.jcUnsettled`）。⛔ 判定与写路径都复用付款侧那一份。 */
ownJcOpen:()=>openOwnDialogFor('jc'),
 /* 归集：写 OWN[单据id] = 档案 id；选已有小微时把关键词去重追加（§九：重心在「不出错」） */
 ownOk:t=>{ const n=NO.find(x=>x.id===t.dataset.id); if(!n) return; const pid=t.dataset.pid;
   if(pid==='__new'){
     const nm=($('#ownNewName').value||'').trim(), kw=($('#ownNewKw').value||'').trim();
     if(!nm||!kw){ toast('<b>新建小微需要「仓库名」与「关键词」都填写</b>，本次未建档'); return; }
     if(n.doc.indexOf(kw)<0){ toast(`关键词 <b>${esc(kw)}</b> 未出现在单据名「${esc(n.doc)}」里，<b>不予建档</b>`); return; }
     const sh=shellOf(n.proj);
     if(!sh){ toast('<b>壳未建档</b>：必须先有壳后有微（铁律 7）'); return; }
     /* 2026-09-13 用户口径：**已归档的壳下不许新建具体小微** ——
        新建出来必然是「在建」，当场破坏「壳归档 ⇔ 小微全归档」这条不变式。要新建，先把壳改回在建。 */
     if(arcOf(sh)){ toast(`<b>壳「${esc(sh.full)}」已归档</b>：不允许在已归档的壳下<b>新建</b>具体小微 —— 新小微必然是「在建」，会破坏「壳归档 ⇔ 小微全归档」。<br>确实要新建，请先把壳改回「在建」`,7000); return; }
     const nid='P'+String(PJs.reduce((mx,p)=>Math.max(mx,parseInt(String(p.id).replace(/\D/g,''),10)||0),0)+1).padStart(2,'0');
     PJs.push(O([nid,nm,nm,n.proj,'','在建','small',sh.id,'|'+kw+'|'],PJ_COLS));
     OWN[n.id]=nid; closeModal(); render();
     toast(`已建档并归集：<b>${esc(nm)}</b>（关键词 <span class="fc">${esc(kw)}</span>）→ 展示名从此<b>按 id 取</b>，不再「待指定」`); return; }
   const p=PJs.find(x=>x.id===pid); if(!p){ toast('未找到该具体小微'); return; }
   const kwEl=$('#ownKw_'+pid), kw=(kwEl&&kwEl.value?kwEl.value:'').trim();
   if(!kw){ toast('<b>须填一个出现在单据名里的关键词</b>才能归集（填不出说明这条不属于它）'); return; }
   if(n.doc.indexOf(kw)<0){ toast(`关键词 <b>${esc(kw)}</b> 未出现在单据名「${esc(n.doc)}」里，<b>不予归集</b>`); return; }
   const added=addKw(pid,kw);
   OWN[n.id]=pid; closeModal(); render();
   toast(`已归集到 <b>${esc(pjDisp(p))}</b>${added?`；关键词 <span class="fc">${esc(kw)}</span> 已去重追加`:'；该关键词已存在、未重复追加'}`); },

 /* —— MOD-15 用户管理（§1.5）——
    管理动作共 5 类：新增账号 / 改密 / 停用启用 / 删除用户（软删）/ 转让管理员。
    ⚠️ 2026-09-12 用户口径：①新增「授权转让」；②**取消账号名与密码的格式限制**
       （账号「非空 + 不重复」即可、密码无要求且可为空）；③新增「删除用户」= 软删；
       ④「不能停用自己」改为「**不能停用 / 删除最后一个在用管理员**」。

    ⭐ 2026-09-20（**片 4b**）：**6 个写动作全部改成调后端** ——
       ⛔ 原来那些"本地改数组 / 改字段"的写法是**假生效**：看着变了、刷新就回去，
          **而且不留痕**（本系统做账号体系就是为了让"谁改的"有出处）。
       ⚠️ 每个动作的成败看 **`res.ok`**（后端恒 HTTP 200，见 `api.py` 顶部）⇒
          失败时把 `res.message` **原样**给用户看（那是 §1.5.1 那句"必须让用户看见"的原话）。
       ⚠️ 壳里那些 `CUR.role!=='admin'` 只是**体验**（早点说"你不行"、别等填完表单才被拒）；
          真正的防线在**后端**（`domain.assert_is_admin` ＋ 防锁死）——
          ⛔ 别以为按钮 `disabled` 就等于拦住了（claim `001-07`：「直接调写操作也必须被拦」）。
       ⚠️ 写完之后一律 `await reloadM15(); render();` —— ⛔ **不手工往 `USERS` 里塞行**：
          库才是真相，壳照它重画（不然就会出现"壳里有一条、库里没有"）。 */
 userAdd:()=>{ modal({title:'新增账号',body:`<div class="tip" style="margin-bottom:calc(10px * var(--fscale))">管理员可<b>建号</b>（§1.5.1）。新增账号一律是<b>普通用户</b> —— 两人权限无区别，<b>不需要选角色</b>。</div>
   <div class="fld"><label>登录账号（非空、不重复即可）</label><input class="inp" id="uAcc" placeholder="如 wanglijia"></div>
   <div class="fld" style="margin-top:calc(6px * var(--fscale))"><label>姓名</label><input class="inp" id="uName" placeholder="如 王丽佳"></div>
   <div class="fld" style="margin-top:calc(6px * var(--fscale))"><label>初始密码（可为空）</label><input class="inp" id="uPwd" placeholder="留空即可；无格式要求"></div>`,
   footer:`<button class="btn" data-act="closeModal">取消</button><button class="btn pri" data-act="userAddOk">创建</button>`}); },
 userAddOk:async()=>{ const acc=($('#uAcc').value||'').trim(), nm=($('#uName').value||'').trim(), pd=($('#uPwd').value||'').trim();
   /* ⚠️ 这里的两条前端校验**保留**（体验：不必往返一趟才知道"没填账号"）；
      ⛔ 但它们**不是判据** —— 重名 / 空账号**最终由后端拒**（`assert_account_usable`）。 */
   if(!acc||!nm){ toast('<b>登录账号与姓名都要填</b>（账号非空即可，不限格式与长度），本次未创建'); return; }
   try{
     const res = await API.m15Create(acc, nm, pd);
     if(res.ok===false) return toast(`<b>没能创建</b>：${esc(res.message||'')}`, 9000);
     closeModal(); await reloadM15(); render();
     toast(esc(res.message||'已创建'), 7000);
   }catch(e){ toast(`<b>没能创建</b>：${esc(String((e&&e.message)||e))}`, 9000); } },
 userTransfer:()=>{ const cands=USERS.filter(u=>u.id!==CUR.id&&u.status==='在用');
   if(!cands.length){ toast('没有可转让的在用账号（先新增或启用一个）'); return; }
   modal({title:'转让管理员（授权转让）',body:`<div class="tip wn" style="margin-bottom:calc(10px * var(--fscale))"><b>授权转让</b>：转让后对方成为<b>管理员</b>、你自己转为<b>普通用户</b> —— 系统内<b>始终只保留一个管理员</b>（防锁死）。</div>
     <div class="fld"><label>转让给（限在用账号）</label><select class="inp" id="utId">${cands.map(u=>`<option value="${u.id}">${esc(u.name)}（${esc(u.acc)}）</option>`).join('')}</select></div>`,
     footer:`<button class="btn" data-act="closeModal">取消</button><button class="btn pri" data-act="userTransferOk">确认转让</button>`}); },
 userTransferOk:async()=>{ const el=$('#utId'); const u=el&&USERS.find(x=>String(x.id)===String(el.value)); if(!u){ toast('未选择转让对象'); return; }
   /* ⚠️ 原来这里是「先全部降级、再升目标」的**本地**写法 —— 已经删掉：
      改成调后端（后端在**同一个事务里**改两行 ⇒ 中间态"两个管理员"不可能被看到）。
      ⛔ 别在壳里再补一遍"降级"：那会让壳和库各有一份"谁是管理员"。 */
   try{
     const res = await API.m15Transfer(u.id);
     if(res.ok===false) return toast(`<b>没能转让</b>：${esc(res.message||'')}`, 9000);
     closeModal(); await reloadM15(); render();
     toast(esc(res.message||'已转让'), 8000);
   }catch(e){ toast(`<b>没能转让</b>：${esc(String((e&&e.message)||e))}`, 9000); } },
 userPwd:t=>{ const u=USERS.find(x=>x.id===t.dataset.id); if(!u) return;
   if(CUR.role!=='admin'){ toast('只有管理员能管理账号'); return; }
   modal({title:`密码与 i8 绑定 · ${esc(u.name)}`,body:`<div class="tip" style="margin-bottom:calc(10px * var(--fscale))">${u.id===CUR.id?'改<b>自己的</b>密码。':'管理员<b>重置他人密码</b>（§1.5.1「可管理其他账号」）。'}<b>无格式要求、可留空</b>（留空 = 清空该账号密码，空密码即可登录）。</div>
     <div class="fld"><label>新密码（可为空）</label><input class="inp" id="upV" placeholder="留空即清空该账号密码"></div>
     <div class="fld" style="margin-top:calc(10px * var(--fscale))"><label>i8 账号（§7.8 · 绑定到本系统账号、每人一份）</label>
       <input class="inp" id="upI8U" value="${esc(u.i8||'')}" autocomplete="off"
         placeholder="留空 = 解绑，抓取回落 .env 的 I8_USER"></div>
     <div class="fld" style="margin-top:calc(6px * var(--fscale))"><label>i8 密码</label>
       <input class="inp" id="upI8P" autocomplete="off" placeholder="留空 = 不改（要清空就把上面的账号也清掉）">
       <div class="mut sm" style="margin-top:calc(4px * var(--fscale))">⚠️ 明文保存（i8 登录要原样用它，哈希就登不上）；列表里不显示
         ⇒ <b>这个框默认是空的</b>，空 = 不改它。</div></div>`,
     footer:`<button class="btn" data-act="closeModal">取消</button><button class="btn pri" data-act="userPwdOk" data-id="${u.id}">保存</button>`}); },
 userPwdOk:async t=>{ const u=USERS.find(x=>String(x.id)===String(t.dataset.id)); if(!u) return;
   /* ⚠️ ⛔ **不 `.trim()`**：§1.5.1 说密码「无格式要求」⇒ 前后的空格**也是密码的一部分**。
      原来这里 trim 了 —— 那会在"用户故意用空格当密码"时**静默改掉他的密码**。 */
   const v = ($('#upV').value||'');
   const i8u = ($('#upI8U').value||'').trim();       /* 账号是标识 ⇒ 去空白 */
   const i8pRaw = ($('#upI8P').value||'');
   /* ⚠️⚠️ **空框 = 不改 i8 密码**（⛔ 不是清空）—— 列表出参不带 i8 密码 ⇒ 这个框默认就是空的，
      当成"清空"会让"只改账号"这一步**静默抹掉**同事的 i8 密码（下次抓取登不上、且没人知道为什么）。
      要清空 ⇒ 把 i8 账号也清掉（解绑 = 两样一起清）。 */
   const i8p = i8pRaw === '' ? null : i8pRaw;
   try{
     const r1 = await API.m15Pwd(u.id, v);
     if(r1.ok===false) return toast(`<b>没能改密</b>：${esc(r1.message||'')}`, 9000);
     const r2 = await API.m15I8(u.id, i8u, i8p);
     if(r2.ok===false) return toast(
       `<b>系统密码已改，但 i8 绑定没存上</b>：${esc(r2.message||'')}<br>
        <span class="sm">（两步是分开的：改密那一步已经生效了 —— 重开本弹窗再存一次 i8 绑定即可）</span>`, 14000);
     closeModal(); await reloadM15(); render();
     toast(`${esc(r1.message||'密码已更新')}<br>${esc(r2.message||'')}`, 9000);
   }catch(e){ toast(`<b>没能保存</b>：${esc(String((e&&e.message)||e))}`, 9000); } },
 /* ⭐ 「查看密码」—— **明文裁定的显式出口**（2026-09-20 用户裁定「要加」）。
    ⚠️ 为什么是"指名要一个"的单独动作、⛔ 不是列表里带出来：列表一打开就全在屏上
       （还容易被截图）；单独动作多一道"用户确实是来看这个的"。
    ⚠️ 出的是**明文** —— 因为本系统是科室内部 2 人的局域网工具，管理员**要能念给同事听**
       （那正是选明文的原因之一）。 */
 userPwdView:async t=>{ const u=USERS.find(x=>String(x.id)===String(t.dataset.id)); if(!u) return;
   try{
     const res = await API.m15Password(u.id);
     if(res.ok===false) return toast(`<b>看不到密码</b>：${esc(res.message||'')}`, 9000);
     const pw = res.password||'';
     /* ⭐ `§7.8` i8 绑定也在这个出口里（**同一个动作**：对管理员而言"把这个同事的凭据念给他"是一件事）。
        ⚠️ 未绑定时**明说"回落 .env"**，⛔ 不显示成空框 —— 那会让人以为"数据没取到"。 */
     const i8u = res.i8_user || '';
     const i8p = res.i8_password || '';
     const i8Block = i8u
       ? `<div class="fld" style="margin-top:calc(6px * var(--fscale))"><label>i8 账号（§7.8 · 每人一份）</label>
            <input class="inp" value="${esc(i8u)}" readonly></div>
          <div class="fld" style="margin-top:calc(6px * var(--fscale))"><label>i8 密码</label>
            <input class="inp" value="${esc(i8p)}" readonly>
            ${i8p?'':'<div class="mut sm" style="margin-top:calc(4px * var(--fscale))">该账号的 i8 <b>密码为空</b> —— 抓取会拿空密码去登录（会失败）</div>'}</div>`
       : `<div class="fld" style="margin-top:calc(6px * var(--fscale))"><label>i8 账号（§7.8 · 每人一份）</label>
            <input class="inp" value="（未绑定）" readonly>
            <div class="mut sm" style="margin-top:calc(4px * var(--fscale))">该账号<b>还没绑 i8</b> ⇒ 抓取回落 <code>.env</code> 的
              <code>I8_USER</code>（过渡期口径）。在「改密 / i8 绑定」里填上即可。</div></div>`;
     modal({title:`查看密码与 i8 绑定 · ${esc(u.name)}`, body:
       `<div class="tip">§1.5.1：密码<b>无格式要求、可为空</b>；本系统为科室内部 2 人使用，<b>明文保存</b>（管理员要能念给同事听）。</div>
        <div class="fld" style="margin-top:calc(10px * var(--fscale))"><label>登录账号</label><input class="inp" value="${esc(res.account||u.acc)}" readonly></div>
        <div class="fld" style="margin-top:calc(6px * var(--fscale))"><label>当前密码</label>
          <input class="inp" id="viewPw" value="${esc(pw)}" readonly>
          ${pw?'':'<div class="mut sm" style="margin-top:calc(4px * var(--fscale))">该账号<b>没有设密码</b>（空密码即可登录 · §1.5.1「可为空」）</div>'}</div>
        ${i8Block}`,
       footer:`<button class="btn" data-act="closeModal">关闭</button>`});
   }catch(e){ toast(`<b>看不到密码</b>：${esc(String((e&&e.message)||e))}`, 9000); } },
 userToggle:async t=>{ const u=USERS.find(x=>String(x.id)===String(t.dataset.id)); if(!u) return;
   if(CUR.role!=='admin'){ toast('只有管理员能停用 / 启用账号'); return; }
   /* ⚠️ 「不能停用最后一个管理员」这句**前端保留**（体验：点了立刻知道，不必往返）；
      ⛔ 但它**不是判据** —— 真拦人的是后端 `domain.assert_last_admin_protected`
      （并在 `001-07` 里被钉住：**直接调写操作也必须被拦**）。 */
   if(u.status==='在用'&&u.role==='admin'&&USERS.filter(x=>x.role==='admin'&&x.status==='在用').length<=1){
     toast('<b>不能停用最后一个管理员</b> —— 会把管理入口锁死（请先转让或新增一个管理员）'); return; }
   const next = u.status==='在用' ? '已停用' : '在用';
   try{
     const res = await API.m15Status(u.id, next);
     if(res.ok===false) return toast(`<b>没能切换</b>：${esc(res.message||'')}`, 9000);
     await reloadM15(); render();
     toast(esc(res.message||'已切换状态'), 7000);
   }catch(e){ toast(`<b>没能切换</b>：${esc(String((e&&e.message)||e))}`, 9000); } },
 userDel:t=>{ const u=USERS.find(x=>x.id===t.dataset.id); if(!u) return;
   if(CUR.role!=='admin'){ toast('只有管理员能删除账号'); return; }
   if(u.id===CUR.id){ toast('<b>不能删除自己</b>（当前登录账号）'); return; }
   if(u.status==='在用'&&u.role==='admin'&&USERS.filter(x=>x.role==='admin'&&x.status==='在用').length<=1){
     toast('<b>不能删除最后一个管理员</b>（防锁死）'); return; }
   modal({title:'删除账号确认',body:`<div class="tip dg" style="margin-bottom:calc(10px * var(--fscale))"><b>⚠️ 删除 = 软删除</b>：账号名保留、不销毁数据 —— 历史留痕（改前人 / 操作人）里的这个人名<b>仍然认得出来</b>，必要时可恢复。</div>
     ${kvBlock([['登录账号',`<span class="fc">${esc(u.acc)}</span>`],['姓名',`<span class="fc">${esc(u.name)}</span>`],['角色',u.role==='admin'?'管理员':'普通用户'],['影响','不再能登录；<b>已产生的留痕记录不受影响</b>']])}`,
     footer:`<button class="btn" data-act="closeModal">取消</button><button class="btn dg" data-act="userDelOk" data-id="${u.id}">确认删除</button>`}); },
 userDelOk:async t=>{ const u=USERS.find(x=>String(x.id)===String(t.dataset.id)); if(!u||u.status==='已删除') return;
   if(CUR.role!=='admin'){ toast('只有管理员能删除账号'); return; }
   if(u.id===CUR.id){ toast('<b>不能删除自己</b>（当前登录账号）'); return; }
   if(u.role==='admin'&&u.status==='在用'&&USERS.filter(x=>x.role==='admin'&&x.status==='在用').length<=1){
     toast('<b>不能删除最后一个管理员</b>（防锁死）'); return; }
   try{
     const res = await API.m15Delete(u.id);
     if(res.ok===false) return toast(`<b>没能删除</b>：${esc(res.message||'')}`, 9000);
     closeModal(); await reloadM15(); render();
     toast(esc(res.message||'已删除（软删）'), 7000);
   }catch(e){ toast(`<b>没能删除</b>：${esc(String((e&&e.message)||e))}`, 9000); } },
 userRestore:async t=>{ const u=USERS.find(x=>String(x.id)===String(t.dataset.id)); if(!u) return;
   if(CUR.role!=='admin'){ toast('只有管理员能恢复账号'); return; }
   try{
     const res = await API.m15Restore(u.id);
     if(res.ok===false) return toast(`<b>没能恢复</b>：${esc(res.message||'')}`, 9000);
     await reloadM15(); render();
     toast(esc(res.message||'已恢复'), 7000);
   }catch(e){ toast(`<b>没能恢复</b>：${esc(String((e&&e.message)||e))}`, 9000); } },
 /* 登出（§1.5.1）：**退出后回到登录页**，业务数据不受影响。
    ⭐ 2026-09-20 片 4b：**接上真鉴权** —— 调 `/api/m15/logout`（**后端清 cookie**），
       成功后**跳 `/login`**（⛔ 不再只弹个 toast 说"已退出"那种假动作）。 */
 logout:()=>{ modal({title:'退出登录',body:`<div class="tip" style="margin-bottom:calc(10px * var(--fscale))">当前登录 <b>${esc(CUR.name)}</b>（${CUR.role==='admin'?'管理员':'普通用户'}）。</div>
     <div class="tip" style="margin:0">退出后回到<b>登录页</b>，登录态失效，<b>业务数据不受影响</b>（§1.5.1）。</div>`,
     footer:`<button class="btn" data-act="closeModal">取消</button><button class="btn pri" data-act="logoutOk">确认登出</button>`}); },
 logoutOk:async()=>{ closeModal();
   try{ await API.m15Logout(); }catch(e){ /* ⚠️ 登出即便请求失败也要把人送回登录页（⛔ 别把人卡在壳里） */ }
   location.href = '/login'; },
 /* ⭐ 外观主题（`ACC-UI-THEME-001/001-06`）：**按用户隔离** ⇒ 存的是"我这个账号用哪套"，
    由 `/static/theme.css` 按会话取出。**入口在 `V.set`（系统设置 ·`MOD-14`）**。 */
 themeSet:async t=>{
  /* ⚠️⚠️ **取主题名的顺序不能反**：`data-theme` 优先，`value` 兜底。
     2026-09-21 实测踩到 —— 写成"`t.value === undefined` 才用 `data-theme`"时，
     `<button>` **也有 `value` 属性**（默认空串！）⇒ 走的是 `value` 分支 ⇒ 把**空串**写回后端
     ⇒ 主题回落到默认套 ⇒ 症状就是用户报的「**换了没反应**」（而且全程不报错，非常像"功能坏了"）。
     ⭐ 通法：**先认最具体的那一个**（`data-*`），别拿"属性存不存在"当判据。 */
  const name=(t.dataset&&t.dataset.theme)||t.value||'';
   try{
     const res = await API.m15ThemeSet(name);
     if(res.ok===false) return toast(`<b>没能换主题</b>：${esc(res.message||'')}`, 9000);
     applyThemeLive();          /* ⭐ 就地生效（⛔ 不整页刷新 —— 那会把用户扔回看板） */
     CUR_THEME=name; render();  /* 下拉选中态 / 色板预览随之刷新 */
     toast(`主题已换成「<b>${esc(name)}</b>」—— 即时生效，<b>不刷新页面</b>`, 4000);
   }catch(e){ toast(`<b>没能换主题</b>：${esc(String((e&&e.message)||e))}`, 9000); } },
/* ⭐⭐ `TAIL-129`（2026-09-27）**界面大小**：与主题**同构**（按用户存、点了即时生效不刷新）。
   ⚠️ 档位键走 `data-key`（⛔ 不读 `value`：`<button>` 也有 `value`（默认空串）⇒ 那正是主题当年
      「换了没反应」的坑，见上一条注释「取主题名的顺序不能反」）。
   ⚠️ 失败**原样显示后端的中文原因**（非法档位后端会显式拒绝 —— 见 `api_set_ui_scale`）。 */
uiScaleSet:async t=>{
  const key=(t.dataset&&t.dataset.key)||'';
  try{
    const res = await API.m15UiScaleSet(key);
    if(res && res.ok===false) return toast(`<b>没能改界面大小</b>：${esc(res.message||'')}`, 9000);
    const got = UI_SCALES.find(s => s.key === key);
    applyUiScale(got ? got.css : '1');      /* ⭐ 就地生效（⛔ 不整页刷新） */
    CUR_UI_SCALE = key; render();           /* 选中态随之刷新 */
    const label = got ? got.label : key;
    toast(`界面大小已改为「<b>${esc(label)}</b>」—— 即时生效，<b>不刷新页面</b>`
      + `<br>（只管屏幕：打印件与导出的 Excel 不受影响）`, 7000);
  }catch(e){ toast(`<b>没能改界面大小</b>：${esc(String((e&&e.message)||e))}`, 9000); } },
 delPj:t=>{ const p=PJs.find(x=>x.id===t.dataset.id);
   /* ⭐ 2026-09-29（`A6` 逐页 · `m01`）：这句原是从《说明书》§7.2 **原样搬过来**的**要求句**
      （「必须**列出删除影响范围**」＝ 写给实现的要求，不是给用户看的话；⛔ 这里刻意拆开写，
      免得墓碑判据扫全文时命中**本注释**）⇒ 守则 §1.1「这个元素是使用用户需要感知的吗」＋
      §2.5「用业务术语，不用内部话术」 ⇒ 改成人话：用户在删除前要知道的是
      **这条删除不可撤销、先看清它会影响到哪些地方**；⚠️ `（§7.2）` 这个出处标记**保留**
      （用户 2026-09-27 裁定 `B`：`§节号` 上屏保留 —— 见 `tools/probe/_shell_text.py` 文件头）。 */
   modal({title:'删除确认',body:`<div class="tip dg"><b>⚠️ 删除不可撤销 —— 先看清它会影响到下面哪些地方</b>（§7.2）</div>
     ${kvBlock([['项目',`<span style="font-size:calc(11.5px * var(--fscale))">${esc(p.full)}</span>`],
       ['关联付款通知书',`<span class="fc">${NO.filter(n=>n.proj===p.full).length} 条</span>`],
       /* ⚠️ 下面三项要**跨模块数**（付款流水 / 库存单据 / 集采合同）⇒ 属 `MOD-13`，尚未落地。
          ⛔ 不显示 `0` —— 那是**假话**（会让人以为"没有关联"）⇒ 如实标"待接通"。
          ⭐ 2026-09-28（`TAIL-131`）：括号里原写「跨域能力」= **内部叫法**（守则 §2.5/§3.3：
          界面用业务术语）⇒ 改成人话；⛔ 别把那个词写回界面。 */
       ['关联付款流水',`<span class="mut">待接通（这一项还没做）</span>`],
       ['关联库存单据行',`<span class="mut">待接通（这一项还没做）</span>`],
       ['关联集采合同',`<span class="mut">待接通（这一项还没做）</span>`]]
       .concat(PJs.filter(x=>x.parent===p.id).length?[['所属小微（仓库名）',`<span class="wn">${PJs.filter(x=>x.parent===p.id).map(x=>esc(x.name)).join(' / ')}</span>`]]:[]))}
     <div class="tip" style="margin:0">项目档案属<b>配置类数据 ⇒ 硬删</b>（§9.4）；被引用的核心业务数据（通知书 / 流水 / 库存单据 / 集采合同）<b>不随删</b> —— 它们仍保留原项目全名，页面上会显示为<b>未建档</b>。</div>
     <div class="tip" style="margin:0"><b>删除这一项还没打通</b>：删除前得先把「影响范围」列全，而上面还有 3 项数不出来 —— 等这几项能列全就开放（所以下面那枚按钮现在是灰的）。</div>`,
     footer:`<button class="btn" data-act="closeModal">取消</button><button class="btn dg" data-act="delPjOk" data-id="${p.id}" disabled title="这一项还没打通：删除前得先把「影响范围」列全，而现还有 3 项数不出来 —— 等它们能列全就开放">确认删除</button>`}); },
 /* ⏳ **尚未接通后端（诚实提示，⛔ 不做假成功）** —— 删除本身（配置类硬删 §9.4）不难，
    难的是**先列影响范围**（§7.2）：要数关联的付款通知书 / 流水 / 库存单据 / 集采合同 = **跨模块统计**，
    属 `MOD-13` 跨域能力。⇒ 在"列得出影响范围"之前**不接删除**，否则 §7.2 就成了一句空话。 */
 delPjOk:t=>{ const p=PJs.find(x=>x.id===t.dataset.id); if(!p) return;
    closeModal();
    toast(`⏳ <b>删除尚未接通后端</b>：「${esc(p.disp||p.name)}」—— 删除前必须<b>列出影响范围</b>（§7.2），那是<b>跨模块统计</b>；<br>该能力未落地前不接删除 —— 避免"列不出影响范围就删了"`,7000); },
 /* ⭐ 2026-09-18 接通（`TAIL-27`）：两个同步都是**登录 i8**（会**强踢**该账号在线用户，D9）
    ⇒ 统一走 `m02Sync()` —— 它先弹**二次确认**（这是 D9 那道闸），确认后才发请求。
    ⚠️ 与 `m02` 表里 API-05/06 两行的「触发」**共用同一个入口**（一份能力只许一个主人）。 */
 syncWh:()=>m02Sync('warehouses'),
 syncPj:()=>m02Sync('common-projects'),
 /* ⭐ 二次确认之后的**唯一出口**：成功/失败都回后端真实状态，把回执**原样**转给用户（⛔ 不吞、不换句话）。 */
 m02SyncOk:async t=>{ const which=String(t.dataset.which||''); const isWh=which!=='common-projects';
    closeModal();
    let r=null;
    try { r = await (isWh ? API.m02SyncWh() : API.m02SyncPj()); }
    catch(e){ try{ await reloadM02(); }catch(_){}
      return fetchResultModal(`同步没能完成 · ${isWh?'仓库名单':'常用项目列表'}`,
        `<b style="color:var(--wn)">${esc(String((e&&e.message)||e))}</b>`); }
    try { await reloadM02(); } catch(_){ /* 取数失败 ⇒ 日志卡里会如实说 */ }
    /* 同步「常用项目列表」会**真的建档**（`ACC-PRJ-SYNC-001`）⇒ 档案与「待人工建档」卡都得跟着刷 */
    if(!isWh){ try{ await reloadProjects(); }catch(_){} }
    if(r && r.degraded) return fetchResultModal(`同步结果 · ${isWh?'仓库名单':'常用项目列表'}`,
      `⚠️ <b>i8 侧不可用，未改动本地档案</b>：${esc(r.message||'')}`);
    const ct=(r&&r.counts)||{};
    /* ⭐ 2026-09-29（`TAIL-190` 用户真机报障）：`待人工` 里**混着两类、出路完全不同** ⇒
       ⛔ 不许只报一个总数、更不许把两类都指向 m01 那张卡 —— 那张卡**只收「挂 ≥2 个仓库」那类**，
       「壳下具体小微」按设计根本不在卡上 ⇒ 用户照旧文案去了档案页，看到的是**空卡** ✗✗。
       分类的**唯一出口 = 后端**（`counts.manual_multi` / `counts.manual_shell`，后端按 `kind` 认），
       壳侧只负责把「去哪」说清（⛔ 不自己判断"有没有 warehouses 键"）。 */
    const nM=Number((ct.manual_multi)||0), nS=Number((ct.manual_shell)||0);
    const more=(!isWh && ct.manual)
      ? `<br>⇒ 待人工 <b>${ct.manual}</b> 条，<b>两类去两个地方</b>：`
        + (nM?`<br>· <b>${nM}</b> 条「一个全名挂多个仓库」⇒ 去 <b>「项目档案」页</b>的「待人工建档」卡，<b>选定一个仓库</b>就地建行`:'')
        + (nS?`<br>· <b>${nS}</b> 条「壳下具体小微」⇒ <b>不用去档案页</b>：它要的是<b>关键词</b>，走<b>建档向导</b>（m03 里遇到该壳时选小微／补词）`:'')
        + ((nM+nS===0)?`<br>· 明细见 <b>「项目档案」页</b>的「待人工建档」卡（老记录没有分类字段时只能看那张卡）`:'')
      : '';
    fetchResultModal(`同步结果 · ${isWh?'仓库名单':'常用项目列表'}`,
      `✅ <b>已同步</b>：${esc((r&&r.message)||('取到 '+((r&&r.count)||0)+' 条'))}${more}`); },

 /* —— MOD-06 —— */
 pjArcToggle:t=>{ pjToggle(String(t.dataset.pk||'')+'Arc'); },   /* ⭐ 归档折叠（①② 2026-09-27）：展开态走 `PJ_OPEN` */
procPjToggle:()=>{ pjToggle('procPj'); render(); },
 procPjPick:t=>{ procPj=t.dataset.pj; pjClose('procPj'); render(); },
 /* —— 过程资料「按模板导出」展开区（2026-09-13：多选项目 · 每项目一份 · ≥2 打 zip）—— */
 procExpToggle:()=>{
   /* ⭐⭐ 2026-09-28（用户报障"点没了还得再点两下才出来"）：**开 / 关的唯一真相 = 面板自己的开合态**
      —— `pjIsOpen('procExpPj')`。⛔ 不能拿 `procExpOn` 当判据：**点浮层外面收起时它不会跟着合**
      ⇒ 两边走散后，再点按钮就变成"关一个已经关了的" ⇒ 要点**两下**才出来（这就是那条报障的根）。
      ⚠️ `procExpOn` 降级为"下方展开区是否可见"的**镜像**（随本次开 / 关同步写，⛔ 别再用它当判据）。 */
   const open=!pjIsOpen('procExpPj');
   procExpOn=open;
    if(procExpOn&&!procExpPjs.length&&procPj) procExpPjs=[procPj];   /* 默认 = 本页当前所选项目 */
   /* ⛔ 也别让页面的「项目」筛选面板同时开着（两个面板会互相遮）。 */
   if(open){ PJ_OPEN['procExpPj']=true; pjClose('procPj'); } else pjClose('procExpPj');
   render();
   /* ⭐ 2026-09-28（`TAIL-142` 同批收口，与台账那个**同款**）：这条也是 **6200ms 长机制说明**，而面板
      （`procExpStrip`）里本来就有同一段「导出形态：每项目一份 … 选 2 个以上打成 zip」 ⇒ toast 只留回执。 */
   if(procExpOn) toast('已展开「按模板导出」：默认选中<b>本页当前项目</b>（可多选）'); },
 procExpPjPick:t=>{ const v=(t&&t.dataset&&t.dataset.pj)||''; if(!v) return;
   const i=procExpPjs.indexOf(v); if(i>=0) procExpPjs.splice(i,1); else procExpPjs.push(v); render(); },
 procExpPjAll:()=>{ procExpPjs=pjSort(PROC_PJS).slice(); render(); },
 procExpPjNone:()=>{ procExpPjs=[]; render(); },
 procExpCancel:()=>{ procExpOn=false; pjClose('procExpPj'); procExpPjs=[]; render(); toast('已收起导出面板（<b>未导出任何文件</b>）'); },
 procExpOk:()=>{ const pjs=procExpPjs.slice(); if(!pjs.length) return toast('请先选择要导出的项目');
   /* ⚠️ 文件名 = **展示名 ＋ 域 ＋ 表名 ＋ 年月**（与后端 `domain.export_file_name` 同构）——
      ⚠️ **表名进文件名**：三张表（表① / 表② / 差异表）**同一形态**，只有数据与文件名不同
      （用户 2026-09-18 裁）；导出**跟随当前所显示的那张表**。 */
      const ym=bjMonth(), fnOf=k=>`${pjLabel(k)}_过程资料_${procTabName()}_${ym}.xlsx`;
      /* ⭐ 2026-09-20 用户裁定：**导出清单弹窗里的表要可排序**（判据 `ACC-X-EXP-001/001-06`）。
      ⚠️⚠️ 排序的**开关是 `data-sort`（无值属性）**，⛔ **不是** `data-sort-key`：
        `data-sort-key` 只是**排序状态的键（表的身份）**。`index.html` 里那段注入逻辑
        **精确匹配 `data-sort`**（就是为此专门写过一版修正，见那里的注释）⇒
        **只加 `data-sort-key` 的话表照样点不动** —— 那就是"看着改了、其实没生效"。
      ⛔ 别照着 `modal:expExt-*` 抄：那张是**刻意不可排**的（`INDEX` 里点名的分组表，合计行要 pin 在表尾）。 */
   const body = pjs.length===1
     ? `<div class="tip" style="margin:0">将生成 <b>1 个文件</b>：<span class="fc">${esc(fnOf(pjs[0]))}</span><br>内容 = <b>当前所显示的那张表</b>（<b>${procTabName()}</b>）按 <b>17 列模板</b>填充（核算月 ｜ 入库 5 类 ｜ 出库 5 类 ｜ 机械 6 列），报<b>分公司工程科</b>（§5.2.2）。</div>`
     : `<div class="tip" style="margin:0">选了 <b>${pjs.length}</b> 个项目 ⇒ 打成一个 <b>zip</b>：<span class="fc">过程资料_${ym}.zip</span>，内含 <b>${pjs.length}</b> 个文件（每个 = 一个项目的 <b>${procTabName()}</b>）。</div>
       ${TBL({cls:'cond',key:'modal:procExp',sty:'margin-top:calc(8px * var(--fscale))',head:'<th>#</th><th>文件（每项目一份）</th>',
       rows:pjs.map((k,i)=>`<tr><td class="fc">${i+1}</td><td>${esc(fnOf(k))}</td></tr>`)})}`;
   modal({title:'导出 · 过程资料（按模板 · 每项目一份）',body,
     footer:`<button class="btn" data-act="closeModal">关闭</button><button class="btn pri" data-act="procExpSave">保存到本地</button>`}); },
 /* ⭐ 接线（`TAIL-04` 路径① · 片 4a）：成品由**后端模板填充**生成 —— 每个项目**一本工作簿**
   （`汇总表` 18 列：序号 ｜ 时间 ｜ 入库 5 类 ｜ 出库 5 类 ｜ 机械 6 列 ＋ 小计 / 合计 / 脚注尾块）；
   选 **≥2 个项目** ⇒ 打成一个 zip。
   ⚠️ **取数跟随当前所显示的那张表**（`tab` ＝ 0 表①原始 / 1 表②调整后 / 2 差异表）——
      壳侧**原样带过去**，⛔ 不在前端另算（差异表 = 逐格「调整后 − 原始」）。
   ⚠️ 失败时后端回 **JSON 200 ＋ `ok:false` ＋ 中文原因**（**一个项目都没选** · 项目**没有数据** ·
      项目**不在档案里**（取不到展示名）· 模板缺失/损坏 · **显示区对账不过**）
      ⇒ 据 `content-type` 分流：JSON ⇒ 弹原因；否则当文件下载。
   ⛔ 前端不自己拼文件名（命名规则的主人在后端，经 `X-Export-Filename` 带出）。 */
 procExpSave:async ()=>{
   const pjs=procExpPjs.slice();
   if(!pjs.length) return toast('请先选择要导出的项目');
   const url='/api/m06/export?projects='+encodeURIComponent(pjs.join(','))
     +'&tab='+encodeURIComponent(procTab);
   const fn=await dlExport(url,{name:'过程资料.xlsx',close:true});
   if(!fn) return;
   toast(pjs.length===1
     ? `已导出 <b>${esc(fn)}</b>：<b>${procTabName()}</b> · 一本工作簿（<b>汇总表</b> 18 列 ＋ 小计 / 合计 / 脚注）`
     : `已导出 <b>${esc(fn)}</b>：<b>${pjs.length}</b> 个项目 ⇒ 一个 zip（每项目一本 · 每本 = <b>${procTabName()}</b>）`,8600); },
 procTab:t=>{ procTab=+t.dataset.i; render(); },
 /* `exportProc` 已按 2026-09-13 用户口径**删除**（原按钮只演示一份）——
    改为 `procExpToggle` 展开区：**多选项目** → 每项目一份 → ≥2 个打成 zip（`procExpOk` 给清单预览）。 */
 /* 库存单据明细：**额外**一份「含数据透视表」的导出（用户口径 2026-09-13）——
    ⚠️ 它**不影响**主表那份朴素导出（「导出 Excel」照旧）。 */
 /* ⭐ 「含数据透视表」那份 = 走**路径②**（脚本直接改 i8 导出源文件，§7.1 / `模板清单` §一）——
    形态**以 `模板_库存单据明细表.xlsx` 为准**：3 张 sheet = 明细（**列随 i8 源文件**，与页面列不同）
    +「**过程资料**」透视（按仓 × 出入库方向 × 物料性质）+「**安全文明施工费**」透视（按仓 × 金额）。
    ⚠️ 2026-09-14 更正：旧文案写「明细（列与页面一致）· 工作表 2 = 透视（按项目 × 月份）」—— **两处都错**
       （路径②不套模板骨架、列随 i8 源文件；透视也不是"按项目 × 月份"那一张）。 */
 expPivot:async ()=>{
   /* ⭐ 2026-09-21 用户裁定「**抓取导出分开**」：这份导出只读**最近一次抓取的源文件缓存**
      （⛔ 不现场登 i8 ⇒ 不再需要二次确认 / 授权参数 —— D9 的确认都在「抓取」侧，与 m07 同一套心智）。
      缓存没有（该月还没抓过）⇒ 后端回「请先抓取」，照样弹窗明说。 */
   const url='/api/m08/inventory/export?period='+encodeURIComponent(fIvYm);
   const fn=await dlExport(url,{name:'库存单据明细表.xlsx'});
   if(!fn) return;
   toast('已导出「库存单据明细（含数据透视表）」：<b>工作表 1</b> = 明细（<b>列随 i8 源文件</b>，与页面列不同）；<b>工作表 2</b> = <b>「过程资料」透视</b>（按仓 × 出入库方向 × 物料性质）；<b>工作表 3</b> = <b>「安全文明施工费」透视</b>（按仓 × 金额）<br>⭐ 用的是<b>最近一次抓取</b>的源文件 —— 若该月有新单据，先抓取再导出<br>⚠️ 这份是<b>单独的一条通道</b>，主表那个「导出 Excel」<b>不受影响</b>',6400); },
 goInvAdj:t=>{ invWhs.length=0; invWhs.push(t.dataset.wh); invOnlyAdj=true; go('m08'); setTimeout(()=>toast(`已跳转库存单据页并自动筛出：<b>${esc(t.dataset.wh)}</b> 被调整过的行`),120); },

 /* —— MOD-07 —— */
 /* ⭐ 接线（`TAIL-04`）：成品由**后端模板法**生成 —— 分仓库 xlsx ＋ 1 个总表打成**一个 zip**。
    ⚠️ 失败时后端回 **JSON 200 ＋ `ok:false` ＋ 中文原因**（模板缺失/损坏 · 该月没有明细 ·
       **缓存级对账不过**）⇒ 据 `content-type` 分流：JSON ⇒ 弹原因；否则当文件下载。
    ⛔ 前端不自己拼文件名（命名规则的主人在后端，经 `X-Export-Filename` 带出）。 */
 zipSfjc:async ()=>{
   const url='/api/m07/settlement/export?period='+encodeURIComponent(fWhYm);
   const fn=await dlExport(url,{name:'收发结存表.zip'});
   if(!fn) return;
   toast(`已导出<b>${pjSort(whRows(fWhYm)).length}</b> 个分仓库 xlsx ＋ 1 个总表（zip）；`
     + `—— 金额按 <b>2 位小数对平（差 1 分也算不平）</b>`,7600); },
 whReset:()=>{ fWhYm=bjMonth(-1); render(); toast(`已重置：核算年月回到 <b>${tmLabel(fWhYm)}</b>（材料报表 = 北京时间上月，§9.2）`); },
 /* —— 焊材 / 气体提取（**核对工具**；数据唯一去向 = 月度会大表）—— */
 fExtStatus:t=>{ fExt.status=t.value; render(); },
 fExtReset:()=>{ fExt.status='在建'; fExt.ym=bjMonth(-1); render(); toast(`已重置：项目状态回到「在建」、金额月份回到 <b>${tmLabel(fExt.ym)}</b>（§9.2）`); },
 /* 「结余」点格即改（2026-09-18 用户裁定 甲）：粒度 = **类别 × 仓库 · 不按月**（维护的是"当前的结存"）。
    ⭐ 接线：**判定与落库一律后端**（`service.save_balance_cell` ⇒ `extract.parse_balance`）——
      空 ⇒ 清空 / 非数字 / 负数 都由后端判，⛔ 前端不复写判据；
      ⛔ 也不本地改 `BAL_EX` 冒充落库：成功后**以后端为准重拉**（`reloadM07()`）。 */
 extBal:async t=>{ const kind=t.dataset.k, wh=t.dataset.p, raw=String(t.value==null?'':t.value).trim();
   const NAME=`结余（${kind} · ${wh}）`;
   let r=null;
   try{ r=await API.m07BalCell({kind:kind,warehouse:wh,raw:raw}); }
   catch(e){ return bgFailed(NAME,{message:String((e&&e.message)||e)}); }
   if(!r||r.ok===false) return bgFailed(NAME,r);
   await reloadM07();
   if(raw===''){ toast(`已清空 <b>${esc(NAME)}</b> ⇒ 导出里该格<b>如实留空</b>`); return; }
   toast(`已保存 <b>${esc(NAME)}</b> = ${M(r.value)}<br><span class="mut sm">历史结余 · 手工录入 —— 导出时按类别 × 仓库带上</span>`); },
 /* 导出：行 = **所筛选项目** · 列 = 项目 → 最早有数据的月 → …（逐月连续）→ 求和（用户口径） */
 expExt:()=>{ const ms=extMons();
   const blk=kind=>{ const list=extVisible(kind);
     const head=`<tr><th>项目</th>${ms.map(m=>`<th>${m}</th>`).join('')}<th>求和</th></tr>`;
     const body=list.length?list.map(w=>`<tr><td class="sm">${esc(w)}</td>${ms.map(m=>{const v=extMon(kind,w,m);return `<td class="num">${v?M(v):'<span class="mut">—</span>'}</td>`;}).join('')}<td class="num">${M(extTotal(kind,w))}</td></tr>`).join('')
       + sumRowOf(head, list, Object.assign({[ms.length+1]:rs=>N2(rs.reduce((a,w)=>a+extTotal(kind,w),0))},
           ...ms.map((m,i)=>({[i+1]:rs=>N2(rs.reduce((a,w)=>a+extMon(kind,w,m),0))}))))
       :EMPTYROW(ms.length+2, '当前筛选条件下没有'+kind+'数据', '换个「项目状态」或月份');
     return `<div class="tip" style="margin:calc(10px * var(--fscale)) 0 calc(6px * var(--fscale))"><b>${kind}</b> · 项目 × 月份</div><div class="tw"><table class="dt cond" data-sort-key="modal:expExt-${kind}"><thead>${head}</thead><tbody>${body}</tbody></table></div>`; };
   modal({title:'导出 · 焊材 / 气体提取（按 项目 × 月份）',body:
     `<div class="tip" style="margin-bottom:calc(8px * var(--fscale))">将导出 <b>1 个工作簿</b>（<b>2 个工作表</b>：<b>焊材</b> / <b>气</b>），每表 = <b>项目 | 结余 | 1月…12月 | 合计</b>（按模板填充）。<br>下表是<b>按月核对视图</b>（列 = <b>${ms[0]||'—'} → … → 求和</b>，自「最早有数据的月」起<b>逐月连续</b>），<b>不是</b>成品的列结构。</div>`+blk('焊材')+blk('气体'),
     footer:`<button class="btn" data-act="closeModal">关闭</button><button class="btn pri" data-act="saveExt">保存到本地</button>`}); },
 /* ⭐ 接线（`TAIL-04` 路径① · 片 1）：成品由**后端模板填充**生成（`模板-焊材气体.xlsx` 的两个 sheet）。
    失败时后端回 **JSON 200 ＋ `ok:false` ＋ 中文原因**（模板缺失/损坏 · 拿不到报告月 · **显示区对账不过**）
    ⇒ 据 `content-type` 分流：JSON ⇒ 弹原因；否则当文件下载。
    ⛔ 前端不自己拼文件名（命名规则的主人在后端，经 `X-Export-Filename` 带出）；
    ⚠️ 筛选**原样带给后端**（`status` / `period`）—— ⛔ 不在前端另筛一遍（否则又是第二份口径）。 */
 saveExt:async ()=>{
   const url='/api/m07/extract/export?status='+encodeURIComponent(fExt.status)
     +'&period='+encodeURIComponent(fExt.ym);
   const fn=await dlExport(url,{name:'焊材气体提取表.xlsx'});
   if(!fn) return;
   toast(`已导出 <b>${esc(fn)}</b>：<b>工作表 1</b> = 焊材、<b>工作表 2</b> = 气；每表 = 项目 | 结余 | 1月…12月 | 合计。` +
     `⚠️「结余」= <b>历史结余 · 由用户手工录入</b>（录入入口 = 本页「结余」列<b>点格即改</b>）；` +
     `<b>未录入 ⇒ 该格如实留空</b>（⛔ 不写 0）、<b>0 是合法录入值</b>`,8600); },
 /* 大表手填录入（OPEN-05）：当月未录入的格子先带入、再就地改正 → 转为本月正常录入。
    列型三种：`ym` 年月（`YYYY-MM`）· `m` 金额（元 · **非负**）· `t` 文本（备注）。手填值不参与欠款计算。 */
 bigEdit:async t=>{ const wh=t.dataset.p, i=+t.dataset.i, NAME=BIGCOLS[i], raw=String(t.value).trim();
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
     : `<b>${esc(NAME)}</b>已录入 <b>${show}</b>（${bjMonth(-1)}）`); },
 /* ---- 月度会大表「选择项目」：多选 + 自定义顺序（2026-09-13 用户口径）----
    弹窗内的操作只改**草稿** `BIGDRAFT`，点「确定」才写回 `BIGSET` —— 弹窗每步都重建 HTML，
    不备草稿层的话"勾一个就冲掉上一个"。 */
 bigPick:t=>{ if(!t||!t.dataset||t.dataset.keep!=='1') BIGDRAFT=BIGSET.slice();
   modal({ title:`选择项目 · 月度会大表的项目（已选 ${BIGDRAFT.length} / 候选 ${bigCands().length}）`,
     reopen:()=>ACT.bigPick({dataset:{keep:'1'},tagName:'BUTTON'}),
     body:`<div class="tip" style="margin-bottom:calc(8px * var(--fscale))">勾选要上表的项目；<b>已选的</b>可用 <b>↑ / ↓</b> 调顺序。点「确定」后 <b>大表 / 导出</b> 两处一律按这个顺序。</div>
       <div style="max-height:52vh;overflow:auto"><table class="dt cond" data-sort-key="modal:bigPick"><thead><tr><th style="width:34px">选</th><th style="width:40px">序</th><th>项目（候选 = 项目档案里「在建」的项目）</th><th style="width:82px">调顺序</th></tr></thead><tbody>
       ${bigCands().map(wh=>{ const k=BIGDRAFT.indexOf(wh), on=k>=0, p=pjRowOf(wh);
         return `<tr><td class="ctr"><input type="checkbox" data-act="bigSelTog" data-wh="${esc(wh)}"${on?' checked':''}></td>
         <td class="fc">${on?k+1:''}</td><td class="sm">${esc(p?pjDispOr(p,wh):wh)}</td>
         <td class="ctr now"><button class="btn sm" data-act="bigSelUp" data-wh="${esc(wh)}"${(on&&k>0)?'':' disabled'}>↑</button> <button class="btn sm" data-act="bigSelDown" data-wh="${esc(wh)}"${(on&&k<BIGDRAFT.length-1)?'':' disabled'} title="${(on&&k<BIGDRAFT.length-1)?'把这一行往下挪一位':'只有「选中了某一行」且它不是最后一行时才能下移'}">↓</button></td></tr>`; }).join('')}
       </tbody></table></div>`,
     footer:`<button class="btn" data-act="closeModal">取消</button><button class="btn dg" data-act="bigSelNone">清空</button><button class="btn pri" data-act="bigPickOk">确定</button>`}); },
 bigSelTog:t=>{ const wh=t.dataset.wh, k=BIGDRAFT.indexOf(wh);
   if(k>=0) BIGDRAFT.splice(k,1); else BIGDRAFT.push(wh);        /* 新勾选的**追加到末尾**（顺序可再调） */
   ACT.bigPick({dataset:{keep:'1'},tagName:'BUTTON'}); },
 bigSelUp:t=>{ const wh=t.dataset.wh, k=BIGDRAFT.indexOf(wh); if(k>0){ BIGDRAFT.splice(k,1); BIGDRAFT.splice(k-1,0,wh); }
   ACT.bigPick({dataset:{keep:'1'},tagName:'BUTTON'}); },
 bigSelDown:t=>{ const wh=t.dataset.wh, k=BIGDRAFT.indexOf(wh); if(k>=0&&k<BIGDRAFT.length-1){ BIGDRAFT.splice(k,1); BIGDRAFT.splice(k+1,0,wh); }
   ACT.bigPick({dataset:{keep:'1'},tagName:'BUTTON'}); },
 bigSelNone:()=>{ BIGDRAFT=[]; ACT.bigPick({dataset:{keep:'1'},tagName:'BUTTON'}); },
 /* ⚠️ 写回必须**原地替换内容**（`BIGSET.length=0` + push），**不能** `BIGSET=…` 重新赋值 ——
    外部（自检 / 导出）拿到的是这个数组的**引用**，重新赋值会让引用失效（同 BIGVAL / AWF 的教训）。 */
 bigPickOk:async ()=>{ const picked=BIGDRAFT.slice();
   /* ⭐ 接线：选择项目与顺序**落库走后端**（`big_service.save_selection`）—— 弹窗内仍是原型的草稿层 */
   let r = null;
   try{ r = await API.m07BigSelection(picked); }
   catch(e){ closeModal(); await reloadM07();
     return toast(`<b>选择项目没能保存</b>：${esc(String((e&&e.message)||e))}`,7000); }
   /* ⚠️⚠️ 2026-09-20 补：`m07` 对**可预期拒绝**回 **HTTP 200 ＋ `ok:false`**（全站口径）⇒ 不会抛。
      原先这里**只看 catch** ⇒ 失败时**照样往下走**、还 toast「已按所选 N 个项目出表」
      ⇒ **把失败说成成功，而且一句原因都不给**（这一处最坏：失败完全静默）。 */
   if(!r || r.ok === false){ closeModal(); await reloadM07();
     return toast(`<b>选择项目没能保存</b>：${esc((r && r.message) || '后端未返回原因')}`,7000); }
   closeModal(); await reloadM07();
   toast(`月度会大表已按所选 <b>${BIGSET.length}</b> 个项目出表（行序即刚才设置的行序）`); },

 /* ⭐ `TAIL-38`：录机械费（`m06` 的机械 6 列是**旁路载体**；原型没画入口 ⇒ §5.2.5 ③ 自行设计）。
    判定与落库**全在后端**：空 ⇒ 0、负数 / 非数字 ⇒ 拒且不写库（`mech_ui.parse_mech_values`）。
    ⭐⭐ 2026-09-26（`TAIL-107` · 用户裁定）：**手录只给正式段** —— 历史段（≤ 截止核算月）的机械费
      以**过程资料导入**的值为准。挡板在后端（`repository.save_mech`，唯一写出口）⇒ 这里只负责
      **提前说清**（守则 §5.5：不能做的要说明原因，⛔ 别让人填完才被拒）。 */
 mechOpen:()=>{ const cands=(typeof PROC_PJS==='object'&&PROC_PJS&&PROC_PJS.length)?PROC_PJS:bigCands();
   const wh=(mechWh&&cands.indexOf(mechWh)>=0)?mechWh:((cands.indexOf(procPj)>=0)?procPj:(cands[0]||''));
   mechWh=wh;
   const now=bjMonth(-1);                                  /* 材料报表类默认 = 北京时间上月（§9.2） */
   /* ⭐⭐ 2026-09-28（用户口径，第二次定稿）：形态 = **一张表、表头一行、数据只有一行** ——
      数据行 = 「**手动填的核算期** ＋ 机械 6 列（列名在后端，`MECH_LABELS`）」，一次填**一个核算期**。
      ⛔ 不再是"一屏列出好多个月份行"（那是我上一版理解错的形态，用户当场纠正："不要好多行了，就要一行"）。
      ⚠️ 核算期是**手动填**的输入框 ⇒ 改它必须**重开弹窗**把新月份那一刻的现值带出来
         （见 `mechYmSet`）—— ⛔ 只改输入框不重载的话，格子里的数还是旧月的 ⇒ 一点保存就**串月**。
      ⚠️ 表头**必须一行**（用户口径"每列的表头要在一行里"）⇒ 表头 `nowrap` ＋ 表格字号降到 11.5px。 */
   const ym=(mechYm&&/^\d{4}-\d{2}$/.test(mechYm))?mechYm:now;   /* 手动填的核算期优先；默认上月（§9.2） */
   mechYm=ym;
   const rowOf=()=>MECH_LABELS.map((_,j)=>{
     const a=mach6Arr(wh,ym); const v=(a&&a[j]!=null&&Number(a[j])!==0)?String(a[j]):'';
     return `<td><input class="inp num" style="width:100%;min-width:84px" data-act="mechCell" data-wh="${esc(wh)}" data-i="${j}" value="${esc(v)}" placeholder="0"></td>`;}).join('');
   modal({title:'录机械费 · 按核算月手录 6 列',wide:true,reopen:()=>ACT.mechOpen(),
     body:`<div class="tip" style="margin-bottom:calc(8px * var(--fscale))">机械 6 列是<b>旁路载体</b>：重抓 i8 / 重导历史<b>都不覆盖</b>它（§5.2.5 ③）。空 ⇒ 0；<b>负数 / 非数字一律拒绝且不写库</b>（判定在后端，原值不变）。<br>
       ⚠️ <b>手录只用于「正式段」</b>（核算月 <b>晚于</b>该项目的<b>截止核算月</b>）⇒ 本表<b>只列可手录的月份</b>；<b>历史段</b>（≤ 截止月）的机械费以<b>过程资料导入</b>的值为准（要改历史值请改 Excel 后重导）。</div>
       <div class="fbar plate">
         <div class="fi"><label>项目</label><select class="inp" id="mechPj" data-act="mechPjPick">${cands.map(k=>`<option value="${esc(k)}"${k===wh?' selected':''}>${esc(k)}</option>`).join('')||'<option value="">（没有候选项目）</option>'}</select></div>
         <span class="mut sm" style="margin:0">一次填<b>一个核算期</b>的 6 列（改核算期 ⇒ 重开并带出该月现值）· 改完点右下「保存」</span>
         </div>
         <div style="overflow-x:auto">
         <table class="dt cond" style="font-size:calc(11.5px * var(--fscale))">
           <thead><tr><th style="white-space:nowrap">核算期</th>${MECH_LABELS.map(nm=>`<th style="white-space:nowrap">${esc(nm)}</th>`).join('')}</tr></thead>
           <tbody><tr><td><input class="inp" id="mechYm" data-act="mechYmSet" style="min-width:88px" value="${esc(ym)}" placeholder="YYYY-MM" title="手动填核算期（YYYY-MM）—— 填完会重新带出该月现值"></td>${rowOf()}</tr></tbody></table></div>`,
     footer:`<span class="mut sm" style="align-self:center">只提交<b>改动过</b>的月份</span><button class="btn" data-act="closeModal" style="margin-left:auto">取消</button><button class="btn pri" data-act="mechOk">保存</button>`}); },
 /* ⭐ 换项目 = **重开弹窗重载该项目的月份与已有值** —— ⛔ 别只改下拉不重载：那张表还是上一个项目的数据，
    一点保存就会把**上一个项目的值写进新项目**（串数据）。⚠️ 先 `closeModal()` 再开，⛔ 不许直接叠加。 */
 mechPjPick:t=>{ mechWh=String((t&&t.value)||''); closeModal(); ACT.mechOpen(); },
/* ⭐ 手动改核算期 ⇒ **关掉重开**（把新月份那一刻的现值带出来）—— ⛔ 不能只改输入框：
   格子里的数还是旧月份的，一点保存就把**旧月的值写进新月**（串数据）。 */
mechYmSet:t=>{ const v=String((t&&t.value)||'').trim();
  if(!/^\d{4}-\d{2}$/.test(v)) return toast('核算期要写成 <b>YYYY-MM</b>（例：2026-09）');
  mechYm=v; closeModal(); ACT.mechOpen(); },
 mechOk:async ()=>{ const cells=[...document.querySelectorAll('[data-act="mechCell"]')];
   if(!cells.length) return toast('这一屏没有可手录的核算月');
   /* ⭐ 项目名取**表格自己带的那份**（`data-wh`，渲染时写死）—— ⛔ 别取下拉框的当前值：
      下拉若已换、表还是旧项目的数，就会把**旧值写进新项目**（串数据）。 */
   const wh=String(cells[0].dataset.wh||'');
   const ym=String(((document.getElementById('mechYm')||{}).value)||'').trim();
   if(!/^\d{4}-\d{2}$/.test(ym)) return toast('核算期要写成 <b>YYYY-MM</b>（例：2026-09）—— 没有提交任何值');
   const values={};
   cells.forEach(el=>{ values['mech_'+(el.dataset.i||'0')]=String(el.value==null?'':el.value); });
   /* ⭐ 形态 = **一行 = 一个核算期**（用户口径）⇒ 只有一个月要提交；下游（挡板 / 保存 / 提示）照旧按月那套走。 */
   const yms=[ym], byYm={}; byYm[ym]=values;
   /* ⛔ **本地兜底**拦住"往历史段手录"（后端也会拒 —— 但那时用户已经填完 6 格了）；
      判据只认后端给的段（`MECH_SECTIONS`，⛔ 壳里不许自己拿截止月比大小）。 */
   const bad=yms.find(ym=>((MECH_SECTIONS[wh]||{})[ym]||'')==='history');
   if(bad){ return toast(`<b>${esc(bad)} 不能手录</b>：<b>${esc(wh)}</b> 的这个月属<b>历史段</b> —— 历史段的机械费以<b>过程资料导入</b>的值为准（要改请改 Excel 后重导）；手录只在<b>正式段</b>（截止核算月之后）用。`,8000); }
   let ok=0, fail='';
   for(const ym of yms){
     let r = null;
     try{ r=await API.m06MechSave({warehouse:wh,ym:ym,values:byYm[ym]}); }
     catch(e){ fail=`${ym}：${String((e&&e.message)||e)}`; break; }
     /* ⚠️⚠️ 2026-09-20 补：原来写的是 `toast((r&&r.message)||'已保存')` ——
        若那次 `ok:false` **恰好没带 `message`** ⇒ 会把**失败显示成「已保存」**（真假成功）。
        ⛔ 别拿"有没有 message"当成败判据；**成败只看 `ok`**。 */
     if(!r || r.ok === false){ fail=`${ym}：${(r && r.message) || '后端未返回原因'}`; break; }
     ok++;
   }
   await reloadMech(); await reloadM07();
   /* 部分失败：**不关弹窗**（用户填的那些还在，改完重按保存即可），并说清"到哪个月为止成功了" */
   if(fail){ render(); return toast(`<b>保存中断</b>（已成功 <b>${ok}</b> / ${yms.length} 个月）：${esc(fail)}`,8000); }
   closeModal(); render();
   toast(`已保存 <b>${ok}</b> 个核算月的机械费（${esc(yms[0])}${yms.length>1?` ~ ${esc(yms[yms.length-1])}`:''}）`); },

 /* —— MOD-08 —— */
 /* 「项目」筛选（**通用控件** = 共用项目面板，**多选**；2026-09-13 用户口径）—— 键 = 仓库名（§2.7.4）。 */
 invWhToggle:()=>{ pjToggle('invWh'); render(); },
 invWh:t=>{ const v=t.dataset.pj; const k=invWhs.indexOf(v); if(k>=0) invWhs.splice(k,1); else invWhs.push(v); render(); },
 invWhAll:()=>{ invWhs.length=0; PROC_PJS.forEach(v=>invWhs.push(v)); render(); },   /* 同款：候选必须与数据源一致（原用演示 `WHs`） */
 invWhNone:()=>{ invWhs.length=0; render(); },
 /* —— 「每列可筛」（Excel 式）—— 全部**从动作进去**；其中 4 个挂在表单元素上 ⇒ 由 `change` 委托直呼
   （⭐ `#2` 2026-09-26 起**没有名单**，⛔ 不必也不许再往哪儿登记） —— */
 ivColOpen:t=>{ const c=String(t.dataset.c); invColOpen=(invColOpen===c?'':c); render(); },
 ivColClose:()=>{ invColOpen=''; render(); },
 ivColClear:t=>{ delete fIvCol[String(t.dataset.c)]; render(); },
 ivColClearAll:()=>{ fIvCol={}; invColOpen=''; render(); toast('已清除全部列筛选'); },
 ivColQ:t=>{ const c=String(t.dataset.c); (fIvCol[c]=fIvCol[c]||{}).q=String(t.value==null?'':t.value).trim(); render(); },
 ivColMin:t=>{ const c=String(t.dataset.c); (fIvCol[c]=fIvCol[c]||{}).min=String(t.value==null?'':t.value).trim(); render(); },
 ivColMax:t=>{ const c=String(t.dataset.c); (fIvCol[c]=fIvCol[c]||{}).max=String(t.value==null?'':t.value).trim(); render(); },
 ivColVal:t=>{ const c=String(t.dataset.c), v=t.dataset.v; const f=(fIvCol[c]=fIvCol[c]||{}); f.v=f.v||[]; const k=f.v.indexOf(v); if(k>=0) f.v.splice(k,1); else f.v.push(v); render(); },
 invOnlyAdj:t=>{ invOnlyAdj=t.value==='1'; render(); },
 clearInvAdj:()=>{ invOnlyAdj=false; invWhs.length=0; fIvCol={}; invColOpen=''; render(); toast('已清除筛选，显示全部行'); },
 adjDlg:t=>{ const iv=IVs.find(x=>x.id===t.dataset.iv), a=adjOf(iv);
   modal({title:`调整单 · ${iv.docNo} #${iv.seq}`,body:
     kvBlock([['物料',`${esc(iv.mat)} ${esc(iv.spec)}`],['仓库',esc(iv.wh)],['项目全名',`<span style="font-size:calc(11.5px * var(--fscale))">${esc(iv.pf)}</span>`],['i8 原始金额',`<span class="fc">${M(iv.amt)}</span>`]])
    +`<div class="f2"><div class="fld"><label>调整后金额 <b>*</b></label><input class="inp num" id="adjAmt" value="${(a?a.newAmt:iv.amt).toFixed(2)}"></div>
      <div class="fld"><label>差额</label><input class="inp num" id="adjDiff" readonly value="0.00"></div></div>
     <div class="fld"><label>调整备注 <b>*</b></label><input class="inp" id="adjRemark" value="${esc(a?a.remark:'')}" placeholder="说明为什么调"></div>
     ${a?`<div class="tip" style="margin:0"><b>留痕：</b>${a.trail.map(x=>`${x.field} ${M(x.before)} → ${M(x.after)}`).join('；')}<br><b>操作人 / 时间：</b>${esc(a.op)} · ${a.time}</div>`:'<div class="tip wn" style="margin:0">调整单<b>打在单据行上</b>，<b>不被 i8 导出覆盖</b>，必须留痕 + 留备注。</div>'}`,
     footer:`<button class="btn" data-act="closeModal">取消</button>${a?'<button class="btn dg" data-act="adjDel" data-iv="'+iv.id+'">撤销调整单</button>':''}<button class="btn pri" data-act="adjOk" data-iv="${iv.id}">保存调整单</button>`});
   setTimeout(()=>{ const f=$('#adjAmt'),g=$('#adjDiff'); if(f&&g){ f.oninput=()=>g.value=SIG(N2(parseFloat(f.value)||0)-iv.amt); f.dispatchEvent(new Event('input')); } },0); },
 /* ⭐ **已接后端**：判定与落库一律后端（`POST /api/m08/adjust`）——
    前端只提交「调整后金额 ＋ 备注」，**判据不在前端复写**（金额 ≥ 0 / 备注必填
    由 `domain.adjustment_problem` 一把管）⇒ 失败时把**后端的原因原样**给用户。
    ⚠️ 「留痕」的改前 / 改后 / 操作人 / 时间全部由后端出（前端算不出来）。 */
 adjOk:async t=>{ const iv=IVs.find(x=>x.id===t.dataset.iv); if(!iv) return;
   const v=String($('#adjAmt').value||'').trim(), rs=$('#adjRemark').value.trim();
   closeModal();
   await ivAct(()=>API.m08Adjust(iv.id,{amount:v,remark:rs}),
     r=>`调整单已保存：${esc(iv.docNo)} #${esc(iv.seq)} ${M(iv.amt)} → <b>${M(r.amount)}</b>（已留痕）<br>过程资料「调整后表」与「差异表」已同步更新`); },
 /* ⭐ 已接后端：撤销调整单（回到 i8 原始金额）—— 落点 `POST /api/m08/adjust/clear`。
    ⚠️ 调整单与 `inv_detail` **物理分离** ⇒ 撤销只删调整单，原始数据本来就没被动过。 */
 adjDel:async t=>{ const iv=IVs.find(x=>x.id===t.dataset.iv); if(!iv) return;
   closeModal();
   await ivAct(()=>API.m08AdjustClear(iv.id), ()=>`已撤销该调整单，<b>原始数据未受影响</b>（回到 i8 值）`); },
 /* `reimport`（「重新导入 i8 数据」按钮）已按用户 2026-09-13 口径**删除**（原话："没啥用，删了吧"）。
    它演示的「重导不覆盖调整单」这条口径本身仍然成立（§9.5 幂等 / `ENT-04`），只是不再单独设按钮。 */

  /* —— MOD-09（手填项**按「核算年月 ＋ 项目」各存一份**：写路径都落在「当前所选核算年月 · 当前所选项目」那一份上） —— */
  /* 「项目」**单选**面板（第 6 个 `projPanel` 调用点）：点一下即切换并收起（与 `MOD-06` 同款） */
  awfPjToggle:()=>{ pjToggle('awfPj'); render(); },
  awfPjPick:t=>{ const v=t.dataset.pj; if(!v) return; awfPj=v; pjClose('awfPj');
    /* ⭐ 切项目 ⇒ **按 (核算年月, 项目) 重取那一份**（手填项是"每项目每月各存一份"，§5.5） */
    reloadM09().then(()=>toast(`特殊费用月报表已切到项目 <b>${esc(PROJ_META_KEY(v).nm)}</b>（自动项与手填项都只算该项目）`)); },
  /* ⭐ 接线：四个写动作**全部走后端**（`/api/m09/fee/*` —— 2026-09-19 `§19` 批 2 起旧 PRG 端点
     `/m09/add` `/m09/cell` **已随旧页删除**，这条 API 就是**唯一出口** `service.act_*`）——
     ⛔ 前端不再本地改数据冒充落库（原先直接改本地的那个演示容器），也**不在前端复写判定**。
     回执里的中文说明（含 §引用）**原样给用户**，失败亦然。 */
  awfAdd:()=>awfAct(()=>API.m09Add({ym:awfYm, project:awfPj}), r=>r.message
    || `已在 <b>${tmLabel(awfYm)}</b> · <b>${esc(PROJ_META_KEY(awfPj).nm)}</b> 增加手填项：<b>名称可改、金额可填</b>（§5.5）`),
  /* `R9`：删除也要说清「做了什么 + 影响多少」—— 后端回执里**带重算后的合计** */
  awfDel:t=>awfAct(()=>API.m09Delete({ym:awfYm, project:awfPj, index:+t.dataset.i}), r=>r.message),
  awfName:t=>awfAct(()=>API.m09Name({ym:awfYm, project:awfPj, index:+t.dataset.i, value:t.value}), r=>r.message),
  /* ⚠️ **前端不判金额合法与否** —— §5.5 的判据唯一出口是后端 `domain.amount_problem`
     （只拦"非数字"、**允许 0 与负数**）；前端再写一遍 = 第二份口径。
     非法 ⇒ 后端拒绝且**原值不变**，重拉后输入框回到库里那个值。 */
  awfAmt:t=>awfAct(()=>API.m09Amount({ym:awfYm, project:awfPj, index:+t.dataset.i, value:t.value}), r=>r.message),
  /* 重置 = 回到默认核算年月 ＋ 默认项目（候选第一个）—— `R4` 要求列表 / 报表页提供「重置」 */
  /* ⭐⭐ `TAIL-156` `P2`：**月度批量录入**（用户口径「一次录好几个月太麻烦」）——
     列 = 本页当前那一份（`awfYm × awfPj`）的**项名**（⛔ 弹窗里不建新项名：项名只认页面那一处定义）；
     行 = **最近 12 个核算月**（止月 = 本页当前核算年月）；填完**一次提交**（`POST /api/m09/fee/batch`）。
     ⚠️ 三件必须**提前说清**（守则 §2.4 / §5.5）：**空格子一律不写**（空 ≠ 0）· **有一个非法金额 ⇒ 整批不写** ·
       已有「同月 + 同名」⇒ **改它的值**（⛔ 不是再添一条）。 */
  awfBatch:()=>{ const rows=awfList();
    if(!rows.length) return toast('<b>这一份还没有项名</b> —— 先在页面上点「＋ 增加手填项」把项名建好，再回来批量填（项名只认页面这一处）',9000);
    const names=rows.map(r=>String(r[0]==null?'':r[0]));
    const end=awfYm||bjMonth(-1);
    /* ⭐ 默认**只 3 行**（用户口径「我不需要那么多行，行的数量要能自定义」）——
       不够点「＋ 加一行」、多了点「－ 减一行」（见 `awfRowAdd`/`awfRowDel`，都是**纯 DOM 插删行**，
       ⛔ 不重排整张表 —— 重排会把已经填好的格子冲掉）。 */
    const months=Array.from({length:3},(_,k)=>ymAdd(end,k-2));
    /* ⭐⭐ 核算期**每一行都能手填**（用户口径「这个核算期要能自定义」）—— 默认值仍是最近 12 个月，
       但可以把任意一行改成任何月份（跨年 / 跳月都行）。
       ⛔ 不搞"起止月区间"那种控件：那要重排表格 ⇒ **填了一半被重排**最难查（已填的值也会丢）。
       直接改行头最省事，且已填的格子一个都不动。 */
    const ymCell=m=>`<td style="white-space:nowrap"><input class="inp" data-act="awfYmCell" style="min-width:96px" value="${esc(m)}" placeholder="YYYY-MM" title="这一行的核算期，可直接改（YYYY-MM）">${m===end?'<span class="mut sm"> · 本页</span>':''}</td>`;
    /* ⚠️ 格子**不带行号**（`data-r` 已删）：行是**可插可删**的（见 `awfRowAdd`），保存时按
       `closest('tr')` **逐行读**才不会被插删打乱 —— ⛔ 别再用"第几个格子"这种位置概念。 */
    const cell=(m,i)=>`<td><input class="inp num" style="width:100%;min-width:92px" data-act="awfCell" data-nm="${esc(names[i])}" value="${esc(m===end?String((rows[i]||[])[1]==null?'':(rows[i]||[])[1]):'')}" placeholder="—"></td>`;
    modal({title:'特殊费用 · 按月批量录入',wide:true,reopen:()=>ACT.awfBatch(),
      body:`<div class="tip" style="margin-bottom:calc(8px * var(--fscale))">列 = <b>本页这一份（${esc(awfYm)} · ${esc(PROJ_META_KEY(awfPj).nm)}）的项名</b>，行 = <b><u>默认 3 行，行数随点随加减</u></b>（不够点「＋ 加一行」、多了点「－ 减一行」）· <b>每一行的核算期都能直接改</b>（止月 = 本页当前核算年月；那一行的金额会预填现值）。<br>
        ⚠️ <b>空格子一律不写</b>（空 ≠ 0，⛔ 不会替你写 0）· <b>只要有一个非法金额 ⇒ 整批都不写</b>（原值不动）· 已有「<b>同月 + 同名</b>」的行 ⇒ <b>改它的金额</b>（⛔ 不是再添一条）。<br>
        ⛔ 这里<b>不新建项名</b>：要加项名请回页面「＋ 增加手填项」（项名只认页面那一处定义）。</div>
        <div style="overflow:auto;max-height:52vh">
          <table class="dt cond" id="awfTbl" style="font-size:calc(11.5px * var(--fscale))">
            <thead><tr><th style="white-space:nowrap">核算期</th>${names.map(nm=>`<th style="white-space:nowrap">${esc(nm||'（未命名）')}</th>`).join('')}</tr></thead>
            <tbody>${months.map(m=>`<tr>${ymCell(m)}${names.map((_,i)=>cell(m,i)).join('')}</tr>`).join('')}</tbody>
          </table></div>
        <div class="fbar plate" style="margin-top:calc(8px * var(--fscale))">
          <span class="mut sm" style="margin:0">行数可以<b>随时加减</b>（默认 3 行）—— 不够就「＋ 加一行」，多了就「－ 减一行」（⛔ 已填的格子不会被冲掉）</span>
          <span style="margin-left:auto;display:flex;gap:calc(6px * var(--fscale))">
            <button class="btn sm" data-act="awfRowAdd">＋ 加一行</button>
            <button class="btn sm" data-act="awfRowDel">－ 减一行</button></span>
        </div>`,
      footer:`<span class="mut sm" style="align-self:center">空格子<b>不写</b> · 一个非法 ⇒ <b>整批不写</b></span><button class="btn" data-act="closeModal" style="margin-left:auto">取消</button><button class="btn pri" data-act="awfBatchOk">保存</button>`}); },
  awfBatchOk:async ()=>{ const trs=[...document.querySelectorAll('#awfTbl tbody tr')];
    if(!trs.length) return toast('这一屏没有可填的格子');
    /* ⭐ 逐行读（行是**可插可删**的 ⇒ ⛔ 别按"第几个格子"定位，那会被插删打乱）；
       ⭐ 核算期每行可手填 ⇒ 提交前**先按行校验**：认不出的（空 / 不是 `YYYY-MM`）**整批退回**；
       ⚠️ 但只在**该行真的填了金额**时才拦 —— 整行都空 = 用户没打算录那一行 ⇒ 跳过不算错
          （守则 §2.4：要求与后果提前说；§5.5：不能提交的要**说清原因**，⛔ 别让人填完才被拒）。 */
    const items=[], months=[];
    for(let k=0;k<trs.length;k++){
      const tr=trs[k], yEl=tr.querySelector('[data-act="awfYmCell"]');
      const raw=String((yEl&&yEl.value)||'').trim();
      const vals={}; let has=false;
      tr.querySelectorAll('[data-act="awfCell"]').forEach(el=>{
        const nm=String(el.dataset.nm||''), v=String(el.value==null?'':el.value);
        if(!items.includes(nm)) items.push(nm);
        vals[nm]=v; if(v.trim()!=='') has=true; });
      if(!raw && !has) continue;
      if(!/^\d{4}-\d{2}$/.test(raw)) return toast(`<b>第 ${k + 1} 行的核算期认不出</b>（要写成 <b>YYYY-MM</b>，例：2026-09）—— 这一批<b>一格都没写</b>`,9000);
      months.push({ym:raw, values:vals});
    }
    if(!months.length) return toast('整张表都是空的 —— 没有要写的内容（⛔ 不会替你写 0）');
    if(!items.length) return toast('没有项名可写 —— 先在页面上把项名建好');
    let r=null;
    try{ r=await API.m09Batch({project:awfPj, items:items, months:months}); }
    catch(e){ return toast(`<b>没能保存</b>：${esc(String((e&&e.message)||e))}`,7000); }
    /* ⚠️ 同 `mechOk` / `awfAct` 那条教训：**成败只看 `ok`**（⛔ 别拿"有没有 message"当判据 —— 那会把失败显示成"已保存"）。 */
    if(!r || r.ok === false) return toast(`<b>没能保存</b>：${esc((r&&r.message)||'后端未返回原因')}`,9000);
    closeModal(); await reloadM09(); render();
    toast(esc(r.message||'已保存（按「月 + 项名」幂等写入）')); },
  /* ⭐ 行数自定义（用户口径「我不需要那么多行，行的数量要能自定义」）——
     ⛔ 不走"重排整张表"（那会把你**已经填好的格子冲掉**）：就是**往表里插一行 / 删一行**（纯 DOM）。
     新行的核算期 = 最后一行的**下一个月**（不合意就地改 —— 每行核算期本来就能手填）。 */
  awfRowAdd:()=>{ const tb=document.querySelector('#awfTbl tbody');
    const trs=tb?[...tb.querySelectorAll('tr')]:[];
    if(!trs.length) return;
    const last=trs[trs.length-1], yEl=last.querySelector('[data-act="awfYmCell"]');
    const cur=String((yEl&&yEl.value)||'').trim();
    const clone=last.cloneNode(true);
    clone.querySelectorAll('input').forEach(el=>{
      if(el.dataset.act==='awfYmCell') el.value=/^\d{4}-\d{2}$/.test(cur)?ymAdd(cur,1):cur;
      else el.value=''; });
    tb.appendChild(clone); },
  awfRowDel:()=>{ const tb=document.querySelector('#awfTbl tbody');
    const trs=tb?[...tb.querySelectorAll('tr')]:[];
    if(trs.length<=1) return toast('只剩一行了 —— 至少留一行（要清空就把格子里填的删掉）');
    trs[trs.length-1].remove(); },
  awfReset:()=>{ awfYm=bjMonth(-1); awfPj=AWF_PJS[0]||''; pjClose('awfPj');
    reloadM09().then(()=>toast(`特殊费用月报表已重置：核算年月回到 <b>${tmLabel(bjMonth(-1))}</b>、项目回到 <b>${esc(PROJ_META_KEY(awfPj).nm)}</b>（材料报表类默认 = 上月，§9.2）`)); },

 /* —— MOD-05 · 逐月欠款台账（2026-09-12 用户口径）——
    两台账**左右并排**（左辅材 / 右机械）、**共用同一个「项目」选择器**、**同一套逻辑**，
   只有「其他支出金额」的取数不同（见 `ledSettle`）；**没有「切换口径」动作**（两侧同时在场）。
    ⚠️「机械」口径下的手填值原先是 MOD-10 的 `machAmt`（按项目一个数）——已升格为**按月**，
       故本动作取代它；MOD-10 改为只读合计。 */
 /* 台账「项目」= 共用面板（单选）：开/收 + 选（选谁都切两侧，语义与原来的下拉一致） */
 ledPjToggle:()=>{ pjToggle('ledPj'); render(); },
 ledPjPick:t=>{ const v=(t&&t.dataset&&t.dataset.pj)||''; if(!v) return; ledProj=v; pjClose('ledPj'); render(); },
 /* ⭐⭐ 2026-09-20 用户定：**总欠款导出** —— 每个项目一行：
    **A 序号 · B 项目展示名 · C 集采 · D 辅材 · E 机械**（⛔ 列序是用户指定的，别"顺手优化"）。
    ⚠️ 后端**失败时回 JSON 200 ＋ `ok:false` ＋ 中文**（一条都算不出来）⇒ 必须**先看 `content-type`**，
       否则会把一段 JSON 当成 xlsx 存下来（用户拿到一个打不开的文件、还不知道为什么 · 同 `procExpSave`）。
    ⚠️ 文件名的**主人是后端**（`X-Export-Filename`），⛔ 壳里不自己拼。
    ⚠️ 口径提示一起说出去：**「机械」未含机械费结算**（该来源未接通）—— 表尾也写了同一句。 */
 /* ---- 「导出总欠款」的**选择项目**（2026-09-28 用户口径："像月度会大表那样"）----
    ⚠️ 与月度会大表那套的**唯一区别**：**不落库** —— 只决定"这一次导出的行集与行序"。
    空 = 全部（保持老行为）。交互结构照 `bigPick`（勾选 + ↑/↓ 调序 + 草稿层），⛔ 两处口径别各写一套。 */
 debtPick:t=>{ const keep=t&&t.dataset&&t.dataset.keep==='1';
   if(!keep) DEBTDRAFT=(DEBTPICK.length?DEBTPICK.slice():debtCands().slice());
   modal({ title:`选择项目 · 导出总欠款要包含哪些项目（已选 ${DEBTDRAFT.length} / 候选 ${debtCands().length}）`,
     reopen:()=>ACT.debtPick({dataset:{keep:'1'},tagName:'BUTTON'}),
     body:`<div class="tip" style="margin-bottom:calc(8px * var(--fscale))">勾选要导出的项目；<b>已选的</b>可用 <b>↑ / ↓</b> 调顺序（<b>导出的行序就是这个</b>）。<b>全清空 = 全部项目</b>（与原来的行为一致）。</div>
       <div style="max-height:52vh;overflow:auto">${TBL({cls:'cond',key:'modal:debtPick',sort:false,head:'<th style="width:34px">选</th><th style="width:40px">序</th><th>项目（候选 = 项目档案全部，含归档）</th><th style="width:82px">调顺序</th>',
       rows:debtCands().map(wh=>{ const k=DEBTDRAFT.indexOf(wh), on=k>=0, p=pjRowOf(wh);
         return `<tr><td class="ctr"><input type="checkbox" data-act="debtPickTog" data-wh="${esc(wh)}"${on?' checked':''}></td>
         <td class="fc">${on?k+1:''}</td><td class="sm">${esc(p?pjDispOr(p,wh):wh)}</td>
         <td class="ctr now"><button class="btn sm" data-act="debtPickUp" data-wh="${esc(wh)}"${(on&&k>0)?'':' disabled'}>↑</button> <button class="btn sm" data-act="debtPickDown" data-wh="${esc(wh)}"${(on&&k<DEBTDRAFT.length-1)?'':' disabled'} title="${(on&&k<DEBTDRAFT.length-1)?'把这一行往下挪一位':'只有「选中了某一行」且它不是最后一行时才能下移'}">↓</button></td></tr>`; })})}</div>`,
     footer:`<button class="btn" data-act="closeModal">取消</button><button class="btn dg" data-act="debtPickNone">全清空（= 全部）</button><button class="btn" data-act="debtPickAll">全选</button><button class="btn pri" data-act="debtPickOk">确定</button>`}); },
 debtPickTog:t=>{ const wh=t.dataset.wh, k=DEBTDRAFT.indexOf(wh);
   if(k>=0) DEBTDRAFT.splice(k,1); else DEBTDRAFT.push(wh);       /* 新勾选追加到末尾（顺序可再调） */
   ACT.debtPick({dataset:{keep:'1'},tagName:'BUTTON'}); },
 debtPickUp:t=>{ const wh=t.dataset.wh, k=DEBTDRAFT.indexOf(wh); if(k>0){ DEBTDRAFT.splice(k,1); DEBTDRAFT.splice(k-1,0,wh); }
   ACT.debtPick({dataset:{keep:'1'},tagName:'BUTTON'}); },
 debtPickDown:t=>{ const wh=t.dataset.wh, k=DEBTDRAFT.indexOf(wh);
   if(k>=0&&k<DEBTDRAFT.length-1){ DEBTDRAFT.splice(k,1); DEBTDRAFT.splice(k+1,0,wh); }
   ACT.debtPick({dataset:{keep:'1'},tagName:'BUTTON'}); },
 debtPickAll:()=>{ DEBTDRAFT=debtCands().slice(); ACT.debtPick({dataset:{keep:'1'},tagName:'BUTTON'}); },
 debtPickNone:()=>{ DEBTDRAFT=[]; ACT.debtPick({dataset:{keep:'1'},tagName:'BUTTON'}); },
 debtPickOk:()=>{ DEBTPICK=DEBTDRAFT.slice(); closeModal(); render();
   return toast(DEBTPICK.length
     ? `「导出总欠款」已按所选 <b>${DEBTPICK.length}</b> 个项目（<b>行序 = 你刚设的顺序</b>）—— 点「导出总欠款」即可`
     : `「导出总欠款」= <b>全部项目</b>（按项目名排序；这也是原来的行为）`, 8000); },

 debtExpAll:async ()=>{
   /* ⭐⭐ 2026-09-28 修（用户走查报障「导出总欠款点击没反应」）：原写法把**未声明的标识符 `url`**
      当 `dlExport` 的第一个参数（`url` 只在别处的局部作用域里）⇒ `ReferenceError`；而本动作是 `async`
      ⇒ 异常变成**未捕获的 promise rejection** ⇒ 界面**毫无反应**（连报错都不给）。
      ⛔ 本注释**刻意不写那句代码字面** —— 写了会被 `tests/test_wired_m05.py` 的判据当成真代码命中（实测踩到）。
      ⚠️ 端点的**唯一出处** = 后端 `mod05_flow/router.py` 的 `GET /api/m05/debt/export`（⛔ 别在壳里拼路径）；
      ⭐ 2026-09-28 同批：带 `projects=`（**顺序即行序**）—— 空 = 全部（老行为）。 */
   const base='/api/m05/debt/export';
   const url=DEBTPICK.length? base+'?projects='+encodeURIComponent(DEBTPICK.join(',')) : base;
   const fn=await dlExport(url,{name:'总欠款.xlsx'});
   if(!fn) return;
   return toast(`已导出 <b>${esc(fn)}</b>：每项目一行（${DEBTPICK.length?`按所选 <b>${DEBTPICK.length}</b> 个项目、行序 = 你设的顺序`:'全部项目、按项目名排序'}）· C 集采 / D 辅材 / E 机械`
     + `<br><span class="sm mut">⚠️「机械」未含机械费结算（该来源未接通）—— 表尾也写了这一句</span>`, 11000);
 },
 /* —— 「导出逐月欠款台账」展开区（2026-09-13 用户口径：一个入口 + 多选项目 + 每项目一簿三表）—— */
 ledExpToggle:()=>{
  /* ⭐ 2026-09-28（用户口径"按着 m06 那个也改"）：**一次点到位** —— 点这个卡头按钮 = 展开区 ＋
     ① 那个「项目（可多选）」面板**一起开**（原先只开展开区，用户还得自己再找一次那个按钮）；再点一次 = 一起收。
     ⚠️⚠️ **这里不能照搬 m06 那条"开 / 关判据只看面板状态"** —— m05 的面板挂在**展开区里**（不在这个按钮上），
        ⇒ **点卡头按钮本身就等于"点到浮层外面"**，通用收起逻辑会先把面板关掉，此时再按面板状态取反
        ⇒ **永远只能开、收不掉**（真机 `㉚-④′` 实测抓到：「收起后按钮仍带 on（cls='btn pri on'）—— 状态不真实」）。
        ⇒ 判据仍用 `ledExpOn` —— 它代表"**展开区是否可见**"，与这个按钮控制的**正好是同一件事**（所以它不叫走散）；
        面板只是**跟着**开 / 关。 */
  ledExpOn=!ledExpOn;
  if(ledExpOn){ PJ_OPEN['ledExpPj']=true; } else pjClose('ledExpPj');
   /* 首次打开：**默认选中本页当前所选项目**（用户口径"要想办法实现自选项目"，默认值取当前是为了少点一下） */
   if(ledExpOn&&!ledExpPjs.length){ const c=ledCur(); ledExpPjs=c?[c]:[]; }
   render();
   /* ⭐ 2026-09-28（`TAIL-142`）：这条原来挂的是 **6200ms 的长 toast** —— 把「导出形态 / 哪几个工作表 / 打包规则」
     整套机制说明弹在屏幕角上：它和面板里那两行说明**重复**，还长时间占着屏幕（守则 §3.4 冗余 · §5.9 说明要贴在对象旁）。
     ⇒ 说明留在面板里（`ledExpStrip`），toast 只说"点上了"这一件（§5.5 反馈）。 */
   if(ledExpOn) toast('已展开「导出台账」：默认选中<b>本页当前项目</b>（可多选）'); },
 ledExpPjToggle:()=>{ pjToggle('ledExpPj'); render(); },
 ledExpPjPick:t=>{ const v=(t&&t.dataset&&t.dataset.pj)||''; if(!v) return;
   const i=ledExpPjs.indexOf(v); if(i>=0) ledExpPjs.splice(i,1); else ledExpPjs.push(v); render(); },
 ledExpPjAll:()=>{ ledExpPjs=ledProjs().slice(); render(); },
 ledExpPjNone:()=>{ ledExpPjs=[]; render(); },
 ledExpCancel:()=>{ ledExpOn=false; pjClose('ledExpPj'); ledExpPjs=[]; render(); toast('已收起导出面板（<b>未导出任何文件</b>）'); },
 ledExpOk:()=>{ const pjs=ledExpPjs.slice(); if(!pjs.length) return toast('请先选择要导出的项目');
   /* ⚠️ 报告月 = **材料报表类默认 = 上月**（§9.2）：台账/特殊费用月报表都**没有「止月」选择器**
      （台账跨月连续、特殊费用月报表是单月列由系统生成）⇒ 这里的「当前年月」就是上月。
      （2026-09-18 修正：原写 `bjMonth()` = 当月，与 §9.2 及后端默认不一致。） */
   const ym=bjMonth(-1), fnOf=k=>`${pjLabel(k)}_欠款台账_${ym}.xlsx`;
   /* ⭐ 2026-09-20 用户裁定：导出清单弹窗里的表**要可排序**（判据 `ACC-X-EXP-001/001-06`）。
      ⚠️ 开关是 **`data-sort`**、`data-sort-key` 只是**身份** —— 两个都要（理由见 `procExpOk` 那段，⛔ 不复述）。 */
   const body = pjs.length===1
     ? `<div class="tip" style="margin:0">将生成 <b>1 个工作簿</b>：<span class="fc">${esc(fnOf(pjs[0]))}</span><br>工作簿内 <b>3 个工作表</b>：<b>辅材欠款</b> · <b>机械欠款</b> · <b>特殊费用月报表</b></div>`
     : `<div class="tip" style="margin:0">选了 <b>${pjs.length}</b> 个项目 ⇒ 打成一个 <b>zip</b>：<span class="fc">逐月欠款台账_${ym}.zip</span>，内含 <b>${pjs.length}</b> 个工作簿（每个 <b>3 个工作表</b>）。</div>
        ${TBL({cls:'cond',key:'modal:ledExp',sty:'margin-top:calc(8px * var(--fscale))',head:'<th>#</th><th>工作簿（每项目一个）</th><th>工作表</th>',
        rows:pjs.map((k,i)=>`<tr><td class="fc">${i+1}</td><td>${esc(fnOf(k))}</td><td class="sm">辅材欠款 / 机械欠款 / 特殊费用月报表</td></tr>`)})}`;
   modal({title:'导出 · 逐月欠款台账（每项目一个工作簿）',body,
     footer:`<button class="btn" data-act="closeModal">关闭</button><button class="btn pri" data-act="ledExpSave">保存到本地</button>`}); },
 /* ⭐ 接线（`TAIL-04` 路径① · **片 2＋3**）：成品由**后端模板填充**生成 —— 每个项目**一本工作簿**
   （3 个 sheet：`辅材` / `机械` / `特殊费用月报表`），选 **≥2 个项目** ⇒ 打成一个 zip。
   ⚠️ 失败时后端回 **JSON 200 ＋ `ok:false` ＋ 中文原因**（**一个项目都没选** · 项目**不在档案里** ·
      模板缺失/损坏 · **显示区对账不过**）⇒ 据 `content-type` 分流：JSON ⇒ 弹原因；否则当文件下载。
   ⛔ 前端不自己拼文件名（命名规则的主人在后端，经 `X-Export-Filename` 带出）；
   ⚠️ 报告月**原样带给后端**（`ym` = 上月，§9.2）—— ⛔ 不在前端另算一份期间。 */
 ledExpSave:async ()=>{
   const pjs=ledExpPjs.slice();
   if(!pjs.length) return toast('请先选择要导出的项目');
   const url='/api/m05/ledger/export?projects='+encodeURIComponent(pjs.join(','))
     +'&ym='+encodeURIComponent(bjMonth(-1));
   const fn=await dlExport(url,{name:'欠款台账.xlsx',close:true});
   if(!fn) return;
   toast(pjs.length===1
     ? `已导出 <b>${esc(fn)}</b>：一本工作簿 / <b>3 个工作表</b>（辅材 / 机械 / 特殊费用月报表）`
     : `已导出 <b>${esc(fn)}</b>：<b>${pjs.length}</b> 个项目 ⇒ 一个 zip（每项目一本工作簿 · 每本 3 个工作表）`,8600); },
 /* ⭐ 已接后端：`POST /m05/ledger/remark`（键 = 口径 + 项目 + 月；**空串 = 清除该格**）。
    ⚠️ 备注输入框是 `change` 事件 ⇒ 失焦才落库（与原型一致），用完以后端为准重拉。 */
 ledNote:t=>{ const sc=t.dataset.sc, pjKey=t.dataset.proj, m=t.dataset.m;
    const v=String(t.value==null?'':t.value).trim();
    const row=pjRowOf(pjKey);
    if(!row||!row.id){ toast('<b>项目没对上档案</b> —— 备注未写入'); return; }
    m05Act(()=>API.postForm('/m05/ledger/remark', {
        category: CAT_API[sc] || sc, project_id: row.id, ym: m, remark: v, end_ym: '',
      }), v ? `台账备注已记录（${esc(m)}）` : '台账备注已清空'); },
 /* `expLed`（左右两栏各自的「导出 Excel」）已按 2026-09-13 用户口径**删除** ——
    改为卡头**一个**导出入口（`ledExpToggle` → 展开区多选项目 → `ledExpOk`）：
    导出形态 = **每个项目一个工作簿**（3 个工作表：辅材欠款 / 机械欠款 / 特殊费用月报表）；≥2 个项目打 zip。 */

 /* ⭐ 接线（`TAIL-04` 路径① · 片 4b）：**月度会大表**成品由**后端模板填充**生成 ——
   **一份**（全项目在一张表里：⛔ 不是每项目一份、⛔ 无 zip）· `Sheet1` 20 列（三级表头 ＋ 合计行）。
   ⚠️ 失败时后端回 **JSON 200 ＋ `ok:false` ＋ 中文原因**（**一行都没有** · 模板缺失/损坏 ·
      **显示区对账不过**）⇒ 据 `content-type` 分流：JSON ⇒ 弹原因；否则当文件下载。
   ⚠️ 月份**原样带给后端**（`bjMonth(-1)` = 材料报表类默认 = 上月，§9.2）—— ⛔ 不在前端另算。
   ⛔ 前端不自己拼文件名（命名规则的主人在后端，经 `X-Export-Filename` 带出）。 */
 bigExport:async ()=>{
   const url='/api/m07/big/export?period='+encodeURIComponent(bjMonth(-1));
   const fn=await dlExport(url,{name:'经济活动分析大表.xlsx'});
   if(!fn) return;
   toast(`已导出 <b>${esc(fn)}</b>：一份（全项目一张表）· <b>20 列</b>（三级表头 ＋ 合计行）；`
     + `派生列与合计**已算成数值**（⛔ 不留公式）`,8600); },

 /* —— MOD-12 —— */
 /* ⭐ 2026-09-20（`M6` 第一片）**本段三个写动作全部接后端**。
    ⚠️⚠️ **上面那行段标记注释一个字都没改** —— 它是**锚点**：`tests/test_wired_m07_big.py` 拿
       「换行 ＋ 空格 ＋ 那个 MOD-12 段标记」（**纯 ASCII**）当**上一段（`bigExport`）的终点**。
       ⇒ 谁改它，就会把**别的模块**的断言切歪（本次实测踩到：`ValueError: substring not found`）。
       ⛔ 要写说明就写在标记**下面**（像这几行），别动标记本身。
       ⚠️ 另注：本块注释里**不能出现注释结束符本身**（本次还顺带踩了一次：写了它会把注释提前闭合，
          后半句直接变成代码 ⇒ `node --check` 报 SyntaxError；`syntax_audit` 当场抓住）。
    ⚠️ 三个写动作**一律**：发请求 → **先判 `ok`**（`API.post` 恒 HTTP 200）→ 再刷本页。
    ⛔ 不再本地 `push` / `splice` 冒充落库（那是"刷新就没了"的假成功 —— 用户 2026-09-20 刚教过这条）。
    ⚠️ 定位一律用行的 **`_dbId`**（后端主键）：§9.8.2-5「写操作按 id 定位」——
       显示用的 `id` 是**业务编号**，它可读、但**不该当定位键**（拿它去写会把动作打到别的行上）。 */
 /* ⛔ 本页**已撤**（2026-09-20 用户裁定）—— 下面三个写动作**已停用**，只如实说明、不发请求。
    ⭐ 为什么留着函数：`V.m12` 是**原型切片**（`ui_parity` 按它逐行对位）⇒ 切片里的按钮还在，
       `ACT` 里没有同名动作会**报错**（点一下 `ACT.dfSave` 是 undefined）。⇒ 留**只会说一句话**的版本。
    ⭐ 差异现在怎么记：**去库存单据打调整单**（`adjDlg` / `adjOk` 那条路）——
        登记在那里，差异表由过程资料自动产出（点了差异行还能跳回来）。
    ⭐⭐ 2026-09-27（`TAIL-117` 批次 7 逐件核过 —— ⛔ **别来"顺手清干净"**）：
       本页这一组（`dfOk` / `dfAdd` / `dfSet` / `dfCancel` / `dfSave` / `dfDel` / `dfFilter` / `dfReset`
       ＋ `index.html` 里 `V.m12` 那片与 `dfDraftRow` / `dfD` / `dfNewOn` / `dfClear` / `dfMonthOpts` / `dfPjOpts`）
       **是有意保留的留痕**，依据 = 用户 2026-09-20 的裁定（`tools/audit/audit_common.py` 的
       `CANCELLED_KEEP_IN_PROTO_AND_DOCS` 那段注释记着全案）：原型 / 壳两边的 `V.m12` 残片**同进同退**
       （`ui_parity` 按它逐行对位，单边删立刻报红，还要连原型导读行号表 / 四检断言 / 验收基线一起重算）。
       ⇒ ⛔ 别只删这一半；要清就整体清（那是另一件大事，先问用户）。
       ⭐ 区别在于：**这是"完整的、仍能渲染的旧规格"**（读状态 / 本地草稿仍可用；真写库那三个已停用，
          因为 `diff_record` 表已 drop、接口已删）—— 而 `TASK` 那种**零引用死码**（本批已删）才是残骸。 */
 dfOk:()=>toast('<b>本页已停用</b>（2026-09-20 裁定）：差异登记**不独立成页** —— '
   + '差异登记在<b>库存单据的调整单</b>里；去「过程资料 → 差异表」可看差异并<b>跳回</b>被调整的行',7200),
 /* —— MOD-12 手工登记（2026-09-13 用户拍板「都改」）：新增 / 录入 / 保存 / 取消 / 删除 / 筛选 / 重置 ——
    范式与 `MOD-03` 手动行、集采子表**同款**：草稿层（`dfD`，键=字段名）+ 表内增行 + 保存才落库。 */
 dfAdd:()=>{ dfNewOn=true; dfClear(); render();
   toast('已在表尾生成<b>一行草稿</b>（尚未保存）—— 填完点该行「保存」落库、点「取消」丢弃<br>「归属」恒为<b>库存单据</b>（§5.8.3）；金额<b>可正可负</b>（+ 上调 / − 下调）',6000); },
 dfSet:t=>{ dfD[t.dataset.k]=t.value; },   /* 草稿层写入口（表单元素走 change ⇒ 委托层直呼；⛔ 无名单）；不重绘，免得每改一格丢焦点 */
 dfCancel:()=>{ dfNewOn=false; dfClear(); render(); toast('已取消登记 —— 草稿行丢弃，<b>未写入任何数据</b>'); },
 dfSave:()=>toast('<b>本页已停用</b>（2026-09-20 裁定）：差异登记**不独立成页** —— '
   + '差异登记在<b>库存单据的调整单</b>里；去「过程资料 → 差异表」可看差异并<b>跳回</b>被调整的行',7200),
 dfDel:()=>toast('<b>本页已停用</b>（2026-09-20 裁定）：差异登记**不独立成页** —— '
   + '差异登记在<b>库存单据的调整单</b>里；去「过程资料 → 差异表」可看差异并<b>跳回</b>被调整的行',7200),
 dfFilter:t=>{ fDf.stat=t.value; render(); },
 dfReset:()=>{ fDf.ym='全部'; fDf.stat='全部'; mp.open=null; render();
   toast('差异登记筛选已重置 —— 核算月与状态都回到<b>全部</b>'); },

 /* —— MOD-11 集采 —— */
/* ⛔ `M5-8` 集采台账**页内导入向导**（`jcImportOpen/Pick/Run/PickSheet/Pj/Map/Ok` ＋ `jcImpResult`）
   已**连件删除**（`TAIL-75` 余项 · 2026-09-23 **用户裁定**：「导入基本上只在刚开始用系统时导一次，
   之后就实时更新了」⇒ **只留通用面**）。
   ⭐ 现在集采台账的导入 = 壳「**数据导入**」页选 `集采台账`（`m11_jc` 域 · `/api/imp/m11_jc/*`）；
   ⛔ 后端 `/api/m11/import/parse|commit` 同批**连件删除**；⛔ 别再往壳里加回
   `jcImp*` / `jcImport*` 这一套（**已删**，见 `tools/audit_common.py::CANCELLED`）。 */

/* ⭐ `M5-9` 导出：**行** = 屏幕上看到的（复用 `jcVisible()` ⇒ ⛔ 不另写一套筛选 —— 两套必打架）；
   **列** = 全列（后端给，含贸易公司 3 列 —— 用户选的口径 (B)）。
   ⚠️ 空行集 ⇒ **明确拦**：⛔ 不导一本空表让人以为坏了，也⛔ 不悄悄改成"导全量"。 */
jcExport:async()=>{ const rows=jcVisible();
  if(!rows.length) return toast('当前筛选下**一行都没有** —— 没什么可导的（先点「重置」看全部）');
  let d=null;
  try{ d=await API.m11Export({ids:rows.map(j=>Number(j.id))}); }
  catch(e){ return toast(`<b>导出失败</b>：${esc(String((e&&e.message)||e))}`,7000); }
  if(!d||d.ok===false) return toast(`<b>导出失败</b>：${esc((d&&d.message)||'后端未返回原因')}`,7000);
  jcDownload(d.filename, d.content_b64);
  toast(`已导出 <b>${rows.length}</b> 行 ⇒ <b>${esc(d.filename)}</b>`
    + '<br><span class="mut sm">列是**全列**（含贸易公司 3 列）—— 屏幕上的隐藏只影响屏幕</span>'); },

/* ⭐ `M5-9` 隐藏 / 显示「贸易公司」三列（**纯屏幕**）。
   ⚠️⚠️ **切换时必须清该表的排序状态**：若用户先按「贸易公司合同金额」（第 9 列）排了序、再隐藏，
      `SORT.i` 仍是 9 ⇒ 界面还在对一列**看不见**的列排序 ⇒ 看着像"排序坏了"（静默错）。 */
jcToggleTrade:()=>{ jcHideTrade=!jcHideTrade;
  SORT['m11:jc']={i:-1,d:0};
  render();
  jcApplyHide();                       /* ⚠️ **必须**：`render()` 重建了整张表 ⇒ 偏好得重新落一次 */
  jcApplyPin();                        /* ⚠️ **同理**，而且这里更要紧：隐藏 / 显示那三列会**改剩下的列宽**
                                          ⇒ 上面量出来的行身份区偏移**当场就过期了**（不重量 = 露缝 / 叠字） */
  toast(jcHideTrade
    ? '已隐藏「贸易公司」三列（剩下的列会**自动变宽**）<br><span class="mut sm">只是屏幕上的事 —— 导出永远是全列</span>'
    : '已显示「贸易公司」三列'); },

/* ⭐ `M5-6b`：「合同金额」筛选（为空 = **待补供应商价**）。
   ⚠️ 这个筛选项是**必需的**，不是锦上添花：`applySorts` 里**空值恒排末尾且不随升降序翻转**
      ⇒ 待补的行**全部沉在表格底部**，"点一下排序"**够不着**它们（用户原以为排序就行）。 */
jcAmt:t=>{ fJc.amt=String(t.value||''); pruneJcPick(); render(); },
/* ⭐ `M5-6b` **甲方单位分类**弹窗 —— 它决定「i8 抓来的合同价是谁的价」：
   正常甲方 ⇒ i8 的价 = 供应商价（落 `contract_amt` · **锚点**）；
   贸易公司甲方 ⇒ i8 的价 = 贸易公司的价（落 `trade_contract_amt`），真供应商价 i8 里没有
     ⇒ 要人工从 Excel 供应商线补进 `contract_amt`。
   ⚠️ **没见过的甲方**抓取时会自动落成「未指定」⇒ 这个弹窗把它们**排在最前面**等人指定。 */
jcPartyDlg:async()=>{ let d=null;
  try{ d=await API.m11PartyKinds(); }
  catch(e){ return toast(`<b>没能取到甲方分类</b>：${esc(String((e&&e.message)||e))}`,7000); }
  if(!d||d.ok===false) return toast(`<b>没能取到甲方分类</b>：${esc((d&&d.message)||'后端未返回原因')}`,7000);
  const items=d.items||[], kn=d.kind_names||{};
  const opt=k=>d.kinds.map(x=>`<option value="${x}"${x===k?' selected':''}>${esc(kn[x]||x)}</option>`).join('');
  const body=`<div class="tip${d.unknown?' wn':' ok'}" style="margin-bottom:calc(10px * var(--fscale))">${
      d.unknown?`<b>⚠️ 有 ${d.unknown} 个甲方还没指定类型</b> —— 它们**排在最前面**。在指定之前，
        它们的金额按「<b>正常</b>」落进「合同金额」列（这个选择**可逆**：指定后会一眼看出对不对）。`
      :'全部甲方都已指定类型 ✅'}
    <br><span class="mut sm">规则：<b>正常甲方</b> ⇒ i8 合同价 = <b>供应商价</b>（落「合同金额」）；<b>贸易公司甲方</b> ⇒ i8 合同价 = <b>贸易公司的价</b>（落「贸易公司合同金额」），而<b>真供应商价 i8 里没有</b> ⇒ 要人工从 Excel 的供应商线补进「合同金额」。</span></div>
    <div class="tw" style="max-height:50vh">${TBL({cls:'cond',key:'modal:jcParty',
      head:'<th>甲方单位（i8 的「甲方单位」原样）</th><th style="width:150px">类型</th><th style="width:88px">合同数</th>',
    rows:items.map(it=>`<tr class="${it.kind==='unknown'?'hl':''}">
      <td>${esc(it.name)}</td>
      <td><select class="inp" data-act="jcPartySet" data-name="${esc(it.name)}"${it.kind==='unknown'?' style="border-color:var(--wn)"':''}>${opt(it.kind)}</select></td>
      <td class="num">${it.count||0}</td></tr>`),
    empty:EMPTYROW(3, '还没有甲方记录', '抓取一次后，i8 里的甲方单位会自动出现在这里')})}</div>
    <div class="tip" style="margin:calc(12px * var(--fscale)) 0 0"><b>⚠️ 改类型**不会**回头重算已有合同的金额</b> —— 与「改规则不重算历史」同款口径。
      已经落错列的行，改完分类后请<b>重抓一次</b>（贸易公司的价会被重新落位）或<b>手工改</b>。</div>`;
  modal({title:'甲方单位分类（决定合同价是谁的价）', wide:true, body,
    footer:`<button class="btn pri" data-act="closeModal">关闭</button>`}); },
jcPartySet:async t=>{ const nm=String(t.dataset.name||''), k=String(t.value||'');
  if(!nm||!k) return;
  let d=null;
  try{ d=await API.m11SetPartyKind({name:nm, kind:k}); }
  catch(e){ return toast(`<b>没能保存</b>：${esc(String((e&&e.message)||e))}`,7000); }
  if(!d||d.ok===false) return toast(`<b>没能保存</b>：${esc((d&&d.message)||'后端未返回原因')}`,7000);
  toast(esc(d.message||'已保存')+`<br><span class="mut sm">⚠️ 已有的合同**不会**重算金额落位 ⇒ 需要时请重抓一次或手改</span>`);
  /* ⚠️ 重开弹窗（刷新那行）—— `jcPartyDlg` 是 async ⇒ 不复用 `modal.reopen`（那只接同步表达式）。 */
  await ACT.jcPartyDlg(); },
/* ⭐ `M5-7`：抓取接通（`POST /api/m11/fetch`）。⚠️ 抓取**会顶号**（`D9`）⇒ **先二次确认**、说清后果。
   ⭐ `M5-6`：加「开始日期」（**增量**）—— 实测全量 40 秒、增量 1~5 秒（差 40~80 倍）。 */
jcFetch:()=>{ const def = jcFetchSinceOn || jcFetchSinceDefault(); modal({title:'抓取采购合同信息· 二次确认',
  body:`<div class="tip wn" style="margin-bottom:calc(10px * var(--fscale))"><b>⚠️ 这一步会登录 i8，可能顶掉该账号其它在线会话</b>（决策 D9）。若同事正在用 i8，请先择时。</div>
    <div class="fld"><label>开始日期 —— 只抓<b>这之后</b>的单据（<b>增量</b>）</label>
      <input class="inp" id="jcFetchSince" type="date" value="${esc(def)}">
      <div class="sm mut" style="margin-top:calc(6px * var(--fscale))">默认 = 台账里<b>最新合同日期 − 3 天</b>（多留几天：i8 的<b>增补合同会沿用原单据日期</b>，卡太紧会漏；重复的会被幂等挡掉）。<br><b>清空</b> = 全量（<b>约 40 秒</b>，首次建档才需要）；带日期 = 增量（<b>1~5 秒</b>）。</div></div>
    <div class="sm" style="line-height:1.9">流程：<b>抓合同</b> → <b>补材料名</b>（只补<b>库里还没有的</b>，逐条问 i8 详情）→ <b>同步「常用项目列表」</b> → <b>按项目匹配</b> → 落库（新抓的默认<b>「纳入台账」</b>）。<br>⚠️ 匹配不上的按口径 = <b>不纳入</b>（i8 的常用列表里也没有 ⇒ 不需要），但**落库前会给你一眼看见**。<br>⚠️ <b>未审批</b>的合同<b>不抓</b>。</div>`,
  footer:`<button class="btn" data-act="closeModal">取消</button><button class="btn pri" data-act="jcFetchOk">确认抓取（会顶号）</button>`}); },
jcFetchOk:async()=>{ const el=$('#jcFetchSince');
  /* ⚠️ 读不到 / 格式不对 ⇒ 传**空串**（= 交给后端按默认增量走），⛔ 不传一个"看着像日期"的脏值：
     后端收到脏值会当成过滤条件发给 i8 ⇒ **静默全量**（最坏的那种）。 */
  const raw = el ? String(el.value || '').trim() : '';
  const since = /^\d{4}-\d{2}-\d{2}$/.test(raw) ? raw : '';
  jcFetchSinceOn = since;                          /* ⭐ 记住用户这次填的 */
  closeModal();
  const r=await jcAct(()=>API.m11Fetch(since),
    d=>`已抓取：匹配上 ${d.matched} 条（新增 ${(d.stats||{}).inserted||0}）· 匹配不上 ${d.unmatched} 条`
      + `<br><span class="mut sm">范围：${d.since ? `起点 <b>${esc(d.since)}</b>（增量）` : '<b>全量</b>（未设起点）'}`
      + ` · 材料名补 <b>${d.material_filled || 0}</b> 条`
      + `${d.material_blank ? `（<b style="color:var(--wn)">${d.material_blank}</b> 条 i8 也没给材料名）` : ''}</span>`);
  /* ⭐ 落库**之后**照样给一眼匹配预览（`unmatched` 是终态、不会被后续抓取覆盖 ⇒ 人得当场看见）。 */
  if(r) modal({title:'抓取结果 · 匹配预览（§6.5.3）',body:jcFetchPreview(r),
    footer:`<button class="btn pri" data-act="closeModal">知道了</button>`}); },
 /* 批量标记的前置：勾选（范围 = 当前筛选结果）；筛选变化 → 裁剪不可见的勾选（R10/R14） */
 jcPick:t=>{ const id=t.dataset.id; if(!id) return; if(jcPick.has(id)) jcPick.delete(id); else jcPick.add(id); render(); },
 jcPickAll:()=>{ const cur=jcVisible(); const hit=cur.filter(j=>jcPick.has(j.id)).length;
   if(hit===0){ cur.forEach(j=>jcPick.add(j.id)); } else { cur.forEach(j=>jcPick.delete(j.id)); } render(); },
 /* 批量标记三态（§6.5.3）：勾选后**一次动作**；人工标记优先，后续全量抓取**不被覆盖**。
    ⭐ `M5-7`：接 `POST /api/m11/tag`（`{ids, tag}`）。后端回 `affected_ids` ⇒ 只清空**刚标过的**那些勾选
    （判据 `001-05`「动作后清空勾选」＋「不改行数」；`jcPick` 里其余项保持不动）。 */
 jcBatchTag:async t=>{ const v=t.dataset.v; if(!jcPick.size){ toast('请先勾选要标记的行'); return; }
   const ids=[...jcPick];
   const r=await jcAct(()=>API.m11Tag({ids, tag:v}),
     x=>`已把 <b>${x.count}</b> 条合同批量标记为 <b>${esc(v)}</b> —— 人工标记优先，后续全量抓取<b>不被覆盖</b>（§6.5.3）`);
   if(r){ (r.affected_ids||[]).map(String).forEach(id=>jcPick.delete(id)); pruneJcPick(); render(); } },
 jcTag:async t=>{ const j=JCs.find(x=>x.id===t.dataset.id); if(!j) return;
   await jcAct(()=>API.m11Tag({id:j.id, tag:t.dataset.v}),
     `合同 <b>${j.id}</b> 已标记为「<b>${esc(t.dataset.v)}</b>」`); },
 /* 存档推进（未存档 → 资产处 → 已存档，§6.7.2）—— ⚠️ 下一态在**前端算**（后端只收目标值）；
    ⛔ **不自动生成存档号**（那会臆造数据）⇒ 存档号请在格子里手填。 */
 jcArch:async t=>{ const j=JCs.find(x=>x.id===t.dataset.id); if(!j) return;
   const next=j.arch==='未存档'?'资产处':j.arch==='资产处'?'已存档':'未存档';
   await jcAct(()=>API.m11Fields({id:j.id, fields:{arch:next}}),
     `合同存档情况推进为「<b>${esc(next)}</b>」（未存档 → 资产处 → 已存档，§6.7.2）<br><span class="mut sm">存档号请在该列手填</span>`); },
 /* 主表「发票金额 / 贸易公司发票金额 / 付款金额」已改为**只读汇总**（= 各自子表合计）——
    录入一律走「子表」，因此不再有主表直改动作（口径 2026-09-12 定案，取代原 jcPay） */
 jcMethod:async t=>{ const j=JCs.find(x=>x.id===t.dataset.id); if(!j) return;
  await jcAct(()=>API.m11Fields({id:j.id, fields:{method:t.value}}),
    '付款方式为<b>自由文本、不限值</b>，不做枚举约束（DEV-J-03）'); },
 /* 合同收发登记（§6.7）**改为可手改**（2026-09-13 用户口径）：存档号 / 寄回日期 / 备注三列。
    ⚠️ 按 §9.3 的留痕清单（只给 统计两金额 / 调整单 / 项目全名与状态）⇒ 这三列**不留痕**（照既有口径、不新增）。
    ⚠️ 寄回日期用 `type="date"`（要的是**完整日期**；R6 只管"选年月"那种滚轮控件）。 */
 jcArchNo:async t=>{ const j=JCs.find(x=>x.id===t.dataset.id); if(!j) return;
   const v=String(t.value==null?'':t.value).trim();
   await jcAct(()=>API.m11Fields({id:j.id, fields:{arch_no:v}}),
     `合同 <b>${j.id}</b> 存档号已保存${v?`：<b>${esc(v)}</b>`:'（已清空）'}`); },
 jcRetDate:async t=>{ const j=JCs.find(x=>x.id===t.dataset.id); if(!j) return;
   const v=String(t.value==null?'':t.value).trim();
   await jcAct(()=>API.m11Fields({id:j.id, fields:{ret_date:v}}),
     `合同 <b>${j.id}</b> 寄回日期已保存${v?`：<b>${esc(v)}</b>`:'（已清空）'}`); },
 jcRemark:async t=>{ const j=JCs.find(x=>x.id===t.dataset.id); if(!j) return;
   const v=String(t.value==null?'':t.value).trim();
   await jcAct(()=>API.m11Fields({id:j.id, fields:{remark:v}}),
     `合同 <b>${j.id}</b> 备注已保存`); },
 /* 子表弹窗**拆开**（2026-09-13 用户口径）：三个弹窗各装**一张**子表，
    入口就近放在「**发票金额 / 贸易公司发票金额 / 付款金额**」三列右侧的「子表」按钮上。
    ⇒ 原「一个按钮装三张子表」的 `jcDetail` 已删除。 */
 jcInvDlg:async t=>{ const j=JCs.find(x=>x.id===t.dataset.id); if(!j) return;
  await jcLoadSub(j);                       /* ⭐ 子表明细**不在列表接口里** ⇒ 开弹窗前拉一次 */
   modal({title:`供应商发票子表 · ${j.id} ${esc(j.material)}`,reopen:()=>ACT.jcInvDlg({dataset:{id:j.id}}),body:
     `${TBL({cls:'cond',key:'modal:jcInv',head:JCINV_THEAD,
      rows:j.invoices.map((v,i)=>`<tr><td class="fc">${i+1}</td><td style="white-space:nowrap">${esc(v[0]||'')}</td><td class="num">${M(v[1])}</td><td class="ctr"><button class="btn sm dg" data-act="jcInvDel" data-id="${j.id}" data-i="${i}">删</button></td></tr>`),
      empty:EMPTYROW(thCount(JCINV_THEAD), '暂无发票', '点本卡右上角「＋ 加一行」录入'),
      sum:(jcSubOn('inv',j.id)?jcSubRow():'')+sumRowOf(JCINV_THEAD, [], {2:[()=>jcInvSum(j),v=>'<b>'+M(v)+'</b>']}, {style:'background:var(--sf2)'})})}
      <div style="margin-top:calc(8px * var(--fscale))"><button class="btn sm" data-act="jcSubAdd" data-id="${j.id}" data-kind="inv">＋ 增加一张发票</button></div>
      <div class="tip" style="margin:calc(12px * var(--fscale)) 0 0"><b>发票子表（ENT-07）</b>：一合同 <b>1..N</b> 张、<b>「发票日期 ＋ 金额」两列</b>（<b>录入必填日期</b>）；<b>金额不设上限</b>（§6.4.1）。<br>${j.tradeCo?'本合同<b>有贸易公司</b> ⇒ <b>结算取「贸易公司发票」子表合计</b>，本子表<b>只作供应商侧台账</b>（§6.4.1）。':'本合同<b>无贸易公司</b> ⇒ <b>结算取本子表合计</b>（§6.4.1）。'}</div>`}); },
 jcTInvDlg:async t=>{ const j=JCs.find(x=>x.id===t.dataset.id); if(!j) return;
  await jcLoadSub(j);
   modal({title:`贸易公司发票子表 · ${j.id} ${esc(j.material)}`,reopen:()=>ACT.jcTInvDlg({dataset:{id:j.id}}),body:
     (j.tradeCo?`${TBL({cls:'cond',key:'modal:jcTInv',head:JCINV_THEAD,
      rows:(j.tradeInvoices||[]).map((v,i)=>`<tr><td class="fc">${i+1}</td><td style="white-space:nowrap">${esc(v[0]||'')}</td><td class="num">${M(v[1])}</td><td class="ctr"><button class="btn sm dg" data-act="jcTInvDel" data-id="${j.id}" data-i="${i}">删</button></td></tr>`),
      empty:EMPTYROW(thCount(JCINV_THEAD), '暂无发票', '点本卡右上角「＋ 加一行」录入'),
      sum:(jcSubOn('tinv',j.id)?jcSubRow():'')+sumRowOf(JCINV_THEAD, [], {2:[()=>jcTradeInvSum(j),v=>'<b>'+M(v)+'</b>']}, {style:'background:var(--sf2)'})})}
      <div style="margin-top:calc(8px * var(--fscale))"><button class="btn sm" data-act="jcSubAdd" data-id="${j.id}" data-kind="tinv">＋ 增加一张发票</button></div>
      <div class="tip" style="margin:calc(12px * var(--fscale)) 0 0"><b>贸易公司发票子表（ENT-07 同款）</b>：<b>「发票日期 ＋ 金额」两列</b>（<b>录入必填日期</b>）；<b>金额不设上限</b>。<br>有贸易公司 ⇒ <b>结算取本子表合计</b>（与供应商侧<b>同一套逻辑</b>，§6.4.1）。</div>`
      :`<div class="tip" style="margin:0">本合同<b>无贸易公司</b> ⇒ <b>不启用该子表</b>（结算取供应商发票合计，§6.4.1）。</div>`)}); },
 jcPayDlg:async t=>{ const j=JCs.find(x=>x.id===t.dataset.id); if(!j) return;
  await jcLoadSub(j);                       /* ⭐ 付款子表同理：列表不给明细 */
   modal({title:`付款子表 · ${j.id} ${esc(j.material)}`,reopen:()=>ACT.jcPayDlg({dataset:{id:j.id}}),body:
     `${TBL({cls:'cond',key:'modal:jcPay',head:JCPAY_THEAD,
      rows:j.payments.map((p,i)=>`<tr><td class="fc" style="white-space:nowrap">${esc(p[0]||'')}</td><td class="num">${M(p[1])}</td><td>${p[2]==='付款域引用'?tag('付款域引用','pri'):tag('手工','in')}</td><td class="ctr"><button class="btn sm dg" data-act="jcPayDel" data-id="${j.id}" data-i="${i}">删</button></td></tr>`),
      empty:EMPTYROW(thCount(JCPAY_THEAD), '暂无付款', '点本卡右上角「＋ 加一行」录入'),
      sum:(jcSubOn('pay',j.id)?jcSubRow():'')+sumRowOf(JCPAY_THEAD, [], {1:[()=>jcPay(j),v=>'<b>'+M(v)+'</b>']}, {style:'background:var(--sf2)'})})}
      <div style="margin-top:calc(8px * var(--fscale));display:flex;gap:calc(6px * var(--fscale))"><button class="btn sm" data-act="jcSubAdd" data-id="${j.id}" data-kind="pay">＋ 手工录入</button>
        <button class="btn sm pri" data-act="jcPayRef" data-id="${j.id}">从付款域引用（R8）</button></div>
      <div class="sm mut" style="margin-top:calc(7px * var(--fscale))">集采付款通知书的收款方都是「资产处集中采购」，真实供应商靠<b>人工录入的「集采实际供应商」</b>做关联锚点；<b>同一笔通知书不可重复引用</b>。</div>
      <div class="tip" style="margin:calc(12px * var(--fscale)) 0 0"><b>付款子表（ENT-08）</b>：一合同 <b>0 / 1 / 多</b> 次，手工录入 + 可从付款域引用。<br><b>欠款口径（§6.4.4）：</b>${j.tradeCo?`有贸易公司 → 贸易公司发票合计 ${M(jcTradeInvSum(j))}`:`无贸易公司 → 供应商发票合计 ${M(jcInvSum(j))}`} − 付款合计 ${M(jcPay(j))} = <b style="color:var(--dg)">${M(jcDebt(j))}</b>（<b>合同级实时，不拆月度</b>）</div>`}); },
 /* —— 集采三张子表的录入 = **表内增行**（2026-09-13 用户口径：发票子表录入要填日期；**取代原先那种浏览器原生输入小窗**）——
    `jcSubAdd` 进增行态（草稿只存 `jcSubD`）· `jcSubSet` 写草稿层（走 `change` 委托）· `jcSubSave` 校验后落库 · `jcSubCancel` 丢弃。
    ⚠️ 旧动作 `jcInvAdd` / `jcTInvAdd` / `jcPayAdd`（`prompt` 单值录入）已删除。 */
 jcSubAdd:t=>{ const j=JCs.find(x=>x.id===t.dataset.id), kind=t.dataset.kind; if(!j||!JCSUB_KIND[kind]) return;
   jcSubKind=kind; jcSubId=j.id; jcSubD={date:(kind==='pay'?SYS_TODAY:''),amt:''};
   jcSubDlg(kind,j.id);
   toast(`已在子表末尾生成<b>一行草稿</b>（尚未保存）—— ${kind==='pay'?'付款日期默认取系统当日，可改':'<b>发票日期必填</b>'}；填完点「保存」落库、点「取消」丢弃`,5600); },
 jcSubSet:t=>{ if(!jcSubKind) return; jcSubD[t.dataset.k]=t.value; },   /* 写草稿层，**不重绘**（避免每改一格就把焦点丢掉） */
 jcSubCancel:()=>{ const k=jcSubKind, id=jcSubId; if(!k) return; jcSubReset(); jcSubDlg(k,id);
   toast('已取消 —— 草稿行丢弃，<b>未写入任何数据</b>'); },
 /* 子表增行 ⇒ `POST /api/m11/invoice/add` / `payment/add`。
    ⭐ `M5-7`：⛔ 原先这里是**本地 push 进数组**冒充落库（刷新就没了）⇒ 改为走后端 + 重拉明细。
    ⚠️⚠️ `jcAct` 内部会 `reloadM11()` ⇒ **行对象被重建**（`JCs` 是原地换内容）⇒ 之后必须**重取**那一行，
    否则 `jcLoadSub` 会写到一个已经不在表里的旧对象上 —— **静默失效**（弹窗看着"没变化"）。 */
 jcSubSave:async()=>{ const j=JCs.find(x=>x.id===jcSubId), kind=jcSubKind; if(!j||!kind) return jcSubReset();
   const dt=String(jcSubD.date||'').trim(), nm=(kind==='pay'?'付款金额':'发票金额'), dn=(kind==='pay'?'付款日期':'发票日期');
   if(!/^\d{4}-\d{2}-\d{2}$/.test(dt)) return toast(`<b>请先填「${dn}」</b>：本子表录入<b>必须填日期</b>（草稿行第一个框）`);
   const v=numOf(jcSubD.amt); if(badMoney(v,{positive:1})) return toast(badMoneyMsg(nm,{positive:1}));
   /* 金额**不设上限**（2026-09-13 用户口径）—— 这里**刻意不接** `overCap`（与「统计两金额 ≤ 审批金额」那条无关）。 */
   const r=await jcAct(
     () => (kind==='pay' ? API.m11PayAdd({id:j.id, date:dt, amount:String(v)})
           : API.m11InvAdd({id:j.id, kind:(kind==='tinv'?'trade':'supplier'), date:dt, amount:String(v)})),
     () => (kind==='pay' ? `已录入付款 <b>${M(v)}</b>（${dt}）`
           : (kind==='tinv' ? `已增加贸易公司发票 <b>${M(v)}</b>（${dt}）` : `已增加发票 <b>${M(v)}</b>（${dt}）`)));
   if(!r) return;
   const j2=JCs.find(x=>x.id===j.id); if(!j2) return;      /* ⚠️ 见上方：`jcAct` 重建了行 ⇒ 重取 */
   jcSubReset();
   await jcLoadSub(j2);                                     /* ⭐ 派生金额一律回后端算（⛔ 不前端现算） */
   render();
   if(JCSUB_KIND[kind]) jcSubDlg(kind,j2.id);               /* 重开弹窗，让新行露面 */
   if(kind==='pay') toast(`已录入付款 <b>${M(v)}</b>（${dt}）→ 欠款 ${M(jcDebt(j2))}`);
   else if(kind==='tinv') toast(`已增加贸易公司发票 <b>${M(v)}</b>（${dt}）→ 结算金额 ${M(jcSettle(j2))}`);
   else toast(`已增加发票 <b>${M(v)}</b>（${dt}）→ 发票合计 ${M(jcInvSum(j2))}`); },
 /* 子表删行 ⇒ `POST /api/m11/invoice/del` / `payment/del`（按**下标**取 id —— 见 `jcLoadSub` 里的 `j._ids`）。 */
 jcInvDel:async t=>{ const j=JCs.find(x=>x.id===t.dataset.id); if(!j) return;
   const rid=((j._ids||{}).inv||[])[+t.dataset.i]; if(!rid) return toast('这行还没从后端载入，请关掉弹窗重开');
   if(!await jcAct(()=>API.m11InvDel({row_id:Number(rid)}), '已删除该发票行')) return;
   const j2=JCs.find(x=>x.id===j.id); if(!j2) return;
   await jcLoadSub(j2); ACT.jcInvDlg({dataset:{id:j2.id}}); render(); },
 jcTInvDel:async t=>{ const j=JCs.find(x=>x.id===t.dataset.id); if(!j) return;
   const rid=((j._ids||{}).tinv||[])[+t.dataset.i]; if(!rid) return toast('这行还没从后端载入，请关掉弹窗重开');
   if(!await jcAct(()=>API.m11InvDel({row_id:Number(rid)}), '已删除该发票行')) return;
   const j2=JCs.find(x=>x.id===j.id); if(!j2) return;
   await jcLoadSub(j2); ACT.jcTInvDlg({dataset:{id:j2.id}}); render(); },
 jcPayDel:async t=>{ const j=JCs.find(x=>x.id===t.dataset.id); if(!j) return;
   const rid=((j._ids||{}).pay||[])[+t.dataset.i]; if(!rid) return toast('这行还没从后端载入，请关掉弹窗重开');
   if(!await jcAct(()=>API.m11PayDel({row_id:Number(rid)}), '已删除该付款行')) return;
   const j2=JCs.find(x=>x.id===j.id); if(!j2) return;
   await jcLoadSub(j2); ACT.jcPayDlg({dataset:{id:j2.id}}); render(); },
 /* 从付款域引用（R8）：**不做任何自动匹配**（DEV-J-01 已否掉标题 / 名字匹配）→ 纯人工选择；
    且**同一笔通知书只能引用一次**（去重，防付款重复计入） */
 jcPayRef:t=>{ const j=JCs.find(x=>x.id===t.dataset.id);
   /* ⚠️ 去重范围 = **全库**（§6.6.2「同一笔付款通知书只能被引用一次」）—— 原实现只按**单个合同**去重，
      会让同一笔被两个合同各引一次、**付款重复计入** ⇒ 2026-09-13 收敛到全库。 */
   const used=jcUsedNids();
   const cam=NO.filter(n=>ntLive(n)&&n.cat==='集采'&&!used.has(n.id));
   modal({title:'从付款域引用付款记录（R8）',body:`<div class="tip" style="margin-bottom:calc(10px * var(--fscale))">集采台账的付款信息可从付款域<b>一键关联引用</b>。因为供应商名不可靠，<b>不做自动匹配</b>（DEV-J-01），由你按「<b>集采实际供应商</b>」人工判断（§6.6.2）；<b>同一笔通知书只能引用一次</b>。</div>
     <div class="fld"><label>选择付款域中分类为「集采」的通知书</label><select class="inp" id="refId">${cam.length?cam.map(n=>`<option value="${n.id}">${esc(n.code)} · ${esc(n.sup||'未录入供应商')} · ${M(n.sp)}</option>`).join(''):'<option value="">（无可引用：已被引用过，或本月无集采单据）</option>'}</select></div>`,
     footer:`<button class="btn" data-act="closeModal">取消</button><button class="btn pri" data-act="jcPayRefOk" data-id="${j.id}">引用</button>`}); },
 /* ⭐ `M5-7`：⛔ 原先这里是**本地 push 进付款数组**冒充落库（刷新就没了）⇒ 改为如实说明。
    它归 `M5-5`（付款域双向引用）—— 那一片会接 `POST /api/m11/payment/add`（`source=notice` +
    **全库去重**由后端 `domain.dedup_blocked` ＋ 唯一键 `uq_jc_payment_notice` 双保险）。 */
 jcPayRefOk:async t=>{ const j=JCs.find(x=>x.id===t.dataset.id); if(!j) return;
   const sel=$('#refId'); const nid=sel&&sel.value; if(!nid) return toast('没有可引用的通知书');
   closeModal();
   /* ⭐ `M5-5`：与 m03 侧「关联集采合同」调**同一个端点** —— 方向不同、**落点相同**（同一份记录）。 */
   await jcLinkAct(()=>API.m11Link({notice_id:Number(nid), contract_id:Number(j.id)}),
     x=>`已把付款通知书引用到集采合同 <b>#${j.id}</b>${x.moved_from?`（原关联 #${x.moved_from} 已解除）`:''}<br><span class="mut sm">两侧同时可见（同一份记录）· 同一笔通知书全库只能引用一次</span>`); },
 /* —— 「关联集采合同」反向入口的动作（2026-09-13 用户裁定）——
    一对一 · 与 R8 共用同一份记录 · 去重按全库 · 金额不一致只提示不拦 · 关联 / 解绑**不留痕**。
    弹窗内所选合同走草稿 `jcLinkSel`：改选择要**重绘弹窗**（金额比对随之更新）。 */
 jcLink:t=>{ const n=NO.find(x=>x.id===t.dataset.id);
   if(!n) return;
   if(!ntLive(n)||n.cat!=='集采'){ toast('仅「集采」分类的记录可关联集采合同'); return; }
   const cur=jcRefOf(n.id), cands=jcLinkCands(n), pk=ntProjKey(n);
   if(!jcLinkSel||!cands.some(j=>j.id===jcLinkSel)) jcLinkSel=cur?cur.id:((cands[0]&&cands[0].id)||null);
   const sel=cands.find(j=>j.id===jcLinkSel)||null;
   const same=sel?N2(jcDebt(sel))===N2(n.sp):false;
   modal({title:`关联集采合同 · ${n.code}`,reopen:()=>ACT.jcLink({dataset:{id:n.id}}),body:
     `<div class="tip" style="margin-bottom:calc(10px * var(--fscale))">把这行<b>集采通知书</b>关联到一张<b>集采合同</b> —— 这是「从付款域引用（R8）」的<b>反向入口</b>，两者<b>写同一份记录</b>（集采合同的付款子表）⇒ <b>双向可见</b>。<br>⚠️ <b>一条通知书只能关联一张合同</b>；<b>同一笔在全库范围内不可重复引用</b>（防付款重复计入）。<br>⭐ <b>候选只列本项目（仓库）的合同</b> —— 本行项目 = <b>${esc(pjLabel(pk)||'（未指定归属）')}</b>${pk?`（仓库名 <span class="fc">${esc(pk)}</span>）`:''}。</div>
     ${cands.length?`<div class="fld"><label>选择集采合同（仅本项目）</label><select class="inp" id="jcLinkId" data-act="jcLinkPick" data-id="${n.id}">${cands.map(j=>`<option value="${j.id}" ${sel&&sel.id===j.id?'selected':''}>${j.id} · ${esc(j.material)} · 欠款 ${M(jcDebt(j))}${j.proj===pk?'':' · 他项目（当前已关联）'}</option>`).join('')}</select></div>`
       :`<div class="tip" style="margin:0"><b>本项目下暂无集采合同</b> —— 请先到「集采台账」页为 <b>${esc(pjLabel(pk)||'该项目')}</b> 建档（或抓到 i8 合同），再回来关联。<br><span class="mut sm">本行项目：${esc(pjLabel(pk)||'（未指定归属）')}${pk?`（仓库名 ${esc(pk)}）`:''}</span></div>`}
     ${sel?`<div class="fld"><label>金额比对（只提示，不拦截）</label><div class="sm" style="line-height:1.8">本行统计付款金额 <b>${M(n.sp)}</b> ｜ ${sel.id} 当前欠款 <b>${M(jcDebt(sel))}</b>${same?' '+tag('一致','ok'):' '+tag('不一致 · 仍可关联','wn')}</div></div>`:''}`,
     footer:`${cur?`<button class="btn dg" data-act="jcUnlink" data-id="${n.id}">取消关联（${cur.id}）</button>`:''}<button class="btn" data-act="closeModal">取消</button><button class="btn pri" data-act="jcLinkOk" data-id="${n.id}" ${cands.length?'':'disabled'} title="${cands.length?'':'本项目下没有可选合同 —— 先到「集采台账」建档'}">${cur?'改关联到所选合同':'关联'}</button>`}); },
 jcLinkPick:t=>{ jcLinkSel=t.value; render(); if(lastModal&&lastModal.reopen) lastModal.reopen(); },
 jcLinkOk:async t=>{ const n=NO.find(x=>x.id===t.dataset.id); if(!n) return;
   const j=JCs.find(x=>x.id===jcLinkSel); if(!j) return toast('没有可关联的集采合同');
   /* ⚠️ 2026-09-13 口径「只能关联本项目的合同」**不需要在这里再拦一道** —— 它由两件事闭合：
      ① 候选只从 `jcLinkCands(n)`（= 本项目合同 ∪ 当前已关联那张）来；
      ② `jcLinkPick` 记录选择后**立即重开弹窗**，`jcLink` 会拿候选集再校验一次 `jcLinkSel`
         ⇒ 任何"他项目"的 id 都会被**回落**成合法候选，走不到这里。
      （曾经在这里写过一道 `j.proj!==pk` 兜底，实测**不可达** ⇒ 按"不留死代码"删掉，
         改由 `_smoke` 的 `T5` 直接断言 ② 那个"回落"行为。） */
   closeModal();
   /* ⭐ `M5-5`：后端保证「一对一」（换合同 = **先解绑再写新**）＋ 全库去重；⛔ 壳里不碰任何数组。 */
   await jcLinkAct(()=>API.m11Link({notice_id:Number(n.id), contract_id:Number(j.id)}),
     x=>`已关联到集采合同 <b>#${j.id}</b>${x.moved_from?`（原关联 #${x.moved_from} 已解除）`:''}<br><span class="mut sm">两侧同时可见（同一份记录）· 金额不一致只提示不拦</span>`); },
 /* 取消关联（`m03` 侧）。⭐ `M5-5`：解绑 = 摘掉那条关联记录 ⇒ **两侧同时**变回"未关联"（只有一份记录）。 */
 jcUnlink:async t=>{ const n=NO.find(x=>x.id===t.dataset.id); if(!n) return;
   closeModal();
   await jcLinkAct(()=>API.m11Unlink({notice_id:Number(n.id)}),
     x=>`已取消与集采合同 <b>#${x.contract_id}</b> 的关联（两侧同时解除）`); },
 /* —— MOD-11 · 手工新增集采合同 = **表内增行（展开区）**（2026-09-13 用户口径）——
    ⚠️ 原来这个动作只开弹窗，而弹窗的「保存」挂的是 `data-act="silent"`（**根本没有落库动作**）
       ⇒ 本次改制时**补上真正的建档动作 `jcRowSave`**（草稿层 `jcND`，与既有 `naD` / `lgD` 同源）。 */
 jcAdd:()=>{ const cands=pjKeysOfRows(ntPjList());
   jcND={date:SYS_TODAY,material:'',supplier:'',contractAmt:'0.00',tradeCo:'',tradeContractAmt:'',method:'',remark:'',
     pj:(fJc.projs.length===1?fJc.projs[0]:(cands[0]||''))};   /* 项目默认 = 当前筛选唯一项，否则候选第一个 */
   jcNewOn=true; pjClose('jcNPj'); render();
   toast('已在表格上方展开「手工新增合同」录入区 —— 填完点「保存」建档、点「取消」丢弃（<b>草稿不入库</b>）<br><span class="mut sm">发票金额 / 贸易公司发票金额 / 付款金额 = 各自子表合计（建档后在各列右侧「子表」里录）</span>',6000); },
 jcRowCancel:()=>{ jcNewOn=false; pjClose('jcNPj'); render(); toast('已取消手工新增合同 —— <b>未写入任何数据</b>'); },
 /* 草稿写入口（不重绘 —— 免得每改一格就丢焦点；本展开区没有"改一格要连带重绘"的字段） */
 jcNSet:t=>{ const k=t.dataset.k; if(k) jcND[k]=t.value; },
 /* 「项目」共用面板（**单选**）—— 第 10 个 `projPanel` 调用点 */
 jcNPjToggle:()=>{ pjToggle('jcNPj'); render(); },
 jcNPjPick:t=>{ const v=(t&&t.dataset&&t.dataset.pj)||''; if(!v) return; jcND.pj=v; pjClose('jcNPj'); render();
   toast(`新增合同的项目已定为 <b>${esc(pjLabel(v))}</b>`); },
 /* 建档（替代原弹窗那句挂 `silent` 的空"保存"） */
 /* 建档 ⇒ `POST /api/m11/add`。⭐ 三态**不由这里给** —— 后端按「手工新增 = 纳入台账」填
    （判据 `001-07` 原文；⛔ 前端不许自己写死一个默认值，那样就成第二份口径了）。
    ⚠️ 项目传的是 **`project_key`（仓库名）**（§2.7.4），翻译成 id 在后端做。 */
 jcRowSave:async()=>{ if(!jcND.pj){ toast('<b>请先选「项目」</b>（点「项目」按钮展开候选）'); return; }
   const amt=numOf(jcND.contractAmt,{empty0:1});
   if(badMoney(amt)){ toast(badMoneyMsg('合同金额')); return; }
   const tAmt=(String(jcND.tradeContractAmt||'').trim()==='')?'':numOf(jcND.tradeContractAmt,{empty0:1});
   if(tAmt!==''&&badMoney(tAmt)){ toast(badMoneyMsg('贸易公司合同金额')); return; }
   const dt=/^\d{4}-\d{2}-\d{2}$/.test(String(jcND.date||''))?jcND.date:SYS_TODAY;
   const r=await jcAct(()=>API.m11Add({
       project_key:jcND.pj, contract_date:dt,
       material_name:String(jcND.material||'').trim(), supplier:String(jcND.supplier||'').trim(),
       contract_amt:String(amt), trade_co:String(jcND.tradeCo||'').trim()||null,
       trade_contract_amt:(tAmt===''?null:String(tAmt)),
       method:String(jcND.method||'').trim(), remark:String(jcND.remark||'').trim()}),
     x=>`已新增集采合同 <b>#${x.id}</b>（${esc(pjLabel(jcND.pj))} · ${esc(String(jcND.material||'').trim()||'（未填材料名）')}）—— 三态默认 <b>${esc(x.tag||'纳入台账')}</b><br><span class="mut sm">发票 / 付款金额请在该行「子表」里录入</span>`);
   if(r){
     /* 新增后**保证看得见**（同 MOD-03 / MOD-04 的做法）：放宽三档筛选；
        该行项目不在「项目」筛选里就**并进去**（否则刚建的合同被自己的筛选挡住）。 */
     if(fJc.tag!=='全部') fJc.tag='全部';
     if(fJc.arch!=='全部') fJc.arch='全部';
     if(fJc.sup) fJc.sup='';
     if(fJc.projs.length&&fJc.projs.indexOf(jcND.pj)<0) fJc.projs.push(jcND.pj);
     jcNewOn=false; pjClose('jcNPj'); render();
   } },

 /* —— MOD-13 ——：⭐ 本模块**没有自己的动作** —— 它是「导出 / 删除」这两件跨页能力的说明页
    （`TAIL-124` · 用户 2026-09-27 裁定 `B`：改成用户视角，⛔ 不在界面上摆工程台账）。
    ⚠️ 2026-09-28 删掉三枚**演示件**（它们点了只会弹**假数据**，用户会当成真功能）：
    `delDemo`（假删除确认框，单号 BZLL-202608-01、金额 128,600.00 全是编的）· `delOk`（"（演示）"toast）·
    `silent2`（"一期 Non-goals"弹窗）。⇒ **真入口**在各业务页：导出 = 各列表页的「导出 Excel」（`exp`）；
    删除 = 行上的「删除」（`plDelOk` / `ntDelOk` / `userDelOk` 等）。 */


 /* —— 筛选 —— */
 /* 筛选项改动即时生效（不设独立「应用筛选」按钮；时间筛选由 tmBtn 统一组件驱动） */
 filterNt:()=>{
   const cEl=$('#fCat'), aEl=$('#fAstat'), sEl=$('#fStat');
   fNt.cat=(cEl&&cEl.value)||'全部';
   fNt.astat=(aEl&&aEl.value)||'全部'; fNt.stat=(sEl&&sEl.value)||'全部';
   prunePick(); render();
 },
 filterReset:()=>{ fNt={month:fNt.month,cat:'全部',astat:'全部',stat:'未付清',projs:[]}; pjClose('pj'); prunePick(); render(); toast(`筛选条件已重置（年月保留 ${fNt.month}，付款状态回到默认「未付清」）`); },
 /* 项目多选 */
 pjToggle:()=>{ pjToggle('pj'); render(); },
 pjPick:t=>{ const f=t.dataset.pj; const i=fNt.projs.indexOf(f); if(i>=0) fNt.projs.splice(i,1); else fNt.projs.push(f); prunePick(); render(); },
 pjAll:()=>{ fNt.projs=PROJ_LIST(); prunePick(); render(); },
 pjNone:()=>{ fNt.projs=[]; prunePick(); render(); },
 /* 统一「年月选择器」组件 */
 /* 年月组件重绘：页面上的调 render()；弹窗内的（scope=fetch）必须重建弹窗，否则面板不刷新 */
 mpRefresh:sc=>{ if((sc==='fetch'||sc==='plimp')&&lastModal&&lastModal.reopen) lastModal.reopen(); else render(); },   /* ⚠️ `'lg'` 已移出：期初的截止年月现在在**展开区**（不是弹窗）⇒ 走 render() */
 mpToggle:t=>{ const id=t.dataset.id; mp.open=mp.open===id?null:id; mp.mode=''; mp.a=''; mp.b=''; mp.wq='';
   mp.year=Number(String(t.dataset.val).slice(0,4))||mp.year; ACT.mpRefresh(t.dataset.scope); },
 mpYear:t=>{ mp.year=(mp.year||Number(String(t.dataset.val).slice(0,4)))+(+t.dataset.d); ACT.mpRefresh(t.dataset.scope); },
 mpMode:t=>{ mp.mode=t.dataset.m; mp.a=''; mp.b=''; mp.wq=''; ACT.mpRefresh(t.dataset.scope); },   /* 面板内切模式（面板有哪些模式由**调用点**声明） */
 mpWQ:t=>{ mp.wq=t.dataset.qy+'Q'+t.dataset.qq; ACT.mpRefresh(t.dataset.scope); },                  /* 周面板：先选季度 → 换该季度的周列表 */
 mpPick:t=>{ const sc=t.dataset.scope, m=t.dataset.m; let v=t.dataset.val;
   if(m==='跨月'){ const a=mp.a||'', b=mp.b||'';                     /* 两击选区间：先点起点、再点终点（只同年内） */
     if(!a||b||v<a){ mp.a=v; mp.b=''; ACT.mpRefresh(sc); return; }
     v=mp.a+'~'+v; }
   mp.a=''; mp.b=''; mp.mode='';
   if(sc==='fetch'){ fetchM=v; mp.open=null; render(); ACT.fetchDlg(); return; }   /* 抓取弹窗内选月 → 重建弹窗回显（三个抓取入口共用） */
   if(sc==='pl'){ plf.ym=v; mp.open=null; prunePlPick(); render(); toast(`付款计划已切到 <b>${tmLabel(v)}</b>`); return; }
   /* ⛔ `plimp`（导入弹窗内选月）已随弹窗删除（`TAIL-75` `B5c`）—— 年月现在在「数据导入」页里选。 */
   if(sc==='lg'){ lgCut=v; mp.open=null; render(); return; }                        /* 期初展开区内选「截止年月」→ **只重绘**（不重算默认值） */
   if(sc==='fl'){ flf.ym=v; mp.open=null; render(); toast(`付款流水已切到 <b>${tmLabel(v)}</b>`); return; }
   if(sc==='awf'){ awfYm=v; mp.open=null; reloadM09(); toast(`特殊费用月报表已切到 <b>${tmLabel(v)}</b>（核算年月，§9.2）`); return; }   /* ⭐ 切换核算年月 ⇒ **重新取数**（手填项按「核算年月 ＋ 项目」各存一份；只 `render()` 会看到上一月那一份） */
   if(sc==='iv'){ fIvYm=v; mp.open=null; render();
     toast(v==='全部'?`库存单据已切到 <b>全部时间</b>（不限单据日期）`:`库存单据已切到 <b>${tmLabel(v)}</b>（核算年月，§9.2）`); return; }
   if(sc==='wh'){ fWhYm=v; mp.open=null; reloadM07(); toast(`收发结存已切到 <b>${tmLabel(v)}</b>（核算年月，§9.2）`); return; }   /* ⭐ 切换核算年月 ⇒ **重新取数**（`WHM[月]` 现在来自后端；只 `render()` 会看到空表） */
   if(sc==='ext'){ fExt.ym=v; mp.open=null; render(); toast(`提取「金额」列已切到 <b>${tmLabel(v)}</b>`); return; }
   if(sc==='pstb'){ pst.ym=v; mp.open=null; render(); return; }                                   /* 付款统计·左栏「按项目」的桶 */
   if(sc==='psta'){ if(/^\d{4}$/.test(v)) pst.year=+v; else if(/^\d{4}Q[1-4]$/.test(v)) pst.q=v;
     mp.open=null; render(); return; }                                                            /* 付款统计·右栏 年 / 季度 */
  if(sc==='df'){ fDf.ym=v; mp.open=null; render(); toast(`差异登记已切到 <b>${tmLabel(v)}</b>（核算月）`); return; }
  fNt.month=v;   /* 已取消「全局核算期」：年月只作用于本表自身的筛选 */
  mp.open=null; prunePick(); render();
  toast(v==='全部'?`已切换到 <b>全部时间</b>（不限单据日期）`
    :`已切换到 <b>${tmLabel(v)}</b>${/^\d{4}-\d{2}$/.test(v)?`（单据日期区间 ${v}-01 ~ ${monthEnd(v)}，闭区间）`:''}`); },
 mpClose:t=>{ mp.open=null; ACT.mpRefresh(t&&t.dataset?t.dataset.scope:null); },
  editSup:async t=>{ const n=NO.find(x=>x.id===t.dataset.id); if(!n) return;
    /* ⚠️ **业务判定不在壳里**：「仅「集采」分类可填」由后端 `notice_actions.jc_supplier_problem` 判
       （唯一出口）。这里只留**显示层**的前置（已剔除 / 已撤单的行不该可编辑）—— 后端那道照样会再拦一次。 */
    if(!ntLive(n)){ toast('这行已剔除 / 已撤单，不能改集采实际供应商'); render(); return; }
    /* ⭐ `M5-5`：⛔ **不本地改 `n.sup`**（那会与后端漂移、刷新就没了）。
       人工改一次 = 对自动预填值的**确认 / 否决** ⇒ 待确认标记（`SUP_SUG`）随之消失 ——
       但要等**后端真收下**才清（否则"改了没存上、标记却没了"）。 */
    const r=await jcLinkAct(()=>API.jcSupplier({notice_id:Number(n.id), supplier:String(t.value).trim()}),
      x=>x.supplier?`已录入集采实际供应商：<b>${esc(x.supplier)}</b> —— 它是「按供应商统计欠款」与集采台账付款引用的<b>关联锚点</b>`:'已清空集采实际供应商');
    if(r) delete SUP_SUG[n.id]; },
  /* ===== 集采供应商自动匹配（§6.6.3）=====
     ⭐ 分叉：1 家 → 预填 + 「自动匹配 · 待确认」（**不静默落库**，须点「采用」）；
             ≥2 家 → 弹窗让用户从命中集里选（**绝不取最长 / 第一个 / 相似度最高的**）；
             0 家 → 手动指定（允许自由录入）。 */
  supMatchRun:async t=>{ const n=NO.find(x=>x.id===t.dataset.id); if(!n) return;
    /* ⚠️ 这里只留**显示层**前置（已剔除 / 已撤单不可匹配）；「仅集采分类」由后端再拦一道。 */
    if(!ntLive(n)){ toast('这行已剔除 / 已撤单，不能自动匹配供应商'); return; }
    /* ⭐ `M5-5`：判定**从壳里搬走**（原先这里调前端的 `supPool`/`supMatch`）——
       现一律问后端 `POST /api/m03/actions/sup-match`（`mod03_notice/sup_match.py`）。
       ⛔ 壳里不再自带第二份片段/等级算法（两份判定 = 迟早漂移）。 */
    let d=null;
    try { d=await API.m03SupMatch({notice_id:Number(n.id)}); }
    catch(e){ return toast(`<b>没能匹配</b>：${esc(String((e&&e.message)||e))}`,7000); }
    if(!d||d.ok===false){ return toast(`<b>没能匹配</b>：${esc((d&&d.message)||'后端未返回原因')}`,7000); }
    const pool=d.pool||[], cands=d.cands||[], lvl=Number(d.level)||0;
    const lvlName=d.level_name||SUP_LVL_NAME[lvl]||'';     /* ⚠️ 后端为准，本地名只兜底 */
    if(!pool.length){ closeModal(); render();
      return toast(`<b>本项目下暂无集采合同供应商</b> —— 请先到「集采台账」页为 <b>${esc(pjLabel(d.project_key||ntProjKey(n))||'该项目')}</b> 建档，再回来匹配<br><span class="mut sm">§6.6.3 前提④：正常流程下一定先有集采合同</span>`,5200); }
    /* ⚠️ **0 家命中**（池非空但四级全不中）⇒ 走「手动指定」—— ⛔ 原先这条会掉进下面的多命中弹窗，
       开出一个**空候选**、点「采用」永远提示"请先选一家"（死路）。 */
    if(!cands.length){ closeModal(); render();
      return toast(`按 <b>全名 → 4 字 → 3 字 → 2 字</b> 四级探测<b>都没命中</b> —— 本项目供应商池共 <b>${pool.length}</b> 家<br><span class="mut sm">${pool.map(esc).join(' · ')}<br>请<b>手工录入</b>，或先到「集采台账」补齐该供应商的合同</span>`,8000); }
    if(cands.length===1){                 /* 1 家：预填 + 待确认（2 字等级同样只预填，不直填） */
      const hit=cands[0];
      /* ⚠️ 预填**也要落库**（原先只改本地 `n.sup` ⇒ 刷新就没了）—— 但**仍标「待确认」**：
         它是"系统猜的"，点「采用」才转正式值（⛔ 不静默落库成正式值）。 */
      const weaken=lvl===4?`<br><span style="color:var(--wn)">⚠️ 仅 <b>2 字片段</b>命中 —— 证据最弱，请务必确认</span>`:'';
      const r=await jcLinkAct(()=>API.jcSupplier({notice_id:Number(n.id), supplier:hit}),
        `按 <b>${esc(lvlName)}</b> 命中 <b>1</b> 家：<b>${esc(hit)}</b><br>已<b>预填</b>并标「<b>自动匹配 · 待确认</b>」—— 点「采用」转正式值，或直接改一下${weaken}`);
      if(r) SUP_SUG[n.id]=hit;            /* ⚠️ reload 之后才标（值以后端为准） */
      return; }
    /* ≥2 家：开弹窗让用户选（候选 = 歧义集本身） */
    supSel=null;
    modal({title:`选择供应商 · ${n.code}`,reopen:()=>ACT.supMatchRun({dataset:{id:n.id}}),
      body:`<div class="tip" style="margin-bottom:calc(10px * var(--fscale))">按 <b>${esc(lvlName)}</b> 命中 <b>${cands.length}</b> 家 —— <b>同等级内的多命中构成歧义</b>，<b>不猜</b>，请你选。<br>⚠️ 系统<b>绝不</b>取"最长的 / 第一个 / 最像的"（§6.6.3「明确不做」）。</div>
      <div class="fld"><label>这些是本项目集采合同里，其「${esc(lvlName)}」出现在单据名中的供应商</label>
      <select class="inp" id="supPickId" data-act="supPick" data-id="${n.id}">${cands.map(s=>`<option value="${esc(s)}">${esc(s)}</option>`).join('')}</select></div>
      <div class="sm mut">单据名称：<span class="fc">${esc(n.doc)}</span><br>本项目供应商池（${pool.length} 家）：${pool.map(esc).join(' · ')}</div>`,
      footer:`<button class="btn" data-act="closeModal">取消</button><button class="btn pri" data-act="supOk" data-id="${n.id}">采用所选供应商</button>`});
    toast(`按 <b>${esc(lvlName)}</b> 命中 <b>${cands.length}</b> 家 —— 已列出让你选（多命中<b>不让系统猜</b>）`,5200); },
  supPick:t=>{ supSel=t.value; },
  supOk:async t=>{ const n=NO.find(x=>x.id===t.dataset.id); if(!n) return; if(!supSel) return toast('请先选择一家供应商');
    const v=String(supSel).trim(); if(!v) return;
    /* ⭐ `M5-5`：⛔ 原先这里只改本地 `n.sup`（**刷新就没了**）⇒ 现落库。
       ⚠️ 落库后还要**标「待确认」**：因为这是"多命中里你选的一家"，仍是**预填**语义（点「采用」才转正式值）。 */
    closeModal();
    const r=await jcLinkAct(()=>API.jcSupplier({notice_id:Number(n.id), supplier:v}),
      `已把「集采实际供应商」设为 <b>${esc(v)}</b>（来自多命中候选 · 已标「自动匹配 · 待确认」—— 点「采用」转正式值）`);
    if(r) SUP_SUG[n.id]=v; },
  supAccept:async t=>{ const n=NO.find(x=>x.id===t.dataset.id); if(!n) return;
    if(!supHas(n)){ toast('这条没有待确认的自动匹配值'); return; }
    const v=String(n.sup||'').trim();            /* ⚠️ reload 后 `NO` 会重建 ⇒ 先把值取出来 */
    /* ⭐ `M5-5`：⛔ 原先这里只 `delete SUP_SUG`（**值根本没进库**，刷新就丢）⇒ 现落库。 */
    const r=await jcLinkAct(()=>API.jcSupplier({notice_id:Number(n.id), supplier:v}),
      `已确认「集采实际供应商」= <b>${esc(v)}</b> —— 「自动匹配 · 待确认」标记已消除，转为正式值<br><span class="mut sm">该字段是「按供应商统计欠款」的关联锚点（§4.4.3）</span>`);
    if(r) delete SUP_SUG[n.id]; },
  supReject:async t=>{ const n=NO.find(x=>x.id===t.dataset.id); if(!n) return;
    /* ⭐ `M5-5`：⛔ 原先这里只清本地（**后端还留着旧值**，刷新就回来）⇒ 现落库清空。 */
    const r=await jcLinkAct(()=>API.jcSupplier({notice_id:Number(n.id), supplier:''}),
      '已放弃自动匹配值 —— 该字段回到手工录入 / 可重新匹配');
    if(r) delete SUP_SUG[n.id]; },
 /* —— MOD-11 / MOD-01 / MOD-08 筛选：改动即时生效（R4，无「应用」按钮） —— */
 jcFilter:()=>{ const a=$('#fTag'), b=$('#fArch'), c=$('#fSup');
   fJc.tag=(a&&a.value)||'全部'; fJc.arch=(b&&b.value)||'全部'; fJc.sup=(c&&c.value)||''; pruneJcPick(); render(); },
 /* ⚠️ 复位一律【原地改字段】，不要 `fJc={...}` 重新赋值 —— 外部（自检）持有的是对象引用，
    重新赋值会让引用失效（同 BIGVAL 的教训） */
 jcReset:()=>{ fJc.tag='纳入台账'; fJc.arch='全部'; fJc.sup=''; fJc.amt=''; fJc.projs.length=0; pjClose('jcPj'); pruneJcPick(); render(); toast('集采台账筛选条件已重置（三态回到默认「纳入台账」）'); },
 /* 「项目」筛选（**通用控件** = 共用项目面板 `projPanel`，多选）—— 与 MOD-03 / MOD-04 同款，只是动作命名空间不同。
    ⚠️ 一律**原地改数组内容**（不要 `fJc.projs=…` 重新赋值）—— 外部持有的是那个数组的引用。 */
 jcPjToggle:()=>{ pjToggle('jcPj'); render(); },
 jcPjPick:t=>{ const v=t.dataset.pj; const i=fJc.projs.indexOf(v); if(i>=0) fJc.projs.splice(i,1); else fJc.projs.push(v); pruneJcPick(); render(); },
 jcPjAll:()=>{ fJc.projs.length=0; fJc.projs.push(...JC_PROJ_LIST()); pruneJcPick(); render(); },
 jcPjNone:()=>{ fJc.projs.length=0; pruneJcPick(); render(); },
 fPjStatus:t=>{ fPj.status=t.value||'在建'; render(); },
 fPjType:t=>{ fPj.type=t.value||'全部'; render(); },
 fPjQ:t=>{ fPj.q=t.value||''; render(); },
 fPjReset:()=>{ fPj.status='在建'; fPj.type='全部'; fPj.q=''; render(); toast('项目档案筛选已重置（状态回到默认「在建」，§2.7）'); },
 fIvDir:t=>{ fIvDir=t.value||'全部'; render(); },
 fIvReset:()=>{ invWhs.length=0; pjClose('invWh'); invOnlyAdj=false; fIvDir='全部'; fIvYm=bjMonth(-1); fIvCol={}; invColOpen=''; render();
   toast(`库存单据筛选已重置 —— 核算年月回到默认的 <b>${tmLabel(bjMonth(-1))}</b>（材料报表类默认 = 上月，§9.2）`); }
};

/* 事件委托 */
/* ⛔ `#2`（2026-09-26）：那张 **「变更事件白名单」（`CHG`）已整份删除** —— 表单类动作**不再需要登记**：
   `change` 委托按「事件只来自表单元素」直接跑（见下面那个 `change` 委托）。
   ⚠️ 原先 64 个名字的名单 ＋ `legacy.js` 追加 3 个 = 每加一个控件都要人记一次，
      漏了就是「选完没反应」的**静默**故障。 */
/* ⚠️ `'themeSet'` **在本列表里出现过、2026-09-21 已移除**：那时它是 `V.m15` 的一个 `<select>`
   （表单元素 ⇒ 当年必须登记，否则 `change` 被静默丢弃）。
   现在它是「外观主题」里的**卡片按钮**（一个 `<button>`，动作名仍是 `themeSet`，主题名走 `data-theme`）⇒
   走**点击委托**那条路，⛔ 不再是表单元素
   （⭐ `#2` 2026-09-26 起连"名单"都没了 ⇒ 想登记也没处登 —— 这一项整条下线）。
   ⚠️ 本注释**刻意不写出那个属性的完整形态**：`test_acc_theme_user.py` 会数"入口只有一处"，
      而它读的是**文本** ⇒ 注释里的示例会把它喂饱（同类坑踩过三次了）。 */
document.addEventListener('click',e=>{
  const t=e.target.closest('[data-act]'); if(!t) return;
  const nm=t.tagName.toLowerCase();
  if(nm==='input'||nm==='select'||nm==='textarea') return;   /* 表单元素交给 change */
  const a=t.dataset.act; if(!a||!ACT[a]) return;
  if(a==='maskBg'){ ACT.maskBg(t,e); return; }
  e.preventDefault(); ACT[a](t,e);
  /* ⭐ **单选面板点一下就收**（`#1` · 2026-09-26 用户要求「写在通用模块里」）——
     由**委托层**做，⛔ 不靠调用点自觉；多选面板渲染的是 `checkbox` ⇒ 天然不收（"勾完不关、好连续选"）。 */
  if(t.dataset.pjKey && t.type==='radio'){ PJ_OPEN[t.dataset.pjKey]=false; render(); }
});
document.addEventListener('change',e=>{
  const t=e.target.closest('[data-act]'); if(!t) return;
  const a=t.dataset.act; /* ⭐ `#2`（2026-09-26）：**没有名单了** —— `change` 事件只可能来自表单元素
     （`data-act` 挂在别的东西上根本收不到 change）⇒ 名单是纯多余的护栏，
     而它每漏登记一个动作就是一次**静默丢弃**（本仓踩过 `jcAmt` / `jcPartySet` / `themeSet`）。 */
  if(ACT[a]) ACT[a](t,e);
});
/* ⭐⭐ **带过滤的输入**（`input` 事件）—— 2026-09-27（用户裁定 ①② · 项目面板"搜索"）。
   ⚠️ 为什么**不走 `change`**（那样简单）：`change` 要等失焦/回车才发，边打边筛才是"找得到"；
   ⚠️ 为什么**不重绘**：`render()` 会把输入框整个重建 ⇒ **焦点与光标一起丢**（壳里踩过，
      见 `jcSubSet` 那条注释）⇒ 这里只**切 DOM 显示**（`applyPjFilters()`），
      关键词存进 `PJ_TXT`（⛔ 不重绘），重绘时由 `render()` 收尾把它填回去。
   ⚠️ 与 `change` / `click` 同一个委托风格：**没有名单**（`data-act` 只可能挂在真实输入上）。 */
document.addEventListener('input',e=>{
  const t=e.target.closest('[data-act="pjSearch"]'); if(!t) return;
  PJ_TXT[String(t.dataset.pk||'')]=t.value;
  applyPjFilters();
});
/* 点面板外部自动收起（年月选择器 / 项目面板）—— 在委托处理之后再跑，点自身不会被误关。
   ⚠️ **每一个项目面板**（MOD-03 pjIsOpen('pj') / MOD-04 pjIsOpen('plPj') / MOD-05 付款流水 pjIsOpen('flPj') / MOD-05 台账 pjIsOpen('ledPj') /
      MOD-05 期初展开区 pjIsOpen('lgPj') · MOD-11 集采新增展开区 pjIsOpen('jcNPj')（2026-09-13 增行模式新增 —— 都在 `.tw` 之外，不会被裁） /
      MOD-06 pjIsOpen('procPj') / MOD-08 pjIsOpen('invWh') / MOD-09 pjIsOpen('awfPj') / MOD-11 pjIsOpen('jcPj') /
      **通用导入面 `IMP.pjIsOpen('pj')`（2026-09-26 补 —— 见下）**）都要在这里登记，
   否则"点空白处不收起"（MOD-04、MOD-08、MOD-11 都曾漏登记）。
   ⚠️⚠️ **2026-09-26 实测漏登记的代价**（用户报障「展开待选列表后无法正常关闭」）：通用导入面换用共用面板时
      忘了把 `IMP.pjIsOpen('pj')` 加进来 ⇒ 面板**只能在"再点一次那个按钮"或"选中一项"时才收**，
      点页面别处一律不收 —— 与其他面板行为不一致（规则 4「相似元素不制造歧义」：同类控件行为必须一样）。
      ⇒ 判据：`backend/tests/test_imp_shell.py::test_本页的面板展开态登记在点外面收起里`（漏登记必红）。 */
document.addEventListener('click',e=>{
  const anyOpen = Object.keys(PJ_OPEN).some(k=>PJ_OPEN[k]);
  if(!anyOpen && mp.open===null) return;
  const inEl=cls=>!!(e.target&&e.target.closest&&e.target.closest(cls));
  let ch=false;
  /* ⭐ `#1`（2026-09-26）：**遍历注册表全关** —— ⛔ 不再逐个列面板名字
     （那份名单正是 2026-09-26 用户报障「展开后关不掉」的根：漏登记一个新面板就静默坏）。
     ⭐⭐ `TAIL-110`（2026-09-26）：**锚只剩一个名字 `.pjwrap`** —— 时间选择器与项目面板共用同一套
     （它同时管「逃出卡片裁剪」`placePops` 与「点浮层外收起」本函数）⇒ 判据只认**锚的包含关系**；
     ⛔ 别再给某类浮层单独加一个锚名（那就是"同一件事两个判据"）。 */
  if(!inEl('.pjwrap')){
    Object.keys(PJ_OPEN).forEach(k=>{ if(PJ_OPEN[k]){ PJ_OPEN[k]=false; ch=true; } });
    if(mp.open!==null){ mp.open=null; ch=true; }
  }
  if(ch){ render(); if(lastModal&&lastModal.reopen) lastModal.reopen(); }
});
document.addEventListener('keydown',e=>{
  /* 「非按钮但可点」元素的键盘等价操作 —— **通用一条，不逐个点名**：
     元素只要声明 `data-act` + `role="button"` + `tabindex="0"`，回车 / 空格即等价于点击
     （焦点框样式见样式表里的 `[data-act][role="button"]:focus-visible`）。
     ⚠️ 真实 `<button>` **不需要**这条（浏览器原生支持回车 / 空格）⇒ 只认带 `role="button"` 的元素，
        否则会与原生行为重复触发。新增可点元素时的做法 = 补那三个属性，**不要再来这里加选择器**。 */
  if(e.key==='Enter'||e.key===' '){
    const t=e.target&&e.target.closest&&e.target.closest('[data-act][role="button"]');
    if(t&&ACT[t.dataset.act]){ e.preventDefault(); ACT[t.dataset.act](t,e); return; }
  }
  if(e.key!=='Escape') return;
  /* ⭐ `#1`（2026-09-26）：**遍历注册表全关** —— ⛔ 不再手写面板名单（`invColOpen` 是另一种控件，单独收）。 */
  if(Object.keys(PJ_OPEN).some(k=>PJ_OPEN[k])||invColOpen!==''||mp.open!==null){ Object.keys(PJ_OPEN).forEach(k=>{ PJ_OPEN[k]=false; }); invColOpen=''; mp.open=null; render(); }
  closeModal(); });

/* =====================================================================
   ⭐⭐ 后端适配层（前端壳）—— 「**原型直接接数据**」的唯一出入口。
   ⛔ 前端**不做任何业务判定**：改分类 / 剔除 / 恢复 一律 POST 给后端，
      由后端**同一批纯函数**（`notice_actions`）判定并落库 —— 一份内容只许一个主人。
   ⚠️ 前端保留的只有**显示逻辑**（筛选 / 排序 / 合计 / 勾选态），它与后端判定**不重叠**。
   ===================================================================== */
