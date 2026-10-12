"""TAIL-313 已审核90条日期的单次修正/恢复；须先迁移并获准重启服务。"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))


class SnapshotMismatch(AssertionError):
    """可安全落盘的身份/预期值差异，不包含连接或配置。"""

    def __init__(self, differences):
        self.differences = differences
        super().__init__("合同快照变化，整批拒写")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def save_json(path, obj):
    path = Path(path)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)


def verify_runtime(evidence):
    """必须有本次获准重启后的进程证据，且当前进程仍存在。"""
    import subprocess

    data = read_json(evidence)
    assert data["service"] == "mtrl-workbench-server" and data["status"] == "Running"
    assert data["restarted"] is True and data["app_status"] == 200
    assert Path(data["app_directory"]).resolve() == (ROOT / "backend").resolve()
    assert data["processes"]
    for path, digest in data["code_hashes"].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest
    assert set(data["code_hashes"]) == {"backend/app/mod11_jc/models.py", "backend/app/mod11_jc/repository.py"}
    latest_source = max((ROOT / p).stat().st_mtime for p in [
        "backend/app/mod11_jc/models.py", "backend/app/mod11_jc/repository.py"])
    for process in data["processes"]:
        pid = int(process["pid"])
        assert datetime.fromisoformat(process["started"]).timestamp() > latest_source
        command = (f"$p=Get-CimInstance Win32_Process -Filter 'ProcessId={pid}'; "
                   "if($p -and $p.CommandLine -match 'uvicorn app.main:app'){"
                   "$p.CreationDate.ToString('o')}else{exit 1}")
        result = subprocess.run(["powershell", "-NoProfile", "-Command", command], capture_output=True, text=True)
        assert result.returncode == 0
        assert datetime.fromisoformat(result.stdout.strip()) == datetime.fromisoformat(process["started"])


def write_dates(connection, before, records, *, restore=False):
    """调用方持同一事务；先锁定并核对整批，任一预期值不符即拒写。"""
    ids = sorted(r["id"] for r in records)
    assert len(ids) == len(set(ids)) == 90 and not {336, 337, 370}.intersection(ids)
    connection.execute(text("set local lock_timeout='3s'"))
    live = {r["id"]: dict(r) for r in connection.execute(text(
        "select c.*,p.warehouse_name project from jc_contract c join project p on p.id=c.project_id "
        "where c.id = any(:ids) order by c.id for update of c"), {"ids": ids}).mappings()}
    if set(live) != set(ids):
        raise SnapshotMismatch([{"id": i, "field": "record", "expected": "present", "actual": "missing"}
                                for i in ids if i not in live])
    expected = {r["id"]: r for r in before}
    assert set(expected) == set(ids)
    differences = []
    for record in records:
        row = live[record["id"]]
        for key in ["contract_no", "project_id", "project"]:
            if row[key] != record[key]:
                differences.append({"id": row["id"], "field": key, "expected": record[key], "actual": row[key]})
        for key, value in expected[row["id"]].items():
            if str(row[key]) != str(value):
                differences.append({"id": row["id"], "field": key, "expected": value, "actual": row[key]})
        if not restore:
            for key, value in [("contract_date", record["expected_old_date"]),
                               ("updated_at", record["expected_updated_at"]), ("contract_date_locked", False)]:
                if str(row[key]) != str(value):
                    differences.append({"id": row["id"], "field": key, "expected": value, "actual": row[key]})
    if differences:
        raise SnapshotMismatch(differences)
    stamp = datetime.now()
    after = []
    for record in records:
        old = live[record["id"]]
        params = {"id": old["id"], "no": old["contract_no"], "project": old["project_id"],
                  "old_date": old["contract_date"], "old_lock": old["contract_date_locked"],
                  "old_updated": old["updated_at"], "stamp": stamp,
                  "date": record["restore_date"] if restore else record["new_date"],
                  "locked": record["restore_locked"] if restore else True}
        result = connection.execute(text(
            "update jc_contract set contract_date=:date,contract_date_locked=:locked,updated_at=:stamp "
            "where id=:id and contract_no=:no and project_id=:project and contract_date=:old_date "
            "and contract_date_locked=:old_lock and updated_at=:old_updated"), params)
        assert result.rowcount == 1, f"合同{old['id']}影响行数不符"
        after.append({**old, "contract_date": params["date"], "contract_date_locked": params["locked"], "updated_at": stamp})
    actual = [dict(r) for r in connection.execute(text(
        "select c.*,p.warehouse_name project from jc_contract c join project p on p.id=c.project_id "
        "where c.id = any(:ids) order by c.id"), {"ids": ids}).mappings()]
    wanted = {r["id"]: r for r in after}
    assert len(actual) == 90
    assert all(r == wanted[r["id"]] for r in actual), "写后镜像与预期不符"
    return actual


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["apply", "restore"])
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--runtime-evidence", type=Path, required=True)
    args = parser.parse_args()
    verify_runtime(args.runtime_evidence)
    path = args.backup / "approved-90.json"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == args.manifest_sha256
    manifest = read_json(path)
    assert manifest["database"] == "mtrl_workbench" and all(r["record_approved"] for r in manifest["records"])
    for name, digest in manifest["source_hashes"].items():
        assert hashlib.sha256((Path("D:/UserData/Desktop/系统导入测试/集采合同") / name).read_bytes()).hexdigest() == digest
    before = read_json(args.backup / "before-90.json")
    records = manifest["records"]
    receipt_path = args.backup / (args.action + "-receipt.json")
    assert not receipt_path.exists(), "已有执行回执，先核对上次结果，禁止直接重跑"
    if args.action == "restore":
        receipt = read_json(args.backup / "apply-receipt.json")
        assert receipt["state"] == "committed"
        original = {r["id"]: r for r in before}
        records = [{**r, "restore_date": original[r["id"]]["contract_date"],
                    "restore_locked": original[r["id"]].get("contract_date_locked", False)} for r in records]
        before = receipt["after"]
    from app.core.config import get_settings

    engine = create_engine(get_settings().database_url, echo=False, connect_args={"connect_timeout": 5})
    with engine.begin() as c:
        assert c.execute(text("select current_database()")).scalar_one() == "mtrl_workbench"
        assert c.execute(text("select version_num from alembic_version")).scalar_one() == "c313261012"
        # 迁移前镜像不存在该列：其明确初始值为false。
        before = [{"contract_date_locked": False, **r} for r in before]
        try:
            after = write_dates(c, before, records, restore=args.action == "restore")
        except SnapshotMismatch as exc:
            save_json(args.backup / "refused-differences.json", exc.differences)
            print(f"整批拒写：{len(exc.differences)}处差异，见私有refused-differences.json")
            raise
        receipt = {"action": args.action, "state": "prepared", "count": len(after), "before": before, "after": after,
                   "manifest_sha256": args.manifest_sha256}
        save_json(receipt_path, receipt)  # 提交前已有完整恢复镜像；prepared需人工核实提交结局。
    receipt["state"] = "committed"
    save_json(receipt_path, receipt)
    engine.dispose()
    print(f"{args.action}: committed {len(after)} records")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # 不打印连接串、异常原文或局部变量；上下文事务负责回滚。
        print(f"STOPPED: {type(exc).__name__}; 核对私有镜像与回执后再操作")
        sys.exit(1)
