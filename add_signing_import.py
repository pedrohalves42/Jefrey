with open('C:\\Users\\Pedro\\jarvis\\src\\jefrey\\api\\main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add import after the metrics_import line
old_import = "from src.jefrey.core.metrics import SERVICE_HEALTH, UPTIME"
new_import = """from src.jefrey.core.metrics import SERVICE_HEALTH, UPTIME
from src.jefrey.api.signing_routes import router as signing_router"""

if old_import in content:
    content = content.replace(old_import, new_import, 1)
    with open('C:\\Users\\Pedro\\jarvis\\src\\jefrey\\api\\main.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('SUCCESS: Added signing_routes import')
else:
    print('Pattern not found - checking what exists...')
    # Show what's around the metrics import
    idx = content.find('from src.jefrey.core.metrics')
    if idx != -1:
        print('Found at index', idx)
        print(content[idx:idx+200])