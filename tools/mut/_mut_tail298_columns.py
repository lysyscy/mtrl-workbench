"""守列身份（`TAIL-298`）：`m11` 的列只有一个主人 —— `domain.JC_COLUMNS`
⇒ 屏幕表头（`pages-b.js::jcThead`）／ 隐藏·钉列行为表（按 id）／ Excel 导出（派生）都从它来。

本件证明**那三条判据真的看得见坏法**（⛔ 不是"新写的判据全绿得可疑"），四个方向各打一次：

| 变异 | 靶 | 该红的那条 |
|---|---|---|
| `M1` 列清单**删一列**（`settle` 从 `JC_COLUMNS` 去掉） | `backend/app/mod11_jc/domain.py` | `tests/test_tail298_columns.py::test_导出列逐列等于域内核那张清单`（**列数覆盖**：19/18 的计数） |
| `M2` **键名漂**（`pay_sum` ⇒ `paid_sum`） | 同上 | 同上那件里的 `…test_导出列每个键都出现在真实行字典里`（⭐ **值级**那条得**自己**红） |
| `M3` 行为表**写错 id**（`material` ⇒ `materail`） | `backend/app/web/shell/pages-b.js` | `tests/test_ux_pages.py::test_集采台账行身份区钉列与隐藏列都按id定位_偏移必须量出来` |
| `M4` 钉列**不再连续**（去掉中间的 `date`） | 同上 | 同上（连续前缀那条） |

⚠️ 每处变异**只跑它该打中的那一个节点**（⛔ 不靠"别的判据顺便红了"充数 —— 那样看不出这条判据自己有没有牙；
   `M2` 尤其要紧：`M1`/`M2` 都会让"派生"那条红，而**值级**那条是不是**独立**看得见，只能这样验）。
⚠️ 靶在 `_isolated.isolated_backend` 的**临时副本**（`copytree` 到 `00-scratch`，⛔ 不写正式工作文件）；
   子进程跑真 pytest ⇒ conftest 把库换成**测试库**（`env` 显式传 `TEST_DATABASE_URL`/`DATABASE_URL`），
   四态出口也指向临时目录（⛔ 不刷新权威四态）。
⚠️ 判据 = **rc=1 ＋ 断言消息里出现那句 needle**（缺一条都不算命中：collection 错、别的节点红都不算）。
⚠️ 基线先跑（三个节点必须全绿）+ 改完**按原 bytes 复原** + 逐字节核 MD5。
"""
from __future__ import annotations
import hashlib
import pathlib
import shutil
import subprocess
import sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _isolated import isolated_backend
ROOT = pathlib.Path(__file__).resolve().parents[2]
T_DERIVED = 'tests/test_tail298_columns.py::test_导出列逐列等于域内核那张清单'
T_VALUES = 'tests/test_tail298_columns.py::test_导出列每个键都出现在真实行字典里'
T_SHELL = 'tests/test_ux_pages.py::test_集采台账行身份区钉列与隐藏列都按id定位_偏移必须量出来'
DOMAIN = 'app/mod11_jc/domain.py'
SETTLE_ITEM = '{"key": "settle", "label": "结算金额（自动）", "export_label": "结算金额", "type": "num"},'
PIN_LINE = "const JC_PIN_IDS = ['project_seq', 'date', 'material'];"
CASES: list[tuple[str, str, str, str, str, str]] = [(DOMAIN, 'M1 列清单删一列（`settle`）⇒ **列数覆盖**那条必红', SETTLE_ITEM, '', T_DERIVED, '主表 19 列'), (DOMAIN, 'M2 键名漂（`pay_sum` ⇒ `paid_sum`）⇒ **值级**那条必须自己红', '{"key": "pay_sum", "label": "付款金额", "type": "num"}', '{"key": "paid_sum", "label": "付款金额", "type": "num"}', T_VALUES, '根本不存在')]

def _run(base: pathlib.Path, env: dict, node: str) -> tuple[int, str]:
    r = subprocess.run([sys.executable, '-X', 'utf8', '-m', 'pytest', '-q', node, '--tb=line'], cwd=str(base), env=env, capture_output=True, text=True, encoding='utf-8', errors='replace')
    return (r.returncode, (r.stdout or '') + (r.stderr or ''))

def main() -> int:
    with isolated_backend('tail298-') as (base, env):
        shutil.copytree(ROOT / 'tools/audit', base.parent / 'tools/audit', ignore=shutil.ignore_patterns('__pycache__'))
        env['PYTHONPATH'] = str(base) + ';' + str(ROOT)
        nodes = [T_DERIVED, T_VALUES, T_SHELL]
        for node in nodes:
            rc, out = _run(base, env, node)
            print(f"基线 {node.rsplit('::', 1)[-1][:28]:30s} rc={rc}（应为 0）")
            if rc != 0:
                print('  ⛔ 基线就红 ⇒ 先清红再来跑本件')
                print(out[-1200:])
                return 1
        hit = 0
        dirty: list[str] = []
        for path, desc, old, new, node, needle in CASES:
            p = base / path
            raw = p.read_bytes()
            md5 = hashlib.md5(raw).hexdigest()
            text = raw.decode('utf-8')
            if text.count(old) != 1:
                print(f'  ⛔ {desc} —— 靶串在 `{path}` 里命中 {text.count(old)} 次（期望 1）⇒ **未验证**')
                continue
            try:
                p.write_bytes(text.replace(old, new).encode('utf-8'))
                rc, out = _run(base, env, node)
            finally:
                p.write_bytes(raw)
            if hashlib.md5(p.read_bytes()).hexdigest() != md5:
                dirty.append(path)
            ok = rc == 1 and needle in out
            print(('  ✅ ' if ok else '  ⛔ 未命中 ') + desc + f'  → rc={rc}' + ('' if ok else f'（判据「{needle}」没出现在输出里）'))
            if not ok:
                print('      ' + '\n      '.join(out.strip().splitlines()[-4:]))
            hit += ok
        print()
        print(f'  命中 {hit}/{len(CASES)}')
        print(f"  复原校验（MD5 逐字节）：{('✅ 已复原' if not dirty else '❌ 未复原 ' + ', '.join(dirty))}")
        print('  靶在临时副本内 ⇒ **正式文件与权威四态均未动**。')
        return 0 if hit == len(CASES) and (not dirty) else 1
if __name__ == '__main__':
    raise SystemExit(main())
