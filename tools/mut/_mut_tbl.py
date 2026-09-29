"""反向灵敏度（`TBL` 表格件 —— `TAIL-64` 的**统一表外壳**）—— 证明那两条结构性判据**真有区分力**。

⚠️ 本件为什么必需：
- `TAIL-64` P0（2026-09-24）把「表外壳」抽进 `TBL` 之后，一批**钉源码形态**的判据当场假红
  （实测：`ACC-FEE-MON-001/001-01`）⇒ 判据被改成**结构无关**的两段式：
  **切片委托 `TBL`** ＋ **内核里真做了那件事**（`shell_src.with_tbl()` 把两段拼起来看）。
- ⚠️ 但 P0 **没为这套新判据补反向灵敏度**（表 A 里查不到 `_mut_tbl*`）⇒ "改坏了会不会红"**没人证过**；
  本件补上（随 `TAIL-64` P1b 一起做）。

三十四靶（改完**立刻按 bytes 复原** ＋ MD5 校验；⚠️ `M2` 打 `shell/proj.js`、`M16`~`M21` 与 `M31`~`M34` 打
`shell/actions.js`、`M22`/`M23` 打 `shell/core.js`、`M24`~`M30` 打 `shell/legacy.js` —— 见下方"哑靶"说明）：
- `M1` **去掉委托**：把 `m15` 切片里的 `TBL({head:'<th>登录账号</th>…` 改成 `TBLBROKEN({…`
  （合法标识符 ⇒ **不触发**语法错，只会让"本页主表没走统一出口"那一条红）。
- `M2` **掏空内核**：把 `TBL` 体内的 `+rows.join('')+` 改成 `+''+` ⇒ "内核没把 rows 拼进 tbody"必须红。
- ⭐ `M3`/`M4`（2026-09-29 · `TAIL-64` **P2② `m06`**）：`m06` 那**两张表**各自去掉委托
  （差异表 / 主表 表①·表②）⇒ 两条新判据各自必须红。
- ⭐ `M5`/`M6`/`M7`/`M8`（2026-09-29 · `TAIL-64` **P2③ `m07`**）：`M5` 提取表去掉委托 · `M6` 大表去掉委托 ·
  `M7` 把提取表的 `sort:false` 改回 `true`（⇒ "刻意不可排"那条必须红）· `M8` 两类顺序颠倒。
- ⭐ `M9`/`M10`（2026-09-29 · `TAIL-64` **P2④ `m05`**）：欠款台账 / 付款流水表各自去掉委托。
- ⭐ `M11`（2026-09-29 · `TAIL-64` **P2⑤ `m08`**）：库存单据明细表去掉委托。
- ⭐ `M12`/`M13`/`M14`（2026-09-29 · `TAIL-64` **P3**）：`m03` 付款通知书表 / `m04` 付款计划表 / `home` 状态一览表
  各去掉一处委托。⚠️ `M14` 那处打的是 `${TBL({head:'<th>对象</th>` —— 该表**没有 `key`**（不参与排序）、
  靠 `sty` 传内联色，是 `TBL` 契约里"最偏"的一个调用点。

⚠️ 判据 = **目标测试件 rc≠0**（不是整支尺子）＋ **那条断言的原话出现在输出里**（⛔ 别只看 rc：别的用例红
也会让 rc≠0）。
⚠️ 子集 pytest **必须**把 `ACC_RESULTS_PATH` 指到 `artifacts/_mut_acc_results.json`（`MEMORY-细则 §十七`）
—— ⛔ 否则把**权威四态**冲成残档、`T4` 报红；⚠️ 本件跑完**必须重跑全套**写回（脚本末尾会提醒）。

用法：python tools/mut/_mut_tbl.py
"""

from __future__ import annotations

import hashlib
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SHELL = ROOT / "backend" / "app" / "web" / "index.html"
#: ⭐ 2026-09-29（`TAIL-64` A′）：modal 那批表住在**拆件**里（`shell/actions.js`），不在 `index.html`
#: ⇒ 靶也要自带文件（同 `M2` 的哑靶教训：**别假设源码在 `index.html`**）。
ACTIONS = ROOT / "backend" / "app" / "web" / "shell" / "actions.js"
#: ⭐ 同类：`core.js`（接线层，人工指认那两张表）—— 同上，⛔ 别假设源码在 `index.html`。
CORE = ROOT / "backend" / "app" / "web" / "shell" / "core.js"
#: ⭐ 同类：`legacy.js`（「四个暂留件」—— 系统设置 ＋ 三个历史导入页；**壳新增** ⇒ `U1` 看不见本件）。
LEGACY = ROOT / "backend" / "app" / "web" / "shell" / "legacy.js"
#: ⭐⭐ **2026-09-29 修一个"哑靶"（本件自己的仪器缺陷）**：`M2` 原来只在 `index.html` 里找 `TBL` 内核，
#: 而壳 **2026-09-28 拆件（`P2-a`）**把 `TBL` 从 `index.html` **搬进了 `shell/proj.js`**
#: （`V.*` 切片留在 `index.html`、顶层段搬走）⇒ `M2` 的靶串**从此一次都命中不到**（实测「命中 0 次」）。
#: ⚠️ 它**不是假绿**（脚本会打印「未命中」并 `rc=1`），但那条变异**一直没被验证过**。
#: ⇒ 现在每个靶**自带文件**：`M3`/`M4` 与 `M1` 打 `index.html`（切片在那儿）、`M2` 打 `shell/proj.js`。
PROJ = ROOT / "backend" / "app" / "web" / "shell" / "proj.js"
PY = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"
TARGETS: tuple[str, ...] = ("tests/test_acc_usr_mgmt.py",   #: `m15`（P1b）那两条判据
                            "tests/test_wired_m06.py",      #: ⭐ `m06`（P2②）那两条判据
                            "tests/test_wired_m07.py",      #: ⭐ `m07`（P2③）收发结存 + 提取表
                            "tests/test_wired_m07_big.py",  #: ⭐ `m07`（P2③）月度会大表
                            "tests/test_wired_m05.py",      #: ⭐ `m05`（P2④）欠款台账 + 付款流水
                            "tests/test_wired_m08.py",      #: ⭐ `m08`（P2⑤）库存单据明细
                            "tests/test_wired_m03_list.py",  #: ⭐ `m03`（P3）
                            "tests/test_wired_m04.py",      #: ⭐ `m04`（P3）
                            "tests/test_acc_home_todo.py",  #: ⭐ `home`（P3）状态一览表
                            "tests/test_acc_jc_shell.py",   #: ⭐ `m11`（P3 余量）集采台账表
                            "tests/test_acc_x_exp.py",      #: ⭐ A′（modal）导出清单表
                            "tests/test_ux_pages.py",       #: ⭐ A′（`core.js`）人工指认清单表
                            "tests/test_wired_m03_pay.py")  #: ⭐ A′（modal）批量付款表
PARTIAL_ACC = ROOT / "artifacts" / "_mut_acc_results.json"

def _b(s: str) -> bytes:
    """⚠️ `bytes` 字面量**只能放 ASCII** ⇒ 含中文的靶串必须这样编（踩过：`SyntaxError`）。"""
    return s.encode("utf-8")


#: `(打哪个文件, 说明, 原文, 改坏成, 期望在输出里出现的断言原话)` —— 靶串都是**单行片段** ⇒ 不必做行尾归一
CASES: list[tuple[pathlib.Path, str, bytes, bytes, str]] = [
    (SHELL, "M1 去掉委托（`m15` 主表不再走 `TBL`）", _b("TBL({head:'<th>登录账号</th>"),
     _b("TBLBROKEN({head:'<th>登录账号</th>"), "本页主表没走统一出口"),
    # ⚠️ `M2` 的靶在 `shell/proj.js`（`TBL` 内核所在件）—— 见文件头那段"哑靶"说明
    (PROJ, "M2 掏空内核（`TBL` 不再把 rows 拼进 tbody）", _b("+rows.join('')+(rows.length"),
     _b("+''+(rows.length"), "内核没有把 rows 拼进 `tbody`"),
    # ⭐ 2026-09-29（`TAIL-64` P2② `m06`）：两张表**各自**去掉委托 ⇒ 两条新判据各自必须红
    (SHELL, "M3 去掉委托（`m06` 差异表不再走 `TBL`）", _b("TBL({head:DIFF_THEAD,"),
     _b("TBLBROKEN({head:DIFF_THEAD,"), "差异表的表外壳没走统一出口"),
    (SHELL, "M4 去掉委托（`m06` 主表 表①·表② 不再走 `TBL`）", _b("TBL({head,rows:body,sum:sumRow+totRow})"),
     _b("TBLBROKEN({head,rows:body,sum:sumRow+totRow})"), "主表（表①/表②）的表外壳没走统一出口"),
    # ⭐ 2026-09-29（`TAIL-64` P2③ `m07`）：三张表各自去掉委托 / 把 `sort:false` 改回 `true`
    (SHELL, "M5 去掉委托（`m07` 提取表 不再走 `TBL`）", _b("TBL({cls:'cond',key:'m07:kinds',sort:false,"),
     _b("TBLBROKEN({cls:'cond',key:'m07:kinds',sort:false,"), "提取表没走统一出口"),
    (SHELL, "M6 去掉委托（`m07` 大表 不再走 `TBL`）",
     _b("TBL({head:BIG_THEAD,key:'m07:bigtable',sort:false,sty:'min-width:1620px',headRows:true,"),
     _b("TBLBROKEN({head:BIG_THEAD,key:'m07:bigtable',sort:false,sty:'min-width:1620px',headRows:true,"),
     "大表没走统一出口"),
    (SHELL, "M7 提取表「刻意不可排」失效（`sort:false` 改回 `true`）",
     _b("sort:false,head:EXT_THEAD"), _b("sort:true,head:EXT_THEAD"), "刻意不可排"),
    (SHELL, "M8 提取表两类顺序颠倒（焊材 / 气体 互换）", _b("rows:[extBlock('焊材')+extBlock('气体')]"),
     _b("rows:[extBlock('气体')+extBlock('焊材')]"), "两类的渲染顺序变了"),
    # ⭐ 2026-09-29（`TAIL-64` P2④ `m05`）：本页两张表各自去掉委托
    (SHELL, "M9 去掉委托（`m05` 逐月欠款台账 不再走 `TBL`）", _b("TBL({head:LED_THEAD,key:'m05:ledger-'+sc,"),
     _b("TBLBROKEN({head:LED_THEAD,key:'m05:ledger-'+sc,"), "逐月欠款台账没走统一出口"),
    (SHELL, "M10 去掉委托（`m05` 付款流水表 不再走 `TBL`）", _b("TBL({head:FL_THEAD,key:'m05:flows',"),
     _b("TBLBROKEN({head:FL_THEAD,key:'m05:flows',"), "付款流水表没走统一出口"),
    # ⭐ 2026-09-29（`TAIL-64` P2⑤ `m08`）：库存单据明细表去掉委托
    (SHELL, "M11 去掉委托（`m08` 库存单据明细表 不再走 `TBL`）", _b("TBL({head:ivThead(),key:'m08:invoices',"),
     _b("TBLBROKEN({head:ivThead(),key:'m08:invoices',"), "库存单据明细表没走统一出口"),
    # ⭐ 2026-09-29（`TAIL-64` P3）：三页各去掉一处委托
    (SHELL, "M12 去掉委托（`m03` 付款通知书表 不再走 `TBL`）", _b("TBL({head:NT_THEAD,key:'m03:notices',"),
     _b("TBLBROKEN({head:NT_THEAD,key:'m03:notices',"), "数据区没了"),
    (SHELL, "M13 去掉委托（`m04` 付款计划表 不再走 `TBL`）", _b("TBL({head:PL_THEAD,key:'m04:plans',"),
     _b("TBLBROKEN({head:PL_THEAD,key:'m04:plans',"), "付款计划表没走统一出口"),
    (SHELL, "M14 去掉委托（`home` 状态一览表 不再走 `TBL`）", _b("${TBL({head:'<th>对象</th>"),
     _b("${TBLBROKEN({head:'<th>对象</th>"), "状态一览表没走统一出口"),
    # ⭐ 2026-09-29（`TAIL-64` P3 余量）：`m10`/`m12`/`m11` 三张收尾表
    (SHELL, "M15 去掉委托（`m11` 集采台账表 不再走 `TBL`）", _b("TBL({head:JC_THEAD,key:'m11:jc',"),
     _b("TBLBROKEN({head:JC_THEAD,key:'m11:jc',"), "集采台账表没走统一出口"),
    # ⭐ 2026-09-29（`TAIL-64` A′）：modal 那批（住 `shell/actions.js`）—— 先落两张最简的
    (ACTIONS, "M16 去掉委托（`modal:procExp` 清单表 不再走 `TBL`）",
     _b("TBL({cls:'cond',key:'modal:procExp',"), _b("TBLBROKEN({cls:'cond',key:'modal:procExp',"),
     "没有清单表"),
    (ACTIONS, "M17 去掉委托（`modal:ledExp` 清单表 不再走 `TBL`）",
     _b("TBL({cls:'cond',key:'modal:ledExp',"), _b("TBLBROKEN({cls:'cond',key:'modal:ledExp',"),
     "没有清单表"),
    (ACTIONS, "M18 把可排表标成刻意不可排（`modal:procExp` 塞 `sort:false`）",
     _b("key:'modal:procExp',"), _b("sort:false,key:'modal:procExp',"), "刻意不可排"),
    (ACTIONS, "M19 去掉委托（`modal:debtPick` 选择项目表 不再走 `TBL`）",
     _b("TBL({cls:'cond',key:'modal:debtPick',"), _b("TBLBROKEN({cls:'cond',key:'modal:debtPick',"),
     "没走统一出口"),
    (ACTIONS, "M20 去掉委托（`modal:jcParty` 甲方分类表 不再走 `TBL`）",
     _b("TBL({cls:'cond',key:'modal:jcParty',"), _b("TBLBROKEN({cls:'cond',key:'modal:jcParty',"),
     "没走统一出口"),
    (ACTIONS, "M21 把「刻意不可排」放回可排（`modal:debtPick` 的 `sort:false` 去掉）",
     _b("key:'modal:debtPick',sort:false,"), _b("key:'modal:debtPick',"), "没声明「刻意不可排」"),
    # ⭐ 2026-09-29（`TAIL-64` A′）：`core.js` 那两张「人工指认」清单表（壳新增 · 无 claim 判据）
    (CORE, "M22 去掉委托（「待选仓库」指认清单表 不再走 `TBL`）",
     _b("TBL({cls:'cond',head:'<th>项目全名</th>"), _b("TBLBROKEN({cls:'cond',head:'<th>项目全名</th>"),
     "没走统一出口"),
    (CORE, "M23 去掉委托（「陌生仓库名」指认清单表 不再走 `TBL`）",
     _b("TBL({cls:'cond',head:'<th>陌生仓库名</th>"), _b("TBLBROKEN({cls:'cond',head:'<th>陌生仓库名</th>"),
     "没走统一出口"),
    # ⭐ 2026-09-29（`TAIL-64` A′）：`legacy.js`（四个暂留件）先落三张
    (LEGACY, "M24 去掉委托（「变更留痕」表 不再走 `TBL`）",
     _b("TBL({head:'<th>时间</th><th>设置项</th>"), _b("TBLBROKEN({head:'<th>时间</th><th>设置项</th>"),
     "没走统一出口"),
    (LEGACY, "M25 去掉委托（导入页「本系统要哪些列」对照表 不再走 `TBL`）",
     _b('TBL({cls:\'sm\',head:\'<th style="text-align:left">列名</th>'),
     _b('TBLBROKEN({cls:\'sm\',head:\'<th style="text-align:left">列名</th>'), "没走统一出口"),
    (LEGACY, "M26 去掉委托（导入页「预览」表 不再走 `TBL`）",
     _b("TBL({cls:'sm',head:pcols,"), _b("TBLBROKEN({cls:'sm',head:pcols,"), "没走统一出口"),
    # ⭐ 2026-09-29（`TAIL-64` A′）：`legacy.js` 收尾 4 张（该件裸表归零）
    (LEGACY, "M27 去掉委托（块通用件 `lgBlock` 那张表 不再走 `TBL`）",
     _b("TBL({head:(b.columns || []).map("), _b("TBLBROKEN({head:(b.columns || []).map("),
     "没走统一出口"),
    (LEGACY, "M28 去掉委托（导入页「字段对照」大表 不再走 `TBL`）",
     _b("TBL({cls:'sm',head:'<th style=\"min-width:92px\"></th>'+IMP.cols.map("),
     _b("TBLBROKEN({cls:'sm',head:'<th style=\"min-width:92px\"></th>'+IMP.cols.map("), "没走统一出口"),
    (LEGACY, "M29 去掉委托（导入页「问题行」表 不再走 `TBL`）",
     _b("TBL({cls:'sm',head:'<th>行</th><th>列</th><th>原值</th><th>原因</th>',"),
     _b("TBLBROKEN({cls:'sm',head:'<th>行</th><th>列</th><th>原值</th><th>原因</th>',"), "没走统一出口"),
    (LEGACY, "M30 去掉委托（导入页「技术细节」无表头表 不再走 `TBL`）",
     _b("TBL({cls:'sm',rows:tech.map(k =>"), _b("TBLBROKEN({cls:'sm',rows:tech.map(k =>"),
     "没走统一出口"),
    # ⭐ 2026-09-29（`TAIL-64` A′）：集采三张子表弹窗（**与原型共享** ⇒ 本批做了双边同步）
    (ACTIONS, "M31 去掉委托（`modal:jcInv` 供应商发票子表 不再走 `TBL`）",
     _b("TBL({cls:'cond',key:'modal:jcInv',"), _b("TBLBROKEN({cls:'cond',key:'modal:jcInv',"),
     "没走统一出口"),
    (ACTIONS, "M32 去掉委托（`modal:jcTInv` 贸易公司发票子表 不再走 `TBL`）",
     _b("TBL({cls:'cond',key:'modal:jcTInv',"), _b("TBLBROKEN({cls:'cond',key:'modal:jcTInv',"),
     "没走统一出口"),
    (ACTIONS, "M33 去掉委托（`modal:jcPay` 付款子表 不再走 `TBL`）",
     _b("TBL({cls:'cond',key:'modal:jcPay',"), _b("TBLBROKEN({cls:'cond',key:'modal:jcPay',"),
     "没走统一出口"),
    (ACTIONS, "M34 去掉委托（`modal:batchPay` 批量付款表 不再走 `TBL`）",
     _b("TBL({cls:'cond',key:'modal:batchPay',"), _b("TBLBROKEN({cls:'cond',key:'modal:batchPay',"),
     "没走统一出口"),
]


def run_target() -> tuple[int, str]:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1",
           # ⚠️ 子集跑 ⇒ 四态落**残档**（⛔ 别写权威档 `acc_results.json`）
           "ACC_RESULTS_PATH": str(PARTIAL_ACC)}
    r = subprocess.run([str(PY), "-m", "pytest", "-q", *TARGETS, "-p", "no:cacheprovider",
                        "--tb=line"], cwd=str(ROOT / "backend"), capture_output=True,
                       text=True, encoding="utf-8", errors="replace", env=env)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main() -> int:
    files = sorted({c[0] for c in CASES})
    orig = {p: p.read_bytes() for p in files}
    md5_before = {p: hashlib.md5(b).hexdigest() for p, b in orig.items()}

    rc0, out0 = run_target()
    print(f"基线（未改坏）{' + '.join(TARGETS)} rc={rc0}（应为 0）")
    if rc0 != 0:
        print("  ⛔ 基线就红 ⇒ 先清红再来跑本件")
        return 1

    hit = 0
    for path, desc, old, new, needle in CASES:
        src = orig[path]
        if src.count(old) != 1:
            print(f"  ⛔ {desc} —— 靶串在 `{path.name}` 里命中 {src.count(old)} 次（期望 1）⇒ **未验证**")
            continue
        try:
            path.write_bytes(src.replace(old, new, 1))
            rc, out = run_target()
        finally:
            path.write_bytes(src)                     # ⭐ 立刻按原 bytes 复原
        ok = rc != 0 and needle in out
        print(("  ✅ " if ok else "  ⛔ 未命中 ") + desc + f"  → rc={rc}"
              + ("" if ok else f"（判据「{needle}」没出现在输出里）"))
        hit += ok

    bad = [p.name for p in files
           if hashlib.md5(p.read_bytes()).hexdigest() != md5_before[p]]
    print()
    print(f"  命中 {hit}/{len(CASES)}")
    print(f"  复原校验（MD5 逐字节 · {len(files)} 件）："
          + ("✅ 复原" if not bad else "❌ 未复原 " + ", ".join(bad)))
    print("⚠️ 本件只跑了目标件 ⇒ **接着必须重跑全套 pytest 写回权威四态**（否则报表掉绿）。")
    return 0 if (hit == len(CASES) and not bad) else 1


if __name__ == "__main__":
    sys.exit(main())
