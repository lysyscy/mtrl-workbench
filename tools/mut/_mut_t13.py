#!/usr/bin/env python
"""`T13` 的反向灵敏度 —— 证明这把尺子**真的有区分力**（不是永远绿的假尺子）。

两处变异（都在主文档**临时副本**上做，跑完逐字节复原）：
  ① 塞 120 行"过程叙事" ⇒ 行数超预算 ⇒ 必须黄；
  ② 插入标题「#### 某批逐批记录」 ⇒ 过程词 ⇒ 必须黄。
基线（未变异）必须 0 命中。任何一处没抓到 ⇒ rc=1（尺子是假的）。
"""
from __future__ import annotations

import hashlib
import pathlib
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
REPO = pathlib.Path(r"D:\dev\mtrl-workbench")
PLAN = REPO / ".workbuddy" / "plans" / "开发计划-主文档.md"
orig = PLAN.read_bytes()
md5_orig = hashlib.md5(orig).hexdigest()
nl = b"\r\n" if b"\r\n" in orig else b"\n"


def run_t13() -> int:
    """返回 T13 命中**条数**（⛔ 别用退出码 —— 上次把语义接反，两处抓到反而报假红）。"""
    r = subprocess.run(
        [str(REPO / "backend" / ".venv" / "Scripts" / "python.exe"), "-c",
         "import sys; sys.path.insert(0, r'tools/audit');"
         "from audit_meta import check_plan_process;"
         "h = check_plan_process();"
         "print('T13 命中', len(h));"
         "[print('   -', x['what']) for x in h]"],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace")
    print((r.stdout or "").strip() or (r.stderr or "")[-300:])
    for l in (r.stdout or "").splitlines():
        if l.startswith("T13 命中"):
            return int(l.split()[2])
    return -1


fail = []
print("基线（未变异）…")
if run_t13() != 0:
    fail.append("基线就有命中（尺子误报）")

FILLER = "> 2026-09-22 过程叙事：当时先量了各页规模，然后抽了内核，跑了反向灵敏度…".encode()
TITLE = "#### 某批逐批记录".encode()
BODY = "当时做了什么…".encode()

for name, inject in (
    ("① 塞 120 行过程叙事 ⇒ 超行数预算", nl.join([b""] + [FILLER] * 120)),
    ("② 插入标题「#### 某批逐批记录」 ⇒ 过程词",
     nl.join([b"", "一些文字".encode(), TITLE, BODY])),
):
    print(f"变异 {name} …")
    PLAN.write_bytes(orig + inject)
    if run_t13() < 1:
        fail.append(f"变异未被抓到：{name}")

PLAN.write_bytes(orig)
md5_back = hashlib.md5(PLAN.read_bytes()).hexdigest()
print(f"复原 MD5 {'一致 ✓' if md5_back == md5_orig else '⚠️ 不一致 ✗'}")
if md5_back != md5_orig:
    fail.append("复原不一致")

print("❌ " + "；".join(fail) if fail else "✅ T13 有区分力：两处变异都黄、基线干净、逐字节复原")
sys.exit(1 if fail else 0)
