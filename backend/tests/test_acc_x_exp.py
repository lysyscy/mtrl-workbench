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

    ⚠️ 「页」在这里 = 导航里的视图（`NAV` 的第二列）—— ⛔ 不是"文件"也不是"卡片"，
       否则"逐页都有导出入口"这句话就没法核（页的粒度不定 ⇒ 断言必然写成橡皮尺）。
    """
    starts = [(m.group(1), m.start()) for m in re.finditer(r"^V\.(m\d+)\s*=", html, re.M)]
    out: dict[str, str] = {}
    for i, (k, s) in enumerate(starts):
        e = starts[i + 1][1] if i + 1 < len(starts) else len(html)
        out[k] = html[s:e]
    return out


#: **非数据页** —— 本就不设导出。
#: ⚠️⚠️ 依据 = **用户 2026-09-20 亲口补的原意**：
#:    > 「我当时说所有页面都能导出的**原意，就是所有有数据的页面**，
#:    >   一些非数据页面根本不算在内的」
#: ⛔ **「非数据」≠「页上没有表」** —— `m15` 页上就有 `m15:users` 那张表，它是**系统/账号数据**、
#:   不是**业务台账**；`m14` 是**配置类**（§9.4）；`m10` 是**暂缓**（页都没做）。
#:    ⇒ ⛔ 所以**不许**拿"页上有没有 `data-sort-key`"当真值来源（那会得出"m15 是数据页"）。
NON_DATA_VIEWS = {"m10", "m14", "m15"}
#: **是数据页、但不单独导出** ⇒ 按 claim 的除外条件，必须在**页面上说明去处**。
EXPORT_EXEMPT = {
    "m09": "随「逐月欠款台账」导出（作为每项目工作簿的第 3 个工作表）",
}


@acc("ACC-X-EXP-001", "001-01")
def test_有数据的页面都有导出入口():
    """claim：「**逐页**都有导出入口；已裁定不设单独导出的页面除外（**且须在页面上说明去处**）」。

    ⚠️⚠️ **这句 claim 的字面有歧义，执行形态是「三段」而不是「字面上的每一个视图」**：
      ① **数据页** ⇒ 必须有导出入口；
      ② **数据页、但不单独导出** ⇒ 必须**在页面上说明去处**（`m09`）；
      ③ **非数据页** ⇒ **不在范围内**（`m10` 暂缓 / `m14` 配置类 / `m15` 系统账号）。
    ⚠️ 本断言**第一版按字面执行**，把 ③ 判成了"3 个缺口" —— **那是误判**（用户当场纠正）。
       误判换来的一样东西是：**证明这句 claim 的字面本身不可执行** ⇒
       已提议把它改写成上面三段（⛔ 否则下一个按字面做的人／模型还会重蹈覆辙）。
    ⚠️ `NON_DATA_VIEWS` 用**双向**钉住：冒出新的／不再成立，**都红** ——
       ⛔ 它是"这份名单已核对过"的意思，不是"允许少做"的意思。
    """
    html = _index()
    views = dict(sorted(set(re.findall(r"\['(m\d+)','([^']+)','[^']+'\]", html))))
    assert len(views) >= 14, f"导航只解析出 {len(views)} 个视图 —— 解析大概失效了"
    slices = _view_slices(html)

    no_entry, missing_note, exempt_ok, wrongly_listed = [], [], [], []
    for k in views:
        has_entry = bool(re.search(r'data-act="exp\w*"', slices.get(k, "")))
        if k in NON_DATA_VIEWS:
            if has_entry:
                wrongly_listed.append(k)     # 非数据页**忽然有了导出入口** ⇒ 口径变了，要同步名单
            continue
        if has_entry:
            continue                          # ① 数据页有入口 ⇒ 闭合
        if re.search(r"不单独[^\"<]{0,40}导出[^\"<]{0,60}", slices.get(k, "")):
            exempt_ok.append(k)               # ② 有「说明去处」⇒ 按除外条件闭合
        else:
            no_entry.append(k)                # ⇒ **新缺口**（数据页、既没入口也没说明）

    assert not no_entry, (
        "这些**数据页既没有导出入口、也没有『不单独导出』的说明**（且不在非数据页名单里）⇒ 新缺口：\n  "
        + "\n  ".join(sorted(no_entry))
        + "\n  ⇒ 要么加导出入口，要么在页面上写明去处（claim 的除外条件要求「说明去处」）。")
    assert not wrongly_listed, (
        f"{sorted(wrongly_listed)} 在**非数据页**名单里，却有了导出入口 ⇒ 口径变了："
        "要么把它从名单里撤下来（那就是数据页，按 ① 走），要么说明为什么非数据页也要导出。")

    # ⭐ 豁免的页**必须真的在页面上写了去处**（⛔ 空挂一个名单不算）
    for k in EXPORT_EXEMPT:
        assert k in exempt_ok, f"{k} 声明了豁免，但页面上找不到『不单独导出』的说明"


__all__ = ["NON_DATA_VIEWS", "EXPORT_EXEMPT"]
