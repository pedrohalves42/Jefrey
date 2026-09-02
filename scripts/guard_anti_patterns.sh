#!/usr/bin/env bash
# guard_anti_patterns.sh — FASE 0 — 6 greps exatos (PLANO_MESTRE v1.1)
# Axiom #6 FAIL-CLOSED + CIPHER-033/026/031 + Security Eng ch.4/8 + DDIA + MCP Spec
# Falha (exit 1) se qualquer anti-pattern for encontrado. Copiado no checklist §0.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
FAIL=0
pass() { echo "  PASS $1"; }
fail() { echo "  FAIL $1"; FAIL=1; }

echo "=== guard_anti_patterns.sh — 6 greps exatos (C1a/C1b/C2/A1/A4/M5/A6) ==="

# GREP-1 C1a HMAC fail-closed: dev-auto-generated-key / auto-key fallback
echo "[GREP-1] C1a HMAC auto-key (dev-auto-generated-key) — deve ser 0"
if grep -rn "dev-auto-generated-key" src/jefrey/eventbus/ --exclude-dir=__pycache__ 2>/dev/null | grep -v ".pyc" ; then
  fail "GREP-1 C1a auto-key encontrado (signing.py:32 deve dar RuntimeError em prod, nao warn)"
else
  pass "GREP-1 C1a 0 hits"
fi

# GREP-2 C1b rate_limit fail-open: return "allow" sem Redis
echo "[GREP-2] C1b rate_limit return \"allow\" fail-open — deve ser 0"
if grep -rn 'return "allow"' src/jefrey/core/rate_limit.py 2>/dev/null ; then
  fail "GREP-2 C1b return \"allow\" em rate_limit.py (deve raise/d deny se Redis ausente)"
else
  pass "GREP-2 C1b 0 hits"
fi
# tambem detectar fallback allow generico em core/
# (fallback allow em comment/logger nao e fail-open real — C1b ja coberto acima)

# GREP-3 silent except: except.*: pass
echo "[GREP-3] except.*: pass (CIPHER-021) — deve ser 0"
if grep -rn -E "except.*:[[:space:]]*pass" src/ 2>/dev/null ; then
  fail "GREP-3 except: pass encontrado (silencia fail-closed)"
else
  pass "GREP-3 0 hits"
fi

# GREP-4 str(dict) nao deterministico — C2 (kid+user_id+timestamp no HMAC)
echo "[GREP-4] str(dict)/str(canonical) nao deterministico — deve ser 0 (exceto json.dumps default=str com redact_pii)"
# audit.py:83 json.dumps(..., default=str) é OK se tiver redact_pii antes — filtra esse caso
HITS4="$(grep -rn -E "str\(.*dict|str\(.*canonical|str\(.*payload" src/jefrey/eventbus/ src/jefrey/core/audit.py 2>/dev/null | grep -v "default=str" | grep -v "# OK:" || true)"
if [ -n "$HITS4" ]; then
  echo "$HITS4"
  fail "GREP-4 str(dict) encontrado (usar json.dumps(..., sort_keys=True, separators=(',',':')) + kid.user_id.timestamp)"
else
  pass "GREP-4 0 hits"
fi
# checagem extra: se audit.py usa default=str sem redact_pii, falha
if grep -q "default=str" src/jefrey/core/audit.py 2>/dev/null; then
  if ! grep -q "redact_pii\|redact" src/jefrey/core/audit.py 2>/dev/null; then
    echo "  NOTE audit.py usa default=str sem redact_pii — C2/M2 pendente (warn, nao fail ainda)"
  fi
fi

# GREP-5 b64encode proibido — A1 JWKS RFC7517 (usar urlsafe_b64encode sem padding + alg RS256 + kid)
echo "[GREP-5] b64encode sem urlsafe_b64encode (A1 RFC7517) — deve ser 0"
HITS5="$(grep -rn "b64encode" src/jefrey/oauth2/ --exclude-dir=__pycache__ 2>/dev/null | grep -v "urlsafe_b64encode" || true)"
if [ -n "$HITS5" ]; then
  echo "$HITS5"
  fail "GREP-5 b64encode nao-urlsafe em oauth2/ (usar urlsafe_b64encode(...).decode().rstrip('=') + alg:RS256 kid)"
else
  pass "GREP-5 0 hits"
fi

# GREP-6 overwrite/valid/In-memory/fallback/creds — A4/M5/A6
echo "[GREP-6] overwrite=True / valid_ / In-memory / :-jefrey / .:/app sem :ro — deve ser 0"
HITS6A="$(grep -rn "overwrite=True" src/ --exclude-dir=__pycache__ 2>/dev/null || true)"
# A2/A6: valid_ stub so e permitido SE gateado com JEFREY_ENV==prod (CIPHER-021 fail-closed)
if grep -q "valid_" src/jefrey/oauth2/token_refresh.py 2>/dev/null; then
  if grep -q 'JEFREY_ENV.*prod' src/jefrey/oauth2/token_refresh.py 2>/dev/null; then
    HITS6B=""
  else
    HITS6B="$(grep -rn "valid_" src/jefrey/oauth2/token_refresh.py --exclude-dir=__pycache__ 2>/dev/null | grep -E 'startswith.*valid_|Simulate.*valid' || true)"
  fi
else
  HITS6B=""
fi
HITS6C="$(grep -rn "In-memory" src/ --exclude-dir=__pycache__ --exclude-dir=.git 2>/dev/null | grep -v "Fallback in-memory" | grep -v "#.*In-memory" || true)"
HITS6D="$(grep -rn -E '\$\{JEFREY_[A-Z_]*PASSWORD:-[^}]*\}' docker-compose.yml 2>/dev/null || true)"
HITS6E="$(grep -rn ".:/app" docker-compose.yml 2>/dev/null | grep -v ":ro" || true)"
HITS6=""
[ -n "$HITS6A" ] && HITS6="${HITS6}${HITS6A}\n"
[ -n "$HITS6B" ] && HITS6="${HITS6}${HITS6B}\n"
[ -n "$HITS6C" ] && HITS6="${HITS6}${HITS6C}\n"
[ -n "$HITS6D" ] && HITS6="${HITS6}${HITS6D}\n"
[ -n "$HITS6E" ] && HITS6="${HITS6}${HITS6E}\n"
if [ -n "$HITS6" ]; then
  printf "%b" "$HITS6"
  fail "GREP-6 hits acima (A4 overwrite=False, stub valid_ NotImplementedError em prod, In-memory->Redis, :-jefrey->\${VAR:?required}, .:/app:ro)"
else
  pass "GREP-6 0 hits"
fi

# Extra: default user/system least privilege
echo "[EXTRA] default user_role=user / user_id=system — deve ser guest/None (Axiom #5)"
if grep -rn '"user"' src/jefrey/core/policy.py 2>/dev/null | grep -q "user_role"; then
  echo "  NOTE policy.py ainda tem \"user\" default (A3) — deve ser guest"
fi

echo ""
if [ "$FAIL" -eq 0 ]; then
  echo "guard_anti_patterns: ALL 6 GREPS PASS (0 hits)"
  exit 0
else
  echo "guard_anti_patterns: FAIL — corrija os hits acima antes de commit (FASE 0)"
  echo "Reproducao C1a: JEFREY_ENV=prod JEFREY_EVENTBUS__HMAC_KEY= python -c \"from src.jefrey.eventbus.signing import _get_hmac_key; _get_hmac_key()\" -> RuntimeError"
  exit 1
fi
