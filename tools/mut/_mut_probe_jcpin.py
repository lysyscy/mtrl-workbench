"""守贸易列显隐后的重量判据：正常默认隐藏可通过，省掉切换的隔离探针必须报红。"""
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'tools/probe')]
from _mut_probe_m11 import _open
from playwright.sync_api import sync_playwright
import _shell_jcpin


def main():
    with sync_playwright() as pw:
        page=_open(pw)
        errors=[]
        _shell_jcpin.check(page,errors)
        assert not errors,errors
        print('normal hidden baseline PASS')
        source=(ROOT/'tools/probe/_shell_jcpin.py').read_text(encoding='utf-8')
        anchor='page.click("#jcTradeBtn")'
        assert source.count(anchor)==2
        ns={'__name__':'isolated_jcpin'}
        exec(source.replace(anchor,'None'),ns)
        errors=[]
        ns['check'](page,errors)
        assert any('宽度没变' in e for e in errors),errors
        print('no-toggle RED width assertion confirmed; no file/database writes')
        page.context.browser.close()
    return 0


if __name__=='__main__':
    raise SystemExit(main())
