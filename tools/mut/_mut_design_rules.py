"""守则结构检查的反向灵敏度：真实测试读取隔离文档，缺引用、空栏和失效定义须报红。"""
from __future__ import annotations

import hashlib
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from tests import test_design_rules as rules


def main() -> int:
    original = rules.DOC
    before = hashlib.sha256(original.read_bytes()).hexdigest()
    text = original.read_text(encoding='utf-8')
    rows = rules._rule_rows(text)
    checks = [rules.test_守则的引用都落得住,
              rules.test_守则每条栏位齐全_判据不许空,
              rules.test_守则的执行层只写执行形态_定义指回前面,
              rules.test_守则的原话可追溯_附录不作口径]
    with tempfile.TemporaryDirectory(prefix='mtrl-design-rules-') as folder:
        # Keep the same document-root shape; reference checks use the real shell source.
        doc = Path(folder) / 'ops' / original.name
        doc.parent.mkdir()
        rules.DOC = doc
        try:
            doc.write_text(text, encoding='utf-8')
            for check in checks:
                check()
            print('正常文档：四项通过')
            cases = [
                ('删除被壳引用的状态规则', '\n'.join(line for line in text.splitlines()
                  if not line.startswith('| §4.2 |')), checks[0]),
                ('清空规则判据栏', text.replace('| §1.1 | 使用用户需要感知这个元素吗？ | 业务操作与决策需要的保留；排障信息放在对应排障区域。 | 实际任务与角色走查。 |',
                  '| §1.1 | 使用用户需要感知这个元素吗？ | 业务操作与决策需要的保留；排障信息放在对应排障区域。 | |'), checks[1]),
                ('定义指向不存在规则', text.replace('| §5.1 | 判断新增元素的用途。 | §1.1 §1.2 |',
                  '| §5.1 | 判断新增元素的用途。 | §99.9 |'), checks[2]),
                ('丢失原话追溯标题', text.replace('## 附录 A · 原始口述对照', '## 来源'), checks[3]),
            ]
            for label, mutated, check in cases:
                assert mutated != text, label + '未命中'
                doc.write_text(mutated, encoding='utf-8')
                try:
                    check()
                except AssertionError:
                    print('红：' + label)
                else:
                    raise AssertionError('漏验：' + label)
            # Fewer valid rows should not fail a structural check merely for being shorter.
            doc.write_text('| ' + ' | '.join(rows[0][1]) + ' |\n', encoding='utf-8')
            checks[1]()
            doc.write_text(next(line for line in text.splitlines() if line.startswith('| §5.1 |')), encoding='utf-8')
            # Supply the referenced definitions without recreating the old execution-row count.
            with doc.open('a', encoding='utf-8') as handle:
                handle.write('\n## §1.1 用途\n## §1.2 动作\n')
            checks[2]()
            print('正常精简：栏位与定义检查均放行')
            doc.write_text(text, encoding='utf-8')
            for check in checks:
                check()
            print('还原隔离输入：四项再次通过')
        finally:
            rules.DOC = original
    assert hashlib.sha256(original.read_bytes()).hexdigest() == before
    print('真实守则字节未变')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
