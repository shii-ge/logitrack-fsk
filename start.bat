@echo off
setlocal enabledelayedexpansion

REM ============================================================
REM  iniciar_tudo.bat
REM  Ajuste as variaveis abaixo para o seu projeto antes de usar.
REM ============================================================

REM Caminho da pasta do projeto: assume que este .bat esta na mesma
REM pasta que app.py e monitor_serial.py (nao precisa editar isto).
set PROJETO_DIR=%~dp0
REM Remove a barra final, se houver, so por consistencia
if "%PROJETO_DIR:~-1%"=="\" set PROJETO_DIR=%PROJETO_DIR:~0,-1%

REM Sem venv: usa o python do sistema (precisa estar no PATH).
set PYTHON_EXE=python

REM Caminho do monitor_serial.py dentro da subpasta scripts
set MONITOR_SCRIPT=%PROJETO_DIR%\scripts\monitor_serial.py

REM Porta serial que o monitor vai usar (deve bater com PORTA_SERIAL no .py)
set PORTA_SERIAL=COM3

echo ============================================
echo   Verificando caminhos...
echo ============================================
echo Pasta do projeto: %PROJETO_DIR%
echo Script monitor:   %MONITOR_SCRIPT%
echo.

where %PYTHON_EXE% >nul 2>nul
if errorlevel 1 (
    echo [ERRO] "%PYTHON_EXE%" nao foi encontrado no PATH.
    echo Abra um cmd e digite "python --version" para testar.
    pause
    goto :fim
)

if not exist "%PROJETO_DIR%\app.py" (
    echo [ERRO] Nao encontrei: %PROJETO_DIR%\app.py
    echo Confira se este .bat esta na mesma pasta do app.py.
    pause
    goto :fim
)

if not exist "%MONITOR_SCRIPT%" (
    echo [ERRO] Nao encontrei: %MONITOR_SCRIPT%
    echo Confira o nome da subpasta ^(scripts^) e do arquivo monitor_serial.py.
    pause
    goto :fim
)

echo Todos os caminhos foram encontrados.
echo.

echo ============================================
echo   Verificando porta serial %PORTA_SERIAL%...
echo ============================================

REM Usa o PowerShell para listar as portas COM disponiveis no Windows
REM e verifica se a porta configurada esta entre elas.
set PORTA_ENCONTRADA=0
for /f "delims=" %%P in ('powershell -NoProfile -Command "[System.IO.Ports.SerialPort]::GetPortNames()"') do (
    if /i "%%P"=="%PORTA_SERIAL%" set PORTA_ENCONTRADA=1
)

if "%PORTA_ENCONTRADA%"=="0" (
    echo.
    echo [AVISO] A porta %PORTA_SERIAL% nao foi encontrada no sistema.
    echo Portas disponiveis no momento:
    powershell -NoProfile -Command "[System.IO.Ports.SerialPort]::GetPortNames()"
    echo.
    echo Verifique se o dispositivo esta conectado e se a porta em
    echo monitor_serial.py corresponde a uma das portas acima.
    echo.
    choice /M "Deseja continuar mesmo assim"
    if errorlevel 2 (
        echo Cancelado pelo usuario.
        goto :fim
    )
) else (
    echo Porta %PORTA_SERIAL% encontrada. Prosseguindo...
)

echo.
echo ============================================
echo   Iniciando processos...
echo ============================================

cd /d "%PROJETO_DIR%"

start "Monitor Serial" cmd /k ""%PYTHON_EXE%" "%MONITOR_SCRIPT%""
timeout /t 2 /nobreak >nul
start "Flask App" cmd /k ""%PYTHON_EXE%" app.py"

echo.
echo Ambos os processos foram iniciados em janelas separadas.
echo Feche as janelas individualmente para encerrar cada um.

:fim
endlocal
