"""`tests` 侧取壳源码的**唯一出口**（转发 `tools/audit/shell_source.py` · 性能 `P4`① 读取点收敛）。

**为什么是转发而不是各读各的**：壳要拆成 `web/shell/*.js` 多件（`P4`②）——
若 26 个测试件各自 `pathlib.read_text("index.html")`，拆完就**静默**读不到接线代码。
⇒ 统一从这里取（合并后的全文 = `SHELL`）。

**为什么不做成一个模块**：`tools/` 不在测试进程的 `sys.path` 上（pytest 的 rootdir 是 `backend/`）
⇒ 本件只做一件事：把**仓根**挂进 `sys.path`，再原样转发。
（单测里 `from tests.shell_src import SHELL`，⛔ 别绕过它去读 `index.html`。）
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
# ⭐ `TAIL-58` 分目录：尺子搬进 `tools/audit/` 后，它们内部的**裸 import**（`from shell_source …`）
#    依赖"脚本所在目录在 `sys.path`"⇒ 以**包方式**导入尺子（如 `tools.audit.ui_parity`）时必须补这一条。
_TOOLS_AUDIT = _ROOT / "tools" / "audit"
if str(_TOOLS_AUDIT) not in sys.path:
    sys.path.insert(0, str(_TOOLS_AUDIT))

from tools.audit.shell_source import (  # noqa: E402
    SHELL,
    SHELL_PARTS,
    SHELL_PATH,
    part_paths,
    parts_text,
    read_shell,
)

def dl_kernel() -> str:
    """⭐ `TAIL-67`（2026-09-21）：`core.js` 里 **`dlExport` 通用件**的源码。

    为什么要有这个函数：8 处导出原本**逐字重复**「fetch → 错误分类 → blob 落盘」那段；
    抽成 `dlExport` 之后，**动作里不再有** `createObjectURL` / `.download` / `content-type` 分流
    ⇒ 那些"钉源码形态"的判据（"必须真下载" / "失败必须给人原因"）就**全部假红**了。
    ⇒ ⭐ 正确的判据是**两段拼起来看**：动作**委托** `dlExport` ＋ **内核里**真的做了那几件事。
    ⛔ 别把判据改回"动作里必须有 createObjectURL" —— 那会逼着以后**不许抽通用件**（与 `TAIL-62/67` 相反）。
    """
    text = read_shell()                       # 合并后的**全部件**（`P4`① 读取点收敛）
    i = text.find("async function dlExport")
    if i < 0:
        return ""
    j = text.find("\n}", i)
    return text[i:j + 2] if j > i else text[i:]


def with_kernel(act: str) -> str:
    """动作的源码 **＋** 它委托的 `dlExport` 内核源码 ⇒ 判据**与结构无关**。"""
    return f"{act}\n{dl_kernel()}"


def tbl_kernel() -> str:
    """⭐ `TAIL-64` P0（2026-09-24）：壳公共区里 **`TBL` 表格件**的源码。

    为什么照 `dl_kernel()` 再来一个：表外壳（`<table class="dt" data-sort …>` 那一圈）抽进 `TBL`
    之后，「切片里必须有 `data-sort-key=` 字面」这类**钉源码形态**的判据会**全部假红** ——
    2026-09-24 实测就红了 `ACC-FEE-MON-001/001-01`。
    ⇒ ⭐ 正确的判据是**两段拼起来看**：切片**委托** `TBL` ＋ **内核里**真的用 `key` 拼出 `data-sort-key`。
    ⛔ 别把判据改回「切片里必须有 `<table`」—— 那会逼着以后**不许抽通用件**（与 `TAIL-64/67` 相反）。
    """
    text = read_shell()
    i = text.find("const TBL=")
    if i < 0:
        return ""
    j = text.find("\n}", i)
    return text[i:j + 2] if j > i else text[i:]


def with_tbl(act: str) -> str:
    """切片源码 **＋** 它委托的 `TBL` 内核源码 ⇒ 判据**与结构无关**。"""
    return f"{act}\n{tbl_kernel()}"


def fbar_kernel() -> str:
    """⭐ `TAIL-64` **P4-a**（2026-09-30）：壳里 **`FBAR` 筛选栏件**的源码。

    为什么照 `tbl_kernel()` 再来一个：一根筛选栏的**外壳**（`<div class="fbar …">…</div>` 那一圈）
    抽进 `FBAR` 之后，「切片里必须有 `<div class="fbar">` 字面」这类**钉源码形态**的判据会**假红**
    （同 `P0` 实测的那次）。
    ⇒ ⭐ 正确的判据是**两段拼起来看**：切片**委托** `FBAR` ＋ **内核里**真把 `body` 拼进 `fbar` 那层。
    ⛔ 别把判据改回「切片里必须有 `<div class="fbar">`」—— 那等于宣布以后**不许抽通用件**。

    ⚠️ 与 `tbl_kernel()` 的取法**不同**：`FBAR` 是**单行**声明 ⇒ 取到**行尾**即可
       （`tbl_kernel()` 那套「找 `\\n}`」在它身上会一路吃到下一个多行函数，取出一大段无关代码）。
    """
    text = read_shell().replace("\r\n", "\n")     # 件的源码是 CRLF ⇒ 归一后再找行尾
    i = text.find("const FBAR=")
    if i < 0:
        return ""
    j = text.find("\n", i)
    return text[i:j] if j > i else text[i:]


def with_fbar(act: str) -> str:
    """切片源码 **＋** 它委托的 `FBAR` 内核源码 ⇒ 判据**与结构无关**。"""
    return f"{act}\n{fbar_kernel()}"


def pjb_kernel() -> str:
    """⭐ `TAIL-64` **P4-d-a**（2026-09-30）：壳里 **`PJB` 项目选择按钮件**的源码。

    同 `tbl_kernel()` / `fbar_kernel()` 的理由：那枚 ▾ 按钮（`pjwrap` 里那一层）抽进 `PJB` 之后，
    「切片里必须有那串手写样板」这类判据会假红。

    ⚠️ 取法与 `fbar_kernel()` **不同**：`PJB` 分**三行**拼串 ⇒ 打不到"行尾"，
       改用**结束标记** `</button>';`（那是这条语句的收尾）。
    """
    text = read_shell().replace("\r\n", "\n")
    i = text.find("const PJB=")
    if i < 0:
        return ""
    marker = "</button>';"
    j = text.find(marker, i)
    return text[i:j + len(marker)] if j > i else text[i:]


def with_pjb(act: str) -> str:
    """切片源码 **＋** 它委托的 `PJB` 内核源码 ⇒ 判据**与结构无关**。"""
    return f"{act}\n{pjb_kernel()}"


def calib_kernel() -> str:
    """⭐ `TAIL-64` **P4-c-a**（2026-09-30）：壳里 **`CALIB` 口径说明块件**的源码。

    同 `tbl_kernel()` / `fbar_kernel()` / `pjb_kernel()` 的理由：页首那个折叠块的**外壳**
    （`<details>` ＋ 标题 ＋ **条数** ＋ `<ul>` ＋ 条目外壳）抽进 `CALIB` 之后，
    「这一段的源码里必须有 `口径说明 · N 条` 字面」这类**钉源码形态**的判据会假红（那串搬进内核了）。
    ⇒ ⭐ 正确的判据是**两段拼起来看**：调用点**委托** `CALIB` ＋ **内核里**真的按条目个数出条数、
    真的把条目包成既定的外壳。⛔ 别把判据改回「切片里必须有那串字面」（＝宣布以后不许抽通用件）。

    ⚠️ 取法同 `pjb_kernel()`（用**结束标记**、不用"行尾"）—— 它是多行拼串。
    """
    text = read_shell().replace("\r\n", "\n")
    i = text.find("const CALIB=")
    if i < 0:
        return ""
    marker = "</ul></details>';"
    j = text.find(marker, i)
    return text[i:j + len(marker)] if j > i else text[i:]


def with_calib(act: str) -> str:
    """切片源码 **＋** 它委托的 `CALIB` 内核源码 ⇒ 判据**与结构无关**。"""
    return f"{act}\n{calib_kernel()}"


#: ⭐ `TAIL-64` **P4-c**：**口径说明块已收进 `CALIB` 出口的页**（`P4-c-b` 起 = 全站 **14** 块全转）。
#:    ⚠️ 它是**壳的事实**（哪几页走了出口）⇒ 住这里，判据件之间**共用一个定义**
#:    （`test_ux_numbers` 逐页核"委托 ＋ 不再裸写"；`test_ux_brief` 数"折叠出口还在不在"）。
#:    ⚠️ 再加页 / 挪页时**同批**改这里（`m12` 虽已撤页，它的切片留痕仍在 ⇒ 也在名单里）。
#: ⚠️ **2026-10-01（`TAIL-213` 甲 · 批 1）：`m03` 已撤块** —— 用户拍板「撤掉折叠的口径说明」
#:   （原话「我一次也没进去看过」）⇒ 从名单里去掉；`m03` 改成**页内默认展开的一小段**
#:   （判据 `test_wired_m03_list` 改钉"这页仍有一段口径说明、且不是收起来的折叠块"）。
#: ⚠️ **2026-10-01（`TAIL-213` 甲 · 批 2）：`m07` / `m08` / `m13` / `m14` 也已撤块**（`m03` 见批 1）。
#:    ⚠️ **订正**：批 2 动手时把「库存单据明细表」那块当成了 `m11` —— 判据当场红（`m08` 的切片里找不到调用点）
#:    ⇒ 正确的号是 **`m08`**（`m11` 那块**没动**，仍在名单里）。教训：**撤块前先按 `page_seg()` 核号**，
#:    ⛔ 别拿"我记忆里的页名"当号。
#: ⚠️⚠️ **2026-10-01（`TAIL-213` 甲 · 批 3/4）：全站 14 块**已按用户拍板撤完
#:   （`m03` → 批 1；`m07`/`m08`/`m13`/`m14` → 批 2；`m05`/`m01`/`m02`/`m09` → 批 3；`m04`/`m06`/`m11`/`m12`/`m15` → 批 4）
#:   ⇒ 名单**清空**（`CALIB` 调用点 = 0）。⛔ 收尾批（撤内核 ＋ 撤 `calib_kernel()/with_calib()` ＋
#:   改那两条判据）见计划 §15 `TAIL-213`；在那之前**别把它加回来**。
CALIB_PAGES: tuple[str, ...] = ()


def page_seg(page: str) -> str:
    """`V.<page>=` 那一段源码（**切片的定义只有一处** = `ui_parity.slices()`；⛔ 别在这儿再写一份）。

    ⚠️ 给"必须**按页**判"的断言用：全局字符串里撞到的同款写法常来自**别的页**（本仓老课）。
    """
    from tools.audit.ui_parity import slices
    seg = slices(read_shell().replace("\r\n", "\n").split("\n")).get(page)
    if seg is None:
        raise KeyError(f"壳里没有 `V.{page}=` 切片")
    return "\n".join(seg)


__all__ = ["CALIB_PAGES", "SHELL", "SHELL_PARTS", "SHELL_PATH", "calib_kernel", "dl_kernel",
           "fbar_kernel", "page_seg", "part_paths", "parts_text", "pjb_kernel", "read_shell",
           "tbl_kernel", "with_calib", "with_fbar", "with_kernel", "with_pjb", "with_tbl"]
