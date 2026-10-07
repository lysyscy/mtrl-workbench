"""**选集的机器眼**（`TAIL-239` 第 3 步）—— 证明 `_run_muts.py` 那道缺口自检**真的会红**。

守什么：`tools/oneoff/_run_muts.py` 的 `cover_gap()` / `report_cover()` ——
「`tools/mut/_mut_*.py` 全集 −（`KEY` ∪ `KEEP_OUT`）＝ 空」这条判据**真有区分力**。

做法：造出三种"名单盖不住"的情形 ⇒ 断言 `--cover-only` **必须报红且报出那个件名** ⇒ 逐字节复原（MD5）。

    backend/.venv/Scripts/python.exe -X utf8 tools/mut/_mut_keycover.py

⚠️⚠️ **为什么这道守卫本身也必须有守卫**（本仓反复吃的那类教训）：
   「装了一个会报警的机器眼」不等于「那个机器眼真的会响」。
   ⛔ 只跑一遍 `--cover-only` 看它说"✅ 一致"＝**什么都没证明** —— 那是**恒真**的判据。
   ⇒ 本件故意把两个方向都改成红：
     ① **缺口方向**：造一支不在 `KEY`/`KEEP_OUT` 的 `_mut_*.py` ⇒ 必须 `rc=1` 且**报出那个名字**；
         ② **陈旧方向**：往 `KEEP_OUT` 塞一个**不存在**的件名 ⇒ 必须 `rc=1` 且报出陈旧
            （⚠️ 这一支最容易被漏：它是 `sorted(listed - on_disk)` 那半边，没断言过就可能是死代码）；
         ③ **慢集孤儿方向**（`TAIL-244` 加）：往 `SLOW_KEY` 塞一个**不在 `KEY`** 的名字 ⇒ 必须 `rc=1`
            （⚠️ 这是**本族同款的静默失效**：`--fast` 的用例从 `KEY` 取 ⇒ 只登记在慢集里的件**没人跑、也没人写为什么**）。
        三处都必须**造得出来的红**（MEMORY「哑靶三形态」：`not any(...)` 必配造得出来的红）。

⚠️ **不碰任何业务件**：临时件只落在 `tools/mut/` 下、且件名以 `T8` 那支同样的约定
   （**用完即删** ⇒ `finally` 必删）；改 `KEEP_OUT` 走 **bytes ＋ MD5 逐字节复原**。
"""

from __future__ import annotations

import hashlib
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
PY = str(ROOT / "backend" / ".venv" / "Scripts" / "python.exe")
RUNNER = ROOT / "tools" / "oneoff" / "_run_muts.py"
MUT = ROOT / "tools" / "mut"
#: ⚠️ 这个名字**必须匹配 `tools/mut/` 的变异件通配**（`_mut_` 开头 ＋ `.py`）
#:   —— 否则造出来的"缺口"根本不成立 ⇒ 这道守卫会拿到一个**恒绿**的假结果。
#:   ⛔ 故意的"无辨识度"正是要点：它只在被造出来到被删掉之间存在。
GAP_NAME = "_mut_tmp_unlisted_probe.py"
GAP_FILE = MUT / GAP_NAME
STALE_NAME = "_mut_tmp_never_existed_probe.py"
#: ③ 慢集孤儿（`TAIL-244`）：只会被**插进 `SLOW_KEY` 字典体**当字符串，从来不落盘
ORPHAN_NAME = "_mut_tmp_slow_orphan_probe.py"


def run_cover() -> tuple[int, str]:
    """跑那道自检（`--cover-only` ⇒ 不跑任何变异件）→ (`rc`, 输出)。"""
    r = subprocess.run([PY, "-X", "utf8", str(RUNNER), "--cover-only"], cwd=str(ROOT),
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main() -> int:
    src = RUNNER.read_bytes()
    md5_before = hashlib.md5(src).hexdigest()
    cases: list[tuple[str, bool, str]] = []

    # ---- ① 缺口方向：盘上多出一支不在两份名单里的件 ----
    GAP_FILE.write_text("# 临时件（`_mut_keycover.py` 用后即删）\nX = 1\n", encoding="utf-8", newline="")
    try:
        rc, out = run_cover()
        ok = rc == 1 and GAP_NAME in out
        cases.append((f"造一支不在名单里的 `{GAP_NAME}` ⇒ 缺口自检必须报红", ok,
                      f"rc={rc}（应为 1）· 输出里有它的名字={'是' if GAP_NAME in out else '否'}"))
    finally:
        GAP_FILE.unlink(missing_ok=True)

    # ---- ② 陈旧方向：`KEEP_OUT` 里塞一个不存在的件名（验那半边不是死代码）----
    # ⚠️⚠️ **必须插进 `KEEP_OUT` 字典体里，不能 append 到文件末尾** ——
    #   文件末尾是 `if __name__ == "__main__": sys.exit(main())` ⇒ 追加的行**永远执行不到**
    #   （首版就栽在这：报红被"通过"了 ⇒ 是 `rc==1` 这条断言把它抓住的，不是运气好）。
    # ⚠️ 锚点**不许写死 `{\n`** —— `_run_muts.py` 是 CRLF ⇒ 那样 `index()` 直接 `ValueError`
    #   （本仓老坑：改已有文件要按它自己的行尾）。
    anchor = b'KEEP_OUT: dict[str, str] = {'
    try:
        i = src.index(anchor) + len(anchor)
        # ⚠️ 插入行**必须跟目标件自己的行尾**（探测一次就复用）—— 写死 `\r\n` 等于给 LF 件埋一颗雷
        nl = b'\r\n' if src[i:i + 2] == b'\r\n' else b'\n'
        i += len(nl)
        RUNNER.write_bytes(src[:i]
                           + f'    "{STALE_NAME}": "（本件自己临时塞的，用后即删）",'.encode("utf-8") + nl
                           + src[i:])
        rc, out = run_cover()
        ok = rc == 1 and STALE_NAME in out
        cases.append((f"往 `KEEP_OUT` 塞一个不存在的 `{STALE_NAME}` ⇒ 必须报陈旧", ok,
                      f"rc={rc}（应为 1）· 输出里有它的名字={'是' if STALE_NAME in out else '否'}"))
    finally:
        RUNNER.write_bytes(src)                       # ⭐ 立刻逐字节复原

    # ---- ③ 慢集孤儿方向：往 `SLOW_KEY` 塞一个**不在 `KEY`** 的名字（`TAIL-244` 加）----
    #   ⚠️ 这一支验的是"**慢集不是第三档**"：`--fast` 的用例从 `KEY` 取 ⇒ 慢集只做过滤
    #   ⇒ 只登记在慢集里的件**没人跑、也没人写为什么**（本族同款的静默失效）。
    anchor = b'SLOW_KEY: frozenset[str] = frozenset({'
    try:
        i = src.index(anchor) + len(anchor)
        nl = b'\r\n' if src[i:i + 2] == b'\r\n' else b'\n'
        i += len(nl)
        RUNNER.write_bytes(src[:i]
                           + f'    "{ORPHAN_NAME}",'.encode("utf-8") + nl
                           + src[i:])
        rc, out = run_cover()
        ok = rc == 1 and ORPHAN_NAME in out
        cases.append((f"往 `SLOW_KEY` 塞一个不在 `KEY` 的 `{ORPHAN_NAME}` ⇒ 必须报孤儿", ok,
                      f"rc={rc}（应为 1）· 输出里有它的名字={'是' if ORPHAN_NAME in out else '否'}"))
    finally:
        RUNNER.write_bytes(src)                       # ⭐ 立刻逐字节复原

    # ---- 复原后必须回到"一致"（几处红都只允许是造出来的）----
    rc, out = run_cover()
    cases.append(("复原后缺口自检必须回到绿（rc=0）", rc == 0,
                  f"rc={rc}（应为 0）· {out.strip().splitlines()[-1][:90] if out.strip() else '<无输出>'}"))

    ok_md5 = hashlib.md5(RUNNER.read_bytes()).hexdigest() == md5_before
    clean = not GAP_FILE.exists()
    cases.append(("`_run_muts.py` 逐字节复原（MD5）", ok_md5, "一致" if ok_md5 else "⛔ 不一致"))
    cases.append(("临时件清场（不留残件）", clean, "✅ 无残留" if clean else f"⛔ 还在：{GAP_FILE.name}"))

    print()
    for name, ok, note in cases:
        print(f"  {'✅' if ok else '⛔ 未命中'} {name} —— {note}")
    hits = sum(1 for _, ok, _ in cases if ok)
    print(f"\n  反向灵敏度：**{hits}/{len(cases)} 命中**"
          f"（⛔ 少一条 = 缺口自检有一半是死的 ⇒ 报出来，别当通过）")
    return 0 if hits == len(cases) else 1


if __name__ == "__main__":
    sys.exit(main())