@echo off
:: ============================================================
:: Disable Windows Auto Update (full disable)
:: MUST run as Administrator
:: ============================================================
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Please run this script as Administrator.
    echo Right-click the file and choose "Run as administrator".
    pause
    exit /b
)

echo Stopping Windows Update services...
net stop wuauserv /y
net stop UsoSvc /y
net stop WaaSMedicSvc /y

echo Disabling service auto-start...
sc config wuauserv start= disabled
sc config UsoSvc start= disabled
sc config WaaSMedicSvc start= disabled

echo Writing Group Policy registry keys...
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU" /v NoAutoUpdate /t REG_DWORD /d 1 /f
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU" /v AUOptions /t REG_DWORD /d 1 /f

echo.
echo [DONE] Windows Auto Update has been disabled.
echo To restore, run restore_windows_update.bat as Administrator.
pause
