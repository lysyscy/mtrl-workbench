"""从 backend 运行 python -m app.mod16_equipment.cli；默认只解析，不连接数据库。"""
import argparse
import json
from pathlib import Path

from app.core.db import session_scope
from .importer import import_equipment_baseline


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for ledger in ("distribution", "inventory", "rental"):
        parser.add_argument(f"--{ledger}-path", type=Path, required=True)
    parser.add_argument("--rental-month", default="2026-11")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="写入当前配置数据库，要求设备三账均为空")
    mode.add_argument("--dry-run", action="store_true", help="只读解析并核对汇总（默认）")
    args = vars(parser.parse_args())
    apply = args.pop("apply")
    args["dry_run"] = not apply
    if apply:
        with session_scope() as db:
            result = import_equipment_baseline(db, **args)
    else:
        result = import_equipment_baseline(None, **args)
    print(json.dumps(result, default=str, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
