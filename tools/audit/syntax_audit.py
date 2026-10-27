"""语法哨 —— 动手前一次性查出那两类"写完才发现"的错。

## 为什么要有它（用户 2026-09-18 点名："先做引号"）
`TAIL-39` 那一轮我在 `.py` 的**中文串里夹了裸英文双引号**，写成语法错**4 次**
（`tools/_acc_add_ownwh.py` / `tools/_mut_*.py` / `tools/_shell_ownwh.py`），每次都等到**跑起来**才发现、
白费一轮；`.html` 的模板串里塞**反引号**也犯过一次（JS 被当场截断，`node --check` 才报出来）。
⇒ 这两类**都能在动手前一次性查出来**：Python 用 `compile()`、JS 用 `node --check`。

## 两条规则
| 规则 | 判红条件 |
|---|---|
| `Q1` | `backend/app` / `backend/tests` / `tools` 下**任一 `.py` 编译不过**（含"中文串里夹裸双引号"那一族） |
| `Q2` | 壳的**每一件**（`backend/app/web/index.html` 的内联 `<script>` ＋ `backend/app/web/shell/*.js`）**过不了 `node --check`**（如模板串里塞了反引号） |
| `Q3` | ⭐ 2026-09-23：**壳目录里只许有壳的件** —— `backend/app/web/` 下出现**备份 / 散件**（`*.bak-sync` · `*.bak` · `*.old` · 不在 `<script src>` 里的 `.js`/`.html`）⇒ **红** |

⚠️ **`Q3` 为什么要进这个哨**（实测踩到，2026-09-23）：`backend/app/web/shell/actions.js.bak-sync`
（09-21 23:28 · **228KB** · **已进 git**）留在目录里 ⇒ ① 每次 `grep` 都命中它 ⇒ 人眼里是**两份彼此矛盾的
源码**（它停在 09-21，之后所有改动都不在里面）；② 它**不在** `SHELL_PARTS` 里 ⇒ **所有机器判据都不看它**
⇒ 错了也没人管 —— 正是"**双份真源**"的典型（同 `U5`/`D26` 那族）。⇒ **留痕请进 git 历史**，⛔ 别留在源码目录。

⚠️ **本哨只查语法**（⛔ 不做风格评审）：能编译 / 能解析就不是它管的事
（"内层引号一律「」"那条是**人写文时的规矩**，不是机器判据 —— 机器只认"它到底能不能跑"）。
⚠️ `Q2` 需要 `node`；**机器上没有就明说未验并退出2**（⛔ 不静默通过 —— 静默通过比不查更坏）。

## 自检（证明这两条**真的有区分力**）
`python tools/syntax_audit.py --selftest` —— 在临时目录里造两个"已知必错"的样本
（`f"说"话"` 的 `.py` ＋ 模板串里塞反引号的 `.html`）⇒ **必须都判红**；再各造一个"合法"样本 ⇒ **必须放行**。
（本仓的规矩：新判据要能证明"改坏了会红" —— 哨子也一样。）

跑法（工程根）：`backend\\.venv\\Scripts\\python.exe tools\\syntax_audit.py`
"""

from __future__ import annotations

import ast
import re
import shutil
import subprocess
import sys
import tempfile
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

#: `Q1` 扫描范围（`tools/` 也扫 —— 那批一次性脚本 pytest **永远不会 import**，正是漏网的那片）
PY_ROOTS = [ROOT / "backend" / "app", ROOT / "backend" / "tests", ROOT / "tools"]

#: 排除目录（虚拟环境 / 缓存 / 产物：不是本仓手写的源码）
SKIP_DIRS = {".venv", "__pycache__", "node_modules", "var", "data", "exports", "dist", "artifacts", ".git", ".pytest_cache"}

sys.path.insert(0, str(ROOT))
from tools.audit.git_index import staged_changes, index_bytes, index_paths
SHELL_PATH = ROOT / 'backend/app/web/index.html'
SHELL = SHELL_PATH


def shell_parts():
    # 仅全量模式装配现有工作区壳；staged不能在import时先读工作区。
    from tools.audit.shell_source import SHELL_PARTS
    return SHELL_PARTS


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


def _extract_script(html: str) -> str:
    """取**所有内联 `<script>…</script>`** 的内容并起来（壳的执行代码就在其中一块里）。

    ⚠️⚠️ 2026-09-28 修（实测踩到，隐藏了好几年）：原实现取 **`blocks[-1]`（最后一块）**，而
      `index.html` 现在有 **两块** 内联脚本（真正的壳代码 260 KB ＋ 末尾一个 7 字节的空块）
      ⇒ `Q2` 一直在 `node --check` 那个**空块** ⇒ **恒绿**。当场后果：我把一段含反引号的注释写进了
      `V.m05` 返回的**模板字面量文本区**（它截断了模板串）⇒ 整页 `Unexpected identifier 'TAIL'`、
      白屏（`PJs is not defined`），而本尺子仍报「✅ 通过」—— 是本条自己文档里点名要抓的那类错，
      却因为**取错块**而漏掉。⇒ 改成**全部块一起查**（空块无害，真块必查）。
    ⭐ 教训与「判据存在 ≠ 判据在管那件事」同族：**尺子取错了对象 ⇒ 绿得毫无意义**。
    """
    blocks = re.findall(r"<script>(.*?)</script>", html, re.S)
    return "\n".join(b for b in blocks if b.strip())


def rule_q2(shell: Path | None = None, *, parts=None, read=Path.read_bytes) -> tuple[list[str], str]:
    """`Q2` —— 壳的 HTML 内联脚本与 JS 件必须过 `node --check`。

    ⚠️ 2026-09-19（`P4`① 读取点收敛）：壳已按 `web/shell/*.js` 拆件 ⇒ **只查 `index.html` 会静默漏掉接线层**
    （而那正是最容易写错、又最贵的一段）。⇒ 默认逐件查：`index.html` 取它的内联 `<script>`，
    外链件（`.js`）整文件就是脚本。传 `shell=` 时退化成"只查这一件"（`--selftest` 用）。

    返回 `(红清单, 说明)`；无 node ⇒ 红清单为空 ＋ 说明里讲明（⛔ 不是通过）。
    """
    parts = [shell] if shell is not None else shell_parts() if parts is None else parts
    if not parts:
        return [], ""
    node = shutil.which("node")
    if not node:
        return [], "⛔ 机器上没有 `node` ⇒ **跳过 Q2**（⛔ 不是通过 —— 请装 node 或人工跑 `node --check`）"
    tmpdir = Path(tempfile.mkdtemp(prefix="syntax_audit_"))
    bad: list[str] = []
    try:
        for target in parts:
            if target.suffix.lower() not in {".html", ".js"}:
                continue  # CSS belongs to the shell inventory, not the JavaScript parser.
            try:
                text = read(target).decode('utf-8')
            except (FileNotFoundError, KeyError):
                bad.append(f"找不到壳的某一件：{target}")
                continue
            js = _extract_script(text) if target.suffix == ".html" else text
            if not js.strip():
                bad.append(f"{target.name}：{'没找到 `<script>` 块' if target.suffix == '.html' else '是空件'}")
                continue
            tmp = tmpdir / f"{target.stem}.js"
            tmp.write_text(js, encoding="utf-8")
            r = subprocess.run([node, "--check", str(tmp)], capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
            if r.returncode != 0:
                err = (r.stderr or "").strip().splitlines()
                head = next((x for x in err if "SyntaxError" in x), err[0] if err else "未知")
                where = next((x for x in err if re.match(r"^\s*\^+\s*$", x)), "")
                bad.append(f"{target.name} 过不了 `node --check`：{head.strip()[:120]}")
                if where:
                    bad[-1] += f"（提示行：{where.strip()[:60]}）"
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    return bad, ""


def rule_q3(web: Path | None = None, parts: list[Path] | None = None) -> list[str]:
    """`Q3` —— **壳目录里只许有壳的件**（`index.html` ＋ `<script src>` 引到的那几件）。

    ⚠️ 只看 `backend/app/web/` 两层（实测那里只有 `index.html` ＋ `shell/`）。
    ⛔ 判的是"**多余的东西**"：备份/散件会让 `grep` 看见第二份源码，而**所有判据都不看它**。
    """
    base = web if web is not None else SHELL_PATH.parent
    known = {p.resolve() for p in (parts if parts is not None else shell_parts())}
    bad: list[str] = []
    for p in sorted(base.rglob("*")):
        if not p.is_file() or p.resolve() in known:
            continue
        if p.suffix.lower() in {".js", ".html", ".bak", ".old", ".orig"} or ".bak" in p.name:
            try:
                rel = p.relative_to(ROOT)
            except ValueError:
                rel = p
            bad.append(f"{rel}（{p.stat().st_size} 字节）**不是壳的件** ⇒ 备份/散件请进 git 历史，"
                       f"⛔ 别留在 `web/` 里（它会让 grep 看见第二份源码，而所有判据都不看它）")
    return bad


def main(argv: list[str]) -> int:
    print("=" * 78)
    print(" 语法哨 · syntax_audit —— 「能编译吗 / 能解析吗 / 壳目录干净吗 / 改到的件有主文头吗」")
    print("=" * 78)

    staged = '--staged' in argv
    if staged:
        try:
            changes = staged_changes(ROOT)
            changed = [p for p, status in changes.items() if status != 'D']
            sp = [p for p in changed if p.suffix == '.py']
            blobs = {p: index_bytes(ROOT, p) for p in sp}
            web = ROOT / 'backend/app/web'
            parts = []
            q3 = []
            if any(p.is_relative_to(web) for p in changes):
                present = set(index_paths(ROOT, 'backend/app/web'))
                if present:
                    manifest = web / 'index.html'
                    html = index_bytes(ROOT, manifest).decode('utf-8')
                    parts = [manifest] + [web/'shell'/name for name in re.findall(r'/static/shell/([\w.\-]+)', html)]
                    known = set(parts)
                    q3 = [f'{p.relative_to(ROOT)}：暂存区壳清单缺件' for p in known - present]
                    q3 += [f'{p.relative_to(ROOT)}：不是壳的件' for p in present - known
                           if p.suffix.lower() in {'.js', '.html', '.bak', '.old', '.orig'} or '.bak' in p.name]
            targets = [p for p in changed if p in parts and p.suffix.lower() in {'.js', '.html'}]
            blobs.update({p: index_bytes(ROOT, p) for p in targets})
            q1 = rule_q1(sp, read=blobs.__getitem__)
            q2, note = rule_q2(parts=targets, read=blobs.__getitem__)
            q4 = rule_q4(sp, read=blobs.__getitem__)
            n_py = len(sp)
        except (OSError, subprocess.CalledProcessError, UnicodeError, ValueError) as exc:
            print('暂存区读取失败：', (getattr(exc, 'stderr', None) or b'').decode('utf-8', errors='replace') or str(exc))
            return 1
    else:
        q1 = rule_q1()
        n_py = len(iter_py())
        q2, note = rule_q2()
        q3 = rule_q3()
        q4 = []
        parts = shell_parts()
    print(f"\n─ Q1 · 每个 `.py` 必须能编译（{'暂存index' if staged else '全量'}：{n_py} 件）")
    if q1:
        print(f"   ⛔ {len(q1)} 个文件编译不过（⚠️ 中文串里夹裸英文双引号是这一族的高发款 —— 内层一律用「」）：")
        for x in q1[:12]:
            print(f"     · {x}")
    else:
        print("   ✅ 全部通过（⭐ **警告级也当错** —— docstring 里把 Windows 路径写成反斜杠那种逃逸）")

    print("\n─ Q2 · 壳 `<script>` 必须过 `node --check`（⚠️ 模板串里塞反引号是这一族的高发款）")
    if note:
        print(f"   {note}")
    elif q2:
        for x in q2:
            print(f"   ⛔ {x}")
    else:
        print("   ✅ 通过")

    print("\n─ Q3 · 壳目录里只许有壳的件（⛔ 备份/散件会让 grep 看见第二份源码）")
    if q3:
        for x in q3:
            print(f"   ⛔ {x}")
    else:
        print(f"   ✅ 通过（{len(parts)} 件：{', '.join(p.name for p in parts)}）")

    must = len(q1) + len(q2) + len(q3)

    if staged:
        print(f"\n─ Q4 · **本轮暂存**的 `.py` 必须有模块 docstring（{len(sp)} 件）")
        if q4:
            for x in q4[:12]:
                print(f"   ⛔ {x}")
        else:
            print("   ✅ 都有主文头")
        must += len(q4)
    else:
        print("\n─ Q4 · 模块 docstring：跳过（要看它请跑 `syntax_audit.py --staged`）")

    print(f"\n结论：**必须修 {must}**" + ("（有红 ⇒ 非零退出）" if must else ""))
    return 1 if must else 2 if note else 0


def _selftest() -> int:
    """自检：两个"已知必错"样本必须判红、两个"合法"样本必须放行（证明哨子真有区分力）。"""
    ok = True
    unverified = False
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

        bad_html = base / "bad.html"
        bad_html.write_text('<script>const a = `x（`API-05`）y`;</script>', encoding="utf-8")
        good_html = base / "good.html"
        good_html.write_text('<script>const a = `x（<span class="fc">API-05</span>）y`;</script>',
                             encoding="utf-8")
        q2, note = rule_q2(bad_html)
        q2_ok, _ = rule_q2(good_html)
        if note:
            print("自检 Q2：", note, "⇒ 无法自证（先装 node）")
            unverified = True
        else:
            print("自检 Q2：坏样本判红 =", bool(q2), "· 好样本放行 =", not q2_ok)
            if q2:
                print("        ", q2[0][:130])
            ok &= bool(q2) and not q2_ok

        css = base / "shell.css"
        css.write_text(".shell { color: red; }", encoding="utf-8")
        bad_js = base / "bad.js"
        bad_js.write_text("const broken = ;", encoding="utf-8")
        css_bad, _ = rule_q2(css)
        js_bad, _ = rule_q2(bad_js)
        print("自检 Q2②：CSS不当脚本 = ", not css_bad, "· 外链JS坏样本判红 = ", bool(js_bad))
        if not unverified:
            ok &= not css_bad and bool(js_bad)

        # Q3：临时目录里造一个"备份散件" ⇒ 必须判红；把它当作"壳件"传进去 ⇒ 必须放行
        stray = base / "stray.js.bak-sync"
        stray.write_text("// 09-21 的旧备份\n", encoding="utf-8")
        q3_bad = rule_q3(web=base, parts=[])
        q3_ok = rule_q3(web=base, parts=[bad_html, good_html, css, bad_js, stray])
        print("自检 Q3：散件判红 =", bool(q3_bad), "· 壳件放行 =", not q3_ok)
        if q3_bad:
            print("        ", q3_bad[0][:110])
        ok &= bool(q3_bad) and not q3_ok

    print("\n自检结论：", "⛔ 自检未通过" if not ok else "Q2缺node，未完成自证" if unverified else "✅ 四条规则都能区分（坏的红、好的放行）")
    return 1 if not ok else 2 if unverified else 0


if __name__ == "__main__":
    sys.exit(_selftest() if "--selftest" in sys.argv[1:] else main(sys.argv[1:]))
