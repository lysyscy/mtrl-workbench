/* shell/pages-a.js —— 壳的**独立件**（`P2-a` 拆件 · 2026-09-28 · 台账 `TAIL-164`）：`MOD-03` / `MOD-04` / `MOD-05` 的页辅助 ＋ `BIND` 注入。
 *
 * ⭐ **为什么单开一件**：付款域三页的筛选、草稿行、台账取数是**同一批人对同一批数据**的活 ⇒ 单开一件。
 *    `index.html` 原来一件套 4000 行（CSS ＋ HTML ＋ 内联脚本混装）⇒ 改一处要翻三个区
 *    （本会话两次白屏的同一个根）。本件是「**只拆非切片**」那一批里的一件。
 * ⛔ **本件不许碰**：任何 `V.<原型页>` 切片（它们**留在 `index.html`** —— 计划 §23 的口径，
 *    `ui_parity` 的 `U1` 逐行比它）· 口径判定（判定全在后端）· 界面文案的主人。
 * ⚠️ **加载顺序**：`index.html` 的 `<script src>` 顺序即真源 —— 本件排在 `actions.js` **之前**
 *    （`actions.js` / `core.js` 里有些表**加载期就求值**到本件的常量）。⛔ 别调顺序。
 * ⚠️ 本件的代码是**原样搬出**（逐字未改，含注释）；来历与搬法见计划 §15 `TAIL-164`。 */

BIND.m03=()=>{ const box=$('#pickAllBox'); if(!box) return;
  /* ⚠️ 全选框的「可见候选」必须与 `pickAll` 走**同一个出口** —— 否则撤单行留在 `vis` 里、
     却永远勾不上 ⇒ 全选框会永久卡在"半选"态（勾满了还是个半选框）。 */
  const vis=ntHit(fNt).filter(ntSelectable).map(n=>n.id), hit=vis.filter(i=>pickSet.has(i)).length;
  box.checked = vis.length>0 && hit===vis.length;
  box.indeterminate = hit>0 && hit<vis.length; };

/* =====================================================================
   5. MOD-04 付款计划
   ===================================================================== */
/* 筛选 / 多选状态（2026-09-12 新增）。
   ⚠️ 复位一律【原地改字段 / 清空】，不要整体重新赋值 —— 外部（自检）持有的是对象引用。 */
let plf={ym:bjMonth(),projs:[],review:'全部'};
let plPick=new Set();
/* 展开态在 `PJ_OPEN`（key='plPj'） */
let plImportM=bjMonth();          /* 「导入付款计划」弹窗里选定的年月（导入后本批数据全归该月） */
/* ---------- 「按付款计划勾选」的月份（⭐ 2026-10-08 用户裁定：月份可选、不限点击时间） ----------
   原口径是"每月 10 号生效 → 月末才可点、月份定死当月"（2026-09-12 定案）。现在**两点都取消**：
     · **不再按日期禁用** —— 那条窗口只是制度上的习惯（制度本身也只约束人、不拦系统，§4.3.7
       「系统不做任何拦截或标记」），做成**按钮置灰**反而挡住正常补勾（用户 2026-10-08 报障）。
     · **月份改为可选** —— `planYm` 是这一个出口，勾哪个月由人挑（候选 = 库里真有的计划月份 ＋ 当月）。
   ⚠️ 判据同源：按钮可用性 = `mod04_plan/plan_ui.window_button`（后端唯一出口，**恒 True**）。
      ⛔ 壳里**不再写第二份**"今天几号够不够 10 号"的判定（原先的 `plWin()` 已删）。 */
let planYm=bjMonth();     /* 「按付款计划勾选」要勾的月份（用户挑的那个月） */
let planSel='';           /* 选月份弹窗里的**草稿**选择（同 `supSel` / `jcLinkSel` 的约定：改选择不重绘，提交时读） */
/* ---------- 付款计划「审查引擎」：拿计划表与 i8 付款通知书**逐笔比对**（取数口径见 §4.3.4） ----------
   ① 比对键 = 单据号；② 「该流程金额」↔ 通知书「审批金额」；③ 「本月预付款金额」↔ 未付金额（审批 − 已付）；
   ④ 同月同一单据号出现 ≥2 次 ⇒ 重复上报（**跨月不算**；**空单据号不参与判重**）。 */
/* ⭐⭐ **审查结果的唯一出口 = 后端**（D18：判定与落库一律后端）。
   原型原先在**前端实时派生**（查 `NO` + 重复检测）；接线后改为**读后端算好的 `result`**
   （`mod04_plan/domain.py::audit_rows` —— 与判据同一份纯函数）⇒ 前端**不再有第二份判定**。
   ⚠️ 保留签名 `(p, all)`：`V.m04` 里各处调用**一行都不用改**（第 2 个参数留着不读）。 */
const plRev=(p)=>String((p&&p.result)||'').trim()||'—';
/* 按单据号命中的 i8 通知书（供「已付款金额 / 剩余付款金额」两列取数）；查不到 → null */
const plHit=p=>{ const c=String(p.docNo||'').trim(); return c?(NO.find(x=>x.code===c)||null):null; };
/* 审查结果的**筛选归并**（2026-09-12）：判定仍是 §4.3.4 的 6 种，筛选下拉只给
   「完全匹配 / 未匹配」两档 —— 「未匹配」= 除「完全匹配」以外的全部判定。 */
const revIs=(rv,f)=> f==='全部' || (f==='未匹配' ? rv!=='完全匹配' : rv===f);
/* ---------- 付款计划的「项目」列 = 用户导入前手工填的**展示名或仓库名**（2026-09-12 用户口径） ----------
   ⚠️ **不是全名** —— 用户不会填全名：太长，而且全名里可能带「小微」字样（壳与具体小微共用全名）。
   ⇒ 系统按 `disp`（展示名）或 `name`（仓库名）**唯一匹配**项目档案：
       命中 1 条 → 正常；命中 0 条 → 「未匹配」（提示核对项目名或先建档）；命中多条 → 「重名」（需人工核对）。
   ⇒ 壳没有展示名也没有仓库名，所以**不会**再出现「壳下 N 个小微 · 待指定」这种提示（那是全名反查的产物）。 */
const plProjHit=v=>{ const s=String(v==null?'':v).trim(); if(!s) return [];
  return PJs.filter(p=>p.type!=='shell'&&(p.name===s||p.disp===s)); };
const plProjOne=v=>{ const h=plProjHit(v); return h.length===1?h[0]:null; };
/* 「项目」筛选的归并键 = 匹配到的项目**展示名** —— 同项目无论填展示名还是仓库名都归到一处；
   匹配不到的填法不产生归并键（只在「全部项目」下可见）。 */
const plProjKey=v=>{ const p=plProjOne(v); return pjKey(p); };   /* 筛选键 = **仓库名**（§2.7.4） */
/* 候选项目 = 计划行里**能匹配到**的项目（**键 = 仓库名**，去重）；**含归档**，归档靠后并标注
   （2026-09-13 用户口径：所有项目候选都含归档；原「只列在建」已作废。与付款通知书页同口径） */
const PL_PROJ_LIST=()=>pjKeysOfRows(uniqBy(PLs,p=>plProjOne(p.proj)));
/* 「项目」列的展示：匹配到 → 显示规范展示名（悬停只给状态）；未匹配 / 重名 → 明示 */
const plProjCell=v=>{ const h=plProjHit(v), raw=esc(String(v==null?'':v))||'—';
  if(h.length===1){ const p=h[0];
    return `<span class="fc" title="${esc(p.status)}">${esc(pjDisp(p))}</span>`; }
  if(!h.length) return `<span class="fc">${raw}</span> <span class="tag t-dg" title="档案里没有这个展示名 / 仓库名 —— 请核对项目名，或先到「项目档案」建档">未匹配</span>`;
  return `<span class="fc">${raw}</span> <span class="tag t-wn" title="有 ${h.length} 条档案的展示名 / 仓库名相同，需人工核对">重名 ${h.length} 条</span>`; };
/* 当前筛选结果 —— 页面、全选框回显、多选删除共用同一份口径（审查结果按**实时派生值**筛） */
const plVisible=()=>PLs.filter(p=>tmIn(plf.ym,p.ym)&&(!plf.projs.length||plf.projs.includes(plProjKey(p.proj)))&&revIs(plRev(p,PLs),plf.review));
/* 勾选集合裁剪到当前可见范围（筛选变化后调用，避免删掉看不见的行） */
const prunePlPick=()=>{ const vis=new Set(plVisible().map(p=>p.id)); [...plPick].forEach(id=>{ if(!vis.has(id)) plPick.delete(id); }); };
/* 与 MOD-03 / MOD-06 共用同一个 projPanel 实现（同一份实现、多个 cfg）——
   候选键一律是**仓库名**（§2.7.4），meta 一律 `PROJ_META_KEY`（仓库名 → 展示名） */
const plPjPanel=()=>projPanel({list:PL_PROJ_LIST,selected:()=>plf.projs,allAct:'plPjAll',noneAct:'plPjNone',pickAct:'plPjPick',meta:PROJ_META_KEY});
/* ---------- 付款计划「手动行」= **表内增行模式**（§4.3.3.1 · 2026-09-16 用户口述新增 · 用户同日追认细节 6 项）----------
   形态**照抄 MOD-03 的既有约定**（`ntRowAdd` / `ntRowSet` / `ntRowSave` / `ntRowCancel`）：
   **不用弹窗**，草稿行插在**表尾**；「编辑」= 该行**原地变草稿行**（不新增行）。
   ⭐ 手动行与导入行**同住一表、走同一条审查链路** —— 判定一律 `plRev()` 按行**实时派生、不看来源**
      （6 种判定 / 同月同单据号判重 / 两档筛选 / KPI 计数 / 表内合计，全都不因"来源是手动"被跳过）。
   ⚠️ **导入不清理它**（§9.5：导入只清并重写自动行）；**只有手动行可编辑**；**删除所有行都有**（§4.3.6 —— 与
      付款通知书「i8 抓取行永不删」**不同，不得照抄**）。 */
const PL_NEW_ID='@new';                    /* 哨兵 id：新增中的草稿行（**不是** `PLs` 里的行）
                                              渲染时插在**表尾**（`applySorts` 会把它钉住、不参与排序；不进合计 / 不进勾选）
                                              ⚠️ 这句注释必须留在**模板字面量之外** —— 写在 `${}` 里会连同注释一起渲染出去 */
let plRowEditId='';                        /* ''=未在编辑；'@new'=新增中；<id>=**原地编辑**该手动行 */
/* ⭐ 落库中（**挡重入** · 守则 §5.5）：连点两次「保存」= 两次 `POST /api/m04/plans`
   ⇒ **落两行完全相同的计划行**；⚠️ 后端**不会挡** —— 同月完全相同的行是**本业务的合法状态**
   （§4.3.3：重复由「重复上报」提示，不靠自动去重掩盖）⇒ 这一道只能由界面挡。
   与 `IMP.busy`（`TAIL-108`）同款。 */
let plSaving=false;
let plD={};                                /* 草稿层（键与 `PL_COLS` 同名 —— "改一格不冲掉别的格"） */
const plRowOn=()=>plRowEditId!=='';        /* 是否处于增行态（渲染草稿行的唯一判据） */
const plBlank=()=>({ym:plf.ym, proj:'', docNo:'', flowAmt:'', monthAmt:'', date:'', method:'现汇', remark:''});
/* 生成 k 个**连续可用**的编号（**从「当前最大编号 + 1」起算**，**不看数组长度**）。
   ⚠️ **为什么不能数长度**：原实现用 `PLs.length+1` ⇒ **删过行之后再导入就会与既有 id 撞号**
      ⇒ `PLs.find(id)` 会**命中错行**（删除 / 编辑 / 勾选 / 再次匹配 / 点选**全按 id 定位**）。2026-09-16 修。
   ⚠️ **导入与手动新增共用这一个出口**（两个入口都别自己拼编号）。 */
const plNextIds=(pfx,k=1)=>{ let mx=0;
  PLs.forEach(p=>{ const s=String(p.id||''); if(!s.startsWith(pfx)) return;
    const n=Number(s.slice(pfx.length)); if(Number.isFinite(n)) mx=Math.max(mx,n); });
  return Array.from({length:k},(_,i)=>pfx+String(mx+1+i).padStart(2,'0')); };
/* 草稿行的「项目」下拉：候选 = **全部已建档项目（含归档、不含壳）**，键 = 仓库名（§2.7.4），
   落库记**项目 id**（§9.8-5 按 id 不按名）；归档标注走共性出口 `pjArcMark(p,true)`（纯文本档）。
   ⚠️ 这里**有意不用共用面板 `projPanel`** —— 草稿行在 `.tw`（滚动容器）**内部**，浮层面板会被裁掉
      （与「弹窗内 3 个项目下拉」同族的既有例外，已在设计规则里登记）。 */
const plProjOptions=cur=>{ const list=PL_PROJ_LIST();
  const opts=list.map(k=>{ const p=pjRowOf(k), arc=pjArcMark(p,true);
    return `<option value="${esc(k)}"${String(cur||'')===String(k)?' selected':''}>${esc(pjDisp(p))}${arc?`（${esc(arc)}）`:''}</option>`; }).join('');
  return `<option value=""${cur?'':' selected'}>（请选择项目）</option>${opts}`; };
/* 草稿行（**列对齐 15 格** —— 逐列与 `PL_THEAD` 对齐；值取草稿层，不是 `PLs` 的行）
   ⚠️ 草稿行**不带 `data-id``：合计行的断言按 `data-id` 收集行做独立复算 ⇒ 带了会污染。 */
const plDraftRow=()=>{ const d=plD, isNew=(plRowEditId===PL_NEW_ID);
  return `<tr class="draftrow">
    <td class="ctr fl"></td>
    <td class="fc">${isNew
      ? '<span class="tag t-in" title="尚未保存 —— 填完点本行右侧「保存」写入；「取消」丢弃（草稿不写入）">手动 · 新增</span>'
      : '<span class="tag t-in" title="正在原地编辑这条手动行 —— 点「保存」写入、点「取消」保持原样（不新增行）">手动 · 编辑</span>'}</td>
    <td><input class="inp now" type="month" style="min-width:104px" data-act="plRowSet" data-k="ym" value="${esc(d.ym||'')}" title="年月 = 归月依据（必填 · 月度形态）；保存后按它归月归档"></td>
    <td><select class="inp" style="min-width:180px" data-act="plRowSet" data-k="proj" title="归属项目（已建档项目 · 含归档、不含壳）—— 写入记项目 id">${plProjOptions(d.proj)}</select></td>
    <td><input class="inp plain" style="min-width:134px" data-act="plRowSet" data-k="docNo" value="${esc(d.docNo||'')}" placeholder="可空" title="单据号允许为空（与导入行同）；保存后按 §4.3.4 实时出审查结果"></td>
    <td class="num"><input class="inp num" style="width:96px" data-act="plRowSet" data-k="flowAmt" value="${esc(d.flowAmt||'0.00')}" title="该流程金额（比对 i8 通知书的审批金额）"></td>
    <td class="num"><span class="mut" title="保存后按命中的 i8 通知书派生（= 该单据已付金额）；单据号未命中 → 显示「—」">—</span></td>
    <td class="num"><span class="mut" title="同上（= 审批金额 − 已付金额 = 未付金额）">—</span></td>
    <td class="num"><input class="inp num" style="width:96px" data-act="plRowSet" data-k="monthAmt" value="${esc(d.monthAmt||'0.00')}" title="本月预付款金额（比对未付金额：超过则判「超过未付」）"></td>
    <td><input class="inp now" type="date" style="min-width:112px" data-act="plRowSet" data-k="date" value="${esc(d.date||'')}"></td>
    <td><select class="inp" data-act="plRowSet" data-k="method">${optsOf(enumVals('payMethod'),d.method||'现汇')}</select></td>
    <td><input class="inp" style="min-width:128px" data-act="plRowSet" data-k="remark" value="${esc(d.remark||'')}" placeholder="—"></td>
    <td><span class="mut sm" title="保存后按 §4.3.4 实时判定 —— 手动行与导入行走同一条链路，不因来源被跳过">保存后判定</span></td>
    <td class="ctr"><span class="mut sm">—</span></td>
    <td class="ctr now"><button class="btn sm pri" data-act="plRowSave"${plSaving?' disabled':''} title="${plSaving?'正在保存 —— 请勿重复点击（连点会落两行相同的计划行）':'校验通过后写入（写入后与导入行同样参与审查）'}">${plSaving?'保存中…':'保存'}</button> <button class="btn sm" data-act="plRowCancel"${plSaving?' disabled':''} title="丢弃这一行草稿（不写入）">取消</button></td>
  </tr>`; };
BIND.m04=()=>{ const box=$('#plAllBox'); if(!box) return;
  const ids=plVisible().map(p=>p.id);
  const hit=ids.filter(i=>plPick.has(i)).length;
  box.checked = ids.length>0 && hit===ids.length;
  box.indeterminate = hit>0 && hit<ids.length; };
/* 全选框状态回显（与 MOD-03 / MOD-04 同款逻辑：全选 / 半选）—— `MOD-11` 集采台账
   ⚠️ 2026-09-13 P6 走查实测：这张表**一直没有 BIND** ⇒ 表头那个「全选」框**永远不反射状态**
      （全勾满了也还是空框、部分勾选也不显半选），而 `R10`② 明确要求"全选支持全选 / 半选回显"。 */
BIND.m11=()=>{ const box=$('#jcAllBox'); if(!box) return;
  const vis=jcVisible();
  const hit=vis.filter(j=>jcPick.has(j.id)).length;
  box.checked = vis.length>0 && hit===vis.length;
  box.indeterminate = hit>0 && hit<vis.length; };

/* =====================================================================
   6. MOD-05 付款流水与欠款统计
   ===================================================================== */
/* =====================================================================
   6.1 逐月欠款台账（按项目 · 按月一行）—— 2026-09-12 用户口径
   =====================================================================
   用户在用的 Excel 台账「〈项目〉辅材欠款」原样落地：第 1 行 = **期初占位行**（截止 YYYY 年 M 月底），
   其后**每月 1 行**（从期初的**次月**起；**空月也出行**、三列记 0）。
   列 = 序号 / 月份 / 其他支出金额 / 付款 / 欠款 / 备注。

   取数（欠款口径见 §4.5.1）：
     · 其他支出金额   辅材：Σ 该月 · 该项目 · 分类=辅材 的**统计结算金额**（`NT.ss`）
                      机械：**派生只读** = 该月「外租零租含税 ＋ 外租包月含税」（`machExtRent`）
                      —— 2026-09-13 起**不再手填**（源头 = 过程资料机械 6 列，`MACHM` 已删除），
                         **只改 `ledSettle` 那一行**即可换口径
     · 付款           辅材 / 机械**同构**：Σ 该月 · 该项目 · 同分类 的**统计付款金额**（`NT.sp`）
     · 欠款           **派生** = 其他支出金额 − 付款（**不存字段**）；注意这是**当月新增欠款**，**不是累计**
     · 备注           人工录入（`LEDNOTE`，键 = 口径|项目键|月）
   归月依据 = 通知书的**单据日期**（`NT.date` 的 YYYY-MM）—— 与抓取 / 筛选同一条时间轴。
   项目归集 = **归属** → **仓库名**（`ntProjKey`，§2.7.4），与「按项目看欠款」同口径。
   期初行   = 该项目在期初占位行里那一条（其余额 = 人工录入；**按分类取**，故两个口径各带各的）。
   ⭐ 2026-09-12 用户口径（第 2 版）：台账**从中间劈开** —— **左 = 辅材、右 = 机械**（两张卡、同一行）；
      **不再有「辅材 / 机械」切换按钮**；两侧**共用同一个「项目」选择器**（同一项目左右对照看），
      各自带「＋ 录入期初占位行 / 导出 Excel」（录入弹窗的「分类」按所在侧预选，仍可改）。 */
let ledProj='';                            /* 台账当前选中的项目（**仓库名** = 候选键，§2.7.4）—— **两侧共用**；显示走 `pjLabel` */
let lgCut=bjMonth(-1);                     /* 「录入期初占位行」里选的**截止年月**（＝台账起点，台账从其次月起） */
let lgCat='辅材';                          /* 「录入期初占位行」里选的**分类**（辅材 / 机械） */
/* ⭐ 期初占位行的**草稿层**（2026-09-13 用户要求）：展开区里改「分类」/ 选「截止年月」都会重绘，
   必须保住已填的金额与备注 —— 否则重绘一次就把刚填的数冲成 0.00。
   写入 = 三个表单动作（lgS / lgP / lgR，走 `change` 委托）；读取 = 展开区渲染；**保存 / 取消后复位**。
   ⭐ 2026-09-13 增行模式（用户拍板 C-1/C-7）：**「录入期初占位行」弹窗取消** ⇒ 改为**栏内展开区**，
      且渲染在 `.tw` **之外**（表格上方的独立条带）—— 这样其内的「项目」共用面板不会被滚动容器裁掉。 */
const LG_R_DEF='系统上线前已发生，无付款通知书';
let lgD={s:'0.00',p:'0.00',r:LG_R_DEF};
let lgPjName='';                           /* 展开区里选的**项目键（仓库名）**（打开时默认＝台账当前项目） */
let lgOn=false;                            /* 增行态开关：展开区是否打开（取代原弹窗的"是否开着"） */
/* 展开态在 `PJ_OPEN`（key='lgPj'） */                        /* 展开区里「项目」共用面板是否展开（真实浮层 —— 在 .tw 之外，不会被裁） */
const LEDNOTE={};                          /* { '口径|项目键|月': 文本 } —— 逐月台账备注（手填；不在 §9.3 留痕范围） */
/* 通知书行的**项目键** = 归属档案行的**仓库名**（§2.7.4）；无归属 / 壳未判定 → ''（落不到任何项目上）。
   `ntProjName` 只在**给人看**时用（展示名）。 */
const ntProjKey=n=>pjKey(ownOf(n));
const ntProjName=n=>{ const k=ntProjKey(n); return k?pjLabel(k):(isShellFull(n.proj)?'（待指定归属）':n.proj); };
const ntYm=n=>String(n.date||'').slice(0,7);
const debtSourceTip=sc=>sc==='集采'
  ? '本项目集采欠款 = 集采台账中纳入台账合同的结算金额−付款金额之和；结算取对应发票子表，付款取付款子表；不计不纳入合同，不按日期截断'
  : `本项目${sc}欠款 = ${sc==='辅材'?'付款通知书辅材统计结算金额之和':'过程资料全部已存月份外租零租含税＋外租包月含税'} − 付款通知书同分类统计付款金额之和 ＋ 本分类期初结算−期初付款；通知书剔除行不计，i8撤单有付款或集采关联仍计入，不按月份截断`;
/* 期初占位行存的是**项目全名** → 归一到**仓库名**（候选键，§2.7.4），才能与台账的项目键对上 */
const lgProjKeyOf=v=>pjKey(pjRowOf(v));
const nextYm=m=>{ const [y,mm]=String(m).split('-').map(Number); const t=new Date(y,mm,1);
  return ymOf(t); };
const prevYm=m=>{ const [y,mm]=String(m).split('-').map(Number); const t=new Date(y,mm-2,1);
  return ymOf(t); };
/* 录入默认项目沿用台账；已有手动记录保留其截止月，新记录默认历史段2025-11。 */
/* 期初占位行的项目候选（与该弹窗下拉**同一集合**）：**含归档**、归档靠后（2026-09-13 用户口径）。
   候选键 = **仓库名**（`pjRowsWithKey` 已把壳剔除 —— 壳没有仓库名） */
const lgPjList=()=>pjRowsWithKey(pjNoShell());
const lgDefPjName=()=>{ const L=lgPjList(), cur=ledCur();
  const hit=L.find(p=>pjKey(p)===cur||pjDisp(p)===cur);
  return (hit||L[0]||{}).name||''; };
const lgCutFor=(v,cat)=>{
  const key=pjKey(pjRowOf(v));
  const existing=LGs.find(l=>l.cat===cat&&lgProjKeyOf(l.proj)===key);
  return existing?existing.cutoff:'2025-11'; };
const ledCutLabel=m=>/^\d{4}-\d{2}$/.test(String(m||''))?`截止 ${m.slice(0,4)} 年 ${Number(m.slice(5,7))} 月底`:'截止时间未填';
/* 台账可选项目 = 该口径下**有数据**的项目（通知书；机械结算源未接线 ⇒ 暂不计）+ **该口径的**期初占位行。**键 = 仓库名**
   ⚠️ 原第 2 行按**演示** `MACH6` 的键补候选 —— 那是演示数据 ⇒ 会往选择器里塞**幻影项目**（真库里没有的仓库名）。
      机械结算源（过程资料机械 6 列）接线时，这里应改成读**后端的机械结算口**。 */
const LED_PROJS=sc=>{ const s=new Set();
  NO.filter(n=>ntLive(n)&&n.cat===sc).forEach(n=>s.add(ntProjKey(n)));
  LGs.filter(l=>l.cat===sc).forEach(l=>s.add(lgProjKeyOf(l.proj)));
  s.delete('');                                        /* 未归属的行落不到任何项目上（真系统里不会有） */
  return [...s].sort(); };
/* 该月的「其他支出金额」 */
const ledSettle=(sc,proj,ym)=> sc==='辅材'
  ? N2(NO.filter(n=>ntLive(n)&&n.cat==='辅材'&&ntYm(n)===ym&&ntProjKey(n)===proj).reduce((a,n)=>a+n.ss,0))
  : N2(machExtRent(proj,ym));   /* ⭐ 换口径只改这一行：机械 = 机械费结算（外租含税两列，**派生只读**） */
/* 该月的「付款」= Σ 同月 · 同项目 · 同分类 的统计付款金额 */
const ledPay=(sc,proj,ym)=>N2(NO.filter(n=>ntLive(n)&&n.cat===sc&&ntYm(n)===ym&&ntProjKey(n)===proj).reduce((a,n)=>a+n.sp,0));
/* ⭐ 已接后端：期初占位行 / 逐月台账行**一律读 `/api/m05/ledger`**（§4.5.4 的唯一出口）。
   ⛔ 原实现按 `LGs` / `NO` / `MACH6` 现算月份区间并逐月求值 —— 第二份口径（机械还读演示数据）。 */
const ledOpen=(sc,proj)=>{ const side=m05Side(sc); if(!side) return null;
  const r=(side.rows||[]).find(x=>x.is_opening); if(!r) return null;
  return { id:side.opening_id, cat:side.label, cutoff:r.month, settle:numOr0(r.other_expense),
           paid:numOr0(r.payment), remark:r.remark||'' }; };
/* 两侧共用候选：数据项目与已建档非壳项目；未建仓-N原键保留，无数据也能查看/导出。 */
const ledProjs=()=>pjSort(uniqBy([...LED_PROJS('辅材'),...LED_PROJS('机械'),
  ...pjNoShell().map(p=>p.name)],v=>v));
/* 当前生效的台账项目（选的这个项目若不在候选里，回落到第一个） */
const ledCur=()=>{ const l=ledProjs(); return l.includes(ledProj)?ledProj:(l[0]||''); };
/* ⭐ 台账「项目」选择器 = **共用面板（单选）**（2026-09-13 用户口径「A 改」）——
   候选 = `ledProjs()`（该分类下有数据 / 有期初行的项目，**键 = 仓库名**）；卡内左右两栏共用这一个值。
   ⚠️ 它落在**卡片头**、**不在滚动容器里** ⇒ 浮层面板不会被裁（这正是它可以用面板、
      而**弹窗内**那 3 处只能用原生 `<select>` 的原因）。 */
/* 展开态在 `PJ_OPEN`（key='ledPj'） */
/* —— 「导出逐月欠款台账」的展开区（2026-09-13 用户口径）——
   原先**左右两栏各一个**「导出 Excel」（各导一侧）；现改为**卡头一个入口**：
   点开一条**渲染在 `.tw` 之外**的展开区 → 用**共用面板多选项目**（默认 = 页面当前所选项目）
   → 导出形态 = **每个项目一个工作簿**，工作簿里 **3 个工作表：辅材欠款 / 机械欠款 / 特殊费用月报表**；
   选 ≥2 个项目 ⇒ 打成一个 zip。
   ⚠️ **特殊费用月报表不再单独设导出按钮** —— 它作为台账工作簿的第 3 个工作表随台账一起导出。
   ⚠️ 面板必须渲染在 `.tw` 之外（浮层才不被滚动容器裁）—— 展开区放在卡内、`<div class="grid2">` **之前**。 */
let ledExpOn=false;          /* 导出展开区是否打开 */
/* 展开态在 `PJ_OPEN`（key='ledExpPj'） */      /* 其中的「项目」多选面板是否展开 */
let ledExpPjs=[];            /* 导出所选项目（**仓库名**数组；空 = 未选 ⇒ 打开时默认取页面当前项目） */
const ledPjPanel=()=>projPanel({list:ledProjs,selected:()=>[ledCur()],pickAct:'ledPjPick',meta:PROJ_META_KEY,single:true});
/* 导出用的「项目」面板 —— **多选**（不走 `single`；面板自带「全选 / 清空」）。候选 = 台账候选（`ledProjs`，**键 = 仓库名**） */
const ledExpPjPanel=()=>projPanel({list:ledProjs,selected:()=>ledExpPjs,allAct:'ledExpPjAll',noneAct:'ledExpPjNone',pickAct:'ledExpPjPick',meta:PROJ_META_KEY});
/* 导出展开区（渲染在 `.tw` **之外** ⇒ 其内的浮层面板不会被裁） */
const ledExpStrip=()=>`${FBAR({cls:'strip',body:`
      <div class="fi"><span class="pill" style="margin:0" title="导出 = 每个项目一个工作簿，工作簿里 3 个工作表：辅材欠款 / 机械欠款 / 特殊费用月报表">① 逐月台账</span></div>
      <div class="fi pjwrap" style="position:relative"><label>项目（可多选）</label>
        ${PJB({act:'ledExpPjToggle',w:186,label:`${ledExpPjs.length?`已选 ${ledExpPjs.length} 个项目`:'请选择项目'}`})}
        ${pjIsOpen('ledExpPj')?ledExpPjPanel():''}</div>
      <div class="fi" style="margin-left:auto;display:flex;gap:calc(6px * var(--fscale))">
        <button class="btn sm pri" data-act="ledExpOk" ${ledExpPjs.length?'':'disabled'} title="${ledExpPjs.length?'按所选项目导出（每项目一个工作簿 · 3 个工作表）':'请先选项目'}">导出台账</button>
        <button class="btn sm" data-act="ledExpCancel">取消</button></div>
      <div class="mut sm" style="flex-basis:100%">导出形态：<b>每个项目一个工作簿</b>（工作表 = 辅材欠款 / 机械欠款 / 特殊费用月报表）；选 <b>2 个以上</b> ⇒ 打成一个 <b>zip</b>。文件名含项目展示名与当前年月（§7.1）。<br>每次打开<b>默认选中本页当前项目</b>（可直接改）；⚠️ 这里的项目只决定<b>导出哪些</b>，⛔ 不改变屏幕上看的是哪个项目。</div>
      <!-- ⭐ 2026-09-28（TAIL-144）：两个导出收在同一条面板里，各自的项目范围就挨着自己的动作
           ⇒ 不再"点右上那个按钮、再跑到最左边选项目"（用户截图报障原话）。
           ⚠️ 本段原先是 core.js 里那段 DOM 注入（BIND.m05）插到卡头的（TAIL-138）—— 现直接渲染在这里，
           ⛔ 别再注入回卡头（卡头只留一个「导出…」入口，那是用户 2026-09-13 的裁定）。
           ⚠️⚠️ 本注释在「模板字面量的文本区」里 ⇒ 三条禁令：不许反引号（会截断模板串）·不许 Markdown 双星号
           （test_acc_x_exp 按"渲染面"扫那条，实测踩到）·注释别跑出注释边界。 -->
      <div style="flex-basis:100%;display:flex;align-items:center;gap:calc(6px * var(--fscale));flex-wrap:wrap;border-top:1px solid var(--bd);padding-top:calc(8px * var(--fscale))">
        <span class="pill" style="margin:0" title="总欠款汇总 = 每个项目一行：A 序号 · B 项目展示名 · C 集采 · D 辅材 · E 机械（实时口径）">② 总欠款汇总</span>
        <button class="btn sm${DEBTPICK.length?' pri':' gost'}" data-act="debtPick" title="「导出总欠款」包含哪些项目、按什么顺序；空 = 全部项目。⚠️ 与上面①那个项目不是同一个东西（那个是导出台账用的）">选择项目（${DEBTPICK.length?`已选 ${DEBTPICK.length} 项`:'全部'}）</button>
        <button class="btn sm" data-act="debtExpAll" title="每个项目一行 · 行序 = 左边「选择项目」排的（空 = 全部项目）">导出总欠款</button>
      </div>
    `})}`;
/* —— 「录入期初占位行」的**项目**共用面板（单选）—— 2026-09-13 增行模式新增（第 9 个 `projPanel` 调用点）——
   ⭐ 它原来在**弹窗**里只能用原生 `<select>`（弹窗主体是滚动容器、浮层会被裁）；
      弹窗取消后改到**栏内展开区**、且整条展开区渲染在 `.tw` **之外** ⇒ 浮层不会被裁
      ⇒ 于是**可以**用共用面板（与全站约定一致；**"弹窗内 3 处下拉"那条例外随之减少一处**）。
   ⚠️ `lgPjList()` 返回的是**档案行** ⇒ 必须过 `pjKeysOfRows()` 转成**候选键**（§2.7.4；U1 那个坑）。 */
const lgPjPanel=()=>projPanel({list:()=>pjKeysOfRows(lgPjList()),selected:()=>[lgPjName],pickAct:'lgPjPick',meta:PROJ_META_KEY,single:true});
/* 「期初占位行」的**增行展开区**（渲染在表格 `.tw` **之外**的上方条带；只在 `lgCat` 对应的那一栏出现）
   ⚠️ 只在该分类对应的一栏渲染 ⇒ **不会出现重复 id**（`lgCat`/`lgS`/`lgP`/`lgR`）。 */
const lgStrip=()=>`${FBAR({cls:'strip mb6',body:`
      <div class="fi"><span class="pill" style="margin:0" title="只保存手动结算和付款，自动付款独立更新">手动期初</span></div>
      <div class="fi pjwrap" style="position:relative"><label>项目</label>
        ${PJB({act:'lgPjToggle',w:150,label:`${esc(pjLabel(lgPjName))}${pjArcMark(pjRowOf(lgPjName))}`})}
        ${pjIsOpen('lgPj')?lgPjPanel():''}</div>
      <div class="fi"><label>分类</label><select class="inp" style="width:auto" id="lgCat" data-act="lgCat">${['辅材','机械'].map(c=>`<option ${lgCat===c?'selected':''}>${c}</option>`).join('')}</select></div>
      <div class="fi"><label>截止年月</label>${tmBtn('lgCutoff',{scope:'lg',val:lgCut,modes:['月']})}</div>
      <div class="fi"><label>统计结算金额</label><input class="inp num" style="width:118px" id="lgS" data-act="lgS" value="${esc(lgD.s)}"></div>
      <div class="fi"><label>统计付款金额</label><input class="inp num" style="width:118px" id="lgP" data-act="lgP" value="${esc(lgD.p)}"></div>
      <div class="fi"><label>备注</label><input class="inp" style="min-width:160px" id="lgR" data-act="lgR" value="${esc(lgD.r)}"></div>
      <button class="btn pri" data-act="addLgOk" title="写入期初占位行（统计结算 / 统计付款一并计入欠款）">保存</button>
      <button class="btn" data-act="lgCancel" title="丢弃这条期初录入（不入库）">取消</button>
      <span class="pill" style="margin-left:auto">${esc(ledCutLabel(lgCut))} ｜ 保存手动金额</span>
      <div class="mut sm" style="flex-basis:100%">⭐ 本行两个金额是<b>手填的静止值</b>：实付请走<b>「手动新增通知书」</b>（统计结算恒 0）—— 它会自动冲减欠款合计与项目池，⛔ 但<b>不会</b>改本行这两个数（要它跟着反映 ⇒ 手工改「统计付款金额」）。⚠️ <b>两者成对使用</b>，分类与项目要和通知书一致，否则冲错池子；只加通知书不填本行 ⇒ 本栏会算成<b>负数</b>。</div>
    `})}`;
/* 造行：期初行 + 从「期初次月」到「最近一个有数据的月」逐月一行（空月也出行） */
const ledRows=(sc,proj)=>{ const side=m05Side(sc); if(!side) return [];
  return (side.display_rows||side.rows||[]).map(r=>({ ym:r.month, open:!!r.is_opening,
    kind:r.row_kind||'month', label:r.month_label||'', manual:numOr0(r.manual_payment), auto:numOr0(r.automatic_payment),
    id: r.is_opening ? side.opening_id : r.seq, cat: side.label,
    s: numOr0(r.other_expense), p: numOr0(r.payment), note: r.remark||'' })); };
/* —— 付款流水（**实际付款记录**）的筛选出口 ——
   ⚠️ 与逐月台账的「付款」列**不是一回事**：台账那一列取「统计付款金额」（欠款口径的旁路字段），
      这里筛的是**实际付款流水**（「已付金额」的来源，§4.4.2）。两个口径并存是**有意**的。 */
const ntOf=f=>NO.find(x=>x.id===f.nid)||null;
const flMonthOf=f=>String(f.date||'').slice(0,7);
const flProjOf=f=>{ const n=ntOf(f); return n?ntProjKey(n):''; };   /* 项目键 = 仓库名（§2.7.4） */
/* ⭐ `TAIL-283`：单据编码**后端随流水一起给**（`_flow_dict` 的 `doc_no`）⇒ ⛔ 不再经 `NO` 缓存取
   —— 那有两个坏处：没载入通知书列表时恒空；通知书失联（`notice_id` 为空 / 指向已删除的单）时
   也取不到 ⇒ 一条**明明有编码**的流水看起来像少了东西（而流水本身照旧要能查）。 */
const flDocNo=f=>f.doc||'';
const flProjs=()=>pjSort(uniqBy(FLs,f=>flProjOf(f)).filter(Boolean));
/* 月份条件已上移到 `tmIn(flf.ym, f.date)`（支持 月 / 跨月 / 年 / 全部）—— 这里只管**非时间**的三个条件 */
/* 「付款项目」= **多选**（全站约定：只有 MOD-09 是单选）· 键 = 仓库名、**按归属**归集（§2.7.4） */
const flHit=f=>(!flf.projs.length||flf.projs.indexOf(flProjOf(f))>=0)
  &&(flf.method==='全部'||f.method===flf.method)
  &&(flf.state==='全部'||(flf.state==='已撤销'?f.voided:!f.voided));
/* ⭐ `TAIL-283`：关键词 = **流水号 / 单据编码**（与搜索框 placeholder 同口径）——
   ⛔ 不再拿**数据库行号** `f.id` 顶流水号（那是"说错话"：拿它搜会命中一个屏幕上看不见的数）。 */
const flVisible=()=>FLs.filter(f=>tmIn(flf.ym,f.date)&&flHit(f)
  &&(!flf.q||(String(f.flowNo||'')+' '+flDocNo(f)).toLowerCase().includes(flf.q.toLowerCase())));
/* ⭐ `TAIL-283`：**屏幕行序**只在 DOM 里 —— 表头点击排序（`applySorts`）是"HTML 字符串 → HTML 字符串"
   的纯函数，`flVisible()` 出来的仍是**数组原序** ⇒ 导出要跟屏幕一致，只能按渲染后的数据行取序
   （数据行挂 `data-flow-id`；合计行 / 空态行没有该属性，天然不入）。
   ⚠️ 虚拟滚动（≥400 行）时表体只留一个窗口 ⇒ 用「DOM 数据行数 = 当前可见行数」当护栏，
   不等就交回数组顺序：**宁可行序不同，也⛔ 不悄悄少导行**。 */
const flDomIds=()=>{ const rows=flVisible();
  const dom=Array.from(document.querySelectorAll('#view table[data-sort-key="m05:flows"] tbody tr[data-flow-id]'));
  return dom.length===rows.length ? dom.map(tr=>Number(tr.dataset.flowId))
                                  : rows.map(r=>Number(r.id)); };
/* ⭐ 付款流水的「付款项目」筛选 = **共用面板 `projPanel`**（2026-09-13 用户口径：不得自造控件）。
   候选 = **流水里出现过的项目**（`flProjs()`，键 = 仓库名，归档排最后由 `pjSort` 处理）；
   ⚠️ 原先这里是自造的**原生 `<select>` 单选** —— 既破坏「统一多选面板」这条复用点，
      又与「全站约定：MOD-09 单选、其余多选」不一致 ⇒ 本次改回共用面板（多选）。 */
/* 展开态在 `PJ_OPEN`（key='flPj'） */
/* ⚠️ 候选 = **流水里出现过的项目** ∪ **当前已选的** —— 后者是为了「点付款统计的条目联动」时，
   那种**当前没有任何流水**的项目也能在面板里看到并勾上（否则"已选 N/M"里那个 N 会凭空多出一个、
   面板里却没有对应勾选框 ⇒ 状态与界面脱节）。这条是原「单选下拉」时代的既定行为，**必须保留**。 */
const flPjPanel=()=>projPanel({list:()=>pjSort(uniqBy([...flProjs(),...flf.projs],v=>v)),selected:()=>flf.projs,allAct:'flPjAll',noneAct:'flPjNone',pickAct:'flPjPick',meta:PROJ_META_KEY});
/* —— 付款统计 · 取数（《说明书》§4.5.5）——
   取值 = Σ有效流水实际付款金额。欠款旁路字段的人工调整不改变付款事实。剔除行不计。
   归月 / 归周 = 有效流水的**付款日期**；**周 = 周一 ~ 周日**（标签取该周周一）；项目按**归属**归集。
   ⭐ 2026-09-13 用户口径：**左栏「按项目」= 选定桶内**的分布（桶 = 月 或 周，可自己选）；
      **右栏趋势**：月粒度看**选定年的 12 个月**、周粒度看**选定季度的全部周**。 */
const wkMon=d=>{ const t=new Date(d+'T00:00:00'); if(isNaN(t.getTime())) return '';
  t.setDate(t.getDate()-((t.getDay()+6)%7));
  return ymdOf(t); };
const tmSun=mon=>tmD(new Date(new Date(mon+'T00:00:00').getTime()+6*864e5));     /* 该周周日 */
const pstYear=()=>pst.year||Number(SYS_YM.slice(0,4));
const pstQq=()=>/^\d{4}Q[1-4]$/.test(pst.q||'')?pst.q:tmQNow();
/* ⭐ 已接后端：付款统计**读 `/api/m05/stats`**（§4.5.5 的唯一出口）。
   ⚠️ 桶（周 / 月）与粒度由后端给；前端只做「当前桶 → 按项目条」这一层**显示**映射。 */
const m05BucketKey=()=>{ const now=new Date();
  const p=n=>String(n).padStart(2,'0');
  const ymd=`${now.getFullYear()}-${p(now.getMonth()+1)}-${p(now.getDate())}`;
  if(pst.gran!=='周') return ymd.slice(0,7)+'-01';
  const d=new Date(`${ymd}T00:00:00`); const wd=(d.getDay()+6)%7;    /* 周一为一周之始 */
  d.setDate(d.getDate()-wd);
  return `${d.getFullYear()}-${p(d.getMonth()+1)}-${p(d.getDate())}`; };
const m05Sun=b=>{ const d=new Date(`${b}T00:00:00`); d.setDate(d.getDate()+6);
  const p=n=>String(n).padStart(2,'0');
  return `${d.getFullYear()}-${p(d.getMonth()+1)}-${p(d.getDate())}`; };
const m05InBucket=(date,bk,g)=>{ const s=String(date||''); if(!s||!bk) return false;
  return g==='周' ? (s>=bk && s<=m05Sun(bk)) : s.slice(0,7)===bk.slice(0,7); };
const pstData=()=>{ const st=M05.stats||{};
  const g=M05_GRAN_UI[st.granularity]||pst.gran;
  const buckets=st.buckets||[], right=st.right||[], left=st.left||[];
  const selected=String(pst.ym||'');
  let bi=buckets.findIndex(b=>g==='周'?b===selected:b.slice(0,7)===selected.slice(0,7));
  if(bi<0) bi=buckets.findIndex(b=>g==='周'?b===m05BucketKey():b.slice(0,7)===m05BucketKey().slice(0,7));
  if(bi<0) bi=buckets.length-1;
  const picked=st.selected;
  const bk=picked?picked.bucket:(bi>=0?buckets[bi]:'');
  const year=st.year||pstYear(), q=st.quarter||pstQq();
  return { g, bk, ax: g==='周'?`${year}-${q}`:String(year),
    keys:buckets,
    labels: g==='周' ? buckets.map(b=>b.slice(5)+' ~ '+m05Sun(b).slice(5))
                     : buckets.map(b=>Number(b.slice(5,7))+' 月'),
    series: buckets.map((b,i)=>[b, numOr0(right[i])]),
    bkLabel: g==='周'&&bk ? (bk.slice(5)+' ~ '+m05Sun(bk).slice(5)) : bk,
    axLabel: g==='周' ? `${year} 年 Q${q}（${(q-1)*3+1}–${q*3} 月）` : `${year} 年`,
    title: g==='周' ? `${year} 年 Q${q}` : `${year} 年`,
    byPj: (picked?picked.projects.map(r=>[r.key||r.label,numOr0(r.amount)]):left.map(r=>[r.key||r.label, numOr0((r.cells||[])[bi])]))
             .filter(x=>x[0]).sort((a,b)=>b[1]-a[1]),
    bkTotal: numOr0(picked?picked.total:right[bi]), bkCnt: numOr0(picked?picked.count:(st.counts||[])[bi]),
    total: N2(right.reduce((a,v)=>a+numOr0(v),0)),
    n: !!buckets.length }; // 空窗口仍保留选桶/时间范围入口，便于查看有付款的期间。
};
const PJ_TRAIL=[];
/* MOD-01 筛选状态（R4：改动即时生效、无「应用」按钮；默认「在建」= §2.7 口径） */
let fPj={status:'在建',type:'全部',q:''};

