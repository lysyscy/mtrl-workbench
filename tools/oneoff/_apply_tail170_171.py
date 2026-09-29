#!/usr/bin/env python
"""`TAIL-170` ＋ `TAIL-171`：跨页统一补齐（用户 2026-09-29 裁定「都按推荐做」）· 一次性脚本。

**三件 + 一件 + 一件**（逐处都先量过真实范围，⛔ 不套模板）：
- `TAIL-170`-① **导出按钮必须写清范围**：全站 8 处 `data-act="exp"` 里 **只有 3 处**写过（`m03` 手写的 · `m11` 由 `BIND.m11` 注入的）
  ⇒ 本批补齐剩余 **6 处**；⚠️ 其中 **3 处是「没有落点」的兜底**（`m06` 朴素那份 / `m08` 朴素那份 / 已取消的差异清单）
     —— 对它们**如实写"还没有落点"**，⛔ **不编一个范围**（编了就是假话，`EXP_ROUTES` 的注释明令禁止）。
- `TAIL-170`-② **置灰必须说明原因**：全站 24 处字面 `disabled` 里 **9 处没 `title`** ⇒ 逐处写「为什么灰 / 怎么解锁」。
- `TAIL-170`-③ **固定列表头与数据行同进同退**（3 张勾选表 `m03`/`m04`/`m11`）：表头首格早有 `.fl`（sticky-left），
  数据行 / 草稿行 / 合计行首格没有 ⇒ 横向滚动时**表头那格浮着、行里那颗勾选框滚走**（错位）。
  口径取「**两边都钉**」（与 `m07`/`m08` 表的首列做法一致；CSS 里 `tbody tr … .fl` 那几条背景规则本来就是为它写的）。
- `TAIL-171`-② **`m03` 手动行「保存」补挡重入**（`ntSaving`）：与 `m04` 同款缺陷（连点两次落两行），
  ⚠️ 手动行没有"单据号唯一约束"这道天然闸（同一笔补两行业务上合法）⇒ 只能界面挡。

用法（工程根）：`… _apply_tail170_171.py --check` / `--write`
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
WEB = REPO / "backend" / "app" / "web"
IDX = WEB / "index.html"
PA = WEB / "shell" / "pages-a.js"
PJ = WEB / "shell" / "proj.js"
AC = WEB / "shell" / "actions.js"
CO = WEB / "shell" / "core.js"
LG = WEB / "shell" / "legacy.js"

SCOPE = '导出当前筛选下看到的这些行'

EDITS: list[tuple[pathlib.Path, str, str, str]] = [
    # ─────────── `TAIL-170`-① 导出按钮写范围（6 处 · 3 真导出 ＋ 3 兜底如实说）
    (IDX, "m04 导出（真导出：当前筛选）",
     '<button class="btn pri" data-act="exp" data-t="付款计划审查结果">导出 Excel</button>',
     f'<button class="btn pri" data-act="exp" data-t="付款计划审查结果" title="{SCOPE}">导出 Excel</button>'),
    (IDX, "m05 导出（真导出：当前筛选）",
     '<button class="btn pri" data-act="exp" data-t="付款流水">导出 Excel</button>',
     f'<button class="btn pri" data-act="exp" data-t="付款流水" title="{SCOPE}">导出 Excel</button>'),
    (IDX, "m01 导出（真导出：当前筛选）",
     '<button class="btn pri" data-act="exp" data-t="项目档案">导出 Excel</button>',
     f'<button class="btn pri" data-act="exp" data-t="项目档案" title="{SCOPE}">导出 Excel</button>'),
    (IDX, "m06 朴素那份（⛔ 没有落点 ⇒ 如实说，不编范围）",
     '<button class="btn pri" data-act="exp" data-t="过程资料" data-sub="${procTabName()}">导出 Excel</button>',
     '<button class="btn pri" data-act="exp" data-t="过程资料" data-sub="${procTabName()}" '
     'title="这一份（朴素）导出还没有落点 —— 点了会如实说明（⛔ 不假装成功）；要按模板导出请用上面的入口">导出 Excel</button>'),
    (IDX, "m08 朴素那份（⛔ 没有落点 ⇒ 如实说）",
     '<button class="btn pri" data-act="exp" data-t="库存单据明细总表">导出 Excel</button>',
     '<button class="btn pri" data-act="exp" data-t="库存单据明细总表" '
     'title="这一份（朴素）导出还没有落点 —— 点了会如实说明（⛔ 不假装成功）；含透视那份有自己的按钮">导出 Excel</button>'),
    (IDX, "差异清单（已取消 ⇒ 如实说）",
     '<button class="btn pri" data-act="exp" data-t="差异清单">导出差异</button>',
     '<button class="btn pri" data-act="exp" data-t="差异清单" '
     'title="差异清单的导出已取消 —— 点了会如实说明（⛔ 不假装成功）">导出差异</button>'),
    (IDX, "m11 标记处也写上（真值由 `BIND.m11` 渲染时再确认一遍）",
     '<button class="btn pri" data-act="exp" data-t="集采台账">导出 Excel</button>',
     '<button class="btn pri" data-act="exp" data-t="集采台账" '
     'title="导出当前屏幕上这些行（含筛选）为 Excel —— 列是全列（隐藏列也会导出）">导出 Excel</button>'),

    # ─────────── `TAIL-170`-② 置灰写理由（9 处）
    (IDX, "m03「付款」置灰说明",
     '<button class="btn pri" data-act="batchPay" ${pk.length?\'\':\'disabled\'}>',
     '<button class="btn pri" data-act="batchPay" ${pk.length?\'\':\'disabled\'} '
     'title="${pk.length?\'把已勾选的付款通知书提交付款（剔除行 / i8 撤单行不进批次）\':\'未勾选时置灰 —— 先勾选要付的行\'}">'),
    (IDX, "m15「恢复」置灰说明",
     '<button class="btn sm" data-act="userRestore" data-id="${u.id}" ${iAmAdmin?\'\':\'disabled\'}>',
     '<button class="btn sm" data-act="userRestore" data-id="${u.id}" ${iAmAdmin?\'\':\'disabled\'} '
     'title="恢复该账号；只有管理员能管理账号（不是管理员时置灰）">'),
    (IDX, "m15「重置密码」置灰说明",
     '<button class="btn sm" data-act="userPwd" data-id="${u.id}" ${iAmAdmin?\'\':\'disabled\'}>',
     '<button class="btn sm" data-act="userPwd" data-id="${u.id}" ${iAmAdmin?\'\':\'disabled\'} '
     'title="重置该账号密码；只有管理员能管理账号（不是管理员时置灰）">'),
    (CO, "m01「确认写到哪一行」置灰说明",
     '<button class="btn pri" data-act="pjPromoteOk"${usable.length ? \'\' : \' disabled\'}>',
     '<button class="btn pri" data-act="pjPromoteOk"${usable.length ? \'\' : \' disabled\'} '
     'title="${usable.length?\'把该小微写到选定的那一行\':\'候选里没有可写的占位行 —— 弹窗里已写明\'}">'),
    (LG, "导入①「解析」置灰说明",
     '<button class="btn pri" data-act="${esc(parseAct)}"${file ? \'\' : \' disabled\'}>',
     '<button class="btn pri" data-act="${esc(parseAct)}"${file ? \'\' : \' disabled\'} '
     'title="${file?\'解析这个文件（一个字节都不写库）\':\'还没选文件 —— 选完才能解析\'}">'),
    (LG, "导入③「生成预览」置灰说明",
     '<button class="btn pri" data-act="impPreview"${lack.length ? \' disabled\' : \'\'}>',
     '<button class="btn pri" data-act="impPreview"${lack.length ? \' disabled\' : \'\'} '
     'title="${lack.length?\'还缺必填项 / 列映射 —— 上面已列出缺什么\':\'生成预览（这一步一个字节都不写库）\'}">'),
    (LG, "导入④「确认落库」置灰说明",
     '<button class="btn pri" data-act="impCommit"${(needPj || IMP.busy) ? \' disabled\' : \'\'}>',
     '<button class="btn pri" data-act="impCommit"${(needPj || IMP.busy) ? \' disabled\' : \'\'} '
     'title="${IMP.busy?\'正在落库 —— 请勿重复点击\':(needPj?\'先回第 ① 步选「这批数据进哪个项目」—— 没选就落不了库\':\'确认落库（这一步才真正写库）\')}">'),
    (AC, "m07 大表「下移」置灰说明",
     '<button class="btn sm" data-act="bigSelDown" data-wh="${esc(wh)}"${(on&&k<BIGDRAFT.length-1)?\'\':\' disabled\'}>',
     '<button class="btn sm" data-act="bigSelDown" data-wh="${esc(wh)}"${(on&&k<BIGDRAFT.length-1)?\'\':\' disabled\'} '
     'title="${(on&&k<BIGDRAFT.length-1)?\'把这一行往下挪一位\':\'只有「选中了某一行」且它不是最后一行时才能下移\'}">'),
    (AC, "m07 欠款表「下移」置灰说明",
     '<button class="btn sm" data-act="debtPickDown" data-wh="${esc(wh)}"${(on&&k<DEBTDRAFT.length-1)?\'\':\' disabled\'}>',
     '<button class="btn sm" data-act="debtPickDown" data-wh="${esc(wh)}"${(on&&k<DEBTDRAFT.length-1)?\'\':\' disabled\'} '
     'title="${(on&&k<DEBTDRAFT.length-1)?\'把这一行往下挪一位\':\'只有「选中了某一行」且它不是最后一行时才能下移\'}">'),

    # ─────────── `TAIL-170`-③ 固定列：表头与数据行同进同退（3 张勾选表）
    (IDX, "m03 数据行首格（勾选框列）跟表头一起钉住",
     '<td class="ctr"><input type="checkbox" class="chk" data-act="pick"',
     '<td class="ctr fl"><input type="checkbox" class="chk" data-act="pick"'),
    (IDX, "m04 数据行首格跟表头一起钉住",
     '<td class="ctr"><input type="checkbox" class="chk" data-act="plPick"',
     '<td class="ctr fl"><input type="checkbox" class="chk" data-act="plPick"'),
    (IDX, "m11 数据行首格跟表头一起钉住",
     '<td class="ctr"><input type="checkbox" class="chk" data-act="jcPick"',
     '<td class="ctr fl"><input type="checkbox" class="chk" data-act="jcPick"'),
    (PJ, "m03 草稿行首格也钉住（否则新增时一横滚就错位）",
     '<td class="ctr"><span class="tag t-in" title="尚未保存',
     '<td class="ctr fl"><span class="tag t-in" title="尚未保存'),
    (PA, "m04 草稿行首格也钉住",
     '<tr class="draftrow">\n    <td class="ctr"></td>',
     '<tr class="draftrow">\n    <td class="ctr fl"></td>'),
    (IDX, "m03 合计行首格也钉住",
     "{tip:'当前筛选结果中「非剔除」行的合计 —— 剔除行不计入（与欠款口径一致）'})",
     "{tip:'当前筛选结果中「非剔除」行的合计 —— 剔除行不计入（与欠款口径一致）',leadCls:'fl'})"),
    (IDX, "m04 合计行首格也钉住",
     '8:rs=>N2(rs.reduce((a,p)=>a+p.monthAmt,0))})',
     "8:rs=>N2(rs.reduce((a,p)=>a+p.monthAmt,0))},{leadCls:'fl'})"),

    # ─────────── `TAIL-171`-② `m03` 手动行保存补挡重入
    (PJ, "`ntSaving` 声明（挨着草稿层两个状态量）",
     "let naEditId='';         /* '' = 新增；否则 = 正在编辑的手动行 id */",
     "let naEditId='';         /* '' = 新增；否则 = 正在编辑的手动行 id */\n"
     "/* ⭐ 落库中（**挡重入** · 守则 §5.5）：连点两次「保存」= 两次 `POST /api/m03/actions/manual-save`\n"
     "   ⇒ **同一份补录落两行**；⚠️ 手动行**没有**「单据号唯一约束」这道天然闸（同一笔补两行业务上是合法状态）\n"
     "   ⇒ 只能由界面挡（与 `plRowSave` 的 `plSaving` / `IMP.busy` 同款）。 */\n"
     "let ntSaving=false;"),
    (PJ, "草稿行「保存」按钮：跟着禁用 ＋ 状态文案",
     '<button class="btn sm pri" data-act="ntRowSave" title="校验通过后落库（统计结算恒 0 · 录入人 = 当前登录用户）">保存</button> '
     '<button class="btn sm" data-act="ntRowCancel" title="丢弃这一行草稿（不入库）">取消</button>',
     '<button class="btn sm pri" data-act="ntRowSave"${ntSaving?\' disabled\':\'\'} '
     'title="${ntSaving?\'正在保存 —— 请勿重复点击\':\'校验通过后落库（统计结算恒 0 · 录入人 = 当前登录用户）\'}">${ntSaving?\'保存中…\':\'保存\'}</button> '
     '<button class="btn sm" data-act="ntRowCancel"${ntSaving?\' disabled\':\'\'} title="丢弃这一行草稿（不入库）">取消</button>'),
    (AC, "`ntRowSave`：本地校验**之后**上闸（校验早退 ⇒ 不会把闸卡死）",
     '  const body={ row_id:(naEditId&&naEditId!==NT_NEW_ID)?String(naEditId):\'\',',
     '  if(ntSaving) return;\n'
     '  ntSaving=true; render();\n'
     '  const body={ row_id:(naEditId&&naEditId!==NT_NEW_ID)?String(naEditId):\'\','),
    # ⚠️ 「失败分支解除闸」那一条**不在本脚本里**：`if(!r || r.ok === false){` 那段在别的动作里也有同形，
    #    脚本里按缩进拼不准（实测差一格就静默不命中）⇒ **改用手工精确替换**（见当轮实况），
    #    ⛔ 别为了"脚本一把过"去放松断言（那正是假绿的温床）。
    (AC, "`ntRowSave`：成功分支解除闸",
     "      naEditId=''; naD={};\n       /* 新增后**保证看得见**",
     "      naEditId=''; naD={}; ntSaving=false;\n       /* 新增后**保证看得见**"),
    (AC, "`ntRowSave`：异常分支解除闸",
     "    .catch(e=>{ toast(`<b>保存失败</b>：${esc(e.message||e)}<br>草稿行已保留，改完再点「保存」`,6000); }); },",
     "    .catch(e=>{ ntSaving=false; toast(`<b>保存失败</b>：${esc(e.message||e)}<br>草稿行已保留，改完再点「保存」`,6000); }); },"),
]


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)

    texts: dict[pathlib.Path, tuple[str, bool]] = {}
    for p in {e[0] for e in EDITS}:
        raw = p.read_bytes()
        crlf = b"\r\n" in raw
        t = raw.decode("utf-8").replace("\r\n", "\n")
        assert (t.replace("\n", "\r\n") if crlf else t).encode("utf-8") == raw, f"{p.name}：行尾 round-trip 不一致"
        texts[p] = (t, crlf)

    ok = 0
    for p, why, old, new in EDITS:
        t, _ = texts[p]
        if old.startswith("RE:"):                    # ⚠️ 正则模式：只给"同形片段在别处也有"的那几处用
            pat = old[3:]
            n = len(re.findall(pat, t))
            if n != 1:
                print(f"  ⛔ {p.name}｜{why}：正则命中 {n} 次（期望 1）")
                k = t.find("草稿行已保留")
                if k >= 0:
                    print(f"     ⤷ 真身（含「草稿行已保留」那段）：{t[k - 220:k + 90]!r}")
                continue
            texts[p] = (re.sub(pat, new, t, count=1), texts[p][1])
            ok += 1
            print(f"  ✅ {p.name:<12} {why}")
            continue
        n = t.count(old)
        if n != 1:
            print(f"  ⛔ {p.name}｜{why}：命中 {n} 次（期望 1）")
            j = t.find(old.split("\n")[0])
            if j >= 0:
                print(f"     ⤷ 真身：{t[j:j + len(old) + 90]!r}")
            continue
        texts[p] = (t.replace(old, new, 1), texts[p][1])
        ok += 1
        print(f"  ✅ {p.name:<12} {why}")
    print(f"\n命中 {ok}/{len(EDITS)}")
    if ok != len(EDITS):
        print("⛔ 有未命中 ⇒ ⛔ 不写")
        return 1
    # 自检：改完之后「导出按钮全部有 title」「字面 disabled 全部有 title」
    idx = texts[IDX][0]
    exps = [ln for ln in idx.split("\n") if 'data-act="exp"' in ln]
    bad_exp = [ln for ln in exps if "title=" not in ln]
    print(f"\n自检：`data-act=\"exp\"` {len(exps)} 处 · 缺 title {len(bad_exp)} 处")
    for ln in bad_exp:
        print(f"   ⛔ {ln.strip()[:150]}")
    src = "\n".join(t for t, _ in texts.values())
    dis = [m.group(0) for m in re.finditer(r"<button[^>]*\bdisabled[^>]*>", src)]
    bad_dis = [d for d in dis if "title=" not in d]
    print(f"自检：字面 disabled 的 button {len(dis)} 处 · 缺 title {len(bad_dis)} 处")
    for d in bad_dis:
        print(f"   ⛔ {d[:150]}")
    if bad_exp or bad_dis:
        print("⛔ 自检没过 ⇒ ⛔ 不写")
        return 1

    if args.write:
        for p, (t, crlf) in texts.items():
            p.write_bytes((t.replace("\n", "\r\n") if crlf else t).encode("utf-8"))
        print(f"\n✅ 已写回 {len(texts)} 个件：{', '.join(sorted(p.name for p in texts))}")
        print("   ⚠️ 接着必做：pytest ⇒ ui_parity（登记 U1 漂移）⇒ 盖章 ⇒ 真机 ⇒ 全闸门")
    else:
        print("\n（`--check`：⛔ 未写任何文件）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
