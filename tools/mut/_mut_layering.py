"""反向灵敏度 · `TAIL-195` 批 1（分层边界：`app/core/**` 不得反向依赖业务包）。

做法：把**故意违规**塞进 `core`（改坏 → 跑 `tests/test_layering.py` 期望红 → **逐字节复原**）。
不红 ⇒ 那条判据是假绿。

三靶：
- `M1` **新增一条反向依赖**（往不在名单里的 `core/config.py` 塞 `import app.mod01_projects`
  —— 它**没触发任何 import 环**（只在 `ast` 层可见）⇒ 只有本判据看得见）⇒ 必须红。
- `M2` **名单不是整件放行**：往**名单里**的 `core/projects.py` 再塞一条**别的**业务包
  （`app.mod05_flow`）⇒ 必须红（若绿，说明名单退化成了"整个文件放行"）。
- `M3` **名单不许留幽灵**：把 `core/projects.py` 那条**已登记**的 import 注释掉
  ⇒ 「放行名单里不许留幽灵条目」必须红。

⚠️ 判据 = **目标测试件 rc≠0** ＋ **那条断言的原话出现在输出里**（⛔ 别只看 rc）。
⚠️ 子集 pytest 用 `ACC_RESULTS_PATH` 指到 `artifacts/_mut_acc_results.json`（⭐ 别把权威四态冲成残档）。

用法：python tools/mut/_mut_layering.py
"""

from __future__ import annotations

import hashlib
import os
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]
CORE = ROOT / "backend" / "app" / "core"
CONFIG = CORE / "config.py"          # 不在放行名单里
PROJECTS = CORE / "projects.py"      # 在放行名单里（测"名单不是整件放行" ＋ "名单不许留幽灵"）
PY = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"
TARGETS: tuple[str, ...] = ("tests/test_layering.py",)
PARTIAL_ACC = ROOT / "artifacts" / "_mut_acc_results.json"

#: ⚠️ 靶串一律写 **ASCII 字面量**（含中文的靶要编 bytes ⇒ 见 `_mut_p5a._b` 的教训）：
#:   本件的三条靶都是 import 语句，天然纯 ASCII。
CASES: list[tuple[pathlib.Path, str, bytes, bytes, str]] = [
    (CONFIG, "M1 往不在名单里的 core 件塞一条业务 import",
     b"from app.core.errors import NotConfiguredError",
     b"from app.core.errors import NotConfiguredError\n"
     b"from app.mod01_projects import models as _ghost  # noqa: F401",
     "反向依赖会成环"),
    (PROJECTS, "M2 往名单里的件再塞**别的**业务包（名单若按整件放行 ⇒ 会漏）",
     b"from app.mod01_projects.models import Project",
     b"from app.mod01_projects.models import Project\n"
     b"from app.mod05_flow import models as _ghost  # noqa: F401",
     "反向依赖会成环"),
    (PROJECTS, "M3 把已登记的反向依赖摘掉（名单就此变成幽灵条目）",
     b"from app.mod01_projects.models import Project",
     b"# from app.mod01_projects.models import Project  # mutated M3",
     "已经不存在"),
]


def run_target() -> tuple[int, str]:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1",
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
        print(out0[-800:])
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
    raise SystemExit(main())
