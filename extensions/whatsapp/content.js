/* Jefrey para WhatsApp Web: le a conversa ABERTA e responde, SO nas conversas que a pessoa liberou no Jefrey.
 * Para ENVIAR algo que a pessoa aprovou, abre a conversa certa (so quando ela esta parada, sem digitar), envia e para.
 * Nao inicia conversas com desconhecidos, nao envia em massa, ignora grupos. Sempre ha pausa humana antes de enviar. */
"use strict";

(function () {
  const C = globalThis.JefreyWACore;
  if (!C || window.__jefreyWA) return;
  window.__jefreyWA = true;

  const READ_MS = 2000;
  const POLL_MS = 3000;
  const DEBOUNCE_MS = 3500; // junta mensagens seguidas antes de pedir resposta
  const seen = new Set(); // ids de mensagens que ja existiam ou ja foram tratadas
  const primed = new Set(); // conversas ja "memorizadas" (o historico antigo nunca e respondido)
  let pending = [];
  let pendingChat = "";
  let debounce = null;
  let busySending = false;
  const tries = {}; // quantas vezes tentamos abrir a conversa de cada mensagem (depois de algumas, avisa que falhou)
  const MAX_TRIES = 4;
  const T0 = window.__JEFREY_WA_TEST__;
  const IDLE_MS = T0 && typeof T0.idleMs === "number" ? T0.idleMs : 15000; // so troca de conversa se a pessoa esta parada
  let lastInput = Date.now();
  ["keydown", "mousedown", "wheel", "touchstart"].forEach((ev) => window.addEventListener(ev, () => (lastInput = Date.now()), true));
  const isIdle = () => Date.now() - lastInput >= IDLE_MS;
  let state = { paired: false, paused: false, server: "" };

  /* Se a extensao foi recarregada/atualizada com esta aba aberta, o contexto antigo morre ("Extension context invalidated"):
   * em vez de encher o console de erros, este script para e avisa para recarregar a pagina. */
  const timers = [];
  let dead = false;
  const alive = () => {
    try {
      return !!(chrome.runtime && chrome.runtime.id);
    } catch (e) {
      return false;
    }
  };
  function shutdown() {
    if (dead) return;
    dead = true;
    timers.forEach(clearInterval);
    clearTimeout(debounce);
    if (badge) {
      badge.textContent = "Jefrey: extensão atualizada. Recarregue a página (F5)";
      badge.style.opacity = "1";
    }
  }
  async function send(msg) {
    if (dead || !alive()) {
      shutdown();
      return undefined;
    }
    try {
      return await chrome.runtime.sendMessage(msg);
    } catch (e) {
      if (!alive() || /context invalidated/i.test(String((e && e.message) || e))) shutdown();
      return undefined;
    }
  }
  const call = (path, method, body) => send({ type: "api", path, method, body });

  /* ---- plaquinha discreta no canto: mostra que o Jefrey esta atento e deixa pausar ---- */
  const badge = document.createElement("div");
  badge.style.cssText =
    "position:fixed;left:12px;bottom:12px;z-index:99999;font:13px system-ui,sans-serif;background:#0b2530;color:#bff;border:1px solid #2bd;border-radius:10px;padding:6px 10px;cursor:pointer;opacity:.92";
  badge.title = "Clique para pausar ou continuar o Jefrey neste WhatsApp";
  document.documentElement.appendChild(badge);
  function paint(extra) {
    if (dead) return; // extensao recarregada: o aviso de "recarregue a pagina" nao pode ser apagado
    badge.textContent = !state.paired ? "Jefrey: não pareado" : state.paused ? "Jefrey: pausado" : extra || "Jefrey: atento";
    badge.style.opacity = state.paused || !state.paired ? "0.6" : "0.92";
  }
  badge.addEventListener("click", async () => {
    const next = !state.paused;
    await send({ type: "setPaused", paused: next });
    state.paused = next;
    paint();
  });
  async function refreshState() {
    const s = await send({ type: "status" });
    state.paired = !!(s && s.paired);
    state.paused = !!(s && s.paused) || state.paused;
    paint();
  }

  /* ---- ler ---- */
  async function flush() {
    const chat = pendingChat;
    const msgs = pending;
    pending = [];
    if (!chat || !msgs.length || state.paused) return;
    const rows = C.parseRows(document);
    const res = await call("/wa/device/inbound", "POST", {
      chat,
      is_group: C.isGroup(document),
      messages: msgs,
      context: C.context(rows.filter((r) => !msgs.some((m) => m.id === r.id)), 6),
    });
    if (res && res.data && res.data.action === "queued") paint(res.data.asked ? "Jefrey: aguardando sua aprovação" : "Jefrey: respondendo…");
  }

  async function readTick() {
    if (!state.paired || state.paused) return;
    const title = C.chatTitle(document);
    if (!title) return;
    const rows = C.parseRows(document);
    const key = C.norm(title);
    if (!primed.has(key)) {
      rows.forEach((r) => seen.add(r.id)); // o que ja estava na tela nao e respondido
      primed.add(key);
      // avisa que a conversa existe (aparece na lista do Jefrey para a pessoa liberar), sem mensagens
      call("/wa/device/inbound", "POST", { chat: title, is_group: C.isGroup(document), messages: [], context: [] });
      return;
    }
    const fresh = C.newIncoming(rows, seen);
    if (!fresh.length) return;
    fresh.forEach((r) => seen.add(r.id));
    if (pendingChat && !C.sameChat(pendingChat, title)) await flush();
    pendingChat = title;
    pending = pending.concat(fresh.map((r) => ({ id: r.id, text: r.text, kind: r.kind, from_me: false })));
    clearTimeout(debounce);
    debounce = setTimeout(flush, DEBOUNCE_MS);
  }

  /* ---- enviar (so o que foi aprovado: pela regra automatica ou pela pessoa) ---- */
  const sleep = (window.__JEFREY_WA_TEST__ && window.__JEFREY_WA_TEST__.sleep) || ((ms) => new Promise((r) => setTimeout(r, ms)));

  async function ensureChatOpen(chat) {
    if (C.sameChat(C.chatTitle(document), chat)) return true;
    if (!isIdle()) return false; // a pessoa esta mexendo no WhatsApp: nao troca a conversa debaixo dela
    if (C.composerText(document) !== "") return false; // ha rascunho na conversa aberta
    let r = C.openChat(document, chat);
    if (!r.ok && C.typeInSearch(document, chat)) {
      await sleep(1500);
      r = C.openChat(document, chat);
      C.clearSearch(document);
    }
    if (!r.ok) return false;
    for (let i = 0; i < 8; i++) {
      await sleep(500);
      if (C.sameChat(C.chatTitle(document), chat)) return true;
    }
    return false;
  }

  async function sendOne(item) {
    if (!C.sameChat(C.chatTitle(document), item.chat)) {
      const opened = await ensureChatOpen(item.chat);
      if (!opened) {
        tries[item.id] = (tries[item.id] || 0) + 1;
        if (tries[item.id] >= MAX_TRIES && isIdle()) {
          await call("/wa/device/sent", "POST", { id: item.id, ok: false }); // nao achei a conversa: avisa em vez de ficar na fila para sempre
          return true;
        }
        return false;
      }
    }
    const can = C.canSendNow(document, item.chat);
    if (!can.ok) return false; // a pessoa digitando: fica na fila para depois
    paint("Jefrey: escrevendo…");
    await sleep(C.humanDelayMs());
    const again = C.canSendNow(document, item.chat); // a pessoa pode ter mudado de conversa ou comecado a digitar
    if (!again.ok || state.paused) return false;
    if (!C.typeText(document, item.text)) {
      await call("/wa/device/sent", "POST", { id: item.id, ok: false });
      return true;
    }
    await sleep(600);
    const btn = C.sendButton(document);
    if (!btn) {
      await call("/wa/device/sent", "POST", { id: item.id, ok: false });
      return true;
    }
    btn.click();
    await sleep(1200);
    const ok = C.composerText(document) === ""; // o campo esvaziou: a mensagem saiu
    await call("/wa/device/sent", "POST", { id: item.id, ok });
    // a mensagem que acabamos de enviar aparece na tela como "minha": nunca e tratada como nova
    C.parseRows(document).forEach((r) => seen.add(r.id));
    return true;
  }

  async function pollTick() {
    if (!state.paired || busySending) return;
    const res = await call("/wa/device/poll");
    if (!res || !res.ok || !res.data) return;
    state.server = res.data.paused ? "pausado" : "";
    if (res.data.paused || state.paused) return paint();
    busySending = true;
    try {
      for (const item of res.data.send || []) {
        if (await sendOne(item)) await sleep(5000); // no maximo uma mensagem a cada poucos segundos
      }
    } finally {
      busySending = false;
      paint();
    }
  }

  const testing = window.__JEFREY_WA_TEST__;
  if (testing) {
    // gancho para os testes (pagina simulada): sem relogios reais
    testing.hooks = { readTick, pollTick, flush, refreshState, state: () => state, seen, badge };
    return;
  }
  refreshState();
  const every = (fn, ms) => timers.push(setInterval(() => (alive() ? fn() : shutdown()), ms));
  every(() => refreshState().catch(() => {}), 15000);
  every(() => readTick().catch(() => {}), READ_MS);
  every(() => pollTick().catch(() => {}), POLL_MS);
})();
