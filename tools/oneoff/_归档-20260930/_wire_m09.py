"""`m09` 特殊费用月报表 · 壳侧接线（`TAIL-27`）—— 一次性批量替换，每处都断言「起点唯一 ＋ 区间含特征串」。

⚠️ 顺序纪律：**先删旧块 → 再替换 → 最后插入**（本脚本按 ①…⑦ 自上而下，互不重叠）。
⚠️ 幂等：每处先查「目标串已在」就直接跳过。
⚠️ 锚必须**唯一** —— 不唯一立刻抛错（不许静默改到别处）。
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SHELL = ROOT / "backend" / "app" / "web" / "index.html"
src = SHELL.read_text(encoding="utf-8")
done: list[str] = []


def sub1(old: str, new: str, tag: str, *, expect: int = 1) -> None:
    """整段替换：`old` 出现次数必须 == `expect`（默认 1）⇒ 否则抛错（不静默）。"""
    global src
    n = src.count(old)
    if n == 0:
        if new in src:
            print(f"  ⏭ {tag}（已接线，跳过）")
            return
        raise SystemExit(f"⛔ {tag}：起点找不到\n--- 期望片段 ---\n{old[:200]}")
    if n != expect:
        raise SystemExit(f"⛔ {tag}：起点命中 {n} 次（期望 {expect}）—— 锚不唯一，先收紧")
    src = src.replace(old, new)
    done.append(tag)
    print(f"  ✅ {tag}")


def sub_block(start: str, end: str, new: str, tag: str) -> None:
    """区间替换 `[start, end]`（`end` 是**该块自己的最后一行**，含行尾）。"""
    global src
    i = src.find(start)
    if i < 0:
        if new in src:
            print(f"  ⏭ {tag}（已接线，跳过）")
            return
        raise SystemExit(f"⛔ {tag}：起点锚找不到\n{start[:160]}")
    if src.count(start) != 1:
        raise SystemExit(f"⛔ {tag}：起点锚命中 {src.count(start)} 次 —— 不唯一")
    j = src.find(end, i)
    if j < 0:
        raise SystemExit(f"⛔ {tag}：终点锚在起点之后找不到\n{end[:160]}")
    j += len(end)
    seg = src[i:j]
    if "awf" not in seg and "AWF" not in seg and "m09" not in seg:
        raise SystemExit(f"⛔ {tag}：区间不含 `awf` 特征串 —— 终点锚吃错了地方")
    src = src[:i] + new + src[j:]
    done.append(tag)
    print(f"  ✅ {tag}（区间 {j - i} → {len(new)} 字符）")


# ============================================================ ① API 客户端
sub1(
    "  m06MechSave: body => API.post('/api/m06/mech', body),\n};",
    "  m06MechSave: body => API.post('/api/m06/mech', body),\n"
    "\n"
    "  /* ---- MOD-09 特殊费用月报表（`TAIL-27`）⚠️ 金额后端出**字符串** ⇒ 适配层过 `N0()` ---- */\n"
    "  m09Fee: (ym, pj) => API.get(`/api/m09/fee?ym=${encodeURIComponent(ym || '')}`\n"
    "    + `&pj=${encodeURIComponent(pj || '')}`),\n"
    "  m09Add: body => API.post('/api/m09/fee/add', body),\n"
    "  m09Name: body => API.post('/api/m09/fee/name', body),\n"
    "  m09Amount: body => API.post('/api/m09/fee/amount', body),\n"
    "  m09Delete: body => API.post('/api/m09/fee/delete', body),\n"
    "};",
    "API 客户端 +m09Fee/+m09Add/+m09Name/+m09Amount/+m09Delete",
)

# ============================================================ ② 数据容器（删演示块）
sub_block(
    "/* ---------- 特殊费用月报表（§5.5，1 自动项 + N 手填项、可增项、项名可改） MOD-09 ----------",
    "const awfTotal = (ym, pj) => { const k = (pj === undefined ? awfPj : pj);"
    " return N2(awfAuto(ym, k) + ((AWF[ym || awfYm] || {})[k] || []).reduce((a, r) => a + r[1], 0)); };",
    """/* ---------- 特殊费用月报表（§5.5，1 自动项 + N 手填项、可增项、项名可改） MOD-09 ----------
   ⭐ **已接后端**（`TAIL-27`）：本页数据**全部来自 `/api/m09/fee`**（由 `reloadM09()` 填）——
      演示容器 `AWF[核算年月][项目键] = [[项名, 金额], …]`（含 3 个月演示值）**已删**。
   ⚠️ **对外的形状不变**：`awfList()` 仍返回 `[[项名, 金额], …]`
      （原型切片按 `r[0]` / `r[1].toFixed(2)` 取用）⇒ **`V.m09` 切片一行不用改**，转形只发生在这一层。
   ⚠️ 金额后端出**字符串** ⇒ 这里**一律过 `N0()`**：不然 `r[1].toFixed` 直接 TypeError **整页崩**。
   ⭐ **判定一律后端**：自动项取数 / 合计 / 金额合法性 / 项名改法，前端**不再自算**（`awfTotal` 直接读后端回包）。 */
let awfYm = bjMonth(-1);                       /* 默认 = 北京时间上月（§9.2，与后端 `domain.default_ym` 同口径） */
let awfPj = '', awfPjOpen = false;
/* ⚠️ 下面这些**只能由 `reloadM09()` 落定** —— `PJs` 是**异步填充**的，
   若仍写成加载时求值（`const x = f(异步变量)`），取数回来时它早已定死成空（**静默空表 / 静默失去候选**，不报错）。 */
let AWF_ROWS = [];        /* 手填项（后端 `manuals`）：`[{index,id,item,amount,…}]` */
let AWF_AUTO = 0;         /* 自动项金额（后端 `auto.amount` = 该核算年月 ＋ 该项目的 `CBS-安文费` 出库） */
let AWF_TOTAL = 0;        /* 合计（后端 `total`）—— 与后端**同一份**算法 */
let AWF_PJS = [];         /* 项目候选（后端 `projects`）—— 键 = **仓库名**（§2.7.4） */
let AWF_CAN_EDIT = false; /* 没有档案行 ⇒ 没有可写的那一份（后端 `can_edit`） */
const awfList = () => AWF_ROWS.map(r => [r.item, N0(r.amount)]);   /* 喂给原型切片的 `[[项名, 金额], …]` */
const awfAuto = () => AWF_AUTO;   /* ⚠️ 原先是前端按 `iv.dd`（**单据日期**）算；口径要的是**核算年月**（`inv_detail.ym`） */
const awfTotal = () => AWF_TOTAL;""",
    "数据容器：删 AWF 演示块，改 4 个后端派生态",
)

# ============================================================ ③ 候选面板 + 默认项目
sub_block(
    "/* 「项目」**单选**面板（2026-09-13 用户裁定）—— 共用 `projPanel`，`single:true` ⇒ 渲染 `radio`、",
    "awfPj = (pjSort(ntPjList())[0] || { name: '' }).name;",
    """/* 「项目」**单选**面板（2026-09-13 用户裁定）—— 共用 `projPanel`，`single:true` ⇒ 渲染 `radio`、
   **不给「全选 / 清空」**。⭐ 候选由 `reloadM09()` 从后端 `/api/m09/fee` 的 `projects` 填（`AWF_PJS`），
   键 = **仓库名**（§2.7.4）—— 与写路径 `repository.project_by_key` **同源**：**选得到的就写得了**。
   ⚠️ 原先读 `pjKeysOfRows(ntPjList())`（档案表全部）—— 那是"能显示"、但不保证后端认；
      接线后一律以后端候选为准（唯一出口 = `mod01_projects.domain.build_candidates`）。
   ⚠️⚠️ `projPanel` 的 `list` 必须是**候选键（仓库名）**，**不是档案行对象**（否则 `data-pj="[object Object]"`）。 */
const awfPjPanel=()=>projPanel({list:()=>AWF_PJS,selected:()=>[awfPj],pickAct:'awfPjPick',meta:PROJ_META_KEY,single:true});
/* ⚠️ 默认项目**不在这里赋** —— 原先写 `(pjSort(ntPjList())[0]||{name:''}).name`，那是**加载时求值**：
   `PJs` 异步填充 ⇒ 取数回来时它早已定死成空（**静默失去默认项目**，且不报错）。
   ⇒ 改由 `reloadM09()` 按后端回包的 `project` 落定（后端 `service._resolve` 已把"没给 / 给了无效值"
     归一成候选第一个；候选为空时才是空串）。 */""",
    "候选面板改 AWF_PJS + 删加载时求值的默认项目",
)

# ============================================================ ④ 写动作
sub_block(
    "  awfPjToggle:()=>{ awfPjOpen=!awfPjOpen; render(); },",
    "  awfReset:()=>{ awfYm=bjMonth(-1); awfPj=(pjSort(ntPjList())[0]||{name:''}).name; awfPjOpen=false; render();\n"
    "    toast(`特殊费用月报表已重置：核算年月回到 <b>${tmLabel(bjMonth(-1))}</b>、项目回到 <b>${esc(PROJ_META_KEY(awfPj).nm)}</b>（材料报表类默认 = 上月，§9.2）`); },",
    """  awfPjToggle:()=>{ awfPjOpen=!awfPjOpen; render(); },
  awfPjPick:t=>{ const v=t.dataset.pj; if(!v) return; awfPj=v; awfPjOpen=false;
    /* ⭐ 切项目 ⇒ **按 (核算年月, 项目) 重取那一份**（手填项是"每项目每月各存一份"，§5.5） */
    reloadM09().then(()=>toast(`特殊费用月报表已切到项目 <b>${esc(PROJ_META_KEY(v).nm)}</b>（自动项与手填项都只算该项目）`)); },
  /* ⭐ 接线：四个写动作**全部走后端**（`/api/m09/fee/*`，与 PRG 端点 `/m09/add` `/m09/cell`
     **同一出口** `service.act_*`）—— ⛔ 前端不再本地改数据冒充落库（原先是 `awfMut().push/splice/赋值`），
     也**不在前端复写判定**。回执里的中文说明（含 §引用）**原样给用户**，失败亦然。 */
  awfAdd:()=>awfAct(()=>API.m09Add({ym:awfYm, project:awfPj}), r=>r.message
    || `已在 <b>${tmLabel(awfYm)}</b> · <b>${esc(PROJ_META_KEY(awfPj).nm)}</b> 增加手填项：<b>名称可改、金额可填</b>（§5.5）`),
  /* `R9`：删除也要说清「做了什么 + 影响多少」—— 后端回执里**带重算后的合计** */
  awfDel:t=>awfAct(()=>API.m09Delete({ym:awfYm, project:awfPj, index:+t.dataset.i}), r=>r.message),
  awfName:t=>awfAct(()=>API.m09Name({ym:awfYm, project:awfPj, index:+t.dataset.i, value:t.value}), r=>r.message),
  /* ⚠️ **前端不判金额合法与否** —— §5.5 的判据唯一出口是后端 `domain.amount_problem`
     （只拦"非数字"、**允许 0 与负数**）；前端再写一遍 = 第二份口径。
     非法 ⇒ 后端拒绝且**原值不变**，重拉后输入框回到库里那个值。 */
  awfAmt:t=>awfAct(()=>API.m09Amount({ym:awfYm, project:awfPj, index:+t.dataset.i, value:t.value}), r=>r.message),
  /* 重置 = 回到默认核算年月 ＋ 默认项目（候选第一个）—— `R4` 要求列表 / 报表页提供「重置」 */
  awfReset:()=>{ awfYm=bjMonth(-1); awfPj=AWF_PJS[0]||''; awfPjOpen=false;
    reloadM09().then(()=>toast(`特殊费用月报表已重置：核算年月回到 <b>${tmLabel(bjMonth(-1))}</b>、项目回到 <b>${esc(PROJ_META_KEY(awfPj).nm)}</b>（材料报表类默认 = 上月，§9.2）`)); },""",
    "四个写动作改走后端（+ 切项目/重置改 reload）",
)

# ============================================================ ⑤ 月份切换 ⇒ 重取数
sub1(
    "   if(sc==='awf'){ awfYm=v; mp.open=null; render();"
    " toast(`特殊费用月报表已切到 <b>${tmLabel(v)}</b>（核算年月，§9.2）`); return; }",
    "   if(sc==='awf'){ awfYm=v; mp.open=null; reloadM09();"
    " toast(`特殊费用月报表已切到 <b>${tmLabel(v)}</b>（核算年月，§9.2）`); return; }"
    "   /* ⭐ 切换核算年月 ⇒ **重新取数**（手填项按「核算年月 ＋ 项目」各存一份；只 `render()` 会看到上一月那一份） */",
    "月份切换 awf ⇒ reloadM09",
)

# ============================================================ ⑥ reloadM09 + awfAct
sub1(
    "async function boot() {",
    """/* ============ MOD-09 特殊费用月报表（前端壳接线 · `TAIL-27`）============
   ⚠️ 后端金额出**字符串**（`numeric(18,2)` 精度保护）⇒ 这里**一律过 `N0()`**：
      原型切片里有 `r[1].toFixed(2)`，字符串会**直接 TypeError 整页崩**（而且不报错地坏）。
   ⚠️ 候选 / 默认项目 / 合计 / 自动项 **全部以后端回包为准**（⛔ 前端不再自算，避免第二份口径）。 */
async function reloadM09() {
  const d = await API.m09Fee(awfYm, awfPj);
  awfYm = d.ym || awfYm;                        /* 后端归一后的核算年月（认不出 ⇒ 回落默认月，§9.2） */
  awfPj = d.project || '';                      /* 后端已把"没给 / 给了无效值"归一成候选第一个 */
  AWF_PJS = (d.projects || []).map(p => p.key).filter(Boolean);
  AWF_ROWS = (d.manuals || []).map(r => ({ index: r.index, id: r.id, item: r.item, amount: N0(r.amount) }));
  AWF_AUTO = N0(d.auto && d.auto.amount);
  AWF_TOTAL = N0(d.total);
  AWF_CAN_EDIT = !!d.can_edit;
  render();
}

/* 写动作统一走这里：**成功/失败都回后端真实状态**，后端那句中文说明**原样转给用户**（不吞、不换句话）。
   ⚠️ 后端对「金额不合法」这类**可预期的拒绝**回的是 **HTTP 200 ＋ `ok:false`**（同 `m07` / `m03`）
      ⇒ 必须**同时**判 `ok === false`，否则那句"金额不合法…"会被当成成功吞掉。 */
async function awfAct(fn, okMsg) {
  let r = null;
  try { r = await fn(); }
  catch (e) {
    await reloadM09();
    return toast(`<b>没能保存</b>：${esc(String((e && e.message) || e))}`, 7000);
  }
  await reloadM09();
  if (!r || r.ok === false) { toast(`<b>没能保存</b>：${esc((r && r.message) || '后端未返回原因')}`, 7000); return null; }
  toast(typeof okMsg === 'function' ? okMsg(r) : okMsg);
  return r;
}

async function boot() {""",
    "新增 reloadM09() 与 awfAct()",
)

# ============================================================ ⑦ boot 逐路容错
sub1(
    "  await soft('收发结存与大表', reloadM07);   /* ⚠️ 必须在 reloadMech / reloadInv **之后**：大表的机械与焊材/气体列取它们 */\n",
    "  await soft('收发结存与大表', reloadM07);   /* ⚠️ 必须在 reloadMech / reloadInv **之后**：大表的机械与焊材/气体列取它们 */\n"
    "  /* ⚠️ `m09` 的自动项与手填项**都由后端自己算**（`mod09_fee/repository.inv_rows` 直读 `inv_detail`）\n"
    "     ⇒ 与壳里的 `IVs` 无关、**不依赖 `reloadInv` 的顺序**（但排在它之后无害）。 */\n"
    "  await soft('特殊费用月报表', reloadM09);\n",
    "boot 加「特殊费用月报表」一路 soft",
)

# ============================================================ ⑧ WIRED
sub1(
    "const WIRED=new Set(['m03','m01','m04','m05','m06','m07','m08']);",
    "const WIRED=new Set(['m03','m01','m04','m05','m06','m07','m08','m09']);",
    "WIRED 加 m09",
)

# ============================================================ ⑨ 注释同步（三处）
sub1(
    "   ── ④ 演示数据（都在文件前半段）：`const JC =` 集采合同 · `const BIGVAL` 大表手填 ·\n"
    "      `const AWF` 特殊费用手填\n"
    "      ⚠️ **付款通知书 / 项目档案 / 付款流水 / 付款计划 / 库存单据（含调整单）的演示数据已删除**",
    "   ── ④ 演示数据（都在文件前半段）：`const JC =` 集采合同 · `const BIGVAL` 大表手填\n"
    "      ⚠️ **付款通知书 / 项目档案 / 付款流水 / 付款计划 / 库存单据（含调整单）/ 收发结存（含活动大表）/\n"
    "      特殊费用手填（`AWF`）的演示数据已删除**",
    "注释④ 演示数据清单同步",
)

sub1(
    "   ⚠️ 其余表（`PLs`/`IVs`/`JCs`/`ADs`/`DFs`/`LGs`/`WHs`/`MACH6`/`AWF`/`BIGVAL`…）**仍是原型模拟数据** ——\n"
    "      对应视图尚未接线（侧栏标「原型态」）。本轮只接 `MOD-03`（打样）。 */",
    "   ⚠️ 其余表（`JCs`/`DFs`/`WHs`… 以及 **集采 / 跨域 / 用户** 各域）**仍是原型模拟数据** ——\n"
    "      对应视图尚未接线（侧栏标「原型态」）。**已接线：`m03`/`m01`/`m04`/`m05`/`m06`/`m07`/`m08`/`m09`**（看 `WIRED`）。 */",
    "注释（数据层）已接线页清单同步",
)

sub1(
    "     · 特殊费用月报表「项目」筛选    → `ntPjList()`           （档案表全部，**排壳**；共用面板 **单选**）",
    "     · 特殊费用月报表「项目」筛选    → `AWF_PJS`             （后端 `/api/m09/fee` 的 `projects` ⇒ 仓库名；共用面板 **单选**）",
    "注释（候选来源索引）m09 同步",
)

SHELL.write_text(src, encoding="utf-8")
print(f"\n共落地 {len(done)} 处：")
for t in done:
    print("  ·", t)
print(f"壳大小 = {len(src)} 字符")
sys.exit(0)
