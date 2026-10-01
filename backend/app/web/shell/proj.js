/* shell/proj.js —— 壳的**独立件**（`P2-a` 拆件 · 2026-09-28 · 台账 `TAIL-164`）：通知书草稿 / 表格件与空态 / 各页表头常量 / 集采与供应商口径。
 *
 * ⭐ **为什么单开一件**：表格外壳（`TBL`）· 空态出口 · 各页列定义 · 集采关联与供应商判定 —— 都是**跨页共用**的口径件。
 *    `index.html` 原来一件套 4000 行（CSS ＋ HTML ＋ 内联脚本混装）⇒ 改一处要翻三个区
 *    （本会话两次白屏的同一个根）。本件是「**只拆非切片**」那一批里的一件。
 * ⛔ **本件不许碰**：任何 `V.<原型页>` 切片（它们**留在 `index.html`** —— 计划 §23 的口径，
 *    `ui_parity` 的 `U1` 逐行比它）· 口径判定（判定全在后端）· 界面文案的主人。
 * ⚠️ **加载顺序**：`index.html` 的 `<script src>` 顺序即真源 —— 本件排在 `actions.js` **之前**
 *    （`actions.js` / `core.js` 里有些表**加载期就求值**到本件的常量）。⛔ 别调顺序。
 * ⚠️ 本件的代码是**原样搬出**（逐字未改，含注释）；来历与搬法见计划 §15 `TAIL-164`。 */

let fNt={month:bjMonth(),cat:'全部',astat:'全部',stat:'未付清',projs:[]};   /* 年月默认「北京时间当月」；付款状态默认「未付清」 */
/* —— 「手动新增 / 编辑付款通知书」弹窗（2026-09-12 用户口径）——
   用途：付「期初占位行」的款 —— 那笔钱没有 i8 单据，只能手工补一行通知书。
   `naD` 是弹窗的**草稿层**：弹窗里的年月组件一改动就要重建弹窗，
   没有草稿层则重建时其它已填字段会被清空（本原型的既定教训，同 payDraft）。 */
let naD={};              /* 弹窗草稿：字段名 → 值（键与 NT_COLS 同名，另加 pid = 选中项目档案 id） */
let naEditId='';         /* '' = 新增；否则 = 正在编辑的手动行 id */
/* ⭐ 落库中（**挡重入** · 守则 §5.5）：连点两次「保存」= 两次 `POST /api/m03/actions/manual-save`
   ⇒ **同一份补录落两行**；⚠️ 手动行**没有**「单据号唯一约束」这道天然闸（同一笔补两行业务上是合法状态）
   ⇒ 只能由界面挡（与 `plRowSave` 的 `plSaving` / `IMP.busy` 同款）。 */
let ntSaving=false;
/* 纯函数：按筛选条件取命中行（供视图与自检共用）
   口径：年月 → 当月 1 号至末日、闭区间；项目可多选（空数组 = 全部项目）
   分类筛选的选项 = 辅材 / 机械 / 集采 / 剔除：
     · 「剔除」是标记不是业务分类（§4.2.2 标记保留、可筛选、不销毁数据），在筛选器里单列一项
     · 剔除行【默认不显示】—— 只有把分类显式切到「剔除」才看得到
       （§4.2.3：只有剔除后剩余的通知书才参与分类，故分类=全部时也不含剔除行）
     · ⭐「分类 = 剔除」= 「看剔除记录」的专用视图：**不受审批状态 / 付款状态筛选约束**
       （否则默认「付款状态 = 未付清」会把剔除行全部挡掉 → 切了也看不到，等于该视图失效） */
/* 项目筛选：候选键 = **仓库名**（§2.7.4），按**归属**命中（壳全名下的行拆到各自小微） */
const ntHit=f=>{ const ex=f.cat==='剔除';
  /* ⭐ 「分类 = 剔除」= 「看剔除记录」的专用视图，**同时承载两类行、按来源分档**：
     · 剔除行（`n.excl`）
     · **i8 已撤单行**（`ntVoid`）—— 用户口径 2026-09-14：撤单行**默认隐藏**，
       藏处 = 并进本视图（**不新增分类枚举值**），渲染时按来源给不同标签，两者不相混。 */
  const arch=n=>ex?(n.excl||ntVoid(n)):ntLive(n);
  return NO.filter(n=>tmIn(f.month,n.date)
    &&(!f.projs||!f.projs.length||f.projs.includes(ntProjKey(n)))
    &&arch(n)
    &&(ex||f.cat==='全部'||n.cat===f.cat)
    &&(ex||f.astat==='全部'||n.astat===f.astat)
    &&(ex||f.stat==='全部'||statOf(n)===f.stat)); };
/* 筛选变化后清理「已勾选」里不可见的行，避免出现选不中/看不见却被计入的幽灵勾选 */
const prunePick=()=>{ const vis=new Set(ntHit(fNt).map(n=>n.id)); [...pickSet].forEach(i=>{ if(!vis.has(i)) pickSet.delete(i); }); };

/* ---------- 手动新增 / 编辑付款通知书（2026-09-12 用户口径）----------
   场景：付「期初占位行」的款 —— 系统上线前那笔欠款**没有 i8 单据**，只能手工补一行通知书。
   用户拍板：① 行内一切信息都可手改（「编辑」走同一个弹窗）② 项目候选 = **全部已建档项目（含归档）**
   ③ 审批金额可改、默认 0 ④ **只对手动行**开放删除 ⑤ **统计结算金额恒 0 且只读** ⑥ 录入人 = 当前登录用户（§1.5.1）
   ⚠️ 全站口径「统计两金额 ≤ 审批金额」对手动行**同样有效**：要付 5 万，就把审批金额也填到 5 万
      （手动行没有 i8 结算，审批金额由人定；否则会被拦截）。 */
const ntPjList=()=>pjRowsWithKey(pjNoShell());   /* 壳本身没有付款单据（§六-9）⇒ 不进候选；一律走共性出口（归档后置 + ord 排序） */
const naNum=v=>{ const raw=String(v==null?'':v).trim(); return raw===''?0:N2(parseFloat(raw)); };
/* 单据日期默认 = 界面当前年月的 1 号（界面在「全部月份」时取北京时间当月）。日期用 `type="date"`，
   与既有 `ACT.jcAdd` 的「合同日期」同款 —— 需要的是**完整日期**（归月按它的 YYYY-MM），不是"选年月"。 */
const naDefDate=()=>tmStart(fNt.month)+'-01';
const ntBlank=()=>{ const L=ntPjList(), cur=ledCur();     /* 默认项目 = 欠款台账当前选中的项目（键 = 仓库名） */
  const pid=(L.find(p=>pjKey(p)===cur)||L[0]||{}).id||'';
  return {date:naDefDate(), code:'', pid, doc:'', biz:'', recv:'',
    cat:'辅材', astat:'已批', approve:'0', sp:'0', sup:''}; };
/* 「付款项目」候选：**值 = 仓库名**（§2.7.4）、**显示 = 展示名**；写库仍按档案 id（§9.8-5） */
const ntOpts=()=>pjSort(ntPjList()).map(p=>`<option value="${esc(p.name)}" ${naD.pid===p.id?'selected':''}>${esc(pjDisp(p))}${pjArcMark(p,1)}</option>`).join('');
/* ---------- 增行模式（2026-09-13 用户口径：**取消「手动新增 / 编辑」弹窗**，改**表内增行**）----------
   甲案（用户 2026-09-13 拍板）：**草稿行不落 `NO`**，只存**草稿层 `naD`**；`naEditId` 三态 =
     `''` = 无草稿 · `NT_NEW_ID`（哨兵 `'@new'`）= **新增中的草稿** · 真实 id = 正在**原地**编辑该手动行。
   ⇒ `NT_COLS` 一字不动 · 既有 `n.manual` 判据（6 处）不动 · 欠款 / 台账 / 合计 / 导出 / 全选可见集
     **全部天然不受影响**（它们只认 `NO`）。
   ⚠️ 草稿行是**列对齐行**（18 个 `<td>`）⇒ `applySorts` 原来的"`<td>` 数 < 表头列数"判据**保不住它**
      ⇒ 已给 `applySorts` 补一条 **`.draftrow` → 钉表尾**（与"合计行"同通道），见该函数。 */
const NT_NEW_ID='@new';                     /* 哨兵 id：新增中的草稿行（**不是** `NO` 的行） */
const ntDraftOn=()=>naEditId!=='';          /* 是否处于增行态（渲染草稿行的唯一判据） */
/* ⭐ 「点新增就把筛选放宽到能看见」—— 2026-09-13 用户口径：**从"保存后"前移到"点新增时"**。
   原逻辑在落库后才切年月 + 放宽三档；改增行后必须在**进入增行态**就放宽，否则用户填了一半
   才发现这一行在筛选之外看不见。⚠️ 「项目」筛选**一律不动**（既有口径）。
   ⚠️ 另有第二重保障：草稿行**无条件渲染**（不走 `ntHit`），即使筛选把它挡在外面也看得见。 */
const ntReveal=()=>{ fNt.month=String(naD.date||naDefDate()).slice(0,7);
  fNt.cat='全部'; fNt.astat='全部'; fNt.stat='全部'; prunePick(); };
/* 草稿行（**列对齐** 18 格 —— 逐列与 `NT_THEAD` 对齐；值取草稿层，不是 `NO` 的行） */
const ntDraftRow=()=>{ const d=naD, cat=d.cat||'辅材', isJc=cat==='集采';
  return `<tr class="draftrow">
    <td class="ctr fl"><span class="tag t-in" title="尚未保存 —— 填完点本行右侧「保存」写入；「取消」丢弃（草稿不写入，与弹窗的「取消」等价）">新增</span></td>
    <td><input class="inp" type="date" data-act="ntRowSet" data-k="date" value="${esc(d.date||'')}" title="单据日期（决定归月）"></td>
    <td><input class="inp" style="min-width:104px" data-act="ntRowSet" data-k="code" value="${esc(d.code||'')}" placeholder="单据编码"></td>
    <td><select class="inp" style="min-width:150px" data-act="ntRowSet" data-k="pid" title="付款项目（已建档项目 · 含归档、不含壳，§六-9）">${ntOpts()}</select></td>
    <td class="ctr"><select class="inp plain" style="width:auto" data-act="ntRowSet" data-k="cat">${optsOf(enumVals('cat'),cat)}</select></td>
    <td><input class="inp" style="min-width:120px" data-act="ntRowSet" data-k="doc" value="${esc(d.doc||'')}" placeholder="单据名称"></td>
    <td><input class="inp" style="min-width:96px" data-act="ntRowSet" data-k="biz" value="${esc(d.biz||'')}" placeholder="业务类型"></td>
    <td><input class="inp" style="min-width:110px" data-act="ntRowSet" data-k="recv" value="${esc(d.recv||'')}" placeholder="收款单位"></td>
    <td><input class="inp plain" style="min-width:132px" data-act="ntRowSet" data-k="sup" value="${esc(d.sup||'')}" placeholder="${isJc?'人工录入':'仅集采可填'}" ${isJc?'':'readonly'}></td>
    <td class="sm">${esc(CUR.name)}</td>
    <td class="num"><input class="inp num" style="width:96px" data-act="ntRowSet" data-k="approve" value="${esc(d.approve)}" title="手动行：审批金额可直接手改（i8 抓取行仍只读）；全站口径「统计两金额 ≤ 审批金额」仍成立"></td>
    <td class="num"><span class="mut" title="尚未写入 —— 写入后按「审批金额 − 已付金额」派生">0.00</span></td>
    <td class="num"><span class="mut">0.00</span></td>
    <td class="num"><span class="mut" title="手动新增行：这笔钱没有新结算（无 i8 单据）⇒ 统计结算金额恒为 0、不可修改；要入账请填「统计付款金额」">0.00</span></td>
    <td class="num"><input class="inp num" style="width:96px" data-act="ntRowSet" data-k="sp" value="${esc(d.sp)}" title="上限 = 审批金额（按发票走，只能往下调）"></td>
    <td class="ctr"><select class="inp" style="width:auto" data-act="ntRowSet" data-k="astat">${enumOpts('astat',d.astat)}</select></td>
    <td class="ctr">${stTag('未付清')}</td>
    <td class="ctr now"><button class="btn sm pri" data-act="ntRowSave"${ntSaving?' disabled':''} title="${ntSaving?'正在保存 —— 请勿重复点击':'校验通过后写入（统计结算恒 0 · 录入人 = 当前登录用户）'}">${ntSaving?'保存中…':'保存'}</button> <button class="btn sm" data-act="ntRowCancel"${ntSaving?' disabled':''} title="丢弃这一行草稿（不写入）">取消</button></td>
  </tr>`; };
/* ===== 列定义 → 表头 / 空态跨列数（阶段 4 · **试点：只接 m03**）=====
   原先"表头 / 每行 `<td>` / 空态行 `colspan`"三处各写一遍 ⇒ **加一列要改三处**。
   其中 `colspan` 是最阴的一处：它是**写死的数字副本**，漏改不会有任何检查器报红，
   只会表现为"空态那一行没铺满表格"（视觉 bug，没人测）。
   ⇒ 把**表头抽成唯一出处**（`NT_THEAD`），**跨列数由它算**（`thCount`）—— 加列时不可能忘记改 colspan。
   ⚠️ 每行的 `<td>` 仍逐行写：值各不相同，收不了（这是**数据**，不是结构）。
   ⚠️ 表头 HTML **一字不改**（只搬进常量）—— `applySorts` 靠表头文本判列类型与可排性，改一个空格都可能改行为。 */
/* ⭐ **表格件**（`TAIL-64` P0 · 2026-09-24）—— 一张表的**外壳**统一由它渲染：表头 / 行 / 空态 / 合计。
   ⭐ 抽它的真理由 = **虚拟滚动只需要挂一处**（本件内），且「表该怎么开」只有一个口径。
   契约：`TBL({head, rows, empty, sum, key, cls, sort, sty, headRows})` ⇒ 返回完整 `<table …>…</table>`（⚠️ 不含外层 `.tw`）。
   ⭐⭐ `TAIL-64` P2③（2026-09-29 · 为 `m07` 的三张表把契约补齐）—— 三个**可选参**，默认值都保持旧行为：
     · `sort`（默认 `true`）：给了 `key` 就**默认同时出 `data-sort`**（可排）；`sort:false` ⇒ **只出 `data-sort-key`**
       —— 表的**身份**要有，但它**刻意不可排**（真例 = `m07:kinds` 分组表 · `m07:bigtable` 大表）。
     · `sty` ⇒ 给 `<table>` 补一个内联 `style`（真例 = 大表 `min-width:1620px`）。
     · `headRows:true` ⇒ `head` 里**自带 `<tr>`**（多行表头），本件不再包一层（真例 = 大表三级表头）。
   ⛔ 与 `sumRowOf` / `thCount` 的分工：那两个是**纯算法**（求和 / 数列），本件只管**拼装**。 */
const TBL=({head='',rows=[],cols=null,list=[],empty='',sum='',key='',cls='',sort=true,sty='',headRows=false})=>{
  /* ⭐ `cols` = **列定义式**（`TAIL-64` P5-d-a · 2026-09-30）：`cols:[{t,r}]` ＋ `list:[…]` ——
     `t` = 表头那一格（**整段 `<th>` HTML`）· `r` = 取值器 `(x,i)=>` 这一格（**整段 `<td>` HTML`）。
     给了 `cols` ⇒ `head` / `rows` **由它派生**（⛔ 别同时再传那两个：本件里 `cols` 优先、那两个被忽略）。 */
  if(cols){ head=cols.map(c=>c.t).join('');
    rows=list.map((x,i)=>'<tr>'+cols.map(c=>c.r(x,i)).join('')+'</tr>'); }

  /* ⭐ `data-vs` = 「这一张表**可以由表级虚拟滚动接管**」的标记（⚠️ **行数够才真的接管** —— 阈值那一侧说了算）。
     ⚠️ **一律带、⛔ 不设开关**：本仓口径是「**别用名单式**」—— 改成「逐表开关 / 逐页点名」的话，
     哪天某张表涨到阈值而没人记得加，它就**永远不生效、且不报错**（这正是 `TAIL-66` 当年的原话）。 */
  const attr=' class="dt'+(cls?' '+cls:'')+'"'+(key?(sort?' data-sort data-sort-key="'+key+'"':' data-sort-key="'+key+'"'):'')+(sty?' style="'+sty+'"':'');
  const th=head?(headRows?'<thead>'+head+'</thead>':'<thead><tr>'+head+'</tr></thead>'):'';
  return '<table'+attr+'>'+th+'<tbody data-vs="'+(key||'1')+'">'
    +rows.join('')+(rows.length?'':empty)+sum+'</tbody></table>';
};

/* ⭐ **筛选栏件**（`TAIL-64` P4-a · 2026-09-30）—— 一根筛选栏的**外壳**统一由它渲染（`fbar` 那层）。
 * 契约：`FBAR({cls, sty, body})` ⇒ 返回 `<div class="fbar [cls]"[ style="…"]>body</div>`。
 * ⚠️ 本批（P4-a）**只收外壳**：栏里的控件（`.fi` / 按钮 / 汇总）留在调用点**原地** —— 与 `TBL` 的 P0 同款，
 *    先证明「外壳换写法、控件留在原地」能做到**行数与渲染字节都不变**；⛔ 别顺手把控件也挪进来。
 * `cls` 的合法取值 = `.fbar` 的变体（`pane` / `strip` / `strip mb6` / `plate`），声明在壳的样式块里。
 * 自证 = 变异脚本（去掉委托 / 掏空内核 ⇒ 对应判据必须红）。 */
const FBAR=({cls='',sty='',body=''})=>'<div class="fbar'+(cls?' '+cls:'')+'"'+(sty?' style="'+sty+'"':'')+'>'+body+'</div>';

/* ⭐ **项目选择按钮件**（`TAIL-64` P4-d · 2026-09-30）—— 共用面板 `projPanel` 的**那枚 ▾ 按钮**
 * 统一由它渲染（`pjwrap` 里那一层）。契约：`PJB({act, w, label, title})` ⇒ 返回完整 `<button…>…</button>`。
 * ⚠️ 为什么把**按钮**也收了（`P4-d` 的第 ② 档）：那串
 *    `style="min-width:Npx;display:inline-flex;align-items:center;justify-content:space-between;gap:calc(8px * var(--fscale))"`
 *    与收尾那枚 `▼` 原本**逐处手写**（12 处），而 `min-width` 实测有 **6 种值** ⇒ §5.9「同类形态只留一处出口」。
 *    ⚠️ `w` 是**显式参数**（宽度按标签长短本就不同，⛔ 不是要抹平它 —— 是把它从长串里**抬出来**）。
 * `title` 只在需要时给（真例 = 通用导入面那枚，悬停要带仓库名）。
 * ⭐ `P4-d-b` 铺量（2026-09-30）时量出**两种形态**，于是补两个参（**默认值都保持旧行为** ⇒ 老调用点零变化）：
 *    · `cls`（默认 `'btn'`）—— 真例 = 台账那枚 `ledPjToggle` 的**动态 class**
 *      （展开时 `btn on`，用户 2026-09-28 `TAIL-142` 要的"点开必须变样"）。
 *    · `attrs`（默认 `''`）—— **排在 `style` 之前**的额外属性。真例 = 同一枚的 `title`：
 *      它原本就写在 `style` **之前**（而 `title` 那个参是排在 `style` **之后**的，见下）。
 *      ⚠️ 属性顺序在 HTML 里**无语义**，但本仓这一路的验收口径是「**渲染字节逐字节不变**」⇒ 照原样摆。
 * ⚠️ `attrs` / `title` **都是"额外属性"但位置不同**（前者在 `style` 前、后者在后）——
 *    ⛔ 别为某一处随手挑一个：挑错了**渲染字节就变了**（脚本里的自证会当场拦下）。
 * ⛔ 与 `projPanel` 的分工：本件只管**那枚按钮**，⛔ 不碰面板（面板仍走 `projPanel` 唯一出口 · 守则 §5.12）。
 * ⚠️ **本件只在壳侧**（⛔ 不进 `U5_GROUPS`）：原型那侧的按钮还是**旧形态**（`gap:8px`、无 `--fscale`），
 *    硬同步会让它的按钮退化成"没有 gap"（`var()` 未定义）⇒ 见 `tools/oneoff/_p4d_pjb_pilot.py` 的文件头。
 * 自证 = 变异脚本（去掉委托 / 掏空内核 ⇒ 对应判据必须红）。 */
const PJB=({act='',w=126,label='',title='',cls='btn',attrs=''})=>'<button class="'+cls+'" data-act="'+act+'"'+attrs
  +' style="min-width:'+w+'px;display:inline-flex;align-items:center;justify-content:space-between;gap:calc(8px * var(--fscale))"'
  +(title?' title="'+title+'"':'')+'><span>'+label+'</span><span class="mut" style="font-size:calc(9px * var(--fscale))">▼</span></button>';

/* ⚠️⚠️ **2026-10-01（`TAIL-213` 甲）：这里的「口径说明块件」`CALIB` 已整件退场。**
 * 用户拍板（原话）：「**每页折叠的口径说明里的也简化或者删除吧？说实话我一次也没进去看过**」
 * ⇒ 全站 **14 块折叠块（74 条 / 5,828 字）全撤**，改成 **13 段页内默认展开的说明**（各 ≤160 字）：
 *    会做错的后果 ⇒ 留（页内或操作现场的悬停）· 复述《说明书》的规则 ⇒ 删（复述必漂）。
 * ⛔ **别再长回来** —— 守卫 = `tests/test_ux_numbers.py::test_口径说明不许再收进折叠块`。
 * 来历 / 逐批实况 = `work/10-designs/设计-口径说明折叠块-20261001.md`（§七 施工实况）。 */

const thCount=h=>(String(h).match(/<th\b/g)||[]).length;   /* 一张表有几列 —— 从表头数出来，不写死 */
/* ⚠️ **表头有几「列」**（不是有几个 `<th>`）—— **两行表头**时两者不等：月度会大表 `<th>` 共 23 个，而**列数是 20**
   （`rowspan` / `colspan` 各只占 1 个 `<th>`）⇒ `thCount` 会把列数**多算**、合计行就会多出几个空 `<td>`，
   而"列对齐"断言**跳过含「合计」的行** ⇒ **完全静默**（2026-09-13 迁移大表时实测踩到，靠新断言才抓出）。
   正确算法 = **首行表头的 `colspan` 累加**（与 §六「列对齐」断言同一套）。 */
const thCols=h=>{ const s=String(h);
  const th=((s.match(/<thead\b[^>]*>([\s\S]*?)<\/thead>/i)||['',s])[1]);
  const row=((th.match(/<tr\b[^>]*>[\s\S]*?<\/tr>/i)||[th])[0]);
  return (row.match(/<th\b[^>]*>[\s\S]*?<\/th>/gi)||[]).reduce((a,x)=>a+(+((x.match(/colspan="(\d+)"/)||[0,1])[1])),0); };

/* ⭐⭐ 2026-09-27（`TAIL-117` 批次 6「四态统一」· 守则 §2.2 / §3.3 / §5.9）：**表内空态的唯一出口**。
   一条空态要回答**两件事**（守则：空态不是"一片空白"，是"说清为什么空 ＋ 下一步点哪儿"）：
     · `why`  = **为什么这一格是空的**（"当前筛选下没有…" / "该项目本月没有…"）——⛔ 别只写"无数据"
     · `next` = **下一步**（换个筛选 / 去哪儿补录 / 无需处理）
   ⚠️ `cols` 一律用 `thCount(某_THEAD)` 派生（⛔ 别写死列数 —— 加一列就会让空态行少一格）。
   ⚠️ 通用导入面那半用 `legacy.js` 的 `lgEmpty(cols, text)`（只出"一句话"，域自报的文案）——
      **两件的分工是有意的**：导入面的话由域给，业务页的话由业务方给。⛔ 别互相调。
   ⛔ 别再手写 `<tr><td colspan=… class="ctr mut">`（判据 `tests/test_ux_states.py` 会红）。 */
const EMPTYROW=(cols,why,next)=>`<tr><td colspan="${cols}" class="ctr" style="padding:calc(22px * var(--fscale))">`
  +`<div class="mut">${why}</div>`
  +(next?`<div class="mut sm" style="margin-top:calc(5px * var(--fscale))">下一步：${next}</div>`:'')+`</td></tr>`;
/* ⭐ 块级空态（**不在表里**的空区：图表 / 卡内内容为空）—— 与 `EMPTYROW` 同款两个问题。
   ⚠️ 为什么单独一个而不是复用 `EMPTYROW`：那块 HTML 不在 `<table>` 里，
      塞 `<tr>` 进去会被浏览器**静默丢弃**（div 上下文里 `tr` 不合法 ⇒ 屏幕上一片空白，
      而这恰恰是"空态"本身 —— 用户看到空白时**分不清**是"没数据"还是"页面坏了"）。 */
const EMPTYBOX=(why,next)=>`<div class="ctr" style="padding:calc(22px * var(--fscale))"><div class="mut">${why}</div>`
  +(next?`<div class="mut sm" style="margin-top:calc(5px * var(--fscale))">下一步：${next}</div>`:'')+`</div>`;

/* —— 「表内合计行」的**唯一出口**（2026-09-13 用户口径：求和一律落在**表内**、与所有表同款）——
   声明式：`sums` = { 列下标: 取值函数 } 或 { 列下标: [取值函数, 格式化函数] }；列数从**表头常量**派生（`thCount`）
   ⇒ 合计行的 `<td>` 数恒 = 表头列数（不可求和的列给空 `<td>`，与空态行同一个列数出口）。
   行首格写 `lead`（默认「合计」）⇒ `applySorts` 会把含「合计」的行**钉在表尾**，天然不被排序卷走。
   `opt` 一览（⚠️ **每一项都有真实调用点，不是预留** —— 2026-09-13 把 10 处既有合计行迁进来时定的）：
     · `lead` 首格内容（**可含 HTML**；默认 `合计`）
     · `leadSpan` 首格 `colspan`（默认 1）—— `MOD-05` 台账 / 流水、`MOD-07` 大表 用它把标签压在前置列上
     · `leadCls` 首格 class（默认无）—— `MOD-05` 两处合计的标签是**居中**（`ctr`）
     · `cells` { 列下标: **整格 HTML** }：非数值格（如收发结存末列的「校验」状态 tag）；与 `sums` 互斥使用
     · `style` 行内样式（默认 `background:var(--sf2);font-weight:500`；`MOD-05` 两处与集采子表传自己的）
     · `tip` 首格 `title`
     · `sticky` 是否带**置底**标记（默认 `true`）—— **分组表**（`MOD-07` 焊材/气体提取）传 `false`
       （分组合计要紧贴本组；两行同时 sticky 会重叠）
   ⚠️ **不要在视图里内联求和**；要加合计就调这里（与 `thCount` / `pjDisp` 同一套「唯一出口」思路）。 */
const sumRowOf=(thead,rows,sums,opt={})=>{
  const n=thCols(thead), span=Math.max(1,opt.leadSpan||1), cells=opt.cells||{};
  const lead=opt.lead===undefined?'合计':opt.lead;
  const style=opt.style===undefined?'background:var(--sf2);font-weight:500':opt.style;
  const tds=[];
  for(let i=0;i<n;){
    if(i===0){ tds.push(`<td${span>1?` colspan="${span}"`:''}${opt.leadCls?` class="${opt.leadCls}"`:''}${opt.tip?` title="${esc(opt.tip)}"`:''}>${lead}</td>`); i=span; continue; }
    if(cells[i]!=null){ tds.push(cells[i]); i++; continue; }
    const s=sums[i];
    if(s==null){ tds.push('<td></td>'); i++; continue; }
    const f=Array.isArray(s)?s[0]:s, fmt=Array.isArray(s)?(s[1]||M):M;
    tds.push(`<td class="num">${fmt(f(rows))}</td>`); i++;
  }
  return `<tr${opt.sticky===false?'':' class="sumrow"'}${style?` style="${style}"`:''}>${tds.join('')}</tr>`;
};

/* —— 各表**表头常量**（唯一出处）：表头与"空态行的跨列数"都从它来 —— 见上方 `thCount` ——
   ⚠️ 一律**逐字搬**，不要顺手改标记/空格：`applySorts` 靠表头文本判列类型与可排性。 */
const LED_THEAD=`      <th style="width:44px">序号</th><th>月份</th><th>其他支出金额</th><th>付款</th><th>欠款</th><th>备注</th><th>操作</th>`;
/* MOD-05 付款流水的表头（与其余 7 张同款：抽常量 ⇒ 空态行的跨列数由 `thCount()` 派生，不写死） */
const FL_THEAD=`<th>流水号</th><th>单据编码</th><th>付款项目</th><th>付款日期</th><th>付款金额</th><th>实际付款方式</th><th>备注</th><th>操作人</th><th>状态</th><th>操作</th>`;
const PJ_THEAD=`<th data-nosort>排序<span class="mut">（自定义 · 全站跟随）</span></th><th>类型</th><th>展示名<span class="mut">（默认取仓库名 · 可改）</span></th><th>仓库名<span class="mut">（唯一标识 · 不可改）</span></th><th>项目全名<span class="mut">（可改 · 留痕）</span></th><th>信息化编号<span class="mut">（不可改）</span></th><th>状态</th><th>所属壳</th><th>小微识别关键词</th><th>操作</th>`;
const DIFF_THEAD=`<th>单据编号</th><th>序号</th><th>物料</th><th>仓库</th><th>原值（i8）</th><th>调整后</th><th>差额</th><th>备注</th><th>操作人</th><th>时间</th><th>操作</th>`;
const INV_THEAD=`<th>单据编号</th><th>序号</th><th>方向</th><th>物料</th><th>规格</th><th>单位</th><th>数量</th><th>不含税单价</th><th>含税单价</th><th>金额</th><th>调整后金额</th><th>价税合计</th><th>业务类型</th><th>供应商 / 班组</th><th>单据日期</th><th>审核日期</th><th>仓库</th><th>wbs 名称</th><th>cbs 名称</th><th>操作</th>`;
/* ⭐ 2026-09-13 用户口径：发票子表**录入时要填日期** ⇒ 新增「发票日期」列（供应商 / 贸易公司两子表共用本表头）。
   ⚠️ 列顺序与「付款子表」同款（**日期在前**）—— 数据槽位同样改 `[日期, 金额]`。 */
const JCINV_THEAD=`<th>#</th><th>发票日期</th><th>金额</th><th>操作</th>`;
const JCPAY_THEAD=`<th>日期</th><th>金额</th><th>来源</th><th>操作</th>`;
/* ---------- 集采三张子表（供应商发票 / 贸易公司发票 / 付款）的**表内增行**录入 ----------
   用户口径（2026-09-13）：① 发票子表**录入时要填日期** ② 发票金额**不做限制**
   （不接 `overCap`，只走 `badMoney({positive:1})` 这唯一出口 = 「必须 > 0」、**无上限**）。
   形态 = 与批 G 三处增行**同范式**：弹窗内**表尾插一行草稿**（行内 `type="date"` ＋ 金额框 ＋ 保存 / 取消）；
   草稿**只存 `jcSubD`、不落 `JCs` 子表** ⇒ 取消即丢弃、子表合计与欠款不受影响。
   ⚠️ 弹窗表都带 `data-sort`，草稿行是**列对齐行**（`<td>` 数 = 表头列数）⇒ 靠行级 `.draftrow`
      并入 `applySorts` 的 pin 通道（钉表尾、不参与排序）；草稿行渲染在**合计行之前** ⇒ pin 后仍是「草稿行 → 合计行」。
   ⚠️ 付款日期默认取 `SYS_TODAY`（原先写死 `'2026-09-11'` 那个日期字面量已删除）。
   发票日期**必填**（未填不许保存）。 */
const JCSUB_KIND={inv:'invoices',tinv:'tradeInvoices',pay:'payments'};
let jcSubKind='', jcSubId='';
let jcSubD={date:'',amt:''};
const jcSubOn=(k,id)=>jcSubKind===k&&jcSubId===id;      /* 渲染草稿行的唯一判据 */
const jcSubReset=()=>{ jcSubKind=''; jcSubId=''; jcSubD={date:'',amt:''}; };
const jcSubDlg=(k,id)=>{ if(!id) return;
  if(k==='inv') ACT.jcInvDlg({dataset:{id}});
  else if(k==='tinv') ACT.jcTInvDlg({dataset:{id}});
  else if(k==='pay') ACT.jcPayDlg({dataset:{id}}); };
/* 草稿行（列对齐 —— 发票两子表 4 格、付款子表 4 格，各自与所在表头一致） */
const jcSubRow=()=>{ const d=jcSubD;
  const dateCell=`<td style="white-space:nowrap"><input class="inp" type="date" style="min-width:134px" data-act="jcSubSet" data-k="date" value="${esc(d.date||'')}" title="必填 —— 发票日期 / 付款日期（决定归月）"></td>`;
  const amtCell=`<td class="num"><input class="inp num" style="width:110px" data-act="jcSubSet" data-k="amt" value="${esc(d.amt||'')}" placeholder="金额" title="必须 > 0；本子表不设上限"></td>`;
  const ops=`<td class="ctr now"><button class="btn sm pri" data-act="jcSubSave" title="校验通过后写入（日期必填 · 金额必须 > 0、无上限）">保存</button> <button class="btn sm" data-act="jcSubCancel" title="丢弃这一行草稿（不写入）">取消</button></td>`;
  if(jcSubKind==='pay') return `<tr class="draftrow">${dateCell}${amtCell}<td>${tag('手工','in')}</td>${ops}</tr>`;
  return `<tr class="draftrow"><td class="fc">新增</td>${dateCell}${amtCell}${ops}</tr>`; };
/* MOD-11 集采台账的表头（第 9 张抽出来的表）—— 空态行的跨列数由它派生（`thCount(JC_THEAD)`），不写死 */
/* ⚠️⚠️ **这里曾经被我插进一段 CSS 规则**（`table.jc-hidetrade > … { display:none }`）——
   大错：**本文件这一段的上下文是 `<script>`（JS），不是 `<style>`** ⇒ 那句 CSS 成了**语法错**
   ⇒ **整段脚本崩掉**（症状是页面里 `PJs is not defined`，因为 `let PJs` 根本没执行到）。
   ⚠️ `syntax_audit` 的 `node --check` 查的是壳的 **JS 件**、**没覆盖到 `index.html` 的这段** ⇒ 没拦住。
   ⇒ 已改成**在 `jcApplyHide()` 里直接设内联 `display`**（见 `shell/actions.js`）——
     效果一样（`table.dt` 是 `width:100%` + `auto` ⇒ 剩下的列**自动变宽**），且**零 CSS 风险**。
   ⛔ 别再往这段加 CSS/HTML：要加样式请找真正的 `<style>` 段。 */

/* MOD-11 集采台账的表头（第 9 张抽出来的表）—— 空态行的跨列数由它派生（`thCount(JC_THEAD)`），不写死。
   ⭐ 2026-09-13 用户口径：**「合同存档情况 / 存档号 / 寄回日期」三项整体右移，紧贴「操作」左边**
     （列数不变 = 20；只调次序）。⚠️ 表内**刻意不设「项目」列** —— 「项目」只作为**筛选**（通用控件）。 */
const JC_THEAD=`
      <th class="ctr fl" style="width:34px"><input type="checkbox" class="chk" id="jcAllBox" data-act="jcPickAll" title="全选 / 取消全选（仅当前筛选结果）"></th>
      <th>序号</th><th>合同日期</th><th>材料名</th><th>供应商</th><th>合同金额</th><th>发票金额</th><th>贸易公司名</th><th>贸易公司合同金额</th><th>贸易公司发票金额</th>
      <th>结算金额<b class="mut">（自动）</b></th><th>付款金额</th><th>欠款金额<b class="mut">（自动）</b></th>
      <th>付款方式<b class="mut">（自由文本）</b></th><th>备注</th><th>三态</th>
      <th>合同存档情况</th><th>存档号</th><th>寄回日期</th><th>操作</th>`;
/* MOD-09 特殊费用月报表的表头 —— 空态（该月还没有手填项）的跨列数由它派生，不写死 */
const AWF_THEAD=`<th>数据项</th><th>来源</th><th>金额</th><th>占合计</th><th>操作</th>`;
/* MOD-07 收发结存的表头（第 11 张抽出来的表）—— 空态行的跨列数由它派生（`thCount(WH_THEAD)`），不写死 */
const WH_THEAD=`<th>仓库名</th><th>行数</th><th>期初金额</th><th>收金额</th><th>发金额</th><th>结存金额</th><th>校验</th>`;
/* MOD-07 焊材 / 气体提取的表头（第 12 张抽出来的表）—— 空态行的跨列数由它派生（`thCount(EXT_THEAD)`）。
   ⭐ 2026-09-18 用户裁定（甲）：本表**加一列「结余」**（位置照成品模板 = 仓库之后、金额之前），**点格即改**。 */
const EXT_THEAD=`<th>类别</th><th>仓库</th><th>结余<b class="mut">（手工录入）</b></th><th>总金额<b class="mut">（累计）</b></th><th>金额<b class="mut">（按所选月份）</b></th>`;
/* MOD-07 月度会大表的表头（第 13 张抽出来的表）—— 用户给的**最终模板**（20 列 · **两行表头**）。
   ⚠️ 两行表头的 `<th>` 总数（23）≠ 数据列数（20）⇒ 本表**刻意不可排**：
      `applySorts` 按 `thead` 里 `<th>` 的下标定位列（`data-i`），两行表头会整体错位。
   ⭐⭐ `TAIL-175`（2026-09-29 用户裁定 `A`）：**首列区（序号 ＋ 项目名称）挂 `.fl`**（sticky-left）——
      大表 `min-width:1620px`，往右填「机械费测算 / 合同价 / 产值累计」（手填 6 列正好在最右）时
      首列区会跟着滚走 ⇒ **看不见自己在给哪个项目填**（会填错行）。
      ⚠️ 两行表头 ⇒ 只有**第 1 行**的前两格是这两列（它们 `rowspan="2"`，第 2 行里没有）；
      ⚠️ 第 2 列必须让开第 1 列的宽，偏移规则在样式块 `.fl + .fl` 那一条（真机量过：两列严丝合缝）。
      ⚠️ 本常量在**原型与壳各存一份**（`ui_parity` 的 `U5` 逐字一致项）⇒ **两边必须同改同句**。 */
const BIG_THEAD=`<tr><th rowspan="2" class="fl">序号</th><th rowspan="2" class="fl">项目名称</th><th rowspan="2">开工时间</th>`
  +`<th colspan="4">辅材使用（不含税）</th><th colspan="4">外租使用（含税）</th>`
  +`<th rowspan="2">合计</th><th rowspan="2">机械费测算</th><th rowspan="2">使用率</th>`
  +`<th colspan="3">产值</th><th rowspan="2">主材累计<b class="mut">（含税）</b></th><th rowspan="2">工程用油</th><th rowspan="2">备注</th></tr>`
  +`<tr><th>焊材<b class="mut">累计</b></th><th>焊材<b class="mut">当月</b></th><th>三气<b class="mut">累计</b></th><th>三气<b class="mut">当月</b></th>`
  +`<th>外租机械<b class="mut">开工累计</b></th><th>外租机械<b class="mut">当月</b></th><th>设备租赁<b class="mut">开工累计</b></th><th>设备租赁<b class="mut">当月</b></th>`
  +`<th>产值完成率</th><th>合同（预估）价</th><th>产值累计<b class="mut">（含税）</b></th></tr>`;
/* —— 2026-09-13 新抽的 3 张表头常量（为「表内合计行」提供列数出口 —— `sumRowOf` 按表头派生列数）——
   ⚠️ 一律**逐字搬**（含换行与缩进），不要顺手改标记/空格 —— `applySorts` 靠表头判列类型与可排性。 */
const PL_THEAD=`
      <th class="ctr fl" style="width:34px"><input type="checkbox" class="chk" id="plAllBox" data-act="plPickAll" title="全选 / 取消全选（仅当前筛选结果）"></th>
      <th>#</th><th>年月</th><th>项目（填报：展示名 / 仓库名）</th><th>单据号（计划填报）</th><th>i8 流程金额</th><th>已付款金额</th><th>剩余付款金额</th><th>本月预付款金额</th><th>付款时间</th><th>付款方式</th><th>备注</th><th>审查结果</th><th>处理</th><th>操作</th>`;
const DF_THEAD=`<th>编号</th><th>核算月</th><th>归属</th><th>项目</th><th>差异内容</th><th>差异金额<b class="mut">（带符号 · + 上调 / − 下调）</b></th><th>状态</th><th>备注</th><th>操作</th>`;
const BP_THEAD=`<th>单据编码</th><th>付款项目</th><th>审批状态</th><th>审批金额</th><th>已付金额</th><th>本次应付</th><th>实际付款方式</th><th>本次付款金额</th><th>操作</th>`;

/* —— 「关联集采合同」：付款域 → 集采域的**反向入口**（2026-09-13 用户裁定；口径见《说明书》§6.6.2）——
   ⚠️ **不新增字段**：关联关系的**唯一存储** = 集采合同**付款子表的那一行**（第 4 槽 = 通知书 id）——
      与「从付款域引用（R8）」**共用同一份记录** ⇒ 两个方向双向可见，不会"同一事实两处存"。
   ⚠️ **一对一**：一条通知书最多关联一张合同（换合同 = 先解绑旧的再写新的）。
   ⚠️ **去重范围 = 全库**（§6.6.2「同一笔付款通知书只能被引用一次」，**不分公司**）。 */
const jcUsedNids=()=>new Set(JCs.flatMap(j=>(j.payments||[]).filter(p=>p[3]).map(p=>p[3])));
/* 反查：这条付款通知书被哪张集采合同引用了（**派生** —— MOD-03 的「已关联」态不是新增字段） */
const jcRefOf=nid=>JCs.find(j=>(j.payments||[]).some(p=>p[3]===nid))||null;
/* 「关联集采合同」的**候选出口**（2026-09-13 用户口径 + **2026-09-14 收窄**）：**只列该付款通知书行"实际项目（仓库）"下、且「供应商」等于该行「集采实际供应商」的合同**。
   项目键 = 该行的**归属档案行的仓库名**（`ntProjKey`，§2.7.4）—— 与 `JC_COLS.proj` **同一个键空间** ⇒ 直接判等。
   ⭐ **供应商收窄**（§6.6.3 附则）：候选 = 「本项目 ＋ 已匹配到的那家供应商」的合同；
      **该供应商为空**（未匹配 / 未填）时**不按供应商过滤**（= 回落到"本项目全部合同"，否则什么都选不了）。
   ⚠️ **例外：当前已关联的那张合同无条件保留在候选里**（即便项目 / 供应商对不上）—— 否则弹窗无法回显"现在关联的是谁"，
      "改 / 解绑"会看起来像"从没关联过"（与「付款流水『付款项目』候选 = 现有 ∪ 当前已选」同一套做法）。
   ⚠️ 唯一出口：弹窗候选、空态判定、提交兜底**都从这里出**，别在别处再写一遍过滤条件。 */
const jcLinkCands=n=>{ const k=ntProjKey(n), cur=jcRefOf(n.id), sup=String(n.sup||'').trim();
  let list=JCs.filter(j=>j.proj===k);
  if(sup) list=list.filter(j=>String(j.supplier||'').trim()===sup);
  return (cur&&list.indexOf(cur)<0)?list.concat([cur]):list; };
/* MOD-03「集采实际供应商」列内的关联区（入口就近放该列 —— 它本就是这行集采单据的专属格） */
const jcLinkCell=n=>{ const j=jcRefOf(n.id);
  return j
    ? `<span style="display:flex;align-items:center;gap:calc(5px * var(--fscale));white-space:nowrap">${tag('已关联 '+j.id,'in')}<button class="btn sm" data-act="jcLink" data-id="${n.id}" title="改关联到别的合同 / 或解绑（关联关系存集采合同付款子表，与 R8 同一份记录）">改 / 解绑</button></span>`
    : `<button class="btn sm" data-act="jcLink" data-id="${n.id}" title="把这行集采通知书关联到一张集采合同（与「从付款域引用」写同一份记录、双向可见）">关联集采合同</button>`; };

/* ===== 集采供应商自动匹配（§6.6.3 · `DEV-J-01` 2026-09-14 改裁）=====
   ⚠️ **反着匹配**：不是"先从单据名里切出简称、再拿去比全名"，而是 **拿候选池去探测单据名** ——
      因为单据名格式不受约束，**"简称在哪、多长"事先不可知**，只能反过来试。
   候选池 = 本项目（仓库名 = 该行归属档案行，`ntProjKey`）集采合同的「供应商」去重（按全名）。
   探测等级（先长后短，取**命中的最高等级**那一批）：① 全名整体 ② 4 字片段 ③ 3 字片段 ④ 2 字片段。
   ⚠️ 准确**不靠算法**、靠"多命中必须问人"这道闸 —— 假阳性的代价只是**多问一次**，不会填错。 */
const SUP_LVL_NAME=['','全名','4 字片段','3 字片段','2 字片段'];
/* ⭐ `M5-5`（2026-09-19）：**候选池 / 片段 / 探测这三个函数已从壳里删掉** ——
   判定搬到了后端 `app/mod03_notice/sup_match.py`（端点 `POST /api/m03/actions/sup-match`）。
   ⛔ **别再在壳里写第二份**：
   ① 两份判定 = 迟早漂移（改一处忘另一处，谁都不知道哪个对）；
   ② 这套规则里有一条**"写错不报错、只是悄悄换了语义"**的（片段长度 = `6 − level`）——
      壳里**真写错过**成 `level + 2`（⇒ 等级越高片段越长、"先长后短"失去意义）而**代码照样跑**；
      那种错**只有后端断言钉得住**。
   ⚠️ `SUP_LVL_NAME` **保留**：仅作**兜底**（后端正常会回 `level_name`；保险起见给个本地名）。 */
/* 待确认标记（**不静默落库**）：id → 自动预填值。点「确认」才转正式值；改一次、重抓、改分类都清 */
const SUP_SUG={};
/* MOD-03 自动化入口按钮（放在「集采实际供应商」列内，与关联区同格） */
const supAutoCell=n=>{ const s=SUP_SUG[n.id];
  return s
    ? `<span style="display:flex;align-items:center;gap:calc(5px * var(--fscale));flex-wrap:wrap;white-space:nowrap">${tag('自动匹配 · 待确认','wn')}<button class="btn sm pri" data-act="supAccept" data-id="${n.id}" title="确认采用自动匹配到的供应商（确认后转正式值）">采用</button><button class="btn sm" data-act="supReject" data-id="${n.id}" title="不采用 —— 清空待确认值，回到手工录入 / 重新匹配">不采用</button></span>`
    : `<button class="btn sm" data-act="supMatchRun" data-id="${n.id}" title="按 §6.6.3 用单据名中的供应商简称在本项目集采合同供应商里做子串匹配（1 家预填 / 多家让你选 / 0 家手工指定）">自动匹配</button>`; };
const supHas=n=>Object.prototype.hasOwnProperty.call(SUP_SUG,n.id);

/* ===== 再次导入的合并策略（§4.2.7 · 2026-09-14 用户拍板「方案乙」）=====
   问题：i8 导入后单据被改动（审批金额改了 / 单据撤了），再次导入会发生什么？
   ⚠️ 先纠正一个易错读法：§4.2.5 里「审批金额 / 付款金额（源）—— ✗ 不被覆盖（源数据）」
      **真实含义是"不被人工改覆盖"，不是"不被 i8 覆盖"** —— i8 的新值必须落到这两个源字段上，
      否则再次导入就等于没抓（用户会以为系统坏了）。
   ⇒ 于是**真正的风险不在源字段，而在"跟着源字段长的旁路字段"**：
      「统计结算金额 / 统计付款金额」的上限 = 审批金额（全站铁律「统计两金额 ≤ 审批金额」），
      一旦审批金额被 i8 **调小**，人工填过的统计值就可能**越界** —— 而这条铁律的拦截
      只发生在"**手改时**"，**拦不住"上限自己掉下来"**。

   ⭐ 方案乙 = **「未手改的跟随、手改过的保留」**（判据 = 留痕，不新增状态位）：
      `hasT(n,'统计结算金额')` / `hasT(n,'统计付款金额')` 即为「这条人工改过没有」的**唯一事实来源**
      —— 复用既有留痕，**不为"是否手改"另开一个字段**（那会是一份必然静默过期的副本）。
      ① 未手改 ⇒ **跟随**新审批金额（重算为新上限）； ⇒ 解决"审批被改小后越界"
      ② 已手改 ⇒ **保留**人工值，**但若越界则挂提醒**（`IMP_WARN`），让人来定 ——
         **绝不自动改写人工判断**（油卡抵扣那类值改掉就是丢业务数据）。
      ③ 审批金额「被改大」时也**不无脑跟随**：已手改的照样保留（否则凭空生出欠款，见下）。
   ⚠️ 欠款的连锁：审批金额调大而统计值跟随 ⇒ 台账里**突然多出欠款，但没多付一分钱**。
      这正是"保留人工值"要保护的东西 ⇒ 方案乙的 ② 顺带把这一坑堵掉。

   ⭐ 「i8 已撤单」：i8 那边**删掉整张单据**（撤单）时，本轮**不硬删** —— 标 `IMP_GONE` 保留可查，
      但**退出全部统计**（与「剔除」同思路：保留标记、不销毁数据）。
      ✅ 口径已定案（2026-09-14）⇒ **有牵涉则硬拦**（见下 `ntVoidJoint`），**不做「删除付款通知书」按钮**。

   ⚠️ 本模块只做**判定与提醒**，不落库 —— 原型里用 `IMP_WARN` / `IMP_GONE` 两个明面表承载，
      由 `fetchNtOk`（= 用户点「按 X 月抓取」）驱动；`rollback` 里清空。 */
const IMP_WARN={};   /* nid → [{field, why}]：再次导入时**人工值越界**的提醒（未改，只提醒） */
const IMP_GONE={};   /* nid → {date,code,doc}：i8 已撤单（本轮不再抓到的行）—— 标记保留、不销毁 */
const impHasWarn=n=>Object.prototype.hasOwnProperty.call(IMP_WARN,n.id);
const impHasGone=n=>Object.prototype.hasOwnProperty.call(IMP_GONE,n.id);
/* ⭐ i8 撤单行的「退出全部统计」唯一出口（2026-09-14 用户口径 · 见《说明书》§4.2.7）——
   口径：i8 侧**真删了**该单据 ⇒ 标「i8 已撤单」保留可查，但**退出全部统计**（与「剔除」同思路）。
   ⚠️ **不可复原（终态）**：单据号必变 ⇒ 不做"下次抓回来自动认回同一行"。
   ⚠️ **有牵涉则硬拦**：该行若已挂付款流水 / 集采关联 ⇒ **不允许静默退出统计**
      （`ntVoidJoint` 判它有没有牵涉；界面提示"请先撤销付款 / 解绑关联"，行留列表 + 带警示）。
   ⭐ 统计侧一律用 `ntLive(n)`（= 未剔除 **且** 未撤单）取"有效行"，**不要再手写 `!n.excl`** ——
      否则新增"撤单"这一档时，会有十几处统计出口漏掉它（正是本项目反复踩的"同一事实多处写"）。 */
/* ⭐ 后端的「i8 已撤单」标记优先（`notice-list` 的 `is_revoked`）；未接线时回落原型的 `IMP_GONE` */
const ntVoid=n=>!!n.revoked||impHasGone(n);
/* 该撤单行有没有牵涉（已挂付款流水 / 集采合同关联）⇒ 有的话不许静默退场 */
const ntVoidJoint=n=>ntVoid(n)&&(paidOf(n.id)>0||!!jcRefOf(n.id));
/* 统计口径下的"有效行"：未剔除 且 未撤单（撤单行一旦有牵涉则**仍算有效**，直到人处理完） */
const ntLive=n=>!n.excl&&(!ntVoid(n)||ntVoidJoint(n));
const ntLiveRows=()=>NO.filter(ntLive);
/* ⭐⭐ 「可进入**付款批次**的候选行」唯一出口（2026-09-14 用户裁定 · 甲案）——
   = **未剔除 且 未撤单**。
   ⚠️ **与 `ntLive` 有意不同、不要合并**：`ntLive` 把「撤单但有牵涉」的行**仍算有效**
      （它**仍进统计**，不许静默丢账，§4.2.7）；但这类行**绝不允许进付款批次** ——
      它的单据在 i8 侧**已被删除**，给它付款 = **把牵涉加深**，与 §4.2.7 给的出路
      （「**请先撤销付款 / 解绑关联**」）方向相反。
   ⚠️ 凡「**勾选 → 付款**」这条链上的准入判据（全选 / 按计划勾选 / 全选框状态回显 /
      付款窗口取行 / 付款提交）**一律走本出口**，不要再手写 `!n.excl` 或 `ntLive` ——
      漏一个出口 = 一条把「已作废的单」送进付款的路（2026-09-14 实测就是这么漏的）。 */
const ntPayCand=n=>ntLive(n)&&!ntVoid(n);
/* ⭐ ⑤ 「**集采未关联**」也**不可付**（§4.4.3 · 用户 2026-09-24 口述「不关联不允许付款」，**无例外**）。
   ⚠️ **判定主人 = 后端**（`mod03_notice/domain.PayRow.block()` 的 `jc_unlinked`）——
     本函数只是**同一条件的壳侧镜像**：付款按钮要在"点之前"就禁用（§4.4.4「前置禁用，不是点了才拦」），
     ⛔ 不能等提交才拦。⇒ 要改口径**回后端改**，这里跟着改，两处必须同进同退。
   ⚠️ 「已关联」的判据 = `jcRefOf(n.id)`（关联关系就存在集采合同的**付款子表**里，§6.6.2）——
     与行内「查看关联」按钮、`ntHasLink` **同一个出口**，⛔ 不另写一份。 */
const ntJcUnlinked=n=>n.cat==='集采'&&!jcRefOf(n.id);
/* 「本次不可付」的**唯一出口**（`''` = 可付）—— 与后端 `PayRow.block()` **逐条对应**：
   ① 审批状态非「已批」· ② 本次应付 ≤ 0 · ⑤ 集采未关联。
   （③ 已剔除 / ④ i8 已撤单在 `ntPayCand` 那层就被挡出批次，⛔ 不在这里再判一遍。）
   ⚠️ 付款窗口里**画行 / 算禁用 / 提交兜底**三处一律走它，⛔ 别再手写一遍条件。 */
const ntPayBlock=n=>n.astat!=='已批'?`审批状态「${n.astat||'（空）'}」非「已批」`
  :(payEff(n)<=0?'本次应付为 0（审批金额 − 已付金额）'
  :(ntJcUnlinked(n)?'集采未关联合同':''));
/* ⭐ 行内**可勾选**的唯一出口（2026-09-21 修 —— 修的是「恢复剔除」的死锁）。
   ⚠️ **勾选 ≠ 能付款**：勾选集服务**两个**批量动作，所以"能勾"与"能付"是两件事：
     · 「批量付款」⇒ 只有**付款候选**能进（闸在 `batchPay` / `batchPayOk`，⛔ 不在这里）；
     · 「恢复剔除」⇒ 只对**剔除行**生效（§4.2.2；且只恢复「人工批量剔除」那一档）。
   ⚠️ 曾把勾选框直接钉死在 `ntPayCand` 上 ⇒ 剔除行**永远勾不上**，而「恢复剔除」又要求
      「必须勾选」才生效 ⇒ **两道门互锁、恢复这条路根本走不通**（用户 2026-09-21 报障）。
   ⇒ 这里 = **付款候选 ∪ 剔除行**。⛔ 别再把付款闸挪到勾选框上；两件事分开才对
      （付款闸在批量付款那一步，且那里还有一道兜底，防"勾上之后才被标撤单"的状态错位）。 */
const ntSelectable=n=>ntPayCand(n)||!!n.excl;
/* ⭐ 列表「分类」列 / 行样式的**唯一分档出口**（2026-09-14 用户口径：按来源分档、两者不相混）：
   · 剔除行 → `剔除`
   · i8 已撤单行 → `i8 已撤单`（有牵涉时**仍留列表 + 带警示**，提示"请先撤销付款 / 解绑关联"）
   · 正常行 → 空（分类下拉照旧）
   ⚠️ 撤单行**不写 `n.excl`** —— 它没被剔除；判据永远是 `ntVoid`（不新增枚举值、不改 `ENUMS.cat`）。 */
const ntArchTag=n=>n.excl?tag('剔除','dg'):(ntVoid(n)?tag('i8 已撤单','wn'):'');
const ntArchCls=n=>n.excl?'ex':(ntVoid(n)?'ex ntvoid':'');
/* 该行是否被「统计结算金额 / 统计付款金额」手改过（留痕 = 唯一事实来源，两个字段各判各的） */
const impManSS=n=>hasT(n,'统计结算金额');
const impManSP=n=>hasT(n,'统计付款金额');
/* ⭐ 合并一条：`src` = 本次抓回来的 i8 源值（审批金额 / 付款金额(源)）。
   返回要写进 toast 的提醒文案数组（空 = 无事）。
   ⚠️ 只在**值真的变了**时才动 —— 值没变就什么都不做（否则每次抓取都"重算"一遍，假动作一堆）。 */
const impMerge=(n,src)=>{
  const oldAp=N2(n.approve), newAp=N2(src.approve);
  const msgs=[];
  if(newAp!==oldAp){
    /* ① 源字段：无条件跟随 i8 新值（"不被覆盖"只针对人工改，不针对 i8） */
    n.approve=newAp; n.pay=N2(src.pay);
    /* ② 旁路字段：未手改 ⇒ 跟随；已手改 ⇒ 保留 + 越界则挂提醒 */
    [['ss',impManSS(n),'统计结算金额'],['sp',impManSP(n),'统计付款金额']].forEach(([k,man,label])=>{
      if(man){                                              /* 手改过 ⇒ 保留人工值 */
        if(overCap(n[k],newAp)) msgs.push(`${label} ${M(n[k])} > 新审批金额 ${M(newAp)}（人工值已保留，请你定夺）`);
      } else { n[k]=newAp; }                                /* 未手改 ⇒ 跟随新上限 */
    });
    if(msgs.length) IMP_WARN[n.id]=msgs;
    else delete IMP_WARN[n.id];
  }
  return msgs; };
/* ⭐ 演示用的「i8 本次返回的审批金额」——**只对特定样本给出改动**，其余返回原值（= 无变化）。
   N05：i8 把审批金额**调小**（触发"人工值越界 → 挂提醒"）
   N08：i8 把审批金额**调大**且该行**未手改**（触发"跟随" + 验证不会凭空生欠款）
   其余一律返回 `null`（= 本次无变化）⇒ 保证断言可复现、也不污染别的样本的既有期望值。 */
const impDemoAp=n=>{
  if(n.id==='N05') return N2(n.approve-10000);      /* 调小 1 万 */
  if(n.id==='N08') return N2(n.approve+20000);      /* 调大 2 万（该行未手改 ⇒ 统计值应跟随） */
  return null; };/* ⚠️ **列头一律只写列名**（2026-09-13 用户口径：列名里的括号注释**全部删除**）——
   原先那 5 处「（展示名）/（仅集采可填）/（i8 只读 · 手动行可改）/（本次应付 · 自动）/（已付款口径）」
   **信息并没有丢**：它们在**对应单元格的 `title`** 里本来就各有一份（鼠标悬停即见），写在列头上只是平白撑宽表格。
   `✎` = 该列可手改（**保留**，用户本次只要求去括号）。
   ⚠️ **列宽用 `style="width:…"` 给"提示值"** —— `table.dt` 是 `width:100%` + 默认 `table-layout:auto`
   ⇒ **有余量时按提示分配、内容长了仍可撑开、真放不下由 `.tw` 横向滚动**（即"自适应"，不写死宽）。
   ⚠️ 表头 HTML 除上述两件事外**一字不改**：`applySorts` 靠表头判可排性（`NOSORT_COL` 认「操作」「处理」）
   ⇒ `<th>操作</th>` 的纯文本必须保持原样；加 `style` 不影响它（`applySorts` 原样保留 `th` 的既有属性）。 */
const NT_THEAD=`
      <th class="ctr fl" style="width:34px"><input type="checkbox" class="chk" id="pickAllBox" data-act="pickAll" title="全选 / 取消全选（仅当前筛选结果）"></th>
      <th style="width:96px">单据日期</th><th style="width:126px">单据编码</th><th>付款项目</th><th style="width:78px">分类</th><th>单据名称</th><th>业务类型</th><th>收款单位</th>
      <th style="width:152px">集采实际供应商</th><th style="width:78px">录入人</th><th style="width:112px">审批金额</th><th style="width:112px">付款金额 ✎</th>
      <th style="width:106px">已付金额</th><th style="width:112px">统计结算金额 ✎</th><th style="width:112px">统计付款金额 ✎</th><th style="width:74px">审批状态</th><th style="width:82px">付款状态</th><th style="width:152px">操作</th>
    `;

/* ⭐ 付款通知书「操作」列（2026-09-14 用户口径：「这列现在是空的，能加什么」）——
   ⚠️ **i8 抓取行的「编辑 / 删除」永久不开放**（源数据只读是铁律，§4.2.5；加了就是给一个必然被拒的按钮）
      ⇒ i8 行的操作**只能是"对这条记录在本系统的处置"**，不是"改 i8 源数据"。
   三件事的来源：
   ① **手动行**：编辑 / 删除（§4.2.6，只对手动行开放 —— 现状不变）。
   ② **撤销付款**：入口原本只在「付款流水与欠款统计」页，但**用户是在这一页发现付错的**
      （状态仍「未付清」/ 金额不对）⇒ 跨页找入口违背「就近」。此处**不新开口径**，
      只是把 §4.4.5 已有能力就近化：仍弹原因框、仍留痕、仍回退已付金额、仍按审批金额重判。
      ⚠️ **仅"有生效流水"时才出**（`paidOf > 0`）—— 没付过的行不给撤销按钮，免得空点。
      多条流水时点它 → 打开流水页并**只筛出这一单**（由 `ntFlows` 落筛选），逐条撤。
   ③ **查看关联**：从通知书**反查"这笔钱付到哪去了"** —— 纯查询、零口径风险。
      有集采关联（`jcRefOf`）或 有流水 才出；两者都没有时不给按钮（无内容可看）。
   ⚠️ 顺序固定：手动行徽标 → 编辑/删除 → 撤销付款 → 查看关联。 */
const ntHasFlow=n=>N2(paidOf(n.id))>0;
const ntHasLink=n=>!!jcRefOf(n.id);
const ntActCell=n=>{
  const L=[];
  if(n.manual) L.push(`<span class="tag t-in">手动</span> <button class="btn sm" data-act="ntEdit" data-id="${n.id}" title="编辑这一行手动新增的通知书（一切信息可改；「统计结算金额」恒 0 只读）">编辑</button> <button class="btn sm dg" data-act="ntDel" data-id="${n.id}" title="删除这一行手动新增的通知书（删除前列影响范围）">删除</button>`);
  if(ntHasFlow(n)) L.push(`<button class="btn sm dg" data-act="ntRevoke" data-id="${n.id}" title="撤销这笔已登记的付款流水。撤销必须填原因并留痕；撤销后「已付金额」回退、状态按「已付金额 ≥ 审批金额」重判（§4.4.5）">撤销付款</button>`);
  if(ntHasLink(n)) L.push(`<button class="btn sm" data-act="ntTrace" data-id="${n.id}" title="查看这行通知书的关联与去向：集采合同关联、已登记付款流水（只读，不改任何数据）">查看关联</button>`);
  return L.length?L.join(' '):'<span class="mut">—</span>'; };

