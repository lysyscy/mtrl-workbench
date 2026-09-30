"""反向灵敏度（一次性）：证明 `tools/audit/ui_parity.py` 的 **U2 / U2b / U3** 有区分力 —— 改坏 ⇒ 必须变红。
（⭐ 2026-09-30 `TAIL-201`：`U1` 那条**已退场** ⇒ 本件剩 **3 靶**；`U1` 当年守的"切片对位"改看
 `tools/audit/shell_verify.py`（差异 ⇒ rc=1 ⇒ 复核后盖章）。）
（⚠️ 2026-09-24 订正：原文写 `tools/ui_parity.py` —— 尺子已随 `TAIL-58` 搬进 `tools/audit/`。）
只动**前端壳** `backend/app/web/index.html`（原型只读）。跑完逐字节复原（MD5 校验）。用完即删。
"""
import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "audit"))  # ⭐ `TAIL-58` 分目录：shell_source 在 audit/
from shell_source import SHELL_PATH as TARGET, pick  # noqa: F401  ← `P4`① 读取点收敛
PY = str(ROOT / "backend" / ".venv" / "Scripts" / "python.exe")
# ⚠️ 2026-09-23（`TAIL-77`）：尺子已随 `TAIL-58` 搬进 `tools/audit/` —— 旧路径会让子进程起不来
#    ⇒ 基线 `rc=2`（≠0）⇒ 每一条变异都"看起来变红"，**全是假红**。
TOOL = str(ROOT / "tools" / "audit" / "ui_parity.py")


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

#: ⚠️ 2026-09-23（`TAIL-77`）：第 4 位 = **是否全替换**。
#:    ⚠️ 2026-09-27：锚点跟着**用户裁定 `B`** 换（「已接后端真实数据」已整句删除）
#:    —— 现在的 U2 守的是「**未接通要如实说 ＋ 必须按页判**」⇒ 变异 = 把那句**改成无条件常挂**。
MUTS = [
    ("U2 未接通标注不再按页判（退回「一律挂一句」）",
     "${WIRED.has(VIEW)?'':'<em>本页数据尚未接通</em>'}", "${'<em>本页数据尚未接通</em>'}", False),
    # ⭐ 2026-09-18：「结余」录入容器 `BAL_EX` 的登记（m07 的第二个演示容器）——
    #    把演示值塞回壳里 ⇒ U2b 必须报红（否则"接线即清"没人管）。
    ("U2b m07 的 BAL_EX 演示值回流", "let BAL_EX = {};",
     "let BAL_EX = { 焊材: { '某项目仓库': 1200.00 } };", False),
    # ⚠️ 2026-09-23（`TAIL-77`）：锚点跟着**当前**那行改 —— `'home'`（2026-09-21 看板进 `WIRED`）
    #    与 `'m11'`/`'m15'` 早已加进去 ⇒ 旧锚点（从 `'m03'` 起）一处都命中不上。
    ("U3 WIRED 空集合", "new Set(['home','m03','m01','m02','m04','m05','m06','m07','m08','m09','m14','m11','m15',",
     "new Set([])", False),
]

hit = 0
for name, old, new, all_ in MUTS:
    # ⚠️ 2026-09-19（性能 `P4`② 三刀真拆）：壳已拆成多件（`web/shell/*.js`）⇒ **锚点在哪件就改哪件**；
    #    ⛔ 锚点/原字节/复原都必须用**那一件**的（拿 `index.html` 的字节写进 js 会把件写坏）。
    tgt = pick(TARGET, old, new)
    raw_t = tgt.read_bytes()
    frag = fit(old.encode("utf-8"), raw_t)
    n = raw_t.count(frag)
    if n == 0 or (not all_ and n != 1):
        print(f"❌ {name}：变异点命中 {n} 次（期望 {'≥1' if all_ else '1'}）")
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
