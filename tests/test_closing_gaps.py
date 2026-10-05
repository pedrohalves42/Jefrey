"""Pendencias fechadas: padroes do instalador (Google e atualizacoes), controle do computador pelo laco real do agente."""
import asyncio
import json

import pytest

from src.jefrey.native import launcher as L


def run(c):
    return asyncio.run(c)


# ---------------- padroes que vem no instalador ----------------
def test_primeira_abertura_copia_os_padroes_sem_sobrescrever(tmp_path):
    src, cfg = tmp_path / "defaults", tmp_path / "home" / "config"
    src.mkdir()
    (src / "google_oauth.json").write_text(json.dumps({"installed": {"client_id": "a", "client_secret": "b"}}), encoding="utf-8")
    (src / "update_url.txt").write_text("https://atualizacoes.exemplo.com/manifest.json", encoding="utf-8")
    (src / "qualquer_outro.txt").write_text("nao e da lista", encoding="utf-8")
    assert sorted(L.seed_defaults(cfg, src)) == ["google_oauth.json", "update_url.txt"]
    assert not (cfg / "qualquer_outro.txt").exists()
    (cfg / "update_url.txt").write_text("https://meu.endereco/manifest.json", encoding="utf-8")  # a pessoa mudou
    (src / "update_url.txt").write_text("https://outro.exemplo.com/m.json", encoding="utf-8")
    assert L.seed_defaults(cfg, src) == []  # segunda abertura: nada e sobrescrito
    assert (cfg / "update_url.txt").read_text(encoding="utf-8") == "https://meu.endereco/manifest.json"


def test_padroes_ausentes_ou_enormes_nao_quebram(tmp_path):
    assert L.seed_defaults(tmp_path / "c", tmp_path / "nao_existe") == []
    src = tmp_path / "d"
    src.mkdir()
    (src / "google_oauth.json").write_text("x" * 30_000, encoding="utf-8")
    assert L.seed_defaults(tmp_path / "c", src) == []  # arquivo grande demais para ser credencial


def test_credencial_do_google_semeada_e_reconhecida(tmp_path, monkeypatch):
    from src.jefrey.core import google_oauth as G
    src, cfg = tmp_path / "defaults", tmp_path / "config"
    src.mkdir()
    (src / "google_oauth.json").write_text(json.dumps({"installed": {"client_id": "id-do-app", "client_secret": "segredo-do-app"}}), encoding="utf-8")
    L.seed_defaults(cfg, src)
    monkeypatch.setenv("JEFREY_CONFIG_DIR", str(cfg))
    monkeypatch.delenv("JEFREY_OAUTH__CLIENT_ID", raising=False)
    monkeypatch.delenv("JEFREY_OAUTH__CLIENT_SECRET", raising=False)
    assert G.credentials() == {"client_id": "id-do-app", "client_secret": "segredo-do-app"}


def test_endereco_das_atualizacoes_vem_do_arquivo_ou_do_ambiente(tmp_path, monkeypatch):
    from src.jefrey.core import updater as U
    monkeypatch.setenv("JEFREY_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("JEFREY_UPDATE_URL", raising=False)
    assert U.manifest_url() == ""
    (tmp_path / "update_url.txt").write_text("  https://atualizacoes.exemplo.com/manifest.json \n", encoding="utf-8")
    assert U.manifest_url() == "https://atualizacoes.exemplo.com/manifest.json"
    monkeypatch.setenv("JEFREY_UPDATE_URL", "https://env.exemplo.com/m.json")
    assert U.manifest_url() == "https://env.exemplo.com/m.json"  # o ambiente manda


def test_build_leva_a_pasta_de_padroes_e_ela_nao_vai_para_o_git():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    bat = (root / "packaging" / "build_exe.bat").read_text(encoding="utf-8")
    assert "packaging\\defaults" in bat and "google_oauth.json" in bat and "update_public_key.txt" in bat
    ign = (root / ".gitignore").read_text(encoding="utf-8")
    assert "packaging/defaults/*" in ign and "!packaging/defaults/README.md" in ign
    import subprocess
    for p in (root / "packaging" / "defaults").iterdir():  # tudo que for colocado aqui precisa ficar fora do Git
        if p.name != "README.md":
            assert subprocess.run(["git", "check-ignore", "-q", str(p)], cwd=root).returncode == 0, p.name


# ---------------- controle do computador pelo laco REAL do agente ----------------
def test_agente_abre_o_programa_pedido_pelo_laco_real(tmp_path, monkeypatch):
    """Um modelo (falso) pede open_app; o laco do agente executa a ferramenta de verdade (sem aprovacao: risco medio) e responde."""
    from src.jefrey.core.agent_loop import run_agent
    from src.jefrey.core.llm_tools import ToolCall
    from src.jefrey.core.tool_runtime import ToolRuntime
    from src.jefrey.skills import computer as C

    monkeypatch.setattr(C.sys, "platform", "win32")
    abertos = []
    monkeypatch.setattr(C, "_start", lambda t: abertos.append(t))
    menu = tmp_path / "Programs"
    menu.mkdir()
    (menu / "Microsoft Word.lnk").write_text("x")
    monkeypatch.setattr(C, "start_menu_dirs", lambda: [menu])
    C._cache.update(at=0.0, apps={})

    tools = {t.name: t for t in C.ComputerSkill().get_tools()}

    class Modelo:
        config = type("C", (), {"is_cloud": True})()
        passos = 0

        async def stream_events(self, messages, tools=None):
            self.passos += 1
            if self.passos == 1:
                yield ToolCall("c1", "open_app", {"name": "word"})
            else:
                resultado = [m for m in messages if m.get("role") == "tool"][-1]["content"]
                yield f"Pronto: {resultado}"

    rt = ToolRuntime(user_id="ana", thread_id="t", resolver=lambda n: tools.get(n))

    async def coleta():
        return [e async for e in run_agent(Modelo(), rt, [{"role": "system", "content": "s"}, {"role": "user", "content": "abre o word"}], tools, "abre o word")]
    ev = run(coleta())
    assert abertos and abertos[0].endswith("Microsoft Word.lnk")
    assert any(e["type"] == "tool_end" and e["tool"] == "open_app" and e["ok"] for e in ev)
    assert not any(e["type"] == "approval_required" for e in ev)
    assert "Abri Microsoft Word" in "".join(e["content"] for e in ev if e["type"] == "token")


def test_agente_pede_aprovacao_antes_de_acionar_rotina_da_alexa(tmp_path, monkeypatch):
    """alexa_routine e risco ALTO: nada e acionado sem a pessoa aprovar."""
    from src.jefrey.core import alexa as A
    from src.jefrey.core.tool_catalog import CATALOG
    chamadas = []

    async def falso(name, **k):
        chamadas.append(name)
        return "ok"
    monkeypatch.setattr(A, "routine", falso)
    assert CATALOG["alexa_routine"].needs_approval is True
    from src.jefrey.core.tool_runtime import ToolRuntime
    from src.jefrey.skills.alexa import AlexaSkill
    tools = {t.name: t for t in AlexaSkill().get_tools()}
    rt = ToolRuntime(user_id="ana", thread_id="t", resolver=lambda n: tools.get(n), approval_timeout=0.3)
    out = run(rt.run("alexa_routine", {"name": "boa noite"}))
    assert chamadas == [] and out.status == "approval_expired"  # sem aprovacao, a rotina nao e acionada


# ---------------- Google: colar as credenciais na tela ----------------
def test_credenciais_do_google_coladas_na_tela(tmp_path, monkeypatch):
    from src.jefrey.core import google_oauth as G
    monkeypatch.setenv("JEFREY_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("JEFREY_OAUTH__CLIENT_ID", raising=False)
    monkeypatch.delenv("JEFREY_OAUTH__CLIENT_SECRET", raising=False)
    assert G.credentials() is None
    for ruim in [("abc", "x" * 30), ("123-abc.apps.googleusercontent.com", "curta"), ("123-abc.apps.googleusercontent.com", "tem espaco " * 3)]:
        with pytest.raises(ValueError):
            G.save_credentials(*ruim)
    G.save_credentials(" 123-abc.apps.googleusercontent.com ", "GOCSPX-abcdefghijklmnop1234")
    assert G.credentials() == {"client_id": "123-abc.apps.googleusercontent.com", "client_secret": "GOCSPX-abcdefghijklmnop1234"}


def test_extensao_do_whatsapp_ganha_pasta_facil_em_documentos(tmp_path, monkeypatch):
    from src.jefrey.core import paths
    monkeypatch.setattr(paths.Path, "home", classmethod(lambda cls: tmp_path))
    (tmp_path / "Documents").mkdir()
    pasta = paths.public_extension_dir()
    assert pasta == tmp_path / "Documents" / "Jefrey" / "extensao-chrome"
    assert (pasta / "manifest.json").is_file() and (pasta / "background.js").is_file()
    assert paths.public_extension_dir() == pasta  # repetir nao quebra


def test_pagina_de_skills_mostra_o_risco_real_de_cada_ferramenta():
    from src.jefrey.api.skills_routes import describe_skills
    riscos = {t["name"]: t["risk"] for s in describe_skills() for t in s["tools"]}
    assert riscos["close_app"] == "high" and riscos["alexa_routine"] == "high" and riscos["open_folder"] == "low"
    assert "unknown" not in set(riscos.values()) and None not in set(riscos.values())


def test_script_que_embute_o_google_nao_mostra_os_valores(tmp_path, monkeypatch, capsys):
    import importlib.util
    spec = importlib.util.spec_from_file_location("seed_google", "scripts/seed_google_defaults.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    env = tmp_path / ".env"
    env.write_text('JEFREY_OAUTH__CLIENT_ID="123-abc.apps.googleusercontent.com"\nJEFREY_OAUTH__CLIENT_SECRET=GOCSPX-segredo-bem-comprido\nOUTRA=1\n', encoding="utf-8")
    assert m.from_env_file(env) == {"JEFREY_OAUTH__CLIENT_ID": "123-abc.apps.googleusercontent.com", "JEFREY_OAUTH__CLIENT_SECRET": "GOCSPX-segredo-bem-comprido"}
    monkeypatch.delenv("JEFREY_OAUTH__CLIENT_ID", raising=False)
    monkeypatch.delenv("JEFREY_OAUTH__CLIENT_SECRET", raising=False)
    monkeypatch.setattr(m, "ROOT", tmp_path)
    monkeypatch.setattr(m.sys, "argv", ["x"])
    assert m.main() == 0
    out = capsys.readouterr().out
    assert "GOCSPX" not in out and "123-abc" not in out
    assert json.loads((tmp_path / "packaging" / "defaults" / "google_oauth.json").read_text(encoding="utf-8"))["installed"]["client_id"].startswith("123-abc")


def test_google_do_instalador_respeita_os_enderecos_ja_registrados(tmp_path, monkeypatch):
    from src.jefrey.core import google_oauth as G
    monkeypatch.setenv("JEFREY_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("JEFREY_OAUTH__REDIRECT_URIS", raising=False)
    assert G.redirect_uri("http://localhost:8000") == "http://localhost:8000/connections/google/callback"  # padrao (cliente Computador)
    (tmp_path / "google_oauth.json").write_text(json.dumps({"installed": {"client_id": "1-a.apps.googleusercontent.com", "client_secret": "x" * 20,
                                                                           "redirect_uris": ["http://localhost:8000/auth/google/callback"]}}), encoding="utf-8")
    assert G.redirect_uri("http://localhost:8000") == "http://localhost:8000/auth/google/callback"  # o que o dono registrou
    assert G.redirect_uri("http://localhost:8001") == "http://localhost:8001/connections/google/callback"  # outra porta: nao ha o que registrar


def test_status_do_google_mostra_o_endereco_de_retorno(tmp_path, monkeypatch):
    from src.jefrey.api import google_connect as GC
    from src.jefrey.core import google_oauth as G
    monkeypatch.setenv("JEFREY_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("JEFREY_OAUTH__REDIRECT_URIS", raising=False)
    monkeypatch.setattr(GC, "_user", lambda r: "ana")
    monkeypatch.setattr(G, "status", lambda uid: {"configured": True, "connected": False})
    req = type("R", (), {"base_url": "http://localhost:8000/"})()
    out = run(GC.google_status(req))
    assert out["redirect_uri"] == "http://localhost:8000/connections/google/callback"


def test_chroma_continua_embutido_sem_servidor_nem_codigo_remoto():
    """As falhas conhecidas do chromadb (pip-audit, 2026-10) estao no modo SERVIDOR e em trust_remote_code: o Jefrey nao usa nenhum dos dois."""
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "src" / "jefrey"
    for p in root.rglob("*.py"):
        if "static" in p.parts:
            continue
        txt = p.read_text(encoding="utf-8", errors="ignore")
        assert "chromadb.HttpClient" not in txt and "trust_remote_code" not in txt, p.name


# ---------------- outra copia do Jefrey (Docker/antiga) ocupando a porta 8000 ----------------
def _resp(code, payload):
    import httpx
    return httpx.Response(code, json=payload, request=httpx.Request("GET", "http://x"))


def test_copia_docker_na_8000_nao_impede_a_instalada_de_abrir(monkeypatch):
    """Antes: o .exe dizia "ja esta aberto" e abria o Jefrey do Docker (versao velha, sem Google/skills novos)."""
    import httpx
    saude = {"status": "healthy", "version": "0.9.0", "security_components": {}}
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _resp(200, saude))  # sem "mode": e um servidor, nao a copia do Windows
    assert L.jefrey_running(8000) is True  # algo responde
    assert L.native_running(8000) is False  # mas nao e a copia nativa


def test_copia_nativa_da_mesma_versao_conta_como_ja_aberta(monkeypatch):
    import httpx
    from src.jefrey import __version__
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _resp(200, {"status": "healthy", "version": __version__, "mode": "native", "security_components": {}}))
    assert L.native_running(8000) is True
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _resp(200, {"status": "healthy", "version": "0.0.1", "mode": "native", "security_components": {}}))
    assert L.native_running(8000) is False  # versao antiga aberta: nao reaproveitar


# ---------------- Google: diagnostico em frases simples ----------------
def _cfg(monkeypatch, tmp_path, uris=None):
    from src.jefrey.core import google_oauth as G
    monkeypatch.setenv("JEFREY_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("JEFREY_OAUTH__REDIRECT_URIS", raising=False)
    inner = {"client_id": "1-a.apps.googleusercontent.com", "client_secret": "x" * 20}
    if uris:
        inner["redirect_uris"] = uris
    (tmp_path / "google_oauth.json").write_text(json.dumps({"installed": inner}), encoding="utf-8")
    return G


def test_diagnostico_cliente_desktop_aceita_qualquer_porta(tmp_path, monkeypatch):
    G = _cfg(monkeypatch, tmp_path)
    d = G.diagnose("http://localhost:8001")
    assert d["client_type"] == "desktop" and d["ok"] is True and d["redirect_uri"].startswith("http://localhost:8001/")


def test_diagnostico_cliente_web_exige_endereco_registrado(tmp_path, monkeypatch):
    G = _cfg(monkeypatch, tmp_path, ["http://localhost:8000/auth/google/callback"])
    d = G.diagnose("http://localhost:8000")
    assert d["client_type"] == "web" and d["ok"] is True and "/auth/google/callback" in d["redirect_uri"]
    d = G.diagnose("http://localhost:8001")  # outra porta: nao ha o que registrar
    assert d["ok"] is False and "8000" in d["advice"] and "Docker" in d["advice"]


def test_diagnostico_sem_credenciais(tmp_path, monkeypatch):
    from src.jefrey.core import google_oauth as G
    monkeypatch.setenv("JEFREY_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("JEFREY_OAUTH__CLIENT_ID", raising=False)
    monkeypatch.delenv("JEFREY_OAUTH__CLIENT_SECRET", raising=False)
    d = G.diagnose("http://localhost:8000")
    assert d["client_type"] == "unknown" and d["ok"] is False
