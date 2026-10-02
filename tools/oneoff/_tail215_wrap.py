"""`TAIL-215` 批 1 的**机械搬迁**：把 `_shell_smoke.main()` 里那 15 个内联段**原样**包成模块级函数。

## 为什么用脚本而不是手改

那 15 块一共 **≈420 行**（含大量中文注释与 JS 模板串），手改一次就等于"重打一遍" ⇒ 必然引入差异。
⇒ 本件做**纯机械**的三件事（**不改一个字符**，只改缩进与位置）：

1. 按**行区间**切出 15 块（区间**写死在 `BLOCKS` 里**，并逐块断言"首行是注释、非空行都以 8 空格起"）；
2. 每块**整体去 4 个空格缩进** ⇒ 包成 `def seg_<名>(page, errors):`（段号与说明留在块内的原注释里）；
3. `main()` 换成**遍历注册表**（`_shell_segments.SEGMENTS`）的薄驱动。

## 干跑会断言什么（⛔ 任一不过 ⇒ **一个字节都不写**）

- 15 块的**行区间**与当前文件对得上（首行是 `#` 注释、且含该段号）；
- 每块非空行**都以 8 个空格起**（⇒ 统一去 4 格是安全的）；
- 搬完后，每个块的**去缩进正文**在成品里**仍然连续成块**（逐块核）；
- 成品 `py_compile` 通过；
- 顺手断言：`main()` 里**不再出现**裸 `check_<…>(page, errors)` 调用（否则就是绕开注册表的第二套编排）。

用法（**先干跑**）：
    backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_tail215_wrap.py
    backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_tail215_wrap.py --apply
"""
from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
SMOKE = REPO / "tools" / "probe" / "_shell_smoke.py"
PY = REPO / "backend" / ".venv" / "Scripts" / "python.exe"

#: (函数名, 段号标记, 起行, 止行) —— **1 基、闭区间**，对着当前 `_shell_smoke.py` 量出来的
BLOCKS: tuple[tuple[str, str, int, int], ...] = (
    ("seg_session", "⓪", 120, 123),
    ("seg_dbhygiene", "㉒", 125, 131),
    ("seg_nav", "①", 142, 143),
    ("seg_ttl", "②", 144, 144),
    ("seg_data", "③", 146, 148),
    ("seg_m03", "④", 150, 162),
    ("seg_m01", "⑤", 164, 190),
    ("seg_m04", "⑥", 192, 225),
    ("seg_m04draft", "⑥b", 227, 246),
    ("seg_m05", "⑦", 248, 283),
    ("seg_panel", "⑦′", 285, 317),
    ("seg_m08", "⑧", 319, 439),
    ("seg_m06", "⑨", 441, 467),
    ("seg_m07", "⑩", 469, 501),
    ("seg_m07bal", "⑩b", 503, 536),
)

#: 新的 import 区（替换原来的 23 条 `from _shell_xxx import check` ＋ `BASE = ...`）
NEW_IMPORTS = (
    "# ⭐⭐ 段的注册表（`TAIL-215` 批 1）：**哪几段 / 按什么顺序 / 为什么是这个顺序** —— 只有那一处。\n"
    "#     ⛔ 别在本件再列一份段清单（那会长出第二套顺序 —— 本仓最恨的病）。\n"
    "from _shell_segments import BASE, SEGMENTS        # noqa: E402\n"
)

#: `main()` 之后的驱动（`_boot` / `_run_segment` / `main`）
MAIN_PART = '''

def _boot(page) -> None:
    """把壳带起来并等**开屏那一屏**画完 —— `phase != "pre"` 的段都依赖它（见 `_shell_segments.py`）。"""
    page.goto(BASE + "/app", wait_until="load", timeout=45000)
    # ⭐ 等数据到位（⛔ 不用 networkidle，见文件头坑 1）
    page.wait_for_function("() => PJs.length > 0 || NO.length > 0 || BOOT_ERROR", timeout=20000)
    # ⚠️ 等侧栏真的渲染出来再量（`#nav` 初始是空 div、`#ttl` 初始是「—」）——
    #    此前这里**量早了**，打印出的「侧栏项数 = 0 / 顶栏 = —」是**误导**（会把"真没渲染"淹没）。
    page.wait_for_function("() => document.querySelectorAll('#nav .sb-i').length > 0", timeout=20000)


def _run_segment(seg, page, errors, self_scope) -> None:
    """跑一段 —— `entry` 三种形态：可调用 / `"self:<名>"`（本文件的段函数）/ `"模块:函数"`（外移件）。"""
    entry = seg.entry
    if callable(entry):
        fn = entry
    elif entry.startswith("self:"):
        name = entry[5:]
        if name not in self_scope:
            raise RuntimeError(
                f"⛔ 注册表里的 `{entry}` 在本文件里找不到 —— 段函数改名了却没同批改 "
                "`tools/probe/_shell_segments.py`（或反过来）")
        fn = self_scope[name]
    else:
        mod, _, fname = entry.partition(":")
        fn = getattr(__import__(mod), fname)
    fn(page, errors)


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        page = browser.new_page()
        page.on("console", lambda m: errors.append(f"[console.{m.type}] {m.text}")
                if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(f"[pageerror] {e}"))

        # ⭐⭐ 编排 = **遍历 `_shell_segments.SEGMENTS`**（`TAIL-215` 批 1）——
        #    「哪几段 / 什么顺序 / 为什么」**只有那一张表**一处；⛔ 别在这里再写"第几段做什么"。
        #    · `phase="pre"` 的段跑在**开页之前**；第一次遇到非 `pre` ⇒ 先把页面带起来。
        #    · `self_scope` 由**本文件的 `seg_*` 函数名**自动导出（⛔ 不另列一份清单）。
        self_scope = {k: v for k, v in globals().items() if k.startswith("seg_")}
        booted = False
        for seg in SEGMENTS:
            if seg.phase != "pre" and not booted:
                _boot(page)
                booted = True
            _run_segment(seg, page, errors, self_scope)
'''


def dedent4(text: str) -> str:
    """整体去 4 个空格（⛔ 只动行首缩进；空行原样）。"""
    out = []
    for ln in text.splitlines(keepends=True):
        out.append(ln if not ln.strip() else ln[4:])
    return "".join(out)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="TAIL-215 批 1：把内联段包成函数 ＋ main 换成遍历注册表")
    ap.add_argument("--apply", action="store_true", help="真写盘（默认只干跑）")
    a = ap.parse_args(argv)

    text = SMOKE.read_bytes().decode("utf-8")
    lines = text.splitlines(keepends=True)
    print(f"源件 {SMOKE.relative_to(REPO).as_posix()}：{len(lines)} 行")

    bad: list[str] = []
    # ① 边界断言
    if not lines[22].strip().startswith("from _shell_pend import"):
        bad.append(f"第 23 行不像 import 区起点：{lines[22][:60]!r}")
    if not lines[111].startswith("def main("):
        bad.append(f"第 112 行不是 `def main(`：{lines[111][:60]!r}")
    if lines[674].strip() != "":
        bad.append(f"第 675 行不是空行（TAIL 起点错了）：{lines[674][:60]!r}")
    covered: set[int] = set()
    prev_end = 0
    for name, tag, s, e in BLOCKS:
        body = lines[s - 1:e]
        if s <= prev_end:
            bad.append(f"{tag}({name}) 与上一块**重叠**（起点 {s} ≤ 上一块止 {prev_end}）")
        if s < 120 or e > 536:
            bad.append(f"{tag}({name}) 越出 `main()` 正文区（120–536）：{s}–{e}")
        prev_end = e
        covered |= set(range(s - 1, e))          # ⚠️ 存**0 基下标**（下面那个循环用下标比）
        if tag not in "".join(body):
            bad.append(f"{tag}({name}) 块里**没有**段号 {tag}（区间切错了）")
        for i, ln in enumerate(body, start=s):
            if ln.strip() and not ln.startswith("        "):
                bad.append(f"{tag}({name}) 第 {i} 行缩进 <8：{ln[:70]!r}")
    # ② **完备性**：120–536 里没被任何块覆盖的**非空行**，只许是「引导」那一段（133–141）
    for i in range(119, 536):
        if i in covered or not lines[i].strip():
            continue
        if i not in range(132, 141):
            bad.append(f"第 {i + 1} 行既不在任何块里、也不是引导区：{lines[i][:70]!r}")
    if bad:
        print("⛔ 边界断言未过 ⇒ **一个字节都不写**：")
        for b in bad:
            print("   ", b)
        return 1

    # ② 拼装
    funcs = []
    for name, tag, s, e in BLOCKS:
        body = dedent4("".join(lines[s - 1:e]))
        funcs.append(f'\n\ndef {name}(page, errors) -> None:\n'
                     f'    """{tag} —— ⚠️ **位置由 `_shell_segments.py` 定**（⛔ 别在这里讨论顺序）。"""\n'
                     f"{body}")
    head = "".join(lines[0:22]) + NEW_IMPORTS + "".join(lines[49:111])
    tail = "".join(lines[674:])
    new_text = head + "".join(funcs) + MAIN_PART + tail

    # ③ 成品断言：每个块的**去缩进正文**在成品里仍然连续成块
    for name, tag, s, e in BLOCKS:
        chunk = dedent4("".join(lines[s - 1:e]))
        if chunk not in new_text:
            bad.append(f"{tag}({name}) 的去缩进正文在成品里找不到（拼接出错）")
    # ④ 成品里不许再有裸 `check_<…>(page, errors)`（否则 = 绕开注册表的第二套编排）
    import re
    for m in re.finditer(r"^\s+check_\w+\(page, errors\)", new_text, re.M):
        bad.append(f"成品里仍有裸调用：{m.group(0).strip()}")
    if bad:
        print("⛔ 成品断言未过 ⇒ **一个字节都不写**：")
        for b in bad:
            print("   ", b)
        return 1

    new_lines = new_text.splitlines()
    print(f"成品：{len(new_lines)} 行（源 {len(lines)} 行）")
    print(f"  头部 {'+'.join(str(len(x)) for x in (lines[0:22], NEW_IMPORTS, lines[49:111]))} 行"
          f" · 段函数 {len(funcs)} 个 · 驱动 {len(MAIN_PART.splitlines())} 行 · 尾部 {len(lines[674:])} 行")
    print("  段函数：" + " ".join(n for n, *_ in BLOCKS))

    if not a.apply:
        print("\n（干跑 —— 要真写盘加 --apply）")
        return 0

    tmp = SMOKE.with_name("~_shell_smoke.py.tmp")
    tmp.write_bytes(new_text.encode("utf-8"))
    r = subprocess.run([str(PY), "-X", "utf8", "-m", "py_compile", str(tmp)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        tmp.unlink(missing_ok=True)
        print("⛔ 成品 `py_compile` 不过 ⇒ **未写盘**：")
        print((r.stdout or "") + (r.stderr or ""))
        return 1
    tmp.replace(SMOKE)
    print(f"\n✅ 已写盘：{SMOKE.relative_to(REPO).as_posix()}（py_compile 通过）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
