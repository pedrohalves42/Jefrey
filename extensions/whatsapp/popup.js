"use strict";
const $ = (id) => document.getElementById(id);

async function render() {
  const s = await chrome.runtime.sendMessage({ type: "status" });
  $("unpaired").hidden = !!(s && s.paired);
  $("paired").hidden = !(s && s.paired);
  $("pause").textContent = s && s.paused ? "Continuar" : "Pausar tudo";
}

$("pair").addEventListener("click", async () => {
  $("msg").className = "msg";
  $("msg").textContent = "Conectando…";
  const r = await chrome.runtime.sendMessage({ type: "pair", code: $("code").value, label: "Chrome" });
  $("msg").className = "msg " + (r && r.ok ? "ok" : "err");
  $("msg").textContent = r && r.ok ? "Pronto! Conectado." : (r && r.error) || "Não consegui conectar.";
  await render();
});

$("pause").addEventListener("click", async () => {
  const s = await chrome.runtime.sendMessage({ type: "status" });
  await chrome.runtime.sendMessage({ type: "setPaused", paused: !(s && s.paused) });
  await render();
});

$("unpair").addEventListener("click", async () => {
  await chrome.runtime.sendMessage({ type: "unpair" });
  $("msg").textContent = "";
  await render();
});

render();
