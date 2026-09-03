@echo off
chcp 65001 >nul
echo === JEFREY v1.0.0 — 1 clique (Ordem B, 167/167) ===
if not exist ".env" (
  echo [.env nao encontrado] criando DEV...
  python scripts/setup.py --dev --non-interactive --force
  if errorlevel 1 echo ERRO setup.py & pause & exit /b 1
)
echo [1/3] docker compose up -d --wait ...
docker compose up -d --wait
if errorlevel 1 echo ERRO compose up & pause & exit /b 1
echo [2/3] docker ps (7/7 healthy esperado) ...
docker ps --format "table {{.Names}}\t{{.Status}}"
echo [3/3] abrindo paginas ...
start http://localhost:8000/docs
start http://localhost:3000
start http://localhost:9090
start http://localhost:5678
echo.
echo === JEFREY rodando como 1 programa ===
echo API: http://localhost:8000/health  MCP: http://localhost:8001/health
echo Grafana: http://localhost:3000  Prometheus: http://localhost:9090  n8n: http://localhost:5678
echo Verifique: python scripts/verify_p6_data.py ^&^& python scripts/_validate_deep.py
pause
