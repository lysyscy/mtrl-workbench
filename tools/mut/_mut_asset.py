"""反向灵敏度（一次性）：证明 `tools/asset_audit.py` 的 A1/A2/A4 有区分力 —— 改坏 ⇒ 必须变红。
跑完逐字节复原（MD5 校验）。用完即删。

⚠️ 片段一律写 `str` 再 `.encode("utf-8")`（bytes 字面量不能含非 ASCII）。
⚠️ 行尾按目标文件归一（本仓行尾不统一）。
"""
import hashlib
import io
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "docs" / "reference" / "legacy-materials.md"
PY = str(ROOT / "backend" / ".venv" / "Scripts" / "python.exe")
# ⚠️ 2026-09-23：`asset_audit.py` 已搬进 `tools/audit/` —— 旧路径下子进程 rc=2（读不到审计件），
#    而脚本把"rc != 1"记成**未变红** ⇒ 假绿（实测：`0/3 如期变红`）。
AUDIT = str(ROOT / "tools" / "audit" / "asset_audit.py")


def run() -> tuple[int, str]:
    p = subprocess.run([PY, AUDIT, "--json"], capture_output=True, text=True, encoding="utf-8")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def fit(frag: bytes, sample: bytes) -> bytes:
    if b"\r\n" in sample:
        return frag.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    return frag.replace(b"\r\n", b"\n")


raw = TARGET.read_bytes()
md5_before = hashlib.md5(raw).hexdigest()

MUTS = [
    ("A1 落点路径", "backend/app/mod07_setl/extract.py", "backend/app/mod07_setl/extract_MISSING.py"),
    ("A2 挂台账", "**`TAIL-04`**（M6 导出真文件时用它做**成品对账**）", "**M6**（导出真文件时）"),
    ("A4 用例号", "`ACC-X-EXP-001`", "`ACC-X-EXP-999`"),
]

hit = 0
for name, old, new in MUTS:
    frag = fit(old.encode("utf-8"), raw)
    assert raw.count(frag) == 1, f"{name}：变异点在源文件里命中 {raw.count(frag)} 次（必须唯一）"
    TARGET.write_bytes(raw.replace(frag, fit(new.encode("utf-8"), raw)))
    rc, out = run()
    ok = rc == 1
    hit += ok
    print(f"{'✅' if ok else '❌'} {name} ⇒ rc={rc}（期望 1）")
    TARGET.write_bytes(raw)  # 复原

md5_after = hashlib.md5(TARGET.read_bytes()).hexdigest()
rc0, _ = run()
print()
print(f"复原后 rc={rc0}（期望 0）· MD5 {'一致' if md5_before == md5_after else '不一致 ⛔'}")
print(f"结论：{hit}/{len(MUTS)} 如期变红")
sys.exit(0 if (hit == len(MUTS) and rc0 == 0 and md5_before == md5_after) else 1)
