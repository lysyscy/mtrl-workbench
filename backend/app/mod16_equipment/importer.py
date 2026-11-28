"""只读解析设备三账基线。先核对来源及关联，再在调用方事务中一次装入空台账。"""
from collections import Counter, defaultdict
from contextlib import closing
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
import re

from openpyxl import load_workbook
from openpyxl.utils.datetime import from_excel
from sqlalchemy import delete, select

from app.core.money import ledger_product, to_money
from .common import ledger_lock, total
from .models import EquipmentItem, EquipmentScrap, EquipmentTransfer, InventoryItem, Location, RentalLine, RentalMonth
from .projects import ProjectRef, project_index
from .rental import category_label, imported_category_label


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


def source_decimal(value):
    return Decimal(str(value)) if value is not None else None


def source_scale(value):
    return value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP) if value is not None else None


def number(value):
    return source_scale(source_decimal(value))


def money(value):
    return to_money(value) if value is not None else None


def imported_amount(amount, quantity, source_price, price):
    if amount is None:
        return None
    if quantity is not None and source_price is not None and abs(amount - quantity * source_price) <= Decimal("0.005"):
        return ledger_product(quantity, price)
    return money(amount)


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
                    purchase_project=text(r[6]) or "", purchase_price=source_decimal(r[7]), current_project=text(r[9]),
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
                        scraps.append(dict(record, scrap_date=dt, original_project=text(r[7]), purchase_price=source_decimal(r[6]),
                                           reason=text(r[9]), rental_stop_status="not_applicable"))
    return items, transfers, scraps


def parse_inventory(path):
    result = {}
    with closing(load_workbook(path, read_only=True, data_only=True)) as book:
        for category, title in (("tool", "2025年年终盘点流动资产"), ("turnover", "周转材料")):
            for n, r in rows(book[title], 3, {4: "单价", 5: "帐面数", 7: "盘点数", 11: "盈亏原因"}, 12):
                if n == 4 or not r[1] or str(r[1]).startswith("合计"):
                    continue
                if not str(r[0]).isdigit() or r[5] is None:
                    raise ValueError(f"{title} 第 {n} 行序号或数量异常")
                result[category, str(n)] = dict(category=category, sort_order=n, source_row=str(n),
                    name=text(r[1]), spec=text(r[2]), unit=text(r[3]), unit_price=source_decimal(r[4]), book_qty=number(r[5]),
                    book_amount=source_decimal(r[6]), count_qty=number(r[7]), count_amount=source_decimal(r[8]), diff_qty=number(r[9]),
                    diff_amount=source_decimal(r[10]), diff_reason=text(r[11]))
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
                    quantity=number(r[4]), unit_price=source_decimal(r[5]), billing_status=billing, amount=source_decimal(r[7]),
                    category_label=imported_category_label(text(r[9])),
                    original_value=source_decimal(r[10]), custom_unit_price=source_decimal(r[11]),
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
                price, original = source_decimal(r[5]), source_decimal(r[11])
                lines.append(dict(project_name=project, name=text(r[1]), spec=text(r[2]), unit=text(r[3]),
                    quantity=number(r[4]), unit_price=price, amount=source_decimal(r[6]), original_value=original,
                    custom_unit_price=price if original is None or source_scale(price) != source_scale(original * Decimal(".05")) else None,
                    billing_status="blank" if r[6] is None else "normal", category_label=imported_category_label(text(r[7])),
                    distribution_note=text(r[8]), source_row=str(n)))
    return lines


def link_jiaozuo_tricycles(items, inventory, links):
    # The accepted baseline pairs these indistinguishable May 2023 vehicles in source order.
    codes = ("电动三轮车-202305-1", "电动三轮车-202305-2")
    for code in codes:
        item = items.get(code)
        if item is None or code in links or item["status"] == "scrapped":
            return
        identity = item["name"], source_scale(item["purchase_price"]), item["quantity"], item["asset_scope"], item["item_category"]
        if not item["source_lists_inventory"] or identity != ("电动三轮车", 5300, 1, "current_asset", "equipment"):
            return
    linked = set(links.values())
    matches = [key for key, row in inventory.items() if key not in linked and
               (row["category"], row["name"], source_scale(row["unit_price"]), row["book_qty"]) ==
               ("tool", "电动三轮车", 5300, 1)]
    if len(matches) == len(codes):
        matches.sort(key=lambda key: inventory[key]["sort_order"])
        links.update(zip(codes, matches, strict=False))


def inventory_fields(row):
    return dict(name=row["name"], spec=row["spec"], unit=row["unit"], quantity=row["book_qty"],
                purchase_price=row["unit_price"], inventory_source_row=row["source_row"],
                source_lists_inventory=True)


def align_baseline(items, inventory, transfers, scraps, lines):
    history = transfers + scraps
    history_codes = {row["code"] for row in history}
    replacements, renamed, rental_names = {}, {}, {}
    for code, item in items.items():
        row = inventory.get(("tool", item["inventory_source_row"]))
        qty = item["quantity"]
        if (item["item_category"] == "equipment" and re.fullmatch(r"盘点\d+", code)
                and row and item["source_lists_inventory"] and qty > 1 and qty == int(qty) == row["book_qty"]
                and not item["rental_source_row"] and code not in history_codes):
            replacements[code] = [dict(item, code=f"{code}-{unit:02d}", quantity=Decimal(1))
                                  for unit in range(1, int(qty) + 1)]

    old_welders = [f"二保焊机-20230711-{unit:02d}" for unit in range(1, 5)]
    if any(code in items for code in old_welders):
        welder = inventory.get(("tool", "75"))
        if ((welder and (welder["name"], welder["book_qty"], source_scale(welder["unit_price"]))) !=
                ("逆变焊机", 15, Decimal("1132.7430")) or not all(
                    code in items and items[code]["inventory_source_row"] == "75" for code in old_welders)):
            raise ValueError("南靖焊机基线与已确认的盘点对应关系不符")
        for unit in range(1, 16):
            old = old_welders[min(unit - 1, 3)]
            code = f"逆变焊机-20230711-{unit:02d}"
            row = dict(items[old], **inventory_fields(welder))
            row.update(code=code, quantity=Decimal(1), purchase_date=date(2023, 7, 11),
                       purchase_project="南靖项目", current_project="南平项目", asset_scope="current_asset",
                       in_rental="yes", remark="实物为4台二保焊机")
            replacements.setdefault(old, []).append(row)
            if unit <= 4:
                renamed[old] = code

    for number_, source_row, price in ((1, "7", "34867.26"), (2, "9", "12570"), (3, "10", "14920.35")):
        old = f"吹扫阀门-未知{number_}"
        if old not in items:
            continue
        item, valve = items[old], inventory.get(("turnover", source_row))
        silencer = inventory.get(("turnover", "8")) if number_ == 1 else None
        if (not valve or valve["name"] != "电动闸阀" or (number_ == 1 and
                (not silencer or silencer["name"] != "消音器")) or source_scale(item["purchase_price"]) != Decimal(price)
                or total(source_scale(row["unit_price"]) for row in (valve, silencer) if row) != Decimal(price)):
            raise ValueError(f"{old}基线与已确认的盘点对应关系不符")
        code = f"电动闸阀-未知{number_}"
        row = dict(item, **inventory_fields(valve))
        row["code"] = renamed[old] = code
        replacements[old] = [row]
        if item["rental_source_row"]:
            rental_names[item["rental_source_row"]] = row
        if silencer:
            row.update(spec="DN150 100公斤，碳钢", status="damaged", in_rental="no",
                       remark="原吹扫阀门一套，阀门已坏")
            other = dict(item, **inventory_fields(silencer))
            other.update(code="消音器-未知1", status="in_use", in_rental="no", remark="原吹扫阀门一套")
            replacements[old].append(other)

    aligned = {}
    for old, item in items.items():
        for row in replacements.get(old, [item]):
            code = row["code"]
            if code in aligned:
                raise ValueError(f"接续设备编号重复：{code}")
            aligned[code] = row
    linked_turnover = {row["inventory_source_row"] for row in aligned.values()
                       if row["item_category"] == "turnover" and row["source_lists_inventory"]}
    for key, row in inventory.items():
        if key[0] == "turnover" and row["name"] == "电缆" and row["spec"] in ("YH35", "YH50") and key[1] not in linked_turnover:
            code = f"盘点电缆-{row['spec']}"
            if code in aligned:
                raise ValueError(f"接续设备编号重复：{code}")
            aligned[code] = dict(**inventory_fields(row), code=code, item_category="turnover", purchase_project="",
                                 current_project="待核", asset_scope="current_asset", status="in_use", in_rental="no",
                                 remark="盘点周转材料接续", i8_sync_status="not_applicable", rental_source_row=None)
    for row in history:
        row["code"] = renamed.get(row["code"], row["code"])
    for line in lines:
        valve = rental_names.get(line["source_row"])
        if valve and source_scale(line["original_value"]) == source_scale(valve["purchase_price"]):
            line.update(code=valve["code"], name=valve["name"], category_label="周转材料")
    return aligned


def remember_location(locations, ref):
    if ref.custom:
        if ref.id is not None:
            locations[ref.custom] = ref.id
        else:
            locations.setdefault(ref.custom, None)


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
    items = align_baseline(items, inventory, transfers, scraps, lines)
    inventory_links, by_rental_row = {}, defaultdict(list)
    for code, item in items.items():
        category = "tool" if item["item_category"] == "equipment" else "turnover"
        key = category, item["inventory_source_row"]
        if item["source_lists_inventory"] and key in inventory:
            inventory_links[code] = key
        by_rental_row[item["rental_source_row"]].append(code)
    link_jiaozuo_tricycles(items, inventory, inventory_links)
    for line in lines:
        if "code" not in line:  # Legacy print sheet has no explicit equipment code.
            matches = by_rental_row[line["source_row"]]
            line["code"] = matches[0] if len(matches) == 1 else None
    uses = Counter(line["code"] for line in lines)
    rental_links = {i: line["code"] for i, line in enumerate(lines) if line["code"] in items and uses[line["code"]] == 1}
    # Match the source rows before converting their monetary values for storage.
    for row in (*items.values(), *scraps):
        row["purchase_price"] = money(row["purchase_price"])
    for row in inventory.values():
        source_price = row["unit_price"]
        row["unit_price"] = price = money(source_price)
        for prefix in ("book", "count", "diff"):
            key = f"{prefix}_amount"
            row[key] = imported_amount(row[key], row[f"{prefix}_qty"], source_price, price)
    for line in lines:
        source_price = line["unit_price"]
        original, custom = line["original_value"], line["custom_unit_price"]
        default_price = source_scale(original * Decimal(".05")) if original is not None else None
        line["original_value"], line["custom_unit_price"] = money(original), money(custom)
        price = money(source_price)
        if source_price is not None and source_scale(source_price) == (source_scale(custom) if custom is not None else default_price):
            price = line["custom_unit_price"] if custom is not None else ledger_product(line["original_value"], Decimal(".05"))
        line["unit_price"] = price
        if line["billing_status"] == "normal":
            line["amount"] = imported_amount(line["amount"], line["quantity"], source_price, price)
        else:
            line["amount"] = money(line["amount"])
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
        for model in (InventoryItem, EquipmentItem, EquipmentTransfer, EquipmentScrap, RentalLine):
            if session.scalar(select(model.id).limit(1)) is not None:
                raise ValueError(f"台账非空，拒绝重复导入 ({model.__tablename__})")
        session.execute(delete(RentalMonth).where(RentalMonth.status == "draft"))
        by_name = defaultdict(list)
        for project in project_index(session).values():
            by_name[project.disp].append(project.id)
        locations = {}
        for records, prefixes in ((items.values(), ("purchase_project", "current_project")),
                                  (transfers, ("from_project", "to_project")), (scraps, ("original_project",))):
            for record in records:
                for prefix in prefixes:
                    ref = match_project(record[prefix], by_name)
                    record.update(ref.fields(prefix))
                    remember_location(locations, ref)
        assets = {k: InventoryItem(**r) for k, r in inventory.items()}
        session.add_all(assets.values())
        if session.scalar(select(RentalMonth.id).where(RentalMonth.month == rental_month)) is None:
            session.add(RentalMonth(month=rental_month))
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
            project = match_project(line["project_name"], by_name)
            remember_location(locations, project)
            if item:
                line["category_label"] = category_label(item.item_category)
            key = project.key()
            line.update(project.fields("project", label="project_name"))
            session.add(RentalLine(month=rental_month, equipment_id=item.id if item else None,
                                   project_sort_order=project_order.setdefault(key, len(project_order)),
                                   row_sort_order=row_counts[key], **line))
            row_counts[key] += 1
        existing = set(session.scalars(select(Location.name)))
        session.add_all(Location(name=name, default_project_id=project_id)
                        for name, project_id in locations.items() if name not in existing)
    return summary
