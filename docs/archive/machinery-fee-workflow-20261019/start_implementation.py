"""归档脚本：记录机械费实施起点与当时授权。"""
from pathlib import Path
import hashlib
import json
import subprocess

root = Path(__file__).resolve().parents[2]
out = root / '.artifacts/machinery-fee-workflow/implementation-20261019'
out.mkdir(parents=True, exist_ok=True)
status = subprocess.run(['git', 'status', '--porcelain=v1', '-z', '--untracked-files=all'], cwd=root, capture_output=True, check=True).stdout
(out / 'baseline-git-status.bin').write_bytes(status)
files = [s[3:] for s in status.decode('utf-8').split('\0') if s]
snap = {p: {'sha256': hashlib.sha256((root / p).read_bytes()).hexdigest(), 'bytes': (root / p).stat().st_size} for p in files if (root / p).is_file()}
(out / 'baseline-files.json').write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding='utf-8')
head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=root, capture_output=True, encoding='utf-8', check=True).stdout.strip()
rules = Path('C:/Users/Administrator/.skills-manager/skills/implement-solo-spec/references')
(out / 'rules.json').write_text(json.dumps({str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in rules.glob('*.md')}, indent=2), encoding='utf-8')
p = root / '.scratch/machinery-fee-workflow/spec.md'
raw = p.read_bytes()
addition = f'''

## 2026-10-19 正式实施授权与接续

用户明确启动TAIL-350～355，采用跨批统筹，累计起点 {head}；开始前的已有修改清单和摘要存于 .artifacts/machinery-fee-workflow/implementation-20261019/baseline-files.json。本次可实施产品代码、隔离数据核验、必要文档和按项目既有授权保存。生产迁移、真实业务导入、i8现场读取、服务重启仍需各自授权。历史拆票时的先不开发仅描述当时边界，已被本次正式开工覆盖。

按350→351→352→353→354/355推进；共享Git、公共文档与最终整合由主Agent串行负责。使用固定执行规则摘要，结束统一对累计改动做独立Standards/Spec双轴审查。工作流候选依据本次实际轨迹收集，先交付结论，不据此自动发布个人技能。
'''
newline = '\r\n' if b'\r\n' in raw else '\n'
if '## 2026-10-19 正式实施授权与接续'.encode() not in raw:
    p.write_bytes(raw + addition.replace('\n', newline).encode())
p = next((root / '.scratch/tails/issues').glob('TAIL-350-*'))
raw = p.read_bytes()
if b'**Status:** ready-for-agent' in raw:
    p.write_bytes(raw.replace(b'**Status:** ready-for-agent', b'**Status:** claimed') + '\n\n**2026-10-19 · 开工。** 用户明确启动350～355；按共同规格的实施授权及隔离边界推进。\n'.encode())
print('Fixed baseline:', head, 'existing files:', len(snap))
