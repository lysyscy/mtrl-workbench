/* shell/pages-a.js —— 壳的**独立件**（`P2-a` 拆件 · 2026-09-28 · 台账 `TAIL-164`）：`MOD-03` / `MOD-05` 的页辅助 ＋ `BIND` 注入。
 *
 * ⭐ **为什么单开一件**：付款域页面的筛选、草稿行、台账取数是**同一批人对同一批数据**的活 ⇒ 单开一件。
 *    `index.html` 原来一件套 4000 行（CSS ＋ HTML ＋ 内联脚本混装）⇒ 改一处要翻三个区
 *    （本会话两次白屏的同一个根）。本件是「**只拆非切片**」那一批里的一件。
 * ⛔ **本件不许碰**：任何 `V.<原型页>` 切片（它们**留在 `index.html`** —— 计划 §23 的口径，
 *    `ui_parity` 的 `U1` 逐行比它）· 口径判定（判定全在后端）· 界面文案的主人。
 * ⚠️ **加载顺序**：`index.html` 的 `<script src>` 顺序即真源 —— 本件排在 `actions.js` **之前**
 *    （`actions.js` / `core.js` 里有些表**加载期就求值**到本件的常量）。⛔ 别调顺序。
 * ⚠️ 本件的代码是**原样搬出**（逐字未改，含注释）；来历与搬法见计划 §15 `TAIL-164`。 */

addBind('m03', ()=>{ const box=$('#pickAllBox'); if(!box) return;
  /* ⚠️ 全选框的「可见候选」必须与 `pickAll` 走**同一个出口** —— 否则撤单行留在 `vis` 里、
     却永远勾不上 ⇒ 全选框会永久卡在"半选"态（勾满了还是个半选框）。 */
  const rows=ntHit(fNt), vis=rows.filter(ntSelectable).map(n=>n.id), hit=vis.filter(i=>pickSet.has(i)).length;
  box.checked = vis.length>0 && hit===vis.length;
  box.indeterminate = hit>0 && hit<vis.length;
  const hidden=ntHiddenPickCount(rows), bar=$('#view .selbar');
  if(!bar) return;
  if(fNt.ids) bar.insertAdjacentHTML('beforebegin',`<div class="sm" style="margin-bottom:calc(8px * var(--fscale))">仅显示本次已剔除或撤单单据 · ${fNt.ids.length} 条 <button class="btn" data-act="ntPasteScopeClear">清除此定位</button></div>`);
  /* 新增核对入口随内容换行，窄屏不能把付款按钮挤出可见区域。 */
  bar.style.flexWrap='wrap'; bar.style.rowGap='calc(6px * var(--fscale))';
  bar.style.paddingTop=bar.style.paddingBottom='calc(6px * var(--fscale))';
  const acts=$('.act',bar); acts.style.flexWrap='wrap'; acts.style.maxWidth='100%';
  if(hidden) $('.m',bar).insertAdjacentHTML('beforeend',` <span class="tag t-wn">当前列表外 ${hidden} 条</span>`);
  if(pickSet.size) $('.act',bar).insertAdjacentHTML('afterbegin',
    `${hidden?`<span class="sm mut">打印、付款按全部勾选</span>`:''}<button class="btn" data-act="pickClear">清空勾选</button>`);
  if(hidden) ['batchCatApply','batchEx','batchUnEx'].forEach(act=>{
    $$(`[data-act="${act}"]`).forEach(t=>{t.disabled=true;t.title='当前列表外还有已勾选记录，请先清空搜索核对';});
  }); });

/* Paste selection uses full bill numbers; only this batch moves to the top. */
let ntPasteTop=new Set(), ntPasteRaw='', ntPasteReport=null, ntPasteBusy=false;
const ntPasteMatch=(raw,notices)=>{
  const key=v=>String(v==null?'':v).trim().toUpperCase();
  const tokens=String(raw||'').split(/[\s,，;；、]+/).filter(Boolean);
  const counts=new Map(), byCode=new Map(), invalid=[];
  tokens.forEach(v=>{
    const k=key(v.replace(/^["“](.+)["”]$/, '$1'));
    if(!/^(?:FKTZS|QTZC)\d{4}(?:0[1-9]|1[0-2])\d{4}$/.test(k)){invalid.push(v);return;}
    counts.set(k,(counts.get(k)||0)+1);
  });
  notices.forEach(n=>{const k=key(n.code);if(!k)return;if(!byCode.has(k))byCode.set(k,[]);byCode.get(k).push(n);});
  const result={total:tokens.length,unique:counts.size,invalid,ids:[],missing:[],ambiguous:[],blocked:[],duplicates:[],paid:[]};
  for(const [code,count] of counts){
    if(count>1)result.duplicates.push(`${code}（${count}次）`);
    const hits=byCode.get(code)||[];
    if(!hits.length){result.missing.push(code);continue;}
    if(hits.length!==1){result.ambiguous.push(`${code}（系统${hits.length}条）`);result.blocked.push(...hits.filter(n=>!ntPayCand(n)));continue;}
    const n=hits[0];
    if(!ntPayCand(n)){result.blocked.push(n);continue;}
    result.ids.push(n.id);
    if(statOf(n)==='已付清')result.paid.push(code);
  }
  return result;
};
const ntPasteReportHTML=r=>{
  const groups=[['未识别为单据号的文本',r.invalid,'dg'],['未找到的单据号',r.missing,'dg'],
    ['系统重号，未勾选',r.ambiguous,'wn'],['重复输入，已合并',r.duplicates,'in'],['已付清，仍可打印',r.paid,'in']];
  return `<p>输入 ${r.total} 段文本，识别出 ${r.unique} 个不重复单据号。${r.ids.length?`已勾选 <b>${r.ids.length}</b> 条，集中在表格顶部。`:'没有可勾选的单据，原勾选保持不变。'}</p>`+
    groups.filter(g=>g[1].length).map(([label,list,color])=>`<div style="margin-top:calc(12px * var(--fscale))"><b class="${color==='dg'?'dg':'mut'}">${label} · ${list.length}</b><div class="sm" style="margin-top:calc(4px * var(--fscale));max-height:calc(160px * var(--fscale));overflow:auto;overflow-wrap:anywhere">${list.map(esc).join('、')}</div></div>`).join('')+
    (r.blocked.length?`<div style="margin-top:calc(16px * var(--fscale))"><b>已剔除或已撤单，未勾选 · ${r.blocked.length}</b> <button class="btn" data-act="ntPasteProcess">去处理</button><p class="sm mut">只筛选这些单据，清空当前勾选；请核对后自行勾选处理。</p><div style="max-height:calc(300px * var(--fscale));overflow:auto">${r.blocked.map(n=>`<div style="padding:calc(8px * var(--fscale)) 0;border-top:1px solid var(--bd);overflow-wrap:anywhere"><b>${esc(n.code)}</b> ${ntArchTag(n)}${n.excl&&ntVoid(n)?' '+tag('i8 已撤单','wn'):''}<div>${esc(n.doc||'（无单据名称）')}</div><div class="sm mut">${esc(ntProjName(n))} · ${esc(n.date)} · ${esc(n.recv||'（无收款单位）')} · 审批金额 ${M(n.approve)}</div></div>`).join('')}</div></div>`:'');
};

/* 全选框状态回显（与 MOD-03 / MOD-04 同款逻辑：全选 / 半选）—— `MOD-11` 集采台账
   ⚠️ 2026-09-13 P6 走查实测：这张表**一直没有 BIND** ⇒ 表头那个「全选」框**永远不反射状态**
      （全勾满了也还是空框、部分勾选也不显半选），而 `R10`② 明确要求"全选支持全选 / 半选回显"。 */
addBind('m11', ()=>{ const box=$('#jcAllBox'); if(!box) return;
  const vis=jcVisible();
  const hit=vis.filter(j=>jcPick.has(j.id)).length;
  box.checked = vis.length>0 && hit===vis.length;
  box.indeterminate = hit>0 && hit<vis.length; });

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
const LEDNOTE={};                          /* { '口径|项目键|月': 文本 } —— 逐月台账备注（手填；不在 §9.3 留痕范围） */
/* 通知书行的**项目键** = 归属档案行的**仓库名**（§2.7.4）；无归属 / 壳未判定 → ''（落不到任何项目上）。
   `ntProjName` 只在**给人看**时用（展示名）。 */
const ntProjKey=n=>pjKey(ownOf(n));
const ntProjName=n=>{ const k=ntProjKey(n); return k?pjLabel(k):(isShellFull(n.proj)?'（待指定归属）':n.proj); };
const ntYm=n=>String(n.date||'').slice(0,7);
const debtSourceTip=sc=>sc==='集采'
  ? '本项目集采欠款 = 集采台账中纳入台账合同的结算金额−付款金额之和；结算取对应发票子表，付款取付款子表；不计不纳入合同，不按日期截断'
  : `本项目${sc}欠款 = ${sc==='辅材'?'付款通知书辅材统计结算金额之和':'过程资料全部已存月份外租零租含税＋外租包月含税'} − 付款通知书同分类统计付款金额之和 ＋ 本分类历史手填调整；通知书剔除行不计，i8撤单有付款或集采关联仍计入，不按月份截断`;
/* 期初占位行存的是**项目全名** → 归一到**仓库名**（候选键，§2.7.4），才能与台账的项目键对上 */
const lgProjKeyOf=v=>pjKey(pjRowOf(v));
const nextYm=m=>{ const [y,mm]=String(m).split('-').map(Number); const t=new Date(y,mm,1);
  return ymOf(t); };
const prevYm=m=>{ const [y,mm]=String(m).split('-').map(Number); const t=new Date(y,mm-2,1);
  return ymOf(t); };
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
        ${PJB({act:'ledExpPjToggle',panel:ledExpPjPanel,w:186,label:`${ledExpPjs.length?`已选 ${ledExpPjs.length} 个项目`:'请选择项目'}`})}
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
/* 历史行和月份覆盖共用直接编辑；金额口径由后端持有。 */
const ledRows=(sc,proj)=>{ const side=m05Side(sc); if(!side) return [];
  return (side.display_rows||side.rows||[]).map(r=>({ym:r.month,kind:r.row_kind||'month',
    label:r.month_label||'',id:r.record_id,seq:r.seq,token:r.token||'',editable:!!r.editable,
    s:numOr0(r.other_expense),p:numOr0(r.payment),note:r.remark||''})); };
const ledHistoryInput=(r,sc,field)=>`<input class="inp led-cell ${field==='remark'?'':'num'}"
  ${field==='cutoff_ym'?'type="month" max="2025-11"':field==='remark'?'maxlength="512"':'inputmode="decimal"'}
  aria-label="${sc} ${r.ym} ${{cutoff_ym:'月份',settle_amount:'结算',paid_amount:'付款',remark:'备注'}[field]}"
  data-act="ledHistoryCell" data-sc="${sc}" data-seq="${r.seq}" data-field="${field}"
  value="${esc(field==='cutoff_ym'?r.ym:field==='settle_amount'?r.s.toFixed(2):field==='paid_amount'?r.p.toFixed(2):r.note)}"
  title="离开单元格即保存">`;
const ledRowPayload=(r,sc)=>({id:r.id||null,project_id:Number((M05.ledger||{}).project_id),
  category:CAT_API[sc],entry_kind:r.kind==='manual'?'manual':'month',cutoff_ym:r.ym,
  settle_amount:r.s.toFixed(2),paid_amount:r.p.toFixed(2),remark:r.note,token:r.token});
let ledAdding=false;
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
/* 与通知书同口径：搜索数据列，忽略大小写、空白及千分位逗号；不搜内部行号或操作。 */
const flSearchMatch=(f,q)=>{
  const norm=v=>String(v==null?'':v).toLocaleLowerCase().replace(/[,，\s]/g,'');
  const needle=norm(q); if(!needle) return true;
  const n=ntOf(f), p=n&&ownOf(n);
  return [f.flowNo,flDocNo(f),f.docDate,f.billName,n&&n.proj,p&&pjDisp(p),
    f.payee,f.categoryLabel,f.amountApproved,f.amountApproved==null?'':M(f.amountApproved),
    f.date,f.amt,f.amt==null?'':M(f.amt),f.method,f.remark,f.op,
    f.voided?'已撤销':'生效',f.voided?f.reason:'']
    .some(v=>norm(v).includes(needle));
};
const flVisible=()=>FLs.filter(f=>tmIn(flf.ym,f.date)&&flHit(f)
  &&flSearchMatch(f,flf.q));
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

