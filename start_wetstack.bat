@echo off
rem WetStack-0 one-click launcher for Windows.
rem
rem   Double-click:  creates .venv if needed, checks the dependencies and installs or repairs them,
rem                  runs the digital-twin self-test after a fresh install (step P0.3), then starts
rem                  the lab workspace and opens it in your browser.
rem   From a prompt: start_wetstack.bat <command> runs python -m wetstack <command> in the venv,
rem                  for example  start_wetstack.bat gate G0   or   start_wetstack.bat questions
rem   Port:          set WETSTACK_PORT=8766 before running to use another port (default 8765).

setlocal EnableExtensions
cd /d "%~dp0"
title WetStack-0 lab

set "VENV=.venv"
set "VPY=.venv\Scripts\python.exe"
if not defined WETSTACK_PORT set "WETSTACK_PORT=8765"
set "FRESH="
set "RC=0"

rem Keep the window open at the end only when started by a double-click or a shortcut (cmd /c).
setlocal EnableDelayedExpansion
set "CL=!CMDCMDLINE!"
set "HOLD="
if /i not "!CL:/c =!"=="!CL!" set "HOLD=1"
endlocal & set "HOLD=%HOLD%"

echo.
echo  WetStack-0 lab launcher
echo  -----------------------

rem 1. Virtual environment: rebuild it if its Python is gone or too old, create it if missing.
if exist "%VPY%" (
  "%VPY%" -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
  if errorlevel 1 (
    echo The .venv folder is unusable: its Python is missing or older than 3.10. Rebuilding it.
    rmdir /s /q "%VENV%"
  )
)
if not exist "%VPY%" (
  call :make_venv
  if errorlevel 1 goto :failed
)

rem 2. Workspace already running from this folder? Just open it, and leave the venv it uses alone.
if not "%~1"=="" goto :deps
"%VPY%" tools\check_env.py --running %WETSTACK_PORT%
if errorlevel 2 (
  echo Close that program, or pick another port from a prompt:  set WETSTACK_PORT=8766  then run start_wetstack.bat
  goto :failed
)
if not errorlevel 1 (
  echo The workspace is already running. Opening it in your browser.
  start "" "http://127.0.0.1:%WETSTACK_PORT%/"
  goto :finish
)

:deps
rem 3. Dependencies: check, install or repair if anything is missing, then check again.
echo Checking dependencies...
"%VPY%" tools\check_env.py
if errorlevel 1 (
  call :install
  if errorlevel 1 goto :failed
  echo Checking again...
  "%VPY%" tools\check_env.py
  if errorlevel 1 goto :failed
)

rem 4. The workspace page is committed, but rebuild it if it has gone missing.
if not exist "web\wetstack_lab.html" (
  echo Building the workspace page...
  "%VPY%" tools\build.py
  if errorlevel 1 goto :failed
)
where git >nul 2>&1
if errorlevel 1 echo Note: git is not on PATH, so the workspace's Commit button won't work until Git for Windows is installed.

rem 5. Run a command if one was given, otherwise start the workspace.
if not "%~1"=="" goto :run_command

if defined FRESH (
  echo.
  echo Fresh install: running the digital-twin self-test, step P0.3. It takes about 30 s and must end PASSED.
  "%VPY%" -m wetstack selftest
  if errorlevel 1 (
    echo.
    echo The self-test did not pass. Paste the output above into Claude Code and ask the lab manager.
    goto :failed
  )
)
goto :serve

:run_command
"%VPY%" -m wetstack %*
set "RC=%ERRORLEVEL%"
goto :finish

:serve
echo.
echo Starting the lab workspace at http://127.0.0.1:%WETSTACK_PORT%/
echo Keep this window open while you work. Press Ctrl+C here to stop; every change is already saved.
echo.
"%VPY%" -m wetstack serve --port %WETSTACK_PORT% --open
set "RC=%ERRORLEVEL%"
goto :finish

:failed
echo.
echo Stopped. Read the message above, fix it, and run start_wetstack.bat again.
set "RC=1"

:finish
if defined HOLD (
  echo.
  pause
)
endlocal & exit /b %RC%

rem ---------------------------------------------------------------- subroutines

:make_venv
call :find_python
if errorlevel 1 exit /b 1
echo Creating the virtual environment in .venv with %BASEPY% ...
%BASEPY% -m venv "%VENV%"
if errorlevel 1 (
  echo Could not create .venv with %BASEPY%.
  exit /b 1
)
set "FRESH=1"
exit /b 0

:find_python
rem Prefer an installed 64-bit Python that numpy, scipy and OpenCV ship wheels for, found through
rem the registry (PEP 514) so nothing gets launched or auto-installed while looking. Then fall back
rem to py -3 and python. Probes read stdin from nul so no prompt can ever wait for an answer.
set "BASEPY="
for %%V in (3.12 3.13 3.11 3.14 3.10) do if not defined BASEPY call :python_from_registry %%V
if not defined BASEPY (
  py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" <nul >nul 2>&1 && set "BASEPY=py -3"
)
if not defined BASEPY (
  python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" <nul >nul 2>&1 && set "BASEPY=python"
)
if defined BASEPY exit /b 0
echo.
echo No Python 3.10 or newer was found. Install Python 3.12, then run this again:
echo     winget install -e --id Python.Python.3.12
echo or get it from https://www.python.org/downloads/ and tick "Add python.exe to PATH".
exit /b 1

:python_from_registry
for %%K in (HKCU HKLM) do if not defined BASEPY (
  for /f "skip=2 tokens=2,*" %%A in ('reg query "%%K\Software\Python\PythonCore\%~1\InstallPath" /v ExecutablePath 2^>nul') do (
    if exist "%%B" "%%B" -c "import sys" <nul >nul 2>&1 && set "BASEPY="%%B""
  )
)
exit /b 0

:install
echo.
echo Installing WetStack and its dependencies into .venv: numpy, scipy, scikit-learn, OpenCV,
echo matplotlib and pyserial. The first time downloads a few hundred MB and takes a few minutes.
"%VPY%" -m pip install --disable-pip-version-check --upgrade pip
if errorlevel 1 goto :install_failed
"%VPY%" -m pip install --disable-pip-version-check -e .
if errorlevel 1 goto :install_failed
set "FRESH=1"
exit /b 0

:install_failed
echo.
echo pip could not install everything. Check the internet connection and the error above.
echo If pip reports a failed build for numpy, scipy or opencv, your Python is newer than their
echo wheels: install Python 3.12, delete the .venv folder and run start_wetstack.bat again.
exit /b 1
