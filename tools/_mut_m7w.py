# -*- coding: utf-8 -*-
"""反向灵敏度（变异测试）—— `MOD-07` 壳接线断言 **是否真有区分力**。

做法：把实现**故意改坏**若干处，确认**对应断言确实变红**；每次立刻按 bytes 复原，最后核对 MD5。

用法：`cd D:\\dev\\mtrl-workbench && backend/.venv/Scripts/python.exe tools/_mut_m7w.py`

⚠️ 本仓纪律（见 memory §十七）：
1. **一律走 bytes**（`write_text` 在 Windows 会把 `\n` 写成 `\r\n` ⇒ MD5 假 BAD）；
2. 变异片段**含中文**时用 `str` ＋ `.encode()`（`b"…"` 只允许 ASCII）；
3. **行尾按目标文件归一**（本仓源码行尾不统一）；
4. 变异点**必须唯一命中**，否则重写（不得当成"已通过"）；
5. 跑完**必须再跑一次全套 `pytest`**（否则 `acc_results.json` 留的是变异态 ⇒ 报表数字是假的）。

⚠️ 本次首跑就抓出 **2 处假绿**（断言写得不够紧）—— 已同步改紧：
   · `in: N0(` 这条正则缺前缀边界 ⇒ 被 `begin:` 里的子串 `in:` 喂饱；
   · `boot()` 断言用 `body.index("reloadMech")` ⇒ 被**注释里**的同名字串喂饱。
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"
FILES = {
    "shell": ROOT / "backend" / "app" / "web" / "index.html",
    "api": ROOT / "backend" / "app" / "mod07_setl" / "api.py",
    "m06r": ROOT / "backend" / "app" / "mod06_proc" / "router.py",
}

#: (说明, 目标文件, 原文片段, 改坏成, 应当变红的测试名)
MUTATIONS: list[tuple[str, str, str, str, str]] = [
    ("adaptWh 的 in 不过 N0()（字符串会拼进求和）",
     "shell", "in: N0(r.in)", "in: r.in",
     "test_适配层把金额转成数字"),
    ("adaptManual 的金额不过 N0()（手填列合计恒 0）",
     "shell",
     "if (isMoney(i)) return (v == null || v === '') ? null : N0(v);",
     "if (isMoney(i)) return (v == null || v === '') ? null : v;",
     "test_适配层把金额转成数字"),
    ("M() 不再认 null（不可得显示 0.00 = 冒充「确实没有」）",
     "shell", "const M=n=>{if(n==null) return '—';", "const M=n=>{",
     "test_金额格式化认null"),
    ("reloadM07 给 BIGSET 兜底填全部候选（会吃掉用户的「清空」）",
     "shell",
     "  render();\n}\n\n/* 写动作统一外壳",
     "  if (!BIGSET.length) BIGSET.push(...bigCands());\n  render();\n}\n\n/* 写动作统一外壳",
     "test_未选题不得被前端兜底填满"),
    ("bigEdit 不再走后端（回到前端本地改 BIGVAL）",
     "shell", "r=await API.m07BigCell(", "r=await badMoney(",
     "test_大表手填走后端且不在前端复写判据"),
    ("bigPickOk 不再落库",
     "shell", "await API.m07BigSelection(picked);",
     "BIGSET.length=0; picked.forEach(k=>BIGSET.push(k));",
     "test_选题落库走后端"),
    # ⚠️ 2026-09-19 订正（顺手清一条**过时**变异）：原锚点是 `zipSfjc` 的「导出尚未落地」提示，
    #    而 `TAIL-04` 落地后 `zipSfjc` 已改成**真产出并下载**（`test_wired_m07.py` 现在断言的是相反方向）
    #    ⇒ 原锚点/原测试名都不复存在（脚本报 SKIP = **未验证**）。现改指**仍然活着**的那条同族主张：
    #    全站通用导出动作 `exp` **必须仍是那条诚实提示**（`test_tail04_export.py` 钉着）。
    ("通用 exp 回到假成功（谎报已生成文件）",
     "shell",
     "⏳ <b>导出尚未落地</b>（属 TAIL-04）：本页按当前筛选应导出",
     "已生成 <b>导出结果.xlsx</b>（假成功）：本页按当前筛选应导出",
     "test_库存单据两种导出并存互不影响且透视提示与模板形态一致"),
    ("抓取端点不要求二次确认（D9 形同虚设）",
     "api", "confirmed=req.confirm", "confirmed=True",
     "test_抓取端点必须显式确认"),
    ("WIRED 去掉 m07",
     "shell", "'m06','m07','m08'", "'m06','m08'",
     "test_WIRED含m07"),
    # ⚠️ 2026-09-19（性能 `P2`）：`boot()` 改成分组并行 ⇒ 变异形态随之搬（**意图不变**：
    #    把 `reloadM07` 挪到 `reloadMech` 之前 ⇒ 大表机械列会取空）。
    ("boot() 里 reloadM07 排到 reloadMech 之前（取到空值）",
     "shell", "    soft('机械 6 列', reloadMech),\n",
     "    soft('收发结存与大表', reloadM07),\n    soft('机械 6 列', reloadMech),\n",
     "test_boot含m07且逐路容错"),
    ("月份切换不再重新取数（只 render ⇒ 空表）",
     "shell", "if(sc==='wh'){ fWhYm=v; mp.open=null; reloadM07();",
     "if(sc==='wh'){ fWhYm=v; mp.open=null; render();",
     "test_月份切换会重新取数"),
    # ---- `TAIL-38`（录机械费入口）----
    ("录机械费入口没挂上 BIND 钩子",
     "shell", "BIND.m06 = function ()", "BIND.m06x = function ()",
     "test_录机械费入口挂在BIND钩子且不改切片"),
    ("录机械费不再走后端（本地改 MACH6）",
     "shell", "API.m06MechSave(", "MACH6[wh]= (",
     "test_录机械费走后端且不在前端复写判据"),
    ("机械列名不再从后端取（前端硬编码）",
     "shell", "d.columns && d.columns.length", "false",
     "test_机械列名由后端给"),
    ("机械写端点不复用 mech_ui 判据（另写一套）",
     "m06r", "values = mech_ui.parse_mech_values(req.values)",
     "values = {k: Decimal(v) for k, v in (req.values or {}).items()}",
     "test_后端机械写端点存在"),
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

    # ⚠️ 必须再跑一次全套（复原态）：否则 acc_results.json 留的是子集运行的结果 ⇒ 四态报表数字是假的
    print("重跑全套 pytest（复原态）…")
    full = subprocess.run([str(PY), "-m", "pytest", "-q", "tests/"],
                          cwd=ROOT / "backend", capture_output=True, text=True)
    print("  全套 pytest 退出码 =", full.returncode)
    return 0 if (ok_md5 and miss == 0 and hit == len(MUTATIONS) and full.returncode == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
