@echo off
REM Runs the three Phase 2 steps in order. Each step waits for the one before.
REM Safe to run again: finished downloads are skipped.
cd /d "%~dp0"
echo === Step 1: US imports by country (Census) ===
py step1_us_imports_census.py
echo.
echo === Step 2: India exports and imports (UN Comtrade) ===
py step2_india_trade_comtrade.py
echo.
echo === Step 3: Checks and summary ===
py step3_checks_and_summary.py
echo.
echo Done. Open the "data" folder for the results.
pause
