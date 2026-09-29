/* shell/view.js —— 壳的**独立件**（`P2-a` 拆件 · 2026-09-28 · 台账 `TAIL-164`）：导航 · 路由 · 渲染内核 · 虚拟滚动（原 §2）。
 *
 * ⭐ **为什么单开一件**：`render()` / `drawVirtual()` / `WIRED` 是**每页都要过**的一层；与页面代码分开，读页面时不必读它。
 *    `index.html` 原来一件套 4000 行（CSS ＋ HTML ＋ 内联脚本混装）⇒ 改一处要翻三个区
 *    （本会话两次白屏的同一个根）。本件是「**只拆非切片**」那一批里的一件。
 * ⛔ **本件不许碰**：任何 `V.<原型页>` 切片（它们**留在 `index.html`** —— 计划 §23 的口径，
 *    `ui_parity` 的 `U1` 逐行比它）· 口径判定（判定全在后端）· 界面文案的主人。
 * ⚠️ **加载顺序**：`index.html` 的 `<script src>` 顺序即真源 —— 本件排在 `actions.js` **之前**
 *    （`actions.js` / `core.js` 里有些表**加载期就求值**到本件的常量）。⛔ 别调顺序。
 * ⚠️ 本件的代码是**原样搬出**（逐字未改，含注释）；来历与搬法见计划 §15 `TAIL-164`。 */

/* =====================================================================
   2. 导航与路由
   ===================================================================== */
const NAV=[
 {g:'概览',items:[['home','看板','—']]},
 {g:'主数据 · 基础',items:[['m01','项目档案','MOD-01'],['m02','i8 接入层','MOD-02']]},
 {g:'付款域',items:[['m03','付款通知书','MOD-03'],['m04','付款计划','MOD-04'],['m05','付款流水与欠款统计','MOD-05']]},
 {g:'报表域',items:[['m06','过程资料','MOD-06'],['m07','收发结存与月度会大表','MOD-07'],['m08','库存单据与调整单','MOD-08'],['m09','特殊费用月报表','MOD-09'],['m10','机械费（暂缓）','MOD-10']]},
 {g:'集采域',items:[['m11','集采台账','MOD-11']]},
 {g:'全局',items:[['imp','数据导入','通用'],['m13','导出与删除','MOD-13'],['m14','规则配置','MOD-14'],['set','系统设置','MOD-14'],['m15','用户管理','MOD-15']]}
];
/* ⚠️ `set` = **暂留件收口**后的壳内页面（`§19` · 2026-09-21）——
  它**不在 `demo/` 原型里**（原型没有这一页）⇒ 实现放在 `web/shell/legacy.js`（接线层加件）。
  ⭐ 这也意味着 `ui_parity` 的 `U1`（只比原型**同名** `V.*` 切片）**不覆盖它** ⇒ 无"逐行对位"负担。
  ⛔ `m08imp`（库存单据导入）已删（2026-09-22 用户裁定「不要了」；`T8` 守卫）。
  ⛔ **`m06imp`（过程资料历史导入页）已下架**（`TAIL-75` `B5c` · 2026-09-22）：能力**整体搬进**
     「**数据导入**」页（`imp`，通用导入面 `/api/imp/m06_proc/*`）⇒ 同一件事不留两个入口。
  ⛔ **`m05imp`（历史付款导入页）也已下架**（`TAIL-75` `B5b` 第三步 · 2026-09-23 **用户裁定 `B`**）：
     同一件事只留一个入口 ⇒ 能力**整体搬进**「**数据导入**」页（`imp`，`/api/imp/m05_flow/*`）。
     ⚠️ **代价已记账**：旧页按**源表列位置**读、通用面按**列名**认 ⇒ 老台账若没有表头，
        请先补一行表头（判据 `ACC-FLOW-IMPORT-001/001-01` 已按此改写）。
     ⛔ 后端 `/api/m05/import/*` 那几条端点**同批连件删除**（`import_api.py`）。 */
const TITLE={home:'看板 · 待办',m01:'项目档案',m02:'i8 接入层',m03:'付款通知书',m04:'付款计划',m05:'付款流水与欠款统计',m06:'过程资料',m07:'收发结存与月度会大表',m08:'库存单据与调整单',m09:'特殊费用月报表',m10:'机械费（暂缓）',m11:'集采台账',m12:'差异登记',m13:'导出与删除',m14:'规则配置',m15:'用户管理',set:'系统设置',imp:'数据导入'};
let VIEW='home';
/* ⭐ **身份状态**（给顶栏"说实话"用）：`'in'` = 拿到了身份；`'none'` = **后端答了、但没有身份**
   （未登录 / 会话过期 / 名字对不上账号）；`''` = **压根没答上来**（取数失败 ⇒ `applyWho` 没跑）。
   ⚠️ 后两者**必须分开**：不然取数失败会被写成"你没登录"（那是**假话**，而用户会照着去登录、白折腾）。
   ⚠️ 由 `core.js` 的 `applyWho` 赋值（那附近有注释）。 */
let WHO_STATE='';
function go(k){ if(VIEW==='m03') pickSet.clear(); VIEW=k;
  /* ⭐ 批次 6（页级四态）：**进页先宣告"这几路要拉"** ⇒ 第一帧就是「正在读取…」，
     而不是先画一张空表（那和"确实没有数据"长得一样，守则 §4.2 明禁）。 */
  markPending(PAGE_LOAD[k]||[]);
  render(); $('.view').scrollTop=0; loadPaths(PAGE_LOAD[k]||[]); }   /* ⭐ `P3` 主体：进了哪页就（首次）拉哪页 —— ⛔ 不成环：`loadPaths` 只 render，不再调 `go` */
function render(){
  /* ⭐ 2026-09-28（用户裁定 `B` · 见审计清单 §六 "裁定 5"）：侧栏每项左侧那一列 = **模块编号**
     （`NAV` 表第三列，如 `MOD-13`）—— 它是**给人看的编号**（文档 / 《说明书》/ 判据件都按这套编号对齐），
     ⛔ **不是**实现细节、**别当黑话清掉**（守则 §3.1 的**例外**栏写着这条；`test_ux_deadcode` 的
     `ACC-UI-SHELL-001/001-35` 钉着它）。 */
  $('#nav').innerHTML=NAV.map(g=>`<div class="sb-g"><h5>${g.g}</h5>${g.items.map(([k,n,c])=>
    /* ⚠️ `dis`（"暂缓"）这一项**仍可点进**（它是一页说明，守则 §4.6 要求"不可用的入口要么隐藏、要么说明原因"）
       ⇒ 挂一句 `title` 说清"点进去是什么" —— 不然用户盯着一个灰项会不确定能不能点。 */
    `<div class="sb-i ${VIEW===k?'on':''} ${k==='m10'?'dis':''}" data-act="go" data-k="${k}" tabindex="0" role="button"${k==='m10'?' title="本模块近期不做 —— 点进去是一页说明"':''}><span class="c">${c}</span><span>${n}</span>${k==='m10'?'<span class="m">暂缓</span>':(WIRED.has(k)?'':'<span class="m">未接通</span>')}</div>`).join('')}</div>`).join('');
  /* ⭐⭐⭐ 2026-09-27（守则 §3.6「开发态标识要**明显但克制**，生产必须没有」· 用户裁定 `B`）：
     **只给"还没接通"的页如实标注，接通的页不挂任何状态牌。**
     ⚠️ 上一版是**每页**都挂一句进度牌（"已接后端真实数据" / "数据为模拟值"那种）—— 那是**给我们自己看的**：
        铺在 16 页标题上对用户是噪音（他只会想"难道还有假的？"），且「原型态 / 模拟值」属开发话术。
     ⛔ **别退回"一律挂一句"**：那正是 U2 当初要防的"对已接线页说假话"，而现在连"说实话"也不必说了 ——
        **不挂**就是最诚实的状态（没标 = 正常可用）。⚠️ 判据：离线 `ui_parity` U2 ＋ 真机 6 处断言
        （现已改成"接通页**不许**标未接通"）。 */
  $('#ttl').innerHTML=`${TITLE[VIEW]}${WIRED.has(VIEW)?'':'<em>本页数据尚未接通</em>'}`;
  /* 顶栏身份标识：取当前登录用户（§1.5.1「不得写死人名」）；转让管理员后随之变化。
     ⚠️ 身份**还没取到**（`boot()` 的那一路失败）时如实说"未取到"，⛔ 不拿人名占位 ——
        占一个名字就是**假值**，而且用户没法从界面上看出"这是猜的"。 */
  /* ⚠️ 没有身份时**要说清怎么办**（⭐ 2026-09-21 收紧「未登录不回落管理员」之后尤其重要）：
     会话缺失/过期 ⇒ 页面各处按钮**都是禁用的** ⇒ 只写"身份未取到"会让人以为**页面坏了**。
     ⛔ 但**不许**在这里自动跳登录页：那会让"看一眼"也变成强制登录，
        并且会让不带会话的真机自检 / 其他探针直接白屏。 */
  const who=$('#who'); if(who) who.innerHTML = CUR.role
    ? `<span class="dot d-ok"></span>${esc(CUR.name||CUR.acc)}（${CUR.role==='admin'?'管理员':'普通用户'}）`
    : (WHO_STATE==='none'
       ? `<span class="dot"></span>未登录 · <a class="link" href="/login">去登录</a>`
       : `<span class="dot"></span>身份未取到`);
  /* ⭐⭐⭐ 2026-09-27（`TAIL-117` 批次 6「四态统一」· 守则 §4.2「加载未完成不给最终数」/ §3.3「状态要真实」）：
     **页级四态的唯一拦截点** —— 「这一页现在该画什么」先问 `pageState()`：
       · `loading`（本页要的路还在拉）⇒ 画「正在读取…」，⛔ **不画空表 / 0 / 空图**
       · `error`（本页要的路坏了）⇒ 画「没能取到 ＋ 哪一块 ＋ 重试」，⛔ 不装作"这页没数据"
     改前这里是**直接渲染**：数据没回来那一瞬，屏幕上是空表（与"确实没有"**一模一样**）。
     ⚠️ 只有 `ready` 才生成真实视图 ⇒ ⛔ 别在这里再判别的条件（判据集中在 `pageState()` 一处）。
     ⚠️ 状态页**不走走虚拟滚动**（`vsOn` 按行数判，喂它没有表的 HTML 是错的）⇒ 直接写入即可。 */
  const st=pageState();
  if(st.kind!=='ready'){
    const gate=pageGate(st);
    const g0=scrollHost(); const keep0=g0?g0.scrollTop:0;
    $('#view').innerHTML=gate;
    const g1=scrollHost(); if(g1) g1.scrollTop=keep0;
    /* ⚠️ **状态页不跑 `BIND[VIEW]`、也不调 `placePops()` / `applyPjFilters()`**：
       那些钩子假设"表 / 卡 / 浮层已经在 DOM 里"（注入按钮、反射全选框、定位面板…）——
       状态页里**一个都没有**，白跑一趟还容易碰出异常。
       ⭐ `placePops()` 只该在**两条真实渲染路径**里调（普通 + 虚拟滚动）—— 常驻判据
         `test_shell_render::test_通用浮层要逃出卡片裁剪_机制只有一处` 数着这个数。
       ⭐ `render` 外层的 `m05Sync()` 照跑（它自己判 `LOADED`，见其注释）。 */
    return;
  }
  /* 视图 HTML 先生成、再统一应用表头排序，最后写入页面（排序是纯字符串变换，见 applySorts） */
  const html=applySorts((V[VIEW]||(()=>'<div class="tip">未实现</div>'))(),VIEW);
  /* ⭐⭐ 滚动位置保留（2026-09-21 报障 m03 勾选跳顶 · **2026-09-25 修对容器**）：
     `pick`（actions.js）这类**本页内刷新**走 `render()`，innerHTML 一换 ⇒ 承接滚动的那个元素
     被**整体重建** ⇒ scrollTop 归零（替换瞬间内容高度塌成 0）。⇒ 写入前**记下**、写完**还原**。
     ⚠️ **容器一律走 `scrollHost()`**（真滚的是表格外框 `.tw`，⛔ 不是 `.view`）——
       2026-09-21 那次只记/还 `.view` ⇒ 对 m03 **完全无效**，用户 2026-09-25 复报。
     ⚠️ `go()` 不受影响 —— 它本来就在 `render()` 之后显式 `scrollTop=0`（切页回顶是**故意的**）。 */
  const scroller=scrollHost(); const keep=scroller?scroller.scrollTop:0;
  /* ⭐⭐ 大表渐进渲染（2026-09-21 用户报障：m08 点进去卡一下 —— 库存明细 1900+ 行，
     一次 innerHTML = 一次性 parse ＋ 布局，阻塞主线程几百毫秒）：
     HTML **仍然一次生成**（排序 / 合计行口径不变），但**分帧写入**：先写第一块，余下每帧追一块。
     ⛔ 切点必须落在行边界（`</tr>`，退而求其次 `>`）—— 半个标签会被浏览器静默吞掉；
     ⛔ `BIND[VIEW]`（注入按钮 / 渲染后钩子）必须等**最后一块**写完再调；
     ⛔ 渲染途中用户切页 ⇒ **丢弃剩余块**（`#view` 已是别的页的内容，续写会串页）。 */
  /* ⛔ 虚拟滚动**设计红线**（两连败换来的，⛔ 别重蹈）：
     ① **每次都写"完整片段"**（pre ＋ 垫高行 ＋ 窗口行 ＋ post，**一次 innerHTML**）——
        绝不往 `#view` 追加表格片段（div 上下文里 `<tr>` 会被解析器**整段吞掉**）；
     ② 绝不把一张表拆成多个 `<table>`（列宽 / 表头吸顶会错位）；
     ③ 行高**实测＋估算混合**（会换行 ⇒ 不能假定等高）：渲染过的行**实测回填**，没渲染的按上限估；
        `base`（第 0 行的绝对位置）用"窗口首行实测位置"自校正。
     ⚠️ **只要行数 ≥ 阈值就虚拟化**，⛔ **不能用"当前数据量小"当判据**（没正式用的页以后可能上万行；
        名单式的下场 = "某页涨上去、忘了加名单 ⇒ 永远不生效"）；例外表 `VSCROLL` **只用来关掉或调阈值**。
     —— 起因 / 实测耗时 / 全局启用的来历见《开发计划》§15 `TAIL-66`。 */
  /* ⚠️ 虚拟滚动那条路也在 `startVirtual` 里就把 DOM 写完了 ⇒ 浮层定位**两条路都要跑**
     （`placePops` 幂等；漏一条 ⇒ 大表页上展开的浮层仍被卡片裁）。 */
  if(vsOn(VIEW) && startVirtual(html, scroller, keep)){ placePops(); applyPjFilters(); return; }
  $('#view').innerHTML=html;
  /* ⚠️ 还原时**重新解析**滚动容器：`.tw` 已被上一行整体重建（旧元素连同它的 scrollTop 一起没了）。 */
  const host2=scrollHost(); if(host2) host2.scrollTop=keep;
  if(BIND[VIEW]) BIND[VIEW]();
  placePops();          /* ⭐ 通用浮层逃出卡片裁剪（`TAIL-109`/`TAIL-110`）—— 见 `placePops` 的注释 */
  applyPjFilters();     /* ⭐ 项目面板的搜索词 / 归档折叠**重涂**（①② 2026-09-27）—— 见该函数注释 */
}
/* ⭐ `TAIL-66` 后的语义：**默认全开**，`VSCROLL` = **例外表** ——
   `{m07:{off:true}}` = 这页不虚拟化；`{m09:{min:800}}` = 这页阈值调到 800。
   ⛔ 加例外必须写理由（在这里注释），否则又变回"名单式"的黑洞。 */
const VS_MIN=400;                 /* 全局默认阈值：≥ 这个行数才虚拟化 */
const VSCROLL={};                 /* 例外表（现为空 ⇒ **所有大表页一律虚拟化**） */
function vsOn(v){ const c=VSCROLL[v]; return !(c && c.off); }
function vsMin(v){ const c=VSCROLL[v]; return (c && c.min) || VS_MIN; }
/* ⭐⭐ **焦点护栏**（`TAIL-66`）：滚动会**重写 innerHTML** ⇒ 正在编辑的输入框会被"连值带焦点"蒸发
   （m07 手填 / m11 子表就是这种页）。⇒ 重写前先看：**焦点是不是在本页的可编辑元素里** ——
   是 ⇒ **推迟重画**（记 `pending`），等焦点离开（`focusout`）或下一次滚动再补画。
   ⛔ 别改成"照画"：那会让用户"输到一半滚一下就没了"，而且**不报错**（最坏的一类缺陷）。 */
function vsEditing(){
  const a=document.activeElement, v=$('#view');
  if(!a||!v||!v.contains(a)) return false;
  const editable=a.tagName==='INPUT'||a.tagName==='TEXTAREA'||a.tagName==='SELECT'||a.isContentEditable===true;
  if(!editable) return false;
  /* ⭐⭐ 2026-09-25 用户报障**第二次**（"滚轮 / 中键自动滚 / 拖滚动条**三种全滚不动**"）的**根**：
     上面那句"**在本页**的可编辑元素里"**太宽** —— m08 这类页的**筛选 / 搜索框也在 `#view` 里** ⇒
     用户点过一次筛选框，焦点就一直留在那儿 ⇒ **每一次重画都被推迟** ⇒ 画面**永远不更新**
     （滚动位置/滚动条在动、内容不动 ⇒ 三种滚法**都**表现为"滚不动"）。
     ⚠️ 为什么之前没抓到：探针**没有把焦点放进筛选框**（那正是用户的操作路径）——
        又一个"量测方式不是用户的方式"（见 `ops/README.md` 同日两条同族纪律）。
     ⇒ 收紧为：**只有焦点落在表格内**（`.tw` 里 = 真会被 `innerHTML` 重写"连值带焦点蒸发"的那些编辑器，
        即 m07 手填 / m11 子表）才推迟；**表外的筛选框不挡滚动**。 */
  return !!(a.closest && a.closest('.tw'));
}
let VS=null;                                    /* 当前虚拟态（切页 / 重渲即重建） */
const EH=28;
const VS_WIN=45, VS_OVER=10;                   /* 窗口行数 / 回看行数（上垫高 = a×EH）—— `TAIL-94` 重写 */                                    /* 未渲染行的估算高（本表众数 ≈27px） */
/* ⭐⭐ 滚动容器**唯一出口**（2026-09-25 修两个用户报障：① m03 勾选一行 ⇒ 列表跳回顶部；
   ② 虚拟滚动"滚快了下面的就渲染不出来" —— **两者同根**）：
   · 真正承接溢出的是**表格外框 `.tw`**（它自带 `max-height` ＋ `overflow:auto`，见 CSS `index.html` 的 `.tw`），
     ⛔ 不是 `.view`（`.view` 的 overflow 被 `.tw` 的高度封顶 ⇒ 它的 `scrollTop` 恒 ≈0）；
   · 2026-09-21 那次"修过"只记/还了 `.view` ⇒ **作用对象错**，所以报障又回来了；
   · ⚠️ `#view` 每次重绘**整体重建** ⇒ 挂在后代上的 `onscroll` 会随 DOM 一起蒸发
     ⇒ 监听一律挂**不会被重建的 `#view`**，并且必须走**捕获阶段**（`scroll` **不冒泡**，
       只有"祖先 ＋ 捕获"两条都满足，才收得到后代 `.tw` 的滚动）。 */
function scrollHost(){ const v=$('#view'); if(!v) return null;
  const t=v.querySelector('.tw'); return (t && t.scrollHeight>t.clientHeight+1) ? t : v; }
function splitRows(html){
  /* ⚠️ 只认 **tbody 里的行**：第一个 `<tr>` 往往是 `<thead>` 的表头行 —— 截在那里，
     整段窗口会写进 thead 上下文（tbody 空、页面没行 —— 2026-09-21 真机抓到）。 */
  const TAG=/<(\/?)(tr|tbody)\b[^>]*>/gi, spans=[]; let open=-1, inTbody=0, m;
  while((m=TAG.exec(html))){
    const name=m[2].toLowerCase();
    if(name==='tbody'){ inTbody+= (m[1]==='/' ? -1 : 1); continue; }
    if(name!=='tr') continue;
    if(m[1]==='/'){ if(open>=0 && inTbody>0) spans.push([open, m.index+m[0].length]); open=-1; }
    else if(open<0 && inTbody>0) open=m.index;
  }
  if(!spans.length) return null;
  return { pre:html.slice(0,spans[0][0]), post:html.slice(spans[spans.length-1][1]),
           rows:spans.map(s=>html.slice(s[0],s[1])) };
}
function startVirtual(html, scroller, keep){
  const sp=splitRows(html);
  if(!sp || sp.rows.length < vsMin(VIEW)) return false;
  VS={view:VIEW, pre:sp.pre, post:sp.post, rows:sp.rows, h:new Array(sp.rows.length).fill(0),
      colN:((sp.pre.match(/<th\b/gi)||[]).length || (sp.rows[0].match(/<td\b/gi)||[]).length || 8),
      base:0, t:0, raf:0, pending:false, a:-1, b:-1, tb:null};
  drawVirtual(true);
  /* ⚠️ 滚动位置的还原见 `render()`（本函数只负责**首帧** —— 此刻 DOM 里还是旧页面）。 */
  const host0=scrollHost(); if(host0) host0.scrollTop=keep;
  /* ⭐⭐ 监听挂**不会被重建的 `#view`** ＋ **捕获阶段**（`scroll` 不冒泡 ⇒ 非捕获收不到 `.tw` 的滚动；
     挂 `.tw` 上则每次重绘随 DOM 蒸发 —— 2026-09-25 用户"滚快了下面渲染不出来"就是这两条一起犯的）。
     ⭐ 重画节奏 = **rAF（每帧最多一次）**，而不是 30ms 的 trailing 去抖：去抖在快速滚动期间只画最后一下、
     中间全是空白垫高行。 */
  const v=$('#view');
  if(v && !v._vsScrollBound){
    v._vsScrollBound=true;
    v.addEventListener('scroll',()=>{
      if(!VS||VS.view!==VIEW) return;
      if(VS.raf) return;
      VS.raf=requestAnimationFrame(()=>{ VS.raf=0; drawVirtual(false); });
    },true);
    /* ⭐ 焦点护栏的**补画**：编辑中被推迟的重画，焦点一离开就补上（否则会留着旧窗口不刷新）。 */
    v.addEventListener('focusout',()=>{
      setTimeout(()=>{ if(VS&&VS.view===VIEW&&VS.pending) drawVirtual(false); },0);
    });
  }
  return true;
}
/* ⭐⭐ 虚拟滚动**重写**（`TAIL-94` · 2026-09-25）：**单一渲染路径 ＋ 文档总高恒定 ＋ 滚动中零写入**。
   前六次尝试全部回滚换来的三条结论（⛔ 别再犯）：
   ① **不再 `$('#view').innerHTML=…`** —— 那会把真容器 `.tw` 一起换掉 ⇒ 打断滚轮手势、`scrollTop` 归零；
      而"程序化改 scrollTop 能动"的假象骗过两次自检（见 `ops/README.md` 两条纪律）。
   ② **不在滚动中写 `scrollTop`** —— 锚定回拉那种"写一下修正"会顶掉用户这一格的滚轮量
      ⇒ 真机表现 =「往下能滚、**往上回不来**」（第 4 次尝试就是这么废的）。
   ③ ⇒ 只用 `tbody.innerHTML` 换**窗口行**（容器 / 表头 / `.tw` 一个字节都不动），
      并让**文档总高恒为 `n*EH`**：下垫高吸收"真高 − 估算"的差量；**贴底时改由上垫高吸收**
      —— 因为最后一行**必须是合计行**、⛔ 不能是空垫高行（真机自检抓过）。
   ④ 于是窗口 = `f(scrollTop)` 的**纯函数**：无反馈环、无累积漂移、上下双向对称。 */
function drawVirtual(first){
  /* ⚠️ 读的必须是**真容器**（`scrollHost()`）—— 读 `.view` 会恒得 `st≈0` ⇒ 窗口永不推进。 */
  const sc=scrollHost()||$('.view'); if(!sc||!VS) return;
  /* ⭐⭐ 焦点护栏（`TAIL-66`）：首帧必须画（否则空页）；滚动重画时若焦点在**表内**编辑控件里 ⇒ 推迟。 */
  if(!first && vsEditing()){ VS.pending=true; return; }
  VS.pending=false;
  const n=VS.rows.length, st=sc.scrollTop, vh=sc.clientHeight;
  let a,b;
  /* ⭐ 底部钳制（虚拟列表标配）：贴底 ⇒ 窗口**必须**收在最后一行（合计行永远如约出现）。 */
  if(st + vh >= n*EH - 2){ b=n; a=Math.max(0, n-VS_WIN-VS_OVER); }
  else { a=Math.max(0, Math.floor(st/EH)-VS_OVER); b=Math.min(n, a+VS_WIN+VS_OVER); }
  /* ⭐ 窗口没变 ⇒ 一个字节都别动（滚动中反复重写会打断手势）。 */
  if(!first && a===VS.a && b===VS.b) return;
  const topH0=a*EH, botH0=(n-b)*EH, winRows=VS.rows.slice(a,b);
  const SP=h => h>0
    ? '<tr class="vsp" style="height:'+Math.round(h)+'px"><td colspan="'+VS.colN+'" style="border:0;padding:0"></td></tr>'
    : '';
  if(first){
    /* 红线①：整页**一次**写完整片段（pre ＋ 上垫高 ＋ 窗口行 ＋ 下垫高 ＋ post），⛔ 不追加片段。 */
    $('#view').innerHTML = VS.pre + SP(topH0) + winRows.join('') + SP(botH0) + VS.post;
    if(BIND[VIEW]) BIND[VIEW]();
    VS.tb=$('#view').querySelector('tbody');
  }else{
    /* ⭐⭐ 滚动重画：**只换 tbody 的行** —— `.tw` / 表头 / `#view` 都不动 ⇒ 手势不被打断、`scrollTop` 不用还。 */
    const tb=(VS.tb && document.contains(VS.tb)) ? VS.tb : $('#view').querySelector('tbody');
    if(!tb) return;
    VS.tb=tb;
    tb.innerHTML = SP(topH0) + winRows.join('') + SP(botH0);
  }
  /* 红线③：窗口行**实测回填**（行高 27~91px 不等高）＋ 差量吸收 ⇒ 文档总高恒为 `n*EH`。 */
  const trs=VS.tb?VS.tb.children:null;
  if(trs && trs.length){
    const hasTop=!!(trs[0] && trs[0].classList && trs[0].classList.contains('vsp'));
    let H=0;
    for(let i=hasTop?1:0; i<trs.length; i++){
      const r=trs[i];
      if(r.classList && r.classList.contains('vsp')) continue;
      const hh=r.getBoundingClientRect().height;
      const gi=a+i-(hasTop?1:0);
      if(gi>=0 && gi<n) VS.h[gi]=+hh.toFixed(1);
      H+=hh;
    }
    const delta=(b-a)*EH - H;                 /* 真高比估算高 ⇒ delta<0 */
    if(b<n){                                  /* 下垫高吸收（它在视口外 ⇒ 不可见） */
      const bt=trs[trs.length-1];
      if(bt && bt.classList.contains('vsp')) bt.style.height=Math.max(0, Math.round(botH0+delta))+'px';
    }else if(hasTop){                         /* ⭐ 贴底：差量吃进**上垫高**（末行必须仍是合计行） */
      trs[0].style.height=Math.max(0, Math.round(topH0+delta))+'px';
    }
    const r0=trs[hasTop?1:0];
    if(r0) VS.base=r0.getBoundingClientRect().top - sc.getBoundingClientRect().top + sc.scrollTop - topH0;
  }
  VS.a=a; VS.b=b;
}

const WIRED=new Set(['home','m03','m01','m02','m04','m05','m06','m07','m08','m09','m14','m11','m15',
  /* ⭐ `§19`「暂留件收口」（2026-09-21）：设置 —— 它**全读后端真数据**（`/api/m14/settings`）
     ⇒ 顶栏照实说「已接后端真实数据」。
     ⛔ `m08imp` 已删（2026-09-22 用户裁定）。 */
  'set',
  /* ⭐ `TAIL-75` `B5`（2026-09-22）：**通用导入面**的壳页 —— 域清单与一步一数据全来自后端
     （`/api/imp/domains` → `/api/imp/{域}/schema|parse|preview|commit|rollback`）⇒ 同样照实说"已接后端"。
     ⛔ `m06imp` **已下架**（`B5c`：能力整体搬进本页）· ⛔ **`m05imp` 也已下架**（`B5b` 第三步 ·
     2026-09-23 用户裁定 `B`：同一件事只留一个入口，`/api/imp/m05_flow/*` 承接）。 */
  'imp']);

/* ---------- 运行记录（§3.1.3 抓取 / §4.6 打印）—— 最小形态：时间 · 对象 · 结果 · 失败原因 ----------
   口径主人 =《材料科业务全流程说明书》§3.1.3 / §4.6「执行记录与看板提示」：
     ① 每次抓取留一条记录 ⇒ 供**看板页**提示「本月尚未抓取」「最近一次抓取失败（含表名与时间）」；
     ② 每次打印留一条记录 ⇒ 供**看板页**提示「打印投递失败」。
   ⚠️ 「存哪里 / 留多久」= **技术实现**（《技术栈选型分析》§3.1「运行记录（技术台账）」）⇒ **不新增 ENT-***，不动业务数据模型。
   ⚠️ 本原型**只做只读展示**（看板页的提示），不做录入界面；**月份由 `at` 派生**、不另存字段（防副本）。
   ⭐ **2026-09-21 接线**：原先这里是**写死的演示数组** `RUNLOG`（看板 ⑦⑬⑭ 读它 ⇒ 看板成了全站
      唯一还在显示模拟数据的页）。现在改由 `reloadHome()` 从 `GET /api/home/run-counts` 填 `HOME`。
   ⚠️⚠️ ⛔ **别改回"在壳里扫执行记录端点最近 N 条"**：那个端点是**窗口**（`limit ≤ 200`），
      而 `run_record` 是**流水表**（实测 ≈10 条/天 ⇒ 一个月 ≈300 条）⇒ **会漏，且漏了不报错**
      （症状 = 看板说"本月未抓" ⇒ 用户照着去重抓 ⇒ 白顶一次 i8 的号）。
      「本月有没有成功抓取」这类**跨全表**的问题一律问后端（SQL 全表，口径在 `app/home/service.py`）。
   字段：`counts` = 三个 0/1 待办数 · `latest` = 最近那条失败记录（**壳负责说成人话**，⛔ 后端不拼字符串）。 */
let HOME = { counts: { fetchDue: 0, fetchFail: 0, printFail: 0 }, latest: { fetchFail: null, printFail: null } };
let HOME_ERR = '';      /* 取数失败 ⇒ ⑦⑬⑭ 三格显「—」并说明，⛔ 不拿 0 冒充"没有待办"（铁律 4） */

