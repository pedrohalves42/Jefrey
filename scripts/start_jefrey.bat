@echo off
REM Jefrey 1 programa 7 pecas — P0 leigo — Axiom #1 FAIL-CLOSED
cd /d %~dp0\..
echo [Jefrey] Subindo 7/7 containers...
docker compose up -d --wait
if errorlevel 1 (
  echo [ERRO] docker compose falhou — veja docker compose ps
  pause
  exit /b 1
)
timeout /t 5 >nul
echo [Jefrey] Health check...
powershell -c "try{$r=Invoke-WebRequest -UseBasicParsing http://localhost:8000/health -TimeoutSec 5; Write-Host $r.Content}catch{Write-Host $_.Exception.Message}"
start http://localhost:8000/
echo [Jefrey] http://localhost:8000/  Grafana http://localhost:3000 admin/%GRAFANA_PASSWORD%
pause
