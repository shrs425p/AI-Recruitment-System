@echo off
:: Run this file as Administrator (right-click -> Run as administrator)
echo Adding firewall rule for ARS Interview Server (port 5000)...
netsh advfirewall firewall delete rule name="ARS Interview Server (Port 5000)" >nul 2>&1
netsh advfirewall firewall add rule name="ARS Interview Server (Port 5000)" dir=in action=allow protocol=TCP localport=5000
if %errorlevel%==0 (
    echo.
    echo SUCCESS: Firewall rule added. Candidates can now access the interview over WiFi.
) else (
    echo.
    echo FAILED: Please run this file as Administrator.
)
echo.
pause
