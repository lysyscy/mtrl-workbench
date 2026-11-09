"""Append project blocks to a completed summary while retaining its original Excel parts."""
from decimal import Decimal
from io import BytesIO
import posixpath
import re
from xml.dom.minidom import parseString
from zipfile import ZipFile

from openpyxl import load_workbook
from openpyxl.formula import Tokenizer
from openpyxl.formula.tokenizer import TokenizerError
from openpyxl.styles.numbers import BUILTIN_FORMATS_REVERSE
from openpyxl.utils.cell import coordinate_from_string, get_column_letter, range_boundaries

from annotate import NS, REL, add, children
from merge import SHEET, dated_title, merge_inputs, norm, project_key, project_title, render_plan, save_merge


def references_row(formula, sheet, row):
    try:
        tokens = Tokenizer(formula).items
    except TokenizerError as error:
        raise ValueError('现有汇总含无法核实引用范围的公式') from error
    for token in tokens:
        if token.subtype != 'RANGE':
            continue
        scope, sep, cells = token.value.rpartition('!')
        target = scope.removeprefix("'").removesuffix("'").replace("''", "'") if sep else sheet
        if target is None or target.casefold() != SHEET.casefold():
            continue
        try:
            _, first, _, last = range_boundaries(cells)
        except ValueError:
            continue
        if first is None or first <= row <= last:
            return True
    return False


def summary_totals(contents, month, projects):
    book = load_workbook(BytesIO(contents), keep_links=False)
    saved = load_workbook(BytesIO(contents), data_only=True, keep_links=False)
    try:
        if SHEET not in book.sheetnames:
            raise ValueError(f'现有汇总缺少「{SHEET}」')
        sheet = book[SHEET]
        last = sheet.max_row
        if (sheet.protection.sheet or any(cell.value is not None for cell in sheet[last] if cell.column != 7)
                or any(r.max_row >= last for r in sheet.merged_cells.ranges)):
            raise ValueError('现有汇总末行须为独立的全表总计')
        old_projects = set()
        totals = []
        pending = False
        for cells in sheet.iter_rows(max_row=last - 1, max_col=3):
            first, _, label = cells
            if project_title(first.value):
                key = project_key(dated_title(str(first.value), month, False, f'{SHEET}!{first.coordinate}'))
                if pending or key in old_projects:
                    raise ValueError('现有汇总的项目区块或项目合计不唯一')
                pending = True
                old_projects.add(key)
            elif norm(label.value) == '合计':
                if not pending:
                    raise ValueError('现有汇总的项目合计缺少对应项目')
                pending = False
                totals.append(f'G{label.row}')
        formula = re.sub(r'[\s$]', '', str(sheet[f'G{last}'].value)).upper()
        if not totals or pending or formula != f'=SUM({",".join(totals)})':
            raise ValueError('现有汇总须以一个引用各项目合计的全表总计结束')
        for ws in book:
            for cells in ws.iter_rows():
                for cell in cells:
                    if cell.data_type != 'f' or (ws == sheet and cell.coordinate == f'G{last}'):
                        continue
                    context = SHEET if ws == sheet else None
                    if not isinstance(cell.value, str) or references_row(cell.value, context, last):
                        raise ValueError(f'{ws.title}!{cell.coordinate} 有需先处理的汇总行引用或特殊公式')
            for name in ws.defined_names.values():
                if references_row('=' + name.attr_text, ws.title, last):
                    raise ValueError(f'名称「{name.name}」引用现有汇总末行，无法安全追加')
        for name in book.defined_names.values():
            if references_row('=' + name.attr_text, None, last):
                raise ValueError(f'名称「{name.name}」引用现有汇总末行，无法安全追加')
        new_projects = set()
        for project in projects:
            key = project_key(project.title)
            if key in old_projects or key in new_projects:
                raise ValueError(f'项目已存在或重复补报：{key}')
            new_projects.add(key)
        cached = {ref: saved[SHEET][ref].value for ref in totals}
        if any(type(value) not in (int, float) for value in cached.values()):
            raise ValueError('现有项目合计缺少有效保存值，请用 Excel 重算并保存')
        return last, {ref: Decimal(str(value)) for ref, value in cached.items()}
    finally:
        saved.close()
        book.close()


class Styles:
    def __init__(self, document):
        self.root = document.documentElement
        formats = children(self.root, 'numFmts')
        self.formats = formats[0] if formats else None
        self.ids = dict(BUILTIN_FORMATS_REVERSE)
        if self.formats is not None:
            self.ids.update((f.getAttribute('formatCode'), int(f.getAttribute('numFmtId')))
                            for f in children(self.formats, 'numFmt'))
        self.xfs, = children(self.root, 'cellXfs')
        self.base = children(self.xfs, 'xf')
        self.modified = {}

    def with_format(self, base, code):
        fmt = self.ids.get(code)
        if fmt is None:
            if self.formats is None:
                self.formats = self.root.ownerDocument.createElementNS(NS, 'numFmts')
                self.root.insertBefore(self.formats, self.root.firstChild)
            fmt = self.ids[code] = max(163, *self.ids.values()) + 1
            add(self.formats, 'numFmt', {'numFmtId': fmt, 'formatCode': code})
            self.formats.setAttribute('count', str(len(children(self.formats, 'numFmt'))))
        node = self.base[base]
        if int(node.getAttribute('numFmtId') or 0) == fmt:
            return base
        key = (base, fmt)
        if key not in self.modified:
            clone = node.cloneNode(deep=True)
            clone.setAttribute('numFmtId', str(fmt))
            clone.setAttribute('applyNumberFormat', '1')
            self.modified[key] = len(self.base) + len(self.modified)
            self.xfs.appendChild(clone)
            self.xfs.setAttribute('count', str(len(self.base) + len(self.modified)))
        return self.modified[key]


def append_rows(contents, rendered, style_sources, first):
    formats = {}
    stage = load_workbook(BytesIO(rendered), data_only=True)
    try:
        sheet = stage[SHEET]
        last = sheet.max_row
        for row in range(first, last):
            for col in 'BI':
                cell = sheet[f'{col}{row}']
                if cell.value is not None and cell.is_date:
                    formats[cell.coordinate] = cell.number_format
    finally:
        stage.close()
    result = BytesIO()
    with ZipFile(BytesIO(contents)) as source, ZipFile(BytesIO(rendered)) as staged, ZipFile(result, 'w') as output:
        workbook = parseString(source.read('xl/workbook.xml'))
        sheets, = children(workbook.documentElement, 'sheets')
        sheet = next(node for node in children(sheets, 'sheet') if node.getAttribute('name') == SHEET)
        rels = parseString(source.read('xl/_rels/workbook.xml.rels'))
        relation = sheet.getAttributeNS(REL, 'id')
        path = next(node.getAttribute('Target') for node in children(rels.documentElement, 'Relationship')
                    if node.getAttribute('Id') == relation)
        path = path.lstrip('/') if path.startswith('/') else posixpath.normpath(posixpath.join('xl', path))
        document = parseString(source.read(path))
        root = document.documentElement
        if ('xl/calcChain.xml' in source.namelist() or
                any(children(root, tag) for tag in ('tableParts', 'drawing', 'legacyDrawing', 'autoFilter'))):
            raise ValueError('现有汇总包含表对象、图形、筛选或独立计算链，无法安全追加')
        styles_doc = parseString(source.read('xl/styles.xml'))
        styles = Styles(styles_doc)
        rows, = children(root, 'sheetData')
        old_rows = children(rows, 'row')
        total = old_rows[-1]
        if int(total.getAttribute('r')) != first:
            raise ValueError('现有汇总的全表总计行位置不明确')
        old_styles = {c.getAttribute('r'): int(c.getAttribute('s') or 0)
                      for row in old_rows for c in children(row, 'c')}
        generated = parseString(staged.read('xl/worksheets/sheet1.xml')).documentElement
        rendered_rows, = children(generated, 'sheetData')
        new_rows = children(rendered_rows, 'row')
        for new in new_rows[:-1]:
            number = int(new.getAttribute('r'))
            added = document.importNode(new, deep=True)
            for cell in children(added, 'c'):
                coord = cell.getAttribute('r')
                column, _ = coordinate_from_string(coord)
                base = old_styles.get(f'{column}{style_sources[number]}', 0)
                style = styles.with_format(base, formats[coord]) if coord in formats else base
                cell.setAttribute('s', str(style))
            rows.insertBefore(added, total)
        total.setAttribute('r', str(last))
        rendered_total, = (cell for cell in children(new_rows[-1], 'c') if cell.getAttribute('r') == f'G{last}')
        for cell in children(total, 'c'):
            column, _ = coordinate_from_string(cell.getAttribute('r'))
            cell.setAttribute('r', f'{column}{last}')
            if column == 'G':
                if rendered_total.hasAttribute('t'):
                    cell.setAttribute('t', rendered_total.getAttribute('t'))
                elif cell.hasAttribute('t'):
                    cell.removeAttribute('t')
                for tag in ('f', 'v'):
                    old, = children(cell, tag)
                    new, = children(rendered_total, tag)
                    cell.replaceChild(document.importNode(new, deep=True), old)
        dimensions, = children(root, 'dimension')
        min_col, min_row, max_col, _ = range_boundaries(dimensions.getAttribute('ref'))
        dimensions.setAttribute('ref', f'{get_column_letter(min_col)}{min_row}:{get_column_letter(max(max_col, 12))}{last}')
        generated_merges, = children(generated, 'mergeCells')
        merges = children(root, 'mergeCells')
        if merges:
            merges = merges[0]
        else:
            merges = document.createElementNS(NS, 'mergeCells')
            root.insertBefore(merges, rows.nextSibling)
        for node in children(generated_merges, 'mergeCell'):
            merges.appendChild(document.importNode(node, deep=True))
        merges.setAttribute('count', str(len(children(merges, 'mergeCell'))))
        replacements = {path: document}
        if styles.modified:
            replacements['xl/styles.xml'] = styles_doc
        if extend_print_area(workbook, sheets, sheet, first, last):
            replacements['xl/workbook.xml'] = workbook
        for entry in source.infolist():
            changed = replacements.get(entry.filename)
            output.writestr(entry, changed.toxml(encoding='UTF-8') if changed else source.read(entry))
    return result.getvalue()


def extend_print_area(workbook, sheets, sheet, first, last):
    sheet_index = str(children(sheets, 'sheet').index(sheet))
    changed = False
    for container in children(workbook.documentElement, 'definedNames'):
        for name in children(container, 'definedName'):
            if name.getAttribute('name') != '_xlnm.Print_Area' or name.getAttribute('localSheetId') != sheet_index:
                continue
            for node in name.childNodes:
                if node.nodeType == node.TEXT_NODE:
                    revised = re.sub(rf'(:\$?[A-Z]{{1,3}}\$?){first}(?=,|$)', rf'\g<1>{last}', node.data)
                    changed |= revised != node.data
                    node.data = revised
    return changed


def append_plan(sources, summary, month, output, confirmed=()):
    contents, projects, output, fingerprints = merge_inputs(sources, summary, month, output, confirmed)
    first, existing = summary_totals(contents, month, projects)
    style_sources = {}
    rendered = render_plan(contents, projects, start_row=first, existing_totals=existing, style_sources=style_sources)
    result = append_rows(contents, rendered, style_sources, first)
    save_merge(result, output, fingerprints)
    return {'output': str(output)}
