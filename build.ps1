# Đóng gói Auto Fill Timesheet thành app chạy độc lập (không cần cài Python).
# Chạy: powershell -ExecutionPolicy Bypass -File build.ps1
# Kết quả: release\AutoFillTimesheet.zip
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$py = ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { python -m venv .venv }
& $py -m pip install -q -r requirements.txt pyinstaller

& $py -m PyInstaller --noconfirm --clean --windowed --onedir `
    --name AutoFillTimesheet `
    --hidden-import main `
    --collect-all selenium `
    config_ui.py

$app = "dist\AutoFillTimesheet"
# Chỉ đóng gói file cấu hình mẫu, KHÔNG đóng gói account.json cá nhân
Copy-Item account.example.json "$app\account.json" -Force
Copy-Item HUONG_DAN.txt "$app\HUONG_DAN.txt" -Force

New-Item -ItemType Directory -Force release | Out-Null
& $py -c "import shutil; shutil.make_archive('release/AutoFillTimesheet', 'zip', 'dist', 'AutoFillTimesheet')"
Write-Host "Da tao release\AutoFillTimesheet.zip"
