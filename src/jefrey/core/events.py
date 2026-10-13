"""Atalho de compatibilidade: este modulo agora mora em application/events.py."""
import sys

from src.jefrey.application import events as _moved

sys.modules[__name__] = _moved
