# Jefrey AI - Smoke Tests (k6)
# Run: k6 run smoke-tests.js
import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');
const apiLatency = new Trend('api_latency');
const mcpLatency = new Trend('mcp_latency');
const wsConnectTime = new Trend('ws_connect_time');
const authSuccess = new Counter('auth_success');
const authFailure = new Counter('auth_failure');

// Configuration
const BASE_URL = __ENV.BASE_URL || 'https://jefrey.your-domain.com';
const MCP_URL = __ENV.MCP_URL || 'https://jefrey.your-domain.com/mcp';
const WS_URL = __ENV.WS_URL || 'wss://jefrey.your-domain.com/ws';
const JWT_TOKEN = __ENV.JWT_TOKEN || '';
const MCP_TOKEN = __ENV.MCP_TOKEN || '';

export const options = {
  stages: [
    { duration: '30s', target: 5 },   // Ramp up
    { duration: '1m', target: 10 },   // Steady state
    { duration: '30s', target: 20 },  // Stress
    { duration: '30s', target: 0 },   // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<2000'],     // 95% requests < 2s
    http_req_failed: ['rate<0.01'],        // Error rate < 1%
    errors: ['rate<0.05'],                 // Custom error rate < 5%
    api_latency: ['p(95)<1500'],           // API p95 < 1.5s
    mcp_latency: ['p(95)<3000'],           // MCP p95 < 3s
    ws_connect_time: ['p(95)<1000'],       // WS connect < 1s
  },
  ext: {
    loadimpact: {
      projectID: __ENV.K6_PROJECT_ID,
      name: 'Jefrey AI Smoke Tests',
    },
  },
};

function authHeaders() {
  return {
    'Authorization': `Bearer ${JWT_TOKEN}`,
    'Content-Type': 'application/json',
    'X-Jefrey-Role': 'user',
  };
}

function mcpHeaders() {
  return {
    'Authorization': `Bearer ${MCP_TOKEN}`,
    'Content-Type': 'application/json',
    'MCP-Protocol-Version': '2025-06-18',
  };
}

export function setup() {
  // Verify endpoints are reachable
  const health = http.get(`${BASE_URL}/health`);
  check(health, { 'health endpoint up': (r) => r.status === 200 });
  
  const mcpHealth = http.get(`${MCP_URL}/health`, { headers: mcpHeaders() });
  check(mcpHealth, { 'MCP health endpoint up': (r) => r.status === 200 });
  
  return { baseUrl: BASE_URL, mcpUrl: MCP_URL };
}

export default function (data) {
  const baseUrl = data.baseUrl;
  const mcpUrl = data.mcpUrl;

  group('Health & Public Endpoints', () => {
    // Public health check
    let res = http.get(`${baseUrl}/health`);
    check(res, { 'GET /health = 200': (r) => r.status === 200 });
    errorRate.add(res.status !== 200);

    // Metrics endpoint
    res = http.get(`${baseUrl}/metrics`);
    check(res, { 'GET /metrics = 200': (r) => r.status === 200 });
    errorRate.add(res.status !== 200);
  });

  group('Authenticated API Endpoints', () => {
    if (!JWT_TOKEN) {
      console.warn('JWT_TOKEN not set, skipping authenticated tests');
      return;
    }

    // Chat endpoint
    const chatPayload = JSON.stringify({
      messages: [{ role: 'user', content: 'Hello, smoke test!' }],
      stream: false,
    });
    
    let start = new Date();
    let res = http.post(`${baseUrl}/chat`, chatPayload, { headers: authHeaders() });
    apiLatency.add(new Date() - start);
    
    check(res, { 
      'POST /chat = 200': (r) => r.status === 200,
      'chat has response': (r) => r.json('response') !== undefined,
    });
    errorRate.add(res.status !== 200);
    authSuccess.add(res.status === 200);
    authFailure.add(res.status !== 200);

    // Memory list
    start = new Date();
    res = http.get(`${baseUrl}/memory/recent?limit=5`, { headers: authHeaders() });
    apiLatency.add(new Date() - start);
    check(res, { 'GET /memory/recent = 200': (r) => r.status === 200 });
    errorRate.add(res.status !== 200);

    // Approvals list
    res = http.get(`${baseUrl}/approvals`, { headers: authHeaders() });
    check(res, { 'GET /approvals = 200': (r) => r.status === 200 });
    errorRate.add(res.status !== 200);
  });

  group('MCP Gateway', () => {
    if (!MCP_TOKEN) {
      console.warn('MCP_TOKEN not set, skipping MCP tests');
      return;
    }

    // MCP Discovery
    let start = new Date();
    let res = http.get(`${mcpUrl}/tools/list`, { headers: mcpHeaders() });
    mcpLatency.add(new Date() - start);
    check(res, { 
      'MCP tools/list = 200': (r) => r.status === 200,
      'has tools': (r) => Array.isArray(r.json('tools')),
    });
    errorRate.add(res.status !== 200);

    // MCP Tool Call (low risk)
    const toolPayload = JSON.stringify({
      method: 'tools/call',
      params: {
        name: 'web_search',
        arguments: { query: 'smoke test', max_results: 1 },
      },
      id: 'smoke-1',
    });
    
    start = new Date();
    res = http.post(`${mcpUrl}`, toolPayload, { headers: mcpHeaders() });
    mcpLatency.add(new Date() - start);
    check(res, { 
      'MCP tool call = 200': (r) => r.status === 200,
      'has result': (r) => r.json('result') !== undefined,
    });
    errorRate.add(res.status !== 200);
  });

  group('WebSocket', () => {
    if (!JWT_TOKEN) return;
    
    const wsUrl = `${WS_URL}?token=${JWT_TOKEN}`;
    const ws = http.ws.connect(wsUrl, null, (socket) => {
      const connectStart = new Date();
      
      socket.on('open', () => {
        wsConnectTime.add(new Date() - connectStart);
        
        // Send ping
        socket.send(JSON.stringify({ type: 'ping', payload: {} }));
        
        socket.setTimeout(() => {
          socket.close();
        }, 5000);
      });
      
      socket.on('message', (msg) => {
        const data = JSON.parse(msg);
        check(data, { 'WS pong received': (d) => d.type === 'pong' });
      });
      
      socket.on('error', () => {
        errorRate.add(true);
      });
    });
    
    check(ws, { 'WS connected': (w) => w !== null });
    errorRate.add(ws === null);
  });

  sleep(1);
}

export function teardown(data) {
  // Final health check
  const res = http.get(`${data.baseUrl}/health`);
  check(res, { 'Final health check = 200': (r) => r.status === 200 });
}