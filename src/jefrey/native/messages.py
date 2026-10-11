"""Janela "Mensagens": o WhatsApp Web dentro do proprio Jefrey (WebView2), sem Chrome e sem extensao.

O mesmo codigo da extensao (core.js + content.js) roda dentro desta janela. So muda a ponte: no lugar de `chrome.runtime.sendMessage`,
o script chama `WaBridge.wa_message` (Python), que fala com o servidor do Jefrey usando o token de um "aparelho" proprio da janela
(aparece na tela Conexoes como "Janela do Jefrey"). A sessao do WhatsApp fica guardada no perfil do Jefrey: o QR code e lido uma vez so.

Seguranca: a ponte so aceita os caminhos /wa/device/* da lista; o texto que vem do WhatsApp continua sendo DADO (a regra esta no servidor).
"""
from __future__ import annotations

import json
import logging
import re
import threading
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

WA_URL = "https://web.whatsapp.com"
TITLE = "Jefrey · Mensagens"
STATE_FILE = "messages.json"
DEVICE_LABEL = "Janela do Jefrey"
ALLOWED_PATHS = ("/wa/device/inbound", "/wa/device/inbox", "/wa/device/history", "/wa/device/command", "/wa/device/poll", "/wa/device/sent")
_USER_RX = re.compile(r"^[A-Za-z0-9_.@-]{1,64}$")

SHIM = """
(function () {
  if (window.top !== window || location.hostname !== "web.whatsapp.com") return;
  var ready = new Promise(function (ok) {
    (function wait() { if (window.pywebview && window.pywebview.api && window.pywebview.api.wa_message) ok(); else setTimeout(wait, 150); })();
  });
  window.chrome = window.chrome || {};
  window.chrome.runtime = {
    id: "jefrey-window",
    sendMessage: function (msg) {
      return ready.then(function () { return window.pywebview.api.wa_message(JSON.stringify(msg)); }).then(function (r) { return JSON.parse(r); });
    },
  };
  var go = function () { try { @@BODY@@ } catch (e) { console.error("jefrey", e); } };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", go); else go();
})();
"""


def build_script(ext_dir: Path) -> str:
    """core.js + content.js da extensao, com a ponte do Python no lugar do Chrome."""
    body = (ext_dir / "core.js").read_text(encoding="utf-8") + "\n" + (ext_dir / "content.js").read_text(encoding="utf-8")
    return SHIM.replace("@@BODY@@", body)


def valid_user(user_id: str) -> bool:
    return bool(_USER_RX.match(user_id or "")) and user_id not in ("system", "anonymous")


def state_path(home: Path) -> Path:
    return home / "config" / STATE_FILE


def load_state(home: Path) -> dict:
    try:
        d = json.loads(state_path(home).read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def save_state(home: Path, state: dict) -> None:
    try:
        f = state_path(home)
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = f.with_suffix(".tmp")
        tmp.write_text(json.dumps(state), encoding="utf-8")
        tmp.replace(f)
    except OSError as e:
        logger.debug("estado das mensagens nao salvo (%s)", type(e).__name__)


class WaBridge:
    """O que a pagina do WhatsApp (com o codigo da extensao) pode pedir ao Jefrey. Nada alem disto."""

    def __init__(self, base_url: str, home: Path, pair: Callable[[str], Optional[str]], http: Optional[Callable[..., dict]] = None):
        self._base, self._home, self._pair = base_url.rstrip("/"), home, pair
        self._http = http or self._real_http
        self._lock = threading.Lock()
        st = load_state(home)
        self._user: str = st.get("user", "") if valid_user(st.get("user", "")) else ""
        self._token: str = self._unprotect(st.get("token", ""))
        self._paused: bool = bool(st.get("paused", False))

    # ---- estado ----
    @staticmethod
    def _protect(v: str) -> str:
        try:
            from src.jefrey.core.secret_store import protect

            return protect(v)
        except Exception:
            return v

    @staticmethod
    def _unprotect(v: str) -> str:
        try:
            from src.jefrey.core.secret_store import unprotect

            return unprotect(v) if v else ""
        except Exception:
            return v or ""

    def _save(self) -> None:
        save_state(self._home, {"user": self._user, "token": self._protect(self._token) if self._token else "", "paused": self._paused,
                                "enabled": bool(self._user)})

    def set_user(self, user_id: str) -> bool:
        """A tela diz quem e a pessoa (o mesmo usuario da interface); troca de pessoa descarta o token antigo."""
        if not valid_user(user_id):
            return False
        with self._lock:
            if user_id != self._user:
                self._user, self._token = user_id, ""
            self._save()
        return True

    @property
    def user(self) -> str:
        return self._user

    def enabled(self) -> bool:
        return bool(self._user)

    # ---- chamadas ao servidor ----
    def _real_http(self, method: str, path: str, token: str, body: Any) -> dict:
        import httpx

        try:
            r = httpx.request(method, self._base + path, headers={"Authorization": "Bearer " + token}, json=body if body is not None else None, timeout=20)
        except httpx.HTTPError:
            return {"ok": False, "status": 0, "error": "jefrey-fechado"}
        try:
            data = r.json()
        except ValueError:
            data = None
        return {"ok": r.is_success, "status": r.status_code, "data": data}

    def _ensure_token(self) -> str:
        with self._lock:
            if not self._token and self._user:
                self._token = self._pair(self._user) or ""
                self._save()
            return self._token

    def _api(self, path: str, method: str, body: Any) -> dict:
        if path not in ALLOWED_PATHS:
            return {"ok": False, "status": 403, "error": "caminho-nao-permitido"}
        token = self._ensure_token()
        if not token:
            return {"ok": False, "status": 0, "error": "nao-pareado"}
        res = self._http(method or "GET", path, token, body)
        if res.get("status") == 401:  # o Jefrey esqueceu este aparelho: pareia de novo uma vez
            with self._lock:
                self._token = ""
            token = self._ensure_token()
            res = self._http(method or "GET", path, token, body) if token else res
        return res

    # ---- o que a pagina chama (pywebview expoe os metodos publicos) ----
    def wa_message(self, raw: str) -> str:
        try:
            msg = json.loads(raw)
        except (TypeError, ValueError):
            return json.dumps({"ok": False})
        kind = msg.get("type") if isinstance(msg, dict) else None
        if kind == "api":
            out = self._api(str(msg.get("path", "")), str(msg.get("method") or "GET").upper(), msg.get("body"))
        elif kind == "status":
            out = {"paired": bool(self._user), "paused": self._paused}
        elif kind == "setPaused":
            self._paused = bool(msg.get("paused"))
            self._save()
            out = {"ok": True}
        else:
            out = {"ok": False}
        return json.dumps(out)


def pair_in_process(user_id: str) -> Optional[str]:
    """Pareia a janela com o servidor que roda neste mesmo processo (sem codigo digitado)."""
    try:
        from src.jefrey.adapters.outbound.sql_whatsapp import WAStore

        code = WAStore.begin_pairing(user_id)["code"]
        return WAStore().complete_pairing(code, DEVICE_LABEL)
    except Exception as e:
        logger.warning("nao consegui parear a janela de mensagens (%s)", type(e).__name__)
        return None


class WaApi:
    """A unica coisa que a pagina do WhatsApp enxerga (o pywebview expoe so os metodos publicos desta classe)."""

    def __init__(self, bridge: WaBridge):
        self._bridge = bridge

    def wa_message(self, raw: str) -> str:
        return self._bridge.wa_message(raw)
