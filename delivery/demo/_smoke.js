/* 材料报表自动化工作台 · 交互原型 自检脚本
   无需浏览器：自写 DOM 桩 + vm.runInContext 跑全量视图与交互，并断言业务口径。
   用法：node demo/_smoke.js
   ── 说明：交互测试会真实修改内存数据（这是预期行为），故在交互组前后做「快照 / 回滚」，
      使纯数据断言始终跑在干净基线上。 */
const fs = require('fs'), vm = require('vm'), path = require('path');
const p = path.join(__dirname, '材料报表自动化工作台-交互原型.html');
const html = fs.readFileSync(p, 'utf8');
const js = html.slice(html.indexOf('<script>') + 8, html.lastIndexOf('</script>'));

/* ---------- DOM 桩 ---------- */
function mkEl(tag) {
  const el = {
    tagName: (tag || 'div').toUpperCase(), _html: '', value: '', textContent: '', checked: false,
    dataset: {}, style: {}, className: '', disabled: false, oninput: null,
    classList: { add() {}, remove() {}, contains() { return false; }, toggle() {} },
    appendChild() {}, remove() {}, focus() {}, dispatchEvent() { return true; },
    setAttribute() {}, getAttribute() { return null; }, closest() { return null; },
    querySelector() { return mkEl('div'); }, querySelectorAll() { return []; }
  };
  Object.defineProperty(el, 'innerHTML', { get() { return el._html; }, set(v) { el._html = String(v); } });
  return el;
}
const cache = {};
const doc = {
  querySelector(sel) { return cache[sel] || (cache[sel] = mkEl('div')); },
  querySelectorAll() { return []; },
  createElement: mkEl, addEventListener() {}, body: mkEl('body')
};
/* ⭐ `window.print()` 调用记录（2026-09-14 加）：用来**行为式**地钉住 DEV-P-07 ——
   「付款通知书批量打印」只准调 i8 接口，**不准自建打印模板**（= 不准走浏览器打印）。
   对照样本 = **手工触发一次**（不再借某个业务功能 —— 2026-09-14「活动大表 A3 打印」已取消）。 */
const PRINT_CALLS = [];
const ctx = { document: doc, window: { print() { PRINT_CALLS.push(1); } }, console, setTimeout, Date, Math, JSON, Object, Array, String, Number, parseFloat, isNaN, Set, prompt: () => '1000', Event: class { constructor(t) { this.type = t; } } };
ctx.globalThis = ctx;
vm.createContext(ctx);

/* 注意：vm 里顶层 const 不会挂到 context 对象上，必须在脚本末尾显式导出 */
/* ⭐ 2026-09-26（`#2`）：`CHG`（变更事件白名单）**已从原型整份删除** ⇒ 这里**不再导出它** ——
   原先导了、而原型里已没有这个绑定 ⇒ `globalThis.__X={…,CHG,…}` 当场 `ReferenceError`，
   整个自检**连一行都跑不了**（症状 = `RUN FAIL: CHG is not defined`）。
   「名单不许回来」由下面那条 `N6′` 守卫看着，⛔ 别再往这里加回去。 */
/* ⭐ 2026-09-26（`#1`）：原型把**所有面板的展开态收进 `PJ_OPEN`**（key 由面板的 `pickAct` 派生）⇒
   原先"各持一个 `let XxxPjOpen`"的写法全部作废。本列表里这 9 项（`pjIsOpen` · `ledPjOpenState` ·
   `lgXState` · `jcNewState` · `ledExpState` · `procExpState` · `jcPjState` · `flPjOpenState` · `procState`）
   连同配套的 4 个 setter 已一并改写成 `pjIsOpen('<key>')` / `PJ_OPEN['<key>']`。
   ⚠️ 改之前的症状：getter ⇒ `RUN FAIL: procPjOpen is not defined`（**自检连一行都跑不了**）；
   setter ⇒ **静默失效**（给一个已删变量赋值，sloppy 模式凭空造个全局、不报错）⇒ 会伪装成"断言怎么都不绿"。 */
const EXPORT = '\n;globalThis.__X={V,ACT,debts,WHs,EXTRACT,sums,IVC5,procAgg,NO,FLs,ADs,MACH6,mach6Arr,machExtRent,machSettleOf,JCs,PJs,IVs,DFs,LGs,'
  + 'statOf,paidOf,jcDebt,jcPay,jcSettle,jcInvSum,jcTradeInvSum,adjOf,ntHit,fNt,monthEnd,SYS_YM,bjMonth,AWF,awfList,awfYmState:()=>awfYm,awfPjState:()=>awfPj,modalOpenerState:()=>modalOpener,dispCell,projMatches,PROJ_LIST,mp,'
  + 'payEff,hasT,pickSet,prunePick,BIND,pjIsOpen:()=>pjIsOpen("pj"),mpState:()=>mp.open,ivDirState:()=>fIvDir,'
  + 'M,N2,PJ_TRAIL,fPj,fJc,fNt,PROMOTE_WH,'
  + 'OWN,ownOf,ownCands,isShellFull,matchKids,kwList,addKw,shellOf,'
  + 'USERS,CUR,U_COLS,PL_COLS,PLs,plf,plPick,PL_PROJ_LIST,plVisible,prunePlPick,plRev,setPlImportM:(m)=>{plImportM=m;},'
  + 'PL_NEW_ID,plRowOn,plRowState:()=>({id:plRowEditId,d:plD}),setPlRow:(o)=>{plRowEditId=o.id;plD=o.d;},plNextIds,'
  + 'plProjHit,plProjOne,plProjKey,plProjCell,'
  + 'SYS_TODAY,plWin,plHit,revIs,setToday:(d)=>{SYS_TODAY=d;},'
  + 'ledRows,ledSettle,ledPay,LED_PROJS,ledProjs,ntProjKey,ntProjName,ntYm,lgProjKeyOf,nextYm,LEDNOTE,pjKey,pjLabel,PROJ_META_KEY,'
  + 'ledState:()=>({proj:ledProj,cut:lgCut}),ledPjOpenState:()=>pjIsOpen("ledPj"),setLed:(o)=>{ledProj=o.proj;lgCut=o.cut;},'
  + 'ntPjList,lgDefPjName,lgEarliest,lgCutFor,prevYm,ntBlank,lgPjList,arcOf,arcOfFull,arcOfDisp,'
  + 'naState:()=>({d:naD,id:naEditId}),setNa:(o)=>{naD=o.d;naEditId=o.id;},setLgPjName:v=>{lgPjName=v;},'
  + 'lgXState:()=>({on:lgOn,pj:lgPjName,cat:lgCat,cut:lgCut,open:pjIsOpen("lgPj")}),setLgX:(o)=>{lgOn=o.on;PJ_OPEN["lgPj"]=!!o.open;},'
  + 'jcNewState:()=>({on:jcNewOn,pj:jcND.pj,open:pjIsOpen("jcNPj")}),setJcNew:(o)=>{jcNewOn=o.on;PJ_OPEN["jcNPj"]=!!o.open;},'
  + 'jcSubState:()=>({kind:jcSubKind,id:jcSubId,d:jcSubD}),setJcSub:(o)=>{jcSubKind=o.kind||"";jcSubId=o.id||"";jcSubD=o.d||{date:"",amt:""};},jcSubOn,JCSUB_KIND,'
  + 'fetchKindState:()=>fetchKind,setFetch:(o)=>{fetchKind=o.kind||"nt";fetchM=o.m||bjMonth();},'
  + 'ledExpState:()=>({on:ledExpOn,open:pjIsOpen("ledExpPj"),pjs:ledExpPjs}),setLedExp:(o)=>{ledExpOn=!!o.on;PJ_OPEN["ledExpPj"]=!!o.open;ledExpPjs.length=0;(o.pjs||[]).forEach(v=>ledExpPjs.push(v));},'
  + 'procExpState:()=>({on:procExpOn,open:pjIsOpen("procExpPj"),pjs:procExpPjs}),setProcExp:(o)=>{procExpOn=!!o.on;PJ_OPEN["procExpPj"]=!!o.open;procExpPjs.length=0;(o.pjs||[]).forEach(v=>procExpPjs.push(v));},'
  + 'ordOf,cmpPj,pjSort,pjSortedAll,renumberPj,pjRowOf,WHs,'
  + 'jcPick,jcVisible,pruneJcPick,JC_PROJ_LIST,jcPjState:()=>pjIsOpen("jcPj"),'
  + 'BIGVAL,BIGSET,bigCands,BIGCOLS,BIGFMT,bigCell,bigRows,bigOwn,bigRent,bigRentCum,bigLease,bigLeaseCum,bigTotalCum,bigHWCum,bigQTCum,bigMatCum,BIG_THEAD,bigDraft:()=>BIGDRAFT,SORT,applySorts,draftState:()=>payDraft,'
  + 'numOf,badMoney,badMoneyMsg,overCap,CAP_TOL,ENUMS,enumVals,enumTag,thCount,fmtTime,nowStamp:now,'
  + 'LED_THEAD,PJ_THEAD,DIFF_THEAD,INV_THEAD,JCINV_THEAD,JCPAY_THEAD,JC_THEAD,AWF_THEAD,FL_THEAD,flf,flVisible,flHit,flProjs,flMonthOf,flProjOf,flPjOpenState:()=>pjIsOpen("flPj"),'
  + 'pst,pstData,pstBucket,pstLatest,pstY,pstAt,pstSum,pstMonthsOfYear,tmSun,tmIn,tmLabel,tmRange,tmStart,tmQof,tmQNow,tmWeeksOfQ,wkMon,RUNLOG,'
  + 'PROC_PJS,procMonths,procRows,procTabName,procState:()=>({pj:procPj,tab:procTab,open:pjIsOpen("procPj")}),setProcTab:t=>{procTab=t;},'
  + 'lgD,LG_R_DEF,pjArcMark,pjDisp,pjDispOr,awfAuto,awfTotal,RULE_EX,SIG,ivYmState:()=>fIvYm,'
  + 'WHM,whRows,whYmState:()=>fWhYm,WH_THEAD,'
  + 'EXTM,extMon,extMons,extWhs,extVisible,extSum,extTotal,extState:()=>fExt,EXT_THEAD,'
  + 'BAL_EX,extBalOf,EXT_BAL_NOTE,extBlock,'
  + 'jcRefOf,jcUsedNids,jcLinkSelState:()=>jcLinkSel,dfState:()=>({on:dfNewOn,d:dfD,f:fDf}),setDf:(o)=>{dfNewOn=!!o.on;Object.keys(dfD).forEach(k=>delete dfD[k]);Object.assign(dfD,o.d||{});fDf.ym=o.f.ym;fDf.stat=o.f.stat;},'
  + 'supPool,supMatch,supFrags,supHas,SUP_LVL_NAME,SUP_SUG,jcLinkCands,supSelState:()=>supSel,setSupSel:v=>{supSel=v;},clearSup:()=>{Object.keys(SUP_SUG).forEach(k=>delete SUP_SUG[k]);},'
  + 'IMP_WARN,IMP_GONE,impHasWarn,impHasGone,impManSS,impManSP,impMerge,impDemoAp,pushTrail,hasT,clearImp:()=>{Object.keys(IMP_WARN).forEach(k=>delete IMP_WARN[k]);Object.keys(IMP_GONE).forEach(k=>delete IMP_GONE[k]);},ntHasFlow,ntHasLink,ntActCell,'
  + 'ntLive,ntVoid,ntVoidJoint,ntPayCand,ntLiveRows,ntArchTag,ntArchCls,ntHit,fNtState:()=>fNt,paidOf,debts};';
try { vm.runInContext(js + EXPORT, ctx, { filename: 'app.js' }); }
catch (e) { console.log('RUN FAIL:', e.message); process.exit(1); }
const X = ctx.__X, V = X.V, ACT = X.ACT;
/* ⭐ 加载后的**初始值快照**：任何交互路径跑完就再也看不出"默认值"了
   （实测教训：付款流水的默认月若写成「全部月份」，交互路径里的 `flReset` 会把它改回当月 ⇒ 断言假绿）。
   凡"默认值"类断言，一律比对这个快照，不要比运行时现况。 */
const FLF0 = X.flf.ym;
/* MOD-12 差异登记的筛选**默认值快照**（默认 = 全部 / 全部，等于"加筛选之前"的行为）——
   ⚠️ 交互路径里有 `dfFilter` / `mpPick(scope=df)`，跑一遍就再也看不出默认值了（与 `FLF0` / `PSTG0` 同款）。 */
const DFF0 = JSON.parse(JSON.stringify(X.dfState().f));
/* ⭐ 同理：**默认值 / 缺省态**一律在"任何交互发生前"取快照 —— 交互路径里有 procTab/procPj 的动作，
   跑完之后就再也看不出"进页面默认停在哪张表"了。 */
const PROCTAB0 = X.procState().tab;
const PROCPJ0 = X.procState().pj;
/* ⭐ 同理：MOD-07 收发结存的**默认核算年月**也要在任何交互前取快照（交互路径里有切月 + 重置）。 */
const FWHY0 = X.whYmState();
/* ⭐ 同上：焊材/气体提取的**默认项目状态**（交互路径里有 fExtStatus/fExtReset ⇒ 跑过就看不出来了）。 */
const FEXT0 = X.extState().status;
/* ⭐ 同上：集采台账「三态标记」的**默认值**（2026-09-13 用户口径 = 「纳入台账」）—— 交互路径里有 `jcFilter`/`jcReset`。 */
const FJCTAG0 = X.fJc.tag;
/* ⭐ 同上：**付款统计的默认粒度**（2026-09-13 用户口径 = 「按周」）—— 交互路径里有 `pstGran`，跑过就看不出来。 */
const PSTG0 = X.pst.gran;

let pass = 0, fail = 0;
const ck = (name, got, exp, tol = 0.005) => {
  const ok = Math.abs(got - exp) < tol; ok ? pass++ : fail++;
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}: ${Number(got).toFixed(2)}${ok ? '' : '  (expect ' + Number(exp).toFixed(2) + ')'}`);
};
const guard = (name, fn) => { try { fn(); pass++; console.log(`PASS  ${name}`); } catch (e) { fail++; console.log(`FAIL  ${name}: ${e.message}`); } };
/* 按 `data-sort-key` **圈定某一张表**再断言 —— 别数整个页面的 <th>：
   那样「往页里加任何一张表」都会把它误判成红（实测过），而误报会训练出「改数字让它变绿」的坏习惯。 */
const _tblByKey = (html, key) => (String(html).match(new RegExp('<table\\b[^>]*data-sort-key="' + key + '"[\\s\\S]*?</table>')) || [''])[0];
const _thCountOf = (html, key) => (_tblByKey(html, key).match(/<th\b/g) || []).length;


console.log('=== 1. 业务口径自检（加载后立即校验） ===');
ck('收发结存行数合计（8 仓）', X.sums(X.WHs, 'rows'), 675);
ck('焊材提取合计', X.EXTRACT['焊材'].reduce((a, x) => a + x[1], 0), 83306.25);
ck('气体提取合计', X.EXTRACT['气体'].reduce((a, x) => a + x[1], 0), 45428.89);
const d0 = X.debts();
ck('辅材欠款（Σ辅材统计结算 − Σ辅材统计付款 ＋ 辅材期初 130,000；含 2 条「油卡下调统计结算」样本：N02 −4200.50 / A17 −2000）', d0['辅材'], 521199.50);
ck('机械欠款（**派生**结算 534,500 = Σ外租零租含税＋外租包月含税 − Σ机械统计付款 449,500 ＋ 机械期初 96,000）', d0['机械'], 181000.00);
ck('集采欠款（合同级）', d0['集采'], 3697000.00);
ck('期初占位已按分类并入辅材 / 机械（不再单列；辅材期初 130,000 + 机械期初 96,000 = 226,000）',
  d0['lg辅材'] + d0['lg机械'], 226000.00);
ck('欠款合计', d0['合计'], 4399199.50);
ck('过程资料列数 = 17', X.IVC5.length * 2 + 6 + 1, 17);
const PJ_DZ = '华能德州热电联产项目#2机组建筑及安装工程';        /* 项目全名（活动大表 / dispCell 用） */
const WH_DZ = '华能德州热电联产项目仓库';                          /* ★ 仓库名 = 项目候选键（§2.7.4） */
const WH_LY = '临沂钢铁余热发电项目仓库';
ck('过程资料·德州 原始入库主辅材（**全月合计** 2026-05~08）', X.procAgg(WH_DZ, false).inC['主辅材'], 90112.00);
ck('过程资料·德州 调整后入库主辅材（**全月合计**）', X.procAgg(WH_DZ, true).inC['主辅材'], 89892.00);
ck('N01 已付金额（流水汇总）', X.paidOf('N01'), 128600.00);
ck('N01 已付 128600 ≥ 审批 128600 → 已付清', X.statOf(X.NO.find(n => n.id === 'N01')) === '已付清' ? 1 : 0, 1);
ck('N02 已付 82000 < 审批 84200.50 → 未付清（按旧基准会误判为已付清）', X.statOf(X.NO.find(n => n.id === 'N02')) === '未付清' ? 1 : 0, 1);
ck('A21 全额付清 → 已付清', X.statOf(X.NO.find(n => n.id === 'A21')) === '已付清' ? 1 : 0, 1);
const A17x = X.NO.find(n => n.id === 'A17');
ck('「统计结算 < 审批金额」样本存在（A17 油卡下调 2000）', A17x.ss - A17x.approve, -2000.00);
ck('A17 统计结算 25800 已手改且有留痕', X.hasT(A17x, '统计结算金额') ? 1 : 0, 1);
ck('全库不存在「统计结算金额 > 审批金额」的行（口径：只能少不能多）',
  X.NO.every(n => n.excl || n.ss <= n.approve + 0.005) ? 1 : 0, 1);
ck('全库不存在「统计付款金额 > 审批金额」的行',
  X.NO.every(n => n.excl || n.sp <= n.approve + 0.005) ? 1 : 0, 1);
ck('剔除记录不计入欠款（ss/sp 均为 0）', X.NO.filter(n => n.excl).every(n => !n.ss && !n.sp) ? 0 : 1, 0);
ck('业务分类无「其他」类', X.NO.filter(n => !n.excl).every(n => ['辅材', '机械', '集采'].includes(n.cat)) ? 1 : 0, 1);
ck('【新】集采实际供应商：抓取后初始为空', X.NO.filter(n => n.cat === '集采' && !n.excl).every(n => n.sup === '') ? 1 : 0, 1);
ck('付款流水条数（含 1 条已撤销）', X.FLs.length, 17);
ck('已撤销流水 = 1 条且带原因', X.FLs.filter(f => f.voided && f.reason).length, 1);

console.log('\n=== 2. 16 个视图渲染 ===');
let vbad = 0; const keys = Object.keys(V);
for (const k of keys) { try { doc.querySelector('#view').innerHTML = V[k](); } catch (e) { vbad++; console.log(`VIEW ${k} FAIL: ${e.message}`); } }
console.log(vbad === 0 ? `PASS  全部 ${keys.length} 个视图渲染通过` : `FAIL  ${vbad} 个视图报错`); vbad === 0 ? pass++ : fail++;

/* 交互测试会改数据（预期行为）：先快照，交互跑完回滚，后续纯数据断言才能在干净状态上跑 */
const SNAP = JSON.stringify({ NO: X.NO, JC: X.JCs, FL: X.FLs, AD: X.ADs, PJ: X.PJs, DF: X.DFs, LG: X.LGs, IV: X.IVs, M6: X.MACH6, LNS: X.LEDNOTE, AWM: X.AWF, BV: X.BIGVAL, BX: X.BAL_EX, OW: X.OWN, US: X.USERS, PL: X.PLs, RX: X.RULE_EX, RL: X.RUNLOG });
function rollback() {
  const o = JSON.parse(SNAP);
  const put = (arr, src) => { arr.length = 0; src.forEach(v => arr.push(v)); };
  put(X.NO, o.NO); put(X.JCs, o.JC); put(X.FLs, o.FL); put(X.ADs, o.AD); put(X.PJs, o.PJ);
  put(X.DFs, o.DF); put(X.LGs, o.LG); put(X.IVs, o.IV);
  /* 运行记录（看板 ⑦⑬⑭ 的数据源）：**本原型里没有任何交互会写它**，但第 10f 组会临时改一条做探针
     ⇒ 一并纳入快照，保证"忘了复位"也不会污染后续断言 */
  put(X.RUNLOG, o.RL);
  /* MACH6 是「仓库名 → 月 → 6 列」的两层结构，同样原地逐层复位（保引用） */
  Object.keys(X.MACH6).forEach(k => delete X.MACH6[k]);
  Object.keys(o.M6).forEach(k => { X.MACH6[k] = {}; Object.keys(o.M6[k]).forEach(y => X.MACH6[k][y] = o.M6[k][y]); });
  /* LEDNOTE：逐月台账备注（口径|项目|月 → 文本），清空再赋值 */
  Object.keys(X.LEDNOTE).forEach(k => delete X.LEDNOTE[k]); Object.assign(X.LEDNOTE, o.LNS);
  /* 台账选中项目 / 期初截止年月：两个原始值，走导出进来的 setLed 复位 */
  X.setLed({ proj: '', cut: X.bjMonth(-1) });
  if (X.ledPjOpenState && X.ledPjOpenState()) X.ACT.ledPjToggle({ dataset: {}, tagName: 'BUTTON' });   /* 面板收起 */
  X.setLgPjName('');                       /* 期初展开区选中的项目键（仓库名；进入增行态时会重算，这里只求干净） */
  X.setLgX({ on: false, open: false });    /* 期初**增行态**开关与「项目」面板展开态（原始值，走导出进来的 setter 复位） */
  X.setJcNew({ on: false, open: false });  /* 集采「手工新增合同」的增行态开关与面板展开态（同理，原始值） */
  X.setJcSub({ kind: '', id: '', d: { date: '', amt: '' } });   /* 集采三张子表的**增行草稿**（同上，原始值 —— 交互路径会进增行态） */
  X.setFetch({ kind: 'nt', m: X.bjMonth() });   /* 抓取目标与抓取月份（原始值）—— 交互路径会开三个抓取弹窗并改月份 */
  X.setLedExp({ on: false, open: false, pjs: [] });   /* 逐月台账「导出」展开区与多选项目（原始值 + 数组原地复位） */
  X.setProcExp({ on: false, open: false, pjs: [] });  /* 过程资料「按模板导出」展开区（同上） */
  X.pst.gran = PSTG0; X.pst.ym = '';                  /* 付款统计粒度（默认「按周」）与桶 —— 交互路径里有 pstGran */
  X.setNa({ d: {}, id: '' });              /* 手动新增弹窗的草稿层 / 编辑目标（同上） */
  X.setPlRow({ id: '', d: {} });           /* MOD-04 **手动行的增行态 / 草稿层**（§4.3.3.1）—— 交互路径会进增行态并落库 */
  /* MOD-12 差异登记的**增行态 / 草稿层 / 两个筛选**（原始值 + 对象原地复位；交互路径会登记 / 筛选 / 删除） */
  X.setDf({ on: false, d: {}, f: { ym: '全部', stat: '全部' } });
  /* OWN（归属：单据id → 档案id）是「一行一条」的映射，同样原地清空再赋值，保引用不变 */
  Object.keys(X.OWN).forEach(k => delete X.OWN[k]); Object.assign(X.OWN, o.OW);
  /* USERS 是数组：与 NO/PJs 同法，清空再逐个 push（保引用） */
  X.USERS.length = 0; o.US.forEach(v => X.USERS.push(v));
  X.PLs.length = 0; o.PL.forEach(v => X.PLs.push(v));
  X.CUR.role = 'admin';   /* 「转让管理员」会改当前登录角色 —— 用原地改字段复位（引用不变） */
  /* AWF（MOD-09 手填项）自 2026-09-13 起是「**核算年月 → 项目键 → [[项名,金额],…]**」**三层结构**
     （按「核算年月 ＋ 项目」各存一份）⇒ 与 MACH6 同法：**原地逐层清空再赋值**（保对象引用不变）。
     ⚠️ 这一处是**改结构时最易漏**的地方：三层漏一层 = 静默污染后续断言。 */
  Object.keys(X.AWF).forEach(k => delete X.AWF[k]);
  Object.keys(o.AWM).forEach(k => {
    X.AWF[k] = {};
    Object.keys(o.AWM[k]).forEach(p => { X.AWF[k][p] = o.AWM[k][p].map(r => r.slice()); });
  });
  /* RULE_EX（MOD-14 剔除规则）自 2026-09-13 起**可增删改**（`const` → `let`）⇒ 必须进快照并原地复位（保引用） */
  put(X.RULE_EX, o.RX);
  /* BIGVAL 是「月 → 项目全名 → 7 个手填值」的两层结构，需原地逐层复位（保持对象引用不变） */
  Object.keys(X.BIGVAL).forEach(k => delete X.BIGVAL[k]);
  Object.keys(o.BV).forEach(k => { X.BIGVAL[k] = {}; Object.keys(o.BV[k]).forEach(p => X.BIGVAL[k][p] = o.BV[k][p].slice()); });
  /* BAL_EX（提取表「结余」手工录入值）是「类别 → 仓库 → 金额」**两层**结构 ⇒ 同法原地逐层复位（保引用）。
     ⚠️ 它自 2026-09-18（用户裁定「甲」）起可增删改（点格即改 / 清空删键）⇒ 必须进快照，否则污染后续断言。 */
  Object.keys(X.BAL_EX).forEach(k => delete X.BAL_EX[k]);
  Object.keys(o.BX).forEach(k => { X.BAL_EX[k] = {}; Object.keys(o.BX[k]).forEach(p => X.BAL_EX[k][p] = o.BX[k][p]); });
  /* SORT 排序状态：默认「无排序」即基线，直接清空即可复位 */
  Object.keys(X.SORT).forEach(k => delete X.SORT[k]);
  /* 集采三态「批量标记」的勾选集合：清空即回到基线（Set 原地 clear，保引用） */
  X.jcPick.clear();
  /* 大表的项目集合与顺序（`BIGSET`）：顶层数组，原地复位为「全部候选」 */
  X.BIGSET.length = 0; X.bigCands().forEach(k => X.BIGSET.push(k));
  /* 集采供应商自动匹配（§6.6.3）的**待确认标记**：id → 预填值，明面对象，清空即回基线 */
  X.clearSup();
  X.setSupSel(null);
  /* 再次导入的合并（§4.2.7）的两个明面表：导入提醒 / i8 已撤单 —— 清空即回基线 */
  X.clearImp();
}
/* fNt / fPj / fJc 是模块私有对象，但导出的是引用，可原地复位；fIvDir / fWhYm 是原始值，走各自的重置动作 */
function resetF() {
  X.fNt.month = '2026-09'; X.fNt.cat = '全部'; X.fNt.astat = '全部'; X.fNt.stat = '未付清'; X.fNt.projs = [];
  X.fPj.status = '在建'; X.fPj.type = '全部'; X.fPj.q = '';
  X.fJc.tag = '纳入台账'; X.fJc.arch = '全部'; X.fJc.sup = '';   /* 「三态标记」默认 = 纳入台账（2026-09-13 用户口径） */
  X.fJc.projs.length = 0;                          /* 「项目」筛选也复位（原地清空，不换数组引用） */
  if (X.jcPjState()) X.ACT.jcPjToggle({ dataset: {}, tagName: 'BUTTON' });   /* 面板收起 */
  X.ACT.fIvReset({ dataset: {}, tagName: 'BUTTON' });
  X.ACT.whReset({ dataset: {}, tagName: 'BUTTON' });
  X.ACT.fExtReset({ dataset: {}, tagName: 'BUTTON' });
  /* MOD-09 的「核算年月 ＋ 项目」（`awfYm` / `awfPj` 都是原始值）—— 走本页**自己的重置动作**复位
     （它同时把 `awfPjOpen` 收起；原始值无法从外部原地改，只能走动作） */
  X.ACT.awfReset({ dataset: {}, tagName: 'BUTTON' });
  /* 大表的**项目集合与顺序**（`BIGSET`）也是顶层数组 ⇒ 原地复位为「全部候选」 */
  X.BIGSET.length = 0; X.bigCands().forEach(k => X.BIGSET.push(k));
  /* 付款流水的筛选（含「付款项目」多选与 `flPjOpen` 展开态）—— 走本页**自己的重置动作** */
  X.ACT.flReset({ dataset: {}, tagName: 'BUTTON' });
  /* MOD-12 差异登记：增行态 / 草稿层 / 两个筛选（`dfReset` 是它自己的重置动作，一并把面板收起） */
  X.setDf({ on: false, d: {}, f: { ym: '全部', stat: '全部' } });
}

console.log('\n=== 3. 交互处理器（真实 ID 驱动） ===');
doc.querySelector('#rReason').value = '';
const cases = [
  ['editss', { id: 'N08', k: 'ss', value: '50000' }], ['editss', { id: 'N08', k: 'pay', value: '30000' }], ['batchPay'], ['revDlg', { fid: 'F2' }],
  ['force', { id: 'PL02' }], ['editFull', { id: 'P01', value: '改名测试' }], ['editStatus', { id: 'P01', value: '归档' }],
  ['editKw', { id: 'P08' }], ['promote', { id: 'P12' }], ['delPj', { id: 'P01' }], ['adjDlg', { iv: 'V01' }],
  ['awfName', { i: '0', value: '油卡使用' }], ['awfAmt', { i: '0', value: '86200' }], ['awfAdd'], ['awfDel', { i: '1' }],
  /* 2026-09-13：MOD-09 加「项目」单选面板 —— 切走再切回（覆盖 toggle + pick 两个动作） */
  ['awfPjToggle'], ['awfPjPick', { pj: WH_LY }], ['awfPjPick', { pj: WH_DZ }],
  ['ledPjPick', { pj: WH_DZ }],
  /* 2026-09-13：逐月账单导出改「一个入口 + 多选项目 + 每项目一簿三表」（两栏内的 expLed 已删） */
  ['ledExpToggle'], ['ledExpPjToggle'], ['ledExpPjPick', { pj: WH_DZ }], ['ledExpPjAll'], ['ledExpPjNone'],
  ['ledExpPjPick', { pj: WH_DZ }], ['ledExpOk'], ['closeModal'], ['ledExpCancel'],
  /* 2026-09-13：过程资料「按模板导出」改多选项目（每项目一份 · ≥2 打 zip） */
  ['procExpToggle'], ['procExpPjToggle'], ['procExpPjPick', { pj: WH_DZ }], ['procExpPjAll'], ['procExpPjNone'],
  ['procExpPjPick', { pj: WH_DZ }], ['procExpOk'], ['closeModal'], ['procExpCancel'],
  /* 2026-09-13：库存单据明细「额外一份含数据透视表」的导出 */
  ['expPivot'],
  ['ledNote', { sc: '辅材', proj: WH_DZ, m: '2026-07', value: '已核' }],
  ['dfOk', { id: 'DF01' }],
  /* 2026-09-13 深夜：MOD-12 差异登记补「手工新建 / 删除 / 筛选」—— 覆盖 增行 / 录入 / 取消 / 删除 / 状态筛选 / 重置 / 核算月面板 */
  ['dfAdd'], ['dfSet', { k: 'detail', value: '交互路径探针差异' }], ['dfSet', { k: 'amount', value: '-123.45' }],
  ['dfSet', { k: 'status', value: '差异保留' }], ['dfCancel'],
  ['dfFilter', { value: '待核对' }], ['dfReset'],
  ['mpPick', { id: 'dfMonth', scope: 'df', val: '2026-08' }], ['dfDel', { id: 'DF01' }], ['dfReset'],
  ['editSup', { id: 'N15', value: '测试供应商' }],
  ['jcTag', { id: 'J10', v: '纳入台账' }], ['jcArch', { id: 'J04' }],
  /* 2026-09-13：三张子表录入改**表内增行**（`jcSubAdd/Set/Save/Cancel`）—— 覆盖 贸易公司发票 / 供应商发票 / 付款 三条线 */
  ['jcSubAdd', { id: 'J03', kind: 'tinv' }], ['jcSubSet', { k: 'date', value: '2026-09-13' }], ['jcSubSet', { k: 'amt', value: '1000' }], ['jcSubSave'],
  ['jcTInvDel', { id: 'J03', i: '0' }],
  ['jcMethod', { id: 'J01', value: '60±7天承兑' }], ['jcInvDlg', { id: 'J03' }], ['jcTInvDlg', { id: 'J03' }], ['jcPayDlg', { id: 'J03' }],
  /* 供应商发票：先验「日期没填 → 保存被拦」，补齐日期后才落库；再加一行后取消（草稿不入库） */
  ['jcSubAdd', { id: 'J01', kind: 'inv' }], ['jcSubSet', { k: 'amt', value: '1000' }], ['jcSubSave'],
  ['jcSubSet', { k: 'date', value: '2026-09-13' }], ['jcSubSet', { k: 'amt', value: '1000' }], ['jcSubSave'],
  ['jcSubAdd', { id: 'J01', kind: 'inv' }], ['jcSubCancel'],
  ['jcInvDel', { id: 'J01', i: '0' }],
  ['jcSubAdd', { id: 'J01', kind: 'pay' }], ['jcSubSet', { k: 'amt', value: '1000' }], ['jcSubSave'], ['jcPayDel', { id: 'J01', i: '0' }],
  ['jcPayRef', { id: 'J01' }], ['jcFetch'], ['jcAdd'],
  /* 2026-09-13 增行模式：集采「手工新增合同」→ 展开区（项目走共用面板单选）+ **真的建档** + 取消 */
  ['jcNPjToggle'], ['jcNPjPick', { pj: WH_DZ }], ['jcNSet', { k: 'material', value: '交互路径探针' }],
  ['jcNSet', { k: 'contractAmt', value: '1000' }], ['jcRowSave'], ['jcAdd'], ['jcRowCancel'],
  /* 2026-09-13 新增：合同收发登记三列可手改 + 「项目」筛选（通用控件） */
  ['jcArchNo', { id: 'J01', value: 'JD-2026-TEST' }], ['jcRetDate', { id: 'J01', value: '2026-09-01' }], ['jcRemark', { id: 'J01', value: '测试备注' }],
  ['jcPjToggle'], ['jcPjPick', { pj: WH_DZ }], ['jcPjAll'], ['jcPjNone'],
  ['procPjToggle'], ['procPjPick', { pj: WH_LY }], ['procTab', { i: '2' }],
  ['invWhToggle'], ['invWh', { pj: WH_DZ }], ['invOnlyAdj', { value: '1' }], ['clearInvAdj'],
  /* 2026-09-13：MOD-08「项目」多选 + 「每列可筛」（Excel 式）*/
  ['invWhAll'], ['invWhNone'], ['invWh', { pj: WH_DZ }],
  ['ivColOpen', { c: '2' }], ['ivColVal', { c: '2', v: '入库' }], ['ivColQ', { c: '3', value: '钢' }],
  ['ivColMin', { c: '9', value: '1000' }], ['ivColMax', { c: '9', value: '99999999' }],
  ['ivColClear', { c: '2' }], ['ivColClose'], ['ivColClearAll'],
  ['goInvAdj', { wh: '华能德州热电联产项目仓库', iv: 'V01' }],
  ['zipSfjc'], ['fetchNt'], ['fetchOne', { t: '付款通知书' }], ['manualUp', { t: '付款通知书' }],
  ['batchUnEx'], ['syncWh'], ['syncPj'], ['addLg'], ['delLg', { id: 'LG01' }], ['delLgOk', { id: 'LG01' }], ['ruleAdd'], ['silent2'],
  ['delDemo'], ['delOk'], ['exp', { t: '付款通知书台账' }], ['batchPayOk'], ['revOk', { fid: 'F2' }],
  ['forceOk', { id: 'PL02' }], ['adjOk', { iv: 'V01' }], ['addLgOk'], ['editKwOk', { id: 'P08' }], ['promoteOk', { id: 'P12' }],
  ['jcPayRefOk', { id: 'J01' }], ['planPick'], ['filterNt'], ['jcFilter'], ['closeModal'], ['pickAll', { checked: true }],
  ['pick', { id: 'N01', checked: true }], ['ntPrint'], ['batchCatApply', { c: '机械' }], ['batchEx'],
  /* 本次新增 / 重做的交互 */
  ['editCat', { id: 'N03', value: '机械' }], ['editDisp', { id: 'P04', value: '新展示名' }],
  ['batchCatApply'], ['pjToggle'], ['pjAll'], ['pjPick', { pj: '第四工程公司2026小微项目' }], ['pjNone'],
  ['plPjPick', { pj: WH_DZ }], ['plPjPick', { pj: WH_DZ }],
  ['mpToggle', { id: 'ntMonth', scope: 'nt', val: '2026-09' }], ['mpYear', { id: 'ntMonth', scope: 'nt', val: '2026', d: '1' }],
  ['mpPick', { id: 'ntMonth', scope: 'nt', val: '2026-08' }], ['mpClose'],
  /* 本次新增：MOD-01 / MOD-08 / MOD-11 筛选器真正生效（R4 即时生效 + 重置） */
  ['fPjStatus', { value: '归档' }], ['fPjType', { value: '普通项目' }], ['fPjQ', { value: '德州' }], ['fPjReset'],
  ['fIvDir', { value: '入库' }], ['fIvReset'], ['jcReset'],
  /* 本次新增：MOD-07 活动大表手填录入（OPEN-05「上次值带入」） */
  ['bigEdit', { p: PJ_DZ, i: '0', value: '96000' }], ['bigEdit', { p: PJ_DZ, i: '3', value: '88.88' }],
  /* 本次新增：表头点击排序 */
  ['headSort', { tk: 'm03:notices', i: '10' }], ['headSort', { tk: 'm03:notices', i: '10' }],
  /* 本次新增：批量付款删除行 / 按月抓取 */
  ['batchPayDel', { id: 'N05' }], ['fetchNt'], ['fetchNtOk'], ['mpRefresh', { scope: 'nt' }],
  /* 2026-09-13：收发结存表 / 库存单据明细表的抓取也走「按月抓取」（默认 = 本页所选核算年月） */
  ['fetchWh'], ['fetchNtOk'], ['closeModal'], ['fetchIv'], ['fetchNtOk'], ['closeModal'],
  ['go', { k: 'm06' }], ['silent'],
  /* 本次新增：MOD-11 集采三态「批量标记」（§6.5.3） */
  ['jcPick', { id: 'J10' }], ['jcBatchTag', { v: '纳入台账' }], ['jcPickAll'], ['jcBatchTag', { v: '待确认' }],
  /* 本次新增：MOD-04 逐行删除 / 取消强制通过 / 行内可改列 / 再次匹配（2026-09-12） */
  ['forceOk', { id: 'PL05' }], ['unforce', { id: 'PL05' }],
  ['plCell', { id: 'PL02', f: 'remark', value: '行内备注' }], ['plCell', { id: 'PL02', f: 'date', value: '2026-09-29' }],
  ['plCell', { id: 'PL02', f: 'method', value: '承兑' }], ['plCell', { id: 'PL14', f: 'docNo', value: 'BZLL-202607-04' }],
  ['plRematch', { id: 'PL14' }], ['plDelRow', { id: 'PL13' }], ['plDelRowOk', { id: 'PL13' }],
  /* 本次新增：按付款计划勾选的窗口（10 号 → 月末）—— 抓取/勾选月固定为北京时间当月 */
  ['mpPick', { id: 'ntMonth', scope: 'nt', val: '全部' }],
  /* 2026-09-13 增行模式：MOD-03 手动新增 / 编辑 / 删除付款通知书（**弹窗已取消 → 表内增行**） */
  ['ntRowAdd'], ['ntRowSet', { k: 'date', value: '2026-09-05' }], ['ntRowSet', { k: 'code', value: 'SD-TEST-01' }],
  ['ntRowSet', { k: 'doc', value: '付期初欠款' }], ['ntRowSet', { k: 'approve', value: '5000' }],
  ['ntRowSet', { k: 'sp', value: '5000' }], ['ntRowSet', { k: 'cat', value: '机械' }], ['ntRowSet', { k: 'cat', value: '辅材' }],
  ['ntRowSave'], ['ntEdit', { id: 'MN01' }], ['ntRowSet', { k: 'biz', value: '行内改业务类型' }],
  ['ntRowCancel'], ['ntRowAdd'], ['ntRowCancel'],
  /* 2026-09-16 新增：MOD-04 **手动行**（表内增行 · §4.3.3.1 · 用户口述新增）—— 新增 / 逐格填 / 保存 / 编辑 / 取消 */
  ['plRowAdd'], ['plRowSet', { k: 'ym', value: '2026-09' }], ['plRowSet', { k: 'proj', value: '德州热电' }],
  ['plRowSet', { k: 'docNo', value: 'SD-PL-TEST' }], ['plRowSet', { k: 'flowAmt', value: '1000' }],
  ['plRowSet', { k: 'monthAmt', value: '1000' }], ['plRowSet', { k: 'remark', value: '手工补录' }], ['plRowSave'],
  ['plRowEdit', { id: 'PL15' }], ['plRowSet', { k: 'remark', value: '编辑中改备注' }], ['plRowCancel'],
  ['plRowAdd'], ['plRowCancel'],
  ['editApprove', { id: 'MN01', value: '6000' }], ['ntDel', { id: 'MN01' }], ['ntDelOk', { id: 'MN01' }],
  ['lgPjToggle'], ['lgPjPick', { pj: WH_LY }], ['lgPjToggle'], ['lgCancel'],
  /* 本次新增：项目档案自定义排序（ord + ↑/↓） */
  ['editOrd', { id: 'P01', value: '3' }], ['ordUp', { id: 'P01' }], ['ordDown', { id: 'P01' }],
  /* 本次新增：MOD-05 付款流水筛选 + 付款统计（2026-09-13）—— 末尾用 flReset 把筛选状态复原，避免污染后续断言 */
  ['flFilter'], ['flSearch'], ['pstGran', { g: '周' }], ['pstGran', { g: '月' }],
  /* 2026-09-13：付款流水的「付款项目」改用**共用面板（多选）** —— 覆盖 开/选/全选/清空/收起 */
  ['flPjToggle'], ['flPjPick', { pj: WH_DZ }], ['flPjAll'], ['flPjNone'], ['flPjToggle'],
  ['pstPj', { pj: WH_DZ }], ['lgS', { value: '111.11' }], ['lgP', { value: '222.22' }], ['lgR', { value: '探针备注' }],
  /* 本次新增：通用时间选择器（2026-09-13）—— 面板内切模式 / 换季度 */
  ['mpMode', { id: 'ntMonth', scope: 'nt', val: '2026-09', m: '年' }], ['mpMode', { id: 'ntMonth', scope: 'nt', val: '2026-09', m: '月' }],
  ['mpWQ', { id: 'ntMonth', scope: 'nt', val: '2026-09', qy: '2026', qq: '3' }],
  /* 第 2 批：付款统计的桶 / 轴（新作用域 pstb / psta；末尾把桶复位到最新数据月，免得污染后续断言） */
  ['mpPick', { id: 'pstBucket', scope: 'pstb', val: '2026-07' }],
  ['mpPick', { id: 'pstAxis', scope: 'psta', val: '2026Q2' }],
  ['mpPick', { id: 'pstAxis', scope: 'psta', val: '2026' }],
  ['mpPick', { id: 'pstBucket', scope: 'pstb', val: '2026-09' }],
  /* 2026-09-13 P4–P6 裁定落地：MOD-14 剔除规则真增删改 · MOD-08「核算年月」 · MOD-12 差异金额带符号 */
  ['ruleAdd'], ['ruleEdit', { i: '0' }], ['ruleSave', { i: '0' }], ['ruleDel', { i: '1' }],
  ['mpPick', { id: 'ivMonth', scope: 'iv', val: '2026-07' }],
  ['mpPick', { id: 'ivMonth', scope: 'iv', val: '全部' }],
  ['fIvReset'], ['closeModal'],
  /* 2026-09-13 裁定⑤·甲：MOD-09 手填项按月各存一份（默认上月） */
  ['mpPick', { id: 'awfMonth', scope: 'awf', val: '2026-06' }],
  ['mpPick', { id: 'awfMonth', scope: 'awf', val: '2026-05' }],
  ['awfAdd'], ['awfReset'],
  /* 2026-09-13：MOD-07 收发结存「核算年月」（默认 = 北京时间上月）—— 末尾 whReset 复位，免得污染后续断言 */
  ['mpPick', { id: 'whMonth', scope: 'wh', val: '2026-06' }],
  ['mpPick', { id: 'whMonth', scope: 'wh', val: '2026-07' }],
  ['whReset'],
  /* 2026-09-13：MOD-07 焊材/气体提取（核对工具）—— 项目状态 / 金额月份 / 导出矩阵 */
  ['fExtStatus', { value: '全部' }], ['fExtStatus', { value: '归档' }],
  ['mpPick', { id: 'extMonth', scope: 'ext', val: '2026-06' }],
  ['mpPick', { id: 'extMonth', scope: 'ext', val: '2026' }],
  ['expExt'], ['closeModal'], ['fExtReset'],
  /* 2026-09-18（用户裁定「甲」）：提取表「结余」列 —— 点格即改（change 类动作，必须进 `CHG`） */
  ['extBal', { k: '焊材', p: WH_LY, value: '1234.50' }], ['extBal', { k: '焊材', p: WH_LY, value: '' }],
  /* 2026-09-13：活动大表「选题」（多选 + 自定义顺序）—— 跑完由 `resetF` 把 BIGSET 复位为全部候选 */
  ['bigPick'], ['bigSelTog', { wh: WH_LY }], ['bigSelUp', { wh: WH_LY }], ['bigSelDown', { wh: WH_LY }], ['bigPickOk'],
  ['bigPick'], ['bigSelNone'], ['bigPickOk'],
  /* 2026-09-13 批 A：付款通知书「集采行」→ 关联集采合同（反向入口）—— 开弹窗 / 换选择 / 关联 / 解绑 */
  /* ⚠️ 2026-09-13：候选已**限定为本项目** ⇒ 交互路径也要选**本行项目下的**合同（N16 = 临沂 → J02） */
  ['jcLink', { id: 'N16' }], ['jcLinkPick', { id: 'N16', value: 'J02' }],
  ['jcLinkOk', { id: 'N16' }], ['jcUnlink', { id: 'N16' }], ['closeModal'],
  ['flReset'],
  /* 2026-09-13 第7条：项目档案「确认删除」**真删**（配置类硬删 §9.4）—— 放末尾，`rollback()` 会复原 PJs */
  ['delPjOk', { id: 'P01' }]
];
let hbad = 0;
for (const [a, ds] of cases) {
  if (!ACT[a]) { console.log(`ACT ${a} MISSING`); hbad++; continue; }
  try { ACT[a]({ dataset: ds || {}, tagName: 'BUTTON', value: (ds && ds.value) || '1000', checked: true }); }
  catch (e) { hbad++; console.log(`ACT ${a} FAIL: ${e.message}`); }
}
console.log(hbad === 0 ? `PASS  全部 ${cases.length} 个交互路径无异常` : `FAIL  ${hbad}/${cases.length} 个交互路径报错`);
hbad === 0 ? pass++ : fail++;
rollback();
resetF();   /* ⭐ 交互路径会留下**筛选状态**（年月 / 方向 / 列筛选 / 面板展开态）—— `rollback()` 只管数据、
               不管筛选 ⇒ 不复位就会污染后面的断言（2026-09-13 实测过同类静默污染）。 */
ACT.pickAll({ tagName: 'INPUT', checked: false });
ck('交互测试后数据已回滚到基线（欠款合计）', X.debts()['合计'], 4399199.50);

console.log('\n=== 4. 防御性校验与本次修订（应被拦截 / 不应抛错） ===');
const pick = (id) => ACT.pick({ dataset: { id }, tagName: 'INPUT', checked: true });
/* 注意：全选/取消全选只作用于【当前筛选结果】，所以测试里的「彻底清空」要直接操作集合 */
const clearPick = () => X.pickSet.clear();

guard('【回归】非法金额被拒绝且原值不变（统计结算金额）', () => {
  const b = X.NO.find(n => n.id === 'N01').ss;
  ACT.editss({ dataset: { id: 'N01', k: 'ss' }, value: 'abc', tagName: 'INPUT' });
  const a = X.NO.find(n => n.id === 'N01').ss;
  if (a !== b) throw new Error(`金额被静默改动：${b} → ${a}`);
});
guard('【回归】机械费结算金额**没有手填入口**（口径：派生只读 ⇒ 不存在 ledSettle 动作）', () => {
  /* ⚠️ 2026-09-26（`#2`）：原先还有半句「也不在 `CHG` 里」——`CHG` 名单已整份删除，
     那句没有主人了；**能证伪的那半句（动作不存在）保留**，判据强度不降。 */
  if (typeof ACT.ledSettle === 'function') throw new Error('ledSettle 动作仍存在 —— 机械结算不该可手填');
});
guard('【回归】非法金额被拒绝且原值不变（集采付款·子表**增行**录入）', () => {
  const b = X.jcPay(X.JCs.find(x => x.id === 'J02'));
  ACT.jcSubAdd({ dataset: { id: 'J02', kind: 'pay' }, tagName: 'BUTTON' });
  ACT.jcSubSet({ dataset: { k: 'date' }, value: '2026-09-13', tagName: 'INPUT' });
  ACT.jcSubSet({ dataset: { k: 'amt' }, value: 'abc', tagName: 'INPUT' });   /* 非法金额 ⇒ 唯一出口 badMoney 拦下 */
  ACT.jcSubSave({ dataset: {}, tagName: 'BUTTON' });
  X.setJcSub({ kind: '', id: '', d: { date: '', amt: '' } });                /* 收尾：退出增行态，别留脏 */
  if (X.jcPay(X.JCs.find(x => x.id === 'J02')) !== b) throw new Error('金额被静默改动');
});
guard('【回归】特殊费用月报表手填金额：非法被拒绝且原值不变', () => {
  const b = X.awfList()[0][1]; ACT.awfAmt({ dataset: { i: '0' }, value: 'oops', tagName: 'INPUT' });
  if (X.awfList()[0][1] !== b) throw new Error('金额被静默改动');
});
guard('撤销：空原因被拦截', () => {
  doc.querySelector('#rReason').value = '';
  ACT.revOk({ dataset: { fid: 'F1' }, tagName: 'BUTTON' });
  if (X.FLs.find(f => f.id === 'F1').voided) throw new Error('空原因却撤销成功');
});
guard('批量付款：空勾选被拦截（不产生流水）', () => {
  clearPick(); const b = X.FLs.length;
  ACT.batchPayOk({ dataset: {}, tagName: 'BUTTON' });
  if (X.FLs.length !== b) throw new Error('空勾选却产生了流水');
});
guard('批量付款：超付被拦截，整批不产生流水', () => {
  clearPick(); pick('N05'); const b = X.FLs.length;
  doc.querySelector('#bm0').value = '现汇'; doc.querySelector('#ba0').value = '999999';
  doc.querySelector('#bRemark').value = ''; doc.querySelector('#bDate').value = '2026-09-12';
  ACT.batchPayOk({ dataset: {}, tagName: 'BUTTON' });
  clearPick();
  if (X.FLs.length !== b) throw new Error('超付却产生了付款流水');
});
guard('批量付款：未审批的行不可付（被拦截）', () => {
  clearPick(); pick('N09'); const b = X.FLs.length;   // N09 审批状态 = 未批
  doc.querySelector('#bm0').value = '现汇'; doc.querySelector('#ba0').value = '1000';
  ACT.batchPayOk({ dataset: {}, tagName: 'BUTTON' });
  clearPick();
  if (X.FLs.length !== b) throw new Error('未审批却产生了付款流水');
});
guard('批量付款：单位金额非法被拦截（保留原值不改动已勾选行）', () => {
  clearPick(); pick('N05'); const b = X.FLs.length;
  doc.querySelector('#ba0').value = 'abc';
  ACT.batchPayOk({ dataset: {}, tagName: 'BUTTON' });
  clearPick();
  if (X.FLs.length !== b) throw new Error('非法金额却产生了流水');
});
guard('集采实际供应商：非集采分类不可写（被拒绝）', () => {
  const f = X.NO.find(n => n.id === 'N01');
  ACT.editSup({ dataset: { id: 'N01' }, value: '某供应商', tagName: 'INPUT' });
  if (f.sup !== '') throw new Error('非集采分类被写入：' + f.sup);
});
guard('集采实际供应商：集采分类可人工录入', () => {
  const f = X.NO.find(n => n.id === 'N15');
  ACT.editSup({ dataset: { id: 'N15' }, value: '山东钢铁集团日照有限公司', tagName: 'INPUT' });
  if (f.sup !== '山东钢铁集团日照有限公司') throw new Error('未写入：' + f.sup);
});
guard('批量改分类：勾选后一次点击即完成（无弹窗、无二次确认）', () => {
  const f = X.NO.find(n => n.id === 'N15');
  if (!f.sup) throw new Error('前置条件失败：集采供应商应先有值');
  clearPick(); pick('N15');
  const t0 = Date.now();
  ACT.batchCatApply({ dataset: { c: '辅材' }, tagName: 'BUTTON' });
  clearPick();
  if (f.cat !== '辅材') throw new Error('一次点击未生效，分类仍为 ' + f.cat);
  if (f.sup !== '') throw new Error('改成非集采后未清空「集采实际供应商」：' + f.sup);
  if (Date.now() - t0 > 50) throw new Error('耗时过长，疑似仍在等待弹窗确认');
});
guard('批量改分类：未勾选时被拦截（不改动任何行）', () => {
  clearPick();
  const snap = X.NO.map(n => n.cat);
  ACT.batchCatApply({ dataset: { c: '机械' }, tagName: 'BUTTON' });
  if (X.NO.some((n, i) => n.cat !== snap[i])) throw new Error('未勾选却改动了分类');
});
guard('批量改分类：剔除行不参与（不会被改分类）', () => {
  clearPick(); pick('X01'); pick('N01');
  ACT.batchCatApply({ dataset: { c: '机械' }, tagName: 'BUTTON' });
  clearPick();
  if (X.NO.find(n => n.id === 'X01').cat === '机械') throw new Error('剔除行被改了分类');
  if (X.NO.find(n => n.id === 'N01').cat !== '机械') throw new Error('正常行未被改分类');
});
guard('单行改分类：下拉直接生效', () => {
  const f = X.NO.find(n => n.id === 'N03');
  ACT.editCat({ dataset: { id: 'N03' }, value: '机械', tagName: 'SELECT' });
  if (f.cat !== '机械') throw new Error('未生效：' + f.cat);
});
guard('展示名：人工修改生效（不影响仓库名与项目归属；按定案「不留痕」）', () => {
  const p = X.PJs.find(x => x.id === 'P04'), t0 = X.PJ_TRAIL.length;
  ACT.editDisp({ dataset: { id: 'P04' }, value: '乌兰察布风光储（简称）', tagName: 'INPUT' });
  if (p.disp !== '乌兰察布风光储（简称）') throw new Error('未写入：' + p.disp);
  if (p.name !== '内蒙乌兰察布风光储一体化项目仓库') throw new Error('仓库名被误改');
  if (p.phid !== '3700000000002104') throw new Error('项目归属字段被误改');
  if (X.PJ_TRAIL.length !== t0) throw new Error('展示名不该产生留痕（留痕只给项目全名 / 状态）');
});
guard('付款金额：手改只做临时覆盖，且不改写 i8 原值', () => {
  const f = X.NO.find(n => n.id === 'N05'), i8 = f.pay;
  ACT.editss({ dataset: { id: 'N05', k: 'pay' }, value: '90000', tagName: 'INPUT' });
  if (X.payEff(f) !== 90000) throw new Error('覆盖未生效：' + X.payEff(f));
  if (f.pay !== i8) throw new Error(`i8 原值被改写：${i8} → ${f.pay}`);
  if (f.trail.some(t => t.field === '付款金额')) throw new Error('会话级覆盖不该留痕（定案：只有统计两金额与调整单留痕）');
});
guard('付款金额：手改不影响「统计付款金额」与欠款口径（不产生隐式副作用）', () => {
  const f = X.NO.find(n => n.id === 'N07'), sp0 = f.sp, d0 = X.debts()['合计'];
  ACT.editss({ dataset: { id: 'N07', k: 'pay' }, value: '60000', tagName: 'INPUT' });
  if (f.sp !== sp0) throw new Error(`统计付款金额被隐式改动：${sp0} → ${f.sp}`);
  if (X.debts()['合计'] !== d0) throw new Error('欠款被隐式改动');
});
guard('付款金额：模拟页面刷新后自动恢复派生默认（审批金额 − 已付金额）', () => {
  const a = X.NO.find(n => n.id === 'N05'), b = X.NO.find(n => n.id === 'N07');
  delete a.payOv; delete b.payOv;                 // 等价于刷新后重建数据
  if (X.payEff(a) !== 96400) throw new Error('N05 未恢复默认：' + X.payEff(a));
  if (X.payEff(b) !== 58700) throw new Error('N07 未恢复默认：' + X.payEff(b));
});
guard('统计结算金额：超过审批金额被拦截且保留原值', () => {
  const f = X.NO.find(n => n.id === 'N01');          // 审批 128,600
  const b = f.ss;
  ACT.editss({ dataset: { id: 'N01', k: 'ss' }, value: '200000', tagName: 'INPUT' });
  if (f.ss !== b) throw new Error(`被写入超额值：${b} → ${f.ss}`);
});
guard('统计付款金额：超过审批金额被拦截且保留原值', () => {
  const f = X.NO.find(n => n.id === 'N01');
  const b = f.sp;
  ACT.editss({ dataset: { id: 'N01', k: 'sp' }, value: '200000', tagName: 'INPUT' });
  if (f.sp !== b) throw new Error(`被写入超额值：${b} → ${f.sp}`);
});
guard('统计结算金额：往下调（少付）允许通过', () => {
  const f = X.NO.find(n => n.id === 'N09');          // 审批 35,600
  ACT.editss({ dataset: { id: 'N09', k: 'ss' }, value: '30000', tagName: 'INPUT' });
  if (f.ss !== 30000) throw new Error('合法下调被误拦：' + f.ss);
});
guard('统计字段：等于审批金额（上限本身）允许通过', () => {
  const f = X.NO.find(n => n.id === 'N09');
  ACT.editss({ dataset: { id: 'N09', k: 'ss' }, value: '35600', tagName: 'INPUT' });
  if (f.ss !== 35600) throw new Error('等于上限被误拦：' + f.ss);
});
/* ⭐ 操作人取「当前登录用户」（《说明书》§1.5.1 末行：**不再是一个写死的名字**）
   写成**行为式断言**（不去 grep 源码字面量 —— 那种黑名单写法正是 §0.7 否掉的"事故驱动 + 穷举措辞"）：
   改一次统计金额 → 断言留痕里的「改前人」= 当前登录用户；跑完把值与该条留痕**原地复位**，不留副作用。 */
guard('操作人｜统计金额手改的留痕「改前人」= 当前登录用户（§1.5.1「不再是一个写死的名字」）', () => {
  const f = X.NO.find(n => n.id === 'N01');          // 审批 128,600
  const ss0 = f.ss, n0 = f.trail.length;
  ACT.editss({ dataset: { id: 'N01', k: 'ss' }, value: '128500', tagName: 'INPUT' });
  const rec = f.trail[f.trail.length - 1];
  const okRec = f.trail.length === n0 + 1 && !!rec && rec.by === X.CUR.name;
  f.trail.length = n0; f.ss = ss0;                    // 原地复位（不留痕、不改值）
  if (!okRec) throw new Error('留痕的「改前人」不是当前登录用户：'
    + (rec ? rec.by : '(没有产生留痕)') + ' / 期望 ' + X.CUR.name);
});
guard('按付款计划勾选：只勾【当月计划】命中的行，且全部落在当前筛选结果内', () => {
  resetF(); clearPick();
  ACT.planPick({ dataset: {}, tagName: 'BUTTON' });
  if (X.pickSet.size <= 0) throw new Error('未勾选任何行');
  const ym = X.plWin().ym;
  const codes = new Set(X.PLs.filter(p => p.ym === ym).map(p => String(p.docNo || '').trim()).filter(Boolean));
  const byCode = new Set(X.NO.filter(n => codes.has(n.code)).map(n => n.id));
  if ([...X.pickSet].some(i => !byCode.has(i))) throw new Error('勾到了当月付款计划之外的行');
  const vis = new Set(X.ntHit(X.fNt).map(n => n.id));
  if ([...X.pickSet].some(i => !vis.has(i))) throw new Error('勾到了当前不可见的行');
  if (X.plWin().ym !== ym) throw new Error('勾选所用的月份不是北京时间当月');
});
guard('按付款计划勾选：跨月单据一并勾上（计划月 = 当月，命中的通知书可在上月 / 更早）', () => {
  resetF(); clearPick();
  ACT.planPick({ dataset: {}, tagName: 'BUTTON' });
  const ym = X.plWin().ym;
  const mon = new Set([...X.pickSet].map(i => X.NO.find(n => n.id === i).date.slice(0, 7)));
  if (!mon.has('2026-08') || !mon.has('2026-07')) throw new Error('跨月样本未覆盖 2026-08 / 2026-07：' + [...mon].join(','));
  if (![...mon].some(m => m !== ym)) throw new Error('没有勾到任何跨月单据');
  /* 勾选范围 = 当月计划命中的「全部月份」通知书；被剔除的不勾 */
  if ([...X.pickSet].some(i => X.NO.find(n => n.id === i).excl)) throw new Error('勾到了剔除行（不可付）');
  resetF(); clearPick();
});
guard('按付款计划勾选：窗口外按钮先禁用（付款计划 10 号生效 → 月末，§4.3.2）', () => {
  const keep = X.SYS_TODAY;
  X.setToday('2026-09-05');
  const off = X.plWin().open, h = V.m03();
  const dis = /data-act="planPick"[^>]*disabled/.test(h);
  X.setToday(keep);
  X.plWin();
  if (off) throw new Error('窗口外（5 号）不应判定为可点');
  if (!dis) throw new Error('窗口外按钮未先禁用');
  if (!X.plWin().open) throw new Error('复位后窗口应重新开放（模拟今天回到窗口内）');
});
guard('按付款计划勾选：不动「项目」筛选，勾选范围尊重已选项目', () => {
  resetF(); clearPick();
  X.fNt.projs.push(WH_DZ);                       /* 用户只选了「德州」 */
  ACT.planPick({ dataset: {}, tagName: 'BUTTON' });
  if (X.fNt.projs.length !== 1 || X.fNt.projs[0] !== WH_DZ) throw new Error('「项目」筛选被系统改动');
  if (X.pickSet.size <= 0) throw new Error('未勾选任何行');
  const bad = [...X.pickSet].filter(i => X.ntProjKey(X.NO.find(n => n.id === i)) !== WH_DZ);
  if (bad.length) throw new Error('勾到了所选项目之外的通知书：' + bad.join(','));
  resetF(); clearPick();
});
guard('调整单：原始值不被覆盖（源数据不动）', () => {
  const iv = X.IVs.find(x => x.id === 'V11');
  if (!X.adjOf(iv)) throw new Error('V11 应有调整单');
  if (iv.amt !== 334800.00) throw new Error('原始值被改动，违反「源数据不动」');
});
guard('全名反查陷阱样本存在（壳下 2 个具体小微共享全名）', () => {
  const shell = X.PJs.find(p => p.type === 'shell'), kids = X.PJs.filter(p => p.parent === shell.id);
  if (kids.length < 2 || !kids.every(k => k.full === shell.full)) throw new Error('样本不成立');
});

/* ===== 本次新增：MOD-07 活动大表手填 + 「上次值带入」（OPEN-05） ===== */
const BIG_DZ = '华能德州热电联产项目仓库';    /* 本月 6 格全录 → 无带入 */
const BIG_LY = '临沂钢铁余热发电项目仓库';    /* 本月只录前 2 格 → 其余 4 格带入自 2026-07 */
const BIG_XY = '江苏新沂生物质发电项目仓库';  /* 本月与 7/6 月皆无记录 → 留空待填 */
const BIG_WL = '内蒙乌兰察布风光储一体化项目仓库';   /* 本月 6 格全录 → 无带入 */
const BIG_CZ = '山西长治焦化升级改造项目仓库';       /* 本月未录、且 7 月也无 → 应回退到 6 月 */

guard('活动大表：手填值可录入并落在本月', () => {
  ACT.bigEdit({ dataset: { p: BIG_XY, i: '1' }, value: '12345.67', tagName: 'INPUT' });
  const c = X.bigCell(BIG_XY, '2026-08', 1);
  if (c.v !== 12345.67) throw new Error('未写入：' + c.v);
  if (c.from !== null) throw new Error('录入后仍被标为带入：' + c.from);
});
guard('活动大表：编辑一格不连带确认同行的其他格（其余仍保持带入）', () => {
  ACT.bigEdit({ dataset: { p: BIG_LY, i: '2' }, value: '58600000', tagName: 'INPUT' });
  const c = X.bigCell(BIG_LY, '2026-08', 3);
  if (c.from !== '2026-07') throw new Error('同行的其他格被误确认：' + c.from);
  if (c.v !== 54100000.00) throw new Error('带入取值错误：' + c.v);
});
guard('活动大表：`ym` 列（开工时间）必须 `YYYY-MM` —— 非法格式被拒绝、合法格式可写入', () => {
  const b = X.bigCell(BIG_XY, '2026-08', 0).v;
  ACT.bigEdit({ dataset: { p: BIG_XY, i: '0' }, value: '2024-13', tagName: 'INPUT' });
  if (X.bigCell(BIG_XY, '2026-08', 0).v !== b) throw new Error('非法年月被写入：' + X.bigCell(BIG_XY, '2026-08', 0).v);
  ACT.bigEdit({ dataset: { p: BIG_XY, i: '0' }, value: '2024-05', tagName: 'INPUT' });
  if (X.bigCell(BIG_XY, '2026-08', 0).v !== '2024-05') throw new Error('合法年月未被写入');
});
guard('活动大表：非法金额被拒绝且原值不变', () => {
  const b = X.bigCell(BIG_XY, '2026-08', 1).v;
  ACT.bigEdit({ dataset: { p: BIG_XY, i: '1' }, value: 'abc', tagName: 'INPUT' });
  if (X.bigCell(BIG_XY, '2026-08', 1).v !== b) throw new Error('非法输入被写入');
});
guard('活动大表：负数被拒绝且原值不变', () => {
  const b = X.bigCell(BIG_XY, '2026-08', 1).v;
  ACT.bigEdit({ dataset: { p: BIG_XY, i: '1' }, value: '-5', tagName: 'INPUT' });
  if (X.bigCell(BIG_XY, '2026-08', 1).v !== b) throw new Error('负数被写入');
});
guard('活动大表：0 是合法录入值，不会被误判为「未录入」而复触发带入', () => {
  /* 用「工程用油」（金额列 · 现 index 4）做样本 —— 备注列（5）是文本列，`0` 与「未录入」的区分不成立 */
  ACT.bigEdit({ dataset: { p: BIG_XY, i: '4' }, value: '0', tagName: 'INPUT' });
  const c = X.bigCell(BIG_XY, '2026-08', 4);
  if (c.v !== 0 || c.from !== null) throw new Error('0 未被当作已录入');
});
guard('活动大表：清空一格 → 回到「上次值带入」状态', () => {
  ACT.bigEdit({ dataset: { p: BIG_LY, i: '2' }, value: '', tagName: 'INPUT' });
  const c = X.bigCell(BIG_LY, '2026-08', 2);
  if (c.from !== '2026-07') throw new Error('清空后未回到带入态：' + c.from);
  if (c.v !== 58540000.00) throw new Error('清空后未取回带入值：' + c.v);
});
guard('活动大表：手填不参与欠款计算（大表机械费测算 ≠ MOD-10 派生结算）', () => {
  const d0 = X.debts()['合计'];
  ACT.bigEdit({ dataset: { p: BIG_DZ, i: '1' }, value: '777777', tagName: 'INPUT' });
  if (X.debts()['合计'] !== d0) throw new Error('手填大表却改动了欠款：' + d0 + ' → ' + X.debts()['合计']);
});
/* ⚠️ 2026-09-14：「活动大表 A3 打印」已取消（用户裁定 —— 出纸改走「按模板导出」）⇒
   原断言「打印读取与页面同一份解析值 + 标注带入项」随之删除（打印侧已不存在）。
   ⇒ **净损失 1 条覆盖**：原先由它承担的「输出须标注『带入项』」现无断言守护（页面侧只由视觉承担）。 */

/* ===== 2026-09-18（用户裁定「甲」）：提取表「结余」列 —— 手工录入 · 点格即改 =====
   粒度 = **类别 × 仓库 · 不按月**；**未录入 ⇒ 空**（导出里如实留空），**`0` 是合法录入值**。 */
const EX_WH = WH_LY;                          /* 提取表里出现过的仓库（焊材 / 气体都有它） */
guard('结余：未录入 ⇒ 取数给 null（⛔ 不是 0）', () => {
  if (X.extBalOf('焊材', '山东邹平铝业项目仓库') !== null) throw new Error('未录入的仓库没给 null');
});
guard('结余：0 是合法录入值，与「未录入」区分开', () => {
  if (X.extBalOf('气体', BIG_WL) !== 0) throw new Error('0 被当成未录入：' + X.extBalOf('气体', BIG_WL));
});
guard('结余：点格即改可录入（粒度 = 类别 × 仓库，不按月）', () => {
  ACT.extBal({ dataset: { k: '焊材', p: EX_WH }, value: '6543.21', tagName: 'INPUT' });
  if (X.extBalOf('焊材', EX_WH) !== 6543.21) throw new Error('未写入：' + X.extBalOf('焊材', EX_WH));
  if (X.extBalOf('气体', EX_WH) !== null) throw new Error('写了一类却动了另一类（粒度不是「类别 × 仓库」）');
});
guard('结余：非法金额被拒绝且原值不变', () => {
  const b = X.extBalOf('焊材', EX_WH);
  ACT.extBal({ dataset: { k: '焊材', p: EX_WH }, value: 'abc', tagName: 'INPUT' });
  if (X.extBalOf('焊材', EX_WH) !== b) throw new Error('非法输入被写入');
});
guard('结余：负数被拒绝且原值不变', () => {
  const b = X.extBalOf('焊材', EX_WH);
  ACT.extBal({ dataset: { k: '焊材', p: EX_WH }, value: '-1', tagName: 'INPUT' });
  if (X.extBalOf('焊材', EX_WH) !== b) throw new Error('负数被写入');
});
guard('结余：清空 ⇒ 回到「未录入」（删键，不是写 0）', () => {
  ACT.extBal({ dataset: { k: '焊材', p: EX_WH }, value: '', tagName: 'INPUT' });
  if (X.extBalOf('焊材', EX_WH) !== null) throw new Error('清空后不是「未录入」：' + X.extBalOf('焊材', EX_WH));
});
guard('结余：表头 5 列（列 +1）', () => {
  const n = (String(X.EXT_THEAD).match(/<th\b/g) || []).length;
  if (n !== 5) throw new Error('提取表表头列数 ≠ 5：' + n);
  if (!/结余/.test(X.EXT_THEAD)) throw new Error('表头里没有「结余」列');
});
guard('结余：表内渲染 —— 0 照写 0、未录入给空、合计行该格留空（照模板）', () => {
  const g = X.extBlock('气体');
  if (!g.includes('data-act="extBal"')) throw new Error('结余格没渲染成可编辑输入');
  if (!g.includes(`data-p="${BIG_WL}" value="0"`)) throw new Error('0 没被照写成「0」');
  if (!g.includes('data-p="江苏新沂生物质发电项目仓库" value=""')) throw new Error('未录入应给空值（⛔ 不写 0）');
  const sum = g.slice(g.lastIndexOf('<tr'));
  if (!/^<tr[^>]*><td>气体合计<\/td><td><\/td><td><\/td>/.test(sum)) {
    throw new Error('合计行的「仓库 / 结余」格应当留空（照模板）：' + sum.slice(0, 120));
  }
});

rollback();
clearPick();
resetF();

console.log('\n=== 5. 单据年月筛选 / 剔除并入分类 / 项目多选 / 展示名 ===');
const ALL = { cat: '全部', astat: '全部', stat: '全部' };
const H = (o) => X.ntHit(Object.assign({}, ALL, o));
ck('【扩数据后】2026-09 默认命中 51 条（不含剔除）', H({ month: '2026-09' }).length, 51);
ck('2026-08 命中 11 条', H({ month: '2026-08' }).length, 11);
ck('2026-07 命中 7 条', H({ month: '2026-07' }).length, 7);
const sum3 = ['2026-07', '2026-08', '2026-09'].reduce((a, m) => a + H({ month: m }).length, 0);
ck('三个月合计（默认不含剔除）= 69 条', sum3, 69);
/* 2026-09-13 演示数据扩充（铺到 2026-01）后，「无遗漏 / 无重复」不再是"三个月 + 当月剔除 = 全库"，
   改写成**三段式恒等式**：三个月有效 ＋ 当月剔除 ＋ 更早月份（2026-01~06）有效 = 全库。 */
const older = X.NO.filter(n => !n.excl && String(n.date) < '2026-07-01').length;
ck('三个月有效 ＋ 当月剔除 8 ＋ 更早月份有效 = 全库（无遗漏 / 无重复）',
  sum3 + H({ month: '2026-09', cat: '剔除' }).length + older, X.NO.length);
ck('年月末日 2026-08', X.monthEnd('2026-08') === '2026-08-31' ? 1 : 0, 1);
ck('年月末日 2026-06（30 天）', X.monthEnd('2026-06') === '2026-06-30' ? 1 : 0, 1);
ck('年月末日 2026-02（平年 28 天）', X.monthEnd('2026-02') === '2026-02-28' ? 1 : 0, 1);
ck('【修订】分类=辅材 不含被剔除行', H({ month: '2026-09', cat: '辅材' }).every(n => !n.excl) ? 1 : 0, 1);
ck('分类=辅材 命中 38 条', H({ month: '2026-09', cat: '辅材' }).length, 38);
ck('分类=机械 命中 4 条', H({ month: '2026-09', cat: '机械' }).length, 4);
ck('分类=集采 命中 9 条', H({ month: '2026-09', cat: '集采' }).length, 9);
ck('三分类合计 = 有效 51 条', ['辅材', '机械', '集采'].reduce((a, c) => a + H({ month: '2026-09', cat: c }).length, 0), 51);
ck('【修订】分类=剔除 命中 8 条且全部为剔除行', H({ month: '2026-09', cat: '剔除' }).filter(n => n.excl).length, 8);
ck('【修订】分类=剔除 不混入有效行', H({ month: '2026-09', cat: '剔除' }).every(n => n.excl) ? 1 : 0, 1);
ck('分类=全部 = 51 条（剔除行默认不显示）', H({ month: '2026-09', cat: '全部' }).length, 51);
ck('分类=全部 时不含任何剔除行', H({ month: '2026-09', cat: '全部' }).every(n => !n.excl) ? 1 : 0, 1);
ck('筛选条件已无 ex（剔除并入分类）', X.fNt.ex === undefined ? 1 : 0, 1);
ck('付款状态=已付清', H({ month: '2026-09', stat: '已付清' }).every(n => !n.excl && X.statOf(n) === '已付清') ? 1 : 0, 1);
ck('付款通知书默认筛选月 = 北京时间当月（bjMonth()，原型模拟时钟 SYS_YM）', X.fNt.month === X.bjMonth() ? 1 : 0, 1);
ck('【新】默认付款状态筛选 = 未付清', X.fNt.stat === '未付清' ? 1 : 0, 1);
ck('存在 filterNt / filterReset / batchPay / 年月组件 / 项目多选 处理器',
  ['filterNt', 'filterReset', 'batchPay', 'mpToggle', 'mpYear', 'mpPick', 'mpClose', 'pjToggle', 'pjPick', 'pjAll', 'pjNone']
    .every(a => typeof X.ACT[a] === 'function') ? 1 : 0, 1);
ck('存在 batchCatApply / editCat / editDisp 处理器',
  ['batchCatApply', 'editCat', 'editDisp'].every(a => typeof X.ACT[a] === 'function') ? 1 : 0, 1);

console.log('\n--- 5a2. 列顺序与项目多选面板 ---');
const H3 = V.m03();
/* ⚠️ 2026-09-13 列头去掉括号注释后，原来的定位串 `'付款项目<span'` 不再存在 ⇒ **原地改写**。
   改法：按"**列头标签**"定位（容忍 `style="width:…"` 这类属性），别退回"命中关键词即算" ——
   「付款项目」在单元格 `title` 与口径说明里也出现过，用裸 `indexOf` 会取到错的位置。 */
const Th = t => H3.search(new RegExp('<th[^>]*>' + t + '</th>'));
const iProj = Th('付款项目'), iCat = Th('分类'), iDoc = Th('单据名称');
ck('分类列位于「付款项目」与「单据名称」之间', (iProj > 0 && iProj < iCat && iCat < iDoc) ? 1 : 0, 1);
/* 2026-09-12：分类列移位不新增（17 列不变）；同日新增「手动新增通知书」后表尾多一列「操作」→ 18 列 */
ck('列数 18（分类列是移动、手动行新增「操作」列）', _thCountOf(H3, 'm03:notices'), 18);
resetF();
if (!X.pjIsOpen()) X.ACT.pjToggle({ dataset: {}, tagName: 'BUTTON' });   // 确保展开，与前面用例的顺序解耦
const HP = V.m03();
ck('项目多选面板：显示展示名（德州热电）', HP.indexOf('>德州热电</span>') >= 0 ? 1 : 0, 1);
ck('项目多选面板：不显示仓库名', HP.indexOf('>华能德州热电联产项目仓库<') < 0 ? 1 : 0, 1);
ck('项目多选面板：候选键是仓库名，悬停提示里给出它（§2.7.4）', HP.indexOf('title="仓库名：') >= 0 ? 1 : 0, 1);
ck('项目多选面板：宽度内容自适应（不再留大片空白）', HP.indexOf('width:max-content') >= 0 ? 1 : 0, 1);
ck('项目多选面板：项目名不做省略号截断', HP.indexOf('text-overflow:ellipsis') < 0 ? 1 : 0, 1);
ck('项目多选面板：候选项 = 有档案的项目（含归档，15 项）', (HP.match(/data-act="pjPick"/g) || []).length, 15);
ck('项目多选面板：归档项带「已归档」标注', (HP.match(/已归档<\/span>/g) || []).length, 1);
if (X.pjIsOpen()) X.ACT.pjToggle({ dataset: {}, tagName: 'BUTTON' });   // 收起
ck('已移除逐行付款与逐行撤销处理器（改为批量 + 流水页）', (X.ACT.payDlg === undefined && X.ACT.payOk === undefined) ? 1 : 0, 1);
ck('已移除旧的「批量改分类」弹窗（batchCat / batchCatOk）', (X.ACT.batchCat === undefined && X.ACT.batchCatOk === undefined) ? 1 : 0, 1);
ck('已移除原生月份选择（monthSel 由统一年月组件取代）', X.ACT.monthSel === undefined ? 1 : 0, 1);

console.log('\n--- 5b. 项目多选筛选 ---');
const PJ_DZ_FULL = '华能德州热电联产项目#2机组建筑及安装工程';
const PJ_LY_FULL = '临沂钢铁集团余热发电项目土建及安装工程';
ck('【扩数据后】单项目命中 9 条（默认不含该项目的剔除）', H({ month: '2026-09', projs: [WH_DZ] }).length, 9);
ck('加上 分类=剔除 才看到该项目的剔除行 = 1 条', H({ month: '2026-09', projs: [WH_DZ], cat: '剔除' }).length, 1);
ck('空数组 = 全部项目', H({ month: '2026-09', projs: [] }).length, 51);
ck('两个项目取并集 = 15 条', H({ month: '2026-09', projs: [WH_DZ, WH_LY] }).length, 15);
ck('项目多选 + 分类 组合生效（德州 · 辅材）= 6 条', H({ month: '2026-09', projs: [WH_DZ], cat: '辅材' }).length, 6);
ck('项目多选 + 剔除 组合生效（德州 · 剔除）= 1 条', H({ month: '2026-09', projs: [WH_DZ], cat: '剔除' }).length, 1);
/* 2026-09-13 用户口径：**所有项目候选都要含归档项目**（归档排最后 + 标注「已归档」）；
   未建档的全名（档案里根本没有那一行）仍不出现 —— 它不是"归档项目"，是"没有档案"。 */
ck('【修订】项目筛选 = 能定位到仓库的项目（含归档）= 15 个（15 个去重项里排除 1 个未建档、壳不进候选）', X.PROJ_LIST().length, 15);
ck('项目筛选**含**已归档项目（原阳金堤河 · P11 状态=归档）', X.PROJ_LIST().some(f => f.indexOf('原阳') >= 0) ? 1 : 0, 1);
ck('项目筛选不含未建档项目（第四分公司机关办公楼维修）', X.PROJ_LIST().every(f => f.indexOf('机关办公楼') < 0) ? 1 : 0, 1);
ck('去重项共 15 个，筛后 14 个（差额 = 1 未建档）', new Set(X.NO.map(n => n.proj)).size, 15);
ck('项目筛选：归档项一律排在最后（前面全是建档且在建的）', (function () {
  /* 候选键是**仓库名** ⇒ 归档判定要先把键解析回档案行再判（不能再用全名反查） */
  const l = X.PROJ_LIST(), isArc = v => X.arcOf(X.pjRowOf(v)), f = l.findIndex(isArc);
  return (f >= 0 && l.slice(f).every(isArc)) ? 1 : 0;
})(), 1);
ck('项目候选：归档项一律排在最后（期初弹窗 / 付款计划 两处同款）', (function () {
  const ok1 = (function () { const l = X.lgPjList(), i = l.findIndex(X.arcOf); return i >= 0 && l.slice(i).every(X.arcOf); })();
  const ok2 = (function () { const l = X.PL_PROJ_LIST(), i = l.findIndex(v => X.arcOf(X.pjRowOf(v))); return l.every((d, k) => i < 0 || k < i || X.arcOf(X.pjRowOf(d))); })();
  return (ok1 && ok2) ? 1 : 0;
})(), 1);
/* 2026-09-13 用户口径「放宽」：自动归集**也**可以匹配到已归档的小微（与弹窗候选同一份清单），
   否则壳归档后新进的单据会全部落到「待指定」而阻塞导入。⇒ 旧断言"自动归集不该算进来"**已反转**。 */
guard('放宽后：自动归集与弹窗候选**都含归档小微**（归档排最后）；匹配范围仍只在该壳下', () => {
  const n = X.NO.find(x => X.isShellFull(x.proj));
  if (!n) throw new Error('找不到壳单据样本');
  const sh = X.shellOf(n.proj);
  const kid = X.PJs.find(p => p.type === 'small' && p.parent === sh.id);
  const kw = X.kwList(kid.kw)[0];
  const bak = kid.status;
  kid.status = '归档';
  const c1 = X.ownCands(n);
  const c2 = kw ? X.matchKids(n.proj, kw + '项目的结算单') : [];
  kid.status = bak;
  const i = c1.findIndex(p => p.id === kid.id);
  if (i < 0) throw new Error('弹窗候选里没有归档小微');
  if (i !== c1.length - 1) throw new Error('归档小微没有排在最后');
  if (!c2.some(p => p.id === kid.id)) throw new Error('放宽后，自动归集仍匹配不到已归档小微');
  if (!c1.every(p => p.parent === sh.id)) throw new Error('匹配范围越出了该壳');
});
guard('项目状态：归档后**能改回在建**（不锁死），且来回改不留副作用', () => {
  const p = X.PJs.find(x => x.status === '在建'), snap = JSON.stringify(X.NO);
  ACT.editStatus({ dataset: { id: p.id }, tagName: 'SELECT', value: '归档' });
  if (X.PJs.find(x => x.id === p.id).status !== '归档') throw new Error('未能改为归档');
  ACT.editStatus({ dataset: { id: p.id }, tagName: 'SELECT', value: '在建' });
  if (X.PJs.find(x => x.id === p.id).status !== '在建') throw new Error('归档后无法改回在建');
  if (JSON.stringify(X.NO) !== snap) throw new Error('状态来回改动了业务数据');
});

console.log('\n--- 5c. 项目展示名解析（含壳下多小微的陷阱） ---');
ck('唯一匹配 → 输出展示名（德州热电）', X.dispCell(PJ_DZ_FULL) === '德州热电' ? 1 : 0, 1);
ck('展示名是短名、独立于仓库名（P04 = 乌兰察布风光储）', X.dispCell('乌兰察布察右中旗风光储一体化项目安装工程') === '乌兰察布风光储' ? 1 : 0, 1);
ck('展示名 ≠ 仓库名（德州项目：展示名「德州热电」/ 仓库名「华能德州热电联产项目仓库」）',
  (X.dispCell(PJ_DZ_FULL) === '德州热电' && X.PJs.find(p => p.id === 'P01').name === '华能德州热电联产项目仓库') ? 1 : 0, 1);
ck('壳全名对应 4 条档案 → 显示「壳下 3 个小微 · 待指定」（计数 = 具体小微数、不含壳行）',
  (X.dispCell('第四工程公司2026小微项目').indexOf('壳下 3 个小微 · 待指定') >= 0
   && X.dispCell('第四工程公司2026小微项目').indexOf('壳下 4 个小微') < 0) ? 1 : 0, 1);
ck('无匹配 → 未建档', X.dispCell('不存在的项目全名XYZ').indexOf('未建档') >= 0 ? 1 : 0, 1);

console.log('\n--- 5c2. 归属判定（链路 C）：付款通知书行 → 项目档案行 ---');
const SH_FULL = '第四工程公司2026小微项目';
const n10 = X.NO.find(n => n.id === 'N10'), a20 = X.NO.find(n => n.id === 'A20');
const PJ_N0 = X.PJs.length;
/* ① 普通项目：全名唯一 ⇒ 归属天生确定，**永不「待指定」** */
ck('普通项目全名 → 归属自动确定到唯一档案行（P01）',
  (X.ownOf({ id: '_t1', proj: PJ_DZ_FULL, doc: '任意单据名' }) || {}).id === 'P01' ? 1 : 0, 1);
ck('普通项目 → 展示名按归属 id 取（德州热电）',
  X.dispCell(PJ_DZ_FULL, { id: '_t1', proj: PJ_DZ_FULL, doc: 'x' }) === '德州热电' ? 1 : 0, 1);
/* ② 壳全名 + 单据名命中关键词 → 唯一命中 ⇒ 自动归集（不弹窗） */
ck('壳全名 + 单据名含「邹平」→ 自动归集到 P08（唯一命中）', (X.ownOf(n10) || {}).id === 'P08' ? 1 : 0, 1);
ck('自动归集后展示名 = 该小微的展示名（邹平铝业，非壳名）', X.dispCell(SH_FULL, n10) === '邹平铝业' ? 1 : 0, 1);
/* ③ 壳全名 + 单据名不含任何关键词 → 无法判定 ⇒ 「待指定」且**可点去指定**
   ⚠️ 演示数据里**不该存在**这种行（未走完归属 ⇒ 整批不入库，`demo/设计规则` §四-7）
   ⇒ 用**临时行对象**构造真实场景（不 push 进 NO、不污染后续断言）。 */
const _tmp20 = { id: '_TMP20', proj: SH_FULL, doc: '无关键词的零星结算' };
const _dc20 = X.dispCell(SH_FULL, _tmp20);
ck('壳全名 + 单据名**命中不了任何小微关键词** → 待指定，且标签可点（data-act=ownOpen；用临时行构造）',
  (X.ownOf(_tmp20) === null && _dc20.indexOf('待指定') >= 0 && _dc20.indexOf('data-act="ownOpen"') >= 0) ? 1 : 0, 1);
ck('⭐ 演示数据里**不存在**「待指定」的行（归属未走完 ⇒ 整批不入库，不可能入库）',
  X.NO.filter(n => X.isShellFull(n.proj) && X.ownOf(n) === null).length, 0);
/* ⑥ 壳行的**每一条**都要能落到某个小微（关键词命中）—— 上面那条的正面表述 */
ck('壳行按单据名关键词自动归集：邹平 → 邹平铝业 · 菏泽 → 菏泽热电（P18）',
  ((X.ownOf(n10) || {}).disp === '邹平铝业' && (X.ownOf(a20) || {}).disp === '菏泽热电') ? 1 : 0, 1);
/* ④ 匹配范围**限定在该壳下**：换一个不存在的壳全名 → 同一个「邹平」不再命中 P08
     （若按"全部小微"匹配，这里会命中 P08 —— 正是"别的壳把钱抢走"的场景） */
ck('匹配限定在该壳下（壳全名对不上 → 不跨壳命中 P08）',
  X.matchKids('第四工程公司2025小微项目', '邹平项目-铝型材结算').length === 0 ? 1 : 0, 1);

/* ⑤ 关键词去重追加（决策 3/4）：用临时行，测完原地移除、不污染后续断言 */
guard('关键词去重追加：已有词不重复加、新词追加在末尾、空白词不写', () => {
  const tmp = { id: '_KW1', name: '临时仓库', disp: '临时', full: '临时全名', phid: '', status: '在建', type: 'small', parent: 'P09', kw: '|邹平|' };
  X.PJs.push(tmp);
  try {
    if (X.addKw('_KW1', '邹平')) throw new Error('已有词被重复追加');
    if (!X.addKw('_KW1', '魏桥')) throw new Error('新词未追加');
    if (tmp.kw !== '|邹平|魏桥|') throw new Error('追加后格式错：' + tmp.kw);
    if (X.addKw('_KW1', '   ')) throw new Error('空白词不应写入');
    if (X.kwList('|a||b|').length !== 2) throw new Error('kwList 解析空片段有误');
  } finally { const i = X.PJs.findIndex(p => p.id === '_KW1'); if (i >= 0) X.PJs.splice(i, 1); }
});

console.log('\n--- 5c3. 归属判定：写操作（归集 / 建档）—— 跑完立刻回滚 ---');
guard('归集到已有小微：写入归属 id + 关键词已存在时不重复追加', () => {
  doc.querySelector('#ownKw_P08').value = '邹平';          /* 桩：预置关键词输入框（该词已在 P08 名下） */
  ACT.ownOk({ dataset: { id: 'N10', pid: 'P08' }, tagName: 'BUTTON' });
  if (X.OWN['N10'] !== 'P08') throw new Error('归属未写入 OWN');
  if (X.ownOf(n10).id !== 'P08') throw new Error('ownOf 未按「已指定归属」返回');
  if (X.dispCell(SH_FULL, n10) !== '邹平铝业') throw new Error('展示名未按归属 id 取');
  const p = X.PJs.find(x => x.id === 'P08');
  if (X.kwList(p.kw).filter(w => w === '邹平').length !== 1) throw new Error('关键词未去重（重复追加了）');
});
guard('归集拦截：关键词未出现在单据名里 → 不予归集（保留原归属）', () => {
  doc.querySelector('#ownKw_P10').value = '南阳';   /* N10 的单据名是「邹平项目-铝型材结算」，不含「南阳」 */
  const before = X.OWN['N10'];
  ACT.ownOk({ dataset: { id: 'N10', pid: 'P10' }, tagName: 'BUTTON' });
  if (X.OWN['N10'] !== before) throw new Error('单据名不含该关键词，却改写了归属');
});
guard('新建小微并归集：建行（type=small + parent=壳 + 关键词落地）+ 归属指向新行', () => {
  doc.querySelector('#ownNewName').value = '河南南阳热电项目仓库';
  doc.querySelector('#ownNewKw').value = '零星';
  ACT.ownOk({ dataset: { id: 'A20', pid: '__new' }, tagName: 'BUTTON' });
  if (X.PJs.length !== PJ_N0 + 1) throw new Error('未建行');
  const np = X.PJs[X.PJs.length - 1];
  if (np.type !== 'small' || np.parent !== 'P09') throw new Error('新建行的类型/所属壳错（须先有壳后有微）');
  if (np.name !== '河南南阳热电项目仓库' || np.kw !== '|零星|') throw new Error('仓库名/关键词未落地');
  if (X.OWN['A20'] !== np.id) throw new Error('归属未指向新建行');
});
guard('归属判定写操作后已回滚（OWN 清空 / PJs 行数复原）', () => {
  rollback();
  if (Object.keys(X.OWN).length !== 0) throw new Error('OWN 未复位');
  if (X.PJs.length !== PJ_N0) throw new Error('PJs 未复位：' + X.PJs.length);
});

console.log('\n--- 5c4. 链路 B 扶正：全名命中 ≥2 条非壳行 ⇒ 人指认「挂到哪一行」（`TAIL-30`-③）---');
/* 判据主人：《说明书》§2.4.2 链路 B ＋ 决策 1 兜底（「同类多条 ⇒ 系统不猜，交给人」）。
   ⚠️ 这一版弹窗画的是 **≥2 条**那一种：仓库名**已知**（抓取回执给的那条陌生仓库名），缺的是"挂哪一行"
      ⇒ 下拉语义 = **选档案行**；命中 **1 条**占位行时系统在抓取过程中**已自动扶正**（弹不出这个窗）。 */
guard('扶正弹窗：候选 = **该全名下的非壳档案行**，标出占位行、非占位行不可选；且不再有「选真实仓库名」那版下拉', () => {
  const p = X.PJs.find(x => x.id === 'P12');
  const same = X.PJs.filter(x => x.full === p.full && x.type !== 'shell');
  if (same.length < 2) throw new Error('同名非壳行不足 2 条 ⇒ 本条判据没有区分力（P19 样本丢了？）');
  ACT.promote({ dataset: { id: 'P12' }, tagName: 'BUTTON' });
  const h = String(doc.querySelector('#modalRoot').innerHTML);
  if (h.indexOf('id="pmRow"') < 0) throw new Error('弹窗里没有「选哪一行」的下拉');
  if (h.indexOf('id="pmName"') >= 0) throw new Error('旧的「选真实仓库名」下拉还在（那是「命中 1 条」的形态）');
  if (h.indexOf(X.PROMOTE_WH) < 0) throw new Error('弹窗没显示那条**已知的陌生仓库名**（抓取回执给的）');
  same.forEach(x => { if (h.indexOf('value="' + x.id + '"') < 0) throw new Error('候选行 ' + x.id + ' 没进下拉'); });
  /* ⚠️ 三个数都要钉：**候选不多不少** ／ 占位行**可选** ／ 非占位行**不可选**（§2.3.1）。
     只数"标注文字"是钉不住的（把 `disabled` 去掉照样全中）。 */
  if ((h.match(/<option value="/g) || []).length !== same.length) throw new Error('下拉里的候选数 ≠ 该全名下的非壳行数（多/少都不行）');
  const nPh = same.filter(x => String(x.name).startsWith('未建仓-')).length;
  if (nPh < 2) throw new Error('占位行样本不足 2 条 ⇒ 判据没有区分力');
  if ((h.match(/（占位行 ✅ 可扶正）/g) || []).length !== nPh) throw new Error('占位行标注数 ≠ 实际占位行数');
  if ((h.match(/（⛔ 已有真实仓库名，不可改）"/g) || []).length !== same.length - nPh) throw new Error('非占位行没标出「不可改」');
  same.forEach(x => {
    const ph = String(x.name).startsWith('未建仓-');
    const want = `<option value="${x.id}"${ph ? '' : ' disabled'}>`;
    if (h.indexOf(want) < 0) throw new Error(`候选行 ${x.id} 的**可选性**不对（应${ph ? '可选' : '不可选'}）—— 非占位行选得进去 = §2.3.1 被破`);
  });
});
guard('扶正落库：只改**被指定的那一行**（按 id 定位），展示名沿用占位名时一并跟着换', () => {
  doc.querySelector('#pmRow').value = 'P19';          /* 桩：预置下拉 = 人指定到 P19 那一行 */
  ACT.promoteOk({ dataset: { id: 'P12' }, tagName: 'BUTTON' });
  const a = X.PJs.find(x => x.id === 'P12'), b = X.PJs.find(x => x.id === 'P19');
  if (b.name !== X.PROMOTE_WH) throw new Error('被指定的那一行没被扶正：' + b.name);
  if (b.disp !== X.PROMOTE_WH) throw new Error('展示名沿用占位名 ⇒ 应一并跟着换（否则屏幕还挂「未建仓-02」）');
  if (a.name !== '未建仓-01') throw new Error('**没被指定的那一行被动了**：' + a.name);
  rollback();
});
guard('扶正拦截：指定到**非占位行**（已有真实仓库名）⇒ 明确拒、一个字不改（§2.3.1）', () => {
  const t = X.PJs.find(x => x.name === '华能德州热电联产项目仓库');
  doc.querySelector('#pmRow').value = t.id;
  ACT.promoteOk({ dataset: { id: 'P12' }, tagName: 'BUTTON' });
  if (t.name !== '华能德州热电联产项目仓库') throw new Error('非占位行的仓库名被改了');
  rollback();
});
doc.querySelector('#pmRow').value = '';   /* 别把预置的下拉留给后面的用例（同 `#rReason` 的做法） */

console.log('\n--- 5d. 付款金额（本次应付）派生默认 = 审批金额 − 已付金额 ---');
const n4 = X.NO.find(n => n.id === 'N04');
ck('N04 本次应付 = 152400（审批 152400 − 已付 0）', X.payEff(n4), 152400.00);
ck('A21 全额付清 → 本次应付自动归零', X.payEff(X.NO.find(n => n.id === 'A21')), 0);
ck('A01 未付款 → 本次应付 = 审批金额 46800', X.payEff(X.NO.find(n => n.id === 'A01')), 46800.00);
ck('存在 14 条「审批金额 ≠ 统计付款金额」（存储口径未受派生影响；N10 为 MOD-05 归属演示留欠 11200）',
  X.NO.filter(n => !n.excl && Math.abs(n.approve - n.sp) > 0.005).length, 14);
ck('剔除记录审批金额 ≠ 0 但统计付款金额为 0（8 条，不参与欠款）',
  X.NO.filter(n => n.excl && n.sp === 0 && n.approve > 0).length, 8);

console.log('\n--- 5d2. 付款状态：默认「未付清」+ 判定基准 = 审批金额 ---');
ck('2026-09 未付清 43 条', H({ month: '2026-09', stat: '未付清' }).length, 43);
ck('2026-09 已付清 8 条', H({ month: '2026-09', stat: '已付清' }).length, 8);
ck('43 + 8 = 51（有效记录全覆盖，无遗漏）', 43 + 8, 51);
ck('未付清结果里不含剔除行', H({ month: '2026-09', stat: '未付清' }).every(n => !n.excl) ? 1 : 0, 1);

console.log('\n--- 5e. 全选：范围与状态回显 ---');
resetF(); clearPick();
ACT.pickAll({ tagName: 'INPUT', checked: true });
const visN = X.ntHit(X.fNt).filter(n => !n.excl).length;
ck(`全选后勾选数 = 当前筛选结果（未付清 ${visN} 条）`, X.pickSet.size, visN);
/* 上界用**派生式**（不写死数字）：可勾选数 = 非剔除行数 —— 演示数据一扩容，写死的数字必然过期 */
const pickable = X.NO.filter(n => !n.excl).length;
ck(`且严格小于全库可勾选数（非剔除 ${pickable} 行），说明未越界`, X.pickSet.size < pickable ? 1 : 0, 1);
ck('全选不含任何剔除行', [...X.pickSet].every(id => !X.NO.find(n => n.id === id).excl) ? 1 : 0, 1);
X.BIND.m03();
ck('全选框：全选中时 checked = true', doc.querySelector('#pickAllBox').checked === true ? 1 : 0, 1);
ACT.pick({ dataset: { id: 'A01' }, tagName: 'INPUT', checked: false });
X.BIND.m03();
ck('全选框：取消一行后 indeterminate = true（半选）', doc.querySelector('#pickAllBox').indeterminate === true ? 1 : 0, 1);
ck('半选时 checked = false', doc.querySelector('#pickAllBox').checked === false ? 1 : 0, 1);
ACT.pickAll({ tagName: 'INPUT', checked: true });   // 重新全选，让断言不依赖上一步
X.fNt.cat = '辅材'; X.prunePick();
const visC = X.ntHit(X.fNt).filter(n => !n.excl).length;
ck(`筛选变化后勾选集合被裁剪到可见范围（辅材·未付清 ${visC} 条）`, X.pickSet.size, visC);
ck('裁剪确实生效（数量严格减少）', X.pickSet.size < visN ? 1 : 0, 1);
X.fNt.cat = '机械'; X.prunePick();
ck('再切到机械（4 条）后勾选只剩 0 条（原选中行都不可见）', X.pickSet.size, 0);
resetF(); clearPick();

console.log('\n--- 5f. 活动大表手填项与「上次值带入」（OPEN-05） ---');
ck('大表手填列 = 6 项（开工时间 / 机械费测算 / 合同价 / 产值累计 / 工程用油 / 备注）', X.BIGCOLS.length, 6);
const BR = X.bigRows('2026-08');
const carry = (p) => BR.find(r => r.wh === p).carryN;
ck('本月已全录 → 无带入（德州）', carry(BIG_DZ), 0);
ck('本月部分未录 → 4 格带入（临沂：本月只录了开工时间 / 机械费测算）', carry(BIG_LY), 4);
ck('本月未录、且 7/6 月都无记录 → **0 格带入**（新沂 = 留空待填，不是"带入"）', carry(BIG_XY), 0);
ck('本月已全录 → 无带入（乌兰察布）', carry(BIG_WL), 0);
ck('本月未录、7 月也无 → 6 格**回退两级**带入（长治 ← 2026-06）', carry(BIG_CZ), 6);
ck('带入来源月份标注正确（临沂 · 合同价 ← 2026-07）', X.bigCell(BIG_LY, '2026-08', 2).from === '2026-07' ? 1 : 0, 1);
ck('带入取值正确（临沂 · 合同价 = 58,540,000）', X.bigCell(BIG_LY, '2026-08', 2).v, 58540000.00);
ck('「最近一次录入值」跨月查找：7 月无长治 → 应取 6 月', X.bigCell(BIG_CZ, '2026-08', 0).from === '2026-06' ? 1 : 0, 1);
ck('跨月带入取值正确（长治 · 开工时间 ← 2026-06 = 2023-11）', X.bigCell(BIG_CZ, '2026-08', 0).v === '2023-11' ? 1 : 0, 1);
ck('再往前也无记录 → 留空待填（新沂在 2026-06 无记录）', X.bigCell(BIG_XY, '2026-06', 0).v === null ? 1 : 0, 1);
ck('带入是只读派生：历史月份的录入值本身不被改写（临沂 7 月合同价仍为 58,540,000）', X.BIGVAL['2026-07'][BIG_LY][2], 58540000.00);
ck('存在 bigEdit 处理器（手填录入入口）', typeof X.ACT.bigEdit === 'function' ? 1 : 0, 1);
const H7 = V.m07();
/* 计数一律**派生**（用 `BR` 独立复算），不写死 —— 项目集合一变就自动跟上 */
const _isM = i => X.BIGFMT[i] === 'm';
const _carryMoney = BR.reduce((a, r) => a + r.cells.filter((c, i) => c.from && _isM(i)).length, 0);
const _carryAny = BR.reduce((a, r) => a + r.carryN, 0);
ck('页面渲染：带入格为黄底输入框（金额列带 num ⇒ class="inp num ed"）', (H7.match(/class="inp num ed"/g) || []).length, _carryMoney);
ck('页面渲染：带入格带来源月标记（↺07月 / ↺06月）', (H7.match(/class="ctag"/g) || []).length, _carryAny);
ck('页面渲染：手填输入框 = 项目数 × 7 列（焊材 / 三气 / 派生列都是只读）', (H7.match(/data-act="bigEdit"/g) || []).length, X.BIGSET.length * X.BIGCOLS.length);

console.log('\n--- 5f2. 活动大表：按最终模板的列结构 + 派生列 + 「选题」（多选 / 顺序） ---');
const _colsOf = t => {
  const tr0 = ((t.match(/<thead>[\s\S]*?<\/thead>/i) || [''])[0].match(/<tr\b[^>]*>[\s\S]*?<\/tr>/i) || [''])[0];
  return (tr0.match(/<th\b[^>]*>[\s\S]*?<\/th>/gi) || []).reduce((a, th) => a + (+((th.match(/colspan="(\d+)"/) || [0, 1])[1])), 0);
};
guard('活动大表：列结构 = 用户**最终模板**（20 列；且**不含**「租分公司设备」「不含税」明细列）', () => {
  const t = _tblByKey(H7, 'm07:bigtable');
  if (!t) throw new Error('没抓到活动大表');
  const cols = _colsOf(t);
  if (cols !== 20) throw new Error('列数 ' + cols + ' ≠ 20');
  const head = (t.match(/<thead>[\s\S]*?<\/thead>/i) || [''])[0];
  ['序号', '项目名称', '开工时间', '辅材使用（不含税）', '外租使用（含税）', '合计', '机械费测算', '使用率', '产值', '主材累计', '工程用油', '备注']
    .forEach(s => { if (head.indexOf(s) < 0) throw new Error('表头缺「' + s + '」'); });
  if (head.indexOf('租分公司设备') >= 0) throw new Error('「租分公司设备」不该进大表');
  if (/外租零租不含税|外租包月不含税/.test(head)) throw new Error('「不含税」明细列不该进大表');
});
guard('活动大表：派生列 = 独立复算（合计 = 外租机械累计 ＋ 设备租赁累计；使用率 ÷ 机械费测算；完成率 ÷ 合同价）', () => {
  const rs = X.bigRows('2026-08');
  if (!rs.length) throw new Error('大表没有行 —— 断言失去区分力');
  rs.forEach(r => {
    const want = X.N2(X.bigRentCum(r.wh) + X.bigLeaseCum(r.wh));
    if (r.totC !== want) throw new Error(r.wh + ' 合计 ' + r.totC + ' ≠ 独立复算 ' + want);
    if (r.rentC !== X.bigRentCum(r.wh) || r.leaseC !== X.bigLeaseCum(r.wh)) throw new Error(r.wh + ' 两列「开工累计」对不上');
  });
  const one = rs.find(r => r.use != null && r.done != null);
  if (!one) throw new Error('没有同时有「机械费测算」与「合同价」的行 —— 断言失去区分力');
  const cap = X.bigCell(one.wh, '2026-08', 1).v, cont = X.bigCell(one.wh, '2026-08', 2).v, outv = X.bigCell(one.wh, '2026-08', 3).v;
  if (one.use !== X.N2(one.totC / cap)) throw new Error('使用率 ≠ 合计 ÷ 机械费测算');
  if (one.done !== X.N2(outv / cont)) throw new Error('产值完成率 ≠ 产值累计 ÷ 合同（预估）价');
});
guard('活动大表「选题」：候选 = 在建·非壳；勾选 / 调序 / 确定后**行序即所设顺序**', () => {
  const cands = X.bigCands();
  if (cands.length < 3) throw new Error('候选项太少 —— 断言失去区分力');
  cands.forEach(w => { const p = X.pjRowOf(w); if (!p || p.status !== '在建' || p.type === 'shell') throw new Error('候选里混进了非「在建」或壳行：' + w); });
  ACT.bigPick({ dataset: {}, tagName: 'BUTTON' });
  ACT.bigSelNone({ dataset: {}, tagName: 'BUTTON' });
  [cands[2], cands[0], cands[1]].forEach(w => ACT.bigSelTog({ dataset: { wh: w }, tagName: 'INPUT', checked: true }));   /* 草稿 = [c2,c0,c1] */
  ACT.bigSelUp({ dataset: { wh: cands[1] }, tagName: 'BUTTON' });                                                      /* c1 上移 ⇒ [c2,c1,c0] */
  ACT.bigPickOk({ dataset: {}, tagName: 'BUTTON' });
  const want = [cands[2], cands[1], cands[0]];
  if (X.BIGSET.join('|') !== want.join('|')) throw new Error('确定后集合 / 顺序不对：' + X.BIGSET.join('|'));
  const page = X.bigRows('2026-08').map(r => r.wh);
  if (page.join('|') !== want.join('|')) throw new Error('页面行序 ≠ 所设顺序');
  resetF();
});

console.log('\n--- 5g. 差异归属收敛 + 材料数据单向流（2026-09-12 口径统一） ---');
ck('差异登记全部归属「库存单据」（不再按发现位置分过程资料）', X.DFs.every(d => d.type === '库存单据') ? 1 : 0, 1);
ck('不存在 type = 过程资料 的差异记录', X.DFs.filter(d => d.type === '过程资料').length, 0);
ck('差异笔数不变（只收敛归属，未增删）', X.DFs.length, 5);
const H12 = V.m12();
ck('MOD-12 写明「差异的修正只改库存单据」', H12.indexOf('差异的修正只改库存单据') >= 0 ? 1 : 0, 1);
ck('MOD-12 写明归属收敛为「库存单据」', H12.indexOf('归属「库存单据」') >= 0 ? 1 : 0, 1);
ck('MOD-12 归属列已无「过程资料」标签', H12.indexOf('>过程资料</span>') < 0 ? 1 : 0, 1);
/* 原先断言只查「OPEN-03 这个词在不在」⇒ 页面把它从「待确认」改成「已确认」也照样绿
   （标签比判据严的假绿，2026-09-14 修正）。判据改为钉住页面**实际写明的两句**。 */
ck('MOD-12 · OPEN-03 已确认（页面须写明「从未做过差异登记」）',
  (H12.indexOf('OPEN-03') >= 0 && H12.indexOf('已确认') >= 0 && H12.indexOf('从未做过差异登记') >= 0) ? 1 : 0, 1);
const H6 = V.m06();
ck('MOD-06 补入「材料数据单向流」并写明引用自库存单据', H6.indexOf('引用自库存单据') >= 0 ? 1 : 0, 1);
ck('MOD-06 口径说明条数标注为 7 条', H6.indexOf('口径说明 · 7 条') >= 0 ? 1 : 0, 1);
ck('MOD-08 调整单口径写明「差异的修正只改库存单据」', V.m08().indexOf('差异的修正只改库存单据') >= 0 ? 1 : 0, 1);

console.log('\n--- 5h. 表头点击排序（全站数据列表） ---');
const _allHtml = Object.keys(V).map(k => { try { return V[k](); } catch (e) { return ''; } }).join('');
/* R13 的两条检查放在 §6（那里有按页渲染结果 vk/PH，能定位到具体页面；此处不再用拼接后的 _allHtml） */
ck('存在 headSort 处理器（表头点击入口）', typeof X.ACT.headSort === 'function' ? 1 : 0, 1);

const _findT = (html, key) => (html.match(/<table\b[^>]*\bdata-sort\b[\s\S]*?<\/table>/g) || []).find(x => x.indexOf('data-tk="' + key + '"') >= 0) || '';
const _thsOf = (html, key) => [..._findT(html, key).matchAll(/<th\b[^>]*>([\s\S]*?)<\/th>/gi)].map(m => m[1].replace(/<[^>]*>/g, '').replace(/\s+/g, '').trim());
const _idxOf = (html, key, name) => _thsOf(html, key).findIndex(h => h.indexOf(name) >= 0);
const _rowsOf = (html, key) => { const t = _findT(html, key); const b = t.match(/<tbody\b[^>]*>([\s\S]*?)<\/tbody>/i); return b ? (b[1].match(/<tr\b[^>]*>[\s\S]*?<\/tr>/gi) || []) : []; };
/* ⭐ 2026-09-13：多张表有了**表内合计行**（`sumRowOf`）⇒ "只看数据行"的断言必须用 `_rowsData`：
   合计行由 `applySorts` 钉在表尾，把它算进"数值单调性 / 最值"里会当场假红（实测踩到）。
   ⚠️ 反过来，`含合计的表：合计行钉在最后`那两条**仍用 `_rowsOf`**（它要的就是含合计的整表）。 */
const _rowsData = (html, key) => _rowsOf(html, key).filter(r => !/^合计/.test(_cellOf(r, 0)));
const _cellOf = (row, i) => {
  const tds = row.match(/<td\b[^>]*>[\s\S]*?<\/td>/gi) || []; const td = tds[i]; if (!td) return '';
  const iv = td.match(/<input\b[^>]*\bvalue="([^"]*)"/i);                 /* 镜像引擎：优先读 input 的值 */
  if (iv) return iv[1];
  return td.slice(td.indexOf('>') + 1, td.lastIndexOf('</td>')).replace(/<[^>]*>/g, '').replace(/\s+/g, '').trim();
};
const _nums = (rows, i) => rows.map(r => { const v = _cellOf(r, i).replace(/,/g, ''); const x = parseFloat(v); return isFinite(x) ? x : NaN; });
const _click = (key, i) => X.ACT.headSort({ dataset: { tk: key, i: String(i) }, tagName: 'TH' });
const _mono = (a, up) => a.every((v, k) => k === 0 || (up ? a[k - 1] <= v : a[k - 1] >= v));

const K3 = 'm03:notices';
delete X.SORT[K3];
const _h0 = X.applySorts(V.m03(), 'm03');
const ci = _idxOf(_h0, K3, '审批金额');
ck('能定位到「审批金额」列（排序入口已注入）', ci > 0 ? 1 : 0, 1);
const _orig = _nums(_rowsData(_h0, K3), ci);

_click(K3, ci);
const _a1 = _nums(_rowsData(X.applySorts(V.m03(), 'm03'), K3), ci);
ck('第 1 次点击 = 升序（数值非递减）', _mono(_a1, true) ? 1 : 0, 1);
ck('升序后最小值在最前（说明按数值排，不是按字符串）', _a1[0], Math.min.apply(null, _orig));

_click(K3, ci);
const _a2 = _nums(_rowsData(X.applySorts(V.m03(), 'm03'), K3), ci);
ck('第 2 次点击 = 降序（数值非递增）', _mono(_a2, false) ? 1 : 0, 1);
ck('降序后最大值在最前', _a2[0], Math.max.apply(null, _orig));

_click(K3, ci);
const _a3 = _nums(_rowsData(X.applySorts(V.m03(), 'm03'), K3), ci);
ck('第 3 次点击 = 回到原序（三态循环闭合）', _a3.join(',') === _orig.join(',') ? 1 : 0, 1);
ck('排序状态记录为「原序」(d=0)', (X.SORT[K3] && X.SORT[K3].d === 0) ? 1 : 0, 1);

_click(K3, ci);
ck('换一列则从该列升序开始（同一时刻只有一列生效）', (function () {
  const c2 = _idxOf(_h0, K3, '单据编码');
  _click(K3, c2);
  return (X.SORT[K3].i === c2 && X.SORT[K3].d === 1) ? 1 : 0;
})(), 1);

const _hv = X.applySorts(V.m03(), 'm03');
ck('表头指示器：当前排序列标 on 且显 ▲（唯一）', (_findT(_hv, K3).indexOf('srt on') >= 0 && (_findT(_hv, K3).match(/▲/g) || []).length === 1) ? 1 : 0, 1);
ck('表头指示器：其余 15 个可排序列显淡色 ↕', (_findT(_hv, K3).match(/↕/g) || []).length, 15);
ck('复选框列不可排（未注入排序入口）', /<th[^>]*data-act="headSort"[^>]*>\s*<input/.test(_findT(_hv, K3)) ? 0 : 1, 1);
ck('表头可聚焦（无障碍：全部排序表头都带 tabindex + role）', (function () {
  const t = _findT(_hv, K3);
  const need = (t.match(/<th[^>]*data-act="headSort"/g) || []).length;
  const has = (t.match(/<th[^>]*data-act="headSort"[^>]*tabindex="0"[^>]*role="button"/g) || []).length;
  return (need > 0 && need === has) ? 1 : 0;
})(), 1);
ck('「操作」列不可排（以 MOD-12 为样本）', /<th[^>]*data-act="headSort"[^>]*>操作/.test(_findT(X.applySorts(V.m12(), 'm12'), 'm12:diffs')) ? 0 : 1, 1);
ck('说明/规则表未被加排序（MOD-14 规则表无 headSort）', /data-act="headSort"/.test(X.applySorts(V.m14(), 'm14')) ? 0 : 1, 1);

ck('含合计的表：合计行钉在最后', (function () {
  delete X.SORT['m07:warehouses'];
  const rs = _rowsOf(X.applySorts(V.m07(), 'm07'), 'm07:warehouses');
  return /合计/.test(_cellOf(rs[rs.length - 1], 0)) ? 1 : 0;
})(), 1);
ck('排序后合计行仍在最后，且数据行确实被重排', (function () {
  const i7 = _idxOf(X.applySorts(V.m07(), 'm07'), 'm07:warehouses', '行数');
  _click('m07:warehouses', i7);
  const rs = _rowsOf(X.applySorts(V.m07(), 'm07'), 'm07:warehouses');
  if (!/合计/.test(_cellOf(rs[rs.length - 1], 0))) return 0;
  const n = _nums(rs.slice(0, rs.length - 1), i7);
  return _mono(n, true) ? 1 : 0;
})(), 1);
ck('分组表（MOD-07 焊材/气体提取）：**分组合计紧贴本类数据行** —— 该表刻意不可排（`applySorts` 会把含「合计」的行钉到表尾、破坏分组）', (function () {
  const h = X.applySorts(V.m07(), 'm07');
  const t = (h.match(/<table[^>]*data-sort-key="m07:kinds"[\s\S]*?<\/table>/) || [''])[0];
  if (!t) return 0;
  if (/\sdata-sort[\s>]/.test((t.match(/^<table\b[^>]*>/) || [''])[0])) return 0;   /* 不该声明 data-sort */
  if (/data-act="headSort"/.test(t)) return 0;                                      /* 不该注入排序入口 */
  const rs = (t.match(/<tr\b[^>]*>[\s\S]*?<\/tr>/g) || []).slice(1);                /* 去掉表头行 */
  const strip = s => String(s).replace(/<[^>]+>/g, '').replace(/&nbsp;/g, ' ').trim();
  const first = rs.map(r => strip((r.match(/<td\b[^>]*>[\s\S]*?<\/td>/) || [''])[0]));
  const iW = first.indexOf('焊材合计'), iG = first.findIndex(x => x === '气体');
  if (iW < 0 || iG < 0) return 0;                                                   /* 失去区分力 */
  if (!(iW < iG)) return 0;
  return /焊材/.test(first[iW - 1] || '') ? 1 : 0;
})(), 1);
ck('含输入框的列（MOD-03 的「统计结算金额」）按 input 的 value 排序（不是读单元格文本）', (function () {
  delete X.SORT[K3];
  const i = _idxOf(X.applySorts(V.m03(), 'm03'), K3, '统计结算金额');
  _click(K3, i);
  const rs = _rowsData(X.applySorts(V.m03(), 'm03'), K3);
  return _mono(_nums(rs, i), true) ? 1 : 0;
})(), 1);
ck('排序只重排行、不改任何单元格内容（行集合不变）', (function () {
  delete X.SORT[K3];
  const before = _nums(_rowsData(X.applySorts(V.m03(), 'm03'), K3), ci).sort((a, b) => a - b).join(',');
  _click(K3, ci);
  const after = _nums(_rowsData(X.applySorts(V.m03(), 'm03'), K3), ci).sort((a, b) => a - b).join(',');
  return before === after ? 1 : 0;
})(), 1);
ck('排序状态按视图分键（切到别的页不影响本页排序）', (function () {
  delete X.SORT['m12:diffs'];
  const h12 = X.applySorts(V.m12(), 'm12');                 /* m12 无排序状态 → 应保持原序、无 on 标记 */
  const m12Clean = _rowsOf(h12, 'm12:diffs').length > 0 && _findT(h12, 'm12:diffs').indexOf('srt on') < 0;
  const m03Keeps = (X.SORT[K3] && X.SORT[K3].i === ci && X.SORT[K3].d === 1);
  return (m12Clean && m03Keeps) ? 1 : 0;
})(), 1);
Object.keys(X.SORT).forEach(k => delete X.SORT[k]);

console.log('\n--- 5i. 弹窗表排序 + 批量付款删除行 / 不可付禁用 ---');
const _modalHtml = () => String(doc.querySelector('#modalRoot').innerHTML);
clearPick(); pick('N05'); pick('N09');                 /* N09 = 未审批 → 不可付 */
ACT.batchPay();
const _mh1 = _modalHtml();
ck('弹窗内的表也支持排序（批量付款窗口）', /<table[^>]*\bdata-sort\b/.test(_mh1) ? 1 : 0, 1);
ck('弹窗表使用稳定的排序键（modal: 前缀）', /data-tk="modal:/.test(_mh1) ? 1 : 0, 1);
ck('每行都有「删除」入口', (_mh1.match(/data-act="batchPayDel"/g) || []).length, 2);
ck('存在不可付行 →「确认付款」被禁用（不是点了才拦）', /data-act="batchPayOk"[^>]*\bdisabled\b/.test(_mh1) ? 1 : 0, 1);
ck('禁用时给出原因（提示要删除不可付行）', _mh1.indexOf('确认付款」已禁用') >= 0 ? 1 : 0, 1);
ACT.batchPayDel({ dataset: { id: 'N09' }, tagName: 'BUTTON' });      /* 删掉不可付的那条 */
ck('删除行同时取消该行勾选', X.pickSet.has('N09') ? 0 : 1, 1);
ck('删除后弹窗重建：只剩 1 行', (_modalHtml().match(/data-act="batchPayDel"/g) || []).length, 1);
ck('删掉不可付行后「确认付款」恢复可点', /data-act="batchPayOk"[^>]*\bdisabled\b/.test(_modalHtml()) ? 0 : 1, 1);
ACT.batchPayDel({ dataset: { id: 'N05' }, tagName: 'BUTTON' });      /* 删空 */
ck('删空后自动关闭弹窗', _modalHtml() === '' ? 1 : 0, 1);
ck('删空后勾选集合为空', X.pickSet.size, 0);
ACT.zipSfjc();
ck('弹窗表带排序：导出 zip 的文件清单', /<table[^>]*\bdata-sort\b/.test(_modalHtml()) ? 1 : 0, 1);
ACT.closeModal({ dataset: {}, tagName: 'BUTTON' });
ACT.jcPayDlg({ dataset: { id: 'J01' }, tagName: 'BUTTON' });
ck('子表已拆开｜付款子表弹窗只装付款子表（1 张表，且不含发票子表）', (function () {
  const h = _modalHtml();
  const n = (h.match(/<table[^>]*\bdata-sort\b/g) || []).length;
  const noInv = h.indexOf('发票子表（ENT-07') < 0;
  return (n === 1 && noInv) ? 1 : 0;
})(), 1);
ACT.closeModal({ dataset: {}, tagName: 'BUTTON' });
ck('弹窗表：点表头能真正重排行（zip 清单按大小 升 → 降 都成立）', (function () {
  ACT.zipSfjc();
  const key = 'modal:zipSfjc';   /* 表键 = 表自己声明的 data-sort-key（不再是"scope + 表序号"） */
  const pull = () => {
    const t = (_modalHtml().match(/<table\b[^>]*\bdata-sort\b[\s\S]*?<\/table>/) || [''])[0];
    const b = t.match(/<tbody\b[^>]*>([\s\S]*?)<\/tbody>/i);
    return (b ? (b[1].match(/<tr\b[^>]*>[\s\S]*?<\/tr>/gi) || []) : [])
      .map(r => parseFloat(_cellOf(r, 2).replace(/,/g, '')));
  };
  ACT.headSort({ dataset: { tk: key, i: 2 }, tagName: 'TH' });
  const a1 = pull();
  ACT.headSort({ dataset: { tk: key, i: 2 }, tagName: 'TH' });
  const a2 = pull();
  const up = a1.length > 1 && a1.every((v, k) => k === 0 || a1[k - 1] <= v);
  const dn = a2.every((v, k) => k === 0 || a2[k - 1] >= v);
  ACT.closeModal({ dataset: {}, tagName: 'BUTTON' });
  delete X.SORT[key];
  return (up && dn) ? 1 : 0;
})(), 1);
ck('批量付款：删除行不丢其他行已填的付款方式 / 金额（草稿保留）', (function () {
  clearPick(); pick('N05'); pick('N09');
  ACT.batchPay();
  ACT.payDraft({ dataset: { id: 'N05', f: 'a' }, value: '12345.67', tagName: 'INPUT' });
  ACT.payDraft({ dataset: { id: 'N05', f: 'm' }, value: '承兑', tagName: 'SELECT' });
  ACT.batchPayDel({ dataset: { id: 'N09' }, tagName: 'BUTTON' });        /* 删掉另一行 → 弹窗重建 */
  const h = _modalHtml();
  const keepAmt = h.indexOf('value="12345.67"') >= 0;
  const keepM = /<option[^>]*selected[^>]*>承兑<\/option>/.test(h);
  ACT.batchPayCancel({ dataset: {}, tagName: 'BUTTON' });
  clearPick();
  return (keepAmt && keepM) ? 1 : 0;
})(), 1);
ck('批量付款：取消后清空草稿', Object.keys(X.draftState()).length, 0);

console.log('\n--- 5j. 抓取 i8 付款通知书 = 按月抓取 ---');
/* ⚠️ 2026-09-23 落点更正（**判词不变、只换落点**）：2026-09-21 用户裁定**删掉 MOD-02 的接口清单表**
   （`TASK` 已不再渲染）⇒ 原来钉在表里的那句"核算年月 → 单据日期起止"没地方找了。
   该口径现在写在**口径说明**里（"时间参数对外一律 start_date / end_date（ISO 闭区间）"）⇒ 改钉它。 */
ck('API-01 入参 = 单据日期起止（ISO 闭区间）—— 口径说明里写明（接口清单表已按 2026-09-21 裁定撤下）',
   (V.m02().indexOf('start_date') >= 0 && V.m02().indexOf('闭区间') >= 0) ? 1 : 0, 1);
ACT.mpPick({ dataset: { id: 'fetchMonth', scope: 'fetch', val: '2026-09' }, tagName: 'BUTTON' });
const _fh = _modalHtml();
ck('抓取弹窗标题写明「按月」', _fh.indexOf('抓取 i8 付款通知书（按月）') >= 0 ? 1 : 0, 1);
ck('抓取弹窗用统一年月组件选月份（scope=fetch）', _fh.indexOf('data-scope="fetch"') >= 0 ? 1 : 0, 1);
ck('回显换算到 i8 的入参：单据日期 2026-09-01 ~ 2026-09-30（闭区间）', _fh.indexOf('单据日期 2026-09-01 ~ 2026-09-30') >= 0 ? 1 : 0, 1);
ck('回显该月命中 59 条（有效 51 + 剔除 8）', (_fh.indexOf('<b>59</b> 条') >= 0 && _fh.indexOf('有效 <b>51</b>') >= 0) ? 1 : 0, 1);
ACT.mpPick({ dataset: { id: 'fetchMonth', scope: 'fetch', val: '2026-08' }, tagName: 'BUTTON' });
const _fh7 = _modalHtml();
ck('改抓取月份后弹窗自动重建、区间随之更新', _fh7.indexOf('单据日期 2026-08-01 ~ 2026-08-31') >= 0 ? 1 : 0, 1);
ck('2026-08 命中 11 条', _fh7.indexOf('<b>11</b> 条') >= 0 ? 1 : 0, 1);
ck('弹窗内年月组件已带 scope（面板可正常展开）', /data-act="mpToggle"[^>]*data-scope="fetch"/.test(_fh7) ? 1 : 0, 1);
ACT.mpToggle({ dataset: { id: 'fetchMonth', scope: 'fetch', val: '2026-08' }, tagName: 'BUTTON' });
const _fh7b = _modalHtml();
ck('弹窗内年月面板可展开（面板由弹窗重建渲染，不是页面 render）', _fh7b.indexOf('data-act="mpYear"') >= 0 ? 1 : 0, 1);
ck('展开后仍保留所选月份与区间', _fh7b.indexOf('单据日期 2026-08-01 ~ 2026-08-31') >= 0 ? 1 : 0, 1);
ck('弹窗内「关闭」按钮已带 scope（点关闭也能重绘弹窗）', /data-act="mpClose"[^>]*data-scope="fetch"/.test(_fh7b) ? 1 : 0, 1);
ACT.mpClose({ dataset: { scope: 'fetch' }, tagName: 'BUTTON' });
ck('关闭面板后弹窗仍在（面板收起、弹窗不关）', _modalHtml().indexOf('抓取 i8 付款通知书') >= 0 ? 1 : 0, 1);
ACT.fetchNtOk({ dataset: {}, tagName: 'BUTTON' });
ck('确认抓取后关闭弹窗', _modalHtml() === '' ? 1 : 0, 1);
clearPick();

console.log('\n--- 5k. 口径差异修正落地（H1/H2/H3 · X1/X2/X6/X10 · M1/M2/M4/M5/M6/M8/M10/M11 · L1–L6/L12/L13） ---');
/* H2：分类 = 剔除 是「看剔除记录」的专用视图 —— 用【真实默认态】断言（不再用 ALL 基座覆盖 stat） */
resetF();
const _defEx = X.ntHit(Object.assign({}, X.fNt, { cat: '剔除' }));
ck('H2｜默认态（付款状态=未付清）下切「分类=剔除」即可见 8 条', _defEx.length, 8);
ck('H2｜该视图只含剔除行', _defEx.every(n => n.excl) ? 1 : 0, 1);
ck('H2｜不受审批状态约束（选「未批」仍是 8 条）', X.ntHit(Object.assign({}, X.fNt, { cat: '剔除', astat: '未批' })).length, 8);
ck('H2｜「分类=全部」仍不含剔除行（默认隐藏未被破坏）', X.ntHit(Object.assign({}, X.fNt, { cat: '全部' })).every(n => !n.excl) ? 1 : 0, 1);

/* H1：付款状态判定基准的“口径展示区”文案 */
ck('H1｜看板状态机写明「≥ 审批金额」且不再出现旧基准',
  (V.home().indexOf('≥ <b>审批金额</b>') >= 0 && V.home().indexOf('≥ 统计付款金额') < 0) ? 1 : 0, 1);
ck('H1｜MOD-05 说明同样改为「已付金额 ≥ 审批金额」',
  (V.m05().indexOf('已付金额 ≥ 审批金额') >= 0 && V.m05().indexOf('≥ 统计付款金额') < 0) ? 1 : 0, 1);

/* X1：集采合同主表 19 字段（2026-09-13 新增「项目」；判据 = 页面写「19 字段」且不再写「15 字段」
   —— 原先断言查「18 字段」，会被页面另一句「原有 18 字段无增删」碰巧命中 ⇒ 改成查「19 字段」。） */
ck('X1｜MOD-11 标注「19 字段」（含结算/欠款两个自动算字段），不再写 15',
  (V.m11().indexOf('19 字段') >= 0 && V.m11().indexOf('15 字段') < 0) ? 1 : 0, 1);

/* X2：贸易公司发票与供应商发票「同一套逻辑」（都取各自子表合计） */
const _J03 = X.JCs.find(j => j.id === 'J03'), _J01 = X.JCs.find(j => j.id === 'J01');
ck('X2｜有贸易公司 → 结算 = 贸易公司发票子表合计', X.jcSettle(_J03), X.jcTradeInvSum(_J03));
ck('X2｜无贸易公司 → 结算 = 供应商发票子表合计', X.jcSettle(_J01), X.jcInvSum(_J01));
ck('X2｜贸易公司发票子表已建立（J03 = 2 张）', (_J03.tradeInvoices || []).length, 2);
ck('X2｜无贸易公司时该子表为空（不参与计算）', (_J01.tradeInvoices || []).length, 0);

/* H3：主表金额 = 只读汇总，录入只走子表 */
ck('H3｜集采欠款基线未变（子表合计 = 原主表值）', X.debts()['集采'], 3697000.00);
ck('H3｜MOD-11 主表已无「付款金额」输入框（jcPay 动作移除）',
  (V.m11().indexOf('data-act="jcPay"') < 0 && X.ACT.jcPay === undefined) ? 1 : 0, 1);
guard('H3｜改付款子表即改欠款（主表为派生汇总，不再清空历史）', () => {
  const j = X.JCs.find(x => x.id === 'J04'), b = X.jcDebt(j), n0 = j.payments.length;
  ACT.jcSubAdd({ dataset: { id: 'J04', kind: 'pay' }, tagName: 'BUTTON' });       /* 增行：付款日期默认取 SYS_TODAY */
  ACT.jcSubSet({ dataset: { k: 'amt' }, value: '1000', tagName: 'INPUT' });
  ACT.jcSubSave({ dataset: {}, tagName: 'BUTTON' });
  if (j.payments.length !== n0 + 1) throw new Error('子表未追加记录');
  if (X.jcPay(j) !== 1000) throw new Error('付款金额未随子表变化：' + X.jcPay(j));
  if (X.jcDebt(j) !== b - 1000) throw new Error('欠款未随子表变化');
  j.payments.pop();
  X.setJcSub({ kind: '', id: '', d: { date: '', amt: '' } });
});

/* X6：分类 / 集采实际供应商 / 三态标记 / 剔除 / 展示名 / 会话级付款金额 —— 一律不留痕 */
guard('X6｜手改分类不留痕', () => {
  const n = X.NO.find(x => x.id === 'N03'), t0 = n.trail.length, c0 = n.cat;
  ACT.editCat({ dataset: { id: 'N03' }, value: '机械', tagName: 'SELECT' });
  const bad = n.trail.length !== t0; n.cat = c0;
  if (bad) throw new Error('分类手改产生了留痕');
});
guard('X6｜集采实际供应商录入不留痕', () => {
  const n = X.NO.find(x => x.id === 'N15'), t0 = n.trail.length;
  ACT.editSup({ dataset: { id: 'N15' }, value: '测试供应商X', tagName: 'INPUT' });
  const bad = n.trail.length !== t0; n.sup = '';
  if (bad) throw new Error('供应商录入产生了留痕');
});
guard('X6｜三态标记不留痕（无 trail 载体）', () => {
  const j = X.JCs.find(x => x.id === 'J12'), t0 = j.tag;
  ACT.jcTag({ dataset: { id: 'J12', v: '纳入台账' }, tagName: 'BUTTON' });
  const bad = !!j.trail; j.tag = t0;
  if (bad) throw new Error('三态标记不应有留痕载体');
});
guard('X6｜人工剔除 / 恢复剔除不留痕（只有 exrule 说明）', () => {
  const n = X.NO.find(x => x.id === 'N01'), t0 = n.trail.length;
  clearPick(); pick('N01');
  ACT.batchEx({ dataset: {}, tagName: 'BUTTON' });
  const marked = n.excl && n.exrule === '人工批量剔除';
  pick('N01');                    /* ⭐ 2026-09-14：恢复剔除改为**只对勾选行生效** ⇒ 必须重新勾上 */
  ACT.batchUnEx({ dataset: {}, tagName: 'BUTTON' });
  clearPick();
  if (!marked) throw new Error('人工剔除未生效');
  if (n.excl) throw new Error('人工剔除未被恢复');
  if (n.trail.length !== t0) throw new Error('剔除 / 恢复产生了留痕');
});
guard('L4｜恢复剔除只恢复「人工批量剔除」，不放开规则命中的剔除', () => {
  const rule = X.NO.find(n => n.id === 'X01');                 /* 规则命中（业务类型=付劳务公司款） */
  if (!rule.excl) throw new Error('前置条件失败：X01 应为规则命中剔除');
  clearPick(); pick('X01');       /* ⭐ 2026-09-14：新语义下必须勾选才轮得到它（不勾 = 根本不参与） */
  ACT.batchUnEx({ dataset: {}, tagName: 'BUTTON' });
  clearPick();
  if (!rule.excl) throw new Error('规则命中的剔除被人工恢复了（破坏「命中即剔除」语义）');
});
/* ⭐ 2026-09-14 用户口径修正：**恢复剔除必须勾选** —— 不能"点一下把所有人工剔除的都放回来"。
   断言要点（三条，各自独立）：
   ① 无勾选时点它 ⇒ **一条都不恢复**（这是本次修正的核心行为）；
   ② 只勾 A ⇒ **只有 A 恢复，B 不动**（证明"按行生效"，不是"按状态生效"）；
   ③ 勾了规则命中的行 ⇒ 也不恢复（由上面 L4 覆盖，这里再验"人工+规则混勾"只恢复人工那条）。 */
guard('§4.2.2（2026-09-14 修正）｜恢复剔除**必须勾选**：无勾选时点它一条都不恢复', () => {
  const a = X.NO.find(x => x.id === 'N01'), b = X.NO.find(x => x.id === 'N02');
  clearPick(); pick('N01'); pick('N02');
  ACT.batchEx({ dataset: {}, tagName: 'BUTTON' });      /* 两条一起人工剔除 */
  if (!(a.excl && b.excl)) throw new Error('前置条件失败：N01/N02 应都是人工剔除');
  clearPick();                                          /* ⭐ 关键：不勾任何行 */
  ACT.batchUnEx({ dataset: {}, tagName: 'BUTTON' });
  const untouched = a.excl && b.excl;
  /* 复位（把这两条还原成"非剔除"，免得污染后面的断言） */
  a.excl = false; a.exrule = ''; b.excl = false; b.exrule = ''; clearPick();
  if (!untouched) throw new Error('无勾选却把人工剔除的行恢复了 —— 「不能点一下全部恢复」被破坏');
});
guard('§4.2.2（2026-09-14 修正）｜恢复剔除**按行生效**：只勾 A ⇒ 只恢复 A，B 保持剔除', () => {
  const a = X.NO.find(x => x.id === 'N01'), b = X.NO.find(x => x.id === 'N02');
  clearPick(); pick('N01'); pick('N02');
  ACT.batchEx({ dataset: {}, tagName: 'BUTTON' });
  clearPick(); pick('N01');                             /* ⭐ 只勾 A */
  ACT.batchUnEx({ dataset: {}, tagName: 'BUTTON' });
  const ok = !a.excl && b.excl;
  a.excl = false; a.exrule = ''; b.excl = false; b.exrule = ''; clearPick();
  if (!ok) throw new Error('恢复剔除没有按勾选行生效：A.excl=' + a.excl + ' B.excl=' + b.excl);
});
guard('§4.2.2（2026-09-14 修正）｜恢复剔除：勾了「规则命中」的行也不恢复（人工+规则混勾只恢复人工那条）', () => {
  const rule = X.NO.find(n => n.id === 'X01');          /* 规则命中 */
  const man = X.NO.find(n => n.id === 'N03');
  if (!rule.excl) throw new Error('前置条件失败：X01 应为规则命中剔除');
  clearPick(); pick('N03');
  ACT.batchEx({ dataset: {}, tagName: 'BUTTON' });      /* N03 人工剔除 */
  if (!man.excl) throw new Error('前置条件失败：N03 应被人工剔除');
  clearPick(); pick('X01'); pick('N03');                /* 混勾：一条规则 + 一条人工 */
  ACT.batchUnEx({ dataset: {}, tagName: 'BUTTON' });
  const ok = rule.excl && !man.excl;
  man.excl = false; man.exrule = ''; clearPick();
  if (!ok) throw new Error('混勾时行为不对：规则命中应保持剔除（' + rule.excl + '）、人工那条应被恢复（' + (!man.excl) + '）');
});

guard('X6｜会话级「付款金额」不留痕', () => {
  const n = X.NO.find(x => x.id === 'N06'), t0 = n.trail.length;
  ACT.editss({ dataset: { id: 'N06', k: 'pay' }, value: '1000', tagName: 'INPUT' });
  const bad = n.trail.length !== t0; delete n.payOv;
  if (bad) throw new Error('会话级覆盖产生了留痕');
});
guard('X6｜统计结算金额仍留痕（唯一的旁路留痕字段）', () => {
  const n = X.NO.find(x => x.id === 'N08'), t0 = n.trail.length;
  ACT.editss({ dataset: { id: 'N08', k: 'ss' }, value: '1000', tagName: 'INPUT' });
  const ok = n.trail.length === t0 + 1; n.ss = n.approve; n.trail.pop();
  if (!ok) throw new Error('统计结算金额未留痕');
});

/* X10：集采合同定时抓取「一期启用」
   ⚠️ 2026-09-23 落点更正（**判词不变、只换落点**）：同前 —— 接口清单表已撤，该口径现写在**口径说明**
   （"集采合同抓取：一期启用「定时自动」"）⇒ 改钉它（claim 仍是"写明触发方式 = 人工点击 ＋ 一期启用定时自动"）。 */
ck('X10｜API-04 触发方式写明「一期启用定时自动」（本页已无接口清单表 ⇒ 口径说明里写明）',
   V.m02().indexOf('一期启用「定时自动」') >= 0 ? 1 : 0, 1);
ck('X10｜抓取日志含「定时自动触发」记录', V.m02().indexOf('定时自动触发') >= 0 ? 1 : 0, 1);
/* X10·3（⭐ 2026-09-30 改判 · `TAIL-64` P4-c 前哨）：原先钉的是「口径说明 · **6** 条」这个**手抄数字** ——
   ⚠️ 实测它**已经漂了**（该块实际有 **7** 条 `<li>`；原型与壳同一位点都写着 6）⇒ 那是**屏幕上的假数字**。
   本条本来要证的是「MOD-02 的**定时抓取约束**确实写进了它的口径说明」。
   ⇒ 改钉**意图**：块在 ＋ 块里有那条约束 ＋ **标注的 N 与实际 `<li>` 数一致**（数字与内容同源，不写死）。
   ⚠️ 壳侧同款守卫（**逐块 · 全站**）在工程仓的测试里（**不在本次交付**）。 */
ck('X10｜MOD-02 口径说明「定时抓取约束」在，且条数标注 = 实际 <li> 数', (function () {
  const b = (V.m02().match(/<details class="tip"><summary>口径说明 · \d+ 条[\s\S]*?<\/details>/) || [''])[0];
  if (!b) return 0;
  const stated = Number((b.match(/口径说明 · (\d+) 条/) || [])[1]);
  const actual = (b.match(/<li>/g) || []).length;
  return stated === actual && b.indexOf('定时') >= 0 ? 1 : 0;
})(), 1);

/* M1：汇总条「已勾选本次应付」取本次应付（不是 i8 源值） */
clearPick(); pick('N02');
const _n2 = X.NO.find(n => n.id === 'N02'), _h3 = V.m03();
const _seg = _h3.slice(_h3.indexOf('已勾选本次应付'));
ck('M1｜汇总条标签已改为「已勾选本次应付」', _h3.indexOf('已勾选本次应付') >= 0 ? 1 : 0, 1);
ck('M1｜取值 = Σ 本次应付（2,200.50），不再取 i8 源值 n.pay',
  (_seg.indexOf(X.M(X.payEff(_n2)) + '</span>') >= 0 && html.indexOf('a+n.pay,0)') < 0) ? 1 : 0, 1);
clearPick();

/* M2 / M4 / M5 */
ck('M2｜MOD-06 材料费来源口径 = 「引用自库存单据 · 派生只读」，全页不写「理论上 =」（原「关系行」随卡片 kv 删除，该口径由「口径说明」承担）',
  (V.m06().indexOf('引用自库存单据') >= 0 && V.m06().indexOf('派生只读') >= 0 && V.m06().indexOf('理论上 =') < 0) ? 1 : 0, 1);
ck('M4｜MOD-09 的 OPEN-06 已标「已定案」，不再写「最终口径待用户确认」',
  (V.m09().indexOf('OPEN-06</span> 已定案') >= 0 && V.m09().indexOf('最终口径待用户确认') < 0) ? 1 : 0, 1);
guard('M5｜期初占位的项目候选含归档（归档排最后并标注），未建档的仍不出现', () => {
  ACT.addLg({ dataset: {}, tagName: 'BUTTON' });
  ACT.lgPjToggle({ dataset: {}, tagName: 'BUTTON' });     /* 打开「项目」共用面板（单选） */
  const h = V.m05();
  ACT.lgCancel({ dataset: {}, tagName: 'BUTTON' });
  /* 2026-09-13 增行模式：期初的「项目」由**弹窗内 `<select>`** 改为**共用面板（单选）**
     ⇒ 改数「面板里候选的 radio 个数」，并断言**归档标注落在最后一个候选上**
       （不再靠"数 `<option>`"那一巧合 —— 那个 select 已不存在）。 */
  const chunks = h.split('data-act="lgPjPick"');
  /* ⚠️ 上界用**派生式**（⛔ 不写死数字）：演示数据一扩容，写死的数字必然过期（2026-09-18 加 P19 样本时踩到）。 */
  const nNonShell = X.PJs.filter(p => p.type !== 'shell').length;
  if (chunks.length - 1 !== nNonShell) throw new Error('非壳项目候选应 = 非壳档案行数 ' + nNonShell + '，实际 ' + (chunks.length - 1));
  if (chunks[chunks.length - 1].indexOf('已归档') < 0) throw new Error('归档项没有排在最后（最后一个候选未带「已归档」标注）');
  if (h.indexOf('第四分公司机关办公楼维修') >= 0) throw new Error('未建档的全名不该出现在候选里');
});

/* M6：按项目看欠款 = 左右两张（辅材 / 机械） */
const _h5 = V.m05();
ck('M6｜MOD-05 有「按项目看欠款」两张（辅材 / 机械），集采注明去向',
  (_h5.indexOf('按项目看<b>辅材</b>欠款') >= 0 && _h5.indexOf('按项目看<b>机械</b>欠款') >= 0
    && _h5.indexOf('集采见台账') >= 0) ? 1 : 0, 1);
ck('M6｜两张卡在**同一行**（同一 .grid2 内，辅材在左、机械在右）', (function () {
  const g = _h5.indexOf('<div class="grid2">');
  const a = _h5.indexOf('按项目看<b>辅材</b>欠款'), b = _h5.indexOf('按项目看<b>机械</b>欠款');
  const t = _h5.indexOf('data-act="ledExpToggle"');      /* 台账卡在本行之后（用它当右边界，别用「逐月欠款台账」——口径说明里也出现过）。⭐ 2026-09-13：两栏内的 `expLed` 已删，改卡头**一个**导出入口 */
  return (g >= 0 && g < a && a < b && b < t) ? 1 : 0;
})(), 1);
ck('M6｜期初占位行不再单独占卡（已合进逐月欠款台账）',
  (_h5.indexOf('期初占位行（§4.5.2）') < 0 && _h5.indexOf('＋ 录入期初占位行') >= 0) ? 1 : 0, 1);
guard('M6｜辅材卡的值 = Σ辅材统计结算 − Σ辅材统计付款 ＋ 该项目辅材期初', () => {
  const proj = X.PJs.find(p => p.id === 'P01').name;
  const fb = X.NO.filter(n => !n.excl && n.cat === '辅材' && X.ntProjKey(n) === proj).reduce((a, n) => a + n.ss - n.sp, 0);
  const lg = X.LGs.filter(l => l.cat === '辅材' && X.lgProjKeyOf(l.proj) === proj).reduce((a, l) => a + l.settle - l.paid, 0);
  if (V.m05().indexOf(X.M(X.N2(fb + lg)) + '</span>') < 0) throw new Error('未见辅材口径值 ' + (fb + lg));
});
guard('M6｜机械卡的值 = 派生结算 − Σ机械统计付款 ＋ 该项目机械期初', () => {
  const proj = X.PJs.find(p => p.id === 'P01').name;
  const ms = X.machSettleOf(proj);
  const sp = X.NO.filter(n => !n.excl && n.cat === '机械' && X.ntProjKey(n) === proj).reduce((a, n) => a + n.sp, 0);
  const lg = X.LGs.filter(l => l.cat === '机械' && X.lgProjKeyOf(l.proj) === proj).reduce((a, l) => a + l.settle - l.paid, 0);
  if (V.m05().indexOf(X.M(X.N2(ms - sp + lg)) + '</span>') < 0) throw new Error('未见机械口径值 ' + (ms - sp + lg));
});

/* M8：付款域引用 —— 不做自动匹配 + 同一笔不可重复引用 */
guard('M8｜同一笔通知书不可重复引用（第二次被拦截，付款不重复计入）', () => {
  const j = X.JCs.find(x => x.id === 'J04');
  /* ⭐ 样本**派生**：取一条**当前未被任何合同引用**的集采通知书。
     ⚠️ 不能写死 `NO.filter(...集采)[0]` —— 演示数据自带的「已关联」样本（J01 那条 `付款域引用` 行）
        会把它占掉，去重收敛到**全库**后首次引用就会被拦 ⇒ 断言当场假红（2026-09-13 实测）。 */
  const _usedIds = new Set(X.JCs.flatMap(x => (x.payments || []).filter(p => p[3]).map(p => p[3])));
  const n = X.NO.filter(x => !x.excl && x.cat === '集采' && !_usedIds.has(x.id))[0];
  if (!n) throw new Error('没有「未被引用」的集采通知书样本 ⇒ 判据无区分力');
  const b = j.payments.length;
  doc.querySelector('#refId').value = n.id;
  ACT.jcPayRefOk({ dataset: { id: 'J04' }, tagName: 'BUTTON' });          /* 第 1 次引用 */
  const first = j.payments.length === b + 1 && j.payments[j.payments.length - 1][3] === n.id;
  ACT.jcPayRef({ dataset: { id: 'J04' }, tagName: 'BUTTON' });            /* 重开弹窗（候选应已排除） */
  doc.querySelector('#refId').value = n.id;
  ACT.jcPayRefOk({ dataset: { id: 'J04' }, tagName: 'BUTTON' });          /* 第 2 次应被拦截 */
  const second = j.payments.length === b + 1;
  j.payments.length = b;
  if (!first) throw new Error('首次引用未写入 nid（去重锚点缺失）');
  if (!second) throw new Error('重复引用未被拦截');
});
ck('M8｜引用弹窗不再做「供应商名」自动匹配（DEV-J-01）', html.indexOf('j.supplier.includes(n.sup.slice(0,2))') < 0 ? 1 : 0, 1);

/* ===== T1–T4：付款通知书「集采行」→ 关联集采合同（2026-09-13 用户裁定；口径见《说明书》§6.6.2）=====
   关联关系的**唯一存储** = 集采合同付款子表的那一行（第 4 槽 = 通知书 id）；MOD-03 的「已关联」是**派生**。
   ⚠️ 以下断言的反查公式**自己写**（`_lkOf`），**不复用原型里的 `jcRefOf` 自证**。 */
const _lkOf = nid => X.JCs.filter(j => (j.payments || []).some(p => p[3] === nid));
const _lkSetNt = (cat, stat) => { X.fNt.month = '2026-09'; X.fNt.cat = cat; X.fNt.astat = '全部'; X.fNt.stat = stat; X.fNt.projs = []; };

/* T1：入口只在「集采 · 非剔除」的行出现（与「集采实际供应商」输入框同生共灭）；剔除视图一个都没有 */
guard('T1｜「关联集采合同」入口只在「集采 · 非剔除」行出现（与「集采实际供应商」输入框同生共灭）', () => {
  const bak = { c: X.fNt.cat, s: X.fNt.stat, a: X.fNt.astat };
  try {
    _lkSetNt('全部', '全部');
    const h = String(V.m03());
    const link = (h.match(/data-act="jcLink"/g) || []).length;
    const sup = (h.match(/data-act="editSup"/g) || []).length;
    if (sup < 3) throw new Error('当月集采行只有 ' + sup + ' 行 ⇒ 断言失去区分力');
    if (link !== sup) throw new Error(`关联入口 ${link} 个 ≠ 集采行 ${sup} 行`);
    _lkSetNt('剔除', '未付清');                       /* 剔除视图：分类只有「剔除」一档 */
    const hx = String(V.m03());
    if (/data-act="jcLink"/.test(hx)) throw new Error('剔除视图里出现了关联入口');
    if (!/<tr class="ex/.test(hx)) throw new Error('剔除视图没有造出真实场景 ⇒ 判据无区分力');
  } finally { X.fNt.cat = bak.c; X.fNt.stat = bak.s; X.fNt.astat = bak.a; }
});

/* T2：「已关联」是派生 —— 由付款子表反查得来，且**已关联 / 未关联两种态在页面上同时可见** */
guard('T2｜「已关联 <合同号>」由付款子表反查得来（派生、不新增字段），且两种态同时可见', () => {
  const bak = { c: X.fNt.cat, s: X.fNt.stat, a: X.fNt.astat };
  try {
    _lkSetNt('集采', '全部');
    const h = String(V.m03());
    /* 可见行 id **取自渲染结果**；期望值由断言自己反查 */
    const ids = [...new Set((h.match(/data-act="jcLink" data-id="([^"]+)"/g) || [])
      .map(s => /data-id="([^"]+)"/.exec(s)[1]))];
    const expLinked = ids.filter(id => _lkOf(id).length === 1);
    if (ids.length < 3) throw new Error('当月可见集采行只有 ' + ids.length + ' 行 ⇒ 断言失去区分力');
    if (!expLinked.length) throw new Error('演示数据里没有任何「已关联」的集采通知书 ⇒ 判据无区分力');
    if (expLinked.length === ids.length) throw new Error('全部都已关联 ⇒ 两种态没有同时出现，判据无区分力');
    const tagN = (h.match(/已关联 J\d\d/g) || []).length;
    const btnN = (h.match(/改 \/ 解绑/g) || []).length;
    if (tagN !== expLinked.length) throw new Error(`「已关联」标记 ${tagN} 个 ≠ 独立反查 ${expLinked.length} 条`);
    if (btnN !== expLinked.length) throw new Error(`「改 / 解绑」按钮 ${btnN} 个 ≠ 独立反查 ${expLinked.length} 条`);
    expLinked.forEach(id => { if (h.indexOf('已关联 ' + _lkOf(id)[0].id) < 0) throw new Error(id + ' 没有显示「已关联 ' + _lkOf(id)[0].id + '」'); });
  } finally { X.fNt.cat = bak.c; X.fNt.stat = bak.s; X.fNt.astat = bak.a; }
});

/* T3：去重范围 = **全库**（跨合同也不可重复引用）—— 行为面 + 数据面双验 */
guard('T3｜同一笔通知书**全库**范围内至多被引用一次（去重不分公司）', () => {
  const cnt = {};
  X.JCs.forEach(j => (j.payments || []).forEach(p => { if (p[3]) cnt[p[3]] = (cnt[p[3]] || 0) + 1; }));
  const dup = Object.keys(cnt).filter(k => cnt[k] > 1);
  if (dup.length) throw new Error('同一笔被多个合同引用：' + dup.join(' · '));
  const linked = X.NO.filter(n => !n.excl && n.cat === '集采' && cnt[n.id]);
  if (!linked.length) throw new Error('没有「已被引用」的样本 ⇒ 无区分力');
  /* 行为面：换**另一张合同**（J04）打开引用弹窗 —— 已被引用的那笔必须不在候选里 */
  const j = X.JCs.find(x => x.id === 'J04');
  if (linked.some(n => (j.payments || []).some(p => p[3] === n.id))) throw new Error('样本选择有误（已被 J04 自己引用，证不出跨合同）');
  ACT.jcPayRef({ dataset: { id: 'J04' }, tagName: 'BUTTON' });
  const h = String(doc.querySelector('#modalRoot').innerHTML);
  ACT.closeModal();
  linked.forEach(n => { if (h.indexOf('value="' + n.id + '"') >= 0) throw new Error(n.id + ' 已被别的合同引用，却仍出现在本合同的候选里（跨合同去重没生效）'); });
});

/* T5（**2026-09-13 用户口径**）：候选**只列本行实际项目（仓库）的合同** ——
   期望值**独立复算**（不复制 `jcLinkCands`），并做"区分力自检"（样本里必须同时出现"多候选"与"零候选"两种情形）。 */
guard('T5｜关联集采合同：候选**只列本行实际项目（仓库）的合同**；他项目合同不得混入；无合同时给空态且主按钮禁用', () => {
  const bak = { m: X.fNt.month, c: X.fNt.cat, s: X.fNt.stat, a: X.fNt.astat, p: X.fNt.projs.slice() };
  const expOf = id => {                                   /* 独立复算：本项目合同 + 当前已关联那张（若有） */
    const n = X.NO.find(x => x.id === id), pk = X.ntProjKey(n);
    const list = X.JCs.filter(j => j.proj === pk).map(j => j.id);
    const cur = _lkOf(id)[0];
    if (cur && list.indexOf(cur.id) < 0) list.push(cur.id);
    return list;
  };
  const optsOf = h => [...new Set((h.match(/<option value="(J\d+)"/g) || []).map(s => /value="(J\d+)"/.exec(s)[1]))];
  const open = id => { ACT.jcLink({ dataset: { id }, tagName: 'BUTTON' }); const h = String(doc.querySelector('#modalRoot').innerHTML); ACT.closeModal(); return h; };
  try {
    /* ① 当前月可见的每一行：候选必须**恰好**等于独立复算的结果（多一个 = 混入他项目；少一个 = 漏） */
    _lkSetNt('集采', '全部');
    const ids = [...new Set((String(V.m03()).match(/data-act="jcLink" data-id="([^"]+)"/g) || [])
      .map(s => /data-id="([^"]+)"/.exec(s)[1]))];
    if (ids.length < 3) throw new Error('可见集采行只有 ' + ids.length + ' 行 ⇒ 断言失去区分力');
    ids.forEach(id => {
      const exp = expOf(id), got = optsOf(open(id));
      const extra = got.filter(x => exp.indexOf(x) < 0), miss = exp.filter(x => got.indexOf(x) < 0);
      if (extra.length) throw new Error(id + ' 的候选里混进了**他项目**的合同：' + extra.join(','));
      if (miss.length) throw new Error(id + ' 的候选漏掉了本项目合同：' + miss.join(','));
    });
    /* ② "本项目 ≥2 张合同"的样本：必须**只**出现那 2 张（若过滤失效会冒出全库合同）——
       样本取**未关联**的，好让 ④ 的兜底断言有干净起点。 */
    const many = X.NO.filter(x => !x.excl && x.cat === '集采' && !_lkOf(x.id).length && expOf(x.id).length >= 2)[0];
    if (!many) throw new Error('演示数据里没有"本项目 ≥2 张合同 + 未关联"的集采行 ⇒ 测不出过滤精度，判据失去区分力');
    const expMany = expOf(many.id), gotMany = optsOf(open(many.id));
    if (gotMany.length !== expMany.length || expMany.some(x => gotMany.indexOf(x) < 0)) {
      throw new Error(many.id + '（项目 ' + X.ntProjKey(many) + '）候选不是本项目那 ' + expMany.length + ' 张：' + gotMany.join(','));
    }
    /* ③ "本项目 0 张合同"的样本：给空态提示 + 不渲染下拉 + 主按钮禁用（不是"点了才拦"） */
    const none = X.NO.filter(x => !x.excl && x.cat === '集采'
      && !X.JCs.some(j => j.proj === X.ntProjKey(x)) && !_lkOf(x.id).length)[0];
    if (!none) throw new Error('演示数据里没有"本项目无合同"的集采行 ⇒ 空态分支没被覆盖，判据失去区分力');
    const he = open(none.id);
    if (he.indexOf('本项目下暂无集采合同') < 0) throw new Error(none.id + ' 本项目下无合同，却没给空态提示');
    if (/data-act="jcLinkPick"/.test(he)) throw new Error(none.id + ' 无候选时仍渲染了合同下拉');
    if (!/data-act="jcLinkOk"[^>]*disabled/.test(he)) throw new Error(none.id + ' 无候选时「关联」按钮没有禁用');
    /* ④ **防绕过**：程序化把选择改成"他项目"的合同 ⇒ 弹窗重绘会把它**回落到本项目候选**
       （`jcLinkPick` 记录后立即重开弹窗，`jcLink` 拿候选集再校验一次 `jcLinkSel` —— 这就是口径的闭合点。
         ⚠️ 实测教训：原先这里想验"提交兜底"，但那样写**根本走不到提交**，断言会误报成"跨项目落库"）。 */
    const other = X.JCs.filter(j => j.proj !== X.ntProjKey(many))[0];
    if (!other) throw new Error('找不到"他项目"的合同样本 ⇒ 判据失去区分力');
    ACT.jcLink({ dataset: { id: many.id }, tagName: 'BUTTON' });
    ACT.jcLinkPick({ dataset: { id: many.id }, value: other.id, tagName: 'SELECT' });
    const h4 = String(doc.querySelector('#modalRoot').innerHTML);
    ACT.closeModal();
    const selNow = (/<option value="(J\d+)"[^>]*selected/.exec(h4) || ['', ''])[1];
    if (expMany.indexOf(selNow) < 0) throw new Error('程序化选了他项目的合同（' + other.id + '）后没有回落到本项目候选，实际选中：' + selNow);
    if (_lkOf(many.id).length) throw new Error('仅仅是"打开弹窗 + 选择"不该产生任何关联（已落库 1 笔）');
  } finally { Object.assign(X.fNt, { month: bak.m, cat: bak.c, astat: bak.a, stat: bak.s }); X.fNt.projs = bak.p; }
});

/* T4：关联 / 一对一 / 解绑 —— **从动作进去、断言可观测结果**（不用内部状态自证；跑完原地复原） */
guard('T4｜关联写入付款子表（双向可见）· 一对一替换 · 解绑可回退 · 金额不一致只提示不拦', () => {
  /* ⚠️ 2026-09-13：候选已**限定为本项目**的合同 ⇒ 样本必须**派生**（原来写死的 J04/J06 不在本行项目里了）：
     找一个「本项目 ≥2 张合同 + 有未关联集采通知书」的项目 —— 否则测不出"一对一替换"。 */
  const cnt = {}; X.JCs.forEach(j => { cnt[j.proj] = (cnt[j.proj] || 0) + 1; });
  const n = X.NO.filter(x => !x.excl && x.cat === '集采' && _lkOf(x.id).length === 0 && cnt[X.ntProjKey(x)] >= 2)[0];
  if (!n) throw new Error('没有「本项目 ≥2 张合同 + 未关联」的集采通知书样本 ⇒ 判据无区分力');
  const pick = X.JCs.filter(x => x.proj === X.ntProjKey(n));
  const jA = pick[0], jB = pick[1];
  const snapA = jA.payments.map(p => p.slice()), snapB = jB.payments.map(p => p.slice()), bA = jA.payments.length, bB = jB.payments.length;
  const bak = { m: X.fNt.month, c: X.fNt.cat, s: X.fNt.stat, a: X.fNt.astat };
  try {
    ACT.jcLink({ dataset: { id: n.id }, tagName: 'BUTTON' });
    let h = String(doc.querySelector('#modalRoot').innerHTML);
    if (h.indexOf('本行统计付款金额') < 0) throw new Error('弹窗没有金额比对区');
    ACT.jcLinkPick({ dataset: { id: n.id }, value: jA.id, tagName: 'SELECT' });     /* 换选择 → 重绘弹窗 */
    h = String(doc.querySelector('#modalRoot').innerHTML);
    if (!new RegExp('value="' + jA.id + '"[^>]*selected').test(h)) throw new Error('换选择后弹窗没有回显所选合同');
    const mis = X.N2(X.jcDebt(jA)) !== X.N2(n.sp);
    if (mis && h.indexOf('不一致 · 仍可关联') < 0) throw new Error('金额不一致时没有给出提示（口径：只提示不拦截）');
    if (!mis && h.indexOf('一致') < 0) throw new Error('金额一致时没有给出「一致」');
    if (h.indexOf(X.M(X.jcDebt(jA))) < 0) throw new Error('弹窗没有显示所选合同的当前欠款');
    ACT.jcLinkOk({ dataset: { id: n.id }, tagName: 'BUTTON' });                    /* 关联 */
    if (jA.payments.length !== bA + 1) throw new Error('付款子表没有 +1 笔（关联没落库）');
    if (jA.payments[jA.payments.length - 1][3] !== n.id) throw new Error('子表未写入通知书 id（关联锚点缺失）');
    if (_lkOf(n.id).length !== 1 || _lkOf(n.id)[0].id !== jA.id) throw new Error('反查不到唯一关联');
    /* 双向可见：MOD-03 上该行显示「已关联<所选>」——⚠️ 月份放到「全部」，
       免得样本行恰好不在当前月可见（**样本是派生的**，不能再假设月份）。 */
    X.fNt.month = '全部'; X.fNt.cat = '集采'; X.fNt.astat = '全部'; X.fNt.stat = '全部'; X.fNt.projs = [];
    if (String(V.m03()).indexOf('已关联 ' + jA.id) < 0) throw new Error('MOD-03 没有显示「已关联 ' + jA.id + '」（双向可见断了）');
    /* 一对一：改关联到本项目另一张合同 ⇒ 旧合同上那笔必须消失 */
    ACT.jcLink({ dataset: { id: n.id }, tagName: 'BUTTON' });
    ACT.jcLinkPick({ dataset: { id: n.id }, value: jB.id, tagName: 'SELECT' });
    ACT.jcLinkOk({ dataset: { id: n.id }, tagName: 'BUTTON' });
    if (jA.payments.length !== bA) throw new Error('换合同后旧合同上那笔没有被摘掉（违反一对一）');
    if (jB.payments.length !== bB + 1) throw new Error('新合同没有 +1 笔');
    if (_lkOf(n.id).length !== 1 || _lkOf(n.id)[0].id !== jB.id) throw new Error('反查不是唯一的新合同');
    if (String(V.m03()).indexOf('已关联 ' + jB.id) < 0) throw new Error('MOD-03 没有跟着变成「已关联 ' + jB.id + '」');
    /* 解绑 */
    ACT.jcUnlink({ dataset: { id: n.id }, tagName: 'BUTTON' });
    if (jB.payments.length !== bB) throw new Error('解绑后新合同那笔没被摘掉');
    if (_lkOf(n.id).length !== 0) throw new Error('解绑后仍能反查到关联');
    if (String(V.m03()).indexOf('已关联 ' + jB.id) >= 0) throw new Error('解绑后 MOD-03 还显示「已关联」');
  } finally {
    /* **无条件原地复原**（写在 throw 之前生效）：只动过这两张合同的付款子表 */
    jA.payments.length = 0; snapA.forEach(p => jA.payments.push(p));
    jB.payments.length = 0; snapB.forEach(p => jB.payments.push(p));
    X.fNt.month = bak.m; X.fNt.cat = bak.c; X.fNt.stat = bak.s; X.fNt.astat = bak.a;
    try { ACT.closeModal(); } catch (e) { }
  }
});

/* M10：三处筛选器真正生效（R4） */
ck('M10｜MOD-01 筛选栏已接上动作（状态/类型/搜索 + 重置 = 4 个）', (V.m01().match(/data-act="fPj/g) || []).length, 4);
guard('M10｜MOD-01 状态筛选生效（在建 / 归档 / 全部 = 与档案表**独立复算**一致）', () => {
  const cnt = () => (V.m01().match(/data-act="delPj"/g) || []).length;
  /* ⚠️ 三个数一律**派生**（⛔ 不写死）：演示数据一扩容（2026-09-18 加 P19）写死的数字必然过期；
     筛选要是坏了（三个数相等 / 归档没被筛掉），这里照样红 —— 区分力没丢。 */
  const n = st => X.PJs.filter(p => st === '全部' || p.status === st).length;
  X.fPj.status = '在建'; const a = cnt();
  X.fPj.status = '归档'; const b = cnt();
  X.fPj.status = '全部'; const c = cnt();
  X.fPj.status = '在建';
  if (!(a === n('在建') && b === n('归档') && c === n('全部'))) throw new Error(`在建 ${a} / 归档 ${b} / 全部 ${c}`);
  if (!(b > 0 && a < c)) throw new Error('归档样本必须存在、且「在建」必须少于「全部」—— 否则筛选判据没有区分力');
});
guard('M10｜MOD-01 名称模糊搜索生效（德州 → 1 行）', () => {
  X.fPj.q = '德州'; const n = (V.m01().match(/data-act="delPj"/g) || []).length; X.fPj.q = '';
  if (n !== 1) throw new Error('搜索结果应为 1 行，实际 ' + n);
});
ck('M10｜MOD-11 筛选栏已接上动作（三态/存档/供应商 三个下拉 + 重置 = 4 个；「项目」走通用面板动作）', (V.m11().match(/data-act="jc(Filter|Reset)"/g) || []).length, 4);
guard('M10｜MOD-11 两态筛选生效（纳入 11 / 不纳入 1 / 全部 12；⭐ TAIL-97：待确认已取消）', () => {
  /* 每行恰好一个「付款子表」入口 ⇒ 用它数行（原 `jcDetail` 已随"子表拆开"删除） */
  const cnt = () => (V.m11().match(/data-act="jcPayDlg"/g) || []).length;
  X.fJc.tag = '纳入台账'; const b = cnt();
  X.fJc.tag = '不纳入'; const a = cnt();
  X.fJc.tag = '全部'; const c = cnt();
  if (!(b === 11 && a === 1 && c === 12)) throw new Error(`纳入 ${b} / 不纳入 ${a} / 全部 ${c}`);
});
guard('M10｜MOD-11 供应商模糊搜索生效（莱芜 → 1 条）', () => {
  X.fJc.sup = '莱芜'; const n = (V.m11().match(/data-act="jcPayDlg"/g) || []).length; X.fJc.sup = '';
  if (n !== 1) throw new Error('应为 1 条，实际 ' + n);
});
/* ============ 2026-09-13 本批（集采合同加「项目」+ 大表主材累计改派生）============ */
ck('N1｜MOD-11 列结构 = 20 列，且「合同存档情况 / 存档号 / 寄回日期」三项紧贴「操作」左边', (function () {
  /* ⚠️ 独立数表头（不借 `thCount()` —— 那是被测对象自己的派生函数，用它自证是假绿温床） */
  const heads = (V.m11().match(/<th\b[\s\S]*?<\/th>/g) || []).map(h => h.replace(/<[^>]*>/g, '').replace(/\s+/g, ''));
  const n = heads.length, i = heads.findIndex(h => h.indexOf('合同存档情况') >= 0);
  const want = ['合同存档情况', '存档号', '寄回日期', '操作'];
  const tail = heads.slice(i, i + 4);
  return (n === 20 && i === n - 4 && want.every((w, k) => (tail[k] || '').indexOf(w) >= 0)) ? 1 : 0;
})(), 1);
guard('N2｜「项目」筛选（通用控件）生效：筛选后行数 = 独立复算', () => {
  /* ⭐ 先把三态固定成已知值（**走真实控件 + 动作**），再断言 —— 否则"当前 tag 是几"取决于前面跑过谁 */
  doc.querySelector('#fTag').value = '纳入台账';
  X.ACT.jcFilter({ dataset: {}, tagName: 'SELECT' });
  const rows = () => (V.m11().match(/data-act="jcPayDlg"/g) || []).length;
  const all = rows();
  const expAll = X.JCs.filter(j => j.tag === '纳入台账').length;          /* 独立复算 */
  let one = -1, back = -1;
  try {
    X.ACT.jcPjPick({ dataset: { pj: WH_DZ }, tagName: 'INPUT' });        /* ⭐ 从**动作**进去，不直接改 fJc */
    one = rows();
    /* 独立复算：德州在「纳入台账」下只剩 J01（J09 是「不纳入」） */
    const expOne = X.JCs.filter(j => j.tag === '纳入台账' && j.proj === WH_DZ).length;
    if (one !== expOne) throw new Error(`德州 ${one} ≠ 独立复算 ${expOne}`);
  } finally {
    X.ACT.jcPjPick({ dataset: { pj: WH_DZ }, tagName: 'INPUT' });        /* 无条件还原（早退也不污染后续） */
    back = rows();
  }
  if (!(all === expAll && back === all)) throw new Error(`默认 ${all}（应 ${expAll}）/ 复位 ${back}`);
  if (one === all || one === 0) throw new Error(`筛选前后行数 ${all} → ${one} —— 断言失去区分力`);
});
ck('N3｜「项目」筛选走通用控件（4 个动作齐备）',
  ['jcPjToggle', 'jcPjPick', 'jcPjAll', 'jcPjNone'].every(a => typeof X.ACT[a] === 'function') ? 1 : 0, 1);
guard('N4｜「项目」面板 = 多选（走通用控件：含「全选 / 清空」，不是单选 radio）', () => {
  ACT.jcPjToggle({ dataset: {}, tagName: 'BUTTON' });
  const h = V.m11();
  const hasAll = h.indexOf('data-act="jcPjAll"') >= 0 && h.indexOf('data-act="jcPjNone"') >= 0;
  const box = (h.match(/data-act="jcPjPick"/g) || []).length;
  const exp = X.JC_PROJ_LIST().length;           /* 选项 = 合同里出现过的项目（去重） */
  const noRadio = h.indexOf('name="projPanelSingle"') < 0;
  ACT.jcPjToggle({ dataset: {}, tagName: 'BUTTON' });   /* 收起，复位 */
  if (!(hasAll && noRadio && box === exp && exp > 0)) throw new Error(`多选面板不对：全选/清空 ${hasAll} / 无单选 ${noRadio} / 选项 ${box}（应 ${exp}）`);
});
guard('N5｜存档号 / 寄回日期 / 备注 三列可手改（走动作进去、断言可观测结果）', () => {
  const j = X.JCs.find(x => x.id === 'J01');
  const b = [j.archNo, j.retDate, j.remark];
  ACT.jcArchNo({ dataset: { id: 'J01' }, value: 'JD-2026-9999', tagName: 'INPUT' });
  ACT.jcRetDate({ dataset: { id: 'J01' }, value: '2026-09-09', tagName: 'INPUT' });
  ACT.jcRemark({ dataset: { id: 'J01' }, value: '本批测试备注', tagName: 'INPUT' });
  const got = [j.archNo, j.retDate, j.remark].join('|');
  /* 原地复位（逐字段写回，别整体换对象） */
  j.archNo = b[0]; j.retDate = b[1]; j.remark = b[2];
  if (got !== 'JD-2026-9999|2026-09-09|本批测试备注') throw new Error('三列未落值：' + got);
});
guard('N6′｜表单类动作**不再需要登记**（`#2` 2026-09-26）：原型里没有 `CHG` 名单', () => {
  /* ⭐ 判词换了（`#2`）：原先钉的是「凡渲染成表单元素的动作都必须在 `CHG` 里」——
     名单拆掉之后那句就没有主人了；**新的主人 = 委托层**（`change` 看见 `data-act` 就跑，不存在漏登记）。
     ⚠️ 命名空间里 `CHG` 一旦回来 ⇒ 说明又有人把名单加上去了 ⇒ 本条红（`M1` 变异靶证明它会红）。 */
  if (typeof X.CHG !== 'undefined') throw new Error('`CHG` 名单又回来了 —— `#2` 已裁定拆掉它（表单类动作不该再靠登记）');
});
guard('N11｜「项目」筛选是本页**第一个**控件（放在筛选栏最左）', () => {
  const h = V.m11();
  const iProj = h.indexOf('data-act="jcPjToggle"'), iTag = h.indexOf('id="fTag"'), iArch = h.indexOf('id="fArch"');
  if (!(iProj >= 0 && iTag >= 0 && iArch >= 0)) throw new Error('筛选控件没找齐');
  if (!(iProj < iTag && iTag < iArch)) throw new Error(`顺序不对：项目 ${iProj} / 三态 ${iTag} / 存档 ${iArch}`);
});
guard('N12｜「三态标记」默认 = 纳入台账（比**加载时快照**；交互路径里有 jcFilter / jcReset）', () => {
  if (FJCTAG0 !== '纳入台账') throw new Error(`加载时默认三态 = ${FJCTAG0}，应为「纳入台账」`);
});
/* ============ 2026-09-13 第二批：过程资料分段竖线 + MOD-08 项目多选 / 每列可筛 / 表外求和 ============ */
guard('N14｜MOD-06 表①②：按「总求和」四段加视觉分隔，且表头 / 数据行 / 合计行 / 总求和行**四处一致**', () => {
  const SEG = [1, 6, 11, 15];                      /* 0 = 核算月；1 入库 · 6 出库 · 11 机械左 4 · 15 不含税 2 */
  const vsepIdx = row => (row.match(/<(?:td|th)\b[^>]*>/g) || []).map((c, k) => (/\bvsep\b/.test(c) ? k : -1)).filter(k => k >= 0);
  const check = tab => {
    ACT.procTab({ dataset: { i: String(tab) }, tagName: 'DIV' });
    const tbl = (String(V.m06()).match(/<table\b[\s\S]*?<\/table>/) || [''])[0];
    const trs = tbl.match(/<tr\b[^>]*>[\s\S]*?<\/tr>/g) || [];
    if (trs.length < 4) throw new Error('表结构不对（行数 ' + trs.length + '）');
    const got = { '表头': vsepIdx(trs[0]), '数据行': vsepIdx(trs[1]), '合计行': vsepIdx(trs[trs.length - 2]) };
    const want = SEG.join(',');
    Object.keys(got).forEach(k => { if (got[k].join(',') !== want) throw new Error(k + '的分隔列 ' + got[k].join(',') + ' ≠ 段首列 ' + want); });
    /* 总求和行是 4 个带 colspan 的合并格 ⇒ 判据换成"**四格都带分隔**" */
    const tot = vsepIdx(trs[trs.length - 1]);
    if (tot.join(',') !== '1,2,3,4') throw new Error('总求和行的分隔格 ' + tot.join(',') + ' ≠ 1,2,3,4（四段各一格）');
  };
  check(0); check(1);
  ACT.procTab({ dataset: { i: '1' }, tagName: 'DIV' });
});
guard('N15｜MOD-08「项目」筛选 = 多选（通用控件；含「全选 / 清空」、无单选 radio）且生效', () => {
  ACT.fIvReset({ dataset: {}, tagName: 'BUTTON' });
  const rows = () => (String(V.m08()).match(/data-act="adjDlg"/g) || []).length;
  const all = rows();
  ACT.invWhToggle({ dataset: {}, tagName: 'BUTTON' });
  const h = String(V.m08());
  const hasAll = h.indexOf('data-act="invWhAll"') >= 0 && h.indexOf('data-act="invWhNone"') >= 0;
  const noRadio = h.indexOf('name="projPanelSingle"') < 0;
  ACT.invWhToggle({ dataset: {}, tagName: 'BUTTON' });
  try {
    const mine = wh => X.IVs.filter(iv => iv.wh === wh && X.tmIn(X.ivYmState(), iv.dd)).length;
    ACT.invWh({ dataset: { pj: WH_DZ }, tagName: 'INPUT' });
    const one = rows(), expOne = mine(WH_DZ);
    ACT.invWh({ dataset: { pj: WH_LY }, tagName: 'INPUT' });          /* 多选：再选一个 ⇒ 行数应增加 */
    const two = rows(), expTwo = mine(WH_DZ) + mine(WH_LY);
    if (!(hasAll && noRadio)) throw new Error('面板不是多选（全选/清空 ' + hasAll + ' · 无单选 ' + noRadio + '）');
    if (one !== expOne || two !== expTwo) throw new Error(`一选 ${one}≠${expOne} / 两选 ${two}≠${expTwo}`);
    if (!(two > one && one < all)) throw new Error(`筛选无区分力：全部 ${all} / 一选 ${one} / 两选 ${two}`);
  } finally { ACT.fIvReset({ dataset: {}, tagName: 'BUTTON' }); }
});
guard('N16｜MOD-08「每列可筛」（Excel 式）：除「操作」列外每列都有入口，且列条件按下、行数 = 独立复算', () => {
  ACT.fIvReset({ dataset: {}, tagName: 'BUTTON' });
  const h0 = String(V.m08());
  const ths = h0.match(/<th\b[^>]*>[\s\S]*?<\/th>/g) || [];
  const withBtn = ths.filter(t => t.indexOf('data-act="ivColOpen"') >= 0).length;
  if (ths.length < 5) throw new Error('表头没抓到 —— 断言失去区分力');
  if (withBtn !== ths.length - 1) throw new Error(`有筛选入口的列 ${withBtn} ≠ 表头列数 ${ths.length} − 1（末列「操作」不参与）`);
  const cs = (h0.match(/data-act="ivColOpen" data-c="(\d+)"/g) || []).map(s => Number(/(\d+)/.exec(s)[1])).sort((a, b) => a - b);
  const want = Array.from({ length: ths.length - 1 }, (_, i) => i).join(',');
  if (cs.join(',') !== want) throw new Error('列筛选入口的列号不是 0..N−1：' + cs.join(','));
  const rows = () => (String(V.m08()).match(/data-act="adjDlg"/g) || []).length;
  const all = rows();
  try {
    ACT.ivColOpen({ dataset: { c: '2' }, tagName: 'BUTTON' });
    ACT.ivColVal({ dataset: { c: '2', v: '入库' }, tagName: 'INPUT', checked: true });
    const inRows = rows();
    const expIn = X.IVs.filter(iv => iv.dir === '入库' && X.tmIn(X.ivYmState(), iv.dd)).length;
    ACT.ivColQ({ dataset: { c: '3' }, tagName: 'INPUT', value: '钢' });   /* 再叠一列 ⇒ 「与」关系 */
    const both = rows();
    const expBoth = X.IVs.filter(iv => iv.dir === '入库' && String(iv.mat).indexOf('钢') >= 0 && X.tmIn(X.ivYmState(), iv.dd)).length;
    if (inRows !== expIn) throw new Error(`列条件（方向=入库）行数 ${inRows} ≠ 独立复算 ${expIn}`);
    if (both !== expBoth) throw new Error(`两列条件（与）行数 ${both} ≠ 独立复算 ${expBoth}`);
    if (!(both < inRows && inRows < all)) throw new Error(`列筛选无区分力：全部 ${all} / 入库 ${inRows} / 入库+钢 ${both}`);
  } finally { ACT.fIvReset({ dataset: {}, tagName: 'BUTTON' }); }
});
/* ============ 2026-09-13 第三批：表内合计行（全局唯一出口 sumRowOf）+ MOD-12 项目列展示名 + 数值列只给区间 ============ */
/* 本块共用小工具（只服务本块；不新增**原型**顶层变量 ⇒ 不动 `__X` 导出） */
const _srTxt = s => String(s).replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
const _srBody = (h, key) => (_tblByKey(h, key).match(/<tbody\b[^>]*>([\s\S]*?)<\/tbody>/) || ['', ''])[1];
const _srRows = (h, key) => _srBody(h, key).match(/<tr\b[\s\S]*?<\/tr>/g) || [];
const _srSumRow = (h, key) => _srRows(h, key).filter(r => /^合计/.test(_srTxt(r)))[0] || '';
const _srSumCells = (h, key) => (_srSumRow(h, key).match(/<td\b[\s\S]*?<\/td>/g) || []).map(_srTxt);
const _srNTh = (h, key) => (((_tblByKey(h, key).match(/<thead\b[^>]*>([\s\S]*?)<\/thead>/i) || ['', ''])[1]).match(/<th\b/g) || []).length;
/* 可见行 id **取自渲染结果**（不复制筛选逻辑 ⇒ 不会自证）；合计值由断言**自己写公式**复算 */
const _srIds = (h, key, attr) => [...new Set((_srBody(h, key).match(new RegExp(attr + '="([^"]+)"', 'g')) || []).map(s => s.slice(attr.length + 2, -1)))];
const _srNum = t => Number(String(t).replace(/[,\s]/g, ''));
const _srStruct = (name, h, key) => {
  const c = _srSumCells(h, key);
  if (!c.length) throw new Error(name + '：tbody 内没有「合计」行');
  const n = _srNTh(h, key);
  if (c.length !== n) throw new Error(`${name}：合计行 ${c.length} 个 <td> ≠ 表头 ${n} 列`);
  const rows = _srRows(h, key);
  if (rows[rows.length - 1] !== _srSumRow(h, key)) throw new Error(name + '：合计行不在表尾');
  return c;
};
const _srEq = (name, c, i, exp) => { if (Math.abs(_srNum(c[i]) - exp) > 0.005) throw new Error(`${name}：第 ${i} 列合计 ${_srNum(c[i])} ≠ 独立复算 ${exp}`); };

guard('N17｜MOD-08 的「合计」行改回**表内**：落在 tbody 内、列数 = 独立数表头、逐列 = 独立复算、随筛选变、排序后仍在表尾', () => {
  ACT.fIvReset({ dataset: {}, tagName: 'BUTTON' });
  const KEY = 'm08:invoices';
  const recalc = h => { const v = _srIds(h, KEY, 'data-iv'), g = id => X.IVs.find(x => x.id === id);
    return { 6: v.reduce((a, id) => a + Number(g(id).qty), 0),
             9: X.N2(v.reduce((a, id) => a + g(id).amt, 0)),
             10: X.N2(v.reduce((a, id) => a + (X.adjOf(g(id)) ? X.adjOf(g(id)).newAmt : 0), 0)),
             11: X.N2(v.reduce((a, id) => a + g(id).tax, 0)) }; };
  const check = h => { const c = _srStruct('MOD-08', h, KEY), e = recalc(h);
    [6, 9, 10, 11].forEach(i => _srEq('MOD-08', c, i, e[i])); return e[9]; };
  const a0 = check(String(V.m08()));
  if (String(V.m08()).indexOf('Σ ') >= 0) throw new Error('旧的「表外求和条」还在（求和应只在表内）');
  try {
    ACT.ivColOpen({ dataset: { c: '2' }, tagName: 'BUTTON' });
    ACT.ivColVal({ dataset: { c: '2', v: '入库' }, tagName: 'INPUT', checked: true });
    const a1 = check(String(V.m08()));
    if (!(a1 < a0)) throw new Error(`合计没随筛选变：${a0} → ${a1}`);
  } finally { ACT.fIvReset({ dataset: {}, tagName: 'BUTTON' }); }
  /* 排序：点「金额」列两次（升 → 降）—— 合计行必须仍在表尾，且值不变 */
  _click(KEY, 9); _click(KEY, 9);
  const c2 = _srStruct('MOD-08 排序后', String(V.m08()), KEY);
  _srEq('MOD-08 排序后', c2, 9, a0);
  _click(KEY, 9);
});
guard('N18｜MOD-03 付款通知书「合计」行：列数对齐 + 逐列 = 独立复算（只算非剔除行）；切「分类=剔除」→ 无合计行', () => {
  const bak = { c: X.fNt.cat, a: X.fNt.astat, s: X.fNt.stat };
  const KEY = 'm03:notices';
  const sumOf = h => { const v = _srIds(h, KEY, 'data-id'), g = id => X.NO.find(n => n.id === id);
    return { 10: X.N2(v.reduce((a, id) => a + g(id).approve, 0)),
             11: X.N2(v.reduce((a, id) => a + X.payEff(g(id)), 0)),
             12: X.N2(v.reduce((a, id) => a + X.paidOf(id), 0)),
             13: X.N2(v.reduce((a, id) => a + g(id).ss, 0)),
             14: X.N2(v.reduce((a, id) => a + g(id).sp, 0)) }; };
  try {
    X.fNt.month = '2026-09'; X.fNt.cat = '全部'; X.fNt.astat = '全部'; X.fNt.stat = '未付清'; X.fNt.projs = [];
    const h0 = String(V.m03()), c0 = _srStruct('MOD-03', h0, KEY), e0 = sumOf(h0);
    [10, 11, 12, 13, 14].forEach(i => _srEq('MOD-03', c0, i, e0[i]));
    X.fNt.stat = '全部';
    const h1 = String(V.m03()), c1 = _srStruct('MOD-03 全状态', h1, KEY), e1 = sumOf(h1);
    [10, 11, 12, 13, 14].forEach(i => _srEq('MOD-03 全状态', c1, i, e1[i]));
    if (!(e1[10] > e0[10])) throw new Error(`放宽付款状态后合计没变：${e0[10]} → ${e1[10]}（断言失去区分力）`);
    X.fNt.cat = '剔除'; X.fNt.stat = '未付清';
    const h2 = String(V.m03());
    if (_srSumCells(h2, KEY).length) throw new Error('「分类=剔除」视图里不该有合计行（剔除行不计入合计）');
    if (!(_srIds(h2, KEY, 'data-id').length > 0)) throw new Error('剔除视图本身没有行 —— 断言失去区分力');
  } finally { X.fNt.cat = bak.c; X.fNt.astat = bak.a; X.fNt.stat = bak.s; }
});
guard('N19｜MOD-04 付款计划「合计」行：列数对齐 + i8 流程金额 / 本月预付款金额 = 独立复算', () => {
  const KEY = 'm04:plans', h = String(V.m04());
  const c = _srStruct('MOD-04', h, KEY), v = _srIds(h, KEY, 'data-id').map(id => X.PLs.find(p => p.id === id));
  _srEq('MOD-04', c, 5, X.N2(v.reduce((a, p) => a + p.flowAmt, 0)));
  _srEq('MOD-04', c, 8, X.N2(v.reduce((a, p) => a + p.monthAmt, 0)));
});
guard('N20｜MOD-11 集采台账「合计」行：列数对齐 + 7 个金额列 = 独立复算', () => {
  const KEY = 'm11:jc', h = String(V.m11());
  const c = _srStruct('MOD-11', h, KEY), v = _srIds(h, KEY, 'data-id').map(id => X.JCs.find(j => j.id === id));
  if (v.length < 2) throw new Error('可见合同太少 —— 断言失去区分力');
  _srEq('MOD-11', c, 5, X.N2(v.reduce((a, j) => a + j.contractAmt, 0)));
  _srEq('MOD-11', c, 6, X.N2(v.reduce((a, j) => a + X.jcInvSum(j), 0)));
  _srEq('MOD-11', c, 8, X.N2(v.reduce((a, j) => a + (Number(j.tradeContractAmt) || 0), 0)));
  _srEq('MOD-11', c, 9, X.N2(v.reduce((a, j) => a + X.jcTradeInvSum(j), 0)));
  _srEq('MOD-11', c, 10, X.N2(v.reduce((a, j) => a + X.jcSettle(j), 0)));
  _srEq('MOD-11', c, 11, X.N2(v.reduce((a, j) => a + X.jcPay(j), 0)));
  _srEq('MOD-11', c, 12, X.N2(v.reduce((a, j) => a + X.jcDebt(j), 0)));
});
guard('N21｜MOD-12 差异登记「合计」行：列数对齐 + 差异金额**带符号净额** = 独立复算', () => {
  /* ⭐ 自备干净基线：本页 2026-09-13 起有筛选（核算月 / 状态）⇒ 从状态里读可见性，
     必须先走**页面自己的重置动作**回到「全部 / 全部」，否则本断言依赖"前面跑过谁"。 */
  rollback(); X.ACT.dfReset({ dataset: {}, tagName: 'BUTTON' });
  const KEY = 'm12:diffs', h = String(V.m12());
  const c = _srStruct('MOD-12', h, KEY);
  const net = X.DFs.reduce((a, d) => a + d.amount, 0);
  if (!(Math.abs(net) > 0.005)) throw new Error('净额为 0 —— 断言失去区分力');
  _srEq('MOD-12', c, 5, net);
});
guard('N22｜批量付款弹窗「合计」行：列数对齐 + 本次应付 = 独立复算', () => {
  const ids = X.NO.filter(n => n.astat === '已批').slice(0, 3).map(n => n.id);
  if (ids.length < 2) throw new Error('没有可付样本 —— 断言失去区分力');
  ids.forEach(i => X.pickSet.add(i));
  try {
    ACT.batchPay();
    const KEY = 'modal:batchPay', h = _modalHtml();
    const c = _srStruct('批量付款', h, KEY);
    _srEq('批量付款', c, 5, X.N2(ids.reduce((a, i) => a + X.payEff(X.NO.find(n => n.id === i)), 0)));
  } finally { ACT.batchPayCancel(); ids.forEach(i => X.pickSet.delete(i)); }
});
guard('N23｜MOD-12「项目」列正文 = 展示名、全名只留在悬停 title（§2.7.4）', () => {
  const h = String(V.m12()), t = _tblByKey(h, 'm12:diffs');
  const rows = (_srBody(h, 'm12:diffs')).match(/<tr\b[\s\S]*?<\/tr>/g) || [];
  let hit = 0;
  rows.filter(r => !/^合计/.test(_srTxt(r))).forEach(r => {
    const m = /title="项目全名：([^"]*)"/.exec(r);
    if (!m || !m[1]) return;
    const full = m[1];
    const cells = (r.match(/<td\b[\s\S]*?<\/td>/g) || []).map(_srTxt);
    const body = cells[3] || '';
    if (body === full) throw new Error(`第 4 列仍显示全名：${body}`);
    /* 独立复算：全名唯一命中一条档案行 ⇒ 正文必须 = 该行展示名 */
    const arch = X.PJs.filter(p => p.full === full);
    if (arch.length === 1) { const exp = arch[0].disp || arch[0].name; if (body !== exp) throw new Error(`第 4 列「${body}」≠ 展示名「${exp}」`); hit++; }
  });
  if (hit < 3) throw new Error(`只有 ${hit} 行能与档案对上 —— 断言失去区分力`);
});
/* ⭐⭐ 2026-09-13 用户口径**更正**（本条判据此前写反了）：
   原判据 = 「数值列**只给**区间、**不得**渲染值清单」—— 起因是 num 列的值清单"点了没反应"，
   而当时的修法是**把值清单删掉**；**用户的真实意图是「修复它」（让勾选生效），不是「删掉它」**。
   ⇒ 判据**原地反转**：数值列**既有**「≥ / ≤」区间、**也有**值清单，且**勾选必须真的生效**。 */
guard('N24｜MOD-08「每列可筛」：数值列**既有「≥ / ≤」区间、也有值清单**，且勾选**真的生效**（不再是"点了没反应"）；文本 / 枚举列值清单照旧', () => {
  ACT.fIvReset({ dataset: {}, tagName: 'BUTTON' });
  const panel = i => { ACT.ivColOpen({ dataset: { c: String(i) }, tagName: 'BUTTON' });
    const m = String(V.m08()).match(/列筛选[\s\S]*?<div class="tw">/); return m ? m[0] : ''; };
  const rows = () => (_srBody(String(V.m08()), 'm08:invoices').match(/data-iv="/g) || []).length;
  try {
    /* ① 6 个数值列：区间入口 + 值清单**都要有**（旧判据要求"不得有值清单"，已反转） */
    [6, 7, 8, 9, 10, 11].forEach(i => { const s = panel(i);
      if (s.indexOf('data-act="ivColMin"') < 0 || s.indexOf('data-act="ivColMax"') < 0) throw new Error(`数值列 ${i} 缺「≥ / ≤」区间入口`);
      if ((s.match(/data-act="ivColVal"/g) || []).length < 2) throw new Error(`数值列 ${i} 的值清单没渲染出来（数值列也要能按值勾选）`); });
    /* ② 勾选**真的生效**：数量列勾一个"既非 0 也非全部"的值 ⇒ 行数 = **独立复算**（自己从 IVs 数） */
    const ym = X.ivYmState();
    const all = X.IVs.filter(iv => X.tmIn(ym, iv.dd) && iv.qty != null);
    const cnt = {}; all.forEach(iv => { const k = String(iv.qty); cnt[k] = (cnt[k] || 0) + 1; });
    const pick = Object.keys(cnt).filter(k => cnt[k] > 0 && cnt[k] < all.length).sort((a, b) => cnt[b] - cnt[a])[0];
    if (!pick) throw new Error('数量列没有"部分命中"的样本 ⇒ 判据无区分力');
    ACT.ivColClear({ dataset: { c: '6' }, tagName: 'BUTTON' });
    const a0 = rows();
    if (a0 !== all.length) throw new Error(`未设条件时行数 ${a0} ≠ 独立复算 ${all.length}`);
    ACT.ivColVal({ dataset: { c: '6', v: pick }, tagName: 'INPUT' });
    const a1 = rows();
    if (a1 !== cnt[pick]) throw new Error(`数量列勾选「${pick}」没生效：${a1} 行 ≠ 独立复算 ${cnt[pick]}`);
    if (!(a1 < a0)) throw new Error('勾选后行数未减少 ⇒ 断言失去区分力');
    /* ③ 勾选与区间是「与」：把区间抬到该值之上 ⇒ 两者无交集 ⇒ 0 行 */
    ACT.ivColMin({ dataset: { c: '6' }, value: String(Number(pick) + 1) });
    if (rows() !== 0) throw new Error('「勾选 + 区间」没有按「与」生效（期望 0 行）');
    ACT.ivColClear({ dataset: { c: '6' }, tagName: 'BUTTON' });
    if (rows() !== a0) throw new Error('清除本列后没有恢复');
    /* ④ 非数值列的值清单照旧 */
    const others = [2, 3, 5, 12, 16];
    const ok = others.filter(i => panel(i).indexOf('data-act="ivColVal"') >= 0).length;
    if (ok !== others.length) throw new Error(`非数值列的值清单丢了：${ok}/${others.length}`);
  } finally { ACT.fIvReset({ dataset: {}, tagName: 'BUTTON' }); }
});
guard('N13｜库存单据「项目」筛选生效 + 键 = 仓库名（多选前的等价性守护）', () => {
  const list = () => {
    const t = (V.m08().match(/<table\b[^>]*data-sort-key="m08:invoices"[\s\S]*?<\/table>/) || [''])[0];
    const b = (t.match(/<tbody\b[^>]*>([\s\S]*?)<\/tbody>/) || ['', ''])[1];
    /* ⭐ 只数**数据行**（每行一个调整单入口）—— 2026-09-13 起表尾多了「合计」行，数 `<tr>` 会把它一起算上 */
    return (b.match(/data-act="adjDlg"/g) || []).length;
  };
  const all = list();
  ACT.invWhToggle({ dataset: {}, tagName: 'BUTTON' });
  const opened = V.m08().indexOf('data-act="invWh"') >= 0;
  ACT.invWhToggle({ dataset: {}, tagName: 'BUTTON' });
  ACT.invWh({ dataset: { pj: WH_DZ }, tagName: 'INPUT' });
  const one = list();
  const exp = X.IVs.filter(iv => iv.wh === WH_DZ && X.tmIn(X.ivYmState(), iv.dd)).length;   /* 独立复算 */
  ACT.fIvReset({ dataset: {}, tagName: 'BUTTON' });
  const back = list();
  if (!opened) throw new Error('面板没打开（`data-act=invWh` 的选项没渲染）');
  if (!(one < all && back === all)) throw new Error(`筛选无效：全部 ${all} / ${WH_DZ} ${one} / 复位 ${back}`);
  if (one !== exp) throw new Error(`${WH_DZ} 行数 ${one} ≠ 独立复算 ${exp}`);
});
ck('N7｜操作列按钮是**两态互切**（「纳入台账」/「不纳入」），且不再叫「改标记」', (function () {
  const h = V.m11();   /* ⭐ TAIL-97：没有「是否纳入台账」那种"回到待确认"的写法了 */
  return (h.indexOf('>不纳入<') >= 0 && h.indexOf('>纳入台账<') >= 0
    && h.indexOf('>是否纳入台账<') < 0 && h.indexOf('>改标记<') < 0) ? 1 : 0;
})(), 1);
guard('N8｜子表已拆开：三个入口分别在「发票金额 / 贸易公司发票金额 / 付款金额」列内', () => {
  const t = (V.m11().match(/<table\b[^>]*data-sort-key="m11:jc"[\s\S]*?<\/table>/) || [''])[0];
  const rowsHtml = t.match(/<tr\b[^>]*>[\s\S]*?<\/tr>/g) || [];
  const cellsOf = r => r.match(/<td\b[\s\S]*?<\/td>/g) || [];
  const at = (cs, a) => cs.findIndex(c => c.indexOf('data-act="' + a + '"') >= 0);
  /* 有贸易公司的行（J03 一类）⇒ 三个入口都要在；
     列序（0 起算）：合同金额 5 · 发票金额 6 · 贸易公司合同金额 8 · 贸易公司发票金额 9 · 结算 10 · 付款 11 */
  const withTrade = rowsHtml.find(r => r.indexOf('data-act="jcTInvDlg"') >= 0);
  if (!withTrade) throw new Error('找不到「有贸易公司」的行 —— 样本不成立');
  const c1 = cellsOf(withTrade);
  const a1 = [at(c1, 'jcInvDlg'), at(c1, 'jcTInvDlg'), at(c1, 'jcPayDlg')];
  /* 无贸易公司的行：贸易公司发票子表**不启用**（那格显示 —），但另两个入口照常在 */
  const noTrade = rowsHtml.find(r => r.indexOf('data-act="jcTInvDlg"') < 0 && r.indexOf('data-act="jcPayDlg"') >= 0);
  if (!noTrade) throw new Error('找不到「无贸易公司」的行 —— 样本不成立');
  const c2 = cellsOf(noTrade);
  const a2 = [at(c2, 'jcInvDlg'), at(c2, 'jcTInvDlg'), at(c2, 'jcPayDlg')];
  if (a1.join(',') !== '6,9,11') throw new Error(`有贸易公司行：入口落在第 ${a1.map(i => i + 1).join(' / ')} 列（应为 7 / 10 / 12）`);
  if (a2.join(',') !== '6,-1,11') throw new Error(`无贸易公司行：入口落在第 ${a2.map(i => i + 1).join(' / ')} 列（应为 7 / — / 12）`);
});
ck('N9｜大表手填列 = 6 项（「主材累计」已移出 BIGCOLS 改派生）', X.BIGCOLS.length, 6);
ck('N9｜「主材累计」已不在 BIGCOLS 里（改为派生）', X.BIGCOLS.indexOf('主材累计') < 0 ? 1 : 0, 1);
guard('N10｜大表「主材累计（含税）」= 独立复算（按项目取集采结算额 · 只计「纳入台账」）', () => {
  /* ⚠️ 判据独立算：直接拿合同表按 proj 过滤 + 自己走 `jcSettle` 的唯一结算口径（不复用 `bigMatCum`） */
  const exp = wh => X.N2(X.JCs.reduce((a, j) => a + (j.tag === '纳入台账' && j.proj === wh ? X.jcSettle(j) : 0), 0));
  const rs = X.bigRows(X.bjMonth(-1));
  if (!rs.length) throw new Error('大表无行 —— 断言失去区分力');
  const bad = rs.filter(r => X.bigMatCum(r.wh) !== exp(r.wh));
  if (bad.length) throw new Error(`${bad.length} 行的主材累计 ≠ 独立复算（例：${bad[0].wh} ${X.bigMatCum(bad[0].wh)} ≠ ${exp(bad[0].wh)}）`);
  /* ⭐ 必须有**非零样本**，否则"全 0"也能过（失去区分力时主动报错，不静默变绿） */
  const nz = rs.filter(r => r.matC > 0).length;
  if (nz < 2) throw new Error(`主材累计非零样本只有 ${nz} 个 —— 断言失去区分力`);
});
guard('N10b｜「主材累计」只计纳入台账（德州：纳入的 J01 计入、不纳入的 J09 不计入）', () => {
  const inc = X.JCs.filter(j => j.tag === '纳入台账' && j.proj === WH_DZ).reduce((a, j) => a + X.jcSettle(j), 0);
  const all = X.JCs.filter(j => j.proj === WH_DZ).reduce((a, j) => a + X.jcSettle(j), 0);
  if (inc === all) throw new Error('纳入 / 不纳入两条口径在当前数据下同值 —— 断言无区分力，请换样本');
  if (X.bigMatCum(WH_DZ) !== X.N2(inc)) throw new Error(`德州主材累计 ${X.bigMatCum(WH_DZ)} ≠ 只计纳入 ${X.N2(inc)}`);
});
guard('M10｜MOD-08 出入库方向筛选生效', () => {
  const all = (V.m08().match(/data-act="adjDlg"/g) || []).length;
  ACT.fIvDir({ dataset: {}, tagName: 'SELECT', value: '出库' });
  const out = (V.m08().match(/data-act="adjDlg"/g) || []).length;
  ACT.fIvReset({ dataset: {}, tagName: 'BUTTON' });
  if (!(out > 0 && out < all)) throw new Error(`方向筛选无效：全部 ${all} / 出库 ${out}`);
});

/* M11 / L1 / L2 / L3 / L6 / L9 / L12 / L13 / U13 */
ck('M11｜对平判据改为「2 位小数归一后判等」（容差 0），合计行改为动态判定',
  (html.indexOf('w.begin+w.in-w.out-w.end)<0.005') < 0
    && html.indexOf('<span class="tag t-ok">容差 0</span>') < 0
    && html.indexOf('tagOf(totBal)') >= 0) ? 1 : 0, 1);
ck('L1｜不再标「说明书 v1.2」（说明书已去版本号）', html.indexOf('说明书》v1.2') < 0 ? 1 : 0, 1);
ck('L1｜侧栏不写版本号（交付文档与原型侧栏一律不带版本）', (html.indexOf('交互原型 · 全模拟数据') >= 0 && !/交互原型 · 全模拟数据\s*v[\d.]/.test(html)) ? 1 : 0, 1);
ck('L2｜导出文件名用「当前年月」（不再硬编码 2026-09；已取消全局核算期，改用 bjMonth()）',
  (html.indexOf('${bjMonth()}.xlsx') >= 0 && html.indexOf('_2026-08.xlsx') < 0) ? 1 : 0, 1);
ck('L3｜剔除规则「付款项目名」为 2 个命中值（与 §4.2.2 结构一致）',
  V.m14().indexOf('第四分公司机关办公楼维修工程｜第四分公司机关后勤维修工程') >= 0 ? 1 : 0, 1);
ck('L6｜MOD-08 明细表补「含税单价 / 审核日期」（列数 18 → 20）', (function () {
  const t = _tblByKey(V.m08(), 'm08:invoices');
  const h = [...t.matchAll(/<th\b[^>]*>([\s\S]*?)<\/th>/gi)].map(m => m[1].replace(/<[^>]*>/g, '').trim());
  return (h.length === 20 && h.some(x => x.indexOf('含税单价') >= 0) && h.some(x => x.indexOf('审核日期') >= 0)) ? 1 : 0;
})(), 1);
/* ⚠️ 2026-09-23 **口径反转**（用户 2026-09-21 裁定：删掉 MOD-02 的接口清单/导出）⇒ 断言跟着**换向**：
   从"本页补了导出"改成"本页**不再提供导出**（各接口的导出在各自业务页）"——⭐ 不是删断言，是**把 claim 反过来钉**。 */
ck('L9｜MOD-02 **不再单独提供导出**（2026-09-21 裁定删除接口清单 ⇒ 导出在各业务页，且本页写明原因）',
   (V.m02().indexOf('data-act="exp"') < 0 && V.m02().indexOf('本页不单独提供导出') >= 0) ? 1 : 0, 1);
ck('L12｜不再使用未定义的 tip 类名 ws', html.indexOf('class="tip ws"') < 0 ? 1 : 0, 1);
ck('L13｜撤销弹窗不再误引 DEV-P-05', html.indexOf('（DEV-P-05）') < 0 ? 1 : 0, 1);
/* 业务事实 2 已按用户口径**整条删除**（2026-09-12：用户原话"当时我只是顺嘴说了一句，
   AI 过度解读并加上了记录和监控，我不需要这个监控相关的东西"）—— 对应断言一并移除。 */
guard('U13｜业务事实 1 告警由【占位行】推导（不再是写死的仓库名）', () => {
  const h = V.home();
  if (h.indexOf('未建仓-01') < 0) throw new Error('告警未引用占位行');
  if (h.indexOf('差别氨纶项目仓库') >= 0) throw new Error('仍保留数据里不存在的陌生仓库名');
});
/* 收尾：把所有筛选状态复位到默认（不影响后续分组） */
resetF(); clearPick();

console.log('\n=== 6. 设计一致性（设计规则中可机器校验的部分） ===');
/* 渲染一次全部视图；后面所有检查复用（避免重复渲染），并用**结构化 class 判断**替代裸 indexOf */
const vk = Object.keys(V), PH = {};
for (const k of vk) PH[k] = V[k]();
const hasCls = (h, name) => new RegExp('<[a-zA-Z][^>]*\\bclass="[^"]*\\b' + name + '\\b').test(h);
const pagesWith = name => vk.filter(k => hasCls(PH[k], name));
const setEq = (a, b) => a.length === b.length && a.every(x => b.indexOf(x) >= 0);
const allH = () => vk.map(k => PH[k]).join('');
/* 基线引导：基线为空或与实际不符时，把**实际值**写到 demo/_tmp_baseline.txt（UTF-8，可含中文），
   读出来贴回常量即可。这一步刻意保留 —— 改「页面集合」时必须有一次显式动作。 */
function bootstrap(name, actual) {
  const f = path.join(__dirname, '_tmp_baseline.txt');
  try { fs.writeFileSync(f, (fs.existsSync(f) ? fs.readFileSync(f, 'utf8') : '') + '\n[' + name + ']\n' + actual + '\n', 'utf8'); } catch (e) {}
  throw new Error('baseline mismatch -> demo/_tmp_baseline.txt');
}

/* ---------- R1｜页首说明折叠：**白名单式**（不再数"几个页面折叠了"） ----------
   旧写法 `detN === 14` 有两个坏处：① 删 A 页折叠 + 给 B 页加折叠 → 计数不变、规则已破却是绿的；
   ② 合法加页面必须改数字 → 养成"改数字让它变绿"的习惯。白名单式：加页面不用改，违规才红。
   ⚠️ **2026-09-14（看板改造）动了本基线**：看板原先整页享受"单行说明不折叠"的豁免；改造后**页内新增一处折叠**
   （`<details class="tip">` 包住「状态机汇总（§8.3）」规则表，为的是让首屏让给待办）
   ⇒ 本页**不再满足"整页保持展开"** ⇒ 从白名单里移出 `'home'`。
   ⚠️ 这不是"放宽"，而是把这条断言的白名单**改准**：移出后 R1 第 1 条反而开始**要求**看板有折叠块。
   ⇨ 判据没变：**白名单页 = 页首说明是单行短说明、且全页一处折叠都没有的页面**。 */
const DETAIL_EXPAND_OK = ['m10'];
guard('R1｜除白名单（MOD-10 整页即说明 / 看板单行说明）外，每个视图的长说明都已折叠为 <details>', () => {
  const bad = vk.filter(k => DETAIL_EXPAND_OK.indexOf(k) < 0 && PH[k].indexOf('<details') < 0);
  if (bad.length) throw new Error('not folded: ' + bad.join(','));
});
guard('R1｜白名单页必须保持展开（不被过度折叠）', () => {
  const bad = DETAIL_EXPAND_OK.filter(k => PH[k].indexOf('<details') >= 0);
  if (bad.length) throw new Error('over-folded: ' + bad.join(','));
});

/* ---------- R2｜指标区两形态：**集合包含**，不数数量 ---------- */
const KPIS_PAGES = ['home', 'm04', 'm05', 'm11'];
guard('R2｜大卡片 .kpis 只允许出现在 4 个「域级总览」页（集合包含 → 新页误用会红、加页面不用改断言）', () => {
  const bad = pagesWith('kpis').filter(k => KPIS_PAGES.indexOf(k) < 0);
  if (bad.length) throw new Error('kpis out of scope: ' + bad.join(','));
});
guard('R2｜白名单页确实用了 .kpis（防被悄悄拆掉）', () => {
  const bad = KPIS_PAGES.filter(k => !hasCls(PH[k], 'kpis'));
  if (bad.length) throw new Error('kpis missing: ' + bad.join(','));
});
/* 「`.selbar` 只允许出现在付款通知书页」这条断言已按用户要求撤掉（2026-09-12）。 */
ck('R2｜未引入替代大卡片的新组件（使用 .sum 的页面数应为 0）', pagesWith('sum').length, 0);

/* ---------- R4｜筛选栏：**等值白名单** ----------
   旧写法 `.fbar 页面数 >= 4` 留了宽容度：实测有 6 处、旧断言只要 ≥4 ⇒ 少一两页照样绿。 */
const FBAR_PAGES = ['m01', 'm03', 'm04', 'm05', 'm06', 'm07', 'm08', 'm09', 'm11', 'm12'];   /* 引导值：实测这 10 个列表 / 报表页（m09 为 2026-09-13 补「核算年月」新增；m07 同日补「收发结存核算年月」；m12 同日深夜补「差异登记筛选」⇒ 每次给页面加筛选栏都属"知情动作"，要显式更新本常量） */
guard('R4｜筛选栏 .fbar 的页面集合与基线一致（等值；旧的 "≥4" 漏掉"少了一页"）', () => {
  const got = pagesWith('fbar').sort();
  if (!FBAR_PAGES || !setEq(got, FBAR_PAGES)) bootstrap('FBAR_PAGES', JSON.stringify(got));
});

/* ---------- R10｜边界态：**四页各造一次真实空场景**（不是 grep 代码） ---------- */
guard('R10｜空态·MOD-03 无数据月份 → 提示行（真实空场景）', () => {
  /* ⚠️「无数据的月份」一律**派生**、不写死：演示数据一扩容，写死的月份就可能变成有数据
     （2026-09-13 把数据铺到 2026-01 时，原先写死的 2026-01 当场失效、本条报红）。 */
  let emptyM = '';
  for (let y = 2025; y <= 2027 && !emptyM; y++) for (let m = 1; m <= 12; m++) {
    const k = y + '-' + String(m).padStart(2, '0');
    if (H({ month: k }).length === 0) { emptyM = k; break; }
  }
  if (!emptyM) throw new Error('找不到任何无数据的月份 → 真实空场景无法构造');
  const bak = X.fNt.month; X.fNt.month = emptyM;
  let h = ''; try { h = V.m03(); } finally { X.fNt.month = bak; }
  if (h.indexOf('没有付款通知书') < 0) throw new Error('m03 empty-state missing');
});
guard('R10｜空态·MOD-01 筛选无结果 → 提示行（真实空场景）', () => {
  const bak = X.fPj.q; X.fPj.q = '__不存在的项目__';
  let h = ''; try { h = V.m01(); } finally { X.fPj.q = bak; }
  if (h.indexOf('没有项目档案') < 0) throw new Error('m01 empty-state missing');
});
guard('R10｜空态·MOD-05 逐月欠款台账无数据 → 提示行（真实空场景）', () => {
  /* 期初占位行撤卡后，MOD-05 的空态由「逐月欠款台账」承担：把所有数据源清掉造真实空场景 */
  const bN = X.NO.slice(), bM = JSON.stringify(X.MACH6), bL = X.LGs.slice();
  X.NO.length = 0; Object.keys(X.MACH6).forEach(k => delete X.MACH6[k]); X.LGs.length = 0;
  let h = ''; try { h = V.m05(); } finally {
    X.NO.length = 0; bN.forEach(v => X.NO.push(v));
    Object.keys(X.MACH6).forEach(k => delete X.MACH6[k]); Object.assign(X.MACH6, JSON.parse(bM));
    X.LGs.length = 0; bL.forEach(v => X.LGs.push(v));
  }
  if (h.indexOf('该项目在本口径下暂无数据') < 0) throw new Error('台账空态 missing');
});
guard('R10｜空态·MOD-08 库存单据清空 → 提示行（真实空场景）', () => {
  const bak = X.IVs.slice(); X.IVs.length = 0;
  let h = ''; try { h = V.m08(); } finally { bak.forEach(v => X.IVs.push(v)); }
  if (h.indexOf('没有库存单据明细') < 0) throw new Error('m08 empty-state missing');
});

/* ---------- R6｜年月组件统一 ---------- */
ck('R6｜统一「时间选择器」组件 `tmBtn` 用于「付款通知书筛选」，且顶栏已无全局年月控件（核算期概念已取消）',
  (hasCls(PH.m03, 'mpwrap') && html.indexOf('monthSlot') < 0) ? 1 : 0, 1);

/* ---------- 组件级一致性（R7 表格 / R11 颜色 / R12 排版）----------
   只新增「白名单式」检查：跑得绿、且以后有人新造变体就会红。不数数量。 */
const btnTokens = () => [...new Set([...allH().matchAll(/class="(btn[^"]*)"/g)].map(m => m[1])
  .filter(c => c.indexOf('$') < 0).flatMap(c => c.split(/\s+/)).filter(t => t))];
const tagTokens = () => [...new Set([...allH().matchAll(/class="(tag[^"]*)"/g)].map(m => m[1])
  .filter(c => c.indexOf('$') < 0).flatMap(c => c.split(/\s+/)).filter(t => t))];
guard('R12｜按钮只用既有变体（btn / sm / pri / dg / gost），不新造 ad-hoc 样式', () => {
  const TOK = ['btn', 'sm', 'pri', 'dg', 'gost'];
  const bad = btnTokens().filter(t => TOK.indexOf(t) < 0);
  if (bad.length) throw new Error('unknown btn token: ' + bad.join(','));
});
guard('R11｜标签只用既有语义色（wn / ok / dg / in / pri / vi）', () => {
  const TOK = ['tag', 't-wn', 't-ok', 't-dg', 't-in', 't-pri', 't-vi'];
  const bad = tagTokens().filter(t => TOK.indexOf(t) < 0);
  if (bad.length) throw new Error('unknown tag color: ' + bad.join(','));
});
guard('R11｜内联样式不得写死色值（允许清单外一律禁止；现有 3 处浮层色已登记待 token 化）', () => {
  const KNOWN = ['#fff', '#0f172a26', '#475569'];
  const got = [...new Set([...allH().matchAll(/style="[^"]*?(#[0-9a-fA-F]{3,8})/g)].map(m => m[1]))];
  const bad = got.filter(c => KNOWN.indexOf(c) < 0);
  if (bad.length) throw new Error('new hardcoded color: ' + bad.join(','));
});

/* ---------- R13｜表头排序：改成**规则式**（不再数"全站几张表标了 data-sort"）----------
   按页遍历（可定位到具体页面），并用"括号配对"方式取表格，避免嵌套表把匹配截断。 */
const tablesOf = () => {
  const out = [];
  for (const k of vk) {
    const h = PH[k]; let i = 0;
    while ((i = h.indexOf('<table', i)) >= 0) {
      const gt = h.indexOf('>', i), open = h.slice(i, gt + 1);
      let depth = 1, j = gt + 1;
      while (depth > 0 && j < h.length) {
        const nt = h.indexOf('<table', j), ct = h.indexOf('</table>', j);
        if (ct < 0) break;
        if (nt >= 0 && nt < ct) { depth++; j = nt + 6; } else { depth--; j = ct + 8; }
      }
      out.push({ page: k, open, inner: h.slice(gt + 1, j - 8) });
      i = j;
    }
  }
  return out;
};
const isDt = t => /\bclass="[^"]*\bdt\b/.test(t.open);
const sortable = t => /\bdata-sort\b/.test(t.open);
const hasHead = t => t.inner.indexOf('<thead') >= 0;
const TABLES = tablesOf();
guard('R13｜凡标了 data-sort 的表都必须是数据表（.dt）且含 <thead> —— 防止把说明/规则表标成"可排"', () => {
  const bad = TABLES.filter(t => sortable(t) && (!isDt(t) || !hasHead(t)));
  if (bad.length) throw new Error('bad sortable: ' + bad.map(t => t.page).join(','));
});
/* ⚠️ 实测发现：**`.dt` 不等于"数据列表"** —— 说明表 / 规则表也借 `.dt` 的边框样式（如 MOD-02 接口清单、MOD-14 规则表）。
   所以 R13 的"覆盖完整性"**不能拿 `.dt` 当判据**；改为「**例外白名单**」：未标 data-sort 的 `.dt` 表，
   只允许出现在下面这些页（那里是说明/规则表）；**新页面或数据页出现未标表 → 红**。 */
const UNSORTABLE_OK_PAGES = ['home', 'm01', 'm02', 'm06', 'm13', 'm14'];
guard('R13｜未标 data-sort 的 .dt 表只允许出现在「说明/规则表所在页」（新页或数据页出现未标表 → 红）', () => {
  const bad = [...new Set(TABLES.filter(t => isDt(t) && hasHead(t) && !sortable(t)).map(t => t.page))]
    .filter(p => UNSORTABLE_OK_PAGES.indexOf(p) < 0);
  if (bad.length) throw new Error('unmarked dt on: ' + bad.join(','));
});
/* 数字只作为**信息**打印，不作为断言 —— 这样加页面/加表时不必改任何数字 */
console.log('   [info] 页内可排序表 = ' + TABLES.filter(sortable).length + ' 张 · 未标 data-sort 的 .dt 表 = '
  + TABLES.filter(t => isDt(t) && hasHead(t) && !sortable(t)).length + ' 张（说明/规则类）');

/* 「MOD-03 冻结页」的两道机器守护（`M03_SIG` 接口签名 / `SELBAR_CSS` 的 CSS 契约）**已撤掉**（2026-09-12）。
   原因：用户澄清当初只说过一句「你怎么动我付款通知书页面了？退回去」——**原意只是把改动退回**，
   立"铁律"与加机器守护都是 AI 自行加码的；用户要求撤掉，故本条与相关断言一并移除。 */

resetF();   /* 以上检查动过筛选状态，复位 */


console.log('\n=== 7. 批量付款与撤销（异步路径） ===');
clearPick(); pick('N05');
doc.querySelector('#bm0').value = '现汇';
doc.querySelector('#ba0').value = '96400.00';
doc.querySelector('#bRemark').value = '';
doc.querySelector('#bDate').value = '2026-09-12';
const flBefore = X.FLs.length;
ACT.batchPayOk({ dataset: {}, tagName: 'BUTTON' });

setTimeout(() => {
  ck('批量付款：正常路径写入 1 条流水', X.FLs.length, flBefore + 1);
  ck('批量付款：流水金额 = 可付余额 96400（审批金额 96400 − 已付 0）', X.FLs[X.FLs.length - 1].amt, 96400.00);
  ck('批量付款：N05 转为已付清', X.statOf(X.NO.find(n => n.id === 'N05')) === '已付清' ? 1 : 0, 1);
  const fid = X.FLs[X.FLs.length - 1].id;
  doc.querySelector('#rReason').value = '测试撤销原因';
  ACT.revOk({ dataset: { fid }, tagName: 'BUTTON' });
  ck('撤销：流水被标记已撤销并留原因', (X.FLs.find(f => f.id === fid).voided && X.FLs.find(f => f.id === fid).reason === '测试撤销原因') ? 1 : 0, 1);
  ck('撤销：通知书已付金额回退 → 未付清', X.statOf(X.NO.find(n => n.id === 'N05')) === '未付清' ? 1 : 0, 1);
  ck('撤销：已付金额归零', X.paidOf('N05'), 0);

  /* ================= MOD-04 付款计划：筛选 / 多选删除 / 选月份导入 ================= */
  console.log('\n--- 9y. MOD-04 付款计划（筛选 · 多选 · 按月导入） ---');
  ck('项目多选面板为共用实现（MOD-03 传 pjPick、MOD-04 传 plPjPick，同一个 projPanel 两个 cfg）',
    (html.indexOf("pickAct:'pjPick'") >= 0 && html.indexOf("pickAct:'plPjPick'") >= 0) ? 1 : 0, 1);
  ck('PL 数据已带「年月」字段（YYYY-MM）', X.PLs.every(p => /^\d{4}-\d{2}$/.test(String(p.ym || ''))) ? 1 : 0, 1);
  ck('付款计划默认筛选年月 = 北京时间当月（bjMonth()）', X.plf.ym === X.bjMonth() ? 1 : 0, 1);
  ck('审查结果默认 = 全部', X.plf.review === '全部' ? 1 : 0, 1);
  ck('MOD-04 筛选 / 多选 / 逐行删除 / 行内改列 / 再次匹配 / 手动行动作齐全',
    ['plFilter', 'plFilterReset', 'plPjToggle', 'plPjPick', 'plPjAll', 'plPjNone', 'plPick', 'plPickAll', 'plDel', 'plDelOk',
      'plDelRow', 'plDelRowOk', 'plCell', 'plRematch', 'unforce', 'plImport', 'plImportOk',
      'plRowAdd', 'plRowSet', 'plRowEdit', 'plRowSave', 'plRowCancel']
      .every(a => typeof ACT[a] === 'function') ? 1 : 0, 1);
  ck('付款计划项目候选 = 计划行能匹配到的项目（展示名，去重）**含归档**、归档排最后', (function () {
    const list = X.PL_PROJ_LIST();
    const expect = [...new Set(X.PLs.map(p => X.plProjKey(p.proj)).filter(Boolean))];
    const allHaveRec = list.every(d => X.PJs.some(p => p.type !== 'shell' && p.name === d));   /* 键 = 仓库名 */
    const isArc = v => X.arcOf(X.pjRowOf(v));
    const i = list.findIndex(isArc);
    const arcLast = (i < 0) || list.slice(i).every(isArc);
    return (list.length > 0 && list.length === expect.length && expect.every(d => list.indexOf(d) >= 0) && allHaveRec && arcLast) ? 1 : 0;
  })(), 1);
  /* —— 「项目」列 = 用户填的展示名 / 仓库名，系统按此匹配档案（不是全名）—— */
  ck('付款计划「项目」列按【展示名或仓库名】匹配档案，全名不作匹配键', (function () {
    const P01 = X.PJs.find(p => p.id === 'P01');
    if (X.plProjOne('德州热电') !== P01) return 0;                          /* 展示名 */
    if (X.plProjOne('华能德州热电联产项目仓库') !== P01) return 0;          /* 仓库名 */
    if (X.plProjOne('华能德州热电联产项目#2机组建筑及安装工程')) return 0; /* 全名不算 */
    return 1;
  })(), 1);
  ck('两种填法归到同一个项目（展示名 / 仓库名 → 同一筛选键）', (function () {
    const a = X.plProjKey('德州热电'), b = X.plProjKey('华能德州热电联产项目仓库');
    return (a && a === b) ? 1 : 0;
  })(), 1);
  ck('填了档案里没有的项目名 → 不猜、标「未匹配」（PL14 菏泽热电二期）',
    X.plProjHit(X.PLs.find(p => p.id === 'PL14').proj).length === 0 ? 1 : 0, 1);
  ck('列头写明填报口径（项目列 = 展示名 / 仓库名）',
    V.m04().indexOf('项目（填报：展示名 / 仓库名）') >= 0 ? 1 : 0, 1);
  ck('「项目」列显示规范展示名、未匹配行标红（填报值仍在悬停里）', (function () {
    const h = V.m04();
    const row = h.split('<tr class=').find(r => r.indexOf('>PL05<') >= 0) || '';   /* PL05 填的是仓库名 */
    const bad = h.split('<tr class=').find(r => r.indexOf('>PL14<') >= 0) || '';   /* PL14 填了不存在的名字 */
    return (row.indexOf('漯河供热') >= 0 && row.indexOf('河南漯河食品产业园供热项目仓库') >= 0
      && bad.indexOf('未匹配') >= 0) ? 1 : 0;
  })(), 1);
  ck('付款计划页渲染三项筛选控件（单据年月 / 项目多选 / 审查结果）', (function () {
    const h = V.m04();
    return (h.indexOf('data-id="plMonth"') >= 0 && h.indexOf('plPjToggle') >= 0 && h.indexOf('id="plReview"') >= 0) ? 1 : 0;
  })(), 1);
  /* —— 审查引擎（2026-09-12 新增：审查结果改为实时比对，不再存字段）—— */
  ck('审查结果不再存字段（`PL_COLS` 无 review，改为 `plRev()` 实时派生）', (function () {
    return (X.PLs.length > 0 && X.PLs[0].review === undefined && typeof X.plRev === 'function') ? 1 : 0;
  })(), 1);
  ck('审查引擎：6 种结果都有样本（完全匹配/金额不符/单据号查不到/无单据号/重复上报/超过未付）',
    new Set(X.PLs.map(p => X.plRev(p, X.PLs))).size, 6);
  ck('同月同一单据号 → 两行都判「重复上报」（PL06 / PL07 除 id 外完全相同）',
    (X.plRev(X.PLs.find(p => p.id === 'PL06'), X.PLs) === '重复上报'
      && X.plRev(X.PLs.find(p => p.id === 'PL07'), X.PLs) === '重复上报') ? 1 : 0, 1);
  ck('空单据号不参与判重（PL14 判「无单据号」，不判重复）',
    X.plRev(X.PLs.find(p => p.id === 'PL14'), X.PLs) === '无单据号' ? 1 : 0, 1);
  ck('「超过未付」= 本月预付款金额 >（审批金额 − 已付金额）：PL05 报 70000 > 未付 67800',
    X.plRev(X.PLs.find(p => p.id === 'PL05'), X.PLs) === '超过未付' ? 1 : 0, 1);
  ck('「金额不符」比的是「该流程金额 ↔ 通知书审批金额」（PL02 抄成 53800 ≠ 54300）',
    X.plRev(X.PLs.find(p => p.id === 'PL02'), X.PLs) === '金额不符' ? 1 : 0, 1);
  ck('「完全匹配」= 单据号对得上 且 该流程金额 = 审批金额 且 不超未付（PL11）',
    X.plRev(X.PLs.find(p => p.id === 'PL11'), X.PLs) === '完全匹配' ? 1 : 0, 1);
  /* —— 审查结果的「筛选两档」：判定仍 6 种，筛选下拉只给 完全匹配 / 未匹配 —— */
  ck('审查结果筛选下拉只两档（全部 / 完全匹配 / 未匹配），不再逐种列 6 项', (function () {
    const m = V.m04().match(/<select class="inp" id="plReview"[^>]*>([\s\S]*?)<\/select>/);
    const sel = m ? m[1] : '';
    return (sel.indexOf('>未匹配<') >= 0 && sel.indexOf('>完全匹配<') >= 0
      && sel.indexOf('>金额不符<') < 0 && sel.indexOf('>超过未付<') < 0) ? 1 : 0;
  })(), 1);
  ck('「未匹配」= 除「完全匹配」以外的全部判定（`revIs` 归并；判定本身仍是 6 种）', (function () {
    const p = X.PLs.find(x => x.id === 'PL02');
    return (X.revIs(X.plRev(p, X.PLs), '未匹配') === true
      && X.revIs('完全匹配', '未匹配') === false
      && X.revIs('完全匹配', '完全匹配') === true) ? 1 : 0;
  })(), 1);
  guard('付款计划：审查结果筛选生效（选「未匹配」只剩非「完全匹配」的行）', () => {
    doc.querySelector('#plReview').value = '未匹配';
    ACT.plFilter({ dataset: {}, tagName: 'SELECT' });
    const vis = X.plVisible();
    if (!vis.length || !vis.every(p => X.plRev(p, X.PLs) !== '完全匹配')) throw new Error('筛选未生效');
  });
  /* —— 新增列：已付款金额 / 剩余付款金额（按单据号命中 i8 通知书后派生）—— */
  ck('新增两列取自 i8 通知书：已付款金额 = 已付（流水汇总）、剩余付款金额 = 未付（审批 − 已付）',
    (function () {
      const n1 = X.plHit(X.PLs.find(p => p.id === 'PL01'));   /* → N19：审批 86200 / 有流水 86200 */
      const n2 = X.plHit(X.PLs.find(p => p.id === 'PL03'));   /* → N24：审批 86800 / 无流水 */
      if (!n1 || !n2) return 0;
      return (X.paidOf(n1.id) === 86200 && X.N2(n1.approve - X.paidOf(n1.id)) === 0
        && X.paidOf(n2.id) === 0 && X.N2(n2.approve - X.paidOf(n2.id)) === 86800) ? 1 : 0;
    })(), 1);
  ck('单据号未命中 → 两列无值（不猜、不留假数据）',
    (X.plHit(X.PLs.find(p => p.id === 'PL14')) === null && X.plHit(X.PLs.find(p => p.id === 'PL13')) === null) ? 1 : 0, 1);
  ck('两列插在「i8 流程金额」与「本月预付款金额」之间（列序）', (function () {
    const m = V.m04().match(/<thead>[\s\S]*?<\/thead>/); const th = m ? m[0] : '';
    const i1 = th.indexOf('i8 流程金额'), i2 = th.indexOf('已付款金额'), i3 = th.indexOf('剩余付款金额'), i4 = th.indexOf('本月预付款金额');
    return (i1 >= 0 && i1 < i2 && i2 < i3 && i3 < i4) ? 1 : 0;
  })(), 1);
  ck('项目列已改为「展示名」（列头 + 取值），全名不再出现在该列', (function () {
    const h = V.m04();
    return (h.indexOf('项目（填报：展示名 / 仓库名）') >= 0 && h.indexOf('项目（全名）') < 0
      && h.indexOf('title="项目全名：') < 0 && h.indexOf('德州热电') >= 0) ? 1 : 0;
  })(), 1);
  /* —— 新增：行内可改列（付款时间 / 付款方式 / 备注 / 未匹配行的单据号）—— */
  guard('付款计划：付款时间 / 付款方式 / 备注 行内可改并立刻落库（不留痕）', () => {
    const p = X.PLs.find(x => x.id === 'PL11');
    ACT.plCell({ dataset: { id: 'PL11', f: 'date' }, tagName: 'INPUT', value: '2026-09-30' });
    ACT.plCell({ dataset: { id: 'PL11', f: 'method' }, tagName: 'SELECT', value: '承兑' });
    ACT.plCell({ dataset: { id: 'PL11', f: 'remark' }, tagName: 'INPUT', value: '已核对' });
    if (p.date !== '2026-09-30' || p.method !== '承兑' || p.remark !== '已核对') throw new Error('手改未落库');
    if (p.trail) throw new Error('这几列按定案不留痕，不应出现 trail');
  });
  ck('单据号只对「未匹配」行开放编辑（「完全匹配」行只读）', (function () {
    const h = V.m04();
    const rowOf = id => h.split('<tr class=').find(r => r.indexOf('>' + id + '<') >= 0) || '';
    const ro = rowOf('PL11'), ed = rowOf('PL14');
    return (ro.indexOf('data-f="docNo"') < 0 && ed.indexOf('data-f="docNo"') >= 0) ? 1 : 0;
  })(), 1);
  guard('付款计划：未匹配行改单据号后「再次匹配」重判为「完全匹配」', () => {
    const p = X.PLs.find(x => x.id === 'PL14');           /* 原「无单据号」；流程金额 268400 */
    if (X.plRev(p, X.PLs) !== '无单据号') throw new Error('样本前置条件不成立');
    ACT.plCell({ dataset: { id: 'PL14', f: 'docNo' }, tagName: 'INPUT', value: 'JC-202609-04' });
    if (X.plRev(p, X.PLs) !== '完全匹配') throw new Error('改后应判「完全匹配」，实际：' + X.plRev(p, X.PLs));
    ACT.plRematch({ dataset: { id: 'PL14' }, tagName: 'BUTTON' });
  });
  /* —— 新增：强制通过 → 取消强制通过 —— */
  guard('付款计划：强制通过后可取消（回到「未处理」并清空备注，不留残余）', () => {
    doc.querySelector('#fRemark').value = '已向项目核实，金额无误';
    ACT.force({ dataset: { id: 'PL05' }, tagName: 'BUTTON' });
    ACT.forceOk({ dataset: { id: 'PL05' }, tagName: 'BUTTON' });
    const p = X.PLs.find(x => x.id === 'PL05');
    if (!p.forced || !p.forceRemark) throw new Error('未进入「已强制通过」');
    ACT.unforce({ dataset: { id: 'PL05' }, tagName: 'BUTTON' });
    if (p.forced || p.forceRemark !== '') throw new Error('取消强制通过 / 清空备注未生效');
    if (X.plRev(p, X.PLs) !== '超过未付') throw new Error('取消后审查结果应回到原判定');
  });
  /* —— 新增：逐行删除（与批量删除同款确认，删后同步移出勾选集合）—— */
  guard('付款计划：逐行删除只删该行（行数与勾选集合同步收敛）', () => {
    const n0 = X.PLs.length, id = 'PL09';
    ACT.plPick({ dataset: { id }, tagName: 'INPUT' });
    if (!X.plPick.has(id)) throw new Error('前置勾选失败');
    ACT.plDelRowOk({ dataset: { id }, tagName: 'BUTTON' });
    if (X.PLs.length !== n0 - 1) throw new Error('行数不对：' + X.PLs.length);
    if (X.PLs.some(p => p.id === id)) throw new Error('该行仍在表里');
    if (X.plPick.has(id)) throw new Error('勾选集合未移除该行');
  });
  guard('付款计划：多选删除只删勾选行（其余不受影响）', () => {
    const n0 = X.PLs.length;
    doc.querySelector('#plReview').value = '全部';
    ACT.plFilter({ dataset: {}, tagName: 'SELECT' });
    const ids = X.plVisible().slice(0, 2).map(p => p.id);
    ids.forEach(id => ACT.plPick({ dataset: { id }, tagName: 'INPUT' }));
    if (X.plPick.size !== 2) throw new Error('未勾选到 2 行');
    ACT.plDelOk({ dataset: {}, tagName: 'BUTTON' });
    if (X.PLs.length !== n0 - 2) throw new Error('删除行数不对：' + X.PLs.length);
    if (X.plPick.size !== 0) throw new Error('勾选集合未清空');
    if (ids.some(id => X.PLs.some(p => p.id === id))) throw new Error('勾选行仍在表里');
  });
  guard('付款计划：导入 = 先选月份（本批全归该月）+ 完全相同行不被覆盖', () => {
    const n0 = X.PLs.length, m = '2026-08';
    X.setPlImportM(m);
    ACT.plImportOk({ dataset: {}, tagName: 'BUTTON' });
    if (X.PLs.length !== n0 + 3) throw new Error('导入行数不对：' + (X.PLs.length - n0));
    const added = X.PLs.slice(n0);
    if (!added.every(p => p.ym === m)) throw new Error('导入行未归入所选月份');
    const strip = p => JSON.stringify(Object.assign({}, p, { id: '' }));
    if (strip(added[0]) !== strip(added[2])) throw new Error('「完全相同的行」被改动（应原样保留、不去重）');
    if (X.plf.ym !== m) throw new Error('导入后未切到该月（应能立刻看到本批）');
  });
  guard('付款计划：筛选变化后勾选集合被裁剪到可见范围', () => {
    X.plVisible().slice(0, 2).forEach(p => ACT.plPick({ dataset: { id: p.id }, tagName: 'INPUT' }));
    if (X.plPick.size !== 2) throw new Error('未勾选到 2 行');
    doc.querySelector('#plReview').value = '完全匹配';
    ACT.plFilter({ dataset: {}, tagName: 'SELECT' });
    if (X.plPick.size !== 0) throw new Error('勾选未被裁剪：' + X.plPick.size);
  });
  /* 复位付款计划筛选状态（原地改字段 / 清空，保引用不变） */
  X.plf.ym = X.bjMonth(); X.plf.projs = []; X.plf.review = '全部'; X.plPick.clear();

  /* ================= MOD-05 · 逐月欠款台账（按项目 · 按月一行） ================= */
  /* ================= MOD-04 **手动行**（§4.3.3.1 · 2026-09-16 用户口述新增 + 同日追认细节 6 项）=================
     用户原话：「付款计划要手动行，**而且手动行一样要被审查**」⇒ 本组守的核心 = **手动行与导入行走同一条链路**：
     判定按行实时派生、**不看来源**；计入合计与 KPI；**导入不清理它**（§9.5）；**只有手动行可编辑**，
     而**删除所有行都有**（§4.3.6 —— 与付款通知书「i8 抓取行永不删」不同，不得照抄）。 */
  console.log('\n--- 9y2. MOD-04 手动行（表内增行 · 与导入行同一条审查链路） ---');
  ck('`PL_COLS` 带 `manual` 列（手动行标记；与 MOD-03 的 `NT_COLS.manual` 同名同义）',
    X.PL_COLS.indexOf('manual') >= 0 ? 1 : 0, 1);
  ck('演示数据里有手动行样本（PL15）', X.PLs.filter(p => p.manual === true).length >= 1 ? 1 : 0, 1);
  ck('手动行动作齐全（新增 / 逐格填 / 编辑 / 保存 / 取消）',
    ['plRowAdd', 'plRowSet', 'plRowEdit', 'plRowSave', 'plRowCancel'].every(a => typeof ACT[a] === 'function') ? 1 : 0, 1);
  ck('`plRowSet` 由 `change` 委托承接（`#2` 起不再靠 `CHG` 登记；表单元素按种类自动跑）',
    !!X.ACT.plRowSet ? 1 : 0, 1);
  /* ⭐⭐ 核心：#1「一样要被审查」—— 同数据、**只把来源改成"导入"** ⇒ 判定必须一模一样 */
  guard('⭐ 手动行与导入行「同一条审查链路」：同数据只差来源 ⇒ 判定完全一致（判定按行实时派生、不看来源）', () => {
    const m = X.PLs.find(p => p.manual === true);
    if (!m) throw new Error('没有手动行样本');
    const asImport = Object.assign({}, m, { id: '@probe-import', manual: false });   /* 唯一差别 = 来源 */
    const a = X.plRev(m, X.PLs), b = X.plRev(asImport, [...X.PLs, asImport]);
    if (a !== b) throw new Error('判定因来源而不同：手动 ' + a + ' vs 导入 ' + b);
  });
  guard('⭐ 手动行**计入表内合计**（全表合计 − 不含该行的合计 = 该行金额，独立复算；按**引用**排除，避免 id 撞号）', () => {
    const m = X.PLs.find(p => p.manual === true);
    const sum = rows => X.N2(rows.reduce((a, p) => a + p.flowAmt, 0));
    const diff = X.N2(sum(X.PLs) - sum(X.PLs.filter(p => p !== m)));
    const diag = 'manual 行 = ' + X.PLs.filter(p => p.manual === true).map(p => p.id).join(',')
      + ' ｜ 共 ' + X.PLs.length + ' 行 ｜ id 重复：'
      + X.PLs.map(p => p.id).filter((v, i, a) => a.indexOf(v) !== i).join(',');
    if (diff !== X.N2(m.flowAmt)) throw new Error('手动行未计入合计（差 ' + diff + '，应 ' + X.N2(m.flowAmt) + '；' + diag + '）');
    if (String(V.m04()).indexOf('>' + m.id + ' ') < 0) throw new Error('手动行未出现在列表页（' + diag + '）');
  });
  ck('行上「手动」徽标：手动行有、导入行没有',
    (function () {
      const h = V.m04();
      const rowOf = id => h.split('<tr class=').find(r => r.indexOf('>' + id + ' ') >= 0 || r.indexOf('>' + id + '<') >= 0) || '';
      return (rowOf('PL15').indexOf('手动</span>') >= 0 && rowOf('PL11').indexOf('手动</span>') < 0) ? 1 : 0;
    })(), 1);
  ck('「编辑」入口**只在手动行**上（导入行是项目端报来的源数据：要改请重新导入）',
    (function () {
      const h = V.m04();
      const rowOf = id => h.split('<tr class=').find(r => r.indexOf('>' + id + ' ') >= 0 || r.indexOf('>' + id + '<') >= 0) || '';
      return (rowOf('PL15').indexOf('data-act="plRowEdit"') >= 0 && rowOf('PL11').indexOf('data-act="plRowEdit"') < 0) ? 1 : 0;
    })(), 1);
  ck('「删除」**所有行都有**（手动行与导入行都可删 —— 与付款通知书「i8 抓取行永不删」不同）',
    (function () {
      const h = V.m04();
      const rowOf = id => h.split('<tr class=').find(r => r.indexOf('>' + id + ' ') >= 0 || r.indexOf('>' + id + '<') >= 0) || '';
      return (rowOf('PL15').indexOf('data-act="plDelRow"') >= 0 && rowOf('PL11').indexOf('data-act="plDelRow"') >= 0) ? 1 : 0;
    })(), 1);
  guard('页头有「＋ 手动新增计划行」入口（不依赖 Excel 的补录入口）', () => {
    if (String(V.m04()).indexOf('data-act="plRowAdd"') < 0) throw new Error('页头没有手动新增入口');
  });
  /* —— 草稿行（照 MOD-03 增行模式的形态）：列对齐 + 钉在「数据行之后、合计行之前」+ 不带 data-id —— */
  guard('草稿行：列数 = **表头 th 数**（独立数表头，不借 thCount 自证）+ 钉在「数据行之后、合计行之前」+ 不带 data-id（不污染合计断言）', () => {
    X.setPlRow({ id: '', d: {} });
    ACT.plRowAdd({ dataset: {}, tagName: 'BUTTON' });
    const h = String(V.m04());
    const tbl = (h.match(/<table\b[^>]*data-sort-key="m04:plans"[\s\S]*?<\/table>/) || [''])[0];
    const draft = (tbl.match(/<tr class="draftrow">[\s\S]*?<\/tr>/) || [''])[0];
    const back = () => X.setPlRow({ id: '', d: {} });
    if (!draft) { back(); throw new Error('草稿行未渲染 / 未带 draftrow 类'); }
    const nTh = ((tbl.match(/<thead\b[\s\S]*?<\/thead>/i) || [''])[0].match(/<th\b/g) || []).length;
    const nTd = (draft.match(/<td\b/g) || []).length;
    if (nTd !== nTh) { back(); throw new Error('草稿行列数 ' + nTd + ' ≠ 表头列数 ' + nTh); }
    if (draft.indexOf('data-id=') >= 0) { back(); throw new Error('草稿行不得带 data-id（会污染合计行的独立复算）'); }
    const iDraft = tbl.indexOf('draftrow'), iSum = tbl.indexOf('sumrow');
    if (iDraft < 0 || iSum < 0 || iDraft > iSum) { back(); throw new Error('草稿行未落在「数据行之后、合计行之前」'); }
    back();
  });
  guard('保存：填完必填 ⇒ 落库且 `manual=true`，并**立即进入同一条审查链路**（判定实时派生 + 计入合计）', () => {
    const ym0 = X.plf.ym;      /* 保存会切筛选（"保证看得见"）⇒ 断言结束还原，免得影响后续按筛选渲染的断言 */
    rollback(); X.setPlRow({ id: '', d: {} });
    const n0 = X.PLs.length;
    ACT.plRowAdd({ dataset: {}, tagName: 'BUTTON' });
    ACT.plRowSet({ dataset: { k: 'ym' }, value: '2026-09', tagName: 'INPUT' });
    ACT.plRowSet({ dataset: { k: 'proj' }, value: '德州热电', tagName: 'SELECT' });
    ACT.plRowSet({ dataset: { k: 'docNo' }, value: '', tagName: 'INPUT' });      /* 空单据号：允许（§4.3.3.1） */
    ACT.plRowSet({ dataset: { k: 'flowAmt' }, value: '12345', tagName: 'INPUT' });
    ACT.plRowSet({ dataset: { k: 'monthAmt' }, value: '12345', tagName: 'INPUT' });
    ACT.plRowSave({ dataset: {}, tagName: 'BUTTON' });
    if (X.PLs.length !== n0 + 1) throw new Error('保存后未落库（行数 ' + X.PLs.length + '）');
    const p = X.PLs[X.PLs.length - 1];
    if (p.manual !== true) throw new Error('新行未标 manual');
    if (X.plRowOn()) throw new Error('保存后增行态未复位');
    if (X.plRev(p, X.PLs) !== '无单据号') throw new Error('空单据号应判「无单据号」，实际：' + X.plRev(p, X.PLs));
    if (X.PLs.filter(x => x.ym === '2026-09').reduce((a, x) => a + x.flowAmt, 0) < 12345) throw new Error('未计入合计');
    rollback(); X.setPlRow({ id: '', d: {} }); X.plf.ym = ym0;
  });
  guard('校验失败（年月空）⇒ **显式拦住 + 草稿行与已填内容都保留**（§4.3.3.1：不清空重填）', () => {
    X.setPlRow({ id: '', d: {} });
    ACT.plRowAdd({ dataset: {}, tagName: 'BUTTON' });
    ACT.plRowSet({ dataset: { k: 'docNo' }, value: 'SD-KEEP-ME', tagName: 'INPUT' });
    ACT.plRowSet({ dataset: { k: 'ym' }, value: '', tagName: 'INPUT' });
    const n0 = X.PLs.length;
    ACT.plRowSave({ dataset: {}, tagName: 'BUTTON' });
    const st = X.plRowState();
    const back = () => X.setPlRow({ id: '', d: {} });
    if (X.PLs.length !== n0) { back(); throw new Error('校验失败仍落了库'); }
    if (st.id === '') { back(); throw new Error('校验失败后草稿行被丢弃（应保留）'); }
    if (st.d.docNo !== 'SD-KEEP-ME') { back(); throw new Error('校验失败后已填内容被清空'); }
    back();
  });
  guard('编辑只对手动行开放：对**导入行**请求编辑 ⇒ 不进编辑态（显式说明，不静默、不当成新增）', () => {
    X.setPlRow({ id: '', d: {} });
    ACT.plRowEdit({ dataset: { id: 'PL11' }, tagName: 'BUTTON' });     /* PL11 = 导入行 */
    if (X.plRowState().id !== '') { X.setPlRow({ id: '', d: {} }); throw new Error('导入行竟进入了编辑态'); }
    ACT.plRowEdit({ dataset: { id: 'PL15' }, tagName: 'BUTTON' });     /* PL15 = 手动行 */
    if (X.plRowState().id !== 'PL15') { X.setPlRow({ id: '', d: {} }); throw new Error('手动行未能进入编辑态'); }
    if (String(V.m04()).indexOf('draftrow') < 0) { X.setPlRow({ id: '', d: {} }); throw new Error('编辑中该行未**原地变草稿行**'); }
    ACT.plRowCancel({ dataset: {}, tagName: 'BUTTON' });
    if (X.plRowState().id !== '') throw new Error('取消后编辑态未复位');
  });
  guard('取消：草稿行丢弃、**不写入任何数据**（新增态与编辑态都试）', () => {
    rollback(); X.setPlRow({ id: '', d: {} });
    const n0 = X.PLs.length, before = JSON.stringify(X.PLs);
    ACT.plRowAdd({ dataset: {}, tagName: 'BUTTON' });
    ACT.plRowSet({ dataset: { k: 'docNo' }, value: 'SD-CANCEL', tagName: 'INPUT' });
    ACT.plRowCancel({ dataset: {}, tagName: 'BUTTON' });
    if (X.PLs.length !== n0 || JSON.stringify(X.PLs) !== before) throw new Error('新增后取消，数据被改动');
    ACT.plRowEdit({ dataset: { id: 'PL15' }, tagName: 'BUTTON' });
    ACT.plRowSet({ dataset: { k: 'remark' }, value: '不该保存' });
    ACT.plRowCancel({ dataset: {}, tagName: 'BUTTON' });
    if (JSON.stringify(X.PLs) !== before) throw new Error('编辑后取消，数据仍被改（应保持原样）');
    rollback(); X.setPlRow({ id: '', d: {} });
  });
  /* —— 编号生成：**唯一出口 `plNextIds`**（2026-09-16 修「数长度 ⇒ 删行后撞号」）—— */
  ck('编号生成走**唯一出口** `plNextIds`：取「当前最大编号 + 1」（**不看数组长度**）', (function () {
    const ids = X.plNextIds('PL', 3);
    const mx = X.PLs.reduce((a, p) => {
      const n = Number(String(p.id).replace(/^PL/, ''));
      return Number.isFinite(n) ? Math.max(a, n) : a;
    }, 0);
    return (ids.length === 3 && ids[0] === 'PL' + String(mx + 1).padStart(2, '0')
      && ids[2] === 'PL' + String(mx + 3).padStart(2, '0')) ? 1 : 0;
  })(), 1);
  guard('⭐ **删过行之后再导入不撞号**（原按 `PLs.length+1` 生成 ⇒ 与既有 id 重复 ⇒ `find(id)` 会命中错行）', () => {
    /* ⚠️ `plImportOk` 会把 `plf.ym` 切到**导入月份** ⇒ 断言结束**必须还原**：
       否则后续"按当前筛选渲染"的断言（如设计一致性的 `type=date` 那条）会看到**空列表**而**假红**（实测踩到）。 */
    const ym0 = X.plf.ym;
    rollback(); X.setPlRow({ id: '', d: {} });
    ACT.plImportOk({ dataset: {}, tagName: 'BUTTON' });
    /* 前置条件构造：**删掉一行** —— 这正是让"数长度"方案失效的那个动作（此处直接改数组，不经删除动作） */
    X.PLs.splice(X.PLs.length - 2, 1);
    ACT.plImportOk({ dataset: {}, tagName: 'BUTTON' });
    const ids = X.PLs.map(p => String(p.id));
    const dup = ids.filter((v, i) => ids.indexOf(v) !== i);
    rollback(); X.setPlRow({ id: '', d: {} }); X.plf.ym = ym0;
    if (dup.length) throw new Error('导入产生重复 id：' + dup.join('、'));
  });
  console.log('\n--- 9z. MOD-05 逐月欠款台账（合并成一张卡的左右两栏 · 同一套逻辑） ---');
  ck('台账：动作齐全（选项目 / 机械手填 / 备注 / 录入期初 / **导出（2026-09-13 起一个入口 + 多选项目）**）',
    ['ledPjPick', 'ledPjToggle', 'ledNote', 'addLg', 'ledExpToggle', 'ledExpOk', 'ledExpCancel'].every(a => typeof ACT[a] === 'function') ? 1 : 0, 1);
  ck('台账：**与两侧台账卡合并为一张卡**（卡头放两侧共用的「项目」选择器 ＋ **卡头一个导出入口**、卡内左右两栏 = 左辅材 / 右机械）、无「切换口径」按钮', (function () {
    const h = V.m05();
    const a = h.indexOf('辅材欠款台账'), b = h.indexOf('机械欠款台账');
    /* 台账那两栏的 .grid2 = **在「辅材欠款台账」之前的最后一个**（后面还会有别的 .grid2，别用全局 lastIndexOf） */
    const g = h.lastIndexOf('<div class="grid2">', a);
    const na = h.indexOf('data-act="addLg" data-sc="辅材"'), nb = h.indexOf('data-act="addLg" data-sc="机械"');
    /* ⭐ 2026-09-13：导出**只有卡头一个入口**（`ledExpToggle`）—— 两栏内的 `expLed` 已删除 */
    const expN = (h.match(/data-act="expLed"/g) || []).length;
    const entryN = (h.match(/data-act="ledExpToggle"/g) || []).length;
    /* 选择器 2026-09-13 起是**共用面板**（单选）：数「开面板的按钮」而不是原生 `<select id="ledProj">` */
    const sel = (h.match(/data-act="ledPjToggle"/g) || []).length;
    /* 「同一张卡」判据：从选择器到**机械栏**之间**不得再开一张卡**（否则又劈成了多张卡） */
    const seg = h.slice(h.indexOf('data-act="ledPjToggle"'), nb);
    return (g >= 0 && g < a && a < na && na < b && b < nb
      && expN === 0 && entryN === 1 && sel === 1 && seg.indexOf('class="card"') < 0
      && h.indexOf('data-act="ledScope"') < 0) ? 1 : 0;
  })(), 1);
  guard('U3｜台账「项目」= **共用面板（单选）**：渲染 radio、不给「全选 / 清空」、候选 = `ledProjs()`，选完两侧共用同一个值', () => {
    const bak = X.ledState();
    try {
      X.ACT.ledPjToggle({ dataset: {}, tagName: 'BUTTON' });
      const h = String(V.m05());
      if (h.indexOf('data-act="ledPjPick"') < 0) throw new Error('台账「项目」没有用共用面板（未渲染候选项）');
      if (h.indexOf('data-act="ledPjAll"') >= 0 || h.indexOf('data-act="ledPjNone"') >= 0) throw new Error('单选面板不该渲染「全选 / 清空」');
      if (!/name="projPanelSingle"/.test(h)) throw new Error('不是单选（缺 radio 的 name 属性）');
      const keys = [...h.matchAll(/data-act="ledPjPick"[^>]*data-pj="([^"]*)"/g)].map(x => x[1]);
      const exp = X.ledProjs();                                   /* 独立复算：候选集合 */
      if (!exp.length || keys.length !== exp.length || exp.some(k => keys.indexOf(k) < 0)) throw new Error('候选与 `ledProjs()` 不一致');
      const other = exp.filter(k => k !== bak.proj)[0];
      if (!other) throw new Error('只有一个候选 ⇒ 判据无区分力');
      X.ACT.ledPjPick({ dataset: { pj: other }, tagName: 'INPUT' });
      if (X.ledState().proj !== other) throw new Error('选完 `ledProj` 没变（两侧共用的就是这一个值）');
      if (String(V.m05()).indexOf(X.pjLabel(other)) < 0) throw new Error('卡头选择器没有回显所选项目的展示名');
      if (X.ledPjOpenState()) throw new Error('选完面板没有收起');
    } finally { X.setLed(bak); if (X.ledPjOpenState()) X.ACT.ledPjToggle({ dataset: {}, tagName: 'BUTTON' }); }
  });
  ck('期初占位行已带「截止年月」（= 台账起点）', X.LGs.every(l => /^\d{4}-\d{2}$/.test(String(l.cutoff || ''))) ? 1 : 0, 1);
  ck('台账第 1 行 = 期初占位行；其后从期初次月起逐月一行、月份连续', (function () {
    const rs = X.ledRows('辅材', WH_DZ);
    if (!rs.length || !rs[0].open) return 0;
    const ms = rs.slice(1).map(r => r.ym);
    if (!ms.length || ms[0] !== X.nextYm(rs[0].ym)) return 0;
    return ms.every((m, i) => i === 0 || m === X.nextYm(ms[i - 1])) ? 1 : 0;
  })(), 1);
  ck('辅材台账：「其他支出金额」= Σ 当月 · 该项目 · 辅材 的统计结算金额（独立复算）', (function () {
    const rows = X.ledRows('辅材', WH_DZ).filter(r => !r.open);
    if (!rows.length) return 0;
    return rows.every(r => {
      const v = X.N2(X.NO.filter(n => !n.excl && n.cat === '辅材' && X.ntYm(n) === r.ym && X.ntProjKey(n) === WH_DZ).reduce((a, n) => a + n.ss, 0));
      return r.s === v;
    }) ? 1 : 0;
  })(), 1);
  ck('台账：「付款」= Σ 同月 · 同项目 · 同分类 的统计付款金额（独立复算）', (function () {
    const rows = X.ledRows('辅材', WH_DZ).filter(r => !r.open);
    if (!rows.length) return 0;
    return rows.every(r => {
      const v = X.N2(X.NO.filter(n => !n.excl && n.cat === '辅材' && X.ntYm(n) === r.ym && X.ntProjKey(n) === WH_DZ).reduce((a, n) => a + n.sp, 0));
      return r.p === v;
    }) ? 1 : 0;
  })(), 1);
  ck('机械台账：「其他支出金额」= **派生只读**（Σ 各月 = 该项目的机械费结算额），不再手填', (function () {
    const keep = X.ledState();
    X.setLed({ proj: WH_DZ, cut: keep.cut });
    const h = V.m05();
    const rs = X.ledRows('机械', WH_DZ).filter(r => !r.open);
    const sum = X.N2(rs.reduce((a, r) => a + r.s, 0));
    X.setLed(keep);
    /* ① 各月之和 = 该项目机械费结算额（= Σ 外租含税两列）；② 那格**不再是输入框**（无 ledSettle 动作） */
    return (rs.length > 0 && sum === X.machSettleOf(WH_DZ)
      && h.indexOf('data-act="ledSettle"') < 0 && X.ACT.ledSettle === undefined) ? 1 : 0;
  })(), 1);
  ck('期初占位行已带「分类」，台账**按分类**取期初（辅材只带辅材的、机械只带机械的）', (function () {
    if (!X.LGs.every(l => l.cat === '辅材' || l.cat === '机械')) return 0;
    const a = X.ledRows('辅材', WH_DZ)[0];     /* 德州期初 = 辅材 → 辅材台账带出 */
    const b = X.ledRows('机械', WH_DZ)[0];     /* 德州在机械口径下**不带**期初 */
    const c = X.ledRows('机械', WH_LY)[0];     /* 临沂期初 = 机械 → 机械台账带出 */
    const d = X.ledRows('辅材', WH_LY)[0];     /* 临沂在辅材口径下**不带**期初 */
    return (a && a.open && b && !b.open && c && c.open && d && !d.open) ? 1 : 0;
  })(), 1);
  ck('台账项目候选：只列该口径下**有数据**或**该口径有期初占位行**的项目', (function () {
    const l = X.LED_PROJS('机械');
    const ok = l.every(p => Object.keys(X.MACH6).some(wh => wh === p)
      || X.NO.some(n => !n.excl && n.cat === '机械' && X.ntProjKey(n) === p)
      || X.LGs.some(g => g.cat === '机械' && X.lgProjKeyOf(g.proj) === p));
    return (l.length > 0 && ok) ? 1 : 0;
  })(), 1);
  ck('台账页面渲染：第 1 行显示「截止 …月底」、合计行在（合计行由排序逻辑钉在最后）', (function () {
    const keep = X.ledState();
    X.setLed({ proj: WH_DZ, cut: keep.cut });
    const h = V.m05();
    X.setLed(keep);
    return (h.indexOf('截止 2026 年 6 月底') >= 0 && h.indexOf('合计：') >= 0) ? 1 : 0;
  })(), 1);
  guard('机械费结算金额：**派生只读** ⇒ 台账「机械」的月行 = 该月「外租零租含税 ＋ 外租包月含税」', () => {
    /* 从**数据源**独立算一遍（不复用 ledSettle）：Σ 该项目各月 MACH6 的第 3/4 列 */
    const want = X.N2(Object.keys(X.MACH6[WH_DZ] || {})
      .reduce((a, k) => a + X.MACH6[WH_DZ][k][2] + X.MACH6[WH_DZ][k][3], 0));
    const rows = X.ledRows('机械', WH_DZ).filter(r => !r.open);
    const got = X.N2(rows.reduce((a, r) => a + r.s, 0));
    if (got !== want) throw new Error(`台账机械月行合计 ${got} ≠ 外租含税两列合计 ${want}`);
    /* 逐月比：每一行都要等于该月两列之和（防止"总额对但月份错位"） */
    rows.forEach(r => {
      const one = X.N2((X.MACH6[WH_DZ][r.ym] || [0, 0, 0, 0, 0, 0])[2] + (X.MACH6[WH_DZ][r.ym] || [0, 0, 0, 0, 0, 0])[3]);
      if (r.s !== one) throw new Error(`${r.ym} 行 ${r.s} ≠ 两列之和 ${one}`);
    });
  });
  guard('台账备注：可写可清（键 = 口径|项目|月）', () => {
    ACT.ledNote({ dataset: { sc: '辅材', proj: WH_DZ, m: '2026-07' }, value: '已核', tagName: 'INPUT' });
    if (X.LEDNOTE['辅材|' + WH_DZ + '|2026-07'] !== '已核') throw new Error('备注未写入');
    ACT.ledNote({ dataset: { sc: '辅材', proj: WH_DZ, m: '2026-07' }, value: '', tagName: 'INPUT' });
    if (X.LEDNOTE['辅材|' + WH_DZ + '|2026-07'] !== undefined) throw new Error('备注未清空');
  });
  /* 2026-09-12 修复回归：录入期初占位行后，台账必须**自动切到该项目**，否则界面上"毫无反应" */
  guard('台账：录入期初占位行后 → 项目选择器自动切到该项目（否则看不到刚录入的那行）', () => {
    const pj = X.PJs.find(p => p.type !== 'shell' && p.status === '在建' && p.full.indexOf('滁州') >= 0);
    if (!pj) throw new Error('找不到样本项目（滁州 · 在建 · 非壳）');
    const want = X.pjKey(pj);
    X.setLed({ proj: WH_DZ, cut: X.ledState().cut });          /* 先把台账停在**别的**项目上 */
    const n0 = X.LGs.length;
    /* 2026-09-13 增行模式：**一律走动作进去**（不再往 DOM 里塞值 —— 没有弹窗可塞了）；
       期初的「项目」现在走**共用面板单选**（`lgPjPick`），金额 / 备注走**草稿层**。 */
    ACT.addLg({ dataset: { sc: '辅材' }, tagName: 'BUTTON' });
    ACT.lgPjPick({ dataset: { pj: pj.name }, tagName: 'INPUT' });
    ACT.lgS({ dataset: {}, value: '123.45', tagName: 'INPUT' });
    ACT.lgP({ dataset: {}, value: '0', tagName: 'INPUT' });
    ACT.lgR({ dataset: {}, value: '期初探针', tagName: 'INPUT' });
    ACT.addLgOk({ dataset: {}, tagName: 'BUTTON' });
    if (X.LGs.length !== n0 + 1) throw new Error('期初占位行未入库');
    if (X.ledState().proj !== want) throw new Error(`台账未切到该项目：${X.ledState().proj} ≠ ${want}`);
    if (X.lgXState().on) throw new Error('保存后展开区没有收起');
    const h = V.m05();
    if (h.indexOf('期初探针') < 0 || h.indexOf('123.45') < 0) throw new Error('台账上看不到刚录入的期初行');
  });
  rollback();   /* 上面几条改过 MACH6 / LEDNOTE / 台账状态 / LGs，复位 */

  /* ================= MOD-03 · 手动新增付款通知书 = **表内增行**（2026-09-13 用户口径） =================
     由来：用户 2026-09-13「我考虑将这三个弹窗全部都取消，改为增行的模式」；甲案（同日拍板）=
     **草稿行不落 `NO`**、只存草稿层 `naD`，哨兵 id `'@new'`。 */
  console.log('\n--- 9w. MOD-03 手动新增 / 编辑 / 删除付款通知书（**增行模式**） ---');
  ck('手动新增动作齐全（增行 / 草稿写入 / 保存 / 取消 / 编辑 / 删除 / 表内改审批金额）',
    ['ntRowAdd', 'ntRowSet', 'ntRowSave', 'ntRowCancel', 'ntEdit', 'ntDel', 'ntDelOk', 'editApprove'].every(a => typeof ACT[a] === 'function') ? 1 : 0, 1);
  ck('MOD-03 卡片头有「手动新增通知书」入口（**增行**，不再弹窗），表尾有「操作」列（列数 18）', (function () {
    const h = V.m03();
    /* 2026-09-13 增行模式：入口动作由 `ntAdd`（开弹窗）改为 `ntRowAdd`（表尾插草稿行）；
       并顺带断言**旧弹窗动作已彻底移除**（残留旧名 = 没改干净；`__X` 里若还留着导出名同样会红）。 */
    /* ⚠️ 用**容错正则**定位「操作」列头（`2026-09-13` 列头加了 `style="width:…"` ⇒ 精确串 `<th>操作</th>` 不再成立）。
       这正是"**别用精确文本 / 标记巧合**"那条教训的现场复现 —— 写断言时就该用这个形态。 */
    return (h.indexOf('data-act="ntRowAdd"') >= 0 && /<th[^>]*>操作<\/th>/.test(h)
      && _thCountOf(h, 'm03:notices') === 18
      && typeof ACT.ntAdd === 'undefined' && typeof ACT.ntOpen === 'undefined' && typeof ACT.naDraft === 'undefined') ? 1 : 0;
  })(), 1);
  /* ⭐ 2026-09-13 新增守护（用户口径：**列名里的括号注释全部删除**）——
     列头一律只写列名；括号类说明搬到**单元格的 `title`**（悬停即见），不再占列宽。
     ⚠️ 判据只看 `<th>` 的**内文**，并先把 `<input …>` 整段剥掉（全选框那个 `title="…（仅当前筛选结果）"` 不算列名）。 */
  ck('MOD-03 列头一律只写列名（不带括号注释）· 列数仍为 18', (function () {
    const h = V.m03();
    const head = (h.match(/<thead\b[\s\S]*?<\/thead>/i) || [''])[0];
    const ths = head.match(/<th\b[^>]*>[\s\S]*?<\/th>/gi) || [];
    const bad = ths.filter(t => /[（(]/.test(t.slice(t.indexOf('>') + 1, t.lastIndexOf('</th>')).replace(/<input\b[^>]*>/gi, '')));
    return (ths.length === 18 && bad.length === 0) ? 1 : 0;
  })(), 1);
  ck('手动新增行的「项目」候选 = 全部已建档项目（含归档、不含壳）', (function () {
    const L = X.ntPjList();
    return (L.length === X.PJs.length - 1 && L.every(p => p.type !== 'shell') && L.some(p => p.status === '归档')) ? 1 : 0;
  })(), 1);
  /* ⭐ 2026-09-13 新增守护（增行模式的**形态契约**）：列对齐 + 钉表尾免排序 + 不进合计 + 首格无勾选框。
     ⚠️ 取值一律走 `ACT.*`（从动作进去）、断言其**可观测结果**（渲染出的行序 / 合计行格 / 单元格）。 */
  guard('增行：草稿行 = **列对齐 18 格** · **钉表尾、不被表头排序卷走** · **不进合计** · **首格无勾选框**', () => {
    const _sumCell = h => ((h.match(/<tr class="sumrow"[^>]*>[\s\S]*?<\/tr>/) || [''])[0].match(/<td\b[^>]*>[\s\S]*?<\/td>/gi) || [])[10] || '';
    /* ⚠️ 基线必须在**同一套筛选**下取 —— `ntRowAdd` 会放宽筛选（C-3 前移），
       若直接拿"放宽前"的合计当基线，变化其实是筛选造成的、与草稿无关（**实测踩到，断言假红**）。
       ⇒ 先"开一次再取消"把筛选摆到放宽后的状态，再取无草稿的基线。 */
    ACT.ntRowAdd({ dataset: {}, tagName: 'BUTTON' });
    ACT.ntRowCancel({ dataset: {}, tagName: 'BUTTON' });
    const sum0 = _sumCell(X.applySorts(V.m03(), 'm03'));
    ACT.ntRowAdd({ dataset: {}, tagName: 'BUTTON' });
    if (X.naState().id !== '@new') throw new Error('增行后草稿层哨兵不是 @new：' + X.naState().id);
    /* 故意把审批金额填成**最大** —— 若“钉表尾”失效，降序下它会被排到**最前**（这才有区分力） */
    ACT.ntRowSet({ dataset: { k: 'approve' }, value: '99999999', tagName: 'INPUT' });
    /* ① 列对齐：草稿行 `<td>` 数必须 = 表头列数（18） */
    const raw = V.m03(), iD = raw.indexOf('<tr class="draftrow"');
    if (iD < 0) throw new Error('没有渲染出草稿行');
    const seg = raw.slice(iD, raw.indexOf('</tr>', iD));
    const tdc = (seg.match(/<td\b/gi) || []).length;
    if (tdc !== 18) throw new Error('草稿行不是列对齐行（<td> 数 = ' + tdc + '，应为 18）');
    /* ② 首格不得是勾选框（草稿行**天然不进**勾选 / 全选范围） */
    if (/data-act="pick"/.test(seg)) throw new Error('草稿行首格渲染了勾选框 —— 它不应进勾选范围');
    /* ③ 排序：把「审批金额」列切到**降序**（两次 headSort），草稿行仍须排在**所有数据行之后** */
    ACT.headSort({ dataset: { tk: 'm03:notices', i: '10' }, tagName: 'TH' });
    ACT.headSort({ dataset: { tk: 'm03:notices', i: '10' }, tagName: 'TH' });
    const hs = X.applySorts(V.m03(), 'm03');
    const rows = hs.slice(hs.indexOf('<tbody'), hs.indexOf('</tbody>')).match(/<tr\b[^>]*>[\s\S]*?<\/tr>/gi) || [];
    const isPin = r => /draftrow/.test(r) || /合计|总计|小计/.test(r.replace(/<[^>]*>/g, ' '));
    const iDraft = rows.findIndex(r => /draftrow/.test(r));
    const iLastData = rows.map(isPin).lastIndexOf(false);
    if (iDraft < 0) throw new Error('排序后草稿行不见了');
    if (iDraft < iLastData) throw new Error('排序后草稿行被卷进数据行之间 —— `applySorts` 的 draftrow 钉尾失效');
    /* ⭐ 反向：证明“排序确实生效”（否则“在表尾”是恒真的空断言） */
    const dataRows = rows.filter(r => !isPin(r));
    if (dataRows.length < 3) throw new Error('演示数据不足 —— 排序断言失去区分力');
    const valOf = r => { const td = (r.match(/<td\b[^>]*>[\s\S]*?<\/td>/gi) || [])[10] || '';
      const m = td.match(/value="([\d.]+)"/) || td.match(/>([\d,]+\.\d\d)</); return m ? parseFloat(String(m[1]).replace(/,/g, '')) : NaN; };
    const vs = dataRows.map(valOf);
    if (vs.some(isNaN)) throw new Error('审批金额列取值失败 —— 断言失去区分力');
    for (let i = 1; i < vs.length; i++) if (vs[i - 1] < vs[i]) throw new Error('降序未生效 —— 断言失去区分力');
    /* ④ 不进合计：草稿行填了 99999999，合计行的「审批金额」必须与无草稿时**完全一致** */
    if (_sumCell(hs) !== sum0) throw new Error('草稿行被算进了合计（合计行「审批金额」变了）');
    ACT.ntRowCancel({ dataset: {}, tagName: 'BUTTON' });
    Object.keys(X.SORT).forEach(k => delete X.SORT[k]);             /* 排序态复位 */
  });
  guard('增行：保存落库（手动标记 / 统计结算恒 0 / 统计付款进台账当月「付款」/ 录入人=当前登录用户 / 草稿层复位）', () => {
    const proj = WH_DZ, before = X.ledPay('辅材', proj, '2026-09'), n0 = X.NO.length;
    const pid = X.PJs.find(p => p.disp === proj || p.name === proj).id;
    /* 先把视图调成"新行一定看不见"的状态（月份 / 分类 / 审批状态 / 付款状态全不对）——
       这样「增行时自动切到该行年月并放宽三档筛选」才是**有内容**的断言（否则它恒真 = 等于没测）。 */
    const bak = { m: X.fNt.month, c: X.fNt.cat, a: X.fNt.astat, s: X.fNt.stat, p: X.fNt.projs.slice() };
    X.fNt.month = '2026-07'; X.fNt.cat = '集采'; X.fNt.astat = '未批'; X.fNt.stat = '已付清'; X.fNt.projs = [];
    ACT.ntRowAdd({ dataset: {}, tagName: 'BUTTON' });
    /* ⭐ C-3（2026-09-13 用户拍板）：放宽筛选**前移到「点新增时」**（不再是保存后）——
       草稿行必须**立刻**看得见，否则用户填了一半才发现它在筛选之外。 */
    if (V.m03().indexOf('class="draftrow"') < 0) throw new Error('点「＋ 手动新增通知书」后没有渲染草稿行');
    if (X.fNt.cat !== '全部' || X.fNt.astat !== '全部' || X.fNt.stat !== '全部') throw new Error('点新增时未放宽三档筛选');
    ACT.ntRowSet({ dataset: { k: 'pid' }, value: pid, tagName: 'SELECT' });
    ACT.ntRowSet({ dataset: { k: 'date' }, value: '2026-09-20', tagName: 'INPUT' });
    ACT.ntRowSet({ dataset: { k: 'code' }, value: 'SD-TEST-9W', tagName: 'INPUT' });
    ACT.ntRowSet({ dataset: { k: 'doc' }, value: '付期初欠款（探针）', tagName: 'INPUT' });
    ACT.ntRowSet({ dataset: { k: 'cat' }, value: '辅材', tagName: 'SELECT' });
    ACT.ntRowSet({ dataset: { k: 'approve' }, value: '50000', tagName: 'INPUT' });
    ACT.ntRowSet({ dataset: { k: 'sp' }, value: '50000', tagName: 'INPUT' });
    ACT.ntRowSave({ dataset: {}, tagName: 'BUTTON' });
    if (X.NO.length !== n0 + 1) throw new Error('未写入新行');
    const n = X.NO[X.NO.length - 1];
    if (n.manual !== true) throw new Error('新行未打「手动」标记');
    if (n.ss !== 0) throw new Error('统计结算金额不是 0：' + n.ss);
    if (n.sp !== 50000) throw new Error('统计付款金额不对：' + n.sp);
    if (n.entry !== X.CUR.name) throw new Error('录入人不是当前登录用户：' + n.entry);
    if (n.date !== '2026-09-20') throw new Error('单据日期不对：' + n.date);
    if (X.OWN[n.id] !== pid) throw new Error('新行未写「归属 id」（§六-12：按 id 存取、禁止按全名反查）');
    if (X.ledPay('辅材', proj, '2026-09') - before !== 50000) throw new Error('台账当月「付款」未计入');
    if (X.naState().id !== '') throw new Error('保存后草稿层未复位（哨兵仍在）');
    const h = V.m03();
    if (h.indexOf('class="draftrow"') >= 0) throw new Error('保存后草稿行仍在（应转为普通手动行）');
    if (h.indexOf('SD-TEST-9W') < 0) throw new Error('新增后列表上看不到新行（视图未切到该行年月 / 未放宽筛选）');
    if (!/data-act="ntEdit" data-id="MN\d+"/.test(h) || !/data-act="ntDel" data-id="MN\d+"/.test(h)) throw new Error('手动行没有编辑 / 删除入口');
    const seg = h.slice(h.indexOf('SD-TEST-9W'), h.indexOf('</tr>', h.indexOf('SD-TEST-9W')));
    if (seg.indexOf('data-k="ss"') >= 0) throw new Error('手动行的统计结算金额仍是可改输入框');
    if (seg.indexOf('恒为 0') < 0) throw new Error('手动行的统计结算金额未标注「恒为 0」');
    Object.assign(X.fNt, { month: bak.m, cat: bak.c, astat: bak.a, stat: bak.s }); X.fNt.projs = bak.p;   /* 还原视图状态 */
  });
  guard('手动行：全站口径「统计两金额 ≤ 审批金额」同样生效（超上限被拦截并保留原值 + **草稿不清空**）', () => {
    const n = X.NO[X.NO.length - 1], b = n.sp;
    ACT.ntEdit({ dataset: { id: n.id }, tagName: 'BUTTON' });
    ACT.ntRowSet({ dataset: { k: 'sp' }, value: '60000', tagName: 'INPUT' });
    ACT.ntRowSave({ dataset: {}, tagName: 'BUTTON' });
    if (X.NO.find(x => x.id === n.id).sp !== b) throw new Error('超上限未被拦截');
    /* 被拦截后草稿必须**留着**（用户要能接着改）—— 弹窗时代是"整批不入库"，行内时代是"这一格不生效" */
    if (X.naState().id !== n.id) throw new Error('被拦截后草稿层被清掉了（应保留草稿让用户改）');
    if (V.m03().indexOf('class="draftrow"') < 0) throw new Error('被拦截后草稿行消失了');
    ACT.ntRowCancel({ dataset: {}, tagName: 'BUTTON' });
  });
  guard('手动行：「编辑」= **原地变草稿行**（不新增行），且能改一切信息、归属按档案 id 写死', () => {
    const n = X.NO[X.NO.length - 1], p2 = X.PJs.find(p => p.status === '归档'), n0 = X.NO.length;
    ACT.ntEdit({ dataset: { id: n.id }, tagName: 'BUTTON' });
    if (X.NO.length !== n0) throw new Error('「编辑」不该新增行（要求原地编辑）');
    const h0 = V.m03();
    const cnt = h0.split('class="draftrow"').length - 1;
    if (cnt !== 1) throw new Error('草稿行数不是 1（实际 ' + cnt + '）—— 原行没被草稿行替换');
    const iD = h0.indexOf('class="draftrow"');
    if (h0.slice(iD, h0.indexOf('</tr>', iD)).indexOf('SD-TEST-9W') < 0) throw new Error('草稿行没落在被编辑的那一行上（不是原地）');
    if (new RegExp('data-act="ntEdit" data-id="' + n.id + '"').test(h0)) throw new Error('被编辑行仍渲染成普通手动行（原地编辑未生效）');
    ACT.ntRowSet({ dataset: { k: 'pid' }, value: p2.id, tagName: 'SELECT' });
    ACT.ntRowSet({ dataset: { k: 'date' }, value: '2026-08-08', tagName: 'INPUT' });
    ACT.ntRowSet({ dataset: { k: 'approve' }, value: '70000', tagName: 'INPUT' });
    ACT.ntRowSet({ dataset: { k: 'sp' }, value: '70000', tagName: 'INPUT' });
    ACT.ntRowSave({ dataset: {}, tagName: 'BUTTON' });
    const m = X.NO.find(x => x.id === n.id);
    if (m.proj !== p2.full || m.date !== '2026-08-08' || m.approve !== 70000 || m.sp !== 70000) throw new Error('编辑未生效');
    if (X.OWN[m.id] !== p2.id) throw new Error('归属未按档案 id 写入');
    if (X.ntProjName(m) !== (p2.disp || p2.name)) throw new Error('归属取数不对：' + X.ntProjName(m));
  });
  guard('i8 抓取行：没有「编辑 / 删除」入口，且审批金额不可被改（手动行专属）', () => {
    const n = X.NO.find(x => x.id === 'N01'), b = n.approve;
    ACT.editApprove({ dataset: { id: 'N01' }, value: '1', tagName: 'INPUT' });
    if (n.approve !== b) throw new Error('i8 行的审批金额被改动了');
    if (/data-act="ntEdit" data-id="N01"/.test(V.m03())) throw new Error('i8 行出现了编辑入口');
  });
  guard('手动行：删除只删该行，并同步清归属与勾选', () => {
    const n = X.NO.find(x => x.manual === true), id = n.id, n0 = X.NO.length;
    X.pickSet.add(id);
    ACT.ntDel({ dataset: { id }, tagName: 'BUTTON' });
    ACT.ntDelOk({ dataset: { id }, tagName: 'BUTTON' });
    if (X.NO.length !== n0 - 1) throw new Error('未删除');
    if (X.OWN[id] !== undefined) throw new Error('归属未清理');
    if (X.pickSet.has(id)) throw new Error('勾选未清理');
  });
  guard('增行：取消 = **整批不入库**（草稿丢弃、数据一字未改、行数不变）· 编辑中取消 = 该行保持原样', () => {
    const n0 = X.NO.length, snap = JSON.stringify(X.NO);
    ACT.ntRowAdd({ dataset: {}, tagName: 'BUTTON' });
    ACT.ntRowSet({ dataset: { k: 'code' }, value: 'SD-CANCEL-X', tagName: 'INPUT' });
    ACT.ntRowSet({ dataset: { k: 'approve' }, value: '12345', tagName: 'INPUT' });
    if (V.m03().indexOf('SD-CANCEL-X') < 0) throw new Error('草稿行没渲染出已填内容 —— 断言失去区分力');
    ACT.ntRowCancel({ dataset: {}, tagName: 'BUTTON' });
    if (X.NO.length !== n0) throw new Error('取消后行数变了（草稿不该入库）');
    if (JSON.stringify(X.NO) !== snap) throw new Error('取消后 NO 内容被改动了');
    if (X.naState().id !== '') throw new Error('取消后草稿层未复位');
    if (V.m03().indexOf('class="draftrow"') >= 0) throw new Error('取消后草稿行仍在');
    /* 「编辑中取消」= 该行**保持原样**（草稿不落库）。
       ⚠️ 前一条「删除」守卫已把手动行删光 ⇒ **本守卫自备夹具**（自己造一行手动行），
          否则 `find` 落空、断言静默失去区分力（实测踩到）。 */
    ACT.ntRowAdd({ dataset: {}, tagName: 'BUTTON' });
    ACT.ntRowSet({ dataset: { k: 'code' }, value: 'SD-FIXTURE-K', tagName: 'INPUT' });
    ACT.ntRowSet({ dataset: { k: 'approve' }, value: '1000', tagName: 'INPUT' });
    ACT.ntRowSet({ dataset: { k: 'sp' }, value: '1000', tagName: 'INPUT' });
    ACT.ntRowSave({ dataset: {}, tagName: 'BUTTON' });
    const mn = X.NO.find(x => x.manual === true);
    if (!mn || mn.code !== 'SD-FIXTURE-K') throw new Error('夹具没造出手动行 —— 断言失去区分力');
    const spBefore = mn.sp, codeBefore = mn.code;
    ACT.ntEdit({ dataset: { id: mn.id }, tagName: 'BUTTON' });
    ACT.ntRowSet({ dataset: { k: 'sp' }, value: '1', tagName: 'INPUT' });
    ACT.ntRowSet({ dataset: { k: 'code' }, value: 'SD-NEVER-SAVED', tagName: 'INPUT' });
    ACT.ntRowCancel({ dataset: {}, tagName: 'BUTTON' });
    if (mn.sp !== spBefore || mn.code !== codeBefore) throw new Error('编辑中取消后该行被改动了（应保持原样）');
    if (V.m03().indexOf('SD-NEVER-SAVED') >= 0) throw new Error('编辑中取消后草稿内容仍渲染在页面上');
    /* 拆夹具：本守卫自己造的行自己删掉，别把状态留给后面的断言（同 `M6` / `T1` 的教训） */
    ACT.ntDel({ dataset: { id: mn.id }, tagName: 'BUTTON' });
    ACT.ntDelOk({ dataset: { id: mn.id }, tagName: 'BUTTON' });
    if (X.NO.some(x => x.code === 'SD-FIXTURE-K')) throw new Error('夹具行未清理');
  });
  ck('期初占位行：默认项目 = 欠款台账当前选中的项目（增行态回显正确）', (function () {
    const keep = X.ledState(), p = X.PJs.find(x => x.disp === '德州热电' || x.name === '德州热电');
    X.setLed({ proj: WH_DZ, cut: keep.cut });
    const exp = X.lgDefPjName();                             /* 期望值**独立取**（不从实现里读回来） */
    ACT.addLg({ dataset: {}, tagName: 'BUTTON' });
    const st = X.lgXState(), h = V.m05();
    ACT.lgCancel({ dataset: {}, tagName: 'BUTTON' });
    X.setLed(keep);
    /* 2026-09-13 增行模式：不再是"弹窗里某个 option 带 selected"，而是
       ① 状态里项目键对 ② 展开区**渲染在当前分类那一栏**（分支条带在、面板入口在）。 */
    return (exp === p.name && st.on === true && st.pj === p.name
      && h.indexOf('data-act="addLgOk"') >= 0 && h.indexOf('data-act="lgPjToggle"') >= 0) ? 1 : 0;
  })(), 1);
  ck('期初占位行：默认截止年月 = 该项目**该分类**已有数据最早月的前一月（**按分类独立算**：德州/临沂 辅材 2026-08→2026-07、机械 2026-05→2026-04）', (function () {
    const f = d => X.PJs.find(x => x.disp === d).name;
    return (X.lgCutFor(f('德州热电'), '辅材') === '2026-07' && X.lgCutFor(f('德州热电'), '机械') === '2026-04'
      && X.lgCutFor(f('临沂钢铁'), '辅材') === '2026-07' && X.lgCutFor(f('临沂钢铁'), '机械') === '2026-04'
      && X.prevYm('2026-01') === '2025-12') ? 1 : 0;
  })(), 1);
  ck('期初占位行：**该分类**完全没数据 → 默认截止年月回退「上月」（新沂生物质无机械数据 → 上月）', (function () {
    const p = X.PJs.find(x => x.disp === '新沂生物质');
    return (p && X.lgEarliest(p.name, '机械') === '' && X.lgCutFor(p.name, '机械') === X.bjMonth(-1)) ? 1 : 0;
  })(), 1);
  guard('期初占位行：展开区内改「分类」→ 截止年月默认值按新分类重算（辅材 2026-07 ↔ 机械 2026-04）', () => {
    const keep = X.ledState(), p = X.PJs.find(x => x.disp === '德州热电');
    X.setLed({ proj: WH_DZ, cut: keep.cut });                 /* 项目默认取台账当前项目 → 先摆到德州 */
    X.setLgPjName(p.name);
    ACT.addLg({ dataset: { sc: '辅材' }, tagName: 'BUTTON' });     /* 从辅材栏进来 → 分类预选「辅材」 */
    const a = X.ledState().cut;
    ACT.lgCat({ dataset: {}, value: '机械', tagName: 'SELECT' });  /* 切成「机械」→ 必须按机械的最早月重算 */
    const b = X.ledState().cut;
    ACT.addLg({ dataset: { sc: '辅材' }, tagName: 'BUTTON' });     /* 复位（lgCat 无独立 setter，从入口复位） */
    ACT.lgCancel({ dataset: {}, tagName: 'BUTTON' });
    X.setLed(keep);
    if (a !== '2026-07' || b !== '2026-04') throw new Error(`分类切换未重算截止年月：辅材 ${a} / 机械 ${b}`);
  });
  guard('期初展开区：改「分类」触发的整页重绘，**已填的金额与备注不丢**（草稿层 `lgD`）', () => {
    const p = X.PJs.find(x => x.disp === '德州热电');
    X.setLgPjName(p.name);
    ACT.addLg({ dataset: { sc: '辅材' }, tagName: 'BUTTON' });          /* 进入增行态 → 草稿复位 */
    ACT.lgS({ dataset: {}, value: '1234.56', tagName: 'INPUT' });       /* 依次填金额 / 备注 */
    ACT.lgP({ dataset: {}, value: '78.90', tagName: 'INPUT' });
    ACT.lgR({ dataset: {}, value: '草稿探针', tagName: 'INPUT' });
    ACT.lgCat({ dataset: {}, value: '机械', tagName: 'SELECT' });       /* 改「分类」→ **整页重绘**（展开区随之重建） */
    const m = V.m05();
    const ok1 = m.indexOf('value="1234.56"') >= 0 && m.indexOf('value="78.90"') >= 0 && m.indexOf('value="草稿探针"') >= 0;
    ACT.lgCancel({ dataset: {}, tagName: 'BUTTON' });
    ACT.addLg({ dataset: { sc: '辅材' }, tagName: 'BUTTON' });          /* 复位 lgCat 与草稿 */
    ACT.lgCancel({ dataset: {}, tagName: 'BUTTON' });
    if (!ok1) throw new Error('重绘展开区后草稿被冲掉（金额 / 备注丢失）');
  });

  /* ⭐ 2026-09-13 新增守护（期初增行模式的**形态契约** —— C-7 / C-8 的落点） */
  guard('增行：期初展开区 = **渲染在 `.tw` 之外** + 「项目」= **共用面板（单选）** + 选完收起 · 取消不入库', () => {
    const p = X.PJs.find(x => x.disp === '德州热电');
    X.setLgPjName(p.name);
    ACT.addLg({ dataset: { sc: '辅材' }, tagName: 'BUTTON' });
    /* ① C-7：展开区必须在**表格滚动容器之外**（否则其内的浮层面板会被 `.tw` 裁掉） */
    const h = V.m05();
    const iStrip = h.indexOf('data-act="addLgOk"'), iTw = h.indexOf('<div class="tw">');
    if (iStrip < 0) throw new Error('增行态没渲染出期初展开区');
    /* ⚠️ 必须**恰好 1 处**：只判"第一处在 .tw 之外"会**假绿** —— 若别处又渲染一份在 `.tw` 里，
       滚动容器照样会把那份里的浮层面板裁掉（实测：变异"挪进 .tw 之内"造成两处，判据仍绿）。 */
    const cntS = h.split('data-act="addLgOk"').length - 1;
    if (cntS !== 1) throw new Error('期初展开区应恰好渲染 1 处，实际 ' + cntS + ' 处');
    if (iTw < 0 || iStrip > iTw) throw new Error('期初展开区落在表格 `.tw` 之内 —— 浮层面板会被滚动容器裁掉');
    /* ② 「项目」= 共用面板（**单选**）：渲染 radio、**不给「全选 / 清空」** */
    ACT.lgPjToggle({ dataset: {}, tagName: 'BUTTON' });
    const hp = V.m05();
    if (hp.indexOf('name="projPanelSingle"') < 0) throw new Error('期初「项目」面板不是单选（未渲染 radio）');
    if (hp.indexOf('data-act="lgPjAll"') >= 0 || hp.indexOf('data-act="lgPjNone"') >= 0) throw new Error('单选面板不该给「全选 / 清空」');
    /* ③ 点一项 → 落到状态 + 面板自动收起 */
    ACT.lgPjPick({ dataset: { pj: WH_LY }, tagName: 'INPUT' });
    const st = X.lgXState();
    if (st.pj !== WH_LY) throw new Error('选完项目没落到状态');
    if (st.open) throw new Error('选完面板没有自动收起');
    /* ④ 取消 = **不入库** + 展开区收起（不残留） */
    const n0 = X.LGs.length;
    ACT.lgS({ dataset: {}, value: '999' });
    ACT.lgCancel({ dataset: {}, tagName: 'BUTTON' });
    if (X.LGs.length !== n0) throw new Error('取消后 LGs 行数变了（草稿不该入库）');
    if (X.lgXState().on) throw new Error('取消后展开区没收起');
    if (V.m05().indexOf('data-act="addLgOk"') >= 0) throw new Error('取消后展开区仍渲染在页面上');
  });

  /* ⭐ 2026-09-13 新增守护（集采「手工新增合同」增行模式：形态契约 + **真的落库**） */
  guard('增行：集采「手工新增合同」= 展开区在 `.tw` 之外 + 项目走共用面板（单选）+ **保存真的建档** · 取消不入库', () => {
    const n0 = X.JCs.length;
    ACT.jcAdd({ dataset: {}, tagName: 'BUTTON' });
    const h = V.m11();
    const iStrip = h.indexOf('data-act="jcRowSave"'), iTw = h.indexOf('<div class="tw">');
    if (iStrip < 0) throw new Error('展开区没渲染出来');
    /* ⚠️ 必须**恰好 1 处**（同 ② 的教训）：只判"第一处在 .tw 之外"会**假绿** ——
       变异"挪进 .tw 之内"实测仍绿，因为那处外置的副本还在、`indexOf` 取的是它。 */
    const cntS = h.split('data-act="jcRowSave"').length - 1;
    if (cntS !== 1) throw new Error('展开区应恰好渲染 1 处，实际 ' + cntS + ' 处');
    if (iTw < 0 || iStrip > iTw) throw new Error('展开区落在表格 `.tw` 之内 —— 浮层面板会被滚动容器裁掉');
    /* ① 取消 = 不入库 */
    ACT.jcNSet({ dataset: { k: 'material' }, value: '不该入库的材料' });
    ACT.jcRowCancel({ dataset: {}, tagName: 'BUTTON' });
    if (X.JCs.length !== n0) throw new Error('取消后 JCs 行数变了（草稿不该入库）');
    /* ② 保存 = **真的建档**（原实现的"保存"挂在 `silent` 上、压根没有落库动作） */
    ACT.jcAdd({ dataset: {}, tagName: 'BUTTON' });
    ACT.jcNPjToggle({ dataset: {}, tagName: 'BUTTON' });
    if (V.m11().indexOf('name="projPanelSingle"') < 0) throw new Error('「项目」不是共用面板单选');
    ACT.jcNPjPick({ dataset: { pj: WH_DZ }, tagName: 'INPUT' });
    ACT.jcNSet({ dataset: { k: 'material' }, value: '探针材料 Q235B' });
    ACT.jcNSet({ dataset: { k: 'supplier' }, value: '探针供应商' });
    ACT.jcNSet({ dataset: { k: 'contractAmt' }, value: '123456.78' });
    ACT.jcRowSave({ dataset: {}, tagName: 'BUTTON' });
    if (X.JCs.length !== n0 + 1) throw new Error('保存后没有建档（JCs 行数没变）—— 落库动作缺失');
    const j = X.JCs[X.JCs.length - 1], jid = j.id;
    if (j.proj !== WH_DZ) throw new Error('项目没落到合同行上：' + j.proj);
    if (j.material !== '探针材料 Q235B') throw new Error('材料名没落库');
    if (j.contractAmt !== 123456.78) throw new Error('合同金额没落库：' + j.contractAmt);
    if (j.tag !== '纳入台账') throw new Error('默认应为「纳入台账」（TAIL-97 取消「待确认」· 与抓取行同一个默认值）：' + j.tag);
    if (!/^JM\d+$/.test(jid)) throw new Error('手工行的 id 形态不对：' + jid);
    if (!Array.isArray(j.invoices) || !Array.isArray(j.payments) || !Array.isArray(j.tradeInvoices)) throw new Error('三个子表未初始化为空数组');
    if (j.arch !== '未存档') throw new Error('存档情况默认应为「未存档」：' + j.arch);
    if (X.jcNewState().on) throw new Error('保存后展开区没收起');
    if (V.m11().indexOf(jid) < 0) throw new Error('建档后列表上看不见新合同（筛选未放宽）');
    /* ③ 非法金额被拦截（走唯一出口 `badMoney`，原值保留） */
    ACT.jcAdd({ dataset: {}, tagName: 'BUTTON' });
    ACT.jcNSet({ dataset: { k: 'contractAmt' }, value: 'abc' });
    const n1 = X.JCs.length;
    ACT.jcRowSave({ dataset: {}, tagName: 'BUTTON' });
    if (X.JCs.length !== n1) throw new Error('非法合同金额没有被拦截（仍然建档了）');
    ACT.jcRowCancel({ dataset: {}, tagName: 'BUTTON' });
    /* 拆夹具：本守卫自己建的那行自己删掉，别把状态留给后面的断言 */
    const k = X.JCs.findIndex(x => x.id === jid); if (k >= 0) X.JCs.splice(k, 1);
  });

  /* ================= MOD-05 · 付款流水筛选（2026-09-13 用户口径） ================= */
  console.log('\n--- 9z2. MOD-05 付款流水：默认当月 · 筛选即时生效 · 不分页 ---');
  ck('付款流水：筛选月默认 = 北京时间当月（**不是「全部月份」**）· 当月 12 条 / 全库 17 条 · 且**不分页**', (function () {
    const h = V.m05();
    /* 不分页判据：整页不得出现页码 / 每页条数类控件 */
    const noPager = h.indexOf('每页') < 0 && h.indexOf('下一页') < 0 && h.indexOf('上一页') < 0;
    /* 默认值一律比 FLF0（加载时快照）—— 比运行时现况会被交互路径里的 flReset 掩盖 */
    return (FLF0 === X.bjMonth() && X.flf.ym === X.bjMonth()
      && X.FLs.length === 17 && X.flVisible().length === 12 && noPager) ? 1 : 0;
  })(), 1);
  ck('付款流水：筛选即时生效（状态=已撤销 → 1 条；付款方式=承兑 → 与按值复算一致）', (function () {
    const keep = { method: X.flf.method, state: X.flf.state };
    X.flf.state = '已撤销'; const a = X.flVisible().length;
    X.flf.state = '全部'; X.flf.method = '承兑'; const b = X.flVisible().length;
    const want = X.FLs.filter(f => X.flMonthOf(f) === X.flf.ym && f.method === '承兑').length;
    X.flf.method = keep.method; X.flf.state = keep.state;
    return (a === 1 && want > 0 && b === want) ? 1 : 0;
  })(), 1);
  guard('付款流水：合计**只算生效流水**（已撤销不计入 —— 与「已付金额 = 流水汇总」§4.4.5 同源）', () => {
    const cur = X.bjMonth();
    const on = X.FLs.filter(f => X.flMonthOf(f) === cur && !f.voided);
    const sum = X.N2(on.reduce((a, f) => a + f.amt, 0));
    const h = V.m05();
    if (h.indexOf(`合计（生效 ${on.length} 条`) < 0) throw new Error('合计行未标注「只算生效」');
    if (h.indexOf(X.M(sum) + '</b>') < 0) throw new Error(`未见合计 ${sum}`);
  });
  guard('付款流水：空态行存在，且跨列数 = 表头列数（**铺满整行**，不写死数字）', () => {
    const keep = X.flf.q; X.flf.q = '不存在的流水号zzz';
    let h = ''; try { h = V.m05(); } finally { X.flf.q = keep; }
    if (h.indexOf('该筛选条件下没有付款流水') < 0) throw new Error('空态提示缺失');
    const cols = (X.FL_THEAD.match(/<th\b/g) || []).length;          /* 独立数表头，不借 thCount */
    if (cols !== 10) throw new Error(`付款流水表头列数变了：${cols}`);
    if (h.indexOf(`colspan="${cols}"`) < 0) throw new Error(`空态 colspan 不等于表头列数 ${cols}`);
  });
  guard('付款流水：关键词**只在「搜索」按钮里生效**（输入框不挂 data-act —— 别的动作不会带着它去搜）', () => {
    /* ⚠️ 2026-09-26（`#2`）：末尾那句「`flQ` 仍在 CHG 里」随名单一起删（没有主人了）；
       要害那半句 = **输入框不挂 `data-act`**（挂了就会随每次输入自动搜），一字未动。 */
    const h = V.m05();
    if (h.indexOf('data-act="flSearch"') < 0) throw new Error('缺「搜索」按钮');
    if (h.indexOf('id="flQ" data-act=') >= 0) throw new Error('关键词输入框仍挂了 data-act（会随输入自动搜）');
    const keep = X.flf.q; X.flf.q = '';
    doc.querySelector('#flQ').value = 'F2';                       /* 先在输入框里打字 */
    const before = X.flVisible().length;
    ACT.flSearch();                                              /* 点按钮才生效 */
    const after = X.flVisible().length;
    X.flf.q = keep;
    if (!(after < before)) throw new Error(`点「搜索」未生效：${before} → ${after}`);
  });

  /* ===== U1–U2：2026-09-13 用户报障修复的**两条守护** =====
     U1 起因：`MOD-09` 的「项目」面板把**档案行对象**当候选键传给 `projPanel` ⇒ `data-pj="[object Object]"`
        ⇒ 选完一点就变「未建档」（用户报「点完变未建档」）。
     U2 起因：付款流水的「付款项目」自造成**原生 `<select>` 单选** —— 破坏「统一多选面板」复用点，
        且与全站约定（MOD-09 单选、其余多选）不符 ⇒ 改回共用面板。 */
  guard('U1｜MOD-09「项目」共用面板：候选键 = **仓库名**（不得是 `[object Object]`），选完不回退成「未建档」', () => {
    const keys = X.PJs.filter(p => p.type !== 'shell' && p.name).map(p => p.name);   /* 独立算候选键，不借面板 */
    try {
      X.ACT.awfReset({ dataset: {}, tagName: 'BUTTON' });        /* 归一：面板收起 + 项目回默认 */
      X.ACT.awfPjToggle({ dataset: {}, tagName: 'BUTTON' });
      const h = String(V.m09());
      const used = [...h.matchAll(/data-act="awfPjPick"[^>]*data-pj="([^"]*)"/g)].map(x => x[1]);
      if (used.length < 2) throw new Error('MOD-09 的「项目」面板没渲染出候选项 ⇒ 判据无区分力');
      const bad = used.filter(v => keys.indexOf(v) < 0);
      if (bad.length) throw new Error('候选键不是仓库名（bug 复现）：' + bad.slice(0, 3).join(' / '));
      const pick = used[used.length - 1];
      X.ACT.awfPjPick({ dataset: { pj: pick }, tagName: 'INPUT' });
      const h2 = String(V.m09());
      if (h2.indexOf('未建档') >= 0) throw new Error('选完之后页面出现「未建档」（bug 未修净）');
      if (h2.indexOf(X.pjLabel(pick)) < 0) throw new Error('选完没有回显该项的展示名「' + X.pjLabel(pick) + '」');
    } finally { X.ACT.awfReset({ dataset: {}, tagName: 'BUTTON' }); }
  });
  guard('U2｜付款流水「付款项目」= **共用面板（多选）**：有「全选 / 清空」、无单选 radio，且勾选真的生效', () => {
    X.ACT.flReset({ dataset: {}, tagName: 'BUTTON' });
    const cnt = () => { const h = String(V.m05());
      return _srRows(h, 'm05:flows').length - (_srSumRow(h, 'm05:flows') ? 1 : 0); };
    try {
      const base = cnt();
      X.ACT.flPjToggle({ dataset: {}, tagName: 'BUTTON' });
      const h = String(V.m05());
      if ((h.match(/data-act="flPjPick"/g) || []).length < 2) throw new Error('付款流水的项目筛选没有用共用面板（未渲染候选项）');
      if (h.indexOf('data-act="flPjAll"') < 0 || h.indexOf('data-act="flPjNone"') < 0) throw new Error('共用面板缺「全选 / 清空」⇒ 不是多选');
      if (/name="projPanelSingle"/.test(h)) throw new Error('渲染成了单选（radio）—— 全站约定：只有 MOD-09 是单选');
      const key = [...h.matchAll(/data-act="flPjPick"[^>]*data-pj="([^"]*)"/g)].map(x => x[1])[0];
      /* 独立复算：该月 · 该项目的流水条数（自己从 FLs → NO 推，**不复用** `flHit` / `flProjOf`） */
      const exp = X.FLs.filter(f => X.tmIn(X.flf.ym, f.date)
        && (function () { const n = X.NO.find(x => x.id === f.nid); return !!(n && X.ntProjKey(n) === key); })()).length;
      X.ACT.flPjPick({ dataset: { pj: key }, tagName: 'INPUT' });
      const got = cnt();
      if (got !== exp) throw new Error(`勾选「${key}」没生效：${got} 行 ≠ 独立复算 ${exp}`);
      if (!(got < base)) throw new Error('勾选后行数没减少 ⇒ 判据无区分力');
      X.ACT.flPjNone({ dataset: {}, tagName: 'BUTTON' });
      if (cnt() !== base) throw new Error('点「清空」后没有回到全部项目');
    } finally { X.ACT.flReset({ dataset: {}, tagName: 'BUTTON' }); }
  });

  /* ================= MOD-05 · 付款统计（2026-09-13 用户口径：甲 = Σ统计付款金额） ================= */
  console.log('\n--- 9z3. MOD-05 付款统计：取值出口 · 按月/周 · 联动 ---');
  guard('付款统计：**默认粒度 = 「按周」**（比的是**加载时快照** —— 交互路径里有 `pstGran`，跑过就看不出来了）', () => {
    if (PSTG0 !== '周') throw new Error('默认粒度不是「按周」，而是 ' + PSTG0);
  });
  guard('付款统计：取值 = Σ「统计付款金额」，与逐月台账「付款」列**同一出口**（按左栏选定桶复算）', () => {
    const keepG = X.pst.gran, keepY = X.pst.ym;
    X.pst.gran = '月'; X.pst.ym = '';                       /* 固定到月粒度 + 默认桶，避免与"周桶"混 */
    const d = X.pstData(), bk = d.bk;
    const viaLed = X.N2(['辅材', '机械', '集采'].reduce((a, sc) =>
      a + X.LED_PROJS(sc).reduce((b, p) => b + X.ledPay(sc, p, bk), 0), 0));
    const viaStat = (d.series.filter(s => s[0] === bk)[0] || [0, 0])[1];
    X.pst.gran = keepG; X.pst.ym = keepY;
    if (!bk) throw new Error('左栏桶为空');
    if (viaLed !== viaStat) throw new Error(`与台账「付款」出口不一致：${viaLed} ≠ ${viaStat}`);
    if (V.m05().indexOf('付款统计') < 0) throw new Error('页面上没有「付款统计」模块');
  });
  ck('付款统计：粒度可切「按月 / 按周」—— 月 = **选定年 12 个月**；周 = **选定季度全部周**（标签为「周一 ~ 周日」）', (function () {
    const keepG = X.pst.gran, keepY = X.pst.ym;
    X.pst.gran = '月'; X.pst.ym = ''; const m = X.pstData();
    X.pst.gran = '周'; X.pst.ym = ''; const w = X.pstData();
    X.pst.gran = keepG; X.pst.ym = keepY;
    /* 独立判：周桶的键必须落在**周一**（用平台 getDay，不复用原型的 wkMon） */
    const isMon = k => new Date(k + 'T00:00:00').getDay() === 1;
    const y = m.keys[0].slice(0, 4);
    const okM = m.keys.length === 12 && m.keys.every(k => k.slice(0, 4) === y) && m.labels[0] === '1 月';
    const okW = w.keys.length >= 12 && w.keys.length <= 14 && w.keys.every(isMon)
      && /^\d{2}-\d{2} ~ \d{2}-\d{2}$/.test(w.labels[0]);
    return (okM && okW && V.m05().indexOf('data-act="pstGran"') >= 0) ? 1 : 0;
  })(), 1);
  ck('付款统计：**左栏桶可选 · 右栏轴可选**（走真实动作：改桶 / 改年 / 改季度；默认 = 数据里最新那个桶）', (function () {
    const keep = { gran: X.pst.gran, ym: X.pst.ym, year: X.pst.year, q: X.pst.q };
    /* 独立算「最新桶」：数据里最晚的那条单据日期 → 其所在月 / 所在周的周一（**不复用原型的函数**） */
    const monOf = d => { const t = new Date(d + 'T00:00:00'); t.setDate(t.getDate() - ((t.getDay() + 6) % 7));
      return t.getFullYear() + '-' + String(t.getMonth() + 1).padStart(2, '0') + '-' + String(t.getDate()).padStart(2, '0'); };
    const lastD = [...new Set(X.NO.filter(n => !n.excl).map(n => String(n.date).slice(0, 10)).filter(Boolean))].sort().pop();
    ACT.pstGran({ dataset: { g: '月' }, tagName: 'BUTTON' });           /* 换粒度会把桶复位 */
    const okDefM = X.pstY() === lastD.slice(0, 7);
    ACT.pstGran({ dataset: { g: '周' }, tagName: 'BUTTON' });
    const okDefW = X.pstY() === monOf(lastD);
    /* 左栏桶：通过真实动作改到 2026-07 → 项目分布跟着换 */
    ACT.pstGran({ dataset: { g: '月' }, tagName: 'BUTTON' });
    ACT.mpPick({ dataset: { id: 'pstBucket', scope: 'pstb', val: '2026-07' }, tagName: 'BUTTON' });
    const d1 = X.pstData();
    const okBucket = X.pst.ym === '2026-07' && d1.bk === '2026-07' && d1.bkLabel === '2026-07' && d1.byPj.length > 0;
    /* 右栏轴：改年 → 12 个月跟着换；改季度 → 周列表跟着换 */
    ACT.mpPick({ dataset: { id: 'pstAxis', scope: 'psta', val: '2025' }, tagName: 'BUTTON' });
    const okYear = X.pst.year === 2025 && X.pstData().keys[0] === '2025-01';
    ACT.pstGran({ dataset: { g: '周' }, tagName: 'BUTTON' });
    ACT.mpPick({ dataset: { id: 'pstAxis', scope: 'psta', val: '2026Q2' }, tagName: 'BUTTON' });
    const d2 = X.pstData();
    const okQ = X.pst.q === '2026Q2' && d2.axLabel.indexOf('Q2') >= 0 && d2.keys.length >= 12;
    const h = V.m05();
    X.pst.gran = keep.gran; X.pst.ym = keep.ym; X.pst.year = keep.year; X.pst.q = keep.q;
    return (okDefM && okDefW && okBucket && okYear && okQ
      && h.indexOf('data-act="mpToggle" data-id="pstBucket"') >= 0
      && h.indexOf('data-act="mpToggle" data-id="pstAxis"') >= 0) ? 1 : 0;
  })(), 1);
  ck('付款统计：**「按项目」在左侧、时间轴在右侧**（用户口径 2026-09-13）', (function () {
    const h = V.m05(); const i = h.indexOf('付款统计');
    const pj = h.indexOf('>按项目</b>', i), tm = h.indexOf('>按' + X.pst.gran + '</b>', i);
    return (i >= 0 && pj > i && tm > pj) ? 1 : 0;
  })(), 1);
  guard('付款统计：点「按项目」条目 → 联动下方「付款流水」按该项目筛选（再点一次取消）', () => {
    const keep = X.flf.projs.slice(); X.flf.projs.length = 0;
    const top = X.pstData().byPj[0][0];
    ACT.pstPj({ dataset: { pj: top }, tagName: 'DIV' });
    const on = X.flf.projs.slice();
    ACT.pstPj({ dataset: { pj: top }, tagName: 'DIV' });
    const off = X.flf.projs.slice();
    X.flf.projs.length = 0; keep.forEach(v => X.flf.projs.push(v));
    if (!(on.length === 1 && on[0] === top)) throw new Error(`点一次没有把该项目并进多选：${on.join(',')}`);
    if (off.length !== 0) throw new Error(`再点一次没有取消：${off.join(',')}`);
  });
  guard('付款统计：**按项目列表必须是完整项目名**（周粒度下不得被当成日期截断前 5 个字符）', () => {
    const keepG = X.pst.gran, keepY = X.pst.ym;
    X.pst.gran = '周'; X.pst.ym = '';
    const d = X.pstData();
    const page = V.m05();
    X.pst.gran = keepG; X.pst.ym = keepY;
    if (d.g !== '周') throw new Error('没切到周粒度 → 这条断言无效');
    if (!d.byPj.length) throw new Error('该周没有项目 → 这条断言无效（得换一个保证有数据的桶）');
    const top = String(d.byPj[0][0]);
    /* 只看**左栏那一段**（「按项目」到「按周」之间）的可见文字，title 不算 —— 旧 bug 坏的正是可见文字 */
    const seg = page.slice(page.indexOf('>按项目</b>'), page.indexOf('>按周</b>'));
    const labs = (seg.match(/class="nm"[^>]*>[^<]*</g) || []).map(s => s.slice(s.indexOf('>') + 1, -1));
    if (!labs.length) throw new Error('左栏没渲染出任何条目');
    /* 左栏显示的是**展示名**（候选键是仓库名，§2.7.4）⇒ 与 `pjLabel(top)` 比，不比键本身 */
    if (labs[0] !== X.pjLabel(top)) throw new Error(`按项目显示的不是规范展示名：「${labs[0]}」≠「${X.pjLabel(top)}」`);
  });
  guard('付款统计：**「按周 / 按月」两个按钮都不是主按钮**（无 pri），且都在卡头**标题右侧（靠左）**、**「按周」在「按月」左边**', () => {
    const h = V.m05();
    const i = h.indexOf('付款统计');
    const a = h.indexOf('data-act="pstGran" data-g="月"', i);
    const b = h.indexOf('data-act="pstGran" data-g="周"', i);
    const sp = h.indexOf('<span class="sp"', i);
    if (a < 0 || b < 0) throw new Error('缺「按月 / 按周」按钮');
    /* ⭐ 2026-09-13 用户口径：**「按周」在「按月」左边**（原来相反） */
    if (!(b < a && a < sp)) throw new Error('按钮不在「标题之后、右侧信息之前」，或「按周」没排在「按月」左边');
    if (h.slice(b - 40, b).indexOf('pri') >= 0 || h.slice(b, a).indexOf('pri') >= 0) throw new Error('「按周」仍是主按钮');
    if (h.slice(a, a + 40).indexOf('pri') >= 0) throw new Error('「按月」仍是主按钮');
  });
  guard('付款统计：点条目后，下方流水的「付款项目」**共用面板**也含该项目（状态与界面不脱节）', () => {
    const keep = X.flf.projs.slice();
    const miss = X.pstData().byPj.map(x => x[0]).find(p => X.flProjs().indexOf(p) < 0);
    if (!miss) { return; }                        /* 若所有项目都已有流水，则本条不适用 */
    X.flf.projs.length = 0; X.flf.projs.push(miss);
    const wasOpen = X.flPjOpenState();
    if (!wasOpen) X.ACT.flPjToggle({ dataset: {}, tagName: 'BUTTON' });   /* 展开共用面板 */
    const h = V.m05();
    if (!wasOpen) X.ACT.flPjToggle({ dataset: {}, tagName: 'BUTTON' });   /* 收起 */
    X.flf.projs.length = 0; keep.forEach(v => X.flf.projs.push(v));
    if (h.indexOf(`data-pj="${miss}"`) < 0) throw new Error('联动的项目（当前无流水）没出现在「付款项目」面板的候选里');
    if (h.indexOf(`data-pj="${miss}" checked`) < 0) throw new Error('联动的项目在面板里没有被勾上（状态与界面脱节）');
  });

  /* ================= MOD-06 过程资料：多核算月 · 项目单选面板 · 默认表② （2026-09-13 用户口径） ================= */
  console.log('\n--- 9za. MOD-06 过程资料：多核算月 · 项目单选面板 · 默认表② ---');
  ck('过程资料：**默认停在表② 调整后表**（比的是**加载时快照** —— 交互路径跑过之后就看不出来了）', PROCTAB0, 1);
  guard('过程资料：表体**一个核算月一行**，且逐月求和 = 全月合计（材料入/出各类 + 机械 6 列**逐列**）', () => {
    const proj = PROCPJ0;
    const ms = X.procMonths(proj);
    if (ms.length < 2) throw new Error('该项目只有 ' + ms.length + ' 个核算月 → 这条断言没有区分力');
    if (ms.slice().sort().join('|') !== ms.join('|')) throw new Error('核算月未按升序：' + ms.join('/'));
    const tot = X.procAgg(proj, false), rows = X.procRows(proj, false);
    const badI = X.IVC5.filter(k => X.N2(rows.reduce((a, r) => a + r.inC[k], 0)) !== tot.inC[k]);
    const badO = X.IVC5.filter(k => X.N2(rows.reduce((a, r) => a + r.outC[k], 0)) !== tot.outC[k]);
    if (badI.length || badO.length) throw new Error(`逐月与合计对不上：入 ${badI.join('/')} 出 ${badO.join('/')}`);
    /* 机械 6 列**逐列**比 —— 只比总额会漏掉"列错位" */
    const badM = [0, 1, 2, 3, 4, 5].filter(i => X.N2(rows.reduce((a, r) => a + r.m[i], 0)) !== tot.m[i]);
    if (badM.length) throw new Error('机械列逐月与合计对不上：列 ' + badM.join('/'));
  });
  guard('过程资料：页面真的渲染出**多行**（行数 = 核算月数，且首列就是核算月）', () => {
    ACT.procTab({ dataset: { i: '1' }, tagName: 'DIV' });
    const h = V.m06();
    const n = (h.match(/<td class="fl fc">/g) || []).length;
    const want = X.procMonths(X.procState().pj).length;
    if (n !== want) throw new Error(`渲染行数 ${n} ≠ 核算月数 ${want}`);
    if (n < 2) throw new Error(`只渲染出 ${n} 行 —— 多核算月的展示没生效（要求 ≥2 行）`);
    const first = (h.match(/<td class="fl fc">([^<]*)</) || [])[1];
    if (!/^\d{4}-\d{2}$/.test(first || '')) throw new Error('首列不是核算月：' + first);
  });
  ck('过程资料：**导出取数跟随当前表**（切表① / 表② / 差异表 → 提示逐一对上；默认即表②）', (function () {
    const cur = X.procState().tab;
    const subOf = () => (V.m06().match(/data-act="exp" data-t="过程资料" data-sub="([^"]*)"/) || [])[1];
    ACT.procTab({ dataset: { i: '1' }, tagName: 'DIV' }); const a = subOf();
    ACT.procTab({ dataset: { i: '0' }, tagName: 'DIV' }); const b = subOf();
    ACT.procTab({ dataset: { i: '2' }, tagName: 'DIV' }); const c = subOf();
    const led = X.procTabName();                                   /* 与页面提示同源，再独立对一次 */
    ACT.procTab({ dataset: { i: String(cur) }, tagName: 'DIV' });
    return (a === '表② 调整后表' && b === '表① 原始表' && c === '差异表' && led === '差异表') ? 1 : 0;
  })(), 1);
  guard('过程资料：项目筛选**复用共用面板且为单选**（radio · 无「全选/清空」· 点一下就切换并收起）', () => {
    ACT.procTab({ dataset: { i: '1' }, tagName: 'DIV' });
    ACT.procPjToggle({ dataset: {}, tagName: 'BUTTON' });
    const h = V.m06();
    const radios = (h.match(/type="radio"/g) || []).length, chks = (h.match(/type="checkbox"/g) || []).length;
    const allBtn = h.indexOf('>全选</button>') >= 0, noneBtn = h.indexOf('>清空</button>') >= 0;
    const checked = (h.match(/checked/g) || []).length;
    if (!(radios === X.PROC_PJS.length && chks === 0 && !allBtn && !noneBtn && checked === 1))
      throw new Error(`单选面板不对：radio ${radios} / checkbox ${chks} / 全选 ${allBtn} / 清空 ${noneBtn} / 选中 ${checked}`);
    /* 从**动作**进去：点另一个候选 → 选中真的换了、面板收起、页面行数跟着换 */
    const other = X.PROC_PJS.filter(f => f !== X.procState().pj)[0];
    ACT.procPjPick({ dataset: { pj: other }, tagName: 'INPUT' });
    const st = X.procState();
    if (st.pj !== other) throw new Error('单选未切换：' + st.pj);
    if (st.open !== false) throw new Error('选中后面板未收起');
    const n = (V.m06().match(/<td class="fl fc">/g) || []).length;
    if (n !== X.procMonths(other).length) throw new Error(`换项目后行数没跟上：${n} ≠ ${X.procMonths(other).length}`);
    ACT.procPjPick({ dataset: { pj: PROCPJ0 }, tagName: 'INPUT' });   /* 复位 */
  });
  ck('过程资料：核算月**只作表内列**（筛选栏已无那个只读框；列本身保留 ⇒ 仍是 17 列）', (function () {
    ACT.procTab({ dataset: { i: '1' }, tagName: 'DIV' });
    const h = V.m06();
    return (h.indexOf('readonly') < 0 && h.indexOf('>核算月</th>') >= 0
      && (h.match(/<thead>([\s\S]*?)<\/thead>/) || ['', ''])[1].split('<th').length - 1 === 17) ? 1 : 0;
  })(), 1);
  ck('三个项目面板的外层都带 .pjwrap（「点外部收起」的唯一契约 —— MOD-04 曾漏挂）',
    (V.m03().indexOf('class="fi pjwrap"') >= 0 && V.m04().indexOf('class="fi pjwrap"') >= 0
      && V.m06().indexOf('class="fi pjwrap"') >= 0) ? 1 : 0, 1);

  /* ================= MOD-06 求和（2026-09-13 用户口径）=================
     ⚠️ 判据一律**独立复算**（自己从 `IVs` / `ADs` / `MACH6` 原始数据累加），**不借** `procAgg` / `procRows`
        —— 用被测对象自己的派生函数自证是既有教训里的"假绿"。 */
  const _procSetPj = () => { if (X.procState().pj !== PROCPJ0) ACT.procPjPick({ dataset: { pj: PROCPJ0 }, tagName: 'INPUT' }); };
  const _procAdjAmt = iv => { const a = X.ADs.find(x => x.ivid === iv.id); return a ? a.newAmt : iv.amt; };
  const _procNum = s => { const m = String(s).match(/(-?[\d,]+\.\d\d)/); if (!m) throw new Error('取不到数字：' + s); return Number(m[1].replace(/,/g, '')); };
  guard('过程资料｜表①② **每个数据列下方**有「合计」行，16 列逐列 = 独立复算（表① 原始 / 表② 调整后**各核一遍**）', () => {
    _procSetPj();
    const g = X.IVs.filter(iv => iv.wh === PROCPJ0);
    const mk = adj => X.IVC5.map(c => X.N2(g.filter(iv => iv.dir === '入库' && iv.c5 === c).reduce((a, iv) => a + (adj ? _procAdjAmt(iv) : iv.amt), 0)))
      .concat(X.IVC5.map(c => X.N2(g.filter(iv => iv.dir === '出库' && iv.c5 === c).reduce((a, iv) => a + (adj ? _procAdjAmt(iv) : iv.amt), 0))))
      .concat([0, 1, 2, 3, 4, 5].map(i => X.N2(Object.keys(X.MACH6[PROCPJ0] || {}).reduce((a, k) => a + X.MACH6[PROCPJ0][k][i], 0))));
    [['1', mk(true), '表②（调整后）'], ['0', mk(false), '表①（原始）']].forEach(([i, want, label]) => {
      ACT.procTab({ dataset: { i: i }, tagName: 'DIV' });
      const tr = (String(V.m06()).match(/<tr[^>]*><td class="fl">合计<\/td>[\s\S]*?<\/tr>/) || [''])[0];
      if (!tr) throw new Error(label + ' 底部没有「合计」行');
      const got = (tr.match(/<td class="num[^"]*">([^<]*)<\/td>/g) || []).map(s => _procNum(s.replace(/<[^>]+>/g, '')));
      if (got.length !== 16) throw new Error(`${label} 的「合计」行有 ${got.length} 个数据格（应为 16 = 入库5+出库5+机械6）`);
      want.forEach((v, k) => { if (got[k] !== v) throw new Error(`${label} 合计第 ${k + 1} 列 ${got[k]} ≠ 独立复算 ${v}`); });
    });
    ACT.procTab({ dataset: { i: String(PROCTAB0) }, tagName: 'DIV' });
  });
  guard('过程资料｜表①② 有「总求和」行 = 入库(5) / 出库(5) / **机械左 4 列**(4) / **不含税 2 列单独**(2) 四段，各 = 独立复算', () => {
    _procSetPj();
    const g = X.IVs.filter(iv => iv.wh === PROCPJ0);
    const m = i => X.N2(Object.keys(X.MACH6[PROCPJ0] || {}).reduce((a, k) => a + X.MACH6[PROCPJ0][k][i], 0));
    const segsOf = h => ((h.match(/<tr[^>]*><td class="fl">总求和[^<]*<\/td>[\s\S]*?<\/tr>/) || [''])[0].match(/<td class="num[^"]*"[^>]*colspan="(\d+)"[^>]*>([^<]*)<\/td>/g) || [])
      .map(s => ({ span: +s.match(/colspan="(\d+)"/)[1], txt: s.replace(/<[^>]+>/g, '') }));
    const seen = {};
    [['1', true, '表②（调整后）'], ['0', false, '表①（原始）']].forEach(([i, adj, label]) => {
      ACT.procTab({ dataset: { i: i }, tagName: 'DIV' });
      const segs = segsOf(String(V.m06()));
      if (segs.length !== 4) throw new Error(`${label} 的「总求和」有 ${segs.length} 段（应为 4 段）`);
      if (segs.map(s => s.span).join(',') !== '5,5,4,2') throw new Error(`${label} 四段的跨列数 ${segs.map(s => s.span).join(',')} ≠ 5,5,4,2`);
      const dir = d => X.N2(g.filter(iv => iv.dir === d).reduce((a, iv) => a + (adj ? _procAdjAmt(iv) : iv.amt), 0));
      const want = [dir('入库'), dir('出库'), X.N2([0, 1, 2, 3].reduce((a, k) => a + m(k), 0)), X.N2([4, 5].reduce((a, k) => a + m(k), 0))];
      const got = segs.map(s => _procNum(s.txt));
      want.forEach((v, k) => { if (got[k] !== v) throw new Error(`${label} 总求和第 ${k + 1} 段 ${got[k]} ≠ 独立复算 ${v}`); });
      seen[label] = got[0];
    });
    /* 表② 与表① 的**入库合计必须不同**（差 = 调整额）⇒ 证明合计跟着**当前显示的那批**走，不是恒取一批 */
    if (seen['表②（调整后）'] === seen['表①（原始）'])
      throw new Error('表② 与表① 的入库合计相同 —— 合计没有跟着当前表走（断言失去区分力）');
    ACT.procTab({ dataset: { i: String(PROCTAB0) }, tagName: 'DIV' });
  });
  guard('过程资料｜差异表也在数据列下方给出「合计」（可求和的只有 原值 / 调整后 / 差额 3 列，跨列数仍 = 11）', () => {
    _procSetPj();
    const adjs = X.IVs.filter(iv => iv.wh === PROCPJ0 && X.adjOf(iv));
    if (!adjs.length) throw new Error('该项目没有调整行 —— 断言失去区分力');
    ACT.procTab({ dataset: { i: '2' }, tagName: 'DIV' });
    const h = String(V.m06());
    const tr = (h.match(/<tr[^>]*><td class="fl" colspan="4">合计<\/td>[\s\S]*?<\/tr>/) || [''])[0];
    if (!tr) throw new Error('差异表底部没有「合计」行');
    const cells = (tr.match(/<td\b[^>]*>/g) || []);
    const span = cells.reduce((a, s) => a + (+((s.match(/colspan="(\d+)"/) || [0, 1])[1])), 0);
    const ths = ((h.match(/<thead>([\s\S]*?)<\/thead>/) || ['', ''])[1].match(/<th\b/g) || []).length;
    if (span !== ths) throw new Error(`差异表合计行跨列数 ${span} ≠ 表头列数 ${ths}`);
    const got = (tr.match(/<td class="num">([^<]*)<\/td>/g) || []).map(s => _procNum(s.replace(/<[^>]+>/g, '')));
    const want = [X.N2(adjs.reduce((s, iv) => s + iv.amt, 0)), X.N2(adjs.reduce((s, iv) => s + X.adjOf(iv).newAmt, 0)), X.N2(adjs.reduce((s, iv) => s + X.N2(X.adjOf(iv).newAmt - iv.amt), 0))];
    if (got.length !== 3) throw new Error(`差异表合计有 ${got.length} 个数据格（应为 3）`);
    want.forEach((v, k) => { if (got[k] !== v) throw new Error(`差异表合计第 ${k + 1} 格 ${got[k]} ≠ 独立复算 ${v}`); });
    ACT.procTab({ dataset: { i: String(PROCTAB0) }, tagName: 'DIV' });
  });
  ACT.procTab({ dataset: { i: '1' }, tagName: 'DIV' });

  /* ================= MOD-07 收发结存「核算年月」（2026-09-13 用户口径） ================= */
  console.log('\n--- 9zg. MOD-07 收发结存：核算年月（默认 = 北京时间上月） ---');
  const _whPick = v => X.ACT.mpPick({ dataset: { id: 'whMonth', scope: 'wh', val: v }, tagName: 'BUTTON' });
  const _whRowSumOf = h => {
    const tr = (h.match(/<td>合计<\/td>[\s\S]*?<\/tr>/) || [''])[0];
    const cells = (tr.match(/<td class="num">([^<]*)<\/td>/g) || []).map(s => Number(s.replace(/<[^>]+>/g, '').replace(/,/g, '')));
    if (!cells.length) throw new Error('没抓到「合计」行 —— 断言失去区分力');
    return cells[0];
  };
  guard('收发结存｜默认核算年月 = **北京时间上月**（§9.2；比的是**加载时快照** —— 交互路径跑过就看不出来了）', () => {
    if (FWHY0 !== X.bjMonth(-1)) throw new Error(`默认 ${FWHY0} ≠ 上月 ${X.bjMonth(-1)}`);
  });
  guard('收发结存｜切月 → 表数据跟着换（行数合计 = 独立复算），且三个月数据**互不相同**（有区分力）', () => {
    const indep = ym => X.WHM[ym].reduce((a, w) => a + w.rows, 0);
    const vals = ['2026-07', '2026-06', '2026-08'].map(ym => {
      _whPick(ym);
      if (X.whYmState() !== ym) throw new Error('切月后状态没跟着走：' + X.whYmState());
      const got = _whRowSumOf(String(V.m07())), want = indep(ym);
      if (got !== want) throw new Error(`切到 ${ym} 后行数合计 ${got} ≠ 独立复算 ${want}`);
      return got;
    });
    if (new Set(vals).size !== vals.length) throw new Error('演示数据里三个月的行数有重复 ⇒ 断言失去区分力：' + vals.join('/'));
  });
  guard('收发结存｜切到**没有数据的月** → 有空态提示行，跨列数 = 表头列数（**独立数 `<th>`**，不借 thCount 自证）', () => {
    _whPick('2026-05');                                   /* 演示数据只铺到 2026-06 ⇒ 05 及更早为空 */
    const h = String(V.m07());
    const ths = (_tblByKey(h, 'm07:warehouses').match(/<th\b/g) || []).length;
    const m = h.match(/<tr><td colspan="(\d+)"[^>]*>([\s\S]*?)<\/td><\/tr>/);
    if (!m) throw new Error('空场景没有提示行（tbody 直接空白）');
    if (+m[1] !== ths) throw new Error(`空态跨列数 ${m[1]} ≠ 表头列数 ${ths}`);
    if (!String(m[2]).replace(/<[^>]+>/g, '').trim()) throw new Error('空态行是空白的');
    _whPick(X.bjMonth(-1));
  });
  guard('收发结存｜「重置」回到默认上月；且 `WHs` **不随月份漂**（MOD-08 的「项目」筛选仍列出全部仓库 —— 防跨页污染）', () => {
    const n0 = X.WHs.length;
    _whPick('2026-06');
    if (X.WHs.length !== n0) throw new Error('切月把 WHs 也换了 ⇒ 跨页污染');
    /* MOD-08 的「项目」筛选 = **共用项目面板（单选）** ⇒ 打开面板数选项（键 = 仓库名），不再有 <option> */
    X.ACT.invWhToggle({ dataset: {}, tagName: 'BUTTON' });
    const n = (String(V.m08()).match(/data-act="invWh"/g) || []).length;
    X.ACT.invWhToggle({ dataset: {}, tagName: 'BUTTON' });       /* 收起，复位 */
    if (n !== n0) throw new Error(`MOD-08「项目」面板列出 ${n} 项 ≠ 全部 ${n0} 仓`);
    X.ACT.whReset({ dataset: {}, tagName: 'BUTTON' });
    if (X.whYmState() !== X.bjMonth(-1)) throw new Error('「重置」没回到默认的「上月」');
  });

  /* ============ MOD-07 焊材 / 气体提取（核对工具；2026-09-13 用户口径）============ */
  console.log('\n--- 9zh. MOD-07 焊材 / 气体提取：项目状态 · 金额月份 · 分组紧贴 ---');
  const _extPick = v => X.ACT.mpPick({ dataset: { id: 'extMonth', scope: 'ext', val: v }, tagName: 'BUTTON' });
  const _extTbl = h => (String(h).match(/<table[^>]*data-sort-key="m07:kinds"[\s\S]*?<\/table>/) || [''])[0];
  const _extCellRows = h => (_extTbl(h).match(/<tr\b[^>]*>[\s\S]*?<\/tr>/g) || []).slice(1)
    .map(r => (r.match(/<td\b[^>]*>([\s\S]*?)<\/td>/g) || []).map(c => c.replace(/<[^>]+>/g, '').replace(/&nbsp;/g, ' ').trim()));
  const _num = s => Number(String(s).replace(/,/g, ''));
  guard('提取表｜「金额」列 = 所选**月份范围**（独立复算）、「总金额」列 = 全部月累计（**不随月份变**）', () => {
    const WH = '临沂钢铁余热发电项目仓库';
    const indep = ym => X.N2(X.extMons().reduce((a, m) => a + (X.tmIn(ym, m) ? X.extMon('焊材', WH, m) : 0), 0));
    /* ⚠️ 列下标随表头走：2026-09-18「结余」列插在「仓库」之后 ⇒ 总金额 / 金额 由 [2][3] 移到 **[3][4]** */
    const cellOf = h => { const r = _extCellRows(h).find(x => x[1] === WH); if (!r) throw new Error('没抓到 ' + WH + ' 的行'); return { total: _num(r[3]), val: _num(r[4]) }; };
    _extPick('2026-08');
    const a = cellOf(V.m07()), ta = X.extTotal('焊材', WH);
    if (a.total !== ta) throw new Error('总金额列 ' + a.total + ' ≠ 独立复算的全月累计 ' + ta);
    if (a.val !== indep('2026-08')) throw new Error('金额列 ' + a.val + ' ≠ 独立复算 ' + indep('2026-08'));
    _extPick('2026-06');
    const b = cellOf(V.m07());
    if (b.total !== a.total) throw new Error('切月后「总金额」跟着变了 —— 它应恒等于全月累计');
    if (b.val === a.val) throw new Error('切月后「金额」没变 ⇒ 断言失去区分力');
    if (b.val !== indep('2026-06')) throw new Error('06 月金额列 ' + b.val + ' ≠ 独立复算 ' + indep('2026-06'));
    _extPick(X.bjMonth(-1));
  });
  guard('提取表｜「项目状态」默认在建（比的是**加载时快照**）；切到「归档」→ 无行且给出**空态提示行**（跨列数 = 表头列数，**独立数 `<th>`**）', () => {
    _extPick(X.bjMonth(-1));
    if (FEXT0 !== '在建') throw new Error('默认项目状态不是「在建」：' + FEXT0);
    if (!_extCellRows(V.m07()).length) throw new Error('「在建」下没有任何行 —— 断言失去区分力');
    X.ACT.fExtStatus({ dataset: {}, tagName: 'SELECT', value: '归档' });
    const h = V.m07();
    const ths = (_extTbl(h).match(/<th\b/g) || []).length;
    const m = h.match(/<tr><td colspan="(\d+)"[^>]*>([\s\S]*?)<\/td><\/tr>/);
    if (!m) throw new Error('切到「归档」后没有空态提示行');
    if (+m[1] !== ths) throw new Error(`空态跨列数 ${m[1]} ≠ 表头列数 ${ths}`);
    if (!String(m[2]).replace(/<[^>]+>/g, '').trim()) throw new Error('空态行是空白的');
    X.ACT.fExtReset({ dataset: {}, tagName: 'BUTTON' });
    if (X.extState().status !== '在建') throw new Error('「重置」没回到默认的「在建」');
  });
  guard('提取表导出｜行 = 所筛选项目 · 列 = 项目 → **最早有数据的月** → …（逐月连续）→ 求和（用户口径）', () => {
    X.ACT.fExtReset({ dataset: {}, tagName: 'BUTTON' });
    X.ACT.expExt({ dataset: {}, tagName: 'BUTTON' });
    const body = String(ctx.document.querySelector('#modalRoot').innerHTML);
    X.ACT.closeModal({ dataset: {}, tagName: 'BUTTON' });
    const t = (body.match(/<table[^>]*data-sort-key="modal:expExt-焊材"[\s\S]*?<\/table>/) || [''])[0];
    if (!t) throw new Error('导出弹窗里没有焊材矩阵');
    const hs = ((t.match(/<thead>[\s\S]*?<\/thead>/) || [''])[0].match(/<th\b[^>]*>([\s\S]*?)<\/th>/g) || []).map(x => x.replace(/<[^>]+>/g, '').trim());
    const want = ['项目'].concat(X.extMons()).concat(['求和']);
    if (hs.join('|') !== want.join('|')) throw new Error(`矩阵表头「${hs.join('|')}」≠ 期望「${want.join('|')}」`);
    const list = X.extVisible('焊材');
    const rows = (t.match(/<tr\b[^>]*>[\s\S]*?<\/tr>/g) || []).slice(1);
    if (rows.length !== list.length + 1) throw new Error(`矩阵数据行 ${rows.length - 1} ≠ 所筛选项目数 ${list.length}`);
    const cells = (rows[0].match(/<td\b[^>]*>([\s\S]*?)<\/td>/g) || []).map(c => c.replace(/<[^>]+>/g, '').trim());
    if (cells[0] !== list[0]) throw new Error('第一行项目与筛选结果首项不一致');
    if (_num(cells[cells.length - 1]) !== X.extTotal('焊材', list[0])) throw new Error('末列「求和」≠ 该项目全月累计');
  });

  /* ================= 通用「时间选择器」：能力由调用点声明（2026-09-13 重做） ================= */
  console.log('\n--- 9t. 通用时间选择器：六模式 · 能力按调用点声明 ---');

  const _openPanel = (id, scope, val, view) => {
    ACT.mpToggle({ dataset: { id: id, scope: scope, val: val }, tagName: 'BUTTON' });
    return view ? view() : String(ctx.document.querySelector('#modalRoot').innerHTML);
  };
  guard('时间选择器：**能力由调用点声明** —— 列表页 4 种模式（月/跨月/年/全部）；抓取弹窗 / 期初截止年月**只有「月」**（不渲染模式条）', function () {
    const h = _openPanel('ntMonth', 'nt', X.fNt.month, () => V.m03());
    const four = ['月', '跨月', '年', '全部'].every(m => h.indexOf(`data-m="${m}"`) >= 0);
    ACT.mpClose({ dataset: { scope: 'nt' } });
    ACT.fetchNt();
    const fh = _openPanel('fetchMonth', 'fetch', '2026-09');
    const onlyM = fh.indexOf('data-act="mpMode"') < 0;      /* 只声明一种模式 ⇒ 不渲染「模式切换条」 */
    ACT.mpClose({ dataset: { scope: 'fetch' } }); ACT.closeModal({ dataset: {}, tagName: 'BUTTON' });
    ACT.addLg({ dataset: { sc: '辅材' }, tagName: 'BUTTON' });
    const lh = _openPanel('lgCutoff', 'lg', X.ledState().cut);
    const onlyL = lh.indexOf('data-act="mpMode"') < 0;
    ACT.mpClose({ dataset: { scope: 'lg' } }); ACT.closeModal({ dataset: {}, tagName: 'BUTTON' });
    ACT.addLg({ dataset: { sc: '辅材' }, tagName: 'BUTTON' }); ACT.closeModal({ dataset: {}, tagName: 'BUTTON' });
    if (!four || !onlyM || !onlyL) throw new Error(`能力声明不符：四模式=${four} 抓取仅月=${onlyM} 期初仅月=${onlyL}`);
  });
  guard('时间选择器：**跨月 = 两击选区间**（先起点、再终点）→ 值 `2026-06~2026-07`，筛选按闭区间生效', () => {
    const keep = X.fNt.month;
    ACT.mpPick({ dataset: { scope: 'nt', val: '2026-06', m: '跨月' }, tagName: 'BUTTON' });   /* 第 1 击 = 起点 */
    ACT.mpPick({ dataset: { scope: 'nt', val: '2026-07', m: '跨月' }, tagName: 'BUTTON' });   /* 第 2 击 = 终点 → 提交 */
    const v = X.fNt.month;
    const hit = X.ntHit({ month: v, cat: '全部', astat: '全部', stat: '全部', projs: [] }).length;
    const want = X.NO.filter(n => !n.excl && n.date >= '2026-06-01' && n.date <= '2026-07-31').length;
    X.fNt.month = keep;
    if (v !== '2026-06~2026-07') throw new Error(`跨月值形态不对：${v}`);
    if (hit !== want) throw new Error(`跨月筛选不对：${hit} ≠ ${want}`);
  });
  guard('时间选择器：「年」模式 = 整年（2026）→ 命中 = 全年 12 个月之和', () => {
    const keep = X.fNt.month;
    ACT.mpPick({ dataset: { scope: 'nt', val: '2026', m: '年' }, tagName: 'BUTTON' });
    const v = X.fNt.month;
    const hit = X.ntHit({ month: v, cat: '全部', astat: '全部', stat: '全部', projs: [] }).length;
    const want = X.NO.filter(n => !n.excl && n.date >= '2026-01-01' && n.date <= '2026-12-31').length;
    X.fNt.month = keep;
    if (v !== '2026') throw new Error(`年值形态不对：${v}`);
    if (hit !== want) throw new Error(`年筛选不对：${hit} ≠ ${want}`);
  });
  guard('时间选择器：**「全部」不再是付款通知书独有**（付款流水 / 付款计划也声明了它）', () => {
    const h = _openPanel('ntMonth', 'nt', X.fNt.month, () => V.m03());
    const ntAll = h.indexOf('data-m="全部"') >= 0;
    ACT.mpClose({ dataset: { scope: 'nt' } });
    const fv = _openPanel('flMonth', 'fl', X.flf.ym, () => V.m05());
    const flAll = fv.indexOf('data-m="全部"') >= 0;
    ACT.mpClose({ dataset: { scope: 'fl' } });
    const pv = _openPanel('plMonth', 'pl', X.plf.ym, () => V.m04());
    const plAll = pv.indexOf('data-m="全部"') >= 0;
    ACT.mpClose({ dataset: { scope: 'pl' } });
    if (!ntAll || !flAll || !plAll) throw new Error(`「全部」未按声明下发：nt=${ntAll} fl=${flAll} pl=${plAll}`);
  });
  resetF(); clearPick(); rollback();

  /* ================= 项目档案的自定义排序（2026-09-13 用户口径） ================= */
  console.log('\n--- 9u. 自定义排序：ord 挂在档案行上，全名 / 仓库名 / 展示名 全站跟随 ---');
  ck('自定义排序：ord 初值 = 建档顺序 1..N', X.PJs.every((p, i) => p.ord === i + 1) ? 1 : 0, 1);
  ck('自定义排序：全名 / 仓库名 / 展示名三种叫法都定位到同一条档案行（同一个 ord）', (function () {
    const p = X.PJs.find(x => x.id === 'P01');
    return (X.pjRowOf(p.full) === p && X.pjRowOf(p.name) === p && X.pjRowOf(p.disp) === p
      && X.ordOf(X.pjRowOf(p.full)) === X.ordOf(p)) ? 1 : 0;
  })(), 1);
  ck('自定义排序：**归档后置优先于 ord**（归档项 ord 改成 1，它仍在最后）', (function () {
    const arc = X.PJs.find(p => p.status === '归档'), bak = arc.ord;
    arc.ord = 1;
    const L = X.pjSortedAll();
    const ok = L[L.length - 1].id === arc.id;
    arc.ord = bak;
    return ok ? 1 : 0;
  })(), 1);
  guard('自定义排序：改 ord → 全站（选项目 / 选仓库 / 选展示名）顺序同步', () => {
    const p = X.PJs.find(x => x.id === 'P07'), bak = p.ord;
    ACT.editOrd({ dataset: { id: p.id }, tagName: 'INPUT', value: '1' });
    const ok = X.pjSortedAll()[0].id === p.id && X.pjSort(X.WHs).length === X.WHs.length;
    p.ord = bak; X.renumberPj();
    if (!ok) throw new Error('改 ord 后顺序没跟上');
  });
  guard('自定义排序：↑ / ↓ = 与相邻一行对调（不跨归档分界）', () => {
    const L = X.pjSortedAll(), a = L[0], b = L[1];
    ACT.ordDown({ dataset: { id: a.id }, tagName: 'BUTTON' });
    const L2 = X.pjSortedAll();
    const ok = L2[0].id === b.id && L2[1].id === a.id;
    ACT.ordUp({ dataset: { id: a.id }, tagName: 'BUTTON' });
    if (!ok) throw new Error('↓ 没有与下一行对调');
    if (X.pjSortedAll()[0].id !== a.id) throw new Error('↑ 没有换回来');
  });
  ck('自定义排序：重编号后序号恒为 1..N、连续无重复', (function () {
    const p = X.PJs.find(x => x.id === 'P05'), bak = p.ord;
    p.ord = 999; X.renumberPj();
    const ords = X.PJs.map(x => x.ord).slice().sort((m, n) => m - n);
    const ok = ords.every((v, i) => v === i + 1);
    p.ord = bak; X.renumberPj();
    return ok ? 1 : 0;
  })(), 1);
  resetF(); clearPick(); rollback();

  /* ================= 小微壳的归档不变式（2026-09-13 用户口径） ================= */
  console.log('\n--- 9v. 归档小微壳：壳归档 ⇔ 具体小微已全部归档 ---');
  guard('归档壳：壳下还有在建小微 → **被拦截**（状态不变、不留痕）', () => {
    const sh = X.PJs.find(p => p.type === 'shell');
    const live = X.PJs.filter(k => k.parent === sh.id && k.status === '在建');
    if (!live.length) throw new Error('样本不成立：该壳下没有在建小微');
    const t0 = X.PJ_TRAIL.length;
    ACT.editStatus({ dataset: { id: sh.id }, tagName: 'SELECT', value: '归档' });
    if (X.PJs.find(p => p.id === sh.id).status !== '在建') throw new Error('壳被归档了（应被拦截）');
    if (X.PJ_TRAIL.length !== t0) throw new Error('被拦截了却还是写了留痕');
  });
  guard('归档壳：壳下小微**全部归档**后 → 壳可以正常归档', () => {
    const sh = X.PJs.find(p => p.type === 'shell');
    X.PJs.filter(k => k.parent === sh.id).forEach(k => { k.status = '归档'; });
    ACT.editStatus({ dataset: { id: sh.id }, tagName: 'SELECT', value: '归档' });
    const ok = X.PJs.find(p => p.id === sh.id).status === '归档';
    X.PJs.filter(k => k.parent === sh.id).forEach(k => { k.status = '在建'; });
    sh.status = '在建';
    if (!ok) throw new Error('小微全归档后，壳仍无法归档');
  });
  guard('对称规则：把壳下**最后一个在建小微**归档 → 壳自动跟着归档', () => {
    const sh = X.PJs.find(p => p.type === 'shell');
    const kids = X.PJs.filter(k => k.parent === sh.id);
    sh.status = '在建';
    kids.forEach((k, i) => { k.status = (i === 0) ? '在建' : '归档'; });   /* 只留第 1 个在建 */
    ACT.editStatus({ dataset: { id: kids[0].id }, tagName: 'SELECT', value: '归档' });
    const ok = kids[0].status === '归档' && sh.status === '归档';
    kids.forEach(k => { k.status = '在建'; }); sh.status = '在建';
    if (!ok) throw new Error('最后一个在建小微归档后，壳没有自动归档');
  });
  guard('已归档的壳下**不许新建小微**（会当场破坏不变式）', () => {
    const n = X.NO.find(x => X.isShellFull(x.proj));
    const sh = X.PJs.find(p => p.type === 'shell' && p.full === n.proj);
    if (!n || !sh) throw new Error('找不到壳单据样本');
    const bak = sh.status, n0 = X.PJs.length;
    sh.status = '归档';
    doc.querySelector('#ownNewName').value = '测试-新小微仓库';
    doc.querySelector('#ownNewKw').value = String(n.doc || '').slice(0, 2);   /* 保证出现在单据名里 */
    ACT.ownOk({ dataset: { id: n.id, pid: '__new' }, tagName: 'BUTTON' });
    sh.status = bak;
    if (X.PJs.length !== n0) throw new Error('已归档的壳下仍被建出了新小微');
  });
  resetF(); clearPick(); rollback();

  /* ================= MOD-15 用户管理（§1.5 角色与权限） ================= */
  console.log('\n--- 9x. MOD-15 用户管理（§1.5） ---');
  ck('账号数与 §1.5.1 一致（2 个）', X.USERS.length, 2);
  ck('MOD-15 右上角有「登出」入口，且 logout / logoutOk 动作在',
    (V.m15().indexOf('data-act="logout"') >= 0 && typeof ACT.logout === 'function' && typeof ACT.logoutOk === 'function') ? 1 : 0, 1);
  ck('MOD-15 管理动作齐全：建号 / 改密 / 停用启用 / 删除 / 转让管理员（仍不设业务权限配置）',
    (['userAdd', 'userAddOk', 'userPwd', 'userPwdOk', 'userToggle', 'userDel', 'userDelOk', 'userRestore', 'userTransfer', 'userTransferOk']
      .every(a => typeof ACT[a] === 'function')
      && !Object.keys(ACT).some(a => /perm/i.test(a))) ? 1 : 0, 1);
  ck('当前登录用户 = 管理员（§1.5.1「用户本人为管理员」）', X.CUR.role === 'admin' ? 1 : 0, 1);
  guard('MOD-15：新增账号一律「在用 · 普通用户」；登录账号不限格式、密码可为空', () => {
    doc.querySelector('#uAcc').value = '李';      /* 口径：非空 + 不重复即可（不再是「字母开头 ≥3 位」） */
    doc.querySelector('#uName').value = '李振'; doc.querySelector('#uPwd').value = '';
    ACT.userAddOk({ dataset: {}, tagName: 'BUTTON' });
    if (X.USERS.length !== 3) throw new Error('未新增（账号名格式被误拦？）');
    const u = X.USERS[X.USERS.length - 1];
    if (u.role !== 'user' || u.status !== '在用') throw new Error('新增账号不是「在用 · 普通用户」');
    if (u.pwd !== '') throw new Error('空密码未被接受（建号）');
  });
  guard('MOD-15：登录账号重复 → 拒绝创建（不新增）', () => {
    const n0 = X.USERS.length;
    doc.querySelector('#uAcc').value = 'zhangwei'; doc.querySelector('#uName').value = '重复'; doc.querySelector('#uPwd').value = '';
    ACT.userAddOk({ dataset: {}, tagName: 'BUTTON' });
    if (X.USERS.length !== n0) throw new Error('重复账号被创建了');
  });
  guard('MOD-15：登录账号为空 → 拒绝创建', () => {
    const n0 = X.USERS.length;
    doc.querySelector('#uAcc').value = '   '; doc.querySelector('#uName').value = '空账号';
    ACT.userAddOk({ dataset: {}, tagName: 'BUTTON' });
    if (X.USERS.length !== n0) throw new Error('空账号被创建了');
  });
  guard('MOD-15：密码无长度限制、可清空（建号与改密都不拦）', () => {
    const n0 = X.USERS.length;
    doc.querySelector('#uAcc').value = 'duanmi'; doc.querySelector('#uName').value = '短密'; doc.querySelector('#uPwd').value = '123';
    ACT.userAddOk({ dataset: {}, tagName: 'BUTTON' });
    if (X.USERS.length !== n0 + 1) throw new Error('3 位密码被误拦（口径：密码不限制长度）');
    const u2 = X.USERS.find(x => x.id === 'U02');
    doc.querySelector('#upV').value = '1';
    ACT.userPwdOk({ dataset: { id: 'U02' }, tagName: 'BUTTON' });
    if (u2.pwd !== '1') throw new Error('改密被误拦（1 位密码）');
    doc.querySelector('#upV').value = '';
    ACT.userPwdOk({ dataset: { id: 'U02' }, tagName: 'BUTTON' });
    if (u2.pwd !== '') throw new Error('空密码未被接受（改密）');
  });
  guard('MOD-15：不能停用 / 删除「最后一个在用管理员」（防锁死）', () => {
    const me = X.USERS.find(x => x.id === X.CUR.id);
    if (me.role !== 'admin' || me.status !== '在用') throw new Error('前置：当前登录应为在用的管理员');
    const n0 = X.USERS.length;
    ACT.userToggle({ dataset: { id: X.CUR.id }, tagName: 'BUTTON' });
    if (me.status !== '在用') throw new Error('把最后一个管理员停用了');
    ACT.userDelOk({ dataset: { id: X.CUR.id }, tagName: 'BUTTON' });   /* 直接调写操作，也必须被拦（不只靠按钮禁用） */
    if (me.status === '已删除' || X.USERS.length !== n0) throw new Error('把最后一个管理员删了');
  });
  guard('MOD-15：停用 ≠ 删除（行数不变、状态可来回切）', () => {
    const n0 = X.USERS.length;
    ACT.userToggle({ dataset: { id: 'U02' }, tagName: 'BUTTON' });
    if (X.USERS.length !== n0) throw new Error('停用把账号删掉了');
    if (X.USERS.find(x => x.id === 'U02').status !== '已停用') throw new Error('未停用');
    ACT.userToggle({ dataset: { id: 'U02' }, tagName: 'BUTTON' });
    if (X.USERS.find(x => x.id === 'U02').status !== '在用') throw new Error('未恢复启用');
  });
  guard('MOD-15：删除用户 = 软删（行保留、账号名可识别、可恢复）', () => {
    const n0 = X.USERS.length, u2 = X.USERS.find(x => x.id === 'U02');
    ACT.userDelOk({ dataset: { id: 'U02' }, tagName: 'BUTTON' });
    if (X.USERS.length !== n0) throw new Error('删除把行删掉了（应为软删）');
    if (u2.status !== '已删除') throw new Error('未标记「已删除」');
    if (!u2.acc || !u2.name) throw new Error('账号名 / 姓名被清空 —— 历史留痕将认不出人');
    ACT.userRestore({ dataset: { id: 'U02' }, tagName: 'BUTTON' });
    if (u2.status !== '在用') throw new Error('未恢复');
  });
  guard('MOD-15：授权转让 —— 目标变管理员、自己转为普通用户（恒只有一个管理员）', () => {
    const u2 = X.USERS.find(x => x.id === 'U02');
    doc.querySelector('#utId').value = 'U02';
    ACT.userTransferOk({ dataset: {}, tagName: 'BUTTON' });
    if (u2.role !== 'admin') throw new Error('目标未成为管理员');
    if (X.CUR.role !== 'user') throw new Error('自己未转为普通用户');
    if (X.USERS.filter(x => x.role === 'admin' && x.status === '在用').length !== 1) throw new Error('管理员不唯一（应为 1）');
  });
  guard('MOD-15 写操作后已回滚（USERS 恢复 2 条 / 当前登录恢复管理员）', () => {
    rollback();
    if (X.USERS.length !== 2) throw new Error('USERS 未复位：' + X.USERS.length);
    if (X.CUR.role !== 'admin') throw new Error('当前登录角色未复位');
  });

  /* ---------- 9z. MOD-11 集采三态「批量标记」（§6.5.3） ---------- */
  const jcAll = () => { doc.querySelector('#fTag').value = '全部'; doc.querySelector('#fArch').value = '全部'; doc.querySelector('#fSup').value = ''; ACT.jcFilter({ dataset: {}, tagName: 'SELECT' }); };
  guard('MOD-11：三态标记 = 逐条 + 批量（§6.5.3 写明「支持批量标记」）', () => {
    const h = V.m11();
    if (h.indexOf('data-act="jcTag"') < 0) throw new Error('缺逐条标记入口');
    if (h.indexOf('data-act="jcBatchTag"') < 0) throw new Error('缺批量标记入口');
    for (const a of ['jcPick', 'jcPickAll', 'jcBatchTag']) if (typeof X.ACT[a] !== 'function') throw new Error('缺动作 ' + a);
  });
  guard('MOD-11：未勾选时批量按钮**先禁用**（R14 前置禁用，不是点了才拦）', () => {
    rollback(); X.jcPick.clear();
    const btns = V.m11().match(/data-act="jcBatchTag"[^>]*/g) || [];
    if (btns.length !== 2) throw new Error('批量按钮应为 2 个，实际 ' + btns.length);
    if (!btns.every(b => /\bdisabled\b/.test(b))) throw new Error('未勾选时未禁用');
    X.jcPick.add('J10');
    const btns2 = V.m11().match(/data-act="jcBatchTag"[^>]*/g) || [];
    if (btns2.some(b => /\bdisabled\b/.test(b))) throw new Error('勾选后仍被禁用');
    X.jcPick.clear();
  });
  guard('MOD-11：批量标记**只作用于勾选行**、动作后清空勾选、不改行数', () => {
    rollback(); X.jcPick.clear(); jcAll();
    const n0 = X.JCs.length, c0 = X.JCs.filter(j => j.tag === '纳入台账').length;
    const tgt = X.JCs.find(j => j.tag !== '纳入台账');
    X.jcPick.add(tgt.id);
    ACT.jcBatchTag({ dataset: { v: '纳入台账' }, tagName: 'BUTTON' });
    const c1 = X.JCs.filter(j => j.tag === '纳入台账').length;
    if (X.JCs.find(j => j.id === tgt.id).tag !== '纳入台账') throw new Error('勾选行未被标记');
    if (c1 !== c0 + 1) throw new Error(`影响了非勾选行：纳入台账 ${c0} → ${c1}`);
    if (X.jcPick.size !== 0) throw new Error('动作后未清空勾选');
    if (X.JCs.length !== n0) throw new Error('行数被改动');
  });
  guard('MOD-11：全选范围 = 当前筛选结果；筛选收紧后勾选被裁剪（不越界）', () => {
    rollback(); X.jcPick.clear(); jcAll();
    ACT.jcPickAll({ dataset: {}, tagName: 'INPUT' });
    if (X.jcPick.size !== X.JCs.length) throw new Error('全部视图下全选应=全库行数');
    /* ⭐ TAIL-97：改用「不纳入」收窄 —— 原来用「待确认」（该值已取消，筛出 0 行）
       ⇒ `vis >= X.JCs.length` 与「全被标记」两条断言**退化成空转**（0 < 12 恒真）。 */
    doc.querySelector('#fTag').value = '不纳入'; ACT.jcFilter({ dataset: {}, tagName: 'SELECT' });
    const vis = X.jcVisible().length;
    if (vis <= 0 || vis >= X.JCs.length) throw new Error('筛选未生效，测试无效');
    if (X.jcPick.size !== vis) throw new Error(`筛选后勾选应裁剪到 ${vis}，实际 ${X.jcPick.size}`);
    ACT.jcBatchTag({ dataset: { v: '纳入台账' }, tagName: 'BUTTON' });
    if (X.JCs.filter(j => j.tag === '不纳入').length !== 0) throw new Error('批量标记未覆盖全部可见行');
    rollback(); X.jcPick.clear(); jcAll();
  });
  /* ===== §10. 本轮新增守护（2026-09-13）=====
     加这几条的理由（都是实测过的"现在不会报红"）：枚举值域被删值 / 金额规整被弄坏 /
     加列只改表头忘了改行 / .tw 丢了高度上限 —— 失效全是**静默**的。 */
  console.log('\n--- 10. 全站守护（枚举值域 · 金额规整 · 列对齐 · 高度上限 · 时间格式 · 无障碍 · 文案一致性）---');   /* 2026-09-15 拆名：原标题末尾写「+ 近期口径（见各子段）」= catch-all ⇒ 去掉；子段 10a–10f 各自有独立标题 */

  guard('枚举值域：每个枚举域的取值集合与原型声明一致（集合式，不数数量）', () => {
    const EXP = {
      cat: ['辅材', '机械', '集采'], payState: ['已付清', '未付清'], astat: ['已批', '未批'],
      payMethod: ['现汇', '承兑', '供应链', '其他'], flowState: ['生效', '已撤销'], ivDir: ['入库', '出库'],
      pjStatus: ['在建', '归档'], pjType: ['normal', 'shell', 'small'],
      jcTag: ['纳入台账', '不纳入'], jcArch: ['未存档', '资产处', '已存档'],
      plRev: ['完全匹配', '金额不符', '单据号查不到', '无单据号', '重复上报', '超过未付'],
      plRevF: ['全部', '完全匹配', '未匹配'], dfState: ['待核对', '已核对', '差异保留']
    };
    const bad = Object.keys(EXP).filter(k => JSON.stringify((X.ENUMS[k] || {}).vals) !== JSON.stringify(EXP[k]));
    if (bad.length) throw new Error('枚举值域不符：' + bad.join('、'));
  });
  guard('枚举：域外值退回灰色破折号（不静默显示空白）', () => {
    const g = X.enumTag('cat', '不存在的分类');
    if (g.indexOf('<span class="mut">—</span>') < 0) throw new Error('域外值未退回破折号：' + g);
    if (X.enumTag('cat', '辅材').indexOf('辅材') < 0) throw new Error('域内值渲染异常');
  });
  guard('金额规整：2 位小数 + HALF_UP + 非法输入原样透出 NaN（铁律 1 · §9.1）', () => {
    const cases = [['12.345', 12.35], ['-0.005', -0.01], ['0.004', 0], ['1.005', 1.01], ['2', 2], ['  8  ', 8]];
    cases.forEach(([i, e]) => { const g = X.numOf(i); if (g !== e) throw new Error('numOf(' + i + ') = ' + g + '，期望 ' + e); });
    if (!Number.isNaN(X.numOf(''))) throw new Error('空串应透出 NaN（不能被当成 0）');
    if (!Number.isNaN(X.numOf('abc'))) throw new Error('非法输入应透出 NaN');
    if (!Number.isNaN(X.numOf(null))) throw new Error('null 应透出 NaN');
  });
  guard('上限判定只有一个容差出口（CAP_TOL）：等于上限不算超、略超即算超', () => {
    if (X.overCap(100, 100)) throw new Error('等于上限被判成超上限');
    if (!X.overCap(100.01, 100)) throw new Error('超出上限未被判出');
    if (X.CAP_TOL !== 0.005) throw new Error('容差常量被改动：' + X.CAP_TOL);
  });
  guard('列对齐：每张可排表的数据行 <td> 数 = 表头列数（排除合计行与跨列行）', () => {
    Object.keys(V).filter(k => k !== 'home').forEach(vk => {
      const h = String(V[vk]());
      (h.match(/<table\b[^>]*\bdata-sort\b[\s\S]*?<\/table>/g) || []).forEach(tbl => {
        /* 列数 = **表头第一行的 `colspan` 累加** —— 两行表头（分组表头）时 `<th>` 总数 ≠ 列数，
           直接数 `<th>` 会把 `MOD-07` 活动大表误判成"23 列"（2026-09-13 大表改两行表头时踩到）。 */
        const _h0 = ((tbl.match(/<thead\b[^>]*>([\s\S]*?)<\/thead>/i) || ['', ''])[1].match(/<tr\b[^>]*>[\s\S]*?<\/tr>/i) || [''])[0];
        const ths = (_h0.match(/<th\b[^>]*>[\s\S]*?<\/th>/gi) || []).reduce((a, th) => a + (+((th.match(/colspan="(\d+)"/) || [0, 1])[1])), 0);
        if (ths < 2) return;
        const b = tbl.match(/<tbody\b[^>]*>([\s\S]*?)<\/tbody>/i); if (!b) return;
        (b[1].match(/<tr\b[^>]*>[\s\S]*?<\/tr>/gi) || []).forEach(r => {
          if (/合计|总计|小计/.test(r)) return;
          if (/<td\b[^>]*\bcolspan=/i.test(r)) return;
          const tdc = (r.match(/<td\b/gi) || []).length;
          if (tdc !== ths) throw new Error(vk + ' 行列数不齐：表头 ' + ths + ' 列，该行 ' + tdc + ' 个 <td>');
        });
      });
    });
  });
  guard('R7①｜.tw 必须有高度上限（否则 sticky 表头跟着滚走）', () => {
    const css = html.slice(html.indexOf('<style>'), html.indexOf('</style>'));
    const m = css.match(/\.tw\{[^}]*\}/);
    if (!m) throw new Error('样式表里找不到 .tw 基规则');
    if (!/max-height\s*:/.test(m[0])) throw new Error('.tw 缺少 max-height —— sticky 表头会跟着滚走');
  });
  guard('时间戳唯一出口：一律「补零 + 到秒」（YYYY-MM-DD HH:MM:SS）', () => {
    const s = X.fmtTime(new Date(2026, 8, 3, 8, 5, 7));
    if (s !== '2026-09-03 08:05:07') throw new Error('fmtTime 未补零：' + s);
    if (!/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(X.nowStamp())) throw new Error('now() 未走 fmtTime：' + X.nowStamp());
    const tr = X.NO.find(x => x.id === 'A17').trail[0];
    if (!/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(tr.at)) throw new Error('预置留痕时间格式不统一：' + tr.at);
  });

  /* ===== 2026-09-13 新增守护（用户拍板）：① 实现载体叙事文案一致性 ② 候选「不施加在建过滤」 ③ 候选键显示 ===== */
  guard('文案一致性｜机械的取数不得被描述成手填（§5.6.1.1：结算 = 派生只读，手填只在源头）', () => {
    const bad = [];
    const strip = h => h.replace(/<[^>]*>/g, '');   /* 先去标签再按纯文本判定（HTML 属性会把字符间距拉长，正文则不会） */
    /* ① 含「结算」的四种形态 —— 全站三页都扫 */
    const P1 = [/手填结算/, /机械费结算[^。；！？]{0,15}手填/, /手填[^。；！？]{0,15}机械费结算/, /结算金额[^。；！？]{0,15}手填/];
    /* ② 不含「结算」的「机械 = …手填」形态 —— **只扫 home / MOD-05**：
       `MOD-10` 整页在讲「源头在过程资料机械 6 列、都先手填」，属**合法描述** ⇒ 对它用 ② 会假红。
       ⚠️ 白名单词（源头 / 列 / 合计 / 大表 / 成本）出现在「机械…手填」之间时放行 —— 它们标志"说的是源头"。 */
    const P2 = [/机械(?![^。；！？]{0,8}(源头|列|合计|大表|成本))[^。；！？]{0,8}手填/];
    const scan = (n, h, pats) => { const t = strip(h); if (pats.some(re => re.test(t))) bad.push(n); };
    scan('home', V.home(), P1.concat(P2));
    scan('MOD-05', V.m05(), P1.concat(P2));
    scan('MOD-10', V.m10(), P1);
    if (bad.length) throw new Error('这些页面仍把机械的取数说成手填：' + bad.join(' / '));
  });
  guard('项目候选不施加「在建」过滤：归档项目一旦有数据就出现、且排最后（§2.7.1）', () => {
    const arc = X.PJs.find(p => X.arcOf(p));
    if (!arc) throw new Error('演示数据里没有归档项目 —— 本断言失去区分力');
    if (X.PL_PROJ_LIST().indexOf(arc.name) >= 0) throw new Error('该归档项本来就在候选里 —— 本断言在当前数据下无区分力');
    const tpl = X.PLs[0];
    X.PLs.push(Object.assign({}, tpl, { id: '__T_CAND', proj: arc.disp || arc.name, docNo: '', flowAmt: 0, monthAmt: 0 }));
    try {
      const after = X.PL_PROJ_LIST();
      if (after.indexOf(arc.name) < 0) throw new Error('挂了计划行后归档项仍未进候选 —— 候选被施加了「在建」过滤');
      if (after[after.length - 1] !== arc.name) throw new Error('归档项没有排在候选最后');
    } finally { X.PLs.pop(); }
  });
  ck('付款流水「付款项目」的筛选与列一律显示**展示名**、不再显示全名（§2.7.4）', (function () {
    const wasOpen = X.flPjOpenState();
    if (!wasOpen) X.ACT.flPjToggle({ dataset: {}, tagName: 'BUTTON' });   /* 展开共用面板才看得到候选项 */
    const h = V.m05();
    if (!wasOpen) X.ACT.flPjToggle({ dataset: {}, tagName: 'BUTTON' });   /* 收起，复位 */
    /* ⚠️ 只核**面板里每个候选项的可见文字**（`<span>`）——
       每项的 `title` 里**刻意**给出「仓库名：X」（§2.7.4 的悬停提示）⇒ 拿整段 HTML 去搜仓库名必然搜得到，
       会**误判成"显示了全名"**（假红）。 */
    const labs = [...h.matchAll(/data-act="flPjPick"[^>]*>\s*<span[^>]*>([^<]*)<\/span>/g)].map(x => x[1]);
    if (!labs.length) return 0;
    const hasDisp = labs.indexOf('德州热电') >= 0;                       /* 显示的是**展示名** */
    const noName = !labs.some(t => t === '华能德州热电联产项目仓库');      /* 不是**仓库名** */
    const headNoFull = h.indexOf('付款项目（全名）') < 0;                 /* 列头也不再写「全名」 */
    return (hasDisp && noName && headNoFull) ? 1 : 0;
  })(), 1);

  /* ===== 2026-09-13 P1 新增守护（用户授权「连带断言」）：非按钮可点元素必须可键盘触发 =====
     由来：P1 走查实测 —— `data-act` 挂在非按钮元素上的共 8 处（侧栏导航项 / 页内跳转链接 / 页签 / 弹窗关闭 ×），
     改动前**只能鼠标点**（只有表头排序 `th` 与「待指定」标签两处例外）。修法是**两条唯一出口**：
       ① 元素自带 `data-act` + `role="button"` + `tabindex="0"`；
       ② 文件末的**通用** keydown 委托（选择器 `[data-act][role="button"]`）+ 样式表里同选择器的焦点框。
     ⇒ 下面三条守的就是「**新加可点元素时不会漏掉键盘可达**」—— 漏了会**当场红**，不靠人眼翻页面。 */
  guard('无障碍｜非按钮可点元素（渲染出的 data-act）必须带 tabindex + role="button"', () => {
    const NATIVE = ['button', 'input', 'select', 'textarea', 'option', 'label'];
    /* 例外白名单：遮罩层 `maskBg` —— 全屏遮罩**不进 Tab 序**（它的键盘等价物 = Esc，已在委托里实现） */
    const SKIP_ACT = ['maskBg'];
    /* ⚠️ 渲染面必须**三处都扫**（只扫 `V.*` 会漏掉真缺陷 —— 首版就漏了侧栏）：
       ① 全部视图 `V[k]()`  ② **应用外壳**（侧栏/顶栏由 `render()` 拼，不在 `V.*` 里）  ③ 弹窗层 `#modalRoot` */
    X.ACT.go({ dataset: { k: 'home' } });
    X.ACT.zipSfjc();
    const faces = Object.keys(V).map(k => [k, String(V[k]())]);
    ['#nav', '#ttl', '#who'].forEach(s => faces.push(['shell' + s, String(doc.querySelector(s).innerHTML)]));
    faces.push(['modal', String(doc.querySelector('#modalRoot').innerHTML)]);
    X.ACT.closeModal();
    const bad = [];
    faces.forEach(([name, h]) => {
      const re = /<([a-zA-Z0-9]+)\b([^>]*?)data-act="([^"]+)"([^>]*?)>/g;
      let m;
      while ((m = re.exec(h))) {
        const tag = m[1].toLowerCase(), act = m[3], attrs = m[2] + m[4];
        if (NATIVE.indexOf(tag) >= 0 || SKIP_ACT.indexOf(act) >= 0) continue;
        if (!/role="button"/.test(attrs) || !/tabindex="0"/.test(attrs)) bad.push(name + ' <' + tag + ' data-act="' + act + '">');
      }
    });
    if (bad.length) throw new Error('这些可点元素键盘不可达（缺 tabindex / role）：' + bad.join(' · '));
  });
  guard('无障碍｜弹窗层的可点元素同样键盘可达（关闭按钮 ×，带 title 作无障碍名）', () => {
    X.ACT.zipSfjc();
    const h = String(doc.querySelector('#modalRoot').innerHTML);
    X.ACT.closeModal();
    const m = h.match(/<span class="x"[^>]*data-act="closeModal"[^>]*>/);
    if (!m) throw new Error('弹窗里找不到关闭按钮');
    if (!/tabindex="0"/.test(m[0]) || !/role="button"/.test(m[0])) throw new Error('弹窗关闭按钮键盘不可达：' + m[0]);
    if (!/title="/.test(m[0])) throw new Error('弹窗关闭按钮缺 title（图标无文字文本，需给无障碍名）');
  });
  guard('无障碍｜键盘委托与焦点框都是「唯一出口」（不得退回逐个点名）', () => {
    const kd0 = html.indexOf("document.addEventListener('keydown'");
    if (kd0 < 0) throw new Error('找不到 keydown 委托');
    const body = html.slice(kd0, kd0 + 1600);
    if (body.indexOf('[data-act][role="button"]') < 0) throw new Error('keydown 委托未使用通用选择器 [data-act][role="button"]');
    if (/closest\('th\[data-act=/.test(body)) throw new Error('keydown 委托退回了「逐个点名」写法（新元素会静默失效）');
    const css = html.slice(html.indexOf('<style>'), html.indexOf('</style>'));
    if (css.indexOf('[data-act][role="button"]:focus-visible') < 0) throw new Error('焦点框不再是「共用一条规则」');
  });

  /* ===== 2026-09-13 P2 新增守护（用户授权「连带断言」）：提示语必须与真实行为一致 =====
     由来：P2 走查实测出 2 处**假反馈** —— ① MOD-02「手动导入」提示"已打开「X」Excel 上传入口"，而**什么都没打开**；
     ② MOD-02「触发」提示"结果已回显"，而回显区是**静态快照、点了不变**。
     判定口径：**提示语可以说"做了什么"（模拟成功），但不得声称"打开了一个界面"** —— 那是用户当场能证伪的。
     取法：**行为式** —— 劫持 DOM 桩的 `body.appendChild` 抓 toast 文案（不 grep 源码）。 */
  guard('提示语必须与真实行为一致：不得声称「已打开 / 已回显」这类未发生的动作', () => {
    const cap = [];
    const orig = doc.body.appendChild;
    doc.body.appendChild = el => { cap.push(String(el.innerHTML)); };
    try {
      X.ACT.manualUp({ dataset: { t: '付款通知书' }, tagName: 'BUTTON' });
      X.ACT.fetchOne({ dataset: { t: '付款通知书' }, tagName: 'BUTTON' });
      X.ACT.syncWh({ dataset: {}, tagName: 'BUTTON' });          /* ⭐「该放过」的正向样本：模拟成功类提示语 */
    } finally { doc.body.appendChild = orig; }
    if (!cap.length) throw new Error('没抓到任何提示语 —— 断言失去区分力');
    if (!cap.some(s => /已同步/.test(s))) throw new Error('正向样本（「已同步」）没抓到或没被放行 —— 断言失去区分力');
    const fake = cap.filter(s => /已打开|结果已回显/.test(s));
    if (fake.length) throw new Error('提示语声称了未发生的动作：' + fake.map(s => s.replace(/<[^>]*>/g, '')).join(' | '));
  });

  /* ===== 2026-09-13 P3 新增守护（用户授权「连带断言」）：完整日期一律用原生日期选择器 =====
     由来：P3 走查实测 —— MOD-04「付款时间」是全站**唯一**用"纯文本框 + `placeholder="YYYY-MM-DD"`"的日期字段
     （其余三处：批量付款「付款日期」· 手动新增「单据日期」· 集采「合同日期」都用 `type="date"`）。
     口径出处：原型 `:1358` 的既定约定「日期用 `type=date`」＋ §六 第 30 条（"选年月才用 `tmBtn`"）。
     ⇒ 手打日期既慢又易错，属用户明确不接受的"笨控件"。 */
  guard('完整日期一律用原生日期选择器（type="date"），不得做成"手打 YYYY-MM-DD"的纯文本框', () => {
    const bad = [], okDate = [];
    const check = (name, h) => {
      if (/placeholder="YYYY-MM-DD"/.test(h)) bad.push(name + '（有 placeholder="YYYY-MM-DD" 的文本框）');
      (h.match(/<input[^>]*>/g) || []).forEach(inp => {
        /* "看起来是日期"的输入框：带 data-f / data-k = date，或 id 形如 `xxxDate` */
        if (!/(data-f="date"|data-k="date"|id="[A-Za-z]*[Dd]ate")/.test(inp)) return;
        if (/type="date"/.test(inp)) okDate.push(name); else bad.push(name + '（日期字段缺 type="date"：' + inp.slice(0, 70) + '）');
      });
    };
    Object.keys(V).forEach(k => check(k, String(V[k]())));
    /* ⚠️ 渲染面必须含**弹窗层** —— 三个日期字段（批量付款「付款日期」/ 手动新增「单据日期」/ 集采「合同日期」）
       都在弹窗里，只扫 `V.*` 会有一条都扫不到（首版实测：改坏弹窗里的日期字段仍然全绿）。 */
    /* ⚠️ 2026-09-13 增行模式：该日期字段**不再在弹窗里** —— 它渲染在**视图**的草稿行上
       ⇒ 改扫 `V.m03()` 的**增行态**（不扫这里就成了盲区：草稿行的日期控件做坏了也全绿）。 */
    X.ACT.ntRowAdd();
    check('view:ntRowDraft', String(V.m03()));
    X.ACT.ntRowCancel();
    if (bad.length) throw new Error('这些日期字段做成了纯文本框 / 缺日期选择器：' + bad.join(' · '));
    if (okDate.length < 2) throw new Error('全站 type="date" 的日期字段只剩 ' + okDate.length + ' 处 —— 断言可能已失去区分力');
  });

  /* ===== 2026-09-13 P5 新增守护（用户授权「连带断言」）：手填项的增 / 删反馈对称 =====
     由来：P5 走查实测 —— `MOD-09` 的 `awfDel`（删除手填项）原先**只 `splice` + `render`、一句提示都没有**：
     页面上只是少了一行、合计悄悄变了，用户不知道"发生了什么、影响多少"；而**旁边的 `awfAdd` 是有提示的**
     ⇒ 同一张表里两个对称动作、反馈不对称（违反 `R9`「成功类说清做了什么 + 影响多少」）。
     取法：**行为式** —— 劫持 DOM 桩的 `body.appendChild` 抓 `toast()` 真实写入的文案（不 grep 源码字面量）。 */
  guard('R9｜特殊费用月报表手填项：删除必须给出反馈，且反馈里带「重算后的合计」', () => {
    const i = 1, L = X.awfList(), saved = L[i];
    if (!saved) throw new Error('演示数据不足 —— 断言失去区分力');
    const orig = doc.body.appendChild;
    let txt = '';
    doc.body.appendChild = el => { txt += String(el.innerHTML) + ' '; };
    const t0 = X.awfTotal(); let t1 = t0;
    try { X.ACT.awfDel({ dataset: { i: String(i) }, tagName: 'BUTTON' }); t1 = X.awfTotal(); }
    finally { doc.body.appendChild = orig; L.splice(i, 0, saved); }
    txt = txt.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
    if (t1 === t0) throw new Error('删除后合计没变 —— 断言失去区分力（删掉的项金额应大于 0）');
    if (!txt) throw new Error('删除手填项**没有任何反馈** —— R9 要求成功类说清「做了什么 + 影响多少」');
    if (txt.indexOf(X.M(t1)) < 0) throw new Error('反馈里没给出重算后的合计（应含「' + X.M(t1) + '」），实际抓到：' + txt);
    if (txt.indexOf(X.M(saved[1])) < 0) throw new Error('反馈里没说明删掉的是什么金额（应含「' + X.M(saved[1]) + '」），实际抓到：' + txt);
  });

  /* ===== 2026-09-13 用户拍板新增守护（① 死控件 ② 项目名不截断）===== */
  guard('无死控件：渲染出的 data-act 必须能解析到 ACT', () => {
    /* 盲区由来：`_smoke` 的交互路径**直接调 `ACT.*`**、不经过 `data-act` 查找 ⇒ 视图里写错一个动作名
       （如 `data-act="pjjPick"`）会变成**点了没反应的死按钮**，而现有断言全绿。本守卫补这个盲区。
       渲染面照例三处都扫：全部视图 + 应用外壳 + 弹窗层。
       ⚠️ 2026-09-26（`#2`）：原先还有后半条判词「表单类动作必须登记在 `CHG`」——
         名单整份删除之后，**"漏登记"这件事不存在了**（`change` 委托看见 `data-act` 就跑）⇒
         那句话随名单一起删；**留下的这半条强度不降**：表单元素与按钮一律按
         「`data-act` 必须解析得到 `ACT`」判，漏了就是死控件（本仓最贵的一类静默）。 */
    const acts = {}; Object.keys(X.ACT).forEach(k => acts[k] = 1);
    const bad = [];
    const scan = (name, h) => {
      const re = /<([a-zA-Z0-9]+)\b([^>]*)>/g; let m;
      while ((m = re.exec(h))) {
        const tag = m[1].toLowerCase(), attrs = m[2];
        const a = /data-act="([^"]+)"/.exec(attrs); if (!a) continue;
        if (!acts[a[1]]) bad.push(name + ' <' + tag + ' data-act="' + a[1] + '"> 没有同名动作');
      }
    };
    Object.keys(V).forEach(k => scan(k, String(V[k]())));
    X.ACT.go({ dataset: { k: 'home' } });
    ['#nav', '#ttl', '#who'].forEach(s => scan('shell' + s, String(doc.querySelector(s).innerHTML)));
    const cand = [];
    [X.NO, X.FLs, X.JCs, X.PLs, X.ADs, X.DFs, X.USERS, X.IVs].forEach(arr => { if (Array.isArray(arr)) arr.slice(0, 2).forEach(o => { if (o && o.id) cand.push(o.id); }); });
    let nModal = 0; const seen = {};
    Object.keys(X.ACT).forEach(k => {
      const ds = {}; ['id', 'fid', 'iv', 'wh', 'k', 'scope', 'pj'].forEach(key => { if (cand.length) ds[key] = cand[0]; });
      try { X.ACT[k]({ dataset: ds, tagName: 'BUTTON', value: '' }); } catch (e) { }
      const h = String(doc.querySelector('#modalRoot').innerHTML);
      if (h && !seen[h]) { seen[h] = 1; nModal++; scan('modal[:' + k + ']', h); }
      try { X.ACT.closeModal(); } catch (e) { }
    });
    /* ⭐ **先无条件回滚，再抛错**：本守卫为了查死控件会**拿假参数真调每一个动作** ——
       像 `jcBatchTag`（缺 `v`）会把 12 条集采合同的 `tag` 全写成 `undefined`，
       `delPj` / `ruleDel` / `awfDel` 等也会真改数据。
       ⚠️ 2026-09-13 实测：不回滚时脏状态会**留给后面的断言**（R10 全选那条因此假红）；
       以前没暴露只是因为后面的断言恰好不依赖这些字段 —— 属"静默污染"，必须堵掉。
       ⚠️ 顺序很重要：**回滚必须写在 throw 之前**，否则一抛错就漏掉了回滚。 */
    const _msg = (nModal < 5) ? ('只抓到 ' + nModal + ' 个弹窗 —— 断言失去区分力')
      : (bad.length ? ('死控件 / 未登记动作：' + bad.join(' · ')) : '');
    rollback(); clearPick(); X.jcPick.clear(); resetF();
    if (_msg) throw new Error(_msg);
  });
  guard('项目名一律不截断：长项目名必须完整渲染（不得截成前若干字符 + 「…」，也不得用 CSS 省略号）', () => {
    const bad = [];
    /* ① **实现标记**：整份原型文件里不得再有 `text-overflow:ellipsis`。
       ⚠️ CSS 的 ellipsis **只裁视觉**，DOM 里的文本仍是全文 ⇒ **行为式断言根本测不出来**。
       实测教训：拍板项②把 4 处内联 ellipsis 去掉了，却漏了样式表里的 `.bars .br .nm`
       —— 看板仓库条 / 「按项目看欠款」/「付款统计按项目」三个位置的**项目名仍被截断**，
       而当时的断言**全绿**。⇒ 这条只能查"是否还有截断容器"这个实现标记。 */
    if (/text-overflow\s*:\s*ellipsis/.test(html)) bad.push('原型文件里仍有 text-overflow:ellipsis（CSS 截断只裁视觉、不截 DOM，行为断言测不出）');
    /* ② 渲染侧：这几个页面是"项目名不截断"的整改对象，不得再有 ellipsis 截断容器 */
    ['m04', 'm05', 'm07', 'm12'].forEach(k => { if (/text-overflow:ellipsis/.test(String(V[k]()))) bad.push(k + '（仍有 ellipsis 截断容器）'); });
    /* ② JS 侧：把展示名 / 填报值临时改长 —— 必须**原样**出现在渲染结果里（原实现会 `slice(0,12)+'…'`） */
    const p = X.PJs.find(x => x.type !== 'shell');
    const pl = X.PLs[0];
    if (!p || !pl) throw new Error('演示数据不足 —— 断言失去区分力');
    const LONG = '超长展示名测试甲甲乙乙丙丙丁丁戊戊';
    const oldDisp = p.disp, oldProj = pl.proj;
    p.disp = LONG; pl.proj = LONG;
    try {
      const h5 = String(V.m05()), h4 = String(V.m04());
      /* ⚠️ 只查"全名在不在"会**假绿**（同一个名字在页内别处也会出现，如台账项目选择器的 `<option>`）
         ⇒ 真正的检测器是：**截断后的形态（前 12 字 + 「…」）不得出现**。 */
      const TRUNC = LONG.slice(0, 12) + '…';
      if (h5.indexOf(TRUNC) >= 0) bad.push('m05（出现截断形态「' + TRUNC + '」）');
      if (h4.indexOf(TRUNC) >= 0) bad.push('m04（出现截断形态）');
      if (h5.indexOf(LONG) < 0) bad.push('m05「按项目看欠款」（长展示名没被渲染出来）');
      if (h4.indexOf(LONG) < 0) bad.push('m04「项目」列（长填报值没被渲染出来）');
    } finally { p.disp = oldDisp; pl.proj = oldProj; }
    if (bad.length) throw new Error('这些位置仍会把项目名截断：' + bad.join(' · '));
  });

  guard('MOD-07 已验收基线的「行数 / 仓数 / 文件数」由数据实时算（不写死）', () => {
    /* 行为式：临时塞一个仓库进 WHs，渲染后那三处数字必须跟着变（写死的 675 / 8 / 9 不会变）。
       ⚠️ 只查"页面上有没有 675 行"是**假绿** —— 数据恰好也是 675 时，写死的值同样"通过"。 */
    const n0 = X.WHs.length, r0 = X.sums(X.WHs, 'rows');
    X.WHs.push({ name: '__临时仓·断言用__', rows: 3, begin: 0, in: 0, out: 0, end: 0 });
    let h; try { h = String(V.m07()); } finally { X.WHs.pop(); }
    const want = (r0 + 3) + ' 行 / ' + (n0 + 1) + ' 仓 / ' + (n0 + 2) + ' 文件';
    if (h.indexOf(want) < 0) throw new Error('「行 / 仓 / 文件」没跟着数据走（期望出现「' + want + '」）');
    if (h.indexOf((n0 + 1) + ' 个分仓库 xlsx') < 0) throw new Error('「输出产物」里的分仓库 xlsx 数没跟着数据走（期望 ' + (n0 + 1) + ' 个）');
  });

  /* ===== 2026-09-13 裁定项落地（①规则可增删改 ②调整单判据 ③差异金额带符号 ⑤MOD-08 核算年月）===== */
  guard('MOD-14 剔除规则真「增 / 删 / 改」：改动落到 RULE_EX，且卡头「N 类有效」实时算', () => {
    const bak = JSON.parse(JSON.stringify(X.RULE_EX));
    try {
      const n0 = X.RULE_EX.length;
      /* 增：走真实入口 ruleAdd → 填弹窗 → ruleSave */
      X.ACT.ruleAdd({ dataset: {}, tagName: 'BUTTON' });
      if (String(doc.querySelector('#modalRoot').innerHTML).indexOf('新增剔除规则') < 0) throw new Error('ruleAdd 没打开新增弹窗');
      doc.querySelector('#rxCat').value = '__断言用规则__';
      doc.querySelector('#rxHit').value = '甲｜乙';
      doc.querySelector('#rxWhy').value = '断言用';
      X.ACT.ruleSave({ dataset: { i: '-1' }, tagName: 'BUTTON' });
      if (X.RULE_EX.length !== n0 + 1) throw new Error('新增没落库（' + n0 + ' → ' + X.RULE_EX.length + '）');
      if (X.RULE_EX[X.RULE_EX.length - 1][0] !== '__断言用规则__') throw new Error('新增的内容没落库');
      /* 卡头「N 类有效」必须**实时算**（原来是写死的「4 类有效」）。
         ⚠️ 判据**不绑措辞**：只要求「卡头里出现当前条数」且「条数一变、卡头就变」——
         这样把「N 类有效」换成「N 类生效」之类的措辞不会假红（只有"写死数字"才会红）。 */
      const head = () => { const m = String(V.m14()).match(/剔除规则（[\s\S]{0,40}?）/); return m ? m[0] : ''; };
      const n1 = X.RULE_EX.length, t1 = head();
      if (!t1) throw new Error('抓不到剔除规则的卡头 —— 断言失去区分力');
      if (t1.indexOf(String(n1)) < 0) throw new Error('卡头里没有当前的有效条数 ' + n1 + '（抓到：' + t1 + '）');
      X.RULE_EX.push(['__临时__', 'x', 'y']); const t2 = head(); X.RULE_EX.pop();
      if (t1 === t2) throw new Error('条数变了、卡头却没变 —— 卡头里的条数是写死的');
      /* 改：走 ruleEdit → ruleSave */
      X.ACT.ruleEdit({ dataset: { i: '0' }, tagName: 'BUTTON' });
      if (String(doc.querySelector('#modalRoot').innerHTML).indexOf('编辑剔除规则') < 0) throw new Error('ruleEdit 没打开编辑弹窗');
      /* ⚠️ 两个字段都要显式写回：弹窗里的输入框会**沿用上一次的值**（此处 `#rxCat` 仍是新增时填的
         `__断言用规则__`）—— 只改一个字段会把另一个字段也带过去（本次实测踩到，断言当场报红）。 */
      doc.querySelector('#rxCat').value = '业务类型';
      doc.querySelector('#rxHit').value = '__改过的命中值__';
      X.ACT.ruleSave({ dataset: { i: '0' }, tagName: 'BUTTON' });
      if (X.RULE_EX[0][1] !== '__改过的命中值__') throw new Error('修改没落库');
      /* 删：走 ruleDel */
      X.ACT.ruleDel({ dataset: { i: String(X.RULE_EX.length - 1) }, tagName: 'BUTTON' });
      if (X.RULE_EX.length !== n0) throw new Error('删除没落库');
      if (String(V.m14()).indexOf('__断言用规则__') >= 0) throw new Error('删掉的行还在页面上');
      /* ⭐「该放过」：分类规则表**必须仍然只读**（它写的是 §4.2.3 的业务口径，可编辑=允许改口径） */
      const h = String(V.m14()), at = h.indexOf('分类规则（判定顺序）');
      if (at < 0) throw new Error('没找到分类规则卡 —— 断言失去区分力');
      if (h.slice(at, at + 2000).indexOf('data-act="ruleEdit"') >= 0) throw new Error('分类规则表不应可编辑');
    } finally {
      X.RULE_EX.length = 0; bak.forEach(v => X.RULE_EX.push(v)); X.ACT.closeModal();
    }
  });

  guard('MOD-08 调整单「调整后金额」判据 = ② ≥ 0（走 badMoney / badMoneyMsg 出口）：负值被拦且原值不变，0 合法可存', () => {
    const iv = X.IVs.find(x => !X.adjOf(x));
    if (!iv) throw new Error('演示数据不足 —— 断言失去区分力');
    const n0 = X.ADs.length, cap = [], orig = doc.body.appendChild;
    doc.body.appendChild = el => { cap.push(String(el.innerHTML)); };
    try {
      X.ACT.adjDlg({ dataset: { iv: iv.id }, tagName: 'BUTTON' });
      doc.querySelector('#adjAmt').value = '-1';
      doc.querySelector('#adjRemark').value = '断言用备注';
      X.ACT.adjOk({ dataset: { iv: iv.id }, tagName: 'BUTTON' });
      if (X.ADs.length !== n0) throw new Error('负值没被拦住（新建了调整单）');
      const msg = cap.join(' ').replace(/<[^>]*>/g, ' ');
      if (msg.indexOf('不合法') < 0 || msg.indexOf('已保留原值') < 0) throw new Error('拦截措辞没走 badMoneyMsg（应含「不合法」+「已保留原值」），实际：' + msg);
      /* ② 档 = ≥ 0 ⇒ **0 必须能存**（这是与 ③ 档的分界，也是这条断言真正有区分力的地方） */
      doc.querySelector('#adjAmt').value = '0';
      X.ACT.adjOk({ dataset: { iv: iv.id }, tagName: 'BUTTON' });
      if (X.ADs.length !== n0 + 1) throw new Error('0 被误拦（② 档应当允许 0）');
      if (X.N2(X.adjOf(iv).newAmt) !== 0) throw new Error('0 没落库');
    } finally { doc.body.appendChild = orig; X.ADs.splice(n0); X.ACT.closeModal(); }
  });

  guard('MOD-12「差异金额」带符号（+ 上调 / − 下调），且与 MOD-08 调整单的差额同源（独立复算）', () => {
    const h = String(V.m12());
    const up = X.DFs.find(d => d.amount > 0), dn = X.DFs.find(d => d.amount < 0);
    if (!up || !dn) throw new Error('演示数据里没有「上调 / 下调」两种符号 —— 断言失去区分力');
    /* ⚠️ 必须用**上调**那条来证明「有 + 号」：`M()` 会把负数照样渲染成 `-220.00`，
       所以只查负数**区分不出** `SIG()` 与 `M()`（假绿）。 */
    if (h.indexOf(X.SIG(up.amount)) < 0) throw new Error('上调的差异没带「+」号（期望出现 ' + X.SIG(up.amount) + '）');
    if (h.indexOf(X.M(dn.amount)) < 0) throw new Error('下调的差异没带「-」号（期望出现 ' + X.M(dn.amount) + '）');
    /* 独立复算：同一笔差异必须 = 「调整后 − i8 原始」（不能只信页面上的数） */
    const d1 = X.DFs.find(d => d.id === 'DF01'), iv = X.IVs.find(x => x.docNo === 'CGRK-202608-002'), ad = X.adjOf(iv);
    if (!ad) throw new Error('DF01 对应的调整单不见了 —— 用例失效');
    if (X.N2(ad.newAmt - iv.amt) !== d1.amount) throw new Error('DF01 差异金额与「调整后 − 原始」对不上：' + d1.amount + ' vs ' + X.N2(ad.newAmt - iv.amt));
  });

  guard('MOD-08「核算年月」：默认 = 北京时间上月（§9.2 材料报表类），切「全部」行数变多、重置回到默认', () => {
    if (X.ivYmState() !== X.bjMonth(-1)) throw new Error('默认核算年月不是上月：' + X.ivYmState());
    const nDef = (String(V.m08()).match(/data-act="adjDlg"/g) || []).length;
    X.ACT.mpPick({ dataset: { id: 'ivMonth', scope: 'iv', val: '全部' }, tagName: 'BUTTON' });
    const nAll = (String(V.m08()).match(/data-act="adjDlg"/g) || []).length;
    X.ACT.fIvReset({ dataset: {}, tagName: 'BUTTON' });
    if (!(nAll > nDef)) throw new Error('切「全部」后行数没变多（默认 ' + nDef + ' / 全部 ' + nAll + '）');
    if (X.ivYmState() !== X.bjMonth(-1)) throw new Error('重置没回到默认的「上月」');
  });

  guard('MOD-09「核算年月」（甲：按月各存一份、不带入；**结构 = 核算年月 → 项目 → 手填项**）：默认上月 · 切月手填项随之换 · 未录的=空+提示行 · 重置回默认', () => {
    const DZ = X.awfPjState();                       /* 默认项目（= 候选第一个 = 德州） */
    /* ① 默认 = 北京时间上月（§9.2 材料报表类） */
    if (X.awfYmState() !== X.bjMonth(-1)) throw new Error('默认核算年月不是上月：' + X.awfYmState());
    if (!DZ) throw new Error('默认项目为空 —— 用例失效');
    /* ② 切到另一个**有数据**的月 → 手填项必须换成那个月的（**不是**同一批数字） */
    const defTxt = String(V.m09());
    X.ACT.mpPick({ dataset: { id: 'awfMonth', scope: 'awf', val: '2026-06' }, tagName: 'BUTTON' });
    if (X.awfYmState() !== '2026-06') throw new Error('选月没生效');
    const j6 = String(V.m09()), l6 = (X.AWF['2026-06'] || {})[DZ];
    if (!l6 || !l6.length) throw new Error('用例失效：2026-06 · 默认项目应有手填项');
    /* 金额输入框渲染的是「该月 · 该项目那一份」的值（实现自己的 2 位小数形态，**不带千分位**） */
    if (j6.indexOf('value="' + l6[0][1].toFixed(2) + '"') < 0) throw new Error('切到 2026-06 后没渲染该月的手填金额 ' + l6[0][1].toFixed(2));
    /* 独立复算：合计 = 该月 · **该项目**的自动项 + Σ 该月 · 该项目手填项 */
    const auto6 = X.N2(X.IVs.filter(iv => iv.cbs === 'CBS-安文费' && iv.dir === '出库' && iv.wh === DZ && String(iv.dd).slice(0, 7) === '2026-06').reduce((a, iv) => a + iv.amt, 0));
    const want6 = X.M(X.N2(auto6 + l6.reduce((a, r) => a + r[1], 0)));
    const tr6 = /合计<\/td>\s*<td><\/td>\s*<td class="num">([\d.,\-]+)<\/td>/.exec(_tblByKey(j6, 'm09:awf'));
    if (!tr6) throw new Error('没抓到 2026-06 的合计行 —— 断言失去区分力');
    if (tr6[1] !== want6) throw new Error('2026-06 合计对不上（' + tr6[1] + ' / 期望 ' + want6 + '）');
    if (j6 === defTxt) throw new Error('切月前后页面完全一样 —— 手填项没按月分家');
    /* ③ 未录的（月 · 项目）→ 手填区为空 + 提示行；合计 = **只有自动项** */
    X.ACT.mpPick({ dataset: { id: 'awfMonth', scope: 'awf', val: '2026-05' }, tagName: 'BUTTON' });
    const j5 = String(V.m09()), tb = _tblByKey(j5, 'm09:awf');
    if (((X.AWF['2026-05'] || {})[DZ] || []).length !== 0) throw new Error('用例失效：2026-05 · 默认项目不该有手填项');
    const col = /colspan="(\d+)"[^>]*>([\s\S]*?)<\/td>/.exec(tb), thN = (tb.match(/<th\b/g) || []).length;
    if (!col) throw new Error('未录的那一份没有提示行（R10①）');
    if (Number(col[1]) !== thN) throw new Error('提示行跨列数 ≠ 表头列数（应派生自 AWF_THEAD）');
    /* ⚠️ 只验"提示行不是空白"，**不绑措辞**（绑了以后改一句话就假红） */
    if (!col[2].replace(/<[^>]*>/g, '').trim()) throw new Error('未录的那一份的提示行是空白的');
    /* 独立复算：合计 = 该月 · 该项目自动项（`CBS-安文费` 出库 · 按仓库名 + 单据日期）——不复用原型同名函数 */
    const auto5 = X.N2(X.IVs.filter(iv => iv.cbs === 'CBS-安文费' && iv.dir === '出库' && iv.wh === DZ && String(iv.dd).slice(0, 7) === '2026-05').reduce((a, iv) => a + iv.amt, 0));
    const totRow = /合计<\/td>\s*<td><\/td>\s*<td class="num">([\d.,\-]+)<\/td>/.exec(tb);
    if (!totRow) throw new Error('没抓到合计行 —— 断言失去区分力');
    if (totRow[1] !== X.M(auto5)) throw new Error('合计不等于该月该项目的自动项（合计 ' + totRow[1] + ' / 期望 ' + X.M(auto5) + '）');
    /* ④ 重置 → 回到默认上月 ＋ 默认项目 */
    X.ACT.awfReset({ dataset: {}, tagName: 'BUTTON' });
    if (X.awfYmState() !== X.bjMonth(-1)) throw new Error('重置没回到默认的上月');
    if (X.awfPjState() !== DZ) throw new Error('重置没回到默认项目');
    /* ⑤ **写路径必须按「月 ＋ 项目」**：在一份"未录"的 (月, 项目) 上增 / 改 / 删 → 只落那一份 */
    X.ACT.mpPick({ dataset: { id: 'awfMonth', scope: 'awf', val: '2026-05' }, tagName: 'BUTTON' });
    const n8 = ((X.AWF['2026-08'] || {})[DZ] || []).length;
    try {
      X.ACT.awfAdd({ dataset: {}, tagName: 'BUTTON' });
      if (((X.AWF['2026-05'] || {})[DZ] || []).length !== 1) throw new Error('在未录的那一份上增加手填项没落在它上面（写路径没按「月 ＋ 项目」）');
      X.ACT.awfName({ dataset: { i: '0' }, value: '__断言用项名__', tagName: 'INPUT' });
      X.ACT.awfAmt({ dataset: { i: '0' }, value: '123.45', tagName: 'INPUT' });
      const r5 = X.AWF['2026-05'][DZ][0];
      if (r5[0] !== '__断言用项名__' || X.N2(r5[1]) !== 123.45) throw new Error('改名 / 改金额没落在该份上');
      if (((X.AWF['2026-08'] || {})[DZ] || []).length !== n8) throw new Error('不该动到别的月（2026-08 行数变了）');
      X.ACT.awfDel({ dataset: { i: '0' }, tagName: 'BUTTON' });
      if (((X.AWF['2026-05'] || {})[DZ] || []).length !== 0) throw new Error('删除没落在该份上');
      /* ⑤b ⭐ **再换一个「非默认项目」写一次** —— 只在默认项目上写，测不出"写路径把项目写死"
         （2026-09-13 反向灵敏度实测：把 `awfMut` 固定成"永远写候选第一个"，只跑 ⑤ 时**照样全绿**）。 */
      const LY2 = '临沂钢铁余热发电项目仓库';
      if (DZ === LY2) throw new Error('用例失效：默认项目不该已经是临沂');
      X.ACT.awfPjPick({ dataset: { pj: LY2 }, tagName: 'INPUT' });
      X.ACT.awfAdd({ dataset: {}, tagName: 'BUTTON' });
      if ((((X.AWF['2026-05'] || {})[LY2]) || []).length !== 1) throw new Error('在**非默认项目**上增加手填项没落在它那一份（写路径把项目写死了）');
      if ((((X.AWF['2026-05'] || {})[DZ]) || []).length !== 0) throw new Error('写到了别的项目上（默认项目那一份被污染）');
      X.ACT.awfDel({ dataset: { i: '0' }, tagName: 'BUTTON' });
      if ((((X.AWF['2026-05'] || {})[LY2]) || []).length !== 0) throw new Error('删除没落在非默认项目那一份上');
    } finally { delete X.AWF['2026-05']; X.ACT.awfReset({ dataset: {}, tagName: 'BUTTON' }); }
  });
  guard('N25｜MOD-09「项目」**单选**筛选：自动项与手填项都只算该项目 —— 切项目后合计 = 独立复算 · 空态按份出现 · 无安文费的项目合计为 0', () => {
    X.ACT.awfReset({ dataset: {}, tagName: 'BUTTON' });
    const DZ = X.awfPjState(), LY = '临沂钢铁余热发电项目仓库', CZ = '山西长治焦化升级改造项目仓库';
    const autoOf = (wh, ym) => X.N2(X.IVs.filter(iv => iv.cbs === 'CBS-安文费' && iv.dir === '出库' && iv.wh === wh && String(iv.dd).slice(0, 7) === ym).reduce((a, iv) => a + iv.amt, 0));
    const totalOf = h => { const m = /合计<\/td>\s*<td><\/td>\s*<td class="num">([\d.,\-]+)<\/td>/.exec(_tblByKey(h, 'm09:awf')); return m ? m[1] : null; };
    /* ① 面板 = **单选**（radio · 不给「全选 / 清空」）且候选 = `ntPjList()`（档案表全部、排壳） */
    X.ACT.awfPjToggle({ dataset: {}, tagName: 'BUTTON' });
    const hp = String(V.m09());
    const single = hp.indexOf('name="projPanelSingle"') >= 0;
    const noAll = hp.indexOf('data-act="awfPjAll"') < 0 && hp.indexOf('data-act="awfPjNone"') < 0;
    const nPick = (hp.match(/data-act="awfPjPick"/g) || []).length, nCand = X.ntPjList().length;
    X.ACT.awfPjToggle({ dataset: {}, tagName: 'BUTTON' });
    if (!(single && noAll)) throw new Error('「项目」面板不是单选（radio ' + single + ' · 无全选/清空 ' + noAll + '）');
    if (nPick !== nCand || nCand < 5) throw new Error('候选数 ' + nPick + ' ≠ ntPjList() ' + nCand + '（或样本太少）');
    /* ② 切到另一个**有自动项**的项目 → 自动项 / 合计都跟着换，且 = 独立复算 */
    const aD = autoOf(DZ, '2026-08'), aL = autoOf(LY, '2026-08');
    if (!(aD > 0 && aL > 0 && aD !== aL)) throw new Error('样本失效：德州 / 临沂 在 2026-08 都该有安文费出库且不相等（' + aD + ' / ' + aL + '）');
    const t0 = totalOf(String(V.m09()));
    X.ACT.awfPjPick({ dataset: { pj: LY }, tagName: 'INPUT' });
    if (X.awfPjState() !== LY) throw new Error('切项目没生效');
    const h1 = String(V.m09()), t1 = totalOf(h1);
    const expL = X.M(X.N2(aL + (((X.AWF['2026-08'] || {})[LY]) || []).reduce((a, r) => a + r[1], 0)));
    if (t1 !== expL) throw new Error('切到临沂后合计 ' + t1 + ' ≠ 独立复算 ' + expL);
    if (h1.indexOf('还没有手填项') < 0) throw new Error('临沂 · 2026-08 没有手填项 → 应出现空态提示行');
    if (t1 === t0) throw new Error('切项目前后合计一样 —— 断言失去区分力');
    /* ③ 切到一个**没有安文费**的项目 → 自动项与合计都为 0 */
    X.ACT.awfPjPick({ dataset: { pj: CZ }, tagName: 'INPUT' });
    const t2 = totalOf(String(V.m09()));
    if (t2 !== X.M(0)) throw new Error('无安文费的项目：合计应为 ' + X.M(0) + '，实得 ' + t2);
    /* ④ 复位（本页自己的重置动作 = 回到默认月 + 默认项目） */
    X.ACT.awfReset({ dataset: {}, tagName: 'BUTTON' });
    if (X.awfPjState() !== DZ) throw new Error('重置没回到默认项目');
  });

  /* ===== 2026-09-13 第四批：既有 10 处合计行迁到统一出口 `sumRowOf` =====
     迁移**等价性**的判据 = 「合计行 = 各数据行之和」（**逐列独立复算**，不看实现怎么写的）；
     另外把「置底」这个**新的视觉约定**也钉住（否则以后被静默拿掉没人知道）。 */
  guard('N26｜10 处既有合计行已迁到 `sumRowOf`：列数（含 colspan 展开）= 表头列数，且**逐列 = 各数据行之和**', () => {
    const TXT = s => String(s).replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
    const TBL = (h, key) => (String(h).match(new RegExp('<table\\b[^>]*data-sort-key="' + key + '"[\\s\\S]*?</table>')) || [''])[0];
    const TRS = t => ((t.match(/<tbody\b[^>]*>([\s\S]*?)<\/tbody>/) || ['', ''])[1].match(/<tr\b[\s\S]*?<\/tr>/g) || []);
    const RAW = r => (r.match(/<td\b[\s\S]*?<\/td>/g) || []);
    /* ⚠️ 取值规则**必须与实现同源**：单元格可能是 `<input>`（手填列）⇒ 优先读它的 `value`，
       只读文本会把**正确实现判成错的**（2026-09-13 实测：大表「机械费测算」列全判成 0）。 */
    const valOf = td => { const iv = String(td).match(/<input\b[^>]*\bvalue="([^"]*)"/i); return iv ? iv[1] : TXT(td); };
    const VAL = (r, i) => valOf(RAW(r)[i]);
    const NTH = t => { const h0 = ((t.match(/<thead\b[^>]*>([\s\S]*?)<\/thead>/i) || ['', ''])[1].match(/<tr\b[^>]*>[\s\S]*?<\/tr>/i) || [''])[0];
      return (h0.match(/<th\b[^>]*>[\s\S]*?<\/th>/gi) || []).reduce((a, th) => a + (+((th.match(/colspan="(\d+)"/) || [0, 1])[1])), 0); };
    /* 合并行展开成"按列"的数组：`colspan` 的首格值占第 0 列，其余补空 ⇒ 下标 = 表头列号 */
    const EXPAND = tr => { const out = [];
      RAW(tr).forEach(td => {
        const sp = +((td.match(/colspan="(\d+)"/) || [0, 1])[1]);
        for (let k = 0; k < sp; k++) out.push(k === 0 ? valOf(td) : '');
      }); return out; };
    const num = x => { const v = Number(String(x).replace(/[,\s]/g, '')); return isFinite(v) ? v : NaN; };
    /* 「合计行」的判据 = **首格含「合计」** —— ⚠️ 不能写 `/^合计/`：分组表的标签是「焊材合计」（**不以「合计」开头**）。 */
    const isSum = r => /合计/.test(valOf(RAW(r)[0]));
    /* ⚠️ **自备干净基线**：这几张表的行数取决于**筛选状态**（前面的交互路径会留下别的月份）
       ⇒ 不重置就可能"表是空的 ⇒ 没有合计行"而**误报**（2026-09-13 实测踩到）。 */
    X.ACT.flReset({ dataset: {}, tagName: 'BUTTON' });
    X.ACT.whReset({ dataset: {}, tagName: 'BUTTON' });
    X.ACT.fExtReset({ dataset: {}, tagName: 'BUTTON' });
    const verify = (name, h, key, cols) => {
      const t = TBL(h, key); if (!t) throw new Error(name + '：找不到表');
      const trs = TRS(t), sr = trs.filter(isSum), data = trs.filter(r => !isSum(r));
      if (!sr.length) throw new Error(name + '：没有合计行');
      if (data.length < 1) throw new Error(name + '：没有数据行 —— 失去区分力');
      const c = EXPAND(sr[0]), n = NTH(t);
      if (c.length !== n) throw new Error(name + '：合计行展开后 ' + c.length + ' 列 ≠ 表头 ' + n + ' 列');
      cols.forEach(i => { const exp = data.reduce((a, r) => a + (num(VAL(r, i)) || 0), 0), got = num(c[i]);
        if (!(Math.abs(got - exp) < 0.005)) throw new Error(name + '：第 ' + i + ' 列合计 ' + got + ' ≠ 各数据行之和 ' + exp); });
      return { c, data, n };
    };
    /* ① MOD-05 逐月欠款台账（辅材 / 机械）—— 3 个金额列 */
    ['辅材', '机械'].forEach(sc => verify('MOD-05 ' + sc + ' 台账', V.m05(), 'm05:ledger-' + sc, [2, 3, 4]));
    /* ② MOD-05 付款流水 —— 合计**只算生效流水**（已撤销不计入）⇒ 走数据独立复算，不靠渲染过滤 */
    {
      const r = verify('MOD-05 付款流水', V.m05(), 'm05:flows', []);
      const exp = X.N2(X.flVisible().filter(f => !f.voided).reduce((a, f) => a + f.amt, 0));
      if (!(Math.abs(num(r.c[4]) - exp) < 0.005)) throw new Error('MOD-05 付款流水：付款金额合计 ' + num(r.c[4]) + ' ≠ 生效流水之和 ' + exp);
    }
    /* ③ MOD-07 收发结存（行数列是**纯整数**、末列是 tag ⇒ 只核前 6 列） */
    verify('MOD-07 收发结存', V.m07(), 'm07:warehouses', [1, 2, 3, 4, 5]);
    /* ④ MOD-07 活动大表（20 列、前两列合并放标签） */
    verify('MOD-07 活动大表', V.m07(), 'm07:bigtable', [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 15, 16, 17, 18]);
    /* ⑤ MOD-07 焊材 / 气体提取：**两张分组合计**，各自 = **本组**数据行之和（按行序切块，不绑文案） */
    {
      const trs = TRS(TBL(V.m07(), 'm07:kinds'));
      const cut = trs.map((r, i) => (isSum(r) ? i : -1)).filter(i => i >= 0);
      if (cut.length !== 2) throw new Error('提取表应有 2 张分组合计（实得 ' + cut.length + '）');
      [[0, cut[0], cut[0]], [cut[0] + 1, cut[1], cut[1]]].forEach((seg, k) => {
        const seg2 = trs.slice(seg[0], seg[1]), c2 = trs[seg[2]];
        /* ⚠️ 可求和的列 = 总金额 / 金额 两列：2026-09-18「结余」列插在「仓库」之后 ⇒ 下标 [3][4]
           （⭐ 结余列**不参与合计** —— 与成品模板一致：模板的合计行该格就是空的）。 */
        [3, 4].forEach(i => { const exp = seg2.reduce((a, r) => a + (num(VAL(r, i)) || 0), 0), got = num(VAL(c2, i));
          if (!(Math.abs(got - exp) < 0.005)) throw new Error('提取表第 ' + (k + 1) + ' 组第 ' + i + ' 列合计 ' + got + ' ≠ 本组之和 ' + exp); });
      });
    }
    /* ⑥ 弹窗 · 集采三张子表：合计 = Σ 该子表自身的数据行 */
    X.ACT.jcInvDlg({ dataset: { id: 'J01' }, tagName: 'BUTTON' }); verify('集采·供应商发票子表', _modalHtml(), 'modal:jcInv', [1]);
    X.ACT.jcTInvDlg({ dataset: { id: 'J03' }, tagName: 'BUTTON' }); verify('集采·贸易公司发票子表', _modalHtml(), 'modal:jcTInv', [1]);
    X.ACT.jcPayDlg({ dataset: { id: 'J01' }, tagName: 'BUTTON' }); verify('集采·付款子表', _modalHtml(), 'modal:jcPay', [1]);
    X.ACT.closeModal({ dataset: {}, tagName: 'BUTTON' });
    /* ⑦ 弹窗 · 提取导出矩阵（列数随月份动态 ⇒ 逐列核到最后一列） */
    X.ACT.expExt();
    {
      const h = _modalHtml();
      ['焊材', '气体'].forEach(kind => {
        const r = verify('提取矩阵·' + kind, h, 'modal:expExt-' + kind, []);
        for (let i = 1; i < r.c.length; i++) {
          const exp = r.data.reduce((a, x) => a + (num(VAL(x, i)) || 0), 0);
          if (!(Math.abs(num(r.c[i]) - exp) < 0.005)) throw new Error('提取矩阵·' + kind + '：第 ' + i + ' 列 ' + num(r.c[i]) + ' ≠ 各数据行之和 ' + exp);
        }
      });
    }
    X.ACT.closeModal({ dataset: {}, tagName: 'BUTTON' });
  });
  guard('N27｜「合计」行**统一置底**：带 `sumrow` 类 + 样式表有对应规则（⭐ `position:sticky` 必须落在 **`<tr>`** 上 + 不透明底色）；⭐ **分组表**必须**不置底**', () => {
    const css = html.slice(html.indexOf('<style>'), html.indexOf('</style>'));
    /* ⭐⭐ 2026-09-16 修正 —— 本断言原先「要求 sticky 写在 `>td` 里」，**把坏写法钉成了契约**：
       而 `position:sticky` 作用在 `<td>` 上时**包含块是表格行**（行高 = 单元格高）⇒ **没有位移空间** ⇒
       该规则**从未生效过**（合计行照旧在屏幕外、且不报错）—— 断言全绿，效果为零。
       实测判据 = 「合计行底 − 容器底」：`td` 写法 **+792.5px** vs `tr` 写法 **−1px**。
       ⇒ 修法：断言**分散到各自该在的那条规则**上 —— 位移看 `<tr>`、底色看 `>td`，并**明令禁止** sticky 回到 `>td`。 */
    const rowRule = (css.match(/\.dt tbody tr\.sumrow\{[^}]*\}/) || [''])[0];
    if (!rowRule) throw new Error('样式表里没有 `.dt tbody tr.sumrow{…}` 规则 —— ⚠️ `position:sticky` 写在 `>td` 上**永不生效**（只有行 / 行组才有位移空间）');
    if (!/position\s*:\s*sticky/.test(rowRule)) throw new Error('置底规则缺 `position:sticky`');
    if (!/bottom\s*:\s*0/.test(rowRule)) throw new Error('置底规则缺 `bottom:0`（贴不到底）');
    const cellRule = (css.match(/\.dt tbody tr\.sumrow>td\{[^}]*\}/) || [''])[0];
    if (!cellRule) throw new Error('样式表里没有 `.dt tbody tr.sumrow>td{…}` 规则（底色与补边线都在这条上）');
    if (!/background\s*:/.test(cellRule)) throw new Error('置底缺不透明底色 —— 数据行会从合计行下面透出来');
    if (/position\s*:\s*sticky/.test(cellRule)) throw new Error('`position:sticky` 写在了 `>td` 上 —— 该写法**永不生效**，必须挪到 `<tr>`');
    const sumRowsOf = (h, key) => { const t = (String(h).match(new RegExp('<table\\b[^>]*data-sort-key="' + key + '"[\\s\\S]*?</table>')) || [''])[0];
      const b = (t.match(/<tbody\b[^>]*>([\s\S]*?)<\/tbody>/) || ['', ''])[1];
      return (b.match(/<tr\b[\s\S]*?<\/tr>/g) || []).filter(r => r.indexOf('class="sumrow"') >= 0); };
    /* ⚠️ **自备干净基线**（同上）：逐页走各自的「重置」动作，保证每张表都有数据行 ⇒ 才谈得上"有没有合计行" */
    X.fNt.month = X.bjMonth();
    X.ACT.filterReset({ dataset: {}, tagName: 'BUTTON' });
    X.ACT.plFilterReset({ dataset: {}, tagName: 'BUTTON' });
    X.ACT.whReset({ dataset: {}, tagName: 'BUTTON' });
    X.ACT.fIvReset({ dataset: {}, tagName: 'BUTTON' });
    X.ACT.awfReset({ dataset: {}, tagName: 'BUTTON' });
    X.ACT.jcReset({ dataset: {}, tagName: 'BUTTON' });
    /* 带合计行、且**应当**置底的页面 / 弹窗（`MOD-06` 两行只加类、未迁实现，也算在内） */
    const need = [['m03', 'm03:notices'], ['m04', 'm04:plans'], ['m07', 'm07:warehouses'], ['m07', 'm07:bigtable'],
      ['m08', 'm08:invoices'], ['m09', 'm09:awf'], ['m11', 'm11:jc'], ['m12', 'm12:diffs']];
    need.forEach(([v, k]) => { if (!sumRowsOf(V[v](), k).length) throw new Error(k + '：合计行没有置底标记（`sumrow`）'); });    /* MOD-06 表①② 的「合计」行（不是「总求和」行）也要置底 */
    { const k = 'm06:awf';
      const t = (String(V.m06()).match(/<table\b[\s\S]*?<\/table>/) || [''])[0];
      if (!/class="sumrow"/.test(t)) throw new Error('MOD-06 表①② 的合计行没有置底标记'); }
    /* ⭐ 该放过的：**分组表**（焊材 / 气体提取）的分组合计要**紧贴本组** ⇒ 必须**不**置底（两行同 sticky 会重叠） */
    if (sumRowsOf(V.m07(), 'm07:kinds').length) throw new Error('分组表（MOD-07 焊材/气体提取）**不该**置底 —— 分组合计要紧贴本组');
  });

  /* ===== 2026-09-13 P6 新增守护（用户授权「连带断言」）：MOD-11 集采台账的两处 R10 盲区 =====
     由来：P6 走查实测 —— ① MOD-11 是**唯一"有筛选栏、却没有空态提示行"的列表页**：
     「供应商」模糊搜索打个匹配不到的词 ⇒ `tbody` 直接**空白**（违反 `R10`①「列表为空给提示行」）；
     ② 它的表头「全选」框**一直没有 `BIND`** ⇒ **永远不反射状态**（全勾满了还是个空框、部分勾选也不显半选），
     而 `R10`② 明确要求"全选支持全选 / 半选（indeterminate）状态回显"（MOD-03 / MOD-04 都有 BIND，只有它漏了）。 */
  guard('R10｜MOD-11 集采台账：筛选无结果 → 必须有空态提示行，且跨列数 = 表头列数（独立数 <th>）', () => {
    /* 空场景**从真实动作进**（改筛选控件 → `jcFilter`），不直接改内部对象 */
    doc.querySelector('#fTag').value = '全部';
    doc.querySelector('#fArch').value = '全部';
    doc.querySelector('#fSup').value = '__断言用·匹配不到的供应商__';
    let h;
    try { X.ACT.jcFilter({ dataset: {}, tagName: 'SELECT' }); h = String(V.m11()); }
    finally { doc.querySelector('#fSup').value = ''; X.ACT.jcReset(); }
    const tb = _tblByKey(h, 'm11:jc');
    if (!tb) throw new Error('没圈定到 m11:jc 这张表 —— 断言失去区分力');
    const thN = (tb.match(/<th\b/g) || []).length, trN = (tb.match(/<tr\b/g) || []).length;
    if (trN !== 2) throw new Error('空场景没造出来（应只有「表头 + 空态」两行，实测 ' + trN + ' 行）');
    const col = /colspan="(\d+)"[^>]*>([\s\S]*?)<\/td>/.exec(tb);
    if (!col) throw new Error('空态行没有 colspan / 没有那一格');
    /* ⚠️ 跨列数**独立数表头 `<th>`** 得出 —— 不能借 `thCount(JC_THEAD)` 自证（写死同一个数字也会绿） */
    if (Number(col[1]) !== thN) throw new Error('空态行跨列数 ' + col[1] + ' ≠ 表头列数 ' + thN + '（应派生自表头常量）');
    /* ⚠️ 只验"提示行不是空白"，**不绑文案措辞** —— 绑了措辞以后改一句话就会假红（R10 只要求"给提示行、不是空白"） */
    if (!col[2].replace(/<[^>]*>/g, '').trim()) throw new Error('空态行是空白的（R10① 要求给提示行，不是空白）');
  });

  guard('R10｜MOD-11 表头「全选」框必须回显状态（全选 → 勾选；取消一行 → 半选）', () => {
    rollback(); X.jcPick.clear();                 /* ⭐ 自备干净基线（与同组其他守卫一致，不依赖前一条的状态） */
    doc.querySelector('#fTag').value = '纳入台账';
    X.ACT.jcFilter({ dataset: {}, tagName: 'SELECT' });   /* 三态固定成已知值（走真实控件），否则"可见几行"取决于前面跑过谁 */
    const box = doc.querySelector('#jcAllBox');
    const diag = () => `[诊断] 三态=${X.fJc.tag} 存档=${X.fJc.arch} 供应商="${X.fJc.sup}" 项目筛选=${X.fJc.projs.length} 可见=${X.jcVisible().length} 勾选=${X.jcPick.size} 合同=${X.JCs.length} 三态分布=` + JSON.stringify(X.JCs.reduce((m, j) => { const k = String(j.tag); m[k] = (m[k] || 0) + 1; return m; }, {}));
    try {
      X.jcPick.clear();
      X.ACT.jcPickAll({ dataset: {}, tagName: 'INPUT' });        /* 空勾选 + 全选 = 把可见行全勾上 */
      X.BIND.m11();
      if (box.checked !== true) throw new Error('全选后表头勾选框没有回显为「已勾选」（checked=' + box.checked + '）' + diag());
      if (box.indeterminate !== false) throw new Error('全选后不应处于半选态' + diag());
      const one = X.jcVisible()[0];
      if (!one) throw new Error('演示数据不足 —— 断言失去区分力' + diag());
      X.jcPick.delete(one.id); X.BIND.m11();
      if (!(box.checked === false && box.indeterminate === true)) throw new Error('取消一行后应显「半选」（indeterminate）' + diag());
    } finally {
      X.jcPick.clear(); X.BIND.m11();                            /* 复原到基线（空勾选）—— 出错也要复位 */
    }
  });

  guard('抓取入口：API-01 / API-02 / API-03 都打开「按月抓取」弹窗（**三个入口行为一致**）；无抓取交互的接口仍是模拟提示', () => {
    const root = () => String(doc.querySelector('#modalRoot').innerHTML);
    const open = (t, api) => { X.ACT.fetchOne({ dataset: { t, api }, tagName: 'BUTTON' }); const h = root(); X.ACT.closeModal(); return h; };
    /* 正向：三个真入口都要打开「按月抓取」弹窗（2026-09-13 用户口径：后两个也按月抓） */
    if (open('付款通知书', 'API-01').indexOf('抓取 i8 付款通知书') < 0) throw new Error('API-01 没有打开「按月抓取」弹窗');
    if (open('收发结存表', 'API-02').indexOf('抓取 i8 收发结存表') < 0) throw new Error('API-02 没有打开「按月抓取」弹窗');
    if (open('库存单据明细表', 'API-03').indexOf('抓取 i8 库存单据明细表') < 0) throw new Error('API-03 没有打开「按月抓取」弹窗');
    /* ⭐「该放过」：没有对应抓取交互的接口（如 API-05 纯 HTTP）⇒ **不得**开弹窗（保持模拟提示） */
    if (open('仓库列表 GetWareHouseList', 'API-05') !== '') throw new Error('无抓取交互的接口不应开弹窗（该放过用例被误伤）');
    X.setFetch({ kind: 'nt', m: X.bjMonth() });
  });

  guard('收发结存表 / 库存单据明细表抓取：弹窗**默认月份 = 本页「核算年月」当前所选**（可改）', () => {
    /* 先把两页的核算年月改成**非默认**的月份 —— 否则"取本页所选"与"取默认值"行为相同，判据没有区分力 */
    X.ACT.mpPick({ dataset: { id: 'whMonth', scope: 'wh', val: '2026-06' }, tagName: 'BUTTON' });
    X.ACT.mpPick({ dataset: { id: 'ivMonth', scope: 'iv', val: '2026-07' }, tagName: 'BUTTON' });
    const sel = { wh: X.whYmState(), iv: X.ivYmState() };
    if (sel.wh !== '2026-06') throw new Error('收发结存核算年月没切成功：' + sel.wh);
    if (sel.iv !== '2026-07') throw new Error('库存单据核算年月没切成功：' + sel.iv);
    const root = () => String(doc.querySelector('#modalRoot').innerHTML);
    X.ACT.fetchOne({ dataset: { t: '收发结存表', api: 'API-02' }, tagName: 'BUTTON' });
    const hw = root(); X.ACT.closeModal();
    if (hw.indexOf('单据日期 ' + sel.wh + '-01 ~ ' + X.monthEnd(sel.wh)) < 0) throw new Error('收发结存抓取弹窗默认月份 ≠ 本页所选（' + sel.wh + '）');
    X.ACT.fetchOne({ dataset: { t: '库存单据明细表', api: 'API-03' }, tagName: 'BUTTON' });
    const hi = root(); X.ACT.closeModal();
    if (hi.indexOf('单据日期 ' + sel.iv + '-01 ~ ' + X.monthEnd(sel.iv)) < 0) throw new Error('库存单据抓取弹窗默认月份 ≠ 本页所选（' + sel.iv + '）');
    X.setFetch({ kind: 'nt', m: X.bjMonth() });
  });

  /* ⭐⭐ 2026-09-13：集采三张子表（供应商发票 / 贸易公司发票 / 付款）录入改「**表内增行**」+
     发票**必填日期** + 发票金额**不设上限**（用户口径）。以下 7 条钉住这套契约。 */
  guard('集采发票子表：表头有「发票日期」列，且数据行真的渲染出日期（供应商 / 贸易公司两侧共用表头）', () => {
    if (String(X.JCINV_THEAD).indexOf('发票日期') < 0) throw new Error('JCINV_THEAD 缺「发票日期」列');
    ['jcInvDlg', 'jcTInvDlg'].forEach(a => {
      X.ACT[a]({ dataset: { id: 'J03' }, tagName: 'BUTTON' });
      const h = String(doc.querySelector('#modalRoot').innerHTML);
      X.ACT.closeModal();
      if (!/20\d\d-\d\d-\d\d/.test(h)) throw new Error(a + '：子表未渲染日期');
    });
  });

  guard('集采子表：**日期必填** —— 只填金额不填日期，点保存不得落库（发票 / 付款同款）', () => {
    const j = X.JCs.find(x => x.id === 'J03');
    const n0 = j.invoices.length, p0 = j.payments.length;
    X.ACT.jcSubAdd({ dataset: { id: 'J03', kind: 'inv' }, tagName: 'BUTTON' });
    X.ACT.jcSubSet({ dataset: { k: 'amt' }, value: '500', tagName: 'INPUT' });
    X.ACT.jcSubSave({ dataset: {}, tagName: 'BUTTON' });
    if (j.invoices.length !== n0) throw new Error('日期未填却落了库（发票）');
    X.ACT.jcSubAdd({ dataset: { id: 'J03', kind: 'pay' }, tagName: 'BUTTON' });
    X.ACT.jcSubSet({ dataset: { k: 'date' }, value: '', tagName: 'INPUT' });   /* 付款默认 SYS_TODAY ⇒ 故意清空 */
    X.ACT.jcSubSet({ dataset: { k: 'amt' }, value: '500', tagName: 'INPUT' });
    X.ACT.jcSubSave({ dataset: {}, tagName: 'BUTTON' });
    if (j.payments.length !== p0) throw new Error('日期未填却落了库（付款）');
    X.setJcSub({ kind: '', id: '', d: { date: '', amt: '' } });
  });

  guard('集采发票金额：**不设上限**（可超合同金额；只走「必须 > 0」这一个出口）', () => {
    const j = X.JCs.find(x => x.id === 'J03');
    const n0 = j.invoices.length, s0 = X.jcInvSum(j);
    const over = X.N2(j.contractAmt + 12345.67);      /* 故意超过合同金额 —— 若有上限会被拦 */
    X.ACT.jcSubAdd({ dataset: { id: 'J03', kind: 'inv' }, tagName: 'BUTTON' });
    X.ACT.jcSubSet({ dataset: { k: 'date' }, value: '2026-09-13', tagName: 'INPUT' });
    X.ACT.jcSubSet({ dataset: { k: 'amt' }, value: String(over), tagName: 'INPUT' });
    X.ACT.jcSubSave({ dataset: {}, tagName: 'BUTTON' });
    if (j.invoices.length !== n0 + 1) throw new Error('超合同金额被拦 —— 发票金额本不该有上限');
    if (X.jcInvSum(j) !== X.N2(s0 + over)) throw new Error('发票合计未随子表更新');
    j.invoices.pop();
    X.setJcSub({ kind: '', id: '', d: { date: '', amt: '' } });
  });

  guard('集采子表：取消 = 草稿行丢弃、**不入库**，且增行态复位', () => {
    const j = X.JCs.find(x => x.id === 'J03'), n0 = j.invoices.length;
    X.ACT.jcSubAdd({ dataset: { id: 'J03', kind: 'inv' }, tagName: 'BUTTON' });
    X.ACT.jcSubSet({ dataset: { k: 'date' }, value: '2026-09-13', tagName: 'INPUT' });
    X.ACT.jcSubSet({ dataset: { k: 'amt' }, value: '500', tagName: 'INPUT' });
    X.ACT.jcSubCancel({ dataset: {}, tagName: 'BUTTON' });
    if (j.invoices.length !== n0) throw new Error('取消后仍入库了');
    if (X.jcSubState().kind) throw new Error('取消后增行态未复位');
  });

  guard('集采付款子表：录入日期**默认取 SYS_TODAY**（原先写死的日期字面量已删除），且草稿可改', () => {
    X.ACT.jcSubAdd({ dataset: { id: 'J04', kind: 'pay' }, tagName: 'BUTTON' });
    const d = X.jcSubState().d.date;
    if (d !== X.SYS_TODAY) throw new Error('默认日期不是 SYS_TODAY，而是 ' + d);
    X.ACT.jcSubSet({ dataset: { k: 'date' }, value: '2026-08-01', tagName: 'INPUT' });
    if (X.jcSubState().d.date !== '2026-08-01') throw new Error('草稿日期写不进');
    X.setJcSub({ kind: '', id: '', d: { date: '', amt: '' } });
  });

  guard('集采子表：草稿行**列对齐（<td> 数 = 表头列数）+ 钉在「数据行之后、合计行之前」**', () => {
    X.ACT.jcInvDlg({ dataset: { id: 'J03' }, tagName: 'BUTTON' });
    X.ACT.jcSubAdd({ dataset: { id: 'J03', kind: 'inv' }, tagName: 'BUTTON' });
    const h = String(doc.querySelector('#modalRoot').innerHTML);
    X.ACT.closeModal();
    const tbl = (h.match(/<table\b[^>]*data-sort-key="modal:jcInv"[\s\S]*?<\/table>/) || [''])[0];
    const draft = (tbl.match(/<tr class="draftrow">[\s\S]*?<\/tr>/) || [''])[0];
    if (!draft) throw new Error('草稿行未渲染 / 未带 draftrow 类');
    const nTh = ((tbl.match(/<thead\b[\s\S]*?<\/thead>/i) || [''])[0].match(/<th\b/g) || []).length;
    const nTd = (draft.match(/<td\b/g) || []).length;
    if (nTd !== nTh) throw new Error('草稿行列数 ' + nTd + ' ≠ 表头列数 ' + nTh);
    const iDraft = tbl.indexOf('draftrow'), iSum = tbl.search(/合计/);
    if (iDraft < 0 || iSum < 0 || iDraft > iSum) throw new Error('草稿行未落在「数据行之后、合计行之前」');
    X.setJcSub({ kind: '', id: '', d: { date: '', amt: '' } });
  });

  guard('集采子表录入：旧动作（jcInvAdd / jcTInvAdd / jcPayAdd）已删除，且原型里不再有 prompt() 录入', () => {
    ['jcInvAdd', 'jcTInvAdd', 'jcPayAdd'].forEach(a => {
      /* ⚠️ 2026-09-26（`#2`）：半句「仍登记在 `CHG` 里」随名单一起删（没有主人了）。 */
      if (typeof X.ACT[a] === 'function') throw new Error(a + ' 仍存在');
    });
    if (html.indexOf('prompt(') >= 0) throw new Error('原型里仍有 prompt() 调用');
  });

  guard('渲染面无 Markdown 泄漏（**）：全部视图 + 集采三张子表弹窗（普通态与增行态）+ 两个导出清单弹窗', () => {
    const bad = [];
    Object.keys(V).forEach(k => { try { if (String(V[k]()).indexOf('**') >= 0) bad.push('V.' + k); } catch (e) {} });
    ['jcInvDlg', 'jcTInvDlg', 'jcPayDlg'].forEach(a => {
      X.ACT[a]({ dataset: { id: 'J03' }, tagName: 'BUTTON' });
      if (String(doc.querySelector('#modalRoot').innerHTML).indexOf('**') >= 0) bad.push(a);
      X.ACT.closeModal();
    });
    X.ACT.jcInvDlg({ dataset: { id: 'J03' }, tagName: 'BUTTON' });
    X.ACT.jcSubAdd({ dataset: { id: 'J03', kind: 'inv' }, tagName: 'BUTTON' });
    if (String(doc.querySelector('#modalRoot').innerHTML).indexOf('**') >= 0) bad.push('子表增行态');
    X.ACT.closeModal();
    X.setJcSub({ kind: '', id: '', d: { date: '', amt: '' } });
    /* ⭐ 2026-09-13：新增的两个「导出清单」弹窗也要扫（它们只在点导出时才渲染，别漏） */
    try {
      const lc = X.ledProjs();
      if (lc.length) { X.setLedExp({ on: true, open: false, pjs: [lc[0]] }); X.ACT.ledExpOk({ dataset: {}, tagName: 'BUTTON' });
        if (String(doc.querySelector('#modalRoot').innerHTML).indexOf('**') >= 0) bad.push('台账导出清单弹窗'); X.ACT.closeModal(); }
      if (X.PROC_PJS.length) { X.setProcExp({ on: true, open: false, pjs: [X.PROC_PJS[0]] }); X.ACT.procExpOk({ dataset: {}, tagName: 'BUTTON' });
        if (String(doc.querySelector('#modalRoot').innerHTML).indexOf('**') >= 0) bad.push('过程资料导出清单弹窗'); X.ACT.closeModal(); }
    } finally { X.setLedExp({ on: false, open: false, pjs: [] }); X.setProcExp({ on: false, open: false, pjs: [] }); }
    if (bad.length) throw new Error('Markdown 泄漏：' + bad.join(' / '));
  });

  guard('枚举出口：全站不再有手写的「分类 / 审批状态 / 流水状态」值域字面量（一律走 ENUMS 唯一出口）', () => {
    /* ⚠️ 判据按**出现次数**：值域字面量在 `ENUMS` 定义里**本来就该有 1 处**（那是主人自己）——
       写成"不得出现"会把主人误判成违规（2026-09-13 实测踩到）。 */
    const cnt = s => html.split(s).length - 1;
    if (cnt("['辅材','机械','集采']") !== 1) throw new Error("分类值域字面量出现 " + cnt("['辅材','机械','集采']") + ' 次（只允许 ENUMS 里那 1 次）');
    if (cnt("['已批','未批']") !== 1) throw new Error("审批状态值域字面量出现 " + cnt("['已批','未批']") + ' 次（只允许 ENUMS 里那 1 次）');
    if (cnt("['全部','生效','已撤销']") !== 0) throw new Error('流水状态值域仍被手写（该走 enumOpts(flowState)）');
    if (X.enumVals('cat').join(',') !== '辅材,机械,集采') throw new Error('ENUMS.cat 值域异常');
    if (X.enumVals('flowState').join(',') !== '生效,已撤销') throw new Error('ENUMS.flowState 值域异常');
    /* 「该放过」：期初展开区的分类下拉是**有意的子集**（只辅材 / 机械）⇒ 保持手写，不得被这条判据误伤 */
    if (cnt("['辅材','机械']") < 1) throw new Error('期初分类子集被误改（该放过用例被误伤）');
  });

  guard('项目档案「确认删除」= **真删**（配置类硬删 §9.4）：行数 -1 · 被引用数据不随删 · 影响范围为真实计数', () => {
    const n0 = X.PJs.length, p = X.PJs.find(x => x.id === 'P01'), i0 = X.PJs.indexOf(p);
    const noCnt = X.NO.filter(n => n.proj === p.full).length;
    const jcCnt = X.JCs.filter(j => j.proj === p.name).length;
    X.ACT.delPj({ dataset: { id: 'P01' }, tagName: 'BUTTON' });
    const dlg = String(doc.querySelector('#modalRoot').innerHTML);
    X.ACT.closeModal();
    if (!/\d+ 条/.test(dlg)) throw new Error('确认弹窗未列出影响范围计数');
    if (dlg.indexOf('本项无关联') >= 0) throw new Error('「集采合同无关联」是过期表述（集采合同自 2026-09-13 起带项目字段）');
    /* ⚠️ 判据只查**渲染面**（这个弹窗），不扫全源码 —— 留档注释里也会出现 `data-act="silent"` 这个词（实测误伤） */
    if (dlg.indexOf('data-act="silent"') >= 0) throw new Error('「确认删除」仍是演示占位（silent）—— 应已改为真删');
    X.ACT.delPjOk({ dataset: { id: 'P01' }, tagName: 'BUTTON' });
    if (X.PJs.length !== n0 - 1) throw new Error('未真正删除（行数 ' + X.PJs.length + '）');
    if (X.PJs.find(x => x.id === 'P01')) throw new Error('P01 仍在列表里');
    if (X.NO.filter(n => n.proj === p.full).length !== noCnt) throw new Error('被引用的通知书被误删');
    if (X.JCs.filter(j => j.proj === p.name).length !== jcCnt) throw new Error('被引用的集采合同被误删');
    X.PJs.splice(i0, 0, p); X.renumberPj();      /* 原位复原（保顺序），本条守卫不留脏 */
  });

  guard('集采发票子表：渲染面不得再出现「只有金额一列」这类**旧表述**（MOD-11 页说明 / 按钮 title / tip / 三张子表弹窗）', () => {
    const hay = [['V.m11', String(V.m11())]];
    ['jcInvDlg', 'jcTInvDlg', 'jcPayDlg'].forEach(a => {
      X.ACT[a]({ dataset: { id: 'J03' }, tagName: 'BUTTON' });
      hay.push([a, String(doc.querySelector('#modalRoot').innerHTML)]);
      X.ACT.closeModal();
    });
    const bad = hay.filter(([, h]) => h.indexOf('只有金额一列') >= 0 || h.indexOf('只有「金额」一列') >= 0).map(([n]) => n);
    if (bad.length) throw new Error('旧表述残留：' + bad.join(' / '));
  });

  guard('库存单据明细表：「重新导入 i8 数据」按钮已删除（动作 + 视图都不再有；重导不覆盖调整单的口径仍在 §9.5）', () => {
    if (typeof X.ACT.reimport === 'function') throw new Error('reimport 动作仍在');
    if (String(V.m08()).indexOf('data-act="reimport"') >= 0) throw new Error('MOD-08 仍渲染「重新导入」按钮');
    /* ⚠️ 2026-09-26（`#2`）：「`CHG` 里仍登记 reimport」那半句随名单一起删（没有主人了）。 */
  });

  console.log('\n--- 10a. 导出入口与提示语一致性（含 §7.1 模板形态）---');
  guard('导出入口（2026-09-13 用户口径）：付款统计 / 特殊费用月报表**不设单独导出按钮**；集采台账按钮不再标「R9 · Excel 风格」', () => {
    const m05 = String(V.m05()), m09 = String(V.m09()), m11 = String(V.m11());
    if (m05.indexOf('data-t="付款统计"') >= 0) throw new Error('付款统计仍有导出按钮（它是付款流水的汇总视图，不单独导出）');
    if (m09.indexOf('data-t="特殊费用月报表"') >= 0) throw new Error('特殊费用月报表仍有导出按钮（它随逐月欠款台账一起导出）');
    if (m09.indexOf('随「逐月欠款台账」导出') < 0) throw new Error('MOD-09 未给出「随台账导出」的说明（用户会以为漏了）');
    if (m11.indexOf('R9 · Excel 风格') >= 0) throw new Error('集采台账按钮仍标「R9 · Excel 风格」（R9 是页面风格，不是导出要求）');
    if (m11.indexOf('data-t="集采台账"') < 0) throw new Error('集采台账导出按钮不该被删');
  });

  /* ⭐ 2026-09-13：逐月欠款台账「导出」重构 —— 一个入口 + 多选项目 + 每项目一簿三表。以下 5 条钉住。 */
  guard('逐月欠款台账导出：**两栏内的 `expLed` 已删、卡头只剩一个导出入口**（`ledExpToggle`）', () => {
    if (typeof X.ACT.expLed === 'function') throw new Error('expLed 动作仍在');
    const h = String(V.m05());
    if (h.indexOf('data-act="expLed"') >= 0) throw new Error('MOD-05 仍渲染 expLed 按钮');
    if ((h.match(/data-act="ledExpToggle"/g) || []).length !== 1) throw new Error('导出入口数 ≠ 1');
  });

  guard('逐月欠款台账导出：展开区**默认选中本页当前项目**，且**不改动页面那个单选项目**（取样 = 非默认项目）', () => {
    const bak = X.ledState(), cands = X.ledProjs();
    if (cands.length < 2) throw new Error('台账候选不足 2 个 ⇒ 判据失去区分力');
    const pick = cands[1];                                    /* 故意取**第二个**（≠ 默认的第一个）*/
    try {
      X.ACT.ledPjPick({ dataset: { pj: pick }, tagName: 'BUTTON' });   /* 用页面自己的动作切项目（不直接改内部状态） */
      if (X.ledState().proj !== pick) throw new Error('页面项目没切成功');
      X.ACT.ledExpToggle({ dataset: {}, tagName: 'BUTTON' });
      const st = X.ledExpState();
      if (!st.on) throw new Error('展开区没打开');
      if (st.pjs.length !== 1 || st.pjs[0] !== pick) throw new Error('默认选中 ≠ 本页当前项目：' + JSON.stringify(st.pjs) + ' vs ' + pick);
      if (X.ledState().proj !== pick) throw new Error('打开导出面板把页面项目改掉了');
    } finally { X.setLedExp({ on: false, open: false, pjs: [] }); X.setLed(bak); }
  });

  guard('逐月欠款台账导出：项目面板 = **多选**（有全选 / 清空、候选项是 checkbox、不是 radio）', () => {
    try {
      X.ACT.ledExpToggle({ dataset: {}, tagName: 'BUTTON' });
      X.ACT.ledExpPjToggle({ dataset: {}, tagName: 'BUTTON' });
      const h = String(V.m05());
      if (h.indexOf('data-act="ledExpPjAll"') < 0 || h.indexOf('data-act="ledExpPjNone"') < 0) throw new Error('缺「全选 / 清空」⇒ 不是多选面板');
      if ((h.match(/data-act="ledExpPjPick"/g) || []).length < 1) throw new Error('面板里没有候选项');
      if (h.indexOf('name="projPanelSingle"') >= 0) throw new Error('渲染成了单选 radio');
    } finally { X.setLedExp({ on: false, open: false, pjs: [] }); }
  });

  guard('逐月欠款台账导出：清单预览 —— 1 个项目 = 1 个工作簿 · **3 个工作表**；≥2 个项目 = zip + 每项目一行', () => {
    const root = () => String(doc.querySelector('#modalRoot').innerHTML);
    const cands = X.ledProjs();
    try {
      X.setLedExp({ on: true, open: false, pjs: [cands[0]] });
      X.ACT.ledExpOk({ dataset: {}, tagName: 'BUTTON' });
      const h1 = root(); X.ACT.closeModal();
      if (h1.indexOf('1 个工作簿') < 0) throw new Error('单项目未说明「1 个工作簿」');
      ['辅材欠款', '机械欠款', '特殊费用月报表'].forEach(t => { if (h1.indexOf(t) < 0) throw new Error('缺工作表：' + t); });
      if (cands.length < 2) throw new Error('候选不足 2 个 ⇒ 判据失去区分力');
      X.setLedExp({ on: true, open: false, pjs: [cands[0], cands[1]] });
      X.ACT.ledExpOk({ dataset: {}, tagName: 'BUTTON' });
      const h2 = root(); X.ACT.closeModal();
      if (h2.indexOf('.zip') < 0) throw new Error('多项目未打成 zip');
      if ((h2.match(/<tr><td class="fc">/g) || []).length !== 2) throw new Error('清单行数 ≠ 所选项目数');
    } finally { X.setLedExp({ on: false, open: false, pjs: [] }); }
  });

  guard('逐月欠款台账导出：展开区渲染在 `.tw` **之外**（浮层面板才不被裁），且**恰好 1 处**', () => {
    try {
      X.setLedExp({ on: true, open: false, pjs: [] });
      const h = String(V.m05());
      const iStrip = h.indexOf('data-act="ledExpPjToggle"'), iTw = h.indexOf('<div class="tw">');
      if (iStrip < 0) throw new Error('展开区未渲染');
      if (!(iStrip < iTw)) throw new Error('展开区不在 `.tw` 之前（会被滚动容器裁）');
      /* ⚠️ 位置判据必须**同时数出现次数** —— 只比 indexOf 的话"既在外面又在里面"抓不到（2026-09-13 踩过） */
      if ((h.match(/data-act="ledExpPjToggle"/g) || []).length !== 1) throw new Error('展开区渲染了多处');
    } finally { X.setLedExp({ on: false, open: false, pjs: [] }); }
  });

  /* ⭐ 2026-09-13 批 3：过程资料多选导出 + 库存单据「含数据透视表」额外导出 */
  guard('过程资料导出：`exportProc` 已删、改展开区**多选项目**（每项目一份 · 17 列模板 · ≥2 打 zip）· 展开区在 `.tw` 之外且恰好 1 处', () => {
    if (typeof X.ACT.exportProc === 'function') throw new Error('exportProc 动作仍在');
    const cands = X.PROC_PJS;
    if (cands.length < 2) throw new Error('候选不足 2 个 ⇒ 判据失去区分力');
    const root = () => String(doc.querySelector('#modalRoot').innerHTML);
    try {
      X.ACT.procExpToggle({ dataset: {}, tagName: 'BUTTON' });
      X.ACT.procExpPjToggle({ dataset: {}, tagName: 'BUTTON' });   /* 面板要展开才渲染得出来（判「多选」必须开着面板） */
      const h = String(V.m06());
      const iStrip = h.indexOf('data-act="procExpPjToggle"'), iTw = h.indexOf('<div class="tw">');
      if (iStrip < 0) throw new Error('展开区未渲染');
      if (!(iStrip < iTw)) throw new Error('展开区不在 `.tw` 之前（浮层会被裁）');
      if ((h.match(/data-act="procExpPjToggle"/g) || []).length !== 1) throw new Error('展开区渲染了多处');
      if (h.indexOf('data-act="procExpPjAll"') < 0 || h.indexOf('data-act="procExpPjNone"') < 0) throw new Error('面板不是多选（缺全选 / 清空）');
      /* 单项目 → 1 个文件；两项目 → zip + 2 行 */
      X.setProcExp({ on: true, open: false, pjs: [cands[0]] });
      X.ACT.procExpOk({ dataset: {}, tagName: 'BUTTON' });
      const h1 = root(); X.ACT.closeModal();
      if (h1.indexOf('1 个文件') < 0 || h1.indexOf('17 列模板') < 0) throw new Error('单项目清单未说明「1 个文件 + 17 列模板」');
      X.setProcExp({ on: true, open: false, pjs: [cands[0], cands[1]] });
      X.ACT.procExpOk({ dataset: {}, tagName: 'BUTTON' });
      const h2 = root(); X.ACT.closeModal();
      if (h2.indexOf('.zip') < 0) throw new Error('多项目未打成 zip');
      if ((h2.match(/<tr><td class="fc">/g) || []).length !== 2) throw new Error('清单行数 ≠ 所选项目数');
    } finally { X.setProcExp({ on: false, open: false, pjs: [] }); }
  });

  guard('过程资料导出：展开区**默认选中本页当前项目**（取样 = 最后一个候选，判据有区分力）', () => {
    const bak = X.procState(), cands = X.PROC_PJS;
    if (cands.length < 2) throw new Error('候选不足 2 个');
    const pick = cands[cands.length - 1];
    try {
      X.ACT.procPjPick({ dataset: { pj: pick }, tagName: 'BUTTON' });   /* 用页面自己的动作切（不直接改内部状态） */
      if (X.procState().pj !== pick) throw new Error('页面项目没切成功');
      X.ACT.procExpToggle({ dataset: {}, tagName: 'BUTTON' });
      const st = X.procExpState();
      if (!st.on) throw new Error('展开区没打开');
      if (st.pjs.length !== 1 || st.pjs[0] !== pick) throw new Error('默认选中 ≠ 本页当前项目：' + JSON.stringify(st.pjs));
    } finally { X.setProcExp({ on: false, open: false, pjs: [] }); X.ACT.procPjPick({ dataset: { pj: bak.pj }, tagName: 'BUTTON' }); }
  });

  guard('库存单据明细：**额外**一个「导出（含数据透视表）」，主表的朴素导出仍在（互不影响）', () => {
    const h = String(V.m08());
    if (h.indexOf('data-act="expPivot"') < 0) throw new Error('缺「导出（含数据透视表）」按钮');
    if (h.indexOf('data-act="exp" data-t="库存单据明细总表"') < 0) throw new Error('主表朴素导出按钮被误删');
    if (typeof X.ACT.expPivot !== 'function') throw new Error('expPivot 动作不在');
  });

  /* ===== §7.1 导出：提示语必须与**模板实际形态**一致（2026-09-14 新增）=====
     由来：`expPivot` 原提示写「明细（**列与页面一致**）· 工作表 2 = 透视（**按项目 × 月份**）」，
     与 `模板_库存单据明细表.xlsx` **两处都不符** —— 真实是 **3 张 sheet**（明细**列随 i8 源文件**
     ＋「过程资料」透视 ＋「安全文明施工费」透视），且走**路径②**（脚本改 i8 源文件、不套模板骨架）。
     ⚠️ 既有的那条"提示语 ≠ 未发生的动作"守护**只盯「已打开 / 结果已回显」字样** ⇒ 这处不在覆盖内。 */
  guard('§7.1｜「导出（含数据透视表）」提示必须与模板实际形态一致（路径②：明细随 i8 源文件 + 两张透视）', () => {
    const cap = []; const orig = doc.body.appendChild;
    doc.body.appendChild = el => { cap.push(String(el.innerHTML)); };
    try { X.ACT.expPivot({ dataset: {}, tagName: 'BUTTON' }); }
    finally { doc.body.appendChild = orig; }
    const txt = cap.join(' ').replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
    if (!txt) throw new Error('点「导出（含数据透视表）」没有任何反馈 —— 断言失去区分力');
    if (txt.indexOf('过程资料') < 0) throw new Error('提示里没有「过程资料」透视（`模板_库存单据明细表.xlsx` 该 sheet 就叫这个名）：' + txt);
    if (txt.indexOf('安全文明施工费') < 0) throw new Error('提示里没有「安全文明施工费」透视（模板第 3 张 sheet）：' + txt);
    if (/列与页面一致/.test(txt)) throw new Error('提示声称「列与页面一致」—— **路径②的明细列随 i8 源文件**，不是页面列（实测模板 28 列 vs 页面 20 列）');
  });

  /* ===== 2026-09-13 深夜：MOD-12 差异登记补「手工新建 / 删除 / 筛选」（用户口述 `OPEN-03` 后裁定「都改」）=====
     由来：`OPEN-03` 已确认 —— 用户**此前从未做过差异登记**（无 Excel / 纸质 / 系统载体），量级 **半年十几~几十笔**。
     ⇒ 原来那页只有「导出差异 + 标记已核对」，**一条都登记不进去**（演示数据之外无法新增）；
       本组守护的就是"能不能手工登记进去 + 能不能筛出来 + 能不能删掉"这三件事。
     ⚠️ 判据一律**从动作进去、用独立事实出来**（不直接改内部状态）；每个都先 `rollback()` 自备干净基线。 */

  /* ⚠️ 本组自带的取行助手：`_rowsOf` / `_rowsData` 依赖 `data-tk`（**只有 `applySorts` 之后的 HTML 才有**），
     直接用 `V.m12()` 的原样 HTML 会取到 0 行（本组踩过一次）⇒ 这里改用 `data-sort-key` 圈表 + 排除「合计」行。 */
  const _dfRows = h => {
    const t = _tblByKey(h, 'm12:diffs');
    const b = (t.match(/<tbody\b[^>]*>([\s\S]*?)<\/tbody>/i) || [, ''])[1];
    return (b.match(/<tr\b[^>]*>[\s\S]*?<\/tr>/gi) || []).filter(r => {
      const c0 = ((r.match(/<td\b[^>]*>([\s\S]*?)<\/td>/i) || [, ''])[1]).replace(/<[^>]*>/g, '').trim();
      return c0 !== '' && c0.indexOf('合计') < 0;
    });
  };

  console.log('\n--- 10b. 差异登记（MOD-12 · §5.8.3）---');
  guard('差异登记｜「＋ 登记差异」入口必须在（本页是手工清单 —— 之前一条都建不出来）', () => {
    rollback();
    const h = String(V.m12());
    if (h.indexOf('data-act="dfAdd"') < 0) throw new Error('缺「＋ 登记差异」入口');
    if (typeof X.ACT.dfAdd !== 'function') throw new Error('dfAdd 动作不在');
    if (typeof X.ACT.dfSave !== 'function' || typeof X.ACT.dfDel !== 'function') throw new Error('登记 / 删除动作不在');
  });

  guard('差异登记｜登记一条：落库 +1 笔 · 归属恒为「库存单据」· 金额带符号 · 编号不撞既有行', () => {
    rollback();
    const before = X.DFs.length, ids0 = X.DFs.map(d => d.id);
    const pj = X.PJs.filter(p => p.type !== 'shell')[0];
    if (!pj) throw new Error('没有可建档项目样本 —— 断言失去区分力');
    try {
      X.ACT.dfAdd({ dataset: {}, tagName: 'BUTTON' });                    /* 走页面自己的入口 */
      if (!X.dfState().on) throw new Error('增行态没打开');
      X.ACT.dfSet({ dataset: { k: 'month' }, value: '2026-08', tagName: 'SELECT' });
      X.ACT.dfSet({ dataset: { k: 'proj' }, value: pj.full, tagName: 'SELECT' });
      X.ACT.dfSet({ dataset: { k: 'detail' }, value: '断言用差异（登记）', tagName: 'INPUT' });
      X.ACT.dfSet({ dataset: { k: 'amount' }, value: '-321.50', tagName: 'INPUT' });
      X.ACT.dfSave({ dataset: {}, tagName: 'BUTTON' });
      const add = X.DFs.filter(d => ids0.indexOf(d.id) < 0);
      if (add.length !== 1) throw new Error('没有落库（新增 ' + add.length + ' 条）');
      const n = add[0];
      if (n.type !== '库存单据') throw new Error('归属不是「库存单据」：' + n.type);
      if (n.amount !== -321.5) throw new Error('金额没落对：' + n.amount);
      if (n.proj !== pj.full) throw new Error('项目没落对');
      if (n.month !== '2026-08') throw new Error('核算月没落对：' + n.month);
      if (n.status !== '待核对') throw new Error('新登记的默认状态应为「待核对」：' + n.status);
      if (X.DFs.length !== before + 1) throw new Error('笔数没 +1');
      if (ids0.indexOf(n.id) >= 0) throw new Error('编号撞了既有行：' + n.id);
      if (X.dfState().on) throw new Error('保存后增行态没复位');
      if (String(V.m12()).indexOf('draftrow') >= 0) throw new Error('保存后草稿行还在');
    } finally { rollback(); }
  });

  guard('差异登记｜必填校验：核算月 / 项目 / 差异内容 缺一不可（缺则拒绝且不入库）', () => {
    rollback();
    const pj = X.PJs.filter(p => p.type !== 'shell')[0], n0 = X.DFs.length;
    const set = (k, v) => X.ACT.dfSet({ dataset: { k }, value: v, tagName: 'INPUT' });
    try {
      X.ACT.dfAdd({ dataset: {}, tagName: 'BUTTON' });
      /* ⚠️ 金额先填成**合法值** —— 否则它会替"必填校验"挡下这一枪，三条必填里
         「差异内容」那条就永远测不到（反向灵敏度实测出来的假绿：M1 去掉该校验后本断言仍绿）。 */
      set('month', '2026-08'); set('proj', pj.full); set('amount', '-1');
      X.ACT.dfSave({ dataset: {}, tagName: 'BUTTON' });        /* 缺「差异内容」 */
      if (X.DFs.length !== n0) throw new Error('缺「差异内容」却落库了');
      set('detail', '断言用差异（必填）'); set('proj', '');
      X.ACT.dfSave({ dataset: {}, tagName: 'BUTTON' });        /* 缺「项目」 */
      if (X.DFs.length !== n0) throw new Error('缺「项目」却落库了');
      set('proj', pj.full); set('month', '');
      X.ACT.dfSave({ dataset: {}, tagName: 'BUTTON' });        /* 缺「核算月」 */
      if (X.DFs.length !== n0) throw new Error('缺「核算月」却落库了');
    } finally { rollback(); }
  });

  guard('差异登记｜金额出口：非数字被拒 · **负数必须放行**（§5.8.3 带符号 —— 走 badMoney 的 signed 出口）', () => {
    rollback();
    const pj = X.PJs.filter(p => p.type !== 'shell')[0], n0 = X.DFs.length;
    const set = (k, v) => X.ACT.dfSet({ dataset: { k }, value: v, tagName: 'INPUT' });
    try {
      X.ACT.dfAdd({ dataset: {}, tagName: 'BUTTON' });
      set('detail', '断言用差异（金额）'); set('proj', pj.full); set('amount', 'abc');
      X.ACT.dfSave({ dataset: {}, tagName: 'BUTTON' });
      if (X.DFs.length !== n0) throw new Error('非数字金额却落库了');
      set('amount', '-88.88');
      X.ACT.dfSave({ dataset: {}, tagName: 'BUTTON' });
      const add = X.DFs.filter(d => d.detail === '断言用差异（金额）');
      if (add.length !== 1) throw new Error('负数金额被误拒 —— 差异金额必须可正可负（§5.8.3）');
      if (add[0].amount !== -88.88) throw new Error('金额没落对：' + add[0].amount);
    } finally { rollback(); }
  });

  guard('差异登记｜草稿行：挂 draftrow（钉表尾）+ 列对齐（<td> 数 = 表头列数）· 取消 = 草稿丢弃、数据一字未改', () => {
    rollback();
    const n0 = X.DFs.length;
    try {
      X.ACT.dfAdd({ dataset: {}, tagName: 'BUTTON' });
      const h = _tblByKey(String(V.m12()), 'm12:diffs');
      const draft = /<tr class="draftrow">[\s\S]*?<\/tr>/.exec(h);
      if (!draft) throw new Error('草稿行没渲染 / 没挂 draftrow（`applySorts` 靠它钉在数据行之后、合计行之前）');
      const thN = (h.match(/<th\b/g) || []).length;
      const tdN = (draft[0].match(/<td\b/g) || []).length;
      if (tdN !== thN) throw new Error('草稿行没列对齐：' + tdN + ' ≠ ' + thN);
      if (X.DFs.length !== n0) throw new Error('光开增行态就改了数据');
      X.ACT.dfCancel({ dataset: {}, tagName: 'BUTTON' });
      if (X.DFs.length !== n0) throw new Error('取消却改了数据');
      if (X.dfState().on) throw new Error('取消后增行态没复位');
      if (String(V.m12()).indexOf('draftrow') >= 0) throw new Error('取消后草稿行还在');
    } finally { rollback(); }
  });

  guard('差异登记｜删除：只删该行（其余一行不动）', () => {
    rollback();
    const n0 = X.DFs.length, victim = X.DFs[0].id, others = X.DFs.slice(1).map(d => d.id);
    try {
      X.ACT.dfDel({ dataset: { id: victim }, tagName: 'BUTTON' });
      if (X.DFs.length !== n0 - 1) throw new Error('笔数没 -1');
      if (X.DFs.some(d => d.id === victim)) throw new Error('该行没删掉');
      if (others.some(id => !X.DFs.some(d => d.id === id))) throw new Error('误删了别的行');
    } finally { rollback(); if (X.DFs.length !== n0) throw new Error('回滚失败（DFs 没复原）'); }
  });

  guard('差异登记｜筛选生效：状态 + 核算月 叠加，行数 = 独立复算（走真实控件 / 真实作用域）', () => {
    rollback();
    try {
      const byStat = X.DFs.reduce((m, d) => { m[d.status] = (m[d.status] || 0) + 1; return m; }, {});
      const pick = Object.keys(byStat).sort((a, b) => byStat[b] - byStat[a])[0];
      if (!pick) throw new Error('没有状态样本 —— 断言失去区分力');
      X.ACT.dfFilter({ dataset: {}, tagName: 'SELECT', value: pick });   /* 动作读的是 t.value（与 cases 里同款驱动） */
      if (X.dfState().f.stat !== pick) throw new Error('状态筛选没写进状态');
      const want = X.DFs.filter(d => d.status === pick).length;
      const got = _dfRows(String(V.m12())).length;
      if (got !== want) throw new Error('状态筛选行数不符：' + got + ' ≠ ' + want);
      /* 叠加核算月：**优先挑一个"该状态组里非满员"的月**，让行数真的变少（否则这条判据没有区分力） */
      const base = X.DFs.filter(d => d.status === pick);
      const cand = base.filter(d => base.filter(o => o.month === d.month).length < base.length)[0];
      const ym = (cand || base[0]).month;
      X.ACT.mpPick({ dataset: { scope: 'df', m: '', val: ym }, tagName: 'BUTTON' });
      if (X.dfState().f.ym !== ym) throw new Error('核算月筛选没写进状态');
      const want2 = X.DFs.filter(d => d.status === pick && d.month === ym).length;
      const got2 = _dfRows(String(V.m12())).length;
      if (got2 !== want2) throw new Error('核算月筛选行数不符：' + got2 + ' ≠ ' + want2);
      if (cand && want2 >= want) throw new Error('叠加筛选后行数没变少 —— 判据失去区分力');
      X.ACT.dfReset({ dataset: {}, tagName: 'BUTTON' });
      const f = X.dfState().f;
      if (f.ym !== '全部' || f.stat !== '全部') throw new Error('重置没回到「全部 / 全部」：' + JSON.stringify(f));
    } finally { rollback(); }
  });

  guard('差异登记｜筛选无结果 → 空态提示行，跨列数 = **独立数表头**（不借 thCount 自证）', () => {
    rollback();
    try {
      const have = [...new Set(X.DFs.map(d => d.month))];
      const empty = ['2026-01', '2026-02', '2026-03', '2026-04', '2026-05'].find(m => have.indexOf(m) < 0);
      if (!empty) throw new Error('找不到空场景（判据失去区分力）');
      X.ACT.mpPick({ dataset: { scope: 'df', m: '', val: empty }, tagName: 'BUTTON' });
      const h = _tblByKey(String(V.m12()), 'm12:diffs');
      const trN = (h.match(/<tr\b/g) || []).length;
      if (trN !== 2) throw new Error('空场景没造出来（应只有「表头 + 空态」两行，实测 ' + trN + ' 行）');
      const col = /colspan="(\d+)"[^>]*>([\s\S]*?)<\/td>/.exec(h);
      if (!col) throw new Error('空态行没有 colspan / 没有那一格');
      const thN = (h.match(/<th\b/g) || []).length;
      if (Number(col[1]) !== thN) throw new Error('空态跨列数 ' + col[1] + ' ≠ 表头列数 ' + thN);
      if (!col[2].replace(/<[^>]*>/g, '').trim()) throw new Error('空态行是空白的（R10① 要求给提示行）');
    } finally { rollback(); }
  });

  guard('差异登记｜筛选默认值 = 「全部 / 全部」——比**加载时快照**（交互路径里有 dfFilter / mpPick(df)）', () => {
    rollback();
    const f = X.dfState().f;
    if (DFF0.ym !== '全部' || DFF0.stat !== '全部') throw new Error('基线快照本身不是「全部 / 全部」：' + JSON.stringify(DFF0));
    if (f.ym !== DFF0.ym || f.stat !== DFF0.stat) throw new Error('筛选默认值被改：' + JSON.stringify(f) + ' ≠ ' + JSON.stringify(DFF0));
  });

  /* ==================== 集采供应商自动匹配（§6.6.3 · DEV-J-01 2026-09-14 改裁）====================
     口径主人 =《说明书》§6.6.3。三条要义：
       ① **反着匹配**（拿候选池探测单据名，不是从单据名里切简称）；
       ② **先长后短取最高等级**（高等级一命中，低等级一律不看）；
       ③ **按命中家数分叉**（1 家预填待确认 / ≥2 家让用户选 / 0 家手工），**绝不猜**。
     ⚠️ 判据一律**从动作进去、用独立事实出来**；每个都先 `rollback()` 自备干净基线。 */
  console.log('\n--- 10c. §6.6.3 集采供应商自动匹配（`DEV-J-01`）---');
  guard('§6.6.3｜片段长度 = 6 − 等级（②4 字 · ③3 字 · ④2 字）—— 独立复算，防等级语义写错', () => {
    /* 这条守的是**等级语义**本身：曾把 `len` 写成 `level+2`（→ ③ 变 5 字、④ 变 6 字），
       等级越高片段越长 ⇒ "先长后短"名存实亡。判据用**独立的长度公式**，不借被测函数自证。 */
    const full = '洛阳市业祥商贸有限公司';
    [2, 3, 4].forEach(lvl => {
      const frs = X.supFrags(full, lvl);
      const wantLen = 6 - lvl;
      if (!frs.length) throw new Error(`等级 ${lvl} 不该没有片段`);
      frs.forEach(f => { if (f.length !== wantLen) throw new Error(`等级 ${lvl} 的片段长度 ${f.length} ≠ ${wantLen}（等级语义写错）`); });
      /* 片段必须**真的是全名的连续子串**（不是切了不该切的位置） */
      frs.forEach(f => { if (full.indexOf(f) < 0) throw new Error(`等级 ${lvl} 的片段「${f}」不是全名连续子串`); });
    });
    if (X.supFrags(full, 1).length !== 1 || X.supFrags(full, 1)[0] !== full) throw new Error('等级 1 应为「全名整体」');
    /* 反向灵敏度：全名比片段还短 ⇒ 该等级必须为空（否则会切出越界片段） */
    if (X.supFrags('业祥', 2).length !== 0) throw new Error('「业祥」(2字) 在等级 2（需 4 字）应无片段');
  });

  guard('§6.6.3｜候选池 = 本项目集采合同供应商，**按全名去重**（同一家多份合同不重复计数）', () => {
    rollback();
    const n = X.NO.find(x => x.id === 'N17');       /* N17 ∈ 新沂项目（池只有「内蒙兴安电力器材有限公司」）*/
    if (!n) throw new Error('样本 N17 不存在');
    /* 独立复算：池 = 全库中「项目 = 该行项目键」的合同供应商去重，用 Set 独立数 */
    const k = X.ntProjKey(n);
    const want = [...new Set(X.JCs.filter(j => j.proj === k).map(j => String(j.supplier || '').trim()).filter(Boolean))];
    const got = X.supPool(n);
    if (got.length !== want.length || want.some(s => got.indexOf(s) < 0))
      throw new Error('候选池不符：' + JSON.stringify(got) + ' ≠ ' + JSON.stringify(want));
    /* 反向灵敏度：**跨项目**供应商绝不许进池（§6.6.3「明确不做跨项目匹配」） */
    const other = X.JCs.find(j => String(j.supplier || '').trim() && j.proj !== k);
    if (other && got.indexOf(String(other.supplier).trim()) >= 0)
      throw new Error('他项目供应商混进了候选池（跨项目匹配被误引入）');
    /* ⭐ **去重判据必须有区分力** —— 实测当前演示数据里"同一项目内同一供应商出现在多份合同"的组数 = **0**
       ⇒ 直接数池长**测不出**去重（去不去重都一样长 = 假绿温床）。
       做法：**临时追加一份同项目、同供应商的第二份合同**，池长**必须不变**；再取一份**不同**供应商，池长**必须+1**
       （后者是"该放过"用例：确认判据不是"池长永远不变"这种傻断言）。rollback 会复原。 */
    const N0 = got.length;
    const sup0 = got[0];
    const src = X.JCs.find(j => j.proj === k);
    X.JCs.push(Object.assign({}, src, { supplier: sup0 }));             /* 同项目同供应商的第二份合同 */
    if (X.supPool(n).length !== N0) throw new Error('同供应商的第二份合同使池变长 —— **去重失效**');
    X.JCs[X.JCs.length - 1].supplier = sup0 + '（另一家）';             /* 改成一个全新的供应商全名 */
    if (X.supPool(n).length !== N0 + 1) throw new Error('新增一家不同供应商却没进池 —— 判据过严（会漏掉真供应商）');
  });

  guard('§6.6.3｜探测顺序：先长后短、**取命中的最高等级那一批**（高等级命中 ⇒ 低等级不看）', () => {
    rollback();
    const n = X.NO.find(x => x.id === 'N17');
    /* N17：单据名**含该供应商全名整体** ⇒ 必须是**等级 1**（全名），而不是退化成 2 字命中 */
    const pool = X.supPool(n);
    const full = pool[0];
    if (String(n.doc).indexOf(full) < 0) throw new Error('样本前提不成立：N17 单据名不含供应商全名');
    const r = X.supMatch(n);
    if (r.lvl !== 1) throw new Error('含全名整体却未判为等级 1（实测 ' + r.lvl + '：' + X.SUP_LVL_NAME[r.lvl] + '）');
    if (r.cands.length !== 1 || r.cands[0] !== full) throw new Error('等级 1 命中集应恰为该全名');
    /* ⭐ 判据的**区分力**验证：人为把「全名」从单据名里去掉（**只改副本**）⇒ 必须掉到更低等级，
       否则说明这条断言根本测不出"先长后短"（假绿温床）。 */
    const docBak = n.doc; n.doc = String(docBak).replace(full, '');
    const r2 = X.supMatch(n);
    n.doc = docBak;
    if (r2.lvl === 1) throw new Error('去掉全名后仍判等级 1 —— 断言失去区分力');
    /* ⭐⭐ **低等级一律不看**（不提前返回就会漏掉这条）：造"高等级命中 A、同时低等级命中 B"的场景 ——
       命中集**只能有 A**，B 绝不许混进来。做法：在单据名里塞进**另一家**的 2 字片段，
       同时保持 A 的全名在单据名里。若不提前返回，B 也会被收进命中集 ⇒ 必须红。 */
    const kk = X.ntProjKey(n);
    const others = [...new Set(X.JCs.filter(j => j.proj === kk).map(j => String(j.supplier || '').trim()).filter(s => s && s !== full))];
    if (others.length) {
      const otherDoc = others[0];
      const otherFrag = X.supFrags(otherDoc, 4)[0];                  /* 另一家的 2 字片段 */
      if (otherFrag) {
        n.doc = docBak + '·' + otherFrag;
        const r3 = X.supMatch(n);
        n.doc = docBak;
        if (r3.cands.indexOf(otherDoc) >= 0)
          throw new Error('高等级已命中，低等级的他家仍被收进命中集 —— 「先长后短、低等级不看」失效');
        if (r3.lvl !== 1 || r3.cands.indexOf(full) < 0) throw new Error('高等级命中被低等级噪声挤掉了');
      }
    }
  });

  guard('§6.6.3｜≥2 家同等级命中 ⇒ 命中集含**全部**同等级家（多命中不猜，交由弹窗让用户选）', () => {
    rollback();
    const n = X.NO.find(x => x.id === 'N15');       /* 德州项目：池 2 家（山东钢铁集团日照… / 德州安泰劳保…）*/
    const pool = X.supPool(n);
    if (pool.length < 2) throw new Error('样本前提不成立：N15 项目供应商池不足 2 家');
    const r = X.supMatch(n);
    if (r.cands.length < 2) throw new Error('多命中样本只判出 ' + r.cands.length + ' 家（应 ≥2）');
    if (r.lvl === 1 || r.lvl === 0) throw new Error('多命中样本的命中等级不合理：' + r.lvl);
    if (r.cands.length === pool.length && pool.length > 2) throw new Error('把整个池当命中集 —— 探测没起作用');
    /* 每一家都必须**真的**在该等级上命中（独立复核片段是否落在单据名里） */
    const doc = String(n.doc);
    r.cands.forEach(s => {
      const frs = X.supFrags(s, r.lvl);
      if (!frs.some(f => doc.indexOf(f) >= 0)) throw new Error(s + ' 被列入命中集，但其「' + X.SUP_LVL_NAME[r.lvl] + '」不在单据名里');
    });
    /* 同等级内**没有遗漏**：池中所有在该等级命中的家都必须在命中集里 */
    const missed = pool.filter(s => s !== r.cands[0] && X.supFrags(s, r.lvl).some(f => doc.indexOf(f) >= 0) && r.cands.indexOf(s) < 0);
    if (missed.length) throw new Error('同等级命中被漏掉：' + JSON.stringify(missed));
  });

  guard('§6.6.3｜0 家命中 ⇒ 返回空命中集（交由用户手工指定），不得硬凑一家', () => {
    rollback();
    const n = X.NO.find(x => x.id === 'N18');       /* 漯河项目：单据名里无本项目供应商任何片段 */
    const r = X.supMatch(n);
    if (r.cands.length !== 0) throw new Error('本该 0 命中，却返回 ' + r.cands.length + ' 家：' + JSON.stringify(r.cands));
    if (r.lvl !== 0) throw new Error('0 命中的等级应为 0，实测 ' + r.lvl);
  });

  /* ⚠️ **刻意不写「空单据名」断言**（原有一条，已删）：实测它**不可证伪** ——
     `''.indexOf(任意非空片段) === -1` ⇒ 空单据名**天然不可能命中**，删掉 `if(!doc)` 保护也照样绿
     （反向灵敏度实测：变异后仍 542/0）。**不可达的断言 = 假绿**，留着只会虚增绿灯数。
     `if(!doc)` 仍保留为**防御性代码**（不删），但不再为它写断言 —— 真正需要守的"0 命中"由 N18 那条覆盖。 */

  /* —— 下面三条走**动作**（不直接改内部状态），断言**可观测结果** —— */
  guard('§6.6.3｜动作 supMatchRun：单命中 ⇒ 写入 sup + 标「自动匹配 · 待确认」（**不静默落库**）', () => {
    rollback();
    const n = X.NO.find(x => x.id === 'N17');       /* 等级 1 单命中 */
    const full = X.supPool(n)[0];
    if (n.sup) throw new Error('样本前提：N17 初始 sup 应为空');
    X.ACT.supMatchRun({ dataset: { id: n.id }, tagName: 'BUTTON' });
    if (n.sup !== full) throw new Error('单命中却没预填 / 预填值不对：' + JSON.stringify(n.sup));
    /* ⭐ 关键：预填**必须同时挂上待确认标记** —— 否则就是"静默落库"（§9.3 旁路表要求） */
    if (!X.supHas(n)) throw new Error('预填了但**没有待确认标记** —— 违反「自动预填不静默落库」');
    if (X.SUP_SUG[n.id] !== full) throw new Error('待确认标记里存的不是自动值：' + JSON.stringify(X.SUP_SUG[n.id]));
    /* 渲染面可见：表格里应出现「自动匹配 · 待确认」标签（**扫渲染结果**，不读内部字段）*/
    const h = _tblByKey(String(V.m03()), 'm03:notices');
    if (h.indexOf('自动匹配 · 待确认') < 0) throw new Error('渲染结果里没有「自动匹配 · 待确认」标记（渲染面无标记 = 用户看不见）');
  });

  guard('§6.6.3｜真实空场景：本项目无集采合同（候选池为空）⇒ 提示且**不写值**、不挂标记', () => {
    rollback();
    const n = X.NO.find(x => x.id === 'N17');
    const k = X.ntProjKey(n);
    /* 造**真空场景**：把本项目下所有合同挪走（不是"造一个空月份"，而是"这个项目真没有合同"） */
    const bak = X.JCs.filter(j => j.proj === k);
    if (!bak.length) throw new Error('样本前提：N17 项目下应有合同');
    const keep = X.JCs.filter(j => j.proj !== k);
    X.JCs.length = 0; keep.forEach(j => X.JCs.push(j));
    const poolN = X.supPool(n).length;
    if (poolN !== 0) throw new Error('空场景没造出来（池仍有 ' + poolN + ' 家）');
    const before = n.sup;
    X.ACT.supMatchRun({ dataset: { id: n.id }, tagName: 'BUTTON' });
    if (n.sup !== before) throw new Error('池为空却改写了 sup');
    if (X.supHas(n)) throw new Error('池为空却挂了待确认标记');
    /* 渲染面：该行应重新出现「自动匹配」可点入口（不是停在空白） */
    const h = _tblByKey(String(V.m03()), 'm03:notices');
    if (h.indexOf('data-act="supMatchRun"') < 0) throw new Error('渲染面没有「自动匹配」入口');
  });

  guard('§6.6.3｜动作 supAccept：点「采用」⇒ 待确认标记消除、值保留（转正式值）', () => {
    rollback();
    const n = X.NO.find(x => x.id === 'N17');
    const full = X.supPool(n)[0];
    X.ACT.supMatchRun({ dataset: { id: n.id }, tagName: 'BUTTON' });
    if (!X.supHas(n)) throw new Error('前置：supMatchRun 没挂上待确认标记');
    X.ACT.supAccept({ dataset: { id: n.id }, tagName: 'BUTTON' });
    if (X.supHas(n)) throw new Error('点了「采用」但待确认标记还在');
    if (n.sup !== full) throw new Error('「采用」后值被清掉了（应保留为正式值）');
  });

  guard('§6.6.3｜动作 supReject：点「不采用」⇒ 值清空、标记消除（回到手工）', () => {
    rollback();
    const n = X.NO.find(x => x.id === 'N17');
    X.ACT.supMatchRun({ dataset: { id: n.id }, tagName: 'BUTTON' });
    if (!n.sup) throw new Error('前置：没预填');
    X.ACT.supReject({ dataset: { id: n.id }, tagName: 'BUTTON' });
    if (n.sup) throw new Error('「不采用」后值没被清空：' + JSON.stringify(n.sup));
    if (X.supHas(n)) throw new Error('「不采用」后待确认标记还在');
  });

  guard('§6.6.3｜人工改写 input ⇒ 视为已确认（待确认标记随之消失）', () => {
    rollback();
    const n = X.NO.find(x => x.id === 'N17');
    X.ACT.supMatchRun({ dataset: { id: n.id }, tagName: 'BUTTON' });
    if (!X.supHas(n)) throw new Error('前置：没挂上待确认标记');
    X.ACT.editSup({ dataset: { id: n.id }, value: '我手填的供应商', tagName: 'INPUT' });
    if (X.supHas(n)) throw new Error('人工改写后待确认标记还在（人工动作应对自动值"就此定性"）');
    if (n.sup !== '我手填的供应商') throw new Error('人工值没写进去：' + JSON.stringify(n.sup));
  });

  guard('§6.6.3｜触发时机：分类改为「集采」**自动跑一次匹配**（走 editCat 动作）', () => {
    rollback();
    const n = X.NO.find(x => x.cat !== '集采' && !x.excl && String(x.doc || ''));
    /* 造场景：把一条**非集采**行的项目挪到「有供应商池」的项目上（只改必要字段） */
    const probe = X.NO.find(x => x.id === 'N17');
    const target = X.NO.find(x => x.id !== 'N17' && !x.excl && x.cat !== '集采');
    if (!target) throw new Error('找不到可改造的非集采行');
    const bakProj = target.proj, bakDoc = target.doc;
    target.proj = probe.proj; target.doc = probe.doc;     /* 用 N17 的项目 + 单据名（含全名）*/
    X.ACT.editCat({ dataset: { id: target.id }, value: '集采', tagName: 'SELECT' });
    const ok = target.sup && X.supHas(target);
    target.proj = bakProj; target.doc = bakDoc;           /* 还原（rollback 之外再保险一次）*/
    if (!ok) throw new Error('分类改为集采后没有自动匹配 + 预填待确认（实测 sup=' + JSON.stringify(target.sup) + '）');
  });

  guard('§6.6.3｜离开集采分类 ⇒ 清空 sup **且**清掉待确认标记', () => {
    rollback();
    const n = X.NO.find(x => x.id === 'N17');
    X.ACT.supMatchRun({ dataset: { id: n.id }, tagName: 'BUTTON' });
    if (!n.sup) throw new Error('前置：没预填');
    X.ACT.editCat({ dataset: { id: n.id }, value: '辅材', tagName: 'SELECT' });
    if (n.sup) throw new Error('改为辅材后 sup 没被清空（该字段仅集采可持有，DEV-P-04）');
    if (X.supHas(n)) throw new Error('改为辅材后待确认标记没清掉');
  });

  guard('§6.6.3｜关联集采合同候选**收窄为「本项目 ＋ 已匹配供应商」**（走后端出口 jcLinkCands）', () => {
    rollback();
    const n = X.NO.find(x => x.id === 'N15');           /* 德州项目：池 2 家 */
    const pool = X.supPool(n);
    if (pool.length < 2) throw new Error('样本前提：德州项目池需 ≥2 家');
    const k = X.ntProjKey(n);
    /* ① 未填供应商 ⇒ 不按供应商过滤 = 本项目全部（保持旧行为，否则什么都选不了） */
    n.sup = '';
    const all = X.JCs.filter(j => j.proj === k).map(j => j.id);
    const got0 = X.jcLinkCands(n).map(j => j.id).filter(id => all.indexOf(id) >= 0);
    if (got0.length !== all.length) throw new Error('未填供应商时候选 ≠ 本项目全部合同');
    /* ② 填上某一家 ⇒ 候选只剩**该供应商**的合同（独立复算） */
    const sup = pool[0];
    n.sup = sup;
    const want = X.JCs.filter(j => j.proj === k && String(j.supplier || '').trim() === sup).map(j => j.id);
    const got = X.jcLinkCands(n).filter(j => j.proj === k).map(j => j.id);
    if (want.length === 0) throw new Error('样本前提：该供应商在本项目应有合同（收窄后候选不能为空）');
    if (got.length !== want.length || want.some(id => got.indexOf(id) < 0))
      throw new Error('候选没收窄到该供应商：' + JSON.stringify(got) + ' ≠ ' + JSON.stringify(want));
    if (want.length >= all.length) throw new Error('收窄前后候选一样多 —— 断言失去区分力');
  });

  guard('§6.6.3｜多命中动作 supMatchRun 开弹窗 + 「确认」写入所选（不猜、不自动选第一个）', () => {
    rollback();
    const n = X.NO.find(x => x.id === 'N15');
    X.ACT.supMatchRun({ dataset: { id: n.id }, tagName: 'BUTTON' });
    /* 多命中 ⇒ 弹窗打开（渲染面有「选择供应商」）+ **值没被自动写入**（绝不猜） */
    const mh = String(doc.querySelector('#modalRoot').innerHTML);
    if (mh.indexOf('选择供应商') < 0) throw new Error('多命中没开消歧弹窗');
    if (n.sup) throw new Error('多命中竟自动写入了一家（必须让用户选）');
    /* 模拟选择 → 确认 */
    const cand = X.supPool(n).find(s => X.supFrags(s, X.supMatch(n).lvl).some(f => String(n.doc).indexOf(f) >= 0));
    if (!cand) throw new Error('找不到可选的命中候选');
    X.ACT.supPick({ value: cand, tagName: 'SELECT' });
    X.ACT.supOk({ dataset: { id: n.id }, tagName: 'BUTTON' });
    if (n.sup !== cand) throw new Error('确认后没写入所选供应商：' + JSON.stringify(n.sup));
    if (!X.supHas(n)) throw new Error('确认所选后没有待确认标记（多命中选完仍应待确认）');
  });

  guard('§6.6.3｜0 命中动作：不开消歧弹窗、不写入值，走「本项目无此供应商」提示', () => {
    rollback();
    const n = X.NO.find(x => x.id === 'N18');
    const before = n.sup;
    X.ACT.supMatchRun({ dataset: { id: n.id }, tagName: 'BUTTON' });
    if (n.sup !== before) throw new Error('0 命中却改写了 sup');
    if (X.supHas(n)) throw new Error('0 命中却挂了待确认标记');
  });

  guard('§6.6.3｜supPick 的 `change` 会被承接（`#2` 起**不再靠 `CHG` 登记** ⇒ 判词换成「动作真存在」）', () => {
    /* ⚠️ 2026-09-26（`#2`）：原判词是「`supPick` 必须在 `CHG` 里」，防的是「表单类动作漏登记 ⇒
       `change` 被静默丢弃」。名单拆掉后**漏登记这回事不存在了**（`change` 委托看见 `data-act` 就跑）
       ⇒ 剩下的失效形态 = **`data-act` 没有同名动作**（由上面那条「无死控件」守）。
       ⇒ 这里保留**能证伪的那半句**：动作必须真在 `ACT` 上。 */
    if (typeof X.ACT.supPick !== 'function') throw new Error('supPick 不是 ACT 上的动作 —— change 会被丢弃');
    ['supMatchRun', 'supOk', 'supAccept', 'supReject'].forEach(a => {
      if (typeof X.ACT[a] !== 'function') throw new Error('动作 ' + a + ' 未定义');
    });
  });

  /* ===== §4.4.5 / 操作列（2026-09-14）：撤销付款 · 查看关联 ===== */
  guard('操作列｜「撤销付款」**只在该行有生效流水时出现**（没付过的不给按钮，免得空点）', () => {
    rollback();
    /* 找一条**有生效流水**的 i8 行，与一条**没有流水**的 i8 行，对比其操作列 HTML */
    const withFlow = X.NO.filter(n => !n.manual && X.ntHasFlow(n));
    const noFlow = X.NO.filter(n => !n.manual && !X.ntHasFlow(n));
    if (!withFlow.length || !noFlow.length) throw new Error('样本前提：需同时存在"有流水"与"无流水"的 i8 行');
    const hw = X.ntActCell(withFlow[0]), hn = X.ntActCell(noFlow[0]);
    if (hw.indexOf('撤销付款') < 0) throw new Error('有生效流水的行没给「撤销付款」按钮');
    if (hn.indexOf('撤销付款') >= 0) throw new Error('没有流水的行也给了「撤销付款」—— 空点按钮');
    /* i8 行**永远不给**编辑 / 删除（源数据只读铁律） */
    if (hw.indexOf('ntEdit') >= 0 || hw.indexOf('ntDel') >= 0) throw new Error('i8 行给了编辑/删除（源数据只读被破坏）');
  });
  guard('操作列｜「撤销付款」单击直连 `revDlg`：仍走原撤销链路（原因必填 + 留痕 + 已付金额回退）', () => {
    rollback();
    const n = X.NO.filter(x => !x.manual && X.ntHasFlow(x))[0];
    const live0 = X.FLs.filter(f => f.nid === n.id && !f.voided);
    if (live0.length !== 1) throw new Error('样本前提：该行应恰好 1 条生效流水（多条走跳转分流）');
    const before = X.paidOf(n.id);
    X.ACT.ntRevoke({ dataset: { id: n.id }, tagName: 'BUTTON' });
    /* 打开了撤销弹窗（渲染面有「撤销原因」），且**还没**改数据 */
    if (String(doc.querySelector('#modalRoot').innerHTML).indexOf('撤销原因') < 0) throw new Error('没开撤销弹窗');
    if (X.paidOf(n.id) !== before) throw new Error('只是打开弹窗，就已改了已付金额');
    /* 空原因 ⇒ 拦截（撤销留痕铁律） */
    doc.querySelector('#rReason').value = '   ';
    X.ACT.revOk({ dataset: { fid: live0[0].id }, tagName: 'BUTTON' });
    if (X.FLs.find(f => f.id === live0[0].id).voided) throw new Error('空原因竟然撤销成功了');
    /* 填了原因 ⇒ 撤销生效 + 已付金额回退（走的是同一套 revOk） */
    doc.querySelector('#rReason').value = '测试撤销';
    X.ACT.revOk({ dataset: { fid: live0[0].id }, tagName: 'BUTTON' });
    const f = X.FLs.find(f => f.id === live0[0].id);
    if (!f.voided || f.reason !== '测试撤销') throw new Error('撤销没生效 / 没留原因');
    if (X.paidOf(n.id) !== X.N2(before - f.amt)) throw new Error('已付金额没回退');
    X.ACT.closeModal();
  });
  guard('操作列｜「撤销付款」多条流水时**分流到流水页并只筛该单**（不做一次撤全部）', () => {
    rollback();
    /* 给某条 i8 行补第二条生效流水，构造"多条" */
    const n = X.NO.filter(x => !x.manual && X.ntHasFlow(x))[0];
    X.FLs.push(Object.assign({}, X.FLs.find(f => f.nid === n.id && !f.voided), { id: 'F_TMP_2', amt: 100 }));
    const live1 = X.FLs.filter(f => f.nid === n.id && !f.voided);
    if (live1.length < 2) throw new Error('样本前提：构造后应有 ≥2 条生效流水');
    X.ACT.ntRevoke({ dataset: { id: n.id }, tagName: 'BUTTON' });
    /* 没开撤销弹窗（分流而不是直接撤），且流水页筛选关键词被设成该单编码 */
    if (X.flf.q !== (n.code || '')) throw new Error('没有把流水页关键词筛成该单：' + JSON.stringify(X.flf.q));
    if (X.FLs.filter(f => f.nid === n.id && !f.voided).length !== live1.length) throw new Error('多条时竟然直接撤了（应分流让人逐条撤）');
  });
  guard('操作列｜「查看关联」是**纯只读**：不改任何数据、不改任何状态', () => {
    rollback();
    const n = X.NO.filter(x => X.ntHasLink(x))[0];
    if (!n) throw new Error('样本前提：需存在已关联集采合同的行');
    const snap = JSON.stringify({ sup: n.sup, sp: n.sp, ss: n.ss, ap: n.approve, trail: n.trail.length,
      jc: X.JCs.map(j => (j.payments || []).length), fl: X.FLs.length });
    X.ACT.ntTrace({ dataset: { id: n.id }, tagName: 'BUTTON' });
    const html = String(doc.querySelector('#modalRoot').innerHTML);
    if (html.indexOf('只读') < 0) throw new Error('弹窗没声明"只读"');
    if (html.indexOf('付款流水') < 0) throw new Error('弹窗没列付款流水（去向的核心内容）');
    const after = JSON.stringify({ sup: n.sup, sp: n.sp, ss: n.ss, ap: n.approve, trail: n.trail.length,
      jc: X.JCs.map(j => (j.payments || []).length), fl: X.FLs.length });
    X.ACT.closeModal();
    if (snap !== after) throw new Error('「查看关联」改动了数据 —— 它必须是只读');
  });
  guard('操作列｜按钮出场规则：手动行有编辑/删除、i8 行没有；查看关联仅在有内容时出', () => {
    rollback();
    /* ⚠️ 演示数据里**没有手动行**（都是 i8 抓取行）⇒ 自造一条，才能验"手动行才有编辑/删除"。
       自造而非改演示数据：手动行是**用户操作产生**的，不该预置进样本（也免得污染别人的期望值）。 */
    const man = Object.assign({}, X.NO.find(x => !x.manual), { id: 'MN_TMP', manual: true, code: 'TMP-MAN' });
    X.NO.push(man);
    const hm = X.ntActCell(man);
    if (hm.indexOf('ntEdit') < 0 || hm.indexOf('ntDel') < 0) throw new Error('手动行缺编辑/删除');
    /* i8 行的无关联无流水 ⇒ 应为占位「—」 */
    const bare = X.NO.filter(n => !n.manual && !X.ntHasFlow(n) && !X.ntHasLink(n));
    if (bare.length) {
      const hb = X.ntActCell(bare[0]);
      if (hb.indexOf('btn') >= 0) throw new Error('无任何可操作内容的行仍渲染了按钮：' + hb);
    }
    if (typeof X.ntActCell !== 'function') throw new Error('ntActCell 未导出');
  });
  guard('操作列｜新增三个动作都已定义（ntRevoke / ntTrace，且 ntActCell 是唯一出口）', () => {
    ['ntRevoke', 'ntTrace'].forEach(a => { if (typeof X.ACT[a] !== 'function') throw new Error('动作 ' + a + ' 未定义'); });
    /* 渲染面确实用到 ntActCell（不是"定义了但没接线"） */
    rollback();
    const h = String(X.V.m03());
    if (h.indexOf('data-act="ntRevoke"') < 0 && h.indexOf('data-act="ntTrace"') < 0 && h.indexOf('data-act="ntEdit"') < 0)
      throw new Error('V.m03 渲染面没接 ntActCell（定义了没接线）');
  });

  /* ===== §4.2.7 再次导入的合并（方案乙）===== */
  guard('§4.2.7｜未手改的统计金额**跟随**新审批金额（i8 把审批调大 ⇒ 统计值跟着走，不留旧值）', () => {
    rollback();
    const n = X.NO.find(x => x.id === 'N08');           /* impDemoAp 对 N08 返回 approve+20000 */
    if (!n) throw new Error('样本前提：需有 N08');
    /* 前提：N08 **没有**统计字段的留痕（= 未手改） */
    if (X.impManSS(n) || X.impManSP(n)) throw new Error('样本前提：N08 不应有统计字段留痕');
    const oldAp = n.approve, newAp = X.N2(n.approve + 20000);
    n.ss = oldAp; n.sp = oldAp;                          /* 造出"旧默认值 = 旧审批金额"的初始态 */
    const msgs = X.impMerge(n, { approve: newAp, pay: n.pay });
    if (msgs.length) throw new Error('未手改不该产生越界提醒');
    if (X.N2(n.approve) !== newAp) throw new Error('审批金额没跟随 i8 新值');
    if (X.N2(n.ss) !== newAp || X.N2(n.sp) !== newAp) throw new Error('未手改的统计金额没跟随新上限：' + n.ss + '/' + n.sp);
  });
  guard('§4.2.7｜**已手改的统计金额保留人工值**（不自动改写业务判断），越界则挂提醒', () => {
    rollback();
    const n = X.NO.find(x => x.id === 'N05');           /* impDemoAp 对 N05 返回 approve-10000 */
    if (!n) throw new Error('样本前提：需有 N05');
    /* 造出"人工手改过统计结算金额"的留痕（这就是「是否手改」的唯一事实来源） */
    const hand = X.N2(n.approve);                        /* 人工值 = 原审批金额 */
    n.ss = hand;
    X.pushTrail ? X.pushTrail(n.trail, { obj: n.code, field: '统计结算金额', before: hand, after: hand }) : null;
    if (!X.impManSS(n)) throw new Error('前置失败：留痕没造出来（impManSS 判据不通）');
    const newAp = X.N2(n.approve - 10000);
    const msgs = X.impMerge(n, { approve: newAp, pay: n.pay });
    if (!msgs.length) throw new Error('人工值越界了却**没有**提醒');
    if (X.N2(n.ss) !== hand) throw new Error('人工值被自动改写了（方案乙要求保留）：' + n.ss + ' ≠ ' + hand);
    if (!X.impHasWarn(n)) throw new Error('越界没挂 IMP_WARN 提醒');
    if (X.N2(n.approve) !== newAp) throw new Error('审批金额（源字段）没跟随 i8 新值');
  });
  guard('§4.2.7｜判据 = 留痕：**没留痕就跟随、有留痕就保留**（同一字段两种命运，靠数据而非开关区分）', () => {
    rollback();
    const a = X.NO.find(x => x.id === 'N08'), b = X.NO.find(x => x.id === 'N09');
    if (!a || !b) throw new Error('样本前提：需有 N08 / N09');
    a.ss = a.approve;                                    /* A：不造留痕 ⇒ 应跟随 */
    b.ss = X.N2(b.approve - 5000);                       /* B：造留痕 ⇒ 应保留 */
    X.pushTrail ? X.pushTrail(b.trail, { obj: b.code, field: '统计结算金额', before: b.approve, after: b.ss }) : null;
    if (X.impManSS(a)) throw new Error('样本前提：A 不应有留痕');
    if (!X.impManSS(b)) throw new Error('样本前提：B 应有留痕（否则这条断言没有区分力）');
    const nApA = X.N2(a.approve + 1000), nApB = X.N2(b.approve - 8000);
    X.impMerge(a, { approve: nApA, pay: a.pay });
    X.impMerge(b, { approve: nApB, pay: b.pay });
    if (X.N2(a.ss) !== nApA) throw new Error('无留痕（未手改）却保留了旧值：' + a.ss + ' ≠ ' + nApA);
    if (X.N2(b.ss) !== X.N2(b.approve + 8000 - 8000 - 0) && X.N2(b.ss) !== X.N2(nApB + 3000))
      throw new Error('有留痕（已手改）却没保留人工值：' + b.ss);
  });
  guard('§4.2.7｜审批金额**没变**时 impMerge 什么都不做（不制造假动作）', () => {
    rollback();
    const n = X.NO.find(x => x.id === 'N08');
    const ss0 = n.ss, sp0 = n.sp, ap0 = n.approve;
    const msgs = X.impMerge(n, { approve: ap0, pay: n.pay });
    if (msgs.length) throw new Error('值没变却报了提醒');
    if (n.ss !== ss0 || n.sp !== sp0 || n.approve !== ap0) throw new Error('值没变却改写了字段');
  });
  console.log('\n--- 10d. §4.2.7 再次导入合并 / i8 已撤单 ---');
  guard('§4.2.7｜「i8 已撤单」是**标记保留、不硬删**（IMP_GONE 承载，行仍在 NO 里）', () => {
    rollback();
    const n = X.NO.find(x => x.id === 'N19');
    if (!n) throw new Error('样本前提：需有 N19');
    const cnt = X.NO.length;
    X.ACT.fetchNtOk({ dataset: {}, tagName: 'BUTTON' });   /* 走真实动作入口（不是内部函数） */
    if (X.NO.length !== cnt) throw new Error('撤单竟然硬删了行（必须保留可查）');
    if (!X.impHasGone(n)) throw new Error('i8 已撤单没被标记');
  });

  /* ===== §4.2.7 i8 撤单处置（2026-09-14 定案口径）=====
     ⚠️ 本组全部**从动作进去**（`ACT.fetchNtOk` 触发撤单），**不直接改 IMP_GONE**
        —— 直接改内部状态会绕过被测动作（把动作分支改成失效也照样绿，本项目已踩过）。
     ⚠️ 每条都先 `rollback()` 自备干净基线，且**独立算**期望值（不借被测对象自己的派生函数自证）。 */
  guard('§4.2.7 撤单①｜撤单行**退出统计**：有效行数 / 台账 Σ统计结算 / 渲染面计数**都要变**，且幅度独立可算', () => {
    rollback();
    /* 样本 = 演示里**无牵涉**的撤单行 N24（N19 有付款流水 ⇒ 归 ② 用；两者分属不同分叉） */
    const n = X.NO.find(x => x.id === 'N24');
    if (!n) throw new Error('样本前提：需有 N24');
    if (X.paidOf(n.id) > 0 || X.jcRefOf(n.id)) throw new Error('样本前提失败：N24 应无牵涉');
    if (n.excl) throw new Error('样本前提失败：N24 应为未剔除行');
    if (!(X.N2(n.ss) > 0)) throw new Error('样本前提失败：N24 的统计结算金额应 > 0（否则没有可观测的位移）');
    /* ⚠️ 选**确实会随撤单位移**的独立量；刻意**不用「辅材欠款总额」**（= Σ(ss−sp)）：
       N24 的 ss == sp ⇒ 差额 0 ⇒ 把「退出统计」改坏也照样绿（正是本项目反复踩的「数据凑巧等值」假绿温床）。 */
    const live0 = X.ntLiveRows().length;
    const in0 = X.NO.filter(x => X.ntLive(x)).length;            /* 独立算，不用 ntLiveRows 的返回 */
    const ym = X.ntYm(n), key = X.ntProjKey(n);
    const st0 = X.ledSettle('辅材', key, ym);
    if (!(st0 >= n.ss)) throw new Error('样本前提失败：ledSettle 应含该行（否则观测不到位移）');
    X.ACT.fetchNtOk({ dataset: {}, tagName: 'BUTTON' });
    if (!X.ntVoid(n)) throw new Error('前置失败：动作没把 N24 标成撤单');
    if (X.ntVoidJoint(n)) throw new Error('样本前提失败：N24 不应有牵涉');
    /* ① 有效行数 -1（两条独立路径必须一致） */
    if (X.NO.filter(x => X.ntLive(x)).length !== in0 - 1) throw new Error('有效行数没 -1（撤单行没退出统计）');
    if (live0 - X.ntLiveRows().length !== 1) throw new Error('ntLiveRows 口径与独立计数不一致');
    /* ② 台账「其他支出」Σ统计结算 恰好少掉该行的 ss（独立算，不借被测函数自证） */
    const st1 = X.ledSettle('辅材', key, ym);
    if (X.N2(st0 - st1) !== X.N2(n.ss)) throw new Error('ledSettle 没按该行 ss 退出：少了 ' + X.N2(st0 - st1) + '，应 ' + n.ss);
    /* ③ 渲染面「有效 N 条」计数同步（走 V.m03 出口 ⇒ 证明导出面也用了同一口径） */
    clearPick(); const F = X.fNtState();
    F.cat = '全部'; F.month = '全部'; F.projs = []; F.astat = '全部'; F.stat = '全部';
    const h = String(X.V.m03());
    const shown = Number((h.match(/有效 (\d+) 条/) || [])[1]);
    if (!(shown > 0)) throw new Error('渲染面没解析出「有效 N 条」计数（标记变了？）');
    if (shown !== X.NO.filter(x => X.ntLive(x)).length) throw new Error('渲染面有效条数 ' + shown + ' ≠ 独立计数 ' + X.NO.filter(x => x.ntLive(x)).length);
  });
  guard('§4.2.7 撤单②｜有牵涉 **硬拦**：挂了付款流水的撤单行**仍算有效**（不许静默退场），且渲染面带警示', () => {
    rollback();
    /* 样本 = N19（演示数据里它**本来就挂了一条生效流水 F9** ⇒ 天然是"有牵涉"样本） */
    const n = X.NO.find(x => x.id === 'N19');
    if (!n) throw new Error('样本前提：需有 N19');
    if (!(X.paidOf(n.id) > 0)) throw new Error('样本前提失败：N19 应已挂生效付款流水（否则这条断言无区分力）');
    const in0 = X.NO.filter(x => X.ntLive(x)).length;
    const d0 = X.debts();
    X.ACT.fetchNtOk({ dataset: {}, tagName: 'BUTTON' });
    if (!X.ntVoid(n)) throw new Error('前置失败：动作没把 N19 标成撤单');
    if (!X.ntVoidJoint(n)) throw new Error('有付款流水却没判成"有牵涉"（ntVoidJoint 失效）');
    if (!X.ntLive(n)) throw new Error('有牵涉的撤单行竟然退出了统计（应硬拦、仍算有效）');
    if (X.NO.filter(x => X.ntLive(x)).length !== in0 - 1) throw new Error('有牵涉时有效行数少得不对（N24 应退场、N19 应留下）');
    /* 渲染面：必须出现警示（有牵涉 = 「⚠ 撤单有牵涉」，且带处置指引） */
    clearPick(); X.fNtState().cat = '全部'; X.fNtState().month = '全部';
    const h = String(X.V.m03());
    if (h.indexOf('撤单有牵涉') < 0) throw new Error('有牵涉的撤单行没在渲染面挂警示');
    if (h.indexOf('请先撤销付款') < 0 && h.indexOf('解绑关联') < 0) throw new Error('警示里没有"请先撤销付款 / 解绑关联"的处置指引');
  });
  guard('§4.2.7 撤单③｜**无牵涉才允许退场**：无流水无关联的撤单行 ⇒ 退出统计（与②对照，两条各有区分力）', () => {
    rollback();
    const n = X.NO.find(x => x.id === 'N24');
    if (!n) throw new Error('样本前提：需有 N24');
    if (X.paidOf(n.id) > 0) throw new Error('样本前提失败：N24 不该有付款流水');
    if (X.jcRefOf(n.id)) throw new Error('样本前提失败：N24 不该有集采关联');
    X.ACT.fetchNtOk({ dataset: {}, tagName: 'BUTTON' });
    if (!X.ntVoid(n)) throw new Error('前置失败：动作没把 N24 标成撤单');
    if (X.ntVoidJoint(n)) throw new Error('无牵涉却判成有牵涉（假阳性）');
    if (X.ntLive(n)) throw new Error('无牵涉的撤单行没退出统计');
    /* 对照组：N19（有牵涉）**必须仍有效** —— 证明本条判据不是"撤单永远退出统计"这种傻断言 */
    const j = X.NO.find(x => x.id === 'N19');
    if (!X.ntLive(j)) throw new Error('对照失败：有牵涉的 N19 也退出了统计（判据没有区分力）');
  });
  guard('§4.2.7 撤单④｜**i8 行无删除入口**：i8 抓取行（含撤单行）的 `ntActCell` 一律不含 `ntDel`', () => {
    rollback();
    const n = X.NO.find(x => x.id === 'N19');
    if (!n || n.manual) throw new Error('样本前提：需有非手动的 N19');
    /* 撤单前 */
    if (X.ntActCell(n).indexOf('ntDel') >= 0) throw new Error('i8 行竟然有删除入口（i8 行永不删、源数据只读）');
    X.ACT.fetchNtOk({ dataset: {}, tagName: 'BUTTON' });
    if (!X.ntVoid(n)) throw new Error('前置失败：动作没把 N19 标成撤单');
    /* 撤单后 —— 撤单行**也不得**出现删除入口（排除撤单靠「退出统计」，不靠删除） */
    if (X.ntActCell(n).indexOf('ntDel') >= 0) throw new Error('撤单行竟然有删除入口（用户已裁定：不做删除按钮）');
    /* 对照：手动行**仍有**删除（证明判据不是"ntDel 永远不出现"这种傻断言） */
    const man = Object.assign({}, n, { id: 'MN_TMP2', manual: true, code: 'TMP-MAN2' });
    if (X.ntActCell(man).indexOf('ntDel') < 0) throw new Error('对照失败：手动行反而没了删除入口（判据没有区分力）');
  });
  guard('§4.2.7 撤单⑤｜撤单行**默认隐藏**、切「分类 = 剔除」**可查**（并进剔除档、按来源分档、不新增枚举值）', () => {
    rollback();
    const n = X.NO.find(x => x.id === 'N24');
    if (!n) throw new Error('样本前提：需有 N24');
    /* ⚠️ 判据独立：`ENUMS.cat` 的值域**不得因撤单而变化**（用户选的甲案 = 并入剔除档，不新增枚举值） */
    const catsBefore = X.enumVals('cat').slice().sort().join(',');
    X.ACT.fetchNtOk({ dataset: {}, tagName: 'BUTTON' });
    if (!X.ntVoid(n)) throw new Error('前置失败：动作没把 N24 标成撤单');
    if (X.enumVals('cat').slice().sort().join(',') !== catsBefore) throw new Error('撤单改动引入了新的分类枚举值（应并入「剔除」档）');
    /* 默认档（分类 = 全部）：撤单行**不可见** */
    clearPick(); const F = X.fNtState();
    F.cat = '全部'; F.month = '全部'; F.projs = []; F.astat = '全部'; F.stat = '全部';
    if (X.ntHit(F).some(x => x.id === n.id)) throw new Error('撤单行在「分类 = 全部」下仍可见（应默认隐藏）');
    /* 切到「分类 = 剔除」：**可查**，且渲染面给的是**撤单专属**标签（与「剔除」不相混） */
    F.cat = '剔除';
    if (!X.ntHit(F).some(x => x.id === n.id)) throw new Error('切到「分类 = 剔除」也查不到撤单行');
    const h = String(X.V.m03());
    if (h.indexOf('i8 已撤单') < 0) throw new Error('渲染面没有撤单来源标识（并进了剔除档却没按来源分档）');
    /* 分档验证：该视图里剔除行显示「剔除」、撤单行显示「i8 已撤单」——两者标签不同 */
    const exRow = X.NO.filter(x => x.excl)[0];
    if (exRow && X.ntArchTag(exRow).indexOf('剔除') < 0) throw new Error('剔除行的来源标签没显示「剔除」');
    if (X.ntArchTag(n).indexOf('i8 已撤单') < 0) throw new Error('撤单行的来源标签不是「i8 已撤单」');
  });

  /* ===== §4.6 付款通知书批量打印（API-07 · DEV-P-07）—— 2026-09-14 新增出口 =====
     口径出处：§4.6 场景五（REQ-R6）· `API-07` · `DEV-P-07`（**非阻塞项**）：
     **勾选通知书 → 人工点击 → 调 i8 接口批量打印**；⛔ **不做自建打印模板**、接口不可用即砍功能。
     ⚠️ 所以本组里有一条断言钉的不是功能、是**范围裁定**：「不得调 window.print()」。 */
  console.log('\n--- 10e. §4.6 批量打印（`API-07` / `DEV-P-07`）---');
  guard('§4.6｜「批量打印」入口存在，且**未勾选时先禁用**（R14 式「先禁用」而不是点了才拦）', () => {
    rollback(); resetF(); clearPick();
    const h0 = String(X.V.m03());
    if ((h0.match(/data-act="ntPrint"/g) || []).length !== 1) throw new Error('渲染面「批量打印」按钮不是恰好 1 个');
    if (!/data-act="ntPrint"[^>]*\bdisabled\b/.test(h0)) throw new Error('一条都没勾选时，按钮没有禁用');
    pick('N01');                                       /* 走真实动作勾一条 */
    if (/data-act="ntPrint"[^>]*\bdisabled\b/.test(String(X.V.m03()))) throw new Error('勾选后按钮仍禁用 —— 断言失去区分力');
    resetF(); clearPick();
  });

  guard('§4.6｜「批量打印」= 把勾选的通知书交给 i8 接口（API-07）：反馈里**接口名 / 条数 / 单据号 / 模拟**齐全', () => {
    rollback(); resetF(); clearPick();
    const ids = ['N01', 'N02']; ids.forEach(pick);
    const cap = []; const orig = doc.body.appendChild;
    doc.body.appendChild = el => { cap.push(String(el.innerHTML)); };
    try { X.ACT.ntPrint({ dataset: {}, tagName: 'BUTTON' }); }
    finally { doc.body.appendChild = orig; }
    const txt = cap.join(' ').replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
    if (!txt) throw new Error('点「批量打印」没有任何反馈');
    if (txt.indexOf('API-07') < 0) throw new Error('反馈里没点名调的是哪个 i8 接口（应含「API-07」）：' + txt);
    if (!/i8/.test(txt)) throw new Error('反馈里没说是调 i8 接口：' + txt);
    if (txt.indexOf('模拟') < 0) throw new Error('原型未标「模拟」（会让人误以为真调了接口）：' + txt);
    if (!/共\s*2\s*条/.test(txt)) throw new Error('反馈里的条数 ≠ 勾选数（勾了 2 条）：' + txt);
    ids.forEach(i => { const c = X.NO.find(n => n.id === i).code;
      if (txt.indexOf(c) < 0) throw new Error('反馈里没列出将打印的单据号 ' + c + '：' + txt); });
    resetF(); clearPick();
  });

  guard('⭐ DEV-P-07｜「批量打印」**不得调 window.print()**（那是「自建打印模板」，正撞范围裁定）', () => {
    rollback(); resetF(); clearPick(); pick('N01');
    const before = PRINT_CALLS.length;
    X.ACT.ntPrint({ dataset: {}, tagName: 'BUTTON' });
    if (PRINT_CALLS.length !== before) throw new Error('「批量打印」调了 window.print() —— 本系统只准把勾选交给 i8 接口，不准自建打印模板（DEV-P-07）');
    /* 对照：**手工触发一次 window.print()** —— 证明探针抓得住、不是空转。
       ⚠️ 2026-09-14 改法：原先借「活动大表 A3 打印」当合法样本，**该功能已取消** ⇒ 改为"自给自足"，
          **不再把"探针有效性"绑在某个业务功能是否存在上**（本次正是吃了这个亏）。 */
    ctx.window.print();
    if (PRINT_CALLS.length === before) throw new Error('探针失效：手工触发的 window.print() 也没被抓到 ⇒ 该断言失去区分力');
    resetF(); clearPick();
  });

  guard('§4.6｜「批量打印」**不动勾选**（打印不改数据 = 非消费型动作，与「付款」这种消费型动作有意不同）', () => {
    rollback(); resetF(); clearPick();
    ['N01', 'N02'].forEach(pick);
    const n0 = X.pickSet.size;
    if (n0 !== 2) throw new Error('前置失败：应勾上 2 条，实际 ' + n0);
    X.ACT.ntPrint({ dataset: {}, tagName: 'BUTTON' });
    if (X.pickSet.size !== n0) throw new Error('打印后勾选被清空了（' + n0 + ' → ' + X.pickSet.size + '）—— 打印不该动勾选');
    resetF(); clearPick();
  });

  guard('§4.2.7｜**撤单行一律不可勾选**（含"有牵涉"那种）；对照：剔除行**必须可勾**（它是「恢复剔除」的前提）、正常行必须可勾', () => {
    rollback(); resetF(); clearPick();
    X.ACT.fetchNtOk({ dataset: {}, tagName: 'BUTTON' });     /* 标 N19（有牵涉）+ N24（无牵涉） */
    const n19 = X.NO.find(n => n.id === 'N19'), n24 = X.NO.find(n => n.id === 'N24');
    if (!n19 || !n24) throw new Error('样本前提：需有 N19 / N24');
    if (!(X.ntVoid(n19) && X.ntVoidJoint(n19))) throw new Error('前置失败：N19 应为「撤单且有牵涉」');
    if (!(X.ntVoid(n24) && !X.ntVoidJoint(n24))) throw new Error('前置失败：N24 应为「撤单且无牵涉」');
    const ex0 = X.NO.filter(x => x.excl)[0];
    if (!ex0) throw new Error('样本前提：需要一个剔除行做对照');
    const ok0 = X.NO.filter(n => X.ntPayCand(n))[0];
    if (!ok0) throw new Error('样本前提：需要一条正常行做对照（否则"全体禁用"也能通过）');
    const F = X.fNtState();
    const bak = { m: F.month, c: F.cat, a: F.astat, s: F.stat, p: F.projs.slice() };
    const setF = (c) => { F.month = '全部'; F.cat = c; F.astat = '全部'; F.stat = '全部'; F.projs.length = 0; };
    try {
      setF('剔除');                                        /* 撤单行只在「分类 = 剔除」档可见 */
      const h = String(X.V.m03());
      const chk = (id, s) => { const m = s.match(new RegExp('<input[^>]*data-act="pick"[^>]*data-id="' + id + '"[^>]*>')); return m ? m[0] : ''; };
      if (!chk('N19', h)) throw new Error('渲染面找不到 N19 的勾选框（「分类 = 剔除」档应能看到撤单行）');
      if (!/\bdisabled\b/.test(chk('N19', h))) throw new Error('「撤单有牵涉」的行**仍可勾选** —— 它不该进付款链（§4.2.7 的出路是"先撤销付款 / 解绑关联"）');
      if (!/\bdisabled\b/.test(chk('N24', h))) throw new Error('无牵涉的撤单行**不该**可勾选（它已退出统计）');
      /* ⭐⭐ 2026-09-21 改（**用户报障** ⇒ 用户裁定优先）：剔除行**必须可勾**。
         原先这条要求"剔除行同样 disabled"，理由是"它已退出统计" —— 那是把 §4.2.2 的
         「**退出统计**」延伸成了「不可勾选」，而「恢复剔除」这条动作恰恰要求
         「**必须先勾选**」（`ACC-PAY-CAT-001/001-10`）⇒ 两条规矩**互锁**，剔除根本恢复不了。
         ⭐ 澄清：**勾选 ≠ 进付款批次** —— 勾选集服务「批量付款」与「恢复剔除」两件事；
            进不进付款批次由 `batchPay` / `batchPayOk` 那道闸管（下面那条 guard 就是它）。
         ⚠️ **撤单行那两条不变**（N19 / N24 仍必须 disabled）：撤单是终态、没有"恢复"这回事。 */
      if (/\bdisabled\b/.test(chk(ex0.id, h))) throw new Error('剔除行被禁用了勾选 ⇒ 「恢复剔除」无路可走（它必须能勾；能否付款是另一道闸）');
      setF('全部');                                        /* 正常行只在默认档可见 */
      const c2 = chk(ok0.id, String(X.V.m03()));
      if (!c2) throw new Error('默认档里找不到正常行 ' + ok0.id + ' 的勾选框');
      if (/\bdisabled\b/.test(c2)) throw new Error('正常行**居然被禁用勾选** —— 该断言失去区分力（"全体禁用"也能通过）');
    } finally {
      Object.assign(F, { month: bak.m, cat: bak.c, astat: bak.a, stat: bak.s }); F.projs.length = 0; bak.p.forEach(v => F.projs.push(v));
      resetF(); clearPick();
    }
  });

  /* ===== ⭐ 付款链的准入闸（2026-09-14 定案 · 甲案）：凡"勾选 → 付款"的入口一律排除撤单行 =====
     由来（实测）：撤单开放勾选后，`pickAll` 会把「撤单但有牵涉」的行勾进去、而 `batchPay` 不拦
     ⇒ 能给一张 **i8 已作废的单**生成新的付款流水，与 §4.2.7「先撤销付款 / 解绑关联」方向相反。 */
  guard('§4.2.7｜**全选不勾撤单行**（含"有牵涉"那种）；对照：同档里的正常行必须在勾选集里', () => {
    rollback(); resetF(); clearPick();
    X.ACT.fetchNtOk({ dataset: {}, tagName: 'BUTTON' });
    const F = X.fNtState();
    const bak = { m: F.month, c: F.cat, a: F.astat, s: F.stat, p: F.projs.slice() };
    F.month = '全部'; F.cat = '全部'; F.astat = '全部'; F.stat = '全部'; F.projs.length = 0;
    try {
      const voids = X.NO.filter(n => X.ntVoid(n)).map(n => n.id);
      if (!voids.length) throw new Error('样本前提：当前没有撤单行');
      X.ACT.pickAll({ tagName: 'INPUT', checked: true });
      const leaked = voids.filter(id => X.pickSet.has(id));
      if (leaked.length) throw new Error('全选把撤单行勾进来了：' + leaked.join(','));
      const cands = X.ntHit(F).filter(n => X.ntPayCand(n)).map(n => n.id);
      if (!cands.length) throw new Error('该档里没有正常行 —— 断言失去区分力');
      if (!cands.some(id => X.pickSet.has(id))) throw new Error('正常行一条都没勾上 —— 断言失去区分力');
      /* ⭐ 全选框状态必须与 `pickAll` **同源**：全勾满后不得停在"半选"（不同源就会永久半选）。
         ⚠️ 这里**显式调 `BIND.m03()`** —— 它正常由 `render()` 触发，但断言里 `VIEW` 未必停在 m03，
         直接读 `#pickAllBox` 会读到"从没被写过"的默认值（实测：首版就是这么假绿的）。 */
      X.BIND.m03();
      const box = doc.querySelector('#pickAllBox');
      if (box.indeterminate) throw new Error('全勾满后全选框仍停在"半选"态 —— 全选候选与 pickAll 不是同一出口');
      if (box.checked !== true) throw new Error('全勾满后全选框没显示为选中');
    } finally {
      Object.assign(F, { month: bak.m, cat: bak.c, astat: bak.a, stat: bak.s }); F.projs.length = 0; bak.p.forEach(v => F.projs.push(v));
      resetF(); clearPick();
    }
  });

  guard('§4.2.7｜**付款窗口排除撤单行**（走 `batchPay`）：即使被硬塞进勾选集也不得进付款批次，且必须**明说排除**', () => {
    rollback(); resetF(); clearPick();
    X.ACT.fetchNtOk({ dataset: {}, tagName: 'BUTTON' });
    const n19 = X.NO.find(n => n.id === 'N19');
    if (!(X.ntVoid(n19) && X.ntVoidJoint(n19))) throw new Error('前置失败：N19 应为「撤单且有牵涉」');
    const ok0 = X.NO.filter(n => X.ntPayCand(n) && n.astat === '已批' && X.payEff(n) > 0)[0];
    if (!ok0) throw new Error('样本前提：需要一条**正常且可付**的行做对照');
    /* ⭐ 刻意**绕过勾选框**直接塞进勾选集 —— 模拟"勾上之后才被标撤单"的状态错位（兜底要防的就是它） */
    X.pickSet.add(n19.id); X.pickSet.add(ok0.id);
    X.ACT.batchPay();
    const h = doc.querySelector('#modalRoot').innerHTML || '';
    X.ACT.batchPayCancel();
    /* ⚠️ 判据必须**行级**：排除提示里**本来就会列出**被排除单据号 ⇒ 全文 grep 该单号会假红
       （实测踩过：首版就是全文 grep，结果"排除了"却报"进了付款窗口"） */
    /* ⚠️ 表体上**会带属性**（如 `data-vs`）⇒ 必须按 **`<tbody` 前缀**切，⛔ 不能带 `>`：
       带 `>` 时这句切不到、会退化成"拿最后 1 个字符当行集"（整条断言失去区分力、且不报错）。
       ⭐ 本断言要钉的是"逐行看有没有那条单据" —— 与表体上挂什么属性无关。 */
    const _tbs = h.indexOf('<tbody');
    const rowsHtml = (_tbs >= 0 ? h.slice(_tbs) : '').split('<tr ').slice(1);
    if (rowsHtml.some(s => s.indexOf(n19.code) >= 0)) throw new Error('撤单行 ' + n19.code + ' 被渲染成了付款行（应被排除）');
    if (!rowsHtml.some(s => s.indexOf(ok0.code) >= 0)) throw new Error('正常行 ' + ok0.code + ' 没进付款窗口 —— 断言失去区分力');
    if (h.indexOf('已自动排除') < 0) throw new Error('排除了却**不提示** —— 静默丢行比报错更难查');
    resetF(); clearPick();
  });

  guard('§4.2.7｜**提交闸**：勾选集里只剩撤单行时，「确认付款」必须走"没有可付款的记录"（**不得为它写流水**）', () => {
    rollback(); resetF(); clearPick();
    X.ACT.fetchNtOk({ dataset: {}, tagName: 'BUTTON' });
    const n24 = X.NO.find(n => n.id === 'N24');   /* 撤单 + 无牵涉 + 本次应付 86800（"可付"的数值条件都满足） */
    if (!X.ntVoid(n24)) throw new Error('前置失败：N24 应为撤单行');
    if (X.payEff(n24) <= 0) throw new Error('样本前提：N24 的本次应付应 > 0 —— 否则"没有可付"可能是别的原因，断言失去区分力');
    const fl0 = X.FLs.length;
    X.pickSet.add(n24.id);
    const cap = []; const orig = doc.body.appendChild;
    doc.body.appendChild = el => { cap.push(String(el.innerHTML)); };
    try { X.ACT.batchPayOk({ dataset: {}, tagName: 'BUTTON' }); }
    finally { doc.body.appendChild = orig; }
    const txt = cap.join(' ').replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
    if (X.FLs.length !== fl0) throw new Error('给「i8 已撤单」的单据写了付款流水（' + fl0 + ' → ' + X.FLs.length + '）');
    if (txt.indexOf('没有可付款的记录') < 0) throw new Error('撤单行被当成可付行往下走了（应先被排除、提示"没有可付款的记录"），实际抓到：' + txt);
    resetF(); clearPick();
  });

  guard('§4.2.7｜**按付款计划勾选也排除撤单行**（`planPick` 是第三个入口；样本 = 撤单 + 有牵涉 + **未付清**）', () => {
    rollback(); resetF(); clearPick();
    /* ⚠️ 样本必须**同时**满足三条，否则断言会被别的过滤"帮忙通过"、从而**失去区分力**：
       · 已挂集采关联（⇒ `ntVoidJoint` ⇒ 仍算 `ntLive`，不会被 `prunePick` 剔掉）
       · **未付清**（计划勾选会把付款状态置为「未付清」，已付清的行会被过滤掉）
       · 演示版付款计划里**有一行指向它**（临时把 PL04 的 docNo 改指过来，跑完还原）
       ⚠️ **实测教训**：首版拿 N19（撤单有牵涉）当样本 —— 它**已付清** ⇒ 被「未付清」过滤挡掉，
         连"漏了"都测不出来（**反向灵敏度变异变绿**才发现，这正是本项目最贵的假绿形态）。 */
    const n15 = X.NO.find(n => n.id === 'N15'), n26 = X.NO.find(n => n.id === 'N26');
    if (!n15 || !n26) throw new Error('样本前提：需有 N15 / N26');
    if (!X.jcRefOf(n15.id)) throw new Error('前置失败：N15 应有集采关联（否则它不构成 ntVoidJoint）');
    X.IMP_GONE[n15.id] = { date: n15.date, code: n15.code, doc: n15.doc };
    if (!(X.ntVoid(n15) && X.ntVoidJoint(n15))) throw new Error('前置失败：N15 标撤单后应为「有牵涉」');
    if (X.statOf(n15) !== '未付清') throw new Error('样本前提：N15 应为未付清（否则会被"未付清"过滤挡掉，断言失去区分力）');
    const pl = X.PLs.find(p => p.id === 'PL04'), bakNo = pl && pl.docNo;
    if (!pl) throw new Error('样本前提：需有 PL04');
    if (!X.plWin().open) throw new Error('前置失败：付款计划窗口未开（模拟今天应落在 10 号 → 月末）');
    pl.docNo = n15.code;
    try {
      X.ACT.planPick({ dataset: {}, tagName: 'BUTTON' });
      if (X.pickSet.has(n15.id)) throw new Error('按付款计划勾选把撤单行 ' + n15.code + ' 勾进来了（它不该进付款链）');
      if (!X.pickSet.has(n26.id)) throw new Error('计划里的正常单 N26 没勾上 —— 断言失去区分力（"一条都没勾"也能通过）');
    } finally { pl.docNo = bakNo; resetF(); clearPick(); }
  });


  guard('§4.2.7｜再次导入**不覆盖**旁路字段：分类 / 集采实际供应商 / 调整单（§4.2.4 · §9.3）', () => {
    rollback();
    const n = X.NO.find(x => x.id === 'N08');
    n.cat = '机械'; n.sup = '某人手填的供应商';        /* 造出人工值 */
    const ad0 = X.ADs.length;
    X.ACT.fetchNtOk({ dataset: {}, tagName: 'BUTTON' });
    if (n.cat !== '机械') throw new Error('再次导入覆盖了「分类」人工判断');
    if (n.sup !== '某人手填的供应商') throw new Error('再次导入覆盖了「集采实际供应商」');
    if (X.ADs.length !== ad0) throw new Error('再次导入动了调整单');
  });
  guard('§4.2.7｜越界提醒在渲染面可见（「导入提醒」标记随行出现），且**值本身未被改写**', () => {
    rollback();
    const n = X.NO.find(x => x.id === 'N05');
    const hand = X.N2(n.approve);
    n.ss = hand;
    X.pushTrail ? X.pushTrail(n.trail, { obj: n.code, field: '统计结算金额', before: hand, after: hand }) : null;
    X.ACT.fetchNtOk({ dataset: {}, tagName: 'BUTTON' });
    if (!X.impHasWarn(n)) throw new Error('走动作入口后没有挂提醒');
    if (X.N2(n.ss) !== hand) throw new Error('提醒的同时把人工值改掉了（应只提醒、不代改）');
    const h = String(X.V.m03());
    if (h.indexOf('导入提醒') < 0) throw new Error('渲染面没有「导入提醒」标记（挂了但没显示）');
  });
  guard('§4.2.7｜impDemoAp 只对 N05 / N08 给改动，其余返回 null（演示样本可控、不污染他人期望值）', () => {
    const changed = X.NO.filter(n => X.impDemoAp(n) != null).map(n => n.id).sort();
    if (changed.join(',') !== 'N05,N08') throw new Error('impDemoAp 影响面超出预期：' + changed.join(','));
  });
  guard('MOD-03｜口径说明条数标注 = 实际 <li> 数（数字与内容同源，不写死）', () => {
    rollback();
    const h = String(X.V.m03());
    /* 取「口径说明」那个 details 块，数里面的 <li>；再与标题里的「N 条」比对 */
    const block = (h.match(/<details class="tip"><summary>口径说明 · \d+ 条[\s\S]*?<\/details>/) || [''])[0];
    if (!block) throw new Error('找不到 MOD-03 的口径说明块');
    const stated = Number((block.match(/口径说明 · (\d+) 条/) || [])[1]);
    const actual = (block.match(/<li>/g) || []).length;
    if (stated !== actual) throw new Error('标注 ' + stated + ' 条 ≠ 实际 ' + actual + ' 条');
  });

  console.log('\n--- 10f. 看板页 = 待办页（8 项待办 · §3.1.3 / §4.6 / §4.3.4 / §5.8.3 / §2.5.1 / §2.4.2；⭐ TAIL-97 撤 jcPending）---');
  /* ⭐ 取把手的**唯一出口**：`data-todo="<键>" ... data-n="<数>"`。
     ⚠️ 刻意**不绑文案措辞**（改一句话不该假红）；数字一律与**数据源独立复算**比对，
       不拿原型自己的出口自证（自证 = 假绿温床）。 */
  const homeTodo = () => {
    const h = String(X.V.home());
    const keys = ['ntUnapproved', 'ownership', 'planUnmatched', 'dfPending', 'placeholder', 'fetchDue', 'fetchFail', 'printFail'];
    const out = {};
    keys.forEach(k => {
      const i = h.indexOf('data-todo="' + k + '"');
      const j = h.indexOf('data-todo="', i + 1);
      const s = i < 0 ? '' : h.slice(i, j < 0 ? h.length : j);
      const mn = s.match(/data-n="(\d+)"/), mv = s.match(/<div class="v">([^<]*)<\/div>/), ml = s.match(/data-act="go"[^>]*data-k="([^"]+)"/);
      out[k] = { seg: s, n: mn ? Number(mn[1]) : null, v: mv ? mv[1] : null, k: ml ? ml[1] : null };
    });
    return out;
  };

  guard('§5·看板｜8 项待办的把手齐全（`data-todo` 恰好 8 个、不重不漏；⭐ TAIL-97 撤 jcPending）', () => {
    const got = [...String(X.V.home()).matchAll(/data-todo="([^"]+)"/g)].map(m => m[1]);
    const want = ['ntUnapproved', 'ownership', 'planUnmatched', 'dfPending', 'placeholder', 'fetchDue', 'fetchFail', 'printFail'];
    if (got.length !== 8) throw new Error('data-todo 个数 = ' + got.length + '（应为 8）');
    if (new Set(got).size !== 8) throw new Error('data-todo 有重复：' + got.join(','));
    const miss = want.filter(k => got.indexOf(k) < 0), extra = got.filter(k => want.indexOf(k) < 0);
    if (miss.length || extra.length) throw new Error('把手集合不符 —— 缺 [' + miss.join(',') + '] / 多 [' + extra.join(',') + ']');
  });

  guard('§5·看板｜①–⑥ 数字 = 数据源**独立复算**（写死数字 / 口径漂 ⇒ 真红）', () => {
    rollback(); resetF(); clearPick();
    const T = homeTodo();
    /* ⚠️ 独立复算：本表达式**刻意不复用**原型里那份计算，各写各的（写完再互相对） */
    const exp = {
      ntUnapproved: X.NO.filter(n => X.ntLive(n) && n.astat === '未批').length,
      ownership: X.NO.filter(n => X.ntLive(n) && X.isShellFull(n.proj) && !X.ntProjKey(n)).length,
      planUnmatched: X.PLs.filter(p => X.plRev(p, X.PLs) !== '完全匹配').length,
      dfPending: X.IVs.filter(iv => X.ADs.some(a => a.ivid === iv.id)).length,
      placeholder: X.PJs.filter(p => p.name.startsWith('未建仓-')).length
    };
    Object.keys(exp).forEach(k => {
      if (T[k].n !== exp[k]) throw new Error(k + ' 的 data-n = ' + T[k].n + '，数据源复算 = ' + exp[k]);
      if (T[k].v !== String(exp[k])) throw new Error(k + ' 的可见数字（' + T[k].v + '）≠ 数据源（' + exp[k] + '）—— 把手与显示不同源');
    });
    const nz = Object.keys(exp).filter(k => exp[k] > 0);
    if (nz.length < 2) throw new Error('样本失去区分力：6 项里只有 ' + nz.length + ' 项 > 0');
  });

  guard('§3.1.3 / §4.6｜⑦⑬⑭ 全由**运行记录**推出（本月是否已抓 · 最近一次抓取失败 · 打印投递失败）', () => {
    const T = homeTodo();
    const rf = X.RUNLOG.filter(r => r.kind === '抓取'), rp = X.RUNLOG.filter(r => r.kind === '打印');
    const fDone = rf.some(r => r.at.slice(0, 7) === X.bjMonth() && r.result === '成功');
    const fFail = [...rf].reverse().find(r => r.result === '失败') || null;
    const pFail = [...rp].reverse().find(r => r.result === '失败') || null;
    if (T.fetchDue.n !== (fDone ? 0 : 1)) throw new Error('⑦「本月抓取」待办数 = ' + T.fetchDue.n + '，按运行记录应为 ' + (fDone ? 0 : 1));
    if (T.fetchFail.n !== (fFail ? 1 : 0)) throw new Error('⑬「最近一次抓取失败」待办数与运行记录不符');
    if (T.printFail.n !== (pFail ? 1 : 0)) throw new Error('⑭「打印投递失败」待办数与运行记录不符');
    /* 口径硬要求：抓取失败的提示**含表名与时间**；打印失败要能定位到单据 */
    if (fFail && (T.fetchFail.seg.indexOf(fFail.obj) < 0 || T.fetchFail.seg.indexOf(fFail.at) < 0))
      throw new Error('⑬ 提示里没同时给出「表名 + 时间」（§3.1.3 要求）：' + T.fetchFail.seg);
    if (pFail && T.printFail.seg.indexOf(pFail.obj) < 0) throw new Error('⑭ 提示里没指出是哪张单据：' + T.printFail.seg);
    if (!fFail || !pFail) throw new Error('样本失去区分力：运行记录里没有失败记录');
    /* 反面对照：⑦⑬⑭ 必须**真的**来自运行记录 —— 把本月那条失败改成成功，⑦⑬ 的预期值必须跟着变 */
    const bak = fFail.result; fFail.result = '成功';
    try {
      const rf2 = X.RUNLOG.filter(r => r.kind === '抓取');
      const fDone2 = rf2.some(r => r.at.slice(0, 7) === X.bjMonth() && r.result === '成功');
      const fFail2 = [...rf2].reverse().find(r => r.result === '失败') || null;
      if (!fDone2) throw new Error('探针失效：把本月失败改成成功后，「本月已抓」仍为假 ⇒ 该断言失去区分力');
      if (fFail2 === fFail) throw new Error('探针失效：最近一次抓取失败没跟着数据变');
    } finally { fFail.result = bak; }
  });

  guard('§5·看板｜8 项每项都「可点」：`data-act="go"` + `data-k` 是已注册视图 + 键盘可达（R13 无障碍）', () => {
    const T = homeTodo();
    Object.keys(T).forEach(k => {
      const s = T[k].seg;
      if (!s) throw new Error(k + ' 的瓦片找不到');
      if (!/data-act="go"/.test(s)) throw new Error(k + ' 没有 data-act="go"（不可点）');
      if (!T[k].k) throw new Error(k + ' 的链接缺 data-k');
      if (vk.indexOf(T[k].k) < 0) throw new Error(k + ' 指向**未注册**的视图 ' + T[k].k);
      if (!/tabindex="0"[^>]*role="button"/.test(s)) throw new Error(k + ' 的链接缺 tabindex="0" + role="button"（键盘不可达）');
    });
  });

  guard('§5·看板｜定位 = 待办页（只增不删）：欠款指标卡保留 · 状态机汇总**折叠**但内容不改 · 业务事实卡已撤', () => {
    const h = String(X.V.home());
    if (h.indexOf('待办') < 0) throw new Error('看板没有「待办」区');
    if (h.indexOf('≥ <b>审批金额</b>') < 0) throw new Error('状态机汇总里的付款状态基准丢了（H1 会红 —— 折叠时不许改内容）');
    if (!/class="kpis"/.test(h)) throw new Error('欠款指标卡（.kpis）被删了 —— 本次改造是「只增不删」');
    if (!/<details class="tip">[\s\S]*状态机汇总[\s\S]*<\/details>/.test(h)) throw new Error('状态机汇总没有折叠');
    if (h.indexOf('业务事实监测告警') >= 0) throw new Error('业务事实监测告警卡没撤（应已并入「占位行待扶正」）');
    if (h.indexOf('未建仓-01') < 0) throw new Error('⑥ 待办没引用占位行（U13 会红）');
  });

  console.log(`\n===== 业务断言：${pass} 通过 / ${fail} 失败 =====`);
  process.exit(fail ? 1 : 0);
}, 700);
