"""反向灵敏度（`cover_gap` —— `T7a`/`T7b` 判据覆盖）—— 证明它**真有区分力** ＋ **新真出口有效**。

⚠️ 本件覆盖两件事：
- **① 逻辑**：往交付面的某个 `MOD-*.md` 能力表**末尾追加一行**「没有用例号的新能力」
  ⇒ 清单里**必须出现它**（`T7a` 无用例认领 ＋ `T7b` 口径 `§9.9.9` 无人 cover）。
- **② 真出口**（⭐ 2026-09-24 补 `main()` **之前**本尺子**空转**：0 行输出、`rc` 恒 0 ——
  而它明明在收工闸门的「12 把尺子」清单里）：把 `tools/t7_expected.txt` **临时挪开**
  ⇒ **必须 `rc=1`**（⛔ 不静默通过）。

⚠️⚠️ **①会临时改交付面的既有文档**（`D:\\工作\\AI\\PRD编写夹 - Workbuddy专用`，**WPS 云同步树**）⇒ 规矩：
   **一次只碰一个文件** · 只**追加一行**（⛔ 不新建文件） · 跑完**立刻按 bytes 复原** ·
   收尾 **MD5 逐字节校验**（用户 2026-09-24：「云同步也没那么蠢，只要别同时大量连续改文件」）。

用法：python tools/mut/_mut_covergap.py
"""

from __future__ import annotations

import hashlib
import os
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
RULER = ROOT / "tools" / "audit" / "cover_gap.py"
REGISTRY = ROOT / "tools" / "t7_expected.txt"
PY = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"
MARKER = "ZZZ变异靶能力ZZZ"                      #: ⭐ 够怪才唯一 —— 免得撞上文档里已有的字

sys.path.insert(0, str(ROOT / "tools" / "audit"))
from audit_common import delivery_root  # noqa: E402


def _env() -> dict[str, str]:
    return {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}


def run_ruler() -> tuple[int, str]:
    r = subprocess.run([str(PY), str(RULER)], cwd=str(ROOT), capture_output=True,
                       text=True, encoding="utf-8", errors="replace", env=_env())
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def pick_target() -> tuple[pathlib.Path, int]:
    """→ (交付面某个 `MOD-*.md`, 它的能力表**列数**)。⛔ 找不到就**报错停手**（别猜）。"""
    prd = delivery_root() / "PRD" / "02-功能规格"
    for p in sorted(prd.glob("MOD-*.md")):
        for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
            if not ln.startswith("|"):
                continue
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            if len(cells) >= 5 and re.fullmatch(r"\d+", cells[0]):
                return p, len(cells)
    raise SystemExit(f"⛔ 交付面里找不到可用的能力表（{prd}）⇒ 本件无法跑")


def main() -> int:
    rc0, out0 = run_ruler()
    print(f"基线：cover_gap rc={rc0} · 输出含 marker = {MARKER in out0}（应 rc=0 · 不含）")
    if rc0 != 0 or MARKER in out0:
        print("  ⛔ 基线不干净 ⇒ 先查（可能是上次变异没复原）")
        return 1

    target, ncols = pick_target()
    before = target.read_bytes()
    md5_before = hashlib.md5(before).hexdigest()
    print(f"① 靶 = {target}（{ncols} 列 · {len(before)} 字节）—— ⚠️ 交付面文件，跑完立刻复原")
    row = ["99", MARKER, "§9.9.9", "（变异靶 · 用完即复原）"] + [""] * (ncols - 5) + [""]
    hits = 0
    try:
        target.write_bytes(before + ("\n" + "| " + " | ".join(row) + " |\n").encode("utf-8"))
        rc, out = run_ruler()
        hit_a = MARKER in out and out.count(MARKER) >= 1
        print(f"  {'✅' if hit_a else '⛔ 未命中'} 追加一行「无用例号的新能力」⇒ 清单里出现它"
              f"（rc={rc} · 命中 {out.count(MARKER)} 处）")
        hits += hit_a
    finally:
        target.write_bytes(before)

    # ---- ② 真出口：登记册读不到 ⇒ 必须 rc=1 ----
    reg_before = REGISTRY.read_bytes()
    reg_tmp = REGISTRY.with_suffix(".txt._mut_tmp")
    try:
        REGISTRY.rename(reg_tmp)
        rc, out = run_ruler()
        hit_b = rc == 1 and "登记册" in out
        print(f"  {'✅' if hit_b else '⛔ 未命中'} 登记册挪开 ⇒ 必须 rc=1（实得 rc={rc}）"
              "（⭐ 这就是 2026-09-24 补的真出口 —— 以前它照样 rc=0）")
        hits += hit_b
    finally:
        reg_tmp.rename(REGISTRY)

    ok_md5 = hashlib.md5(target.read_bytes()).hexdigest() == md5_before
    ok_reg = REGISTRY.exists() and REGISTRY.read_bytes() == reg_before
    print()
    print(f"  复原校验：交付面文件 MD5 {'✅ 逐字节一致' if ok_md5 else '❌ 不一致'}"
          f" · 登记册 {'✅ 原样' if ok_reg else '❌ 不一致'}")
    print(f"  反向灵敏度：**{hits}/2 命中**")
    return 0 if (hits == 2 and ok_md5 and ok_reg) else 1


if __name__ == "__main__":
    sys.exit(main())
