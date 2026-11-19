"""使用 Windows x64 Python 构建一个包含 Tk 和报表依赖的 EXE。"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parents[1] / "backend"
sys.path.insert(0, str(BACKEND))


def assets(work):
    import openpyxl
    from openpyxl.packaging.core import DocumentProperties
    from openpyxl.packaging.custom import CustomPropertyList
    from app.mod02_i8.sm2_crypto import _BUILTIN_PRIVATE_KEY, _crypt
    from app.report_export import setl_export as writer

    dest = work / "assets"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "public.txt").write_text(_crypt(_BUILTIN_PRIVATE_KEY).public_key, encoding="ascii")
    source = writer.require_template(writer.SETL_TEMPLATE)
    # 单机模板只保留版式；原模板的透视字典也包含旧仓库和业务行。
    seed = work / "seed.xlsx"
    with ZipFile(source) as original, ZipFile(seed, "w", ZIP_DEFLATED) as stripped:
        for item in original.infolist():
            data = original.read(item)
            if item.filename == "xl/pivotCache/pivotCacheDefinition1.xml":
                data = re.sub(b'(<sharedItems\\b[^>]*>).*?(</sharedItems>)', rb'\1\2', data,
                              flags=re.S)
                data = re.sub(b' refreshedBy="[^"]*"', b'', data)
            stripped.writestr(item, data)
    frame = writer.frame_from_rows([{field: 0 if head in writer.NUM_COLS else "示例"
                                     for field, head in writer.FIELD_TO_HEADER}])
    sheet = work / "sheet.xlsx"
    writer.update_sheet_data(frame, sheet, ["示例"])
    workbook = openpyxl.load_workbook(sheet)
    workbook.properties = DocumentProperties(creator="收发结存")
    workbook.custom_doc_props = CustomPropertyList()
    workbook.save(sheet)
    workbook.close()
    writer.patch_pivot(sheet, dest / "layout.xlsx", frame, ["示例"], template=seed)
    return dest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("work", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    work = args.work.resolve()
    dest = assets(work)
    subprocess.run([
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--onefile", "--windowed",
        "--name", "收发结存", "--paths", str(BACKEND), "--add-data", f"{dest}{os.pathsep}assets",
        "--exclude-module", "app.mod02_i8.sm2_crypto", "--exclude-module", "app.core.app_settings",
        "--exclude-module", "pytest", "--distpath", str(args.out.resolve()),
        "--workpath", str(work / "freeze"), "--specpath", str(work), str(HERE / "desktop.py"),
    ], check=True)


if __name__ == "__main__":
    main()
