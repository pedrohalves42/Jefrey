"""Atalho de compatibilidade: este modulo agora mora em adapters/outbound/llm_provider.py."""
import sys

from src.jefrey.adapters.outbound import llm_provider as _moved

sys.modules[__name__] = _moved
