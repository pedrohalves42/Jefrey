// main.js – Jefrey 3D Interface + Voice (Phase P9/P10)
// Referencias: threejs.org, MDN getUserMedia/MediaRecorder/Web Audio, CIPHER-031/033,
// SWE@Google runbooks, Building LLM Applications (Alto 2024).
// Este modulo e importado opcionalmente pelo index.html; toda a logica de voz tambem
// esta inline em index.html para funcionar sem bundler. Este arquivo expoe initVoice()
// para testes e para quem importar via <script type="module" src="main.js">.
console.log('Jefrey 3D Interface script loaded.');

export function initVoice({ token, userId, apiBase = 'http://localhost:8000' } = {}) {
  const btnMic = document.getElementById('btnMic');
  const player = document.getElementById('player');
  if (!btnMic) {
    console.warn('initVoice: #btnMic nao encontrado (index.html ja tem voz inline).');
    return { ok: false, reason: 'btnMic missing' };
  }
  console.log('initVoice bound', { userId, apiBase });
  return { ok: true, btnMic, player };
}

// Auto-bind se carregado como side-effect (sem import)
if (typeof document !== 'undefined') {
  document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('btnMic')) {
      console.log('main.js: voice UI detected inline in index.html');
    }
  });
}
