#!/usr/bin/env python
"""「抓取导出分开」三处改造（重写版：每个调用都带 tag；已应用的自动跳过）。"""
from __future__ import annotations

import pathlib
import re
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(r"D:\dev\mtrl-workbench")
BAK = ROOT / ".workbuddy" / "scratch"
BAK.mkdir(parents=True, exist_ok=True)


def patch(p, old, new, tag):
    t = p.read_text(encoding="utf-8", errors="replace")
    if old not in t:
        print(f"·  {p.name}: 跳过（已应用或无锚点）⇒ {tag}")
        return
    shutil.copy2(p, BAK / (p.name + ".bak-split"))
    p.write_text(t.replace(old, new, 1), encoding="utf-8", newline="")
    print(f"✅ {p.name}: {tag}")


FETCH = ROOT / "backend/app/mod08_inv/fetch_service.py"
SERVICE = ROOT / "backend/app/report_export/service.py"
ROUTER = ROOT / "backend/app/mod08_inv/router.py"

patch(FETCH,
      "        rows = importer.parse_rows(content)",
      "        try:                                   # ⭐ 2026-09-21 用户裁定「抓取导出分开」：\n"
      "            source_cache.save(SPEC_KEY, plan[\"ym\"], content)   # 源文件按月存档 ⇒\n"
      "        except OSError as cache_exc:           # 「含透视导出」只读这份缓存（⛔ 不再现场登 i8）。\n"
      "            logger.warning(\"i8 源文件存档失败（不影响抓取）：%s\", cache_exc)\n"
      "        rows = importer.parse_rows(content)",
      "① run_fetch 存档源文件")

patch(SERVICE,
      "def export_inventory(session: Session, period: str, *, export_bytes=None,\n"
      "                     allow_kick: bool = False) -> Path:",
      "def export_inventory(session: Session, period: str, *, export_bytes=None) -> Path:",
      "② export_inventory 删 allow_kick")

patch(SERVICE,
      "    - **src 来源 = HTTP 现导**（`mod02_i8.report_export.export`，`spec_key=\"inv\"`）\n"
      "      —— 照素材包 `app/export_runner.py::run_once()` 的 kcdj 分支。",
      "    - **src 来源 = 最近一次抓取的源文件缓存**（`mod02_i8.source_cache`；2026-09-21 用户裁定\n"
      "      「抓取导出分开」—— 抓取时把 i8 源文件按月存档，导出**只读缓存**，⛔ 不再现场登 i8：\n"
      "      与 `m07` 同一套心智，「抓取」是全站唯一碰 i8 的动作）。缓存没有 ⇒ **显式报「请先抓取」**。",
      "② export_inventory docstring")

patch(SERVICE,
      "    `export_bytes` 仅**测试注入**用（离线驱动成品生成、**不连 i8**）；缺省走真机现导。\n"
      "    `allow_kick` 透传给 `I8Client`（**默认 `False`** —— D9：强踢只能由界面二次确认后显式授权）。",
      "    `export_bytes` 仅**测试注入**用（离线驱动成品生成、**不连 i8**）；缺省读源文件缓存。",
      "② export_inventory docstring 2")

patch(SERVICE,
      "    content = (export_bytes() if export_bytes is not None\n"
      "               else _fetch_inventory_bytes(session, ym, allow_kick=allow_kick))",
      "    content = (export_bytes() if export_bytes is not None\n"
      "               else source_cache.load(\"inv\", ym))\n"
      "    if content is None:\n"
      "        raise MustReportError(\n"
      "            f\"{period_label(ym)} 的 i8 源文件不在本地 —— 请先在「库存单据」页抓取一次\"\n"
      "            \"（含透视导出用的是最近一次抓取的源文件，⛔ 不现场登 i8）。\")",
      "② export_inventory 读缓存")

# 删现导包装 `_fetch_inventory_bytes`（函数体到下一个顶层 def 之前）
t = SERVICE.read_text(encoding="utf-8", errors="replace")
m = re.search(r"\ndef _fetch_inventory_bytes\(.*?\n(?=\ndef )", t, re.S)
if m:
    t = t.replace(m.group(0), "\n", 1)
    SERVICE.write_text(t, encoding="utf-8", newline="")
    print("✅ service: 删 `_fetch_inventory_bytes`")

patch(ROUTER,
      "    request: Request,\n    allow_kick: bool = Query(\n"
      "        False, description=\"⭐ 须用户在界面二次确认后才为 true（D9：强踢该账号其他在线会话）\"\n    ),\n):",
      "    request: Request,\n):",
      "③ router 端点删 allow_kick")

patch(ROUTER,
      "    - ⭐ **`allow_kick`**（query，**默认 `false`**）透传给 `I8Client`：cookie 有效 / **命中磁盘缓存**时\n"
      "      **不重登、不顶号**；仅当缓存与登录都拿不到可用会话、且**界面已二次确认**时才允许强踢（D9）。\n"
      "      ⛔ **绝不擅自踢人** —— 不传即 `false`。⚠️ 本轮只把该能力备好，**壳侧交互不改**（后续再定）。\n",
      "    - ⭐ 2026-09-21 用户裁定「抓取导出分开」：src = **最近一次抓取的源文件缓存**（`source_cache`），\n"
      "      **导出不碰 i8** ⇒ 不再有 `allow_kick`（D9 的二次确认都在「抓取」侧）。缺缓存 ⇒ 中文报「请先抓取」。\n",
      "③ router docstring")

patch(ROUTER,
      "            path = EX.export_inventory(s, period, allow_kick=allow_kick)",
      "            path = EX.export_inventory(s, period)",
      "③ router 调用")
print("完成")
