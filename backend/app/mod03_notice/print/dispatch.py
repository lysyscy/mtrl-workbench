"""出纸**通道分流**（`TAIL-46`-②）—— 打印投递的**唯一出口**。

口径照用户调好的 `i8一键打印_新版`（2026-09-18 用户亲测）：

| 通道 | 怎么出纸 | 什么时候用 |
|---|---|---|
| `auto` | 依次试 **IPP → 系统驱动 → RAW 9100** | 默认；换打印机不用先知道它的脾气 |
| `ipp` | 标准方式（`ipp://`，走 HTTP 传输） | 打印机自己能解释 PDF（Ricoh IM 3000 走这条） |
| `driver` | 交 **Windows 打印驱动** | **最稳**；有的打印机没有 PDF 解释器，只认位图格式 |
| `raw` | 整卷发到 `host:9100` | ⚠️ 只对"自己能读 PDF"的打印机有意义；多数小型机会打出**乱码** |

⭐⭐ 两条硬规矩（都是实测教训换来的）：
1. **绝不重复出纸**：某一档回了「已投递（未核实）」就**停住** —— 那句话的意思是"**可能已经打了**"，
   ⛔ 不许再往下试一档（否则同一张纸打两遍）。往下试**只允许**发生在"**明确报错**"时。
2. **失败要带全每一档的理由**（`001-08`）：全失败时逐档列出原因 —— 只给一句"打印失败"，
   现场无从下手（2026-09-16 实测：只看到 `0x0400` 时完全不知道是 document-format 被拒）。

⚠️ 本模块**不碰浏览器内核对、不碰排版**（那是 `render.py` 的活）；只负责"这本 PDF 怎么送到打印机那儿"。
"""

from __future__ import annotations

import importlib
import os
import re
import socket
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable

from app.core.config import effective_of, get_settings
from app.core.errors import MustReportError
from app.mod03_notice.print.ipp import send_pdf
from app.mod03_notice.settings_store import MODE_LABEL, validate_print_mode

#: ⭐ `auto` 的试法顺序 —— 口径照 `i8一键打印_新版`（⛔ 别改顺序：先标准、再驱动、最后 RAW）
AUTO_ORDER: tuple[str, ...] = ("ipp", "driver", "raw")

_RAW_PORT = 9100  # ⚠️ RAW 的标准端口；地址里那个端口（如 631）是 **IPP** 用的，两者不是一回事
_URI_HOST_RE = re.compile(r"^(?:ipp|ipps|https?|raw)://([^/\s:@]+)", re.IGNORECASE)

# ---------------------------------------------------------------- 打印落地件（`driver` 通道）
#: ⭐⭐ 用户 **2026-09-20** 口径：「**如果打印的话，不要在本地留文件**」。
#:   本来只有 `driver` 通道会在 `%TEMP%` 落一份 PDF（`ipp` / `raw` 是**整卷发字节**、零文件）。
#: ⚠️⚠️ **不能写完就删**：Windows 驱动是**异步**读盘的，删早了会印出**空白件**（2026-09 实测教训）。
#:   ⇒ 两条一起上：① **到点自删**（`_TMP_KEEP_SECONDS`）；② **下次打印前扫一遍**兜底
#:   （进程被杀 / 崩溃时定时器没机会跑，靠这个收尾）。
_TMP_KEEP_SECONDS = 90.0
_TMP_PREFIX = "m03print_"


def sweep_temp_files(now: float | None = None) -> int:
    """清掉**上次遗留**的打印落地件 ⇒ 返回清掉几个。

    ⚠️ 只按**时间**判（⛔ 绝不删"刚建的那份"）—— 那可能正是驱动在读的。
    ⚠️ 这是**兜底**，不是常规路（常规路是 `_drop_later` 的定时删除）。
    """
    t = time.time() if now is None else now
    dropped = 0
    for path in Path(tempfile.gettempdir()).glob(f"{_TMP_PREFIX}*.pdf"):
        try:
            if t - path.stat().st_mtime > _TMP_KEEP_SECONDS:
                path.unlink(missing_ok=True)
                dropped += 1
        except OSError:                                  # noqa: PERF203 —— 单个删不掉不影响别的
            continue
    return dropped


def _drop_later(path: str, delay: float | None = None) -> None:
    """到点自删（⚠️ 驱动异步读盘 ⇒ **不能立刻删**，见 `_TMP_KEEP_SECONDS` 那段）。

    ⚠️ `delay` 的默认值**不能在形参上写 `=_TMP_KEEP_SECONDS`** —— 那是**定义时**求值，
       自检改不动它（`monkeypatch` 模块常量无效）；这里改成**调用时**取。
    ⚠️ 在**写完文件之后马上**调（⛔ 不是"投递成功之后"）：这样连
       `ShellExecute` / `startfile` **抛异常**那条路也覆盖得到（否则那份文件会永久留下）。
    ⚠️ `daemon=True` —— ⛔ 不许这个定时器把进程退出拖住。
    """
    wait = _TMP_KEEP_SECONDS if delay is None else delay
    timer = threading.Timer(wait, lambda: Path(path).unlink(missing_ok=True))
    timer.daemon = True
    timer.start()


def _stage_pdf(pdf: bytes) -> str:
    """把 PDF 落成一份**待自删**的临时件 ⇒ 返回路径（**`driver` 通道唯一的落盘处**）。

    ⭐ 抽成独立函数是为了**可测**：`send_driver` 会**真出纸**，⛔ 自检绝不能调它；
       而"写完就排上自删"这件事必须被钉住 —— 否则「打印不留文件」只是一句空话。
    """
    sweep_temp_files()                                    # 顺手收上次的尾（⛔ 不碰"刚建的那份"）
    fd, path = tempfile.mkstemp(suffix=".pdf", prefix=_TMP_PREFIX)
    with os.fdopen(fd, "wb") as handle:
        handle.write(pdf)
    _drop_later(path)                                     # ⭐ 写完就排上自删（异常路径也覆盖）
    return path


def raw_target(printer_uri: str) -> tuple[str, int]:
    """打印机地址 → RAW 投递目标 `(host, 9100)`。

    ⚠️ **端口固定 9100**：地址里写的端口（`ipp://host:631/…`）是 **IPP** 用的 —— 照抄到 RAW
       等于投错门（631 上没人听 RAW）。
    """
    m = _URI_HOST_RE.match(str(printer_uri or "").strip())
    if not m:
        raise MustReportError(
            f"打印机地址看不懂：「{printer_uri}」"
            "（RAW 通道要能从中取出 IP —— 应形如 ipp://192.168.5.248）"
        )
    return m.group(1), _RAW_PORT


def send_raw(pdf: bytes, printer_uri: str) -> str:
    """整卷发到 `host:9100` → 返回"投递说明"。

    ⚠️ RAW **没有任何回执**（发完即断连）⇒ 只能如实说「已投递（未核实）」：
       ⛔ 不许谎报"打完了"，也⛔ **不算失败**（用户 2026-09-18 实测教训：假失败 ⇒ 人会重复打、白浪费纸）。
    """
    host, port = raw_target(printer_uri)
    try:
        with socket.create_connection((host, port), timeout=10.0) as sock:
            sock.sendall(pdf)
    except OSError as exc:
        raise MustReportError(
            f"RAW 投递失败（{host}:{port}）—— {type(exc).__name__}: {exc}"
            "（有的打印机根本没开 9100 这个口）"
        ) from exc
    return (
        f"已投递（未核实）—— 已按 RAW {host}:{port} 整卷发完（这个通道没有回执）；"
        f"⚠️ 若打出乱码 ⇒ 这台打印机不认 PDF，请把出纸通道改成「{MODE_LABEL['driver']}」"
    )


def list_printers() -> list[str]:
    """本机装了驱动的打印机名（设置弹窗给「系统驱动」通道选 —— 名字要**一字不差**）。

    ⚠️ 拿不到就回空表：这只影响"给不给提示"，⛔ 不报错、⛔ 不猜一个名字出来。
    """
    try:
        import win32print  # type: ignore
    except Exception:  # noqa: BLE001  ← 没装 pywin32 / 不是 Windows：都是"拿不到"，一样对待
        return []
    try:
        return [str(p[2]) for p in win32print.EnumPrinters(2)]
    except Exception:  # noqa: BLE001
        return []


def send_driver(pdf: bytes, printer_name: str = "") -> str:
    """交 **Windows 打印驱动**出纸 → 返回"投递说明"。

    - 有 `pywin32` ⇒ `ShellExecute("printto", …)`：**能指定**打印机名（空则交给系统默认打印机）。
    - 没有 `pywin32` ⇒ 退到 `os.startfile(…, "print")`：**只能**打到系统默认打印机
      ⇒ 这时若用户指定了名字，**如实说清没指定上**（⛔ 不假装指定成功）。
    - ⚠️ 「交给驱动」≠「打完了」（驱动是**异步**的）⇒ 一律「已投递（未核实）」。

    ⭐ 落地的临时 PDF **到点自删**（用户 2026-09-20 口径：**打印不在本地留文件**）——
       ⚠️ 但**不能立刻删**（驱动异步读盘，删早了印空白件）⇒ 见 `_TMP_KEEP_SECONDS` 那两段：
       **到点自删** ＋ **下次打印前扫残留**。
    """
    name = str(printer_name or "").strip()
    path = _stage_pdf(pdf)

    try:
        win32api = importlib.import_module("win32api")
    except Exception:  # noqa: BLE001  ← 没装 pywin32 ⇒ 走下面那条退路
        win32api = None

    if win32api is not None:
        win32api.ShellExecute(0, "printto" if name else "print", path,
                              f'"{name}"' if name else "", ".", 0)
        to = f"「{name}」" if name else "系统默认打印机"
        return f"已投递（未核实）—— 已交系统打印驱动出纸（{to}）；出纸与否请看打印机"

    if not hasattr(os, "startfile"):
        raise MustReportError("「系统驱动」通道只在 Windows 上能用（本机不是）")
    os.startfile(path, "print")  # type: ignore[attr-defined]  # 退路：走文件关联的"打印"动词
    if name:
        return (
            f"已投递（未核实）—— 本机没有打印驱动接口（`pywin32` 未装）⇒ 已交**系统默认打印机**；"
            f"⚠️ 你设的「{name}」**没能指定上**（要指定请先装 `pywin32`）"
        )
    return "已投递（未核实）—— 已交系统默认打印机（`pywin32` 未装，走文件关联的打印动词）"


def dispatch_pdf(
    pdf: bytes,
    *,
    mode: str | None = None,
    printer_uri: str | None = None,
    printer_name: str | None = None,
    ipp: Callable[[bytes, str | None], str] | None = None,
    driver: Callable[[bytes, str], str] | None = None,
    raw: Callable[[bytes, str], str] | None = None,
) -> str:
    """投递一本 PDF（**唯一出口**）→ 返回"投递说明"（空串 = 已核实；非空 = 已投递但无法核实）。

    - 三个通道**可注入**（测试用桩 ⇒ ⛔ 自检不许碰真实打印机）。
    - `mode` / `printer_uri` / `printer_name` 留空 ⇒ 取**当前设置**（设置改完即生效，无需重启）。
    - ⭐ 见模块头那两条硬规矩（**绝不重复出纸** / **失败带全每一档的理由**）。
    """
    s = get_settings()
    name = str(printer_name if printer_name is not None else s.printer_name or "").strip()
    m = validate_print_mode(mode if mode is not None else (s.print_mode or "auto"), name)
    uri = printer_uri if printer_uri is not None else effective_of(
        "printer_ipp_url", s.printer_ipp_url
    )

    chans: dict[str, Callable[[], str]] = {
        "ipp": lambda: (ipp or send_pdf)(pdf, uri or None),
        "driver": lambda: (driver or send_driver)(pdf, name),
        "raw": lambda: (raw or send_raw)(pdf, uri),
    }

    order = list(AUTO_ORDER) if m == "auto" else [m]
    fails: list[tuple[str, str]] = []
    for ch in order:
        label = MODE_LABEL.get(ch, ch)
        try:
            note = str(chans[ch]() or "")
        except MustReportError as exc:
            fails.append((label, str(exc)))  # 真失败 ⇒ 记下理由，继续试下一档
            continue
        if not note:
            return f"自动选「{label}」：已投递（打印机已接收）" if m == "auto" else note
        # ⭐ **停住**：这句话的意思是"可能已经打了" ⇒ ⛔ 再试下一档会重复出纸
        return f"自动选「{label}」：{note}" if m == "auto" else note

    if len(order) == 1:
        raise MustReportError(f"出纸失败（{fails[0][0]} 通道）：{fails[0][1]}")
    raise MustReportError(
        "三种出纸方式都没能投递：\n"
        + "\n".join(f"· {label}：{why}" for label, why in fails)
        + "\n（可先用「只导出 PDF」确认制单本身没问题；再按上面各档的原因处理）"
    )
