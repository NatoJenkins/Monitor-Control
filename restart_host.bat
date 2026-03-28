@echo off
echo Stopping MonitorControl host...
powershell -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*launch_host*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" 2>nul
timeout /t 2 /nobreak >nul
echo Starting MonitorControl host...
start "" pythonw "%~dp0launch_host.pyw"
echo Done.
