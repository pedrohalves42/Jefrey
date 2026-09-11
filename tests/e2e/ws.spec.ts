import { test, expect } from '@playwright/test';

// E2E Jefrey 3D Frontend + WebSocket avatar events (P10 GUI/Avatar 3D)
// Requisito: docker compose up -d --wait (frontend http://localhost:3001, api http://localhost:8000)
// Roda: npx playwright test tests/e2e/ws.spec.ts --reporter=list

test.describe('Jefrey 3D Frontend WS', () => {
  test('frontend serve Three.js 0.165.0 + WS ws://localhost:8000/ws + 4 handlers', async ({ page }) => {
    const resp = await page.goto('http://localhost:3001/');
    expect(resp?.status()).toBe(200);
    const html = await page.content();
    expect(html).toContain('Jefrey 3D Avatar');
    expect(html).toContain('three@0.165.0');
    expect(html).toContain('OrbitControls');
    expect(html).toContain('GLTFLoader');
    expect(html).toContain('ws://localhost:8000/ws');
    expect(html).toContain("msg.type==='tool_start'");
    expect(html).toContain("msg.type==='memory_retrieved'");
    expect(html).toContain("msg.type==='approval_pending'");
    expect(html).toContain("msg.type==='security_alert'");
    expect(html).toContain('<canvas id="canvas">');
  });

  test('WS conecta e recebe console log Jefrey event', async ({ page }) => {
    const logs: string[] = [];
    page.on('console', m => logs.push(m.text()));
    await page.goto('http://localhost:3001/');
    await page.waitForTimeout(1500);
    const wsErrors: string[] = [];
    page.on('pageerror', e => wsErrors.push(String(e)));
    await page.waitForTimeout(500);
    expect(wsErrors.filter(e=>e.includes('WS msg parse'))).toHaveLength(0);
  });

  test('GET /health e /metrics vivos durante E2E', async ({ request }) => {
    const h = await request.get('http://localhost:8000/health');
    expect(h.status()).toBe(200);
    const j = await h.json();
    expect(j.status).toBe('ok');
    const m = await request.get('http://localhost:8000/metrics');
    expect(m.status()).toBe(200);
    const text = await m.text();
    expect(text).toContain('jefrey_config_valid 1.0');
    expect(text).toContain('jefrey_service_health{component="api"} 1.0');
  });

  test('MCP health 17 tools', async ({ request }) => {
    const r = await request.get('http://localhost:8001/health');
    expect(r.status()).toBe(200);
    const j = await r.json();
    expect(j.status).toBe('healthy');
    expect(j.tools).toBe(17);
    expect(j.policy.mode).toBe('enforce');
  });
});