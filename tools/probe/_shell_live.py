"""`_shell_live` —— **㉘ 活服务与代码是不是同一份**（`TAIL-129` · 2026-09-27 用户报障逼出来的）。

⚠️⚠️ 为什么真机自检**必须**有这一条：本工程后端**没有 `--reload`**（见 `ops/server_ctl.ps1` 开篇：
   「改完 Python 代码必须重启进程，否则新端点/新逻辑一律不生效」）⇒ 改完后端**忘了重启**时：
   · 用户看到的**还是老行为**（2026-09-27 原话：「**还是没改对**」—— 截图里字段还叫「材料单据」，
     而那个名字在仓里**已经不存在了**）；
   · 而**离线判据全绿** —— pytest 是**直接 import 代码**、根本不走那个进程；真机自检若只打界面，
     界面上也看不出"后端是哪一份"。
   ⇒ 症状 = 「**用户说没修好，仓里 907 条判据说修好了**」—— 最贵的一种红（整轮返工）。

⭐ 判法（⛔ 不查操作系统、⛔ 不猜进程号、⛔ 不碰 psutil）：拿**公开只读端点**的回包，
   去比**代码里的真源** —— 活服务认得哪些导入域、每个域有哪些字段，正是这次报障的那一面。
   ⚠️ 两端只比**清单**（域名集合 / 字段标签列表），⛔ 不比分值或文案（那些天天在改，比了就是天天假红）。
"""

from __future__ import annotations

import pathlib
import sys


def _code_contract() -> dict[str, list[str]]:
    """代码里的导入域契约：`{域号: [字段标签…]}`（建一次 app ⇒ 各域 `build_router` 跑过 ⇒ 注册表填满）。"""
    root = pathlib.Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root / "backend"))
    from app.import_kit.api import REGISTRY          # noqa: PLC0415
    from app.main import create_app                  # noqa: PLC0415

    create_app()
    return {d: [f.label for f in spec.fields] for d, spec in REGISTRY.items()}


def check(errors: list[str], base: str) -> None:
    """㉘ 逐域比「活服务回的字段契约」与「代码里的声明」。"""
    try:
        import httpx
    except ImportError:                              # pragma: no cover —— 探针环境恒有它（FastAPI 依赖）
        print("㉘ 活服务与代码同一份：（跳过 · 环境没有 httpx）")
        return
    try:
        want = _code_contract()
    except Exception as exc:                         # noqa: BLE001
        errors.append(f"㉘ 读不到**代码里**的导入域契约（{type(exc).__name__}: {exc}）")
        return
    try:
        live = httpx.get(base + "/api/imp/domains", timeout=20).json()
        got = {d["domain"] for d in (live.get("domains") or [])}
    except Exception as exc:                         # noqa: BLE001
        errors.append(f"㉘ 问不到活服务的导入域清单（{type(exc).__name__}: {exc}）"
                      " —— 后端在跑吗？（`ops\\server_ctl.ps1 -Action status`）")
        return

    bad: list[str] = []
    if got != set(want):
        bad.append(f"域清单不一致：活服务 {sorted(got)} / 代码 {sorted(want)}"
                   "（最常见的成因：**改完后端没重启**，或某个域没进 `REGISTRY`）")
    for dom in sorted(got & set(want)):
        try:
            sch = httpx.get(f"{base}/api/imp/{dom}/schema", timeout=20).json()
            labels = [f.get("label") for f in (sch.get("fields") or [])]
        except Exception as exc:                     # noqa: BLE001
            bad.append(f"域 `{dom}` 的 schema 取不到（{type(exc).__name__}: {exc}）")
            continue
        if labels != want[dom]:
            bad.append(f"域 `{dom}` 的字段契约不一致：活服务 {labels} / 代码 {want[dom]}")

    if bad:
        print(f"㉘ 活服务与代码同一份：⛔ {len(bad)} 条不一致")
        for b in bad:
            print("   ❌", b)
        errors.append(
            "㉘ **活服务跑的不是仓里这份代码**（后端没有热重载 ⇒ 改完必须重启）：\n"
            + "\n".join("      " + b for b in bad)
            + "\n      ⇒ 先跑 `powershell -File ops\\server_ctl.ps1 -Action restart`，再复跑本自检"
              "（⚠️ 不重启的话，**离线判据全绿也说明不了任何事** —— 用户看到的仍是旧行为）")
    else:
        print(f"㉘ 活服务与代码同一份：✅ {len(got)} 个导入域的字段契约逐一对上"
              "（顺手挡住「改完没重启」这一整类假绿）")


__all__ = ["check"]
