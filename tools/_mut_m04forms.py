"""反向灵敏度（m04 强制通过 · 请求级断言）—— 证明新断言**真的有区分力**。

做法：逐个把实现故意改坏 ⇒ 断言**对应的那条测试确实变红** ⇒ 逐字节复原（MD5）。
    python tools/_mut_m04forms.py
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
B = ROOT / "backend"
PY = B / ".venv" / "Scripts" / "python.exe"
TEST = "tests/test_page_m04_forms.py"

ROUTER = B / "app" / "mod04_plan" / "router.py"
REPO = B / "app" / "mod04_plan" / "repository.py"
DOMAIN = B / "app" / "mod04_plan" / "domain.py"
VIEW = B / "app" / "mod04_plan" / "view.py"

CASES: list[tuple[str, Path, str, str]] = [
    ("M1 端点参数退回 Query（表单提交即 422）", ROUTER,
     "    row_id: int = Form(...),\n    remark: str = Form(\"\"),",
     "    row_id: int = Query(...),\n    remark: str = Form(\"\"),"),
    ("M2 强制通过不再落备注（留痕丢失）", REPO,
     '    row.forced_remark = str(remark or "").strip()',
     '    row.forced_remark = ""'),
    ("M3 空备注不再被拒（口径失守）", DOMAIN,
     '    if not text:\n        raise MustReportError("强制通过必须填写备注（说明为什么放行）—— 空备注不被接受")',
     "    if False:\n        pass"),
    ("M4 页面不再给出强制通过入口", VIEW,
     'action="/m04/force">\'',
     'action="/m04/forceX">\''),
]


def run_tests() -> tuple[int, bool]:
    p = subprocess.run([str(PY), "-m", "pytest", "-q", TEST],
                       cwd=B, capture_output=True, text=True, encoding="utf-8")
    out = p.stdout + p.stderr
    failed = "failed" in out or p.returncode != 0
    return p.returncode, failed


def md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def main() -> int:
    before = {p: (p.read_bytes(), md5(p)) for p in (ROUTER, REPO, DOMAIN, VIEW)}
    _, failed0 = run_tests()
    print(f"  基线：全部通过 = {not failed0}")
    if failed0:
        print("  ⛔ 基线就不是全绿 ⇒ 停手")
        return 1

    hits = 0
    for name, path, old, new in CASES:
        text = path.read_text(encoding="utf-8")
        if old not in text:
            print(f"  ❌ {name} —— 变异串没找到（实现已变？）")
            continue
        path.write_text(text.replace(old, new, 1), encoding="utf-8")
        rc, failed = run_tests()
        path.write_bytes(before[path][0])          # 立刻复原
        print(f"  {'✅' if failed else '❌'} {name} —— 期望变红 ⇒ {'命中' if failed else '仍绿（断言没区分力）'}")
        hits += 1 if failed else 0

    ok = all(md5(p) == before[p][1] for p in before)
    print(f"\n  复原校验（MD5 逐字节）：{'✅ 4/4' if ok else '❌ 有文件没复原'}")
    print(f"  反向灵敏度：**{hits}/{len(CASES)} 命中**")
    return 0 if (hits == len(CASES) and ok) else 1


if __name__ == "__main__":
    sys.exit(main())
