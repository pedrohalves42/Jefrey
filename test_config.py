print('1. Loading config...')
from src.jefrey.core.config import get_settings
print('2. Config module loaded')
s = get_settings()
print('3. Settings loaded')
print('   provider:', s.llm.provider)
print('   model:', s.llm.model)
print('   base_url:', s.llm.base_url)
print('   embeddings model:', s.embeddings.model)