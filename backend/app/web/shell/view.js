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
 {g:'全局',items:[['imp','数据导入','通用'],['m14','规则配置','MOD-14'],['set','系统设置','MOD-14'],['m15','用户管理','MOD-15']]}
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
const TITLE={home:'看板 · 待办',m01:'项目档案',m02:'i8 接入层',m03:'付款通知书',m04:'付款计划',m05:'付款流水与欠款统计',m06:'过程资料',m07:'收发结存与月度会大表',m08:'库存单据与调整单',m09:'特殊费用月报表',m10:'机械费（暂缓）',m11:'集采台账',m12:'差异登记',m14:'规则配置',m15:'用户管理',set:'系统设置',imp:'数据导入'};
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
     （`NAV` 表第三列，如 `MOD-14`）—— 它是**给人看的编号**（文档 / 《说明书》/ 判据件都按这套编号对齐），
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
    /* ⚠️ **状态页不跑 `runBind(VIEW)`、也不调 `placePops()` / `applyPjFilters()`**：
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
     ⛔ `runBind(VIEW)`（注入按钮 / 渲染后钩子）必须等**最后一块**写完再调；
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
  /* ⭐ `TAIL-64` P5-a：`vsOn` 这一层门移进 `startVirtual` 内部。
     ⭐ **P5-c**（2026-09-30）：**页级那条路已删** ⇒ 虚拟滚动只剩**表级**这一条。
     ⚠️ `scroller` 这个参数**同批删掉**：它原本只给页级那半用，而页级那半其实一直**没用它**
        （自己 `scrollHost()` 重取一个）⇒ 留着会让人以为"传进去就有用"。 */
  if(startVirtual(html, keep)){ placePops(); applyPjFilters(); return; }
  $('#view').innerHTML=html;
  /* ⚠️ 还原时**重新解析**滚动容器：`.tw` 已被上一行整体重建（旧元素连同它的 scrollTop 一起没了）。 */
  const host2=scrollHost(); if(host2) host2.scrollTop=keep;
  runBind(VIEW);
  placePops();          /* ⭐ 通用浮层逃出卡片裁剪（`TAIL-109`/`TAIL-110`）—— 见 `placePops` 的注释 */
  applyPjFilters();     /* ⭐ 项目面板的搜索词 / 归档折叠**重涂**（①② 2026-09-27）—— 见该函数注释 */
}
/* ⭐ `TAIL-66` 后的语义：**默认全开**，`VSCROLL` = **例外表** ——
   `{m07:{off:true}}` = 这页不虚拟化；`{m09:{min:800}}` = 这页阈值调到 800。
   ⛔ 加例外必须写理由（在这里注释），否则又变回"名单式"的黑洞。 */
const VS_MIN=400;                 /* 全局默认阈值：≥ 这个行数才虚拟化 */
/* 例外表（**现为空**）＝ **逃生阀**（⛔ 不是"逐页点名"的名单）：某页哪天出回归，能在这里一键关掉 / 调阈值。
   ⭐ `TAIL-64` P5-b（2026-09-30）：**表级那条路已经"一律优先"** —— 凡带 `data-vs` 标记的表
   （现在**每一张表**都带）一旦行数够，就由表级接管 ⇒ 不再需要 `m08` 那种"点名"例外（`P5-a` 试点期加过、
   `P5-b` 撤掉）。
   ⭐ **P5-c**（同日）：页级那条路删掉之后，`off` **恢复 `TAIL-66` 的原意 = 「这页不虚拟化」** ——
   `P5-a` 试点期它曾短暂表示"**页级**对它关掉、改走表级"，那个语义随页级那条路一起没了（⛔ 别再往那个方向理解）。
   ⛔ 加例外必须写理由（在这里），否则又变回"名单式"的黑洞。 */
const VSCROLL={};
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
/* ⭐ `TAIL-64` P5-a（2026-09-30）：**表级**虚拟滚动的实例表（一页可以有多张带 `data-vs` 的表）。
   ⭐ **P5-c**（同日）：**页级那条路已删** ⇒ 壳里只剩这一个"虚拟态"（原先那个整页实例 `VS` 一并删掉：
   ⛔ 本轮起"把整页重写成窗口"的形态不该再出现，见 `drawVirtual` 的红线②）。
   ⚠️ 每次分派（`startVirtual`）**先清空**、认领时再填 —— 旧形态只在"本页没有带标记的表"那一支清空
   ⇒ 别的分支会把上一页认领过的实例留到下页（真机量测读得到，见 `_p5c_survey.py`）。 */
let VS_TS=[];
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
  /* ⭐ `TAIL-64` P5-a 曾在这里加过一条"当前虚拟态那张表优先"——⭐ **P5-c**（2026-09-30）**撤掉**：
     那是 P5-a 两条路并存期的拐杖（页级实例**没有** `tw`）⇒ 页级删掉后它只会让"记/还哪个容器"
     取决于**最后画过哪张表**（多表页上不可预期）。现在回到唯一那条口径：**第一个自带滚动的 `.tw`**；
     而表级那条路**自己**按每张表记/还（见 `startVirtualTables`），⛔ 不靠这里。 */
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
/* ⭐ 垫高行的**唯一出口**（`TAIL-64` P5-a 起两处要用：页级那条路 ＋ 表级首帧）—— 形态**逐字未改**。 */
function vsPad(h, colN){
  return h>0
    ? '<tr class="vsp" style="height:'+Math.round(h)+'px"><td colspan="'+colN+'" style="border:0;padding:0"></td></tr>'
    : '';
}
/* ⭐⭐ `TAIL-64` P5-a（2026-09-30）：本页所有**带 `data-vs` 标记**的 `tbody` 块（在**字符串层**找，
   ⛔ 不是先写进 DOM 再找 —— 那样 1000+ 行会被浏览器**整批 parse**，正是 `TAIL-66` 当初要避免的卡顿）。 */
function vsTableHits(html){
  return [...String(html).matchAll(/<tbody[^>]*\bdata-vs="[^"]*"[^>]*>[\s\S]*?<\/tbody>/g)];
}
/* ⭐⭐ 滚动监听的**唯一挂载点** —— ⛔ 必须排在 `startVirtual` 里**任何 `return` 之前**
   （它下面有三处提前退出：逃生阀 `vsOn`／本页没有带标记的表／分派）。⭐ 这条规矩的来历（`P5-a`）：
   当时它写在**页级那半**里，而表级那条从函数顶部就 `return` ⇒ **表级页一个监听都挂不上**
   （2026-09-30 真机当场抓到：滚动条能拖、内容一动不动；而离线判据全绿）。
   ⚠️ `P5-c` 之后页级那条路已删，但**这条规矩不变** —— 剩下那三处 `return` 一样会把它跳过。
   ⚠️ 挂**不会被重建的 `#view`** ＋ **捕获阶段**（`scroll` **不冒泡** ⇒ 非捕获收不到 `.tw` 的滚动；
      挂 `.tw` 上则每次重绘随 DOM 蒸发 —— 2026-09-25 用户"滚快了下面渲染不出来"就是这两条一起犯的）。 */
function vsBindScroll(){
  const v=$('#view');
  if(!v || v._vsScrollBound) return;
  v._vsScrollBound=true;
  /* ⭐ `P5-c`：滚动的**来源**只可能是**某一张表自己的 `.tw`**（表级是唯一那条路）⇒ 按来源挑实例。
     ⚠️ 实例的 `tw` **正是事件目标**时才认它 —— 顺带保证"元素已从文档里摘掉"的老实例不会被误认
        （`VS_TS` 每页会清空，但清空之前那个旧元素可能还挂在事件流上）。 */
  v.addEventListener('scroll',(e)=>{
    const it=VS_TS.find(x=>x.tw===e.target);
    if(!it) return;
    if(it.raf) return;
    it.raf=requestAnimationFrame(()=>{ it.raf=0; drawVirtual(it); });
  },true);
  /* ⭐ 焦点护栏的**补画**：编辑中被推迟的重画，焦点一离开就补上（否则会留着旧窗口不刷新）。 */
  v.addEventListener('focusout',()=>{
    setTimeout(()=>{ VS_TS.forEach(it=>{ if(it&&it.pending) drawVirtual(it); }); },0);
  });
}
function startVirtual(html, keep){
  /* ⭐⭐ `TAIL-64` P5-a（2026-09-30）：**本页若有带 `data-vs` 的表 ⇒ 由表级接管**。
     ⭐ **P5-c**（同日）：页级那条路（"整页一张大表"）**已删** ⇒ 这里只分派给 `startVirtualTables`。
     ⛔ **顺序不许动**：先**挂监听**（下面三处 `return` 都会跳过它 —— 而"没挂上监听"的真机症状是
        「滚动条能拖、内容一动不动」，且**离线判据全绿**，2026-09-30 当场抓到过一次）
        ⇒ 再**清空**实例表 ⇒ 再**逃生阀** ⇒ 再**分派**。
     ⭐ 监听与**重画节奏**（`rAF`：每帧最多一次 —— ⛔ 别改回 30ms 去抖：那在快速滚动期间只画最后一下、
        中间全是空白垫高行）都在 `vsBindScroll()` 里，就在下面第一行挂好。 */
  vsBindScroll();
  VS_TS=[];                              /* ⭐ P5-c：**每页一律先清空**（⛔ 别只在某一条支路里清 ⇒ 会串页） */
  if(!vsOn(VIEW)) return false;          /* ⭐ 逃生阀：`VSCROLL` 的 `off` ＝ **本页不虚拟化**（`TAIL-66` 原意） */
  const ts=vsTableHits(html);
  if(!ts.length) return false;           /* 本页没有带标记的表 ⇒ 交回 `render()` 直写 */
  return startVirtualTables(html, ts, keep);
}
/* ⭐⭐ `TAIL-64` P5-a（2026-09-30）**表级**虚拟滚动 —— "让**每张表自己**滚"（`P5-c` 起是**唯一**那条路）。
   **做法**：
     ① 首帧**按字符串拼**（页里每张 `data-vs` 的 `tbody` 先只放一个**全长垫高**）⇒ 整页仍是**一次**
        `innerHTML` —— ⛔ 不先写全量再改（那会让 1000+ 行被浏览器整批 parse，正是 `TAIL-66` 要避免的卡顿）；
     ② 写完立刻把 `keep` **还给那张表自己的 `.tw`**（此刻文档总高已 = 行数×估算高 ⇒ 还原不会被钳）；
     ③ 再按**真实**容器画首帧（`drawVirtual(实例)`）—— 窗口 / 垫高 / 实测回填**全部复用**同一条路。
   ⚠️ **认领表体时按刚打上的 `data-vs-i` 标记对位，⛔ 不按 `data-vs` 的值查**：`TBL` 的 `key` 缺省是 `'1'`
      ⇒ **一页里多张表同键**（`m14` 实测 5 张全叫 `1`）⇒ 按值查会**把窗口画到别人那张表上**
      （不报错 —— 只是那张表被替成另一个窗口，看起来就是花屏）。
   ⚠️ **带标记但不在 `.tw` 里**（没自带滚动容器）的表**接管不了** ⇒ 行**原样写回**、本轮不虚拟化
      （⛔ 别硬画：窗口是按"它自己的 `.tw`"算的 —— 没有容器 ⇒ 整张表只剩一个垫高行，看起来**表是空的**）。
   ⚠️ 实测（`tools/oneoff/_p5c_survey.py`）：全站 17 页里**有 9 张带标记的表不在 `.tw` 里**
      （`home`/`m02`/`m07` 的 `kinds`/`m10`/`m14` 五张）—— 它们今天都在阈值以下，所以谁也没发现。 */
function startVirtualTables(html, hits, keep){
  const insts=[];
  let out=html;
  /* 从后往前替换（⛔ 免得位移把前面的下标全打乱）。 */
  for(let i=hits.length-1;i>=0;i--){
    const sp=splitRows(hits[i][0]);
    if(!sp || sp.rows.length < vsMin(VIEW)) continue;      /* 这张表行数不够 ⇒ **它不动**，其余照常 */
    const open=/<tbody\b[^>]*>/.exec(sp.pre);
    /* ⛔ 连 `tbody` 开标签都找不到 ⇒ **这张表不动**（别冒险把行换成垫高：认不回它 = 一张空表）。 */
    if(!open) continue;
    const key=(hits[i][0].match(/\bdata-vs="([^"]*)"/)||[,'1'])[1];
    const inst={view:VIEW, key:key, hit:i, pre:sp.pre, post:sp.post, rows:sp.rows,
                h:new Array(sp.rows.length).fill(0),
                colN:((sp.rows[0].match(/<td\b/gi)||[]).length || 8),
                base:0, t:0, raf:0, pending:false, a:-1, b:-1, tb:null, tw:null};
    /* ⭐ 给这一张 `tbody` 打一个**唯一**标记（`hit` = 这块在页里的序号）—— 写完按它对位认领。 */
    const at=open.index + open[0].length - 1;
    const pre=sp.pre.slice(0, at) + ' data-vs-i="'+i+'"' + sp.pre.slice(at);
    out = out.slice(0,hits[i].index) + pre + vsPad(sp.rows.length*EH, inst.colN) + sp.post
        + out.slice(hits[i].index + hits[i][0].length);
    insts.unshift(inst);
  }
  if(!insts.length) return false;                          /* 一张都不够行数 ⇒ 交回 `render()` 直写 */
  $('#view').innerHTML=out;
  runBind(VIEW);
  const live=[];
  insts.forEach(inst=>{
    inst.tb=$('#view').querySelector('tbody[data-vs-i="'+inst.hit+'"]');
    inst.tw=(inst.tb && inst.tb.closest) ? inst.tb.closest('.tw') : null;
    if(!inst.tb || !inst.tw){                              /* ⭐ 接管不了 ⇒ 行原样写回（见上面那条注记） */
      if(inst.tb) inst.tb.innerHTML=inst.pre+inst.rows.join('')+inst.post;
      return;
    }
    inst.tw.scrollTop=keep;                                /* ⭐ 记/还**这张表自己的** `.tw`（⛔ 还错对象不报错，只会悄悄跳顶） */
    live.push(inst);
  });
  VS_TS=live;
  /* ⭐ 首帧：按**真实**容器画（`force` = 此刻不适用焦点护栏 —— 表体还没行，推迟会把表画成空的）。 */
  live.forEach(inst=>{ inst.force=true; drawVirtual(inst); inst.force=false; });
  return true;
}
/* ⭐⭐ 虚拟滚动**重写**（`TAIL-94` · 2026-09-25）：**单一渲染路径 ＋ 文档总高恒定 ＋ 滚动中零写入**。
   前六次尝试全部回滚换来的三条结论（⛔ 别再犯）：
   ① **滚动重画里绝不动 `#view`** —— 那会把真容器 `.tw` 一起换掉 ⇒ 打断滚轮手势、`scrollTop` 归零；
      而"程序化改 scrollTop 能动"的假象骗过两次自检（见 `ops/README.md` 两条纪律）。
      ⚠️ `#view` 那句整页写在**首帧**（`render()` / `startVirtualTables` 拼接那一次）是允许的 ——
         区别在"**用户已经开始滚之后**还改不改它"。
   ② **不在滚动中写 `scrollTop`** —— 锚定回拉那种"写一下修正"会顶掉用户这一格的滚轮量
      ⇒ 真机表现 =「往下能滚、**往上回不来**」（第 4 次尝试就是这么废的）。
   ③ ⇒ 只用 `tbody.innerHTML` 换**窗口行**（容器 / 表头 / `.tw` 一个字节都不动），
      并让**文档总高恒为 `n*EH`**：下垫高吸收"真高 − 估算"的差量；**贴底时改由上垫高吸收**
      —— 因为最后一行**必须是合计行**、⛔ 不能是空垫高行（真机自检抓过）。
   ④ 于是窗口 = `f(scrollTop)` 的**纯函数**：无反馈环、无累积漂移、上下双向对称。
   ⭐ `TAIL-64` P5-c（2026-09-30）：本函数**只收一个表实例** —— 页级那条路已删，原先"整页写窗口"那个
      `first` 分支（连同壳里那个整页实例 `VS`）一起没了。⛔ 别再长出第二条：**一条路一份口径**。 */
function drawVirtual(inst){
  /* ⚠️ 读的必须是**真容器** ＝ **这张表自己的 `.tw`** —— 读 `.view` 会恒得 `st≈0` ⇒ 窗口永不推进。
     ⛔ 没有自带滚动容器的表**本来就接管不了**（认领时已挡掉，见 `startVirtualTables`）⇒ 这里直接返回。 */
  const sc=inst&&inst.tw; if(!sc) return;
  /* ⭐⭐ 焦点护栏（`TAIL-66`）：滚动重画时若焦点在**表内**编辑控件里 ⇒ **推迟**（⛔ 别改成"照画"：
     那会让用户"输到一半滚一下就没了"，而且**不报错** —— 最坏的一类缺陷）。
     ⚠️ `inst.force` = **首帧**：那一刻表体还是空的（只有全长垫高）⇒ 被推迟就会画成一张空表。 */
  if(!inst.force && vsEditing()){ inst.pending=true; return; }
  inst.pending=false;
  const n=inst.rows.length, st=sc.scrollTop, vh=sc.clientHeight;
  let a,b;
  /* ⭐ 底部钳制（虚拟列表标配）：贴底 ⇒ 窗口**必须**收在最后一行（合计行永远如约出现）。 */
  if(st + vh >= n*EH - 2){ b=n; a=Math.max(0, n-VS_WIN-VS_OVER); }
  else { a=Math.max(0, Math.floor(st/EH)-VS_OVER); b=Math.min(n, a+VS_WIN+VS_OVER); }
  /* ⭐ 窗口没变 ⇒ 一个字节都别动（滚动中反复重写会打断手势）。 */
  if(a===inst.a && b===inst.b) return;
  const topH0=a*EH, botH0=(n-b)*EH, winRows=inst.rows.slice(a,b);
  const SP=h=>vsPad(h, inst.colN);              /* ⭐ P5-a：垫高行**抽成共用出口**（形态一字未改） */
  /* ⭐⭐ 滚动重画：**只换 tbody 的行** —— `.tw` / 表头 / `#view` 都不动 ⇒ 手势不被打断、`scrollTop` 不用还。 */
  const tb=(inst.tb && document.contains(inst.tb)) ? inst.tb : sc.querySelector('tbody');
  if(!tb) return;
  inst.tb=tb;
  tb.innerHTML = SP(topH0) + winRows.join('') + SP(botH0);
  /* 红线③：窗口行**实测回填**（行高 27~91px 不等高）＋ 差量吸收 ⇒ 文档总高恒为 `n*EH`。 */
  const trs=inst.tb?inst.tb.children:null;
  if(trs && trs.length){
    const hasTop=!!(trs[0] && trs[0].classList && trs[0].classList.contains('vsp'));
    let H=0;
    for(let i=hasTop?1:0; i<trs.length; i++){
      const r=trs[i];
      if(r.classList && r.classList.contains('vsp')) continue;
      const hh=r.getBoundingClientRect().height;
      const gi=a+i-(hasTop?1:0);
      if(gi>=0 && gi<n) inst.h[gi]=+hh.toFixed(1);
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
    if(r0) inst.base=r0.getBoundingClientRect().top - sc.getBoundingClientRect().top + sc.scrollTop - topH0;
  }
  inst.a=a; inst.b=b;
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


