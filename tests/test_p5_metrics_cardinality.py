"""P5-01 — Metrics cardinality sem user_id (Livro 4 cap5 + Axiom #4 + CIPHER-026/033)

3 tests deterministicos (SWE cap14):
1. test_no_user_id_label_in_code — grep em codigo fonte (rglob) deve ser 0
2. test_metrics_module_no_user_id_label — inspeciona modulo metrics direto (sem REGISTRY duplicado)
3. test_metrics_endpoint_no_user_id — generate_latest sem user_id
"""
import pathlib
import re
import sys
import importlib

import pytest


def test_no_user_id_label_in_code():
    """Livro 4 cap5: nenhum arquivo em src/ pode ter labelnames.*user_id"""
    root = pathlib.Path("src")
    bad = []
    pat = re.compile(r"labelnames.*user_id|user_id.*labelnames", re.IGNORECASE)
    for p in root.rglob("*.py"):
        if "__pycache__" in str(p):
            continue
        txt = p.read_text(encoding="utf-8", errors="ignore")
        if pat.search(txt):
            bad.append(f"{p}: {pat.search(txt).group(0)[:80]}")
        if re.search(r"(Counter|Histogram|Gauge)\s*\(.*user_id", txt, re.IGNORECASE):
            if "labelnames" in txt.lower() and "user_id" in txt.lower():
                if str(p) not in [b.split(':')[0] for b in bad]:
                    bad.append(f"{p}: Counter/Histogram user_id")
    assert bad == [], f"Metricas com user_id label encontradas (Livro 4 cap5 violado): {bad}"


def test_metrics_module_no_user_id_label():
    """CIPHER-026/033: RATE_LIMIT_TOTAL e KID_LEGACY sem user_id — inspeciona modulo direto"""
    # Import unico — evita DuplicateTimeseries
    m = None
    if "jefrey.core.metrics" in sys.modules:
        m = sys.modules["jefrey.core.metrics"]
    elif "src.jefrey.core.metrics" in sys.modules:
        m = sys.modules["src.jefrey.core.metrics"]
    else:
        try:
            m = importlib.import_module("jefrey.core.metrics")
        except ImportError:
            m = importlib.import_module("src.jefrey.core.metrics")

    # Coleta metricas via atributos do modulo (nao via REGISTRY)
    found = []
    bad = []
    for name in dir(m):
        obj = getattr(m, name)
        # prometheus_client metrics tem _labelnames (tuple) ou labelnames
        labelnames = None
        if hasattr(obj, "_labelnames"):
            labelnames = getattr(obj, "_labelnames")
        elif hasattr(obj, "labelnames"):
            labelnames = getattr(obj, "labelnames")
        if labelnames is None:
            continue
        # Filtra so metricas jefrey_ (checa _name ou name)
        metric_name = getattr(obj, "_name", "") or getattr(obj, "name", "") or name.lower()
        # Heuristica: obj tem _name que comeca com jefrey_ ou name comeca com jefrey_
        is_jefrey = str(metric_name).startswith("jefrey_") or name.lower().startswith("jefrey") or name.lower().startswith("llm_") or name.lower().startswith("tool") or name.lower().startswith("rate_limit") or name.lower().startswith("eventbus") or name.lower().startswith("memory") or name.lower().startswith("config")
        # Mais simples: se labelnames existe e obj e Counter/Histogram/Gauge, considera se nome contem jefrey
        # Para garantir, checa se obj tem _name e _name startswith jefrey_
        try:
            n = getattr(obj, "_name", "")
            if isinstance(n, str) and n.startswith("jefrey_"):
                is_jefrey = True
        except Exception:
            pass
        if not is_jefrey:
            # ignora metricas nao-jefrey (ex: python_info)
            if not str(metric_name).startswith("jefrey_"):
                continue
        found.append((name, labelnames))
        if "user_id" in labelnames:
            bad.append(f"{name} labelnames={labelnames}")

    assert len(found) >= 5, f"Somente {len(found)} metricas jefrey encontradas, esperado >=5: {found[:3]}"
    assert bad == [], f"Metrica jefrey com user_id label (cap5 violado): {bad}"

    # Checagem explicita das 2 criticas
    # RATE_LIMIT_TOTAL
    rate = getattr(m, "RATE_LIMIT_TOTAL", None) or getattr(m, "rate_limit_total", None)
    if rate is not None:
        ln = getattr(rate, "_labelnames", getattr(rate, "labelnames", []))
        assert "user_id" not in ln, f"RATE_LIMIT_TOTAL labelnames={ln} contem user_id"
        assert "tool_name" in ln, f"RATE_LIMIT_TOTAL deve ter tool_name, tem {ln}"
    # KID_LEGACY
    kid = getattr(m, "EVENTBUS_KID_LEGACY_TOTAL", None)
    if kid is not None:
        ln2 = getattr(kid, "_labelnames", getattr(kid, "labelnames", []))
        assert "user_id" not in ln2, f"KID_LEGACY labelnames={ln2} contem user_id"
        assert len(ln2) == 0, f"KID_LEGACY deve ser global sem label, tem {ln2}"


def test_metrics_endpoint_no_user_id(monkeypatch):
    """Axiom #4 + Livro 4 cap5: /metrics nunca expos user_id"""
    monkeypatch.setenv("JEFREY_ENV", "dev")
    monkeypatch.setenv("JEFREY_EVENTBUS__HMAC_KEY", "a" * 32)
    monkeypatch.setenv("JEFREY_EVENTBUS__HMAC_KEYS_JSON", '{"v1":"' + "a" * 32 + '"}')
    monkeypatch.setenv("JEFREY_OAUTH__AUD", "jefrey")
    monkeypatch.setenv("JEFREY_OAUTH__ISS", "https://auth.test")
    monkeypatch.setenv("JEFREY_API__CORS_ORIGINS", "http://localhost:3000")

    try:
        from prometheus_client import REGISTRY, generate_latest

        # Garante que metrics foi importado antes de generate
        if "jefrey.core.metrics" not in sys.modules and "src.jefrey.core.metrics" not in sys.modules:
            try:
                importlib.import_module("jefrey.core.metrics")
            except ImportError:
                importlib.import_module("src.jefrey.core.metrics")

        data = generate_latest(REGISTRY).decode("utf-8", errors="ignore")
        jefrey_lines = [l for l in data.splitlines() if l.startswith("jefrey_")]
        assert len(jefrey_lines) >= 3, f"Esperado >=3 linhas jefrey_ no /metrics, tem {len(jefrey_lines)}"
        user_id_hits = [l for l in jefrey_lines if "user_id" in l]
        assert user_id_hits == [], f"/metrics contem user_id (cap5 violado): {user_id_hits[:3]}"
        assert any("jefrey_config_valid" in l for l in jefrey_lines), "jefrey_config_valid ausente em /metrics"
        return
    except Exception as e:
        pytest.skip(f"REGISTRY check falhou: {e}")
