"""jefrey doctor: cada problema tem um status e uma correcao; nada depende da maquina real."""
from pathlib import Path

import pytest

from src.jefrey.core.doctor import FAIL, OK, WARN, Check, Probes, run_checks, summarize

GOOD_STATUS = {k: {"status": "ok"} for k in ("api", "postgres", "redis", "ollama", "mcp", "stt", "tts")}
TAGS = {"models": [{"name": "qwen3:1.7b"}, {"name": "embeddinggemma:latest"}]}


def probes(tmp_path, *, health=200, status=GOOD_STATUS, tags=TAGS, ram=(16.0, 8.0), disk=50.0,
           chat=("ollama", "qwen3:1.7b"), emb="embeddinggemma", env_text="JEFREY_API__SECRET_KEY=" + "a" * 40, py=(3, 12), env=None):
    (tmp_path / ".env").write_text(env_text, encoding="utf-8") if env_text is not None else None

    def get(url):
        if url.endswith("/health"):
            return health, {"status": "ok"}
        if url.endswith("/api/status"):
            return (200, status) if status is not None else (500, None)
        if url.endswith("/api/tags"):
            return (200, tags) if tags is not None else (0, None)
        return 404, None

    return Probes(base_url="http://x", ollama_url="http://o", project_dir=tmp_path, env=env or {}, python_version=py,
                  http_get=get, memory_gb=lambda: ram, disk_free_gb=lambda p: disk, chat_model=lambda: chat, embed_model=lambda: emb)


def by_id(checks):
    return {c.id: c for c in checks}


def test_ambiente_saudavel_nao_tem_problemas(tmp_path):
    checks = run_checks(probes(tmp_path))
    assert all(c.status == OK for c in checks), [(c.id, c.detail) for c in checks if c.status != OK]
    assert summarize(checks) == (len(checks), 0, 0)


def test_servidor_fora_do_ar_tem_correcao(tmp_path):
    c = by_id(run_checks(probes(tmp_path, health=0)))["api"]
    assert c.status == FAIL and "docker compose up" in c.fix


def test_servico_essencial_e_opcional_caindo(tmp_path):
    st = {**GOOD_STATUS, "postgres": {"status": "down"}, "mcp": {"status": "down"}}
    c = by_id(run_checks(probes(tmp_path, status=st)))
    assert c["postgres"].status == FAIL and c["mcp"].status == WARN
    assert "mcp-server" in c["mcp"].fix  # nome do servico no compose


def test_modelo_de_conversa_ou_memoria_ausente(tmp_path):
    c = by_id(run_checks(probes(tmp_path, tags={"models": [{"name": "outro:1b"}]})))
    assert c["chat_model"].status == FAIL and "ollama pull qwen3:1.7b" in c["chat_model"].fix
    assert c["embed_model"].status == FAIL and "ollama pull embeddinggemma" in c["embed_model"].fix


def test_modelo_sem_tag_casa_com_qualquer_versao(tmp_path):
    c = by_id(run_checks(probes(tmp_path, chat=("ollama", "embeddinggemma"))))
    assert c["chat_model"].status == OK


def test_chat_na_nuvem_nao_exige_modelo_local(tmp_path):
    c = by_id(run_checks(probes(tmp_path, tags={"models": []}, chat=("anthropic", "claude-sonnet-4-5"))))
    assert c["chat_model"].status == OK and "nuvem" in c["chat_model"].detail


def test_ollama_inacessivel(tmp_path):
    c = by_id(run_checks(probes(tmp_path, tags=None)))
    assert c["models"].status == FAIL and "jefrey-ollama" in c["models"].fix


@pytest.mark.parametrize("ram,esperado", [((16, 0.5), FAIL), ((16, 1.8), WARN), ((16, 4.0), OK)])
def test_faixas_de_memoria(tmp_path, ram, esperado):
    assert by_id(run_checks(probes(tmp_path, ram=ram)))["ram"].status == esperado


@pytest.mark.parametrize("disk,esperado", [(0.4, FAIL), (3.0, WARN), (20.0, OK)])
def test_faixas_de_disco(tmp_path, disk, esperado):
    c = by_id(run_checks(probes(tmp_path, disk=disk)))["disk"]
    assert c.status == esperado
    if esperado == FAIL:
        assert "builder prune" in c.fix


def test_segredos(tmp_path):
    assert by_id(run_checks(probes(tmp_path, env_text=None)))["env"].status == FAIL
    assert by_id(run_checks(probes(tmp_path, env_text="JEFREY_API__SECRET_KEY=curta")))["secret"].status == FAIL
    assert by_id(run_checks(probes(tmp_path, env_text="JEFREY_API__SECRET_KEY=CHANGE_ME_" + "x" * 40)))["secret"].status == FAIL
    assert by_id(run_checks(probes(tmp_path)))["secret"].status == OK


def test_segredo_vem_do_ambiente_quando_nao_esta_no_arquivo(tmp_path):
    c = by_id(run_checks(probes(tmp_path, env_text="OUTRA=1", env={"JEFREY_API__SECRET_KEY": "b" * 40})))
    assert c["secret"].status == OK


def test_python_antigo(tmp_path):
    assert by_id(run_checks(probes(tmp_path, py=(3, 10))))["python"].status == FAIL
    assert by_id(run_checks(probes(tmp_path, py=(3, 11))))["python"].status == WARN


def test_whatsapp_so_e_verificado_quando_ligado(tmp_path):
    assert "whatsapp" not in by_id(run_checks(probes(tmp_path)))
    c = by_id(run_checks(probes(tmp_path, env={"JEFREY_WHATSAPP__ENABLED": "true", "JEFREY_WHATSAPP__VERIFY_TOKEN": "t"})))["whatsapp"]
    assert c.status == FAIL and "APP_SECRET" in c.detail and "ALLOWED" in c.detail
    full = {"JEFREY_WHATSAPP__ENABLED": "true", "JEFREY_WHATSAPP__VERIFY_TOKEN": "t", "JEFREY_WHATSAPP__APP_SECRET": "s",
            "JEFREY_WHATSAPP__ACCESS_TOKEN": "a", "JEFREY_WHATSAPP__PHONE_NUMBER_ID": "1", "JEFREY_WHATSAPP__ALLOWED": "5511999990000"}
    assert by_id(run_checks(probes(tmp_path, env=full)))["whatsapp"].status == OK


def test_todo_problema_ou_aviso_traz_uma_correcao(tmp_path):
    ruim = probes(tmp_path, health=0, status=None, tags=None, ram=(16, 0.3), disk=0.2, env_text=None, py=(3, 9))
    for c in run_checks(ruim):
        if c.status != OK:
            assert c.fix, f"{c.id} sem correcao sugerida"


def test_summarize():
    cs = [Check("a", "A", OK, ""), Check("b", "B", WARN, ""), Check("c", "C", FAIL, ""), Check("d", "D", OK, "")]
    assert summarize(cs) == (2, 1, 1)
