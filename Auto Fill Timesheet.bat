@echo off
rem Mo giao dien Auto Fill Timesheet (khong hien cua so console)
where pythonw >nul 2>nul && (start "" pythonw "%~dp0config_ui.py") || (start "" pyw "%~dp0config_ui.py")
