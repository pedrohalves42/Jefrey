import React from "react"
import ReactDOM from "react-dom/client"
import App from "./App.tsx"
import "./index.css"

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)

// Aplicativo instalavel e abertura offline da "casca". O service worker (public/sw.js) nunca
// intercepta a API; so aparece em producao para nao atrapalhar o servidor de desenvolvimento.
if (import.meta.env.PROD && "serviceWorker" in navigator && window.isSecureContext) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {
      /* sem service worker o app funciona igual, so nao abre offline */
    })
  })
}
