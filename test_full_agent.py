import asyncio
import os
# Increase timeout for Ollama
os.environ["OLLAMA_REQUEST_TIMEOUT"] = "300"

from src.jefrey.core.agent import JefreyAgent

async def test_agent():
    print("Creating agent...")
    agent = JefreyAgent()
    print(f"Tools: {[t.name for t in agent.tools]}")
    
    # Test health check
    print("\nHealth check...")
    health = await agent.health_check()
    print(f"Health: {health}")
    
    # Test simple query
    print("\nTesting query...")
    response = await agent.run("Olá, como você está?")
    print(f"Response: {response}")
    
    # Test note saving
    print("\nTesting note save...")
    response = await agent.run("Salve uma nota: 'Teste de integração do Jefrey'")
    print(f"Response: {response}")
    
    # Test note search
    print("\nTesting note search...")
    response = await agent.run("Busque notas sobre Jefrey")
    print(f"Response: {response}")

if __name__ == "__main__":
    asyncio.run(test_agent())