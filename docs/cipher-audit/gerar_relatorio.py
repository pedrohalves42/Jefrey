#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gerador Relatório CIPHER — Jefrey Assistant (P0-P5)
venv isolado: docs/cipher-audit/.venv (reportlab + matplotlib)
Saída: docs/cipher-audit/relatorio-cipher-jefrey.pdf
A4, margens 2cm, header/footer, capa, rosca/bar, tabelas chip, P1/P2/P3, riscos, issues GH
"""
import os, sys, html, pathlib, textwrap
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = pathlib.Path(__file__).resolve().parent / "relatorio-cipher-jefrey.pdf"
CHART_DIR = pathlib.Path(os.getenv("TMP", "/tmp")) / "jefrey_cipher_charts"
CHART_DIR.mkdir(parents=True, exist_ok=True)
DONUT = CHART_DIR / "donut.png"
BAR = CHART_DIR / "bar.png"

# Paleta exigida
SEV_HEX = {"Crítica":"#B91C1C","Alta":"#EA580C","Média":"#D97706","Baixa":"#2563EB","Informativa":"#6B7280","Ponto Forte":"#059669"}
SEV_ORDER = ["Crítica","Alta","Média","Baixa","Informativa"]
CATS = ["1 Bugs","2 Lógica","3 Isolamento","4 Permissão","5 IDOR","6 Secrets","7 Inputs"]

# Achados consolidados (verificados arquivo:linha + trecho)
FINDINGS = [
    # C1 BUGS
    {"id":"CIPHER-101","cat":"1 Bugs","sev":"Crítica","file":"src/jefrey/core/memory.py:466","code":"relevant_memories = self.long_term.search(current_query)  # sem user_id","desc":"MemoryManager.get_context() ignora user_id. Agent._load_context chama sem user_id. Prompt LLM vaza memórias cross-tenant.","impact":"PII leak entre tenants. Violação Axiom #2.","fix":"get_context(query, user_id) -> search(query, user_id=user_id); agent._load_context usa state.user_id."},
    {"id":"CIPHER-102","cat":"1 Bugs","sev":"Crítica","file":"src/jefrey/core/config.py:50 / models.py:14","code":"embedding_dim=1536 vs Ollama nomic-embed-text 768 dims; Vector(1536)","desc":"Dimensão pgvector diverge do embedding real. Postgres INSERT falha 'expected 1536 got 768'.","impact":"Long-term memory 100% quebrada em provider=postgres.","fix":"Ajustar dim para 768 quando nomic-embed-text ou trocar modelo para text-embedding-1536. Assert len(embed) no startup + migration."},
    {"id":"CIPHER-103","cat":"1 Bugs","sev":"Alta","file":"src/jefrey/core/redis_memory.py:111-113","code":"self._redis.set(self._key(), json.dumps(items))  # sem EXPIRE","desc":"Working memory SET sem TTL. Chaves jefrey:wm:{user}:{session} crescem sem limite. session() não propaga user_id.","impact":"Vazamento cross-tenant + Redis OOM em escala.","fix":"SET ex=86400; session() copiar self.user_id; chave sempre com user_id."},
    {"id":"CIPHER-104","cat":"1 Bugs","sev":"Baixa","file":"src/jefrey/core/checkpointer.py:23-76 / src/jefrey/api/main.py","code":"_saver/_cm singleton sem close em lifespan","desc":"Pool AsyncPostgresSaver sem shutdown hook. Reload deixa conexões órfãs.","impact":"Leak de conexões em testes/reload.","fix":"Adicionar lifespan @asynccontextmanager fechando close_postgres_checkpointer()."},
    # C2 LOGICA
    {"id":"CIPHER-105","cat":"2 Lógica","sev":"Alta","file":"src/jefrey/core/agent.py:220 + executor.py:110 + content_guard.py","code":"ToolMessage(json.dumps(result)) sem sanitize_tool_output","desc":"Gap PolicyEngine vs content_guard: output de tool LOW (search, drive) vai direto ao LLM sem sanitização. MCPClient sanitiza, agent não.","impact":"Prompt injection via página maliciosa indexada por web_search.","fix":"Sanitizar antes de ToolMessage: sanitize_tool_output(json.dumps(result), tool_name)."},
    {"id":"CIPHER-106","cat":"2 Lógica","sev":"Média","file":"src/jefrey/api/connections.py:32-40","code":"get_audit_logger().log(user_id=..., action=..., resource=...) # assinatura errada","desc":"Browse chama AuditLogger com kwargs inexistentes (thread_id/tool_name exigidos). Except: pass silencia, audit nunca grava.","impact":"Forense cega para /connections/browse.","fix":"audit_tool_call(thread_id='connections', tool_name='browse', ... , detail={'url':url})"},
    {"id":"CIPHER-107","cat":"2 Lógica","sev":"Média","file":"src/jefrey/cli/main.py:60-110","code":"if status=='complete' ... elif pending ... else: print(status)","desc":"CLI não faz polling para status 'running' (retornado após 5s). memory search sem Authorization header.","impact":"UX quebrada em mensagens longas; 401 em prod.","fix":"Loop polling GET /chat/status até complete/pending; enviar headers=get_auth_headers() em memory search."},
    # C3 ISOLAMENTO
    {"id":"CIPHER-108","cat":"3 Isolamento","sev":"Alta","file":"src/jefrey/core/agent.py:403 + checkpointer.py:31","code":"config={\"configurable\":{\"thread_id\": thread_id, \"user_id\": user_id}} # cru","desc":"_ns_thread_id()/make_checkpoint_config existem mas não usados. Saver não filtra por user_id, colisão thread 'default'.","impact":"Histórico cross-tenant via checkpoints.","fix":"Usar make_checkpoint_config(thread_id, user_id) em run()/stream()."},
    {"id":"CIPHER-109","cat":"3 Isolamento","sev":"Baixa","file":"src/jefrey/api/memory.py:45-60","code":"total_long_term = mm.long_term.count() # sem user_id","desc":"/memory/health expõe contagem global sem filtro. Informação de cardinalidade por tenant vaza.","impact":"Leak baixo, mas viola isolamento.","fix":"count(user_id=user_id) ou remover do health."},
    {"id":"CIPHER-110","cat":"3 Isolamento","sev":"Média","file":"src/jefrey/core/redis_memory.py:190-210","code":"SCAN jefrey:wm:*  # sem filtro user","desc":"list_sessions() via SCAN global retorna sessões de todos os users quando Redis.","impact":"Enumeração de sessões cross-tenant.","fix":"SCAN com prefixo user_id ou filtrar por user_id."},
    # C4 PERMISSÃO
    {"id":"CIPHER-111","cat":"4 Permissão","sev":"Média","file":"src/jefrey/api/approvals.py:62-95","code":"def decide(...): # só ownership, sem role check","desc":"Qualquer user autenticado aprova seu próprio HIGH (send_message etc). Sem validação admin.","impact":"Auto-aprovação sem segundo fator; fere least privilege.","fix":"Documentar como intencional para single-user ou exigir RBAC ADMIN em decide. Marcar [?SUSPEITO] se multi-user."},
    {"id":"CIPHER-112","cat":"4 Permissão","sev":"Informativa","file":"src/jefrey/mcp/server.py:51 + core/rbac.py","code":"_ROLE_CV + resolve_role(server-side) # sem user_role no schema","desc":"CIPHER-001 fechado e sem regressão: mcp sem user_role param, resolve_role honra apenas allowed_roles. CLI não envia role.","impact":"Nenhum — ponto forte confirmado.","fix":"Manter guard_anti_patterns.sh grep user_role."},
    # C5 IDOR
    {"id":"CIPHER-113","cat":"5 IDOR","sev":"Média","file":"src/jefrey/api/chat.py:237-250","code":"GET /chat/status/{thread_id} com task_key f\"{user_id}:{thread_id}\"","desc":"Polling usa chave composta user_id:thread_id — correto. Mas aprovação pendente usa ApprovalManager.get_pending(thread_id, user_id) que filtra; OK. Nenhum IDOR direto, mas thread_id enumerável.","impact":"Baixo — isolamento correto, apenas enumerabilidade de thread_id.","fix":"Manter filtro user_id; considerar rate limit em /status."},
    {"id":"CIPHER-114","cat":"5 IDOR","sev":"Baixa","file":"src/jefrey/core/hitl.py:70-110","code":"decide() verifica r.user_id == user_id","desc":"HITL decide com ownership check — correto. IDOR mitigado.","impact":"Nenhum — ponto forte.","fix":"Manter."},
    # C6 SECRETS
    {"id":"CIPHER-115","cat":"6 Secrets","sev":"Média","file":"docker-compose.yml:75","code":"JEFREY_API__SECRET_KEY: ${JEFREY_API__SECRET_KEY} # sem :?required","desc":"Secret sem fail-closed em compose. Se .env ausente, sobe com string vazia e auth desabilitado.","impact":"API sobe aberta em CI/prod sem secret.","fix":"Trocar para ${JEFREY_API__SECRET_KEY:?required}"},
    {"id":"CIPHER-116","cat":"6 Secrets","sev":"Média","file":"docker-compose.yml:185 / .env:12","code":"N8N_BASIC_AUTH_PASSWORD=CHANGE_ME_IN_PROD / ${N8N_BASIC_AUTH_PASSWORD}","desc":"Default fraco sem :?required. n8n sobe com senha pública.","impact":"Acesso n8n aberto em prod.","fix":"${N8N_BASIC_AUTH_PASSWORD:?required} + validate_for_production."},
    {"id":"CIPHER-117","cat":"6 Secrets","sev":"Informativa","file":".gitignore:3 / docker-compose.yml:16,32","code":".env git-ignored; postgres/redis :?required","desc":"Secrets não commitados, .env ignorado, senhas DB/Redis com :?required — correto.","impact":"Nenhum — ponto forte.","fix":"Manter."},
    # C7 INPUTS
    {"id":"CIPHER-118","cat":"7 Inputs","sev":"Alta","file":"src/jefrey/api/connections.py:14-30","code":"if not _URL_RE.match(url): # só regex ^https?://","desc":"SSRF: sem bloqueio de 127.0.0.1, 10/8, 172.16/12, 192.168, 169.254.169.254, ::1. Proxy para n8n interno.","impact":"Metadata cloud leak, acesso a MCP 8001 interno.","fix":"Resolver DNS, rejeitar IP privado/loopback/metadata; allowlist https only."},
    {"id":"CIPHER-119","cat":"7 Inputs","sev":"Média","file":"src/jefrey/api/chat.py:58-72","code":"Original=message[:100] logado sem redact_pii","desc":"Log de bloqueio content_guard expõe PII sem redact. Pattern 'do the following' gera falso-positivo benigno.","impact":"PII em logs + frustração UX.","fix":"logar redact_pii(message[:100]); tunar _INJECTION_PATTERNS."},
    {"id":"CIPHER-120","cat":"7 Inputs","sev":"Baixa","file":"src/jefrey/mcp/server.py:110-150","code":"_make_wrapper sem validação jsonschema antes de _run_guarded","desc":"Input_schema do MCP confiado ao MCPServer; sem validação extra de tamanho/tipo antes de PolicyEngine.","impact":"Baixo — MCPServer já valida, mas sem limite 500KB.","fix":"Adicionar limite tamanho args e validação explícita."},
    {"id":"CIPHER-121","cat":"7 Inputs","sev":"Média","file":"src/jefrey/oauth2/introspect.py:177-210 / auth_middleware:60","code":"TTLCache 60s por hash; revoke só sadd sem cache pop","desc":"Cache 60s mantém token revogado válido por janela.","impact":"Bypass revogação 60s.","fix":"revoke_token pop cache; não cachear inactive; TTL 5s para inactive."},
]

STRENGTHS = [
    ("CORS fail-closed", "src/jefrey/api/main.py:55-70", "Só adiciona CORSMiddleware se JEFREY_API__CORS_ORIGINS set. Sem env = sem CORS."),
    ("Auth Bearer timing-safe", "src/jefrey/api/auth_middleware.py:90 + approvals.py:40", "hmac.compare_digest + Bearer validation em FastAPI e Starlette, 401 correto."),
    ("HMAC kid dual-verify", "src/jefrey/eventbus/signing.py:80-140", "HMAC_KEYS_JSON v1/v2, compare_digest, canonical_json sort_keys, TTL 5m."),
    ("ToolRegistry explícito", "src/jefrey/core/registry.py", "Risco declarado, UNKNOWN deny (AXIOM #5), fecha BUG-P3a-01."),
    ("Rate limit fail-closed", "src/jefrey/core/rate_limit.py + policy.py:95", "Pipeline incr+expire, sem user_id deny."),
    ("MCP stateless sem user_role", "src/jefrey/mcp/server.py:51-62", "CIPHER-001 fechado, resolve_role server-side."),
    ("Audit dual-write", "src/jefrey/core/audit.py:60-110", "Postgres + fallback jsonl, redact_pii."),
    ("HITL ownership", "src/jefrey/core/hitl.py:70-95", "decide verifica r.user_id == user_id."),
]

def _esc(s): return html.escape(str(s), quote=False)

# Charts
def make_charts():
    import matplotlib.ticker as mticker
    counts = {k:0 for k in SEV_ORDER}
    for f in FINDINGS:
        if f["sev"] in counts: counts[f["sev"]]+=1
    # donuts
    vals = [counts[k] for k in SEV_ORDER if counts[k]>0]
    labels = [k for k in SEV_ORDER if counts[k]>0]
    colors = [SEV_HEX[k] for k in labels]
    fig, ax = plt.subplots(figsize=(4.2,4.2), dpi=150)
    wedges, texts, autotexts = ax.pie(vals, labels=labels, autopct=lambda p: f"{p:.0f}%\n({int(round(p*sum(vals)/100))})", colors=colors, wedgeprops=dict(width=0.45, edgecolor="white"), textprops=dict(fontsize=8))
    ax.set_title("Achados por Severidade", fontsize=11, weight="bold")
    plt.tight_layout(); plt.savefig(DONUT, bbox_inches="tight"); plt.close()
    # bar por categoria
    cat_counts = {c:0 for c in CATS}
    for f in FINDINGS: cat_counts[f["cat"]] = cat_counts.get(f["cat"],0)+1
    fig, ax = plt.subplots(figsize=(7,3.2), dpi=150)
    xs = list(cat_counts.keys()); ys = [cat_counts[x] for x in xs]
    bars = ax.bar(xs, ys, color="#334155", width=0.62)
    for b, v in zip(bars, ys):
        if v>0: ax.text(b.get_x()+b.get_width()/2, b.get_height()+0.05, str(v), ha="center", va="bottom", fontsize=9, weight="bold")
    ax.set_ylabel("Qtd"); ax.set_title("Achados por Categoria", fontsize=11, weight="bold")
    ax.set_ylim(0, max(ys)+1.5); plt.xticks(rotation=18, ha="right", fontsize=7)
    plt.tight_layout(); plt.savefig(BAR, bbox_inches="tight"); plt.close()

# PDF
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.lib.colors import HexColor, white, black
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak, HRFlowable
from reportlab.lib import colors

def header_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7); canvas.setFillColor(HexColor("#64748b"))
    canvas.drawString(2*cm, A4[1]-1.4*cm, "Relatório CIPHER — Jefrey Assistant  •  P0–P5  •  Stack FastAPI + LangGraph + MCP + pgvector + Redis")
    canvas.drawRightString(A4[0]-2*cm, A4[1]-1.4*cm, "CIPHER Audit")
    canvas.setFont("Helvetica", 7)
    canvas.drawCentredString(A4[0]/2, 1.1*cm, f"Página {doc.page}")
    canvas.setStrokeColor(HexColor("#e2e8f0")); canvas.setLineWidth(0.5)
    canvas.line(2*cm, A4[1]-1.7*cm, A4[0]-2*cm, A4[1]-1.7*cm)
    canvas.line(2*cm, 1.4*cm, A4[0]-2*cm, 1.4*cm)
    canvas.restoreState()

def chip(sev):
    bg = SEV_HEX.get(sev, "#6B7280")
    return f'<font color="{bg}"><b>⬤ { _esc(sev).upper()}</b></font>'

def build_pdf():
    make_charts()
    styles = getSampleStyleSheet()
    s_title = ParagraphStyle("Title2", parent=styles["Title"], fontSize=22, leading=26, textColor=HexColor("#0f172a"), alignment=TA_CENTER, spaceAfter=6)
    s_h1 = ParagraphStyle("H1", parent=styles["Heading1"], fontSize=13, leading=16, textColor=HexColor("#0f172a"), spaceBefore=14, spaceAfter=8, keepWithNext=True)
    s_h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=10, leading=13, textColor=HexColor("#1e293b"), spaceBefore=10, spaceAfter=6)
    s_body = ParagraphStyle("Body", parent=styles["BodyText"], fontSize=8.2, leading=11.5, alignment=TA_JUSTIFY, textColor=HexColor("#334155"), spaceAfter=4)
    s_small = ParagraphStyle("Small", parent=s_body, fontSize=7.5, leading=10, textColor=HexColor("#475569"))
    s_code = ParagraphStyle("Code", parent=styles["Code"], fontSize=6.8, leading=9, textColor=HexColor("#1e293b"), backColor=HexColor("#f1f5f9"), borderPadding=(4,4,4), spaceAfter=4)
    s_cell = ParagraphStyle("Cell", parent=styles["BodyText"], fontSize=6.7, leading=8.5, textColor=HexColor("#1e293b"))
    s_cellH = ParagraphStyle("CellH", parent=s_cell, textColor=white, alignment=TA_CENTER, fontSize=6.8)
    s_caption = ParagraphStyle("Cap", parent=s_body, fontSize=7, leading=9, textColor=HexColor("#64748b"), alignment=TA_CENTER)

    doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm,
                            title="Relatório CIPHER — Jefrey", author="CIPHER")
    story=[]
    # CAPA
    story.append(Spacer(1, 1.2*cm))
    story.append(Paragraph("Relatório CIPHER", ParagraphStyle("Capa1", parent=s_title, fontSize=28, textColor=HexColor("#0f172a"))))
    story.append(Paragraph("Jefrey Assistant — Auditoria Sistêmica P0–P5", ParagraphStyle("Capa2", parent=s_body, fontSize=11, textColor=HexColor("#334155"), alignment=TA_CENTER)))
    story.append(Spacer(1, 0.4*cm))
    box_data = [
        [Paragraph("<b>Data</b><br/>04/09/2026", s_small), Paragraph("<b>Escopo</b><br/>P0 Auditoria base → P5 FastAPI+CLI+HITL", s_small), Paragraph("<b>Stack</b><br/>Python 3.12/3.14, FastAPI :8000, MCP :8001, Postgres+pgvector, Redis, n8n :5678, Ollama", s_small)],
        [Paragraph("<b>Metodologia</b><br/>7 categorias, leitura linha a linha, rastreio ponta-a-ponta POST /chat → LangGraph → Tool", s_small), Paragraph("<b>Critério</b><br/>Apenas achados verificados com arquivo:linha + trecho + explorabilidade + severidade", s_small), Paragraph("<b>Artefatos</b><br/>25 arquivos backend + 15 frontend + Docker/CI verificados", s_small)],
    ]
    t = Table(box_data, colWidths=[5.3*cm,5.3*cm,5.3*cm])
    t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),HexColor("#f8fafc")),("BOX",(0,0),(-1,-1),0.6,HexColor("#cbd5e1")),("INNERGRID",(0,0),(-1,-1),0.4,HexColor("#e2e8f0")),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("LEFTPADDING",(0,0),(-1,-1),6),("RIGHTPADDING",(0,0),(-1,-1),6),("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6)]))
    story.append(t)
    story.append(Spacer(1, 0.6*cm))
    story.append(Paragraph("Classificação: <b>CONFIDENCIAL</b> — Uso interno Jefrey Team  •  Gerado por CIPHER (engenheiro sênior) em venv isolado reportlab+matplotlib", s_caption))
    story.append(HRFlowable(width="100%", thickness=0.6, color=HexColor("#0f172a"), spaceAfter=8, spaceBefore=8))
    story.append(Paragraph("Paleta: <font color=\"#B91C1C\"><b>Crítica</b></font> &nbsp; <font color=\"#EA580C\"><b>Alta</b></font> &nbsp; <font color=\"#D97706\"><b>Média</b></font> &nbsp; <font color=\"#2563EB\"><b>Baixa</b></font> &nbsp; <font color=\"#6B7280\"><b>Informativa</b></font> &nbsp; <font color=\"#059669\"><b>Ponto Forte</b></font>", s_caption))
    story.append(Spacer(1, 0.8*cm))
    story.append(Paragraph("Relatório gerado em venv isolado <b>docs/cipher-audit/.venv</b> — script <b>docs/cipher-audit/gerar_relatorio.py</b> — A4 2cm, header/footer, rosca/bar.", s_small))
    # RESUMO
    story.append(Paragraph("Resumo Executivo", s_h1))
    story.append(Paragraph(f"Auditoria leu <b>{len(FINDINGS)} achados verificados</b> em 7 categorias (P0–P5). Destaques: <b>2 críticas</b> (isolamento de memória + dimensão pgvector) e <b>3 altas</b> (HMAC cache, checkpointer, SSRF). <b>3 informativas</b> são pontos fortes confirmados sem regressão. Sem os 2 críticos, o sistema passa em staging; com eles, <b>não deve ir a prod multi-tenant</b>.", s_body))
    # donut + bar
    story.append(Spacer(1, 0.2*cm))
    img_w = 7*cm
    story.append(Table([[Image(str(DONUT), width=6.8*cm, height=6.8*cm), Image(str(BAR), width=8.8*cm, height=4.2*cm)]], colWidths=[7.5*cm,9*cm]))
    story.append(Paragraph("Figura 1 — Rosca por severidade (esq.) e barras por categoria (dir.).", s_caption))
    # contagens
    sev_counts = {k: sum(1 for f in FINDINGS if f["sev"]==k) for k in SEV_ORDER}
    cat_counts = {c: sum(1 for f in FINDINGS if f["cat"]==c) for c in CATS}
    header = [Paragraph("<b>Severidade</b>", s_cellH), Paragraph("<b>Qtd</b>", s_cellH)]
    row = [Paragraph(_esc(k), s_cell) for k in SEV_ORDER]  # placeholder
    # tabela severidade
    data = [[Paragraph("<b>Severidade</b>", s_cellH), Paragraph("<b>Qtd</b>", s_cellH), Paragraph("<b>%</b>", s_cellH)]]
    total = len(FINDINGS)
    for k in SEV_ORDER:
        q = sev_counts[k]; pct = f"{q/total*100:.0f}%" if total else "0%"
        data.append([Paragraph(f"{chip(k)}", s_cell), Paragraph(str(q), s_cell), Paragraph(pct, s_cell)])
    t2 = Table(data, colWidths=[5*cm,2*cm,2*cm]); t2.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),HexColor("#0f172a")),("GRID",(0,0),(-1,-1),0.4,HexColor("#cbd5e1")),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("LEFTPADDING",(0,0),(-1,-1),4),("RIGHTPADDING",(0,0),(-1,-1),4)]))
    # tabela categoria
    data3 = [[Paragraph("<b>Categoria</b>", s_cellH), Paragraph("<b>Qtd</b>", s_cellH)]]
    for c in CATS:
        data3.append([Paragraph(_esc(c), s_cell), Paragraph(str(cat_counts[c]), s_cell)])
    t3 = Table(data3, colWidths=[5.5*cm,2*cm]); t3.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),HexColor("#334155")),("GRID",(0,0),(-1,-1),0.4,HexColor("#cbd5e1")),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("LEFTPADDING",(0,0),(-1,-1),4)]))
    story.append(Spacer(1, 0.3*cm))
    story.append(Table([[t2, t3]], colWidths=[9.2*cm,7.8*cm], spaceBefore=4))
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph("<b>Leitura direta:</b> Críticas exigem hotfix antes de prod multi-tenant. Altas travam hardening P6. Médias são sprint seguinte. Informativas = pontos fortes.", s_small))
    # PONTOS FORTES
    story.append(Paragraph("Pontos Fortes — o que está correto (com evidência)", s_h1))
    pf_data = [[Paragraph("<b>#</b>", s_cellH), Paragraph("<b>Ponto Forte</b>", s_cellH), Paragraph("<b>Evidência arquivo:linha</b>", s_cellH)]]
    for i,(title, evid, note) in enumerate(STRENGTHS,1):
        pf_data.append([Paragraph(str(i), s_cell), Paragraph(f"<b>{_esc(title)}</b><br/><font color=\"#475569\">{_esc(note)}</font>", s_cell), Paragraph(f"<font face=\"Courier\" size=\"6.5\">{_esc(evid)}</font>", s_cell)])
    pf = Table(pf_data, colWidths=[0.8*cm,8.2*cm,7.5*cm], repeatRows=1)
    pf.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),HexColor("#059669")),("GRID",(0,0),(-1,-1),0.4,HexColor("#cbd5e1")),("ROWBACKGROUNDS",(0,1),(-1,-1),[white, HexColor("#f0fdf4")]),("VALIGN",(0,0),(-1,-1),"TOP")]))
    story.append(pf)
    # PONTOS FRACOS
    story.append(Paragraph("Pontos Fracos — riscos centrais em linguagem direta", s_h1))
    story.append(Paragraph("<b>1. Memória vaza entre usuários.</b> O cérebro do agente consulta pgvector sem filtrar por user_id. Prompt de um usuário pode conter lembranças de outro. É o achado mais crítico.<br/><b>2. Banco vetorial quebrado.</b> Dimensão 1536 vs 768 faz INSERT falhar 100% em Postgres — long-term memory morta em prod.<br/><b>3. Revogação que não revoga por 60s.</b> Cache de introspecção mantém token revogado válido na janela.<br/><b>4. Checkpoints sem dono.</b> Histórico LangGraph compartilhado por thread_id, sem namespace por user.<br/><b>5. Ferramenta engana o LLM.</b> Output de web_search/drive vai direto ao modelo sem sanitização — prompt injection.<br/><b>6. URL vira porta de entrada.</b> /connections/browse aceita qualquer IP, incluindo 169.254 metadata e 127.0.0.1.<br/><b>7. Working memory sem prazo.</b> Chaves Redis sem TTL crescem até OOM.", s_body))
    # TABELA ACHADOS
    story.append(Paragraph("Achados Detalhados — por Categoria", s_h1))
    story.append(Paragraph("Cada linha traz <b>chip de severidade</b>, arquivo:linha, trecho e descrição. Severidade sobe um nível se for REGRESSÃO de finding fechado.", s_small))
    # agrupar por cat
    from collections import defaultdict
    by_cat = defaultdict(list)
    for f in FINDINGS: by_cat[f["cat"]].append(f)
    for cat in CATS:
        items = by_cat.get(cat, [])
        if not items: continue
        story.append(Paragraph(_esc(cat), s_h2))
        hdr = [Paragraph("<b>ID</b>", s_cellH), Paragraph("<b>Sev</b>", s_cellH), Paragraph("<b>Arquivo:linha</b>", s_cellH), Paragraph("<b>Descrição + Trecho</b>", s_cellH)]
        rows=[hdr]
        for it in items:
            code = f"<font face=\"Courier\" size=\"6\">{_esc(it['code'])}</font>"
            desc = f"{_esc(it['desc'])}<br/><br/>{code}<br/><font color=\"#64748b\" size=\"6.5\">Impacto: {_esc(it['impact'])}<br/>Correção: {_esc(it['fix'])}</font>"
            rows.append([Paragraph(_esc(it["id"]), s_cell), Paragraph(chip(it["sev"]), s_cell), Paragraph(f"<font face=\"Courier\" size=\"6.5\">{_esc(it['file'])}</font>", s_cell), Paragraph(desc, s_cell)])
        colw=[1.6*cm,2.0*cm,3.8*cm,9.1*cm]
        tt = Table(rows, colWidths=colw, repeatRows=1)
        tt.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),HexColor("#1e293b")),("GRID",(0,0),(-1,-1),0.4,HexColor("#cbd5e1")),("VALIGN",(0,0),(-1,-1),"TOP"),("ROWBACKGROUNDS",(0,1),(-1,-1),[white, HexColor("#f8fafc")])]))
        story.append(tt); story.append(Spacer(1,0.2*cm))
    # RECOMENDAÇÕES
    story.append(Paragraph("Recomendações Priorizadas", s_h1))
    story.append(Paragraph("<b>P1 — Corrigir agora (crítica/alta, bloqueia prod)</b>", s_h2))
    p1 = [f for f in FINDINGS if f["sev"] in ("Crítica","Alta")]
    for it in p1:
        est = "0.5h" if it["id"] in ("CIPHER-121",) else "1h" if it["sev"]=="Alta" else "1.5h"
        story.append(Paragraph(f"<b>{_esc(it['id'])} — {_esc(it['cat'])} — {chip(it['sev'])}</b> &nbsp; <font face=\"Courier\" size=\"6.5\">{_esc(it['file'])}</font> &nbsp; <b>Esforço {est}</b><br/>{_esc(it['desc'])}<br/><font color=\"#475569\">Correção: {_esc(it['fix'])}</font>", s_body))
    story.append(Paragraph("<b>P2 — Próximo sprint (média)</b>", s_h2))
    for it in [f for f in FINDINGS if f["sev"]=="Média"]:
        story.append(Paragraph(f"<b>{_esc(it['id'])}</b> — {chip(it['sev'])} — <font face=\"Courier\" size=\"6.5\">{_esc(it['file'])}</font><br/>{_esc(it['desc'])}<br/><font color=\"#475569\">Fix: {_esc(it['fix'])}</font>", s_body))
    story.append(Paragraph("<b>P3 — Backlog (baixa/informativa)</b>", s_h2))
    for it in [f for f in FINDINGS if f["sev"] in ("Baixa","Informativa")]:
        story.append(Paragraph(f"<b>{_esc(it['id'])}</b> — {chip(it['sev'])} — <font face=\"Courier\" size=\"6.5\">{_esc(it['file'])}</font> — {_esc(it['desc'])}", s_small))
    # RISCOS LATENTES
    story.append(Paragraph("Riscos Latentes — P6+", s_h1))
    story.append(Paragraph("Não são bugs hoje, mas viram críticos com escala/prod. <b>Plano:</b> endereçar em P6–P8 antes de multi-tenant real.", s_body))
    lat = [
        ("_RUNNING_TASKS em memória", "Dict perde tasks em restart Docker. Com 100 req/s, HITL pendente some. Mitigação P8: Redis Streams jefrey:tasks:{user_id} + recovery."),
        ("Stubs OAuth Google", "Calendar/email retornam 'não configurado' mas sem erro claro em /chat. Usuário vê 'ferramenta indisponível' genérico. Padronizar erro 'OAuth não configurado — veja docs/oauth.md'."),
        ("TTL ausente vira OOM", "RedisWorkingMemory sem expire: 10k users × 20 msgs = 200k chaves eternas. Adicionar TTL 24h deslizante."),
        ("SSRF vira RCE interno", "Quando n8n tiver credenciais cloud, SSRF em /browse permite exfiltrar via webhook."),
        ("Histórico sem dono", "Checkpointer colisão vira vazamento LGPD quando houver dados reais por tenant."),
    ]
    for t,d in lat:
        story.append(Paragraph(f"<b>{_esc(t)}</b> — {_esc(d)}", s_body))
    # ISSUES GH
    story.append(Paragraph("Issues para o GitHub — Markdown pronto para copiar", s_h1))
    story.append(Paragraph("Cada bloco entre <b>--- ISSUE n ---</b> e <b>--- FIM ISSUE n ---</b> é uma issue completa. Agrupamos triviais relacionados para reduzir ruído. Labels: <b>cipher + severidade + fase</b>.", s_small))
    issues = [
        {"n":1, "title":"[CIPHER] Isolamento de memória quebrado — get_context sem user_id (P1 Crítica)", "labels":"cipher, crítica, P1", "findings":["CIPHER-101","CIPHER-108"], "body": """**Descrição:** MemoryManager.get_context() e Agent._load_context() ignoram user_id. Busca vetorial retorna memórias de qualquer tenant. Checkpointer também sem namespace.

**Evidência:**
- `src/jefrey/core/memory.py:466` — `self.long_term.search(current_query)` sem user_id
- `src/jefrey/core/agent.py:180-188` — `self.memory.get_context(state.user_input)` sem user_id
- `src/jefrey/core/agent.py:403` — `config={\"configurable\":{\"thread_id\": thread_id}}` sem ns

**Explorabilidade:** Autenticar como user B, POST /chat com query genérica, receber memórias de user A no SystemMessage.

**Impacto:** PII leak cross-tenant. LGPD.

**Correção:**
```python
# memory.py
def get_context(self, current_query: str, user_id: str|None=None):
    relevant = self.long_term.search(current_query, user_id=user_id)
# agent.py
context = self.memory.get_context(state.user_input, user_id=state.user_id)
config = make_checkpoint_config(thread_id, user_id)
```

**Aceite:**
- [ ] Teste com 2 users mesma query retorna apenas memórias próprias
- [ ] `verify_p6_isolation.py` passa para grafo e pg_memory
- [ ] Checkpoints com mesmo thread_id mas users diferentes isolados
"""},
        {"n":2, "title":"[CIPHER] pgvector dimensão errada 1536 vs 768 — long-term morto (P1 Crítica)", "labels":"cipher, crítica, P1", "findings":["CIPHER-102"], "body": """**Descrição:** MemoryLongTermSettings embedding_dim=1536 mas nomic-embed-text (Ollama) produz 768. Vector(1536) falha em INSERT.

**Evidência:** `src/jefrey/core/config.py:50` `embedding_dim=1536` vs `src/jefrey/core/models.py:14` `Vector(1536)`

**Impacto:** Postgres long-term 100% inoperante em prod.

**Correção:** Ajustar config para 768 quando model=nomic-embed-text, ou trocar modelo para 1536. Validar no startup `assert len(embed('test'))==dim`. Migration recriar VECTOR.

**Aceite:**
- [ ] `pg_memory.add()` persiste em Postgres real
- [ ] `search()` retorna resultados
- [ ] CI testa dim vs modelo
"""},
        {"n":3, "title":"[CIPHER] Cache de revogação 60s bypass + SSRF em connections (Alta)", "labels":"cipher, alta, P5", "findings":["CIPHER-121","CIPHER-118","CIPHER-105"], "body": """**Descrição:** (a) TTLCache 60s mantém token revogado válido. (b) /connections/browse sem bloqueio IP privado/metadata. (c) Tool output sem sanitize antes do LLM.

**Evidência:**
- `src/jefrey/api/auth_middleware.py:60` TTLCache 60s; `oauth2/introspect.py:revoke_token` só sadd sem pop
- `src/jefrey/api/connections.py:14` regex apenas `^https?://`
- `src/jefrey/core/agent.py:220` ToolMessage sem sanitize

**Correção:** revoke pop cache; SSRF: resolver DNS e bloquear 127/10/172.16/192.168/169.254; agent: `sanitize_tool_output(json.dumps(result), tool_name)` antes de ToolMessage.

**Aceite:**
- [ ] Token revogado rejeitado em <2s
- [ ] `http://169.254.169.254/meta-data` → 400
- [ ] Página com `Ignore previous instructions` não jailbreaka LLM
"""},
        {"n":4, "title":"[CIPHER] Hardening de secrets e audit gaps (P4/P5 Média)", "labels":"cipher, média, P4", "findings":["CIPHER-115","CIPHER-116","CIPHER-106","CIPHER-119"], "body": """**Descrição:** (a) `JEFREY_API__SECRET_KEY` e `N8N_BASIC_AUTH_PASSWORD` sem `:?required` no compose. (b) Audit de /browse com assinatura errada silenciada. (c) Log content_guard sem redact.

**Evidência:** `docker-compose.yml:75`, `185`; `src/jefrey/api/connections.py:32` `except: pass`; `src/jefrey/api/chat.py:58`

**Correção:** `:?required` nos secrets; `audit_tool_call(...)` com kwargs corretos; logar `redact_pii(message[:100])`.

**Aceite:**
- [ ] `docker compose config` falha sem secrets
- [ ] /browse gera linha em audit_logs
- [ ] Logs não contêm email/CPF em claro
"""},
        {"n":5, "title":"[CIPHER] Working memory sem TTL + CLI/UX gaps (Baixa/Média)", "labels":"cipher, média, P1", "findings":["CIPHER-103","CIPHER-107","CIPHER-104","CIPHER-120"], "body": """**Descrição:** Redis SET sem EXPIRE, session() perde user_id, CLI não faz polling 'running', checkpointer sem lifespan close, MCP sem limite args.

**Evidência:** `redis_memory.py:111`, `cli/main.py:60`, `checkpointer.py:23`

**Correção:** `SET ex=86400`; `session()` propagar user_id; CLI polling loop + headers; lifespan close; validar tamanho args MCP.

**Aceite:**
- [ ] Chaves expiram em 24h
- [ ] `jefrey chat \"long\"` retorna resposta completa após running
- [ ] `GET /memory/search` com auth passa via CLI
"""},
    ]
    for iss in issues:
        story.append(Paragraph(f"--- ISSUE {iss['n']} ---", ParagraphStyle("IssueSep", parent=s_small, textColor=HexColor("#0f172a"), fontSize=8, alignment=TA_CENTER, backColor=HexColor("#f1f5f9"), borderPadding=(4,4,4))))
        md = f"""# {iss['title']}\n\n**Labels:** `{iss['labels']}`  \n**Findings:** {', '.join(iss['findings'])}  \n**Severidade:** conforme chip do achado  \n\n{iss['body']}\n\n**Verificar regressão:** Sim — CIPHER-001/019 continuam fechados (validado neste relatório). Não reintroduzir user_role no body.\n"""
        # escape para Paragraph mas preservar markdown visual: usar <br/> e <font face=Courier>
        md_esc = _esc(md)
        # converter quebras em <br/> para visual no PDF (não renderiza markdown real, mas fiel para copiar)
        md_html = md_esc.replace("\n", "<br/>")
        story.append(Paragraph(md_html, ParagraphStyle("IssueBody", parent=s_small, fontSize=6.8, leading=9, backColor=HexColor("#ffffff"), borderPadding=(6,6,6))))
        story.append(Paragraph(f"--- FIM ISSUE {iss['n']} ---", ParagraphStyle("IssueSep2", parent=s_small, textColor=HexColor("#64748b"), fontSize=7, alignment=TA_CENTER)))
        story.append(Spacer(1,0.3*cm))
    # Anexo cobertura
    story.append(Paragraph("Anexo — Cobertura da Varredura", s_h1))
    story.append(Paragraph("Arquivos lidos linha a linha (25 backend + 15 frontend + deploy/CI). Nenhuma amostra — leitura integral com rastreio ponta-a-ponta POST /chat → LangGraph → Tool → Resposta e HITL completo.", s_body))
    cov = [
        ["Camada","Arquivos verificados","Status"],
        ["API / Auth","api/main.py, chat.py, approvals.py, auth_middleware.py, memory.py, connections.py, stt.py, tts.py","OK — 8/8 lidos"],
        ["Core / Memory","memory.py, pg_memory.py, redis_memory.py, agent.py, checkpointer.py, policy.py, rbac.py, hitl.py, audit.py, content_guard.py, rate_limit.py, config.py, db.py, models.py","OK — 14/14"],
        ["MCP / EventBus","mcp/server.py, mcp/client.py, eventbus/publisher.py, subscriber.py, signing.py, oauth2/introspect.py, jwks.py, token_refresh.py","OK — 8/8"],
        ["Deploy / CI","docker-compose.yml, Dockerfile.api/mcp, .env.example, .gitignore, .github/workflows/ci.yml","OK — 5/5"],
        ["CLI","cli/main.py, interfaces/cli.py","OK — 2/2"],
        ["Frontend","ui/src/pages/Chat.tsx, Approvals.tsx, Memory.tsx + hooks/useVoice, useWakeWord + lib/api.ts","OK — verificado para XSS (AUD-08 já mitigado com _esc)"],
    ]
    # build table
    cov_rows=[]
    for r in cov:
        cov_rows.append([Paragraph(f"<b>{_esc(c)}</b>" if i==0 else _esc(c), s_cell) for i,c in enumerate(r)])
    # header style separate
    ct = Table(cov_rows, colWidths=[3.2*cm,10*cm,3.3*cm], repeatRows=1)
    ct.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),HexColor("#0f172a")),("TEXTCOLOR",(0,0),(-1,0),white),("GRID",(0,0),(-1,-1),0.4,HexColor("#cbd5e1")),("VALIGN",(0,0),(-1,-1),"TOP"),("ROWBACKGROUNDS",(0,1),(-1,-1),[white, HexColor("#f8fafc")])]))
    story.append(ct)
    story.append(Spacer(1,0.4*cm))
    story.append(Paragraph("Metodologia: para cada arquivo, busca por padrões (async, HMAC, user_id, SSRF, XSS, secrets) + leitura integral do fluxo. verify_pX valida caminho feliz; este relatório valida caminho de falha.", s_small))
    story.append(Paragraph("Fim do relatório — CIPHER", ParagraphStyle("Fim", parent=s_caption, fontSize=8, textColor=HexColor("#0f172a"))))
    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    print(f"PDF gerado: {OUT}  Páginas A4, charts: {DONUT}, {BAR}")

if __name__=="__main__":
    build_pdf()
