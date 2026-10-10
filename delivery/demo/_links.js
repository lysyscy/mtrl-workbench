/* 引用健康自检（断链扫描）—— 只查"引用目标在不在"，不评判引用对不对
   用法：node demo/_links.js
        （本机 node 全路径示例：
          & node delivery\demo\_links.js）

   ── 与 demo/_doccheck.js 的分工（不要合并成一个） ──────────────────────
     _doccheck.js  查「**表述**」是否过期 —— 只扫"现行文档"；沿革层**有意排除**（否则对旧表述必然误报）
     _links.js     查「**引用目标**」是否存在 —— **全库都扫（含沿革层）**；它不查表述，故不会误报
                    ⭐ 扫描范围含 **`.md` 与 `.html`**（2026-09-13 起：原型里的文件路径引用此前无人查）

   为什么需要它：2026-09-12 删掉 5 份沿革文件 → **25 处引用当场失效**，而 _doccheck.js 仍报「14 通过 / 0 失败」。
   ⇒ **自检绿 ≠ 引用健康**。本脚本补这个盲区（沿革层是此前的"无人看管区"）。

   ── 三档判定（信号要干净，否则没人看红灯） ──────────────────────────
     OK     目标可达（不输出）
     FAIL   判定为"文件 / 目录引用"，但**目标不存在**，且**未登记** → 需要处理
     FAIL   **交付断点**：**交付面**文件引用**交付面之外**的目标 ——
            ① `沿革/`（或改名前的旧前缀 `过程资料/`）；② **只存在于沿革层 / 属"已裁剪未收录"的目标**
            （2026-09-12 升格：原先 ② 只报 WARN，与 ① 双标）。沿革层内部引用照旧放行。
     WARN   目标不存在，但**同一句已作声明**（「未收录 / 不在本次交付 / 裁剪」）→ 只需知悉
     非引用 不是路径（编号并列 `MOD-01/03`、函数 `N2()`、术语 `SNAP/rollback`）→ **静默跳过**
   ⚠️ 本脚本**只查"目标在不在"**，因此**查不出**：编号悬空（`DEV-R-06` 之类引用号在定义处不存在，
      被 `WORDY` 当"术语并列"跳过）→ 那一类由 `demo/_ids.js` 覆盖。

   ── 判"像不像引用"的规则（宁可漏，不可误报） ────────────────────────
     · 带扩展名的裸文件名（`原型档案.md`）→ 全库按 basename 认
     · 带斜杠的路径 → **首个片段必须是真实存在的目录名**，否则判为"术语并列"跳过
     · 目录简写（`tests/`）→ 目录名存在即通过
     · 前缀简写（`demo/设计规则` → 指向 `设计规则-提炼自付款通知书页.md`）→ basename 前缀匹配即通过
     · 文件相对 + 工作区根，两种基准都试（素材包内文档用的是**包内相对路径**）

   已知刻意不覆盖：带空格的 token、无扩展名的书名号简称（《变更与评审台账》）。
   新增豁免：往 IGNORE（彻底忽略）/ KNOWN（报为 WARN）里加一条，**并写明依据**。 */

const fs = require('fs'), path = require('path');
const ROOT = path.join(__dirname, '..');
const SKIP_DIRS = new Set(['.git', 'node_modules', '.workbuddy', '__pycache__', '.venv']);
const EXTS = ['.md', '.js', '.py', '.json', '.html', '.xlsx', '.txt', '.csv', '.yml', '.yaml', '.ps1', '.bat'];

/* ── 彻底忽略（连 WARN 都不报）──
   ⚠️ 旧前缀 `过程资料/` 的忽略项已移除（2026-09-12）—— 它改由下面的「交付断点」处理：
      沿革层内部保留原文（不算问题），**交付面出现它 = 交付断点（FAIL）**。 */
const IGNORE = [
  {
    test: (t, ctx) => t === '沿革/' && ctx.file === '材料科业务全流程说明书.md'
      && /不得出现指向它的引用|交付断点/.test(ctx.text),
    why: '**规则本身必须能点名该目录**：《说明书》§0.2 的唯一职责就是"禁止根目录引用沿革层"，'
      + '这句话无法在不写目录名的情况下表达。豁免范围**刻意最窄** —— '
      + '仅「**裸目录名 `沿革/`** + 同句含禁令措辞」，且仅在《说明书》内；'
      + '**任何 `沿革/xxx.md` 具体路径一律仍判交付断点**。'
  },
  {
    test: t => /(^|\/)_tmp_[^/]*$/.test(t),
    why: '`_tmp_*` 是**自检的临时中转文件**（落盘回显 / 基线引导用，跑完即删）。文档里提到它们是在说明"机制"，'
      + '不构成"应该存在的文件" ⇒ 不作断链处理。（2026-09-12 引入基线引导机制时新增）'
  }
];

/* ── 报为 WARN：目标确实不在，但**同句已作声明** ──
   ⭐ `legacyOnly`（2026-09-12 更名 —— 原字段名 `fromDeliverable` **与注释语义相反**，
      实测 `true` 反而把"交付面断链"降级成 WARN ⇒ 这是"名字与行为相反"的坑，已纠正）：
      `true` = 该目标**只存在于沿革层 / 或属"已裁剪未收录"** ⇒ **交付面引用它 = 交付断点（FAIL）**。
      交付面要放行，**必须同句有声明措辞**（「未收录 / 不在本次交付 / 裁剪」）——
      即"我在声明它不在包内"，而不是"我随手引用一个交付外的东西"。沿革层内部一律 WARN（历史引用，放行）。 */
const KNOWN = [
  {
    test: t => /^tests\//.test(t),
    why: '指向工程仓 backend/tests 的判据文件 —— 交付面扫描范围外，仓库侧由 doc_audit（T1-T4）看管（2026-09-21 TAIL-58 分目录时登记）',
    legacyOnly: true
  },
  {
    test: t => /(口径与实现差异清单-20260912|文档整合分析与方案-20260912|PRD素材完备性评估|文档评审-素材完备性评估与合并研判|材料科业务全流程说明书-v1\.2|原型开发日志-README|DEMO交接文档|口径变更说明-20260912|设计规则-更正记录|改动方案-20260912-待确认|PRD输入信息记录-20260912)/.test(t),
    why: '勘误附录 §一 / §三 已登记为「已移出 或 已合并」的沿革文件',
    legacyOnly: true
  },
  {
    test: t => /^(材料报表自动化\/|运维手册\.md|系统设计总纲\.md|架构说明\.md|全自动建档-实施计划-v1\.0\.md|技术栈选型分析-v1\.0\.md)/.test(t),
    why: '《PRD素材包 清单.md》已声明：原始素材目录 / 已裁剪未收录 / 封装时的版本钉死文件名',
    legacyOnly: true
  },
  {
    /* ⭐ 2026-09-26 登记：原型里那句「原先 64 个名字的名单 ＋ `legacy.js` 追加 3 个」是**壳侧留痕**
       （`#2` 拆「变更事件白名单」时写的），指的是**工程仓**的壳件 `backend/app/web/shell/legacy.js` ——
       交付面里没有这个文件（交付面 = 根目录诸份 + demo/ + PRD/ + PRD素材包/）。
       ⚠️ 与 `tests/` 那条同款：**它是"我在点名一个交付面之外的东西"** ⇒ 同句必须写明「不在本次交付」
       （原型那行已写）⇒ 报 WARN 而不是 FAIL。⛔ 别为了灭这条红去改那句留痕（它说的是实话）。 */
    test: t => t === 'legacy.js',
    why: '指向**工程仓**的壳实现件 `backend/app/web/shell/legacy.js` —— 交付面扫描范围外、**不在本次交付**；壳侧由仓库的判据与真机探针看管',
    legacyOnly: true
  }
];
/* 交付面放行的唯一条件：**同句**含"声明它不在交付内"的措辞 */
const DECLARED = /未收录|不在本次交付|不收录|裁剪/;

/* ── 1. 单次遍历建索引 ── */
/* ⭐ 沿革层前缀判定（含 2026-09-12 改名前的旧前缀 `过程资料/`）：
     - 沿革层内部：历史段落保留原文，不作处理
     - **交付面**：出现即为**交付断点**（该目录不在交付内、会被整体移除 → 新对话撞空） */
const LEGACY_LAYER = t =>
  t === '沿革' || t.indexOf('沿革/') === 0 || t === '过程资料' || t.indexOf('过程资料/') === 0;

const relSet = new Set(), relDirs = new Set(), fileBases = new Set(), dirBases = new Set(), mdFiles = [];
(function walk(dir) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, e.name);
    if (e.isDirectory()) {
      if (SKIP_DIRS.has(e.name)) continue;
      dirBases.add(e.name);
      const rd = path.relative(ROOT, full).split(path.sep).join('/');
      relDirs.add(rd + '/');
      let p = rd; while (p && p !== '.') { relDirs.add(p + '/'); p = path.posix.dirname(p); }
      walk(full);
    } else {
      const r = path.relative(ROOT, full).split(path.sep).join('/');
      relSet.add(r); fileBases.add(e.name);
      { const __ext = path.extname(e.name).toLowerCase(); if (__ext === '.md' || __ext === '.html') mdFiles.push(full); }
    }
  }
})(ROOT);

/* ── 2. 判定 ── */
const WORDY = /^[A-Za-z][A-Za-z0-9-]{0,15}$/;   // 编号 / 术语（MOD-01、SNAP、i8、CHG-E）
const norm = t => t.trim().replace(/\\/g, '/').replace(/^\.\//, '');

function check(t, fileDirRel) {
  if (!t || t.length > 180) return 'notref';
  if (/[*…{}<>|"',=\s]/.test(t)) return 'notref';
  if (t.includes('§')) return 'notref';
  const raw = t.replace(/\/+$/, '');
  const hasExt = EXTS.includes(path.extname(raw).toLowerCase());
  const isDirLike = t.endsWith('/');
  if (!hasExt && !t.includes('/')) return 'notref';
  if (!hasExt && /[()（）]/.test(t)) return 'notref';          // 函数调用
  const segs = raw.split('/');
  if (segs.length >= 3 && !hasExt) return 'notref';            // 术语并列（MOD-01/03/06/08/11）

  const last = segs[segs.length - 1];
  for (const base of [fileDirRel, '']) {                       // 文件相对 → 工作区根
    const c = base ? `${base}/${raw}` : raw;
    if (relSet.has(c) || relDirs.has(c + '/')) return 'ok';
  }
  if (segs.length === 1) return fileBases.has(raw) || dirBases.has(raw) ? 'ok' : 'miss';
  if (!dirBases.has(segs[0]) && !relDirs.has(segs[0] + '/')) {  // 首片段不是真目录
    return WORDY.test(segs[0]) ? 'notref' : 'miss';
  }
  if (isDirLike) return dirBases.has(last) || relDirs.has(last + '/') ? 'ok' : 'miss';
  if (dirBases.has(last) || relDirs.has(last + '/')) return 'ok';
  for (const b of fileBases) if (b.startsWith(last)) return 'ok';  // 前缀简写
  return 'miss';
}

/* ── 3. 扫描 ── */
const fails = [], warns = [];
let okRefs = 0;   /* 通过计数（2026-09-15 横幅统一）：目标存在的引用数 */
const TREE = /^[\s│├└─|+]*([^\s←→]+?\.(?:md|js|py|json|html|xlsx))\s*(?:←|→|$)/;

for (const f of mdFiles) {
  const rel = path.relative(ROOT, f).split(path.sep).join('/');
  const dr = path.posix.dirname(rel);
  const dirRel = dr === '.' ? '' : dr;
  const lines = fs.readFileSync(f, 'utf8').split(/\r?\n/);
  const legacyFile = rel.indexOf('沿革/') === 0;
  let inFence = false;
  lines.forEach((ln, i) => {
    if (/^\s*```/.test(ln)) { inFence = !inFence; return; }
    const cands = [];
    if (inFence) { const m = TREE.exec(ln); if (m) cands.push(m[1]); }
    else {
      let m; const bt = /`([^`]+)`/g; while ((m = bt.exec(ln))) cands.push(m[1]);
      const bk = /《([^》]+)》/g; while ((m = bk.exec(ln))) cands.push(m[1]);
    }
    for (const raw of cands) {
      const t = norm(raw);
      if (IGNORE.some(r => r.test(t, { file: rel, text: ln }))) continue;
      /* ⭐ 交付断点（2026-09-12 新增）：交付面**不得**出现 `沿革/`（或旧前缀 `过程资料/`）——
         沿革层内部引用照旧放行（历史段落保留原文）；《说明书》§0.2 已明令。 */
      if (LEGACY_LAYER(t)) {
        if (!legacyFile) fails.push({
          file: rel, line: i + 1, token: t, text: ln.trim().slice(0, 88),
          why: '交付面引用 `沿革/`（或旧前缀 `过程资料/`）= **交付断点**：该目录不在交付内、会被整体移除（《说明书》§0.2）'
        });
        continue;
      }
      const v = check(t, dirRel);
      if (v === 'notref') continue;
      if (v === 'ok') { okRefs++; continue; }
      const hit = KNOWN.find(r => r.test(t));
      /* ⭐ 交付面**不得**引用"只存在于沿革层 / 已裁剪未收录"的目标 —— 那是**交付断点**（新对话撞空）。
         唯一的放行方式 = **同一句作出声明**（"已裁剪未收录 / 不在本次交付内"）；
         不做声明就引用 ⇒ FAIL（2026-09-12 从 WARN 升格 —— 原先它与 `沿革/` 双标）。 */
      const declared = DECLARED.test(ln);
      const asWarn = !!hit && (legacyFile || (declared && hit.legacyOnly));
      const rec = {
        file: rel, line: i + 1, token: t, text: ln.trim().slice(0, 88),
        why: asWarn ? hit.why
          : (hit ? '⚠️ 该目标**只存在于交付面之外**（沿革层 / 原始素材目录 / 已裁剪未收录）—— 交付面引用它 = **交付断点**（新对话撞空）。'
                 + '若确属"声明其不在交付内"，请**在同一句**写明「未收录 / 不在本次交付」等措辞。'
                 : undefined)
      };
      (asWarn ? warns : fails).push(rec);
    }
  });
}

/* ── 4. 报告 ── */
const brief = (arr, tag) => {
  const byToken = new Map();
  for (const x of arr) {
    const k = x.token + '||' + (x.why || '');
    if (!byToken.has(k)) byToken.set(k, { token: x.token, why: x.why, hits: [] });
    byToken.get(k).hits.push(`${x.file}:${x.line}`);
  }
  for (const g of byToken.values()) {
    console.log(`${tag}  \`${g.token}\`  ×${g.hits.length}`);
    if (g.why) console.log(`       依据：${g.why}`);
    console.log(`       位置：${g.hits.join('  ·  ')}`);
  }
};
if (fails.length) { console.log('── FAIL · 未登记的断链（建议处理）──\n'); brief(fails, 'FAIL'); }
if (warns.length) { console.log('\n── WARN · 已知悬空（有登记依据，知悉即可）──\n'); brief(warns, 'WARN'); }
console.log(`\n===== 引用健康自检：${okRefs} 通过 / ${fails.length} 失败 · WARN ${warns.length} =====`);
console.log(`扫描范围：全库 ${relSet.size} 文件 / ${relDirs.size} 目录，逐字扫了 ${mdFiles.length} 份 .md / .html（沿革层已于 2026-09-14 移出工作区；已排除 .workbuddy / node_modules 等）`);
console.log(fails.length
  ? '（FAIL = 需要处理的断链；若属有意保留，请往 KNOWN 里加一条并写明依据）'
  : '（无未登记断链；WARN 均为勘误附录已登记的历史引用）');
process.exit(fails.length ? 1 : 0);
