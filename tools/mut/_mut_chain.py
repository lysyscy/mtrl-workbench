"""反向灵敏度（链路对账）—— 证明 `chain_audit` 的每一把尺子**真的有区分力**。

做法：逐次把**源代码/真源/认领表**故意改坏一处 ⇒ 断言**对应的那条红确实出现/消失** ⇒ 逐字节复原（MD5）。
⚠️ 本尺子**本来就红** ⇒ 不能只看 `rc`：必须断言"**那条具体的红**"。

    python tools/mut/_mut_chain.py

⚠️⚠️ **2026-10-06（`TAIL-233`）修：子进程的输出编码 —— 症状与当初记的**不一样**，差点判错方向**。
    当初记的是「抛 `UnicodeDecodeError`」，实测跑出来是 **`RuntimeError: chain_audit --json 没有输出（rc=0）`**：
    ⭐ 因为 `subprocess.run(text=True, encoding="utf-8")` 的解码发生在**内部那个读 stdout 的线程**
    （`threading.py` 的 `_readerthread`）里 ⇒ **`UnicodeDecodeError` 不会从 `run()` 抛出来**（被线程吞了）
    ⇒ `run()` 正常返回、而 `p.stdout` 是**空串** ⇒ 表象是「**子进程没输出**」。
    ⛔ 这个坑最坏的地方：**看起来像"尺子/环境坏了"**，其实只是父件解错了码。
    实测：子进程不加 `-X utf8` 时管道下输出的是 **cp936**（2087 字节 · utf-8 解不了 · gbk 能解）。
    ⇒ 正解三件一起：`-X utf8` ＋ 环境 `PYTHONIOENCODING=utf-8` ＋ `errors="replace"`（**当保险**）。
    ⛔ **只加 `errors="replace"` 不够** —— 实测那样能拿到 1906 字符、也能 `json.loads` 过，
    但里面是**替换字符** ⇒ 属"看着能用、其实内容已坏"（本仓：`Invalid control character` 那族的同亲）。
"""

from __future__ import annotations

import atexit
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PY = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"
EXP = ROOT / "tools" / "chain_expected.txt"
SRC = ROOT / "tools" / "chain_sources.txt"


def run() -> dict:
    # ⚠️ 2026-09-23（`TAIL-58` 分目录的漏网件）：尺子已搬进 `tools/audit/` ⇒ 旧路径会让
    #    `chain_audit` 起不来、`stdout` 为空 ⇒ `json.loads` 抛异常 ⇒ **本脚本中途崩掉**。
    # ⚠️⚠️ 2026-10-06（`TAIL-233`）：`-X utf8` ＋ `PYTHONIOENCODING` **不是锦上添花，是必需** ——
    #    少了它们，子进程管道输出是 cp936，而解码发生在**内部读线程**里 ⇒ 异常被吞、
    #    `p.stdout` 变空串 ⇒ 报成「没有输出」（⚠️ 看着像尺子坏了）；`errors="replace"` 只当**保险**。
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
    p = subprocess.run([str(PY), "-X", "utf8", str(ROOT / "tools" / "audit" / "chain_audit.py"), "--json"],
                       cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env)
    if not (p.stdout or "").strip():
        raise RuntimeError(f"chain_audit --json 没有输出（rc={p.returncode}）：{(p.stderr or '')[:200]}")
    return json.loads(p.stdout)


def md5(b: bytes) -> str:
    return hashlib.md5(b).hexdigest()


def main() -> int:
    exp0, src0 = EXP.read_bytes(), SRC.read_bytes()
    h_exp, h_src = md5(exp0), md5(src0)
    hits = 0

    # ⚠️⚠️ **崩溃也要复原**（2026-09-23 实测踩到）：本脚本变异的是**被 git 管的**两张真源表
    #    （`chain_expected.txt` / `chain_sources.txt`）；原先只在**每条正常跑完**时才 `write_bytes` 复原
    #    ⇒ 一旦中途抛异常（例如 `run()` 抛错），**变异就留在工作区**（实测：认领表里留了
    #    `ipp.py::send_pdf_TYPO` ⇒ `chain_audit` 报红，而脚本自己已经崩了、什么都没说）。
    #    ⇒ 用 `atexit` 兜底：正常 / 异常 / `sys.exit` 三条路都会复原（幂等，重复写无害）。
    def _restore() -> None:
        EXP.write_bytes(exp0)
        SRC.write_bytes(src0)

    atexit.register(_restore)

    def expect(name: str, needle: str, *, must: bool = True) -> None:
        nonlocal hits
        d = run()
        found = any(needle in r for r in d["red"])
        good = found is must
        print(f"  {'✅' if good else '❌'} {name} —— 期望{'出现' if must else '消失'}「{needle[:34]}」"
              f" ⇒ {'命中' if found else '未见'}")
        hits += 1 if good else 0
        EXP.write_bytes(exp0)
        SRC.write_bytes(src0)

    # M1 · C3 落点名字写错 ⇒ 报「落点名字在文件里找不到」
    # ⚠️ 2026-10-06（`TAIL-233`）：本件的 `write_text` 一律带 `newline=""` ——
    #    两张真源表都是 **CRLF**（实测 229/0 · 37/0），而 `write_text` 默认把 `\n` 译成 `os.linesep`
    #    ⇒ 文本里原有的 `\r\n` 会被写成 **`\r\r\n`**。断言照样过（`splitlines` 不在意），
    #    **但那是"碰巧没露出来"** ⇒ 按本仓规矩（改已有文件用 `newline=""`）一并修。
    #    ⛔ 且 M5 那处连拼都不能用 `"\n"`（`splitlines()` 会把行尾吃掉）—— 见 M5 处的 `nl`。
    EXP.write_text(exp0.decode("utf-8").replace(
        "print/ipp.py::send_pdf", "print/ipp.py::send_pdf_TYPO"), encoding="utf-8", newline="")
    expect("M1 落点名字写错", "落点名字在文件里找不到")

    # M2 · C2 文档锚改一字 ⇒ 报「文档锚在真源里找不到」
    EXP.write_text(exp0.decode("utf-8").replace(
        "勾选通知书 → 点「批量打印」", "勾选通知书 → 点「批量打印X」"), encoding="utf-8", newline="")
    expect("M2 文档锚改一字", "文档锚在真源里找不到")

    # M3 · C1 链路代码未注册 ⇒ 报「没在 chain_sources.txt 注册」
    SRC.write_text(src0.decode("utf-8").replace(
        "P5|批量打印与只导出 PDF", "# P5|批量打印与只导出 PDF"), encoding="utf-8", newline="")
    expect("M3 链路代码未注册", "没在 chain_sources.txt 注册")

    # M4 · ⭐ C5「状态」这把尺子（**六把里唯一从没被验过的那把**：M1=C3 落点 · M2=C2 文档锚
    #      · M3=C1 注册 · M5=C6 覆盖哨 —— C4 判据、C5 状态都没人验）
    # ⚠️⚠️ 2026-10-06（`TAIL-233`）：**本条原先是恒真的空动作** —— 它 replace 的那句
    #   「指定项目不在统计范围 · 认领缺口」**命中 0 次**（那条缺口早被修掉了），
    #   判据又查两串**不在 `red` 里**的文本（`red` 恒为 0）⇒ `not any(...)` 恒真 ⇒ 报 ✅ 也是假的。
    #   ⭐ 本仓**又一例「哑靶」**（同类前几例见 `IDE-细节.md` §十一：靶落在注释里 / 靶带着旧尾巴 ⇒ 静默 SKIP /
    #   复原没走 `finally`）⇒ 教训升级：**判据写成
    #   `not any(...)` 时必须同时证明"红造得出来"** —— 只断言"坏事没发生"的自测 = 没有守卫的自测。
    # ⇒ 改成两段式：**造红**（已接 ⇒ 接线缺 ⇒ C5 必报）**＋ 销红**（改回已接 ⇒ 那条红必须消失）。
    #   靶**动态取**第一行 P1 认领行（⛔ 不写死整行：真源一改就漂，本仓老课）。
    base_red = len(run()["red"])
    p1_src = next(l for l in exp0.decode("utf-8").splitlines()
                  if l.startswith("P1|") and l.endswith("|已接"))
    EXP.write_text(exp0.decode("utf-8").replace(
        p1_src, p1_src.removesuffix("|已接") + "|接线缺", 1), encoding="utf-8", newline="")
    d_bad = run()
    got_red = any("C5 状态=接线缺" in r for r in d_bad["red"])
    EXP.write_text(exp0.decode("utf-8"), encoding="utf-8", newline="")
    d_ok = run()
    gone = len(d_ok["red"]) == base_red
    hit = got_red and gone
    print(f"  {'✅' if hit else '❌'} M4 C5「状态」：已接 ⇒ 接线缺（必须报红：{len(d_bad['red'])}）"
          f"· 改回已接（红必须消失 ⇒ {len(d_ok['red'])}，基线 {base_red}）")
    hits += 1 if hit else 0

    # M5 · C6 覆盖哨：把 P1 全部认领行删掉 ⇒ 报「没有任何认领行」
    # ⚠️ `splitlines()` + `join("\n")` 会把**整份**行尾写成 LF（M1–M4 走 `replace` 才幸免）⇒
    #    变异顺带改全件行尾 = 靶打偏，违「改已有文件按它自己的行尾」⇒ 下面按源件行尾拼。
    nl = "\r\n" if b"\r\n" in exp0 else "\n"
    keep = [l for l in exp0.decode("utf-8").splitlines() if not l.startswith("P1|")]
    EXP.write_text(nl.join(keep) + nl, encoding="utf-8", newline="")
    d = run()
    hit = any(s["chain"] == "P1" and s["total"] == 0 for s in d["summary"])
    print(f"  {'✅' if hit else '❌'} M5 删掉 P1 全部认领行 —— 总览里 P1 变「没有任何认领行」")
    hits += 1 if hit else 0
    EXP.write_bytes(exp0)

    # 逐字节复原校验
    ok = md5(EXP.read_bytes()) == h_exp and md5(SRC.read_bytes()) == h_src
    print(f"\n  复原校验：认领表 {'✅' if ok else '❌'} · 真源注册表 {'✅' if ok else '❌'}"
          f"（MD5 逐字节）")
    print(f"\n  反向灵敏度：**{hits}/5 命中**")
    return 0 if (hits == 5 and ok) else 1


if __name__ == "__main__":
    sys.exit(main())
