"""提交前检查 Python 语法、警告及暂存模块说明。

--staged 只读取 Git stage-0 字节；删除不读取工作区，Git 失败返回非零。
React 的 TypeScript 和构建检查由前端组件命令持有。
"""
from __future__ import annotations

import ast
import subprocess
import sys
import tempfile
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PY_ROOTS = [ROOT / 'backend/app', ROOT / 'backend/tests', ROOT / 'tools']
SKIP_DIRS = {'.venv', '__pycache__', 'node_modules', 'var', 'data', 'exports', 'dist', 'artifacts', '.git', '.pytest_cache'}
sys.path.insert(0, str(ROOT))
from tools.audit.git_index import staged_changes, index_bytes


def iter_py() -> list[Path]:
    out: list[Path] = []
    for root in PY_ROOTS:
        if not root.exists():
            continue
        for p in sorted(root.rglob("*.py")):
            if any(part in SKIP_DIRS for part in p.parts):
                continue
            out.append(p)
    return out


def rule_q1(paths: list[Path] | None = None, *, read=Path.read_bytes) -> list[str]:
    """`Q1` —— 每个 `.py` 必须能 `compile()`。返回红清单（每条含路径 + 行列 + 出错那几行）。

    ⭐⭐ **警告当错**（2026-10-06 加 · `/retro`）：`compile()` 报的 `SyntaxWarning`（最常见 ＝
    docstring 里写了 `D:/dev/...` 这种 **Windows 路径写成反斜杠**（`\\d` 不是合法转义）**只打一行、
    rc 仍 0** ⇒ 闸门全绿而坑留在盘上（当天实测：把仓外绝对路径写进 docstring 就中招）。
    ⚠️ **本条当月就抓到了它自己**：加完这句的**第一次跑**把本文件 docstring 里那处反斜杠路径点了出来
    ⇒ **判据一落地就有牙**，不是"写了规矩等下次"。
    ⇒ 现在 `warnings` 一律 `error`：**警告与错误同判**。
    ⚠️ 开这条前量过：**全仓 884 个 `.py` 零警告**（2026-10-06）⇒ 不存在"存量噪音要我一起清"。
    """
    bad: list[str] = []
    for p in (paths if paths is not None else iter_py()):
        src = read(p).decode("utf-8", errors="replace")
        try:
            rel = p.relative_to(ROOT)
        except ValueError:
            rel = p
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error")
                compile(src, str(p), "exec")
        except SyntaxError as exc:
            lines = src.splitlines()
            i = (exc.lineno or 1) - 1
            ctx = " ｜ ".join(x.strip() for x in lines[max(0, i - 1): i + 1])
            bad.append(f"{rel}:{exc.lineno}: {exc.msg}｜{ctx[:150]}")
        except Warning as exc:                         # `SyntaxWarning` 等落在这一支
            ln = getattr(exc, "lineno", None) or 1
            lines = src.splitlines()
            ctx = " ｜ ".join(x.strip() for x in lines[max(0, ln - 2): ln])
            bad.append(f"{rel}:{ln}: **警告级**（当错）：{exc}｜{ctx[:130]}")
        except ValueError as exc:                     # 例如源码里混入 NUL
            bad.append(f"{p}: 读不出/编译不了：{exc}")
    return bad


def rule_q4(paths: list[Path], *, read=Path.read_bytes) -> list[str]:
    """`Q4` —— **本轮提交/改动到的 `.py` 必须有模块 docstring**（"守什么"写在第一段）。

    ⭐ 为什么只查**改动到的**件（`--staged`）：全仓要求 docstring 会把 `tools/oneoff/` 那批
    一次性脚本全点成红（它们多数没有）⇒ 那是**存量债**，不是本轮的动作。
    ⇒ 口径：**新写/改动的那一件**必须有主文头（同 `mut_cover` 台账抓 docstring 第一段那套思路）。

    ⚠️ 它能抓的一族（本轮真踩过）：**把注释放到 docstring 前面** ⇒ 那段字符串不再是 docstring
    （`__doc__` 变 `None`）⇒ 而"有没有 docstring"没有任何尺子看得见。
    ⛔ 抓不到**函数级**那一种（AST 看不见注释）⇒ 那半条靠 `tools/README.md` 纪律。
    """
    bad: list[str] = []
    for p in paths:
        src = read(p).decode("utf-8", errors="replace")
        try:
            tree = ast.parse(src, str(p))
        except SyntaxError:
            continue                                   # `Q1` 负责报它，这里不重复
        if not (ast.get_docstring(tree) or "").strip():
            try:                                  # ⚠️ 自检样本在仓外（临时目录）⇒ 别让 `relative_to` 崩了整支
                shown = p.relative_to(ROOT)
            except ValueError:
                shown = p
            bad.append(f"{shown}：**模块没有 docstring**"
                       f" ⇒ 下个接手的人不知道它守什么（第一段写「守什么」）")
    return bad


def main(argv: list[str]) -> int:
    staged = '--staged' in argv
    if staged:
        try:
            changes = staged_changes(ROOT)
            paths = [p for p, status in changes.items() if status != 'D' and p.suffix == '.py']
            blobs = {p: index_bytes(ROOT, p) for p in paths}
            q1 = rule_q1(paths, read=blobs.__getitem__)
            q4 = rule_q4(paths, read=blobs.__getitem__)
        except (OSError, subprocess.CalledProcessError, UnicodeError, ValueError) as exc:
            stderr = getattr(exc, 'stderr', None) or b''
            print('暂存区读取失败：', stderr.decode('utf-8', errors='replace') or str(exc))
            return 1
    else:
        paths = iter_py()
        q1 = rule_q1(paths)
        q4 = []
    print(f"Python 语法与警告（{'暂存 index' if staged else '全量'}）：{len(paths)} 件")
    for issue in q1:
        print('  ', issue)
    if staged:
        print(f'暂存模块说明：{len(q4)} 个问题')
        for issue in q4:
            print('  ', issue)
    print(f'必须修：{len(q1) + len(q4)}')
    return 1 if q1 or q4 else 0


def _selftest() -> int:
    """自检：Python 语法、警告与模块说明的坏样本判红、合法样本放行。"""
    ok = True
    with tempfile.TemporaryDirectory(prefix="syntax_selftest_") as d:
        base = Path(d)
        bad_py = base / "bad.py"
        bad_py.write_text('X = f"拒绝理由要说清"为什么不能人工指定"：{1}"\n', encoding="utf-8")
        good_py = base / "good.py"
        good_py.write_text('X = f"拒绝理由要说清「为什么」：{1}"\n', encoding="utf-8")

        q1 = rule_q1([bad_py])
        q1_ok = rule_q1([good_py])
        print("自检 Q1：坏样本判红 =", bool(q1), "· 好样本放行 =", not q1_ok)
        if q1:
            print("        ", q1[0][:130])
        ok &= bool(q1) and not q1_ok

        # Q1 ② 警告级（2026-10-06 加）：docstring 里的 `D:\dev\...` ⇒ `\d` 逃义。
        #   ⚠️ **旧实现对这一族是「编译通过、只打一行警告」⇒ 闸门全绿而坑留在盘上**（当天实测）。
        warn_py = base / "warn.py"
        warn_py.write_text('"""背景（D:\\dev\\.归档-mtrl）。"""\n', encoding="utf-8")
        nowarn_py = base / "nowarn.py"
        nowarn_py.write_text('"""背景（D:/dev/.归档-mtrl）。"""\n', encoding="utf-8")
        q1w = rule_q1([warn_py])
        q1w_ok = rule_q1([nowarn_py])
        print("自检 Q1②：反斜杠路径判红 =", bool(q1w), "· 正斜杠放行 =", not q1w_ok)
        if q1w:
            print("        ", q1w[0][:130])
        ok &= bool(q1w) and not q1w_ok

        # Q4：模块 docstring（抓「注释放 docstring 前面 ⇒ `__doc__` 变 None」那一族）
        nodoc_py = base / "nodoc.py"
        nodoc_py.write_text("X = 1\n", encoding="utf-8")
        withdoc_py = base / "withdoc.py"
        withdoc_py.write_text('"""守什么：这一支守哪条判据。"""\nX = 1\n', encoding="utf-8")
        q4_bad = rule_q4([nodoc_py])
        q4_ok = rule_q4([withdoc_py])
        print("自检 Q4：没 docstring 判红 =", bool(q4_bad), "· 有 docstring 放行 =", not q4_ok)
        if q4_bad:
            print("        ", q4_bad[0][:110])
        ok &= bool(q4_bad) and not q4_ok

    print("\n自检结论：", "通过" if ok else "未通过")
    return 0 if ok else 1



if __name__ == '__main__':
    sys.exit(_selftest() if '--selftest' in sys.argv[1:] else main(sys.argv[1:]))
