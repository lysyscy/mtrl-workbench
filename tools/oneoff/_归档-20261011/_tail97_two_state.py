"""一次性件（`TAIL-97` · 2026-09-25）：存量 **「待确认」⇒「纳入台账」**（两态化的收尾）。

**为什么有它**：`TAIL-97` **取消了「待确认」这一态**（用户裁定：抓来即「纳入台账」）——
  而库里还留着当初抓取时落下的 **258 条「待确认」** ⇒ 不迁它们就是**非法值**
  （枚举 `models.TAGS` 里已经没有「待确认」了 ⇒ 界面筛选/按钮会把它当域外值）。

**迁移前先出数字影响**（用户 2026-09-25 的硬要求「迁移前把数字影响列给我看」）：
  dry-run 会打印每个库的「待确认条数 / Σ结算 / 迁移后 KPI 增量」，取数**复用现场出口**
  （`mod11_jc.service.build_list`）⇒ 与 `tools/probe/_probe_tail97_impact.py` 同一份口径。

**备份（改前，落仓侧 `.workbuddy/backups/`）**：
  ① **逐行回滚点** = 受影响行的 `(id, tag)` CSV（**精确、可直接回滚**）；
  ② **整库 `pg_dump -Fc`**（双保险；⛔ 找不到 `pg_dump.exe` 就**显式说明并跳过**，不假装有）。

⚠️ 打到**两个库**：`DATABASE_URL`（真机）＋ `TEST_DATABASE_URL`（给断言）—— 与迁移纪律一致。
⚠️ 幂等：再跑一次受影响 = 0 条（⛔ 不会重复改）。

用法（工程根）：
    backend\\.venv\\Scripts\\python.exe tools\\oneoff\\_tail97_two_state.py          # 只报（dry-run）
    backend\\.venv\\Scripts\\python.exe tools\\oneoff\\_tail97_two_state.py --apply  # 真改（先备份）
"""

from __future__ import annotations

import csv
import datetime as dt
import os
import pathlib
import subprocess
import sys
from decimal import Decimal

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import create_engine, select                             # noqa: E402
from sqlalchemy.engine import make_url                                  # noqa: E402
from sqlalchemy.orm import Session                                      # noqa: E402

from app.core.config import get_settings                                # noqa: E402
from app.mod11_jc import service as M11                                 # noqa: E402
from app.mod11_jc.models import TAG_IN, JcContract                      # noqa: E402

#: ⚠️ **历史值**，已从 `models` 删除（`TAIL-97`）—— 本件是**存量迁移**，只能写死它。
LEGACY_PENDING = "待确认"

BACKUP_DIR = ROOT / ".workbuddy" / "backups"
PG_DUMP = pathlib.Path(r"C:\Program Files\PostgreSQL\16\bin\pg_dump.exe")


def _num(x) -> str:
    return f"{Decimal(str(x or 0)).quantize(Decimal('0.01')):,.2f}"


def full_dump(tag: str) -> pathlib.Path | None:
    """整库 dump（自定义格式）—— 与"逐行回滚点"双保险。"""
    url = make_url(get_settings().database_url)
    if not PG_DUMP.exists():
        print(f"  ⚠️ 找不到 {PG_DUMP} ⇒ **整库备份跳过**（逐行回滚点仍已生成，够精确回滚）")
        return None
    out = BACKUP_DIR / f"mtrl-db-{tag}-before-tail97.dump"
    env = {**os.environ, "PGPASSWORD": url.password or ""}
    r = subprocess.run(
        [str(PG_DUMP), "-h", url.host or "127.0.0.1", "-p", str(url.port or 5432),
         "-U", url.username or "postgres", "-d", url.database or "", "-Fc", "-f", str(out)],
        env=env, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  ⛔ pg_dump 失败（rc={r.returncode}）：{r.stderr.strip()[:200]}")
        return None
    print(f"  ✅ 整库备份 → {out.name}（{out.stat().st_size / 1024:.0f} KB）")
    return out


def plan(s: Session) -> tuple[list[JcContract], dict]:
    rows = list(s.execute(select(JcContract).where(JcContract.tag == LEGACY_PENDING)).scalars())
    settle = Decimal("0.00")
    for r in M11.build_list(s)["rows"]:
        if str(r.get("tag") or "") == LEGACY_PENDING:
            settle += Decimal(str(r.get("settle") or 0))
    return rows, {"n": len(rows), "settle": settle}


def run(label: str, url: str, *, apply: bool, tag: str) -> int:
    if not url:
        print(f"\n=== {label} ===\n  ⚠️ 未配置 URL ⇒ 跳过")
        return 0
    engine = create_engine(url)
    with Session(engine) as s:
        rows, stat = plan(s)
        print(f"\n=== {label} ===")
        print(f"  待确认存量 = {stat['n']} 条 · Σ结算 = {_num(stat['settle'])}（迁移后计入集采欠款/主材累计）")
        if not rows:
            print("  ✅ 无需迁移（幂等：再跑也不会改东西）")
            return 0
        if not apply:
            return stat["n"]

        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        bak = BACKUP_DIR / f"tail97-pending-rollback-{tag}-{label}.csv"
        with bak.open("w", encoding="utf-8-sig", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["id", "contract_no", "tag_before"])
            for r in rows:
                w.writerow([int(r.id), str(r.contract_no or ""), str(r.tag or "")])
        print(f"  ✅ 逐行回滚点 → {bak.name}（{len(rows)} 行）")

        for r in rows:
            r.tag = TAG_IN
        s.commit()
        left = s.execute(select(JcContract).where(JcContract.tag == LEGACY_PENDING)).scalars().all()
        print(f"  已迁 {len(rows)} 条 ⇒ 「{TAG_IN}」✓（复核：库里还剩「{LEGACY_PENDING}」{len(left)} 条）")
        return len(rows)


def main(argv: list[str]) -> int:
    apply = "--apply" in argv
    settings = get_settings()
    tag = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    print("=" * 78)
    print(("  写入" if apply else "  DRY-RUN（只报不写）") + f" · TAIL-97 存量迁移：{LEGACY_PENDING} ⇒ {TAG_IN}")
    print("=" * 78)

    if apply:
        print("① 备份")
        full_dump(tag)

    n_main = run("主库", settings.database_url, apply=apply, tag=tag)
    n_test = run("测试库", settings.test_database_url, apply=apply, tag=tag)

    print("\n" + "-" * 78)
    if apply:
        print(f"  完成：主库 {n_main} 条 · 测试库 {n_test} 条已迁。")
    else:
        print(f"  预计影响：主库 {n_main} 条 · 测试库 {n_test} 条（加 `--apply` 才真改；改前自动备份）。")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main(sys.argv[1:]))
