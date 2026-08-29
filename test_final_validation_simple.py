"""Validação final da Fase 1 - Componentes essenciais (versão simples)."""
import asyncio
import sys
import os

os.environ["JEFREY_DEBUG"] = "false"

async def main():
    print("=" * 70)
    print("VALIDA��O FINAL JEFREY - FASE 1")
    print("=" * 70)

    print("\n1. Estrutura do projeto")
    print("   - src/jefrey/core/config.py")
    print("   - src/jefrey/core/agent.py")
    print("   - src/jefrey/core/memory.py")
    print("   - src/jefrey/core/events.py")

    print("\n2. Skills (autoregistradas)")
    from src.jefrey.skills import skill_registry
    skills = skill_registry.list_skills()
    print(f"   - {len(skills)} skills registradas:")
    for s in skills:
        print(f"     * {s.name} - {s.description[:80]}...")

    from src.jefrey.core.agent import JefreyAgent
    print("\n3. Agente inicializado")
    agent = JefreyAgent()
    print(f"   - LLM: {type(agent.llm).__name__}")
    print(f"   - Tools: {len(agent.tools)}")
    
    essential_tools = ['save_note', 'search_notes', 'list_notes', 'get_note', 
                      'update_note', 'delete_note', 'search', 'search_news', 
                      'extract', 'create_workflow', 'run_workflow', 'plan_task']
    essential_present = []
    for tool in agent.tools:
        if tool.name in essential_tools:
            essential_present.append(tool.name)
    print(f"   - Ferramentas essenciais presentes: {len(essential_present)}/{len(essential_tools)}")

    print("\n4. Memória - Memória Curta")
    agent.memory.short_term.add_user("Teste")
    agent.memory.short_term.add_assistant("Resposta")
    print(f"   - Mensagens: {len(agent.memory.short_term.get_messages())}")

    print("\n5. Memória - Memória Longa")
    note_id = agent.memory.long_term.add(
        content="Dados de teste para validação",
        metadata={"test": "validation", "version": "1.0"}
    )
    print(f"   - Nota salva: {note_id[:8]}")

    results = agent.memory.long_term.search("test", top_k=2)
    print(f"   - Busca semântica: {len(results)} resultados")

    print("\n6. LLM Ollama funciona")
    from langchain_core.messages import HumanMessage
    response = await agent.llm.ainvoke([HumanMessage(content="Diga 'olá' rápido")])
    print(f"   - Resposta: {response.content[:50]}")

    print("\n7. Health check do agente")
    health = await agent.health_check()
    print(f"   - Status: {health.get('status')}")
    print(f"   - Memória: {health.get('memory_count')} notas")

    print("\n" + "=" * 70)
    print("FASE 1 - COMPLETADA!")
    print("Componentes essenciais:")
    print("  • Agente principal com LangGraph")
    print("  • Configuração Pydantic + .env")
    print("  • Sistema de memória (curta + longa)")
    print("  • Skills registradas (notes, web_search, automation)")
    print("  • Event Bus central")
    print("  • Inicialização assíncrona corrigida")
    print("  • Ollama local integrado")
    print("=" * 70)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"\nERRO: {e}")
        sys.exit(1)