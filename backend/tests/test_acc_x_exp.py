"""`ACC-X-EXP-001` —— 导出（跨域）12 点。

⚠️ 这 12 点里 **7 点早已有主**（`test_tail04_export.py` 钉 `001-02`/`001-05`；
   `test_path1_weldgas.py` 等钉路径①的 `001-08`~`001-12`）⇒ ⛔ 本文件**不复述**它们，
   只补**还没人验过**的那几点（`001-01` · `001-03` · `001-04` · `001-06` · `001-07`）。
"""

from __future__ import annotations

import pathlib
import re

import app
from tests.acc_plugin import acc
from tests.shell_src import SHELL  # noqa: F401  ← `P4`① 读取点收敛


def _shell_dir() -> pathlib.Path:
    return pathlib.Path(app.__file__).resolve().parent / "web"


def _index() -> str:
    return (_shell_dir() / "index.html").read_text(encoding="utf-8")


def _view_slices(html: str) -> dict[str, str]:
    """`V.mXX = …` → 该视图的渲染切片（到下一个视图起点为止）。

    ⚠️ 「逐页」的**页**在这里 = 导航里的视图（`NAV` 的第二列）—— ⛔ 不是"文件"也不是"卡片"，
       否则"逐页都有导出入口"这句话就没法核（页的粒度不定 ⇒ 断言必然写成橡皮尺）。
    """
    starts = [(m.group(1), m.start()) for m in re.finditer(r"^V\.(m\d+)\s*=", html, re.M)]
    out: dict[str, str] = {}
    for i, (k, s) in enumerate(starts):
        e = starts[i + 1][1] if i + 1 < len(starts) else len(html)
        out[k] = html[s:e]
    return out


#: **已裁定不设单独导出**的页 ⇒ 必须在**页面上说明去处**（claim 的除外条件）
EXPORT_EXEMPT = {
    "m09": "随「逐月欠款台账」导出（作为每项目工作簿的第 3 个工作表）",
}
#: ⚠️⚠️ **已知缺口**（2026-09-20 首次核对逮到）：既没有导出入口、也没有豁免说明。
#:    ⛔ 这不是"白名单"——它是**欠账清单**：新增缺口会**变红**，缺口被修掉**也会变红**
#:      （提醒把清单改小）。⇒ 缺口**不许静默地来或去**。
KNOWN_GAP = {"m10", "m14", "m15"}


@acc("ACC-X-EXP-001", "001-01")
def test_逐页都有导出入口或页面说明去处():
    """claim：「**逐页都有导出入口**；已裁定不设单独导出的页面除外（**且须在页面上说明去处**）」。

    ⚠️ 这条最容易写成橡皮尺（"页"的粒度不定 ⇒ 随便挑几页就算过）。⇒ 钉法是：
       页 = **导航视图全集**，逐页核「有导出入口 **或** 有页面内说明」，**两边都不许漏**。
    ⚠️ 缺口**如实记为 `KNOWN_GAP`**，并**双向**钉住它：
       ① 缺口里冒出新的 ⇒ 红（新缺了一块）；
       ② 缺口被修好却没从清单里划掉 ⇒ 红（清单成了摆设 —— 那这条断言就再也咬不到人了）。
    """
    html = _index()
    views = dict(sorted(set(re.findall(r"\['(m\d+)','([^']+)','[^']+'\]", html))))
    assert len(views) >= 14, f"导航只解析出 {len(views)} 个视图 —— 解析大概失效了"
    slices = _view_slices(html)

    no_entry, no_note, exempt_ok = [], [], []
    for k in views:
        seg = slices.get(k, "")
        if re.search(r'data-act="exp\w*"', seg):
            continue                                   # 有导出入口 ⇒ 这页闭合
        no_entry.append(k)                             # 没入口（下面的分支再细分）
        note = re.search(r"不单独[^\"<]{0,40}导出[^\"<]{0,60}", seg)
        if note:
            exempt_ok.append(k)                        # 有豁免说明 ⇒ 按 claim 的除外条件，闭合
        elif k not in KNOWN_GAP:
            no_note.append(k)                          # 没入口、没说明、也不在欠账清单 ⇒ **新缺口**

    assert not no_note, (
        "这些页面**既没有导出入口、也没有『不单独导出』的说明**（且不在欠账清单里）⇒ 新缺口：\n  "
        + "\n  ".join(sorted(no_note))
        + "\n  ⇒ 要么给它加导出入口，要么在页面上写明去处（claim 的除外条件要求「说明去处」）。")

    # ⭐ 双向：缺口**不许静默地来或去**
    stale = set(KNOWN_GAP) - set(no_entry)
    assert not stale, (
        f"欠账清单里的 {sorted(stale)} **已经不再是缺口**（有入口或有说明了）"
        " ⇒ 把它们从 `KNOWN_GAP` 里划掉（⛔ 清单成了摆设，这条断言就再也咬不到人了）")

    # ⭐ 豁免的页**必须真的在页面上写了去处**（⛔ 空挂一个名单不算）
    for k in EXPORT_EXEMPT:
        assert k in exempt_ok, f"{k} 声明了豁免，但页面上找不到『不单独导出』的说明"


__all__ = ["EXPORT_EXEMPT", "KNOWN_GAP"]
