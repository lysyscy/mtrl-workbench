# -*- coding: utf-8 -*-
"""反向灵敏度（变异测试）—— `MOD-09` 壳接线断言 **是否真有区分力**。

做法：把实现**故意改坏**若干处，确认**对应断言确实变红**；每次立刻按 bytes 复原，最后核对 MD5。

用法：`cd D:\\dev\\mtrl-workbench && backend/.venv/Scripts/python.exe tools/_mut_m09.py`

⚠️ 本仓纪律（见 memory §十七）：
1. **一律走 bytes**（`write_text` 在 Windows 会把 `\\n` 写成 `\\r\\n` ⇒ MD5 假 BAD）；
2. 变异片段**含中文**时用 `str` ＋ `.encode()`（`b"…"` 只允许 ASCII）；
3. **行尾按目标文件归一**（本仓源码行尾不统一）；
4. 变异点**必须唯一命中**，否则重写（不得当成"已通过"）；
5. 默认重跑复原态全套 `pytest`；显式 `--no-full-suite` 跳过，本轮不刷新权威四态。

⚠️ 本次首跑抓出 **3 处假绿**（两处是**断言**不够紧、一处是**变异点**没改干净）—— 已同步收紧：
   · `awfPj = d.project` 那条断言**放错了测试**（写在「数据源」那条里，而变异号指的是「候选与默认项目」那条）
     ⇒ 断言搬进它自己该管的用例；
   · 「后端剔除页面专用列」原写成 `"D.PAGE_ONLY_KEYS" in API` —— **文档注释里的 `domain.PAGE_ONLY_KEYS`
     含该子串** ⇒ 把实现改成 `if False:` **照样绿**（同族坑：断言被前缀/子串喂饱）⇒ 改为钉 `_row()` 函数体；
   · 「awfAdd 不再走后端」的变异写成 `()=>null && API.m09Add(` —— **`API.m09Add(` 还在** ⇒ 变异根本没改掉那处调用。
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "audit"))  # ⭐ `TAIL-58` 分目录：shell_source 在 audit/
from shell_source import SHELL_PATH, pick  # noqa: E402  ← `P4`① 读取点收敛

ROOT = Path(__file__).resolve().parents[2]
PY = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"
FILES = {
    "shell": SHELL_PATH,
    "api": ROOT / "backend" / "app" / "mod09_fee" / "api.py",
}

#: (说明, 目标文件, 原文片段, 改坏成, 应当变红的测试名)
MUTATIONS: list[tuple[str, str, str, str, str]] = [
    ("awfList 的金额不过 N0()（切片里的 toFixed 会崩）",
     "shell", "[r.item, N0(r.amount)]", "[r.item, r.amount]",
     "test_m09适配层把金额转成数字"),
    ("awfAuto 回到前端按 IVs 自算（口径错成「单据日期」）",
     "shell", "const awfAuto = () => AWF_AUTO;", "const awfAuto = () => IVs.length;",
     "test_m09自动项不再由前端按单据日期算"),
    ("awfTotal 回到前端自算（第二份口径）",
     "shell", "const awfTotal = () => AWF_TOTAL;",
     "const awfTotal = () => N2(AWF_AUTO + AWF_ROWS.reduce((a, r) => a + r.amount, 0));",
     "test_m09合计不再由前端自算"),
    ("演示容器 AWF 又回来了",
     "shell", "let AWF_ROWS = [];", "let AWF = { '2026-08': {} };\nlet AWF_ROWS = [];",
     "test_m09演示容器已删"),
    ("reloadM09 不落定默认项目（静默空）",
     "shell", "awfPj = d.project || '';", "awfPj = awfPj;",
     "test_m09候选与默认项目由重拉落定"),    ("候选面板又读 ntPjList()（与后端未必同源）",
     "shell", "projPanel({list:()=>AWF_PJS,", "projPanel({list:()=>pjKeysOfRows(ntPjList()),",
     "test_m09面板候选用后端清单"),
    ("awfAdd 不再走后端",
     "shell", "awfAdd:()=>awfAct(()=>API.m09Add(", "awfAdd:()=>awfAct(()=>localAdd(",
     "test_m09四个写动作都走后端"),
    ("awfDel 本地删数据冒充落库",
     "shell", "awfDel:t=>awfAct(()=>API.m09Delete({ym:awfYm, project:awfPj, index:+t.dataset.i}), r=>r.message)",
     "awfDel:t=>(AWF_ROWS.splice(+t.dataset.i,1),awfAct(()=>API.m09Delete({ym:awfYm, project:awfPj, index:+t.dataset.i}), r=>r.message))",
     "test_m09不得本地改数据冒充落库"),
    ("awfAmt 在前端复写金额判据",
     "shell", "awfAmt:t=>awfAct(()=>API.m09Amount(",
     "awfAmt:t=>awfAct(()=>isNaN(+t.value) ? null : API.m09Amount(",
     "test_m09金额判据不在前端复写"),
    ("awfAct 不判 ok===false（后端那句原因被吞）",
     "shell", "  await reloadM09();\n  if (!r || r.ok === false) {", "  await reloadM09();\n  if (!r) {",
     "test_m09失败也要看回执"),
    ("月份切换不再重新取数（看到上一月那一份）",
     "shell", "if(sc==='awf'){ awfYm=v; mp.open=null; reloadM09();",
     "if(sc==='awf'){ awfYm=v; mp.open=null; render();",
     "test_m09切月份切项目都重取数"),
    ("V.m09 切片里直连后端（原型渲染逻辑被改）",
     "shell", "  const list=awfList();", "  const list=API.m09Fee();",
     "test_m09切片不得直连后端"),
    ("WIRED 去掉 m09",
     "shell", "'m08','m09'", "'m08'",
     "test_m09已进WIRED与boot"),
    # ⚠️ 2026-09-19（性能 `P3` 主体）：`boot()` **不再逐路拉** ⇒ 原锚点（`soft('特殊费用月报表', reloadM09)`）
    #    **已不存在**（脚本会报 SKIP＝未验证）。改指**取数表**里的同一个意图：m09 没有取数出口 ⇒
    #    `test_m09已进WIRED与boot` 的「`LOADERS` 里有「特殊费用月报表」」会红。
    ("取数表里没有 m09 这一路（那页永远空）",
     "shell", "  '特殊费用月报表': reloadM09,", "  '特殊费用月报表X': reloadM09,",
     "test_m09已进WIRED与boot"),
    ("后端读端点不走 _payload",
     "api", 'return _payload(s, ym=str(p.get("ym") or ""), pj=str(p.get("pj") or ""))',
     "return {}",
     "test_后端m09端点存在且复用service出口"),
    ("后端 _payload 不走 build_page_data（另写一套组装）",
     "api", 'data = SV.build_page_data(s, SV.parse_state({"ym": ym, "pj": pj}))',
     "data = {}",
     "test_后端m09端点存在且复用service出口"),
    ("后端写端点不走 act_delete（另写一套）",
     "api", "return _flash(SV.act_delete(s, ym=req.ym, project_key=req.project, index=req.index))",
     'return _flash({"kind": "ok", "message": "已删除"})',
     "test_后端m09端点存在且复用service出口"),
    ("后端不剔除页面专用列（ops 漏进 API）",
     "api", "if k in D.PAGE_ONLY_KEYS:", "if False:",
     "test_后端m09端点剔除页面专用列"),
]


def _fit(fragment: bytes, sample: bytes) -> bytes:
    if b"\r\n" in sample:
        return fragment.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    return fragment.replace(b"\r\n", b"\n")


def main() -> int:
    orig = {k: p.read_bytes() for k, p in FILES.items()}
    md5_before = {k: hashlib.md5(v).hexdigest() for k, v in orig.items()}
    for k, v in orig.items():
        print(f"{k}: {len(v)} 字节 · MD5 {md5_before[k][:12]}")

    hit = miss = 0
    for i, (label, fkey, old, new, test_name) in enumerate(MUTATIONS, 1):
        # ⚠️ 2026-09-19（性能 `P4`② 三刀真拆）：壳是多件 ⇒ 锚点在哪件就改哪件（⛔ 仍逐字节复原）。
        #    ⚠️ 判断基准一律用**原始** `SHELL_PATH`：`FILES["shell"]` 已被上一条改成别的件，
        #    拿它当基准会**累积失效**（实测：第 6 条起全 SKIP）。
        if fkey == "shell":
            FILES["shell"] = pick(SHELL_PATH, old, new)
            orig["shell"] = FILES["shell"].read_bytes()
            md5_before["shell"] = hashlib.md5(FILES["shell"].read_bytes()).hexdigest()
        target = orig[fkey]
        o = _fit(old.encode("utf-8"), target)
        n = _fit(new.encode("utf-8"), target)
        cnt = target.count(o)
        if cnt != 1:
            print(f"  {i:2d}. ⚠️ SKIP（变异点命中 {cnt} 次）—— [{fkey}] {label}")
            miss += 1
            continue
        FILES[fkey].write_bytes(target.replace(o, n))
        r = subprocess.run(
            [str(PY), "-m", "pytest", "-q", "-k", test_name, "tests/"],
            cwd=ROOT / "backend", capture_output=True, text=True,
        )
        bad = r.returncode != 0
        print(f"  {i:2d}. {'✅ 变红' if bad else '⛔ 仍绿（假绿！）'} —— [{fkey}] {label}  [{test_name}]")
        if bad:
            hit += 1
        FILES[fkey].write_bytes(target)

    md5_after = {k: hashlib.md5(p.read_bytes()).hexdigest() for k, p in FILES.items()}
    ok_md5 = all(md5_after[k] == md5_before[k] for k in FILES)
    print(f"\n命中 {hit}/{len(MUTATIONS) - miss} · SKIP {miss} · "
          f"MD5 {'逐字节复原 ✅' if ok_md5 else '⛔ 不一致'}")

    # 默认保留复原态完整测试；写权威四态仍需显式结果出口。
    if "--no-full-suite" in sys.argv:
        print("跳过全套 pytest（--no-full-suite）：本轮不刷新权威四态")
        full_rc = 0
    else:
        print("重跑全套 pytest（复原态）…")
        full = subprocess.run([str(PY), "-m", "pytest", "-q", "tests/"],
                              cwd=ROOT / "backend", capture_output=True, text=True)
        print("  全套 pytest 退出码 =", full.returncode)
        full_rc = full.returncode
    return 0 if (ok_md5 and miss == 0 and hit == len(MUTATIONS) and full_rc == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
