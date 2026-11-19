"""在隔离目录运行桌面流程，模拟 i8 端点并独立读回报表。"""

import io
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

import httpx
import openpyxl

import build
import desktop
import report
from app.mod02_i8.login import LOGIN_PATH


def export_bytes():
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "报表1"
    from app.report_export.schema_cols import SFJC_HEADER
    sheet.append(SFJC_HEADER)
    for warehouse, end in [("甲仓", 13.21), ("甲仓", 15.66), ("乙仓", 14.31)]:
        sheet.append([warehouse, "材料", "0001", "=测试品", "A", "件", "主材",
                      1, 10, 1, 10, 10, 1, 1, 20-end, 1, end])
        sheet.cell(sheet.max_row, 4).data_type = "s"
    sheet.append(["合计", None, None, None, None, None, None, 3, 30])
    buffer = io.BytesIO()
    workbook.save(buffer)
    workbook.close()
    return buffer.getvalue()


class DesktopCheck(unittest.TestCase):
    def test_from_login_to_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            dest = directory / "月报.zip"
            client_type = httpx.Client
            raw = export_bytes()
            calls = []
            favorites = []
            def reply(request):
                path = request.url.path
                calls.append(path)
                if path == LOGIN_PATH:
                    self.assertNotIn(b"fake-password", request.content)
                    return httpx.Response(200, text='{"accesstoken":"mock"}',
                                          headers={"Set-Cookie": "sid=test; Path=/"})
                self.assertEqual(request.headers["Cookie"], "sid=test")
                if path.endswith("GetCommonUseList"):
                    return httpx.Response(200, json={"Record": favorites})
                self.assertEqual(path, report.I8_PATH_REPORT_EXPORT)
                payload = json.loads(request.content)["queryParams"][0]["sheetQueryParams"]
                self.assertEqual({p["paramKey"]: p["paramValue"] for p in payload},
                                 dict(a="2026", b="10", aa="2026", bb="10", pc="101"))
                return httpx.Response(200, content=raw)

            def client(**kwargs):
                return client_type(transport=httpx.MockTransport(reply), **kwargs)

            def finish(window):
                until = time.monotonic() + 20
                while window.busy and time.monotonic() < until:
                    window.root.update()
                    time.sleep(0.02)
                self.assertFalse(window.busy)

            with (patch.object(report, "ASSETS", build.assets(directory)),
                  patch("httpx.Client", side_effect=client),
                  patch.dict("os.environ", LOCALAPPDATA=tmp),
                  patch.object(desktop.filedialog, "asksaveasfilename", return_value=str(dest)),
                  patch.object(desktop.messagebox, "showerror") as error,
                  patch.object(desktop.messagebox, "showinfo")):
                root = desktop.tk.Tk()
                root.withdraw()
                window = desktop.Window(root)
                try:
                    window.site.set("https://i8.example.invalid")
                    window.user.set("test")
                    window.password.set("fake-password")
                    window.company.set("试点公司")
                    window.month.set("2026-10")
                    window.refresh()
                    finish(window)
                    self.assertIn("常用项目", window.status.get())
                    self.assertTrue(window.export.instate(["disabled"]))
                    favorites.extend([{"PhId": "101", "BillName": "测试甲"},
                                      {"PhId": "102", "BillName": "测试乙"}])
                    window.refresh()
                    finish(window)
                    window.toggle("102")
                    self.assertEqual(window.selected(), ["101"])
                    window.save()
                    finish(window)
                    error.assert_not_called()
                    with ZipFile(dest) as archive:
                        self.assertEqual(set(archive.namelist()), {
                            "试点公司2026年10月收发结存表.xlsx", "甲仓.xlsx", "乙仓.xlsx"})
                        main = openpyxl.load_workbook(io.BytesIO(archive.read(
                            "试点公司2026年10月收发结存表.xlsx")))
                        summary = main["Sheet1"]
                        self.assertEqual([summary[f"E{i}"].value for i in (4, 5, 6)],
                                         [28.87, 14.31, 43.18])
                        self.assertEqual(main["报表1"].max_row, 4)
                        self.assertEqual(main["报表1"]["D2"].data_type, "s")
                        self.assertEqual(summary._pivots[0].cache.recordCount, 3)
                        self.assertEqual(summary._pivots[0].location.ref, "A3:E6")
                        main.close()
                        for wh, count in (("甲仓", 2), ("乙仓", 1)):
                            sub = openpyxl.load_workbook(io.BytesIO(archive.read(wh + ".xlsx")))
                            self.assertEqual(sub.active.max_row, count + 1)
                            self.assertEqual(sub.active["C2"].value, "0001")
                            self.assertEqual(sub.active["D2"].data_type, "s")
                            sub.close()
                    before = dest.read_bytes()
                    raw = b"session expired"
                    window.save()
                    finish(window)
                    error.assert_called_once()
                    self.assertEqual(dest.read_bytes(), before)
                    window.user.set("different")
                    self.assertFalse(window.selected())
                    self.assertEqual(calls.count(LOGIN_PATH), 2)
                finally:
                    window.close()


if __name__ == "__main__":
    unittest.main()
