print('1. Loading memory...')
from src.jefrey.core.memory import get_memory_manager
print('2. Memory module loaded')
mem = get_memory_manager()
print('3. Memory manager created')
print('   short term max messages:', mem.short_term._max_messages)
print('   long term collection:', mem.long_term._collection.name)
print('   long term count:', mem.long_term.count())