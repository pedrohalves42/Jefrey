/* Service worker do Jefrey: conservador de proposito.
 *
 * Regra de ouro: NUNCA intercepta chamadas da API (chat, memoria, aprovacoes, voz, auth, metricas,
 * configuracoes...). So guarda a "casca" do aplicativo (arquivos estaticos) para ele abrir mesmo
 * sem conexao. Qualquer outra requisicao segue direto para a rede, sem passar por aqui.
 */
const VERSION = "jefrey-shell-v1"
const SHELL = ["/", "/manifest.json", "/images/icon-192.png"]
// caminhos estaticos que podem ficar em cache (nomes com hash em /assets/ nunca mudam de conteudo)
const STATIC_PREFIXES = ["/assets/", "/images/"]
const STATIC_FILES = ["/manifest.json", "/favicon.ico", "/vite.svg"]
// paginas do aplicativo (navegacao): rede primeiro, casca guardada se estiver offline
const APP_PAGES = ["/", "/memoria", "/skills", "/configuracoes", "/avancado"]

self.addEventListener("install", event => {
  event.waitUntil(
    caches
      .open(VERSION)
      .then(c => c.addAll(SHELL))
      .catch(() => {}) // sem rede na instalacao: segue sem casca
      .then(() => self.skipWaiting()),
  )
})

self.addEventListener("activate", event => {
  event.waitUntil(
    caches
      .keys()
      .then(keys => Promise.all(keys.filter(k => k !== VERSION).map(k => caches.delete(k))))
      .then(() => self.clients.claim()),
  )
})

function isStatic(url) {
  return STATIC_FILES.includes(url.pathname) || STATIC_PREFIXES.some(p => url.pathname.startsWith(p))
}

self.addEventListener("fetch", event => {
  const req = event.request
  if (req.method !== "GET") return // nunca mexe em POST/PUT/DELETE
  const url = new URL(req.url)
  if (url.origin !== self.location.origin) return // so o proprio Jefrey

  // 1) arquivos estaticos: cache primeiro, atualiza em segundo plano
  if (isStatic(url)) {
    event.respondWith(
      caches.open(VERSION).then(cache =>
        cache.match(req).then(hit => {
          const fresh = fetch(req)
            .then(resp => {
              if (resp.ok) cache.put(req, resp.clone()).catch(() => {})
              return resp
            })
            .catch(() => hit)
          return hit || fresh
        }),
      ),
    )
    return
  }

  // 2) navegacao pelas paginas do app: rede primeiro; offline -> casca guardada
  if (req.mode === "navigate" && APP_PAGES.includes(url.pathname)) {
    event.respondWith(
      fetch(req)
        .then(resp => {
          if (resp.ok && url.pathname === "/") caches.open(VERSION).then(c => c.put("/", resp.clone())).catch(() => {})
          return resp
        })
        .catch(() => caches.match("/").then(hit => hit || Response.error())),
    )
    return
  }

  // 3) todo o resto (API, voz, streaming, auth...): nao intercepta
})
