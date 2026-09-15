with open('C:\\Users\\Pedro\\jarvis\\src\\jefrey\\api\\main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add include_router after metrics_router
old_include = "app.include_router(metrics_router)"
new_include = """app.include_router(metrics_router)
app.include_router(signing_router)"""

if old_include in content:
    content = content.replace(old_include, new_include, 1)
    with open('C:\\Users\\Pedro\\jarvis\\src\\jefrey\\api\\main.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('SUCCESS: Added signing_router include')
else:
    print('Pattern not found - checking what exists...')
    idx = content.find('app.include_router(metrics_router)')
    if idx != -1:
        print('Found at index', idx)
        print(content[idx:idx+100])