#!/usr/bin/env python
"""`T14`/`T15` 反向灵敏度 —— 证明这几条尺子**真的有牙**。

变异（都在**新增临时件**上做，跑完清干净；⛔ 不改任何源文件）：
  ① 往 `work/00-scratch/` 放一个**改 mtime 为 20 天前**的文件 ⇒ `T14` 必须命中；
  ② 往 `artifacts/` 放一个过程类 md ⇒ `T15` 必须命中；
  ③ 往 `tools/` 根放一个 .py ⇒ `T14` 必须命中；
  ④ 往 `work/40-decisions/` 放一个**状态词出档**的临时件 ⇒ `T15` **新条**（2026-10-11 `TAIL-296`）必须命中；
  ⑤ 同区放一个「**已定稿**却不写落地位置」的临时件 ⇒ 新条必须命中（缺的就是那一行）；
  ⑥ ⭐ **反向**：把 ⑤ 那件**补上落地位置**（其余不动）⇒ ⛔ 必须**不再**报（证明新条不误伤正当写的件）。
基线：⚠️ **只作对照**，⛔ 不要求为 0（2026-10-01 订正）—— 现实里基线**有**既存的 T15 黄（某几件文档
文头不全），钉"绝对 0"会让本件**永远红**。判法 = **比相对增量**：每处变异之后命中数必须 > 基线，且清场后回到基线。
⚠️ **基线到底几条 = 看本件自己打出的「命中 N」，⛔ 别把数字抄进注释**（抄了必漂 —— 2026-10-11 `TAIL-296`
实测：这里原写「基线本来就有 **5 条** `T15` 黄〔`10-designs` 4 件 ＋ `40-decisions` 1 件〕」，
而当天实况是 **`10-designs` 1 件、`40-decisions` 0 件** ⇒ 那条注**已过期**，本批改成"看读数"）。
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import time

# ⛔ **结果隔离**（本仓纪律）：非全套 pytest 必须把四态结果写到**临时文件** ——
#    否则每处变异都会把权威 `artifacts/acc_results.json` 冲成单条 ⇒ `doc_audit` 的 T4 立刻报红。
os.environ.setdefault("ACC_RESULTS_PATH", "../artifacts/_mut_acc_results.json")

sys.stdout.reconfigure(encoding="utf-8")
R = pathlib.Path(r"D:\dev\mtrl-workbench")
SCRATCH = R / ".codebuddy" / "work" / "00-scratch" / "_t14_probe_tmp.txt"
ART = R / "artifacts" / "_t15_probe_tmp.md"
TOOLS = R / "tools" / "_t14_probe_tmp.py"
#: ④⑤⑥ 的靶 = **决策区**（`T15` 新条的扫描面 = `audit_work.DECISION_ZONES`）。
#: ⚠️ 探针件名要同时过三关（2026-10-11 订正：原用 `_t15_probe_tmp.md`）：
#:   ① **必须以 `D` 开头** —— `40-decisions` 的命名尺（`audit_meta.WORK_NAME_PREFIX`）只认 `D`；
#:      脚本被硬杀留下残件时，不这么起名会让 `T12` 报红（假红比不跑更坏）；
#:   ② ⛔ **不能叫 `D索引-*`** —— 那是 `T15` 的文头豁免前缀，新条就看不见它了（靶当场失效）；
#:   ③ 件内文头四词齐全（见 `PROBE_HEAD`）⇒ 只有新条会命中，变异前后的差才归因得清。
DEC = R / ".codebuddy" / "work" / "40-decisions" / "D_t15_probe_tmp.md"
#: 探针件的三种形态（都带齐文头四词，好让**只有**新条命中 —— 变异前后的差才归因得清）
PROBE_HEAD = ("# T15 探针（临时件 · 跑完即删）\n\n"
              "> 读者：变异脚本｜回答：这条尺子还有没有牙｜何时读：跑 `tools/mut/_mut_t14t15.py` 时\n")
PROBE_OUT_OF_RANGE = PROBE_HEAD + "> 状态：**已办结**\n"           # ④ 出档
PROBE_NO_DECL = PROBE_HEAD + "> 状态：**已定稿**\n"                 # ⑤ 五档之内、但缺落地位置
PROBE_WITH_DECL = (PROBE_NO_DECL                                   # ⑥ 反向：补上那一行 ⇒ 不该再报
                   + "\n**落地位置**：`tools/mut/_mut_t14t15.py` · 同批改：`tools/audit/audit_work.py`\n")


def hits() -> int:
    # ⚠️⚠️ 2026-10-01（`TAIL-204` 第 7 步）**第三个同款坑**：漏了 `-X utf8` —— 子进程按本机默认编码
    #    （GBK）写 stdout，而本件按 utf-8 解 ⇒ 那行 `命中 N` 成了乱码 ⇒ `startswith("命中")` 永远不成立
    #    ⇒ 本函数返回 **-1** ⇒ 三处变异**一处都没验到**（症状 = "基线有命中（误报）＋ 三条都未被抓到"）。
    #    ⭐ 同族：`_mut_t12.py` 一模一样的病（同日一起修）；根因都是**同一句规矩没抄到**：
    #    「跑审计件的子进程必须带 `-X utf8`」。
    r = subprocess.run(
        [str(R / "backend" / ".venv" / "Scripts" / "python.exe"), "-X", "utf8", "-c",
         "import sys; sys.path.insert(0, r'tools/audit');"
         "from audit_work import check_scratch_ttl as a, check_artifacts_and_headers as b;"
         "h = a() + b();"
         "print('命中', len(h));"
         "[print('  -', x['code'], x['rel'], x['what'][:40]) for x in h]"],
        cwd=R, capture_output=True, text=True, encoding="utf-8", errors="replace")
    print((r.stdout or "").strip() or (r.stderr or "")[-200:])
    for l in (r.stdout or "").splitlines():
        if l.startswith("命中"):
            return int(l.split()[1])
    return -1


fail = []
print("基线…")
#: ⚠️⭐ 2026-10-01（第 7 步）**改成相对比较**：原来要求"基线必须 0 命中" —— 而基线**本来就有既存的 `T15` 黄**
#:   （哪几件、几条：**看下面打出的读数** —— ⛔ 别在这儿抄数字，抄了必漂）。
#:   ⇒ 钉"绝对 0"会让本件**永远红**（那不是判据有问题，是**靶的假设过期**了 —— 同 `_mut_t20` 那次的订正）。
base_n = hits()
if base_n < 0:
    fail.append("基线读数失败（子进程没吐出「命中 N」）")
print(f"   （基线命中 {base_n} —— ⚠️ 非 0 = 既有的 T15 黄〔具体件名见上面那几行〕；故比**相对增量**）")

#: ⚠️ 探针件一律 **try/finally 清场**：中途抛错也不能把临时件留在决策区里（那会变成别人的黄）。
try:
    print("变异①：scratch 里放 20 天前的文件…")
    SCRATCH.write_text("tmp", encoding="utf-8")
    old = time.time() - 20 * 86400
    os.utime(SCRATCH, (old, old))
    if hits() <= base_n:
        fail.append("① 超期 scratch 未被抓到")
    SCRATCH.unlink(missing_ok=True)

    print("变异②：artifacts 里放过程类 md…")
    ART.write_text("# 假的过程类 md\n", encoding="utf-8")
    if hits() <= base_n:
        fail.append("② artifacts 过程 md 未被抓到")
    ART.unlink(missing_ok=True)

    print("变异③：tools 根放散件 .py…")
    TOOLS.write_text("# 假的散件\n", encoding="utf-8")
    if hits() <= base_n:
        fail.append("③ tools 根散件未被抓到")
    TOOLS.unlink(missing_ok=True)

    print("变异④：决策区放「状态词出档」的探针件…")
    DEC.write_text(PROBE_OUT_OF_RANGE, encoding="utf-8")
    if hits() <= base_n:
        fail.append("④ 决策区状态词出档未被抓到（`TAIL-296` 新条没牙）")
    DEC.unlink(missing_ok=True)

    print("变异⑤：决策区放「已定稿却不写落地位置」的探针件…")
    DEC.write_text(PROBE_NO_DECL, encoding="utf-8")
    if hits() <= base_n:
        fail.append("⑤ 决策区「已定稿」缺落地位置未被抓到")
    DEC.unlink(missing_ok=True)

    print("变异⑥（反向）：同件补上落地位置 ⇒ 不许再报…")
    DEC.write_text(PROBE_WITH_DECL, encoding="utf-8")
    if hits() != base_n:
        fail.append("⑥ 补了落地位置仍在报 = **误伤**（正当写的件不该被这条逮住）")
    DEC.unlink(missing_ok=True)
finally:
    for p in (SCRATCH, ART, TOOLS, DEC):
        p.unlink(missing_ok=True)

print("复检基线…")
if hits() != base_n:
    fail.append("清场不完（基线命中数没回到原值）")

print("❌ " + "；".join(fail) if fail else
      f"✅ 有区分力：六处变异各如其分（①②③④⑤ 让命中数超过基线、⑥ 补上落地位置后回到基线）、"
      f"清场后回到 {base_n}、临时件已清"
      "（⚠️ 基线 {base_n} 非 0 = 既有的 T15 黄，不是本件造的）".replace("{base_n}", str(base_n)))
sys.exit(1 if fail else 0)
