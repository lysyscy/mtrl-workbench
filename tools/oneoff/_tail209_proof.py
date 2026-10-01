"""`TAIL-209` 自证：把一处说明块**写长** ⇒ `test_说明块都不超长_弹窗也在内` **必须红**；跑完**逐字节还原**。

⚠️ 为什么另做一条离线判据、又为什么要自证：
   真机 ㉖ 的靶是 `#view .tip` —— **弹窗不在它视野里** ⇒ 弹窗说明**没有机器眼**（只会越写越长、没人会红）。
   本件证明新判据**真的会拦**（能证伪），⛔ 不是"写了个恒过的摆设"。
"""
from __future__ import annotations

import hashlib
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
TARGET = ROOT / "backend" / "app" / "web" / "index.html"
ANCHOR = "<b>备注点格即改</b>。</div>"
TEST = "tests/test_ux_text.py::test_说明块都不超长_弹窗也在内"

orig = TARGET.read_bytes()
before = hashlib.md5(orig).hexdigest()
text = orig.decode("utf-8")
assert text.count(ANCHOR) == 1, f"锚点不唯一（{text.count(ANCHOR)} 处）—— 自证要重定靶"

env = {"PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
run = [str(ROOT / "backend/.venv/Scripts/python.exe"), "-m", "pytest", "-q", TEST,
       "-p", "no:cacheprovider", "--tb=no", "--no-header"]

try:
    base = subprocess.run(run, cwd=ROOT / "backend", env={**__import__("os").environ, **env},
                          capture_output=True, text=True, encoding="utf-8")
    print(f"① 基线（未改动）⇒ rc={base.returncode}（应为 0）")
    TARGET.write_text(text.replace(ANCHOR, "<b>备注点格即改</b>。" + "补" * 300 + "</div>"),
                      encoding="utf-8", newline="")
    mut = subprocess.run(run, cwd=ROOT / "backend", env={**__import__("os").environ, **env},
                         capture_output=True, text=True, encoding="utf-8")
    print(f"② 把一处说明块写长 ⇒ rc={mut.returncode}（**必须非 0** —— 判据真的会拦）")
    tail = [ln for ln in (mut.stdout or "").splitlines() if "字" in ln or "FAILED" in ln][-3:]
    for ln in tail:
        print("   ", ln.strip()[:150])
    ok = base.returncode == 0 and mut.returncode != 0
finally:
    TARGET.write_bytes(orig)

after = hashlib.md5(TARGET.read_bytes()).hexdigest()
print(f"③ 逐字节还原：{'✅ 一致' if after == before else '❌ 不一致！'}（{before} → {after}）")
print("结论：" + ("✅ 新判据能证伪（写长必红 ＋ 还原干净）" if ok and after == before else "❌ 见上面"))
sys.exit(0 if ok and after == before else 1)
