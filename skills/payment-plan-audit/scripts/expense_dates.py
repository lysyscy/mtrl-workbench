"""Normalize expense dates and change their display without resaving the workbook."""
import argparse
from datetime import date, datetime
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import posixpath
import re
from tempfile import NamedTemporaryFile
from xml.dom.minidom import parseString
from zipfile import ZipFile

from openpyxl import load_workbook
from openpyxl.utils.datetime import from_excel, to_excel

from annotate import NS, REL, add, children


MONTH_FORMAT = 'yyyy"年"m"月";@'
SERIAL_START = date(1990, 1, 1)
SERIAL_STOP = date(2101, 1, 1)


def expense_date(value, number_format, epoch):
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        text = value.strip().replace('年', '-').replace('月', '-').removesuffix('日').removesuffix('-')
        match = re.fullmatch(r'(\d{4})[-./](\d{1,2})(?:[-./](\d{1,2}))?', text)
        if match:
            year, month, day = match.groups()
            return date(int(year), int(month), int(day or 1))
    if type(value) in (int, float):
        match = re.fullmatch(r'(\d{4})\.(\d{1,2})', str(value))
        if match:
            year, digits = match.groups()
            if digits == '1':
                if not number_format.startswith('0.00'):
                    raise ValueError('小数年月可能是 1 月或 10 月，请先改成明确的年月')
                digits = '10'
            return date(int(year), int(digits), 1)
        if to_excel(SERIAL_START, epoch) <= value < to_excel(SERIAL_STOP, epoch):
            return from_excel(value, epoch)
    raise ValueError('无法识别费用日期，请改成明确的年月或日期')


def formatted_workbook(original, plan):
    book = load_workbook(BytesIO(original), keep_links=False)
    try:
        sheet = book[plan['sheet']]
        headers = {str(sheet[f"B{r['row']}"].value or '').strip() for r in plan['structures'] if r['kind'] == '表头'}
        if '费用日期' not in headers or headers - {'', '费用日期'}:
            raise ValueError('B 列未确认为费用日期')
        edits = {}
        for row in plan['rows']:
            cell = sheet[f"B{row['row']}"]
            if cell.value is None or cell.value == '' or (cell.is_date and cell.number_format == MONTH_FORMAT):
                continue
            try:
                value = expense_date(cell.value, cell.number_format, book.epoch)
            except ValueError as error:
                raise ValueError(f'{sheet.title}!{cell.coordinate}：{error}') from error
            edits[cell.coordinate] = to_excel(value, book.epoch)
    finally:
        book.close()
    if not edits:
        return original, 0

    result = BytesIO()
    with ZipFile(BytesIO(original)) as source, ZipFile(result, 'w') as output:
        workbook = parseString(source.read('xl/workbook.xml'))
        sheets, = children(workbook.documentElement, 'sheets')
        sheet = next(node for node in children(sheets, 'sheet') if node.getAttribute('name') == plan['sheet'])
        relation = sheet.getAttributeNS(REL, 'id')
        rels = parseString(source.read('xl/_rels/workbook.xml.rels'))
        path = next(node.getAttribute('Target') for node in children(rels.documentElement, 'Relationship')
                    if node.getAttribute('Id') == relation)
        path = path.lstrip('/') if path.startswith('/') else posixpath.normpath(posixpath.join('xl', path))
        worksheet = parseString(source.read(path))
        styles = parseString(source.read('xl/styles.xml'))
        root = styles.documentElement
        formats = children(root, 'numFmts')
        if not formats:
            container = styles.createElementNS(NS, 'numFmts')
            root.insertBefore(container, root.firstChild)
            formats = [container]
        formats = formats[0]
        existing = children(formats, 'numFmt')
        ids = {node.getAttribute('formatCode'): int(node.getAttribute('numFmtId')) for node in existing}
        month_id = ids.get(MONTH_FORMAT)
        if month_id is None:
            month_id = max([163, *ids.values()]) + 1
            add(formats, 'numFmt', {'numFmtId': month_id, 'formatCode': MONTH_FORMAT})
            formats.setAttribute('count', str(len(existing) + 1))
        xfs, = children(root, 'cellXfs')
        base_styles = children(xfs, 'xf')
        date_styles = {}
        cells = {cell.getAttribute('r'): cell for cell in worksheet.getElementsByTagNameNS(NS, 'c')}
        shared_removed = 0
        for coordinate, serial in edits.items():
            cell = cells[coordinate]
            base = int(cell.getAttribute('s') or 0)
            if base not in date_styles:
                style = base_styles[base].cloneNode(deep=True)
                style.setAttribute('numFmtId', str(month_id))
                style.setAttribute('applyNumberFormat', '1')
                date_styles[base] = len(base_styles) + len(date_styles)
                xfs.appendChild(style)
            shared_removed += cell.getAttribute('t') == 's'
            cell.setAttribute('s', str(date_styles[base]))
            cell.setAttribute('t', 'n')
            for node in children(cell, 'is') + children(cell, 'v'):
                cell.removeChild(node)
            add(cell, 'v', value=format(serial, '.16g'))
        xfs.setAttribute('count', str(len(base_styles) + len(date_styles)))
        replacements = {path: worksheet, 'xl/styles.xml': styles}
        if shared_removed:
            name = 'xl/sharedStrings.xml'
            shared = parseString(source.read(name))
            count = shared.documentElement.getAttribute('count')
            if count:
                shared.documentElement.setAttribute('count', str(int(count) - shared_removed))
                replacements[name] = shared
        for entry in source.infolist():
            changed = replacements.get(entry.filename)
            output.writestr(entry, changed.toxml(encoding='UTF-8') if changed else source.read(entry))
    payload = result.getvalue()
    check = load_workbook(BytesIO(payload), keep_links=False)
    try:
        sheet = check[plan['sheet']]
        for coordinate, serial in edits.items():
            cell = sheet[coordinate]
            if cell.number_format != MONTH_FORMAT or cell.value != from_excel(serial, check.epoch):
                raise ValueError(f'{sheet.title}!{coordinate}：费用月份读回校验失败')
    finally:
        check.close()
    return payload, len(edits)


def format_file(source, month, sheet, backup_dir):
    from audit import read_plan

    if not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', month):
        raise ValueError('月份须为YYYY-MM')
    source = Path(source).resolve(strict=True)
    plan = read_plan(source, month, sheet)
    original = source.read_bytes()
    digest = sha256(original).hexdigest()
    if digest != plan['source_sha256']:
        raise ValueError('原表已变化，请重新读取')
    lock_names = [source.with_name('~$' + name) for name in (source.name, source.name[2:])]
    if any(lock.exists() for lock in lock_names):
        raise ValueError('请保存并关闭 Excel 后再整理')
    payload, changed = formatted_workbook(original, plan)
    if not changed:
        return {'changed': 0, 'source': str(source)}
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / f'{datetime.now():%Y%m%d-%H%M%S}-{digest[:12]}-费用月份整理前-{source.name}'
    with backup.open('xb') as out:
        out.write(original)
    if sha256(backup.read_bytes()).hexdigest() != digest:
        raise ValueError('写前备份校验失败')
    temp = None
    try:
        with NamedTemporaryFile(dir=source.parent, suffix='.xlsx', delete=False) as out:
            temp = Path(out.name)
            out.write(payload)
        if source.read_bytes() != original or any(lock.exists() for lock in lock_names):
            raise ValueError('整理期间原表已变化或打开，请重新读取')
        os.replace(temp, source)
    finally:
        if temp:
            temp.unlink(missing_ok=True)
    return {'changed': changed, 'source': str(source), 'backup': str(backup)}


def main():
    from snapshot import configure

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    parser.add_argument('--month', required=True)
    parser.add_argument('--sheet')
    args = parser.parse_args()
    configure()
    backup = Path.home() / '.mtrl-workbench/backups/payment-plan-audit'
    print(json.dumps(format_file(args.source, args.month, args.sheet, backup), ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError) as error:
        raise SystemExit(str(error)) from None
