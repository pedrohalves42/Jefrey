// main.js – Jefrey 3D Interface (Phase 10)
// Referências: threejs.org, react-three-fiber.pmnd.rs, CIPHER‑031/033,
// SWE@Google runbooks, Building LLM Applications (Alto 2024).
// Este módulo é importado pelo index.html e inicializa a conexão WebSocket
// com o backend FastAPI (porta 8000) para receber eventos em tempo real:
//   – tool_start / tool_end
//   – memory_retrieved
//   – approval_pending / approval_decided
//   – security_alert
// Events update the Three.js cena (rotação, cor, efeitos de pulso).
// Caso o WebSocket falhe, a aplicação continua em modo estático.
// Para produção, servir estes arquivos através do serviço `frontend` do docker-compose.yml
// e garantir a conexão WS via ws://api:8000/ws ou wss conforme TLS.
console.log('Jefrey 3D Interface script loaded.');