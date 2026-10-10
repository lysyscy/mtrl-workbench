/* 编号可解析性自检（"引用号在定义处是否存在"）—— 用法：node demo/_ids.js
        （本机 node 全路径示例：
          & node delivery\demo\_ids.js）

   ── 为什么需要它（第四个自检，2026-09-12 新增） ──────────────────────
     前三个自检各守一段，**都不守"编号能不能解析"**：
       _smoke.js     业务断言（原型跑起来对不对）
       _doccheck.js  表述是否过期 · 是否抄了数字 · 表格列数是否一致
       _links.js     引用**目标（文件 / 目录）**在不在
     ⇒ `_links.js` 把 `DEV-R-06` 这类 token 当"术语并列"直接跳过（见其 WORDY 分支），
        因此**任何 `XXX-nn` 引用号悬空都不会变红**。
     实证（2026-09-12 外部审计）：`DEV-R-01…08` 被 12 处引用，而 §5.10 的清单表
        只有 `#` 序号、**没有编号列** —— 号是悬空的，而三个自检全绿。

   ── 判定（信号要干净）────────────────────────────────────────────────
     定义 = 该编号出现在**某张表的首列**（`| \`DEV-R-01\` | …` 形态）—— 本项目所有清单表
            （附录 E.1 / E.2 / F、§4.9 / §5.10 / §6.9）都满足这个形态。
     引用 = 该编号在**交付面**任何位置出现。
     FAIL = 被引用但**全库都找不到定义处**（新对话 / AI 无法定位 ⇒ 只能猜）。
     info = 有定义但从未被引用（只是提示，不算问题）。

   ── 覆盖范围（刻意收窄，宁缺勿误报）──────────────────────────────────
     只查**有干净定义表**的前缀：`API-nn` · `ENT-nn` · `MOD-nn` · `DEV-P-nn` · `DEV-R-nn` · `DEV-J-nn` · `ACC-<域>-<序>`（2026-09-14 新增；**其定义处 = `PRD/验收/用例索引.md` 的首列**）
     刻意**不查**：
       `OPEN-nn`   —— 本项目允许"已定案但编号保留不用"，号可能不出现于 §三（属正常）
       `REQ-Rn`    —— 附录 C 首列写成 `R1` / `R15 · R16 …`，与 `REQ-R15` 形态不同（会误报）
       `CHG-*`     —— 只用于追溯、不进交付面
       裸 `Rn`      —— 与需求号 / 设计规则号同名不同义（规则 7 已要求带限定词）
   ⚠️ 引用侧**只扫交付面**（根目录诸份 + `demo/` + `PRD/` + `PRD素材包/`，**排除 `沿革/`**）：
      沿革层是历史留档，允许引用已退役编号；交付面必须"新对话打开就能解析"。
      **引用侧含 `.md` 与 `.html`**（2026-09-12 补）：原型 HTML 里的 `DEV-*` / `MOD-*` 等引用同样要求可解析；
      **定义侧仍只在 `.md` 里找**（HTML 不是编号的定义处）。 */

const fs = require('fs'), path = require('path');
const ROOT = path.join(__dirname, '..');
const SKIP_DIRS = new Set(['.git', 'node_modules', '.workbuddy', '__pycache__', '.venv']);
const LEGACY_DIR = '沿革';            // 引用侧排除（定义侧仍扫，允许定义落在沿革之外任意处）

const TOKEN = /\b((?:API|ENT|MOD|DEV-[PRJ])-\d{2}|ACC-[A-Z0-9]+(?:-[A-Z0-9]+)*-\d{3})\b/g;

/* ── 1. 收集 .md（定义 + 引用）与 .html（**只作引用侧**）── */
const mdFiles = [], htmlFiles = [];
(function walk(dir) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, e.name);
    if (e.isDirectory()) { if (!SKIP_DIRS.has(e.name)) walk(full); continue; }
    const ext = path.extname(e.name).toLowerCase();
    if (ext === '.md') mdFiles.push(full);
    else if (ext === '.html') htmlFiles.push(full);
  }
})(ROOT);

const rel = f => path.relative(ROOT, f).split(path.sep).join('/');
const inLegacy = r => r === LEGACY_DIR || r.indexOf(LEGACY_DIR + '/') === 0;

/* ── 2. 定义表：全库扫「首列」；引用表：只扫交付面 ── */
const defined = new Map();     // token -> [『file:line』]
const quoted = new Map();      // token -> [『file:line』]   (引用处)
const seenTokens = new Set();

for (const f of mdFiles) {
  const r = rel(f);
  const lines = fs.readFileSync(f, 'utf8').split(/\r?\n/);
  lines.forEach((ln, i) => {
    const toks = ln.match(TOKEN) || [];
    for (const t of toks) {
      seenTokens.add(t);
      /* 定义：本行以 `|` 开头，且**首个单元格**就是该编号 */
      const firstCell = /^\s*\|\s*([^|]*?)\s*\|/.exec(ln);
      if (firstCell && firstCell[1].replace(/[`*\s]/g, '') === t) {
        if (!defined.has(t)) defined.set(t, []);
        defined.get(t).push(`${r}:${i + 1}`);
      }
      if (!inLegacy(r)) {
        if (!quoted.has(t)) quoted.set(t, []);
        quoted.get(t).push(`${r}:${i + 1}`);
      }
    }
  });
}

/* ── 2b. 引用侧：原型 HTML 也要扫（**只做引用、不做定义**）──
   ⭐ 2026-09-12 外部审计补：原型是"页面与交互的现行出处"，里面引用了
      `DEV-P-*` / `DEV-J-*` / `DEV-R-*` / `MOD-*` / `API-*`。
      此前只扫 .md ⇒ **说明书删掉某个号，原型不会红** —— 这是"绿 ≠ 健康"的又一个结构性缺口。 */
for (const f of htmlFiles) {
  const r = rel(f);
  if (inLegacy(r)) continue;
  const lines = fs.readFileSync(f, 'utf8').split(/\r?\n/);
  lines.forEach((ln, i) => {
    for (const t of (ln.match(TOKEN) || [])) {
      seenTokens.add(t);
      if (!quoted.has(t)) quoted.set(t, []);
      quoted.get(t).push(`${r}:${i + 1}`);
    }
  });
}

/* ── 3. 判定 ── */
const fails = [], orphan = [];
for (const [t, where] of quoted) {
  if (!defined.has(t)) fails.push({ token: t, where });
}
for (const [t, where] of defined) {
  if (!quoted.has(t)) orphan.push({ token: t, where });
}

/* 通过数（2026-09-15 横幅统一）= 被引用的号里有定义的那些 */
const passIds = quoted.size - fails.length;

/* ── 4. 报告 ── */
if (fails.length) {
  console.log('── FAIL · 引用号悬空（交付面引用了，但全库找不到定义处）──\n');
  for (const x of fails.sort((a, b) => a.token.localeCompare(b.token))) {
    console.log(`FAIL  \`${x.token}\`  ×${x.where.length}  引用位置：${x.where.join('  ·  ')}`);
  }
  console.log('\n（修法：**定义处补出该编号**，或把引用改成可定位形态（如「§5.10 第 6 项」）—— 二者择一，勿并存）');
} else {
  console.log('（无悬空编号：交付面引用的每一个 `API-*` / `ENT-*` / `MOD-*` / `DEV-*` 都能在定义处解析）');
}
if (orphan.length) {
  console.log('\n── info · 有定义但从未被引用（仅提示，不是问题）──\n');
  for (const x of orphan.sort((a, b) => a.token.localeCompare(b.token))) {
    console.log(`info  \`${x.token}\`  定义于：${x.where[0]}`);
  }
}

console.log(`\n===== 编号可解析性自检：${passIds} 通过 / ${fails.length} 失败 · info ${orphan.length} =====`);
/* 引用侧份数单独算：引用侧**排除沿革层**，与"全库 .md"不是同一个数
   （2026-09-12 更正：原先把 `mdFiles.length` 直接当"引用侧份数"，与同句"（已排除 沿革/）"自相矛盾）。 */
const refMdCount = mdFiles.filter(f => !inLegacy(rel(f))).length;
console.log(`扫描：全库 ${mdFiles.length} 份 .md 找**定义**；引用侧 = ${refMdCount} 份 .md + ${htmlFiles.length} 份 .html（已排除 \`${LEGACY_DIR}/\` —— 该层已于 2026-09-14 移出工作区）`);
console.log(`覆盖前缀：API-nn · ENT-nn · MOD-nn · DEV-P-nn · DEV-R-nn · DEV-J-nn · ACC-<域>-<序>（OPEN-nn / REQ-Rn / CHG-* 刻意不查，见文件头）`);
process.exit(fails.length ? 1 : 0);
