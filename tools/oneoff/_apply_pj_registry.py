"""**`#1` 面板展开态收进共用件注册表**（`TAIL-104` · 2026-09-26 用户裁定「写在通用模块里，不必靠自觉」）。

方案 = `work/10-designs/设计-共用件收口-面板注册表与委托自动化-20260926.md` §一。
本件是**一次性补丁**：照本仓既有做法 —— **先全断言、再统一写盘**；任一环对不上就**原地停**，⛔ 不写坏壳。

做四件事：
  ① `index.html`：加 `PJ_OPEN` / `pjIsOpen` / `pjToggle` / `pjClose` ＋ `projPanel` 自己派生 key（`data-pj-key`）；
  ② `actions.js`：click 委托里加「**单选面板点一下就收**」；「点面板外面收起」**改成遍历注册表**（名单消失）；
  ③ 11 个 `let XxxPjOpen` 声明删除（化为一行指针注释）＋ 全部读写换成语义调用；
  ④ 断言：迁移后**壳里不许再出现那些裸变量名**（漏一处就停）。

跑法：`backend\\.venv\\Scripts\\python.exe tools\\oneoff\\_apply_pj_registry.py`（dry-run）
      `… _apply_pj_registry.py --apply`（真写盘）
"""

from __future__ import annotations

import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
WEB = REPO / "backend" / "app" / "web"
HTML = WEB / "index.html"
ACT = WEB / "shell" / "actions.js"
LEG = WEB / "shell" / "legacy.js"

#: (变量名, 注册表 key) —— key 必须 = 该面板 `pickAct` 去掉 `Pick`（`projPanel` 就是这么派生的）
FLAGS: tuple[tuple[str, str], ...] = (
    ("pjOpen", "pj"),                 # MOD-03
    ("plPjOpen", "plPj"),             # MOD-04
    ("flPjOpen", "flPj"),             # MOD-05 流水
    ("ledPjOpen", "ledPj"),           # MOD-05 台账（单选）
    ("ledExpPjOpen", "ledExpPj"),     # MOD-05 台账导出（多选）
    ("procPjOpen", "procPj"),         # MOD-06（单选）
    ("procExpPjOpen", "procExpPj"),   # MOD-06 导出（多选）
    ("lgPjOpen", "lgPj"),             # MOD-05 期初占位（单选）
    ("jcPjOpen", "jcPj"),             # MOD-11 筛选（多选）
    ("jcNPjOpen", "jcNPj"),           # MOD-11 新增（单选）
    ("awfPjOpen", "awfPj"),           # MOD-09（单选）
    ("invWhOpen", "invWh"),           # MOD-08 仓库筛选（`pickAct:'invWh'` —— 没有 Pick 后缀）
)

#: 声明行**逐字**替换（`(文件, 原文, 新文)`）—— 都是从壳里 grep 出来的真样子，⛔ 不许凭记忆写
DECLS: tuple[tuple[pathlib.Path, str, str], ...] = (
    (HTML, "let awfPj = '', awfPjOpen = false;", "let awfPj = '';"),
    (HTML, "let pjOpen=false;", "/* 展开态在 `PJ_OPEN`（key='pj' · `#1` 2026-09-26 收口） */"),
    (HTML, "let plPjOpen=false;", "/* 展开态在 `PJ_OPEN`（key='plPj'） */"),
    (HTML, "let lgPjOpen=false;", "/* 展开态在 `PJ_OPEN`（key='lgPj'） */"),
    (HTML, "let ledPjOpen=false;", "/* 展开态在 `PJ_OPEN`（key='ledPj'） */"),
    (HTML, "let ledExpPjOpen=false;", "/* 展开态在 `PJ_OPEN`（key='ledExpPj'） */"),
    (HTML, "let flPjOpen=false;", "/* 展开态在 `PJ_OPEN`（key='flPj'） */"),
    (HTML, "let procPj='', procTab=1, procPjOpen=false;", "let procPj='', procTab=1;"),
    (HTML, "let procExpOn=false, procExpPjOpen=false, procExpPjs=[];",
     "let procExpOn=false, procExpPjs=[];"),
    (HTML, "let jcPjOpen=false;", "/* 展开态在 `PJ_OPEN`（key='jcPj'） */"),
    (HTML, "let jcNPjOpen=false;", "/* 展开态在 `PJ_OPEN`（key='jcNPj'） */"),
    (HTML, "let invWhs=[], invWhOpen=false, fIvCol={}, invColOpen='', invOnlyAdj=false, fIvDir='全部', fIvYm=bjMonth(-1);",
     "let invWhs=[], fIvCol={}, invColOpen='', invOnlyAdj=false, fIvDir='全部', fIvYm=bjMonth(-1);"),
    # `IMP` 状态对象里的那个成员（通用导入面）
    (LEG, "ym: '', pjOpen: false, pjDisp: {}, hasCut: false, hasYm: false,",
     "ym: '', pjDisp: {}, hasCut: false, hasYm: false,"),
)

#: 注册表本体（插在 `projPanel` 定义**之前**）
REGISTRY = """/* ⭐⭐ **浮层面板展开态的唯一主人**（`#1` · 2026-09-26 用户裁定：
   「写在通用模块里，不必靠每个模块设计的时候自觉」）。
   ⛔ 调用点**不再各持一个 `let XxxPjOpen`** —— 全部走 `PJ_OPEN[key]`（key 由面板的 `pickAct` 派生）。
   ⭐ 三条自动行为（一个名字都不用登记 —— 原先那份"13 个名字逐个登记"的名单**整个消失**）：
     ① 点面板里的 `radio` ⇒ **选中后自动收起**（委托层做；多选面板渲染的是 `checkbox` ⇒ 天然不收）；
     ② 点 `.pjwrap` 之外 ⇒ 委托层**遍历注册表全关**；
     ③ 触发按钮 ⇒ `pjToggle(key)`。
   ⚠️ 2026-09-26 两次现场都出在"名单/自觉"上：漏登记 `IMP.pjOpen` ⇒ 用户报障「展开后关不掉」；
      单选点完要不要自收**根本没有规则**（6 处各写）。 */
const PJ_OPEN = {};
const pjIsOpen = k => !!PJ_OPEN[String(k)];
const pjToggle = k => { const s = String(k); PJ_OPEN[s] = !PJ_OPEN[s]; render(); };
const pjClose = k => { const s = String(k); if (PJ_OPEN[s]) { PJ_OPEN[s] = false; return true; } return false; };
"""

#: `projPanel`：派生 key ＋ 把 key 写进输入元素（供委托层认面板）
PANEL_OLD = "const projPanel=c=>{ const meta=c.meta||PROJ_META_FULL, single=!!c.single;"
PANEL_NEW = ("const projPanel=c=>{ const meta=c.meta||PROJ_META_FULL, single=!!c.single;\n"
             "  /* ⭐ key **由 `pickAct` 派生**（`ledPjPick` ⇒ `ledPj`）⇒ ⛔ 调用点不用传、也不会漏传。 */\n"
             "  const pk=String(c.pickAct||'').replace(/Pick$/,'');")
INPUT_OLD = 'data-act="${c.pickAct}" data-pj="${esc(v)}"'
INPUT_NEW = 'data-act="${c.pickAct}" data-pj="${esc(v)}" data-pj-key="${pk}"'

#: 委托层：单选点一下就收
DELEGATE_OLD = """  if(a==='maskBg'){ ACT.maskBg(t,e); return; }
  e.preventDefault(); ACT[a](t,e);
});"""
DELEGATE_NEW = """  if(a==='maskBg'){ ACT.maskBg(t,e); return; }
  e.preventDefault(); ACT[a](t,e);
  /* ⭐ **单选面板点一下就收**（`#1` · 2026-09-26 用户要求「写在通用模块里」）——
     由**委托层**做，⛔ 不靠调用点自觉；多选面板渲染的是 `checkbox` ⇒ 天然不收（"勾完不关、好连续选"）。 */
  if(t.dataset.pjKey && t.type==='radio'){ PJ_OPEN[t.dataset.pjKey]=false; render(); }
});"""

#: 「点面板外面收起」：名单 ⇒ 遍历注册表
CLOSER_OLD = """document.addEventListener('click',e=>{
  if(!pjOpen && !plPjOpen && !flPjOpen && !procPjOpen && !jcPjOpen && !invWhOpen && !awfPjOpen && !ledPjOpen && !lgPjOpen && !jcNPjOpen && !ledExpPjOpen && !procExpPjOpen && !IMP.pjOpen && mp.open===null) return;
  const inEl=cls=>!!(e.target&&e.target.closest&&e.target.closest(cls));
  let ch=false;
  if(pjOpen && !inEl('.pjwrap')){ pjOpen=false; ch=true; }
  if(plPjOpen && !inEl('.pjwrap')){ plPjOpen=false; ch=true; }
  if(procPjOpen && !inEl('.pjwrap')){ procPjOpen=false; ch=true; }
  if(jcPjOpen && !inEl('.pjwrap')){ jcPjOpen=false; ch=true; }
  if(invWhOpen && !inEl('.pjwrap')){ invWhOpen=false; ch=true; }
  if(awfPjOpen && !inEl('.pjwrap')){ awfPjOpen=false; ch=true; }
  if(flPjOpen && !inEl('.pjwrap')){ flPjOpen=false; ch=true; }
  if(ledPjOpen && !inEl('.pjwrap')){ ledPjOpen=false; ch=true; }
  if(ledExpPjOpen && !inEl('.pjwrap')){ ledExpPjOpen=false; ch=true; }
  if(procExpPjOpen && !inEl('.pjwrap')){ procExpPjOpen=false; ch=true; }
  if(lgPjOpen && !inEl('.pjwrap')){ lgPjOpen=false; ch=true; }
  if(jcNPjOpen && !inEl('.pjwrap')){ jcNPjOpen=false; ch=true; }
  if(IMP.pjOpen && !inEl('.pjwrap')){ IMP.pjOpen=false; ch=true; }
  if(mp.open!==null && !inEl('.mpwrap')){ mp.open=null; ch=true; }
  if(ch){ render(); if(lastModal&&lastModal.reopen) lastModal.reopen(); }
});"""
CLOSER_NEW = """document.addEventListener('click',e=>{
  const anyOpen = Object.keys(PJ_OPEN).some(k=>PJ_OPEN[k]);
  if(!anyOpen && mp.open===null) return;
  const inEl=cls=>!!(e.target&&e.target.closest&&e.target.closest(cls));
  let ch=false;
  /* ⭐ `#1`（2026-09-26）：**遍历注册表全关** —— ⛔ 不再逐个列面板名字
     （那份名单正是 2026-09-26 用户报障「展开后关不掉」的根：漏登记一个新面板就静默坏）。 */
  if(!inEl('.pjwrap')) Object.keys(PJ_OPEN).forEach(k=>{ if(PJ_OPEN[k]){ PJ_OPEN[k]=false; ch=true; } });
  if(mp.open!==null && !inEl('.mpwrap')){ mp.open=null; ch=true; }
  if(ch){ render(); if(lastModal&&lastModal.reopen) lastModal.reopen(); }
});"""


#: **Esc 收面板**：原先也是一份**手写名单**（11 个名字逐个置 false）⇒ 同样改成遍历注册表。
#: ⚠️ 本仓"名单式登记"共 **两处**（click 收面板 ＋ Esc 收面板）—— 这就是 `#1` 要一起解决的。
ESC_OLD = ("  if(pjOpen||plPjOpen||flPjOpen||ledPjOpen||procPjOpen||jcPjOpen||invWhOpen||awfPjOpen||lgPjOpen"
           "||jcNPjOpen||ledExpPjOpen||procExpPjOpen||invColOpen!==''||mp.open!==null){ pjOpen=false; plPjOpen=false;"
           " flPjOpen=false; ledPjOpen=false; procPjOpen=false; jcPjOpen=false; invWhOpen=false; awfPjOpen=false;"
           " lgPjOpen=false; jcNPjOpen=false; ledExpPjOpen=false; procExpPjOpen=false; invColOpen=''; mp.open=null;"
           " render(); }")
ESC_NEW = ("  /* ⭐ `#1`（2026-09-26）：**遍历注册表全关** —— ⛔ 不再手写面板名单（`invColOpen` 是另一种控件，单独收）。 */\n"
           "  if(Object.keys(PJ_OPEN).some(k=>PJ_OPEN[k])||invColOpen!==''||mp.open!==null)"
           "{ Object.keys(PJ_OPEN).forEach(k=>{ PJ_OPEN[k]=false; }); invColOpen=''; mp.open=null; render(); }")


def _migrate(text: str, flag: str, key: str, where: str) -> str:
    """一个变量的读写换成语义调用（顺序不可换：`=!` → `=false` → `!F` → 其余读）。"""
    n = len(re.findall(r"\b" + flag + r"\b", text))
    assert n > 0, f"{where}：`{flag}` 一处都没找到（声明已删？那就别再迁）"
    text = re.sub(r"\b" + flag + r"\s*=\s*!\s*" + flag + r"\b", f"pjToggle('{key}')", text)
    text = re.sub(r"\b" + flag + r"\s*=\s*false\b", f"pjClose('{key}')", text)
    text = re.sub(r"!\s*\b" + flag + r"\b", f"!pjIsOpen('{key}')", text)
    text = re.sub(r"\b" + flag + r"\b", f"pjIsOpen('{key}')", text)
    left = re.findall(r"\b" + flag + r"\b", text)
    assert not left, f"{where}：`{flag}` 还剩 {len(left)} 处没迁（⛔ 不许留下裸变量）"
    return text


def _one(text: str, old: str, new: str, where: str, times: int = 1) -> str:
    got = text.count(old)
    assert got == times, f"{where}：命中 {got} 处（期望 {times}）\n  找的是：{old[:110]}"
    return text.replace(old, new, times)


def main(argv: list[str]) -> int:
    files = {p: p.read_text(encoding="utf-8") for p in (HTML, ACT, LEG)}

    # ① 声明：逐字替换（先做 —— 否则 `=false` 那条会把声明也吃掉）
    for path, old, new in DECLS:
        files[path] = _one(files[path], old, new, path.name)

    # ② 注册表 ＋ `projPanel` 派生 key
    files[HTML] = _one(files[HTML], PANEL_OLD, REGISTRY + PANEL_NEW, "index.html(projPanel)")
    files[HTML] = _one(files[HTML], INPUT_OLD, INPUT_NEW, "index.html(面板输入)")

    # ③ 委托层：单选自动收 ＋ 点外面遍历注册表
    files[ACT] = _one(files[ACT], DELEGATE_OLD, DELEGATE_NEW, "actions.js(click 委托)")
    files[ACT] = _one(files[ACT], CLOSER_OLD, CLOSER_NEW, "actions.js(点外面收起)")
    files[ACT] = _one(files[ACT], ESC_OLD, ESC_NEW, "actions.js(Esc 收面板)")

    # ④ 逐变量迁移（`IMP.pjOpen` 是对象成员，单独处理）
    for flag, key in FLAGS:
        for path in (HTML, ACT):
            if re.search(r"\b" + flag + r"\b", files[path]):
                files[path] = _migrate(files[path], flag, key, path.name)
    files[LEG] = _migrate(files[LEG], "pjOpen", "impPj", "legacy.js")

    # ⑤ 反向断言：那些裸变量名**一处都不许再出现**
    for flag, _ in FLAGS:
        for path, text in files.items():
            assert not re.search(r"\b" + flag + r"\b", text), f"{path.name}：`{flag}` 还在（迁移没干净）"

    if "--apply" not in argv:
        print("dry-run ✅ 全部断言通过（⛔ 未写盘）：")
        for path, text in files.items():
            print(f"   {path.name}: {len(text.splitlines())} 行"
                  f"（PJ_OPEN 出现 {text.count('PJ_OPEN')} 次）")
        return 0

    for path, text in files.items():
        path.write_text(text, encoding="utf-8", newline="")
    print("✅ 已写盘：index.html / actions.js / legacy.js")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main(sys.argv))
