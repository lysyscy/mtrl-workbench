/* shell/ui.js —— 壳的**独立件**（`P2-a` 拆件 · 2026-09-28 · 台账 `TAIL-164`）：共用 UI 件与浮层（时间面板 / 项目工具 / 项目面板 / 浮层定位）。
 *
 * ⭐ **为什么单开一件**：「选一个项目 / 选一个时段」与浮层定位是**跨页共用**的机制（守则 §5.12 的唯一出口）⇒ 单开一件。
 *    `index.html` 原来一件套 4000 行（CSS ＋ HTML ＋ 内联脚本混装）⇒ 改一处要翻三个区
 *    （本会话两次白屏的同一个根）。本件是「**只拆非切片**」那一批里的一件。
 * ⛔ **本件不许碰**：任何 `V.<原型页>` 切片（它们**留在 `index.html`** —— 计划 §23 的口径，
 *    `ui_parity` 的 `U1` 逐行比它）· 口径判定（判定全在后端）· 界面文案的主人。
 * ⚠️ **加载顺序**：`index.html` 的 `<script src>` 顺序即真源 —— 本件排在 `actions.js` **之前**
 *    （`actions.js` / `core.js` 里有些表**加载期就求值**到本件的常量）。⛔ 别调顺序。
 * ⚠️ 本件的代码是**原样搬出**（逐字未改，含注释）；来历与搬法见计划 §15 `TAIL-164`。 */

let pickSet=new Set();
const monthEnd=m=>{const [y,mm]=m.split('-').map(Number); return m+'-'+String(new Date(y,mm,0).getDate()).padStart(2,'0');};
/* ---------- 统一「年月选择器」组件：按钮 → 年步进 + 12 宫格月，最多两次点击 ----------
   替代原生 input[type=month]（原生只支持滚轮/逐月翻，太慢）。
   全前端凡需「选时间」处一律用 tmBtn(id,{scope,val,modes}) 渲染，由 mpToggle/mpYear/mpMode/mpWQ/mpPick 驱动。 */
let mp={open:null,year:2026,mode:'',a:'',b:'',wq:''};
/* 展开态在 `PJ_OPEN`（key='pj' · `#1` 2026-09-26 收口） */
/* ⭐ 通用「时间选择器」组件（2026-09-13 重做；替掉原 `mpBtn` / `mpPanel`）
   原版缺陷：「全部月份」写在组件内部、按 `scope==='nt'` 现判 ⇒ 只有付款通知书有
   ⇒ **组件一份、能力却是散的**（违反 §八 准则 1「同一个事实只写一处」）。
   现在：**能力由调用点声明**（`cfg.modes`），**组件内部不再有任何 `scope===xxx` 分支**。
   modes：'月' · '跨月' · '年' · '季度' · '周' · '全部'
   值：`2026-09` · `2026-06~2026-07`（跨月，**只同年内**）· `2026` · `2026Q3`
       · 周 = 该周**周一**的 `YYYY-MM-DD` · 全部 = `全部`
   ⚠️ 抓取 / 付款计划导入 / 期初截止年月 **有意只声明「月」**（业务上就是"一次一个月"）——
      写进配置防"顺手统一"。 */
const tmBtn=(id,cfg)=>`<div class="mpwrap pjwrap" style="position:relative;display:inline-block">
  <button class="btn" data-act="mpToggle" data-id="${id}" data-scope="${cfg.scope}" data-val="${esc(cfg.val)}" style="min-width:118px;display:inline-flex;align-items:center;justify-content:space-between;gap:calc(8px * var(--fscale))"><span class="fc">${esc(cfg.label==null?cfg.val:cfg.label)}</span><span class="mut" style="font-size:calc(9px * var(--fscale))">▼</span></button>
  ${mp.open===id?tmPanel(id,cfg):''}</div>`;
/* ⚠️ 上面那个 `pjwrap` 是**浮层锚**（与 `.mpwrap` 并存：`.mpwrap` 是"点外面收起"的历史判据，
   `pjwrap` 才是**逃出卡片裁剪**那套机制认的锚）—— 见 `placePops()` 的注释。
   ⛔ 别删 `pjwrap`：删了时间选择器就退回"被卡片 overflow 裁"的老形态（`TAIL-110`）。 */
const tmModes={月:1,跨月:1,年:1,季度:1,周:1,全部:1};
const tmParse=v=>{ v=String(v==null?'':v);
  if(v==='全部') return {mode:'全部'};
  if(/^\d{4}Q[1-4]$/.test(v)) return {mode:'季度',y:+v.slice(0,4),q:+v.slice(5)};
  if(/^\d{4}-\d{2}~\d{4}-\d{2}$/.test(v)) return {mode:'跨月',y:+v.slice(0,4),a:v.slice(0,7),b:v.slice(8,15)};
  if(/^\d{4}-\d{2}-\d{2}$/.test(v)) return {mode:'周',y:+v.slice(0,4),mon:v};
  if(/^\d{4}-\d{2}$/.test(v)) return {mode:'月',y:+v.slice(0,4),ym:v};
  if(/^\d{4}$/.test(v)) return {mode:'年',y:+v};
  return {mode:'月',ym:v}; };
/* 时间范围判定（**各页筛选共用**，一处实现）：v 见上；d = 'YYYY-MM' 或 'YYYY-MM-DD' */
const tmIn=(v,d)=>{ const k=String(d||'').slice(0,7); v=String(v==null?'':v);
  if(!v||v==='全部') return true;
  if(/^\d{4}-\d{2}~\d{4}-\d{2}$/.test(v)) return k>=v.slice(0,7)&&k<=v.slice(8,15);
  if(/^\d{4}-\d{2}$/.test(v)) return k===v;
  if(/^\d{4}$/.test(v)) return k.slice(0,4)===v;
  return true; };
const tmLabel=v=>String(v==null?'':v)==='全部'?'全部时间':String(v).replace('~',' ~ ');
const tmStart=v=>{ const s=String(v==null?'':v);
  if(/^\d{4}-\d{2}~\d{4}-\d{2}$/.test(s)) return s.slice(0,7);
  if(/^\d{4}-\d{2}$/.test(s)) return s;
  if(/^\d{4}$/.test(s)) return s+'-01';
  return bjMonth(); };
/* 把筛选值渲染成"对应的单据日期闭区间"（只读回显用） */
const tmRange=v=>{ const s=String(v==null?'':v);
  if(!s||s==='全部') return '不限（全部时间）';
  if(/^\d{4}-\d{2}~\d{4}-\d{2}$/.test(s)) return s.slice(0,7)+'-01 ~ '+monthEnd(s.slice(8,15));
  if(/^\d{4}-\d{2}$/.test(s)) return s+'-01 ~ '+monthEnd(s);
  if(/^\d{4}$/.test(s)) return s+'-01-01 ~ '+s+'-12-31';
  return s; };
const tp2=n=>String(n).padStart(2,'0');
const tmD=t=>t.getFullYear()+'-'+tp2(t.getMonth()+1)+'-'+tp2(t.getDate());
const tmQof=d=>{ const t=new Date(d+'T00:00:00'); return t.getFullYear()+'Q'+(Math.floor(t.getMonth()/3)+1); };
const tmQNow=()=>tmQof(SYS_TODAY);
/* 某季度的全部周（**周一 ~ 周日**）→ [[周一, 周日], ...] —— 界面直接显示起止日期 */
const tmWeeksOfQ=(y,q)=>{ const out=[], last=new Date(y,q*3,0);
  const t=new Date(y,(q-1)*3,1); t.setDate(t.getDate()-((t.getDay()+6)%7));   /* 回退到该周周一 */
  for(; t<=last; t.setDate(t.getDate()+7)){ const s=new Date(t); s.setDate(s.getDate()+6); out.push([tmD(t),tmD(s)]); }
  return out; };
const tmPanel=(id,cfg)=>{
  const modes=(cfg.modes||['月']).filter(m=>tmModes[m]);
  const sc=cfg.scope, v=String(cfg.val==null?'':cfg.val), st=tmParse(v);
  const md=(mp.mode&&modes.indexOf(mp.mode)>=0)?mp.mode:(modes.indexOf(st.mode)>=0?st.mode:modes[0]);
  const y=mp.year||st.y||Number(v.slice(0,4))||2026;
  const D=(act,ds,cls,txt)=>`<button class="btn sm ${cls||''}" data-act="${act}"${Object.keys(ds).map(k=>` data-${k}="${esc(ds[k])}"`).join('')}>${txt}</button>`;
  /* 模式切换条**只在声明了 2 种以上模式时**才渲染 —— 只给「月」的调用点不该出现切换条 */
  const head=modes.length>1?`<div style="display:flex;gap:calc(4px * var(--fscale));flex-wrap:wrap;margin-bottom:calc(7px * var(--fscale))">${['月','跨月','年','季度','周','全部'].filter(m=>modes.indexOf(m)>=0)
    .map(m=>D('mpMode',{id:id,scope:sc,val:v,m:m},md===m?'pri':'',m)).join('')}</div>`:'';
  const yhead=`<div style="display:flex;align-items:center;gap:calc(6px * var(--fscale));margin-bottom:calc(7px * var(--fscale))">
      ${D('mpYear',{id:id,scope:sc,val:y,d:'-1'},'','‹')}
      <div style="flex:1;text-align:center;font-family:var(--fm);font-size:calc(13px * var(--fscale))">${y} 年</div>
      ${D('mpYear',{id:id,scope:sc,val:y,d:'1'},'','›')}</div>`;
  const grid=c=>`<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:calc(4px * var(--fscale))">${c}</div>`;
  let body='';
  if(md==='月'){
    body=yhead+grid(Array.from({length:12},(_,i)=>{const k=y+'-'+tp2(i+1);
      return D('mpPick',{id:id,scope:sc,val:k,m:'月'},k===v?'pri':'',(i+1)+'月');}).join(''));
  }else if(md==='跨月'){
    const a=mp.a||st.a||'', b=mp.b||st.b||'';
    body=yhead+`<div class="mut sm" style="margin:calc(-3px * var(--fscale)) 0 calc(6px * var(--fscale))">先点起点、再点终点（<b>只允许同一年内</b>）</div>`
      +grid(Array.from({length:12},(_,i)=>{const k=y+'-'+tp2(i+1), on=(a&&b)?(k>=a&&k<=b):(k===a);
        return D('mpPick',{id:id,scope:sc,val:k,m:'跨月'},on?'pri':'',(i+1)+'月');}).join(''))
      +`<div style="margin-top:calc(7px * var(--fscale))"><span class="pill">已选 <b>${a||'—'}</b> ~ <b>${b||'—'}</b></span></div>`;
  }else if(md==='年'){
    const ys=[]; for(let k=y-4;k<=y+4;k++) ys.push(k);
    body=`<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:calc(4px * var(--fscale))">${ys.map(k=>D('mpPick',{id:id,scope:sc,val:String(k),m:'年'},String(k)===v?'pri':'',String(k))).join('')}</div>`;
  }else if(md==='季度'){
    body=yhead+grid([1,2,3,4].map(q=>D('mpPick',{id:id,scope:sc,val:y+'Q'+q,m:'季度'},(y+'Q'+q)===v?'pri':'','Q'+q)).join(''))
      +`<div class="mut sm" style="margin-top:calc(6px * var(--fscale))">Q1 = 1–3 月 · Q2 = 4–6 月 · Q3 = 7–9 月 · Q4 = 10–12 月（自然季度）</div>`;
  }else if(md==='周'){
    const wq=/^\d{4}Q[1-4]$/.test(mp.wq)?mp.wq:(st.mode==='周'?tmQof(st.mon):tmQNow());
    const qy=+wq.slice(0,4), qq=+wq.slice(5);
    body=yhead+`<div style="display:flex;gap:calc(4px * var(--fscale));margin-bottom:calc(6px * var(--fscale))">${[1,2,3,4].map(q=>D('mpWQ',{id:id,scope:sc,val:v,qy:qy,qq:q},qq===q?'pri':'','Q'+q)).join('')}</div>`
      +`<div style="max-height:186px;overflow-y:auto;display:flex;flex-direction:column;gap:calc(3px * var(--fscale))">${tmWeeksOfQ(qy,qq).map(w=>
          D('mpPick',{id:id,scope:sc,val:w[0],m:'周'},w[0]===v?'pri':'',`<span style="font-family:var(--fm)">${w[0].slice(5)} ~ ${w[1].slice(5)}</span>`)).join('')}</div>`;
  }else{
    body=`<div class="mut sm">不限时间（不按单据日期筛选）</div>
      <div style="margin-top:calc(7px * var(--fscale))">${D('mpPick',{id:id,scope:sc,val:'全部',m:'全部'},'pri','切换为「全部」')}</div>`;
  }
  const quick=`<div style="display:flex;flex-wrap:wrap;gap:calc(5px * var(--fscale));margin-top:calc(7px * var(--fscale))">
      ${modes.indexOf('月')>=0?D('mpPick',{id:id,scope:sc,val:bjMonth(),m:'月'},'','本月（北京时间）'):''}
      ${md==='季度'?D('mpPick',{id:id,scope:sc,val:tmQNow(),m:'季度'},'','本季'):''}
      ${md==='周'?D('mpPick',{id:id,scope:sc,val:wkMon(SYS_TODAY),m:'周'},'','本周'):''}
      ${D('mpClose',{scope:sc},'','关闭')}</div>`;
  return `<div class="pjpop" style="position:absolute;z-index:80;top:calc(100% + 4px);left:0;background:var(--sf);border:1px solid var(--bd);border-radius:8px;box-shadow:0 8px 24px var(--shadow-pop);padding:calc(9px * var(--fscale));width:238px">
    ${head}${body}${quick}</div>`;
};

/* ---------- 项目档案查询：展示名解析 ----------
   ⚠️ 同一全名可能对应多条档案（1 个壳 + N 个具体小微共享同一全名）→ 此时只提示、不猜（铁律 5/6） */
const projMatches=full=>PJs.filter(p=>p.full===full);

/* ---------- 归属判定（链路 C） · 2026-09-12 定案 ----------
   「归属」= 这一行付款通知书算在【哪一条项目档案行】头上，存在 OWN[单据id]。
   · 全名不含「小微」→ 普通项目：全名唯一 ⇒ 归属天生确定，**永不「待指定」**
   · 全名含「小微」  → 小微壳：拿「单据名称」在**该壳下**各小微的关键词里匹配
       命中 1 个 → 自动归集；命中多个 / 未命中 → 需人工指定（弹窗问）
   ⚠️ 匹配范围**限定在该壳下**：关键词允许重复（决策 4），跨壳匹配会把钱记到别的壳头上
   ⚠️ 归属一律按 id 存取，禁止按全名反查（铁律 5/6） */
const SHELLKW=()=>'小微';                    /* 关键字配置化：正式实现读 MOD-14 配置，原型里固定 */
const kwList=k=>(k||'').split('|').filter(Boolean);
const isShellFull=full=>full.indexOf(SHELLKW())>=0;
const shellOf=full=>PJs.find(p=>p.type==='shell'&&p.full===full);
/* 该壳下的**全部**具体小微（**含归档**、归档排最后）—— 自动归集与弹窗候选**共用这一份**
   （2026-09-13 用户口径「放宽」：自动归集**也可以匹配到已归档的小微** ——
     壳归档后仍可能有新单据，若自动归集只看在建，这些单据会全部落到「待指定」而**阻塞导入**。
   ⚠️ 匹配范围**仍然只在该壳下**：关键词允许重复，跨壳会把钱记到别的壳头上。） */
const kidsAll=sid=>pjSort(PJs.filter(p=>p.parent===sid));
/* ---------- 项目候选的三条口径（2026-09-13 用户口径）----------
   ① **所有项目候选都要含归档项目** ② 归档项**一律排在最后** ③ 归档项**标注「已归档」**。
   ⚠️ 只放开"可选范围"，**不动默认筛选**：MOD-01 的状态筛选仍默认「在建」（§2.7）。
   ⚠️「未建档」的全名（档案里根本没有这一行）**仍不出现** —— 那不是"归档项目"、是"没有档案"。 */
/* ===== 项目候选 · **共性出口**（2026-09-13 阶段 2 收口；同日补「键 / 显示」统一）=====
   各候选的**筛选条件**天然不同（业务差异），但这几件事**必须一致、且只写一处**：
     ① **键 = 仓库名**（「键 / 显示」的唯一出口见下方 `pjKey` / `pjLabel`）② **显示 = 展示名**
     ③ 排序（归档后置 > ord，见 `pjSort`）④ 归档项**排最后 + 标注** ⑤ **未建档的不出现**
   ⇒ 「候选该列谁」看下面索引；「候选长什么样（键 / 显示 / 排序 / 标注）」一律走本区块。

   【候选来源索引 —— 改"某个候选该列谁"就去对应那一个函数】
     · 付款通知书「项目」筛选        → `PROJ_LIST()`          （通知书的**归属档案行**，去重取仓库名 ⇒ 壳不进候选）
     · 付款计划「项目」筛选          → `PL_PROJ_LIST()`       （计划行能唯一匹配到的档案行 ⇒ 仓库名）
     · 手动新增通知书 / 期初占位行   → `ntPjList()` / `lgPjList()`（档案表全部，**排壳**）
     · 手动新增集采合同「项目」      → `ntPjList()`             （档案表全部，**排壳**；合同必有项目）
     · 归属判定弹窗                  → `ownCands(n)`          （该壳下的具体小微）
     · 逐月欠款台账「项目」选择器    → `ledProjs()`           （该分类下有数据 / 有期初行；**键 = 仓库名**；共用面板 **单选**）
     · 过程资料「项目」              → `PROC_PJS`             （库存单据 `IV.wh` 去重 ⇒ 仓库名；共用面板 **单选**）
     · 库存单据「项目」筛选          → `WHs`                  （**同一份仓库清单**；键 = 仓库名，共用面板 **多选**）
     · 付款流水「付款项目」筛选      → `flProjs()`           （流水按**归属**归集 ⇒ 仓库名；共用面板 **多选**；
                                                              面板候选 = 流水里的项目 **∪ 当前已选的**）
     · 集采台账「项目」筛选          → `JC_PROJ_LIST()`       （集采合同 `proj` 去重 ⇒ 仓库名；合同**必有项目**）
     · 特殊费用月报表「项目」筛选    → `AWF_PJS`             （后端 `/api/m09/fee` 的 `projects` ⇒ 仓库名；共用面板 **单选**）
   ⚠️⚠️ **`projPanel` 的 `list` 必须是「候选键（仓库名）」，不是「档案行对象」**（2026-09-13 修：
      上面几处凡是拿到**档案行**的（如 `ntPjList()`），**必须过一层 `pjKeysOfRows()` 转成键**；
      否则 `data-pj="[object Object]"` ⇒ 选完一点就查不到该行 ⇒ 显示「未建档」。）
   ⚠️ 已撤掉的旧项（不要再按它找）：收发结存**没有**「仓库」筛选（它只有「核算年月」）。
   ⚠️ **刻意不把这些来源合成一个函数** —— 筛选条件是真的不同，硬合会造出一个满是开关的怪物，
      比现在的「逐处各写一遍」更难懂。要收敛的是**共性的那几件事**，不是筛选条件。 */

const pjDisp=p=>(p&&(p.disp||p.name))||'';            /* 档案行显示名：展示名 → 仓库名 → 空 */
const pjDispOr=(p,d)=>{ const v=pjDisp(p); return v||d; };
const pjNoShell=()=>PJs.filter(p=>p.type!=='shell'); /* 壳本身没有付款单据（§六-9）⇒ 不进候选 */
const uniqBy=(rows,f)=>[...new Set(rows.map(f).filter(v=>v!=null&&v!==''))];   /* 去重取值（候选最常用的形态） */
/* 归档标注的**唯一出口**：`plain` 给 `<select><option>` 用（那里只能用纯文本），否则给带提示的标签 */
const pjArcMark=(p,plain)=>arcOf(p)?(plain?ARC_TEXT:' '+arcTag()):'';

const arcOf=p=>!!p&&p.status==='归档';
const arcOfFull=full=>{ const m=projMatches(full); return m.length>0&&m.every(p=>arcOf(p)); };
const arcOfDisp=d=>arcOf(PJs.find(p=>p.type!=='shell'&&pjDisp(p)===d));
/* ---------- 自定义排序（2026-09-13 用户口径）----------
   排序主体 = **档案行**（说"项目排序"其实是**仓库排序**：仓库名 = 唯一标识，§9.8-4）。
   ⇒ **全名 / 仓库名 / 展示名**只是同一条档案行的三种叫法，统一按"该值定位到的档案行的 ord"排。
   优先级：**归档后置** > **ord** > （ord 相同则保持原顺序，`Array#sort` 稳定）。 */
const ORD_MAX=99999;
const ordOf=p=>{ const n=Number(p&&p.ord); return isFinite(n)?n:ORD_MAX; };
/* 按值定位档案行：全名 / 仓库名 / 展示名 任一命中；壳全名优先命中**壳**那一行（不是它的小微） */
const pjRowByVal=v=>PJs.find(p=>p.type==='shell'&&p.full===v)||PJs.find(p=>p.full===v||p.name===v||p.disp===v)||null;
const pjRowOf=x=>{ if(x==null) return null;
  if(typeof x==='string') return pjRowByVal(x);
  if(PJs.indexOf(x)>=0) return x;                                  /* 本身就是档案行 */
  return pjRowByVal(x.full)||pjRowByVal(x.name)||pjRowByVal(x.disp)||null; };   /* 仓库表这类"带名字但不是档案行"的对象 */
const cmpPj=(a,b)=>{ const ra=pjRowOf(a), rb=pjRowOf(b);
  const d=(ra&&arcOf(ra)?1:0)-(rb&&arcOf(rb)?1:0); if(d) return d;
  return ordOf(ra)-ordOf(rb); };
const pjSort=arr=>arr.slice().sort(cmpPj);
/* 重编号：按当前顺序（归档后置 → ord → 稳定）重新赋 1..N，保证**连续无重复** */
const pjSortedAll=()=>PJs.slice().sort(cmpPj);
const renumberPj=()=>{ let i=1; pjSortedAll().forEach(p=>{ p.ord=i++; }); };
const ARC_TEXT='（已归档）';   /* <select> 的 option 里只能用纯文本 */
const arcTag=()=>'<span class="tag t-in" title="该项目已归档：仍可被选中（数据不锁、状态随时可改回在建），只是各处默认筛选不显示它">已归档</span>';

/* ===== 项目候选的「键」与「显示」—— **全站唯一出口**（2026-09-13 用户口径）=====
   ⭐ **键 = 仓库名**（`ENT-01.name`：**唯一、不允许人工修改**，§9.8-4「仓库名不可人工修改」）
      —— **不得用「项目全名」当候选键**：全名**可人工修改**、且**壳与具体小微共用同一全名**（§2.2）。
   ⭐ **显示 = 展示名**（`pjDisp`：展示名 → 仓库名 → 空）。
   ⚠️ **小微壳没有仓库 ⇒ 不进任何项目候选**（与「壳本身没有付款单据」同一条链）；
       **未判定归属的行落不到任何仓库名 ⇒ 只在「全部项目」下可见**
       （真实系统里不会出现：归属未走完 ⇒ **整批不入库**，《设计规则》§四-7 · 《实施计划》§三 链路 C）。
   ⚠️ **写库一律仍按档案 id**（§9.8-5「按 id 不按名」）—— 「键 = 仓库名」管的是**给人选 / 给人筛**这一层，
      两者不冲突：仓库名可人工改？**不可以**（§9.8-4），但 id 更硬、且弹窗回传用 id 更安全。 */
const pjKey=p=>(p&&p.name)||'';                                  /* 档案行 → 候选键（仓库名）；壳 → '' */
const pjLabel=v=>{ const p=pjRowOf(v); return p?pjDisp(p):String(v==null?'':v); };   /* 候选键 → 显示文字（展示名） */
const pjKeysOfRows=rows=>pjSort([...new Set(rows.map(r=>pjKey(r)).filter(Boolean))]); /* 档案行集合 → 去重排序的候选键 */
const pjRowsWithKey=rows=>pjSort(rows.filter(p=>pjKey(p)));      /* 剔除壳（无仓库名）后按 归档后置 > ord 排 */
const matchKids=(full,doc)=>{ const sh=shellOf(full); if(!sh) return [];
  return kidsAll(sh.id).filter(p=>kwList(p.kw).some(w=>doc.indexOf(w)>=0)); };
/* 取归属（只读、无副作用）：已指定 > 普通项目全名唯一 > 壳下唯一命中 > null（待指定） */
const ownOf=n=>{
  if(!n) return null;
  if(OWN[n.id]){ const p=PJs.find(x=>x.id===OWN[n.id]); if(p) return p; }
  if(!isShellFull(n.proj)) return PJs.find(p=>p.full===n.proj)||null;
  const hit=matchKids(n.proj,n.doc); return hit.length===1?hit[0]:null;
};
/* 弹窗候选 = 该壳下的**全部**小微（**含归档**、归档排最后）—— 与自动归集**同一份清单**（`kidsAll`） */
const ownCands=n=>{ const sh=shellOf(n.proj); return sh?kidsAll(sh.id):[]; };
/* 关键词去重追加（决策 3/4）：词已存在则不重复追加 */
const addKw=(pid,w)=>{ const p=PJs.find(x=>x.id===pid); if(!p) return false;
  w=(w||'').trim(); if(!w) return false;
  const cur=kwList(p.kw); if(cur.indexOf(w)>=0) return false;
  p.kw='|'+cur.concat([w]).join('|')+'|'; return true; };

/* 展示名解析：**优先按【归属 id】取**；取不到才回退（禁止按全名反查猜） */
function dispCell(full,n){
  const ow=ownOf(n);
  if(ow) return esc(pjDispOr(ow,'—'));
  const m=projMatches(full);
  if(!m.length) return '<span class="tag t-dg" title="档案里没有该全名 → 触发自动建档">未建档</span>';
  if(m.length===1) return esc(pjDispOr(m[0],'—'));
  /* 壳全名 + 归属未判定 → 「待指定」：**可点**去指定（无行上下文时只提示、不可点） */
  if(!n) return `<span class="tag t-wn" title="该全名对应 ${m.length} 条档案（1 个壳 + ${m.length-1} 个具体小微共享同一全名）。系统禁止用全名反查，写操作一律按 id 定位，需先指定具体小微">壳下 ${m.length-1} 个小微 · 待指定</span>`;
  return `<span class="tag t-wn" data-act="ownOpen" data-id="${n.id}" tabindex="0" role="button" style="cursor:pointer" title="该全名对应 ${m.length} 条档案（1 个壳 + ${m.length-1} 个具体小微共享同一全名）→ 点此指定它属于哪个具体小微">壳下 ${m.length-1} 个小微 · 待指定</span>`;
}
/* 项目筛选候选项 = **能定位到仓库的项目（含归档）**；归档项排最后并标注（2026-09-13 用户口径）。
   ⭐ **键 = 仓库名**（§2.7.4）：由「归属档案行」取 `name` ⇒ **壳不进候选**（没有仓库名）、
      **未判定归属的行也落不进来**（真实系统里本就不存在这种行：归属未走完 ⇒ 整批不入库）。
      未建档的全名同样不列。 */
const PROJ_LIST=()=>pjKeysOfRows(uniqBy(NO,n=>ownOf(n)));
/* 集采台账「项目」筛选的候选（2026-09-13 新增）—— = 集采合同 `proj` 去重（**键 = 仓库名**，§2.7.4）。
   ⚠️ 候选取自**合同自己带的值**、不取全站项目档案 —— 筛选要筛的是"这批合同里出现过的项目"，
      与 `PROJ_LIST()`（按通知书的归属档案行）是**不同的筛选条件**（§ 上方【候选来源索引】的既定做法）。
   ⚠️ 合同必有项目 ⇒ **不需要"未指定"档**。 */
const JC_PROJ_LIST=()=>pjSort(uniqBy(JCs,j=>j.proj));
/* 面板宽度 = 内容自适应（max-content）：既不留下大片空白，也不会把项目名截断。
   行内一律 nowrap，不做省略号 —— 名字必须完整可读。 */
/* 通用「项目面板」：MOD-03 / MOD-04 / **MOD-06** **共用一份实现**，cfg 决定
   项目列表 / 已选集合 / 动作名 / **标签怎么显示（meta）** / **能不能多选（`single`）**。
   ⭐ **三个调用点的候选键一律是「仓库名」**（§2.7.4），meta 一律用 `PROJ_META_KEY`
      ——「仓库名 → 展示名」这件事**只有这一处**要写。
   ⭐ `single` 是**由调用点声明**的能力开关（与 `tmBtn` 的 `modes` 同一套思路）：
      单选时渲染 `radio`（不是 checkbox）、**不渲染「全选 / 清空」**（多选才需要），
      并且**面板内不出现 `scope===xxx` 之类的分支**。
   ⭐⭐ **单选 ⇒ 点一下就收**：`projPanel` 只渲染 `radio` ＋ `data-act="${c.pickAct}"`，
      而"收起哪一个展开态"由**注册表 `PJ_OPEN`**（key 由 `pickAct` 派生）＋ `pjPick` 统一做
      ⇒ ⛔ **调用点不许各写一遍**（原来那 6 处裸变量已删净）。
      ⚠️⚠️ **别把"某处有判据"当免责话写进注释**：这里曾写着「这条有机器判据 `test_proj_panel.py`」，
         而**那个文件从来不存在** —— **承诺一个不存在的检查，比不承诺更糟**（下一个人会放心把活交给它）。
         要写判据就把**文件名 ＋ 判词**写全，让机器扫得出来；真盯着它的是 `_shell_smoke.py` /
         `_shell_legacy.py` 的面板 round-trip（真点一下 ⇒ 收起）＋ `pjPick` 里那行统一收起。
   选中值一律走 `data-pj`（含义 = 该面板的筛选键 = **仓库名**）。 */
const PROJ_META_KEY=v=>{ const p=pjRowOf(v);
  return { nm:p?pjDisp(p):'未建档', warn:!p, arc:arcOf(p), title:'仓库名：'+v }; };
const PROJ_META_FULL=v=>{ const m=projMatches(v);
  return { nm:m.length===1?pjDisp(m[0]):(m.length>1?`${m.length-1} 个小微（同一壳）`:'未建档'),
           warn:m.length!==1, arc:arcOfFull(v), title:'项目全名：'+v }; };
/* ⭐⭐ **浮层面板展开态的唯一主人**（`#1` · 2026-09-26 用户裁定：
   「写在通用模块里，不必靠每个模块设计的时候自觉」）。
   ⛔ 调用点**不再各持一个 `let XxxPjOpen`** —— 全部走 `PJ_OPEN[key]`（key 由面板的 `pickAct` 派生）。
   ⭐ 三条自动行为（一个名字都不用登记 —— 原先那份"13 个名字逐个登记"的名单**整个消失**）：
     ① 点面板里的 `radio` ⇒ **选中后自动收起**（委托层做；多选面板渲染的是 `checkbox` ⇒ 天然不收）；
     ② 点 `.pjwrap` 之外 ⇒ 委托层**遍历注册表全关**；
     ③ 触发按钮 ⇒ `pjToggle(key)`。
   ⚠️ 2026-09-26 两次现场都出在"名单/自觉"上：漏登记 `IMP.pjIsOpen('pj')` ⇒ 用户报障「展开后关不掉」；
      单选点完要不要自收**根本没有规则**（6 处各写）。 */
const PJ_OPEN = {};
/* ⭐⭐ 项目面板的**过滤词**（去 ①② · 2026-09-27 用户裁定）：`{面板 key: 关键词}`。
   ⚠️ 为什么要单独存一份、而不是"让输入框自己拿着"：过滤**只切 DOM 显示、不重绘**
      （⛔ 重绘会把焦点与光标一起丢掉 —— 壳里踩过，见 `jcSubSet` 那行注释），
      而面板在**勾选 / 展开归档**时会重绘 ⇒ 重绘时要把关键词**填回去**，
      ⛔ 否则"勾一个候选就把搜索词清零"（多选场景等于没法用）。 */
const PJ_TXT = {};
const pjIsOpen = k => !!PJ_OPEN[String(k)];
const pjToggle = k => { const s = String(k); PJ_OPEN[s] = !PJ_OPEN[s]; render(); };
const pjClose = k => { const s = String(k); if (PJ_OPEN[s]) { PJ_OPEN[s] = false; return true; } return false; };
const projPanel=c=>{ const meta=c.meta||PROJ_META_FULL, single=!!c.single;
  /* ⭐ key **由 `pickAct` 派生**（`ledPjPick` ⇒ `ledPj`）⇒ ⛔ 调用点不用传、也不会漏传。 */
  const pk=String(c.pickAct||'').replace(/Pick$/,'');
  /* ⭐⭐ 2026-09-27（用户裁定 ①②：「项目会越来越多，候选不能无限增长」）：
     ① **搜索框**：按**展示名 / 仓库名**包含匹配 —— 它**不改候选集合**（§2.7.1 一字不动：含归档、
        排最后、标注都还在），只是让人**找得到**；
     ② **归档折叠**：归档项（本来就在最后）**默认折成一行**，点开照旧可选。
        ⚠️⚠️ 折叠行上**必须报「已选 k」** —— 多选面板的「全选」含归档（§2.7.1「含归档」）⇒
           折起来若不报，就会出现"**看不见的已选**"（状态不真实可见，本仓明令禁止）。
     ⚠️ 折叠的展开态**也进 `PJ_OPEN`**（key = `pk+'Arc'`）—— 壳里"展开态唯一主人"那条纪律，
        ⛔ 不许另开一份 `let xxxArcOpen`。
     ⚠️ 那个 `class="pjpop"` 是给 `placePops()` 用的（渲染后把它提升为 `fixed`）—— 见该函数注释。
        ⛔ 别删：删了面板又会被宿主卡片裁（用户 2026-09-26 报的"行数显示不全"）。 */
  const all=c.list(), sel=c.selected();
  const act=all.filter(v=>!meta(v).arc), arc=all.filter(v=>meta(v).arc);
  const arcOpen=pjIsOpen(pk+'Arc');
  const arcSel=arc.filter(v=>sel.includes(v)).length;
  const row=v=>{const on=sel.includes(v), mt=meta(v);
    return `<label data-pj-row data-pj-match="${esc((mt.nm+' '+v).toLowerCase())}" title="${esc(mt.title)}" style="display:flex;gap:calc(7px * var(--fscale));align-items:center;padding:calc(5px * var(--fscale)) calc(6px * var(--fscale));border-radius:5px;cursor:pointer;font-size:calc(12px * var(--fscale));white-space:nowrap">
      <input type="${single?'radio':'checkbox'}"${single?' name="projPanelSingle"':''} class="chk" style="flex:0 0 auto" data-act="${c.pickAct}" data-pj="${esc(v)}" data-pj-key="${pk}" ${on?'checked':''}>
      <span${mt.warn?' style="color:var(--wn-d)"':''}>${esc(mt.nm)}</span>${mt.arc?' '+arcTag():''}</label>`;};
  return `<div class="pjpop" style="position:absolute;z-index:80;top:calc(100% + 5px);left:0;width:max-content;min-width:178px;max-width:340px;max-height:264px;overflow-y:auto;overflow-x:hidden;background:var(--sf);border:1px solid var(--bd);border-radius:8px;box-shadow:0 8px 24px var(--shadow-pop);padding:calc(5px * var(--fscale))">
  <div style="display:flex;gap:calc(6px * var(--fscale));align-items:center;padding:calc(2px * var(--fscale)) calc(4px * var(--fscale)) calc(6px * var(--fscale))">
    ${single?'':`<button class="btn sm" data-act="${c.allAct}">全选</button><button class="btn sm" data-act="${c.noneAct}">清空</button>`}
    <span class="mut" style="font-size:calc(11px * var(--fscale));margin-left:calc(4px * var(--fscale));white-space:nowrap">${single?'单选 · ':''}已选 ${sel.length}/${all.length}</span>
  </div>
  <div style="padding:0 calc(4px * var(--fscale)) calc(6px * var(--fscale))"><input class="inp" data-act="pjSearch" data-pk="${pk}" value="${esc(PJ_TXT[pk]||'')}"
    placeholder="搜索项目（展示名 / 仓库名）" style="width:100%;min-width:186px" title="只筛这一屏显示，⚠️ 不影响「全选 / 清空」的范围（那是全部 ${all.length} 个候选）"></div>
  <div data-pj-body>
    ${act.map(row).join('')}
    ${arc.length?`<button class="btn sm" data-act="pjArcToggle" data-pk="${pk}" style="width:100%;justify-content:flex-start;margin:calc(4px * var(--fscale)) 0 calc(2px * var(--fscale))">${arcOpen?'▾':'▸'} 已归档（${arc.length}${arcSel?` · 已选 ${arcSel}`:''}）</button>
      <div data-pj-arc${arcOpen?'':' hidden'}>${arc.map(row).join('')}</div>`:''}
    <div class="mut sm" data-pj-none hidden style="padding:calc(8px * var(--fscale)) calc(6px * var(--fscale))">没有匹配的项目</div>
  </div></div>`; };

/* ⭐⭐ 项目面板的**过滤 / 折叠重涂**（渲染后跑一次）—— 2026-09-27（用户裁定 ①②）。
   ⚠️ 为什么必须"渲染后重涂"：过滤是**纯 DOM** 的（打字不重绘 ⇒ 不丢焦点），
      可面板一重绘（勾选 / 展开）那点 DOM 改动就没了 ⇒ 渲染收尾要**按 `PJ_TXT` 再涂一遍**；
      折叠块同理（按 `PJ_OPEN[pk+'Arc']` 复位）。
   ⚠️ **有关键词时归档自动展开**：搜索的意义就是"找得到"，藏在折里等于搜不到（`0 命中` 是假话）。
   ⚠️ 空态要说人话：**"没有匹配「xx」的项目"** —— ⛔ 不许只留一片空白（用户会以为面板坏了）。 */
function applyPjFilters(){
  document.querySelectorAll('.pjpop').forEach(p=>{
    const box=p.querySelector('[data-act="pjSearch"]'); if(!box) return;
    const q=String(box.value||'').trim().toLowerCase();
    let hit=0;
    p.querySelectorAll('[data-pj-row]').forEach(r=>{
      const m=!q || String(r.dataset.pjMatch||'').includes(q);
      r.hidden=!m; if(m) hit++;
    });
    const arcBlock=p.querySelector('[data-pj-arc]');
    if(arcBlock) arcBlock.hidden = q ? false : !pjIsOpen(String(box.dataset.pk||'')+'Arc');
    const none=p.querySelector('[data-pj-none]');
    if(none){ none.hidden=hit>0; if(!hit) none.textContent=`没有匹配「${String(box.value||'').trim()}」的项目`; }
  });
}
/* ⭐⭐⭐ **通用浮层的「逃出卡片裁剪」机制** —— 全壳**只有这一处**（2026-09-26 立 · `TAIL-109` 起 · `TAIL-110` 收口）。
   适用对象 = **任何**展开的浮层：项目面板（`projPanel`）＋ **时间选择器（`tmPanel`）** ＋ 将来新增的浮层。

   **为什么需要**：`.card{...overflow:hidden}`（见上面 CSS，给表格圆角用的）会把**卡片矩形之外**的部分剪掉，
   而浮层是 `absolute` ⇒ 实测（真机量过，`TAIL-109`）：卡片下沿在 504、面板伸到 567 ⇒ **裁掉 63px ＝
   最下面 2~3 行**，而那几行**既看不见也滚不到**（面板自身 `scrollH≈clientH` —— 不是它自己的滚动问题）。

   **怎么做**：每次渲染后把展开的面板**提升为 `fixed`**（`fixed` 的包含块是视口，**不受非 transform 祖先的
   `overflow` 裁剪** ⇒ 逃出卡片），位置按**触发按钮**算、高度按**按钮下方到窗口底**算 ⇒ 一行都不缺；
   太长时面板自己的 `overflow-y:auto` 兜住。

   **怎么挂**：调用点只需两件事（⛔ 不需要知道本函数存在）——
     ① 浮层的**锚**加 `class="pjwrap"`（`position:relative` 的那个容器；名字里的 `pj` 是**历史遗留**，
        现在是通用锚 —— ⛔ 别再新建第二种锚名，那会让本机制要认两套名字）；
     ② 浮层的**盒**加 `class="pjpop"`。
   ⚠️ 面板**留在原 DOM 位置**（仍在锚内）——「点浮层外收起」的委托层判的就是锚的包含关系，
      搬走它 ⇒ "点浮层内"会被当成"点外面"（那种 bug 极隐蔽：点一下就收）。
   ⚠️ 触发按钮取 **`:scope > button`（锚的**直接**子按钮）**：浮层里的「全选 / 清空 / 31 个日期格」也是
      `<button>`，按 DOM 序拿"第一个 button"会拿成浮层内那个（位置就全错了）。
   ⚠️ 两条渲染路径都要调（`render()` 正常那条 ＋ **虚拟滚动提前 return 那条**）—— 见 `render()` 里的调用。 */
function placePops(){
  document.querySelectorAll('.pjwrap').forEach(w=>{
    const p=w.querySelector(':scope > .pjpop'); if(!p) return;
    const b=w.querySelector(':scope > button'); if(!b) return;
    const r=b.getBoundingClientRect();
    p.style.position='fixed';
    p.style.top=(r.bottom+5)+'px';
    /* 只给"按钮下方到窗口底"这段（最少 140px）—— 浮层自己的 `overflow-y:auto` 兜住更长的清单 */
    p.style.maxHeight=Math.max(140, innerHeight-r.bottom-14)+'px';
    /* 左右也夹进视口（按钮靠右时浮层不许把右边顶出去） */
    const wide=Math.min(340, Math.max(178, p.offsetWidth||260));
    p.style.left=Math.max(6, Math.min(r.left, innerWidth-wide-6))+'px';
  });
}
/* 浮层是 `fixed` ⇒ 外层一滚，它得**跟着按钮走**（否则"粘"在原地像浮在空中）。
   ⚠️ 监听挂 `document` ＋ **捕获阶段**（`scroll` 不冒泡 —— 同虚拟滚动那两行注释里记的坑）。 */
if(!window._pjPopBound){
  window._pjPopBound=true;
  window.addEventListener('resize', placePops);
  document.addEventListener('scroll', placePops, true);
}
const pjPanel=()=>projPanel({list:PROJ_LIST,selected:()=>fNt.projs,allAct:'pjAll',noneAct:'pjNone',pickAct:'pjPick',meta:PROJ_META_KEY});

/* 筛选条件：选择器即时生效（不设独立的「应用筛选」按钮） */
