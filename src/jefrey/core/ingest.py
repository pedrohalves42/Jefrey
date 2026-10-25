"""Atalho de compatibilidade: este modulo agora mora em domain/ingest.py."""
import sys

from src.jefrey.domain import ingest as _moved

sys.modules[__name__] = _moved
