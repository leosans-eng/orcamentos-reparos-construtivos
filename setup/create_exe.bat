@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0.."

set "PYTHON=.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
    echo Ambiente virtual nao encontrado.
    echo Crie com: python -m venv .venv
    echo Depois: .venv\Scripts\pip install -r requirements.txt
    exit /b 1
)

for /f "delims=" %%V in ('"%PYTHON%" setup\read_app_version.py') do set "APPVER=%%V"
echo Versao do app: %APPVER%

echo.
echo [1/2] Instalando dependencias de build...
"%PYTHON%" -m pip install -r requirements.txt --quiet
if errorlevel 1 exit /b 1

echo.
echo [2/2] Gerando executavel com PyInstaller...
"%PYTHON%" -m PyInstaller --noconfirm ORC.spec
if errorlevel 1 exit /b 1

echo.
echo Concluido:
echo   dist\ORC\ORC.exe
echo.
echo Para gerar o instalador: setup\orc_installer.bat
