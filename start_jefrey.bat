@echo off
REM start_jefrey.bat v2 — Jefrey 1 programa 7 pecas — F6-4 PWA One-Click (Axiom #7)
REM Uso: duplo clique. Sobe 7/7 jefrey_* + abre http://localhost:8000
setlocal
cd /d "%~dp0"
echo === Jefrey One-Click v2 ===
echo [1/4] Verificando docker...
docker --version >nul 2>&1 || (echo Docker nao encontrado. Instale Docker Desktop. & pause & exit /b 1)
echo [2/4] Subindo stack 7/7 (jefrey-api, postgres, redis, mcp, n8n, prometheus, grafana)...
docker compose up -d --build
if errorlevel 1 (echo Falha no docker compose up & pause & exit /b 1)
echo [3/4] Aguardando health 7/7 (timeout 90s)...
set COUNT=0
:loop
docker compose ps --format "table {{.Name}} {{.Status}}" | findstr /i "healthy" >nul
for /f %%c in ('docker compose ps --format "{{.Status}}" ^| findstr /c:"healthy" /c:"Up" ^| find /c /v ""') do set HC=%%c
echo  7/7 check tentativa %COUNT% — aguarde...
timeout /t 5 /nobreak >nul
set /a COUNT+=1
if %COUNT% GEQ 18 goto open
docker compose ps | findstr /i "healthy" | find /c "healthy" >nul 2>&1
if %COUNT% LSS 6 goto loop
:open
echo [4/4] Abrindo Jefrey...
start "" http://localhost:8000
echo.
echo Pronto! Se ver HUD preto + "Pronto" no header, esta vivo.
echo Dica: primeira visita mostra wizard 3 passos. Fale "oi" ou clique no microfone.
echo Logs: docker compose logs -f jefrey-api
echo Parar: docker compose down
pause
