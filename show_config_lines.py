import sys
sys.path.append(r'C:/Users/Pedro/jarvis')
p = open(r'C:\Users\Pedro\jarvis\src\jefrey\core\config.py', 'r', encoding='utf-8').read()
for i, line in enumerate(p.splitlines()[180:210], 181):
    print(f"{i:3}: {line}")