"""The adapter must condition a transfer write on the observed source project."""
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
import json
import logging
from threading import Lock
from typing import Protocol

import httpx
from sqlalchemy import select

from app.core.db import session_scope
from app.core.errors import ExternalServiceError
from app.core.money import to_money
from app.mod02_i8 import equipment_relay as contract
from app.mod02_i8.browser_session import StrictSessionEnded, StrictSessionStopped, StrictSessionUnavailable
from app.mod02_i8.login import I8AuthFailedError
from .common import encoded, ledger_lock, record, require
from .models import EquipmentItem, EquipmentTransfer
from .projects import ProjectRef, project_index


logger = logging.getLogger(__name__)

ISSUES = ("pending", "failed", "conflict")
UNAVAILABLE = "i8接口暂未接通，已保存本地待同步"


class Adapter(Protocol):
    def snapshot(self, code: str) -> dict | None: ...
    def save_equipment(self, data: dict) -> None: ...
    def transfer(self, code: str, expected_project: str, to_project: str) -> None: ...


@dataclass
class SyncResult:
    status: str
    message: str
    snapshot: dict | None = None
    conflict: dict | None = None


def transfer_precondition(snapshot, code, from_project, to_project, *, project_name=None, project_id=None):
    if snapshot is None:
        return SyncResult("pending", "未查到 i8 设备，调拨待同步")
    matches = (snapshot["current_project"] == (project_name or from_project) if project_id is None
               else str(snapshot.get("phid_pc")) == project_id)
    if not matches:
        local = {"code": code, "from_project": from_project, "to_project": to_project}
        return SyncResult("conflict", "i8 当前项目与本地调出项目不一致，请核对", snapshot,
                          {"snapshot": snapshot, "local": local, "from_project": from_project})
    return None


def checked_project(snapshot, project, matches=True, *, project_id=None):
    if snapshot and matches and (snapshot["current_project"] == project if project_id is None
                                 else str(snapshot.get("phid_pc")) == project_id):
        return SyncResult("synced", "已同步并核对 i8 所在项目", snapshot)
    return SyncResult("failed", "i8 写入后未核对成功，请核对后重试", snapshot)


def equipment_conflict(snapshot):
    return SyncResult("conflict", "相同编号的 i8 设备所在项目不同，请核对", snapshot)


class FormTransport(Protocol):
    def get_json(self, path: str, **kwargs) -> dict: ...
    def post_json(self, path: str, **kwargs) -> dict: ...


class SaveRejected(ValueError):
    """The form explicitly stopped before saving."""


class I8CustomFormEquipmentAdapter:
    """Inject an authorized I8Client-compatible transport and verified reference IDs."""

    LIST = "/sup/customServer/getList"
    SAVE = contract.SAVE
    ORG = contract.ORG
    ORG_NAME = "第四工程公司"
    TRANSFER_SCHEME = contract.SCHEME
    TRANSFER_REFERENCE_ORG = "3700000000000869"
    # Fixed organizational query filters observed on the sbzx list, not session data.
    CLIENT_FILTER = ("e48f570da0f71818a59e798cfa48fa57bc388a6b8519dc9d0f237f397f1fdf63"
                     "f4b6f41b8fbed0c7a9520cd37c2e728810b59c1f0f0f253c")
    QUERY_FILTER = "5e3410ab22038162"

    def __init__(self, transport: FormTransport, *, project_ids: Mapping[str, str],
                 unit_ids: Mapping[str, str] | None = None,
                 project_names: Mapping[str, str] | None = None,
                 transfer_operator: tuple[str, str] | None = None):
        self.transport = transport
        self.project_ids = project_ids
        self.project_names = project_names or {}
        self.unit_ids = unit_ids or {}
        self.transfer_operator = transfer_operator

    def _list_rows(self, business):
        rows, ids = [], set()
        total = None
        page = 0
        while True:
            body = self.transport.post_json(self.LIST, data={
                "customBusCode": business, "containerId": f"p_form_{business}_m_list",
                "clientfilter": self.CLIENT_FILTER, "queryfilter": self.QUERY_FILTER,
                "page": str(page), "start": str(len(rows)), "limit": "100",
            })
            if not isinstance(body, Mapping) or "data" not in body or "total" not in body:
                raise ValueError("i8 自定义表单列表不完整")
            try:
                count = int(body["total"])
            except (TypeError, ValueError, OverflowError) as exc:
                raise ValueError("i8 自定义表单列表条数无法核对") from exc
            batch = body["data"]
            if (not isinstance(batch, list) or count < 0 or
                    (total is not None and total != count) or body.get("success") is False
                    or body.get("Success") is False or body.get("status") not in (None, "success")):
                raise ValueError("i8 自定义表单列表不完整")
            total = count
            for row in batch:
                if not isinstance(row, Mapping) or not row.get("phid") or str(row["phid"]) in ids:
                    raise ValueError("i8 列表主键重复或缺少标识")
                if business == "sbzx" and not row.get("u_device_code"):
                    raise ValueError("i8 设备缺少编码")
                ids.add(str(row["phid"]))
                rows.append(row)
            if len(rows) == total:
                return rows
            if not batch or len(rows) > total:
                raise ValueError("i8 自定义表单列表条数不符")
            page += 1

    @staticmethod
    def _snapshot(row):
        return {key: row.get(key) for key in (
            "phid", "bill_name", "phid_pc", "phid_pc_EXName", "u_device_code",
            "u_indata", "u_yz", "u_spec", "u_msunit", "u_bz", "phid_org", "u_use_org",
            "ng_record_ver",
        )} | {"current_project": row.get("phid_pc_EXName")}

    def list_equipment(self):
        return [self._snapshot(row) for row in self._list_rows("sbzx")]

    def _equipment_row(self, code):
        matches = [row for row in self._list_rows("sbzx") if row["u_device_code"] == code]
        if len(matches) > 1:
            raise ValueError("i8 设备编码重复")
        return matches[0] if matches else None

    def lookup_by_code(self, code):
        row = self._equipment_row(code)
        return self._snapshot(row) if row is not None else None

    def _save(self, code, data):
        response = self.transport.post_json(self.SAVE, retry_expired=False, data={
            "customBusCode": code, "data": encoded(data), "billNoStatus": "1",
            "isContinue": encoded({"warn": "0", "validateWarn": "0", "checkProjOrgWarn": "0"}),
        })
        status = response.get("status")
        if status in ("validateWarn", "validateForbid", "warn", "checkProjOrgWarn") or (
                status == "error" and code != "ldzcdb"):
            raise SaveRejected("i8 未接受保存")
        phid = response.get("data")
        if status != "success" or not isinstance(phid, str) or not phid.strip():
            raise ValueError("i8 保存回执未确认成功")
        return phid

    @staticmethod
    def _form(row):
        return {"form": {"key": "phid", "modifiedRow" if row.get("phid") else "newRow": row}}

    def create_equipment(self, data):
        code, project = data["code"], data["current_project"]
        if not code or len(code) > 50:
            raise ValueError("i8 设备编码须为 1 至 50 个字符")
        original = self._equipment_row(code)
        before = self._snapshot(original) if original is not None else None
        linked_phid = data.get("current_project_phid")
        project_id = self.project_ids.get(project) if linked_phid is None else linked_phid
        project_name = self.project_names.get(project, project)
        if not project_id:
            return SyncResult("pending", "缺少 i8 项目映射，设备待同步", before)
        if before and (str(before["phid_pc"]) != project_id or
                       (linked_phid is None and before["current_project"] != project_name)):
            return equipment_conflict(before)
        purchase_date = data.get("purchase_date")
        price = data.get("purchase_price")
        row = {"u_device_code": code, "bill_name": data["name"], "phid_pc": project_id,
               "u_spec": data.get("spec"),
               "u_yz": to_money(price) if price is not None else None, "u_bz": data.get("remark"),
               "u_indata": f"{date.fromisoformat(str(purchase_date))} 00:00:00" if purchase_date else None}
        if data.get("unit"):
            unit_id = self.unit_ids.get(data["unit"])
            if not unit_id:
                return SyncResult("pending", "缺少 i8 单位映射，设备待同步", before)
            row["u_msunit"] = unit_id
        version = None
        if original is not None:
            changes = {key: value for key, value in row.items()
                       if not _field_matches(key, before.get(key), value)}
            if not changes:
                return checked_project(before, project_name, project_id=linked_phid)
            version = original.get("ng_record_ver")
            if type(version) is not int or version < 0:
                raise ValueError("i8 设备缺少有效记录版本")
            # The edit form sends the full current row, including the server version.
            form_row = original | changes | {"u_yz": row["u_yz"]}
            for key in ("u_indata", "bill_dt", "app_dt"):
                if form_row.get(key):
                    form_row[key] = form_row[key].split(" ")[0]
            if "app_dt" in form_row and form_row["app_dt"] is None:
                form_row["app_dt"] = ""
        else:
            row.update(phid_org=self.ORG, u_use_org=self.ORG)
            form_row = row
        saved_id = self._save("sbzx", {"p_form_sbzx_m": self._form(form_row)})
        after = self.lookup_by_code(code)
        matches = (
            after is not None and str(after["phid"]) == saved_id
            and (before is None or str(before["phid"]) == saved_id)
            and (version is None or (
                type(after["ng_record_ver"]) is int and after["ng_record_ver"] > version))
            and all(_field_matches(key, after.get(key), value) for key, value in row.items())
        )
        return checked_project(after, project_name, matches, project_id=linked_phid)

    def create_transfer(self, code, from_project, to_project, *, transfer_date=None, remark=None,
                        from_project_phid=None, to_project_phid=None, persist=None):
        original = self._equipment_row(code)
        before = self._snapshot(original) if original is not None else None
        source_name = self.project_names.get(from_project, from_project)
        origin = self.project_ids.get(from_project) if from_project_phid is None else from_project_phid
        stop = transfer_precondition(before, code, from_project, to_project, project_name=source_name,
                                     project_id=origin)
        if stop:
            return stop
        destination = self.project_ids.get(to_project) if to_project_phid is None else to_project_phid
        if not origin or not destination:
            return SyncResult("pending", "缺少 i8 项目映射，调拨待同步", before)
        if str(before["phid_pc"]) != origin or str(before["phid_org"]) != self.ORG:
            local = {"code": code, "from_project": from_project, "phid_pc": origin, "to_project": to_project}
            return SyncResult("conflict", "i8 调出项目主键或管理组织不一致，请核对", before,
                              {"snapshot": before, "local": local, "from_project": from_project})
        if not self.transfer_operator or not all(self.transfer_operator):
            return SyncResult("pending", "未配置当前 i8 账号的录入人，调拨待同步", before)
        if transfer_date is None:
            raise ValueError("缺少 i8 调拨日期")
        operator_id, operator_name = self.transfer_operator
        if before["current_project"]:
            source_name = before["current_project"]
        destination_name = self.project_names.get(to_project, to_project)
        header = {
            "phid_fill_psn": operator_id, "phid_fill_psn_EXName": operator_name,
            "bill_dt": date.fromisoformat(str(transfer_date)).isoformat(),
            "phid_schemeid": self.TRANSFER_SCHEME,
            "phid_org": self.ORG, "phid_org_EXName": self.ORG_NAME, "phid_pc": origin,
            "bill_no": None, "bill_name": None, "wf_flag": None, "app_status": None,
        }
        detail = {
            "rel_key1": None, "u_sbmc": before["phid"], "u_sbmc_EXName": before["bill_name"],
            "u_sbbm": code, "u_spe": before["u_spec"], "phid_pc": origin, "phid_pc_EXName": source_name,
            "u_inproj": destination, "u_inproj_EXName": destination_name, "key": None, "detail_row_no": 0,
            "imp_info": encoded({
                "SchemePhId": self.TRANSFER_SCHEME, "SSign": "p_form_sbzx_m",
                "TSign": "p_form_ldzcdb_d", "SOrgPhId": self.TRANSFER_REFERENCE_ORG,
                "STable": "p_form_sbzx_m", "SPk": "phid", "SPkValue": str(before["phid"]),
                "SName": "流动资产台账",
            }),
        }
        if before["u_msunit"]:
            detail.update(u_msuint=before["u_msunit"], u_msuint_EXName=original.get("u_msunit_EXName"))
        if original.get("u_prc") is not None:
            detail["u_prc"] = original["u_prc"]
        if remark is not None:
            detail["u_bz"] = remark
        payload = {
            "p_form_ldzcdb_m": self._form(header),
            "p_form_ldzcdb_d": {"isChanged": True, "table": {"key": "phid", "newRow": [{"row": detail}]}},
        }
        evidence = {"awaiting_readback": True, "code": code, "phid": before["phid"],
                    "to_project": to_project, "destination_id": destination, "origin_id": origin,
                    "destination_name": destination_name, "destination_linked": to_project_phid is not None,
                    "workflow_phase": "saving"}
        if persist is not None:
            persist(evidence)
        try:
            evidence["bill_phid"] = self._save("ldzcdb", payload)
        except SaveRejected:
            raise
        except Exception:
            return SyncResult("failed", "i8 调拨保存回执未知，重试时只回查", before, evidence)
        evidence["workflow_phase"] = "saved"
        if persist is not None:
            persist(evidence)
        return self.submit_transfer(evidence, persist)

    def submit_transfer(self, evidence, persist=None, *, resume=False):
        bill_phid = evidence["bill_phid"]
        if not self.transfer_operator or not all(self.transfer_operator):
            return SyncResult("pending", "未配置当前 i8 账号的录入人，调拨待送审", conflict=evidence)
        headers = {"env": "java", "accept": "application/json",
                   "gatewayauthparams": f"ldzcdb|{self.ORG}|{self.transfer_operator[0]}|ldzcdb|"}
        try:
            if resume:
                bill, = (row for row in self._list_rows("ldzcdb") if str(row["phid"]) == bill_phid)
                if str(bill.get("app_status")) != "0" or str(bill.get("wf_flag")) != "0":
                    return self.verify_transfer(evidence | {"workflow_phase": "submitting"})
                if str(bill.get("phid_pc")) != evidence["origin_id"] or str(bill.get("phid_org")) != self.ORG:
                    raise ValueError("i8 调拨单归属不一致")
            precheck = self.transport.post_json(
                contract.START_FLOW, params={"customBusCode": "ldzcdb"}, headers=headers, retry_expired=False,
                json=[{"id": bill_phid, "isContinue": "0", "impSchemeId": self.TRANSFER_SCHEME}],
            )
            if precheck.get("status") != "success" or not any(
                str(row["id"]) == bill_phid and row["passFlag"] == "1" and row["isContinue"] == "0"
                and str(row["impSchemeId"]) == self.TRANSFER_SCHEME for row in precheck["data"]
            ):
                raise ValueError("i8 调拨送审预检未通过")
            flow_info = self.transport.get_json(
                contract.FLOW_INFO, headers=headers, retry_expired=False,
                params={"biztype": "ldzcdb", "bizphid": bill_phid, "flowType": "1"},
            )
            if flow_info.get("success") is not True:
                raise ValueError("i8 未返回调拨流程")
            info = flow_info["data"]
            if info.get("hasRuningFlow") is True:
                evidence = evidence | {"workflow_phase": "submitting"}
                return self.verify_transfer(evidence)
            definition, = [row for row in info["pdlist"] if row["id"] == contract.PROCESS]
            if definition["mincommentlen"] != "0" or definition["mustsignature"] != "false":
                raise ValueError("i8 调拨流程的送审条件已变化")
            dynamic = self.transport.get_json(
                contract.DYNAMIC_INFO, headers=headers, retry_expired=False,
                params={"procDefId": contract.PROCESS, "formMetadataId": "ldzcdb",
                        "formPk": bill_phid, "orgId": "", "flowType": "1"},
            )
            branch = contract.BRANCH
            if dynamic.get("success") is not True or not any(
                row["sourceId"] == branch["sourceId"] and row["destinationId"] == branch["destActId"]
                and row["id"] == branch["transitionId"]
                for row in dynamic["data"]["dynamicInfo"]["simplyData"]["nextTrans"]
            ):
                raise ValueError("i8 调拨流程缺少项目设备员节点")
        except Exception:
            return SyncResult("pending", "i8 调拨单已保存，送审预检未通过，可重试送审", conflict=evidence)

        data = {
            "minCommentLen": 0, "needsignature": False, "pdid": contract.PROCESS,
            "hasDiagramPermission": True, "flowdesc": info.get("flowDesc") or None, "remark": "",
            "biztype": "ldzcdb", "bizphid": bill_phid, "signature": "", "dynamicNode": [branch], "orgId": None,
            "candidateUsersMap": {contract.APPROVER_NODE: [contract.APPROVER]},
            "formApproveUserId": None, "assignedApproveUsers": None, "formUrlParam": None,
        }
        evidence = evidence | {"workflow_phase": "submitting"}
        if persist is not None:
            persist(evidence)
        try:
            response = self.transport.post_json(
                contract.SUBMIT, headers=headers, retry_expired=False,
                data={"data": encoded(data), "flowType": "1"},
            )
            if response.get("success") is not True or response.get("formPluginError") is True:
                raise ValueError("i8 送审回执未确认成功")
        except Exception:
            return SyncResult("failed", "i8 调拨送审回执未知，重试时只回查", conflict=evidence)
        return self.verify_transfer(evidence)

    def verify_transfer(self, evidence):
        bill_phid = evidence.get("bill_phid")
        bill = None
        if bill_phid:
            try:
                bill = next((row for row in self._list_rows("ldzcdb") if str(row["phid"]) == bill_phid), None)
            except (ExternalServiceError, StrictSessionStopped, httpx.HTTPError, ValueError) as exc:
                logger.warning('i8 调拨单读取失败：%s', type(exc).__name__)
        try:
            after = self.lookup_by_code(evidence["code"])
        except Exception:
            after = None
        if bill_phid and (
            not bill or not bill.get("bill_no") or str(bill.get("phid_pc")) != evidence["origin_id"]
            or str(bill.get("phid_org")) != self.ORG
        ):
            return SyncResult("failed", "i8 调拨单未核对成功，重试时只回查", after, evidence)
        if evidence.get("workflow_phase"):
            if not bill:
                return SyncResult("failed", "i8 调拨单主键未确认，重试时只回查", after, evidence)
            evidence = evidence | {"bill_no": bill["bill_no"]}
            if str(bill.get("app_status")) != "1" or str(bill.get("wf_flag")) != "2":
                return SyncResult("pending", f"i8 调拨单 {bill['bill_no']} 待审核生效", after, evidence)
        same_device = after is not None and str(after["phid"]) == str(evidence["phid"])
        destination_name = evidence.get("destination_name", evidence["to_project"])
        destination_id = evidence["destination_id"]
        if (same_device and str(after["phid_pc"]) == evidence["destination_id"]
                and (evidence.get("destination_linked") or after["current_project"] == destination_name)):
            return checked_project(after, destination_name, project_id=destination_id)
        if bill and same_device and str(after["phid_pc"]) == evidence["origin_id"]:
            receipt = evidence | {"bill_no": bill["bill_no"]}
            return SyncResult("pending", f"i8 调拨单 {bill['bill_no']} 已保存，设备项目待更新", after, receipt)
        return SyncResult("failed", "i8 调拨尚未核对成功，重试时只核对所在项目", after, evidence)


def _field_matches(key, actual, wanted):
    if actual in (None, "") or wanted in (None, ""):
        return actual in (None, "") and wanted in (None, "")
    if key == "u_yz":
        return to_money(str(actual)) == to_money(wanted)
    return str(actual) == str(wanted)


def _sync_legacy(adapter, data, transfer_projects=None):
    code, project = data["code"], data["current_project"]
    snapshot = adapter.snapshot(code)
    if transfer_projects is None:
        if snapshot and snapshot["current_project"] != project:
            return equipment_conflict(snapshot)
        adapter.save_equipment(data)
    else:
        origin, project = transfer_projects
        stop = transfer_precondition(snapshot, code, origin, project)
        if stop:
            return stop
        adapter.transfer(code, origin, project)
    return checked_project(adapter.snapshot(code), project)


def i8_project(ref, projects):
    if ref.id is None:
        return ref.display(projects), None
    project = projects.get(ref.id)
    if project is None or not project.phid.strip():
        raise ValueError("关联的项目档案缺少 i8 项目标识")
    return project.disp, project.phid.strip()


def synchronize(item, projects, transfer=None, adapter: Adapter | I8CustomFormEquipmentAdapter | None = None,
                *, initial_project=None, record_transfer_progress=None):
    target = transfer if transfer is not None else item
    result = SyncResult("pending", UNAVAILABLE)
    if adapter is not None:
        try:
            if transfer is None:
                ref = initial_project or ProjectRef.from_row(item, "current_project")
                name, phid = i8_project(ref, projects)
                data = record(item) | ref.fields("current_project")
                data.update(current_project=name, current_project_phid=phid,
                            purchase_date=item.purchase_date.isoformat() if item.purchase_date else None)
                if isinstance(adapter, I8CustomFormEquipmentAdapter):
                    result = adapter.create_equipment(data)
                else:
                    result = _sync_legacy(adapter, data)
            else:
                prior = json.loads(transfer.i8_conflict_json or "{}")
                if isinstance(adapter, I8CustomFormEquipmentAdapter) and prior.get("awaiting_readback"):
                    if prior.get("workflow_phase") == "saved":
                        result = adapter.submit_transfer(prior, record_transfer_progress, resume=True)
                    else:
                        result = adapter.verify_transfer(prior)
                else:
                    origin, origin_phid = i8_project(ProjectRef.from_row(transfer, "from_project"), projects)
                    destination, destination_phid = i8_project(ProjectRef.from_row(transfer, "to_project"), projects)
                    if isinstance(adapter, I8CustomFormEquipmentAdapter):
                        result = adapter.create_transfer(item.code, origin, destination,
                                                         transfer_date=transfer.transfer_date, remark=transfer.remark,
                                                         from_project_phid=origin_phid, to_project_phid=destination_phid,
                                                         persist=record_transfer_progress)
                    else:
                        result = _sync_legacy(adapter, {"code": item.code, "current_project": destination},
                                              (origin, destination))
            item.i8_snapshot_json = encoded(result.snapshot) if result.snapshot is not None else None
            if transfer is not None:
                transfer.i8_conflict_json = encoded(result.conflict) if result.conflict else None
        except (I8AuthFailedError, StrictSessionEnded, StrictSessionStopped, StrictSessionUnavailable):
            result = SyncResult("pending", "i8 会话已失效，已保存本地待同步")
        except SaveRejected:
            if transfer is not None:
                transfer.i8_conflict_json = None
            result = SyncResult("failed", "i8 未接受保存，可核对后重试")
        except Exception:
            result = SyncResult("failed", "i8 同步失败，已保存本地，可重新核对同步")
    target.i8_sync_status, target.i8_sync_message = result.status, result.message
    return receipt(target)


# Concurrent requests in the API worker must not replay the same equipment queue.
_sync_locks = tuple(Lock() for _ in range(64))


def receipt(row):
    return {"id": row.id, "status": row.i8_sync_status, "message": row.i8_sync_message}


def transfer_awaiting_readback(row):
    return json.loads(row.i8_conflict_json or "{}").get("awaiting_readback", False)


def sync_lock(key):
    return _sync_locks[key % len(_sync_locks)]


def i8_scope(item):
    return (item.item_category == "equipment") & (item.asset_scope == "current_asset")


def sync_queue(key, adapter):
    with sync_lock(key):
        return _drain(key, adapter)


def _drain(key, adapter):
    with session_scope() as db:
        item = require(db, EquipmentItem, key)
        if not i8_scope(item):
            return {"equipment": [], "transfers": []}
        pending = db.scalars(select(EquipmentTransfer).where(
            EquipmentTransfer.equipment_id == key, EquipmentTransfer.i8_sync_status.in_(ISSUES)
        ).order_by(EquipmentTransfer.transfer_date, EquipmentTransfer.id)).all()
        projects = project_index(db) if adapter is not None else {}
        # The first outstanding transfer retains the project before the local move.
        revision = item.updated_at
        db.expunge_all()
    equipment, transfers = [], []
    if item.i8_sync_status in ISSUES:
        origin = ProjectRef.from_row(pending[0], "from_project") if pending else None
        equipment.append(synchronize(item, projects, adapter=adapter, initial_project=origin))
        with session_scope() as db:
            ledger_lock(db)
            saved = require(db, EquipmentItem, key)
            if saved.updated_at != revision:
                # A newer local edit owns the pending status.
                return {"equipment": [receipt(saved)], "transfers": [receipt(r) for r in pending]}
            saved.i8_snapshot_json = item.i8_snapshot_json
            saved.i8_sync_status, saved.i8_sync_message = item.i8_sync_status, item.i8_sync_message
        if item.i8_sync_status != "synced":
            return {"equipment": equipment, "transfers": [receipt(r) for r in pending]}
    for index, row in enumerate(pending):
        result = _sync_transfer(item, projects, row, adapter)
        transfers.append(result)
        if result["status"] != "synced":
            transfers.extend(receipt(r) for r in pending[index + 1:])
            break
    return {"equipment": equipment, "transfers": transfers}


def _sync_transfer(item, projects, row, adapter):
    expected = row.i8_conflict_json

    def reserve(evidence):
        nonlocal expected
        # Commit each phase before its remote write so recovery can tell what may have been sent.
        intent = encoded(evidence)
        with session_scope() as db:
            ledger_lock(db)
            saved = require(db, EquipmentTransfer, row.id)
            prior = json.loads(expected or "{}")
            allowed_from = {"saving": None, "saved": "saving", "submitting": "saved"}
            if (saved.i8_sync_status not in ISSUES or saved.i8_conflict_json != expected
                    or prior.get("workflow_phase") != allowed_from[evidence["workflow_phase"]]
                    or (not prior.get("workflow_phase") and prior.get("awaiting_readback"))):
                raise RuntimeError("i8 调拨同步状态已变化")
            saved.i8_conflict_json = intent
            saved.i8_sync_message = "i8 调拨结果待核对"
        expected = row.i8_conflict_json = intent

    result = synchronize(item, projects, row, adapter, record_transfer_progress=reserve)
    with session_scope() as db:
        ledger_lock(db)
        saved = require(db, EquipmentTransfer, row.id)
        if saved.i8_sync_status not in ISSUES or saved.i8_conflict_json != expected:
            return receipt(saved)
        saved.i8_sync_status, saved.i8_sync_message = row.i8_sync_status, row.i8_sync_message
        saved.i8_conflict_json = row.i8_conflict_json
        require(db, EquipmentItem, item.id).i8_snapshot_json = item.i8_snapshot_json
    return result
