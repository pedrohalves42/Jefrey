"""Servidor do CELULAR (separado da API principal, que continua so em 127.0.0.1).

Pequeno de proposito: so mostra a pagina, pareia com codigo de uso unico e repassa perguntas ao Jefrey.
Regras (fail-closed), valem para TODA rota:
  - o pedido precisa vir de um endereco da rede local (nunca da internet);
  - o Host precisa ser um IP (o celular abre pelo endereco do QR): nome de dominio e recusado (DNS rebinding);
  - pedidos de escrita so da propria pagina (Origin = Host);
  - depois do pareamento, cada pedido leva o token da sessao; sem ele, nada responde.
Acoes de risco continuam pedindo aprovacao NO COMPUTADOR: o celular nao aprova nada.
"""
from __future__ import annotations

from typing import Awaitable, Callable
from urllib.parse import urlsplit

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response
from starlette.routing import Route

from src.jefrey.domain.pairing import PairingBook, host_is_ip_literal, is_private_ip

MAX_MESSAGE = 1000
Relay = Callable[[str, str], Awaitable[str]]

PAGE = """<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex"><title>Jefrey</title>
<style>:root{color-scheme:dark}body{margin:0;font:18px system-ui;background:#0b0e11;color:#eef;display:flex;flex-direction:column;min-height:100vh}
header{padding:16px;font-weight:600;border-bottom:1px solid #223}main{flex:1;padding:16px;overflow:auto}
.m{max-width:85%;margin:8px 0;padding:10px 14px;border-radius:14px;white-space:pre-wrap}.u{background:#1d4ed8;margin-left:auto}.j{background:#1b2230}
form{display:flex;gap:8px;padding:12px;border-top:1px solid #223}input{flex:1;font:inherit;padding:12px;border-radius:12px;border:1px solid #334;background:#10151c;color:#fff}
button{font:inherit;padding:12px 18px;border-radius:12px;border:0;background:#2563eb;color:#fff}</style></head><body>
<header>Jefrey no celular</header><main id="log" aria-live="polite"></main>
<form id="f"><input id="q" autocomplete="off" placeholder="Fale com o Jefrey" aria-label="Mensagem"><button>Enviar</button></form>
<script>
const log=document.getElementById('log'),q=document.getElementById('q');
function add(t,c){const d=document.createElement('div');d.className='m '+c;d.textContent=t;log.appendChild(d);log.scrollTop=log.scrollHeight;return d}
let tok=null;try{tok=localStorage.getItem('jf_tok')}catch(e){}
async function pair(){const m=location.hash.match(/c=(\\d{8})/);if(!m)return;history.replaceState(null,'',location.pathname);
 const r=await fetch('/pair',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code:m[1],name:'Celular'})});
 if(r.ok){tok=(await r.json()).token;try{localStorage.setItem('jf_tok',tok)}catch(e){}add('Pareado! Pode falar comigo.','j')}else add('Código inválido ou vencido. Gere outro no computador.','j')}
pair();
document.getElementById('f').onsubmit=async e=>{e.preventDefault();const t=q.value.trim();if(!t)return;q.value='';add(t,'u');
 if(!tok){add('Primeiro leia o QR code no computador.','j');return}
 const w=add('…','j');try{const r=await fetch('/ask',{method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+tok},body:JSON.stringify({message:t})});
 const d=await r.json();w.textContent=r.ok?d.answer:(r.status==401?'Sessão expirou: leia o QR de novo.':(d.error||'Não consegui agora.'))}catch(err){w.textContent='Sem conexão com o computador.'}};
</script></body></html>"""


def build_phone_app(book: PairingBook, relay: Relay, enabled: Callable[[], bool] = lambda: True) -> Starlette:
    def _json(data: dict, status: int = 200) -> JSONResponse:
        return JSONResponse(data, status_code=status, headers={"Cache-Control": "no-store"})

    def _refuse(request: Request) -> Response | None:
        client = request.client.host if request.client else ""
        if not enabled() or not is_private_ip(client) or not host_is_ip_literal(request.headers.get("host", "")):
            return Response("Nao permitido", status_code=403)
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            origin = request.headers.get("origin")
            if origin is None or urlsplit(origin).netloc.lower() != request.headers.get("host", "").lower():
                return Response("Nao permitido", status_code=403)
        return None

    async def page(request: Request):
        return _refuse(request) or HTMLResponse(PAGE, headers={"Cache-Control": "no-store", "X-Frame-Options": "DENY",
                                                               "Referrer-Policy": "no-referrer",
                                                               "Content-Security-Policy": "default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'"})

    async def pair(request: Request):
        if (r := _refuse(request)) is not None:
            return r
        try:
            body = await request.json()
        except ValueError:
            return _json({"error": "pedido invalido"}, 400)
        token = book.redeem(str(body.get("code", "")), str(body.get("name", "Celular")))
        return _json({"token": token}) if token else _json({"error": "codigo invalido ou vencido"}, 403)

    async def ask(request: Request):
        if (r := _refuse(request)) is not None:
            return r
        auth = request.headers.get("authorization", "")
        dev = book.check(auth[7:]) if auth.lower().startswith("bearer ") else None
        if dev is None:
            return _json({"error": "sessao invalida"}, 401)
        try:
            body = await request.json()
        except ValueError:
            return _json({"error": "pedido invalido"}, 400)
        text = str(body.get("message", "")).strip()
        if not text or len(text) > MAX_MESSAGE:
            return _json({"error": "mensagem vazia ou longa demais"}, 400)
        try:
            return _json({"answer": await relay(dev.user_id, text)})
        except Exception:
            return _json({"error": "O Jefrey não respondeu agora. Tente de novo."}, 502)

    return Starlette(routes=[Route("/", page), Route("/pair", pair, methods=["POST"]), Route("/ask", ask, methods=["POST"])])
