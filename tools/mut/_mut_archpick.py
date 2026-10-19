# -*- coding: utf-8 -*-
"""反向灵敏度（变异测试）—— `ACC-PRJ-SYNC-001/001-12 · 001-13`（`TAIL-45`）。

做法：把实现**故意改坏**，确认对应断言**确实变红**；每处跑完**逐字节复原**并核 MD5。
⚠️ 变异点一律**不是**"无害变异"（改了行为不变 ⇒ 断言当然不红），且**不改动断言本身的锚字符串**。
⚠️ 跑 pytest 时把结果**另写**一份（⛔ 别把全套的 `var/state/verification/acc_results.json` 冲掉）。

跑法（工程根）：`backend\\.venv\\Scripts\\python.exe tools\\_mut_archpick.py`
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

MUTATIONS: list[dict] = [
    {
        "id": "M1", "point": "ACC-PRJ-SYNC-001/001-12", "file": "backend/app/mod01_projects/archive_pending.py",
        "old": "        if RECORD_KEY not in detail:\n            continue          # ⚠️ 失败的同步（没建任何行、档案没变）⇒ 跳过它，见口径 1",
        "new": "        if False:          # 变异：把「失败的同步」也当最近一次（清单凭空消失）\n            continue",
        "test": "tests/test_archive_pending.py", "k": "没带清单的同步记录要跳过",
        "why": "「失败那次不换清单」改成照认 ⇒ 同步失败一次，用户的待办凭空消失",
    },
    {
        "id": "M2", "point": "ACC-PRJ-SYNC-001/001-12", "file": "backend/app/mod01_projects/archive_pending.py",
        "old": "        if norm_full_name(full) in have_full:\n            continue            # ① 已经建过行",
        "new": "        if False:            # 变异：不按当前档案现算（已建过行的还摆着）\n            continue",
        "test": "tests/test_archive_pending.py", "k": "已经建过行的当场丢掉",
        "why": "现算失效 ⇒ 用户对着**已经解决**的清单白干（`TAIL-41` 同族）",
    },
    {
        "id": "M3", "point": "ACC-PRJ-SYNC-001/001-12", "file": "backend/app/mod01_projects/archive_pending.py",
        "old": "        if len(left) < 2:\n            continue            # ② 剩下的不够两条 ⇒ 系统下次同步自己建",
        "new": "        if False:            # 变异：剩一个也照样打扰人\n            continue",
        "test": "tests/test_archive_pending.py", "k": "候选不足两条的当场丢掉",
        "why": "「剩下的系统自己能建」也报给用户 ⇒ 白打扰一次（且建出来还是同一条规则）",
    },
    {
        "id": "M4", "point": "ACC-PRJ-SYNC-001/001-13", "file": "backend/app/mod01_projects/archive_pending.py",
        "old": '    if wh not in hit["warehouses"]:',
        "new": '    if False:             # 变异：手填的仓库名也收（§9.4 破）',
        "test": "tests/test_archive_pending.py", "k": "手填或已被占用",
        "why": "守卫没了 ⇒ 人手打的仓库名会写进档案（与 i8 不符的假档案行）",
    },
    {
        "id": "M5", "point": "ACC-PRJ-SYNC-001/001-13", "file": SHELL,
        "old": "pjAct(()=>API.pjArchRow({full_name:it.full, warehouse_name:wh}),",
        "new": "API.pjArchRow({full_name:it.full, warehouse_name:wh}),   /* 变异：绕过统一外壳（不重拉） */",
        "test": "tests/test_wired_m01.py", "k": "建档动作只从后端给的候选",
        "why": "绕过 `pjAct` ⇒ 写完不重拉：清单少一条看不见（本地没改数组也不刷新）",
    },
    {
        "id": "M6", "point": "ACC-PRJ-SYNC-001/001-13", "file": SHELL,
        "old": "  const opts = it.whs.map(w => `<option value=\"${esc(w)}\">${esc(w)}</option>`).join('');",
        "new": "  const opts = it.stored.map(w => `<option value=\"${esc(w)}\">${esc(w)}</option>`).join('');  /* 变异：把「当时那份」当选 */",
        "test": "tests/test_wired_m01.py", "k": "建档动作只从后端给的候选",
        "why": "候选换成含「已被占用」的那份 ⇒ 用户选到必被后端拒的名字（白填一次）",
    },
]


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def run(test: str, k: str) -> int:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["ACC_RESULTS_PATH"] = MUT_RESULTS
    r = subprocess.run([str(PY), "-m", "pytest", "-q", test, "-k", k, "-p", "no:cacheprovider",
                        "--no-header", "-x"], cwd=BE, env=env, capture_output=True, text=True,
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
        # ⚠️ **行尾归一**（本仓 .py 有 CRLF 也有 LF）：锚点一律按 `\n` 写，这里换成目标文件的行尾
        #    —— 不换的话多行锚点会**永远"命中 0"**（2026-09-18 实测踩到）。
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
        print(f"{m['id']} [{m['point']}] {'✅ 变红' if rc != 0 else '❌ 仍绿（断言没抓住！）'}"
              f"  rc={rc} · MD5复原={'是' if same else '否❗'}")
        print(f"    {m['file']} ← {m['why']}")

    leftover = ROOT / MUT_RESULTS
    if leftover.exists():
        leftover.unlink()
    print(f"\n合计 {ok}/{len(MUTATIONS)} 中 · 源文件全部逐字节复原 = {'是' if bad == 0 else '否'}")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
