"""`TAIL-210` 第 3 批②（重复句）· 把"**同一件事在两处说**"的几句**收进一处定义**。

口径（用户 2026-10-01「123 按推荐」＋ 审计件 §三-5「只并『同一件事在两处说』的」）：
- **并**：同一句/同一标签在 ≥2 处出现、且**将来改一处会漏另一处** ⇒ 抽成壳内共用常量（同件内就地声明；
  跨件的声明在 `core.js` —— ⚠️ `actions.js` 在**运行期**引用后声明的 const，**本仓既有做法**（`actions.js` 里 `IMP.step=0` 就是这么用的）。
- **⛔ 不并**（都写进审计件理由）：
  ① `class="tip"` 块里的两处（`core.js:1380/1414` · `actions.js:901/1041`）—— 抽成 `${CONST}` 后，
     `tests/test_ux_text.py::test_说明块都不超长` 的 `_JSX` 会把它**整段剥掉** ⇒ 那条判据对这块**失明**
     （弹窗那两处**离线是唯一守卫**）⇒ **不拿守卫换去重**；
  ② `pages-a.js:264` / `pages-b.js:59` —— 共同片段只有「文件名含项目展示名与当前年月（§7.1）。」19 字；
  ③ `m12`（已撤页残片）那 6 处 —— 按 `actions.js:2039` 的既定规矩：**要清就整体清**（另一件大事）。
- **删一处**（乙案）：`index.html:1503` 卡头把 CALIB 条 1 已说过的话又念一遍 ⇒ 删掉重复那半句。

跑法：`backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_front5_dup.py`   # 干跑
      `… --apply`                                                 # 落盘
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SHELL = "backend/app/web/shell"
WEB = "backend/app/web"

#: (件, 行号, 原文, 新文, 该行命中次数) —— ⚠️ 只做**行内**替换（⛔ 不动行数）
REPL: list[tuple[str, int, str, str, int]] = [
    # ── core.js：抓取失败提示 / 降级提示 / 归属弹窗那两句 ──────────────────
    (f"{SHELL}/core.js", 693,
     '+ `<span class="mut sm">本系统<b>不会自动重试登录</b>—— 请确认 i8 账号后再试；i8 抓不到时可走「手动导入」</span>`);',
     '+ `<span class="mut sm">${I8_LOGIN_TIP}</span>`);', 1),
    (f"{SHELL}/core.js", 853,
     '+ `<span class="mut sm">本系统<b>不会自动重试登录</b>—— 请确认 i8 账号后再试；i8 抓不到时可走「手动导入」</span>`);',
     '+ `<span class="mut sm">${I8_LOGIN_TIP}</span>`);', 1),
    (f"{SHELL}/core.js", 677,
     '+ `<span class="mut sm">可到「导入」入口上传 i8 导出的 Excel</span>`);',
     '+ `<span class="mut sm">${IMP_DEGRADE_TIP}</span>`);', 1),
    (f"{SHELL}/core.js", 824,
     '+ `<span class="mut sm">可到「导入」入口上传 i8 导出的 Excel</span>`);',
     '+ `<span class="mut sm">${IMP_DEGRADE_TIP}</span>`);', 1),
    (f"{SHELL}/core.js", 483,
     '>选已有小微时，<b>须填一个出现在上面单据名里的关键词</b>（选中后<b>去重追加</b>到该小微名下，供下次自动命中）；填不出说明不是它。</p>',
     '>${OWN_KW_HINT}</p>', 1),
    (f"{SHELL}/core.js", 488, '<label>识别关键词（须出现在单据名里）</label>',
     '<label>${OWN_KW_LABEL}</label>', 1),
    # ── actions.js：三条"表内增行"toast / 两条"取消"toast / 归属弹窗两句 / i8 账号标签 ──
    (f"{SHELL}/actions.js", 704, '（尚未保存）—— 填完点该行「保存」写入、点「取消」丢弃', '${DRAFT_HINT}', 1),
    (f"{SHELL}/actions.js", 828, '（尚未保存）—— 填完点该行「保存」写入、点「取消」丢弃', '${DRAFT_HINT}', 1),
    (f"{SHELL}/actions.js", 2047, '（尚未保存）—— 填完点该行「保存」写入、点「取消」丢弃', '${DRAFT_HINT}', 1),
    (f"{SHELL}/actions.js", 750,
     "toast(was?`已放弃对 <b>${esc(was)}</b> 的修改 —— 该行<b>保持原样</b>（草稿未写入）`:'已取消新增 —— 草稿行丢弃，<b>未写入任何数据</b>'); }",
     'toast(DRAFT_CANCEL_MSG(was)); }', 1),
    (f"{SHELL}/actions.js", 838,
     "toast(was?`已放弃对 <b>${esc(was)}</b> 的修改 —— 该行<b>保持原样</b>（草稿未写入）`:'已取消新增 —— 草稿行丢弃，<b>未写入任何数据</b>'); }",
     'toast(DRAFT_CANCEL_MSG(was)); }', 1),
    (f"{SHELL}/actions.js", 1167,
     '>选已有小微时，<b>须填一个出现在上面单据名里的关键词</b>（选中后<b>去重追加</b>到该小微名下，供下次自动命中）；填不出说明不是它。</p>',
     '>${OWN_KW_HINT}</p>', 1),
    (f"{SHELL}/actions.js", 1177, '<label>识别关键词（须出现在单据名里）</label>',
     '<label>${OWN_KW_LABEL}</label>', 1),
    (f"{SHELL}/actions.js", 1307, '<label>i8 账号（§7.8 · 每人一份）</label>',
     '<label>${I8_ACC_LABEL}</label>', 1),
    (f"{SHELL}/actions.js", 1312, '<label>i8 账号（§7.8 · 每人一份）</label>',
     '<label>${I8_ACC_LABEL}</label>', 1),
    # ── legacy.js：「这批数据进哪个项目」那个 label 在两个分支各写一遍 ──────
    (f"{SHELL}/legacy.js", 433, '<label>这批数据进哪个项目（键 = 仓库名，§2.7.4）</label>',
     '<label>${IMP_PJ_LABEL}</label>', 1),
    (f"{SHELL}/legacy.js", 441, '<label>这批数据进哪个项目（键 = 仓库名，§2.7.4）</label>',
     '<label>${IMP_PJ_LABEL}</label>', 1),
    # ── index.html：卡头把 CALIB 已说过的话又念一遍 ⇒ 删重复那半句（乙案）──
    (f"{WEB}/index.html", 1503, '命中即剔除，<b>标记保留、可筛选、不销毁数据</b>', '命中即剔除', 1),
]

#: (件, 锚点整行, 要插在锚点**之前**的整块) —— ⚠️ 后做（会改行数）
DECLS: list[tuple[str, str, str]] = [
    (f"{SHELL}/core.js",
     "/* ⭐ 名字格**按内容定宽**（`ACC-PRJ-LIST-001/001-07`「长项目名必须完整可读 —— ⛔ 不得被容器硬切」）",
     "/* ---------- 共用文案（**一处在说、多处引用** ⇒ ⛔ 别在两处各写一遍）----------\n"
     "   ⭐ 2026-10-01（`TAIL-210` 批 3b）：这几句原先在 2 处逐字重复（同一件事、两处各写一遍\n"
     "   ⇒ 改一处必漏另一处）。⚠️ 判「要不要并」只看一句：**同一句在 ≥2 处、且将来会一起改**吗？\n"
     "   ⛔ `class=\"tip\"` 块里的那两处**刻意不并**（抽成 `${CONST}` 会让离线那条长度判据对它们**失明**）。 */\n"
     "const I8_LOGIN_TIP = '本系统<b>不会自动重试登录</b>—— 请确认 i8 账号后再试；i8 抓不到时可走「手动导入」';\n"
     "const IMP_DEGRADE_TIP = '可到「导入」入口上传 i8 导出的 Excel';\n"
     "const OWN_KW_LABEL = '识别关键词（须出现在单据名里）';\n"
     "const OWN_KW_HINT = '选已有小微时，<b>须填一个出现在上面单据名里的关键词</b>（选中后<b>去重追加</b>到该小微名下，供下次自动命中）；填不出说明不是它。';\n"),
    (f"{SHELL}/actions.js",
     "/* ⭐ `M5-5`：跨页写动作的**统一包装**（关联 / 解绑 / 集采实际供应商）—— 成功后**两侧同刷**。",
     "/* ---------- 共用文案（**一处在说、多处引用** ⇒ ⛔ 别在两处各写一遍）----------\n"
     "   ⭐ 2026-10-01（`TAIL-210` 批 3b）：三条「表内增行」toast · 两条「取消」toast · `i8 账号`那枚 label\n"
     "   原先各写一遍。⚠️ `DRAFT_CANCEL_MSG` 是**函数**（两处只差一个局部变量 `was`）。\n"
     "   ⚠️ `OWN_KW_*` 两句声明在 `core.js`（那边也用）—— 本件在**运行期**引用后声明的 const，**本仓既有做法**。 */\n"
     "const DRAFT_HINT = '（尚未保存）—— 填完点该行「保存」写入、点「取消」丢弃';\n"
     "const DRAFT_CANCEL_MSG = was => was\n"
     "  ? `已放弃对 <b>${esc(was)}</b> 的修改 —— 该行<b>保持原样</b>（草稿未写入）`\n"
     "  : '已取消新增 —— 草稿行丢弃，<b>未写入任何数据</b>';\n"
     "const I8_ACC_LABEL = 'i8 账号（§7.8 · 每人一份）';\n"),
    (f"{SHELL}/legacy.js",
     "const SET = {items: [], logs: [], tips: [], errs: [], msg: '', kind: 'ok'};   /* 系统设置 */",
     "/* ---------- 共用文案（**一处在说、多处引用** ⇒ ⛔ 别在两处各写一遍）----------\n"
     "   ⭐ 2026-10-01（`TAIL-210` 批 3b）：这个 label 在 `ctxBar` 的两个分支各写了一遍。 */\n"
     "const IMP_PJ_LABEL = '这批数据进哪个项目（键 = 仓库名，§2.7.4）';\n"),
]


def _read(p: pathlib.Path) -> str:
    with open(p, encoding="utf-8", newline="") as f:
        return f.read()


def _write(p: pathlib.Path, text: str) -> None:
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def main() -> int:
    apply = "--apply" in sys.argv
    cache: dict[str, str] = {}
    bad: list[str] = []
    for rel, ln, old, new, cnt in REPL:
        p = ROOT / rel
        cache.setdefault(rel, _read(p))
        lines = cache[rel].split("\n")
        if ln - 1 >= len(lines):
            bad.append(f"{rel}:{ln} —— 行号超出")
            continue
        got = lines[ln - 1].count(old)
        if got != cnt:
            bad.append(f"{rel}:{ln} —— 期望 {cnt} 次、实测 {got} 次：{old[:60]!r}")
    for rel, anchor, _ in DECLS:
        p = ROOT / rel
        cache.setdefault(rel, _read(p))
        n = cache[rel].count("\n" + anchor)
        if n != 1:
            bad.append(f"{rel} —— 锚点命中 {n} 次（要 1）：{anchor[:50]!r}")
    print(f"替换 {len(REPL)} 条 ＋ 声明 {len(DECLS)} 块 ⇒ 不达标 {len(bad)}")
    for x in bad:
        print("   ✗", x)
    if bad or not apply:
        print("（干跑 —— ⛔ 没写盘）" if not apply else "（⛔ 不达标 ⇒ 整批不写盘）")
        return 1 if bad else 0

    for rel in sorted(cache):
        p = ROOT / rel
        text = _read(p)
        lines = text.split("\n")
        for r, ln, old, new, cnt in REPL:
            if r != rel:
                continue
            assert lines[ln - 1].count(old) == cnt, f"写盘前复核失败 {rel}:{ln}"
            lines[ln - 1] = lines[ln - 1].replace(old, new, cnt)
        text = "\n".join(lines)
        for r, anchor, block in DECLS:
            if r != rel:
                continue
            assert text.count("\n" + anchor) == 1, f"写盘前复核失败（锚点）{rel}"
            text = text.replace("\n" + anchor, "\n" + block + anchor, 1)
        _write(p, text)
        print(f"   已写 {rel}")
    print(f"\n✅ 落盘完成：{len(cache)} 件")
    return 0


if __name__ == "__main__":
    sys.exit(main())
