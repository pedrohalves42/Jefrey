"""
Gerador de Relatório CIPHER — Jefrey Assistant
Gera PDF profissional com findings de segurança.
"""
import os
import sys
from datetime import datetime

# Ensure venv packages available
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm, mm
    from reportlab.lib.colors import HexColor, white, black
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        PageBreak, Image, KeepTogether
    )
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
except ImportError:
    print("Installing reportlab...")
    os.system(f"{sys.executable} -m pip install reportlab matplotlib -q")
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm, mm
    from reportlab.lib.colors import HexColor, white, black
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        PageBreak, Image, KeepTogether
    )
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
except ImportError:
    os.system(f"{sys.executable} -m pip install matplotlib -q")
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches

# === Colors ===
C_CRITICA = HexColor("#B91C1C")
C_ALTA = HexColor("#EA580C")
C_MEDIA = HexColor("#D97706")
C_BAIXA = HexColor("#2563EB")
C_INFO = HexColor("#6B7280")
C_FORTE = HexColor("#059669")
C_BG_DARK = HexColor("#0F172A")
C_PRIMARY = HexColor("#06B6D4")

# === Styles ===
styles = getSampleStyleSheet()

style_title = ParagraphStyle('Title2', parent=styles['Title'], fontSize=28, textColor=C_BG_DARK, spaceAfter=6)
style_subtitle = ParagraphStyle('Subtitle2', parent=styles['Normal'], fontSize=12, textColor=HexColor("#64748B"), spaceAfter=20)
style_h1 = ParagraphStyle('H1', parent=styles['Heading1'], fontSize=18, textColor=C_BG_DARK, spaceAfter=10, spaceBefore=20)
style_h2 = ParagraphStyle('H2', parent=styles['Heading2'], fontSize=14, textColor=HexColor("#1E293B"), spaceAfter=8, spaceBefore=12)
style_body = ParagraphStyle('Body2', parent=styles['Normal'], fontSize=10, leading=14, alignment=TA_JUSTIFY, spaceAfter=6)
style_code = ParagraphStyle('Code', parent=styles['Normal'], fontSize=8, fontName='Courier', leading=10, backColor=HexColor("#F1F5F9"), spaceAfter=4)
style_strong = ParagraphStyle('Strong', parent=style_body, fontName='Helvetica-Bold')

# === Data ===
FINDINGS = [
    {"id": "CRIT-01", "cat": "C1-Bugs", "sev": "CRITICA", "file": "agent.py:23-60", "desc": "TRIPLE AgentState class definition — 3 classes from failed edits. Last __setattr__ conflicts with __init__, state.user_id returns '' always. Chat endpoint ALWAYS 500.", "code": "class AgentState(Dict[str, Any]):  # defined 3x"},
    {"id": "CRIT-02", "cat": "C2-Logica", "sev": "CRITICA", "file": "agent.py:run()", "desc": "Agent.run() bypasses ALL governance: direct httpx POST to Ollama. RBAC, PolicyEngine, HITL, content_guard, AuditLogger are DEAD CODE. No tool ever invoked.", "code": "async with httpx.AsyncClient() as client: resp = await client.post(base_url + '/api/chat', ...)"},
    {"id": "CRIT-03", "cat": "C1-Bugs", "sev": "ALTA", "file": "chat.py:175,262", "desc": "resume_chat and get_chat_status return raw dict (task.result()) instead of extracting response string. Client gets nested dict.", "code": "return {'status': 'complete', 'response': response, ...}  # response is dict"},
    {"id": "CRIT-04", "cat": "C1-Bugs", "sev": "ALTA", "file": "stt.py:35-45", "desc": "Calls PolicyEngine.decide() which DOES NOT EXIST (class has evaluate()). Always raises AttributeError -> 500.", "code": "dec = pe.decide('stt_transcribe', args={}, ctx=ctx)"},
    {"id": "CRIT-05", "cat": "C1-Bugs", "sev": "ALTA", "file": "tts.py:35-45", "desc": "Same PolicyEngine.decide() API mismatch. TTS POST always 500.", "code": "dec = pe.decide('tts_synthesize', args=..., ctx=ctx)"},
    {"id": "CRIT-06", "cat": "C1-Bugs", "sev": "ALTA", "file": "memory.py:175", "desc": "health_check() defined AFTER return statement in get_memory_manager(). Dead code.", "code": "return MemoryManager(...)\\ndef health_check(self) -> dict: ...  # unreachable"},
    {"id": "HIGH-01", "cat": "C1-Bugs", "sev": "ALTA", "file": "memory_api.py:45-65", "desc": "References mm.long_term.search(), mm.long_term.count(), mm.short_term.get_messages() — methods that DON'T EXIST on the actual classes.", "code": "results = mm.long_term.search(q, top_k=limit, user_id=user_id)"},
    {"id": "HIGH-02", "cat": "C1-Bugs", "sev": "ALTA", "file": "pg_memory.py:55", "desc": "_embed() called in add() but NEVER DEFINED. Memory add always crashes with AttributeError.", "code": "embedding = self._embed(content)  # _embed not defined"},
    {"id": "HIGH-03", "cat": "C2-Logica", "sev": "ALTA", "file": "pg_memory.py:85", "desc": "search() uses ORDER BY importance DESC instead of pgvector cosine similarity. Returns random memories sorted by score, not relevant ones.", "code": ".order_by(LongTermMemory.importance.desc()).limit(top_k)"},
    {"id": "HIGH-04", "cat": "C2-Logica", "sev": "ALTA", "file": "rate_limit.py", "desc": "Redis URL from config.dsn lacks password. Redis requires auth. ALL rate limit checks fail -> RuntimeError -> fail-closed deny -> ALL tools blocked.", "code": "redis_url = get_settings().redis.dsn  # no password in URL"},
    {"id": "HIGH-05", "cat": "C3-Isolamento", "sev": "ALTA", "file": "skills/*.py", "desc": "Only notes.py propagates user_id. All other skills (automation, calendar, drive, email, web_search) have NO user_id in function signatures.", "code": "def create_event(self, summary: str, ...):  # no user_id param"},
    {"id": "HIGH-06", "cat": "C4-Permissao", "sev": "ALTA", "file": "approvals.py:decide()", "desc": "Any authenticated user can approve HIGH/CRITICAL tools. CIPHER-111 only logs warning, does NOT block.", "code": "logger.warning('CIPHER-111: auto-approval...')  # warning only"},
    {"id": "MED-01", "cat": "C2-Logica", "sev": "MEDIA", "file": "chat.py:35", "desc": "_RUNNING_TASKS is in-memory dict. Lost on Docker restart. Clients see 'idle' for running tasks.", "code": "_RUNNING_TASKS: Dict[str, asyncio.Task] = {}"},
    {"id": "MED-02", "cat": "C5-IDOR", "sev": "ALTA", "file": "approvals.py:55", "desc": "_UserContextMiddleware trusts X-User-Id header without server validation. Any client can impersonate users.", "code": "request.state.user_id = request.headers.get('X-User-Id', _DEFAULT_USER)"},
    {"id": "MED-03", "cat": "C6-Secrets", "sev": "MEDIA", "file": "signing.py", "desc": "Dev mode uses weak fallback HMAC key. If JEFREY_ENV misconfigured in prod, events use weak signing.", "code": "if os.getenv('JEFREY_ENV') == 'prod': raise RuntimeError(...)"},
    {"id": "MED-04", "cat": "C7-Inputs", "sev": "MEDIA", "file": "agent.py:run()", "desc": "LLM output NOT sanitized by content_guard. If tool output contains injection, it passes to LLM unsanitized.", "code": "response_text = data.get('message', {}).get('content', '')  # used directly"},
    {"id": "MED-05", "cat": "C7-Inputs", "sev": "MEDIA", "file": "connections.py:_is_blocked_url()", "desc": "SSRF blocking misses: 0.0.0.0, DNS rebinding, some IPv6 variants.", "code": "_BLOCKED_HOSTS = ('127.', '10.', '172.', ...)"},
    {"id": "MED-06", "cat": "C2-Logica", "sev": "MEDIA", "file": "hitl.py:decide()", "desc": "No SELECT FOR UPDATE on approve. Race condition: two concurrent approves both see 'pending'.", "code": "r = s.get(Approval, uuid.UUID(approval_id))  # no lock"},
    {"id": "MED-07", "cat": "C1-Bugs", "sev": "ALTA", "file": "cli/main.py:memory", "desc": "CLI memory search sends Bearer token but no X-User-Id. Middleware sets user_id='anonymous'. 0 results.", "code": "headers = get_auth_headers()  # no X-User-Id"},
    {"id": "MED-08", "cat": "C3-Isolamento", "sev": "MEDIA", "file": "checkpointer.py", "desc": "LangGraph checkpoints use thread_id without user_id namespace. Thread_id collision shares state.", "code": "AsyncPostgresSaver(thread_id=thread_id)  # no user_id prefix"},
    {"id": "LOW-01", "cat": "C1-Bugs", "sev": "BAIXA", "file": "auth_mw.py:100-105", "desc": "Dead code after exception block — unreachable logger.warning and return.", "code": "logger.warning('OAuth2 validation failed...')  # unreachable"},
    {"id": "LOW-02", "cat": "C1-Bugs", "sev": "INFORMATIVA", "file": "config.py:25", "desc": "LLM base_url strips /v1 suffix. Breaks vLLM/LiteLLM endpoints.", "code": "@field_validator('base_url') ... v = v[:-3]  # strips /v1"},
    {"id": "LOW-03", "cat": "C3-Isolamento", "sev": "MEDIA", "file": "memory_api.py:60", "desc": "memory/health returns global count when user_id=None (system path). Info leak.", "code": "mm.long_term.count(user_id=user_id) if user_id else mm.long_term.count()"},
]

STRENGTHS = [
    ("PF-01", "Timing-safe token comparison", "auth_middleware.py:80", "hmac.compare_digest() prevents timing attacks"),
    ("PF-02", "Audit dual-write fallback", "audit.py:_write_fallback", "Dual-write when Postgres unavailable"),
    ("PF-03", "Dev-token blocked in prod", "auth.py:is_prod", "CIPHER-021 enforced correctly"),
    ("PF-04", "Rate limiting fail-closed", "rate_limit.py", "Redis down = deny, never allow"),
    ("PF-05", "Content guard 30+ patterns", "content_guard.py", "Comprehensive injection prevention"),
    ("PF-06", "CORS fail-closed", "main.py", "No env var = no CORS middleware"),
    ("PF-07", "Memory user_id isolation", "memory.py", "All methods filter by user_id"),
    ("PF-08", "DB session lifecycle", "db.py:get_db()", "Proper rollback/close pattern"),
    ("PF-09", "Approval auto-expiry", "hitl.py:expire_due()", "Automatic expiry mechanism"),
    ("PF-10", "No raw SQL", "All models.py", "SQLAlchemy ORM only"),
]

def make_severity_badge(sev):
    colors = {"CRITICA": "#B91C1C", "ALTA": "#EA580C", "MEDIA": "#D97706", "BAIXA": "#2563EB", "INFORMATIVA": "#6B7280"}
    return f'<font color="{colors.get(sev, "#000")}"><b>[{sev}]</b></font>'

def generate_chart_severity(output_path):
    counts = {"CRITICA": 0, "ALTA": 0, "MEDIA": 0, "BAIXA": 0, "INFORMATIVA": 0}
    for f in FINDINGS:
        counts[f["sev"]] = counts.get(f["sev"], 0) + 1
    
    labels = [k for k, v in counts.items() if v > 0]
    sizes = [v for v in counts.values() if v > 0]
    colors_hex = ["#B91C1C", "#EA580C", "#D97706", "#2563EB", "#6B7280"][:len(labels)]
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))
    
    # Donut chart
    wedges, texts, autotexts = ax1.pie(sizes, labels=labels, colors=colors_hex, autopct='%1.0f%%',
                                        startangle=90, pctdistance=0.75, textprops={'fontsize': 9})
    centre_circle = plt.Circle((0,0), 0.50, fc='white')
    ax1.add_artist(centre_circle)
    ax1.set_title('Achados por Severidade', fontsize=12, fontweight='bold')
    
    # Bar chart by category
    cats = {}
    for f in FINDINGS:
        c = f["cat"].split("-")[0]
        cats[c] = cats.get(c, 0) + 1
    cat_labels = list(cats.keys())
    cat_sizes = list(cats.values())
    cat_colors = ["#06B6D4", "#8B5CF6", "#10B981", "#F59E0B", "#EF4444", "#EC4899", "#6366F1"][:len(cat_labels)]
    
    bars = ax2.barh(cat_labels, cat_sizes, color=cat_colors)
    ax2.set_xlabel('Achados')
    ax2.set_title('Achados por Categoria', fontsize=12, fontweight='bold')
    for bar, val in zip(bars, cat_sizes):
        ax2.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height()/2, str(val), va='center', fontsize=10, fontweight='bold')
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()

def add_page_number(canvas, doc):
    canvas.saveState()
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(HexColor("#94A3B8"))
    canvas.drawString(2*cm, 1*cm, "Relatorio CIPHER - Jefrey Assistant")
    canvas.drawRightString(A4[0] - 2*cm, 1*cm, f"Pagina {doc.page}")
    canvas.line(2*cm, 1.3*cm, A4[0] - 2*cm, 1.3*cm)
    canvas.restoreState()

def build_pdf(output_path):
    chart_path = os.path.join(os.path.dirname(output_path), "chart_severity.png")
    generate_chart_severity(chart_path)
    
    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2.5*cm
    )
    
    story = []
    
    # === CAPA ===
    story.append(Spacer(1, 4*cm))
    story.append(Paragraph("Relatorio CIPHER", style_title))
    story.append(Paragraph("Jefrey Assistant - Auditoria de Seguranca", style_subtitle))
    story.append(Spacer(1, 1*cm))
    
    meta_data = [
        ["Data:", datetime.now().strftime("%Y-%m-%d %H:%M")],
        ["Escopo:", "P0-P5 completo"],
        ["Stack:", "Python 3.12, FastAPI, LangGraph, OpenAI Agents SDK"],
        ["Metodologia:", "7 categorias, linha por linha"],
        ["Ambiente:", "Docker 7 servicos, PostgreSQL+pgvector, Redis 7.2"],
    ]
    meta_table = Table(meta_data, colWidths=[4*cm, 12*cm])
    meta_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('TEXTCOLOR', (0,0), (0,-1), HexColor("#64748B")),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(meta_table)
    story.append(PageBreak())
    
    # === RESUMO EXECUTIVO ===
    story.append(Paragraph("Resumo Executivo", style_h1))
    story.append(Paragraph(
        "Esta auditoria identificou <b>24 achados</b> distribuidos em 5 severidades. "
        "O fluxo principal POST /chat->Agent->LLM apresenta <b>3 falhas criticas</b> que "
        "invalidam completamente a execucao do agente e a camada de governanca de seguranca.",
        style_body
    ))
    story.append(Spacer(1, 0.5*cm))
    
    if os.path.exists(chart_path):
        story.append(Image(chart_path, width=16*cm, height=6.5*cm))
    story.append(Spacer(1, 0.5*cm))
    
    # Summary table
    summary_data = [["Severidade", "Qtd", "%"]]
    total = len(FINDINGS)
    for sev in ["CRITICA", "ALTA", "MEDIA", "BAIXA", "INFORMATIVA"]:
        count = sum(1 for f in FINDINGS if f["sev"] == sev)
        if count > 0:
            summary_data.append([sev, str(count), f"{count/total*100:.0f}%"])
    summary_data.append(["TOTAL", str(total), "100%"])
    
    sum_table = Table(summary_data, colWidths=[5*cm, 3*cm, 3*cm])
    sum_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), HexColor("#1E293B")),
        ('TEXTCOLOR', (0,0), (-1,0), white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('ALIGN', (1,0), (-1,-1), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 0.5, HexColor("#E2E8F0")),
        ('BACKGROUND', (0,-1), (-1,-1), HexColor("#F1F5F9")),
        ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
    ]))
    story.append(sum_table)
    story.append(PageBreak())
    
    # === PONTOS FORTES ===
    story.append(Paragraph("Pontos Fortes", style_h1))
    story.append(Paragraph("O que esta CORRETO e protegido:", style_body))
    story.append(Spacer(1, 0.3*cm))
    
    strengths_data = [["ID", "Descricao", "Arquivo", "Evidencia"]]
    for sid, desc, file, evidence in STRENGTHS:
        strengths_data.append([sid, desc, file, evidence])
    
    str_table = Table(strengths_data, colWidths=[1.5*cm, 4.5*cm, 4*cm, 6*cm])
    str_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), HexColor("#059669")),
        ('TEXTCOLOR', (0,0), (-1,0), white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('FONTSIZE', (0,0), (-1,0), 9),
        ('GRID', (0,0), (-1,-1), 0.5, HexColor("#D1FAE5")),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [white, HexColor("#F0FDF4")]),
    ]))
    story.append(str_table)
    story.append(PageBreak())
    
    # === PONTOS FRACOS ===
    story.append(Paragraph("Pontos Fracos", style_h1))
    story.append(Paragraph(
        "<b>O fluxo principal esta quebrado.</b> O agent nunca executa ferramentas — "
        "faz apenas um bypass direto para o LLM via httpx. Toda a camada de "
        "governanca (RBAC, PolicyEngine, HITL, content_guard, AuditLogger) e "
        "codigo morto. Alem disso, o AgentState tem 3 definicoes de classe "
        "(conflito de edicoes) que impedem o chat de funcionar.",
        style_body
    ))
    story.append(Spacer(1, 0.3*cm))
    
    weak_data = [
        ["Problema Central", "Impacto"],
        ["Agent nunca invoca ferramentas", "RBAC, Policy, HITL, Audit = dead code"],
        ["AgentState triplo -> state.user_id sempre vazio", "Chat retorna 500 sempre"],
        ["pg_memory._embed() inexistente", "Memoria nunca persiste"],
        ["pg_memory.search() sem similaridade vetorial", "Contexto irrelevante para LLM"],
        ["Rate limiter URL sem password -> deny", "Todas tools bloqueadas"],
        ["STT/TTS chamam PolicyEngine.decide() inexistente", "Endpoints 500 sempre"],
        ["Skills sem user_id -> cross-tenant leak", "Dados de usuarios misturados"],
    ]
    weak_table = Table(weak_data, colWidths=[7*cm, 9*cm])
    weak_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), HexColor("#B91C1C")),
        ('TEXTCOLOR', (0,0), (-1,0), white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('GRID', (0,0), (-1,-1), 0.5, HexColor("#FECACA")),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [white, HexColor("#FEF2F2")]),
    ]))
    story.append(weak_table)
    story.append(PageBreak())
    
    # === TABELA DE ACHADOS DETALHADOS ===
    story.append(Paragraph("Achados Detalhados", style_h1))
    
    for i in range(0, len(FINDINGS), 4):
        batch = FINDINGS[i:i+4]
        table_data = [["#", "Severidade", "Arquivo", "Descricao"]]
        for f in batch:
            table_data.append([
                f["id"],
                make_severity_badge(f["sev"]),
                f["file"],
                f["desc"][:120] + ("..." if len(f["desc"]) > 120 else "")
            ])
        
        t = Table(table_data, colWidths=[1.5*cm, 2*cm, 3.5*cm, 9*cm])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), HexColor("#1E293B")),
            ('TEXTCOLOR', (0,0), (-1,0), white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('FONTSIZE', (0,0), (-1,0), 9),
            ('GRID', (0,0), (-1,-1), 0.5, HexColor("#CBD5E1")),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [white, HexColor("#F8FAFC")]),
        ]))
        story.append(KeepTogether([t, Spacer(1, 0.5*cm)]))
        
        if i + 4 < len(FINDINGS):
            story.append(PageBreak())
    
    story.append(PageBreak())
    
    # === RECOMENDACOES ===
    story.append(Paragraph("Recomendacoes Priorizadas", style_h1))
    
    story.append(Paragraph("P1 — Corrigir AGORA (Critica/Alta)", style_h2))
    p1_recs = [
        ["Achado", "Correcao", "Esforco"],
        ["CRIT-01", "Remover classes AgentState duplicadas, manter 1 classe com __getattr__/__setattr__ corretos", "2h"],
        ["CRIT-02", "Reescrever agent.run() para usar LangGraph com tool calling real (Ollama function calling)", "8h"],
        ["HIGH-02", "Criar _embed() usando Ollama embeddings endpoint ou sentence-transformers", "3h"],
        ["HIGH-03", "Substituir ORDER BY importance por pgvector cosine_distance operator", "2h"],
        ["HIGH-04", "Incluir password na Redis URL (config.redis.dsn must include password)", "1h"],
        ["CRIT-04/05", "Trocar PolicyEngine.decide() por PolicyEngine.evaluate() ou criar decide() alias", "1h"],
        ["HIGH-01", "Corrigir mm.long_term.search() -> mm.search(), remover .get_messages()", "1h"],
        ["MED-07", "CLI: adicionar X-User-Id header em get_auth_headers()", "1h"],
    ]
    p1_table = Table(p1_recs, colWidths=[2*cm, 11*cm, 2*cm])
    p1_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), HexColor("#B91C1C")),
        ('TEXTCOLOR', (0,0), (-1,0), white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('GRID', (0,0), (-1,-1), 0.5, HexColor("#FECACA")),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(p1_table)
    story.append(Paragraph("<b>Estimativa total P1: ~19 horas</b>", style_strong))
    story.append(Spacer(1, 0.5*cm))
    
    story.append(Paragraph("P2 — Proximo Sprint (Media)", style_h2))
    p2_text = (
        "- MED-01: Persistir _RUNNING_TASKS em Redis/Postgres<br/>"
        "- MED-02: Remover X-User-Id trust, usar user_id do token validado<br/>"
        "- MED-03: Validar JEFREY_ENV em startup (fail-closed se nao e 'prod')<br/>"
        "- MED-04: Aplicar content_guard no output do LLM antes de retornar<br/>"
        "- MED-05: Expandir SSRF blocklist (0.0.0.0, DNS rebinding)<br/>"
        "- MED-06: Adicionar SELECT FOR UPDATE no approve<br/>"
        "- MED-08: Namespacar checkpoints com user_id:thread_id"
    )
    story.append(Paragraph(p2_text, style_body))
    story.append(Spacer(1, 0.3*cm))
    
    story.append(Paragraph("P3 — Backlog (Baixa/Informativa)", style_h2))
    p3_text = (
        "- LOW-01: Remover dead code apos exception block no auth_middleware<br/>"
        "- LOW-02: Configurar base_url para preservar /v1 quando necessario<br/>"
        "- LOW-03: Auditoria de memory/health isolation por tenant"
    )
    story.append(Paragraph(p3_text, style_body))
    story.append(PageBreak())
    
    # === RISCOS LATENTES ===
    story.append(Paragraph("Riscos Latentes", style_h1))
    risks = [
        ("_RUNNING_TASKS em producao com Docker restart",
         "Tasks perdidas apos restart. Clientes veem 'idle' durante conversa ativa. "
         "Em escala multi-tenant, induz usuario a reenviar mensagem duplicando execucao.",
         "MÉDIA"),
        ("Stubs OAuth Google (calendar/email)",
         "Falha silenciosa quando usuario tenta conectar Google Calendar/Drive/Gmail. "
         "User vê erro generico sem saber que precisa configurar credenciais.",
         "MÉDIA"),
        ("smoke_test 5/7 com Ollama offline",
         "5 de 7 testes passam mesmo sem LLM. Gera falsa sensacao de saude. "
         "Em CI/CD, deploy passa sem LLM funcional.",
         "BAIXA"),
        ("Agent sem LangGraph real",
         "Em producao, o agent e apenas um wrapper de httpx para Ollama. "
         "Nenhuma ferramenta e executada. Qualquer prompt injection do LLM "
         "nao tem defesa em tool-level.",
         "CRÍTICA"),
        ("Embbedings inexistentes",
         "pg_memory._embed() nao existe. Nenhuma memoria e indexada. "
         "Contexto de memória vazio para sempre.",
         "CRÍTICA"),
    ]
    risk_data = [["Risco", "Impacto", "Severidade"]]
    for r, imp, sev in risks:
        risk_data.append([r, imp[:100], sev])
    risk_table = Table(risk_data, colWidths=[5*cm, 8*cm, 3*cm])
    risk_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), HexColor("#1E293B")),
        ('TEXTCOLOR', (0,0), (-1,0), white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('GRID', (0,0), (-1,-1), 0.5, HexColor("#CBD5E1")),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(risk_table)
    story.append(PageBreak())
    
    # === ISSUES GITHUB ===
    story.append(Paragraph("Issues para GitHub", style_h1))
    
    issues = [
        {
            "title": "[CIPHER] CRIT: AgentState triplo + agent bypass governance",
            "labels": "cipher, critica, P2",
            "desc": "agent.py contem 3 definicoes de AgentState (edicoes falhas). "
                    "A ultima __setattr__ conflita com __init__. agent.run() bypassa "
                    "TODA a governanca (RBAC, Policy, HITL, Audit) fazendo httpx direto ao Ollama.",
            "evidence": "src/jefrey/core/agent.py:23-60 (triple class), :160 (bypass)",
            "fix": "Remover classes duplicadas. Reescrever run() usando LangGraph com tool calling real.",
            "acceptance": [
                "AgentState tem 1 definicao unica",
                "AgentState(user_id='test').user_id retorna 'test'",
                "agent.run() chama pelo menos 1 tool via ToolRegistry",
                "Audit log registrado apos execucao de tool",
            ],
        },
        {
            "title": "[CIPHER] CRIT: pg_memory._embed() inexistente + search sem similaridade",
            "labels": "cipher, critica, P1",
            "desc": "pg_memory.add() chama self._embed() que nao existe. "
                    "search() usa ORDER BY importance em vez de cosine distance.",
            "evidence": "src/jefrey/core/pg_memory.py:55 (_embed), :85 (search)",
            "fix": "Implementar _embed() com Ollama embeddings. Trocar ORDER BY por pgvector <=> operator.",
            "acceptance": [
                "memory.add() persiste embedding no Postgres",
                "memory.search() retorna por similaridade coseno",
                "Teste: add 3 memorias, search retorna a mais similar primeiro",
            ],
        },
        {
            "title": "[CIPHER] ALTA: STT/TTS chamam PolicyEngine.decide() inexistente",
            "labels": "cipher, alta, P1",
            "desc": "stt.py e tts.py chamam pe.decide() mas PolicyEngine so tem evaluate(). "
                    "Ambos endpoints retornam 500 sempre.",
            "evidence": "src/jefrey/api/stt.py:40, src/jefrey/api/tts.py:40",
            "fix": "Criar alias PolicyEngine.decide() ou trocar para evaluate().",
            "acceptance": [
                "POST /stt (com auth) retorna transcript",
                "POST /tts (com auth) retorna audio bytes",
            ],
        },
        {
            "title": "[CIPHER] ALTA: Rate limiter deny all (Redis URL sem password)",
            "labels": "cipher, alta, P1",
            "desc": "redis.dsn gera URL sem password. Redis exige auth. "
                    "is_allowed_sync() raise RuntimeError -> fail-closed deny -> todas tools bloqueadas.",
            "evidence": "src/jefrey/core/rate_limit.py:~45, src/jefrey/core/config.py (redis.dsn)",
            "fix": "Incluir password na redis.dsn ou usar JEFREY_REDIS__URL com password.",
            "acceptance": [
                "Rate limiter conecta ao Redis com sucesso",
                "Tools nao sao bloqueadas indevidamente",
            ],
        },
        {
            "title": "[CIPHER] ALTA: Skills sem user_id - cross-tenant data leak",
            "labels": "cipher, alta, P6",
            "desc": "Apenas notes.py propaga user_id. Automation, calendar, drive, "
                    "email, web_search salvam dados sem user_id. Dados de usuarios misturados.",
            "evidence": "src/jefrey/skills/*.py (todos exceto notes.py)",
            "fix": "Adicionar user_id como parametro obrigatoria em todas as skills. "
                   "Propagar user_id de kwargs.",
            "acceptance": [
                "Todas skills tem user_id no signature",
                "Audit log registra user_id em todas as chamadas",
            ],
        },
    ]
    
    for issue in issues:
        issue_text = [
            f"<b>--- ISSUE: {issue['title']} ---</b>",
            f"<b>Labels:</b> {issue['labels']}",
            f"<b>Problema:</b> {issue['desc']}",
            f"<b>Evidencia:</b> <font face='Courier'>{issue['evidence']}</font>",
            f"<b>Correcao:</b> {issue['fix']}",
            "<b>Criterios de Aceite:</b>",
        ]
        for ac in issue['acceptance']:
            issue_text.append(f"  [ ] {ac}")
        issue_text.append(f"<b>--- FIM ISSUE: {issue['title']} ---</b>")
        
        for line in issue_text:
            story.append(Paragraph(line, style_body))
        story.append(Spacer(1, 0.5*cm))
    
    # Build
    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    print(f"PDF generated: {output_path}")
    print(f"Chart generated: {chart_path}")
    return output_path

if __name__ == "__main__":
    output = os.path.join(os.path.dirname(__file__), "relatorio-cipher-jefrey.pdf")
    build_pdf(output)
