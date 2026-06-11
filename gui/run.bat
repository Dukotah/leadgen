@echo off
cd /d "%~dp0"
echo Installing dependencies (first run only)...
python -m pip install --quiet -r requirements.txt
echo.
echo Starting Lead Engine...
start "" http://127.0.0.1:5000
python app.py
pause
