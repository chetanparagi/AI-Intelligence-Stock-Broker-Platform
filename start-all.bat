@echo off
start "Backend" cmd /k "%~dp0start-backend.bat"
start "Frontend" cmd /k "%~dp0start-frontend.bat"
timeout /t 25 >nul
start http://localhost:3000
