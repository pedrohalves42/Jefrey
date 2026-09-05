"""CLI do Jefrey desacoplado (consome a API HTTP FastAPI - Fase P5).

Uso:
  python -m src.jefrey.cli.main chat "Olá, Jefrey!"
  python -m src.jefrey.cli.main approvals list
  python -m src.jefrey.cli.main approvals decide <ID> approved
"""
from __future__ import annotations

import os
import sys
import time
import httpx
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

app = typer.Typer(
    name="jefrey",
    help="CLI do Assistente Jefrey (conectado via API)",
    add_completion=False,
)
approvals_app = typer.Typer(help="Gerenciamento de aprovações HITL")
memory_app = typer.Typer(help="Consulta de memória vetorial")

app.add_typer(approvals_app, name="approvals")
app.add_typer(memory_app, name="memory")

console = Console()

def get_base_url() -> str:
    return os.environ.get("JEFREY_API_URL", "http://localhost:8000")

def get_auth_headers() -> dict[str, str]:
    from src.jefrey.core.config import get_settings
    secret = os.environ.get("JEFREY_API__SECRET_KEY") or get_settings().api.secret_key
    if secret:
        return {"Authorization": f"Bearer {secret}"}
    return {}

@app.command(name="chat")
def chat_cmd(
    message: str = typer.Argument(..., help="Mensagem para enviar ao assistente"),
    thread_id: str = typer.Option("default", "--thread", "-t", help="ID da conversa/thread"),
    url: str = typer.Option(None, "--url", "-u", help="URL base da API Jefrey"),
):
    """Envia uma mensagem ao assistente via API REST."""
    base_url = url or get_base_url()
    headers = get_auth_headers()

    with console.status("[bold green]Processando..."):
        try:
            with httpx.Client(base_url=base_url, timeout=30.0) as client:
                res = client.post("/chat", json={"message": message, "thread_id": thread_id}, headers=headers)
        except Exception as e:
            console.print(f"[bold red]Erro de conexão com API em {base_url}: {e}[/bold red]")
            sys.exit(1)

    if res.status_code == 400:
        console.print(f"[bold red]Bloqueado/Erro 400:[/bold red] {res.json().get('detail')}")
        return

    if res.status_code != 200:
        console.print(f"[bold red]Erro {res.status_code}:[/bold red] {res.text}")
        return

    data = res.json()
    status = data.get("status")

    if status == "complete":
        console.print(Panel(data.get("response", ""), title="Jefrey", border_style="cyan"))
    elif status == "pending_approval":
        aid = data.get("approval_id")
        console.print(Panel(
            f"[bold yellow]Ação requer aprovação humana (HITL)![/bold yellow]\n\n"
            f"• Approval ID: [bold]{aid}[/bold]\n"
            f"• Thread ID: {thread_id}\n\n"
            f"Para aprovar: [cyan]python -m src.jefrey.cli.main approvals decide {aid} approved[/cyan]\n"
            f"Para rejeitar: [red]python -m src.jefrey.cli.main approvals decide {aid} rejected[/red]",
            title="⚠️ HITL Pendente",
            border_style="yellow",
        ))
    elif status == "running":
        console.print("[dim]Execucao longa iniciada, aguardando conclusao...[/dim]")
        # Poll /chat/status/{thread_id} com backoff 1.5->5s, 60s
        deadline = time.time() + 60
        delay = 1.5
        while time.time() < deadline:
            try:
                with httpx.Client(base_url=base_url, timeout=10.0) as poll_c:
                    r2 = poll_c.get(f"/chat/status/{thread_id}", headers=headers)
                    j2 = r2.json()
                    s2 = j2.get("status")
                    if s2 == "complete":
                        console.print(Panel(j2.get("response", ""), title="Jefrey", border_style="cyan"))
                        return
                    if s2 == "error":
                        console.print(f"[bold red]Erro:[/bold red] {j2.get('message') or j2}")
                        return
                    if s2 == "pending_approval":
                        aid = j2.get("approval_id")
                        console.print(Panel(f"[bold yellow]Aprovacao pendente![/bold yellow] ID: {aid}", title="HITL", border_style="yellow"))
                        return
            except Exception as e:
                console.print(f"[dim]poll erro (retry): {e}[/dim]")
            time.sleep(delay)
            delay = min(delay * 1.2, 5.0)
        console.print("[bold red]Polling timeout (60s) — tente: GET /chat/status/{thread_id}[/bold red]")
    else:
        console.print(f"Status: {status} - {data.get('message', '')}")

@approvals_app.command(name="list")
def list_pending(
    url: str = typer.Option(None, "--url", "-u", help="URL base da API"),
):
    """Lista aprovações pendentes."""
    base_url = url or get_base_url()
    headers = get_auth_headers()

    try:
        with httpx.Client(base_url=base_url, timeout=10.0) as client:
            res = client.get("/approvals/pending", headers=headers)
    except Exception as e:
        console.print(f"[bold red]Erro ao consultar approvals: {e}[/bold red]")
        sys.exit(1)

    if res.status_code != 200:
        console.print(f"[bold red]Erro {res.status_code}:[/bold red] {res.text}")
        return

    data = res.json()
    items = data.get("pending", [])
    if not items:
        console.print("[dim]Nenhuma aprovação pendente.[/dim]")
        return

    table = Table(title="Aprovações HITL Pendentes")
    table.add_column("ID", style="cyan")
    table.add_column("Ferramenta", style="magenta")
    table.add_column("Risco", style="yellow")
    table.add_column("Thread", style="dim")
    table.add_column("Expira Em", style="dim")

    for item in items:
        table.add_row(
            item.get("id"),
            item.get("tool_name"),
            item.get("risk_level", "").upper(),
            item.get("thread_id"),
            item.get("expires_at", "—"),
        )
    console.print(table)

@approvals_app.command(name="decide")
def decide_approval(
    approval_id: str = typer.Argument(..., help="ID da aprovação"),
    decision: str = typer.Argument(..., help="approved | rejected"),
    url: str = typer.Option(None, "--url", "-u", help="URL base da API"),
):
    """Decide (aprova ou rejeita) uma solicitação pendente."""
    base_url = url or get_base_url()
    headers = get_auth_headers()

    try:
        with httpx.Client(base_url=base_url, timeout=10.0) as client:
            res = client.post(
                f"/approvals/{approval_id}/decide",
                json={"decision": decision, "decided_by": "cli_user"},
                headers=headers,
            )
    except Exception as e:
        console.print(f"[bold red]Erro ao decidir approval: {e}[/bold red]")
        sys.exit(1)

    if res.status_code == 200 and res.json().get("ok"):
        console.print(f"[bold green]✓ Aprovação {approval_id} decidida como '{decision}'[/bold green]")
    else:
        console.print(f"[bold red]✗ Falha ao decidir: {res.text}[/bold red]")

@memory_app.command(name="search")
def search_memory_cmd(
    query: str = typer.Argument(..., help="Termo para busca semântica"),
    limit: int = typer.Option(5, "--limit", "-l", help="Limite de resultados"),
    url: str = typer.Option(None, "--url", "-u", help="URL base da API"),
):
    """Busca termos na memória vetorial de longo prazo."""
    base_url = url or get_base_url()
    headers = get_auth_headers()
    try:
        with httpx.Client(base_url=base_url, timeout=10.0) as client:
            res = client.get("/memory/search", params={"q": query, "limit": limit}, headers=headers)
    except Exception as e:
        console.print(f"[bold red]Erro ao buscar na memória: {e}[/bold red]")
        sys.exit(1)

    if res.status_code != 200:
        console.print(f"[bold red]Erro {res.status_code}:[/bold red] {res.text}")
        return

    data = res.json()
    memories = data.get("memories", [])
    if not memories:
        console.print("[dim]Nenhuma memória relevante encontrada.[/dim]")
        return

    table = Table(title=f"Resultados da Memória ({len(memories)})")
    table.add_column("Conteúdo", style="cyan")
    table.add_column("Similaridade", style="green")

    for m in memories:
        sim = f"{m.get('similarity', 0.0):.1%}" if isinstance(m.get('similarity'), (int, float)) else str(m.get('similarity', ''))
        table.add_row(m.get("content", ""), sim)
    console.print(table)

def main():
    app()

if __name__ == "__main__":
    main()
