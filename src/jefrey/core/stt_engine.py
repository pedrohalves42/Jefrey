"""Atalho de compatibilidade: este modulo agora mora em adapters/outbound/stt_engine.py."""
import sys

from src.jefrey.adapters.outbound import stt_engine as _moved

sys.modules[__name__] = _moved
