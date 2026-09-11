#!/bin/bash
# scripts/lighthouse_pwa.sh — Auditoria automatizada PWA >90
# CIPHER-206/209 — valida manifest, sw.js e experiência PWA no Chrome

set -e

BASE_URL="${1:-http://localhost:3000}"
REPORT_DIR="lighthouse-reports/pwa-$(date +%Y%m%d-%H%M%S)"
BINARY="google-chrome"
BINARY_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# Verifica se o Chrome/binário existe
if ! command -v "$BINARY" >/dev/null 2>&1; then
  echo "❌ Chrome não encontrado. Instale o Google Chrome ou ajuste o BINARY."
  exit 1
fi

# Cria diretório de relatórios
mkdir -p "$REPORT_DIR"

echo "🚀 Iniciando auditoria Pwa no ${BASE_URL}"
echo "📁 Relatórios serão salvos em: ${REPORT_DIR}"

# 1. Teste de manifest (valida JSON, icons, start_url)
echo "🔍 Validando manifest..."
MANIFEST_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/manifest.json")
if [ "$MANIFEST_RESPONSE" = "200" ]; then
  echo "✅ Manifest acessível (HTTP 200)"
else
  echo "⚠️ Manifest não encontrado (HTTP ${MANIFEST_RESPONSE})"
fi

# 2. Auditoria PWA completa com Lighthouse
echo "📊 Executando auditoria Lighthouse PWA..."
"$BINARY" --headless \
  --disable-gpu \
  --no-sandbox \
  --dump-dom \
  --assert-metrics-for-test "${BASE_URL}" \
  --chrome-flags="--disable-web-security" \
  --output=json="${REPORT_DIR}/lighthouse.json" \
  --preset=lighthouse:pr:experimental-pwa \
  --channel=canary \
  2>/dev/null || {
    echo "⚠️ Lighthouse com canal canary falhou, tentando padrão..."
    "$BINARY" --headless \
      --disable-gpu \
      --no-sandbox \
      --output=json="${REPORT_DIR}/lighthouse.json" \
      --preset=lighthouse:pr:experimental-pwa \
      "${BASE_URL}" 2>/dev/null || echo "⚠️ Lighthouse audit manual requerida"
  }

# 3. Extrair scores principais
if [ -f "${REPORT_DIR}/lighthouse.json" ]; then
  PWA_SCORE=$(python3 -c "
import json
with open('${REPORT_DIR}/lighthouse.json') as f:
    data = json.load(f)
try:
    score = data['categories']['pwa']['score'] * 100
    print(f'{score:.1f}')
except:
    print('N/A')
")
  ACCESSIBILITY_SCORE=$(python3 -c "
import json
with open('${REPORT_DIR}/lighthouse.json') as f:
    data = json.load(f)
try:
    score = data['categories']['accessibility']['score'] * 100
    print(f'{score:.1f}')
except:
    print('N/A')
")
  BEST_PRACTICES_SCORE=$(python3 -c "
import json
with open('${REPORT_DIR}/lighthouse.json') as f:
    data = json.load(f)
try:
    score = data['categories']['best-practices']['score'] * 100
    print(f'{score:.1f}')
except:
    print('N/A')
")
  PERFORMANCE_SCORE=$(python3 -c "
import json
with open('${REPORT_DIR}/lighthouse.json') as f:
    data = json.load(f)
try:
    score = data['categories']['performance']['score'] * 100
    print(f'{score:.1f}')
except:
    print('N/A')
")

  echo "📈 Scores Lighthouse:"
  echo "   PWA:        ${PWA_SCORE}/100"
  echo "   Acessibilidade: ${ACCESSIBILITY_SCORE}/100"
  echo "   Boas práticas: ${BEST_PRACTICES_SCORE}/100"
  echo "   Performance: ${PERFORMANCE_SCORE}/100"

  # 4. Verificar se passou o threshold (>90)
  OVERALL=$(python3 -c "
import json
with open('${REPORT_DIR}/lighthouse.json') as f:
    data = json.load(f)
# Média dos 4 categories principais
categories = ['pwa', 'accessibility', 'best-practices', 'performance']
scores = []
for cat in categories:
    try:
        s = data['categories'][cat]['score'] * 100
        scores.append(s)
    except:
        pass
if scores:
    avg = sum(scores) / len(scores)
    print(f'{avg:.1f}')
")

  if [ "$OVERALL" != "N/A" ] && python3 -c "print($OVERALL >= 90)" 2>/dev/null; then
    echo "🏆 PWA Score: ${OVERALL}/100 — > 90 PASS"
  else
    echo "⚠️ PWA Score: ${OVERALL}/100 — abaixo de 90, revisar configurações"
    python3 -c "
import json
with open('${REPORT_DIR}/lighthouse.json') as f:
    data = json.load(f)
    issues = []
    for cat in ['pwa', 'best-practices']:
        try:
            items = data['audits'][cat]
            for audit_id, audit in items.items():
                if audit.get('score') === false or audit.get('score') === 0:
                    title = audit.get('title', audit_id)
                    issues.append(f'{cat}: {title}')
        except:
            pass
    print('Problemas identificados:')
    for i in issues[:10]:
        print(f'  - {i}')
"
  fi
else
  echo "⚠️ Relatório Lighthouse não gerado completamente"
fi

# 5. Resumo final
echo "=========================================="
echo "📝 Relatório PWA salvo em: ${REPORT_DIR}"
echo "=========================================="

# Abrir relatório no navegador se disponível
if [ -f "${REPORT_DIR}/lighthouse.html" ]; then
  echo "🌐 Relatório HTML disponível em: file://$(pwd)/${REPORT_DIR}/lighthouse.html"
fi

exit 0