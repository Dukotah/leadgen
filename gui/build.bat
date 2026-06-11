@echo off
REM ============================================================
REM  Build LeadEngine.exe locally on Windows.
REM  Requires Python 3.10+ installed and on PATH.
REM  Output: dist\LeadEngine.exe  (one self-contained file)
REM ============================================================
cd /d "%~dp0\.."
echo Installing build dependencies...
python -m pip install --upgrade pip
python -m pip install -r gui\requirements.txt
python -m pip install pyinstaller
echo.
echo Running quick self-tests...
python leadgen\tests\test_engine.py || goto :err
python leadgen\tests\test_features.py || goto :err
echo.
echo Building the EXE (this takes a few minutes)...
pyinstaller --clean --noconfirm gui\LeadEngine.spec || goto :err
echo.
echo ============================================================
echo   DONE — your app is at:  dist\LeadEngine.exe
echo   Double-click it to launch the Lead Engine.
echo ============================================================
pause
exit /b 0

:err
echo.
echo BUILD FAILED — see the messages above.
pause
exit /b 1
