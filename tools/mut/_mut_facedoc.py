"""交付面文档保护的隔离自证：调用同一实现处理副本，不写正式交付面。

页脚后内容、缺件及能力编号损失仍报红；仅篇幅缩短作为需调查的提示。
保护有效要求的可见性，不把历史WPS同步事故变成永远只许增字的规则。
"""
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools/audit'))
from audit_face import check_footer_tail, check_prd_baseline
from audit_common import FOOTER_MARKER, RED, YELLOW


def main():
    with tempfile.TemporaryDirectory(prefix='mtrl-face-proof-') as temp:
        root = Path(temp)
        file = root/'PRD/02-功能规格/MOD-11.md'
        file.parent.mkdir(parents=True)
        normal = '# Example\n\n| 1 | A |\n| 2 | B |\n\n'+FOOTER_MARKER+'：fixture\n'
        file.write_text(normal, encoding='utf-8')
        baseline = {file.relative_to(root).as_posix(): (len(normal.splitlines()), 2)}
        assert not check_prd_baseline(root, baseline), '正常件不可误伤'
        assert not check_footer_tail(root), '正常页脚不可误伤'
        file.write_text(normal+'Important\n', encoding='utf-8')
        assert any(h['level']==RED for h in check_footer_tail(root)), '页脚后条目必须可见'
        file.write_text(normal.replace('\n\n','\n'), encoding='utf-8')
        hits = check_prd_baseline(root, baseline)
        assert any(h['level']==YELLOW for h in hits) and not any(h['level']==RED for h in hits), '仅缩短提示调查，不拦截已授权精简'
        file.write_text(normal.replace('| 2 | B |', '| B | B |'), encoding='utf-8')
        assert any(h['level']==RED for h in check_prd_baseline(root, baseline)), '能力编号损失不能免验'
        file.unlink()
        assert any(h['level']==RED for h in check_prd_baseline(root, baseline)), '缺件不能免验'
        file.write_text(normal+'\n', encoding='utf-8')
        assert not check_prd_baseline(root, baseline), '正常增字不可误伤'
    print('隔离自证：正常放行、页脚丢落、篇幅提示、能力编号损失、缺件及正常增长通过')
    return 0


if __name__=='__main__':
    sys.exit(main())
