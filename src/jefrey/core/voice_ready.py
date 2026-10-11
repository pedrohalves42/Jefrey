"""Atalho de compatibilidade: este modulo agora mora em adapters/outbound/voice_ready.py."""
import sys

from src.jefrey.adapters.outbound import voice_ready as _moved

sys.modules[__name__] = _moved
