@echo off
:: Run this file as Administrator (right-click -> Run as administrator)
echo ===================================================
echo   AI Recruitment System - Candidate Firewall Setup
echo ===================================================
echo Adding inbound firewall rule for ARS Candidate HTTPS Portal (port 5000)...
netsh advfirewall firewall delete rule name="ARS Candidate HTTPS Portal (Port 5000)" >nul 2>&1
netsh advfirewall firewall add rule name="ARS Candidate HTTPS Portal (Port 5000)" dir=in action=allow protocol=TCP localport=5000
if %errorlevel%==0 (
    echo.
    echo SUCCESS: Firewall rule added. Candidates can now access the interview portal
    echo          over the LAN at: https://^<host-ip^>:5000/candidate-interview/^<token^>
    echo.
    echo NOTE: HR Management Portal remains secure on loopback (127.0.0.1:5001)
    echo       and is NOT exposed to the local network.
) else (
    echo.
    echo FAILED: Please right-click this file and select "Run as administrator".
)
echo.
pause
