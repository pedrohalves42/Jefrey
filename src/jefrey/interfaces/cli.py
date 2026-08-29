"""CLI Interativo Profissional - Jefrey."""
from __future__ import annotations
import asyncio
import sys
import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Prompt
from rich.table import Table
from rich.live import Live
from rich.spinner import Spinner
from rich.text import Text

# Adiciona src ao path para imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.jefrey.core.agent import JefreyAgent
from src.jefrey.core.config import get_settings, reload_settings
from src.jefrey.core.memory import get_memory_manager
from src.jefrey.skills import skill_registry
from src.jefrey.core.events import event_bus, SystemEvents

app = typer.Typer(
    name="jefrey",
    help="Jefrey - Assistente Pessoal de IA Avançado",
    add_completion=False,
    no_args_is_help=False,
)

console = Console()


class CLIInterface:
    """Interface CLI rica e interativa."""
    
    def __init__(self):
        self.agent: JefreyAgent | None = None
        self.thread_id = "cli_session"
        self.running = False
        self._setup_event_handlers()
    
    def _setup_event_handlers(self):
        @event_bus.on(SystemEvents.TOOL_CALL)
        async def on_tool_call(event):
            tool_name = event.data.get("tool", "")
            console.print(f"[dim]🔧 Executando: [bold]{tool_name}[/bold][/dim]")
        
        @event_bus.on(SystemEvents.TOOL_RESULT)
        async def on_tool_result(event):
            tool_name = event.data.get("tool", "")
            success = event.data.get("success", False)
            if success:
                console.print(f"[dim green]✓ {tool_name} concluído[/dim green]")
            else:
                error = event.data.get("error", "Erro desconhecido")
                console.print(f"[dim red]✗ {tool_name} falhou: {error}[/dim red]")
    
    async def initialize(self) -> bool:
        """Inicializa agente e skills."""
        with console.status("[bold blue]Inicializando Jefrey...", spinner="dots"):
            try:
                # Registra skills automaticamente (import side-effect)
                from src.jefrey.skills import notes, web_search, calendar, email, automation
                
                tools = skill_registry.get_all_tools()
                self.agent = JefreyAgent(tools=tools)
                
                # Health check
                health = await self.agent.health_check()
                
                if health["status"] == "healthy":
                    console.print("[green]✅ Jefrey inicializado com sucesso![/green]")
                else:
                    console.print(f"[yellow]⚠️ Jefrey iniciado com limitações: {health}[/yellow]")
                
                return True
            except Exception as e:
                console.print(f"[red]❌ Erro ao inicializar: {e}[/red]")
                return False
    
    def print_welcome(self):
        """Exibe boas-vindas."""
        cfg = get_settings()
        
        welcome_text = f"""
# 🤖 Jefrey v{cfg.version}

Olá, **{cfg.user_name}**! Sou seu assistente pessoal de IA.

## 🛠️ Skills Carregadas
"""
        skills = skill_registry.list_skills()
        for skill in skills:
            status = "🟢" if skill.enabled_by_default else "🔴"
            welcome_text += f"- {status} **{skill.name}**: {skill.description}\n"
        
        welcome_text += """
## 💡 Comandos Especiais
- `/help` - Mostra esta ajuda
- `/skills` - Lista skills e ferramentas
- `/memory` - Mostra estatísticas de memória
- `/health` - Verifica saúde do sistema
- `/clear` - Limpa histórico da conversa
- `/reload` - Recarrega configurações
- `/exit` ou `Ctrl+C` - Sai do programa

## 🎯 Exemplos
- "Salva nota: título 'Reunião', conteúdo 'Discutir Q4', tags ['#trabalho']"
- "Busca na web: últimos lançamentos IA generativa"
- "Cria workflow: nome 'relatório-semanal', steps [...]
- "Qual minha nota sobre 'projeto Alpha'?"
"""
        console.print(Panel(Markdown(welcome_text), title="🤖 Jefrey", border_style="blue"))
    
    async def run_interactive(self):
        """Loop principal interativo."""
        self.running = True
        self.print_welcome()
        
        while self.running:
            try:
                # Prompt com estilo
                user_input = Prompt.ask("\n[bold cyan]Você[/bold cyan]")
                
                if not user_input.strip():
                    continue
                
                # Comandos especiais
                if user_input.startswith("/"):
                    await self._handle_command(user_input)
                    continue
                
                # Processa mensagem normal
                await self._process_message(user_input)
                
            except KeyboardInterrupt:
                console.print("\n[yellow]Encerrando...[/yellow]")
                break
            except EOFError:
                break
            except Exception as e:
                console.print(f"[red]Erro: {e}[/red]")
        
        console.print("[blue]Até logo! 👋[/blue]")
    
    async def _process_message(self, user_input: str):
        """Processa mensagem do usuário com streaming visual."""
        with Live(Spinner("dots", text="[bold green]Jefrey está pensando..."), console=console, transient=True):
            response = await self.agent.run(user_input, thread_id=self.thread_id)
        
        # Exibe resposta formatada
        console.print(Panel(Markdown(response), title="🤖 Jefrey", border_style="green", padding=(1, 2)))
    
    async def _handle_command(self, cmd: str):
        """Processa comandos especiais."""
        cmd = cmd.lower().strip()
        
        if cmd in ("/exit", "/quit", "/q"):
            self.running = False
            
        elif cmd == "/help":
            self.print_welcome()
            
        elif cmd == "/skills":
            self._show_skills()
            
        elif cmd == "/memory":
            await self._show_memory()
            
        elif cmd == "/health":
            await self._show_health()
            
        elif cmd == "/clear":
            self.agent.memory.clear_short_term()
            self.thread_id = f"cli_session_{__import__('uuid').uuid4().hex[:8]}"
            console.print("[green]✅ Histórico limpo, nova sessão iniciada[/green]")
            
        elif cmd == "/reload":
            reload_settings()
            console.print("[green]✅ Configurações recarregadas[/green]")
            
        else:
            console.print(f"[yellow]Comando desconhecido: {cmd}. Use /help[/yellow]")
    
    def _show_skills(self):
        """Mostra skills e ferramentas disponíveis."""
        table = Table(title="🛠️ Skills e Ferramentas")
        table.add_column("Skill", style="cyan")
        table.add_column("Descrição", style="white")
        table.add_column("Ferramentas", style="green")
        table.add_column("Status", style="yellow")
        
        for skill_meta in skill_registry.list_skills():
            skill_obj = skill_registry.get_skill(skill_meta.name)
            tools = [t.name for t in skill_obj.get_tools()] if skill_obj else []
            status = "🟢 Ativa" if skill_obj and skill_obj.is_initialized else "🔴 Inativa"
            table.add_row(skill_meta.name, skill_meta.description, ", ".join(tools), status)
        
        console.print(table)
    
    async def _show_memory(self):
        """Mostra estatísticas de memória."""
        mem = self.agent.memory
        
        table = Table(title="🧠 Memória")
        table.add_column("Tipo", style="cyan")
        table.add_column("Estatística", style="white")
        table.add_column("Valor", style="green")
        
        st = mem.short_term
        table.add_row("Curto Prazo", "Mensagens", str(len(st)))
        table.add_row("Curto Prazo", "Tokens estimados", str(st.token_count))
        
        lt_count = mem.long_term.count()
        table.add_row("Longo Prazo", "Total de memórias", str(lt_count))
        
        console.print(table)
        
        # Mostra memórias recentes
        recent = mem.long_term.list_recent(5)
        if recent:
            console.print("\n[bold]Memórias Recentes:[/bold]")
            for m in recent:
                tags = m["metadata"].get("tags", [])
                tag_str = " ".join(f"[dim]{t}[/dim]" for t in tags)
                console.print(f"  • {m['content'][:80]}... {tag_str}")
    
    async def _show_health(self):
        """Mostra health check."""
        health = await self.agent.health_check()
        
        table = Table(title="🏥 Health Check")
        table.add_column("Componente", style="cyan")
        table.add_column("Status", style="white")
        table.add_column("Detalhes", style="green")
        
        for key, value in health.items():
            if key == "status":
                status_icon = "🟢" if value == "healthy" else "🟡" if value == "degraded" else "🔴"
                table.add_row("Geral", f"{status_icon} {value}", "")
            else:
                table.add_row(key.capitalize(), "✅" if value == "ok" or (isinstance(value, int) and value > 0) else "❌", str(value))
        
        console.print(table)


# ============================================
# COMANDOS TYPER
# ============================================

@app.command()
def chat(
    thread_id: str = typer.Option("cli_session", "--thread", "-t", help="ID da thread de conversa"),
    message: Optional[str] = typer.Argument(None, help="Mensagem única (modo não-interativo)"),
):
    """Inicia chat interativo ou envia mensagem única."""
    cli = CLIInterface()
    
    async def run():
        if not await cli.initialize():
            raise typer.Exit(1)
        
        if message:
            # Modo não-interativo
            response = await cli.agent.run(message, thread_id=thread_id)
            console.print(Panel(Markdown(response), title="🤖 Jefrey", border_style="green"))
        else:
            # Modo interativo
            await cli.run_interactive()
    
    asyncio.run(run())


@app.command()
def test():
    """Executa testes de smoke do sistema."""
    from scripts.smoke_test import main
    asyncio.run(main())


@app.command()
def setup():
    """Executa setup inicial (credenciais, diretórios, etc)."""
    from scripts.setup import main
    asyncio.run(main())


@app.command()
def skills():
    """Lista skills disponíveis."""
    from src.jefrey.skills import skill_registry
    from src.jefrey.core.config import get_settings
    
    # Força import das skills
    from src.jefrey.skills import notes, web_search, calendar, email, automation
    
    table = Table(title="🛠️ Skills Registradas")
    table.add_column("Nome", style="cyan")
    table.add_column("Descrição", style="white")
    table.add_column("Ferramentas", style="green")
    table.add_column("Tags", style="yellow")
    table.add_column("Auth", style="red")
    
    for skill_meta in skill_registry.list_skills():
        skill_obj = skill_registry.get_skill(skill_meta.name)
        tools = [t.name for t in skill_obj.get_tools()] if skill_obj else []
        table.add_row(
            skill_meta.name,
            skill_meta.description,
            ", ".join(tools),
            ", ".join(skill_meta.tags),
            "🔐" if skill_meta.requires_auth else "🔓",
        )
    
    console.print(table)


@app.command()
def health():
    """Verifica saúde do sistema."""
    from src.jefrey.core.agent import JefreyAgent
    from src.jefrey.skills import skill_registry
    from src.jefrey.skills import notes, web_search, calendar, email, automation
    
    async def check():
        tools = skill_registry.get_all_tools()
        agent = JefreyAgent(tools=tools)
        health = await agent.health_check()
        
        table = Table(title="🏥 Health Check")
        table.add_column("Componente", style="cyan")
        table.add_column("Status", style="white")
        table.add_column("Detalhes", style="green")
        
        for key, value in health.items():
            if key == "status":
                status_icon = "🟢" if value == "healthy" else "🟡" if value == "degraded" else "🔴"
                table.add_row("Geral", f"{status_icon} {value}", "")
            else:
                table.add_row(key.capitalize(), "✅" if value == "ok" or (isinstance(value, int) and value > 0) else "❌", str(value))
        
        console.print(table)
    
    asyncio.run(check())


@app.command()
def version():
    """Mostra versão."""
    from src.jefrey import __version__
    console.print(f"Jefrey v{__version__}")


if __name__ == "__main__":
    app()