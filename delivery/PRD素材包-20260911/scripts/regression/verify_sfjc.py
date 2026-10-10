# -*- coding: utf-8 -*-
"""
收发结存回归对账：以「验收标准/收发结存/<年>-<月>.json」为唯一验收依据。
用法:
  python verify_sfjc.py gen <年> <月>      # 生成基准提案（已有验收标准时拒绝覆盖）
  python verify_sfjc.py check <年> <月>    # 对比当前状态与验收标准（默认动作）
  python verify_sfjc.py                    # 等价 check 上月
验收标准目录: 项目根\验收标准\收发结存\（用户手工核对通过的文件放这里，我以它为准）
对账口径: 库 stock_monthly 行数与各仓库金额汇总（期初/收/发/结存）、
          成品 zip 文件清单、总表 xlsx 的 sheet 与透视值字段、mtrl_extract 焊材/气体提取
"""
import os
import sys
import re
import json
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
APP = os.path.join(ROOT, 'app')
OUT = os.path.join(ROOT, 'output')
STD = os.path.join(ROOT, '验收标准', '收发结存')
sys.path.insert(0, APP)

MONEY = ['期初金额', '收金额', '发金额', '结存金额']


def _db_snapshot(month):
    """库快照：总行数 + 按仓库行数与四金额汇总"""
    import sqlite3
    conn = sqlite3.connect(os.path.join(APP, 'data', 'workbench.db'))
    conn.row_factory = sqlite3.Row
    try:
        total = conn.execute('SELECT COUNT(*) FROM stock_monthly WHERE month=?',
                             (month,)).fetchone()[0]
        rows = conn.execute(
            'SELECT 仓库, COUNT(*) AS cnt, '
            'SUM(期初金额) AS s0, SUM(收金额) AS s1, SUM(发金额) AS s2, SUM(结存金额) AS s3 '
            'FROM stock_monthly WHERE month=? GROUP BY 仓库 ORDER BY 仓库',
            (month,)).fetchall()
        wh = {}
        for r in rows:
            wh[r['仓库']] = {'rows': r['cnt'],
                             '期初金额': round(r['s0'] or 0, 2),
                             '收金额': round(r['s1'] or 0, 2),
                             '发金额': round(r['s2'] or 0, 2),
                             '结存金额': round(r['s3'] or 0, 2)}
        return {'month': month, 'total_rows': total, 'warehouses': wh}
    finally:
        conn.close()


def _mtrl_snapshot(month):
    """mtrl_extract 快照：cat → 仓库 → 金额"""
    import sqlite3
    conn = sqlite3.connect(os.path.join(APP, 'data', 'workbench.db'))
    try:
        rows = conn.execute(
            'SELECT cat, wh, amount FROM mtrl_extract WHERE month=? '
            'ORDER BY cat, wh', (month,)).fetchall()
        out = {}
        for cat, wh, amt in rows:
            out.setdefault(cat, {})[wh] = round(amt or 0, 2)
        return out
    finally:
        conn.close()


def _xlsx_features(src):
    """zip 层读 xlsx（src 为 xlsx 路径或文件字节）：sheet 名列表 + 各透视表值字段
    （不依赖 openpyxl，避免 WPS Nested 报错）"""
    import io as _io
    try:
        if isinstance(src, (bytes, bytearray)):
            zf = zipfile.ZipFile(_io.BytesIO(src))
        else:
            zf = zipfile.ZipFile(src)
        with zf as z:
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


def _zip_snapshot(y, m):
    """成品zip：文件名清单 + 总表（体积最大 xlsx）特征，找不到返回 None"""
    d = os.path.join(OUT, '收发结存', '%d年%d月' % (y, m))
    if not os.path.isdir(d):
        return None
    zips = [f for f in os.listdir(d) if f.endswith('.zip')]
    if not zips:
        return None
    zp = os.path.join(d, zips[0])
    with zipfile.ZipFile(zp) as zf:
        files = sorted((i.filename, i.file_size) for i in zf.infolist())
        big = max((i for i in zf.infolist()
                   if i.filename.endswith('.xlsx')), key=lambda i: i.file_size, default=None)
        feat = _xlsx_features(zf.read(big.filename)) if big else None
    return {'zip': zips[0], 'files': files,
            'size': os.path.getsize(zp),
            'main_xlsx': big.filename if big else None,
            'xlsx': feat}


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
    snap = {'db': _db_snapshot(month),
            'mtrl': _mtrl_snapshot(month),
            'zip': _zip_snapshot(y, m)}
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(snap, f, ensure_ascii=False, indent=1)
    print('基准提案已生成: %s' % path)
    print('  库行数: %d, 仓库数: %d, 提取: %s, zip: %s' % (
        snap['db']['total_rows'], len(snap['db']['warehouses']),
        sum(len(v) for v in snap['mtrl'].values()),
        (snap['zip'] or {}).get('zip', '无')))
    print('  提示：请人工核对后确认；此文件即验收标准，之后 check 以它为准。')
    return 0


def check(y, m):
    month = '%04d-%02d' % (y, m)
    path = _std_path(month)
    if not os.path.exists(path):
        print('!! 该月无验收标准（%s）' % path)
        print('   需先由人工核对成品后生成基准：python verify_sfjc.py gen %d %d' % (y, m))
        return 2
    with open(path, encoding='utf-8') as f:
        base = json.load(f)
    problems = []

    # 1) 库对账
    cur = _db_snapshot(month)
    b = base['db']
    if cur['total_rows'] != b['total_rows']:
        problems.append('库行数: 基准 %d vs 当前 %d' % (b['total_rows'], cur['total_rows']))
    for wh, bwh in b['warehouses'].items():
        cwh = cur['warehouses'].get(wh)
        if not cwh:
            problems.append('仓库 %s 缺失（基准 %d 行）' % (wh, bwh['rows']))
            continue
        for k in ['rows'] + MONEY:
            if abs(cwh[k] - bwh[k]) > 0.01:
                problems.append('仓库 %s %s: 基准 %s vs 当前 %s' % (wh, k, bwh[k], cwh[k]))
    for wh in cur['warehouses']:
        if wh not in b['warehouses']:
            problems.append('多出仓库 %s（当前 %d 行）' % (wh, cur['warehouses'][wh]['rows']))

    # 2) 焊材/气体提取对账
    if 'mtrl' in base:
        cm = _mtrl_snapshot(month)
        bm = base['mtrl']
        keys = set(bm) | set(cm)
        for cat in sorted(keys):
            for wh in sorted(set(bm.get(cat, {})) | set(cm.get(cat, {}))):
                av, cv = bm.get(cat, {}).get(wh, 0), cm.get(cat, {}).get(wh, 0)
                if abs(av - cv) > 0.01:
                    problems.append('提取 %s %s: 基准 %s vs 当前 %s' % (cat, wh, av, cv))

    # 3) 成品 zip 对账（文件清单 + 总表结构）
    cz = _zip_snapshot(y, m)
    bz = base.get('zip')
    if bz is None and cz is not None:
        problems.append('成品zip: 基准无，当前有 %s' % cz['zip'])
    elif bz is not None and cz is None:
        problems.append('成品zip: 基准有 %s，当前缺失' % bz['zip'])
    elif bz and cz:
        bf = set(n for n, _ in bz['files'])
        cf = set(n for n, _ in cz['files'])
        for n in sorted(bf - cf):
            problems.append('zip缺文件: %s' % n)
        for n in sorted(cf - bf):
            problems.append('zip多出文件: %s' % n)
        bx, cx = bz.get('xlsx'), cz.get('xlsx')
        if bx and cx:
            if bx.get('sheets') != cx.get('sheets'):
                problems.append('总表sheet: 基准 %s vs 当前 %s' % (bx.get('sheets'), cx.get('sheets')))
            if bx.get('pivots') != cx.get('pivots'):
                problems.append('透视值字段: 基准 %s vs 当前 %s' % (bx.get('pivots'), cx.get('pivots')))
        elif bx != cx:
            problems.append('总表特征: 基准 %s vs 当前 %s' % (bx, cx))

    if problems:
        print('!! 与验收标准不一致（%d 处）：' % len(problems))
        for p in problems:
            print('  -', p)
        return 1
    print('✔ 对账通过：库 %d 行 / %d 仓库，提取 %d 项，zip %s（%d 文件）' % (
        cur['total_rows'], len(cur['warehouses']),
        sum(len(v) for v in _mtrl_snapshot(month).values()),
        (cz or {}).get('zip', '无'), len((cz or {}).get('files', []))))
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
