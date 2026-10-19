"""Open only the generated copy read-only and render a print preview through the installed spreadsheet app."""
from pathlib import Path
import json
import hashlib
import winreg
import win32com.client

root = Path(__file__).resolve().parents[2]
evidence = root / '.artifacts/machinery-fee-workflow/implementation-20261019'
path = Path(json.loads((evidence / 'export-verification-input.json').read_text(encoding='utf-8'))['path'])
before = hashlib.sha256(path.read_bytes()).hexdigest()
progid = None
for name in ('Excel.Application', 'ket.Application', 'et.Application'):
    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, name + '\\CLSID'):
            progid = name
            break
    except FileNotFoundError:
        continue
if not progid:
    print(json.dumps({'native_application': 'unavailable', 'opened': False}))
    raise SystemExit(2)
app = win32com.client.DispatchEx(progid)
app.Visible = False
app.DisplayAlerts = False
book = None
try:
    book = app.Workbooks.Open(str(path), UpdateLinks=0, ReadOnly=True)
    print_file = evidence / 'mechanical-print-preview.pdf'
    book.ExportAsFixedFormat(0, str(print_file))
    result = {'application': progid, 'version': str(app.Version), 'opened': True,
              'sheets': [book.Worksheets(i).Name for i in range(1, book.Worksheets.Count + 1)],
              'print_preview': str(print_file), 'print_bytes': print_file.stat().st_size,
              'original_export_unchanged': hashlib.sha256(path.read_bytes()).hexdigest() == before}
    (evidence / 'native-spreadsheet-verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))
finally:
    if book is not None:
        book.Close(SaveChanges=False)
    app.Quit()
