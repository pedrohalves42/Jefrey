// F6-4 PWA sw.js — cache-first assets, network-first api (DDIA cap3) — FIX J.A.R.V.I.S. v2
const CACHE = "jefrey-v2";
const ASSETS = ["/", "/vite.svg", "/manifest.json"];
self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ASSETS).catch(()=>{})));
  self.skipWaiting();
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k)))));
  self.clients.claim();
});
self.addEventListener("fetch", (e) => {
  if (e.request.method !== "GET") return;
  const url = new URL(e.request.url);
  if (url.pathname.startsWith("/chat") || url.pathname.startsWith("/auth") || url.pathname.startsWith("/connections") || url.pathname.startsWith("/memory") || url.pathname.startsWith("/stt") || url.pathname.startsWith("/tts") || url.pathname.startsWith("/health") || url.pathname.startsWith("/metrics")) {
    e.respondWith(fetch(e.request).catch(() => caches.match(e.request)));
    return;
  }
  e.respondWith(caches.match(e.request).then((cached) => cached || fetch(e.request).then((resp) => {
    if (resp.ok && e.request.method === "GET" && url.origin === location.origin) {
      const clone = resp.clone();
      caches.open(CACHE).then((c) => c.put(e.request, clone)).catch(()=>{});
    }
    return resp;
  }).catch(() => cached)));
});
