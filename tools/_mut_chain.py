"""反向灵敏度（一次性）：证明 `tools/chain_audit.py` 的 C2/C3 有区分力、且「修好能消号」。
⚠️ 这把尺子**当前本来就是红的**（14 条缺口）⇒ 不能只看 rc，必须断言**具体那条**出现/消失。
只动 `tools/chain_expected.txt`。跑完逐字节复原（MD5 校验）。用完即删。
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "tools" / "chain_expected.txt"
PY = str(ROOT / "backend" / ".venv" / "Scripts" / "python.exe")
TOOL = str(ROOT / "tools" / "chain_audit.py")


def run() -> dict:
    p = subprocess.run([PY, TOOL, "--json"], capture_output=True, text=True, encoding="utf-8")
    return json.loads(p.stdout)


def blob(res: dict) -> str:
    return "\n".join(res["red"] + res["yellow"] + res["unclaimed"])


def fit(frag: bytes, sample: bytes) -> bytes:
    if b"\r\n" in sample:
        return frag.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    return frag.replace(b"\r\n", b"\n")


raw = TARGET.read_bytes()
md5_before = hashlib.md5(raw).hexdigest()
base = run()
print(f"改前：红 {len(base['red'])} · 黄 {len(base['yellow'])} · 未认领 {len(base['unclaimed'])}")

CASES = [
    ("C3 幽灵落点名",
     "backend/app/mod01_projects/repository.py::next_placeholder",
     "backend/app/mod01_projects/repository.py::next_placeholder_XXX",
     lambda r: "落点名字在文件里找不到" in blob(r), "落点名字在文件里找不到"),
    ("C2 文档锚改了字",
     "付款侧自动建档", "付款侧全自动建档案",
     lambda r: "C2 文档锚在真源里找不到" in blob(r), "C2 文档锚在真源里找不到"),
    ("修改一条「缺」为「已接」⇒ 该分支消号",
     "弹窗列表|—|缺：需补判据（链路级）|缺",
     "弹窗列表|backend/app/core/errors.py::MustReportError|ACC-PRJ-OWN-001|已接",
     lambda r: "弹窗列表" not in "\n".join(r["red"]), "弹窗列表 不再出现在红里"),
]

hit = 0
for name, old, new, ok_fn, expect in CASES:
    frag = fit(old.encode("utf-8"), raw)
    n = raw.count(frag)
    if n != 1:
        print(f"❌ {name}：变异点命中 {n} 次（必须唯一）")
        continue
    TARGET.write_bytes(raw.replace(frag, fit(new.encode("utf-8"), raw)))
    r = run()
    ok = ok_fn(r)
    hit += ok
    print(f"{'✅' if ok else '❌'} {name} ⇒ 期望「{expect}」")
    TARGET.write_bytes(raw)

md5_after = hashlib.md5(TARGET.read_bytes()).hexdigest()
after = run()
same = len(after["red"]) == len(base["red"]) and len(after["yellow"]) == len(base["yellow"])
print()
print(f"复原后 红 {len(after['red'])} / 黄 {len(after['yellow'])}（与改前一致：{same}）· "
      f"MD5 {'一致' if md5_before == md5_after else '不一致 ⛔'}")
print(f"结论：{hit}/{len(CASES)} 如期命中")
sys.exit(0 if (hit == len(CASES) and same and md5_before == md5_after) else 1)
