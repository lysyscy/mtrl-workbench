"""Copy project submissions into one Excel sheet for payment plan audit."""
from __future__ import annotations

import argparse
from copy import copy
from dataclasses import dataclass, field
from decimal import Decimal
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import re
from statistics import mean
from tempfile import NamedTemporaryFile
from xml.dom.minidom import parseString
from zipfile import ZipFile

from openpyxl import Workbook, load_workbook
from openpyxl.cell.rich_text import CellRichText, TextBlock
from openpyxl.cell.text import InlineFont
from openpyxl.utils import get_column_letter

from audit import FIELD_OF, METHODS, norm, text
from expense_dates import MONTH_FORMAT, expense_date


SHEET = '材机付款计划明细'
SHEETS = (SHEET, '材机付款计划')
FIELDS = ('subject', 'expense_date', 'doc_no', 'payee', 'flow_amount', 'paid',
          'planned_amount', 'remaining', 'pay_date', 'pay_method', 'remark', 'note')
HEADERS = FIELD_OF | {norm(label): key for label, key in (
    ('科目', 'subject'), ('费用日期', 'expense_date'), ('已付款金额', 'paid'),
    ('剩余付款金额', 'remaining'), ('付款附注', 'note'),
)}
REQUIRED = {'doc_no', 'flow_amount', 'planned_amount'}
PERIOD = re.compile(r'(?<!\d)(?:(\d{4}|\d{2})\s*年\s*)?(0?[1-9]|1[0-2])\s*月(?:份)?')
SUBTOTAL = '小计'
TOTALS = {'合计', '总计', '大合计', '项目合计'}


@dataclass
class Group:
    subject: object = None
    rows: list = field(default_factory=list)


@dataclass
class Project:
    title: str
    groups: list[Group] = field(default_factory=list)


def columns(row):
    return {HEADERS[norm(cell.value)]: cell.column for cell in row if norm(cell.value) in HEADERS}


def project_title(value):
    value = text(value)
    return '项目' in value and '付款计划' in value


def project_key(title):
    return re.sub(r'\s+', '', title.split('项目', 1)[0])


def title_with_blanks(title, sample):
    heading, _, _ = title.partition('付款计划')
    _, _, sample_suffix = sample.partition('付款计划')
    label = re.search(r'(本月[^，,。；;：:（）()\r\n]*预计回款)\s*[：:]', sample_suffix)
    payback = label[1] if label else '本月预计回款'
    return f'{heading}付款计划（账面数：　万，{payback}：　万）'


def write_title(cell, title):
    prefix, opening, suffix = title.rpartition('（')
    font = cell.font
    attributes = {name: getattr(font, name) for name in InlineFont.__elements__
                  if name not in ('rFont', 'color')}
    red = InlineFont(rFont=font.name, color='FFFF0000', **attributes)
    cell.value = CellRichText([prefix, TextBlock(red, opening + suffix)])


def dated_title(value, month, confirmed, location):
    start = value.index('项目') + len('项目')
    match = PERIOD.search(value, start)
    year, number = map(int, month.split('-'))
    title_year = int(match[1]) if match and match[1] else year
    if match and match[1] and len(match[1]) == 2:
        title_year += year // 100 * 100
    if match and (title_year, int(match[2])) != (year, number) and not confirmed:
        raise ValueError(f'{location} 的项目标题月份与 {month} 不符，须确认后再合并')
    label = f'{year}年{number}月份'
    if match:
        return value[:match.start()] + label + value[match.end():]
    return value[:start] + label + value[start:]


def read_projects(source, contents, month, confirmed):
    book = load_workbook(BytesIO(contents), keep_links=False)
    saved = load_workbook(BytesIO(contents), data_only=True, keep_links=False)
    try:
        sheets = [book[name] for name in SHEETS if name in book.sheetnames]
        if len(sheets) != 1:
            raise ValueError(f'{source.name} 须有且仅有一张材机付款计划表')
        sheet = sheets[0]
        values = saved[sheet.title]
        merged_subject = {}
        for region in sheet.merged_cells.ranges:
            if region.min_col == region.max_col == 1:
                subject = sheet.cell(region.min_row, 1).value
                merged_subject.update(dict.fromkeys(range(region.min_row, region.max_row + 1), subject))

        projects = []
        project = group = None
        header = {}
        for row in sheet.iter_rows(max_col=max(12, sheet.max_column)):
            if not any(cell.value is not None for cell in row):
                continue
            number = row[0].row
            location = f'{source.name} / {sheet.title}!A{number}'
            first = row[0].value
            if project_title(first):
                project = Project(dated_title(text(first), month, confirmed, location))
                projects.append(project)
                group = None
                header = {}
                continue
            found = columns(row)
            if REQUIRED <= found.keys():
                if project is None:
                    raise ValueError(f'{location} 上方没有项目标题')
                header = found
                if 'note' not in header and 12 not in header.values():
                    header['note'] = 12
                group = None
                continue
            if not header:
                continue
            doc = row[header['doc_no'] - 1].value
            if found and all(cell.value is None or norm(cell.value) in HEADERS for cell in row[:11]):
                continue
            labels = {norm(doc), norm(first)}
            if SUBTOTAL in labels or labels & TOTALS:
                group = None
                continue
            payee = row[header['payee'] - 1].value if 'payee' in header else None
            if re.fullmatch(r'(?:项目)?负责人(?:[（(]签字[）)])?[：:]?', text(payee)) and all(
                cell.value is None or cell.column == header['payee'] for cell in row[:12]
            ):
                continue
            detail = {}
            for key in FIELDS[1:]:
                if key not in header:
                    continue
                original = row[header[key] - 1]
                cell = values.cell(number, header[key])
                if original.data_type == 'f' and cell.value is None:
                    raise ValueError(f'{source.name} / {sheet.title}!{original.coordinate} 公式无保存值，请在 Excel 重算并保存')
                if cell.value is not None:
                    detail[key] = (cell.value, cell.data_type, cell.number_format)
            if not (detail.keys() - {'expense_date'}):
                continue
            if 'expense_date' in detail and detail['expense_date'][0] != '':
                value, _, fmt = detail['expense_date']
                try:
                    detail['expense_date'] = (expense_date(value, fmt, saved.epoch), 'd', MONTH_FORMAT)
                except ValueError as error:
                    location = values.cell(number, header['expense_date']).coordinate
                    raise ValueError(f'{source.name} / {sheet.title}!{location}：{error}') from error
            # A method written under payment date can be moved when its own cell is empty.
            if text(detail.get('pay_date', (None,))[0]) in METHODS and 'pay_method' not in detail:
                detail['pay_method'] = detail.pop('pay_date')
            subject = merged_subject.get(number, first) if header.get('subject', 1) == 1 else row[header['subject'] - 1].value
            if group is None or group.subject != subject:
                group = Group(subject)
                project.groups.append(group)
            group.rows.append(detail)
        if not any(project.groups for project in projects):
            raise ValueError(f'{source.name} 未识别出材机付款明细')
        return [project for project in projects if project.groups]
    finally:
        saved.close()
        book.close()


def style_row(sheet, target, template, source, width=12):
    for column in range(1, width + 1):
        cell = sheet.cell(target, column)
        base = template.cell(source, column)
        cell.font = copy(base.font)
        cell.fill = copy(base.fill)
        cell.border = copy(base.border)
        cell.alignment = copy(base.alignment)
        cell.number_format = base.number_format


def copy_value(cell, value, kind='s'):
    cell.value = value
    if isinstance(value, str):
        cell.data_type = 'e' if kind == 'e' else 's'


def sum_rows(sheet, total, column, start, end, cache):
    letter = get_column_letter(column)
    cell = sheet.cell(total, column, f'=SUM({letter}{start}:{letter}{end})')
    values = []
    for row in range(start, end + 1):
        detail = sheet.cell(row, column)
        if detail.data_type == 'e':
            values.append(detail.value)
        elif type(detail.value) in (int, float):
            values.append(Decimal(str(detail.value)))
    cache[cell.coordinate] = sum_cached(values)


def sum_cached(values):
    values = list(values)
    error = next((value for value in values if isinstance(value, str)), None)
    return error if error is not None else sum(values, Decimal(0))


def render_plan(template_contents, projects, *, start_row=1, existing_totals=None, style_sources=None):
    base = load_workbook(BytesIO(template_contents), keep_links=False)
    try:
        if SHEET not in base.sheetnames:
            raise ValueError(f'成品样表缺少「{SHEET}」')
        template = base[SHEET]
        expected = {key: index for index, key in enumerate(FIELDS[:11], 1)}
        if not project_title(template['A1'].value) or columns(template[2][:11]) != expected:
            raise ValueError('成品样表须按约定使用 A1 项目标题及 A2:K2 材机表头')
        template_titles = {}
        for (cell,) in template.iter_rows(max_col=1):
            if project_title(cell.value):
                template_titles.setdefault(project_key(cell.value), cell)
        default_height = template.sheet_format.defaultRowHeight
        row_height = round(mean(template.row_dimensions[number].height or default_height
                                for number in range(1, template.max_row + 1)), 2)
        second = template['C3'].value
        second = second if FIELD_OF.get(norm(second)) == 'doc_no' else None
        detail_style = 4 if second else 3
        subtotal_style = next((cell.row for (cell,) in template.iter_rows(min_col=3, max_col=3)
                               if norm(cell.value) == SUBTOTAL), detail_style)
        project_style = next((row[0].row - 1 for row in template.iter_rows(min_row=3, max_col=1)
                              if project_title(row[0].value)), subtotal_style)
        book = Workbook()
        book.epoch = base.epoch
        book.loaded_theme = base.loaded_theme
        sheet = book.active
        sheet.title = SHEET
        sheet.sheet_format = copy(template.sheet_format)
        sheet.sheet_view.showGridLines = template.sheet_view.showGridLines
        sheet.page_setup = copy(template.page_setup)
        sheet.page_margins = copy(template.page_margins)
        sheet.print_options = copy(template.print_options)
        for column in 'ABCDEFGHIJKLM':
            if column in template.column_dimensions:
                sheet.column_dimensions[column].width = template.column_dimensions[column].width
        cache = dict(existing_totals or {})
        project_totals = list(cache)
        row = start_row

        def style(target, source):
            style_row(sheet, target, template, source)
            if style_sources is not None:
                style_sources[target] = source

        ordered = sorted(projects, key=lambda project: template_titles[project_key(project.title)].row
                         if project_key(project.title) in template_titles else template.max_row + 1)
        for project in ordered:
            sample_title = template_titles.get(project_key(project.title))
            style(row, sample_title.row if sample_title else 1)
            title = title_with_blanks(project.title, sample_title.value if sample_title else '')
            write_title(sheet.cell(row, 1), title)
            sheet.merge_cells(start_row=row, end_row=row, start_column=1, end_column=11)
            row += 1
            style(row, 2)
            for col in range(1, 12):
                copy_value(sheet.cell(row, col), template.cell(2, col).value)
            row += 1
            if second:
                style(row, 3)
                copy_value(sheet.cell(row, 3), second)
                for col in (1, 2, *range(4, 12)):
                    sheet.merge_cells(start_row=row - 1, end_row=row, start_column=col, end_column=col)
                row += 1
            subtotal_rows = []
            for group in project.groups:
                first = row
                for detail in group.rows:
                    style(row, detail_style)
                    for col, key in enumerate(FIELDS[1:], 2):
                        if key in detail:
                            value, kind, number_format = detail[key]
                            cell = sheet.cell(row, col)
                            copy_value(cell, value, kind)
                            if key in ('expense_date', 'pay_date'):
                                cell.number_format = number_format
                    row += 1
                style(row, subtotal_style)
                copy_value(sheet.cell(row, 3), SUBTOTAL)
                for col in (5, 7):
                    sum_rows(sheet, row, col, first, row - 1, cache)
                if group.subject is not None:
                    copy_value(sheet.cell(first, 1), group.subject)
                    sheet.merge_cells(start_row=first, end_row=row, start_column=1, end_column=1)
                subtotal_rows.append(row)
                row += 1
            style(row, project_style)
            copy_value(sheet.cell(row, 3), '合计')
            for letter in 'EG':
                refs = [f'{letter}{n}' for n in subtotal_rows]
                cell = sheet[f'{letter}{row}']
                cell.value = f'=SUM({",".join(refs)})'
                cache[cell.coordinate] = sum_cached(cache[ref] for ref in refs)
            project_totals.append(f'G{row}')
            row += 1
        style(row, template.max_row)
        sheet[f'G{row}'] = f'=SUM({",".join(project_totals)})'
        cache[f'G{row}'] = sum_cached(cache[ref] for ref in project_totals)
        for number in range(start_row, row + 1):
            sheet.row_dimensions[number].height = row_height
        raw = BytesIO()
        book.save(raw)
        return with_formula_cache(raw, cache)
    finally:
        base.close()


def with_formula_cache(raw, cache):
    output = BytesIO()
    with ZipFile(raw) as archive, ZipFile(output, 'w') as target:
        for item in archive.infolist():
            contents = archive.read(item)
            if item.filename == 'xl/worksheets/sheet1.xml':
                document = parseString(contents)
                for cell in document.getElementsByTagName('c'):
                    coord = cell.getAttribute('r')
                    if coord in cache:
                        value, = cell.getElementsByTagName('v')
                        cached = cache[coord]
                        if isinstance(cached, str):
                            cell.setAttribute('t', 'e')
                        else:
                            cached = format(cached, 'f')
                        value.appendChild(document.createTextNode(cached))
                contents = document.toxml(encoding='utf-8')
            target.writestr(item, contents)
    return output.getvalue()


def merge_inputs(sources, template, month, output, confirmed):
    if not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', month):
        raise ValueError('月份须为 YYYY-MM')
    sources = [Path(path).resolve(strict=True) for path in sources]
    template = Path(template).resolve(strict=True)
    output = Path(output).resolve()
    confirmed = {Path(path).resolve() for path in confirmed}
    if not sources or len(set(sources)) != len(sources) or template in sources:
        raise ValueError('请提供不重复的项目原表，成品样表须单独指定')
    if not confirmed <= set(sources):
        raise ValueError('月份确认须指向本次指定的项目原表')
    if output.suffix.lower() != '.xlsx' or output.exists():
        raise ValueError('输出须为尚不存在的 .xlsx 文件')
    template_data = template.read_bytes()
    fingerprints = {template: sha256(template_data).digest()}
    projects = []
    for path in sources:
        if path.suffix.lower() != '.xlsx' or path.name.startswith('~$'):
            raise ValueError(f'项目原表须为已保存的 .xlsx 文件：{path.name}')
        contents = path.read_bytes()
        fingerprints[path] = sha256(contents).digest()
        projects.extend(read_projects(path, contents, month, path in confirmed))
    return template_data, projects, output, fingerprints


def save_merge(result, output, fingerprints):
    for path, fingerprint in fingerprints.items():
        if sha256(path.read_bytes()).digest() != fingerprint:
            raise ValueError(f'处理期间文件发生变化，请重新合并：{path.name}')
    output.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=output.parent, delete=False) as pending:
        temporary = Path(pending.name)
    try:
        temporary.write_bytes(result)
        os.link(temporary, output)
    finally:
        temporary.unlink()


def merge(sources, template, month, output, confirmed=()):
    template_data, projects, output, fingerprints = merge_inputs(sources, template, month, output, confirmed)
    result = render_plan(template_data, projects)
    save_merge(result, output, fingerprints)
    return {'output': str(output), 'projects': len(projects),
            'rows': sum(len(group.rows) for project in projects for group in project.groups)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', action='append', required=True)
    entry = parser.add_mutually_exclusive_group(required=True)
    entry.add_argument('--template')
    entry.add_argument('--append-to', help='从现有汇总追加新项目，另存新文件')
    parser.add_argument('--month', required=True)
    parser.add_argument('--confirm-month', action='append', default=[])
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if args.append_to:
        from append_plan import append_plan
        result = append_plan(args.source, args.append_to, args.month, args.output, args.confirm_month)
    else:
        result = merge(args.source, args.template, args.month, args.output, args.confirm_month)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError) as exc:
        raise SystemExit(f'合并未完成：{exc}') from None
