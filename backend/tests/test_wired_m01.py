"""`m01`（项目档案）**前端壳接线**断言（离线 · 静态）＋ `/api/m01/trails` 契约。

**为什么单独立一个文件**：`ui_parity` 只管「壳的视图切片与原型**逐行一致**」，它自己写明了
**测不了**「标了已接后端、其实没接」。本文件补的正是那一条。

⚠️ **本文件测不了什么（别误当已覆盖）**：这些是**静态检查** —— 壳里有没有那些接线点，
   **不证明运行时真的调通**。运行时那一段由 `tools/probe/_e2e_m01_wired.py`（真机 ＋ **真库**、跑完清理）覆盖。
   ⇒ 两把都要：这正是「**判据绿 ≠ 链路对**」的教训。

⭐ 其中三条是**反向**断言（"不许再出现"）：前端**不得自己算**状态不变式、
   不得再用本地赋值冒充落库、不得对没接的动作**假装成功** —— 判定与落库只许有一个出口（后端）。
"""

from __future__ import annotations

from pathlib import Path




# --------------------------------------------------------------- 接线点（正向）












# --------------------------------------------------------------- 反向（不许再出现）








# --------------------------------------------------- 链路 B「人工指认」（`TAIL-30`-③）








# --------------------------------------------------------------- 端点契约






def test_trails端点存在且limit有边界():
    """`GET /api/m01/trails`：存在、且 `limit` 有下上界（越界由 FastAPI 直接 422，不连库）。"""
    from fastapi.testclient import TestClient

    from app.main import create_app
    from app.mod01_projects.router import router as mod01_router

    routes = {(r.path, tuple(sorted(r.methods))) for r in mod01_router.routes}
    assert ("/api/m01/trails", ("GET",)) in routes

    client = TestClient(create_app(), raise_server_exceptions=False)
    assert client.get("/api/m01/trails?limit=0").status_code == 422
    assert client.get("/api/m01/trails?limit=999").status_code == 422
