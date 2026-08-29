import sys
sys.path.append(r'C:/Users/Pedro/jarvis')
from src.jefrey.core.config import reload_settings
s = reload_settings()
print('LLM Provider:', s.llm.provider)
print('LLM Model:', s.llm.model)
print('LLM API Key:', s.llm.api_key)
print('LLM Base URL:', s.llm.base_url)
print('Embeddings Model:', s.embeddings.model)
print('Embeddings Base URL:', s.embeddings.base_url)
print('Memory Embedding Model:', s.memory.long_term.embedding_model)