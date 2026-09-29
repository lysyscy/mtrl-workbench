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


__all__ = ["SHELL", "SHELL_PARTS", "SHELL_PATH", "dl_kernel", "fbar_kernel", "part_paths",
           "parts_text", "read_shell", "tbl_kernel", "with_fbar", "with_kernel", "with_tbl"]
