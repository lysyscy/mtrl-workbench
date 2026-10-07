"""反向灵敏度（`syntax_audit` —— 「能编译吗 / 能解析吗 / 壳目录干净吗」）—— 证明它**真有区分力**。

⚠️ 本件为什么必需：`syntax_audit.py` **自带** `--selftest`（在临时目录里造样本 ⇒ `Q1`/`Q2`/`Q3` 各证明一次），
   但**没有任何地方跑它** —— 收工闸门跑的是 `syntax_audit.py`（**不带参数**）⇒ 那份自证是**休眠的**
   （写了、当时能过、此后**没人会碰它** ⇒ 尺子腐化了也没人知道）—— ⭐ "有一次证明过" ≠ "有守卫"。
   本件把两件事一起做：① 把那份休眠自检**叫醒**（`M4`）② 在**活树**上各改坏一处 ——
   内建自检用的是**临时样本**，它证明不了"**真仓里的文件**确实被这把尺子看得见"。

五靶（每处改完**立刻按 bytes 复原** ＋ 收尾 MD5 校验）：
- `M1` `Q1`：在 `tools/` 下新建一个**语法错**的 `.py` ⇒ 必须红（用完删掉；⚠️ 名字**故意不带** `_mut_`，
  免得被「变异件清单」当成常驻件统计）。
- `M2` `Q2`：把壳的**最小一件**（`web/shell/print-export.js`）追加一段过不了 `node --check` 的内容 ⇒ 必须红。
  ⚠️ **动过壳件** ⇒ 本轮收尾必须多走一步 `shell_verify.py --snapshot` 盖章（`MEMORY.md §〇之二`）。
- `M3` `Q3`：在 `backend/app/web/shell/` 下放一个 `*.bak-sync` 散件 ⇒ 必须红（用完删掉）。
- `M4` 内建 `--selftest`（临时样本里**逐规则各证明一次** · ⛔ needle 不钉条数：段数随尺子加规则变）
  ⇒ 必须 `rc=0` ＋ 结论行自报"都能区分"（⚠️ 没有 `node` 时它会自报"无法自证" ⇒ 本件判失败，
  那是**对的** —— ⛔ 别把它当通过）。
- ⭐ `M5` `Q2` **内联脚本**：把语法错塞进 `index.html` 的**真内联脚本**（第一块）⇒ 必须红。
  ⚠️ 2026-09-28 补：`_extract_script` 原取 `blocks[-1]`（= 那个 **7 字节空块**）⇒ `Q2` **恒绿**；
  `M2` 只打外链件、抓不到 ⇒ 这条是那个缺陷的专用眼。

用法：python tools/mut/_mut_syntax.py
"""

from __future__ import annotations

import hashlib
import os
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
RULER = ROOT / "tools" / "audit" / "syntax_audit.py"
PY = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"

Q1_TMP = ROOT / "tools" / "_tmp_q1_broken.py"           #: ⚠️ 用完删；名字不带 `_mut_`
Q2_TARGET = ROOT / "backend" / "app" / "web" / "shell" / "print-export.js"   #: 壳件里最小的一件
Q2I_TARGET = ROOT / "backend" / "app" / "web" / "index.html"                  #: 内联脚本那一块（M5）
Q3_TMP = ROOT / "backend" / "app" / "web" / "shell" / "_tmp_stray.js.bak-sync"


def _env() -> dict[str, str]:
    return {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}


def run_ruler(*extra: str) -> tuple[int, str, int]:
    """→ (`必须修 N`, 输出, rc)。⚠️ `N` 解析不到 ⇒ `-1`（子进程没起来 ⇒ 每处"看起来变红" = 全假红）。

    ⚠️ `--selftest` 模式**不打**「必须修」那一行（它打的是「自检结论」）⇒ 那条靶**只能看 rc**。
    """
    r = subprocess.run([str(PY), str(RULER), *extra], cwd=str(ROOT), capture_output=True,
                       text=True, encoding="utf-8", errors="replace", env=_env())
    out = (r.stdout or "") + (r.stderr or "")
    m = re.search(r"必须修 (\d+)", out)
    return (int(m.group(1)) if m else -1), out, r.returncode


def main() -> int:
    base_n, base_out, _ = run_ruler()
    print(f"基线（未改坏）syntax_audit 必须修 {base_n}（应为 0）")
    if base_n != 0:
        print("  ⛔ 基线就不干净 ⇒ 先清红再来跑本件")
        return 1

    hits = 0
    total = 5

    # ---- M1 `Q1`：新造一个编译不过的 `.py` ----
    Q1_TMP.write_text('X = f"说"话"\n', encoding="utf-8")
    try:
        n, out, _ = run_ruler()
    finally:
        Q1_TMP.unlink(missing_ok=True)
    ok = n > 0 and Q1_TMP.name in out
    hits += ok
    print(f"  {'✅' if ok else '⛔ 未命中'} M1 `Q1` 造一个语法错的 `.py` ⇒ 必须修 {n}（应含 {Q1_TMP.name}）")

    # ---- M2 `Q2`：壳件追加一段 node 解析不了的内容 ----
    before = Q2_TARGET.read_bytes()
    try:
        Q2_TARGET.write_bytes(before + b"\nconst _tmp_broken = ;\n")
        n, out, _ = run_ruler()
    finally:
        Q2_TARGET.write_bytes(before)
    ok = n > 0 and f"{Q2_TARGET.name} 过不了" in out
    hits += ok
    print(f"  {'✅' if ok else '⛔ 未命中'} M2 `Q2` 壳件追加语法错 ⇒ 必须修 {n}（应含「{Q2_TARGET.name} 过不了」）")

    # ---- M3 `Q3`：壳目录放一个备份散件 ----
    Q3_TMP.write_text("// 临时散件（本件用完即删）\n", encoding="utf-8")
    try:
        n, out, _ = run_ruler()
    finally:
        Q3_TMP.unlink(missing_ok=True)
    ok = n > 0 and Q3_TMP.name in out
    hits += ok
    print(f"  {'✅' if ok else '⛔ 未命中'} M3 `Q3` 壳目录放 `*.bak-sync` ⇒ 必须修 {n}（应含 {Q3_TMP.name}）")

    # ---- M4：把**休眠的内建自检**叫醒（⚠️ 它不打「必须修」那一行 ⇒ 这条**只看 rc ＋ 结论行**）----
    #   ⛔ needle **对条数不敏感**（钉「自检结论」＋「都能区分」，⛔ 不钉"三条/四条/五条"）：
    #     自检段数随尺子加规则增减，而结论行里那个条数是**尺子自己写的**、未必等于段数
    #     ⇒ 钉数字的断言必然过期 —— **本靶就是这样烂掉的**（恒判未命中）。
    #     （⛔ 连这条注释也不许钉"现状几段"：钉了就在重犯同一个病，且没有机器眼会喊。）
    #   ⭐ 失败方向仍然有牙：自检不过时结论行打的是「⛔ 自检未通过」⇒ 两个 needle 都命中不了。
    #   ♻ **造红配方**（要验这两段 needle 有牙时照跑）：把任一段换成 `"__NO_SUCH_WORD__"`
    #     ⇒ 必须报「⛔ 未命中 M4」＋ `4/5` ＋ rc=1；逐字节复原后必须回到 `5/5`。
    _n, out, rc = run_ruler("--selftest")
    ok = rc == 0 and "自检结论" in out and "都能区分" in out
    hits += ok
    print(f"  {'✅' if ok else '⛔ 未命中'} M4 内建 `--selftest` ⇒ 结论行须自报「每条规则都能区分」（⛔ 不钉条数）"
          f"（rc={rc}，应为 0；⚠️ 无 node 时它会自报『无法自证』⇒ 本件判失败，那是对的）")

    # ---- M5 `Q2`：把语法错塞进 `index.html` 的**真内联脚本**（第一块）----
    #   ⚠️ 2026-09-28 补：原 `_extract_script` 取 `blocks[-1]`（= `index.html` 里**末尾那个 7 字节空块**）
    #      ⇒ `Q2` 对着空块 `node --check` ⇒ **恒绿**；当场后果：一段含反引号的注释写进 `V.m05` 的模板字面量
    #      文本区（截断模板串 ⇒ 白屏），本尺子仍报「✅ 通过」。M2 只打**外链件**，抓不到这条 ⇒ 补本靶。
    raw = Q2I_TARGET.read_bytes()
    try:
        i = raw.index(b"</script>")            # 第一块（真壳代码）的结尾
        Q2I_TARGET.write_bytes(raw[:i] + b"\nconst _tmp_broken_inline = ;\n" + raw[i:])
        n, out, _ = run_ruler()
    finally:
        Q2I_TARGET.write_bytes(raw)
    ok = n > 0 and f"{Q2I_TARGET.name} 过不了" in out
    hits += ok
    print(f"  {'✅' if ok else '⛔ 未命中'} M5 `Q2` 内联脚本塞语法错 ⇒ 必须修 {n}"
          f"（应含「{Q2I_TARGET.name} 过不了」—— 这条专打「取错块」那个缺陷）")

    # ---- 复原校验：两个临时件必须**不存在** + 两处壳件逐字节复原 ----
    leftovers = [p for p in (Q1_TMP, Q3_TMP) if p.exists()]
    shell_ok = hashlib.md5(Q2_TARGET.read_bytes()).hexdigest() == \
        hashlib.md5(before).hexdigest()
    shell_ok = shell_ok and hashlib.md5(Q2I_TARGET.read_bytes()).hexdigest() == hashlib.md5(raw).hexdigest()
    print()
    print(f"  临时件残留：{'❌ ' + str(leftovers) if leftovers else '✅ 无'}"
          f" · 壳件逐字节复原：{'✅' if shell_ok else '❌'}")
    print(f"  反向灵敏度：**{hits}/{total} 命中**")
    return 0 if (hits == total and not leftovers and shell_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
