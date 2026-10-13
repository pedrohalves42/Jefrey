"""Atalho de compatibilidade: este modulo agora mora em application/notify.py."""
import sys

from src.jefrey.application import notify as _moved

sys.modules[__name__] = _moved
