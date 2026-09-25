@echo off
:: ============================================================
:: Restore Windows Auto Update (default automatic mode)
:: MUST run as Administrator
:: ============================================================
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Please run this script as Administrator.
    echo Right-click the file and choose "Run as administrator".
    pause
    exit /b
)

echo Restoring service auto-start...
sc config wuauserv start= auto
sc config UsoSvc start= auto
sc config WaaSMedicSvc start= demand

echo Starting Windows Update service...
net start wuauserv

echo Removing Group Policy registry keys...
reg delete "HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU" /v NoAutoUpdate /f
reg delete "HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU" /v AUOptions /f

echo.
echo [DONE] Windows Auto Update has been restored to default automatic mode.
pause
