"""导出产物的**进程内临时存放**（`PDF-001-04` 的新形态 · 2026-09-20）。

⭐⭐ 为什么不再落盘（用户 **2026-09-20** 口径，原文）：

> 「如果**打印**的话，不要在本地留文件；如果**导出**的话，**换成浏览器下载**吧」

旧做法 = 渲染 ⇒ 写 `artifacts/pdf/<批次>/<单号>.pdf` ⇒ 回一个路径。实测的两个毛病：

| 毛病 | 实据 |
|---|---|
| 本机**越攒越多** | 09-15 起已攒 **884 个 / 7.7MB**（用户并不知道自己在攒） |
| 那条路径**没人用** | 壳里 `m03RunBatch` **压根没读** `download_url` ⇒ 用户看到"导出完成"，然后**自己去翻目录** |

⇒ 新做法：渲染出的字节**只在内存里停一下**，等浏览器来取，取走/TTL 到期即清：

```
POST /api/m03/batch (mode=pdf)  ⇒ 渲染 ＋ 回**完整报告**（哪几张没产出、为什么 —— 禁静默）
                                  ＋ 把字节存进本模块 ⇒ 拿一个 token
GET  /api/m03/pdf/{token}       ⇒ 单张 = PDF；多张 = **打包 zip** ⇒ 流给浏览器（attachment）
```

⚠️ **为什么不"渲染完直接返回流"（一步到位）**：那会把**逐条的失败清单**丢掉 ——
   而"哪几张没产出、为什么"是硬要求（`PDF-001-05` / `001-06` 禁静默）。
   ⇒ 只能两步；两步就得有个地方**在两次请求之间存一下**，本模块就是那个地方。

⚠️ **不落盘的代价（如实说）**：**进程重启就没了**（可取回窗口 = 进程存活期 ＋ `TTL_SECONDS`）。
   可接受：用户点完导出**紧接着**就下载。真过期/重启了 ⇒ `router` 给**显式 404 ＋ 中文**，
   ⛔ 绝不静默回一个空文件 —— 空 zip 会让人以为"导出成功但没东西"，那是最难查的一类。

⚠️ 取用**不删**（`get` 是幂等的）：下载中断可以重试；清理一律交给 TTL，⛔ 不搞"取一次就销毁"
   （那种设计下"手一抖点两次"就变成"第二次报过期"，很难解释）。
"""

from __future__ import annotations

import secrets
import threading
import time
from collections.abc import Sequence

#: 产物在内存里最多停多久（秒）—— 过期即清（⛔ 不无界占内存）。
TTL_SECONDS = 15 * 60

_lock = threading.Lock()
#: `token → (存入时刻, {文件名: 字节})`
_store: dict[str, tuple[float, dict[str, bytes]]] = {}


def sweep(now: float | None = None) -> int:
    """清掉过期批次 ⇒ 返回清掉几个。

    ⚠️ 每次存取都**顺手做一次**（O(批次数)，量级极小）—— ⛔ 不起后台线程：
       那会多一个"谁负责停它"的问题，而收益只有一丁点。
    """
    t = time.time() if now is None else now
    with _lock:
        dead = [k for k, (born, _) in _store.items() if t - born > TTL_SECONDS]
        for key in dead:
            _store.pop(key, None)
    return len(dead)


def put(files: Sequence[tuple[str, bytes]]) -> str:
    """存一批产物 ⇒ **token**。⚠️ 空批次 ⇒ 回**空串**（⛔ 不造一个"取出来是空的"token）。"""
    items = [(str(name), bytes(blob)) for name, blob in (files or ()) if name and blob]
    if not items:
        return ""
    sweep()
    token = secrets.token_urlsafe(16)
    with _lock:
        _store[token] = (time.time(), dict(items))
    return token


def get(token: str) -> dict[str, bytes] | None:
    """取一批产物（**不删**，见模块头）；取不到 ⇒ `None`。"""
    sweep()
    with _lock:
        item = _store.get(str(token or ""))
    return dict(item[1]) if item else None


def clear() -> None:
    """清空（**仅供自检** —— 别的用例不该被上一批的残留串味）。"""
    with _lock:
        _store.clear()


__all__ = ["TTL_SECONDS", "sweep", "put", "get", "clear"]
