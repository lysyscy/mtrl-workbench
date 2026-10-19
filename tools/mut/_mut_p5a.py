"""反向灵敏度（**表级虚拟滚动** —— `TAIL-64` `P5-a` ＋ `P5-c`）—— 证明那几条**结构性**判据真有区分力。

⚠️ 本件为什么必需：`P5-a` 把虚拟滚动从"整页"下沉到"**那张表自己**"，而它**不产生任何渲染差异**
   （窗口大小、行高、合计行位置都一样）⇒ 人眼 / 真机 / `U1` 都看不出"某一处到底接没接上"。
   ⚠️ 尤其第一条：把**滚动监听的挂载点**写错位置那次，**离线判据全绿、`node --check` 全绿**，
      靠真机才发现（滚动条能拖、内容一动不动）⇒ 只有"改坏了必须红"能证明它。

七靶（改完**立刻按 bytes 复原** ＋ MD5 校验）：
- `M1` **内核不拼标记**：`TBL` 里 `'<tbody data-vs="'` 改成 `'<tbody data-vz="'`（合法字面 ⇒ 不触发语法错）
  ⇒ "认领不到任何表"必须红。
- `M2` **摘掉挂载点**：`view.js` 里 `vsBindScroll();` 那一次调用改成 `void 0;` ⇒ "表级那条路没人挂监听"必须红。
- `M3` **摘掉分派**：`view.js` 里 `vsTableHits(html)` 换成 `[]` ⇒ "表级那条路永远不会接管"必须红。
- `M4` **摘掉清空**（`P5-c`）：`startVirtual` 里那句 `VS_TS=[];` 改成 `void 0;`
  ⇒ "分派前先清空"必须红（摘了 ⇒ 上一页认领过的表留到下页，滚动时认错对象、**不报错**）。
- `M5` **不写回行**（`P5-c`）：那张**没有 `.tw`** 的表本该"行原样写回"，把写回那句抹掉
  ⇒ "只剩一个垫高行"必须红（真机表现 = 一张**看起来是空的**表）。
- `M6` **认领会认错表**（`P5-c`）：把按 `data-vs-i` **对位**改回按 `data-vs` 的**值**查
  ⇒ "不该按值查"必须红（一页多表同键时窗口会画到别人那张表上）。
- `M7` **滚动帧退回整页写**（`P5-c` / 红线②）：把"只换 `tbody` 的行"改成 `$('#view').innerHTML=…`
  ⇒ 红线② 必须红（那正是当年**两次用户报障**的病根：打断滚轮手势、`scrollTop` 归零）。

⚠️ 判据 = **目标测试件 rc≠0** ＋ **那条断言的原话出现在输出里**（⛔ 别只看 rc）。
⚠️ 子集 pytest 用 `ACC_RESULTS_PATH` 指到 `artifacts/_mut_acc_results.json`（⭐ 别把权威四态冲成残档）。

用法：python tools/mut/_mut_p5a.py
"""

from __future__ import annotations

from pathlib import Path as _WorkspacePath
import sys as _workspace_sys
_workspace_sys.path.insert(0, str(_WorkspacePath(__file__).resolve().parents[2] / 'tools/audit'))
from workspace_paths import output as _run_output, output_dir as _run_dir

import hashlib
import os
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]
SHELL = ROOT / "backend" / "app" / "web" / "index.html"
#: ⭐ `P5-a` 的两处源码**各有其件**：滚动那套在 `shell/view.js`，`TBL` 内核在 `shell/proj.js`
#: （同 `M2` 的哑靶教训：**别假设源码在 `index.html`**）。
VIEW = ROOT / "backend" / "app" / "web" / "shell" / "view.js"
PROJ = ROOT / "backend" / "app" / "web" / "shell" / "proj.js"
PY = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"
TARGETS: tuple[str, ...] = ("tests/test_shell_render.py",)   #: ⭐ 三条结构判据都在这一件里
PARTIAL_ACC = ROOT / _run_dir() / "_mut_acc_results.json"


def _b(s: str) -> bytes:
    """⚠️ `bytes` 字面量**只能放 ASCII** ⇒ 含中文的靶串必须这样编（踩过：`SyntaxError`）。"""
    return s.encode("utf-8")


CASES: list[tuple[pathlib.Path, str, bytes, bytes, str]] = [
    (PROJ, "M1 内核不拼标记（`data-vs` 改名 ⇒ 认领不到任何表）",
     _b("'<tbody data-vs=\"'+(key||'1')+'\">'"), _b("'<tbody data-vz=\"'+(key||'1')+'\">'"),
     "认领不到任何表"),
    (VIEW, "M2 摘掉挂载点（表级那条路没人挂滚动监听）",
     _b("vsBindScroll();"), _b("void 0;"),
     "没有统一挂载点"),
    #: ⚠️ 靶要取**调用那一句**（`=vsTableHits(html)`）—— 光写 `vsTableHits(html)` 会**同时命中定义**（哑靶）。
    (VIEW, "M3 摘掉分派（表级那条路永远不会接管）",
     _b("const ts=vsTableHits(html);"), _b("const ts=[];"),
     "永远不会接管"),
    #: ⚠️ `VS_TS=[];` 在壳里出现**两次**（`let VS_TS=[];` 声明 ＋ `startVirtual` 里那句）⇒ 靶带上**行首缩进**
    #:    才恰好命中一次（删了声明那个 `let` 就不是同一件事了）。
    (VIEW, "M4 摘掉清空（上一页认领过的表会留到下页）",
     _b("  VS_TS=[];"), _b("  void 0;"),
     "少了这一步"),
    (VIEW, "M5 没 `.tw` 的表不写回行（那张表看起来会是空的）",
     _b("if(inst.tb) inst.tb.innerHTML=inst.pre+inst.rows.join('')+inst.post;"),
     _b("/* 变异M5：不写回 */"),
     "只剩一个垫高行"),
    (VIEW, "M6 认领按 `data-vs` 的值查（一页多表同键 ⇒ 画到别人表上）",
     _b("querySelector('tbody[data-vs-i=\"'+inst.hit+'\"]')"),
     _b("querySelector('tbody[data-vs=\"'+inst.key+'\"]')"),
     "认领表体不是按"),
    (VIEW, "M7 滚动帧退回整页写（红线②：打断滚轮手势、`scrollTop` 归零）",
     _b("tb.innerHTML = SP(topH0) + winRows.join('') + SP(botH0);"),
     _b("$('#view').innerHTML = inst.pre + SP(topH0) + winRows.join('') + SP(botH0) + inst.post;"),
     "红线②破了"),
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
