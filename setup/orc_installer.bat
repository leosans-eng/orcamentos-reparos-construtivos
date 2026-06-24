@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0.."

call "%~dp0create_exe.bat"
if errorlevel 1 exit /b 1

for /f "delims=" %%V in ('".venv\Scripts\python.exe" setup\read_app_version.py') do set "APPVER=%%V"

set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if "%ISCC%"=="" (
    echo Inno Setup 6 nao encontrado. Instale em https://jrsoftware.org/isinfo.php
    echo O .exe esta em dist\ORC\ORC.exe
    exit /b 1
)

echo.
echo Gerando instalador...
"%ISCC%" /DMyAppVersion=%APPVER% setup\orc_installer.iss
if errorlevel 1 exit /b 1

echo.
echo Concluido:
echo   dist\ORC\ORC.exe
echo   setup\output\ORC_Instalador_%APPVER%.exe
echo.
echo Atualize version.json no GitHub com versao=%APPVER% e o link do instalador.
