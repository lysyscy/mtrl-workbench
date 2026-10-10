# -*- coding: utf-8 -*-
"""
库存单据回归对账：以「验收标准/库存单据/<年>-<月>.json」为唯一验收依据。
用法:
  python verify_kcdj.py gen <年> <月>      # 生成基准提案（已有验收标准时拒绝覆盖）
  python verify_kcdj.py check <年> <月>    # 对比当前状态与验收标准（默认动作）
  python verify_kcdj.py                    # 等价 check 上月
对账口径: 库 inv_detail 行数与按物料性质（库位）分组金额汇总、单据编号双向差集、
          成品 xlsx 的 sheet 与透视值字段
"""
import os
import sys
import re
import json
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
APP = os.path.join(ROOT, 'app')
OUT = os.path.join(ROOT, 'output')
STD = os.path.join(ROOT, '验收标准', '库存单据')
sys.path.insert(0, APP)


def _db_snapshot(month):
    """inv_detail 快照：总行数 + 按物料性质行数与金额汇总 + 单据编号集合"""
    import sqlite3
    conn = sqlite3.connect(os.path.join(APP, 'data', 'workbench.db'))
    try:
        total = conn.execute('SELECT COUNT(*) FROM inv_detail WHERE month=?',
                             (month,)).fetchone()[0]
        rows = conn.execute(
            'SELECT 物料性质 AS k, COUNT(*) AS cnt, SUM(金额) AS amt '
            'FROM inv_detail WHERE month=? GROUP BY 物料性质 ORDER BY k',
            (month,)).fetchall()
        groups = {r[0]: {'rows': r[1], '金额': round(r[2] or 0, 2)} for r in rows}
        doc_ids = sorted(x[0] for x in conn.execute(
            'SELECT DISTINCT 单据编号 FROM inv_detail WHERE month=?', (month,)))
        return {'month': month, 'total_rows': total, 'groups': groups,
                'doc_count': len(doc_ids), 'doc_ids': doc_ids}
    finally:
        conn.close()


def _xlsx_features(path):
    """zip 层读 xlsx：sheet 名 + 各透视表值字段（避免 openpyxl 打开 WPS 透视文件）"""
    try:
        with zipfile.ZipFile(path) as z:
            wb = z.read('xl/workbook.xml').decode('utf-8')
            sheets = re.findall(r'<[^>]*sheet[^>]*name="([^"]+)"', wb)
            pivots = {}
            for n in z.namelist():
                m = re.match(r'xl/pivotTables/pivotTable(\d+)\.xml$', n)
                if m:
                    xml = z.read(n).decode('utf-8')
                    dfs = re.findall(r'<dataField[^>]*name="([^"]+)"', xml)
                    pivots[m.group(1)] = dfs
            return {'sheets': sheets, 'pivots': pivots}
    except Exception:
        return None


def _product_snapshot(y, m):
    """成品 xlsx：文件名 + 结构特征，找不到返回 None"""
    d = os.path.join(OUT, '库存单据明细表', '%d年%d月' % (y, m))
    if not os.path.isdir(d):
        return None
    xs = [f for f in os.listdir(d) if f.endswith('.xlsx')]
    if not xs:
        return None
    p = os.path.join(d, xs[0])
    feat = _xlsx_features(p)
    return {'file': xs[0], 'size': os.path.getsize(p), 'xlsx': feat}


def _std_path(month):
    return os.path.join(STD, month + '.json')


def gen(y, m):
    os.makedirs(STD, exist_ok=True)
    month = '%04d-%02d' % (y, m)
    path = _std_path(month)
    if os.path.exists(path):
        print('!! 验收标准已存在（%s）' % path)
        print('   不覆盖。如需更新：删除该文件后重新 gen，或直接编辑。')
        return 3
    snap = {'db': _db_snapshot(month), 'product': _product_snapshot(y, m)}
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(snap, f, ensure_ascii=False, indent=1)
    print('基准提案已生成: %s' % path)
    print('  库行数: %d, 单据编号: %d, 物料性质分组: %s, 成品: %s' % (
        snap['db']['total_rows'], snap['db']['doc_count'],
        ', '.join('%s(%d行)' % (k, v['rows']) for k, v in snap['db']['groups'].items()),
        (snap['product'] or {}).get('file', '无')))
    print('  提示：请人工核对后确认；此文件即验收标准，之后 check 以它为准。')
    return 0


def check(y, m):
    month = '%04d-%02d' % (y, m)
    path = _std_path(month)
    if not os.path.exists(path):
        print('!! 该月无验收标准（%s）' % path)
        print('   需先由人工核对成品后生成基准：python verify_kcdj.py gen %d %d' % (y, m))
        return 2
    with open(path, encoding='utf-8') as f:
        base = json.load(f)
    problems = []

    # 1) 库对账（行数 + 物料性质分组）
    cur = _db_snapshot(month)
    b = base['db']
    if cur['total_rows'] != b['total_rows']:
        problems.append('库行数: 基准 %d vs 当前 %d' % (b['total_rows'], cur['total_rows']))
    for k, bv in b['groups'].items():
        cv = cur['groups'].get(k)
        if not cv:
            problems.append('分组 %s 缺失（基准 %d 行）' % (k, bv['rows']))
            continue
        if cv['rows'] != bv['rows'] or abs(cv['金额'] - bv['金额']) > 0.01:
            problems.append('分组 %s: 基准 %d行/%s vs 当前 %d行/%s'
                            % (k, bv['rows'], bv['金额'], cv['rows'], cv['金额']))
    for k in cur['groups']:
        if k not in b['groups']:
            problems.append('多出分组 %s（当前 %d 行）' % (k, cur['groups'][k]['rows']))

    # 2) 单据编号差集
    if 'doc_ids' in b:
        bd, cd = set(b['doc_ids']), set(cur['doc_ids'])
        for d in sorted(bd - cd):
            problems.append('单据编号缺失: %s' % d)
        for d in sorted(cd - bd):
            problems.append('多出单据编号: %s' % d)

    # 3) 成品结构对账
    cp = _product_snapshot(y, m)
    bp = base.get('product')
    if bp is None and cp is not None:
        problems.append('成品: 基准无，当前有 %s' % cp['file'])
    elif bp is not None and cp is None:
        problems.append('成品: 基准有 %s，当前缺失' % bp['file'])
    elif bp and cp:
        bx, cx = bp.get('xlsx'), cp.get('xlsx')
        if bx and cx:
            if bx.get('sheets') != cx.get('sheets'):
                problems.append('成品sheet: 基准 %s vs 当前 %s' % (bx.get('sheets'), cx.get('sheets')))
            if bx.get('pivots') != cx.get('pivots'):
                problems.append('透视值字段: 基准 %s vs 当前 %s' % (bx.get('pivots'), cx.get('pivots')))
        elif bx != cx:
            problems.append('成品特征: 基准 %s vs 当前 %s' % (bx, cx))

    if problems:
        print('!! 与验收标准不一致（%d 处）：' % len(problems))
        for p in problems:
            print('  -', p)
        return 1
    print('✔ 对账通过：库 %d 行 / %d 单据编号 / %d 分组，成品 %s' % (
        cur['total_rows'], cur['doc_count'], len(cur['groups']),
        (cp or {}).get('file', '无')))
    return 0


def main():
    args = sys.argv[1:]
    action = 'check'
    if args and args[0] in ('gen', 'check'):
        action = args[0]
        args = args[1:]
    if len(args) < 2:
        import datetime
        now = datetime.datetime.now()
        y, m = now.year, now.month
    else:
        y, m = int(args[0]), int(args[1])
    return gen(y, m) if action == 'gen' else check(y, m)


if __name__ == '__main__':
    sys.exit(main())
