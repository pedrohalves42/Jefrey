"""Atalho de compatibilidade: este modulo agora mora em application/scheduler.py."""
import sys

from src.jefrey.application import scheduler as _moved

sys.modules[__name__] = _moved
