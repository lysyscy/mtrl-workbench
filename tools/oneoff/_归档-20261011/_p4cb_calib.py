#!/usr/bin/env python
r"""`TAIL-64` **`P4-c-b`**：把**余下 13 块**「口径说明 · N 条」也收进出口 `CALIB`（2026-09-30）。

**背景**：`P4-c-a`（试点 `m13`）已把出口立起来 ⇒ 本批是**铺量**（施工图 §8.10 的批切法 = 分小批；
⚠️ 「按两侧对齐情况分」那个依据**已随 `TAIL-201` 消失** ⇒ 本批按**页**一次铺完，理由见下）。

**⛔ 为什么敢一次铺完 13 块**（与 `P4-b`/`P4-d-b` 的"一次铺"同款）：
  · 每块**逐块**都过一遍 **`node` 真渲染 + 逐字节比对**（⛔ 不是"看起来一样"）；
  · 「原文」一侧**从 git 里取**（`6abd900:backend/app/web/index.html`）—— 不是我在内存里"重建"的，
    所以比的是**改动前的真文件** vs **将写入的真文件**（含已转的 `m13` ⇒ 顺带回归"加参后它没变"）；
  · 形状**量过**（`_p4ca_survey.py`）：14 块里 `<ul style>` 只有 **1 种**、`<summary>` 只有 **2 种**
    （差异 = `m03` 那多出来的一个 `&nbsp;`）、每条 `<li>` 各自单行且无反引号 / 无 `${}`。

**出口要补一个参**：`post`（默认 `''`）—— 条数与灰色提示之间那一段。真例 = **`m03` 的 `&nbsp;`**。
  ⚠️ **必须保留它**（按原样传参），⛔ 不许"顺手统一掉"：本批唯一的硬证据就是**渲染字节不变**，
  为一个 `&nbsp;`（会让排版表现略变）降级证明强度**不划算**（同 `P5-d` 那条「口径②不放宽」）。

用法：`backend\.venv\Scripts\python.exe -X utf8 tools\oneoff\_p4cb_calib.py`（干跑 ＋ 自证）
     `… --write`
"""

from __future__ import annotations

import argparse
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
WEB = ROOT / "backend" / "app" / "web"
INDEX = WEB / "index.html"
PROJ = WEB / "shell" / "proj.js"
SCRATCH = ROOT / ".workbuddy" / "work" / "00-scratch"
NODE_FALLBACK = r"C:\Users\Administrator\.workbuddy\binaries\node\versions\22.22.2-3\node.exe"
BASE_COMMIT = "6abd900"          # ⭐ 改动前那一笔（`P4-c-a` 之前）

HEAD = '  <details class="tip"><summary>口径说明 · '
TAIL = '</ul></details>'
UL_LINE = ('    <ul style="margin:calc(6px * var(--fscale)) 0 0;'
           'padding-left:calc(17px * var(--fscale));line-height:1.8">')
SUM_TAIL = '<span class="mut sm">点开查看（默认收起，把空间让给数据）</span></summary>'

K_HEAD_OLD = ("const CALIB=({items=[]})=>'<details class=\"tip\"><summary>口径说明 · '+items.length+' 条 "
              "<span class=\"mut sm\">点开查看（默认收起，把空间让给数据）</span></summary>\\n'")
K_HEAD_NEW = ("const CALIB=({items=[],post=''})=>'<details class=\"tip\"><summary>口径说明 · '+items.length"
              "+' 条 '+post+'<span class=\"mut sm\">点开查看（默认收起，把空间让给数据）</span></summary>\\n'")
K_L2 = ("  +'    <ul style=\"margin:calc(6px * var(--fscale)) 0 0;"
        "padding-left:calc(17px * var(--fscale));line-height:1.8\">\\n'")
K_L3 = "  +'      <li>'+items.join('</li>\\n      <li>')+'</li>\\n'"
K_L4 = "  +'    </ul></details>';"
#: ⚠️ 喂给 `node` 的必须是**整条语句**（4 行）—— 第一版只给了头一行 ⇒ 出口只吐一个标题（自证当场抓到）
K_OLD_SRC = "\n".join([K_HEAD_OLD, K_L2, K_L3, K_L4])
K_NEW_SRC = "\n".join([K_HEAD_NEW, K_L2, K_L3, K_L4])
#: 出口那段**文档注释**里补一句 `post` 的说明（⛔ 不另起一段注释 —— 它就住在本件头上）
DOC_OLD = " * 自证 = 变异脚本（去掉委托 ／ 内核另写死条数 ／ 内核不包条目外壳 ⇒ 对应判据必须红）。 */"
DOC_NEW = (" * ⚠️ `post`（默认 `''`）= **条数与灰色提示之间那一段**。真例 = `m03` 那个 `&nbsp;` ——\n"
           " *    ⛔ **按原样传参，不许顺手统一掉**：本批唯一的硬证据是「渲染字节逐字节不变」，\n"
           " *    为一个不换行空格（会让排版表现略变）降级证明强度**不划算**（同 `P5-d` 那条「不放宽」）。\n"
           + DOC_OLD)


def rd(p: pathlib.Path) -> tuple[str, str]:
    raw = p.read_text(encoding="utf-8", newline="")
    return raw.replace("\r\n", "\n"), ("\r\n" if "\r\n" in raw else "\n")


def wr(p: pathlib.Path, text: str, nl: str) -> None:
    p.write_text(text if nl == "\n" else text.replace("\n", nl), encoding="utf-8", newline="")


def git_text(path: str) -> str:
    r = subprocess.run(["git", "--no-pager", "show", f"{BASE_COMMIT}:{path}"],
                       cwd=str(ROOT), capture_output=True)
    assert r.returncode == 0, f"⛔ 取不到 {BASE_COMMIT}:{path} —— {r.stderr[:200]!r}"
    return r.stdout.decode("utf-8").replace("\r\n", "\n")


def page_of(text: str, idx: int) -> str:
    cur = "（切片外）"
    for m in re.finditer(r"(?m)^V\.([A-Za-z0-9_]+)\s*=", text[:idx]):
        cur = m.group(1)
    return cur


def parse_blocks(text: str) -> list[dict]:
    """把**原文**里的每一块「口径说明 · N 条」拆开 ⇒ `[{page, old, items, gap, start, end}]`。"""
    out: list[dict] = []
    for m in re.finditer(re.escape(HEAD) + r"(\d+) 条 ", text):
        start = m.start()
        end = text.index(TAIL, start) + len(TAIL)
        old = text[start:end]
        lines = old.split("\n")
        head = lines[0]
        # 头一行 = `  <details …>口径说明 · N 条 ` ＋ [gap] ＋ `<span…>…</span></summary>`
        mid = head[len(HEAD) + len(m.group(1)) + len(" 条 "):]
        assert mid.endswith(SUM_TAIL), f"头一行形状变了：{head[:90]}"
        gap = mid[:-len(SUM_TAIL)]
        assert lines[1] == UL_LINE, f"`<ul>` 那行不是同款：{lines[1][:90]}"
        assert lines[-1] == "    " + TAIL, f"尾行形状变了：{lines[-1][:60]}"
        items: list[str] = []
        for ln in lines[2:-1]:
            s = ln.strip()
            assert s.startswith("<li>") and s.endswith("</li>") and s.count("<li>") == 1, \
                f"条目形状变了：{ln[:60]}"
            body = s[4:-5]
            assert "`" not in body and "${" not in body and "\\" not in body, \
                f"条目里有模板字面量不认的字符：{body[:40]}"
            items.append(body)
        assert len(items) == len(lines) - 3, f"条目数对不上：{len(items)} vs {len(lines)}"
        out.append({"page": page_of(text, start), "old": old, "items": items, "gap": gap,
                    "start": start, "end": end})
    return out


def call_site(blk: dict) -> str:
    """新调用点（`\\n` 归一）—— 行数 = 原文 - 1（`<ul>` 那行进出口了）。"""
    pre = "  ${CALIB({" + (f"post:'{blk['gap']}'," if blk["gap"] else "") + "items:["
    return "\n".join([pre] + ["    `" + it + "`," for it in blk["items"]] + ["  ]})}"])


def run_js(pairs: list[tuple[str, str, str]], kernel: str, path: pathlib.Path) -> bool:
    """`pairs = [(页, 原文, 新调用点)]` —— 全部**逐字节**比对（`node` 真渲染）。"""
    js = ["/* 自动生成（`tools/oneoff/_p4cb_calib.py`）—— P4-c-b 的渲染字节自证 */", kernel, ""]
    for page, old, new in pairs:
        assert "\\" not in old and "\\" not in new, f"待比文本里有反斜杠（模板字面量会当转义）：{page}"
        assert "${" not in old and "`" not in old, f"原文里有模板字面量不认的字符：{page}"
        js.append(f"const OLD_{page}=`{old}`;")
        js.append(f"const NEW_{page}=`{new}`;")
    js.append("let bad=0;")
    js.append("const cmp=(p,a,b)=>{ if(a===b){ console.log('  ✅ '+p+'：逐字节一致（'+a.length+' 字）'); }")
    js.append("  else { bad++; console.log('  ❌ '+p+'：**不一致**\\n     旧='+JSON.stringify(a)"
              "+'\\n     新='+JSON.stringify(b)); } };")
    for page, _, _ in pairs:
        js.append(f"cmp('{page}',OLD_{page},NEW_{page});")
    js.append("process.exit(bad?1:0);")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(js) + "\n", encoding="utf-8", newline="")
    node = shutil.which("node") or NODE_FALLBACK
    r = subprocess.run([node, str(path)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    sys.stdout.write(r.stdout or "")
    sys.stderr.write(r.stderr or "")
    return r.returncode == 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    shell, nl_shell = rd(INDEX)
    proj, nl_proj = rd(PROJ)
    old_shell = git_text("backend/app/web/index.html")     # ⚠️ 保持 LF（解析用）—— 比对时再换成真行尾
    print(f"   换行：index.html={nl_shell!r} · proj.js={nl_proj!r} · 原文取自 {BASE_COMMIT}")

    # ── 出口加 `post` 参（默认 `''` ⇒ 已转的 `m13` 渲染字节不变）
    assert proj.count(K_OLD_SRC) == 1, "⛔ 找不到原 `CALIB` 定义（整条 4 行；已改过？）"
    assert proj.count(DOC_OLD) == 1, "⛔ 找不到出口那段文档注释的尾行"
    new_proj = proj.replace(K_OLD_SRC, K_NEW_SRC, 1).replace(DOC_OLD, DOC_NEW, 1)

    # ── 原文 14 块 ⇒ 目标：13 块还是字面块、`m13` 已走出口
    old_blocks = parse_blocks(old_shell)
    cur_blocks = parse_blocks(shell)
    pages = [b["page"] for b in old_blocks]
    assert len(old_blocks) == 14, f"原文块数 = {len(old_blocks)}（期望 14）"
    assert len(cur_blocks) == 13, f"当前字面块数 = {len(cur_blocks)}（期望 13 —— m13 已转）"
    assert "m13" not in [b["page"] for b in cur_blocks], "m13 又变回字面块了？"
    print(f"   原文 {len(old_blocks)} 块：{' '.join(pages)}")
    print(f"   当前待转 {len(cur_blocks)} 块：{' '.join(b['page'] for b in cur_blocks)}")

    # ── 逐块换（⛔ 从后往前替换，免得位移）
    new_shell = shell
    news: dict[str, str] = {}
    for blk in sorted(cur_blocks, key=lambda b: -b["start"]):
        cs = call_site(blk)
        news[blk["page"]] = cs
        new_shell = new_shell[:blk["start"]] + cs + new_shell[blk["end"]:]
    assert len(parse_blocks(new_shell)) == 0, "⛔ 换完还剩字面块"

    # ── `m13`（已转）的新调用点：从将写入的文本里**原样取出**
    m13 = [b for b in old_blocks if b["page"] == "m13"]
    assert len(m13) == 1
    m13_new = call_site(m13[0])
    assert m13_new in new_shell, "⛔ `m13` 的调用点与将写入的文本不一致（它应当**逐字未变**）"
    news["m13"] = m13_new

    # ── 自证：**原文（git 里那一份）** vs **将写入的文本**（14 页全比 ⇒ 含 m13 的回归）
    pairs = [(b["page"], b["old"].replace("\n", nl_shell), news[b["page"]].replace("\n", nl_shell))
             for b in old_blocks]
    print(f"\n自证：原文（{BASE_COMMIT} 里的真文件） vs 将写入的真文本 —— 逐字节（{len(pairs)} 页）")
    if not run_js(pairs, K_NEW_SRC, SCRATCH / "_p4cb_selfcheck.js"):
        print("  ⛔ 自证不过 —— 拒写")
        return 1

    # ── 行数账（每块 -1）
    d_old, d_new = len(shell.split("\n")), len(new_shell.split("\n"))
    print(f"\n   index.html 行数：{d_old} → {d_new}（差 {d_new - d_old} ＝ -{len(cur_blocks)} 块 × 1 行）")
    assert d_new == d_old - len(cur_blocks)
    n_ul = len(re.findall(re.escape(UL_LINE), new_shell))
    assert n_ul == 0, f"⛔ 还留着 {n_ul} 条手写的 `<ul style>`"
    assert new_shell.count("CALIB({") == 14, f"⛔ 调用点数 = {new_shell.count('CALIB({')}（期望 14）"

    if not args.write:
        print("\n（干跑：⛔ 未写）")
        return 0

    wr(INDEX, new_shell, nl_shell)
    wr(PROJ, new_proj, nl_proj)
    assert rd(INDEX)[0] == new_shell, "⛔ index.html 写回不一致"
    assert rd(PROJ)[0] == new_proj, "⛔ proj.js 写回不一致"
    print("\n✅ 已落盘：14 块全走出口 `CALIB`（出口补 `post` 参，默认值保持旧行为）")
    print("⚠️ 接着必跑：`syntax_audit` → 改判据（见本批说明）→ 全套 pytest → 真机 → 全闸门 → `shell_verify --snapshot`")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
