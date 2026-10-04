@echo off
REM Iniciar o Jefrey (duplo clique).
REM   start_jefrey.bat            -> modo leve: so o essencial (4 containers, usa menos memoria)
REM   start_jefrey.bat completo   -> tambem monitoramento (Grafana/Prometheus), n8n e MCP
REM Defina JEFREY_NO_BROWSER=1 para nao abrir o navegador (util em automacao).
setlocal EnableExtensions
cd /d "%~dp0"
title Jefrey

set PROFILE=
if /i "%~1"=="completo" set PROFILE=--profile full

echo.
echo === Iniciando o Jefrey ===

echo [1/4] Verificando o Docker...
docker --version >nul 2>&1
if errorlevel 1 goto nodocker
docker info >nul 2>&1
if not errorlevel 1 goto dockerok

echo O Docker Desktop esta fechado. Abrindo e esperando ele ficar pronto...
start "" "%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
set /a TRIES=0
:waitdocker
docker info >nul 2>&1
if not errorlevel 1 goto dockerok
set /a TRIES+=1
if %TRIES% GEQ 36 goto dockerfail
timeout /t 5 /nobreak >nul
goto waitdocker

:nodocker
echo Nao encontrei o Docker. Instale o Docker Desktop: https://www.docker.com/products/docker-desktop
pause
exit /b 1

:dockerfail
echo O Docker nao ficou pronto em 3 minutos. Abra o Docker Desktop manualmente e tente de novo.
pause
exit /b 1

:dockerok
echo [2/4] Subindo os servicos...
docker compose %PROFILE% up -d
if errorlevel 1 goto upfail

echo [3/4] Esperando o Jefrey ficar pronto (ate 3 minutos)...
powershell -NoProfile -Command "$ok=$false; for($i=0;$i -lt 36;$i++){ try { if((Invoke-WebRequest -UseBasicParsing -Uri http://localhost:8000/health -TimeoutSec 3).StatusCode -eq 200){$ok=$true;break} } catch {}; Start-Sleep -Seconds 5 }; if($ok){exit 0}else{exit 1}"
if errorlevel 1 goto notready

echo [4/4] Pronto.
if not defined JEFREY_NO_BROWSER start "" http://localhost:8000
echo.
echo O Jefrey esta em http://localhost:8000
echo Dica: no Edge/Chrome use "Instalar aplicativo" para abrir o Jefrey como um programa do Windows.
echo Para parar: stop_jefrey.bat
if not defined JEFREY_NO_BROWSER timeout /t 8 >nul
exit /b 0

:upfail
echo Falha ao subir os servicos. Rode: docker compose logs --tail 50
pause
exit /b 1

:notready
echo O Jefrey nao respondeu a tempo. Veja o diagnostico:
echo   python -m src.jefrey.cli doctor
pause
exit /b 1
