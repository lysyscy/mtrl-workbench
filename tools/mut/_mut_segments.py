#!/usr/bin/env python
"""真机自检**段注册表**的反向灵敏度（`TAIL-215` 批 1 ＋ 批 2）—— 证明对应守卫**真的有牙**。

守什么（`backend/tests/test_shell_segments.py`）：段号不重复 · 相位成块 ·
`last=True` 恰一条且在表末 · `after=` 指向的段真在表里且确实在前 · `entry` 都解析得到真函数 ·
编排件真遍历注册表 · 编排件里不许有绕过注册表的**裸调用**。

**为什么必需**：那 8 条里，**现在全是绿的** ⇒ 「它们到底会不会红」**没人知道**。
本仓规矩（`_mut_vs.py` 文件头原话）：**新做的机制若不证明「改坏了会被抓住」，它跟没做一样**。

**保留的靶**（各改一处 ⇒ 跑同一支判据 ⇒ **必须那一条红** ⇒ 立刻按 bytes 复原）：

| 靶 | 改哪 | 该红的是 |
|---|---|---|
| `M1` | `_shell_segments.py`：㉞ 那条去掉 `last=True` | 「恰好一条 `last=True`」 |
| `M3` | 同件：⑥b 的 `after=("⑥",)` 改成**幽灵段号** `"㊿"` | 「`after` 指向的段必须在表里」 |
| `M4` | 同件：`"_shell_m11cost:check"` 里的函数名**打错** | 「`entry` 都解析得到真函数」 |
| `M5` | 同件：⓪ 的相位 `"pre"` 改成 `"body"` | 「相位必须成块」 |
| `M6` | `_shell_smoke.py`：编排循环后塞一行**裸调用** | 「编排件里不许再有裸调用」 |
| `M7` | 同件：把一条 `模块:check` 改回 `"self:…"` | ⭐「段代码不许放回编排件」（批 2） |

⚠️ 真机件的纪律照旧：跑完**必复原**（`finally`）＋ 收尾 **MD5 校验**（⛔ 不给盘上留坏态）。
⚠️ 本件**不需要壳在跑**（判据是离线的）；本件直接写正式靶，必须先准备隔离副本，当前不可作为普通执行入口。

⚠️⚠️ **2026-10-06（`TAIL-233`）修：靶件全是 CRLF，而 `TARGETS` 的锚点是带 `\n` 的源码字面**
    ⇒ 含换行的锚点**全部打空**、件死在 `M2` 那条「锚点命中 0 次 ⇒ 锚点漂了」上
    ⇒ 症状读起来像"锚点漂了"，真因却是**行尾**（**7 个靶里 6 个含换行**；实测 `_shell_segments.py` 140/0
    · `_shell_smoke.py` 97/0）。⇒ 比对前**行尾归一**（`_norm`）、写回**按该件原本的行尾**（`_fit`）
    —— 后半句是必须的：⛔ 否则一次变异就把 CRLF 件悄悄改成 LF ⇒ 收尾 MD5 复原校验背黑锅。
    ⭐ 判「锚点漂了」还是「行尾打空」，量一下就分得开：**`read_text()` 会做通用换行转换（看起来在），
    而 `decode()` 不会**（异件走的是后者）⇒ 两者不一致就说明是行尾。

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
    ("M3", "⑦′ 的 `after` 指向幽灵段号", SEG,
     'after=("⑦",), why="同上：接着 ⑦ 那一屏真点 ⇒ 相邻且保序"',
     'after=("㊿",), why="同上：接着 ⑦ 那一屏真点 ⇒ 相邻且保序"',
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


def _norm(b: bytes) -> str:
    """靶件字节 → 文本，**行尾归一为 LF**（比对锚点用；见文件头 2026-10-06 那段）。

    ⚠️ `_mut_shellapi.py` 里有**逐字相同**的一份。**⛔ 别在本件改一份、忘了另一份** ——
    两处任一漂了，那一支就会重新变成"一件都没验过"（且症状是"锚点没命中"，极像别的问题）。
    """
    return b.decode("utf-8").replace("\r\n", "\n")


def _fit(text: str, orig: bytes) -> bytes:
    """把归一后的文本写回**该件原本的行尾风格**（⛔ 别把 CRLF 件写成 LF ⇒ 复原校验会背黑锅）。"""
    b = text.encode("utf-8")
    return b.replace(b"\n", b"\r\n") if b"\r\n" in orig else b


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
            src = _norm(originals[path])                     # ⭐ 归一后再比对（靶件是 CRLF）
            if src.count(old) != 1:
                fail.append(f"{code} 锚点命中 {src.count(old)} 次（期望 1）⇒ **锚点漂了**，不是判据没牙")
                continue
            path.write_bytes(_fit(src.replace(old, new), originals[path]))
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
