"""Atalho de compatibilidade: este modulo agora mora em adapters/outbound/embeddings.py."""
import sys

from src.jefrey.adapters.outbound import embeddings as _moved

sys.modules[__name__] = _moved
