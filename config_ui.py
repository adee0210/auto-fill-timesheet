"""Giao diện cấu hình account.json và chọn project/activity cho auto-fill-timesheet.

Chạy: python config_ui.py
"""

import json
import os
import subprocess
import sys
import threading
import tkinter as tk
from datetime import datetime, timedelta
from pathlib import Path
from tkinter import messagebox, ttk

# Khi đóng gói thành .exe (PyInstaller), file cấu hình nằm cạnh file .exe
FROZEN = getattr(sys, "frozen", False)
PROJECT_DIR = (
    Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parent
)
WORKER_FLAG = "--worker"
CONFIG_PATH = PROJECT_DIR / "account.json"
EXAMPLE_PATH = PROJECT_DIR / "account.example.json"
OPTIONS_PATH = PROJECT_DIR / "options.json"
MAIN_PATH = PROJECT_DIR / "main.py"
VENV_PYTHON = PROJECT_DIR / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
# Không bật cửa sổ console đen khi chạy main.py từ giao diện (Windows)
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

TEXT_FIELDS = [
    ("url", "URL hệ thống"),
    ("username", "Tên đăng nhập"),
    ("password", "Mật khẩu"),
    ("time_sleep_duration", "Chờ tối đa mỗi bước (giây)"),
    ("start_day", "Từ ngày (DD.MM.YYYY)"),
    ("end_day", "Đến ngày (DD.MM.YYYY)"),
    ("start_time_morning", "Sáng bắt đầu"),
    ("end_time_morning", "Sáng kết thúc"),
    ("start_time_afternoon", "Chiều bắt đầu"),
    ("end_time_afternoon", "Chiều kết thúc"),
]
DATE_FORMAT = "%d.%m.%Y"


def read_json(path):
    with path.open(encoding="utf-8-sig") as f:
        return json.load(f)


def expand_days(text):
    """Đọc ngày/khoảng ngày từ ô nhập. Trả về None (và báo lỗi) nếu có ngày sai."""
    days = []
    for part in text.replace(",", " ").split():
        start, _, end = part.partition("-")
        try:
            first = datetime.strptime(start, DATE_FORMAT)
            last = datetime.strptime(end or start, DATE_FORMAT)
        except ValueError:
            messagebox.showerror(
                "Lỗi ngày", f"Ngày không hợp lệ: {part!r}\n(DD.MM.YYYY hoặc DD.MM.YYYY-DD.MM.YYYY)"
            )
            return None
        while first <= last:
            days.append(first.strftime(DATE_FORMAT))
            first += timedelta(days=1)
    return list(dict.fromkeys(days))


class ConfigApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Auto Fill Timesheet - Cấu hình")
        self.resizable(False, False)

        path = CONFIG_PATH if CONFIG_PATH.exists() else EXAMPLE_PATH
        self.config_data = read_json(path)
        self.project_map = {}  # tên project -> danh sách activity (mapping 1-1)
        self.vars = {}

        self._build_form()
        self._load_options()
        self._fill_form()

    # ---------- Giao diện ----------
    def _build_form(self):
        frame = ttk.Frame(self, padding=12)
        frame.grid(sticky="nsew")
        row = 0

        ttk.Label(frame, text="Trình duyệt").grid(row=row, column=0, sticky="w", pady=2)
        self.vars["driver"] = tk.StringVar()
        ttk.Combobox(
            frame, textvariable=self.vars["driver"], values=["chrome", "edge"],
            state="readonly", width=40,
        ).grid(row=row, column=1, sticky="w", pady=2)
        row += 1

        for key, label in TEXT_FIELDS:
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=2)
            self.vars[key] = tk.StringVar()
            ttk.Entry(
                frame, textvariable=self.vars[key], width=43,
                show="*" if key == "password" else "",
            ).grid(row=row, column=1, sticky="w", pady=2)
            row += 1

        ttk.Separator(frame).grid(row=row, column=0, columnspan=2, sticky="ew", pady=8)
        row += 1

        ttk.Label(frame, text="Project").grid(row=row, column=0, sticky="w", pady=2)
        self.vars["project"] = tk.StringVar()
        self.project_box = ttk.Combobox(frame, textvariable=self.vars["project"], width=40)
        self.project_box.grid(row=row, column=1, sticky="w", pady=2)
        self.project_box.bind("<<ComboboxSelected>>", self._on_project_change)
        row += 1

        ttk.Label(frame, text="Activity").grid(row=row, column=0, sticky="w", pady=2)
        self.vars["activity"] = tk.StringVar()
        self.activity_box = ttk.Combobox(frame, textvariable=self.vars["activity"], width=40)
        self.activity_box.grid(row=row, column=1, sticky="w", pady=2)
        row += 1

        ttk.Label(
            frame,
            text="Để trống project/activity = dùng lựa chọn mặc định như trước.",
            foreground="gray",
        ).grid(row=row, column=0, columnspan=2, sticky="w")
        row += 1

        ttk.Button(
            frame, text="Tải danh sách project/activity từ hệ thống",
            command=self._fetch_options,
        ).grid(row=row, column=0, columnspan=2, sticky="ew", pady=4)
        row += 1

        ttk.Separator(frame).grid(row=row, column=0, columnspan=2, sticky="ew", pady=8)
        row += 1

        ttk.Label(frame, text="Ngày nghỉ lễ\n(mỗi dòng 1 ngày)").grid(
            row=row, column=0, sticky="nw", pady=2
        )
        self.holidays_text = tk.Text(frame, width=32, height=6)
        self.holidays_text.grid(row=row, column=1, sticky="w", pady=2)
        row += 1

        buttons = ttk.Frame(frame)
        buttons.grid(row=row, column=0, columnspan=2, sticky="e", pady=(10, 4))
        ttk.Button(buttons, text="Lưu", command=self._save).pack(side="left", padx=4)
        ttk.Button(buttons, text="Lưu & chạy", command=self._save_and_run).pack(
            side="left", padx=4
        )
        row += 1

        ttk.Separator(frame).grid(row=row, column=0, columnspan=2, sticky="ew", pady=8)
        row += 1

        ttk.Label(
            frame, text="Ngày cần xóa\n(mỗi dòng 1 ngày\nhoặc khoảng\nDD.MM.YYYY-DD.MM.YYYY)"
        ).grid(row=row, column=0, sticky="nw", pady=2)
        self.delete_text = tk.Text(frame, width=32, height=4)
        self.delete_text.grid(row=row, column=1, sticky="w", pady=2)
        row += 1

        ttk.Button(
            frame, text="Xóa toàn bộ entry của các ngày này", command=self._delete
        ).grid(row=row, column=1, sticky="e", pady=4)
        row += 1

        self.log = tk.Text(frame, width=60, height=8, state="disabled")
        self.log.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(6, 0))

    def _fill_form(self):
        for key, var in self.vars.items():
            var.set(str(self.config_data.get(key, "")))
        self.holidays_text.insert("1.0", "\n".join(self.config_data.get("holidays", [])))
        self._on_project_change()

    # ---------- Project / activity ----------
    def _load_options(self):
        if OPTIONS_PATH.exists():
            data = read_json(OPTIONS_PATH)
            self.project_map = {p["name"]: p.get("activities", []) for p in data["projects"]}
        self.project_box["values"] = [""] + list(self.project_map)

    def _on_project_change(self, _event=None):
        activities = self.project_map.get(self.vars["project"].get(), [])
        self.activity_box["values"] = [""] + activities
        if _event is not None and self.vars["activity"].get() not in activities:
            self.vars["activity"].set("")

    # ---------- Lưu / chạy ----------
    def _collect(self):
        data = dict(self.config_data)
        for key, var in self.vars.items():
            data[key] = var.get().strip()

        try:
            data["time_sleep_duration"] = float(data["time_sleep_duration"])
            if data["time_sleep_duration"].is_integer():
                data["time_sleep_duration"] = int(data["time_sleep_duration"])
        except ValueError:
            raise ValueError("Thời gian chờ phải là số.") from None

        holidays = [
            line.strip()
            for line in self.holidays_text.get("1.0", "end").replace(",", "\n").splitlines()
            if line.strip()
        ]
        for value in [data["start_day"], data["end_day"], *holidays]:
            try:
                datetime.strptime(value, DATE_FORMAT)
            except ValueError:
                raise ValueError(f"Ngày không hợp lệ: {value!r} (DD.MM.YYYY)") from None
        data["holidays"] = sorted(
            dict.fromkeys(holidays), key=lambda d: datetime.strptime(d, DATE_FORMAT)
        )
        return data

    def _save(self):
        try:
            data = self._collect()
        except ValueError as exc:
            messagebox.showerror("Lỗi cấu hình", str(exc))
            return False
        with CONFIG_PATH.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        self.config_data = data
        self._write_log(f"Đã lưu {CONFIG_PATH.name}")
        return True

    def _save_and_run(self):
        if self._save():
            self._run_main([], "Đang điền timesheet...")

    def _delete(self):
        days = expand_days(self.delete_text.get("1.0", "end"))
        if days is None:
            return
        if not days:
            messagebox.showinfo("Xóa entry", "Hãy nhập ít nhất một ngày cần xóa.")
            return
        preview = ", ".join(days[:10]) + (" ..." if len(days) > 10 else "")
        if not messagebox.askyesno(
            "Xác nhận xóa",
            f"Xóa TOÀN BỘ entry của {len(days)} ngày sau?\n\n{preview}\n\n"
            "Thao tác này không hoàn tác được.",
            icon="warning",
        ):
            return
        if self._save():
            self._run_main(["--delete", *days], f"Đang xóa entry của {len(days)} ngày...")

    def _fetch_options(self):
        if self._save():
            self._run_main(["--fetch-options"], "Đang tải danh sách project/activity...",
                           on_done=self._after_fetch)

    def _after_fetch(self):
        self._load_options()
        self._on_project_change()
        self._write_log(f"Đã tải {len(self.project_map)} project.")

    def _run_main(self, args, message, on_done=None):
        self._write_log(message)

        def run(command):
            process = subprocess.Popen(
                command,
                cwd=PROJECT_DIR, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"},
                creationflags=NO_WINDOW,
            )
            assert process.stdout is not None
            for line in process.stdout:
                self.after(0, self._write_log, line.rstrip())
            return process.wait()

        def worker():
            # Chạy thẳng bằng Python trong .venv để biết chính xác khi nào main.py xong
            if FROZEN:
                # Bản .exe: tự gọi lại chính nó ở chế độ worker để chạy main.py
                code = run([sys.executable, WORKER_FLAG, *args])
                finish(code)
                return
            code = 0
            if not VENV_PYTHON.exists():
                self.after(0, self._write_log, "Đang tạo môi trường .venv (lần đầu)...")
                code = run([sys.executable, "-m", "venv", str(PROJECT_DIR / ".venv")])
                if code == 0:
                    code = run([str(VENV_PYTHON), "-m", "pip", "install", "-r",
                                str(PROJECT_DIR / "requirements.txt")])
            if code == 0:
                code = run([str(VENV_PYTHON), "-u", str(MAIN_PATH), *args])
            finish(code)

        def finish(code):
            self.after(0, self._write_log, "Hoàn tất." if code == 0 else f"Lỗi (mã {code}).")
            if code == 0 and on_done:
                self.after(0, on_done)

        threading.Thread(target=worker, daemon=True).start()

    def _write_log(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == WORKER_FLAG:
        import traceback

        try:
            import main as timesheet

            timesheet.main(sys.argv[2:])
        except Exception:
            traceback.print_exc()
            sys.exit(1)
    else:
        ConfigApp().mainloop()
