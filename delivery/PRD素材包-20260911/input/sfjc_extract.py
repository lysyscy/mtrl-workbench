# -*- coding: utf-8 -*-
"""
收发结存表 → 焊材/气体入库金额提取（月度经济分析会用）
- 复用 sfjc_process.read_raw（拆合并/剔合计/转数字）
- 气体：D列资源名称 **白名单精确匹配**（config: gas_list，| 分隔；仅统计名单内物料，误伤免疫，新气体加名单即可）
- 焊材：D列资源名称 含 焊丝|焊条|焊锡丝（关键词初筛 + not_weld 子串排除，极大概率全是焊材）
- 按仓库（A列）汇总 L列收金额；名单/关键词均可配置（config 表，DB 优先）
用法（库内函数，程序壳调用）:
    from sfjc_extract import extract_data
    data = extract_data(path, gas_list=..., weld_kw=..., not_weld=...)  # 由 export_runner 从 config 传入
    # -> {'气体': {仓库: 金额}, '气体明细': [(物料, 金额)...], '焊材': {...}, '焊材明细': [...]}
"""
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

# 仅在本模块被独立运行（不经过程序壳）时兜底；正式链路由 export_runner 从 config 传入。
# 值与 app\db.py DEFAULT_CONFIG 保持一致，改动请同步两处
DEFAULT_GAS = '液氩|氩气|二氧化碳|二氧化碳气|液氧|丙烷|氧气'


def _matched(df, kws, exclude):
    """关键词初筛 + 子串排除名单；返回 (汇总dict, 物料清单list[(物料,金额)])"""
    pat = '|'.join(x for x in (kws or '').split('|') if x)
    if not pat:
        return {}, []
    mask = df['资源名称'].astype(str).str.contains(pat, na=False, regex=True)
    if exclude:
        ex = [x for x in exclude.split('|') if x]
        if ex:
            mask &= ~df['资源名称'].str.contains('|'.join(ex), na=False, regex=True)
    sub = df[mask]
    items = []
    for name, grp in sub.groupby('资源名称'):
        items.append((str(name), round(float(grp['收金额'].sum()), 2)))
    by_wh = {str(w): round(float(v), 2) for w, v in sub.groupby('仓库')['收金额'].sum().items()}
    return by_wh, sorted(items, key=lambda x: -x[1])


def extract_data(path, gas_list=None, weld_kw=None, not_weld=None):
    """读收发结存原始导出，返回 气体(白名单)/焊材 按仓库汇总 + 物料明细（供核对名单）"""
    import sfjc_process
    df = sfjc_process.read_raw(path)
    gas_list = gas_list if gas_list is not None else DEFAULT_GAS
    weld_kw = weld_kw if weld_kw is not None else '焊丝|焊条|焊锡丝'
    not_weld = not_weld if not_weld is not None else ''
    gl = set(x for x in gas_list.split('|') if x)
    gas_df = df[df['资源名称'].astype(str).isin(gl)]
    gas_wh = {str(w): round(float(v), 2) for w, v in gas_df.groupby('仓库')['收金额'].sum().items()}
    gas_items = [(str(n), round(float(g['收金额'].sum()), 2)) for n, g in gas_df.groupby('资源名称')]
    weld_wh, weld_items = _matched(df, weld_kw, not_weld)
    return {
        '气体': gas_wh, '气体明细': sorted(gas_items, key=lambda x: -x[1]),
        '焊材': weld_wh, '焊材明细': weld_items,
    }


if __name__ == '__main__':
    src = sys.argv[1] if len(sys.argv) > 1 else None
    if not src:
        print('用法: python sfjc_extract.py <收发结存原始导出.xlsx>')
        sys.exit(1)
    r = extract_data(src)
    for cat in ('气体', '焊材'):
        print('==== %s 按仓库汇总 ====' % cat)
        for wh, amt in sorted(r[cat].items()):
            print('  %s: %.2f' % (wh, amt))
        print('  合计: %.2f' % sum(r[cat].values()))
        print('  ---- 物料明细（核对名单用）----')
        for name, amt in r[cat + '明细']:
            print('    %s: %.2f' % (name, amt))
