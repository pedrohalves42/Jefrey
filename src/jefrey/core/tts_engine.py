"""Atalho de compatibilidade: este modulo agora mora em adapters/outbound/tts_engine.py."""
import sys

from src.jefrey.adapters.outbound import tts_engine as _moved

sys.modules[__name__] = _moved
