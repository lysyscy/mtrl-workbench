"""反向灵敏度（一次性）：证明 `tools/ui_parity.py` 的 U1/U2/U3 有区分力 —— 改坏 ⇒ 必须变红。
只动**前端壳** `backend/app/web/index.html`（原型只读）。跑完逐字节复原（MD5 校验）。用完即删。
"""
import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
from shell_source import SHELL_PATH as TARGET, pick  # noqa: F401  ← `P4`① 读取点收敛
PY = str(ROOT / "backend" / ".venv" / "Scripts" / "python.exe")
TOOL = str(ROOT / "tools" / "ui_parity.py")


def run() -> int:
    p = subprocess.run([PY, TOOL, "--json"], capture_output=True, text=True, encoding="utf-8")
    return p.returncode


def fit(frag: bytes, sample: bytes) -> bytes:
    if b"\r\n" in sample:
        return frag.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    return frag.replace(b"\r\n", b"\n")


raw = TARGET.read_bytes()
md5_before = hashlib.md5(raw).hexdigest()
rc0 = run()
print(f"改前 rc={rc0}（期望 0）")

MUTS = [
    ("U1 视图切片漂移", "V.m03=()=>{", "V.m03=()=>{/* 顺手改了原型逻辑 */"),
    ("U2b 少了「已接后端真实数据」措辞", "已接后端真实数据", "已接真实数据"),
    # ⭐ 2026-09-18：「结余」录入容器 `BAL_EX` 的登记（m07 的第二个演示容器）——
    #    把演示值塞回壳里 ⇒ U2b 必须报红（否则"接线即清"没人管）。
    ("U2b m07 的 BAL_EX 演示值回流", "let BAL_EX = {};",
     "let BAL_EX = { 焊材: { '某项目仓库': 1200.00 } };"),
    ("U3 WIRED 空集合", "new Set(['m03','m01','m02','m04','m05','m06','m07','m08','m09','m14'])", "new Set([])"),
]

hit = 0
for name, old, new in MUTS:
    # ⚠️ 2026-09-19（性能 `P4`② 三刀真拆）：壳已拆成多件（`web/shell/*.js`）⇒ **锚点在哪件就改哪件**；
    #    ⛔ 锚点/原字节/复原都必须用**那一件**的（拿 `index.html` 的字节写进 js 会把件写坏）。
    tgt = pick(TARGET, old, new)
    raw_t = tgt.read_bytes()
    frag = fit(old.encode("utf-8"), raw_t)
    n = raw_t.count(frag)
    if n != 1:
        print(f"❌ {name}：变异点命中 {n} 次（必须唯一）")
        continue
    tgt.write_bytes(raw_t.replace(frag, fit(new.encode("utf-8"), raw_t)))
    rc = run()
    ok = rc == 1
    hit += ok
    print(f"{'✅' if ok else '❌'} {name} ⇒ rc={rc}（期望 1）")
    tgt.write_bytes(raw_t)                      # ⭐ 每条立刻按原字节复原（⛔ 别等循环结束 —— 会互相污染）

TARGET.write_bytes(raw)
md5_after = hashlib.md5(TARGET.read_bytes()).hexdigest()
rc_end = run()
print()
print(f"复原后 rc={rc_end}（期望 0）· MD5 {'一致' if md5_before == md5_after else '不一致 ⛔'}")
print(f"结论：{hit}/{len(MUTS)} 如期变红")
sys.exit(0 if (hit == len(MUTS) and rc_end == 0 and md5_before == md5_after) else 1)
