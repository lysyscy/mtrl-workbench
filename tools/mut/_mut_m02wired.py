# -*- coding: utf-8 -*-
"""反向灵敏度（变异测试）—— `m02` 壳接线的断言（`TAIL-27`）。

做法：把**壳里**那几处实现**故意改坏**，确认对应断言**确实变红**；每处跑完**逐字节复原**并核 MD5。
⚠️ 变异点一律**不是"无害变异"**（改了行为不变 ⇒ 断言当然不红），且**不改动断言本身的锚字符串**。
⚠️ 跑 pytest 时把结果**另写**一份（⛔ 别把全套的 `var/state/verification/acc_results.json` 冲掉）。

跑法（工程根）：`backend\\.venv\\Scripts\\python.exe tools\\_mut_m02wired.py`
"""

from __future__ import annotations

from pathlib import Path as _WorkspacePath
import sys as _workspace_sys
_workspace_sys.path.insert(0, str(_WorkspacePath(__file__).resolve().parents[2] / 'tools/audit'))
from workspace_paths import output as _run_output, output_dir as _run_dir

import hashlib
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PY = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"
BE = ROOT / "backend"
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "audit"))  # ⭐ `TAIL-58` 分目录：shell_source 在 audit/
from shell_source import SHELL_PATH as SHELL, pick  # noqa: F401  ← `P4`① 读取点收敛
MUT_RESULTS = str(ROOT / _run_dir() / "_mut_acc_results.json")
T = "tests/test_wired_m02.py"

MUTATIONS: list[dict] = [
    {
        "id": "M1", "file": SHELL,
        "old": "  const kv = host.querySelector('.kv');\n  if (kv) kv.innerHTML = m02EchoKv();",
        "new": "  const kv = host.querySelector('.kv');\n  if (kv) kv.innerHTML = kv.innerHTML;   /* 变异：注入失效（回显卡又变回演示表达式） */",
        "test": T, "k": "两张卡由渲染后注入",
        "why": "回显卡没被真数据覆盖 ⇒ 页面上露出**演示值**（`WHs`/`JCs` 那份）＝ 假话",
    },
    {
        "id": "M2", "file": SHELL,
        "old": "  const tb = host.querySelector('table[data-sort-key=\"m02:logs\"] tbody');\n  if (tb) tb.innerHTML = m02LogRows();",
        "new": "  const tb = host.querySelector('table[data-sort-key=\"m02:logs\"] tbody');\n  if (tb) tb.innerHTML = tb.innerHTML;   /* 变异：日志卡不换真行（留着 8 行硬编码演示） */",
        "test": T, "k": "两张卡由渲染后注入",
        "why": "日志卡还是原型那 8 行假记录 ⇒ 用户看到的是「曾经抓过 1373 行」这种不存在的事",
    },
    {
        "id": "M3", "file": SHELL,
        "old": "  {label: '付款通知书', api: 'API-01', keys: ['付款通知书'], bare_month: true},",
        "new": "  {label: '付款通知书', api: 'API-01', keys: ['付款通知书'], bare_month: false},   /* 变异：不认纯年月 */",
        "test": T, "k": "纯年月的执行记录",
        "why": "回显卡对**已经抓过**的付款通知书说「还没有执行记录」（2026-09-18 真机实测的那条假话）",
    },
    {
        "id": "M4", "file": SHELL,
        # ⚠️ 锚点**不带行首缩进**（ACT 条目是单空格风格，缩进数会漂）⇒ 只替换行内那段文字
        "old": "if(api==='API-05'||tt==='仓库列表') return m02Sync('warehouses');",
        "new": "    if(api==='API-04') return toast('已触发抓取：采购合同信息（模拟）→ 成功');   /* 变异：给没落点的接口编一条 */",
        "test": T, "k": "反向_没落点的接口",
        "why": "给集采域（M5 未开工）那个接口**假装成功** —— 正是 §15 里点名的「假成功」",
    },
    {
        "id": "M5", "file": SHELL,
        "old": "  return !!it.bare_month && /^\\d{4}-\\d{2}$/.test(String(r.target).trim());",
        "new": "  return !!it.bare_month && /^\\d{4}$/.test(String(r.target).trim());   /* 变异：只认年份 */",
        "test": T, "k": "纯年月的执行记录",
        "why": "认法改错（只认 4 位年份）⇒ 真记录认不出来，回显又成「没有记录」",
    },
]


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def run(test: str, k: str) -> int:
    env = dict(os.environ)
    env.update({"PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1",
                "CODEBUDDY_SAFE_DELETE_ENABLED": "0"})
    r = subprocess.run([str(PY), "-m", "pytest", "-q", test, "-k", k, "-p", "no:cacheprovider",
                        "--no-header"], cwd=BE, env=env, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.returncode


def main() -> int:
    ok, bad = 0, 0
    for m in MUTATIONS:
        f = ROOT / m["file"]
        # ⚠️ 2026-09-19（性能 `P4`② 三刀真拆）：壳已拆成多件（`web/shell/*.js`）⇒ 锚点在哪件就改哪件。
        f = pick(f, m["old"], m["new"])
        before = md5(f)
        raw = f.read_bytes()
        eol = b"\r\n" if b"\r\n" in raw else b"\n"
        needle = m["old"].encode("utf-8").replace(b"\n", eol)
        newb = m["new"].encode("utf-8").replace(b"\n", eol)
        cnt = raw.count(needle)
        if cnt != 1:
            print(f"❌ {m['id']} 变异点命中 {cnt} 次（须唯一）—— 源码可能已变，按现码重写锚点")
            bad += 1
            continue
        f.write_bytes(raw.replace(needle, newb))
        try:
            rc = run(m["test"], m["k"])
        finally:
            f.write_bytes(raw)
        same = md5(f) == before
        good = rc != 0 and same
        ok += 1 if good else 0
        bad += 0 if good else 1
        print(f"{m['id']} [m02 壳接线] {'✅ 变红' if rc != 0 else '❌ 仍绿（断言没抓住！）'}"
              f"  rc={rc} · MD5复原={'是' if same else '否❗'}")
        print(f"    {m['file']} ← {m['why']}")

    leftover = Path(MUT_RESULTS)
    if leftover.exists():
        leftover.unlink()
    print(f"\n合计 {ok}/{len(MUTATIONS)} 中 · 源文件全部逐字节复原 = {'是' if bad == 0 else '否'}")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
