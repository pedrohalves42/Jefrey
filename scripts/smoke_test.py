"""Smoke Test - Verificação rápida do sistema Jefrey."""
from __future__ import annotations
import asyncio
import sys
from pathlib import Path

# Garante saída UTF-8 mesmo em consoles cp1252 (evita UnicodeEncodeError com emojis do rich).
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Adiciona src e raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()


async def test_config():
    """Testa configurações."""
    from src.jefrey.core.config import get_settings
    
    settings = get_settings()
    assert settings.name == "Jefrey"
    assert settings.version == "0.1.0"
    assert settings.llm.provider in ("openai", "anthropic", "ollama")
    return True, "Configurações carregadas"


async def test_memory():
    """Testa sistema de memória."""
    from src.jefrey.core.memory import get_memory_manager
    
    mem = get_memory_manager()
    
    # Teste memória curta
    mem.short_term.add_user("Olá")
    mem.short_term.add_assistant("Oi!")
    assert len(mem.short_term) == 2
    
    # Teste memória longa
    note_id = mem.long_term.add("Teste de memória", metadata={"test": True})
    assert note_id is not None
    
    results = mem.long_term.search("memória", top_k=1)
    assert len(results) >= 1
    
    # Cleanup
    mem.long_term.delete(note_id)
    mem.short_term.clear()
    
    return True, f"Memória OK (longo prazo: {mem.long_term.count()} itens)"


async def test_skills_loading():
    """Testa carregamento de skills."""
    from src.jefrey.skills import skill_registry
    
    # Importa skills para registrar
    from src.jefrey.skills import notes, web_search, calendar, email, automation
    
    skills = skill_registry.list_skills()
    assert len(skills) >= 3  # notes, web_search, automation no mínimo
    
    tools = skill_registry.get_all_tools()
    tool_names = [t.name for t in tools]
    
    # Verifica tools essenciais
    essential_tools = ["save_note", "search_notes", "search"]
    for et in essential_tools:
        assert any(et in t for t in tool_names), f"Tool essencial não encontrada: {et}"
    
    return True, f"Skills: {len(skills)} carregadas, {len(tools)} ferramentas"


async def test_agent_basic():
    """Testa agente básico (sem LLM real se não configurado)."""
    from src.jefrey.core.agent import JefreyAgent
    from src.jefrey.skills import skill_registry
    from src.jefrey.skills import notes, web_search, automation
    
    tools = skill_registry.get_all_tools()
    agent = JefreyAgent(tools=tools)
    
    # Health check
    health = await agent.health_check()
    assert "status" in health
    
    return True, f"Agente OK - Status: {health['status']}"


async def test_notes_skill():
    """Testa skill de notas completa."""
    from src.jefrey.skills import skill_registry
    from src.jefrey.skills import notes
    
    skill_obj = skill_registry.get_skill("notes")
    assert skill_obj is not None
    assert skill_obj.is_initialized
    
    tools = {t.name: t for t in skill_obj.get_tools()}
    
    # Salva nota
    result = await tools["save_note"].ainvoke({
        "title": "Teste Smoke",
        "content": "Conteúdo de teste para smoke test",
        "tags": ["#test", "#smoke"],
    })
    assert result["saved"]
    note_id = result["id"]
    
    # Busca nota
    results = await tools["search_notes"].ainvoke({"query": "smoke test"})
    assert len(results) >= 1
    
    # Lista notas
    listed = await tools["list_notes"].ainvoke({"limit": 5})
    assert len(listed) >= 1
    
    # Cleanup
    await tools["delete_note"].ainvoke({"note_id": note_id})
    
    return True, "Skill Notes: CRUD completo funcionando"


async def test_web_search_skill():
    """Testa skill de busca web (se API key configurada)."""
    import os
    from src.jefrey.skills import skill_registry
    from src.jefrey.skills import web_search
    
    if not os.getenv("TAVILY_API_KEY"):
        return True, "Skill Web Search: TAVILY_API_KEY não configurado (pulando)"
    
    skill_obj = skill_registry.get_skill("web_search")
    if not skill_obj or not skill_obj.is_initialized:
        return False, "Skill Web Search: não inicializada (verifique TAVILY_API_KEY)"
    
    tools = {t.name: t for t in skill_obj.get_tools()}
    
    result = await tools["search"].ainvoke({"query": "Python 3.12 features", "max_results": 2})
    assert "results" in result
    assert len(result["results"]) > 0
    
    return True, "Skill Web Search: busca funcionando"


async def test_event_bus():
    """Testa event bus."""
    from src.jefrey.core.events import event_bus, Event, SystemEvents
    
    received = []
    
    async def handler(event: Event):
        received.append(event.name)
    
    event_bus.on("test.event", handler)
    await event_bus.emit_sync("test.event", {"data": "test"})
    
    assert "test.event" in received
    
    # Testa wildcard
    wildcard_received = []
    event_bus.on_any(lambda e: wildcard_received.append(e.name))
    await event_bus.emit_sync("test.wildcard", {})
    assert "test.wildcard" in wildcard_received
    
    return True, "Event Bus: handlers e wildcards funcionando"


async def run_all_tests():
    """Executa todos os testes."""
    tests = [
        ("Configuração", test_config),
        ("Memória", test_memory),
        ("Skills Loading", test_skills_loading),
        ("Agente Básico", test_agent_basic),
        ("Skill Notes", test_notes_skill),
        ("Skill Web Search", test_web_search_skill),
        ("Event Bus", test_event_bus),
    ]
    
    results = []
    
    console.print(Panel("[bold blue]🧪 Jefrey Smoke Test[/bold blue]", border_style="blue"))
    
    for name, test_func in tests:
        try:
            with console.status(f"[yellow]Testando {name}...", spinner="dots"):
                success, message = await test_func()
            results.append((name, True, message))
            console.print(f"[green]✅ {name}[/green]: {message}")
        except Exception as e:
            results.append((name, False, str(e)))
            console.print(f"[red]❌ {name}[/red]: {e}")
    
    # Resumo
    table = Table(title="📊 Resumo dos Testes")
    table.add_column("Teste", style="cyan")
    table.add_column("Status", style="white")
    table.add_column("Detalhes", style="green")
    
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    
    for name, ok, msg in results:
        status = "[green]PASS[/green]" if ok else "[red]FAIL[/red]"
        table.add_row(name, status, msg)
    
    console.print(table)
    
    if passed == total:
        console.print(Panel(f"[bold green]🎉 Todos os {total} testes passaram![/bold green]", border_style="green"))
        return 0
    else:
        console.print(Panel(f"[bold red]❌ {total - passed} de {total} testes falharam[/bold red]", border_style="red"))
        return 1


def main():
    """Entry point."""
    # Windows: o psycopg v3 em modo assíncrono (checkpointer Postgres) exige SelectorEventLoop;
    # o ProactorEventLoop padrão do Windows não é suportado.
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)


if __name__ == "__main__":
    main()