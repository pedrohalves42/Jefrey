"""Teste final Fase 1 - Jefrey."""
import asyncio
import sys
import os

os.environ["JEFREY_DEBUG"] = "false"

from src.jefrey.core.agent import JefreyAgent

async def main():
    print("=" * 60)
    print("JEFREY - Teste Final Fase 1")
    print("=" * 60)

    print("\n[1/4] Inicializando agente...")
    agent = JefreyAgent()
    print(f"      OK - LLM: {type(agent.llm).__name__}")
    print(f"      OK - Tools: {len(agent.tools)}")

    # Teste direto do LLM (mais rápido que LangGraph)
    print("\n[2/4] Testando LLM (Ollama)...")
    from langchain_core.messages import HumanMessage
    response = await agent.llm.ainvoke([HumanMessage(content="Diga 'olá' em português")])
    print(f"      OK - Resposta: {response.content[:100]}")

    # Teste de memória curta
    print("\n[3/4] Testando memória curta...")
    agent.memory.short_term.add_user("Olá")
    agent.memory.short_term.add_assistant("Olá! Como posso ajudar?")
    msgs = agent.memory.short_term.get_messages()
    print(f"      OK - Mensagens: {len(msgs)}")

    # Teste de memória longa (save + search)
    print("\n[4/4] Testando memória longa (ChromaDB)...")
    note_id = agent.memory.long_term.add(
        content="Pedro gosta de café sem açúcar",
        metadata={"type": "preference", "user": "Pedro"},
    )
    print(f"      OK - Nota salva: {note_id[:8]}")

    results = agent.memory.long_term.search("preferências de Pedro", top_k=3)
    print(f"      OK - Busca: {len(results)} resultados")
    if results:
        print(f"      OK - Top: {results[0]['content'][:50]}...")

    print("\n" + "=" * 60)
    print("FASE 1 - TODOS OS TESTES PASSARAM!")
    print("=" * 60)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"\nERRO: {e}", file=sys.stderr)
        sys.exit(1)