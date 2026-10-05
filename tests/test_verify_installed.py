import importlib.util
from pathlib import Path

import httpx

_spec = importlib.util.spec_from_file_location("verify_installed", Path(__file__).resolve().parents[1] / "scripts" / "verify_installed.py")
V = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(V)


def _servidor(falha: set[str] = frozenset(), skills_riscos=("low", "high")):
    def handler(req: httpx.Request) -> httpx.Response:
        p = req.url.path
        if "text/html" in req.headers.get("accept", ""):  # navegador: o servidor devolve a pagina da interface
            return httpx.Response(200, text="<html></html>", headers={"content-type": "text/html"})
        if p in falha:
            return httpx.Response(500, json={"detail": "x"})
        if p == "/auth/dev-token":
            return httpx.Response(200, json={"access_token": "t"})
        if p == "/skills":
            return httpx.Response(200, json={"skills": [{"name": "a", "tools": [{"name": "t", "risk": r} for r in skills_riscos]}]})
        if p == "/wa/open-extension-folder":
            return httpx.Response(200, json={"ok": True, "path": str(Path(__file__).parent)})
        if req.url.path in V.SPA_PAGES:
            return httpx.Response(200, text="<html></html>", headers={"content-type": "text/html"}) if "text/html" in req.headers.get("accept", "") else httpx.Response(401)
        return httpx.Response(200, json={"status": "ok"})
    return httpx.MockTransport(handler)


def test_checks_listam_o_que_falhou():
    r = V.run_checks("http://x", transport=_servidor({"/brains"}))
    por_nome = {n: ok for n, ok, _ in r}
    assert por_nome["brains"] is False and por_nome["health"] is True
    assert V.summarize(r) == 1


def test_tudo_certo_devolve_zero():
    r = V.run_checks("http://x", transport=_servidor())
    assert all(ok for _, ok, _ in r), [x for x in r if not x[1]]
    assert V.summarize(r) == 0


def test_skill_com_risco_desconhecido_reprova():
    r = V.run_checks("http://x", transport=_servidor(skills_riscos=("low", "unknown")))
    assert {n: ok for n, ok, _ in r}["skills sem risco desconhecido"] is False


def test_pagina_spa_sem_accept_html_nao_e_testada_como_api():
    r = V.run_checks("http://x", transport=_servidor())
    assert any(n.startswith("pagina /") and ok for n, ok, _ in r)


def test_saida_nunca_mostra_o_token():
    r = V.run_checks("http://x", transport=_servidor())
    assert "Bearer" not in " ".join(d for _, _, d in r) and "access_token" not in " ".join(d for _, _, d in r)
