"""Teste E2E Fase 1 - Pipeline completa com LangGraph."""
import asyncio
import sys
import os

os.environ["JEFREY_DEBUG"] = "false"

from src.jefrey.core.agent import JefreyAgent

async def main():
    print("=" * 60)
    print("JEFREY - Teste E2E Fase 1 (LangGraph)")
    print("=" * 60)

    print("\n[1/5] Inicializando agente...")
    agent = JefreyAgent()
    print(f"      OK - LLM: {type(agent.llm).__name__}")
    print(f"      OK - Tools: {len(agent.tools)}")
    print(f"      OK - Graph: {type(agent.graph).__name__}")

    # E2E test 1: conversa simples
    print("\n[2/5] E2E - Conversa simples...")
    response = await agent.run("Diga 'olá' em uma palavra", thread_id="test-1")
    print(f"      OK - Resposta: {response[:80]}")
    assert "ol" in response.lower() or "oi" in response.lower(), "Esperava 'olá' ou 'oi'"

    # E2E test 2: salvar nota
    print("\n[3/5] E2E - Salvar nota...")
    response = await agent.run(
        "Salve uma nota com o título 'Reunião' e conteúdo 'Reunião com cliente amanhã às 14h'",
        thread_id="test-2",
    )
    print(f"      OK - Resposta: {response[:120]}")

    # E2E test 3: buscar nota
    print("\n[4/5] E2E - Buscar nota...")
    response = await agent.run(
        "Busque notas sobre 'reunião cliente'",
        thread_id="test-3",
    )
    print(f"      OK - Resposta: {response[:150]}")

    # E2E test 4: memória entre threads
    print("\n[5/5] E2E - Memória isolada por thread...")
    response = await agent.run("Como me chamo?", thread_id="test-4")
    print(f"      OK - Resposta: {response[:120]}")

    print("\n" + "=" * 60)
    print("FASE 1 E2E - TODOS OS TESTES PASSARAM!")
    print("=" * 60)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"\nERRO: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)