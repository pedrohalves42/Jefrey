import sys, asyncio
sys.path.append(r'C:/Users/Pedro/jarvis')
from src.jefrey.skills import notes, automation, skill_registry
from src.jefrey.core.agent import JefreyAgent

print('Skills:', [s.name for s in skill_registry.list_skills()])
print('Tools:', len(skill_registry.get_all_tools()))

agent = JefreyAgent(tools=skill_registry.get_all_tools())

async def test():
    print('\n=== Teste simples ===')
    resp = await agent.run('Oi')
    print('Resp:', resp[:200])

asyncio.run(test())