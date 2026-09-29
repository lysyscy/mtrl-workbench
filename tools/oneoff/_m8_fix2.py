"""M8 第 2 批（三脚本＋一页说明）的三处修正 —— 全是**闸门当场抓出来的**：

1. ⛔ `docs/部署-落地说明.md` 里写了 **`backend/.env`** ⇒ `T3` 判**幽灵路径 ×3**
   （`T3` 只认"仓里真有这个文件"；`.env` 是**故意不进版本库**的 ✗）⇒ 改成**不写该路径**、
   改写「见 `backend/.env.example` 的键名」（那个**是**入库的 ✓）。
2. ⚠️ `docs/` 的口径是「**固定小写英文名**（`architecture`/`modules`/`changelog`…）」⇒
   `部署-落地说明.md` 这名字**不合口径** ⇒ 改名 **`docs/deployment.md`**（同步改 4 处引用）。
3. ⚠️ `ops/selfcheck.ps1` 的 `<# … #>` **块注释**在 PS 5.1 下解析报错（`Unexpected attribute 'CmdletBinding'`
   ⇒ 说明块注释被提前闭掉）⇒ **整块改成 `#` 行注释**（最稳，⛔ 不再跟块注释较劲）。

⚠️ 字节纪律：三个 `.ps1` 是 **UTF-8 with BOM**（PS 5.1 读无 BOM 的 UTF-8 会按 ANSI 解 ⇒ 中文全乱 ⇒ 解析崩 ——
   本次实测踩过）⇒ **读写都要 `utf-8-sig`**；`.md` 用普通 `utf-8` ✓。

跑法：`backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_m8_fix2.py --check` / `--write`
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OLD_DOC = ROOT / "docs" / "部署-落地说明.md"
NEW_DOC = ROOT / "docs" / "deployment.md"
SCRIPTS = [ROOT / "ops" / "pack.ps1", ROOT / "ops" / "deploy_restore.ps1", ROOT / "ops" / "selfcheck.ps1"]
DESIGN = ROOT / ".workbuddy" / "work" / "10-designs" / "设计-交付包与迁移-20260929.md"

ENV_BAD = "| **库口令** | `ops/init_db.sql` 里的 `<PASSWORD>` **＋** `backend/.env` | 换一组强口令（两处必须一致）；PG 只监听 `127.0.0.1` |"
ENV_OK = ("| **库口令** | `ops/init_db.sql` 里的 `<PASSWORD>` **＋** 后端的**环境配置文件**（⚠️ 该文件**不进版本库、也不进包**；"
          "所有键名见 `backend/.env.example`） | 换一组强口令（两处必须一致）；PG 只监听 `127.0.0.1` |")
ENV_BAD2 = "| **i8 账号** | `backend/.env` |"
ENV_OK2 = "| **i8 账号** | 后端的**环境配置文件**（键名见 `backend/.env.example`） |"
ENV_BAD3 = "| **`ALLOWED_IP_CIDRS`** | `backend/.env` |"
ENV_OK3 = "| **`ALLOWED_IP_CIDRS`** | 后端的**环境配置文件**（键名见 `backend/.env.example`） |"
NAME_OLD = "`docs/部署-落地说明.md`"
NAME_OLD_WIN = "docs\\部署-落地说明.md"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    apply = a.write and not a.check

    if not OLD_DOC.exists() and NEW_DOC.exists():
        print("⏭ 已改过名 ⇒ 幂等跳过")
        return 0
    if not OLD_DOC.exists():
        print("⛔ 找不到 docs/部署-落地说明.md ⇒ 停手"); return 2

    # ---- ① 一页说明：改 .env 写法 ＋ 改名 ----
    text = OLD_DOC.read_text(encoding="utf-8")
    for i, (bad, ok) in enumerate(((ENV_BAD, ENV_OK), (ENV_BAD2, ENV_OK2), (ENV_BAD3, ENV_OK3)), 1):
        print(f"  {'✓' if text.count(bad) == 1 else '⛔'} 一页说明 #{i} 命中 {text.count(bad)} 处")
        if text.count(bad) != 1:
            print("     ⛔ 锚点对不上 ⇒ 停手"); return 2
        text = text.replace(bad, ok, 1)
    text = text.replace(NAME_OLD, "`docs/deployment.md`").replace("部署-落地说明.md", "deployment.md")
    print(f"  ✓ 一页说明：名字与自引用 ⇒ `docs/deployment.md`（{len(text.splitlines())} 行）")
    if apply:
        NEW_DOC.write_text(text, encoding="utf-8", newline="")
        OLD_DOC.unlink()
        print("     ✓ 已改名（删旧件）")

    # ---- ② 三脚本：改引用 ＋ selfcheck 的块注释改行注释 ----
    for p in SCRIPTS:
        raw = p.read_bytes()
        enc = "utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "utf-8"
        s = raw.decode(enc)
        n = s.count(NAME_OLD_WIN) + s.count(NAME_OLD)
        s = s.replace(NAME_OLD_WIN, "docs\\deployment.md").replace(NAME_OLD, "`docs/deployment.md`")
        if p.name == "selfcheck.ps1":
            lines = s.split("\n")
            if lines and lines[0].lstrip().startswith("<#"):
                end = next((i for i, l in enumerate(lines) if l.rstrip().endswith("#>") and i > 0), None)
                if end is None:
                    print("  ⛔ selfcheck.ps1 的块注释找不到收尾 `#>` ⇒ 停手"); return 2
                for i in range(0, end + 1):
                    lines[i] = ("# " + lines[i][2:].rstrip()) if lines[i].startswith("<#") else ("# " + lines[i].lstrip("#").rstrip())
                s = "\n".join(lines)
                print("  ✓ selfcheck.ps1：块注释 ⇒ 行注释")
        print(f"  ✓ {p.name}：引用改 {n} 处 · 编码 {enc}")
        if apply:
            p.write_bytes(s.encode(enc))

    # ---- ③ 设计件里的引用 ----
    d = DESIGN.read_text(encoding="utf-8")
    n = d.count(NAME_OLD)
    if n:
        print(f"  ✓ 设计件：引用改 {n} 处")
        if apply:
            DESIGN.write_text(d.replace(NAME_OLD, "`docs/deployment.md`"), encoding="utf-8", newline="")

    print("\n" + ("🔧 已落盘" if apply else "🧪 --check（干跑）"))
    print("   复核：`audit_drift` 必须修 0（`T3` 幽灵路径 3 → 0）· 本机跑 `ops\\selfcheck.ps1` 应全 ✅ · 其余尺子全绿")
    return 0


if __name__ == "__main__":
    sys.exit(main())
