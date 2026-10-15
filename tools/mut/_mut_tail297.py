"""守TAIL-297治理工具：登记自测不能假绿、票索引不能空扫、敏感目录不能用旧根、中文幽灵探针有区分力。

源码只在独立模块命名空间改坏，正式文件不作靶；正常自测通过后，坏实现必须断言失败或返回非零。
"""
from pathlib import Path
import contextlib
import io
import types

ROOT=Path(__file__).resolve().parents[2]
CASES=[
    ('tools/oneoff/_oneoff_measure.py','工作树盘点误计缓存','"__pycache__" not in p.parts','True'),
    ('tools/oneoff/_run_muts.py','未登记假绿','return 1 if (gap or stale or orphan_slow) else 0','return 0'),
    ('tools/oneoff/_run_muts.py','实件自测漏对账','    return report_cover()\n\n\nif __name__','    return 0\n\n\nif __name__'),
    ('tools/oneoff/_list_tails.py','历史索引空扫','return a, c, d','return a, c, []'),
    ('tools/oneoff/_prepush_sensitive.py','旧目录假绿','".artifacts/recovery/backups/",','".workbuddy/backups/",'),
    ('tools/oneoff/_prepush_sensitive.py','git失败吞掉', 'return subprocess.run(["git",', 'return ""\n    return subprocess.run(["git",'),
    ('tools/probe/_cn_path_probe.py','中文缺失漏候选','missing.append((i,raw))','pass'),
]


def load(rel,old=None,new=None):
    import sys
    sys.path.insert(0,str(ROOT/'tools/oneoff'))
    module=types.ModuleType('isolated_tail297')
    module.__file__=str(ROOT/rel)
    text=(ROOT/rel).read_text(encoding='utf-8')
    if old is not None:
        assert text.count(old)==1,(rel,old,text.count(old))
        text=text.replace(old,new)
    exec(compile(text,module.__file__,'exec'),module.__dict__)
    if rel.endswith('_oneoff_measure.py'):
        module.selftest=lambda: measure_fixture(module)
    return module


def measure_fixture(module):
    import tempfile
    with tempfile.TemporaryDirectory() as temp:
        folder=Path(temp)
        live=folder/'live'; live.write_text('live',encoding='utf-8')
        archive=folder/'_归档-20990101'; archive.mkdir(); history=archive/'history'; history.write_text('history',encoding='utf-8')
        cache=folder/'__pycache__'; cache.mkdir(); (cache/'cache').write_text('cache',encoding='utf-8')
        assert module.workspace_files(folder)==sorted([live,history]), '实际未提交归档必须在盘点中，缓存不计'
    return 0


def main():
    for rel in dict.fromkeys(r[0] for r in CASES):
        normal=load(rel)
        with contextlib.redirect_stdout(io.StringIO()):
            assert normal.selftest()==0,rel
    for rel,label,old,new in CASES:
        if label=='实件自测漏对账':
            normal=load(rel)
            normal.KEEP_OUT=dict(normal.KEEP_OUT)
            del normal.KEEP_OUT['_mut_tail275.py']
            with contextlib.redirect_stdout(io.StringIO()):
                assert normal.selftest()==1, '真实登记缺口必须红'
        broken=load(rel,old,new)
        # Remove a real registration in memory to prove --selftest inspects live inventory.
        if label=='实件自测漏对账':
            broken.KEEP_OUT=dict(broken.KEEP_OUT)
            del broken.KEEP_OUT['_mut_tail275.py']
        failed=False
        with contextlib.redirect_stdout(io.StringIO()):
            try:
                if label=='实件自测漏对账':
                    assert broken.selftest()==1, '登记缺口被假绿吞掉'
                else:
                    assert broken.selftest()==0
            except AssertionError:
                failed=True
        assert failed,'坏实现未被抓住：'+label
        print('PASS',label,'正常绿 / 坏实现红')
    print(f'PASS 正式文件未写靶；{len(CASES)}项反向灵敏度通过')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
