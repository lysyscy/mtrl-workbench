"""只读解析设备三账基线。先核对来源及关联，再在调用方事务中一次装入空台账。"""
from collections import Counter, defaultdict
from contextlib import closing
from datetime import date, datetime
from decimal import Decimal
import re

from openpyxl import load_workbook
from openpyxl.utils.datetime import from_excel
from sqlalchemy import select

from app.core.money import ledger_product
from .common import ledger_lock, total
from .models import EquipmentItem, EquipmentScrap, EquipmentTransfer, InventoryItem, RentalLine, RentalMonth
from .projects import ProjectRef, project_index


PROJECT_ALIASES = {
    "晋江污泥处理项目": "晋江污泥项目",
    "福建南平项目": "南平项目",
    "焦作佰利磷酸铁": "焦作佰利项目",
    "沭阳锅炉项目": "沭阳热电厂",
    "沭阳热电厂项目": "沭阳热电厂",
    "泗阳4#锅炉": "泗阳#4",
    "泗阳项目": "泗阳#4",
    "灵宝项目": "灵宝二期",
    "太康龙源纸业项目": "龙源纸业项目",
    "大唐雷州项目": "大唐雷州",
    "乌兰察布储能": "乌兰察布项目",
    "乌兰察布储能项目": "乌兰察布项目",
    "鄂旗项目": "乌兰察布项目",
}


def text(value):
    return None if value is None else str(value).strip() or None


def number(value):
    return ledger_product(Decimal(str(value)), Decimal(1)) if value is not None else None


def rows(sheet, header_row, headers, width):
    """Check identifying columns before positional parsing (including multi-row headers)."""
    data = sheet.iter_rows(min_row=header_row, max_col=width, values_only=True)
    header = next(data, ())
    if any(i >= len(header) or header[i] != label for i, label in headers.items()):
        raise ValueError(f"{sheet.title} 第 {header_row} 行表头不符")
    return enumerate(data, header_row + 1)


def source_date(value, epoch):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date) or value is None:
        return value
    if isinstance(value, (float, int)) and 1 <= value < 100000:
        return from_excel(value, epoch).date()
    match = re.fullmatch(r"(\d{4})[-./]?(\d{1,2})[-./]?(\d{2})(?:[^\d].*)?", str(value))
    if match:
        y, m, d = map(int, match.groups())
        return date(y, m, d)
    return None


def transfer_date_note(value, epoch):
    if not isinstance(value, str):
        parsed = source_date(value, epoch)
        return parsed, None if parsed else text(value)
    value = value.strip()
    match = re.fullmatch(r"(\d{4})(\d{2})(\d{2})(\D.*)?", value, re.DOTALL)
    if not match:
        match = re.fullmatch(r"(\d{4})[-./](\d{1,2})[-./](\d{1,2})(\D.*)?", value, re.DOTALL)
    if not match:
        return None, text(value)
    year, month, day, note = match.groups()
    try:
        parsed = date(int(year), int(month), int(day))
    except ValueError:
        return None, text(value)
    return parsed, text(note.strip(" \t\r\n；;,，:：")) if note else None


def match_project(value, by_name):
    matches = by_name.get(PROJECT_ALIASES.get(value, value), ())
    if len(matches) == 1:
        return ProjectRef(value, matches[0], value if value == "鄂旗项目" else None)
    return ProjectRef(value, custom=value or None)


def parse_distribution(path):
    items, transfers, scraps = {}, [], []
    with closing(load_workbook(path, read_only=True, data_only=True)) as book:
        for category, title, prefix in (("equipment", "工机具基础信息", ""), ("turnover", "周转材料", "周转材料")):
            headers = {0: "工机具编号", 1: "名称", 4: "信息化用购买日期", 5: "购买日期", 9: "当前所在项目",
                       13: "列租赁表", 14: "列资产账", 15: "租赁底稿行", 16: "盘点来源行", 19: "数量"}
            for n, r in rows(book[title], 2, headers, 21):
                code = text(r[0])
                if code in (None, "-") and not r[1]:
                    continue  # Empty formula/template row.
                if not r[1] or not code or code in items or r[19] is None:
                    raise ValueError(f"{title} 第 {n} 行名称、数量或编号异常")
                scope = {"是": "current_asset", "否": "off_book", "固定资产": "fixed_asset"}[r[11]]
                items[code] = dict(code=code, item_category=category, name=text(r[1]), spec=text(r[2]),
                    unit=text(r[3]), purchase_date=source_date(r[4], book.epoch), purchase_date_text=text(r[5]),
                    purchase_project=text(r[6]) or "", purchase_price=number(r[7]), current_project=text(r[9]),
                    status={"在用": "in_use", "损坏": "damaged", "待报废": "pending_scrap", "报废": "scrapped"}[r[8]],
                    asset_scope=scope, source_lists_inventory={"是": True, "否": False}[r[14]],
                    in_rental={"是": "yes", "否": "no", "待核": "pending"}[r[13]], quantity=number(r[19]),
                    rental_source_row=text(r[15]), inventory_source_row=text(r[16]), source_info=text(r[17]),
                    remark="\n".join(filter(None, [text(r[10]), text(r[20])])) or None, i8_sync_status="not_applicable")
            for kind in ("调拨记录", "报废记录"):
                sheet = book[prefix + kind]
                is_transfer = kind == "调拨记录"
                headers = {0: "工机具编号", 9 if is_transfer else 8: "调拨日期" if is_transfer else "报废日期"}
                for n, r in rows(sheet, 1, headers, 11):
                    code = text(r[0])
                    if not code:
                        continue
                    if code not in items or items[code]["item_category"] != category:
                        raise ValueError(f"{sheet.title} 第 {n} 行找不到同类设备")
                    item = items[code]
                    record = dict(code=code, item_category=category, quantity=item["quantity"])
                    if is_transfer:
                        dt, date_note = transfer_date_note(r[9], book.epoch)
                        note = "；".join(dict.fromkeys(filter(None, [date_note, text(r[10])]))) or None
                        transfers.append(dict(record, transfer_date=dt, from_project=text(r[7]), to_project=text(r[8]),
                            remark=note, rental_attribution="not_applicable", i8_sync_status="not_applicable"))
                    else:
                        dt = source_date(r[8], book.epoch)
                        if not dt:
                            raise ValueError(f"{sheet.title} 第 {n} 行缺完整报废日期")
                        item.update(status="scrapped", scrap_date=dt, scrap_reason=text(r[9]))
                        scraps.append(dict(record, scrap_date=dt, original_project=text(r[7]), purchase_price=number(r[6]),
                                           reason=text(r[9]), rental_stop_status="not_applicable"))
    return items, transfers, scraps


def parse_inventory(path):
    result = {}
    with closing(load_workbook(path, read_only=True, data_only=True)) as book:
        for category, title in (("tool", "2025年年终盘点流动资产"), ("turnover", "周转材料")):
            for n, r in rows(book[title], 3, {4: "单价", 5: "帐面数", 7: "盘点数", 11: "盈亏原因"}, 12):
                if n == 4 or not r[1] or str(r[1]).startswith("合计"):
                    continue
                if not str(r[0]).isdigit() or r[5] is None or r[7] is None:
                    raise ValueError(f"{title} 第 {n} 行序号或数量异常")
                result[category, str(n)] = dict(category=category, sort_order=n, source_row=str(n),
                    name=text(r[1]), spec=text(r[2]), unit=text(r[3]), unit_price=number(r[4]), book_qty=number(r[5]),
                    book_amount=number(r[6]), count_qty=number(r[7]), count_amount=number(r[8]), diff_qty=number(r[9]),
                    diff_amount=number(r[10]), diff_reason=text(r[11]))
    return result


def parse_rental(path):
    lines = []
    with closing(load_workbook(path, read_only=True, data_only=True)) as book:
        if "本月租赁" in book:
            headers = {0: "项目", 1: "设备名称", 4: "数量", 5: "租赁单价（元）", 6: "本月收费", 7: "金额（元）",
                       9: "类别", 10: "原值（元）", 11: "自定义单价（元）", 12: "底稿行", 15: "对应设备编号"}
            for n, r in rows(book["本月租赁"], 5, headers, 16):
                if not any(v is not None for v in r):
                    continue
                if not r[0] or not r[1] or r[4] is None or r[12] is None:
                    raise ValueError(f"本月租赁第 {n} 行缺项目、名称、数量或底稿行")
                billing = {"计费": "normal", "金额留空": "blank"}[r[6]]
                if billing == "blank" and r[7] is not None:
                    raise ValueError(f"本月租赁第 {n} 行收费状态与金额冲突")
                if billing == "normal" and r[5] is not None and r[7] is None:
                    raise ValueError(f"本月租赁第 {n} 行缺少已计费金额，请核对公式缓存")
                lines.append(dict(project_name=text(r[0]), name=text(r[1]), spec=text(r[2]), unit=text(r[3]),
                    quantity=number(r[4]), unit_price=number(r[5]), billing_status=billing, amount=number(r[7]),
                    category_label=text(r[9]) or "", original_value=number(r[10]), custom_unit_price=number(r[11]),
                    source_row=text(r[12]), code=text(r[15])))
        else:
            sheet = book["分公司9月份 (2)"]
            project = None
            for n, r in rows(sheet, 1, {0: "租赁费明细（费用划转）", 11: "原值"}, 12):
                if str(r[0]).startswith("单位："):
                    project = r[0].partition("：")[2].strip()
                if not str(r[0]).isdigit() or not r[1]:
                    continue
                if not project or r[4] is None:
                    raise ValueError(f"{sheet.title} 第 {n} 行缺项目或数量")
                price, original = number(r[5]), number(r[11])
                lines.append(dict(project_name=project, name=text(r[1]), spec=text(r[2]), unit=text(r[3]),
                    quantity=number(r[4]), unit_price=price, amount=number(r[6]), original_value=original,
                    custom_unit_price=price if price != ledger_product(original, Decimal(".05")) else None,
                    billing_status="blank" if r[6] is None else "normal", category_label=text(r[7]) or "",
                    distribution_note=text(r[8]), source_row=str(n)))
    return lines


def import_equipment_baseline(session, *, distribution_path, inventory_path, rental_path,
                              rental_month="2026-11", dry_run=False):
    """Dry runs need no session. Apply flushes under the shared ledger lock; caller owns commit."""
    if not re.fullmatch(r"[0-9]{4}-(0[1-9]|1[0-2])", rental_month):
        raise ValueError("租赁月份须为 YYYY-MM")
    items, transfers, scraps = parse_distribution(distribution_path)
    inventory = parse_inventory(inventory_path)
    lines = parse_rental(rental_path)
    if not items or not inventory or not lines:
        raise ValueError("三账基线缺少有效明细")
    inventory_links, by_rental_row = {}, defaultdict(list)
    for code, item in items.items():
        category = "tool" if item["item_category"] == "equipment" else "turnover"
        key = category, item["inventory_source_row"]
        if item["source_lists_inventory"] and key in inventory:
            inventory_links[code] = key
        by_rental_row[item["rental_source_row"]].append(code)
    for line in lines:
        if "code" not in line:  # Legacy print sheet has no explicit equipment code.
            matches = by_rental_row[line["source_row"]]
            line["code"] = matches[0] if len(matches) == 1 else None
    uses = Counter(line["code"] for line in lines)
    rental_links = {i: line["code"] for i, line in enumerate(lines) if line["code"] in items and uses[line["code"]] == 1}
    tool_rows = [r for r in inventory.values() if r["category"] == "tool"]
    equipment = sum(r["item_category"] == "equipment" for r in items.values())
    summary = dict(equipment_count=equipment, turnover_count=len(items)-equipment, transfer_count=len(transfers),
        scrap_count=len(scraps), inventory_tool_count=len(tool_rows), inventory_turnover_count=len(inventory)-len(tool_rows),
        inventory_tool_book_total=total(r["book_amount"] for r in tool_rows), rental_line_count=len(lines),
        rental_grand_total=total(r["amount"] for r in lines), linked_inventory_count=len(inventory_links),
        linked_rental_count=len(rental_links))
    if dry_run:
        return summary

    with session.begin_nested():
        ledger_lock(session)
        for model in (InventoryItem, EquipmentItem, EquipmentTransfer, EquipmentScrap, RentalMonth, RentalLine):
            if session.scalar(select(model.id).limit(1)) is not None:
                raise ValueError(f"台账非空，拒绝重复导入 ({model.__tablename__})")
        by_name = defaultdict(list)
        for project in project_index(session).values():
            by_name[project.disp].append(project.id)
        for records, prefixes in ((items.values(), ("purchase_project", "current_project")),
                                  (transfers, ("from_project", "to_project")), (scraps, ("original_project",))):
            for record in records:
                for prefix in prefixes:
                    record.update(match_project(record[prefix], by_name).fields(prefix))
        assets = {k: InventoryItem(**r) for k, r in inventory.items()}
        session.add_all(list(assets.values()) + [RentalMonth(month=rental_month)])
        session.flush()
        equipment_rows = {k: EquipmentItem(**r) for k, r in items.items()}
        for code, key in inventory_links.items():
            equipment_rows[code].inventory_item_id = assets[key].id
        session.add_all(equipment_rows.values())
        session.flush()
        for model, history in ((EquipmentTransfer, transfers), (EquipmentScrap, scraps)):
            for record in history:
                session.add(model(equipment_id=equipment_rows[record.pop("code")].id, **record))
        project_order, row_counts = {}, Counter()
        for i, line in enumerate(lines):
            line.pop("code")
            item = equipment_rows.get(rental_links.get(i))
            project = (ProjectRef.from_row(item, "current_project") if item and item.current_project_id is not None
                       else match_project(line["project_name"], by_name))
            key = project.key()
            line.update(project.fields("project", label="project_name"))
            session.add(RentalLine(month=rental_month, equipment_id=item.id if item else None,
                                   project_sort_order=project_order.setdefault(key, len(project_order)),
                                   row_sort_order=row_counts[key], **line))
            row_counts[key] += 1
    return summary
