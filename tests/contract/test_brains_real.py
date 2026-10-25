"""Contrato dos cerebros com CHAVE REAL (opt-in). Nao roda na suite normal.

Como rodar:  crie um JSON fora do repositorio, ex. {"openai": "sk-...", "groq": "gsk_..."}, e
  JEFREY_CONTRACT_KEYS=C:/caminho/chaves.json  pytest tests/contract -m contract -q
Nada aqui imprime chaves.
"""
import asyncio
import json
import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.contract

_KEYS_FILE = os.getenv("JEFREY_CONTRACT_KEYS", "")
pytest.importorskip("httpx")
if not (_KEYS_FILE and Path(_KEYS_FILE).is_file()):
    pytest.skip("defina JEFREY_CONTRACT_KEYS para rodar o contrato com chaves reais", allow_module_level=True)

KEYS: dict = json.loads(Path(_KEYS_FILE).read_text(encoding="utf-8"))


async def _ask(text="Responda apenas: ok") -> str:
    from src.jefrey.core.llm_provider import get_llm_client
    out = []
    async for ev in get_llm_client().stream_events([{"role": "user", "content": text}]):
        if isinstance(ev, str):
            out.append(ev)
    return "".join(out)


@pytest.fixture(autouse=True)
def casa_limpa(tmp_path, monkeypatch):
    monkeypatch.setenv("JEFREY_CONFIG_DIR", str(tmp_path))


@pytest.mark.parametrize("brain_id", sorted(KEYS))
def test_cada_cerebro_conectado_responde(brain_id):
    from src.jefrey.core import brains
    asyncio.run(brains.connect(brain_id, KEYS[brain_id]))
    assert brains.state()["brains"][0]["id"] == brain_id
    assert asyncio.run(_ask()).strip()


def test_reserva_assume_com_chave_real():
    """Principal com chave invalida + reserva valida => a resposta vem da reserva."""
    from src.jefrey.core import brains
    ids = sorted(KEYS)
    if len(ids) < 1:
        pytest.skip("precisa de ao menos uma chave valida")
    good = ids[0]
    bad = "groq" if good != "groq" else "openai"
    brains._attach_for_test = getattr(brains, "_attach_for_test", None)
    asyncio.run(brains.connect(good, KEYS[good]))
    try:
        asyncio.run(brains.connect(bad, "chave-invalida-" + "x" * 24, primary=True))
    except Exception:
        pytest.skip("o cadastro recusou a chave invalida antes do teste (validacao previa): reserva coberta por tests/test_brains_failover_http.py")
    assert asyncio.run(_ask()).strip()
