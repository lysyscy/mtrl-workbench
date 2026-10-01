"""诊断 2：把 m04 那块**就地加长**，看 `_tip_blocks()` 数出来多少字；跑完逐字节还原。"""
from __future__ import annotations

import hashlib
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "backend" / "tests"))

from test_ux_text import _tip_blocks  # noqa: E402

F = ROOT / "backend" / "app" / "web" / "index.html"
orig = F.read_bytes()
KEY = "备注点格即改"


def show(tag: str) -> None:
    hit = [r for r in _tip_blocks() if KEY in r[3]]
    print(f"{tag}：命中 {len(hit)} 块 ⇒ {[(n, ln, c) for n, ln, c, _ in hit]}")


show("① 原样")
text = orig.decode("utf-8")
anchor = f"<b>{KEY}</b>。</div>"
print(f"   锚点出现 {text.count(anchor)} 次")
try:
    F.write_text(text.replace(anchor, f"<b>{KEY}</b>。" + "补" * 120 + "</div>", 1),
                 encoding="utf-8", newline="")
    show("② 加长 120 字后")
finally:
    F.write_bytes(orig)
print("③ 还原 md5：", hashlib.md5(F.read_bytes()).hexdigest() == hashlib.md5(orig).hexdigest())
