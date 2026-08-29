from src.jefrey.skills import skill_registry
print('Skills:', skill_registry.list_skills())
print('Tools:', list(skill_registry._tools.keys()))