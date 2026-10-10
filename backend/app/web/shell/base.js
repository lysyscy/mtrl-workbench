/* shell/base.js —— 壳的**独立件**（`P2-a` 拆件 · 2026-09-28 · 台账 `TAIL-164`）：公共常量 · 纯函数 · 表头排序内核（原 §1 工具层 / §1.5 表头排序 ＋ §0 里的数据常量）。
 *
 * ⭐ **为什么单开一件**：这三章是**谁都要用**的底座（金额 / 日期 / 枚举 / 取值出口 / 排序内核）⇒ 单开一件，改页面时不必读它。
 *    `index.html` 原来一件套 4000 行（CSS ＋ HTML ＋ 内联脚本混装）⇒ 改一处要翻三个区
 *    （本会话两次白屏的同一个根）。本件是「**只拆非切片**」那一批里的一件。
 * ⛔ **本件不许碰**：任何 `V.<原型页>` 切片（它们**留在 `index.html`** —— 计划 §23 的口径，
 *    `ui_parity` 的 `U1` 逐行比它）· 口径判定（判定全在后端）· 界面文案的主人。
 * ⚠️ **加载顺序**：`index.html` 的 `<script src>` 顺序即真源 —— 本件排在 `actions.js` **之前**
 *    （`actions.js` / `core.js` 里有些表**加载期就求值**到本件的常量）。⛔ 别调顺序。
 * ⚠️ 本件的代码是**原样搬出**（逐字未改，含注释）；来历与搬法见计划 §15 `TAIL-164`。 */

const PJ_COLS = ['id','name','disp','full','phid','status','type','parent','kw','ord'];
/* ---------- 账号（§1.5 角色与权限） MOD-15 ----------
   口径（§1.5.1 = 最终口径）：账号数 2 个 · **两人权限无区别** · 用户本人为**管理员**、可管理其他账号（建号 / 改密）。
   §1.5.2：系统外（项目端 / 会计 / 资产处 / 大领导 / 供应商 / 班组）**一律不设账号**。
   ⇒ 故本页**不设角色 / 权限配置** —— 权限无区别，配了也没有区别。 */
const U_COLS=['id','acc','name','role','status','last','pwd'];
/* ⚠️ 行形状（`adaptUser` 产出，与 `U_COLS` **逐位对应**）：`id · acc · name · role · status · last · pwd`
   ⚠️ `U_COLS` **暂留** —— 它还被 `ACT.userAddOk`（**原型**建号写路径）用着；
      那个动作在**片 4b** 改成调 `/api/m15/actions/create` 之后，`U_COLS` 才能删。
   ⭐ **2026-09-20 `m15` 已接后端** ⇒ 原先的演示数组 `U_RAW` **已删**
   （⛔ 不用原型模拟数据：那会让人以为"页面上看到的就是库里的"）。
   ⛔ `pwd` **永远是空串** —— 列表接口**不带密码**（要看走「查看密码」动作，§1.5.1 明文裁定的唯一出口）。 */
/* ---------- 仓库 / 收发结存（§5.3.2） MOD-07 ---------- */
const WH = [
  ['W1','华能德州热电联产项目仓库',37,1010.78,41700.94,41700.94,1010.78],
  ['W2','临沂钢铁余热发电项目仓库',209,20289.57,115557.82,118655.72,17191.67],
  ['W3','江苏新沂生物质发电项目仓库',22,0,27737.11,27737.12,-0.01],
  ['W4','内蒙乌兰察布风光储一体化项目仓库',70,-0.02,1006008.09,1006008.10,-0.03],
  ['W5','山西长治焦化升级改造项目仓库',37,0,185596.47,0,185596.47],
  ['W6','安徽滁州垃圾焚烧发电项目仓库',151,0.02,277396.42,277396.42,0.02],
  ['W7','河南漯河食品产业园供热项目仓库',148,0.03,229622.56,229622.56,0.03],
  ['W8','山东邹平铝业项目仓库',1,0,1526.16,1526.16,0]
];
/* 焊材 / 气体提取（`R22` · §5.3.3）—— **按月存**（2026-09-13 用户口径）：
   ① 「实际不需要显示单独的表」—— 这部分数据的**唯一去向就是月度会大表**（大表那两列 = 系统自动填）；
   ② 本页那张表退化为**核对工具**（"防止数据出问题、还是要一个表格来把控"），不再是独立产出；
   ③ `EXTM[核算年月] = { 焊材:[…], 气体:[…] }`，每项 = `[仓库名, 金额]`。
   ⚠️ 原先这里还有 `EXTRACT = EXTM['2026-08']` 的**已验收基线别名** —— 已随演示块一并删除
      （它指向的正是演示数据；取数口径现在**唯一出口 = 后端 `/api/m07/extract`**）。 */
let EXTM = {};   /* ⭐ 已接后端：由 `reloadM07()` 从 `/api/m07/extract` 转形填充
   （演示块 3 个月 ＋ 已失效的 `EXTRACT` 别名一并删除；取数口径唯一出口 = 后端 `extract`）。 */
/* 提取表「结余」列的**手工录入值**（2026-09-18 用户裁定 甲：结余 = **历史结余 · 由用户手工录入**，
   系统没有任何来源）—— 与 `EXTM` 分开：⚠️ 粒度 = **类别 × 仓库 · 不按月**。
   ⭐ 已接后端：由 `reloadM07()` 从 `/api/m07/extract` 的 `balances` 转形填充（演示值不搬进来）；
   ⭐ **未录入的键不出现**（域值 `null`）⇒ 导出里如实留空；**`0` 是合法录入值**。 */
let BAL_EX = {};
let EXT_ANNUAL = {}, EXT_STATE = {loaded:false,error:'',year:''};
/* 结余列的性质说明 —— **唯一出口**（表格 `title` 与表下说明都用它，⛔ 别在别处再写一遍）。 */
const EXT_BAL_NOTE = '2025-11及之前金额由用户手工录入，计入合计（未录入留空；0 是合法值）';
/* 结余取数出口：**未录入给 `null`**（不是 0 —— 0 会被读成"确实为 0"）。 */
const extBalOf = (kind, wh) => { const m = BAL_EX[kind]; const v = m ? m[wh] : undefined; return v === undefined ? null : v; };

/* ---------- 付款通知书（ENT-02） MOD-03 ---------- */
/* manual = 「手动新增行」标记（2026-09-12 新增）：i8 抓取行为 undefined、手动新增行为 true。
   用途三处：① 列表打「手动」标签 ② 只对手动行开放「编辑 / 删除」 ③ 手动行的「统计结算金额」恒 0 只读。
   ⚠️ 追加在**末尾** —— `O(arr,NT_COLS)` 按位置取值，已有 19 元素的行 `manual` 自然为 undefined。 */
const NT_COLS = ['id','date','code','proj','doc','biz','recv','entry','approve','pay','ss','sp','cat','astat','excl','exrule','sup','trail','planId','manual'];

/* ---------- 付款流水 MOD-05 ---------- */
const FL_COLS = ['id','nid','date','amt','method','remark','op','voided','reason'];
/* 付款流水的筛选状态（R4：改动即时生效、无「应用」按钮）
   ⭐ 2026-09-13 用户口径：与 MOD-03 / MOD-04 **同一逻辑 —— 默认按「当前核算月」核算**，
     一个月内流水有限 ⇒ **不做分页**（分页取舍见 `demo/设计规则` §六 第 28 条）。 */
let flf={ym:bjMonth(),projs:[],method:'全部',state:'全部',q:''};
/* ⚠️ 关键词**不随输入即时生效** —— 只在点「搜索」按钮时读取输入框（用户口径 2026-09-13：
   「关键词搜索右边加一个搜索按钮，并取消掉其他动作触发的搜索」）⇒ `flQ` 刻意**不挂 `data-act`**（走不到委托层）。 */
/* 付款统计（《说明书》§4.5 场景四的「付款」侧）：粒度 = 月 / 周（周 = 周一 ~ 周日） */
let pst={gran:'周',ym:'',year:0,q:''};   /* ⭐ 2026-09-13 用户口径：付款统计**默认粒度 = 「按周」**（原为「按月」） */

/* ---------- 付款计划（ENT-03） MOD-04 ---------- */
const PL_COLS = ['id','ym','proj','docNo','flowAmt','monthAmt','date','method','remark','forced','forceRemark','manual'];
/* ym = 「导入时选定的年月」：导入前先选月份，本批数据的年月 = 所选月。
   **跨月允许完全相同、不去重不覆盖**；**同月同一单据号不得两行**（空单据号不参与判重）。
   ⚠️ 审查结果**不再存字段** —— 一律由 `plRev()` 按 §4.3.4 取数口径**实时比对**得出（2026-09-12）。
   ⚠️ `manual` = **手动行**标记（§4.3.3.1 · 2026-09-16 用户口述新增）：手动行与导入行**同住一表**、
      进**同一条审查链路**（判定按行实时派生、不看来源）、**导入不清理它**（§9.5）。 */

/* ---------- 期初占位行（§4.5.2） MOD-05 ----------
   `cat`    = **分类**（辅材 / 机械）：期初占位行**按其分类进入对应的欠款池**，
              也是「逐月欠款台账」按口径取期初行的依据（辅材台账只带辅材的期初）。
              ⚠️ 只有**辅材 / 机械**两种 —— 集采的欠款由集采台账负责（§6.4.4），不在这里。
   `cutoff` = **截止年月**（"截止 YYYY 年 M 月底"）：它是逐月欠款台账的**第 1 行**，也是**逐月的起点**
              （台账从 cutoff 的**次月**开始按月出行）。 */
const LG_COLS = ['id','proj','cat','settle','paid','cutoff','remark','op','date'];

/* ---------- 库存单据明细（§3.4） MOD-08 ---------- */
const IV_COLS = ['id','docNo','seq','dir','mat','spec','unit','qty','px','pi','amt','tax','biz','cp','dd','ad','wbs','cbs','wh','pf','c5'];
/* ---------- 调整单（ENT-04，打在单据行上、不被 i8 导出覆盖） MOD-08 ---------- */
const AD_COLS = ['id','ivid','newAmt','remark','op','time','trail'];
/* ---------- 机械费 · 源头 = **过程资料的机械 6 列**（2026-09-13 口径变更；`MACHM` 已删除） ----------
   ⭐ **口径**：机械费的**源头数据在「过程资料的机械 6 列」**（原设计在"机械费报表"，因该报表价值不高、
      暂挂此处 —— 《说明书》§5.6 备查口径随之更新）。
   ⭐ **机械费结算金额 = 派生只读** = 该核算月的「**外租零租含税 ＋ 外租包月含税**」（第 3 / 第 4 列）。
   ⭐ **「租分公司设备」「内租设备」（及外租不含税两列）不参与付款欠款统计** —— 这两项的付款由
      **会计直接划拨**，不经材料科的付款欠款流程；它们仍存在于过程资料 / 月度会大表 /（将来的）机械费报表。
   ⇒ 取数一律走 `machSettleOf(仓库名)` / `machExtRent(仓库名,月)` ⇒ **换口径只改这两个函数**，
      看板 / `MOD-10` / 逐月欠款台账 / `debts()` 全都不用动。
   ⚠️ **`MACHM`（机械费·按月手填）已删除** —— 结算不再手填，**手填的位置下移到过程资料的机械 6 列**。 */
const machExtRent=(wh,ym)=>N2(MACH6_RENT.reduce((a,i)=>a+mach6Arr(wh,ym)[i],0));   /* ⭐ 该月**机械费结算金额**（派生） */
const machSettleOf=wh=>N2(Object.keys(MACH6[wh]||{}).reduce((a,k)=>a+machExtRent(wh,k),0));  /* ⭐ 该项目结算合计 */
/* 六列机械费（外租分零租/包月、含税/不含税各一列，§5.2.2）—— **源头表**，`键 = 仓库名`（§2.7.4）、`按核算月`。
   列序：0 租分公司设备 · 1 内租设备 · **2 外租零租含税** · **3 外租包月含税** · 4 外租零租不含税 · 5 外租包月不含税。
   ⭐ 只有 **第 2 / 3 列**进「机械费结算金额」（见上）；其余四列仍是**过程资料 / 月度会大表 /（将来）机械费报表的共通值**。
   ⚠️ 各项目「外租含税」合计刻意与机械通知书对得上：德州 96,000 / 临沂 45,000 / 乌兰 198,000 /
      滁州 74,500 / 长治 121,000（合计 534,500）⇒ 机械欠款 181,000**基线不变**。
   新沂 / 漯河 / 邹平壳 无机械费 ⇒ 不在这张表里（取数回退 MACH6_Z）。 */
/* ⭐ **已接后端**：由 `reloadMech()` 从 `/api/m06/mech` 填充（原先由演示数组生成 —— 已删）。
   ⚠️ **结构刻意与原型一致**（`{仓库名: {核算月: [6 列]}}`）⇒ 下面 `mach6Arr` / `machSettleOf`
     等十几处引用**一行不用改**，只换来源。
   ⭐⭐ 来源**按分界月切**（2026-09-26 用户裁定 · `TAIL-107`）：**历史段（≤ 截止核算月）= 过程资料导入的
     快照值**；正式段 = `proc_mech_manual`（旁路表：重抓 i8 / 重导历史都不覆盖，§5.2.5 ③）。
     ⛔ 判定在**后端**（`domain.column_source`）—— 壳里只管显示。 */
let MACH6 = {};
/* ⭐ `{仓库名: {核算月: 'history'|'formal'}}`（后端 `sections` 给）—— 用来把
   "**历史段不许手录**"在界面上说清（守则 §5.5：不能做的要置灰并说明原因）。⛔ 别在壳里自算段。 */
let MECH_SECTIONS = {};
/* ⭐ 2026-09-28（用户口径：「在过程资料页给历史段加一个标记就好了」）：**该项目机械历史段的截止核算月**
   （= `MECH_SECTIONS` 里最后一个 `history` 月，⛔ 判段只认后端给的分段 —— 壳里不拿截止月比大小）。
   用途 = 过程资料页那句「历史段截至 YYYY-MM，此后为手录段」；无快照 ⇒ 空串。 */
const mechCutLabel=wh=>{ const s=MECH_SECTIONS[wh]||{}; const h=Object.keys(s).filter(k=>s[k]==='history').sort(); return h.length?h[h.length-1]:''; };
const MACH6_Z=[0,0,0,0,0,0];
const MACH6_RENT=[2,3];                                                   /* 进结算的两列：外租零租含税 / 外租包月含税 */
const mach6Arr=(wh,ym)=>(MACH6[wh]||{})[ym]||MACH6_Z;                     /* 某项目某核算月的机械 6 列 */
const mach6Of=(p,ym)=>N2(mach6Arr(p,ym).reduce((a,b)=>a+b,0));           /* 某项目某核算月的机械合计 */
/* ---------- 集采台账（ENT-06/07/08/09） MOD-11 ----------
   口径（2026-09-12 定案）：合同主表 = 18 字段，其中
     · 发票金额 / 贸易公司发票金额 / 付款金额 —— **由各自子表汇总得出**（不再主表直改）；
     · 结算金额 / 欠款金额 —— 系统自动算。
   贸易公司发票与供应商发票**同一套逻辑**：有贸易公司时结算取【贸易公司发票子表合计】，
   无贸易公司时取【供应商发票子表合计】。
   ⭐ **2026-09-13 用户裁定（选「乙」）**：合同主表**新增「项目」字段** ⇒ 共 **19 字段**（§6.4.1）。
     · 键 = **仓库名**（§2.7.4，全站统一）；**合同必有项目**（抓取回来的必带、手工新增时选择）⇒ 不存在"为空"。
     · 用途只有两处：① 本页的「**项目筛选**」（走**通用控件** = 共用项目面板）② 月度会大表
       「**主材累计（含税）**」按项目取集采结算额（§5.7.1；**只计「纳入台账」的合同**）。
     · ⚠️ **表内刻意不设「项目」列**（用户口径 2026-09-13）—— 只有筛选，不展示成列。
     · ⚠️ 字段**追加在末尾**：`O(r, JC_COLS)` 按**位置**取值 ⇒ 老数据行自然为 `undefined`
       （同 `NT_COLS` 的 `manual` 老坑）。 */
/* ⭐ `M5-7`（2026-09-19）：原先这里是一张 12 行的**演示数组** `JC` ＋ 列序 `JC_COLS`
   （`JCs=JC.map(r=>O(r,JC_COLS))` 按**位置**取值）—— **已删**。
   现在 `JCs` 由 `reloadM11()` 从 `GET /api/m11/list` 填充，行形状见壳适配层 `adaptJc`
   （字段名与 `JC_COLS` 时代**完全一致** ⇒ `V.m11` 一行都不用改，`ui_parity` 的 `U1` 零漂移）。 */

/* ---------- 差异登记（§5.8.3） MOD-12 ----------
   口径（2026-09-12 定案）：差异归属**统一为「库存单据」**——差异的修正只改库存单据；
   过程资料里的材料费**引用自库存单据**，随之反映，不独立承载差异。（故 type 不再出现「过程资料」） */
const DF_COLS = ['id','month','type','proj','detail','amount','status','remark'];
/* ⭐ 2026-09-20（`M6` 第一片）：本页**已接后端** ⇒ 原先那张 5 行**演示数组 `DF` 已删**。
   ⚠️ `DF_COLS` **留着**（它在这里只是**行形状说明**，与原型同源）—— 同款的还有
      `FL_COLS` / `IV_COLS` / `AD_COLS`：都不是"还没清掉的残骸"，而是**列清单 / 行形状说明**
      （2026-09-27 批次 7 逐个数过 58 个顶层常量，真死码只有 `TASK`，见下）。
   ⭐ 金额仍**带符号**（+ 上调 / − 下调）—— 这条口径没变，只是主人换成了后端
      `mod08_inv`（调整单）＋ `mod06_proc`（差异表）
      （§5.8.3；判据点 `ACC-DIF-REG-001/001-04`「负数必须放行」）。
   ⚠️ 旧演示数据里"前三条与调整单一一对应"那段说明**已随数据一起删**：真数据由后端给，⛔ 别在这里再举例子。 */
/* ⛔ 原 5 行演示数组 `DF` **已于 2026-09-20 删除**（本页接后端）—— 这里不留任何占位变量：
   名字留着只会让人以为"是不是还得填"，真数据一律来自 `/api/m12/list`。 */
/* ⭐⭐ 2026-09-27（`TAIL-117` 批次 7「残骸清理」）：**这里原有一张 6 行「接口清单表」`TASK`**（`API-01`…`API-06`：
   接口名 / 触发方式 / 数据源 / 用途），**已删**。为什么：
     ① 它**零引用**（`V.*` 一个切片都不用它，`m02` 那两张卡 2026-09-20 起改读**执行记录**真数据）；
     ② 就算它被渲染，内容也是**开发视角**（`API-0x` 代号 ＋ 触发方式 ＋ 数据源）—— 触守则 §3.1/§3.4；
     ③ 它是《说明书》附录 E.1 的**子集**（数据源就是文档本身）⇒ 需要时去查文档，⛔ 别在壳里再抄一份
        （抄一份就是"两份真源"，文档一改它就静默过期）。
   ⚠️ 原先这里还有一句"`TASK` 刻意不接"的注释（`core.js` 的 `reloadM02` 上方）—— 同批一并订正。
   ⛔ 判据：`tests/test_ux_deadcode.py`（这张表 / 那句过期话术都不许回来）。 */
/* ---------- 规则配置 MOD-14 ----------
   ⭐ 2026-09-18 接线（`TAIL-40`）：**剔除规则的唯一主人在后端** —— `exclude_rule` 表，
      经 `/api/m14/rules` 读写；⚠️ **库空 ⇒ 出厂默认**（=《说明书》§4.2.2 那张表）。
   ⚠️ `RULE_EX` = **展示三元组**（规则类别 / 命中值 / 业务含义）—— `V.m14` 直接吃这个形状，
      所以**切片一行未改**；`RULE_RAW` 保留后端原始行（**写动作要 `id`**）；
      `RULE_KINDS` = 可选类别（下拉与真数据同源，⛔ 不用自由文本填类别）。
   ⚠️ **改规则不重算历史**：已产生的剔除标记（`exclude_source=rule`）不受影响、也不重算（§4.2.2）
      —— 后端不重算，前端也不许补一个。
   配置类数据按 §9.4 = **硬删**（不留痕）。
   ⚠️ 分类规则（`RULE_CA`）与小微识别关键字**保持只读**：前者是 §4.2.3 的业务口径（可编辑=允许改口径），
      后者的主人在**项目行**（`MOD-01` 可改），本页只是只读展示。 */
let RULE_EX = [];
let RULE_RAW = [];
let RULE_KINDS = [];
/*: 当前规则值从哪来（`系统配置` / `出厂默认（§4.2.2）`）—— 页面要**如实**告诉用户 */
let RULE_SRC = '';
const RULE_CA = [['①','业务类型 = 付设备租赁款','机械'],['②','收款单位 = 资产处集中采购','集采'],['③','以上都不满足','辅材']];
/* ---------- 月度会大表（§5.7）MOD-07 ----------
   ⭐ 2026-09-13 用户口径（**大改**）：列结构以用户给的**最终模板**为准（20 列，见 `BIG_THEAD`）。
   · 手填列 **6 项**（`BIGCOLS`）：开工时间 / 机械费测算 / 合同（预估）价 / 产值累计（含税）/ 工程用油 / 备注。
   · **取消**「机械费」「产值」两列；「合计 / 使用率 / 产值完成率」改为**派生**（见 `bigRows`）。
   · `BIGVAL[月][仓库名][列]` = 手填值的**唯一存储**（null / 缺省 = 该月未录入）。
     ⚠️ 键 = **仓库名**（§2.7.4；原为「项目全名」，随"项目集合改为多选"一并统一）。
   · 「本月」= **材料报表口径 = 北京时间上月**（`bjMonth(-1)`）—— 月度报表做的是上一个月的账。
   · 本月未录入的格子 → 向前取「最近一次录入值」带入（OPEN-05），黄底标出带入自哪个月、待确认。
   · 列型 `BIGFMT`：`ym` 年月（`YYYY-MM`）· `m` 金额（元 · **非负**）· `t` 文本（备注）。 */
const BIGCOLS = ['开工时间','机械费测算','合同价','产值累计','工程用油','备注'];
const BIGFMT  = ['ym','m','m','m','m','t'];
/* 手填值：`BIGVAL[月][仓库名] = [6 个值]`（与 `BIGCOLS` 同序）；`null` / 缺省 = 该月未录入。
   ⭐ 2026-09-13：「**主材累计（含税）**」**移出 `BIGCOLS`**（由手填改为**派生**，取数走 `bigMatCum`）
     ⇒ 手填列 **7 → 6**，每行的值数组也由 7 元**左移为 6 元**（"工程用油"由 5 → 4、"备注"由 6 → 5）。
   演示数据刻意铺出**三种缺口**（供「上次值带入 / 留空待填」演示）：
   · 德州 / 乌兰 / 滁州：本月 6 格全录 ⇒ 无带入；
   · **临沂**：本月只录了前 2 格（开工时间 / 机械费测算）⇒ 其余 4 格应带入自 `2026-07`；
   · **长治**：本月未录、且 `2026-07` 也没有它 ⇒ 应**回退两级**取 `2026-06`；
   · **新沂**：三个月都没有 ⇒ **留空待填**。
   其余在建项目（邹平 / 唐山海港 / 菏泽 / 未建仓-01 / 潍坊 / 泰州 / 廊坊 / 海阳 / 湛江）全空。 */
let BIGVAL = {};   /* ⭐ 已接后端：由 `reloadM07()` 从 `/api/m07/big` 的 `manual` 转形填充
   （演示块 3 个月已删；⚠️ **全量月份**都要填 —— 「上次值带入」`OPEN-05` 要向更早月份取最近一次录入值）。 */

/* ---------- 特殊费用月报表（§5.5，1 自动项 + N 手填项、可增项、项名可改） MOD-09 ----------
   ⭐ **已接后端**（`TAIL-27`）：本页数据**全部来自 `/api/m09/fee`**（由 `reloadM09()` 填）——
      演示容器 `AWF[核算年月][项目键] = [[项名, 金额], …]`（含 3 个月演示值）**已删**。
   ⚠️ **对外的形状不变**：`awfList()` 仍返回 `[[项名, 金额], …]`
      （原型切片按 `r[0]` / `r[1].toFixed(2)` 取用）⇒ **`V.m09` 切片一行不用改**，转形只发生在这一层。
   ⚠️ 金额后端出**字符串** ⇒ 这里**一律过 `N0()`**：不然 `r[1].toFixed` 直接 TypeError **整页崩**。
   ⭐ **判定一律后端**：自动项取数 / 合计 / 金额合法性 / 项名改法，前端**不再自算**（`awfTotal` 直接读后端回包）。
   ⭐ **「项目」候选与默认项目 `AWF_PJS` / `awfPj` 也只由 `reloadM09()` 落定** ——
      候选与写路径**同源**（后端 `build_candidates` ⇒ 键 = 仓库名 ⇒ `project_by_key` 认得到）：**选得到就写得了**。
      ⚠️ 原先候选读 `pjKeysOfRows(ntPjList())`（档案表全部）——"能显示"但不保证后端认；
      ⚠️ 原先默认项目在**加载时**求值（`(pjSort(ntPjList())[0]||{name:''}).name`）—— `PJs` 异步填充 ⇒
        取数回来时它早已定死成空（**静默失去默认项目**，不报错）⇒ 改由后端回包的 `project` 落定
        （后端 `service._resolve` 已把"没给 / 给了无效值"归一成候选第一个；候选为空时才是空串）。 */
let awfYm = bjMonth(-1);                       /* 默认 = 北京时间上月（§9.2，与后端 `domain.default_ym` 同口径） */
let awfPj = '';
/* ⚠️ 下面这些**只能由 `reloadM09()` 落定** —— `PJs` 是**异步填充**的，
   若仍写成加载时求值（`const x = f(异步变量)`），取数回来时它早已定死成空（**静默空表 / 静默失去候选**，不报错）。 */
let AWF_ROWS = [];        /* 手填项（后端 `manuals`）：`[{index,id,item,amount,…}]` */
let AWF_AUTO = 0;         /* 自动项金额（后端 `auto.amount` = 该核算年月 ＋ 该项目的 `CBS-安文费` 出库） */
let AWF_TOTAL = 0;        /* 合计（后端 `total`）—— 与后端**同一份**算法 */
let AWF_PJS = [];         /* 项目候选（后端 `projects`）—— 键 = **仓库名**（§2.7.4） */
let AWF_CAN_EDIT = false; /* 没有档案行 ⇒ 没有可写的那一份（后端 `can_edit`） */
const awfList = () => AWF_ROWS.map(r => [r.item, N0(r.amount)]);   /* 喂给原型切片的 `[[项名, 金额], …]` */
const awfAuto = () => AWF_AUTO;   /* ⚠️ 原先是前端按 `iv.dd`（**单据日期**）算；口径要的是**核算年月**（`inv_detail.ym`） */
const awfTotal = () => AWF_TOTAL;
/* =====================================================================
   1. 工具层
   ===================================================================== */
const O=(r,c)=>{const o={};c.forEach((k,i)=>o[k]=r[i]);return o};
let PLs=[];   /* ⭐ 已接后端：由 `reloadPlans()` 从 `/api/m04/plans` 填充（原先由演示数组 `PL` 生成 —— 已删） */
const USERS=[];   /* ⭐ 已接后端：由 `reloadM15()` 从 `/api/m15/users` **原地填充**（演示数组 `U_RAW` 已删） */
/* ⭐⭐ 以下三张表**已接后端**（前端壳）：空数组起手，由 `boot()` 用 API 填 —— ⛔ 不用原型模拟数据。
     · `NO` 付款通知书 ← `GET /api/m03/notice-list?period=`（**全量**，筛选用前端 `ntHit` 原样做）
     · `PJs` 项目档案    ← `GET /api/m01/projects`
     · `FLs` 付款流水    ← `GET /api/m05/flows`
   ⚠️ 已在 `WIRED` 里的页**一律取真数据**（侧栏据此标「已接后端真实数据」）；
      ⛔ 已接线的页**不得再回落到原型模拟数据** —— 那是"两句真话互相打架"。
   ✅ **2026-09-21 起 `home`（看板）也进了 `WIRED`**：⑦⑬⑭ 三项接的是**执行记录**
      （`GET /api/home/run-counts`，见 `HOME` 声明处）⇒ ⭐ **全站已无"显示模拟数据"的页**。
   ⚠️ `DFs` 是个例外：它**不接后端**、恒为空数组 —— 它只是 `V.m12` 那个**已撤页**切片的
      对位残留（⛔ 别拿它当"差异待核对"的数；差异现在的载体 = **调整单**，看板 ⑤ 数 `IVs` 里
      有调整单的行）。 */
let NO=[], PJs=[], FLs=[];
/* 当前登录用户：⭐ **由 `applyWho()` 从 `/api/m15/users` 的 `me` 填充**（§1.5.1「用户本人为管理员」）。
   ⭐ `boot()` 一进来就调 `reloadWho()` ⇒ **首屏顶栏就是真身份**（⛔ 不必先进一次用户管理页）。
   ⛔⛔ **初值一律留空，⛔ 不许拿一个人名/账号当占位** —— 本行原先写的是
      `{id:'U01',acc:'zhangwei',name:'张伟',role:'admin'}`：那是**壳里写死的假身份**
      （库里根本没有这个账号，见 `ACC-USR-MGMT-001/001-11`「不得写死成某个名字」）。
      症状 = 用户看到"**同一个人两个名字**"：顶栏先显示「张伟」，进过用户管理页之后才变成真名。
   ⚠️ 刻意**不写成 USERS[0] 的引用** —— 自检回滚会整体替换 USERS 的内容，引用会失效（同「原地复位」的教训）。 */
let CUR={id:'',acc:'',name:'',role:''};
/* ⭐ 主题（`ACC-UI-THEME-001/001-06` 按用户隔离）：**可选清单** ＋ **我这个账号当前用哪套**，
   都由 `reloadM15()` 从 `/api/m15/theme` 填 —— ⛔ 壳里**不写死**主题名单
   （那是第二份真相：后端加一套主题，这里不同步就"选不到"）。 */
let THEMES_LIST=[], CUR_THEME='';
/* ⭐ 每套主题的**配色标本**（住 `V.set` 的「外观主题」卡）：由 `reloadTheme()` 从后端填 ——
   形态 `{name, pri, bg, sf, bd, tx, on}`。⛔ 壳里**不写任何色值**（那是第二份真源）。 */
let THEME_PALETTE=[];
let IVs=[], ADs=[];   /* ⭐ 已接后端：由 `reloadInv()` 从 `/api/m08/inventory` 填充（原先由演示数组 `IV`/`AD` 生成 —— 已删） */
/* ⭐ `M5-7` 起：`JCs` 由 `reloadM11()` 从 `/api/m11/list` **原地填充**（原先的演示数组 `JC` 与列序 `JC_COLS` **已删**；
   行形状见 `adaptJc` —— 字段名与 `JC_COLS` 时代**一致**，所以 `V.m11` 一行没改）。
   ⚠️ 它是 `const` ⇒ 只许改**内容**（`length=0` ＋ `push`），⛔ 不许整支换引用（`JC_PROJ_LIST` 等派生量会失效）。 */
const JCs=[], DFs=[], LGs=[]   /* ⭐ 已接后端：由 `reloadM05()` 从 `/api/m05/debt` 的 `openings` **原地填充**（原先由演示数组 `LG` 生成 —— 已删）；⚠️ 它是 `const` ⇒ 只许 `splice` 原地改 */;
/* ⭐ 2026-09-20：`DFs` **也**接后端了（`M6` 第一片）—— 原先写的是 `DF.map(r=>O(r,DF_COLS))`（演示数组），
   现在由 `reloadM12()` 原地填充。⚠️ 它是 `const`（还跟 `JCs`/`LGs` 写在同一行声明里）⇒ 只许改**内容**。 */
const WHs=WH.map(r=>O(r,['id','name','rows','begin','in','out','end']));
/* ---------- 收发结存：**按月存**（2026-09-13 新增「核算年月」选择，§5.3.2「每个月出一份分仓库表」） ----------
   默认年月 = **材料报表类 = 北京时间上月**（§9.2）⇒ 由 `fWhYm` 承载（初值 `bjMonth(-1)`）。
   · `WHM[核算年月]` = 该月的分仓库收发结存（每仓：行数 / 期初 / 收 / 发 / 结存）。
   · ⭐ `WHs` **刻意保持原样**（= `2026-08` 那一份）—— 它是**仓库主数据 + 已验收基线**，
     还被 `MOD-08` 的「仓库」下拉与既有断言引用 ⇒ **不能让它跟着月份漂**（否则跨页污染）。
     按月取数一律走 **`whRows(ym)`**。
   · 数据自洽：`end = begin + in − out`，且**上月结存 = 本月期初**（跨月连贯）。
   · 2026-08 = §5.3.2 **已验收基线**（675 行 / 8 仓 / 9 文件），**不得改动**。 */
let WHM = {};   /* ⭐ 已接后端：由 `reloadM07()` 从 `/api/m07/settlement` **原地填充**
   （演示块 3 个月已删 —— 原先它是 `2026-08/07/06` 的模拟分仓库结存）。
   ⚠️ 对象身份不变：`whRows(ym)` 与 `V.m07` 都按**当前核算年月**取数（`fWhYm`）。 */
const whRows = ym => WHM[ym] || [];                 /* 收发结存的**按月取数出口**（`MOD-07` 用） */
let fWhYm = bjMonth(-1);                            /* 默认 = 北京时间上月（§9.2） */
/* 自定义排序号的初值 = 建档顺序 1..N（此后由 `editOrd` / `ordUp` / `ordDown` 维护，且始终重编号保持连续） */
PJs.forEach((p,i)=>{ if(p.ord==null) p.ord=i+1; });

const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>[...r.querySelectorAll(s)];
const esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
/* 时间戳的**唯一出口**：一律「补零 + 到秒」（`YYYY-MM-DD HH:MM:SS`）。
   ⚠️ 原先用 `toLocaleString('zh-CN')` —— 它**不补零**（`2026-9-13 8:35:12`），
      与预置留痕里的 `2026-09-18 09:42` 两种格式并存。留痕的用途是"事后查得清"，
      时间格式必须统一、且到秒。 */
const fmtTime=d=>{ const t=d?new Date(d):new Date(); const p=n=>String(n).padStart(2,'0');
  return t.getFullYear()+'-'+p(t.getMonth()+1)+'-'+p(t.getDate())+' '+p(t.getHours())+':'+p(t.getMinutes())+':'+p(t.getSeconds()); };
const now=()=>fmtTime();
/* ROUND_HALF_UP（2 位小数、远离零取整）：先消掉二进制尾噪，再按十进制第 3 位进位。
   ⚠️ 正式实现须按 §9.1 用 Decimal + ROUND_HALF_UP；本原型只用它让取整方向与 HALF_UP 一致。 */
function r2(x){ if(!isFinite(x)||Math.abs(x)>=1e15) return x;
  const neg=x<0, t=Math.round(Math.abs(x)*1e9)/1e9, s=t.toFixed(10), i=s.indexOf('.');
  let n=Number(s.slice(0,i)+s.slice(i+1,i+3));
  if(Number(s.charAt(i+3))>=5) n+=1;
  return (neg?-1:1)*(n/100); }
/* ⚠️ `null` / `undefined` ⇒ 「—」（**不可得 ≠ 0** —— 与后端口径一致：大表的「主材累计」取数口未接入时给 null，若按 `Number(null)||0` 会显示「0.00」= 冒充「确实没有」）。
   ⭐ 对**数字入参**行为**完全不变**（`M(0)`→`0.00` · `M(-1.5)`→`-1.50` · `M(1234.5)`→`1,234.50`）。 */
const M=n=>{if(n==null) return '—'; const v=r2(Number(n)||0); const s=Math.abs(v).toFixed(2); return (v<0?'-':'')+s.replace(/\B(?=(\d{3})+(?!\d))/g,',');};
/* ⭐⭐ 2026-09-27（`TAIL-117` 批次 4 · 守则 §2.3 / §5.7「数字带单位/口径/时间」· §6-8）：
   **KPI / 汇总大数一律带单位** —— 原来 `M()` 只出数字（`83,191,167.72`），单位靠人猜。
   ⚠️ 只给 **KPI 那一格**用；表格里逐格加「元」会把格子撑爆、且列头已说明是金额
      （"要不要给每个金额列头也加（元）"评估过：`*_THEAD` 全在 `ui_parity` 的 `U5` 登记表里
       ⇒ 改它们＝**同批改交付面的原型**，收益低 ⇒ 本批不动，理由记在审计清单 §十 批次 4）。
   ⚠️ `null` ⇒ 仍是「—」（**不可得 ≠ 0**，与 `M` 同口径）〔⛔ 别写成 `M(v)+'元'` —— 那会显示「— 元」〕。 */
const MONEY=v=>v==null?'—':M(v)+'<span class="u">元</span>';
/* 金额规整：NaN 必须原样透出，绝不能被当成 0（否则非法输入会静默把金额清成 0） */
const N2=n=>{const x=Number(n); return isNaN(x)?NaN:r2(x);};
const PCT=n=>(Number(n)*100).toFixed(1)+'%';
const SIG=n=>(n>0?'+':'')+M(n);
const CN='零一二三四五六七八九十';
/* 已删除（2026-09-12）：「全局核算期」概念及 MON / MONL —— 各表默认年月一律走 bjMonth(偏移)。 */

/* 派生：付款流水汇总、状态、欠款 */
/* ⭐ 已付金额 = **后端流水汇总**（`notice-list` 的 `amount_paid`）—— ⛔ 前端**不重算钱**。
   未接线的页（本地无该字段）才回落到原型内存流水，保持原型态可用。 */
const paidOf=nid=>{ const n=NO.find(x=>x.id===nid);
  return N2(n&&n.paidApi!=null ? n.paidApi
    : FLs.filter(f=>f.nid===nid&&!f.voided).reduce((a,f)=>a+f.amt,0)); };
/* 付款状态判定基准 = 审批金额（§4.4.2）
   ⚠️ 已作废、勿用：「按统计付款金额判状态」—— 统计字段只管算欠款、不管判状态
   已付金额 ≥ 审批金额 → 已付清；无「部分付」中间态 */
function statOf(n){ if(n.excl) return '—'; return paidOf(n.id)>=n.approve?'已付清':'未付清'; }
const hasT=(n,label)=>hasTrail(n.trail,label);   /* 留痕读取的唯一出口（形状见上） */
/* 付款金额（本次应付）：默认 = 审批金额 − 已付金额，随付款 / 撤销实时变化。
   人工手改 = 【仅本次会话的临时覆盖】，只写在 payOv 上：
     · 不写 i8 原值 n.pay（源数据永不被改写）
     · 不写库、不影响「统计付款金额」与欠款口径
     · 刷新页面即失效，自动恢复为派生默认
   页面刷新后 payOv 不存在 → 回到派生默认，这正是所要的行为。 */
const payOver=n=>n.payOv!=null;
const payEff=n=>payOver(n)?N2(n.payOv):N2(n.approve-paidOf(n.id));
/* ⭐⭐ **主表那 5 个派生金额列一律读后端派生值**（`M5-7` 判定搬家；唯一出口 = `mod11_jc.domain`）。
   ⛔ 原实现在浏览器里按**子表数组**现算 —— 那是**第二份口径**（早晚与后端分叉），而且
      `/api/m11/list` **故意不给子表明细**（`adaptJc` 里那三个数组**恒为空**）⇒ 算出来**恒 0**。
   ✅ 保留原函数签名 ⇒ `V.m11` 一行都不用改（`ui_parity` 的 `U1` 才能保持 0 漂移）。
   ⚠️ 后端金额出**字符串** ⇒ 过 `N2()`（漏了会让"求和"变**字符串拼接**、合计安静地错）。
   ⚠️⚠️ **`jcInvSum` / `jcTradeInvSum` 原先漏搬了**（2026-09-26 用户报障原话：「宜化项目**发票子表导入成功**，
      但**发票金额没跟着动**」）：它们当时仍按本地子表现算 ⇒ **主表那两列恒显示 0.00**
      （后端其实算对了 —— 实测 `inv_sum` 已是 52235.70 / 358722.46 / 54556.61，页面却全 0）。
      ⇒ 一并改读后端；⭐ 子表弹窗**也**读它：加/删子表行时 `jcAct` 内部会 `reloadM11()`
      （列表随即重拉，含刚加的那张票）⇒ 弹窗合计与主表**同一个数**，⛔ 不必（也**不许**）再按本地数组现算一遍。
   ⛔ 后端键名以 `domain.DERIVED_MONEY_KEYS` 为准：是 **`pay_sum`**，⛔ 不是 `pay`。 */
const jcInvSum=j=>N2(j.inv_sum);
const jcTradeInvSum=j=>N2(j.trade_inv_sum);
const jcSettle=j=>N2(j.settle);
const jcPay=j=>N2(j.pay_sum);
const jcDebt=j=>N2(j.debt);
function debts(){
  /* ⭐ 已接后端：三类 ＋ 合计**一律读 `/api/m05/debt`**（§4.5.1 的唯一出口）。
     ⛔ 原实现在浏览器里按 `NO`/`MACH6`/`JCs`/`LGs` 现算 —— 那是**第二份口径**，
        而且机械会读到**演示数据**（与后端 KPI 打架）。 */
  const d = M05.debt || {};
  const get = c => numOr0(((d.by_category || []).find(x => x.category === c) || {}).amount);
  return {
    辅材: get('material'), 机械: get('mechanical'), 集采: get('jc'), 合计: numOr0(d.total),
    /* 兼容旧字段（别的页可能读）：一律 0（后端不单列这几项了） */
    辅材S: 0, 辅材P: 0, lg辅材: 0, machSettle: 0, machPaid: 0, lg机械: 0,
  };
}
function sums(rows,k){ return N2(rows.reduce((a,r)=>a+(r[k]||0),0)); }

/* UI 原子 */
function toast(msg,ms=2600){ const t=document.createElement('div'); t.className='toast'; t.innerHTML=msg; document.body.appendChild(t); setTimeout(()=>t.remove(),ms); }
let lastModal=null;      /* 最近一次打开的弹窗参数（弹窗内的排序/年月组件需要能重绘弹窗） */
let fetchM=bjMonth();    /* 抓取 i8 付款通知书：本次要抓的年月（默认「北京时间当月」；i8 侧换算为单据日期起止） */
/* ⭐ 2026-09-13 用户口径：**收发结存表与库存单据明细表也按「所选月份」抓取** ——
   三个抓取弹窗共用同一套「按月抓取」形态与同一个月份状态 `fetchM`；
   两个新入口打开时**把默认月份初始化成该页当前所选核算年月**（`fWhYm` / `fIvYm`），用户可改。 */
let fetchKind='nt';      /* 当前抓取弹窗的目标：nt=付款通知书 · wh=收发结存表 · iv=库存单据明细表 */
let payDraft={};         /* 批量付款弹窗的草稿 {单据id: {m:付款方式, a:付款金额}} —— 重建弹窗时不丢已填值 */
let jcLinkSel=null;      /* 「关联集采合同」弹窗里所选的合同 id（草稿；改选择要重绘弹窗 —— 金额比对随之更新） */
let modalOpener=null;    /* D2 焦点归还（2026-09-15）：记住「打开弹窗的那个元素」，关闭时把焦点还回去。
                            ⚠️ DOM-stub（`_smoke`）没有 `document.activeElement` ⇒ 全程防御式，取不到就是 null。 */
let supSel=null;         /* 「选择供应商」弹窗（§6.6.3 多命中）里所选的全名（草稿；改选择不重绘，提交时读 */
let OWN={};              /* 「归属」：付款通知书 id → 项目档案行 id。空 = 待指定（链路 C 尚未判定）。
                            属【付款通知书行】的字段（不是项目档案的字段）；普通项目自动确定，壳全名须判定。
                            落库 + 不被导入覆盖的持久值（正式实现在导入时写入，原型里由弹窗写） */
function modal(o){
  const root=$('#modalRoot');
  lastModal=o;
  modalOpener=(typeof document!=='undefined' && document.activeElement && document.activeElement.focus)
    ? document.activeElement : null;   /* D2：记下触发元素 */
  /* 弹窗内的表格同样支持表头排序：用 sortKey 给每类弹窗一个稳定键
     （不传则按标题推导并去掉数字，保证「已勾选 3 条」这类变化不会换键） */
  const sk=o.sortKey||('modal:'+String(o.title||'').replace(/[\d\s·]+/g,''));
  root.innerHTML=`<div class="mask" data-act="maskBg"><div class="modal ${o.wide?'wide':''}${o.monthPicker?' month-picker':''}">
    <h3>${o.title}<span class="x" data-act="closeModal" tabindex="0" role="button" title="关闭（Esc）">×</span></h3>
    <div class="mb">${applySorts(o.body,sk)}</div>
    ${o.footer===null?'':`<div class="mf">${o.footer||'<button class="btn" data-act="closeModal">关闭</button>'}</div>`}
  </div></div>`;
}
const closeModal=()=>{$('#modalRoot').innerHTML=''; lastModal=null; jcLinkSel=null; if(modalOpener&&modalOpener.focus){ try{modalOpener.focus();}catch(_){} } modalOpener=null;};   /* D2：归还焦点 */
const tag=(t,c)=>`<span class="tag t-${c}">${esc(t)}</span>`;
/* ===== 配置层 · 枚举（值域的**唯一出处**）=====
   值域的主人 = 《材料科业务全流程说明书》附录 E 的 `ENT-*`。本层**只放值域与显示 / 语义色**，
   **不放业务口径**（金额基准 / 判定基准 / 上限 / 留痕范围 → 一律回《说明书》）。
   一处声明 → 三个出口消费：`enumTag`（标签）/ `enumOpts`·`optsOf`（下拉）/ `enumTone`（取色）。
   ⇒ **加一个枚举值只改这里一行**（原先要同时改"判断式 + 标签渲染 + 筛选下拉"三处，漏一处就静默显示空白）。
   ⚠️ 值不在域内时 `enumTag` 退回灰色破折号 —— **宁可显眼地空，也不要静默少一个值**。 */
const ENUMS={
  cat:      {vals:['辅材','机械','集采'], tone:{辅材:'pri',机械:'wn',集采:'vi'}},
  payState: {vals:['已付清','未付清'], tone:{已付清:'ok',未付清:'wn'}, dot:1},
  astat:    {vals:['已批','未批'], tone:{已批:'ok',未批:'dg'}},
  payMethod:{vals:['现汇','承兑','供应链','其他'], tone:{现汇:'in',承兑:'wn',供应链:'pri',其他:'in'}},
  flowState:{vals:['生效','已撤销'], tone:{生效:'ok',已撤销:'dg'}},
  ivDir:    {vals:['入库','出库'], tone:{入库:'ok',出库:'wn'}},
  pjStatus: {vals:['在建','归档'], tone:{在建:'in',归档:'in'}},
  pjType:   {vals:['normal','shell','small'], text:{normal:'普通项目',shell:'小微壳',small:'具体小微'}, tone:{normal:'in',shell:'vi',small:'wn'}},
  jcTag:    {vals:['纳入台账','不纳入'], tone:{纳入台账:'ok',不纳入:'in'}},
  jcArch:   {vals:['未存档','资产处','已存档'], tone:{未存档:'wn',资产处:'pri',已存档:'ok'}},
  plRev:    {vals:['完全匹配','金额不符','单据号查不到','无单据号','重复上报','超过未付'],
             tone:{完全匹配:'ok',金额不符:'wn',单据号查不到:'dg',无单据号:'dg',重复上报:'wn',超过未付:'dg'}},
  plRevF:   {vals:['全部','完全匹配','未匹配']},            /* 筛选两档归并（判定仍 6 种，见 §4.3.4）*/
  dfState:  {vals:['待核对','已核对','差异保留'], tone:{待核对:'wn',已核对:'ok',差异保留:'dg'}}
};
const enumVals=k=>ENUMS[k].vals;
const enumText=(k,v)=>(ENUMS[k].text||{})[v]!==undefined?(ENUMS[k].text||{})[v]:v;
const enumTone=(k,v)=>(ENUMS[k].tone||{})[v]||'in';
/* 枚举 → 标签：全站**唯一渲染出口** */
const enumTag=(k,v)=>{ if(v==null||v===''||enumVals(k).indexOf(v)<0) return '<span class="mut">—</span>';
  const tone=enumTone(k,v), dot=ENUMS[k].dot?`<span class="dot d-${tone}"></span>`:'';
  return `<span class="tag t-${tone}">${dot}${esc(enumText(k,v))}</span>`; };
/* 下拉：`list` 传完整候选（可含「全部」「剔除」这类**伪值**），`cur` = 当前值 */
const optsOf=(list,cur)=>list.map(v=>`<option ${String(cur)===v?'selected':''}>${v}</option>`).join('');
const enumOpts=(k,cur,all)=>optsOf(all?['全部'].concat(enumVals(k)):enumVals(k),cur);
/* —— 既有渲染函数改为「薄封装」，旧调用点一处不改 —— */
const catTag=c=>enumTag('cat',c);
const astatTag=a=>enumTag('astat',a);
const stTag=s=>enumTag('payState',s);
const revTag=r=>({'完全匹配':'ok','无单据号':'plan-missing','单据号查不到':'plan-notfound','重复上报':'plan-duplicate','超过未付':'plan-over','金额不符':'plan-amount'}[r]||enumTone('plRev',r));

/* ===== 写路径 · 金额校验与上限（2026-09-13 阶段 3 收口）=====
   为什么要收口：**「上限 = 审批金额」与「非法即拦、保留原值」是铁律 3 的落点**，
   原先散在每个可改字段处各写一遍 —— 措辞、判据（`<0` 还是 `<=0`）、容差各有微差。
   本区块只提供**四个纯函数**（不接管控制流：拦什么、提示什么仍由调用点决定）：
     · `numOf(raw,{empty0})`       解析成数（空串按 0 还是按 NaN 由调用点定）
     · `badMoney(v,{positive})`    是否非法（`positive` = 必须 > 0；否则 ≥ 0）
     · `badMoneyMsg(标签,{unit,positive})` 统一措辞「〈标签〉不合法：请填…（…），已保留原值」
     · `overCap(v,上限)`           超上限（**容差只此一处**）
   ⚠️ 提示**后面的补充说明**（如「按发票走，只能往下调」）仍写在各调用点 —— 那是业务话术，不是通用件。
   ⚠️ `CAP_TOL` 是**浮点噪声容差**（不是业务容差；业务口径是 §9.1「判定容差 0」）。
      它只用于"是否超上限"的判断，避免 1e-13 级尾噪把等于上限的值判成超限。 */
const CAP_TOL=0.005;
const overCap=(v,cap)=>Number(v)>Number(cap)+CAP_TOL;
const numOf=(raw,o)=>{ const t=String(raw==null?'':raw).trim();
  return (t===''&&o&&o.empty0)?0:N2(parseFloat(t)); };
/* ⚠️ `signed` = **允许正负号**（差异金额专用：§5.8.3「带符号 · + 上调 / − 下调」）。
   默认仍拒负数 ⇒ 既有调用点行为一字不变。 */
const badMoney=(v,o)=>isNaN(v)||((o&&o.positive)?v<=0:((o&&o.signed)?false:v<0));
const badMoneyMsg=(label,o)=>`<b>${label}不合法</b>：请填${o&&o.positive?'正数':((o&&o.signed)?'数字（可带正负号，+ 上调 / − 下调）':'非负数')}（${(o&&o.unit)||'2 位小数'}），已保留原值`;

/* ===== 留痕的统一形状与唯一写入出口（2026-09-13 定案）=====
   《说明书》§9.3 规定留痕**范围**（只给统计结算 / 统计付款金额 · 调整单 · 项目全名与状态），
   并要求记「改前值 / 改后值 / 改动人 / 时间」。
   ⚠️ 原型原先有**三套数组排法**（付款通知书 `[字段,改前,改后,人,时间,说明]` ·
      项目档案 `[时间,名,字段,改前,改后,人]` · 调整单 `[字段,改前,改后]`）——
      读的人得先数下标，**排法记错一次就是静默错值**（本项目已把"按 id 不按名"写成铁律，同理）。
   ⇒ 统一成**对象**：`{ obj, field, before, after, by, at, note }`（`obj` / `note` 可空）。
   ⇒ **写入只走 `pushTrail`、读取只走 `hasTrail` / `trailOf`**，不再有第二套排法。 */
const mkTrail=o=>({ obj:o.obj||'', field:o.field, before:o.before, after:o.after,
  by:o.by||CUR.name, at:o.at||now(), note:o.note||'' });
const pushTrail=(list,o)=>{ const r=mkTrail(o); list.push(r); return r; };
const hasTrail=(list,field)=>(list||[]).some(t=>t&&t.field===field);
const trailOf=(list,field)=>(list||[]).filter(t=>t&&t.field===field);

/* =====================================================================
   1.5 表头点击排序（全站数据列表统一处理）
   ── 为什么做成「HTML 字符串 → HTML 字符串」的纯函数：本原型是"全量重渲染 +
      字符串模板"，在整页 HTML 生成后统一重排行，可一处覆盖所有数据表；
      且纯函数能被自检直接断言行序（若改为操作真实 DOM，现有自检桩无法验证）。
   ── 三态循环：升序 → 降序 → 原序（可反复切换；同一时刻只有一列生效）。
   ── 只处理标了 data-sort 的表。不可排的列：表头为空 / 操作 / 处理 / 含复选框 / 标 data-nosort。
   ── 排序状态的键 = 表自己声明的 **`data-sort-key`**（稳定身份）；未声明时才回退「scope + 出现次序」。
       ⇒ **加一张可排表不会串位**；新表**必须**声明 data-sort-key。
   ── 合计行（含「合计 / 总计 / 小计」）与跨列提示行钉在最后，不参与排序。
   ── 排序只重排行，不改任何单元格内容。
   ===================================================================== */
let SORT={};                                            /* { 表键: {i:列索引, d:1|-1|0} } */
const NOSORT_COL={'':1,'操作':1,'处理':1};               /* 这些列头不参与排序 */
const _plain=s=>String(s).replace(/<[^>]*>/g,'').replace(/\s+/g,' ').trim();
const _num=s=>{const t=String(s).replace(/[,¥%\s]/g,''); if(t==='')return null; const x=Number(t); return isFinite(x)?x:null;};
const _date=s=>/^\d{4}-\d{2}(-\d{2})?$/.test(String(s));
/* 单元格取值优先级：data-v 属性 → <input value>（可改金额列 / 大表手填列）→ 文本 */
function _cellRaw(td){
  if(td===undefined) return '';
  const dv=td.match(/\bdata-v="([^"]*)"/); if(dv) return dv[1];
  const iv=td.match(/<input\b[^>]*\bvalue="([^"]*)"/i); if(iv) return iv[1];
  return _plain(td.slice(td.indexOf('>')+1, td.lastIndexOf('</td>')));
}
/* 列类型自动判定：日期先判 —— 否则 2026-08-03 会被 parseFloat 吞成 2026 */
function _colType(vals){
  let n=0,d=0,t=0;
  vals.forEach(v=>{ if(v==='')return; t++; if(_date(v)) d++; else if(_num(v)!==null) n++; });
  if(!t) return 'text';
  if(d/t>=0.7) return 'date';
  if(n/t>=0.7) return 'num';
  return 'text';
}
function _cmp(a,b,t,dir){
  const ea=(a===''), eb=(b==='');
  if(ea&&eb) return 0;
  if(ea) return 1;                                      /* 空值恒排最后，不随升降序翻转 */
  if(eb) return -1;
  let r;
  if(t==='num'){const x=_num(a),y=_num(b); r=(x===null?0:x)-(y===null?0:y);}
  else if(t==='date') r=(a<b?-1:(a>b?1:0));
  else r=String(a).localeCompare(String(b),'zh-Hans-CN');
  return dir*r;
}
/* 主函数：scope 用于给表编稳定键（同一视图同一位置 = 同一张表） */
function applySorts(html,scope){
  let n=0;
  return String(html).replace(/<table\b[^>]*>[\s\S]*?<\/table>/gi,tbl=>{
    const open=tbl.match(/^<table\b[^>]*>/i); if(!open) return tbl;
    if(!/\sdata-sort[\s>]/.test(open[0])) return tbl;   /* ⚠️ 必须**精确匹配 `data-sort` 属性本身**：原来的 `\bdata-sort\b`
                                                           会把 `data-sort-key` 也算成"可排"（`-` 是词边界）⇒ 只声明 key 想表达
                                                           "可排但用稳定键"会被误判；而**刻意不可排**的表（如 `MOD-07` 焊材/气体提取的
                                                           分组表）只写 key 就会被注入排序入口、合计行还会被 pin 到表尾。 */
    const body=tbl.slice(open[0].length, tbl.lastIndexOf('</table>'));
    if(/<table\b/i.test(body)) return tbl;                        /* 嵌套表跳过，避免误伤 */
    const thead=body.match(/<thead\b[^>]*>[\s\S]*?<\/thead>/i);
    const tbody=body.match(/<tbody\b[^>]*>[\s\S]*?<\/tbody>/i);
    if(!thead||!tbody) return tbl;
    const idx=n++;
    /* 表的**身份**优先取它自己声明的 `data-sort-key`（稳定 · 与表在页面里的位置无关）；
       没声明才回退「scope + 出现次序」—— 回退键会随表的位置漂移（加一张表就把后面的键全冲掉），
       因此**新表一律声明 `data-sort-key`**，回退分支只为兼容保留。
       ⚠️ 别混用两个名字：`data-sort-key`（**表**声明 · 输入）≠ `data-tk`（th 上的运行时键 · 输出）。 */
    const decl=open[0].match(/\bdata-sort-key="([^"]*)"/i);
    const key=decl?decl[1]:(scope+'#'+idx);
    const ths=[...thead[0].matchAll(/<th\b([^>]*)>([\s\S]*?)<\/th>/gi)];
    if(ths.length<2) return tbl;
    const can=ths.map(th=>(/\bdata-nosort\b/.test(th[1])||/<input\b/i.test(th[2]))?false:!NOSORT_COL[_plain(th[2])]);
    const st=SORT[key]||(SORT[key]={i:-1,d:0});
    const tbOpen=tbody[0].match(/^<tbody\b[^>]*>/i)[0];
    const tbInner=tbody[0].slice(tbOpen.length, tbody[0].lastIndexOf('</tbody>'));
    const rows=tbInner.match(/<tr\b[^>]*>[\s\S]*?<\/tr>/gi)||[];
    const pin=[],data=[];
    rows.forEach(r=>{
      const tdc=(r.match(/<td\b/gi)||[]).length;
      /* ⭐ 2026-09-13 增行模式：草稿行（`tr.draftrow`）与「合计行 / 跨列行」走**同一条 pin 通道** ——
         钉表尾、不参与排序、不参与取值。
         ⚠️ 必须**锚在行首那个 `<tr>` 标签的 class 上**，不能靠"`<td>` 数 < 表头列数" ——
            `MOD-03` 的草稿行是**列对齐行**（`<td>` 数 = 列数），那条判据**保不住它**（实测推演）。 */
      const openTag=(r.match(/^<tr\b[^>]*>/i)||[''])[0];
      if(/\bdraftrow\b/.test(openTag)||/合计|总计|小计/.test(_plain(r))||tdc<ths.length) pin.push(r); else data.push(r);
    });
    let out=data;
    if(st.i>=0&&st.d!==0&&can[st.i]&&data.length>1){
      const vals=data.map(r=>_cellRaw((r.match(/<td\b[^>]*>[\s\S]*?<\/td>/gi)||[])[st.i]));
      const tp=_colType(vals);
      out=data.map((r,k)=>({r,v:vals[k]})).sort((a,b)=>_cmp(a.v,b.v,tp,st.d)).map(o=>o.r);
    }
    /* 表头：注入 class / 点击动作 / 排序指示器 */
    const newTh=ths.map((th,k)=>{
      if(!can[k]) return '<th'+th[1]+'>'+th[2]+'</th>';
      const on=(st.i===k&&st.d!==0);
      let a=th[1];
      a=/\bclass="/.test(a)?a.replace(/\bclass="([^"]*)"/,(m,c)=>'class="'+c+' srt'+(on?' on':'')+'"'):a+' class="srt'+(on?' on':'')+'"';
      a+=' data-act="headSort" data-tk="'+key+'" data-i="'+k+'" tabindex="0" role="button" title="点击排序：升序 → 降序 → 原序"';
      return '<th'+a+'>'+th[2]+'<span class="sind">'+(on?(st.d>0?'▲':'▼'):'↕')+'</span></th>';
    }).join('');
    const newHead=thead[0].match(/^<thead\b[^>]*>/i)[0]
      +(thead[0].match(/<tr\b[^>]*>/i)||['<tr>'])[0]+newTh+'</tr></thead>';
    return open[0]+newHead+tbOpen+out.concat(pin).join('\n')+'</tbody>'+tbl.slice(tbl.lastIndexOf('</tbody>')+8);
  });
}


