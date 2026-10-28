"""Annotate OOXML in place without rewriting business cells or formula caches."""
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from hashlib import sha256
from io import BytesIO
import os
from pathlib import Path
import posixpath
from tempfile import NamedTemporaryFile
from xml.dom.minidom import parseString
from zipfile import ZipFile
from openpyxl.utils import column_index_from_string

NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
META = '__付款核对标记'
OWNER = 'payment-plan-audit:v1'
RULE = 'N("payment-plan-audit:v1")=0'
INFO_RULE = 'N("payment-plan-audit:paid")=0'


def children(node, tag):
    return [c for c in node.childNodes if c.nodeType == c.ELEMENT_NODE and c.localName == tag]


def add(parent, tag, attrs=None, value=None):
    node = parent.ownerDocument.createElementNS(parent.namespaceURI, tag)
    for k, v in (attrs or {}).items():
        node.setAttribute(k, str(v))
    if value is not None:
        node.appendChild(parent.ownerDocument.createTextNode(str(value)))
    parent.appendChild(node)
    return node


def string(node):
    return ''.join(n.data for n in node.childNodes if n.nodeType == n.TEXT_NODE)


def value(cell, shared):
    if cell is None:
        return ''
    if cell.getAttribute('t') == 'inlineStr':
        return ''.join(string(n) for n in cell.getElementsByTagNameNS(NS, 't'))
    vs = children(cell, 'v')
    raw = string(vs[0]) if vs else ''
    return shared[int(raw)] if cell.getAttribute('t') == 's' else raw


def write(cell, content):
    for node in list(cell.childNodes):
        cell.removeChild(node)
    cell.setAttribute('t', 'inlineStr')
    add(add(cell, 'is'), 't', {'xml:space': 'preserve'}, content)


def instructions(plan):
    notes, targets, paid_targets = defaultdict(list), set(), set()
    def amount(n):
        value = Decimal(n)
        return format(value, ',.0f') if value == value.to_integral() else format(value, ',.2f')
    duplicates = defaultdict(list)
    for r in plan['rows']:
        if r['doc_no']:
            duplicates[r['doc_no']].append(r['row'])
    for r in plan['rows']:
        if r['final_status'] == '核对通过' and not r.get('month_payments'):
            continue
        def issue(message, key='doc_no'):
            notes[r['row']].append(message)
            targets.add(r['cells'].get(key, f"A{r['row']}"))
            targets.add(f"M{r['row']}")
        n = r['system']
        result = r['audit_result']
        if r.get('month_payments'):
            day = lambda p: f"{int(p['pay_date'][5:7])}/{int(p['pay_date'][8:10])}"
            if sum(Decimal(p['amount']) for p in r['month_payments']) == Decimal(r['planned_amount'] or '0'):
                paid = '、'.join(day(p) for p in r['month_payments'])+('累计' if len(r['month_payments'])>1 else '')+'已付同金额'
            else:
                paid = '、'.join(f"{day(p)}已付{amount(p['amount'])}元" for p in r['month_payments'])
            notes[r['row']].append(paid)
            paid_targets.update((r['cells']['planned_amount'], f"M{r['row']}"))
        if r.get('plan_already_paid'):
            continue
        if result == '无单据号':
            issue('缺单据号')
        elif result == '单据号查不到':
            issue('系统快照中未找到此号')
        elif result == '重复上报':
            issue('单号重复，另见'+'、'.join(str(i) for i in duplicates[r['doc_no']] if i != r['row'])+'行')
        elif result == '超过未付':
            unpaid = Decimal(n['approved'])-Decimal(n['paid'])
            issue(f"计划{amount(r['planned_amount'])}，系统未付{amount(unpaid)}，超{amount(Decimal(r['planned_amount'])-unpaid)}元", 'planned_amount')
        elif result == '金额不符':
            issue(f"流程{amount(r['flow_amount'])}，系统审批{amount(n['approved'])}元", 'flow_amount')
        for problem in r['input_issues']:
            if '流程金额' in problem:
                issue(f"缺流程金额，系统审批{amount(n['approved'])}元" if n else '流程金额缺失或无效', 'flow_amount')
            elif '预付款金额' in problem:
                issue('计划金额缺失或无效', 'planned_amount')
            elif '合同付款方式' in problem:
                issue(problem, 'pay_method')
            elif '付款方式' in problem:
                issue(f"方式“{r['pay_method_raw'] or '空'}”待确认", 'pay_method')
            elif '项目未唯一' in problem:
                issue('项目归属待核：系统为'+r['system_owner'], 'project')
            elif '项目未识别' in problem:
                issue('项目未识别', 'project')
            elif '剔除或撤单' in problem:
                issue('系统已'+('/'.join(x for key, x in [('excluded', '剔除'), ('i8_revoked', '撤单')] if n[key])))
            else:
                issue(problem)
    for warning in plan['source_warnings']:
        cell = warning['cell'].rsplit('!', 1)[1]
        row = int(''.join(c for c in cell if c.isdigit()))
        targets.add(cell)
        targets.add(f'M{row}')
        if warning.get('expected') is not None:
            field = {'flow_amount':'流程汇总','planned_amount':'计划汇总'}.get(warning.get('amount_field'),'汇总')
            notes[row].append(f"{field}{amount(warning['observed'])}，明细和{amount(warning['expected'])}（差{amount(warning['difference'])}元）")
        else:
            notes[row].append(warning['issue'])
    for r in plan['structures']:
        if r['kind'] == '待确认行':
            notes[r['row']].append('行用途待确认，未纳入明细')
            targets.add(f"A{r['row']}")
    targets.update(f'M{row}' for row in notes if f'M{row}' not in paid_targets)
    return {row: '；'.join(dict.fromkeys(messages)) for row, messages in notes.items()}, targets, paid_targets-targets


def appearance(styles):
    """Append only our note styles; preserve every original style definition."""
    root = styles.documentElement
    def collection(tag, before=()):
        nodes = children(root, tag)
        if nodes:
            return nodes[0]
        node = add(root, tag, {'count': 0})
        later = next((n for n in root.childNodes if n.nodeType == n.ELEMENT_NODE and n.localName in before), None)
        if later:
            root.insertBefore(node, later)
        return node
    def intern(parent, node):
        existing = [n for n in parent.childNodes if n.nodeType == n.ELEMENT_NODE]
        found = next((i for i,n in enumerate(existing) if n.toxml() == node.toxml()), None)
        if found is not None:
            return found
        parent.appendChild(node)
        parent.setAttribute('count', str(len(existing)+1))
        return len(existing)
    dxfs = collection('dxfs', ('tableStyles', 'colors', 'extLst'))
    palette = {RULE: ('FFFBE9E7','FF9C3930'), INFO_RULE: ('FFEAF2FA','FF285C87')}
    ids = {}
    for rule, (bg,fg) in palette.items():
        dxf = styles.createElementNS(NS, 'dxf')
        add(add(dxf,'font'), 'color', {'rgb':fg})
        fill = add(add(dxf,'fill'),'patternFill',{'patternType':'solid'})
        add(fill,'fgColor',{'rgb':bg})
        add(fill,'bgColor',{'indexed':64})
        ids[rule] = intern(dxfs,dxf)
    fonts, fills, xfs = collection('fonts'), collection('fills'), collection('cellXfs')
    note_ids = {}
    for kind,fg,bg in [('body','FF334155',None),('header','FFFFFFFF','FF294D68')]:
        font = styles.createElementNS(NS,'font')
        add(font,'sz',{'val':10})
        add(font,'color',{'rgb':fg})
        add(font,'name',{'val':'Microsoft YaHei'})
        if kind == 'header':
            add(font,'b')
        font_id = intern(fonts,font)
        fill = styles.createElementNS(NS,'fill')
        pattern = add(fill,'patternFill',{'patternType':'solid' if bg else 'none'})
        if bg:
            add(pattern,'fgColor',{'rgb':bg})
            add(pattern,'bgColor',{'indexed':64})
        fill_id = intern(fills,fill)
        xf = styles.createElementNS(NS,'xf')
        for key,v in dict(numFmtId=0,fontId=font_id,fillId=fill_id,borderId=0,xfId=0,
                          applyFont=1,applyFill=1,applyAlignment=1).items():
            xf.setAttribute(key,str(v))
        add(xf,'alignment',{'horizontal':'left','vertical':'center','wrapText':1,'indent':1})
        note_ids[kind] = intern(xfs,xf)
    return ids, note_ids


def annotate(plan, backup_dir):
    source = Path(plan['source'])
    original = source.read_bytes()
    if sha256(original).hexdigest() != plan['source_sha256']:
        raise ValueError('原表已变化，未标注；请重新核对')
    if source.with_name('~$'+source.name).exists():
        raise ValueError('Excel可能正打开此表，请保存并关闭后重跑，未覆盖原件')
    with ZipFile(BytesIO(original)) as archive:
        entries = archive.infolist()
        if len({e.filename for e in entries}) != len(entries):
            raise ValueError('工作簿含重名部件，未标注')
        parts = {e.filename: archive.read(e) for e in entries}
    wb = parseString(parts['xl/workbook.xml'])
    rels = parseString(parts['xl/_rels/workbook.xml.rels'])
    sheets = children(wb.documentElement, 'sheets')[0]
    relationships = {n.getAttribute('Id'): n.getAttribute('Target') for n in children(rels.documentElement, 'Relationship')}
    def path_of(s):
        target = relationships[s.getAttributeNS(REL, 'id')]
        return target.lstrip('/') if target.startswith('/') else posixpath.normpath(posixpath.join('xl', target))
    sheet = next(s for s in children(sheets, 'sheet') if s.getAttribute('name') == plan['sheet'])
    path = path_of(sheet)
    ws = parseString(parts[path])
    business_cells = {c.getAttribute('r'): c.toxml() for c in ws.getElementsByTagNameNS(NS, 'c')
                      if c.getAttribute('r').rstrip('0123456789') != 'M'}
    shared = []
    if 'xl/sharedStrings.xml' in parts:
        shared = [''.join(string(t) for t in n.getElementsByTagNameNS(NS, 't'))
                  for n in children(parseString(parts['xl/sharedStrings.xml']).documentElement, 'si')]
    metadata = next((s for s in children(sheets, 'sheet') if s.getAttribute('name') == META), None)
    previous, other_records = {}, []
    if metadata:
        meta_path = path_of(metadata)
        prior = parseString(parts[meta_path])
        cells = {n.getAttribute('r'): n for n in prior.getElementsByTagNameNS(NS, 'c')}
        if value(cells.get('A1'), shared) != OWNER:
            raise ValueError('同名核对元数据表不属于本skill，未覆盖')
        for row in prior.getElementsByTagNameNS(NS, 'row'):
            cs = children(row, 'c')
            if int(row.getAttribute('r')) > 1 and len(cs) == 3:
                record = tuple(value(c, shared) for c in cs)
                if record[0] == plan['sheet']:
                    previous[record[1]] = record[2]
                else:
                    other_records.append(record)
    else:
        meta_path = 'xl/worksheets/paymentPlanAudit.xml'
        if meta_path in parts:
            raise ValueError('核对元数据部件已被占用')
        ids = {n.getAttribute('Id') for n in children(rels.documentElement, 'Relationship')}
        rid = 'rIdPaymentPlanAudit'
        if rid in ids:
            raise ValueError('核对元数据关系已被占用')
        metadata = add(sheets, 'sheet', {'name': META, 'sheetId': max(int(s.getAttribute('sheetId')) for s in children(sheets, 'sheet'))+1, 'state': 'veryHidden'})
        metadata.setAttribute('xmlns:r', REL)
        metadata.setAttributeNS(REL, 'r:id', rid)
        add(rels.documentElement, 'Relationship', {'Id': rid, 'Type': REL+'/worksheet', 'Target': 'worksheets/paymentPlanAudit.xml'})
        types = parseString(parts['[Content_Types].xml'])
        add(types.documentElement, 'Override', {'PartName': '/'+meta_path, 'ContentType': 'application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml'})
        parts['[Content_Types].xml'] = types.toxml(encoding='utf-8')
    data = children(ws.documentElement, 'sheetData')[0]
    rows = {int(r.getAttribute('r')): r for r in children(data, 'row')}
    for row in rows.values():
        for cell in children(row, 'c'):
            if cell.getAttribute('r').rstrip('0123456789') == 'M':
                current = value(cell, shared)
                if not previous and current:
                    raise ValueError('M列已有人工内容，未覆盖；须先确定说明列位置')
                if current in previous:
                    write(cell, previous[current])
    for cf in list(children(ws.documentElement, 'conditionalFormatting')):
        for rule in list(children(cf, 'cfRule')):
            if any(string(f) in (RULE, INFO_RULE) for f in children(rule, 'formula')):
                cf.removeChild(rule)
        if not children(cf, 'cfRule'):
            ws.documentElement.removeChild(cf)
    styles = parseString(parts['xl/styles.xml'])
    style_ids, note_ids = appearance(styles)
    notes, targets, paid_targets = instructions(plan)
    texts = dict(notes)
    texts.update({r['row']: '核对说明' for r in plan['structures'] if r['kind'] == '表头'})
    headers = {r['row'] for r in plan['structures'] if r['kind'] == '表头'}
    records = list(other_records)
    for number, note in sorted(texts.items()):
        row = rows[number]
        cell = next((c for c in children(row, 'c') if c.getAttribute('r') == f'M{number}'), None)
        if cell is None:
            cell = add(row, 'c', {'r': f'M{number}'})
            later = next((c for c in children(row, 'c') if c is not cell and column_index_from_string(c.getAttribute('r').rstrip('0123456789')) > 13), None)
            if later:
                row.insertBefore(cell, later)
        manual = value(cell, shared)
        written = manual+'；'+note if manual else note
        write(cell, written)
        cell.setAttribute('s', str(note_ids['header' if number in headers else 'body']))
        records.append((plan['sheet'], written, manual))
    for rule_formula, addresses in ((RULE, targets), (INFO_RULE, paid_targets)):
        if not addresses:
            continue
        cf = add(ws.documentElement, 'conditionalFormatting', {'sqref': ' '.join(sorted(addresses))})
        later = next((n for n in ws.documentElement.childNodes if n.nodeType == n.ELEMENT_NODE and n.localName in ('dataValidations', 'hyperlinks', 'printOptions', 'pageMargins', 'pageSetup', 'headerFooter', 'drawing', 'legacyDrawing', 'extLst')), None)
        if later:
            ws.documentElement.insertBefore(cf, later)
        priorities = [int(r.getAttribute('priority')) for r in ws.getElementsByTagNameNS(NS, 'cfRule') if r.hasAttribute('priority')]
        add(add(cf, 'cfRule', {'type': 'expression', 'dxfId': style_ids[rule_formula], 'priority': max(priorities, default=0)+1}), 'formula', value=rule_formula)
    cols = children(ws.documentElement, 'cols')
    if not cols:
        cols = add(ws.documentElement, 'cols')
        ws.documentElement.insertBefore(cols, data)
    else:
        cols = cols[0]
    for c in list(children(cols, 'col')):
        low, high = int(c.getAttribute('min')), int(c.getAttribute('max'))
        if low <= 13 <= high:
            for a, b in ((low, 12), (14, high)):
                if a <= b:
                    split = c.cloneNode(True)
                    split.setAttribute('min', str(a))
                    split.setAttribute('max', str(b))
                    cols.insertBefore(split, c)
            cols.removeChild(c)
    note_col = add(cols, 'col', {'min': 13, 'max': 13, 'width': 82, 'customWidth': 1})
    later = next((c for c in children(cols, 'col') if int(c.getAttribute('min')) > 13), None)
    if later:
        cols.insertBefore(note_col, later)
    dimensions = children(ws.documentElement, 'dimension')
    if dimensions and ':' in dimensions[0].getAttribute('ref'):
        end = dimensions[0].getAttribute('ref').split(':')[1]
        if len(end.rstrip('0123456789')) == 1 and end[0] < 'M':
            dimensions[0].setAttribute('ref', 'A1:M'+''.join(c for c in end if c.isdigit()))
    meta = parseString(f'<worksheet xmlns="{NS}"><sheetData/></worksheet>')
    md = children(meta.documentElement, 'sheetData')[0]
    for i, values in enumerate([(OWNER, plan['snapshot']['captured_at'], plan['month']), *records], 1):
        row = add(md, 'row', {'r': i})
        for col, v in zip('ABC', values):
            write(add(row, 'c', {'r': f'{col}{i}'}), v)
    parts.update({path: ws.toxml(encoding='utf-8'), meta_path: meta.toxml(encoding='utf-8'),
                  'xl/styles.xml': styles.toxml(encoding='utf-8'),
                  'xl/workbook.xml': wb.toxml(encoding='utf-8'),
                  'xl/_rels/workbook.xml.rels': rels.toxml(encoding='utf-8')})
    written_cells = {c.getAttribute('r'): c.toxml() for c in parseString(parts[path]).getElementsByTagNameNS(NS, 'c')
                     if c.getAttribute('r').rstrip('0123456789') != 'M'}
    if written_cells != business_cells:
        raise ValueError('标注改变了业务单元格，未替换原件')
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir/(datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+plan['source_sha256'][:12]+'-'+source.name)
    with backup.open('xb') as out:
        out.write(original)
    temp = None
    try:
        with NamedTemporaryFile(dir=source.parent, suffix='.xlsx', delete=False) as out:
            temp = Path(out.name)
        with ZipFile(temp, 'w') as archive:
            for entry in entries:
                archive.writestr(entry, parts.pop(entry.filename))
            for name, content in parts.items():
                archive.writestr(name, content)
        with ZipFile(temp) as archive:
            if archive.testzip():
                raise ValueError('标注工作簿校验失败，原件未替换')
        if sha256(source.read_bytes()).hexdigest() != plan['source_sha256']:
            raise ValueError('标注期间原表变化，未覆盖；请重新核对')
        os.replace(temp, source)
    finally:
        if temp and temp.exists():
            temp.unlink()
    return {'backup': str(backup), 'sha256': sha256(source.read_bytes()).hexdigest(),
            'rows_with_notes': len(notes), 'marked_cells': len(targets|paid_targets)}
