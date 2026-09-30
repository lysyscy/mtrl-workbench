"""`TAIL-40` 壳侧接线：`m14` 规则配置（剔除规则换后端来源）。

改动 8 处（每处断言**起点唯一**）：
 ① 常量块：删演示常量 `RULE_EX` 的 4 条演示值 ⇒ 空容器 ＋ `RULE_RAW`（写动作用的 id）＋ `RULE_KINDS`
 ② API 客户端：4 个端点（读 / 增 / 改 / 删）
 ③ `reloadM14()`：后端 → `RULE_RAW` / `RULE_KINDS` / `RULE_SRC` / `RULE_EX`
 ④ 三个写动作（`ruleForm` / `ruleSave` / `ruleDel`）改走后端；**规则类别改下拉**（与后端 `kinds` 同源）
 ⑤ `V.m14` 切片里那句「本页各条命中值为演示值」⇒ 改成**以系统配置为准 + 来源**（唯一必要改动，需登记漂移）
 ⑥ `WIRED` ＋ `boot()`
 ⑦ 头部注释里「已接线」清单补 `m14`

⛔ 判定与落库**一律后端**；页面上不做任何本地改数据冒充落库。
"""

from __future__ import annotations

import pathlib

ROOT = pathlib.Path(r"D:\dev\mtrl-workbench")
SHELL = ROOT / "backend" / "app" / "web" / "index.html"

src = SHELL.read_text(encoding="utf-8")
if "let RULE_RAW" in src:
    print("已接线过（幂等跳过）")
    raise SystemExit(0)

steps: list[str] = []


def sub1(old: str, new: str, what: str) -> None:
    global src
    n = src.count(old)
    if n != 1:
        raise SystemExit(f"⛔ [{what}] 锚命中 {n} 次（要求恰好 1 次）")
    src = src.replace(old, new, 1)
    steps.append(what)


def sub_span(start: str, end: str, new: str, what: str) -> None:
    """把 `start`（含）到 `end`（不含）之间整段换掉；两锚各须唯一。"""
    global src
    if src.count(start) != 1:
        raise SystemExit(f"⛔ [{what}] 起点锚命中 {src.count(start)} 次")
    if src.count(end) != 1:
        raise SystemExit(f"⛔ [{what}] 终点锚命中 {src.count(end)} 次")
    s = src.index(start)
    e = src.index(end, s)
    assert e > s
    src = src[:s] + new + src[e:]
    steps.append(what)


# ============================================================== ① 常量块
sub_span(
    "/* ---------- 规则配置 MOD-14 ----------",
    "const RULE_CA = ",
    """/* ---------- 规则配置 MOD-14 ----------
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
""",
    "① 常量块：演示值 ⇒ 空容器 + RULE_RAW/RULE_KINDS/RULE_SRC",
)

# ============================================================== ② API 客户端
sub1(
    "  /* ---- MOD-09 特殊费用月报表（`TAIL-27`）",
    """  /* ---- MOD-14 剔除规则（`TAIL-40`）⚠️ 唯一主人在库；⛔ 前端不做任何本地改数据冒充落库 ---- */
  m14Rules: () => API.get('/api/m14/rules'),
  m14RuleAdd: body => API.post('/api/m14/rules', body),
  m14RuleSet: (id, body) => API.send('PUT', `/api/m14/rules/${id}`, body),
  /* ⚠️ 写动作**恒 HTTP 200**，成败看回包的 `ok` —— 规则不合法是 §4.2.2 的可预期拒绝，
     后端那句中文必须原样给用户看。 */
  m14RuleDel: id => API.send('DELETE', `/api/m14/rules/${id}`, null),

  /* ---- MOD-09 特殊费用月报表（`TAIL-27`）""",
    "② API 客户端：4 个 m14 端点",
)

# ============================================================== ③ reloadM14
sub1(
    "async function reloadMech() {",
    """/* 规则配置（`MOD-14`）—— 剔除规则读后端（**唯一主人在库**）。
   ⚠️ 「加载时算出来的派生量」一律在**本函数里重算**（本项目反复踩的坑：写在数据层 ⇒ 静默空）。 */
async function reloadM14() {
  const d = await API.m14Rules();
  RULE_RAW = d.rules || [];
  RULE_KINDS = d.kinds || [];
  RULE_SRC = d.source_label || '';
  /* ⚠️ 后端给 `kind_label`（**展示名**）—— 本页只展示，故用展示名；
     写动作要的是 `kind`（内部值）⇒ 从 `RULE_RAW[i]` 取，别从展示三元组反推。 */
  RULE_EX = RULE_RAW.map(r => [r.kind_label, r.values, r.meaning]);
}

async function reloadMech() {""",
    "③ reloadM14()",
)

# ============================================================== ④ 三个写动作
sub_span(
    " ruleAdd:()=>ACT.ruleForm(-1),",
    "\n /* —— MOD-03 付款通知书 —— */",
    """ ruleAdd:()=>ACT.ruleForm(-1),
 ruleEdit:t=>ACT.ruleForm(+t.dataset.i),
 ruleForm:i=>{ const r=i>=0?RULE_EX[i]:null; if(i>=0&&!r) return;
   /* ⚠️ 规则类别必须是**后端认的四个 key 之一** ⇒ 用后端给的 `kinds` 做下拉。
      ⛔ 不用自由文本：填个「收款单位」后端会拒（§4.2.2 硬约束），填个错别字就更看不出问题。 */
   if(!RULE_KINDS.length) return toast('<b>规则类别还没取到</b> —— 页面顶部有取数失败的提示；请刷新后重试');
   const cur=i>=0?(RULE_RAW[i]||{}):{};
   const sel = `<select class="inp" id="rxKind">`
     + RULE_KINDS.map(k=>`<option value="${esc(k.kind)}"${k.kind===cur.kind?' selected':''}>${esc(k.label)}</option>`).join('')
     + `</select>`;
   modal({title:i>=0?`编辑剔除规则 · ${esc(r[0])}`:'新增剔除规则',
     body:`<div class="tip" style="margin-bottom:10px">配置类数据<b>硬删</b>、不留痕（§9.4）；改规则<b>只影响后续抓取</b>，已产生的剔除标记<b>不重算</b>（§4.2.2）。</div>
       <div class="fld"><label>规则类别 <b>*</b></label>${sel}</div>
       <div class="fld"><label>命中值 <b>*</b>（多个用 ｜ 分隔）</label><input class="inp" id="rxHit" value="${esc(i>=0?r[1]:'')}" placeholder="例：水电｜水费｜电费"></div>
       <div class="fld"><label>剔除的业务含义</label><input class="inp" id="rxWhy" value="${esc(i>=0?r[2]:'')}" placeholder="例：期间费用，非材料/机械"></div>`,
     footer:`<button class="btn" data-act="closeModal">取消</button><button class="btn pri" data-act="ruleSave" data-i="${i}">${i>=0?'保存修改':'新增'}</button>`}); },
 /* ⭐ **落库走后端**：回执一律用后端那句中文原话（含「不重算」提醒）；失败**不关弹窗** ⇒ 已填内容都在。 */
 ruleSave:async t=>{ const i=+t.dataset.i;
   const body={kind:$('#rxKind').value, values:$('#rxHit').value.trim(), meaning:$('#rxWhy').value.trim()};
   if(!body.values) return toast('<b>命中值不能为空</b> —— 弹窗未关闭，已填内容都在');
   try{
     const res = i>=0 ? await API.m14RuleSet((RULE_RAW[i]||{}).id, body) : await API.m14RuleAdd(body);
     if(res.ok===false) return toast(`<b>没能保存</b>：${esc(res.message||'')}`, 8000);
     closeModal(); await reloadM14(); render();
     toast(esc(res.message||'已保存'), 7000);
   }catch(e){ toast(`<b>没能保存</b>：${esc(String((e&&e.message)||e))}`, 8000); } },
 ruleDel:async t=>{ const i=+t.dataset.i, r=RULE_EX[i]; if(!r) return;
   try{
     const res = await API.m14RuleDel((RULE_RAW[i]||{}).id);
     if(res.ok===false) return toast(`<b>没能删除</b>：${esc(res.message||'')}`, 8000);
     await reloadM14(); render();
     toast(esc(res.message||'已删除'), 7000);
   }catch(e){ toast(`<b>没能删除</b>：${esc(String((e&&e.message)||e))}`, 8000); } },
""",
    "④ 三个写动作改走后端",
)

# ============================================================== ⑤ 切片里那句「演示值」
sub1(
    "      <div class=\"tip\" style=\"margin:6px 0 0\"><b>本页各条「命中值」为演示值</b>（原型数据全虚构）；"
    "<b>真实业务配置值一律以《说明书》§4.2.2 为准</b>。<br>⭐ 本表<b>可增 / 删 / 改</b>"
    "（配置类数据 = 硬删、不留痕，§9.4）；<b>改的只是这张演示表本身</b>，"
    "已产生的剔除标记（exrule）不受影响、也不重算。</div></div>",
    "      <div class=\"tip\" style=\"margin:6px 0 0\"><b>本页「命中值」以系统配置为准</b>"
    "（当前来源：${esc(RULE_SRC)}）；初始即《说明书》§4.2.2 那张表。<br>⭐ 本表<b>可增 / 删 / 改</b>"
    "（配置类数据 = 硬删、不留痕，§9.4）；改动<b>只影响后续抓取</b>，"
    "已产生的剔除标记不受影响、也不重算。</div></div>",
    "⑤ V.m14 切片：演示值文案 ⇒ 以系统配置为准（唯一必要改动）",
)

# ============================================================== ⑥ WIRED + boot
sub1(
    "const WIRED=new Set(['m03','m01','m04','m05','m06','m07','m08','m09']);",
    "const WIRED=new Set(['m03','m01','m04','m05','m06','m07','m08','m09','m14']);",
    "⑥ WIRED 加 m14",
)
sub1(
    "  await soft('特殊费用月报表', reloadM09);",
    "  await soft('特殊费用月报表', reloadM09);\n  await soft('规则配置', reloadM14);   /* 独立取数 ⇒ 无顺序依赖 */",
    "⑥ boot() 加一路 soft（规则配置）",
)

# ============================================================== ⑦ 头部注释清单
sub1(
    "**已接线：`m03`/`m01`/`m04`/`m05`/`m06`/`m07`/`m08`/`m09`**（看 `WIRED`）。 */",
    "**已接线：`m03`/`m01`/`m04`/`m05`/`m06`/`m07`/`m08`/`m09`/`m14`**（看 `WIRED`）。 */",
    "⑦ 头部注释：已接线清单补 m14",
)

SHELL.write_text(src, encoding="utf-8")
print("✅ 接线完成，共", len(steps), "处：")
for s in steps:
    print("   ·", s)
