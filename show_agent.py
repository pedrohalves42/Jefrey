import sys
sys.path.append(r'C:/Users/Pedro/jarvis')
p = open(r'C:\Users\Pedro\jarvis\src\jefrey\core\agent.py', 'r', encoding='utf-8').read()
for i, line in enumerate(p.splitlines()[:100], 1):
    print(f"{i:3}: {line}")