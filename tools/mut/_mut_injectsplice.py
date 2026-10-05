"""**反向灵敏度**：`T22`（注入档「两行粘成一行」）**真有区分力**，且**不误伤正常排版**。

守什么：`tools/audit/audit_meta.py` 的 `check_line_splices` ＋ 两个常量
（`INJECT_DOCS` ＝ 目标集 · `SPLICE_RE` ＝ 模式本体）。
为什么值得有：当天实测 `MEMORY.md` 因编辑工具的锚点末尾多写一个换行而从 **93 行变 92 行**，
而**闸门 rc=0 · pytest 全绿 · 没有任何尺子看得见**（`MEMORY.md` 不在任何判据的栏位检查里）
⇒ 注入档每轮都被读，那处损坏谁也发现不了。

做法：把 `MEMORY.md` 真的粘一行 ⇒ 必须报；再把**正常排版**（上一行句号收尾 ＋ 下一行是列表项）
放进去 ⇒ **必须不报**（这一条比"会报"更要紧：`SPLICE_RE` 第一版用 `\\s*`，跨行匹配，
于是**全仓 78 件 md 全部命中、真粘连 0 件** —— 一条只会误报的判据比没有判据更坏）。
最后把模式本体改坏 ⇒ 必须**不再报**（证明那半边是承重的）。

⚠️ 一律 bytes ＋ 改完立刻按原 bytes 复原 ＋ 末尾 MD5 逐字节校验。
⚠️ 粘行这件事本机**真的发生过**，所以本件复原后必须核**行数**（少一行就是没复原干净）。
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MEM = ROOT / ".codebuddy" / "memory" / "MEMORY.md"
META = ROOT / "tools" / "audit" / "audit_meta.py"
PY = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"
AUDIT = ROOT / "tools" / "audit" / "doc_audit.py"


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def run_audit() -> tuple[int, str, int]:
    """→ (`必须修 N`, 全量输出, `MEMORY.md` 现行数)。⚠️ **必须带 `-v`** ——
    否则黄档只按件聚合成「N 条 <路径>」，"某条黄档编报了什么"在输出里根本看不见。"""
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
    r = subprocess.run([str(PY), str(AUDIT), "-v"], cwd=str(ROOT), capture_output=True,
                       text=True, encoding="utf-8", errors="replace", env=env)
    out = (r.stdout or "") + (r.stderr or "")
    m = re.search(r"必须修 (\d+)", out)
    n = len(MEM.read_text(encoding="utf-8").splitlines())
    return (int(m.group(1)) if m else -1), out, n


def t22_lines(out: str) -> list[str]:
    return [ln for ln in out.splitlines() if "[T22]" in ln]


def _restore(p: Path, src: bytes) -> None:
    p.write_bytes(src)
    assert p.read_bytes() == src, "复原后逐字节不一致：" + str(p)


def main() -> int:
    if not MEM.exists() or not META.exists():
        print("⛔ 靶件不在位（注入档三件 / `audit_meta.py`）⇒ 本件无法跑")
        return 1

    mem_src, meta_src = MEM.read_bytes(), META.read_bytes()
    base_red, base_out, base_n = run_audit()
    base_t22 = t22_lines(base_out)
    print(f"基线（未改坏）必须修 {base_red}（应为 0）· `T22` 命中 {len(base_t22)} 条"
          f"（应为 0）· `MEMORY.md` {base_n} 行")
    if base_red != 0 or base_t22:
        print("  ⛔ 基线就不干净 ⇒ 先把红 / `T22` 黄清了再来跑本件")
        return 1

    cases: list[tuple[str, str, Path, bytes, object, str]] = []
    cases.append(("S1", "`T22` 真粘连（两行被粘成一行）必须报", MEM, mem_src, "glue", "hit"))
    cases.append(("S2", "**正常排版**（句号收尾 ＋ 下一行列表项）**必须不报**", MEM, mem_src,
                  "normal", "clean"))
    cases.append(("S3", "模式本体改坏（标点类换成不可能命中的）⇒ 必须**不再报**", META, meta_src,
                  "break_re", "clean"))

    hit = 0
    for tag, desc, path, src, mode, expect in cases:
        try:
            raw = path.read_bytes()
            text = raw.decode("utf-8")
            if mode == "glue":
                # 找一处「以句号收尾的正文行」＋ 其下一行是列表项 ⇒ 把两者之间那个换行**删掉**。
                lines = text.split("\n")
                done = False
                for i in range(len(lines) - 1):
                    if not lines[i].rstrip().endswith("。"):
                        continue
                    if not re.match(r"^\s*(?:[-*+]\s|>\s)", lines[i + 1]):
                        continue
                    lines[i] = lines[i].rstrip() + " " + lines[i + 1].lstrip()
                    del lines[i + 1]
                    done = True
                    break
                assert done, "MEMORY.md 里找不到可粘的相邻两行 ⇒ 本件需重定靶"
                path.write_bytes("\n".join(lines).encode("utf-8"))
            elif mode == "normal":
                anchor = "\n## "
                assert anchor in text, "锚点 \n## 不在了 ⇒ 本件需重定靶"
                path.write_bytes(text.replace(
                    anchor, "\n这一行以句号收尾，下面是正常另起一行的列表项。\n\n- 正常列表项。\n\n## ", 1
                ).encode("utf-8"))
            elif mode == "break_re":
                old = "。；：、，）】」!?！？"
                assert text.count(old) == 1, "模式本体写法变了 ⇒ 本件需重定靶"
                path.write_bytes(text.replace(old, "␀", 1).encode("utf-8"))
            red, out, n = run_audit()
        finally:
            _restore(path, src)
        got = len(t22_lines(out))
        ok = (got > 0) if expect == "hit" else (got == 0)
        if tag == "S1":
            ok = ok and n == base_n - 1, "粘完没少一行（%d → %d）⇒ 改法没生效" % (base_n, n)
        print("  %s %s %s  →  `T22` 命中 %d 条（期望 %s）%s"
              % ("✅" if ok else "⛔ 未命中", tag, desc, got, expect,
                 "  · 必须修 %d" % red if red else ""))
        hit += bool(ok)

    dirty = [p for p, b in ((MEM, mem_src), (META, meta_src)) if md5(p) != hashlib.md5(b).hexdigest()]
    n_after = len(MEM.read_text(encoding="utf-8").splitlines())
    ok_final = not dirty and n_after == base_n
    print()
    print("  命中 %d/%d" % (hit, len(cases)))
    print("  复原校验（MD5 逐字节）：%s · `MEMORY.md` 行数 %d → %d %s"
          % ("✅ 全部复原" if not dirty else "❌ 未复原：" + "、".join(map(str, dirty)),
             base_n, n_after, "✅" if n_after == base_n else "❌ 少行 = 没复原干净"))
    return 0 if (hit == len(cases) and ok_final) else 1


if __name__ == "__main__":
    sys.exit(main())
