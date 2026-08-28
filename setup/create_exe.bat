@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0.."
set "NOPAUSE=%~1"
set "EXITCODE=0"

set "PYTHON=.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
    echo Ambiente virtual nao encontrado.
    echo Crie com: python -m venv .venv
    echo Depois: .venv\Scripts\pip install -r requirements.txt
    set "EXITCODE=1"
    goto :fim
)

for /f "delims=" %%V in ('"%PYTHON%" setup\read_app_version.py') do set "APPVER=%%V"
echo Versao do app: %APPVER%

echo.
echo [1/3] Instalando dependencias de build...
"%PYTHON%" -m pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo ERRO ao instalar dependencias.
    set "EXITCODE=1"
    goto :fim
)

echo.
echo [2/3] Criptografando credenciais do Idebras...
"%PYTHON%" setup\empacotar_credenciais_idebras.py
if errorlevel 1 (
    echo ERRO ao empacotar credenciais do Idebras.
    set "EXITCODE=1"
    goto :fim
)

echo.
echo [3/3] Gerando executavel com PyInstaller...
"%PYTHON%" -m PyInstaller --noconfirm ORC.spec
if errorlevel 1 (
    echo ERRO ao gerar o executavel com PyInstaller.
    set "EXITCODE=1"
    goto :fim
)

if exist "dist\ORC\.env" del /f /q "dist\ORC\.env" >nul 2>&1

echo.
echo Concluido:
echo   dist\ORC\ORC.exe
echo.
if /i not "%NOPAUSE%"=="nopause" (
    echo Para gerar o instalador: setup\orc_installer.bat
)

:fim
if not "%EXITCODE%"=="0" (
    echo.
    echo create_exe.bat falhou.
)
if /i not "%NOPAUSE%"=="nopause" (
    echo.
    pause
)
exit /b %EXITCODE%
