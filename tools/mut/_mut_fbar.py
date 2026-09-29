"""反向灵敏度（`FBAR` 筛选栏件 —— `TAIL-64` **P4** 的**统一筛选栏外壳出口**）——
证明「筛选栏外壳走一个出口」那条判据**真有区分力**。

⚠️ 本件为什么必需：
- `TAIL-64` P4-a（2026-09-30）把一根筛选栏的**外壳**（`<div class="fbar …">…</div>`）抽进 `FBAR`
  之后，页面**渲染字节一字不变** ⇒ 肉眼、`U1`（两侧同批同句 ⇒ "一致"）、真机**都看不出它有没有被换掉**；
  只有"把它改坏 ⇒ 判据必须红"这一条能证明那处**真的委托出去了、而且内核真把控件拼进了栏里**。
- ⭐ 这正是本仓的老课：**"判据存在" ≠ "判据在管那件事"** —— 没有反向灵敏度的判据是**假绿**候选。

四靶（改完**立刻按 bytes 复原** ＋ MD5 校验）：
- `M1` **去掉委托**：把 `V.m01` 那一处的 `FBAR({body:` 改成 `FBARBROKEN({body:`
  （合法标识符 ⇒ **不触发**语法错，只会让"本页筛选栏没走统一出口"那一条红）。
- `M2` **掏空内核**：把 `FBAR` 体内的 `'>'+body+'</div>'` 改成 `'>'+''+'</div>'`
  ⇒ "内核没把 body 拼进栏内"必须红（⚠️ 靶在 `shell/proj.js` —— `FBAR` 住在那儿，⛔ 别假设在 `index.html`）。
- ⭐ `P4-b`（2026-09-30）补的两靶（**全站铺开之后那半条判据**得有牙）：
  · `M3` **内核不再出 `fbar` 那层**（把类名 `fbar` 改成 `fbX`）⇒ "内核不再渲染 `fbar` 那层"必须红；
  · `M4` **又裸写一层外壳**（在某调用点前面插一个 `<div class="fbar">`）⇒ "全站还有 N 处裸外壳"必须红。
- ⚠️ **`M1`/`M4` 的靶必须自带页内上下文**：`P4-b` 之后 `${FBAR({body:` 在 `index.html` 里出现 **11 次**
  ⇒ 光用这一小段**不是唯一**（脚本会打印"未验证"）。现取 `m01` 那一栏的首个子件当上下文。

⚠️ 判据 = **目标测试件 rc≠0**（不是整支尺子）＋ **那条断言的原话出现在输出里**（⛔ 别只看 rc：别的用例红
也会让 rc≠0）。
⚠️ 子集 pytest **必须**把 `ACC_RESULTS_PATH` 指到 `artifacts/_mut_acc_results.json`（`MEMORY-细则 §十七`）
—— ⛔ 否则把**权威四态**冲成残档、`T4` 报红；⚠️ 本件跑完**必须重跑全套**写回（脚本末尾会提醒）。

用法：python tools/mut/_mut_fbar.py
"""

from __future__ import annotations

import hashlib
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SHELL = ROOT / "backend" / "app" / "web" / "index.html"
#: ⭐ P4-a 的教训同款：**别假设源码在哪个件里** —— `FBAR` 的口径件住在 `shell/proj.js`
#:   （同 `_mut_tbl.py` 的 `M2` 那次"哑靶"：件 2026-09-28 拆出去后，靶串一次都命中不到）。
PROJ = ROOT / "backend" / "app" / "web" / "shell" / "proj.js"
PY = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"
TARGETS: tuple[str, ...] = ("tests/test_ux_pages.py",)   #: ⭐ P4-a 那条判据所在件
PARTIAL_ACC = ROOT / "artifacts" / "_mut_acc_results.json"


def _b(s: str) -> bytes:
    """⚠️ `bytes` 字面量**只能放 ASCII** ⇒ 含中文的靶串必须这样编（踩过：`SyntaxError`）。"""
    return s.encode("utf-8")


def _bml(s: str) -> bytes:
    """**多行**靶串：⚠️ 壳件是 **CRLF** ⇒ 多行靶串必须把 `\\n` 先换成 `\\r\\n`（否则一次都命中不到、
    而脚本只会打印"未验证" —— 那是**哑靶**，不是假绿但也没人证过）。"""
    return s.replace("\n", "\r\n").encode("utf-8")


#: ⭐ `P4-b` 之后 `${FBAR({body:` 在 `index.html` 里出现 **11 次** ⇒ 靶**必须自带页内上下文**才唯一。
#:   ⚠️ 上下文要**够长**：第一版取到「项目状态（默认在建）」为止 ⇒ 命中 **2 次**（`m01` 的 `fPjStatus`
#:   与 `m07` 提取表的 `fExtStatus` 那两栏**首个子件同名**）⇒ 再往后带到 `id="fPjStatus"` 才唯一。
M01_HEAD = '${FBAR({body:`\n      <div class="fi"><label>项目状态（默认在建）</label><select class="inp" id="fPjStatus"'

#: `(打哪个文件, 说明, 原文, 改坏成, 期望在输出里出现的断言原话)` —— 靶串都是**单行片段** ⇒ 不必做行尾归一
CASES: list[tuple[pathlib.Path, str, bytes, bytes, str]] = [
    (SHELL, "M1 去掉委托（`m01` 筛选栏外壳不再走 `FBAR`）", _bml(M01_HEAD),
     _bml(M01_HEAD.replace("FBAR({body:", "FBARBROKEN({body:", 1)), "筛选栏外壳没走统一出口"),
    # ⚠️ `M2` 的靶在 `shell/proj.js`（`FBAR` 内核所在件）
    (PROJ, "M2 掏空内核（`FBAR` 不再把 body 拼进栏内）", _b("+'>'+body+'</div>'"),
     _b("+'>'+''+'</div>'"), "没有把 `body` 拼进栏内"),
    # ⭐ 2026-09-30（`TAIL-64` P4-b）：全站铺开之后，**"漏网的裸外壳"** 这条得单独有牙 ——
    #   ① `M3` 把内核那个类名改掉（外壳整层没了）；② `M4` 在某个调用点前面**又裸写一层**外壳。
    (PROJ, "M3 内核不再出 `fbar` 那层（类名改掉）", _b("'<div class=\"fbar'+(cls?"),
     _b("'<div class=\"fbX'+(cls?"), "内核不再渲染 `fbar` 那层"),
    #: ⚠️ `M4` 的插入物是**一段合法的模板表达式**（`${''}`）⇒ 不触发语法错，只会让"全站还有裸外壳"那一条红
    (SHELL, "M4 又裸写一层外壳（调用点前面插一个 `<div class=\"fbar\">`）", _bml(M01_HEAD),
     _bml('${\'\'}<div class="fbar">' + M01_HEAD), "处筛选栏是**裸写**的外壳"),
]


def run_target() -> tuple[int, str]:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1",
           # ⚠️ 子集跑 ⇒ 四态落**残档**（⛔ 别写权威档 `acc_results.json`）
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
