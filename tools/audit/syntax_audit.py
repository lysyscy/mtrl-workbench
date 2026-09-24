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
⚠️ `Q2` 需要 `node`；**机器上没有就"跳过"并明说**（⛔ 不静默通过 —— 静默通过比不查更坏）。

## 自检（证明这两条**真的有区分力**）
`python tools/syntax_audit.py --selftest` —— 在临时目录里造两个"已知必错"的样本
（`f"说"话"` 的 `.py` ＋ 模板串里塞反引号的 `.html`）⇒ **必须都判红**；再各造一个"合法"样本 ⇒ **必须放行**。
（本仓的规矩：新判据要能证明"改坏了会红" —— 哨子也一样。）

跑法（工程根）：`backend\\.venv\\Scripts\\python.exe tools\\syntax_audit.py`
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

#: `Q1` 扫描范围（`tools/` 也扫 —— 那批一次性脚本 pytest **永远不会 import**，正是漏网的那片）
PY_ROOTS = [ROOT / "backend" / "app", ROOT / "backend" / "tests", ROOT / "tools"]

#: 排除目录（虚拟环境 / 缓存 / 产物：不是本仓手写的源码）
SKIP_DIRS = {".venv", "__pycache__", "node_modules", "artifacts", ".git", ".pytest_cache"}

# ⚠️ 2026-09-19（`P4`① 读取点收敛）：壳的件清单来自唯一出口 `shell_source`（顺序 = 浏览器执行顺序）。
#    `SHELL` 仍指 `index.html` 本体（存在性检查 / 单件模式用）。
from shell_source import SHELL_PARTS, SHELL_PATH  # noqa: E402  ← `P4`① 读取点收敛
SHELL = SHELL_PATH


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


def rule_q1(paths: list[Path] | None = None) -> list[str]:
    """`Q1` —— 每个 `.py` 必须能 `compile()`。返回红清单（每条含路径 + 行列 + 出错那几行）。"""
    bad: list[str] = []
    for p in (paths if paths is not None else iter_py()):
        src = p.read_text(encoding="utf-8", errors="replace")
        try:
            compile(src, str(p), "exec")
        except SyntaxError as exc:
            try:
                rel = p.relative_to(ROOT)
            except ValueError:
                rel = p
            lines = src.splitlines()
            i = (exc.lineno or 1) - 1
            ctx = " ｜ ".join(x.strip() for x in lines[max(0, i - 1): i + 1])
            bad.append(f"{rel}:{exc.lineno}: {exc.msg}｜{ctx[:150]}")
        except ValueError as exc:                       # 例如源码里混入 NUL
            bad.append(f"{p}: 读不出/编译不了：{exc}")
    return bad


def _extract_script(html: str) -> str:
    """取最后一个 `<script>…</script>` 的内容（壳的执行代码就在那里）。"""
    blocks = re.findall(r"<script>(.*?)</script>", html, re.S)
    return blocks[-1] if blocks else ""


def rule_q2(shell: Path | None = None) -> tuple[list[str], str]:
    """`Q2` —— 壳的**每一件**都必须过 `node --check`。

    ⚠️ 2026-09-19（`P4`① 读取点收敛）：壳已按 `web/shell/*.js` 拆件 ⇒ **只查 `index.html` 会静默漏掉接线层**
    （而那正是最容易写错、又最贵的一段）。⇒ 默认逐件查：`index.html` 取它的内联 `<script>`，
    外链件（`.js`）整文件就是脚本。传 `shell=` 时退化成"只查这一件"（`--selftest` 用）。

    返回 `(红清单, 说明)`；无 node ⇒ 红清单为空 ＋ 说明里讲明（⛔ 不是通过）。
    """
    node = shutil.which("node")
    if not node:
        return [], "⛔ 机器上没有 `node` ⇒ **跳过 Q2**（⛔ 不是通过 —— 请装 node 或人工跑 `node --check`）"
    parts = [shell] if shell is not None else SHELL_PARTS
    tmpdir = Path(tempfile.mkdtemp(prefix="syntax_audit_"))
    bad: list[str] = []
    try:
        for target in parts:
            if not target.exists():
                bad.append(f"找不到壳的某一件：{target}")
                continue
            text = target.read_text(encoding="utf-8")
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
    known = {p.resolve() for p in (parts if parts is not None else SHELL_PARTS)}
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
    print(" 语法哨 · syntax_audit —— 「能编译吗 / 能解析吗 / 壳目录干净吗」动手前一次查完")
    print("=" * 78)

    q1 = rule_q1()
    n_py = len(iter_py())
    print(f"\n─ Q1 · 每个 `.py` 必须能编译（扫了 {n_py} 个文件：`backend/app` · `backend/tests` · `tools`）")
    if q1:
        print(f"   ⛔ {len(q1)} 个文件编译不过（⚠️ 中文串里夹裸英文双引号是这一族的高发款 —— 内层一律用「」）：")
        for x in q1[:12]:
            print(f"     · {x}")
    else:
        print("   ✅ 全部通过")

    q2, note = rule_q2()
    print("\n─ Q2 · 壳 `<script>` 必须过 `node --check`（⚠️ 模板串里塞反引号是这一族的高发款）")
    if note:
        print(f"   {note}")
    elif q2:
        for x in q2:
            print(f"   ⛔ {x}")
    else:
        print("   ✅ 通过")

    q3 = rule_q3()
    print("\n─ Q3 · 壳目录里只许有壳的件（⛔ 备份/散件会让 grep 看见第二份源码）")
    if q3:
        for x in q3:
            print(f"   ⛔ {x}")
    else:
        print(f"   ✅ 通过（{len(SHELL_PARTS)} 件：{', '.join(p.name for p in SHELL_PARTS)}）")

    must = len(q1) + len(q2) + len(q3)
    print(f"\n结论：**必须修 {must}**" + ("（有红 ⇒ 非零退出）" if must else ""))
    return 0 if must == 0 else 1


def _selftest() -> int:
    """自检：两个"已知必错"样本必须判红、两个"合法"样本必须放行（证明哨子真有区分力）。"""
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

        bad_html = base / "bad.html"
        bad_html.write_text('<script>const a = `x（`API-05`）y`;</script>', encoding="utf-8")
        good_html = base / "good.html"
        good_html.write_text('<script>const a = `x（<span class="fc">API-05</span>）y`;</script>',
                             encoding="utf-8")
        q2, note = rule_q2(bad_html)
        q2_ok, _ = rule_q2(good_html)
        if note:
            print("自检 Q2：", note, "⇒ 无法自证（先装 node）")
            ok = False
        else:
            print("自检 Q2：坏样本判红 =", bool(q2), "· 好样本放行 =", not q2_ok)
            if q2:
                print("        ", q2[0][:130])
            ok &= bool(q2) and not q2_ok

        # Q3：临时目录里造一个"备份散件" ⇒ 必须判红；把它当作"壳件"传进去 ⇒ 必须放行
        stray = base / "stray.js.bak-sync"
        stray.write_text("// 09-21 的旧备份\n", encoding="utf-8")
        q3_bad = rule_q3(web=base, parts=[])
        q3_ok = rule_q3(web=base, parts=[bad_html, good_html, stray])
        print("自检 Q3：散件判红 =", bool(q3_bad), "· 壳件放行 =", not q3_ok)
        if q3_bad:
            print("        ", q3_bad[0][:110])
        ok &= bool(q3_bad) and not q3_ok

    print("\n自检结论：", "✅ 三条规则都能区分（坏的红、好的放行）" if ok else "⛔ 自检未通过")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(_selftest() if "--selftest" in sys.argv[1:] else main(sys.argv[1:]))
