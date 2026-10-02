#!/usr/bin/env python
"""真机自检**段注册表**的反向灵敏度（`TAIL-215` 批 1 ＋ 批 2）—— 证明那 9 条守卫**真的有牙**。

守什么（`backend/tests/test_shell_segments.py`）：段的清单/次序（金标）· 段号不重复 · 相位成块 ·
`last=True` 恰一条且在表末 · `after=` 指向的段真在表里且确实在前 · `entry` 都解析得到真函数 ·
编排件真遍历注册表 · 编排件里不许有绕过注册表的**裸调用**。

**为什么必需**：那 8 条里，**现在全是绿的** ⇒ 「它们到底会不会红」**没人知道**。
本仓规矩（`_mut_vs.py` 文件头原话）：**新做的机制若不证明「改坏了会被抓住」，它跟没做一样**。

**七个靶**（各改一处 ⇒ 跑同一支判据 ⇒ **必须那一条红** ⇒ 立刻按 bytes 复原）：

| 靶 | 改哪 | 该红的是 |
|---|---|---|
| `M1` | `_shell_segments.py`：㉞ 那条去掉 `last=True` | 「恰好一条 `last=True`」 |
| `M2` | 同件：**删掉 ⑧ 那条** | 「金标清单」（少了哪一段要有人看见） |
| `M3` | 同件：⑥b 的 `after=("⑥",)` 改成**幽灵段号** `"㊿"` | 「`after` 指向的段必须在表里」 |
| `M4` | 同件：`"_shell_m11cost:check"` 里的函数名**打错** | 「`entry` 都解析得到真函数」 |
| `M5` | 同件：⓪ 的相位 `"pre"` 改成 `"body"` | 「相位必须成块」 |
| `M6` | `_shell_smoke.py`：编排循环后塞一行**裸调用** | 「编排件里不许再有裸调用」 |
| `M7` | 同件：把一条 `模块:check` 改回 `"self:…"` | ⭐「段代码不许放回编排件」（批 2） |

⚠️ 真机件的纪律照旧：跑完**必复原**（`finally`）＋ 收尾 **MD5 校验**（⛔ 不给盘上留坏态）。
⚠️ 本件**不需要壳在跑**（判据是离线的）⇒ 可以进闸门关键集（`tools/oneoff/_run_muts.py`）。

用法：`backend\\.venv\\Scripts\\python.exe -X utf8 tools\\mut\\_mut_segments.py`
"""
from __future__ import annotations

import hashlib
import pathlib
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(__file__).resolve().parents[2]
PY = str(ROOT / "backend" / ".venv" / "Scripts" / "python.exe")
SEG = ROOT / "tools" / "probe" / "_shell_segments.py"
SMOKE = ROOT / "tools" / "probe" / "_shell_smoke.py"
TEST = "tests/test_shell_segments.py"

#: (代号, 说明, 目标件, 原串, 改后串, **该红的那条判据名**)
TARGETS: tuple[tuple[str, str, pathlib.Path, str, str, str], ...] = (
    ("M1", "㉞ 去掉 `last=True`", SEG,
     '"全页", net=True, last=True,', '"全页", net=True,',
     "test_最后一段恰好一条且在表末"),
    ("M2", "删掉 ⑧ 那一整条", SEG,
     '    Seg("⑧", "m08 库存单据：全量行数 == 后端 ＋ **真滚轮**滚得动", "body", "_shell_m08:check", "m08"),\n',
     "",
     "test_段清单与次序必须等于金标"),
    ("M3", "⑥b 的 `after` 指向幽灵段号", SEG,
     'after=("⑥",), why="接着 ⑥ 那一屏真点（同一页的下一步）⇒ 两段**必须相邻且保序**"',
     'after=("㊿",), why="接着 ⑥ 那一屏真点（同一页的下一步）⇒ 两段**必须相邻且保序**"',
     "test_after_指向的段必须在表里且排在本条之前"),
    ("M4", "`模块:函数` 里的函数名打错（`entry` 解析不到）", SEG,
     '"_shell_m11cost:check"', '"_shell_m11cost:check_typo"',
     "test_每条entry都解析得到真函数"),
    ("M5", "⓪ 的相位改成 `body`（相位不再成块）", SEG,
     'Seg("⓪", "播种会话票（以在用管理员身份）", "pre",',
     'Seg("⓪", "播种会话票（以在用管理员身份）", "body",',
     "test_相位必须成块pre_boot_body"),
    ("M6", "编排件里塞一行绕过注册表的裸调用", SMOKE,
     "            _run_segment(seg, page, errors)",
     "            _run_segment(seg, page, errors)\n            check_m11(page, errors)",
     "test_编排件里不许再有裸调用"),
    ("M7", "注册表里又出现 `self:`（段代码塞回编排件）", SEG,
     '"_shell_m03:check"', '"self:seg_m03"',
     "test_段代码不许放回编排件"),
)


def md5(p: pathlib.Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def run_test() -> tuple[int, str]:
    r = subprocess.run([PY, "-X", "utf8", "-m", "pytest", TEST, "-q", "--no-header"],
                       cwd=str(ROOT / "backend"), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main() -> int:
    originals = {p: p.read_bytes() for p in {SEG, SMOKE}}
    md5s = {p: md5(p) for p in originals}

    print("基线（未改坏）：")
    rc0, out0 = run_test()
    print(f"  判据 rc={rc0}（期望 0）")
    if rc0 != 0:
        print("  ⛔ 基线就红 ⇒ 先清红再来跑本件")
        print(out0[-800:])
        return 1

    fail: list[str] = []
    try:
        for code, what, path, old, new, needle in TARGETS:
            src = originals[path].decode("utf-8")
            if src.count(old) != 1:
                fail.append(f"{code} 锚点命中 {src.count(old)} 次（期望 1）⇒ **锚点漂了**，不是判据没牙")
                continue
            path.write_bytes(src.replace(old, new).encode("utf-8"))
            try:
                rc, out = run_test()
                hit = needle in out
                print(f"  {'✅' if (rc != 0 and hit) else '⛔'} {code} {what:34s} rc={rc} "
                      f"{'（该红的那条出现了）' if hit else '（⚠️ 没看到 ' + needle + '）'}")
                if rc == 0:
                    fail.append(f"{code} 改坏后**判据没红**（{needle}）⇒ 这条守卫是**假绿**")
                elif not hit:
                    fail.append(f"{code} 判据红了、但**不是那一条**（没看到 {needle}）⇒ 靶没打在点上")
            finally:
                path.write_bytes(originals[path])
    finally:
        for p, b in originals.items():
            p.write_bytes(b)

    print("复原校验…")
    for p, want in md5s.items():
        got = md5(p)
        ok = got == want
        print(f"  {'✅' if ok else '⛔'} {p.relative_to(ROOT).as_posix()} MD5 {got[:12]}…")
        if not ok:
            fail.append(f"{p.name} **没复原**（MD5 {want[:12]} → {got[:12]}）")

    rc, _ = run_test()
    if rc != 0:
        fail.append("复原后判据仍红 ⇒ 盘上留了坏态")

    if fail:
        print("❌ " + "；".join(fail))
        return 1
    print(f"✅ 有区分力：{len(TARGETS)} 个靶**全部必红**、且红的正是那一条；改坏件已逐字节复原")
    return 0


if __name__ == "__main__":
    sys.exit(main())
