"""Atalho de compatibilidade: este modulo agora mora em adapters/outbound/secret_store.py."""
import sys

from src.jefrey.adapters.outbound import secret_store as _moved

sys.modules[__name__] = _moved
