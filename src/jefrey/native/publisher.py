"""Publicar nas redes pela janela do Jefrey (a pessoa ja entrou na conta nela). Roteiros de JavaScript por rede.

Cada roteiro: abre o campo de nova publicacao, escreve o texto, anexa as imagens e so entao clica em publicar (se `send` for verdadeiro).
O estado vai para `window.__jfPublish` e o Python acompanha de fora, porque o `evaluate_js` nao espera promessas.
O texto e as imagens entram no roteiro como JSON (nunca como codigo): nada do que a pessoa escreve vira instrucao.

AVISO: os seletores das redes mudam. O roteiro do X usa identificadores de teste estaveis; Facebook e Instagram usam rotulos de
acessibilidade e foram escritos sem conta de teste: se falharem, o resultado diz em qual passo parou (nada e publicado pela metade).
"""
from __future__ import annotations

import json
import time
from typing import Any, Callable, Optional

COMPOSE_URLS = {"x": "https://x.com/compose/post", "facebook": "https://www.facebook.com/", "instagram": "https://www.instagram.com/"}

HELPERS = r"""
const sleep = ms => new Promise(r => setTimeout(r, ms));
const S = window.__jfPublish = { state: "running", step: "iniciando", message: "" };
const fail = (msg) => { S.state = "error"; S.message = msg; };
const ok = (msg) => { S.state = "done"; S.message = msg; };
async function waitFor(fn, ms) { const t = Date.now(); while (Date.now() - t < (ms || 15000)) { try { const v = fn(); if (v) return v; } catch (e) {} await sleep(250); } return null; }
const clickable = (sel, re) => [...document.querySelectorAll(sel)].find(e => re.test((e.innerText || e.getAttribute("aria-label") || "").trim()));
function toFiles(list) {
  return list.map(f => { const bin = atob(f.b64); const u = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i); return new File([u], f.name, { type: f.type }); });
}
function attach(input, files) { const dt = new DataTransfer(); files.forEach(f => dt.items.add(f)); input.files = dt.files; input.dispatchEvent(new Event("input", { bubbles: true })); input.dispatchEvent(new Event("change", { bubbles: true })); }
async function typeText(el, text) { el.focus(); await sleep(150); document.execCommand("insertText", false, text); await sleep(400); }
"""

RECIPES = {
    "x": r"""
(async function () {
  S.step = "abrindo o campo do post";
  const box = await waitFor(() => document.querySelector('[data-testid="tweetTextarea_0"]'));
  if (!box) return fail("Não achei o campo do post. Entre na sua conta do X nesta janela e tente de novo.");
  S.step = "escrevendo";
  await typeText(box, P.text);
  if (P.files.length) {
    S.step = "anexando as imagens";
    const inp = await waitFor(() => document.querySelector('input[data-testid="fileInput"]') || document.querySelector('input[type="file"]'));
    if (!inp) return fail("Não achei onde anexar as imagens.");
    attach(inp, toFiles(P.files));
    await sleep(3000);
  }
  if (!P.send) return ok("Texto escrito no X. Falta só publicar.");
  S.step = "publicando";
  const btn = await waitFor(() => { const b = document.querySelector('[data-testid="tweetButton"]') || document.querySelector('[data-testid="tweetButtonInline"]'); return b && b.getAttribute("aria-disabled") !== "true" && !b.disabled ? b : null; }, 20000);
  if (!btn) return fail("O botão de publicar não ficou disponível (texto grande demais ou imagem ainda enviando).");
  btn.click();
  await sleep(3500);
  const still = document.querySelector('[data-testid="tweetTextarea_0"]');
  return ok(still && (still.innerText || "").trim().length > 5 ? "Cliquei em publicar, mas o texto continua na tela. Confira na janela." : "Publicado no X.");
})();
""",
    "facebook": r"""
(async function () {
  S.step = "abrindo o campo de nova publicação";
  const open = await waitFor(() => clickable('[role="button"]', /no que voc[eê] est[aá] pensando|what'?s on your mind|criar publica/i));
  if (!open) return fail("Não achei o campo de nova publicação. Entre na sua conta do Facebook nesta janela e tente de novo.");
  open.click();
  const box = await waitFor(() => document.querySelector('[role="dialog"] [contenteditable="true"][role="textbox"]'));
  if (!box) return fail("A janela de nova publicação não abriu.");
  S.step = "escrevendo";
  await typeText(box, P.text);
  if (P.files.length) {
    S.step = "anexando as imagens";
    const add = clickable('[role="dialog"] [role="button"], [role="dialog"] [aria-label]', /foto\/v[ií]deo|photo\/video/i);
    if (add) add.click();
    const inp = await waitFor(() => document.querySelector('[role="dialog"] input[type="file"]'));
    if (!inp) return fail("Não achei onde anexar as imagens.");
    attach(inp, toFiles(P.files));
    await sleep(4000);
  }
  if (!P.send) return ok("Texto escrito no Facebook. Falta só publicar.");
  S.step = "publicando";
  const btn = await waitFor(() => { const b = clickable('[role="dialog"] [role="button"], [role="dialog"] [aria-label]', /^(publicar|post)$/i); return b && b.getAttribute("aria-disabled") !== "true" ? b : null; }, 20000);
  if (!btn) return fail("Não achei o botão de publicar.");
  btn.click();
  await sleep(4000);
  return ok(document.querySelector('[role="dialog"] [contenteditable="true"][role="textbox"]') ? "Cliquei em publicar, mas a janela continua aberta. Confira na janela." : "Publicado no Facebook.");
})();
""",
    "instagram": r"""
(async function () {
  if (!P.files.length) return fail("O Instagram precisa de pelo menos uma imagem. Crie um carrossel primeiro.");
  S.step = "abrindo nova publicação";
  const create = await waitFor(() => clickable('a, div[role="button"], span', /^(criar|create|nova publica[cç][aã]o|new post)$/i));
  if (!create) return fail("Não achei o botão Criar. Entre na sua conta do Instagram nesta janela e tente de novo.");
  create.click();
  const post = await waitFor(() => clickable('a, div[role="button"], span', /^(publica[cç][aã]o|post)$/i), 8000);
  if (post) post.click();
  S.step = "anexando as imagens";
  const inp = await waitFor(() => document.querySelector('input[type="file"]'));
  if (!inp) return fail("Não achei onde escolher as imagens.");
  attach(inp, toFiles(P.files));
  await sleep(4000);
  for (let i = 0; i < 2; i++) {
    S.step = "avançando";
    const next = await waitFor(() => clickable('div[role="button"], button', /^(avan[cç]ar|next)$/i), 10000);
    if (!next) return fail("Não achei o botão Avançar.");
    next.click();
    await sleep(1500);
  }
  S.step = "escrevendo a legenda";
  const cap = await waitFor(() => document.querySelector('[aria-label*="legenda"], [aria-label*="caption"], div[contenteditable="true"][role="textbox"]'));
  if (!cap) return fail("Não achei o campo da legenda.");
  await typeText(cap, P.text);
  if (!P.send) return ok("Imagens e legenda prontas no Instagram. Falta só compartilhar.");
  S.step = "compartilhando";
  const share = await waitFor(() => clickable('div[role="button"], button', /^(compartilhar|share)$/i), 10000);
  if (!share) return fail("Não achei o botão Compartilhar.");
  share.click();
  await sleep(6000);
  return ok("Pedi para compartilhar no Instagram. Confira na janela se apareceu a confirmação.");
})();
""",
}


def build_script(net: str, text: str, files: list[dict], send: bool) -> str:
    """Roteiro completo. Texto e arquivos entram como JSON (so dados)."""
    if net not in RECIPES:
        raise ValueError("rede sem roteiro de publicacao")
    params = json.dumps({"text": text, "files": files, "send": bool(send)}, ensure_ascii=False)
    return f"(function(){{ const P = {params};\n{HELPERS}\n{RECIPES[net]}\n}})();"


def run(window: Any, net: str, text: str, files: list[dict], send: bool, *, timeout: float = 90.0,
        sleep: Callable[[float], None] = time.sleep) -> dict:
    """Roda o roteiro na janela e acompanha ate terminar. {"ok": bool, "message": str, "step": str}."""
    window.evaluate_js(build_script(net, text, files, send))
    waited = 0.0
    last: dict = {}
    while waited < timeout:
        sleep(1.0)
        waited += 1.0
        try:
            raw: Optional[str] = window.evaluate_js("JSON.stringify(window.__jfPublish || null)")
            last = json.loads(raw) if raw else {}
        except Exception:
            last = {}
        if last.get("state") in ("done", "error"):
            return {"ok": last["state"] == "done", "message": str(last.get("message", "")), "step": str(last.get("step", ""))}
    return {"ok": False, "message": f"Demorou demais no passo “{last.get('step', '?')}”. Confira na janela.", "step": str(last.get("step", ""))}
