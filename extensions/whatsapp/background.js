/* Jefrey para WhatsApp Web: ponte com o programa Jefrey (so no mesmo computador).
 * Guarda o endereco e o token do aparelho; a pagina do WhatsApp nunca ve o token. */
"use strict";

const PORTS = [8000, 8001, 8002, 8003, 8004, 8005, 8006, 8007, 8008, 8009, 8010];

async function store() {
  return await chrome.storage.local.get(["base", "token", "paused"]);
}

async function findBase(preferred) {
  const tries = preferred ? [preferred] : [];
  for (const p of PORTS) tries.push("http://127.0.0.1:" + p);
  for (const base of tries) {
    try {
      const r = await fetch(base + "/health", { signal: AbortSignal.timeout(1500) });
      if (r.ok && (await r.text()).includes("security_components")) return base;
    } catch (e) {
      /* tenta a proxima porta */
    }
  }
  return null;
}

async function api(path, method, body) {
  let { base, token } = await store();
  if (!base || !token) return { ok: false, status: 0, error: "nao-pareado" };
  const send = async (b) =>
    fetch(b + path, {
      method: method || "GET",
      headers: { Authorization: "Bearer " + token, "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
      signal: AbortSignal.timeout(20000),
    });
  try {
    let r = await send(base);
    return { ok: r.ok, status: r.status, data: await r.json().catch(() => null) };
  } catch (e) {
    const found = await findBase(null); // o Jefrey pode ter aberto em outra porta
    if (found && found !== base) {
      await chrome.storage.local.set({ base: found });
      try {
        const r = await send(found);
        return { ok: r.ok, status: r.status, data: await r.json().catch(() => null) };
      } catch (e2) {
        /* cai no erro abaixo */
      }
    }
    return { ok: false, status: 0, error: "jefrey-fechado" };
  }
}

async function pair(code, label) {
  const base = await findBase((await store()).base);
  if (!base) return { ok: false, error: "O Jefrey não está aberto neste computador." };
  const r = await fetch(base + "/wa/device/pair", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code: String(code || "").trim(), label: label || "Chrome" }),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok || !data.token) return { ok: false, error: r.status === 403 ? "Código inválido ou vencido. Peça um novo no Jefrey." : "Não consegui parear agora." };
  await chrome.storage.local.set({ base: base, token: data.token, paused: false });
  return { ok: true };
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  (async () => {
    if (msg.type === "pair") return pair(msg.code, msg.label);
    if (msg.type === "api") return api(msg.path, msg.method, msg.body);
    if (msg.type === "status") {
      const s = await store();
      return { paired: !!(s.base && s.token), paused: !!s.paused };
    }
    if (msg.type === "setPaused") {
      await chrome.storage.local.set({ paused: !!msg.paused });
      return { ok: true };
    }
    if (msg.type === "unpair") {
      await chrome.storage.local.remove(["token"]);
      return { ok: true };
    }
    return { ok: false };
  })()
    .then(sendResponse)
    .catch(() => sendResponse({ ok: false, error: "erro" }));
  return true;
});
