"""收发结存桌面窗口：核对本次常用项目范围，按所选月份保存报表。"""

from __future__ import annotations

import json
import os
import queue
import threading
import tkinter as tk
from datetime import date, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import httpx
import pywintypes

import preferences
from report import GUIDE, connect, generate, projects, validate_name


class Window:
    def __init__(self, root):
        self.root = root
        root.title("收发结存月报")
        root.minsize(560, 560)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        panel = ttk.Frame(root, padding=18)
        panel.grid(sticky="nsew")
        panel.columnconfigure(1, weight=1)
        self.settings = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "收发结存" / "偏好.json"
        try:
            saved = json.loads(self.settings.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            saved = {}
        if not isinstance(saved, dict):
            saved = {}
        self.save_timer = None
        self.dirty = False
        self.site = tk.StringVar(value=preferences.route_for(saved.get("site")))
        self.company = tk.StringVar(value=saved.get("company", ""))
        self.user = tk.StringVar(value=saved.get("user", ""))
        self.ciphertext = saved.get("protected_password", "")
        initial_status = "选择线路，核对账号后读取常用项目。"
        try:
            password = preferences.unprotect(self.ciphertext)
        except (pywintypes.error, ValueError, TypeError):
            password = ""
            initial_status = "此 Windows 用户无法读取上次保存的密码，请重新填写。"
        self.password = tk.StringVar(value=password)
        self.saved_password = password
        self.excluded = saved.get("excluded_projects", {})
        if not isinstance(self.excluded, dict):
            self.excluded = {}
        self.folder = saved.get("folder", "")
        previous = date.today().replace(day=1) - timedelta(days=1)
        self.month = tk.StringVar(value=saved.get("month", previous.strftime("%Y-%m")))
        self.busy = False
        self.client = None
        self.messages = queue.Queue()
        self.fields = []
        for row, (name, variable) in enumerate((
                ("i8 地址", self.site), ("i8 账号", self.user), ("密码", self.password),
                ("报表单位名称", self.company), ("核算年月", self.month))):
            ttk.Label(panel, text=name).grid(row=row, column=0, sticky="w", padx=(0, 14))
            if variable is self.site:
                entry = ttk.Combobox(panel, textvariable=variable, values=tuple(preferences.ROUTES),
                                     state="readonly")
                self.route_box = entry
            elif variable is self.month:
                months = []
                candidate = date.today().replace(day=1)
                for _ in range(25):
                    months.append(candidate.strftime("%Y-%m"))
                    candidate = (candidate - timedelta(days=1)).replace(day=1)
                entry = ttk.Combobox(panel, textvariable=variable, values=months)
            else:
                entry = ttk.Entry(panel, textvariable=variable, show="•" if row == 2 else "")
            entry.grid(row=row, column=1, sticky="ew", pady=3)
            self.fields.append(entry)
        self.fetch = ttk.Button(panel, text="连接并读取常用项目", command=self.refresh)
        self.fetch.grid(row=5, column=0, columnspan=2, sticky="w", pady=(8, 2))
        ttk.Label(panel, text="连接时可能使该账号在其他设备上的 i8 会话下线。").grid(
            row=6, column=0, columnspan=2, sticky="w")
        ttk.Separator(panel).grid(row=7, column=0, columnspan=2, sticky="ew", pady=12)
        ttk.Label(panel, text="本次报表项目").grid(row=8, column=0, sticky="w")
        self.count = ttk.Label(panel)
        self.count.grid(row=8, column=1, sticky="e")
        ttk.Label(panel, text=GUIDE, wraplength=500, justify="left").grid(
            row=9, column=0, columnspan=2, sticky="w", pady=(4, 8))
        table = ttk.Frame(panel)
        table.grid(row=10, column=0, columnspan=2, sticky="nsew")
        panel.rowconfigure(10, weight=1)
        table.columnconfigure(0, weight=1)
        table.rowconfigure(0, weight=1)
        self.list = ttk.Treeview(table, columns=("selected", "name"), show="headings",
                                 selectmode="browse", height=7)
        self.list.heading("selected", text="纳入")
        self.list.heading("name", text="i8 常用项目")
        self.list.column("selected", width=54, stretch=False, anchor="center")
        self.list.column("name", width=380)
        self.list.grid(sticky="nsew")
        scroll = ttk.Scrollbar(table, orient="vertical", command=self.list.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.list.configure(yscrollcommand=scroll.set)
        self.list.bind("<ButtonRelease-1>", lambda e: self.toggle(self.list.identify_row(e.y)))
        self.list.bind("<space>", lambda e: self.toggle(self.list.focus()))
        self.status = tk.StringVar(value=initial_status)
        ttk.Label(panel, textvariable=self.status, wraplength=500, justify="left").grid(
            row=11, column=0, columnspan=2, sticky="w", pady=8)
        self.export = ttk.Button(panel, text="生成收发结存报表…", command=self.save)
        self.export.grid(row=12, column=0, columnspan=2, sticky="e")
        for var in (self.site, self.user, self.password):
            var.trace_add("write", lambda *_: self.disconnect())
        for var in (self.site, self.user, self.password, self.company, self.month):
            var.trace_add("write", lambda *_: self.schedule_save())
        self.update_controls()
        root.protocol("WM_DELETE_WINDOW", self.close)

    def schedule_save(self):
        self.dirty = True
        if self.save_timer is not None:
            self.root.after_cancel(self.save_timer)
        self.save_timer = self.root.after(350, self.persist)

    def persist(self):
        if self.save_timer is not None:
            self.root.after_cancel(self.save_timer)
            self.save_timer = None
        if not self.dirty:
            return True
        password = self.password.get()
        try:
            if password != self.saved_password:
                self.ciphertext = preferences.protect(password)
                self.saved_password = password
            preferences.write(self.settings, {
                "site": preferences.ROUTES[self.site.get()], "user": self.user.get(),
                "protected_password": self.ciphertext, "company": self.company.get(),
                "month": self.month.get(), "excluded_projects": self.excluded, "folder": self.folder,
            })
        except (OSError, pywintypes.error):
            self.status.set("本次设置未能保存，请检查 Windows 用户配置目录的写入权限。")
            return False
        self.dirty = False
        return True

    def disconnect(self):
        if self.client is not None:
            self.client.close()
            self.client = None
        self.list.delete(*self.list.get_children())
        self.fetch.configure(text="连接并读取常用项目")
        self.status.set("请连接 i8 并核对本账号的常用项目。")
        self.update_controls()

    def selected(self):
        return [key for key in self.list.get_children() if self.list.set(key, "selected") == "✓"]

    def update_controls(self):
        selected = len(self.selected())
        self.count.configure(text=f"已选 {selected} / {len(self.list.get_children())} 个")
        self.export.configure(state="normal" if selected and not self.busy else "disabled")
        for widget in [self.fetch, *self.fields]:
            widget.configure(state="disabled" if self.busy else "normal")
        if not self.busy:
            self.route_box.configure(state="readonly")

    def toggle(self, key):
        if key and not self.busy:
            checked = self.list.set(key, "selected") == "✓"
            self.list.set(key, "selected", "" if checked else "✓")
            account = self.user.get().strip()
            excluded = set(self.excluded.get(account, []))
            if checked:
                excluded.add(key)
            else:
                excluded.discard(key)
            self.excluded[account] = sorted(excluded)
            self.schedule_save()
            self.update_controls()

    def run(self, label, work, done, failed=None):
        self.busy = True
        self.status.set(label)
        self.update_controls()

        def worker():
            try:
                self.messages.put((True, work()))
            except Exception as exc:
                if isinstance(exc, httpx.HTTPError):
                    error = "i8 请求失败，请核对网络、登录状态和账号权限后重试。"
                elif isinstance(exc, OSError):
                    error = "读写文件失败。请确认保存位置有可用空间和写入权限，文件未被占用。"
                else:
                    error = str(exc) or "操作失败，请核对输入后重试。"
                self.messages.put((False, error))

        def poll():
            try:
                ok, value = self.messages.get_nowait()
            except queue.Empty:
                self.root.after(100, poll)
                return
            self.busy = False
            if ok:
                done(value)
            else:
                if failed:
                    failed()
                self.status.set(value)
                messagebox.showerror("操作未完成", value, parent=self.root)
            self.update_controls()

        threading.Thread(target=worker, daemon=True).start()
        self.root.after(100, poll)

    def refresh(self):
        site = preferences.ROUTES[self.site.get()]
        user, password, previous = self.user.get(), self.password.get(), self.client
        unchecked = self.excluded.get(user.strip(), [])
        self.list.delete(*self.list.get_children())

        def read():
            client = previous or connect(site, user, password)
            try:
                return client, projects(client)
            except Exception:
                if previous is None:
                    client.close()
                raise

        def display(result):
            self.client, names = result
            for key, name in names.items():
                self.list.insert("", "end", iid=key, values=("" if key in unchecked else "✓", name))
            self.fetch.configure(text="刷新常用项目")
            self.status.set("请核对名单，点击项目可切换是否纳入。" if names else "未找到常用项目。" + GUIDE)

        self.run("正在读取 i8 常用项目…", read, display, self.disconnect)

    def save(self):
        from app.mod02_i8.report_export import single_month
        month, company, keys = self.month.get().strip(), self.company.get().strip(), self.selected()
        try:
            year, number, _, _ = single_month(month)
            validate_name(company)
        except Exception as exc:
            messagebox.showerror("请核对报表信息", str(exc))
            return
        name = f"{company}{year}年{number}月收发结存表.zip"
        path = filedialog.asksaveasfilename(parent=self.root, title="保存总表和分仓表",
                                            initialdir=self.folder or None,
                                            initialfile=name, defaultextension=".zip",
                                            filetypes=[("ZIP 压缩包", "*.zip")])
        if not path:
            return
        self.folder = str(Path(path).parent)
        self.schedule_save()
        def complete(result):
            count, rows = result
            self.status.set(f"已保存到 {path}")
            messagebox.showinfo("报表已生成", f"{rows} 条明细，{count} 份分仓表和 1 份总表。\n\n{path}")
        self.run("正在从 i8 取数并生成报表…",
                 lambda: generate(self.client, month, keys, company, Path(path)), complete)

    def close(self):
        if self.busy:
            self.status.set("正在处理，请等待本次操作结束后关闭。")
            return
        if not self.persist() and not messagebox.askyesno(
                "设置尚未保存", "无法保存本次设置。仍要退出吗？", parent=self.root):
            return
        self.disconnect()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    Window(root)
    root.mainloop()
