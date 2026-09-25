"""`TAIL-97` 一次性补丁：**壳（`index.html` / `shell/*.js`）⇄ 交付面原型** 同改「三态 ⇒ 两态」。

**为什么要一个脚本**（⛔ 不用一堆 `Edit`）：
  · `ui_parity` 的 `U1` 要求壳的 `V.<页>` 切片与原型同名切片**逐行一致** ⇒ 两边**必须同改**；
  · `U5` 要求 `ENUMS` 等顶层件**逐字一致** ⇒ 更得同改；
  · 改多处必须**先全断言、再统一写盘** —— 按文件写 = 半成品（本项目 2026-09-25 踩过）。

**两条纪律**：
  ① ⛔ **不动行尾**：`index.html` 是 CRLF、原型是 LF ⇒ 先归一到 `\\n`、改完按原风格还原，
     且**先做 round-trip 逐字节比对**（不改任何东西也必须能原样还原 ⇒ 行尾假设错了当场暴露）；
  ② 每条替换**断言命中期望次数** ⇒ 对不上就**整批一行都不写**。

用法：
  `backend/.venv/Scripts/python.exe tools/oneoff/_apply_tail97_two_state.py`          # 只报不写
  `backend/.venv/Scripts/python.exe tools/oneoff/_apply_tail97_two_state.py --apply`  # 真写
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHELL = ROOT / "backend" / "app" / "web" / "index.html"
CORE = ROOT / "backend" / "app" / "web" / "shell" / "core.js"
ACTIONS = ROOT / "backend" / "app" / "web" / "shell" / "actions.js"
PROTO = Path(r"D:\工作\AI\PRD编写夹 - Workbuddy专用\demo\材料报表自动化工作台-交互原型.html")

# (说明, 原文, 改成) —— **壳与原型逐字同改**
BOTH: list[tuple[str, str, str]] = [
    (
        "枚举 `jcTag` 三值 ⇒ 两值（`U5` 顶层件，两边必须逐字一致）",
        "  jcTag:    {vals:['待确认','纳入台账','不纳入'], tone:{待确认:'wn',纳入台账:'ok',不纳入:'in'}},",
        "  jcTag:    {vals:['纳入台账','不纳入'], tone:{纳入台账:'ok',不纳入:'in'}},",
    ),
    (
        "看板：删掉 `nJc`（④ 号待办的口径出口）",
        "  const nJc =JCs.filter(j=>j.tag==='待确认').length;            /* ④ §6.5.3 三态（抓取不覆盖人工标记） */\n",
        "",
    ),
    (
        "看板：`tN`（共 N 项需处理）随之少一项",
        "  const tN=nUn+nOwn+nPl+nJc+nAdj+ph.length+(fDone?0:1)+(fFail?1:0)+(pFail?1:0);",
        "  const tN=nUn+nOwn+nPl+nAdj+ph.length+(fDone?0:1)+(fFail?1:0)+(pFail?1:0);",
    ),
    (
        "看板：撤掉「集采合同待确认」瓦片（用户裁定 9 项 ⇒ 8 项）",
        "    tile('jcPending',nJc,'wn','集采合同待确认',nJc,'三态 = 待确认（抓取不覆盖人工标记） · ','m11','去集采台账'),\n",
        "",
    ),
    (
        "看板：段首注释「9 项待办」⇒ 8",
        "     9 项待办，每项一个 `.kpi` 瓦片：",
        "     8 项待办，每项一个 `.kpi` 瓦片：",
    ),
    (
        "看板：口径对照表那一行（状态机文案）",
        '    <tr><td>集采合同纳入</td><td>待确认 → 纳入台账 / 不纳入</td><td>人工标记，<b>抓取不覆盖</b></td><td class="fc">§6.5.3</td></tr>',
        '    <tr><td>集采合同纳入</td><td>纳入台账 / 不纳入</td><td>抓来即<b>纳入台账</b>；改「不纳入」后<b>抓取不覆盖</b></td><td class="fc">§6.5.3</td></tr>',
    ),
    (
        "`m02` 卡片：「采购合同信息 N 条（待确认 N）」⇒ 纳入台账",
        "        <dt>采购合同信息</dt><dd>${JCs.length} 条（待确认 ${JCs.filter(j=>j.tag==='待确认').length}）</dd>",
        "        <dt>采购合同信息</dt><dd>${JCs.length} 条（纳入台账 ${JCs.filter(j=>j.tag==='纳入台账').length}）</dd>",
    ),
    (
        "`m11`：手工新增 pill 的 title（原写「三态默认待确认」，与代码 `DEFAULT_TAG_ON_CREATE` 本就矛盾）",
        '      <div class="fi"><span class="pill" style="margin:0" title="建一张集采合同主表行（三态默认「待确认」，与抓取行一致）">手工新增合同</span></div>',
        '      <div class="fi"><span class="pill" style="margin:0" title="建一张集采合同主表行（两态默认「纳入台账」，与抓取行一致）">手工新增合同</span></div>',
    ),
    (
        "`m11`：保存按钮的 title（同上）",
        '      <button class="btn pri" data-act="jcRowSave" title="建档（三态默认「待确认」，与抓取行一致）">保存</button>',
        '      <button class="btn pri" data-act="jcRowSave" title="建档（两态默认「纳入台账」，与抓取行一致）">保存</button>',
    ),
    (
        "`m11`：撤掉 KPI「待确认合同」（两态下它恒 0 ⇒ 留着就是一块恒零的假 KPI）",
        '    <div class="kpi wn"><div class="k">待确认合同</div><div class="v">${JCs.filter(j=>j.tag===\'待确认\').length}</div><div class="s">新抓取默认「待确认」</div></div>\n',
        "",
    ),
    (
        "`m11`：筛选栏 label「三态标记」⇒「两态标记」",
        '      <div class="fi"><label>三态标记</label><select class="inp" id="fTag" data-act="jcFilter">${enumOpts(\'jcTag\',fJc.tag,1)}</select></div>',
        '      <div class="fi"><label>两态标记</label><select class="inp" id="fTag" data-act="jcFilter">${enumOpts(\'jcTag\',fJc.tag,1)}</select></div>',
    ),
    (
        "`m11`：行高亮（原「待确认」行加 `hl`）⇒ 只留「不纳入」的 `ex`",
        '    ${jcRows.map((j,i)=>`<tr class="${j.tag===\'待确认\'?\'hl\':j.tag===\'不纳入\'?\'ex\':\'\'}">',
        '    ${jcRows.map((j,i)=>`<tr class="${j.tag===\'不纳入\'?\'ex\':\'\'}">',
    ),
    (
        "`m11`：操作列按钮分叉 ⇒ 两态互切",
        '        ${j.tag===\'待确认\'?`<button class="btn sm pri" data-act="jcTag" data-id="${j.id}" data-v="纳入台账">纳入</button>\n'
        '          <button class="btn sm" data-act="jcTag" data-id="${j.id}" data-v="不纳入">不纳入</button>`\n'
        '          :`<button class="btn sm" data-act="jcTag" data-id="${j.id}" data-v="待确认">是否纳入台账</button>`}',
        '        ${j.tag===\'不纳入\'?`<button class="btn sm pri" data-act="jcTag" data-id="${j.id}" data-v="纳入台账">纳入台账</button>`\n'
        '          :`<button class="btn sm" data-act="jcTag" data-id="${j.id}" data-v="不纳入">不纳入</button>`}',
    ),
    (
        "`m11`：页内口径 tip（三态 ⇒ 两态 ＋ 写明「抓取不覆盖」那条铁律）",
        '      <div class="tip" style="margin:0"><b>三态标记（§6.5.3）</b>：待确认（新抓取默认）→ 纳入台账 / 不纳入。<b>逐条</b>标记，或<b>勾选后一次批量标记</b>（范围 = 当前筛选结果）；<b>已手动标记的在后续全量抓取中持久保留</b>。</div>',
        '      <div class="tip" style="margin:0"><b>两态标记（§6.5.3）</b>：抓来即 <b>纳入台账</b>，可改 <b>不纳入</b>。<b>逐条</b>标记，或<b>勾选后一次批量标记</b>（范围 = 当前筛选结果）；⭐ <b>已手动标记的「不纳入」在后续全量抓取中持久保留</b>（抓取不许改回来）。</div>',
    ),
    (
        "`m11` 段首注释：「三态标记」默认 ⇒「两态标记」默认",
        "⭐ 2026-09-13 用户口径：**「三态标记」默认 = 「纳入台账」**",
        "⭐ 2026-09-13 用户口径：**「两态标记」默认 = 「纳入台账」**",
    ),
]

# (说明, 原文, 改成, 期望命中次数) —— **只在原型**
PROTO_ONLY: list[tuple[str, str, str, int]] = [
    (
        "原型演示数据：合同的「待确认」⇒「纳入台账」（3 行演示 ＋ 1 处新建模板）",
        "'待确认',[],[],[],",
        "'纳入台账',[],[],[],",
        4,
    ),
    (
        "原型态回执 `ACT.jcFetch`：抓取默认值话术",
        "默认标记为「<b>待确认</b>」",
        "默认标记为「<b>纳入台账</b>」",
        1,
    ),
    (
        "原型态回执 `ACT.jcRowSave`：新建默认值话术",
        "—— 三态默认 <b>待确认</b>，需「纳入台账」后才计入欠款统计",
        "—— 两态默认 <b>纳入台账</b>，会自动计入欠款统计",
        1,
    ),
]

# (文件, 说明, 原文, 改成, 期望次数) —— **只在壳的独有件**
SHELL_ONLY: list[tuple[Path, str, str, str, int]] = [
    (
        CORE,
        "抓取回执（`core.js`）：「匹配上（已落库 · 默认「待确认」）」",
        "（已落库 · 默认「待确认」）",
        "（已落库 · 默认「纳入台账」）",
        1,
    ),
    (
        ACTIONS,
        "抓取弹窗流程说明（`actions.js`）：「落库（新抓的默认「待确认」）」",
        "落库（新抓的默认<b>「待确认」</b>）",
        "落库（新抓的默认<b>「纳入台账」</b>）",
        1,
    ),
]


def load(path: Path) -> tuple[str, bool, bytes]:
    raw = path.read_bytes()
    crlf = b"\r\n" in raw
    return raw.decode("utf-8").replace("\r\n", "\n"), crlf, raw


def main() -> int:
    apply = "--apply" in sys.argv
    errors: list[str] = []
    out: list[tuple[Path, str, bool, int]] = []

    def patch(path: Path, items: list[tuple[str, str, str, int]]) -> None:
        text, crlf, raw = load(path)
        # ① round-trip：不改任何东西也必须逐字节还原（行尾假设错了当场暴露）
        back = text.replace("\n", "\r\n") if crlf else text
        if back.encode("utf-8") != raw:
            errors.append(f"{path.name}｜行尾 round-trip 不一致 ⇒ ⛔ 先查行尾假设，本件不动")
            return
        d0, d1 = text.count("\n"), None
        for desc, old, new, want in items:
            n = text.count(old)
            if n != want:
                errors.append(f"{path.name}｜{desc} —— 命中 {n} 次（期望 {want}）")
                continue
            text = text.replace(old, new, want)
        d1 = text.count("\n")
        out.append((path, text, crlf, d1 - d0))

    both = [(d, o, n, 1) for d, o, n in BOTH]
    patch(SHELL, both + [(d, o, n, c) for _p, d, o, n, c in SHELL_ONLY if _p == SHELL])
    patch(PROTO, both + PROTO_ONLY)
    for p, d, o, n, c in SHELL_ONLY:
        if p is not SHELL:
            patch(p, [(d, o, n, c)])

    print("=" * 76)
    print(("  写入" if apply else "  DRY-RUN（只报不写）") + " ·  TAIL-97 壳 ⇄ 原型「三态 ⇒ 两态」补丁")
    print("=" * 76)
    for path, _t, crlf, delta in out:
        print(f"  {path.name:<42} 行数 {delta:+d}   行尾={'CRLF' if crlf else 'LF'}")
    print(f"\n  两边同改 {len(BOTH)} 条 · 仅原型 {len(PROTO_ONLY)} 条 · 仅壳 {len(SHELL_ONLY)} 条")

    if errors:
        print("\n⛔ 有锚点对不上 ⇒ **一行都没写**：")
        for e in errors:
            print("   " + e)
        return 1

    if apply:
        for path, text, crlf, _d in out:
            path.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))
        print("\n  ✅ 已写盘。")
    else:
        print("\n  （加 --apply 才真写。）")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
