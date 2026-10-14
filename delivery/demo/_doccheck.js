/* 文档一致性自检（事实登记表 + 跨文件比对）—— 用法：node demo/_doccheck.js
        （本机 node 全路径示例：
          & node delivery\demo\_doccheck.js）

   ── 与其它自检的分工 ─────────────────────────────────────────────────
     _smoke.js     业务断言（原型跑起来对不对）        —— 改原型后必跑
     _doccheck.js  **本文**：文档事实是否漂了 + 表格列数
     _links.js     引用**目标（文件 / 目录）**在不在 + 交付面是否引用沿革层
     _ids.js       引用**编号**在定义处是否存在（防"号悬空"）

   ── 为什么从"手写正则黑名单"改成"事实登记表"（2026-09-12 用户拍板 · C-甲）──
     旧写法是一串"禁止出现的字符串"正则。它的失败模式（**与谁写无关**）：
       ① **事故驱动**：规则只在踩过一次坑之后才存在 ⇒ 覆盖集合是**事故的函数**，不随文档规模收敛；
       ② **要求预先穷举反例形态**：实测旧守卫写 `/14 模块/`，文档写「14 **个**模块」⇒ 漏（措辞是开放的）；
       ③ **漏了是静默的**：不报错，只有恰好读到才发现。
     新写法把校验从"**枚举措辞**"换成"**比对取值**"：
       · 每个事实登记一行：**键 + 主人文件 + 怎么实时取值 + 文档里怎么表述它**
       · 值**永远从主人处实时算**，不写死在脚本里 ⇒ 主人改了值，这里自动跟着改，不会过期
       · 文档一旦表述该事实，就与实时值比对：**不等 → FAIL**；相等但不在主人处 → **WARN（复述=副本）**
       ⇒ **新增一个事实 = 加一行**；不需要写正则、不需要预判所有措辞变体。

   ── 判定档（信号要干净，否则没人看红灯）──────────────────────────────
     FAIL  ① 计数类事实：文档写的数字 ≠ 主人实时值
           ② 表述类事实：出现了该事实**被推翻的说法**（负向表述）
           ③ 必备要素：该存在的现行要素缺失
           ④ 表格列数：同一张表内列数不一致
           ⑤ 表格分隔行 > 1：一张表只应有一个表头 + 一个分隔行（重复表头 = 畸形表）
     WARN  计数写对了，但**不在主人处**（属"摘要式复述"，漂移后是静默的 —— 建议改指针）
     info  实时测得的事实值（只打印，不断言；新增事实不必改这里）

   ── 新增检查项：往 REG 里加一行即可。三种 kind：
       kind:'count'  计数类：owner + measure()（实时取值）+ stated（文档里怎样表述该事实）
       kind:'text'   表述类：forbid（该事实被推翻的说法）
       kind:'must'   必备要素：in（哪个文件）+ re（必须存在的形态）
   ⚠️ 每条事实**必须有一个主人**（唯一出处）；主人处允许复述，别处只应写指针。 */

const fs = require('fs'), path = require('path');
const ROOT = path.resolve(__dirname, '../../docs/requirements');

/* ── 现行文档（= 需要被校验的范围；沿革层**有意排除**，否则对旧表述必然误报）── */
const MANUAL   = '材料科业务全流程说明书.md';
const PLAN     = '全自动建档-实施计划.md';
const TECH     = '技术栈选型分析.md';
const DESIGN   = 'demo/设计规则-提炼自付款通知书页.md';
const PACK     = '../../delivery/PRD素材包-20260911';
const PACKLIST = PACK + '/清单.md';
const TMLIST    = 'demo/模板/模板清单.md';
const PRDDIR    = 'PRD';                        /* 交付面第 6 项（2026-09-14） */
const DELIVDOC  = '交付说明书.md';               /* 交付面第 7 项（2026-09-15）：交付包总说明 */
const PRDIDX    = 'PRD/01-需求索引.md';
const PRDNONG   = 'PRD/04-Non-goals.md';
const GUIDE     = 'demo/原型导读.md';   /* 2026-09-15 纳入：它的规模数字从此被实时校验 */
const FILES = [MANUAL, PLAN, TECH, DESIGN, PACKLIST, TMLIST, PRDIDX, PRDNONG, GUIDE];

/* ⚠️ 原型 HTML **不进 `FILES`** —— 它含大量 `|`（`||` 运算符、文本表格…），会被"表格列数"检查误判。
   但它必须被**读入**：导读里那几个规模数字（视图 / 代码分区 / 表头常量）**由它实时算出来**。
   ⚠️ 计数一律**先剥块注释** —— 注释里出现过 `data-act="名"` 这种**举例文字**（实测：不剥会多算 1–2 个）。 */
const PROTO = path.join(__dirname, '材料报表自动化工作台-交互原型.html');
const protoRaw = fs.existsSync(PROTO) ? fs.readFileSync(PROTO, 'utf8') : '';
const protoCode = protoRaw.replace(/\/\*[\s\S]*?\*\//g, '');
const nViews   = () => new Set([...protoCode.matchAll(/^\s*V\.([A-Za-z_]\w*)\s*=/gm)].map(m => m[1])).size;
const nTheads  = () => new Set([...protoCode.matchAll(/const\s+([A-Z][A-Z0-9_]*_THEAD)\s*=/g)].map(m => m[1])).size;
const nBanners = () => (protoRaw.match(/^\s*\/\* =+\s*$/gm) || []).length;
/* 导读里"由**表格**承载行数"的小节 → 数该节表的**数据行数**（减去表头 + 分隔行）。
   ⚠️ 为什么不直接数正文里的数字：技术计数（视图数 / 交互路径数 / 断言数）**不得写进文档**
   （《说明书》§0.7.1 规则 4）；而"这张表有几行"本身就是事实 ⇒ 与原型实算比对，
   既能对漂移报警，又不违反"不写计数"。返回 −1 表示小节标记没找到（必然不等 ⇒ FAIL）。 */
const guideRows = (from, to) => {
  const t = src[GUIDE] || '';
  const a = t.indexOf(from), b = t.indexOf(to, a + 1);
  if (a < 0 || b < 0) return -1;
  return (t.slice(a, b).match(/^\|/gm) || []).length - 2;
};

/* ── 读入 ── */
const src = {};
let pass = 0, fail = 0, warn = 0;
const F = [], W = [];
for (const f of FILES) {
  const p = path.join(ROOT, f);
  if (!fs.existsSync(p)) { F.push(`文件不存在：${f}`); fail++; continue; }
  src[f] = fs.readFileSync(p, 'utf8');
}
const lines = f => (src[f] || '').split(/\r?\n/);
const countOf = (re, f) => ((src[f] || '').match(re) || []).length;
const distinctOf = (re, f) => new Set((src[f] || '').match(re) || []).size;
const countFilesOnDisk = dir => (function walk(d) {
  let n = 0;
  for (const e of fs.readdirSync(d, { withFileTypes: true })) {
    /* ⚠️ **排除 `__pycache__`**（2026-09-18 实测踩到）：打印链路会**按路径 import 素材包里的反解件**
       ⇒ 解释器往素材包写编译缓存（`.pyc`）—— 那**不是素材**，却会把本事实位的数字顶高
       （1103 → 1104 ⇒ 报一条修不掉的 FAIL，且**只要跑一次打印测试就复发**）。
       ⇒ 计数只认"素材"：缓存目录一律不计。 */
    if (e.isDirectory() && e.name === '__pycache__') continue;
    if (e.isDirectory()) n += walk(path.join(d, e.name)); else n++;
  }
  return n;
})(path.join(ROOT, dir));

/* ══ 事实登记表 ══════════════════════════════════════════════════════════ */
/* 事实键 → 实时值：供 text.wantRef / must.re() 动态取值（避免"守卫自己的期望值过期"） */
const VAL = new Map();

const REG = [

  /* ── ① 计数类事实：值从「主人」实时算，别处一旦复述就比对 ── */
  {
    kind: 'count', key: '功能模块数', owner: MANUAL,
    measure: () => distinctOf(/^\|\s*`(MOD-\d{2})`/gm, MANUAL),
    /* ⚠️ 必须排除"章节号尾巴"：`### 8.2 模块依赖矩阵` 里的 `2 模块` 会被误当成"2 个模块"
       （负数后顾：前面是数字或 `.` 或 `§` 的，不算在说"模块数"） */
    stated: /(?<![\d.§])(\d{1,3})\s*个?\s*模块/g,
    note: '主人 = 附录 F 的首列'
  },
  {
    kind: 'count', key: '关键口径条数', owner: MANUAL,
    measure: () => countOf(/^\|\s*`DEV-[PRJ]-\d{2}`/gm, MANUAL),
    stated: /(\d+)\s*条\s*(?:关键)?口径/g,
    note: '主人 = §4.9 / §5.10 / §6.9 三张清单的行数'
  },
  {
    kind: 'count', key: '设计规则条数', owner: DESIGN,
    measure: () => countOf(/^### R\d+/gm, DESIGN),
    /* ⚠️ **两种语序都要认**：「16 条…规则」与「设计规则 16 条」。
       实证（2026-09-12 外部审计 · 反向灵敏度）：只写前一种时，文档改成
       「可复用设计规则 16 条」会**静默漏过**（守卫绿、值已错）—— 这是"措辞是开放的"的典型。 */
    stated: [/(\d+)\s*条(?:可复用)?(?:设计)?规则/g, /(?:可复用)?(?:设计)?规则\s*(\d+)\s*条/g],
    note: '主人 = 设计规则文档的 `### Rn` 小节'
  },
  {
    kind: 'count', key: '实施阶段数', owner: PLAN,
    measure: () => distinctOf(/^\|\s*\*\*阶段 (\d+)/gm, PLAN),
    stated: /(\d+)\s*阶段/g,
    note: '主人 = 实施计划 §六 的阶段表'
  },
  {
    kind: 'count', key: '素材包文件数', owner: PACKLIST,
    measure: () => countFilesOnDisk(PACK),
    /* ⚠️ 同上：既认「共 N 个文件」，也认「（N 文件）」—— 后者实测会漏（2026-09-12 外部审计） */
    stated: [/共\s*\*{0,2}(\d+)\s*个文件/g, /（\s*\*{0,2}(\d+)\s*文件\s*）/g],
    note: '主人 = 盘上实数（清单.md 在包内）'
  },

  /* ── ② 表述类事实：该事实被推翻的说法一律 FAIL ── */
  {
    kind: 'count', key: '集采合同主表字段数', owner: MANUAL,
    measure: () => {
      /* 数 §6.4.1「合同主表」字段清单表的数据行（总行数 − 表头 − 分隔行）——
         用途：给 `text.wantRef` 与附录 E 的 `must` 提供**实时**期望值（D-8④）。 */
      const t = src[MANUAL] || '';
      const a = t.indexOf('#### 6.4.1 合同主表');
      const b = t.indexOf('#### 6.4.2', a + 1);
      const seg = a < 0 ? '' : t.slice(a, b < 0 ? t.length : b);
      return (seg.match(/^\|\s*[^|\s]/gm) || []).length - 2;
    },
    /* ⚠️ 语序刻意只认「共 N 字段」一种：宽正则会把 `技术栈选型分析.md` 里
       「§6.4 **N 字段**」这类复述也卷进来，而那份文档本期「待重做」不许改
       ⇒ 会产生一条**永远修不掉的 WARN**。窄口径 + `wantRef` 更稳。 */
    stated: /共\s*\*{0,2}(\d+)\s*字段/g,
    note: '主人 = §6.4.1 的字段清单表行数'
  },

  { kind: 'text', key: '付款状态判定基准', forbid: /≥\s*统计付款金额/, want: '审批金额', ref: '§4.4.2 · `DEV-P-02`' },
  { kind: 'text', key: '集采合同主表字段数', forbid: /15\s*字段/, wantRef: '集采合同主表字段数', wantSuffix: ' 字段', ref: '§6.4.1 · 附录 E `ENT-06`' },
  { kind: 'text', key: '留痕范围', forbid: /所有旁路改动留痕/, want: '清单式（见 §9.3 的"勿扩大、勿缩小"表）', ref: '§9.3' },
  { kind: 'text', key: '过程资料材料费来源', forbid: /理论上\s*=/, want: '引用自库存单据（派生只读）', ref: '§5.2.3 / §5.2.4' },
  { kind: 'text', key: '付款金额（本次应付）持久性', forbid: /留痕\)\s*（?旁路字段/, want: '会话级覆盖 · 不留痕', ref: '§4.2.5 · §9.3' },
  { kind: 'text', key: '普通项目 ↔ 仓库', forbid: /允许 1:N|不强制 1:1/, want: '1 : 1', ref: '《实施计划》决策 2' },
  { kind: 'text', key: '《说明书》是否带版本号', forbid: /说明书》v1\.[23]|说明书-v1\.3\.md/, want: '不带版本号', ref: '§0.4（只写现行口径）' },
  { kind: 'text', key: '设计规则编号范围', forbid: /R1–R1[345]/, wantRef: '设计规则条数', wantPrefix: '`R1`–`R', wantSuffix: '`', ref: '设计规则文档（`want` 取「设计规则条数」实时值 ⇒ 加规则后不会再写死过期）' },
  {
    kind: 'text', key: '自检数字不得抄进文档',
    forbid: /\d{2,4}\s*项断言|断言共\s*\*{0,2}\d|\d{2,4}\s*通过\s*\/\s*\d+\s*失败|\d{2,4}\s*条交互路径|\d{2,4}\s*个视图/,
    want: '跑 `demo/` 的自检脚本看实时值（断言数 / 通过数 / 交互路径数 / 视图数一律不抄）', ref: '§0.7.1 规则 4'
  },

  /* ── ③ 回归守护（2026-09-13 补 · D-12）：把这轮修好的「文档与实现相反」的表述钉住 ── */
  { kind: 'text', key: '机械费结算是否可手填', forbid: /机械[^|｜\n]{0,14}行内可编辑/, want: '机械费结算 = **派生只读**（手填只在过程资料机械 6 列）', ref: '§5.6.1.1 · `MOD-05`' },
  { kind: 'text', key: '项目候选的键', forbid: /全名反查展示名/, want: '**键 = 仓库名**、显示 = 展示名（`PROJ_META_KEY`）', ref: '§2.7.4' },
  { kind: 'text', key: '统一时间选择器组件名', forbid: /\bmpBtn\b/, want: '`tmBtn`（面板由 mpToggle / mpYear / mpMode / mpWQ / mpPick 驱动）', ref: '设计规则 R6 · §六 第 30 条' },

  /* ── ③ 必备要素：现行文档里必须存在（缺失即 FAIL）── */
  { kind: 'must', key: '§4.4.4 批量付款', in: MANUAL, re: /#### 4\.4\.4 批量付款/, ref: '`CHG-2026-09-12-E`' },
  { kind: 'must', key: '§4.4.5 撤销付款流水', in: MANUAL, re: /#### 4\.4\.5 撤销付款流水/, ref: '`CHG-2026-09-12-E`' },
  { kind: 'must', key: '§9.3 留痕清单', in: MANUAL, re: /留痕范围（勿扩大、勿缩小）/, ref: '§9.3' },
  { kind: 'must', key: '附录 E 合同主表指向唯一字段清单', in: MANUAL, re: /^\|\s*`ENT-06`.*字段清单见 §6\.4\.1.*\| §6\.4\.1 \|$/m, ref: '附录E.2 ENT-06 → §6.4.1' },
  { kind: 'must', key: '§4.2.2「剔除视图不受状态筛选」', in: MANUAL, re: /切到它时\*\*不再受「审批状态 \/ 付款状态」筛选约束\*\*|不受审批状态 \/ 付款状态筛选影响/, ref: '§4.2.2' },
  { kind: 'must', key: '§6.4.2 贸易公司发票子表', in: MANUAL, re: /贸易公司发票子表/, ref: '`CHG-2026-09-12-F`' },
  { kind: 'must', key: '§4.2.5 统计字段上限口径', in: MANUAL, re: /上限 = 审批金额|≤ 审批金额/, ref: '§4.2.5' },
  { kind: 'must', key: '§6.5.2 集采定时抓取', in: MANUAL, re: /定时自动/, ref: '`OPEN-T9`' },
  { kind: 'must', key: '设计规则 §六（仅属交互层的约定 · 现行出处）', in: DESIGN, re: /## 六、仅属交互层的约定/, ref: 'demo/设计规则 §六（原 PRD输入信息汇总 §3.4 已并入，2026-09-12）' },
  { kind: 'must', key: '§0.7.3 自查表含 _ids.js', in: MANUAL, re: /node delivery\/demo\/_ids\.js/, ref: '§0.7.3' },

  /* ── ④ 字段级事实的「必备要素」（2026-09-13 补 · D-9）：附录 E 与正文成对存在的事实，至少钉住"必须存在"的形态 ── */
  { kind: 'must', key: '附录 E `ENT-02` 付款状态两态', in: MANUAL, re: /已付清 \/ 未付清/, ref: '§4.4.2 · 附录 E `ENT-02`' },
  { kind: 'must', key: '附录 E `ENT-02` 归属按 id 存取', in: MANUAL, re: /禁止按全名反查/, ref: '§2.5.1 · §9.8-5/6' },

  /* ── ⑤ `demo/原型导读.md`（2026-09-15 纳入）：骨架 ＋ **规模数字 = 原型实时算** ──
     ⚠️ 为什么用 `must` ＋ **函数式 `re`** 而不是 `count`：`count` 的机制是"owner 处算 ＋ 别处复述即比对"，
     会把**本来就该写规模数字的导读**判成 WARN（复述）；而这里要的是**两个来源必须相等**，不等即 **FAIL**。
     ⇒ 这样"导读随原型漂移"就有了机器报警（此前只能靠 §七 的复核命令人工跑）。 */
  { kind: 'must', key: '导读 · 骨架 §三 逐页索引', in: GUIDE, re: /^## 三、逐页索引/m, ref: '导读 §三' },
  { kind: 'must', key: '导读 · 骨架 §四 动作总表', in: GUIDE, re: /^## 四、动作总表/m, ref: '导读 §四' },
  { kind: 'must', key: '导读 · 骨架 §五 表头常量', in: GUIDE, re: /^## 五、表头常量/m, ref: '导读 §五' },
  { kind: 'must', key: '导读 · 骨架 §七 可执行复核命令', in: GUIDE, re: /^## 七、/m, ref: '导读 §七' },
  { kind: 'must', key: '导读 · 历史用途与当前权威边界', in: GUIDE, re: () => { const t = src[GUIDE] || ''; return /不是规格本身/.test(t) && /历史交互规格的权威是该时期原型本身/.test(t) && /已不决定当前运行界面/.test(t) && /当前业务目标回说明书与PRD/.test(t) && !/现行交互基准/.test(t); }, ref: '导读 §〇（历史三层权威位）' },
  { kind: 'must', key: '导读「视图数」= 原型实时算', in: GUIDE, re: () => guideRows('### 2.1', '### 2.2') === nViews(), ref: '§2.1 视图表行数 vs 原型 `V.*` 定义数' },
  { kind: 'must', key: '导读「代码分区数」= 原型实时算', in: GUIDE, re: () => guideRows('### 2.2', '## 三、') === nBanners(), ref: '§2.2 分区表行数 vs 原型 `/* ====` 横幅数' },
  { kind: 'must', key: '导读「表头常量数」= 原型实时算', in: GUIDE, re: () => guideRows('## 五、', '## 六、') === nTheads(), ref: '§五 常量表行数 vs 原型 `const *_THEAD` 去重数' }
];
/* ═══════════════════════════════════════════════════════════════════════ */

/* ── 1. 计数类：实时取值 + 逐文档比对 ── */
const measured = [];
for (const r of REG) {
  if (r.kind !== 'count') continue;
  let v;
  try { v = r.measure(); } catch (e) { F.push(`【${r.key}】实时取值失败：${e.message}`); fail++; continue; }
  measured.push({ key: r.key, value: v, owner: r.owner, note: r.note });
  VAL.set(r.key, v);
  /* ⚠️ `stated` 允许是**一个正则或一组正则**（多语序）——
     只写一种语序 = 守卫只覆盖一种措辞，换个语序就静默漏过。 */
  const STATES = Array.isArray(r.stated) ? r.stated : [r.stated];
  for (const f of FILES) {
    if (!src[f]) continue;
    lines(f).forEach((ln, i) => {
      for (const st of STATES) {
        const re = new RegExp(st.source, 'g');
        let m;
        while ((m = re.exec(ln))) {
          const n = Number(m[1]);
          if (n !== v) {
            F.push(`${f}:${i + 1}  【${r.key}】文档写 **${n}**，主人（${r.owner}）实时值 = **${v}**`
              + `\n        > ${ln.trim().slice(0, 96)}`);
            fail++;
          } else if (f !== r.owner) {
            W.push(`${f}:${i + 1}  【${r.key}】复述了主人处的值（${v}）—— 属"摘要式复述"，主人改了它不会跟着改，建议改指针`);
            warn++;
          }
        }
      }
    });
  }
}

/* ── 2. 表述类：该事实被推翻的说法 ── */
/* text.want 允许写成"引用某条 count 的实时值"（wantRef）—— 守卫自己的期望值也会静默过期。
   ⚠️ `wantPrefix` 与 `wantSuffix` 都可省略（拼在实时值两侧，用于 `R1`–`R19` 这类"带壳的值"）。 */
const wantOf = r => r.wantRef ? ((r.wantPrefix || '') + VAL.get(r.wantRef) + (r.wantSuffix || '')) : r.want;
for (const r of REG) {
  if (r.kind !== 'text') continue;
  for (const f of FILES) {
    if (!src[f]) continue;
    lines(f).forEach((ln, i) => {
      if (r.forbid.test(ln)) {
        F.push(`${f}:${i + 1}  【${r.key}】出现被推翻的说法 → 应为「${wantOf(r)}」${r.ref ? `（${r.ref}）` : ''}`
          + `\n        > ${ln.trim().slice(0, 96)}`);
        fail++;
      }
    });
  }
}

/* ── 3. 必备要素 ── */
for (const r of REG) {
  if (r.kind !== 'must') continue;
  if (!src[r.in]) { F.push(`【${r.key}】无法校验：文件未读入（${r.in}）`); fail++; continue; }
  /* ⚠️ `re` 是函数时，返回值**可以是 boolean** —— 用于"跨行 / 跨节的数量比对"（正则表达不了）：
     例如「导读 §2.1 表行数 = 原型视图数」，**两个来源相等才通过**。 */
  const re2 = typeof r.re === 'function' ? r.re() : r.re;
  const ok = typeof re2 === 'boolean' ? re2 : re2.test(src[r.in]);
  if (ok) pass++;
  else { F.push(`${r.in}  缺失必备要素【${r.key}】${r.ref ? ` → ${r.ref}` : ''}`); fail++; }
}

/* ── 4b. `delivery/` 目录只应有产品资料 7 项（2026-09-13 补 · D-8①；2026-09-14 交付面 5 → 6，加 PRD/；
       2026-09-15 交付面 6 → 7，加《交付说明书》）──
   由来：技能里写着"根目录只应该是交付面 N 项"，但此前四个检查器**都没有执行它** ——
   临时件 / 新目录落进根目录不会被发现，而"交付面法则"是本项目最高纪律。
   白名单 = 产品资料 7 项（含 PRD/ 与《交付说明书》）。
   ⚠️ `沿革` 已于 2026-09-14 **从白名单移除**（该层已永久移出工作区，见技能）⇒ 它若回归根目录，
   本检查会**报 FAIL** —— 这才是"交付面法则"的本意（原条目是"尚未移出"的过渡许可）。
   ⚠️ 纯目录列举、零措辞依赖 ⇒ 不会误报。
   ⚠️ **放宽白名单必须配反向灵敏度**（本文件只放行"交付面"本身，不放行任何临时件：
   加一个白名单外的临时文件应**立刻 FAIL 并点名**）。 */
const ROOT_ALLOW = new Set([MANUAL, DELIVDOC, PLAN, TECH, PRDDIR, 'demo']);
{
  const unexpected = fs.readdirSync(ROOT).filter(n => !ROOT_ALLOW.has(n));
  if (unexpected.length) {
    F.push(`根目录出现「交付面之外」的条目：${unexpected.join(' · ')}`
      + `\n        > docs/requirements/ 只放现行产品正文及分册——临时件请落 .scratch/<effort>/`);
    fail++;
  } else pass++;
}

/* ── 4c. 导读 §四（动作总表）的名称必须都能在原型里找到 —— 2026-09-15 补（审计 S2）──
   由来：导读 §四 曾长期列着一个**原型里并不存在**的动作名（`silent`；活的只有 `silent2`），
   而那时**没有任何检查器覆盖 §四** ⇒ 幽灵条目**静默存活**至今。
   ⚠️ 只做**单向**检查（导读 ⊆ 原型）：反方向必然含噪声 —— 实测"原型有、导读无"里混着
   `if` / `for` / `toast` 这类**非动作名**（模板插值 / 局部变量）⇒ **不硬套**。
   ⚠️ 取原型动作全集时**先剥块注释**（注释里的 `data-act="名"` 是举例文字）。 */
const protoActs = (() => {
  const u = new Set();
  for (const m of protoCode.matchAll(/data-act="([A-Za-z0-9_]+)"/g)) u.add(m[1]);
  for (const m of protoCode.matchAll(/ACT\.([A-Za-z0-9_]+)\s*=/g)) u.add(m[1]);
  const blk = protoCode.match(/const\s+ACT\s*=\s*\{([\s\S]*?)\n\s*\};/);
  if (blk) for (const m of blk[1].matchAll(/(?:^|\n)\s*([A-Za-z0-9_]+)\s*[:(]/g)) u.add(m[1]);
  return u;
})();
{
  const t = src[GUIDE] || '';
  const a4 = t.indexOf('## 四、动作总表');
  const b4 = t.indexOf('## 五、表头常量', a4 + 1);
  const names = a4 < 0 ? [] : [...t.slice(a4, b4 < 0 ? t.length : b4).matchAll(/^\|\s*`([A-Za-z0-9_]+)`\s*\|/gm)].map(m => m[1]);
  const ghost = names.filter(n => !protoActs.has(n));
  if (a4 < 0 || !names.length) {
    F.push(`${GUIDE}  找不到「§四 动作总表」，或表里没有动作名（导读被改动过？）`);
    fail++;
  } else if (ghost.length) {
    F.push(`${GUIDE}  §四 动作总表列了**原型里不存在**的动作名：${ghost.join(' · ')}`
      + `\n        > 幽灵条目会让人以为界面上有这个入口 —— 请从 §四 删掉，或核对原型是否真的少了它`);
    fail++;
  } else pass++;
}

/* ── 4. 表格结构：同一张表内列数必须一致 ──────────────────────────────
   由来：曾替换 §四 目录表时漏删旧表最后一行（4 列 vs 新表 2 列）→ 把表切成两半，
   而当时三个自检**全绿、无人发现**。计数时跳过反引号内的管道与 `\|` 转义
   （附录 E 的 `\|词1\|词2\|` 会干扰）。 */
const countCols = s => {
  let n = 0, inTick = false;
  for (let i = 0; i < s.length; i++) {
    const ch = s[i];
    if (ch === '`') { inTick = !inTick; continue; }
    if (inTick) continue;
    if (ch === '\\') { i++; continue; }
    if (ch === '|') n++;
  }
  return n;
};
for (const f of FILES) {
  if (!src[f]) continue;
  let tbl = null;
  /* ⭐ 新增（2026-09-12 外部审计）：**一张表只应有一个分隔行**（`|---|` 紧跟表头）。
     实证：《说明书》§6.5.2 曾把「表头 + 分隔行」重复成两遍 → 渲染成畸形表，
     而"列数一致"查不出（两遍列数相同）。 */
  const flush = () => {
    if (tbl && tbl.seps > 1) {
      F.push(`${f}  表格有 **${tbl.seps} 个分隔行**（表始于第 ${tbl.start} 行）—— 多半是**重复了表头 + 分隔行**`);
      fail++;
    }
    tbl = null;
  };
  lines(f).forEach((ln, i) => {
    if (!/^\s*\|/.test(ln)) { flush(); return; }
    const isSep = /^\s*\|[\s:|-]+\|\s*$/.test(ln);
    const n = countCols(ln);
    if (!tbl) { tbl = { start: i + 1, n, seps: isSep ? 1 : 0 }; return; }
    if (isSep) { tbl.seps++; return; }
    if (n === tbl.n) return;
    F.push(`${f}:${i + 1}  表格列数不一致（本行 ${n} 个 | · 表头 ${tbl.n} 个 · 表始于第 ${tbl.start} 行）`
      + `\n        > ${ln.trim().slice(0, 96)}`);
    fail++;
  });
  flush();
  pass++;
}

/* ── 报告 ── */
if (F.length) {
  console.log('── FAIL（需要处理）──\n');
  F.forEach(x => console.log('FAIL  ' + x));
} else {
  console.log('（现行文档与"事实主人"实时值一致；表格列数无异常）');
}
if (W.length) {
  console.log('\n── WARN（已写对，但属"复述"—— 建议改指针）──\n');
  W.forEach(x => console.log('WARN  ' + x));
}
console.log('\n── info · 本次实时测得的事实值（不断言，供人核对）──\n');
measured.forEach(x => console.log(`info  ${x.key} = ${x.value}   ← 主人：${x.owner}${x.note ? `（${x.note}）` : ''}`));

console.log(`\n===== 文档一致性自检：${pass} 通过 / ${fail} 失败 · WARN ${warn} =====`);
console.log(`事实登记表：${REG.length} 条（count ${REG.filter(r => r.kind === 'count').length} · `
  + `text ${REG.filter(r => r.kind === 'text').length} · must ${REG.filter(r => r.kind === 'must').length}）`
  + `｜ 校验范围：现行文档 ${FILES.length} 份（沿革层已于 2026-09-14 移出工作区）`);
console.log(fail ? '（以上为"文档漏改 / 事实漂移"提示，非代码缺陷；修完再跑一次）'
  : '（现行文档无事实漂移）');
process.exit(fail ? 1 : 0);
