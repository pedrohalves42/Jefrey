import sys, asyncio
sys.path.append('C:/Users/Pedro/jarvis')
from src.jefrey.skills import notes, automation, skill_registry
print('Registered skills:', [s.name for s in skill_registry.list_skills()])
print('Tools count:', len(skill_registry.get_all_tools()))
print('Tool names:', [t.name for t in skill_registry.get_all_tools()])
