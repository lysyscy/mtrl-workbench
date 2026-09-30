"""反向灵敏度 · `TAIL-195` 批 1b（`core` 取数口 ＋ 装配层接线）—— **四靶**。

做法：把**故意改坏**（漏接 / 静默 / 回落 / 别名）塞进对应文件（改坏 → 跑 `tests/test_core_bindings.py`
期望红且**那条断言的原话**出现在输出里 → **逐字节复原**）。不红 ⇒ 那条判据是假绿。

- `B1` **漏接一件**：装配层少接一个口（`projects`）⇒ `test_装配层把三个口都接上了` 必红。
- `B2` **静默回空表**：`core/projects.py` 把"没接上 ⇒ 显式报错"改成 `return {}`
  ⇒ ⛔ 那会把"没装配"读成"库里一个项目都没有"（本仓最贵的一类错：看着正常、数字不对）。
- `B3` **回落共享账号**：`core/identity.py` 把"没接上 ⇒ 拒绝"改成回落 ⇒ 拿 `.env` 那个共享账号去登录
  （§7.8：会顶掉同事的在线会话、留痕记错人）。
- `B4` **别名冒充转发**：装配层接成模块级别名（`from …repository import all_projects as _ALIAS`）
  ⇒ `monkeypatch` 打不着（⭐ 批 **2c** 实测踩过的坑：12 条判据当场红）。

⚠️ 判据 = **目标测试件 rc≠0** ＋ **那条断言的原话出现在输出里**（⛔ 别只看 rc）。
⚠️ 子集 pytest 用 `ACC_RESULTS_PATH` 指到 `artifacts/_mut_acc_results.json`（⭐ 别把权威四态冲成残档）。
⚠️ 靶串含中文 ⇒ 一律经 `_b()` 编 bytes（ASCII 字面量的坑见 `_mut_layering` 的注释）。

用法：`python tools/mut/_mut_core_bindings.py`
"""

from __future__ import annotations

import hashlib
import os
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]
APP = ROOT / "backend" / "app"
CORE = APP / "core"
ASSEMBLY = APP / "core_bindings.py"          # 装配层（接线的地方）
PROJECTS_CORE = CORE / "projects.py"         # 取数口之一（项目行）
IDENTITY_CORE = CORE / "identity.py"         # 取数口之一（身份 → i8 绑定）
PY = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"
TARGETS: tuple[str, ...] = ("tests/test_core_bindings.py",)
PARTIAL_ACC = ROOT / "artifacts" / "_mut_acc_results.json"


def _b(text: str) -> bytes:
    return text.encode("utf-8")


CASES: list[tuple[pathlib.Path, str, bytes, bytes, str]] = [
    (ASSEMBLY, "B1 装配层漏接一件（项目行口）",
     _b("    PJ.bind_rows_loader(_project_rows)\n"),
     _b(""),
     "项目行的取数口没接上"),
    (PROJECTS_CORE, "B2 取数口没接上时静默回空表（而不是显式报错）",
     _b('    if _ROWS_LOADER is None:\n'
        '        raise RuntimeError(\n'
        '            "项目行的取数口没接上 ⇒ `project_index` 拒做 —— 见 `app.core_bindings.register_all()`")\n'),
     _b("    if _ROWS_LOADER is None:\n        return {}\n"),
     "不许静默回空表"),
    (IDENTITY_CORE, "B3 身份口没接上时回落 .env（而不是拒绝）",
     _b('        if _BINDING_LOOKUP is None:\n'),
     _b('        if _BINDING_LOOKUP is None:\n'
        '            row = None\n'
        '        elif True:\n'),
     "不许回落"),
    (ASSEMBLY, "B4 取数口接成模块级别名（测试补丁再也打不着）",
     _b('def _project_rows(session):\n'
        '    """取数口 · 全部项目行（**转发**）。"""\n'
        '    from app.mod01_projects import repository as P1R\n'
        '\n'
        '    return P1R.all_projects(session)\n'),
     _b('from app.mod01_projects.repository import all_projects as _P1_ALIAS\n'
        '\n'
        '\n'
        'def _project_rows(session):\n'
        '    """取数口 · 全部项目行（**别名** —— 故意改坏）。"""\n'
        '    return _P1_ALIAS(session)\n'),
     "接成别名了"),
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
