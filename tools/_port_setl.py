"""把移植来的 `setl_export.py` 收口：
① 删掉素材包遗留的模块级全局量（`SRC` / `OUT_DIR` / `LABEL` —— 其中 `OUT_DIR` 引用了
   已不存在的 `ROOT`，**import 就会 NameError**）
② `main(src, out_dir, label)` → `build_zip(rows_or_df, out_dir, label)`（数据来源换成库）
③ 对账不过 ⇒ 硬失败；空数据 ⇒ 显式拒做（⛔ 不产出空成品冒充"交付了"）
④ 去掉素材包的 `__main__` 直跑入口（本仓的入口是 `service.export_settlement`）

断言每处唯一命中；不命中就抛错。
"""

from __future__ import annotations

import pathlib

P = pathlib.Path(r"D:\dev\mtrl-workbench\backend\app\report_export\setl_export.py")
src = P.read_text(encoding="utf-8")
steps: list[str] = []


def sub1(old: str, new: str, what: str) -> None:
    global src
    n = src.count(old)
    if n != 1:
        raise SystemExit(f"⛔ [{what}] 锚命中 {n} 次（要求恰好 1 次）")
    src = src.replace(old, new, 1)
    steps.append(what)


# ---------------------------------------------------------------- ① 清全局量
sub1(
    "NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'\n"
    "MONEY_FIELDS = ['期初金额', '收金额', '发金额', '结存金额']\n"
    "SRC = None\n"
    "OUT_DIR = os.path.join(ROOT, 'output')\n"
    "LABEL = ''\n",
    "NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'\n"
    "MONEY_FIELDS = ['期初金额', '收金额', '发金额', '结存金额']\n",
    "① 删掉遗留全局量 SRC/OUT_DIR/LABEL",
)

# ---------------------------------------------------------------- ②③ 换入口
i = src.index("def main(src=None, out_dir=None, label=None):")
j = src.index("if __name__ == '__main__':")
NEW = '''def build_zip(rows_or_df, out_dir, label):
    """把一期的收发结存明细做成 **zip**（分仓库 xlsx ＋ 总表）→ 返回 zip 路径。

    - `rows_or_df`：`setl_detail` 明细行（**本仓主路径**）或已建好的 DataFrame
    - `out_dir`：中间目录（**会被清空** —— 防"月与月之间仓库集合变化"时旧文件残留，
      这是素材包原有行为，保留）
    - `label`：期间标签（如 `2026年9月`）；成品名 = `第四工程公司{label}收发结存表`（同素材包命名）
    """
    require_template(SETL_TEMPLATE)      # ⭐ 本仓适配：模板缺失 / 损坏 ⇒ 显式报错
    df = rows_or_df if isinstance(rows_or_df, pd.DataFrame) else frame_from_rows(rows_or_df)
    if df.empty:
        raise MustReportError(
            '「%s」没有任何收发结存明细 ⇒ **不产出成品文件**'
            '（空文件会被当成"交付了"，比不导出更坏）—— 请先抓取或导入该月数据。' % label
        )

    out_dir = str(out_dir)
    if os.path.isdir(out_dir):
        for f in os.listdir(out_dir):
            try:
                os.remove(os.path.join(out_dir, f))
            except OSError:
                pass
    os.makedirs(out_dir, exist_ok=True)
    show_order = [w for w in df['仓库'].unique() if w == w]
    print('数据:', len(df), '行 | 仓库(%d):' % len(show_order), show_order)

    files = []
    for wh in show_order:
        sub = df[df['仓库'] == wh].copy()
        fn = os.path.join(out_dir, f'{wh}.xlsx')
        write_warehouse_file(sub, fn)
        files.append(fn)
        print('  分仓库:', os.path.basename(fn), len(sub), '行')

    work = os.path.join(out_dir, '_work.xlsx')
    main_fn = os.path.join(out_dir, f'第四工程公司{label}收发结存表.xlsx')
    pv, grand = update_sheet_data(df, work, show_order)
    patch_pivot(work, main_fn, df, show_order)
    os.remove(work)
    files.append(main_fn)

    problems = verify(main_fn, df, pv, grand, show_order)
    # ⭐ 本仓适配：对账不过 ⇒ **硬失败**（素材包只是打印出来给人看；生产里静默交付一个
    #    数字对不上的成品是最坏的失败形态 —— 文件看着正常、数是错的）
    if problems:
        raise MustReportError(
            '成品文件**透视表对账未通过** ⇒ 已中止，未交付：'
            + '；'.join(problems[:5])
            + ('' if len(problems) <= 5 else '（等共 %d 条）' % len(problems))
        )
    print('✓ 透视表对账全部通过 | 总计: 期初%.2f 收%.2f 发%.2f 结存%.2f' % (
        grand['期初金额'], grand['收金额'], grand['发金额'], grand['结存金额']))

    zip_fn = os.path.join(out_dir, f'第四工程公司{label}收发结存表.zip')
    with zipfile.ZipFile(zip_fn, 'w', zipfile.ZIP_DEFLATED) as zf:
        for fn in files:
            zf.write(fn, os.path.basename(fn))
    print('✓ 打包:', os.path.basename(zip_fn))
    # 输出目录只保留 zip（分仓库/总表已进 zip，删除中间 xlsx）
    for fn in files:
        try:
            os.remove(fn)
            print('  清理中间文件:', os.path.basename(fn))
        except OSError:
            pass
    return zip_fn
'''
src = src[:i] + NEW + "\n\n" + src[j:]
steps.append("②③ main → build_zip（对账硬失败 / 空数据拒做）")

# ---------------------------------------------------------------- ④ 去直跑入口
k = src.index("if __name__ == '__main__':")
src = src[:k] + '''if __name__ == '__main__':          # 仅供人工试跑：`python setl_export.py <out_dir> <label>`
    import sys as _sys

    print(build_zip([], _sys.argv[1], _sys.argv[2] if len(_sys.argv) > 2 else ''))
'''
steps.append("④ 直跑入口改成人工试跑提示")

# ---------------------------------------------------------------- 补 import
sub1(
    "from app.report_export.resources import SETL_TEMPLATE, require_template",
    "from app.core.errors import MustReportError\n"
    "from app.report_export.resources import SETL_TEMPLATE, require_template",
    "⑤ 补 MustReportError import",
)

P.write_text(src, encoding="utf-8")
print("✅ 收口完成，共", len(steps), "处：")
for s in steps:
    print("   ·", s)
