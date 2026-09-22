# -*- coding: utf-8 -*-
"""④ 打印设置**合并进 `MOD-03`**：清幽灵值 ＋ 改交付面判词（2026-09-21 用户裁定「按建议」）。

两件事：
1. **清库里那一行 `printer_ipp_url`** —— 它已不是设置项（`SPECS` 里删了），但旧行若还在，
   就是"**看不见却能生效**"的幽灵值（打印读取路径已改成只读 `.env` ⇒ 它不再生效，但留着会误导）。
2. **改交付面判词**（`ACC-CFG-SETUP-001` 的 `criterion` ＋ `001-01`）：**四类 → 三类**连接参数，
   并注明打印机地址**不在本页**。
   ⚠️ 交付面 json 是 **CRLF** ⇒ 按原 EOL 写回（先做往返逐字节自检）。

跑法（工程根）：`backend\\.venv\\Scripts\\python.exe tools\\_apply_print_merge.py`
"""

from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "audit"))  # ⭐ `TAIL-58` 分目录
from acc_report import resolve_baseline  # noqa: E402

KEY = "printer_ipp_url"
CASE = "ACC-CFG-SETUP-001"

NEW_CRITERION = (
    "系统设置页只放「会变且与「谁的账号」无关」的连接参数（i8 服务地址 / 两个版式 ID）；"
    "取值 **库 → `.env`**、改动**留痕**；⛔ **打印机地址不在本页** —— "
    "2026-09-21 用户裁定「打印设置从 `MOD-14` 合并进 `MOD-03`」：它的入口与存储都归 `MOD-03`"
    "（见 `ACC-PAY-SETUP-001`）；i8 账号密码与开发运维参数**不上本页**"
)
NEW_001_01 = (
    "设置页列出 §7.8 的**三类**连接参数（i8 服务地址 ＋ 两个版式 ID）；"
    "⛔ **不出现** i8 账号/密码、**不出现** i8 四个接口路径、**不出现**开发运维参数；"
    "⛔ 也**不出现**打印机地址（它属 `MOD-03` 打印设置 —— 一个入口、一处存储，见 `ACC-PAY-SETUP-001`）"
)


def clean_db() -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
    from sqlalchemy import delete, select

    from app.core.db import session_scope
    from app.mod14_config.models import AppSetting

    with session_scope() as s:
        rows = list(s.execute(select(AppSetting).where(AppSetting.key == KEY)).scalars())
        if not rows:
            print(f"· 库里没有 `{KEY}` 这一行 —— 无需清理")
            return
        for r in rows:
            print(f"· 删掉幽灵值：key={r.key!r} value={r.value!r}")
        s.execute(delete(AppSetting).where(AppSetting.key == KEY))
        s.commit()
        left = list(s.execute(select(AppSetting).where(AppSetting.key == KEY)).scalars())
        print(f"· 复核：清理后该键剩 {len(left)} 行")


def patch_baseline() -> int:
    path = resolve_baseline(None)
    raw = path.read_bytes()
    data = json.loads(raw.decode("utf-8"))
    eol = "\r\n" if b"\r\n" in raw else "\n"

    def dump(obj) -> bytes:
        return json.dumps(obj, ensure_ascii=False, indent=2).replace("\n", eol).encode("utf-8")

    if dump(data) != raw:
        print("⛔ 往返**不是**逐字节一致 —— 先别改交付面")
        return 1

    case = data["cases"][CASE]
    old_c, old_p = case["criterion"], case["points"][0]["claim"]
    if old_c == NEW_CRITERION and old_p == NEW_001_01:
        print("· 交付面判词已是新文本 —— 跳过")
        return 0

    bak = path.with_name(f"_backup-print-merge-{datetime.now().strftime('%Y%m%d-%H%M')}.json")
    shutil.copy2(path, bak)
    case["criterion"] = NEW_CRITERION
    case["points"][0]["claim"] = NEW_001_01
    path.write_bytes(dump(data))
    print(f"· 判词已改（{CASE}）：criterion ＋ 001-01")
    print(f"  备份 = {bak.name} · 结尾无多余换行 = {not path.read_bytes().endswith(b'\n')}")
    return 0


def main() -> int:
    print("① 清库里的幽灵值")
    clean_db()
    print("② 改交付面判词（四类 → 三类）")
    return patch_baseline()


if __name__ == "__main__":
    raise SystemExit(main())
