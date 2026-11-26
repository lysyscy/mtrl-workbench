"""Request shapes that the equipment sync may send through the browser relay."""

import json
import re
from urllib.parse import parse_qsl, urlsplit

from app.mod02_i8.browser_session import StrictTargetMismatch


SAVE = "/sup/customServer/save"
START_FLOW = "/sup/customServer/startFlow"
FLOW_INFO = "/WorkFlow3/WorkFlow/GetStartFlowExecutionInfo"
DYNAMIC_INFO = "/WorkFlow3/WorkFlow/GetProcessDynamicInfo"
SUBMIT = "/WorkFlow3/WorkFlow/CreateProcInst"
EQUIPMENT_PATHS = frozenset({SAVE, START_FLOW, FLOW_INFO, DYNAMIC_INFO, SUBMIT})
ORG = "3700000000000014"
SCHEME = "3700000000000363"
PROCESS = "xzd_102196:2:369735"
APPROVER_NODE = "ext-gen2225"
APPROVER = "3700000000000715"
BRANCH = {"sourceId": "ext-gen1795", "transitionId": "ext-gen3164", "destActId": APPROVER_NODE}
WORKFLOW_HEADERS = frozenset({"env", "gatewayauthparams"})


def _fields(value):
    pairs = parse_qsl(value, keep_blank_values=True, strict_parsing=True, errors="strict", max_num_fields=8)
    fields = dict(pairs)
    if len(fields) != len(pairs):
        raise ValueError("duplicate form fields")
    return fields


def _phid(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9]{1,20}", value) is not None


def _keys(value, *names):
    return isinstance(value, dict) and value.keys() == set(names)


def _save(form):
    if not _keys(form, "customBusCode", "data", "billNoStatus", "isContinue") or form["billNoStatus"] != "1":
        return False
    if json.loads(form["isContinue"]) != {"warn": "0", "validateWarn": "0", "checkProjOrgWarn": "0"}:
        return False
    data = json.loads(form["data"])
    if form["customBusCode"] == "sbzx" and _keys(data, "p_form_sbzx_m"):
        master = data["p_form_sbzx_m"]
        if not _keys(master, "form") or not isinstance(master["form"], dict):
            return False
        row = master["form"]
        operation = "modifiedRow" if "modifiedRow" in row else "newRow"
        return (
            _keys(row, "key", operation) and row["key"] == "phid" and isinstance(row[operation], dict)
            and bool(row[operation].get("u_device_code")) and row[operation].get("phid_org") == ORG
            and (operation == "newRow" or _phid(row[operation].get("phid")))
        )
    if form["customBusCode"] != "ldzcdb" or not _keys(data, "p_form_ldzcdb_m", "p_form_ldzcdb_d"):
        return False
    master, detail = data["p_form_ldzcdb_m"], data["p_form_ldzcdb_d"]
    if not _keys(master, "form") or not _keys(master["form"], "key", "newRow"):
        return False
    row = master["form"]["newRow"]
    if (
        master["form"]["key"] != "phid" or not isinstance(row, dict)
        or row.get("phid_org") != ORG or row.get("phid_schemeid") != SCHEME
        or "phid" in row
        or any(key not in row or row[key] is not None for key in ("bill_no", "bill_name", "app_status", "wf_flag"))
        or not all(_phid(row.get(key)) for key in ("phid_pc", "phid_fill_psn"))
    ):
        return False
    if not _keys(detail, "isChanged", "table") or detail["isChanged"] is not True:
        return False
    table = detail["table"]
    if not _keys(table, "key", "newRow") or table["key"] != "phid":
        return False
    rows = table["newRow"]
    return (
        isinstance(rows, list) and len(rows) == 1 and _keys(rows[0], "row") and isinstance(rows[0]["row"], dict)
        and "phid" not in rows[0]["row"] and rows[0]["row"].get("key") is None
        and _phid(rows[0]["row"].get("u_sbmc")) and _phid(rows[0]["row"].get("u_inproj"))
        and rows[0]["row"].get("phid_pc") == row["phid_pc"]
    )


def _submit(form):
    if not _keys(form, "data", "flowType") or form["flowType"] != "1":
        return False
    data = json.loads(form["data"])
    if not isinstance(data, dict) or not _phid(data.get("bizphid")) or data.get("flowdesc") not in (None, ""):
        return False
    return data == {
        "minCommentLen": 0, "needsignature": False, "pdid": PROCESS, "hasDiagramPermission": True,
        "flowdesc": data["flowdesc"], "remark": "", "biztype": "ldzcdb", "bizphid": data["bizphid"],
        "signature": "", "dynamicNode": [BRANCH], "orgId": None, "candidateUsersMap": {APPROVER_NODE: [APPROVER]},
        "formApproveUserId": None, "assignedApproveUsers": None, "formUrlParam": None,
    }


def _valid(method, url, headers, body):
    path = url.path
    query = _fields(url.query)
    media_type = headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if path == SAVE:
        return method == "POST" and not query and media_type == "application/x-www-form-urlencoded" and _save(_fields(body))
    if headers.get("env") != "java" or not re.fullmatch(
        rf"ldzcdb\|{ORG}\|[0-9]{{1,20}}\|ldzcdb\|", headers.get("gatewayauthparams", "")
    ):
        return False
    if path == SUBMIT:
        return method == "POST" and not query and media_type == "application/x-www-form-urlencoded" and _submit(_fields(body))
    if path == START_FLOW:
        if method != "POST" or query != {"customBusCode": "ldzcdb"} or media_type != "application/json":
            return False
        rows = json.loads(body)
        return (
            isinstance(rows, list) and len(rows) == 1 and _keys(rows[0], "id", "isContinue", "impSchemeId")
            and _phid(rows[0]["id"]) and rows[0]["isContinue"] == "0" and rows[0]["impSchemeId"] == SCHEME
        )
    if method != "GET" or body:
        return False
    if path == FLOW_INFO:
        return (_keys(query, "biztype", "bizphid", "flowType") and query["biztype"] == "ldzcdb"
                and _phid(query["bizphid"]) and query["flowType"] == "1")
    return (_keys(query, "procDefId", "formMetadataId", "formPk", "orgId", "flowType")
            and query["procDefId"] == PROCESS and query["formMetadataId"] == "ldzcdb"
            and _phid(query["formPk"]) and query["orgId"] == "" and query["flowType"] == "1")


def require_equipment_request(method, raw_url, headers, body):
    try:
        url = urlsplit(raw_url)
        if url.path in EQUIPMENT_PATHS and not url.fragment and not url.username and not url.password and _valid(
            method, url, {key.lower(): value for key, value in headers.items()}, body.decode("utf-8"),
        ):
            return
    except (ValueError, KeyError, RecursionError):
        pass
    raise StrictTargetMismatch("请求超出设备同步接口允许范围，已停止发送。")
