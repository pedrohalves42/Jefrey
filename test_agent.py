print('1. Loading agent...')
from src.jefrey.core.agent import JefreyAgent
print('2. Agent module loaded')
agent = JefreyAgent()
print('3. Agent created')
print('   tools:', [t.name for t in agent.tools])
print('   llm type:', type(agent.llm).__name__)