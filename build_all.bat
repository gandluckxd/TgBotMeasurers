@echo off
chcp 65001 >nul 2>&1
echo ============================================================
echo Building EXE files...
echo ============================================================
echo.

echo [1/2] Building MeasurersBot.exe...
.\venv\Scripts\pyinstaller.exe --clean MeasurersBot.spec
if %errorlevel% neq 0 (
    echo ERROR: Failed to build MeasurersBot.exe
    pause
    exit /b 1
)
echo OK MeasurersBot.exe built successfully
echo.

echo [2/2] Building sheets_exporter.exe...
.\venv\Scripts\pyinstaller.exe --clean sheets_exporter.spec
if %errorlevel% neq 0 (
    echo ERROR: Failed to build sheets_exporter.exe
    pause
    exit /b 1
)
echo OK sheets_exporter.exe built successfully
echo.

echo.
echo [3/3] Copying config files...
copy .env dist\.env >nul 2>&1
if exist credentials.json (
    copy credentials.json dist\credentials.json >nul 2>&1
    echo OK Copied: .env, credentials.json
) else (
    echo WARNING: credentials.json not found, copied only .env
)
echo.

echo ============================================================
echo OK All files built successfully!
echo ============================================================
echo.
echo Files in dist folder:
echo   - MeasurersBot.exe
echo   - sheets_exporter.exe
echo   - .env
echo   - credentials.json
echo.
echo Copy entire dist folder to server
echo Database measurerers_bot.db will be created automatically
echo.
pause
