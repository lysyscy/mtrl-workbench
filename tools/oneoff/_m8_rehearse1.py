"""M8 本机预演 **第 1 步**（空库迁移）＋ 顺手订正一处**文档错址**。

## 一、订正：`.env` 在**仓根**，不在 `backend/`

实测（2026-09-29）：`backend/app/core/config.py:19` = `ENV_FILE: Path = PROJECT_ROOT / ".env"`，
且根 `.env` 的键名已列（`DATABASE_URL` / `TEST_DATABASE_URL` / `PRD_ACCEPTANCE_BASELINE` / `I8_*` / `PRINTER_NAME` …
⇒ ⚠️ **没有 `backend/.env` 这个文件**）。⇒ 我先前在 `docs/deployment.md` 与 `ops/deploy_restore.ps1` 里写的
「后端的 `.env`」**指错了地方** ✗ ⇒ 全量改成「**仓根 `.env`**」（目标机落地时会照着找 ⇒ 指错就是落地即卡）。

## 二、预演第 1 步：在**测试库**上把 schema 清空、再从零迁到 head

⭐ 为什么用测试库：它**本来就是一次性的**（`ops/init_db.sql` 写明"开发库与测试库物理隔离"，pytest 会重建）。
⚠️⚠️ **安全闸**：① 只动 `TEST_DATABASE_URL` 指的那个库；② 断言它的库名**必须含 `_test`** ⇒
   否则**当场停手**（⛔ 绝不把 `DROP SCHEMA` 打到开发库上）；③ ⛔ 不碰 `.env` 文件、不碰 8000 上的现役服务。

验到的：`alembic upgrade head` 在**空库**上一路走通（＝落地最大风险）＋ 建出多少张表。

跑法：`backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_m8_rehearse1.py --check`（只看订正锚点）
      `… --write`（落订正 ＋ 跑预演）
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / ".env"
DOC = ROOT / "docs" / "deployment.md"
DEPLOY = ROOT / "ops" / "deploy_restore.ps1"

FIXES: list[tuple[Path, str, str]] = [
    (DOC, "后端的**环境配置文件**（⚠️ 该文件**不进版本库、也不进包**；所有键名见 `backend/.env.example`）",
     "**仓根 `.env`**（⚠️ 该文件**不进版本库、也不进包**；所有键名见**仓根 `.env.example`**）"),
    (DOC, "后端的**环境配置文件**（键名见 `backend/.env.example`）",
     "**仓根 `.env`**（键名见**仓根 `.env.example`**）"),
    (DOC, "`backend/.env`", "`.env`（仓根）"),
    (DEPLOY, "$envFile = Join-Path $RepoRoot 'backend\\.env'", "$envFile = Join-Path $RepoRoot '.env'   # ⚠️ 在**仓根**（不是 backend/）"),
    (DEPLOY, "缺 backend\\.env ⇒", "缺**仓根** `.env` ⇒"),
]


def read_env() -> dict[str, str]:
    d: dict[str, str] = {}
    for line in ENV.read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            d[k.strip()] = v.strip()
    return d


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    apply = a.write and not a.check

    # ---- 一、订正错址 ----
    print("一、订正 `.env` 位置（仓根，不是 backend/）")
    for i, (p, old, new) in enumerate(FIXES, 1):
        try:
            s = p.read_text(encoding="utf-8-sig")
        except FileNotFoundError:
            print(f"  ⏭ #{i} {p.name}：文件不在 ⇒ 跳过"); continue
        n = s.count(old)
        print(f"  {'✓' if n >= 1 else '⏭'} #{i} {p.name}：命中 {n} 处")
        # ⚠️ 本组锚点**全是同一个错址**（`backend/.env`）⇒ 命中多处时**全量替**是对的
        #    （2026-09-29 实测：`i8 账号` 与 `ALLOWED_IP_CIDRS` 两行措辞**完全相同** ⇒ 命中 2 处）
        if n >= 1 and apply:
            enc = "utf-8-sig" if p.suffix == ".ps1" else "utf-8"
            p.write_text(s.replace(old, new), encoding=enc, newline="")
    print("  （`n=0` 的那条说明先前已改过或措辞不同 ⇒ ⛔ 不静默当成功，已打印出来）")

    if not apply:
        print("\n🧪 --check（干跑；⛔ 未跑预演）")
        return 0

    # ---- 二、预演第 1 步 ----
    print("\n二、预演第 1 步：测试库清空 ⇒ 从零迁到 head")
    env = read_env()
    url = env.get("TEST_DATABASE_URL", "")
    if not url:
        print("  ⛔ 根 `.env` 里没有 `TEST_DATABASE_URL` ⇒ 停手"); return 2
    dbname = url.rsplit("/", 1)[-1].split("?")[0]
    print(f"  目标库 = {dbname}（⚠️ 口令已遮；只动这一个）")
    if "_test" not in dbname:
        print(f"  ⛔ 安全闸：库名 `{dbname}` 不含 `_test` ⇒ **停手**（⛔ 绝不 DROP 非测试库）"); return 2

    py = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"
    # ① 清空 schema（只连测试库）
    code = ("from sqlalchemy import create_engine, text; import os; "
            "e = create_engine(os.environ['DATABASE_URL']); "
            "c = e.connect(); c.exec_driver_sql('DROP SCHEMA public CASCADE'); "
            "c.exec_driver_sql('CREATE SCHEMA public'); c.commit(); c.close(); "
            "print('schema 已清空')")
    tmp = ROOT / "tools" / "oneoff" / "_m8_rehearse_drop.py"
    tmp.write_text(code, encoding="utf-8")
    e2 = dict(os.environ, DATABASE_URL=url)
    r = subprocess.run([str(py), "-X", "utf8", str(tmp)], cwd=str(ROOT / "backend"),
                       env=e2, capture_output=True, text=True, encoding="utf-8", errors="replace")
    print("  " + (r.stdout or r.stderr).strip().splitlines()[-1])
    if r.returncode:
        print("  ⛔ 清空失败 ⇒ 停手"); return 1

    # ② 从零迁到 head（环境变量覆盖 ⇒ 指向测试库）
    r = subprocess.run([str(py), "-m", "alembic", "upgrade", "head"], cwd=str(ROOT / "backend"),
                       env=e2, capture_output=True, text=True, encoding="utf-8", errors="replace")
    tail = [l for l in ((r.stdout or "") + (r.stderr or "")).splitlines() if l.strip()][-3:]
    print("  alembic: " + " | ".join(tail))
    if r.returncode:
        print("  ⛔ **迁移在空库上失败** —— 这正是本轮预演要炸出来的东西 ⇒ 把上面输出发我"); return 1

    # ③ 数表
    code = ("from sqlalchemy import create_engine, text; import os; "
            "e = create_engine(os.environ['DATABASE_URL']); "
            "c = e.connect(); print(c.execute(text('select count(*) from information_schema.tables "
            "where table_schema = current_schema()')).scalar()); c.close()")
    tmp.write_text(code, encoding="utf-8")
    r = subprocess.run([str(py), "-X", "utf8", str(tmp)], cwd=str(ROOT / "backend"),
                       env=e2, capture_output=True, text=True, encoding="utf-8", errors="replace")
    n = (r.stdout or "").strip().splitlines()[-1] if r.stdout else "?"
    print(f"  ✅ 空库迁移成功 ⇒ 建出 **{n}** 张表")
    tmp.unlink(missing_ok=True)
    print("\n⭐ 结论：`alembic upgrade head` 在**空库**上一路走通 ⇒ 落地时这条最大的风险已排掉。")
    print("   ⚠️ 下一步（预演第 2 步）：临时在 8001 起第二实例指向该库 ⇒ 跑 `ops\\selfcheck.ps1 -Base http://127.0.0.1:8001`。")
    print("   ⛔ 本步**不动**现役库 / 8000 现役服务；⚠️ 测试库被清空是**预期**（pytest 会重建）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
