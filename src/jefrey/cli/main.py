"""P5 â€” Jefrey CLI Client.

Cliente de linha de comando que consome a API REST do Jefrey.
Comandos: chat, approvals (list/decide), memory (search), stt, tts.
"""
from __future__ import annotations

import os
import json
from typing import Optional

import httpx
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

app = typer.Typer(
    name="jefrey",
    help="Jefrey AI Assistant CLI",
    add_completion=False,
    rich_markup_mode="rich",
)

console = Console()

# Config
API_BASE = os.getenv("JEFREY_API_BASE", "http://localhost:8000")
DEFAULT_TIMEOUT = 30.0

# Global state
_current_token: Optional[str] = None
_current_user_id: str = "cli-user"


def get_client(token: Optional[str] = None) -> httpx.Client:
    """Cria cliente HTTP com headers de auth."""
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    elif _current_token:
        headers["Authorization"] = f"Bearer {_current_token}"
    return httpx.Client(base_url=API_BASE, headers=headers, timeout=DEFAULT_TIMEOUT)


def get_async_client(token: Optional[str] = None) -> httpx.AsyncClient:
    """Cria cliente HTTP assÃ­ncrono com headers de auth."""
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    elif _current_token:
        headers["Authorization"] = f"Bearer {_current_token}"
    return httpx.AsyncClient(base_url=API_BASE, headers=headers, timeout=DEFAULT_TIMEOUT)


# â”€â”€ Auth commands â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

auth_app = typer.Typer(name="auth", help="AutenticaÃ§Ã£o e tokens")
app.add_typer(auth_app)


@auth_app.command("dev-token")
def auth_dev_token(
    user_id: str = typer.Option("cli-user", "--user", "-u", help="User ID para o token"),
    base_url: str = typer.Option(API_BASE, "--base-url", help="Base URL da API"),
):
    """ObtÃ©m token de desenvolvimento (sÃ³ funciona em ambiente dev)."""
    global _current_token, _current_user_id

    with get_client() as client:
        try:
            resp = client.post("/auth/dev-token", json={"user_id": user_id})
            if resp.status_code == 403:
                console.print("[red]dev-token desabilitado em produÃ§Ã£o[/red]")
                raise typer.Exit(1)
            resp.raise_for_status()
            data = resp.json()
            _current_token = data["token"]
            _current_user_id = data.get("user_id", user_id)
            console.print(f"[green]Token obtido:[/green] {_current_token[:16]}...")
            console.print(f"User ID: {_current_user_id}")
            console.print(f"Expira em: {data.get('expires_in', 'N/A')}s")
        except httpx.HTTPStatusError as e:
            console.print(f"[red]Erro HTTP {e.response.status_code}:[/red] {e.response.text}")
            raise typer.Exit(1)
        except Exception as e:
            console.print(f"[red]Erro:[/red] {e}")
            raise typer.Exit(1)


@auth_app.command("login")
def auth_login(
    base_url: str = typer.Option(API_BASE, "--base-url", help="Base URL da API"),
):
    """Inicia fluxo OAuth2 Google (abre browser)."""
    with get_client() as client:
        try:
            resp = client.get("/auth/google/login")
            resp.raise_for_status()
            data = resp.json()
            auth_url = data["auth_url"]
            state = data["state"]
            console.print(f"[blue]Abra no browser:[/blue] {auth_url}")
            console.print(f"State (guarde para validar): {state}")
        except Exception as e:
            console.print(f"[red]Erro:[/red] {e}")
            raise typer.Exit(1)


# â”€â”€ Chat commands â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

chat_app = typer.Typer(name="chat", help="Conversa com o agente")
app.add_typer(chat_app)


@chat_app.command("")
def chat_send(
    message: str = typer.Argument(..., help="Mensagem para enviar"),
    thread_id: str = typer.Option("default", "--thread", "-t", help="Thread ID"),
    stream: bool = typer.Option(False, "--stream", "-s", help="Stream response"),
    base_url: str = typer.Option(API_BASE, "--base-url", help="Base URL da API"),
):
    """Envia mensagem para o agente."""
    with get_client() as client:
        try:
            payload = {"message": message, "thread_id": thread_id}
            if stream:
                # Streaming
                with client.stream("POST", "/chat", json=payload) as resp:
                    resp.raise_for_status()
                    console.print(f"[dim]Thread:[/dim] {thread_id}")
                    console.print("[bold green]Jefrey:[/bold green] ", end="")
                    for chunk in resp.iter_text():
                        console.print(chunk, end="")
                    console.print()
            else:
                resp = client.post("/chat", json=payload)
                resp.raise_for_status()
                data = resp.json()
                _print_chat_response(data)
        except httpx.HTTPStatusError as e:
            console.print(f"[red]Erro HTTP {e.response.status_code}:[/red] {e.response.text}")
            raise typer.Exit(1)
        except Exception as e:
            console.print(f"[red]Erro:[/red] {e}")
            raise typer.Exit(1)


@chat_app.command("resume")
def chat_resume(
    thread_id: str = typer.Argument(..., help="Thread ID para retomar"),
    base_url: str = typer.Option(API_BASE, "--base-url", help="Base URL da API"),
):
    """Retoma thread suspensa por aprovaÃ§Ã£o HITL."""
    with get_client() as client:
        try:
            resp = client.post(f"/chat/resume/{thread_id}")
            resp.raise_for_status()
            data = resp.json()
            _print_chat_response(data)
        except httpx.HTTPStatusError as e:
            console.print(f"[red]Erro HTTP {e.response.status_code}:[/red] {e.response.text}")
            raise typer.Exit(1)


@chat_app.command("status")
def chat_status(
    thread_id: str = typer.Argument(..., help="Thread ID"),
    base_url: str = typer.Option(API_BASE, "--base-url", help="Base URL da API"),
):
    """Consulta status de uma thread."""
    with get_client() as client:
        try:
            resp = client.get(f"/chat/status/{thread_id}")
            resp.raise_for_status()
            data = resp.json()
            console.print(Panel.fit(json.dumps(data, indent=2, ensure_ascii=False), title=f"Thread {thread_id}"))
        except httpx.HTTPStatusError as e:
            console.print(f"[red]Erro HTTP {e.response.status_code}:[/red] {e.response.text}")
            raise typer.Exit(1)


def _print_chat_response(data: dict):
    """Formata resposta do chat para CLI."""
    status = data.get("status", "unknown")

    if status == "pending_approval":
        approval_id = data.get("approval_id", "N/A")
        tool = data.get("tool", "N/A")
        console.print(Panel(
            f"[yellow]â³ Aguardando aprovaÃ§Ã£o HITL[/yellow]\n"
            f"Approval ID: {approval_id}\n"
            f"Ferramenta: {tool}\n"
            f"Use: [bold]jefrey approvals decide {approval_id} approve[/bold]",
            title="HITL Pendente",
            border_style="yellow"
        ))
    elif status == "completed":
        response = data.get("response", "")
        console.print(f"[bold green]Jefrey:[/bold green] {response}")
    elif status == "error":
        console.print(f"[red]Erro:[/red] {data.get('error', 'Desconhecido')}")
    else:
        console.print(Panel.fit(json.dumps(data, indent=2, ensure_ascii=False), title=f"Status: {status}"))


# â”€â”€ Approvals commands â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

approvals_app = typer.Typer(name="approvals", help="Gerenciar aprovaÃ§Ãµes HITL")
app.add_typer(approvals_app)


@approvals_app.command("list")
def approvals_list(
    base_url: str = typer.Option(API_BASE, "--base-url", help="Base URL da API"),
):
    """Lista aprovaÃ§Ãµes pendentes."""
    with get_client() as client:
        try:
            resp = client.get("/approvals/pending")
            resp.raise_for_status()
            data = resp.json()

            if not data:
                console.print("[dim]Nenhuma aprovaÃ§Ã£o pendente[/dim]")
                return

            table = Table(title="AprovaÃ§Ãµes Pendentes")
            table.add_column("ID", style="cyan")
            table.add_column("Ferramenta", style="green")
            table.add_column("Risco", style="red")
            table.add_column("Thread", style="blue")
            table.add_column("Motivo")

            for a in data:
                table.add_row(
                    a.get("id", "")[:12],
                    a.get("tool_name", ""),
                    a.get("risk_level", ""),
                    a.get("thread_id", ""),
                    a.get("reason", "")[:50]
                )
            console.print(table)
        except httpx.HTTPStatusError as e:
            console.print(f"[red]Erro HTTP {e.response.status_code}:[/red] {e.response.text}")
            raise typer.Exit(1)


@approvals_app.command("decide")
def approvals_decide(
    approval_id: str = typer.Argument(..., help="Approval ID"),
    decision: str = typer.Argument(..., help="approve ou reject"),
    reason: str = typer.Option("", "--reason", "-r", help="Motivo da decisÃ£o"),
    base_url: str = typer.Option(API_BASE, "--base-url", help="Base URL da API"),
):
    """Decide uma aprovaÃ§Ã£o pendente."""
    if decision not in ("approve", "reject"):
        console.print("[red]DecisÃ£o deve ser 'approve' ou 'reject'[/red]")
        raise typer.Exit(1)

    with get_client() as client:
        try:
            resp = client.post(
                f"/approvals/{approval_id}/decide",
                json={"decision": decision, "reason": reason}
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("ok"):
                console.print(f"[green]AprovaÃ§Ã£o {decision}d com sucesso[/green]")
            else:
                console.print(f"[red]Falha:[/red] {data.get('error', 'Desconhecido')}")
        except httpx.HTTPStatusError as e:
            console.print(f"[red]Erro HTTP {e.response.status_code}:[/red] {e.response.text}")
            raise typer.Exit(1)


# â”€â”€ Memory commands â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

memory_app = typer.Typer(name="memory", help="Busca e gerencia memÃ³ria")
app.add_typer(memory_app)


@memory_app.command("search")
def memory_search(
    query: str = typer.Argument(..., help="Termo de busca"),
    limit: int = typer.Option(5, "--limit", "-l", help="Limite de resultados"),
    base_url: str = typer.Option(API_BASE, "--base-url", help="Base URL da API"),
):
    """Busca memÃ³rias por similaridade semÃ¢ntica."""
    with get_client() as client:
        try:
            resp = client.get("/memory/search", params={"q": query, "limit": limit})
            resp.raise_for_status()
            data = resp.json()

            memories = data.get("memories", [])
            if not memories:
                console.print("[dim]Nenhuma memÃ³ria encontrada[/dim]")
                return

            table = Table(title=f"MemÃ³rias para: {query}")
            table.add_column("Score", justify="right", style="cyan")
            table.add_column("ConteÃºdo", style="white")
            table.add_column("Tipo", style="green")

            for m in memories:
                score = m.get("score", m.get("similarity", 0))
                content = m.get("content", m.get("text", ""))[:100]
                type_ = m.get("type", m.get("layer", ""))
                table.add_row(f"{score:.3f}", content, type_)

            console.print(table)
            console.print(f"[dim]Total: {data.get('count', len(memories))}[/dim]")
        except httpx.HTTPStatusError as e:
            console.print(f"[red]Erro HTTP {e.response.status_code}:[/red] {e.response.text}")
            raise typer.Exit(1)


@memory_app.command("add")
def memory_add(
    content: str = typer.Argument(..., help="ConteÃºdo da memÃ³ria"),
    title: str = typer.Option("", "--title", "-t", help="TÃ­tulo opcional"),
    type_: str = typer.Option("note", "--type", help="Tipo (note, doc, etc)"),
    base_url: str = typer.Option(API_BASE, "--base-url", help="Base URL da API"),
):
    """Adiciona memÃ³ria ao longo prazo."""
    with get_client() as client:
        try:
            resp = client.post("/memory/add", json={
                "content": content,
                "title": title,
                "type": type_
            })
            resp.raise_for_status()
            data = resp.json()
            console.print(f"[green]MemÃ³ria salva:[/green] ID={data.get('id')}, chars={data.get('chars')}")
        except httpx.HTTPStatusError as e:
            console.print(f"[red]Erro HTTP {e.response.status_code}:[/red] {e.response.text}")
            raise typer.Exit(1)


@memory_app.command("health")
def memory_health(
    base_url: str = typer.Option(API_BASE, "--base-url", help="Base URL da API"),
):
    """Health check do sistema de memÃ³ria."""
    with get_client() as client:
        try:
            resp = client.get("/memory/health")
            resp.raise_for_status()
            data = resp.json()
            console.print(Panel.fit(json.dumps(data, indent=2, ensure_ascii=False), title="Memory Health"))
        except httpx.HTTPStatusError as e:
            console.print(f"[red]Erro HTTP {e.response.status_code}:[/red] {e.response.text}")
            raise typer.Exit(1)


# â”€â”€ STT commands â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

stt_app = typer.Typer(name="stt", help="Speech-to-Text")
app.add_typer(stt_app)


@stt_app.command("transcribe")
def stt_transcribe(
    audio_file: str = typer.Argument(..., help="Arquivo de Ã¡udio (WAV/MP3)"),
    base_url: str = typer.Option(API_BASE, "--base-url", help="Base URL da API"),
):
    """Transcreve arquivo de Ã¡udio."""
    if not os.path.exists(audio_file):
        console.print(f"[red]Arquivo nÃ£o encontrado:[/red] {audio_file}")
        raise typer.Exit(1)

    with get_client() as client:
        try:
            with open(audio_file, "rb") as f:
                files = {"audio": (os.path.basename(audio_file), f, "audio/wav")}
                # Need to remove Content-Type for multipart
                client.headers.pop("Content-Type", None)
                resp = client.post("/stt", files=files)
                client.headers["Content-Type"] = "application/json"
            resp.raise_for_status()
            data = resp.json()
            console.print(f"[bold green]TranscriÃ§Ã£o:[/bold green] {data.get('transcript', '')}")
            console.print(f"[dim]DuraÃ§Ã£o: {data.get('duration', 'N/A')}s[/dim]")
        except httpx.HTTPStatusError as e:
            console.print(f"[red]Erro HTTP {e.response.status_code}:[/red] {e.response.text}")
            raise typer.Exit(1)
        except Exception as e:
            console.print(f"[red]Erro:[/red] {e}")
            raise typer.Exit(1)


@stt_app.command("health")
def stt_health(
    base_url: str = typer.Option(API_BASE, "--base-url", help="Base URL da API"),
):
    """Health check do STT."""
    with get_client() as client:
        try:
            resp = client.get("/stt/health")
            resp.raise_for_status()
            data = resp.json()
            console.print(Panel.fit(json.dumps(data, indent=2, ensure_ascii=False), title="STT Health"))
        except httpx.HTTPStatusError as e:
            console.print(f"[red]Erro HTTP {e.response.status_code}:[/red] {e.response.text}")
            raise typer.Exit(1)


# â”€â”€ TTS commands â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

tts_app = typer.Typer(name="tts", help="Text-to-Speech")
app.add_typer(tts_app)


@tts_app.command("synthesize")
def tts_synthesize(
    text: str = typer.Argument(..., help="Texto para sintetizar"),
    output: str = typer.Option("output.mp3", "--output", "-o", help="Arquivo de saÃ­da"),
    voice: str = typer.Option(None, "--voice", "-v", help="Voice ID (ex: pt_BR-faber-medium, Charon)"),
    format: str = typer.Option("mp3", "--format", "-f", help="mp3 ou wav"),
    base_url: str = typer.Option(API_BASE, "--base-url", help="Base URL da API"),
):
    """Sintetiza texto em Ã¡udio."""
    with get_client() as client:
        try:
            payload = {"text": text, "format": format}
            if voice:
                payload["voice_id"] = voice
            resp = client.post("/tts", json=payload)
            resp.raise_for_status()

            audio_bytes = resp.content
            with open(output, "wb") as f:
                f.write(audio_bytes)

            console.print(f"[green]Ãudio salvo:[/green] {output} ({len(audio_bytes)} bytes)")
            console.print(f"[dim]Provider: {resp.headers.get('X-TTS-Provider', 'N/A')}[/dim]")
            console.print(f"[dim]Voice: {resp.headers.get('X-TTS-Voice', 'N/A')}[/dim]")
        except httpx.HTTPStatusError as e:
            console.print(f"[red]Erro HTTP {e.response.status_code}:[/red] {e.response.text}")
            raise typer.Exit(1)


@tts_app.command("voices")
def tts_voices(
    base_url: str = typer.Option(API_BASE, "--base-url", help="Base URL da API"),
):
    """Lista vozes disponÃ­veis."""
    with get_client() as client:
        try:
            resp = client.get("/tts/voices")
            resp.raise_for_status()
            data = resp.json()

            table = Table(title="Vozes DisponÃ­veis")
            table.add_column("ID", style="cyan")
            table.add_column("Nome", style="green")
            table.add_column("Provider", style="blue")

            for v in data.get("voices", []):
                table.add_row(v.get("id", ""), v.get("name", ""), v.get("provider", ""))

            console.print(table)
        except httpx.HTTPStatusError as e:
            console.print(f"[red]Erro HTTP {e.response.status_code}:[/red] {e.response.text}")
            raise typer.Exit(1)


@tts_app.command("health")
def tts_health(
    base_url: str = typer.Option(API_BASE, "--base-url", help="Base URL da API"),
):
    """Health check do TTS."""
    with get_client() as client:
        try:
            resp = client.get("/tts/health")
            resp.raise_for_status()
            data = resp.json()
            console.print(Panel.fit(json.dumps(data, indent=2, ensure_ascii=False), title="TTS Health"))
        except httpx.HTTPStatusError as e:
            console.print(f"[red]Erro HTTP {e.response.status_code}:[/red] {e.response.text}")
            raise typer.Exit(1)


# â”€â”€ System commands â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

# System commands (integrated into main app)
# System commands integrated into main app
# (health, version already at root level)

# Actually just add a simple health check to main app
@app.command("health")
def health_check(
    base_url: str = typer.Option(API_BASE, "--base-url", help="Base URL da API"),
):
    """Health check geral da API."""
    with get_client() as client:
        try:
            resp = client.get("/health")
            resp.raise_for_status()
            data = resp.json()
            console.print(Panel.fit(json.dumps(data, indent=2, ensure_ascii=False), title="API Health"))
        except httpx.HTTPStatusError as e:
            console.print(f"[red]Erro HTTP {e.response.status_code}:[/red] {e.response.text}")
            raise typer.Exit(1)


@app.command("version")
def version():
    """Mostra versÃ£o do CLI."""
    from src.jefrey.core.config import get_settings
    cfg = get_settings()
    console.print(f"Jefrey CLI v{cfg.version}")


@app.command("doctor")
def doctor(
    base_url: str = typer.Option("http://localhost:8000", help="Endereco do servidor do Jefrey"),
    ollama_url: str = typer.Option("http://localhost:11434", help="Endereco do Ollama"),
):
    """Diagnostica o ambiente e mostra como resolver cada problema."""
    from pathlib import Path
    from src.jefrey.core.doctor import FAIL, OK, WARN, Probes, run_checks, summarize

    checks = run_checks(Probes(base_url=base_url.rstrip("/"), ollama_url=ollama_url.rstrip("/"), project_dir=Path.cwd()))
    icon = {OK: "[green]OK[/green]", WARN: "[yellow]AVISO[/yellow]", FAIL: "[red]PROBLEMA[/red]"}
    table = Table(title="Diagnostico do Jefrey")
    table.add_column("", no_wrap=True)
    table.add_column("Item")
    table.add_column("Situacao")
    for ch in checks:
        table.add_row(icon[ch.status], ch.label, ch.detail)
    console.print(table)
    problems = [ch for ch in checks if ch.status != OK and ch.fix]
    if problems:
        console.print("\n[bold]Como resolver:[/bold]")
        for ch in problems:
            console.print(f"  - {ch.label}: {ch.fix}")
    ok, warn, fail = summarize(checks)
    console.print(f"\n{ok} ok, {warn} aviso(s), {fail} problema(s).")
    raise typer.Exit(code=1 if fail else 0)


@app.command("backup")
def backup(
    out: str = typer.Option("backups", help="Pasta onde guardar o arquivo .zip"),
    include_secrets: bool = typer.Option(False, "--incluir-segredos", help="Inclui chaves e tokens (guarde o arquivo em local seguro!)"),
    no_db: bool = typer.Option(False, "--sem-banco", help="Nao exporta o banco de dados (Postgres)"),
):
    """Salva configuracao, memorias, arquivos e banco em um unico .zip."""
    from pathlib import Path
    from src.jefrey.core.backup import BackupError, create_backup, docker_pg_dump

    try:
        path = create_backup(Path(out), config_dir=Path("config"), data_dir=Path("data"),
                             include_secrets=include_secrets, db_dump=None if no_db else docker_pg_dump)
    except BackupError as e:
        console.print(f"[red]{e}[/red]  (use --sem-banco para salvar so arquivos)")
        raise typer.Exit(code=1)
    size = path.stat().st_size / 1024 / 1024
    console.print(f"[green]Backup salvo:[/green] {path} ({size:.1f} MB)")
    if include_secrets:
        console.print("[yellow]Este arquivo contem chaves e tokens. Nao compartilhe.[/yellow]")


@app.command("restore")
def restore(
    file: str = typer.Argument(..., help="Arquivo .zip gerado por 'jefrey backup'"),
    yes: bool = typer.Option(False, "--sim", help="Nao pedir confirmacao"),
    no_db: bool = typer.Option(False, "--sem-banco", help="Nao restaura o banco de dados"),
):
    """Restaura um backup. O que existe hoje e guardado em pastas '.antes-da-restauracao-...'."""
    from pathlib import Path
    from src.jefrey.core.backup import BackupError, docker_pg_restore, read_manifest, restore_backup

    try:
        m = read_manifest(Path(file))
    except BackupError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=1)
    console.print(f"Backup de {m.get('created')}: {m.get('counts')}")
    if not yes and not typer.confirm("Restaurar agora? (o que existe sera guardado, nao apagado)"):
        raise typer.Exit(code=1)
    try:
        r = restore_backup(Path(file), config_dir=Path("config"), data_dir=Path("data"),
                           db_restore=None if no_db else docker_pg_restore)
    except BackupError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=1)
    console.print(f"[green]Restaurado:[/green] {r['config']} arquivos de config, {r['data']} de dados, banco={'sim' if r['db'] else 'nao'}")
    for p in r["moved_to"]:
        console.print(f"  versao anterior guardada em: {p}")
    console.print("Reinicie o Jefrey: docker compose restart jefrey-api")


if __name__ == "__main__":
    app()