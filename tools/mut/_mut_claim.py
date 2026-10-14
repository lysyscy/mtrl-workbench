"""反向灵敏度（`claim_audit`：「凡写裁定类提法，必须指得出 ① 日期 ② 出处」）—— 证明它**真会红**。

做法：在**活文档**里挑一行「有裁定 ＋ 有日期 ＋ 有出处」的行 ⇒ **删掉它的日期** ⇒ `claim_audit` 必须 **`rc=1`**
⇒ 立刻**逐字节复原**（MD5）⇒ 复原后必须回 `rc=0`。

⚠️ 判据为什么是 `rc`：2026-09-24 **用户裁定 `A`** 之前它是"黄不判红"（`rc` 恒 0），当时本件的判据只能取
   "**该行出现在清单里**"；现在它**接了真出口**（清零式闸门：有黄 ⇒ 非零退出）⇒ 判据**升级成 `rc=1`**（更硬：
   它同时证明"识别到了"与"闸门真的非零"）。
⚠️ 靶是**动态找**的（不写死行号/原文）—— 今天已中过多次"锚点过期"：凡"挑一条符合某几条正则的行"，一律用
   **同源正则现找**，⛔ 不抄行号。

用法：python tools/mut/_mut_claim.py
"""

from __future__ import annotations

import hashlib
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
PY = str(ROOT / "backend" / ".venv" / "Scripts" / "python.exe")
TOOL = str(ROOT / "tools" / "audit" / "claim_audit.py")
DOC = ROOT / "docs" / "status.md"

#: 与 `claim_audit.py` **同源**的四条正则（⛔ 别另写一套：口径只许一份）
CLAIM_RE = re.compile(r"用户(裁定|拍板)|裁定\s*[ABC]\b|已裁定|裁定过")
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}|\d{1,2}\s*月\s*\d{1,2}\s*日|\d{1,2}\s*月")
SRC_RE = re.compile(r"`[^`]*[:：]\s*\d+`|见\s*§|§\d|memory|\*\*§|`[^`]+\.md`")
DEFER_RE = re.compile(r"待裁定|尚待裁定|未裁定")


def run_tool() -> tuple[int, str]:
    # ⚠️⚠️ 2026-10-01（`TAIL-205` 收口 · 新闸门 `_run_muts.py` 一跑就抓到）：**漏了 `-X utf8`** ——
    #    子进程按本机默认编码（GBK）写 stdout，而本件按 utf-8 解 ⇒ **`UnicodeDecodeError` 直接崩**，
    #    连 `rc` 都取不到（本件 docstring 写着"判据是 rc"，实际它**从来没走到那一步**）。
    #    ⭐ 同族（本轮第 3 例）：`_mut_t12` / `_mut_t14t15` —— 见 `_run_muts.py` 的头注。
    p = subprocess.run([PY, "-X", "utf8", TOOL], cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def find_anchor(lines: list[str]) -> tuple[int, str] | None:
    """第一个「有裁定 ＋ 有日期 ＋ 有出处」的行 ⇒ `(1-based 行号, 行文本)`。"""
    for i, line in enumerate(lines, 1):
        if CLAIM_RE.search(line) and DATE_RE.search(line) and SRC_RE.search(line) \
                and not DEFER_RE.search(line):
            return i, line
    return None


def main() -> int:
    raw = DOC.read_bytes()
    md5_before = hashlib.md5(raw).hexdigest()
    anchor = find_anchor(raw.decode("utf-8").splitlines())
    if anchor is None:
        print("  ⛔ 找不到「有裁定 ＋ 有日期 ＋ 有出处」的锚行 ⇒ 本件无法自证")
        return 1
    lineno, line = anchor
    marker = f"{DOC.name}:{lineno}:"                      # `claim_audit` 输出里的定位串

    rc0, out0 = run_tool()
    print(f"  基线：claim_audit rc={rc0}（期望 0）· 锚行 = 第 {lineno} 行")
    if rc0 != 0 or marker in out0:
        print("  ⛔ 基线不干净（rc≠0，或锚行已在清单里）⇒ 停手")
        return 1

    # ⚠️⚠️ 2026-10-01（`TAIL-205` 收口 · 新闸门 `_run_muts.py` 一跑就抓到）：**原来只删第一处日期** ——
    #    而锚行（计划第 6 行）里**还含一个带日期的文件名**（`docs/archive/journal/2026-10-01.md`）
    #    ⇒ 删完**仍有日期** ⇒ `C1` 不亮 ⇒ 本件报 `0/1 命中`（它报"没抓到"是对的，**错的是一开始的判法太窄**）。
    #    ⇒ 改成把该行**所有日期样式**删掉（这才是"删掉它的日期"的本意）。
    mutated = DATE_RE.sub("", line)
    if mutated == line:
        print("  ⛔ 日期没删掉（正则没命中）⇒ 停手")
        return 1
    DOC.write_text(raw.decode("utf-8").replace(line, mutated, 1), encoding="utf-8", newline="")

    rc, out = run_tool()
    DOC.write_bytes(raw)                                   # ⭐ 立刻复原
    found = rc == 1 and marker in out
    ok_md5 = hashlib.md5(DOC.read_bytes()).hexdigest() == md5_before
    rc_end, out_end = run_tool()
    print(f"  {'✅' if found else '❌'} 删日期 ⇒ rc={rc}（期望 1）· 该行{'出现在' if marker in out else '**没**出现在'}"
          f" `C1` 清单里{'' if found else ' —— ⛔ 没抓到，闸门是假的'}")
    print(f"\n  复原校验（MD5 逐字节）：{'✅ 一致' if ok_md5 else '❌ 不一致'}")
    print(f"  复原后：rc={rc_end}（期望 0）· 清单里不再有该行 = {marker not in out_end}（期望 True）")
    print(f"  反向灵敏度：**{1 if (found and ok_md5 and rc_end == 0) else 0}/1 命中**")
    return 0 if (found and ok_md5 and rc_end == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
