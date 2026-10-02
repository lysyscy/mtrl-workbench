"""壳真机自检 · **㊲ `m11` 打开不卡（重绘代价与行数无关）**（`TAIL-214` · 2026-10-02 用户报障）。

**它验什么**：进 `m11`（集采台账 · 20 列 × 330 行）时，单次 `render()` 里
**"会逼浏览器先把布局结算完"的那些读**（`getBoundingClientRect()` ＋ `offset*` / `client*` / `scroll*`）
**调用次数不随行数增长** —— 也就是「量列偏移」这件事**只该按列算一次**，⛔ 不该按行重算。
⚠️ 计数**包含那一族全部**（⛔ 不是只数 `getBoundingClientRect`）：坏写法随时可能换上
`offsetLeft / offsetWidth` 那一套 —— 它们**同样**强制同步布局 ⇒ 只认 rect 的判据**比发生面窄**（假绿）。
自证的 `M2` 就是专门用 `offsetWidth` 造一遍 thrash 来钉这条。

**为什么量"次数"而不量"耗时"**（同族：`tools/probe/_m11_open_time.py` 文件头那条口径）：
  耗时随机器 / 数据量波动 ⇒ 拿它当判据只会变噪音；而"**rect 读 ↔ 样式写**交替"（= layout thrashing）
  在**次数**上有个干净的指纹：坏写法 = **每行 3 次**（329 行 ≈ 987 次），好写法 ≈ **4 次**（只按列量）。
  ⇒ 判据 = **斜率**（把行数缩到 1/6 再量一次，两次的差 ÷ 行数差要 ≈ 0），⛔ 不是"耗时小于多少 ms"。

**病根与证据链**（2026-10-02）：
  `_m11_open_time.py`：T_nav ≈ `render()` ≈ **3 s**（接口只占 19 ms ⇒ 后端无罪）；
  `_m11_profile.py`：CDP 剖面 top1 = `getBoundingClientRect`（≈3.4 s/次），
  **按调用者归账** ⇒ `off`（`shell/actions.js:121`）—— 即 `jcApplyPin()` 在 `tbody` **逐行**量偏移。
  `_m11_verify.py`：**单变量**（打桩 `scrollHost`）⇒ 排除它，把矛头钉回 `off`。

⚠️ **为什么必须在真机**：离线看不见"渲染时读了几次几何"—— 它只在**浏览器里跑起来**才存在；
  ⚠️ 也别用"源码里数 `getBoundingClientRect` 出现几次"替代：那数不出**读了几次**（循环里的那一行可以跑 330 遍）。

**怎么造两个行数**：把 `JCs`（`m11` 的数据源 · `const` 数组 ⇒ **原地** `splice`）在**浏览器内存里**切短一截。
  ⚠️ **只活在浏览器内存里**（同 `_shell_render_check.py` 的口径：不写任何业务数据、不落库）；
  ⚠️ 量完**立刻还原并重画**（本段后面还有别的段要用真机）。
"""

from __future__ import annotations

#: 那张表（`data-sort-key` 是稳定锚 —— 同 `_shell_jcpin.py`）
SEL = 'table[data-sort-key="m11:jc"]'
#: 斜率上限：**每多一行，最多允许多读几次几何**。
#: ⚠️ 坏写法 = **3.0**（每行 3 次 · 实测）；好写法 ≈ **0**（只按列量）⇒ 0.5 既证得动、又不误伤。
MAX_PER_ROW = 0.5
#: 两次量测的**行数差**下限：差得太少 ⇒ 斜率是噪声（这条防"本段空跑还绿"）
MIN_ROWS_GAP = 50

JS = r"""(arg) => {
  const [sel, minAll] = arg;
  let n = 0;
  /* ⭐⭐ 计数**所有会"逼浏览器把布局结算完"的读**（⛔ 别只数 `getBoundingClientRect`）——
     本仓这一族的坏写法随时可能换成 `offsetLeft / offsetWidth` 那一套（它们**同样**强制同步布局），
     只认 rect 就会**瞎掉**（判据覆盖面比发生面窄 = 假绿；2026-10-02 自证的 `M2` 专打这条）。 */
  const rect = Element.prototype.getBoundingClientRect;
  Element.prototype.getBoundingClientRect = function () { n += 1; return rect.apply(this, arguments); };
  const PROPS = ['offsetLeft', 'offsetTop', 'offsetWidth', 'offsetHeight',
                 'clientWidth', 'clientHeight', 'scrollWidth', 'scrollHeight'];
  const descs = [];
  PROPS.forEach(p => {
    const d = Object.getOwnPropertyDescriptor(HTMLElement.prototype, p);
    if (!d || !d.get) return;                       /* 不是访问器 ⇒ 跳过（⛔ 别硬包） */
    descs.push([p, d]);
    Object.defineProperty(HTMLElement.prototype, p,
      Object.assign({}, d, {get () { n += 1; return d.get.call(this); }}));
  });
  const undo = () => {
    Element.prototype.getBoundingClientRect = rect;
    descs.forEach(([p, d]) => Object.defineProperty(HTMLElement.prototype, p, d));
  };
  const rowsN = () => document.querySelectorAll(sel + ' tbody > tr').length;
  const measure = () => {
    n = 0;
    const t0 = performance.now();
    render();
    return { reads: n, ms: Math.round(performance.now() - t0), rows: rowsN() };
  };
  try {
    const all = JCs.slice();
    if (all.length < minAll) {
      return {err: `m11 数据只有 ${all.length} 行（< ${minAll}）⇒ 行数差不够，本段验不了行数无关性`};
    }
    const full = measure();
    const keep = Math.max(10, Math.round(all.length / 6));
    JCs.splice(keep);                                  /* ⚠️ `JCs` 是 `const` ⇒ 只许原地切短（同 `LGs` 的教训） */
    const small = measure();
    JCs.length = 0; all.forEach(r => JCs.push(r));     /* 还原（原顺序、原条数） */
    const back = measure();
    return {all: all.length, keep: keep, full: full, small: small, back: back};
  } finally {
    undo();                                            /* ⛔ 计数器必须摘掉（否则后面那些段全在测"被包过的 DOM"） */
    render();                                          /* ⛔ 必须按原数据重画（不留"半张表"给后面的段） */
  }
}"""


def check(page, errors: list[str]) -> None:
    """㊲ `m11` 重绘代价与行数无关（见文件头）。"""
    from _shell_common import goto

    goto(page, "m11")
    page.wait_for_timeout(200)
    d = page.evaluate(JS, [SEL, 3 * MIN_ROWS_GAP])
    print("㊲ m11 打开不卡（单次重绘的「几何读次数」与行数无关）：")
    if d.get("err"):
        errors.append(f"㊲ {d['err']} —— 本段验不了（⛔ 别让它静默通过：真机是这条唯一的判据面）")
        print(f"   ⛔ {d['err']}")
        return

    full, small = d["full"], d["small"]
    gap = full["rows"] - small["rows"]
    per_row = (full["reads"] - small["reads"]) / gap if gap else 999
    print(f"   · 全量 {d['all']} 行 ⇒ 表内 {full['rows']} 行：`render()` 读几何 **{full['reads']}** 次"
          f" · 耗时 **{full['ms']} ms**")
    print(f"   · 切短到 {d['keep']} 行 ⇒ 表内 {small['rows']} 行：`render()` 读几何 **{small['reads']}** 次"
          f" · 耗时 **{small['ms']} ms**")
    print(f"   · 还原后（{d['back']['rows']} 行）：读 {d['back']['reads']} 次 · 耗时 {d['back']['ms']} ms")

    if gap < MIN_ROWS_GAP:
        errors.append(f"㊲ 两次量测的行数只差 {gap} 行（< {MIN_ROWS_GAP}）⇒ 斜率是噪声，本段无效")
        print(f"   ⛔ 行数差 {gap} < {MIN_ROWS_GAP} ⇒ 本段无效（⛔ 别让它静默通过）")
        return

    ok = per_row <= MAX_PER_ROW
    print(("   ✅" if ok else "   ⛔")
          + f"㊲ 每多一行只多读 **{per_row:.2f}** 次几何（上限 {MAX_PER_ROW}）"
          + ("—— 偏移是按**列**量的，与行数无关" if ok else
             "—— 偏移退化成了**按行**量：`render()` 里「读几何 ↔ 写样式」交替 = layout thrashing，"
             "行数一涨就线性恶化"))
    if not ok:
        errors.append(
            f"㊲ m11 单次重绘的几何读次数**随行数增长**（每行 {per_row:.2f} 次 · 上限 {MAX_PER_ROW}）"
            f"—— 实为 `jcApplyPin()`（`shell/actions.js`）在 `tbody` 逐行重算列偏移"
            f"（=`off(i)` 落在行循环里）⇒ 329 行 × 3 ≈ 987 次「rect 读 ↔ `style.left` 写」交替，"
            f"每次都要对 20 列 × 330 行 ＋ sticky 钉列的大表**重排** ⇒ 单次 `render()` ≈ 3 s"
            f"（用户 2026-10-02 报障「打开 mod11 卡几秒」的根因 · `TAIL-214`）。"
            f"⇒ 修法：**按列的偏移提到行循环外算一次**（读全 ＋ 写全，⛔ 别边读边写）")
