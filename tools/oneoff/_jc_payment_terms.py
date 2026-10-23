"""TAIL-432 备注迁移：默认只读预览；真实回写须另获授权并提供已确认预览摘要。"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from sqlalchemy import create_engine, inspect, text
from app.core.config import get_settings
from app.mod11_jc.domain import remark_payment_proposal

FIELDS = ("payment_term", "payment_method", "remark")


def target_fingerprint(connection):
    table = connection.execute(text("SELECT n.nspname,c.relname,c.oid::text FROM pg_class c "
        "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.oid='jc_contract'::regclass")).one()
    url = connection.engine.url
    return hashlib.sha256(str((url.host, url.port, url.database, tuple(table))).encode()).hexdigest()


def snapshot(connection, *, lock=False):
    columns = {c["name"] for c in inspect(connection).get_columns("jc_contract")}
    fields = ",".join(name if name in columns else "'' AS " + name for name in FIELDS)
    return [dict(r) for r in connection.execute(text(
        "SELECT id,contract_no,project_id," + fields + " FROM jc_contract ORDER BY id" + (" FOR UPDATE" if lock else ""))).mappings()]


def proposal(rows):
    result = []
    for row in rows:
        before = {key: row[key] or "" for key in FIELDS}
        after = remark_payment_proposal(**before)
        if before != after:
            result.append({"id": row["id"], "contract_no": row["contract_no"], "project_id": row["project_id"], "before": before, "after": after})
    return result


def apply_preview(connection, preview):
    """在同一事务锁住并重新核对；任一变化即整批拒绝。"""
    live = {r["id"]: r for r in snapshot(connection, lock=True)}
    for item in preview:
        row = live.get(item["id"])
        if not row or row["contract_no"] != item["contract_no"] or row["project_id"] != item["project_id"]:
            raise ValueError("合同身份已变化，请重新生成迁移对照")
        if {key: row[key] or "" for key in FIELDS} != item["before"] or remark_payment_proposal(**item["before"]) != item["after"]:
            raise ValueError("合同约定或备注已变化，请重新生成迁移对照")
    for item in preview:
        result = connection.execute(text("UPDATE jc_contract SET payment_term=:payment_term,payment_method=:payment_method,remark=:remark WHERE id=:id"),
                                    {"id": item["id"], **item["after"]})
        if result.rowcount != 1:
            raise ValueError("迁移行数不符，整批回滚")
    return len(preview)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("preview", type=Path, help="本机预览JSON；默认创建，并同时生成可读Markdown对照")
    parser.add_argument("--apply", action="store_true", help="仅在用户明确授权真实迁移后使用")
    parser.add_argument("--confirmed-sha256", default="")
    args = parser.parse_args()
    engine = create_engine(get_settings().database_url, echo=False)
    try:
        if args.apply:
            raw = args.preview.read_bytes()
            if not args.confirmed_sha256 or hashlib.sha256(raw).hexdigest() != args.confirmed_sha256:
                raise ValueError("请提供用户已确认预览的SHA256")
            saved = json.loads(raw)
            with engine.begin() as connection:
                if saved["target"] != target_fingerprint(connection):
                    raise ValueError("数据库或合同表schema与预览不同")
                count = apply_preview(connection, saved["changes"])
            print(f"已迁移 {count} 条；事务已提交")
        else:
            with engine.connect() as connection:
                connection.execute(text("SET TRANSACTION READ ONLY"))
                target = target_fingerprint(connection)
                rows = snapshot(connection)
            changes = proposal(rows)
            args.preview.parent.mkdir(parents=True, exist_ok=True)
            with args.preview.open("x", encoding="utf-8") as output:
                json.dump({"target": target, "inspected": len(rows), "changes": changes}, output, ensure_ascii=False, indent=2)
            def cell(value):
                return str(value).replace("|", "\\|").replace("\n", "<br>")
            lines = ["# 集采备注迁移对照", "", f"只读扫描 {len(rows)} 条合同，建议迁移 {len(changes)} 条；尚未回写。保留未明确片段及已填字段。", "", "|合同ID / 合同号 / 项目ID|原备注|账期前→后|方式前→后|剩余备注|", "|---|---|---|---|---|"]
            for item in changes:
                b, a = item["before"], item["after"]
                lines.append("|" + "|".join(map(cell, [f'{item["id"]} / {item["contract_no"] or "无编号"} / {item["project_id"]}', b["remark"], b["payment_term"] + " → " + a["payment_term"], b["payment_method"] + " → " + a["payment_method"], a["remark"]])) + "|")
            args.preview.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")
            print(f"只读扫描 {len(rows)} 条；建议迁移 {len(changes)} 条；未回写")
            print("预览SHA256", hashlib.sha256(args.preview.read_bytes()).hexdigest())
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
