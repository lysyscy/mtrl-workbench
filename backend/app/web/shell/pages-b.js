/* shell/pages-b.js —— 壳的**独立件**（`P2-a` 拆件 · 2026-09-28 · 台账 `TAIL-164`）：`MOD-01`…`MOD-13` 各章的页辅助（各章里 `V.*` 之外的段）。
 *
 * ⭐ **为什么单开一件**：其余各页的筛选 / 口径 / 取数片段集中一件 ⇒ 各页的口径改动不必再翻 4000 行。
 *    `index.html` 原来一件套 4000 行（CSS ＋ HTML ＋ 内联脚本混装）⇒ 改一处要翻三个区
 *    （本会话两次白屏的同一个根）。本件是「**只拆非切片**」那一批里的一件。
 * ⛔ **本件不许碰**：任何 `V.<原型页>` 切片（它们**留在 `index.html`** —— 计划 §23 的口径，
 *    `ui_parity` 的 `U1` 逐行比它）· 口径判定（判定全在后端）· 界面文案的主人。
 * ⚠️ **加载顺序**：`index.html` 的 `<script src>` 顺序即真源 —— 本件排在 `actions.js` **之前**
 *    （`actions.js` / `core.js` 里有些表**加载期就求值**到本件的常量）。⛔ 别调顺序。
 * ⚠️ 本件的代码是**原样搬出**（逐字未改，含注释）；来历与搬法见计划 §15 `TAIL-164`。 */

const IVC5=['主辅材','工具','劳保','周转材料','临时设施'];
const amtOf=iv=>{const a=ADs.find(x=>x.ivid===iv.id); return a?a.newAmt:iv.amt};
const adjOf=iv=>ADs.find(x=>x.ivid===iv.id);
let PROC_PJS=[];
let PROC_MATRIX={};
let procPj='', procTab=1;   /* 初值同理由 `reloadInv()` 落定（不能取加载时的 `PROC_PJS[0]`） */
/* 项目、核算月、明细与合计均取后端同一领域矩阵。 */
const procMonths=proj=>(PROC_MATRIX[proj]?.raw||[]).map(r=>r.ym);
function procAgg(proj,adjusted,ym){
  const matrix=PROC_MATRIX[proj]||{}, tab=adjusted?'adjusted':'raw';
  const values=ym ? (matrix[tab]||[]).find(r=>r.ym===ym)||{} : matrix.totals?.[tab]||{};
  const num=k=>values[k]==null?null:Number(values[k]);
  const inC={},outC={};
  IVC5.forEach(c=>{inC[c]=num('in_'+c);outC[c]=num('out_'+c);});
  const m=MACH6_Z.map((_,i)=>num('mech_'+i));
  return {inC,outC,m};
}
/* 表体数据源：**一个核算月一行**（`[{ym,inC,outC,m}]`）—— 表① 与表② 是同一批月份，按下标对齐 */
const procRows=(proj,adjusted)=>procMonths(proj).map(ym=>Object.assign({ym},procAgg(proj,adjusted,ym)));
/* 当前选中的表名 —— 导出取数与按钮提示共用（**默认 = 表② 调整后表**） */
const procTabName=()=>procTab===2?'差异表':(procTab===1?'表② 调整后表':'表① 原始表');
/* MOD-06 的「项目」候选 = **库存单据里出现过的仓库**（`IV.wh` = 仓库名 ⇒ 天然就是候选键，§2.7.4）。
   **复用共用的项目面板 `projPanel`，但由调用点声明为「单选」**（2026-09-13 用户口径）；
   显示名走 `PROJ_META_KEY`（仓库名 → 展示名）。 */
const procPjPanel=()=>projPanel({list:()=>pjSort(PROC_PJS),selected:()=>[procPj],pickAct:'procPjPick',meta:PROJ_META_KEY,single:true});
/* 过程资料批量导出：同一弹窗复选项目并确认，默认当前项目；每项目一本，多个项目ZIP。 */
let procExpPjs=[];
/* 按提交顺序保存单格，未完成的输入留在当前格。 */
let procMechWrites=Promise.resolve();
const procExpDlg=()=>{
  const keys=pjSort(PROC_PJS),selected=new Set(procExpPjs);
  modal({title:`批量导出 · ${procTabName()}`,wide:true,body:`
    <div class="tip">导出所选项目的当前表；每项目一份，多个项目打包为 ZIP。</div>
    <div style="display:flex;gap:calc(8px * var(--fscale));margin-bottom:calc(8px * var(--fscale))"><button class="btn sm" data-act="procExpPjAll">全选</button><button class="btn sm" data-act="procExpPjNone">清空</button><span id="procExportCount" class="mut sm">已选 ${selected.size} 个项目</span></div>
    <div id="procExportProjects" style="max-height:48vh;overflow:auto;display:flex;flex-direction:column;gap:calc(8px * var(--fscale))">
      ${keys.map(key=>`<label style="display:flex;align-items:flex-start;gap:calc(8px * var(--fscale));overflow-wrap:anywhere"><input type="checkbox" class="chk" data-act="procExpPjPick" data-pj="${esc(key)}" ${selected.has(key)?'checked':''}><span>${esc(pjLabel(key))}</span></label>`).join('')}
    </div><div id="procExportError" class="sm" role="alert"></div>`,
    footer:`<button class="btn" data-act="procExpCancel">取消</button><button class="btn pri" data-act="procExpSave" title="${selected.size?'导出所选项目':'请先选择项目'}" ${selected.size?'':'disabled'}>导出</button>`});
};
const procExpSelection=()=>{
  const selected=new Set(procExpPjs);
  document.querySelectorAll('#procExportProjects input').forEach(el=>el.checked=selected.has(el.dataset.pj));
  const count=document.querySelector('#procExportCount');if(count) count.textContent=`已选 ${selected.size} 个项目`;
  const save=document.querySelector('[data-act="procExpSave"]');if(save){save.disabled=!selected.size;save.title=selected.size?'导出所选项目':'请先选择项目';}
};
const bigCands = () => pjKeysOfRows(pjNoShell().filter(p=>p.status==='在建'));   /* 候选 = 在建 · 非壳（实时算） */
/* ⭐ 2026-10-09（用户报障「排序能排、行不动」）：弹窗里的行**必须按草稿顺序画**。
   原来rows 直接 `bigCands()`（=档案顺序）⇒ 「序」列显示对了、行却不动，看起来像排序坏了。
   口径：已选的按**草稿顺序**排在前面，未选的按候选顺序接在后面 —— 与「先选后排」的用法一致。*/
const bigOrdered = () => { const d=BIGDRAFT||[], c=bigCands();
  return [...d.filter(wh=>c.includes(wh)), ...c.filter(wh=>!d.includes(wh))]; };
/* 集采台账筛选区：**说出所选的是哪些项目**（2026-10-09 用户要求）。
   原文只显示「已选 N 个」⇒ 筛完看不见筛的是什么（§4.7 同一对象的名称口径一致）。
   1 个 =「XX集采台账」｜2-3 个 =「XX、XX集采台账」｜4+ =「XX、XX、XX等 N 个项目集采台账」（§4.6 禁用态另有原因才置灰）。*/
const jcProjTxt = () => { const ks=fJc.projs||[]; if(!ks.length) return '';
  const nm=k=>pjDispOr(pjRowOf(k),k);
  return ks.length>3 ? `${ks.slice(0,3).map(nm).join('、')}等 ${ks.length} 个项目集采台账`
                     : `${ks.map(nm).join('、')}集采台账`; };
let BIGSET = [];   /* ⭐ 已接后端：由 `reloadM07()` 从 `/api/m07/big` 的 `selected` 原地填充（行序 = 大表自己的顺序；未选择项目时后端给「全部候选」，与原型同款） */
let BIGDRAFT = null;         /* 选择项目弹窗的**草稿**（「确定」前的临时顺序） */

/* ⭐⭐ 2026-09-28（用户口径）：「**导出总欠款**」也支持**选择项目 + 定顺序**（与月度会大表同一套交互）。
   ⚠️ 与月度会大表那套的**唯一区别**：它**不落库** —— 只决定"这一次导出的行集与行序"，不改任何数据；
   空数组 = **全部项目**（保持原来"一键全量"的行为，⛔ 不逼用户每次都选）。
   候选 = **项目档案全部（含归档 · 排壳）** —— 与「手动新增通知书 / 期初占位行」的项目候选**同一个出口**
   （导出的确会含归档项目，而且导出行序要能跟档案一致）。 */
const debtCands = () => pjSort(pjKeysOfRows(lgPjList()));
let DEBTPICK = [];           /* 已选项目（**仓库名**数组，顺序 = 导出行序）；空 = 全部 */
let DEBTDRAFT = null;        /* 选择项目弹窗的草稿（「确定」前的临时顺序） */
/* ⭐ 大表每一格的取数（**唯一出口**：页面渲染 / 导出共用）。
   `ym` = 核算月（默认 `bjMonth(-1)`，§9.2 材料报表类）。
   · 焊材 / 三气：取自库存入库原单（`EXTM`）—— 当月走 `extMon`、累计读后端年度合计（含历史列）。
   · 外租机械 = **外租零租含税 ＋ 外租包月含税**（= 进结算那两列）⇒ 当月复用 `machExtRent`、累计复用 `machSettleOf`。
   · 设备租赁（含内租）= **内租设备**（机械 6 列的第 1 列）。
   · **合计 = 外租机械开工累计 ＋ 设备租赁开工累计**（用户口径；已按模板图逐行核对）。
   ⚠️ **「租分公司设备」与两个「不含税」列不进本表**（用户口径）。 */
const bigRent     = (wh,ym) => machExtRent(wh, ym);
const bigRentCum  = wh => machSettleOf(wh);
const bigLease    = (wh,ym) => N2(mach6Arr(wh,ym)[1]);
const bigLeaseCum = wh => N2(Object.keys(MACH6[wh]||{}).reduce((a,k)=>a+bigLease(wh,k),0));
const bigTotalCum = wh => N2(bigRentCum(wh) + bigLeaseCum(wh));
let EXT_TOTALS = {};
const extAllTotal=(kind,wh,year)=>EXT_STATE.loaded?N0(((EXT_TOTALS[year]||{})[kind]||{})[wh]??extBalOf(kind,wh)):null;
const bigHWCum = (wh,year) => extAllTotal('焊材', wh,year), bigQTCum = (wh,year) => extAllTotal('气体', wh,year);
/* 会议大表与年度提取同源；累计不是按所看月份截断。 */
const bigExtractTip=(kind,cum)=>`${kind==='气体'?'三气':kind}${cum?'累计 = 手录2025-11及之前＋会议月份所属年12个月的提取金额；2025年1—11月不重复计入，往年展示金额不再加进合计':'当月 = 本项目核算月的提取金额'}；来源为库存单据明细原单入库金额，${kind==='气体'?'资源名称按气体白名单精确匹配':'按焊材关键词包含并排除工具等子串'}，不取出库、价税合计或调整金额`;
/* ⭐ **主材累计（含税）** 的**取数唯一出口**（2026-09-13 用户裁定：由手填改为**派生**）——
   口径 = **按项目取「集采台账结算」额**：= 该项目集采合同**结算金额之和**（§5.7.1）。
     · 结算口径本身**照搬** `jcSettle`（有贸易公司 → 贸易公司发票子表合计；无 → 供应商发票子表合计，§6.4.1），
       **不另立算法**；
     · ⭐ **只计「纳入台账」的合同**（用户 2026-09-13 裁定「甲」）—— 与 `MOD-11` 的「Σ 结算金额」KPI **同口径**；
     · 键 = 仓库名（§2.7.4）；项目恒有值 ⇒ 不需要"未指定"档。
   ⚠️ 视图 / 导出**一律走本出口**，不要在渲染里内联求和。 */
/* ⚠️ 「主材累计（含税）」的取数口**集采台账属 M5**：未接入时给 `null`（页面显「—」），⛔ 不写 0 冒充「确实没有」（`TAIL-25`；口径 = 后端 `mat_available`）。 */
const bigMatCum = wh => MAT_OK ? N2(JCs.filter(j => j.tag === '纳入台账' && j.proj === wh).reduce((a, j) => a + jcSettle(j), 0)) : null;
/* （原 `TOK` / `pickExtra` 已废：大表不再按"项目全名关键词"匹配，改按**仓库名**走上面的出口。） */
/* 库存焊材 / 气体：EXTM保存全部核算月金额供大表累计；年度页面读后端年度网格。
   extMon/extAllTotal未读取返回null，成功读取后的缺月为0。
   extSum为所选年金额，extTotal为历史列加所选年金额；历史手录值由BAL_EX保存。 */
let fExt = { status: '在建', year: bjMonth(-1).slice(0,4) };   /* 项目状态默认「在建」（用户口径）；年份默认上月所属年（§9.2） */
const extMons = () => Object.keys(EXTM).sort();
const extMon = (kind, wh, m) => { if(!EXT_STATE.loaded) return null; const h = ((EXTM[m] || {})[kind] || []).find(x => x[0] === wh); return h ? h[1] : 0; };
const extWhs = kind => { const s = new Set(); extMons().forEach(m => (EXTM[m][kind] || []).forEach(x => s.add(x[0]))); return pjSort([...s]); };
const extStatusOf = wh => { const p = pjRowOf(wh); return p ? p.status : ''; };
const extVisible = kind => EXT_STATE.loaded?((EXT_ANNUAL[kind]||{}).rows||[]).map(row=>row.warehouse):[];
const extAnnualOf=(kind,wh)=>((EXT_ANNUAL[kind]||{}).rows||[]).find(row=>row.warehouse===wh);
const extSum=(kind,wh)=>{const row=extAnnualOf(kind,wh);return row?N0(row.total)-N0(row.balance):null;};
const extTotal=(kind,wh)=>{const row=extAnnualOf(kind,wh);return row?N0(row.total):null;};
function extBlock(kind){
  const head=extHead();
  if(!EXT_STATE.loaded) return EMPTYROW(thCount(head),EXT_STATE.error||'正在读取库存年度汇总…','');
  const grid=EXT_ANNUAL[kind]||{},list=grid.rows||[];
  if(!list.length) return EMPTYROW(thCount(head),'当前筛选条件下没有'+kind+'数据','换个项目状态或年份');
  const rows=list.map(row=>{const wh=row.warehouse,bal=extBalOf(kind,wh);
    return `<tr><td class="fl">${esc(kind)}</td><td class="sm fl" style="min-width:180px;max-width:260px;white-space:normal;overflow-wrap:anywhere">${esc(wh)}</td><td class="num">${M(N0(row.prior))}</td>${row.cells.map(v=>`<td class="num">${v==null?'':M(N0(v))}</td>`).join('')}<td class="num">${M(N0(row.total))}</td><td class="num"><input class="inp num" data-act="extBal" data-k="${esc(kind)}" data-p="${esc(wh)}" value="${bal==null?'':esc(String(bal))}" placeholder="未录入" title="2025-11及之前金额，计入合计"></td></tr>`;
  }).join('');
  return rows+`<tr class="sum"><td class="fl">${kind}合计</td><td class="fl"></td>${(grid.sum_row||[]).map(v=>`<td class="num">${v==null?'':M(N0(v))}</td>`).join('')}<td></td></tr>`;
}
/* 手填值解析（OPEN-05）：当月已录入 → 用当月值（无标记）；否则向更早月份取「最近一次录入值」带入（标来源月）。
   注意用 != null 判断：0 是合法录入值，不能被当作「未录入」。 */
const bigOwn=(wh,m,i)=>{ const r=BIGVAL[m]&&BIGVAL[m][wh]; return (r&&r[i]!=null)?r[i]:null; };
/* 某一格的值：本月已录 → 直接取；否则**向前取最近一次录入值**（带入 · OPEN-05），并标出来源月。 */
function bigCell(wh,month,i){
  const own=bigOwn(wh,month,i);
  if(own!=null) return {v:own,from:null};
  const earlier=Object.keys(BIGVAL).filter(m=>m<month).sort().reverse();   /* 由近及远，实现「最近一次」 */
  for(const m of earlier){ const h=bigOwn(wh,m,i); if(h!=null) return {v:h,from:m}; }
  return {v:null,from:null};
}
/* 大表完整行（页面渲染、导出**共用**，保证「所见即所印」）—— 行序 = `BIGSET`（大表自己的顺序）。 */
function bigRows(month){
  return BIGSET.map(wh=>{ const p=pjRowOf(wh);
    const cells=BIGCOLS.map((c,i)=>bigCell(wh,month,i));
    const rentC=bigRentCum(wh), leaseC=bigLeaseCum(wh), totC=bigTotalCum(wh);
    const cap=bigCell(wh,month,1).v;                                /* 机械费测算（手填） */
    const cont=bigCell(wh,month,2).v, outv=bigCell(wh,month,3).v;   /* 合同（预估）价 / 产值累计（手填） */
    return { wh, disp:p?pjDispOr(p,wh):wh, cells, carryN:cells.filter(c=>c.from).length,
      hwc:bigHWCum(wh,month.slice(0,4)), hw:extMon('焊材',wh,month), qtc:bigQTCum(wh,month.slice(0,4)), qt:extMon('气体',wh,month),
      rentC, rent:bigRent(wh,month), leaseC, lease:bigLease(wh,month), totC,
      matC:bigMatCum(wh),                     /* 主材累计（含税）= 派生（按项目取集采台账结算额） */
      use:(cap?N2(totC/cap):null),            /* 使用率 = 合计 ÷ 机械费测算 */
      done:(cont?N2(outv/cont):null) };       /* 产值完成率 = 产值累计 ÷ 合同（预估）价 */
  });
}
/* 手填值的显示 / 落库换算（**界面形态 ↔ 存储形态**的唯一出口）：
   `ym` 年月原样（`YYYY-MM`）· `m` 金额按元（非负）· `t` 文本原样。非法一律给 NaN，由调用点走 `badMoney` 出口。 */
const bigDisp=(v,i)=>v==null?'':String(v);
const bigStore=(raw,i)=>{ const s=String(raw==null?'':raw).trim();
  if(BIGFMT[i]==='t') return s;
  if(BIGFMT[i]==='ym') return /^\d{4}-(0[1-9]|1[0-2])$/.test(s)?s:null;   /* `null` = 格式非法（**不能用 NaN 判**：`isNaN('2024-05')` 恒为 true） */
  return N2(parseFloat(s)); };
let invWhs=[], fIvCol={}, invColOpen='', invOnlyAdj=false, fIvDir='全部', fIvYm=bjMonth(-1);
/* ⚠️ 候选 = **库存单据里真实出现过的仓库名**（`PROC_PJS`）——
   原先用演示主数据 `WHs.map(w=>w.name)`：那 8 个演示仓库名与 i8 真名对不上，
   **选了候选也筛不出任何行**（静默失配、不报错）。 */
const invWhPanel=()=>projPanel({list:()=>pjSort(uniqBy(IVs,iv=>iv.wh)),selected:()=>invWhs,allAct:'invWhAll',noneAct:'invWhNone',pickAct:'invWh',meta:PROJ_META_KEY});
/* ---------- 「每列可筛」（Excel 式自动筛选）----------
   `IV_FCOL` = 列元数据的**唯一出处**：`i` = 该列在 `INV_THEAD` 里的下标（0 起算；**末列「操作」不参与**），
   `k` = 取数字段（`adj` = 调整后金额，派生自调整单），`t` = 列型 ——
     · `text`  → 「包含」输入框 + 值清单多选
     · `enum`  → 值清单多选（方向 / 单位 / 业务类型 / 仓库）
     · `date`  → 「包含」（按 `YYYY-MM` 前缀模糊）+ 值清单多选
     · `num`   → 「≥ / ≤」区间**＋ 值清单多选**（两者都给：区间管"多大范围"、值清单管"具体哪几个数"）
   同一列可同时用多种条件，条件之间是**与**关系；不同列之间也是**与**关系。 */
const IV_FCOL=[
 {i:0,k:'docNo',t:'text'},{i:1,k:'seq',t:'text'},{i:2,k:'dir',t:'enum'},{i:3,k:'mat',t:'text'},
 {i:4,k:'spec',t:'text'},{i:5,k:'unit',t:'enum'},{i:6,k:'qty',t:'num'},{i:7,k:'px',t:'num'},
 {i:8,k:'pi',t:'num'},{i:9,k:'amt',t:'num'},{i:10,k:'adj',t:'num'},{i:11,k:'tax',t:'num'},
 {i:12,k:'biz',t:'enum'},{i:13,k:'cp',t:'text'},{i:14,k:'dd',t:'date'},{i:15,k:'ad',t:'date'},
 {i:16,k:'wh',t:'enum'},{i:17,k:'wbs',t:'text'},{i:18,k:'cbs',t:'text'}
];
const IV_COLN=IV_FCOL.length;                    /* 参与列筛选的列数（= INV_THEAD 列数 − 1 个「操作」列） */
const ivColMeta=i=>IV_FCOL.filter(c=>c.i===i)[0];
const ivRaw=(iv,i)=>{ const c=ivColMeta(i); if(!c) return ''; if(c.k==='adj'){ const a=adjOf(iv); return a?a.newAmt:''; } const v=iv[c.k]; return v==null?'':v; };
const ivTxt=(iv,i)=>String(ivRaw(iv,i));
const ivHasF=i=>{ const f=fIvCol[i]; return !!(f&&((f.v&&f.v.length)||(f.q!=null&&f.q!=='')||(f.min!=null&&f.min!=='')||(f.max!=null&&f.max!==''))); };
const ivColN=()=>IV_FCOL.filter(c=>ivHasF(c.i)).length;
/* 值清单 = 该列在「当前年月 + 只调整 + 方向」这三个**粗筛**下出现过的值（去重、字典序）——
   与 Excel 一致：下拉里列的是"当前可见范围内的值"。⚠️ 不复用 `V.m08` 的 `list`（那会自我循环）。 */
const ivDistinct=i=>[...new Set(IVs.filter(iv=>tmIn(fIvYm,iv.dd)&&(!invOnlyAdj||adjOf(iv))&&(fIvDir==='全部'||iv.dir===fIvDir)).map(iv=>ivTxt(iv,i)).filter(v=>v!==''))].sort();
const ivColPass=(iv,i)=>{ const f=fIvCol[i]; if(!f) return true; const c=ivColMeta(i); if(!c) return true;
  if(c.t==='num'){ const raw=ivRaw(iv,i); if(raw==='') return false; const v=Number(raw);
    if(f.min!=null&&f.min!==''&&!(v>=Number(f.min))) return false;
    if(f.max!=null&&f.max!==''&&!(v<=Number(f.max))) return false;
    /* ⭐⭐ 2026-09-13 用户口径**更正**：数值列的**值清单勾选必须生效**。
       原实现这里只看 `min` / `max`、**忽略 `f.v`** ⇒ 值清单"点了没反应"；
       当时的修法是把值清单删掉 —— **理解偏了**（用户要的是"修复它"而非"删掉它"）。
       语义与文本列一致：**多选值之间是「或」，与「≥ / ≤」区间之间是「与」**。 */
    if(f.v&&f.v.length&&f.v.indexOf(String(raw))<0) return false;
    return true; }
  const s=ivTxt(iv,i);
  if(f.q!=null&&f.q!==''&&s.toLowerCase().indexOf(String(f.q).toLowerCase())<0) return false;
  if(f.v&&f.v.length&&f.v.indexOf(s)<0) return false; return true; };
/* 表头 = `INV_THEAD` + 每列插一个筛选入口（**末列「操作」不插**）。
   ⚠️ 用 `<button>` 而不是 `<input>` —— `applySorts` 判定"该列可排"时会跳过**含 `<input>` 的表头**
      （那本来是给"全选"框用的）⇒ 用 `<input>` 会把整列变成不可排。⚠️ 按钮不写进 `INV_THEAD`
      常量本身（它要用于 `thCount` 与列对齐断言，保持纯净）。 */
const ivThead=()=>{ let n=-1; return INV_THEAD.replace(/<th\b([^>]*)>([\s\S]*?)<\/th>/g,(m,a,txt)=>{ n++;
  if(n>=IV_COLN) return m; const on=ivHasF(n);
  return `<th${a}>${txt} <button class="btn sm" data-act="ivColOpen" data-c="${n}" title="筛选本列${on?'（已设条件）':''}" style="padding:0 calc(4px * var(--fscale))">▾${on?'<b style="color:var(--pri)">·</b>':''}</button></th>`; }); };
/* 列筛选面板：**渲染在表格之外**（表格滚动容器 `.tw` 会裁掉浮层 ⇒ 不能贴着表头弹出） */
const ivColPanel=()=>{ const i=Number(invColOpen), c=ivColMeta(i); if(!c) return '';
  const f=fIvCol[i]||{};
  /* ⭐⭐ 2026-09-13 用户口径**更正**（本条此前写反了）：**数值列照旧给值清单，而且必须真的生效**。
     起因：原实现数值列也渲染了值清单，但 `ivColPass` 的 num 分支只看 `min` / `max`、**忽略勾选值**
     ⇒ 清单"点了没反应"（用户报「数量列不能用」）；当时的修法是**把值清单删掉** —— **理解偏了**，
     用户要的是「**修复这个 bug**」而不是「**把勾选删掉**」。
     现修法：值清单**各列型一律渲染**（右侧一栏），num 列的勾选在 `ivColPass` 里**真的参与判定**。 */
  const vals=ivDistinct(i);
  const nm=String(((String(INV_THEAD).match(/<th\b[^>]*>([\s\S]*?)<\/th>/g)||[])[i]||'')).replace(/<[^>]*>/g,'').trim()||('第'+(i+1)+'列');
  return `<div style="display:flex;gap:calc(8px * var(--fscale));align-items:flex-start;flex-wrap:wrap;padding:calc(2px * var(--fscale)) 0">
    <div style="min-width:168px"><div class="mut sm" style="margin-bottom:calc(3px * var(--fscale))">列：<b>${esc(nm)}</b></div>
      ${c.t==='text'||c.t==='date'?`<input class="inp" data-act="ivColQ" data-c="${i}" value="${esc(f.q||'')}" placeholder="包含…${c.t==='date'?'（如 2026-08）':''}">`:''}
      ${c.t==='num'?`<div style="display:flex;gap:calc(4px * var(--fscale))"><input class="inp num" data-act="ivColMin" data-c="${i}" value="${f.min==null?'':esc(String(f.min))}" placeholder="≥"><input class="inp num" data-act="ivColMax" data-c="${i}" value="${f.max==null?'':esc(String(f.max))}" placeholder="≤"></div>`:''}
      <div style="margin-top:calc(6px * var(--fscale))"><button class="btn sm" data-act="ivColClear" data-c="${i}">清除本列</button><button class="btn sm" data-act="ivColClose">收起</button></div></div>
    <div style="max-height:172px;overflow:auto;border-left:1px solid var(--bd2);padding-left:calc(8px * var(--fscale))">
      ${vals.length?vals.map(v=>`<label style="display:flex;gap:calc(6px * var(--fscale));align-items:center;padding:calc(3px * var(--fscale)) calc(6px * var(--fscale));font-size:calc(12px * var(--fscale));white-space:nowrap;cursor:pointer"><input type="checkbox" class="chk" style="flex:0 0 auto" data-act="ivColVal" data-c="${i}" data-v="${esc(v)}" ${(f.v||[]).indexOf(v)>=0?'checked':''}><span>${esc(v)}</span></label>`).join(''):'<div class="mut sm">该列当前无值</div>'}
    </div></div>`;
};
const sumAdj=iv=>{const a=adjOf(iv); return a?N2(a.newAmt-iv.amt):0};
const awfPjPanel=()=>projPanel({list:()=>AWF_PJS,selected:()=>[awfPj],pickAct:'awfPjPick',meta:PROJ_META_KEY,single:true});
const AWF_RATIO_TIP='占合计 = 本行金额÷本项目本核算月合计（安全文明施工费＋全部手填项，含0及负数）；不跨项目或月份，合计不大于0显示—';
/* ⚠️ 默认项目**不在这里赋** —— 原先写 `(pjSort(ntPjList())[0]||{name:''}).name`，那是**加载时求值**：
   `PJs` 异步填充 ⇒ 取数回来时它早已定死成空（**静默失去默认项目**，且不报错）。
   ⇒ 改由 `reloadM09()` 按后端回包的 `project` 落定（后端 `service._resolve` 已把"没给 / 给了无效值"
     归一成候选第一个；候选为空时才是空串）。 */
let dfNewOn=false;
let dfD={month:'',proj:'',detail:'',amount:'',remark:'',status:'待核对'};
let fDf={ym:'全部',stat:'全部'};
const dfBlank=()=>({month:/^\d{4}-\d{2}$/.test(fDf.ym)?fDf.ym:bjMonth(-1),proj:'',detail:'',amount:'',remark:'',status:'待核对'});
/* ⚠️ 草稿层复位**必须原地改字段**（不能 `dfD=dfBlank()`）—— `dfD` 是导出给自检的**对象引用**，
   重新赋值会换掉引用 ⇒ 自检拿到的还是旧对象（本项目反复踩过这条）。 */
const dfClear=()=>{ Object.keys(dfD).forEach(k=>delete dfD[k]); Object.assign(dfD,dfBlank()); };
/* ⛔ `nextDfId`（本地算编号）**已于 2026-09-20 删除**。
   ⚠️ 后半句「编号由 `mod12_diff.domain.next_seq` 发」**已过期**（当日稍后 `MOD-12` 整个
   页面被用户裁定取消）⇒ 差异**不再有独立编号**，它是**调整单的产物**、编号由 `m08` 承载
   （判据点 `ACC-DIF-REG-001/001-02`）。 */
/* 核算月候选 = 数据里出现过的月 ∪ 上月 ∪ 当月（倒序）——**行内**选月。
   ⚠️ 有意**不用** `tmBtn`：草稿行在 `.tw` 滚动容器里，年月浮层会被裁掉
      （与「月度会大表开工时间」同源的技术理由；§六-30 那条「凡选时间一律用 tmBtn」的既有例外）。 */
const dfMonthOpts=()=>optsOf([...new Set([...DFs.map(d=>d.month),bjMonth(-1),bjMonth()])].filter(m=>/^\d{4}-\d{2}$/.test(m)).sort().reverse(),dfD.month);
/* 「项目」候选 = **复用 MOD-03 手动行的同一出口** `ntPjList()`（全部已建档 · 含归档 · 不含壳，§六-9）；
   落库写**全名**（与差异登记既有数据形状一致），显示走 `pjDisp` + `pjArcMark` 两个共性出口。
⚠️⚠️ 2026-09-20 修（用户实测：「手动增行**默认项目已经选了**，但点保存显示**未选择项目**不能保存」）：
   **必须有空占位项** —— `<select>` 里没有任何 `selected` 时，**浏览器会把第一个选项「显示」成已选**，
   而草稿层 `dfD.proj` 仍是空串 ⇒ **显示骗了人**：用户以为选了、状态里没有 ⇒ 保存必被拒（且看不出为什么）。
   ⇒ 照**已跑通的兄弟页**（`m04` 的 `plProjOptions`）加 `<option value="">（请选择项目）</option>` 并默认选它。
   ⛔ **不是**"把第一个候选塞进 `dfD.proj`" —— 那会让人在**没选**的情况下，
      把差异**静默记到第一个项目头上**（记错账比记不上更贵：账面上多了一笔不属于它的差异）。
   ⭐ 这条也顺带让判据点 `001-03`（项目必填）**在界面上真的够得着** —— 否则它永远只在后端被"想象"着测。 */
const dfPjList=()=>pjSort(ntPjList());
const dfPjOpts=()=>`<option value=""${dfD.proj?'':' selected'}>（请选择项目）</option>`
  + dfPjList().map(p=>`<option value="${esc(p.full)}" ${dfD.proj===p.full?'selected':''}>${esc(pjDisp(p))}${pjArcMark(p,1)}</option>`).join('');
/* 草稿行：**列对齐**（`<td>` 数 = 表头列数）· 挂 `draftrow`（`applySorts` 把它钉在数据行之后、合计行之前）。
   「归属」恒为「库存单据」（§5.8.3）⇒ 只显示、不可选。 */
const dfDraftRow=()=>`<tr class="draftrow">
  <td class="fc">新增</td>
  <td><select class="inp" style="min-width:104px" data-act="dfSet" data-k="month" title="核算月（这笔差异归到哪个月）">${dfMonthOpts()}</select></td>
  <td>${tag('库存单据','in')}</td>
  <td><select class="inp" style="min-width:170px" data-act="dfSet" data-k="proj" title="项目（全部已建档 · 含归档、不含壳）">${dfPjOpts()}</select></td>
  <td><input class="inp" style="min-width:150px" data-act="dfSet" data-k="detail" value="${esc(dfD.detail)}" placeholder="差在哪（一句话）"></td>
  <td class="num"><input class="inp num" style="width:104px" data-act="dfSet" data-k="amount" value="${esc(dfD.amount)}" placeholder="可正可负" title="带符号：+ 上调 / − 下调（§5.8.3），与调整单差额同源"></td>
  <td class="ctr"><select class="inp" style="width:auto" data-act="dfSet" data-k="status">${enumOpts('dfState',dfD.status)}</select></td>
  <td><input class="inp" style="min-width:130px" data-act="dfSet" data-k="remark" value="${esc(dfD.remark)}" placeholder="备注"></td>
  <td class="ctr now"><button class="btn sm pri" data-act="dfSave" title="校验通过后写入（归属恒为「库存单据」）">保存</button> <button class="btn sm" data-act="dfCancel" title="丢弃这一行草稿（不写入）">取消</button></td></tr>`;
let fJc={tag:'纳入台账',arch:'全部',sup:'',projs:[],amt:''};
/* 展开态在 `PJ_OPEN`（key='jcPj'） */                 /* 「项目」多选面板的展开态（第 4 个 projPanel 调用点） */
/* 集采三态「批量标记」的勾选集合（§6.5.3）：范围 = **当前筛选结果**，筛选变化时裁剪 */
let jcPick=new Set();
/* 「项目」筛选走**通用控件**（= 共用项目面板 `projPanel`，多选、默认全部；2026-09-13 用户口径）——
   ⚠️ 本项目**表内不设「项目」列**，项目只作为筛选条件存在。 */
const jcPjPanel=()=>projPanel({list:JC_PROJ_LIST,selected:()=>fJc.projs,allAct:'jcPjAll',noneAct:'jcPjNone',pickAct:'jcPjPick',meta:PROJ_META_KEY});
/* —— 「手工新增集采合同」的**增行展开区**（2026-09-13 增行模式，用户拍板 C-1 / C-6 / C-7）——
   ⚠️ 弹窗已取消 ⇒ 改为**表格上方的独立条带**，且渲染在 `.tw` **之外**（浮层面板才不会被裁）。
   ⚠️ 主表 **19 字段放不进 20 列**，且表内**刻意不设「项目」列** ⇒ 真正的"建档录入项"全部放这里；
      「发票金额 / 贸易公司发票金额 / 付款金额」= **各自子表合计**、「结算 / 欠款」= 自动算
      ⇒ **一律不出现在新增区**（建档后走各列右侧的「子表」）。 */
let jcNewOn=false;                 /* 增行态开关（取代原弹窗的"是否开着"） */
/* 展开态在 `PJ_OPEN`（key='jcNPj'） */               /* 「项目」共用面板（**单选** —— 第 10 个 `projPanel` 调用点）是否展开 */
let jcND={date:SYS_TODAY,material:'',supplier:'',contractAmt:'0.00',tradeCo:'',tradeContractAmt:'',method:'',remark:'',pj:''};
const jcNPjPanel=()=>projPanel({list:()=>pjKeysOfRows(ntPjList()),selected:()=>[jcND.pj],pickAct:'jcNPjPick',meta:PROJ_META_KEY,single:true});
const jcNewStrip=()=>`${FBAR({cls:'strip mb6',body:`
      <div class="fi"><span class="pill" style="margin:0" title="建一张集采合同主表行（两态默认「纳入台账」，与抓取行一致）">手工新增合同</span></div>
      <div class="fi pjwrap" style="position:relative"><label>项目</label>
        ${PJB({act:'jcNPjToggle',w:150,label:`${esc(pjLabel(jcND.pj)||'请选择项目')}${pjArcMark(pjRowOf(jcND.pj))}`})}
        ${pjIsOpen('jcNPj')?jcNPjPanel():''}</div>
      <div class="fi"><label>合同日期</label><input class="inp" type="date" id="jcNDate" data-act="jcNSet" data-k="date" value="${esc(jcND.date)}"></div>
      <div class="fi"><label>材料名</label><input class="inp" style="min-width:150px" id="jcNMaterial" data-act="jcNSet" data-k="material" value="${esc(jcND.material)}" placeholder="例：热轧卷板 Q235B"></div>
      <div class="fi"><label>供应商</label><input class="inp" style="min-width:150px" id="jcNSupplier" data-act="jcNSet" data-k="supplier" value="${esc(jcND.supplier)}"></div>
      <div class="fi"><label>合同金额</label><input class="inp num" style="width:118px" id="jcNAmt" data-act="jcNSet" data-k="contractAmt" value="${esc(jcND.contractAmt)}"></div>
      <div class="fi"><label>贸易公司名</label><input class="inp" style="min-width:130px" id="jcNTradeCo" data-act="jcNSet" data-k="tradeCo" value="${esc(jcND.tradeCo)}" placeholder="留空 = 无贸易公司"></div>
      <div class="fi"><label>贸易公司合同金额</label><input class="inp num" style="width:118px" id="jcNTradeAmt" data-act="jcNSet" data-k="tradeContractAmt" value="${esc(jcND.tradeContractAmt)}" placeholder="—"></div>
      <div class="fi"><label>付款方式</label><input class="inp" style="min-width:130px" id="jcNMethod" data-act="jcNSet" data-k="method" value="${esc(jcND.method)}" placeholder="自由文本 · 例 60±7天承兑"></div>
      <div class="fi"><label>备注</label><input class="inp" style="min-width:130px" id="jcNRemark" data-act="jcNSet" data-k="remark" value="${esc(jcND.remark)}"></div>
      <button class="btn pri" data-act="jcRowSave" title="建档（两态默认「纳入台账」，与抓取行一致）">保存</button>
      <button class="btn" data-act="jcRowCancel" title="丢弃这条录入（不入库）">取消</button>
      <span class="pill" style="margin-left:auto">发票金额 / 贸易公司发票金额 / 付款金额 = <b>各自子表合计</b>（建档后在各列右侧「子表」里录）</span>
    `})}`;
const jcVisible=()=>JCs.filter(j=>(fJc.tag==='全部'||j.tag===fJc.tag)
  &&(fJc.arch==='全部'||j.arch===fJc.arch)
  &&(!fJc.projs.length||fJc.projs.includes(j.proj))
  /* ⭐ 「待补供应商价」= `contract_amt` 为 0/空 —— 主要是**贸易公司合同**（i8 那个价落进
     `trade_contract_amt` 了，真供应商价要人工从 Excel 供应商线补）。`0` 即"没填"（前端已显示「— 待补」）。 */
  &&(fJc.amt===''||(fJc.amt==='blank'?!j.contractAmt:!!j.contractAmt))
  &&(!fJc.sup.trim()||(j.supplier||'').includes(fJc.sup.trim())));
const pruneJcPick=()=>{ const vis=new Set(jcVisible().map(j=>j.id)); [...jcPick].forEach(id=>{ if(!vis.has(id)) jcPick.delete(id); }); };
let busy=false;
const kvBlock=pairs=>`<div style="display:grid;grid-template-columns:118px 1fr;gap:calc(6px * var(--fscale)) calc(12px * var(--fscale));font-size:calc(12px * var(--fscale));margin-bottom:calc(13px * var(--fscale))">${pairs.map(([k,v])=>`<div class="mut">${k}</div><div>${v}</div>`).join('')}</div>`;

