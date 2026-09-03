#!/usr/bin/env bash
set -e
echo "=== JEFREY v1.0.0 — 1 clique (Ordem B, 167/167) ==="
if [ ! -f .env ]; then
  echo "[.env nao encontrado] criando DEV..."
  python scripts/setup.py --dev --non-interactive --force
fi
echo "[1/3] docker compose up -d --wait ..."
docker compose up -d --wait
echo "[2/3] docker ps (7/7 healthy esperado) ..."
docker ps --format "table {{.Names}}\t{{.Status}}"
echo "[3/3] abrindo paginas (se xdg-open disponivel) ..."
command -v xdg-open >/dev/null && xdg-open http://localhost:8000/docs || echo "Abra http://localhost:8000/docs"
echo ""
echo "=== JEFREY rodando como 1 programa ==="
echo "API: http://localhost:8000/health  MCP: http://localhost:8001/health"
echo "Grafana: http://localhost:3000  Prometheus: http://localhost:9090  n8n: http://localhost:5678"
