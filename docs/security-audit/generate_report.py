#!/usr/bin/env python3
"""
Gerador de Relatório de Auditoria de Segurança — Projeto Jefrey
Gera um PDF profissional em português brasileiro usando reportlab + matplotlib.
"""

import os
import io
import textwrap
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, mm
from reportlab.lib.colors import HexColor, white, black, Color
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image, KeepTogether, HRFlowable, ListFlowable, ListItem
)
from reportlab.platypus.flowables import Flowable
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ──────────────────────────────────────────────
# CONSTANTS
# ──────────────────────────────────────────────
PAGE_W, PAGE_H = A4
MARGIN = 2 * cm

# Color palette
CRITICAL_COLOR = HexColor("#B91C1C")
HIGH_COLOR     = HexColor("#EA580C")
MEDIUM_COLOR   = HexColor("#D97706")
LOW_COLOR      = HexColor("#2563EB")
STRENGTH_COLOR = HexColor("#059669")

DARK_BG        = HexColor("#1E293B")
HEADER_BG      = HexColor("#0F172A")
ACCENT         = HexColor("#3B82F6")
LIGHT_GRAY     = HexColor("#F1F5F9")
MID_GRAY       = HexColor("#CBD5E1")
TEXT_DARK       = HexColor("#1E293B")
TEXT_SECONDARY  = HexColor("#64748B")

SEVERITY_COLORS = {
    "CRÍTICO": "#B91C1C",
    "ALTO":     "#EA580C",
    "MÉDIO":    "#D97706",
    "BAIXO":    "#2563EB",
}

# ──────────────────────────────────────────────
# FINDINGS DATA
# ──────────────────────────────────────────────
FINDINGS = [
    {
        "id": "1.1",
        "category": "Banco sem Tranca",
        "severity": "CRÍTICO",
        "title": "Tabelas de memória sem isolamento por usuário/tenant",
        "files": [
            "src/jefrey/core/models.py (todas as classes _MemoryMixin, linhas 17–38)",
            "src/jefrey/core/pg_memory.py (métodos search, get, update, delete, list_recent)",
        ],
        "description": (
            "As 5 tabelas de memória (episódica, semântica, preferência, procedimental e operacional) "
            "NÃO possuem coluna user_id. Todas as consultas retornam TODOS os dados de TODOS os "
            "usuários. Um deploy multiusuário vazaria memórias entre usuários distintos."
        ),
        "impact": "Vazamento completo de dados entre usuários em ambiente multiusuário.",
        "recommendation": "Adicionar coluna user_id a todas as tabelas de memória e filtrar todas as consultas.",
        "ref": "CWE-863: Incorrect Authorization",
    },
    {
        "id": "1.2",
        "category": "Banco sem Tranca",
        "severity": "ALTO",
        "title": "ApprovalManager.get_pending() retorna todas as aprovações sem filtro",
        "files": [
            "src/jefrey/core/hitl.py, método get_pending() (linha ~100)",
        ],
        "description": (
            "GET /approvals/pending retorna TODAS as aprovações pendentes sem filtragem por "
            "usuário. Qualquer usuário autenticado visualiza aprovações de outros usuários."
        ),
        "impact": "Exposição de aprovações pendentes de outros usuários.",
        "recommendation": "Filtrar aprovações por user_id ou thread ownership.",
        "ref": "CWE-863: Incorrect Authorization",
    },
    {
        "id": "1.3",
        "category": "Banco sem Tranca",
        "severity": "MÉDIO",
        "title": "Ausência de Row Level Security (RLS) no banco de dados",
        "files": [
            "docker-compose.yml",
            "src/jefrey/core/db.py",
        ],
        "description": (
            "O PostgreSQL não possui políticas RLS. Mesmo que o filtro no nível da aplicação seja "
            "adicionado depois, não existe defesa em profundidade."
        ),
        "impact": "Falha de defesa em profundidade; um bug na aplicação expõe todos os dados.",
        "recommendation": "Implementar RLS no PostgreSQL como camada extra de proteção.",
        "ref": "CWE-863: Incorrect Authorization",
    },
    {
        "id": "2.1",
        "category": "Permissão no Navegador",
        "severity": "ALTO",
        "title": "Endpoints da API (chat, memory) sem verificações RBAC",
        "files": [
            "src/jefrey/api/chat.py (POST /chat) — sem validação de papel",
            "src/jefrey/api/memory.py (GET /memory/search, GET /memory) — sem validação de papel",
        ],
        "description": (
            "O RBAC é aplicado apenas no ToolExecutor e no gateway MCP. Os endpoints FastAPI "
            "(chat, memory) aceitam requisições de qualquer pessoa sem verificar o papel. Um "
            "usuário convidado pode conversar com o agente e acessar a busca de memória."
        ),
        "impact": "Usuários não autorizados acessam funcionalidades restritas.",
        "recommendation": "Adicionar middleware RBAC em todos os endpoints FastAPI.",
        "ref": "CWE-862: Missing Authorization",
    },
    {
        "id": "3.1",
        "category": "IDOR",
        "severity": "ALTO",
        "title": "Endpoint decide de aprovação sem verificação de posse",
        "files": [
            "src/jefrey/api/approvals.py, função decide() (linha ~65)",
        ],
        "description": (
            "POST /approvals/{id}/decide requer apenas o token Bearer — qualquer usuário "
            "autenticado pode aprovar/rejeitar QUALQUER aprovação de QUALQUER thread. Não há "
            "verificação de que o aprovador tem autoridade sobre aquela aprovação ou thread específica."
        ),
        "impact": "Um usuário malicioso pode aprovar ou rejeitar operações de outros usuários.",
        "recommendation": "Adicionar verificação de posse (ownership) antes de permitir decisão.",
        "ref": "CWE-639: Authorization Bypass Through User-Controlled Key",
    },
    {
        "id": "4.1",
        "category": "Chaves Expostas",
        "severity": "CRÍTICO",
        "title": "Chave real da API Tavily em arquivo .env",
        "files": [
            ".env, linha 29",
        ],
        "description": (
            "JEFREY_TAVILY_API_KEY=tvly-dev-qwgiq-... está presente no diretório de trabalho. "
            "Embora .env esteja no .gitignore, se o padrão falhar ou o arquivo for commitado "
            "acidentalmente, a chave fica exposta publicamente."
        ),
        "impact": "Chave de API de terceiros exposta, possíveis custos financeiros e abuso.",
        "recommendation": "Usar variáveis de ambiente ou Docker secrets; roterar a chave atual.",
        "ref": "CWE-798: Use of Hard-coded Credentials",
    },
    {
        "id": "4.2",
        "category": "Chaves Expostas",
        "severity": "MÉDIO",
        "title": "Credenciais de banco codificadas no docker-compose.yml",
        "files": [
            "docker-compose.yml, linhas 10–12",
        ],
        "description": (
            "POSTGRES_USER: jefrey, POSTGRES_PASSWORD: jefrey, POSTGRES_DB: jefrey. "
            "Credenciais padrão são aceitáveis para desenvolvimento, mas devem usar secrets/"
            "variáveis em produção."
        ),
        "impact": "Credenciais padrão facilmente adivinháveis em produção.",
        "recommendation": "Usar Docker secrets ou variáveis externas em produção.",
        "ref": "CWE-798: Use of Hard-coded Credentials",
    },
    {
        "id": "4.3",
        "category": "Chaves Expostas",
        "severity": "BAIXO",
        "title": "Chave secreta padrão vazia permite bypass completo de autenticação",
        "files": [
            "src/jefrey/core/config.py, classe APISettings (linha ~270)",
        ],
        "description": (
            "secret_key: str = \"\" — Quando vazia, o middleware de auth rejeita TODAS as "
            "requisições (projetado corretamente), mas não há validação na inicialização que "
            "avisa ou recusa iniciar quando secret_key está vazia em produção."
        ),
        "impact": "Possível confusão em produção; middleware pode rejeitar tudo ou aceitar tudo dependendo da config.",
        "recommendation": "Adicionar validação na inicialização para secret_key em modo produção.",
        "ref": "CWE-521: Weak Password Requirements",
    },
    {
        "id": "5.1",
        "category": "Inputs sem Tratamento",
        "severity": "MÉDIO",
        "title": "Padrões regex do content_guard são limitados",
        "files": [
            "src/jefrey/core/content_guard.py",
        ],
        "description": (
            "Apenas 7 padrões de detecção. Faltam: prompt injection codificado, padrões multilíngues, "
            "bypass via Unicode, instruções em base64, tags de system prompt aninhadas."
        ),
        "impact": "Ataques de prompt injection podem bypassar as proteções atuais.",
        "recommendation": "Expandir os padrões com listas de verificação OWASP LLM e testes adversariais.",
        "ref": "CWE-20: Improper Input Validation",
    },
]

STRENGTHS = [
    "Autenticação Bearer token em todos os endpoints de aprovação",
    "Content guard aplicado à entrada do usuário em POST /chat",
    "Content guard aplicado à saída externa do MCP",
    "RBAC aplicado no ToolExecutor e gateway MCP",
    "Validação UUID antes de tocar no banco de dados",
    "arguments_json omitido da resposta de listagem",
    "mode='off' não contorna o RBAC",
    "Papel resolvido no lado do servidor",
    "Detecção de callable síncrono no ToolExecutor",
    "Fallback de auditoria em caso de falha no PostgreSQL",
    "ToolRegistry fail-safe: ferramentas não registradas são bloqueadas",
    ".env devidamente no .gitignore",
    "Bypass do admin funciona corretamente",
]

RECOMMENDATIONS = [
    ("P1", "Adicionar user_id às tabelas de memória + filtrar todas as consultas", "CRÍTICO"),
    ("P2", "Adicionar middleware RBAC aos endpoints FastAPI", "ALTO"),
    ("P3", "Adicionar verificação de posse ao endpoint decide de aprovação", "ALTO"),
    ("P4", "Adicionar validação na inicialização para secret_key", "MÉDIO"),
    ("P5", "Expandir padrões do content_guard", "MÉDIO"),
    ("P6", "Usar Docker secrets para credenciais em produção", "MÉDIO"),
    ("P7", "Considerar RLS do PostgreSQL como defesa em profundidade", "BAIXO"),
]

GITHUB_ISSUES = [
    {
        "number": 1,
        "title": "[Segurança] Memória sem isolamento por usuário — vazamento de dados entre usuários",
        "labels": ["security", "critical"],
        "body": (
            "## Descrição\n\n"
            "As 5 tabelas de memória (episódica, semântica, preferência, procedimental e operacional) "
            "não possuem coluna `user_id`. Todas as consultas no `pg_memory.py` retornam TODOS os "
            "dados de TODOS os usuários.\n\n"
            "## Arquivos afetados\n\n"
            "- `src/jefrey/core/models.py` (todas as classes `_MemoryMixin`, linhas 17–38)\n"
            "- `src/jefrey/core/pg_memory.py` (métodos search, get, update, delete, list_recent)\n\n"
            "## Impacto\n\n"
            "Um deploy multiusuário vazaria memórias entre usuários distintos.\n\n"
            "## Solução\n\n"
            "1. Adicionar coluna `user_id` (UUID, NOT NULL) a todas as tabelas de memória\n"
            "2. Filtrar todas as consultas por `user_id`\n"
            "3. Adicionar migração Alembic para coluna existente\n"
            "4. Considerar RLS como defesa em profundidade"
        ),
    },
    {
        "number": 2,
        "title": "[Segurança] API endpoints (chat/memory) sem verificação RBAC",
        "labels": ["security", "high"],
        "body": (
            "## Descrição\n\n"
            "O RBAC é aplicado apenas no `ToolExecutor` e no gateway MCP. Os endpoints FastAPI "
            "(chat, memory) aceitam requisições de qualquer pessoa sem verificar o papel.\n\n"
            "## Arquivos afetados\n\n"
            "- `src/jefrey/api/chat.py` — POST /chat sem validação de papel\n"
            "- `src/jefrey/api/memory.py` — GET /memory/search, GET /memory sem validação de papel\n\n"
            "## Impacto\n\n"
            "Um usuário convidado pode conversar com o agente e acessar a busca de memória.\n\n"
            "## Solução\n\n"
            "Adicionar middleware ou dependência RBAC em todos os endpoints FastAPI."
        ),
    },
    {
        "number": 3,
        "title": "[Segurança] Approval decide sem verificação de posse (IDOR)",
        "labels": ["security", "high"],
        "body": (
            "## Descrição\n\n"
            "POST /approvals/{id}/decide requer apenas o token Bearer — qualquer usuário autenticado "
            "pode aprovar/rejeitar QUALQUER aprovação de QUALQUER thread.\n\n"
            "## Arquivos afetados\n\n"
            "- `src/jefrey/api/approvals.py`, função `decide()` (linha ~65)\n\n"
            "## Impacto\n\n"
            "Um usuário malicioso pode aprovar ou rejeitar operações de outros usuários.\n\n"
            "## Solução\n\n"
            "Adicionar verificação de ownership: confirmar que o aprovador tem autoridade sobre a "
            "aprovação ou thread específica antes de processar a decisão."
        ),
    },
    {
        "number": 4,
        "title": "[Segurança] Chaves padrão e validação de startup ausente",
        "labels": ["security", "medium"],
        "body": (
            "## Descrição\n\n"
            "Dois problemas agrupados:\n\n"
            "1. `secret_key` vazio por padrão — sem validação na inicialização\n"
            "2. Credenciais de banco codificadas no `docker-compose.yml`\n\n"
            "## Arquivos afetados\n\n"
            "- `src/jefrey/core/config.py` — `secret_key: str = \"\"` (linha ~270)\n"
            "- `docker-compose.yml` — credenciais padrão (linhas 10–12)\n\n"
            "## Solução\n\n"
            "1. Adicionar validação na inicialização que recusa iniciar em modo produção com secret_key vazio\n"
            "2. Usar Docker secrets ou variáveis de ambiente para credenciais em produção"
        ),
    },
    {
        "number": 5,
        "title": "[Segurança] content_guard com padrões insuficientes",
        "labels": ["security", "medium"],
        "body": (
            "## Descrição\n\n"
            "O content_guard possui apenas 7 padrões de detecção. Faltam verificações para:\n\n"
            "- Prompt injection codificado\n"
            "- Padrões multilíngues\n"
            "- Bypass via Unicode\n"
            "- Instruções em base64\n"
            "- Tags de system prompt aninhadas\n\n"
            "## Arquivos afetados\n\n"
            "- `src/jefrey/core/content_guard.py`\n\n"
            "## Solução\n\n"
            "Expandir os padrões seguindo OWASP LLM Security Top 10 e realizar testes adversariais."
        ),
    },
]


# ──────────────────────────────────────────────
# CHART GENERATION (matplotlib → reportlab Image)
# ──────────────────────────────────────────────

def make_donut_chart():
    """Donut chart de distribuição de severidade."""
    severity_counts = {}
    for f in FINDINGS:
        severity_counts[f["severity"]] = severity_counts.get(f["severity"], 0) + 1

    order = ["CRÍTICO", "ALTO", "MÉDIO", "BAIXO"]
    labels = [s for s in order if s in severity_counts]
    values = [severity_counts[s] for s in labels]
    colors = [SEVERITY_COLORS[s] for s in labels]

    fig, ax = plt.subplots(figsize=(4.5, 3.5), dpi=150)
    wedges, texts, autotexts = ax.pie(
        values, labels=labels, colors=colors, autopct="%1.0f%%",
        startangle=90, pctdistance=0.78,
        wedgeprops=dict(width=0.42, edgecolor="white", linewidth=2),
    )
    for t in texts:
        t.set_fontsize(9)
        t.set_fontweight("bold")
    for t in autotexts:
        t.set_fontsize(8)
        t.set_color("white")
    ax.set_title("Distribuição por Severidade", fontsize=11, fontweight="bold", pad=12)

    # Center text
    ax.text(0, 0, f"{sum(values)}\nachados", ha="center", va="center",
            fontsize=13, fontweight="bold", color="#1E293B")

    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", transparent=False, facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return buf


def make_bar_chart():
    """Bar chart de achados por categoria."""
    cat_counts = {}
    for f in FINDINGS:
        cat_counts[f["category"]] = cat_counts.get(f["category"], 0) + 1

    categories = list(cat_counts.keys())
    counts = [cat_counts[c] for c in categories]

    # Short names for display
    short_names = {
        "Banco sem Tranca": "Banco s/\nTranca",
        "Permissão no Navegador": "Permiss.\nNavegador",
        "IDOR": "IDOR",
        "Chaves Expostas": "Chaves\nExpostas",
        "Inputs sem Tratamento": "Inputs s/\nTratamento",
    }
    display_names = [short_names.get(c, c) for c in categories]

    fig, ax = plt.subplots(figsize=(5.5, 3.2), dpi=150)
    bar_colors = ["#B91C1C", "#EA580C", "#2563EB", "#D97706", "#64748B"]
    bars = ax.bar(display_names, counts, color=bar_colors[:len(categories)],
                  width=0.55, edgecolor="white", linewidth=1.2)

    for bar, count in zip(bars, counts):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.08,
                str(count), ha="center", va="bottom", fontsize=10, fontweight="bold",
                color="#1E293B")

    ax.set_ylabel("Nº de Achados", fontsize=9)
    ax.set_title("Achados por Categoria", fontsize=11, fontweight="bold", pad=12)
    ax.set_ylim(0, max(counts) + 1.2)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(axis="x", labelsize=8)
    ax.tick_params(axis="y", labelsize=8)

    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", transparent=False, facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return buf


# ──────────────────────────────────────────────
# CUSTOM FLOWABLES
# ──────────────────────────────────────────────

class SeverityBadge(Flowable):
    """Inline severity badge."""
    def __init__(self, text, color_hex, width=70, height=16):
        Flowable.__init__(self)
        self.text = text
        self.color = HexColor(color_hex)
        self.width = width
        self.height = height

    def draw(self):
        self.canv.setFillColor(self.color)
        self.canv.roundRect(0, 0, self.width, self.height, 4, fill=1, stroke=0)
        self.canv.setFillColor(white)
        self.canv.setFont("Helvetica-Bold", 7)
        self.canv.drawCentredString(self.width/2, 4.5, self.text)


class ColorBar(Flowable):
    """Left color accent bar for finding cards."""
    def __init__(self, color_hex, height, width=4):
        Flowable.__init__(self)
        self.color = HexColor(color_hex)
        self.width = width
        self.height = height

    def draw(self):
        self.canv.setFillColor(self.color)
        self.canv.roundRect(0, 0, self.width, self.height, 2, fill=1, stroke=0)


# ──────────────────────────────────────────────
# DOCUMENT BUILDER
# ──────────────────────────────────────────────

def build_styles():
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        "CoverTitle", fontSize=28, fontName="Helvetica-Bold",
        textColor=white, alignment=TA_CENTER, leading=34,
        spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        "CoverSubtitle", fontSize=13, fontName="Helvetica",
        textColor=HexColor("#94A3B8"), alignment=TA_CENTER, leading=18,
        spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        "CoverMeta", fontSize=10, fontName="Helvetica",
        textColor=HexColor("#CBD5E1"), alignment=TA_CENTER, leading=14,
    ))
    styles.add(ParagraphStyle(
        "SectionTitle", fontSize=16, fontName="Helvetica-Bold",
        textColor=TEXT_DARK, spaceBefore=16, spaceAfter=8, leading=20,
    ))
    styles.add(ParagraphStyle(
        "SubSectionTitle", fontSize=12, fontName="Helvetica-Bold",
        textColor=TEXT_DARK, spaceBefore=10, spaceAfter=4, leading=15,
    ))
    styles.add(ParagraphStyle(
        "BodyText2", fontSize=9.5, fontName="Helvetica",
        textColor=TEXT_DARK, alignment=TA_JUSTIFY, leading=13, spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        "SmallText", fontSize=8.5, fontName="Helvetica",
        textColor=TEXT_SECONDARY, leading=11,
    ))
    styles.add(ParagraphStyle(
        "FindingTitle", fontSize=11, fontName="Helvetica-Bold",
        textColor=TEXT_DARK, leading=14, spaceAfter=3,
    ))
    styles.add(ParagraphStyle(
        "FindingBody", fontSize=9, fontName="Helvetica",
        textColor=TEXT_DARK, alignment=TA_JUSTIFY, leading=12.5, spaceAfter=3,
    ))
    styles.add(ParagraphStyle(
        "CodeText", fontSize=8, fontName="Courier",
        textColor=HexColor("#334155"), leading=10, spaceAfter=3,
        backColor=LIGHT_GRAY, borderPadding=4,
    ))
    styles.add(ParagraphStyle(
        "TableHeader", fontSize=8.5, fontName="Helvetica-Bold",
        textColor=white, alignment=TA_CENTER, leading=11,
    ))
    styles.add(ParagraphStyle(
        "TableCell", fontSize=8.5, fontName="Helvetica",
        textColor=TEXT_DARK, alignment=TA_LEFT, leading=11,
    ))
    styles.add(ParagraphStyle(
        "IssueTitle", fontSize=10, fontName="Helvetica-Bold",
        textColor=TEXT_DARK, leading=13, spaceAfter=2,
    ))
    styles.add(ParagraphStyle(
        "IssueBody", fontSize=8.5, fontName="Helvetica",
        textColor=TEXT_DARK, leading=11, spaceAfter=2,
    ))
    styles.add(ParagraphStyle(
        "TOCEntry", fontSize=10, fontName="Helvetica",
        textColor=TEXT_DARK, leading=14, spaceAfter=2,
    ))

    return styles


def header_footer(canvas, doc):
    """Draw header and footer on every page."""
    canvas.saveState()

    # Header line
    canvas.setStrokeColor(ACCENT)
    canvas.setLineWidth(1.5)
    canvas.line(MARGIN, PAGE_H - MARGIN + 8, PAGE_W - MARGIN, PAGE_H - MARGIN + 8)

    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(TEXT_SECONDARY)
    canvas.drawString(MARGIN, PAGE_H - MARGIN + 12, "Relatório de Auditoria de Segurança — Projeto Jefrey")
    canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - MARGIN + 12, "CONFIDENCIAL")

    # Footer
    canvas.setStrokeColor(MID_GRAY)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN, MARGIN - 10, PAGE_W - MARGIN, MARGIN - 10)

    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(TEXT_SECONDARY)
    canvas.drawString(MARGIN, MARGIN - 22, f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    canvas.drawCentredString(PAGE_W / 2, MARGIN - 22, "Jefrey Security Audit")
    canvas.drawRightString(PAGE_W - MARGIN, MARGIN - 22, f"Página {doc.page}")

    canvas.restoreState()


def cover_page_first(canvas, doc):
    """Cover page without header/footer."""
    pass  # drawn by the cover flowables


def build_cover(story, styles):
    """Build the cover page."""
    story.append(Spacer(1, 3 * cm))

    # Big colored block for title area
    # We use a Table as a visual block
    cover_data = [
        [Paragraph("RELATÓRIO DE AUDITORIA<br/>DE SEGURANÇA", styles["CoverTitle"])],
        [Spacer(1, 6)],
        [Paragraph("Projeto Jefrey — Análise de Segurança Completa", styles["CoverSubtitle"])],
        [Spacer(1, 12)],
        [Paragraph("Versão 1.0 — Junho 2025", styles["CoverMeta"])],
        [Paragraph("Classificação: CONFIDENCIAL", styles["CoverMeta"])],
    ]

    cover_table = Table(cover_data, colWidths=[PAGE_W - 2*MARGIN])
    cover_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), HEADER_BG),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 16),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 16),
        ("LEFTPADDING", (0, 0), (-1, -1), 24),
        ("RIGHTPADDING", (0, 0), (-1, -1), 24),
        ("ROUNDEDCORNERS", [8, 8, 8, 8]),
    ]))
    story.append(cover_table)

    story.append(Spacer(1, 1.5 * cm))

    # Summary info box
    summary_items = [
        ["Stack Detectada", "Python 3.14 · FastAPI · LangGraph · PostgreSQL 16 + pgvector"],
        ["Achados", f"{len(FINDINGS)} (2 críticos · 3 altos · 3 médios · 1 baixo)"],
        ["Pontos Fortes", f"{len(STRENGTHS)} controles de segurança validados"],
        ["Recomendações", f"{len(RECOMMENDATIONS)} ações priorizadas (P1–P7)"],
    ]
    summary_data = []
    for label, value in summary_items:
        summary_data.append([
            Paragraph(f"<b>{label}</b>", ParagraphStyle("sb", fontSize=9, fontName="Helvetica-Bold",
                                                         textColor=ACCENT, leading=12)),
            Paragraph(value, ParagraphStyle("sv", fontSize=9, fontName="Helvetica",
                                            textColor=TEXT_DARK, leading=12)),
        ])

    summary_table = Table(summary_data, colWidths=[4.5*cm, PAGE_W - 2*MARGIN - 4.5*cm])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_GRAY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("LINEBELOW", (0, 0), (-1, -2), 0.5, MID_GRAY),
        ("ROUNDEDCORNERS", [6, 6, 6, 6]),
    ]))
    story.append(summary_table)

    story.append(PageBreak())


def build_toc(story, styles):
    """Table of contents."""
    story.append(Paragraph("SUMÁRIO", styles["SectionTitle"]))
    story.append(Spacer(1, 4))

    toc_items = [
        "1. Visão Geral da Auditoria",
        "2. Stack Tecnológica Detectada",
        "3. Resumo Executivo",
        "4. Distribuição dos Achados",
        "5. Achados Detalhados",
        "    5.1 Banco sem Tranca (3 achados)",
        "    5.2 Permissão no Navegador (1 achado)",
        "    5.3 IDOR (1 achado)",
        "    5.4 Chaves Expostas (3 achados)",
        "    5.5 Inputs sem Tratamento (1 achado)",
        "6. Pontos Fortes e Controles Válidos",
        "7. Recomendações Priorizadas",
        "8. Issues para GitHub",
        "9. Conclusão",
    ]
    for item in toc_items:
        indent = 20 if item.startswith("    ") else 0
        st = ParagraphStyle("toc_item", fontSize=10, fontName="Helvetica",
                            textColor=TEXT_DARK, leading=16, leftIndent=indent)
        story.append(Paragraph(item.strip(), st))

    story.append(PageBreak())


def build_overview(story, styles):
    """Section 1: Overview."""
    story.append(Paragraph("1. VISÃO GERAL DA AUDITORIA", styles["SectionTitle"]))
    story.append(HRFlowable(width="100%", thickness=1, color=ACCENT, spaceAfter=8))

    overview_text = (
        "Este relatório apresenta os resultados da auditoria de segurança realizada no Projeto Jefrey, "
        "um sistema de agente de IA baseado em LangGraph com interface CLI. A auditoria avaliou a "
        "segurança da aplicação em múltiplas dimensões: isolamento de dados, autorização, autenticação, "
        "gerenciamento de segredos e validação de entrada."
    )
    story.append(Paragraph(overview_text, styles["BodyText2"]))
    story.append(Spacer(1, 6))

    overview_text2 = (
        "A análise identificou <b>9 achados</b> distribuídos em 5 categorias, incluindo 2 de severidade "
        "crítica que requerem ação imediata. Também foram validados <b>13 pontos fortes</b> que demonstram "
        "uma base sólida de controles de segurança na aplicação."
    )
    story.append(Paragraph(overview_text2, styles["BodyText2"]))


def build_stack(story, styles):
    """Section 2: Stack."""
    story.append(Spacer(1, 8))
    story.append(Paragraph("2. STACK TECNOLÓGICA DETECTADA", styles["SectionTitle"]))
    story.append(HRFlowable(width="100%", thickness=1, color=ACCENT, spaceAfter=8))

    stack_data = [
        [Paragraph("<b>Camada</b>", styles["TableHeader"]),
         Paragraph("<b>Tecnologia</b>", styles["TableHeader"]),
         Paragraph("<b>Detalhes</b>", styles["TableHeader"])],
        [Paragraph("Linguagem", styles["TableCell"]),
         Paragraph("Python 3.14", styles["TableCell"]),
         Paragraph("Runtime principal", styles["TableCell"])],
        [Paragraph("Framework", styles["TableCell"]),
         Paragraph("FastAPI + Starlette + LangGraph", styles["TableCell"]),
         Paragraph("API na porta 8000; approvals no Starlette; loop do agente via LangGraph", styles["TableCell"])],
        [Paragraph("ORM/Banco", styles["TableCell"]),
         Paragraph("SQLAlchemy + psycopg", styles["TableCell"]),
         Paragraph("PostgreSQL 16 + pgvector para embeddings", styles["TableCell"])],
        [Paragraph("Autenticação", styles["TableCell"]),
         Paragraph("Bearer token middleware", styles["TableCell"]),
         Paragraph("JEFREY_API__SECRET_KEY — somente no app Starlette (approvals)", styles["TableCell"])],
        [Paragraph("Frontend", styles["TableCell"]),
         Paragraph("CLI (typer + rich + httpx)", styles["TableCell"]),
         Paragraph("Sem frontend web", styles["TableCell"])],
        [Paragraph("Deploy", styles["TableCell"]),
         Paragraph("Docker Compose", styles["TableCell"]),
         Paragraph("postgres, redis, n8n, mcp-server, jefrey-api", styles["TableCell"])],
    ]

    stack_table = Table(stack_data, colWidths=[3*cm, 5*cm, PAGE_W - 2*MARGIN - 8*cm])
    stack_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), white),
        ("BACKGROUND", (0, 1), (-1, -1), white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, LIGHT_GRAY]),
        ("GRID", (0, 0), (-1, -1), 0.5, MID_GRAY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(stack_table)


def build_executive_summary(story, styles):
    """Section 3: Executive summary."""
    story.append(Spacer(1, 10))
    story.append(Paragraph("3. RESUMO EXECUTIVO", styles["SectionTitle"]))
    story.append(HRFlowable(width="100%", thickness=1, color=ACCENT, spaceAfter=8))

    summary_text = (
        "A auditoria revelou vulnerabilidades significativas em <b>isolamento de dados</b> e "
        "<b>autorização</b>. Os dois achados críticos — memória sem isolamento por usuário e "
        "chave de API real em .env — representam riscos imediatos que devem ser tratados como "
        "prioridade máxima."
    )
    story.append(Paragraph(summary_text, styles["BodyText2"]))
    story.append(Spacer(1, 4))

    summary_text2 = (
        "Os achados de severidade alta (RBAC ausente em endpoints, IDOR em aprovações) indicam "
        "lacunas no modelo de autorização que poderiam ser explorados por qualquer usuário "
        "autenticado. As recomendações deste relatório seguem uma ordem de prioridade (P1–P7) "
        "que deve guiar o remediamento."
    )
    story.append(Paragraph(summary_text2, styles["BodyText2"]))

    # Severity summary table
    story.append(Spacer(1, 8))
    sev_summary = [
        [Paragraph("<b>Severidade</b>", styles["TableHeader"]),
         Paragraph("<b>Quantidade</b>", styles["TableHeader"]),
         Paragraph("<b>Ação Necessária</b>", styles["TableHeader"])],
        [Paragraph("<font color='#B91C1C'><b>CRÍTICO</b></font>", styles["TableCell"]),
         Paragraph("2", styles["TableCell"]),
         Paragraph("Remediar imediatamente", styles["TableCell"])],
        [Paragraph("<font color='#EA580C'><b>ALTO</b></font>", styles["TableCell"]),
         Paragraph("3", styles["TableCell"]),
         Paragraph("Remediar antes do próximo release", styles["TableCell"])],
        [Paragraph("<font color='#D97706'><b>MÉDIO</b></font>", styles["TableCell"]),
         Paragraph("3", styles["TableCell"]),
         Paragraph("Remediar no curto prazo", styles["TableCell"])],
        [Paragraph("<font color='#2563EB'><b>BAIXO</b></font>", styles["TableCell"]),
         Paragraph("1", styles["TableCell"]),
         Paragraph("Melhorar na próxima iteração", styles["TableCell"])],
    ]

    sev_table = Table(sev_summary, colWidths=[3.5*cm, 3*cm, PAGE_W - 2*MARGIN - 6.5*cm])
    sev_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), white),
        ("BACKGROUND", (0, 1), (-1, -1), white),
        ("GRID", (0, 0), (-1, -1), 0.5, MID_GRAY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(sev_table)


def build_charts(story, styles):
    """Section 4: Charts."""
    story.append(Spacer(1, 10))
    story.append(Paragraph("4. DISTRIBUIÇÃO DOS ACHADOS", styles["SectionTitle"]))
    story.append(HRFlowable(width="100%", thickness=1, color=ACCENT, spaceAfter=8))

    donut_buf = make_donut_chart()
    bar_buf = make_bar_chart()

    img_w = 7.5 * cm
    donut_img = Image(donut_buf, width=img_w, height=img_w * 0.78)
    bar_img = Image(bar_buf, width=img_w * 1.15, height=img_w * 0.68)

    charts_table = Table([[donut_img, bar_img]], colWidths=[PAGE_W/2 - MARGIN, PAGE_W/2 - MARGIN])
    charts_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(charts_table)


def build_finding_card(finding, styles):
    """Build a finding card as a list of flowables."""
    sev_color = SEVERITY_COLORS[finding["severity"]]
    elements = []

    # Title row with badge
    title_text = f"<font color='{sev_color}'><b>[{finding['id']}]</b></font>  {finding['title']}"
    elements.append(Paragraph(title_text, styles["FindingTitle"]))

    # Severity badge + category
    badge_data = [[
        Paragraph(f"<font color='{sev_color}'><b>{finding['severity']}</b></font>", styles["TableCell"]),
        Paragraph(f"Categoria: {finding['category']}", styles["SmallText"]),
        Paragraph(f"Ref: {finding['ref']}", styles["SmallText"]),
    ]]
    badge_table = Table(badge_data, colWidths=[2.2*cm, 6*cm, 5*cm])
    badge_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), HexColor(sev_color + "15")),
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_GRAY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("BOX", (0, 0), (-1, -1), 0.5, HexColor(sev_color + "40")),
        ("ROUNDEDCORNERS", [4, 4, 4, 4]),
    ]))
    elements.append(badge_table)
    elements.append(Spacer(1, 4))

    # Description
    elements.append(Paragraph(f"<b>Descrição:</b> {finding['description']}", styles["FindingBody"]))

    # Files
    files_text = "<b>Arquivos afetados:</b><br/>" + "<br/>".join(
        [f"• <font face='Courier' size='8'>{f}</font>" for f in finding["files"]]
    )
    elements.append(Paragraph(files_text, styles["FindingBody"]))

    # Impact
    elements.append(Paragraph(f"<b>Impacto:</b> {finding['impact']}", styles["FindingBody"]))

    # Recommendation
    elements.append(Paragraph(f"<b>Recomendação:</b> {finding['recommendation']}", styles["FindingBody"]))

    return elements


def build_findings(story, styles):
    """Section 5: Detailed findings."""
    story.append(Spacer(1, 10))
    story.append(Paragraph("5. ACHADOS DETALHADOS", styles["SectionTitle"]))
    story.append(HRFlowable(width="100%", thickness=1, color=ACCENT, spaceAfter=8))

    # Group by category
    categories_order = [
        "Banco sem Tranca",
        "Permissão no Navegador",
        "IDOR",
        "Chaves Expostas",
        "Inputs sem Tratamento",
    ]
    cat_subtitles = {
        "Banco sem Tranca": "5.1 Banco sem Tranca",
        "Permissão no Navegador": "5.2 Permissão no Navegador",
        "IDOR": "5.3 IDOR",
        "Chaves Expostas": "5.4 Chaves Expostas",
        "Inputs sem Tratamento": "5.5 Inputs sem Tratamento",
    }

    for cat in categories_order:
        cat_findings = [f for f in FINDINGS if f["category"] == cat]
        if not cat_findings:
            continue

        story.append(Spacer(1, 6))
        story.append(Paragraph(cat_subtitles[cat], styles["SubSectionTitle"]))

        for finding in cat_findings:
            card_elements = build_finding_card(finding, styles)

            # Wrap each finding in a bordered table for visual card effect
            inner_content = []
            for elem in card_elements:
                inner_content.append(elem)

            # Use KeepTogether for small findings, but allow break for larger ones
            story.append(KeepTogether(card_elements))

            # Separator between findings in same category
            if finding != cat_findings[-1]:
                story.append(Spacer(1, 4))
                story.append(HRFlowable(width="90%", thickness=0.5, color=MID_GRAY,
                                        spaceAfter=4, spaceBefore=4))


def build_strengths(story, styles):
    """Section 6: Strengths."""
    story.append(PageBreak())
    story.append(Paragraph("6. PONTOS FORTES E CONTROLES VÁLIDOS", styles["SectionTitle"]))
    story.append(HRFlowable(width="100%", thickness=1, color=STRENGTH_COLOR, spaceAfter=8))

    intro = (
        "A auditoria também identificou <b>13 controles de segurança</b> que estão funcionando "
        "corretamente. Estes pontos representam uma base sólida que deve ser mantida e expandida."
    )
    story.append(Paragraph(intro, styles["BodyText2"]))
    story.append(Spacer(1, 6))

    # Strengths table
    strength_data = [
        [Paragraph("<b>#</b>", styles["TableHeader"]),
         Paragraph("<b>Controle</b>", styles["TableHeader"]),
         Paragraph("<b>Status</b>", styles["TableHeader"])],
    ]
    for i, s in enumerate(STRENGTHS, 1):
        strength_data.append([
            Paragraph(str(i), styles["TableCell"]),
            Paragraph(s, styles["TableCell"]),
            Paragraph("<font color='#059669'><b>✓ VÁLIDO</b></font>", styles["TableCell"]),
        ])

    s_table = Table(strength_data, colWidths=[1*cm, PAGE_W - 2*MARGIN - 3*cm, 2*cm])
    s_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), STRENGTH_COLOR),
        ("TEXTCOLOR", (0, 0), (-1, 0), white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, HexColor("#ECFDF5")]),
        ("GRID", (0, 0), (-1, -1), 0.5, MID_GRAY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("ALIGN", (2, 1), (2, -1), "CENTER"),
    ]))
    story.append(s_table)


def build_recommendations(story, styles):
    """Section 7: Recommendations."""
    story.append(Spacer(1, 10))
    story.append(Paragraph("7. RECOMENDAÇÕES PRIORIZADAS", styles["SectionTitle"]))
    story.append(HRFlowable(width="100%", thickness=1, color=ACCENT, spaceAfter=8))

    intro = (
        "As seguintes recomendações estão ordenadas por prioridade de implementação. "
        "A prioridade P1 deve ser executada imediatamente."
    )
    story.append(Paragraph(intro, styles["BodyText2"]))
    story.append(Spacer(1, 6))

    rec_data = [
        [Paragraph("<b>Prioridade</b>", styles["TableHeader"]),
         Paragraph("<b>Ação</b>", styles["TableHeader"]),
         Paragraph("<b>Severidade</b>", styles["TableHeader"])],
    ]
    for priority, action, sev in RECOMMENDATIONS:
        sev_color = SEVERITY_COLORS.get(sev, "#64748B")
        rec_data.append([
            Paragraph(f"<b>{priority}</b>", styles["TableCell"]),
            Paragraph(action, styles["TableCell"]),
            Paragraph(f"<font color='{sev_color}'><b>{sev}</b></font>", styles["TableCell"]),
        ])

    r_table = Table(rec_data, colWidths=[2*cm, PAGE_W - 2*MARGIN - 5.5*cm, 3.5*cm])
    r_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, LIGHT_GRAY]),
        ("GRID", (0, 0), (-1, -1), 0.5, MID_GRAY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("ALIGN", (0, 1), (0, -1), "CENTER"),
        ("ALIGN", (2, 1), (2, -1), "CENTER"),
    ]))
    story.append(r_table)


def build_github_issues(story, styles):
    """Section 8: GitHub issues."""
    story.append(PageBreak())
    story.append(Paragraph("8. ISSUES PARA GITHUB", styles["SectionTitle"]))
    story.append(HRFlowable(width="100%", thickness=1, color=ACCENT, spaceAfter=8))

    intro = (
        "As issues abaixo estão formatadas para criação direta no GitHub. "
        "Cada issue inclui título, labels e corpo descritivo."
    )
    story.append(Paragraph(intro, styles["BodyText2"]))
    story.append(Spacer(1, 6))

    for issue in GITHUB_ISSUES:
        # Issue header
        labels_str = ", ".join([f"<font color='#3B82F6'><b>{l}</b></font>" for l in issue["labels"]])
        header_text = f"<b>ISSUE #{issue['number']}: {issue['title']}</b>"
        story.append(Paragraph(header_text, styles["IssueTitle"]))
        story.append(Paragraph(f"Labels: {labels_str}", styles["SmallText"]))
        story.append(Spacer(1, 3))

        # Issue body in a code-like box
        body_lines = issue["body"].split("\n")
        body_formatted = issue["body"].replace("\n", "<br/>")
        body_formatted = body_formatted.replace("**", "<b>").replace("**", "</b>")

        # Simple markdown to reportlab conversion
        body_formatted = issue["body"]
        # Handle ## headers
        import re
        body_formatted = re.sub(r'^## (.+)$', r'<b>\1</b>', body_formatted, flags=re.MULTILINE)
        # Handle **bold**
        body_formatted = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', body_formatted)
        # Handle - bullets
        body_formatted = re.sub(r'^- (.+)$', r'• \1', body_formatted, flags=re.MULTILINE)
        # Handle numbered lists
        body_formatted = re.sub(r'^(\d+)\. (.+)$', r'\1. \2', body_formatted, flags=re.MULTILINE)
        # Convert newlines
        body_formatted = body_formatted.replace("\n", "<br/>")

        body_style = ParagraphStyle(
            "issue_body", fontSize=8.5, fontName="Courier",
            textColor=TEXT_DARK, leading=12, backColor=LIGHT_GRAY,
            borderPadding=8, spaceAfter=4,
        )
        story.append(Paragraph(body_formatted, body_style))

        story.append(Spacer(1, 8))
        if issue != GITHUB_ISSUES[-1]:
            story.append(HRFlowable(width="100%", thickness=0.5, color=MID_GRAY, spaceAfter=6))


def build_conclusion(story, styles):
    """Section 9: Conclusion."""
    story.append(Spacer(1, 10))
    story.append(Paragraph("9. CONCLUSÃO", styles["SectionTitle"]))
    story.append(HRFlowable(width="100%", thickness=1, color=ACCENT, spaceAfter=8))

    conclusion_text = (
        "O Projeto Jefrey demonstra uma base sólida de controles de segurança, com 13 mecanismos "
        "validados incluindo autenticação Bearer, content guard, RBAC no ToolExecutor e validação "
        "UUID. No entanto, a auditoria identificou lacunas críticas em <b>isolamento de dados</b> e "
        "<b>autorização</b> que devem ser tratadas com urgência."
    )
    story.append(Paragraph(conclusion_text, styles["BodyText2"]))
    story.append(Spacer(1, 4))

    conclusion_text2 = (
        "A ação imediata deve focar nos <b>2 achados críticos</b> (P1 e P6) e nos <b>3 achados "
        "altos</b> (P2 e P3). A implementação das 7 recomendações priorizadas elevará "
        "significativamente o postura de segurança do sistema e o preparará para um deploy "
        "multiusuário seguro em produção."
    )
    story.append(Paragraph(conclusion_text2, styles["BodyText2"]))
    story.append(Spacer(1, 4))

    conclusion_text3 = (
        "Recomenda-se uma nova auditoria de segurança após a implementação das recomendações "
        "P1–P3 para validar as correções e identificar possíveis regressões."
    )
    story.append(Paragraph(conclusion_text3, styles["BodyText2"]))

    story.append(Spacer(1, 20))

    # Signature block
    sig_data = [
        [Paragraph("<b>Auditor Responsável</b>", styles["BodyText2"]),
         Paragraph(f"<b>Data:</b> {datetime.now().strftime('%d/%m/%Y')}", styles["BodyText2"])],
        [Paragraph("Jefrey Security Audit Team", styles["SmallText"]),
         Paragraph("Versão 1.0", styles["SmallText"])],
    ]
    sig_table = Table(sig_data, colWidths=[PAGE_W/2 - MARGIN, PAGE_W/2 - MARGIN])
    sig_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEABOVE", (0, 0), (0, 0), 1, TEXT_DARK),
        ("LINEABOVE", (1, 0), (1, 0), 1, TEXT_DARK),
    ]))
    story.append(sig_table)


def main():
    output_path = os.path.join(os.path.dirname(__file__), "relatorio-auditoria-seguranca.pdf")

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN + 10,  # Extra space for header
        bottomMargin=MARGIN + 5,
        title="Relatório de Auditoria de Segurança — Projeto Jefrey",
        author="Jefrey Security Audit Team",
        subject="Auditoria de Segurança",
    )

    styles = build_styles()
    story = []

    # Build all sections
    build_cover(story, styles)
    build_toc(story, styles)
    build_overview(story, styles)
    build_stack(story, styles)
    build_executive_summary(story, styles)
    story.append(PageBreak())
    build_charts(story, styles)
    story.append(PageBreak())
    build_findings(story, styles)
    build_strengths(story, styles)
    build_recommendations(story, styles)
    build_github_issues(story, styles)
    build_conclusion(story, styles)

    # Build PDF with different templates for cover vs content pages
    def first_page(canvas, doc):
        """Cover page - no header/footer."""
        pass

    def later_pages(canvas, doc):
        """Content pages - with header/footer."""
        header_footer(canvas, doc)

    doc.build(story, onFirstPage=first_page, onLaterPages=later_pages)
    print(f"PDF gerado com sucesso: {output_path}")

    # Verify
    file_size = os.path.getsize(output_path)
    print(f"Tamanho do arquivo: {file_size:,} bytes ({file_size/1024:.1f} KB)")

    # Count pages using reportlab's reader
    from reportlab.lib.utils import open_for_read
    try:
        import PyPDF2
        with open(output_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            print(f"Número de páginas: {len(reader.pages)}")
    except ImportError:
        print("(PyPDF2 não instalado — verificação de páginas pulada)")

    return output_path


if __name__ == "__main__":
    main()
