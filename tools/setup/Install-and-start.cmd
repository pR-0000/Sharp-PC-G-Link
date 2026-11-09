@echo off
setlocal
cd /d "%~dp0..\.."
if exist ".venv\Scripts\python.exe" goto dependencies
where py >nul 2>&1
if errorlevel 1 goto plainpython
py -3 -m venv .venv
if errorlevel 1 goto failed
goto dependencies
:plainpython
where python >nul 2>&1
if errorlevel 1 goto missingpython
python -m venv .venv
if errorlevel 1 goto failed
:dependencies
".venv\Scripts\python.exe" -c "import sys; assert sys.version_info >= (3, 10); import tkinter, serial" >nul 2>&1
if not errorlevel 1 goto launch
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -c "import sys; assert sys.version_info >= (3, 10); import tkinter, serial"
if errorlevel 1 goto failed
:launch
start "" ".venv\Scripts\pythonw.exe" "Sharp PC-G Link.pyw"
exit /b 0
:missingpython
echo Python 3.10 or newer with Tkinter is required.
echo Download: https://www.python.org/downloads/windows/
pause
exit /b 1
:failed
echo Setup failed. Check Python 3.10+, Tkinter and Internet access.
pause
exit /b 1
